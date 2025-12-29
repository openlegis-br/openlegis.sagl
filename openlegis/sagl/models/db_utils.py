# -*- coding: utf-8 -*-
"""
Database utility functions for creating SQLAlchemy engines with proper pool configuration.
This helps prevent "MySQL server has gone away" errors by:
- Using pool_pre_ping to check connections before use
- Recycling connections before they timeout
- Configuring appropriate pool sizes
"""
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool, NullPool
import logging

logger = logging.getLogger(__name__)


def create_db_engine(database_url, echo=False, use_pool=True, pool_size=5, max_overflow=10, pool_recycle=3600):
    """
    Create a SQLAlchemy engine with proper pool configuration to prevent "MySQL server has gone away" errors.
    
    Args:
        database_url: Database connection URL (e.g., mysql+pymysql://user:pass@host/db)
        echo: Whether to echo SQL statements (default: False)
        use_pool: Whether to use connection pooling (default: True). Set to False for migrations.
        pool_size: Number of connections to maintain in the pool (default: 5)
        max_overflow: Maximum number of connections to create beyond pool_size (default: 10)
        pool_recycle: Seconds before recycling a connection (default: 3600, MySQL's default wait_timeout)
    
    Returns:
        SQLAlchemy Engine instance
    """
    # Base engine arguments
    engine_args = {
        'echo': echo,
    }
    
    if use_pool:
        # Use QueuePool with proper settings
        engine_args.update({
            'poolclass': QueuePool,
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_recycle': pool_recycle,  # Recycle connections before MySQL's wait_timeout
            'pool_pre_ping': True,  # Check if connection is alive before using it
            'pool_reset_on_return': 'commit',  # Reset connection state on return
        })
    else:
        # Use NullPool for migrations or one-off operations
        engine_args.update({
            'poolclass': NullPool,
        })
    
    try:
        engine = create_engine(database_url, **engine_args)
        logger.debug(f"Engine criado com pool configurado: use_pool={use_pool}, pool_size={pool_size if use_pool else 'N/A'}")
        return engine
    except Exception as e:
        logger.error(f"Erro ao criar engine: {e}")
        raise
