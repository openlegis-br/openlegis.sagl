# -*- coding: utf-8 -*-
"""Views Grok para tramitação unificada"""

from grokcore.component import context
from grokcore.view import View as GrokView, name
from grokcore.security import require
from zope.interface import Interface
from sqlalchemy import select, case, func, or_, and_
from sqlalchemy.orm import selectinload
from openlegis.sagl.models.models import (
    Tramitacao, TramitacaoAdministrativo, UnidadeTramitacao,
    StatusTramitacao, StatusTramitacaoAdministrativo,
    MateriaLegislativa, DocumentoAdministrativo, Usuario,
    UsuarioUnidTram, Autoria, Autor, TipoMateriaLegislativa, TipoDocumentoAdministrativo
)
from AccessControl import getSecurityManager
import json
import logging
import time
from threading import Lock

from .config import Session  # Mantido para compatibilidade
from openlegis.sagl.db_session import db_session, db_session_readonly
from DateTime import DateTime

logger = logging.getLogger(__name__)

# ============================================
# CACHE DE CONTADORES (OTIMIZAÇÃO)
# ============================================

# Cache simples em memória para contadores
_contadores_cache = {}
_cache_lock = Lock()
_cache_ttl = 300  # 5 minutos em segundos

# ---------------------------------------------------------------------
# Base com utilitários compartilhados (similar a ProposicoesAPIBase)
# ---------------------------------------------------------------------
class TramitacaoAPIBase:
    """Classe base com métodos utilitários compartilhados para views de tramitação"""
    
    def _get_cod_usuario(self):
        """
        Obtém código do usuário logado
        Segue o mesmo padrão de recebimento_proposicoes.py: usa AUTHENTICATED_USER.getUserName()
        Usa db_session_readonly() para garantir gerenciamento correto da sessão.
        """
        try:
            col_username = self.request.AUTHENTICATED_USER.getUserName()
            with db_session_readonly() as session:
                usuario = (
                    session.query(Usuario)
                    .filter(
                        Usuario.col_username == col_username,
                        Usuario.ind_excluido == 0,
                        Usuario.ind_ativo == 1,
                    )
                    .first()
                )
                if usuario:
                    cod_usuario = usuario.cod_usuario
                    return cod_usuario
                else:
                    logger.warning(f"[tramitacao] _get_cod_usuario - Usuário '{col_username}' não encontrado no banco ou está inativo/excluído")
                    return None
        except Exception as e:
            logger.warning(f"[tramitacao] Não foi possível obter cod_usuario: {e}", exc_info=True)
            return None


def _get_cache_key(cod_usuario, cod_unid_tramitacao, filtro_tipo):
    """Gera chave única para cache"""
    return f"{cod_usuario}_{cod_unid_tramitacao or 'all'}_{filtro_tipo or 'TODOS'}"

def _get_cached_contadores(cod_usuario, cod_unid_tramitacao, filtro_tipo):
    """
    Obtém contadores do cache se ainda válidos.
    
    Returns:
        tuple: (dados, is_valid) ou (None, False) se não há cache válido
    """
    cache_key = _get_cache_key(cod_usuario, cod_unid_tramitacao, filtro_tipo)
    
    with _cache_lock:
        if cache_key in _contadores_cache:
            cached_data, timestamp = _contadores_cache[cache_key]
            if time.time() - timestamp < _cache_ttl:
                logger.debug(f"Cache HIT para contadores: {cache_key}")
                return cached_data, True
            else:
                # Cache expirado, remove
                del _contadores_cache[cache_key]
                logger.debug(f"Cache EXPIRADO para contadores: {cache_key}")
    
    return None, False

def _set_cached_contadores(cod_usuario, cod_unid_tramitacao, filtro_tipo, dados):
    """Armazena contadores no cache"""
    cache_key = _get_cache_key(cod_usuario, cod_unid_tramitacao, filtro_tipo)
    
    with _cache_lock:
        _contadores_cache[cache_key] = (dados, time.time())
        logger.debug(f"Cache SET para contadores: {cache_key}")
        
        # Limpa cache antigo (mais de 1 hora)
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in _contadores_cache.items()
            if current_time - timestamp > 3600
        ]
        for key in expired_keys:
            del _contadores_cache[key]

def _invalidate_cache_contadores(cod_usuario=None, cod_unid_tramitacao=None):
    """
    Invalida cache de contadores (função local que também chama a função do módulo cache).
    
    Args:
        cod_usuario: Se fornecido, invalida apenas para esse usuário
        cod_unid_tramitacao: Se fornecido, invalida apenas para essa unidade
    """
    # Chama a função do módulo cache para garantir invalidação consistente
    try:
        from .cache import invalidate_cache_contadores
        invalidate_cache_contadores(cod_usuario, cod_unid_tramitacao)
    except Exception as e:
        logger.warning(f"Erro ao invalidar cache via módulo cache: {e}")
    
    # Também invalida cache local (se houver)
    with _cache_lock:
        if cod_usuario is None:
            # Invalida todo o cache
            cache_size_before = len(_contadores_cache)
            _contadores_cache.clear()
            logger.debug(f"[_invalidate_cache_contadores] Cache local completamente invalidado ({cache_size_before} entradas removidas)")
        else:
            # Invalida cache específico
            keys_to_remove = []
            for key in _contadores_cache.keys():
                if key.startswith(f"{cod_usuario}_"):
                    if cod_unid_tramitacao is None or f"_{cod_unid_tramitacao}_" in key:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del _contadores_cache[key]
            
            if keys_to_remove:
                logger.debug(f"[_invalidate_cache_contadores] Cache local invalidado para usuário {cod_usuario} (unidade: {cod_unid_tramitacao or 'todas'}) - {len(keys_to_remove)} entradas removidas")

# ============================================
# FUNÇÕES DE ORDENAÇÃO
# ============================================

def _obter_ordenacao_completa_materia(query, ordenacao='asc'):
    """
    Aplica ordenação completa para tramitações de MATÉRIA.
    
    Ordenação:
    1. Primária: dat_encaminha (asc/desc)
    2. Terciária: ano_ident_basica (asc/desc)
    3. Quaternária: num_ident_basica (asc/desc)
    
    Args:
        query: Query SQLAlchemy para Tramitacao
        ordenacao: 'asc' ou 'desc' (padrão: 'asc')
    
    Returns:
        Query com ordenação aplicada
    """
    from openlegis.sagl.models.models import MateriaLegislativa
    
    # Detecta se é MySQL verificando o dialeto da query
    is_mysql = False
    try:
        # Tenta várias formas de obter o bind/engine
        bind = None
        if hasattr(query, 'session') and query.session:
            bind = getattr(query.session, 'bind', None)
        elif hasattr(query, '_bind'):
            bind = query._bind
        elif hasattr(query, 'bind'):
            bind = query.bind
        
        if bind:
            dialect_name = getattr(bind.dialect, 'name', None) if hasattr(bind, 'dialect') else None
            is_mysql = dialect_name == 'mysql' or dialect_name == 'pymysql'
        else:
            # Se não conseguir detectar, assume MySQL (comum no projeto)
            is_mysql = True
    except:
        # Em caso de erro, assume MySQL (baseado no erro reportado)
        is_mysql = True
    
    # Ordenação primária: dat_encaminha
    if is_mysql:
        # MySQL: usa ISNULL() para colocar NULLs no final
        if ordenacao == 'desc':
            query = query.order_by(func.isnull(Tramitacao.dat_encaminha).asc(), Tramitacao.dat_encaminha.desc())
        else:
            query = query.order_by(func.isnull(Tramitacao.dat_encaminha).asc(), Tramitacao.dat_encaminha.asc())
    else:
        # PostgreSQL: usa .nulls_last()
        if ordenacao == 'desc':
            query = query.order_by(Tramitacao.dat_encaminha.desc().nulls_last())
        else:
            query = query.order_by(Tramitacao.dat_encaminha.asc().nulls_last())
    
    # Ordenação terciária: ano da matéria
    if is_mysql:
        if ordenacao == 'desc':
            query = query.order_by(func.isnull(MateriaLegislativa.ano_ident_basica).asc(), MateriaLegislativa.ano_ident_basica.desc())
            # Ordenação quaternária: número da matéria
            query = query.order_by(func.isnull(MateriaLegislativa.num_ident_basica).asc(), MateriaLegislativa.num_ident_basica.desc())
        else:
            query = query.order_by(func.isnull(MateriaLegislativa.ano_ident_basica).asc(), MateriaLegislativa.ano_ident_basica.asc())
            query = query.order_by(func.isnull(MateriaLegislativa.num_ident_basica).asc(), MateriaLegislativa.num_ident_basica.asc())
    else:
        if ordenacao == 'desc':
            query = query.order_by(MateriaLegislativa.ano_ident_basica.desc().nulls_last())
            # Ordenação quaternária: número da matéria
            query = query.order_by(MateriaLegislativa.num_ident_basica.desc().nulls_last())
        else:
            query = query.order_by(MateriaLegislativa.ano_ident_basica.asc().nulls_last())
            query = query.order_by(MateriaLegislativa.num_ident_basica.asc().nulls_last())
    
    return query

def _obter_ordenacao_completa_documento(query, ordenacao='asc'):
    """
    Aplica ordenação completa para tramitações de DOCUMENTO.
    
    Ordenação:
    1. Primária: dat_encaminha (asc/desc)
    2. Terciária: ano_documento (asc/desc)
    3. Quaternária: num_documento (asc/desc)
    
    Args:
        query: Query SQLAlchemy para TramitacaoAdministrativo
        ordenacao: 'asc' ou 'desc' (padrão: 'asc')
    
    Returns:
        Query com ordenação aplicada
    """
    from openlegis.sagl.models.models import DocumentoAdministrativo
    
    # Detecta se é MySQL verificando o dialeto da query
    is_mysql = False
    try:
        # Tenta várias formas de obter o bind/engine
        bind = None
        if hasattr(query, 'session') and query.session:
            bind = getattr(query.session, 'bind', None)
        elif hasattr(query, '_bind'):
            bind = query._bind
        elif hasattr(query, 'bind'):
            bind = query.bind
        
        if bind:
            dialect_name = getattr(bind.dialect, 'name', None) if hasattr(bind, 'dialect') else None
            is_mysql = dialect_name == 'mysql' or dialect_name == 'pymysql'
        else:
            # Se não conseguir detectar, assume MySQL (comum no projeto)
            is_mysql = True
    except:
        # Em caso de erro, assume MySQL (baseado no erro reportado)
        is_mysql = True
    
    # Ordenação primária: dat_encaminha
    if is_mysql:
        # MySQL: usa ISNULL() para colocar NULLs no final
        if ordenacao == 'desc':
            query = query.order_by(func.isnull(TramitacaoAdministrativo.dat_encaminha).asc(), TramitacaoAdministrativo.dat_encaminha.desc())
        else:
            query = query.order_by(func.isnull(TramitacaoAdministrativo.dat_encaminha).asc(), TramitacaoAdministrativo.dat_encaminha.asc())
    else:
        # PostgreSQL: usa .nulls_last()
        if ordenacao == 'desc':
            query = query.order_by(TramitacaoAdministrativo.dat_encaminha.desc().nulls_last())
        else:
            query = query.order_by(TramitacaoAdministrativo.dat_encaminha.asc().nulls_last())
    
    # Ordenação terciária: ano do documento
    if is_mysql:
        if ordenacao == 'desc':
            query = query.order_by(func.isnull(DocumentoAdministrativo.ano_documento).asc(), DocumentoAdministrativo.ano_documento.desc())
            # Ordenação quaternária: número do documento
            query = query.order_by(func.isnull(DocumentoAdministrativo.num_documento).asc(), DocumentoAdministrativo.num_documento.desc())
        else:
            query = query.order_by(func.isnull(DocumentoAdministrativo.ano_documento).asc(), DocumentoAdministrativo.ano_documento.asc())
            query = query.order_by(func.isnull(DocumentoAdministrativo.num_documento).asc(), DocumentoAdministrativo.num_documento.asc())
    else:
        if ordenacao == 'desc':
            query = query.order_by(DocumentoAdministrativo.ano_documento.desc().nulls_last())
            # Ordenação quaternária: número do documento
            query = query.order_by(DocumentoAdministrativo.num_documento.desc().nulls_last())
        else:
            query = query.order_by(DocumentoAdministrativo.ano_documento.asc().nulls_last())
            query = query.order_by(DocumentoAdministrativo.num_documento.asc().nulls_last())
    
    return query

def _ordenar_lista_tramitacoes(tramitacoes, ordenacao='asc'):
    """
    Ordena lista final de tramitações (após merge de MATERIA + DOCUMENTO).
    
    Ordenação:
    1. Primária: dat_encaminha (asc/desc)
    2. Secundária: tipo (MATERIA=1 primeiro, DOCUMENTO=2 depois)
    3. Terciária: ano (materia_ano ou documento_ano)
    4. Quaternária: número (materia_num ou documento_num)
    
    Args:
        tramitacoes: Lista de dicionários com tramitações
        ordenacao: 'asc' ou 'desc' (padrão: 'asc')
    
    Returns:
        Lista ordenada
    """
    reverse = (ordenacao == 'desc')
    
    def chave_ordenacao(tram):
        # Ordenação primária: dat_encaminha
        dat_encaminha = tram.get('dat_encaminha') or ''
        
        # Ordenação secundária: tipo (MATERIA=1, DOCUMENTO=2)
        tipo_ordem = 1 if tram.get('tipo') == 'MATERIA' else 2
        
        # Ordenação terciária: ano
        if tram.get('tipo') == 'MATERIA':
            ano = int(tram.get('materia_ano') or 0)
            num = int(tram.get('materia_num') or 0)
        else:
            ano = int(tram.get('documento_ano') or 0)
            num = int(tram.get('documento_num') or 0)
        
        return (dat_encaminha, tipo_ordem, ano, num)
    
    return sorted(tramitacoes, key=chave_ordenacao, reverse=reverse)

# ============================================
# MONITORAMENTO DE PERFORMANCE
# ============================================

def _log_performance(operation, elapsed_time, query_count=None):
    """
    Registra métricas de performance.
    
    Args:
        operation: Nome da operação (ex: 'caixa_entrada', 'rascunhos')
        elapsed_time: Tempo decorrido em segundos
        query_count: Número de queries executadas (opcional)
    """
    if elapsed_time > 1.0:
        logger.warning(f"⚠️ OPERAÇÃO LENTA: {operation} levou {elapsed_time:.2f}s" + 
                      (f" ({query_count} queries)" if query_count else ""))
    elif elapsed_time > 0.5:
        logger.info(f"⏱️ {operation} levou {elapsed_time:.2f}s" + 
                   (f" ({query_count} queries)" if query_count else ""))
    else:
        logger.debug(f"✓ {operation} levou {elapsed_time:.2f}s" + 
                    (f" ({query_count} queries)" if query_count else ""))


def _get_ip(request):
    """Obtém IP do cliente"""
    if "HTTP_X_FORWARDED_FOR" in request.environ:
        return request.environ["HTTP_X_FORWARDED_FOR"]
    elif "REMOTE_ADDR" in request.environ:
        return request.environ["REMOTE_ADDR"]
    return None


def _registrar_log(context, request, modulo, metodo, cod_registro, dados=None):
    """
    Registra ação do usuário no banco de logs (dbcon_logs)
    
    Args:
        context: Contexto Zope (self.context)
        request: Request object
        modulo: Nome do módulo (ex: 'tramitacao_materia', 'tramitacao_documento')
        metodo: Nome do método/ação (ex: 'tramitacao_salvar', 'tramitacao_receber')
        cod_registro: Código do registro afetado
        dados: Dados adicionais (opcional, pode ser string ou dict)
    """
    try:
        # Verifica se dbcon_logs está configurado
        if not hasattr(context, 'dbcon_logs') or not context.dbcon_logs:
            return
        
        # Obtém usuário - mesma abordagem de pesquisa_documentos_administrativos.py
        from Products.CMFCore.utils import getToolByName
        
        try:
            mtool = getToolByName(context, 'portal_membership')
            if mtool.isAnonymousUser():
                return
            
            member = mtool.getAuthenticatedMember()
            if not member:
                return
            
            username = member.getUserName()
            if not username:
                return
        except (AttributeError, KeyError):
            # Se não conseguir obter portal_membership, tenta método alternativo
            try:
                from AccessControl import getSecurityManager
                user = getSecurityManager().getUser()
                if user is None or user.getUserName() == 'Anonymous User':
                    return
                username = user.getUserName()
            except Exception:
                return
        
        # Obtém IP
        ip = _get_ip(request)
        
        # Formata dados
        dados_str = None
        if dados:
            if isinstance(dados, dict):
                dados_str = str(dados.items())
            else:
                dados_str = str(dados)
        
        # Formata data
        data_str = DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
        
        # Registra log via ZSQL
        if hasattr(context, 'zsql') and hasattr(context.zsql, 'logs_registrar_zsql'):
            context.zsql.logs_registrar_zsql(
                usuario=username,
                data=data_str,
                modulo=modulo,
                metodo=metodo,
                cod_registro=cod_registro,
                IP=ip or '',
                dados=dados_str
            )
    except Exception as e:
        # Não interrompe o fluxo se o log falhar
        logger.warning(f"Erro ao registrar log: {e}", exc_info=True)


