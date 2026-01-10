# -*- coding: utf-8 -*-
"""
View para fornecer dados JSON para a interface de pasta digital
"""
import json
import logging
import os
import shutil
import hashlib
import traceback
import copy
import time
from datetime import date, datetime
from five import grok
from zope.interface import Interface
from Products.CMFCore.utils import getToolByName
from openlegis.sagl.browser.processo_leg.processo_leg_utils import (
    get_processo_dir,
    get_cache_file_path,
    safe_check_file,
    safe_check_files_batch,
    safe_check_file_with_content,
    get_file_size,
    get_file_info_for_hash,
    secure_path_join
)
from openlegis.sagl.browser.processo_leg.processo_leg_service import ProcessoLegService
from z3c.saconfig import named_scoped_session
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload, selectinload
from openlegis.sagl.models.models import (
    MateriaLegislativa, TipoMateriaLegislativa, Emenda, TipoEmenda,
    Substitutivo, Relatoria, Comissao, Anexada, DocumentoAcessorio,
    Tramitacao, StatusTramitacao, NormaJuridica, VinculoNormaJuridica,
    TipoNormaJuridica, DocumentoAdministrativo, DocumentoAdministrativoMateria,
    TipoDocumentoAdministrativo, Proposicao, TipoProposicao
)

Session = named_scoped_session('minha_sessao')

logger = logging.getLogger(__name__)

# OTIMIZAÇÃO: Cache pequeno para hash de documentos (TTL curto para garantir atualização rápida)
# Formato: {cod_materia: (hash_value, timestamp)}
# TTL: 30 segundos - garante que mudanças sejam detectadas rapidamente
_hash_cache = {}
_HASH_CACHE_TTL = 30  # 30 segundos - cache curto para garantir atualização rápida
_HASH_CACHE_MAX_SIZE = 50  # Máximo de 50 entradas no cache

class DateTimeJSONEncoder(json.JSONEncoder):
    """Encoder JSON customizado para converter objetos date/datetime para string"""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            if isinstance(obj, datetime):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            else:
                return obj.strftime('%Y-%m-%d')
        return super().default(obj)

# Cache temporário para rastrear tasks recém-criadas (evita race condition)
# Formato: {cod_materia: (task_id, timestamp)}
_recent_tasks_cache = {}
import threading

# Cache para documentos prontos - REMOVIDO: usando apenas cache em filesystem
# O cache em filesystem é automaticamente removido quando o diretório é apagado
# Isso simplifica a invalidação e evita problemas de cache em memória
_ready_documents_cache_ttl = 300.0  # 5 minutos - TTL para cache de documentos prontos (filesystem)

# Funções para gerenciar cache em filesystem (dentro do diretório da pasta de cada matéria)
# Usa função utilitária compartilhada
def _get_cache_file_path(cod_materia_int):
    """Retorna o caminho do arquivo de cache para uma matéria (dentro do diretório da pasta)"""
    return get_cache_file_path(cod_materia_int)

def _load_cache_from_filesystem(cod_materia_int):
    """Carrega cache do filesystem para uma matéria"""
    try:
        cache_file = _get_cache_file_path(cod_materia_int)
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Valida estrutura
                if isinstance(data, dict) and 'documentos' in data and 'timestamp' in data:
                    documentos_data = data['documentos']
                    timestamp = data['timestamp']
                    documents_hash = data.get('hash', None)
                    documents_sizes = data.get('sizes', None)  # Tamanhos dos arquivos
                    logger.debug(f"[_load_cache_from_filesystem] Cache carregado do filesystem para matéria {cod_materia_int}")
                    return (documentos_data, timestamp, documents_hash, documents_sizes)
    except Exception as e:
        logger.debug(f"[_load_cache_from_filesystem] Erro ao carregar cache do filesystem para {cod_materia_int}: {e}")
    return None

def _calculate_documents_sizes(cod_materia, portal):
    """
    Calcula os tamanhos dos arquivos coletados para uma matéria.
    Retorna um dicionário com {nome_arquivo: tamanho} ou None em caso de erro.
    """
    try:
        sizes = {}
        
        if not hasattr(portal, 'sapl_documentos'):
            return sizes
        
        # 1. Texto integral
        arquivo_texto = f"{cod_materia}_texto_integral.pdf"
        if hasattr(portal.sapl_documentos, 'materia'):
            size = get_file_size(portal.sapl_documentos.materia, arquivo_texto)
            if size:
                sizes[arquivo_texto] = size
        
        # 2. Redação final
        arquivo_redacao = f"{cod_materia}_redacao_final.pdf"
        if hasattr(portal.sapl_documentos, 'materia'):
            size = get_file_size(portal.sapl_documentos.materia, arquivo_redacao)
            if size:
                sizes[arquivo_redacao] = size
        
        # 3. Emendas
        try:
            session = Session()
            try:
                emendas = session.query(Emenda)\
                    .filter(Emenda.cod_materia == cod_materia)\
                    .filter(Emenda.ind_excluido == 0)\
                    .all()
                for emenda_obj in emendas:
                    if hasattr(portal.sapl_documentos, 'emenda'):
                        filename = f"{emenda_obj.cod_emenda}_emenda.pdf"
                        size = get_file_size(portal.sapl_documentos.emenda, filename)
                        if size is not None:
                            sizes[filename] = size
            finally:
                session.close()
        except Exception as e:
            logger.debug(f"[_calculate_documents_sizes] Erro ao obter tamanhos de emendas: {e}")
        
        # 4. Substitutivos
        try:
            session = Session()
            try:
                substitutivos = session.query(Substitutivo)\
                    .filter(Substitutivo.cod_materia == cod_materia)\
                    .filter(Substitutivo.ind_excluido == 0)\
                    .all()
                for subst_obj in substitutivos:
                    if hasattr(portal.sapl_documentos, 'substitutivo'):
                        filename = f"{subst_obj.cod_substitutivo}_substitutivo.pdf"
                        size = get_file_size(portal.sapl_documentos.substitutivo, filename)
                        if size:
                            sizes[filename] = size
            finally:
                session.close()
        except Exception as e:
            logger.debug(f"[_calculate_documents_sizes] Erro ao obter tamanhos de substitutivos: {e}")
        
        # 5. Documentos acessórios
        try:
            session = Session()
            try:
                docs_acessorios = session.query(DocumentoAcessorio)\
                    .filter(DocumentoAcessorio.cod_materia == cod_materia)\
                    .filter(DocumentoAcessorio.ind_excluido == 0)\
                    .all()
                for doc_obj in docs_acessorios:
                    if hasattr(portal.sapl_documentos, 'documento_acessorio'):
                        filename = f"{doc_obj.cod_documento}_documento_acessorio.pdf"
                        size = get_file_size(portal.sapl_documentos.documento_acessorio, filename)
                        if size is not None:
                            sizes[filename] = size
            finally:
                session.close()
        except Exception as e:
            logger.debug(f"[_calculate_documents_sizes] Erro ao obter tamanhos de documentos acessórios: {e}")
        
        return sizes
    except Exception as e:
        logger.warning(f"[_calculate_documents_sizes] Erro ao calcular tamanhos dos documentos: {e}")
        return None

def _save_cache_to_filesystem(cod_materia_int, documentos_data, timestamp, documents_hash, documents_sizes=None):
    """Salva cache no filesystem para uma matéria (dentro do diretório da pasta)"""
    try:
        cache_file = _get_cache_file_path(cod_materia_int)
        # Garante que o diretório existe
        cache_dir = os.path.dirname(cache_file)
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        
        data = {
            'documentos': documentos_data,
            'timestamp': timestamp,
            'hash': documents_hash,
            'cod_materia': str(cod_materia_int)
        }
        # Adiciona tamanhos dos arquivos se fornecidos
        if documents_sizes is not None:
            data['sizes'] = documents_sizes
        
        # Escreve atomicamente (cria arquivo temporário primeiro)
        temp_file = cache_file + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, cls=DateTimeJSONEncoder)
        # Move arquivo temporário para o arquivo final (operação atômica)
        os.replace(temp_file, cache_file)
        logger.debug(f"[_save_cache_to_filesystem] Cache salvo no filesystem para matéria {cod_materia_int} em {cache_file}")
    except Exception as e:
        logger.warning(f"[_save_cache_to_filesystem] Erro ao salvar cache no filesystem para {cod_materia_int}: {e}")

def _delete_cache_from_filesystem(cod_materia_int):
    """Remove cache do filesystem para uma matéria"""
    try:
        cache_file = _get_cache_file_path(cod_materia_int)
        if os.path.exists(cache_file):
            os.unlink(cache_file)
            logger.debug(f"[_delete_cache_from_filesystem] Cache removido do filesystem para matéria {cod_materia_int}")
    except Exception as e:
        logger.debug(f"[_delete_cache_from_filesystem] Erro ao remover cache do filesystem para {cod_materia_int}: {e}")

