# -*- coding: utf-8 -*-
"""Tarefa Celery para junção de PDFs em lote (seguindo padrão do sistema)"""

import logging
import base64
import urllib.request
import urllib.parse
import urllib.error
import json
from io import BytesIO
from typing import List, Dict, Any
from Acquisition import aq_inner, aq_base
from .utils import zope_task

logger = logging.getLogger(__name__)


def _resolver_site_real(contexto_zope):
    """
    Resolve o site real removendo wrappers (RequestContainer, etc).
    
    Args:
        contexto_zope: Contexto Zope que pode ser um wrapper
        
    Returns:
        Site real sem wrappers
    """
    site_real = contexto_zope
    try:
        if 'RequestContainer' in str(type(contexto_zope)):
            site_inner = aq_inner(contexto_zope)
            if 'RequestContainer' not in str(type(site_inner)):
                site_real = site_inner
            else:
                try:
                    site_base = aq_base(site_inner)
                    if 'RequestContainer' not in str(type(site_base)):
                        site_real = site_base
                except Exception:
                    pass
    except Exception:
        pass
    return site_real


def _juntar_pdfs_sem_sessao(tipo: str, cod_tramitacao: int, arquivo_pdf: BytesIO, pdf_principal_bytes: bytes):
    """
    Junta PDFs sem precisar de sessão SQLAlchemy (para uso em tasks Celery)
    
    Args:
        tipo: 'MATERIA' ou 'DOCUMENTO'
        cod_tramitacao: Código da tramitação
        arquivo_pdf: BytesIO com conteúdo do PDF anexo
        pdf_principal_bytes: Bytes do PDF principal
        
    Returns:
        bytes: PDF mesclado
    """
    import pymupdf
    
    # Valida que anexo é PDF
    arquivo_pdf.seek(0)
    try:
        pdf_doc = pymupdf.open(stream=arquivo_pdf)
        pdf_doc.close()
        arquivo_pdf.seek(0)
    except Exception as e:
        raise ValueError(f"Arquivo anexo não é um PDF válido: {e}")
    
    # Valida que principal é PDF
    try:
        pdf_principal_doc = pymupdf.open(stream=BytesIO(pdf_principal_bytes))
        pdf_principal_doc.close()
    except Exception as e:
        raise ValueError(f"PDF principal não é válido: {e}")
    
    # Junta PDFs usando PyMuPDF
    merger = pymupdf.open()
    try:
        # Adiciona PDF principal primeiro
        pdf_principal_doc = pymupdf.open(stream=BytesIO(pdf_principal_bytes))
        pdf_principal_doc.bake()
        merger.insert_pdf(pdf_principal_doc)
        pdf_principal_doc.close()
        
        # Adiciona PDF anexo
        arquivo_pdf.seek(0)
        pdf_anexo_doc = pymupdf.open(stream=arquivo_pdf)
        pdf_anexo_doc.bake()
        merger.insert_pdf(pdf_anexo_doc)
        pdf_anexo_doc.close()
        
        # Gera PDF mesclado
        output_stream = BytesIO()
        merger.save(output_stream)
        output_stream.seek(0)
        pdf_mesclado_bytes = output_stream.getvalue()
        
        return pdf_mesclado_bytes
        
    finally:
        merger.close()


