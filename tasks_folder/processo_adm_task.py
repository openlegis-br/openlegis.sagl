"""
Tarefa Celery assíncrona para geração de processo administrativo integral.

Esta tarefa processa a geração do PDF do processo integral de forma assíncrona,
permitindo que o usuário continue usando o sistema enquanto aguarda a conclusão.

FLUXO:
1. Task faz chamada HTTP para view ProcessoAdmTaskExecutor no Zope (ou coleta direta)
2. View faz download dos arquivos e retorna informações
3. Task faz processamento pesado (mesclagem, validação, salvamento)
"""
import logging
import os
import sys
import time
import json
import hashlib
import urllib.request
import urllib.parse
import urllib.error
import gc
import shutil
import uuid
from datetime import datetime, date
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Any

# Configura logging ANTES de importar qualquer coisa
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Importa bibliotecas de PDF
try:
    import fitz
    import pikepdf
except ImportError as e:
    logger.error(f"[processo_adm_task] ERRO ao importar bibliotecas de PDF: {e}", exc_info=True)
    raise

# Importa as dependências
try:
    from .utils import zope_task
except Exception as e:
    logger.error(f"[processo_adm_task] ERRO ao importar dependências: {e}", exc_info=True)
    raise

# Importa SQLAlchemy (usado apenas nas funções de coleta que são chamadas pela view)
try:
    from sqlalchemy import and_, or_
    from sqlalchemy.orm import selectinload
    from openlegis.sagl.models.models import (
        DocumentoAdministrativo, TipoDocumentoAdministrativo,
        DocumentoAcessorioAdministrativo, TramitacaoAdministrativo,
        DocumentoAdministrativoMateria, CientificacaoDocumento, Usuario,
        MateriaLegislativa, TipoMateriaLegislativa, StatusTramitacaoAdministrativo
    )
except Exception as e:
    logger.error(f"[processo_adm_task] ERRO ao importar SQLAlchemy: {e}", exc_info=True)
    raise

# Importa funções de cientificações já migradas
try:
    from openlegis.sagl.browser.processo_adm.processo_adm import (
        coletar_cientificacoes_com_nomes,
        gerar_folha_cientificacao_pdf,
        _convert_to_datetime_string
    )
except Exception as e:
    logger.warning(f"[processo_adm_task] Não foi possível importar funções de cientificações: {e}")
    coletar_cientificacoes_com_nomes = None
    gerar_folha_cientificacao_pdf = None
    _convert_to_datetime_string = None

# Importa funções de cache e assinaturas
try:
    from openlegis.sagl.browser.processo_adm.pasta_digital import (
        _load_cache_from_filesystem_adm,
        _save_cache_to_filesystem_adm,
        _compare_documents_with_metadados_adm,
        _calculate_documents_hash_adm
    )
    from openlegis.sagl.browser.processo_adm.processo_adm_utils import (
        get_cache_file_path_adm, get_processo_dir_adm, secure_path_join
    )
except Exception as e:
    logger.error(f"[processo_adm_task] ❌ Não foi possível importar funções de cache: {e}", exc_info=True)
    _load_cache_from_filesystem_adm = None
    _save_cache_to_filesystem_adm = None
    _compare_documents_with_metadados_adm = None
    _calculate_documents_hash_adm = None
    get_cache_file_path_adm = None
    get_processo_dir_adm = None
    secure_path_join = None

# Constantes (mesmas da view)
MAX_PAGES = 5000
MAX_WORKERS = 4
CHUNK_SIZE_PAGES = 200
MIN_PDF_SIZE_FOR_CHUNKS = 50 * 1024 * 1024  # 50 MB
MEMORY_CLEANUP_INTERVAL = 50
PAGE_SAVE_BATCH_SIZE = 50
PAGE_SAVE_TIMEOUT = 5

PDF_OPTIMIZATION_SETTINGS = {
    'garbage': 4,
    'deflate': True,
    'clean': True,
    'ascii': True,
}

PAGE_SAVE_OPTIMIZATION_SETTINGS = {
    'garbage': 2,
    'deflate': True,
    'clean': False,
    'ascii': False,
}

# Estágios do processo
class ProcessStage:
    """Estágios padronizados do processo de geração"""
    INIT = 'init'
    DADOS_DOCUMENTO = 'dados_documento'
    PREPARAR_DIRS = 'preparar_dirs'
    COLETAR_DOCS = 'coletar_docs'
    MESCLAR_DOCS = 'mesclar_docs'
    SALVAR_PAGINAS = 'salvar_paginas'
    SALVAR_PDF = 'salvar_pdf'
    LIMPAR_TEMP = 'limpar_temp'
    CONCLUIDO = 'concluido'


# Funções secure_path_join e _convert_to_datetime_string foram removidas daqui
# Agora são importadas de processo_adm_utils e processo_adm respectivamente
# Se as importações falharem, cria versões locais simples como fallback

# Fallback para secure_path_join se importação falhar
if secure_path_join is None:
    def secure_path_join(base_path: str, *paths: str) -> str:
        """Junta caminhos de forma segura, prevenindo path traversal (fallback)"""
        full_path = os.path.normpath(os.path.join(base_path, *paths))
        base = os.path.normpath(base_path)
        if not full_path.startswith(base + os.sep) and full_path != base:
            raise ValueError(f"Path traversal attempt detected: {full_path}")
        if os.path.islink(full_path):
            raise ValueError(f"Symbolic links not allowed: {full_path}")
        return full_path

# Fallback para _convert_to_datetime_string se importação falhar
if _convert_to_datetime_string is None:
    def _convert_to_datetime_string(date_obj):
        """Converte objetos datetime.date ou datetime.datetime para string (fallback)"""
        if date_obj is None:
            return ''
        if isinstance(date_obj, datetime):
            return date_obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(date_obj, date):
            return date_obj.strftime('%Y-%m-%d')
        return str(date_obj)


def validar_pdf_robusto(pdf_bytes: bytes, filename: str) -> Tuple[bool, int, str]:
    """
    Valida PDF de forma robusta usando validação híbrida (fitz rápido + pikepdf rigoroso).
    
    Returns:
        Tuple[bool, int, str]: (é_válido, num_páginas, mensagem_erro)
    """
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            num_pages = len(pdf)
            if num_pages == 0:
                return False, 0, "PDF não tem páginas"
            return True, num_pages, ""
    except Exception as fitz_err:
        try:
            with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
                num_pages = len(pdf.pages)
                if num_pages == 0:
                    return False, 0, "PDF não tem páginas"
                if not pdf.Root:
                    return False, 0, "PDF não tem estrutura raiz válida"
                return True, num_pages, ""
        except Exception as pikepdf_err:
            error_msg = str(pikepdf_err).lower()
            if 'format error' in error_msg or 'object out of range' in error_msg:
                return False, 0, f"PDF corrompido: {pikepdf_err}"
            return False, 0, f"Erro ao validar PDF: {pikepdf_err}"


def _verificar_arquivo_existe_via_http(portal_url: str, caminho_relativo: str) -> bool:
    """
    Verifica se um arquivo existe no Zope usando HEAD request.
    Evita que o Zope tente renderizar página de erro quando o arquivo não existe.
    
    Args:
        portal_url: URL base do portal
        caminho_relativo: Caminho relativo do arquivo
        
    Returns:
        bool: True se arquivo existe (status 200), False caso contrário
    """
    try:
        base_url = portal_url.rstrip('/')
        url = f"{base_url}/{caminho_relativo}"
        
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
        req.add_header('Accept', 'application/pdf,application/octet-stream')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except urllib.error.HTTPError as e:
        # 404 ou qualquer outro erro HTTP significa que não existe
        if e.code == 404:
            # Lê e descarta corpo da resposta para evitar problemas
            try:
                e.read()
            except:
                pass
        return False
    except Exception:
        # Qualquer outro erro também significa que provavelmente não existe
        return False


