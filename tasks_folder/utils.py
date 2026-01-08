from AccessControl.SecurityManagement import newSecurityManager, noSecurityManager
from Testing.makerequest import makerequest
from ZODB.POSException import ConflictError
from zope.traversing.interfaces import BeforeTraverseEvent
from zope.component.hooks import setSite
from zope.event import notify
import transaction
import Zope2
import logging
from celery import Celery, Task
from celery.signals import worker_process_init, worker_process_shutdown
import os
import pypdf
from dateutil.parser import parse
from asn1crypto import cms
import qrcode
from io import BytesIO
from functools import wraps

# CRÍTICO: Importa o app Celery de tasks.py em vez de criar um novo
# Isso garante que todos usem o MESMO app Celery que o worker está usando
# Usa lazy loading para evitar import circular
_celery_app = None

def get_celery_app():
    """Obtém o app Celery compartilhado de tasks.py (lazy loading)"""
    global _celery_app
    if _celery_app is None:
        try:
            # Tenta importar o app de tasks.py
            from tasks import app as celery_app
            _celery_app = celery_app
        except ImportError as e:
            # Fallback: se tasks.py ainda não foi carregado, cria um temporário
            # Mas isso não deve acontecer em produção quando o worker está rodando
            logging.warning(f"[utils] tasks.py ainda não carregado ({e}), criando app temporário")
            _celery_app = Celery('tasks', config_source='celeryconfig')
    return _celery_app

# Propriedade para compatibilidade com código existente que usa 'celery' diretamente
# Mas agora sempre retorna o app compartilhado de tasks.py
# NÃO inicializa no nível do módulo para evitar import circular
class CeleryProxy:
    """Proxy para o app Celery que faz lazy loading"""
    def __getattr__(self, name):
        return getattr(get_celery_app(), name)
    
    def __call__(self, *args, **kwargs):
        return get_celery_app()(*args, **kwargs)

# Cria o proxy - isso evita import circular
celery = CeleryProxy()

# Monkey patch para tratar exceções mal serializadas no backend Redis
def patch_redis_backend():
    """Aplica patch no backend Redis para tratar exceções mal serializadas"""
    try:
        from celery.backends.redis import RedisBackend
        from celery.backends.base import BaseBackend
        
        # Salva o método original se ainda não foi salvo
        if not hasattr(RedisBackend, '_original_get_task_meta_for'):
            RedisBackend._original_get_task_meta_for = RedisBackend._get_task_meta_for
        
        def safe_get_task_meta_for(self, task_id):
            """Versão segura que trata erros de decodificação"""
            try:
                return self._original_get_task_meta_for(task_id)
            except ValueError as ve:
                if "Exception information must include" in str(ve):
                    # Tarefa com exceção mal serializada - deleta e retorna dict vazio
                    logging.warning(f"[RedisBackend Patch] Tarefa {task_id} tem exceção mal serializada, deletando do Redis")
                    try:
                        # Tenta deletar a tarefa problemática do Redis
                        key = self.get_key_for_task(task_id)
                        self.client.delete(key)
                    except:
                        pass
                    # Retorna estrutura mínima para não quebrar o fluxo
                    return {
                        'status': 'FAILURE',
                        'result': None,
                        'traceback': None,
                        'children': None,
                        'date_done': None
                    }
                raise
            except Exception as e:
                # Outros erros - loga e retorna dict vazio
                logging.warning(f"[RedisBackend Patch] Erro ao obter meta da tarefa {task_id}: {e}")
                return {
                    'status': 'FAILURE',
                    'result': None,
                    'traceback': None,
                    'children': None,
                    'date_done': None
                }
        
        # Aplica o patch apenas se ainda não foi aplicado
        if RedisBackend._get_task_meta_for != safe_get_task_meta_for:
            RedisBackend._get_task_meta_for = safe_get_task_meta_for
    except Exception as e:
        logging.warning(f"[utils] Não foi possível aplicar patch no RedisBackend: {e}")

# Aplica o patch após criar a instância do Celery
patch_redis_backend()


# CRÍTICO: Worker process initialization para garantir isolamento de conexões ZODB
# Isso é necessário porque quando Celery usa prefork pool, as conexões ZODB do processo
# pai são copiadas para os processos filhos, o que pode causar corrupção de BTrees.
# Este hook garante que cada worker process tenha sua própria conexão ZODB limpa.

@worker_process_init.connect
def close_zodb_connections_on_fork(**kwargs):
    """
    Limpa estado ZODB quando um worker process é iniciado após fork.
    
    CRÍTICO: Este hook é executado DEPOIS do fork, então precisamos:
    1. Invalidar qualquer cache do Zope2 que possa ter sido copiado do processo pai
    2. Fechar todas as conexões ZODB existentes
    3. Garantir que o próximo acesso ao ZODB crie uma conexão completamente nova
    
    Isso é crítico porque:
    1. ZODB connections não são seguras para compartilhar entre processos
    2. BTrees podem ser corrompidos se acessados de múltiplos processos
    3. Cada worker process deve ter sua própria conexão ZODB isolada
    """
    logger = logging.getLogger(__name__)
    try:
        # CRÍTICO: Aborta qualquer transação pendente
        # Isso garante que não estamos usando uma transação do processo pai
        try:
            txn = transaction.get()
            if txn is not None:
                transaction.abort()
        except:
            pass
        
        # CRÍTICO: Tenta fechar todas as conexões ZODB existentes
        # Isso força o ZODB a criar uma nova conexão quando necessário
        try:
            # Tenta obter o app Zope se já foi inicializado
            app = Zope2.app()
            if hasattr(app, '_p_jar') and app._p_jar is not None:
                conn = app._p_jar
                # Fecha a conexão
                try:
                    conn.close()
                    logger.debug("[worker_process_init] Conexão ZODB fechada")
                except:
                    pass
                
                # Se a conexão tem um DB, tenta fechar todas as conexões do DB
                if hasattr(conn, 'db') and conn.db is not None:
                    db = conn.db
                    # Fecha todas as conexões abertas no DB
                    try:
                        for conn_id, db_conn in list(db._connections.items()):
                            try:
                                if hasattr(db_conn, 'close'):
                                    db_conn.close()
                            except:
                                pass
                        logger.debug("[worker_process_init] Todas as conexões do DB fechadas")
                    except:
                        pass
        except Exception as close_err:
            # Se não conseguir fechar, continua - pode ser que não haja conexão ainda
            logger.debug(f"[worker_process_init] Nenhuma conexão ZODB para fechar: {close_err}")
        
        # CRÍTICO: Tenta invalidar o cache do Zope2
        # Isso garante que Zope2.app() retornará uma nova instância
        try:
            # Tenta limpar qualquer cache interno do Zope2
            if hasattr(Zope2, '_app'):
                delattr(Zope2, '_app')
                logger.debug("[worker_process_init] Cache do Zope2.app() invalidado")
        except:
            pass
        
        # Limpa estado do Zope2
        # Isso garante que cada worker process começa com estado limpo
        try:
            setSite(None)
            noSecurityManager()
        except:
            pass
        
        # CRÍTICO: Aborta transação novamente após fechar conexões
        try:
            txn = transaction.get()
            if txn is not None:
                transaction.abort()
        except:
            pass
        
        logger.info("[worker_process_init] Worker process inicializado com estado ZODB limpo e conexões fechadas")
    except Exception as e:
        logger.warning(f"[worker_process_init] Erro ao limpar estado ZODB: {e}", exc_info=True)


