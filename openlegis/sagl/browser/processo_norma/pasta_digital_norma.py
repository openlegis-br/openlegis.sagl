# -*- coding: utf-8 -*-
"""
View para fornecer dados JSON para a interface de pasta digital de normas jurídicas.
Adaptado de pasta_digital.py para trabalhar com normas ao invés de matérias.
"""
import json
import logging
import os
import hashlib
import time
import shutil
import copy
import traceback
import threading
import re
from datetime import date, datetime
from five import grok
from zope.interface import Interface
from Products.CMFCore.utils import getToolByName
from openlegis.sagl.browser.processo_norma.processo_norma_utils import (
    get_processo_norma_dir,
    get_cache_norma_file_path,
    TEMP_DIR_PREFIX_NORMA,
    safe_check_file,
    safe_check_files_batch,
    get_file_size,
    get_file_info_for_hash,
    secure_path_join
)
from openlegis.sagl.browser.processo_norma.processo_norma_service import ProcessoNormaService
from z3c.saconfig import named_scoped_session
from sqlalchemy import and_, or_
from openlegis.sagl.models.models import (
    NormaJuridica, TipoNormaJuridica, VinculoNormaJuridica,
    MateriaLegislativa, TipoMateriaLegislativa
)

Session = named_scoped_session('minha_sessao')
logger = logging.getLogger(__name__)

# Cache temporário para rastrear tasks recém-criadas (evita race condition)
# Formato: {cod_norma: (task_id, timestamp)}
_recent_tasks_cache = {}

# Cache para hash de documentos (TTL curto para garantir atualização rápida)
_hash_cache = {}
_HASH_CACHE_TTL = 30  # 30 segundos
_HASH_CACHE_MAX_SIZE = 50

# TTL para cache de documentos prontos (filesystem)
_ready_documents_cache_ttl = 300.0  # 5 minutos

# Lock por cod_norma para evitar criação simultânea de tasks
_task_creation_locks = {}
_locks_lock = threading.Lock()  # Lock para proteger o dicionário de locks

class DateTimeJSONEncoder(json.JSONEncoder):
    """Encoder JSON customizado para converter objetos date/datetime para string"""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            if isinstance(obj, datetime):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            else:
                return obj.strftime('%Y-%m-%d')
        return super().default(obj)


# Funções auxiliares para gerenciamento de cache e hash
def _load_cache_from_filesystem(cod_norma_int):
    """Carrega cache do filesystem para uma norma"""
    try:
        cache_file = get_cache_norma_file_path(cod_norma_int)
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'documentos' in data and 'timestamp' in data:
                    documentos_data = data['documentos']
                    timestamp = data['timestamp']
                    documents_hash = data.get('hash', None)
                    documents_sizes = data.get('sizes', None)
                    return (documentos_data, timestamp, documents_hash, documents_sizes)
    except Exception as e:
        pass
    return None

def _save_cache_to_filesystem(cod_norma_int, documentos_data, timestamp, documents_hash, documents_sizes=None):
    """Salva cache no filesystem para uma norma"""
    try:
        cache_file = get_cache_norma_file_path(cod_norma_int)
        cache_dir = os.path.dirname(cache_file)
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        
        data = {
            'documentos': documentos_data,
            'timestamp': timestamp,
            'hash': documents_hash,
            'cod_norma': str(cod_norma_int)
        }
        if documents_sizes is not None:
            data['sizes'] = documents_sizes
        
        temp_file = cache_file + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, cls=DateTimeJSONEncoder)
        os.replace(temp_file, cache_file)
    except Exception as e:
        logger.warning(f"[_save_cache_to_filesystem] Erro ao salvar cache no filesystem para {cod_norma_int}: {e}")

def _delete_cache_from_filesystem(cod_norma_int):
    """Remove cache do filesystem para uma norma"""
    try:
        cache_file = get_cache_norma_file_path(cod_norma_int)
        if os.path.exists(cache_file):
            os.unlink(cache_file)
    except Exception as e:
        pass

