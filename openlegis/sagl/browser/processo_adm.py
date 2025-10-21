# -*- coding: utf-8 -*-
import os
import shutil
import time
import random
import fcntl
from io import BytesIO
from DateTime import DateTime
from five import grok
from zope.interface import Interface
import uuid
import fitz
import logging
from datetime import datetime, timedelta
import pikepdf

# ReportLab para a Folha de Cientificações
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Reuso dos estilos da Ficha de Votação (com fallback seguro)
# ------------------------------------------------------------------------------
try:
    # ajuste este import conforme a localização do módulo com a ficha de votação
    from processo_leg_integral import get_cached_styles
except Exception:
    try:
        from processo_leg_integral_view import get_cached_styles
    except Exception:
        # Fallback: cópia fiel mínima dos estilos usados
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        _style_cache = {}
        _theme_import = {
            'primary': '#003366',
            'secondary': '#E1F5FE',
            'success': '#4CAF50',
            'danger': '#F44336',
            'warning': '#FFC107',
            'light_gray': '#F5F5F5',
            'text': '#212121',
            'muted': '#757575'
        }
        def get_cached_styles():
            if not _style_cache:
                base = getSampleStyleSheet()
                _style_cache.update(base.byName)
                _style_cache.update({
                    'Header1': ParagraphStyle(
                        name='Header1', parent=base['Heading1'], fontSize=14,
                        leading=18, alignment=TA_CENTER, textColor=colors.HexColor(_theme_import['primary'])
                    ),
                    'Header2': ParagraphStyle(
                        name='Header2', parent=base['Heading2'], fontSize=11,
                        leading=13, alignment=TA_LEFT, textColor=colors.HexColor(_theme_import['primary'])
                    ),
                    'Label': ParagraphStyle(
                        name='Label', parent=base['Normal'], fontSize=9, leading=11,
                        alignment=TA_LEFT, textColor=colors.HexColor(_theme_import['muted'])
                    ),
                    'Value': ParagraphStyle(
                        name='Value', parent=base['Normal'], fontSize=9, leading=11,
                        alignment=TA_LEFT, textColor=colors.HexColor(_theme_import['text'])
                    ),
                    'VoteResult': ParagraphStyle(  # usado como faixa/banner
                        name='VoteResult', parent=base['Normal'], fontSize=12, leading=15,
                        alignment=TA_CENTER, textColor=colors.white,
                        backColor=colors.HexColor(_theme_import['primary'])
                    ),
                    'TotalizadorCabecalho': ParagraphStyle(
                        name='TotalizadorCabecalho', parent=base['Heading4'], fontSize=9,
                        leading=11, alignment=TA_CENTER, textColor=colors.white
                    ),
                    'TotalizadorConteudo': ParagraphStyle(
                        name='TotalizadorConteudo', parent=base['Normal'], fontSize=9,
                        leading=11, alignment=TA_CENTER, textColor=colors.HexColor(_theme_import['text'])
                    ),
                    'TotalizadorDestaque': ParagraphStyle(
                        name='TotalizadorDestaque', parent=base['Heading4'], fontSize=9,
                        leading=11, alignment=TA_CENTER, textColor=colors.HexColor(_theme_import['primary'])
                    ),
                })
            return _style_cache

# ------------------------------------------------------------------------------
# Paleta local para cores de células
# ------------------------------------------------------------------------------
_theme = {
    'primary': '#003366',
    'secondary': '#E1F5FE',
    'success': '#4CAF50',
    'danger':   '#F44336',
    'warning':  '#FFC107',
    'light_gray': '#F5F5F5',
    'text': '#212121',
    'muted': '#757575',
}

