# -*- coding: utf-8 -*-
from five import grok
from zope.interface import Interface
from z3c.saconfig import named_scoped_session
from openlegis.sagl.models.models import (
    MateriaLegislativa, TipoMateriaLegislativa, Tramitacao,
    Autoria, AutoriaEmenda, AutoriaSubstitutivo, Relatoria, Parlamentar, UnidadeTramitacao, StatusTramitacao,
    Comissao, Orgao, Autor, TipoAutor, Bancada, Legislatura, TipoFimRelatoria,
    DocumentoAcessorio, TipoDocumento, Substitutivo, Emenda, TipoEmenda, Parecer,
    RegimeTramitacao, QuorumVotacao, TipoNormaJuridica, TipoSituacaoNorma,
    NormaJuridica, Anexada, Numeracao
)
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy import case, func, and_, or_, cast, String, Integer, select, text, asc, desc, literal, union_all, column
from sqlalchemy.sql import expression, literal_column
import re
from datetime import datetime
import json
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
from Products.CMFCore.utils import getToolByName
from functools import lru_cache
import logging
import time

logger = logging.getLogger(__name__)
Session = named_scoped_session('minha_sessao')

# =================================================================== #
# FUNÇÕES UTILITÁRIAS E CACHEADAS
# =================================================================== #

def _build_autor_name_expression(TipoAutor_alias=None, Parlamentar_alias=None, Comissao_alias=None, 
                                  Bancada_alias=None, Legislatura_alias=None, Autor_alias=None):
    """Constrói e retorna a expressão SQLAlchemy para o nome formatado do autor.
    Aceita aliases opcionais para uso em queries com múltiplas tabelas."""
    TipoAutor_ref = TipoAutor_alias if TipoAutor_alias else TipoAutor
    Parlamentar_ref = Parlamentar_alias if Parlamentar_alias else Parlamentar
    Comissao_ref = Comissao_alias if Comissao_alias else Comissao
    Bancada_ref = Bancada_alias if Bancada_alias else Bancada
    Legislatura_ref = Legislatura_alias if Legislatura_alias else Legislatura
    Autor_ref = Autor_alias if Autor_alias else Autor
    
    bancada_formatada = func.concat(
        Bancada_ref.nom_bancada, " (",
        func.date_format(Legislatura_ref.dat_inicio, '%Y'), "-",
        func.date_format(Legislatura_ref.dat_fim, '%Y'), ")"
    )
    nom_autor_case = case(
        (TipoAutor_ref.des_tipo_autor == 'Parlamentar', Parlamentar_ref.nom_parlamentar),
        (TipoAutor_ref.des_tipo_autor == 'Bancada', bancada_formatada),
        (TipoAutor_ref.des_tipo_autor == 'Comissao', Comissao_ref.nom_comissao),
        (True, Autor_ref.nom_autor)
    )
    return nom_autor_case

@lru_cache(maxsize=2)  # Apenas 2: anonymous/authenticated (não precisa mais filtrar por tipo_pesquisa)
def _get_tipos_materia_cached(is_anonymous, session_factory):
    session = session_factory()
    try:
        query = session.query(TipoMateriaLegislativa).filter(
            TipoMateriaLegislativa.ind_excluido == 0
        )
        if is_anonymous:
            query = query.filter(TipoMateriaLegislativa.ind_publico == 1)
        
        tipos = query.order_by(TipoMateriaLegislativa.des_tipo_materia).all()
        result = {'principais': [], 'acessorias': []}
        
        # Verificar se já existem tipos com texto exato "Emenda" ou "Substitutivo"
        textos_acessorios = set()
        
        for t in tipos:
            item = {'id': t.tip_materia, 'text': t.des_tipo_materia}
            if t.tip_natureza == 'P':
                result['principais'].append(item)
            elif t.tip_natureza == 'A':
                result['acessorias'].append(item)
                # Guardar textos dos tipos acessórios para verificar duplicação
                if t.des_tipo_materia:
                    textos_acessorios.add(t.des_tipo_materia.strip().lower())
        
        # Adicionar Emenda e Substitutivo apenas se não existirem tipos com esses nomes exatos
        # (sempre em Matérias Acessórias, mesmo que não existam tipos acessórios cadastrados)
        if 'emenda' not in textos_acessorios:
            result['acessorias'].append({'id': 'EMENDA', 'text': 'Emenda'})
        if 'substitutivo' not in textos_acessorios:
            result['acessorias'].append({'id': 'SUBSTITUTIVO', 'text': 'Substitutivo'})
        
        return result
    finally:
        session.close()

@lru_cache(maxsize=1)
def _get_autores_cached(session_factory):
    session = session_factory()
    try:
        nome_autor_expr = _build_autor_name_expression()
        query = session.query(Autor.cod_autor, nome_autor_expr.label('nome_autor'))\
            .join(TipoAutor, Autor.tip_autor == TipoAutor.tip_autor)\
            .outerjoin(Parlamentar, Autor.cod_parlamentar == Parlamentar.cod_parlamentar)\
            .outerjoin(Comissao, Autor.cod_comissao == Comissao.cod_comissao)\
            .outerjoin(Bancada, Autor.cod_bancada == Bancada.cod_bancada)\
            .outerjoin(Legislatura, Bancada.num_legislatura == Legislatura.num_legislatura)\
            .filter(Autor.ind_excluido == 0).order_by(nome_autor_expr)
        autores = query.all()
        return [{'id': cod, 'text': nome} for cod, nome in autores if nome]
    finally:
        session.close()

@lru_cache(maxsize=1)
def _get_unidades_tramitacao_cached(session_factory):
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
            .filter(UnidadeTramitacao.ind_excluido == 0, UnidadeTramitacao.ind_leg == 1)\
            .order_by(nome_unidade)
        unidades = query.all()
        return [{'id': cod, 'text': nome} for cod, nome in unidades if nome]
    finally:
        session.close()

@lru_cache(maxsize=1)
def _get_status_tramitacao_cached(session_factory):
    session = session_factory()
    try:
        query = session.query(StatusTramitacao).filter(
            StatusTramitacao.ind_excluido == 0
        ).order_by(StatusTramitacao.sgl_status)
        status_list = query.all()
        return [{'id': s.cod_status, 'text': f"{s.sgl_status} - {s.des_status}"} for s in status_list]
    finally:
        session.close()

@lru_cache(maxsize=1)
def _get_tipos_autor_cached(session_factory):
    session = session_factory()
    try:
        query = session.query(TipoAutor).filter(
            TipoAutor.ind_excluido == 0
        ).order_by(TipoAutor.des_tipo_autor)
        tipos = query.all()
        return [{'id': t.tip_autor, 'text': t.des_tipo_autor} for t in tipos]
    finally:
        session.close()

@lru_cache(maxsize=1)
def _get_relatores_cached(session_factory):
    """Retorna apenas parlamentares que podem ser relatores."""
    session = session_factory()
    try:
        # Buscar parlamentares que já foram relatores ou todos os parlamentares ativos
        # Vamos buscar parlamentares que têm relatorias ou todos os parlamentares ativos
        query = session.query(
            Parlamentar.cod_parlamentar,
            Parlamentar.nom_parlamentar
        ).filter(
            Parlamentar.ind_excluido == 0
        ).order_by(Parlamentar.nom_parlamentar)
        parlamentares = query.all()
        return [{'id': cod, 'text': nome} for cod, nome in parlamentares if nome]
    finally:
        session.close()

# =================================================================== #
# CLASSE MateriaLegislativaView COM EXPORTAÇÃO DE PDF MELHORADA
# =================================================================== #

