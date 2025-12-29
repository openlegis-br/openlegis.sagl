###############################################################################
# Copyright (c) 2025 by OpenLegis
# GNU General Public Licence (GPL)
# Este programa é software livre sob os termos da GPL v2 ou superior
###############################################################################

# Importações padrão
import os
import socket
import logging
import asyncio
import threading
from AccessControl import ModuleSecurityInfo
from Products.CMFCore.utils import ToolInit
from Products.PythonScripts.Utility import allow_module
from zope.component import provideUtility
from App.config import getConfiguration
from zope.component import queryUtility


# Importações do projeto
from openlegis.sagl import Portal, SAGLTool
from openlegis.sagl.config import PROJECTNAME
from openlegis.sagl.lexml import SAGLOAIServer
from openlegis.sagl.interfaces import (
    IWebSocketServerUtility, 
    IWebSocketServerService,
    ISAPLDocumentManager,
)
from openlegis.sagl.browser.websocket_server import WebSocketServerService
from openlegis.sagl.document_manager import SAPLDocumentManager

# Logger
logger = logging.getLogger(__name__)

###############################################################################
# CONFIGURAÇÃO DE SEGURANÇA
###############################################################################

def patch_celery_for_zope():
    """Patch Celery's LazyModule to handle __file__ attribute for Zope compatibility"""
    try:
        # Import celery.local to ensure it's loaded, then patch it
        try:
            import celery.local
            from celery.local import LazyModule
            
            # Check if already patched
            if hasattr(LazyModule, '_original_getattr_patched'):
                return
            
            # Store original __getattr__
            original_getattr = LazyModule.__getattr__
            LazyModule._original_getattr_patched = True
            
            def patched_getattr(self, name):
                # Handle common module attributes that proxy modules might not have
                # These attributes are accessed by Zope's refcount function and other introspection tools
                proxy_module_attrs = ('__file__', '__path__', '__loader__', '__spec__', '__package__')
                
                # First check: if it's a known proxy module attribute, return None immediately
                if name in proxy_module_attrs:
                    return None
                
                # For other attributes, try the original behavior
                try:
                    return original_getattr(self, name)
                except AttributeError:
                    # If ModuleType.__getattribute__ failed, check if it's a proxy module attribute
                    # This is a safety net in case the attribute list needs to be extended
                    if name in proxy_module_attrs:
                        return None
                    # Re-raise for attributes we don't explicitly handle
                    raise
            
            LazyModule.__getattr__ = patched_getattr
            logger.debug("Patch do Celery LazyModule aplicado com sucesso")
        except ImportError:
            # Celery not available, skip patching
            pass
        
        # Patch Zope's ApplicationManager.refcount to handle modules without __file__
        try:
            from App.ApplicationManager import ApplicationManager
            original_refcount = ApplicationManager.refcount
            
            def patched_refcount(self):
                """Patched refcount that handles modules without __file__ attribute"""
                import sys
                result = {}
                for name, module in sys.modules.items():
                    try:
                        if module is None:
                            continue
                        # Try to get __file__, but handle AttributeError gracefully
                        try:
                            file_path = getattr(module, '__file__', None)
                        except (AttributeError, TypeError):
                            file_path = None
                        # Count references
                        refcount = sys.getrefcount(module)
                        if refcount > 3:  # filter out normal references
                            result[name] = (refcount, file_path)
                    except (TypeError, AttributeError):
                        # Skip modules that can't be inspected
                        continue
                return result
            
            ApplicationManager.refcount = patched_refcount
        except (ImportError, AttributeError):
            # ApplicationManager not available, skip
            pass
            
    except Exception as e:
        logger.warning(f"Erro ao aplicar patch do Celery para Zope: {e}")

def configure_module_security():
    """Configura permissões para módulos Python usados em código restrito"""

    # Permite métodos específicos de socket e tempfile
    ModuleSecurityInfo('socket.socket').declarePublic('fileno')
    ModuleSecurityInfo('tempfile.NamedTemporaryFile').declarePublic('flush')

    # Lista de módulos permitidos
    allowed_modules = [
        'zlib', 'sys', 'os', 'restpki_client', 'Acquisition',
        'ExtensionClass', 'App.FindHomes', 'trml2pdf', 'html2rml',
        'time', '_strptime', 'csv', 'pdb', 'json', 'collections',
        'base64', 'socket', 'fcntl', 'struct', 'array', 'datetime',
        'pypdf', 'pymupdf', 'io', 'PIL', 'uuid', 'binascii', 're', 'xml',
        'xml.sax', 'xml.sax.saxutils', 'email.message', 'email.encoders',
        'email.utils', 'email.mime.application', 'email.mime.multipart',
        'email.mime.text', 'AccessControl.PermissionRole',
        'collections.Counter', 'reportlab', 'reportlab.lib', 'logging',
        'reportlab.lib.utils', 'operator', 'locale', 'zlib.crc32'
    ]

    for module in allowed_modules:
        allow_module(module)

