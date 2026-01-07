# -*- coding: utf-8 -*-
"""
Módulo para geração de processo integral de normas jurídicas.
Adaptado de processo_leg.py para trabalhar com normas ao invés de matérias.
"""
import os
import shutil
import tempfile
import json
import time
import logging
from typing import List, Dict, Any, Tuple
from DateTime import DateTime
from five import grok
from zope.interface import Interface
from datetime import date, datetime
from openlegis.sagl import get_base_path
from Products.CMFCore.utils import getToolByName
from z3c.saconfig import named_scoped_session
from sqlalchemy import and_, or_
from openlegis.sagl.models.models import (
    NormaJuridica, TipoNormaJuridica, VinculoNormaJuridica,
    MateriaLegislativa, TipoMateriaLegislativa
)
from openlegis.sagl.browser.processo_norma.processo_norma_utils import (
    get_processo_norma_dir,
    get_processo_norma_dir_hash,
    get_cache_norma_file_path,
    TEMP_DIR_PREFIX_NORMA
)
from openlegis.sagl.browser.processo_leg.processo_leg_utils import (
    safe_check_file,
    secure_path_join
)

# Configuração de logging
logger = logging.getLogger(__name__)

# Configuração SQLAlchemy
Session = named_scoped_session('minha_sessao')

def _convert_to_datetime_string(date_obj):
    """Converte objetos datetime.date ou datetime.datetime para string"""
    if date_obj is None:
        return None
    if isinstance(date_obj, (date, datetime)):
        if isinstance(date_obj, datetime):
            return date_obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return date_obj.strftime('%Y-%m-%d')
    return str(date_obj)

class PDFGenerationError(Exception):
    """Exceção personalizada para erros na geração de PDF"""
    pass

class SecurityError(Exception):
    """Exceção para problemas de segurança"""
    pass