def _get_tipo_tramitacao(request):
    """Detecta tipo de tramitação da URL ou parâmetro"""
    path = request.get('PATH_INFO', '')
    if 'tramitacao_materia' in path or request.form.get('tipo') == 'MATERIA':
        return 'MATERIA'
    elif 'tramitacao_documento' in path or request.form.get('tipo') == 'DOCUMENTO':
        return 'DOCUMENTO'
    return 'MATERIA'  # default


def _get_nome_unidade_tramitacao(unidade):
    """
    Obtém o nome da unidade de tramitação.
    UnidadeTramitacao pode ser uma Comissao, Orgao ou Parlamentar.
    """
    if not unidade:
        return ''
    
    # Verifica se é comissão
    if unidade.comissao:
        return unidade.comissao.nom_comissao or ''
    
    # Verifica se é órgão
    if unidade.orgao:
        return unidade.orgao.nom_orgao or ''
    
    # Verifica se é parlamentar
    if unidade.parlamentar:
        return unidade.parlamentar.nom_parlamentar or unidade.parlamentar.nom_completo or ''
    
    return ''


def _get_nom_autor_join(autor):
    """
    Obtém o nome formatado do autor (nom_autor_join).
    Lógica baseada em autoria_obter_zsql.zsql:
    - Se for Parlamentar: usa nom_parlamentar
    - Se for Bancada: usa nom_bancada
    - Se for Comissão: usa nom_comissao
    - Caso contrário: usa nom_autor
    """
    if not autor:
        return ''
    
    # Carrega relacionamentos se necessário
    if not autor.tipo_autor:
        return autor.nom_autor or ''
    
    tipo_autor = autor.tipo_autor.des_tipo_autor if hasattr(autor.tipo_autor, 'des_tipo_autor') else ''
    
    if tipo_autor == 'Parlamentar' and autor.parlamentar:
        return autor.parlamentar.nom_parlamentar or autor.parlamentar.nom_completo or autor.nom_autor or ''
    elif tipo_autor == 'Bancada' and autor.bancada:
        return autor.bancada.nom_bancada or autor.nom_autor or ''
    elif tipo_autor == 'Comissao' and autor.comissao:
        return autor.comissao.nom_comissao or autor.nom_autor or ''
    else:
        return autor.nom_autor or ''


def _get_autoria_materia(session, cod_materia):
    """
    Obtém a autoria formatada de uma matéria.
    Retorna string com nomes dos autores separados por vírgula.
    Usa os relacionamentos do SQLAlchemy (Autoria -> Autor).
    
    DEPRECATED: Use _get_autoria_batch() para carregar múltiplas matérias de uma vez.
    """
    if not cod_materia:
        return ''
    
    try:
        # Busca a matéria com eager loading da autoria, autor e seus relacionamentos
        materia = session.query(MateriaLegislativa).options(
            selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.tipo_autor),
            selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.parlamentar),
            selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.bancada),
            selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.comissao)
        ).filter(
            MateriaLegislativa.cod_materia == cod_materia,
            MateriaLegislativa.ind_excluido == 0
        ).first()
        
        if not materia or not materia.autoria:
            return ''
        
        # Filtra autorias não excluídas
        autorias_validas = [
            autoria for autoria in materia.autoria
            if autoria.ind_excluido == 0 
            and autoria.autor 
            and autoria.autor.ind_excluido == 0
        ]
        
        if not autorias_validas:
            return ''
        
        # Obtém nomes formatados
        nomes_com_ind = [
            (_get_nom_autor_join(autoria.autor), autoria.ind_primeiro_autor)
            for autoria in autorias_validas
            if _get_nom_autor_join(autoria.autor)
        ]
        
        if not nomes_com_ind:
            return ''
        
        # Ordena: primeiro autor primeiro (ind_primeiro_autor=1 vem antes de 0), depois por nome
        # ind_primeiro_autor: 1 = primeiro autor, 0 = coautor
        nomes_com_ind.sort(key=lambda x: (-x[1], x[0]))
        
        nomes = [nome for nome, _ in nomes_com_ind]
        return ', '.join(nomes) if nomes else ''
    except Exception as e:
        logger.warning(f"Erro ao obter autoria da matéria {cod_materia}: {e}", exc_info=True)
        return ''


def _get_autoria_batch(session, cod_materias):
    """
    OTIMIZAÇÃO: Carrega autoria de múltiplas matérias em batch (evita N+1 queries).
    
    Args:
        session: SQLAlchemy session
        cod_materias: Lista de códigos de matérias
    
    Returns:
        Dict {cod_materia: string_autoria} com autoria formatada para cada matéria
    """
    if not cod_materias:
        return {}
    
    try:
        # Remove duplicatas e None
        cod_materias_unicos = list(set([m for m in cod_materias if m]))
        if not cod_materias_unicos:
            return {}
        
        # Busca todas as matérias com eager loading da autoria em uma única query
        materias = session.query(MateriaLegislativa).options(
            selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.tipo_autor),
            selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.parlamentar),
            selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.bancada),
            selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.comissao)
        ).filter(
            MateriaLegislativa.cod_materia.in_(cod_materias_unicos),
            MateriaLegislativa.ind_excluido == 0
        ).all()
        
        # Processa autoria para cada matéria
        resultado = {}
        for materia in materias:
            if not materia.autoria:
                resultado[materia.cod_materia] = ''
                continue
            
            # Filtra autorias não excluídas
            autorias_validas = [
                autoria for autoria in materia.autoria
                if autoria.ind_excluido == 0 
                and autoria.autor 
                and autoria.autor.ind_excluido == 0
            ]
            
            if not autorias_validas:
                resultado[materia.cod_materia] = ''
                continue
            
            # Obtém nomes formatados
            nomes_com_ind = [
                (_get_nom_autor_join(autoria.autor), autoria.ind_primeiro_autor)
                for autoria in autorias_validas
                if _get_nom_autor_join(autoria.autor)
            ]
            
            if not nomes_com_ind:
                resultado[materia.cod_materia] = ''
                continue
            
            # Ordena: primeiro autor primeiro (ind_primeiro_autor=1 vem antes de 0), depois por nome
            nomes_com_ind.sort(key=lambda x: (-x[1], x[0]))
            nomes = [nome for nome, _ in nomes_com_ind]
            resultado[materia.cod_materia] = ', '.join(nomes)
        
        # Preenche com string vazia para matérias que não foram encontradas
        for cod_materia in cod_materias_unicos:
            if cod_materia not in resultado:
                resultado[cod_materia] = ''
        
        return resultado
    except Exception as e:
        logger.warning(f"Erro ao obter autoria em batch: {e}", exc_info=True)
        # Retorna dict vazio em caso de erro
        return {cod: '' for cod in cod_materias if cod}


