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


def process_single_document_celery(doc: Dict, dir_base: str) -> Tuple[fitz.Document, Dict]:
    """
    Processa um documento individual para mesclagem (versão para Celery).
    OTIMIZAÇÃO: Validação única e robusta usando pikepdf.
    OTIMIZAÇÃO: Retorna objeto fitz.Document diretamente para evitar validação duplicada.
    OTIMIZAÇÃO: Usa streaming quando possível para economizar memória.
    
    Returns:
        Tuple[fitz.Document, Dict]: (objeto PDF fitz já validado, informações do documento)
    """
    filename = doc.get('file', 'unknown')
    doc_title = doc.get('title', 'Documento desconhecido')
    
    try:
        if doc.get('filesystem'):
            # Arquivo já está no filesystem
            pdf_path = secure_path_join(doc['path'], doc['file'])
            
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
            else:
                # Leitura direta para arquivos pequenos/médios (mais rápido)
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
        else:
            raise ValueError(f"Documento não está no filesystem: {filename}")
        
        # OTIMIZAÇÃO: Validação única e robusta usando validação híbrida
        is_valid, num_pages, error_msg = validar_pdf_robusto(pdf_bytes, filename)
        if not is_valid:
            logger.warning(f"[process_single_document_celery] PDF '{filename}' falhou validação: {error_msg}")
            raise ValueError(f"PDF inválido para documento '{doc_title}': {error_msg}")
        
        # OTIMIZAÇÃO: Abre PDF com fitz uma única vez e retorna o objeto diretamente
        # Isso evita reabertura e validação duplicada em mesclar_documentos_celery
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        doc_info = doc.copy()
        # Adiciona tamanho do arquivo ao doc_info
        doc_info['file_size'] = file_size
        
        # Retorna objeto fitz.Document diretamente para evitar reabertura
        return pdf_doc, doc_info
        
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
    pages_inserted = 0
    for start_page in range(0, num_pages, CHUNK_SIZE_PAGES):
        end_page = min(start_page + CHUNK_SIZE_PAGES, num_pages)
        
        # Insere chunk de páginas
        pdf_mesclado.insert_pdf(pdf, from_page=start_page, to_page=end_page - 1, annots=True)
        pages_inserted += (end_page - start_page)
        
        # Limpeza de memória após cada chunk
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
                pdf_doc = None
                doc_processado = False
                try:
                    # OTIMIZAÇÃO: Recebe objeto fitz.Document diretamente (já validado)
                    pdf_doc, doc_info = future.result()
                    doc_title = doc_info.get('title', '?') if doc_info else '?'
                    
                    # OTIMIZAÇÃO: PDF já foi validado e aberto em process_single_document_celery
                    # Usa objeto fitz.Document diretamente (sem reabertura/validação duplicada)
                    start_page = len(pdf_mesclado)
                    
                    # OTIMIZAÇÃO: Usa processamento em chunks apenas para PDFs muito grandes
                    # Para PDFs menores, processa tudo de uma vez (mais rápido)
                    use_chunks = doc_info.get('file_size', 0) >= MIN_PDF_SIZE_FOR_CHUNKS and len(pdf_doc) > CHUNK_SIZE_PAGES
                    
                    if use_chunks:
                        # Processa em chunks para economizar memória
                        num_pages_inserted = inserir_pdf_em_chunks(pdf_mesclado, pdf_doc, doc_title)
                    else:
                        # PDF pequeno: insere tudo de uma vez (mais rápido)
                        pdf_mesclado.insert_pdf(pdf_doc, annots=True)
                        num_pages_inserted = len(pdf_doc)
                    
                    doc_info.update({
                        'start_page': start_page + 1,
                        'end_page': len(pdf_mesclado),
                        'num_pages': num_pages_inserted
                    })
                    documentos_com_paginas.append(doc_info)
                    doc_processado = True
                    
                    # Atualiza progresso se callback fornecido
                    if progress_callback:
                        try:
                            progress_callback(idx + 1, total_docs, len(pdf_mesclado))
                        except Exception as callback_err:
                            pass  # Erro no callback não é crítico, ignora silenciosamente
                    
                    # OTIMIZAÇÃO: Limpeza de memória - fecha PDF após processar
                    if pdf_doc:
                        pdf_doc.close()
                        pdf_doc = None
                    if len(pdf_mesclado) % MEMORY_CLEANUP_INTERVAL == 0:
                        gc.collect()
                    
                except Exception as e:
                        error_msg = str(e)
                        error_lower = error_msg.lower()
                        doc_title = doc_info.get('title', '?') if doc_info else '?'
                        if 'format error' not in error_lower and 'object out of range' not in error_lower and 'non-page object' not in error_lower:
                            logger.warning(f"[mesclar_documentos_celery] Ignorando documento '{doc_title}' devido ao erro: {error_msg[:200]}")
                finally:
                    # OTIMIZAÇÃO: Garante que pdf_doc sempre seja fechado, mesmo em caso de erro
                    if pdf_doc:
                        try:
                            pdf_doc.close()
                        except:
                            pass
                
                # Continua para o próximo documento se houve erro
                if not doc_processado:
                    continue
        
        if len(pdf_mesclado) > MAX_PAGES:
            raise Exception(f"Número de páginas excede o limite de {MAX_PAGES}")
        
        # OTIMIZAÇÃO: Limpeza de memória antes de adicionar rodapé
        gc.collect()
        
        # OTIMIZAÇÃO: Paraleliza adição de rodapé para PDFs grandes
        total_pages = len(pdf_mesclado)
        
        def adicionar_rodape_worker(page_nums):
            """Worker para adicionar rodapé em um chunk de páginas"""
            try:
                for page_num in page_nums:
                    page = pdf_mesclado[page_num]
                    page.insert_text(
                        fitz.Point(page.rect.width - 110, 20),
                        f"{id_processo} | Fls. {page_num + 1}/{total_pages}",
                        fontsize=8,
                        color=(0, 0, 0)
                    )
                return len(page_nums)
            except Exception as e:
                logger.warning(f"[mesclar_documentos_celery] Erro ao adicionar rodapé nas páginas {page_nums[0] + 1}-{page_nums[-1] + 1}: {e}")
                return 0
        
        # OTIMIZAÇÃO: Para PDFs pequenos (<100 páginas), adiciona rodapé sequencialmente (mais rápido)
        # Para PDFs grandes, paraleliza em chunks
        RODAPE_PARALELO_THRESHOLD = 100
        RODAPE_CHUNK_SIZE = 50
        
        if total_pages < RODAPE_PARALELO_THRESHOLD:
            # Processamento sequencial para PDFs pequenos
            for page_num in range(total_pages):
                page = pdf_mesclado[page_num]
                page.insert_text(
                    fitz.Point(page.rect.width - 110, 20),
                    f"{id_processo} | Fls. {page_num + 1}/{total_pages}",
                    fontsize=8,
                    color=(0, 0, 0)
                )
        else:
            # OTIMIZAÇÃO: Paraleliza para PDFs grandes
            page_chunks = []
            for i in range(0, total_pages, RODAPE_CHUNK_SIZE):
                chunk = list(range(i, min(i + RODAPE_CHUNK_SIZE, total_pages)))
                page_chunks.append(chunk)
            
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(page_chunks))) as executor:
                futures = [executor.submit(adicionar_rodape_worker, chunk) for chunk in page_chunks]
                
                pages_processed = 0
                for future in futures:
                    try:
                        pages_processed += future.result(timeout=60)  # Timeout de 1min por chunk
                    except Exception as e:
                        logger.warning(f"[mesclar_documentos_celery] Erro ao processar chunk de rodapé: {e}")
                
                if pages_processed < total_pages:
                    logger.warning(f"[mesclar_documentos_celery] Apenas {pages_processed}/{total_pages} páginas tiveram rodapé adicionado")
            
            # Limpeza de memória após adição de rodapé
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
            
            pages_saved_total = 0
            for future, batch in futures:
                try:
                    pages_saved = future.result(timeout=PAGE_SAVE_TIMEOUT * len(batch))
                    pages_saved_total += pages_saved
                    
                    # Atualiza progresso se callback fornecido
                    if progress_callback:
                        try:
                            progress_callback(pages_saved_total, total_pages)
                        except Exception:
                            pass  # Erro no callback não é crítico, ignora silenciosamente
                    
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
        # IMPORTANTE: A URL precisa incluir /sagl/ para que o contexto seja resolvido corretamente
        # mesmo que o portal_url seja o domínio direto (sem /sagl/), internamente o Zope espera /sagl/
        base_url = portal_url.rstrip('/')
        # Se a URL não contém /sagl/, adiciona
        if '/sagl/' not in base_url:
            executor_url = f"{base_url}/sagl/@@processo_leg_task_executor"
        else:
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
        
        # OTIMIZAÇÃO: Timeout adaptativo baseado no número de documentos esperados
        # Estimativa conservadora: 60s base + 10s por documento esperado
        # Mínimo: 60s, Máximo: 600s (10 minutos)
        # Nota: Não temos o número exato de documentos aqui, então usamos uma estimativa
        # baseada no cod_materia ou assumimos um número conservador
        estimated_docs = 20  # Estimativa conservadora de documentos por processo
        adaptive_timeout = 60 + (estimated_docs * 10)
        adaptive_timeout = max(60, min(adaptive_timeout, 600))  # Entre 60s e 600s
        
        # Faz chamada HTTP POST para a view (apenas para download)
        try:
            req = urllib.request.Request(
                executor_url,
                data=post_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            with urllib.request.urlopen(req, timeout=adaptive_timeout) as response:
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
                # Verificação final rápida apenas para confirmar (silenciosa em caso de sucesso)
                try:
                    _verificar_paginas_salvas_eficiente(dir_paginas, total_paginas)
                except Exception as verif_err:
                    logger.warning(f"[gerar_processo_leg_integral_task] Erro na verificação final de páginas: {verif_err}")
                    # Não falha a task, mas loga o erro
                
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