###############################################################################
# VERIFICAÇÃO DE INSTÂNCIA E PORTA
###############################################################################

def get_base_path():
    """Obtém o caminho base da instalação (ex: /var/openlegis/SAGL6)"""
    try:
        config = getConfiguration()
        instancehome = config.instancehome  # ex: /var/openlegis/SAGL6/parts/instance
        # Remove '/parts/instance' ou '/instance' do final para obter o caminho base
        if instancehome.endswith('/parts/instance'):
            return instancehome[:-15]  # Remove '/parts/instance'
        elif instancehome.endswith('/instance'):
            return instancehome[:-9]  # Remove '/instance'
        else:
            # Fallback: assume que o caminho base está 2 níveis acima
            return os.path.dirname(os.path.dirname(instancehome))
    except Exception as e:
        logger.warning(f"Não foi possível obter caminho base: {e}")
        # Fallback para SAGL6
        return '/var/openlegis/SAGL6'

def is_instance():
    """Verifica se esta é a instância 0 com base no instancehome configurado"""
    try:
        config = getConfiguration()
        instancehome = config.instancehome  # ex: /var/openlegis/SAGL6/parts/instance
        return instancehome.endswith('/instance')
    except Exception as e:
        logger.warning(f"Não foi possível obter instancehome: {e}")
        return False

def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Verifica se a porta está em uso (bind falhará se já houver alguém escutando)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False  # Sucesso no bind => porta livre
        except OSError:
            return True   # Falhou no bind => porta já em uso

###############################################################################
# CRIAÇÃO DO BANCO DE DADOS
###############################################################################