def _calculate_documents_hash(cod_norma, portal, force_recalculate=False):
    """Calcula hash dos documentos disponíveis para uma norma"""
    global _hash_cache
    
    current_time = time.time()
    cache_key = f"norma_{cod_norma}"
    
    # CRÍTICO: Se force_recalculate, sempre ignora cache e recalcula
    # Isso garante que mudanças recentes sejam detectadas
    if force_recalculate:
        # Remove do cache para forçar recálculo
        _hash_cache.pop(cache_key, None)
    elif cache_key in _hash_cache:
        cached_hash, cache_timestamp = _hash_cache[cache_key]
        age = current_time - cache_timestamp
        if age < _HASH_CACHE_TTL:
            return cached_hash
        else:
            del _hash_cache[cache_key]
    
    if len(_hash_cache) >= _HASH_CACHE_MAX_SIZE:
        sorted_items = sorted(_hash_cache.items(), key=lambda x: x[1][1])
        items_to_remove = len(_hash_cache) - _HASH_CACHE_MAX_SIZE + 1
        for key, _ in sorted_items[:items_to_remove]:
            del _hash_cache[key]
    
    try:
        hash_data = []
        
        if not hasattr(portal, 'sapl_documentos'):
            return None
        
        # 1. Texto integral da norma
        arquivo_texto = f"{cod_norma}_texto_integral.pdf"
        if hasattr(portal.sapl_documentos, 'norma_juridica'):
            if safe_check_file(portal.sapl_documentos.norma_juridica, arquivo_texto):
                file_info = get_file_info_for_hash(portal.sapl_documentos.norma_juridica, arquivo_texto)
                if file_info:
                    hash_data.append(f"texto_integral:{'|'.join(file_info)}")
                else:
                    hash_data.append(f"texto_integral:exists")
            else:
                hash_data.append(f"texto_integral:not_exists")
        else:
            hash_data.append(f"texto_integral:not_exists")
        
        # 1.1. Texto compilado da norma
        arquivo_compilado = f"{cod_norma}_texto_consolidado.pdf"
        if hasattr(portal.sapl_documentos, 'norma_juridica'):
            if safe_check_file(portal.sapl_documentos.norma_juridica, arquivo_compilado):
                file_info = get_file_info_for_hash(portal.sapl_documentos.norma_juridica, arquivo_compilado)
                if file_info:
                    hash_data.append(f"texto_compilado:{'|'.join(file_info)}")
                else:
                    hash_data.append(f"texto_compilado:exists")
            else:
                hash_data.append(f"texto_compilado:not_exists")
        else:
            hash_data.append(f"texto_compilado:not_exists")
        
        # 2. Matéria relacionada (se houver)
        try:
            session = Session()
            try:
                norma = session.query(NormaJuridica)\
                    .filter(NormaJuridica.cod_norma == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
            finally:
                session.close()
            
            if norma and norma.cod_materia:
                    arquivo_materia = f"{norma.cod_materia}_texto_integral.pdf"
                    if hasattr(portal.sapl_documentos, 'materia'):
                        if safe_check_file(portal.sapl_documentos.materia, arquivo_materia):
                            file_info = get_file_info_for_hash(portal.sapl_documentos.materia, arquivo_materia)
                            if file_info:
                                hash_data.append(f"materia_relacionada:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"materia_relacionada:exists")
                        else:
                            hash_data.append(f"materia_relacionada:not_exists")
        except Exception as e:
            pass
        
        # 3. Normas relacionadas (vinculadas)
        try:
            session = Session()
            try:
                # OTIMIZAÇÃO: Adiciona JOIN com TipoNormaJuridica para evitar N+1 queries
                vinculos_referente = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referida == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referente == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                vinculos_referida = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referente == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referida == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                normas_vinculadas = set()
                # ATUALIZAÇÃO: Agora retorna (vinculo, norma, tipo_norma)
                for vinculo_obj, norma_obj, tipo_norma_obj in vinculos_referente:
                    normas_vinculadas.add(norma_obj.cod_norma)
                for vinculo_obj, norma_obj, tipo_norma_obj in vinculos_referida:
                    normas_vinculadas.add(norma_obj.cod_norma)
                
                # OTIMIZAÇÃO: Verifica múltiplos arquivos em batch ao invés de sequencial
                if normas_vinculadas and hasattr(portal.sapl_documentos, 'norma_juridica'):
                    arquivos_normas_vinculadas = [f"{cod_norma_vinculada}_texto_integral.pdf" for cod_norma_vinculada in sorted(normas_vinculadas)]
                    arquivos_existentes = safe_check_files_batch(portal.sapl_documentos.norma_juridica, arquivos_normas_vinculadas)
                    
                    for cod_norma_vinculada in sorted(normas_vinculadas):
                        arquivo_norma = f"{cod_norma_vinculada}_texto_integral.pdf"
                        if arquivos_existentes.get(arquivo_norma, False):
                            file_info = get_file_info_for_hash(portal.sapl_documentos.norma_juridica, arquivo_norma)
                            if file_info:
                                hash_data.append(f"norma_vinculada_{cod_norma_vinculada}:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"norma_vinculada_{cod_norma_vinculada}:exists")
                        else:
                            hash_data.append(f"norma_vinculada_{cod_norma_vinculada}:not_exists")
            finally:
                session.close()
        except Exception as e:
            pass
        
        # 4. Anexos da norma
        try:
            from openlegis.sagl.models.models import AnexoNorma
            session = Session()
            try:
                anexos = session.query(AnexoNorma)\
                    .filter(AnexoNorma.cod_norma == cod_norma)\
                    .filter(AnexoNorma.ind_excluido == 0)\
                    .order_by(AnexoNorma.cod_anexo)\
                    .all()
                
                hash_data.append(f"anexos_count:{len(anexos)}")
                # OTIMIZAÇÃO: Verifica múltiplos anexos em batch ao invés de sequencial
                if anexos and hasattr(portal.sapl_documentos, 'norma_juridica'):
                    arquivos_anexos = [f"{cod_norma}_anexo_{anexo.cod_anexo}" for anexo in anexos]
                    arquivos_existentes = safe_check_files_batch(portal.sapl_documentos.norma_juridica, arquivos_anexos)
                    
                    for anexo in anexos:
                        id_anexo = f"{cod_norma}_anexo_{anexo.cod_anexo}"
                        if arquivos_existentes.get(id_anexo, False):
                            file_info = get_file_info_for_hash(portal.sapl_documentos.norma_juridica, id_anexo)
                            if file_info:
                                hash_data.append(f"anexo_{anexo.cod_anexo}:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"anexo_{anexo.cod_anexo}:exists")
                        else:
                            hash_data.append(f"anexo_{anexo.cod_anexo}:not_exists")
                elif anexos:
                    # Se não tem container, marca todos como não existentes
                    for anexo in anexos:
                        hash_data.append(f"anexo_{anexo.cod_anexo}:not_exists")
            finally:
                session.close()
        except Exception as e:
            pass
        
        if hash_data:
            hash_string = "|".join(sorted(hash_data))
            calculated_hash = hashlib.md5(hash_string.encode('utf-8')).hexdigest()
            _hash_cache[cache_key] = (calculated_hash, current_time)
            return calculated_hash
        else:
            return None
    except Exception as e:
        logger.warning(f"[_calculate_documents_hash] Erro ao calcular hash dos documentos: {e}")
        return None

def _collect_current_documents_metadata(cod_norma_int, portal):
    """
    Coleta metadados dos documentos atuais do sistema para uma norma (sem fazer download).
    Retorna uma lista de dicionários com informações sobre cada documento que seria coletado.
    
    Returns:
        list: Lista de dicionários com {'file': nome_arquivo, 'file_size': tamanho, 'title': titulo}
    """
    documentos_atual = []
    
    try:
        if not hasattr(portal, 'sapl_documentos'):
            return documentos_atual
        
        # Calcula diretório base para verificar arquivos coletados
        dir_base = get_processo_norma_dir(cod_norma_int)
        
        # Função auxiliar para obter tamanho de arquivo coletado no diretório (apenas para fallback)
        def _get_collected_file_size(filename):
            """Obtém tamanho do arquivo coletado no diretório, se existir (usado apenas como fallback)"""
            try:
                file_path = os.path.join(dir_base, filename)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    return os.path.getsize(file_path)
            except Exception:
                pass
            return 0
        
        # Obtém dados da norma para construir nomes de arquivos
        try:
            session = Session()
            try:
                result = session.query(NormaJuridica, TipoNormaJuridica)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(NormaJuridica.cod_norma == cod_norma_int)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
                
                if result:
                    norma_obj, tipo_obj = result
                    tipo = tipo_obj.sgl_tipo_norma if hasattr(tipo_obj, 'sgl_tipo_norma') and tipo_obj.sgl_tipo_norma else 'LEI'
                    numero = norma_obj.num_norma if hasattr(norma_obj, 'num_norma') and norma_obj.num_norma else '0'
                    ano = norma_obj.ano_norma if hasattr(norma_obj, 'ano_norma') and norma_obj.ano_norma else '2025'
                else:
                    # Fallback para valores padrão se norma não encontrada
                    tipo = 'LEI'
                    numero = '0'
                    ano = '2025'
            finally:
                session.close()
            
            # 1. Capa do processo - sempre incluída, pois é sempre gerada durante a coleta
            arquivo_capa = f"capa_{tipo}-{numero}-{ano}.pdf"
            
            # Obtém tamanho atual da capa via HTTP (para detectar mudanças)
            capa_size = 0
            try:
                base_url = portal.absolute_url() if hasattr(portal, 'absolute_url') else ''
                if base_url:
                    # Tenta usar método específico para normas, se existir
                    url = f"{base_url}/modelo_proposicao/capa_norma?cod_norma={cod_norma_int}&action=download"
                    import urllib.request
                    req = urllib.request.Request(url)
                    req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                    
                    try:
                        with urllib.request.urlopen(req, timeout=10) as response:
                            capa_data = response.read()
                            if capa_data:
                                capa_size = len(capa_data)
                    except urllib.error.HTTPError as http_err:
                        if http_err.code == 404:
                            # Tenta fallback para capa_processo se norma tiver cod_materia
                            session = Session()
                            try:
                                norma = session.query(NormaJuridica)\
                                    .filter(NormaJuridica.cod_norma == cod_norma_int)\
                                    .filter(NormaJuridica.ind_excluido == 0)\
                                    .first()
                                if norma and norma.cod_materia:
                                    url = f"{base_url}/modelo_proposicao/capa_processo?cod_materia={norma.cod_materia}&action=download"
                                    req = urllib.request.Request(url)
                                    req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                                    with urllib.request.urlopen(req, timeout=10) as response:
                                        capa_data = response.read()
                                        if capa_data:
                                            capa_size = len(capa_data)
                            finally:
                                session.close()
            except Exception as e:
                # Se falhar ao obter via HTTP, tenta usar arquivo no diretório
                capa_size = _get_collected_file_size(arquivo_capa)
            
            # Sempre inclui a capa na lista (sempre é gerada na coleta)
            documentos_atual.append({
                'file': arquivo_capa,
                'file_size': capa_size,
                'title': 'Capa da Norma'
            })
        except Exception as e:
            pass
        
        # 2. Texto integral
        # CRÍTICO: Sempre verifica, mesmo se não existir (para detectar remoções)
        arquivo_texto = f"{cod_norma_int}_texto_integral.pdf"
        if hasattr(portal.sapl_documentos, 'norma_juridica'):
            if safe_check_file(portal.sapl_documentos.norma_juridica, arquivo_texto):
                size = get_file_size(portal.sapl_documentos.norma_juridica, arquivo_texto) or 0
                documentos_atual.append({
                    'file': arquivo_texto,
                    'file_size': size,
                    'title': 'Texto Integral'
                })
            # Se não existe, não adiciona (será detectado como removido na comparação se estava no JSON)
        
        # 3. Texto compilado
        # CRÍTICO: Sempre verifica, mesmo se não existir (para detectar remoções)
        arquivo_compilado = f"{cod_norma_int}_texto_consolidado.pdf"
        if hasattr(portal.sapl_documentos, 'norma_juridica'):
            if safe_check_file(portal.sapl_documentos.norma_juridica, arquivo_compilado):
                size = get_file_size(portal.sapl_documentos.norma_juridica, arquivo_compilado) or 0
                documentos_atual.append({
                    'file': arquivo_compilado,
                    'file_size': size,
                    'title': 'Texto Compilado'
                })
            # Se não existe, não adiciona (será detectado como removido na comparação se estava no JSON)
        
        # 4. Matéria relacionada
        try:
            session = Session()
            try:
                norma = session.query(NormaJuridica)\
                    .filter(NormaJuridica.cod_norma == cod_norma_int)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
                
                if norma and norma.cod_materia:
                    # CRÍTICO: Sempre verifica matéria relacionada, mesmo se não existir (para detectar remoções)
                    arquivo_materia = f"{norma.cod_materia}_texto_integral.pdf"
                    if hasattr(portal.sapl_documentos, 'materia'):
                        if safe_check_file(portal.sapl_documentos.materia, arquivo_materia):
                            size = get_file_size(portal.sapl_documentos.materia, arquivo_materia) or 0
                            documentos_atual.append({
                                'file': arquivo_materia,
                                'file_size': size,
                                'title': 'Matéria Relacionada'
                            })
                        # Se não existe, não adiciona (será detectado como removido na comparação se estava no JSON)
            finally:
                session.close()
        except Exception as e:
            pass
        
        # 5. Normas relacionadas (vinculadas)
        try:
            session = Session()
            try:
                # OTIMIZAÇÃO: Adiciona JOIN com TipoNormaJuridica para evitar N+1 queries
                vinculos_referente = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referida == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referente == cod_norma_int)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                vinculos_referida = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referente == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referida == cod_norma_int)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                normas_vinculadas = set()
                # ATUALIZAÇÃO: Agora retorna (vinculo, norma, tipo_norma)
                for vinculo_obj, norma_obj, tipo_norma_obj in vinculos_referente:
                    normas_vinculadas.add(norma_obj.cod_norma)
                for vinculo_obj, norma_obj, tipo_norma_obj in vinculos_referida:
                    normas_vinculadas.add(norma_obj.cod_norma)
                
                # OTIMIZAÇÃO: Verifica múltiplos arquivos em batch ao invés de sequencial
                if normas_vinculadas and hasattr(portal.sapl_documentos, 'norma_juridica'):
                    arquivos_normas_vinculadas = [f"{cod_norma_vinculada}_texto_integral.pdf" for cod_norma_vinculada in sorted(normas_vinculadas)]
                    arquivos_existentes = safe_check_files_batch(portal.sapl_documentos.norma_juridica, arquivos_normas_vinculadas)
                    
                    for cod_norma_vinculada in sorted(normas_vinculadas):
                        # CRÍTICO: Sempre verifica normas relacionadas, mesmo se não existirem (para detectar remoções)
                        arquivo_norma = f"{cod_norma_vinculada}_texto_integral.pdf"
                        if arquivos_existentes.get(arquivo_norma, False):
                            size = get_file_size(portal.sapl_documentos.norma_juridica, arquivo_norma) or 0
                            documentos_atual.append({
                                'file': arquivo_norma,
                                'file_size': size,
                                'title': f'Norma Relacionada {cod_norma_vinculada}'
                            })
                        # Se não existe, não adiciona (será detectado como removido na comparação se estava no JSON)
            finally:
                session.close()
        except Exception as e:
            pass
        
        # 6. Anexos da norma
        try:
            from openlegis.sagl.models.models import AnexoNorma
            session = Session()
            try:
                anexos = session.query(AnexoNorma)\
                    .filter(AnexoNorma.cod_norma == cod_norma_int)\
                    .filter(AnexoNorma.ind_excluido == 0)\
                    .order_by(AnexoNorma.cod_anexo)\
                    .all()
                
                for anexo in anexos:
                    # CRÍTICO: Sempre verifica anexos, mesmo se não existirem (para detectar remoções)
                    id_anexo = f"{cod_norma_int}_anexo_{anexo.cod_anexo}"
                    if hasattr(portal.sapl_documentos, 'norma_juridica'):
                        if safe_check_file(portal.sapl_documentos.norma_juridica, id_anexo):
                            size = get_file_size(portal.sapl_documentos.norma_juridica, id_anexo) or 0
                            documentos_atual.append({
                                'file': id_anexo,
                                'file_size': size,
                                'title': f'Anexo {anexo.cod_anexo} - {anexo.txt_descricao or "Sem descrição"}'
                            })
                        # Se não existe, não adiciona (será detectado como removido na comparação se estava no JSON)
                        # CRÍTICO: Se o anexo foi excluído do ZODB mas o registro ainda existe, será detectado como removido
            finally:
                session.close()
        except Exception as e:
            pass
        
    except Exception as e:
        logger.warning(f"[_collect_current_documents_metadata] Erro ao coletar metadados dos documentos: {e}")
    
    return documentos_atual


def _compare_documents_with_metadados(cod_norma_int, portal):
    """
    Compara os documentos ATUAIS do sistema com dados armazenados em documentos_metadados.json.
    
    Returns:
        tuple: (has_changes, details_dict) onde:
            - has_changes: True se há mudanças que exigem regeneração
            - details_dict: dicionário com detalhes das mudanças (novos, removidos, modificados)
    """
    try:
        # Calcula diretório base
        dir_base = get_processo_norma_dir(cod_norma_int)
        metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
        
        # Se não existe metadados, precisa gerar pasta digital
        if not os.path.exists(metadados_path):
            return (True, {'error': 'JSON não existe'})
        
        # Se diretório não existe, há mudanças (precisa regenerar)
        if not os.path.exists(dir_base):
            return (True, {'error': 'Diretório não existe'})
        
        # Carrega metadados da última geração
        with open(metadados_path, 'r', encoding='utf-8') as f:
            metadados = json.load(f)
        
        documentos_metadados = metadados.get('documentos', [])
        
        if not documentos_metadados:
            return (False, {})
        
        # Coleta documentos ATUAIS do sistema
        documentos_atual = _collect_current_documents_metadata(cod_norma_int, portal)
        
        # Função auxiliar para obter tamanho real do arquivo coletado no diretório
        def _get_collected_file_size_in_dir(filename):
            """Obtém tamanho do arquivo coletado no diretório, se existir"""
            try:
                file_path = os.path.join(dir_base, filename)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    return os.path.getsize(file_path)
            except Exception:
                pass
            return 0
        
        # Cria mapas para comparação (por nome de arquivo)
        metadados_map = {doc.get('file', ''): doc for doc in documentos_metadados}
        atual_map = {doc.get('file', ''): doc for doc in documentos_atual}
        
        has_changes = False
        details = {
            'added': [],
            'removed': [],
            'modified': [],
        }
        
        # CRÍTICO: Verifica mudança na quantidade de documentos coletados
        # Se a quantidade mudou, há mudança significativa que requer regeneração
        count_metadados = len(metadados_map)
        count_atual = len(atual_map)
        if count_metadados != count_atual:
            has_changes = True
            details['count_changed'] = {
                'old_count': count_metadados,
                'new_count': count_atual
            }
            # Continua verificando quais documentos foram adicionados/removidos abaixo
        
        # CRÍTICO: Verifica TODOS os documentos coletados para detectar:
        # 1. Documentos ADICIONADOS (estão no sistema mas não estavam no JSON)
        # 2. Documentos EXCLUÍDOS (estavam no JSON mas não estão mais no sistema)
        # 3. Documentos ALTERADOS (estão em ambos mas o tamanho mudou)
        
        # Primeiro, verifica arquivos que estavam no JSON (para detectar exclusões)
        for file_name, doc_meta in metadados_map.items():
            if file_name not in atual_map:
                # CASO 1: Documento EXCLUÍDO - estava no JSON mas não está mais no sistema
                has_changes = True
                details['removed'].append(file_name)
        
        # Depois, verifica arquivos que estão no sistema (para detectar adições e alterações)
        for file_name, doc_atual in atual_map.items():
            if file_name not in metadados_map:
                # CASO 2: Documento ADICIONADO - está no sistema mas não estava no JSON
                has_changes = True
                details['added'].append(file_name)
            else:
                # CASO 3: Documento existe em ambos - verifica se foi ALTERADO ou REMOVIDO
                doc_meta = metadados_map[file_name]
                size_meta = doc_meta.get('file_size', 0)
                size_atual = doc_atual.get('file_size', 0)
                
                # Para todos os documentos baixados (incluindo capa), sempre usa o tamanho atual do sistema
                size_to_compare = size_atual
                size_in_dir = _get_collected_file_size_in_dir(file_name)
                
                # Verifica se é capa para definir tamanho mínimo de comparação e tolerância
                is_capa = file_name.startswith('capa_') and file_name.endswith('.pdf')
                min_size = 0 if is_capa else 100
                
                # Tolerância para variações de tamanho (especialmente para capa que pode ter pequenas variações na geração)
                # Para capa: tolera até 1KB de diferença (pequenas variações na geração do PDF são normais)
                # Para outros documentos: tolera até 100 bytes de diferença
                size_tolerance = 1024 if is_capa else 100
                
                # SUBCASO 3.1: Documento foi EXCLUÍDO (tinha tamanho válido no JSON mas tamanho atual é 0)
                if size_meta > min_size and size_to_compare == 0:
                    # Arquivo estava no JSON com tamanho válido mas não existe mais no sistema - foi removido
                    has_changes = True
                    details['removed'].append(file_name)
                # SUBCASO 3.2: Documento foi ALTERADO (ambos têm tamanho válido mas são diferentes)
                elif size_meta > min_size and size_to_compare > min_size:
                    if size_meta != size_to_compare:
                        # Calcula diferença absoluta
                        size_diff = abs(size_meta - size_to_compare)
                        
                        # Se a diferença está dentro da tolerância, ignora (especialmente para capa)
                        if size_diff > size_tolerance:
                            # Diferença significativa - marca como modificado
                            has_changes = True
                            details['modified'].append({
                                'file': file_name,
                                'old_size': size_meta,
                                'new_size': size_to_compare
                            })
                # SUBCASO 3.3: Documento foi ADICIONADO (não tinha no JSON mas tem agora)
                elif size_meta == 0 and size_to_compare > min_size:
                    has_changes = True
                    details['added'].append(file_name)
        
        if has_changes:
            pass
        
        return (has_changes, details)
        
    except Exception as e:
        logger.warning(f"[_compare_documents_with_metadados] Erro ao comparar documentos com metadados: {e}")
        # Em caso de erro, assume que há mudanças (mais seguro)
        return (True, {'error': str(e)})


def _calculate_documents_sizes(cod_norma, portal):
    """Calcula os tamanhos dos arquivos coletados para uma norma"""
    try:
        sizes = {}
        
        if not hasattr(portal, 'sapl_documentos'):
            return sizes
        
        # Texto integral da norma
        arquivo_texto = f"{cod_norma}_texto_integral.pdf"
        if hasattr(portal.sapl_documentos, 'norma_juridica'):
            size = get_file_size(portal.sapl_documentos.norma_juridica, arquivo_texto)
            if size:
                sizes[arquivo_texto] = size
        
        # Matéria relacionada
        try:
            session = Session()
            try:
                norma = session.query(NormaJuridica)\
                    .filter(NormaJuridica.cod_norma == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
            finally:
                session.close()
            
            if norma and norma.cod_materia:
                    arquivo_materia = f"{norma.cod_materia}_texto_integral.pdf"
                    if hasattr(portal.sapl_documentos, 'materia'):
                        size = get_file_size(portal.sapl_documentos.materia, arquivo_materia)
                        if size:
                            sizes[arquivo_materia] = size
        except Exception as e:
            pass
        
        # Normas relacionadas
        try:
            session = Session()
            try:
                # OTIMIZAÇÃO: Adiciona JOIN com TipoNormaJuridica para evitar N+1 queries
                vinculos_referente = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referida == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referente == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                vinculos_referida = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referente == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referida == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                normas_vinculadas = set()
                # ATUALIZAÇÃO: Agora retorna (vinculo, norma, tipo_norma)
                for vinculo_obj, norma_obj, tipo_norma_obj in vinculos_referente:
                    normas_vinculadas.add(norma_obj.cod_norma)
                for vinculo_obj, norma_obj, tipo_norma_obj in vinculos_referida:
                    normas_vinculadas.add(norma_obj.cod_norma)
                
                for cod_norma_vinculada in normas_vinculadas:
                    arquivo_norma = f"{cod_norma_vinculada}_texto_integral.pdf"
                    if hasattr(portal.sapl_documentos, 'norma_juridica'):
                        size = get_file_size(portal.sapl_documentos.norma_juridica, arquivo_norma)
                        if size:
                            sizes[arquivo_norma] = size
            finally:
                session.close()
        except Exception as e:
            pass
        
        return sizes
    except Exception as e:
        logger.warning(f"[_calculate_documents_sizes] Erro ao calcular tamanhos dos documentos: {e}")
        return None


class PastaDigitalNormaMixin:
    """Mixin com métodos compartilhados para views de pasta digital de normas"""
    
    def _get_session(self):
        """Retorna sessão SQLAlchemy thread-safe"""
        return Session()
    
    def _get_norma_cached(self, cod_norma):
        """
        Cache de norma principal para evitar queries repetidas na mesma requisição.
        
        Compatível com Zope - cache armazenado na instância da view.
        Retorna tuple (NormaJuridica, TipoNormaJuridica) ou None.
        """
        if not hasattr(self, '_norma_cache'):
            self._norma_cache = {}
        cod_str = str(cod_norma)
        if cod_str not in self._norma_cache:
            session = self._get_session()
            try:
                result = session.query(NormaJuridica, TipoNormaJuridica)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(NormaJuridica.cod_norma == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
                self._norma_cache[cod_str] = result
            except Exception as e:
                logger.error(f"[_get_norma_cached] Erro ao buscar norma {cod_norma}: {e}", exc_info=True)
                self._norma_cache[cod_str] = None
            finally:
                session.close()
        return self._norma_cache[cod_str]
    
    def _get_norma_data(self, cod_norma):
        """Obtém dados básicos da norma"""
        try:
            session = self._get_session()
            try:
                result = session.query(NormaJuridica, TipoNormaJuridica)\
                    .join(TipoNormaJuridica, 
                          NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(NormaJuridica.cod_norma == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
                
                if not result:
                    return None
                
                norma_obj, tipo_obj = result
                
                return {
                    'cod_norma': norma_obj.cod_norma,
                    'tipo': tipo_obj.sgl_tipo_norma,
                    'numero': norma_obj.num_norma,
                    'ano': norma_obj.ano_norma,
                    'data_norma': norma_obj.dat_norma,
                    'descricao': tipo_obj.des_tipo_norma,
                    'id_exibicao': f"{tipo_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma}"
                }
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Erro ao obter dados da norma: {e}", exc_info=True)
            return None
    
    def _get_pasta_data(self, cod_norma, action, tool, portal):
        """Obtém dados da pasta digital chamando diretamente a view processo_norma_integral"""
        try:
            # Cria um objeto de resposta base para garantir que nunca seja None
            base_response = {
                'async': True,  # SEMPRE True para action=pasta (força o monitor aparecer)
                'task_id': None,
                'status': 'PENDING',
                'documentos': [],
                'cod_norma': int(cod_norma) if cod_norma and str(cod_norma).isdigit() else cod_norma,
                'paginas_geral': 0,
                'message': 'Processando pasta digital...'
            }
            
            # Para action='download', retorna dados mínimos
            if action == 'download':
                base_response['action'] = 'download'
                base_response['async'] = False
                return base_response
            
            # Para action='pasta', processa normalmente
            if action == 'pasta':
                try:
                    portal_url = str(portal.absolute_url())
                    cod_norma_int = int(cod_norma)
                    cod_norma_str = str(cod_norma_int)
                    
                    # Verifica se já existe task ativa antes de criar nova
                    has_active_task = False
                    task_id = None
                    task_status = None
                    
                    # 1. Verifica cache de tasks recém-criadas
                    current_time = time.time()
                    cache_ttl = 60.0  # 60 segundos
                    needs_regeneration = False
                    
                    if cod_norma_str in _recent_tasks_cache:
                        cached_task_id, cache_timestamp = _recent_tasks_cache[cod_norma_str]
                        if current_time - cache_timestamp < cache_ttl:
                            has_recent_task = True
                            
                            # Verifica se há documentos prontos mesmo com task recente
                            try:
                                service = ProcessoNormaService(self.context, self.request)
                                check_result = service.get_documentos_prontos(cod_norma, skip_signature_check=True)
                                
                                if isinstance(check_result, dict) and 'documentos' in check_result and len(check_result.get('documentos', [])) > 0:
                                    # Verifica se diretório ainda existe antes de retornar documentos
                                    dir_base_check = get_processo_norma_dir(cod_norma_int)
                                    if not os.path.exists(dir_base_check):
                                        _recent_tasks_cache.pop(cod_norma_str, None)
                                        _delete_cache_from_filesystem(cod_norma_int)
                                        has_recent_task = False
                                        cached_task_id = None
                                        needs_regeneration = True
                                    else:
                                        # Diretório existe - documentos prontos encontrados
                                        if not needs_regeneration:
                                            result_copy = copy.deepcopy(check_result)
                                            result_copy['async'] = False
                                            result_copy['task_id'] = None
                                            result_copy['message'] = 'Carregando documentos...'
                                            if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                                result_copy['paginas_geral'] = result_copy['total_paginas']
                                            if 'cod_norma' not in result_copy:
                                                result_copy['cod_norma'] = cod_norma_int
                                            documents_hash = _calculate_documents_hash(cod_norma_int, portal)
                                            documents_sizes = _calculate_documents_sizes(cod_norma_int, portal)
                                            _save_cache_to_filesystem(cod_norma_int, result_copy, current_time, documents_hash, documents_sizes)
                                            return result_copy
                            except Exception as check_err:
                                pass
                            
                            # Se não encontrou documentos prontos, retorna status PENDING
                            if has_recent_task and not needs_regeneration:
                                dir_base_check = get_processo_norma_dir(cod_norma_int)
                                if os.path.exists(dir_base_check):
                                    try:
                                        service_status = ProcessoNormaService(self.context, self.request)
                                        task_status_detail = service_status.verificar_task_status(cached_task_id)
                                        if task_status_detail:
                                            base_response.update({
                                                'task_id': str(cached_task_id),
                                                'status': task_status_detail.get('status', 'PENDING'),
                                                'message': task_status_detail.get('message', 'Tarefa recém-criada, aguardando processamento'),
                                            })
                                            if 'current' in task_status_detail:
                                                base_response['current'] = task_status_detail['current']
                                            if 'total' in task_status_detail:
                                                base_response['total'] = task_status_detail['total']
                                            if 'stage' in task_status_detail:
                                                base_response['stage'] = task_status_detail['stage']
                                        else:
                                            base_response.update({
                                                'task_id': str(cached_task_id),
                                                'status': 'PENDING',
                                                'message': 'Tarefa recém-criada, aguardando processamento'
                                            })
                                    except Exception as status_err:
                                        base_response.update({
                                            'task_id': str(cached_task_id),
                                            'status': 'PENDING',
                                            'message': 'Tarefa recém-criada, aguardando processamento'
                                        })
                                    return base_response
                        else:
                            _recent_tasks_cache.pop(cod_norma_str, None)
                    
                    # 2. Verifica tasks ativas no Celery usando serviço
                    try:
                        service = ProcessoNormaService(self.context, self.request)
                        has_active_task, task_id, task_status = service.verificar_tasks_ativas(cod_norma_int)
                    except Exception as task_check_err:
                        pass
                    
                    if not has_active_task and cod_norma_str in _recent_tasks_cache:
                        _recent_tasks_cache.pop(cod_norma_str, None)
                    
                    # Se encontrou task ativa, verifica se os arquivos existem
                    if has_active_task and task_id:
                        dir_hash = hashlib.md5(str(cod_norma_int).encode()).hexdigest()
                        prefix = f"{TEMP_DIR_PREFIX_NORMA}{dir_hash}"
                        install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
                        temp_base = os.path.abspath(os.path.join(install_home, 'var', 'tmp'))
                        dir_base = secure_path_join(temp_base, prefix)
                        metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                        
                        if not os.path.exists(metadados_path):
                            _recent_tasks_cache.pop(cod_norma_str, None)
                            _delete_cache_from_filesystem(cod_norma_int)
                            has_active_task = False
                            task_id = None
                        else:
                            _recent_tasks_cache[cod_norma_str] = (task_id, current_time)
                            if len(_recent_tasks_cache) > 20:
                                sorted_items = sorted(_recent_tasks_cache.items(), key=lambda x: x[1][1])
                                for key, _ in sorted_items[:-20]:
                                    _recent_tasks_cache.pop(key, None)
                            
                            try:
                                service_status = ProcessoNormaService(self.context, self.request)
                                task_status_detail = service_status.verificar_task_status(task_id)
                                if task_status_detail:
                                    base_response.update({
                                        'task_id': str(task_id),
                                        'status': task_status_detail.get('status', task_status or 'PENDING'),
                                        'message': task_status_detail.get('message', 'Tarefa já está em execução ou na fila'),
                                    })
                                    if 'current' in task_status_detail:
                                        base_response['current'] = task_status_detail['current']
                                    if 'total' in task_status_detail:
                                        base_response['total'] = task_status_detail['total']
                                    if 'stage' in task_status_detail:
                                        base_response['stage'] = task_status_detail['stage']
                                else:
                                    base_response.update({
                                        'task_id': str(task_id),
                                        'status': str(task_status or 'PENDING'),
                                        'message': 'Tarefa já está em execução ou na fila'
                                    })
                            except Exception as status_err:
                                base_response.update({
                                    'task_id': str(task_id),
                                    'status': str(task_status or 'PENDING'),
                                    'message': 'Tarefa já está em execução ou na fila'
                                })
                            return base_response
                    
                    # Verifica se o diretório base existe
                    dir_base = get_processo_norma_dir(cod_norma_int)
                    
                    if not os.path.exists(dir_base):
                        _recent_tasks_cache.pop(cod_norma_str, None)
                        _delete_cache_from_filesystem(cod_norma_int)
                        _hash_cache.pop(cod_norma_str, None)
                        has_recent_task = False
                        cached_task_id = None
                    else:
                        has_recent_task = False
                        cached_task_id = None
                        if cod_norma_str in _recent_tasks_cache:
                            cached_task_id, cache_timestamp = _recent_tasks_cache[cod_norma_str]
                            time_since_cache = time.time() - cache_timestamp
                            if time_since_cache < 60.0:
                                has_recent_task = True
                    
                    # Verifica documentos prontos se há task recente
                    if has_recent_task:
                        try:
                            # CRÍTICO: Verifica hash antes de retornar documentos prontos (força recálculo)
                            current_hash_check = _calculate_documents_hash(cod_norma_int, portal, force_recalculate=True)
                            
                            # Verifica se há metadados para comparar hash
                            dir_base_check = get_processo_norma_dir(cod_norma_int)
                            metadados_path = os.path.join(dir_base_check, 'documentos_metadados.json')
                            
                            hash_matches = True
                            if current_hash_check and os.path.exists(metadados_path):
                                try:
                                    with open(metadados_path, 'r', encoding='utf-8') as f:
                                        metadados = json.load(f)
                                    metadados_hash = metadados.get('documents_hash')
                                    
                                    if metadados_hash and metadados_hash != current_hash_check:
                                        hash_matches = False
                                        # Limpa cache e força nova task
                                        _delete_cache_from_filesystem(cod_norma_int)
                                        _recent_tasks_cache.pop(cod_norma_str, None)
                                        has_recent_task = False
                                        cached_task_id = None
                                        # Limpa diretório do processo
                                        if os.path.exists(dir_base_check):
                                            shutil.rmtree(dir_base_check, ignore_errors=True)
                                except Exception as metadados_err:
                                    logger.warning(f"[_get_pasta_data] Erro ao verificar metadados durante task recente: {metadados_err}")
                            
                            if hash_matches:
                                service = ProcessoNormaService(self.context, self.request)
                                result = service.get_documentos_prontos(cod_norma, skip_signature_check=True)
                                
                                if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                    if os.path.exists(dir_base_check):
                                        result_copy = copy.deepcopy(result)
                                        if cached_task_id:
                                            result_copy['async'] = True
                                            result_copy['task_id'] = str(cached_task_id)
                                            result_copy['status'] = 'SUCCESS'
                                            result_copy['message'] = 'Pasta digital gerada com sucesso'
                                        else:
                                            result_copy['async'] = False
                                            result_copy['task_id'] = None
                                            result_copy['message'] = 'Carregando documentos...'
                                        
                                        if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                            result_copy['paginas_geral'] = result_copy['total_paginas']
                                        if 'cod_norma' not in result_copy:
                                            result_copy['cod_norma'] = cod_norma_int
                                        
                                        documents_hash = _calculate_documents_hash(cod_norma_int, portal)
                                        documents_sizes = _calculate_documents_sizes(cod_norma_int, portal)
                                        _save_cache_to_filesystem(cod_norma_int, result_copy, current_time, documents_hash, documents_sizes)
                                        return result_copy
                        except Exception as view_err:
                            logger.error(f"[_get_pasta_data] Erro ao verificar documentos prontos (task recente): {view_err}", exc_info=True)
                    
                    # Se não há task recente, verifica cache de documentos prontos
                    if not has_recent_task:
                        cached_data = _load_cache_from_filesystem(cod_norma_int)
                        if cached_data:
                            if len(cached_data) == 4:
                                cached_docs, cache_timestamp, cached_hash, cached_sizes = cached_data
                            elif len(cached_data) == 3:
                                cached_docs, cache_timestamp, cached_hash = cached_data
                                cached_sizes = None
                            else:
                                cached_docs, cache_timestamp = cached_data
                                cached_hash = None
                                cached_sizes = None
                            
                            if current_time - cache_timestamp < _ready_documents_cache_ttl:
                                # CRÍTICO: Força recálculo do hash para garantir detecção de mudanças recentes
                                current_hash = _calculate_documents_hash(cod_norma_int, portal, force_recalculate=True)
                                
                                if cached_hash is None or current_hash is None:
                                    # Cache antigo sem hash ou não foi possível calcular hash atual
                                    _delete_cache_from_filesystem(cod_norma_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    _recent_tasks_cache.pop(cod_norma_str, None)
                                elif current_hash != cached_hash:
                                    # Hash mudou - documentos foram modificados, excluídos ou adicionados
                                    _delete_cache_from_filesystem(cod_norma_int)
                                    # Limpa cache de tasks recentes para forçar criação de nova task
                                    _recent_tasks_cache.pop(cod_norma_str, None)
                                    # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Limpa diretório do processo para forçar regeneração completa
                                    try:
                                        dir_base_cleanup = get_processo_norma_dir(cod_norma_int)
                                        if os.path.exists(dir_base_cleanup):
                                            shutil.rmtree(dir_base_cleanup, ignore_errors=True)
                                    except Exception as cleanup_err:
                                        logger.warning(f"[_get_pasta_data] Erro ao limpar diretório do processo: {cleanup_err}")
                                    # Não retorna do cache - continua para criar nova task
                                else:
                                    # Hash válido e igual - verifica se os arquivos ainda existem no filesystem
                                    # CRÍTICO: Mesmo com hash igual, sempre verifica metadados para detectar mudanças que o hash pode não capturar
                                    # (ex: arquivo adicionado que não estava no hash anterior, ou mudanças de tamanho que não alteram o hash)
                                    dir_base_check = get_processo_norma_dir(cod_norma_int)
                                    metadados_path = os.path.join(dir_base_check, 'documentos_metadados.json')
                                    
                                    # Verifica se os arquivos existem no filesystem
                                    if not os.path.exists(metadados_path):
                                        _delete_cache_from_filesystem(cod_norma_int)
                                        # CRÍTICO: Não retorna do cache - continua para criar nova task e mostrar monitor
                                        # Não entra no else abaixo, vai direto para criar task
                                    else:
                                        # CRÍTICO: Sempre compara com metadados, mesmo com hash igual
                                        # O hash pode não detectar todas as mudanças (ex: arquivo novo que não estava no hash anterior)
                                        has_changes_metadados, changes_details = _compare_documents_with_metadados(cod_norma_int, portal)
                                        
                                        if has_changes_metadados:
                                            # Mudanças detectadas mesmo com hash igual - arquivos foram adicionados, removidos ou modificados
                                            _delete_cache_from_filesystem(cod_norma_int)
                                            # Limpa cache de tasks recentes para forçar criação de nova task
                                            _recent_tasks_cache.pop(cod_norma_str, None)
                                            # Não retorna do cache - continua para criar nova task
                                            # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                            has_recent_task = False
                                            cached_task_id = None
                                            # Limpa diretório do processo para forçar regeneração completa
                                            try:
                                                dir_base_cleanup = get_processo_norma_dir(cod_norma_int)
                                                if os.path.exists(dir_base_cleanup):
                                                    shutil.rmtree(dir_base_cleanup, ignore_errors=True)
                                            except Exception as cleanup_err:
                                                logger.warning(f"[_get_pasta_data] Erro ao limpar diretório do processo: {cleanup_err}")
                                            # Não cria result_copy - continua para criar nova task
                                        else:
                                            # Hash válido e comparação com metadados corresponde - cache ainda é válido
                                            documentos_count_cached = len(cached_docs.get('documentos', [])) if isinstance(cached_docs, dict) else 0
                                            # Cria result_copy - comparação com metadados passou
                                            result_copy = copy.deepcopy(cached_docs)
            
                                            # Só processa result_copy se foi criado (tamanhos não mudaram ou não há cache para comparar)
                                            if result_copy is not None:
                                                # CRÍTICO: Verifica se há task recente no cache para mostrar monitor
                                                has_recent_task_for_monitor = False
                                                task_id_for_monitor = None
                                                if cod_norma_str in _recent_tasks_cache:
                                                    cached_task_id_check, cache_timestamp_check = _recent_tasks_cache[cod_norma_str]
                                                    time_since_cache_check = time.time() - cache_timestamp_check
                                                    if time_since_cache_check < 60.0:
                                                        has_recent_task_for_monitor = True
                                                        task_id_for_monitor = str(cached_task_id_check)
                                                
                                                if has_recent_task_for_monitor:
                                                    result_copy['async'] = True
                                                    result_copy['task_id'] = task_id_for_monitor
                                                    result_copy['status'] = 'SUCCESS'
                                                    result_copy['message'] = 'Pasta digital gerada com sucesso'
                                                else:
                                                    result_copy['async'] = False
                                                    result_copy['task_id'] = None
                                                    result_copy['message'] = 'Carregando documentos...'
                                                
                                                if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                                    result_copy['paginas_geral'] = result_copy['total_paginas']
                                                if 'cod_norma' not in result_copy:
                                                    result_copy['cod_norma'] = cod_norma_int
                                                
                                                return result_copy
                            else:
                                _delete_cache_from_filesystem(cod_norma_int)
                        
                        # Cache não encontrado ou expirado, verifica documentos no sistema
                        # Cache não encontrado ou expirado, verifica documentos no sistema
                        try:
                            # Usa serviço para obter documentos prontos
                            service = ProcessoNormaService(self.context, self.request)
                            result = service.get_documentos_prontos(cod_norma, skip_signature_check=True)
                            
                            # Se encontrou documentos prontos, verifica hash ANTES de retornar
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                documentos_count = len(result.get('documentos', []))
                                
                                # CRÍTICO: Calcula hash dos documentos ATUAIS antes de retornar (força recálculo)
                                # Isso garante que mudanças recentes sejam detectadas
                                current_documents_hash = _calculate_documents_hash(cod_norma_int, portal, force_recalculate=True)
                                
                                # Verifica se há hash em cache para comparar
                                should_return_documents = True
                                
                                # CRÍTICO: Compara usando documentos_metadados.json (única fonte de verdade)
                                # Sempre executa comparação, mesmo com hash igual, para detectar mudanças que o hash pode não capturar
                                # (ex: arquivo adicionado que não estava no hash anterior)
                                has_changes_metadados, changes_details = _compare_documents_with_metadados(cod_norma_int, portal)
                                
                                if has_changes_metadados:
                                    # Mudanças detectadas ou JSON não existe - precisa regenerar
                                    
                                    # Verifica se há task ativa antes de criar nova task (evita criar tasks duplicadas)
                                    try:
                                        service_check = ProcessoNormaService(self.context, self.request)
                                        has_active_task_check, task_id_check, task_status_check = service_check.verificar_tasks_ativas(cod_norma_int)
                                        if has_active_task_check:
                                            # Não cria nova task - aguarda task atual completar
                                            should_return_documents = False
                                            has_recent_task = True
                                            cached_task_id = task_id_check
                                            # Não limpa cache - mantém task ativa
                                        else:
                                            # Limpa cache de tasks recentes para forçar criação de nova task
                                            _recent_tasks_cache.pop(cod_norma_str, None)
                                            # Limpa cache de documentos
                                            _delete_cache_from_filesystem(cod_norma_int)
                                            should_return_documents = False
                                            # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                            has_recent_task = False
                                            cached_task_id = None
                                    except Exception as check_task_err:
                                        logger.warning(f"[_get_pasta_data] Erro ao verificar tasks ativas: {check_task_err}, assumindo que precisa criar nova task")
                                        # Em caso de erro, assume que precisa criar nova task
                                        _recent_tasks_cache.pop(cod_norma_str, None)
                                        _delete_cache_from_filesystem(cod_norma_int)
                                        should_return_documents = False
                                        has_recent_task = False
                                        cached_task_id = None
                                else:
                                    # Comparação com metadados corresponde - documentos prontos estão atualizados
                                    should_return_documents = True
                                
                                # Se hash corresponde (ou não havia cache), retorna os documentos prontos
                                if should_return_documents:
                                    # CRÍTICO: Cria uma cópia profunda para evitar problemas de referência compartilhada
                                    result_copy = copy.deepcopy(result)
                                    
                                    # CRÍTICO: Verifica se há task recente no cache para mostrar monitor
                                    has_recent_task_for_monitor = False
                                    task_id_for_monitor = None
                                    if cod_norma_str in _recent_tasks_cache:
                                        cached_task_id_check, cache_timestamp_check = _recent_tasks_cache[cod_norma_str]
                                        time_since_cache_check = time.time() - cache_timestamp_check
                                        if time_since_cache_check < 60.0:
                                            has_recent_task_for_monitor = True
                                            task_id_for_monitor = str(cached_task_id_check)
                                    
                                    if has_recent_task_for_monitor:
                                        result_copy['async'] = True
                                        result_copy['task_id'] = task_id_for_monitor
                                        result_copy['status'] = 'SUCCESS'
                                        result_copy['message'] = 'Pasta digital gerada com sucesso'
                                    else:
                                        result_copy['async'] = False
                                        result_copy['task_id'] = None
                                        result_copy['message'] = 'Carregando documentos...'
                                    
                                    # Garante campos obrigatórios
                                    if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                        result_copy['paginas_geral'] = result_copy['total_paginas']
                                    if 'cod_norma' not in result_copy:
                                        result_copy['cod_norma'] = cod_norma_int
                                    
                                    # CRÍTICO: Atualiza cache com hash e tamanhos calculados (apenas filesystem)
                                    documents_sizes = _calculate_documents_sizes(cod_norma_int, portal)
                                    _save_cache_to_filesystem(cod_norma_int, result_copy, current_time, current_documents_hash, documents_sizes)
                                    
                                    return result_copy
                                else:
                                    # Documentos prontos não correspondem (quantidade, hash ou tamanhos), não retorna - continua para criar nova task
                                    # Limpa cache de tasks recentes para forçar criação de nova task
                                    _recent_tasks_cache.pop(cod_norma_str, None)
                                    # Limpa cache de documentos (já foi limpo antes, mas garantindo)
                                    _delete_cache_from_filesystem(cod_norma_int)
                                    # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                        except Exception as check_err:
                            logger.warning(f"[_get_pasta_data] Erro ao verificar documentos prontos (sem task recente): {check_err}, continuando para criar nova task")
                    
                    # Se não há task recente, cria nova task
                    if not has_recent_task:
                        try:
                            dir_hash = hashlib.md5(str(cod_norma_int).encode()).hexdigest()
                            prefix = f"{TEMP_DIR_PREFIX_NORMA}{dir_hash}"
                            install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
                            temp_base = os.path.abspath(os.path.join(install_home, 'var', 'tmp'))
                            dir_base = secure_path_join(temp_base, prefix)
                            
                            if os.path.exists(dir_base):
                                shutil.rmtree(dir_base, ignore_errors=True)
                            
                            _delete_cache_from_filesystem(cod_norma_int)
                        except Exception as cleanup_err:
                            logger.warning(f"[_get_pasta_data] Erro ao apagar diretório (continuando mesmo assim): {cleanup_err}")
                        
                        # Usa lock por cod_norma para evitar criação simultânea
                        with _locks_lock:
                            if cod_norma_str not in _task_creation_locks:
                                _task_creation_locks[cod_norma_str] = threading.Lock()
                            task_lock = _task_creation_locks[cod_norma_str]
                        
                        with task_lock:
                            dir_base_double_check = get_processo_norma_dir(cod_norma_int)
                            if not os.path.exists(dir_base_double_check):
                                _recent_tasks_cache.pop(cod_norma_str, None)
                                _delete_cache_from_filesystem(cod_norma_int)
                            else:
                                if cod_norma_str in _recent_tasks_cache:
                                    cached_task_id, cache_timestamp = _recent_tasks_cache[cod_norma_str]
                                    if time.time() - cache_timestamp < cache_ttl:
                                        try:
                                            service_status = ProcessoNormaService(self.context, self.request)
                                            task_status_detail = service_status.verificar_task_status(cached_task_id)
                                            if task_status_detail:
                                                base_response.update({
                                                    'task_id': str(cached_task_id),
                                                    'status': task_status_detail.get('status', 'PENDING'),
                                                    'message': task_status_detail.get('message', 'Tarefa recém-criada, aguardando processamento'),
                                                })
                                                if 'current' in task_status_detail:
                                                    base_response['current'] = task_status_detail['current']
                                                if 'total' in task_status_detail:
                                                    base_response['total'] = task_status_detail['total']
                                                if 'stage' in task_status_detail:
                                                    base_response['stage'] = task_status_detail['stage']
                                            else:
                                                base_response.update({
                                                    'task_id': str(cached_task_id),
                                                    'status': 'PENDING',
                                                    'message': 'Tarefa recém-criada, aguardando processamento'
                                                })
                                        except Exception as status_err:
                                            base_response.update({
                                                'task_id': str(cached_task_id),
                                                'status': 'PENDING',
                                                'message': 'Tarefa recém-criada, aguardando processamento'
                                            })
                                        return base_response
                            
                            # Usa serviço para criar task assíncrona
                            service = ProcessoNormaService(self.context, self.request)
                            result = service.criar_task_async(cod_norma_int, portal_url)
                            
                            if result and isinstance(result, dict) and 'task_id' in result:
                                new_task_id = str(result.get('task_id'))
                                _recent_tasks_cache[cod_norma_str] = (new_task_id, time.time())
                                if len(_recent_tasks_cache) > 20:
                                    sorted_items = sorted(_recent_tasks_cache.items(), key=lambda x: x[1][1])
                                    for key, _ in sorted_items[:-20]:
                                        _recent_tasks_cache.pop(key, None)
                                
                                try:
                                    service_status = ProcessoNormaService(self.context, self.request)
                                    task_status_detail = service_status.verificar_task_status(new_task_id)
                                    if task_status_detail:
                                        task_real_status = task_status_detail.get('status', 'PENDING')
                                        if task_real_status in ('PENDING', 'PROGRESS', 'STARTED'):
                                            base_response.update({
                                                'task_id': new_task_id,
                                                'status': task_real_status,
                                                'message': task_status_detail.get('message', 'Regenerando pasta digital...'),
                                                'async': True
                                            })
                                            if 'current' in task_status_detail:
                                                base_response['current'] = task_status_detail['current']
                                            if 'total' in task_status_detail:
                                                base_response['total'] = task_status_detail['total']
                                            if 'stage' in task_status_detail:
                                                base_response['stage'] = task_status_detail['stage']
                                            return base_response
                                except Exception as status_check_err:
                                    pass
                                
                                time.sleep(0.2)
                                
                                try:
                                    check_result = service.get_documentos_prontos(cod_norma, skip_signature_check=True)
                                    
                                    if isinstance(check_result, dict) and 'documentos' in check_result and len(check_result.get('documentos', [])) > 0:
                                        try:
                                            service_status = ProcessoNormaService(self.context, self.request)
                                            task_status_detail = service_status.verificar_task_status(new_task_id)
                                            if task_status_detail:
                                                task_real_status = task_status_detail.get('status', 'PENDING')
                                                if task_real_status in ('PENDING', 'PROGRESS', 'STARTED'):
                                                    result_copy = copy.deepcopy(check_result)
                                                    result_copy['async'] = True
                                                    result_copy['task_id'] = new_task_id
                                                    result_copy['status'] = task_real_status
                                                    result_copy['message'] = task_status_detail.get('message', 'Processando pasta digital...')
                                                    if 'current' in task_status_detail:
                                                        result_copy['current'] = task_status_detail['current']
                                                    if 'total' in task_status_detail:
                                                        result_copy['total'] = task_status_detail['total']
                                                    if 'stage' in task_status_detail:
                                                        result_copy['stage'] = task_status_detail['stage']
                                                    if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                                        result_copy['paginas_geral'] = result_copy['total_paginas']
                                                    if 'cod_norma' not in result_copy:
                                                        result_copy['cod_norma'] = cod_norma_int
                                                    return result_copy
                                                elif task_real_status == 'SUCCESS':
                                                    result_copy = copy.deepcopy(check_result)
                                                    result_copy['async'] = True
                                                    result_copy['task_id'] = new_task_id
                                                    result_copy['status'] = 'SUCCESS'
                                                    result_copy['message'] = 'Pasta digital gerada com sucesso'
                                                    if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                                        result_copy['paginas_geral'] = result_copy['total_paginas']
                                                    if 'cod_norma' not in result_copy:
                                                        result_copy['cod_norma'] = cod_norma_int
                                                    documents_hash = _calculate_documents_hash(cod_norma_int, portal)
                                                    documents_sizes = _calculate_documents_sizes(cod_norma_int, portal)
                                                    _save_cache_to_filesystem(cod_norma_int, result_copy, time.time(), documents_hash, documents_sizes)
                                                    return result_copy
                                        except Exception as status_check_err:
                                            pass
                                        
                                        result_copy = copy.deepcopy(check_result)
                                        result_copy['async'] = True
                                        result_copy['task_id'] = new_task_id
                                        result_copy['status'] = 'SUCCESS'
                                        result_copy['message'] = 'Pasta digital gerada com sucesso'
                                        if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                            result_copy['paginas_geral'] = result_copy['total_paginas']
                                        if 'cod_norma' not in result_copy:
                                            result_copy['cod_norma'] = cod_norma_int
                                        documents_hash = _calculate_documents_hash(cod_norma_int, portal)
                                        documents_sizes = _calculate_documents_sizes(cod_norma_int, portal)
                                        _save_cache_to_filesystem(cod_norma_int, result_copy, time.time(), documents_hash, documents_sizes)
                                        return result_copy
                                except Exception as check_err:
                                    logger.warning(f"[_get_pasta_data] Erro ao verificar documentos prontos após criar task: {check_err}", exc_info=True)
                                
                                try:
                                    service_status = ProcessoNormaService(self.context, self.request)
                                    task_status_detail = service_status.verificar_task_status(new_task_id)
                                    if task_status_detail:
                                        base_response.update({
                                            'task_id': new_task_id,
                                            'status': task_status_detail.get('status', result.get('status', 'PENDING')),
                                            'message': task_status_detail.get('message', result.get('message', 'Regenerando pasta digital...')),
                                            'async': True
                                        })
                                        if 'current' in task_status_detail:
                                            base_response['current'] = task_status_detail['current']
                                        if 'total' in task_status_detail:
                                            base_response['total'] = task_status_detail['total']
                                        if 'stage' in task_status_detail:
                                            base_response['stage'] = task_status_detail['stage']
                                    else:
                                        base_response.update({
                                            'task_id': new_task_id,
                                            'status': str(result.get('status', 'PENDING')),
                                        'message': result.get('message', 'Regenerando pasta digital...'),
                                        'async': True
                                    })
                                except Exception as status_err:
                                    base_response.update({
                                        'task_id': new_task_id,
                                        'status': str(result.get('status', 'PENDING')),
                                        'message': result.get('message', 'Regenerando pasta digital...'),
                                        'async': True
                                    })
                                return base_response
                            else:
                                logger.error(f"[_get_pasta_data] Serviço não conseguiu criar task assíncrona")
                                base_response['error'] = 'Falha ao criar task assíncrona'
                                return base_response
                    
                except Exception as async_err:
                    logger.error(f"[_get_pasta_data] Erro no processamento assíncrono: {async_err}", exc_info=True)
                    base_response.update({
                        'error': f'Erro ao processar: {str(async_err)}',
                        'error_type': async_err.__class__.__name__,
                        'error_trace': traceback.format_exc()[:500]
                    })
                    return base_response
            
            # Para outras actions, processa síncrono
            else:
                try:
                    service = ProcessoNormaService(self.context, self.request)
                    result = service.get_documentos_prontos(cod_norma, skip_signature_check=False)
                    
                    if isinstance(result, dict):
                        result['async'] = False
                        result['message'] = 'Processamento síncrono concluído'
                        if 'paginas_geral' not in result and 'total_paginas' in result:
                            result['paginas_geral'] = result['total_paginas']
                        if 'cod_norma' not in result:
                            result['cod_norma'] = cod_norma
                        return result
                    else:
                        logger.error(f"[_get_pasta_data] Resultado síncrono inválido: {type(result)}")
                        base_response.update({
                            'async': False,
                            'error': f'Resultado inesperado: {type(result)}'
                        })
                        return base_response
                except Exception as sync_err:
                    logger.error(f"[_get_pasta_data] Erro no processamento síncrono: {sync_err}")
                    base_response.update({
                        'async': False,
                        'error': str(sync_err),
                        'error_type': sync_err.__class__.__name__
                    })
                    return base_response
                    
        except Exception as e:
            logger.error(f"[_get_pasta_data] Erro geral: {e}", exc_info=True)
            return {
                'async': True,
                'error': str(e),
                'documentos': [],
                'cod_norma': cod_norma,
                'paginas_geral': 0,
                'message': 'Erro ao processar pasta digital'
            }
    
    def _get_portal_config(self, portal):
        """Obtém configurações do portal"""
        try:
            if hasattr(portal, 'sapl_documentos'):
                props = portal.sapl_documentos.props_sagl
                return {
                    'nom_casa': props.getProperty('nom_casa', ''),
                    'reuniao_sessao': props.getProperty('reuniao_sessao', '')
                }
            return {}
        except Exception as e:
            logger.error(f"Erro ao obter configurações do portal: {e}", exc_info=True)
            return {}
    
    def _get_materias_relacionadas(self, cod_norma, portal):
        """Obtém matérias relacionadas à norma (a matéria que originou a norma)"""
        try:
            session = self._get_session()
            try:
                # OTIMIZAÇÃO: Usa cache de norma se disponível
                if hasattr(self, '_get_norma_cached'):
                    result = self._get_norma_cached(cod_norma)
                    norma = result[0] if result else None
                else:
                    norma = session.query(NormaJuridica)\
                        .filter(NormaJuridica.cod_norma == cod_norma)\
                        .filter(NormaJuridica.ind_excluido == 0)\
                        .first()
                
                if not norma or not norma.cod_materia:
                    return []
                
                # Busca a matéria que originou a norma
                materia_result = session.query(MateriaLegislativa, TipoMateriaLegislativa)\
                    .join(TipoMateriaLegislativa, 
                          MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                    .filter(MateriaLegislativa.cod_materia == norma.cod_materia)\
                    .filter(MateriaLegislativa.ind_excluido == 0)\
                    .first()
                
                if not materia_result:
                    return []
                
                materia_obj, tipo_obj = materia_result
                
                return [{
                    'cod_materia': materia_obj.cod_materia,
                    'tipo': tipo_obj.sgl_tipo_materia,
                    'numero': materia_obj.num_ident_basica,
                    'ano': materia_obj.ano_ident_basica,
                    'id_exibicao': f"{tipo_obj.sgl_tipo_materia} {materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica}"
                }]
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Erro ao obter matérias relacionadas: {e}", exc_info=True)
            return []
    
    def _get_normas_relacionadas(self, cod_norma, portal):
        """Obtém normas relacionadas (vinculadas)"""
        try:
            session = self._get_session()
            try:
                from sqlalchemy import or_
                
                # Busca normas onde cod_norma é referente (normas que esta norma referencia)
                vinculos_referente = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referida == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referente == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                # Busca normas onde cod_norma é referida (normas que referenciam esta norma)
                vinculos_referida = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_referente == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma_referida == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                normas_list = []
                # Adiciona normas referenciadas por esta norma
                for vinculo_obj, norma_obj, tipo_obj in vinculos_referente:
                    normas_list.append({
                        'cod_norma': norma_obj.cod_norma,
                        'tipo': tipo_obj.sgl_tipo_norma,
                        'numero': norma_obj.num_norma,
                        'ano': norma_obj.ano_norma,
                        'id_exibicao': f"{tipo_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma}"
                    })
                
                # Adiciona normas que referenciam esta norma
                for vinculo_obj, norma_obj, tipo_obj in vinculos_referida:
                    normas_list.append({
                        'cod_norma': norma_obj.cod_norma,
                        'tipo': tipo_obj.sgl_tipo_norma,
                        'numero': norma_obj.num_norma,
                        'ano': norma_obj.ano_norma,
                        'id_exibicao': f"{tipo_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma}"
                    })
                
                return normas_list
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Erro ao obter normas relacionadas: {e}", exc_info=True)
            return []


class PastaDigitalNormaView(PastaDigitalNormaMixin, grok.View):
    """View que renderiza o HTML da pasta digital de normas diretamente"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pasta_digital_norma')

    def update(self):
        """Método update do Grok - garante que headers sejam definidos"""
        self.request.RESPONSE.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.request.RESPONSE.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.request.RESPONSE.setHeader('Pragma', 'no-cache')
        self.request.RESPONSE.setHeader('Expires', '0')

    def __call__(self):
        """Intercepta a chamada para escrever HTML diretamente na resposta"""
        self.update()
        html = self.render()
        
        if not isinstance(html, str):
            html = str(html)
        
        self.request.RESPONSE.setHeader('Content-Type', 'text/html; charset=utf-8')
        
        if isinstance(html, str):
            html_bytes = html.encode('utf-8')
        else:
            html_bytes = html
        
        self.request.RESPONSE.setBody(html_bytes)
        return ''

    def render(self):
        """Renderiza HTML da pasta digital com dados já incluídos"""
        try:
            cod_norma = self.request.form.get('cod_norma') or self.request.get('cod_norma')
            action = self.request.form.get('action', 'pasta')
            
            if not cod_norma:
                return self._render_error('Parâmetro cod_norma é obrigatório')
            
            # Obtém todos os dados
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            tool = getToolByName(self.context, 'portal_sagl')
            
            norma_data = self._get_norma_data(cod_norma)
            pasta_data = self._get_pasta_data(cod_norma, action, tool, portal)
            # Garante que pasta_data nunca seja None
            if pasta_data is None:
                pasta_data = {
                    'error': 'Erro ao obter dados da pasta',
                    'async': False,
                    'documentos': []
                }
            portal_config = self._get_portal_config(portal)
            materias_relacionadas = self._get_materias_relacionadas(cod_norma, portal)
            normas_relacionadas = self._get_normas_relacionadas(cod_norma, portal)
            
            # Renderiza HTML com os dados
            html_result = self._render_html(
                cod_norma, action, norma_data, pasta_data, 
                portal_config, materias_relacionadas, normas_relacionadas, 
                str(portal.absolute_url())
            )
            
            # Validação final
            if isinstance(html_result, str):
                # Verifica pasta:null e corrige
                if '"pasta":null' in html_result:
                    logger.warning(f"[render] Encontrado 'pasta':null, corrigindo...")
                    html_result = html_result.replace('"pasta":null', '"pasta":{}')
                if '"pasta": null' in html_result:
                    logger.warning(f"[render] Encontrado 'pasta': null, corrigindo...")
                    html_result = html_result.replace('"pasta": null', '"pasta": {}')
            
            return html_result
            
        except Exception as e:
            logger.error(f"Erro ao renderizar pasta digital: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return self._render_error(str(e))
    
    def _render_error(self, error_msg):
        """Renderiza página de erro"""
        return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <title>Erro - Pasta Digital</title>
</head>
<body>
    <h1>Erro</h1>
    <p>{error_msg}</p>
</body>
</html>"""
    
    def _render_html(self, cod_norma, action, norma, pasta, portal_config, 
                    materias_relacionadas, normas_relacionadas, portal_url):
        """Renderiza o HTML completo da pasta digital"""
        # Garante que cod_norma e portal_url são strings válidas
        cod_norma_str = str(cod_norma).strip() if cod_norma else ''
        portal_url_str = str(portal_url).strip() if portal_url else ''
        
        # GARANTIA ABSOLUTA: pasta nunca é None/null
        if pasta is None:
            logger.warning(f"[_render_html] pasta is None, FORÇANDO dict vazio")
            pasta = {}
        elif not isinstance(pasta, dict):
            logger.warning(f"[_render_html] pasta não é dict ({type(pasta)}), convertendo para dict")
            pasta = {}
        
        # Garante que todos os valores None sejam convertidos para valores válidos
        # Dados específicos para template de normas (independente de matérias)
        data_dict = {
            'cod_norma': cod_norma_str,
            'action': str(action) if action else 'pasta',
            'is_norma': True,  # Flag para indicar que é uma norma
            'norma': norma if norma is not None else {},
            'pasta': pasta,  # Já garantido que é um dict válido
            'portal_config': portal_config if portal_config is not None else {},
            'materias_relacionadas': materias_relacionadas if materias_relacionadas is not None else [],
            'normas_relacionadas': normas_relacionadas if normas_relacionadas is not None else [],
            'portal_url': portal_url_str
        }
        
        # Serializa o JSON com encoder customizado
        data_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder)
        
        # Verifica múltiplas formas de "pasta":null
        pasta_null_variations = [
            '"pasta":null',
            '"pasta": null', 
            '"pasta" :null',
            '"pasta" : null',
            "'pasta':null",
            "'pasta': null",
            'pasta:null',
            'pasta: null'
        ]
        
        pasta_found_as_null = any(variation in data_json for variation in pasta_null_variations)
        
        # Se encontrou pasta:null, CORRIGE IMEDIATAMENTE
        if pasta_found_as_null:
            logger.error(f"[_render_html] ERRO CRÍTICO: JSON contém pasta:null!")
            for variation in pasta_null_variations:
                if variation in data_json:
                    replacement = variation.split(':')[0] + ':{}'
                    data_json = data_json.replace(variation, replacement)
            
            # Se após substituições ainda tem pasta:null, força reconstrução
            if any(variation in data_json for variation in pasta_null_variations):
                logger.error(f"[_render_html] pasta:null persiste após substituições, RECONSTRUINDO...")
                data_dict['pasta'] = {}
                data_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder)
        
        # Carrega template específico para normas (independente de matérias)
        import pkg_resources
        template_path = None
        try:
            dist = pkg_resources.get_distribution('openlegis.sagl')
            template_path = os.path.join(
                dist.location, 'openlegis', 'sagl', 'skins', 'consultas', 'norma_juridica',
                'pasta_digital', 'index_html.html'
            )
            
            if not os.path.exists(template_path):
                template_path = os.path.join(
                    os.path.dirname(__file__),
                    '..', '..', 'skins', 'consultas', 'norma_juridica',
                    'pasta_digital', 'index_html.html'
                )
        except Exception:
            pass
        
        # Se template existe, usa ele
        if template_path and os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                
                # Preenche links de favicon e CSS
                if portal_url_str:
                    favicon_filename = 'logo_casa.gif'
                    if portal_config and portal_config.get('id_logo'):
                        favicon_filename = portal_config.get('id_logo', 'logo_casa.gif')
                    
                    favicon_url = f"{portal_url_str}/sapl_documentos/props_sagl/{favicon_filename}"
                    html = html.replace('<link rel="shortcut icon" type="image/x-icon" href="" id="favicon">', 
                                      f'<link rel="shortcut icon" type="image/x-icon" href="{favicon_url}" id="favicon">')
                    
                    css_bootstrap_url = f"{portal_url_str}/assets/css/bootstrap.min.css"
                    css_icons_url = f"{portal_url_str}/assets/css/icons.min.css"
                    css_app_url = f"{portal_url_str}/assets/css/app.css"
                    css_all_url = f"{portal_url_str}/css/all.min.css"
                    
                    html = html.replace('<link rel="stylesheet" href="" id="css-bootstrap">',
                                      f'<link rel="stylesheet" href="{css_bootstrap_url}" id="css-bootstrap">')
                    html = html.replace('<link rel="stylesheet" href="" id="css-icons">',
                                      f'<link rel="stylesheet" href="{css_icons_url}" id="css-icons">')
                    html = html.replace('<link rel="stylesheet" href="" id="css-app">',
                                      f'<link rel="stylesheet" href="{css_app_url}" id="css-app">')
                    html = html.replace('<link rel="stylesheet" href="" id="css-all">',
                                      f'<link rel="stylesheet" href="{css_all_url}" id="css-all">')
                
                # Template específico para normas - não precisa de adaptação
                # O template já está configurado para usar endpoints de normas
                
                # Injeta APP_DATA no template
                patterns = [
                    'let APP_DATA = {',
                    'var APP_DATA = {', 
                    'const APP_DATA = {',
                    'let APP_DATA={',
                    'var APP_DATA={',
                    'const APP_DATA={',
                    'APP_DATA = {',
                    'APP_DATA={'
                ]
                
                start_idx = -1
                pattern_found = None
                
                for pattern in patterns:
                    start_idx = html.find(pattern)
                    if start_idx != -1:
                        pattern_found = pattern
                        break
                
                if start_idx != -1:
                    # Encontra o fechamento correspondente
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    string_char = None
                    end_idx = -1
                    search_start = start_idx + len(pattern_found)
                    
                    for i in range(search_start, len(html)):
                        char = html[i]
                        
                        if escape_next:
                            escape_next = False
                            continue
                            
                        if char == '\\':
                            escape_next = True
                            continue
                            
                        if (char == '"' or char == "'") and not in_string:
                            in_string = True
                            string_char = char
                            continue
                        elif char == string_char and in_string:
                            in_string = False
                            string_char = None
                            continue
                            
                        if in_string:
                            continue
                            
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            if brace_count == 0:
                                end_idx = i + 1
                                while end_idx < len(html) and html[end_idx] in ' \n\t\r':
                                    end_idx += 1
                                if end_idx < len(html) and html[end_idx] == ';':
                                    end_idx += 1
                                break
                            brace_count -= 1
                    
                    if end_idx > start_idx:
                        injected_code = f'let APP_DATA = {data_json}; // Dados injetados pelo servidor'
                        html = html[:start_idx] + injected_code + html[end_idx:]
                else:
                    # Fallback: injeta no início do primeiro script
                    script_start = html.find('<script>')
                    if script_start != -1:
                        injected_code = f'let APP_DATA = {data_json}; // Dados injetados pelo servidor\n        '
                        html = html[:script_start + 8] + injected_code + html[script_start + 8:]
                
                # Validação final
                for variation in pasta_null_variations[:4]:
                    if variation in html:
                        logger.error(f"[_render_html] ENCONTRADO {variation} no HTML final, corrigindo...")
                        replacement = variation.split(':')[0] + ':{}'
                        html = html.replace(variation, replacement)
                
                return html
            except Exception as e:
                logger.error(f"Erro ao ler template HTML: {e}", exc_info=True)
        
        # Fallback: retorna HTML básico com dados JSON
        safe_data_json = data_json
        for variation in pasta_null_variations:
            if variation in safe_data_json:
                replacement = variation.split(':')[0] + ':{}'
                safe_data_json = safe_data_json.replace(variation, replacement)
        
        return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pasta Digital - {norma.get('id_exibicao', 'Norma') if norma else 'Norma'}</title>
    <link rel="stylesheet" href="{portal_url_str}/assets/css/bootstrap.min.css">
    <link rel="stylesheet" href="{portal_url_str}/assets/css/icons.min.css">
    <link rel="stylesheet" href="{portal_url_str}/assets/css/app.css">
</head>
<body>
    <div id="app"></div>
    <script>
        let APP_DATA = {safe_data_json};
    </script>
    <script src="{portal_url_str}/assets/js/pasta-digital.js"></script>
</body>
</html>"""


class PastaDigitalNormaDataView(PastaDigitalNormaMixin, grok.View):
    """View que retorna JSON com todos os dados necessários para a página de pasta digital de normas"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pasta_digital_norma_data')

    def render(self):
        """Retorna JSON com dados da pasta digital de normas"""
        self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
        
        try:
            cod_norma = self.request.form.get('cod_norma') or self.request.get('cod_norma')
            action = self.request.form.get('action', 'pasta')
            
            if not cod_norma:
                return json.dumps({
                    'error': 'Parâmetro cod_norma é obrigatório',
                    'success': False
                }, cls=DateTimeJSONEncoder)
            
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            tool = getToolByName(self.context, 'portal_sagl')
            
            norma_data = self._get_norma_data(cod_norma)
            pasta_data = self._get_pasta_data(cod_norma, action, tool, portal)
            portal_config = self._get_portal_config(portal)
            materias_relacionadas = self._get_materias_relacionadas(cod_norma, portal)
            normas_relacionadas = self._get_normas_relacionadas(cod_norma, portal)
            
            response = {
                'success': True,
                'cod_norma': cod_norma,
                'action': action,
                'norma': norma_data,
                'pasta': pasta_data,
                'portal_config': portal_config,
                'materias_relacionadas': materias_relacionadas,
                'normas_relacionadas': normas_relacionadas,
                'portal_url': str(portal.absolute_url())
            }
            
            return json.dumps(response, ensure_ascii=False, cls=DateTimeJSONEncoder)
            
        except Exception as e:
            logger.error(f"Erro ao obter dados da pasta digital de normas: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return json.dumps({
                'error': str(e),
                'success': False
            }, ensure_ascii=False, cls=DateTimeJSONEncoder)


class ProcessoNormaDownloadDocumentoView(PastaDigitalNormaMixin, grok.View):
    """View para download de documentos individuais da pasta digital de normas"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_norma_download_documento')
    
    def render(self):
        try:
            # Extrai parâmetros
            cod_norma_str = self.request.form.get('cod_norma') or self.request.get('cod_norma')
            filename = self.request.form.get('file') or self.request.get('file')
            title = self.request.form.get('title') or self.request.get('title') or ''
            
            if not cod_norma_str or not filename:
                self.request.response.setStatus(400)
                return "Parâmetros cod_norma e file são obrigatórios"
            
            # Valida filename (segurança - evita path traversal)
            if '..' in filename or '/' in filename or '\\' in filename:
                self.request.response.setStatus(400)
                return "Nome de arquivo inválido"
            
            cod_norma_int = int(cod_norma_str)
            
            # IMPORTANTE: Busca sempre no filesystem (diretório da pasta digital)
            # Se o usuário conseguiu abrir a pasta digital, já tem permissão adequada
            # Todos os arquivos da pasta digital são copiados para o diretório durante a geração
            
            file_content = self._get_file_from_pasta_dir(cod_norma_int, filename)
            
            if file_content is None:
                self.request.response.setStatus(404)
                return "Arquivo não encontrado"
            
            # Define nome do arquivo para download: usa título se disponível, senão usa filename
            if title:
                # Sanitiza título para nome de arquivo seguro
                import re
                safe_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', title)
                safe_filename = safe_filename[:100]  # Limita tamanho
                # Adiciona extensão do arquivo original
                extension = '.pdf'
                if '.' in filename:
                    extension = '.' + filename.rsplit('.', 1)[-1].lower()
                safe_filename = safe_filename + extension
            else:
                safe_filename = filename.replace(' ', '_')  # Nome seguro para download
            
            content_type = 'application/pdf'
            
            self.request.response.setHeader('Content-Type', content_type)
            self.request.response.setHeader(
                'Content-Disposition',
                f'attachment; filename="{safe_filename}"'
            )
            self.request.response.setHeader('Content-Length', str(len(file_content)))
            
            return file_content
            
        except ValueError:
            self.request.response.setStatus(400)
            return "Parâmetro cod_norma inválido"
        except Exception as e:
            logger.error(f"[processo_norma_download_documento] Erro: {e}", exc_info=True)
            self.request.response.setStatus(500)
            return f"Erro ao baixar documento: {str(e)}"
    
    def _get_file_from_pasta_dir(self, cod_norma, filename):
        """
        Obtém arquivo do diretório da pasta digital no filesystem.
        
        IMPORTANTE: O 'filename' vem do campo 'file' do cache.json, que contém
        o nome do arquivo original (ex: "capa_DM-5779-2025.pdf", "20038_texto_integral.pdf").
        
        Esses arquivos são copiados para o diretório pasta_digital/{cod_norma}/ durante a geração.
        """
        try:
            dir_base = get_processo_norma_dir(cod_norma)
            
            # Tenta primeiro no diretório raiz com o nome exato do arquivo
            file_path = os.path.join(dir_base, filename)
            
            # Validação adicional de segurança: garante que o arquivo está dentro do diretório
            # Resolve caminho absoluto para evitar path traversal
            dir_base_abs = os.path.abspath(dir_base)
            file_path_abs = os.path.abspath(file_path)
            
            if not file_path_abs.startswith(dir_base_abs):
                logger.warning(f"[_get_file_from_pasta_dir] Tentativa de path traversal: {filename}")
                return None
            
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                logger.debug(f"[_get_file_from_pasta_dir] Arquivo não encontrado no diretório raiz: {file_path}")
                
                # Para capa, tenta gerar dinamicamente
                if filename.startswith('capa_'):
                    logger.debug(f"[_get_file_from_pasta_dir] Tentando gerar capa dinamicamente: {filename}")
                    file_content = self._get_capa_dinamica(cod_norma, filename, dir_base)
                    if file_content:
                        return file_content
                
                # Se não encontrou, tenta buscar o arquivo original no ZODB e salvar no diretório
                # Isso permite que arquivos sejam baixados mesmo se não foram copiados durante a geração
                logger.debug(f"[_get_file_from_pasta_dir] Tentando buscar arquivo original no ZODB: {filename}")
                file_content = self._get_file_from_zodb_and_save(cod_norma, filename, dir_base)
                if file_content:
                    return file_content
                
                return None
            
            # Lê arquivo do filesystem
            with open(file_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"[_get_file_from_pasta_dir] Erro ao obter {filename} do diretório: {e}", exc_info=True)
            return None
    
    def _get_file_from_zodb_and_save(self, cod_norma, filename, dir_base):
        """
        Busca arquivo no ZODB e salva no diretório para uso futuro.
        Usa o mesmo método que a geração da pasta digital usa para copiar arquivos.
        """
        try:
            from Products.CMFCore.utils import getToolByName
            from openlegis.sagl.browser.processo_norma.processo_norma_utils import safe_check_file
            
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            
            if not hasattr(portal, 'sapl_documentos'):
                return None
            
            # Determina o container baseado no nome do arquivo
            container = None
            
            # Texto integral da norma
            if filename.endswith('_texto_integral.pdf'):
                if hasattr(portal.sapl_documentos, 'norma_juridica'):
                    container = portal.sapl_documentos.norma_juridica
            # Texto consolidado
            elif filename.endswith('_texto_consolidado.pdf'):
                if hasattr(portal.sapl_documentos, 'norma_juridica'):
                    container = portal.sapl_documentos.norma_juridica
            # Capa
            elif filename.startswith('capa_'):
                # Capa é gerada dinamicamente, não está no ZODB
                return None
            # Anexos
            elif '_anexo_' in filename:
                if hasattr(portal.sapl_documentos, 'norma_juridica'):
                    container = portal.sapl_documentos.norma_juridica
            # Matéria relacionada
            elif hasattr(portal.sapl_documentos, 'materia'):
                # Pode ser matéria relacionada
                container = portal.sapl_documentos.materia
            
            if not container:
                logger.debug(f"[_get_file_from_zodb_and_save] Container não identificado para: {filename}")
                return None
            
            # Verifica se arquivo existe no container
            if not safe_check_file(container, filename):
                logger.debug(f"[_get_file_from_zodb_and_save] Arquivo não existe no ZODB: {filename}")
                return None
            
            # Lê arquivo do ZODB
            if not hasattr(container, filename):
                return None
            
            file_obj = getattr(container, filename)
            
            # Extrai dados do arquivo
            if hasattr(file_obj, 'data'):
                file_content = file_obj.data
            elif hasattr(file_obj, 'read'):
                file_obj.seek(0)
                file_content = file_obj.read()
            else:
                return None
            
            if not file_content:
                return None
            
            # Salva no diretório para uso futuro
            try:
                file_path = os.path.join(dir_base, filename)
                os.makedirs(dir_base, mode=0o700, exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                logger.info(f"[_get_file_from_zodb_and_save] Arquivo copiado do ZODB e salvo: {filename}")
            except Exception as save_err:
                logger.warning(f"[_get_file_from_zodb_and_save] Erro ao salvar arquivo no diretório: {save_err}")
                # Continua mesmo se não conseguir salvar
            
            return file_content
            
        except Exception as e:
            logger.error(f"[_get_file_from_zodb_and_save] Erro ao buscar arquivo no ZODB: {e}", exc_info=True)
            return None
    
    def _get_capa_dinamica(self, cod_norma, filename, dir_base):
        """
        Gera capa dinamicamente via HTTP (mesmo método usado durante a coleta).
        """
        try:
            from Products.CMFCore.utils import getToolByName
            import urllib.request
            
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            base_url = portal.absolute_url() if hasattr(portal, 'absolute_url') else ''
            
            if not base_url:
                return None
            
            # Tenta gerar capa via HTTP
            url = f"{base_url}/modelo_proposicao/capa_norma?cod_norma={cod_norma}&action=download"
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'SAGL-PDF-Download/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                capa_data = response.read()
                if capa_data:
                    # Salva no diretório para uso futuro
                    try:
                        file_path = os.path.join(dir_base, filename)
                        os.makedirs(dir_base, mode=0o700, exist_ok=True)
                        with open(file_path, 'wb') as f:
                            f.write(capa_data)
                        logger.info(f"[_get_capa_dinamica] Capa gerada e salva: {filename}")
                    except Exception as save_err:
                        logger.warning(f"[_get_capa_dinamica] Erro ao salvar capa: {save_err}")
                    
                    return capa_data
        except Exception as e:
            logger.debug(f"[_get_capa_dinamica] Erro ao gerar capa dinamicamente: {e}")
            return None
