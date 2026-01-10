# CRÍTICO: Criar o app Celery AQUI primeiro, antes de qualquer import
# Isso garante que todos os módulos usem o MESMO app Celery
from celery import Celery
import logging
import sys

# Configura logging imediatamente para ver o que está acontecendo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Logs removidos - apenas logs de erro são mantidos

# Cria o app Celery centralizado - este é o app que o worker usa com -A tasks
try:
    app = Celery('tasks', config_source='celeryconfig')
except Exception as e:
    logger.error(f"[tasks.py] ERRO ao criar app Celery: {e}", exc_info=True)
    raise


# Import tasks to register them with the Celery app
from tasks_folder.proposicao_autuar import proposicao_autuar_task
from tasks_folder.peticao_autuar import peticao_autuar_task
from tasks_folder.indexar_arquivo import indexar_arquivo_task

# Import processo_leg_task - CRÍTICO: deve ser importado para registrar a tarefa
# Se houver erro aqui, a tarefa não será registrada e o worker não conseguirá executá-la
try:
    from tasks_folder.processo_leg_task import gerar_processo_leg_integral_task
    
    # CRÍTICO: Garante que a task está exposta no módulo mesmo se houver erro na verificação
    # Isso permite que SAGLTool._import_task_function() encontre a task via hasattr(tasks, 'gerar_processo_leg_integral_task')
    
    if gerar_processo_leg_integral_task is None:
        logger.error("[tasks.py] ✗ gerar_processo_leg_integral_task é None após importação!")
    elif hasattr(gerar_processo_leg_integral_task, 'name'):
        task_name = gerar_processo_leg_integral_task.name
        # Verifica se está registrada no Celery
        if task_name not in app.tasks:
            logger.error(f"[tasks.py] ✗ Tarefa {task_name} NÃO está registrada no Celery!")
            logger.error(f"[tasks.py] Tarefas disponíveis: {list(app.tasks.keys())[:20]}")
            # Tenta registrar manualmente
            logger.warning(f"[tasks.py] Tentando registrar manualmente...")
            try:
                app.register_task(gerar_processo_leg_integral_task)
            except Exception as reg_err:
                logger.error(f"[tasks.py] Erro ao registrar manualmente: {reg_err}", exc_info=True)
except ImportError as ie:
    logger.error(f"[tasks.py] ERRO de importação ao importar gerar_processo_leg_integral_task: {ie}", exc_info=True)
    import traceback
    logger.error(f"[tasks.py] Traceback completo:\n{traceback.format_exc()}")
    # CRÍTICO: Define como None para evitar AttributeError no SAGLTool
    gerar_processo_leg_integral_task = None
except Exception as e:
    logger.error(f"[tasks.py] ERRO ao importar gerar_processo_leg_integral_task: {e}", exc_info=True)
    import traceback
    logger.error(f"[tasks.py] Traceback completo:\n{traceback.format_exc()}")
    # CRÍTICO: Define como None para evitar AttributeError no SAGLTool
    gerar_processo_leg_integral_task = None

# CRÍTICO: Garante que a task está sempre exposta no módulo (mesmo que seja None em caso de erro)
# Isso permite que SAGLTool._import_task_function() verifique com hasattr()
if 'gerar_processo_leg_integral_task' not in globals():
    gerar_processo_leg_integral_task = None

# Import processo_norma_task - CRÍTICO: deve ser importado para registrar a tarefa
# Se houver erro aqui, a tarefa não será registrada e o worker não conseguirá executá-la
try:
    from tasks_folder.processo_norma_task import gerar_processo_norma_integral_task
    
    if hasattr(gerar_processo_norma_integral_task, 'name'):
        task_name = gerar_processo_norma_integral_task.name
        # Verifica se está registrada no Celery
        if task_name not in app.tasks:
            logger.error(f"[tasks.py] ✗ Tarefa {task_name} NÃO está registrada no Celery!")
            logger.error(f"[tasks.py] Tarefas disponíveis: {list(app.tasks.keys())[:20]}")
            # Tenta registrar manualmente
            logger.warning(f"[tasks.py] Tentando registrar manualmente...")
            try:
                app.register_task(gerar_processo_norma_integral_task)
            except Exception as reg_err:
                logger.error(f"[tasks.py] Erro ao registrar manualmente: {reg_err}", exc_info=True)
    else:
        logger.warning(f"[tasks.py] Tarefa importada mas sem atributo 'name'")
except Exception as e:
    logger.error(f"[tasks.py] ERRO ao importar gerar_processo_norma_integral_task: {e}", exc_info=True)
    import traceback
    logger.error(f"[tasks.py] Traceback completo:\n{traceback.format_exc()}")
    # Não re-raise para não quebrar o worker, mas loga o erro
    # raise

# Import processo_adm_task - CRÍTICO: deve ser importado para registrar a tarefa
# Se houver erro aqui, a tarefa não será registrada e o worker não conseguirá executá-la
try:
    from tasks_folder.processo_adm_task import gerar_processo_adm_integral_task
    
    if hasattr(gerar_processo_adm_integral_task, 'name'):
        task_name = gerar_processo_adm_integral_task.name
        # Verifica se está registrada no Celery
        if task_name not in app.tasks:
            logger.error(f"[tasks.py] ✗ Tarefa {task_name} NÃO está registrada no Celery!")
            logger.error(f"[tasks.py] Tarefas disponíveis: {list(app.tasks.keys())[:20]}")
            # Tenta registrar manualmente
            logger.warning(f"[tasks.py] Tentando registrar manualmente...")
            try:
                app.register_task(gerar_processo_adm_integral_task)
            except Exception as reg_err:
                logger.error(f"[tasks.py] Erro ao registrar manualmente: {reg_err}", exc_info=True)
    else:
        logger.warning(f"[tasks.py] Tarefa importada mas sem atributo 'name'")
except Exception as e:
    logger.error(f"[tasks.py] ERRO ao importar gerar_processo_adm_integral_task: {e}", exc_info=True)
    import traceback
    logger.error(f"[tasks.py] Traceback completo:\n{traceback.format_exc()}")
    # Não re-raise para não quebrar o worker, mas loga o erro
    # raise

# Logs removidos - apenas logs de erro são mantidos

# Alias para compatibilidade com código que espera 'celery' em vez de 'app'
celery = app