class TramitacaoCaixaEntradaUnificadaView(GrokView, TramitacaoAPIBase):
    """View para caixa de entrada UNIFICADA (ambos os tipos)"""
    
    context(Interface)
    name('tramitacao_caixa_entrada_unificada_json')
    require('zope2.View')
    
    def render(self):
        """Retorna dados da caixa de entrada UNIFICADA em JSON (MATERIA + DOCUMENTO)"""
        # O require('zope2.View') já garante autenticação
        
        # MONITORAMENTO: Inicia contagem de tempo e queries
        start_time = time.time()
        query_count = 0
        
        # Filtro opcional por tipo (se não fornecido, retorna ambos)
        filtro_tipo = self.request.form.get('tipo', '')  # 'MATERIA', 'DOCUMENTO' ou '' (ambos)
        
        # Filtros por tipo específico de matéria ou documento
        filtro_tipo_materia = self.request.form.get('tipo_materia', '').strip()
        filtro_tipo_documento = self.request.form.get('tipo_documento', '').strip()
        
        # Parâmetros de busca e filtros avançados (aplicados no backend para todos os resultados)
        busca_termo = self.request.form.get('busca', '').strip()
        filtro_numero = self.request.form.get('numero', '').strip()
        filtro_ano = self.request.form.get('ano', '').strip()
        filtro_interessado = self.request.form.get('interessado', '').strip()
        filtro_status = self.request.form.get('status', '').strip()
        filtro_data_inicial = self.request.form.get('data_inicial', '').strip()
        filtro_data_final = self.request.form.get('data_final', '').strip()
        
        # Parâmetro de ordenação (asc ou desc, padrão: asc)
        ordenacao = self.request.form.get('ordenacao', 'asc').lower()
        if ordenacao not in ['asc', 'desc']:
            ordenacao = 'asc'
        
        # Usa context manager para leitura
        try:
            with db_session_readonly() as session:
                # Obtém código do usuário - apenas via método _get_cod_usuario (maior segurança)
                cod_usuario = self._get_cod_usuario()
                
                # Se não conseguir obter cod_usuario, não pode continuar
                if not cod_usuario:
                    logger.error("Não foi possível obter cod_usuario. Verifique se o usuário está autenticado e tem registro na tabela Usuario.")
                    dados = {
                        'tramitacoes': [],
                        'total': 0,
                        'total_materias': 0,
                        'total_documentos': 0,
                        'filtro_tipo': filtro_tipo or 'TODOS',
                        'titulo': 'Caixa de Entrada Unificada - Todas as Tramitações',
                        'erro': 'Não foi possível identificar o usuário. Verifique se está autenticado.'
                    }
                    self.request.response.setHeader('Content-Type', 'application/json')
                    return json.dumps(dados, default=str)
                
                # Verifica se foi solicitado filtrar por uma unidade específica
                cod_unid_tramitacao_filtro = None
                if 'cod_unid_tramitacao' in self.request.form:
                    try:
                        cod_unid_tramitacao_filtro = int(self.request.form.get('cod_unid_tramitacao'))
                    except (ValueError, TypeError):
                        pass
                
                # Obtém unidades do usuário (mesma lógica dos scripts antigos)
                unidades = session.query(UsuarioUnidTram).filter(
                    UsuarioUnidTram.cod_usuario == cod_usuario,
                    UsuarioUnidTram.ind_excluido == 0
                ).all()
                
                if not unidades:
                    # Usuário sem unidades ou nenhuma unidade cadastrada
                    dados = {
                        'tramitacoes': [],
                        'total': 0,
                        'total_materias': 0,
                        'total_documentos': 0,
                        'filtro_tipo': filtro_tipo or 'TODOS',
                        'titulo': 'Caixa de Entrada Unificada - Todas as Tramitações'
                    }
                    self.request.response.setHeader('Content-Type', 'application/json')
                    return json.dumps(dados, default=str)
                
                # Se foi solicitado filtrar por unidade específica, verifica se o usuário tem acesso
                if cod_unid_tramitacao_filtro:
                    unidades_usuario = [u.cod_unid_tramitacao for u in unidades]
                    if cod_unid_tramitacao_filtro not in unidades_usuario:
                        # Usuário não tem acesso a essa unidade
                        dados = {
                            'tramitacoes': [],
                            'total': 0,
                            'total_materias': 0,
                            'total_documentos': 0,
                            'filtro_tipo': filtro_tipo or 'TODOS',
                            'titulo': 'Caixa de Entrada Unificada - Todas as Tramitações'
                        }
                        self.request.response.setHeader('Content-Type', 'application/json')
                        return json.dumps(dados, default=str)
                    # Filtra apenas a unidade solicitada
                    unidades = [u for u in unidades if u.cod_unid_tramitacao == cod_unid_tramitacao_filtro]
                
                # OTIMIZAÇÃO: Agrupa unidades por tipo de responsabilidade para reduzir queries
                unidades_responsavel = [u.cod_unid_tramitacao for u in unidades if u.ind_responsavel == 1]
                unidades_nao_responsavel = [u.cod_unid_tramitacao for u in unidades if u.ind_responsavel == 0]
                
                # Lista para armazenar todas as tramitações
                todas_tramitacoes = []
                
                # Importa TramitacaoService para usar filtro de rascunhos posteriores
                from .services import TramitacaoService
                service = TramitacaoService(session)
                
                # Busca tramitações de MATÉRIAS (se filtro permitir)
                if not filtro_tipo or filtro_tipo == 'MATERIA':
                    # OTIMIZAÇÃO: Query única para unidades responsáveis
                    if unidades_responsavel:
                        tramitacoes_resp = session.query(Tramitacao).options(
                            selectinload(Tramitacao.status_tramitacao),
                            selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                            selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                            selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                            selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                            selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                            selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                            selectinload(Tramitacao.materia_legislativa).selectinload(MateriaLegislativa.tipo_materia_legislativa)
                        ).filter(
                            Tramitacao.cod_unid_tram_dest.in_(unidades_responsavel),
                            Tramitacao.ind_ult_tramitacao == 1,
                            Tramitacao.dat_encaminha.isnot(None),
                            # ✅ REMOVIDO: Tramitacao.dat_recebimento.is_(None) - processos visualizados/recebidos devem permanecer na caixa de entrada
                            Tramitacao.ind_excluido == 0
                        ).join(
                            StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
                        ).filter(
                            StatusTramitacao.ind_retorno_tramitacao == 1
                        ).join(
                            MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
                        ).filter(
                            MateriaLegislativa.ind_tramitacao == 1,
                            MateriaLegislativa.ind_excluido == 0
                        )
                        
                        # Filtro por tipo de matéria (sigla) - aplica no backend
                        if filtro_tipo_materia:
                            tramitacoes_resp = tramitacoes_resp.join(
                                TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
                            ).filter(
                                TipoMateriaLegislativa.sgl_tipo_materia == filtro_tipo_materia
                            )
                        
                        # Aplica filtro para excluir tramitações com rascunhos posteriores
                        # Usa a primeira unidade responsável para o filtro (ou None se não houver)
                        cod_unid_tram_dest_filtro = unidades_responsavel[0] if unidades_responsavel else None
                        tramitacoes_resp = service.filtrar_tramitacoes_caixa_entrada('MATERIA', tramitacoes_resp, cod_unid_tram_dest_filtro)
                        
                        # Aplica filtros de busca avançados (aplicados no backend para todos os resultados)
                        if filtro_numero:
                            tramitacoes_resp = tramitacoes_resp.filter(MateriaLegislativa.num_ident_basica.like(f'%{filtro_numero}%'))
                        if filtro_ano:
                            tramitacoes_resp = tramitacoes_resp.filter(MateriaLegislativa.ano_ident_basica.like(f'%{filtro_ano}%'))
                        if filtro_status:
                            tramitacoes_resp = tramitacoes_resp.filter(StatusTramitacao.des_status == filtro_status)
                        if filtro_data_inicial:
                            try:
                                from datetime import datetime
                                data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                                tramitacoes_resp = tramitacoes_resp.filter(Tramitacao.dat_encaminha >= data_inicial_obj)
                            except (ValueError, TypeError):
                                pass
                        if filtro_data_final:
                            try:
                                from datetime import datetime
                                data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                                # Adiciona 23:59:59 para incluir todo o dia
                                data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                                tramitacoes_resp = tramitacoes_resp.filter(Tramitacao.dat_encaminha <= data_final_obj)
                            except (ValueError, TypeError):
                                pass
                        if busca_termo:
                            # Busca em ementa, número/ano, e será aplicado também em autoria após carregar
                            tramitacoes_resp = tramitacoes_resp.filter(
                                or_(
                                    MateriaLegislativa.txt_ementa.like(f'%{busca_termo}%'),
                                    func.concat(MateriaLegislativa.num_ident_basica, '/', MateriaLegislativa.ano_ident_basica).like(f'%{busca_termo}%')
                                )
                            )
                        
                        # Aplica ordenação completa (data, ano, número)
                        tramitacoes_resp = _obter_ordenacao_completa_materia(tramitacoes_resp, ordenacao).all()
                        query_count += 1  # MONITORAMENTO
                        
                        for tram in tramitacoes_resp:
                            todas_tramitacoes.append({
                                'tipo': 'MATERIA',
                                'cod_tramitacao': tram.cod_tramitacao,
                                'cod_entidade': tram.cod_materia,  # Adiciona cod_entidade para compatibilidade
                                'cod_materia': tram.cod_materia,
                                'dat_encaminha': tram.dat_encaminha.isoformat() if tram.dat_encaminha else None,
                                'dat_visualizacao': tram.dat_visualizacao.isoformat() if tram.dat_visualizacao else None,
                                'dat_recebimento': tram.dat_recebimento.isoformat() if tram.dat_recebimento else None,
                                'dat_fim_prazo': tram.dat_fim_prazo.isoformat() if tram.dat_fim_prazo else None,
                                'des_status': tram.status_tramitacao.des_status if tram.status_tramitacao else '',
                                'unidade_origem': _get_nome_unidade_tramitacao(tram.unidade_tramitacao_),
                                'unidade_destino': _get_nome_unidade_tramitacao(tram.unidade_tramitacao),
                                'materia_des_tipo': tram.materia_legislativa.tipo_materia_legislativa.des_tipo_materia if tram.materia_legislativa and tram.materia_legislativa.tipo_materia_legislativa else '',
                                'materia_num': tram.materia_legislativa.num_ident_basica if tram.materia_legislativa else '',
                                'materia_ano': tram.materia_legislativa.ano_ident_basica if tram.materia_legislativa else '',
                                'materia_ementa': tram.materia_legislativa.txt_ementa if tram.materia_legislativa else '',
                                'materia_sigla': tram.materia_legislativa.tipo_materia_legislativa.sgl_tipo_materia if tram.materia_legislativa and tram.materia_legislativa.tipo_materia_legislativa else '',
                                # Autoria será adicionada em batch depois
                            })
                    
                    # OTIMIZAÇÃO: Query única para unidades não-responsáveis
                    if unidades_nao_responsavel:
                        tramitacoes_nao_resp = session.query(Tramitacao).options(
                            selectinload(Tramitacao.status_tramitacao),
                            selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                            selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                            selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                            selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                            selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                            selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                            selectinload(Tramitacao.materia_legislativa).selectinload(MateriaLegislativa.tipo_materia_legislativa)
                        ).filter(
                            Tramitacao.cod_unid_tram_dest.in_(unidades_nao_responsavel),
                            # Para unidades não responsáveis: cod_usuario_dest deve ser igual ao usuário OU NULL (mesma lógica do ZSQL)
                            (Tramitacao.cod_usuario_dest == cod_usuario) | (Tramitacao.cod_usuario_dest.is_(None)),
                            Tramitacao.ind_ult_tramitacao == 1,
                            Tramitacao.dat_encaminha.isnot(None),
                            # ✅ REMOVIDO: Tramitacao.dat_recebimento.is_(None) - processos visualizados/recebidos devem permanecer na caixa de entrada
                            Tramitacao.ind_excluido == 0
                        ).join(
                            StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
                        ).filter(
                            StatusTramitacao.ind_retorno_tramitacao == 1
                        ).join(
                            MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
                        ).filter(
                            MateriaLegislativa.ind_tramitacao == 1,
                            MateriaLegislativa.ind_excluido == 0
                        )
                        
                        # Filtro por tipo de matéria (sigla) - aplica no backend
                        if filtro_tipo_materia:
                            tramitacoes_nao_resp = tramitacoes_nao_resp.join(
                                TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
                            ).filter(
                                TipoMateriaLegislativa.sgl_tipo_materia == filtro_tipo_materia
                            )
                        
                        # Aplica filtro para excluir tramitações com rascunhos posteriores
                        # Usa a primeira unidade não responsável para o filtro (ou None se não houver)
                        cod_unid_tram_dest_filtro = unidades_nao_responsavel[0] if unidades_nao_responsavel else None
                        tramitacoes_nao_resp = service.filtrar_tramitacoes_caixa_entrada('MATERIA', tramitacoes_nao_resp, cod_unid_tram_dest_filtro)
                        
                        # Aplica filtros de busca avançados (aplicados no backend para todos os resultados)
                        if filtro_numero:
                            tramitacoes_nao_resp = tramitacoes_nao_resp.filter(MateriaLegislativa.num_ident_basica.like(f'%{filtro_numero}%'))
                        if filtro_ano:
                            tramitacoes_nao_resp = tramitacoes_nao_resp.filter(MateriaLegislativa.ano_ident_basica.like(f'%{filtro_ano}%'))
                        if filtro_status:
                            tramitacoes_nao_resp = tramitacoes_nao_resp.filter(StatusTramitacao.des_status == filtro_status)
                        if filtro_data_inicial:
                            try:
                                from datetime import datetime
                                data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                                tramitacoes_nao_resp = tramitacoes_nao_resp.filter(Tramitacao.dat_encaminha >= data_inicial_obj)
                            except (ValueError, TypeError):
                                pass
                        if filtro_data_final:
                            try:
                                from datetime import datetime
                                data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                                # Adiciona 23:59:59 para incluir todo o dia
                                data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                                tramitacoes_nao_resp = tramitacoes_nao_resp.filter(Tramitacao.dat_encaminha <= data_final_obj)
                            except (ValueError, TypeError):
                                pass
                        if busca_termo:
                            # Busca em ementa, número/ano, e será aplicado também em autoria após carregar
                            tramitacoes_nao_resp = tramitacoes_nao_resp.filter(
                                or_(
                                    MateriaLegislativa.txt_ementa.like(f'%{busca_termo}%'),
                                    func.concat(MateriaLegislativa.num_ident_basica, '/', MateriaLegislativa.ano_ident_basica).like(f'%{busca_termo}%')
                                )
                            )
                        
                        # Aplica ordenação completa (data, ano, número)
                        tramitacoes_nao_resp = _obter_ordenacao_completa_materia(tramitacoes_nao_resp, ordenacao).all()
                        query_count += 1  # MONITORAMENTO
                        
                        for tram in tramitacoes_nao_resp:
                            cod_materia = tram.cod_materia if tram.materia_legislativa else None
                            todas_tramitacoes.append({
                            'tipo': 'MATERIA',
                            'cod_tramitacao': tram.cod_tramitacao,
                            'cod_entidade': cod_materia,  # Adiciona cod_entidade para compatibilidade
                            'cod_materia': cod_materia,
                            'dat_encaminha': tram.dat_encaminha.isoformat() if tram.dat_encaminha else None,
                            'dat_recebimento': tram.dat_recebimento.isoformat() if tram.dat_recebimento else None,
                            'dat_fim_prazo': tram.dat_fim_prazo.isoformat() if tram.dat_fim_prazo else None,
                            'des_status': tram.status_tramitacao.des_status if tram.status_tramitacao else '',
                            'unidade_origem': _get_nome_unidade_tramitacao(tram.unidade_tramitacao_),
                            'unidade_destino': _get_nome_unidade_tramitacao(tram.unidade_tramitacao),
                            'materia_des_tipo': tram.materia_legislativa.tipo_materia_legislativa.des_tipo_materia if tram.materia_legislativa and tram.materia_legislativa.tipo_materia_legislativa else '',
                            'materia_num': tram.materia_legislativa.num_ident_basica if tram.materia_legislativa else '',
                            'materia_ano': tram.materia_legislativa.ano_ident_basica if tram.materia_legislativa else '',
                            'materia_ementa': tram.materia_legislativa.txt_ementa if tram.materia_legislativa else '',
                                'materia_sigla': tram.materia_legislativa.tipo_materia_legislativa.sgl_tipo_materia if tram.materia_legislativa and tram.materia_legislativa.tipo_materia_legislativa else '',
                                # Autoria será adicionada em batch depois (linha ~1017)
                            })
                
                # Busca tramitações de DOCUMENTOS ADMINISTRATIVOS (se filtro permitir)
                if not filtro_tipo or filtro_tipo == 'DOCUMENTO':
                    # OTIMIZAÇÃO: Query única para unidades responsáveis
                    # Para unidades responsáveis: não verifica cod_usuario_dest (mesma lógica do script antigo)
                    if unidades_responsavel:
                        tramitacoes_doc_resp = session.query(TramitacaoAdministrativo).options(
                            selectinload(TramitacaoAdministrativo.status_tramitacao_administrativo),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                            selectinload(TramitacaoAdministrativo.documento_administrativo).selectinload(DocumentoAdministrativo.tipo_documento_administrativo)
                        ).filter(
                            TramitacaoAdministrativo.cod_unid_tram_dest.in_(unidades_responsavel),
                            TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                            TramitacaoAdministrativo.dat_encaminha.isnot(None),
                            # ✅ REMOVIDO: TramitacaoAdministrativo.dat_recebimento.is_(None) - processos visualizados/recebidos devem permanecer na caixa de entrada
                            TramitacaoAdministrativo.ind_excluido == 0
                        ).join(
                            StatusTramitacaoAdministrativo, TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status
                        ).filter(
                            StatusTramitacaoAdministrativo.ind_retorno_tramitacao == 1
                        ).join(
                            DocumentoAdministrativo, TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
                        ).filter(
                            DocumentoAdministrativo.ind_tramitacao == 1,
                            DocumentoAdministrativo.ind_excluido == 0
                        )
                        
                        # Filtro por tipo de documento (sigla) - aplica no backend
                        if filtro_tipo_documento:
                            tramitacoes_doc_resp = tramitacoes_doc_resp.join(
                                TipoDocumentoAdministrativo, DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento
                            ).filter(
                                TipoDocumentoAdministrativo.sgl_tipo_documento == filtro_tipo_documento
                            )
                        
                        # Aplica filtro para excluir tramitações com rascunhos posteriores
                        # Usa a primeira unidade responsável para o filtro (ou None se não houver)
                        cod_unid_tram_dest_filtro = unidades_responsavel[0] if unidades_responsavel else None
                        tramitacoes_doc_resp = service.filtrar_tramitacoes_caixa_entrada('DOCUMENTO', tramitacoes_doc_resp, cod_unid_tram_dest_filtro)
                        
                        # Aplica filtros de busca avançados (aplicados no backend para todos os resultados)
                        if filtro_numero:
                            tramitacoes_doc_resp = tramitacoes_doc_resp.filter(DocumentoAdministrativo.num_documento.like(f'%{filtro_numero}%'))
                        if filtro_ano:
                            tramitacoes_doc_resp = tramitacoes_doc_resp.filter(DocumentoAdministrativo.ano_documento.like(f'%{filtro_ano}%'))
                        if filtro_status:
                            tramitacoes_doc_resp = tramitacoes_doc_resp.filter(StatusTramitacaoAdministrativo.des_status == filtro_status)
                        if filtro_data_inicial:
                            try:
                                from datetime import datetime
                                data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                                tramitacoes_doc_resp = tramitacoes_doc_resp.filter(TramitacaoAdministrativo.dat_encaminha >= data_inicial_obj)
                            except (ValueError, TypeError):
                                pass
                        if filtro_data_final:
                            try:
                                from datetime import datetime
                                data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                                # Adiciona 23:59:59 para incluir todo o dia
                                data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                                tramitacoes_doc_resp = tramitacoes_doc_resp.filter(TramitacaoAdministrativo.dat_encaminha <= data_final_obj)
                            except (ValueError, TypeError):
                                pass
                        if busca_termo:
                            # Busca em assunto, interessado, número/ano
                            tramitacoes_doc_resp = tramitacoes_doc_resp.filter(
                                or_(
                                    DocumentoAdministrativo.txt_assunto.like(f'%{busca_termo}%'),
                                    DocumentoAdministrativo.txt_interessado.like(f'%{busca_termo}%'),
                                    func.concat(DocumentoAdministrativo.num_documento, '/', DocumentoAdministrativo.ano_documento).like(f'%{busca_termo}%')
                                )
                            )
                        
                        # Aplica ordenação completa (data, ano, número)
                        tramitacoes_doc_resp = _obter_ordenacao_completa_documento(tramitacoes_doc_resp, ordenacao).all()
                        query_count += 1  # MONITORAMENTO
                        
                        for tram in tramitacoes_doc_resp:
                            todas_tramitacoes.append({
                            'tipo': 'DOCUMENTO',
                            'cod_tramitacao': tram.cod_tramitacao,
                            'cod_entidade': tram.cod_documento,  # Adiciona cod_entidade para compatibilidade
                            'cod_documento': tram.cod_documento,
                            'dat_encaminha': tram.dat_encaminha.isoformat() if tram.dat_encaminha else None,
                            'dat_visualizacao': tram.dat_visualizacao.isoformat() if tram.dat_visualizacao else None,
                            'dat_recebimento': tram.dat_recebimento.isoformat() if tram.dat_recebimento else None,
                            'dat_fim_prazo': tram.dat_fim_prazo.isoformat() if tram.dat_fim_prazo else None,
                            'des_status': tram.status_tramitacao_administrativo.des_status if tram.status_tramitacao_administrativo else '',
                            'unidade_origem': _get_nome_unidade_tramitacao(tram.unidade_tramitacao_),
                            'unidade_destino': _get_nome_unidade_tramitacao(tram.unidade_tramitacao),
                            'documento_des_tipo': tram.documento_administrativo.tipo_documento_administrativo.des_tipo_documento if tram.documento_administrativo and tram.documento_administrativo.tipo_documento_administrativo else '',
                            'documento_num': tram.documento_administrativo.num_documento if tram.documento_administrativo else '',
                            'documento_ano': tram.documento_administrativo.ano_documento if tram.documento_administrativo else '',
                            'documento_assunto': tram.documento_administrativo.txt_assunto if tram.documento_administrativo else '',
                            'documento_interessado': tram.documento_administrativo.txt_interessado if tram.documento_administrativo else '',
                                'documento_sigla': tram.documento_administrativo.tipo_documento_administrativo.sgl_tipo_documento if tram.documento_administrativo and tram.documento_administrativo.tipo_documento_administrativo else '',
                            })
                    
                    # OTIMIZAÇÃO: Query única para unidades não-responsáveis
                    # Para unidades não responsáveis: cod_usuario_dest deve ser igual ao usuário OU NULL (mesma lógica do ZSQL)
                    if unidades_nao_responsavel:
                        tramitacoes_doc_nao_resp = session.query(TramitacaoAdministrativo).options(
                            selectinload(TramitacaoAdministrativo.status_tramitacao_administrativo),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                            selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                            selectinload(TramitacaoAdministrativo.documento_administrativo).selectinload(DocumentoAdministrativo.tipo_documento_administrativo)
                        ).filter(
                            TramitacaoAdministrativo.cod_unid_tram_dest.in_(unidades_nao_responsavel),
                            # Para unidades não responsáveis: cod_usuario_dest deve ser igual ao usuário OU NULL (mesma lógica do ZSQL)
                            (TramitacaoAdministrativo.cod_usuario_dest == cod_usuario) | (TramitacaoAdministrativo.cod_usuario_dest.is_(None)),
                            TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                            TramitacaoAdministrativo.dat_encaminha.isnot(None),
                            # ✅ REMOVIDO: TramitacaoAdministrativo.dat_recebimento.is_(None) - processos visualizados/recebidos devem permanecer na caixa de entrada
                            TramitacaoAdministrativo.ind_excluido == 0
                        ).join(
                            StatusTramitacaoAdministrativo, TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status
                        ).filter(
                            StatusTramitacaoAdministrativo.ind_retorno_tramitacao == 1
                        ).join(
                            DocumentoAdministrativo, TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
                        ).filter(
                            DocumentoAdministrativo.ind_tramitacao == 1,
                            DocumentoAdministrativo.ind_excluido == 0
                        )
                        
                        # Filtro por tipo de documento (sigla) - aplica no backend
                        if filtro_tipo_documento:
                            tramitacoes_doc_nao_resp = tramitacoes_doc_nao_resp.join(
                                TipoDocumentoAdministrativo, DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento
                            ).filter(
                                TipoDocumentoAdministrativo.sgl_tipo_documento == filtro_tipo_documento
                            )
                        
                        # Aplica filtro para excluir tramitações com rascunhos posteriores
                        # Usa a primeira unidade não responsável para o filtro (ou None se não houver)
                        cod_unid_tram_dest_filtro = unidades_nao_responsavel[0] if unidades_nao_responsavel else None
                        tramitacoes_doc_nao_resp = service.filtrar_tramitacoes_caixa_entrada('DOCUMENTO', tramitacoes_doc_nao_resp, cod_unid_tram_dest_filtro)
                        
                        # Aplica filtros de busca avançados (aplicados no backend para todos os resultados)
                        if filtro_numero:
                            tramitacoes_doc_nao_resp = tramitacoes_doc_nao_resp.filter(DocumentoAdministrativo.num_documento.like(f'%{filtro_numero}%'))
                        if filtro_ano:
                            tramitacoes_doc_nao_resp = tramitacoes_doc_nao_resp.filter(DocumentoAdministrativo.ano_documento.like(f'%{filtro_ano}%'))
                        if filtro_status:
                            tramitacoes_doc_nao_resp = tramitacoes_doc_nao_resp.filter(StatusTramitacaoAdministrativo.des_status == filtro_status)
                        if filtro_data_inicial:
                            try:
                                from datetime import datetime
                                data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                                tramitacoes_doc_nao_resp = tramitacoes_doc_nao_resp.filter(TramitacaoAdministrativo.dat_encaminha >= data_inicial_obj)
                            except (ValueError, TypeError):
                                pass
                        if filtro_data_final:
                            try:
                                from datetime import datetime
                                data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                                # Adiciona 23:59:59 para incluir todo o dia
                                data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                                tramitacoes_doc_nao_resp = tramitacoes_doc_nao_resp.filter(TramitacaoAdministrativo.dat_encaminha <= data_final_obj)
                            except (ValueError, TypeError):
                                pass
                        if busca_termo:
                            # Busca em assunto, interessado, número/ano
                            tramitacoes_doc_nao_resp = tramitacoes_doc_nao_resp.filter(
                                or_(
                                    DocumentoAdministrativo.txt_assunto.like(f'%{busca_termo}%'),
                                    DocumentoAdministrativo.txt_interessado.like(f'%{busca_termo}%'),
                                    func.concat(DocumentoAdministrativo.num_documento, '/', DocumentoAdministrativo.ano_documento).like(f'%{busca_termo}%')
                                )
                            )
                        
                        # Aplica ordenação completa (data, ano, número)
                        tramitacoes_doc_nao_resp = _obter_ordenacao_completa_documento(tramitacoes_doc_nao_resp, ordenacao).all()
                        query_count += 1  # MONITORAMENTO
                        
                        for tram in tramitacoes_doc_nao_resp:
                            todas_tramitacoes.append({
                            'tipo': 'DOCUMENTO',
                            'cod_tramitacao': tram.cod_tramitacao,
                            'cod_entidade': tram.cod_documento,  # Adiciona cod_entidade para compatibilidade
                            'cod_documento': tram.cod_documento,
                            'dat_encaminha': tram.dat_encaminha.isoformat() if tram.dat_encaminha else None,
                            'dat_visualizacao': tram.dat_visualizacao.isoformat() if tram.dat_visualizacao else None,
                            'dat_recebimento': tram.dat_recebimento.isoformat() if tram.dat_recebimento else None,
                            'dat_fim_prazo': tram.dat_fim_prazo.isoformat() if tram.dat_fim_prazo else None,
                            'des_status': tram.status_tramitacao_administrativo.des_status if tram.status_tramitacao_administrativo else '',
                            'unidade_origem': _get_nome_unidade_tramitacao(tram.unidade_tramitacao_),
                            'unidade_destino': _get_nome_unidade_tramitacao(tram.unidade_tramitacao),
                            'documento_des_tipo': tram.documento_administrativo.tipo_documento_administrativo.des_tipo_documento if tram.documento_administrativo and tram.documento_administrativo.tipo_documento_administrativo else '',
                            'documento_num': tram.documento_administrativo.num_documento if tram.documento_administrativo else '',
                            'documento_ano': tram.documento_administrativo.ano_documento if tram.documento_administrativo else '',
                            'documento_assunto': tram.documento_administrativo.txt_assunto if tram.documento_administrativo else '',
                            'documento_interessado': tram.documento_administrativo.txt_interessado if tram.documento_administrativo else '',
                            'documento_sigla': tram.documento_administrativo.tipo_documento_administrativo.sgl_tipo_documento if tram.documento_administrativo and tram.documento_administrativo.tipo_documento_administrativo else '',
                        })
                
                # OTIMIZAÇÃO: Carrega autoria em batch para todas as matérias (evita N+1 queries)
                cod_materias_para_autoria = [
                    tram['cod_materia'] for tram in todas_tramitacoes 
                    if tram['tipo'] == 'MATERIA' and tram.get('cod_materia')
                ]
                if cod_materias_para_autoria:
                    autoria_batch = _get_autoria_batch(session, cod_materias_para_autoria)
                    query_count += 1  # MONITORAMENTO
                    # Adiciona autoria às tramitações
                    for tram in todas_tramitacoes:
                        if tram['tipo'] == 'MATERIA' and tram.get('cod_materia'):
                            tram['materia_autoria'] = autoria_batch.get(tram['cod_materia'], '')
                
                # Aplica filtro de interessado/apuração (após carregar autoria)
                # Este filtro precisa ser aplicado após carregar dados porque autoria/interessado
                # não estão diretamente nas queries SQL iniciais
                if filtro_interessado:
                    todas_tramitacoes = [
                        tram for tram in todas_tramitacoes
                        if (
                            (tram['tipo'] == 'MATERIA' and filtro_interessado.lower() in (tram.get('materia_autoria') or '').lower()) or
                            (tram['tipo'] == 'DOCUMENTO' and filtro_interessado.lower() in (tram.get('documento_interessado') or '').lower())
                        )
                    ]
                
                # Aplica filtro de busca em autoria/interessado (complementa busca nas queries SQL)
                # A busca em ementa/assunto/número já foi aplicada nas queries SQL, mas busca em autoria/interessado
                # precisa ser feita aqui porque esses dados são carregados depois
                # Nota: Se busca_termo foi usado, os resultados já foram filtrados por ementa/assunto/número nas queries SQL.
                # Aqui, complementamos mantendo também os que têm o termo em autoria/interessado.
                # Como os dados já passaram pelo filtro SQL, mantemos todos (já filtrados por ementa/assunto/número)
                # e também incluímos os que têm o termo em autoria/interessado.
                # Na prática, se busca_termo existe, os dados já estão filtrados corretamente pelas queries SQL.
                
                # Remove duplicatas (mesma lógica do script antigo caixa_entrada_pysc.py linhas 28-32)
                # O script antigo remove duplicatas baseado apenas no cod_tramitacao
                tramitacoes_dict = {}
                for tram in todas_tramitacoes:
                    # Usa apenas cod_tramitacao como chave (mesma lógica do script antigo)
                    cod_tramitacao = tram['cod_tramitacao']
                    if cod_tramitacao not in tramitacoes_dict:
                        tramitacoes_dict[cod_tramitacao] = tram
                
                # Ordenação final: aplica ordenação completa (data, tipo, ano, número)
                # Isso garante que MATERIA vem antes de DOCUMENTO quando datas são iguais
                # IMPORTANTE: Todos os filtros já foram aplicados nas queries SQL acima:
                # - filtro_tipo (MATERIA/DOCUMENTO) - aplicado nas linhas 741, 876
                # - filtro_tipo_materia (sigla) - aplicado nas linhas 771-776, 838-843
                # - filtro_tipo_documento (sigla) - aplicado nas linhas 907-912, 975-980
                # - cod_unid_tramitacao_filtro (unidade) - aplicado na linha 727
                # A ordenação é aplicada após os filtros, garantindo que os resultados estejam
                # ordenados corretamente dentro do conjunto filtrado.
                tramitacoes_unicas = _ordenar_lista_tramitacoes(
                    list(tramitacoes_dict.values()),
                    ordenacao
                )
                
                # Estatísticas: calculadas ANTES da paginação, após todos os filtros serem aplicados
                # Isso garante que os totais reflitam o conjunto completo de resultados filtrados,
                # não apenas os da página atual.
                total_materias = sum(1 for t in tramitacoes_unicas if t['tipo'] == 'MATERIA')
                total_documentos = sum(1 for t in tramitacoes_unicas if t['tipo'] == 'DOCUMENTO')
                total_geral = len(tramitacoes_unicas)
                
                # Aplica paginação se fornecida
                limit = None
                offset = 0
                
                # Em Zope, request.form funciona tanto para GET (query string) quanto POST
                # Mas vamos tentar também request.get() como fallback
                limit_str = self.request.form.get('limit', '') or self.request.get('limit', '')
                if limit_str:
                    try:
                        limit_val = int(limit_str)
                        if limit_val > 0:  # limit=0 significa sem limite
                            limit = limit_val
                    except (ValueError, TypeError):
                        pass
                
                # Tenta obter offset do request.form ou request.get()
                offset_str = self.request.form.get('offset', '') or self.request.get('offset', '')
                if offset_str:
                    try:
                        offset = int(offset_str)
                        if offset < 0:
                            offset = 0
                    except (ValueError, TypeError):
                        offset = 0
                
                # Paginação: aplicada DEPOIS de todos os filtros e ordenação
                # IMPORTANTE: Os filtros são sempre processados no backend (queries SQL),
                # garantindo que a paginação seja feita sobre o conjunto completo de resultados filtrados.
                # Isso garante que:
                # 1. Os totais (total, total_materias, total_documentos) reflitam todos os resultados filtrados
                # 2. A navegação entre páginas mantenha os mesmos filtros aplicados
                # 3. A performance seja otimizada (filtros aplicados no banco, não em memória)
                if limit is not None:
                    tramitacoes_paginadas = tramitacoes_unicas[offset:offset + limit]
                else:
                    tramitacoes_paginadas = tramitacoes_unicas[offset:]
                
                # Obtém nome da unidade se houver filtro por unidade específica
                nome_unidade_filtro = None
                if cod_unid_tramitacao_filtro:
                    # Busca a unidade para obter o nome
                    unidade_filtro = session.query(UnidadeTramitacao).filter(
                        UnidadeTramitacao.cod_unid_tramitacao == cod_unid_tramitacao_filtro
                    ).first()
                    if unidade_filtro:
                        nome_unidade_filtro = _get_nome_unidade_tramitacao(unidade_filtro)
                
                dados = {
                    'tramitacoes': tramitacoes_paginadas,
                    'total': total_geral,  # Total geral, não apenas da página
                    'total_materias': total_materias,
                    'total_documentos': total_documentos,
                    'filtro_tipo': filtro_tipo or 'TODOS',
                    'titulo': 'Caixa de Entrada Unificada - Todas as Tramitações',
                    'mostrar_unidade_breadcrumb': cod_unid_tramitacao_filtro is not None,  # Só mostra unidade se houver filtro
                    'cod_unid_tramitacao_filtro': cod_unid_tramitacao_filtro,
                    'nome_unidade_filtro': nome_unidade_filtro
                }
                
                # MONITORAMENTO: Registra performance
                elapsed_time = time.time() - start_time
                _log_performance('caixa_entrada', elapsed_time, query_count)
                
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps(dados, default=str)
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Erro ao obter caixa de entrada unificada (tempo: {elapsed_time:.2f}s): {e}", exc_info=True)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps({'erro': f'Erro ao carregar tramitações: {str(e)}'})


