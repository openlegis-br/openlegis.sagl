"""
Tarefa Celery assíncrona para geração de processo legislativo integral.

Esta tarefa processa a geração do PDF do processo integral de forma assíncrona,
permitindo que o usuário continue usando o sistema enquanto aguarda a conclusão.

FLUXO:
1. Task faz chamada HTTP para view ProcessoLegTaskExecutor no Zope
2. View faz download dos arquivos e retorna informações
3. Task faz processamento pesado (mesclagem, validação, salvamento)
"""
import logging
import os
import sys
import time
import json
import random
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
    logger.error(f"[processo_leg_task] ERRO ao importar bibliotecas de PDF: {e}", exc_info=True)
    raise

# Importa as dependências
try:
    from .utils import zope_task
except Exception as e:
    logger.error(f"[processo_leg_task] ERRO ao importar dependências: {e}", exc_info=True)
    raise

# Constantes (mesmas da view)
MAX_PAGES = 5000
MAX_WORKERS = 4
# OTIMIZAÇÃO: Tamanho do chunk para processamento de PDFs grandes (em páginas)
CHUNK_SIZE_PAGES = 200  # Processa 200 páginas por vez para PDFs grandes (aumentado de 50 para melhor performance)
# OTIMIZAÇÃO: Tamanho mínimo de PDF (em bytes) para usar processamento em chunks
MIN_PDF_SIZE_FOR_CHUNKS = 50 * 1024 * 1024  # 50 MB (aumentado de 10MB - arquivos menores são processados de uma vez)
# OTIMIZAÇÃO: Frequência de limpeza de memória (a cada N páginas)
MEMORY_CLEANUP_INTERVAL = 50  # Limpeza a cada 50 páginas (aumentado de 5 para melhor performance)
# OTIMIZAÇÃO: Tamanho do batch para salvamento de páginas
PAGE_SAVE_BATCH_SIZE = 50  # Salva 50 páginas por batch (aumentado de 15 para melhor performance)
# OTIMIZAÇÃO: Timeout por página (em segundos)
PAGE_SAVE_TIMEOUT = 5  # 5 segundos por página (reduzido de 10s - batches maiores são mais eficientes)
PDF_OPTIMIZATION_SETTINGS = {
    'garbage': 4,
    'deflate': True,
    'clean': True,
    'ascii': True,
}
# OTIMIZAÇÃO: Configurações mais leves para salvamento de páginas individuais (mais rápido)
PAGE_SAVE_OPTIMIZATION_SETTINGS = {
    'garbage': 2,  # Menos agressivo para melhor performance
    'deflate': True,
    'clean': False,  # Não limpa - já foi limpo durante mesclagem
    'ascii': False,  # Não converte para ASCII - mais rápido
}

