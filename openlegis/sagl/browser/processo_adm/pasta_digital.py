# -*- coding: utf-8 -*-
"""
Views da Pasta Digital Administrativa.
Interface HTML e endpoints JSON para visualização do processo administrativo integral.

Baseado em pasta_digital.py do legislativo, adaptado para documentos administrativos.
"""
import json
import logging
import os
import re
import time
import threading
import hashlib
import copy
import shutil
from datetime import datetime, date
from zope.interface import Interface
from zope.component import getUtility
from Products.CMFCore.utils import getToolByName
from five import grok

from z3c.saconfig import named_scoped_session
from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload
from openlegis.sagl.models.models import (
    DocumentoAdministrativo, TipoDocumentoAdministrativo,
    DocumentoAcessorioAdministrativo, DocumentoAdministrativoMateria,
    DocumentoAdministrativoVinculado,
    Usuario, UsuarioTipoDocumento, UsuarioConsultaDocumento,
    UsuarioUnidTram, TramitacaoAdministrativo, UnidadeTramitacao,
    AssinaturaDocumento, CientificacaoDocumento, Peticao
)

from openlegis.sagl.browser.processo_adm.processo_adm_utils import (
    get_processo_dir_adm, get_cache_file_path_adm,
    safe_check_file, safe_check_files_batch, get_file_size,
    get_file_info_for_hash, secure_path_join
)
from openlegis.sagl.browser.processo_adm.processo_adm_service import ProcessoAdmService

logger = logging.getLogger(__name__)
Session = named_scoped_session('minha_sessao')

# Cache de tasks recentes (evita criar múltiplas tasks)
_recent_tasks_cache = {}
_cache_lock = threading.Lock()

# Cache TTL para documentos prontos (em segundos)
_ready_documents_cache_ttl = 300  # 5 minutos

# Cache para hash de documentos (TTL curto para garantir atualização rápida)
_hash_cache = {}
_HASH_CACHE_TTL = 30  # 30 segundos
_HASH_CACHE_MAX_SIZE = 50  # Máximo de 50 entradas

# Locks para evitar criação simultânea de tasks (alinhado com processo_leg)
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


def safe_json_for_javascript(json_str):
    """
    Garante que o JSON está seguro para ser inserido diretamente em JavaScript.
    Remove ou escapa caracteres que podem quebrar a sintaxe JavaScript.
    """
    if not json_str:
        return '{}'
    
    # Remove caracteres de controle (exceto tabs e newlines que já foram tratados)
    # Mas garantimos que foram substituídos por espaços
    json_str = json_str.replace('\x00', '')  # Null bytes
    json_str = json_str.replace('\x08', '')  # Backspace
    json_str = json_str.replace('\x0c', '')  # Form feed
    
    # Garante que não há quebras de linha não escapadas
    # (já devem ter sido removidas, mas fazemos novamente por segurança)
    json_str = json_str.replace('\n', ' ').replace('\r', ' ')
    
    # Remove múltiplos espaços consecutivos (pode indicar problemas)
    json_str = re.sub(r' +', ' ', json_str)
    
    # Valida que ainda é JSON válido após limpeza
    try:
        json.loads(json_str)
    except json.JSONDecodeError:
        # Se não for JSON válido após limpeza, retorna JSON vazio mas válido
        return '{}'
    
    return json_str


# ==============================================================================
# FUNÇÕES DE CACHE E ASSINATURAS (MD5)
# ==============================================================================

def _load_cache_from_filesystem_adm(cod_documento_int):
    """
    Carrega cache do filesystem para um documento administrativo.
    
    Returns:
        dict|None: Dicionário completo com todos os dados do cache (documentos, total_paginas, timestamp, hash, sizes)
                  ou None se não conseguir carregar
    """
    try:
        cache_file = get_cache_file_path_adm(cod_documento_int)
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Valida estrutura
                if isinstance(data, dict) and 'documentos' in data and 'timestamp' in data:
                    # CRÍTICO: Retorna o dict completo para preservar total_paginas e outros campos
                    logger.debug(f"[_load_cache_from_filesystem_adm] Cache carregado para documento {cod_documento_int}, total_paginas={data.get('total_paginas', 0)}")
                    return data
                else:
                    logger.warning(f"[_load_cache_from_filesystem_adm] Estrutura de cache inválida para documento {cod_documento_int}")
    except Exception as e:
        logger.debug(f"[_load_cache_from_filesystem_adm] Erro ao carregar cache para {cod_documento_int}: {e}")
    return None


def _save_cache_to_filesystem_adm(cod_documento_int, documentos_data, timestamp, documents_hash, documents_sizes=None):
    """Salva cache no filesystem para um documento administrativo (dentro do diretório da pasta)"""
    try:
        cache_file = get_cache_file_path_adm(cod_documento_int)
        logger.debug(f"[_save_cache_to_filesystem_adm] Caminho do cache: {cache_file}")
        
        # Garante que o diretório existe
        cache_dir = os.path.dirname(cache_file)
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        logger.debug(f"[_save_cache_to_filesystem_adm] Diretório garantido: {cache_dir}")
        
        # Alinhado com processo_leg: aceita tanto dict quanto lista
        # Se for dict, extrai 'documentos' e campos adicionais; se for lista, usa diretamente
        if isinstance(documentos_data, dict):
            documentos_list = documentos_data.get('documentos', [])
            # Extrai campos adicionais se presentes (total_paginas, status, message)
            total_paginas = documentos_data.get('total_paginas', 0)
            status = documentos_data.get('status', 'SUCCESS')
            message = documentos_data.get('message', 'Pasta digital gerada com sucesso')
            logger.debug(f"[_save_cache_to_filesystem_adm] Dict recebido: {len(documentos_list)} documentos, total_paginas={total_paginas}")
        else:
            documentos_list = documentos_data if isinstance(documentos_data, list) else []
            total_paginas = 0
            status = 'SUCCESS'
            message = 'Pasta digital gerada com sucesso'
            logger.debug(f"[_save_cache_to_filesystem_adm] Lista recebida: {len(documentos_list)} documentos")
        
        data = {
            'documentos': documentos_list,
            'timestamp': timestamp,
            'hash': documents_hash,
            'cod_documento': str(cod_documento_int),
            'total_paginas': total_paginas,  # Inclui total_paginas
            'status': status,  # Inclui status
            'message': message  # Inclui mensagem
        }
        # Adiciona tamanhos dos arquivos se fornecidos
        if documents_sizes is not None:
            data['sizes'] = documents_sizes
        
        logger.debug(f"[_save_cache_to_filesystem_adm] Dados preparados: {len(data.get('documentos', []))} documentos, timestamp={timestamp}, hash={documents_hash[:16] if documents_hash else 'None'}...")
        
        # Escreve atomicamente (cria arquivo temporário primeiro) - alinhado com processo_leg
        temp_file = cache_file + '.tmp'
        logger.debug(f"[_save_cache_to_filesystem_adm] Escrevendo arquivo temporário: {temp_file}")
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, cls=DateTimeJSONEncoder)
            f.flush()
            os.fsync(f.fileno())  # Força escrita no disco
        
        # Verifica se o arquivo temporário foi criado
        if not os.path.exists(temp_file):
            raise Exception(f"Arquivo temporário não foi criado: {temp_file}")
        
        temp_size = os.path.getsize(temp_file)
        logger.debug(f"[_save_cache_to_filesystem_adm] Arquivo temporário criado: {temp_file} (tamanho: {temp_size} bytes)")
        
        # Move arquivo temporário para o arquivo final (operação atômica)
        os.replace(temp_file, cache_file)
        
        # Verifica se o arquivo final foi criado
        if not os.path.exists(cache_file):
            raise Exception(f"Arquivo final não foi criado após replace: {cache_file}")
        
        final_size = os.path.getsize(cache_file)
        
    except Exception as e:
        logger.error(f"[_save_cache_to_filesystem_adm] ❌ Erro ao salvar cache no filesystem para {cod_documento_int}: {e}", exc_info=True)
        # Não re-raise para não quebrar a task - cache é opcional


def _delete_cache_from_filesystem_adm(cod_documento_int):
    """Deleta cache do filesystem para um documento administrativo"""
    try:
        cache_file = get_cache_file_path_adm(cod_documento_int)
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logger.debug(f"[_delete_cache_from_filesystem_adm] Cache deletado para documento {cod_documento_int}")
    except Exception as e:
        logger.warning(f"[_delete_cache_from_filesystem_adm] Erro ao deletar cache para {cod_documento_int}: {e}")


def _calculate_documents_sizes_adm(cod_documento, portal):
    """
    Calcula os tamanhos dos arquivos coletados para um documento administrativo.
    Retorna um dicionário com {nome_arquivo: tamanho} ou {} em caso de erro.
    """
    try:
        sizes = {}
        
        if not hasattr(portal, 'sapl_documentos'):
            return sizes
        
        # 1. Texto integral
        arquivo_texto = f"{cod_documento}_texto_integral.pdf"
        if hasattr(portal.sapl_documentos, 'administrativo'):
            size = get_file_size(portal.sapl_documentos.administrativo, arquivo_texto)
            if size:
                sizes[arquivo_texto] = size
        
        # 2. Documentos acessórios
        try:
            session = Session()
            try:
                docs_acessorios = session.query(DocumentoAcessorioAdministrativo)\
                    .filter(DocumentoAcessorioAdministrativo.cod_documento == cod_documento)\
                    .filter(DocumentoAcessorioAdministrativo.ind_excluido == 0)\
                    .all()
                for doc_obj in docs_acessorios:
                    filename = f"{doc_obj.cod_documento_acessorio}.pdf"
                    if hasattr(portal.sapl_documentos, 'administrativo'):
                        size = get_file_size(portal.sapl_documentos.administrativo, filename)
                        if size is not None:
                            sizes[filename] = size
            finally:
                session.close()
        except Exception as e:
            logger.debug(f"[_calculate_documents_sizes_adm] Erro ao obter tamanhos de documentos acessórios: {e}")
        
        # 3. Tramitações
        try:
            session = Session()
            try:
                tramitacoes = session.query(TramitacaoAdministrativo)\
                    .filter(TramitacaoAdministrativo.cod_documento == cod_documento)\
                    .filter(TramitacaoAdministrativo.ind_excluido == 0)\
                    .all()
                for tram_obj in tramitacoes:
                    filename = f"{tram_obj.cod_tramitacao}_tram.pdf"
                    if hasattr(portal.sapl_documentos, 'administrativo') and hasattr(portal.sapl_documentos.administrativo, 'tramitacao'):
                        size = get_file_size(portal.sapl_documentos.administrativo.tramitacao, filename)
                        if size is not None:
                            sizes[filename] = size
            finally:
                session.close()
        except Exception as e:
            logger.debug(f"[_calculate_documents_sizes_adm] Erro ao obter tamanhos de tramitações: {e}")
        
        return sizes
    except Exception as e:
        logger.warning(f"[_calculate_documents_sizes_adm] Erro ao calcular tamanhos: {e}")
        return {}


def _collect_current_documents_metadata_adm(cod_documento_int, portal):
    """
    Coleta metadados dos documentos atuais do sistema para comparação com cache.
    Retorna lista de dicionários com informações dos documentos.
    """
    documentos_atual = []
    session = None
    
    try:
        session = Session()
        
        # 1. Capa do processo - sempre incluída, pois é sempre gerada durante a coleta
        # A capa é gerada dinamicamente via HTTP e não existe no ZODB
        # CRÍTICO: Sempre regeneramos a capa via HTTP para obter o tamanho atual
        # Isso garante que qualquer mudança no assunto ou outros campos seja detectada
        # através da comparação de tamanhos (sem tolerância para a capa)
        try:
            # Obtém dados do documento para construir nome da capa
            resultado = session.query(DocumentoAdministrativo, TipoDocumentoAdministrativo)\
                .join(TipoDocumentoAdministrativo, 
                      DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
                .filter(DocumentoAdministrativo.cod_documento == cod_documento_int)\
                .filter(DocumentoAdministrativo.ind_excluido == 0)\
                .first()
            
            if resultado:
                doc_obj, tipo_obj = resultado
                tipo = tipo_obj.sgl_tipo_documento if hasattr(tipo_obj, 'sgl_tipo_documento') and tipo_obj.sgl_tipo_documento else 'DOC'
                numero = doc_obj.num_documento if hasattr(doc_obj, 'num_documento') and doc_obj.num_documento else '0'
                ano = doc_obj.ano_documento if hasattr(doc_obj, 'ano_documento') and doc_obj.ano_documento else '2025'
            else:
                # Fallback para valores padrão se documento não encontrado
                tipo = 'DOC'
                numero = '0'
                ano = '2025'
            
            arquivo_capa = f"capa_{tipo}-{numero}-{ano}.pdf"
            
            # Obtém tamanho atual da capa via HTTP (para detectar mudanças)
            capa_size = 0
            try:
                base_url = portal.absolute_url() if hasattr(portal, 'absolute_url') else ''
                if base_url:
                    # Usa modelo_proposicao.capa_processo_adm com action=download
                    # Precisa gerar nom_arquivo temporário para a chamada
                    import uuid
                    nom_arquivo_temp = uuid.uuid4().hex
                    url = f"{base_url}/modelo_proposicao/capa_processo_adm?cod_documento={cod_documento_int}&nom_arquivo={nom_arquivo_temp}&action=download"
                    import urllib.request
                    req = urllib.request.Request(url)
                    req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                    
                    with urllib.request.urlopen(req, timeout=10) as response:
                        capa_data = response.read()
                        if capa_data:
                            capa_size = len(capa_data)
            except Exception as e:
                # Se falhar ao obter via HTTP, tenta usar arquivo no diretório
                logger.debug(f"[_collect_current_documents_metadata_adm] Erro ao obter capa via HTTP: {e}, usando arquivo do diretório")
                from openlegis.sagl.browser.processo_adm.processo_adm_utils import get_processo_dir_adm
                dir_base = get_processo_dir_adm(cod_documento_int)
                capa_path = os.path.join(dir_base, arquivo_capa)
                if os.path.exists(capa_path):
                    capa_size = os.path.getsize(capa_path)
            
            # Sempre inclui a capa na lista (sempre é gerada na coleta)
            documentos_atual.append({
                'file': arquivo_capa,
                'file_size': capa_size,  # Tamanho atual obtido via HTTP ou do diretório
                'title': 'Capa do Processo'
            })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata_adm] Erro ao obter dados da capa: {e}")
            # Continua mesmo sem dados da capa
        
        # 2. Texto integral
        try:
            arquivo_texto = f"{cod_documento_int}_texto_integral.pdf"
            if hasattr(portal.sapl_documentos, 'administrativo'):
                if safe_check_file(portal.sapl_documentos.administrativo, arquivo_texto):
                    size = get_file_size(portal.sapl_documentos.administrativo, arquivo_texto) or 0
                    documentos_atual.append({
                        'file': arquivo_texto,
                        'file_size': size,
                        'title': 'Texto Integral'
                    })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata_adm] Erro ao processar texto integral: {e}")
        
        # 3. Documentos Acessórios
        try:
            docs_acessorios = session.query(DocumentoAcessorioAdministrativo)\
                .filter(and_(
                    DocumentoAcessorioAdministrativo.cod_documento == cod_documento_int,
                    DocumentoAcessorioAdministrativo.ind_excluido == 0
                ))\
                .all()
            
            for doc_obj in docs_acessorios:
                arquivo_acessorio = f"{doc_obj.cod_documento_acessorio}.pdf"
                if hasattr(portal.sapl_documentos, 'administrativo'):
                    if safe_check_file(portal.sapl_documentos.administrativo, arquivo_acessorio):
                        size = get_file_size(portal.sapl_documentos.administrativo, arquivo_acessorio) or 0
                        documentos_atual.append({
                            'file': arquivo_acessorio,
                            'file_size': size,
                            'title': doc_obj.nom_documento or 'Documento Acessório'
                        })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata_adm] Erro ao processar documentos acessórios: {e}")
        
        # 4. Tramitações
        try:
            tramitacoes = session.query(TramitacaoAdministrativo)\
                .filter(and_(
                    TramitacaoAdministrativo.cod_documento == cod_documento_int,
                    TramitacaoAdministrativo.ind_excluido == 0
                ))\
                .order_by(TramitacaoAdministrativo.dat_tramitacao, TramitacaoAdministrativo.cod_tramitacao)\
                .all()
            
            for tram_obj in tramitacoes:
                arquivo_tram = f"{tram_obj.cod_tramitacao}_tram.pdf"
                if hasattr(portal.sapl_documentos, 'administrativo') and hasattr(portal.sapl_documentos.administrativo, 'tramitacao'):
                    if safe_check_file(portal.sapl_documentos.administrativo.tramitacao, arquivo_tram):
                        size = get_file_size(portal.sapl_documentos.administrativo.tramitacao, arquivo_tram) or 0
                        documentos_atual.append({
                            'file': arquivo_tram,
                            'file_size': size,
                            'title': f"Tramitação"
                        })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata_adm] Erro ao processar tramitações: {e}")
        
        # 5. Matérias Vinculadas
        try:
            materias_vinculadas = session.query(DocumentoAdministrativoMateria)\
                .filter(and_(
                    DocumentoAdministrativoMateria.cod_documento == cod_documento_int,
                    DocumentoAdministrativoMateria.ind_excluido == 0
                ))\
                .all()
            
            for mat_vinculada_obj in materias_vinculadas:
                # Matéria vinculada não tem PDF próprio, apenas referência
                # Pode ser usado para tracking se necessário
                pass
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata_adm] Erro ao processar matérias vinculadas: {e}")
        
        # 6. Folha de Cientificações (gerada dinamicamente, sempre existe se houver cientificações)
        try:
            cientificacoes = session.query(CientificacaoDocumento)\
                .filter(and_(
                    CientificacaoDocumento.cod_documento == cod_documento_int,
                    CientificacaoDocumento.ind_excluido == 0
                ))\
                .count()
            
            if cientificacoes > 0:
                # A folha é gerada dinamicamente, então não tem arquivo no ZODB
                # Obtém tamanho atual da folha via arquivo no diretório (para detectar mudanças)
                folha_size = 0
                try:
                    # Tenta obter tamanho do arquivo gerado no diretório
                    from openlegis.sagl.browser.processo_adm.processo_adm_utils import get_processo_dir_adm
                    dir_base = get_processo_dir_adm(cod_documento_int)
                    if dir_base:
                        folha_path = os.path.join(dir_base, 'folha_cientificacoes.pdf')
                        if os.path.exists(folha_path):
                            folha_size = os.path.getsize(folha_path)
                except Exception as e:
                    logger.debug(f"[_collect_current_documents_metadata_adm] Erro ao obter tamanho da folha de cientificações: {e}")
                
                # Sempre inclui a folha na lista (sempre é gerada se houver cientificações)
                documentos_atual.append({
                    'file': 'folha_cientificacoes.pdf',
                    'file_size': folha_size,  # Tamanho atual obtido do diretório
                    'title': 'Folha de Cientificações',
                    'count': cientificacoes  # Metadado adicional
                })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata_adm] Erro ao processar cientificações: {e}")
        
    except Exception as e:
        logger.warning(f"[_collect_current_documents_metadata_adm] Erro ao coletar metadados: {e}")
    finally:
        if session:
            session.close()
    
    return documentos_atual


