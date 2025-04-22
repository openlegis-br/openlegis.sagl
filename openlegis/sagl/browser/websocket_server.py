from five import grok
from zope.component import provideUtility
from openlegis.sagl.interfaces import IWebSocketServerUtility
from openlegis.sagl.interfaces import IWebSocketServerService
import asyncio
import websockets
import logging
import uuid
import json
import os
import psutil
from datetime import datetime, timedelta
import time
from sqlalchemy.orm import sessionmaker, joinedload
from z3c.saconfig import named_scoped_session
from sqlalchemy import select
from openlegis.sagl.models.models import (
    SessaoPlenaria, 
    SessaoPlenariaPainel,
    TipoSessaoPlenaria,
    SessaoLegislativa,
    Legislatura
)

# Configurações
Session = named_scoped_session('minha_sessao')
logger = logging.getLogger(__name__)
WEBSOCKET_PORT = 8765
ALLOWED_ORIGINS = ["http://localhost", "http://127.0.0.1", "http://seusite.com"]
MAX_MESSAGE_RATE = 100
SERVER_VERSION = "1.4.0"
PROTOCOL_VERSION = "1.1"
PING_INTERVAL = 20
PING_TIMEOUT = 60

class SessionState:
    """Gerencia o estado persistente das sessões"""
    def __init__(self):
        self.last_sessions = {}
        self.last_active_items = {}
        
    async def save_state(self, sessao, item):
        """Salva o estado atual da sessão"""
        if sessao:
            self.last_sessions[sessao.cod_sessao_plen] = {
                'sessao': self.format_sessao_info(sessao),
                'item': self.format_item_info(item) if item else None,
                'timestamp': datetime.now()
            }
            
            if item:
                self.last_active_items[sessao.cod_sessao_plen] = item.cod_item
            elif sessao.cod_sessao_plen in self.last_active_items:
                del self.last_active_items[sessao.cod_sessao_plen]
    
    async def get_last_state(self, cod_sessao):
        return self.last_sessions.get(cod_sessao)

    async def get_last_item_for_session(self, cod_sessao):
        return self.last_active_items.get(cod_sessao)

    def format_sessao_info(self, sessao):
        if not sessao:
            return None
            
        status = 'ABERTA' if sessao.hr_inicio_sessao and not sessao.hr_fim_sessao else 'ENCERRADA'
            
        return {
            'cod_sessao_plen': sessao.cod_sessao_plen,
            'num_sessao_plen': sessao.num_sessao_plen,
            'tipo_sessao': {
                'codigo': sessao.tip_sessao,
                'nome': sessao.tipo_sessao_plenaria.nom_sessao if sessao.tipo_sessao_plenaria else None
            },
            'legislatura': {
                'numero': sessao.num_legislatura,
                'data_inicio': sessao.legislatura.dat_inicio.isoformat() if sessao.legislatura and sessao.legislatura.dat_inicio else None,
                'data_fim': sessao.legislatura.dat_fim.isoformat() if sessao.legislatura and sessao.legislatura.dat_fim else None
            },
            'sessao_legislativa': {
                'codigo': sessao.cod_sessao_leg,
                'numero': sessao.sessao_legislativa.num_sessao_leg if sessao.sessao_legislativa else None,
                'tipo': sessao.sessao_legislativa.tip_sessao_leg if sessao.sessao_legislativa else None
            },
            'datas': {
                'inicio_sessao': sessao.dat_inicio_sessao.isoformat() if sessao.dat_inicio_sessao else None,
                'fim_sessao': sessao.dat_fim_sessao.isoformat() if sessao.dat_fim_sessao else None,
                'horario_inicio': sessao.hr_inicio_sessao,
                'horario_fim': sessao.hr_fim_sessao
            },
            'status': status
        }

    def format_item_info(self, item):
        if not item:
            return None
            
        return {
            'cod_item': item.cod_item,
            'tipo_item': item.tip_item,
            'cod_sessao_plen': item.cod_sessao_plen,
            'ordem': item.num_ordem,
            'texto_exibicao': item.txt_exibicao,
            'fase': item.nom_fase,
            'cod_materia': item.cod_materia,
            'autoria': item.txt_autoria,
            'turno': item.txt_turno,
            'data_inicio': item.dat_inicio.isoformat() if item.dat_inicio else None,
            'data_fim': item.dat_fim.isoformat() if item.dat_fim else None,
            'extrapauta': bool(item.ind_extrapauta),
            'ind_exibicao': item.ind_exibicao,
            'status': 'ATIVO' if item.ind_exibicao == 1 else 'INATIVO'
        }