def _baixar_arquivo_via_http(portal_url: str, caminho_relativo: str, caminho_saida: str, max_retries: int = 3, verificar_antes: bool = True) -> bool:
    """
    Baixa um arquivo via HTTP do Zope.
    
    Trata 404 silenciosamente para evitar que o Zope renderize páginas de erro
    que causam problemas com AUTHENTICATED_USER não definido.
    
    Args:
        portal_url: URL base do portal
        caminho_relativo: Caminho relativo do arquivo (ex: sapl_documentos/administrativo/doc.pdf)
        caminho_saida: Caminho completo onde salvar o arquivo
        max_retries: Número máximo de tentativas (apenas para erros não-404)
        verificar_antes: Se True, verifica existência com HEAD antes de tentar GET
        
    Returns:
        bool: True se baixou com sucesso, False caso contrário (inclui 404)
    """
    # Verifica se arquivo já existe
    if os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 0:
        return True
    
    # CRÍTICO: Verifica se arquivo existe ANTES de tentar baixar
    # Isso evita que o Zope tente fazer traverse e gere erro NotFound
    if verificar_antes:
        if not _verificar_arquivo_existe_via_http(portal_url, caminho_relativo):
            return False
    
    base_url = portal_url.rstrip('/')
    url = f"{base_url}/{caminho_relativo}"
    
    # Tenta baixar o arquivo (com retries apenas para erros não-404)
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
            # Adiciona header para evitar que o Zope tente renderizar página de erro
            req.add_header('Accept', 'application/pdf,application/octet-stream,*/*')
            
            # OTIMIZAÇÃO: Timeout adaptativo - se arquivo já existe, estima timeout baseado no tamanho
            # Timeout padrão de 30s, aumenta para arquivos grandes (>5MB)
            download_timeout = 30
            if os.path.exists(caminho_saida):
                try:
                    existing_size = os.path.getsize(caminho_saida)
                    if existing_size > 5 * 1024 * 1024:
                        # Para arquivos grandes, aumenta timeout proporcionalmente (~2s por MB)
                        download_timeout = max(30, int(existing_size / (1024 * 1024)) * 2)
                except Exception:
                    pass  # Se não conseguir obter tamanho, usa timeout padrão
            
            with urllib.request.urlopen(req, timeout=download_timeout) as response:
                # Verifica código de status
                if response.status == 404:
                    return False
                
                file_data = response.read()
                
                if file_data and len(file_data) > 0:
                    # Cria diretório se necessário
                    dir_saida = os.path.dirname(caminho_saida)
                    if dir_saida:
                        os.makedirs(dir_saida, exist_ok=True)
                    with open(caminho_saida, 'wb') as f:
                        f.write(file_data)
                    return True
                else:
                    return False
                    
        except urllib.error.HTTPError as e:
            # Trata 404 de forma silenciosa (não tenta novamente)
            if e.code == 404:
                # Lê e descarta o corpo da resposta 404 para evitar problemas com páginas de erro
                try:
                    e.read()
                except:
                    pass
                return False
            
            # Para outros erros HTTP, tenta novamente se houver tentativas restantes
            if attempt < max_retries - 1:
                time.sleep(1 * (2 ** attempt))  # Backoff exponencial
                continue
            
            logger.warning(f"[_baixar_arquivo_via_http] Erro HTTP {e.code} ao baixar {caminho_relativo}: {e.reason}")
            return False
            
        except urllib.error.URLError as e:
            # Erros de URL (timeout, conexão, etc) - tenta novamente se houver tentativas restantes
            if attempt < max_retries - 1:
                time.sleep(1 * (2 ** attempt))
                continue
            
            logger.warning(f"[_baixar_arquivo_via_http] Erro de URL ao baixar {caminho_relativo}: {e.reason}")
            return False
            
        except Exception as e:
            # CRÍTICO: Captura qualquer exceção, incluindo KeyError do Zope quando tenta fazer traverse
            # Isso evita que erros do Zope (como NotFound/KeyError) propaguem
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Se for erro do Zope (KeyError, NotFound), trata como 404
            if 'NotFound' in error_type or 'KeyError' in error_type or '404' in error_msg:
                return False
            
            # Para outros erros, tenta novamente se houver tentativas restantes
            if attempt < max_retries - 1:
                time.sleep(1 * (2 ** attempt))
                continue
            
            logger.error(f"[_baixar_arquivo_via_http] Erro inesperado ao baixar {caminho_relativo}: {e} ({error_type})")
            return False
    
    return False