def _compare_documents_with_metadados_adm(cod_documento_int, portal):
    """
    Compara os documentos ATUAIS do sistema com dados armazenados em documentos_metadados.json ou cache.json.
    
    Returns:
        tuple: (has_changes, details_dict) onde:
            - has_changes: True se há mudanças que exigem regeneração
            - details_dict: dicionário com detalhes das mudanças (novos, removidos, modificados)
    """
    try:
        dir_base = get_processo_dir_adm(cod_documento_int)
        
        # Se diretório não existe, há mudanças (precisa regenerar)
        if not os.path.exists(dir_base):
            return (True, {'error': 'Diretório não existe'})
        
        metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
        cache_path = get_cache_file_path_adm(cod_documento_int)
        
        # Prioridade 1: Tenta usar documentos_metadados.json (formato usado pela task de geração)
        # Prioridade 2: Se não existe, usa cache.json (formato usado pelo cache do filesystem)
        metadados_file = None
        if os.path.exists(metadados_path):
            metadados_file = metadados_path
        elif os.path.exists(cache_path):
            metadados_file = cache_path
        
        # Se não existe nenhum dos dois, precisa gerar pasta digital
        if not metadados_file:
            return (True, {'error': 'JSON não existe'})
        
        # Carrega metadados da última geração
        with open(metadados_file, 'r', encoding='utf-8') as f:
            metadados = json.load(f)
        
        # CRÍTICO: Verifica se o cod_documento nos metadados corresponde ao atual
        # Se não corresponder, os metadados são de outro documento - invalida cache
        metadados_cod_doc = metadados.get('cod_documento')
        if metadados_cod_doc is not None:
            try:
                metadados_cod_int = int(metadados_cod_doc)
                if metadados_cod_int != cod_documento_int:
                    logger.warning(f"[_compare_documents_with_metadados_adm] Metadados são de outro documento (cod_documento nos metadados: {metadados_cod_int}, atual: {cod_documento_int}). Invalidando cache.")
                    return (True, {'error': f'Metadados de outro documento (cod_documento={metadados_cod_int} vs {cod_documento_int})'})
            except (ValueError, TypeError):
                # Se não conseguir converter, continua (pode ser string ou formato antigo)
                pass
        
        documentos_metadados = metadados.get('documentos', [])
        
        if not documentos_metadados:
            return (False, {})
        
        # Coleta documentos ATUAIS do sistema
        documentos_atual = _collect_current_documents_metadata_adm(cod_documento_int, portal)
        
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
        
        # Verifica arquivos removidos
        # CRÍTICO: Ignora arquivos removidos que são apenas nomes incorretos (ex: texto integral de outro cod_documento)
        for file_name, doc_meta in metadados_map.items():
            if file_name not in atual_map:
                # Verifica se é um arquivo de texto integral com cod_documento diferente
                # Se sim, pode ser apenas um nome incorreto nos metadados antigos - não é mudança crítica
                is_texto_integral_wrong_cod = False
                if file_name.endswith('_texto_integral.pdf'):
                    # Extrai cod_documento do nome do arquivo nos metadados
                    try:
                        cod_from_file = int(file_name.replace('_texto_integral.pdf', ''))
                        # Verifica se existe o arquivo correto no atual
                        arquivo_texto_correto = f"{cod_documento_int}_texto_integral.pdf"
                        if arquivo_texto_correto in atual_map:
                            # O arquivo correto existe - isso é apenas correção de nome, não mudança
                            is_texto_integral_wrong_cod = True
                    except (ValueError, TypeError):
                        pass
                
                if not is_texto_integral_wrong_cod:
                    has_changes = True
                    details['removed'].append(file_name)
                # else: Não marca como mudança - é apenas correção de nome (arquivo correto existe)
        
        # Verifica arquivos novos e modificados
        for file_name, doc_atual in atual_map.items():
            if file_name not in metadados_map:
                has_changes = True
                details['added'].append(file_name)
            else:
                # Arquivo existe em ambos - verifica se tamanho mudou
                doc_meta = metadados_map[file_name]
                size_meta = doc_meta.get('file_size', 0)
                size_atual = doc_atual.get('file_size', 0)
                
                # Para folha de cientificações, também compara count
                # Mas só marca como mudança se o count realmente mudou
                is_folha_cientificacoes = file_name == 'folha_cientificacoes.pdf'
                count_changed = False
                if is_folha_cientificacoes:
                    count_meta = doc_meta.get('count', 0)
                    count_atual = doc_atual.get('count', 0)
                    if count_meta != count_atual:
                        count_changed = True
                        has_changes = True
                        details['modified'].append({
                            'file': file_name,
                            'type': 'count_change',
                            'old_count': count_meta,
                            'new_count': count_atual
                        })
                
                # Para capa e folha de cientificações, usa pequena tolerância para variações do gerador de PDF
                # A capa e folha são sempre regeneradas via HTTP quando coletamos metadados
                # Tolerância pequena (0.1% ou 100 bytes, o que for maior) evita falsos positivos
                # causados por variações mínimas do gerador, mas detecta mudanças reais no conteúdo
                is_capa = file_name.startswith('capa_') and file_name.endswith('.pdf')
                # Aplica tolerância tanto para capa quanto para folha de cientificações
                has_tolerance = is_capa or is_folha_cientificacoes
                
                size_to_compare = size_atual
                
                # Verifica mudança de tamanho apenas se ambos os tamanhos são válidos (> 0)
                # Para folha de cientificações, se o count mudou, já foi marcado como mudança acima
                # Apenas verifica tamanho se o count não mudou (para evitar duplicar mudanças)
                if size_meta > 0 and size_to_compare > 0:
                    if size_meta != size_to_compare:
                        if has_tolerance:
                            # Para capa e folha de cientificações, aplica pequena tolerância para variações do gerador
                            # Tolerância: 0.1% ou 100 bytes (o que for maior)
                            diff_percent = abs(size_meta - size_to_compare) / size_meta if size_meta > 0 else 0
                            diff_bytes = abs(size_meta - size_to_compare)
                            # Tolerância mínima: 100 bytes ou 0.1% do tamanho original
                            tolerance_bytes = max(100, int(size_meta * 0.001))  # 0.1% ou 100 bytes
                            
                            if diff_bytes > tolerance_bytes:
                                # Diferença maior que a tolerância - mudança real detectada
                                # Mas para folha de cientificações, só marca como mudança de tamanho se o count não mudou
                                # (se o count mudou, já foi marcado acima como count_change e não precisa marcar novamente)
                                if not (is_folha_cientificacoes and count_changed):
                                    has_changes = True
                                    file_type = 'Capa' if is_capa else 'Folha de cientificações'
                                    details['modified'].append({
                                        'file': file_name,
                                        'type': 'size_change',
                                        'old_size': size_meta,
                                        'new_size': size_to_compare,
                                        'diff_percent': f"{diff_percent * 100:.2f}%",
                                        'diff_bytes': diff_bytes,
                                        'tolerance_bytes': tolerance_bytes
                                    })
                                    # Mudança real detectada (diferença maior que tolerância)
                            else:
                                # Diferença dentro da tolerância - variação do gerador, ignorar
                                pass
                        else:
                            # Para outros arquivos, compara exatamente (sem tolerância)
                            has_changes = True
                            details['modified'].append({
                                'file': file_name,
                                'type': 'size_change',
                                'old_size': size_meta,
                                'new_size': size_to_compare
                            })
                elif size_meta == 0 and size_to_compare > 0:
                    # Arquivo foi criado (tamanho mudou de 0 para > 0)
                    # Para folha de cientificações, isso já foi capturado pelo count_change se o count mudou
                    # Se não for folha ou se for folha mas o count não mudou (caso raro), marca como mudança
                    if not (is_folha_cientificacoes and count_changed):
                        has_changes = True
                        details['modified'].append({
                            'file': file_name,
                            'type': 'size_change',
                            'old_size': size_meta,
                            'new_size': size_to_compare
                        })
                elif size_meta > 0 and size_to_compare == 0:
                    # Arquivo foi removido (tamanho mudou de > 0 para 0) - isso é uma mudança real
                    # Para folha de cientificações, isso deve ser capturado pelo count mudando para 0
                    # Se não foi capturado pelo count (caso raro), marca como mudança de tamanho
                    if not (is_folha_cientificacoes and count_changed):
                        has_changes = True
                        details['modified'].append({
                            'file': file_name,
                            'type': 'size_change',
                            'old_size': size_meta,
                            'new_size': size_to_compare
                        })
        
        # Mudanças detectadas (ou não) - retorna resultado
        
        return (has_changes, details)
        
    except Exception as e:
        logger.warning(f"[_compare_documents_with_metadados_adm] Erro ao comparar documentos: {e}")
        # Em caso de erro, assume que há mudanças (mais seguro)
        return (True, {'error': str(e)})


def _calculate_documents_hash_adm(cod_documento, portal):
    """
    Calcula um hash dos documentos disponíveis para um documento administrativo.
    Isso permite detectar quando documentos são adicionados, modificados ou excluídos.
    Retorna None em caso de erro.
    
    OTIMIZAÇÃO: Usa cache pequeno com TTL curto (30s) para evitar recálculos repetidos.
    """
    global _hash_cache
    
    # Verifica cache primeiro
    current_time = time.time()
    cache_key = cod_documento
    
    if cache_key in _hash_cache:
        cached_hash, cache_timestamp = _hash_cache[cache_key]
        age = current_time - cache_timestamp
        
        if age < _HASH_CACHE_TTL:
            logger.debug(f"[_calculate_documents_hash_adm] Hash retornado do cache para cod_documento={cod_documento} (idade: {age:.1f}s)")
            return cached_hash
        else:
            del _hash_cache[cache_key]
    
    # Limpa cache antigo se muito grande
    if len(_hash_cache) >= _HASH_CACHE_MAX_SIZE:
        sorted_items = sorted(_hash_cache.items(), key=lambda x: x[1][1])
        items_to_remove = len(_hash_cache) - _HASH_CACHE_MAX_SIZE + 1
        for key, _ in sorted_items[:items_to_remove]:
            del _hash_cache[key]
        logger.debug(f"[_calculate_documents_hash_adm] Cache limpo: removidas {items_to_remove} entradas antigas")
    
    try:
        hash_data = []
        session = None
        
        if not hasattr(portal, 'sapl_documentos'):
            return None
        
        # 1. Verifica texto integral
        arquivo_texto = f"{cod_documento}_texto_integral.pdf"
        if hasattr(portal.sapl_documentos, 'administrativo'):
            if safe_check_file(portal.sapl_documentos.administrativo, arquivo_texto):
                file_info = get_file_info_for_hash(portal.sapl_documentos.administrativo, arquivo_texto)
                if file_info:
                    hash_data.append(f"texto_integral:{'|'.join(file_info)}")
                else:
                    hash_data.append(f"texto_integral:exists")
            else:
                hash_data.append(f"texto_integral:not_exists")
        else:
            hash_data.append(f"texto_integral:not_exists")
        
        # 2-6. Consultas SQLAlchemy consolidadas em uma única sessão
        try:
            session = Session()
            
            # 2. Documentos Acessórios
            try:
                docs_acessorios_query = session.query(DocumentoAcessorioAdministrativo)\
                    .filter(and_(
                        DocumentoAcessorioAdministrativo.cod_documento == cod_documento,
                        DocumentoAcessorioAdministrativo.ind_excluido == 0
                    ))
                
                docs_acessorios = docs_acessorios_query.all()
                hash_data.append(f"acessorios_count:{len(docs_acessorios)}")
                
                if docs_acessorios and hasattr(portal.sapl_documentos, 'administrativo'):
                    arquivos_acessorios = [f"{doc_obj.cod_documento_acessorio}.pdf" for doc_obj in docs_acessorios]
                    resultados_acessorios = safe_check_files_batch(portal.sapl_documentos.administrativo, arquivos_acessorios)
                    
                    for doc_obj in docs_acessorios:
                        arquivo_acessorio = f"{doc_obj.cod_documento_acessorio}.pdf"
                        if resultados_acessorios.get(arquivo_acessorio, False):
                            file_info = get_file_info_for_hash(portal.sapl_documentos.administrativo, arquivo_acessorio)
                            if file_info:
                                hash_data.append(f"acessorio_{doc_obj.cod_documento_acessorio}:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"acessorio_{doc_obj.cod_documento_acessorio}:exists")
                        else:
                            hash_data.append(f"acessorio_{doc_obj.cod_documento_acessorio}:not_exists")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash_adm] Erro ao processar documentos acessórios: {e}")
            
            # 3. Tramitações
            try:
                tramitacoes_query = session.query(TramitacaoAdministrativo)\
                    .filter(and_(
                        TramitacaoAdministrativo.cod_documento == cod_documento,
                        TramitacaoAdministrativo.ind_excluido == 0
                    ))
                
                tramitacoes = tramitacoes_query.all()
                hash_data.append(f"tramitacoes_count:{len(tramitacoes)}")
                
                if tramitacoes and hasattr(portal.sapl_documentos, 'administrativo') and hasattr(portal.sapl_documentos.administrativo, 'tramitacao'):
                    arquivos_tramitacoes = [f"{tram_obj.cod_tramitacao}_tram.pdf" for tram_obj in tramitacoes]
                    resultados_tramitacoes = safe_check_files_batch(portal.sapl_documentos.administrativo.tramitacao, arquivos_tramitacoes)
                    
                    for tram_obj in tramitacoes:
                        arquivo_tram = f"{tram_obj.cod_tramitacao}_tram.pdf"
                        if resultados_tramitacoes.get(arquivo_tram, False):
                            file_info = get_file_info_for_hash(portal.sapl_documentos.administrativo.tramitacao, arquivo_tram)
                            if file_info:
                                hash_data.append(f"tram_{tram_obj.cod_tramitacao}:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"tram_{tram_obj.cod_tramitacao}:exists")
                        else:
                            hash_data.append(f"tram_{tram_obj.cod_tramitacao}:not_exists")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash_adm] Erro ao processar tramitações: {e}")
            
            # 4. Cientificações (conta apenas, não tem arquivo)
            try:
                cientificacoes_count = session.query(CientificacaoDocumento)\
                    .filter(and_(
                        CientificacaoDocumento.cod_documento == cod_documento,
                        CientificacaoDocumento.ind_excluido == 0
                    ))\
                    .count()
                
                hash_data.append(f"cientificacoes_count:{cientificacoes_count}")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash_adm] Erro ao processar cientificações: {e}")
            
        finally:
            if session:
                session.close()
        
        # Calcula hash MD5
        hash_string = '|'.join(sorted(hash_data))
        documents_hash = hashlib.md5(hash_string.encode('utf-8')).hexdigest()
        
        # Armazena no cache
        _hash_cache[cache_key] = (documents_hash, current_time)
        
        logger.debug(f"[_calculate_documents_hash_adm] Hash calculado para cod_documento={cod_documento}: {documents_hash[:16]}...")
        
        return documents_hash
        
    except Exception as e:
        logger.warning(f"[_calculate_documents_hash_adm] Erro ao calcular hash para cod_documento={cod_documento}: {e}")
        return None


