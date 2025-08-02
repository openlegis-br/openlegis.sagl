# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import hashlib
from io import BytesIO
from DateTime import DateTime
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import fitz
import logging
import pikepdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.rl_config import defaultPageSize
from reportlab.lib.units import mm

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes para otimização de PDF
PDF_OPTIONS = {
    'garbage': 3,
    'deflate': True,
    'clean': True,
    'use_objstms': True
}

# Limites de segurança
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB
MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500MB
MAX_PAGES = 1000
MAX_DOCUMENTS = 100

class PDFGenerationError(Exception):
    """Exceção personalizada para erros na geração de PDF"""
    pass

class SecurityError(Exception):
    """Exceção para problemas de segurança"""
    pass

def validate_pdf_content(pdf_bytes):
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise PDFGenerationError(f"Tamanho do PDF excede {MAX_PDF_SIZE//(1024*1024)}MB")
    if not pdf_bytes.startswith(b'%PDF-'):
        raise PDFGenerationError("O arquivo não é um PDF válido")
    return True

def secure_path_join(base_path, *paths):
    full = os.path.abspath(os.path.join(base_path, *paths))
    if not full.startswith(os.path.abspath(base_path)):
        raise SecurityError("Tentativa de acesso não permitido")
    return full

def gerar_ficha_votacao_pdf(dados_votacao, caminho_saida, nome_camara, nome_sessao, logo_bytes=None):
    """Gera um PDF da ficha de votação com design profissional aprimorado"""
    try:
        # Configuração do documento com margens para impressão
        margin_left = margin_right = 15 * mm
        doc = SimpleDocTemplate(
            caminho_saida,
            pagesize=A4,
            rightMargin=margin_right,
            leftMargin=margin_left,
            topMargin=5 * mm,
            bottomMargin=20 * mm
        )

        # --- ESTILOS AVANÇADOS ---
        styles = getSampleStyleSheet()
        theme = {
            'primary': '#003366',
            'secondary': '#E1F5FE',
            'success': '#4CAF50',
            'danger': '#F44336',
            'warning': '#FFC107',
            'light_gray': '#F5F5F5',
            'text': '#212121',
            'muted': '#757575'
        }

        styles.add(ParagraphStyle(
            name='Header1',
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor(theme['primary']),
            fontName='Helvetica-Bold',
            spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='Header2',
            fontSize=11,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.HexColor(theme['primary']),
            fontName='Helvetica-Bold',
            spaceAfter=8,
            borderLeft=2,
            borderColor=colors.HexColor(theme['primary']),
            leftPadding=6
        ))
        styles.add(ParagraphStyle(
            name='Label',
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            textColor=colors.HexColor(theme['muted']),
            fontName='Helvetica-Bold',
            spaceAfter=2
        ))
        styles.add(ParagraphStyle(
            name='Value',
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            textColor=colors.HexColor(theme['text']),
            fontName='Helvetica',
            spaceAfter=8
        ))
        styles.add(ParagraphStyle(
            name='VoteResult',
            fontSize=12,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.white,
            backColor=colors.HexColor(theme['primary']),
            fontName='Helvetica-Bold',
            spaceBefore=10,
            spaceAfter=15,
            padding=6
        ))
        styles.add(ParagraphStyle(
            name='TotalizadorCabecalho',
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            textColor=colors.white,
            backColor=colors.HexColor(theme['primary']),
            fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='TotalizadorConteudo',
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            textColor=colors.HexColor(theme['text']),
            fontName='Helvetica'
        ))
        styles.add(ParagraphStyle(
            name='TotalizadorDestaque',
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            textColor=colors.HexColor(theme['text']),
            fontName='Helvetica-Bold'
        ))



        elements = []

        # 1. CABEÇALHO INSTITUCIONAL
        if logo_bytes:
            logo_stream = BytesIO(logo_bytes)
            logo_img = Image(
                logo_stream,
                width=50, height=50
            )
        else:
            # fallback para arquivo estático ou nada
            logo_img = Image('logo_camara.png', width=60, height=60) \
                       if os.path.exists('logo_camara.png') else ''

        nome_camara_para_header = Paragraph(
            nome_camara + '<br/>' + dados_votacao.get('sessao',''),
            ParagraphStyle(
              'CamaraNameHeader',
              fontSize=13,
              leading=15,
              alignment=TA_LEFT,
              textColor=colors.HexColor(theme['primary']),
              fontName='Helvetica-Bold',
              spaceAfter=14
            )
        )

        # (c) Parágrafo com título da sessão e ID fica na segunda linha
        title_para_header = Paragraph('REGISTRO DE VOTAÇÃO', style=styles['Header1'])
        
        id_para_header = Paragraph(
            f"ID: {hashlib.md5(str(dados_votacao).encode()).hexdigest()[:8]}",
            styles['Label']
        )

        header_data = [
            # Linha 1: Nome da Câmara, centralizado sobre as 3 colunas
            [ logo_img, nome_camara_para_header, '' ],
            [ '', title_para_header, id_para_header ]
        ]

        header_table = Table(header_data, colWidths=[60, '*', 80])
        header_table.setStyle(TableStyle([
            # Linha 1: alinhar verticalmente o logo e o nome
            ('VALIGN',        (0,0), (1,0),   'MIDDLE'),
            ('ALIGN',         (0,0), (0,0),   'CENTER'),
            ('ALIGN',         (1,0), (1,0),   'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,0),  6),

            # Linha 2: mesma formatação que antes
            ('VALIGN',        (0,1), (-1,1),  'MIDDLE'),
            ('ALIGN',         (0,1), (0,1),   'CENTER'),
            ('ALIGN',         (2,1), (2,1),   'RIGHT'),
            ('LINEBELOW',     (1,1), (1,1),   1, colors.HexColor(theme['primary'])),
            ('BOTTOMPADDING', (0,1), (-1,1),  10),
        ]))
        elements.append(header_table)

        # 2. INFORMAÇÕES DA SESSÃO (Grid 2 colunas)
        session_data = [
            [
                Paragraph(f"<b>{nome_sessao}:</b>", styles['Label']),
                Paragraph(dados_votacao.get('sessao',''), styles['Value']),
                Paragraph('<b>Data/Hora:</b>', styles['Label']),
                Paragraph(f"{dados_votacao.get('data_sessao','')} {dados_votacao.get('hora_sessao','')}", styles['Value'])
            ],
            [
                Paragraph('<b>Legislatura:</b>', styles['Label']),
                Paragraph(dados_votacao.get('legislatura',''), styles['Value']),
                Paragraph('<b>Fase:</b>', styles['Label']),
                Paragraph(dados_votacao.get('fase',''), styles['Value']),
            ],
            [
                Paragraph('<b>Tipo de Votação:</b>', styles['Label']),
                Paragraph(dados_votacao.get('txt_tipo_votacao',''), styles['Value']),
                Paragraph('<b>Turno de Discussão:</b>', styles['Label']),
                Paragraph(dados_votacao.get('txt_turno','—'), styles['Value'])
            ],
            [
                Paragraph('<b>Quórum:</b>', styles['Label']),
                Paragraph(dados_votacao.get('txt_quorum',''), styles['Value']),
                # Se não precisar de quarta coluna neste row, deixe vazia:
                Paragraph('', styles['Label']),
                Paragraph('', styles['Value'])
            ]
        ]

        session_table = Table(session_data, colWidths=['20%','30%','20%','30%'], hAlign='LEFT')
        session_table.setStyle(TableStyle([
            ('VALIGN',       (0,0), (-1,-1), 'TOP'),
            ('ALIGN',        (0,0), (-1,-1), 'LEFT'),
            ('GRID',         (0,0), (-1,-1), 0.5, colors.HexColor('#EEEEEE')),
            ('BACKGROUND',   (0,0), (-1,-1), colors.white),
            ('LEFTPADDING',  (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
        ]))
        elements.extend([session_table, Spacer(1, 15)])

        # 3. INFORMAÇÕES DA MATÉRIA
        elements.append(Paragraph(
            f"{dados_votacao.get('tipo_materia','')} nº {dados_votacao.get('num_materia','')}/{dados_votacao.get('ano_materia','')}",
            styles['Header2']
        ))
        elements.append(Paragraph(
            f"<b>Autoria:</b> {dados_votacao.get('autoria_materia','')}",
            styles['Value']
        ))
        elements.append(Spacer(1, 5))
        ementa_style = ParagraphStyle(
            'EmentaStyle', parent=styles['Value'],
            alignment=TA_JUSTIFY,
            backColor=colors.HexColor(theme['light_gray']),
            borderPadding=5,
            spaceAfter=15
        )
        elements.append(Paragraph(
            f"<b>Ementa:</b> {dados_votacao.get('ementa_materia','')}",
            ementa_style
        ))

        # 4. RESULTADO COM DESTAQUE
        result_text = f"RESULTADO: {dados_votacao.get('txt_resultado','').upper()}"
        elements.append(Paragraph(result_text, styles['VoteResult']))

        # 5. DETALHAMENTO NOMINAL (se aplicável)
        votos = []
        if dados_votacao.get('txt_tipo_votacao') == 'Nominal':
            elements.append(Paragraph('DETALHAMENTO DA VOTAÇÃO', styles['Header2']))
            table_data = [[
                Paragraph('Vereador', styles['TotalizadorCabecalho']),
                Paragraph('Partido', styles['TotalizadorCabecalho']),
                Paragraph('Voto', styles['TotalizadorCabecalho'])
            ]]
            vote_colors = {
                'Sim': colors.HexColor(theme['success']),
                'Não': colors.HexColor(theme['danger']),
                'Abstenção': colors.HexColor(theme['warning'])
            }
            for v in dados_votacao.get('votos_nominais', []):
                vote = v.get('voto','').strip()
                votos.append(vote)
                table_data.append([
                    Paragraph(v.get('nom_completo',''), styles['Value']),
                    Paragraph(v.get('partido',''), styles['Value']),
                    Paragraph(vote, styles['Value'])
                ])
            vote_table = Table(table_data, colWidths=['50%', '30%', '20%'], repeatRows=1)
            vote_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor(theme['primary'])),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('ALIGN',      (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0,0), (-1,0), 9),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor('#EEEEEE')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#FAFAFA')])
            ]))
            for i, row in enumerate(table_data[1:], start=1):
                vote = row[2].text
                if vote in vote_colors:
                    vote_table.setStyle(TableStyle([
                        ('BACKGROUND', (2,i), (2,i), vote_colors[vote])
                    ]))
            elements.extend([vote_table, Spacer(1, 15)])

        # 6. TOTALIZADORES COMPLETOS
        tot_sim = int(dados_votacao.get('num_votos_sim') or 0)
        tot_nao = int(dados_votacao.get('num_votos_nao') or 0)
        tot_abst = int(dados_votacao.get('num_abstencao') or 0)
        tot_aus = int(dados_votacao.get('num_ausentes') or 0)
        tot_pres = votos.count('Na Presid.') if dados_votacao.get('txt_tipo_votacao') == 'Nominal' else 0
        tot_geral = tot_sim + tot_nao + tot_abst + tot_aus + tot_pres

        total_data = [
            [
                Paragraph('Tipo de Voto', styles['TotalizadorCabecalho']),
                Paragraph('Quantidade', styles['TotalizadorCabecalho']),
                Paragraph('Percentual', styles['TotalizadorCabecalho'])
            ],
            [
                Paragraph('Votos "Sim"', styles['TotalizadorConteudo']),
                Paragraph(str(tot_sim), styles['TotalizadorConteudo']),
                Paragraph(f'{(tot_sim/tot_geral*100):.1f}%' if tot_geral > 0 else '0%', styles['TotalizadorConteudo'])
            ],
            [
                Paragraph('Votos "Não"', styles['TotalizadorConteudo']),
                Paragraph(str(tot_nao), styles['TotalizadorConteudo']),
                Paragraph(f'{(tot_nao/tot_geral*100):.1f}%' if tot_geral > 0 else '0%', styles['TotalizadorConteudo'])
            ],
            [
                Paragraph('Abstenções', styles['TotalizadorConteudo']),
                Paragraph(str(tot_abst), styles['TotalizadorConteudo']),
                Paragraph(f'{(tot_abst/tot_geral*100):.1f}%' if tot_geral > 0 else '0%', styles['TotalizadorConteudo'])
            ],
            [
                Paragraph('Na Presidência', styles['TotalizadorConteudo']),
                Paragraph(str(tot_pres), styles['TotalizadorConteudo']),
                Paragraph(f'{(tot_pres/tot_geral*100):.1f}%' if tot_geral > 0 else '0%', styles['TotalizadorConteudo'])
            ],
            [
                Paragraph('Ausentes', styles['TotalizadorConteudo']),
                Paragraph(str(tot_aus), styles['TotalizadorConteudo']),
                Paragraph(f'{(tot_aus/tot_geral*100):.1f}%' if tot_geral > 0 else '0%', styles['TotalizadorConteudo'])
            ],
            [
                Paragraph('TOTAL GERAL', styles['TotalizadorDestaque']),
                Paragraph(str(tot_geral), styles['TotalizadorDestaque']),
                Paragraph('100%', styles['TotalizadorDestaque'])
            ]
        ]

        total_table = Table(total_data, colWidths=['50%', '25%', '25%'])
        total_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(theme['primary'])),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('ALIGN',      (1,1), (-1,-1), 'CENTER'),
            ('FONTNAME',   (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor(theme['light_gray']),
            ),
            ('BOX',        (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
            ('LINEABOVE',  (0,-1), (-1,-1), 1, colors.HexColor(theme['primary'])),
            ('BACKGROUND', (0,1), (0,1), colors.HexColor('#E8F5E9')),
            ('BACKGROUND', (0,2), (0,2), colors.HexColor('#FFEBEE')),
            ('BACKGROUND', (0,3), (0,3), colors.HexColor('#FFF8E1')),
        ]))
        elements.append(Paragraph('TOTALIZAÇÃO DE VOTOS', styles['Header2']))
        elements.append(total_table)

        # 7. RODAPÉ PROFISSIONAL
        def footer(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor(theme['primary']))
            canvas.setLineWidth(0.5)
            canvas.line(margin_left, 40, doc.width + margin_left, 40)
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.HexColor(theme['muted']))
            canvas.drawString(margin_left, 30, f"Documento gerado eletronicamente - {nome_camara}")
            footer_text = f"{DateTime().strftime('%d/%m/%Y %H:%M')} | Página {canvas.getPageNumber()}"
            canvas.drawRightString(doc.width + margin_left, 30, footer_text)
            canvas.restoreState()

        # Constrói o documento
        doc.build(elements, onFirstPage=footer, onLaterPages=footer)
        logger.info(f"PDF gerado com sucesso em: {caminho_saida}")

    except Exception as e:
        logger.error(f"Erro na geração do PDF: {str(e)}", exc_info=True)
        raise PDFGenerationError(f"Falha na geração do PDF: {str(e)}")

