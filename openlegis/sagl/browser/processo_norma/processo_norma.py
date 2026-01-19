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
import urllib.request
import urllib.parse
import urllib.error
from typing import List, Dict, Any, Tuple
from functools import wraps
from DateTime import DateTime
from five import grok
from zope.interface import Interface
from datetime import date, datetime
from openlegis.sagl import get_base_path
from Products.CMFCore.utils import getToolByName
from z3c.saconfig import named_scoped_session
from sqlalchemy import and_, or_
from concurrent.futures import ThreadPoolExecutor
from openlegis.sagl.models.models import (
    NormaJuridica, TipoNormaJuridica, VinculoNormaJuridica,
    MateriaLegislativa, TipoMateriaLegislativa
)
from openlegis.sagl.browser.processo_norma.processo_norma_utils import (
    get_processo_norma_dir,
    get_processo_norma_dir_hash,
    get_cache_norma_file_path,
    TEMP_DIR_PREFIX_NORMA,
    safe_check_file,
    safe_check_files_batch,
    secure_path_join
)

# Configuração de logging melhorada (similar a processo_leg)
def setup_logging():
    """Configura o logging de forma segura sem resource leaks"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Remove handlers existentes para evitar duplicação
    for handler in logger.handlers[:]:
        try:
            handler.close()
            logger.removeHandler(handler)
        except Exception as e:
            print(f"Erro ao fechar handler: {e}")
    
    # Formatter comum
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # FileHandler com contexto seguro
    try:
        base_path = get_base_path()
        log_path = os.path.join(base_path, 'pdf_generation.log')
        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Erro ao criar file handler: {e}")
    
    # StreamHandler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Inicializa o logging
logger = setup_logging()

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

# Limites de segurança (similar a processo_leg)
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB
MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500MB
MAX_PAGES = 5000
MAX_DOCUMENTS = 500

def validate_pdf_content(pdf_bytes: bytes) -> bool:
    """Valida se o conteúdo é um PDF válido e dentro dos limites de tamanho"""
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise PDFGenerationError(f"PDF size exceeds {MAX_PDF_SIZE//(1024*1024)}MB limit")
    if not pdf_bytes.startswith(b'%PDF-'):
        raise PDFGenerationError("Invalid PDF file signature")
    return True

def timeit(func):
    """Decorator para medição de tempo de execução"""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start_time
        return result
    return wrapper


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
            # Capa do processo - usa método padrão do sistema e faz download via HTTP
            arquivo_capa = f"capa_{dados_norma['tipo']}-{dados_norma['numero']}-{dados_norma['ano']}.pdf"
            caminho_capa = secure_path_join(dir_base, arquivo_capa)
            # Converte data_norma para string se necessário
            data_norma_str = _convert_to_datetime_string(dados_norma['data_norma'])
            data_capa = DateTime(data_norma_str, datefmt='international').strftime('%Y-%m-%d 00:00:01')
            
            # Gera a capa usando o método padrão do sistema (gera no temp_folder)
            # IMPORTANTE: modelo_proposicao está em /sagl/portal_skins/sk_sagl/modelo_proposicao
            # Precisa acessar através do caminho completo: portal_skins.sk_sagl.modelo_proposicao
            url_path = None
            cod_para_capa = None
            
                # Tenta usar método específico para normas, se existir
            try:
                # Tenta acessar através do caminho completo
                portal_skins = getattr(self.context, 'portal_skins', None)
                modelo_proposicao = None
                
                if portal_skins:
                    sk_sagl = getattr(portal_skins, 'sk_sagl', None)
                    if sk_sagl:
                        modelo_proposicao = getattr(sk_sagl, 'modelo_proposicao', None)
                
                # Se não encontrou pelo caminho completo, tenta acesso direto via Acquisition
                if modelo_proposicao is None:
                    modelo_proposicao = getattr(self.context, 'modelo_proposicao', None)
                
                # Tenta chamar capa_norma se o método existir
                if modelo_proposicao is not None:
                    if hasattr(modelo_proposicao, 'capa_norma'):
                        modelo_proposicao.capa_norma(cod_norma=dados_norma['cod_norma'], action='gerar')
                        url_path = 'capa_norma'
                    else:
                        logger.warning(f"[coletar_documentos] modelo_proposicao encontrado mas não tem método capa_norma")
                
                # Se não encontrou capa_norma, tenta fallback: usa método de matéria se norma tiver cod_materia
                if url_path is None:
                    session_capa = self._get_session()
                    try:
                        norma_capa = session_capa.query(NormaJuridica)\
                            .filter(NormaJuridica.cod_norma == dados_norma['cod_norma'])\
                            .filter(NormaJuridica.ind_excluido == 0)\
                            .first()
                        
                        if norma_capa and norma_capa.cod_materia:
                            # Acessa modelo_proposicao através do caminho completo
                            if portal_skins:
                                sk_sagl = getattr(portal_skins, 'sk_sagl', None)
                                if sk_sagl:
                                    modelo_proposicao = getattr(sk_sagl, 'modelo_proposicao', None)
                                    if modelo_proposicao:
                                        modelo_proposicao.capa_processo(cod_materia=norma_capa.cod_materia, action='gerar')
                                        url_path = 'capa_processo'
                                        cod_para_capa = norma_capa.cod_materia
                                    else:
                                        # Fallback: tenta acesso direto
                                        modelo_proposicao = getattr(self.context, 'modelo_proposicao', None)
                                        if modelo_proposicao:
                                            modelo_proposicao.capa_processo(cod_materia=norma_capa.cod_materia, action='gerar')
                                            url_path = 'capa_processo'
                                            cod_para_capa = norma_capa.cod_materia
                        else:
                            raise PDFGenerationError("Norma não possui matéria relacionada e não há método capa_norma disponível")
                    finally:
                        session_capa.close()
                        
            except Exception as e:
                logger.error(f"[coletar_documentos] Erro ao gerar/baixar capa do processo: {str(e)}", exc_info=True)
                logger.error(f"[coletar_documentos] Contexto: {type(self.context).__name__}, tem modelo_proposicao: {hasattr(self.context, 'modelo_proposicao')}")
                raise PDFGenerationError(f"Falha ao gerar/baixar capa do processo: {str(e)}")
            
            try:
                # OTIMIZAÇÃO: Polling simplificado - verifica apenas 2 vezes rapidamente
                # Se não estiver pronto, o download com timeout maior vai aguardar a geração
                capa_ready = False
                
                # Primeira verificação rápida após 0.5s
                time.sleep(0.5)
                try:
                    test_url = url if 'url' in locals() else None
                    if test_url:
                        test_req = urllib.request.Request(test_url)
                        test_req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                        test_req.get_method = lambda: 'HEAD'
                        try:
                            with urllib.request.urlopen(test_req, timeout=1) as test_response:
                                if test_response.status == 200:
                                    capa_ready = True
                        except (urllib.error.HTTPError, urllib.error.URLError):
                            pass  # Ainda não está pronto, continua
                except Exception:
                    pass
                
                # Faz download via HTTP (com timeout maior para aguardar geração se necessário)
                base_url = self.context.absolute_url()
                if 'url_path' in locals() and url_path == 'capa_norma':
                    url = f"{base_url}/modelo_proposicao/capa_norma?cod_norma={dados_norma['cod_norma']}&action=download"
                else:
                    url = f"{base_url}/modelo_proposicao/capa_processo?cod_materia={cod_para_capa}&action=download"
                
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                
                try:
                    # Timeout aumentado para 60s - a geração de PDF pode demorar
                    # Se o polling detectou que está pronto, este download será rápido
                    # Se não detectou, o timeout maior permite que a geração termine
                    with urllib.request.urlopen(req, timeout=60) as response:
                        capa_data = response.read()
                    
                    if capa_data and len(capa_data) > 0:
                        # Valida o conteúdo do PDF antes de salvar
                        validate_pdf_content(capa_data)
                        # Salva no filesystem
                        with open(caminho_capa, 'wb') as f:
                            f.write(capa_data)
                    else:
                        raise PDFGenerationError("Download da capa retornou dados vazios")
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 404:
                        raise PDFGenerationError(f"Capa do processo não encontrada (404): {url}")
                    else:
                        raise PDFGenerationError(f"Erro HTTP ao baixar capa: {http_err.code} - {http_err.reason}")
                except Exception as e:
                    raise PDFGenerationError(f"Erro ao baixar capa via HTTP: {str(e)}")
                    
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[coletar_documentos] Erro ao gerar/baixar capa do processo: {str(e)}", exc_info=True)
                logger.error(f"[coletar_documentos] Traceback completo:\n{error_traceback}")
                logger.error(f"[coletar_documentos] Contexto: {type(self.context).__name__}, tem modelo_proposicao: {hasattr(self.context, 'modelo_proposicao')}")
                raise PDFGenerationError(f"Falha ao gerar/baixar capa do processo: {str(e)}")

            documentos.append({
                "data": data_capa,
                "path": dir_base,
                "file": arquivo_capa,
                "title": "Capa da Norma",
                "filesystem": True
            })

            # OTIMIZAÇÃO: Usar uma única sessão SQLAlchemy para todas as queries
            session = self._get_session()
            try:
                # Busca a norma uma vez para reutilizar
                norma = session.query(NormaJuridica)\
                    .filter(NormaJuridica.cod_norma == dados_norma['cod_norma'])\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
                
                if not norma:
                    raise ValueError("Norma não encontrada")
                
                # OTIMIZAÇÃO: Coleta todos os nomes de arquivos para verificação em batch
                arquivos_para_verificar = []
                arquivos_info = {}  # Armazena informações sobre cada arquivo
                
                # Texto integral da norma
                arquivo_texto = f"{dados_norma['cod_norma']}_texto_integral.pdf"
                data_norma_str = _convert_to_datetime_string(dados_norma['data_norma'])
                data_texto = DateTime(data_norma_str, datefmt='international').strftime('%Y-%m-%d 00:00:02')
                arquivos_para_verificar.append(arquivo_texto)
                arquivos_info[arquivo_texto] = {
                    "data": data_texto,
                    "path": self.context.sapl_documentos.norma_juridica,
                    "title": f"{dados_norma['descricao']} nº {dados_norma['numero']}/{dados_norma['ano']}"
                }

                # Texto compilado da norma
                arquivo_compilado = f"{dados_norma['cod_norma']}_texto_consolidado.pdf"
                data_compilado = DateTime(data_norma_str, datefmt='international').strftime('%Y-%m-%d 00:00:03')
                arquivos_para_verificar.append(arquivo_compilado)
                arquivos_info[arquivo_compilado] = {
                    "data": data_compilado,
                    "path": self.context.sapl_documentos.norma_juridica,
                    "title": "Texto Compilado"
                }

                # Matéria relacionada (se houver)
                if norma.cod_materia:
                    materia_result = session.query(MateriaLegislativa, TipoMateriaLegislativa)\
                        .join(TipoMateriaLegislativa, 
                              MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                        .filter(MateriaLegislativa.cod_materia == norma.cod_materia)\
                        .filter(MateriaLegislativa.ind_excluido == 0)\
                        .first()
                    
                    if materia_result:
                        materia_obj, tipo_obj = materia_result
                        arquivo_materia = f"{materia_obj.cod_materia}_texto_integral.pdf"
                        arquivos_para_verificar.append(arquivo_materia)
                        data_materia_str = _convert_to_datetime_string(materia_obj.dat_apresentacao)
                        arquivos_info[arquivo_materia] = {
                            "data": DateTime(data_materia_str, datefmt='international').strftime('%Y-%m-%d 00:00:02'),
                            "path": self.context.sapl_documentos.materia,
                            "title": f"{tipo_obj.sgl_tipo_materia} {materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica} (matéria relacionada)"
                        }

                # OTIMIZAÇÃO: Executa ambas as queries de vínculos na mesma sessão
                # Busca normas onde cod_norma é referente (normas que esta norma referencia)
                vinculos_referente = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referida == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referente == dados_norma['cod_norma'])\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                # Busca normas onde cod_norma é referida (normas que referenciam esta norma)
                vinculos_referida = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referente == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referida == dados_norma['cod_norma'])\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                # Adiciona arquivos de normas relacionadas à lista de verificação
                for vinculo_obj, norma_obj, tipo_obj in vinculos_referente + vinculos_referida:
                    arquivo_norma = f"{norma_obj.cod_norma}_texto_integral.pdf"
                    arquivos_para_verificar.append(arquivo_norma)
                    data_norma_rel_str = _convert_to_datetime_string(norma_obj.dat_norma)
                    arquivos_info[arquivo_norma] = {
                        "data": DateTime(data_norma_rel_str, datefmt='international').strftime('%Y-%m-%d 00:00:03'),
                        "path": self.context.sapl_documentos.norma_juridica,
                        "title": f"{tipo_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma} (norma relacionada)"
                    }

                # Anexos da norma
                from openlegis.sagl.models.models import AnexoNorma
                anexos = session.query(AnexoNorma)\
                    .filter(AnexoNorma.cod_norma == dados_norma['cod_norma'])\
                    .filter(AnexoNorma.ind_excluido == 0)\
                    .order_by(AnexoNorma.cod_anexo)\
                    .all()
                
                for anexo in anexos:
                    id_anexo = f"{dados_norma['cod_norma']}_anexo_{anexo.cod_anexo}"
                    arquivos_para_verificar.append(id_anexo)
                    data_anexo = DateTime(data_norma_str, datefmt='international').strftime('%Y-%m-%d 00:00:04')
                    arquivos_info[id_anexo] = {
                        "data": data_anexo,
                        "path": self.context.sapl_documentos.norma_juridica,
                        "title": f"Anexo {anexo.cod_anexo} - {anexo.txt_descricao or 'Sem descrição'}"
                    }
                
                # OTIMIZAÇÃO: Verifica todos os arquivos em batch por container
                # Agrupa arquivos por container
                arquivos_por_container = {}
                for arquivo in arquivos_para_verificar:
                    info = arquivos_info.get(arquivo, {})
                    container = info.get('path')
                    if container:
                        if container not in arquivos_por_container:
                            arquivos_por_container[container] = []
                        arquivos_por_container[container].append(arquivo)
                
                # Verifica arquivos em batch por container
                arquivos_existentes = set()
                for container, arquivos_list in arquivos_por_container.items():
                    resultados = safe_check_files_batch(container, arquivos_list)
                    arquivos_existentes.update(arquivo for arquivo, existe in resultados.items() if existe)
                
                # Adiciona documentos que existem
                for arquivo in arquivos_para_verificar:
                    if arquivo in arquivos_existentes:
                        info = arquivos_info[arquivo]
                        documentos.append({
                            "data": info["data"],
                            "path": info["path"],
                            "file": arquivo,
                            "title": info["title"],
                            "filesystem": False  # Precisa ser baixado via HTTP
                        })
                        
            except Exception as e:
                logger.warning(f"Erro ao coletar dados do banco: {str(e)}", exc_info=True)
            finally:
                session.close()

            # Ordenação específica para documentos da norma:
            # 1. Capa (sempre primeiro)
            # 2. Texto Integral da própria norma (sempre segundo)
            # 3. Texto Consolidado da própria norma (sempre terceiro)
            # 4. Demais documentos (ordenados por data)
            cod_norma_str = str(dados_norma['cod_norma'])
            
            def get_document_priority(doc):
                """Retorna prioridade do documento para ordenação"""
                file_name = doc.get('file', '')
                title = doc.get('title', '').lower()
                
                # Prioridade 1: Capa
                if file_name.startswith('capa_') or 'capa' in title:
                    return (1, doc.get('data', ''))
                
                # Prioridade 2: Texto Integral da própria norma
                if file_name == f"{cod_norma_str}_texto_integral.pdf":
                    return (2, doc.get('data', ''))
                
                # Prioridade 3: Texto Consolidado da própria norma
                if file_name == f"{cod_norma_str}_texto_consolidado.pdf":
                    return (3, doc.get('data', ''))
                
                # Prioridade 4: Demais documentos (ordenados por data)
                return (4, doc.get('data', ''))
            
            documentos.sort(key=get_document_priority)
            return documentos

        except Exception as e:
            logger.error(f"Erro ao coletar documentos: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha na coleta de documentos: {str(e)}")

    def _safe_has_file(self, container, filename: str) -> bool:
        """Verifica se um arquivo existe no container"""
        return safe_check_file(container, filename)
    
    def _get_container_cache(self, container):
        """Obtém cache de objectIds para um container"""
        if not hasattr(self, '_container_cache'):
            self._container_cache = {}
        container_id = id(container)
        if container_id not in self._container_cache:
            try:
                if hasattr(container, 'objectIds'):
                    self._container_cache[container_id] = set(container.objectIds())
                else:
                    self._container_cache[container_id] = set()
            except Exception as e:
                self._container_cache[container_id] = set()
        return self._container_cache[container_id]
    
    def _safe_has_file_cached(self, container, filename: str) -> bool:
        """Verifica se um arquivo existe no container usando cache"""
        obj_ids = self._get_container_cache(container)
        exists = filename in obj_ids
        if not exists and filename.lower().endswith('.pdf'):
            base = filename[:-4]
            exists = base in obj_ids
        return exists

    @timeit
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
                                        'file': doc_meta.get('file', ''),  # NOVO: Inclui nome do arquivo original para download
                                        'title': doc_meta.get('title', ''),
                                        'data': doc_meta.get('data', ''),
                                        'url': f"{base_url}?cod_norma={self.cod_norma}&pagina={first_id}{cache_bust_param}",
                                        'paginas_geral': metadados.get('total_paginas', 0),
                                        'paginas': paginas,
                                        'id_paginas': [p['id_pagina'] for p in paginas],
                                        'paginas_doc': len(paginas)
                                    })
            
                        if documentos_formatados:
                            # Aplica a mesma ordenação: Capa, Texto Integral, Texto Consolidado, demais documentos
                            cod_norma_str = str(self.cod_norma)
                            
                            def get_document_priority_for_meta(doc):
                                """Retorna prioridade do documento para ordenação (versão para metadados)"""
                                file_name = doc.get('file', '')
                                title = doc.get('title', '').lower()
                                
                                # Prioridade 1: Capa
                                if file_name.startswith('capa_') or 'capa' in title:
                                    return (1, doc.get('data', ''))
                                
                                # Prioridade 2: Texto Integral da própria norma
                                if file_name == f"{cod_norma_str}_texto_integral.pdf":
                                    return (2, doc.get('data', ''))
                                
                                # Prioridade 3: Texto Consolidado da própria norma
                                if file_name == f"{cod_norma_str}_texto_consolidado.pdf":
                                    return (3, doc.get('data', ''))
                                
                                # Prioridade 4: Demais documentos (ordenados por data)
                                return (4, doc.get('data', ''))
                            
                            documentos_formatados.sort(key=get_document_priority_for_meta)
                            
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
            error_msg = str(se)
            logger.error(f"[PaginaProcessoNorma] Erro de segurança ao acessar: {file_path or pagina} - {se}")
            # Verifica se o erro é "Base path does not exist" - indica que precisa regenerar pasta
            if "Base path does not exist" in error_msg:
                # Retorna status 404 com header especial indicando que precisa regenerar
                self.request.RESPONSE.setStatus(404)
                self.request.RESPONSE.setHeader('X-Pasta-Regenerate', 'true')
                self.request.RESPONSE.setHeader('X-Pasta-Cod-Norma', str(cod_norma))
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                import json
                return json.dumps({
                    'error': 'Base path does not exist',
                    'regenerate': True,
                    'cod_norma': str(cod_norma)
                }, ensure_ascii=False)
            # Outros erros de segurança retornam 403
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
    Esta view é chamada via HTTP pelo Celery worker, permitindo que a execução
    aconteça no contexto do Zope que já está rodando. Todos os documentos são
    baixados via HTTP, evitando problemas de acesso direto ao ZODB.
    """
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_norma_task_executor')

    def _get_session(self):
        """Retorna sessão SQLAlchemy thread-safe"""
        return Session()

    def _construir_url_documento(self, container, filename: str) -> str:
        """Constrói URL do documento para download via HTTP"""
        if hasattr(container, 'absolute_url'):
            base_url = container.absolute_url()
            return f"{base_url}/{filename}"
        else:
            # Tenta obter URL do contexto
            if hasattr(self.context, 'absolute_url'):
                base_url = self.context.absolute_url()
                container_name = getattr(container, '__name__', '')
                if container_name:
                    return f"{base_url}/{container_name}/{filename}"
                else:
                    return f"{base_url}/{filename}"
        return None
    
    def _baixar_documento_via_http_com_retry(self, url: str, caminho_saida: str, filename: str, max_retries: int = 3) -> bool:
        """
        Baixa um documento via HTTP com retry e backoff exponencial.
        OTIMIZAÇÃO: Retry com backoff exponencial para lidar com falhas temporárias.
        """
        # OTIMIZAÇÃO: Cache - verifica se arquivo já existe antes de baixar
        if os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 0:
            return True
        
        # Cria opener HTTP reutilizável para connection pooling
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'SAGL-PDF-Generator/1.0')]
        
        base_delay = 1.0  # Delay inicial de 1 segundo
        
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                
                # OTIMIZAÇÃO: Timeout adaptativo baseado no tamanho esperado
                timeout = 60 if attempt == 0 else 90  # Timeout maior em retries
                
                with opener.open(req, timeout=timeout) as response:
                    file_data = response.read()
                
                if file_data and len(file_data) > 0:
                    # Salva no filesystem
                    with open(caminho_saida, 'wb') as f:
                        f.write(file_data)
                    return True
                else:
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Download de '{filename}' retornou dados vazios")
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Backoff exponencial
                        time.sleep(delay)
                    continue
                    
            except urllib.error.HTTPError as http_err:
                if http_err.code == 404:
                    return False  # 404 não deve ser retentado
                elif http_err.code >= 500 and attempt < max_retries - 1:
                    # Erros 5xx são retentáveis
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro HTTP {http_err.code} ao baixar '{filename}', tentando novamente em {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro HTTP ao baixar '{filename}': {http_err.code} - {http_err.reason}")
                    return False
                    
            except urllib.error.URLError as url_err:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro de URL ao baixar '{filename}', tentando novamente em {delay}s: {url_err}")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro de URL ao baixar '{filename}': {url_err}")
                    return False
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro ao baixar '{filename}', tentando novamente em {delay}s: {e}")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro ao baixar '{filename}': {e}")
                    return False
        
        return False
    
    def _baixar_documento_via_http(self, container, filename: str, caminho_saida: str) -> bool:
        """Baixa um documento do container Zope via HTTP e salva no filesystem (compatibilidade)"""
        try:
            # Constrói URL do objeto para download via HTTP
            url = self._construir_url_documento(container, filename)
            if not url:
                logger.warning(f"[_baixar_documento_via_http] Não foi possível construir URL para '{filename}'")
                return False
            
            # Usa função otimizada com retry
            return self._baixar_documento_via_http_com_retry(url, caminho_saida, filename)
        except Exception as e:
            logger.warning(f"[_baixar_documento_via_http] Erro ao baixar '{filename}': {e}")
            return False
    
    def _baixar_documento_worker(self, doc: Dict, dir_base: str) -> Tuple[Dict, bool]:
        """
        Worker para download paralelo de documentos.
        Retorna (doc_baixado, sucesso)
        """
        if doc.get('filesystem'):
            # Já está no filesystem, apenas retorna
            return doc, True
        
        # Precisa baixar via HTTP
        container = doc.get('path')
        filename = doc.get('file', '')
        
        if not container or not filename:
            logger.warning(f"[_baixar_documento_worker] Documento sem container ou filename, pulando: {doc.get('title', '?')}")
            return None, False
        
        # Cria caminho único para o arquivo
        caminho_arquivo = secure_path_join(dir_base, filename)
        
        # Constrói URL
        url = self._construir_url_documento(container, filename)
        if not url:
            logger.warning(f"[_baixar_documento_worker] Não foi possível construir URL para '{filename}'")
            return None, False
        
        # Baixa via HTTP com retry
        if self._baixar_documento_via_http_com_retry(url, caminho_arquivo, filename):
            # Atualiza documento para indicar que está no filesystem
            doc_baixado = doc.copy()
            doc_baixado['path'] = dir_base
            doc_baixado['filesystem'] = True
            return doc_baixado, True
        else:
            logger.warning(f"[_baixar_documento_worker] Falha ao baixar documento '{filename}'")
            return None, False

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
            
            # Verifica se o contexto tem os atributos necessários
            # IMPORTANTE: O contexto deve ser o site /sagl, que contém sapl_documentos.
            # Quando acessado via HTTP com VirtualHostRoot, o contexto pode ser o root do Zope,
            # mas o VirtualHostRoot permite que sapl_documentos seja acessado via Acquisition.
            try:
                # Tenta acessar sapl_documentos - pode estar disponível via Acquisition mesmo que
                # o contexto seja o root (quando VirtualHostRoot está configurado)
                sapl_docs = getattr(self.context, 'sapl_documentos', None)
                if sapl_docs is None:
                    error_msg = f"Contexto não tem sapl_documentos. Tipo: {type(self.context).__name__}. Esperado: site /sagl (que contém sapl_documentos) ou root com VirtualHostRoot configurado."
                    logger.error(f"[ProcessoNormaTaskExecutor] {error_msg}")
                    self.request.RESPONSE.setStatus(500)
                    self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                    return json.dumps({'error': error_msg, 'success': False, 'context_type': context_type})
            except Exception as attr_err:
                logger.error(f"[ProcessoNormaTaskExecutor] Erro ao verificar atributos do contexto: {attr_err}", exc_info=True)
                self.request.RESPONSE.setStatus(500)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': f'Erro ao verificar contexto: {str(attr_err)}', 'success': False})
            
            view = ProcessoNormaView(self.context, self.request)
            view.update()
            
            try:
                # Etapa 1: Obter dados da norma
                dados_norma = view.obter_dados_norma(cod_norma)
                
                # Etapa 2: Preparar diretórios
                dir_base, dir_paginas = view.preparar_diretorios(cod_norma)
                
                # Etapa 3: Coletar documentos
                documentos = view.coletar_documentos(dados_norma, dir_base)
                
                # Etapa 4: Baixar todos os documentos que não estão no filesystem
                # OTIMIZAÇÃO: Paralelização de downloads usando ThreadPoolExecutor
                documentos_baixados = []
                documentos_para_baixar = []
                
                # Separa documentos que já estão no filesystem dos que precisam ser baixados
                for doc in documentos:
                    if doc.get('filesystem'):
                        # Já está no filesystem, apenas adiciona
                        documentos_baixados.append(doc)
                    else:
                        # Precisa baixar via HTTP
                        documentos_para_baixar.append(doc)
                
                # OTIMIZAÇÃO: Paraleliza downloads quando há múltiplos documentos
                if documentos_para_baixar:
                    max_workers = min(4, len(documentos_para_baixar))  # Máximo de 4 workers simultâneos
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Submete todos os downloads
                        futures = {executor.submit(self._baixar_documento_worker, doc, dir_base): doc for doc in documentos_para_baixar}
                        
                        # Processa resultados conforme completam
                        for future in futures:
                            try:
                                doc_baixado, sucesso = future.result(timeout=300)  # Timeout de 5 minutos por documento
                                if sucesso and doc_baixado:
                                    documentos_baixados.append(doc_baixado)
                            except Exception as e:
                                doc_original = futures[future]
                                logger.warning(f"[ProcessoNormaTaskExecutor] Erro ao baixar documento '{doc_original.get('file', '?')}': {e}")
                
                # Prepara dados para retornar (apenas informações, não processa)
                id_processo = dados_norma.get('id_exibicao', '')
                
                # Handler para converter objetos não serializáveis
                def default_serializer(obj):
                    """Handler para converter objetos não serializáveis"""
                    if isinstance(obj, str):
                        return obj
                    try:
                        if hasattr(obj, '__name__'):
                            return str(obj.__name__)
                        return str(obj)
                    except Exception:
                        return None
                
                # Converte documentos para estruturas serializáveis (todos já devem estar no filesystem)
                documentos_serializaveis = []
                for doc in documentos_baixados:
                    doc_serializavel = {}
                    for key, value in doc.items():
                        # Todos os documentos devem ter path como string agora
                        if key == 'path' and not isinstance(value, str):
                            # Se ainda não for string, converte
                            doc_serializavel['path'] = str(value) if value else dir_base
                        else:
                            doc_serializavel[key] = value
                    documentos_serializaveis.append(doc_serializavel)
                
                # Converte dados_norma: apenas campos serializáveis
                dados_norma_serializavel = {}
                for key, value in dados_norma.items():
                    try:
                        json.dumps(value, default=default_serializer)
                        dados_norma_serializavel[key] = value
                    except (TypeError, ValueError):
                        converted = default_serializer(value)
                        if converted is not None:
                            dados_norma_serializavel[key] = converted
                
                # Retorna informações para que a task Celery faça o processamento pesado
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
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[ProcessoNormaTaskExecutor] Erro ao gerar processo: {gen_err}", exc_info=True)
                logger.error(f"[ProcessoNormaTaskExecutor] Traceback completo:\n{error_traceback}")
                self.request.RESPONSE.setStatus(500)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'success': False,
                    'error': str(gen_err),
                    'error_type': type(gen_err).__name__,
                    'traceback': error_traceback,
                    'cod_norma': cod_norma,
                    'context_type': type(self.context).__name__,
                    'context_id': getattr(self.context, 'id', 'N/A'),
                    'has_sapl_documentos': hasattr(self.context, 'sapl_documentos'),
                    'has_modelo_proposicao': hasattr(self.context, 'modelo_proposicao')
                })
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"[ProcessoNormaTaskExecutor] Erro inesperado: {e}", exc_info=True)
            logger.error(f"[ProcessoNormaTaskExecutor] Traceback completo:\n{error_traceback}")
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({
                'error': str(e),
                'error_type': type(e).__name__,
                'success': False,
                'traceback': error_traceback
            })


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