class ProcessoNormaView(grok.View):
    """Visualização principal para geração do processo integral de normas jurídicas em PDF"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_norma_integral')

    def _get_session(self):
        """Retorna sessão SQLAlchemy thread-safe"""
        return Session()

    def _get_dir_hash(self, cod_norma):
        """Retorna o hash do diretório para um cod_norma (cached)"""
        if not hasattr(self, '_dir_hash_cache'):
            self._dir_hash_cache = {}
        cod_str = str(cod_norma)
        if cod_str not in self._dir_hash_cache:
            self._dir_hash_cache[cod_str] = get_processo_norma_dir_hash(cod_norma)
        return self._dir_hash_cache[cod_str]

    def update(self):
        """Extrai parâmetros da requisição antes do render"""
        self.cod_norma = self.request.form.get('cod_norma')
        self.action = self.request.form.get('action', 'json')

    @property
    def temp_base(self) -> str:
        """Diretório base temporário seguro"""
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        base = os.path.abspath(os.path.join(install_home, 'var', 'tmp'))
        try:
            os.makedirs(base, mode=0o700, exist_ok=True)
        except Exception as e:
            logger.error(f"Não foi possível criar base temp '{base}': {e}")
            raise PDFGenerationError(f"Falha na preparação dos diretórios: {e}")
        return base

    def preparar_diretorios(self, cod_norma: str) -> Tuple[str, str]:
        """Cria diretórios temporários de trabalho com segurança"""
        try:
            if not cod_norma or not str(cod_norma).isdigit():
                raise ValueError("Código da norma inválido")

            dir_base = get_processo_norma_dir(cod_norma)
            
            temp_base_abs = os.path.abspath(self.temp_base)
            dir_base_abs = os.path.abspath(dir_base)
            if not dir_base_abs.startswith(temp_base_abs + os.sep):
                raise SecurityError(f"Diretório do processo fora do temp_base permitido: {dir_base}")
            
            if os.path.exists(dir_base):
                shutil.rmtree(dir_base, ignore_errors=True)
            os.makedirs(dir_base, mode=0o700, exist_ok=True)
            
            dir_paginas = secure_path_join(dir_base, 'pages')
            os.makedirs(dir_paginas, mode=0o700, exist_ok=True)

            return dir_base, dir_paginas

        except Exception as e:
            logger.error(f"Erro ao preparar diretórios: {e}", exc_info=True)
            raise PDFGenerationError(f"Falha na preparação dos diretórios: {e}")

    def obter_dados_norma(self, cod_norma):
        """Obtém informações básicas da norma jurídica com validação - SQLAlchemy"""
        try:
            if not cod_norma or not str(cod_norma).isdigit():
                raise ValueError("Código da norma inválido")

            session = self._get_session()
            try:
                result = session.query(NormaJuridica, TipoNormaJuridica)\
                    .join(TipoNormaJuridica, 
                          NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(NormaJuridica.cod_norma == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
                
                if not result:
                    raise ValueError("Norma não encontrada")
                
                norma_obj, tipo_obj = result
                
                data_norma = _convert_to_datetime_string(norma_obj.dat_norma)
                
                return {
                    'id': f"{tipo_obj.sgl_tipo_norma}-{norma_obj.num_norma}-{norma_obj.ano_norma}",
                    'id_exibicao': f"{tipo_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma}",
                    'tipo': tipo_obj.sgl_tipo_norma,
                    'numero': norma_obj.num_norma,
                    'ano': norma_obj.ano_norma,
                    'data_norma': data_norma,
                    'descricao': tipo_obj.des_tipo_norma,
                    'cod_norma': norma_obj.cod_norma
                }
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Erro ao obter dados da norma: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha ao obter dados da norma: {str(e)}")

    def coletar_documentos(self, dados_norma: Dict, dir_base: str) -> List[Dict]:
        """Coleta documentos relacionados à norma"""
        documentos = []

        try:
            # Texto integral da norma
            arquivo_texto = f"{dados_norma['cod_norma']}_texto_integral.pdf"
            data_norma_str = _convert_to_datetime_string(dados_norma['data_norma'])
            data_texto = DateTime(data_norma_str, datefmt='international').strftime('%Y-%m-%d 00:00:01')

            if self._safe_has_file(self.context.sapl_documentos.norma_juridica, arquivo_texto):
                documentos.append({
                    "data": data_texto,
                    "path": self.context.sapl_documentos.norma_juridica,
                    "file": arquivo_texto,
                    "title": f"{dados_norma['descricao']} nº {dados_norma['numero']}/{dados_norma['ano']}"
                })

            # Matérias relacionadas - SQLAlchemy
            session = self._get_session()
            try:
                materias = session.query(MateriaLegislativa, TipoMateriaLegislativa)\
                    .join(TipoMateriaLegislativa, 
                          MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                    .filter(MateriaLegislativa.cod_norma == dados_norma['cod_norma'])\
                    .filter(MateriaLegislativa.ind_excluido == 0)\
                    .all()
                
                for materia_obj, tipo_obj in materias:
                    arquivo_materia = f"{materia_obj.cod_materia}_texto_integral.pdf"
                    if self._safe_has_file(self.context.sapl_documentos.materia, arquivo_materia):
                        data_materia_str = _convert_to_datetime_string(materia_obj.dat_apresentacao)
                        documentos.append({
                            "data": DateTime(data_materia_str, datefmt='international').strftime('%Y-%m-%d 00:00:02'),
                            "path": self.context.sapl_documentos.materia,
                            "file": arquivo_materia,
                            "title": f"{tipo_obj.sgl_tipo_materia} {materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica} (matéria relacionada)"
                        })
            finally:
                session.close()

            # Normas relacionadas (vinculadas) - SQLAlchemy
            session = self._get_session()
            try:
                vinculos = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_relacionada == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma == dados_norma['cod_norma'])\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                for vinculo_obj, norma_obj, tipo_obj in vinculos:
                    arquivo_norma = f"{norma_obj.cod_norma}_texto_integral.pdf"
                    if self._safe_has_file(self.context.sapl_documentos.norma_juridica, arquivo_norma):
                        data_norma_str = _convert_to_datetime_string(norma_obj.dat_norma)
                        documentos.append({
                            "data": DateTime(data_norma_str, datefmt='international').strftime('%Y-%m-%d 00:00:03'),
                            "path": self.context.sapl_documentos.norma_juridica,
                            "file": arquivo_norma,
                            "title": f"{tipo_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma} (norma relacionada)"
                        })
            finally:
                session.close()

            # Ordenar por data
            documentos.sort(key=lambda x: x['data'])
            return documentos

        except Exception as e:
            logger.error(f"Erro ao coletar documentos: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha na coleta de documentos: {str(e)}")

    def _safe_has_file(self, container, filename: str) -> bool:
        """Verifica se um arquivo existe no container"""
        return safe_check_file(container, filename)

    def render(self):
        """Método render - verificação de documentos prontos"""
        try:
            if not self.cod_norma:
                raise ValueError("O parâmetro cod_norma é obrigatório")

            if self.action == 'download':
                try:
                    dados_norma = self.obter_dados_norma(self.cod_norma)
                    nome_arquivo_download = f"{dados_norma['tipo']}_{dados_norma['numero']}_{dados_norma['ano']}.pdf"
                    
                    dir_base = get_processo_norma_dir(self.cod_norma)
                    nome_arquivo_final = f"processo_norma_integral_{self.cod_norma}.pdf"
                    caminho_arquivo_final = os.path.join(dir_base, nome_arquivo_final)
                    
                    if os.path.exists(caminho_arquivo_final):
                        with open(caminho_arquivo_final, 'rb') as f:
                            pdf_data = f.read()
                        
                        self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
                        self.request.RESPONSE.setHeader(
                            'Content-Disposition',
                            f'inline; filename="{nome_arquivo_download}"'
                        )
                        self.request.RESPONSE.setHeader('Content-Length', str(len(pdf_data)))
                        return pdf_data
                    else:
                        error_msg = f"Arquivo não encontrado: {nome_arquivo_download}. O processo ainda não foi gerado."
                        logger.warning(f"[ProcessoNormaView] Arquivo não encontrado para download: {caminho_arquivo_final}")
                        self.request.RESPONSE.setStatus(404)
                        self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
                        return error_msg
                        
                except Exception as download_err:
                    logger.error(f"[ProcessoNormaView] Erro ao fazer download: {download_err}", exc_info=True)
                    self.request.RESPONSE.setStatus(500)
                    self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
                    return f"Erro ao fazer download: {str(download_err)}"

            skip_signature_check = self.request.form.get('skip_signature_check') == '1'
            
            if not skip_signature_check:
                error_msg = "Geração síncrona de PDF não é mais suportada. Use sempre o modo assíncrono (Celery task)."
                logger.warning(f"[ProcessoNormaView] Tentativa de geração síncrona rejeitada para cod_norma={self.cod_norma}")
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'error': error_msg,
                    'success': False,
                    'cod_norma': self.cod_norma
                })
            
            try:
                dados_norma = self.obter_dados_norma(self.cod_norma)
                dir_base = get_processo_norma_dir(self.cod_norma)
                
                if not os.path.exists(dir_base):
                    result = {
                        'documentos': [],
                        'total_paginas': 0,
                        'cod_norma': self.cod_norma
                    }
                    if self.action == 'json':
                        self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                        return json.dumps(result)
                    return result
                
                dir_paginas = secure_path_join(dir_base, 'pages')
                metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                
                if skip_signature_check:
                    time.sleep(0.5)
                
                metadados_existe = os.path.exists(metadados_path)
                dir_paginas_existe = os.path.exists(dir_paginas)
                
                if dir_paginas_existe and not metadados_existe:
                    if skip_signature_check:
                        max_retries = 10
                        base_delay = 0.5
                    else:
                        max_retries = 3
                        base_delay = 0.5
                    
                    for retry in range(max_retries):
                        retry_delay = base_delay * (retry + 1)
                        time.sleep(retry_delay)
                        metadados_existe = os.path.exists(metadados_path)
                        if metadados_existe:
                            break
                
                if metadados_existe and dir_paginas_existe:
                    with open(metadados_path, 'r', encoding='utf-8') as f:
                        metadados = json.load(f)
                    
                    pdf_files = [f for f in os.listdir(dir_paginas) if f.endswith('.pdf') and f.startswith('pg_')]
                    
                    if pdf_files and len(pdf_files) > 0:
                        base_url = f"{self.context.absolute_url()}/@@pagina_processo_norma_integral"
                        documentos_formatados = []
                        
                        try:
                            cache_bust_ts = int(os.path.getmtime(metadados_path))
                        except (OSError, ValueError):
                            cache_bust_ts = int(time.time())
                        cache_bust_param = f"&_t={cache_bust_ts}"
                        
                        if 'documentos' in metadados and len(metadados['documentos']) > 0:
                            for i, doc_meta in enumerate(metadados['documentos'], 1):
                                doc_id = f"{i:04d}.pdf"
                                start_page = doc_meta.get('start_page', 1)
                                end_page = doc_meta.get('end_page', 1)
                                first_id = f"pg_{start_page:04d}.pdf"
                                
                                paginas = []
                                for page_num in range(start_page, end_page + 1):
                                    pg_id = f"pg_{page_num:04d}.pdf"
                                    if os.path.exists(os.path.join(dir_paginas, pg_id)):
                                        paginas.append({
                                            'num_pagina': str(page_num),
                                            'id_pagina': pg_id,
                                            'url': f"{base_url}?cod_norma={self.cod_norma}&pagina={pg_id}{cache_bust_param}"
                                        })
                                
                                if paginas:
                                    documentos_formatados.append({
                                        'id': doc_id,
                                        'title': doc_meta.get('title', ''),
                                        'data': doc_meta.get('data', ''),
                                        'url': f"{base_url}?cod_norma={self.cod_norma}&pagina={first_id}{cache_bust_param}",
                                        'paginas_geral': metadados.get('total_paginas', 0),
                                        'paginas': paginas,
                                        'id_paginas': [p['id_pagina'] for p in paginas],
                                        'paginas_doc': len(paginas)
                                    })
            
                        if documentos_formatados:
                            result = {
                                'documentos': documentos_formatados,
                                'total_paginas': metadados.get('total_paginas', 0),
                                'id_processo': metadados.get('id_processo', ''),
                                'cod_norma': self.cod_norma
                            }
                            
                            if self.action == 'json':
                                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                                return json.dumps(result)
                            return result
                
                result = {
                    'documentos': [],
                    'total_paginas': 0,
                    'cod_norma': self.cod_norma
                }
                
                if self.action == 'json':
                    self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                    return json.dumps(result)
                return result
                
            except Exception as check_err:
                logger.error(f"[ProcessoNormaView] Erro ao verificar documentos prontos: {check_err}", exc_info=True)
                self.request.RESPONSE.setStatus(500)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'error': f"Erro ao verificar documentos prontos: {str(check_err)}",
                    'success': False,
                    'cod_norma': self.cod_norma
                })

        except ValueError as ve:
            logger.error(f"Erro de validação: {str(ve)}")
            self.request.RESPONSE.setStatus(400)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({'error': str(ve), 'success': False})
        except Exception as e:
            logger.error(f"Erro no render: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({'error': str(e), 'success': False})


class PaginaProcessoNorma(grok.View):
    """Visualização para páginas individuais do processo de norma"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_norma_integral')

    @property
    def temp_base(self) -> str:
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        return secure_path_join(install_home, 'var/tmp')

    def render(self):
        """Renderiza uma página individual do processo"""
        try:
            cod_norma = self.request.form.get('cod_norma', '')
            pagina = self.request.form.get('pagina', '')
        except (AttributeError, KeyError):
            try:
                cod_norma = getattr(self.request, 'cod_norma', '')
                pagina = getattr(self.request, 'pagina', '')
            except AttributeError:
                cod_norma = ''
                pagina = ''
        
        if cod_norma:
            cod_norma = str(cod_norma).strip()
        if pagina:
            pagina = str(pagina).strip()
        
        if not cod_norma:
            logger.error("[PaginaProcessoNorma] cod_norma não fornecido")
            self.request.RESPONSE.setStatus(400)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return "Parâmetro cod_norma é obrigatório"
        
        if not pagina:
            logger.error("[PaginaProcessoNorma] pagina não fornecida")
            self.request.RESPONSE.setStatus(400)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return "Parâmetro pagina é obrigatório"
        
        file_path = None
        try:
            dir_base = get_processo_norma_dir(cod_norma)
            dir_pages = secure_path_join(dir_base, 'pages')
            file_path = secure_path_join(dir_pages, pagina)
            
            with open(file_path, 'rb') as f:
                data = f.read()
            self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
            self.request.RESPONSE.setHeader(
                'Content-Disposition',
                f'inline; filename="{pagina}"'
            )
            return data
        except FileNotFoundError:
            logger.error(f"[PaginaProcessoNorma] Arquivo não encontrado: {file_path or pagina}")
            self.request.RESPONSE.setStatus(404)
            return "Página não encontrada"
        except SecurityError as se:
            logger.error(f"[PaginaProcessoNorma] Erro de segurança ao acessar: {file_path or pagina} - {se}")
            self.request.RESPONSE.setStatus(403)
            return "Acesso não permitido"
        except Exception as e:
            logger.error(f"[PaginaProcessoNorma] Erro inesperado: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return f"Erro ao carregar página: {str(e)}"


class LimparProcessoNormaView(grok.View):
    """Visualização para limpeza de diretórios temporários de normas"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_norma_integral_limpar')

    @property
    def temp_base(self) -> str:
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        return os.path.abspath(os.path.join(install_home, 'var/tmp'))

    def render(self, cod_norma):
        try:
            if not cod_norma or not str(cod_norma).isdigit():
                raise ValueError("Código da norma inválido")

            dir_base = get_processo_norma_dir(cod_norma)

            if not os.path.abspath(dir_base).startswith(self.temp_base):
                raise SecurityError("Tentativa de acesso a caminho não permitido")

            if os.path.exists(dir_base):
                shutil.rmtree(dir_base)
                return f"Diretório temporário '{dir_base}' removido com sucesso."
            return f"Diretório '{dir_base}' não existe ou já foi removido."

        except SecurityError as e:
            logger.error(f"Erro de segurança: {str(e)}", exc_info=True)
            self.request.RESPONSE.setStatus(403)
            return "Acesso não permitido"

        except Exception as e:
            logger.error(f"Erro ao limpar diretório temporário: {str(e)}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return f"Erro ao limpar diretório temporário: {str(e)}"


class ProcessoNormaTaskExecutor(grok.View):
    """
    View que executa a geração do processo de norma no contexto do Zope.
    Esta view é chamada via HTTP pelo Celery worker.
    """
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_norma_task_executor')

    def _get_session(self):
        """Retorna sessão SQLAlchemy thread-safe"""
        return Session()

    def render(self):
        """Executa a geração do processo de norma"""
        import json as json_lib
        try:
            cod_norma = self.request.form.get('cod_norma') or self.request.get('cod_norma')
            
            if not cod_norma:
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': 'Parâmetro cod_norma é obrigatório', 'success': False})
            
            try:
                cod_norma = int(cod_norma)
            except (ValueError, TypeError):
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': 'cod_norma deve ser um número', 'success': False})
            
            view = ProcessoNormaView(self.context, self.request)
            view.update()
            
            try:
                dados_norma = view.obter_dados_norma(cod_norma)
                dir_base, dir_paginas = view.preparar_diretorios(cod_norma)
                documentos = view.coletar_documentos(dados_norma, dir_base)
                
                id_processo = dados_norma.get('id_exibicao', '')
                
                def default_serializer(obj):
                    if isinstance(obj, str):
                        return obj
                    try:
                        if hasattr(obj, '__name__'):
                            return str(obj.__name__)
                        return str(obj)
                    except Exception:
                        return None
                
                documentos_serializaveis = []
                for doc in documentos:
                    doc_serializavel = {}
                    for key, value in doc.items():
                        if key == 'path' and not isinstance(value, str):
                            doc_serializavel['path'] = str(value) if value else dir_base
                        else:
                            doc_serializavel[key] = value
                    documentos_serializaveis.append(doc_serializavel)
                
                dados_norma_serializavel = {}
                for key, value in dados_norma.items():
                    try:
                        json.dumps(value, default=default_serializer)
                        dados_norma_serializavel[key] = value
                    except (TypeError, ValueError):
                        converted = default_serializer(value)
                        if converted is not None:
                            dados_norma_serializavel[key] = converted
                
                self.request.RESPONSE.setStatus(200)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'success': True,
                    'cod_norma': cod_norma,
                    'dir_base': dir_base,
                    'dir_paginas': dir_paginas,
                    'id_processo': id_processo,
                    'documentos': documentos_serializaveis,
                    'dados_norma': dados_norma_serializavel
                }, default=default_serializer)
                
            except Exception as gen_err:
                logger.error(f"[ProcessoNormaTaskExecutor] Erro ao gerar processo: {gen_err}", exc_info=True)
                self.request.RESPONSE.setStatus(500)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'success': False,
                    'error': str(gen_err),
                    'cod_norma': cod_norma
                })
            
        except Exception as e:
            logger.error(f"[ProcessoNormaTaskExecutor] Erro inesperado: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({'error': str(e), 'success': False})


class ProcessoNormaStatusView(grok.View):
    """View para verificar status da geração do processo de norma"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_norma_integral_status')

    def render(self):
        """Retorna o status da tarefa"""
        from Products.CMFCore.utils import getToolByName
        
        try:
            task_id = self.request.form.get('task_id') or self.request.get('task_id')
            
            if not task_id:
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': 'Parâmetro task_id é obrigatório', 'status': 'ERROR'})
            
            tool = getToolByName(self.context, 'portal_sagl')
            status = tool.get_task_status(task_id)
            
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps(status)
            
        except Exception as e:
            logger.error(f"[ProcessoNormaStatusView] Erro ao verificar status: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({'error': str(e), 'status': 'ERROR'})
