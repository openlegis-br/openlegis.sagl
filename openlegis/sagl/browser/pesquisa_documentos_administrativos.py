# -*- coding: utf-8 -*-
from five import grok
from zope.interface import Interface
from z3c.saconfig import named_scoped_session
from openlegis.sagl.models.models import (
    DocumentoAdministrativo, TipoDocumentoAdministrativo, TramitacaoAdministrativo,
    UnidadeTramitacao, StatusTramitacaoAdministrativo, TipoPeticionamento,
    Comissao, Orgao, Parlamentar, UsuarioTipoDocumento, UsuarioConsultaDocumento, Usuario,
    DocumentoAcessorioAdministrativo, DocumentoAdministrativoVinculado, DocumentoAdministrativoMateria,
    MateriaLegislativa, TipoMateriaLegislativa
)
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy import case, func, and_, or_, cast, String, Integer, select, text, asc, desc, literal
from sqlalchemy.sql import expression
import re
from datetime import datetime
import json
import logging
from functools import lru_cache
import io
import csv
import openpyxl
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet

logger = logging.getLogger(__name__)
Session = named_scoped_session('minha_sessao')

# =================================================================== #
# FUNÇÕES UTILITÁRIAS E CACHEADAS
# ===================================================================

def _get_tipos_documento_com_permissao(context, session):
    """Retorna tipos de documento administrativo disponíveis baseado em permissões do usuário.
    
    Lógica de permissões:
    - Manager, Operador, Operador Modulo Administrativo, Consulta Modulo Administrativo: todos os tipos
    - Authenticated: tipos públicos OU tipos com permissão específica
    - Anônimo: apenas tipos públicos
    """
    from Products.CMFCore.utils import getToolByName
    mtool = getToolByName(context, 'portal_membership')
    
    try:
        # Verificar roles do usuário
        is_anonymous = mtool.isAnonymousUser()
        
        # Roles que têm acesso total
        roles_com_acesso_total = ['Manager', 'Operador', 'Operador Modulo Administrativo', 'Consulta Modulo Administrativo']
        has_full_access = False
        
        if not is_anonymous:
            member = mtool.getAuthenticatedMember()
            if member:
                # Verificar cada role individualmente
                for role in roles_com_acesso_total:
                    if member.has_role([role]):
                        has_full_access = True
                        break
        
        # Construir query base (sempre filtrar por não excluídos)
        query_base = session.query(TipoDocumentoAdministrativo).filter(
            TipoDocumentoAdministrativo.ind_excluido == 0
        )
        
        if has_full_access:
            # Operadores veem todos os tipos (tentar principais primeiro, senão todos)
            query = query_base.filter(TipoDocumentoAdministrativo.tip_natureza == 'P')
            count_principais = query.count()
            if count_principais == 0:
                # Se não houver principais, retornar todos
                query = query_base
        elif is_anonymous:
            # Anônimos: APENAS tipos principais (tip_natureza == 'P') E públicos (ind_publico == 1)
            query = session.query(TipoDocumentoAdministrativo).filter(
                TipoDocumentoAdministrativo.ind_excluido == 0,
                TipoDocumentoAdministrativo.ind_publico == 1,
                TipoDocumentoAdministrativo.tip_natureza == 'P'
            )
        else:
            # Usuários autenticados: tipos principais que sejam públicos OU com permissão
            member = mtool.getAuthenticatedMember()
            cod_usuario = None
            if member:
                username = member.getUserName()
                if username:
                    usuario = session.query(Usuario).filter(
                        Usuario.col_username == username,
                        Usuario.ind_excluido == 0
                    ).first()
                    if usuario:
                        cod_usuario = usuario.cod_usuario
            
            tipos_permitidos = set()
            if cod_usuario:
                tipos_incluir = session.query(UsuarioTipoDocumento.tip_documento).filter(
                    UsuarioTipoDocumento.cod_usuario == cod_usuario,
                    UsuarioTipoDocumento.ind_excluido == 0
                ).all()
                tipos_permitidos.update([t[0] for t in tipos_incluir])
                
                tipos_consulta = session.query(UsuarioConsultaDocumento.tip_documento).filter(
                    UsuarioConsultaDocumento.cod_usuario == cod_usuario,
                    UsuarioConsultaDocumento.ind_excluido == 0
                ).all()
                tipos_permitidos.update([t[0] for t in tipos_consulta])
            
            if tipos_permitidos:
                # Usuários autenticados com permissões: tipos principais que sejam públicos OU com permissão
                query = query_base.filter(
                    TipoDocumentoAdministrativo.tip_natureza == 'P',
                    or_(
                        TipoDocumentoAdministrativo.ind_publico == 1,
                        TipoDocumentoAdministrativo.tip_documento.in_(list(tipos_permitidos))
                    )
                )
            else:
                # Usuários autenticados sem permissões específicas: apenas tipos principais públicos
                query = query_base.filter(
                    TipoDocumentoAdministrativo.ind_publico == 1,
                    TipoDocumentoAdministrativo.tip_natureza == 'P'
                )
        
        tipos = query.order_by(TipoDocumentoAdministrativo.des_tipo_documento).all()
        
        resultado = []
        tipos_acessorios_filtrados = 0
        tipos_nao_publicos_filtrados = 0
        
        for t in tipos:
            if t.tip_documento and t.des_tipo_documento:
                # Verificação adicional de segurança: para anônimos, garantir que apenas tipos principais sejam retornados
                if is_anonymous and t.tip_natureza != 'P':
                    tipos_acessorios_filtrados += 1
                    continue
                
                # Verificação adicional: garantir que tipos públicos realmente sejam públicos
                if is_anonymous and t.ind_publico != 1:
                    tipos_nao_publicos_filtrados += 1
                    continue
                
                resultado.append({
                    'id': str(t.tip_documento),
                    'text': str(t.des_tipo_documento)
                })
        
        if tipos_acessorios_filtrados > 0:
            logger.error(f"ERRO CRÍTICO: {tipos_acessorios_filtrados} tipos acessórios foram retornados pela query para anônimo!")
        if tipos_nao_publicos_filtrados > 0:
            logger.error(f"ERRO CRÍTICO: {tipos_nao_publicos_filtrados} tipos não públicos foram retornados pela query para anônimo!")
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro em _get_tipos_documento_com_permissao: {str(e)}", exc_info=True)
        # Em caso de erro, retornar lista vazia
        return []