@worker_process_shutdown.connect
def close_zodb_connections_on_shutdown(**kwargs):
    """
    Fecha todas as conexões ZODB quando um worker process é encerrado.
    """
    logger = logging.getLogger(__name__)
    try:
        # Aborta qualquer transação pendente
        try:
            txn = transaction.get()
            if txn is not None:
                transaction.abort()
        except:
            pass
        
        # Fecha conexões ZODB
        try:
            app = Zope2.app()
            if hasattr(app, '_p_jar') and app._p_jar is not None:
                conn = app._p_jar
                try:
                    conn.close()
                except:
                    pass
        except:
            pass
        
        # Limpa estado
        try:
            setSite(None)
            noSecurityManager()
        except:
            pass
        
        logger.info("[worker_process_shutdown] Conexões ZODB fechadas no worker process")
    except Exception as e:
        logger.debug(f"[worker_process_shutdown] Erro ao fechar conexões ZODB: {e}")


# CRÍTICO: Monkey patch para HTTPRequest do Zope adicionar suporte a SESSION
# Isso é necessário porque scripts PythonScript podem acessar HTTPRequest do Zope
# através do Acquisition framework, e esse HTTPRequest não tem SESSION
_httprequest_original_getattr = None
_httprequest_patched = False

def patch_httprequest_for_session():
    """
    Faz monkey patch temporário no HTTPRequest do Zope para adicionar suporte a SESSION
    quando estamos em contexto Celery.
    
    Returns:
        Função para restaurar o patch original
    """
    global _httprequest_original_getattr, _httprequest_patched
    
    try:
        from ZPublisher.HTTPRequest import HTTPRequest
        
        # Se já foi aplicado, não aplica novamente
        if _httprequest_patched:
            return lambda: None
        
        # Salva o método original
        if _httprequest_original_getattr is None:
            _httprequest_original_getattr = HTTPRequest.__getattr__
        
        def patched_getattr(self, name):
            # CRÍTICO: Se for SESSION, sempre retorna MockSession em contexto Celery
            # Não tenta o método original primeiro para evitar AttributeError
            if name == 'SESSION':
                # Verifica se estamos em uma tarefa Celery
                import os
                celery_context = (
                    'CELERY_WORKER' in os.environ or 
                    'CELERY_TASK_ID' in os.environ or
                    hasattr(self, '_celery_mock_session')
                )
                
                if celery_context:
                    # Cria um mock de SESSION se ainda não existe
                    if not hasattr(self, '_celery_mock_session'):
                        self._celery_mock_session = MockSession()
                    return self._celery_mock_session
            
            # Para outros atributos, tenta o método original
            try:
                return _httprequest_original_getattr(self, name)
            except AttributeError as e:
                # Se for SESSION e não detectou contexto Celery antes, tenta novamente
                if name == 'SESSION':
                    # Sempre retorna MockSession em contexto Celery (fallback)
                    if not hasattr(self, '_celery_mock_session'):
                        self._celery_mock_session = MockSession()
                    return self._celery_mock_session
                raise
        
        # Aplica o patch
        HTTPRequest.__getattr__ = patched_getattr
        _httprequest_patched = True
        logging.debug("[zope_task] Monkey patch aplicado ao HTTPRequest para SESSION")
        
        # Retorna uma função para restaurar
        def restore_patch():
            global _httprequest_patched
            if _httprequest_patched and _httprequest_original_getattr is not None:
                HTTPRequest.__getattr__ = _httprequest_original_getattr
                _httprequest_patched = False
                logging.debug("[zope_task] Monkey patch restaurado no HTTPRequest")
        
        return restore_patch
    except Exception as e:
        logging.warning(f"[zope_task] Erro ao aplicar monkey patch no HTTPRequest: {e}")
        return lambda: None


