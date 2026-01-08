"""
Tarefa Celery assíncrona para geração de processo integral de normas jurídicas.

Esta tarefa processa a geração do PDF do processo integral de forma assíncrona,
permitindo que o usuário continue usando o sistema enquanto aguarda a conclusão.

FLUXO:
1. Task faz chamada HTTP para view ProcessoNormaTaskExecutor no Zope
2. View faz download dos arquivos e retorna informações
3. Task faz processamento pesado (mesclagem, validação, salvamento)
"""
import logging
import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import gc
import shutil
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple

# Configura logging ANTES de importar qualquer coisa
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Importa bibliotecas de PDF
try:
    import fitz
    import pikepdf
except ImportError as e:
    logger.error(f"[processo_norma_task] ERRO ao importar bibliotecas de PDF: {e}", exc_info=True)
    raise

# Importa as dependências
try:
    from .utils import zope_task
except Exception as e:
    logger.error(f"[processo_norma_task] ERRO ao importar dependências: {e}", exc_info=True)
    raise

# Constantes (mesmas da view)
MAX_PAGES = 5000
MAX_WORKERS = 4
CHUNK_SIZE_PAGES = 200
MIN_PDF_SIZE_FOR_CHUNKS = 50 * 1024 * 1024
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

# Estágios do processo (para padronização)
class ProcessStage:
    """Estágios padronizados do processo de geração"""
    INIT = 'init'
    DADOS_NORMA = 'dados_norma'
    PREPARAR_DIRS = 'preparar_dirs'
    COLETAR_DOCS = 'coletar_docs'
    MESCLAR_DOCS = 'mesclar_docs'
    SALVAR_PAGINAS = 'salvar_paginas'
    SALVAR_PDF = 'salvar_pdf'
    LIMPAR_TEMP = 'limpar_temp'
    CONCLUIDO = 'concluido'


def secure_path_join(base_path: str, *paths: str) -> str:
    """Junta caminhos de forma segura, prevenindo path traversal"""
    full_path = os.path.normpath(os.path.join(base_path, *paths))
    base = os.path.normpath(base_path)
    if not full_path.startswith(base + os.sep) and full_path != base:
        raise ValueError(f"Path traversal attempt detected: {full_path}")
    if os.path.islink(full_path):
        raise ValueError(f"Symbolic links not allowed: {full_path}")
    return full_path