@lru_cache(maxsize=1)
def _get_unidades_tramitacao_cached(session_factory):
    """Retorna unidades de tramitação administrativas."""
    session = session_factory()
    try:
        nome_unidade = case(
            (UnidadeTramitacao.cod_comissao != None, Comissao.nom_comissao),
            (UnidadeTramitacao.cod_orgao != None, Orgao.nom_orgao),
            (UnidadeTramitacao.cod_parlamentar != None, Parlamentar.nom_parlamentar),
            else_=''
        ).label('nome_unidade')
        query = session.query(UnidadeTramitacao.cod_unid_tramitacao, nome_unidade)\
            .outerjoin(Comissao, UnidadeTramitacao.cod_comissao == Comissao.cod_comissao)\
            .outerjoin(Orgao, UnidadeTramitacao.cod_orgao == Orgao.cod_orgao)\
            .outerjoin(Parlamentar, UnidadeTramitacao.cod_parlamentar == Parlamentar.cod_parlamentar)\
            .filter(UnidadeTramitacao.ind_excluido == 0, UnidadeTramitacao.ind_adm == 1)\
            .order_by(nome_unidade)
        unidades = query.all()
        return [{'id': cod, 'text': nome} for cod, nome in unidades if nome]
    finally:
        session.close()

@lru_cache(maxsize=1)
def _get_status_tramitacao_cached(session_factory):
    """Retorna status de tramitação administrativa."""
    session = session_factory()
    try:
        query = session.query(StatusTramitacaoAdministrativo).filter(
            StatusTramitacaoAdministrativo.ind_excluido == 0
        ).order_by(StatusTramitacaoAdministrativo.sgl_status)
        status_list = query.all()
        return [{'id': s.cod_status, 'text': f"{s.sgl_status} - {s.des_status}"} for s in status_list]
    finally:
        session.close()

@lru_cache(maxsize=1)
def _get_tipos_peticionamento_cached(session_factory):
    """Retorna tipos de peticionamento (classificação)."""
    session = session_factory()
    try:
        query = session.query(TipoPeticionamento).filter(
            TipoPeticionamento.ind_doc_adm == 1,
            TipoPeticionamento.ind_excluido == 0
        ).order_by(TipoPeticionamento.des_tipo_peticionamento)
        tipos = query.all()
        return [{'id': t.tip_peticionamento, 'text': t.des_tipo_peticionamento} for t in tipos]
    finally:
        session.close()

# =================================================================== #
# CLASSE DocumentoAdministrativoView
# ===================================================================

