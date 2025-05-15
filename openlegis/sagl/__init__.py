###############################################################################
# Cabeçalho de Licença
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


# Importações do projeto
from openlegis.sagl import Portal, SAGLTool
from openlegis.sagl.config import PROJECTNAME
from openlegis.sagl.lexml import SAGLOAIServer
from openlegis.sagl.interfaces import (
    IWebSocketServerUtility, 
    IWebSocketServerService
)
from openlegis.sagl.browser.websocket_server import WebSocketServerService

# Logger
logger = logging.getLogger(__name__)

###############################################################################
# CONFIGURAÇÃO DE SEGURANÇA
###############################################################################

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
        'collections.Counter', 'reportlab', 'reportlab.lib',
        'reportlab.lib.utils', 'operator', 'locale', 'zlib.crc32'
    ]

    for module in allowed_modules:
        allow_module(module)

###############################################################################
# VERIFICAÇÃO DE INNSTANCIA E PORTA
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
