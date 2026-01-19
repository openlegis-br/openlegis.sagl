# -*- coding: utf-8 -*-
"""
SessionFactory padrão para todo o SAGL.

Este módulo fornece funções padronizadas para criar e gerenciar sessões SQLAlchemy
com compatibilidade garantida para SQLAlchemy 2.0 e 2.1+.

⚠️ IMPORTANTE: SQLAlchemy 2.0+ usa autobegin
============================================

No SQLAlchemy 2.0+, a Session usa autobegin - a transação é iniciada
automaticamente na primeira operação (add, flush, etc.).
O zope.sqlalchemy captura isso através do evento 'after_begin' e registra
a sessão no transaction manager automaticamente.

NÃO chame session.begin() manualmente - deixe o SQLAlchemy e zope.sqlalchemy
controlarem a transação.

Uso:
    # Para operações de ESCRITA (INSERT, UPDATE, DELETE)
    from openlegis.sagl.db_session import db_session
    
    session = db_session()
    session.add(objeto)
    session.flush()  # opcional, se precisar do PK
    # NÃO chame commit() - Zope fará isso automaticamente
    
    # Para operações de LEITURA apenas
    from openlegis.sagl.db_session import db_session_readonly
    
    with db_session_readonly() as session:
        dados = session.query(Modelo).all()
        # Sessão é fechada automaticamente ao sair do with
"""

import logging
import threading
from contextlib import contextmanager
from typing import Optional

try:
    from z3c.saconfig import named_scoped_session
    from zope.sqlalchemy import register
    from transaction import get as get_transaction
except ImportError as e:
    raise ImportError(
        f"Dependências necessárias não encontradas: {e}. "
        "Certifique-se de que z3c.saconfig e zope.sqlalchemy estão instalados."
    )

logger = logging.getLogger(__name__)

# Obtém a Session factory do z3c.saconfig
# Usa a sessão configurada no ZCML (geralmente 'minha_sessao')
_SessionFactory = named_scoped_session('minha_sessao')

# ⚠️ NÃO registramos a factory globalmente - isso causa warning:
# "Session event listen on a scoped_session requires that its creation callable is associated with the Session class"
# 
# Em vez disso, registramos cada instância de sessão individualmente quando necessário
# (como em tramitacao/config.py via get_session())
# 
# Isso é mais seguro e evita problemas com scoped_session


def _get_sqlalchemy_version() -> tuple:
    """Retorna a versão do SQLAlchemy como tupla (major, minor, patch)."""
    try:
        import sqlalchemy
        version = sqlalchemy.__version__
        parts = version.split('.')
        return tuple(int(part) for part in parts[:3])
    except Exception:
        return (0, 0, 0)


def _validate_session_transaction(session) -> bool:
    """
    Valida se a sessão tem uma transação ativa.
    
    Returns:
        True se a transação está ativa, False caso contrário
    """
    try:
        tx = session.get_transaction()
        if tx is None:
            return False
        # SQLAlchemy 2.0+ tem is_active
        if hasattr(tx, 'is_active'):
            return tx.is_active
        # Fallback para versões antigas
        return True
    except Exception as e:
        logger.warning(f"Erro ao validar transação: {e}")
        return False


def db_session():
    """
    Cria e registra uma sessão para operações de ESCRITA.
    
    ⚠️ CRÍTICO - SQLAlchemy 2.0+:
    =============================
    SQLAlchemy 2.0+ usa "autobegin" - a transação é iniciada automaticamente
    na primeira operação (add, flush, etc.). NÃO chame session.begin() manualmente.
    O zope.sqlalchemy captura isso através do evento 'after_begin' e registra
    a sessão no transaction manager automaticamente.
    
    ✅ Uso CORRETO:
        session = db_session()  # Eventos registrados, transação será iniciada automaticamente
        session.add(objeto)    # Autobegin inicia transação aqui
        session.flush()        # Opcional, para garantir IDs gerados
        # NÃO chame commit() - Zope fará isso automaticamente
        # NÃO chame rollback() - Zope fará isso em caso de erro
        # NÃO chame close() - Zope gerencia o ciclo de vida
    
    ❌ NUNCA faça:
        with db_session() as session:  # ❌ Fecha transação ao sair
        session.commit()  # ❌ Zope faz isso
        session.rollback()  # ❌ Zope faz isso
        session.close()  # ❌ Zope gerencia
        with session:  # ❌ Fecha transação
        session.begin()  # ❌ Não necessário - autobegin faz isso automaticamente
    
    Returns:
        Session: Sessão SQLAlchemy registrada no transaction manager do Zope
        
    Raises:
        RuntimeError: Se não for possível registrar a sessão no transaction manager
    """
    # Cria sessão usando a factory do z3c.saconfig
    session = _SessionFactory()
    
    # Log detalhado da criação incluindo thread info
    thread_name = threading.current_thread().name
    thread_id = threading.get_ident()
    session_id = id(session)
    sa_version = _get_sqlalchemy_version()
    in_transaction = session.in_transaction() if hasattr(session, 'in_transaction') else 'N/A'
    logger.info(
        f"db_session: Sessão criada na thread: {thread_name} (ID: {thread_id}), "
        f"session id: {session_id}, "
        f"in_transaction: {in_transaction}, "
        f"SQLAlchemy={sa_version[0]}.{sa_version[1]}"
    )
    
    # ✅ Registra eventos na sessão (zope.sqlalchemy-4.1)
    # NÃO chame session.begin() antes - deixa o zope.sqlalchemy controlar
    # Quando a transação começar (autobegin), o evento 'after_begin' será disparado
    # e registrará a sessão no transaction manager via join_transaction()
    try:
        register(session, keep_session=True)
        logger.debug(f"db_session: Sessão {id(session)} com eventos registrados")
    except ImportError:
        logger.error("db_session: zope.sqlalchemy não disponível - ERRO CRÍTICO")
        try:
            session.close()
        except:
            pass
        raise RuntimeError("zope.sqlalchemy não está disponível")
    except Exception as e:
        logger.error(f"db_session: Erro ao registrar sessão: {e}", exc_info=True)
        try:
            session.close()
        except:
            pass
        raise RuntimeError(f"Falha ao registrar sessão no transaction manager: {e}")
    
    # ⚠️ NÃO chame session.begin() manualmente
    # O SQLAlchemy 2.0+ usa autobegin - a transação será iniciada automaticamente
    # na primeira operação (add, flush, etc.)
    # O zope.sqlalchemy captura isso através do evento 'after_begin'
    
    # Retorna a sessão - NÃO fecha, NÃO commita, NÃO faz rollback
    # O Zope fará tudo isso no final do request através do transaction manager
    return session