# ------------------------------------------------------------------------------
# Rodapé (mesmo padrão visual)
# ------------------------------------------------------------------------------
def add_footer(canvas, doc):
    canvas.saveState()
    margin_left = 15 * mm
    width, _ = doc.pagesize
    canvas.setStrokeColor(colors.HexColor(_theme['primary']))
    canvas.setLineWidth(0.5)
    canvas.line(margin_left, 40, width - margin_left, 40)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.HexColor(_theme['muted']))
    canvas.drawString(margin_left, 30, "Documento gerado eletronicamente")
    canvas.drawRightString(width - margin_left, 30, f"{DateTime().strftime('%d/%m/%Y %H:%M')} | Página {canvas.getPageNumber()}")
    canvas.restoreState()

# ------------------------------------------------------------------------------
# Cabeçalho específico da FOLHA DE CIENTIFICAÇÕES
# ------------------------------------------------------------------------------
def build_header_cientificacoes(nome_casa, styles, logo_bytes=None):
    logo_img = None
    if logo_bytes:
        try:
            logo_img = Image(BytesIO(logo_bytes), width=50, height=50)
        except Exception:
            logo_img = None

    title_para = Paragraph(f"<b>{nome_casa}</b><br/>Processo Administrativo", styles['Header1'])
    header_data = [
        [logo_img if logo_img else '', title_para, ''],
        ['', Paragraph("FOLHA DE CIENTIFICAÇÕES", styles['Header1']), '']
    ]
    header_table = Table(header_data, colWidths=[60, '*', 80])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (1,0), (1,0), 'LEFT'),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('LINEBELOW', (0,1), (-1,1), 1, colors.HexColor(_theme['primary'])),
        ('BOTTOMPADDING', (0,1), (-1,1), 10),
    ]))
    return header_table

# ------------------------------------------------------------------------------
# Sanitização de PDFs
# ------------------------------------------------------------------------------
def sanear_pdf(pdf_bytes, title=None, mod_date=None):
    def tentar_fitz(stream):
        try:
            doc = fitz.open(stream=stream, filetype="pdf")
            _ = doc.page_count
            if title or mod_date:
                md = doc.metadata or {}
                if title: md["title"] = title
                if mod_date: md["modDate"] = mod_date
                doc.set_metadata(md)
            doc.bake()
            out = BytesIO()
            doc.save(out, garbage=3, deflate=True)
            out.seek(0)
            return fitz.open(stream=out, filetype="pdf")
        except Exception as e:
            logger.warning(f"[sanear_pdf] fitz falhou: {e}")
            return None

    result = tentar_fitz(BytesIO(pdf_bytes))
    if result:
        return result

    try:
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
            out = BytesIO()
            pdf.save(out)
            out.seek(0)
            return tentar_fitz(out)
    except Exception as e:
        logger.error(f"[sanear_pdf] pikepdf falhou: {e}")
        return None

# ------------------------------------------------------------------------------
# JOIN dos nomes (cientificador/cientificado) NA VIEW
# ------------------------------------------------------------------------------
def coletar_cientificacoes_com_nomes(context, cod_documento, somente_pendentes=False):
    params = {'cod_documento': cod_documento, 'ind_excluido': 0}
    if somente_pendentes:
        params['ind_pendente'] = 1
    rows = context.zsql.cientificacao_documento_obter_zsql(**params)

    dados = []
    for r in rows:
        try:
            nom_cientificador = None
            nom_cientificado = None
            for u in context.zsql.usuario_obter_zsql(cod_usuario=r.cod_cientificador):
                nom_cientificador = getattr(u, 'nom_completo', None)
                break
            for u in context.zsql.usuario_obter_zsql(cod_usuario=r.cod_cientificado):
                nom_cientificado = getattr(u, 'nom_completo', None)
                break
            dados.append({
                'id': r.id,
                'cod_documento': r.cod_documento,
                'cod_cientificador': r.cod_cientificador,
                'nom_cientificador': nom_cientificador or '(não identificado)',
                'cod_cientificado': r.cod_cientificado,
                'nom_cientificado': nom_cientificado or '(não identificado)',
                'dat_envio': getattr(r, 'dat_envio', '') or '',
                'dat_expiracao': getattr(r, 'dat_expiracao', '') or '',
                'dat_leitura': getattr(r, 'dat_leitura', '') or '',
            })
        except Exception as e:
            logger.warning(f"[coletar_cientificacoes] id={getattr(r,'id','?')} erro: {e}")
    return dados