def coletar_documentos_processo_adm(session, portal_url: str, cod_documento: int, dir_base: str, progress_callback=None) -> Tuple[List[Dict], str, str]:
    """
    Coleta todos os documentos do processo administrativo usando SQLAlchemy.
    
    Migrado de processo_adm.py (antigo) linhas 453-534.
    
    Args:
        session: Sessão SQLAlchemy
        portal_url: URL base do portal
        cod_documento: Código do documento administrativo
        dir_base: Diretório base onde salvar arquivos
        progress_callback: Função opcional para atualizar progresso
        
    Returns:
        tuple: (lista_documentos, id_processo, nome_arquivo_final)
    """
    documentos = []
    id_processo = None
    processo_integral_nome = f"documento-{cod_documento}.pdf"
    
    try:
        # 1. Obter dados do documento administrativo (SQLAlchemy)
        doc_result = session.query(DocumentoAdministrativo, TipoDocumentoAdministrativo)\
            .join(TipoDocumentoAdministrativo, 
                  DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
            .filter(DocumentoAdministrativo.cod_documento == cod_documento)\
            .filter(DocumentoAdministrativo.ind_excluido == 0)\
            .first()
        
        if not doc_result:
            raise ValueError(f"Documento {cod_documento} não encontrado")
        
        doc_adm, tipo_doc = doc_result
        processo_integral_nome = f"{tipo_doc.sgl_tipo_documento}-{doc_adm.num_documento}-{doc_adm.ano_documento}.pdf"
        id_processo = f"{tipo_doc.sgl_tipo_documento} {doc_adm.num_documento}/{doc_adm.ano_documento}"
        
        # Data base do documento
        dat_documento = _convert_to_datetime_string(doc_adm.dat_documento) if doc_adm.dat_documento else ''
        if not dat_documento:
            dat_documento = datetime.now().strftime('%Y-%m-%d 00:00:00')
        
        if progress_callback:
            progress_callback(5, 100, 'Gerando capa...')
        
        # 2. Gerar capa do processo (SEMPRE GERADA) - Usa modelo_proposicao.capa_processo_adm
        # IMPORTANTE: A capa deve ser sempre gerada, mesmo sem documentos associados
        # Segue o mesmo padrão do processo_leg: gera via modelo_proposicao e faz download via HTTP
        try:
            # Reutiliza doc_result já obtido acima
            doc_obj, tipo_obj = doc_adm, tipo_doc
            tipo = tipo_obj.sgl_tipo_documento if tipo_obj.sgl_tipo_documento else 'DOC'
            numero = doc_obj.num_documento if doc_obj.num_documento else 0
            ano = doc_obj.ano_documento if doc_obj.ano_documento else 2025
            
            arquivo_capa = f"capa_{tipo}-{numero}-{ano}.pdf"
            caminho_capa = os.path.join(dir_base, arquivo_capa)
            data_capa = f"{dat_documento[:10]} 00:00:01"  # Primeira posição
            
            # Gera a capa usando o método padrão do sistema (gera no temp_folder)
            # IMPORTANTE: modelo_proposicao está em /sagl/portal_skins/sk_sagl/modelo_proposicao
            # Precisa acessar através do caminho completo: portal_skins.sk_sagl.modelo_proposicao
            # NOTA: Na task Celery não temos acesso direto ao contexto Zope, então usamos HTTP
            
            # Passo 1: Gera capa via HTTP (action=gerar) - salva no temp_folder
            nom_arquivo_temp = uuid.uuid4().hex  # Nome temporário para geração
            capa_url_gerar = f"{portal_url}/modelo_proposicao/capa_processo_adm?cod_documento={cod_documento}&nom_arquivo={nom_arquivo_temp}&action=gerar"
            
            try:
                req_gerar = urllib.request.Request(capa_url_gerar)
                req_gerar.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                with urllib.request.urlopen(req_gerar, timeout=30) as response:
                    # Apenas verifica se a requisição foi bem-sucedida
                    pass
                
                # OTIMIZAÇÃO: Polling simplificado - verifica apenas 1 vez rapidamente
                # Se não estiver pronto, o download com timeout maior vai aguardar a geração
                time.sleep(0.5)
                
                # Passo 2: Faz download via HTTP (action=download) - obtém PDF gerado
                capa_url_download = f"{portal_url}/modelo_proposicao/capa_processo_adm?cod_documento={cod_documento}&nom_arquivo={nom_arquivo_temp}&action=download"
                
                req_download = urllib.request.Request(capa_url_download)
                req_download.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                
                try:
                    with urllib.request.urlopen(req_download, timeout=60) as response:
                        capa_data = response.read()
                    
                    if capa_data and len(capa_data) > 0:
                        # Salva no filesystem com nome padronizado
                        with open(caminho_capa, 'wb') as f:
                            f.write(capa_data)
                        
                        capa_size = os.path.getsize(caminho_capa)
                        if capa_size == 0:
                            raise Exception("Download da capa retornou dados vazios")
                        
                        documentos.append({
                            "data": data_capa,
                            "path": dir_base,
                            "file": arquivo_capa,
                            "title": "Capa do Processo",
                            "filesystem": True
                        })
                    else:
                        raise Exception("Download da capa retornou dados vazios")
                        
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 404:
                        raise Exception(f"Capa do processo não encontrada (404): {capa_url_download}")
                    else:
                        raise Exception(f"Erro HTTP ao baixar capa: {http_err.code} - {http_err.reason}")
                except Exception as download_err:
                    raise Exception(f"Erro ao baixar capa via HTTP: {str(download_err)}")
                    
            except urllib.error.HTTPError as http_err:
                if http_err.code == 404:
                    raise Exception(f"Capa do processo não encontrada (404): {capa_url_gerar}")
                else:
                    raise Exception(f"Erro HTTP ao gerar capa: {http_err.code} - {http_err.reason}")
            except Exception as gen_err:
                raise Exception(f"Erro ao gerar capa via HTTP: {str(gen_err)}")
                    
        except Exception as e:
            logger.error(f"[coletar_documentos_processo_adm] Erro ao gerar/baixar capa do processo: {str(e)}", exc_info=True)
            raise Exception(f"Falha ao gerar/baixar capa do processo administrativo: {str(e)}")
        
        if progress_callback:
            progress_callback(10, 100, 'Coletando texto integral...')
        
        # 3. Coletar texto integral (ZODB via HTTP)
        nom_arquivo_texto = f"{cod_documento}_texto_integral.pdf"
        texto_path_rel = f"sapl_documentos/administrativo/{nom_arquivo_texto}"
        texto_path_abs = os.path.join(dir_base, nom_arquivo_texto)
        
        try:
            if _baixar_arquivo_via_http(portal_url, texto_path_rel, texto_path_abs):
                documentos.append({
                    "data": f"{dat_documento[:10]} 00:00:02",
                    'path': dir_base,
                    'file': nom_arquivo_texto,
                    'title': f"{tipo_doc.des_tipo_documento} {doc_adm.num_documento}/{doc_adm.ano_documento}",
                    'filesystem': True
                })
            else:
                # Arquivo não encontrado (404) - silencioso, não é obrigatório ter texto integral
                pass
        except Exception as e:
            # Trata qualquer erro na coleta de forma silenciosa
            # Continua - não é obrigatório ter texto integral
            pass
        
        if progress_callback:
            progress_callback(20, 100, 'Coletando documentos acessórios...')
        
        # 4. Coletar documentos acessórios (SQLAlchemy + ZODB via HTTP)
        # OTIMIZAÇÃO: Downloads paralelos (mesmo padrão da view)
        documentos_acessorios = session.query(DocumentoAcessorioAdministrativo)\
            .filter(DocumentoAcessorioAdministrativo.cod_documento == cod_documento)\
            .filter(DocumentoAcessorioAdministrativo.ind_excluido == 0)\
            .order_by(DocumentoAcessorioAdministrativo.dat_documento)\
            .all()
        
        if documentos_acessorios:
            # OTIMIZAÇÃO: Coleta URLs primeiro, depois baixa em paralelo
            itens_para_baixar = []
            
            for doc_acess in documentos_acessorios:
                # Formato correto é {cod}.pdf (alinhado com pasta_digital.py e view)
                nome_acessorio = f"{doc_acess.cod_documento_acessorio}.pdf"
                acessorio_path_rel = f"sapl_documentos/administrativo/{nome_acessorio}"
                acessorio_path_abs = os.path.join(dir_base, nome_acessorio)
                
                itens_para_baixar.append({
                    'path_rel': acessorio_path_rel,
                    'path_abs': acessorio_path_abs,
                    'filename': nome_acessorio,
                    'doc': doc_acess,
                    'dat': _convert_to_datetime_string(doc_acess.dat_documento) if doc_acess.dat_documento else dat_documento
                })
            
            # OTIMIZAÇÃO: Downloads paralelos
            if itens_para_baixar:
                max_workers = min(4, len(itens_para_baixar))
                
                def _baixar_item(item):
                    """Worker para download de um item"""
                    try:
                        if _baixar_arquivo_via_http(portal_url, item['path_rel'], item['path_abs'], verificar_antes=True):
                            return item
                    except Exception as e:
                        logger.debug(f"[coletar_documentos_processo_adm] Erro ao baixar {item['filename']}: {e}")
                    return None
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(_baixar_item, item): item for item in itens_para_baixar}
                    
                    for future in futures:
                        try:
                            item = future.result(timeout=300)
                            if item:
                                doc_acess = item['doc']
                                nome_acessorio = item['filename']
                                documentos.append({
                                    "data": item['dat'],
                                    'path': dir_base,
                                    'file': nome_acessorio,
                                    'title': doc_acess.nom_documento or f'Documento Acessório {doc_acess.cod_documento_acessorio}',
                                    'filesystem': True
                                })
                        except Exception as e:
                            item = futures[future]
                            logger.warning(f"[coletar_documentos_processo_adm] Erro ao baixar documento acessório '{item['filename']}': {e}")
        
        if progress_callback:
            progress_callback(40, 100, 'Coletando tramitações...')
        
        # 5. Coletar tramitações (SQLAlchemy + ZODB via HTTP)
        # OTIMIZAÇÃO: Downloads paralelos (mesmo padrão da view)
        from openlegis.sagl.models.models import StatusTramitacaoAdministrativo
        tramitacoes = session.query(TramitacaoAdministrativo, StatusTramitacaoAdministrativo)\
            .outerjoin(StatusTramitacaoAdministrativo, TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status)\
            .filter(TramitacaoAdministrativo.cod_documento == cod_documento)\
            .filter(TramitacaoAdministrativo.ind_excluido == 0)\
            .order_by(TramitacaoAdministrativo.dat_tramitacao, TramitacaoAdministrativo.cod_tramitacao)\
            .all()
        
        if tramitacoes:
            # OTIMIZAÇÃO: Coleta URLs primeiro, depois baixa em paralelo
            itens_para_baixar = []
            
            for tram, status in tramitacoes:
                nome_tram = f"{tram.cod_tramitacao}_tram.pdf"
                tram_path_rel = f"sapl_documentos/administrativo/tramitacao/{nome_tram}"
                tram_path_abs = os.path.join(dir_base, nome_tram)
                
                itens_para_baixar.append({
                    'path_rel': tram_path_rel,
                    'path_abs': tram_path_abs,
                    'filename': nome_tram,
                    'tram': tram,
                    'status': status,
                    'dat': _convert_to_datetime_string(tram.dat_tramitacao) if tram.dat_tramitacao else dat_documento
                })
            
            # OTIMIZAÇÃO: Downloads paralelos
            if itens_para_baixar:
                max_workers = min(4, len(itens_para_baixar))
                
                def _baixar_item(item):
                    """Worker para download de um item"""
                    try:
                        if _baixar_arquivo_via_http(portal_url, item['path_rel'], item['path_abs'], verificar_antes=True):
                            return item
                    except Exception as e:
                        logger.debug(f"[coletar_documentos_processo_adm] Erro ao baixar {item['filename']}: {e}")
                    return None
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(_baixar_item, item): item for item in itens_para_baixar}
                    
                    for future in futures:
                        try:
                            item = future.result(timeout=300)
                            if item:
                                tram = item['tram']
                                status = item['status']
                                nome_tram = item['filename']
                                des_status = status.des_status if status else 'Tramitação'
                                documentos.append({
                                    "data": item['dat'],
                                    'path': dir_base,
                                    'file': nome_tram,
                                    'title': f"Tramitação ({des_status})",
                                    'filesystem': True
                                })
                        except Exception as e:
                            item = futures[future]
                            logger.warning(f"[coletar_documentos_processo_adm] Erro ao baixar tramitação '{item['filename']}': {e}")
        
        if progress_callback:
            progress_callback(60, 100, 'Coletando matérias vinculadas...')
        
        # 6. Coletar matérias vinculadas (SQLAlchemy + ZODB via HTTP)
        # OTIMIZAÇÃO: Downloads paralelos (mesmo padrão da view)
        # Na task Celery, não temos acesso direto ao portal, então não podemos fazer verificação em lote
        # Mas ainda podemos fazer downloads paralelos
        from openlegis.sagl.models.models import MateriaLegislativa, TipoMateriaLegislativa
        materias_vinculadas = session.query(DocumentoAdministrativoMateria, MateriaLegislativa, TipoMateriaLegislativa)\
            .join(MateriaLegislativa, DocumentoAdministrativoMateria.cod_materia == MateriaLegislativa.cod_materia)\
            .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
            .filter(DocumentoAdministrativoMateria.cod_documento == cod_documento)\
            .filter(DocumentoAdministrativoMateria.ind_excluido == 0)\
            .filter(MateriaLegislativa.ind_excluido == 0)\
            .all()
        
        if materias_vinculadas:
            # OTIMIZAÇÃO: Para cada matéria, tenta encontrar apenas um arquivo válido
            # Verifica sufixo mais provável primeiro (_texto_integral.pdf antes de _redacao_final.pdf)
            sufixos = ['_texto_integral.pdf', '_redacao_final.pdf']
            itens_para_baixar = []
            materias_processadas = set()
            
            for doc_mat, materia, tipo_materia in materias_vinculadas:
                # Evita processar a mesma matéria duas vezes
                materia_id = materia.cod_materia
                if materia_id in materias_processadas:
                    continue
                
                # Adiciona ambos os sufixos para tentar baixar em paralelo
                # A função _baixar_arquivo_via_http já verifica existência via HTTP HEAD antes
                for sufixo in sufixos:
                    nome_materia = f"{materia.cod_materia}{sufixo}"
                    materia_path_rel = f"sapl_documentos/materia/{nome_materia}"
                    materia_path_abs = os.path.join(dir_base, nome_materia)
                    
                    itens_para_baixar.append({
                        'path_rel': materia_path_rel,
                        'path_abs': materia_path_abs,
                        'filename': nome_materia,
                        'doc_mat': doc_mat,
                        'materia': materia,
                        'tipo_materia': tipo_materia,
                        'sufixo': sufixo,
                        'materia_id': materia_id  # Para rastrear e evitar duplicatas
                    })
                materias_processadas.add(materia_id)
            
            # OTIMIZAÇÃO: Downloads paralelos - tenta baixar ambos os sufixos em paralelo
            # mas só adiciona a primeira matéria que for coletada com sucesso (evita duplicatas)
            if itens_para_baixar:
                max_workers = min(4, len(itens_para_baixar))
                
                def _baixar_item(item):
                    """Worker para download de um item"""
                    try:
                        # Verifica existência via HTTP HEAD antes de tentar baixar
                        if _baixar_arquivo_via_http(portal_url, item['path_rel'], item['path_abs'], verificar_antes=True):
                            return item
                    except Exception:
                        pass
                    return None
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(_baixar_item, item): item for item in itens_para_baixar}
                    
                    # Rastreia quais matérias já foram coletadas para evitar duplicatas
                    materias_coletadas = set()
                    
                    # Processa futures na ordem de prioridade (texto_integral primeiro)
                    # Usa as_completed para processar assim que cada download terminar
                    for future in as_completed(futures):
                        try:
                            item = future.result(timeout=300)
                            if item:
                                materia_id = item['materia_id']
                                # Evita adicionar a mesma matéria duas vezes (prioriza primeira encontrada)
                                if materia_id not in materias_coletadas:
                                    materia = item['materia']
                                    tipo_materia = item['tipo_materia']
                                    nome_materia = item['filename']
                                    documentos.append({
                                        "data": dat_documento,
                                        'path': dir_base,
                                        'file': nome_materia,
                                        'title': f"{tipo_materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica} (mat. vinculada)",
                                        'filesystem': True
                                    })
                                    materias_coletadas.add(materia_id)
                        except Exception as e:
                            item = futures[future]
                            logger.warning(f"[coletar_documentos_processo_adm] Erro ao baixar matéria vinculada '{item['filename']}': {e}")
        
        if progress_callback:
            progress_callback(80, 100, 'Gerando folha de cientificações...')
        
        # 7. Gerar folha de cientificações (se houver)
        try:
            if coletar_cientificacoes_com_nomes:
                dados_cient = coletar_cientificacoes_com_nomes(session, cod_documento, somente_pendentes=False)
                if dados_cient:
                    # Gera folha de cientificações
                    folha_nome = "folha_cientificacoes.pdf"
                    folha_caminho = os.path.join(dir_base, folha_nome)
                    
                    try:
                        if gerar_folha_cientificacao_pdf:
                            gerar_folha_cientificacao_pdf(
                                session, portal_url, cod_documento, folha_caminho, dados_cient
                            )
                        
                        # Obtém tamanho do arquivo gerado para incluir nos metadados
                        folha_size = 0
                        if os.path.exists(folha_caminho):
                            folha_size = os.path.getsize(folha_caminho)
                        
                        # CRÍTICO: Inclui count (número de cientificações) e file_size nos metadados
                        # Isso permite que a comparação detecte mudanças reais no número de cientificações
                        # e ignore variações pequenas de tamanho (dentro da tolerância)
                        documentos.append({
                            "data": "9999-12-31 23:59:59",  # Garante última posição
                            "path": dir_base,
                            "file": folha_nome,
                            "title": "Folha de Cientificações",
                            "filesystem": True,
                            "count": len(dados_cient),  # Número de cientificações
                            "file_size": folha_size  # Tamanho do arquivo gerado
                        })
                        logger.info(f"[coletar_documentos_processo_adm] Folha de cientificações gerada (count={len(dados_cient)}, size={folha_size})")
                    except Exception as gen_err:
                        logger.error(f"[coletar_documentos_processo_adm] Erro ao gerar folha de cientificações: {gen_err}", exc_info=True)
                        # Continua sem a folha se houver erro
        except Exception as e:
            logger.warning(f"[coletar_documentos_processo_adm] Erro ao coletar cientificações: {e}")
        
        # 8. Ordenar documentos por data
        documentos.sort(key=lambda d: d.get('data', ''))
        
        return documentos, id_processo, processo_integral_nome
        
    except Exception as e:
        logger.error(f"[coletar_documentos_processo_adm] Erro ao coletar documentos: {e}", exc_info=True)
        raise


