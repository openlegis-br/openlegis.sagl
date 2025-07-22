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

# Permitir reexecução de tarefas em caso de falha (ZODB ConflictError, etc)
task_acks_late = True                       # só marca como "ACK" após completar com sucesso
task_reject_on_worker_lost = True           # rejeita se o worker morre no meio
task_acks_on_failure_or_timeout = True      # re-encaminha a tarefa se falhar

# Reintento padrão (usado se não especificar em @task)
task_default_retry_delay = 5                # segundos entre reintentos
task_default_max_retries = 5                # número máximo de tentativas

# Rotas específicas por fila
task_routes = {
    'tasks_folder.protocolo_prefeitura.protocolo_prefeitura_task': {'queue': 'prefeitura'}
    #'tasks_folder.utils.proposicao_autuar_task': {'queue': 'assinaturas'},  # opcional, se quiser separar
}
