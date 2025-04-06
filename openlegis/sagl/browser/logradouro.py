from five import grok
from zope.interface import Interface, implementer
from sqlalchemy.orm import sessionmaker
from z3c.saconfig import named_scoped_session
from openlegis.sagl.models.models import Logradouro, Localidade, Base
from sqlalchemy import create_engine
import json
from sqlalchemy import or_, text, String
from sqlalchemy.sql.expression import column
from sqlalchemy.orm import joinedload
import io
import csv
import openpyxl  # Para Excel
from reportlab.lib.pagesizes import A4  # Para PDF
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from openlegis.sagl.interfaces import ILogradouroTableViewExporter
from sqlalchemy import asc, exc
import unicodedata
from sqlalchemy import func  # Import the 'func' object from SQLAlchemy

Session = named_scoped_session('minha_sessao')

import logging

logging.basicConfig(level=logging.DEBUG)


def normalize_string(s):
    """Remove accents and convert to lowercase."""
    if s is None:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn').lower()


class LogradouroTableView(grok.View):
    grok.context(Interface)
    grok.name('logradouro_table_view')
    grok.require('zope2.Public')

    def render(self):
        session = Session()
        try:
            draw = int(self.request.get('draw', 0))
            start = int(self.request.get('start', 0))
            length = int(self.request.get('length', 10))
            search_value = self.request.get('search[value]', '').lower()

            # Base query with explicit joins and eager loading of 'localidade'
            query = session.query(Logradouro) \
                .options(joinedload(Logradouro.localidade)) \
                .filter(Logradouro.ind_excluido == 0)  # Filtro inicial
            logging.debug(f"Consulta inicial: {str(query.statement)}")

            # Base query for counting with explicit joins
            count_query = session.query(Logradouro) \
                .join(Logradouro.localidade) \
                .filter(Logradouro.ind_excluido == 0)  # Filtro inicial
            logging.debug(f"Consulta de contagem inicial: {str(count_query.statement)}")

            # Apply global filtering
            if search_value:
                search_expression = "%{}%".format(normalize_string(search_value))
                filter_condition = or_(
                    func.lower(Logradouro.nom_logradouro).like(search_expression),
                    func.lower(Logradouro.nom_bairro).like(search_expression),
                    func.lower(Logradouro.num_cep).like(search_expression),
                    Logradouro.localidade.has(func.lower(Localidade.nom_localidade).like(search_expression)),
                    func.lower(column('cod_logradouro').cast(String)).like(search_expression)
                )
                query = query.filter(Logradouro.ind_excluido == 0).filter(
                    filter_condition)  # Filtro de exclusão
                count_query = count_query.filter(Logradouro.ind_excluido == 0).filter(
                    filter_condition)  # Filtro de exclusão
                logging.debug(f"Consulta após filtro global: {str(query.statement)}")
                logging.debug(f"Consulta de contagem após filtro global: {str(count_query.statement)}")

            # Apply column-specific filtering
            columns = ['codigo', 'nome', 'bairro', 'cep', 'localidade']  # Column names for filtering
            for i, col_name in enumerate(columns):
                col_search_value = self.request.get(f'columns[{i}][search][value]', '').lower()
                if col_search_value:
                    col_search_expression = "%{}%".format(normalize_string(col_search_value))
                    if col_name == 'codigo':
                        # Filtragem para a coluna 'codigo'
                        query = query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            func.lower(column('cod_logradouro').cast(String)).like(col_search_expression))
                        count_query = count_query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            func.lower(column('cod_logradouro').cast(String)).like(col_search_expression))
                        logging.debug(f"Consulta após filtro de codigo: {str(query.statement)}")
                        logging.debug(f"Consulta de contagem após filtro de codigo: {str(count_query.statement)}")
                    elif col_name == 'nome':
                        query = query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            func.lower(Logradouro.nom_logradouro).like(col_search_expression))
                        count_query = count_query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            func.lower(Logradouro.nom_logradouro).like(col_search_expression))
                        logging.debug(f"Consulta após filtro de nome: {str(query.statement)}")
                        logging.debug(f"Consulta de contagem após filtro de nome: {str(count_query.statement)}")
                    elif col_name == 'bairro':
                        query = query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            func.lower(Logradouro.nom_bairro).like(col_search_expression))
                        count_query = count_query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            func.lower(Logradouro.nom_bairro).like(col_search_expression))
                        logging.debug(f"Consulta após filtro de bairro: {str(query.statement)}")
                        logging.debug(f"Consulta de contagem após filtro de bairro: {str(count_query.statement)}")
                    elif col_name == 'cep':
                        query = query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            func.lower(Logradouro.num_cep).like(col_search_expression))
                        count_query = count_query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            func.lower(Logradouro.num_cep).like(col_search_expression))
                        logging.debug(f"Consulta após filtro de cep: {str(query.statement)}")
                        logging.debug(f"Consulta de contagem após filtro de cep: {str(count_query.statement)}")
                    elif col_name == 'localidade':
                        # Filtragem usando o relacionamento
                        query = query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            Logradouro.localidade.has(
                                func.lower(Localidade.nom_localidade).like(col_search_expression)))
                        count_query = count_query.filter(Logradouro.ind_excluido == 0).filter(  # Filtro de exclusão
                            Logradouro.localidade.has(
                                func.lower(Localidade.nom_localidade).like(col_search_expression)))
                        logging.debug(f"Consulta após filtro de localidade: {str(query.statement)}")
                        logging.debug(
                            f"Consulta de contagem após filtro de localidade: {str(count_query.statement)}")

            # Apply default ordering by Nome (disregarding special characters)
            order_column_index = self.request.get('order[0][column]')
            order_direction = self.request.get('order[0][dir]', 'asc')
            logging.debug(f"Índice da coluna para ordenação: {order_column_index}")
            logging.debug(f"Direção da ordenação: {order_direction}")

            if order_column_index is None:
                query = query.order_by(func.lower(Logradouro.nom_logradouro))
            else:
                order_column_index = int(order_column_index)
                order_columns = ['cod_logradouro', 'nom_logradouro', 'nom_bairro', 'num_cep',
                                 'localidade.nom_localidade']  # Adjusted for the client-side columns

                if order_column_index < len(order_columns):
                    order_by_column = order_columns[order_column_index]
                    if order_by_column:
                        if '.' in order_by_column:
                            related_table, related_column = order_by_column.split('.')
                            if related_table == 'localidade':
                                # Corrigido aqui: Use Logradouro.localidade para acessar a relação
                                order_attr = getattr(Logradouro.localidade, related_column, None)
                                if order_attr is not None:
                                    normalized_order_attr = func.lower(order_attr)
                                    if order_direction == 'desc':
                                        query = query.order_by(normalized_order_attr.desc())
                                    else:
                                        query = query.order_by(normalized_order_attr)
                        elif order_by_column == 'nom_logradouro':
                            normalized_order_attr = func.lower(Logradouro.nom_logradouro)
                            if order_direction == 'desc':
                                query = query.order_by(normalized_order_attr.desc())
                            else:
                                query = query.order_by(normalized_order_attr)
                        elif order_by_column == 'nom_bairro':
                            normalized_order_attr = func.lower(Logradouro.nom_bairro)
                            if order_direction == 'desc':
                                query = query.order_by(normalized_order_attr.desc())
                            else:
                                query = query.order_by(normalized_order_attr)
                        elif order_by_column == 'num_cep':
                            normalized_order_attr = func.lower(Logradouro.num_cep)
                            if order_direction == 'desc':
                                query = query.order_by(normalized_order_attr.desc())
                            else:
                                query = query.order_by(normalized_order_attr)

            # Apply pagination to the data retrieval query
            logradouros = query.offset(start).limit(length).all()
            logging.debug(f"Consulta final para paginação: {str(query.statement)}")

            # Get total filtered records using the count_query
            records_filtered = count_query.count()
            logging.debug(f"Consulta final para contagem: {str(count_query.statement)}")

            # Format data for DataTables
            data = [
                [
                    logr.cod_logradouro,
                    logr.nom_logradouro,
                    logr.nom_bairro,
                    logr.num_cep,
                    logr.localidade.nom_localidade if logr.localidade else None
                ]
                for logr in logradouros
            ]

            response_data = {
                'draw': draw,
                'recordsTotal': session.query(Logradouro).filter(Logradouro.ind_excluido == 0).count(),
                'recordsFiltered': records_filtered,
                'data': data
            }
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(response_data, ensure_ascii=False)
        except exc.SQLAlchemyError as e:
            logging.error(f"Erro ao acessar o banco de dados: {e}")
            session.rollback()  # Importante em caso de erro!
            self.request.response.status = 500
            return json.dumps({'error': 'Erro ao acessar os dados'}, ensure_ascii=False)
        finally:
            session.close()