# ------------------------------------------------------------------------------
# Folha de Cientificações (só gera se houver dados)
# ------------------------------------------------------------------------------
def gerar_folha_cientificacao_pdf(context, cod_documento, caminho_saida, dados_cientificacoes):
    # Proteção: não gera se não houver registros
    if not dados_cientificacoes:
        logger.info(f"[cientificacoes] Nenhuma cientificação — folha não será gerada para {cod_documento}.")
        return

    styles = get_cached_styles()

    # Nome da Casa / Logo
    nome_casa = '(não definido)'
    logo_bytes = None
    try:
        props = context.sapl_documentos.props_sagl
        nome_casa = props.getProperty('nom_casa', '(não definido)')
        id_logo = props.getProperty('id_logo', None)
        if id_logo and hasattr(props, id_logo):
            logo_obj = getattr(props, id_logo)
            logo_bytes = bytes(logo_obj.data)
    except Exception:
        pass

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm, topMargin=5*mm, bottomMargin=20*mm
    )

    elements = []

    # Cabeçalho específico
    header_table = build_header_cientificacoes(nome_casa, styles, logo_bytes=logo_bytes)
    elements.append(header_table)
    elements.append(Spacer(1, 10))

    # Info do documento
    try:
        info_doc = context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento)[0]
        titulo_doc = f"{info_doc.des_tipo_documento} {info_doc.num_documento}/{info_doc.ano_documento}"
        elements.append(Paragraph(titulo_doc, styles['Header2']))
        elements.append(Spacer(1, 6))
    except Exception:
        pass

    # Banner (usa o mesmo estilo “VoteResult” como faixa azul)
    elements.append(Paragraph("LISTA DE CIENTIFICAÇÕES", styles['VoteResult']))
    elements.append(Spacer(1, 8))

    # Tabela (sem coluna ID)
    head = styles['TotalizadorCabecalho']
    cell = styles['Value']
    table_data = [[
        Paragraph("Cientificador", head),
        Paragraph("Cientificado", head),
        Paragraph("Envio", head),
        Paragraph("Expiração", head),
        Paragraph("Leitura", head),
    ]]

    total = 0
    pendentes = 0
    lidas = 0
    expiradas = 0
    now_dt = DateTime()

    for r in dados_cientificacoes:
        total += 1
        dat_envio = r.get('dat_envio', '')
        dat_exp = r.get('dat_expiracao', '')
        dat_read = r.get('dat_leitura', '')

        if dat_read:
            lidas += 1
            status_txt = dat_read
        else:
            try:
                exp_dt = DateTime(dat_exp) if dat_exp else None
                if exp_dt and now_dt > exp_dt:
                    expiradas += 1
                    status_txt = 'EXPIRADA'
                else:
                    pendentes += 1
                    status_txt = 'PENDENTE'
            except Exception:
                pendentes += 1
                status_txt = 'PENDENTE'

        table_data.append([
            Paragraph(r.get('nom_cientificador', ''), cell),
            Paragraph(r.get('nom_cientificado', ''), cell),
            Paragraph(dat_envio, cell),
            Paragraph(dat_exp, cell),
            Paragraph(status_txt, cell),
        ])

    # colWidths recalibradas para 5 colunas
    table = Table(table_data, colWidths=[140, 140, 70, 70, 70], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(_theme['primary'])),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#EEEEEE')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#FAFAFA')]),
        ('ALIGN', (0,1), (-1,-1), 'LEFT'),

        # >>> alinhamento vertical <<<
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),   # cabeçalho
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),  # linhas de dados
    ]))

    # Pintar a coluna "Leitura" por status (agora é a coluna 4)
    for i, r in enumerate(dados_cientificacoes, start=1):
        dat_read = r.get('dat_leitura', '')
        dat_exp = r.get('dat_expiracao', '')
        if dat_read:
            color_cell = colors.HexColor(_theme['success'])
        else:
            try:
                exp_dt = DateTime(dat_exp) if dat_exp else None
                color_cell = colors.HexColor(_theme['danger']) if (exp_dt and now_dt > exp_dt) else colors.HexColor(_theme['warning'])
            except Exception:
                color_cell = colors.HexColor(_theme['warning'])
        table.setStyle(TableStyle([('BACKGROUND', (4, i), (4, i), color_cell)]))

    elements.append(table)
    elements.append(Spacer(1, 10))

    # Totalização (inalterada)
    totals_head = styles['TotalizadorCabecalho']
    totals_cell = styles['TotalizadorConteudo']
    totals_emph = styles['TotalizadorDestaque']
    totals_data = [
        [Paragraph("Categoria", totals_head),
         Paragraph("Quantidade", totals_head),
         Paragraph("Percentual", totals_head)],
        [Paragraph("Pendentes", totals_cell),
         Paragraph(str(pendentes), totals_cell),
         Paragraph(f"{(pendentes/total*100):.1f}%" if total else "0%", totals_cell)],
        [Paragraph("Lidas", totals_cell),
         Paragraph(str(lidas), totals_cell),
         Paragraph(f"{(lidas/total*100):.1f}%" if total else "0%", totals_cell)],
        [Paragraph("Expiradas", totals_cell),
         Paragraph(str(expiradas), totals_cell),
         Paragraph(f"{(expiradas/total*100):.1f}%" if total else "0%", totals_cell)],
        [Paragraph("TOTAL", totals_emph),
         Paragraph(str(total), totals_emph),
         Paragraph("100%" if total else "0%", totals_emph)],
    ]
    totals_table = Table(totals_data, colWidths=['50%', '25%', '25%'])
    totals_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(_theme['primary'])),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor(_theme['light_gray'])),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor(_theme['primary'])),
        ('BACKGROUND', (0,1), (0,1), colors.HexColor('#FFF8E1')),
        ('BACKGROUND', (0,2), (0,2), colors.HexColor('#E8F5E9')),
        ('BACKGROUND', (0,3), (0,3), colors.HexColor('#FFEBEE')),
    ]))
    elements.append(Paragraph('TOTALIZAÇÃO', styles['Header2']))
    elements.append(totals_table)

    # Build e otimização via fitz
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    with fitz.open(stream=buffer.read(), filetype='pdf') as pdf:
        pdf.bake()
        pdf.save(caminho_saida, garbage=3, deflate=True, use_objstms=True)


