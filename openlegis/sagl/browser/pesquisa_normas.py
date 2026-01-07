# -*- coding: utf-8 -*-
from five import grok
from zope.interface import Interface
from z3c.saconfig import named_scoped_session
from openlegis.sagl.models.models import (
    NormaJuridica, TipoNormaJuridica, TipoSituacaoNorma, VinculoNormaJuridica, TipoVinculoNorma
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
from threading import local

logger = logging.getLogger(__name__)
Session = named_scoped_session('minha_sessao')

# Cache simples em memória para mapa de assuntos (thread-local para segurança)
_thread_local = local()

def _get_mapa_assunto_cached(session):
    """
    Retorna o mapa de assuntos com cache simples.
    O cache é invalidado a cada requisição (thread-local).
    """
    if not hasattr(_thread_local, 'mapa_assunto_cache'):
        _thread_local.mapa_assunto_cache = {
            str(row[0]): row[1] for row in session.execute(
                text("SELECT cod_assunto, des_assunto FROM assunto_norma WHERE ind_excluido=0")
            )
        }
    return _thread_local.mapa_assunto_cache

def _clear_mapa_assunto_cache():
    """Limpa o cache de assuntos (útil para testes ou quando necessário)"""
    if hasattr(_thread_local, 'mapa_assunto_cache'):
        delattr(_thread_local, 'mapa_assunto_cache')

def _is_operador_norma(mtool):
    """
    Verifica se o usuário autenticado tem perfil de operador de normas.
    
    Considera como operador os perfis:
    - 'Operador'
    - 'Operador Norma'
    
    Args:
        mtool: Portal membership tool
        
    Returns:
        bool: True se o usuário é operador, False caso contrário
    """
    if mtool.isAnonymousUser():
        return False
    member = mtool.getAuthenticatedMember()
    return member.has_role(['Operador', 'Operador Norma'])


def normalize(text):
    if not text:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()


def _filter_monosyllabic_words(palavras):
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
        palavras_filtradas.append(palavra)
    
    return palavras_filtradas


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
                # Abordagem Híbrida: Remove caracteres especiais e prepara termos
                termos_limpos = re.sub(r'[^\w\s]', ' ', termo)
                termos_limpos = ' '.join(termos_limpos.split())  # Remove espaços múltiplos
                
                if not termos_limpos:
                    return query
                
                palavras = termos_limpos.split()
                # Filtrar stop words e palavras muito curtas
                palavras_filtradas = _filter_monosyllabic_words(palavras)
                if not palavras_filtradas:
                    return query
                
                # Para cada palavra, criar condição que busca em qualquer campo
                # OTIMIZAÇÃO: Se a palavra tem 3+ caracteres, usar busca que pode aproveitar índices
                condicoes_por_palavra = []
                for palavra in palavras_filtradas:
                    # Para palavras curtas, usar busca com wildcards (não usa índice mas necessário)
                    # Para palavras maiores, tentar otimizar quando possível
                    if len(palavra) >= 3:
                        # Tentar usar busca que pode aproveitar índices quando o termo começa sem wildcard
                        # Mas ainda usar ilike para garantir compatibilidade
                        palavra_term = f"%{palavra}%"
                    else:
                        palavra_term = f"%{palavra}%"
                    
                    condicao_palavra = or_(
                        NormaJuridica.txt_ementa.ilike(palavra_term),
                        NormaJuridica.txt_indexacao.ilike(palavra_term),
                        NormaJuridica.txt_observacao.ilike(palavra_term)
                    )
                    condicoes_por_palavra.append(condicao_palavra)
                
                # ESTRATÉGIA: Buscar frase completa OU todas as palavras (AND)
                # - Frase completa: para resultados exatos (prioridade)
                # - Todas as palavras (AND): garante que todas as palavras digitadas estejam presentes
                # Isso garante relevância: resultados devem conter todas as palavras importantes
                frase_completa_term = f"%{termos_limpos}%"
                condicao_frase_completa = or_(
                    NormaJuridica.txt_ementa.ilike(frase_completa_term),
                    NormaJuridica.txt_indexacao.ilike(frase_completa_term),
                    NormaJuridica.txt_observacao.ilike(frase_completa_term)
                )
                query = query.filter(or_(condicao_frase_completa, and_(*condicoes_por_palavra)))
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
        # Filtro por assunto (apenas um assunto por vez)
        if (cod_assunto := request.get('lst_assunto_norma')):
            # Processar apenas um assunto (pode vir como string ou lista com um único elemento)
            if isinstance(cod_assunto, list):
                cod_assunto = cod_assunto[0] if cod_assunto else None
            if cod_assunto:
                c_clean = str(cod_assunto).strip()
                if c_clean and c_clean != '1':
                    # Buscar o código em qualquer posição: pode estar no início, meio ou fim
                    # O campo cod_assunto é CHAR(16) e armazena valores separados por vírgula, possivelmente com vírgulas no início/fim
                    query = query.filter(
                        or_(
                            NormaJuridica.cod_assunto.like(f'%,{c_clean},%'),  # No meio: ,{c},
                            NormaJuridica.cod_assunto.like(f'%,{c_clean}'),    # No final: ,{c}
                            NormaJuridica.cod_assunto.like(f'{c_clean},%'),    # No início: {c},
                            NormaJuridica.cod_assunto.like(f'{c_clean}')       # Valor único: {c}
                        )
                    )
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

    def _format_results(self, results_raw, mapa_assunto, session, contadores_normas_relacionadas=None):
        """
        Formata os resultados das normas.
        
        Args:
            results_raw: Lista de objetos NormaJuridica
            mapa_assunto: Dicionário com mapeamento de códigos de assunto para descrições
            session: Sessão do SQLAlchemy
            contadores_normas_relacionadas: Dicionário opcional com contadores pré-calculados
                                          {cod_norma: quantidade} para evitar N+1 queries
        """
        formatted = []
        portal_url = getToolByName(self.context, 'portal_url')()
        mtool = getToolByName(self.context, 'portal_membership')
        is_operador = _is_operador_norma(mtool)
        docs_folder = self.context.sapl_documentos.norma_juridica
        
        # Se contadores não foram fornecidos, buscar todos de uma vez (evita N+1)
        if contadores_normas_relacionadas is None:
            cods_normas = [n.cod_norma for n in results_raw]
            if cods_normas:
                contadores_query = session.query(
                    VinculoNormaJuridica.cod_norma_referida,
                    func.count(VinculoNormaJuridica.cod_vinculo).label('qtd')
                ).filter(
                    VinculoNormaJuridica.cod_norma_referida.in_(cods_normas),
                    VinculoNormaJuridica.ind_excluido == 0
                ).group_by(VinculoNormaJuridica.cod_norma_referida).all()
                contadores_normas_relacionadas = {row[0]: row[1] for row in contadores_query}
            else:
                contadores_normas_relacionadas = {}
        
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
                'url_pasta_digital': None,
            }
            texto_integral_pdf = f"{norma.cod_norma}_texto_integral.pdf"
            if hasattr(docs_folder, texto_integral_pdf):
                item['url_texto_integral'] = f"{portal_url}/pysc/download_norma_pysc?cod_norma={norma.cod_norma}&texto_original=1"
                # Adicionar link para pasta digital apenas para usuários autenticados
                if not mtool.isAnonymousUser():
                    item['url_pasta_digital'] = f"{portal_url}/@@pasta_digital_norma?cod_norma={norma.cod_norma}&action=pasta"
            texto_consolidado_pdf = f"{norma.cod_norma}_texto_consolidado.pdf"
            if hasattr(docs_folder, texto_consolidado_pdf):
                item['url_texto_consolidado'] = f"{portal_url}/pysc/download_norma_pysc?cod_norma={norma.cod_norma}&texto_consolidado=1"
            codigos = [c.strip() for c in (norma.cod_assunto or '').split(',') if c.strip() and c.strip() != '1']
            item['assunto'] = ", ".join([mapa_assunto.get(c, c) for c in codigos])
            
            # Usar contador pré-calculado (evita N+1 queries)
            item['qtd_normas_relacionadas'] = contadores_normas_relacionadas.get(norma.cod_norma, 0)
            
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
            # Usar cache para mapa de assuntos
            mapa_assunto = _get_mapa_assunto_cached(session)
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
                
                # Pré-calcular contadores de normas relacionadas para evitar N+1 queries
                cods_normas_export = [n.cod_norma for n in results_raw]
                contadores_normas_relacionadas = {}
                if cods_normas_export:
                    contadores_query = session.query(
                        VinculoNormaJuridica.cod_norma_referida,
                        func.count(VinculoNormaJuridica.cod_vinculo).label('qtd')
                    ).filter(
                        VinculoNormaJuridica.cod_norma_referida.in_(cods_normas_export),
                        VinculoNormaJuridica.ind_excluido == 0
                    ).group_by(VinculoNormaJuridica.cod_norma_referida).all()
                    contadores_normas_relacionadas = {row[0]: row[1] for row in contadores_query}
                
                results_formatted = self._format_results(
                    results_raw, 
                    mapa_assunto, 
                    session,
                    contadores_normas_relacionadas
                )
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
            
            # Estatísticas por assunto - OTIMIZADO: usa SQL ao invés de carregar todas as normas
            # Buscar apenas cod_norma e cod_assunto (campos necessários) para reduzir uso de memória
            stats_by_assunto = {}
            normas_query = query.with_entities(NormaJuridica.cod_norma, NormaJuridica.cod_assunto).all()
            normas_sem_assunto = 0
            
            for cod_norma, cod_assunto in normas_query:
                if not cod_assunto or str(cod_assunto).strip() == '':
                    normas_sem_assunto += 1
                else:
                    codigos = [c.strip() for c in str(cod_assunto).split(',') if c.strip() and c.strip() != '1']
                    if codigos:
                        # Contar a norma apenas no primeiro assunto válido para que o total bata
                        cod = codigos[0]
                        if cod:
                            assunto_desc = mapa_assunto.get(cod, f'Assunto {cod}')
                            stats_by_assunto[assunto_desc] = stats_by_assunto.get(assunto_desc, 0) + 1
                    else:
                        normas_sem_assunto += 1
            
            # Adicionar "Não classficada" se houver normas sem assunto
            if normas_sem_assunto > 0:
                stats_by_assunto['Não classficada'] = normas_sem_assunto
            
            # Ordenar por quantidade (decrescente)
            stats_by_assunto = dict(sorted(stats_by_assunto.items(), key=lambda x: x[1], reverse=True))
            page = int(self.request.get('pagina', 1))
            page_size = min(max(int(self.request.get('itens_por_pagina', 10)), 1), 100)
            
            # Buscar resultados paginados
            results_paginados = ordered_query.offset((page - 1) * page_size).limit(page_size).all()
            
            # Pré-calcular contadores de normas relacionadas para evitar N+1 queries
            cods_normas_paginadas = [n.cod_norma for n in results_paginados]
            contadores_normas_relacionadas = {}
            if cods_normas_paginadas:
                contadores_query = session.query(
                    VinculoNormaJuridica.cod_norma_referida,
                    func.count(VinculoNormaJuridica.cod_vinculo).label('qtd')
                ).filter(
                    VinculoNormaJuridica.cod_norma_referida.in_(cods_normas_paginadas),
                    VinculoNormaJuridica.ind_excluido == 0
                ).group_by(VinculoNormaJuridica.cod_norma_referida).all()
                contadores_normas_relacionadas = {row[0]: row[1] for row in contadores_query}
            
            data = {
                'data': self._format_results(
                    results_paginados,
                    mapa_assunto,
                    session,
                    contadores_normas_relacionadas
                ),
                'total': total_count,
                'page': page,
                'per_page': page_size,
                'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0,
                'has_previous': page > 1,
                'has_next': page < ((total_count + page_size - 1) // page_size if total_count > 0 else 0),
                'stats': stats,
                'stats_by_assunto': stats_by_assunto
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


class NormasRelacionadasJSON(grok.View):
    grok.context(Interface)
    grok.name('normas_relacionadas_json')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        try:
            cod_norma = self.request.get('cod_norma')
            if not cod_norma:
                self.request.response.setStatus(400)
                return json.dumps({'error': 'cod_norma é obrigatório'})
            
            try:
                cod_norma = int(cod_norma)
            except ValueError:
                self.request.response.setStatus(400)
                return json.dumps({'error': 'cod_norma deve ser um número'})
            
            # Buscar normas relacionadas (que alteraram esta norma)
            # cod_norma_referida = norma que foi alterada
            # cod_norma_referente = norma que alterou
            normas_relacionadas = session.query(
                NormaJuridica,
                TipoNormaJuridica,
                TipoVinculoNorma
            ).join(
                VinculoNormaJuridica,
                VinculoNormaJuridica.cod_norma_referente == NormaJuridica.cod_norma
            ).join(
                TipoNormaJuridica,
                NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma
            ).join(
                TipoVinculoNorma,
                VinculoNormaJuridica.tip_vinculo == TipoVinculoNorma.tipo_vinculo
            ).filter(
                VinculoNormaJuridica.cod_norma_referida == cod_norma,
                VinculoNormaJuridica.ind_excluido == 0,
                NormaJuridica.ind_excluido == 0,
                TipoVinculoNorma.ind_excluido == 0
            ).all()
            
            portal_url = getToolByName(self.context, 'portal_url')()
            mtool = getToolByName(self.context, 'portal_membership')
            is_operador = _is_operador_norma(mtool)
            
            resultado = []
            for norma, tipo_norma, tipo_vinculo in normas_relacionadas:
                detail_url = f"{portal_url}/{'cadastros' if is_operador else 'consultas'}/norma_juridica/norma_juridica_mostrar_proc?cod_norma={norma.cod_norma}"
                resultado.append({
                    'cod_norma': norma.cod_norma,
                    'sgl_tipo_norma': tipo_norma.sgl_tipo_norma if tipo_norma else '',
                    'des_tipo_norma': tipo_norma.des_tipo_norma if tipo_norma else '',
                    'num_norma': norma.num_norma,
                    'ano_norma': norma.ano_norma,
                    'txt_ementa': norma.txt_ementa or '',
                    'des_vinculo': tipo_vinculo.des_vinculo if tipo_vinculo else '',
                    'detail_url': detail_url
                })
            
            self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({'normas_relacionadas': resultado}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro em NormasRelacionadasJSON: {str(e)}", exc_info=True)
            self.request.response.setStatus(500)
            return json.dumps({
                'error': 'Erro interno ao processar a requisição',
                'details': str(e)
            })
        finally:
            session.close()