class WebSocketServerService(grok.GlobalUtility):
    grok.implements(IWebSocketServerService)

    def __init__(self):
        self.state_manager = SessionState()
        self.lock = asyncio.Lock()
        self._server_task = None
        self._server_start_time = None
        self.clients = {}
        self.rooms = {
            'geral': set(),
            'sessoes': {},
        }
        self.max_connections = 1000

    async def _start_server_task(self):
        self._server_start_time = datetime.now()
    
        logger.info("Iniciando servidor WebSocket...")
        try:
            async with websockets.serve(
                self.websocket_handler,
                "0.0.0.0",
                WEBSOCKET_PORT,
                ping_interval=PING_INTERVAL,
                ping_timeout=PING_TIMEOUT,
                close_timeout=None,
                max_size=2**20,
                compression=None,
                origins=None
            ):
                logger.info(f"Servidor WebSocket executando em ws://0.0.0.0:{WEBSOCKET_PORT}")
                monitor_task = asyncio.create_task(self.monitor_sessoes_e_itens())
                health_task = asyncio.create_task(self.health_monitor())
                try:
                    await asyncio.Future()
                finally:
                    monitor_task.cancel()
                    health_task.cancel()
                    await asyncio.gather(monitor_task, health_task, return_exceptions=True)
        except Exception as e:
            logger.error(f"Erro ao iniciar servidor WebSocket: {e}", exc_info=True)
            raise

    async def websocket_handler(self, websocket, path=None):
        client_id = str(uuid.uuid4())
        
        try:
            origin = None
            if hasattr(websocket, 'request_headers'):
                origin = websocket.request_headers.get('Origin')
            elif hasattr(websocket, 'headers'):
                origin = websocket.headers.get('Origin')
            
            logger.info(f"Cliente {client_id} conectando de origem: {origin}")

            async with self.lock:
                if len(self.clients) >= self.max_connections:
                    logger.warning(f"Número máximo de conexões atingido ({self.max_connections})")
                    await websocket.close(code=1013, reason="Too many connections")
                    return
                
                self.clients[websocket] = {
                    "id": client_id,
                    "rooms": set(['geral']),
                    "connected_at": datetime.now(),
                    "last_active": datetime.now(),
                    "message_count": 0,
                    "last_message_time": time.time()
                }
                self.rooms['geral'].add(websocket)
            
            logger.info(f"Cliente {client_id} conectado com sucesso. Total de clientes: {len(self.clients)}")

            try:
                await self._send_initial_state(websocket, client_id)
            except Exception as e:
                logger.error(f"Erro ao enviar estado inicial para {client_id}: {e}", exc_info=True)
                raise

            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=PING_INTERVAL * 2)
                    async with self.lock:
                        self.clients[websocket]["last_active"] = datetime.now()
                        self.clients[websocket]["message_count"] += 1
                        self.clients[websocket]["last_message_time"] = time.time()
                    
                    await self._process_client_message(websocket, client_id, message)
                except asyncio.TimeoutError:
                    try:
                        await websocket.ping()
                        continue
                    except ConnectionError:
                        break
                except websockets.exceptions.ConnectionClosed:
                    break
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem do cliente {client_id}: {e}", exc_info=True)
                    break

        except Exception as e:
            logger.error(f"Erro na conexão com {client_id}: {str(e)}", exc_info=True)
        finally:
            logger.info(f"Encerrando conexão com {client_id}")
            await self.remove_client_from_all_rooms(websocket)

    async def _send_initial_state(self, websocket, client_id):
        try:
            await self._safe_send(websocket, {
                "event": "connected",
                "client_id": client_id,
                "message": "Conectado ao servidor de sessões plenárias",
                "server_info": {
                    "version": SERVER_VERSION,
                    "uptime": str(datetime.now() - self._server_start_time) if self._server_start_time else "0",
                    "max_connections": self.max_connections,
                    "current_connections": len(self.clients),
                    "last_updated": datetime.now().isoformat()
                },
                "protocol": {
                    "version": PROTOCOL_VERSION,
                    "compatible_clients": ["1.1+"]
                },
                "timestamp": datetime.now().isoformat()
            })

            session = Session()
            try:
                active_sessao, active_item = fetch_active_sessao_and_item(session)
            
                if active_sessao:
                    room_name = f"sessao_{active_sessao.cod_sessao_plen}"
                    sessao_info = self.state_manager.format_sessao_info(active_sessao)
                
                    await self._safe_send(websocket, {
                        "event": "current_sessao",
                        "data": sessao_info,
                        "room": room_name
                    })

                    if active_item:
                        item_info = self.state_manager.format_item_info(active_item)
                        await self._safe_send(websocket, {
                            "event": "current_item",
                            "data": {
                                "item": item_info,
                                "sessao": sessao_info
                            },
                            "room": room_name
                        })
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Erro ao enviar estado inicial para {client_id}: {e}", exc_info=True)
            raise
            
    async def _process_client_message(self, websocket, client_id, message):
        try:
            msg = json.loads(message)
            
            async with self.lock:
                client_info = self.clients.get(websocket)
                if not client_info:
                    return
                
                now = time.time()
                if client_info["message_count"] > 0:
                    min_interval = 60 / MAX_MESSAGE_RATE
                    if now - client_info["last_message_time"] < min_interval:
                        await websocket.close(code=1008, reason="Rate limit exceeded")
                        return
                
                client_info["message_count"] += 1
                client_info["last_message_time"] = now

            action = msg.get("action")

            if action == "join_room":
                await self._handle_join_room(websocket, client_id, msg)
            elif action == "leave_room":
                await self._handle_leave_room(websocket, client_id, msg)
            elif action == "get_room_info":
                await self._handle_get_room_info(websocket, msg)
            elif action == "list_rooms":
                await self._handle_list_rooms(websocket, client_id)
            elif action == "get_current_state":
                await self._send_current_state(websocket)
            elif msg.get("type") == "heartbeat":
                async with self.lock:
                    self.clients[websocket]["last_active"] = datetime.now()
            else:
                await self._safe_send(websocket, {
                    "event": "error",
                    "message": f"Ação desconhecida: {action}"
                })
                
        except json.JSONDecodeError:
            await self._safe_send(websocket, {
                "event": "error",
                "message": "Mensagem JSON inválida"
            })
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}", exc_info=True)
            await self._safe_send(websocket, {
                "event": "error",
                "message": "Erro interno ao processar mensagem"
            })

    async def _send_current_state(self, websocket):
        session = Session()
        try:
            active_sessao, active_item = fetch_active_sessao_and_item(session)
            
            if active_sessao:
                room_name = f"sessao_{active_sessao.cod_sessao_plen}"
                sessao_info = self.state_manager.format_sessao_info(active_sessao)
            
                await self._safe_send(websocket, {
                    "event": "current_sessao",
                    "data": sessao_info,
                    "room": room_name
                })

                if active_item:
                    item_info = self.state_manager.format_item_info(active_item)
                    await self._safe_send(websocket, {
                        "event": "current_item",
                        "data": {
                            "item": item_info,
                            "sessao": sessao_info
                        },
                        "room": room_name
                    })
        finally:
            session.close()

    async def _handle_join_room(self, websocket, client_id, msg):
        cod_sessao_plen = msg.get("cod_sessao_plen")
        if not cod_sessao_plen:
            await self._safe_send(websocket, {
                "event": "error",
                "message": "Código da sessão não fornecido"
            })
            return
            
        room_name = f"sessao_{cod_sessao_plen}"
        
        sessao = await asyncio.to_thread(fetch_complete_sessao, cod_sessao_plen)
        if not sessao:
            await self._safe_send(websocket, {
                "event": "error",
                "message": f"Sessão {cod_sessao_plen} não encontrada"
            })
            return
            
        async with self.lock:
            if room_name not in self.rooms['sessoes']:
                self.rooms['sessoes'][room_name] = {
                    'websockets': set(),
                    'info': self.state_manager.format_sessao_info(sessao)
                }
            
            self.rooms['sessoes'][room_name]['websockets'].add(websocket)
            self.clients[websocket]['rooms'].add(room_name)
        
        await self._safe_send(websocket, {
            "event": "room_joined",
            "room": room_name,
            "status": "success"
        })
        
        active_item = await asyncio.to_thread(get_active_item_for_sessao, cod_sessao_plen)
        if active_item:
            await self._safe_send(websocket, {
                "event": "current_item",
                "data": {
                    "item": self.state_manager.format_item_info(active_item),
                    "sessao": self.state_manager.format_sessao_info(sessao)
                },
                "room": room_name
            })

    async def _handle_leave_room(self, websocket, client_id, msg):
        room_name = msg.get("room_name")
        if not room_name or room_name == 'geral':
            return
            
        async with self.lock:
            if room_name in self.rooms['sessoes'] and websocket in self.rooms['sessoes'][room_name]['websockets']:
                self.rooms['sessoes'][room_name]['websockets'].remove(websocket)
                self.clients[websocket]['rooms'].remove(room_name)
                
                await self._safe_send(websocket, {
                    "event": "room_left",
                    "room_name": room_name,
                    "status": "success"
                })
                logger.info(f"Cliente {client_id} saiu da sala {room_name}")

    async def _handle_get_room_info(self, websocket, msg):
        room_name = msg.get("room_name")
        if not room_name:
            await self._safe_send(websocket, {
                "event": "error",
                "message": "Nome da sala não fornecido"
            })
            return
            
        if room_name == 'geral':
            room_info = {
                'nome': 'geral',
                'tipo': 'geral',
                'clientes': len(self.rooms['geral'])
            }
        elif room_name in self.rooms['sessoes']:
            room_info = {
                'nome': room_name,
                'tipo': 'sessao_plenaria',
                'clientes': len(self.rooms['sessoes'][room_name]['websockets']),
                **self.rooms['sessoes'][room_name]['info']
            }
        else:
            await self._safe_send(websocket, {
                "event": "error",
                "message": f"Sala {room_name} não encontrada"
            })
            return
            
        await self._safe_send(websocket, {
            "event": "room_info",
            "room_info": room_info
        })

    async def _handle_list_rooms(self, websocket, client_id):
        client_rooms = [r for r in self.clients[websocket]['rooms'] if r != 'geral']
        rooms_info = []
        
        for room_name in client_rooms:
            if room_name in self.rooms['sessoes']:
                rooms_info.append({
                    'nome': room_name,
                    'tipo': 'sessao_plenaria',
                    'clientes': len(self.rooms['sessoes'][room_name]['websockets']),
                    **self.rooms['sessoes'][room_name]['info']
                })
        
        await self._safe_send(websocket, {
            "event": "room_list",
            "rooms": rooms_info
        })

    async def _safe_send(self, websocket, message):
        try:
            if isinstance(message, dict):
                await websocket.send(json.dumps(message))
            else:
                await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Tentativa de enviar mensagem para conexão fechada")
            await self.remove_client_from_all_rooms(websocket)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}", exc_info=True)
            await self.remove_client_from_all_rooms(websocket)

    async def remove_client_from_all_rooms(self, websocket):
        async with self.lock:
            if websocket in self.clients:
                client_id = self.clients[websocket]['id']
                logger.info(f"Removendo cliente {client_id} de todas as salas")
                
                if websocket in self.rooms['geral']:
                    self.rooms['geral'].remove(websocket)
                
                for room_name in list(self.rooms['sessoes'].keys()):
                    if websocket in self.rooms['sessoes'][room_name]['websockets']:
                        self.rooms['sessoes'][room_name]['websockets'].remove(websocket)
                        
                self.clients.pop(websocket, None)
                logger.info(f"Cliente {client_id} removido. Total de clientes: {len(self.clients)}")

    async def monitor_sessoes_e_itens(self):
        check_interval = 2
    
        while True:
            try:
                await asyncio.sleep(check_interval)
            
                session = Session()
                try:
                    active_sessao, active_item = fetch_active_sessao_and_item(session)
                    
                    if active_sessao:
                        sessao_key = active_sessao.cod_sessao_plen
                        last_state = await self.state_manager.get_last_state(sessao_key)
                        last_active_item_id = await self.state_manager.get_last_item_for_session(sessao_key)
                        
                        current_item_id = active_item.cod_item if active_item else None
                        
                        # Item foi finalizado (ind_exibicao=0 e dat_fim preenchido)
                        if last_active_item_id and not current_item_id:
                            last_item = await self.get_item_info(session, last_active_item_id)
                            if last_item and last_item.get('dat_fim'):
                                await self._notify_item_finalized(active_sessao, last_item)
                        
                        # Item foi alterado
                        elif last_active_item_id and current_item_id and last_active_item_id != current_item_id:
                            last_item = await self.get_item_info(session, last_active_item_id)
                            if last_item:
                                await self._notify_item_removal(active_sessao, last_item)
                            if active_item:
                                await self._notify_new_item(active_sessao, active_item)
                        
                        # Novo item adicionado
                        elif not last_active_item_id and current_item_id:
                            if active_item:
                                await self._notify_new_item(active_sessao, active_item)
                        
                        # Salva estado atual
                        await self.state_manager.save_state(active_sessao, active_item)
                    else:
                        # Nenhuma sessão ativa
                        await self._notify_no_active_session()
                
                finally:
                    session.close()
                
            except Exception as e:
                logger.error(f"Erro no monitoramento: {e}")
                await asyncio.sleep(5)

    async def get_item_info(self, session, cod_item):
        try:
            stmt = select(SessaoPlenariaPainel).where(
                SessaoPlenariaPainel.cod_item == cod_item
            )
            item = session.execute(stmt).scalar_one_or_none()
            if item:
                return self.state_manager.format_item_info(item)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar item {cod_item}: {e}")
            return None

    async def _notify_item_finalized(self, sessao, item_info):
        """Notifica que um item foi finalizado (ind_exibicao=0 e dat_fim preenchido)"""
        room_name = f"sessao_{sessao.cod_sessao_plen}"
        sessao_info = self.state_manager.format_sessao_info(sessao)
        
        message = {
            "event": "item_finalized",
            "data": {
                "item": item_info,
                "sessao": sessao_info
            },
            "room": room_name
        }
        
        await self._broadcast_to_room(room_name, message)
        await self._broadcast_to_room('geral', message)

    async def _notify_item_removal(self, sessao, item_info):
        room_name = f"sessao_{sessao.cod_sessao_plen}"
        sessao_info = self.state_manager.format_sessao_info(sessao)
        
        message = {
            "event": "item_removed",
            "data": {
                "item": item_info,
                "sessao": sessao_info
            },
            "room": room_name
        }
        
        await self._broadcast_to_room(room_name, message)
        await self._broadcast_to_room('geral', message)

    async def _notify_new_item(self, sessao, item):
        room_name = f"sessao_{sessao.cod_sessao_plen}"
        item_info = self.state_manager.format_item_info(item)
        sessao_info = self.state_manager.format_sessao_info(sessao)
        
        message = {
            "event": "item_update",
            "data": {
                "item": item_info,
                "sessao": sessao_info
            },
            "room": room_name
        }
        
        await self._broadcast_to_room(room_name, message)
        await self._broadcast_to_room('geral', message)

    async def _notify_no_active_session(self):
        message = {
            "event": "no_active_session",
            "data": {
                "timestamp": datetime.now().isoformat()
            },
            "room": "geral"
        }
        await self._broadcast_to_room('geral', message)

    async def _broadcast_to_room(self, room_name, data):
        try:
            async with self.lock:
                if room_name == 'geral':
                    target_room = self.rooms['geral']
                else:
                    target_room = self.rooms['sessoes'].get(room_name, {}).get('websockets', set())
                
                json_data = json.dumps(data)
                
                disconnected = []
                for ws in list(target_room):
                    try:
                        await ws.send(json_data)
                    except (websockets.exceptions.ConnectionClosed, ConnectionError):
                        disconnected.append(ws)
                    except Exception as e:
                        logger.error(f"Erro ao enviar para cliente: {e}")
                        disconnected.append(ws)

            for ws in disconnected:
                await self.remove_client_from_all_rooms(ws)
                
        except Exception as e:
            logger.error(f"Erro no broadcast para sala {room_name}: {e}")

    async def health_monitor(self):
        while True:
            await asyncio.sleep(3600)
            stats = {
                "total_clients": sum(len(room['websockets']) for room in self.rooms['sessoes'].values()) + len(self.rooms['geral']),
                "total_rooms": len(self.rooms['sessoes']),
                "oldest_connection": min(client['connected_at'] for client in self.clients.values()) if self.clients else None,
                "memory_usage": psutil.Process().memory_info().rss / 1024 / 1024
            }
            logger.info(f"Estatísticas do servidor: {stats}")

    async def get_server_stats(self):
        return {
            "active_connections": len(self.clients),
            "active_rooms": len(self.rooms['sessoes']),
            "uptime": str(datetime.now() - self._server_start_time) if self._server_start_time else None,
            "system_load": os.getloadavg()[0] if hasattr(os, 'getloadavg') else None,
            "memory_usage": psutil.Process().memory_info().rss / 1024 / 1024
        }

    async def restart_server(self):
        if self._server_task:
            self._server_task.cancel()
            await self._server_task
        self._server_task = asyncio.create_task(self._start_server_task())

