# -*- coding: utf-8 -*-
import io
import csv
import json
import logging

from zope.interface import Interface, implementer

from grokcore.view import View as GrokView, name
from grokcore.component import context
from grokcore.security import require

from sqlalchemy import or_, String, func, cast, exc
from sqlalchemy.sql.expression import column, collate
from sqlalchemy.orm import joinedload

from z3c.saconfig import named_scoped_session

from openlegis.sagl.models.models import Logradouro, Localidade
from openlegis.sagl.interfaces import ILogradouroTableViewExporter

# Exportadores
import openpyxl  # Excel
from reportlab.lib.pagesizes import A4  # PDF
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

Session = named_scoped_session('minha_sessao')

# ---------------------------------------------------------------------
# Collation para MySQL acento-insensível e case-insensível
# MySQL 8+ -> 'utf8mb4_0900_ai_ci'
# MySQL 5.7 -> 'utf8mb4_unicode_ci'
COLLATION = 'utf8mb4_0900_ai_ci'


def ai_ci(col):
    """Força comparação/ordenação acento- e case-insensível no MySQL."""
    return collate(func.coalesce(col, ''), COLLATION)


class LogradouroTableView(GrokView):
    context(Interface)
    name('logradouro_table_view')
    require('zope2.Public')

    def render(self):
        session = Session()
        try:
            # Parâmetros DataTables
            draw = int(self.request.get('draw', 0))
            start = int(self.request.get('start', 0))
            length = int(self.request.get('length', 10))
            search_value = (self.request.get('search[value]', '') or '')

            # Query base com eager load da relação (para montar linhas sem N+1)
            query = (
                session.query(Logradouro)
                .options(joinedload(Logradouro.localidade))
                .filter(Logradouro.ind_excluido == 0)
            )
            logger.debug("Consulta inicial montada.")

            # Query de contagem após filtros (sem paginação)
            count_query = (
                session.query(Logradouro)
                .join(Logradouro.localidade)
                .filter(Logradouro.ind_excluido == 0)
            )

            # -------- Filtro global (barra de busca) --------
            if search_value:
                sv = f"%{search_value}%"
                filter_condition = or_(
                    ai_ci(Logradouro.nom_logradouro).like(sv),
                    ai_ci(Logradouro.nom_bairro).like(sv),
                    ai_ci(Logradouro.num_cep).like(sv),
                    Logradouro.localidade.has(ai_ci(Localidade.nom_localidade).like(sv)),
                    ai_ci(cast(column('cod_logradouro'), String)).like(sv),
                )
                query = query.filter(filter_condition)
                count_query = count_query.filter(filter_condition)
                logger.debug("Filtro global aplicado.")

            # -------- Filtros por coluna --------
            # Ordem no cliente: ['codigo', 'nome', 'bairro', 'cep', 'localidade']
            columns = ['codigo', 'nome', 'bairro', 'cep', 'localidade']
            for i, col_name in enumerate(columns):
                col_sv = (self.request.get(f'columns[{i}][search][value]', '') or '')
                if not col_sv:
                    continue
                sv = f"%{col_sv}%"
                if col_name == 'codigo':
                    expr = ai_ci(cast(column('cod_logradouro'), String)).like(sv)
                    query = query.filter(expr)
                    count_query = count_query.filter(expr)
                elif col_name == 'nome':
                    expr = ai_ci(Logradouro.nom_logradouro).like(sv)
                    query = query.filter(expr)
                    count_query = count_query.filter(expr)
                elif col_name == 'bairro':
                    expr = ai_ci(Logradouro.nom_bairro).like(sv)
                    query = query.filter(expr)
                    count_query = count_query.filter(expr)
                elif col_name == 'cep':
                    expr = ai_ci(Logradouro.num_cep).like(sv)
                    query = query.filter(expr)
                    count_query = count_query.filter(expr)
                elif col_name == 'localidade':
                    expr_rel = Logradouro.localidade.has(ai_ci(Localidade.nom_localidade).like(sv))
                    query = query.filter(expr_rel)
                    count_query = count_query.filter(expr_rel)
                logger.debug(f"Filtro por coluna '{col_name}' aplicado: {col_sv!r}")

            # -------- Ordenação --------
            order_column_index = self.request.get('order[0][column]')
            order_direction = (self.request.get('order[0][dir]', 'asc') or 'asc').lower()

            if order_column_index is None:
                # Ordenação padrão por nome (acento-insensível)
                query = query.order_by(ai_ci(Logradouro.nom_logradouro))
            else:
                order_column_index = int(order_column_index)
                order_columns = [
                    'cod_logradouro',
                    'nom_logradouro',
                    'nom_bairro',
                    'num_cep',
                    'localidade.nom_localidade',
                ]
                if order_column_index < len(order_columns):
                    oc = order_columns[order_column_index]
                    if oc == 'cod_logradouro':
                        order_expr = ai_ci(cast(Logradouro.cod_logradouro, String))
                    elif oc == 'nom_logradouro':
                        order_expr = ai_ci(Logradouro.nom_logradouro)
                    elif oc == 'nom_bairro':
                        order_expr = ai_ci(Logradouro.nom_bairro)
                    elif oc == 'num_cep':
                        order_expr = ai_ci(Logradouro.num_cep)
                    elif oc == 'localidade.nom_localidade':
                        # garante join quando ordenar por campo relacionado
                        query = query.join(Logradouro.localidade)
                        order_expr = ai_ci(Localidade.nom_localidade)
                    else:
                        order_expr = ai_ci(Logradouro.nom_logradouro)
                    query = query.order_by(order_expr.desc() if order_direction == 'desc' else order_expr)

            # -------- Paginação + Execução --------
            query_paged = query.offset(start).limit(length)
            logradouros = query_paged.all()
            logger.debug("Consulta final executada com paginação.")

            records_total = session.query(Logradouro).filter(Logradouro.ind_excluido == 0).count()
            records_filtered = count_query.count()

            # -------- Formatação DataTables --------
            data = [
                [
                    logr.cod_logradouro,
                    logr.nom_logradouro,
                    logr.nom_bairro,
                    logr.num_cep,
                    (logr.localidade.nom_localidade if logr.localidade else None),
                ]
                for logr in logradouros
            ]

            response_data = {
                'draw': draw,
                'recordsTotal': records_total,
                'recordsFiltered': records_filtered,
                'data': data,
            }
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(response_data, ensure_ascii=False)
        except exc.SQLAlchemyError as e:
            logger.error(f"Erro ao acessar o banco de dados: {e}")
            session.rollback()
            self.request.response.status = 500
            return json.dumps({'error': 'Erro ao acessar os dados'}, ensure_ascii=False)
        finally:
            session.close()