def process_single_document_celery(doc: Dict, dir_base: str) -> Tuple[bytes, Dict]:
    """
    Processa um documento individual para mesclagem (versão para Celery).
    OTIMIZAÇÃO: Validação única e robusta usando pikepdf.
    """
    filename = doc.get('file', 'unknown')
    doc_title = doc.get('title', 'Documento desconhecido')
    
    try:
        if doc.get('filesystem'):
            pdf_path = secure_path_join(dir_base, doc['file'])
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {pdf_path}")
            
            file_size = os.path.getsize(pdf_path)
            STREAMING_THRESHOLD = 50 * 1024 * 1024  # 50 MB
            if file_size > STREAMING_THRESHOLD:
                pdf_bytes = bytearray()
                with open(pdf_path, 'rb') as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        pdf_bytes.extend(chunk)
                pdf_bytes = bytes(pdf_bytes)
            else:
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
        else:
            raise ValueError(f"Documento não está no filesystem: {filename}")
        
        # Validação robusta
        is_valid, num_pages, error_msg = validar_pdf_robusto(pdf_bytes, filename)
        if not is_valid:
            logger.warning(f"[process_single_document_celery] PDF '{filename}' falhou validação: {error_msg}")
            raise ValueError(f"PDF inválido para documento '{doc_title}': {error_msg}")
        
        doc_info = doc.copy()
        doc_info['file_size'] = file_size
        return pdf_bytes, doc_info
        
    except Exception as e:
        error_str = str(e).lower()
        if 'format error' in error_str or 'object out of range' in error_str or 'non-page object' in error_str:
            logger.warning(f"[process_single_document_celery] PDF corrompido para documento '{doc_title}': {e}")
            raise ValueError(f"PDF corrompido para documento '{doc_title}'")
        logger.warning(f"[process_single_document_celery] Erro ao processar documento '{doc_title}': {e}")
        raise


