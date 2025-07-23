# celeryconfig.py
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'

# Garantir que o Celery tente reconectar caso o Redis não esteja pronto na inicialização
broker_connection_retry_on_startup = True

# Serialização segura
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Timezone local para agendamento e logs
timezone = 'America/Sao_Paulo'
enable_utc = False

# Otimizações para ZODB
worker_prefetch_multiplier = 1
task_acks_late = True
task_reject_on_worker_lost = True
task_track_started = True

# Reintento padrão (usado se não especificar em @task)
task_default_retry_delay = 10               # segundos entre reintentos
task_default_max_retries = 3                # número máximo de tentativas

# Timeouts
broker_transport_options = {
    'visibility_timeout': 600,  # 10 minutos
    'max_retries': 3
}

# Rotas específicas por fila
task_routes = {
    #'tasks_folder.protocolo_prefeitura.protocolo_prefeitura_task': {'queue': 'prefeitura'}
    #'tasks_folder.utils.proposicao_autuar_task': {'queue': 'assinaturas'},  # opcional, se quiser separar
}
