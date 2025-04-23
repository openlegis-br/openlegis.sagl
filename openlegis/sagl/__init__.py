###############################################################################
# Cabeçalho de Licença
###############################################################################
# Copyright (c) 2025 by OpenLegis
# GNU General Public Licence (GPL)
# Este programa é software livre sob os termos da GPL v2 ou superior
###############################################################################

# Importações padrão
from AccessControl import ModuleSecurityInfo
from Products.CMFCore.utils import ToolInit
from Products.PythonScripts.Utility import allow_module
from zope.component import provideUtility

# Importações do projeto
from openlegis.sagl import Portal, SAGLTool
from openlegis.sagl.config import PROJECTNAME
from openlegis.sagl.lexml import SAGLOAIServer
from openlegis.sagl.interfaces import (
    IWebSocketServerUtility, 
    IWebSocketServerService
)
from openlegis.sagl.browser.websocket_server import WebSocketServerService

# Configuração de logging
import logging
import asyncio
import threading

logger = logging.getLogger(__name__)

###############################################################################
# CONFIGURAÇÃO DE SEGURANÇA
###############################################################################

def configure_module_security():
    """Configura permissões para módulos Python usados em código restrito"""
    
    # Permite métodos específicos de socket
    ModuleSecurityInfo('socket.socket').declarePublic('fileno')
    
    # Permite uso de arquivos temporários
    ModuleSecurityInfo('tempfile.NamedTemporaryFile').declarePublic('flush')
    
    # Lista de módulos permitidos
    allowed_modules = [
        'zlib', 'sys', 'os', 'restpki_client', 'Acquisition',
        'ExtensionClass', 'App.FindHomes', 'trml2pdf', 'html2rml',
        'time', '_strptime', 'csv', 'pdb', 'json', 'collections',
        'base64', 'socket', 'fcntl', 'struct', 'array', 'datetime',
        'datetime.datetime.timetuple', 'pypdf', 'pymupdf', 'io',
        'io.BytesIO', 'PIL', 'uuid', 'binascii', 're', 'xml',
        'xml.sax', 'xml.sax.saxutils', 'email.message', 'email.encoders',
        'email.utils', 'email.mime.application', 'email.mime.multipart',
        'email.mime.text', 'AccessControl.PermissionRole',
        'collections.Counter', 'reportlab', 'reportlab.lib',
        'reportlab.lib.utils', 'operator', 'locale', 'zlib.crc32'
    ]
    
    for module in allowed_modules:
        allow_module(module)

###############################################################################
# INICIALIZAÇÃO DO WEBSOCKET
###############################################################################

def initialize_websocket_service():
    """Configura e inicia o serviço WebSocket em background"""
    
    service = WebSocketServerService()
    
    # Registra o serviço como utilitário Zope
    provideUtility(service, IWebSocketServerUtility)
    provideUtility(service, IWebSocketServerService)
    
    # Inicia em thread separada
    thread = threading.Thread(
        target=lambda: asyncio.run(service._start_server_task()),
        daemon=True,
        name="WebSocketServerThread"
    )
    thread.start()
    
    logger.info("Serviço WebSocket registrado e iniciado")

###############################################################################
# REGISTRO DE COMPONENTES PRINCIPAIS
###############################################################################

def register_main_components(context):
    """Registra os principais componentes do sistema"""
    
    # Ferramentas do SAGL
    tools = (SAGLTool.SAGLTool,)
    
    # Inicialização da ferramenta
    ToolInit(
        'SAGL Tool',
        tools=tools,
        icon='tool.gif'
    ).initialize(context)

    # Portal SAGL
    context.registerClass(
        Portal.SAGL,
        constructors=(
            Portal.manage_addSAGLForm,
            Portal.manage_addSAGL,
        ),
        icon='openlegisIcon.gif'
    )

    # Servidor OAI LexML
    context.registerClass(
        SAGLOAIServer.SAGLOAIServer,
        constructors=(
            SAGLOAIServer.manage_addSAGLOAIServerForm,
            SAGLOAIServer.manage_addSAGLOAIServer,
        ),
        icon='oai_service.png'
    )

###############################################################################
# INICIALIZAÇÃO PRINCIPAL
###############################################################################

def initialize(context):
    """Função principal de inicialização do pacote"""
    
    # 1. Configura segurança
    configure_module_security()
    
    # 2. Registra componentes principais
    register_main_components(context)
    
    # 3. Inicia serviço WebSocket
    initialize_websocket_service()
