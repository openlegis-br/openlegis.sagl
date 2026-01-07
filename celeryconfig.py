# celeryconfig.py
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'

# Garantir que o Celery tente reconectar caso o Redis não esteja pronto na inicialização
broker_connection_retry_on_startup = True

# Serialização segura
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Configuração para garantir serialização correta de exceções
result_backend_always_retry = True
result_backend_max_retries = 3

# Expiração automática de resultados (24 horas)
result_expires = 86400  # 24 horas em segundos

# Timezone local para agendamento e logs
timezone = 'America/Sao_Paulo'
enable_utc = False

# Otimizações para ZODB
worker_prefetch_multiplier = 1
task_acks_late = True
task_reject_on_worker_lost = True
task_track_started = True

# CRÍTICO: Configuração para evitar corrupção de BTrees em workers
# Se usar prefork (padrão), cada worker process deve ter sua própria conexão ZODB isolada
# Alternativa: usar --pool=threads na linha de comando do worker para compartilhar ZODB com segurança
# worker_pool = 'prefork'  # Padrão - requer isolamento de conexões ZODB (já implementado)
# worker_pool = 'threads'  # Alternativa mais segura para ZODB, mas pode ter limitações com GIL
worker_max_tasks_per_child = 50  # Reinicia workers periodicamente para evitar acúmulo de estado

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

# Módulos que contêm tarefas (necessário para o worker descobrir as tarefas)
# NOTA: tasks_folder.processo_leg_task NÃO deve estar aqui porque é importado em tasks.py
# Se estiver aqui, pode causar import circular ou ordem de importação incorreta
include = [
    'tasks',  # tasks.py importa todas as tasks, incluindo processo_leg_task
    'tasks_folder.proposicao_autuar',
    'tasks_folder.peticao_autuar',
    'tasks_folder.indexar_arquivo',
    # 'tasks_folder.processo_leg_task',  # REMOVIDO - importado via tasks.py
]
