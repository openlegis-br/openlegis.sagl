# -*- coding: utf-8 -*-
"""Tarefa Celery para geração de PDF de despachos (seguindo padrão do sistema)"""

import logging
import urllib.request
import urllib.parse
import urllib.error
import json
from io import BytesIO
from .utils import zope_task

logger = logging.getLogger(__name__)


def _juntar_pdfs_sem_sessao(tipo: str, cod_tramitacao: int, arquivo_pdf: BytesIO, nome_arquivo: str, contexto_zope):
    """
    Junta PDFs sem precisar de sessão SQLAlchemy (para uso em tasks Celery)
    
    Args:
        tipo: 'MATERIA' ou 'DOCUMENTO'
        cod_tramitacao: Código da tramitação
        arquivo_pdf: BytesIO com conteúdo do PDF anexo
        nome_arquivo: Nome original do arquivo
        contexto_zope: Contexto Zope para acessar repositório
    """
    import pymupdf
    
    if not contexto_zope:
        raise ValueError("Contexto Zope necessário para salvar arquivos")
    
    # Valida que é PDF
    arquivo_pdf.seek(0)
    try:
        pdf_doc = pymupdf.open(stream=arquivo_pdf)
        pdf_doc.close()
        arquivo_pdf.seek(0)
    except Exception as e:
        raise ValueError(f"Arquivo não é um PDF válido: {e}")
    
    # Nome do arquivo anexo (temporário)
    anexo_filename = f"{cod_tramitacao}_tram_anexo1.pdf"
    base_filename = f"{cod_tramitacao}_tram.pdf"
    
    # Repositório
    if tipo == 'MATERIA':
        repo = contexto_zope.sapl_documentos.materia.tramitacao
    else:
        repo = contexto_zope.sapl_documentos.administrativo.tramitacao
    
    # Verifica se PDF principal existe
    if not hasattr(repo, base_filename):
        raise ValueError(f"PDF principal {base_filename} não encontrado")
    
    # Remove anexo anterior se existir
    if hasattr(repo, anexo_filename):
        repo.manage_delObjects([anexo_filename])
    
    # Salva anexo temporário
    arquivo_pdf.seek(0)
    repo.manage_addFile(
        id=anexo_filename,
        file=arquivo_pdf.read(),
        content_type='application/pdf',
        title=f'Anexo da tramitação {cod_tramitacao}'
    )
    
    # Junta PDFs usando PyMuPDF
    merger = pymupdf.open()
    try:
        # Lista de arquivos para juntar (principal primeiro, depois anexo)
        filenames = [base_filename, anexo_filename]
        
        for filename in filenames:
            if not hasattr(repo, filename):
                logger.warning(f"Arquivo {filename} não encontrado, pulando...")
                continue
            
            # Obtém arquivo do repositório
            arq = getattr(repo, filename)
            if not hasattr(arq, 'data'):
                logger.warning(f"Arquivo {filename} não possui atributo 'data', pulando...")
                continue
            
            # Converte para BytesIO
            arquivo = BytesIO(bytes(arq.data))
            arquivo.seek(0)
            
            # Abre PDF com PyMuPDF
            pdf_doc = pymupdf.open(stream=arquivo)
            pdf_doc.bake()
            merger.insert_pdf(pdf_doc)
            pdf_doc.close()
        
        # Salva PDF mesclado
        output_stream = BytesIO()
        merger.save(output_stream)
        output_stream.seek(0)
        content = output_stream.getvalue()
        
        # Atualiza arquivo principal no repositório
        pdf_principal = getattr(repo, base_filename)
        pdf_principal.update_data(content)
        logger.info(f"PDF mesclado atualizado: {base_filename}")
        
    finally:
        merger.close()
        
        # Remove anexo temporário após junção bem-sucedida
        try:
            if hasattr(repo, anexo_filename):
                repo.manage_delObjects([anexo_filename])
        except Exception as e:
            logger.warning(f"Falha ao remover anexo temporário: {e}")


