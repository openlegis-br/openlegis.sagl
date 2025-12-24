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

def is_instance():
    """Verifica se esta é a instância 0 com base no instancehome configurado"""
    try:
        config = getConfiguration()
        instancehome = config.instancehome  # ex: /var/openlegis/SAGL5/parts/instance
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

        logger.info("Serviço WebSocket registrado e iniciado")

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

    # 3. Inicia o WebSocket apenas se esta for a instância 'instance0'
    if is_instance():
        if is_port_in_use(8765):
            logger.warning("Porta 8765 já está em uso. WebSocket não será iniciado.")
        else:
            initialize_websocket_service()

    # 4. REGISTRA A UTILITY DE GERENCIAMENTO DE DOCUMENTOS NA ZODB
    try:
        # Tenta usar o context como raiz, normalmente funciona em SAPL puro.
        provideUtility(SAPLDocumentManager(context), ISAPLDocumentManager)
        m = queryUtility(ISAPLDocumentManager)
        logger.info("Testando queryUtility após registro: %s", m)
        logger.info("ISAGLDocumentManager registrado com sucesso.")
    except Exception as e:
        logger.exception("Erro ao registrar ISAGLDocumentManager: %s", e)

    # 5. VERIFICA E CRIA APLICAÇÃO SAGL NA RAIZ SE NÃO EXISTIR
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