class TramitacaoRascunhosView(GrokView, TramitacaoAPIBase):
    """View para rascunhos unificados (ambos os tipos)"""
    
    context(Interface)
    name('tramitacao_rascunhos_json')
    require('zope2.View')
    
    def render(self):
        """Retorna rascunhos (tramitações não enviadas) em JSON"""
        # O require('zope2.View') já garante autenticação
        
        # MONITORAMENTO: Inicia contagem de tempo e queries
        start_time = time.time()
        query_count = 0
        
        filtro_tipo = self.request.form.get('tipo', '')
        
        # Filtros por tipo específico de matéria ou documento
        filtro_tipo_materia = self.request.form.get('tipo_materia', '').strip()
        filtro_tipo_documento = self.request.form.get('tipo_documento', '').strip()
        
        # Parâmetros de busca e filtros avançados (aplicados no backend para todos os resultados)
        busca_termo = self.request.form.get('busca', '').strip()
        filtro_numero = self.request.form.get('numero', '').strip()
        filtro_ano = self.request.form.get('ano', '').strip()
        filtro_interessado = self.request.form.get('interessado', '').strip()
        filtro_status = self.request.form.get('status', '').strip()
        filtro_data_inicial = self.request.form.get('data_inicial', '').strip()
        filtro_data_final = self.request.form.get('data_final', '').strip()
        
        # Parâmetro de ordenação (asc ou desc, padrão: asc)
        ordenacao = self.request.form.get('ordenacao', 'asc').lower()
        if ordenacao not in ['asc', 'desc']:
            ordenacao = 'asc'
        
        # Usa context manager para leitura
        try:
            with db_session_readonly() as session:
                # Obtém código do usuário - apenas via método _get_cod_usuario (maior segurança)
                cod_usuario = self._get_cod_usuario()
                
                if not cod_usuario:
                    logger.warning("Não foi possível obter cod_usuario para rascunhos")
                    dados = {
                        'tramitacoes': [],
                        'total': 0,
                        'total_materias': 0,
                        'total_documentos': 0,
                        'filtro_tipo': filtro_tipo or 'TODOS',
                        'titulo': 'Rascunhos - Todas as Tramitações',
                        'erro': 'Não foi possível identificar o usuário. Verifique se está autenticado.'
                    }
                    self.request.response.setHeader('Content-Type', 'application/json')
                    return json.dumps(dados, default=str)
                
                # Rascunhos são por usuário, não por unidade
                # Não filtra por unidade - mostra todos os rascunhos do usuário
                
                # OTIMIZAÇÃO: Lê parâmetros de paginação antes das queries
                limit = None
                offset = 0
                limit_str = self.request.form.get('limit', '')
                if limit_str:
                    try:
                        limit_val = int(limit_str)
                        if limit_val > 0:
                            limit = limit_val
                        elif limit_val == 0:
                            limit = None  # limit=0 significa sem limite
                    except (ValueError, TypeError):
                        pass
                
                offset_str = self.request.form.get('offset', '')
                if offset_str:
                    try:
                        offset = int(offset_str)
                        if offset < 0:
                            offset = 0
                    except (ValueError, TypeError):
                        offset = 0
                
                todas_tramitacoes = []
                
                # ✅ CRÍTICO: Calcula total real ANTES de aplicar paginação SQL
                # Isso é necessário para que a paginação funcione corretamente
                total_materias_count = 0
                total_documentos_count = 0
                if limit is not None:
                    # Calcula total de matérias
                    if not filtro_tipo or filtro_tipo == 'MATERIA':
                        filtros_materia_count = [
                            Tramitacao.cod_usuario_local == cod_usuario,
                            Tramitacao.ind_ult_tramitacao == 0,
                            Tramitacao.ind_excluido == 0,
                            Tramitacao.dat_encaminha.is_(None)
                        ]
                        query_count_materia = session.query(func.count(Tramitacao.cod_tramitacao)).filter(
                            *filtros_materia_count
                        ).join(
                            MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
                        ).filter(
                            MateriaLegislativa.ind_tramitacao == 1,
                            MateriaLegislativa.ind_excluido == 0
                        )
                        
                        # Aplica filtros avançados
                        if filtro_tipo_materia:
                            query_count_materia = query_count_materia.join(
                                TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
                            ).filter(
                                TipoMateriaLegislativa.sgl_tipo_materia == filtro_tipo_materia
                            )
                        if filtro_numero:
                            query_count_materia = query_count_materia.filter(MateriaLegislativa.num_ident_basica.like(f'%{filtro_numero}%'))
                        if filtro_ano:
                            query_count_materia = query_count_materia.filter(MateriaLegislativa.ano_ident_basica.like(f'%{filtro_ano}%'))
                        if filtro_status:
                            query_count_materia = query_count_materia.join(
                                StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
                            ).filter(StatusTramitacao.des_status == filtro_status)
                        if filtro_data_inicial:
                            try:
                                from datetime import datetime
                                data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                                query_count_materia = query_count_materia.filter(Tramitacao.dat_tramitacao >= data_inicial_obj)
                            except (ValueError, TypeError):
                                pass
                        if filtro_data_final:
                            try:
                                from datetime import datetime
                                data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                                data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                                query_count_materia = query_count_materia.filter(Tramitacao.dat_tramitacao <= data_final_obj)
                            except (ValueError, TypeError):
                                pass
                        if busca_termo:
                            query_count_materia = query_count_materia.filter(
                                or_(
                                    MateriaLegislativa.txt_ementa.like(f'%{busca_termo}%'),
                                    func.concat(MateriaLegislativa.num_ident_basica, '/', MateriaLegislativa.ano_ident_basica).like(f'%{busca_termo}%')
                                )
                            )
                        
                        total_materias_count = query_count_materia.scalar() or 0
                        query_count += 1
                    
                    # Calcula total de documentos
                    if not filtro_tipo or filtro_tipo == 'DOCUMENTO':
                        filtros_doc_count = [
                            TramitacaoAdministrativo.cod_usuario_local == cod_usuario,
                            TramitacaoAdministrativo.ind_ult_tramitacao == 0,
                            TramitacaoAdministrativo.ind_excluido == 0,
                            TramitacaoAdministrativo.dat_encaminha.is_(None)
                        ]
                        query_count_doc = session.query(func.count(TramitacaoAdministrativo.cod_tramitacao)).filter(
                            *filtros_doc_count
                        ).join(
                            DocumentoAdministrativo, TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
                        ).filter(
                            DocumentoAdministrativo.ind_tramitacao == 1,
                            DocumentoAdministrativo.ind_excluido == 0
                        )
                        
                        # Aplica filtros avançados
                        if filtro_tipo_documento:
                            query_count_doc = query_count_doc.join(
                                TipoDocumentoAdministrativo, DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento
                            ).filter(
                                TipoDocumentoAdministrativo.sgl_tipo_documento == filtro_tipo_documento
                            )
                        if filtro_numero:
                            query_count_doc = query_count_doc.filter(DocumentoAdministrativo.num_documento.like(f'%{filtro_numero}%'))
                        if filtro_ano:
                            query_count_doc = query_count_doc.filter(DocumentoAdministrativo.ano_documento.like(f'%{filtro_ano}%'))
                        if filtro_interessado:
                            query_count_doc = query_count_doc.filter(DocumentoAdministrativo.txt_interessado.like(f'%{filtro_interessado}%'))
                        if filtro_status:
                            query_count_doc = query_count_doc.join(
                                StatusTramitacaoAdministrativo, TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status
                            ).filter(StatusTramitacaoAdministrativo.des_status == filtro_status)
                        if filtro_data_inicial:
                            try:
                                from datetime import datetime
                                data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                                query_count_doc = query_count_doc.filter(TramitacaoAdministrativo.dat_tramitacao >= data_inicial_obj)
                            except (ValueError, TypeError):
                                pass
                        if filtro_data_final:
                            try:
                                from datetime import datetime
                                data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                                data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                                query_count_doc = query_count_doc.filter(TramitacaoAdministrativo.dat_tramitacao <= data_final_obj)
                            except (ValueError, TypeError):
                                pass
                        if busca_termo:
                            query_count_doc = query_count_doc.filter(
                                or_(
                                    DocumentoAdministrativo.txt_assunto.like(f'%{busca_termo}%'),
                                    DocumentoAdministrativo.txt_interessado.like(f'%{busca_termo}%'),
                                    func.concat(DocumentoAdministrativo.num_documento, '/', DocumentoAdministrativo.ano_documento).like(f'%{busca_termo}%')
                                )
                            )
                        
                        total_documentos_count = query_count_doc.scalar() or 0
                        query_count += 1
                
                # Busca rascunhos de MATÉRIAS
                # Rascunho = ind_ult_tramitacao == 0 (não é última tramitação) E dat_encaminha IS NULL (não foi enviado)
                if not filtro_tipo or filtro_tipo == 'MATERIA':
                    filtros_materia = [
                        Tramitacao.cod_usuario_local == cod_usuario,
                        Tramitacao.ind_ult_tramitacao == 0,  # Rascunho não é última tramitação
                        Tramitacao.ind_excluido == 0,
                        Tramitacao.dat_encaminha.is_(None)  # Rascunho = não encaminhado (não foi enviado)
                    ]
                    # Não filtra por unidade - rascunhos são por usuário
                    
                    query_materia = session.query(Tramitacao).options(
                    selectinload(Tramitacao.status_tramitacao),
                    selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                    selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                    selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                    selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                    selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                    selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                        selectinload(Tramitacao.materia_legislativa).selectinload(MateriaLegislativa.tipo_materia_legislativa)
                    ).filter(*filtros_materia).join(
                        MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
                    ).filter(
                        MateriaLegislativa.ind_tramitacao == 1,
                        MateriaLegislativa.ind_excluido == 0
                    )
                    
                    # Aplica filtros avançados
                    if filtro_tipo_materia:
                        query_materia = query_materia.join(
                            TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
                        ).filter(
                            TipoMateriaLegislativa.sgl_tipo_materia == filtro_tipo_materia
                        )
                    if filtro_numero:
                        query_materia = query_materia.filter(MateriaLegislativa.num_ident_basica.like(f'%{filtro_numero}%'))
                    if filtro_ano:
                        query_materia = query_materia.filter(MateriaLegislativa.ano_ident_basica.like(f'%{filtro_ano}%'))
                    if filtro_status:
                        query_materia = query_materia.join(
                            StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
                        ).filter(StatusTramitacao.des_status == filtro_status)
                    if filtro_data_inicial:
                        try:
                            from datetime import datetime
                            data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                            query_materia = query_materia.filter(Tramitacao.dat_tramitacao >= data_inicial_obj)
                        except (ValueError, TypeError):
                            pass
                    if filtro_data_final:
                        try:
                            from datetime import datetime
                            data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                            data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                            query_materia = query_materia.filter(Tramitacao.dat_tramitacao <= data_final_obj)
                        except (ValueError, TypeError):
                            pass
                    if busca_termo:
                        query_materia = query_materia.filter(
                            or_(
                                MateriaLegislativa.txt_ementa.like(f'%{busca_termo}%'),
                                func.concat(MateriaLegislativa.num_ident_basica, '/', MateriaLegislativa.ano_ident_basica).like(f'%{busca_termo}%')
                            )
                        )
                    
                    # Aplica ordenação completa (data, ano, número)
                    # Para rascunhos, usa dat_tramitacao em vez de dat_encaminha (rascunhos não têm dat_encaminha)
                    from openlegis.sagl.models.models import MateriaLegislativa as ML
                    
                    # Detecta se é MySQL
                    is_mysql = False
                    try:
                        bind = None
                        if hasattr(query_materia, 'session') and query_materia.session:
                            bind = getattr(query_materia.session, 'bind', None)
                        elif hasattr(query_materia, '_bind'):
                            bind = query_materia._bind
                        elif hasattr(query_materia, 'bind'):
                            bind = query_materia.bind
                        if bind:
                            dialect_name = getattr(bind.dialect, 'name', None) if hasattr(bind, 'dialect') else None
                            is_mysql = dialect_name == 'mysql' or dialect_name == 'pymysql'
                        else:
                            is_mysql = True
                    except:
                        is_mysql = True
                    
                    # Ordenação primária: dat_tramitacao
                    if is_mysql:
                        if ordenacao == 'desc':
                            query_materia = query_materia.order_by(func.isnull(Tramitacao.dat_tramitacao).asc(), Tramitacao.dat_tramitacao.desc())
                        else:
                            query_materia = query_materia.order_by(func.isnull(Tramitacao.dat_tramitacao).asc(), Tramitacao.dat_tramitacao.asc())
                    else:
                        if ordenacao == 'desc':
                            query_materia = query_materia.order_by(Tramitacao.dat_tramitacao.desc().nulls_last())
                        else:
                            query_materia = query_materia.order_by(Tramitacao.dat_tramitacao.asc().nulls_last())
                    
                    # Ordenação terciária: ano da matéria
                    if is_mysql:
                        if ordenacao == 'desc':
                            query_materia = query_materia.order_by(func.isnull(ML.ano_ident_basica).asc(), ML.ano_ident_basica.desc())
                            query_materia = query_materia.order_by(func.isnull(ML.num_ident_basica).asc(), ML.num_ident_basica.desc())
                        else:
                            query_materia = query_materia.order_by(func.isnull(ML.ano_ident_basica).asc(), ML.ano_ident_basica.asc())
                            query_materia = query_materia.order_by(func.isnull(ML.num_ident_basica).asc(), ML.num_ident_basica.asc())
                    else:
                        if ordenacao == 'desc':
                            query_materia = query_materia.order_by(ML.ano_ident_basica.desc().nulls_last())
                            query_materia = query_materia.order_by(ML.num_ident_basica.desc().nulls_last())
                        else:
                            query_materia = query_materia.order_by(ML.ano_ident_basica.asc().nulls_last())
                            query_materia = query_materia.order_by(ML.num_ident_basica.asc().nulls_last())
                    
                    # OTIMIZAÇÃO: Aplica paginação SQL quando possível
                    # Se há limit, busca um pouco mais (limit * 2 + offset) para garantir dados suficientes após merge
                    # NÃO aplica offset aqui - será aplicado em Python após mesclar e ordenar
                    if limit is not None:
                        # Busca mais dados para garantir que temos suficientes após mesclar com documentos
                        # Calcula quantos itens precisamos: offset + limit * 2 (para garantir dados após merge)
                        query_materia = query_materia.limit(offset + (limit * 2))
                    
                    rascunhos_materia = query_materia.all()
                    query_count += 1  # MONITORAMENTO
                    
                    for tram in rascunhos_materia:
                        cod_materia = tram.cod_materia
                        todas_tramitacoes.append({
                        'tipo': 'MATERIA',
                        'cod_tramitacao': tram.cod_tramitacao,
                        'cod_entidade': cod_materia,
                        'dat_tramitacao': tram.dat_tramitacao.isoformat() if tram.dat_tramitacao else None,
                        'dat_fim_prazo': tram.dat_fim_prazo.isoformat() if tram.dat_fim_prazo else None,
                        'des_status': tram.status_tramitacao.des_status if tram.status_tramitacao else '',
                        'unidade_origem': _get_nome_unidade_tramitacao(tram.unidade_tramitacao_),
                        'unidade_destino': _get_nome_unidade_tramitacao(tram.unidade_tramitacao),
                        'materia_des_tipo': tram.materia_legislativa.tipo_materia_legislativa.des_tipo_materia if tram.materia_legislativa and tram.materia_legislativa.tipo_materia_legislativa else '',
                        'materia_num': tram.materia_legislativa.num_ident_basica if tram.materia_legislativa else '',
                        'materia_ano': tram.materia_legislativa.ano_ident_basica if tram.materia_legislativa else '',
                        'materia_ementa': tram.materia_legislativa.txt_ementa if tram.materia_legislativa else '',
                            'materia_sigla': tram.materia_legislativa.tipo_materia_legislativa.sgl_tipo_materia if tram.materia_legislativa and tram.materia_legislativa.tipo_materia_legislativa else '',
                            # Autoria será adicionada em batch depois
                        })
                
                # Busca rascunhos de DOCUMENTOS
                # Rascunho = ind_ult_tramitacao == 0 (não é última tramitação) E dat_encaminha IS NULL (não foi enviado)
                if not filtro_tipo or filtro_tipo == 'DOCUMENTO':
                    filtros_doc = [
                        TramitacaoAdministrativo.cod_usuario_local == cod_usuario,
                        TramitacaoAdministrativo.ind_ult_tramitacao == 0,  # Rascunho não é última tramitação
                        TramitacaoAdministrativo.ind_excluido == 0,
                        TramitacaoAdministrativo.dat_encaminha.is_(None)  # Rascunho = não encaminhado (não foi enviado)
                    ]
                    # Não filtra por unidade - rascunhos são por usuário
                    
                    query_doc = session.query(TramitacaoAdministrativo).options(
                    selectinload(TramitacaoAdministrativo.status_tramitacao_administrativo),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                        selectinload(TramitacaoAdministrativo.documento_administrativo).selectinload(DocumentoAdministrativo.tipo_documento_administrativo)
                    ).filter(*filtros_doc).join(
                        DocumentoAdministrativo, TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
                    ).filter(
                        DocumentoAdministrativo.ind_tramitacao == 1,
                        DocumentoAdministrativo.ind_excluido == 0
                    )
                    
                    # Aplica filtros avançados
                    if filtro_tipo_documento:
                        query_doc = query_doc.join(
                            TipoDocumentoAdministrativo, DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento
                        ).filter(
                            TipoDocumentoAdministrativo.sgl_tipo_documento == filtro_tipo_documento
                        )
                    if filtro_numero:
                        query_doc = query_doc.filter(DocumentoAdministrativo.num_documento.like(f'%{filtro_numero}%'))
                    if filtro_ano:
                        query_doc = query_doc.filter(DocumentoAdministrativo.ano_documento.like(f'%{filtro_ano}%'))
                    if filtro_interessado:
                        query_doc = query_doc.filter(DocumentoAdministrativo.txt_interessado.like(f'%{filtro_interessado}%'))
                    if filtro_status:
                        query_doc = query_doc.join(
                            StatusTramitacaoAdministrativo, TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status
                        ).filter(StatusTramitacaoAdministrativo.des_status == filtro_status)
                    if filtro_data_inicial:
                        try:
                            from datetime import datetime
                            data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                            query_doc = query_doc.filter(TramitacaoAdministrativo.dat_tramitacao >= data_inicial_obj)
                        except (ValueError, TypeError):
                            pass
                    if filtro_data_final:
                        try:
                            from datetime import datetime
                            data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                            data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                            query_doc = query_doc.filter(TramitacaoAdministrativo.dat_tramitacao <= data_final_obj)
                        except (ValueError, TypeError):
                            pass
                    if busca_termo:
                        query_doc = query_doc.filter(
                            or_(
                                DocumentoAdministrativo.txt_assunto.like(f'%{busca_termo}%'),
                                DocumentoAdministrativo.txt_interessado.like(f'%{busca_termo}%'),
                                func.concat(DocumentoAdministrativo.num_documento, '/', DocumentoAdministrativo.ano_documento).like(f'%{busca_termo}%')
                            )
                        )
                    
                    # Aplica ordenação completa (data, ano, número)
                    # Para rascunhos, usa dat_tramitacao em vez de dat_encaminha
                    from openlegis.sagl.models.models import DocumentoAdministrativo as DA
                    
                    # Detecta se é MySQL
                    is_mysql = False
                    try:
                        bind = None
                        if hasattr(query_doc, 'session') and query_doc.session:
                            bind = getattr(query_doc.session, 'bind', None)
                        elif hasattr(query_doc, '_bind'):
                            bind = query_doc._bind
                        elif hasattr(query_doc, 'bind'):
                            bind = query_doc.bind
                        if bind:
                            dialect_name = getattr(bind.dialect, 'name', None) if hasattr(bind, 'dialect') else None
                            is_mysql = dialect_name == 'mysql' or dialect_name == 'pymysql'
                        else:
                            is_mysql = True
                    except:
                        is_mysql = True
                    
                    # Ordenação primária: dat_tramitacao
                    if is_mysql:
                        if ordenacao == 'desc':
                            query_doc = query_doc.order_by(func.isnull(TramitacaoAdministrativo.dat_tramitacao).asc(), TramitacaoAdministrativo.dat_tramitacao.desc())
                        else:
                            query_doc = query_doc.order_by(func.isnull(TramitacaoAdministrativo.dat_tramitacao).asc(), TramitacaoAdministrativo.dat_tramitacao.asc())
                    else:
                        if ordenacao == 'desc':
                            query_doc = query_doc.order_by(TramitacaoAdministrativo.dat_tramitacao.desc().nulls_last())
                        else:
                            query_doc = query_doc.order_by(TramitacaoAdministrativo.dat_tramitacao.asc().nulls_last())
                    
                    # Ordenação terciária: ano do documento
                    if is_mysql:
                        if ordenacao == 'desc':
                            query_doc = query_doc.order_by(func.isnull(DA.ano_documento).asc(), DA.ano_documento.desc())
                            query_doc = query_doc.order_by(func.isnull(DA.num_documento).asc(), DA.num_documento.desc())
                        else:
                            query_doc = query_doc.order_by(func.isnull(DA.ano_documento).asc(), DA.ano_documento.asc())
                            query_doc = query_doc.order_by(func.isnull(DA.num_documento).asc(), DA.num_documento.asc())
                    else:
                        if ordenacao == 'desc':
                            query_doc = query_doc.order_by(DA.ano_documento.desc().nulls_last())
                            query_doc = query_doc.order_by(DA.num_documento.desc().nulls_last())
                        else:
                            query_doc = query_doc.order_by(DA.ano_documento.asc().nulls_last())
                            query_doc = query_doc.order_by(DA.num_documento.asc().nulls_last())
                    
                    # OTIMIZAÇÃO: Aplica paginação SQL quando possível
                    # NÃO aplica offset aqui - será aplicado em Python após mesclar e ordenar
                    if limit is not None:
                        # Busca mais dados para garantir que temos suficientes após mesclar com matérias
                        # Calcula quantos itens precisamos: offset + limit * 2 (para garantir dados após merge)
                        query_doc = query_doc.limit(offset + (limit * 2))
                    
                    rascunhos_doc = query_doc.all()
                    query_count += 1  # MONITORAMENTO
                    
                    for tram in rascunhos_doc:
                        todas_tramitacoes.append({
                        'tipo': 'DOCUMENTO',
                        'cod_tramitacao': tram.cod_tramitacao,
                        'cod_entidade': tram.cod_documento,
                        'dat_tramitacao': tram.dat_tramitacao.isoformat() if tram.dat_tramitacao else None,
                        'dat_fim_prazo': tram.dat_fim_prazo.isoformat() if tram.dat_fim_prazo else None,
                        'des_status': tram.status_tramitacao_administrativo.des_status if tram.status_tramitacao_administrativo else '',
                        'unidade_origem': _get_nome_unidade_tramitacao(tram.unidade_tramitacao_),
                        'unidade_destino': _get_nome_unidade_tramitacao(tram.unidade_tramitacao),
                        'documento_des_tipo': tram.documento_administrativo.tipo_documento_administrativo.des_tipo_documento if tram.documento_administrativo and tram.documento_administrativo.tipo_documento_administrativo else '',
                        'documento_num': tram.documento_administrativo.num_documento if tram.documento_administrativo else '',
                        'documento_ano': tram.documento_administrativo.ano_documento if tram.documento_administrativo else '',
                        'documento_assunto': tram.documento_administrativo.txt_assunto if tram.documento_administrativo else '',
                        'documento_sigla': tram.documento_administrativo.tipo_documento_administrativo.sgl_tipo_documento if tram.documento_administrativo and tram.documento_administrativo.tipo_documento_administrativo else '',
                            'documento_interessado': tram.documento_administrativo.txt_interessado if tram.documento_administrativo else '',
                        })
                
                # OTIMIZAÇÃO: Carrega autoria em batch para todas as matérias (evita N+1 queries)
                cod_materias_para_autoria = [
                    tram.get('cod_entidade') or tram.get('cod_materia') for tram in todas_tramitacoes 
                    if tram['tipo'] == 'MATERIA' and (tram.get('cod_entidade') or tram.get('cod_materia'))
                ]
                if cod_materias_para_autoria:
                    autoria_batch = _get_autoria_batch(session, cod_materias_para_autoria)
                    query_count += 1  # MONITORAMENTO
                    # Adiciona autoria às tramitações
                    for tram in todas_tramitacoes:
                        if tram['tipo'] == 'MATERIA':
                            cod_materia = tram.get('cod_entidade') or tram.get('cod_materia')
                            if cod_materia:
                                tram['materia_autoria'] = autoria_batch.get(cod_materia, '')
                
                # Ordenação final: aplica ordenação completa (data, tipo, ano, número)
                # Para rascunhos, usa dat_tramitacao em vez de dat_encaminha
                def chave_ordenacao_rascunho(tram):
                    # Ordenação primária: dat_tramitacao (rascunhos não têm dat_encaminha)
                    dat_tramitacao = tram.get('dat_tramitacao') or ''
                    # Ordenação secundária: tipo (MATERIA=1, DOCUMENTO=2)
                    tipo_ordem = 1 if tram.get('tipo') == 'MATERIA' else 2
                    # Ordenação terciária: ano
                    if tram.get('tipo') == 'MATERIA':
                        ano = int(tram.get('materia_ano') or 0)
                        num = int(tram.get('materia_num') or 0)
                    else:
                        ano = int(tram.get('documento_ano') or 0)
                        num = int(tram.get('documento_num') or 0)
                    return (dat_tramitacao, tipo_ordem, ano, num)
                
                todas_tramitacoes.sort(key=chave_ordenacao_rascunho, reverse=(ordenacao == 'desc'))
                
                # Estatísticas
                # Se já calculamos o total via COUNT, usa esses valores
                # Caso contrário, calcula a partir dos resultados retornados
                if limit is not None and (total_materias_count > 0 or total_documentos_count > 0):
                    # Usa totais calculados via COUNT (mais preciso)
                    total_materias = total_materias_count
                    total_documentos = total_documentos_count
                    total_geral = total_materias + total_documentos
                else:
                    # Sem paginação ou sem COUNT, calcula a partir dos resultados
                    total_materias = sum(1 for t in todas_tramitacoes if t['tipo'] == 'MATERIA')
                    total_documentos = sum(1 for t in todas_tramitacoes if t['tipo'] == 'DOCUMENTO')
                    total_geral = len(todas_tramitacoes)
                
                # Paginação já foi aplicada parcialmente no SQL, agora aplica final em Python
                # (necessário porque mesclamos resultados de matérias e documentos)
                
                # Aplica limit e offset
                if limit is not None:
                    tramitacoes_paginadas = todas_tramitacoes[offset:offset + limit]
                else:
                    tramitacoes_paginadas = todas_tramitacoes[offset:]
                
                dados = {
                    'tramitacoes': tramitacoes_paginadas,
                    'total': total_geral,  # Total geral, não apenas da página
                    'total_materias': total_materias,
                    'total_documentos': total_documentos,
                    'filtro_tipo': filtro_tipo or 'TODOS',
                    'mostrar_unidade_breadcrumb': False,  # Rascunhos são do usuário, não da unidade
                    'cod_unid_tramitacao_filtro': None,
                    'nome_unidade_filtro': None
                }
                
                # MONITORAMENTO: Registra performance
                elapsed_time = time.time() - start_time
                _log_performance('rascunhos', elapsed_time, query_count)
                
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps(dados, default=str)
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Erro ao obter rascunhos (tempo: {elapsed_time:.2f}s): {e}", exc_info=True)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps({'erro': f'Erro ao carregar rascunhos: {str(e)}'})