def check_pdf_security(pdf_bytes):
    """Verifica se o PDF contém elementos potencialmente maliciosos"""
    try:
        # Verifica JavaScript com pikepdf
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                if '/JS' in page or '/JavaScript' in page:
                    raise SecurityError("PDF contém JavaScript potencialmente malicioso")
        
        # Verificação adicional com fitz
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                if page.get_links() or page.get_xobjects():
                    # Verificação simplificada de elementos ativos
                    logger.warning("PDF contém elementos interativos/ativos")
        
        return True
    except Exception as e:
        logger.error(f"Falha na verificação de segurança do PDF: {e}")
        raise SecurityError(f"Falha na verificação de segurança do PDF: {e}")

def sanear_pdf(pdf_bytes, titulo=None, data_modificacao=None):
    """Sanear e reparar um PDF utilizando PyMuPDF (fitz) com fallback para pikepdf"""
    def tentar_fitz(stream):
        try:
            with fitz.open(stream=stream, filetype="pdf") as doc:
                if len(doc) > MAX_PAGES:
                    raise PDFGenerationError(f"PDF excede o limite de {MAX_PAGES} páginas")
                
                # Atualizar metadados se fornecido
                if titulo or data_modificacao:
                    metadados = doc.metadata or {}
                    if titulo:
                        metadados["title"] = str(titulo)[:100]
                    if data_modificacao:
                        metadados["modDate"] = str(data_modificacao)
                    doc.set_metadata(metadados)
                
                # Otimizar PDF
                saida = BytesIO()
                doc.save(saida, **PDF_OPTIONS)
                saida.seek(0)
                
                validate_pdf_content(saida.getvalue())
                check_pdf_security(saida.getvalue())
                
                return fitz.open(stream=saida, filetype="pdf")
            
        except Exception as e:
            logger.warning(f"[sanear_pdf] Falha no Fitz: {e}")
            return None

    try:
        validate_pdf_content(pdf_bytes)
        check_pdf_security(pdf_bytes)
        
        # Tentar primeiro com Fitz
        resultado = tentar_fitz(BytesIO(pdf_bytes))
        
        if resultado:
            return resultado

        # Fallback com pikepdf
        logger.info("[sanear_pdf] Tentando reparar com pikepdf")
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
            # Remover elementos potencialmente perigosos
            for page in pdf.pages:
                if '/Annots' in page:
                    del page.Annots
                if '/AA' in page:
                    del page.AA
            
            saida = BytesIO()
            pdf.save(saida)
            saida.seek(0)
            
            validate_pdf_content(saida.getvalue())
            resultado = tentar_fitz(saida)
            
            if resultado:
                logger.info("[sanear_pdf] PDF reparado com pikepdf")
                return resultado
            
            logger.error("[sanear_pdf] pikepdf salvou, mas o fitz ainda falhou")
            raise PDFGenerationError("Não foi possível reparar o PDF")
            
    except Exception as e:
        logger.error(f"[sanear_pdf] Erro ao processar PDF: {e}")
        raise PDFGenerationError(f"Falha ao processar PDF: {str(e)}")