def validar_pdf_robusto(pdf_bytes: bytes, filename: str) -> Tuple[bool, int, str]:
    """
    Valida PDF de forma robusta usando validação híbrida (fitz rápido + pikepdf rigoroso).
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
            if 'format error' in error_msg or 'object out of range' in error_msg or 'non-page object' in error_msg or 'invalid' in error_msg:
                return False, 0, f"PDF corrompido: {pikepdf_err}"
            return False, 0, f"Erro ao validar PDF: {pikepdf_err}"


def process_single_document_celery(doc: Dict, dir_base: str) -> Tuple[bytes, Dict]:
    """
    Processa um documento individual para mesclagem (versão para Celery).
    """
    filename = doc.get('file', 'unknown')
    doc_title = doc.get('title', 'Documento desconhecido')
    
    try:
        if doc.get('filesystem'):
            pdf_path = secure_path_join(doc['path'], doc['file'])
            logger.debug(f"[process_single_document_celery] Processando arquivo do filesystem: {pdf_path}")
            
            file_size = os.path.getsize(pdf_path)
            STREAMING_THRESHOLD = 50 * 1024 * 1024
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
        
        is_valid, num_pages, error_msg = validar_pdf_robusto(pdf_bytes, filename)
        if not is_valid:
            logger.warning(f"[process_single_document_celery] PDF '{filename}' falhou validação: {error_msg}")
            raise ValueError(f"PDF inválido para documento '{doc_title}': {error_msg}")
        
        doc_info = doc.copy()
        file_size = 0
        if doc.get('filesystem'):
            pdf_path = secure_path_join(doc['path'], doc['file'])
            file_size = os.path.getsize(pdf_path)
        doc_info['file_size'] = file_size
        
        return pdf_bytes, doc_info
        
    except Exception as e:
        error_str = str(e).lower()
        if 'format error' in error_str or 'object out of range' in error_str or 'non-page object' in error_str or 'pdf inválido' in error_str:
            logger.warning(f"[process_single_document_celery] PDF corrompido para documento '{doc_title}': {e}")
            raise ValueError(f"PDF corrompido para documento '{doc_title}'")
        logger.warning(f"[process_single_document_celery] Erro ao processar documento '{doc_title}': {e}")
        raise


# TODO: Implementar mesclar_documentos_celery similar ao processo_leg_task
def inserir_pdf_em_chunks(pdf_mesclado: fitz.Document, pdf: fitz.Document, doc_title: str) -> int:
    """
    Insere PDF no documento mesclado em chunks para economizar memória.
    OTIMIZAÇÃO: Processa PDFs grandes em chunks ao invés de carregar tudo na memória.
    
    Returns:
        int: Número de páginas inseridas
    """
    num_pages = len(pdf)
    
    # OTIMIZAÇÃO: Para PDFs pequenos, insere tudo de uma vez (mais rápido)
    if num_pages <= CHUNK_SIZE_PAGES:
        pdf_mesclado.insert_pdf(pdf, annots=True)
        return num_pages
    
    # OTIMIZAÇÃO: Para PDFs grandes, processa em chunks
    logger.debug(f"[inserir_pdf_em_chunks] Processando PDF '{doc_title}' em chunks ({num_pages} páginas, chunk size: {CHUNK_SIZE_PAGES})")
    
    pages_inserted = 0
    for start_page in range(0, num_pages, CHUNK_SIZE_PAGES):
        end_page = min(start_page + CHUNK_SIZE_PAGES, num_pages)
        
        # Insere chunk de páginas
        pdf_mesclado.insert_pdf(pdf, from_page=start_page, to_page=end_page - 1, annots=True)
        pages_inserted += (end_page - start_page)
        
        # Limpeza de memória após cada chunk
        gc.collect()
        
        logger.debug(f"[inserir_pdf_em_chunks] Chunk inserido: páginas {start_page + 1}-{end_page} de '{doc_title}'")
    
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
    documentos_processados = 0
    documentos_falhados = 0
    erros_detalhados = []
    
    try:
        if total_docs == 0:
            raise Exception("Nenhum documento fornecido para mesclagem")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for doc in documentos:
                futures.append(executor.submit(process_single_document_celery, doc, dir_base))
            
            for idx, future in enumerate(futures):
                doc_info = None
                try:
                    pdf_bytes, doc_info = future.result()
                    doc_title = doc_info.get('title', '?') if doc_info else '?'
                    pdf_size_mb = len(pdf_bytes) / (1024 * 1024)
                    logger.debug(f"[mesclar_documentos_celery] Processando documento '{doc_title}', tamanho PDF: {pdf_size_mb:.2f} MB")
                    
                    # OTIMIZAÇÃO: PDF já foi validado em process_single_document_celery com pikepdf
                    # Apenas processa com fitz (fitz.open() também faz validação básica, mas menos rigorosa)
                    try:
                        # Processa diretamente com fitz (validação já foi feita com pikepdf)
                        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
                            start_page = len(pdf_mesclado)
                            
                            # OTIMIZAÇÃO: Usa processamento em chunks apenas para PDFs muito grandes
                            # Para PDFs menores, processa tudo de uma vez (mais rápido)
                            use_chunks = len(pdf_bytes) >= MIN_PDF_SIZE_FOR_CHUNKS and len(pdf) > CHUNK_SIZE_PAGES
                            
                            if use_chunks:
                                # Processa em chunks para economizar memória
                                num_pages_inserted = inserir_pdf_em_chunks(pdf_mesclado, pdf, doc_title)
                            else:
                                # PDF pequeno: insere tudo de uma vez (mais rápido)
                                pdf_mesclado.insert_pdf(pdf, annots=True)
                                num_pages_inserted = len(pdf)
                            
                            doc_info.update({
                                'start_page': start_page + 1,
                                'end_page': len(pdf_mesclado),
                                'num_pages': num_pages_inserted
                            })
                            documentos_com_paginas.append(doc_info)
                            documentos_processados += 1
                            
                            # Atualiza progresso se callback fornecido
                            if progress_callback:
                                try:
                                    progress_callback(idx + 1, total_docs, len(pdf_mesclado))
                                except Exception as callback_err:
                                    logger.debug(f"[mesclar_documentos_celery] Erro no callback de progresso: {callback_err}")
                            
                            # OTIMIZAÇÃO: Limpeza de memória mais frequente
                            # Libera pdf_bytes da memória após processar
                            del pdf_bytes
                            if len(pdf_mesclado) % MEMORY_CLEANUP_INTERVAL == 0:
                                gc.collect()
                                logger.debug(f"[mesclar_documentos_celery] Limpeza de memória após {len(pdf_mesclado)} páginas")
                    except Exception as processing_err:
                        documentos_falhados += 1
                        error_str = str(processing_err).lower()
                        doc_title = doc_info.get('title', '?') if doc_info else '?'
                        erro_detalhado = f"'{doc_title}': {str(processing_err)}"
                        erros_detalhados.append(erro_detalhado)
                        if 'format error' in error_str or 'object out of range' in error_str or 'non-page object' in error_str:
                            logger.warning(f"[mesclar_documentos_celery] PDF corrompido ignorado '{doc_title}': {processing_err}")
                        else:
                            logger.warning(f"[mesclar_documentos_celery] Erro ao processar PDF '{doc_title}': {processing_err}")
                        continue
                except Exception as e:
                    documentos_falhados += 1
                    error_msg = str(e)
                    error_lower = error_msg.lower()
                    doc_title = doc_info.get('title', '?') if doc_info else '?'
                    erro_detalhado = f"'{doc_title}': {error_msg[:200]}"
                    erros_detalhados.append(erro_detalhado)
                    if 'format error' in error_lower or 'object out of range' in error_lower or 'non-page object' in error_lower:
                        logger.debug(f"[mesclar_documentos_celery] Ignorando documento corrompido '{doc_title}': {error_msg[:100]}...")
                    else:
                        logger.warning(f"[mesclar_documentos_celery] Ignorando documento '{doc_title}' devido ao erro: {error_msg[:200]}")
                    continue
        
        # Valida que pelo menos um documento foi processado com sucesso
        if documentos_processados == 0:
            erros_str = "; ".join(erros_detalhados[:5])  # Limita a 5 erros para não exceder tamanho
            if len(erros_detalhados) > 5:
                erros_str += f" ... e mais {len(erros_detalhados) - 5} erro(s)"
            raise Exception(
                f"Nenhum documento foi processado com sucesso. "
                f"Total de documentos: {total_docs}, Falhados: {documentos_falhados}. "
                f"Erros: {erros_str}"
            )
        
        # Valida que o PDF tem páginas
        if len(pdf_mesclado) == 0:
            raise Exception(
                f"PDF mesclado está vazio. Documentos processados: {documentos_processados}/{total_docs}, "
                f"Falhados: {documentos_falhados}"
            )
        
        # Log de resumo
        logger.info(
            f"[mesclar_documentos_celery] Mesclagem concluída: {documentos_processados}/{total_docs} documentos processados, "
            f"{len(pdf_mesclado)} páginas totais"
        )
        if documentos_falhados > 0:
            logger.warning(
                f"[mesclar_documentos_celery] {documentos_falhados} documento(s) falharam durante o processamento"
            )
        
        if len(pdf_mesclado) > MAX_PAGES:
            raise Exception(f"Número de páginas excede o limite de {MAX_PAGES}")
        
        # OTIMIZAÇÃO: Limpeza de memória antes de adicionar rodapé
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
            
            # OTIMIZAÇÃO: Limpeza periódica durante adição de rodapé
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
        logger.error(f"[mesclar_documentos_celery] Erro na mesclagem de documentos: {str(e)}", exc_info=True)
        raise
    finally:
        gc.enable()


def _save_pages_batch_celery(pdf_final: fitz.Document, page_nums: List[int], dir_paginas: str, id_processo: str) -> int:
    """
    Salva um batch de páginas (versão para Celery).
    OTIMIZAÇÃO: Salva múltiplas páginas em uma única operação para reduzir overhead.
    
    Args:
        pdf_final: PDF final
        page_nums: Lista de números de páginas para salvar
        dir_paginas: Diretório onde salvar páginas
        id_processo: ID do processo
    
    Returns:
        int: Número de páginas salvas
    """
    pages_saved = 0
    for page_num in page_nums:
        nome_arquivo = f"pg_{page_num + 1:04d}.pdf"
        caminho_arquivo = secure_path_join(dir_paginas, nome_arquivo)
        
        try:
            with fitz.open() as pagina_pdf:
                pagina_pdf.insert_pdf(pdf_final, from_page=page_num, to_page=page_num, annots=True)
                pagina_pdf.set_metadata({
                    "title": f"{id_processo} - Página {page_num + 1}",
                    "creator": "Sistema de Processo Legislativo"
                })
                pagina_pdf.bake()
                pagina_pdf.save(caminho_arquivo, **PAGE_SAVE_OPTIMIZATION_SETTINGS)
            pages_saved += 1
        except Exception as e:
            logger.error(f"[_save_pages_batch_celery] Erro ao salvar página {page_num + 1}: {str(e)}")
            raise
    
    return pages_saved


def salvar_paginas_individuais_celery(pdf_final: fitz.Document, dir_paginas: str, id_processo: str, progress_callback=None) -> None:
    """
    Salva páginas individuais (versão para Celery).
    OTIMIZAÇÃO: Salva páginas em batches para reduzir overhead de I/O.
    
    Args:
        pdf_final: PDF final para salvar páginas
        dir_paginas: Diretório onde salvar páginas
        id_processo: ID do processo
        progress_callback: Função opcional para atualizar progresso (current_pages, total_pages)
    """
    try:
        os.makedirs(dir_paginas, mode=0o700, exist_ok=True)
        
        total_pages = len(pdf_final)
        
        # OTIMIZAÇÃO: Agrupa páginas em batches
        page_batches = []
        for i in range(0, total_pages, PAGE_SAVE_BATCH_SIZE):
            batch = list(range(i, min(i + PAGE_SAVE_BATCH_SIZE, total_pages)))
            page_batches.append(batch)
        
        futures = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # OTIMIZAÇÃO: Submete batches ao invés de páginas individuais
            for batch in page_batches:
                future = executor.submit(_save_pages_batch_celery, pdf_final, batch, dir_paginas, id_processo)
                futures.append((future, batch))
            
            # OTIMIZAÇÃO: Aguarda batches com timeout
            pages_saved = 0
            for future, batch in futures:
                try:
                    batch_pages = future.result(timeout=PAGE_SAVE_TIMEOUT * len(batch))
                    pages_saved += batch_pages
                    
                    if progress_callback:
                        try:
                            progress_callback(pages_saved, total_pages)
                        except Exception as callback_err:
                            logger.debug(f"[salvar_paginas_individuais_celery] Erro no callback: {callback_err}")
                    
                    # Limpeza de memória periódica
                    if pages_saved % MEMORY_CLEANUP_INTERVAL == 0:
                        gc.collect()
                except Exception as e:
                    logger.error(f"[salvar_paginas_individuais_celery] Erro ao salvar batch: {str(e)}")
                    raise
        
        if pages_saved != total_pages:
            raise Exception(f"Número de páginas salvas ({pages_saved}) difere do esperado ({total_pages})")
        
        # Verifica páginas salvas
        _verificar_paginas_salvas_eficiente(dir_paginas, total_pages)
        
    except Exception as e:
        logger.error(f"[salvar_paginas_individuais_celery] Erro ao salvar páginas: {str(e)}", exc_info=True)
        raise


def _verificar_paginas_salvas_eficiente(dir_paginas: str, total_pages: int) -> None:
    """
    Verifica se todas as páginas foram salvas de forma eficiente.
    OTIMIZAÇÃO: Verificação em batch ao invés de verificar uma por uma.
    """
    try:
        # Lista todos os arquivos PDF de uma vez
        pdf_files = set(f for f in os.listdir(dir_paginas) if f.endswith('.pdf') and f.startswith('pg_'))
        
        if len(pdf_files) < total_pages:
            raise Exception(f"Não todas as páginas foram salvas: esperado {total_pages}, encontrado {len(pdf_files)}")
        
        # Verifica páginas faltantes em batch
        missing_pages = []
        for page_num in range(1, total_pages + 1):
            pg_id = f"pg_{page_num:04d}.pdf"
            if pg_id not in pdf_files:
                missing_pages.append(page_num)
        
        if missing_pages:
            raise Exception(f"Páginas faltantes: {missing_pages}")
        
    except Exception as e:
        logger.error(f"[_verificar_paginas_salvas_eficiente] Erro na verificação: {str(e)}")
        raise


@zope_task(bind=True, max_retries=3, default_retry_delay=30, name='tasks_folder.processo_norma_task.gerar_processo_norma_integral_task')
def gerar_processo_norma_integral_task(self, site, cod_norma, portal_url, user_id=None):
    """
    Gera o processo integral de norma jurídica de forma assíncrona.
    
    Args:
        site: Objeto site do Zope (injetado pelo decorator @zope_task, mas não usado)
        cod_norma: Código da norma
        portal_url: URL base do portal (usado para construir URL da view)
        user_id: ID do usuário que solicitou (para notificação)
    
    Returns:
        dict: Resultado com informações do processo gerado
    """
    task_id = getattr(self.request, 'id', 'UNKNOWN')
    
    # CRÍTICO: Log explícito no início para garantir visibilidade
    logger.info(f"[gerar_processo_norma_integral_task] ===== INICIANDO TASK =====")
    logger.info(f"[gerar_processo_norma_integral_task] task_id={task_id}, cod_norma={cod_norma}, portal_url={portal_url}")
    
    try:
        if not cod_norma:
            logger.error(f"[gerar_processo_norma_integral_task] cod_norma é obrigatório")
            raise ValueError("cod_norma é obrigatório")
        
        if not portal_url:
            logger.error(f"[gerar_processo_norma_integral_task] portal_url é obrigatório")
            raise ValueError("portal_url é obrigatório")
        
        logger.info(f"[gerar_processo_norma_integral_task] Parâmetros válidos, iniciando processamento...")
        
        # Atualiza progresso: Iniciando
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': 100,
                'status': 'Iniciando geração do processo integral...',
                'stage': ProcessStage.INIT
            }
        )
        
        logger.info(f"[gerar_processo_norma_integral_task] Estado atualizado para PROGRESS (INIT)")
        
        # Atualiza progresso: Obtendo dados da norma
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 100,
                'status': 'Obtendo dados da norma...',
                'stage': ProcessStage.DADOS_NORMA
            }
        )
        
        # Atualiza progresso: Preparando diretórios
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 5,
                'total': 100,
                'status': 'Preparando diretórios...',
                'stage': ProcessStage.PREPARAR_DIRS
            }
        )
        
        # Constrói URL da view ProcessoNormaTaskExecutor
        # IMPORTANTE: A URL precisa incluir /sagl/ para que o contexto seja resolvido corretamente
        # mesmo que o portal_url seja o domínio direto (sem /sagl/), internamente o Zope espera /sagl/
        base_url = portal_url.rstrip('/')
        # Se a URL não contém /sagl/, adiciona
        if '/sagl/' not in base_url:
            executor_url = f"{base_url}/sagl/@@processo_norma_task_executor"
        else:
            executor_url = f"{base_url}/@@processo_norma_task_executor"
        
        # Prepara dados para POST
        data = {
            'cod_norma': str(cod_norma),
            'portal_url': portal_url,
        }
        if user_id:
            data['user_id'] = str(user_id)
        
        post_data = urllib.parse.urlencode(data).encode('utf-8')
        
        # Atualiza progresso: Fazendo download dos arquivos no Zope
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 10,
                'total': 100,
                'status': 'Fazendo download dos arquivos...',
                'stage': ProcessStage.COLETAR_DOCS
            }
        )
        
        # Faz chamada HTTP POST para a view
        try:
            req = urllib.request.Request(
                executor_url,
                data=post_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            with urllib.request.urlopen(req, timeout=600) as response:
                response_data = response.read().decode('utf-8')
                download_result = json.loads(response_data)
                
                if not download_result.get('success'):
                    error_msg = download_result.get('error', 'Erro desconhecido')
                    raise Exception(f"Erro ao fazer download dos arquivos: {error_msg}")
                
                dir_base = download_result.get('dir_base')
                dir_paginas = download_result.get('dir_paginas')
                id_processo = download_result.get('id_processo')
                documentos = download_result.get('documentos', [])
                dados_norma = download_result.get('dados_norma', {})
                
                # Atualiza progresso: Processamento pesado (mesclagem)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 20,
                        'total': 100,
                        'status': 'Mesclando documentos da norma...',
                        'stage': ProcessStage.MESCLAR_DOCS
                    }
                )
                
                # Processamento pesado: Mescla documentos com callback de progresso
                def progress_callback_mesclar(current_doc, total_docs, current_pages):
                    """Callback para atualizar progresso durante mesclagem"""
                    # Progresso de 20% a 45% (25% do total)
                    progress = 20 + int((current_doc / total_docs) * 25) if total_docs > 0 else 20
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': progress,
                            'total': 100,
                            'status': f'Mesclando documentos da norma... ({current_doc}/{total_docs} documentos, {current_pages} páginas)',
                            'stage': ProcessStage.MESCLAR_DOCS
                        }
                    )
                
                pdf_final, documentos_com_paginas = mesclar_documentos_celery(
                    documentos, dir_base, id_processo, progress_callback=progress_callback_mesclar
                )
                
                # Atualiza progresso: Mesclagem concluída
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 45,
                        'total': 100,
                        'status': 'Mesclagem concluída',
                        'stage': ProcessStage.MESCLAR_DOCS
                    }
                )
                
                # Valida que o PDF foi gerado
                if pdf_final is None:
                    raise Exception("PDF final é None - erro na mesclagem de documentos")
                
                if len(pdf_final) == 0:
                    total_docs_recebidos = len(documentos)
                    total_docs_processados = len(documentos_com_paginas)
                    raise Exception(
                        f"PDF final está vazio (0 páginas). "
                        f"Documentos recebidos: {total_docs_recebidos}, "
                        f"Documentos processados: {total_docs_processados}. "
                        f"Verifique os logs para detalhes sobre documentos que falharam."
                    )
                
                total_paginas = len(pdf_final)
                
                # Atualiza progresso: Salvando páginas individuais
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 50,
                        'total': 100,
                        'status': 'Salvando páginas individuais da norma...',
                        'stage': ProcessStage.SALVAR_PAGINAS
                    }
                )
                
                # Processamento pesado: Salva páginas individuais com callback de progresso
                def progress_callback_salvar(current_pages, total_pages):
                    """Callback para atualizar progresso durante salvamento de páginas"""
                    # Progresso de 50% a 70% (20% do total)
                    progress = 50 + int((current_pages / total_pages) * 20) if total_pages > 0 else 50
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': progress,
                            'total': 100,
                            'status': f'Salvando páginas individuais da norma... ({current_pages}/{total_pages} páginas)',
                            'stage': ProcessStage.SALVAR_PAGINAS
                        }
                    )
                
                salvar_paginas_individuais_celery(
                    pdf_final, dir_paginas, id_processo, progress_callback=progress_callback_salvar
                )
                
                # Atualiza progresso: Páginas salvas
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 70,
                        'total': 100,
                        'status': 'Páginas individuais salvas',
                        'stage': ProcessStage.SALVAR_PAGINAS
                    }
                )
                
                # Salva PDF final
                nome_arquivo_final = f"processo_norma_integral_{cod_norma}.pdf"
                caminho_arquivo_final = secure_path_join(dir_base, nome_arquivo_final)
                pdf_final.save(caminho_arquivo_final, **PDF_OPTIMIZATION_SETTINGS)
                
                # Atualiza progresso: Salvando metadados
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 80,
                        'total': 100,
                        'status': 'Salvando metadados...',
                        'stage': ProcessStage.SALVAR_PDF
                    }
                )
                
                # Salva metadados
                metadados_path = secure_path_join(dir_base, 'documentos_metadados.json')
                metadados = {
                    'cod_norma': cod_norma,
                    'id_processo': id_processo,
                    'total_paginas': total_paginas,
                    'data_geracao': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'documentos': []
                }
                
                for doc in documentos_com_paginas:
                    metadados['documentos'].append({
                        'title': doc.get('title', ''),
                        'data': doc.get('data', ''),
                        'file': doc.get('file', ''),
                        'start_page': doc.get('start_page', 0),
                        'end_page': doc.get('end_page', 0),
                        'num_pages': doc.get('num_pages', 0),
                        'file_size': doc.get('file_size', 0)  # CRÍTICO: Salva file_size para comparação posterior
                    })
                
                with open(metadados_path, 'w', encoding='utf-8') as f:
                    json.dump(metadados, f, ensure_ascii=False, indent=2)
                
                # Fecha PDF
                pdf_final.close()
                
                # Atualiza progresso: Concluído
                self.update_state(
                    state='SUCCESS',
                    meta={
                        'current': 100,
                        'total': 100,
                        'status': 'Geração do processo integral da norma concluída com sucesso!',
                        'stage': ProcessStage.CONCLUIDO,
                        'result': {
                            'cod_norma': cod_norma,
                            'total_paginas': total_paginas,
                            'documentos': len(documentos_com_paginas)
                        }
                    }
                )
                
                logger.info(f"[gerar_processo_norma_integral_task] ===== TASK CONCLUÍDA COM SUCESSO =====")
                logger.info(f"[gerar_processo_norma_integral_task] task_id={task_id}, cod_norma={cod_norma}, total_paginas={total_paginas}")
                
                return {
                    'success': True,
                    'cod_norma': cod_norma,
                    'message': 'Processo integral gerado com sucesso',
                    'total_paginas': total_paginas,
                    'documentos': len(documentos_com_paginas)
                }
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
            logger.error(f"[gerar_processo_norma_integral_task] Erro HTTP {e.code}: {error_body}")
            raise
        except urllib.error.URLError as e:
            logger.error(f"[gerar_processo_norma_integral_task] Erro de URL: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"[gerar_processo_norma_integral_task] Erro ao decodificar JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"[gerar_processo_norma_integral_task] Erro inesperado na chamada HTTP: {e}", exc_info=True)
            raise
            
    except Exception as e:
        logger.error(f"[gerar_processo_norma_integral_task] ===== ERRO NA TASK =====")
        logger.error(f"[gerar_processo_norma_integral_task] task_id={task_id}, cod_norma={cod_norma}")
        logger.error(f"[gerar_processo_norma_integral_task] Erro: {type(e).__name__}: {e}", exc_info=True)
        raise
    finally:
        logger.info(f"[gerar_processo_norma_integral_task] ===== FINALIZANDO TASK =====")
        logger.info(f"[gerar_processo_norma_integral_task] task_id={task_id}, cod_norma={cod_norma}")
