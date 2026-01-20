# -*- coding: utf-8 -*-
"""Tarefa Celery para geração de PDF em lote (seguindo padrão do sistema)"""

import logging
import urllib.request
import urllib.parse
import urllib.error
import json
from typing import List, Dict, Any
from io import BytesIO
from .utils import zope_task

logger = logging.getLogger(__name__)


@zope_task(bind=True, max_retries=3, default_retry_delay=30, name='tasks_folder.tramitacao_pdf_lote_task.gerar_pdf_despacho_lote_task')
def gerar_pdf_despacho_lote_task(
    self,
    site,  # Injetado automaticamente pelo @zope_task
    tipo: str,
    cod_tramitacoes: List[int],  # Lista de códigos de tramitação
    portal_url: str,
    site_path: str = 'sagl',
    user_id: str = None
):
    """
    Tarefa Celery para gerar PDF para múltiplas tramitações.
    
    Segue padrão de processo_adm: recebe dados via HTTP, gera PDFs e salva no repositório.
    
    Args:
        site: Objeto site do Zope (injetado pelo decorator @zope_task)
        tipo: 'MATERIA' ou 'DOCUMENTO'
        cod_tramitacoes: Lista de códigos de tramitação
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
        # Atualiza estado da tarefa
        self.update_state(
            state='PROGRESS',
            meta={
                'status': 'PROGRESS',
                'status_text': f'Iniciando geração de PDF para {total} tramitações...',
                'current': 0,
                'total': total,
                'processadas': 0,
                'sucesso': 0,
                'erro': 0,
                'stage': 'init'
            }
        )
        
        # Constrói URL da view TramitacaoPDFTaskExecutor
        base_url = portal_url.rstrip('/')
        if '/sagl/' not in base_url:
            executor_url = f"{base_url}/sagl/@@tramitacao_pdf_task_executor"
        else:
            executor_url = f"{base_url}/@@tramitacao_pdf_task_executor"
        
        # Importa generator (uma vez para todas)
        from openlegis.sagl.browser.tramitacao.pdf.generator import TramitacaoPDFGenerator
        generator = TramitacaoPDFGenerator(session=None, contexto_zope=site)
        
        # Processa cada tramitação
        for idx, cod_tramitacao in enumerate(cod_tramitacoes):
            try:
                # Atualiza progresso
                progress = int((idx / total) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': 'PROGRESS',
                        'status_text': f'Obtendo dados {idx + 1}/{total} (tramitação {cod_tramitacao})...',
                        'current': idx + 1,
                        'total': total,
                        'progress': progress,
                        'processadas': idx,
                        'sucesso': len([r for r in resultados if r.get('status') == 'SUCCESS']),
                        'erro': len([r for r in resultados if r.get('status') == 'ERROR']),
                        'tramitacao_atual': cod_tramitacao,
                        'stage': 'obter_dados'
                    }
                )
                
                # Prepara dados para POST
                data = {
                    'tipo': str(tipo),
                    'cod_tramitacao': str(cod_tramitacao),
                }
                
                # Codifica dados para POST
                post_data = urllib.parse.urlencode(data).encode('utf-8')
                
                # Faz chamada HTTP POST para obter dados preparados
                req = urllib.request.Request(
                    executor_url,
                    data=post_data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                
                with urllib.request.urlopen(req, timeout=300) as response:
                    response_data = response.read().decode('utf-8')
                    result = json.loads(response_data)
                    
                    if not result.get('success'):
                        error_msg = result.get('error', 'Erro desconhecido')
                        resultados.append({
                            'cod_tramitacao': cod_tramitacao,
                            'status': 'ERROR',
                            'message': error_msg,
                            'error': error_msg
                        })
                        continue
                    
                    # Extrai dados preparados
                    dados = result.get('dados', {})
                    
                    # Atualiza progresso
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'status': 'PROGRESS',
                            'status_text': f'Gerando PDF {idx + 1}/{total} (tramitação {cod_tramitacao})...',
                            'current': idx + 1,
                            'total': total,
                            'progress': progress,
                            'processadas': idx,
                            'sucesso': len([r for r in resultados if r.get('status') == 'SUCCESS']),
                            'erro': len([r for r in resultados if r.get('status') == 'ERROR']),
                            'tramitacao_atual': cod_tramitacao,
                            'stage': 'gerar_pdf'
                        }
                    )
                    
                    # Gera PDF usando dados recebidos
                    pdf_buffer = generator.gerar_pdf_com_dados(tipo, dados, contexto_zope=site)
                    pdf_bytes = pdf_buffer.getvalue()
                    
                    # Converte PDF para base64 para retornar na resposta
                    import base64
                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                    
                    pdf_filename = f"{cod_tramitacao}_tram.pdf"
                    
                    # ✅ Salva PDF no repositório via chamada HTTP (como na task individual)
                    try:
                        salvar_url = base_url.rstrip('/')
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
                            logger.info(f"[gerar_pdf_despacho_lote_task] PDF salvo no repositório via view HTTP (cod_tramitacao={cod_tramitacao})")
                    except Exception as e:
                        logger.error(f"[gerar_pdf_despacho_lote_task] Erro ao salvar PDF via view HTTP para tramitação {cod_tramitacao}: {e}", exc_info=True)
                        # Continua mesmo se houver erro ao salvar (PDF ainda está disponível em base64)
                    
                    resultados.append({
                        'cod_tramitacao': cod_tramitacao,
                        'status': 'SUCCESS',
                        'message': 'PDF gerado com sucesso',
                        'pdf_filename': pdf_filename,
                        'pdf_base64': pdf_base64,
                        'tipo': tipo
                    })
            
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
                logger.error(f"Erro HTTP {e.code} ao gerar PDF para tramitação {cod_tramitacao}: {error_body}")
                resultados.append({
                    'cod_tramitacao': cod_tramitacao,
                    'status': 'ERROR',
                    'message': f'Erro HTTP {e.code}',
                    'error': error_body
                })
            except urllib.error.URLError as e:
                logger.error(f"Erro de URL ao gerar PDF para tramitação {cod_tramitacao}: {e}")
                resultados.append({
                    'cod_tramitacao': cod_tramitacao,
                    'status': 'ERROR',
                    'message': f'Erro de conexão: {str(e)}',
                    'error': str(e)
                })
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar JSON para tramitação {cod_tramitacao}: {e}")
                resultados.append({
                    'cod_tramitacao': cod_tramitacao,
                    'status': 'ERROR',
                    'message': 'Resposta inválida do servidor',
                    'error': str(e)
                })
            except Exception as e:
                logger.error(f"Erro ao gerar PDF para tramitação {cod_tramitacao}: {e}", exc_info=True)
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