def inserir_pdf_em_chunks(pdf_mesclado: fitz.Document, pdf: fitz.Document, doc_title: str) -> int:
    """
    Insere PDF no documento mesclado em chunks para economizar memória.
    OTIMIZAÇÃO: Processa PDFs grandes em chunks ao invés de carregar tudo na memória.
    
    Returns:
        int: Número de páginas inseridas
    """
    num_pages = len(pdf)
    
    if num_pages <= CHUNK_SIZE_PAGES:
        pdf_mesclado.insert_pdf(pdf, annots=True)
        return num_pages
    
    pages_inserted = 0
    for start_page in range(0, num_pages, CHUNK_SIZE_PAGES):
        end_page = min(start_page + CHUNK_SIZE_PAGES, num_pages)
        pdf_mesclado.insert_pdf(pdf, from_page=start_page, to_page=end_page - 1, annots=True)
        pages_inserted += (end_page - start_page)
        gc.collect()
    
    return pages_inserted


def mesclar_documentos_celery(documentos: List[Dict], dir_base: str, id_processo: str, progress_callback=None) -> Tuple[fitz.Document, List[Dict]]:
    """
    Mescla documentos em um único PDF (versão para Celery).
    OTIMIZAÇÃO: Processa PDFs grandes em chunks para economizar memória.
    
    Args:
        documentos: Lista de documentos para mesclar
        dir_base: Diretório base onde os documentos estão
        id_processo: ID do processo
        progress_callback: Função opcional para atualizar progresso (current_doc, total_docs, current_pages)
    """
    pdf_mesclado = fitz.open()
    documentos_com_paginas = []
    total_docs = len(documentos)
    
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for doc in documentos:
                futures.append(executor.submit(process_single_document_celery, doc, dir_base))
            
            for idx, future in enumerate(futures):
                doc_info = None
                try:
                    pdf_bytes, doc_info = future.result()
                    doc_title = doc_info.get('title', '?') if doc_info else '?'
                    
                    try:
                        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
                            start_page = len(pdf_mesclado)
                            
                            use_chunks = len(pdf_bytes) >= MIN_PDF_SIZE_FOR_CHUNKS and len(pdf) > CHUNK_SIZE_PAGES
                            
                            if use_chunks:
                                num_pages_inserted = inserir_pdf_em_chunks(pdf_mesclado, pdf, doc_title)
                            else:
                                pdf_mesclado.insert_pdf(pdf, annots=True)
                                num_pages_inserted = len(pdf)
                            
                            doc_info.update({
                                'start_page': start_page + 1,
                                'end_page': len(pdf_mesclado),
                                'num_pages': num_pages_inserted
                            })
                            documentos_com_paginas.append(doc_info)
                            
                            if progress_callback:
                                try:
                                    progress_callback(idx + 1, total_docs, len(pdf_mesclado))
                                except Exception:
                                    pass
                            
                            del pdf_bytes
                            if len(pdf_mesclado) % MEMORY_CLEANUP_INTERVAL == 0:
                                gc.collect()
                    except Exception as processing_err:
                        error_str = str(processing_err).lower()
                        if 'format error' in error_str or 'object out of range' in error_str or 'non-page object' in error_str:
                            logger.warning(f"[mesclar_documentos_celery] PDF corrompido ignorado '{doc_title}': {processing_err}")
                        continue
                except Exception as e:
                    error_msg = str(e).lower()
                    doc_title = doc_info.get('title', '?') if doc_info else '?'
                    if 'format error' in error_msg or 'object out of range' in error_msg or 'non-page object' in error_msg:
                        pass  # Ignora documento corrompido
                    continue
        
        if len(pdf_mesclado) > MAX_PAGES:
            raise Exception(f"Número de páginas excede o limite de {MAX_PAGES}")
        
        gc.collect()
        
        # Adiciona rodapé e metadados
        for page_num in range(len(pdf_mesclado)):
            page = pdf_mesclado[page_num]
            page.insert_text(
                fitz.Point(page.rect.width - 110, 20),
                f"{id_processo} | Fls. {page_num + 1}/{len(pdf_mesclado)}",
                fontsize=8,
                color=(0, 0, 0)
            )
            
            if (page_num + 1) % MEMORY_CLEANUP_INTERVAL == 0:
                gc.collect()
        
        pdf_mesclado.set_metadata({
            "title": id_processo,
            "creator": "SAGL",
            "producer": "PyMuPDF",
            "creationDate": time.strftime('%Y-%m-%d %H:%M:%S')
        })
        pdf_mesclado.bake()
        
        return pdf_mesclado, documentos_com_paginas
        
    except Exception as e:
        logger.error(f"[mesclar_documentos_celery] Erro na mesclagem: {str(e)}", exc_info=True)
        raise


def _verificar_paginas_salvas_eficiente(dir_paginas: str, total_pages: int, cod_documento: int, portal_url: str = None) -> None:
    """
    Verifica se todas as páginas foram salvas de forma eficiente e estão acessíveis.
    CRÍTICO: Verifica TODAS as páginas (não apenas amostra) para garantir que nenhuma esteja faltando.
    Se portal_url fornecido, também verifica acessibilidade via HTTP.
    
    Args:
        dir_paginas: Diretório onde as páginas foram salvas
        total_pages: Número total de páginas esperado
        cod_documento: Código do documento administrativo
        portal_url: URL do portal (opcional, para verificação HTTP)
    """
    try:
        # Força sincronização do filesystem antes de verificar
        # Garante que todos os arquivos foram completamente escritos no disco
        import time
        time.sleep(0.5)  # Pequena espera para garantir que I/O foi completado
        
        # Sincroniza diretório se possível (Linux)
        try:
            import subprocess
            subprocess.run(['sync'], timeout=5, check=False, capture_output=True)
        except Exception:
            pass  # Ignora erros de sync (pode não estar disponível)
        
        # Lista todos os arquivos PDF de uma vez
        pdf_files = set(f for f in os.listdir(dir_paginas) if f.endswith('.pdf') and f.startswith('pg_'))
        
        if len(pdf_files) < total_pages:
            missing_count = total_pages - len(pdf_files)
            raise Exception(f"Não todas as páginas foram salvas: esperado {total_pages}, encontrado {len(pdf_files)} (faltam {missing_count})")
        
        # CRÍTICO: Verifica TODAS as páginas (não apenas amostra) para garantir integridade
        missing_pages = []
        empty_pages = []
        for page_num in range(1, total_pages + 1):
            pg_id = f"pg_{page_num:04d}.pdf"
            if pg_id not in pdf_files:
                missing_pages.append(page_num)
            else:
                # Verifica se arquivo existe e não está vazio
                pg_path = os.path.join(dir_paginas, pg_id)
                if not os.path.exists(pg_path):
                    missing_pages.append(page_num)
                else:
                    file_size = os.path.getsize(pg_path)
                    if file_size == 0:
                        empty_pages.append(page_num)
                        logger.warning(f"[_verificar_paginas_salvas_eficiente] Página {page_num} está vazia: {pg_path}")
        
        if missing_pages:
            raise Exception(f"Páginas faltantes (não encontradas no filesystem): {missing_pages}")
        
        if empty_pages:
            raise Exception(f"Páginas vazias (tamanho 0 bytes): {empty_pages}")
        
        # Se portal_url fornecido, verifica acessibilidade via HTTP
        # CRÍTICO: Verifica TODAS as páginas via HTTP para garantir que nenhuma esteja faltando
        if portal_url:
            base_url = portal_url.rstrip('/')
            inaccessible_pages = []
            
            # Verifica TODAS as páginas via HTTP (não apenas amostra)
            # Isso garante que nenhuma página esteja faltando antes de retornar SUCCESS
            # CRÍTICO: Usa retry com delay para garantir que arquivos estejam disponíveis via HTTP
            max_http_retries = 3
            http_retry_delay = 1.0  # 1 segundo entre retries
            
            for page_num in range(1, total_pages + 1):
                pg_id = f"pg_{page_num:04d}.pdf"
                page_url = f"{base_url}/@@pagina_processo_adm_integral?cod_documento={cod_documento}&pagina={pg_id}"
                
                page_accessible = False
                last_error = None
                
                # Tenta verificar página com retries
                for retry_num in range(max_http_retries):
                    try:
                        req = urllib.request.Request(page_url, method='HEAD')
                        req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                        req.add_header('Accept', 'application/pdf')
                        
                        # Timeout reduzido para verificação rápida (5 segundos)
                        with urllib.request.urlopen(req, timeout=5) as response:
                            if response.status == 200:
                                page_accessible = True
                                break  # Página está acessível, sai do loop de retries
                            else:
                                last_error = f"Status {response.status}"
                                
                    except urllib.error.HTTPError as e:
                        if e.code == 404:
                            last_error = f"HTTP 404"
                        else:
                            last_error = f"HTTP {e.code}"
                        # Lê e descarta corpo da resposta para evitar problemas
                        try:
                            e.read()
                        except:
                            pass
                        # Se não for 404, pode ser temporário - tenta novamente
                        if e.code != 404 and retry_num < max_http_retries - 1:
                            time.sleep(http_retry_delay)
                            continue
                    except urllib.error.URLError as e:
                        last_error = f"URL Error: {e}"
                        # Erro de conexão/timeout - tenta novamente se houver retries restantes
                        if retry_num < max_http_retries - 1:
                            time.sleep(http_retry_delay)
                            continue
                    except Exception as http_err:
                        last_error = f"Exception: {http_err}"
                        # Tenta novamente se houver retries restantes
                        if retry_num < max_http_retries - 1:
                            time.sleep(http_retry_delay)
                            continue
                    
                    # Se chegou aqui sem sucesso e ainda há retries, já fez sleep dentro do except acima
                    # Não precisa fazer sleep novamente aqui
                
                # Se página não ficou acessível após todos os retries, marca como inacessível
                if not page_accessible:
                    inaccessible_pages.append(page_num)
                    logger.error(f"[_verificar_paginas_salvas_eficiente] ❌ Página {page_num} ({pg_id}) não acessível via HTTP após {max_http_retries} tentativas. Último erro: {last_error}")
                
            if inaccessible_pages:
                error_msg = (
                    f"Páginas não acessíveis via HTTP (404): {inaccessible_pages}. "
                    f"Verifique se os arquivos foram salvos corretamente no diretório {dir_paginas} "
                    f"e se a view pagina_processo_adm_integral está funcionando corretamente."
                )
                logger.error(f"[_verificar_paginas_salvas_eficiente] ❌ {error_msg}")
                raise Exception(error_msg)
        
    except Exception as e:
        logger.error(f"[_verificar_paginas_salvas_eficiente] ❌ Erro na verificação: {str(e)}")
        raise


