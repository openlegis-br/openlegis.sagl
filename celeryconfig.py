# celeryconfig.py
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'
broker_connection_retry_on_startup=True
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'America/Sao_Paulo'

task_routes = {
    'tasks_folder.protocolo_prefeitura.protocolo_prefeitura_task': {'queue': 'prefeitura'}
}