def _collect_current_documents_metadata(cod_materia_int, portal):
    """
    Coleta metadados dos documentos atuais do sistema (sem fazer download).
    Retorna uma lista de dicionários com informações sobre cada documento que seria coletado.
    
    Para a capa, obtém o tamanho atual via HTTP para detectar mudanças.
    Para fichas de votação, verifica se existem no diretório coletado.
    
    Returns:
        list: Lista de dicionários com {'file': nome_arquivo, 'file_size': tamanho, 'title': titulo}
    """
    documentos_atual = []
    
    try:
        if not hasattr(portal, 'sapl_documentos'):
            return documentos_atual
        
        # Calcula diretório base para verificar arquivos coletados
        install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
        hash_materia = hashlib.md5(str(cod_materia_int).encode()).hexdigest()
        dir_base = os.path.join(install_home, f'var/tmp/processo_leg_integral_{hash_materia}')
        
        
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
        
        # Obtém dados da matéria para construir nomes de arquivos
        try:
            # Tenta obter dados básicos da matéria usando SQLAlchemy
            session = Session()
            try:
                result = session.query(MateriaLegislativa, TipoMateriaLegislativa)\
                    .join(TipoMateriaLegislativa, 
                          MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                    .filter(MateriaLegislativa.cod_materia == cod_materia_int)\
                    .filter(MateriaLegislativa.ind_excluido == 0)\
                    .first()
                
                if result:
                    materia_obj, tipo_obj = result
                    tipo = tipo_obj.sgl_tipo_materia if hasattr(tipo_obj, 'sgl_tipo_materia') and tipo_obj.sgl_tipo_materia else 'PL'
                    numero = materia_obj.num_ident_basica if hasattr(materia_obj, 'num_ident_basica') and materia_obj.num_ident_basica else '0'
                    ano = materia_obj.ano_ident_basica if hasattr(materia_obj, 'ano_ident_basica') and materia_obj.ano_ident_basica else '2025'
                else:
                    # Fallback para valores padrão se matéria não encontrada
                    tipo = 'PL'
                    numero = '0'
                    ano = '2025'
            finally:
                session.close()
            
            # 1. Capa do processo - sempre incluída, pois é sempre gerada durante a coleta
            # A capa é gerada dinamicamente via HTTP e não existe no ZODB
            # CRÍTICO: Para detectar mudanças na capa, obtemos o tamanho atual via HTTP
            # ao invés de usar o arquivo antigo no diretório
            arquivo_capa = f"capa_{tipo}-{numero}-{ano}.pdf"
            
            # Obtém tamanho atual da capa via HTTP (para detectar mudanças)
            capa_size = 0
            try:
                base_url = portal.absolute_url() if hasattr(portal, 'absolute_url') else ''
                if base_url:
                    url = f"{base_url}/modelo_proposicao/capa_processo?cod_materia={cod_materia_int}&action=download"
                    import urllib.request
                    req = urllib.request.Request(url)
                    req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                    
                    with urllib.request.urlopen(req, timeout=10) as response:
                        capa_data = response.read()
                        if capa_data:
                            capa_size = len(capa_data)
            except Exception as e:
                # Se falhar ao obter via HTTP, tenta usar arquivo no diretório
                logger.debug(f"[_collect_current_documents_metadata] Erro ao obter capa via HTTP: {e}, usando arquivo do diretório")
                capa_size = _get_collected_file_size(arquivo_capa)
            
            # Sempre inclui a capa na lista (sempre é gerada na coleta)
            documentos_atual.append({
                    'file': arquivo_capa,
                    'file_size': capa_size,  # Tamanho atual obtido via HTTP ou do diretório
                    'title': 'Capa do Processo'
                })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao obter dados da matéria: {e}")
            # Continua mesmo sem dados da matéria
        
        # 2. Texto integral
        arquivo_texto = f"{cod_materia_int}_texto_integral.pdf"
        if hasattr(portal.sapl_documentos, 'materia'):
            if safe_check_file(portal.sapl_documentos.materia, arquivo_texto):
                size = get_file_size(portal.sapl_documentos.materia, arquivo_texto) or 0
                documentos_atual.append({
                    'file': arquivo_texto,
                    'file_size': size,
                    'title': 'Texto Integral'
                })
        
        # 3. Redação final
        arquivo_redacao = f"{cod_materia_int}_redacao_final.pdf"
        if hasattr(portal.sapl_documentos, 'materia'):
            if safe_check_file(portal.sapl_documentos.materia, arquivo_redacao):
                size = get_file_size(portal.sapl_documentos.materia, arquivo_redacao)
                documentos_atual.append({
                    'file': arquivo_redacao,
                    'file_size': size,
                    'title': 'Redação Final'
                })
        
        # 4. Emendas
        session = None
        try:
            session = Session()
            emendas = session.query(Emenda)\
                .filter(and_(Emenda.cod_materia == cod_materia_int, Emenda.ind_excluido == 0))\
                .all()
            
            for emenda_obj in emendas:
                arquivo_emenda = f"{emenda_obj.cod_emenda}_emenda.pdf"
                if hasattr(portal.sapl_documentos, 'emenda'):
                    if safe_check_file(portal.sapl_documentos.emenda, arquivo_emenda):
                        size = get_file_size(portal.sapl_documentos.emenda, arquivo_emenda) or 0
                        documentos_atual.append({
                            'file': arquivo_emenda,
                            'file_size': size,
                            'title': f'Emenda {emenda_obj.cod_emenda}'
                        })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar emendas: {e}")
        finally:
            if session:
                session.close()
        
        # 5. Substitutivos
        try:
            session = Session()
            substitutivos = session.query(Substitutivo)\
                .filter(and_(Substitutivo.cod_materia == cod_materia_int, Substitutivo.ind_excluido == 0))\
                .all()
            
            for subst_obj in substitutivos:
                arquivo_sub = f"{subst_obj.cod_substitutivo}_substitutivo.pdf"
                if hasattr(portal.sapl_documentos, 'substitutivo'):
                    if safe_check_file(portal.sapl_documentos.substitutivo, arquivo_sub):
                        size = get_file_size(portal.sapl_documentos.substitutivo, arquivo_sub)
                        documentos_atual.append({
                            'file': arquivo_sub,
                            'file_size': size,
                            'title': f'Substitutivo {subst_obj.cod_substitutivo}'
                        })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar substitutivos: {e}")
        finally:
            if session:
                session.close()
        
        # 6. Votações (fichas de votação são geradas dinamicamente, mas contamos)
        try:
            pysc = None
            if hasattr(portal, 'pysc'):
                pysc = portal.pysc
            elif hasattr(portal, 'context') and hasattr(portal.context, 'pysc'):
                pysc = portal.context.pysc
            
            if pysc and hasattr(pysc, 'votacao_obter_pysc'):
                votacoes = pysc.votacao_obter_pysc(cod_materia=cod_materia_int) or []
                votacoes_relevantes = []
                
                for votacao in votacoes:
                    fase = votacao.get('fase', '')
                    if fase == "Expediente - Leitura de Matérias":
                        continue
                    
                    # Filtra votações de leitura
                    turno = votacao.get('txt_turno', '')
                    resultado = votacao.get('txt_resultado', '')
                    tipo_votacao = votacao.get('txt_tipo_votacao', '')
                    
                    if (turno and 'leitura' in turno.lower()) or \
                       (resultado and 'lido em plenário' in resultado.lower()) or \
                       (tipo_votacao and 'leitura' in tipo_votacao.lower()):
                        continue
                    
                    votacoes_relevantes.append(votacao)
                
                # Numera as fichas de votação apenas com as votações relevantes
                for i, votacao in enumerate(votacoes_relevantes):
                    turno = votacao.get('txt_turno', '')
                    nome_arquivo = f'ficha_votacao_{i + 1}.pdf'
                    # Tenta obter tamanho do arquivo coletado, se existir
                    ficha_size = _get_collected_file_size(nome_arquivo)
                    documentos_atual.append({
                        'file': nome_arquivo,
                        'file_size': ficha_size,  # Usa tamanho real se arquivo existe no diretório
                        'title': f'Registro de Votação ({turno})'
                    })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar votações: {e}")
        
        # 7. Relatorias/Pareceres
        try:
            session = Session()
            relatorias = session.query(Relatoria, Comissao)\
                .join(Comissao, Relatoria.cod_comissao == Comissao.cod_comissao)\
                .filter(and_(
                    Relatoria.cod_materia == cod_materia_int,
                    Relatoria.ind_excluido == 0,
                    Comissao.ind_excluido == 0
                ))\
                .all()
            
            for rel_obj, comissao_obj in relatorias:
                arquivo_rel = f"{rel_obj.cod_relatoria}_parecer.pdf"
                if hasattr(portal.sapl_documentos, 'parecer_comissao'):
                    if safe_check_file(portal.sapl_documentos.parecer_comissao, arquivo_rel):
                        size = get_file_size(portal.sapl_documentos.parecer_comissao, arquivo_rel) or 0
                        documentos_atual.append({
                            'file': arquivo_rel,
                            'file_size': size,
                            'title': f'Parecer {comissao_obj.sgl_comissao} nº {rel_obj.num_parecer}/{rel_obj.ano_parecer}'
                        })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar relatorias: {e}")
        finally:
            if session:
                session.close()
        
        # 8. Matérias Anexadas
        try:
            session = Session()
            anexadas = session.query(Anexada, MateriaLegislativa, TipoMateriaLegislativa)\
                .join(MateriaLegislativa, Anexada.cod_materia_anexada == MateriaLegislativa.cod_materia)\
                .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                .filter(and_(
                    Anexada.cod_materia_principal == cod_materia_int,
                    Anexada.ind_excluido == 0
                ))\
                .all()
            
            for anexada_obj, materia_obj, tipo_obj in anexadas:
                arquivo_anexada = f"{anexada_obj.cod_materia_anexada}_texto_integral.pdf"
                if hasattr(portal.sapl_documentos, 'materia'):
                    if safe_check_file(portal.sapl_documentos.materia, arquivo_anexada):
                        size = get_file_size(portal.sapl_documentos.materia, arquivo_anexada)
                        documentos_atual.append({
                            'file': arquivo_anexada,
                            'file_size': size,
                            'title': f"{tipo_obj.sgl_tipo_materia} {materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica} (anexada)"
                        })
                        
                        # Documentos acessórios das matérias anexadas
                        docs_anexada = session.query(DocumentoAcessorio, Proposicao)\
                            .outerjoin(Proposicao, Proposicao.cod_mat_ou_doc == DocumentoAcessorio.cod_documento)\
                            .outerjoin(TipoProposicao, Proposicao.tip_proposicao == TipoProposicao.tip_proposicao)\
                            .filter(or_(Proposicao.cod_proposicao.is_(None), TipoProposicao.ind_mat_ou_doc == 'D'))\
                            .filter(and_(
                                DocumentoAcessorio.cod_materia == anexada_obj.cod_materia_anexada,
                                DocumentoAcessorio.ind_excluido == 0
                            ))\
                            .all()
                        
                        for doc_obj, proposta_obj in docs_anexada:
                            arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                            if hasattr(portal.sapl_documentos, 'materia'):
                                if safe_check_file(portal.sapl_documentos.materia, arquivo_acessorio):
                                    size = get_file_size(portal.sapl_documentos.materia, arquivo_acessorio) or 0
                                    documentos_atual.append({
                                        'file': arquivo_acessorio,
                                        'file_size': size,
                                        'title': f"{doc_obj.nom_documento} (acess. de anexada)"
                                    })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar matérias anexadas: {e}")
        finally:
            if session:
                session.close()
        
        # 9. Matérias Anexadoras
        try:
            session = Session()
            anexadoras = session.query(Anexada, MateriaLegislativa, TipoMateriaLegislativa)\
                .join(MateriaLegislativa, Anexada.cod_materia_principal == MateriaLegislativa.cod_materia)\
                .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                .filter(and_(
                    Anexada.cod_materia_anexada == cod_materia_int,
                    Anexada.ind_excluido == 0
                ))\
                .all()
            
            for anexada_obj, materia_obj, tipo_obj in anexadoras:
                arquivo_anexadora = f"{anexada_obj.cod_materia_principal}_texto_integral.pdf"
                if hasattr(portal.sapl_documentos, 'materia'):
                    if safe_check_file(portal.sapl_documentos.materia, arquivo_anexadora):
                        size = get_file_size(portal.sapl_documentos.materia, arquivo_anexadora)
                        documentos_atual.append({
                            'file': arquivo_anexadora,
                            'file_size': size,
                            'title': f"{tipo_obj.sgl_tipo_materia} {materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica} (anexadora)"
                        })
                        
                        # Documentos acessórios das matérias anexadoras
                        docs_anexadora = session.query(DocumentoAcessorio, Proposicao)\
                            .outerjoin(Proposicao, Proposicao.cod_mat_ou_doc == DocumentoAcessorio.cod_documento)\
                            .outerjoin(TipoProposicao, Proposicao.tip_proposicao == TipoProposicao.tip_proposicao)\
                            .filter(or_(Proposicao.cod_proposicao.is_(None), TipoProposicao.ind_mat_ou_doc == 'D'))\
                            .filter(and_(
                                DocumentoAcessorio.cod_materia == anexada_obj.cod_materia_principal,
                                DocumentoAcessorio.ind_excluido == 0
                            ))\
                            .all()
                        
                        for doc_obj, proposta_obj in docs_anexadora:
                            arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                            if hasattr(portal.sapl_documentos, 'materia'):
                                if safe_check_file(portal.sapl_documentos.materia, arquivo_acessorio):
                                    size = get_file_size(portal.sapl_documentos.materia, arquivo_acessorio) or 0
                                    documentos_atual.append({
                                        'file': arquivo_acessorio,
                                        'file_size': size,
                                        'title': f"{doc_obj.nom_documento} (acess. de anexadora)"
                                    })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar matérias anexadoras: {e}")
        finally:
            if session:
                session.close()
        
        # 10. Documentos Acessórios da Matéria Principal
        try:
            session = Session()
            documentos_acessorios = session.query(DocumentoAcessorio, Proposicao)\
                .outerjoin(Proposicao, Proposicao.cod_mat_ou_doc == DocumentoAcessorio.cod_documento)\
                .outerjoin(TipoProposicao, Proposicao.tip_proposicao == TipoProposicao.tip_proposicao)\
                .filter(or_(Proposicao.cod_proposicao == None, TipoProposicao.ind_mat_ou_doc == 'D'))\
                .filter(and_(
                    DocumentoAcessorio.cod_materia == cod_materia_int,
                    DocumentoAcessorio.ind_excluido == 0
                ))\
                .all()
            
            for doc_obj, proposta_obj in documentos_acessorios:
                arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                if hasattr(portal.sapl_documentos, 'materia'):
                    if safe_check_file(portal.sapl_documentos.materia, arquivo_acessorio):
                        size = get_file_size(portal.sapl_documentos.materia, arquivo_acessorio)
                        documentos_atual.append({
                            'file': arquivo_acessorio,
                            'file_size': size,
                            'title': doc_obj.nom_documento
                        })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar documentos acessórios: {e}")
        finally:
            if session:
                session.close()
        
        # 11. Tramitações
        try:
            session = Session()
            tramitacoes = session.query(Tramitacao, StatusTramitacao)\
                .join(StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status)\
                .filter(and_(
                    Tramitacao.cod_materia == cod_materia_int,
                    Tramitacao.ind_excluido == 0
                ))\
                .order_by(Tramitacao.dat_tramitacao, Tramitacao.cod_tramitacao)\
                .all()
            
            for tram_obj, status_obj in tramitacoes:
                arquivo_tram = f"{tram_obj.cod_tramitacao}_tram.pdf"
                if hasattr(portal.sapl_documentos, 'materia') and hasattr(portal.sapl_documentos.materia, 'tramitacao'):
                    if safe_check_file(portal.sapl_documentos.materia.tramitacao, arquivo_tram):
                        size = get_file_size(portal.sapl_documentos.materia.tramitacao, arquivo_tram)
                        documentos_atual.append({
                            'file': arquivo_tram,
                            'file_size': size,
                            'title': f"Tramitação ({status_obj.des_status})"
                        })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar tramitações: {e}")
        finally:
            if session:
                session.close()
        
        # 12. Normas Jurídicas Relacionadas
        try:
            session = Session()
            normas = session.query(NormaJuridica, TipoNormaJuridica)\
                .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                .filter(and_(
                    NormaJuridica.cod_materia == cod_materia_int,
                    NormaJuridica.ind_excluido == 0
                ))\
                .all()
            
            for norma_obj, tipo_norma_obj in normas:
                arquivo_norma = f"{norma_obj.cod_norma}_texto_integral.pdf"
                if hasattr(portal.sapl_documentos, 'norma_juridica'):
                    if safe_check_file(portal.sapl_documentos.norma_juridica, arquivo_norma):
                        size = get_file_size(portal.sapl_documentos.norma_juridica, arquivo_norma) or 0
                        documentos_atual.append({
                            'file': arquivo_norma,
                            'file_size': size,
                            'title': f"{tipo_norma_obj.sgl_tipo_norma} nº {norma_obj.num_norma}/{norma_obj.ano_norma}"
                        })
        except Exception as e:
            logger.debug(f"[_collect_current_documents_metadata] Erro ao processar normas jurídicas: {e}")
        finally:
            if session:
                session.close()
        
    except Exception as e:
        logger.warning(f"[_collect_current_documents_metadata] Erro ao coletar metadados dos documentos: {e}")
    
    return documentos_atual


def _compare_documents_with_metadados(cod_materia_int, portal):
    """
    Compara os documentos ATUAIS do sistema com dados armazenados em documentos_metadados.json.
    
    IMPORTANTE: Para cada geração, os documentos são coletados do sistema novamente.
    Esta função compara os documentos que seriam coletados AGORA com o que foi coletado na última geração.
    
    Returns:
        tuple: (has_changes, details_dict) onde:
            - has_changes: True se há mudanças que exigem regeneração
            - details_dict: dicionário com detalhes das mudanças (novos, removidos, modificados)
    """
    try:
        # Calcula diretório base
        install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
        hash_materia = hashlib.md5(str(cod_materia_int).encode()).hexdigest()
        dir_base = os.path.join(install_home, f'var/tmp/processo_leg_integral_{hash_materia}')
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
            logger.debug(f"[_compare_documents_with_metadados] Nenhum documento nos metadados")
            return (False, {})
        
        # Coleta documentos ATUAIS do sistema
        documentos_atual = _collect_current_documents_metadata(cod_materia_int, portal)
        
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
        
        # Separa fichas de votação dos outros documentos
        # Fichas de votação têm numeração baseada em índice, então comparamos por quantidade e tamanho total
        fichas_meta = {doc.get('file', ''): doc for doc in documentos_metadados 
                      if doc.get('file', '').startswith('ficha_votacao_')}
        fichas_atual = {doc.get('file', ''): doc for doc in documentos_atual 
                       if doc.get('file', '').startswith('ficha_votacao_')}
        
        outros_docs_meta = {doc.get('file', ''): doc for doc in documentos_metadados 
                           if not doc.get('file', '').startswith('ficha_votacao_')}
        outros_docs_atual = {doc.get('file', ''): doc for doc in documentos_atual 
                            if not doc.get('file', '').startswith('ficha_votacao_')}
        
        # Cria mapas para comparação (por nome de arquivo) - apenas para documentos não-fichas
        metadados_map = outros_docs_meta
        atual_map = outros_docs_atual
        
        has_changes = False
        details = {
            'added': [],      # Arquivos novos
            'removed': [],    # Arquivos removidos
            'modified': [],   # Arquivos que mudaram de tamanho
        }
        
        # COMPARAÇÃO ESPECIAL PARA FICHAS DE VOTAÇÃO
        # Compara quantidade e tamanho total, não nomes individuais (que podem mudar por ordem)
        if len(fichas_meta) != len(fichas_atual):
            has_changes = True
            if len(fichas_atual) > len(fichas_meta):
                details['added'].extend([f"fichas_votacao (+{len(fichas_atual) - len(fichas_meta)})"])
            else:
                details['removed'].extend([f"fichas_votacao (-{len(fichas_meta) - len(fichas_atual)})"])
        else:
            # Mesma quantidade - verifica se os arquivos coletados no diretório correspondem
            # Lista todas as fichas de votação no diretório
            fichas_in_dir = []
            try:
                for filename in os.listdir(dir_base):
                    if filename.startswith('ficha_votacao_') and filename.endswith('.pdf'):
                        file_path = os.path.join(dir_base, filename)
                        if os.path.isfile(file_path):
                            fichas_in_dir.append({
                                'file': filename,
                                'size': os.path.getsize(file_path)
                            })
            except Exception as e:
                logger.debug(f"[_compare_documents_with_metadados] Erro ao listar fichas no diretório: {e}")
            
            # Compara tamanho total das fichas
            total_size_meta = sum(doc.get('file_size', 0) for doc in fichas_meta.values())
            total_size_atual = sum(doc.get('file_size', 0) for doc in fichas_atual.values())
            total_size_dir = sum(f.get('size', 0) for f in fichas_in_dir)
            
            # Usa o tamanho do diretório se disponível (mais confiável)
            size_to_compare_fichas = total_size_dir if total_size_dir > 0 else total_size_atual
            
            if total_size_meta > 0 and size_to_compare_fichas > 0:
                # Tolerância de 1% para diferenças de geração (PDFs podem ter tamanho ligeiramente diferente)
                diff_percent = abs(total_size_meta - size_to_compare_fichas) / total_size_meta if total_size_meta > 0 else 0
                if diff_percent > 0.01:  # Mais de 1% de diferença
                    has_changes = True
                    details['modified'].append({
                        'type': 'fichas_votacao_total',
                        'old_size': total_size_meta,
                        'new_size': size_to_compare_fichas
                    })
            elif total_size_meta > 0 and size_to_compare_fichas == 0:
                # Tinha fichas antes mas não tem mais
                has_changes = True
                details['removed'].append('fichas_votacao')
            elif total_size_meta == 0 and size_to_compare_fichas > 0:
                # Não tinha fichas antes mas tem agora
                has_changes = True
                details['added'].append('fichas_votacao')
        
        # Verifica arquivos removidos (estavam no JSON mas não estão mais no sistema)
        for file_name, doc_meta in metadados_map.items():
            if file_name not in atual_map:
                has_changes = True
                details['removed'].append(file_name)
        
        # Verifica arquivos novos (estão no sistema mas não estavam no JSON)
        for file_name, doc_atual in atual_map.items():
            if file_name not in metadados_map:
                has_changes = True
                details['added'].append(file_name)
            else:
                # Arquivo existe em ambos - verifica se tamanho mudou
                doc_meta = metadados_map[file_name]
                size_meta = doc_meta.get('file_size', 0)
                size_atual = doc_atual.get('file_size', 0)
                
                # CRÍTICO: Para todos os documentos baixados (incluindo capa), sempre usa o tamanho atual do sistema
                # O arquivo no diretório pode ser antigo e não refletir mudanças recentes no sistema.
                # size_atual já contém o tamanho atual obtido do sistema (via HTTP para capa, via ZODB para outros)
                size_to_compare = size_atual
                size_in_dir = _get_collected_file_size_in_dir(file_name)  # Apenas para log/debug
                
                # Verifica se é capa para definir tamanho mínimo de comparação
                is_capa = file_name.startswith('capa_') and file_name.endswith('.pdf')
                
                
                # Fichas de votação já foram comparadas acima por quantidade e tamanho total
                # Aqui comparamos todos os arquivos baixados (incluindo capa) usando tamanho atual do sistema
                # Todos os documentos agora usam size_to_compare que contém o tamanho atual do sistema
                
                # Define tamanho mínimo para comparação (0 para capa, 100 para outros)
                min_size = 0 if is_capa else 100
                
                # Se ambos têm tamanho válido, compara diretamente
                if size_meta > min_size and size_to_compare > min_size:
                    if size_meta != size_to_compare:
                        has_changes = True
                        details['modified'].append({
                            'file': file_name,
                            'old_size': size_meta,
                            'new_size': size_to_compare
                        })
                        tipo_arquivo = "Capa" if is_capa else "Arquivo"
                # Se tinha no JSON mas não conseguiu obter tamanho atual do sistema
                elif size_meta > min_size and size_to_compare == 0:
                    # Arquivo estava no JSON mas não foi possível obter tamanho atual
                    # Pode indicar erro ou que o arquivo foi removido do sistema
                    # Por segurança, não marca como mudança automaticamente - pode ser erro temporário
                    tipo_arquivo = "Capa" if is_capa else "Arquivo"
                    logger.warning(f"[_compare_documents_with_metadados] {tipo_arquivo} {file_name} está no JSON ({size_meta} bytes) mas não foi possível obter tamanho atual do sistema")
                # Se não tinha no JSON mas tem agora, é um arquivo novo
                elif size_meta == 0 and size_to_compare > min_size:
                    has_changes = True
                    details['modified'].append({
                        'file': file_name,
                        'old_size': size_meta,
                        'new_size': size_to_compare
                    })
                    tipo_arquivo = "Capa" if is_capa else "Arquivo"
        
        if not has_changes:
            logger.debug(f"[_compare_documents_with_metadados] Nenhuma mudança detectada: {len(documentos_atual)} documentos correspondem aos metadados")
        
        return (has_changes, details)
        
    except Exception as e:
        logger.warning(f"[_compare_documents_with_metadados] Erro ao comparar documentos com metadados: {e}")
        # Em caso de erro, assume que há mudanças (mais seguro)
        return (True, {'error': str(e)})

def _calculate_documents_hash(cod_materia, portal):
    """
    Calcula um hash dos documentos disponíveis para uma matéria.
    Isso permite detectar quando documentos são adicionados, modificados ou excluídos.
    Retorna None em caso de erro.
    
    OTIMIZAÇÃO: Usa cache pequeno com TTL curto (30s) para evitar recálculos repetidos
    em um curto período, mas garante que mudanças sejam detectadas rapidamente.
    """
    global _hash_cache
    
    # OTIMIZAÇÃO: Verifica cache primeiro (TTL curto para garantir atualização rápida)
    current_time = time.time()
    cache_key = cod_materia
    
    if cache_key in _hash_cache:
        cached_hash, cache_timestamp = _hash_cache[cache_key]
        age = current_time - cache_timestamp
        
        # Se cache ainda é válido (menos de 30 segundos), retorna hash em cache
        if age < _HASH_CACHE_TTL:
            logger.debug(f"[_calculate_documents_hash] Hash retornado do cache para cod_materia={cod_materia} (idade: {age:.1f}s)")
            return cached_hash
        else:
            # Cache expirado, remove
            logger.debug(f"[_calculate_documents_hash] Cache expirado para cod_materia={cod_materia} (idade: {age:.1f}s)")
            del _hash_cache[cache_key]
    
    # OTIMIZAÇÃO: Limpa cache antigo se muito grande (mantém apenas últimos 50)
    if len(_hash_cache) >= _HASH_CACHE_MAX_SIZE:
        # Remove entradas mais antigas
        sorted_items = sorted(_hash_cache.items(), key=lambda x: x[1][1])
        items_to_remove = len(_hash_cache) - _HASH_CACHE_MAX_SIZE + 1
        for key, _ in sorted_items[:items_to_remove]:
            del _hash_cache[key]
        logger.debug(f"[_calculate_documents_hash] Cache limpo: removidas {items_to_remove} entradas antigas")
    
    try:
        hash_data = []
        
        # Obtém o contexto do portal
        if not hasattr(portal, 'sapl_documentos'):
            return None
        
        # 1. Verifica texto integral (lazy loading)
        arquivo_texto = f"{cod_materia}_texto_integral.pdf"
        if hasattr(portal.sapl_documentos, 'materia'):
            if safe_check_file(portal.sapl_documentos.materia, arquivo_texto):
                # LAZY LOADING: Só obtém metadados se arquivo existe
                file_info = get_file_info_for_hash(portal.sapl_documentos.materia, arquivo_texto)
                if file_info:
                    hash_data.append(f"texto_integral:{'|'.join(file_info)}")
                else:
                    hash_data.append(f"texto_integral:exists")
            else:
                hash_data.append(f"texto_integral:not_exists")
        else:
            hash_data.append(f"texto_integral:not_exists")
        
        # 2. Verifica redação final (lazy loading)
        arquivo_redacao = f"{cod_materia}_redacao_final.pdf"
        if hasattr(portal.sapl_documentos, 'materia'):
            if safe_check_file(portal.sapl_documentos.materia, arquivo_redacao):
                # LAZY LOADING: Só obtém metadados se arquivo existe
                file_info = get_file_info_for_hash(portal.sapl_documentos.materia, arquivo_redacao)
                if file_info:
                    hash_data.append(f"redacao_final:{'|'.join(file_info)}")
                else:
                    hash_data.append(f"redacao_final:exists")
            else:
                hash_data.append(f"redacao_final:not_exists")
        else:
            hash_data.append(f"redacao_final:not_exists")
        
        # 3-8. Todas as consultas SQLAlchemy consolidadas em uma única sessão
        # OTIMIZAÇÃO: Usa uma única sessão para todas as consultas, reduzindo overhead
        session = None
        try:
            session = Session()
            
            # 3. Conta e verifica emendas
            # OTIMIZAÇÃO: Usa and_() para filtros compostos, verificação em batch e eager loading
            try:
                # OTIMIZAÇÃO: Eager loading usando selectinload (mais eficiente para múltiplos registros)
                # selectinload faz queries separadas otimizadas ao invés de JOINs que podem gerar duplicação
                emendas_query = session.query(Emenda)\
                    .filter(and_(Emenda.cod_materia == cod_materia, Emenda.ind_excluido == 0))
                
                # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                # Usa try/except para não quebrar se relações não existirem
                try:
                    # Tenta carregar relação tipo_emenda se existir
                    emendas_query = emendas_query.options(selectinload(Emenda.tipo_emenda))
                except (AttributeError, Exception):
                    # Se relação não existir, continua sem eager loading
                    pass
                
                emendas = emendas_query.all()
                hash_data.append(f"emendas_count:{len(emendas)}")
                
                # OTIMIZAÇÃO: Verifica múltiplos arquivos de uma vez quando possível
                if emendas and hasattr(portal.sapl_documentos, 'emenda'):
                    # Prepara lista de arquivos para verificação em batch
                    arquivos_emendas = [f"{emenda_obj.cod_emenda}_emenda.pdf" for emenda_obj in emendas]
                    # Verifica todos os arquivos de uma vez (chama objectIds() uma única vez)
                    resultados_emendas = safe_check_files_batch(portal.sapl_documentos.emenda, arquivos_emendas)
                    
                    # Processa resultados
                    for emenda_obj in emendas:
                        arquivo_emenda = f"{emenda_obj.cod_emenda}_emenda.pdf"
                        if resultados_emendas.get(arquivo_emenda, False):
                            # LAZY LOADING: Só obtém metadados se arquivo existe
                            file_info = get_file_info_for_hash(portal.sapl_documentos.emenda, arquivo_emenda)
                            if file_info:
                                hash_data.append(f"emenda_{emenda_obj.cod_emenda}:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"emenda_{emenda_obj.cod_emenda}:exists")
                        else:
                            hash_data.append(f"emenda_{emenda_obj.cod_emenda}:not_exists")
                else:
                    # Se não tem emendas ou container, marca todos como não existentes
                    for emenda_obj in emendas:
                        hash_data.append(f"emenda_{emenda_obj.cod_emenda}:not_exists")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash] Erro ao processar emendas: {e}")
            
            # 4. Conta e verifica substitutivos
            # OTIMIZAÇÃO: Usa and_() para filtros compostos, verificação em batch e eager loading
            try:
                # OTIMIZAÇÃO: Eager loading usando selectinload
                substitutivos_query = session.query(Substitutivo)\
                    .filter(and_(Substitutivo.cod_materia == cod_materia, Substitutivo.ind_excluido == 0))
                
                # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                try:
                    # Tenta carregar relação tipo_substitutivo se existir
                    substitutivos_query = substitutivos_query.options(selectinload(Substitutivo.tipo_substitutivo))
                except (AttributeError, Exception):
                    # Se relação não existir, continua sem eager loading
                    pass
                
                substitutivos = substitutivos_query.all()
                hash_data.append(f"substitutivos_count:{len(substitutivos)}")
                
                # OTIMIZAÇÃO: Verifica múltiplos arquivos de uma vez quando possível
                if substitutivos and hasattr(portal.sapl_documentos, 'substitutivo'):
                    # Prepara lista de arquivos para verificação em batch
                    arquivos_substitutivos = [f"{subst_obj.cod_substitutivo}_substitutivo.pdf" for subst_obj in substitutivos]
                    # Verifica todos os arquivos de uma vez (chama objectIds() uma única vez)
                    resultados_substitutivos = safe_check_files_batch(portal.sapl_documentos.substitutivo, arquivos_substitutivos)
                    
                    # Processa resultados
                    for subst_obj in substitutivos:
                        arquivo_sub = f"{subst_obj.cod_substitutivo}_substitutivo.pdf"
                        if resultados_substitutivos.get(arquivo_sub, False):
                            # LAZY LOADING: Só obtém metadados se arquivo existe
                            file_info = get_file_info_for_hash(portal.sapl_documentos.substitutivo, arquivo_sub)
                            if file_info:
                                hash_data.append(f"substitutivo_{subst_obj.cod_substitutivo}:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"substitutivo_{subst_obj.cod_substitutivo}:exists")
                        else:
                            hash_data.append(f"substitutivo_{subst_obj.cod_substitutivo}:not_exists")
                else:
                    # Se não tem substitutivos ou container, marca todos como não existentes
                    for subst_obj in substitutivos:
                        hash_data.append(f"substitutivo_{subst_obj.cod_substitutivo}:not_exists")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash] Erro ao processar substitutivos: {e}")
            
            # 5. Conta votações (fichas de votação são geradas dinamicamente)
            try:
                # Tenta acessar pysc via portal ou context
                pysc = None
                if hasattr(portal, 'pysc'):
                    pysc = portal.pysc
                elif hasattr(portal, 'context') and hasattr(portal.context, 'pysc'):
                    pysc = portal.context.pysc
                
                if pysc and hasattr(pysc, 'votacao_obter_pysc'):
                    votacoes = pysc.votacao_obter_pysc(cod_materia=cod_materia) or []
                    # Filtra apenas votações relevantes (exclui "Expediente - Leitura de Matérias")
                    votacoes_relevantes = [v for v in votacoes if v.get('fase', '') != "Expediente - Leitura de Matérias"]
                    hash_data.append(f"votacoes_count:{len(votacoes_relevantes)}")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash] Erro ao processar votações: {e}")
            
            # 6. Conta relatorias/pareceres
            # OTIMIZAÇÃO: Usa and_() para filtros compostos e eager loading
            try:
                # OTIMIZAÇÃO: Eager loading usando selectinload
                relatorias_query = session.query(Relatoria)\
                    .filter(and_(Relatoria.cod_materia == cod_materia, Relatoria.ind_excluido == 0))
                
                # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                try:
                    # Tenta carregar relação comissao se existir
                    relatorias_query = relatorias_query.options(selectinload(Relatoria.comissao))
                except (AttributeError, Exception):
                    # Se relação não existir, continua sem eager loading
                    pass
                
                relatorias = relatorias_query.all()
                hash_data.append(f"relatorias_count:{len(relatorias)}")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash] Erro ao processar relatorias: {e}")
            
            # 7. Conta e verifica tramitações
            # OTIMIZAÇÃO: Usa and_() para filtros compostos, order_by e eager loading
            try:
                # OTIMIZAÇÃO: Eager loading usando selectinload
                tramitacoes_query = session.query(Tramitacao)\
                    .filter(and_(Tramitacao.cod_materia == cod_materia, Tramitacao.ind_excluido == 0))\
                    .order_by(Tramitacao.dat_tramitacao)
                
                # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                try:
                    # Tenta carregar relações se existirem
                    tramitacoes_query = tramitacoes_query.options(
                        selectinload(Tramitacao.status_tramitacao),
                        selectinload(Tramitacao.unidade_tramitacao_destino)
                    )
                except (AttributeError, Exception):
                    # Se relações não existirem, tenta carregar individualmente
                    try:
                        tramitacoes_query = tramitacoes_query.options(selectinload(Tramitacao.status_tramitacao))
                    except (AttributeError, Exception):
                        pass
                    try:
                        tramitacoes_query = tramitacoes_query.options(selectinload(Tramitacao.unidade_tramitacao_destino))
                    except (AttributeError, Exception):
                        pass
                
                tramitacoes = tramitacoes_query.all()
                hash_data.append(f"tramitacoes_count:{len(tramitacoes)}")
                
                # Verifica arquivos PDF de tramitações (batch)
                if tramitacoes and hasattr(portal.sapl_documentos, 'materia') and hasattr(portal.sapl_documentos.materia, 'tramitacao'):
                    # OTIMIZAÇÃO: Verifica múltiplos arquivos de uma vez quando possível
                    arquivos_tramitacoes = [f"{tram_obj.cod_tramitacao}_tram.pdf" for tram_obj in tramitacoes]
                    # Verifica todos os arquivos de uma vez (chama objectIds() uma única vez)
                    resultados_tramitacoes = safe_check_files_batch(portal.sapl_documentos.materia.tramitacao, arquivos_tramitacoes)
                    
                    # Processa resultados
                    for tram_obj in tramitacoes:
                        arquivo_tram = f"{tram_obj.cod_tramitacao}_tram.pdf"
                        if resultados_tramitacoes.get(arquivo_tram, False):
                            # LAZY LOADING: Só obtém metadados se arquivo existe
                            file_info = get_file_info_for_hash(portal.sapl_documentos.materia.tramitacao, arquivo_tram)
                            if file_info:
                                hash_data.append(f"tramitacao_{tram_obj.cod_tramitacao}:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"tramitacao_{tram_obj.cod_tramitacao}:exists")
                        else:
                            hash_data.append(f"tramitacao_{tram_obj.cod_tramitacao}:not_exists")
                else:
                    # Se não tem pasta de tramitações, marca todas como não existentes
                    for tram_obj in tramitacoes:
                        hash_data.append(f"tramitacao_{tram_obj.cod_tramitacao}:not_exists")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash] Erro ao processar tramitações: {e}")
            
            # 8. Conta e verifica documentos acessórios
            # OTIMIZAÇÃO: Usa and_() para filtros compostos e batch queries para evitar N+1
            try:
                # Documentos acessórios da matéria principal
                # OTIMIZAÇÃO: Eager loading usando selectinload
                documentos_acessorios_query = session.query(DocumentoAcessorio)\
                    .filter(and_(DocumentoAcessorio.cod_materia == cod_materia, DocumentoAcessorio.ind_excluido == 0))
                
                # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                try:
                    # Tenta carregar relação tipo_documento se existir
                    documentos_acessorios_query = documentos_acessorios_query.options(selectinload(DocumentoAcessorio.tipo_documento))
                except (AttributeError, Exception):
                    # Se relação não existir, continua sem eager loading
                    pass
                
                documentos_acessorios = documentos_acessorios_query.all()
                hash_data.append(f"documentos_acessorios_principal_count:{len(documentos_acessorios)}")
                
                # Verifica arquivos PDF de documentos acessórios da matéria principal (batch)
                if documentos_acessorios and hasattr(portal.sapl_documentos, 'materia'):
                    # OTIMIZAÇÃO: Verifica múltiplos arquivos de uma vez quando possível
                    arquivos_acessorios = [f"{doc_obj.cod_documento}.pdf" for doc_obj in documentos_acessorios]
                    # Verifica todos os arquivos de uma vez (chama objectIds() uma única vez)
                    resultados_acessorios = safe_check_files_batch(portal.sapl_documentos.materia, arquivos_acessorios)
                    
                    # Processa resultados
                    for doc_obj in documentos_acessorios:
                        arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                        if resultados_acessorios.get(arquivo_acessorio, False):
                            # LAZY LOADING: Só obtém metadados se arquivo existe
                            file_info = get_file_info_for_hash(portal.sapl_documentos.materia, arquivo_acessorio)
                            if file_info:
                                hash_data.append(f"acessorio_principal_{doc_obj.cod_documento}:{'|'.join(file_info)}")
                            else:
                                hash_data.append(f"acessorio_principal_{doc_obj.cod_documento}:exists")
                        else:
                            hash_data.append(f"acessorio_principal_{doc_obj.cod_documento}:not_exists")
                else:
                    # Se não tem pasta de matérias, marca todos como não existentes
                    for doc_obj in documentos_acessorios:
                        hash_data.append(f"acessorio_principal_{doc_obj.cod_documento}:not_exists")
                
                # Documentos acessórios de matérias anexadas
                # OTIMIZAÇÃO: Query única com filtro composto e eager loading
                anexadas_query = session.query(Anexada)\
                    .filter(and_(Anexada.cod_materia_principal == cod_materia, Anexada.ind_excluido == 0))
                
                # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                # Baseado no modelo, Anexada tem relações: materia_legislativa (anexada) e materia_legislativa_ (principal)
                try:
                    # Tenta carregar relações se existirem (nomes podem variar conforme modelo)
                    anexadas_query = anexadas_query.options(
                        selectinload(Anexada.materia_legislativa_),
                        selectinload(Anexada.materia_legislativa)
                    )
                except (AttributeError, Exception):
                    # Se relações não existirem, tenta carregar individualmente
                    try:
                        anexadas_query = anexadas_query.options(selectinload(Anexada.materia_legislativa_))
                    except (AttributeError, Exception):
                        pass
                    try:
                        anexadas_query = anexadas_query.options(selectinload(Anexada.materia_legislativa))
                    except (AttributeError, Exception):
                        pass
                
                anexadas = anexadas_query.all()
                hash_data.append(f"anexadas_count:{len(anexadas)}")
                
                # OTIMIZAÇÃO: Batch query para documentos acessórios de matérias anexadas
                # Evita N+1 queries fazendo uma única query com IN() para todas as matérias anexadas
                docs_por_anexada = {}
                if anexadas:
                    materias_anexadas_ids = [anexada_obj.cod_materia_anexada for anexada_obj in anexadas]
                    # Query única para todos os documentos acessórios das matérias anexadas
                    # OTIMIZAÇÃO: Eager loading usando selectinload
                    docs_anexadas_all_query = session.query(DocumentoAcessorio)\
                        .filter(and_(
                            DocumentoAcessorio.cod_materia.in_(materias_anexadas_ids),
                            DocumentoAcessorio.ind_excluido == 0
                        ))
                    
                    # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                    try:
                        # Tenta carregar relação tipo_documento se existir
                        docs_anexadas_all_query = docs_anexadas_all_query.options(selectinload(DocumentoAcessorio.tipo_documento))
                    except (AttributeError, Exception):
                        # Se relação não existir, continua sem eager loading
                        pass
                    
                    docs_anexadas_all = docs_anexadas_all_query.all()
                    
                    # Agrupa documentos por matéria anexada para processamento
                    for doc_obj in docs_anexadas_all:
                        if doc_obj.cod_materia not in docs_por_anexada:
                            docs_por_anexada[doc_obj.cod_materia] = []
                        docs_por_anexada[doc_obj.cod_materia].append(doc_obj)
                
                for anexada_obj in anexadas:
                    # Usa documentos já carregados em batch
                    docs_anexada = docs_por_anexada.get(anexada_obj.cod_materia_anexada, [])
                    hash_data.append(f"acessorios_anexada_{anexada_obj.cod_materia_anexada}_count:{len(docs_anexada)}")
                    
                    # Verifica arquivos PDF de documentos acessórios de matérias anexadas (batch)
                    if docs_anexada and hasattr(portal.sapl_documentos, 'materia'):
                        # OTIMIZAÇÃO: Verifica múltiplos arquivos de uma vez quando possível
                        arquivos_anexada = [f"{doc_obj.cod_documento}.pdf" for doc_obj in docs_anexada]
                        # Verifica todos os arquivos de uma vez (chama objectIds() uma única vez)
                        resultados_anexada = safe_check_files_batch(portal.sapl_documentos.materia, arquivos_anexada)
                        
                        # Processa resultados
                        for doc_obj in docs_anexada:
                            arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                            if resultados_anexada.get(arquivo_acessorio, False):
                                # LAZY LOADING: Só obtém metadados se arquivo existe
                                file_info = get_file_info_for_hash(portal.sapl_documentos.materia, arquivo_acessorio)
                                if file_info:
                                    hash_data.append(f"acessorio_anexada_{doc_obj.cod_documento}:{'|'.join(file_info)}")
                                else:
                                    hash_data.append(f"acessorio_anexada_{doc_obj.cod_documento}:exists")
                            else:
                                hash_data.append(f"acessorio_anexada_{doc_obj.cod_documento}:not_exists")
                    else:
                        # Se não tem pasta de matérias, marca todos como não existentes
                        for doc_obj in docs_anexada:
                            hash_data.append(f"acessorio_anexada_{doc_obj.cod_documento}:not_exists")
                
                # Documentos acessórios de matérias anexadoras
                # OTIMIZAÇÃO: Query única com filtro composto e eager loading
                anexadoras_query = session.query(Anexada)\
                    .filter(and_(Anexada.cod_materia_anexada == cod_materia, Anexada.ind_excluido == 0))
                
                # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                # Baseado no modelo, Anexada tem relações: materia_legislativa (anexada) e materia_legislativa_ (principal)
                try:
                    # Tenta carregar relações se existirem (nomes podem variar conforme modelo)
                    anexadoras_query = anexadoras_query.options(
                        selectinload(Anexada.materia_legislativa_),
                        selectinload(Anexada.materia_legislativa)
                    )
                except (AttributeError, Exception):
                    # Se relações não existirem, tenta carregar individualmente
                    try:
                        anexadoras_query = anexadoras_query.options(selectinload(Anexada.materia_legislativa_))
                    except (AttributeError, Exception):
                        pass
                    try:
                        anexadoras_query = anexadoras_query.options(selectinload(Anexada.materia_legislativa))
                    except (AttributeError, Exception):
                        pass
                
                anexadoras = anexadoras_query.all()
                hash_data.append(f"anexadoras_count:{len(anexadoras)}")
                
                # OTIMIZAÇÃO: Batch query para documentos acessórios de matérias anexadoras
                # Evita N+1 queries fazendo uma única query com IN() para todas as matérias anexadoras
                docs_por_anexadora = {}
                if anexadoras:
                    materias_anexadoras_ids = [anexadora_obj.cod_materia_principal for anexadora_obj in anexadoras]
                    # Query única para todos os documentos acessórios das matérias anexadoras
                    # OTIMIZAÇÃO: Eager loading usando selectinload
                    docs_anexadoras_all_query = session.query(DocumentoAcessorio)\
                        .filter(and_(
                            DocumentoAcessorio.cod_materia.in_(materias_anexadoras_ids),
                            DocumentoAcessorio.ind_excluido == 0
                        ))
                    
                    # OTIMIZAÇÃO: Tenta adicionar eager loading se houver relações definidas no modelo
                    try:
                        # Tenta carregar relação tipo_documento se existir
                        docs_anexadoras_all_query = docs_anexadoras_all_query.options(selectinload(DocumentoAcessorio.tipo_documento))
                    except (AttributeError, Exception):
                        # Se relação não existir, continua sem eager loading
                        pass
                    
                    docs_anexadoras_all = docs_anexadoras_all_query.all()
                    
                    # Agrupa documentos por matéria anexadora para processamento
                    for doc_obj in docs_anexadoras_all:
                        if doc_obj.cod_materia not in docs_por_anexadora:
                            docs_por_anexadora[doc_obj.cod_materia] = []
                        docs_por_anexadora[doc_obj.cod_materia].append(doc_obj)
                
                for anexadora_obj in anexadoras:
                    # Usa documentos já carregados em batch
                    docs_anexadora = docs_por_anexadora.get(anexadora_obj.cod_materia_principal, [])
                    hash_data.append(f"acessorios_anexadora_{anexadora_obj.cod_materia_principal}_count:{len(docs_anexadora)}")
                    
                    # Verifica arquivos PDF de documentos acessórios de matérias anexadoras (batch)
                    if docs_anexadora and hasattr(portal.sapl_documentos, 'materia'):
                        # OTIMIZAÇÃO: Verifica múltiplos arquivos de uma vez quando possível
                        arquivos_anexadora = [f"{doc_obj.cod_documento}.pdf" for doc_obj in docs_anexadora]
                        # Verifica todos os arquivos de uma vez (chama objectIds() uma única vez)
                        resultados_anexadora = safe_check_files_batch(portal.sapl_documentos.materia, arquivos_anexadora)
                        
                        # Processa resultados
                        for doc_obj in docs_anexadora:
                            arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                            if resultados_anexadora.get(arquivo_acessorio, False):
                                # LAZY LOADING: Só obtém metadados se arquivo existe
                                file_info = get_file_info_for_hash(portal.sapl_documentos.materia, arquivo_acessorio)
                                if file_info:
                                    hash_data.append(f"acessorio_anexadora_{doc_obj.cod_documento}:{'|'.join(file_info)}")
                                else:
                                    hash_data.append(f"acessorio_anexadora_{doc_obj.cod_documento}:exists")
                            else:
                                hash_data.append(f"acessorio_anexadora_{doc_obj.cod_documento}:not_exists")
                    else:
                        # Se não tem pasta de matérias, marca todos como não existentes
                        for doc_obj in docs_anexadora:
                            hash_data.append(f"acessorio_anexadora_{doc_obj.cod_documento}:not_exists")
            except Exception as e:
                logger.debug(f"[_calculate_documents_hash] Erro ao processar documentos acessórios: {e}")
                
        except Exception as e:
            logger.debug(f"[_calculate_documents_hash] Erro geral nas consultas SQLAlchemy: {e}")
        finally:
            # Garante que a sessão seja fechada mesmo em caso de erro
            if session is not None:
                try:
                    session.close()
                except:
                    pass
        
        # Calcula hash MD5 dos dados coletados
        if hash_data:
            hash_string = "|".join(sorted(hash_data))
            calculated_hash = hashlib.md5(hash_string.encode('utf-8')).hexdigest()
            
            # OTIMIZAÇÃO: Armazena no cache com timestamp
            _hash_cache[cache_key] = (calculated_hash, current_time)
            
            logger.debug(f"[_calculate_documents_hash] Hash calculado para cod_materia={cod_materia}: {calculated_hash[:8]}... (dados: {len(hash_data)} itens, cache size: {len(_hash_cache)})")
            # Log dos primeiros itens do hash para debug
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[_calculate_documents_hash] Primeiros itens do hash: {sorted(hash_data)[:5]}")
            return calculated_hash
        else:
            logger.warning(f"[_calculate_documents_hash] Nenhum dado coletado para calcular hash (cod_materia={cod_materia})")
            return None
    except Exception as e:
        logger.warning(f"[_calculate_documents_hash] Erro ao calcular hash dos documentos: {e}")
        return None

