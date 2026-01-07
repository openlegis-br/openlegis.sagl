# -*- coding: utf-8 -*-
"""
Utilitários para processo integral de normas jurídicas.
"""
import os
import hashlib
import logging

logger = logging.getLogger(__name__)

# Prefixo do diretório temporário para normas
TEMP_DIR_PREFIX_NORMA = 'processo_norma_integral_'


def get_processo_norma_dir(cod_norma):
    """
    Retorna o diretório base do processo integral para uma norma jurídica.
    
    Args:
        cod_norma: Código da norma (int ou str)
        
    Returns:
        str: Caminho completo do diretório base
    """
    install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
    hash_norma = hashlib.md5(str(cod_norma).encode()).hexdigest()
    return os.path.join(install_home, f'var/tmp/{TEMP_DIR_PREFIX_NORMA}{hash_norma}')


def get_processo_norma_dir_hash(cod_norma):
    """
    Retorna apenas o hash do diretório (sem o caminho completo).
    
    Args:
        cod_norma: Código da norma (int ou str)
        
    Returns:
        str: Hash MD5 do cod_norma
    """
    return hashlib.md5(str(cod_norma).encode()).hexdigest()


def get_cache_norma_file_path(cod_norma):
    """
    Retorna o caminho do arquivo de cache para uma norma.
    O cache fica dentro do diretório do processo.
    
    Args:
        cod_norma: Código da norma (int ou str)
        
    Returns:
        str: Caminho completo do arquivo de cache
    """
    dir_base = get_processo_norma_dir(cod_norma)
    return os.path.join(dir_base, 'cache.json')


def secure_path_join(base_path: str, *paths: str) -> str:
    """
    Junta caminhos de forma segura, prevenindo path traversal.
    
    Args:
        base_path: Caminho base
        *paths: Caminhos adicionais para juntar
    
    Returns:
        str: Caminho completo normalizado e validado
    
    Raises:
        ValueError: Se houver tentativa de path traversal ou link simbólico
    """
    full_path = os.path.normpath(os.path.join(base_path, *paths))
    base = os.path.normpath(base_path)
    
    # Verifica path traversal
    if not full_path.startswith(base + os.sep) and full_path != base:
        raise ValueError(f"Path traversal attempt detected: {full_path}")
    
    # Verifica links simbólicos
    if os.path.islink(full_path):
        raise ValueError(f"Symbolic links not allowed: {full_path}")
    
    return full_path