class TramitacaoItensEnviadosView(GrokView, TramitacaoAPIBase):
    """View para itens enviados unificados (ambos os tipos)"""
    
    context(Interface)
    name('tramitacao_itens_enviados_json')
    require('zope2.View')
    
    def render(self):
        """Retorna itens enviados (tramitações encaminhadas mas não recebidas) em JSON"""
        # O require('zope2.View') já garante autenticação
        
        # MONITORAMENTO: Inicia contagem de tempo e queries
        start_time = time.time()
        query_count = 0
        
        filtro_tipo = self.request.form.get('tipo', '')
        
        # Filtros por tipo específico de matéria ou documento
        filtro_tipo_materia = self.request.form.get('tipo_materia', '').strip()
        filtro_tipo_documento = self.request.form.get('tipo_documento', '').strip()
        
        # Parâmetros de busca e filtros avançados (aplicados no backend para todos os resultados)
        busca_termo = self.request.form.get('busca', '').strip()
        filtro_numero = self.request.form.get('numero', '').strip()
        filtro_ano = self.request.form.get('ano', '').strip()
        filtro_interessado = self.request.form.get('interessado', '').strip()
        filtro_status = self.request.form.get('status', '').strip()
        filtro_data_inicial = self.request.form.get('data_inicial', '').strip()
        filtro_data_final = self.request.form.get('data_final', '').strip()
        
        # Parâmetro de ordenação (asc ou desc, padrão: asc)
        ordenacao = self.request.form.get('ordenacao', 'asc').lower()
        if ordenacao not in ['asc', 'desc']:
            ordenacao = 'asc'
        
        # Usa context manager para leitura
        try:
            with db_session_readonly() as session:
                # Obtém código do usuário - apenas via método _get_cod_usuario (maior segurança)
                cod_usuario = self._get_cod_usuario()
                
                if not cod_usuario:
                    logger.warning("Não foi possível obter cod_usuario para itens enviados")
                    dados = {
                        'tramitacoes': [],
                        'total': 0,
                        'total_materias': 0,
                        'total_documentos': 0,
                        'filtro_tipo': filtro_tipo or 'TODOS',
                        'titulo': 'Itens Enviados - Todas as Tramitações',
                        'erro': 'Não foi possível identificar o usuário. Verifique se está autenticado.'
                    }
                    self.request.response.setHeader('Content-Type', 'application/json')
                    return json.dumps(dados, default=str)
                
                # Itens enviados são por usuário, não por unidade
                # Não filtra por unidade - mostra todos os itens enviados do usuário
                
                # OTIMIZAÇÃO: Lê parâmetros de paginação antes das queries
                limit = None
                offset = 0
                limit_str = self.request.form.get('limit', '')
                if limit_str:
                    try:
                        limit_val = int(limit_str)
                        if limit_val > 0:
                            limit = limit_val
                        elif limit_val == 0:
                            limit = None  # limit=0 significa sem limite
                    except (ValueError, TypeError):
                        pass
                
                offset_str = self.request.form.get('offset', '')
                if offset_str:
                    try:
                        offset = int(offset_str)
                        if offset < 0:
                            offset = 0
                    except (ValueError, TypeError):
                        offset = 0
                
                todas_tramitacoes = []
                
                # ✅ CRÍTICO: Calcula total real ANTES de aplicar paginação SQL
                # Isso é necessário para que a paginação funcione corretamente
                total_materias_count = 0
                total_documentos_count = 0
                if limit is not None:
                    # Calcula total de matérias
                    if not filtro_tipo or filtro_tipo == 'MATERIA':
                        filtros_materia_count = [
                            Tramitacao.cod_usuario_local == cod_usuario,
                            Tramitacao.ind_ult_tramitacao == 1,
                            Tramitacao.dat_encaminha.isnot(None),
                            Tramitacao.dat_recebimento.is_(None),
                            Tramitacao.ind_excluido == 0
                        ]
                        query_count_materia = session.query(func.count(Tramitacao.cod_tramitacao)).filter(
                            *filtros_materia_count
                        ).join(
                            MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
                        ).filter(
                            MateriaLegislativa.ind_tramitacao == 1,
                            MateriaLegislativa.ind_excluido == 0
                        )
                        
                        # Aplica filtros avançados
                        if filtro_tipo_materia:
                            query_count_materia = query_count_materia.join(
                                TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
                            ).filter(
                                TipoMateriaLegislativa.sgl_tipo_materia == filtro_tipo_materia
                            )
                        if filtro_numero:
                            query_count_materia = query_count_materia.filter(MateriaLegislativa.num_ident_basica.like(f'%{filtro_numero}%'))
                        if filtro_ano:
                            query_count_materia = query_count_materia.filter(MateriaLegislativa.ano_ident_basica.like(f'%{filtro_ano}%'))
                        if filtro_status:
                            query_count_materia = query_count_materia.join(
                                StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
                            ).filter(StatusTramitacao.des_status == filtro_status)
                        if filtro_data_inicial:
                            try:
                                from datetime import datetime
                                data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                                query_count_materia = query_count_materia.filter(Tramitacao.dat_encaminha >= data_inicial_obj)
                            except (ValueError, TypeError):
                                pass
                        if filtro_data_final:
                            try:
                                from datetime import datetime
                                data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                                data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                                query_count_materia = query_count_materia.filter(Tramitacao.dat_encaminha <= data_final_obj)
                            except (ValueError, TypeError):
                                pass
                        if busca_termo:
                            query_count_materia = query_count_materia.filter(
                                or_(
                                    MateriaLegislativa.txt_ementa.like(f'%{busca_termo}%'),
                                    func.concat(MateriaLegislativa.num_ident_basica, '/', MateriaLegislativa.ano_ident_basica).like(f'%{busca_termo}%')
                                )
                            )
                        
                        total_materias_count = query_count_materia.scalar() or 0
                        query_count += 1
                    
                    # Calcula total de documentos
                    if not filtro_tipo or filtro_tipo == 'DOCUMENTO':
                        filtros_doc_count = [
                            TramitacaoAdministrativo.cod_usuario_local == cod_usuario,
                            TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                            TramitacaoAdministrativo.dat_encaminha.isnot(None),
                            TramitacaoAdministrativo.dat_recebimento.is_(None),
                            TramitacaoAdministrativo.ind_excluido == 0
                        ]
                        query_count_doc = session.query(func.count(TramitacaoAdministrativo.cod_tramitacao)).filter(
                            *filtros_doc_count
                        ).join(
                            DocumentoAdministrativo, TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
                        ).filter(
                            DocumentoAdministrativo.ind_tramitacao == 1,
                            DocumentoAdministrativo.ind_excluido == 0
                        )
                        
                        # Aplica filtros avançados
                        if filtro_tipo_documento:
                            query_count_doc = query_count_doc.join(
                                TipoDocumentoAdministrativo, DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento
                            ).filter(
                                TipoDocumentoAdministrativo.sgl_tipo_documento == filtro_tipo_documento
                            )
                        if filtro_numero:
                            query_count_doc = query_count_doc.filter(DocumentoAdministrativo.num_documento.like(f'%{filtro_numero}%'))
                        if filtro_ano:
                            query_count_doc = query_count_doc.filter(DocumentoAdministrativo.ano_documento.like(f'%{filtro_ano}%'))
                        if filtro_interessado:
                            query_count_doc = query_count_doc.filter(DocumentoAdministrativo.txt_interessado.like(f'%{filtro_interessado}%'))
                        if filtro_status:
                            query_count_doc = query_count_doc.join(
                                StatusTramitacaoAdministrativo, TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status
                            ).filter(StatusTramitacaoAdministrativo.des_status == filtro_status)
                        if filtro_data_inicial:
                            try:
                                from datetime import datetime
                                data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                                query_count_doc = query_count_doc.filter(TramitacaoAdministrativo.dat_encaminha >= data_inicial_obj)
                            except (ValueError, TypeError):
                                pass
                        if filtro_data_final:
                            try:
                                from datetime import datetime
                                data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                                data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                                query_count_doc = query_count_doc.filter(TramitacaoAdministrativo.dat_encaminha <= data_final_obj)
                            except (ValueError, TypeError):
                                pass
                        if busca_termo:
                            query_count_doc = query_count_doc.filter(
                                or_(
                                    DocumentoAdministrativo.txt_assunto.like(f'%{busca_termo}%'),
                                    DocumentoAdministrativo.txt_interessado.like(f'%{busca_termo}%'),
                                    func.concat(DocumentoAdministrativo.num_documento, '/', DocumentoAdministrativo.ano_documento).like(f'%{busca_termo}%')
                                )
                            )
                        
                        total_documentos_count = query_count_doc.scalar() or 0
                        query_count += 1
                
                # Busca itens enviados de MATÉRIAS
                # Itens enviados = ind_encaminha=1 AND ind_recebido=0 = dat_encaminha IS NOT NULL AND dat_recebimento IS NULL
                if not filtro_tipo or filtro_tipo == 'MATERIA':
                    filtros_materia = [
                    Tramitacao.cod_usuario_local == cod_usuario,
                    Tramitacao.ind_ult_tramitacao == 1,
                    Tramitacao.dat_encaminha.isnot(None),  # ind_encaminha = 1
                        Tramitacao.dat_recebimento.is_(None),  # ind_recebido = 0
                        Tramitacao.ind_excluido == 0
                    ]
                    # Não filtra por unidade - itens enviados são por usuário
                    
                    query_materia = session.query(Tramitacao).options(
                    selectinload(Tramitacao.status_tramitacao),
                    selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                    selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                    selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                    selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                    selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                    selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                        selectinload(Tramitacao.materia_legislativa).selectinload(MateriaLegislativa.tipo_materia_legislativa)
                    ).filter(*filtros_materia).join(
                        MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
                    ).filter(
                        MateriaLegislativa.ind_tramitacao == 1,
                        MateriaLegislativa.ind_excluido == 0
                    )
                    
                    # Aplica filtros avançados
                    if filtro_tipo_materia:
                        query_materia = query_materia.join(
                            TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
                        ).filter(
                            TipoMateriaLegislativa.sgl_tipo_materia == filtro_tipo_materia
                        )
                    if filtro_numero:
                        query_materia = query_materia.filter(MateriaLegislativa.num_ident_basica.like(f'%{filtro_numero}%'))
                    if filtro_ano:
                        query_materia = query_materia.filter(MateriaLegislativa.ano_ident_basica.like(f'%{filtro_ano}%'))
                    if filtro_status:
                        query_materia = query_materia.join(
                            StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
                        ).filter(StatusTramitacao.des_status == filtro_status)
                    if filtro_data_inicial:
                        try:
                            from datetime import datetime
                            data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                            query_materia = query_materia.filter(Tramitacao.dat_encaminha >= data_inicial_obj)
                        except (ValueError, TypeError):
                            pass
                    if filtro_data_final:
                        try:
                            from datetime import datetime
                            data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                            data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                            query_materia = query_materia.filter(Tramitacao.dat_encaminha <= data_final_obj)
                        except (ValueError, TypeError):
                            pass
                    if busca_termo:
                        query_materia = query_materia.filter(
                            or_(
                                MateriaLegislativa.txt_ementa.like(f'%{busca_termo}%'),
                                func.concat(MateriaLegislativa.num_ident_basica, '/', MateriaLegislativa.ano_ident_basica).like(f'%{busca_termo}%')
                            )
                        )
                    
                    # Aplica ordenação completa (data, ano, número)
                    query_materia = _obter_ordenacao_completa_materia(query_materia, ordenacao)
                    
                    # OTIMIZAÇÃO: Aplica paginação SQL quando possível
                    # NÃO aplica offset aqui - será aplicado em Python após mesclar e ordenar
                    if limit is not None:
                        # Busca mais dados para garantir que temos suficientes após mesclar com documentos
                        # Calcula quantos itens precisamos: offset + limit * 2 (para garantir dados após merge)
                        query_materia = query_materia.limit(offset + (limit * 2))
                    
                    itens_materia = query_materia.all()
                    query_count += 1  # MONITORAMENTO
                    
                    for tram in itens_materia:
                        cod_materia = tram.cod_materia
                        todas_tramitacoes.append({
                        'tipo': 'MATERIA',
                        'cod_tramitacao': tram.cod_tramitacao,
                        'cod_entidade': cod_materia,
                        'dat_encaminha': tram.dat_encaminha.isoformat() if tram.dat_encaminha else None,
                        'dat_visualizacao': tram.dat_visualizacao.isoformat() if tram.dat_visualizacao else None,
                        'dat_recebimento': tram.dat_recebimento.isoformat() if tram.dat_recebimento else None,
                        'cod_usuario_local': tram.cod_usuario_local,
                        'dat_fim_prazo': tram.dat_fim_prazo.isoformat() if tram.dat_fim_prazo else None,
                        'des_status': tram.status_tramitacao.des_status if tram.status_tramitacao else '',
                        'unidade_origem': _get_nome_unidade_tramitacao(tram.unidade_tramitacao_),
                        'unidade_destino': _get_nome_unidade_tramitacao(tram.unidade_tramitacao),
                        'materia_des_tipo': tram.materia_legislativa.tipo_materia_legislativa.des_tipo_materia if tram.materia_legislativa and tram.materia_legislativa.tipo_materia_legislativa else '',
                        'materia_num': tram.materia_legislativa.num_ident_basica if tram.materia_legislativa else '',
                        'materia_ano': tram.materia_legislativa.ano_ident_basica if tram.materia_legislativa else '',
                        'materia_ementa': tram.materia_legislativa.txt_ementa if tram.materia_legislativa else '',
                            'materia_sigla': tram.materia_legislativa.tipo_materia_legislativa.sgl_tipo_materia if tram.materia_legislativa and tram.materia_legislativa.tipo_materia_legislativa else '',
                            # Autoria será adicionada em batch depois
                        })
                
                # Busca itens enviados de DOCUMENTOS
                # Itens enviados = ind_encaminha=1 AND ind_recebido=0 = dat_encaminha IS NOT NULL AND dat_recebimento IS NULL
                if not filtro_tipo or filtro_tipo == 'DOCUMENTO':
                    filtros_doc = [
                        TramitacaoAdministrativo.cod_usuario_local == cod_usuario,
                        TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                        TramitacaoAdministrativo.dat_encaminha.isnot(None),  # ind_encaminha = 1
                        TramitacaoAdministrativo.dat_recebimento.is_(None),  # ind_recebido = 0
                        TramitacaoAdministrativo.ind_excluido == 0
                    ]
                    # Não filtra por unidade - itens enviados são por usuário
                    
                    query_doc = session.query(TramitacaoAdministrativo).options(
                    selectinload(TramitacaoAdministrativo.status_tramitacao_administrativo),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                    selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                        selectinload(TramitacaoAdministrativo.documento_administrativo).selectinload(DocumentoAdministrativo.tipo_documento_administrativo)
                    ).filter(*filtros_doc).join(
                        DocumentoAdministrativo, TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
                    ).filter(
                        DocumentoAdministrativo.ind_tramitacao == 1,
                        DocumentoAdministrativo.ind_excluido == 0
                    )
                    
                    # Aplica filtros avançados
                    if filtro_tipo_documento:
                        query_doc = query_doc.join(
                            TipoDocumentoAdministrativo, DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento
                        ).filter(
                            TipoDocumentoAdministrativo.sgl_tipo_documento == filtro_tipo_documento
                        )
                    if filtro_numero:
                        query_doc = query_doc.filter(DocumentoAdministrativo.num_documento.like(f'%{filtro_numero}%'))
                    if filtro_ano:
                        query_doc = query_doc.filter(DocumentoAdministrativo.ano_documento.like(f'%{filtro_ano}%'))
                    if filtro_interessado:
                        query_doc = query_doc.filter(DocumentoAdministrativo.txt_interessado.like(f'%{filtro_interessado}%'))
                    if filtro_status:
                        query_doc = query_doc.join(
                            StatusTramitacaoAdministrativo, TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status
                        ).filter(StatusTramitacaoAdministrativo.des_status == filtro_status)
                    if filtro_data_inicial:
                        try:
                            from datetime import datetime
                            data_inicial_obj = datetime.strptime(filtro_data_inicial, '%Y-%m-%d')
                            query_doc = query_doc.filter(TramitacaoAdministrativo.dat_encaminha >= data_inicial_obj)
                        except (ValueError, TypeError):
                            pass
                    if filtro_data_final:
                        try:
                            from datetime import datetime
                            data_final_obj = datetime.strptime(filtro_data_final, '%Y-%m-%d')
                            data_final_obj = datetime.combine(data_final_obj.date(), datetime.max.time().replace(microsecond=0))
                            query_doc = query_doc.filter(TramitacaoAdministrativo.dat_encaminha <= data_final_obj)
                        except (ValueError, TypeError):
                            pass
                    if busca_termo:
                        query_doc = query_doc.filter(
                            or_(
                                DocumentoAdministrativo.txt_assunto.like(f'%{busca_termo}%'),
                                DocumentoAdministrativo.txt_interessado.like(f'%{busca_termo}%'),
                                func.concat(DocumentoAdministrativo.num_documento, '/', DocumentoAdministrativo.ano_documento).like(f'%{busca_termo}%')
                            )
                        )
                    
                    # Aplica ordenação completa (data, ano, número)
                    query_doc = _obter_ordenacao_completa_documento(query_doc, ordenacao)
                    
                    # OTIMIZAÇÃO: Aplica paginação SQL quando possível
                    # NÃO aplica offset aqui - será aplicado em Python após mesclar e ordenar
                    if limit is not None:
                        # Busca mais dados para garantir que temos suficientes após mesclar com matérias
                        # Calcula quantos itens precisamos: offset + limit * 2 (para garantir dados após merge)
                        query_doc = query_doc.limit(offset + (limit * 2))
                    
                    itens_doc = query_doc.all()
                    query_count += 1  # MONITORAMENTO
                    
                    for tram in itens_doc:
                        todas_tramitacoes.append({
                        'tipo': 'DOCUMENTO',
                        'cod_tramitacao': tram.cod_tramitacao,
                        'cod_entidade': tram.cod_documento,
                        'dat_encaminha': tram.dat_encaminha.isoformat() if tram.dat_encaminha else None,
                        'dat_visualizacao': tram.dat_visualizacao.isoformat() if tram.dat_visualizacao else None,
                        'dat_recebimento': tram.dat_recebimento.isoformat() if tram.dat_recebimento else None,
                        'cod_usuario_local': tram.cod_usuario_local,
                        'dat_fim_prazo': tram.dat_fim_prazo.isoformat() if tram.dat_fim_prazo else None,
                        'des_status': tram.status_tramitacao_administrativo.des_status if tram.status_tramitacao_administrativo else '',
                        'unidade_origem': _get_nome_unidade_tramitacao(tram.unidade_tramitacao_),
                        'unidade_destino': _get_nome_unidade_tramitacao(tram.unidade_tramitacao),
                        'documento_des_tipo': tram.documento_administrativo.tipo_documento_administrativo.des_tipo_documento if tram.documento_administrativo and tram.documento_administrativo.tipo_documento_administrativo else '',
                        'documento_num': tram.documento_administrativo.num_documento if tram.documento_administrativo else '',
                        'documento_ano': tram.documento_administrativo.ano_documento if tram.documento_administrativo else '',
                        'documento_assunto': tram.documento_administrativo.txt_assunto if tram.documento_administrativo else '',
                        'documento_sigla': tram.documento_administrativo.tipo_documento_administrativo.sgl_tipo_documento if tram.documento_administrativo and tram.documento_administrativo.tipo_documento_administrativo else '',
                            'documento_interessado': tram.documento_administrativo.txt_interessado if tram.documento_administrativo else '',
                        })
                
                # OTIMIZAÇÃO: Carrega autoria em batch para todas as matérias (evita N+1 queries)
                cod_materias_para_autoria = [
                    tram['cod_entidade'] for tram in todas_tramitacoes 
                    if tram['tipo'] == 'MATERIA' and tram.get('cod_entidade')
                ]
                if cod_materias_para_autoria:
                    autoria_batch = _get_autoria_batch(session, cod_materias_para_autoria)
                    query_count += 1  # MONITORAMENTO
                    # Adiciona autoria às tramitações
                    for tram in todas_tramitacoes:
                        if tram['tipo'] == 'MATERIA' and tram.get('cod_entidade'):
                            tram['materia_autoria'] = autoria_batch.get(tram['cod_entidade'], '')
                
                # Ordenação final: aplica ordenação completa (data, tipo, ano, número)
                # Isso garante que MATERIA vem antes de DOCUMENTO quando datas são iguais
                todas_tramitacoes = _ordenar_lista_tramitacoes(todas_tramitacoes, ordenacao)
                
                # Estatísticas
                # Se já calculamos o total via COUNT, usa esses valores
                # Caso contrário, calcula a partir dos resultados retornados
                if limit is not None and (total_materias_count > 0 or total_documentos_count > 0):
                    # Usa totais calculados via COUNT (mais preciso)
                    total_materias = total_materias_count
                    total_documentos = total_documentos_count
                    total_geral = total_materias + total_documentos
                else:
                    # Sem paginação ou sem COUNT, calcula a partir dos resultados
                    total_materias = sum(1 for t in todas_tramitacoes if t['tipo'] == 'MATERIA')
                    total_documentos = sum(1 for t in todas_tramitacoes if t['tipo'] == 'DOCUMENTO')
                    total_geral = len(todas_tramitacoes)
                
                # Paginação já foi aplicada parcialmente no SQL, agora aplica final em Python
                # (necessário porque mesclamos resultados de matérias e documentos)
                
                # Aplica limit e offset
                if limit is not None:
                    tramitacoes_paginadas = todas_tramitacoes[offset:offset + limit]
                else:
                    tramitacoes_paginadas = todas_tramitacoes[offset:]
                
                dados = {
                    'tramitacoes': tramitacoes_paginadas,
                    'total': total_geral,  # Total geral, não apenas da página
                    'total_materias': total_materias,
                    'total_documentos': total_documentos,
                    'filtro_tipo': filtro_tipo or 'TODOS',
                    'mostrar_unidade_breadcrumb': False,  # Itens enviados são do usuário, não da unidade
                    'cod_unid_tramitacao_filtro': None,
                    'nome_unidade_filtro': None
                }
                
                # MONITORAMENTO: Registra performance
                elapsed_time = time.time() - start_time
                _log_performance('itens_enviados', elapsed_time, query_count)
                
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps(dados, default=str)
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Erro ao obter itens enviados (tempo: {elapsed_time:.2f}s): {e}", exc_info=True)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps({'erro': f'Erro ao carregar itens enviados: {str(e)}'})


