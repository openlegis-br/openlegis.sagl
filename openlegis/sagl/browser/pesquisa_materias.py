# -*- coding: utf-8 -*-
from five import grok
from zope.interface import Interface
from z3c.saconfig import named_scoped_session
from openlegis.sagl.models.models import (
    MateriaLegislativa, TipoMateriaLegislativa, Tramitacao,
    Autoria, Relatoria, Parlamentar, UnidadeTramitacao, StatusTramitacao,
    Comissao, Orgao, Autor, TipoAutor, Bancada, Legislatura, TipoFimRelatoria,
    DocumentoAcessorio, TipoDocumento, Substitutivo, Emenda, TipoEmenda, Parecer,
    RegimeTramitacao, QuorumVotacao, TipoNormaJuridica, TipoSituacaoNorma,
    NormaJuridica
)
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy import case, func, and_, or_, cast, String, select, text, asc, desc
from sqlalchemy.sql import expression
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

logger = logging.getLogger(__name__)
Session = named_scoped_session('minha_sessao')

# =================================================================== #
# FUNÇÕES UTILITÁRIAS E CACHEADAS
# =================================================================== #

def _build_autor_name_expression():
    """Constrói e retorna a expressão SQLAlchemy para o nome formatado do autor."""
    bancada_formatada = func.concat(
        Bancada.nom_bancada, " (",
        func.date_format(Legislatura.dat_inicio, '%Y'), "-",
        func.date_format(Legislatura.dat_fim, '%Y'), ")"
    )
    nom_autor_case = case(
        (TipoAutor.des_tipo_autor == 'Parlamentar', Parlamentar.nom_parlamentar),
        (TipoAutor.des_tipo_autor == 'Bancada', bancada_formatada),
        (TipoAutor.des_tipo_autor == 'Comissao', Comissao.nom_comissao),
        else_=Autor.nom_autor
    )
    return nom_autor_case