# ------------------------------------------------------------------------------
# VIEWS
# ------------------------------------------------------------------------------
class ProcessoAdm(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral')
    install_home = os.environ.get('INSTALL_HOME')

    def download_files(self, cod_documento, forcar_regeneracao=False):
        """Gera/atualiza a pasta do processo e cria a Folha de Cientificações (somente se houver registros)."""
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_adm_integral_{cod_documento}')
        pagepath = os.path.join(dirpath, 'pages')
        ready_file = os.path.join(dirpath, ".ready")
        lock_file = os.path.join(dirpath, ".lock")

        # Cache rápido
        if os.path.exists(ready_file) and not forcar_regeneracao:
            try:
                with open(ready_file, 'r') as f:
                    ultima_geracao = datetime.strptime(f.read(), '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - ultima_geracao) < timedelta(seconds=30):
                    logger.info(f"[cache-hit] {cod_documento}")
                    return
            except Exception:
                pass

        os.makedirs(dirpath, exist_ok=True)
        with open(lock_file, 'w') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                logger.warning(f"[lock] Em uso: {cod_documento}")
                return

            # double-check
            if os.path.exists(ready_file) and not forcar_regeneracao:
                try:
                    with open(ready_file, 'r') as rf:
                        ultima_geracao = datetime.strptime(rf.read(), '%Y-%m-%d %H:%M:%S')
                    if (datetime.now() - ultima_geracao) < timedelta(seconds=30):
                        return
                except Exception:
                    pass

            # Limpa e recria
            if os.path.exists(dirpath):
                shutil.rmtree(dirpath)
            os.makedirs(dirpath, exist_ok=True)
            os.makedirs(pagepath, exist_ok=True)

            lst_arquivos = []
            id_processo = None
            processo_integral_nome = f"documento-{cod_documento}.pdf"

            # Coleta itens do processo
            for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
                processo_integral_nome = f"{documento.sgl_tipo_documento}-{documento.num_documento}-{documento.ano_documento}.pdf"
                id_processo = f"{documento.sgl_tipo_documento} {documento.num_documento}/{documento.ano_documento}"

                # Capa
                id_capa = uuid.uuid4().hex
                id_arquivo = f"{id_capa}.pdf"
                self.context.modelo_proposicao.capa_processo_adm(cod_documento=cod_documento, nom_arquivo=id_capa, action='gerar')
                if hasattr(self.context.temp_folder, id_arquivo):
                    lst_arquivos.append({
                        "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d 00:00:01'),
                        'path': self.context.temp_folder,
                        'file': id_arquivo,
                        'title': 'Capa do Processo'
                    })

                # Texto integral
                nom_arquivo = f"{cod_documento}_texto_integral.pdf"
                if hasattr(self.context.sapl_documentos.administrativo, nom_arquivo):
                    lst_arquivos.append({
                        "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d 00:00:02'),
                        'path': self.context.sapl_documentos.administrativo,
                        'file': nom_arquivo,
                        'title': f"{documento.des_tipo_documento} {documento.num_documento}/{documento.ano_documento}"
                    })

                # Acessórios
                for docadm in self.context.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento=documento.cod_documento, ind_excluido=0):
                    nome = f"{docadm.cod_documento_acessorio}.pdf"
                    if hasattr(self.context.sapl_documentos.administrativo, nome):
                        lst_arquivos.append({
                            "data": DateTime(docadm.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                            'path': self.context.sapl_documentos.administrativo,
                            'file': nome,
                            'title': docadm.nom_documento
                        })

                # Tramitações
                for tram in self.context.zsql.tramitacao_administrativo_obter_zsql(cod_documento=documento.cod_documento, rd_ordem='1', ind_excluido=0):
                    nome = f"{tram.cod_tramitacao}_tram.pdf"
                    if hasattr(self.context.sapl_documentos.administrativo.tramitacao, nome):
                        lst_arquivos.append({
                            "data": DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                            'path': self.context.sapl_documentos.administrativo.tramitacao,
                            'file': nome,
                            'title': f"Tramitação ({tram.des_status})"
                        })

                # Matérias vinculadas
                for mat in self.context.zsql.documento_administrativo_materia_obter_zsql(cod_documento=documento.cod_documento, ind_excluido=0):
                    materia = self.context.zsql.materia_obter_zsql(cod_materia=mat.cod_materia, ind_excluido=0)[0]
                    for sufixo in ['_redacao_final.pdf', '_texto_integral.pdf']:
                        nome = f"{mat.cod_materia}{sufixo}"
                        if hasattr(self.context.sapl_documentos.materia, nome):
                            lst_arquivos.append({
                                "data": DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                                'path': self.context.sapl_documentos.materia,
                                'file': nome,
                                'title': f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica} (mat. vinculada)"
                            })
                            break

            # Folha de Cientificações — somente se houver dados (e por último)
            try:
                dados_cient = coletar_cientificacoes_com_nomes(self.context, cod_documento, somente_pendentes=False)
                if not dados_cient:
                    logger.info(f"[cientificacoes] Nenhuma cientificação para {cod_documento}; folha não será gerada.")
                else:
                    folha_nome = "folha_cientificacoes.pdf"
                    folha_caminho = os.path.join(dirpath, folha_nome)
                    gerar_folha_cientificacao_pdf(self.context, cod_documento, folha_caminho, dados_cient)

                    lst_arquivos.append({
                        "data": "9999-12-31 23:59:59",  # garante última posição
                        "path": dirpath,
                        "file": folha_nome,
                        "title": "Folha de Cientificações",
                        "filesystem": True
                    })
            except Exception as e:
                logger.error(f"Folha de Cientificações falhou: {e}")

            # Ordenação e numeração
            lst_arquivos.sort(key=lambda d: d['data'])
            lst_arquivos = [(i+1, j) for i, j in enumerate(lst_arquivos)]

            # Merge
            merger = fitz.open()
            for i, dic in lst_arquivos:
                downloaded_pdf = f"{i:04d}.pdf"
                if dic.get('filesystem'):
                    p = os.path.join(dic['path'], dic['file'])
                    if not os.path.exists(p):
                        logger.error(f"FS não encontrado: {p}")
                        continue
                    with open(p, 'rb') as fh:
                        raw = fh.read()
                else:
                    arq = getattr(dic['path'], dic['file'], None)
                    if not arq:
                        logger.error(f"Zope obj não encontrado: {dic['path']}/{dic['file']}")
                        continue
                    raw = bytes(arq.data)

                doc_tmp = sanear_pdf(raw, title=dic['title'], mod_date=dic['data'])
                if not doc_tmp:
                    logger.error(f"Sanear falhou: {dic['title']}")
                    continue

                try:
                    merger.insert_pdf(doc_tmp)
                    with open(os.path.join(dirpath, downloaded_pdf), 'wb') as fsave:
                        fsave.write(doc_tmp.tobytes())
                except Exception as e:
                    logger.error(f"Insert falhou: {dic['title']}: {e}")

            # Final consolidado + rodapé numeração
            if not id_processo:
                id_processo = f"Documento {cod_documento}"
            merged_pdf = merger.tobytes()
            existing_pdf = fitz.open(stream=merged_pdf)
            numPages = existing_pdf.page_count

            for page_index in range(numPages):
                w = existing_pdf[page_index].rect.width
                txt = f"Fls. {page_index+1}/{numPages}"
                p1 = fitz.Point(w - 110, 25)
                shp = existing_pdf[page_index].new_shape()
                shp.insert_text(p1, f"{id_processo}\n{txt}", fontname="helv", fontsize=8)
                shp.commit()

            existing_pdf.set_metadata({
                "title": id_processo,
                "modDate": DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
            })
            data = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)

            with open(os.path.join(dirpath, processo_integral_nome), 'wb') as fpdf:
                fpdf.write(data)

            # Páginas individuais
            for i in range(numPages):
                file_name = os.path.join(pagepath, f"pg_{i+1:04d}.pdf")
                with fitz.open() as one:
                    one.insert_pdf(existing_pdf, from_page=i, to_page=i)
                    one.set_metadata({
                        "title": f"pg_{i+1:04d}.pdf",
                        "modDate": DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                    })
                    one.save(file_name, deflate=True, garbage=3, use_objstms=1)

            # Mark ready
            with open(ready_file, 'w') as rf:
                rf.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def render(self, cod_documento, action):
        portal_url = self.context.portal_url.portal_url()
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_adm_integral_{cod_documento}')
        pagepath = os.path.join(dirpath, 'pages')
        ready_file = os.path.join(dirpath, ".ready")

        time.sleep(random.uniform(0.1, 0.3))

        if action != 'pagina':
            self.download_files(cod_documento, forcar_regeneracao=(action == 'force'))

        if action == 'download':
            for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
                arquivo_final = f"{documento.sgl_tipo_documento}-{documento.num_documento}-{documento.ano_documento}.pdf"
            with open(os.path.join(dirpath, arquivo_final), 'rb') as download:
                arquivo = download.read()
                self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
                self.context.REQUEST.RESPONSE.setHeader('Content-Disposition', f'inline; filename={arquivo_final}')
                return arquivo

        # pasta (índice)
        if action in ('pasta', '', None):
            if not os.path.exists(ready_file):
                self.context.REQUEST.RESPONSE.setStatus(202)
                return {"status": "processing"}

            try:
                page_paths = [f for f in os.listdir(pagepath) if f.startswith("pg_")]
                file_paths = []
                for file in os.listdir(dirpath):
                    if file.startswith("0") and file.endswith(".pdf"):
                        filepath = os.path.join(dirpath, file)
                        with open(filepath, 'rb') as arq:
                            arq2 = fitz.open(arq)
                            file_paths.append({
                                'id': file,
                                'title': arq2.metadata.get("title") or file,
                                'date': arq2.metadata.get("modDate"),
                                'pages': list(range(1, arq2.page_count + 1))
                            })

                file_paths.sort(key=lambda d: d['id'])
                indice = []
                for item in file_paths:
                    for pagina in item['pages']:
                        indice.append({'id': item['id'], 'title': item['title'], 'date': item["date"]})

                indice1 = [(i + 1, j) for i, j in enumerate(indice)]
                lst_indice = []
                for i, arquivo in indice1:
                    lst_indice.append({
                        'id': arquivo['id'],
                        'titulo': arquivo['title'],
                        'data': arquivo['date'],
                        'num_pagina': str(i),
                        'pagina': f'pg_{i:04d}.pdf'
                    })

                pasta = []
                for item in file_paths:
                    dic_indice = {
                        'id': item['id'],
                        'title': item['title'],
                        'data': item['date'],
                        "url": f"{portal_url}/@@pagina_processo_adm_integral?cod_documento={cod_documento}%26pagina=pg_0001.pdf",
                        "paginas_geral": len(page_paths),
                        'paginas': [],
                        'paginas_doc': 0
                    }
                    for pag in lst_indice:
                        if item['id'] == str(pag.get('id', pag)):
                            dic_indice['paginas'].append({
                                'num_pagina': pag['num_pagina'],
                                'id_pagina': pag['pagina'],
                                "url": f"{portal_url}/@@pagina_processo_adm_integral?cod_documento={cod_documento}%26pagina={pag['pagina']}"
                            })
                    dic_indice['paginas_doc'] = len(dic_indice['paginas'])
                    pasta.append(dic_indice)

                return pasta
            except Exception as e:
                logger.error(f"Erro pasta: {e}")
                self.context.REQUEST.RESPONSE.setStatus(500)
                return {"error": str(e)}