def verificar_permissao_acesso(context, cod_documento, user, session=None):
    """
    Verifica se o usuário tem permissão para acessar o documento administrativo.
    
    Baseado em verifica_permissao.py, mas usando SQLAlchemy.
    
    Args:
        context: Contexto Zope
        cod_documento: Código do documento administrativo
        user: Usuário autenticado (Zope user)
        session: Sessão SQLAlchemy (opcional, cria nova se não fornecida)
        
    Returns:
        tuple: (can_view: bool, motivo: list) onde motivo contém os motivos de acesso
    """
    can_view = False
    motivo = []
    close_session = False
    
    try:
        # Cria sessão se não fornecida
        if session is None:
            session = Session()
            close_session = True
        
        # 1. Verifica roles administrativos (acesso total)
        if user.has_role(['Manager', 'Operador', 'Operador Modulo Administrativo', 'Consulta Modulo Administrativo']):
            can_view = True
            motivo.append('role_admin')
            return (can_view, motivo)
        
        # 2. Verifica se documento é público
        # Carrega documento com o tipo de documento (que contém ind_publico)
        documento = session.query(DocumentoAdministrativo).options(
            selectinload(DocumentoAdministrativo.tipo_documento_administrativo)
        ).filter(
            DocumentoAdministrativo.cod_documento == cod_documento,
            DocumentoAdministrativo.ind_excluido == 0
        ).first()
        
        if not documento:
            return (False, motivo)
        
        # Verifica ind_publico do tipo de documento (não do documento em si)
        if documento.tipo_documento_administrativo and documento.tipo_documento_administrativo.ind_publico == 1:
            can_view = True
            motivo.append('documento_publico')
            return (can_view, motivo)
        
        # 3. Verifica usuário autenticado
        if not user.has_role(['Authenticated']):
            return (False, motivo)
        
        # Obtém usuário do banco
        username = user.getUserName()
        usuario_obj = session.query(Usuario).filter(
            Usuario.col_username == username
        ).first()
        
        if not usuario_obj:
            return (False, motivo)
        
        cod_usuario = usuario_obj.cod_usuario
        
        # 4. Verifica permissões específicas
        
        # a) Autor de petição
        peticao = session.query(Peticao).filter(
            Peticao.cod_usuario == cod_usuario,
            Peticao.cod_documento == cod_documento,
            Peticao.ind_excluido == 0
        ).first()
        
        if peticao:
            can_view = True
            motivo.append('autor_peticao')
        
        # b) Permissão no tipo de documento
        if documento.tip_documento:
            # Permissão direta
            usuario_tipo = session.query(UsuarioTipoDocumento).filter(
                UsuarioTipoDocumento.tip_documento == documento.tip_documento,
                UsuarioTipoDocumento.cod_usuario == cod_usuario,
                UsuarioTipoDocumento.ind_excluido == 0
            ).first()
            
            if usuario_tipo:
                can_view = True
                motivo.append('permissao_tipo')
            else:
                # Permissão de consulta
                usuario_consulta = session.query(UsuarioConsultaDocumento).filter(
                    UsuarioConsultaDocumento.tip_documento == documento.tip_documento,
                    UsuarioConsultaDocumento.cod_usuario == cod_usuario,
                    UsuarioConsultaDocumento.ind_excluido == 0
                ).first()
                
                if usuario_consulta:
                    can_view = True
                    motivo.append('consulta_tipo')
        
        # c) Pedido de assinatura no documento
        assinatura_doc = session.query(AssinaturaDocumento).filter(
            AssinaturaDocumento.codigo == cod_documento,
            AssinaturaDocumento.tipo_doc == 'documento',
            AssinaturaDocumento.cod_usuario == cod_usuario,
            AssinaturaDocumento.ind_excluido == 0
        ).first()
        
        if assinatura_doc:
            can_view = True
            motivo.append('assinatura_documento')
        
        # d) Solicitação de assinatura no texto integral (cientificação)
        cientificacao = session.query(CientificacaoDocumento).filter(
            CientificacaoDocumento.cod_documento == cod_documento,
            CientificacaoDocumento.cod_cientificado == cod_usuario,
            CientificacaoDocumento.ind_excluido == 0
        ).first()
        
        if cientificacao:
            can_view = True
            motivo.append('cientificacao_documento')
        
        # e) Solicitação de assinatura em documentos acessórios
        documentos_acessorios = session.query(DocumentoAcessorioAdministrativo).filter(
            DocumentoAcessorioAdministrativo.cod_documento == cod_documento,
            DocumentoAcessorioAdministrativo.ind_excluido == 0
        ).all()
        
        for doc_acessorio in documentos_acessorios:
            assinatura_acessorio = session.query(AssinaturaDocumento).filter(
                AssinaturaDocumento.codigo == doc_acessorio.cod_documento_acessorio,
                AssinaturaDocumento.tipo_doc == 'doc_acessorio_adm',
                AssinaturaDocumento.cod_usuario == cod_usuario,
                AssinaturaDocumento.ind_excluido == 0
            ).first()
            
            if assinatura_acessorio:
                can_view = True
                motivo.append('assinatura_acessorio')
                break
        
        # f) Usuário de origem ou destino em tramitações
        tramitacoes = session.query(TramitacaoAdministrativo).filter(
            TramitacaoAdministrativo.cod_documento == cod_documento,
            TramitacaoAdministrativo.ind_excluido == 0
        ).all()
        
        for tram in tramitacoes:
            if tram.cod_usuario_local == cod_usuario or tram.cod_usuario_dest == cod_usuario:
                can_view = True
                motivo.append('tramitacao_usuario')
                break
            
            # Usuário vinculado a unidade de origem ou destino
            usuario_unid = session.query(UsuarioUnidTram).filter(
                UsuarioUnidTram.cod_unid_tramitacao.in_([tram.cod_unid_tram_local, tram.cod_unid_tram_dest]),
                UsuarioUnidTram.cod_usuario == cod_usuario
            ).first()
            
            if usuario_unid:
                can_view = True
                motivo.append('tramitacao_unidade')
                break
            
            # Solicitação de assinatura em tramitações
            assinatura_tram = session.query(AssinaturaDocumento).filter(
                AssinaturaDocumento.codigo == tram.cod_tramitacao,
                AssinaturaDocumento.tipo_doc == 'tramitacao_adm',
                AssinaturaDocumento.cod_usuario == cod_usuario,
                AssinaturaDocumento.ind_excluido == 0
            ).first()
            
            if assinatura_tram:
                can_view = True
                motivo.append('assinatura_tramitacao')
                break
        
        return (can_view, motivo)
        
    except Exception as e:
        logger.error(f"[verificar_permissao_acesso] Erro ao verificar permissão: {e}", exc_info=True)
        return (False, motivo)
    finally:
        if close_session and session:
            session.close()


def registrar_acesso_documento(cod_documento, user, autorizado, motivo=None):
    """
    Registra acesso ao documento no log (se necessário).
    
    Args:
        cod_documento: Código do documento
        user: Usuário
        autorizado: Se o acesso foi autorizado
        motivo: Lista de motivos (opcional)
    """
    try:
        username = user.getUserName() if user else 'anonymous'
        motivo_str = ', '.join(motivo) if motivo else 'nenhum'
        logger.info(f"[acesso_documento] cod_documento={cod_documento}, user={username}, autorizado={autorizado}, motivo={motivo_str}")
        # TODO: Implementar registro em tabela de logs se necessário
    except Exception as e:
        logger.debug(f"[registrar_acesso_documento] Erro ao registrar acesso: {e}")