# Estágios do processo (para padronização)
class ProcessStage:
    """Estágios padronizados do processo de geração"""
    INIT = 'init'
    DADOS_MATERIA = 'dados_materia'
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
    OTIMIZAÇÃO: Tenta fitz primeiro (mais rápido), usa pikepdf apenas se necessário.
    
    Returns:
        Tuple[bool, int, str]: (é_válido, num_páginas, mensagem_erro)
    """
    # OTIMIZAÇÃO: Tenta validação rápida com fitz primeiro
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            num_pages = len(pdf)
            if num_pages == 0:
                return False, 0, "PDF não tem páginas"
            # Se fitz validou com sucesso, retorna (mais rápido)
            return True, num_pages, ""
    except Exception as fitz_err:
        # Se fitz falhou, tenta pikepdf (mais rigoroso) para confirmar corrupção
        try:
            with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
                num_pages = len(pdf.pages)
                if num_pages == 0:
                    return False, 0, "PDF não tem páginas"
                if not pdf.Root:
                    return False, 0, "PDF não tem estrutura raiz válida"
                # pikepdf conseguiu abrir, então o PDF é válido (fitz pode ter tido problema temporário)
                return True, num_pages, ""
        except Exception as pikepdf_err:
            # Ambos falharam, PDF está corrompido
            error_msg = str(pikepdf_err).lower()
            if 'format error' in error_msg or 'object out of range' in error_msg or 'non-page object' in error_msg or 'invalid' in error_msg:
                return False, 0, f"PDF corrompido: {pikepdf_err}"
            return False, 0, f"Erro ao validar PDF: {pikepdf_err}"


def process_single_document_celery(doc: Dict, dir_base: str) -> Tuple[bytes, Dict]:
    """
    Processa um documento individual para mesclagem (versão para Celery).
    OTIMIZAÇÃO: Validação única e robusta usando pikepdf.
    OTIMIZAÇÃO: Usa streaming quando possível para economizar memória.
    """
    filename = doc.get('file', 'unknown')
    doc_title = doc.get('title', 'Documento desconhecido')
    
    try:
        if doc.get('filesystem'):
            # Arquivo já está no filesystem
            pdf_path = secure_path_join(doc['path'], doc['file'])
            logger.debug(f"[process_single_document_celery] Processando arquivo do filesystem: {pdf_path} (título: '{doc_title}')")
            
            # OTIMIZAÇÃO: Para arquivos muito grandes (>50MB), usa leitura em chunks (streaming)
            # Para arquivos menores, leitura direta é mais rápida
            file_size = os.path.getsize(pdf_path)
            STREAMING_THRESHOLD = 50 * 1024 * 1024  # 50 MB
            if file_size > STREAMING_THRESHOLD:
                # Streaming para arquivos muito grandes
                pdf_bytes = bytearray()
                with open(pdf_path, 'rb') as f:
                    while True:
                        chunk = f.read(1024 * 1024)  # Lê 1MB por vez
                        if not chunk:
                            break
                        pdf_bytes.extend(chunk)
                pdf_bytes = bytes(pdf_bytes)
                logger.debug(f"[process_single_document_celery] Arquivo muito grande lido via streaming: {len(pdf_bytes)} bytes")
            else:
                # Leitura direta para arquivos pequenos/médios (mais rápido)
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
                logger.debug(f"[process_single_document_celery] Arquivo do filesystem lido: {len(pdf_bytes)} bytes")
        else:
            raise ValueError(f"Documento não está no filesystem: {filename}")
        
        # OTIMIZAÇÃO: Validação única e robusta usando pikepdf
        is_valid, num_pages, error_msg = validar_pdf_robusto(pdf_bytes, filename)
        if not is_valid:
            logger.warning(f"[process_single_document_celery] PDF '{filename}' falhou validação: {error_msg}")
            raise ValueError(f"PDF inválido para documento '{doc_title}': {error_msg}")
        
        logger.debug(f"[process_single_document_celery] PDF '{filename}' validado: {num_pages} páginas")
        
        doc_info = doc.copy()
        # Adiciona tamanho do arquivo ao doc_info
        file_size = 0
        if doc.get('filesystem'):
            pdf_path = secure_path_join(doc['path'], doc['file'])
            file_size = os.path.getsize(pdf_path)
        # Sempre adiciona file_size ao doc_info, mesmo que seja 0 (garante que o campo existe)
        doc_info['file_size'] = file_size
        logger.debug(f"[process_single_document_celery] Retornando PDF '{filename}' com sucesso (título: '{doc_title}', tamanho: {file_size} bytes)")
        return pdf_bytes, doc_info
        
    except Exception as e:
        error_str = str(e).lower()
        if 'format error' in error_str or 'object out of range' in error_str or 'non-page object' in error_str or 'pdf inválido' in error_str:
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
                            
                            # Atualiza progresso se callback fornecido
                            if progress_callback:
                                try:
                                    progress_callback(idx + 1, total_docs, len(pdf_mesclado))
                                except Exception as callback_err:
                                    logger.debug(f"[mesclar_documentos_celery] Erro no callback de progresso: {callback_err}")
                            
                            # OTIMIZAÇÃO: Limpeza de memória mais frequente (a cada 5 páginas)
                            # Libera pdf_bytes da memória após processar
                            del pdf_bytes
                            if len(pdf_mesclado) % MEMORY_CLEANUP_INTERVAL == 0:
                                gc.collect()
                                logger.debug(f"[mesclar_documentos_celery] Limpeza de memória após {len(pdf_mesclado)} páginas")
                    except Exception as processing_err:
                        error_str = str(processing_err).lower()
                        doc_title = doc_info.get('title', '?') if doc_info else '?'
                        if 'format error' in error_str or 'object out of range' in error_str or 'non-page object' in error_str:
                            logger.warning(f"[mesclar_documentos_celery] PDF corrompido ignorado '{doc_title}': {processing_err}")
                        else:
                            logger.warning(f"[mesclar_documentos_celery] Erro ao processar PDF '{doc_title}': {processing_err}")
                        continue
                except Exception as e:
                    error_msg = str(e)
                    error_lower = error_msg.lower()
                    doc_title = doc_info.get('title', '?') if doc_info else '?'
                    if 'format error' in error_lower or 'object out of range' in error_lower or 'non-page object' in error_lower:
                        logger.debug(f"[mesclar_documentos_celery] Ignorando documento corrompido '{doc_title}': {error_msg[:100]}...")
                    else:
                        logger.warning(f"[mesclar_documentos_celery] Ignorando documento '{doc_title}' devido ao erro: {error_msg[:200]}")
                    continue
        
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


def _save_single_page_celery(pdf_final: fitz.Document, page_num: int, dir_paginas: str, id_processo: str) -> None:
    """
    Salva uma única página do PDF (versão para Celery).
    OTIMIZAÇÃO: Operação otimizada com configurações mais leves, mas mantém bake() para preservar informações.
    """
    nome_arquivo = f"pg_{page_num + 1:04d}.pdf"
    caminho_arquivo = secure_path_join(dir_paginas, nome_arquivo)
    
    try:
        with fitz.open() as pagina_pdf:
            pagina_pdf.insert_pdf(pdf_final, from_page=page_num, to_page=page_num, annots=True)
            pagina_pdf.set_metadata({
                "title": f"{id_processo} - Página {page_num + 1}",
                "creator": "Sistema de Processo Legislativo"
            })
            # CRÍTICO: bake() é necessário para preservar todas as informações (anotações, formatação, etc.)
            # Mantido para garantir integridade dos documentos
            pagina_pdf.bake()
            # Usa configurações mais leves para salvamento de páginas individuais (mais rápido que PDF_OPTIMIZATION_SETTINGS)
            pagina_pdf.save(caminho_arquivo, **PAGE_SAVE_OPTIMIZATION_SETTINGS)
    except Exception as e:
        logger.error(f"[_save_single_page_celery] Erro ao salvar página {page_num + 1}: {str(e)}")
        raise


def _save_pages_batch_celery(pdf_final: fitz.Document, page_nums: List[int], dir_paginas: str, id_processo: str) -> int:
    """
    Salva múltiplas páginas em batch (versão para Celery).
    OTIMIZAÇÃO: Salva páginas em batch para reduzir overhead de I/O.
    
    Returns:
        int: Número de páginas salvas com sucesso
    """
    pages_saved = 0
    for page_num in page_nums:
        try:
            _save_single_page_celery(pdf_final, page_num, dir_paginas, id_processo)
            pages_saved += 1
        except Exception as e:
            logger.warning(f"[_save_pages_batch_celery] Erro ao salvar página {page_num + 1} no batch: {str(e)}")
            # Continua salvando outras páginas do batch mesmo se uma falhar
            continue
    
    return pages_saved


def salvar_paginas_individuais_celery(pdf_final: fitz.Document, dir_paginas: str, id_processo: str, progress_callback=None) -> None:
    """
    Salva páginas individuais (versão para Celery).
    OTIMIZAÇÃO: Salva páginas em batches para reduzir overhead de I/O e timeout reduzido.
    
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
            
            # OTIMIZAÇÃO: Aguarda batches com timeout reduzido (10s por página)
            total_timeout = total_pages * PAGE_SAVE_TIMEOUT
            logger.debug(f"[salvar_paginas_individuais_celery] Timeout total: {total_timeout}s ({PAGE_SAVE_TIMEOUT}s por página)")
            
            pages_saved_total = 0
            for future, batch in futures:
                try:
                    pages_saved = future.result(timeout=PAGE_SAVE_TIMEOUT * len(batch))
                    pages_saved_total += pages_saved
                    
                    # Atualiza progresso se callback fornecido
                    if progress_callback:
                        try:
                            progress_callback(pages_saved_total, total_pages)
                        except Exception as callback_err:
                            logger.debug(f"[salvar_paginas_individuais_celery] Erro no callback de progresso: {callback_err}")
                    
                    if pages_saved < len(batch):
                        logger.warning(f"[salvar_paginas_individuais_celery] Batch incompleto: {pages_saved}/{len(batch)} páginas salvas")
                except Exception as e:
                    logger.error(f"[salvar_paginas_individuais_celery] Erro ao salvar batch de páginas {batch[0] + 1}-{batch[-1] + 1}: {str(e)}", exc_info=True)
                    raise
        
        # OTIMIZAÇÃO: Verificação eficiente de páginas salvas
        _verificar_paginas_salvas_eficiente(dir_paginas, total_pages)
        
        
    except Exception as e:
        logger.error(f"[salvar_paginas_individuais_celery] Erro ao salvar páginas individuais: {str(e)}", exc_info=True)
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
        
        # Verifica tamanho dos arquivos em batch (apenas uma amostra para performance)
        # Verifica apenas algumas páginas aleatórias ao invés de todas
        sample_size = min(10, total_pages)  # Verifica até 10 páginas aleatórias
        sample_pages = random.sample(range(1, total_pages + 1), sample_size)
        
        for page_num in sample_pages:
            pg_id = f"pg_{page_num:04d}.pdf"
            pg_path = os.path.join(dir_paginas, pg_id)
            if os.path.getsize(pg_path) == 0:
                raise Exception(f"Página está vazia: {pg_path}")
        
        logger.debug(f"[_verificar_paginas_salvas_eficiente] Verificação concluída: {total_pages} páginas, {sample_size} amostradas")
        
    except Exception as e:
        logger.error(f"[_verificar_paginas_salvas_eficiente] Erro na verificação: {str(e)}")
        raise


