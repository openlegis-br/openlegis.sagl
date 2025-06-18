# -*- coding: utf-8 -*-
from five import grok
from zope.interface import Interface
from z3c.saconfig import named_scoped_session
from openlegis.sagl.models.models import (
    NormaJuridica, TipoNormaJuridica, TipoSituacaoNorma
)
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_, func, cast, String, text, asc, desc
from sqlalchemy.sql import expression
from datetime import datetime
import json
import unicodedata
import io
import csv
import openpyxl
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
import re
import logging
from Products.CMFCore.utils import getToolByName
from Products.AdvancedQuery import Or, Eq

logger = logging.getLogger(__name__)
Session = named_scoped_session('minha_sessao')


def normalize(text):
    if not text:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()


def parse_date(value):
    try:
        return datetime.strptime(value, '%d/%m/%Y')
    except (ValueError, TypeError):
        return None


class NormasTableView(grok.View):
    grok.context(Interface)
    grok.name('normas_table_json')
    grok.require('zope2.View')

    def _build_query(self, session):
        request = self.request
        query = session.query(NormaJuridica).options(
            joinedload(NormaJuridica.tipo_norma_juridica),
            joinedload(NormaJuridica.tipo_situacao_norma),
        )
        query = query.filter(NormaJuridica.ind_excluido == 0)
        mtool = getToolByName(self.context, 'portal_membership')
        if mtool.isAnonymousUser():
            query = query.filter(NormaJuridica.ind_publico == 1)
        termo = request.get('txt_assunto')
        if termo:
            if str(request.get('chk_textual')).lower() in ('on', 'true', '1'):
                try:
                    sapl_doc = self.context.restrictedTraverse('sapl_documentos/norma_juridica')
                    catalog = sapl_doc.Catalog
                    zope_query = Or(Eq('ementa', termo), Eq('PrincipiaSearchSource', termo))
                    results = catalog.evalAdvancedQuery(zope_query)
                    cods = []
                    for r in results:
                        item_id_raw = r.id
                        if isinstance(item_id_raw, str):
                            match = re.match(r'^\d+', item_id_raw)
                            if match:
                                cods.append(int(match.group(0)))
                        elif isinstance(item_id_raw, int):
                            cods.append(item_id_raw)
                    if cods:
                        if len(cods) > 500:
                            logger.warning("Busca textual retornou muitos resultados; limitando a 500 normas.")
                            cods = cods[:500]
                        query = query.filter(NormaJuridica.cod_norma.in_(cods))
                    else:
                        query = query.filter(expression.false())
                except Exception as e:
                    logger.error(f"Erro na busca textual via Catálogo Zope: {str(e)}", exc_info=True)
                    return query.filter(expression.false())
            else:
                like_term = f"%{termo}%"
                query = query.filter(or_(
                    NormaJuridica.txt_ementa.ilike(like_term),
                    NormaJuridica.txt_indexacao.ilike(like_term),
                    NormaJuridica.txt_observacao.ilike(like_term)
                ))
        if (tipos := request.get('lst_tip_norma')):
            if isinstance(tipos, str):
                tipos = tipos.split(',')
            query = query.filter(NormaJuridica.tip_norma.in_(tipos))
        if (numero := request.get('txt_numero')):
            try:
                query = query.filter(NormaJuridica.num_norma == int(numero))
            except Exception:
                pass
        if (ano := request.get('txt_ano')):
            try:
                query = query.filter(NormaJuridica.ano_norma == int(ano))
            except Exception:
                pass
        if (cod_assunto := request.get('lst_assunto_norma')):
            if isinstance(cod_assunto, str):
                codigos = [v.strip() for v in cod_assunto.split(',') if v.strip() and v.strip() != '1']
            elif isinstance(cod_assunto, list):
                codigos = [str(v).strip() for v in cod_assunto if str(v).strip() and str(v).strip() != '1']
            else:
                codigos = []
            # Monta filtro dinâmico (aceita qualquer posição, considerando campo tipo ",1,2,5,")
            if codigos:
                filters = [NormaJuridica.cod_assunto.like(f'%,{c},%') for c in codigos]
                query = query.filter(or_(*filters))
        if (sit := request.get('lst_tip_situacao_norma')):
            try:
                query = query.filter(NormaJuridica.cod_situacao == int(sit))
            except Exception:
                pass
        if (dt_ini := parse_date(request.get('dt_norma'))):
            query = query.filter(NormaJuridica.dat_norma >= dt_ini)
        if (dt_fim := parse_date(request.get('dt_norma2'))):
            query = query.filter(NormaJuridica.dat_norma <= dt_fim)
        if (pub_ini := parse_date(request.get('dt_public'))):
            query = query.filter(NormaJuridica.dat_publicacao >= pub_ini)
        if (pub_fim := parse_date(request.get('dt_public2'))):
            query = query.filter(NormaJuridica.dat_publicacao <= pub_fim)
        return query

    def _apply_ordering(self, query):
        ordem_campo = self.request.get('ordem_campo')
        ordem_direcao = self.request.get('ordem_direcao', 'asc')
        rd_ordem = self.request.get('rd_ordem', '1')  # 1: mais recentes, 0: mais antigos
        colunas = {
            'des_tipo_norma': TipoNormaJuridica.des_tipo_norma,
            'num_norma': NormaJuridica.num_norma,
            'ano_norma': NormaJuridica.ano_norma,
            'txt_ementa': NormaJuridica.txt_ementa,
            'dat_norma': NormaJuridica.dat_norma,
            'situacao': TipoSituacaoNorma.des_tipo_situacao,
            'dat_publicacao': NormaJuridica.dat_publicacao,
        }
        if ordem_campo and ordem_campo in colunas:
            coluna_ordenacao = colunas[ordem_campo]
            if ordem_campo == 'des_tipo_norma':
                query = query.join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)
            elif ordem_campo == 'situacao':
                query = query.join(TipoSituacaoNorma, NormaJuridica.cod_situacao == TipoSituacaoNorma.tip_situacao_norma)
            direcao = desc if ordem_direcao == 'desc' else asc
            query = query.order_by(
                direcao(coluna_ordenacao),
                desc(NormaJuridica.ano_norma),
                desc(NormaJuridica.num_norma)
            )
        else:
            if rd_ordem == '0':
                query = query.order_by(
                    asc(NormaJuridica.ano_norma),
                    asc(func.lpad(cast(NormaJuridica.num_norma, String), 6, '0'))
                )
            else:
                query = query.order_by(
                    desc(NormaJuridica.ano_norma),
                    desc(func.lpad(cast(NormaJuridica.num_norma, String), 6, '0'))
                )
        return query

    def _format_results(self, results_raw, mapa_assunto):
        formatted = []
        portal_url = getToolByName(self.context, 'portal_url')()
        mtool = getToolByName(self.context, 'portal_membership')
        is_operador = mtool.getAuthenticatedMember().has_role(['Operador', 'Operador Norma'])
        docs_folder = self.context.sapl_documentos.norma_juridica
        for norma in results_raw:
            tipo_norma = norma.tipo_norma_juridica
            situacao = norma.tipo_situacao_norma
            detail_url = f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/norma_juridica/norma_juridica_mostrar_proc?cod_norma={norma.cod_norma}"
            item = {
                'cod_norma': norma.cod_norma,
                'des_tipo_norma': tipo_norma.des_tipo_norma if tipo_norma else '',
                'num_norma': norma.num_norma,
                'ano_norma': norma.ano_norma,
                'txt_ementa': norma.txt_ementa or '',
                'dat_norma': norma.dat_norma.strftime('%d/%m/%Y') if norma.dat_norma else '',
                'dat_publicacao': norma.dat_publicacao.strftime('%d/%m/%Y') if norma.dat_publicacao else '',
                'situacao': situacao.des_tipo_situacao if situacao else '',
                'detail_url': detail_url,
                'url_texto_integral': None,
                'url_redacao_final': None,
            }
            texto_integral_pdf = f"{norma.cod_norma}_texto_integral.pdf"
            if hasattr(docs_folder, texto_integral_pdf):
                item['url_texto_integral'] = f"{portal_url}/pysc/download_norma_pysc?cod_norma={norma.cod_norma}&texto_original=1"
            texto_consolidado_pdf = f"{norma.cod_norma}_texto_consolidado.pdf"
            if hasattr(docs_folder, texto_consolidado_pdf):
                item['url_texto_consolidado'] = f"{portal_url}/pysc/download_norma_pysc?cod_norma={norma.cod_norma}&texto_consolidado=1"
            codigos = [c.strip() for c in (norma.cod_assunto or '').split(',') if c.strip() and c.strip() != '1']
            item['assunto'] = ", ".join([mapa_assunto.get(c, c) for c in codigos])
            formatted.append(item)
        return formatted

    def _export_pdf(self, formatted_for_export):
        """Gera um PDF aprimorado dos resultados de normas jurídicas no padrão moderno."""
        self.request.response.setHeader('Content-Type', 'application/pdf')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="normas_juridicas.pdf"')

        if not formatted_for_export:
            return b""

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
            title="Relatório de Normas Jurídicas"
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
        elements.append(Paragraph("RELATÓRIO DE NORMAS JURÍDICAS", styles['Title']))
        elements.append(Paragraph(f"Data de geração: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Paragraph(f"Total de registros: {len(formatted_for_export)}", styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))
        header_labels = [
            'Tipo',
            'Número/Ano',
            'Ementa',
            'Data Norma',
            'Publicação',
            'Situação',
            'Assunto'
        ]
        table_data = []
        table_data.append([Paragraph(label, header_style) for label in header_labels])
        for item in formatted_for_export:
            item['num_ano_combined'] = f"{item['num_norma']}/{item['ano_norma']}"
            row = [
                Paragraph(str(item.get('des_tipo_norma', '')), normal_style),
                Paragraph(str(item.get('num_ano_combined', '')), normal_style),
                Paragraph(str(item.get('txt_ementa', '')), normal_style),
                Paragraph(str(item.get('dat_norma', '')), normal_style),
                Paragraph(str(item.get('dat_publicacao', '')), normal_style),
                Paragraph(str(item.get('situacao', '')), normal_style),
                Paragraph(str(item.get('assunto', '')), normal_style),
            ]
            table_data.append(row)
        page_width, page_height = landscape(A4)
        content_width = page_width - doc.leftMargin - doc.rightMargin
        col_widths = [
            0.15 * content_width,  # Tipo
            0.12 * content_width,  # Número/Ano
            0.29 * content_width,  # Ementa
            0.10 * content_width,  # Data Norma
            0.10 * content_width,  # Publicação
            0.10 * content_width,  # Situação
            0.14 * content_width   # Assunto
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
            ('ALIGN', (6,1), (6,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#2F5597')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F2F2F2')]),
            ('LEFTPADDING', (0,0), (-1,-1), 3),
            ('RIGHTPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(table)
        def footer(canvas, doc_):
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            page_num = f"Página {doc_.page}"
            canvas.drawRightString(page_width - 1.5*cm, 1*cm, page_num)
            canvas.drawString(1.5*cm, 1*cm, "SAGL")
            canvas.restoreState()
        doc.build(elements, onFirstPage=footer, onLaterPages=footer)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data

    def _export_csv(self, formatted_for_export, mapa_assunto):
        output = io.StringIO()
        exportado_em = datetime.now().strftime('%d/%m/%Y %H:%M')
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['Exportado em', exportado_em])
        writer.writerow(['Tipo', 'Número', 'Ano', 'Data Norma', 'Publicação', 'Situação', 'Assunto', 'Ementa'])
        for norm in formatted_for_export:
            writer.writerow([
                norm['des_tipo_norma'],
                norm['num_norma'],
                norm['ano_norma'],
                norm['dat_norma'],
                norm['dat_publicacao'],
                norm['situacao'],
                norm['assunto'],
                norm['txt_ementa']
            ])
        self.request.response.setHeader('Content-Type', 'text/csv; charset=utf-8')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename=normas.csv')
        return output.getvalue().encode('utf-8-sig')

    def _export_excel(self, formatted_for_export, mapa_assunto):
        output = io.BytesIO()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Normas Jurídicas"
        exportado_em = datetime.now().strftime('%d/%m/%Y %H:%M')
        ws.append(['Exportado em', exportado_em])
        ws.append(['Tipo', 'Número', 'Ano', 'Data Norma', 'Publicação', 'Situação', 'Assunto', 'Ementa'])
        for norm in formatted_for_export:
            ws.append([
                norm['des_tipo_norma'],
                norm['num_norma'],
                norm['ano_norma'],
                norm['dat_norma'],
                norm['dat_publicacao'],
                norm['situacao'],
                norm['assunto'],
                norm['txt_ementa']
            ])
        for column in ws.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column[0].column_letter].width = adjusted_width
        wb.save(output)
        self.request.response.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename=normas.xlsx')
        return output.getvalue()

    def render(self):
        session = Session()
        try:
            mapa_assunto = {
                str(row[0]): row[1] for row in session.execute(
                    text("SELECT cod_assunto, des_assunto FROM assunto_norma WHERE ind_excluido=0")
                )
            }
            query = self._build_query(session)
            formato = self.request.get('formato', '').lower()
            ordered_query = self._apply_ordering(query)
            paginar_exportacao = self.request.get('paginar_exportacao') == '1'
            if formato in ('csv', 'excel', 'pdf'):
                if paginar_exportacao:
                    page = int(self.request.get('pagina', 1))
                    page_size = min(max(int(self.request.get('itens_por_pagina', 10)), 1), 100)
                    offset = (page - 1) * page_size
                    results_raw = ordered_query.offset(offset).limit(page_size).all()
                else:
                    results_raw = ordered_query.all()
                    if getToolByName(self.context, 'portal_membership').isAnonymousUser() and len(results_raw) > 300:
                        self.request.response.setStatus(403)
                        return json.dumps({
                            'error': 'Exportação muito grande. O limite é de 300 linhas para usuários não autenticados.',
                            'details': 'Use mais filtros ou autentique-se para exportar todos os resultados.'
                        })
                results_formatted = self._format_results(results_raw, mapa_assunto)
                if formato == 'csv':
                    return self._export_csv(results_formatted, mapa_assunto)
                elif formato == 'excel':
                    return self._export_excel(results_formatted, mapa_assunto)
                elif formato == 'pdf':
                    return self._export_pdf(results_formatted)
            total_count = query.with_entities(func.count(NormaJuridica.cod_norma.distinct())).scalar()
            stats_query = query.with_entities(
                TipoNormaJuridica.des_tipo_norma,
                func.count(NormaJuridica.cod_norma.distinct())
            ).join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma) \
             .group_by(TipoNormaJuridica.des_tipo_norma) \
             .order_by(desc(func.count(NormaJuridica.cod_norma.distinct())))
            stats = {tipo: contagem for tipo, contagem in stats_query.all()}
            page = int(self.request.get('pagina', 1))
            page_size = min(max(int(self.request.get('itens_por_pagina', 10)), 1), 100)
            data = {
                'data': self._format_results(
                    ordered_query.offset((page - 1) * page_size).limit(page_size).all(),
                    mapa_assunto
                ),
                'total': total_count,
                'page': page,
                'per_page': page_size,
                'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0,
                'has_previous': page > 1,
                'has_next': page < ((total_count + page_size - 1) // page_size if total_count > 0 else 0),
                'stats': stats
            }
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(data)
        except Exception as e:
            logger.error(f"Erro em NormasTableView: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({
                'error': 'Erro interno ao processar a requisição',
                'details': str(e)
            })
        finally:
            session.close()

# Os endpoints de tipos, situações e assuntos seguem iguais

class TiposNormaJSON(grok.View):
    grok.context(Interface)
    grok.name('tipos_norma_json')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        dados = session.query(TipoNormaJuridica)\
                      .filter_by(ind_excluido=0)\
                      .order_by(TipoNormaJuridica.des_tipo_norma)\
                      .all()
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps([
            {'id': t.tip_norma, 'descricao': t.des_tipo_norma} for t in dados
        ], ensure_ascii=False)


class SituacoesNormaJSON(grok.View):
    grok.context(Interface)
    grok.name('situacoes_norma_json')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        dados = session.query(TipoSituacaoNorma)\
                      .filter_by(ind_excluido=0)\
                      .order_by(TipoSituacaoNorma.des_tipo_situacao)\
                      .all()
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps([
            {'id': s.tip_situacao_norma, 'descricao': s.des_tipo_situacao} for s in dados
        ], ensure_ascii=False)


class AssuntosNormaJSON(grok.View):
    grok.context(Interface)
    grok.name('assuntos_norma_json')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        sql_query = text("""
            SELECT cod_assunto, des_assunto 
            FROM assunto_norma 
            WHERE ind_excluido=0 
            ORDER BY des_assunto
        """)
        dados = session.execute(sql_query).fetchall()
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps([
            {'id': str(d[0]), 'descricao': d[1]} for d in dados
        ], ensure_ascii=False)
