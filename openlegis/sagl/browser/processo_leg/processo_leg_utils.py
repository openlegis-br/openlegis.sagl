# -*- coding: utf-8 -*-
"""
Utilitários compartilhados para processo legislativo.
Centraliza lógica comum usada por processo_leg.py e pasta_digital.py
"""
import os
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Prefixo do diretório temporário
TEMP_DIR_PREFIX = 'processo_leg_integral_'


class SecurityError(Exception):
    """Exceção para problemas de segurança"""
    pass


def secure_path_join(base_path: str, *paths: str) -> str:
    """Junção segura de caminhos com verificações de segurança"""
    base = os.path.abspath(base_path)
    full_path = os.path.abspath(os.path.join(base, *paths))

    # Verificações de segurança
    if not os.path.exists(base):
        raise SecurityError(f"Base path does not exist: {base}")
    if not os.path.isdir(base):
        raise SecurityError(f"Base path is not a directory: {base}")
    if not full_path.startswith(base + os.sep):
        raise SecurityError(f"Path traversal attempt detected: {full_path}")
    if os.path.islink(full_path):
        raise SecurityError(f"Symbolic links not allowed: {full_path}")

    return full_path


def get_processo_dir(cod_materia):
    """
    Retorna o diretório base do processo legislativo para uma matéria.
    
    Args:
        cod_materia: Código da matéria (int ou str)
        
    Returns:
        str: Caminho completo do diretório base
    """
    install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
    hash_materia = hashlib.md5(str(cod_materia).encode()).hexdigest()
    return os.path.join(install_home, f'var/tmp/{TEMP_DIR_PREFIX}{hash_materia}')


def get_processo_dir_hash(cod_materia):
    """
    Retorna apenas o hash do diretório (sem o caminho completo).
    
    Args:
        cod_materia: Código da matéria (int ou str)
        
    Returns:
        str: Hash MD5 do cod_materia
    """
    return hashlib.md5(str(cod_materia).encode()).hexdigest()


def get_cache_file_path(cod_materia):
    """
    Retorna o caminho do arquivo de cache para uma matéria.
    O cache fica dentro do diretório do processo.
    
    Args:
        cod_materia: Código da matéria (int ou str)
        
    Returns:
        str: Caminho completo do arquivo de cache
    """
    dir_base = get_processo_dir(cod_materia)
    return os.path.join(dir_base, 'cache.json')


def safe_check_file(container, filename):
    """
    Verifica se um arquivo existe no container usando objectIds.
    Não carrega o objeto do ZODB, apenas verifica metadados.
    
    Args:
        container: Container Zope (ex: portal.sapl_documentos.materia)
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


def safe_check_file_with_content(container, filename):
    """
    Verifica se um arquivo existe e tem conteúdo usando objectIds e tamanho.
    Mais rigoroso que safe_check_file - verifica se o arquivo não está vazio.
    
    Args:
        container: Container Zope
        filename: Nome do arquivo a verificar
        
    Returns:
        bool: True se o arquivo existe e tem conteúdo, False caso contrário
    """
    try:
        if hasattr(container, 'objectIds'):
            obj_ids = container.objectIds()
            exists = filename in obj_ids
            if not exists and filename.lower().endswith('.pdf'):
                base = filename[:-4]
                exists = base in obj_ids
            
            if exists:
                # Verifica se o arquivo tem conteúdo (não está vazio/excluído)
                try:
                    file_obj = getattr(container, filename, None)
                    if file_obj is None and filename.lower().endswith('.pdf'):
                        file_obj = getattr(container, filename[:-4], None)
                    
                    if file_obj is not None:
                        # Verifica se tem tamanho (arquivo não vazio)
                        if hasattr(file_obj, 'get_size'):
                            size = file_obj.get_size()
                            if size is None or size == 0:
                                logger.debug(f"[safe_check_file_with_content] Arquivo {filename} existe mas está vazio (size=0)")
                                return False
                        elif hasattr(file_obj, 'data'):
                            try:
                                data = file_obj.data
                                if data is None or len(data) == 0:
                                    logger.debug(f"[safe_check_file_with_content] Arquivo {filename} existe mas está vazio (data=None ou len=0)")
                                    return False
                            except:
                                logger.debug(f"[safe_check_file_with_content] Arquivo {filename} existe mas não pode ser acessado")
                                return False
                except Exception as e:
                    logger.debug(f"[safe_check_file_with_content] Erro ao verificar conteúdo de {filename}: {e}")
                    return False
            
            return exists
        else:
            logger.debug(f"[safe_check_file_with_content] Container não tem objectIds()")
            return False
    except Exception as e:
        logger.debug(f"[safe_check_file_with_content] Erro ao verificar {filename}: {e}")
        return False


def safe_check_files_batch(container, filenames):
    """
    Verifica múltiplos arquivos de uma vez usando objectIds (sem cache).
    Mais eficiente que verificar arquivos individualmente.
    
    Args:
        container: Container Zope (ex: portal.sapl_documentos.materia)
        filenames: Lista de nomes de arquivos a verificar
        
    Returns:
        dict: Dicionário com {filename: bool} indicando se cada arquivo existe e tem tamanho > 0
    """
    results = {}
    try:
        if hasattr(container, 'objectIds'):
            # OTIMIZAÇÃO: Chama objectIds() uma única vez para todos os arquivos
            obj_ids = container.objectIds()
            obj_ids_set = set(obj_ids)  # Converte para set para busca O(1)
            
            for filename in filenames:
                exists = filename in obj_ids_set
                if not exists and filename.lower().endswith('.pdf'):
                    base = filename[:-4]
                    exists = base in obj_ids_set
                
                if exists:
                    # Verifica tamanho apenas se arquivo existe
                    try:
                        file_obj = getattr(container, filename, None)
                        if file_obj is None and filename.lower().endswith('.pdf'):
                            file_obj = getattr(container, filename[:-4], None)
                        
                        if file_obj is not None:
                            if hasattr(file_obj, 'get_size'):
                                size = file_obj.get_size()
                                if size is None or size == 0:
                                    results[filename] = False
                                    continue
                        results[filename] = True
                    except Exception as e:
                        logger.debug(f"[safe_check_files_batch] Erro ao verificar {filename}: {e}")
                        results[filename] = True  # Assume que existe se está em objectIds
                else:
                    results[filename] = False
        else:
            # Se não tem objectIds, marca todos como não existentes
            for filename in filenames:
                results[filename] = False
    except Exception as e:
        logger.debug(f"[safe_check_files_batch] Erro ao verificar arquivos: {e}")
        # Em caso de erro, marca todos como não existentes
        for filename in filenames:
            results[filename] = False
    
    return results


def get_file_size(container, filename):
    """
    Obtém o tamanho do arquivo no container sem carregar o conteúdo.
    Retorna o tamanho em bytes ou None se não for possível obter.
    
    Args:
        container: Container Zope (ex: portal.sapl_documentos.materia)
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