@zope_task(bind=True, max_retries=3, default_retry_delay=30, name='tasks_folder.tramitacao_pdf_task.gerar_pdf_despacho_task')
def gerar_pdf_despacho_task(
    self,
    site,  # Injetado automaticamente pelo @zope_task
    tipo: str,
    cod_tramitacao: int,
    portal_url: str,
    site_path: str = 'sagl',
    user_id: str = None,
    dados_tramitacao_json: str = None  # ✅ Dados do request em JSON (opcional)
):
    """
    Tarefa Celery para gerar PDF do despacho de tramitação.
    
    Segue padrão de processo_adm: recebe dados via HTTP, gera PDF e salva no repositório.
    
    Args:
        self: Instância da task (injetado pelo decorator)
        site: Objeto site do Zope (injetado pelo decorator @zope_task)
        tipo: 'MATERIA' ou 'DOCUMENTO'
        cod_tramitacao: Código da tramitação
        portal_url: URL base do portal
        site_path: Caminho do site Zope (padrão: 'sagl')
        user_id: ID do usuário (opcional)
    
    Returns:
        dict com status e informações do PDF gerado
    """
    task_id = getattr(self.request, 'id', 'UNKNOWN')
    
    try:
        # Atualiza estado da tarefa
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'Iniciando geração de PDF...',
                'status_text': 'Iniciando geração de PDF...',
                'current': 10,
                'total': 100,
                'stage': 'init'
            }
        )
        
        # Constrói URL da view TramitacaoPDFTaskExecutor
        base_url = portal_url.rstrip('/')
        if '/sagl/' not in base_url:
            executor_url = f"{base_url}/sagl/@@tramitacao_pdf_task_executor"
        else:
            executor_url = f"{base_url}/@@tramitacao_pdf_task_executor"
        
        # Prepara dados para POST
        data = {
            'tipo': str(tipo),
            'cod_tramitacao': str(cod_tramitacao),
        }
        
        # ✅ Se dados_tramitacao_json foi fornecido, passa diretamente (dados do request)
        # Isso garante que o PDF seja gerado com os dados atualizados, não do banco
        if dados_tramitacao_json:
            data['dados_tramitacao_json'] = dados_tramitacao_json
            logger.info(f"[gerar_pdf_despacho_task] Usando dados do request para gerar PDF (cod_tramitacao={cod_tramitacao})")
        
        # Codifica dados para POST
        post_data = urllib.parse.urlencode(data).encode('utf-8')
        
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'PROGRESS',
                'status_text': 'Obtendo dados da tramitação...',
                'current': 20,
                'total': 100,
                'stage': 'obter_dados'
            }
        )
        
        # Faz chamada HTTP POST para obter dados preparados
        try:
            req = urllib.request.Request(
                executor_url,
                data=post_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            with urllib.request.urlopen(req, timeout=300) as response:
                response_data = response.read().decode('utf-8')
                
                # Log para debug se resposta estiver vazia ou inválida
                if not response_data or not response_data.strip():
                    logger.error(f"[gerar_pdf_despacho_task] Resposta vazia do executor. Status: {response.status}, URL: {executor_url}")
                    raise Exception("Resposta vazia do servidor executor")
                
                # Tenta parsear JSON
                try:
                    result = json.loads(response_data)
                except json.JSONDecodeError as e:
                    logger.error(f"[gerar_pdf_despacho_task] Resposta não é JSON válido. Primeiros 500 chars: {response_data[:500]}")
                    raise
                
                if not result.get('success'):
                    error_msg = result.get('error', 'Erro desconhecido')
                    raise Exception(f"Erro ao obter dados: {error_msg}")
                
                # Extrai dados preparados
                dados = result.get('dados', {})
                
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': 'PROGRESS',
                        'status_text': 'Gerando PDF...',
                        'current': 50,
                        'total': 100,
                        'stage': 'gerar_pdf'
                    }
                )
                
                # Gera PDF usando dados recebidos (sem precisar de sessão)
                from openlegis.sagl.browser.tramitacao.pdf.generator import TramitacaoPDFGenerator
                
                # Cria generator sem sessão (apenas para usar métodos de geração)
                generator = TramitacaoPDFGenerator(session=None, contexto_zope=site)
                
                # Gera PDF com dados recebidos
                pdf_buffer = generator.gerar_pdf_com_dados(tipo, dados, contexto_zope=site)
                pdf_bytes = pdf_buffer.getvalue()
                
                # Converte PDF para base64 para retornar na resposta
                import base64
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                
                # ✅ Salva PDF via chamada HTTP para a view de salvamento (view tem contexto Zope correto)
                try:
                    salvar_url = portal_url.rstrip('/')
                    if '/sagl/' not in salvar_url:
                        salvar_url = f"{salvar_url}/sagl/@@tramitacao_salvar_pdf"
                    else:
                        salvar_url = f"{salvar_url}/@@tramitacao_salvar_pdf"
                    
                    # Chama view para salvar PDF
                    save_data = urllib.parse.urlencode({
                        'tipo': str(tipo),
                        'cod_tramitacao': str(cod_tramitacao),
                        'pdf_base64': pdf_base64
                    }).encode('utf-8')
                    
                    save_req = urllib.request.Request(
                        salvar_url,
                        data=save_data,
                        headers={'Content-Type': 'application/x-www-form-urlencoded'}
                    )
                    
                    with urllib.request.urlopen(save_req, timeout=60) as save_response:
                        save_result = save_response.read().decode('utf-8')
                        logger.info(f"[gerar_pdf_despacho_task] PDF salvo no repositório via view HTTP (cod_tramitacao={cod_tramitacao})")
                except Exception as e:
                    logger.error(f"[gerar_pdf_despacho_task] Erro ao salvar PDF via view HTTP: {e}", exc_info=True)
                    # Continua mesmo se houver erro ao salvar (PDF ainda está disponível em base64)
                
                pdf_filename = f"{cod_tramitacao}_tram.pdf"
                
                self.update_state(
                    state='SUCCESS',
                    meta={
                        'status': 'SUCCESS',
                        'status_text': 'PDF gerado com sucesso',
                        'current': 100,
                        'total': 100,
                        'stage': 'concluido',
                        'pdf_base64': pdf_base64,
                        'pdf_filename': pdf_filename,
                        'tipo': tipo,
                        'cod_tramitacao': cod_tramitacao
                    }
                )
                
                return {
                    'status': 'SUCCESS',
                    'message': 'PDF gerado com sucesso',
                    'pdf_filename': pdf_filename,
                    'pdf_base64': pdf_base64,
                    'cod_tramitacao': cod_tramitacao,
                    'tipo': tipo
                }
        
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
            logger.error(f"[gerar_pdf_despacho_task] Erro HTTP {e.code}: {error_body}")
            raise Exception(f"Erro HTTP {e.code} ao obter dados: {error_body}")
        except urllib.error.URLError as e:
            logger.error(f"[gerar_pdf_despacho_task] Erro de URL: {e}")
            raise Exception(f"Erro de conexão ao obter dados: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"[gerar_pdf_despacho_task] Erro ao decodificar JSON: {e}")
            raise Exception(f"Resposta inválida do servidor: {str(e)}")
        except Exception as e:
            logger.error(f"[gerar_pdf_despacho_task] Erro inesperado: {e}", exc_info=True)
            raise
    
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'FAILURE',
                'error': str(e),
                'status_text': 'Erro ao gerar PDF'
            }
        )
        raise