def resolve_site(site, logger=None):
    """
    Resolve um site do Zope, removendo wrappers RequestContainer e garantindo acesso a zsql.
    
    Esta função é crítica para tarefas assíncronas do Celery, onde o site pode vir
    envolvido em RequestContainer do Acquisition framework.
    
    Args:
        site: Objeto site do Zope (pode ser RequestContainer)
        logger: Logger opcional para mensagens de debug
    
    Returns:
        Objeto site real (não RequestContainer) com zsql acessível
    
    Raises:
        Exception: Se não conseguir resolver um site válido
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    from Acquisition import aq_inner, aq_base
    site_real = site
    
    # Passo 1: Tenta remover wrappers do Acquisition
    if 'RequestContainer' in str(type(site)):
        logger.debug(f"[resolve_site] Site é RequestContainer, tentando aq_inner...")
        try:
            site_inner = aq_inner(site)
            if 'RequestContainer' not in str(type(site_inner)):
                site_real = site_inner
                logger.debug(f"[resolve_site] Site resolvido via aq_inner")
            else:
                # Tenta aq_base
                try:
                    site_base = aq_base(site_inner)
                    if 'RequestContainer' not in str(type(site_base)):
                        site_real = site_base
                        logger.debug(f"[resolve_site] Site resolvido via aq_base")
                except Exception as e:
                    logger.debug(f"[resolve_site] Erro ao usar aq_base: {e}")
        except Exception as e:
            logger.debug(f"[resolve_site] Erro ao usar aq_inner: {e}")
    
    # Passo 2: Se ainda for RequestContainer, tenta obter via app diretamente
    if 'RequestContainer' in str(type(site_real)):
        logger.debug(f"[resolve_site] Ainda é RequestContainer, tentando via app.sagl...")
        try:
            app = makerequest(Zope2.app())
            if hasattr(app, 'sagl'):
                app_sagl = getattr(app, 'sagl')
                # Remove wrappers do Acquisition
                try:
                    app_sagl_inner = aq_inner(app_sagl)
                    if 'RequestContainer' not in str(type(app_sagl_inner)):
                        app_sagl = app_sagl_inner
                except Exception as e:
                    logger.debug(f"[resolve_site] Erro ao remover wrapper de app.sagl: {e}")
                
                site_real = app_sagl
                logger.info(f"[resolve_site] Site resolvido via app.sagl")
        except Exception as e:
            logger.warning(f"[resolve_site] Erro ao obter site via app: {e}")
    
    # Passo 3: Verificação final
    if 'RequestContainer' in str(type(site_real)):
        error_msg = f"Site ainda é RequestContainer após todas as tentativas. Type: {type(site_real)}"
        logger.error(f"[resolve_site] {error_msg}")
        raise Exception(error_msg)
    
    # Passo 4: Garante que zsql esteja acessível
    try:
        zsql_test = getattr(site_real, 'zsql', None)
        if zsql_test is None:
            # Tenta através de portal_skins.sk_sagl
            if hasattr(site_real, 'portal_skins'):
                portal_skins = getattr(site_real, 'portal_skins')
                if hasattr(portal_skins, 'sk_sagl'):
                    sk_sagl = getattr(portal_skins, 'sk_sagl')
                    zsql_test = getattr(sk_sagl, 'zsql', None)
                    if zsql_test is not None:
                        # Tenta adicionar zsql diretamente ao site
                        try:
                            setattr(site_real, 'zsql', zsql_test)
                            logger.debug(f"[resolve_site] zsql adicionado ao site via sk_sagl")
                        except Exception as e:
                            logger.debug(f"[resolve_site] Não foi possível adicionar zsql ao site: {e}")
    except Exception as e:
        logger.debug(f"[resolve_site] Erro ao verificar zsql: {e}")
    
    return site_real


class MockResponse:
    """
    Mock de RESPONSE para uso em tarefas assíncronas do Celery.
    
    Fornece uma interface mínima compatível com o que PythonScripts e templates
    do Zope esperam de um objeto RESPONSE.
    """
    # Permite acesso sem verificação de segurança do AccessControl
    __allow_access_to_unprotected_subobjects__ = 1
    
    def __init__(self):
        self.status = 200
        self.headers = {}
    
    def setStatus(self, status):
        """Define o status HTTP"""
        self.status = status
    
    def setHeader(self, name, value):
        """Define um header HTTP"""
        self.headers[name] = value
    
    def getStatus(self):
        """Retorna o status HTTP"""
        return self.status
    
    def getHeader(self, name, default=None):
        """Retorna um header HTTP"""
        return self.headers.get(name, default)


class MockSession:
    """
    Mock de SESSION para uso em tarefas assíncronas do Celery.
    Compatível com o que PythonScripts esperam de um objeto SESSION do Zope.
    """
    __allow_access_to_unprotected_subobjects__ = 1
    
    def __init__(self):
        self._data = {}
    
    def get(self, key, default=None):
        """Compatível com SESSION.get()"""
        return self._data.get(key, default)
    
    def __getitem__(self, key):
        """Compatível com SESSION[key]"""
        return self._data[key]
    
    def __setitem__(self, key, value):
        """Compatível com SESSION[key] = value"""
        self._data[key] = value
    
    def __contains__(self, key):
        """Compatível com 'key in SESSION'"""
        return key in self._data
    
    def __getattr__(self, name):
        """Permite acesso dinâmico a atributos"""
        if name in self._data:
            return self._data[name]
        return None
    
    def __str__(self):
        """Retorna representação string do SESSION"""
        return str(self._data)
    
    def __repr__(self):
        """Retorna representação do SESSION"""
        return f"MockSession({self._data})"


class MockRequest:
    """
    Mock de REQUEST para uso em tarefas assíncronas do Celery.
    
    Fornece uma interface mínima compatível com o que PythonScripts e templates
    do Zope esperam de um objeto REQUEST.
    """
    # Permite acesso sem verificação de segurança do AccessControl
    __allow_access_to_unprotected_subobjects__ = 1
    
    def __init__(self, form_data=None, url='', environ=None):
        """
        Args:
            form_data: Dicionário com dados do formulário (padrão: {})
            url: URL da requisição (padrão: '')
            environ: Dicionário com variáveis de ambiente (padrão: {})
        """
        self.form = form_data if form_data is not None else {}
        self.environ = environ if environ is not None else {}
        self.URL = url
        # Usa MockResponse em vez de type() para evitar problemas de segurança
        self.RESPONSE = MockResponse()
        # Atributos comuns que podem ser acessados
        # SESSION é um objeto MockSession (compatível com o que o Zope espera)
        self.SESSION = MockSession()
        # other contém informações adicionais como traverse_subpath
        self.other = {'traverse_subpath': []}
        # Atributos adicionais comuns do REQUEST do Zope
        self.PARENTS = []
        self.steps = []
        self.debug = False
        self.method = 'GET'
        self.ACTUAL_URL = url
        self.PATH_INFO = ''
        self.QUERY_STRING = ''
        self.AUTHENTICATED_USER = None
        self.AUTHENTICATION_PATH = ''
        self.cookies = {}
        self._auth = ''
    
    def get(self, key, default=None):
        """Compatível com REQUEST.get()"""
        return self.form.get(key, default)
    
    def __getitem__(self, key):
        """Compatível com acesso via []"""
        return self.form.get(key)
    
    def __contains__(self, key):
        """Compatível com 'in' operator"""
        return key in self.form
    
    def __getattr__(self, name):
        """
        Permite acesso a atributos dinamicamente, como o Zope HTTPRequest faz.
        Isso garante que atributos como SESSION sejam acessíveis mesmo quando
        acessados via __getattr__ do Zope.
        """
        # Se for um atributo que já existe, retorna normalmente
        if name in self.__dict__:
            return self.__dict__[name]
        
        # Atributos comuns do REQUEST do Zope que podem ser acessados
        common_attrs = {
            'SESSION': self.SESSION,
            'RESPONSE': self.RESPONSE,
            'form': self.form,
            'environ': self.environ,
            'other': self.other,
            'PARENTS': self.PARENTS,
            'steps': self.steps,
            'debug': self.debug,
            'URL': self.URL,
            'ACTUAL_URL': self.ACTUAL_URL,
            'method': self.method,
            'PATH_INFO': self.PATH_INFO,
            'QUERY_STRING': self.QUERY_STRING,
            'AUTHENTICATED_USER': self.AUTHENTICATED_USER,
            'AUTHENTICATION_PATH': self.AUTHENTICATION_PATH,
            'cookies': self.cookies,
            '_auth': self._auth,
        }
        
        if name in common_attrs:
            return common_attrs[name]
        
        # Para outros atributos, retorna None ou levanta AttributeError
        # Isso simula o comportamento do HTTPRequest do Zope
        raise AttributeError(name)
    
    def setVirtualRoot(self, path):
        """Método necessário para compatibilidade com Zope"""
        pass
    
    def traverse(self, path):
        """Método necessário para compatibilidade com Zope"""
        return None
    
    def __str__(self):
        return f"<MockRequest URL={self.URL}>"
    
    def __repr__(self):
        return f"MockRequest(url={self.URL}, form={self.form})"


class ContextWrapper:
    """
    Wrapper para context de views Zope que fornece acesso a zsql e outros atributos.
    
    Este wrapper garante que self.context.zsql funcione mesmo que zsql esteja
    em portal_skins.sk_sagl, e remove wrappers RequestContainer do Acquisition.
    
    Uso típico:
        context_wrapper = ContextWrapper(site)
        view = SomeView(context_wrapper, request)
    """
    def __init__(self, site_obj, logger=None):
        """
        Args:
            site_obj: Objeto site do Zope (pode ser RequestContainer)
            logger: Logger opcional para mensagens de debug
        """
        if logger is None:
            logger = logging.getLogger(__name__)
        
        self._logger = logger
        # Garante que site_obj não seja RequestContainer
        from Acquisition import aq_inner, aq_base
        self._site = site_obj
        
        # Tenta obter o site real removendo wrappers
        try:
            if 'RequestContainer' in str(type(site_obj)):
                site_inner = aq_inner(site_obj)
                if 'RequestContainer' not in str(type(site_inner)):
                    self._site = site_inner
                else:
                    try:
                        site_base = aq_base(site_inner)
                        if 'RequestContainer' not in str(type(site_base)):
                            self._site = site_base
                    except Exception as e:
                        logger.debug(f"[ContextWrapper] Erro ao usar aq_base: {e}", exc_info=True)
        except Exception as e:
            logger.debug(f"[ContextWrapper] Erro ao usar aq_inner: {e}", exc_info=True)
        
        # Obtém sk_sagl para acesso rápido a zsql
        try:
            if hasattr(self._site, 'portal_skins'):
                portal_skins = getattr(self._site, 'portal_skins')
                if hasattr(portal_skins, 'sk_sagl'):
                    self._sk_sagl = getattr(portal_skins, 'sk_sagl')
                else:
                    self._sk_sagl = None
            else:
                self._sk_sagl = None
        except Exception as e:
            logger.debug(f"[ContextWrapper] Erro ao obter sk_sagl: {e}", exc_info=True)
            self._sk_sagl = None
        
        # Obtém zsql diretamente se disponível
        try:
            if hasattr(self._site, 'zsql'):
                self._zsql = getattr(self._site, 'zsql')
            elif self._sk_sagl is not None and hasattr(self._sk_sagl, 'zsql'):
                self._zsql = getattr(self._sk_sagl, 'zsql')
            else:
                self._zsql = None
        except Exception as e:
            logger.debug(f"[ContextWrapper] Erro ao obter zsql: {e}", exc_info=True)
            self._zsql = None
    
    def __getattr__(self, name):
        """Fornece acesso a atributos do site, com fallback para sk_sagl"""
        # Importa POSKeyError apenas quando necessário
        try:
            from ZODB.POSException import POSKeyError
        except ImportError:
            POSKeyError = Exception  # Fallback se não disponível
        
        # Se for zsql, retorna diretamente ou de sk_sagl
        if name == 'zsql':
            if self._zsql is not None:
                return self._zsql
            elif self._sk_sagl is not None:
                try:
                    return getattr(self._sk_sagl, 'zsql')
                except (POSKeyError, AttributeError) as e:
                    self._logger.debug(f"[ContextWrapper] Erro ao obter zsql de sk_sagl: {e}", exc_info=True)
                    # Tenta obter do site diretamente como último recurso
                    return getattr(self._site, 'zsql')
            else:
                # Tenta obter do site diretamente
                return getattr(self._site, 'zsql')
        # Para outros atributos, tenta obter do site
        try:
            return getattr(self._site, name)
        except (POSKeyError, AttributeError) as e:
            # Se for POSKeyError, loga mas não propaga (objeto pode ter sido deletado)
            if isinstance(e, POSKeyError):
                self._logger.debug(f"[ContextWrapper] POSKeyError ao acessar '{name}' do site (objeto pode ter sido deletado): {e}", exc_info=True)
            # Se não encontrar no site, tenta em sk_sagl
            if self._sk_sagl is not None:
                try:
                    return getattr(self._sk_sagl, name)
                except (POSKeyError, AttributeError) as e2:
                    if isinstance(e2, POSKeyError):
                        self._logger.debug(f"[ContextWrapper] POSKeyError ao acessar '{name}' de sk_sagl: {e2}", exc_info=True)
                    # Se ambos falharem, propaga o erro original
                    if isinstance(e, AttributeError):
                        raise
                    # Para POSKeyError, levanta AttributeError para manter compatibilidade
                    raise AttributeError(f"'{type(self._site).__name__}' object has no attribute '{name}' (POSKeyError: {e})")
            # Se não tem sk_sagl e é AttributeError, propaga
            if isinstance(e, AttributeError):
                raise
            # Para POSKeyError, levanta AttributeError
            raise AttributeError(f"'{type(self._site).__name__}' object has no attribute '{name}' (POSKeyError: {e})")
    
    def __setattr__(self, name, value):
        """Define atributos no site subjacente"""
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            setattr(self._site, name, value)

class ZopeContext:
    """
    Context manager para gerenciar contexto Zope em tarefas Celery.
    
    Simplifica o setup e cleanup do ambiente Zope, incluindo:
    - Configuração do ambiente Zope
    - Criação de REQUEST mock com SESSION
    - Setup de segurança
    - Gerenciamento de transações
    """
    
    def __init__(self, site_path='sagl', task_id=None, logger=None):
        """
        Inicializa ZopeContext.
        
        IMPORTANTE: No Zope, sapl_documentos sempre está em /sagl/sapl_documentos,
        então o site_path padrão é sempre 'sagl'.
        """
        self.site_path = site_path.strip().strip('/') if site_path else 'sagl'
        self.task_id = task_id or 'UNKNOWN'
        self.logger = logger or logging.getLogger(__name__)
        self.app = None
        self.site = None
        self.request = None
        self._restore_patch = None
        self._original_cwd = None
    
    def __enter__(self):
        """Configura o ambiente Zope"""
        try:
            # Aplica monkey patch para HTTPRequest
            self._restore_patch = patch_httprequest_for_session()
            
            # Configura ambiente Zope
            self._setup_zope_environment()
            
            # Obtém app Zope
            self.app = self._get_zope_app()
            
            # Resolve site
            self.site = self._resolve_site(self.app)
            
            # Cria e injeta REQUEST mock
            self.request = self._create_and_inject_request(self.site)
            
            # Configura segurança
            self._setup_security(self.app)
            
            return self
        except Exception as e:
            self.logger.error(f"[ZopeContext] Erro ao configurar contexto: {e}", exc_info=True)
            if self._restore_patch:
                self._restore_patch()
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Limpa o ambiente Zope e fecha conexões ZODB"""
        try:
            # Aborta qualquer transação pendente antes de fechar conexões
            try:
                txn = transaction.get()
                if txn is not None:
                    transaction.abort()
            except:
                pass
            
            if self._restore_patch:
                self._restore_patch()
            
            noSecurityManager()
            setSite(None)
            
            # CRÍTICO: Fecha a conexão ZODB de forma segura
            # Não fecha completamente para evitar problemas com outros workers,
            # mas garante que a transação está abortada
            if self.app and hasattr(self.app, '_p_jar'):
                try:
                    conn = self.app._p_jar
                    # Não fecha a conexão completamente, apenas aborta a transação
                    # A conexão será reutilizada pelo próximo uso
                    # conn.close()  # Comentado para evitar problemas com reutilização
                except:
                    pass
            
            if self._original_cwd:
                try:
                    os.chdir(self._original_cwd)
                except:
                    pass
        except Exception as e:
            self.logger.warning(f"[ZopeContext] Erro ao limpar contexto: {e}", exc_info=True)
    
    def _setup_zope_environment(self):
        """Configura variáveis de ambiente e diretório de trabalho"""
        # Salva diretório atual
        self._original_cwd = os.getcwd()
        
        # Encontra buildout_dir e zope.conf
        buildout_dir = os.environ.get('BUILDOUT_DIR', '/var/openlegis/SAGL6')
        zope_config = os.path.join(buildout_dir, 'parts', 'instance', 'etc', 'zope.conf')
        
        if not os.path.exists(zope_config):
            # Tenta caminhos alternativos
            current_dir = os.getcwd()
            rel_config = os.path.abspath(
                os.path.join(current_dir, '..', '..', '..', 'parts', 'instance', 'etc', 'zope.conf')
            )
            if os.path.exists(rel_config):
                zope_config = rel_config
                buildout_dir = os.path.dirname(os.path.dirname(os.path.dirname(rel_config)))
            else:
                raise Exception(f"zope.conf não encontrado. Tentou: {zope_config}, {rel_config}")
        
        os.chdir(buildout_dir)
        os.environ['ZOPE_CONFIG'] = zope_config
        self.logger.info(f"[ZopeContext] ZOPE_CONFIG: {zope_config}")
    
    def _get_zope_app(self):
        """
        Obtém e configura app Zope com conexão ZODB completamente isolada.
        
        CRÍTICO: Este método garante que cada worker process tenha sua própria
        conexão ZODB isolada, evitando corrupção de BTrees quando múltiplos
        processos acessam o mesmo objeto ZODB.
        
        A estratégia é:
        1. Abortar todas as transações pendentes
        2. Fechar qualquer conexão ZODB existente
        3. Invalidar cache do Zope2 para forçar nova instância
        4. Obter uma nova conexão ZODB completamente isolada
        5. Garantir que o app está registrado na conexão
        """
        try:
            # CRÍTICO: Aborta qualquer transação pendente antes de começar
            # Isso garante que não estamos usando uma transação corrompida do processo pai
            # E também invalida qualquer cache de objetos persistentes
            try:
                txn = transaction.get()
                if txn is not None:
                    transaction.abort()
            except:
                pass
            
            # CRÍTICO: Fecha qualquer conexão ZODB existente antes de obter nova
            # Isso garante que não estamos reutilizando uma conexão do processo pai
            try:
                # Tenta obter app atual (se existir)
                try:
                    old_app = Zope2.app()
                    if hasattr(old_app, '_p_jar') and old_app._p_jar is not None:
                        old_conn = old_app._p_jar
                        # Fecha a conexão
                        try:
                            old_conn.close()
                            self.logger.debug("[ZopeContext] Conexão ZODB existente fechada")
                        except:
                            pass
                except:
                    pass
                
                # Tenta invalidar cache do Zope2 APENAS se bobo_application estiver inicializado
                # Não invalidamos se bobo_application for None, pois pode precisar ser inicializado
                try:
                    if hasattr(Zope2, 'bobo_application') and Zope2.bobo_application is not None:
                        if hasattr(Zope2, '_app'):
                            delattr(Zope2, '_app')
                            self.logger.debug("[ZopeContext] Cache do Zope2.app() invalidado")
                except:
                    pass
            except Exception as e:
                self.logger.debug(f"[ZopeContext] Erro ao fechar conexões existentes: {e}")
            
            # CRÍTICO: Aborta transação novamente após fechar conexões
            try:
                txn = transaction.get()
                if txn is not None:
                    transaction.abort()
            except:
                pass
            
            # CRÍTICO: Verifica se Zope2 foi inicializado (bobo_application não é None)
            # Se não estiver, verifica se há _app cacheado que podemos usar ou tenta inicializar
            if not hasattr(Zope2, 'bobo_application') or Zope2.bobo_application is None:
                # Primeiro, verifica se há um _app cacheado que podemos usar diretamente
                if hasattr(Zope2, '_app') and Zope2._app is not None:
                    # Se há _app cacheado, configura bobo_application para retornar esse app
                    self.logger.debug("[ZopeContext] bobo_application é None, mas _app está cacheado, configurando bobo_application")
                    cached_app = Zope2._app
                    # Cria uma função wrapper que retorna o app cacheado
                    def _get_app_from_cache(*args, **kw):
                        return cached_app
                    Zope2.bobo_application = _get_app_from_cache
                    zope_app = Zope2.app()
                else:
                    # Se não há _app cacheado, tenta inicializar via startup
                    # Mas captura o erro "already in databases" que indica inicialização parcial
                    try:
                        from Zope2.App import startup
                        startup.startup()
                        self.logger.debug("[ZopeContext] Zope2 inicializado via startup()")
                        zope_app = Zope2.app()
                    except ValueError as ve:
                        # Se o erro é "already in databases", significa que os bancos já estão registrados
                        # mas bobo_application não foi configurado. Isso indica um estado inconsistente
                        # que geralmente ocorre quando o Zope2 foi parcialmente inicializado.
                        # A melhor solução é reiniciar o worker Celery.
                        if "already in databases" in str(ve):
                            self.logger.error(
                                "[ZopeContext] Zope2 em estado inconsistente: bancos registrados mas bobo_application é None. "
                                "Isso geralmente indica que o Zope2 foi parcialmente inicializado. "
                                "Reinicie o worker Celery completamente."
                            )
                            raise Exception(
                                "Zope2 está em estado inconsistente: bancos de dados já registrados mas bobo_application é None. "
                                "Isso geralmente ocorre quando o Zope2 foi parcialmente inicializado em um processo anterior. "
                                "SOLUÇÃO: Reinicie o worker Celery completamente (pare e inicie novamente) para limpar o estado e permitir inicialização completa do Zope2."
                            ) from ve
                        raise
                    except Exception as startup_err:
                        self.logger.error(f"[ZopeContext] Erro ao inicializar Zope2: {startup_err}", exc_info=True)
                        raise Exception(
                            f"Zope2 não foi inicializado e não foi possível inicializar automaticamente. "
                            f"Erro: {startup_err}. Verifique a configuração do Zope2 e do worker Celery."
                        ) from startup_err
            else:
                # CRÍTICO: Obtém o app Zope (agora com conexão completamente nova)
                # Zope2.app() deve criar uma nova conexão se a anterior foi fechada
                try:
                    zope_app = Zope2.app()
                except (TypeError, AttributeError) as e:
                    # Se bobo_application ainda é None após tentativa de inicialização
                    if "'NoneType' object is not callable" in str(e) or "bobo_application" in str(e):
                        raise Exception(
                            "Zope2 não foi inicializado corretamente. "
                            "bobo_application ainda é None após tentativa de inicialização. "
                            "Verifique a configuração do Zope2 e do worker Celery."
                        ) from e
                    raise
            
            # CRÍTICO: Verifica se o app tem uma conexão válida
            # Se não tiver ou estiver fechada, obtém uma nova
            if hasattr(zope_app, '_p_jar') and zope_app._p_jar is not None:
                conn = zope_app._p_jar
                # Verifica se a conexão está fechada ou inválida
                if hasattr(conn, 'closed') and conn.closed:
                    self.logger.warning("[ZopeContext] Conexão ZODB estava fechada, forçando nova conexão")
                    # Se estiver fechada, obtém uma nova conexão do DB
                    if hasattr(conn, 'db') and conn.db is not None:
                        db = conn.db
                        new_conn = db.open()
                        zope_app._p_jar = new_conn
                        conn = new_conn
            
            app = makerequest(zope_app)
            self.logger.info(f"[ZopeContext] App Zope obtido: {type(app)}")
            
            # CRÍTICO: Garante que o app está registrado na conexão ZODB
            # Isso é necessário para que o app seja reconhecido pela conexão
            try:
                if hasattr(app, '_p_jar') and app._p_jar is not None:
                    conn = app._p_jar
                    # Registra o app na conexão se necessário
                    if hasattr(app, '_p_oid') and app._p_oid is None:
                        try:
                            conn.register(app)
                            self.logger.debug("[ZopeContext] App registrado na conexão ZODB")
                        except Exception as e:
                            self.logger.debug(f"[ZopeContext] Erro ao registrar app: {e}")
            except Exception as e:
                self.logger.debug(f"[ZopeContext] Erro ao configurar conexão ZODB: {e}")
            
            # CRÍTICO: Inicia uma nova transação limpa
            # Isso garante que não estamos usando uma transação do processo pai
            # E também invalida qualquer cache de objetos persistentes da transação anterior
            transaction.begin()
            
            # CRÍTICO: Força sincronização da conexão ZODB
            # Isso garante que estamos usando uma conexão completamente nova
            try:
                if hasattr(app, '_p_jar') and app._p_jar is not None:
                    conn = app._p_jar
                    # Sincroniza a conexão para garantir que está limpa
                    if hasattr(conn, 'sync'):
                        conn.sync()
            except Exception as e:
                self.logger.debug(f"[ZopeContext] Erro ao sincronizar conexão ZODB: {e}")
            
            return app
        except Exception as e:
            self.logger.error(f"[ZopeContext] Erro ao obter app Zope: {e}", exc_info=True)
            raise
    
    def _resolve_site(self, app):
        """
        Resolve site do Zope usando função existente resolve_site.
        
        CRÍTICO: Garante que estamos obtendo uma referência completamente nova
        ao site, não uma referência de cache de uma transação anterior.
        
        Detecta automaticamente se o sistema roda em domínio direto (sem /sagl/)
        ou com subpath (/sagl/), tentando primeiro o path fornecido e depois o root.
        
        IMPORTANTE: Mesmo quando o Apache usa VirtualHostRoot apontando para /sagl/,
        o objeto 'sagl' deve existir no root do Zope para que o traverse funcione
        corretamente quando executado via código Python (sem requisição HTTP).
        """
        # CRÍTICO: Aborta e reinicia transação para garantir objetos frescos
        # Isso invalida qualquer cache de objetos persistentes
        try:
            txn = transaction.get()
            if txn is not None:
                transaction.abort()
            transaction.begin()
        except Exception as e:
            self.logger.debug(f"[ZopeContext] Erro ao reiniciar transação antes de resolver site: {e}")
        
        # Tenta obter o site através de traverse
        # IMPORTANTE: No Zope, sapl_documentos sempre está em /sagl/sapl_documentos,
        # então o site sempre deve estar em /sagl/ (ou o path fornecido)
        site = None
        traverse_path = self.site_path or 'sagl'  # Garante que sempre há um path (padrão 'sagl')
        
        # Tenta usar o path fornecido (ou 'sagl' como padrão)
        if traverse_path:
            try:
                # Converte string para lista de paths se necessário
                if isinstance(traverse_path, str):
                    # Remove barras e divide por '/'
                    path_parts = [p for p in traverse_path.strip('/').split('/') if p]
                    if path_parts:
                        # IMPORTANTE: Com VirtualHostRoot, o objeto 'sagl' deve existir no root
                        # Faça traverse para o path especificado
                        site = app.unrestrictedTraverse(path_parts)
                        
                        # Verifica se o objeto obtido parece ser um site válido
                        if not (hasattr(site, 'portal_skins') or hasattr(site, 'zsql') or hasattr(site, 'sapl_documentos')):
                            # O objeto obtido não parece ser um site, tenta verificar se há um site dentro dele
                            self.logger.warning(f"[ZopeContext] Objeto obtido via '{traverse_path}' não parece ser um site, verificando...")
                            # Se não é um site válido, tenta usar o root
                            if hasattr(app, traverse_path):
                                # O path existe, mas pode não ser o site diretamente
                                # Continua usando o objeto obtido, o resolve_site pode ajudar
                                pass
                            else:
                                raise KeyError(f"Path '{traverse_path}' não encontrado")
                    else:
                        # Se path está vazio após limpar, usa root
                        site = app
                else:
                    # Se já é uma lista ou tupla, usa diretamente
                    site = app.unrestrictedTraverse(traverse_path)
                    
                    # Verifica se o objeto obtido parece ser um site válido
                    if not (hasattr(site, 'portal_skins') or hasattr(site, 'zsql') or hasattr(site, 'sapl_documentos')):
                        self.logger.warning(f"[ZopeContext] Objeto obtido via path não parece ser um site válido")
                        
                self.logger.debug(f"[ZopeContext] Site obtido via path '{traverse_path}': {type(site)}")
                
            except (KeyError, AttributeError) as e:
                # Se falhar (path não existe via traverse), tenta outras formas de acessar
                self.logger.info(f"[ZopeContext] Path '{traverse_path}' não encontrado via traverse ({e}), tentando alternativas...")
                
                # IMPORTANTE: No Zope, sapl_documentos sempre está em /sagl/sapl_documentos,
                # então 'sagl' DEVE existir. Tenta acessar diretamente via getattr
                if isinstance(traverse_path, str) and '/' not in traverse_path.strip('/'):
                    try:
                        if hasattr(app, traverse_path):
                            site = getattr(app, traverse_path)
                            self.logger.info(f"[ZopeContext] Encontrado '{traverse_path}' via getattr direto em app")
                            # Verifica se é um site válido (deve ter sapl_documentos se for /sagl/)
                            if hasattr(site, 'portal_skins') or hasattr(site, 'zsql') or hasattr(site, 'sapl_documentos'):
                                self.logger.info(f"[ZopeContext] Objeto '{traverse_path}' é um site válido")
                            else:
                                # Se não tem sapl_documentos mas deveria ter, há um problema
                                if traverse_path == 'sagl':
                                    error_msg = f"Objeto 'sagl' encontrado mas não tem sapl_documentos/portal_skins/zsql. Isso não deveria acontecer!"
                                    self.logger.error(f"[ZopeContext] {error_msg}")
                                    raise Exception(error_msg)
                                self.logger.warning(f"[ZopeContext] Objeto '{traverse_path}' não parece ser um site válido")
                                site = app
                        else:
                            # Path não existe - isso é um erro se for 'sagl'
                            if traverse_path == 'sagl':
                                error_msg = f"Objeto 'sagl' não encontrado no root do Zope! sapl_documentos sempre deve estar em /sagl/sapl_documentos"
                                self.logger.error(f"[ZopeContext] {error_msg}")
                                raise Exception(error_msg)
                            # Para outros paths, tenta usar root
                            site = app
                            self.logger.warning(f"[ZopeContext] Path '{traverse_path}' não existe, tentando root como fallback")
                    except Exception as attr_err:
                        if traverse_path == 'sagl':
                            # Se é 'sagl' e falhou, isso é crítico
                            error_msg = f"Erro crítico ao acessar 'sagl': {attr_err}. sapl_documentos sempre deve estar em /sagl/sapl_documentos"
                            self.logger.error(f"[ZopeContext] {error_msg}")
                            raise Exception(error_msg) from attr_err
                        self.logger.debug(f"[ZopeContext] Erro ao acessar '{traverse_path}' via getattr: {attr_err}")
                        site = app
                else:
                    # Path complexo - se for '/sagl' ou similar, tenta usar 'sagl' simples
                    if 'sagl' in str(traverse_path):
                        try:
                            site = getattr(app, 'sagl')
                            self.logger.info(f"[ZopeContext] Path complexo contém 'sagl', usando app.sagl diretamente")
                        except Exception:
                            error_msg = f"Path '{traverse_path}' contém 'sagl' mas não foi possível acessar app.sagl"
                            self.logger.error(f"[ZopeContext] {error_msg}")
                            raise Exception(error_msg)
                    else:
                        site = app
                        self.logger.warning(f"[ZopeContext] Usando root como fallback para path complexo '{traverse_path}'")
                
                # Verifica se o site obtido parece ser válido
                if hasattr(site, 'portal_skins') or hasattr(site, 'zsql') or hasattr(site, 'sapl_documentos'):
                    self.logger.info(f"[ZopeContext] Site selecionado é válido (tem portal_skins, zsql ou sapl_documentos)")
                else:
                    if traverse_path == 'sagl':
                        error_msg = "Site 'sagl' não tem portal_skins/zsql/sapl_documentos - configuração incorreta do Zope!"
                        self.logger.error(f"[ZopeContext] {error_msg}")
                        raise Exception(error_msg)
                    self.logger.warning(f"[ZopeContext] Site selecionado não tem portal_skins/zsql/sapl_documentos, mas usando mesmo assim")
        else:
            # Se site_path está vazio, usa 'sagl' como padrão (não root)
            # IMPORTANTE: sapl_documentos sempre está em /sagl/sapl_documentos
            try:
                site = getattr(app, 'sagl')
                self.logger.info(f"[ZopeContext] site_path vazio, usando 'sagl' como padrão (sapl_documentos está em /sagl/sapl_documentos)")
            except AttributeError:
                error_msg = "site_path vazio e objeto 'sagl' não encontrado no root do Zope! sapl_documentos sempre deve estar em /sagl/sapl_documentos"
                self.logger.error(f"[ZopeContext] {error_msg}")
                raise Exception(error_msg)
        
        # Resolve o site removendo wrappers
        resolved_site = resolve_site(site, self.logger)
        
        return resolved_site
    
    def _create_and_inject_request(self, site):
        """Cria e injeta REQUEST mock com SESSION"""
        request = MockRequest()
        
        # Injeta no site
        try:
            from Acquisition import aq_base
            base = aq_base(site)
            if hasattr(base, 'REQUEST'):
                delattr(base, 'REQUEST')
            setattr(base, 'REQUEST', request)
        except Exception as e:
            self.logger.warning(f"[ZopeContext] Erro ao injetar REQUEST no site: {e}")
            try:
                setattr(site, 'REQUEST', request)
            except:
                pass
        
        # Notifica evento BeforeTraverse
        try:
            notify(BeforeTraverseEvent(site, request))
        except Exception as e:
            self.logger.warning(f"[ZopeContext] Erro ao notificar BeforeTraverseEvent: {e}")
        
        # Injeta REQUEST em sapl_documentos e modelo_proposicao se existirem
        self._inject_request_in_objects(site, request)
        
        return request
    
    def _inject_request_in_objects(self, site, request):
        """Injeta REQUEST em objetos relacionados (sapl_documentos, modelo_proposicao)"""
        try:
            from Acquisition import aq_base
            
            if hasattr(site, 'sapl_documentos'):
                sapl_doc = site.sapl_documentos
                if sapl_doc:
                    base = aq_base(sapl_doc)
                    if not hasattr(base, '__parent__') or getattr(base, '__parent__', None) != site:
                        try:
                            setattr(base, '__parent__', site)
                        except:
                            pass
                    
                    if hasattr(base, 'REQUEST'):
                        delattr(base, 'REQUEST')
                    setattr(base, 'REQUEST', request)
                    
                    # Injeta em modelo_proposicao se existir
                    if hasattr(sapl_doc, 'modelo_proposicao'):
                        modelo_prop = sapl_doc.modelo_proposicao
                        if modelo_prop:
                            base_mp = aq_base(modelo_prop)
                            if not hasattr(base_mp, '__parent__') or getattr(base_mp, '__parent__', None) != sapl_doc:
                                try:
                                    setattr(base_mp, '__parent__', sapl_doc)
                                except:
                                    pass
                            
                            if hasattr(base_mp, 'REQUEST'):
                                delattr(base_mp, 'REQUEST')
                            setattr(base_mp, 'REQUEST', request)
        except Exception as e:
            self.logger.warning(f"[ZopeContext] Erro ao injetar REQUEST em objetos: {e}")
    
    def _setup_security(self, app):
        """Configura segurança do Zope"""
        try:
            user = app.acl_users.getUserById('admin')
            newSecurityManager(None, user)
            setSite(self.site)
        except Exception as e:
            self.logger.warning(f"[ZopeContext] Erro ao configurar segurança: {e}")
    
    def commit(self):
        """Faz commit da transação"""
        try:
            txn = transaction.get()
            if txn is not None and not txn.isDoomed():
                transaction.commit()
            else:
                self.logger.warning("[ZopeContext] Transação está doomed ou None")
        except Exception as e:
            self.logger.error(f"[ZopeContext] Erro ao fazer commit: {e}", exc_info=True)
            transaction.abort()
            raise
    
    def abort(self):
        """Aborta a transação"""
        try:
            transaction.abort()
        except Exception as e:
            self.logger.warning(f"[ZopeContext] Erro ao abortar transação: {e}")


