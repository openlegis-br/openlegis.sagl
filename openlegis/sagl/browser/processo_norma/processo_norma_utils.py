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
    base = os.path.abspath(base_path)
    full_path = os.path.abspath(os.path.join(base, *paths))

    # Verificações de segurança
    if not os.path.exists(base):
        raise ValueError(f"Base path does not exist: {base}")
    if not os.path.isdir(base):
        raise ValueError(f"Base path is not a directory: {base}")
    if not full_path.startswith(base + os.sep):
        raise ValueError(f"Path traversal attempt detected: {full_path}")
    if os.path.islink(full_path):
        raise ValueError(f"Symbolic links not allowed: {full_path}")

    return full_path


def safe_check_file(container, filename):
    """
    Verifica se um arquivo existe no container usando objectIds.
    Não carrega o objeto do ZODB, apenas verifica metadados.
    
    Args:
        container: Container Zope (ex: portal.sapl_documentos.norma)
        filename: Nome do arquivo a verificar
        
    Returns:
        bool: True se o arquivo existe, False caso contrário
    """
    try:
        if hasattr(container, 'objectIds'):
            obj_ids = container.objectIds()
            exists = filename in obj_ids
            if not exists and filename.lower().endswith('.pdf'):
                # Tenta sem extensão .pdf
                base = filename[:-4]
                exists = base in obj_ids
            return exists
        return False
    except Exception as e:
        logger.debug(f"[safe_check_file] Erro ao verificar {filename}: {e}")
        return False


def get_file_size(container, filename):
    """
    Obtém o tamanho do arquivo no container sem carregar o conteúdo.
    Retorna o tamanho em bytes ou None se não for possível obter.
    
    Args:
        container: Container Zope (ex: portal.sapl_documentos.norma)
        filename: Nome do arquivo a verificar
        
    Returns:
        int: Tamanho do arquivo em bytes, ou None se não disponível
    """
    try:
        file_obj = getattr(container, filename, None)
        if file_obj is None and filename.lower().endswith('.pdf'):
            file_obj = getattr(container, filename[:-4], None)
        
        if file_obj is not None:
            if hasattr(file_obj, 'get_size'):
                size = file_obj.get_size()
                if size is not None and size > 0:
                    return size
    except Exception as e:
        logger.debug(f"[get_file_size] Erro ao obter tamanho de {filename}: {e}")
    return None


def get_file_info_for_hash(container, filename):
    """
    Obtém informações de um arquivo para cálculo de hash.
    Retorna lista de strings com informações (modified, size, etc).
    
    Args:
        container: Container Zope
        filename: Nome do arquivo
        
    Returns:
        list: Lista de strings com informações do arquivo
    """
    file_info = []
    try:
        file_obj = getattr(container, filename, None)
        if file_obj is None and filename.lower().endswith('.pdf'):
            file_obj = getattr(container, filename[:-4], None)
        
        if file_obj is not None:
            if hasattr(file_obj, 'modified'):
                file_info.append(f"modified:{file_obj.modified()}")
            if hasattr(file_obj, 'get_size'):
                try:
                    size = file_obj.get_size()
                    file_info.append(f"size:{size}")
                except:
                    pass
            elif hasattr(file_obj, 'data'):
                try:
                    data = file_obj.data
                    if data is not None:
                        file_info.append(f"size:{len(data)}")
                except:
                    pass
    except Exception as e:
        logger.debug(f"[get_file_info_for_hash] Erro ao obter info de {filename}: {e}")
    
    return file_info
