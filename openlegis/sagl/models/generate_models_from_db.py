# -*- coding: utf-8 -*-
"""
Script para gerar models.py a partir de um banco de dados MySQL existente
Execute com: bin/zopepy src/openlegis.sagl/openlegis/sagl/models/generate_models_from_db.py

Lê as configurações de conexão do buildout.cfg automaticamente.
"""
import sys
import os
from pathlib import Path

# Adiciona eggs do buildout ao path (zopepy pode não ter todos os eggs)
# O caminho é relativo ao diretório de trabalho, não ao arquivo
import os
cwd = os.getcwd()
buildout_dir = Path(cwd)
eggs_dir = buildout_dir / 'eggs' / 'v5'

if eggs_dir.exists():
    # Adiciona todos os eggs ao path
    eggs_list = sorted([egg for egg in eggs_dir.iterdir() if egg.is_dir() and egg.name.endswith('.egg')], reverse=True)
    for egg in eggs_list:
        egg_str = str(egg.absolute())
        if egg_str not in sys.path:
            sys.path.insert(0, egg_str)

try:
    from sqlalchemy import MetaData, inspect
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.orm import declarative_base
except ImportError as e:
    print(f"ERRO: Não foi possível importar SQLAlchemy: {e}")
    print(f"Eggs dir: {eggs_dir}")
    print(f"Eggs encontrados: {len(list(eggs_dir.glob('*.egg'))) if eggs_dir.exists() else 0}")
    print(f"SQLAlchemy egg: {list(eggs_dir.glob('SQLAlchemy*.egg')) if eggs_dir.exists() else []}")
    raise