def ensure_mysql_database():
    """Cria o banco de dados MySQL se não existir e aplica migrations usando models.py"""
    try:
        import MySQLdb
        
        # Valores padrão (podem ser configurados via variáveis de ambiente)
        mysql_host = os.environ.get('MYSQL_HOST', 'localhost')
        mysql_user = os.environ.get('MYSQL_USER', 'root')
        mysql_pass = os.environ.get('MYSQL_PASS', 'openlegis')
        mysql_db = os.environ.get('MYSQL_DB', 'openlegis')
        
        try:
            db = MySQLdb.connect(host=mysql_host, user=mysql_user, passwd=mysql_pass)
        except Exception as e:
            logger.warning("Não foi possível conectar ao MySQL para criar banco: %s", str(e))
            return False
        
        if db:
            cursor = db.cursor()
            created = False
            
            # Verifica se o banco já existe consultando INFORMATION_SCHEMA
            try:
                cursor.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s", (mysql_db,))
                db_exists = cursor.fetchone() is not None
                cursor.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = 'openlegis_logs'")
                logs_exists = cursor.fetchone() is not None
                
                if not db_exists or not logs_exists:
                    # Banco não existe, precisa criar
                    if not db_exists:
                        cursor.execute("CREATE SCHEMA %s DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" % mysql_db)
                    if not logs_exists:
                        cursor.execute("CREATE SCHEMA openlegis_logs DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    db.commit()
                    logger.info("Schemas MySQL criados: %s e openlegis_logs", mysql_db)
                    created = True
            except Exception as e:
                # Se houver erro, tenta criar de qualquer forma (pode ser que não tenha permissão para consultar INFORMATION_SCHEMA)
                logger.debug("Erro ao verificar bancos existentes, tentando criar: %s", str(e))
                try:
                    cursor.execute("CREATE SCHEMA IF NOT EXISTS %s DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" % mysql_db)
                    cursor.execute("CREATE SCHEMA IF NOT EXISTS openlegis_logs DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    db.commit()
                    created = True
                except Exception as e2:
                    # Banco pode já existir
                    logger.debug("Erro ao criar schemas (podem já existir): %s", str(e2))
            
            # Tenta criar usuário MySQL (pode falhar se já existir)
            try:
                # Verifica se o usuário já existe
                cursor.execute("SELECT User FROM mysql.user WHERE User = 'sagl' AND Host = 'localhost'")
                user_exists = cursor.fetchone() is not None
                
                if not user_exists:
                    cursor.execute("CREATE USER 'sagl'@'localhost' IDENTIFIED BY 'sagl'")
                    logger.debug("Usuário MySQL 'sagl' criado")
                
                cursor.execute("GRANT ALL ON %s.* TO 'sagl'@'localhost'" % mysql_db)
                cursor.execute("GRANT ALL ON openlegis_logs.* TO 'sagl'@'localhost'")
                db.commit()
            except Exception as e:
                # Usuário pode já existir ou não ter permissão para criar usuário, não é crítico
                logger.debug("Erro ao criar/atualizar usuário MySQL 'sagl' (pode não ter permissão): %s", str(e))
            
            db.close()
            
            # Cria tabelas usando SQLAlchemy models.py através do Alembic
            # O apply_migrations já tem fallback para create_tables_from_base se não houver migrations
            try:
                from openlegis.sagl.models.migrations import apply_migrations
                
                # Constrói URL do banco de dados para o Alembic
                database_url = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}/{mysql_db}?charset=utf8mb4"
                
                # Aplica migrations (ou cria tabelas diretamente do Base se não houver migrations)
                # apply_migrations já cuida das tabelas de logs também
                apply_migrations(database_url)
                    
            except Exception as e:
                logger.warning("Erro ao aplicar migrations/criar tabelas: %s", str(e))
                import traceback
                logger.debug(traceback.format_exc())
            
            return True
        return False
    except ImportError:
        logger.warning("MySQLdb não disponível - banco de dados não será criado automaticamente")
        return False
    except Exception as e:
        logger.warning("Erro ao criar banco de dados MySQL: %s", str(e))
        import traceback
        logger.debug(traceback.format_exc())
        return False

###############################################################################
# INICIALIZAÇÃO DO WEBSOCKET
###############################################################################

def initialize_websocket_service():
    """Configura e inicia o serviço WebSocket em thread de fundo"""

    try:
        service = WebSocketServerService()
        provideUtility(service, IWebSocketServerUtility)
        provideUtility(service, IWebSocketServerService)

        def run_server():
            try:
                asyncio.run(service._start_server_task())
            except Exception as e:
                logger.exception("Erro ao iniciar WebSocketServerService: %s", e)

        thread = threading.Thread(
            target=run_server,
            daemon=True,
            name="WebSocketServerThread"
        )
        thread.start()

        logger.info("Servidor WebSocket configurado e iniciando na porta 8765")

    except Exception as e:
        logger.exception("Falha ao registrar ou iniciar o serviço WebSocket: %s", e)

###############################################################################
# REGISTRO DE COMPONENTES PRINCIPAIS
###############################################################################

def register_main_components(context):
    """Registra os principais componentes do sistema"""

    tools = (SAGLTool.SAGLTool,)

    ToolInit(
        'SAGL Tool',
        tools=tools,
        icon='tool.gif'
    ).initialize(context)

    context.registerClass(
        Portal.SAGL,
        constructors=(Portal.manage_addSAGLForm, Portal.manage_addSAGL),
        icon='openlegisIcon.gif'
    )

    context.registerClass(
        SAGLOAIServer.SAGLOAIServer,
        constructors=(
            SAGLOAIServer.manage_addSAGLOAIServerForm,
            SAGLOAIServer.manage_addSAGLOAIServer
        ),
        icon='oai_service.png'
    )

###############################################################################
# INICIALIZAÇÃO PRINCIPAL DO PACOTE
###############################################################################

def initialize(context):
    """Função principal de inicialização do pacote"""

    # 0. Aplica patch para compatibilidade Celery/Zope (antes de qualquer import do Celery)
    patch_celery_for_zope()

    # 1. Configura segurança
    configure_module_security()

    # 2. Registra componentes
    register_main_components(context)

    # 3. Cria o banco de dados MySQL se não existir (antes de iniciar o WebSocket)
    if is_instance():
        logger.info("Verificando/criando banco de dados MySQL...")
        ensure_mysql_database()

    # 4. Inicia o WebSocket apenas se esta for a instância 'instance0'
    # DESATIVADO: WebSocket desabilitado
    # if is_instance():
    #     if is_port_in_use(8765):
    #         logger.warning("Porta 8765 já está em uso. WebSocket não será iniciado.")
    #     else:
    #         initialize_websocket_service()

    # 5. REGISTRA A UTILITY DE GERENCIAMENTO DE DOCUMENTOS NA ZODB
    try:
        # Tenta usar o context como raiz, normalmente funciona em SAPL puro.
        provideUtility(SAPLDocumentManager(context), ISAPLDocumentManager)
        m = queryUtility(ISAPLDocumentManager)
        logger.debug("ISAGLDocumentManager registrado")
    except Exception as e:
        logger.exception("Erro ao registrar ISAGLDocumentManager: %s", e)

    # 6. VERIFICA E CRIA APLICAÇÃO SAGL NA RAIZ SE NÃO EXISTIR
    # Usar um timer para executar após o Zope estar totalmente inicializado
    def create_sagl_after_startup():
        """Cria a aplicação SAGL após o Zope estar totalmente inicializado"""
        import time
        time.sleep(5)  # Aguarda 5 segundos para o Zope estar totalmente pronto e a conexão ZODB estar estável
        
        try:
            # Get the root application directly from Zope2
            import Zope2
            app = Zope2.app()
            
            if app is None:
                logger.warning("Não foi possível obter a aplicação Zope para verificar/criar SAGL")
                return
            
            sagl_id = 'sagl'
            
            # Check if SAGL already exists in root
            if hasattr(app, 'objectIds') and sagl_id in app.objectIds():
                # Aplicação já existe, não precisa fazer nada nem logar
                return
            
            # SAGL doesn't exist, create it
            logger.info("SAGL '%s' não encontrado na raiz, criando aplicação após inicialização...", sagl_id)
            
            try:
                # Garante que o banco de dados existe (já foi criado anteriormente, mas verifica novamente)
                ensure_mysql_database()
                
                # Define the create function locally
                def create(container, sagl_id):
                    from openlegis.sagl import Portal
                    from zope.component.hooks import setSite
                    if sagl_id in container.objectIds():
                        sagl = getattr(container, sagl_id)
                        return (sagl, False)
                    factory = container.manage_addProduct['openlegis.sagl']
                    factory.manage_addSAGL(sagl_id, title='SAGL', database="MySQL")
                    sagl = getattr(container, sagl_id)
                    setSite(sagl)
                    return (sagl, True)
                
                from zope.component.hooks import setSite
                import transaction
                from AccessControl.SecurityManagement import newSecurityManager, noSecurityManager
                
                # Set up security manager
                acl_users = app.acl_users
                admin_user = 'admin'
                user = acl_users.getUser(admin_user)
                if user:
                    user = user.__of__(acl_users)
                    newSecurityManager(None, user)
                    logger.info("Usuário admin configurado para criação do SAGL")
                else:
                    # Try to create admin user
                    try:
                        if hasattr(acl_users, 'userFolderAddUser'):
                            acl_users.userFolderAddUser(admin_user, 'openlegis', ['Manager'], [])
                            transaction.commit()
                            user = acl_users.getUser(admin_user)
                            if user:
                                user = user.__of__(acl_users)
                                newSecurityManager(None, user)
                                logger.info("Usuário admin criado para criação do SAGL")
                    except Exception as e:
                        logger.warning("Não foi possível criar/obter usuário admin: %s", str(e))
                        return  # Can't proceed without admin user
                
                # Create SAGL
                sagl, created = create(app, sagl_id)
                
                if created:
                    logger.info("SAGL '%s' criado com sucesso durante inicialização do Zope", sagl_id)
                    
                    # Run setup profile
                    try:
                        setup_tool = getattr(sagl, 'portal_setup')
                        setup_tool.runAllImportStepsFromProfile('profile-openlegis.sagl:default')
                        logger.info("Profile openlegis.sagl:default aplicado durante inicialização")
                    except Exception as e:
                        logger.warning("Erro ao aplicar profile durante inicialização: %s", str(e))
                    
                    # Mark objects as changed to ensure they're saved
                    if hasattr(app, '_p_changed'):
                        app._p_changed = 1
                    if hasattr(sagl, '_p_changed'):
                        sagl._p_changed = 1
                    
                    # Commit transaction to ensure persistence
                    transaction.commit()
                    logger.info("SAGL '%s' inicializado e commitado com sucesso durante inicialização do Zope", sagl_id)
                    
                    # Verify it was created
                    if sagl_id in app.objectIds():
                        logger.info("VERIFICAÇÃO: SAGL '%s' confirmado nos objectIds após commit", sagl_id)
                    else:
                        logger.warning("AVISO: SAGL '%s' não encontrado nos objectIds após commit - pode não ter persistido", sagl_id)
                
                noSecurityManager()
                
            except Exception as e:
                logger.error("Erro ao criar SAGL após inicialização: %s", str(e))
                import traceback
                logger.error(traceback.format_exc())
                try:
                    noSecurityManager()
                except:
                    pass
        except Exception as e:
            logger.warning("Erro ao verificar/criar SAGL após inicialização: %s", str(e))
            # Não falha a inicialização se houver erro aqui
    
    # Inicia o timer em uma thread separada para executar após a inicialização
    # A thread verifica silenciosamente se a aplicação existe e só loga se precisar criar
    timer_thread = threading.Thread(target=create_sagl_after_startup, daemon=True, name="SAGLCreationThread")
    timer_thread.start()