@lru_cache(maxsize=2)
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
        for t in tipos:
            item = {'id': t.tip_materia, 'text': t.des_tipo_materia}
            if t.tip_natureza == 'P':
                result['principais'].append(item)
            elif t.tip_natureza == 'A':
                result['acessorias'].append(item)
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

    def _parse_int_list_param(self, param_name):
        values = self.request.get(param_name)
        if not values:
            return None
        if isinstance(values, str):
            if values.startswith('[') and values.endswith(']'):
                values = values[1:-1]
            return [int(v.strip()) for v in values.split(',') if v.strip().isdigit()]
        elif isinstance(values, list):
            return [int(v) for v in values if str(v).isdigit()]
        return None

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

    def _apply_all_filters(self, query, session):
        query = self._apply_materia_filters(query)
        query = self._apply_date_filters(query)
        query = self._apply_text_search(query)
        query = self._apply_author_filter(query)
        query = self._apply_rapporteur_filter(query)
        query = self._apply_tramitacao_filters(query, session)
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
        dat1 = self._parse_date_param('dat_apresentacao')
        dat2 = self._parse_date_param('dat_apresentacao2')
        if dat1 and dat2:
            query = query.filter(MateriaLegislativa.dat_apresentacao.between(dat1, dat2))
        elif dat1:
            query = query.filter(MateriaLegislativa.dat_apresentacao >= dat1)
        elif dat2:
            query = query.filter(MateriaLegislativa.dat_apresentacao <= dat2)
        return query

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
            like_term = f"%{termo}%"
            return query.filter(or_(
                MateriaLegislativa.txt_ementa.ilike(like_term),
                MateriaLegislativa.txt_indexacao.ilike(like_term),
                MateriaLegislativa.txt_observacao.ilike(like_term)
            ))

    def _apply_author_filter(self, query):
        cod_autor = self._parse_int_param('cod_autor')
        if cod_autor is not None:
            # O outerjoin é necessário para não excluir matérias sem autor, 
            # mas a filtragem por autor específico deve ser um JOIN mais restritivo.
            # O SQLAlchemy é inteligente o suficiente para converter para INNER JOIN se for filtrado.
            query = query.join(Autoria, MateriaLegislativa.cod_materia == Autoria.cod_materia)\
                         .filter(Autoria.cod_autor == cod_autor, Autoria.ind_excluido == 0)
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
            query = query.order_by(desc(coluna_ordenacao) if ordem_direcao == 'desc' else asc(coluna_ordenacao))

        # Ordenação padrão
        else:
            ordem = self.request.get('rd_ordem', '1')
            order_logic = [
                MateriaLegislativa.ano_ident_basica,
                func.lpad(cast(MateriaLegislativa.num_ident_basica, String), 6, '0')
            ]
            if ordem == '0':
                query = query.order_by(asc(order_logic[0]), asc(order_logic[1]))
            else:
                query = query.order_by(desc(order_logic[0]), desc(order_logic[1]))

        return query

    def _format_results(self, results_raw):
        formatted = []
        portal_url = getToolByName(self.context, 'portal_url')()
        mtool = getToolByName(self.context, 'portal_membership')
        is_operador = mtool.getAuthenticatedMember().has_role(['Operador', 'Operador Materia'])
        docs_folder = self.context.sapl_documentos.materia
        for materia, tipo_materia in results_raw:
            detail_url = f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/materia/materia_mostrar_proc?cod_materia={materia.cod_materia}"
            item = {
                'cod_materia': materia.cod_materia,
                'des_tipo_materia': tipo_materia.des_tipo_materia,
                'num_ident_basica': materia.num_ident_basica,
                'ano_ident_basica': materia.ano_ident_basica,
                'txt_ementa': materia.txt_ementa or '',
                'dat_apresentacao': materia.dat_apresentacao.strftime('%d/%m/%Y') if materia.dat_apresentacao else '',
                'autores': '',
                'detail_url': detail_url,
                'url_texto_integral': None,
                'url_redacao_final': None,
            }
            texto_integral_pdf = f"{materia.cod_materia}_texto_integral.pdf"
            if hasattr(docs_folder, texto_integral_pdf):
                item['url_texto_integral'] = f"{portal_url}/pysc/download_materia_pysc?cod_materia={materia.cod_materia}&texto_original=1"
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
            
            autoria_query = session.query(Autoria.cod_materia, nom_autor_join_expr)\
                .join(Autor, Autoria.cod_autor == Autor.cod_autor)\
                .join(TipoAutor, Autor.tip_autor == TipoAutor.tip_autor)\
                .outerjoin(Parlamentar, Autor.cod_parlamentar == Parlamentar.cod_parlamentar)\
                .outerjoin(Comissao, Autor.cod_comissao == Comissao.cod_comissao)\
                .outerjoin(Bancada, Autor.cod_bancada == Bancada.cod_bancada)\
                .outerjoin(Legislatura, Bancada.num_legislatura == Legislatura.num_legislatura)\
                .filter(Autoria.cod_materia.in_(materia_ids), Autoria.ind_excluido == 0, Autor.ind_excluido == 0)\
                .order_by(Autoria.cod_materia, Autoria.ind_primeiro_autor.desc(), nom_autor_join_expr).all()
            
            for m_id, nom_autor in autoria_query:
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
        
        fieldnames = ['des_tipo_materia', 'num_ident_basica', 'ano_ident_basica', 'txt_ementa', 'dat_apresentacao', 'autores']
        
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(formatted_for_export)
        return output.getvalue().encode('utf-8')

    def _export_excel(self, results_raw):
        self.request.response.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="materias.xlsx"')
        if not results_raw: return b""
        formatted_for_export = self._add_authorship_info(self._format_results(results_raw))
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Matérias"
        
        header = ['des_tipo_materia', 'num_ident_basica', 'ano_ident_basica', 'txt_ementa', 'dat_apresentacao', 'autores']
        
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
        data_keys = ['des_tipo_materia', 'num_ano_combined', 'txt_ementa', 'dat_apresentacao', 'autores']
        header_labels = ['Tipo', 'Número/Ano', 'Ementa', 'Apresentação', 'Autoria']
        
        # Preparar dados da tabela
        table_data = []
        
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
                Paragraph(str(item.get('autores', '')), normal_style)
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
            0.23 * content_width   # Autores
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

    def render(self):
        session = Session()
        try:
            # Uma sugestão antes de qualquer alteração de código:
            # Rode o comando `ANALYZE TABLE tramitacao;` no seu MySQL.
            # Às vezes, as estatísticas da tabela ficam desatualizadas e o MySQL
            # escolhe um plano de execução ruim mesmo com o índice correto.
            
            query = self._build_base_query_for_filters(session)
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
            stats_results = stats_query.all()
            
            stats = {tipo: contagem for tipo, contagem in stats_results}

            # Aplicar ordenação para a consulta final paginada/exportada
            ordered_query = self._apply_ordering(query, session)
            formato = self.request.get('formato', '').lower()
            if formato in ('csv', 'excel', 'pdf'):
                is_anonymous = getToolByName(self.context, 'portal_membership').isAnonymousUser()
                paginar_exportacao = self.request.get('paginar_exportacao') == '1'
                if paginar_exportacao:
                    page = self._parse_int_param('pagina', 1)
                    page_size = min(max(self._parse_int_param('itens_por_pagina', 10), 1), 100)
                    offset = (page - 1) * page_size
                    results_raw = ordered_query.offset(offset).limit(page_size).all()
                else:
                    results_raw = ordered_query.all()
                    MAX_ANON_EXPORT = 300
                    if is_anonymous and len(results_raw) > MAX_ANON_EXPORT:
                        self.request.response.setStatus(403)
                        return json.dumps({
                            'error': f'Exportação muito grande. O limite é de {MAX_ANON_EXPORT} linhas.',
                            'details': 'Use mais filtros ou autentique-se para exportar todos os resultados.'
                        })
                if formato == 'csv': return self._export_csv(results_raw)
                if formato == 'excel': return self._export_excel(results_raw)
                if formato == 'pdf': return self._export_pdf(results_raw)

            page = self._parse_int_param('pagina', 1)
            page_size = min(max(self._parse_int_param('itens_por_pagina', 10), 1), 100)
            data = self._paginate_and_respond(ordered_query, page, page_size, total_count)
            
            data['stats'] = stats
            
            self.request.response.setHeader('Content-Type', 'application/json')
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
            substitutivos_data = [
                {
                    'cod_substitutivo': s.cod_substitutivo,
                    'des_tipo_substitutivo': s.des_tipo_substitutivo,
                    'dat_apresentacao': s.dat_apresentacao.strftime('%d/%m/%Y') if s.dat_apresentacao else None
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
            emendas_data = [
                {
                    'cod_emenda': e.cod_emenda,
                    'tip_emenda': e.tip_emenda,
                    'des_tipo_emenda': te.des_tipo_emenda if te else None,
                    'dat_apresentacao': e.dat_apresentacao.strftime('%d/%m/%Y') if e.dat_apresentacao else None
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

            # 8. PARECERES
            Parecer_p = aliased(Parecer, name='parecer_p')
            Relatoria_p = aliased(Relatoria, name='relatoria_p')
            Parlamentar_p = aliased(Parlamentar, name='parlamentar_p')
            Comissao_p = aliased(Comissao, name='comissao_p')
            pareceres_q = session.query(Parecer_p, Relatoria_p, Parlamentar_p, Comissao_p).\
                outerjoin(Relatoria_p, Parecer_p.cod_relatoria == Relatoria_p.cod_relatoria).\
                outerjoin(Parlamentar_p, Relatoria_p.cod_parlamentar == Parlamentar_p.cod_parlamentar).\
                outerjoin(Comissao_p, Relatoria_p.cod_comissao == Comissao_p.cod_comissao).\
                filter(Parecer_p.cod_materia == cod_materia, Parecer_p.ind_excluido == 0).\
                order_by(Parecer_p.cod_relatoria).all()
            pareceres_data = [
                {
                    'num_parecer': p.num_parecer,
                    'ano_parecer': p.ano_parecer,
                    'txt_parecer': p.txt_parecer,
                    'relator': parl.nom_parlamentar if parl else None,
                    'comissao': com.nom_comissao if com else None
                }
                for p, r, parl, com in pareceres_q
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
                'ultima_tramitacao': {
                    'data': tram_obj.dat_tramitacao.strftime('%d/%m/%Y') if tram_obj and tram_obj.dat_tramitacao else None,
                    'unidade_destino': unid_dest_nome,
                    'status': stat_tram_obj.des_status if stat_tram_obj else None,
                    'prazo_fim': tram_obj.dat_fim_prazo.strftime('%d/%m/%Y') if tram_obj and hasattr(tram_obj, 'dat_fim_prazo') and tram_obj.dat_fim_prazo else None
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
