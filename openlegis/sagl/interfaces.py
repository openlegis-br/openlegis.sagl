# -*- coding: utf-8 -*-
from zope.interface import Interface, Attribute

class IFileSAGL(Interface):
    """ interface para ser implementada no tipo file do zope
    """


class ISAPLDocumentManager(Interface):
    def existe_documento(tipo, nome):
        """Retorna True se o documento 'nome' do tipo 'tipo' existe no repositório."""


class ILogradouroTableViewExporter(Interface):
    """Interface for Logradouro table view exporters."""

    def render(data, columns, request):
        """Renders the exported data."""

    def get_data_query(request):
        """Builds and returns the data query for export."""


class IWebSocketServerUtility(Interface):
    """Interface para o utilitário do servidor WebSocket"""
    
    async def websocket_handler(websocket, path):
        """Manipulador principal de conexões WebSocket"""
    
    async def monitor_sessoes_e_itens():
        """Monitora mudanças nas sessões e itens"""
    
    async def get_server_stats():
        """Retorna estatísticas do servidor"""
    
    async def restart_server():
        """Reinicia o servidor WebSocket"""
    
    clients = Attribute("Dicionário de clientes conectados")
    rooms = Attribute("Dicionário de salas disponíveis")
    max_connections = Attribute("Número máximo de conexões permitidas")


class IWebSocketServerService(Interface):
    """Interface para o serviço do servidor WebSocket"""
    
    async def broadcast_to_room(room_name, message):
        """Envia uma mensagem para todos os clientes em uma sala"""
    
    async def get_active_sessions():
        """Retorna informações sobre sessões ativas"""
    
    async def get_active_item_for_session(cod_sessao_plen):
        """Retorna o item ativo para uma sessão específica"""
    
    version = Attribute("Versão do servidor WebSocket")
    protocol_version = Attribute("Versão do protocolo suportado")
    server_start_time = Attribute("Data/hora de inicialização do servidor")


class ISessionStateManager(Interface):
    """Interface para o gerenciador de estado das sessões"""
    
    async def save_state(sessao, item):
        """Salva o estado atual da sessão"""
    
    async def get_last_state(cod_sessao):
        """Recupera o último estado salvo de uma sessão"""
    
    async def get_last_item_for_session(cod_sessao):
        """Recupera o último item ativo de uma sessão"""
    
    def format_sessao_info(sessao):
        """Formata as informações da sessão para envio"""
    
    def format_item_info(item):
        """Formata as informações do item para envio"""


class IWebSocketMessage(Interface):
    """Interface para mensagens WebSocket"""
    
    event = Attribute("Tipo do evento (ex: 'item_update', 'session_end')")
    data = Attribute("Dados da mensagem")
    room = Attribute("Sala de destino (opcional)")
    timestamp = Attribute("Data/hora da mensagem")
    
    def validate():
        """Valida a estrutura da mensagem"""