class AfterCommitTask(Task):
    """Tarefa que só será enfileirada após o commit da transação ZODB."""
    abstract = True

    def apply_async(self, args=None, kwargs=None, **options):
        # CRÍTICO: Sempre cria o resultado assíncrono primeiro para garantir que temos um task_id
        # Isso é necessário porque o código que chama apply_async espera um objeto com 'id'
        try:
            # Tenta obter a transação, mas não falha se não houver
            txn = None
            try:
                txn = transaction.get()
                logging.debug(f"[AfterCommitTask] Transação obtida: {txn}, isDoomed: {txn.isDoomed() if txn else 'N/A'}")
            except Exception as txn_err:
                logging.debug(f"[AfterCommitTask] Não foi possível obter transação: {txn_err}")
            
            # Sempre cria o resultado assíncrono primeiro
            # CRÍTICO: Usa Task.apply_async diretamente em vez de super() para evitar problemas de resolução
            logging.debug(f"[AfterCommitTask] Chamando Task.apply_async() diretamente com args={args}, kwargs={kwargs}")
            async_result = None
            try:
                # Chama o método da classe pai diretamente
                async_result = Task.apply_async(self, args=args, kwargs=kwargs, **options)
                logging.debug(f"[AfterCommitTask] Task.apply_async() retornou: {type(async_result)}, valor: {async_result}")
            except Exception as super_err:
                logging.error(f"[AfterCommitTask] Erro ao chamar Task.apply_async(): {super_err}", exc_info=True)
                # Se Task.apply_async() falhar, tenta usar delay() como fallback
                try:
                    logging.warning(f"[AfterCommitTask] Tentando Task.delay() como fallback")
                    async_result = Task.delay(self, *args or [], **kwargs or {})
                    logging.debug(f"[AfterCommitTask] Task.delay() retornou: {type(async_result)}, valor: {async_result}")
                except Exception as delay_err:
                    logging.error(f"[AfterCommitTask] Task.delay() também falhou: {delay_err}", exc_info=True)
                    raise Exception(f"Falha ao criar tarefa: apply_async={super_err}, delay={delay_err}")
            
            # CRÍTICO: Verifica se o resultado é None ANTES de tentar acessar qualquer atributo
            if async_result is None:
                error_msg = "[AfterCommitTask] Task.apply_async() retornou None! Verifique se o Celery está configurado corretamente."
                logging.error(error_msg)
                # Tenta obter mais informações sobre o problema
                if hasattr(self, 'app'):
                    logging.error(f"[AfterCommitTask] Celery app broker: {getattr(self.app, 'broker_connection', None)}")
                raise Exception("Falha ao criar tarefa assíncrona: apply_async retornou None")
            
            # Verifica se o resultado é válido
            if async_result is None:
                error_msg = "[AfterCommitTask] super().apply_async() retornou None! Verifique se o Celery está configurado corretamente."
                logging.error(error_msg)
                # Tenta obter mais informações sobre o problema
                if hasattr(self, 'app'):
                    logging.error(f"[AfterCommitTask] Celery app broker: {getattr(self.app, 'broker_connection', None)}")
                raise Exception("Falha ao criar tarefa assíncrona: apply_async retornou None")
            
            # Verifica se tem id
            if not hasattr(async_result, 'id'):
                logging.error(f"[AfterCommitTask] async_result não tem atributo 'id'. Tipo: {type(async_result)}, Atributos: {[a for a in dir(async_result) if not a.startswith('_')][:10]}")
                raise Exception("Falha ao criar tarefa assíncrona: resultado não tem 'id'")
            
            task_id = getattr(async_result, 'id', None)
            if task_id is None:
                logging.error(f"[AfterCommitTask] async_result.id é None. Tipo: {type(async_result)}")
                raise Exception("Falha ao criar tarefa assíncrona: resultado não tem 'id' válido")
            
            logging.debug(f"[AfterCommitTask] Tarefa criada com sucesso. task_id: {task_id}")
            
            # Se há uma transação ativa e não está doomed, registra o hook
            if txn is not None and not txn.isDoomed():
                try:
                    # Registra o hook para executar após o commit
                    # O hook não faz nada agora, mas mantém a compatibilidade
                    txn.addAfterCommitHook(
                        self._run_after_commit,
                        args=[args, kwargs, options]
                    )
                    logging.debug(f"[AfterCommitTask] Hook de commit registrado")
                except Exception as e:
                    logging.warning(f"[AfterCommitTask] Falha ao registrar hook: {e}", exc_info=True)
                    # Se falhar ao registrar hook, a tarefa já foi enfileirada, então está OK

            # Sempre retorna o resultado assíncrono com task_id
            return async_result
        except Exception as e:
            logging.error(f"[AfterCommitTask] Erro em apply_async: {e}", exc_info=True)
            raise

    def _run_after_commit(self, success, args, kwargs, options):
        # NOTA: A tarefa já foi enfileirada em apply_async, então não precisamos executá-la novamente
        # O hook foi mantido apenas para compatibilidade, mas não faz nada
        # A tarefa já foi enfileirada e tem um task_id válido
        if not success:
            logging.warning("[AfterCommitTask] Transação abortada. Tarefa pode ter sido enfileirada antes do abort.")