# Lock por cod_materia para evitar criação simultânea de tasks
_task_creation_locks = {}
_locks_lock = threading.Lock()  # Lock para proteger o dicionário de locks



class PastaDigitalMixin:
    """Mixin com métodos compartilhados entre PastaDigitalView e PastaDigitalDataView"""

    def _get_materia_data(self, cod_materia):
        """Obtém dados da matéria usando SQLAlchemy"""
        try:
            materia_info = {
                'cod_materia': cod_materia,
                'sgl_tipo_materia': '',
                'num_ident_basica': '',
                'ano_ident_basica': '',
                'titulo': f'Matéria {cod_materia}'
            }
            
            # SQLAlchemy
            try:
                session = Session()
                try:
                    result = session.query(MateriaLegislativa, TipoMateriaLegislativa)\
                        .join(TipoMateriaLegislativa, 
                              MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                        .filter(MateriaLegislativa.cod_materia == cod_materia)\
                        .filter(MateriaLegislativa.ind_excluido == 0)\
                        .first()
                    
                    if result:
                        materia_obj, tipo_obj = result
                        materia_info.update({
                            'sgl_tipo_materia': tipo_obj.sgl_tipo_materia or '',
                            'num_ident_basica': materia_obj.num_ident_basica or '',
                            'ano_ident_basica': materia_obj.ano_ident_basica or '',
                            'titulo': f"{tipo_obj.sgl_tipo_materia} {materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica}".strip()
                        })
                        # Se o título ficou vazio, usa fallback
                        if not materia_info['titulo'] or materia_info['titulo'] == '/':
                            materia_info['titulo'] = f'Matéria {cod_materia}'
                finally:
                    session.close()
            except Exception as sql_err:
                logger.error(f"Erro ao executar SQLAlchemy query: {sql_err}")
            
            return materia_info
        except Exception as e:
            logger.error(f"Erro ao obter dados da matéria: {e}", exc_info=True)
            return {
                'cod_materia': cod_materia,
                'titulo': f'Matéria {cod_materia}',
                'error': str(e)
            }

    def _get_portal_config(self, portal):
        """Obtém configurações do portal (logo, nome da casa, etc.)"""
        try:
            config = {
                'nom_casa': '',
                'id_logo': None,
                'existe_logo': False,
                'logo_url': None
            }
            
            # Obtém nome da casa
            try:
                sapl_docs = getattr(portal, 'sapl_documentos', None)
                if sapl_docs:
                    props = getattr(sapl_docs, 'props_sagl', None)
                    if props:
                        config['nom_casa'] = getattr(props, 'nom_casa', '')
                        config['id_logo'] = getattr(props, 'id_logo', None)
                        
                        # Verifica se logo existe
                        if config['id_logo']:
                            try:
                                # Tenta verificar se o logo existe
                                image_ids = props.objectIds('Image')
                                if config['id_logo'] in image_ids:
                                    config['existe_logo'] = True
                                    config['logo_url'] = f"sapl_documentos/props_sagl/{config['id_logo']}"
                            except:
                                pass
            except Exception as e:
                logger.error(f"Erro ao obter configuração do portal: {e}")
            
            return config
        except Exception as e:
            logger.error(f"Erro ao obter configuração do portal: {e}")
            return {
                'nom_casa': '',
                'id_logo': None,
                'existe_logo': False,
                'logo_url': None
            }

    def _get_materias_relacionadas(self, cod_materia, portal):
        """Obtém matérias relacionadas (anexadas/anexadoras)"""
        try:
            relacionadas = {
                'anexadas': [],
                'anexadoras': [],
                'tem_relacionadas': False
            }
            
            # SQLAlchemy
            try:
                session = Session()
                try:
                    # Matérias anexadas (filhas) - com JOIN
                    anexadas = session.query(Anexada, MateriaLegislativa, TipoMateriaLegislativa)\
                        .join(MateriaLegislativa, Anexada.cod_materia_anexada == MateriaLegislativa.cod_materia)\
                        .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                        .filter(Anexada.cod_materia_principal == cod_materia)\
                        .filter(Anexada.ind_excluido == 0)\
                        .filter(MateriaLegislativa.ind_excluido == 0)\
                        .all()
                    
                    for anexada_obj, materia_obj, tipo_obj in anexadas:
                        relacionadas['anexadas'].append({
                            'cod_materia': anexada_obj.cod_materia_anexada,
                            'sgl_tipo_materia': tipo_obj.sgl_tipo_materia or '',
                            'num_ident_basica': materia_obj.num_ident_basica or '',
                            'ano_ident_basica': materia_obj.ano_ident_basica or '',
                            'titulo': f"{tipo_obj.sgl_tipo_materia}-{materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica}"
                        })
                    
                    # Matérias anexadoras (pais) - com JOIN
                    anexadoras = session.query(Anexada, MateriaLegislativa, TipoMateriaLegislativa)\
                        .join(MateriaLegislativa, Anexada.cod_materia_principal == MateriaLegislativa.cod_materia)\
                        .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                        .filter(Anexada.cod_materia_anexada == cod_materia)\
                        .filter(Anexada.ind_excluido == 0)\
                        .filter(MateriaLegislativa.ind_excluido == 0)\
                        .all()
                    
                    for anexada_obj, materia_obj, tipo_obj in anexadoras:
                        relacionadas['anexadoras'].append({
                            'cod_materia': anexada_obj.cod_materia_principal,
                            'sgl_tipo_materia': tipo_obj.sgl_tipo_materia or '',
                            'num_ident_basica': materia_obj.num_ident_basica or '',
                            'ano_ident_basica': materia_obj.ano_ident_basica or '',
                            'titulo': f"{tipo_obj.sgl_tipo_materia}-{materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica}"
                        })
                finally:
                    session.close()
            except Exception as e:
                logger.error(f"Erro ao obter matérias relacionadas (SQLAlchemy): {e}")
            
            relacionadas['tem_relacionadas'] = len(relacionadas['anexadas']) > 0 or len(relacionadas['anexadoras']) > 0
            return relacionadas
        except Exception as e:
            logger.error(f"Erro ao obter matérias relacionadas: {e}")
            return {
                'anexadas': [],
                'anexadoras': [],
                'tem_relacionadas': False
            }

    def _get_documentos_administrativos(self, cod_materia, portal):
        """Obtém documentos administrativos vinculados - SQLAlchemy"""
        try:
            documentos = []
            session = Session()
            try:
                # Busca documentos administrativos vinculados à matéria com JOIN
                docs_materia = session.query(DocumentoAdministrativoMateria, DocumentoAdministrativo, TipoDocumentoAdministrativo)\
                    .join(DocumentoAdministrativo, DocumentoAdministrativoMateria.cod_documento == DocumentoAdministrativo.cod_documento)\
                    .join(TipoDocumentoAdministrativo, DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
                    .filter(DocumentoAdministrativoMateria.cod_materia == cod_materia)\
                    .filter(DocumentoAdministrativoMateria.ind_excluido == 0)\
                    .filter(DocumentoAdministrativo.ind_excluido == 0)\
                    .all()
                
                for doc_materia_obj, doc_obj, tipo_doc_obj in docs_materia:
                    documentos.append({
                        'cod_documento': doc_obj.cod_documento,
                        'sgl_tipo_documento': tipo_doc_obj.sgl_tipo_documento or '',
                        'num_documento': doc_obj.num_documento or '',
                        'ano_documento': doc_obj.ano_documento or '',
                        'titulo': f"{tipo_doc_obj.sgl_tipo_documento}-{doc_obj.num_documento}/{doc_obj.ano_documento}"
                    })
            finally:
                session.close()
            
            return documentos
        except Exception as e:
            logger.error(f"Erro ao obter documentos administrativos: {e}")
            return []

    def _get_normas_juridicas(self, cod_materia, portal):
        """Obtém normas jurídicas derivadas"""
        try:
            normas = []
            # SQLAlchemy
            try:
                session = Session()
                try:
                    normas_query = session.query(NormaJuridica, TipoNormaJuridica)\
                        .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                        .filter(NormaJuridica.cod_materia == cod_materia)\
                        .filter(NormaJuridica.ind_excluido == 0)\
                        .all()
                    
                    for norma_obj, tipo_norma_obj in normas_query:
                        normas.append({
                            'cod_norma': norma_obj.cod_norma,
                            'sgl_norma': tipo_norma_obj.sgl_tipo_norma or '',
                            'num_norma': norma_obj.num_norma or '',
                            'ano_norma': norma_obj.ano_norma or '',
                            'titulo': f"{tipo_norma_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma}"
                        })
                finally:
                    session.close()
            except Exception as e:
                logger.error(f"Erro ao obter normas jurídicas (SQLAlchemy): {e}")
            
            return normas
        except Exception as e:
            logger.error(f"Erro ao obter normas jurídicas: {e}")
            return []

    def _get_pasta_data(self, cod_materia, action, tool, portal):
        """Obtém dados da pasta digital chamando diretamente a view processo_leg_integral"""
        try:
            # Cria um objeto de resposta base para garantir que nunca seja None
            base_response = {
                'async': True,  # SEMPRE True para action=pasta (força o monitor aparecer)
                'task_id': None,
                'status': 'PENDING',
                'documentos': [],
                'cod_materia': int(cod_materia) if cod_materia and str(cod_materia).isdigit() else cod_materia,
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
                    cod_materia_int = int(cod_materia)
                    cod_materia_str = str(cod_materia_int)  # Define no início para uso em todo o escopo
                    
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
                    
                    if cod_materia_str in _recent_tasks_cache:
                        cached_task_id, cache_timestamp = _recent_tasks_cache[cod_materia_str]
                        if current_time - cache_timestamp < cache_ttl:
                            # Task foi criada recentemente, mas verifica se já há documentos prontos
                            
                            # Inicializa has_recent_task antes do try block para evitar UnboundLocalError
                            has_recent_task = True
                            
                            # CRÍTICO: Verifica se há documentos prontos mesmo com task recente
                            # A task pode ter completado rapidamente
                            try:
                                # Usa serviço para obter documentos prontos
                                service = ProcessoLegService(self.context, self.request)
                                check_result = service.get_documentos_prontos(cod_materia, skip_signature_check=True)
                                
                                if isinstance(check_result, dict) and 'documentos' in check_result and len(check_result.get('documentos', [])) > 0:
                                    # CRÍTICO: Verifica se diretório ainda existe antes de retornar documentos
                                    # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                    from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                                    dir_base_check = get_processo_dir(cod_materia_int)
                                    if not os.path.exists(dir_base_check):
                                        # Diretório não existe - documentos foram apagados
                                        # Limpa cache de tasks recentes
                                        _recent_tasks_cache.pop(cod_materia_str, None)
                                        # Limpa cache de documentos (filesystem)
                                        _delete_cache_from_filesystem(cod_materia_int)
                                        # Força criação de nova task
                                        has_recent_task = False
                                        cached_task_id = None
                                        needs_regeneration = True
                                        # Continua para criar nova task (não retorna aqui)
                                    else:
                                        # Diretório existe - verifica se documentos foram alterados usando documentos_metadados.json
                                        # CRÍTICO: Usa comparação com documentos_metadados.json
                                        has_changes_metadados, changes_details = _compare_documents_with_metadados(cod_materia_int, portal)
                                        
                                        if has_changes_metadados:
                                            # Mudanças detectadas - arquivos foram adicionados, removidos ou modificados
                                            # Limpa cache de tasks recentes
                                            _recent_tasks_cache.pop(cod_materia_str, None)
                                            # Limpa cache de documentos
                                            _delete_cache_from_filesystem(cod_materia_int)
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
                                                if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                                    result_copy['paginas_geral'] = result_copy['total_paginas']
                                                if 'cod_materia' not in result_copy:
                                                    result_copy['cod_materia'] = cod_materia_int
                                                # CRÍTICO: Calcula hash e tamanhos dos documentos e atualiza cache (apenas filesystem)
                                                documents_hash = _calculate_documents_hash(cod_materia_int, portal)
                                                documents_sizes = _calculate_documents_sizes(cod_materia_int, portal)
                                                _save_cache_to_filesystem(cod_materia_int, result_copy, current_time, documents_hash, documents_sizes)
                                                
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
                                from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                                dir_base_check = get_processo_dir(cod_materia_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_materia_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem(cod_materia_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Continua para criar nova task (não retorna aqui)
                                else:
                                    # Diretório existe - retorna status PENDING normalmente
                                    # Se não encontrou documentos prontos, retorna status PENDING
                                    # Obtém status detalhado da task para incluir informações de progresso
                                    try:
                                        service_status = ProcessoLegService(self.context, self.request)
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
                            _recent_tasks_cache.pop(cod_materia_str, None)
                    
                    # 2. Verifica tasks ativas no Celery usando serviço
                    try:
                        service = ProcessoLegService(self.context, self.request)
                        has_active_task, task_id, task_status = service.verificar_tasks_ativas(cod_materia_int)
                        if has_active_task:
                            logger.debug(f"[_get_pasta_data] Task ativa encontrada via serviço: {task_id}, status: {task_status}")
                    except Exception as task_check_err:
                        logger.debug(f"[_get_pasta_data] Erro ao verificar tasks ativas: {task_check_err}")
                    
                    # CRÍTICO: Se não há task ativa no Celery, limpa cache (task pode ter terminado)
                    if not has_active_task and cod_materia_str in _recent_tasks_cache:
                        _recent_tasks_cache.pop(cod_materia_str, None)
                    
                    # Se encontrou task ativa, verifica se os arquivos existem antes de retornar
                    # Se os arquivos foram apagados, invalida a task e cria nova
                    if has_active_task and task_id:
                        # CRÍTICO: Verifica se os arquivos existem mesmo com task ativa
                        # Se os arquivos foram apagados manualmente, a task pode estar rodando mas os arquivos não existem
                        from openlegis.sagl.browser.processo_leg.processo_leg_utils import secure_path_join
                        dir_hash = hashlib.md5(str(cod_materia_int).encode()).hexdigest()
                        prefix = f"processo_leg_integral_{dir_hash}"
                        install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
                        temp_base = os.path.abspath(os.path.join(install_home, 'var', 'tmp'))
                        dir_base = secure_path_join(temp_base, prefix)
                        metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                        
                        if not os.path.exists(metadados_path):
                            # Arquivos não existem - task pode estar rodando mas arquivos foram apagados
                            # Limpa cache de tasks
                            _recent_tasks_cache.pop(cod_materia_str, None)
                            # Limpa cache de documentos
                            _delete_cache_from_filesystem(cod_materia_int)
                            # Não retorna task existente - continua para criar nova task
                            has_active_task = False
                            task_id = None
                        else:
                            # Arquivos existem - retorna task ativa
                            _recent_tasks_cache[cod_materia_str] = (task_id, current_time)
                            # Limpa cache antigo (mantém apenas últimos 20)
                            if len(_recent_tasks_cache) > 20:
                                sorted_items = sorted(_recent_tasks_cache.items(), key=lambda x: x[1][1])
                                for key, _ in sorted_items[:-20]:
                                    _recent_tasks_cache.pop(key, None)
                            
                            # Obtém status detalhado da task para incluir informações de progresso
                            try:
                                service_status = ProcessoLegService(self.context, self.request)
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
                    from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                    dir_base = get_processo_dir(cod_materia_int)
                    
                    if not os.path.exists(dir_base):
                        # Diretório não existe - documentos foram apagados
                        # Limpa cache de tasks recentes
                        _recent_tasks_cache.pop(cod_materia_str, None)
                        # Limpa cache de documentos
                        _delete_cache_from_filesystem(cod_materia_int)
                        # Limpa cache de hash
                        _hash_cache.pop(cod_materia_str, None)
                        # Força criação de nova task (has_recent_task = False)
                        has_recent_task = False
                        cached_task_id = None
                    else:
                        # Diretório existe - verifica se há task recente no cache (pode ser polling após SUCCESS)
                        # Se houver task recente, não verifica assinatura (apenas verifica se arquivos existem)
                        # Se não houver task recente, verifica assinatura para decidir se precisa regenerar
                        has_recent_task = False
                        cached_task_id = None
                        if cod_materia_str in _recent_tasks_cache:
                            cached_task_id, cache_timestamp = _recent_tasks_cache[cod_materia_str]
                            time_since_cache = time.time() - cache_timestamp
                            # Se a task foi criada recentemente (dentro de 60 segundos), pode ser polling após SUCCESS
                            if time_since_cache < 60.0:
                                has_recent_task = True
                    
                    # CRÍTICO: Só verifica documentos prontos se há task recente (polling após SUCCESS)
                    # Se não há task recente (acesso inicial OU documentos apagados), pula verificação e vai direto criar task
                    if has_recent_task:
                        try:
                            # Usa serviço para obter documentos prontos
                            service = ProcessoLegService(self.context, self.request)
                            result = service.get_documentos_prontos(cod_materia, skip_signature_check=True)
                            
                            # CRÍTICO: Se retornou estrutura vazia, verifica se diretório existe
                            # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) == 0:
                                # Verifica se diretório existe
                                from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                                dir_base_check = get_processo_dir(cod_materia_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_materia_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem(cod_materia_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Continua para criar nova task (não retorna aqui)
                            
                            # Se encontrou documentos prontos, verifica se diretório ainda existe antes de retornar
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                # CRÍTICO: Verifica se diretório ainda existe antes de retornar documentos
                                # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                                dir_base_check = get_processo_dir(cod_materia_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_materia_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem(cod_materia_int)
                                    # Força criação de nova task
                                    has_recent_task = False
                                    cached_task_id = None
                                    # Continua para criar nova task (não retorna aqui)
                                else:
                                    # Diretório existe - verifica se documentos foram alterados usando documentos_metadados.json
                                    # CRÍTICO: Usa comparação com documentos_metadados.json
                                    has_changes_metadados, changes_details = _compare_documents_with_metadados(cod_materia_int, portal)
                                    
                                    if has_changes_metadados:
                                        # Mudanças detectadas - arquivos foram adicionados, removidos ou modificados
                                        # Limpa cache de tasks recentes
                                        _recent_tasks_cache.pop(cod_materia_str, None)
                                        # Limpa cache de documentos
                                        _delete_cache_from_filesystem(cod_materia_int)
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
                                        if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                            result_copy['paginas_geral'] = result_copy['total_paginas']
                                        if 'cod_materia' not in result_copy:
                                            result_copy['cod_materia'] = cod_materia_int
                                        
                                        # CRÍTICO: Calcula hash e tamanhos dos documentos e atualiza cache (apenas filesystem)
                                        documents_hash = _calculate_documents_hash(cod_materia_int, portal)
                                        documents_sizes = _calculate_documents_sizes(cod_materia_int, portal)
                                        _save_cache_to_filesystem(cod_materia_int, result_copy, current_time, documents_hash, documents_sizes)
                                        
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
                            service = ProcessoLegService(self.context, self.request)
                            result = service.get_documentos_prontos(cod_materia, skip_signature_check=True)
                            
                            # Se encontrou documentos prontos, retorna eles
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                # CRÍTICO: Documentos já existem, pula monitor e mostra apenas carregamento
                                result['async'] = False
                                result['task_id'] = None
                                result['message'] = 'Carregando documentos...'
                                
                                # Garante campos obrigatórios
                                if 'paginas_geral' not in result and 'total_paginas' in result:
                                    result['paginas_geral'] = result['total_paginas']
                                if 'cod_materia' not in result:
                                    result['cod_materia'] = cod_materia_int
                                
                                return result
                            else:
                                # CRÍTICO: Se retornou estrutura vazia, verifica se diretório existe
                                # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                                dir_base_check = get_processo_dir(cod_materia_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_materia_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem(cod_materia_int)
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
                                    service = ProcessoLegService(self.context, self.request)
                                    result = service.get_documentos_prontos(cod_materia, skip_signature_check=True)
                                    
                                    # CRÍTICO: Se retornou estrutura vazia, verifica se diretório existe
                                    # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                    if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) == 0:
                                        # Verifica se diretório existe
                                        from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                                        dir_base_check = get_processo_dir(cod_materia_int)
                                        if not os.path.exists(dir_base_check):
                                            # Diretório não existe - documentos foram apagados
                                            # Limpa cache de tasks recentes
                                            _recent_tasks_cache.pop(cod_materia_str, None)
                                            # Limpa cache de documentos (filesystem)
                                            _delete_cache_from_filesystem(cod_materia_int)
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
                                        
                                        if 'paginas_geral' not in result and 'total_paginas' in result:
                                            result['paginas_geral'] = result['total_paginas']
                                        if 'cod_materia' not in result:
                                            result['cod_materia'] = cod_materia_int
                                        
                                        return result
                                except Exception as retry_err:
                                    logger.warning(f"[_get_pasta_data] Erro no retry: {retry_err}")
                                
                                # CRÍTICO: Antes de retornar status de processamento, verifica se diretório existe
                                # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                                from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                                dir_base_check = get_processo_dir(cod_materia_int)
                                if not os.path.exists(dir_base_check):
                                    # Diretório não existe - documentos foram apagados
                                    # Limpa cache de tasks recentes
                                    _recent_tasks_cache.pop(cod_materia_str, None)
                                    # Limpa cache de documentos
                                    _delete_cache_from_filesystem(cod_materia_int)
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
                        # Primeiro, verifica o cache de documentos prontos (memória e filesystem)
                        cached_data = None
                        # Cache em memória removido - usa apenas filesystem
                        cached_data = None
                        if False:  # Nunca entra aqui - cache em memória removido
                            pass
                        else:
                            # Tenta carregar do filesystem (único cache agora)
                            cached_data = _load_cache_from_filesystem(cod_materia_int)
                            if cached_data:
                                logger.debug(f"[_get_pasta_data] Cache carregado do filesystem para {cod_materia_str}")
                        
                        if cached_data:
                            # Formato: (documentos_data, timestamp, documents_hash, documents_sizes) ou versões antigas para compatibilidade
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
                                # Verifica se os documentos mudaram comparando o hash
                                current_hash = _calculate_documents_hash(cod_materia_int, portal)
                                
                                
                                # Se não há hash no cache (cache antigo) ou não foi possível calcular hash atual,
                                # não usa o cache - verifica documentos no sistema para garantir dados atualizados
                                if cached_hash is None or current_hash is None:
                                    # Cache antigo sem hash ou não foi possível calcular hash atual
                                    _delete_cache_from_filesystem(cod_materia_int)
                                elif current_hash != cached_hash:
                                    # Hash mudou - documentos foram modificados, excluídos ou adicionados
                                    _delete_cache_from_filesystem(cod_materia_int)
                                else:
                                    # Hash válido e igual - verifica se os arquivos ainda existem no filesystem
                                    # Se os arquivos foram apagados do filesystem, força regeneração mesmo com hash igual
                                    
                                    # Calcula o diretório base (mesma lógica do processo_leg.py)
                                    install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
                                    hash_materia = hashlib.md5(str(cod_materia_int).encode()).hexdigest()
                                    dir_base = os.path.join(install_home, f'var/tmp/processo_leg_integral_{hash_materia}')
                                    metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                                    
                                    # Verifica se os arquivos existem no filesystem
                                    if not os.path.exists(metadados_path):
                                        _delete_cache_from_filesystem(cod_materia_int)
                                        # CRÍTICO: Não retorna do cache - continua para criar nova task e mostrar monitor
                                        # Não entra no else abaixo, vai direto para criar task
                                    else:
                                        # Hash válido e arquivos existem - verifica se documentos foram alterados usando documentos_metadados.json
                                        # CRÍTICO: Usa comparação com documentos_metadados.json
                                        has_changes_metadados, changes_details = _compare_documents_with_metadados(cod_materia_int, portal)
                                        
                                        if has_changes_metadados:
                                            # Mudanças detectadas - arquivos foram adicionados, removidos ou modificados
                                            _delete_cache_from_filesystem(cod_materia_int)
                                            # Limpa cache de tasks recentes para forçar criação de nova task
                                            _recent_tasks_cache.pop(cod_materia_str, None)
                                            # Não retorna do cache - continua para criar nova task
                                            # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                            has_recent_task = False
                                            cached_task_id = None
                                            # Não cria result_copy - continua para criar nova task
                                        else:
                                            # Hash válido e comparação com metadados corresponde - cache ainda é válido
                                            documentos_count_cached = len(cached_docs.get('documentos', [])) if isinstance(cached_docs, dict) else 0
                                            # Cria result_copy - comparação com metadados passou
                                            result_copy = copy.deepcopy(cached_docs)
            
                                            # Só processa result_copy se foi criado (tamanhos não mudaram ou não há cache para comparar)
                                            if result_copy is not None:
                                                # CRÍTICO: Verifica se há task recente no cache para mostrar monitor
                                                # Se houver task recente (dentro de 60 segundos), mostra monitor com status SUCCESS
                                                has_recent_task_for_monitor = False
                                                task_id_for_monitor = None
                                                if cod_materia_str in _recent_tasks_cache:
                                                    cached_task_id_check, cache_timestamp_check = _recent_tasks_cache[cod_materia_str]
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
                                                
                                                if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                                    result_copy['paginas_geral'] = result_copy['total_paginas']
                                                if 'cod_materia' not in result_copy:
                                                    result_copy['cod_materia'] = cod_materia_int
                                                
                                                return result_copy
                            else:
                                # Cache expirado, remove (filesystem)
                                _delete_cache_from_filesystem(cod_materia_int)
                        
                        # Cache não encontrado ou expirado, verifica documentos no sistema
                        try:
                            # Usa serviço para obter documentos prontos
                            service = ProcessoLegService(self.context, self.request)
                            result = service.get_documentos_prontos(cod_materia, skip_signature_check=True)
                            
                            # Se encontrou documentos prontos, verifica hash ANTES de retornar
                            if isinstance(result, dict) and 'documentos' in result and len(result.get('documentos', [])) > 0:
                                documentos_count = len(result.get('documentos', []))
                                
                                # CRÍTICO: Calcula hash dos documentos ATUAIS antes de retornar
                                current_documents_hash = _calculate_documents_hash(cod_materia_int, portal)
                                
                                # Verifica se há hash em cache para comparar
                                should_return_documents = True
                                
                                # CRÍTICO: Só compara quantidade/tamanhos se HÁ CACHE no filesystem
                                # Se não há cache (primeira geração), aceita os documentos encontrados
                                cached_data_check = _load_cache_from_filesystem(cod_materia_int)
                                
                                # CRÍTICO: Compara usando documentos_metadados.json (única fonte de verdade)
                                # Se JSON não existe ou há diferenças, precisa regenerar
                                has_changes_metadados, changes_details = _compare_documents_with_metadados(cod_materia_int, portal)
                                
                                if has_changes_metadados:
                                    # Mudanças detectadas ou JSON não existe - precisa regenerar
                                    
                                    # Verifica se há task ativa antes de criar nova task (evita criar tasks duplicadas)
                                    try:
                                        service_check = ProcessoLegService(self.context, self.request)
                                        has_active_task_check, task_id_check, task_status_check = service_check.verificar_tasks_ativas(cod_materia_int)
                                        if has_active_task_check:
                                            # Não cria nova task - aguarda task atual completar
                                            should_return_documents = False
                                            has_recent_task = True
                                            cached_task_id = task_id_check
                                            # Não limpa cache - mantém task ativa
                                        else:
                                            # Limpa cache de tasks recentes para forçar criação de nova task
                                            _recent_tasks_cache.pop(cod_materia_str, None)
                                            # Limpa cache de documentos
                                            _delete_cache_from_filesystem(cod_materia_int)
                                            should_return_documents = False
                                            # CRÍTICO: Força has_recent_task = False para garantir criação de nova task
                                            has_recent_task = False
                                            cached_task_id = None
                                    except Exception as check_task_err:
                                        logger.warning(f"[_get_pasta_data] Erro ao verificar tasks ativas: {check_task_err}, assumindo que precisa criar nova task")
                                        # Em caso de erro, assume que precisa criar nova task
                                        _recent_tasks_cache.pop(cod_materia_str, None)
                                        _delete_cache_from_filesystem(cod_materia_int)
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
                                    if cod_materia_str in _recent_tasks_cache:
                                        cached_task_id_check, cache_timestamp_check = _recent_tasks_cache[cod_materia_str]
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
                                    if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                        result_copy['paginas_geral'] = result_copy['total_paginas']
                                    if 'cod_materia' not in result_copy:
                                        result_copy['cod_materia'] = cod_materia_int
                                    
                                    # CRÍTICO: Atualiza cache com hash e tamanhos calculados (apenas filesystem)
                                    documents_sizes = _calculate_documents_sizes(cod_materia_int, portal)
                                    _save_cache_to_filesystem(cod_materia_int, result_copy, current_time, current_documents_hash, documents_sizes)
                                    
                                    return result_copy
                                else:
                                    # Documentos prontos não correspondem (quantidade, hash ou tamanhos), não retorna - continua para criar nova task
                                    # Nota: should_return_documents = False pode ter sido definido por:
                                    # - Quantidade não corresponde (linha 1992)
                                    # - Hash mudou (linha 2015)
                                    # - Tamanhos mudaram (linha 2047)
                                    # Limpa cache de tasks recentes para forçar criação de nova task
                                    _recent_tasks_cache.pop(cod_materia_str, None)
                                    # Limpa cache de documentos (já foi limpo antes, mas garantindo)
                                    _delete_cache_from_filesystem(cod_materia_int)
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
                            from openlegis.sagl.browser.processo_leg.processo_leg_utils import secure_path_join
                            dir_hash = hashlib.md5(str(cod_materia_int).encode()).hexdigest()
                            prefix = f"processo_leg_integral_{dir_hash}"
                            install_home = os.environ.get('INSTALL_HOME', '/var/openlegis/SAGL6')
                            temp_base = os.path.abspath(os.path.join(install_home, 'var', 'tmp'))
                            dir_base = secure_path_join(temp_base, prefix)
                            
                            # SEMPRE apaga o diretório se existir para forçar regeneração
                            if os.path.exists(dir_base):
                                shutil.rmtree(dir_base, ignore_errors=True)
                            
                            # CRÍTICO: Invalida cache de documentos prontos ao iniciar nova geração (filesystem)
                            _delete_cache_from_filesystem(cod_materia_int)
                        except Exception as cleanup_err:
                            logger.warning(f"[_get_pasta_data] Erro ao apagar diretório (continuando mesmo assim): {cleanup_err}")
                        
                        # SEMPRE inicia nova geração
                        
                        # CRÍTICO: Usa lock por cod_materia para evitar criação simultânea
                        with _locks_lock:
                            if cod_materia_str not in _task_creation_locks:
                                _task_creation_locks[cod_materia_str] = threading.Lock()
                            task_lock = _task_creation_locks[cod_materia_str]
                        
                        # Adquire o lock para este cod_materia
                        with task_lock:
                            # CRÍTICO: Verifica se diretório existe antes do double-check
                            # Se diretório não existe, documentos foram apagados - limpa cache e cria nova task
                            from openlegis.sagl.browser.processo_leg.processo_leg_utils import get_processo_dir
                            dir_base_double_check = get_processo_dir(cod_materia_int)
                            if not os.path.exists(dir_base_double_check):
                                # Diretório não existe - documentos foram apagados
                                # Limpa cache de tasks recentes
                                _recent_tasks_cache.pop(cod_materia_str, None)
                                # Limpa cache de documentos (filesystem)
                                _delete_cache_from_filesystem(cod_materia_int)
                                # Continua para criar nova task (não retorna aqui)
                            else:
                                # Diretório existe - verifica novamente após adquirir o lock (double-check)
                                if cod_materia_str in _recent_tasks_cache:
                                    cached_task_id, cache_timestamp = _recent_tasks_cache[cod_materia_str]
                                    if time.time() - cache_timestamp < cache_ttl:
                                        logger.debug(f"[_get_pasta_data] Task foi criada por outra thread enquanto aguardava lock: {cached_task_id}")
                                        # Obtém status detalhado da task para incluir informações de progresso
                                        try:
                                            service_status = ProcessoLegService(self.context, self.request)
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
                            service = ProcessoLegService(self.context, self.request)
                            result = service.criar_task_async(cod_materia_int, portal_url)
                            
                            if result and isinstance(result, dict) and 'task_id' in result:
                                new_task_id = str(result.get('task_id'))
                                # CRÍTICO: Adiciona ao cache imediatamente para evitar race condition
                                _recent_tasks_cache[cod_materia_str] = (new_task_id, time.time())
                                # Limpa cache antigo (mantém apenas últimos 20)
                                if len(_recent_tasks_cache) > 20:
                                    sorted_items = sorted(_recent_tasks_cache.items(), key=lambda x: x[1][1])
                                    for key, _ in sorted_items[:-20]:
                                        _recent_tasks_cache.pop(key, None)
                                
                                
                                # CRÍTICO: Primeiro verifica status da task para obter informações de progresso
                                # Se task está em PROGRESS, retorna status PROGRESS com informações de progresso
                                try:
                                    service_status = ProcessoLegService(self.context, self.request)
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
                                    check_result = service.get_documentos_prontos(cod_materia, skip_signature_check=True)
                                    
                                    if isinstance(check_result, dict) and 'documentos' in check_result and len(check_result.get('documentos', [])) > 0:
                                        # Documentos prontos encontrados! Mas verifica status real da task primeiro
                                        # CRÍTICO: Verifica status real da task para garantir que não retornamos SUCCESS prematuramente
                                        try:
                                            service_status = ProcessoLegService(self.context, self.request)
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
                                                    if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                                        result_copy['paginas_geral'] = result_copy['total_paginas']
                                                    if 'cod_materia' not in result_copy:
                                                        result_copy['cod_materia'] = cod_materia_int
                                                    return result_copy
                                                # Se task realmente completou (SUCCESS), retorna SUCCESS
                                                elif task_real_status == 'SUCCESS':
                                                    result_copy = copy.deepcopy(check_result)
                                                    result_copy['async'] = True
                                                    result_copy['task_id'] = new_task_id
                                                    result_copy['status'] = 'SUCCESS'
                                                    result_copy['message'] = 'Pasta digital gerada com sucesso'
                                                    if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                                        result_copy['paginas_geral'] = result_copy['total_paginas']
                                                    if 'cod_materia' not in result_copy:
                                                        result_copy['cod_materia'] = cod_materia_int
                                                    documents_hash = _calculate_documents_hash(cod_materia_int, portal)
                                                    documents_sizes = _calculate_documents_sizes(cod_materia_int, portal)
                                                    _save_cache_to_filesystem(cod_materia_int, result_copy, time.time(), documents_hash, documents_sizes)
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
                                        if 'paginas_geral' not in result_copy and 'total_paginas' in result_copy:
                                            result_copy['paginas_geral'] = result_copy['total_paginas']
                                        if 'cod_materia' not in result_copy:
                                            result_copy['cod_materia'] = cod_materia_int
                                        documents_hash = _calculate_documents_hash(cod_materia_int, portal)
                                        documents_sizes = _calculate_documents_sizes(cod_materia_int, portal)
                                        _save_cache_to_filesystem(cod_materia_int, result_copy, time.time(), documents_hash, documents_sizes)
                                        return result_copy
                                except Exception as check_err:
                                    logger.warning(f"[_get_pasta_data] Erro ao verificar documentos prontos após criar task: {check_err}", exc_info=True)
                                
                                # Se não encontrou documentos prontos, retorna status PENDING com monitor ativo
                                # Obtém status detalhado da task para incluir informações de progresso
                                try:
                                    service_status = ProcessoLegService(self.context, self.request)
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
            else:
                try:
                    # Usa serviço para obter documentos (modo síncrono)
                    service = ProcessoLegService(self.context, self.request)
                    result = service.get_documentos_prontos(cod_materia, skip_signature_check=False)
                    
                    # Processa resultado
                    if isinstance(result, dict):
                        result['async'] = False
                        result['message'] = 'Processamento síncrono concluído'
                        # Garante campos obrigatórios
                        if 'paginas_geral' not in result and 'total_paginas' in result:
                            result['paginas_geral'] = result['total_paginas']
                        if 'cod_materia' not in result:
                            result['cod_materia'] = cod_materia
                        
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
            # Retorna pelo menos um objeto válido
            return {
                'async': True,
                'error': str(e),
                'documentos': [],
                'cod_materia': cod_materia,
                'paginas_geral': 0,
                'message': 'Erro ao processar pasta digital'
            }





class PastaDigitalView(PastaDigitalMixin, grok.View):
    """View que renderiza o HTML da pasta digital diretamente"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pasta_digital')

    def update(self):
        """Método update do Grok - garante que headers sejam definidos"""
        # Define headers ANTES de qualquer processamento
        self.request.RESPONSE.setHeader('Content-Type', 'text/html; charset=utf-8')
        # Evita cache para garantir que sempre use a versão mais recente
        self.request.RESPONSE.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.request.RESPONSE.setHeader('Pragma', 'no-cache')
        self.request.RESPONSE.setHeader('Expires', '0')

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
        # setBody() substitui todo o conteúdo da resposta
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
            cod_materia = self.request.form.get('cod_materia') or self.request.get('cod_materia')
            action = self.request.form.get('action', 'pasta')
            
            if not cod_materia:
                return self._render_error('Parâmetro cod_materia é obrigatório')
            
            # Obtém todos os dados
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            tool = getToolByName(self.context, 'portal_sagl')
            
            materia_data = self._get_materia_data(cod_materia)
            pasta_data = self._get_pasta_data(cod_materia, action, tool, portal)
            # Garante que pasta_data nunca seja None
            if pasta_data is None:
                pasta_data = {
                    'error': 'Erro ao obter dados da pasta',
                    'async': False,
                    'documentos': []
                }
            portal_config = self._get_portal_config(portal)
            materias_relacionadas = self._get_materias_relacionadas(cod_materia, portal)
            documentos_adm = self._get_documentos_administrativos(cod_materia, portal)
            normas = self._get_normas_juridicas(cod_materia, portal)
            
            # Log removido - apenas logs de erro são mantidos
            
            # Renderiza HTML com os dados
            html_result = self._render_html(
                cod_materia, action, materia_data, pasta_data, 
                portal_config, materias_relacionadas, documentos_adm, 
                normas, str(portal.absolute_url())
            )
            
            # VALIDAÇÃO FINAL SIMPLIFICADA E DIRETA
            # Remove completamente as validações antigas e problemáticas
            # e substitui por uma verificação/correção direta
            if isinstance(html_result, str):
                # VERIFICAÇÃO DIRETA E SIMPLES
                # 1. Procura por "pasta":null (com ou sem espaço)
                pasta_null_found = False
                
                # Verifica forma 1: "pasta":null
                if '"pasta":null' in html_result:
                    pasta_null_found = True
                    logger.warning(f"[render] Encontrado 'pasta':null, corrigindo...")
                    html_result = html_result.replace('"pasta":null', '"pasta":{}')
                
                # Verifica forma 2: "pasta": null
                if '"pasta": null' in html_result:
                    pasta_null_found = True
                    logger.warning(f"[render] Encontrado 'pasta': null, corrigindo...")
                    html_result = html_result.replace('"pasta": null', '"pasta": {}')
                
                # Log removido - apenas logs de erro são mantidos
            
            # Retorna o HTML diretamente - Grok vai processar corretamente com Content-Type definido
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

    def _render_html(self, cod_materia, action, materia, pasta, portal_config, 
                    materias_relacionadas, documentos_adm, normas, portal_url):
        """Renderiza o HTML completo da pasta digital"""
        import json
        
        # Garante que cod_materia e portal_url são strings válidas
        cod_materia_str = str(cod_materia).strip() if cod_materia else ''
        portal_url_str = str(portal_url).strip() if portal_url else ''
        
        # Log para debug - reduzido para melhor performance
        logger.debug(f"[_render_html] Dados recebidos: cod_materia={cod_materia_str}, action={action}")
        if isinstance(pasta, dict):
            logger.debug(f"  pasta keys: {list(pasta.keys())}, documentos: {len(pasta.get('documentos', []))}")
        
        # GARANTIA ABSOLUTA: pasta nunca é None/null
        if pasta is None:
            logger.warning(f"[_render_html] pasta is None, FORÇANDO dict vazio")
            pasta = {}
        elif not isinstance(pasta, dict):
            logger.warning(f"[_render_html] pasta não é dict ({type(pasta)}), convertendo para dict")
            pasta = {}
        
        # Garante que todos os valores None sejam convertidos para valores válidos
        data_dict = {
            'cod_materia': cod_materia_str,
            'action': str(action) if action else 'pasta',
            'materia': materia if materia is not None else {},
            'pasta': pasta,  # Já garantido que é um dict válido
            'portal_config': portal_config if portal_config is not None else {},
            'materias_relacionadas': materias_relacionadas if materias_relacionadas is not None else {},
            'documentos_administrativos': documentos_adm if documentos_adm is not None else [],
            'normas_juridicas': normas if normas is not None else [],
            'portal_url': portal_url_str
        }
        
        # Serializa o JSON com encoder customizado para objetos date/datetime
        data_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder)
        
        # VALIDAÇÃO CRÍTICA ANTES DE INJETAR (logs reduzidos)
        logger.debug(f"[_render_html] JSON serializado: {len(data_json)} caracteres")
        
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
        
        # Verifica se pasta é um objeto (CORRIGIDO: inclui espaço DEPOIS dos dois pontos)
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
        
        # Se encontrou pasta:null, CORRIGE IMEDIATAMENTE
        if pasta_found_as_null and not pasta_is_object:
            logger.error(f"[_render_html] ERRO CRÍTICO: JSON contém pasta:null!")
            
            # DEBUG: Mostra contexto em torno de "pasta"
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
                data_json = json.dumps(data_dict, ensure_ascii=False, cls=DateTimeJSONEncoder)
            
            # Validação pós-correção (CORRIGIDO: inclui espaço DEPOIS dos dois pontos)
            pasta_found_as_null_after = any(variation in data_json for variation in pasta_null_variations)
            
            if pasta_found_as_null_after:
                logger.error(f"[_render_html] ERRO PERSISTENTE: pasta ainda é null após todas as correções!")
                # Último recurso: substitui brutalmente
                data_json = data_json.replace('"pasta":null', '"pasta":{}')
                data_json = data_json.replace('"pasta": null', '"pasta":{}')
                data_json = data_json.replace("'pasta':null", "'pasta':{}")
                data_json = data_json.replace("'pasta': null", "'pasta':{}")
        
        # Lê o template HTML e injeta os dados
        # O template está em src/openlegis.sagl/openlegis/sagl/skins/consultas/materia/pasta_digital/index_html.html
        import pkg_resources
        try:
            # Tenta obter o caminho do pacote
            dist = pkg_resources.get_distribution('openlegis.sagl')
            template_path = os.path.join(
                dist.location, 'openlegis', 'sagl', 'skins', 'consultas', 'materia',
                'pasta_digital', 'index_html.html'
            )
            
            # Se não encontrar, tenta caminho relativo
            if not os.path.exists(template_path):
                template_path = os.path.join(
                    os.path.dirname(__file__),
                    '..', '..', 'skins', 'consultas', 'materia',
                    'pasta_digital', 'index_html.html'
                )
            
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
            
            # Preenche os links vazios de favicon e CSS
            if portal_url_str:
                # Favicon - usa logo_casa.gif se disponível, senão brasao.gif
                # Baseado no portal_config que já foi obtido
                favicon_filename = 'logo_casa.gif'
                if portal_config and portal_config.get('id_logo'):
                    favicon_filename = portal_config.get('id_logo', 'logo_casa.gif')
                
                favicon_url = f"{portal_url_str}/sapl_documentos/props_sagl/{favicon_filename}"
                
                # Preenche o link do favicon
                html = html.replace('<link rel="shortcut icon" type="image/x-icon" href="" id="favicon">', 
                                  f'<link rel="shortcut icon" type="image/x-icon" href="{favicon_url}" id="favicon">')
                
                # CSS - Preenche diretamente no servidor para evitar FOUC (Flash of Unstyled Content)
                # Os CSS devem ser carregados antes da renderização da página
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
            
            # PROCURA POR 'let APP_DATA = {' - MAIS ROBUSTO
            
            # Lista de padrões possíveis
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
                    logger.debug(f"[_render_html] Encontrado padrão: '{pattern}' na posição {start_idx}")
                    break
            
            if start_idx == -1:
                logger.warning("[_render_html] Nenhum padrão APP_DATA encontrado no template!")
                # Fallback: injeta no início do primeiro script
                script_start = html.find('<script>')
                if script_start != -1:
                    script_end = html.find('</script>', script_start)
                    if script_end != -1:
                        # Injeta APP_DATA no início do script
                        injected_code = f'let APP_DATA = {data_json}; // Dados injetados pelo servidor\n        '
                        html = html[:script_start + 8] + injected_code + html[script_start + 8:]
                        logger.debug("[_render_html] APP_DATA injetado no início do primeiro script")
                    else:
                        logger.error("[_render_html] Não foi possível encontrar fechamento </script>")
                else:
                    logger.error("[_render_html] Não foi possível encontrar tag <script> no template")
            else:
                # Encontra o fechamento correspondente
                brace_count = 0
                in_string = False
                escape_next = False
                string_char = None
                end_idx = -1
                
                # Posição inicial para começar a contar (após a abertura {)
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
                            # Procura ponto e vírgula opcional
                            while end_idx < len(html) and html[end_idx] in ' \n\t\r':
                                end_idx += 1
                            if end_idx < len(html) and html[end_idx] == ';':
                                end_idx += 1
                            break
                        brace_count -= 1
                
                if end_idx > start_idx:
                    # INJEÇÃO SEGURA - garante que pasta não é null
                    safe_data_json = data_json
                    
                    # Substitui no HTML
                    injected_code = f'let APP_DATA = {safe_data_json}; // Dados injetados pelo servidor'
                    html_new = html[:start_idx] + injected_code + html[end_idx:]
                    
                    # VALIDAÇÃO PÓS-INJEÇÃO - CRÍTICA (logs reduzidos)
                    # Verifica se pasta é null no trecho INJETADO
                    injected_segment = injected_code
                    pasta_is_null_injected = any(variation in injected_segment for variation in pasta_null_variations)
                    
                    if pasta_is_null_injected:
                        logger.error(f"[_render_html] ERRO: pasta:null no trecho injetado!")
                        # Tenta corrigir no HTML
                        for variation in pasta_null_variations:
                            if variation in html_new:
                                replacement = variation.split(':')[0] + ':{}'
                                html_new = html_new.replace(variation, replacement)
                    
                    # Aplica a substituição
                    html = html_new
                    logger.debug(f"[_render_html] Injeção aplicada (substituído de {start_idx} até {end_idx})")
                    
                else:
                    logger.warning("[_render_html] Não foi possível encontrar fechamento de APP_DATA")
                    # Fallback simples
                    html = html.replace(pattern_found, f'let APP_DATA = {data_json};', 1)
            
            # VALIDAÇÃO FINAL ABSOLUTA (logs reduzidos)
            # Verifica se há pasta:null no HTML final
            for variation in pasta_null_variations[:4]:  # Apenas variações com aspas duplas
                if variation in html:
                    logger.error(f"[_render_html] ENCONTRADO {variation} no HTML final, corrigindo...")
                    replacement = variation.split(':')[0] + ':{}'
                    html = html.replace(variation, replacement)
            
            return html
        except Exception as e:
            logger.error(f"Erro ao ler template HTML: {e}", exc_info=True)
            # Garante que o JSON não tenha pasta:null no fallback
            safe_data_json = data_json
            # Define variações de pasta:null para correção
            pasta_null_variations_fallback = [
                '"pasta":null',
                '"pasta": null', 
                '"pasta" :null',
                '"pasta" : null',
                "'pasta':null",
                "'pasta': null",
                'pasta:null',
                'pasta: null'
            ]
            for variation in pasta_null_variations_fallback:
                if variation in safe_data_json:
                    replacement = variation.split(':')[0] + ':{}'
                    safe_data_json = safe_data_json.replace(variation, replacement)
            # Fallback: retorna HTML básico com dados JSON
            return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <title>Pasta Digital - {materia.get('titulo', cod_materia) if isinstance(materia, dict) and materia else cod_materia}</title>
</head>
<body>
    <h1>Pasta Digital</h1>
    <script>
        let APP_DATA = {safe_data_json};
        console.log('Dados carregados:', APP_DATA);
    </script>
    <p>Carregando...</p>
</body>
    </html>"""



    # Métodos auxiliares compartilhados (copiados de PastaDigitalDataView)


class PastaDigitalDataView(PastaDigitalMixin, grok.View):
    """View que retorna JSON com todos os dados necessários para a página de pasta digital"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pasta_digital_data')

    def render(self):
        """Retorna JSON com dados da pasta digital"""
        self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
        
        try:
            cod_materia = self.request.form.get('cod_materia') or self.request.get('cod_materia')
            action = self.request.form.get('action', 'pasta')
            
            if not cod_materia:
                return json.dumps({
                    'error': 'Parâmetro cod_materia é obrigatório',
                    'success': False
                }, cls=DateTimeJSONEncoder)
            
            # Obtém informações básicas
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            tool = getToolByName(self.context, 'portal_sagl')
            
            # Obtém dados da matéria
            materia_data = self._get_materia_data(cod_materia)
            
            # Obtém dados da pasta digital
            logger.debug(f"[_get_pasta_data_json] Chamando _get_pasta_data para cod_materia={cod_materia}, action={action}")
            pasta_data = self._get_pasta_data(cod_materia, action, tool, portal)
            logger.debug(f"[_get_pasta_data_json] _get_pasta_data retornou: type={type(pasta_data)}, id={id(pasta_data) if pasta_data else 'None'}")
            
            # Log detalhado do pasta_data retornado
            if isinstance(pasta_data, dict):
                # Verifica se lista de documentos está vazia quando não deveria estar
                if 'documentos' in pasta_data:
                    documentos = pasta_data['documentos']
                    if isinstance(documentos, list) and len(documentos) == 0:
                        # Verifica se é esperado (task ativa ou regeneração em andamento)
                        is_expected_empty = (
                            pasta_data.get('async') is True and 
                            pasta_data.get('task_id') and 
                            pasta_data.get('status') in ('PENDING', 'PROGRESS')
                        )
                        if not is_expected_empty:
                            logger.warning(f"[_get_pasta_data_json] ATENÇÃO: Lista de documentos está vazia quando não deveria estar! task_id={pasta_data.get('task_id')}, status={pasta_data.get('status')}")
                else:
                    logger.warning(f"[_get_pasta_data_json] ATENÇÃO: Chave 'documentos' não encontrada em pasta_data!")
            
            # Obtém configurações do portal
            portal_config = self._get_portal_config(portal)
            
            # Obtém matérias relacionadas
            materias_relacionadas = self._get_materias_relacionadas(cod_materia, portal)
            
            # Obtém documentos administrativos
            documentos_adm = self._get_documentos_administrativos(cod_materia, portal)
            
            # Obtém normas jurídicas
            normas = self._get_normas_juridicas(cod_materia, portal)
            
            # Monta resposta
            response = {
                'success': True,
                'cod_materia': cod_materia,
                'action': action,
                'materia': materia_data,
                'pasta': pasta_data,
                'portal_config': portal_config,
                'materias_relacionadas': materias_relacionadas,
                'documentos_administrativos': documentos_adm,
                'normas_juridicas': normas,
                'portal_url': str(portal.absolute_url())
            }
            
            return json.dumps(response, ensure_ascii=False, cls=DateTimeJSONEncoder)
            
        except Exception as e:
            logger.error(f"Erro ao obter dados da pasta digital: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return json.dumps({
                'error': str(e),
                'success': False
            }, ensure_ascii=False, cls=DateTimeJSONEncoder)


class ProcessoLegDownloadDocumentoView(PastaDigitalMixin, grok.View):
    """View para download de documentos individuais da pasta digital legislativa"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_download_documento')
    
    def render(self):
        try:
            # Extrai parâmetros
            cod_materia_str = self.request.form.get('cod_materia') or self.request.get('cod_materia')
            filename = self.request.form.get('file') or self.request.get('file')
            
            if not cod_materia_str or not filename:
                self.request.response.setStatus(400)
                return "Parâmetros cod_materia e file são obrigatórios"
            
            # Valida filename (segurança - evita path traversal)
            if '..' in filename or '/' in filename or '\\' in filename:
                self.request.response.setStatus(400)
                return "Nome de arquivo inválido"
            
            cod_materia_int = int(cod_materia_str)
            
            # IMPORTANTE: Busca sempre no filesystem (diretório da pasta digital)
            # Se o usuário conseguiu abrir a pasta digital, já tem permissão adequada
            # Todos os arquivos da pasta digital são copiados para o diretório durante a geração
            
            file_content = self._get_file_from_pasta_dir(cod_materia_int, filename)
            
            if file_content is None:
                self.request.response.setStatus(404)
                return "Arquivo não encontrado"
            
            # Define headers de resposta
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
            return "Parâmetro cod_materia inválido"
        except Exception as e:
            logger.error(f"[processo_leg_download_documento] Erro: {e}", exc_info=True)
            self.request.response.setStatus(500)
            return f"Erro ao baixar documento: {str(e)}"
    
    def _get_file_from_pasta_dir(self, cod_materia, filename):
        """
        Obtém arquivo do diretório da pasta digital no filesystem.
        
        IMPORTANTE: O 'filename' vem do campo 'file' do cache.json, que contém
        o nome do arquivo original (ex: "capa_PL-123-2025.pdf", "79431_texto_integral.pdf").
        
        Esses arquivos são copiados para o diretório pasta_digital/{cod_materia}/ durante a geração.
        """
        try:
            dir_base = get_processo_dir(cod_materia)
            
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
                    file_content = self._get_capa_dinamica(cod_materia, filename, dir_base)
                    if file_content:
                        return file_content
                
                # Se não encontrou, tenta buscar o arquivo original no ZODB e salvar no diretório
                # Isso permite que arquivos sejam baixados mesmo se não foram copiados durante a geração
                logger.debug(f"[_get_file_from_pasta_dir] Tentando buscar arquivo original no ZODB: {filename}")
                file_content = self._get_file_from_zodb_and_save(cod_materia, filename, dir_base)
                if file_content:
                    return file_content
                
                return None
            
            # Lê arquivo do filesystem
            with open(file_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"[_get_file_from_pasta_dir] Erro ao obter {filename} do diretório: {e}", exc_info=True)
            return None
    
    def _get_file_from_zodb_and_save(self, cod_materia, filename, dir_base):
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
            
            # Matéria principal - texto integral
            if filename.endswith('_texto_integral.pdf'):
                if hasattr(portal.sapl_documentos, 'materia'):
                    container = portal.sapl_documentos.materia
            # Emendas
            elif '_emenda_' in filename or filename.endswith('_emenda.pdf'):
                if hasattr(portal.sapl_documentos, 'emenda'):
                    container = portal.sapl_documentos.emenda
            # Substitutivos
            elif '_substitutivo_' in filename or filename.endswith('_substitutivo.pdf'):
                if hasattr(portal.sapl_documentos, 'substitutivo'):
                    container = portal.sapl_documentos.substitutivo
            # Relatorias
            elif '_relatoria_' in filename or filename.endswith('_relatoria.pdf'):
                if hasattr(portal.sapl_documentos, 'relatoria'):
                    container = portal.sapl_documentos.relatoria
            # Documentos acessórios
            elif '_acessorio_' in filename or filename.endswith('_acessorio.pdf'):
                if hasattr(portal.sapl_documentos, 'materia') and hasattr(portal.sapl_documentos.materia, 'documento_acessorio'):
                    container = portal.sapl_documentos.materia.documento_acessorio
            # Tramitações
            elif '_tram.pdf' in filename or filename.endswith('_tramitacao.pdf'):
                if hasattr(portal.sapl_documentos, 'materia') and hasattr(portal.sapl_documentos.materia, 'tramitacao'):
                    container = portal.sapl_documentos.materia.tramitacao
            # Capa
            elif filename.startswith('capa_'):
                # Capa é gerada dinamicamente, não está no ZODB
                return None
            
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
    
    def _get_capa_dinamica(self, cod_materia, filename, dir_base):
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
            capa_url = f"{base_url}/modelo_proposicao/capa_processo?cod_materia={cod_materia}"
            
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
                        logger.info(f"[_get_capa_dinamica] Capa gerada e salva: {filename}")
                    except Exception as save_err:
                        logger.warning(f"[_get_capa_dinamica] Erro ao salvar capa: {save_err}")
                    
                    return file_content
            
            return None
            
        except Exception as e:
            logger.error(f"[_get_capa_dinamica] Erro ao gerar capa dinamicamente: {e}", exc_info=True)
            return None
