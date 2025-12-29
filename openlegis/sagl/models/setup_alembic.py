# -*- coding: utf-8 -*-
"""
Script para inicializar Alembic e criar a estrutura de migrations
"""
import os
import sys
import shutil
from pathlib import Path


def setup_alembic():
    """Inicializa a estrutura do Alembic para migrations"""
    try:
        # Determina o diretório base (raiz do projeto SAGL6)
        current_file = Path(__file__)
        # Vai de models/setup_alembic.py até SAGL6/
        project_root = current_file.parent.parent.parent.parent.parent
        
        alembic_ini = project_root / 'alembic.ini'
        migrations_dir = project_root / 'migrations'
        versions_dir = migrations_dir / 'versions'
        env_py = migrations_dir / 'env.py'
        script_py_mako = migrations_dir / 'script.py.mako'
        
        # Se já existe, não recria
        if alembic_ini.exists() and migrations_dir.exists() and env_py.exists():
            print("Alembic já está configurado.")
            print(f"  alembic.ini: {alembic_ini}")
            print(f"  migrations/: {migrations_dir}")
            return True
        
        # Cria diretórios
        migrations_dir.mkdir(exist_ok=True)
        versions_dir.mkdir(exist_ok=True)
        print(f"Criado: {migrations_dir}")
        
        # Cria alembic.ini a partir do template
        template_path = current_file.parent / 'alembic.ini.template'
        if template_path.exists():
            shutil.copy(template_path, alembic_ini)
            print(f"Criado: {alembic_ini}")
        else:
            # Cria alembic.ini básico
            alembic_ini_content = """[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =

[logger_alembic]
level = INFO
handlers =

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
            with open(alembic_ini, 'w') as f:
                f.write(alembic_ini_content)
            print(f"Criado: {alembic_ini}")
        
        # Cria env.py
        env_py_content = """# -*- coding: utf-8 -*-
\"\"\"
Alembic environment configuration for SAGL migrations
\"\"\"
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
src_dir = project_root / 'src'
sys.path.insert(0, str(src_dir))

from openlegis.sagl.models.alembic_env import *
"""
        with open(env_py, 'w') as f:
            f.write(env_py_content)
        print(f"Criado: {env_py}")
        
        # Cria script.py.mako (template básico)
        if not script_py_mako.exists():
            script_mako_content = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
            with open(script_py_mako, 'w') as f:
                f.write(script_mako_content)
            print(f"Criado: {script_py_mako}")
        
        print("\nAlembic configurado com sucesso!")
        print("\nPróximos passos:")
        print("1. Crie a migration inicial:")
        print(f"   cd {project_root}")
        print("   bin/alembic revision --autogenerate -m 'Initial migration'")
        print("2. Aplique as migrations:")
        print("   bin/alembic upgrade head")
        print("\nOu as migrations serão aplicadas automaticamente no próximo startup do Zope.")
        
        return True
        
    except ImportError:
        print("ERRO: Alembic não está instalado.")
        print("Execute: bin/buildout")
        return False
    except Exception as e:
        print(f"ERRO ao configurar Alembic: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    setup_alembic()