def zope_task(**task_kw):
    """
    Decorador para tarefas Celery que precisam de contexto Zope.
    
    Configura automaticamente o ambiente Zope, cria REQUEST mock com SESSION,
    gerencia transações e limpa recursos após a execução.
    """
    task_kw.setdefault("bind", True)

    def wrap(func):
        @wraps(func)
        def task_instance(self, *args, **kw):
            task_id = getattr(self.request, 'id', 'UNKNOWN')
            # IMPORTANTE: No Zope, sapl_documentos sempre está em /sagl/sapl_documentos,
            # então o site_path padrão é sempre 'sagl'
            site_path = kw.pop('site_path', 'sagl')
            site_path = site_path.strip().strip('/') if site_path else 'sagl'
            cod_proposicao = kw.get('cod_proposicao', None)
            cod_materia = kw.get('cod_materia', None)
            cod_info = f" | cod_proposicao={cod_proposicao}" if cod_proposicao else (f" | cod_materia={cod_materia}" if cod_materia else "")
            
            retry_count = getattr(self.request, 'retries', 0)
            logger = logging.getLogger(__name__)
            
            if retry_count > 0:
                logger.warning(f"[zope_task] Retry #{retry_count}{cod_info} para {func.__name__}")
            
            try:
                # CRÍTICO: Aborta qualquer transação pendente ANTES de entrar no ZopeContext
                # Isso garante que não estamos usando transações do processo pai
                try:
                    txn = transaction.get()
                    if txn is not None:
                        transaction.abort()
                except:
                    pass
                
                # Usa ZopeContext como context manager para simplificar setup/cleanup
                logger.info(f"[zope_task] ===== INICIANDO EXECUÇÃO DA FUNÇÃO {func.__name__} =====")
                logger.info(f"[zope_task] task_id={task_id}, site_path={site_path}{cod_info}")
                
                with ZopeContext(site_path=site_path, task_id=task_id, logger=logger) as ctx:
                    logger.info(f"[zope_task] ZopeContext criado com sucesso, site obtido: {type(ctx.site)}")
                    
                    # CRÍTICO: Aborta transação atual e inicia nova limpa
                    # Isso garante que estamos usando uma transação completamente isolada
                    try:
                        txn = transaction.get()
                        if txn is not None:
                            transaction.abort()
                        transaction.begin()
                    except Exception as e:
                        logger.debug(f"[zope_task] Erro ao limpar transação: {e}")
                        transaction.begin()
                    
                    logger.info(f"[zope_task] Transação limpa, chamando função {func.__name__}...")
                    
                    # Executa a função com o site
                    result = func(self, ctx.site, *args, **kw)
                    
                    logger.info(f"[zope_task] Função {func.__name__} executada com sucesso, fazendo commit...")
                    
                    # Faz commit da transação
                    ctx.commit()
                    
                    logger.info(f"[zope_task] ===== FUNÇÃO {func.__name__} CONCLUÍDA COM SUCESSO =====")
                    
                    return result
            
            except ConflictError as e:
                logger.warning(f"[zope_task] Conflito de transação{cod_info}: {e}", exc_info=True)

                if retry_count < 3:
                    countdown = 5 + (retry_count * 5)
                    self.app.send_task(
                        self.name,
                        args=args,
                        kwargs=kw,
                        countdown=countdown,
                        retry=True,
                        retry_policy={
                            'max_retries': 3,
                            'interval_start': 10,
                            'interval_step': 10,
                            'interval_max': 60,
                        }
                    )
                    return None
                else:
                    logger.error(f"[zope_task] Número máximo de retries atingido para {self.name}{cod_info}")
                    # Converte para exceção serializável
                    raise Exception(f"ConflictError: {str(e)}")

            except Exception as e:
                try:
                    transaction.abort()
                except:
                    pass
                logger.error(f"[zope_task] ===== ERRO DURANTE EXECUÇÃO DA TAREFA =====")
                logger.error(f"[zope_task] Função: {func.__name__}{cod_info}")
                logger.error(f"[zope_task] Erro: {type(e).__name__}: {e}", exc_info=True)
                # Converte exceção para uma exceção serializável
                raise Exception(f"{type(e).__name__}: {str(e)}")

            # O cleanup é feito automaticamente pelo ZopeContext.__exit__

        # Se o nome da tarefa não foi especificado, usa o nome padrão do módulo.função
        # Isso garante que o nome seja consistente com o que o Celery espera
        if 'name' not in task_kw:
            # Usa o nome do módulo e função como nome da tarefa
            # O Celery espera o formato: módulo.função
            module_name = func.__module__
            func_name = func.__name__
            task_kw['name'] = f'{module_name}.{func_name}'
        
        task_name = task_kw.get('name', f'{func.__module__}.{func.__name__}')
        
        # CRÍTICO: Usa o app Celery compartilhado de tasks.py
        # Tenta importar diretamente para evitar problemas com proxy
        try:
            from tasks import app as celery_app
        except ImportError:
            # Fallback: usa get_celery_app()
            celery_app = get_celery_app()
        
        
        try:
            registered_task = celery_app.task(base=AfterCommitTask, **task_kw)(task_instance)
            # Verifica se a tarefa foi registrada
            if hasattr(registered_task, 'name'):
                actual_name = registered_task.name
                # Verifica se está no registro do Celery
                if actual_name not in celery_app.tasks:
                    logging.warning(f"[zope_task] Tarefa {actual_name} NÃO encontrada no registro do Celery!")
                    logging.warning(f"[zope_task] Tarefas registradas: {list(celery_app.tasks.keys())[:10]}")
            else:
                logging.warning(f"[zope_task] Tarefa registrada mas sem atributo 'name'")
            return registered_task
        except Exception as e:
            logging.error(f"[zope_task] ERRO ao registrar tarefa {func.__name__} do módulo {func.__module__}: {e}", exc_info=True)
            raise

    return wrap

