from celery import Celery

from tasks_folder.proposicao_autuar import proposicao_autuar_task
from tasks_folder.peticao_autuar import peticao_autuar_task
from tasks_folder.indexar_arquivo import indexar_arquivo_task

celery = Celery('tasks', config_source='celeryconfig')