def read_buildout_config():
    """
    Lê as configurações MySQL do buildout.cfg
    
    O buildout.cfg permite opções duplicadas (não suportado pelo ConfigParser padrão),
    então lemos o arquivo como texto e extraímos apenas as linhas que precisamos.
    
    Returns:
        dict: Dicionário com mysql-host, mysql-user, mysql-pass, mysql-db
              ou None se não encontrar o arquivo
    """
    # Tenta encontrar buildout.cfg na raiz do projeto
    current_dir = Path(__file__).parent
    # models/ -> sagl/ -> openlegis/ -> openlegis.sagl/ -> src/ -> SAGL6/
    project_root = current_dir.parent.parent.parent.parent.parent
    buildout_cfg = project_root / 'buildout.cfg'
    
    # Se não encontrou, tenta diretório de trabalho atual
    if not buildout_cfg.exists():
        cwd = Path.cwd()
        buildout_cfg = cwd / 'buildout.cfg'
    
    if not buildout_cfg.exists():
        return None
    
    try:
        # Lê o arquivo como texto e procura pelas configurações MySQL
        # Procura na seção [buildout]
        mysql_config = {}
        in_buildout_section = False
        
        with open(buildout_cfg, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Detecta início da seção [buildout]
                if line.startswith('[buildout]'):
                    in_buildout_section = True
                    continue
                
                # Detecta início de outra seção (para de procurar)
                if line.startswith('[') and not line.startswith('[buildout'):
                    in_buildout_section = False
                    continue
                
                # Se estamos na seção [buildout], procura pelas configurações MySQL
                if in_buildout_section:
                    if line.startswith('mysql-host'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            mysql_config['mysql-host'] = parts[1].strip()
                    elif line.startswith('mysql-user'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            mysql_config['mysql-user'] = parts[1].strip()
                    elif line.startswith('mysql-pass'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            mysql_config['mysql-pass'] = parts[1].strip()
                    elif line.startswith('mysql-db'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            mysql_config['mysql-db'] = parts[1].strip()
        
        # Retorna apenas se encontrou pelo menos uma configuração
        return mysql_config if mysql_config else None
        
    except Exception as e:
        print(f"Aviso: Erro ao ler buildout.cfg: {e}", file=sys.stderr)
        return None


def generate_models(database_url, output_file=None, schema=None):
    """
    Gera models.py a partir de um banco de dados MySQL
    
    Args:
        database_url: URL de conexão do banco (ex: mysql+pymysql://root:openlegis@localhost/openlegis_painel)
        output_file: Caminho do arquivo de saída (opcional)
        schema: Nome do schema (opcional, para MySQL geralmente é o nome do banco)
    """
    try:
        print(f"Conectando ao banco de dados...")
        # Import here to avoid circular imports
        from openlegis.sagl.models.db_utils import create_db_engine
        engine = create_db_engine(database_url, echo=False, use_pool=True)
        
        # Cria metadata a partir do banco
        metadata = MetaData()
        metadata.reflect(bind=engine, schema=schema)
        
        print(f"Encontradas {len(metadata.tables)} tabelas")
        
        # Gera o código dos models
        models_code = generate_models_code(metadata, engine)
        
        # Salva em arquivo
        if output_file:
            output_path = Path(output_file)
        else:
            # Salva no mesmo diretório deste script
            current_dir = Path(__file__).parent
            output_path = current_dir / 'models_painel.py'
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(models_code)
        
        print(f"\nModels gerados com sucesso em: {output_path}")
        print(f"Total de tabelas: {len(metadata.tables)}")
        
        return output_path
        
    except Exception as e:
        print(f"ERRO ao gerar models: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_models_code(metadata, engine):
    """Gera o código Python dos models a partir do metadata"""
    
    inspector = inspect(engine)
    
    code = '''# -*- coding: utf-8 -*-
"""
Models gerados automaticamente a partir do banco de dados
Gerado em: {timestamp}
"""
from typing import List, Optional
from sqlalchemy import Column, DECIMAL, Date, DateTime, ForeignKeyConstraint, Index, Integer, TIMESTAMP, Time, text, Enum, BigInteger
from sqlalchemy.dialects.mysql import CHAR, INTEGER, LONGTEXT, MEDIMALTEXT, TEXT, TINYINT, TINYTEXT, VARCHAR, JSON, BIGINT
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()

'''.format(timestamp=__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # Ordena tabelas por dependências (tabelas sem FKs primeiro)
    tables = list(metadata.tables.values())
    sorted_tables = sort_tables_by_dependencies(tables)
    
    for table in sorted_tables:
        code += generate_table_model(table, inspector)
        code += '\n\n'
    
    return code


def sort_tables_by_dependencies(tables):
    """Ordena tabelas por dependências (topological sort)"""
    # Cria um grafo de dependências
    dependencies = {}
    for table in tables:
        deps = set()
        for fk in table.foreign_keys:
            deps.add(fk.column.table.name)
        dependencies[table.name] = deps
    
    # Ordenação topológica simples
    sorted_tables = []
    remaining = set(t.name for t in tables)
    
    while remaining:
        # Encontra tabelas sem dependências pendentes
        ready = [t for t in tables if t.name in remaining and 
                 not (dependencies.get(t.name, set()) & remaining)]
        
        if not ready:
            # Ciclo detectado ou dependência quebrada, adiciona as restantes
            ready = [t for t in tables if t.name in remaining]
        
        sorted_tables.extend(ready)
        remaining -= set(t.name for t in ready)
    
    return sorted_tables


def generate_table_model(table, inspector):
    """Gera o código Python para uma tabela"""
    
    # Nome da classe (PascalCase)
    class_name = to_pascal_case(table.name)
    
    # Obtém informações da tabela
    columns_info = inspector.get_columns(table.name)
    indexes = inspector.get_indexes(table.name)
    foreign_keys = inspector.get_foreign_keys(table.name)
    
    code = f"class {class_name}(Base):\n"
    code += f'    __tablename__ = \'{table.name}\'\n'
    
    # Table args (indexes e foreign keys)
    table_args = []
    
    # Foreign keys
    fk_constraints = []
    for fk in foreign_keys:
        fk_cols = fk['constrained_columns']
        ref_table = fk['referred_table']
        ref_cols = fk['referred_columns']
        ondelete = fk.get('options', {}).get('ondelete', 'RESTRICT')
        
        fk_constraint = f"ForeignKeyConstraint({fk_cols!r}, ['{ref_table}.{ref_cols[0]}'], ondelete='{ondelete}')"
        fk_constraints.append(fk_constraint)
    
    # Indexes
    index_list = []
    for idx in indexes:
        if idx['unique']:
            index_list.append(f"Index('{idx['name']}', {idx['column_names']!r}, unique=True)")
        else:
            index_list.append(f"Index('{idx['name']}', {idx['column_names']!r})")
    
    if fk_constraints or index_list:
        code += '    __table_args__ = (\n'
        for fk in fk_constraints:
            code += f'        {fk},\n'
        for idx in index_list:
            code += f'        {idx},\n'
        code += '    )\n'
    
    code += '\n'
    
    # Columns
    for col_info in columns_info:
        col_name = col_info['name']
        col_type = col_info['type']
        nullable = col_info.get('nullable', True)
        default = col_info.get('default')
        primary_key = col_info.get('primary_key', False)
        autoincrement = col_info.get('autoincrement', False)
        
        # Mapeia tipo SQLAlchemy
        sqlalchemy_type = map_sqlalchemy_type(col_type)
        
        # Gera mapped_column
        col_def = f"    {col_name} = mapped_column({sqlalchemy_type}"
        
        if primary_key:
            col_def += ", primary_key=True"
        if not nullable:
            col_def += ", nullable=False"
        if default is not None:
            if isinstance(default, str):
                col_def += f", server_default=text(\"{default}\")"
            else:
                col_def += f", server_default=text('{default}')"
        if autoincrement and not primary_key:
            col_def += ", autoincrement=True"
        
        col_def += ")"
        code += col_def + '\n'
    
    return code


def map_sqlalchemy_type(sql_type):
    """Mapeia tipo SQL para tipo SQLAlchemy"""
    type_str = str(sql_type)
    type_str_lower = type_str.lower()
    
    # Tipos MySQL específicos
    if 'int' in type_str_lower:
        if 'bigint' in type_str_lower:
            return 'BIGINT'
        elif 'tinyint' in type_str_lower:
            return 'TINYINT'
        elif 'smallint' in type_str_lower:
            return 'Integer'
        else:
            return 'Integer'
    elif 'varchar' in type_str_lower:
        # Extrai tamanho se houver
        import re
        match = re.search(r'varchar\((\d+)\)', type_str_lower)
        if match:
            size = int(match.group(1))
            return f'VARCHAR({size})'
        return 'VARCHAR(255)'
    elif 'char' in type_str_lower:
        import re
        match = re.search(r'char\((\d+)\)', type_str_lower)
        if match:
            size = int(match.group(1))
            return f'CHAR({size})'
        return 'CHAR(1)'
    elif 'text' in type_str_lower:
        if 'longtext' in type_str_lower:
            return 'LONGTEXT'
        elif 'mediumtext' in type_str_lower:
            return 'MEDIUMTEXT'
        elif 'tinytext' in type_str_lower:
            return 'TINYTEXT'
        else:
            return 'TEXT'
    elif 'datetime' in type_str_lower:
        return 'DateTime'
    elif 'date' in type_str_lower:
        return 'Date'
    elif 'time' in type_str_lower:
        return 'Time'
    elif 'timestamp' in type_str_lower:
        return 'TIMESTAMP'
    elif 'decimal' in type_str_lower or 'numeric' in type_str_lower:
        import re
        match = re.search(r'decimal\((\d+),(\d+)\)', type_str_lower)
        if match:
            precision = int(match.group(1))
            scale = int(match.group(2))
            return f'DECIMAL({precision}, {scale})'
        return 'DECIMAL'
    elif 'enum' in type_str_lower:
        # Extrai valores do enum
        import re
        match = re.search(r'enum\((.*?)\)', type_str_lower)
        if match:
            values = match.group(1).replace("'", "").split(',')
            values_str = ', '.join([f"'{v.strip()}'" for v in values])
            return f"Enum({values_str})"
        return 'Enum'
    elif 'json' in type_str_lower:
        return 'JSON'
    elif 'blob' in type_str_lower:
        return 'BLOB'
    else:
        return 'TEXT'  # Fallback


def to_pascal_case(snake_str):
    """Converte snake_case para PascalCase"""
    components = snake_str.split('_')
    return ''.join(x.capitalize() for x in components)


if __name__ == '__main__':
    import argparse
    
    # Lê configurações do buildout.cfg
    buildout_config = read_buildout_config()
    
    # Define defaults baseados no buildout.cfg ou valores padrão
    default_host = buildout_config.get('mysql-host', 'localhost') if buildout_config else 'localhost'
    default_user = buildout_config.get('mysql-user', 'root') if buildout_config else 'root'
    default_pass = buildout_config.get('mysql-pass', 'openlegis') if buildout_config else 'openlegis'
    default_db = buildout_config.get('mysql-db', 'openlegis') if buildout_config else 'openlegis'
    
    parser = argparse.ArgumentParser(
        description='Gera models.py a partir de um banco de dados MySQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
Valores padrão lidos do buildout.cfg:
  Host: {default_host}
  Usuário: {default_user}
  Banco: {default_db}

Exemplos:
  # Usar valores do buildout.cfg
  bin/zopepy src/openlegis.sagl/openlegis/sagl/models/generate_models_from_db.py
  
  # Sobrescrever apenas o banco
  bin/zopepy src/openlegis.sagl/openlegis/sagl/models/generate_models_from_db.py -d openlegis_logs
  
  # Sobrescrever tudo
  bin/zopepy src/openlegis.sagl/openlegis/sagl/models/generate_models_from_db.py \\
      -H localhost -u root -p senha -d outro_banco
        '''
    )
    parser.add_argument('--database', '-d', default=default_db, 
                       help=f'Nome do banco de dados (padrão: {default_db} do buildout.cfg)')
    parser.add_argument('--user', '-u', default=default_user,
                       help=f'Usuário MySQL (padrão: {default_user} do buildout.cfg)')
    parser.add_argument('--password', '-p', default=default_pass,
                       help='Senha MySQL (padrão: do buildout.cfg)')
    parser.add_argument('--host', '-H', default=default_host,
                       help=f'Host MySQL (padrão: {default_host} do buildout.cfg)')
    parser.add_argument('--output', '-o', help='Arquivo de saída (padrão: models_<database>.py)')
    
    args = parser.parse_args()
    
    database_url = f"mysql+pymysql://{args.user}:{args.password}@{args.host}/{args.database}?charset=utf8mb4"
    
    print(f"Gerando models do banco: {args.database}")
    if buildout_config:
        print(f"Configurações do buildout.cfg carregadas")
    else:
        print(f"Aviso: buildout.cfg não encontrado, usando valores padrão")
    print(f"Host: {args.host}")
    print(f"Usuário: {args.user}")
    print()
    
    result = generate_models(database_url, args.output, schema=args.database)
    
    if result:
        print(f"\n✓ Sucesso! Models gerados em: {result}")
    else:
        print("\n✗ Falha ao gerar models")
        sys.exit(1)