def formatar_documentos(result, cod_materia, base_url):
    """
    Transforma o resultado de render() em lista de dicts conforme especificação.
    """
    documentos = result.get('documentos', [])
    total_paginas = result.get('total_paginas', 0)
    out = []
    for idx, doc in enumerate(documentos, start=1):
        doc_id = f"{idx:04d}.pdf"
        first_num = doc['paginas'][0]
        first_id = f"pg_{int(first_num):04d}.pdf"
        url_geral = f"{base_url}?cod_materia={cod_materia}%26pagina={first_id}"
        paginas = []
        for num in doc['paginas']:
            pg_id = f"pg_{int(num):04d}.pdf"
            paginas.append({
                'num_pagina': str(num),
                'id_pagina': pg_id,
                'url': f"{base_url}?cod_materia={cod_materia}%26pagina={pg_id}"
            })
        out.append({
            'id': doc_id,
            'title': doc['titulo'],
            'data': doc['data'],
            'url': url_geral,
            'paginas_geral': total_paginas,
            'paginas': paginas,
            'id_paginas': [],
            'paginas_doc': doc.get('num_paginas', len(paginas))
        })
    return out

class ProcessoLegView(grok.View):
    """Visualização principal para geração do processo legislativo em PDF"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_integral')
    
    # Configurações
    TEMP_DIR_PREFIX = 'processo_leg_integral_'
    
    @property
    def temp_base(self):
        """Diretório base temporário seguro"""
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        return secure_path_join(install_home, 'var/tmp')

    def preparar_diretorios(self, cod_materia):
        """Cria diretórios temporários de trabalho com segurança"""
        try:
            # Validação do código da matéria
            if not cod_materia or not str(cod_materia).isdigit():
                raise ValueError("Código da matéria inválido")
            
            # Cria hash segura para nome do diretório
            dir_hash = hashlib.md5(str(cod_materia).encode()).hexdigest()
            dir_base = secure_path_join(
                self.temp_base, 
                f"{self.TEMP_DIR_PREFIX}{dir_hash}"
            )
            dir_paginas = secure_path_join(dir_base, 'pages')
            
            # Limpeza segura de diretórios existentes
            if os.path.exists(dir_base):
                shutil.rmtree(dir_base, ignore_errors=True)
            
            # Criação dos diretórios
            os.makedirs(dir_base, mode=0o700, exist_ok=True)
            os.makedirs(dir_paginas, mode=0o700, exist_ok=True)
            
            return dir_base, dir_paginas
            
        except Exception as e:
            logger.error(f"Erro ao preparar diretórios: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha na preparação dos diretórios: {str(e)}")

    def obter_dados_materia(self, cod_materia):
        """Obtém informações básicas da matéria legislativa com validação"""
        try:
            if not cod_materia or not str(cod_materia).isdigit():
                raise ValueError("Código da matéria inválido")
            
            materia = self.context.zsql.materia_obter_zsql(cod_materia=cod_materia)
            if not materia:
                raise ValueError("Matéria não encontrada")
                
            materia = materia[0]
            return {
                'id': f"{materia.sgl_tipo_materia}-{materia.num_ident_basica}-{materia.ano_ident_basica}",
                'id_exibicao': f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica}",
                'tipo': materia.sgl_tipo_materia,
                'numero': materia.num_ident_basica,
                'ano': materia.ano_ident_basica,
                'data_apresentacao': materia.dat_apresentacao,
                'descricao': materia.des_tipo_materia,
                'cod_materia': materia.cod_materia
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter dados da matéria: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha ao obter dados da matéria: {str(e)}")

    def coletar_documentos(self, dados_materia, dir_base):
        """Coleta documentos relacionados à matéria com validação"""
        nome_camara = self.context.sapl_documentos.props_sagl.getProperty(
            'nom_casa', '(não definido)'
        )
        nome_sessao = self.context.sapl_documentos.props_sagl.getProperty(
            'reuniao_sessao', '(não definido)'
        )
        props = self.context.sapl_documentos.props_sagl
        id_logo = props.getProperty('id_logo', None)
        logo_bytes = None
        if id_logo and hasattr(props, id_logo):
            logo_obj = getattr(props, id_logo)
            logo_bytes = bytes(logo_obj.data)  # blob da imagem
        documentos = []
        total_size = 0
        
        try:
            # Função auxiliar para adicionar documentos com verificação de tamanho
            def adicionar_documento(doc_info):
                nonlocal total_size
                if len(documentos) >= MAX_DOCUMENTS:
                    raise PDFGenerationError(f"Número máximo de documentos ({MAX_DOCUMENTS}) excedido")
                
                if hasattr(doc_info['path'], doc_info['file']):
                    arquivo_obj = getattr(doc_info['path'], doc_info['file'])
                    file_size = len(bytes(arquivo_obj.data))
                    
                    if total_size + file_size > MAX_TOTAL_SIZE:
                        raise PDFGenerationError(f"Tamanho total dos documentos excede {MAX_TOTAL_SIZE//(1024*1024)}MB")
                    
                    total_size += file_size
                    documentos.append(doc_info)

            # Capa do processo
            arquivo_capa = f"capa_{dados_materia['tipo']}-{dados_materia['numero']}-{dados_materia['ano']}.pdf"
            self.context.modelo_proposicao.capa_processo(
                cod_materia=dados_materia['cod_materia'], 
                action='gerar'
            )
            
            adicionar_documento({
                "data": DateTime(dados_materia['data_apresentacao'], datefmt='international').strftime('%Y-%m-%d 00:00:01'),
                "path": self.context.temp_folder,
                "file": arquivo_capa,
                "title": "Capa do Processo"
            })

            # Texto integral da matéria
            arquivo_texto = f"{dados_materia['cod_materia']}_texto_integral.pdf"
            data_texto = DateTime(dados_materia['data_apresentacao'], datefmt='international').strftime('%Y-%m-%d 00:00:02')
            
            for proposta in self.context.zsql.proposicao_obter_zsql(
                cod_mat_ou_doc=dados_materia['cod_materia'], 
                ind_mat_ou_doc='M'
            ):
                data_texto = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
            
            adicionar_documento({
                "data": data_texto,
                "path": self.context.sapl_documentos.materia,
                "file": arquivo_texto,
                "title": f"{dados_materia['descricao']} nº {dados_materia['numero']}/{dados_materia['ano']}"
            })

            # Redação Final (adicionando o novo código)
            nom_redacao = f"{dados_materia['cod_materia']}_redacao_final.pdf"
            if hasattr(self.context.sapl_documentos.materia, nom_redacao):
                doc_redacao = {
                    "data": DateTime(dados_materia['data_apresentacao'], datefmt='international').strftime('%Y-%m-%d 00:00:03'),
                    "path": self.context.sapl_documentos.materia,
                    "file": nom_redacao,
                    "title": "Redação Final"
                }
            
                # Atualiza data se houver proposta associada
                for proposicao in self.context.zsql.proposicao_obter_zsql(
                    cod_mat_ou_doc=dados_materia['cod_materia'],
                    ind_mat_ou_doc='M'
                ):
                    doc_redacao["data"] = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
            
                adicionar_documento(doc_redacao)

            # Fichas de votação
            votacoes = self.context.pysc.votacao_obter_pysc(cod_materia=dados_materia['cod_materia'])
            for i, votacao in enumerate(votacoes):
                fase = votacao.get('fase', '')
                if fase == "Expediente - Leitura de Matérias":
                   logger.info(f"[coletar_documentos] Pulando regisro de votação na fase: {fase}")
                   continue  # não gera nem registra essa ficha

                nome_arquivo = f'ficha_votacao_{i + 1}.pdf'
                caminho_arquivo = secure_path_join(dir_base, nome_arquivo)

                # Gera o PDF da ficha
                gerar_ficha_votacao_pdf(votacao, caminho_arquivo, nome_camara, nome_sessao, logo_bytes=logo_bytes)

                # Lê bytes e valida
                with open(caminho_arquivo, 'rb') as f:
                    pdf_bytes = f.read()
                validate_pdf_content(pdf_bytes)

                raw_date = votacao.get('dat_sessao', '')
                try:
                    date_obj = raw_date if isinstance(raw_date, DateTime) else DateTime(raw_date, datefmt='international')
                    date_str = date_obj.strftime('%Y-%m-%d')
                except Exception:
                    date_str = str(raw_date)[:10]
                hora_str = votacao.get('hora_sessao', '00:00:00')
                data_votacao = f"{date_str} {hora_str}"
                pdf = sanear_pdf(
                    pdf_bytes,
                    titulo="Registro de Votação",
                    data_modificacao=data_votacao
                )

                if pdf:
                    documentos.append({
                        "data": data_votacao,
                        "file": nome_arquivo,
                        "title": "Registro de Votação",
                        "path": dir_base,
                        "filesystem": True
                    })

            # Emendas
            for emenda in self.context.zsql.emenda_obter_zsql(
                cod_materia=dados_materia['cod_materia'], 
                ind_excluido=0
            ):
                arquivo_emenda = f"{emenda.cod_emenda}_emenda.pdf"
                data_emenda = DateTime(emenda.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                
                for proposta in self.context.zsql.proposicao_obter_zsql(cod_emenda=emenda.cod_emenda):
                    data_emenda = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

                adicionar_documento({
                    "data": data_emenda,
                    "path": self.context.sapl_documentos.emenda,
                    "file": arquivo_emenda,
                    "title": f"Emenda {emenda.des_tipo_emenda} nº {emenda.num_emenda}"
                })

            # Substitutivos
            for substitutivo in self.context.zsql.substitutivo_obter_zsql(
                cod_materia=dados_materia['cod_materia'],
                ind_excluido=0
            ):
                arquivo_substitutivo = f"{substitutivo.cod_substitutivo}_substitutivo.pdf"
                if hasattr(self.context.sapl_documentos.substitutivo, arquivo_substitutivo):
                    doc_substitutivo = {
                        "data": DateTime(substitutivo.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                        "path": self.context.sapl_documentos.substitutivo,
                        "file": arquivo_substitutivo,
                        "title": f"Substitutivo nº {substitutivo.num_substitutivo}"
                    }
                
                    # Atualiza data se houver proposta associada
                    for proposta in self.context.zsql.proposicao_obter_zsql(
                        cod_substitutivo=substitutivo.cod_substitutivo
                    ):
                        doc_substitutivo["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                
                    adicionar_documento(doc_substitutivo)

            # Relatorias/Pareceres
            for relat in self.context.zsql.relatoria_obter_zsql(
                cod_materia=dados_materia['cod_materia'],
                ind_excluido=0
            ):
                arquivo_parecer = f"{relat.cod_relatoria}_parecer.pdf"
                if hasattr(self.context.sapl_documentos.parecer_comissao, arquivo_parecer):
                    doc_parecer = {
                        "data": DateTime(relat.dat_destit_relator, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                        "path": self.context.sapl_documentos.parecer_comissao,
                        "file": arquivo_parecer
                    }
                
                    # Atualiza data se houver proposta associada
                    for proposta in self.context.zsql.proposicao_obter_zsql(
                        cod_parecer=relat.cod_relatoria
                    ):
                        doc_parecer["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                
                    # Obtém informações da comissão
                    comissao = self.context.zsql.comissao_obter_zsql(
                        cod_comissao=relat.cod_comissao,
                        ind_excluido=0
                    )[0]
                    doc_parecer["title"] = (
                        f"Parecer {comissao.sgl_comissao} nº "
                        f"{relat.num_parecer}/{relat.ano_parecer}"
                    )
                
                    adicionar_documento(doc_parecer)

            # Matérias Anexadas
            for anexada in self.context.zsql.anexada_obter_zsql(
                cod_materia_principal=dados_materia['cod_materia'],
                ind_excluido=0
            ):
                arquivo_anexada = f"{anexada.cod_materia_anexada}_texto_integral.pdf"
                if hasattr(self.context.sapl_documentos.materia, arquivo_anexada):
                    doc_anexada = {
                        "data": DateTime(anexada.dat_anexacao, datefmt='international').strftime('%Y-%m-%d 23:58:00'),
                        "path": self.context.sapl_documentos.materia,
                        "file": arquivo_anexada,
                        "title": (
                            f"{anexada.tip_materia_anexada} "
                            f"{anexada.num_materia_anexada}/{anexada.ano_materia_anexada} "
                            "(anexada)"
                        )
                    }
                    adicionar_documento(doc_anexada)
                
                    # Documentos acessórios das matérias anexadas
                    for documento in self.context.zsql.documento_acessorio_obter_zsql(
                        cod_materia=anexada.cod_materia_anexada,
                        ind_excluido=0
                    ):
                        arquivo_acessorio = f"{documento.cod_documento}.pdf"
                        if hasattr(self.context.sapl_documentos.materia, arquivo_acessorio):
                            doc_acessorio = {
                                "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                                "path": self.context.sapl_documentos.materia,
                                "file": arquivo_acessorio,
                                "title": f"{documento.nom_documento} (acess. de anexada)"
                            }
                        
                            # Atualiza data se houver proposta associada
                            for proposta in self.context.zsql.proposicao_obter_zsql(
                                cod_mat_ou_doc=documento.cod_documento,
                                ind_mat_ou_doc='D'
                            ):
                                doc_acessorio["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        
                            adicionar_documento(doc_acessorio)

            # Matérias Anexadoras
            for anexadora in self.context.zsql.anexada_obter_zsql(
                cod_materia_anexada=dados_materia['cod_materia'],
                ind_excluido=0
            ):
                arquivo_anexadora = f"{anexadora.cod_materia_principal}_texto_integral.pdf"
                if hasattr(self.context.sapl_documentos.materia, arquivo_anexadora):
                    doc_anexadora = {
                        "data": DateTime(anexadora.dat_anexacao, datefmt='international').strftime('%Y-%m-%d 23:58:00'),
                        "path": self.context.sapl_documentos.materia,
                        "file": arquivo_anexadora,
                        "title": (
                            f"{anexadora.tip_materia_principal} "
                            f"{anexadora.num_materia_principal}/{anexadora.ano_materia_principal} "
                            "(anexadora)"
                        )
                    }
                    adicionar_documento(doc_anexadora)
                
                    # Documentos acessórios das matérias anexadoras
                    for documento in self.context.zsql.documento_acessorio_obter_zsql(
                        cod_materia=anexadora.cod_materia_principal,
                        ind_excluido=0
                    ):
                        arquivo_acessorio = f"{documento.cod_documento}.pdf"
                        if hasattr(self.context.sapl_documentos.materia, arquivo_acessorio):
                            doc_acessorio = {
                                "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                                "path": self.context.sapl_documentos.materia,
                                "file": arquivo_acessorio,
                                "title": f"{documento.nom_documento} (acess. de anexadora)"
                            }
                        
                            # Atualiza data se houver proposta associada
                            for proposta in self.context.zsql.proposicao_obter_zsql(
                                cod_mat_ou_doc=documento.cod_documento,
                                ind_mat_ou_doc='D'
                            ):
                                doc_acessorio["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        
                            adicionar_documento(doc_acessorio)

            # Documentos Acessórios da Matéria Principal
            for documento in self.context.zsql.documento_acessorio_obter_zsql(
                cod_materia=dados_materia['cod_materia'],
                ind_excluido=0
            ):
                arquivo_acessorio = f"{documento.cod_documento}.pdf"
                if hasattr(self.context.sapl_documentos.materia, arquivo_acessorio):
                    doc_acessorio = {
                        "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                        "path": self.context.sapl_documentos.materia,
                        "file": arquivo_acessorio,
                        "title": documento.nom_documento
                    }
                
                    # Atualiza data se houver proposta associada
                    for proposta in self.context.zsql.proposicao_obter_zsql(
                        cod_mat_ou_doc=documento.cod_documento,
                        ind_mat_ou_doc='D'
                    ):
                        doc_acessorio["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                
                    adicionar_documento(doc_acessorio)

            # Tramitações
            for tram in self.context.zsql.tramitacao_obter_zsql(
                cod_materia=dados_materia['cod_materia'],
                rd_ordem='1',
                ind_excluido=0
            ):
                arquivo_tram = f"{tram.cod_tramitacao}_tram.pdf"
                if hasattr(self.context.sapl_documentos.materia.tramitacao, arquivo_tram):
                    adicionar_documento({
                        "data": DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                        "path": self.context.sapl_documentos.materia.tramitacao,
                        "file": arquivo_tram,
                        "title": f"Tramitação ({tram.des_status})"
                    })

            # Normas Jurídicas Relacionadas
            for norma in self.context.zsql.materia_buscar_norma_juridica_zsql(
                cod_materia=dados_materia['cod_materia']
            ):
                arquivo_norma = f"{norma.cod_norma}_texto_integral.pdf"
                if hasattr(self.context.sapl_documentos.norma_juridica, arquivo_norma):
                    adicionar_documento({
                        "data": DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 23:59:00'),
                        "path": self.context.sapl_documentos.norma_juridica,
                        "file": arquivo_norma,
                        "title": f"{norma.sgl_norma} nº {norma.num_norma}/{norma.ano_norma}"
                    })

            # Ordenar por data
            documentos.sort(key=lambda x: x['data'])
            return documentos
            
        except Exception as e:
            logger.error(f"Erro ao coletar documentos: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha na coleta de documentos: {str(e)}")

    def mesclar_documentos(self, documentos, dir_base, id_processo):
        """Mescla documentos em um único PDF com tratamento de erros"""
        try:
            pdf_mesclado = fitz.open()
            total_size = 0
            documentos_com_paginas = []

            current_page = 1

            for i, documento in enumerate(documentos, 1):
                try:
                    if documento.get('filesystem'):
                        caminho_arquivo = secure_path_join(documento['path'], documento['file'])
                        with open(caminho_arquivo, 'rb') as f:
                            pdf_bytes = f.read()
                    else:
                        arquivo_obj = getattr(documento['path'], documento['file'])
                        pdf_bytes = bytes(arquivo_obj.data)
                    
                    validate_pdf_content(pdf_bytes)
                    total_size += len(pdf_bytes)
                    
                    if total_size > MAX_TOTAL_SIZE:
                        raise PDFGenerationError(f"Tamanho total excede {MAX_TOTAL_SIZE//(1024*1024)}MB")

                    pdf = sanear_pdf(
                        pdf_bytes, 
                        titulo=documento["title"], 
                        data_modificacao=documento["data"]
                    )
                    
                    if not pdf:
                        raise PDFGenerationError(f"Documento corrompido: {documento['title']}")

                    start_page = len(pdf_mesclado) + 1
                    pdf_mesclado.insert_pdf(pdf)
                    end_page = len(pdf_mesclado)
                    num_pages = end_page - start_page + 1

                    documento['start_page'] = start_page
                    documento['end_page'] = end_page
                    documento['num_pages'] = num_pages
                    documentos_com_paginas.append(documento)

                    caminho_individual = secure_path_join(dir_base, f"{i:04d}.pdf")
                    with open(caminho_individual, 'wb') as f:
                        pdf.save(f, **PDF_OPTIONS)

                except Exception as e:
                    logger.error(f"Erro ao processar {documento['file']}: {str(e)}", exc_info=True)
                    raise PDFGenerationError(f"Erro ao processar documento: {documento['title']}")

            if len(pdf_mesclado) > MAX_PAGES:
                raise PDFGenerationError(f"Número de páginas excede o limite de {MAX_PAGES}")

            self._adicionar_rodape_e_metadados(pdf_mesclado, id_processo)

            return pdf_mesclado, documentos_com_paginas
            
        except Exception as e:
            logger.error(f"Erro na mesclagem de documentos: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha na mesclagem de documentos: {str(e)}")

    def salvar_paginas_individuais(self, pdf_final, dir_paginas, id_processo):
        """Salva páginas individuais com numeração consistente"""
        try:
            if not os.path.exists(dir_paginas):
                os.makedirs(dir_paginas, mode=0o700)

            for page_num in range(len(pdf_final)):
                nome_arquivo = f"pg_{page_num + 1:04d}.pdf"
                caminho_arquivo = secure_path_join(dir_paginas, nome_arquivo)

                with fitz.open() as pagina_pdf:
                    pagina_pdf.insert_pdf(pdf_final, from_page=page_num, to_page=page_num)
                    
                    pagina_pdf.set_metadata({
                        "title": f"{id_processo} - Página {page_num + 1}",
                        "creator": "Sistema de Processo Legislativo"
                    })
                    
                    pagina_pdf.save(caminho_arquivo, **PDF_OPTIONS)
                    
        except Exception as e:
            logger.error(f"Erro ao salvar páginas individuais: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha ao salvar páginas individuais: {str(e)}")

    def _adicionar_rodape_e_metadados(self, pdf, id_processo):
        """Adiciona rodapé e metadados consistentes ao PDF"""
        total_paginas = len(pdf)
    
        for num_pagina in range(total_paginas):
            pagina = pdf[num_pagina]
            largura = pagina.rect.width
        
            # Texto do rodapé
            texto_rodape = f"{id_processo} | Pág. {num_pagina + 1}/{total_paginas}"
            posicao = fitz.Point(largura - 100, 20)
        
            forma = pagina.new_shape()
            forma.insert_text(
                posicao, 
                texto_rodape, 
                fontname="helv", 
                fontsize=8,
                color=fitz.utils.getColor("gray")
            )
            forma.commit()

        # Metadados consistentes
        pdf.set_metadata({
            "title": id_processo,
            "creator": "Sistema de Processo Legislativo",
            "producer": "PyMuPDF",
            "creationDate": DateTime().strftime('%Y-%m-%d %H:%M:%S')
        })

    def render(self, cod_materia, action='json'):
        """
        Se action=='download', retorna o PDF;
        se action=='json', retorna somente a lista formatada.
        """
        try:
            # 1. Preparação
            dir_base, dir_paginas = self.preparar_diretorios(cod_materia)
            dados_materia = self.obter_dados_materia(cod_materia)
            documentos_raw = self.coletar_documentos(dados_materia, dir_base)
            
            # 2. Mesclar documentos obtendo também o mapeamento de páginas
            pdf_final, documentos_com_paginas = self.mesclar_documentos(
                documentos_raw, dir_base, dados_materia['id_exibicao']
            )
            total_paginas = len(pdf_final)

            # 3. Salvar páginas individuais
            self.salvar_paginas_individuais(pdf_final, dir_paginas, dados_materia['id_exibicao'])

            # 4. Formatando a resposta
            result = {
                'documentos': [],
                'total_paginas': total_paginas,
                'id_processo': dados_materia['id_exibicao']
            }

            base_url = f"{self.context.absolute_url()}/@@pagina_processo_leg_integral"
            
            for i, doc in enumerate(documentos_com_paginas, 1):
                doc_id = f"{i:04d}.pdf"
                first_page = doc['start_page']
                first_id = f"pg_{first_page:04d}.pdf"
                
                paginas = []
                for page_num in range(doc['start_page'], doc['end_page'] + 1):
                    pg_id = f"pg_{page_num:04d}.pdf"
                    paginas.append({
                        'num_pagina': str(page_num),
                        'id_pagina': pg_id,
                        'url': f"{base_url}?cod_materia={cod_materia}%26pagina={pg_id}"
                    })
                
                result['documentos'].append({
                    'id': doc_id,
                    'title': doc['title'],
                    'data': doc['data'],
                    'url': f"{base_url}?cod_materia={cod_materia}%26pagina={first_id}",
                    'paginas_geral': total_paginas,
                    'paginas': paginas,
                    'id_paginas': [p['id_pagina'] for p in paginas],
                    'paginas_doc': doc['num_pages']
                })

            # 5. Retornar conforme o action
            if action == 'json':
                return result
            if action == 'download':
                nome_final = f"{dados_materia['id']}.pdf"
                caminho_final = os.path.join(dir_base, nome_final)
                pdf_final.save(caminho_final, **PDF_OPTIONS)
                with open(caminho_final, 'rb') as f:
                    conteudo = f.read()
                self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
                self.request.RESPONSE.setHeader(
                    'Content-Disposition',
                    f'inline; filename="{nome_final}"'
                )
                return conteudo

            return result
        
        except Exception as e:
            logger.error(f"Erro no render: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return {'error': str(e)}

class PaginaProcessoLeg(grok.View):
    """Exibe página individual usando secure_path_join."""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_leg_integral')
    TEMP_DIR_PREFIX = 'processo_leg_integral_'

    @property
    def temp_base(self):
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        return secure_path_join(install_home, 'var/tmp')

    def render(self, cod_materia, pagina):
        dir_hash = hashlib.md5(str(cod_materia).encode()).hexdigest()
        dir_base = secure_path_join(self.temp_base, f'{self.TEMP_DIR_PREFIX}{dir_hash}')
        dir_pages = secure_path_join(dir_base, 'pages')
        file_path = secure_path_join(dir_pages, pagina)

        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            resp = self.context.REQUEST.response
            resp.setHeader('Content-Type', 'application/pdf')
            resp.setHeader('Content-Disposition', f'inline; filename="{pagina}"')
            return data
        except FileNotFoundError:
            self.request.response.setStatus(404)
            return "Página não encontrada"
        except SecurityError:
            self.request.response.setStatus(403)
            return "Acesso não permitido"

class LimparProcessoLegView(grok.View):
    """Visualização para limpeza de diretórios temporários."""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_integral_limpar')
    
    @property
    def temp_base(self):
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        return os.path.abspath(os.path.join(install_home, 'var/tmp'))

    def render(self, cod_materia):
        try:
            if not cod_materia or not str(cod_materia).isdigit():
                raise ValueError("Código da matéria inválido")
            
            dir_hash = hashlib.md5(str(cod_materia).encode()).hexdigest()
            dir_base = os.path.join(self.temp_base, f'processo_leg_integral_{dir_hash}')
            
            if not os.path.abspath(dir_base).startswith(self.temp_base):
                raise SecurityError("Tentativa de acesso a caminho não permitido")
            
            if os.path.exists(dir_base):
                shutil.rmtree(dir_base)
                return f"Diretório temporário '{dir_base}' removido com sucesso."
            return f"Diretório '{dir_base}' não existe ou já foi removido."
            
        except SecurityError as e:
            logger.error(f"Erro de segurança: {str(e)}", exc_info=True)
            self.request.RESPONSE.setStatus(403)
            return "Acesso não permitido"
            
        except Exception as e:
            logger.error(f"Erro ao limpar diretório temporário: {str(e)}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return f"Erro ao limpar diretório temporário: {str(e)}"