class MateriaLegislativaView(grok.View):
    """View principal da busca com exportação PDF aprimorada."""
    grok.context(Interface)
    grok.name('materias_legislativas_json')
    grok.require('zope2.View')

    def _parse_int_param(self, param_name, default=None):
        value = self.request.get(param_name)
        return int(value) if value and str(value).isdigit() else default

    def _parse_list_param(self, param_name):
        """Retorna lista de valores (strings ou inteiros) do parâmetro."""
        values = self.request.get(param_name)
        if not values:
            return None
        if isinstance(values, str):
            if values.startswith('[') and values.endswith(']'):
                try:
                    return json.loads(values)
                except:
                    return [values]
            return [values]
        if isinstance(values, (list, tuple)):
            return list(values)
        return [values]
    
    def _parse_list_param(self, param_name):
        """Retorna lista de valores (strings ou inteiros) do parâmetro."""
        values = self.request.get(param_name)
        if not values:
            return None
        if isinstance(values, str):
            if values.startswith('[') and values.endswith(']'):
                try:
                    return json.loads(values)
                except:
                    return [values]
            # Tentar dividir por vírgula
            return [v.strip() for v in values.split(',') if v.strip()]
        if isinstance(values, (list, tuple)):
            return list(values)
        return [values]
    
    def _parse_int_list_param(self, param_name):
        """Retorna lista de inteiros do parâmetro (filtra valores não numéricos)."""
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
        if not date_str: return None
        try:
            if '/' in date_str:
                return datetime.strptime(date_str, '%d/%m/%Y').date()
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None

    def _build_base_query_for_filters(self, session):
        query = session.query(MateriaLegislativa, TipoMateriaLegislativa)\
            .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
            .filter(MateriaLegislativa.ind_excluido == 0)
        mtool = getToolByName(self.context, 'portal_membership')
        if mtool.isAnonymousUser():
            query = query.filter(TipoMateriaLegislativa.ind_publico == 1)
        return query

    def _build_acessoria_principal_query(self, session):
        """Constrói query para matérias acessórias principais (tip_natureza='A')."""
        mtool = getToolByName(self.context, 'portal_membership')
        # Usar literal_column com CAST e COLLATE para garantir mesma collation
        query = session.query(
            MateriaLegislativa.cod_materia.label('cod_item'),
            literal_column("CAST('acessoria_principal' AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('tipo_item'),
            MateriaLegislativa.cod_materia.label('cod_materia_principal'),
            literal_column("CAST(tipo_materia_legislativa.des_tipo_materia AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('des_tipo_materia'),
            MateriaLegislativa.num_ident_basica.label('num_ident_basica'),
            MateriaLegislativa.ano_ident_basica.label('ano_ident_basica'),
            literal_column("CAST(COALESCE(materia_legislativa.txt_ementa, '') AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('txt_ementa'),
            MateriaLegislativa.dat_apresentacao.label('dat_apresentacao'),
            MateriaLegislativa.num_protocolo.label('num_protocolo'),
            MateriaLegislativa.cod_materia.label('cod_materia'),
            literal_column("CAST(COALESCE(tipo_materia_legislativa.sgl_tipo_materia, '') AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('sgl_tipo_materia'),
            cast(None, Integer).label('cod_emenda'),
            cast(None, Integer).label('cod_substitutivo'),
            cast(None, Integer).label('tip_emenda'),
            literal_column("CAST(NULL AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('des_tipo_emenda'),
            cast(None, Integer).label('num_emenda'),
            cast(None, Integer).label('num_substitutivo')
        ).join(
            TipoMateriaLegislativa,
            MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
        ).filter(
            TipoMateriaLegislativa.tip_natureza == 'A',
            MateriaLegislativa.ind_excluido == 0
        )
        if mtool.isAnonymousUser():
            query = query.filter(TipoMateriaLegislativa.ind_publico == 1)
        return query

    def _build_emenda_query(self, session):
        """Constrói query para emendas."""
        mtool = getToolByName(self.context, 'portal_membership')
        query = session.query(
            Emenda.cod_emenda.label('cod_item'),
            literal_column("CAST('emenda' AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('tipo_item'),
            Emenda.cod_materia.label('cod_materia_principal'),
            literal_column("CAST(tipo_emenda.des_tipo_emenda AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('des_tipo_materia'),
            Emenda.num_emenda.label('num_ident_basica'),
            func.year(Emenda.dat_apresentacao).label('ano_ident_basica'),
            literal_column("CAST(COALESCE(emenda.txt_ementa, '') AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('txt_ementa'),
            Emenda.dat_apresentacao.label('dat_apresentacao'),
            Emenda.num_protocolo.label('num_protocolo'),
            Emenda.cod_materia.label('cod_materia'),
            literal_column("CAST(NULL AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('sgl_tipo_materia'),
            Emenda.cod_emenda.label('cod_emenda'),
            cast(None, Integer).label('cod_substitutivo'),
            Emenda.tip_emenda.label('tip_emenda'),
            literal_column("CAST(tipo_emenda.des_tipo_emenda AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('des_tipo_emenda'),
            Emenda.num_emenda.label('num_emenda'),
            cast(None, Integer).label('num_substitutivo')
        ).join(
            TipoEmenda, Emenda.tip_emenda == TipoEmenda.tip_emenda
        ).join(
            MateriaLegislativa, Emenda.cod_materia == MateriaLegislativa.cod_materia
        ).join(
            TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
        ).filter(
            Emenda.ind_excluido == 0
        )
        if mtool.isAnonymousUser():
            query = query.filter(TipoMateriaLegislativa.ind_publico == 1)
        return query

    def _build_substitutivo_query(self, session):
        """Constrói query para substitutivos."""
        mtool = getToolByName(self.context, 'portal_membership')
        query = session.query(
            Substitutivo.cod_substitutivo.label('cod_item'),
            literal_column("CAST('substitutivo' AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('tipo_item'),
            Substitutivo.cod_materia.label('cod_materia_principal'),
            literal_column("CAST('Substitutivo' AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('des_tipo_materia'),
            Substitutivo.num_substitutivo.label('num_ident_basica'),
            func.year(Substitutivo.dat_apresentacao).label('ano_ident_basica'),
            literal_column("CAST(COALESCE(substitutivo.txt_ementa, '') AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('txt_ementa'),
            Substitutivo.dat_apresentacao.label('dat_apresentacao'),
            Substitutivo.num_protocolo.label('num_protocolo'),
            Substitutivo.cod_materia.label('cod_materia'),
            literal_column("CAST(NULL AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('sgl_tipo_materia'),
            cast(None, Integer).label('cod_emenda'),
            Substitutivo.cod_substitutivo.label('cod_substitutivo'),
            cast(None, Integer).label('tip_emenda'),
            literal_column("CAST(NULL AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('des_tipo_emenda'),
            cast(None, Integer).label('num_emenda'),
            Substitutivo.num_substitutivo.label('num_substitutivo')
        ).join(
            MateriaLegislativa, Substitutivo.cod_materia == MateriaLegislativa.cod_materia
        ).join(
            TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
        ).filter(
            Substitutivo.ind_excluido == 0
        )
        if mtool.isAnonymousUser():
            query = query.filter(TipoMateriaLegislativa.ind_publico == 1)
        return query

    def _determine_search_scope(self, session):
        """Determina o escopo da pesquisa baseado nos tipos de matéria selecionados."""
        tipos_selecionados = self._parse_list_param('tip_id_basica')
        
        # Verificar se há filtros avançados aplicados (exceto data de apresentação)
        # Filtros avançados que não se aplicam a emendas e substitutivos:
        tem_filtro_avancado = False
        if (self._parse_int_param('cod_status') is not None or
            self._parse_int_param('cod_unid_tramitacao') is not None or
            self._parse_int_param('cod_unid_tramitacao2') is not None or
            self._parse_int_param('num_processo') is not None or
            self._parse_int_param('num_protocolo') is not None or
            (self.request.get('ind_tramitacao') and self.request.get('ind_tramitacao').isdigit()) or
            self._parse_int_param('cod_relator') is not None or
            self._parse_int_param('tip_autor') is not None or
            self._parse_date_param('dat_publicacao') is not None or
            self._parse_date_param('dat_publicacao2') is not None):
            tem_filtro_avancado = True
        
        if not tipos_selecionados:
            # Se nenhum tipo selecionado
            if tem_filtro_avancado:
                # Se há filtro avançado (exceto data de apresentação), pesquisar apenas matérias principais
                return {
                    'pesquisa_principal': True,
                    'pesquisa_acessoria': False,
                    'pesquisa_emenda': False,  # Não incluir emendas quando há filtro avançado
                    'pesquisa_substitutivo': False,  # Não incluir substitutivos quando há filtro avançado
                    'tipos_principais': None,
                    'tipos_acessorios': None
                }
            else:
                # Comportamento padrão: principais + emendas + substitutivos
                return {
                    'pesquisa_principal': True,
                    'pesquisa_acessoria': False,
                    'pesquisa_emenda': True,  # Incluir emendas quando nenhum tipo selecionado
                    'pesquisa_substitutivo': True,  # Incluir substitutivos quando nenhum tipo selecionado
                    'tipos_principais': None,
                    'tipos_acessorios': None
                }
        
        # Verificar se há opções especiais selecionadas
        pesquisa_emenda = 'EMENDA' in tipos_selecionados
        pesquisa_substitutivo = 'SUBSTITUTIVO' in tipos_selecionados
        
        # Se há filtros avançados e não são apenas EMENDA/SUBSTITUTIVO selecionados, excluir emendas e substitutivos
        if tem_filtro_avancado and not (pesquisa_emenda or pesquisa_substitutivo):
            # Se há filtros avançados e não foram selecionados especificamente EMENDA/SUBSTITUTIVO,
            # pesquisar apenas matérias principais (excluir emendas e substitutivos)
            tipos_normais = [t for t in tipos_selecionados if t not in ('EMENDA', 'SUBSTITUTIVO')]
            if tipos_normais:
                # Buscar tipos principais
                tipos_materia = session.query(
                    TipoMateriaLegislativa.tip_materia,
                    TipoMateriaLegislativa.tip_natureza
                ).filter(
                    TipoMateriaLegislativa.tip_materia.in_([int(t) for t in tipos_normais if t.isdigit()]),
                    TipoMateriaLegislativa.ind_excluido == 0
                ).all()
                
                tipos_principais_ids = [t.tip_materia for t in tipos_materia if t.tip_natureza == 'P']
                tipos_acessorios_ids = [t.tip_materia for t in tipos_materia if t.tip_natureza == 'A']
                
                return {
                    'pesquisa_principal': bool(tipos_principais_ids),
                    'pesquisa_acessoria': bool(tipos_acessorios_ids),
                    'pesquisa_emenda': False,  # Excluir emendas quando há filtros avançados
                    'pesquisa_substitutivo': False,  # Excluir substitutivos quando há filtros avançados
                    'tipos_principais': tipos_principais_ids if tipos_principais_ids else None,
                    'tipos_acessorios': tipos_acessorios_ids if tipos_acessorios_ids else None
                }
            else:
                # Apenas tipos não numéricos selecionados, pesquisar apenas principais
                return {
                    'pesquisa_principal': True,
                    'pesquisa_acessoria': False,
                    'pesquisa_emenda': False,
                    'pesquisa_substitutivo': False,
                    'tipos_principais': None,
                    'tipos_acessorios': None
                }
        
        # Remover opções especiais da lista para verificar tipos normais
        tipos_normais = [t for t in tipos_selecionados if t not in ('EMENDA', 'SUBSTITUTIVO')]
        
        # Buscar tipos acessórios relacionados a emenda/substitutivo em tipo_materia_legislativa
        tipos_acessorios_emenda = []
        tipos_acessorios_substitutivo = []
        
        if pesquisa_emenda or pesquisa_substitutivo:
            # Buscar tipos acessórios que correspondem exatamente a "Emenda" ou "Substitutivo"
            # (busca case-insensitive e por correspondência exata ou parcial)
            tipos_acessorios = session.query(
                TipoMateriaLegislativa.tip_materia,
                TipoMateriaLegislativa.des_tipo_materia
            ).filter(
                TipoMateriaLegislativa.tip_natureza == 'A',
                TipoMateriaLegislativa.ind_excluido == 0
            ).all()
            
            for tipo in tipos_acessorios:
                if not tipo.des_tipo_materia:
                    continue
                tipo_nome_lower = tipo.des_tipo_materia.lower().strip()
                # Verificar correspondência exata ou se contém "emenda" ou "substitutivo"
                if pesquisa_emenda:
                    if tipo_nome_lower == 'emenda' or 'emenda' in tipo_nome_lower:
                        tipos_acessorios_emenda.append(tipo.tip_materia)
                if pesquisa_substitutivo:
                    if tipo_nome_lower == 'substitutivo' or 'substitutivo' in tipo_nome_lower:
                        tipos_acessorios_substitutivo.append(tipo.tip_materia)
        
        # Combinar tipos acessórios selecionados com tipos relacionados a emenda/substitutivo
        tipos_acessorios_combinados = set()
        
        # Se apenas opções especiais foram selecionadas (Emenda e/ou Substitutivo)
        if not tipos_normais:
            # Adicionar tipos acessórios relacionados encontrados em tipo_materia_legislativa
            tipos_acessorios_combinados.update(tipos_acessorios_emenda)
            tipos_acessorios_combinados.update(tipos_acessorios_substitutivo)
            
            if pesquisa_emenda and pesquisa_substitutivo:
                # Ambos selecionados: pesquisa unificada de emendas e substitutivos
                return {
                    'pesquisa_principal': False,
                    'pesquisa_acessoria': True,  # Marcar como acessória para usar query unificada
                    'pesquisa_emenda': True,
                    'pesquisa_substitutivo': True,
                    'tipos_principais': None,
                    'tipos_acessorios': list(tipos_acessorios_combinados) if tipos_acessorios_combinados else None
                }
            elif pesquisa_emenda:
                return {
                    'pesquisa_principal': False,
                    'pesquisa_acessoria': True,  # Marcar como acessória para incluir tipos relacionados
                    'pesquisa_emenda': True,
                    'pesquisa_substitutivo': False,
                    'tipos_principais': None,
                    'tipos_acessorios': list(tipos_acessorios_combinados) if tipos_acessorios_combinados else None
                }
            elif pesquisa_substitutivo:
                return {
                    'pesquisa_principal': False,
                    'pesquisa_acessoria': True,  # Marcar como acessória para incluir tipos relacionados
                    'pesquisa_emenda': False,
                    'pesquisa_substitutivo': True,
                    'tipos_principais': None,
                    'tipos_acessorios': list(tipos_acessorios_combinados) if tipos_acessorios_combinados else None
                }
        
        # Verificar quais tipos são principais e quais são acessórios
        if tipos_normais:
            tipos_principais_ids = []
            tipos_acessorios_ids = []
            
            tipos_materia = session.query(
                TipoMateriaLegislativa.tip_materia,
                TipoMateriaLegislativa.tip_natureza,
                TipoMateriaLegislativa.des_tipo_materia
            ).filter(
                TipoMateriaLegislativa.tip_materia.in_([int(t) for t in tipos_normais if t.isdigit()]),
                TipoMateriaLegislativa.ind_excluido == 0
            ).all()
            
            # Verificar se algum dos tipos selecionados corresponde a "Emenda" ou "Substitutivo"
            for tipo in tipos_materia:
                if tipo.tip_natureza == 'P':
                    tipos_principais_ids.append(tipo.tip_materia)
                elif tipo.tip_natureza == 'A':
                    tipos_acessorios_ids.append(tipo.tip_materia)
                    # Verificar se o tipo corresponde a "Emenda" ou "Substitutivo"
                    if tipo.des_tipo_materia:
                        tipo_nome_lower = tipo.des_tipo_materia.lower().strip()
                        if 'emenda' in tipo_nome_lower:
                            pesquisa_emenda = True
                            if tipo.tip_materia not in tipos_acessorios_emenda:
                                tipos_acessorios_emenda.append(tipo.tip_materia)
                        if 'substitutivo' in tipo_nome_lower:
                            pesquisa_substitutivo = True
                            if tipo.tip_materia not in tipos_acessorios_substitutivo:
                                tipos_acessorios_substitutivo.append(tipo.tip_materia)
            
            # Adicionar tipos acessórios relacionados a emenda/substitutivo se encontrados
            if tipos_acessorios_emenda:
                tipos_acessorios_ids.extend(tipos_acessorios_emenda)
            if tipos_acessorios_substitutivo:
                tipos_acessorios_ids.extend(tipos_acessorios_substitutivo)
            
            # Remover duplicatas
            tipos_acessorios_ids = list(set(tipos_acessorios_ids)) if tipos_acessorios_ids else []
            
            pesquisa_principal = len(tipos_principais_ids) > 0
            pesquisa_acessoria = len(tipos_acessorios_ids) > 0 or pesquisa_emenda or pesquisa_substitutivo
            
            return {
                'pesquisa_principal': pesquisa_principal,
                'pesquisa_acessoria': pesquisa_acessoria,
                'pesquisa_emenda': pesquisa_emenda,
                'pesquisa_substitutivo': pesquisa_substitutivo,
                'tipos_principais': tipos_principais_ids if tipos_principais_ids else None,
                'tipos_acessorios': tipos_acessorios_ids if tipos_acessorios_ids else None
            }
        
        # Fallback: comportamento padrão
        return {
            'pesquisa_principal': True,
            'pesquisa_acessoria': False,
            'pesquisa_emenda': False,
            'pesquisa_substitutivo': False,
            'tipos_principais': None,
            'tipos_acessorios': None
        }

    def _apply_all_filters(self, query, session):
        query = self._apply_materia_filters(query)
        query = self._apply_date_filters(query)
        query = self._apply_text_search(query)
        query = self._apply_author_filter(query)
        query = self._apply_rapporteur_filter(query)
        query = self._apply_tramitacao_filters(query, session)
        return query
    
    def _apply_all_filters_to_unified_query(self, query, session):
        """Aplica filtros à query unificada de matérias principais (compatível com UNION)."""
        # Filtro por número, ano, protocolo
        if (val := self._parse_int_param('num_ident_basica')) is not None:
            query = query.filter(MateriaLegislativa.num_ident_basica == val)
        if (val := self._parse_int_param('ano_ident_basica')) is not None:
            query = query.filter(MateriaLegislativa.ano_ident_basica == val)
        if (val := self._parse_int_param('num_protocolo')) is not None:
            query = query.filter(MateriaLegislativa.num_protocolo == val)
        
        # Filtro por tipo (já aplicado na query base, mas pode ser refinado)
        if (tipos := self._parse_int_list_param('tip_id_basica')):
            # Buscar tipos principais
            tipos_principais = session.query(TipoMateriaLegislativa.tip_materia).filter(
                TipoMateriaLegislativa.tip_materia.in_(tipos),
                TipoMateriaLegislativa.tip_natureza == 'P',
                TipoMateriaLegislativa.ind_excluido == 0
            ).all()
            if tipos_principais:
                tipos_ids = [t.tip_materia for t in tipos_principais]
                # Filtrar pela matéria através do join
                query = query.filter(MateriaLegislativa.tip_id_basica.in_(tipos_ids))
        
        # Filtro por tramitação
        if (val := self.request.get('ind_tramitacao')) and val.isdigit():
            query = query.filter(MateriaLegislativa.ind_tramitacao == int(val))
        
        # Filtro por data de apresentação
        dat1 = self._parse_date_param('dat_apresentacao')
        dat2 = self._parse_date_param('dat_apresentacao2')
        if dat1 and dat2:
            query = query.filter(MateriaLegislativa.dat_apresentacao.between(dat1, dat2))
        elif dat1:
            query = query.filter(MateriaLegislativa.dat_apresentacao >= dat1)
        elif dat2:
            query = query.filter(MateriaLegislativa.dat_apresentacao <= dat2)
        
        # Filtro por texto (ementa)
        termo = self.request.get('des_assunto')
        if termo:
            termos_limpos = re.sub(r'[^\w\s]', ' ', termo)
            termos_limpos = ' '.join(termos_limpos.split())
            if termos_limpos:
                # Filtrar palavras monossílabas antes de fazer a busca
                palavras = termos_limpos.split()
                palavras_filtradas = self._filter_monosyllabic_words(palavras)
                if palavras_filtradas:
                    termos_filtrados = ' '.join(palavras_filtradas)
                    palavra_term = f"%{termos_filtrados}%"
                    query = query.filter(MateriaLegislativa.txt_ementa.ilike(palavra_term))
        
        # Filtro por autoria
        cod_autor = self._parse_int_param('cod_autor')
        chk_coautor = self.request.get('chk_coautor') == '1'
        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
        if cod_autor is not None:
            autoria_subq = session.query(Autoria.cod_materia).filter(
                Autoria.cod_autor == cod_autor,
                Autoria.ind_excluido == 0
            )
            # Filtro de coautor: apenas quando ind_primeiro_autor = 0
            if chk_coautor:
                autoria_subq = autoria_subq.filter(Autoria.ind_primeiro_autor == 0)
            # Filtro de primeiro autor: apenas quando ind_primeiro_autor = 1
            elif chk_primeiro_autor:
                autoria_subq = autoria_subq.filter(Autoria.ind_primeiro_autor == 1)
            autoria_subq = autoria_subq.distinct()
            query = query.filter(MateriaLegislativa.cod_materia.in_(autoria_subq))
        
        return query

    def _apply_materia_filters(self, query):
        for field in ['num_ident_basica', 'ano_ident_basica', 'num_protocolo', 'num_processo']:
            if (val := self._parse_int_param(field)) is not None:
                query = query.filter(getattr(MateriaLegislativa, field) == val)
        if (tipos := self._parse_int_list_param('tip_id_basica')):
            query = query.filter(MateriaLegislativa.tip_id_basica.in_(tipos))
        if (val := self.request.get('ind_tramitacao')) and val.isdigit():
            query = query.filter(MateriaLegislativa.ind_tramitacao == int(val))
        return query

    def _apply_date_filters(self, query):
        # Data de Apresentação
        dat1 = self._parse_date_param('dat_apresentacao')
        dat2 = self._parse_date_param('dat_apresentacao2')
        if dat1 and dat2:
            query = query.filter(MateriaLegislativa.dat_apresentacao.between(dat1, dat2))
        elif dat1:
            query = query.filter(MateriaLegislativa.dat_apresentacao >= dat1)
        elif dat2:
            query = query.filter(MateriaLegislativa.dat_apresentacao <= dat2)
        
        # Data de Publicação (NOVO)
        dat_pub1 = self._parse_date_param('dat_publicacao')
        dat_pub2 = self._parse_date_param('dat_publicacao2')
        if dat_pub1 and dat_pub2:
            query = query.filter(MateriaLegislativa.dat_publicacao.between(dat_pub1, dat_pub2))
        elif dat_pub1:
            query = query.filter(MateriaLegislativa.dat_publicacao >= dat_pub1)
        elif dat_pub2:
            query = query.filter(MateriaLegislativa.dat_publicacao <= dat_pub2)
        
        return query

    def _calculate_stats_by_author(self, final_data, autor_filtrado=None, apenas_coautor=False, apenas_primeiro_autor=False):
        """Calcula estatísticas por autor a partir dos dados formatados, incluindo quantidade por tipo de matéria.
        
        Comportamento:
        - Sem filtro de autor específico:
          * Se "apenas como coautor" marcado: considera apenas coautores (não primeiros autores)
          * Se "apenas como 1º autor" marcado: considera apenas primeiros autores
          * Se nenhuma opção marcada: considera todos os autores (primeiros e coautores)
        - Com filtro de autor específico:
          * Considera apenas o autor filtrado, respeitando as opções de coautor/1º autor
        - Para emendas e substitutivos: considera apenas o primeiro autor (se não houver filtro específico)
        
        Args:
            final_data: Lista de dados formatados das matérias
            autor_filtrado: Nome do autor a ser filtrado (opcional). Se fornecido, apenas esse autor será considerado,
                           respeitando as opções de coautor/1º autor.
            apenas_coautor: Se True, considera apenas coautores (não primeiros autores).
                           Também exclui emendas e substitutivos, pois essas tabelas não têm ind_primeiro_autor.
            apenas_primeiro_autor: Se True, considera apenas primeiros autores.
                                  Também exclui emendas e substitutivos, pois essas tabelas não têm ind_primeiro_autor.
        """
        stats_by_author = {}
        for item in final_data:
            autores_str = item.get('autores', '')
            # Se há autor filtrado, o item DEVE ter autores (a query SQL já filtrou)
            # Se não tem autores, pode ser um problema de carregamento de autoria
            if not autores_str:
                if autor_filtrado:
                    # Se há autor filtrado mas o item não tem autores, isso é um problema
                    # A query SQL já filtrou por esse autor, então deveria ter autoria
                    # Mas vamos pular para evitar erro (pode ser um problema de carregamento)
                    continue
                else:
                    # Sem autor filtrado, pular itens sem autores
                    continue
            
            # Obter tipo de matéria
            tipo_item = item.get('tipo_item', '')
            des_tipo_materia = item.get('des_tipo_materia', '')
            
            # Se os filtros "apenas como coautor" ou "apenas como 1º autor" estão ativos, excluir emendas e substitutivos
            # pois essas tabelas não têm o campo ind_primeiro_autor para distinguir primeiro autor de coautor
            # EXCETO quando há autor filtrado, pois nesse caso a query SQL já filtrou corretamente
            if (apenas_coautor or apenas_primeiro_autor) and not autor_filtrado:
                if tipo_item in ('emenda', 'substitutivo'):
                    continue  # Pular emendas e substitutivos quando filtros de primeiro autor/coautor estão ativos (sem autor específico)
            
            # Normalizar tipo de matéria para agrupamento
            if tipo_item == 'emenda':
                tipo_normalizado = 'Emenda'
            elif tipo_item == 'substitutivo':
                tipo_normalizado = 'Substitutivo'
            elif tipo_item == 'acessoria_principal':
                tipo_normalizado = 'Acessória'
            else:
                # Para matérias principais, usar a descrição do tipo
                tipo_normalizado = des_tipo_materia if des_tipo_materia else 'Principal'
            
            # Separar autores (podem estar separados por vírgula)
            autores_list = [a.strip() for a in autores_str.split(',') if a.strip()]
            if autores_list:
                    # Se há filtro por autor, verificar se o autor filtrado está na lista (pode ser autor ou coautor)
                    if autor_filtrado:
                        # Normalizar nomes para comparação (case-insensitive, remover espaços extras)
                        autor_filtrado_normalizado = autor_filtrado.strip()
                        autores_list_normalizados = [a.strip() for a in autores_list]
                        
                        # Verificar se o autor filtrado está na lista (comparação case-insensitive e normalizada)
                        # Normalizar removendo espaços extras e convertendo para minúsculas
                        autor_encontrado = None
                        autor_filtrado_normalizado_lower = ' '.join(autor_filtrado_normalizado.split()).lower()
                        
                        for i, autor in enumerate(autores_list_normalizados):
                            autor_normalizado_lower = ' '.join(autor.split()).lower()
                            if autor_normalizado_lower == autor_filtrado_normalizado_lower:
                                autor_encontrado = i
                                break
                        
                        if autor_encontrado is None:
                            # Se não encontrou com comparação exata, tentar comparação parcial (pode haver diferenças de formatação)
                            # Por exemplo: "Paulão" vs "Paulão (Deputado)" ou "Paulão - Deputado"
                            for i, autor in enumerate(autores_list_normalizados):
                                autor_normalizado_lower = ' '.join(autor.split()).lower()
                                # Verificar se o nome do autor filtrado está contido no nome do autor da lista
                                # ou vice-versa (para lidar com formatações diferentes)
                                if (autor_filtrado_normalizado_lower in autor_normalizado_lower or 
                                    autor_normalizado_lower in autor_filtrado_normalizado_lower):
                                    # Verificar se é uma correspondência razoável (não apenas uma palavra comum)
                                    if len(autor_filtrado_normalizado_lower) >= 3:  # Evitar matches muito curtos
                                        autor_encontrado = i
                                        break
                        
                        if autor_encontrado is None:
                            continue  # Autor filtrado não está na lista
                        
                        # IMPORTANTE: Quando há autor filtrado + filtro de coautor/1º autor,
                        # a query SQL já filtrou corretamente (ind_primeiro_autor == 0 ou == 1)
                        # Então todos os resultados já atendem ao filtro.
                        # 
                        # A lista de autores inclui TODOS os autores da matéria (primeiros e coautores),
                        # não apenas os que atendem ao filtro. A lista é ordenada por ind_primeiro_autor.desc(),
                        # então primeiros autores vêm primeiro, mas isso não significa que o autor filtrado
                        # não possa aparecer em outras posições também (se ele for autor de múltiplas matérias).
                        #
                        # Como a query SQL já garantiu o filtro, NÃO precisamos verificar a posição na lista.
                        # A verificação abaixo estava incorreta e estava pulando itens válidos.
                        #
                        # REMOVIDO: Não vamos mais verificar a posição na lista quando há autor filtrado,
                        # porque a query SQL já garantiu que o autor atende ao filtro (coautor ou 1º autor).
                        # A lista de autores pode incluir todos os autores da matéria, então a posição
                        # não é um indicador confiável do filtro aplicado.
                        # Quando há filtro de autor específico, o gráfico por autor deve mostrar APENAS esse autor
                        # (não todos os coautores do item)
                        # Usar o nome exato da lista para manter consistência
                        autor = autores_list[autor_encontrado]
                    else:
                        # Sem filtro de autor específico, mas respeitando as opções do formulário:
                        # - Se "apenas como coautor": considerar apenas coautores (não primeiros autores)
                        # - Se "apenas como 1º autor": considerar apenas primeiros autores
                        # - Se nenhuma opção selecionada: considerar todos os autores (primeiros e coautores)
                        # - Para emendas e substitutivos: considerar apenas o primeiro autor (se não houver filtro específico)
                        
                        if tipo_item in ('emenda', 'substitutivo'):
                            # Para emendas e substitutivos, considerar apenas o primeiro autor
                            autor = autores_list[0]
                        elif apenas_coautor:
                            # Apenas coautores: considerar todos os autores EXCETO o primeiro
                            for autor in autores_list[1:]:  # Pular o primeiro autor
                                if autor not in stats_by_author:
                                    stats_by_author[autor] = {
                                        'total': 0,
                                        'tipos': {}
                                    }
                                stats_by_author[autor]['total'] += 1
                                stats_by_author[autor]['tipos'][tipo_normalizado] = stats_by_author[autor]['tipos'].get(tipo_normalizado, 0) + 1
                            continue  # Já processou todos os coautores, pular para próximo item
                        elif apenas_primeiro_autor:
                            # Apenas primeiros autores: considerar apenas o primeiro autor
                            autor = autores_list[0]
                        else:
                            # Sem filtro: considerar todos os autores (primeiros e coautores)
                            for autor in autores_list:
                                if autor not in stats_by_author:
                                    stats_by_author[autor] = {
                                        'total': 0,
                                        'tipos': {}
                                    }
                                stats_by_author[autor]['total'] += 1
                                stats_by_author[autor]['tipos'][tipo_normalizado] = stats_by_author[autor]['tipos'].get(tipo_normalizado, 0) + 1
                            continue  # Já processou todos os autores, pular para próximo item
                    
                    if autor not in stats_by_author:
                        stats_by_author[autor] = {
                            'total': 0,
                            'tipos': {}
                        }
                    stats_by_author[autor]['total'] += 1
                    stats_by_author[autor]['tipos'][tipo_normalizado] = stats_by_author[autor]['tipos'].get(tipo_normalizado, 0) + 1
        
        # Ordenar por total (decrescente) e depois alfabeticamente
        sorted_authors = sorted(stats_by_author.items(), key=lambda x: (-x[1]['total'], x[0]))
        return dict(sorted_authors)
    
    def _get_autor_name_by_cod(self, cod_autor, session):
        """Busca o nome do autor a partir do cod_autor."""
        if cod_autor is None:
            return None
        try:
            nome_autor_expr = _build_autor_name_expression()
            autor = session.query(Autor.cod_autor, nome_autor_expr.label('nome_autor'))\
                .join(TipoAutor, Autor.tip_autor == TipoAutor.tip_autor)\
                .outerjoin(Parlamentar, Autor.cod_parlamentar == Parlamentar.cod_parlamentar)\
                .outerjoin(Comissao, Autor.cod_comissao == Comissao.cod_comissao)\
                .outerjoin(Bancada, Autor.cod_bancada == Bancada.cod_bancada)\
                .outerjoin(Legislatura, Bancada.num_legislatura == Legislatura.num_legislatura)\
                .filter(Autor.cod_autor == cod_autor, Autor.ind_excluido == 0)\
                .first()
            if autor:
                return autor.nome_autor
            return None
        except Exception:
            return None
    
    def _filter_monosyllabic_words(self, palavras):
        """Filtra palavras monossílabas (stop words) da lista de palavras."""
        # Lista de palavras monossílabas comuns em português (artigos, preposições, pronomes, etc.)
        stop_words_monosyllabic = {
            # Artigos
            'a', 'à', 'ao', 'aos', 'as', 'da', 'das', 'de', 'do', 'dos', 'e', 'em', 'na', 'nas', 'no', 'nos',
            'o', 'os', 'um', 'uma', 'uns', 'umas',
            # Preposições
            'para', 'por', 'com', 'sem', 'sob', 'sobre', 'entre', 'contra', 'até', 'desde', 'perante', 'mediante',
            # Pronomes
            'que', 'se', 'me', 'te', 'nos', 'vos', 'lhe', 'lhes', 'este', 'esta', 'estes', 'estas',
            'esse', 'essa', 'esses', 'essas', 'aquele', 'aquela', 'aqueles', 'aquelas',
            # Conjunções
            'ou', 'mas', 'porém', 'todavia', 'contudo', 'entretanto', 'logo', 'portanto', 'assim', 'então',
            'também', 'tampouco', 'não', 'nem',
            # Advérbios
            'já', 'ainda', 'só', 'sempre', 'nunca', 'jamais', 'agora', 'depois', 'antes', 'hoje', 'ontem',
            'amanhã', 'aqui', 'aí', 'ali', 'lá', 'cá', 'sim', 'não', 'talvez', 'bem', 'mal',
            # Verbos auxiliares comuns (formas monossílabas)
            'é', 'são', 'foi', 'ser', 'ter', 'tem', 'tinha', 'teve', 'há', 'houve', 'era', 'eram', 'foram',
            'está', 'estão', 'estava', 'estavam', 'esteve', 'estiveram'
        }
        
        # Filtrar palavras monossílabas conhecidas e palavras muito curtas (1-2 caracteres)
        palavras_filtradas = []
        for palavra in palavras:
            palavra_lower = palavra.lower()
            # Ignorar palavras muito curtas (1-2 caracteres) ou que estão na lista de stop words
            if len(palavra) <= 2 or palavra_lower in stop_words_monosyllabic:
                continue
            # Verificar se é monossílaba por heurística simples: palavras de 3 caracteres com apenas 1 vogal
            if len(palavra) == 3:
                # Contar vogais
                vogais = sum(1 for c in palavra_lower if c in 'aeiouáéíóúâêîôûàèìòùãõ')
                # Se tem apenas 1 vogal, provavelmente é monossílaba
                if vogais <= 1:
                    continue
            palavras_filtradas.append(palavra)
        
        return palavras_filtradas
    
    def _apply_text_search(self, query):
        termo = self.request.get('des_assunto')
        if not termo:
            return query
        
        
        if self.request.get('chk_textual') == '1':
            try:
                sapl_doc = self.context.restrictedTraverse('sapl_documentos/materia')
                catalog = sapl_doc.Catalog
                from Products.AdvancedQuery import And, Or, Eq, In
                query_parts = [Or(Eq('ementa', termo), Eq('PrincipiaSearchSource', termo))]
                final_query = And(*query_parts) if len(query_parts) > 1 else query_parts[0]
                results = catalog.evalAdvancedQuery(final_query)
                cods = []
                for r in results:
                    item_id_raw = r.id
                    if isinstance(item_id_raw, str):
                        match = re.match(r'^\d+', item_id_raw)
                        if match:
                            cods.append(int(match.group(0)))
                    elif isinstance(item_id_raw, int):
                        cods.append(item_id_raw)
                logger.info(f"Cods da pesquisa textual: {cods}")
                return query.filter(MateriaLegislativa.cod_materia.in_(cods)) if cods else query.filter(expression.false())
            except Exception as e:
                logger.error(f"Erro na busca textual (chk_textual=1): {str(e)}", exc_info=True)
                return query.filter(expression.false())
        else:
            # Abordagem Híbrida: FULLTEXT (prioritário) + LIKE (fallback)
            # Remove caracteres especiais e prepara termos
            termos_limpos = re.sub(r'[^\w\s]', ' ', termo)
            termos_limpos = ' '.join(termos_limpos.split())  # Remove espaços múltiplos
            
            if not termos_limpos:
                return query
            
            palavras = termos_limpos.split()
            # Filtrar palavras monossílabas (stop words) e palavras muito curtas
            palavras = self._filter_monosyllabic_words(palavras)
            if not palavras:
                return query
            
            # ESTRATÉGIA 1: Tentar FULLTEXT primeiro (mais rápido e ordena por relevância)
            try:
                # FULLTEXT em modo BOOLEAN:
                # - Exige que TODAS as palavras estejam presentes (AND)
                # - Permite palavras em qualquer ordem
                # - Usa + antes de cada palavra para exigir presença
                # - Ordena resultados por relevância
                palavras_fulltext = ' '.join([f'+{palavra}' for palavra in palavras])
                fulltext_expr = text(
                    "MATCH(txt_ementa, txt_indexacao, txt_observacao) "
                    "AGAINST(:search_term IN BOOLEAN MODE)"
                ).bindparams(search_term=palavras_fulltext)
                return query.filter(fulltext_expr)
            except Exception as e:
                # ESTRATÉGIA 2: Fallback para LIKE quando FULLTEXT não está disponível
                logger.warning(f"FULLTEXT não disponível, usando LIKE como fallback: {str(e)}")
                return self._apply_like_search_fallback(query, termos_limpos, palavras)
    
    def _apply_like_search_fallback(self, query, termos_limpos, palavras):
        """Fallback usando LIKE quando FULLTEXT não está disponível"""
        # Exige que TODAS as palavras estejam presentes (AND)
        # Permite palavras em qualquer ordem
        
        # Para cada palavra, criar condições que buscam em qualquer campo
        # e combinar com AND para exigir todas as palavras
        condicoes_por_palavra = []
        for palavra in palavras:
            palavra_term = f"%{palavra}%"
            # Cada palavra deve estar em pelo menos um dos campos (OR entre campos)
            condicao_palavra = or_(
                MateriaLegislativa.txt_ementa.ilike(palavra_term),
                MateriaLegislativa.txt_indexacao.ilike(palavra_term),
                MateriaLegislativa.txt_observacao.ilike(palavra_term)
            )
            condicoes_por_palavra.append(condicao_palavra)
        
        # Todas as palavras devem estar presentes (AND entre palavras)
        # Mas cada palavra pode estar em qualquer campo (OR entre campos)
        return query.filter(and_(*condicoes_por_palavra))

    def _apply_author_filter(self, query):
        cod_autor = self._parse_int_param('cod_autor')
        tip_autor = self._parse_int_param('tip_autor')  # NOVO: Tipo de autor
        chk_coautor = self.request.get('chk_coautor') == '1'  # NOVO: Apenas coautor
        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'  # NOVO: Apenas primeiro autor
        
        if cod_autor is not None:
            query = query.join(Autoria, MateriaLegislativa.cod_materia == Autoria.cod_materia)\
                         .join(Autor, Autoria.cod_autor == Autor.cod_autor)\
                         .filter(Autoria.cod_autor == cod_autor, Autoria.ind_excluido == 0, Autor.ind_excluido == 0)
            
            # Filtro de coautor: apenas quando ind_primeiro_autor = 0
            if chk_coautor:
                query = query.filter(Autoria.ind_primeiro_autor == 0)
            # Filtro de primeiro autor: apenas quando ind_primeiro_autor = 1
            elif chk_primeiro_autor:
                query = query.filter(Autoria.ind_primeiro_autor == 1)
        
        # Filtro por tipo de autor (sem autor específico)
        elif tip_autor is not None:
            query = query.join(Autoria, MateriaLegislativa.cod_materia == Autoria.cod_materia)\
                         .join(Autor, Autoria.cod_autor == Autor.cod_autor)\
                         .filter(Autor.tip_autor == tip_autor, Autoria.ind_excluido == 0, Autor.ind_excluido == 0)
        
        return query

    def _apply_rapporteur_filter(self, query):
        cod_relator = self._parse_int_param('cod_relator')
        if cod_relator is not None:
            query = query.join(Relatoria, MateriaLegislativa.cod_materia == Relatoria.cod_materia)\
                         .filter(Relatoria.cod_parlamentar == cod_relator, Relatoria.ind_excluido == 0)
        return query
    
    def _apply_tramitacao_filters(self, query, session):
        cod_status = self._parse_int_param('cod_status')
        cod_unid_atual = self._parse_int_param('cod_unid_tramitacao')
        cod_unid_passou = self._parse_int_param('cod_unid_tramitacao2')

        # --- INÍCIO DA OTIMIZAÇÃO ---
        # Filtro por localização atual (unidade e/ou status)
        if cod_status or cod_unid_atual:
            # Subconsulta para ranquear as tramitações de cada matéria,
            # com a mais recente (maior data e maior código) em primeiro lugar (rn=1).
            # Esta abordagem usa a window function ROW_NUMBER() que é altamente otimizada
            # para este tipo de tarefa e usa o índice idx_tram_ultima perfeitamente.
            subq = session.query(
                Tramitacao.cod_materia,
                Tramitacao.cod_status,
                Tramitacao.cod_unid_tram_dest,
                func.row_number().over(
                    partition_by=Tramitacao.cod_materia,
                    order_by=[desc(Tramitacao.dat_tramitacao), desc(Tramitacao.cod_tramitacao)]
                ).label('rn')
            ).filter(Tramitacao.ind_excluido == 0).subquery('ranked_tramitacoes')

            # Alias para a subconsulta, permitindo que filtremos seus resultados
            ranked_alias = aliased(subq)

            # Começamos a construir a consulta final que selecionará apenas
            # as matérias cuja última tramitação (rn=1) atende aos critérios.
            materias_filtradas_query = session.query(ranked_alias.c.cod_materia).filter(ranked_alias.c.rn == 1)

            # Aplicamos os filtros de status e/ou unidade de destino.
            if cod_status:
                materias_filtradas_query = materias_filtradas_query.filter(ranked_alias.c.cod_status == cod_status)
            if cod_unid_atual:
                materias_filtradas_query = materias_filtradas_query.filter(ranked_alias.c.cod_unid_tram_dest == cod_unid_atual)
            
            # A consulta principal é filtrada para incluir apenas as matérias
            # que estão na lista de códigos retornada pela consulta otimizada.
            query = query.filter(MateriaLegislativa.cod_materia.in_(materias_filtradas_query))
        # --- FIM DA OTIMIZAÇÃO ---

        # Filtro por unidade onde a matéria já passou (lógica mantida)
        if cod_unid_passou:
            tramitou_em = session.query(Tramitacao.cod_materia).filter(
                Tramitacao.cod_unid_tram_dest == cod_unid_passou,
                Tramitacao.ind_excluido == 0
            ).distinct()
            query = query.filter(MateriaLegislativa.cod_materia.in_(tramitou_em))

        return query

    def _apply_filters_to_acessoria_query(self, query, session):
        """Aplica filtros comuns à query de matérias acessórias principais."""
        # Filtro por número
        if (val := self._parse_int_param('num_ident_basica')) is not None:
            query = query.filter(MateriaLegislativa.num_ident_basica == val)
        # Filtro por ano
        if (val := self._parse_int_param('ano_ident_basica')) is not None:
            query = query.filter(MateriaLegislativa.ano_ident_basica == val)
        # Filtro por protocolo
        if (val := self._parse_int_param('num_protocolo')) is not None:
            query = query.filter(MateriaLegislativa.num_protocolo == val)
        # Filtro por tipo
        if (tipos := self._parse_int_list_param('tip_id_basica')):
            query = query.filter(MateriaLegislativa.tip_id_basica.in_(tipos))
        # Filtro por data
        dat1 = self._parse_date_param('dat_apresentacao')
        dat2 = self._parse_date_param('dat_apresentacao2')
        if dat1 and dat2:
            query = query.filter(MateriaLegislativa.dat_apresentacao.between(dat1, dat2))
        elif dat1:
            query = query.filter(MateriaLegislativa.dat_apresentacao >= dat1)
        elif dat2:
            query = query.filter(MateriaLegislativa.dat_apresentacao <= dat2)
        # Filtro por texto
        termo = self.request.get('des_assunto')
        if termo:
            termos_limpos = re.sub(r'[^\w\s]', ' ', termo)
            termos_limpos = ' '.join(termos_limpos.split())
            if termos_limpos:
                palavras = [p for p in termos_limpos.split() if len(p) >= 2]
                if palavras:
                    try:
                        palavras_fulltext = ' '.join([f'+{palavra}' for palavra in palavras])
                        fulltext_expr = text(
                            "MATCH(txt_ementa, txt_indexacao, txt_observacao) "
                            "AGAINST(:search_term IN BOOLEAN MODE)"
                        ).bindparams(search_term=palavras_fulltext)
                        query = query.filter(fulltext_expr)
                    except Exception:
                        palavra_term = f"%{termos_limpos}%"
                        query = query.filter(
                            or_(
                                MateriaLegislativa.txt_ementa.ilike(palavra_term),
                                MateriaLegislativa.txt_indexacao.ilike(palavra_term),
                                MateriaLegislativa.txt_observacao.ilike(palavra_term)
                            )
                        )
        # Filtro por autoria (via subquery)
        cod_autor = self._parse_int_param('cod_autor')
        chk_coautor = self.request.get('chk_coautor') == '1'
        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
        if cod_autor is not None:
            autoria_subq = session.query(Autoria.cod_materia).filter(
                Autoria.cod_autor == cod_autor,
                Autoria.ind_excluido == 0
            )
            # Filtro de coautor: apenas quando ind_primeiro_autor = 0
            if chk_coautor:
                autoria_subq = autoria_subq.filter(Autoria.ind_primeiro_autor == 0)
            # Filtro de primeiro autor: apenas quando ind_primeiro_autor = 1
            elif chk_primeiro_autor:
                autoria_subq = autoria_subq.filter(Autoria.ind_primeiro_autor == 1)
            autoria_subq = autoria_subq.distinct()
            query = query.filter(MateriaLegislativa.cod_materia.in_(autoria_subq))
        # Filtro por tramitação
        if (val := self.request.get('ind_tramitacao')) and val.isdigit():
            query = query.filter(MateriaLegislativa.ind_tramitacao == int(val))
        # Filtro por matéria principal (não se aplica a matérias acessórias principais)
        return query

    def _apply_filters_to_emenda_query(self, query, session):
        """Aplica filtros à query de emendas.
        Aplica apenas filtros básicos e data de apresentação (filtro avançado permitido).
        Filtros avançados são aplicados somente a matérias principais.
        """
        # Filtro por número de emenda (básico)
        if (val := self._parse_int_param('num_ident_basica')) is not None:
            query = query.filter(Emenda.num_emenda == val)
        # Filtro por ano (da data de apresentação) (básico)
        if (val := self._parse_int_param('ano_ident_basica')) is not None:
            query = query.filter(func.year(Emenda.dat_apresentacao) == val)
        # Filtro por data de apresentação (avançado, mas permitido para emendas)
        dat1 = self._parse_date_param('dat_apresentacao')
        dat2 = self._parse_date_param('dat_apresentacao2')
        if dat1 and dat2:
            query = query.filter(Emenda.dat_apresentacao.between(dat1, dat2))
        elif dat1:
            query = query.filter(Emenda.dat_apresentacao >= dat1)
        elif dat2:
            query = query.filter(Emenda.dat_apresentacao <= dat2)
        # Filtro por texto (básico)
        termo = self.request.get('des_assunto')
        if termo:
            termos_limpos = re.sub(r'[^\w\s]', ' ', termo)
            termos_limpos = ' '.join(termos_limpos.split())
            if termos_limpos:
                palavra_term = f"%{termos_limpos}%"
                query = query.filter(Emenda.txt_ementa.ilike(palavra_term))
        # Filtro por autor (básico) - usar AutoriaEmenda
        cod_autor = self._parse_int_param('cod_autor')
        chk_coautor = self.request.get('chk_coautor') == '1'
        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
        if cod_autor is not None:
            # NOTA: AutoriaEmenda não tem campo ind_primeiro_autor, então os filtros "apenas como coautor"
            # e "apenas como 1º autor" não se aplicam a emendas. Se algum filtro estiver ativo, não retornar emendas.
            if chk_coautor or chk_primeiro_autor:
                # Quando filtros de primeiro autor/coautor estão ativos, não incluir emendas
                # pois não há como distinguir primeiro autor de coautor em emendas
                query = query.filter(False)  # Retorna vazio
            else:
                autoria_subq = session.query(AutoriaEmenda.cod_emenda).filter(
                    AutoriaEmenda.cod_autor == cod_autor,
                    AutoriaEmenda.ind_excluido == 0
                ).distinct()
                query = query.filter(Emenda.cod_emenda.in_(autoria_subq))
        # Filtro por matéria principal (básico, necessário para relacionar)
        cod_materia_principal = self._parse_int_param('cod_materia')
        if cod_materia_principal is not None:
            query = query.filter(Emenda.cod_materia == cod_materia_principal)
        else:
            # Tentar buscar matéria principal por tipo, número e ano
            # Verificar se tip_id_basica contém apenas IDs numéricos (não EMENDA/SUBSTITUTIVO)
            tipos_selecionados = self._parse_list_param('tip_id_basica')
            tipos_numericos = [int(t) for t in tipos_selecionados if t and t.isdigit()] if tipos_selecionados else []
            
            # Só aplicar filtro de matéria principal se houver tipos numéricos selecionados
            # e não houver EMENDA/SUBSTITUTIVO na seleção
            if tipos_numericos and 'EMENDA' not in (tipos_selecionados or []) and 'SUBSTITUTIVO' not in (tipos_selecionados or []):
                num_materia = self._parse_int_param('num_ident_basica')
                ano_materia = self._parse_int_param('ano_ident_basica')
                if len(tipos_numericos) == 1 and num_materia and ano_materia:
                    materia_subq = session.query(MateriaLegislativa.cod_materia).filter(
                        MateriaLegislativa.tip_id_basica == tipos_numericos[0],
                        MateriaLegislativa.num_ident_basica == num_materia,
                        MateriaLegislativa.ano_ident_basica == ano_materia,
                        MateriaLegislativa.ind_excluido == 0
                    )
                    query = query.filter(Emenda.cod_materia.in_(materia_subq))
        # NOTA: Filtros avançados (num_protocolo, cod_autor, ind_tramitacao, etc.) 
        # são aplicados somente a matérias principais, não a emendas
        return query

    def _apply_filters_to_substitutivo_query(self, query, session):
        """Aplica filtros à query de substitutivos.
        Aplica apenas filtros básicos e data de apresentação (filtro avançado permitido).
        Filtros avançados são aplicados somente a matérias principais.
        """
        # Filtro por número de substitutivo (básico)
        if (val := self._parse_int_param('num_ident_basica')) is not None:
            query = query.filter(Substitutivo.num_substitutivo == val)
        # Filtro por ano (da data de apresentação) (básico)
        if (val := self._parse_int_param('ano_ident_basica')) is not None:
            query = query.filter(func.year(Substitutivo.dat_apresentacao) == val)
        # Filtro por data de apresentação (avançado, mas permitido para substitutivos)
        dat1 = self._parse_date_param('dat_apresentacao')
        dat2 = self._parse_date_param('dat_apresentacao2')
        if dat1 and dat2:
            query = query.filter(Substitutivo.dat_apresentacao.between(dat1, dat2))
        elif dat1:
            query = query.filter(Substitutivo.dat_apresentacao >= dat1)
        elif dat2:
            query = query.filter(Substitutivo.dat_apresentacao <= dat2)
        # Filtro por texto (básico)
        termo = self.request.get('des_assunto')
        if termo:
            termos_limpos = re.sub(r'[^\w\s]', ' ', termo)
            termos_limpos = ' '.join(termos_limpos.split())
            if termos_limpos:
                palavra_term = f"%{termos_limpos}%"
                query = query.filter(Substitutivo.txt_ementa.ilike(palavra_term))
        # Filtro por autor (básico) - usar AutoriaSubstitutivo
        cod_autor = self._parse_int_param('cod_autor')
        chk_coautor = self.request.get('chk_coautor') == '1'
        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
        if cod_autor is not None:
            # NOTA: AutoriaSubstitutivo não tem campo ind_primeiro_autor, então os filtros "apenas como coautor"
            # e "apenas como 1º autor" não se aplicam a substitutivos. Se algum filtro estiver ativo, não retornar substitutivos.
            if chk_coautor or chk_primeiro_autor:
                # Quando filtros de primeiro autor/coautor estão ativos, não incluir substitutivos
                # pois não há como distinguir primeiro autor de coautor em substitutivos
                query = query.filter(False)  # Retorna vazio
            else:
                autoria_subq = session.query(AutoriaSubstitutivo.cod_substitutivo).filter(
                    AutoriaSubstitutivo.cod_autor == cod_autor,
                    AutoriaSubstitutivo.ind_excluido == 0
                ).distinct()
                query = query.filter(Substitutivo.cod_substitutivo.in_(autoria_subq))
        # Filtro por matéria principal (básico, necessário para relacionar)
        cod_materia_principal = self._parse_int_param('cod_materia')
        if cod_materia_principal is not None:
            query = query.filter(Substitutivo.cod_materia == cod_materia_principal)
        else:
            # Tentar buscar matéria principal por tipo, número e ano
            # Verificar se tip_id_basica contém apenas IDs numéricos (não EMENDA/SUBSTITUTIVO)
            tipos_selecionados = self._parse_list_param('tip_id_basica')
            tipos_numericos = [int(t) for t in tipos_selecionados if t and t.isdigit()] if tipos_selecionados else []
            
            # Só aplicar filtro de matéria principal se houver tipos numéricos selecionados
            # e não houver EMENDA/SUBSTITUTIVO na seleção
            if tipos_numericos and 'EMENDA' not in (tipos_selecionados or []) and 'SUBSTITUTIVO' not in (tipos_selecionados or []):
                num_materia = self._parse_int_param('num_ident_basica')
                ano_materia = self._parse_int_param('ano_ident_basica')
                if len(tipos_numericos) == 1 and num_materia and ano_materia:
                    materia_subq = session.query(MateriaLegislativa.cod_materia).filter(
                        MateriaLegislativa.tip_id_basica == tipos_numericos[0],
                        MateriaLegislativa.num_ident_basica == num_materia,
                        MateriaLegislativa.ano_ident_basica == ano_materia,
                        MateriaLegislativa.ind_excluido == 0
                    )
                    query = query.filter(Substitutivo.cod_materia.in_(materia_subq))
        # NOTA: Filtros avançados (num_protocolo, cod_autor, ind_tramitacao, etc.) 
        # são aplicados somente a matérias principais, não a substitutivos
        return query

    def _build_unified_acessoria_query(self, session):
        """Constrói query unificada para matérias acessórias (acessórias principais + emendas + substitutivos)."""
        # Construir as três subqueries
        query_acessoria = self._build_acessoria_principal_query(session)
        query_emenda = self._build_emenda_query(session)
        query_substitutivo = self._build_substitutivo_query(session)
        
        # Aplicar filtros em cada subquery
        query_acessoria = self._apply_filters_to_acessoria_query(query_acessoria, session)
        query_emenda = self._apply_filters_to_emenda_query(query_emenda, session)
        query_substitutivo = self._apply_filters_to_substitutivo_query(query_substitutivo, session)
        
        # Fazer UNION ALL das três queries
        query_unificada = union_all(
            query_acessoria,
            query_emenda,
            query_substitutivo
        ).alias('materias_unificadas')
        
        # Criar query final a partir do alias, selecionando todas as colunas explicitamente
        unified_query = session.query(
            query_unificada.c.cod_item,
            query_unificada.c.tipo_item,
            query_unificada.c.cod_materia_principal,
            query_unificada.c.des_tipo_materia,
            query_unificada.c.num_ident_basica,
            query_unificada.c.ano_ident_basica,
            query_unificada.c.txt_ementa,
            query_unificada.c.dat_apresentacao,
            query_unificada.c.num_protocolo,
            query_unificada.c.cod_materia,
            query_unificada.c.sgl_tipo_materia,
            query_unificada.c.cod_emenda,
            query_unificada.c.cod_substitutivo,
            query_unificada.c.tip_emenda,
            query_unificada.c.des_tipo_emenda,
            query_unificada.c.num_emenda,
            query_unificada.c.num_substitutivo
        )
        
        # Aplicar ordenação básica (por data de apresentação)
        ordem = self.request.get('rd_ordem', '1')
        if ordem == '0':
            unified_query = unified_query.order_by(asc(query_unificada.c.dat_apresentacao))
        else:
            unified_query = unified_query.order_by(desc(query_unificada.c.dat_apresentacao))
        
        return unified_query

    def _format_unified_results(self, results_raw, session):
        """Formata resultados da query unificada de matérias acessórias."""
        if not results_raw:
            return []
        
        start_time = time.time()
        formatted = []
        portal_url = getToolByName(self.context, 'portal_url')()
        mtool = getToolByName(self.context, 'portal_membership')
        is_operador = False
        if not mtool.isAnonymousUser():
            member = mtool.getAuthenticatedMember()
            if member:
                is_operador = member.has_role(['Operador', 'Operador Materia'])
        
        # Separar IDs de matérias principais e IDs de matérias principais relacionadas (para emendas/substitutivos)
        cod_materias_principais_unificadas = []  # Matérias principais que aparecem na query unificada
        cod_materias_principais_relacionadas = []  # Matérias principais relacionadas a emendas/substitutivos
        
        for r in results_raw:
            try:
                tipo_item = getattr(r, 'tipo_item', None)
                cod_item = getattr(r, 'cod_item', None)
                cod_materia_principal = getattr(r, 'cod_materia_principal', None)
                if tipo_item == 'principal' and cod_item:
                    cod_materias_principais_unificadas.append(cod_item)
                elif tipo_item in ('emenda', 'substitutivo') and cod_materia_principal:
                    cod_materias_principais_relacionadas.append(cod_materia_principal)
            except (AttributeError, IndexError):
                # Fallback: tentar acesso por índice se getattr falhar
                try:
                    tipo_item = r[1] if len(r) > 1 else None
                    cod_item = r[0] if len(r) > 0 else None
                    cod_materia_principal = r[2] if len(r) > 2 else None
                    if tipo_item == 'principal' and cod_item:
                        cod_materias_principais_unificadas.append(cod_item)
                    elif tipo_item in ('emenda', 'substitutivo') and cod_materia_principal:
                        cod_materias_principais_relacionadas.append(cod_materia_principal)
                except (IndexError, TypeError):
                    continue
        
        cod_materias_principais_unificadas = list(set(cod_materias_principais_unificadas))
        cod_materias_principais_relacionadas = list(set(cod_materias_principais_relacionadas))
        
        # Buscar todas as informações adicionais para matérias principais (igual a _format_results)
        materia_ids = cod_materias_principais_unificadas
        docs_folder = self.context.sapl_documentos.materia
        
        # Dicionários para armazenar informações agregadas (inicializados vazios se não houver matérias principais)
        subst_dict = {}
        emenda_dict = {}
        anexadas_dict = {}
        anexadora_dict = {}
        doc_acessorio_dict = {}
        parecer_dict = {}
        regime_dict = {}
        tramitacao_dict = {}
        norma_dict = {}
        materia_info_dict = {}  # Otimização: buscar ind_tramitacao e cod_regime_tramitacao em batch
        
        if materia_ids:
            try:
                # Contagem de substitutivos
                subst_counts = session.query(
                    Substitutivo.cod_materia,
                    func.count(Substitutivo.cod_substitutivo).label('qtd')
                ).filter(
                    Substitutivo.cod_materia.in_(materia_ids),
                    Substitutivo.ind_excluido == 0
                ).group_by(Substitutivo.cod_materia).all()
                subst_dict = {m_id: qtd for m_id, qtd in subst_counts}
                
                # Contagem de emendas
                emenda_counts = session.query(
                    Emenda.cod_materia,
                    func.count(Emenda.cod_emenda).label('qtd')
                ).filter(
                    Emenda.cod_materia.in_(materia_ids),
                    Emenda.ind_excluido == 0
                ).group_by(Emenda.cod_materia).all()
                emenda_dict = {m_id: qtd for m_id, qtd in emenda_counts}
                
                # Informações de anexadas (matérias anexadas a esta)
                Anexada_anex = aliased(Anexada, name='anexada_anex')
                MateriaLegislativa_anex = aliased(MateriaLegislativa, name='materia_anex')
                TipoMateriaLegislativa_anex = aliased(TipoMateriaLegislativa, name='tipo_anex')
                anexadas_info = session.query(
                    Anexada_anex.cod_materia_principal,
                    MateriaLegislativa_anex.cod_materia,
                    TipoMateriaLegislativa_anex.sgl_tipo_materia,
                    MateriaLegislativa_anex.num_ident_basica,
                    MateriaLegislativa_anex.ano_ident_basica
                ).join(
                    MateriaLegislativa_anex, Anexada_anex.cod_materia_anexada == MateriaLegislativa_anex.cod_materia
                ).join(
                    TipoMateriaLegislativa_anex, MateriaLegislativa_anex.tip_id_basica == TipoMateriaLegislativa_anex.tip_materia
                ).filter(
                    Anexada_anex.cod_materia_principal.in_(materia_ids),
                    Anexada_anex.ind_excluido == 0,
                    MateriaLegislativa_anex.ind_excluido == 0
                ).order_by(
                    Anexada_anex.cod_materia_principal,
                    MateriaLegislativa_anex.ano_ident_basica.desc(),
                    MateriaLegislativa_anex.num_ident_basica
                ).all()
                
                anexadas_dict = {}
                for m_id, cod_materia_anex, sgl_tipo, num, ano in anexadas_info:
                    if m_id not in anexadas_dict:
                        anexadas_dict[m_id] = []
                    identificacao = f"{sgl_tipo or ''} {num}/{ano}".strip()
                    anexadas_dict[m_id].append({
                        'cod_materia': cod_materia_anex,
                        'identificacao': identificacao
                    })
                
                # Contagem de anexadoras
                anexadora_counts = session.query(
                    Anexada.cod_materia_anexada,
                    func.count(Anexada.cod_materia_principal).label('qtd')
                ).filter(
                    Anexada.cod_materia_anexada.in_(materia_ids),
                    Anexada.ind_excluido == 0
                ).group_by(Anexada.cod_materia_anexada).all()
                anexadora_dict = {m_id: qtd for m_id, qtd in anexadora_counts}
                
                # Contagem de documentos acessórios
                doc_acessorio_counts = session.query(
                    DocumentoAcessorio.cod_materia,
                    func.count(DocumentoAcessorio.cod_documento).label('qtd')
                ).filter(
                    DocumentoAcessorio.cod_materia.in_(materia_ids),
                    DocumentoAcessorio.ind_excluido == 0
                ).group_by(DocumentoAcessorio.cod_materia).all()
                doc_acessorio_dict = {m_id: qtd for m_id, qtd in doc_acessorio_counts}
                
                # Contagem de pareceres
                parecer_counts = session.query(
                    Relatoria.cod_materia,
                    func.count(Relatoria.cod_relatoria).label('qtd')
                ).filter(
                    Relatoria.cod_materia.in_(materia_ids),
                    Relatoria.ind_excluido == 0,
                    Relatoria.num_parecer.isnot(None)
                ).group_by(Relatoria.cod_materia).all()
                parecer_dict = {m_id: qtd for m_id, qtd in parecer_counts}
                
                # Regime de tramitação
                regimes = session.query(RegimeTramitacao).filter(
                    RegimeTramitacao.ind_excluido == 0
                ).all()
                regime_dict = {r.cod_regime_tramitacao: {'des': r.des_regime_tramitacao} 
                              for r in regimes}
                
                # Última tramitação
                Tramitacao_ult = aliased(Tramitacao, name='tramitacao_ult')
                StatusTram_ult = aliased(StatusTramitacao, name='status_tram_ult')
                UnidadeTram_ult = aliased(UnidadeTramitacao, name='unidade_tram_ult')
                Comissao_ult = aliased(Comissao, name='comissao_ult')
                Orgao_ult = aliased(Orgao, name='orgao_ult')
                Parlamentar_ult = aliased(Parlamentar, name='parlamentar_ult')
                
                nome_unidade_expr = case(
                    (UnidadeTram_ult.cod_comissao != None, Comissao_ult.nom_comissao),
                    (UnidadeTram_ult.cod_orgao != None, Orgao_ult.nom_orgao),
                    (UnidadeTram_ult.cod_parlamentar != None, Parlamentar_ult.nom_parlamentar),
                    else_=cast(None, String)
                ).label('nom_unidade')
                
                tramitacoes_ult = session.query(
                    Tramitacao_ult.cod_materia,
                    StatusTram_ult.des_status,
                    nome_unidade_expr,
                    Tramitacao_ult.dat_tramitacao,
                    Tramitacao_ult.dat_fim_prazo
                ).outerjoin(
                    StatusTram_ult, Tramitacao_ult.cod_status == StatusTram_ult.cod_status
                ).outerjoin(
                    UnidadeTram_ult, Tramitacao_ult.cod_unid_tram_dest == UnidadeTram_ult.cod_unid_tramitacao
                ).outerjoin(
                    Comissao_ult, UnidadeTram_ult.cod_comissao == Comissao_ult.cod_comissao
                ).outerjoin(
                    Orgao_ult, UnidadeTram_ult.cod_orgao == Orgao_ult.cod_orgao
                ).outerjoin(
                    Parlamentar_ult, UnidadeTram_ult.cod_parlamentar == Parlamentar_ult.cod_parlamentar
                ).filter(
                    Tramitacao_ult.cod_materia.in_(materia_ids),
                    Tramitacao_ult.ind_excluido == 0,
                    Tramitacao_ult.ind_ult_tramitacao == 1
                ).order_by(
                    Tramitacao_ult.cod_materia,
                    desc(Tramitacao_ult.dat_tramitacao),
                    desc(Tramitacao_ult.cod_tramitacao)
                ).all()
                
                tramitacao_dict = {}
                for cod_materia, des_status, nom_unidade, dat_tramitacao, dat_fim_prazo in tramitacoes_ult:
                    # Se já existe uma tramitação para esta matéria, manter apenas a primeira (mais recente)
                    if cod_materia not in tramitacao_dict:
                        tramitacao_dict[cod_materia] = {
                            'des_status': des_status or '',
                            'nom_unidade': nom_unidade or '',
                            'dat_tramitacao': dat_tramitacao.strftime('%d/%m/%Y %H:%M:%S') if dat_tramitacao else '',
                            'dat_fim_prazo': dat_fim_prazo.strftime('%d/%m/%Y') if dat_fim_prazo else ''
                        }
                
                # Normas derivadas
                TipoNormaJuridica_norma = aliased(TipoNormaJuridica, name='tipo_norma_norma')
                normas_derivadas = session.query(
                    NormaJuridica.cod_materia,
                    TipoNormaJuridica_norma.sgl_tipo_norma,
                    NormaJuridica.num_norma,
                    NormaJuridica.ano_norma,
                    NormaJuridica.cod_norma
                ).join(
                    TipoNormaJuridica_norma, NormaJuridica.tip_norma == TipoNormaJuridica_norma.tip_norma
                ).filter(
                    NormaJuridica.cod_materia.in_(materia_ids),
                    NormaJuridica.ind_excluido == 0
                ).all()
                
                for m_id, sgl_tipo, num, ano, cod_norma in normas_derivadas:
                    if m_id not in norma_dict:
                        norma_dict[m_id] = {
                            'sgl_tipo_norma': sgl_tipo,
                            'num_norma': num,
                            'ano_norma': ano,
                            'cod_norma': cod_norma
                        }
                
                # Otimização: buscar ind_tramitacao e cod_regime_tramitacao em batch
                # em vez de uma query por matéria
                materias_info = session.query(
                    MateriaLegislativa.cod_materia,
                    MateriaLegislativa.ind_tramitacao,
                    MateriaLegislativa.cod_regime_tramitacao
                ).filter(
                    MateriaLegislativa.cod_materia.in_(materia_ids)
                ).all()
                
                for m_id, ind_tram, cod_regime in materias_info:
                    materia_info_dict[m_id] = {
                        'ind_tramitacao': ind_tram,
                        'cod_regime_tramitacao': cod_regime
                    }
            except Exception as e:
                # Em caso de erro, continuar com dicionários vazios
                logger.error(f"Erro ao buscar informações agregadas: {e}")
                pass
        
        # Buscar informações das matérias principais relacionadas (para emendas e substitutivos)
        cod_materias_principais = cod_materias_principais_relacionadas
        
        materias_principais_dict = {}
        if cod_materias_principais:
            materias_principais = session.query(
                MateriaLegislativa.cod_materia,
                TipoMateriaLegislativa.des_tipo_materia,
                TipoMateriaLegislativa.sgl_tipo_materia,
                MateriaLegislativa.num_ident_basica,
                MateriaLegislativa.ano_ident_basica
            ).join(
                TipoMateriaLegislativa,
                MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
            ).filter(
                MateriaLegislativa.cod_materia.in_(cod_materias_principais),
                MateriaLegislativa.ind_excluido == 0
            ).all()
            
            for mat in materias_principais:
                identificacao_principal = f"{mat.sgl_tipo_materia or ''} {mat.num_ident_basica}/{mat.ano_ident_basica}".strip()
                materias_principais_dict[mat.cod_materia] = {
                    'des_tipo_materia': mat.des_tipo_materia,
                    'sgl_tipo_materia': mat.sgl_tipo_materia or '',
                    'num_ident_basica': mat.num_ident_basica,
                    'ano_ident_basica': mat.ano_ident_basica,
                    'identificacao': identificacao_principal,
                    'url': f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/materia/materia_mostrar_proc?cod_materia={mat.cod_materia}"
                }
        
        for r in results_raw:
            # Acessar colunas usando getattr (literal_column com label cria atributos acessíveis)
            try:
                tipo_item = getattr(r, 'tipo_item', None)
                cod_item = getattr(r, 'cod_item', None)
                cod_materia_principal = getattr(r, 'cod_materia_principal', None)
                des_tipo_materia = getattr(r, 'des_tipo_materia', None)
                num_ident_basica = getattr(r, 'num_ident_basica', None)
                ano_ident_basica = getattr(r, 'ano_ident_basica', None)
                txt_ementa = getattr(r, 'txt_ementa', None)
                dat_apresentacao = getattr(r, 'dat_apresentacao', None)
                num_protocolo = getattr(r, 'num_protocolo', None)
                cod_materia = getattr(r, 'cod_materia', None)
                sgl_tipo_materia = getattr(r, 'sgl_tipo_materia', None)
                cod_emenda = getattr(r, 'cod_emenda', None)
                cod_substitutivo = getattr(r, 'cod_substitutivo', None)
                tip_emenda = getattr(r, 'tip_emenda', None)
                des_tipo_emenda = getattr(r, 'des_tipo_emenda', None)
                num_emenda = getattr(r, 'num_emenda', None)
                num_substitutivo = getattr(r, 'num_substitutivo', None)
            except (AttributeError, IndexError):
                # Fallback: tentar acesso por índice se getattr falhar
                try:
                    tipo_item = r[1] if len(r) > 1 else None
                    cod_item = r[0] if len(r) > 0 else None
                    cod_materia_principal = r[2] if len(r) > 2 else None
                    des_tipo_materia = r[3] if len(r) > 3 else None
                    num_ident_basica = r[4] if len(r) > 4 else None
                    ano_ident_basica = r[5] if len(r) > 5 else None
                    txt_ementa = r[6] if len(r) > 6 else None
                    dat_apresentacao = r[7] if len(r) > 7 else None
                    num_protocolo = r[8] if len(r) > 8 else None
                    cod_materia = r[9] if len(r) > 9 else None
                    sgl_tipo_materia = r[10] if len(r) > 10 else None
                    cod_emenda = r[11] if len(r) > 11 else None
                    cod_substitutivo = r[12] if len(r) > 12 else None
                    tip_emenda = r[13] if len(r) > 13 else None
                    des_tipo_emenda = r[14] if len(r) > 14 else None
                    num_emenda = r[15] if len(r) > 15 else None
                    num_substitutivo = r[16] if len(r) > 16 else None
                except (IndexError, TypeError):
                    continue
            
            # Construir identificação baseada no tipo
            if tipo_item == 'principal' or tipo_item == 'acessoria_principal':
                # Para matérias principais, usar des_tipo_materia no formato "Requerimento n° 491/2025"
                identificacao = f"{des_tipo_materia or ''} n° {num_ident_basica}/{ano_ident_basica}".strip()
                detail_url = f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/materia/materia_mostrar_proc?cod_materia={cod_item}"
            elif tipo_item == 'emenda':
                tipo_emenda_str = f"{des_tipo_emenda or ''} " if des_tipo_emenda else ""
                # Buscar identificação da matéria principal
                materia_principal_info = materias_principais_dict.get(cod_materia_principal) if cod_materia_principal else None
                if materia_principal_info:
                    identificacao_principal = materia_principal_info.get('identificacao', f"{materia_principal_info.get('sgl_tipo_materia', '')} {materia_principal_info.get('num_ident_basica', '')}/{materia_principal_info.get('ano_ident_basica', '')}".strip())
                    identificacao = f"Emenda {tipo_emenda_str}nº {num_emenda} ao {identificacao_principal}".strip()
                else:
                    identificacao = f"Emenda {tipo_emenda_str}nº {num_emenda}".strip()
                detail_url = f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/materia/materia_mostrar_proc?cod_materia={cod_materia_principal}#emenda"
            elif tipo_item == 'substitutivo':
                # Buscar identificação da matéria principal
                materia_principal_info = materias_principais_dict.get(cod_materia_principal) if cod_materia_principal else None
                if materia_principal_info:
                    identificacao_principal = materia_principal_info.get('identificacao', f"{materia_principal_info.get('sgl_tipo_materia', '')} {materia_principal_info.get('num_ident_basica', '')}/{materia_principal_info.get('ano_ident_basica', '')}".strip())
                    identificacao = f"Substitutivo nº {num_substitutivo} ao {identificacao_principal}".strip()
                else:
                    identificacao = f"Substitutivo nº {num_substitutivo}"
                detail_url = f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/materia/materia_mostrar_proc?cod_materia={cod_materia_principal}#substitutivo"
            else:
                identificacao = ""
                detail_url = ""
            
            item = {
                'cod_materia': cod_materia if tipo_item in ('principal', 'acessoria_principal') else cod_materia_principal,
                'cod_item': cod_item,
                'tipo_item': tipo_item,
                'des_tipo_materia': des_tipo_materia,
                'sgl_tipo_materia': sgl_tipo_materia or '',
                'num_ident_basica': num_ident_basica,
                'ano_ident_basica': ano_ident_basica if ano_ident_basica else (dat_apresentacao.year if dat_apresentacao else None),
                'txt_ementa': txt_ementa or '',
                'dat_apresentacao': dat_apresentacao.strftime('%d/%m/%Y') if dat_apresentacao else '',
                'num_protocolo': num_protocolo,
                'identificacao': identificacao,
                'autores': '',
                'detail_url': detail_url,
                'url_texto_integral': None,
                'url_redacao_final': None,
                'url_pasta_digital': None,
                'materia_principal': materias_principais_dict.get(cod_materia_principal) if tipo_item in ('emenda', 'substitutivo') else None,
                # Campos específicos
                'cod_emenda': cod_emenda if tipo_item == 'emenda' else None,
                'cod_substitutivo': cod_substitutivo if tipo_item == 'substitutivo' else None,
                'num_emenda': num_emenda if tipo_item == 'emenda' else None,
                'num_substitutivo': num_substitutivo if tipo_item == 'substitutivo' else None,
                'des_tipo_emenda': des_tipo_emenda if tipo_item == 'emenda' else None,
            }
            
            # Para matérias principais, adicionar todas as informações adicionais (igual a _format_results)
            if tipo_item == 'principal':
                # Otimização: usar dicionário em vez de query individual por matéria
                materia_info = materia_info_dict.get(cod_item, {})
                item['ind_tramitacao'] = materia_info.get('ind_tramitacao')
                item['cod_regime_tramitacao'] = materia_info.get('cod_regime_tramitacao')
                
                # Adicionar informações agregadas
                item['qtd_substitutivos'] = subst_dict.get(cod_item, 0)
                item['qtd_emendas'] = emenda_dict.get(cod_item, 0)
                item['qtd_anexadas'] = len(anexadas_dict.get(cod_item, []))
                item['anexadas'] = [
                    {
                        'identificacao': a['identificacao'],
                        'url': f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/materia/materia_mostrar_proc?cod_materia={a['cod_materia']}"
                    }
                    for a in anexadas_dict.get(cod_item, [])
                ]
                item['qtd_anexadoras'] = anexadora_dict.get(cod_item, 0)
                item['qtd_documentos_acessorios'] = doc_acessorio_dict.get(cod_item, 0)
                item['qtd_pareceres'] = parecer_dict.get(cod_item, 0)
                item['des_regime_tramitacao'] = regime_dict.get(item.get('cod_regime_tramitacao'), {}).get('des', '')
                item['ult_tramitacao'] = tramitacao_dict.get(cod_item, {})
                
                # Verificar se usuário pode acessar cadastro de normas
                is_operador_norma = False
                if not mtool.isAnonymousUser():
                    member = mtool.getAuthenticatedMember()
                    if member:
                        is_operador_norma = member.has_role(['Operador', 'Operador Norma'])
                
                norma_derivada_data = norma_dict.get(cod_item)
                if norma_derivada_data:
                    norma_derivada_data['url'] = f"{portal_url}/{'cadastros' if is_operador_norma else 'consultas'}/norma_juridica/norma_juridica_mostrar_proc?cod_norma={norma_derivada_data['cod_norma']}"
                item['norma_derivada'] = norma_derivada_data
            
            # URLs para documentos (se aplicável)
            if tipo_item in ('principal', 'acessoria_principal'):
                docs_folder = self.context.sapl_documentos.materia
                texto_integral_pdf = f"{cod_item}_texto_integral.pdf"
                if hasattr(docs_folder, texto_integral_pdf):
                    item['url_texto_integral'] = f"{portal_url}/pysc/download_materia_pysc?cod_materia={cod_item}&texto_original=1"
                    # Adicionar link para pasta digital apenas para usuários autenticados e matérias principais
                    if tipo_item == 'principal' and not mtool.isAnonymousUser():
                        item['url_pasta_digital'] = f"{portal_url}/consultas/materia/pasta_digital/?cod_materia={cod_item}&action=pasta"
                # Para matérias principais, também buscar redação final
                if tipo_item == 'principal':
                    redacao_final_pdf = f"{cod_item}_redacao_final.pdf"
                    if hasattr(docs_folder, redacao_final_pdf):
                        item['url_redacao_final'] = f"{portal_url}/pysc/download_materia_pysc?cod_materia={cod_item}&redacao_final=1"
            elif tipo_item == 'emenda':
                emenda_id = f"{cod_emenda}_emenda.pdf"
                try:
                    sapl_emendas = self.context.sapl_documentos.emenda
                    if hasattr(sapl_emendas, emenda_id):
                        item['url_texto_integral'] = f"{portal_url}/sapl_documentos/emenda/{emenda_id}"
                except:
                    pass
            elif tipo_item == 'substitutivo':
                subst_id = f"{cod_substitutivo}_substitutivo.pdf"
                try:
                    sapl_subst = self.context.sapl_documentos.substitutivo
                    if hasattr(sapl_subst, subst_id):
                        item['url_texto_integral'] = f"{portal_url}/sapl_documentos/substitutivo/{subst_id}"
                except:
                    pass
            
            formatted.append(item)
        
        return formatted

    def _add_unified_authorship_info(self, formatted_results, session, max_results=None):
        """Adiciona informações de autoria para resultados unificados.
        
        Args:
            formatted_results: Lista de resultados formatados
            session: Sessão do banco de dados
            max_results: Limite máximo de resultados a processar (None = sem limite)
        """
        if not formatted_results:
            return []
        
        start_time = time.time()
        
        # Proteção automática: limitar processamento se houver muitos resultados
        # Isso evita processar 78k+ resultados de uma vez (causa timeout)
        AUTO_LIMIT = 10000  # Limite automático para evitar problemas de performance
        effective_limit = max_results if max_results is not None else AUTO_LIMIT
        
        if len(formatted_results) > effective_limit:
            logger.warning(f"_add_unified_authorship_info: limitando processamento a {effective_limit} de {len(formatted_results)} resultados para evitar timeout")
            # Processar apenas uma amostra e adicionar autoria vazia para os demais
            sample_results = formatted_results[:effective_limit]
            # Processar amostra sem limite adicional (já está limitada)
            processed_sample = self._add_unified_authorship_info(sample_results, session, max_results=effective_limit)
            # Adicionar autoria vazia para os demais
            remaining_results = [
                {**item, 'autores': ''} 
                for item in formatted_results[effective_limit:]
            ]
            elapsed = time.time() - start_time
            if elapsed > 1.0:
                logger.info(f"_add_unified_authorship_info levou {elapsed:.2f}s para {len(formatted_results)} resultados (limitado a {effective_limit})")
            return processed_sample + remaining_results
        
        # Separar por tipo - usar sets para lookup O(1) em vez de listas O(n)
        materias_principal_ids = {r['cod_item'] for r in formatted_results if r['tipo_item'] == 'principal'}
        materias_acessoria_ids = {r['cod_item'] for r in formatted_results if r['tipo_item'] == 'acessoria_principal'}
        emendas_ids = [r['cod_emenda'] for r in formatted_results if r['tipo_item'] == 'emenda' and r['cod_emenda']]
        substitutivos_ids = [r['cod_substitutivo'] for r in formatted_results if r['tipo_item'] == 'substitutivo' and r['cod_substitutivo']]
        
        autoria_dict = {}
        
        # Otimização: unificar query de matérias principais e acessórias (ambas usam tabela Autoria)
        # Isso reduz de 2 queries para 1 query
        all_materia_ids = list(materias_principal_ids | materias_acessoria_ids)
        
        # Otimização crítica: processar em chunks para evitar queries muito grandes
        # MySQL tem limite prático de ~1000-2000 parâmetros em IN()
        CHUNK_SIZE = 1000
        if all_materia_ids:
            nome_autor_expr = _build_autor_name_expression()
            
            # Processar em chunks para evitar queries muito grandes
            for i in range(0, len(all_materia_ids), CHUNK_SIZE):
                chunk_ids = all_materia_ids[i:i + CHUNK_SIZE]
                autoria_query = session.query(
                    Autoria.cod_materia,
                    nome_autor_expr.label('nome_autor')
                ).join(Autor, Autoria.cod_autor == Autor.cod_autor)\
                 .join(TipoAutor, Autor.tip_autor == TipoAutor.tip_autor)\
                 .outerjoin(Parlamentar, Autor.cod_parlamentar == Parlamentar.cod_parlamentar)\
                 .outerjoin(Comissao, Autor.cod_comissao == Comissao.cod_comissao)\
                 .outerjoin(Bancada, Autor.cod_bancada == Bancada.cod_bancada)\
                 .outerjoin(Legislatura, Bancada.num_legislatura == Legislatura.num_legislatura)\
                 .filter(
                     Autoria.cod_materia.in_(chunk_ids),
                     Autoria.ind_excluido == 0,
                     Autor.ind_excluido == 0
                 ).order_by(
                     Autoria.cod_materia,
                     Autoria.ind_primeiro_autor.desc(),
                     nome_autor_expr
                 ).all()
                
                # Separar resultados por tipo de matéria (usar sets para lookup O(1))
                for cod_materia, nome in autoria_query:
                    # Determinar se é principal ou acessória
                    if cod_materia in materias_principal_ids:
                        key = ('principal', cod_materia)
                    else:
                        key = ('acessoria_principal', cod_materia)
                    
                    if key not in autoria_dict:
                        autoria_dict[key] = []
                    autoria_dict[key].append(nome)
        
        # Buscar autoria para emendas (também processar em chunks)
        if emendas_ids:
            # Remover duplicatas e processar em chunks
            emendas_ids = list(set(emendas_ids))
            TipoAutorEmenda_aut = aliased(TipoAutor, name='tipo_autor_emenda_aut')
            ParlamentarEmenda_aut = aliased(Parlamentar, name='parlamentar_emenda_aut')
            ComissaoEmenda_aut = aliased(Comissao, name='comissao_emenda_aut')
            BancadaEmenda_aut = aliased(Bancada, name='bancada_emenda_aut')
            LegislaturaEmenda_aut = aliased(Legislatura, name='legislatura_emenda_aut')
            AutorEmenda_aut = aliased(Autor, name='autor_emenda_aut')
            
            autor_nome_expr = _build_autor_name_expression(
                TipoAutor_alias=TipoAutorEmenda_aut,
                Parlamentar_alias=ParlamentarEmenda_aut,
                Comissao_alias=ComissaoEmenda_aut,
                Bancada_alias=BancadaEmenda_aut,
                Legislatura_alias=LegislaturaEmenda_aut,
                Autor_alias=AutorEmenda_aut
            )
            
            # Processar emendas em chunks
            for i in range(0, len(emendas_ids), CHUNK_SIZE):
                chunk_emendas = emendas_ids[i:i + CHUNK_SIZE]
                autoria_emendas = session.query(
                    AutoriaEmenda.cod_emenda,
                    autor_nome_expr.label('nome_autor')
                ).select_from(AutoriaEmenda)\
                 .join(AutorEmenda_aut, AutoriaEmenda.cod_autor == AutorEmenda_aut.cod_autor)\
                 .join(TipoAutorEmenda_aut, AutorEmenda_aut.tip_autor == TipoAutorEmenda_aut.tip_autor)\
                 .outerjoin(ParlamentarEmenda_aut, AutorEmenda_aut.cod_parlamentar == ParlamentarEmenda_aut.cod_parlamentar)\
                 .outerjoin(ComissaoEmenda_aut, AutorEmenda_aut.cod_comissao == ComissaoEmenda_aut.cod_comissao)\
                 .outerjoin(BancadaEmenda_aut, AutorEmenda_aut.cod_bancada == BancadaEmenda_aut.cod_bancada)\
                 .outerjoin(LegislaturaEmenda_aut, BancadaEmenda_aut.num_legislatura == LegislaturaEmenda_aut.num_legislatura)\
                 .filter(
                     AutoriaEmenda.cod_emenda.in_(chunk_emendas),
                     AutoriaEmenda.ind_excluido == 0,
                     AutorEmenda_aut.ind_excluido == 0
                 ).all()
                
                for cod_emenda, nome in autoria_emendas:
                    key = ('emenda', cod_emenda)
                    if key not in autoria_dict:
                        autoria_dict[key] = []
                    autoria_dict[key].append(nome)
        
        # Buscar autoria para substitutivos (também processar em chunks)
        if substitutivos_ids:
            # Remover duplicatas e processar em chunks
            substitutivos_ids = list(set(substitutivos_ids))
            TipoAutorSubst_aut = aliased(TipoAutor, name='tipo_autor_subst_aut')
            ParlamentarSubst_aut = aliased(Parlamentar, name='parlamentar_subst_aut')
            ComissaoSubst_aut = aliased(Comissao, name='comissao_subst_aut')
            BancadaSubst_aut = aliased(Bancada, name='bancada_subst_aut')
            LegislaturaSubst_aut = aliased(Legislatura, name='legislatura_subst_aut')
            AutorSubst_aut = aliased(Autor, name='autor_subst_aut')
            
            autor_nome_expr = _build_autor_name_expression(
                TipoAutor_alias=TipoAutorSubst_aut,
                Parlamentar_alias=ParlamentarSubst_aut,
                Comissao_alias=ComissaoSubst_aut,
                Bancada_alias=BancadaSubst_aut,
                Legislatura_alias=LegislaturaSubst_aut,
                Autor_alias=AutorSubst_aut
            )
            
            # Processar substitutivos em chunks
            for i in range(0, len(substitutivos_ids), CHUNK_SIZE):
                chunk_subst = substitutivos_ids[i:i + CHUNK_SIZE]
                autoria_subst = session.query(
                    AutoriaSubstitutivo.cod_substitutivo,
                    autor_nome_expr.label('nome_autor')
                ).select_from(AutoriaSubstitutivo)\
                 .join(AutorSubst_aut, AutoriaSubstitutivo.cod_autor == AutorSubst_aut.cod_autor)\
                 .join(TipoAutorSubst_aut, AutorSubst_aut.tip_autor == TipoAutorSubst_aut.tip_autor)\
                 .outerjoin(ParlamentarSubst_aut, AutorSubst_aut.cod_parlamentar == ParlamentarSubst_aut.cod_parlamentar)\
                 .outerjoin(ComissaoSubst_aut, AutorSubst_aut.cod_comissao == ComissaoSubst_aut.cod_comissao)\
                 .outerjoin(BancadaSubst_aut, AutorSubst_aut.cod_bancada == BancadaSubst_aut.cod_bancada)\
                 .outerjoin(LegislaturaSubst_aut, BancadaSubst_aut.num_legislatura == LegislaturaSubst_aut.num_legislatura)\
                 .filter(
                     AutoriaSubstitutivo.cod_substitutivo.in_(chunk_subst),
                     AutoriaSubstitutivo.ind_excluido == 0,
                     AutorSubst_aut.ind_excluido == 0
                 ).all()
                
                for cod_subst, nome in autoria_subst:
                    key = ('substitutivo', cod_subst)
                    if key not in autoria_dict:
                        autoria_dict[key] = []
                    autoria_dict[key].append(nome)
        
        # Adicionar autoria aos resultados
        for result in formatted_results:
            tipo_item = result['tipo_item']
            cod_item = result.get('cod_emenda') if tipo_item == 'emenda' else (result.get('cod_substitutivo') if tipo_item == 'substitutivo' else result.get('cod_item'))
            key = (tipo_item, cod_item)
            result['autores'] = ', '.join(autoria_dict.get(key, []))
        
        elapsed = time.time() - start_time
        if elapsed > 1.0:
            logger.info(f"_add_unified_authorship_info levou {elapsed:.2f}s para {len(formatted_results)} resultados")
        
        return formatted_results

    def _apply_ordering(self, query, session):
        ordem_campo = self.request.get('ordem_campo')
        ordem_direcao = self.request.get('ordem_direcao', 'asc')
        
        # Ordenação por Número (default: ano desc, depois número)
        if ordem_campo == 'num_ident_basica':
            order_logic = [
                MateriaLegislativa.ano_ident_basica,
                func.lpad(cast(MateriaLegislativa.num_ident_basica, String), 6, '0')
            ]
            if ordem_direcao == 'desc':
                query = query.order_by(desc(order_logic[0]), desc(order_logic[1]))
            else:
                query = query.order_by(asc(order_logic[0]), asc(order_logic[1]))

        # Ordenação apenas pelo Ano (ano e número)
        elif ordem_campo == 'ano_ident_basica':
            order_by_ano = asc(MateriaLegislativa.ano_ident_basica) if ordem_direcao == 'asc' else desc(MateriaLegislativa.ano_ident_basica)
            order_by_num = asc(func.lpad(cast(MateriaLegislativa.num_ident_basica, String), 6, '0')) if ordem_direcao == 'asc' else desc(func.lpad(cast(MateriaLegislativa.num_ident_basica, String), 6, '0'))
            query = query.order_by(order_by_ano, order_by_num)

        # Ordenação por Autoria (primeiro autor alfabético)
        elif ordem_campo == 'autores':
            nome_autor_expr = _build_autor_name_expression()
            from sqlalchemy.orm import aliased
            sub_autor = (
                session.query(
                    Autoria.cod_materia,
                    nome_autor_expr.label('nom_autor')
                )
                .join(Autor, Autoria.cod_autor == Autor.cod_autor)
                .join(TipoAutor, Autor.tip_autor == TipoAutor.tip_autor)
                .outerjoin(Parlamentar, Autor.cod_parlamentar == Parlamentar.cod_parlamentar)
                .outerjoin(Comissao, Autor.cod_comissao == Comissao.cod_comissao)
                .outerjoin(Bancada, Autor.cod_bancada == Bancada.cod_bancada)
                .outerjoin(Legislatura, Bancada.num_legislatura == Legislatura.num_legislatura)
                .filter(Autoria.ind_excluido == 0, Autor.ind_excluido == 0)
                .order_by(
                    Autoria.cod_materia,
                    Autoria.ind_primeiro_autor.desc(),
                    nome_autor_expr
                )
            ).subquery('primeiro_autor')
            query = query.outerjoin(
                sub_autor, MateriaLegislativa.cod_materia == sub_autor.c.cod_materia
            )
            order_col = sub_autor.c.nom_autor
            if ordem_direcao == 'desc':
                query = query.order_by(desc(order_col))
            else:
                query = query.order_by(asc(order_col))

        # Ordenação por outros campos textuais
        elif ordem_campo in ['des_tipo_materia', 'txt_ementa', 'dat_apresentacao']:
            coluna_ordenacao = {
                'des_tipo_materia': TipoMateriaLegislativa.des_tipo_materia,
                'txt_ementa': MateriaLegislativa.txt_ementa,
                'dat_apresentacao': MateriaLegislativa.dat_apresentacao
            }[ordem_campo]
            order_col = desc(coluna_ordenacao) if ordem_direcao == 'desc' else asc(coluna_ordenacao)
            query = query.order_by(order_col)

        # Ordenação padrão
        else:
            ordem = self.request.get('rd_ordem', '1')
            order_logic = [
                MateriaLegislativa.ano_ident_basica,
                func.lpad(cast(MateriaLegislativa.num_ident_basica, String), 6, '0')
            ]
            if ordem == '0':
                # Mais antigos primeiro
                query = query.order_by(asc(order_logic[0]), asc(order_logic[1]))
            else:
                # Mais recentes primeiro (padrão)
                query = query.order_by(desc(order_logic[0]), desc(order_logic[1]))

        return query

    def _format_results(self, results_raw):
        if not results_raw:
            return []
        
        formatted = []
        portal_url = getToolByName(self.context, 'portal_url')()
        mtool = getToolByName(self.context, 'portal_membership')
        # Verificar se é operador: usuário autenticado com perfis "Operador" ou "Operador Materia"
        is_operador = False
        if not mtool.isAnonymousUser():
            member = mtool.getAuthenticatedMember()
            if member:
                is_operador = member.has_role(['Operador', 'Operador Materia'])
        docs_folder = self.context.sapl_documentos.materia
        
        materia_ids = [r[0].cod_materia for r in results_raw]
        session = Session()
        
        try:
            # Agregações em batch (evita N+1 queries)
            # Contagem de substitutivos
            subst_counts = session.query(
                Substitutivo.cod_materia,
                func.count(Substitutivo.cod_substitutivo).label('qtd')
            ).filter(
                Substitutivo.cod_materia.in_(materia_ids),
                Substitutivo.ind_excluido == 0
            ).group_by(Substitutivo.cod_materia).all()
            subst_dict = {m_id: qtd for m_id, qtd in subst_counts}
            
            # Contagem de emendas
            emenda_counts = session.query(
                Emenda.cod_materia,
                func.count(Emenda.cod_emenda).label('qtd')
            ).filter(
                Emenda.cod_materia.in_(materia_ids),
                Emenda.ind_excluido == 0
            ).group_by(Emenda.cod_materia).all()
            emenda_dict = {m_id: qtd for m_id, qtd in emenda_counts}
            
            # Informações de anexadas (matérias anexadas a esta)
            Anexada_anex = aliased(Anexada, name='anexada_anex')
            MateriaLegislativa_anex = aliased(MateriaLegislativa, name='materia_anex')
            TipoMateriaLegislativa_anex = aliased(TipoMateriaLegislativa, name='tipo_anex')
            anexadas_info = session.query(
                Anexada_anex.cod_materia_principal,
                MateriaLegislativa_anex.cod_materia,
                TipoMateriaLegislativa_anex.sgl_tipo_materia,
                MateriaLegislativa_anex.num_ident_basica,
                MateriaLegislativa_anex.ano_ident_basica
            ).join(
                MateriaLegislativa_anex, Anexada_anex.cod_materia_anexada == MateriaLegislativa_anex.cod_materia
            ).join(
                TipoMateriaLegislativa_anex, MateriaLegislativa_anex.tip_id_basica == TipoMateriaLegislativa_anex.tip_materia
            ).filter(
                Anexada_anex.cod_materia_principal.in_(materia_ids),
                Anexada_anex.ind_excluido == 0,
                MateriaLegislativa_anex.ind_excluido == 0
            ).order_by(
                Anexada_anex.cod_materia_principal,
                MateriaLegislativa_anex.ano_ident_basica.desc(),
                MateriaLegislativa_anex.num_ident_basica
            ).all()
            
            anexadas_dict = {}
            for m_id, cod_materia_anex, sgl_tipo, num, ano in anexadas_info:
                if m_id not in anexadas_dict:
                    anexadas_dict[m_id] = []
                identificacao = f"{sgl_tipo or ''} {num}/{ano}".strip()
                # URL será construída no loop principal onde já temos acesso ao is_operador
                anexadas_dict[m_id].append({
                    'cod_materia': cod_materia_anex,
                    'identificacao': identificacao
                })
            
            # Contagem de anexadoras (matérias que anexaram esta) - mantido para compatibilidade
            anexadora_counts = session.query(
                Anexada.cod_materia_anexada,
                func.count(Anexada.cod_materia_principal).label('qtd')
            ).filter(
                Anexada.cod_materia_anexada.in_(materia_ids),
                Anexada.ind_excluido == 0
            ).group_by(Anexada.cod_materia_anexada).all()
            anexadora_dict = {m_id: qtd for m_id, qtd in anexadora_counts}
            
            # Contagem de documentos acessórios
            doc_acessorio_counts = session.query(
                DocumentoAcessorio.cod_materia,
                func.count(DocumentoAcessorio.cod_documento).label('qtd')
            ).filter(
                DocumentoAcessorio.cod_materia.in_(materia_ids),
                DocumentoAcessorio.ind_excluido == 0
            ).group_by(DocumentoAcessorio.cod_materia).all()
            doc_acessorio_dict = {m_id: qtd for m_id, qtd in doc_acessorio_counts}
            
            # Contagem de pareceres de comissão (estão em Relatoria, não em Parecer)
            # Pareceres são identificados quando num_parecer não é nulo na Relatoria
            parecer_counts = session.query(
                Relatoria.cod_materia,
                func.count(Relatoria.cod_relatoria).label('qtd')
            ).filter(
                Relatoria.cod_materia.in_(materia_ids),
                Relatoria.ind_excluido == 0,
                Relatoria.num_parecer.isnot(None)  # Apenas relatorias com parecer
            ).group_by(Relatoria.cod_materia).all()
            parecer_dict = {m_id: qtd for m_id, qtd in parecer_counts}
            
            # Regime de tramitação (join já feito na query principal)
            # Buscar regimes para formatação
            regimes = session.query(RegimeTramitacao).filter(
                RegimeTramitacao.ind_excluido == 0
            ).all()
            # RegimeTramitacao só tem des_regime_tramitacao, não tem sgl_regime_tramitacao
            regime_dict = {r.cod_regime_tramitacao: {'des': r.des_regime_tramitacao} 
                          for r in regimes}
            
            # Última tramitação (buscar em batch)
            Tramitacao_ult = aliased(Tramitacao, name='tramitacao_ult')
            StatusTram_ult = aliased(StatusTramitacao, name='status_tram_ult')
            UnidadeTram_ult = aliased(UnidadeTramitacao, name='unidade_tram_ult')
            Comissao_ult = aliased(Comissao, name='comissao_ult')
            Orgao_ult = aliased(Orgao, name='orgao_ult')
            Parlamentar_ult = aliased(Parlamentar, name='parlamentar_ult')
            
            # Expressão para nome da unidade de tramitação
            # O nome vem de Comissao, Orgao ou Parlamentar, não há campo direto em UnidadeTramitacao
            nome_unidade_expr = case(
                (UnidadeTram_ult.cod_comissao != None, Comissao_ult.nom_comissao),
                (UnidadeTram_ult.cod_orgao != None, Orgao_ult.nom_orgao),
                (UnidadeTram_ult.cod_parlamentar != None, Parlamentar_ult.nom_parlamentar),
                else_=cast(None, String)  # Fallback: nenhum nome disponível
            ).label('nom_unidade')
            
            # Normas derivadas (buscar em batch)
            TipoNormaJuridica_norma = aliased(TipoNormaJuridica, name='tipo_norma_norma')
            normas_derivadas = session.query(
                NormaJuridica.cod_materia,
                TipoNormaJuridica_norma.sgl_tipo_norma,
                NormaJuridica.num_norma,
                NormaJuridica.ano_norma,
                NormaJuridica.cod_norma
            ).join(
                TipoNormaJuridica_norma, NormaJuridica.tip_norma == TipoNormaJuridica_norma.tip_norma
            ).filter(
                NormaJuridica.cod_materia.in_(materia_ids),
                NormaJuridica.ind_excluido == 0
            ).all()
            # Criar dict: cod_materia -> primeira norma (geralmente há apenas uma)
            norma_dict = {}
            for cod_materia, sgl_tipo_norma, num_norma, ano_norma, cod_norma in normas_derivadas:
                if cod_materia not in norma_dict:
                    norma_dict[cod_materia] = {
                        'sgl_norma': sgl_tipo_norma or '',
                        'num_norma': num_norma,
                        'ano_norma': ano_norma,
                        'cod_norma': cod_norma
                    }
            
            tramitacoes_ult = session.query(
                Tramitacao_ult.cod_materia,
                StatusTram_ult.des_status,
                nome_unidade_expr,
                Tramitacao_ult.dat_tramitacao,
                Tramitacao_ult.dat_fim_prazo
            ).outerjoin(
                StatusTram_ult, Tramitacao_ult.cod_status == StatusTram_ult.cod_status
            ).outerjoin(
                UnidadeTram_ult, Tramitacao_ult.cod_unid_tram_dest == UnidadeTram_ult.cod_unid_tramitacao
            ).outerjoin(
                Comissao_ult, UnidadeTram_ult.cod_comissao == Comissao_ult.cod_comissao
            ).outerjoin(
                Orgao_ult, UnidadeTram_ult.cod_orgao == Orgao_ult.cod_orgao
            ).outerjoin(
                Parlamentar_ult, UnidadeTram_ult.cod_parlamentar == Parlamentar_ult.cod_parlamentar
            ).filter(
                Tramitacao_ult.cod_materia.in_(materia_ids),
                Tramitacao_ult.ind_excluido == 0,
                Tramitacao_ult.ind_ult_tramitacao == 1
            ).order_by(
                Tramitacao_ult.cod_materia,
                desc(Tramitacao_ult.dat_tramitacao),
                desc(Tramitacao_ult.cod_tramitacao)
            ).all()
            
            tramitacao_dict = {}
            for cod_materia, des_status, nom_unidade, dat_tramitacao, dat_fim_prazo in tramitacoes_ult:
                # Se já existe uma tramitação para esta matéria, manter apenas a primeira (mais recente)
                # devido à ordenação por dat_tramitacao DESC
                if cod_materia not in tramitacao_dict:
                    tramitacao_dict[cod_materia] = {
                        'des_status': des_status or '',
                        'nom_unidade': nom_unidade or '',
                        'dat_tramitacao': dat_tramitacao.strftime('%d/%m/%Y %H:%M:%S') if dat_tramitacao else '',
                        'dat_fim_prazo': dat_fim_prazo.strftime('%d/%m/%Y') if dat_fim_prazo else ''
                    }
            
        except Exception as e:
            logger.error(f"Erro ao buscar agregações: {str(e)}", exc_info=True)
            subst_dict = {}
            emenda_dict = {}
            anexada_dict = {}
            anexadora_dict = {}
            doc_acessorio_dict = {}
            parecer_dict = {}
            regime_dict = {}
            tramitacao_dict = {}
            norma_dict = {}
        finally:
            session.close()
        
        # Formatar resultados
        # Verificar se usuário pode acessar cadastro de normas (apenas Operador ou Operador Norma)
        is_operador_norma = False
        if not mtool.isAnonymousUser():
            member = mtool.getAuthenticatedMember()
            if member:
                is_operador_norma = member.has_role(['Operador', 'Operador Norma'])
        
        for materia, tipo_materia in results_raw:
            detail_url = f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/materia/materia_mostrar_proc?cod_materia={materia.cod_materia}"
            norma_derivada_data = norma_dict.get(materia.cod_materia)
            if norma_derivada_data:
                norma_derivada_data['url'] = f"{portal_url}/{'cadastros' if is_operador_norma else 'consultas'}/norma_juridica/norma_juridica_mostrar_proc?cod_norma={norma_derivada_data['cod_norma']}"
            # Formatar identificação no formato "Requerimento n° 491/2025"
            identificacao = f"{tipo_materia.des_tipo_materia or ''} n° {materia.num_ident_basica}/{materia.ano_ident_basica}".strip()
            item = {
                'cod_materia': materia.cod_materia,
                'tipo_item': 'principal',  # Matérias principais da query normal
                'des_tipo_materia': tipo_materia.des_tipo_materia,
                'sgl_tipo_materia': tipo_materia.sgl_tipo_materia or '',
                'num_ident_basica': materia.num_ident_basica,
                'ano_ident_basica': materia.ano_ident_basica,
                'txt_ementa': materia.txt_ementa or '',
                'dat_apresentacao': materia.dat_apresentacao.strftime('%d/%m/%Y') if materia.dat_apresentacao else '',
                'num_protocolo': materia.num_protocolo,
                'ind_tramitacao': materia.ind_tramitacao,
                'identificacao': identificacao,  # Título formatado no formato "Requerimento n° 491/2025"
                'autores': '',
                'detail_url': detail_url,
                'url_texto_integral': None,
                'url_redacao_final': None,
                'url_pasta_digital': None,
                # Novos campos com agregações
                'qtd_substitutivos': subst_dict.get(materia.cod_materia, 0),
                'qtd_emendas': emenda_dict.get(materia.cod_materia, 0),
                'qtd_anexadas': len(anexadas_dict.get(materia.cod_materia, [])),
                'anexadas': [
                    {
                        'identificacao': a['identificacao'],
                        'url': f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/materia/materia_mostrar_proc?cod_materia={a['cod_materia']}"
                    }
                    for a in anexadas_dict.get(materia.cod_materia, [])
                ],  # Lista de objetos com identificação e URL das matérias anexadas
                'qtd_anexadoras': anexadora_dict.get(materia.cod_materia, 0),
                'qtd_documentos_acessorios': doc_acessorio_dict.get(materia.cod_materia, 0),
                'qtd_pareceres': parecer_dict.get(materia.cod_materia, 0),
                'cod_regime_tramitacao': materia.cod_regime_tramitacao,
                'des_regime_tramitacao': regime_dict.get(materia.cod_regime_tramitacao, {}).get('des', ''),
                # Informações da última tramitação
                'ult_tramitacao': tramitacao_dict.get(materia.cod_materia, {}),
                # Norma derivada
                'norma_derivada': norma_dict.get(materia.cod_materia)
            }
            texto_integral_pdf = f"{materia.cod_materia}_texto_integral.pdf"
            if hasattr(docs_folder, texto_integral_pdf):
                item['url_texto_integral'] = f"{portal_url}/pysc/download_materia_pysc?cod_materia={materia.cod_materia}&texto_original=1"
                # Adicionar link para pasta digital apenas para usuários autenticados
                if not mtool.isAnonymousUser():
                    item['url_pasta_digital'] = f"{portal_url}/consultas/materia/pasta_digital/?cod_materia={materia.cod_materia}&action=pasta"
            redacao_final_pdf = f"{materia.cod_materia}_redacao_final.pdf"
            if hasattr(docs_folder, redacao_final_pdf):
                item['url_redacao_final'] = f"{portal_url}/pysc/download_materia_pysc?cod_materia={materia.cod_materia}&redacao_final=1"
            formatted.append(item)
        return formatted

    def _add_authorship_info(self, formatted_results):
        if not formatted_results:
            return []
        
        session = Session()
        try:
            materia_ids = [r['cod_materia'] for r in formatted_results]
            if not materia_ids:
                return formatted_results
            
            authors_dict = {m_id: [] for m_id in materia_ids}
            nom_autor_join_expr = _build_autor_name_expression().label('nom_autor_join')
            
            autoria_query = session.query(
                Autoria.cod_materia, 
                nom_autor_join_expr,
                TipoAutor.des_tipo_autor
            )\
                .join(Autor, Autoria.cod_autor == Autor.cod_autor)\
                .join(TipoAutor, Autor.tip_autor == TipoAutor.tip_autor)\
                .outerjoin(Parlamentar, Autor.cod_parlamentar == Parlamentar.cod_parlamentar)\
                .outerjoin(Comissao, Autor.cod_comissao == Comissao.cod_comissao)\
                .outerjoin(Bancada, Autor.cod_bancada == Bancada.cod_bancada)\
                .outerjoin(Legislatura, Bancada.num_legislatura == Legislatura.num_legislatura)\
                .filter(Autoria.cod_materia.in_(materia_ids), Autoria.ind_excluido == 0, Autor.ind_excluido == 0)\
                .order_by(Autoria.cod_materia, Autoria.ind_primeiro_autor.desc(), nom_autor_join_expr).all()
            
            for m_id, nom_autor, des_tipo_autor in autoria_query:
                if nom_autor:
                    # Não exibir tipo de autor entre parênteses
                    authors_dict[m_id].append(nom_autor)
            
            for result in formatted_results:
                result['autores'] = ', '.join(authors_dict.get(result['cod_materia'], []))
                
            return formatted_results
        finally:
            session.close()

    def _paginate_and_respond(self, query, page, page_size, total_count):
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        page = min(page, total_pages) if total_pages > 0 else 1
        offset = (page - 1) * page_size
        
        # O eagar loading (joinedload) dos autores pode ser útil aqui
        # Dependendo da complexidade, pode ser melhor manter o _add_authorship_info separado.
        results_raw = query.offset(offset).limit(page_size).all() if total_count > 0 else []
        
        formatted_data = self._format_results(results_raw)
        final_data = self._add_authorship_info(formatted_data)
        
        return {
            'data': final_data, 'total': total_count, 'page': page,
            'per_page': page_size, 'total_pages': total_pages,
            'has_previous': page > 1, 'has_next': page < total_pages
        }

    def _export_csv(self, results_raw):
        self.request.response.setHeader('Content-Type', 'text/csv; charset=utf-8')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="materias.csv"')
        output = io.StringIO()
        if not results_raw: return ""
        formatted_for_export = self._add_authorship_info(self._format_results(results_raw))
        
        # Renomear 'autores' para 'autoria' nos dados antes de exportar
        for item in formatted_for_export:
            if 'autores' in item:
                item['autoria'] = item.pop('autores')
        
        fieldnames = ['des_tipo_materia', 'num_ident_basica', 'ano_ident_basica', 'txt_ementa', 'dat_apresentacao', 'autoria']
        
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(formatted_for_export)
        return output.getvalue().encode('utf-8')

    def _export_excel(self, results_raw):
        self.request.response.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="materias.xlsx"')
        if not results_raw: return b""
        formatted_for_export = self._add_authorship_info(self._format_results(results_raw))
        
        # Renomear 'autores' para 'autoria' nos dados antes de exportar
        for item in formatted_for_export:
            if 'autores' in item:
                item['autoria'] = item.pop('autores')
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Matérias"
        
        header = ['des_tipo_materia', 'num_ident_basica', 'ano_ident_basica', 'txt_ementa', 'dat_apresentacao', 'autoria']
        
        ws.append(header)
        for r in formatted_for_export:
            ws.append([str(r.get(col, '')) for col in header])
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    def _export_pdf(self, results_raw):
        """Gera um arquivo PDF aprimorado a partir dos resultados."""
        self.request.response.setHeader('Content-Type', 'application/pdf')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="materias_legislativas.pdf"')
        
        if not results_raw:
            return b""
        
        # Formata os dados para exportação
        formatted_for_export = self._add_authorship_info(self._format_results(results_raw))
        
        # Configurações do documento
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
            title="Relatório de Matérias Legislativas"
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
        header_style.alignment = 1 # Center
        
        # Cabeçalho com metadados
        elements = []
        elements.append(Paragraph("RELATÓRIO DE MATÉRIAS LEGISLATIVAS", styles['Title']))
        elements.append(Paragraph(f"Data de geração: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Paragraph(f"Total de registros: {len(formatted_for_export)}", styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))
        
        # Dados da tabela
        data_keys = ['des_tipo_materia', 'num_ano_combined', 'txt_ementa', 'dat_apresentacao', 'autoria']
        header_labels = ['Tipo', 'Número/Ano', 'Ementa', 'Apresentação', 'Autoria']
        
        # Preparar dados da tabela
        table_data = []
        
        # Renomear 'autores' para 'autoria' nos dados antes de exportar
        for item in formatted_for_export:
            if 'autores' in item:
                item['autoria'] = item.pop('autores')
        
        # Cabeçalho da tabela
        table_data.append([Paragraph(label, header_style) for label in header_labels])
        
        # Linhas de dados
        for item in formatted_for_export:
            item['num_ano_combined'] = f"{item['num_ident_basica']}/{item['ano_ident_basica']}"
            
            row = [
                Paragraph(str(item.get('des_tipo_materia', '')), normal_style),
                Paragraph(str(item.get('num_ano_combined', '')), normal_style),
                Paragraph(str(item.get('txt_ementa', '')), normal_style),
                Paragraph(str(item.get('dat_apresentacao', '')), normal_style),
                Paragraph(str(item.get('autoria', '')), normal_style)
            ]
            table_data.append(row)
        
        # Configurações da tabela
        page_width, page_height = landscape(A4)
        content_width = page_width - doc.leftMargin - doc.rightMargin
        
        # Larguras das colunas (ajustáveis conforme necessidade)
        col_widths = [
            0.15 * content_width,  # Tipo
            0.12 * content_width,  # Número/Ano
            0.38 * content_width,  # Ementa
            0.12 * content_width,  # Apresentação
            0.23 * content_width   # Autoria
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
            ('ALIGN', (2,1), (2,-1), 'LEFT'),
            ('ALIGN', (4,1), (4,-1), 'LEFT'),
            
            # Grid e bordas
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#2F5597')),
            
            # Zebrado (alternância de cores)
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

    def _export_csv_unified(self, formatted_results):
        """Exporta resultados unificados para CSV."""
        self.request.response.setHeader('Content-Type', 'text/csv; charset=utf-8')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="materias_acessorias.csv"')
        output = io.StringIO()
        if not formatted_results: return ""
        
        # Renomear 'autores' para 'autoria' nos dados antes de exportar
        for item in formatted_results:
            if 'autores' in item:
                item['autoria'] = item.pop('autores')
        
        fieldnames = ['des_tipo_materia', 'identificacao', 'num_ident_basica', 'ano_ident_basica', 'txt_ementa', 'dat_apresentacao', 'autoria']
        
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(formatted_results)
        return output.getvalue().encode('utf-8')

    def _export_excel_unified(self, formatted_results):
        """Exporta resultados unificados para Excel."""
        self.request.response.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="materias_acessorias.xlsx"')
        if not formatted_results: return b""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Matérias Acessórias"
        
        # Renomear 'autores' para 'autoria' nos dados antes de exportar
        for item in formatted_results:
            if 'autores' in item:
                item['autoria'] = item.pop('autores')
        
        header = ['Tipo', 'Identificação', 'Número', 'Ano', 'Ementa', 'Apresentação', 'Autoria']
        
        ws.append(header)
        for r in formatted_results:
            ws.append([
                str(r.get('des_tipo_materia', '')),
                str(r.get('identificacao', '')),
                str(r.get('num_ident_basica', '')),
                str(r.get('ano_ident_basica', '')),
                str(r.get('txt_ementa', '')),
                str(r.get('dat_apresentacao', '')),
                str(r.get('autoria', ''))
            ])
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    def _export_pdf_unified(self, formatted_results):
        """Exporta resultados unificados para PDF."""
        self.request.response.setHeader('Content-Type', 'application/pdf')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="materias_acessorias.pdf"')
        
        if not formatted_results:
            return b""
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
            title="Relatório de Matérias Acessórias"
        )
        
        styles = getSampleStyleSheet()
        normal_style = styles['Normal']
        normal_style.fontSize = 8
        normal_style.leading = 10
        normal_style.wordWrap = 'LTR'
        
        header_style = styles['Heading4']
        header_style.fontSize = 9
        header_style.leading = 12
        header_style.textColor = colors.white
        header_style.alignment = 1
        
        elements = []
        elements.append(Paragraph("RELATÓRIO DE MATÉRIAS ACESSÓRIAS", styles['Title']))
        elements.append(Paragraph(f"Data de geração: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Paragraph(f"Total de registros: {len(formatted_results)}", styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))
        
        header_labels = ['Tipo', 'Identificação', 'Ementa', 'Apresentação', 'Autoria']
        table_data = []
        
        # Renomear 'autores' para 'autoria' nos dados antes de exportar
        for item in formatted_results:
            if 'autores' in item:
                item['autoria'] = item.pop('autores')
        
        table_data.append([Paragraph(label, header_style) for label in header_labels])
        
        for item in formatted_results:
            row = [
                Paragraph(str(item.get('des_tipo_materia', '')), normal_style),
                Paragraph(str(item.get('identificacao', '')), normal_style),
                Paragraph(str(item.get('txt_ementa', '')), normal_style),
                Paragraph(str(item.get('dat_apresentacao', '')), normal_style),
                Paragraph(str(item.get('autoria', '')), normal_style)
            ]
            table_data.append(row)
        
        page_width, page_height = landscape(A4)
        content_width = page_width - doc.leftMargin - doc.rightMargin
        
        col_widths = [
            0.15 * content_width,
            0.20 * content_width,
            0.35 * content_width,
            0.12 * content_width,
            0.18 * content_width
        ]
        
        table = Table(
            table_data,
            colWidths=col_widths,
            repeatRows=1,
            hAlign='LEFT'
        )
        
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (0,1), (1,-1), 'CENTER'),
            ('ALIGN', (2,1), (2,-1), 'LEFT'),
            ('ALIGN', (4,1), (4,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#2F5597')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F2F2F2')]),
            ('LEFTPADDING', (0,0), (-1,-1), 3),
            ('RIGHTPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        
        elements.append(table)
        
        def footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            page_num = canvas.getPageNumber()
            text = f"Página {page_num}"
            canvas.drawRightString(page_width - doc.rightMargin, 1*cm, text)
            canvas.restoreState()
        
        doc.build(elements, onFirstPage=footer, onLaterPages=footer)
        
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data

    def render(self):
        session = Session()
        render_start_time = time.time()
        try:
            # Uma sugestão antes de qualquer alteração de código:
            # Rode o comando `ANALYZE TABLE tramitacao;` no seu MySQL.
            # Às vezes, as estatísticas da tabela ficam desatualizadas e o MySQL
            # escolhe um plano de execução ruim mesmo com o índice correto.
            
            # Verificar se deve calcular estatísticas (carregamento sob demanda)
            calcular_estatisticas = self.request.get('calcular_estatisticas', '0') == '1'
            
            # Determinar escopo baseado nos tipos selecionados
            scope_start = time.time()
            scope = self._determine_search_scope(session)
            if time.time() - render_start_time > 1.0:
                logger.debug(f"_determine_search_scope levou {time.time() - scope_start:.2f}s")
            
            # Inicializar variáveis que podem não ser definidas em todos os caminhos
            ordered_query = None
            
            # Casos especiais: apenas emenda ou apenas substitutivo (agora inclui tipos acessórios relacionados)
            # Esses casos agora são tratados como pesquisa_acessoria=True, então caem no bloco seguinte
            if scope['pesquisa_acessoria'] and not scope['pesquisa_principal']:
                # Apenas matérias acessórias (unificadas: acessórias principais + emendas + substitutivos)
                # Construir queries individuais para ter controle sobre o que incluir
                queries_para_unir = []
                
                # Adicionar query de matérias acessórias principais se houver tipos acessórios selecionados
                if scope['tipos_acessorios']:
                    query_acessoria_principal = self._build_acessoria_principal_query(session)
                    query_acessoria_principal = query_acessoria_principal.filter(
                        MateriaLegislativa.tip_id_basica.in_(scope['tipos_acessorios'])
                    )
                    query_acessoria_principal = self._apply_filters_to_acessoria_query(query_acessoria_principal, session)
                    queries_para_unir.append(query_acessoria_principal)
                
                # Adicionar query de emendas se solicitado (sempre pesquisar na tabela dedicada)
                if scope['pesquisa_emenda']:
                    query_emenda = self._build_emenda_query(session)
                    query_emenda = self._apply_filters_to_emenda_query(query_emenda, session)
                    queries_para_unir.append(query_emenda)
                
                # Adicionar query de substitutivos se solicitado (sempre pesquisar na tabela dedicada)
                if scope['pesquisa_substitutivo']:
                    query_substitutivo = self._build_substitutivo_query(session)
                    query_substitutivo = self._apply_filters_to_substitutivo_query(query_substitutivo, session)
                    queries_para_unir.append(query_substitutivo)
                
                # Se não há queries para unir, retornar vazio
                if not queries_para_unir:
                    results_raw = []
                    total_count = 0
                    stats = {}
                    stats_by_author = {}
                    formatted_data = []
                    final_data = []
                elif len(queries_para_unir) == 1:
                    # Se há apenas uma query, usar diretamente
                    query = queries_para_unir[0]
                    # Aplicar ordenação usando as colunas da query
                    ordem = self.request.get('rd_ordem', '1')
                    # As queries de emenda e substitutivo têm dat_apresentacao como coluna
                    if scope['pesquisa_emenda'] and not scope['pesquisa_substitutivo']:
                        # Query de emenda - usar coluna Emenda.dat_apresentacao
                        if ordem == '0':
                            query = query.order_by(asc(Emenda.dat_apresentacao))
                        else:
                            query = query.order_by(desc(Emenda.dat_apresentacao))
                    elif scope['pesquisa_substitutivo'] and not scope['pesquisa_emenda']:
                        # Query de substitutivo - usar coluna Substitutivo.dat_apresentacao
                        if ordem == '0':
                            query = query.order_by(asc(Substitutivo.dat_apresentacao))
                        else:
                            query = query.order_by(desc(Substitutivo.dat_apresentacao))
                    else:
                        # Para matérias acessórias principais, usar MateriaLegislativa.dat_apresentacao
                        if ordem == '0':
                            query = query.order_by(asc(MateriaLegislativa.dat_apresentacao))
                        else:
                            query = query.order_by(desc(MateriaLegislativa.dat_apresentacao))
                    
                    query_start = time.time()
                    results_raw = query.all()
                    query_elapsed = time.time() - query_start
                    total_count = len(results_raw)
                    if query_elapsed > 1.0:
                        logger.debug(f"Query única levou {query_elapsed:.2f}s para {total_count} resultados")
                    
                    format_start = time.time()
                    formatted_data = self._format_unified_results(results_raw, session)
                    format_elapsed = time.time() - format_start
                    if format_elapsed > 1.0:
                        logger.debug(f"_format_unified_results levou {format_elapsed:.2f}s")
                    
                    authorship_start = time.time()
                    final_data = self._add_unified_authorship_info(formatted_data, session)
                    authorship_elapsed = time.time() - authorship_start
                    if authorship_elapsed > 1.0:
                        logger.debug(f"_add_unified_authorship_info levou {authorship_elapsed:.2f}s para {len(formatted_data)} resultados")
                    
                    # Calcular estatísticas apenas se solicitado (carregamento sob demanda)
                    stats = {}
                    stats_by_author = {}
                    if calcular_estatisticas:
                        # Obter parâmetros de filtro de autoria
                        cod_autor = self._parse_int_param('cod_autor')
                        chk_coautor = self.request.get('chk_coautor') == '1'
                        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
                        autor_filtrado = None
                        if cod_autor is not None:
                            autor_filtrado = self._get_autor_name_by_cod(cod_autor, session)
                        
                        # Calcular estatísticas por tipo, respeitando os filtros de autoria
                        for item in final_data:
                            # Verificar se o item deve ser incluído baseado nos filtros de autoria
                            autores_str = item.get('autores', '')
                            if autores_str:
                                autores_list = [a.strip() for a in autores_str.split(',') if a.strip()]
                                
                                # Se há filtro de autor específico, verificar se deve incluir
                                if autor_filtrado:
                                    if autor_filtrado not in autores_list:
                                        continue  # Pular se o autor filtrado não está na lista
                                    # Verificar filtros de coautor/1º autor
                                    if chk_coautor:
                                        # Apenas coautor: o autor filtrado não deve ser o primeiro
                                        if autores_list[0] == autor_filtrado:
                                            continue  # Pular se o autor filtrado é o primeiro autor
                                    elif chk_primeiro_autor:
                                        # Apenas 1º autor: o autor filtrado deve ser o primeiro
                                        if autores_list[0] != autor_filtrado:
                                            continue  # Pular se o autor filtrado não é o primeiro autor
                                elif chk_coautor:
                                    # Sem autor específico, mas com filtro "apenas como coautor"
                                    # Considerar apenas itens onde há coautores (mais de 1 autor)
                                    if len(autores_list) <= 1:
                                        continue  # Pular se não há coautores (apenas 1 autor)
                            
                            # Incluir o item nas estatísticas
                            tipo_item = item.get('tipo_item', '')
                            if tipo_item == 'emenda':
                                # Agrupar todas as emendas independente do tipo
                                stats['Emenda'] = stats.get('Emenda', 0) + 1
                            elif tipo_item == 'substitutivo':
                                # Agrupar todos os substitutivos independente do tipo
                                stats['Substitutivo'] = stats.get('Substitutivo', 0) + 1
                            else:
                                # Para outros tipos, usar des_tipo_materia
                                tipo_materia = item.get('des_tipo_materia', '')
                                if tipo_materia:
                                    stats[tipo_materia] = stats.get(tipo_materia, 0) + 1
                        # Ordenar estatísticas por quantidade (decrescente)
                        stats = dict(sorted(stats.items(), key=lambda x: (-x[1], x[0])))
                        # Calcular estatísticas por autor
                        stats_by_author = self._calculate_stats_by_author(final_data, autor_filtrado, chk_coautor, chk_primeiro_autor)
                else:
                    # Unificar múltiplas queries
                    query_unificada = union_all(*queries_para_unir).alias('materias_unificadas')
                    query = session.query(
                        query_unificada.c.cod_item,
                        query_unificada.c.tipo_item,
                        query_unificada.c.cod_materia_principal,
                        query_unificada.c.des_tipo_materia,
                        query_unificada.c.num_ident_basica,
                        query_unificada.c.ano_ident_basica,
                        query_unificada.c.txt_ementa,
                        query_unificada.c.dat_apresentacao,
                        query_unificada.c.num_protocolo,
                        query_unificada.c.cod_materia,
                        query_unificada.c.sgl_tipo_materia,
                        query_unificada.c.cod_emenda,
                        query_unificada.c.cod_substitutivo,
                        query_unificada.c.tip_emenda,
                        query_unificada.c.des_tipo_emenda,
                        query_unificada.c.num_emenda,
                        query_unificada.c.num_substitutivo
                    )
                    # Aplicar ordenação
                    ordem = self.request.get('rd_ordem', '1')
                    if ordem == '0':
                        query = query.order_by(asc(query_unificada.c.dat_apresentacao))
                    else:
                        query = query.order_by(desc(query_unificada.c.dat_apresentacao))
                    
                    # Calcular total_count de forma eficiente usando COUNT
                    count_start = time.time()
                    total_count_query = session.query(func.count(query_unificada.c.cod_item.distinct()))
                    total_count = total_count_query.scalar() or 0
                    count_elapsed = time.time() - count_start
                    if count_elapsed > 2.0:
                        logger.warning(f"COUNT query levou {count_elapsed:.2f}s, total_count={total_count} (lento - considere aplicar índices)")
                    elif count_elapsed > 1.0:
                        logger.debug(f"COUNT query levou {count_elapsed:.2f}s, total_count={total_count}")
                    
                    # Calcular estatísticas apenas se solicitado (carregamento sob demanda)
                    stats = {}
                    stats_by_author = {}
                    if calcular_estatisticas:
                        # Otimização: usar amostragem para grandes volumes (limite de 5k registros)
                        # Isso evita carregar todos os resultados em memória e timeout
                        # Reduzido para 5k para melhorar performance quando não há índices
                        start_time = time.time()
                        total_count_for_stats = total_count
                        max_sample_size = 5000  # Limite máximo de amostra para estatísticas (reduzido para melhor performance)
                        
                        if total_count_for_stats > max_sample_size:
                            logger.info(f"Estatísticas: usando amostragem de {max_sample_size} registros de {total_count_for_stats} totais")
                            query_stats_start = time.time()
                            stats_query_sample = query.limit(max_sample_size).all()
                            query_stats_elapsed = time.time() - query_stats_start
                            if query_stats_elapsed > 1.0:
                                logger.debug(f"Query de estatísticas levou {query_stats_elapsed:.2f}s para {len(stats_query_sample)} resultados")
                        else:
                            query_stats_start = time.time()
                            stats_query_sample = query.all()
                            query_stats_elapsed = time.time() - query_stats_start
                            if query_stats_elapsed > 1.0:
                                logger.debug(f"Query de estatísticas levou {query_stats_elapsed:.2f}s para {len(stats_query_sample)} resultados")
                        
                        format_stats_start = time.time()
                        formatted_stats = self._format_unified_results(stats_query_sample, session)
                        format_stats_elapsed = time.time() - format_stats_start
                        if format_stats_elapsed > 1.0:
                            logger.debug(f"Formatação de estatísticas levou {format_stats_elapsed:.2f}s para {len(formatted_stats)} resultados")
                        
                        # Obter parâmetros de filtro de autoria ANTES de processar autoria
                        # Isso permite ajustar o limite de processamento baseado no filtro
                        cod_autor = self._parse_int_param('cod_autor')
                        chk_coautor = self.request.get('chk_coautor') == '1'
                        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
                        autor_filtrado = None
                        if cod_autor is not None:
                            autor_filtrado = self._get_autor_name_by_cod(cod_autor, session)
                        
                        # Otimização adicional: para estatísticas, limitar processamento de autoria
                        # Não precisamos de todos os autores para estatísticas, apenas uma amostra
                        # IMPORTANTE: Quando há autor filtrado, precisamos processar TODOS os itens da amostra
                        # para garantir que o gráfico por autor mostre o total correto
                        authorship_stats_start = time.time()
                        # Se há autor filtrado, processar todos os itens da amostra (sem limite adicional)
                        # Caso contrário, limitar a 3000 para melhorar performance
                        max_authorship_for_stats = None if autor_filtrado else 3000
                        final_stats = self._add_unified_authorship_info(formatted_stats, session, max_results=max_authorship_for_stats)
                        authorship_stats_elapsed = time.time() - authorship_stats_start
                        if authorship_stats_elapsed > 1.0:
                            logger.debug(f"Autoria de estatísticas levou {authorship_stats_elapsed:.2f}s para {len(formatted_stats)} resultados")
                        
                        elapsed_stats = time.time() - start_time
                        if elapsed_stats > 2.0:
                            logger.warning(f"Estatísticas levaram {elapsed_stats:.2f}s para processar (query={query_stats_elapsed:.2f}s, format={format_stats_elapsed:.2f}s, autoria={authorship_stats_elapsed:.2f}s)")
                        
                        # Calcular estatísticas por tipo, respeitando os filtros de autoria
                        # Obter parâmetros de filtro de autoria
                        cod_autor = self._parse_int_param('cod_autor')
                        chk_coautor = self.request.get('chk_coautor') == '1'
                        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
                        autor_filtrado = None
                        if cod_autor is not None:
                            autor_filtrado = self._get_autor_name_by_cod(cod_autor, session)
                        
                        # Calcular estatísticas a partir dos resultados, respeitando filtros de autoria
                        for item in final_stats:
                            # Verificar se o item deve ser incluído baseado nos filtros de autoria
                            autores_str = item.get('autores', '')
                            if autores_str:
                                autores_list = [a.strip() for a in autores_str.split(',') if a.strip()]
                                
                                # Se há filtro de autor específico, verificar se deve incluir
                                if autor_filtrado:
                                    if autor_filtrado not in autores_list:
                                        continue  # Pular se o autor filtrado não está na lista
                                    # Verificar filtros de coautor/1º autor
                                    if chk_coautor:
                                        # Apenas coautor: o autor filtrado não deve ser o primeiro
                                        if autores_list[0] == autor_filtrado:
                                            continue  # Pular se o autor filtrado é o primeiro autor
                                    elif chk_primeiro_autor:
                                        # Apenas 1º autor: o autor filtrado deve ser o primeiro
                                        if autores_list[0] != autor_filtrado:
                                            continue  # Pular se o autor filtrado não é o primeiro autor
                                elif chk_coautor or chk_primeiro_autor:
                                    # Sem autor específico, mas com filtro de coautor/1º autor
                                    # Se "apenas como coautor", considerar apenas itens onde há coautores
                                    if chk_coautor:
                                        if len(autores_list) <= 1:
                                            continue  # Pular se não há coautores (apenas 1 autor)
                                    # Se "apenas como 1º autor", considerar apenas o primeiro autor
                                    # Mas para estatísticas por tipo, isso não afeta (todos os itens têm primeiro autor)
                                    # Então não precisa filtrar aqui
                            
                            # Incluir o item nas estatísticas
                            tipo_item = item.get('tipo_item', '')
                            if tipo_item == 'emenda':
                                # Agrupar todas as emendas independente do tipo
                                stats['Emenda'] = stats.get('Emenda', 0) + 1
                            elif tipo_item == 'substitutivo':
                                # Agrupar todos os substitutivos independente do tipo
                                stats['Substitutivo'] = stats.get('Substitutivo', 0) + 1
                            else:
                                # Para outros tipos, usar des_tipo_materia
                                tipo_materia = item.get('des_tipo_materia', '')
                                if tipo_materia:
                                    stats[tipo_materia] = stats.get(tipo_materia, 0) + 1
                        # Ordenar estatísticas por quantidade (decrescente)
                        stats = dict(sorted(stats.items(), key=lambda x: (-x[1], x[0])))
                        # Calcular estatísticas por autor a partir da amostra
                        # autor_filtrado, chk_coautor e chk_primeiro_autor já foram obtidos acima
                        stats_author_start = time.time()
                        stats_by_author = self._calculate_stats_by_author(final_stats, autor_filtrado, chk_coautor, chk_primeiro_autor)
                        stats_author_elapsed = time.time() - stats_author_start
                        if stats_author_elapsed > 1.0:
                            logger.debug(f"Cálculo de estatísticas por autor levou {stats_author_elapsed:.2f}s para {len(final_stats)} resultados")
                    
                    # Aplicar paginação na query SQL antes de executar
                    page = self._parse_int_param('pagina', 1)
                    page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
                    page = min(page, total_pages) if total_pages > 0 else 1
                    offset = (page - 1) * page_size
                    
                    # Executar query com LIMIT e OFFSET para a página atual
                    query_start = time.time()
                    results_raw = query.offset(offset).limit(page_size).all()
                    query_elapsed = time.time() - query_start
                    if query_elapsed > 1.0:
                        logger.debug(f"Query paginada levou {query_elapsed:.2f}s para {len(results_raw)} resultados (offset={offset}, limit={page_size})")
                    
                    format_start = time.time()
                    formatted_data = self._format_unified_results(results_raw, session)
                    format_elapsed = time.time() - format_start
                    if format_elapsed > 1.0:
                        logger.debug(f"_format_unified_results levou {format_elapsed:.2f}s")
                    
                    authorship_start = time.time()
                    final_data = self._add_unified_authorship_info(formatted_data, session)
                    authorship_elapsed = time.time() - authorship_start
                    if authorship_elapsed > 1.0:
                        logger.debug(f"_add_unified_authorship_info levou {authorship_elapsed:.2f}s para {len(formatted_data)} resultados")
            elif scope['pesquisa_acessoria'] and scope['pesquisa_principal']:
                # Todas (principais + acessórias) - usar UNION
                query_principal = self._build_base_query_for_filters(session)
                # Filtrar por tipos principais se especificado
                if scope['tipos_principais']:
                    query_principal = query_principal.filter(MateriaLegislativa.tip_id_basica.in_(scope['tipos_principais']))
                query_principal = self._apply_all_filters(query_principal, session)
                query_acessoria = self._build_unified_acessoria_query(session)
                # Filtrar por tipos acessórios se especificado
                if scope['tipos_acessorios']:
                    # Isso requer uma abordagem mais complexa, vamos filtrar depois
                    pass
                # Combinar resultados
                results_principal = query_principal.all()
                results_acessoria = query_acessoria.all()
                total_count = len(results_principal) + len(results_acessoria)
                formatted_principal = self._format_results(results_principal)
                formatted_acessoria = self._format_unified_results(results_acessoria, session)
                final_data_principal = self._add_authorship_info(formatted_principal)
                final_data_acessoria = self._add_unified_authorship_info(formatted_acessoria, session)
                final_data = final_data_principal + final_data_acessoria
                stats_query = query_principal.with_entities(
                    TipoMateriaLegislativa.des_tipo_materia,
                    func.count(MateriaLegislativa.cod_materia.distinct())
                ).group_by(
                    TipoMateriaLegislativa.des_tipo_materia
                ).order_by(
                    desc(func.count(MateriaLegislativa.cod_materia.distinct()))
                )
                # Calcular estatísticas apenas se solicitado (carregamento sob demanda)
                stats = {}
                stats_by_author = {}
                if calcular_estatisticas:
                    stats_results = stats_query.all()
                    stats = {tipo: contagem for tipo, contagem in stats_results}
                    # Calcular estatísticas por autor
                    # Se há filtro por autor, considerar apenas esse autor no gráfico
                    cod_autor = self._parse_int_param('cod_autor')
                    chk_coautor = self.request.get('chk_coautor') == '1'
                    chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
                    autor_filtrado = None
                    if cod_autor is not None:
                        autor_filtrado = self._get_autor_name_by_cod(cod_autor, session)
                    stats_by_author = self._calculate_stats_by_author(final_data, autor_filtrado, chk_coautor, chk_primeiro_autor)
            else:
                # Apenas matérias principais (ou principais + emendas + substitutivos se nenhum tipo selecionado)
                # Se emendas ou substitutivos devem ser incluídos (quando nenhum tipo selecionado)
                if scope['pesquisa_emenda'] or scope['pesquisa_substitutivo']:
                    # Construir query de matérias principais compatível com UNION
                    mtool = getToolByName(self.context, 'portal_membership')
                    query_principal = session.query(
                        MateriaLegislativa.cod_materia.label('cod_item'),
                        literal_column("CAST('principal' AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('tipo_item'),
                        MateriaLegislativa.cod_materia.label('cod_materia_principal'),
                        literal_column("CAST(tipo_materia_legislativa.des_tipo_materia AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('des_tipo_materia'),
                        MateriaLegislativa.num_ident_basica.label('num_ident_basica'),
                        MateriaLegislativa.ano_ident_basica.label('ano_ident_basica'),
                        literal_column("CAST(COALESCE(materia_legislativa.txt_ementa, '') AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('txt_ementa'),
                        MateriaLegislativa.dat_apresentacao.label('dat_apresentacao'),
                        MateriaLegislativa.num_protocolo.label('num_protocolo'),
                        MateriaLegislativa.cod_materia.label('cod_materia'),
                        literal_column("CAST(COALESCE(tipo_materia_legislativa.sgl_tipo_materia, '') AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('sgl_tipo_materia'),
                        cast(None, Integer).label('cod_emenda'),
                        cast(None, Integer).label('cod_substitutivo'),
                        cast(None, Integer).label('tip_emenda'),
                        literal_column("CAST(NULL AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci").label('des_tipo_emenda'),
                        cast(None, Integer).label('num_emenda'),
                        cast(None, Integer).label('num_substitutivo')
                    ).join(
                        TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
                    ).filter(
                        MateriaLegislativa.ind_excluido == 0,
                        TipoMateriaLegislativa.tip_natureza == 'P'  # Apenas principais
                    )
                    if mtool.isAnonymousUser():
                        query_principal = query_principal.filter(TipoMateriaLegislativa.ind_publico == 1)
                    
                    # Aplicar filtros
                    query_principal = self._apply_all_filters_to_unified_query(query_principal, session)
                    
                    queries_para_unir = [query_principal]
                    
                    # Adicionar query de emendas se solicitado
                    if scope['pesquisa_emenda']:
                        query_emenda = self._build_emenda_query(session)
                        query_emenda = self._apply_filters_to_emenda_query(query_emenda, session)
                        queries_para_unir.append(query_emenda)
                    
                    # Adicionar query de substitutivos se solicitado
                    if scope['pesquisa_substitutivo']:
                        query_substitutivo = self._build_substitutivo_query(session)
                        query_substitutivo = self._apply_filters_to_substitutivo_query(query_substitutivo, session)
                        queries_para_unir.append(query_substitutivo)
                    
                    # Unificar múltiplas queries
                    query_unificada = union_all(*queries_para_unir).alias('materias_unificadas')
                    query = session.query(
                        query_unificada.c.cod_item,
                        query_unificada.c.tipo_item,
                        query_unificada.c.cod_materia_principal,
                        query_unificada.c.des_tipo_materia,
                        query_unificada.c.num_ident_basica,
                        query_unificada.c.ano_ident_basica,
                        query_unificada.c.txt_ementa,
                        query_unificada.c.dat_apresentacao,
                        query_unificada.c.num_protocolo,
                        query_unificada.c.cod_materia,
                        query_unificada.c.sgl_tipo_materia,
                        query_unificada.c.cod_emenda,
                        query_unificada.c.cod_substitutivo,
                        query_unificada.c.tip_emenda,
                        query_unificada.c.des_tipo_emenda,
                        query_unificada.c.num_emenda,
                        query_unificada.c.num_substitutivo
                    )
                    # Aplicar ordenação
                    ordem = self.request.get('rd_ordem', '1')
                    if ordem == '0':
                        query = query.order_by(asc(query_unificada.c.dat_apresentacao))
                    else:
                        query = query.order_by(desc(query_unificada.c.dat_apresentacao))
                    
                    # Calcular total_count de forma eficiente usando COUNT
                    count_start = time.time()
                    total_count_query = session.query(func.count(query_unificada.c.cod_item.distinct()))
                    total_count = total_count_query.scalar() or 0
                    count_elapsed = time.time() - count_start
                    if count_elapsed > 2.0:
                        logger.warning(f"COUNT query levou {count_elapsed:.2f}s, total_count={total_count} (lento - considere aplicar índices)")
                    elif count_elapsed > 1.0:
                        logger.debug(f"COUNT query levou {count_elapsed:.2f}s, total_count={total_count}")
                    
                    # Calcular estatísticas apenas se solicitado (carregamento sob demanda)
                    stats = {}
                    stats_by_author = {}
                    if calcular_estatisticas:
                        # Para performance, sempre usar queries agregadas para estatísticas por tipo
                        # e amostra limitada para estatísticas por autor
                        
                        # Estatísticas de matérias principais usando query agregada (mais eficiente)
                        stats_query_principal = session.query(
                            TipoMateriaLegislativa.des_tipo_materia,
                            func.count(MateriaLegislativa.cod_materia.distinct())
                        ).join(
                            TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
                        ).filter(
                            MateriaLegislativa.ind_excluido == 0,
                            TipoMateriaLegislativa.tip_natureza == 'P'
                        )
                        if mtool.isAnonymousUser():
                            stats_query_principal = stats_query_principal.filter(TipoMateriaLegislativa.ind_publico == 1)
                        stats_query_principal = self._apply_all_filters_to_unified_query(stats_query_principal, session)
                        stats_query_principal = stats_query_principal.group_by(TipoMateriaLegislativa.des_tipo_materia)
                        stats_principal = stats_query_principal.all()
                        for tipo, count in stats_principal:
                            if tipo:
                                stats[tipo] = count
                        
                        # Contar emendas
                        if scope['pesquisa_emenda']:
                            query_emenda_count = self._build_emenda_query(session)
                            query_emenda_count = self._apply_filters_to_emenda_query(query_emenda_count, session)
                            # Usar subquery para contar
                            emenda_subq = query_emenda_count.subquery()
                            count_emendas = session.query(func.count(emenda_subq.c.cod_item.distinct())).scalar() or 0
                            if count_emendas > 0:
                                stats['Emenda'] = count_emendas
                        
                        # Contar substitutivos
                        if scope['pesquisa_substitutivo']:
                            query_subst_count = self._build_substitutivo_query(session)
                            query_subst_count = self._apply_filters_to_substitutivo_query(query_subst_count, session)
                            # Usar subquery para contar
                            subst_subq = query_subst_count.subquery()
                            count_subst = session.query(func.count(subst_subq.c.cod_item.distinct())).scalar() or 0
                            if count_subst > 0:
                                stats['Substitutivo'] = count_subst
                        
                        # Calcular estatísticas por autor - usar amostragem para grandes volumes
                        # IMPORTANTE: Usar a mesma ordenação que será aplicada aos resultados da pesquisa
                        # A query unificada já tem ordenação, mas vamos garantir consistência
                        # Otimização: usar amostragem para grandes volumes (limite de 10k registros)
                        total_count_for_stats = total_count
                        max_sample_size = 5000  # Limite máximo de amostra para estatísticas (reduzido para melhor performance)
                        
                        if total_count_for_stats > max_sample_size:
                            logger.info(f"Estatísticas: usando amostragem de {max_sample_size} registros de {total_count_for_stats} totais")
                            stats_query_sample = query.limit(max_sample_size).all()
                        else:
                            stats_query_sample = query.all()
                        
                        formatted_stats = self._format_unified_results(stats_query_sample, session)
                        # Limitar autoria para estatísticas (não precisamos de todos os autores)
                        final_stats = self._add_unified_authorship_info(formatted_stats, session, max_results=5000)
                        # Se há filtro por autor, considerar apenas esse autor no gráfico
                        cod_autor = self._parse_int_param('cod_autor')
                        chk_coautor = self.request.get('chk_coautor') == '1'
                        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
                        autor_filtrado = None
                        if cod_autor is not None:
                            autor_filtrado = self._get_autor_name_by_cod(cod_autor, session)
                        stats_by_author = self._calculate_stats_by_author(final_stats, autor_filtrado, chk_coautor, chk_primeiro_autor)
                        
                        # Ordenar estatísticas por quantidade (decrescente)
                        stats = dict(sorted(stats.items(), key=lambda x: (-x[1], x[0])))
                    
                    # Aplicar paginação na query SQL antes de executar
                    page = self._parse_int_param('pagina', 1)
                    page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
                    page = min(page, total_pages) if total_pages > 0 else 1
                    offset = (page - 1) * page_size
                    
                    # Executar query com LIMIT e OFFSET para a página atual
                    query_start = time.time()
                    results_raw = query.offset(offset).limit(page_size).all()
                    query_elapsed = time.time() - query_start
                    if query_elapsed > 1.0:
                        logger.debug(f"Query paginada levou {query_elapsed:.2f}s para {len(results_raw)} resultados (offset={offset}, limit={page_size})")
                    
                    format_start = time.time()
                    formatted_data = self._format_unified_results(results_raw, session)
                    format_elapsed = time.time() - format_start
                    if format_elapsed > 1.0:
                        logger.debug(f"_format_unified_results levou {format_elapsed:.2f}s")
                    
                    authorship_start = time.time()
                    final_data = self._add_unified_authorship_info(formatted_data, session)
                    authorship_elapsed = time.time() - authorship_start
                    if authorship_elapsed > 1.0:
                        logger.debug(f"_add_unified_authorship_info levou {authorship_elapsed:.2f}s para {len(formatted_data)} resultados")
                    
                    ordered_query = None  # Já processado, não precisa paginar novamente
                else:
                    # Apenas matérias principais (comportamento padrão quando tipos são selecionados)
                    query = self._build_base_query_for_filters(session)
                    # Filtrar por tipos principais se especificado
                    if scope['tipos_principais']:
                        query = query.filter(MateriaLegislativa.tip_id_basica.in_(scope['tipos_principais']))
                    query = self._apply_all_filters(query, session)
                    
                    # Clonar a query para contagem e estatísticas antes de ordenar/paginar
                    stats_query_base = query

                    # 1. Obter a contagem total de forma eficiente
                    # O .distinct() é importante se os joins causarem duplicatas
                    total_count_query = stats_query_base.with_entities(func.count(MateriaLegislativa.cod_materia.distinct()))
                    total_count = total_count_query.scalar()

                    # 2. Obter as estatísticas por tipo
                    stats_query = stats_query_base.with_entities(
                        TipoMateriaLegislativa.des_tipo_materia,
                        func.count(MateriaLegislativa.cod_materia.distinct())
                    ).group_by(
                        TipoMateriaLegislativa.des_tipo_materia
                    ).order_by(
                        desc(func.count(MateriaLegislativa.cod_materia.distinct()))
                    )
                    # Calcular estatísticas apenas se solicitado (carregamento sob demanda)
                    stats = {}
                    stats_by_author = {}
                    if calcular_estatisticas:
                        stats_results = stats_query.all()
                        stats = {tipo: contagem for tipo, contagem in stats_results}
                        # Ordenar estatísticas por quantidade (decrescente)
                        stats = dict(sorted(stats.items(), key=lambda x: (-x[1], x[0])))
                        # Calcular estatísticas por autor usando TODOS os resultados
                        # Como é carregamento sob demanda, não há necessidade de amostragem
                        # IMPORTANTE: Usar a mesma ordenação que será aplicada aos resultados da pesquisa
                        stats_query_ordered = self._apply_ordering(query, session)
                        stats_autor_query = stats_query_ordered.all()
                        formatted_stats_autor = self._format_results(stats_autor_query)
                        final_stats_autor = self._add_authorship_info(formatted_stats_autor)
                        # Se há filtro por autor, considerar apenas esse autor no gráfico
                        cod_autor = self._parse_int_param('cod_autor')
                        chk_coautor = self.request.get('chk_coautor') == '1'
                        chk_primeiro_autor = self.request.get('chk_primeiro_autor') == '1'
                        autor_filtrado = None
                        if cod_autor is not None:
                            autor_filtrado = self._get_autor_name_by_cod(cod_autor, session)
                        stats_by_author = self._calculate_stats_by_author(final_stats_autor, autor_filtrado, chk_coautor, chk_primeiro_autor)

                    # Aplicar ordenação para a consulta final paginada/exportada
                    ordered_query = self._apply_ordering(query, session)
            formato = self.request.get('formato', '').lower()
            if formato in ('csv', 'excel', 'pdf'):
                is_anonymous = getToolByName(self.context, 'portal_membership').isAnonymousUser()
                paginar_exportacao = self.request.get('paginar_exportacao') == '1'
                if scope['pesquisa_acessoria'] and not scope['pesquisa_principal']:
                    # Para matérias acessórias, usar resultados já formatados
                    if paginar_exportacao:
                        page = self._parse_int_param('pagina', 1)
                        page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                        offset = (page - 1) * page_size
                        results_for_export = final_data[offset:offset + page_size]
                    else:
                        results_for_export = final_data
                        MAX_ANON_EXPORT = 300
                        if is_anonymous and len(results_for_export) > MAX_ANON_EXPORT:
                            self.request.response.setStatus(403)
                            return json.dumps({
                                'error': f'Exportação muito grande. O limite é de {MAX_ANON_EXPORT} linhas.',
                                'details': 'Use mais filtros ou autentique-se para exportar todos os resultados.'
                            })
                    # Converter para formato compatível com exportação
                    results_raw_for_export = [r for r in results_for_export]
                elif scope['pesquisa_acessoria'] and scope['pesquisa_principal']:
                    # Para todas, usar resultados já formatados
                    if paginar_exportacao:
                        page = self._parse_int_param('pagina', 1)
                        page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                        offset = (page - 1) * page_size
                        results_for_export = final_data[offset:offset + page_size]
                    else:
                        results_for_export = final_data
                        MAX_ANON_EXPORT = 300
                        if is_anonymous and len(results_for_export) > MAX_ANON_EXPORT:
                            self.request.response.setStatus(403)
                            return json.dumps({
                                'error': f'Exportação muito grande. O limite é de {MAX_ANON_EXPORT} linhas.',
                                'details': 'Use mais filtros ou autentique-se para exportar todos os resultados.'
                            })
                    results_raw_for_export = [r for r in results_for_export]
                else:
                    # Para matérias principais, usar query normal ou final_data se ordered_query for None
                    if ordered_query is None:
                        # Query unificada já foi processada, usar final_data
                        if paginar_exportacao:
                            page = self._parse_int_param('pagina', 1)
                            page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                            offset = (page - 1) * page_size
                            results_for_export = final_data[offset:offset + page_size] if final_data else []
                        else:
                            results_for_export = final_data if final_data else []
                            MAX_ANON_EXPORT = 300
                            if is_anonymous and len(results_for_export) > MAX_ANON_EXPORT:
                                self.request.response.setStatus(403)
                                return json.dumps({
                                    'error': f'Exportação muito grande. O limite é de {MAX_ANON_EXPORT} linhas.',
                                    'details': 'Use mais filtros ou autentique-se para exportar todos os resultados.'
                                })
                        results_raw_for_export = [r for r in results_for_export]
                    else:
                        # Usar query normal
                        if paginar_exportacao:
                            page = self._parse_int_param('pagina', 1)
                            page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                            offset = (page - 1) * page_size
                            results_raw_for_export = ordered_query.offset(offset).limit(page_size).all()
                        else:
                            results_raw_for_export = ordered_query.all()
                            MAX_ANON_EXPORT = 300
                            if is_anonymous and len(results_raw_for_export) > MAX_ANON_EXPORT:
                                self.request.response.setStatus(403)
                                return json.dumps({
                                    'error': f'Exportação muito grande. O limite é de {MAX_ANON_EXPORT} linhas.',
                                    'details': 'Use mais filtros ou autentique-se para exportar todos os resultados.'
                                })
                
                # Determinar se deve usar exportação unificada
                # Usar unificada se: pesquisa_acessoria=True OU ordered_query=None (query unificada já processada)
                usar_exportacao_unificada = scope['pesquisa_acessoria'] or ordered_query is None
                
                if formato == 'csv': 
                    if usar_exportacao_unificada:
                        return self._export_csv_unified(results_raw_for_export)
                    return self._export_csv(results_raw_for_export)
                if formato == 'excel': 
                    if usar_exportacao_unificada:
                        return self._export_excel_unified(results_raw_for_export)
                    return self._export_excel(results_raw_for_export)
                if formato == 'pdf': 
                    if usar_exportacao_unificada:
                        return self._export_pdf_unified(results_raw_for_export)
                    return self._export_pdf(results_raw_for_export)

            # Paginação para JSON
            # Casos que usam resultados já formatados (acessórias, emendas, substitutivos, ou todas)
            if (scope['pesquisa_acessoria'] or scope['pesquisa_emenda'] or scope['pesquisa_substitutivo']):
                # Se ordered_query é None, significa que a paginação já foi aplicada na query SQL
                # e final_data já contém apenas os resultados da página atual
                if ordered_query is None:
                    # Paginação já foi aplicada na query SQL, usar final_data diretamente
                    data = {
                        'data': final_data, 'total': total_count, 'page': page,
                        'per_page': page_size, 'total_pages': total_pages,
                        'has_previous': page > 1, 'has_next': page < total_pages,
                        'stats': stats,
                        'stats_by_author': stats_by_author if 'stats_by_author' in locals() else {}
                    }
                else:
                    # Paginar resultados já formatados (caso antigo, para compatibilidade)
                    page = self._parse_int_param('pagina', 1)
                    page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
                    page = min(page, total_pages) if total_pages > 0 else 1
                    offset = (page - 1) * page_size
                    paginated_data = final_data[offset:offset + page_size]
                    data = {
                        'data': paginated_data, 'total': total_count, 'page': page,
                        'per_page': page_size, 'total_pages': total_pages,
                        'has_previous': page > 1, 'has_next': page < total_pages,
                        'stats': stats,
                        'stats_by_author': stats_by_author if 'stats_by_author' in locals() else {}
                    }
            else:
                # Apenas matérias principais - usar ordered_query
                if ordered_query is None:
                    # Se ordered_query não foi definido, significa que a query unificada já foi processada
                    # Usar final_data para paginação
                    page = self._parse_int_param('pagina', 1)
                    page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
                    page = min(page, total_pages) if total_pages > 0 else 1
                    offset = (page - 1) * page_size
                    paginated_data = final_data[offset:offset + page_size] if final_data else []
                    
                    data = {
                        'data': paginated_data,
                        'total': total_count,
                        'page': page,
                        'per_page': page_size,
                        'total_pages': total_pages,
                        'has_previous': page > 1,
                        'has_next': page < total_pages,
                        'stats': stats,
                        'stats_by_author': stats_by_author if 'stats_by_author' in locals() else {}
                    }
                else:
                    page = self._parse_int_param('pagina', 1)
                    page_size = min(max(self._parse_int_param('itens_por_pagina', 12), 1), 100)
                    data = self._paginate_and_respond(ordered_query, page, page_size, total_count)
                    data['stats'] = stats
                    # stats_by_author já foi calculado acima a partir de todos os resultados
                    data['stats_by_author'] = stats_by_author if 'stats_by_author' in locals() else {}
            
            self.request.response.setHeader('Content-Type', 'application/json')
            
            # Monitoramento de performance detalhado
            elapsed_total = time.time() - render_start_time
            total_count_str = str(total_count) if 'total_count' in locals() else 'N/A'
            calcular_estatisticas_str = str(calcular_estatisticas) if 'calcular_estatisticas' in locals() else 'N/A'
            
            if elapsed_total > 5.0:
                logger.warning(f"Pesquisa completa levou {elapsed_total:.2f}s (lenta) - total_count={total_count_str}, calcular_estatisticas={calcular_estatisticas_str}")
            elif elapsed_total > 2.0:
                logger.info(f"Pesquisa levou {elapsed_total:.2f}s - total_count={total_count_str}, calcular_estatisticas={calcular_estatisticas_str}")
            
            return json.dumps(data)

        except Exception as e:
            logger.error(f"Erro em MateriaLegislativaView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro interno ao processar a requisição', 'details': str(e)})
        finally:
            session.close()

# ... (Restante das classes de View mantido como estava) ...
# =================================================================== #
# ENDPOINT DE TRAMITAÇÃO (NOVO)
# =================================================================== #

class TramitacaoMateriaView(grok.View):
    """Retorna o histórico de tramitação de uma matéria em formato JSON."""
    grok.context(Interface)
    grok.name('tramitacao_materia_json')
    grok.require('zope2.View')

    def _get_nome_unidade_expr(self, alias_unidade, alias_comissao, alias_orgao, alias_parlamentar):
        """Constrói a expressão CASE para obter o nome da unidade de tramitação."""
        return case(
            (alias_unidade.cod_comissao != None, alias_comissao.nom_comissao),
            (alias_unidade.cod_orgao != None, alias_orgao.nom_orgao),
            (alias_unidade.cod_parlamentar != None, alias_parlamentar.nom_parlamentar),
            else_=''
        )

    def render(self):
        session = Session()
        try:
            cod_materia = self.request.get('cod_materia')
            if not cod_materia or not cod_materia.isdigit():
                self.request.response.setStatus(400)
                return json.dumps({'error': 'Parâmetro `cod_materia` inválido ou ausente.'})

            cod_materia = int(cod_materia)

            # Aliases para joins múltiplos na mesma tabela
            UT_Origem = aliased(UnidadeTramitacao, name='ut_origem')
            Comissao_Origem = aliased(Comissao, name='com_origem')
            Orgao_Origem = aliased(Orgao, name='org_origem')
            Parlamentar_Origem = aliased(Parlamentar, name='par_origem')

            UT_Destino = aliased(UnidadeTramitacao, name='ut_destino')
            Comissao_Destino = aliased(Comissao, name='com_destino')
            Orgao_Destino = aliased(Orgao, name='org_destino')
            Parlamentar_Destino = aliased(Parlamentar, name='par_destino')

            # Expressões CASE para nomes de origem e destino
            nome_origem_expr = self._get_nome_unidade_expr(
                UT_Origem, Comissao_Origem, Orgao_Origem, Parlamentar_Origem
            ).label('nome_origem')
            nome_destino_expr = self._get_nome_unidade_expr(
                UT_Destino, Comissao_Destino, Orgao_Destino, Parlamentar_Destino
            ).label('nome_destino')

            # Construção da Query
            query = session.query(
                Tramitacao.dat_tramitacao,
                nome_origem_expr,
                nome_destino_expr,
                StatusTramitacao.des_status,
                Tramitacao.ind_ult_tramitacao
            ).outerjoin(UT_Origem, Tramitacao.cod_unid_tram_local == UT_Origem.cod_unid_tramitacao)\
             .outerjoin(Comissao_Origem, UT_Origem.cod_comissao == Comissao_Origem.cod_comissao)\
             .outerjoin(Orgao_Origem, UT_Origem.cod_orgao == Orgao_Origem.cod_orgao)\
             .outerjoin(Parlamentar_Origem, UT_Origem.cod_parlamentar == Parlamentar_Origem.cod_parlamentar)\
             .outerjoin(UT_Destino, Tramitacao.cod_unid_tram_dest == UT_Destino.cod_unid_tramitacao)\
             .outerjoin(Comissao_Destino, UT_Destino.cod_comissao == Comissao_Destino.cod_comissao)\
             .outerjoin(Orgao_Destino, UT_Destino.cod_orgao == Orgao_Destino.cod_orgao)\
             .outerjoin(Parlamentar_Destino, UT_Destino.cod_parlamentar == Parlamentar_Destino.cod_parlamentar)\
             .join(StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status)\
             .filter(
                Tramitacao.cod_materia == cod_materia,
                Tramitacao.ind_excluido == 0
             ).order_by(
                desc(Tramitacao.dat_tramitacao),
                desc(Tramitacao.cod_tramitacao)
             )

            results = query.all()

            # Formatação do resultado para o frontend
            timeline = []
            for r in results:
                timeline.append({
                    "data": r.dat_tramitacao.strftime('%d/%m/%Y') if r.dat_tramitacao else '',
                    "unidade_origem": r.nome_origem or 'Não informado',
                    "unidade_destino": r.nome_destino or 'Não informado',
                    "status_tramitacao": f"{r.des_status}",
                    "passo_atual": r.ind_ult_tramitacao == 1
                })

            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(timeline)

        except Exception as e:
            logger.error(f"Erro em TramitacaoMateriaView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro interno ao buscar o histórico de tramitação.', 'details': str(e)})
        finally:
            session.close()

# =================================================================== #
# CLASSES DE APOIO PARA OS FILTROS (mantidas as originais)
# =================================================================== #

class TiposMateriaView(grok.View):
    grok.context(Interface)
    grok.name('tipos_materia_json')
    grok.require('zope2.View')

    def render(self):
        try:
            mtool = getToolByName(self.context, 'portal_membership')
            is_anonymous = mtool.isAnonymousUser()
            results = _get_tipos_materia_cached(is_anonymous, Session)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(results)
        except Exception as e:
            logger.error(f"Erro em TiposMateriaView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao buscar tipos de matéria', 'details': str(e)})

class AutoresView(grok.View):
    grok.context(Interface)
    grok.name('autores_json')
    grok.require('zope2.View')

    def render(self):
        try:
            results = _get_autores_cached(Session)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(results)
        except Exception as e:
            logger.error(f"Erro em AutoresView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao buscar autores', 'details': str(e)})

class UnidadesTramitacaoView(grok.View):
    grok.context(Interface)
    grok.name('unidades_tramitacao_json')
    grok.require('zope2.View')

    def render(self):
        try:
            results = _get_unidades_tramitacao_cached(Session)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(results)
        except Exception as e:
            logger.error(f"Erro em UnidadesTramitacaoView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao buscar unidades de tramitação', 'details': str(e)})

class StatusTramitacaoView(grok.View):
    grok.context(Interface)
    grok.name('status_tramitacao_json')
    grok.require('zope2.View')

    def render(self):
        try:
            results = _get_status_tramitacao_cached(Session)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(results)
        except Exception as e:
            logger.error(f"Erro em StatusTramitacaoView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao buscar status de tramitação', 'details': str(e)})

class TiposAutorView(grok.View):
    grok.context(Interface)
    grok.name('tipos_autor_json')
    grok.require('zope2.View')

    def render(self):
        try:
            results = _get_tipos_autor_cached(Session)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(results)
        except Exception as e:
            logger.error(f"Erro em TiposAutorView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao buscar tipos de autor', 'details': str(e)})

class RelatoresView(grok.View):
    grok.context(Interface)
    grok.name('relatores_json')
    grok.require('zope2.View')

    def render(self):
        try:
            results = _get_relatores_cached(Session)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(results)
        except Exception as e:
            logger.error(f"Erro em RelatoresView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao buscar relatores', 'details': str(e)})


class MateriaDetalheView(grok.View):
    """Endpoint detalhado para uma matéria legislativa."""
    grok.context(Interface)
    grok.name('materia_detalhe_json')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        try:
            cod_materia = self.request.get('cod_materia')
            if not cod_materia or not str(cod_materia).isdigit():
                self.request.response.setStatus(400)
                return json.dumps({'error': 'Parâmetro `cod_materia` inválido ou ausente.'})

            cod_materia = int(cod_materia)

            # ALIASES EXCLUSIVOS (SEM REPETIÇÃO)
            Materia = aliased(MateriaLegislativa, name='materia')
            TipoMat = aliased(TipoMateriaLegislativa, name='tipo_materia')
            Tram = aliased(Tramitacao, name='tram')
            StatTram = aliased(StatusTramitacao, name='stat_tram')
            UT_Dest = aliased(UnidadeTramitacao, name='ut_dest')
            Org_Dest = aliased(Orgao, name='org_dest')
            Com_Dest = aliased(Comissao, name='com_dest')
            Parl_Dest = aliased(Parlamentar, name='parl_dest')
            RegTram = aliased(RegimeTramitacao, name='reg_tram')
            QuorumVot = aliased(QuorumVotacao, name='quorum_vot')

            # 1. DADOS PRINCIPAIS + ÚLTIMA TRAMITAÇÃO + regime/quórum
            materia = session.query(
                Materia, TipoMat, Tram, StatTram, RegTram, QuorumVot
            ).\
                join(TipoMat, Materia.tip_id_basica == TipoMat.tip_materia).\
                outerjoin(
                    Tram, and_(
                        Materia.cod_materia == Tram.cod_materia,
                        Tram.ind_excluido == 0,
                        Tram.ind_ult_tramitacao == 1
                    )
                ).\
                outerjoin(StatTram, Tram.cod_status == StatTram.cod_status).\
                outerjoin(RegTram, Materia.cod_regime_tramitacao == RegTram.cod_regime_tramitacao).\
                outerjoin(QuorumVot, Materia.tip_quorum == QuorumVot.cod_quorum).\
                filter(Materia.cod_materia == cod_materia).\
                first()
            if not materia:
                self.request.response.setStatus(404)
                return json.dumps({'error': 'Matéria não encontrada.'})

            materia_obj, tipo_obj, tram_obj, stat_tram_obj, regime_obj, quorum_obj = materia

            # 2. AUTORES
            Autoria_aut = aliased(Autoria, name='autoria_aut')
            Autor_aut = aliased(Autor, name='autor_aut')
            TipoAutor_aut = aliased(TipoAutor, name='tipo_autor_aut')
            Parlamentar_aut_lj = aliased(Parlamentar, name='parlamentar_aut_lj')
            Comissao_aut_lj = aliased(Comissao, name='comissao_aut_lj')
            Bancada_aut_lj = aliased(Bancada, name='bancada_aut_lj')
            Legislatura_aut_lj = aliased(Legislatura, name='legislatura_aut_lj')

            autor_nome_expr = case(
                (TipoAutor_aut.des_tipo_autor == 'Parlamentar', Parlamentar_aut_lj.nom_parlamentar),
                (TipoAutor_aut.des_tipo_autor == 'Bancada',
                    func.concat(
                        Bancada_aut_lj.nom_bancada, " (",
                        func.date_format(Legislatura_aut_lj.dat_inicio, '%Y'), "-",
                        func.date_format(Legislatura_aut_lj.dat_fim, '%Y'), ")"
                    )
                ),
                (TipoAutor_aut.des_tipo_autor == 'Comissao', Comissao_aut_lj.nom_comissao),
                (True, Autor_aut.nom_autor)
            ).label('nome')

            autores = session.query(autor_nome_expr).\
                select_from(Autoria_aut).\
                join(Autor_aut, Autoria_aut.cod_autor == Autor_aut.cod_autor).\
                join(TipoAutor_aut, Autor_aut.tip_autor == TipoAutor_aut.tip_autor).\
                outerjoin(Parlamentar_aut_lj, Autor_aut.cod_parlamentar == Parlamentar_aut_lj.cod_parlamentar).\
                outerjoin(Comissao_aut_lj, Autor_aut.cod_comissao == Comissao_aut_lj.cod_comissao).\
                outerjoin(Bancada_aut_lj, Autor_aut.cod_bancada == Bancada_aut_lj.cod_bancada).\
                outerjoin(Legislatura_aut_lj, Bancada_aut_lj.num_legislatura == Legislatura_aut_lj.num_legislatura).\
                filter(
                    Autoria_aut.cod_materia == cod_materia,
                    Autoria_aut.ind_excluido == 0,
                    Autor_aut.ind_excluido == 0
                ).\
                order_by(Autoria_aut.ind_primeiro_autor.desc(), autor_nome_expr).\
                all()
            autores = [a.nome for a in autores]

            # 3. TODAS RELATORIAS
            Relatoria_rel = aliased(Relatoria, name='relatoria_rel')
            Parlamentar_rel = aliased(Parlamentar, name='parlamentar_rel')
            Comissao_rel = aliased(Comissao, name='comissao_rel')
            relatorias_q = session.query(
                Relatoria_rel, Parlamentar_rel, Comissao_rel
            ).outerjoin(
                Parlamentar_rel, Relatoria_rel.cod_parlamentar == Parlamentar_rel.cod_parlamentar
            ).outerjoin(
                Comissao_rel, Relatoria_rel.cod_comissao == Comissao_rel.cod_comissao
            ).filter(
                Relatoria_rel.cod_materia == cod_materia,
                Relatoria_rel.ind_excluido == 0
            ).order_by(
                Relatoria_rel.num_ordem
            ).all()
            relatorias_data = [
                {
                    'cod_relatoria': r.cod_relatoria,
                    'relator': parl.nom_parlamentar if parl else None,
                    'comissao': com.nom_comissao if com else None,
                    'dat_desig_relator': r.dat_desig_relator.strftime('%d/%m/%Y') if r.dat_desig_relator else None
                }
                for r, parl, com in relatorias_q
            ]
            # para retrocompatibilidade, manter também o atual:
            relatoria_obj, parlamentar_rel, comissao_rel = relatorias_q[0] if relatorias_q else (None, None, None)
            nome_relator = parlamentar_rel.nom_parlamentar if parlamentar_rel else None
            nome_comissao_rel = comissao_rel.nom_comissao if comissao_rel else None

            # 4. SUBSTITUTIVOS
            substitutivos = session.query(Substitutivo).filter(
                Substitutivo.cod_materia == cod_materia,
                Substitutivo.ind_excluido == 0
            ).order_by(Substitutivo.cod_substitutivo).all()
            
            # Buscar autoria dos substitutivos
            cod_substitutivos = [s.cod_substitutivo for s in substitutivos]
            autoria_subst_dict = {}
            if cod_substitutivos:
                AutoriaSubst_aut = aliased(AutoriaSubstitutivo, name='autoria_subst_aut')
                AutorSubst_aut = aliased(Autor, name='autor_subst_aut')
                TipoAutorSubst_aut = aliased(TipoAutor, name='tipo_autor_subst_aut')
                ParlamentarSubst_aut = aliased(Parlamentar, name='parlamentar_subst_aut')
                ComissaoSubst_aut = aliased(Comissao, name='comissao_subst_aut')
                BancadaSubst_aut = aliased(Bancada, name='bancada_subst_aut')
                LegislaturaSubst_aut = aliased(Legislatura, name='legislatura_subst_aut')
                
                autor_nome_expr = _build_autor_name_expression(
                    TipoAutor_alias=TipoAutorSubst_aut,
                    Parlamentar_alias=ParlamentarSubst_aut,
                    Comissao_alias=ComissaoSubst_aut,
                    Bancada_alias=BancadaSubst_aut,
                    Legislatura_alias=LegislaturaSubst_aut,
                    Autor_alias=AutorSubst_aut
                )
                
                autoria_subst = session.query(
                    AutoriaSubst_aut.cod_substitutivo,
                    autor_nome_expr.label('nome_autor')
                ).select_from(AutoriaSubst_aut)\
                 .join(AutorSubst_aut, AutoriaSubst_aut.cod_autor == AutorSubst_aut.cod_autor)\
                 .join(TipoAutorSubst_aut, AutorSubst_aut.tip_autor == TipoAutorSubst_aut.tip_autor)\
                 .outerjoin(ParlamentarSubst_aut, AutorSubst_aut.cod_parlamentar == ParlamentarSubst_aut.cod_parlamentar)\
                 .outerjoin(ComissaoSubst_aut, AutorSubst_aut.cod_comissao == ComissaoSubst_aut.cod_comissao)\
                 .outerjoin(BancadaSubst_aut, AutorSubst_aut.cod_bancada == BancadaSubst_aut.cod_bancada)\
                 .outerjoin(LegislaturaSubst_aut, BancadaSubst_aut.num_legislatura == LegislaturaSubst_aut.num_legislatura)\
                 .filter(
                     AutoriaSubst_aut.cod_substitutivo.in_(cod_substitutivos),
                     AutoriaSubst_aut.ind_excluido == 0,
                     AutorSubst_aut.ind_excluido == 0
                 ).all()
                
                for cod_subst, nome in autoria_subst:
                    if cod_subst not in autoria_subst_dict:
                        autoria_subst_dict[cod_subst] = []
                    autoria_subst_dict[cod_subst].append(nome)
            
            substitutivos_data = [
                {
                    'cod_substitutivo': s.cod_substitutivo,
                    'num_substitutivo': s.num_substitutivo,
                    'des_tipo_substitutivo': 'Substitutivo',  # Tipo fixo, não há tabela de tipos
                    'dat_apresentacao': s.dat_apresentacao.strftime('%d/%m/%Y') if s.dat_apresentacao else None,
                    'txt_ementa': s.txt_ementa or '',
                    'autores': ', '.join(autoria_subst_dict.get(s.cod_substitutivo, []))
                }
                for s in substitutivos
            ]

            # 5. EMENDAS (INCLUINDO TIPO)
            Emenda_e = aliased(Emenda, name='emenda_e')
            TipoEmenda_te = aliased(TipoEmenda, name='tipo_emenda_te')
            emendas = session.query(Emenda_e, TipoEmenda_te).\
                join(TipoEmenda_te, Emenda_e.tip_emenda == TipoEmenda_te.tip_emenda).\
                filter(
                    Emenda_e.cod_materia == cod_materia,
                    Emenda_e.ind_excluido == 0
                ).order_by(Emenda_e.cod_emenda).all()
            
            # Buscar autoria das emendas
            cod_emendas = [e.cod_emenda for e, _ in emendas]
            autoria_emenda_dict = {}
            if cod_emendas:
                    AutoriaEmenda_aut = aliased(AutoriaEmenda, name='autoria_emenda_aut')
                    AutorEmenda_aut = aliased(Autor, name='autor_emenda_aut')
                    TipoAutorEmenda_aut = aliased(TipoAutor, name='tipo_autor_emenda_aut')
                    ParlamentarEmenda_aut = aliased(Parlamentar, name='parlamentar_emenda_aut')
                    ComissaoEmenda_aut = aliased(Comissao, name='comissao_emenda_aut')
                    BancadaEmenda_aut = aliased(Bancada, name='bancada_emenda_aut')
                    LegislaturaEmenda_aut = aliased(Legislatura, name='legislatura_emenda_aut')
                    
                    autor_nome_expr = _build_autor_name_expression(
                        TipoAutor_alias=TipoAutorEmenda_aut,
                        Parlamentar_alias=ParlamentarEmenda_aut,
                        Comissao_alias=ComissaoEmenda_aut,
                        Bancada_alias=BancadaEmenda_aut,
                        Legislatura_alias=LegislaturaEmenda_aut,
                        Autor_alias=AutorEmenda_aut
                    )
                    
                    autoria_emenda = session.query(
                        AutoriaEmenda_aut.cod_emenda,
                        autor_nome_expr.label('nome_autor')
                    ).select_from(AutoriaEmenda_aut)\
                     .join(AutorEmenda_aut, AutoriaEmenda_aut.cod_autor == AutorEmenda_aut.cod_autor)\
                     .join(TipoAutorEmenda_aut, AutorEmenda_aut.tip_autor == TipoAutorEmenda_aut.tip_autor)\
                     .outerjoin(ParlamentarEmenda_aut, AutorEmenda_aut.cod_parlamentar == ParlamentarEmenda_aut.cod_parlamentar)\
                     .outerjoin(ComissaoEmenda_aut, AutorEmenda_aut.cod_comissao == ComissaoEmenda_aut.cod_comissao)\
                     .outerjoin(BancadaEmenda_aut, AutorEmenda_aut.cod_bancada == BancadaEmenda_aut.cod_bancada)\
                     .outerjoin(LegislaturaEmenda_aut, BancadaEmenda_aut.num_legislatura == LegislaturaEmenda_aut.num_legislatura)\
                     .filter(
                         AutoriaEmenda_aut.cod_emenda.in_(cod_emendas),
                         AutoriaEmenda_aut.ind_excluido == 0,
                         AutorEmenda_aut.ind_excluido == 0
                     ).all()
                
                    for cod_emenda, nome in autoria_emenda:
                        if cod_emenda not in autoria_emenda_dict:
                            autoria_emenda_dict[cod_emenda] = []
                        autoria_emenda_dict[cod_emenda].append(nome)
            
            emendas_data = [
                {
                    'cod_emenda': e.cod_emenda,
                    'num_emenda': e.num_emenda,
                    'tip_emenda': e.tip_emenda,
                    'des_tipo_emenda': te.des_tipo_emenda if te else None,
                    'dat_apresentacao': e.dat_apresentacao.strftime('%d/%m/%Y') if e.dat_apresentacao else None,
                    'autores': ', '.join(autoria_emenda_dict.get(e.cod_emenda, []))
                }
                for e, te in emendas
            ]

            # 6. DOCUMENTOS ACESSÓRIOS + tipo
            DocumentoAcessorio_doc = aliased(DocumentoAcessorio, name='documento_acessorio_doc')
            TipoDocumento_doc = aliased(TipoDocumento, name='tipo_documento_doc')
            docs = session.query(DocumentoAcessorio_doc, TipoDocumento_doc).\
                join(TipoDocumento_doc, DocumentoAcessorio_doc.tip_documento == TipoDocumento_doc.tip_documento).\
                filter(
                    DocumentoAcessorio_doc.cod_materia == cod_materia,
                    DocumentoAcessorio_doc.ind_excluido == 0
                ).order_by(DocumentoAcessorio_doc.cod_documento).all()
            docs_data = [
                {
                    'cod_documento': d.cod_documento,
                    'tip_documento': d.tip_documento,
                    'des_tipo_documento': td.des_tipo_documento,
                    'nom_documento': d.nom_documento,
                    'nom_autor_documento': d.nom_autor_documento or '',
                    'dat_documento': d.dat_documento.strftime('%d/%m/%Y') if d.dat_documento else None,
                    'txt_ementa': d.txt_ementa
                }
                for d, td in docs
            ]

            # 7. ÚLTIMA TRAMITAÇÃO - DESTINO
            unid_dest_nome = None
            if tram_obj:
                if tram_obj.cod_unid_tram_dest:
                    ut = session.query(UT_Dest, Org_Dest, Com_Dest, Parl_Dest).\
                        outerjoin(Org_Dest, UT_Dest.cod_orgao == Org_Dest.cod_orgao).\
                        outerjoin(Com_Dest, UT_Dest.cod_comissao == Com_Dest.cod_comissao).\
                        outerjoin(Parl_Dest, UT_Dest.cod_parlamentar == Parl_Dest.cod_parlamentar).\
                        filter(UT_Dest.cod_unid_tramitacao == tram_obj.cod_unid_tram_dest).\
                        first()
                    if ut:
                        ut_obj, org_obj, com_obj, parl_obj = ut
                        if com_obj and com_obj.nom_comissao:
                            unid_dest_nome = com_obj.nom_comissao
                        elif org_obj and org_obj.nom_orgao:
                            unid_dest_nome = org_obj.nom_orgao
                        elif parl_obj and parl_obj.nom_parlamentar:
                            unid_dest_nome = parl_obj.nom_parlamentar

            # 8. PARECERES DE COMISSÃO (estão em Relatoria, não em Parecer)
            # Pareceres são identificados quando num_parecer não é nulo na Relatoria
            Relatoria_p = aliased(Relatoria, name='relatoria_p')
            Parlamentar_p = aliased(Parlamentar, name='parlamentar_p')
            Comissao_p = aliased(Comissao, name='comissao_p')
            pareceres_q = session.query(Relatoria_p, Parlamentar_p, Comissao_p).\
                outerjoin(Parlamentar_p, Relatoria_p.cod_parlamentar == Parlamentar_p.cod_parlamentar).\
                outerjoin(Comissao_p, Relatoria_p.cod_comissao == Comissao_p.cod_comissao).\
                filter(
                    Relatoria_p.cod_materia == cod_materia,
                    Relatoria_p.ind_excluido == 0,
                    Relatoria_p.num_parecer.isnot(None)  # Apenas relatorias com parecer
                ).\
                order_by(Relatoria_p.num_ordem).all()
            pareceres_data = [
                {
                    'cod_relatoria': r.cod_relatoria,
                    'num_parecer': r.num_parecer,
                    'ano_parecer': r.ano_parecer,
                    'txt_parecer': r.txt_parecer,
                    'tip_conclusao': r.tip_conclusao,
                    'tip_apresentacao': r.tip_apresentacao,
                    'relator': parl.nom_parlamentar if parl else None,
                    'comissao': com.nom_comissao if com else None
                }
                for r, parl, com in pareceres_q
            ]

            # 9. NORMAS JURÍDICAS
            NormaJuridica_n = aliased(NormaJuridica, name='norma_n')
            TipoNormaJuridica_tn = aliased(TipoNormaJuridica, name='tipo_norma_n')
            normas = session.query(NormaJuridica_n, TipoNormaJuridica_tn).\
                join(TipoNormaJuridica_tn, NormaJuridica_n.tip_norma == TipoNormaJuridica_tn.tip_norma).\
                filter(
                    NormaJuridica_n.cod_materia == cod_materia,
                    NormaJuridica_n.ind_excluido == 0
                ).all()
            normas_data = [
                {
                    'cod_norma': n.cod_norma,
                    'tip_norma': n.tip_norma,
                    'des_tipo_norma': tn.des_tipo_norma if tn else None,
                    'num_norma': n.num_norma,
                    'ano_norma': n.ano_norma,
                    'dat_norma': n.dat_norma.strftime('%d/%m/%Y') if n.dat_norma else None,
                    'dat_publicacao': n.dat_publicacao.strftime('%d/%m/%Y') if n.dat_publicacao else None,
                    'txt_ementa': n.txt_ementa
                }
                for n, tn in normas
            ]
            
            # 10. MATÉRIAS ANEXADAS (matérias anexadas a esta)
            anexadas = session.query(
                Anexada, MateriaLegislativa, TipoMateriaLegislativa
            ).join(
                MateriaLegislativa, Anexada.cod_materia_anexada == MateriaLegislativa.cod_materia
            ).join(
                TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
            ).filter(
                Anexada.cod_materia_principal == cod_materia,
                Anexada.ind_excluido == 0,
                MateriaLegislativa.ind_excluido == 0
            ).all()
            anexadas_data = [
                {
                    'cod_materia': mat.cod_materia,
                    'sgl_tipo': tipo.sgl_tipo_materia,
                    'des_tipo': tipo.des_tipo_materia,
                    'num_ident_basica': mat.num_ident_basica,
                    'ano_ident_basica': mat.ano_ident_basica,
                    'url': f"{getToolByName(self.context, 'portal_url')()}/consultas/materia/materia_mostrar_proc?cod_materia={mat.cod_materia}"
                }
                for anex, mat, tipo in anexadas
            ]
            
            # 11. MATÉRIAS ANEXADORAS (matérias que anexaram esta)
            anexadoras = session.query(
                Anexada, MateriaLegislativa, TipoMateriaLegislativa
            ).join(
                MateriaLegislativa, Anexada.cod_materia_principal == MateriaLegislativa.cod_materia
            ).join(
                TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia
            ).filter(
                Anexada.cod_materia_anexada == cod_materia,
                Anexada.ind_excluido == 0,
                MateriaLegislativa.ind_excluido == 0
            ).all()
            anexadoras_data = [
                {
                    'cod_materia': mat.cod_materia,
                    'sgl_tipo': tipo.sgl_tipo_materia,
                    'des_tipo': tipo.des_tipo_materia,
                    'num_ident_basica': mat.num_ident_basica,
                    'ano_ident_basica': mat.ano_ident_basica,
                    'url': f"{getToolByName(self.context, 'portal_url')()}/consultas/materia/materia_mostrar_proc?cod_materia={mat.cod_materia}"
                }
                for anex, mat, tipo in anexadoras
            ]
            
            # 12. PROCESSO (NUMERAÇÃO)
            numeracao = session.query(Numeracao).filter(
                Numeracao.cod_materia == cod_materia
            ).first()
            processo_data = {
                'num_materia': numeracao.num_materia if numeracao else None,
                'ano_materia': numeracao.ano_materia if numeracao else None
            } if numeracao else None
            
            # Adicionar URLs para documentos e pareceres
            portal_url = getToolByName(self.context, 'portal_url')()
            mtool = getToolByName(self.context, 'portal_membership')
            # Verificar se é operador: usuário autenticado com perfis "Operador" ou "Operador Materia"
            is_operador = False
            if not mtool.isAnonymousUser():
                member = mtool.getAuthenticatedMember()
                if member:
                    is_operador = member.has_role(['Operador', 'Operador Materia'])
            
            # URLs para documentos acessórios
            for doc in docs_data:
                doc_id = f"{doc['cod_documento']}.pdf"
                try:
                    sapl_docs = self.context.sapl_documentos.materia
                    if hasattr(sapl_docs, doc_id):
                        doc['url'] = f"{portal_url}/sapl_documentos/materia/{doc_id}"
                    else:
                        doc['url'] = None
                except:
                    doc['url'] = None
            
            # URLs para substitutivos
            for subst in substitutivos_data:
                subst_id = f"{subst['cod_substitutivo']}_substitutivo.pdf"
                try:
                    sapl_subst = self.context.sapl_documentos.substitutivo
                    if hasattr(sapl_subst, subst_id):
                        subst['url'] = f"{portal_url}/sapl_documentos/substitutivo/{subst_id}"
                    else:
                        subst['url'] = None
                except:
                    subst['url'] = None
            
            # URLs para emendas
            for emenda in emendas_data:
                emenda_id = f"{emenda['cod_emenda']}_emenda.pdf"
                try:
                    sapl_emendas = self.context.sapl_documentos.emenda
                    if hasattr(sapl_emendas, emenda_id):
                        emenda['url'] = f"{portal_url}/sapl_documentos/emenda/{emenda_id}"
                    else:
                        emenda['url'] = None
                except:
                    emenda['url'] = None
            
            # URLs para pareceres
            for parecer in pareceres_data:
                parecer_id = f"{parecer['cod_relatoria']}_parecer.pdf"
                try:
                    sapl_pareceres = self.context.sapl_documentos.parecer_comissao
                    if hasattr(sapl_pareceres, parecer_id):
                        parecer['url'] = f"{portal_url}/sapl_documentos/parecer_comissao/{parecer_id}"
                    else:
                        parecer['url'] = None
                except:
                    parecer['url'] = None

            resp = {
                'cod_materia': materia_obj.cod_materia,
                'tipo_materia': tipo_obj.des_tipo_materia,
                'numero': materia_obj.num_ident_basica,
                'ano': materia_obj.ano_ident_basica,
                'ementa': materia_obj.txt_ementa,
                'apresentacao': materia_obj.dat_apresentacao.strftime('%d/%m/%Y') if materia_obj.dat_apresentacao else None,
                'autores': autores,
                'relator': nome_relator,
                'comissao_relator': nome_comissao_rel,
                'relatorias': relatorias_data,
                'regime_tramitacao': {
                    'cod_regime_tramitacao': regime_obj.cod_regime_tramitacao if regime_obj else None,
                    'des_regime_tramitacao': regime_obj.des_regime_tramitacao if regime_obj else None
                } if regime_obj else None,
                'quorum': {
                    'cod_quorum': quorum_obj.cod_quorum if quorum_obj else None,
                    'des_quorum': quorum_obj.des_quorum if quorum_obj else None,
                    'txt_formula': quorum_obj.txt_formula if quorum_obj else None
                } if quorum_obj else None,
                'dat_fim_prazo': materia_obj.dat_fim_prazo.strftime('%d/%m/%Y') if hasattr(materia_obj, 'dat_fim_prazo') and materia_obj.dat_fim_prazo else None,
                'substitutivos': substitutivos_data,
                'emendas': emendas_data,
                'documentos_acessorios': docs_data,
                'pareceres': pareceres_data,
                'normas_juridicas': normas_data,
                'anexadas': anexadas_data,
                'anexadoras': anexadoras_data,
                'processo': processo_data,
                'ultima_tramitacao': {
                    'data': tram_obj.dat_tramitacao.strftime('%d/%m/%Y') if tram_obj and tram_obj.dat_tramitacao else None,
                    'unidade_destino': unid_dest_nome,
                    'status': stat_tram_obj.des_status if stat_tram_obj else None,
                    'prazo_fim': tram_obj.dat_fim_prazo.strftime('%d/%m/%Y') if tram_obj and hasattr(tram_obj, 'dat_fim_prazo') and tram_obj.dat_fim_prazo else None,
                    'txt_tramitacao': tram_obj.txt_tramitacao if tram_obj and hasattr(tram_obj, 'txt_tramitacao') else None
                } if tram_obj else None
            }

            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(resp, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Erro ao obter detalhes da matéria: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao obter detalhes da matéria', 'details': str(e)})
        finally:
            session.close()

class MateriaDocumentosView(grok.View):
    """Endpoint para buscar apenas os documentos de uma matéria (emendas, substitutivos, pareceres, documentos acessórios)."""
    grok.context(Interface)
    grok.name('materia_documentos_json')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        try:
            cod_materia = self.request.get('cod_materia')
            tipo_documento = self.request.get('tipo')  # 'emendas', 'substitutivos', 'pareceres', 'documentos_acessorios'
            
            if not cod_materia:
                self.request.response.setStatus(400)
                return json.dumps({'error': 'cod_materia é obrigatório'})
            
            cod_materia = int(cod_materia)
            portal_url = getToolByName(self.context, 'portal_url')()
            
            result = {}
            
            if tipo_documento in ['emendas', None]:
                # EMENDAS
                Emenda_e = aliased(Emenda, name='emenda_e')
                TipoEmenda_te = aliased(TipoEmenda, name='tipo_emenda_te')
                emendas = session.query(Emenda_e, TipoEmenda_te).\
                    join(TipoEmenda_te, Emenda_e.tip_emenda == TipoEmenda_te.tip_emenda).\
                    filter(
                        Emenda_e.cod_materia == cod_materia,
                        Emenda_e.ind_excluido == 0
                    ).order_by(Emenda_e.cod_emenda).all()
                
                # Buscar autoria das emendas
                cod_emendas = [e.cod_emenda for e, _ in emendas]
                autoria_emenda_dict = {}
                if cod_emendas:
                    AutoriaEmenda_aut = aliased(AutoriaEmenda, name='autoria_emenda_aut')
                    AutorEmenda_aut = aliased(Autor, name='autor_emenda_aut')
                    TipoAutorEmenda_aut = aliased(TipoAutor, name='tipo_autor_emenda_aut')
                    ParlamentarEmenda_aut = aliased(Parlamentar, name='parlamentar_emenda_aut')
                    ComissaoEmenda_aut = aliased(Comissao, name='comissao_emenda_aut')
                    BancadaEmenda_aut = aliased(Bancada, name='bancada_emenda_aut')
                    LegislaturaEmenda_aut = aliased(Legislatura, name='legislatura_emenda_aut')
                    
                    autor_nome_expr = _build_autor_name_expression(
                        TipoAutor_alias=TipoAutorEmenda_aut,
                        Parlamentar_alias=ParlamentarEmenda_aut,
                        Comissao_alias=ComissaoEmenda_aut,
                        Bancada_alias=BancadaEmenda_aut,
                        Legislatura_alias=LegislaturaEmenda_aut,
                        Autor_alias=AutorEmenda_aut
                    )
                    
                    autoria_emenda = session.query(
                        AutoriaEmenda_aut.cod_emenda,
                        autor_nome_expr.label('nome_autor')
                    ).select_from(AutoriaEmenda_aut)\
                     .join(AutorEmenda_aut, AutoriaEmenda_aut.cod_autor == AutorEmenda_aut.cod_autor)\
                     .join(TipoAutorEmenda_aut, AutorEmenda_aut.tip_autor == TipoAutorEmenda_aut.tip_autor)\
                     .outerjoin(ParlamentarEmenda_aut, AutorEmenda_aut.cod_parlamentar == ParlamentarEmenda_aut.cod_parlamentar)\
                     .outerjoin(ComissaoEmenda_aut, AutorEmenda_aut.cod_comissao == ComissaoEmenda_aut.cod_comissao)\
                     .outerjoin(BancadaEmenda_aut, AutorEmenda_aut.cod_bancada == BancadaEmenda_aut.cod_bancada)\
                     .outerjoin(LegislaturaEmenda_aut, BancadaEmenda_aut.num_legislatura == LegislaturaEmenda_aut.num_legislatura)\
                     .filter(
                         AutoriaEmenda_aut.cod_emenda.in_(cod_emendas),
                         AutoriaEmenda_aut.ind_excluido == 0,
                         AutorEmenda_aut.ind_excluido == 0
                     ).all()
                    
                    for cod_emenda, nome in autoria_emenda:
                        if cod_emenda not in autoria_emenda_dict:
                            autoria_emenda_dict[cod_emenda] = []
                        autoria_emenda_dict[cod_emenda].append(nome)
                
                emendas_data = []
                for e, te in emendas:
                    emenda_id = f"{e.cod_emenda}_emenda.pdf"
                    url = None
                    try:
                        sapl_emendas = self.context.sapl_documentos.emenda
                        if hasattr(sapl_emendas, emenda_id):
                            url = f"{portal_url}/sapl_documentos/emenda/{emenda_id}"
                    except:
                        pass
                    emendas_data.append({
                        'cod_emenda': e.cod_emenda,
                        'num_emenda': e.num_emenda,
                        'tip_emenda': e.tip_emenda,
                        'des_tipo_emenda': te.des_tipo_emenda if te else None,
                        'dat_apresentacao': e.dat_apresentacao.strftime('%d/%m/%Y') if e.dat_apresentacao else None,
                        'autores': ', '.join(autoria_emenda_dict.get(e.cod_emenda, [])),
                        'url': url
                    })
                result['emendas'] = emendas_data
            
            if tipo_documento in ['substitutivos', None]:
                # SUBSTITUTIVOS
                substitutivos = session.query(Substitutivo).filter(
                    Substitutivo.cod_materia == cod_materia,
                    Substitutivo.ind_excluido == 0
                ).order_by(Substitutivo.cod_substitutivo).all()
                
                # Buscar autoria dos substitutivos
                cod_substitutivos = [s.cod_substitutivo for s in substitutivos]
                autoria_subst_dict = {}
                if cod_substitutivos:
                    AutoriaSubst_aut = aliased(AutoriaSubstitutivo, name='autoria_subst_aut')
                    AutorSubst_aut = aliased(Autor, name='autor_subst_aut')
                    TipoAutorSubst_aut = aliased(TipoAutor, name='tipo_autor_subst_aut')
                    ParlamentarSubst_aut = aliased(Parlamentar, name='parlamentar_subst_aut')
                    ComissaoSubst_aut = aliased(Comissao, name='comissao_subst_aut')
                    BancadaSubst_aut = aliased(Bancada, name='bancada_subst_aut')
                    LegislaturaSubst_aut = aliased(Legislatura, name='legislatura_subst_aut')
                    
                    autor_nome_expr = _build_autor_name_expression(
                        TipoAutor_alias=TipoAutorSubst_aut,
                        Parlamentar_alias=ParlamentarSubst_aut,
                        Comissao_alias=ComissaoSubst_aut,
                        Bancada_alias=BancadaSubst_aut,
                        Legislatura_alias=LegislaturaSubst_aut,
                        Autor_alias=AutorSubst_aut
                    )
                    
                    autoria_subst = session.query(
                        AutoriaSubst_aut.cod_substitutivo,
                        autor_nome_expr.label('nome_autor')
                    ).select_from(AutoriaSubst_aut)\
                     .join(AutorSubst_aut, AutoriaSubst_aut.cod_autor == AutorSubst_aut.cod_autor)\
                     .join(TipoAutorSubst_aut, AutorSubst_aut.tip_autor == TipoAutorSubst_aut.tip_autor)\
                     .outerjoin(ParlamentarSubst_aut, AutorSubst_aut.cod_parlamentar == ParlamentarSubst_aut.cod_parlamentar)\
                     .outerjoin(ComissaoSubst_aut, AutorSubst_aut.cod_comissao == ComissaoSubst_aut.cod_comissao)\
                     .outerjoin(BancadaSubst_aut, AutorSubst_aut.cod_bancada == BancadaSubst_aut.cod_bancada)\
                     .outerjoin(LegislaturaSubst_aut, BancadaSubst_aut.num_legislatura == LegislaturaSubst_aut.num_legislatura)\
                     .filter(
                         AutoriaSubst_aut.cod_substitutivo.in_(cod_substitutivos),
                         AutoriaSubst_aut.ind_excluido == 0,
                         AutorSubst_aut.ind_excluido == 0
                     ).all()
                    
                    for cod_subst, nome in autoria_subst:
                        if cod_subst not in autoria_subst_dict:
                            autoria_subst_dict[cod_subst] = []
                        autoria_subst_dict[cod_subst].append(nome)
                
                substitutivos_data = []
                for s in substitutivos:
                    subst_id = f"{s.cod_substitutivo}_substitutivo.pdf"
                    url = None
                    try:
                        sapl_subst = self.context.sapl_documentos.substitutivo
                        if hasattr(sapl_subst, subst_id):
                            url = f"{portal_url}/sapl_documentos/substitutivo/{subst_id}"
                    except:
                        pass
                    substitutivos_data.append({
                        'cod_substitutivo': s.cod_substitutivo,
                        'num_substitutivo': s.num_substitutivo,
                        'des_tipo_substitutivo': 'Substitutivo',
                        'dat_apresentacao': s.dat_apresentacao.strftime('%d/%m/%Y') if s.dat_apresentacao else None,
                        'txt_ementa': s.txt_ementa or '',
                        'autores': ', '.join(autoria_subst_dict.get(s.cod_substitutivo, [])),
                        'url': url
                    })
                result['substitutivos'] = substitutivos_data
            
            if tipo_documento in ['pareceres', None]:
                # PARECERES
                Relatoria_p = aliased(Relatoria, name='relatoria_p')
                Parlamentar_p = aliased(Parlamentar, name='parlamentar_p')
                Comissao_p = aliased(Comissao, name='comissao_p')
                TipoFimRelatoria_p = aliased(TipoFimRelatoria, name='tipo_fim_relatoria_p')
                pareceres_q = session.query(Relatoria_p, Parlamentar_p, Comissao_p, TipoFimRelatoria_p).\
                    outerjoin(Parlamentar_p, Relatoria_p.cod_parlamentar == Parlamentar_p.cod_parlamentar).\
                    outerjoin(Comissao_p, Relatoria_p.cod_comissao == Comissao_p.cod_comissao).\
                    outerjoin(TipoFimRelatoria_p, Relatoria_p.tip_fim_relatoria == TipoFimRelatoria_p.tip_fim_relatoria).\
                    filter(
                        Relatoria_p.cod_materia == cod_materia,
                        Relatoria_p.ind_excluido == 0,
                        Relatoria_p.num_parecer.isnot(None)
                    ).order_by(Relatoria_p.num_ordem).all()
                pareceres_data = []
                for r, parl, com, tipo_fim in pareceres_q:
                    parecer_id = f"{r.cod_relatoria}_parecer.pdf"
                    url = None
                    try:
                        sapl_pareceres = self.context.sapl_documentos.parecer_comissao
                        if hasattr(sapl_pareceres, parecer_id):
                            url = f"{portal_url}/sapl_documentos/parecer_comissao/{parecer_id}"
                    except:
                        pass
                    pareceres_data.append({
                        'cod_relatoria': r.cod_relatoria,
                        'num_parecer': r.num_parecer,
                        'ano_parecer': r.ano_parecer,
                        'relator': parl.nom_parlamentar if parl else None,
                        'comissao': com.nom_comissao if com else None,
                        'tip_fim_relatoria': r.tip_fim_relatoria,
                        'des_fim_relatoria': tipo_fim.des_fim_relatoria if tipo_fim else None,
                        'url': url
                    })
                result['pareceres'] = pareceres_data
            
            if tipo_documento in ['documentos_acessorios', None]:
                # DOCUMENTOS ACESSÓRIOS
                DocumentoAcessorio_doc = aliased(DocumentoAcessorio, name='documento_acessorio_doc')
                TipoDocumento_doc = aliased(TipoDocumento, name='tipo_documento_doc')
                docs = session.query(DocumentoAcessorio_doc, TipoDocumento_doc).\
                    join(TipoDocumento_doc, DocumentoAcessorio_doc.tip_documento == TipoDocumento_doc.tip_documento).\
                    filter(
                        DocumentoAcessorio_doc.cod_materia == cod_materia,
                        DocumentoAcessorio_doc.ind_excluido == 0
                    ).order_by(DocumentoAcessorio_doc.cod_documento).all()
                docs_data = []
                for d, td in docs:
                    doc_id = f"{d.cod_documento}.pdf"
                    url = None
                    try:
                        sapl_docs = self.context.sapl_documentos.materia
                        if hasattr(sapl_docs, doc_id):
                            url = f"{portal_url}/sapl_documentos/materia/{doc_id}"
                    except:
                        pass
                    docs_data.append({
                        'cod_documento': d.cod_documento,
                        'tip_documento': d.tip_documento,
                        'des_tipo_documento': td.des_tipo_documento,
                        'nom_documento': d.nom_documento,
                        'nom_autor_documento': d.nom_autor_documento or '',
                        'dat_documento': d.dat_documento.strftime('%d/%m/%Y') if d.dat_documento else None,
                        'txt_ementa': d.txt_ementa or '',
                        'url': url
                    })
                result['documentos_acessorios'] = docs_data
            
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Erro ao buscar documentos da matéria: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({'error': 'Erro ao buscar documentos', 'details': str(e)})
        finally:
            session.close()