@zope_task(bind=True, max_retries=3, default_retry_delay=30, name='tasks_folder.tramitacao_anexo_lote_task.juntar_pdfs_lote_task')
def juntar_pdfs_lote_task(
    self,
    site,  # Injetado automaticamente pelo @zope_task
    tipo: str,
    cod_tramitacoes: List[int],  # Lista de códigos de tramitação
    arquivo_pdf_base64: str,  # Base64 para serialização JSON (mesmo anexo para todos)
    nome_arquivo: str,
    portal_url: str,
    site_path: str = 'sagl',
    user_id: str = None
):
    """
    Tarefa Celery para juntar o mesmo anexo em múltiplas tramitações.
    
    A task junta os PDFs diretamente usando PyMuPDF e o contexto Zope.
    
    Args:
        site: Objeto site do Zope (injetado pelo decorator @zope_task)
        tipo: 'MATERIA' ou 'DOCUMENTO'
        cod_tramitacoes: Lista de códigos de tramitação
        arquivo_pdf_base64: Conteúdo do PDF anexo em base64 (mesmo para todos)
        nome_arquivo: Nome original do arquivo
        portal_url: URL base do portal
        site_path: Caminho do site Zope (padrão: 'sagl')
        user_id: ID do usuário (opcional)
    
    Returns:
        dict com status e resultados de cada tramitação
    """
    task_id = getattr(self.request, 'id', 'UNKNOWN')
    total = len(cod_tramitacoes)
    resultados = []
    
    try:
        # Converte base64 para BytesIO (uma vez para todos)
        arquivo_pdf_bytes = base64.b64decode(arquivo_pdf_base64)
        arquivo_pdf = BytesIO(arquivo_pdf_bytes)
        
        # Atualiza estado da tarefa
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'PROGRESS',
                'status_text': f'Iniciando junção de anexo em {total} tramitações...',
                'current': 0,
                'total': total,
                'progress': 0,
                'processadas': 0,
                'sucesso': 0,
                'erro': 0,
                'stage': 'init'
            }
        )
        
        # Processa cada tramitação
        for idx, cod_tramitacao in enumerate(cod_tramitacoes):
            try:
                # Atualiza progresso
                progress = int((idx / total) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': 'PROGRESS',
                        'status_text': f'Juntando anexo {idx + 1}/{total} (tramitação {cod_tramitacao})...',
                        'current': idx + 1,
                        'total': total,
                        'progress': progress,
                        'processadas': idx,
                        'sucesso': len([r for r in resultados if r.get('status') == 'SUCCESS']),
                        'erro': len([r for r in resultados if r.get('status') == 'ERROR']),
                        'tramitacao_atual': cod_tramitacao,
                        'stage': 'juntando_pdf'
                    }
                )
                
                # Constrói URL da view executor para obter PDF principal
                base_url = portal_url.rstrip('/')
                if '/sagl/' not in base_url:
                    executor_url = f"{base_url}/sagl/@@tramitacao_anexo_task_executor"
                else:
                    executor_url = f"{base_url}/@@tramitacao_anexo_task_executor"
                
                # Faz chamada HTTP POST para obter PDF principal
                data_check = {'tipo': str(tipo), 'cod_tramitacao': str(cod_tramitacao)}
                post_data_check = urllib.parse.urlencode(data_check).encode('utf-8')
                req_check = urllib.request.Request(executor_url, data=post_data_check, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                
                with urllib.request.urlopen(req_check, timeout=300) as response_check:
                    result_check = json.loads(response_check.read().decode('utf-8'))
                    if not result_check.get('success'):
                        error_msg = result_check.get('error', 'Erro desconhecido')
                        raise Exception(f"Erro ao obter PDF principal: {error_msg}")
                    
                    pdf_principal_base64 = result_check.get('pdf_base64')
                    if not pdf_principal_base64:
                        raise Exception("PDF principal não encontrado no resultado")
                    
                    pdf_principal_bytes = base64.b64decode(pdf_principal_base64)
                
                # Reseta BytesIO para cada tramitação (reutiliza o mesmo arquivo)
                arquivo_pdf.seek(0)
                
                # Junta PDFs (retorna bytes do PDF mesclado)
                pdf_mesclado_bytes = _juntar_pdfs_sem_sessao(tipo, cod_tramitacao, arquivo_pdf, pdf_principal_bytes)
                
                # Converte PDF mesclado para base64
                pdf_mesclado_base64 = base64.b64encode(pdf_mesclado_bytes).decode('utf-8')
                
                resultados.append({
                    'cod_tramitacao': cod_tramitacao,
                    'status': 'SUCCESS',
                    'message': 'Anexo juntado com sucesso',
                    'pdf_base64': pdf_mesclado_base64,
                    'tipo': tipo
                })
            
            except Exception as e:
                logger.error(f"Erro ao juntar anexo para tramitação {cod_tramitacao}: {e}", exc_info=True)
                resultados.append({
                    'cod_tramitacao': cod_tramitacao,
                    'status': 'ERROR',
                    'message': str(e),
                    'error': str(e)
                })
        
        sucesso = len([r for r in resultados if r.get('status') == 'SUCCESS'])
        erro = len([r for r in resultados if r.get('status') == 'ERROR'])
        
        self.update_state(
            state='SUCCESS',
            meta={
                'status': 'SUCCESS',
                'status_text': f'Concluído: {sucesso} sucesso, {erro} erro(s)',
                'current': total,
                'total': total,
                'progress': 100,
                'processadas': total,
                'sucesso': sucesso,
                'erro': erro,
                'resultados': resultados,
                'stage': 'concluido'
            }
        )
        
        return {
            'status': 'SUCCESS',
            'message': f'Processamento concluído: {sucesso} sucesso, {erro} erro(s)',
            'total': total,
            'sucesso': sucesso,
            'erro': erro,
            'resultados': resultados
        }
    
    except Exception as e:
        logger.error(f"Erro ao processar lote: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'FAILURE',
                'error': str(e),
                'status_text': 'Erro ao processar lote',
                'resultados': resultados
            }
        )
        raise
