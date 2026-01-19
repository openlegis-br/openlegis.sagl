# -*- coding: utf-8 -*-
"""Tarefa Celery para junção de PDFs (seguindo padrão do sistema)"""

import logging
import base64
import urllib.request
import urllib.parse
import urllib.error
import json
from io import BytesIO
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


@zope_task(bind=True, max_retries=3, default_retry_delay=30, name='tasks_folder.tramitacao_anexo_task.juntar_pdfs_task')
def juntar_pdfs_task(
    self,
    site,  # Injetado automaticamente pelo @zope_task
    tipo: str,
    cod_tramitacao: int,
    arquivo_pdf_base64: str,  # Base64 para serialização JSON
    nome_arquivo: str,
    portal_url: str,
    site_path: str = 'sagl',
    user_id: str = None
):
    """
    Tarefa Celery para juntar anexo ao PDF de tramitação.
    
    A task junta os PDFs diretamente usando PyMuPDF e o contexto Zope.
    
    Args:
        self: Instância da task (injetado pelo decorator)
        site: Objeto site do Zope (injetado pelo decorator @zope_task)
        tipo: 'MATERIA' ou 'DOCUMENTO'
        cod_tramitacao: Código da tramitação
        arquivo_pdf_base64: Conteúdo do PDF anexo em base64
        nome_arquivo: Nome original do arquivo
        portal_url: URL base do portal
        site_path: Caminho do site Zope (padrão: 'sagl')
        user_id: ID do usuário (opcional)
    
    Returns:
        dict com status e informações da junção
    """
    task_id = getattr(self.request, 'id', 'UNKNOWN')
    
    try:
        # Atualiza estado da tarefa
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'Iniciando junção de anexo...',
                'status_text': 'Iniciando junção de anexo...',
                'current': 10,
                'total': 100,
                'stage': 'init'
            }
        )
        
        # Converte base64 para BytesIO
        arquivo_pdf_bytes = base64.b64decode(arquivo_pdf_base64)
        arquivo_pdf = BytesIO(arquivo_pdf_bytes)
        
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'PROGRESS',
                'status_text': 'Aguardando PDF principal ser gerado...',
                'current': 20,
                'total': 100,
                'stage': 'aguardar_pdf_principal'
            }
        )
        
        # Aguarda um pouco antes de começar a tentar obter o PDF principal
        # Isso dá tempo para a task de geração do PDF começar e salvar o arquivo
        # Como as tasks podem executar em paralelo, aguardamos um tempo maior
        # para garantir que o PDF principal seja gerado primeiro
        import time
        logger.info(f"Task de junção aguardando 5 segundos antes de tentar obter PDF principal (cod_tramitacao={cod_tramitacao})")
        time.sleep(5)  # Aguarda 5 segundos antes de começar (aumentado de 3 para 5)
        
        # Constrói URL da view executor para obter PDF principal
        base_url = portal_url.rstrip('/')
        if '/sagl/' not in base_url:
            executor_url = f"{base_url}/sagl/@@tramitacao_anexo_task_executor"
        else:
            executor_url = f"{base_url}/@@tramitacao_anexo_task_executor"
        
        # Faz chamada HTTP POST para obter PDF principal
        data = {
            'tipo': str(tipo),
            'cod_tramitacao': str(cod_tramitacao),
        }
        post_data = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(executor_url, data=post_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        
        # Tenta obter PDF principal com retries (pode não estar pronto ainda)
        max_tentativas = 10  # Aumentado para 10 tentativas
        tentativa = 0
        pdf_principal_bytes = None
        
        while tentativa < max_tentativas and pdf_principal_bytes is None:
            try:
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': 'PROGRESS',
                        'status_text': f'Obtendo PDF principal... (tentativa {tentativa + 1}/{max_tentativas})',
                        'current': 30 + (tentativa * 3),
                        'total': 100,
                        'stage': 'obter_pdf_principal'
                    }
                )
                
                with urllib.request.urlopen(req, timeout=300) as response:
                    response_data = response.read().decode('utf-8')
                    result = json.loads(response_data)
                    
                    if not result.get('success'):
                        error_msg = result.get('error', 'Erro desconhecido')
                        # Se o erro é que o PDF não foi encontrado, tenta novamente
                        if 'não encontrado' in error_msg.lower() or 'not found' in error_msg.lower() or 'não tem PDF' in error_msg.lower():
                            if tentativa < max_tentativas - 1:
                                tentativa += 1
                                time.sleep(3)  # Aguarda 3 segundos antes de tentar novamente
                                logger.info(f"PDF principal não encontrado, tentativa {tentativa + 1}/{max_tentativas}")
                                continue
                        raise Exception(f"Erro ao obter PDF principal: {error_msg}")
                    
                    pdf_principal_base64 = result.get('pdf_base64')
                    if not pdf_principal_base64:
                        if tentativa < max_tentativas - 1:
                            tentativa += 1
                            time.sleep(3)  # Aguarda 3 segundos antes de tentar novamente
                            logger.info(f"PDF principal não encontrado no resultado, tentativa {tentativa + 1}/{max_tentativas}")
                            continue
                        raise Exception("PDF principal não encontrado no resultado após várias tentativas")
                    
                    pdf_principal_bytes = base64.b64decode(pdf_principal_base64)
                    
                    # Valida que o PDF não está vazio ou muito pequeno
                    # Um PDF de despacho completo geralmente tem pelo menos 10KB
                    # PDFs muito pequenos podem ser PDFs antigos ou incompletos
                    tamanho_minimo = 10 * 1024  # 10KB
                    if len(pdf_principal_bytes) < tamanho_minimo:
                        if tentativa < max_tentativas - 1:
                            tentativa += 1
                            time.sleep(3)  # Aguarda 3 segundos antes de tentar novamente
                            logger.warning(f"PDF principal muito pequeno ({len(pdf_principal_bytes)} bytes, mínimo esperado: {tamanho_minimo} bytes), tentativa {tentativa + 1}/{max_tentativas}")
                            pdf_principal_bytes = None  # Reseta para tentar novamente
                            continue
                        else:
                            logger.warning(f"PDF principal muito pequeno ({len(pdf_principal_bytes)} bytes), mas já foram feitas todas as tentativas. Continuando mesmo assim...")
                    
                    # Valida que é um PDF válido (deve começar com %PDF)
                    if not pdf_principal_bytes.startswith(b'%PDF'):
                        if tentativa < max_tentativas - 1:
                            tentativa += 1
                            time.sleep(3)  # Aguarda 3 segundos antes de tentar novamente
                            logger.warning(f"PDF principal não é um PDF válido, tentativa {tentativa + 1}/{max_tentativas}")
                            pdf_principal_bytes = None  # Reseta para tentar novamente
                            continue
                    
                    logger.info(f"PDF principal obtido com sucesso: {len(pdf_principal_bytes)} bytes")
                    break  # Sucesso, sai do loop
            except urllib.error.HTTPError as e:
                if e.code == 404 or e.code == 500:
                    if tentativa < max_tentativas - 1:
                        tentativa += 1
                        time.sleep(3)  # Aguarda 3 segundos antes de tentar novamente
                        logger.info(f"Erro HTTP {e.code} ao obter PDF principal, tentativa {tentativa + 1}/{max_tentativas}")
                        continue
                raise
            except Exception as e:
                if tentativa < max_tentativas - 1:
                    tentativa += 1
                    time.sleep(3)  # Aguarda 3 segundos antes de tentar novamente
                    logger.warning(f"Erro ao obter PDF principal: {e}, tentativa {tentativa + 1}/{max_tentativas}")
                    continue
                raise
        
        if pdf_principal_bytes is None:
            raise Exception(f"PDF principal não encontrado após {max_tentativas} tentativas")
        
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'PROGRESS',
                'status_text': 'Juntando PDFs...',
                'current': 60,
                'total': 100,
                'stage': 'juntando_pdf'
            }
        )
        
        # Junta PDFs (retorna bytes do PDF mesclado)
        pdf_mesclado_bytes = _juntar_pdfs_sem_sessao(tipo, cod_tramitacao, arquivo_pdf, pdf_principal_bytes)
        
        # Converte PDF mesclado para base64
        pdf_mesclado_base64 = base64.b64encode(pdf_mesclado_bytes).decode('utf-8')
        
        self.update_state(
            state='SUCCESS',
            meta={
                'status': 'SUCCESS',
                'status_text': 'Anexo juntado com sucesso',
                'current': 100,
                'total': 100,
                'stage': 'concluido',
                'pdf_base64': pdf_mesclado_base64,
                'tipo': tipo,
                'cod_tramitacao': cod_tramitacao
            }
        )
        
        return {
            'status': 'SUCCESS',
            'message': 'Anexo juntado com sucesso',
            'pdf_base64': pdf_mesclado_base64,
            'tipo': tipo,
            'cod_tramitacao': cod_tramitacao
        }
    
    except Exception as e:
        logger.error(f"Erro ao juntar anexo: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'FAILURE',
                'error': str(e),
                'status_text': 'Erro ao juntar anexo'
            }
        )
        raise