class LimparPasta(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_limpar')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_documento):
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_adm_integral_{cod_documento}')
        if os.path.exists(dirpath) and os.path.isdir(dirpath):
            lock_file = os.path.join(dirpath, ".lock")
            if os.path.exists(lock_file):
                return f"Não foi possível remover {dirpath} - processo em andamento"
            shutil.rmtree(dirpath)
            return f'Diretório {dirpath} removido com sucesso.'
        return f'Diretório {dirpath} não existe.'

class PaginaProcessoAdm(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_adm_integral')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_documento, pagina):
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_adm_integral_{cod_documento}')
        pagepath = os.path.join(dirpath, 'pages')
        try:
            file_path = os.path.join(pagepath, pagina)
            with open(file_path, 'rb') as download:
                data = download.read()
            self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
            self.context.REQUEST.RESPONSE.setHeader('Content-Disposition', f'inline; filename={pagina}')
            return data
        except FileNotFoundError:
            self.context.REQUEST.RESPONSE.setStatus(404)
            return "Arquivo não encontrado"
        except Exception as e:
            logger.exception(f"Erro ao exibir página: {e}")
            self.context.REQUEST.RESPONSE.setStatus(500)
            return "Erro ao processar o arquivo"

class ProcessoAdmStatus(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_status')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_documento):
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_adm_integral_{cod_documento}')
        ready_file = os.path.join(dirpath, ".ready")
        lock_file = os.path.join(dirpath, ".lock")
        if os.path.exists(lock_file):
            return "processing"
        if os.path.exists(ready_file):
            return "ready"
        return "pending"