def make_qrcode(text):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    fp = BytesIO()
    img.save(fp, "PNG")
    return fp

def get_signatures(fileStream):
    try:
        reader = pypdf.PdfReader(fileStream)
        fields = reader.get_fields()
        signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
        lst_signers = []
        for v in signature_field_values:
            try:
                if '/M' in v:
                    signing_time = parse(v['/M'][2:].strip("'").replace("'", ":"))
                else:
                    signing_time = None
                if '/Name' in v:
                    name, cpf = v['/Name'].split(':')[0:2]
                else:
                    name, cpf = None, None
                raw_signature_data = v['/Contents']
                for attrdict in parse_signatures(raw_signature_data):
                    dic = {
                        'signer_name': name or attrdict.get('signer'),
                        'signer_cpf': cpf or attrdict.get('cpf'),
                        'signing_time': str(signing_time) or attrdict.get('signing_time'),
                        'signer_certificate': attrdict.get('oname')
                    }
                    lst_signers.append(dic)
            except Exception as e:
                logging.error(f"Erro ao processar assinatura: {e}")
                continue
        lst_signers.sort(key=lambda dic: dic['signing_time'], reverse=True)
        return lst_signers
    except Exception as e:
        logging.error(f"Erro ao obter assinaturas: {e}")
        return None

def parse_signatures(raw_signature_data):
    try:
        info = cms.ContentInfo.load(raw_signature_data)
        signed_data = info['content']
        certificates = signed_data['certificates']
        signer_infos = signed_data['signer_infos'][0]
        signers = []
        for signer_info in signer_infos:
            for cert in certificates:
                cert = cert.native['tbs_certificate']
                issuer = cert['issuer']
                subject = cert['subject']
                oname = issuer.get('organization_name', '')
                lista = subject['common_name'].split(':')
                signer = lista[0]
                cpf = lista[1] if len(lista) > 1 else ''
                dic = {
                    'type': subject.get('organization_name', ''),
                    'signer': signer,
                    'cpf': cpf,
                    'oname': oname
                }
        signers.append(dic)
        return signers
    except Exception as e:
        logging.error(f"Erro ao analisar assinaturas: {e}")
        return None