def salvar_paginas_individuais_celery(pdf_final: fitz.Document, dir_paginas: str, id_processo: str, progress_callback=None) -> None:
    """
    Salva páginas individuais (versão para Celery).
    OTIMIZAÇÃO: Salva páginas em batches para reduzir overhead de I/O.
    CRÍTICO: Garante que todas as páginas sejam salvas corretamente e verificadas após salvamento.
    """
    try:
        os.makedirs(dir_paginas, mode=0o700, exist_ok=True)
        
        total_pages = len(pdf_final)
        page_batches = []
        for i in range(0, total_pages, PAGE_SAVE_BATCH_SIZE):
            batch = list(range(i, min(i + PAGE_SAVE_BATCH_SIZE, total_pages)))
            page_batches.append(batch)
        
        pages_saved_total = 0
        pages_with_errors = []
        
        for batch in page_batches:
            for page_num in batch:
                page_num_display = page_num + 1  # Página 1-indexed para exibição
                nome_arquivo = f"pg_{page_num_display:04d}.pdf"
                caminho_arquivo = secure_path_join(dir_paginas, nome_arquivo)
                
                try:
                    # Remove arquivo existente se houver (pode estar corrompido)
                    if os.path.exists(caminho_arquivo):
                        try:
                            os.remove(caminho_arquivo)
                        except Exception:
                            pass
                    
                    # Cria PDF da página individual
                    with fitz.open() as pagina_pdf:
                        pagina_pdf.insert_pdf(pdf_final, from_page=page_num, to_page=page_num, annots=True)
                        pagina_pdf.set_metadata({
                            "title": f"{id_processo} - Página {page_num_display}",
                            "creator": "Sistema de Processo Administrativo"
                        })
                        pagina_pdf.bake()
                        pagina_pdf.save(caminho_arquivo, **PAGE_SAVE_OPTIMIZATION_SETTINGS)
                    
                    # CRÍTICO: Verifica se arquivo foi salvo corretamente após salvamento
                    if not os.path.exists(caminho_arquivo):
                        raise Exception(f"Arquivo não encontrado após salvamento: {caminho_arquivo}")
                    
                    file_size = os.path.getsize(caminho_arquivo)
                    if file_size == 0:
                        raise Exception(f"Arquivo está vazio após salvamento: {caminho_arquivo} (0 bytes)")
                    
                    # Força flush do filesystem para garantir que arquivo foi escrito
                    try:
                        fd = os.open(caminho_arquivo, os.O_RDONLY)
                        os.fsync(fd)
                        os.close(fd)
                    except Exception:
                        pass  # Ignora erros de sync (pode não estar disponível em todos os sistemas)
                    
                    pages_saved_total += 1
                    
                    if progress_callback:
                        try:
                            progress_callback(pages_saved_total, total_pages)
                        except Exception:
                            pass
                    
                except Exception as e:
                    error_msg = f"Erro ao salvar página {page_num_display} ({nome_arquivo}): {e}"
                    logger.error(f"[salvar_paginas_individuais_celery] ❌ {error_msg}")
                    pages_with_errors.append((page_num_display, nome_arquivo, str(e)))
                    # NÃO continua silenciosamente - falha se houver erro
                    raise Exception(error_msg)
        
        # Verificação final após salvar todas as páginas
        if pages_saved_total != total_pages:
            raise Exception(
                f"Não todas as páginas foram salvas: esperado {total_pages}, salvo {pages_saved_total}. "
                f"Erros: {pages_with_errors}"
            )
        
        # Força sincronização final do filesystem
        try:
            import subprocess
            subprocess.run(['sync'], timeout=5, check=False, capture_output=True)
        except Exception:
            pass  # Ignora erros de sync
        
    except Exception as e:
        logger.error(f"[salvar_paginas_individuais_celery] ❌ Erro ao salvar páginas: {str(e)}", exc_info=True)
        raise