class PastaDigitalAdmView(grok.View):
    """View principal da pasta digital administrativa - renderiza HTML"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pasta_digital_adm')
    
    def update(self):
        """Método update do Grok - garante que headers sejam definidos"""
        # Define headers ANTES de qualquer processamento
        self.request.RESPONSE.setHeader('Content-Type', 'text/html; charset=utf-8')
        # Evita cache para garantir que sempre use a versão mais recente
        self.request.RESPONSE.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.request.RESPONSE.setHeader('Pragma', 'no-cache')
        self.request.RESPONSE.setHeader('Expires', '0')
        
        # Garante que AUTHENTICATED_USER está definido no REQUEST (necessário para DTML templates)
        if 'AUTHENTICATED_USER' not in self.request:
            try:
                from AccessControl import getSecurityManager
                security_manager = getSecurityManager()
                user = security_manager.getUser()
                if user:
                    self.request['AUTHENTICATED_USER'] = user
            except (ImportError, AttributeError):
                # Se não conseguir obter o usuário, cria um usuário anônimo para evitar erros
                from AccessControl.users import nobody
                self.request['AUTHENTICATED_USER'] = nobody
    
    def __call__(self):
        """Intercepta a chamada para escrever HTML diretamente na resposta"""
        # Chama update primeiro para definir headers
        self.update()
        
        # Chama render para obter o HTML
        html = self.render()
        
        # Garante que o HTML seja uma string
        if not isinstance(html, str):
            html = str(html)
        
        # IMPORTANTE: Define Content-Type antes de escrever
        self.request.RESPONSE.setHeader('Content-Type', 'text/html; charset=utf-8')
        
        # Usa setBody() em vez de write() para garantir que o HTML seja renderizado
        if isinstance(html, str):
            html_bytes = html.encode('utf-8')
        else:
            html_bytes = html
        
        self.request.RESPONSE.setBody(html_bytes)
        
        # Retorna string vazia para evitar processamento adicional do Grok
        return ''
    
    def render(self):
        """Renderiza HTML da pasta digital com dados já incluídos"""
        try:
            cod_documento = self.request.form.get('cod_documento') or self.request.get('cod_documento')
            action = self.request.form.get('action', 'pasta')
            
            if not cod_documento:
                return self._render_error('Parâmetro cod_documento é obrigatório')
            
            try:
                cod_documento = int(cod_documento)
            except (ValueError, TypeError):
                return self._render_error('cod_documento inválido')
            
            # Verifica permissão
            # Tenta múltiplas formas de obter o usuário autenticado (compatibilidade Zope)
            user = None
            try:
                user = self.request.get('AUTHENTICATED_USER')
            except (AttributeError, KeyError):
                pass
            
            if not user:
                try:
                    user = self.request.get('AUTHENTICATED_USER', None)
                except (AttributeError, KeyError):
                    pass
            
            if not user:
                try:
                    from AccessControl import getSecurityManager
                    from zope.security import checkPermission
                    security_manager = getSecurityManager()
                    user = security_manager.getUser()
                    if user and hasattr(user, 'getId') and not user.getId():
                        user = None
                except (ImportError, AttributeError):
                    pass
            
            if not user:
                return self._render_error('Usuário não autenticado')
            
            can_view, motivo = verificar_permissao_acesso(self.context, cod_documento, user)
            
            if not can_view:
                registrar_acesso_documento(cod_documento, user, False, motivo)
                return self._render_error(f'Acesso não autorizado para o usuário {user.getUserName()}')
            
            registrar_acesso_documento(cod_documento, user, True, motivo)
            
            # Obtém todos os dados
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            tool = getToolByName(self.context, 'portal_sagl')
            
            documento_data = self._get_documento_data(cod_documento)
            pasta_data = self._get_pasta_data(cod_documento, action, tool, portal)
            # Garante que pasta_data nunca seja None
            if pasta_data is None:
                pasta_data = {
                    'error': 'Erro ao obter dados da pasta',
                    'async': False,
                    'documentos': []
                }
            portal_config = self._get_portal_config(portal)
            materias_vinculadas = self._get_materias_vinculadas(cod_documento, portal)
            documentos_administrativos_vinculados = self._get_documentos_administrativos_vinculados(cod_documento, portal)
            portal_url = str(portal.absolute_url())
            
            # Renderiza HTML com os dados
            html_result = self._render_html(
                cod_documento, action, documento_data, pasta_data, 
                portal_config, materias_vinculadas, documentos_administrativos_vinculados, portal_url
            )
            
            # Retorna o HTML diretamente
            return html_result
            
        except Exception as e:
            logger.error(f"[PastaDigitalAdmView] Erro: {e}", exc_info=True)
            try:
                # Tenta definir AUTHENTICATED_USER no REQUEST para evitar erros em templates de erro
                if 'AUTHENTICATED_USER' not in self.request:
                    try:
                        from AccessControl import getSecurityManager
                        security_manager = getSecurityManager()
                        user = security_manager.getUser()
                        if user:
                            self.request['AUTHENTICATED_USER'] = user
                    except (ImportError, AttributeError):
                        pass
            except Exception:
                pass  # Ignora erros ao tentar definir AUTHENTICATED_USER
            
            self.request.RESPONSE.setStatus(500)
            return self._render_error(str(e))
    
    def _render_error(self, error_msg):
        """Renderiza página de erro formatada"""
        # Determina se é erro de acesso não autorizado
        is_unauthorized = 'não autorizado' in error_msg.lower() or 'não autenticado' in error_msg.lower()
        status_code = 403 if is_unauthorized else 400
        
        self.request.RESPONSE.setStatus(status_code)
        
        # Obtém URL base do portal para o link "Página Inicial" e CSSs
        home_url = '/'
        portal_url = ''
        try:
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            if portal and hasattr(portal, 'absolute_url'):
                portal_url = portal.absolute_url()
                home_url = portal_url
                # Garante que termina com /
                if not home_url.endswith('/'):
                    home_url += '/'
        except Exception as e:
            logger.debug(f"[_render_error] Erro ao obter URL do portal: {e}")
            # Tenta obter do REQUEST se possível
            try:
                request_url = self.request.get('ACTUAL_URL', '') or self.request.get('REQUEST_URI', '')
                if request_url:
                    # Extrai base URL (até /sagl/ por exemplo)
                    from urllib.parse import urlparse
                    parsed = urlparse(request_url)
                    if '/@@' in parsed.path:
                        # Remove tudo após /@@
                        base_path = parsed.path.split('/@@')[0]
                        portal_url = f"{parsed.scheme}://{parsed.netloc}{base_path}"
                        home_url = portal_url
                    else:
                        # Usa apenas até o primeiro / após o domínio
                        path_parts = parsed.path.strip('/').split('/')
                        if path_parts and path_parts[0]:
                            # Pega apenas o primeiro segmento (ex: /sagl/)
                            portal_url = f"{parsed.scheme}://{parsed.netloc}/{path_parts[0]}"
                            home_url = portal_url
                        else:
                            portal_url = f"{parsed.scheme}://{parsed.netloc}"
                            home_url = portal_url
                    # Garante que termina com /
                    if not home_url.endswith('/'):
                        home_url += '/'
                        portal_url = home_url
            except Exception:
                pass
        
        # URLs dos CSSs do sistema
        css_bootstrap_url = f"{portal_url}/assets/css/bootstrap.min.css" if portal_url else ''
        css_icons_url = f"{portal_url}/assets/css/icons.min.css" if portal_url else ''
        css_app_url = f"{portal_url}/assets/css/app.css" if portal_url else ''
        
        # Gera HTML com CSSs do sistema se disponíveis
        css_links = ''
        if css_bootstrap_url:
            css_links += f'    <link rel="stylesheet" href="{css_bootstrap_url}">\n'
        if css_icons_url:
            css_links += f'    <link rel="stylesheet" href="{css_icons_url}">\n'
        if css_app_url:
            css_links += f'    <link rel="stylesheet" href="{css_app_url}">\n'
        
        return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Erro - Pasta Digital</title>
{css_links}    <style>
        body {{
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .error-container {{
            max-width: 600px;
            width: 100%;
        }}
        .error-icon {{
            width: 80px;
            height: 80px;
            margin: 0 auto 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
        }}
        .error-message {{
            font-size: 16px;
            line-height: 1.6;
            text-align: left;
        }}
        .log-info-icon {{
            width: 20px;
            height: 20px;
            flex-shrink: 0;
        }}
        @media (max-width: 640px) {{
            .error-message {{
                font-size: 14px;
            }}
        }}
    </style>
</head>
<body class="bg-light">
    <div class="error-container">
        <div class="card shadow-lg">
            <div class="card-body p-4 p-md-5 text-center">
                <div class="error-icon bg-danger text-white mb-4">
                    ⚠️
                </div>
                <h1 class="card-title mb-3">Erro de Acesso</h1>
                <div class="error-message alert alert-danger mb-4">
                    {error_msg}
                </div>
                {"<div class='alert alert-info d-flex align-items-center justify-content-center'><svg class='log-info-icon me-2' fill='currentColor' viewBox='0 0 20 20'><path fill-rule='evenodd' d='M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z' clip-rule='evenodd'/></svg><span>A tentativa de acesso foi registrada nos logs do sistema para fins de auditoria e segurança.</span></div>" if is_unauthorized else ""}
                <div class="mt-4 d-flex gap-2 justify-content-center flex-wrap">
                    <a href="javascript:history.back()" class="btn btn-secondary">Voltar</a>
                    <a href="{home_url}" class="btn btn-primary">Página Inicial</a>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    def _get_documento_data(self, cod_documento):
        """Obtém dados do documento administrativo"""
        session = Session()
        try:
            resultado = session.query(DocumentoAdministrativo, TipoDocumentoAdministrativo)\
                .join(TipoDocumentoAdministrativo, 
                      DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
                .filter(DocumentoAdministrativo.cod_documento == cod_documento)\
                .filter(DocumentoAdministrativo.ind_excluido == 0)\
                .first()
            
            if not resultado:
                return None
            
            doc_obj, tipo_obj = resultado
            
            # CRÍTICO: Constrói identificação do processo no formato: PA 308/2025
            sgl_tipo = tipo_obj.sgl_tipo_documento or ''
            num_doc = doc_obj.num_documento or 0
            ano_doc = doc_obj.ano_documento or 0
            id_processo = f"{sgl_tipo} {num_doc}/{ano_doc}" if sgl_tipo and num_doc and ano_doc else f"Documento {doc_obj.cod_documento}"
            
            # Constrói título completo (pode ser usado como fallback)
            titulo_completo = f"{tipo_obj.des_tipo_documento or sgl_tipo} {num_doc}/{ano_doc}" if tipo_obj.des_tipo_documento else id_processo
            
            return {
                'cod_documento': doc_obj.cod_documento,
                'num_documento': doc_obj.num_documento,
                'ano_documento': doc_obj.ano_documento,
                'des_tipo_documento': tipo_obj.des_tipo_documento or '',
                'sgl_tipo_documento': tipo_obj.sgl_tipo_documento or '',
                'id_processo': id_processo,  # CRÍTICO: Identificação formatada (ex: PA 308/2025)
                'titulo': titulo_completo,  # Título completo para exibição
                'txt_assunto': doc_obj.txt_assunto or '',
                'txt_observacao': doc_obj.txt_observacao or '',
                'txt_interessado': doc_obj.txt_interessado or '',
                'dat_documento': doc_obj.dat_documento.strftime('%Y-%m-%d') if doc_obj.dat_documento else None,
                'num_protocolo': doc_obj.num_protocolo,
            }
        finally:
            session.close()
    
    def _get_pasta_data(self, cod_documento, action, tool, portal):
        """
        Obtém dados da pasta digital com cache robusto e verificação de tasks.
        Alinhado com processo_leg - mesma lógica de regeneração.
        """
        try:
            # Cria um objeto de resposta base para garantir que nunca seja None
            base_response = {
                'async': True,  # SEMPRE True para action=pasta (força o monitor aparecer)
                'task_id': None,
                'status': 'PENDING',
                'documentos': [],
                'cod_documento': int(cod_documento) if cod_documento and str(cod_documento).isdigit() else cod_documento,
                'total_paginas': 0,
                'message': 'Processando pasta digital...'
            }
            
            # Para action='download', retorna dados mínimos
            if action == 'download':
                base_response['action'] = 'download'
                base_response['async'] = False
                return base_response
            
            # Para action='pasta', processa normalmente (mesma lógica do processo_leg)
            if action == 'pasta':
                try:
                    import traceback
                    portal_url = str(portal.absolute_url())
                    cod_documento_int = int(cod_documento)
                    cod_documento_str = str(cod_documento_int)  # Define no início para uso em todo o escopo
                    
                    # CRÍTICO: Verifica se já existe task ativa antes de criar nova
                    # Isso evita enfileirar tasks infinitamente
                    has_active_task = False
                    task_id = None
                    task_status = None
                    
                    # 1. Verifica cache de tasks recém-criadas (evita race condition)
                    current_time = time.time()
                    cache_ttl = 60.0  # 60 segundos - aumentado para garantir que tasks grandes ainda estejam no cache quando documentos forem encontrados
                    
                    # Flag para indicar se regeneração foi detectada (evita retornar documentos quando precisa regenerar)
                    needs_regeneration = False
                    
                    if cod_documento_str in _recent_tasks_cache:
                        cached_task_id, cache_timestamp = _recent_tasks_cache[cod_documento_str]
                        if current_time - cache_timestamp < cache_ttl:
                            # Task foi criada recentemente, mas verifica se já há documentos prontos
                            
                            # Inicializa has_recent_task antes do try block para evitar UnboundLocalError
                            has_recent_task = True
                            
                            # CRÍTICO: Verifica se há documentos prontos mesmo com task recente
                            # A task pode ter completado rapidamente
                            try:
                                # Usa serviço para obter documentos prontos
                                service = ProcessoAdmService(self.context, self.request)
                                check_result = service.get_documentos_prontos(cod_documento, skip_signature_check=True)
                                
                                if isinstance(check_result, dict) and 'documentos' in check_result and len(check_result.get('documentos', [])) > 0:
                                    # CRÍTICO: Verifica se diretório ainda existe antes de retornar documentos
                                    # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                    dir_base_check = get_processo_dir_adm(cod_documento_int)
                                    if not os.path.exists(dir_base_check):
                                        # Diretório não existe - documentos foram apagados
                                        # Limpa cache de tasks recentes
                                        _recent_tasks_cache.pop(cod_documento_str, None)
                                        # Limpa cache de documentos (filesystem)
                                        _delete_cache_from_filesystem_adm(cod_documento_int)
                                        # Força criação de nova task
                                        has_recent_task = False
                                        cached_task_id = None
                                        needs_regeneration = True
                                        # Continua para criar nova task (não retorna aqui)
                                    else:
                                        # Diretório existe - verifica se documentos foram alterados usando documentos_metadados.json
                                        # CRÍTICO: Usa comparação com documentos_metadados.json
                                        has_changes_metadados, changes_details = _compare_documents_with_metadados_adm(cod_documento_int, portal)
                                        
                                        if has_changes_metadados:
                                            # Mudanças detectadas - arquivos foram adicionados, removidos ou modificados
                                            # Limpa cache de tasks recentes
                                            _recent_tasks_cache.pop(cod_documento_str, None)
                                            # Limpa cache de documentos
                                            _delete_cache_from_filesystem_adm(cod_documento_int)
                                            # Força criação de nova task
                                            has_recent_task = False
                                            cached_task_id = None
                                            needs_regeneration = True
                                            # Continua para criar nova task (não retorna aqui)
                                        else:
                                            # Diretório existe e comparação com metadados corresponde - documentos estão atualizados
                                            # Documentos prontos encontrados!
                                            # CRÍTICO: Só retorna documentos se não precisa regenerar
                                            if not needs_regeneration:
                                                result_copy = copy.deepcopy(check_result)
                                                # CRÍTICO: Documentos já existem, pula monitor e mostra apenas carregamento
                                                result_copy['async'] = False
                                                result_copy['task_id'] = None
                                                result_copy['message'] = 'Carregando documentos...'
                                                if 'total_paginas' in result_copy:
                                                    result_copy['total_paginas'] = result_copy['total_paginas']
                                                if 'cod_documento' not in result_copy:
                                                    result_copy['cod_documento'] = cod_documento_int
                                                # CRÍTICO: Calcula hash e tamanhos dos documentos e atualiza cache (apenas filesystem)
                                                documents_hash = _calculate_documents_hash_adm(cod_documento_int, portal)
                                                documents_sizes = _calculate_documents_sizes_adm(cod_documento_int, portal)
                                                _save_cache_to_filesystem_adm(cod_documento_int, result_copy, current_time, documents_hash, documents_sizes)
                                                
                                                return result_copy
                            except Exception as check_err:
                                logger.debug(f"[_get_pasta_data] Erro ao verificar documentos prontos (task recente): {check_err}")
                            
                            # CRÍTICO: Antes de retornar status PENDING, verifica se diretório existe
                            # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                            # CRÍTICO: Se has_recent_task foi forçado para False (regeneração necessária), não retorna PENDING
                            if not has_recent_task or needs_regeneration:
                                # Regeneração foi detectada - não retorna PENDING, continua para criar nova task
                                # Não retorna aqui - continua para criar nova task
                                pass
                            else:
                                dir_base_check = get_processo_dir_adm(cod_documento_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_documento_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem_adm(cod_documento_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Continua para criar nova task (não retorna aqui)
                                else:
                                    # Diretório existe - retorna status PENDING normalmente
                                    # Se não encontrou documentos prontos, retorna status PENDING
                                    # Obtém status detalhado da task para incluir informações de progresso
                                    try:
                                        service_status = ProcessoAdmService(self.context, self.request)
                                        task_status_detail = service_status.verificar_task_status(cached_task_id)
                                        if task_status_detail:
                                            # Inclui informações de progresso se disponíveis
                                            base_response.update({
                                                'task_id': str(cached_task_id),
                                                'status': task_status_detail.get('status', 'PENDING'),
                                                'message': task_status_detail.get('message', 'Tarefa recém-criada, aguardando processamento'),
                                            })
                                            # Adiciona informações de progresso se disponíveis
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
                                        logger.debug(f"[_get_pasta_data] Erro ao obter status detalhado da task: {status_err}")
                                        base_response.update({
                                            'task_id': str(cached_task_id),
                                            'status': 'PENDING',
                                            'message': 'Tarefa recém-criada, aguardando processamento'
                                        })
                                    return base_response
                        else:
                            # Cache expirado, remove
                            _recent_tasks_cache.pop(cod_documento_str, None)
                    
                    # 2. Verifica tasks ativas no Celery usando serviço
                    try:
                        service = ProcessoAdmService(self.context, self.request)
                        has_active_task, task_id, task_status = service.verificar_tasks_ativas(cod_documento_int)
                        if has_active_task:
                            logger.debug(f"[_get_pasta_data] Task ativa encontrada via serviço: {task_id}, status: {task_status}")
                    except Exception as task_check_err:
                        logger.debug(f"[_get_pasta_data] Erro ao verificar tasks ativas: {task_check_err}")
                    
                    # CRÍTICO: Se não há task ativa no Celery, limpa cache (task pode ter terminado)
                    if not has_active_task and cod_documento_str in _recent_tasks_cache:
                        _recent_tasks_cache.pop(cod_documento_str, None)
                    
                    # Se encontrou task ativa, verifica se os arquivos existem antes de retornar
                    # Se os arquivos foram apagados, invalida a task e cria nova
                    if has_active_task and task_id:
                        # CRÍTICO: Verifica se os arquivos existem mesmo com task ativa
                        # Se os arquivos foram apagados manualmente, a task pode estar rodando mas os arquivos não existem
                        dir_base = get_processo_dir_adm(cod_documento_int)
                        metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                        
                        if not os.path.exists(metadados_path):
                            # Arquivos não existem - task pode estar rodando mas arquivos foram apagados
                            # Limpa cache de tasks
                            _recent_tasks_cache.pop(cod_documento_str, None)
                            # Limpa cache de documentos
                            _delete_cache_from_filesystem_adm(cod_documento_int)
                            # Não retorna task existente - continua para criar nova task
                            has_active_task = False
                            task_id = None
                        else:
                            # Arquivos existem - retorna task ativa
                            _recent_tasks_cache[cod_documento_str] = (task_id, current_time)
                            # Limpa cache antigo (mantém apenas últimos 20)
                            if len(_recent_tasks_cache) > 20:
                                sorted_items = sorted(_recent_tasks_cache.items(), key=lambda x: x[1][1])
                                for key, _ in sorted_items[:-20]:
                                    _recent_tasks_cache.pop(key, None)
                            
                            # Obtém status detalhado da task para incluir informações de progresso
                            try:
                                service_status = ProcessoAdmService(self.context, self.request)
                                task_status_detail = service_status.verificar_task_status(task_id)
                                if task_status_detail:
                                    # Inclui informações de progresso se disponíveis
                                    base_response.update({
                                        'task_id': str(task_id),
                                        'status': task_status_detail.get('status', task_status or 'PENDING'),
                                        'message': task_status_detail.get('message', 'Tarefa já está em execução ou na fila'),
                                    })
                                    # Adiciona informações de progresso se disponíveis
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
                                logger.debug(f"[_get_pasta_data] Erro ao obter status detalhado da task: {status_err}")
                                base_response.update({
                                    'task_id': str(task_id),
                                    'status': str(task_status or 'PENDING'),
                                    'message': 'Tarefa já está em execução ou na fila'
                                })
                            return base_response
                    
                    # CRÍTICO: Verifica se o diretório base existe ANTES de verificar tasks recentes
                    # Se o diretório não existe, documentos foram apagados - limpa cache e cria nova task
                    dir_base = get_processo_dir_adm(cod_documento_int)
                    
                    if not os.path.exists(dir_base):
                        # Diretório não existe - documentos foram apagados
                        # Limpa cache de tasks recentes
                        _recent_tasks_cache.pop(cod_documento_str, None)
                        # Limpa cache de documentos
                        _delete_cache_from_filesystem_adm(cod_documento_int)
                        # Limpa cache de hash
                        if cod_documento_str in _hash_cache:
                            _hash_cache.pop(cod_documento_str, None)
                        # Força criação de nova task (has_recent_task = False)
                        has_recent_task = False
                        cached_task_id = None
                    else:
                        # Diretório existe - verifica se há task recente no cache (pode ser polling após SUCCESS)
                        # Se houver task recente, não verifica assinatura (apenas verifica se arquivos existem)
                        # Se não houver task recente, verifica assinatura para decidir se precisa regenerar
                        has_recent_task = False
                        cached_task_id = None
                        if cod_documento_str in _recent_tasks_cache:
                            cached_task_id, cache_timestamp = _recent_tasks_cache[cod_documento_str]
                            time_since_cache = time.time() - cache_timestamp
                            # Se a task foi criada recentemente (dentro de 60 segundos), pode ser polling após SUCCESS
                            if time_since_cache < 60.0:
                                has_recent_task = True
                    
                    # CRÍTICO: Só verifica documentos prontos se há task recente (polling após SUCCESS)
                    # Se não há task recente (acesso inicial OU documentos apagados), pula verificação e vai direto criar task
                    if has_recent_task:
                        try:
                            # Usa serviço para obter documentos prontos
                            service = ProcessoAdmService(self.context, self.request)
                            result = service.get_documentos_prontos(cod_documento, skip_signature_check=True)
                            
                            # CRÍTICO: Se retornou estrutura vazia, verifica se diretório existe
                            # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) == 0:
                                # Verifica se diretório existe
                                dir_base_check = get_processo_dir_adm(cod_documento_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_documento_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem_adm(cod_documento_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Continua para criar nova task (não retorna aqui)
                            
                            # Se encontrou documentos prontos, verifica se diretório ainda existe antes de retornar
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                # CRÍTICO: Verifica se diretório ainda existe antes de retornar documentos
                                # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                dir_base_check = get_processo_dir_adm(cod_documento_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_documento_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem_adm(cod_documento_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Continua para criar nova task (não retorna aqui)
                                else:
                                    # Diretório existe - verifica se documentos foram alterados usando documentos_metadados.json
                                    # CRÍTICO: Usa comparação com documentos_metadados.json
                                    has_changes_metadados, changes_details = _compare_documents_with_metadados_adm(cod_documento_int, portal)
                                    
                                    if has_changes_metadados:
                                        # Mudanças detectadas - arquivos foram adicionados, removidos ou modificados
                                        # Limpa cache de tasks recentes
                                        _recent_tasks_cache.pop(cod_documento_str, None)
                                        # Limpa cache de documentos
                                        _delete_cache_from_filesystem_adm(cod_documento_int)
                                        # Força criação de nova task
                                        has_recent_task = False
                                        cached_task_id = None
                                        needs_regeneration = True
                                        # Continua para criar nova task (não retorna aqui)
                                    else:
                                        # Diretório existe e comparação com metadados corresponde - documentos estão atualizados
                                        # CRÍTICO: Cria uma cópia profunda para evitar problemas de referência compartilhada
                                        result_copy = copy.deepcopy(result)
                                        
                                        # CRÍTICO: Sempre mostra monitor quando documentos são encontrados
                                        # Mesmo sem task recente, mostra monitor com status SUCCESS para feedback visual
                                        if cached_task_id:
                                            result_copy['async'] = True
                                            result_copy['task_id'] = str(cached_task_id)
                                            result_copy['status'] = 'SUCCESS'
                                            result_copy['message'] = 'Pasta digital gerada com sucesso'
                                        else:
                                            # Sem task recente - documentos já existem, pula monitor e mostra apenas carregamento
                                            result_copy['async'] = False
                                            result_copy['task_id'] = None
                                            result_copy['message'] = 'Carregando documentos...'
                                        
                                        # Garante campos obrigatórios
                                        if 'total_paginas' in result_copy:
                                            result_copy['total_paginas'] = result_copy['total_paginas']
                                        if 'cod_documento' not in result_copy:
                                            result_copy['cod_documento'] = cod_documento_int
                                        
                                        # CRÍTICO: Calcula hash e tamanhos dos documentos e atualiza cache (apenas filesystem)
                                        documents_hash = _calculate_documents_hash_adm(cod_documento_int, portal)
                                        documents_sizes = _calculate_documents_sizes_adm(cod_documento_int, portal)
                                        _save_cache_to_filesystem_adm(cod_documento_int, result_copy, current_time, documents_hash, documents_sizes)
                                        
                                        return result_copy
                        except Exception as view_err:
                            logger.error(f"[_get_pasta_data] Erro ao verificar documentos prontos (task recente): {view_err}", exc_info=True)
                    
                    # Se há task recente mas não encontrou documentos, aguarda e tenta novamente
                    if has_recent_task:
                        try:
                            # Salva action original
                            original_action = self.request.form.get('action')
                            
                            # Prepara para chamar a view
                            # Usa serviço para obter documentos prontos (retry após task recente)
                            service = ProcessoAdmService(self.context, self.request)
                            result = service.get_documentos_prontos(cod_documento, skip_signature_check=True)
                            
                            # Se encontrou documentos prontos, retorna eles
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                # CRÍTICO: Documentos já existem, pula monitor e mostra apenas carregamento
                                result['async'] = False
                                result['task_id'] = None
                                result['message'] = 'Carregando documentos...'
                                
                                # Garante campos obrigatórios
                                if 'total_paginas' in result:
                                    result['total_paginas'] = result['total_paginas']
                                if 'cod_documento' not in result:
                                    result['cod_documento'] = cod_documento_int
                                
                                return result
                            else:
                                # CRÍTICO: Se retornou estrutura vazia, verifica se diretório existe
                                # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                dir_base_check = get_processo_dir_adm(cod_documento_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_documento_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem_adm(cod_documento_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Continua para criar nova task (não retorna aqui)
                                else:
                                    # Se há task recente mas não encontrou documentos, pode ser que ainda estejam sendo salvos
                                    # Aguarda um pouco e tenta novamente (retry)
                                    time.sleep(1.0)  # Aguarda 1 segundo para dar tempo dos arquivos serem salvos
                                
                                # Tenta novamente
                                try:
                                    # Usa serviço para obter documentos prontos (retry)
                                    service = ProcessoAdmService(self.context, self.request)
                                    result = service.get_documentos_prontos(cod_documento, skip_signature_check=True)
                                    
                                    # CRÍTICO: Se retornou estrutura vazia, verifica se diretório existe
                                    # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                    if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) == 0:
                                        # Verifica se diretório existe
                                        dir_base_check = get_processo_dir_adm(cod_documento_int)
                                        if not os.path.exists(dir_base_check):
                                            # Diretório não existe - documentos foram apagados
                                            # Limpa cache de tasks recentes
                                            _recent_tasks_cache.pop(cod_documento_str, None)
                                            # Limpa cache de documentos (filesystem)
                                            _delete_cache_from_filesystem_adm(cod_documento_int)
                                            # Força criação de nova task
                                            has_recent_task = False
                                            cached_task_id = None
                                            needs_regeneration = True
                                            # Continua para criar nova task (não retorna aqui)
                                    
                                    if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                        # CRÍTICO: Sempre mostra monitor quando documentos são encontrados
                                        result['async'] = True
                                        result['task_id'] = None  # Sem task_id específico, mas monitor aparece
                                        result['status'] = 'SUCCESS'
                                        result['message'] = 'Pasta digital carregada com sucesso'
                                        
                                        if 'total_paginas' in result:
                                            result['total_paginas'] = result['total_paginas']
                                        if 'cod_documento' not in result:
                                            result['cod_documento'] = cod_documento_int
                                        
                                        return result
                                except Exception as retry_err:
                                    logger.warning(f"[_get_pasta_data] Erro no retry: {retry_err}")
                                
                                # CRÍTICO: Antes de retornar status de processamento, verifica se diretório existe
                                # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                dir_base_check = get_processo_dir_adm(cod_documento_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_documento_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem_adm(cod_documento_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Continua para criar nova task (não retorna aqui)
                                else:
                                    # Se ainda não encontrou após retry, retorna status de processamento
                                    base_response.update({
                                        'task_id': cached_task_id,
                                        'status': 'PROGRESS',
                                        'message': 'Documentos ainda sendo processados, aguarde...',
                                        'documentos': []
                                    })
                                    return base_response
                        except Exception as view_err:
                            logger.error(f"[_get_pasta_data] Erro ao verificar documentos prontos: {view_err}", exc_info=True)
                    
                    # CRÍTICO: Se não há task recente, verifica se há documentos prontos antes de criar nova task
                    # Isso é importante para quando loadDocumentosAfterSuccess é chamado após SUCCESS
                    # mas o cache de tasks recentes não está mais ativo
                    if not has_recent_task:
                        # Primeiro, verifica o cache de documentos prontos (filesystem)
                        cached_data = None
                        # Cache em memória removido - usa apenas filesystem
                        cached_data = _load_cache_from_filesystem_adm(cod_documento_int)
                        if cached_data:
                            logger.debug(f"[_get_pasta_data] Cache carregado do filesystem para {cod_documento_str}")
                        
                        if cached_data:
                            # CRÍTICO: cached_data agora é um dict completo (não mais tupla)
                            # Mantém compatibilidade com versões antigas que retornavam tupla
                            if isinstance(cached_data, dict):
                                # Formato novo: dict completo com todos os campos
                                cache_timestamp = cached_data.get('timestamp', 0)
                                cached_hash = cached_data.get('hash', None)
                                cached_sizes = cached_data.get('sizes', None)
                                # cached_docs pode ser dict completo ou apenas lista de documentos
                                cached_docs = cached_data  # Usa o dict completo para preservar total_paginas
                            elif isinstance(cached_data, (tuple, list)):
                                # Formato antigo (tupla) - compatibilidade
                                if len(cached_data) == 4:
                                    cached_docs, cache_timestamp, cached_hash, cached_sizes = cached_data
                                elif len(cached_data) == 3:
                                    cached_docs, cache_timestamp, cached_hash = cached_data
                                    cached_sizes = None
                                else:
                                    cached_docs, cache_timestamp = cached_data
                                    cached_hash = None
                                    cached_sizes = None
                            else:
                                logger.warning(f"[_get_pasta_data] Formato de cache desconhecido: {type(cached_data)}")
                                cached_data = None
                            
                            if cached_data and cache_timestamp and current_time - cache_timestamp < _ready_documents_cache_ttl:
                                # Verifica se os documentos mudaram comparando o hash
                                current_hash = _calculate_documents_hash_adm(cod_documento_int, portal)
                                
                                # Se não há hash no cache (cache antigo) ou não foi possível calcular hash atual,
                                # não usa o cache - verifica documentos no sistema para garantir dados atualizados
                                if cached_hash is None or current_hash is None:
                                    # Cache antigo sem hash ou não foi possível calcular hash atual
                                    _delete_cache_from_filesystem_adm(cod_documento_int)
                                elif current_hash != cached_hash:
                                    # Hash mudou - documentos foram modificados, excluídos ou adicionados
                                    _delete_cache_from_filesystem_adm(cod_documento_int)
                                else:
                                    # Hash válido e igual - verifica se os arquivos ainda existem no filesystem
                                    # Se os arquivos foram apagados do filesystem, força regeneração mesmo com hash igual
                                    
                                    # Calcula o diretório base
                                    dir_base = get_processo_dir_adm(cod_documento_int)
                                    metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                                    
                                    # Verifica se os arquivos existem no filesystem
                                    if not os.path.exists(metadados_path):
                                        _delete_cache_from_filesystem_adm(cod_documento_int)
                                        # CRÍTICO: Não retorna do cache - continua para criar nova task e mostrar monitor
                                        # Não entra no else abaixo, vai direto para criar task
                                    else:
                                        # Hash válido e arquivos existem - verifica se documentos foram alterados usando documentos_metadados.json
                                        # CRÍTICO: Usa comparação com documentos_metadados.json
                                        has_changes_metadados, changes_details = _compare_documents_with_metadados_adm(cod_documento_int, portal)
                                        
                                        if has_changes_metadados:
                                            # Mudanças detectadas - arquivos foram adicionados, removidos ou modificados
                                            _delete_cache_from_filesystem_adm(cod_documento_int)
                                            # Limpa cache de tasks recentes para forçar criação de nova task
                                            _recent_tasks_cache.pop(cod_documento_str, None)
                                            # Não retorna do cache - continua para criar nova task
                                            # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                            has_recent_task = False
                                            cached_task_id = None
                                            # Não cria result_copy - continua para criar nova task
                                        else:
                                            # Hash válido e comparação com metadados corresponde - cache ainda é válido
                                            # Cria result_copy - comparação com metadados passou
                                            if isinstance(cached_docs, dict):
                                                # cached_docs já é um dict completo (formato novo)
                                                result_copy = copy.deepcopy(cached_docs)
                                                # Garante que tem a estrutura esperada
                                                if 'documentos' not in result_copy:
                                                    result_copy['documentos'] = []
                                                # Preserva total_paginas do cache
                                                if 'total_paginas' not in result_copy or result_copy.get('total_paginas', 0) == 0:
                                                    # Se total_paginas não está no cache ou é 0, tenta calcular dos documentos
                                                    documentos_list = result_copy.get('documentos', [])
                                                    if documentos_list:
                                                        # Calcula total_paginas como o end_page do último documento
                                                        total_calc = 0
                                                        for doc in documentos_list:
                                                            end_page = doc.get('end_page', 0) or doc.get('num_pages', 0)
                                                            if end_page > total_calc:
                                                                total_calc = end_page
                                                        if total_calc > 0:
                                                            result_copy['total_paginas'] = total_calc
                                                            logger.debug(f"[_get_pasta_data] total_paginas calculado dos documentos: {total_calc}")
                                            else:
                                                # Se cached_docs não é dict (formato antigo), constrói dict com documentos
                                                documentos_list = cached_docs if isinstance(cached_docs, list) else []
                                                # Calcula total_paginas dos documentos
                                                total_calc = 0
                                                for doc in documentos_list:
                                                    end_page = doc.get('end_page', 0) or doc.get('num_pages', 0)
                                                    if end_page > total_calc:
                                                        total_calc = end_page
                                                
                                                result_copy = {
                                                    'documentos': documentos_list,
                                                    'total_paginas': total_calc,
                                                    'cod_documento': cod_documento_int
                                                }
            
                                            # Só processa result_copy se foi criado (tamanhos não mudaram ou não há cache para comparar)
                                            if result_copy is not None:
                                                # CRÍTICO: Verifica se há task recente no cache para mostrar monitor
                                                # Se houver task recente (dentro de 60 segundos), mostra monitor com status SUCCESS
                                                has_recent_task_for_monitor = False
                                                task_id_for_monitor = None
                                                if cod_documento_str in _recent_tasks_cache:
                                                    cached_task_id_check, cache_timestamp_check = _recent_tasks_cache[cod_documento_str]
                                                    time_since_cache_check = time.time() - cache_timestamp_check
                                                    if time_since_cache_check < 60.0:  # Task foi criada há menos de 60 segundos
                                                        has_recent_task_for_monitor = True
                                                        task_id_for_monitor = str(cached_task_id_check)
                                                
                                                # CRÍTICO: Se há task recente, mostra monitor. Se não, pula monitor e mostra apenas carregamento
                                                if has_recent_task_for_monitor:
                                                    result_copy['async'] = True
                                                    result_copy['task_id'] = task_id_for_monitor
                                                    result_copy['status'] = 'SUCCESS'
                                                    result_copy['message'] = 'Pasta digital gerada com sucesso'
                                                else:
                                                    # Sem task recente - documentos já existem, pula monitor e mostra apenas carregamento
                                                    result_copy['async'] = False
                                                    result_copy['task_id'] = None
                                                    result_copy['message'] = 'Carregando documentos...'
                                                
                                                # Garante campos obrigatórios
                                                if 'cod_documento' not in result_copy:
                                                    result_copy['cod_documento'] = cod_documento_int
                                                
                                                # CRÍTICO: Garante que total_paginas está presente e é um número válido
                                                total_paginas_cache = result_copy.get('total_paginas', 0)
                                                if total_paginas_cache == 0 or total_paginas_cache is None:
                                                    # Recalcula se necessário
                                                    documentos_list = result_copy.get('documentos', [])
                                                    total_recalc = 0
                                                    for doc in documentos_list:
                                                        end_page = doc.get('end_page', 0) or doc.get('num_pages', 0)
                                                        if end_page > total_recalc:
                                                            total_recalc = end_page
                                                    if total_recalc > 0:
                                                        result_copy['total_paginas'] = total_recalc
                                                        logger.debug(f"[_get_pasta_data] total_paginas recalculado: {total_recalc}")
                                                
                                                logger.debug(f"[_get_pasta_data] Retornando cache com total_paginas={result_copy.get('total_paginas', 0)}")
                                                return result_copy
                            else:
                                # Cache expirado, remove (filesystem)
                                _delete_cache_from_filesystem_adm(cod_documento_int)
                        
                        # Cache não encontrado ou expirado, verifica documentos no sistema
                        try:
                            # Usa serviço para obter documentos prontos
                            service = ProcessoAdmService(self.context, self.request)
                            result = service.get_documentos_prontos(cod_documento, skip_signature_check=True)
                            
                            # Se encontrou documentos prontos, verifica hash ANTES de retornar
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                documentos_count = len(result.get('documentos', []))
                                
                                # CRÍTICO: Calcula hash dos documentos ATUAIS antes de retornar
                                current_documents_hash = _calculate_documents_hash_adm(cod_documento_int, portal)
                                
                                # Verifica se há hash em cache para comparar
                                should_return_documents = True
                                
                                # CRÍTICO: Compara usando documentos_metadados.json (única fonte de verdade)
                                # Se JSON não existe ou há diferenças, precisa regenerar
                                has_changes_metadados, changes_details = _compare_documents_with_metadados_adm(cod_documento_int, portal)
                                
                                logger.debug(f"[_get_pasta_data] Comparação de metadados: has_changes={has_changes_metadados}, details={changes_details}")
                                
                                if has_changes_metadados:
                                    # Mudanças detectadas ou JSON não existe - precisa regenerar
                                    
                                    # Verifica se há task ativa antes de criar nova task (evita criar tasks duplicadas)
                                    try:
                                        service_check = ProcessoAdmService(self.context, self.request)
                                        has_active_task_check, task_id_check, task_status_check = service_check.verificar_tasks_ativas(cod_documento_int)
                                        if has_active_task_check:
                                            # Não cria nova task - aguarda task atual completar
                                            should_return_documents = False
                                            has_recent_task = True
                                            cached_task_id = task_id_check
                                            # Não limpa cache - mantém task ativa
                                        else:
                                            # Limpa cache de tasks recentes para forçar criação de nova task
                                            _recent_tasks_cache.pop(cod_documento_str, None)
                                            # Limpa cache de documentos
                                            _delete_cache_from_filesystem_adm(cod_documento_int)
                                            should_return_documents = False
                                            # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                            has_recent_task = False
                                            cached_task_id = None
                                    except Exception as check_task_err:
                                        logger.warning(f"[_get_pasta_data] Erro ao verificar tasks ativas: {check_task_err}, assumindo que precisa criar nova task")
                                        # Em caso de erro, assume que precisa criar nova task
                                        _recent_tasks_cache.pop(cod_documento_str, None)
                                        _delete_cache_from_filesystem_adm(cod_documento_int)
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
                                    # Se houver task recente (dentro de 60 segundos), mostra monitor com status SUCCESS
                                    has_recent_task_for_monitor = False
                                    task_id_for_monitor = None
                                    if cod_documento_str in _recent_tasks_cache:
                                        cached_task_id_check, cache_timestamp_check = _recent_tasks_cache[cod_documento_str]
                                        time_since_cache_check = time.time() - cache_timestamp_check
                                        if time_since_cache_check < 60.0:  # Task foi criada há menos de 60 segundos
                                            has_recent_task_for_monitor = True
                                            task_id_for_monitor = str(cached_task_id_check)
                                    
                                    # CRÍTICO: Se há task recente, mostra monitor. Se não, pula monitor e mostra apenas carregamento
                                    if has_recent_task_for_monitor:
                                        result_copy['async'] = True
                                        result_copy['task_id'] = task_id_for_monitor
                                        result_copy['status'] = 'SUCCESS'
                                        result_copy['message'] = 'Pasta digital gerada com sucesso'
                                    else:
                                        # Sem task recente - documentos já existem, pula monitor e mostra apenas carregamento
                                        result_copy['async'] = False
                                        result_copy['task_id'] = None
                                        result_copy['message'] = 'Carregando documentos...'
                                    
                                    # Garante campos obrigatórios
                                    if 'cod_documento' not in result_copy:
                                        result_copy['cod_documento'] = cod_documento_int
                                    
                                    # CRÍTICO: Garante que total_paginas está presente e é um número válido
                                    total_paginas_service = result_copy.get('total_paginas', 0)
                                    if total_paginas_service == 0 or total_paginas_service is None:
                                        # Recalcula dos documentos se necessário
                                        documentos_list = result_copy.get('documentos', [])
                                        total_recalc = 0
                                        for doc in documentos_list:
                                            end_page = doc.get('end_page', 0) or doc.get('num_pages', 0)
                                            if end_page > total_recalc:
                                                total_recalc = end_page
                                        if total_recalc > 0:
                                            result_copy['total_paginas'] = total_recalc
                                            logger.debug(f"[_get_pasta_data] total_paginas recalculado do serviço: {total_recalc}")
                                    
                                    logger.debug(f"[_get_pasta_data] Retornando documentos do serviço com total_paginas={result_copy.get('total_paginas', 0)}")
                                    
                                    # CRÍTICO: Atualiza cache com hash e tamanhos calculados (apenas filesystem)
                                    documents_sizes = _calculate_documents_sizes_adm(cod_documento_int, portal)
                                    _save_cache_to_filesystem_adm(cod_documento_int, result_copy, current_time, current_documents_hash, documents_sizes)
                                    
                                    return result_copy
                                else:
                                    # Documentos prontos não correspondem (quantidade, hash ou tamanhos), não retorna - continua para criar nova task
                                    # Limpa cache de tasks recentes para forçar criação de nova task
                                    _recent_tasks_cache.pop(cod_documento_str, None)
                                    # Limpa cache de documentos (já foi limpo antes, mas garantindo)
                                    _delete_cache_from_filesystem_adm(cod_documento_int)
                                    # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                        except Exception as check_err:
                            logger.warning(f"[_get_pasta_data] Erro ao verificar documentos prontos (sem task recente): {check_err}, continuando para criar nova task")
                    
                    # CRÍTICO: Se não há task recente (acesso inicial OU documentos foram apagados), SEMPRE apaga diretório e cria nova task
                    # Documentos podem ter sido alterados, substituídos ou excluídos no sistema
                    # Não verifica documentos prontos - sempre regenera para garantir dados atualizados
                    if not has_recent_task:
                        try:
                            from openlegis.sagl.browser.processo_adm.processo_adm_utils import secure_path_join
                            dir_hash = hashlib.md5(str(cod_documento_int).encode()).hexdigest()
                            prefix = f"processo_adm_integral_{dir_hash}"
                            install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
                            temp_base = os.path.abspath(os.path.join(install_home, 'var', 'tmp'))
                            dir_base = secure_path_join(temp_base, prefix)
                            
                            # SEMPRE apaga o diretório se existir para forçar regeneração
                            if os.path.exists(dir_base):
                                shutil.rmtree(dir_base, ignore_errors=True)
                            
                            # CRÍTICO: Invalida cache de documentos prontos ao iniciar nova geração (filesystem)
                            _delete_cache_from_filesystem_adm(cod_documento_int)
                        except Exception as cleanup_err:
                            logger.warning(f"[_get_pasta_data] Erro ao apagar diretório (continuando mesmo assim): {cleanup_err}")
                        
                        # SEMPRE inicia nova geração
                        
                        # CRÍTICO: Usa lock por cod_documento para evitar criação simultânea
                        with _locks_lock:
                            if cod_documento_str not in _task_creation_locks:
                                _task_creation_locks[cod_documento_str] = threading.Lock()
                            task_lock = _task_creation_locks[cod_documento_str]
                        
                        # Adquire o lock para este cod_documento
                        with task_lock:
                            # CRÍTICO: Verifica se diretório existe antes do double-check
                            # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                            dir_base_double_check = get_processo_dir_adm(cod_documento_int)
                            if not os.path.exists(dir_base_double_check):
                                # Diretório não existe - documentos foram apagados
                                # Limpa cache de tasks recentes
                                _recent_tasks_cache.pop(cod_documento_str, None)
                                # Limpa cache de documentos (filesystem)
                                _delete_cache_from_filesystem_adm(cod_documento_int)
                                # Continua para criar nova task (não retorna aqui)
                            else:
                                # Diretório existe - verifica novamente após adquirir o lock (double-check)
                                if cod_documento_str in _recent_tasks_cache:
                                    cached_task_id, cache_timestamp = _recent_tasks_cache[cod_documento_str]
                                    if time.time() - cache_timestamp < cache_ttl:
                                        logger.debug(f"[_get_pasta_data] Task foi criada por outra thread enquanto aguardava lock: {cached_task_id}")
                                        # Obtém status detalhado da task para incluir informações de progresso
                                        try:
                                            service_status = ProcessoAdmService(self.context, self.request)
                                            task_status_detail = service_status.verificar_task_status(cached_task_id)
                                            if task_status_detail:
                                                # Inclui informações de progresso se disponíveis
                                                base_response.update({
                                                    'task_id': str(cached_task_id),
                                                    'status': task_status_detail.get('status', 'PENDING'),
                                                    'message': task_status_detail.get('message', 'Tarefa recém-criada, aguardando processamento'),
                                                })
                                                # Adiciona informações de progresso se disponíveis
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
                                            logger.debug(f"[_get_pasta_data] Erro ao obter status detalhado da task: {status_err}")
                                            base_response.update({
                                                'task_id': str(cached_task_id),
                                                'status': 'PENDING',
                                                'message': 'Tarefa recém-criada, aguardando processamento'
                                            })
                                        return base_response
                            
                            # Usa serviço para criar task assíncrona
                            service = ProcessoAdmService(self.context, self.request)
                            result = service.criar_task_async(cod_documento_int, portal_url)
                            
                            if result and isinstance(result, dict) and 'task_id' in result:
                                new_task_id = str(result.get('task_id'))
                                # CRÍTICO: Adiciona ao cache imediatamente para evitar race condition
                                _recent_tasks_cache[cod_documento_str] = (new_task_id, time.time())
                                # Limpa cache antigo (mantém apenas últimos 20)
                                if len(_recent_tasks_cache) > 20:
                                    sorted_items = sorted(_recent_tasks_cache.items(), key=lambda x: x[1][1])
                                    for key, _ in sorted_items[:-20]:
                                        _recent_tasks_cache.pop(key, None)
                                
                                # CRÍTICO: Primeiro verifica status da task para obter informações de progresso
                                # Se task está em PROGRESS, retorna status PROGRESS com informações de progresso
                                try:
                                    service_status = ProcessoAdmService(self.context, self.request)
                                    task_status_detail = service_status.verificar_task_status(new_task_id)
                                    if task_status_detail:
                                        task_real_status = task_status_detail.get('status', 'PENDING')
                                        # Se task está em execução (PENDING, PROGRESS, STARTED), retorna esse status com progresso
                                        if task_real_status in ('PENDING', 'PROGRESS', 'STARTED'):
                                            base_response.update({
                                                'task_id': new_task_id,
                                                'status': task_real_status,
                                                'message': task_status_detail.get('message', 'Regenerando pasta digital...'),
                                                'async': True
                                            })
                                            # Adiciona informações de progresso se disponíveis
                                            if 'current' in task_status_detail:
                                                base_response['current'] = task_status_detail['current']
                                            if 'total' in task_status_detail:
                                                base_response['total'] = task_status_detail['total']
                                            if 'stage' in task_status_detail:
                                                base_response['stage'] = task_status_detail['stage']
                                            return base_response
                                except Exception as status_check_err:
                                    logger.debug(f"[_get_pasta_data] Erro ao verificar status da task: {status_check_err}")
                                
                                # Se task não está em execução (já completou ou erro), verifica documentos
                                # Pequeno delay para dar tempo da task processar se necessário
                                task_creation_time = time.time()
                                time.sleep(0.2)  # Reduzido de 0.5s para 0.2s para permitir progresso aparecer mais cedo
                                
                                # Verifica se há documentos prontos usando serviço
                                try:
                                    check_result = service.get_documentos_prontos(cod_documento, skip_signature_check=True)
                                    
                                    if isinstance(check_result, dict) and 'documentos' in check_result and len(check_result.get('documentos', [])) > 0:
                                        # Documentos prontos encontrados! Mas verifica status real da task primeiro
                                        # CRÍTICO: Verifica status real da task para garantir que não retornamos SUCCESS prematuramente
                                        try:
                                            service_status = ProcessoAdmService(self.context, self.request)
                                            task_status_detail = service_status.verificar_task_status(new_task_id)
                                            if task_status_detail:
                                                task_real_status = task_status_detail.get('status', 'PENDING')
                                                # Se task ainda está em execução (PENDING, PROGRESS, STARTED), retorna esse status
                                                if task_real_status in ('PENDING', 'PROGRESS', 'STARTED'):
                                                    result_copy = copy.deepcopy(check_result)
                                                    result_copy['async'] = True
                                                    result_copy['task_id'] = new_task_id
                                                    result_copy['status'] = task_real_status
                                                    result_copy['message'] = task_status_detail.get('message', 'Processando pasta digital...')
                                                    # Adiciona informações de progresso se disponíveis
                                                    if 'current' in task_status_detail:
                                                        result_copy['current'] = task_status_detail['current']
                                                    if 'total' in task_status_detail:
                                                        result_copy['total'] = task_status_detail['total']
                                                    if 'stage' in task_status_detail:
                                                        result_copy['stage'] = task_status_detail['stage']
                                                    if 'total_paginas' in result_copy:
                                                        result_copy['total_paginas'] = result_copy['total_paginas']
                                                    if 'cod_documento' not in result_copy:
                                                        result_copy['cod_documento'] = cod_documento_int
                                                    return result_copy
                                                # Se task realmente completou (SUCCESS), retorna SUCCESS
                                                elif task_real_status == 'SUCCESS':
                                                    result_copy = copy.deepcopy(check_result)
                                                    result_copy['async'] = True
                                                    result_copy['task_id'] = new_task_id
                                                    result_copy['status'] = 'SUCCESS'
                                                    result_copy['message'] = 'Pasta digital gerada com sucesso'
                                                    if 'total_paginas' in result_copy:
                                                        result_copy['total_paginas'] = result_copy['total_paginas']
                                                    if 'cod_documento' not in result_copy:
                                                        result_copy['cod_documento'] = cod_documento_int
                                                    documents_hash = _calculate_documents_hash_adm(cod_documento_int, portal)
                                                    documents_sizes = _calculate_documents_sizes_adm(cod_documento_int, portal)
                                                    _save_cache_to_filesystem_adm(cod_documento_int, result_copy, time.time(), documents_hash, documents_sizes)
                                                    return result_copy
                                        except Exception as status_check_err:
                                            logger.debug(f"[_get_pasta_data] Erro ao verificar status real da task: {status_check_err}")
                                            # Em caso de erro, assume que task completou (comportamento anterior)
                                        
                                        # Fallback: Se não conseguiu verificar status, retorna SUCCESS (comportamento anterior)
                                        result_copy = copy.deepcopy(check_result)
                                        result_copy['async'] = True
                                        result_copy['task_id'] = new_task_id
                                        result_copy['status'] = 'SUCCESS'
                                        result_copy['message'] = 'Pasta digital gerada com sucesso'
                                        if 'total_paginas' in result_copy:
                                            result_copy['total_paginas'] = result_copy['total_paginas']
                                        if 'cod_documento' not in result_copy:
                                            result_copy['cod_documento'] = cod_documento_int
                                        documents_hash = _calculate_documents_hash_adm(cod_documento_int, portal)
                                        documents_sizes = _calculate_documents_sizes_adm(cod_documento_int, portal)
                                        _save_cache_to_filesystem_adm(cod_documento_int, result_copy.get('documentos', []), time.time(), documents_hash, documents_sizes)
                                        return result_copy
                                except Exception as check_err:
                                    logger.warning(f"[_get_pasta_data] Erro ao verificar documentos prontos após criar task: {check_err}", exc_info=True)
                                
                                # Se não encontrou documentos prontos, retorna status PENDING com monitor ativo
                                # Obtém status detalhado da task para incluir informações de progresso
                                try:
                                    service_status = ProcessoAdmService(self.context, self.request)
                                    task_status_detail = service_status.verificar_task_status(new_task_id)
                                    if task_status_detail:
                                        # Inclui informações de progresso se disponíveis
                                        base_response.update({
                                            'task_id': new_task_id,
                                            'status': task_status_detail.get('status', result.get('status', 'PENDING')),
                                            'message': task_status_detail.get('message', result.get('message', 'Regenerando pasta digital...')),
                                            'async': True  # Garante que async está True para mostrar monitor
                                        })
                                        # Adiciona informações de progresso se disponíveis
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
                                            'async': True  # Garante que async está True para mostrar monitor
                                        })
                                except Exception as status_err:
                                    logger.debug(f"[_get_pasta_data] Erro ao obter status detalhado da task: {status_err}")
                                    base_response.update({
                                        'task_id': new_task_id,
                                        'status': str(result.get('status', 'PENDING')),
                                        'message': result.get('message', 'Regenerando pasta digital...'),
                                        'async': True  # Garante que async está True para mostrar monitor
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
            return base_response
            
        except Exception as e:
            logger.error(f"[_get_pasta_data] Erro geral: {e}", exc_info=True)
            return {
                'async': True,
                'error': str(e),
                'documentos': [],
                'cod_documento': cod_documento,
                'total_paginas': 0,
                'message': 'Erro ao processar pasta digital'
            }
    
    def _get_materias_vinculadas(self, cod_documento, portal):
        """
        Obtém matérias vinculadas ao documento administrativo.
        
        Retorna no formato esperado pelo frontend com anexadas e anexadoras.
        Nota: No processo_adm, não há distinção entre anexadas e anexadoras como no processo_leg,
        então todas as matérias vinculadas são tratadas como vinculadas (colocadas em 'anexadas').
        """
        try:
            vinculadas = {
                'anexadas': [],
                'anexadoras': [],
                'tem_vinculadas': False
            }
            
            # SQLAlchemy
            try:
                session = Session()
                try:
                    # Matérias vinculadas ao documento administrativo
                    from openlegis.sagl.models.models import MateriaLegislativa, TipoMateriaLegislativa
                    materias_vinculadas = session.query(DocumentoAdministrativoMateria, MateriaLegislativa, TipoMateriaLegislativa)\
                        .join(MateriaLegislativa, DocumentoAdministrativoMateria.cod_materia == MateriaLegislativa.cod_materia)\
                        .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                        .filter(DocumentoAdministrativoMateria.cod_documento == cod_documento)\
                        .filter(DocumentoAdministrativoMateria.ind_excluido == 0)\
                        .filter(MateriaLegislativa.ind_excluido == 0)\
                        .all()
                    
                    for vinculada_obj, materia_obj, tipo_obj in materias_vinculadas:
                        materia_info = {
                            'cod_materia': vinculada_obj.cod_materia,
                            'sgl_tipo_materia': tipo_obj.sgl_tipo_materia or '',
                            'num_ident_basica': materia_obj.num_ident_basica or '',
                            'ano_ident_basica': materia_obj.ano_ident_basica or '',
                            'titulo': f"{tipo_obj.sgl_tipo_materia}-{materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica}"
                        }
                        # No processo_adm, não há distinção entre anexadas e anexadoras,
                        # então todas as matérias vinculadas são colocadas em 'anexadas'
                        vinculadas['anexadas'].append(materia_info)
                finally:
                    session.close()
            except Exception as e:
                logger.error(f"Erro ao obter matérias vinculadas (SQLAlchemy): {e}")
            
            vinculadas['tem_vinculadas'] = len(vinculadas['anexadas']) > 0 or len(vinculadas['anexadoras']) > 0
            return vinculadas
        except Exception as e:
            logger.error(f"Erro ao obter matérias vinculadas: {e}")
            return {
                'anexadas': [],
                'anexadoras': [],
                'tem_vinculadas': False
            }
    
    def _get_documentos_administrativos_vinculados(self, cod_documento, portal):
        """
        Obtém documentos administrativos vinculados ao documento administrativo atual.
        
        Usa o modelo DocumentoAdministrativoVinculado para buscar documentos vinculados:
        - Documentos onde cod_documento_vinculante = cod_documento (documentos que este vinculou)
        - Documentos onde cod_documento_vinculado = cod_documento (documentos que vincularam este)
        
        Retorna lista de documentos administrativos vinculados com informações para links
        para pasta digital, similar ao que ocorre com normas_vinculadas no processo_leg.
        """
        try:
            documentos_vinculados = []
            cod_docs_coletados = set()  # Para evitar duplicatas
            
            # SQLAlchemy
            try:
                session = Session()
                try:
                    # Busca documentos vinculados usando o modelo DocumentoAdministrativoVinculado
                    # 1. Documentos onde este documento é o vinculante (cod_documento_vinculante)
                    #    ou seja, busca documentos vinculados que este documento vinculou
                    docs_como_vinculante = session.query(
                        DocumentoAdministrativoVinculado.cod_documento_vinculado,
                        DocumentoAdministrativo,
                        TipoDocumentoAdministrativo
                    )\
                        .join(DocumentoAdministrativo,
                              DocumentoAdministrativoVinculado.cod_documento_vinculado == DocumentoAdministrativo.cod_documento)\
                        .join(TipoDocumentoAdministrativo,
                              DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
                        .filter(DocumentoAdministrativoVinculado.cod_documento_vinculante == cod_documento)\
                        .filter(DocumentoAdministrativoVinculado.ind_excluido == 0)\
                        .filter(DocumentoAdministrativo.ind_excluido == 0)\
                        .all()
                    
                    # 2. Documentos onde este documento é o vinculado (cod_documento_vinculado)
                    #    ou seja, busca documentos vinculantes que vincularam este documento
                    docs_como_vinculado = session.query(
                        DocumentoAdministrativoVinculado.cod_documento_vinculante,
                        DocumentoAdministrativo,
                        TipoDocumentoAdministrativo
                    )\
                        .join(DocumentoAdministrativo,
                              DocumentoAdministrativoVinculado.cod_documento_vinculante == DocumentoAdministrativo.cod_documento)\
                        .join(TipoDocumentoAdministrativo,
                              DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
                        .filter(DocumentoAdministrativoVinculado.cod_documento_vinculado == cod_documento)\
                        .filter(DocumentoAdministrativoVinculado.ind_excluido == 0)\
                        .filter(DocumentoAdministrativo.ind_excluido == 0)\
                        .all()
                    
                    # Processa documentos onde este é vinculante
                    for cod_doc_vinculado, doc_adm_obj, tipo_doc_obj in docs_como_vinculante:
                        if cod_doc_vinculado not in cod_docs_coletados:
                            cod_docs_coletados.add(cod_doc_vinculado)
                            documentos_vinculados.append({
                                'cod_documento': doc_adm_obj.cod_documento,
                                'sgl_tipo_documento': tipo_doc_obj.sgl_tipo_documento or '',
                                'num_documento': doc_adm_obj.num_documento or '',
                                'ano_documento': doc_adm_obj.ano_documento or '',
                                'titulo': f"{tipo_doc_obj.sgl_tipo_documento} {doc_adm_obj.num_documento}/{doc_adm_obj.ano_documento}"
                            })
                    
                    # Processa documentos onde este é vinculado
                    for cod_doc_vinculante, doc_adm_obj, tipo_doc_obj in docs_como_vinculado:
                        if cod_doc_vinculante not in cod_docs_coletados:
                            cod_docs_coletados.add(cod_doc_vinculante)
                            documentos_vinculados.append({
                                'cod_documento': doc_adm_obj.cod_documento,
                                'sgl_tipo_documento': tipo_doc_obj.sgl_tipo_documento or '',
                                'num_documento': doc_adm_obj.num_documento or '',
                                'ano_documento': doc_adm_obj.ano_documento or '',
                                'titulo': f"{tipo_doc_obj.sgl_tipo_documento} {doc_adm_obj.num_documento}/{doc_adm_obj.ano_documento}"
                            })
                finally:
                    session.close()
            except Exception as e:
                logger.error(f"Erro ao obter documentos administrativos vinculados (SQLAlchemy): {e}")
            
            return documentos_vinculados
        except Exception as e:
            logger.error(f"Erro ao obter documentos administrativos vinculados: {e}")
            return []
    
    def _get_portal_config(self, portal):
        """Obtém configurações do portal"""
        try:
            # Tenta obter configurações básicas do portal
            config = {
                'id_logo': 'logo_casa.gif',  # Padrão
                'nome_casa': 'Casa Legislativa',  # Padrão
            }
            
            # Tenta obter do portal_sagl se disponível
            try:
                tool = getToolByName(self.context, 'portal_sagl')
                if hasattr(tool, 'get_properties'):
                    props = tool.get_properties()
                    if props:
                        if 'id_logo' in props:
                            config['id_logo'] = props['id_logo']
                        if 'nome_casa' in props:
                            config['nome_casa'] = props['nome_casa']
            except:
                pass
            
            return config
        except Exception as e:
            logger.debug(f"[_get_portal_config] Erro ao obter config: {e}")
            return {}
    
    def _render_html(self, cod_documento, action, documento, pasta, portal_config, materias_vinculadas, documentos_administrativos_vinculados, portal_url):
        """Renderiza o HTML completo da pasta digital"""
        # Garante que cod_documento e portal_url são strings válidas
        cod_documento_str = str(cod_documento).strip() if cod_documento else ''
        portal_url_str = str(portal_url).strip() if portal_url else ''
        
        # GARANTIA ABSOLUTA: pasta nunca é None/null e sempre tem estrutura válida
        if pasta is None:
            logger.warning(f"[_render_html] pasta is None, FORÇANDO estrutura padrão")
            pasta = {
                'async': True,
                'task_id': None,
                'status': 'PENDING',
                'documentos': [],
                'total_paginas': 0,
                'message': 'Iniciando geração...'
            }
        elif not isinstance(pasta, dict):
            logger.warning(f"[_render_html] pasta não é dict ({type(pasta)}), convertendo para dict padrão")
            pasta = {
                'async': True,
                'task_id': None,
                'status': 'PENDING',
                'documentos': [],
                'total_paginas': 0,
                'message': 'Iniciando geração...'
            }
        elif len(pasta) == 0:
            # Se pasta é um dict vazio, adiciona estrutura padrão
            logger.debug(f"[_render_html] pasta está vazio, adicionando estrutura padrão")
            pasta = {
                'async': True,
                'task_id': None,
                'status': 'PENDING',
                'documentos': [],
                'total_paginas': 0,
                'message': 'Iniciando geração...'
            }
        else:
            # Garante que pasta tem as propriedades mínimas necessárias
            if 'async' not in pasta:
                pasta['async'] = True
            if 'documentos' not in pasta:
                pasta['documentos'] = []
            if 'total_paginas' not in pasta:
                pasta['total_paginas'] = 0
            if 'status' not in pasta:
                pasta['status'] = 'PENDING'
        
        # Garante que todos os valores None sejam convertidos para valores válidos
        data_dict = {
            'cod_documento': cod_documento_str,
            'action': str(action) if action else 'pasta',
            'documento': documento if documento is not None else {},
            'pasta': pasta,  # Já garantido que é um dict válido
            'portal_config': portal_config if portal_config is not None else {},
            'materias_vinculadas': materias_vinculadas if materias_vinculadas is not None else {'anexadas': [], 'anexadoras': [], 'tem_vinculadas': False},
            'documentos_administrativos': documentos_administrativos_vinculados if documentos_administrativos_vinculados is not None else [],
            'portal_url': portal_url_str
        }
        
        # Serializa o JSON com encoder customizado para objetos date/datetime
        # IMPORTANTE: Usa separators para garantir JSON compacto (sem espaços extras)
        # Isso evita problemas com formatação no JavaScript
        try:
            data_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
            # Valida que o JSON é válido
            json.loads(data_json)
            # Remove qualquer quebra de linha acidental
            data_json = data_json.replace('\n', ' ').replace('\r', ' ')
        except (TypeError, ValueError) as e:
            logger.error(f"[_render_html] Erro ao serializar JSON: {e}")
            # Fallback: converte None para null explicitamente
            def default_serializer(obj):
                if obj is None:
                    return None
                if isinstance(obj, (date, datetime)):
                    if isinstance(obj, datetime):
                        return obj.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        return obj.strftime('%Y-%m-%d')
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            data_json = json.dumps(data_dict, ensure_ascii=False, default=default_serializer, separators=(',', ':'))
            # Remove quebras de linha
            data_json = data_json.replace('\n', ' ').replace('\r', ' ')
        
        # VALIDAÇÃO CRÍTICA ANTES DE INJETAR (logs reduzidos)
        logger.debug(f"[_render_html] JSON serializado: {len(data_json)} caracteres")
        
        # Verifica múltiplas formas de "pasta":null
        pasta_null_variations = [
            '"pasta":null',
            '"pasta": null', 
            '"pasta":null',
            '"pasta": null',
            "'pasta':null",
            "'pasta': null"
        ]
        
        pasta_found_as_null = any(variation in data_json for variation in pasta_null_variations)
        
        # Verifica se pasta é um objeto (inclui espaço DEPOIS dos dois pontos)
        pasta_is_object = (
            '"pasta":{' in data_json or 
            '"pasta" :{' in data_json or
            '"pasta": {' in data_json or  # CORREÇÃO: espaço DEPOIS dos dois pontos
            '"pasta" : {' in data_json or  # CORREÇÃO: espaços antes e depois dos dois pontos
            "'pasta':{" in data_json or
            'pasta:{' in data_json or
            # Verifica se tem "pasta" e não é null (indicando que é um objeto)
            ('"pasta"' in data_json and not pasta_found_as_null)
        )
        
        if pasta_found_as_null:
            logger.error(f"[_render_html] ENCONTRADO pasta:null no JSON!")
            logger.error(f"[_render_html] Forçando pasta para dict vazio")
            
            # Loga contexto para debug
            pasta_index = data_json.find('"pasta"')
            if pasta_index >= 0:
                context_start = max(0, pasta_index - 50)
                context_end = min(len(data_json), pasta_index + 100)
                logger.error(f"[_render_html] Contexto de 'pasta' no JSON: ...{data_json[context_start:context_end]}...")
            
            # Força substituição em TODAS as variações possíveis
            original_json = data_json
            for variation in pasta_null_variations:
                if variation in data_json:
                    logger.error(f"[_render_html] Substituindo {variation} por {variation.split(':')[0]}:{{}}")
                    replacement = variation.split(':')[0] + ':{}'
                    data_json = data_json.replace(variation, replacement)
            
            # Se após substituições ainda tem pasta:null, força reconstrução
            if any(variation in data_json for variation in pasta_null_variations):
                logger.error(f"[_render_html] pasta:null persiste após substituições, RECONSTRUINDO...")
                data_dict['pasta'] = {}
                data_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                data_json = data_json.replace('\n', ' ').replace('\r', ' ')
            
            # Validação pós-correção (inclui espaço DEPOIS dos dois pontos)
            if any(variation in data_json for variation in pasta_null_variations):
                logger.error(f"[_render_html] pasta:null AINDA persiste após reconstrução! Forçando substituição direta...")
                for variation in pasta_null_variations:
                    data_json = data_json.replace(variation, variation.split(':')[0] + ':{}')
                # Valida JSON após correção
                try:
                    json.loads(data_json)
                except json.JSONDecodeError:
                    logger.error(f"[_render_html] JSON inválido após correção de pasta:null")
                    data_dict['pasta'] = {}
                    data_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                    data_json = data_json.replace('\n', ' ').replace('\r', ' ')
        
        # Validação final do JSON antes de injetar
        try:
            json.loads(data_json)
        except json.JSONDecodeError as e:
            logger.error(f"[_render_html] JSON inválido antes de injetar: {e}")
            # Último recurso: reconstroi com pasta vazio
            data_dict['pasta'] = {}
            data_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
            data_json = data_json.replace('\n', ' ').replace('\r', ' ')
        
        # Lê o template HTML e injeta os dados
        # CRÍTICO: Usa index_html.html (template completo/atualizado)
        # O template está em src/openlegis.sagl/openlegis/sagl/skins/consultas/documento_administrativo/pasta_digital/index_html.html
        import pkg_resources
        try:
            # Tenta obter o caminho do pacote
            dist = pkg_resources.get_distribution('openlegis.sagl')
            # CRÍTICO: Usa index_html.html como template principal
            template_path = os.path.join(
                dist.location, 'openlegis', 'sagl', 'skins', 'consultas', 'documento_administrativo',
                'pasta_digital', 'index_html.html'
            )
            
            # Se não encontrar, tenta caminho relativo
            if not os.path.exists(template_path):
                template_path = os.path.join(
                    os.path.dirname(__file__),
                    '..', '..', 'skins', 'consultas', 'documento_administrativo',
                    'pasta_digital', 'index_html.html'
                )
            
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
            
            # Preenche os links vazios de favicon e CSS
            if portal_url_str:
                # Favicon
                favicon_filename = portal_config.get('id_logo', 'logo_casa.gif')
                favicon_url = f"{portal_url_str}/sapl_documentos/props_sagl/{favicon_filename}"
                
                html = html.replace('<link rel="shortcut icon" type="image/x-icon" href="" id="favicon">', 
                                  f'<link rel="shortcut icon" type="image/x-icon" href="{favicon_url}" id="favicon">')
                
                # CSS
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
            
            # Injeta dados JSON no template - abordagem simplificada e robusta
            # Procura pelo padrão exato do template: "let APP_DATA = {"
            app_data_start = html.find('let APP_DATA = {')
            
            if app_data_start == -1:
                # Tenta outros padrões
                app_data_start = html.find('var APP_DATA = {')
                if app_data_start == -1:
                    app_data_start = html.find('const APP_DATA = {')
                    if app_data_start == -1:
                        app_data_start = html.find('let APP_DATA={')
            
            if app_data_start != -1:
                # Encontra o fechamento }; correspondente
                # Começa após "let APP_DATA = {" (ou variante)
                search_pos = app_data_start + html[app_data_start:].find('{') + 1
                brace_count = 1
                in_string = False
                escape_next = False
                string_char = None
                end_pos = -1
                
                for i in range(search_pos, len(html)):
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
                        brace_count -= 1
                        if brace_count == 0:
                            # Encontrou o fechamento - procura pelo ;
                            end_pos = i + 1
                            # Pula espaços em branco
                            while end_pos < len(html) and html[end_pos] in ' \n\t\r':
                                end_pos += 1
                            # Procura pelo ponto e vírgula
                            if end_pos < len(html) and html[end_pos] == ';':
                                end_pos += 1
                                # Pula possíveis espaços após o ;
                                while end_pos < len(html) and html[end_pos] in ' \n\t\r':
                                    end_pos += 1
                                # Pula possíveis comentários após o ; (// ...)
                                if end_pos < len(html) - 1 and html[end_pos:end_pos+2] == '//':
                                    # Pula até o fim da linha
                                    while end_pos < len(html) and html[end_pos] != '\n':
                                        end_pos += 1
                                    # Pula o \n se existir
                                    if end_pos < len(html) and html[end_pos] == '\n':
                                        end_pos += 1
                            break
                
                if end_pos > app_data_start:
                    # Valida JSON antes de injetar
                    try:
                        json.loads(data_json)
                        safe_json = data_json
                    except json.JSONDecodeError as e:
                        logger.error(f"[_render_html] JSON inválido: {e}")
                        # Força pasta vazio
                        data_dict['pasta'] = {}
                        safe_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                        safe_json = safe_json.replace('\n', ' ').replace('\r', ' ')
                    
                    # Validação adicional: garante que o JSON não contém caracteres problemáticos
                    # Escapa possíveis problemas com caracteres especiais
                    try:
                        # Testa se o JSON é válido e pode ser parseado
                        test_dict = json.loads(safe_json)
                        # Re-serializa para garantir formatação consistente (usa separators para JSON compacto)
                        safe_json_final = json.dumps(test_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                        # Remove quebras de linha e caracteres problemáticos
                        safe_json_final = safe_json_final.replace('\n', ' ').replace('\r', ' ')
                        # Valida novamente após limpeza
                        json.loads(safe_json_final)
                    except Exception as e:
                        logger.error(f"[_render_html] Erro ao validar JSON final: {e}")
                        # Último recurso: pasta vazio
                        data_dict['pasta'] = {}
                        safe_json_final = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                        safe_json_final = safe_json_final.replace('\n', ' ').replace('\r', ' ')
                    
                    # Substitui todo o bloco: desde "let APP_DATA = {" até "};"
                    # IMPORTANTE: Garante que não há quebras de linha ou caracteres problemáticos
                    # CRÍTICO: Valida que o JSON é válido antes de injetar e sanitiza para JavaScript
                    try:
                        # Sanitiza o JSON para uso seguro em JavaScript
                        safe_js_json = safe_json_for_javascript(safe_json_final)
                        
                        # Valida sintaxe básica: deve começar e terminar com chaves balanceadas
                        if not safe_js_json.strip().startswith('{') or not safe_js_json.strip().endswith('}'):
                            raise ValueError("JSON não está entre chaves")
                        # Valida que é JSON válido após sanitização
                        json.loads(safe_js_json)
                        
                        # Cria a substituição com JSON sanitizado
                        replacement = f'let APP_DATA = {safe_js_json}; // Dados injetados pelo servidor'
                        html = html[:app_data_start] + replacement + html[end_pos:]
                        logger.debug(f"[_render_html] APP_DATA injetado (posição {app_data_start} até {end_pos}, JSON size: {len(safe_js_json)})")
                    except (ValueError, json.JSONDecodeError, TypeError) as e:
                        logger.error(f"[_render_html] Erro ao validar JSON antes de injetar: {e}")
                        # Último recurso: usa JSON vazio mas válido e sanitizado
                        fallback_json = json.dumps({'cod_documento': str(cod_documento), 'pasta': {}, 'documento': {}, 'portal_url': portal_url_str or ''}, ensure_ascii=False, separators=(',', ':'))
                        fallback_json = safe_json_for_javascript(fallback_json)
                        replacement = f'let APP_DATA = {fallback_json}; // Dados injetados pelo servidor (fallback)'
                        html = html[:app_data_start] + replacement + html[end_pos:]
                        logger.warning(f"[_render_html] Usando JSON fallback devido a erro de validação")
                else:
                    logger.warning(f"[_render_html] Não foi possível encontrar fechamento de APP_DATA (end_pos={end_pos})")
                    # Fallback: substitui desde "let APP_DATA = {" até o próximo "};"
                    # Procura por múltiplos padrões para encontrar o fechamento correto
                    if search_pos < len(html):
                        # Valida JSON antes de usar e sanitiza
                        try:
                            json.loads(data_json)
                            safe_json_fallback = safe_json_for_javascript(data_json)
                        except:
                            data_dict['pasta'] = {}
                            safe_json_fallback = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                            safe_json_fallback = safe_json_for_javascript(safe_json_fallback)
                        
                        # Procura pelo fechamento "};" próximo, mas verifica que é do APP_DATA
                        # Limita a busca a um intervalo razoável (não muito longe)
                        max_search = min(search_pos + 5000, len(html))
                        closing = html.find('};', search_pos, max_search)
                        
                        if closing > search_pos:
                            # Verifica que o fechamento faz sentido (não está no meio de uma string)
                            # Conta quantas chaves abrem e fecham entre search_pos e closing
                            test_html = html[app_data_start:closing+2]
                            brace_test = test_html.count('{') - test_html.count('}')
                            if brace_test >= 0:  # Mais ou igual chaves de abertura que fechamento
                                # Substitui desde app_data_start (começo do "let APP_DATA") até após o "};"
                                replacement_fallback = f'let APP_DATA = {safe_json_fallback}; // Dados injetados pelo servidor'
                                # Pula o ; se já estiver no fechamento encontrado
                                if closing + 2 < len(html) and html[closing+2] == '\n':
                                    html = html[:app_data_start] + replacement_fallback + '\n' + html[closing+3:]
                                else:
                                    html = html[:app_data_start] + replacement_fallback + html[closing+2:]
                                logger.debug(f"[_render_html] APP_DATA injetado usando fallback (posição {app_data_start} até {closing+2})")
                            else:
                                logger.error(f"[_render_html] Fechamento encontrado mas estrutura de chaves não confere (brace_test={brace_test})")
                        else:
                            logger.error(f"[_render_html] Não foi possível encontrar fechamento '}};' próximo (search_pos={search_pos}, max_search={max_search})")
            else:
                logger.warning("[_render_html] Padrão APP_DATA não encontrado no template")
                # Fallback: injeta no primeiro script
                script_start = html.find('<script>')
                if script_start != -1:
                    # Valida JSON antes de injetar e sanitiza
                    try:
                        json.loads(data_json)
                        safe_injection_json = safe_json_for_javascript(data_json)
                    except:
                        data_dict['pasta'] = {}
                        safe_injection_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                        safe_injection_json = safe_json_for_javascript(safe_injection_json)
                    injection = f'let APP_DATA = {safe_injection_json}; // Dados injetados pelo servidor\n        '
                    html = html[:script_start + 8] + injection + html[script_start + 8:]
                    
            
            # VALIDAÇÃO FINAL ABSOLUTA (logs reduzidos)
            # Verifica se há pasta:null no HTML final
            for variation in pasta_null_variations[:4]:  # Apenas variações com aspas duplas
                if variation in html:
                    logger.error(f"[_render_html] ERRO CRÍTICO: pasta:null ainda presente no HTML final após injeção!")
                    replacement = variation.split(':')[0] + ':{}'
                    html = html.replace(variation, replacement)
            
            # Validação final: verifica se há JSON mal formado no HTML e caracteres problemáticos
            # Procura de forma mais robusta pelo padrão APP_DATA
            app_data_patterns = ['let APP_DATA = {', 'var APP_DATA = {', 'const APP_DATA = {', 'let APP_DATA={']
            app_data_pattern = -1
            for pattern in app_data_patterns:
                app_data_pattern = html.find(pattern)
                if app_data_pattern >= 0:
                    break
            
            if app_data_pattern >= 0:
                # Extrai o JSON para validação usando contagem de chaves (mais robusto)
                json_start = app_data_pattern + html[app_data_pattern:].find('{')
                # Começa com 1 porque já estamos na chave de abertura
                brace_count = 1
                in_string = False
                escape_next = False
                string_char = None
                json_end = -1
                
                # Conta chaves para encontrar o fechamento correto
                # Começa do próximo caractere após a chave de abertura
                for i in range(json_start + 1, len(html)):
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
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            # Procura pelo ponto e vírgula após o }
                            while json_end < len(html) and html[json_end] in ' \n\t\r':
                                json_end += 1
                            if json_end < len(html) and html[json_end] == ';':
                                json_end += 1
                            break
                
                if json_end > json_start and json_end <= len(html):
                    json_str = html[json_start:json_end].rstrip(';').strip()
                    try:
                        # Valida que é JSON válido
                        parsed = json.loads(json_str)
                        # Re-serializa para garantir formatação consistente
                        fixed_json = json.dumps(parsed, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                        fixed_json = safe_json_for_javascript(fixed_json)
                        # Valida novamente após sanitização
                        json.loads(fixed_json)
                        
                        # Se mudou, substitui
                        if fixed_json != json_str:
                            logger.debug(f"[_render_html] JSON corrigido durante validação final (tamanho: {len(json_str)} -> {len(fixed_json)})")
                            # Substitui mantendo a estrutura let APP_DATA = {...};
                            html = html[:json_start] + fixed_json + html[json_end:]
                    except json.JSONDecodeError as e:
                        logger.error(f"[_render_html] ERRO CRÍTICO: JSON inválido no HTML final: {e}")
                        logger.error(f"[_render_html] JSON problemático (primeiros 800 chars): {json_str[:800] if len(json_str) > 800 else json_str}")
                        logger.error(f"[_render_html] Posição do erro: char {e.pos if hasattr(e, 'pos') else 'unknown'}")
                        # Tenta corrigir reconstruindo com pasta vazio e sanitiza
                        data_dict['pasta'] = {}
                        data_json_final = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder, separators=(',', ':'))
                        data_json_final = safe_json_for_javascript(data_json_final)
                        html = html[:json_start] + data_json_final + html[json_end:]
                else:
                    logger.warning(f"[_render_html] Não foi possível extrair JSON completo para validação (start={json_start}, end={json_end})")
            
            return html
            
        except FileNotFoundError:
            logger.error(f"[_render_html] Template não encontrado: {template_path}")
            return self._render_error(f"Template não encontrado: {template_path}")
        except Exception as e:
            logger.error(f"[_render_html] Erro ao carregar template: {e}", exc_info=True)
            return self._render_error(f"Erro ao carregar template: {str(e)}")


class PastaDigitalAdmDataView(grok.View):
    """View que retorna dados JSON da pasta digital"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pasta_digital_adm_data')
    
    def update(self):
        """Método update do Grok - garante que headers sejam definidos"""
        # Define headers ANTES de qualquer processamento
        self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
        # Evita cache para garantir que sempre use a versão mais recente
        self.request.RESPONSE.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.request.RESPONSE.setHeader('Pragma', 'no-cache')
        self.request.RESPONSE.setHeader('Expires', '0')
    
    def __call__(self):
        """Intercepta a chamada para retornar JSON diretamente"""
        # Chama update primeiro para definir headers
        self.update()
        
        # Chama render para obter o JSON
        json_result = self.render()
        
        # Garante que seja uma string
        if not isinstance(json_result, str):
            json_result = str(json_result)
        
        # Define Content-Type antes de escrever (garantia extra)
        self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
        
        # Usa setBody() para garantir que o JSON seja retornado corretamente
        json_bytes = json_result.encode('utf-8')
        self.request.RESPONSE.setBody(json_bytes)
        
        # Retorna string vazia para evitar processamento adicional do Grok
        return ''
    
    def render(self):
        """Retorna dados JSON da pasta digital"""
        try:
            # Obtém cod_documento de form ou query string
            cod_documento = self.request.form.get('cod_documento') or self.request.get('cod_documento')
            if not cod_documento:
                self.request.RESPONSE.setStatus(400)
                return json.dumps({'success': False, 'error': 'cod_documento não fornecido'})
            
            try:
                cod_documento = int(cod_documento)
            except (ValueError, TypeError):
                self.request.RESPONSE.setStatus(400)
                return json.dumps({'success': False, 'error': 'cod_documento inválido'})
            
            # Verifica permissão
            # Tenta múltiplas formas de obter o usuário autenticado (compatibilidade Zope)
            user = None
            try:
                user = self.request.get('AUTHENTICATED_USER')
            except (AttributeError, KeyError):
                pass
            
            if not user:
                try:
                    from AccessControl import getSecurityManager
                    security_manager = getSecurityManager()
                    user = security_manager.getUser()
                    if user and hasattr(user, 'getId') and not user.getId():
                        user = None
                except (ImportError, AttributeError):
                    pass
            
            if not user:
                self.request.RESPONSE.setStatus(401)
                return json.dumps({'success': False, 'error': 'Usuário não autenticado'})
            
            can_view, motivo = verificar_permissao_acesso(self.context, cod_documento, user)
            
            if not can_view:
                registrar_acesso_documento(cod_documento, user, False, motivo)
                self.request.RESPONSE.setStatus(403)
                return json.dumps({'success': False, 'error': 'Acesso não autorizado'})
            
            registrar_acesso_documento(cod_documento, user, True, motivo)
            
            # Obtém dados usando o serviço
            service = ProcessoAdmService(self.context, self.request)
            result = service.get_documentos_prontos(cod_documento, skip_signature_check=False)
            
            # Garante que result seja um dicionário válido
            if result is None:
                result = {'documentos': [], 'total_paginas': 0, 'cod_documento': cod_documento}
            elif not isinstance(result, dict):
                logger.warning(f"[PastaDigitalAdmDataView] Result não é dict: {type(result)}")
                result = {'documentos': [], 'total_paginas': 0, 'cod_documento': cod_documento, 'error': 'Formato de resposta inválido'}
            
            # Garante que tem a estrutura mínima esperada
            if 'documentos' not in result:
                result['documentos'] = []
            if 'cod_documento' not in result:
                result['cod_documento'] = cod_documento
            
            # CRÍTICO: Preserva total_paginas do resultado original (não substitui se já existe)
            # Se não existe, inicializa como 0 (será recalculado depois se necessário)
            if 'total_paginas' not in result:
                result['total_paginas'] = 0
            
            # Adiciona informações do documento
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            session = Session()
            try:
                documento = session.query(DocumentoAdministrativo, TipoDocumentoAdministrativo)\
                    .join(TipoDocumentoAdministrativo, 
                          DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
                    .filter(DocumentoAdministrativo.cod_documento == cod_documento)\
                    .filter(DocumentoAdministrativo.ind_excluido == 0)\
                    .first()
                
                if documento:
                    doc_obj, tipo_obj = documento
                    result['titulo'] = f"{tipo_obj.sgl_tipo_documento} {doc_obj.num_documento}/{doc_obj.ano_documento}"
                    result['cod_documento'] = cod_documento
            except Exception as e:
                logger.warning(f"[PastaDigitalAdmDataView] Erro ao obter dados do documento: {e}")
            finally:
                session.close()
            
            # Obtém matérias vinculadas
            # Usa função standalone ou cria instância temporária
            try:
                pasta_view = PastaDigitalAdmView(self.context, self.request)
                materias_vinculadas = pasta_view._get_materias_vinculadas(cod_documento, portal)
                result['materias_vinculadas'] = materias_vinculadas
                
                documentos_administrativos_vinculados = pasta_view._get_documentos_administrativos_vinculados(cod_documento, portal)
                result['documentos_administrativos'] = documentos_administrativos_vinculados
            except Exception as e:
                logger.warning(f"[PastaDigitalAdmDataView] Erro ao obter matérias vinculadas/documentos vinculados: {e}")
                result['materias_vinculadas'] = {'anexadas': [], 'anexadoras': [], 'tem_vinculadas': False}
                result['documentos_administrativos'] = []
            
            # CRÍTICO: Usa total_paginas do resultado original (já vem calculado corretamente do serviço)
            total_paginas_result = result.get('total_paginas', 0)
            documentos_list = result.get('documentos', [])
            
            # Se total_paginas é 0 mas há documentos, tenta recalcular (fallback)
            if total_paginas_result == 0 and len(documentos_list) > 0:
                # PRIORIDADE 1: Tenta contar páginas reais no diretório
                try:
                    from openlegis.sagl.browser.processo_adm.processo_adm_utils import get_processo_dir_adm
                    dir_base = get_processo_dir_adm(cod_documento)
                    dir_paginas = os.path.join(dir_base, 'pages')
                    if os.path.exists(dir_paginas) and os.path.isdir(dir_paginas):
                        pagina_files = [f for f in os.listdir(dir_paginas) if f.lower().endswith('.pdf')]
                        total_paginas_result = len(pagina_files)
                except Exception:
                    pass
                
                # PRIORIDADE 2: Se ainda não tem, calcula baseado nos documentos
                if total_paginas_result == 0:
                    total_calculado = 0
                    for doc in documentos_list:
                        if 'num_pages' in doc and doc.get('num_pages'):
                            total_calculado += int(doc.get('num_pages', 0) or 0)
                        elif 'end_page' in doc and 'start_page' in doc:
                            start = int(doc.get('start_page', 1) or 1)
                            end = int(doc.get('end_page', 1) or 1)
                            if end >= start:
                                total_calculado += (end - start + 1)
                        elif 'paginas' in doc and isinstance(doc.get('paginas'), list):
                            total_calculado += len(doc['paginas'])
                        elif 'paginas_doc' in doc:
                            total_calculado += int(doc.get('paginas_doc', 0) or 0)
                    
                    if total_calculado > 0:
                        total_paginas_result = total_calculado
                    else:
                        total_paginas_result = 1  # Mínimo de 1 página
            
            # CRÍTICO: Garante que total_paginas_result é um int e não está None
            total_paginas_final = int(total_paginas_result) if total_paginas_result is not None else 0
            if total_paginas_final == 0 and len(documentos_list) > 0:
                # Última tentativa: calcula a partir dos documentos se ainda está 0
                total_calculado_final = 0
                for doc in documentos_list:
                    if 'num_pages' in doc and doc.get('num_pages'):
                        total_calculado_final += int(doc.get('num_pages', 0) or 0)
                if total_calculado_final > 0:
                    total_paginas_final = total_calculado_final
                else:
                    total_paginas_final = 1  # Mínimo
            
            # Constrói resposta com estrutura esperada pelo frontend
            response_data = {
                'success': True,
                'pasta': {
                    'documentos': documentos_list,
                    'total_paginas': total_paginas_final,  # CRÍTICO: Usa valor garantido como int
                    'cod_documento': result.get('cod_documento', cod_documento),
                    'titulo': result.get('titulo', ''),
                    'async': False,  # Processo já foi concluído
                    'status': 'SUCCESS',
                    'task_id': None
                },
                'materias_vinculadas': result.get('materias_vinculadas', {'anexadas': [], 'anexadoras': [], 'tem_vinculadas': False}),
                'documentos_administrativos': result.get('documentos_administrativos', [])
            }
            
            # Adiciona campos extras se existirem
            if 'titulo' in result:
                response_data['titulo'] = result['titulo']
            
            # CRÍTICO: Verificação final antes de serializar - garante que total_paginas está presente
            if 'total_paginas' not in response_data['pasta'] or response_data['pasta']['total_paginas'] == 0:
                logger.error(f"[PastaDigitalAdmDataView] ❌ ERRO CRÍTICO: total_paginas não está presente ou é 0! Forçando valor mínimo.")
                response_data['pasta']['total_paginas'] = max(1, total_paginas_final) if total_paginas_final > 0 else 1
                # Recalcula dos documentos como última tentativa
                if response_data['pasta']['total_paginas'] == 1:
                    total_recalc = sum(doc.get('num_pages', 0) or 0 for doc in documentos_list if doc.get('num_pages'))
                    if total_recalc > 0:
                        response_data['pasta']['total_paginas'] = total_recalc
            
            # Retorna JSON válido
            json_str = json.dumps(response_data, ensure_ascii=False, cls=DateTimeJSONEncoder)
            # Valida que o JSON é válido antes de retornar
            try:
                json_valido = json.loads(json_str)
                # CRÍTICO: Verifica se total_paginas está no JSON validado
                if 'pasta' not in json_valido or 'total_paginas' not in json_valido['pasta']:
                    logger.error(f"[PastaDigitalAdmDataView] ❌ JSON validado mas pasta.total_paginas não encontrado! pasta_keys={list(json_valido.get('pasta', {}).keys()) if 'pasta' in json_valido else 'pasta não existe'}")
                    # Força adicionar total_paginas se não estiver presente
                    if 'pasta' in json_valido:
                        json_valido['pasta']['total_paginas'] = total_paginas_final
                        json_str = json.dumps(json_valido, ensure_ascii=False, cls=DateTimeJSONEncoder)
            except json.JSONDecodeError as e:
                logger.error(f"[PastaDigitalAdmDataView] JSON inválido gerado: {e}")
                self.request.RESPONSE.setStatus(500)
                return json.dumps({'success': False, 'error': 'Erro ao serializar resposta JSON'})
            
            return json_str
            
        except Exception as e:
            logger.error(f"[PastaDigitalAdmDataView] Erro: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return json.dumps({'success': False, 'error': str(e)})


class ProcessoAdmDownloadDocumentoView(grok.View):
    """View para download de documentos individuais da pasta digital administrativa"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_download_documento')
    
    def render(self):
        try:
            # Extrai parâmetros
            cod_documento_str = self.request.form.get('cod_documento') or self.request.get('cod_documento')
            filename = self.request.form.get('file') or self.request.get('file')
            
            if not cod_documento_str or not filename:
                self.request.response.setStatus(400)
                return "Parâmetros cod_documento e file são obrigatórios"
            
            # Valida filename (segurança - evita path traversal)
            if '..' in filename or '/' in filename or '\\' in filename:
                self.request.response.setStatus(400)
                return "Nome de arquivo inválido"
            
            cod_documento_int = int(cod_documento_str)
            
            # IMPORTANTE: Busca sempre no filesystem (diretório da pasta digital)
            # Se o usuário conseguiu abrir a pasta digital, já tem permissão adequada
            # Todos os arquivos da pasta digital são copiados para o diretório durante a geração
            
            file_content = self._get_file_from_pasta_dir(cod_documento_int, filename)
            
            if file_content is None:
                self.request.response.setStatus(404)
                return "Arquivo não encontrado"
            
            # Define nome do arquivo para download: usa título se disponível, senão usa filename
            title = self.request.form.get('title') or self.request.get('title') or ''
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
            return "Parâmetro cod_documento inválido"
        except Exception as e:
            logger.error(f"[processo_adm_download_documento] Erro: {e}", exc_info=True)
            self.request.response.setStatus(500)
            return f"Erro ao baixar documento: {str(e)}"
    
    def _get_file_from_pasta_dir(self, cod_documento, filename):
        """
        Obtém arquivo do diretório da pasta digital no filesystem.
        
        IMPORTANTE: O 'filename' vem do campo 'file' do cache.json, que contém
        o nome do arquivo original (ex: "capa_DM-5779-2025.pdf", "20038_texto_integral.pdf").
        
        Esses arquivos são copiados para o diretório pasta_digital/{cod_documento}/ durante a geração.
        """
        try:
            dir_base = get_processo_dir_adm(cod_documento)
            
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
                    file_content = self._get_capa_dinamica(cod_documento, filename, dir_base)
                    if file_content:
                        return file_content
                
                # Se não encontrou, tenta buscar o arquivo original no ZODB e salvar no diretório
                # Isso permite que arquivos sejam baixados mesmo se não foram copiados durante a geração
                logger.debug(f"[_get_file_from_pasta_dir] Tentando buscar arquivo original no ZODB: {filename}")
                file_content = self._get_file_from_zodb_and_save(cod_documento, filename, dir_base)
                if file_content:
                    return file_content
                
                return None
            
            # Lê arquivo do filesystem
            with open(file_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"[_get_file_from_pasta_dir] Erro ao obter {filename} do diretório: {e}", exc_info=True)
            return None
    
    def _get_file_from_zodb_and_save(self, cod_documento, filename, dir_base):
        """
        Busca arquivo no ZODB e salva no diretório para uso futuro.
        Usa o mesmo método que a geração da pasta digital usa para copiar arquivos.
        """
        try:
            from Products.CMFCore.utils import getToolByName
            
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            
            if not hasattr(portal, 'sapl_documentos'):
                return None
            
            # Determina o container baseado no nome do arquivo
            container = None
            
            # Documentos administrativos principais
            if filename.endswith('_texto_integral.pdf'):
                if hasattr(portal.sapl_documentos, 'administrativo'):
                    container = portal.sapl_documentos.administrativo
            # Documentos acessórios
            elif '_acessorio_' in filename or filename.endswith('_acessorio.pdf'):
                if hasattr(portal.sapl_documentos, 'administrativo'):
                    container = portal.sapl_documentos.administrativo
            # Tramitações
            elif '_tram.pdf' in filename or filename.endswith('_tramitacao.pdf'):
                if hasattr(portal.sapl_documentos, 'administrativo') and hasattr(portal.sapl_documentos.administrativo, 'tramitacao'):
                    container = portal.sapl_documentos.administrativo.tramitacao
            # Capa
            elif filename.startswith('capa_'):
                # Capa é gerada dinamicamente, não está no ZODB
                return None
            # Folha de ciências
            elif filename == 'folha_cientificacoes.pdf':
                if hasattr(portal.sapl_documentos, 'administrativo'):
                    container = portal.sapl_documentos.administrativo
            
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
    
    def _get_capa_dinamica(self, cod_documento, filename, dir_base):
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
            
            # URL da view de capa (mesma usada durante a geração)
            capa_url = f"{base_url}/@@capa_processo_adm_integral?cod_documento={cod_documento}"
            
            # Faz requisição HTTP para gerar capa
            with urllib.request.urlopen(capa_url) as response:
                file_content = response.read()
                
                if file_content:
                    # Salva no diretório para uso futuro
                    try:
                        file_path = os.path.join(dir_base, filename)
                        os.makedirs(dir_base, mode=0o700, exist_ok=True)
                        with open(file_path, 'wb') as f:
                            f.write(file_content)
                    except Exception as save_err:
                        logger.warning(f"[_get_capa_dinamica] Erro ao salvar capa: {save_err}")
                    
                    return file_content
            
            return None
            
        except Exception as e:
            logger.error(f"[_get_capa_dinamica] Erro ao gerar capa dinamicamente: {e}", exc_info=True)
            return None