class TramitacaoSalvarView(GrokView, TramitacaoAPIBase):
    """View para salvar tramitação (individual)"""
    
    context(Interface)
    name('tramitacao_salvar_json')
    require('zope2.View')
    
    def render(self):
        """Salva tramitação individual"""
        # O require('zope2.View') já garante autenticação
        
        from datetime import datetime
        from .services import TramitacaoService
        
        tipo = _get_tipo_tramitacao(self.request)
        
        # NÃO usa 'with' - isso fecha a transação no SQLAlchemy 2.0
        session = db_session()
        cod_usuario = self._get_cod_usuario(session=session)  # Reutiliza sessão para evitar padrão misto
        # Se não conseguir obter cod_usuario, continua mesmo assim (require já garante autenticação)
        # O código abaixo funcionará mesmo sem cod_usuario, usando fallback
        
        # Obtém dados do formulário
        cod_tramitacao = self.request.form.get('hdn_cod_tramitacao')
        if tipo == 'MATERIA':
            cod_entidade = int(self.request.form.get('hdn_cod_materia', 0))
        else:
            cod_entidade = int(self.request.form.get('hdn_cod_documento', 0))
        
        if not cod_entidade:
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps({'erro': 'Código da entidade não fornecido'})
        
        # Prepara dados
        dados = {
            'cod_unid_tram_local': int(self.request.form.get('lst_cod_unid_tram_local', 0)),
            'cod_usuario_local': cod_usuario,
            'dat_encaminha': self.request.form.get('txt_dat_encaminha', ''),
            'cod_unid_tram_dest': int(self.request.form.get('lst_cod_unid_tram_dest', 0)) if self.request.form.get('lst_cod_unid_tram_dest') else None,
            'cod_usuario_dest': int(self.request.form.get('lst_cod_usuario_dest', 0)) if self.request.form.get('lst_cod_usuario_dest') else None,
            'cod_status': int(self.request.form.get('lst_cod_status', 0)),
            'txt_tramitacao': self.request.form.get('txa_txt_tramitacao', ''),
            'dat_fim_prazo': self.request.form.get('txt_dat_fim_prazo', ''),
        }
        
        # Campos específicos de matéria
        if tipo == 'MATERIA':
            dados['ind_urgencia'] = int(self.request.form.get('rad_ind_urgencia', 0))
            dados['sgl_turno'] = self.request.form.get('sgl_turno', '')
        
        # Validações
        service = TramitacaoService(session)
        
        # Verifica duplicata (apenas para novas tramitações)
        if not cod_tramitacao:
            if service.verificar_tramitacao_duplicada(
                tipo, cod_entidade,
                dados['cod_unid_tram_local'],
                dados.get('cod_unid_tram_dest', 0),
                cod_usuario,
                dados['cod_status']
            ):
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps({
                    'erro': 'Você já incluiu uma tramitação idêntica! Verifique na caixa de Rascunhos ou de Itens Enviados.'
                })
        
        # Salva tramitação
        cod_tramitacao_salvo = service.salvar_tramitacao(
            tipo, cod_entidade, dados,
            int(cod_tramitacao) if cod_tramitacao else None
        )
        
        # Registra log de auditoria
        tipo = _get_tipo_tramitacao(self.request)
        modulo = 'tramitacao_materia' if tipo == 'MATERIA' else 'tramitacao_documento'
        _registrar_log(
            self.context, self.request,
            modulo=modulo,
            metodo='tramitacao_salvar_json',
            cod_registro=cod_tramitacao_salvo,
            dados={'tipo': tipo, 'cod_entidade': cod_entidade, 'cod_tramitacao_anterior': cod_tramitacao or None, 'acao': 'incluir' if not cod_tramitacao else 'atualizar'}
        )
        
        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps({
            'sucesso': True,
            'cod_tramitacao': cod_tramitacao_salvo,
            'mensagem': 'Tramitação salva com sucesso.'
        })

