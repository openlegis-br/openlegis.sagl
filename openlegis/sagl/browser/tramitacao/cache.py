# -*- coding: utf-8 -*-
"""
Módulo neutro para invalidação de cache de contadores.

Este módulo não depende de views ou services, permitindo ser usado
dentro de afterCommitHook sem interferir na transação.
"""

import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)

# Cache simples em memória para contadores (compartilhado com views.py)
_contadores_cache = {}
_cache_lock = Lock()


def invalidate_cache_contadores(cod_usuario=None, cod_unid_tramitacao=None):
    """
    Invalida cache de contadores.
    
    Este é um módulo neutro que pode ser usado dentro de afterCommitHook
    sem interferir na transação.
    
    Args:
        cod_usuario: Se fornecido, invalida apenas para esse usuário
        cod_unid_tramitacao: Se fornecido, invalida apenas para essa unidade
    """
    with _cache_lock:
        if cod_usuario is None:
            # Invalida todo o cache
            _contadores_cache.clear()
        else:
            # Invalida cache específico
            keys_to_remove = []
            for key in _contadores_cache.keys():
                if key.startswith(f"{cod_usuario}_"):
                    if cod_unid_tramitacao is None or f"_{cod_unid_tramitacao}_" in key:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del _contadores_cache[key]