@contextmanager
def db_session_readonly():
    """
    Context manager para operações de LEITURA apenas.
    
    Esta função cria uma sessão que é fechada automaticamente após o uso.
    Use apenas para operações de leitura (SELECT). Para escrita, use db_session().
    
    ✅ Uso CORRETO:
        with db_session_readonly() as session:
            dados = session.query(Modelo).all()
            # Sessão é fechada automaticamente ao sair do with
    
    ⚠️ NÃO use para escrita:
        with db_session_readonly() as session:  # ❌ Não registra no transaction manager
            session.add(objeto)  # ❌ Pode não funcionar corretamente
    
    Yields:
        Session: Sessão SQLAlchemy para leitura
        
    Note:
        A sessão é expurgada e fechada automaticamente ao sair do context manager.
        Isso é seguro para leitura, mas NÃO deve ser usado para operações de escrita.
    """
    session = _SessionFactory()
    try:
        logger.debug(f"db_session_readonly: Sessão criada - id={id(session)}")
        yield session
    except Exception as e:
        logger.error(f"db_session_readonly: Erro na sessão: {e}", exc_info=True)
        # Tenta expurgar antes de levantar erro
        try:
            session.expunge_all()
        except:
            pass
        raise
    finally:
        # Para leitura, expurgamos objetos e fechamos a sessão
        try:
            session.expunge_all()
        except:
            pass
        try:
            session.close()
            logger.debug(f"db_session_readonly: Sessão {id(session)} fechada")
        except:
            pass


def get_session_factory():
    """
    Retorna a factory de sessões configurada.
    
    Use apenas se precisar de controle total sobre a criação de sessões.
    Na maioria dos casos, use db_session() ou db_session_readonly().
    
    Returns:
        callable: Factory de sessões do z3c.saconfig
    """
    return _SessionFactory


def validate_sqlalchemy_compatibility() -> dict:
    """
    Valida compatibilidade com SQLAlchemy 2.0+ e retorna informações.
    
    Returns:
        dict: Informações sobre a versão do SQLAlchemy e compatibilidade
    """
    version = _get_sqlalchemy_version()
    major, minor = version[0], version[1]
    
    info = {
        'version': '.'.join(str(v) for v in version),
        'major': major,
        'minor': minor,
        'patch': version[2] if len(version) > 2 else 0,
        'is_2_0_plus': major >= 2,
        'is_2_1_plus': major > 2 or (major == 2 and minor >= 1),
        'requires_explicit_begin': major >= 2,
        'compatible': True,
        'warnings': []
    }
    
    if major < 2:
        info['warnings'].append(
            "SQLAlchemy < 2.0 detectado. Considere atualizar para 2.0+ para melhor "
            "compatibilidade com zope.sqlalchemy."
        )
    elif major == 2 and minor == 0:
        # SQLAlchemy 2.0.x - versão atual estável
        # Não há necessidade de warning, apenas informação
        pass
    
    if info['requires_explicit_begin']:
        info['notes'] = (
            "SQLAlchemy 2.0+ usa autobegin - a transação é iniciada automaticamente "
            "na primeira operação. NÃO chame session.begin() manualmente. "
            "O zope.sqlalchemy captura isso através do evento 'after_begin'."
        )
    
    return info


# Valida compatibilidade na importação
_compatibility_info = validate_sqlalchemy_compatibility()
if _compatibility_info['warnings']:
    for warning in _compatibility_info['warnings']:
        logger.warning(f"db_session: {warning}")

if _compatibility_info['requires_explicit_begin']:
    logger.info(
        f"db_session: SQLAlchemy {_compatibility_info['version']} detectado. "
        "Usando autobegin - transação iniciada automaticamente na primeira operação. "
        "zope.sqlalchemy captura via evento 'after_begin'."
    )