# NOTA: TramitacaoLoteSalvarView foi movida para api.py para evitar conflito de configuração
# A implementação atual está em api.py com validações melhoradas
# NOTA: TramitacaoReceberView foi movida para api.py para evitar conflito de configuração
# A implementação atual está em api.py com validações melhoradas


class TramitacaoExcluirView(GrokView, TramitacaoAPIBase):
    """View para excluir tramitação"""
    
    context(Interface)
    name('tramitacao_excluir_json')
    require('zope2.View')
    
    def render(self):
        """Exclui tramitação (soft delete)"""
        # O require('zope2.View') já garante autenticação
        
        from .services import TramitacaoService
        
        tipo = _get_tipo_tramitacao(self.request)
        
        # NÃO usa 'with' - isso fecha a transação no SQLAlchemy 2.0
        session = db_session()
        cod_usuario = self._get_cod_usuario(session=session)  # Reutiliza sessão para evitar padrão misto
        # Se não conseguir obter cod_usuario, continua mesmo assim (require já garante autenticação)
        # O código abaixo funcionará mesmo sem cod_usuario, usando fallback
        
        cod_tramitacao = int(self.request.form.get('hdn_cod_tramitacao', 0))
        if not cod_tramitacao:
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps({'erro': 'Código da tramitação não fornecido'})
        
        service = TramitacaoService(session)
        sucesso = service.excluir_tramitacao(tipo, cod_tramitacao)
        
        if sucesso:
            # Registra log de auditoria
            tipo = _get_tipo_tramitacao(self.request)
            modulo = 'tramitacao_materia' if tipo == 'MATERIA' else 'tramitacao_documento'
            _registrar_log(
                self.context, self.request,
                modulo=modulo,
                metodo='tramitacao_excluir_json',
                cod_registro=cod_tramitacao,
                dados={'tipo': tipo, 'soft_delete': True}
            )
            
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps({
                'sucesso': True,
                'mensagem': 'Tramitação excluída com sucesso.'
            })
        else:
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps({'erro': 'Tramitação não encontrada'})


