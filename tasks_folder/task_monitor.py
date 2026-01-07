"""
Utilitários para monitorar tarefas Celery no Zope.

Este módulo fornece funções para verificar o status, resultado e progresso
de tarefas Celery executadas de forma assíncrona.
"""
from celery.result import AsyncResult
from tasks import celery
import logging
import json
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def get_task_status(task_id):
    """
    Obtém o status atual de uma tarefa Celery.
    
    Args:
        task_id (str): ID da tarefa retornado por apply_async() ou delay()
    
    Returns:
        dict: Dicionário com informações sobre o status da tarefa:
            - status: Estado da tarefa (PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED)
            - ready: Se a tarefa foi concluída (sucesso ou falha)
            - result: Resultado da tarefa (se concluída com sucesso)
            - error: Mensagem de erro (se falhou)
            - traceback: Stack trace (se falhou)
            - task_id: ID da tarefa
            - date_done: Data/hora de conclusão (se concluída)
    """
    if not task_id:
        return {
            'status': 'INVALID',
            'ready': False,
            'error': 'Task ID não fornecido',
            'task_id': None
        }
    
    try:
        result = AsyncResult(task_id, app=celery)
        
        response = {
            'task_id': task_id,
            'status': result.state,
            'ready': result.ready(),
        }
        
        if result.ready():
            if result.successful():
                response['result'] = result.result
                response['date_done'] = datetime.now().isoformat()
            else:
                # Tarefa falhou - trata exceções mal serializadas
                try:
                    # Tenta obter informações do resultado
                    if result.info:
                        if isinstance(result.info, dict):
                            response['error'] = result.info.get('error', str(result.info))
                            if 'traceback' in result.info:
                                response['traceback'] = result.info['traceback']
                        else:
                            response['error'] = str(result.info)
                    else:
                        response['error'] = 'Erro desconhecido'
                    
                    # Tenta obter traceback se disponível
                    if hasattr(result, 'traceback') and result.traceback:
                        response['traceback'] = result.traceback
                        
                except ValueError as ve:
                    # Erro ao decodificar exceção (exceção mal serializada)
                    logger.warning(f"Erro ao decodificar exceção da tarefa {task_id}: {ve}")
                    response['error'] = 'Erro ao processar resultado da tarefa (exceção mal serializada)'
                    response['error_detail'] = str(ve)
                except Exception as decode_error:
                    # Outro erro ao decodificar
                    logger.warning(f"Erro ao decodificar resultado da tarefa {task_id}: {decode_error}")
                    response['error'] = f'Erro ao processar resultado: {str(decode_error)}'
                
                response['date_done'] = datetime.now().isoformat()
        else:
            # Tarefa ainda em execução
            if result.state == 'PENDING':
                response['message'] = 'Tarefa aguardando execução'
            elif result.state == 'STARTED' or result.state == 'PROGRESS':
                response['message'] = 'Tarefa em execução'
                # Tenta obter informações de progresso
                try:
                    if result.info and isinstance(result.info, dict):
                        # Atualiza response com informações de progresso (current, total, status, stage)
                        # Nota: Se result.info tem 'status', ele sobrescreve o status do estado
                        # mas isso é intencional - o status no meta é a mensagem de status
                        response.update(result.info)
                    else:
                        # Se não tem info, tenta obter do backend
                        try:
                            if hasattr(result, 'backend') and result.backend:
                                meta = result.backend.get_task_meta(task_id)
                                if meta and 'result' in meta:
                                    meta_result = meta['result']
                                    if isinstance(meta_result, dict):
                                        response.update(meta_result)
                                        logger.debug(f"[get_task_status] Progresso obtido do backend para {task_id}: {meta_result}")
                        except Exception as backend_err:
                            logger.debug(f"[get_task_status] Erro ao obter progresso do backend: {backend_err}")
                except (ValueError, Exception) as e:
                    # Ignora erros ao decodificar progresso
                    logger.debug(f"Erro ao obter progresso da tarefa {task_id}: {e}")
            elif result.state == 'RETRY':
                response['message'] = 'Tarefa sendo reexecutada após falha'
                try:
                    if result.info:
                        response['retry_info'] = str(result.info)
                except (ValueError, Exception) as e:
                    logger.debug(f"Erro ao obter info de retry da tarefa {task_id}: {e}")
        
        return response
        
    except ValueError as ve:
        # Erro específico de decodificação de exceção
        logger.error(f"Erro de decodificação ao obter status da tarefa {task_id}: {ve}", exc_info=True)
        return {
            'status': 'ERROR',
            'ready': False,
            'error': f'Erro ao decodificar resultado da tarefa: {str(ve)}',
            'error_type': 'DECODE_ERROR',
            'task_id': task_id
        }
    except Exception as e:
        logger.error(f"Erro ao obter status da tarefa {task_id}: {e}", exc_info=True)
        return {
            'status': 'ERROR',
            'ready': False,
            'error': f'Erro ao consultar tarefa: {str(e)}',
            'task_id': task_id
        }