class LogradouroTableViewExportBase(grok.View):
    grok.context(Interface)
    grok.require('zope2.Public')
    grok_component_name = None  # Make it explicitly non-registrable

    def __init__(self, context, request):
        super().__init__(context, request)
        self.data_to_export = None
        self.columns_to_export = None

    @staticmethod
    def get_data_query(request, default_order_by='nom_logradouro', default_order_direction='asc'):
        """
        Builds the SQLAlchemy query with filters and ordering for export.
        """
        session = Session()
        try:
            search_value = request.get('search[value]', '').lower()
            order_column_index = request.get('order[0][column]')
            order_direction = request.get('order[0][dir]')

            logging.debug(f"Parâmetros da requisição de exportação: {request.form}")

            # Base query with explicit joins and selecting specific columns
            query = session.query(Logradouro.nom_logradouro, Logradouro.nom_bairro, Logradouro.num_cep,
                                  Localidade.nom_localidade) \
                .join(Logradouro.localidade) \
                .filter(Logradouro.ind_excluido == 0)  # Filtro inicial
            logging.debug(f"Consulta exportar inicial: {str(query.statement)}")

            # Apply global filtering
            if search_value:
                search_expression = "%{}%".format(normalize_string(search_value))
                filter_condition = or_(
                    func.lower(Logradouro.nom_logradouro).like(search_expression),
                    func.lower(Logradouro.nom_bairro).like(search_expression),
                    func.lower(Logradouro.num_cep).like(search_expression),
                    func.lower(Localidade.nom_localidade).like(search_expression),
                    func.lower(column('cod_logradouro').cast(String)).like(search_expression)
                )
                query = query.filter(Logradouro.ind_excluido == 0).filter(
                    filter_condition)  # Filtro de exclusão
                logging.debug(f"Consulta exportar após filtro global: {str(query.statement)}")

            # Apply column-specific filtering
            column_indices_map = {
                '1': 'nome',  # '1' vem do DataTables (índice da coluna nome)
                '2': 'bairro',  # '2' vem do DataTables (índice da coluna bairro)
                '3': 'cep',  # '3' vem do DataTables (índice da coluna cep)
                '4': 'localidade'  # '4' vem do DataTables (índice da coluna localidade)
            }

            # Apply column-specific filtering
            for i_str, col_name in column_indices_map.items():
                col_search_value = request.get(f'columns[{i_str}][search][value]', '').lower()
                logging.debug(f"Valor de columns[{i_str}][search][value] para exportação: {col_search_value}")
                if col_search_value:
                    col_search_expression = "%{}%".format(normalize_string(col_search_value))
                    if col_name == 'nome':
                        query = query.filter(Logradouro.ind_excluido == 0).filter(
                            func.lower(Logradouro.nom_logradouro).like(col_search_expression))
                        logging.debug(f"Consulta exportar após filtro de nome: {str(query.statement)}")
                    elif col_name == 'bairro':
                        query = query.filter(Logradouro.ind_excluido == 0).filter(
                            func.lower(Logradouro.nom_bairro).like(col_search_expression))
                        logging.debug(f"Consulta exportar após filtro de bairro: {str(query.statement)}")
                    elif col_name == 'cep':
                        query = query.filter(Logradouro.ind_excluido == 0).filter(
                            func.lower(Logradouro.num_cep).like(col_search_expression))
                        logging.debug(f"Consulta exportar após filtro de cep: {str(query.statement)}")
                    elif col_name == 'localidade':
                        query = query.filter(Logradouro.ind_excluido == 0).join(Logradouro.localidade).filter(
                            func.lower(Localidade.nom_localidade).like(col_search_expression))
                        logging.debug(f"Consulta exportar após filtro de localidade: {str(query.statement)}")

            # Apply ordering
            if order_column_index is not None:
                order_columns_map = {
                    '0': func.lower(Logradouro.nom_logradouro),
                    '1': func.lower(Logradouro.nom_bairro),
                    '2': func.lower(Logradouro.num_cep),
                    '3': func.lower(Localidade.nom_localidade),
                }
                if order_column_index in order_columns_map:
                    order_attr = order_columns_map[order_column_index]
                    if order_direction == 'desc':
                        query = query.order_by(order_attr.desc())
                    else:
                        query = query.order_by(order_attr)
            else:
                # Apply default ordering
                if default_order_by == 'nom_logradouro':
                    order_attr = func.lower(Logradouro.nom_logradouro)
                elif default_order_by == 'nom_bairro':
                    order_attr = func.lower(Logradouro.nom_bairro)
                elif default_order_by == 'num_cep':
                    order_attr = func.lower(Logradouro.num_cep)
                elif default_order_by == 'nom_localidade':
                    order_attr = func.lower(Localidade.nom_localidade)
                else:
                    order_attr = func.lower(Logradouro.nom_logradouro)  # Default to nome

                if default_order_direction == 'desc':
                    query = query.order_by(order_attr.desc())
                else:
                    query = query.order_by(order_attr)

            data_to_export = query.all()
            logging.debug(f"Consulta exportar final: {str(query.statement)}")
            columns_to_export = ['Nome', 'Bairro', 'CEP', 'Localidade']
            return data_to_export, columns_to_export
        except exc.SQLAlchemyError as e:
            logging.error(f"Erro ao preparar dados para exportação: {e}")
            raise  # Re-lança a exceção para ser tratada pelo chamador
        finally:
            session.close()

    @staticmethod
    def render(data, columns, request):
        """
        This method must be overridden in subclasses to provide the specific
        export rendering logic (CSV, Excel, PDF).
        """
        raise NotImplementedError("Subclasses must implement the 'render' method.")