class LogradouroTableViewExportBase(GrokView):
    """Classe base para exportação — não registrada (sem name())."""
    context(Interface)
    require('zope2.Public')
    # Sem name() aqui para não registrar esta base como view.

    def __init__(self, context, request):
        super().__init__(context, request)
        self.data_to_export = None
        self.columns_to_export = None

    @staticmethod
    def get_data_query(request, default_order_by='nom_logradouro', default_order_direction='asc'):
        """
        Monta a query SQLAlchemy com filtros e ordenação para exportação.
        Retorna (dados, colunas).
        """
        session = Session()
        try:
            search_value = (request.get('search[value]', '') or '')
            order_column_index = request.get('order[0][column]')
            order_direction = (request.get('order[0][dir]', '') or '').lower()

            logger.debug(f"Parâmetros da requisição de exportação: {dict(request.form)}")

            # Query base selecionando colunas necessárias e juntando Localidade
            query = (
                session.query(
                    Logradouro.nom_logradouro,
                    Logradouro.nom_bairro,
                    Logradouro.num_cep,
                    Localidade.nom_localidade,
                )
                .join(Logradouro.localidade)
                .filter(Logradouro.ind_excluido == 0)
            )

            # -------- Filtro global (barra de busca) --------
            if search_value:
                sv = f"%{search_value}%"
                filter_condition = or_(
                    ai_ci(Logradouro.nom_logradouro).like(sv),
                    ai_ci(Logradouro.nom_bairro).like(sv),
                    ai_ci(Logradouro.num_cep).like(sv),
                    ai_ci(Localidade.nom_localidade).like(sv),
                    ai_ci(cast(column('cod_logradouro'), String)).like(sv),
                )
                query = query.filter(filter_condition)
                logger.debug("Export: filtro global aplicado.")

            # -------- Filtros por coluna (índices do DataTables) --------
            column_indices_map = {
                '1': 'nome',       # nome
                '2': 'bairro',     # bairro
                '3': 'cep',        # cep
                '4': 'localidade', # localidade
            }
            for i_str, col_name in column_indices_map.items():
                col_sv = (request.get(f'columns[{i_str}][search][value]', '') or '')
                if not col_sv:
                    continue
                sv = f"%{col_sv}%"
                if col_name == 'nome':
                    query = query.filter(ai_ci(Logradouro.nom_logradouro).like(sv))
                elif col_name == 'bairro':
                    query = query.filter(ai_ci(Logradouro.nom_bairro).like(sv))
                elif col_name == 'cep':
                    query = query.filter(ai_ci(Logradouro.num_cep).like(sv))
                elif col_name == 'localidade':
                    query = query.filter(ai_ci(Localidade.nom_localidade).like(sv))
                logger.debug(f"Export: filtro por coluna '{col_name}' aplicado: {col_sv!r}")

            # -------- Ordenação --------
            if order_column_index is not None:
                order_map = {
                    '0': ai_ci(Logradouro.nom_logradouro),  # fallback: nome
                    '1': ai_ci(Logradouro.nom_bairro),
                    '2': ai_ci(Logradouro.num_cep),
                    '3': ai_ci(Localidade.nom_localidade),
                }
                order_expr = order_map.get(order_column_index, ai_ci(Logradouro.nom_logradouro))
                query = query.order_by(order_expr.desc() if order_direction == 'desc' else order_expr)
            else:
                # Default
                if default_order_by == 'nom_logradouro':
                    order_expr = ai_ci(Logradouro.nom_logradouro)
                elif default_order_by == 'nom_bairro':
                    order_expr = ai_ci(Logradouro.nom_bairro)
                elif default_order_by == 'num_cep':
                    order_expr = ai_ci(Logradouro.num_cep)
                elif default_order_by == 'nom_localidade':
                    order_expr = ai_ci(Localidade.nom_localidade)
                else:
                    order_expr = ai_ci(Logradouro.nom_logradouro)
                query = query.order_by(order_expr.desc() if default_order_direction == 'desc' else order_expr)

            data_to_export = query.all()
            columns_to_export = ['Nome', 'Bairro', 'CEP', 'Localidade']
            logger.debug("Export: consulta final executada.")
            return data_to_export, columns_to_export
        except exc.SQLAlchemyError as e:
            logger.error(f"Erro ao preparar dados para exportação: {e}")
            raise
        finally:
            session.close()

    @staticmethod
    def render(data, columns, request):
        raise NotImplementedError("Subclasses devem implementar 'render'.")