# Funções auxiliares de banco de dados
def fetch_complete_sessao(cod_sessao_plen):
    session = Session()
    try:
        stmt = (
            select(SessaoPlenaria)
            .options(
                joinedload(SessaoPlenaria.tipo_sessao_plenaria),
                joinedload(SessaoPlenaria.sessao_legislativa),
                joinedload(SessaoPlenaria.legislatura)
            )
            .where(SessaoPlenaria.cod_sessao_plen == cod_sessao_plen)
        )
        return session.execute(stmt).scalar_one_or_none()
    except Exception as e:
        logger.error(f"Erro ao buscar sessão plenária {cod_sessao_plen}: {e}")
        return None
    finally:
        session.close()

def fetch_active_sessao_and_item(session):
    try:
        stmt_painel = select(SessaoPlenariaPainel).where(
            SessaoPlenariaPainel.ind_exibicao == 1
        )
        active_item = session.execute(stmt_painel).scalar_one_or_none()
        
        active_sessao = None
        if active_item:
            stmt_sessao = (
                select(SessaoPlenaria)
                .options(
                    joinedload(SessaoPlenaria.tipo_sessao_plenaria),
                    joinedload(SessaoPlenaria.sessao_legislativa),
                    joinedload(SessaoPlenaria.legislatura)
                )
                .where(SessaoPlenaria.cod_sessao_plen == active_item.cod_sessao_plen)
            )
            active_sessao = session.execute(stmt_sessao).scalar_one_or_none()
        
        return active_sessao, active_item
    except Exception as e:
        logger.error(f"Erro ao buscar sessão e item ativos: {e}")
        return None, None

def get_active_item_for_sessao(cod_sessao_plen):
    session = Session()
    try:
        stmt = select(SessaoPlenariaPainel).where(
            SessaoPlenariaPainel.cod_sessao_plen == cod_sessao_plen,
            SessaoPlenariaPainel.ind_exibicao == 1
        )
        return session.execute(stmt).scalar_one_or_none()
    except Exception as e:
        logger.error(f"Erro ao buscar item ativo para sessão {cod_sessao_plen}: {e}")
        return None
    finally:
        session.close()

# Registra o utility
provideUtility(WebSocketServerService(), IWebSocketServerService)