def wait_for_task(task_id, timeout=None, interval=1):
    """
    Aguarda a conclusão de uma tarefa (bloqueante).
    
    Args:
        task_id (str): ID da tarefa
        timeout (int, optional): Tempo máximo de espera em segundos. None = sem timeout
        interval (float): Intervalo entre verificações em segundos
    
    Returns:
        dict: Resultado da tarefa (mesmo formato de get_task_status)
    
    Raises:
        TimeoutError: Se o timeout for excedido
    """
    result = AsyncResult(task_id, app=celery)
    start_time = time.time()
    
    while not result.ready():
        if timeout and (time.time() - start_time) > timeout:
            raise TimeoutError(f"Timeout aguardando tarefa {task_id}")
        time.sleep(interval)
    
    return get_task_status(task_id)


def get_task_result(task_id):
    """
    Obtém o resultado de uma tarefa concluída.
    
    Args:
        task_id (str): ID da tarefa
    
    Returns:
        O resultado da tarefa, ou None se ainda não concluída ou falhou
    
    Raises:
        Exception: Se a tarefa falhou, levanta a exceção original
    """
    result = AsyncResult(task_id, app=celery)
    
    if not result.ready():
        return None
    
    if result.successful():
        return result.result
    else:
        # Re-levanta a exceção original
        raise result.result if isinstance(result.result, Exception) else Exception(str(result.info))


def revoke_task(task_id, terminate=False):
    """
    Cancela uma tarefa.
    
    Args:
        task_id (str): ID da tarefa
        terminate (bool): Se True, força a terminação imediata do worker
    
    Returns:
        bool: True se a tarefa foi cancelada com sucesso
    """
    try:
        celery.control.revoke(task_id, terminate=terminate)
        return True
    except Exception as e:
        logger.error(f"Erro ao cancelar tarefa {task_id}: {e}", exc_info=True)
        return False


def get_task_info(task_id):
    """
    Obtém informações detalhadas sobre uma tarefa.
    
    Args:
        task_id (str): ID da tarefa
    
    Returns:
        dict: Informações detalhadas incluindo metadados
    """
    result = AsyncResult(task_id, app=celery)
    
    info = get_task_status(task_id)
    
    # Adiciona informações adicionais se disponíveis
    if hasattr(result, 'backend') and result.backend:
        try:
            meta = result.backend.get_task_meta(task_id)
            if meta:
                info['meta'] = {
                    'task_name': meta.get('task_name'),
                    'worker': meta.get('worker'),
                    'date_created': meta.get('date_created'),
                    'date_started': meta.get('date_started'),
                }
        except Exception as e:
            logger.debug(f"Não foi possível obter metadados da tarefa: {e}")
    
    return info