# ============================================
# ENDPOINT OTIMIZADO PARA CONTADORES
# ============================================

class TramitacaoContadoresView(GrokView, TramitacaoAPIBase):
    """
    View otimizada para retornar apenas contadores (sem buscar todos os dados).
    Usa cache e queries COUNT() para máxima performance.
    """
    
    context(Interface)
    name('tramitacao_contadores_json')
    require('zope2.View')
    
    def render(self):
        """Retorna contadores otimizados em JSON"""
        start_time = time.time()
        query_count = 0
        
        # Filtro opcional por tipo
        filtro_tipo = self.request.form.get('tipo', '')  # 'MATERIA', 'DOCUMENTO' ou '' (ambos)
        
        # Usa context manager para leitura
        try:
            with db_session_readonly() as session:
                # Obtém código do usuário - apenas via método _get_cod_usuario (maior segurança)
                cod_usuario = self._get_cod_usuario()
                
                if not cod_usuario:
                    self.request.response.setHeader('Content-Type', 'application/json')
                    return json.dumps({
                        'entrada': 0,
                        'rascunhos': 0,
                        'enviados': 0,
                        'erro': 'Usuário não identificado'
                    })
                
                # Verifica se foi solicitado filtrar por uma unidade específica
                cod_unid_tramitacao_filtro = None
                if 'cod_unid_tramitacao' in self.request.form:
                    try:
                        cod_unid_tramitacao_filtro = int(self.request.form.get('cod_unid_tramitacao'))
                    except (ValueError, TypeError):
                        pass
                
                # Verifica se deve forçar atualização (ignorar cache)
                forcar_atualizacao = self.request.form.get('forcar_atualizacao', '').lower() in ('true', '1', 'yes')
                
                if forcar_atualizacao:
                    # Invalida cache antes de calcular
                    _invalidate_cache_contadores(cod_usuario, cod_unid_tramitacao_filtro)
                
                # Verifica cache para contadores
                cache_key_entrada = _get_cache_key(cod_usuario, cod_unid_tramitacao_filtro, filtro_tipo or 'TODOS')
                cached_entrada, is_valid_entrada = _get_cached_contadores(cod_usuario, cod_unid_tramitacao_filtro, filtro_tipo or 'TODOS')
                
                # Se temos cache válido para entrada e não está forçando atualização, usa ele
                if not forcar_atualizacao and is_valid_entrada and cached_entrada:
                    entrada_total = cached_entrada.get('total', 0)
                    logger.debug(f"Cache HIT para contador entrada: {entrada_total}")
                else:
                    # Calcula contador de entrada
                    entrada_total = self._contar_caixa_entrada(session, cod_usuario, cod_unid_tramitacao_filtro, filtro_tipo)
                    query_count += 1
                    
                    # Armazena no cache
                    _set_cached_contadores(
                        cod_usuario, 
                        cod_unid_tramitacao_filtro, 
                        filtro_tipo or 'TODOS',
                        {'total': entrada_total}
                    )
                
                # Contadores de rascunhos e enviados (não usam filtro de unidade)
                rascunhos_total = self._contar_rascunhos(session, cod_usuario, filtro_tipo)
                query_count += 1
                
                enviados_total = self._contar_enviados(session, cod_usuario, filtro_tipo)
                query_count += 1
                
                elapsed_time = time.time() - start_time
                if elapsed_time > 0.5:
                    logger.warning(f"⚠️ OPERAÇÃO LENTA: contadores levou {elapsed_time:.2f}s ({query_count} queries)")
                
                dados = {
                    'entrada': entrada_total,
                    'rascunhos': rascunhos_total,
                    'enviados': enviados_total,
                    'atualizado': True  # Indica que os dados foram atualizados
                }
                
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps(dados)
        except Exception as e:
            logger.error(f"Erro ao obter contadores: {e}", exc_info=True)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps({
                'entrada': 0,
                'rascunhos': 0,
                'enviados': 0,
                'erro': str(e)
            })
    
    def _contar_caixa_entrada(self, session, cod_usuario, cod_unid_tramitacao_filtro, filtro_tipo):
        """
        Conta tramitações na caixa de entrada usando COUNT().
        
        OTIMIZAÇÕES APLICADAS:
        - Reutiliza alias de rascunho para evitar criação múltipla
        - Queries otimizadas para usar índices (ver indices_performance.sql)
        - Subqueries EXISTS otimizadas com índices compostos
        """
        from sqlalchemy import func, exists, and_
        from sqlalchemy.orm import aliased
        
        # Obtém unidades do usuário
        unidades = session.query(UsuarioUnidTram).filter(
            UsuarioUnidTram.cod_usuario == cod_usuario,
            UsuarioUnidTram.ind_excluido == 0
        ).all()
        
        if not unidades:
            logger.warning(f"Nenhuma unidade encontrada para usuário {cod_usuario}")
            return 0
        
        logger.debug(f"Unidades encontradas para usuário {cod_usuario}: {len(unidades)} unidades")
        
        # Filtra por unidade específica se solicitado
        if cod_unid_tramitacao_filtro:
            unidades_usuario = [u.cod_unid_tramitacao for u in unidades]
            if cod_unid_tramitacao_filtro not in unidades_usuario:
                return 0
            unidades = [u for u in unidades if u.cod_unid_tramitacao == cod_unid_tramitacao_filtro]
        
        unidades_responsavel = [u.cod_unid_tramitacao for u in unidades if u.ind_responsavel == 1]
        unidades_nao_responsavel = [u.cod_unid_tramitacao for u in unidades if u.ind_responsavel == 0]
        
        total = 0
        
        # OTIMIZAÇÃO: Cria aliases uma única vez e reutiliza
        rascunho_alias = aliased(Tramitacao)
        rascunho_doc_alias = aliased(TramitacaoAdministrativo)
        
        # Subquery EXISTS otimizada para rascunhos de matérias
        # NOTA: Requer índice idx_tramitacao_rascunhos (ver indices_performance.sql)
        rascunho_exists_materia = exists().where(
            and_(
                rascunho_alias.cod_materia == Tramitacao.cod_materia,
                rascunho_alias.ind_ult_tramitacao == 0,  # Rascunho
                rascunho_alias.dat_encaminha.is_(None),  # Não enviado
                rascunho_alias.ind_excluido == 0
            )
        )
        
        # Subquery EXISTS otimizada para rascunhos de documentos
        # NOTA: Requer índice idx_tramitacao_adm_rascunhos (ver indices_performance.sql)
        rascunho_exists_doc = exists().where(
            and_(
                rascunho_doc_alias.cod_documento == TramitacaoAdministrativo.cod_documento,
                rascunho_doc_alias.ind_ult_tramitacao == 0,  # Rascunho
                rascunho_doc_alias.dat_encaminha.is_(None),  # Não enviado
                rascunho_doc_alias.ind_excluido == 0
            )
        )
        
        # Conta MATÉRIAS
        if not filtro_tipo or filtro_tipo == 'MATERIA':
            # Unidades responsáveis
            if unidades_responsavel:
                # Query otimizada - usa índice idx_tramitacao_caixa_entrada
                # ✅ REMOVIDO: Tramitacao.dat_recebimento.is_(None) - processos visualizados/recebidos devem ser contados
                query_resp = session.query(func.count(Tramitacao.cod_tramitacao)).filter(
                    Tramitacao.cod_unid_tram_dest.in_(unidades_responsavel),
                    Tramitacao.ind_ult_tramitacao == 1,
                    Tramitacao.dat_encaminha.isnot(None),
                    Tramitacao.ind_excluido == 0
                ).join(
                    StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
                ).filter(
                    StatusTramitacao.ind_retorno_tramitacao == 1
                ).join(
                    MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
                ).filter(
                    MateriaLegislativa.ind_tramitacao == 1,
                    MateriaLegislativa.ind_excluido == 0
                ).filter(~rascunho_exists_materia)
                
                count_resp = query_resp.scalar() or 0
                total += count_resp
            
            # Unidades não responsáveis
            if unidades_nao_responsavel:
                # Query otimizada - usa índice idx_tramitacao_caixa_entrada
                # ✅ REMOVIDO: Tramitacao.dat_recebimento.is_(None) - processos visualizados/recebidos devem ser contados
                query_nao_resp = session.query(func.count(Tramitacao.cod_tramitacao)).filter(
                    Tramitacao.cod_unid_tram_dest.in_(unidades_nao_responsavel),
                    # Para unidades não responsáveis: cod_usuario_dest deve ser igual ao usuário OU NULL
                    (Tramitacao.cod_usuario_dest == cod_usuario) | (Tramitacao.cod_usuario_dest.is_(None)),
                    Tramitacao.ind_ult_tramitacao == 1,
                    Tramitacao.dat_encaminha.isnot(None),
                    Tramitacao.ind_excluido == 0
                ).join(
                    StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
                ).filter(
                    StatusTramitacao.ind_retorno_tramitacao == 1
                ).join(
                    MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
                ).filter(
                    MateriaLegislativa.ind_tramitacao == 1,
                    MateriaLegislativa.ind_excluido == 0
                ).filter(~rascunho_exists_materia)
                
                count_nao_resp = query_nao_resp.scalar() or 0
                total += count_nao_resp
        
        # Conta DOCUMENTOS
        if not filtro_tipo or filtro_tipo == 'DOCUMENTO':
            # Unidades não responsáveis (documentos só aparecem em não responsáveis)
            if unidades_nao_responsavel:
                # Query otimizada - usa índice idx_tramitacao_adm_caixa_entrada
                # ✅ REMOVIDO: TramitacaoAdministrativo.dat_recebimento.is_(None) - processos visualizados/recebidos devem ser contados
                query_doc = session.query(func.count(TramitacaoAdministrativo.cod_tramitacao)).filter(
                    TramitacaoAdministrativo.cod_unid_tram_dest.in_(unidades_nao_responsavel),
                    # Para unidades não responsáveis: cod_usuario_dest deve ser igual ao usuário OU NULL
                    (TramitacaoAdministrativo.cod_usuario_dest == cod_usuario) | (TramitacaoAdministrativo.cod_usuario_dest.is_(None)),
                    TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                    TramitacaoAdministrativo.dat_encaminha.isnot(None),
                    TramitacaoAdministrativo.ind_excluido == 0
                ).join(
                    StatusTramitacaoAdministrativo, 
                    TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status
                ).filter(
                    StatusTramitacaoAdministrativo.ind_retorno_tramitacao == 1
                ).join(
                    DocumentoAdministrativo, 
                    TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
                ).filter(
                    DocumentoAdministrativo.ind_tramitacao == 1,
                    DocumentoAdministrativo.ind_excluido == 0
                ).filter(~rascunho_exists_doc)
                
                count_doc = query_doc.scalar() or 0
                total += count_doc
        
        return total
    
    def _contar_rascunhos(self, session, cod_usuario, filtro_tipo):
        """Conta rascunhos usando COUNT()"""
        from sqlalchemy import func
        
        total = 0
        
        # Conta MATÉRIAS
        # Rascunho = ind_ult_tramitacao == 0 (não é última tramitação) E dat_encaminha IS NULL (não foi enviado)
        if not filtro_tipo or filtro_tipo == 'MATERIA':
            count_materia = session.query(func.count(Tramitacao.cod_tramitacao)).filter(
                Tramitacao.cod_usuario_local == cod_usuario,
                Tramitacao.ind_ult_tramitacao == 0,  # Rascunho não é última tramitação
                Tramitacao.dat_encaminha.is_(None),  # Rascunho = não encaminhado (não foi enviado)
                Tramitacao.ind_excluido == 0
            ).join(
                MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
            ).filter(
                MateriaLegislativa.ind_excluido == 0
            ).scalar() or 0
            total += count_materia
        
        # Conta DOCUMENTOS
        # Rascunho = ind_ult_tramitacao == 0 (não é última tramitação) E dat_encaminha IS NULL (não foi enviado)
        if not filtro_tipo or filtro_tipo == 'DOCUMENTO':
            count_doc = session.query(func.count(TramitacaoAdministrativo.cod_tramitacao)).filter(
                TramitacaoAdministrativo.cod_usuario_local == cod_usuario,
                TramitacaoAdministrativo.ind_ult_tramitacao == 0,  # Rascunho não é última tramitação
                TramitacaoAdministrativo.dat_encaminha.is_(None),  # Rascunho = não encaminhado (não foi enviado)
                TramitacaoAdministrativo.ind_excluido == 0
            ).join(
                DocumentoAdministrativo, 
                TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
            ).filter(
                DocumentoAdministrativo.ind_excluido == 0
            ).scalar() or 0
            total += count_doc
        
        return total
    
    def _contar_enviados(self, session, cod_usuario, filtro_tipo):
        """Conta itens enviados usando COUNT()"""
        from sqlalchemy import func
        
        total = 0
        
        # Conta MATÉRIAS
        # Itens enviados = ind_encaminha=1 AND ind_recebido=0 = dat_encaminha IS NOT NULL AND dat_recebimento IS NULL
        if not filtro_tipo or filtro_tipo == 'MATERIA':
            count_materia = session.query(func.count(Tramitacao.cod_tramitacao)).filter(
                Tramitacao.cod_usuario_local == cod_usuario,
                Tramitacao.ind_ult_tramitacao == 1,
                Tramitacao.dat_encaminha.isnot(None),  # ind_encaminha = 1
                Tramitacao.dat_recebimento.is_(None),  # ind_recebido = 0
                Tramitacao.ind_excluido == 0
            ).join(
                MateriaLegislativa, Tramitacao.cod_materia == MateriaLegislativa.cod_materia
            ).filter(
                MateriaLegislativa.ind_tramitacao == 1,
                MateriaLegislativa.ind_excluido == 0
            ).scalar() or 0
            total += count_materia
        
        # Conta DOCUMENTOS
        # Itens enviados = ind_encaminha=1 AND ind_recebido=0 = dat_encaminha IS NOT NULL AND dat_recebimento IS NULL
        if not filtro_tipo or filtro_tipo == 'DOCUMENTO':
            count_doc = session.query(func.count(TramitacaoAdministrativo.cod_tramitacao)).filter(
                TramitacaoAdministrativo.cod_usuario_local == cod_usuario,
                TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                TramitacaoAdministrativo.dat_encaminha.isnot(None),  # ind_encaminha = 1
                TramitacaoAdministrativo.dat_recebimento.is_(None),  # ind_recebido = 0
                TramitacaoAdministrativo.ind_excluido == 0
            ).join(
                DocumentoAdministrativo, 
                TramitacaoAdministrativo.cod_documento == DocumentoAdministrativo.cod_documento
            ).filter(
                DocumentoAdministrativo.ind_tramitacao == 1,
                DocumentoAdministrativo.ind_excluido == 0
            ).scalar() or 0
            total += count_doc
        
        return total