@implementer(ILogradouroTableViewExporter)
class LogradouroTableViewExportCSV(LogradouroTableViewExportBase):
    name('exportar_logradouros_csv')
    require('zope2.Public')

    def render(self):
        data, columns = LogradouroTableViewExportBase.get_data_query(self.request)

        # Monta CSV (UTF-8)
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(columns)
        for nom_logradouro, nom_bairro, num_cep, nom_localidade in data:
            writer.writerow([nom_logradouro, nom_bairro, num_cep, nom_localidade])

        csv_output = output.getvalue()
        self.request.response.setHeader('Content-Type', 'text/csv; charset=utf-8')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="logradouros.csv"')
        return csv_output


@implementer(ILogradouroTableViewExporter)
class LogradouroTableViewExportExcel(LogradouroTableViewExportBase):
    name('exportar_logradouros_excel')
    require('zope2.Public')

    def render(self):
        data, columns = LogradouroTableViewExportBase.get_data_query(self.request)

        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.append(columns)
        for nom_logradouro, nom_bairro, num_cep, nom_localidade in data:
            sheet.append([nom_logradouro, nom_bairro, num_cep, nom_localidade])

        output = io.BytesIO()
        wb.save(output)
        excel_output = output.getvalue()

        self.request.response.setHeader(
            'Content-Type',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="logradouros.xlsx"')
        return excel_output


@implementer(ILogradouroTableViewExporter)
class LogradouroTableViewExportPDF(LogradouroTableViewExportBase):
    name('exportar_logradouros_pdf')
    require('zope2.Public')

    def render(self):
        data, columns = LogradouroTableViewExportBase.get_data_query(self.request)

        # Monta dados para tabela
        table_rows = [columns]
        for nom_logradouro, nom_bairro, num_cep, nom_localidade in data:
            table_rows.append([nom_logradouro, nom_bairro, num_cep, nom_localidade])

        output = io.BytesIO()
        # paisagem (A4 horizontal)
        doc = SimpleDocTemplate(output, pagesize=(A4[1], A4[0]))

        table = Table(table_rows, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEEEEE')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        doc.build([table])

        self.request.response.setHeader('Content-Type', 'application/pdf')
        self.request.response.setHeader('Content-Disposition', 'inline; filename="logradouros.pdf"')
        return output.getvalue()


def get_column_by_name(model, column_name):
    """Helper para obter atributo de coluna SQLAlchemy por nome (inclui relacionado com '.')."""
    if '.' in column_name:
        related_table_name, related_column_name = column_name.split('.')
        if hasattr(model, related_table_name):
            related_attr = getattr(model, related_table_name)
            try:
                target = related_attr.property.mapper.class_
                if hasattr(target, related_column_name):
                    return getattr(target, related_column_name)
            except Exception:
                return None
    elif hasattr(model, column_name):
        return getattr(model, column_name)
    return None