def list_pending_and_failed_tasks():
    """
    Lista todas as tarefas pendentes e com erro no Celery.
    
    Returns:
        dict: Dicionário com:
            - pending: Lista de tarefas pendentes (active, reserved, scheduled)
            - failed: Lista de tarefas com erro (FAILURE)
            - summary: Resumo com contadores
    """
    result = {
        'pending': [],
        'failed': [],
        'summary': {
            'active': 0,
            'reserved': 0,
            'scheduled': 0,
            'failed': 0,
            'total_pending': 0,
            'total_failed': 0
        }
    }
    
    try:
        inspect = celery.control.inspect()
        
        if inspect is None:
            logger.warning("[list_pending_and_failed_tasks] Não foi possível obter inspect (workers podem não estar conectados)")
            result['error'] = 'Workers não estão conectados ou não foi possível acessar o Celery'
            return result
        
        # Lista tarefas ativas (em execução)
        active_tasks = inspect.active()
        if active_tasks:
            for worker, tasks in active_tasks.items():
                result['summary']['active'] += len(tasks)
                for task in tasks:
                    task_info = {
                        'task_id': task.get('id'),
                        'name': task.get('name'),
                        'worker': worker,
                        'status': 'STARTED',
                        'kwargs': task.get('kwargs', {}),
                        'args': task.get('args', []),
                        'time_start': task.get('time_start'),
                    }
                    result['pending'].append(task_info)
        
        # Lista tarefas reservadas (na fila, aguardando execução)
        reserved_tasks = inspect.reserved()
        if reserved_tasks:
            for worker, tasks in reserved_tasks.items():
                result['summary']['reserved'] += len(tasks)
                for task in tasks:
                    task_info = {
                        'task_id': task.get('id'),
                        'name': task.get('name'),
                        'worker': worker,
                        'status': 'PENDING',
                        'kwargs': task.get('kwargs', {}),
                        'args': task.get('args', []),
                    }
                    result['pending'].append(task_info)
        
        # Lista tarefas agendadas (scheduled)
        scheduled_tasks = inspect.scheduled()
        if scheduled_tasks:
            for worker, tasks in scheduled_tasks.items():
                result['summary']['scheduled'] += len(tasks)
                for task in tasks:
                    task_request = task.get('request', {})
                    task_info = {
                        'task_id': task_request.get('id'),
                        'name': task_request.get('task'),
                        'worker': worker,
                        'status': 'SCHEDULED',
                        'kwargs': task_request.get('kwargs', {}),
                        'args': task_request.get('args', []),
                        'eta': task.get('eta'),
                        'expires': task.get('expires'),
                    }
                    result['pending'].append(task_info)
        
        result['summary']['total_pending'] = len(result['pending'])
        
        # Para encontrar tarefas com erro, precisamos verificar o backend Redis
        # Como não temos uma lista direta de task_ids com erro, vamos tentar usar
        # a API do Celery para verificar tarefas registradas que falharam
        # Nota: Esta é uma limitação - o Celery não fornece uma API direta para
        # listar todas as tarefas com erro, apenas podemos verificar task_ids conhecidos
        
        # Alternativa: tentar usar o backend para listar tarefas com status FAILURE
        # Isso requer acesso direto ao Redis, que pode não estar disponível aqui
        # Por enquanto, retornamos uma mensagem informativa
        result['failed_note'] = 'Para listar tarefas com erro, é necessário verificar task_ids específicos usando get_task_status()'
        
        # Tentar usar stats para ver se há informações sobre tarefas falhadas
        try:
            stats = inspect.stats()
            if stats:
                for worker, worker_stats in stats.items():
                    if 'total' in worker_stats:
                        result['summary']['worker_stats'] = worker_stats
        except Exception as stats_err:
            logger.debug(f"Erro ao obter stats dos workers: {stats_err}")
        
    except Exception as e:
        logger.error(f"Erro ao listar tarefas pendentes: {e}", exc_info=True)
        result['error'] = str(e)
    
    return result


def find_failed_tasks_in_redis(limit=100):
    """
    Tenta encontrar tarefas com erro no Redis diretamente.
    
    Nota: Esta função requer acesso ao backend Redis do Celery e pode não funcionar
    em todos os ambientes.
    
    Args:
        limit (int): Limite de tarefas a verificar (padrão: 100)
    
    Returns:
        list: Lista de dicionários com informações sobre tarefas com erro
    """
    failed_tasks = []
    
    try:
        if not hasattr(celery, 'backend') or celery.backend is None:
            logger.warning("[find_failed_tasks_in_redis] Backend do Celery não disponível")
            return failed_tasks
        
        backend = celery.backend
        
        # Tentar acessar o cliente Redis diretamente
        if hasattr(backend, 'client'):
            client = backend.client
            
            # Listar todas as chaves que começam com o prefixo do Celery
            # O padrão típico é: celery-task-meta-<task_id>
            try:
                if hasattr(client, 'keys'):
                    # Nota: keys() pode ser lento em produção, mas é útil para depuração
                    pattern = backend.key_prefix + '*'
                    keys = client.keys(pattern)
                    
                    checked = 0
                    for key in keys[:limit]:
                        checked += 1
                        try:
                            # Extrai o task_id da chave
                            task_id = key.decode('utf-8').replace(backend.key_prefix, '') if isinstance(key, bytes) else key.replace(backend.key_prefix, '')
                            
                            # Obtém o status da tarefa
                            task_status = get_task_status(task_id)
                            
                            # Se a tarefa falhou, adiciona à lista
                            if task_status.get('status') == 'FAILURE':
                                failed_tasks.append({
                                    'task_id': task_id,
                                    'status': task_status.get('status'),
                                    'error': task_status.get('error'),
                                    'error_type': task_status.get('error_type'),
                                })
                        except Exception as task_err:
                            logger.debug(f"Erro ao verificar tarefa {key}: {task_err}")
                            continue
                    
                    logger.info(f"[find_failed_tasks_in_redis] Verificadas {checked} tarefas, encontradas {len(failed_tasks)} com erro")
                    
            except Exception as keys_err:
                logger.warning(f"[find_failed_tasks_in_redis] Erro ao listar chaves do Redis: {keys_err}")
        else:
            logger.warning("[find_failed_tasks_in_redis] Backend não tem cliente Redis acessível")
            
    except Exception as e:
        logger.error(f"Erro ao buscar tarefas com erro no Redis: {e}", exc_info=True)
    
    return failed_tasks