@zope_task(bind=True, max_retries=3, default_retry_delay=30, name='tasks_folder.processo_adm_task.gerar_processo_adm_integral_task')
def gerar_processo_adm_integral_task(self, site, cod_documento: int, portal_url: str):
    """
    Task Celery para gerar processo administrativo integral.
    
    Args:
        self: Instância da task (injetado pelo decorator)
        site: Objeto site do Zope (injetado pelo decorator, mas não usado diretamente)
        cod_documento: Código do documento administrativo
        portal_url: URL do portal Zope
        
    Returns:
        dict: Resultado da geração
    """
    task_id = getattr(self.request, 'id', 'UNKNOWN')
    
    # Atualiza progresso
    self.update_state(
        state='PROGRESS',
        meta={
            'current': 0,
            'total': 100,
            'status': 'Iniciando...',
            'stage': ProcessStage.INIT
        }
    )
    
    try:
        # Calcula diretório base
        dir_base = get_processo_dir_adm(cod_documento) if get_processo_dir_adm else None
        if not dir_base:
            install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
            hash_documento = hashlib.md5(str(cod_documento).encode()).hexdigest()
            dir_base = os.path.join(install_home, f'var/tmp/processo_adm_integral_{hash_documento}')
        
        pagepath = os.path.join(dir_base, 'pages')
        
        # VERIFICAÇÃO DE CACHE: Verifica se precisa regenerar
        # CRÍTICO: Inicializa documents_sizes antes de qualquer uso (evita UnboundLocalError)
        documents_sizes = {}
        
        if _load_cache_from_filesystem_adm:
            try:
                # Carrega cache do filesystem (retorna dict completo)
                cache_data = _load_cache_from_filesystem_adm(cod_documento)
                if cache_data and isinstance(cache_data, dict):
                    # CRÍTICO: O cache salvo usa chaves 'hash' e 'sizes', não 'documents_hash' e 'documents_sizes'
                    timestamp = cache_data.get('timestamp')
                    documents_hash = cache_data.get('hash')  # Chave correta: 'hash', não 'documents_hash'
                    documents_sizes_from_cache = cache_data.get('sizes')  # Chave correta: 'sizes', não 'documents_sizes'
                    
                    # Usa documents_sizes do cache se disponível
                    if documents_sizes_from_cache and isinstance(documents_sizes_from_cache, dict):
                        documents_sizes = documents_sizes_from_cache
                    
                    # Verifica idade do cache
                    if timestamp is not None:
                        current_time = time.time()
                        cache_age = current_time - timestamp
                        
                        # Se cache é recente (menos de 1 hora), verifica se PDF existe
                        if cache_age < 3600:  # 1 hora
                            # CRÍTICO: Obtém nome do arquivo correto dos metadados ou tenta encontrar no diretório
                            # O nome do arquivo pode ser PA-308-2025.pdf (não processo_integral.pdf)
                            pdf_final_path = None
                            processo_integral_nome = None
                            
                            # Tenta obter nome do arquivo dos metadados primeiro
                            metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                            if os.path.exists(metadados_path):
                                try:
                                    with open(metadados_path, 'r', encoding='utf-8') as f:
                                        metadados = json.load(f)
                                    processo_integral_nome = metadados.get('arquivo_final')
                                    if processo_integral_nome:
                                        pdf_final_path = os.path.join(dir_base, processo_integral_nome)
                                except Exception:
                                    pass
                            
                            # Se não encontrou nos metadados, tenta encontrar qualquer PDF no diretório
                            # que não seja página individual (não começa com 'pg_')
                            if not pdf_final_path or not os.path.exists(pdf_final_path):
                                try:
                                    if os.path.exists(dir_base):
                                        pdf_files = [f for f in os.listdir(dir_base) 
                                                    if f.endswith('.pdf') and not f.startswith('pg_') 
                                                    and not f.startswith('capa_') and f != 'folha_cientificacoes.pdf']
                                        if pdf_files:
                                            # Pega o primeiro PDF encontrado (deve ser o processo integral)
                                            processo_integral_nome = pdf_files[0]
                                            pdf_final_path = os.path.join(dir_base, processo_integral_nome)
                                except Exception:
                                    pass
                            
                            # Se encontrou PDF válido, retorna cache
                            if pdf_final_path and os.path.exists(pdf_final_path):
                                file_size = os.path.getsize(pdf_final_path)
                                if file_size > 0:
                                    self.update_state(
                                        state='SUCCESS',
                                        meta={
                                            'current': 100,
                                            'total': 100,
                                            'status': 'Cache válido - PDF já existe',
                                            'stage': ProcessStage.CONCLUIDO,
                                            'cached': True,
                                            'arquivo': processo_integral_nome or 'processo_integral.pdf'
                                        }
                                    )
                                    return {
                                        'success': True,
                                        'cached': True,
                                        'pdf_path': pdf_final_path,
                                        'pages_path': pagepath,
                                        'arquivo': processo_integral_nome or 'processo_integral.pdf',
                                        'message': 'PDF gerado anteriormente (cache válido)'
                                    }
            except Exception as cache_err:
                # Continua com geração normal se verificação de cache falhar
                # documents_sizes permanece como {} (já inicializado)
                pass
        
        # Inicializa pdf_final_path com nome padrão (será atualizado depois com nome correto)
        pdf_final_path = os.path.join(dir_base, 'processo_integral.pdf')
        
        # Prepara diretórios
        os.makedirs(dir_base, exist_ok=True)
        os.makedirs(pagepath, exist_ok=True)
        
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 5,
                'total': 100,
                'status': 'Preparando diretórios...',
                'stage': ProcessStage.PREPARAR_DIRS
            }
        )
        
        # Coleta documentos usando SQLAlchemy diretamente na task
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 10,
                'total': 100,
                'status': 'Coletando documentos...',
                'stage': ProcessStage.COLETAR_DOCS
            }
        )
        
        # Coleta documentos via HTTP (mesmo padrão do processo_leg)
        # Faz chamada HTTP para ProcessoAdmTaskExecutor que roda no contexto Zope
        # e tem acesso ao componente registry para obter a sessão SQLAlchemy
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 10,
                'total': 100,
                'status': 'Fazendo download dos arquivos...',
                'stage': ProcessStage.COLETAR_DOCS
            }
        )
        
        # Constrói URL da view ProcessoAdmTaskExecutor
        base_url = portal_url.rstrip('/')
        if '/sagl/' not in base_url:
            executor_url = f"{base_url}/sagl/@@processo_adm_task_executor"
        else:
            executor_url = f"{base_url}/@@processo_adm_task_executor"
        
        # Prepara dados para POST
        data = {
            'cod_documento': str(cod_documento),
            'portal_url': portal_url,
        }
        
        # Codifica dados para POST
        post_data = urllib.parse.urlencode(data).encode('utf-8')
        
        # Inicializa processo_integral_nome com valor padrão (será sobrescrito se HTTP for bem-sucedido)
        processo_integral_nome = f"documento-{cod_documento}.pdf"
        
        # Faz chamada HTTP POST para a view (apenas para download)
        try:
            req = urllib.request.Request(
                executor_url,
                data=post_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            with urllib.request.urlopen(req, timeout=600) as response:  # Timeout de 10 minutos para download
                response_data = response.read().decode('utf-8')
                download_result = json.loads(response_data)
                
                if not download_result.get('success'):
                    error_msg = download_result.get('error', 'Erro desconhecido')
                    raise Exception(f"Erro ao fazer download dos arquivos: {error_msg}")
                
                # Extrai dados do resultado
                dir_base_from_response = download_result.get('dir_base')
                dir_paginas = download_result.get('dir_paginas')
                id_processo = download_result.get('id_processo')
                documentos = download_result.get('documentos', [])
                dados_documento = download_result.get('dados_documento', {})
                
                # Usa dir_base da resposta se fornecido, senão usa o calculado
                if dir_base_from_response:
                    dir_base = dir_base_from_response
                    pagepath = dir_paginas if dir_paginas else os.path.join(dir_base, 'pages')
                
                # Constrói nome do arquivo final a partir dos dados do documento
                # Formato: PA-308-2025.pdf (mesmo formato usado na view)
                if dados_documento:
                    tipo = dados_documento.get('tipo', 'DOC')
                    numero = dados_documento.get('numero', cod_documento)
                    ano = dados_documento.get('ano', datetime.now().year)
                    processo_integral_nome = f"{tipo}-{numero}-{ano}.pdf"
                else:
                    # Fallback: usa id_processo ou cod_documento
                    if id_processo:
                        # Remove espaços do id_processo para formar nome do arquivo
                        processo_integral_nome = id_processo.replace(' ', '-').replace('/', '-') + '.pdf'
                    # Se não tiver id_processo, usa o valor padrão já definido
                
                # Atualiza pdf_final_path com o nome correto
                pdf_final_path = os.path.join(dir_base, processo_integral_nome)
                    
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
            logger.error(f"[gerar_processo_adm_integral_task] Erro HTTP {e.code}: {error_body}")
            raise Exception(f"Erro HTTP {e.code} ao fazer download dos arquivos: {error_body}")
        except urllib.error.URLError as e:
            logger.error(f"[gerar_processo_adm_integral_task] Erro de URL: {e}")
            raise Exception(f"Erro de conexão ao fazer download dos arquivos: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"[gerar_processo_adm_integral_task] Erro ao decodificar JSON: {e}")
            raise Exception(f"Resposta inválida do servidor: {str(e)}")
        except Exception as e:
            logger.error(f"[gerar_processo_adm_integral_task] Erro inesperado na chamada HTTP: {e}", exc_info=True)
            raise
        
        # IMPORTANTE: A capa deve sempre ser coletada (sempre gerada)
        # Se não há capa, significa que houve erro na geração (que já foi tratado acima)
        # Se há capa mas nenhum outro documento, isso é aceitável - pelo menos a capa existe
        if not documentos:
            mensagem_erro = (
                f"Nenhum documento foi coletado para o processo administrativo {cod_documento}, "
                f"incluindo a capa que deveria ser sempre gerada. "
                f"Verifique se houve erro na geração da capa ou se os arquivos PDF existem no ZODB: "
                f"- Texto integral: {cod_documento}_texto_integral.pdf, "
                f"- Documentos acessórios: {{cod}}_acessorio.pdf, "
                f"- Tramitações: {{cod}}_tram.pdf em sapl_documentos/administrativo/tramitacao/."
            )
            logger.error(f"[gerar_processo_adm_integral_task] {mensagem_erro}")
            raise Exception(mensagem_erro)
        
        # Se há pelo menos a capa, é válido continuar mesmo sem outros documentos
        if len(documentos) == 1 and documentos[0].get('title') == 'Capa do Processo':
            pass  # Apenas a capa foi coletada - processo continuará apenas com a capa
        
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 70,
                'total': 100,
                'status': 'Mesclando documentos...',
                'stage': ProcessStage.MESCLAR_DOCS
            }
        )
        
        # Mescla documentos com callback de progresso
        def progress_callback_mesclar(current_doc, total_docs, current_pages):
            """Callback para atualizar progresso durante mesclagem"""
            progress = 70 + int((current_doc / total_docs) * 15) if total_docs > 0 else 70
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': progress,
                    'total': 100,
                    'status': f'Mesclando documentos... ({current_doc}/{total_docs} documentos, {current_pages} páginas)',
                    'stage': ProcessStage.MESCLAR_DOCS
                }
            )
        
        pdf_final, documentos_com_paginas = mesclar_documentos_celery(
            documentos, dir_base, id_processo, progress_callback=progress_callback_mesclar
        )
        
        total_paginas = len(pdf_final)
        
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 85,
                'total': 100,
                'status': 'Salvando páginas individuais...',
                'stage': ProcessStage.SALVAR_PAGINAS
            }
        )
        
        # Salva páginas individuais com callback de progresso
        def progress_callback_salvar(current_pages, total_pages):
            """Callback para atualizar progresso durante salvamento de páginas"""
            progress = 85 + int((current_pages / total_pages) * 10) if total_pages > 0 else 85
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': progress,
                    'total': 100,
                    'status': f'Salvando páginas individuais... ({current_pages}/{total_pages} páginas)',
                    'stage': ProcessStage.SALVAR_PAGINAS
                }
            )
        
        salvar_paginas_individuais_celery(
            pdf_final, pagepath, id_processo, progress_callback=progress_callback_salvar
        )
        
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 95,
                'total': 100,
                'status': 'Salvando PDF final...',
                'stage': ProcessStage.SALVAR_PDF
            }
        )
        
        # Salva PDF final
        caminho_arquivo_final = os.path.join(dir_base, processo_integral_nome)
        if os.path.exists(caminho_arquivo_final):
            try:
                os.remove(caminho_arquivo_final)
            except Exception:
                pass
        
        pdf_final.save(caminho_arquivo_final, **PDF_OPTIMIZATION_SETTINGS)
        
        # Salva metadados e cache
        # CRÍTICO: documents_sizes já foi inicializado acima (no início da função, antes do bloco de cache)
        # Aqui vamos reinicializar para coletar os tamanhos dos documentos processados agora
        documentos_sizes = {}
        
        metadados = {
            'cod_documento': cod_documento,
            'id_processo': id_processo,
            'data_geracao': datetime.now().isoformat(),
            'total_paginas': total_paginas,
            'arquivo_final': processo_integral_nome,  # CRÍTICO: Nome do arquivo PDF final gerado
            'documentos': []
        }
        
        documentos_metadados = []
        
        for doc in documentos_com_paginas:
            doc_info = {
                'title': doc.get('title', ''),
                'data': doc.get('data', ''),
                'file': doc.get('file', ''),
                'file_size': doc.get('file_size', 0),
                'start_page': doc.get('start_page', 1),
                'end_page': doc.get('end_page', 1),
                'num_pages': doc.get('num_pages', 1)
            }
            # CRÍTICO: Inclui count para folha de cientificações (permite comparação correta)
            # Se o documento tiver count (folha de cientificações), inclui nos metadados
            if 'count' in doc:
                doc_info['count'] = doc.get('count', 0)
            metadados['documentos'].append(doc_info)
            
            # Prepara dados para cache (inclui count se presente)
            cache_doc_info = {
                'file': doc.get('file', ''),
                'file_size': doc.get('file_size', 0),
                'title': doc.get('title', '')
            }
            # CRÍTICO: Inclui count para folha de cientificações no cache também
            if 'count' in doc:
                cache_doc_info['count'] = doc.get('count', 0)
            documentos_metadados.append(cache_doc_info)
            documentos_sizes[doc.get('file', '')] = doc.get('file_size', 0)
        
        # Salva metadados JSON
        metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
        with open(metadados_path, 'w', encoding='utf-8') as f:
            json.dump(metadados, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        
        # Salva cache (com hash e timestamp)
        if _save_cache_to_filesystem_adm:
            try:
                # Calcula hash dos documentos (requer portal, pode falhar no Celery)
                # Por enquanto, usa hash baseado nos metadados salvos
                timestamp = time.time()
                hash_data_string = json.dumps(documentos_metadados, sort_keys=True, default=str)
                documents_hash = hashlib.md5(hash_data_string.encode('utf-8')).hexdigest()
                
                # CRÍTICO: Constrói dict completo para o cache (mesmo formato usado em pasta_digital.py)
                # Inclui todos os campos necessários: documentos, total_paginas, status, message
                cache_data_dict = {
                    'documentos': metadados.get('documentos', []),  # Usa documentos completos do metadados
                    'total_paginas': total_paginas,
                    'cod_documento': cod_documento,
                    'status': 'SUCCESS',
                    'message': 'Pasta digital gerada com sucesso'
                }
                
                # Salva cache usando função do pasta_digital
                # Nota: A função pode precisar do portal para calcular hash completo
                # Por enquanto, salva com hash simplificado
                _save_cache_to_filesystem_adm(
                    cod_documento,
                    cache_data_dict,  # Passa dict completo ao invés de apenas lista
                    timestamp,
                    documents_hash,
                    documents_sizes
                )
                
                # Verifica se o arquivo foi realmente criado
                from openlegis.sagl.browser.processo_adm.processo_adm_utils import get_cache_file_path_adm
                cache_file = get_cache_file_path_adm(cod_documento)
                if not os.path.exists(cache_file):
                    logger.error(f"[gerar_processo_adm_integral_task] ❌ ERRO: cache.json não foi criado! Caminho esperado: {cache_file}")
            except Exception as cache_err:
                logger.error(f"[gerar_processo_adm_integral_task] ❌ Erro ao salvar cache: {cache_err}", exc_info=True)
                # Não falha a task se cache não puder ser salvo, mas loga o erro
        
        # CRÍTICO: Verificação final - garante que TODOS os arquivos existem antes de retornar SUCCESS
        # Mesmo padrão do processo_leg: verifica metadados e páginas antes de retornar SUCCESS
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 98,
                'total': 100,
                'status': 'PDF final salvo, verificando integridade...',
                'stage': ProcessStage.SALVAR_PDF
            }
        )
        
        # Verifica metadados (verificação final)
        if not os.path.exists(metadados_path):
            raise Exception(f"Metadados não encontrados após verificação final: {metadados_path}")
        
        # CRÍTICO: Verificação completa de todas as páginas antes de retornar SUCCESS
        # Garante que TODAS as páginas existem no filesystem e são acessíveis via HTTP
        _verificar_paginas_salvas_eficiente(pagepath, total_paginas, cod_documento, portal_url)
        
        # Marca como pronto
        ready_file = os.path.join(dir_base, '.ready')
        with open(ready_file, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # SOMENTE APÓS TODAS AS VERIFICAÇÕES: Atualiza progresso para SUCCESS
        self.update_state(
            state='SUCCESS',
            meta={
                'current': 100,
                'total': 100,
                'status': 'Processo administrativo gerado com sucesso!',
                'stage': ProcessStage.CONCLUIDO,
                'arquivo': processo_integral_nome,
                'dir_base': dir_base
            }
        )
        
        return {
            'status': 'SUCCESS',
            'cod_documento': cod_documento,
            'total_paginas': total_paginas,
            'arquivo': processo_integral_nome,
            'dir_base': dir_base,
            'message': 'Processo administrativo gerado com sucesso'
        }
        
    except Exception as e:
        logger.error(f"[gerar_processo_adm_integral_task] Erro na task {task_id}: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'status': 'Erro ao gerar processo'
            }
        )
        raise