@zope_task(bind=True, max_retries=3, default_retry_delay=30, name='tasks_folder.processo_leg_task.gerar_processo_leg_integral_task')
def gerar_processo_leg_integral_task(self, site, cod_materia, portal_url, user_id=None):
    """
    Gera o processo legislativo integral de forma assíncrona.
    
    OPÇÃO 1 IMPLEMENTADA: Esta task faz uma chamada HTTP para a view ProcessoLegTaskExecutor
    no Zope que já está rodando, evitando acesso direto ao ZODB e eliminando problemas
    de corrupção de BTree.
    
    Args:
        site: Objeto site do Zope (injetado pelo decorator @zope_task, mas não usado)
        cod_materia: Código da matéria
        portal_url: URL base do portal (usado para construir URL da view)
        user_id: ID do usuário que solicitou (para notificação)
    
    Returns:
        dict: Resultado com informações do processo gerado
    """
    task_id = getattr(self.request, 'id', 'UNKNOWN')
    
    try:
        # Valida parâmetros obrigatórios
        if not cod_materia:
            raise ValueError("cod_materia é obrigatório")
        
        if not portal_url:
            raise ValueError("portal_url é obrigatório")
        
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
        
        # Atualiza progresso: Obtendo dados da matéria
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 100,
                'status': 'Obtendo dados da matéria...',
                'stage': ProcessStage.DADOS_MATERIA
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
        
        # Constrói URL da view ProcessoLegTaskExecutor
        # Remove barra final se houver
        base_url = portal_url.rstrip('/')
        executor_url = f"{base_url}/@@processo_leg_task_executor"
        
        
        # Prepara dados para POST
        data = {
            'cod_materia': str(cod_materia),
            'portal_url': portal_url,
        }
        if user_id:
            data['user_id'] = str(user_id)
        
        # Codifica dados para POST
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
                dir_base = download_result.get('dir_base')
                dir_paginas = download_result.get('dir_paginas')
                id_processo = download_result.get('id_processo')
                documentos = download_result.get('documentos', [])
                dados_materia = download_result.get('dados_materia', {})
                
                # Atualiza progresso: Processamento pesado (mesclagem)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 20,
                        'total': 100,
                        'status': 'Mesclando documentos...',
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
                            'status': f'Mesclando documentos... ({current_doc}/{total_docs} documentos, {current_pages} páginas)',
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
                if pdf_final is None or len(pdf_final) == 0:
                    raise Exception("PDF final não foi gerado ou está vazio")
                
                total_paginas = len(pdf_final)
                
                # Atualiza progresso: Salvando páginas individuais
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 50,
                        'total': 100,
                        'status': 'Salvando páginas individuais...',
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
                            'status': f'Salvando páginas individuais... ({current_pages}/{total_pages} páginas)',
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
                
                # Salva metadados
                metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                metadados = {
                    'cod_materia': cod_materia,
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
                        'file_size': doc.get('file_size', 0),
                        'start_page': doc.get('start_page', 1),
                        'end_page': doc.get('end_page', 1),
                        'num_pages': doc.get('num_pages', 1)
                    })
                
                with open(metadados_path, 'w', encoding='utf-8') as f:
                    json.dump(metadados, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                
                # Verifica se metadados foram salvos
                if not os.path.exists(metadados_path):
                    raise Exception(f"Falha ao salvar metadados: arquivo não existe após escrita: {metadados_path}")
                
                # Atualiza progresso: Salvando PDF final
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 75,
                        'total': 100,
                        'status': 'Salvando PDF final...',
                        'stage': ProcessStage.SALVAR_PDF
                    }
                )
                
                # Processamento pesado: Salva PDF final
                nome_arquivo_final = f"processo_leg_integral_{cod_materia}.pdf"
                caminho_arquivo_final = os.path.join(dir_base, nome_arquivo_final)
                
                if os.path.exists(caminho_arquivo_final):
                    try:
                        os.remove(caminho_arquivo_final)
                    except Exception:
                        pass
                
                pdf_final.save(caminho_arquivo_final, **PDF_OPTIMIZATION_SETTINGS)
                
                # Verifica se o PDF final foi salvo e não está vazio
                if not os.path.exists(caminho_arquivo_final):
                    raise Exception(f"Falha ao salvar PDF final: arquivo não existe após escrita: {caminho_arquivo_final}")
                
                pdf_final_size = os.path.getsize(caminho_arquivo_final)
                if pdf_final_size == 0:
                    raise Exception(f"PDF final está vazio: {caminho_arquivo_final}")
                
                # Arquivos coletados são mantidos para permitir comparação direta com metadados
                # Isso permite verificar se arquivos foram modificados comparando diretamente com os arquivos no diretório
                logger.debug(f"[gerar_processo_leg_integral_task] Arquivos coletados mantidos no diretório {dir_base} para comparação com metadados")
                
                # Atualiza progresso: PDF final salvo
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 90,
                        'total': 100,
                        'status': 'PDF final salvo, verificando integridade...',
                        'stage': ProcessStage.SALVAR_PDF
                    }
                )
                
                # CRÍTICO: Verificação final - garante que TODOS os arquivos existem antes de retornar SUCCESS
                # Verifica metadados (verificação final)
                if not os.path.exists(metadados_path):
                    raise Exception(f"Metadados não encontrados após verificação final: {metadados_path}")
                
                # OTIMIZAÇÃO: Verificação eficiente de páginas (já foi verificada em salvar_paginas_individuais_celery)
                # Verificação final rápida apenas para confirmar
                _verificar_paginas_salvas_eficiente(dir_paginas, total_paginas)
                
                # SOMENTE APÓS TODAS AS VERIFICAÇÕES: Atualiza progresso para SUCCESS
                self.update_state(
                    state='SUCCESS',
                    meta={
                        'current': 100,
                        'total': 100,
                        'status': 'Processo integral gerado com sucesso!',
                        'stage': ProcessStage.CONCLUIDO,
                        'arquivo': nome_arquivo_final,
                        'dir_base': dir_base
                    }
                )
                
                
                return {
                    'status': 'success',
                    'cod_materia': cod_materia,
                    'arquivo': nome_arquivo_final,
                    'dir_base': dir_base,
                    'task_id': task_id
                }
                    
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
            logger.error(f"[gerar_processo_leg_integral_task] Erro HTTP {e.code}: {error_body}")
            raise Exception(f"Erro HTTP {e.code} ao chamar view: {error_body}")
        except urllib.error.URLError as e:
            logger.error(f"[gerar_processo_leg_integral_task] Erro de URL: {e}")
            raise Exception(f"Erro ao conectar com Zope: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"[gerar_processo_leg_integral_task] Erro ao decodificar JSON: {e}")
            raise Exception(f"Resposta inválida do Zope: {e}")
        except Exception as e:
            logger.error(f"[gerar_processo_leg_integral_task] Erro inesperado na chamada HTTP: {e}", exc_info=True)
            raise
        
    except Exception as e:
        logger.error(f"[gerar_processo_leg_integral_task] Erro: {e}", exc_info=True)
        error_info = {
            'error': str(e),
            'error_type': type(e).__name__,
            'status': 'Erro durante a geração'
        }
        self.update_state(
            state='FAILURE',
            meta=error_info
        )
        
        # Tenta criar notificação de erro
        try:
            from .notificacao import notificar_processo_leg_erro
            notificar_processo_leg_erro(site, task_id, user_id, str(e))
        except Exception as notify_err:
            logger.debug(f"Erro ao notificar: {notify_err}")
        
        raise
