# -*- coding: utf-8 -*-
"""Utilitários e classes base para tramitação"""

import logging
import hashlib
import time
from typing import Optional, Dict, Any, List, Callable
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Sistema de Cache Simples
# ---------------------------------------------------------------------
class SimpleCache:
    """
    Cache simples em memória com TTL (Time To Live).
    Útil para consultas frequentes que não mudam frequentemente.
    """
    
    def __init__(self, default_ttl: int = 300):
        """
        Args:
            default_ttl: TTL padrão em segundos (5 minutos)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache se ainda válido"""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if time.time() > entry['expires']:
            # Expirou, remove
            del self._cache[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Armazena valor no cache com TTL"""
        ttl = ttl or self.default_ttl
        self._cache[key] = {
            'value': value,
            'expires': time.time() + ttl
        }
    
    def clear(self, pattern: Optional[str] = None):
        """
        Limpa cache.
        
        Args:
            pattern: Se fornecido, limpa apenas chaves que começam com pattern
        """
        if pattern:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()
    
    def invalidate(self, key: str):
        """Invalida uma chave específica"""
        if key in self._cache:
            del self._cache[key]


# Instância global do cache
_cache = SimpleCache(default_ttl=300)  # 5 minutos padrão


def cached(key_prefix: str, ttl: int = 300):
    """
    Decorator para cachear resultados de funções.
    
    Args:
        key_prefix: Prefixo para a chave do cache
        ttl: TTL em segundos
    
    Exemplo:
        @cached('unidades_usuario', ttl=600)
        def obter_unidades(cod_usuario):
            # ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Gera chave do cache baseada nos argumentos
            key_parts = [key_prefix]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5('|'.join(key_parts).encode()).hexdigest()
            full_key = f"{key_prefix}:{cache_key}"
            
            # Tenta obter do cache
            cached_value = _cache.get(full_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {full_key}")
                return cached_value
            
            # Não está no cache, executa função
            logger.debug(f"Cache miss: {full_key}")
            result = func(*args, **kwargs)
            
            # Armazena no cache
            _cache.set(full_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# ---------------------------------------------------------------------
# Validações Robustas de Segurança
# ---------------------------------------------------------------------
class SecurityValidationError(Exception):
    """Exceção para erros de validação de segurança"""
    pass


def validar_codigo_inteiro_seguro(valor: Any, nome_campo: str, min_valor: int = 1, max_valor: int = 2147483647) -> int:
    """
    Valida e converte código para inteiro com verificações de segurança.
    
    Args:
        valor: Valor a validar
        nome_campo: Nome do campo para mensagens de erro
        min_valor: Valor mínimo permitido
        max_valor: Valor máximo permitido
    
    Returns:
        Código validado como inteiro
    
    Raises:
        SecurityValidationError: Se validação falhar
    """
    if valor is None:
        raise SecurityValidationError(f'{nome_campo} não fornecido')
    
    # Converte para string primeiro para validar formato
    if isinstance(valor, str):
        valor_str = valor.strip()
        if not valor_str:
            raise SecurityValidationError(f'{nome_campo} não pode ser vazio')
        
        # Verifica se contém apenas dígitos (proteção contra SQL injection)
        if not valor_str.isdigit():
            raise SecurityValidationError(f'{nome_campo} deve ser um número válido')
        
        try:
            valor = int(valor_str)
        except ValueError:
            raise SecurityValidationError(f'{nome_campo} deve ser um número válido')
    
    if not isinstance(valor, int):
        try:
            valor = int(valor)
        except (ValueError, TypeError):
            raise SecurityValidationError(f'{nome_campo} deve ser um número válido')
    
    # Verifica limites
    if valor < min_valor:
        raise SecurityValidationError(f'{nome_campo} deve ser maior ou igual a {min_valor}')
    
    if valor > max_valor:
        raise SecurityValidationError(f'{nome_campo} deve ser menor ou igual a {max_valor}')
    
    return valor


def validar_string_segura(valor: Any, nome_campo: str, max_length: int = 1000, permitir_vazio: bool = True) -> str:
    """
    Valida string com verificações de segurança.
    
    Args:
        valor: Valor a validar
        nome_campo: Nome do campo para mensagens de erro
        max_length: Tamanho máximo permitido
        permitir_vazio: Se False, não permite string vazia
    
    Returns:
        String validada
    
    Raises:
        SecurityValidationError: Se validação falhar
    """
    if valor is None:
        if permitir_vazio:
            return ''
        raise SecurityValidationError(f'{nome_campo} não fornecido')
    
    valor_str = str(valor).strip()
    
    if not permitir_vazio and not valor_str:
        raise SecurityValidationError(f'{nome_campo} não pode ser vazio')
    
    if len(valor_str) > max_length:
        raise SecurityValidationError(f'{nome_campo} excede o tamanho máximo de {max_length} caracteres')
    
    # Verifica caracteres perigosos (proteção básica contra XSS)
    caracteres_perigosos = ['<', '>', '&', '"', "'"]
    for char in caracteres_perigosos:
        if char in valor_str:
            logger.warning(f"Caractere potencialmente perigoso encontrado em {nome_campo}: {char}")
            # Não bloqueia, apenas loga (pode ser necessário em alguns casos)
    
    return valor_str


def validar_tipo_enum(valor: Any, nome_campo: str, valores_permitidos: List[str], case_sensitive: bool = False) -> str:
    """
    Valida valor contra lista de valores permitidos (enum).
    
    Args:
        valor: Valor a validar
        nome_campo: Nome do campo para mensagens de erro
        valores_permitidos: Lista de valores permitidos
        case_sensitive: Se False, compara sem considerar maiúsculas/minúsculas
    
    Returns:
        Valor validado
    
    Raises:
        SecurityValidationError: Se validação falhar
    """
    if valor is None:
        raise SecurityValidationError(f'{nome_campo} não fornecido')
    
    valor_str = str(valor).strip()
    
    if not case_sensitive:
        valor_str = valor_str.upper()
        valores_permitidos = [v.upper() for v in valores_permitidos]
    
    if valor_str not in valores_permitidos:
        raise SecurityValidationError(
            f'{nome_campo} inválido: {valor}. Valores permitidos: {", ".join(valores_permitidos)}'
        )
    
    return valor_str


# ---------------------------------------------------------------------
# Tratamento Seguro de Arquivos
# ---------------------------------------------------------------------
class FileValidationError(Exception):
    """Exceção para erros de validação de arquivos"""
    pass


# Extensões permitidas para upload
ALLOWED_EXTENSIONS = {
    'pdf': ['application/pdf'],
    'doc': ['application/msword'],
    'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
}

# Tamanho máximo de arquivo (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validar_arquivo_seguro(
    arquivo: Any,
    extensoes_permitidas: Optional[List[str]] = None,
    tamanho_maximo: Optional[int] = None,
    nome_campo: str = 'arquivo'
) -> Dict[str, Any]:
    """
    Valida arquivo com verificações de segurança.
    
    Args:
        arquivo: Objeto de arquivo a validar
        extensoes_permitidas: Lista de extensões permitidas (ex: ['pdf', 'doc'])
        tamanho_maximo: Tamanho máximo em bytes
        nome_campo: Nome do campo para mensagens de erro
    
    Returns:
        Dicionário com informações do arquivo validado:
        {
            'nome': str,
            'tamanho': int,
            'extensao': str,
            'tipo_mime': str
        }
    
    Raises:
        FileValidationError: Se validação falhar
    """
    if arquivo is None:
        raise FileValidationError(f'{nome_campo} não fornecido')
    
    # Verifica se tem atributos necessários
    if not hasattr(arquivo, 'filename') or not hasattr(arquivo, 'read'):
        raise FileValidationError(f'{nome_campo} não é um arquivo válido')
    
    nome_arquivo = arquivo.filename
    if not nome_arquivo:
        raise FileValidationError(f'{nome_campo} não tem nome')
    
    # Valida extensão
    extensao = nome_arquivo.rsplit('.', 1)[-1].lower() if '.' in nome_arquivo else ''
    
    if extensoes_permitidas:
        if extensao not in extensoes_permitidas:
            raise FileValidationError(
                f'{nome_campo} tem extensão inválida: {extensao}. '
                f'Extensões permitidas: {", ".join(extensoes_permitidas)}'
            )
    
    # Valida tamanho
    tamanho_maximo = tamanho_maximo or MAX_FILE_SIZE
    
    # Tenta obter tamanho
    try:
        # Se for um objeto de arquivo, tenta obter tamanho
        if hasattr(arquivo, 'seek') and hasattr(arquivo, 'tell'):
            posicao_atual = arquivo.tell()
            arquivo.seek(0, 2)  # Vai para o final
            tamanho = arquivo.tell()
            arquivo.seek(posicao_atual)  # Volta para posição original
        elif hasattr(arquivo, 'file') and hasattr(arquivo.file, 'seek'):
            # Para FieldStorage do cgi
            posicao_atual = arquivo.file.tell()
            arquivo.file.seek(0, 2)
            tamanho = arquivo.file.tell()
            arquivo.file.seek(posicao_atual)
        else:
            # Tenta ler para verificar tamanho (não ideal, mas funciona)
            conteudo = arquivo.read()
            tamanho = len(conteudo)
            if hasattr(arquivo, 'seek'):
                arquivo.seek(0)
    except Exception as e:
        logger.warning(f"Erro ao obter tamanho do arquivo: {e}")
        tamanho = 0
    
    if tamanho > tamanho_maximo:
        raise FileValidationError(
            f'{nome_campo} excede o tamanho máximo de {tamanho_maximo / (1024*1024):.1f}MB'
        )
    
    if tamanho == 0:
        raise FileValidationError(f'{nome_campo} está vazio')
    
    # Determina tipo MIME
    tipo_mime = ALLOWED_EXTENSIONS.get(extensao, ['application/octet-stream'])[0]
    
    return {
        'nome': nome_arquivo,
        'tamanho': tamanho,
        'extensao': extensao,
        'tipo_mime': tipo_mime
    }


def sanitizar_nome_arquivo(nome: str) -> str:
    """
    Sanitiza nome de arquivo removendo caracteres perigosos.
    
    Args:
        nome: Nome do arquivo original
    
    Returns:
        Nome sanitizado
    """
    import re
    
    # Remove caracteres perigosos
    nome_sanitizado = re.sub(r'[<>:"/\\|?*]', '_', nome)
    
    # Remove espaços múltiplos
    nome_sanitizado = re.sub(r'\s+', '_', nome_sanitizado)
    
    # Remove pontos múltiplos
    nome_sanitizado = re.sub(r'\.+', '.', nome_sanitizado)
    
    # Limita tamanho
    if len(nome_sanitizado) > 255:
        nome_parte, extensao = nome_sanitizado.rsplit('.', 1) if '.' in nome_sanitizado else (nome_sanitizado, '')
        nome_sanitizado = nome_parte[:255 - len(extensao) - 1] + '.' + extensao
    
    return nome_sanitizado


# ---------------------------------------------------------------------
# Utilitários de Data
# ---------------------------------------------------------------------
def validar_data_segura(data_str: str, formato: str = '%d/%m/%Y', nome_campo: str = 'data') -> Optional[datetime]:
    """
    Valida e converte string de data com verificações de segurança.
    
    Args:
        data_str: String de data
        formato: Formato esperado da data
        nome_campo: Nome do campo para mensagens de erro
    
    Returns:
        Objeto datetime ou None se data_str for vazia
    
    Raises:
        SecurityValidationError: Se validação falhar
    """
    if not data_str or not data_str.strip():
        return None
    
    try:
        data = datetime.strptime(data_str.strip(), formato)
        
        # Valida que a data não está muito no futuro (proteção contra erros)
        if data > datetime.now() + timedelta(days=365 * 10):  # 10 anos no futuro
            raise SecurityValidationError(f'{nome_campo} está muito no futuro')
        
        # Valida que a data não está muito no passado (proteção contra erros)
        if data < datetime(1900, 1, 1):
            raise SecurityValidationError(f'{nome_campo} está muito no passado')
        
        return data
    except ValueError as e:
        raise SecurityValidationError(f'{nome_campo} inválida: {data_str}. Formato esperado: {formato}')


# ---------------------------------------------------------------------
# Função para limpar cache
# ---------------------------------------------------------------------
def limpar_cache_tramitacao():
    """Limpa cache relacionado a tramitação"""
    _cache.clear('tramitacao:')


def invalidar_cache_unidade(cod_unidade: int):
    """Invalida cache de uma unidade específica"""
    _cache.invalidate(f'unidade:{cod_unidade}')


def invalidar_cache_usuario(cod_usuario: int):
    """Invalida cache de um usuário específico"""
    _cache.invalidate(f'usuario:{cod_usuario}')
