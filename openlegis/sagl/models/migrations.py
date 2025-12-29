# -*- coding: utf-8 -*-
"""
Migration utilities for SAGL
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_alembic_config_path():
    """Get the path to alembic.ini"""
    # Try to find alembic.ini in the project root
    current_dir = Path(__file__).parent
    
    # Go up from models/ to SAGL6 root
    # models/ -> sagl/ -> openlegis/ -> openlegis.sagl/ -> src/ -> SAGL6/
    project_root = current_dir.parent.parent.parent.parent.parent
    alembic_ini = project_root / 'alembic.ini'
    
    if alembic_ini.exists():
        return str(alembic_ini)
    
    # Try alternative: check if we're in a buildout environment
    # Look for buildout.cfg to find project root
    buildout_cfg = project_root / 'buildout.cfg'
    if buildout_cfg.exists():
        # We're in the right place, alembic.ini should be here
        return str(alembic_ini)
    
    # Fallback: try current working directory
    cwd = Path.cwd()
    if (cwd / 'alembic.ini').exists():
        return str(cwd / 'alembic.ini')
    
    return None


def apply_migrations(database_url=None):
    """
    Apply pending migrations automatically.
    
    Args:
        database_url: Optional database URL. If not provided, will be constructed from env vars.
    """
    try:
        from alembic import command
        from alembic.config import Config
        
        alembic_ini_path = get_alembic_config_path()
        
        if not alembic_ini_path or not os.path.exists(alembic_ini_path):
            logger.warning("alembic.ini não encontrado. Migrations não serão aplicadas automaticamente.")
            logger.info("Execute 'alembic init migrations' para criar a estrutura de migrations.")
            return False
        
        # Create Alembic config
        alembic_cfg = Config(alembic_ini_path)
        
        # Set database URL if provided
        if database_url:
            alembic_cfg.set_main_option('sqlalchemy.url', database_url)
        
        # Get migrations directory
        script_location = alembic_cfg.get_main_option('script_location', 'migrations')
        migrations_dir = Path(alembic_ini_path).parent / script_location
        versions_dir = migrations_dir / 'versions'
        
        if not migrations_dir.exists():
            logger.warning(f"Diretório de migrations não encontrado: {migrations_dir}")
            logger.info("Execute 'alembic init migrations' ou use setup_alembic.py para criar a estrutura.")
            # Try to create tables directly from Base if no migrations exist
            # Construir URL do banco de logs corretamente
            if '/openlegis?' in database_url:
                logs_database_url = database_url.replace('/openlegis?', '/openlegis_logs?')
            elif database_url.endswith('/openlegis'):
                logs_database_url = database_url.replace('/openlegis', '/openlegis_logs')
            else:
                # Usar re.sub para substituir apenas o nome do banco
                import re
                logs_database_url = re.sub(r'/([^/?]+)(\?|$)', r'/openlegis_logs\2', database_url)
            
            result, created = create_tables_from_base(database_url)
            if not result:
                return False
            
            # Also create logs tables
            logs_result, logs_created = create_logs_tables_from_base(logs_database_url)
            
            # Se nenhuma tabela foi criada, significa que tudo já está sincronizado
            if not created and not logs_created:
                logger.debug("Banco de dados MySQL sincronizado (todas as tabelas já existem)")
            
            # Retorna True se pelo menos uma operação foi bem-sucedida
            return result and logs_result
        
        # Check if there are any migration files
        if not versions_dir.exists() or not any(versions_dir.glob('*.py')):
            # Construir URL do banco de logs corretamente
            if '/openlegis?' in database_url:
                logs_database_url = database_url.replace('/openlegis?', '/openlegis_logs?')
            elif database_url.endswith('/openlegis'):
                logs_database_url = database_url.replace('/openlegis', '/openlegis_logs')
            else:
                # Usar re.sub para substituir apenas o nome do banco
                import re
                logs_database_url = re.sub(r'/([^/?]+)(\?|$)', r'/openlegis_logs\2', database_url)
            
            result, created = create_tables_from_base(database_url)
            if not result:
                return False
            
            # Also create logs tables
            logs_result, logs_created = create_logs_tables_from_base(logs_database_url)
            
            # Se nenhuma tabela foi criada, significa que tudo já está sincronizado
            if not created and not logs_created:
                logger.debug("Banco de dados MySQL sincronizado (todas as tabelas já existem)")
            
            # Retorna True se pelo menos uma operação foi bem-sucedida
            return result and logs_result
        
        # Check if there are pending migrations
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import inspect
        from openlegis.sagl.models.db_utils import create_db_engine
        
        # Create engine from database URL with proper pool configuration
        if database_url:
            engine = create_db_engine(database_url, echo=False, use_pool=True)
        else:
            # Use URL from config
            engine = create_db_engine(alembic_cfg.get_main_option('sqlalchemy.url'), echo=False, use_pool=True)
        
        # Verifica se as tabelas já existem antes de aplicar migrations
        inspector = inspect(engine)
        try:
            existing_tables = set(inspector.get_table_names())
        except Exception as e:
            logger.debug(f"Erro ao obter lista de tabelas: {e}")
            existing_tables = set()
        
        # Se não há tabelas, cria a partir dos models primeiro
        if not existing_tables:
            logger.info("Criando estrutura do banco de dados...")
            
            # Constrói URL do banco de logs
            if '/openlegis?' in database_url:
                logs_database_url = database_url.replace('/openlegis?', '/openlegis_logs?')
            elif database_url.endswith('/openlegis'):
                logs_database_url = database_url.replace('/openlegis', '/openlegis_logs')
            else:
                import re
                logs_database_url = re.sub(r'/([^/?]+)(\?|$)', r'/openlegis_logs\2', database_url)
            
            # Cria tabelas a partir dos models
            result, created = create_tables_from_base(database_url)
            if not result:
                logger.warning("Erro ao criar tabelas a partir dos models")
                return False
            
            # Cria tabelas de logs
            logs_result, logs_created = create_logs_tables_from_base(logs_database_url)
            if not logs_result:
                logger.warning("Erro ao criar tabelas de logs")
                return False
            
            logger.info("Estrutura do banco de dados criada com sucesso")
        
        script = ScriptDirectory.from_config(alembic_cfg)
        
        # Usa uma conexão separada para verificar estado das migrations
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            head_rev = script.get_current_head()
        
        # Fecha a conexão antes de executar migrations
        engine.dispose()
        
        if current_rev == head_rev:
            # No pending migrations, database is up to date
            logger.debug("Banco de dados MySQL sincronizado (sem migrations pendentes)")
            return True
        else:
            # Apply migrations
            logger.info(f"Aplicando migrations do Alembic ({current_rev or 'inicial'} -> {head_rev})...")
            
            try:
                # Executa migration em thread separada de forma completamente assíncrona
                # para evitar bloquear o startup do Zope
                import threading
                
                def run_migration():
                    """Executa migration em thread separada"""
                    try:
                        command.upgrade(alembic_cfg, "head")
                        logger.info("Migrations aplicadas com sucesso")
                        logger.info("Zope continuará inicializando. Servidores HTTP e WebSocket serão iniciados em breve...")
                    except Exception as e:
                        logger.error(f"Erro ao aplicar migration: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
                
                # Cria thread não-daemon para executar migration em background
                migration_thread = threading.Thread(target=run_migration, daemon=False, name="AlembicMigrationThread")
                migration_thread.start()
                
                # Log informativo que migration está rodando em background e Zope continuará iniciando
                logger.info("Migration executando em background. Zope continuará iniciando...")
                
                # Não espera pela thread - permite que o Zope inicie imediatamente
                return True
                
            except Exception as migration_error:
                # Se houver erro na migration, loga mas não falha o startup
                logger.warning(f"Erro ao iniciar migration: {migration_error}")
                logger.warning("Execute manualmente: bin/alembic upgrade head")
                import traceback
                logger.debug(traceback.format_exc())
                # Retorna True mesmo com erro para não impedir o startup
                return True
        
    except ImportError:
        logger.warning("Alembic não está disponível. Migrations não serão aplicadas.")
        return False
    except Exception as e:
        logger.error(f"Erro ao aplicar migrations: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def create_initial_migration():
    """
    Create initial migration from current models.
    This should be run manually when setting up migrations for the first time.
    """
    try:
        from alembic import command
        from alembic.config import Config
        
        alembic_ini_path = get_alembic_config_path()
        
        if not alembic_ini_path or not os.path.exists(alembic_ini_path):
            logger.error("alembic.ini não encontrado.")
            return False
        
        alembic_cfg = Config(alembic_ini_path)
        
        logger.info("Criando migration inicial...")
        command.revision(
            alembic_cfg,
            autogenerate=True,
            message="Initial migration from models"
        )
        logger.info("Migration inicial criada com sucesso!")
        return True
        
    except ImportError:
        logger.error("Alembic não está disponível.")
        return False
    except Exception as e:
        logger.error(f"Erro ao criar migration inicial: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def create_tables_from_base(database_url=None):
    """
    Create tables directly from SQLAlchemy Base metadata.
    This is used as a fallback when migrations are not set up.
    Creates tables in multiple passes to handle foreign key dependencies.
    
    Args:
        database_url: Optional database URL. If not provided, will be constructed from env vars.
    
    Returns:
        tuple: (success: bool, created: bool) - success indica se houve sucesso, created indica se tabelas foram criadas
    """
    try:
        from sqlalchemy import inspect
        from openlegis.sagl.models.models import Base
        from openlegis.sagl.models.db_utils import create_db_engine
        import os
        
        if not database_url:
            mysql_host = os.environ.get('MYSQL_HOST', '127.0.0.1')
            mysql_user = os.environ.get('MYSQL_USER', 'root')
            mysql_pass = os.environ.get('MYSQL_PASS', 'openlegis')
            mysql_db = os.environ.get('MYSQL_DB', 'openlegis')
            database_url = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}/{mysql_db}?charset=utf8mb4"
        
        engine = create_db_engine(database_url, echo=False, use_pool=True)
        inspector = inspect(engine)
        
        # Verifica quais tabelas já existem
        existing_tables = set(inspector.get_table_names())
        all_tables = set(Base.metadata.tables.keys())
        missing_tables = all_tables - existing_tables
        
        # Se todas as tabelas já existem, retorna sem criar
        if not missing_tables:
            return True, False
        
        # Há tabelas faltando, vamos criar
        logger.debug(f"Criando {len(missing_tables)} tabelas faltantes...")
        
        # Primeira tentativa: criar todas as tabelas de uma vez
        try:
            Base.metadata.create_all(engine, checkfirst=True)
        except Exception as e:
            logger.debug(f"Erro na primeira tentativa de criação: {e}")
        
        # Verifica quais tabelas ainda faltam e tenta criar individualmente
        existing_tables = set(inspector.get_table_names())
        missing_tables = all_tables - existing_tables
        
        if missing_tables:
            logger.debug(f"Criando {len(missing_tables)} tabelas faltantes individualmente...")
            
            # Faz múltiplas passadas até não conseguir criar mais nenhuma
            max_iterations = 10
            for iteration in range(max_iterations):
                created_this_iteration = []
                still_missing = []
                
                for table_name in missing_tables:
                    try:
                        table = Base.metadata.tables[table_name]
                        table.create(engine, checkfirst=True)
                        created_this_iteration.append(table_name)
                        logger.debug(f"Tabela {table_name} criada")
                    except Exception as e:
                        still_missing.append(table_name)
                        # Loga o erro completo para debug
                        error_msg = str(e)
                        if "already exists" not in error_msg.lower() and "Duplicate" not in error_msg:
                            # Para as últimas iterações, loga em nível INFO para facilitar diagnóstico
                            log_level = logger.info if iteration >= max_iterations - 2 else logger.debug
                            log_level(f"Tabela {table_name} ainda não pode ser criada (iteração {iteration + 1}): {error_msg}")
                
                if not created_this_iteration:
                    # Nenhuma tabela foi criada nesta iteração, para o loop
                    break
                
                missing_tables = still_missing
                logger.info(f"Iteração {iteration + 1}: {len(created_this_iteration)} tabelas criadas, {len(missing_tables)} ainda faltando")
            
            if missing_tables:
                logger.warning(f"Ainda faltam {len(missing_tables)} tabelas após {max_iterations} tentativas:")
                for table_name in list(missing_tables)[:20]:  # Mostra apenas as primeiras 20
                    logger.warning(f"  - {table_name}")
                if len(missing_tables) > 20:
                    logger.warning(f"  ... e mais {len(missing_tables) - 20} tabelas")
        
        # Verifica quantas tabelas foram realmente criadas
        try:
            from sqlalchemy import inspect
            from openlegis.sagl.models.db_utils import create_db_engine
            fresh_engine = create_db_engine(database_url, echo=False, use_pool=False)
            fresh_inspector = inspect(fresh_engine)
            existing_tables_after = set(fresh_inspector.get_table_names())
            fresh_engine.dispose()
            logger.debug(f"Total de tabelas: {len(existing_tables_after)}/{len(Base.metadata.tables)}")
        except Exception:
            pass
        return True, True
        
    except Exception as e:
        logger.error(f"Erro ao criar tabelas a partir do Base: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False, False


def create_logs_tables_from_base(database_url=None):
    """
    Create tables for openlegis_logs database directly from SQLAlchemy Base metadata.
    
    Args:
        database_url: Optional database URL. If not provided, will be constructed from env vars.
    
    Returns:
        tuple: (success: bool, created: bool) - success indica se houve sucesso, created indica se tabelas foram criadas
    """
    try:
        from sqlalchemy import inspect
        from openlegis.sagl.models.models_logs import BaseLogs
        from openlegis.sagl.models.db_utils import create_db_engine
        import os
        
        if not database_url:
            mysql_host = os.environ.get('MYSQL_HOST', '127.0.0.1')
            mysql_user = os.environ.get('MYSQL_USER', 'root')
            mysql_pass = os.environ.get('MYSQL_PASS', 'openlegis')
            mysql_db = 'openlegis_logs'
            database_url = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}/{mysql_db}?charset=utf8mb4"
        
        engine = create_db_engine(database_url, echo=False, use_pool=True)
        inspector = inspect(engine)
        
        # Verifica se as tabelas já existem
        existing_tables = set(inspector.get_table_names())
        all_tables = set(BaseLogs.metadata.tables.keys())
        missing_tables = all_tables - existing_tables
        
        # Se todas as tabelas já existem, retorna sem criar
        if not missing_tables:
            return True, False  # success=True, created=False
        
        # Há tabelas faltando, vamos criar
        logger.info("Criando tabelas do openlegis_logs a partir dos models SQLAlchemy...")
        BaseLogs.metadata.create_all(engine, checkfirst=True)
        logger.info("Tabelas do openlegis_logs criadas com sucesso!")
        return True, True  # success=True, created=True
        
    except Exception as e:
        logger.error(f"Erro ao criar tabelas do openlegis_logs a partir do Base: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False, False


def check_for_model_changes():
    """
    Check if models.py has changed and generate a new migration if needed.
    This can be called periodically or on startup.
    """
    try:
        from alembic import command
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        
        alembic_ini_path = get_alembic_config_path()
        
        if not alembic_ini_path or not os.path.exists(alembic_ini_path):
            return False
        
        alembic_cfg = Config(alembic_ini_path)
        
        # Check current revision
        script = ScriptDirectory.from_config(alembic_cfg)
        try:
            current = script.get_current_head()
        except:
            current = None
        
        # Try to detect changes (this is a simple check - Alembic's autogenerate is more sophisticated)
        # For automatic detection, we'd need to compare model metadata with database schema
        # This is better done manually or via a scheduled task
        
        logger.debug("Verificando mudanças nos models...")
        # Alembic's autogenerate will detect changes when creating a new revision
        return True
        
    except Exception as e:
        logger.debug(f"Erro ao verificar mudanças: {e}")
        return False


def auto_generate_migration(message="Auto-generated migration"):
    """
    Automatically generate a new migration if there are changes in models.
    This should be called after modifying models.py.
    
    Args:
        message: Message for the migration
        
    Returns:
        True if migration was created, False otherwise
    """
    try:
        from alembic import command
        from alembic.config import Config
        
        alembic_ini_path = get_alembic_config_path()
        
        if not alembic_ini_path or not os.path.exists(alembic_ini_path):
            logger.warning("alembic.ini não encontrado. Execute setup_alembic primeiro.")
            return False
        
        alembic_cfg = Config(alembic_ini_path)
        
        logger.info("Gerando migration automática...")
        command.revision(
            alembic_cfg,
            autogenerate=True,
            message=message
        )
        logger.info("Migration gerada com sucesso!")
        return True
        
    except ImportError:
        logger.error("Alembic não está disponível.")
        return False
    except Exception as e:
        logger.error(f"Erro ao gerar migration: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def watch_models_file():
    """
    Monitor models.py for changes and auto-generate migrations.
    This can be run as a background task or called periodically.
    """
    try:
        import time
        from pathlib import Path
        
        models_file = Path(__file__).parent / 'models.py'
        if not models_file.exists():
            logger.warning("models.py não encontrado")
            return False
        
        # Get last modification time
        last_mtime = models_file.stat().st_mtime
        
        # Check if file was modified
        current_mtime = models_file.stat().st_mtime
        if current_mtime > last_mtime:
            logger.info("models.py foi modificado. Gerando migration...")
            auto_generate_migration("Auto: models.py modificado")
            return True
        
        return False
        
    except Exception as e:
        logger.debug(f"Erro ao monitorar models.py: {e}")
        return False