@implementer(ILogradouroTableViewExporter)
class LogradouroTableViewExportCSV(LogradouroTableViewExportBase):
    grok.name('exportar_logradouros_csv')

    def render(self):
        data, columns = LogradouroTableViewExportBase.get_data_query(self.request)
        # Prepare data for CSV
        header = columns
        csv_data = [header]
        for nom_logradouro, nom_bairro, num_cep, nom_localidade in data:
            csv_data.append([nom_logradouro, nom_bairro, num_cep, nom_localidade])

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerows(csv_data)
        csv_output = output.getvalue()

        self.request.response.setHeader('Content-Type', 'text/csv')
        self.request.response.setHeader('Content-Disposition', 'attachment;filename="logradouros.csv"')
        return csv_output


@implementer(ILogradouroTableViewExporter)
class LogradouroTableViewExportExcel(LogradouroTableViewExportBase):
    grok.name('exportar_logradouros_excel')

    def render(self):
        data, columns = LogradouroTableViewExportBase.get_data_query(self.request)
        # Prepare data for Excel
        header = columns
        excel_data = [header]
        for nom_logradouro, nom_bairro, num_cep, nom_localidade in data:
            excel_data.append([nom_logradouro, nom_bairro, num_cep, nom_localidade])

        wb = openpyxl.Workbook()
        sheet = wb.active

        for row in excel_data:
            sheet.append(row)

        # Use BytesIO to save the workbook in memory
        output = io.BytesIO()
        wb.save(output)
        excel_output = output.getvalue()

        self.request.response.setHeader('Content-Type',
                                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.request.response.setHeader('Content-Disposition', 'attachment;filename="logradouros.xlsx"')
        return excel_output


@implementer(ILogradouroTableViewExporter)
class LogradouroTableViewExportPDF(LogradouroTableViewExportBase):
    grok.name('exportar_logradouros_pdf')

    def render(self):
        data, columns = LogradouroTableViewExportBase.get_data_query(self.request)
        # Prepare data for PDF
        header = columns
        pdf_data = [header]
        for nom_logradouro, nom_bairro, num_cep, nom_localidade in data:
            pdf_data.append([nom_logradouro, nom_bairro, num_cep, nom_localidade])

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=(A4[1], A4[0]))
        styles = getSampleStyleSheet()
        table_data = []
        for row in pdf_data:
            table_data.append(row)

        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
        ]))

        doc.build([table])

        self.request.response.setHeader('Content-Type', 'application/pdf')
        self.request.response.setHeader('Content-Disposition', 'inline;filename="logradouros.pdf"')
        return output.getvalue()


def get_column_by_name(model, column_name):
    """Helper function to get SQLAlchemy column attribute by name."""
    if '.' in column_name:
        related_table_name, related_column_name = column_name.split('.')
        if hasattr(model, related_table_name):
            related_attr = getattr(model, related_table_name)
            if hasattr(related_attr.property.argument(), related_column_name):
                return getattr(related_attr.property.argument(), related_column_name)
    elif hasattr(model, column_name):
        return getattr(model, column_name)
    return None