class DocumentoAdministrativoView(grok.View):
    """View principal da busca de processos administrativos com exportação."""
    grok.context(Interface)
    grok.name('documentos_administrativos_json')
    grok.require('zope2.View')

    def _parse_int_param(self, param_name, default=None):
        value = self.request.get(param_name)
        return int(value) if value and str(value).isdigit() else default

    def _parse_list_param(self, param_name):
        """Retorna lista de valores do parâmetro."""
        values = self.request.get(param_name)
        if not values:
            return None
        if isinstance(values, (list, tuple)):
            return [str(v) for v in values if v]
        if isinstance(values, str):
            if values.startswith('[') and values.endswith(']'):
                try:
                    return json.loads(values)
                except:
                    return [values]
            return [v.strip() for v in values.split(',') if v.strip()]
        return [str(values)]

    def _parse_int_list_param(self, param_name):
        """Retorna lista de inteiros do parâmetro."""
        values = self._parse_list_param(param_name)
        if not values:
            return None
        result = []
        for v in values:
            try:
                result.append(int(v))
            except (ValueError, TypeError):
                continue
        return result if result else None

    def _parse_date_param(self, param_name):
        date_str = self.request.get(param_name)
        if not date_str:
            return None
        try:
            if '/' in date_str:
                return datetime.strptime(date_str, '%d/%m/%Y').date()
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None

    def _build_base_query(self, session):
        """Constrói query base para documentos administrativos com filtros de permissão."""
        from Products.CMFCore.utils import getToolByName
        mtool = getToolByName(self.context, 'portal_membership')
        request = self.request
        user = request.get('AUTHENTICATED_USER')
        is_anonymous = mtool.isAnonymousUser()
        
        query = session.query(DocumentoAdministrativo, TipoDocumentoAdministrativo)\
            .join(TipoDocumentoAdministrativo, DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
            .filter(DocumentoAdministrativo.ind_excluido == 0)
        
        # Aplicar filtros de permissão
        roles_com_acesso_total = ['Manager', 'Operador', 'Operador Modulo Administrativo', 'Consulta Modulo Administrativo']
        has_full_access = False
        if not is_anonymous and user:
            has_full_access = any(user.has_role([role]) for role in roles_com_acesso_total)
        
        if has_full_access:
            # Usuários com acesso total veem todos os documentos
            pass
        elif is_anonymous:
            # Anônimos veem apenas documentos com tipo público
            query = query.filter(TipoDocumentoAdministrativo.ind_publico == 1)
        else:
            # Usuários autenticados: documentos com tipo público OU tipo com permissão
            username = user.getUserName() if user else None
            cod_usuario = None
            if username:
                usuario = session.query(Usuario).filter(
                    Usuario.col_username == username,
                    Usuario.ind_excluido == 0
                ).first()
                if usuario:
                    cod_usuario = usuario.cod_usuario
            
            # Buscar tipos permitidos (otimizado: uma única query com UNION)
            tipos_permitidos = set()
            if cod_usuario:
                # Combinar tipos de inclusão e consulta em uma única query
                tipos_incluir = session.query(UsuarioTipoDocumento.tip_documento).filter(
                    UsuarioTipoDocumento.cod_usuario == cod_usuario,
                    UsuarioTipoDocumento.ind_excluido == 0
                )
                tipos_consulta = session.query(UsuarioConsultaDocumento.tip_documento).filter(
                    UsuarioConsultaDocumento.cod_usuario == cod_usuario,
                    UsuarioConsultaDocumento.ind_excluido == 0
                )
                # Usar union para combinar resultados
                tipos_combinados = tipos_incluir.union(tipos_consulta).all()
                tipos_permitidos = {t[0] for t in tipos_combinados}
            
            # Filtrar: tipo público OU tipo com permissão
            if tipos_permitidos:
                query = query.filter(
                    or_(
                        TipoDocumentoAdministrativo.ind_publico == 1,
                        DocumentoAdministrativo.tip_documento.in_(list(tipos_permitidos))
                    )
                )
            else:
                # Se não tem permissões específicas, apenas tipos públicos
                query = query.filter(TipoDocumentoAdministrativo.ind_publico == 1)
        
        return query

    def _apply_all_filters(self, query, session):
        """Aplica todos os filtros à query."""
        query = self._apply_documento_filters(query)
        query = self._apply_date_filters(query)
        query = self._apply_text_search(query)
        query = self._apply_tramitacao_filters(query, session)
        return query

    def _apply_documento_filters(self, query):
        """Aplica filtros básicos de documento."""
        # Filtro por número
        if (val := self._parse_int_param('txt_num_documento')) is not None:
            query = query.filter(DocumentoAdministrativo.num_documento == val)
        
        # Filtro por ano
        if (val := self._parse_int_param('txt_ano_documento')) is not None:
            query = query.filter(DocumentoAdministrativo.ano_documento == val)
        
        # Filtro por protocolo
        if (val := self._parse_int_param('txt_num_protocolo')) is not None:
            query = query.filter(DocumentoAdministrativo.num_protocolo == val)
        
        # Filtro por processo (NPC)
        if (val := self._parse_int_param('txt_npc')) is not None:
            # NPC geralmente está relacionado ao número do documento
            query = query.filter(DocumentoAdministrativo.num_documento == val)
        
        # Filtro por tipo de documento
        if (tipos := self._parse_int_list_param('lst_tip_documento')):
            query = query.filter(DocumentoAdministrativo.tip_documento.in_(tipos))
        
        # Filtro por tramitação
        if (val := self.request.get('rad_tramitando')):
            if val.isdigit():
                query = query.filter(DocumentoAdministrativo.ind_tramitacao == int(val))
        
        # Filtro por classificação (tipo de peticionamento)
        if (val := self._parse_int_param('lst_assunto')) is not None:
            query = query.filter(DocumentoAdministrativo.cod_assunto == val)
        
        return query

    def _apply_date_filters(self, query):
        """Aplica filtros de data."""
        dat1 = self._parse_date_param('dt_apres1')
        dat2 = self._parse_date_param('dt_apres2')
        if dat1 and dat2:
            query = query.filter(DocumentoAdministrativo.dat_documento.between(dat1, dat2))
        elif dat1:
            query = query.filter(DocumentoAdministrativo.dat_documento >= dat1)
        elif dat2:
            query = query.filter(DocumentoAdministrativo.dat_documento <= dat2)
        
        return query

    def _filter_monosyllabic_words(self, palavras):
        """Filtra palavras monossílabas (stop words)."""
        stop_words_monosyllabic = {
            'a', 'à', 'ao', 'aos', 'as', 'da', 'das', 'de', 'do', 'dos', 'e', 'em', 'na', 'nas', 'no', 'nos',
            'o', 'os', 'um', 'uma', 'uns', 'umas', 'para', 'por', 'com', 'sem', 'sob', 'sobre', 'entre',
            'contra', 'até', 'desde', 'que', 'se', 'me', 'te', 'nos', 'vos', 'lhe', 'lhes', 'ou', 'mas',
            'já', 'ainda', 'só', 'sempre', 'nunca', 'jamais', 'agora', 'depois', 'antes', 'hoje', 'ontem',
            'é', 'são', 'foi', 'ser', 'ter', 'tem', 'tinha', 'teve', 'há', 'houve', 'era', 'eram', 'foram',
            'está', 'estão', 'estava', 'estavam', 'esteve', 'estiveram'
        }
        
        palavras_filtradas = []
        for palavra in palavras:
            palavra_lower = palavra.lower()
            if len(palavra) <= 2 or palavra_lower in stop_words_monosyllabic:
                continue
            if len(palavra) == 3:
                vogais = sum(1 for c in palavra_lower if c in 'aeiouáéíóúâêîôûàèìòùãõ')
                if vogais <= 1:
                    continue
            palavras_filtradas.append(palavra)
        
        return palavras_filtradas

    def _apply_text_search(self, query):
        """Aplica busca por texto (assunto e interessado)."""
        termo_assunto = self.request.get('txa_txt_assunto')
        termo_interessado = self.request.get('txa_txt_interessado')
        
        if not termo_assunto and not termo_interessado:
            return query
        
        # Busca por assunto
        if termo_assunto:
            termos_limpos = re.sub(r'[^\w\s]', ' ', termo_assunto)
            termos_limpos = ' '.join(termos_limpos.split())
            if termos_limpos:
                palavras = termos_limpos.split()
                palavras_filtradas = self._filter_monosyllabic_words(palavras)
                if palavras_filtradas:
                    frase_completa_term = f"%{termos_limpos}%"
                    condicao_frase = or_(
                        DocumentoAdministrativo.txt_assunto.ilike(frase_completa_term),
                        DocumentoAdministrativo.txt_observacao.ilike(frase_completa_term)
                    )
                    
                    condicoes_palavras = []
                    for palavra in palavras_filtradas:
                        palavra_term = f"%{palavra}%"
                        condicoes_palavras.append(
                            or_(
                                DocumentoAdministrativo.txt_assunto.ilike(palavra_term),
                                DocumentoAdministrativo.txt_observacao.ilike(palavra_term)
                            )
                        )
                    
                    query = query.filter(or_(condicao_frase, and_(*condicoes_palavras)))
        
        # Busca por interessado
        if termo_interessado:
            termo_interessado_limpo = re.sub(r'[^\w\s]', ' ', termo_interessado)
            termo_interessado_limpo = ' '.join(termo_interessado_limpo.split())
            if termo_interessado_limpo:
                termo_interessado_pattern = f"%{termo_interessado_limpo}%"
                query = query.filter(DocumentoAdministrativo.txt_interessado.ilike(termo_interessado_pattern))
        
        return query

    def _apply_tramitacao_filters(self, query, session):
        """Aplica filtros de tramitação com otimização de performance."""
        cod_status = self._parse_int_param('lst_status')
        cod_unid_atual = self._parse_int_param('lst_localizacao')
        cod_unid_passou = self._parse_int_param('lst_tramitou')
        
        # Filtro por status ou localização atual (usando join direto com última tramitação)
        # Otimização: usar ind_ult_tramitacao em vez de window function
        if cod_status or cod_unid_atual:
            tramitacao_alias = aliased(TramitacaoAdministrativo)
            query = query.join(
                tramitacao_alias,
                and_(
                    tramitacao_alias.cod_documento == DocumentoAdministrativo.cod_documento,
                    tramitacao_alias.ind_ult_tramitacao == 1,
                    tramitacao_alias.ind_excluido == 0
                )
            )
            
            if cod_status:
                query = query.filter(tramitacao_alias.cod_status == cod_status)
            if cod_unid_atual:
                query = query.filter(tramitacao_alias.cod_unid_tram_dest == cod_unid_atual)
        
        # Filtro por unidade onde o documento já passou (otimizado)
        if cod_unid_passou:
            tramitou_em = session.query(TramitacaoAdministrativo.cod_documento).filter(
                or_(
                    TramitacaoAdministrativo.cod_unid_tram_local == cod_unid_passou,
                    TramitacaoAdministrativo.cod_unid_tram_dest == cod_unid_passou
                ),
                TramitacaoAdministrativo.ind_excluido == 0
            ).distinct()
            query = query.filter(DocumentoAdministrativo.cod_documento.in_(tramitou_em))
        
        return query

    def _format_results(self, results, session):
        """Formata resultados para JSON com otimizações de performance (batch queries)."""
        from Products.CMFCore.utils import getToolByName
        portal_url = getToolByName(self.context, 'portal_url')()
        mtool = getToolByName(self.context, 'portal_membership')
        request = self.request
        
        if not results:
            return []
        
        # Verificar se é operador ou tem permissão específica
        is_operador = False
        cod_usuario = None
        if not mtool.isAnonymousUser():
            member = mtool.getAuthenticatedMember()
            if member:
                is_operador = member.has_role(['Operador', 'Operador Modulo Administrativo'])
                # Buscar código do usuário para verificar permissões específicas
                username = member.getUserName()
                if username:
                    usuario = session.query(Usuario).filter(
                        Usuario.col_username == username,
                        Usuario.ind_excluido == 0
                    ).first()
                    if usuario:
                        cod_usuario = usuario.cod_usuario
        
        # Cache de permissões por tipo de documento (para otimização)
        tipos_com_permissao = set()
        if cod_usuario and not is_operador:
            # Buscar tipos com permissão de inclusão/gerenciamento
            tipos_permitidos = session.query(UsuarioTipoDocumento.tip_documento).filter(
                UsuarioTipoDocumento.cod_usuario == cod_usuario,
                UsuarioTipoDocumento.ind_excluido == 0
            ).all()
            tipos_com_permissao = {t[0] for t in tipos_permitidos}
        
        # Extrair códigos dos documentos para batch queries
        cod_documentos = [doc.cod_documento for doc, _ in results]
        
        # BATCH QUERY 1: Buscar todas as últimas tramitações de uma vez
        ultimas_tramitacoes = session.query(TramitacaoAdministrativo)\
            .filter(
                TramitacaoAdministrativo.cod_documento.in_(cod_documentos),
                TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                TramitacaoAdministrativo.ind_excluido == 0
            ).all()
        
        # Criar dicionário de tramitações por documento
        tramitacoes_dict = {t.cod_documento: t for t in ultimas_tramitacoes}
        
        # BATCH QUERY 2: Buscar todas as unidades de tramitação necessárias
        unid_trams = set()
        for tram in ultimas_tramitacoes:
            unid = tram.cod_unid_tram_dest or tram.cod_unid_tram_local
            if unid:
                unid_trams.add(unid)
        
        unidades_dict = {}
        if unid_trams:
            unidades = session.query(UnidadeTramitacao)\
                .outerjoin(Comissao, UnidadeTramitacao.cod_comissao == Comissao.cod_comissao)\
                .outerjoin(Orgao, UnidadeTramitacao.cod_orgao == Orgao.cod_orgao)\
                .outerjoin(Parlamentar, UnidadeTramitacao.cod_parlamentar == Parlamentar.cod_parlamentar)\
                .filter(UnidadeTramitacao.cod_unid_tramitacao.in_(unid_trams)).all()
            
            # Criar dicionários para nomes
            orgaos_ids = {u.cod_orgao for u in unidades if u.cod_orgao}
            comissoes_ids = {u.cod_comissao for u in unidades if u.cod_comissao}
            parlamentares_ids = {u.cod_parlamentar for u in unidades if u.cod_parlamentar}
            
            orgaos_dict = {}
            if orgaos_ids:
                orgaos = session.query(Orgao.cod_orgao, Orgao.nom_orgao)\
                    .filter(Orgao.cod_orgao.in_(orgaos_ids)).all()
                orgaos_dict = {o.cod_orgao: o.nom_orgao for o in orgaos}
            
            comissoes_dict = {}
            if comissoes_ids:
                comissoes = session.query(Comissao.cod_comissao, Comissao.nom_comissao)\
                    .filter(Comissao.cod_comissao.in_(comissoes_ids)).all()
                comissoes_dict = {c.cod_comissao: c.nom_comissao for c in comissoes}
            
            parlamentares_dict = {}
            if parlamentares_ids:
                parlamentares = session.query(Parlamentar.cod_parlamentar, Parlamentar.nom_parlamentar)\
                    .filter(Parlamentar.cod_parlamentar.in_(parlamentares_ids)).all()
                parlamentares_dict = {p.cod_parlamentar: p.nom_parlamentar for p in parlamentares}
            
            # Montar dicionário de unidades com nomes
            for unidade in unidades:
                nome = ''
                if unidade.cod_orgao:
                    nome = orgaos_dict.get(unidade.cod_orgao, '')
                elif unidade.cod_comissao:
                    nome = comissoes_dict.get(unidade.cod_comissao, '')
                elif unidade.cod_parlamentar:
                    nome = parlamentares_dict.get(unidade.cod_parlamentar, '')
                unidades_dict[unidade.cod_unid_tramitacao] = nome
        
        # BATCH QUERY 3: Buscar todos os status de uma vez
        status_ids = {t.cod_status for t in ultimas_tramitacoes if t.cod_status}
        status_dict = {}
        if status_ids:
            status_list = session.query(StatusTramitacaoAdministrativo)\
                .filter(StatusTramitacaoAdministrativo.cod_status.in_(status_ids)).all()
            status_dict = {s.cod_status: f"{s.sgl_status} - {s.des_status}" for s in status_list}
        
        # BATCH QUERY 4: Contar documentos acessórios para todos os documentos
        contagens_acessorios = session.query(
            DocumentoAcessorioAdministrativo.cod_documento,
            func.count(DocumentoAcessorioAdministrativo.cod_documento_acessorio).label('qtd')
        ).filter(
            DocumentoAcessorioAdministrativo.cod_documento.in_(cod_documentos),
            DocumentoAcessorioAdministrativo.ind_excluido == 0
        ).group_by(DocumentoAcessorioAdministrativo.cod_documento).all()
        qtd_acessorios_dict = {c.cod_documento: c.qtd for c in contagens_acessorios}
        
        # BATCH QUERY 5: Contar processos vinculados para todos os documentos
        contagens_vinculados = session.query(
            DocumentoAdministrativoVinculado.cod_documento_vinculante,
            func.count(DocumentoAdministrativoVinculado.cod_vinculo).label('qtd')
        ).filter(
            DocumentoAdministrativoVinculado.cod_documento_vinculante.in_(cod_documentos),
            DocumentoAdministrativoVinculado.ind_excluido == 0
        ).group_by(DocumentoAdministrativoVinculado.cod_documento_vinculante).all()
        qtd_vinculados_dict = {c.cod_documento_vinculante: c.qtd for c in contagens_vinculados}
        
        # BATCH QUERY 6: Contar matérias vinculadas para todos os documentos
        contagens_materias = session.query(
            DocumentoAdministrativoMateria.cod_documento,
            func.count(DocumentoAdministrativoMateria.cod_vinculo).label('qtd')
        ).filter(
            DocumentoAdministrativoMateria.cod_documento.in_(cod_documentos),
            DocumentoAdministrativoMateria.ind_excluido == 0
        ).group_by(DocumentoAdministrativoMateria.cod_documento).all()
        qtd_materias_dict = {c.cod_documento: c.qtd for c in contagens_materias}
        
        # Cache da pasta de documentos (verificar uma vez)
        docs_folder = None
        try:
            for nome_pasta in ['administrativo', 'documento_administrativo']:
                try:
                    if hasattr(self.context.sapl_documentos, nome_pasta):
                        docs_folder = getattr(self.context.sapl_documentos, nome_pasta)
                        break
                except (AttributeError, KeyError):
                    continue
        except Exception:
            pass
        
        # Formatar resultados usando os dados em batch
        formatted = []
        for doc, tipo_doc in results:
            ultima_tramitacao = tramitacoes_dict.get(doc.cod_documento)
            
            # Determinar URL de visualização
            pode_editar = is_operador or (cod_usuario and doc.tip_documento in tipos_com_permissao)
            if pode_editar:
                url_visualizacao = f"{portal_url}/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento={doc.cod_documento}"
            else:
                url_visualizacao = f"{portal_url}/consultas/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento={doc.cod_documento}"
            
            # Formatar data
            dat_documento_str = doc.dat_documento.strftime('%d/%m/%Y') if doc.dat_documento else ''
            dat_fim_prazo_str = doc.dat_fim_prazo.strftime('%d/%m/%Y') if doc.dat_fim_prazo else ''
            
            # Buscar localização atual (usando cache)
            localizacao_atual = ''
            if ultima_tramitacao:
                unid_tram = ultima_tramitacao.cod_unid_tram_dest or ultima_tramitacao.cod_unid_tram_local
                if unid_tram:
                    localizacao_atual = unidades_dict.get(unid_tram, '')
            
            # Status atual (usando cache)
            status_atual = ''
            dat_tramitacao_str = ''
            if ultima_tramitacao and ultima_tramitacao.cod_status:
                status_atual = status_dict.get(ultima_tramitacao.cod_status, '')
                if ultima_tramitacao.dat_tramitacao:
                    dat_tramitacao_str = ultima_tramitacao.dat_tramitacao.strftime('%d/%m/%Y %H:%M:%S')
            
            # Contagens (usando cache)
            qtd_documentos_acessorios = qtd_acessorios_dict.get(doc.cod_documento, 0)
            qtd_processos_vinculados = qtd_vinculados_dict.get(doc.cod_documento, 0)
            qtd_materias_vinculadas = qtd_materias_dict.get(doc.cod_documento, 0)
            
            # Gerar URLs para texto integral e pasta digital
            url_texto_integral = None
            url_pasta_digital = None
            if docs_folder:
                texto_integral_pdf = f"{doc.cod_documento}_texto_integral.pdf"
                try:
                    arquivo = getattr(docs_folder, texto_integral_pdf, None)
                    if arquivo is not None:
                        url_texto_integral = f"{portal_url}/pysc/download_documento_pysc?cod_documento={doc.cod_documento}"
                        if not mtool.isAnonymousUser():
                            url_pasta_digital = f"{portal_url}/consultas/documento_administrativo/pasta_digital/?cod_documento={doc.cod_documento}&action=pasta"
                except (AttributeError, KeyError):
                    pass
            
            formatted.append({
                'cod_documento': doc.cod_documento,
                'num_documento': doc.num_documento,
                'ano_documento': doc.ano_documento,
                'tip_documento': doc.tip_documento,
                'sgl_tipo_documento': tipo_doc.sgl_tipo_documento or '',
                'des_tipo_documento': tipo_doc.des_tipo_documento or '',
                'txt_assunto': doc.txt_assunto or '',
                'txt_interessado': doc.txt_interessado or '',
                'dat_documento': dat_documento_str,
                'dat_fim_prazo': dat_fim_prazo_str,
                'num_protocolo': doc.num_protocolo,
                'ind_tramitacao': doc.ind_tramitacao,
                'localizacao_atual': localizacao_atual,
                'status_atual': status_atual,
                'dat_tramitacao': dat_tramitacao_str,
                'url_visualizacao': url_visualizacao,
                'url_texto_integral': url_texto_integral,
                'url_pasta_digital': url_pasta_digital,
                'qtd_documentos_acessorios': qtd_documentos_acessorios,
                'qtd_processos_vinculados': qtd_processos_vinculados,
                'qtd_materias_vinculadas': qtd_materias_vinculadas
            })
        
        return formatted

    def _apply_ordering(self, query):
        """Aplica ordenação."""
        ordem = self.request.get('rd_ordenacao', '1')
        if ordem == '2':  # Ascendente
            query = query.order_by(
                TipoDocumentoAdministrativo.sgl_tipo_documento,
                asc(DocumentoAdministrativo.ano_documento),
                asc(func.lpad(cast(DocumentoAdministrativo.num_documento, String), 5, '0'))
            )
        else:  # Descendente (padrão)
            query = query.order_by(
                TipoDocumentoAdministrativo.sgl_tipo_documento,
                desc(DocumentoAdministrativo.ano_documento),
                desc(func.lpad(cast(DocumentoAdministrativo.num_documento, String), 5, '0'))
            )
        return query

    def _calculate_stats_by_type(self, final_data):
        """Calcula estatísticas por tipo de documento administrativo.
        
        Args:
            final_data: Lista de dados formatados dos documentos
            
        Returns:
            Dicionário com tipos como chaves e contagens como valores, ordenado por quantidade (decrescente)
        """
        stats_by_type = {}
        
        for item in final_data:
            tipo_documento = item.get('des_tipo_documento', '')
            if tipo_documento:
                stats_by_type[tipo_documento] = stats_by_type.get(tipo_documento, 0) + 1
        
        # Ordenar por quantidade (decrescente)
        stats_by_type = dict(sorted(stats_by_type.items(), key=lambda x: x[1], reverse=True))
        
        return stats_by_type

    def _export_csv(self, results_raw, session):
        """Exporta resultados para CSV."""
        self.request.response.setHeader('Content-Type', 'text/csv; charset=utf-8')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="processos_administrativos.csv"')
        output = io.StringIO()
        if not results_raw:
            return ""
        
        dados_formatados = self._format_results(results_raw, session)
        
        fieldnames = ['des_tipo_documento', 'num_documento', 'ano_documento', 'txt_assunto', 
                     'txt_interessado', 'dat_documento', 'num_protocolo', 'localizacao_atual', 'status_atual']
        
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(dados_formatados)
        return output.getvalue().encode('utf-8')

    def _export_excel(self, results_raw, session):
        """Exporta resultados para Excel."""
        self.request.response.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="processos_administrativos.xlsx"')
        if not results_raw:
            return b""
        
        dados_formatados = self._format_results(results_raw, session)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Processos Administrativos"
        
        header = ['Tipo', 'Número', 'Ano', 'Assunto', 'Interessado', 'Data', 'Protocolo', 'Localização', 'Situação']
        
        ws.append(header)
        for r in dados_formatados:
            ws.append([
                str(r.get('des_tipo_documento', '')),
                str(r.get('num_documento', '')),
                str(r.get('ano_documento', '')),
                str(r.get('txt_assunto', '')),
                str(r.get('txt_interessado', '')),
                str(r.get('dat_documento', '')),
                str(r.get('num_protocolo', '')),
                str(r.get('localizacao_atual', '')),
                str(r.get('status_atual', ''))
            ])
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    def _export_pdf(self, results_raw, session):
        """Gera um arquivo PDF a partir dos resultados."""
        self.request.response.setHeader('Content-Type', 'application/pdf')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="processos_administrativos.pdf"')
        
        if not results_raw:
            return b""
        
        dados_formatados = self._format_results(results_raw, session)
        
        # Configurações do documento
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
            title="Relatório de Processos Administrativos"
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        normal_style = styles['Normal']
        normal_style.fontSize = 8
        normal_style.leading = 10
        normal_style.wordWrap = 'LTR'
        
        header_style = styles['Heading4']
        header_style.fontSize = 9
        header_style.leading = 12
        header_style.textColor = colors.white
        header_style.alignment = 1  # Center
        
        # Cabeçalho com metadados
        elements = []
        elements.append(Paragraph("RELATÓRIO DE PROCESSOS ADMINISTRATIVOS", styles['Title']))
        elements.append(Paragraph(f"Data de geração: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Paragraph(f"Total de registros: {len(dados_formatados)}", styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))
        
        # Dados da tabela
        header_labels = ['Tipo', 'Número/Ano', 'Assunto', 'Interessado', 'Data', 'Protocolo', 'Localização', 'Situação']
        
        # Preparar dados da tabela
        table_data = []
        
        # Cabeçalho da tabela
        table_data.append([Paragraph(label, header_style) for label in header_labels])
        
        # Linhas de dados
        for item in dados_formatados:
            num_ano = f"{item.get('num_documento', '')}/{item.get('ano_documento', '')}"
            row = [
                Paragraph(str(item.get('des_tipo_documento', '')), normal_style),
                Paragraph(str(num_ano), normal_style),
                Paragraph(str(item.get('txt_assunto', '')), normal_style),
                Paragraph(str(item.get('txt_interessado', '')), normal_style),
                Paragraph(str(item.get('dat_documento', '')), normal_style),
                Paragraph(str(item.get('num_protocolo', '') or ''), normal_style),
                Paragraph(str(item.get('localizacao_atual', '')), normal_style),
                Paragraph(str(item.get('status_atual', '')), normal_style)
            ]
            table_data.append(row)
        
        # Configurações da tabela
        page_width, page_height = landscape(A4)
        content_width = page_width - doc.leftMargin - doc.rightMargin
        
        # Larguras das colunas
        col_widths = [
            0.12 * content_width,  # Tipo
            0.10 * content_width,  # Número/Ano
            0.20 * content_width,  # Assunto
            0.15 * content_width,  # Interessado
            0.10 * content_width,  # Data
            0.10 * content_width,  # Protocolo
            0.13 * content_width,  # Localização
            0.10 * content_width   # Situação
        ]
        
        # Criar tabela
        table = Table(
            table_data,
            colWidths=col_widths,
            repeatRows=1,  # Repete cabeçalho em cada página
            hAlign='LEFT'
        )
        
        # Estilo da tabela
        table.setStyle(TableStyle([
            # Cabeçalho
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            
            # Linhas de dados
            ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (0,1), (1,-1), 'CENTER'),
            ('ALIGN', (2,1), (4,-1), 'LEFT'),
            
            # Grid e bordas
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#2F5597')),
            
            # Zebrado
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F2F2F2')]),
            
            # Espaçamento interno
            ('LEFTPADDING', (0,0), (-1,-1), 3),
            ('RIGHTPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        
        elements.append(table)
        
        # Rodapé com numeração de páginas
        def footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            page_num = f"Página {doc.page}"
            canvas.drawRightString(page_width - 1.5*cm, 1*cm, page_num)
            canvas.drawString(1.5*cm, 1*cm, "SAGL")
            canvas.restoreState()
        
        # Construir documento PDF
        doc.build(elements, onFirstPage=footer, onLaterPages=footer)
        
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data

    def render(self):
        """Processa a requisição e retorna JSON ou exportação."""
        from Products.CMFCore.utils import getToolByName
        
        # Verificar formato de exportação
        formato = self.request.get('formato', '')
        calcular_estatisticas = self.request.get('calcular_estatisticas', '0') == '1'
        
        session = Session()
        try:
            # Construir query base
            query = self._build_base_query(session)
            
            # Aplicar filtros
            query = self._apply_all_filters(query, session)
            
            # Aplicar ordenação
            query = self._apply_ordering(query)
            
            # Para exportação, buscar todos os resultados
            if formato in ('csv', 'excel', 'xlsx', 'pdf'):
                results = query.all()
                
                if formato == 'csv':
                    return self._export_csv(results, session)
                elif formato in ('excel', 'xlsx'):
                    return self._export_excel(results, session)
                elif formato == 'pdf':
                    return self._export_pdf(results, session)
            
            # Para JSON normal, usar paginação
            pagina = self._parse_int_param('pagina', 1)
            itens_por_pagina = self._parse_int_param('itens_por_pagina', 10)
            offset = (pagina - 1) * itens_por_pagina
            
            # Contar total
            total = query.count()
            
            # Buscar resultados
            results = query.offset(offset).limit(itens_por_pagina).all()
            
            # Formatar resultados
            dados_formatados = self._format_results(results, session)
            
            # Calcular estatísticas se solicitado
            stats_by_type = {}
            if calcular_estatisticas:
                # Buscar todos os resultados para estatísticas (com limite para performance)
                max_stats = 5000
                stats_query = query.limit(max_stats).all()
                stats_formatados = self._format_results(stats_query, session)
                stats_by_type = self._calculate_stats_by_type(stats_formatados)
            
            # Retornar JSON
            self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({
                'total': total,
                'pagina': pagina,
                'itens_por_pagina': itens_por_pagina,
                'total_paginas': (total + itens_por_pagina - 1) // itens_por_pagina if itens_por_pagina > 0 else 0,
                'dados': dados_formatados,
                'stats_by_type': stats_by_type
            }, ensure_ascii=False, indent=2)
        finally:
            session.close()

# =================================================================== #
# VIEWS PARA DADOS DE FILTROS
# ===================================================================

class TiposDocumentoView(grok.View):
    """Retorna tipos de documento para filtros com permissões."""
    grok.context(Interface)
    grok.name('tipos_documento_administrativo_json')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        try:
            tipos = _get_tipos_documento_com_permissao(self.context, session)
            self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps(tipos, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao buscar tipos de documento: {str(e)}", exc_info=True)
            self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps([], ensure_ascii=False)
        finally:
            session.close()

class UnidadesTramitacaoView(grok.View):
    """Retorna unidades de tramitação para filtros."""
    grok.context(Interface)
    grok.name('unidades_tramitacao_administrativo_json')
    grok.require('zope2.View')

    def render(self):
        unidades = _get_unidades_tramitacao_cached(Session)
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(unidades, ensure_ascii=False)

class StatusTramitacaoView(grok.View):
    """Retorna status de tramitação para filtros."""
    grok.context(Interface)
    grok.name('status_tramitacao_administrativo_json')
    grok.require('zope2.View')

    def render(self):
        status = _get_status_tramitacao_cached(Session)
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(status, ensure_ascii=False)

class TiposPeticionamentoView(grok.View):
    """Retorna tipos de peticionamento para filtros."""
    grok.context(Interface)
    grok.name('tipos_peticionamento_json')
    grok.require('zope2.View')

    def render(self):
        tipos = _get_tipos_peticionamento_cached(Session)
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(tipos, ensure_ascii=False)

class DocumentoAdministrativoDocumentosView(grok.View):
    """Retorna documentos acessórios, processos vinculados e matérias vinculadas de um processo administrativo."""
    grok.context(Interface)
    grok.name('documento_administrativo_documentos_json')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        try:
            from Products.CMFCore.utils import getToolByName
            cod_documento = self.request.get('cod_documento')
            tipo_documento = self.request.get('tipo')  # 'documentos_acessorios', 'processos_vinculados', 'materias_vinculadas'
            
            if not cod_documento:
                self.request.response.setStatus(400)
                return json.dumps({'error': 'cod_documento é obrigatório'})
            
            cod_documento = int(cod_documento)
            portal_url = getToolByName(self.context, 'portal_url')()
            
            result = {}
            
            if tipo_documento in ['documentos_acessorios', None]:
                # DOCUMENTOS ACESSÓRIOS
                DocumentoAcessorioAdm_doc = aliased(DocumentoAcessorioAdministrativo, name='doc_acessorio_adm')
                TipoDocumentoAdm_doc = aliased(TipoDocumentoAdministrativo, name='tipo_doc_adm')
                docs = session.query(DocumentoAcessorioAdm_doc, TipoDocumentoAdm_doc).\
                    join(TipoDocumentoAdm_doc, DocumentoAcessorioAdm_doc.tip_documento == TipoDocumentoAdm_doc.tip_documento).\
                    filter(
                        DocumentoAcessorioAdm_doc.cod_documento == cod_documento,
                        DocumentoAcessorioAdm_doc.ind_excluido == 0
                    ).order_by(DocumentoAcessorioAdm_doc.cod_documento_acessorio).all()
                docs_data = []
                for d, td in docs:
                    doc_id = f"{d.cod_documento_acessorio}_documento_acessorio.pdf"
                    url = None
                    try:
                        sapl_docs = self.context.sapl_documentos.administrativo
                        if hasattr(sapl_docs, doc_id):
                            url = f"{portal_url}/sapl_documentos/administrativo/{doc_id}"
                    except:
                        pass
                    docs_data.append({
                        'cod_documento_acessorio': d.cod_documento_acessorio,
                        'tip_documento': d.tip_documento,
                        'des_tipo_documento': td.des_tipo_documento if td else '',
                        'nom_documento': d.nom_documento or '',
                        'nom_autor_documento': d.nom_autor_documento or '',
                        'dat_documento': d.dat_documento.strftime('%d/%m/%Y') if d.dat_documento else None,
                        'txt_assunto': d.txt_assunto or '',
                        'url': url
                    })
                result['documentos_acessorios'] = docs_data
            
            if tipo_documento in ['processos_vinculados', None]:
                # PROCESSOS VINCULADOS
                processos = session.query(DocumentoAdministrativo, TipoDocumentoAdministrativo).\
                    join(DocumentoAdministrativoVinculado, 
                         DocumentoAdministrativoVinculado.cod_documento_vinculado == DocumentoAdministrativo.cod_documento).\
                    join(TipoDocumentoAdministrativo, 
                         DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento).\
                    filter(
                        DocumentoAdministrativoVinculado.cod_documento_vinculante == cod_documento,
                        DocumentoAdministrativoVinculado.ind_excluido == 0,
                        DocumentoAdministrativo.ind_excluido == 0
                    ).order_by(DocumentoAdministrativo.ano_documento.desc(), DocumentoAdministrativo.num_documento.desc()).all()
                processos_data = []
                for proc, tipo_proc in processos:
                    processos_data.append({
                        'cod_documento': proc.cod_documento,
                        'num_documento': proc.num_documento,
                        'ano_documento': proc.ano_documento,
                        'sgl_tipo_documento': tipo_proc.sgl_tipo_documento or '',
                        'des_tipo_documento': tipo_proc.des_tipo_documento or '',
                        'txt_assunto': proc.txt_assunto or '',
                        'txt_interessado': proc.txt_interessado or '',
                        'dat_documento': proc.dat_documento.strftime('%d/%m/%Y') if proc.dat_documento else None,
                        'url': f"{portal_url}/consultas/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento={proc.cod_documento}"
                    })
                result['processos_vinculados'] = processos_data
            
            if tipo_documento in ['materias_vinculadas', None]:
                # MATÉRIAS VINCULADAS
                MateriaLegislativa_mat = aliased(MateriaLegislativa, name='materia_legislativa')
                TipoMateriaLegislativa_mat = aliased(TipoMateriaLegislativa, name='tipo_materia')
                materias = session.query(MateriaLegislativa_mat, TipoMateriaLegislativa_mat).\
                    join(DocumentoAdministrativoMateria, 
                         DocumentoAdministrativoMateria.cod_materia == MateriaLegislativa_mat.cod_materia).\
                    join(TipoMateriaLegislativa_mat, 
                         MateriaLegislativa_mat.tip_id_basica == TipoMateriaLegislativa_mat.tip_materia).\
                    filter(
                        DocumentoAdministrativoMateria.cod_documento == cod_documento,
                        DocumentoAdministrativoMateria.ind_excluido == 0,
                        MateriaLegislativa_mat.ind_excluido == 0
                    ).order_by(MateriaLegislativa_mat.ano_ident_basica.desc(), MateriaLegislativa_mat.num_ident_basica.desc()).all()
                materias_data = []
                for mat, tipo_mat in materias:
                    materias_data.append({
                        'cod_materia': mat.cod_materia,
                        'num_ident_basica': mat.num_ident_basica,
                        'ano_ident_basica': mat.ano_ident_basica,
                        'sgl_tipo_materia': tipo_mat.sgl_tipo_materia or '',
                        'des_tipo_materia': tipo_mat.des_tipo_materia or '',
                        'txt_ementa': mat.txt_ementa or '',
                        'dat_apresentacao': mat.dat_apresentacao.strftime('%d/%m/%Y') if mat.dat_apresentacao else None,
                        'url': f"{portal_url}/consultas/materia/materia_mostrar_proc?cod_materia={mat.cod_materia}"
                    })
                result['materias_vinculadas'] = materias_data
            
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Erro ao buscar documentos do processo administrativo: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao buscar documentos', 'details': str(e)})
        finally:
            session.close()
