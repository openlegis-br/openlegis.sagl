#!/bin/bash
# Script para inicializar Alembic no projeto SAGL
# Execute este script a partir da raiz do projeto (onde está o buildout.cfg)

# Obtém o diretório do script e sobe até a raiz do projeto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

cd "$PROJECT_ROOT" || exit 1

# Criar diretórios
mkdir -p migrations/versions

# Criar alembic.ini
cat > alembic.ini << 'EOF'
# A generic, single database configuration.

[alembic]
# path to migration scripts
script_location = migrations

# sys.path path, will be prepended to sys.path if present.
prepend_sys_path = .

version_path_separator = os

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
EOF

# Criar env.py
cat > migrations/env.py << 'ENVEOF'
# -*- coding: utf-8 -*-
"""
Alembic environment configuration for SAGL migrations
"""
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
src_dir = project_root / 'src'
sys.path.insert(0, str(src_dir))

from openlegis.sagl.models.alembic_env import *
ENVEOF

# Criar script.py.mako (template básico)
cat > migrations/script.py.mako << 'MAKOEOF'
"""${message}

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
MAKOEOF

# Ajustar permissões
chown -R zope:zope migrations alembic.ini 2>/dev/null || true
chmod 755 migrations migrations/versions
chmod 644 alembic.ini migrations/env.py migrations/script.py.mako

echo "Alembic inicializado com sucesso!"
echo ""
echo "Próximos passos:"
echo "1. Crie a migration inicial:"
echo "   bin/alembic revision --autogenerate -m 'Initial migration'"
echo "2. Aplique as migrations:"
echo "   bin/alembic upgrade head"

