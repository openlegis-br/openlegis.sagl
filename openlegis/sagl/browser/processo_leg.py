# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import hashlib
import gc
import sys
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, wraps
import time
from typing import List, Dict, Any, Tuple, Optional
from DateTime import DateTime
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import fitz
import logging
import pikepdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.pdfgen import canvas
from reportlab.rl_config import defaultPageSize
from reportlab.lib.units import mm, inch
from PIL import Image as PILImage


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuração de logging de performance
perf_logger = logging.getLogger('performance')
perf_logger.setLevel(logging.DEBUG)
perf_handler = logging.FileHandler('performance_metrics.log')
perf_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
perf_logger.addHandler(perf_handler)

# Configurações globais de performance
sys.setrecursionlimit(10000)
gc.disable()

# Constantes para otimização de PDF
PDF_OPTIMIZATION_SETTINGS = {
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
MAX_WORKERS = 4

# Cache de temas e estilos
_style_cache = {}
_theme = {
    'primary': '#003366',
    'secondary': '#E1F5FE',
    'success': '#4CAF50',
    'danger': '#F44336',
    'warning': '#FFC107',
    'light_gray': '#F5F5F5',
    'text': '#212121',
    'muted': '#757575'
}

class PDFGenerationError(Exception):
    """Exceção personalizada para erros na geração de PDF"""
    pass

class SecurityError(Exception):
    """Exceção para problemas de segurança"""
    pass

def timeit(func):
    """Decorator para medição de tempo de execução"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        gc.enable()
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start_time
            perf_logger.debug(f"{func.__name__} executed in {elapsed:.4f} seconds")
            gc.disable()
        return result
    return wrapper

@lru_cache(maxsize=32)
def get_cached_styles():
    """Retorna estilos com cache para melhor performance"""
    if not _style_cache:
        # 1) Load the standard sample stylesheet and copy only the named styles
        base_styles = getSampleStyleSheet()
        for name, style in base_styles.byName.items():
            _style_cache[name] = style

        # 2) Define your custom styles, including the missing Totalizador* ones
        custom_styles = {
            'Header1': ParagraphStyle(
                name='Header1',
                parent=_style_cache['Heading1'],
                fontSize=14, leading=18,
                alignment=TA_CENTER,
                textColor=colors.HexColor(_theme['primary'])
            ),
            'Header2': ParagraphStyle(
                name='Header2',
                parent=_style_cache['Heading2'],
                fontSize=11, leading=13,
                alignment=TA_LEFT,
                textColor=colors.HexColor(_theme['primary'])
            ),
            'Label': ParagraphStyle(
                name='Label',
                parent=_style_cache['Normal'],
                fontSize=9, leading=11,
                alignment=TA_LEFT,
                textColor=colors.HexColor(_theme['muted'])
            ),
            'Value': ParagraphStyle(
                name='Value',
                parent=_style_cache['Normal'],
                fontSize=9, leading=11,
                alignment=TA_LEFT,
                textColor=colors.HexColor(_theme['text'])
            ),
            'VoteResult': ParagraphStyle(
                name='VoteResult',
                parent=_style_cache['Normal'],
                fontSize=12, leading=15,
                alignment=TA_CENTER,
                textColor=colors.white,
                backColor=colors.HexColor(_theme['primary'])
            ),

            # ——— The missing Totalizador styles ———
            'TotalizadorCabecalho': ParagraphStyle(
                name='TotalizadorCabecalho',
                parent=_style_cache['Heading4'],
                fontSize=9, leading=11,
                alignment=TA_CENTER,
                textColor=colors.white
            ),
            'TotalizadorConteudo': ParagraphStyle(
                name='TotalizadorConteudo',
                parent=_style_cache['Normal'],
                fontSize=9, leading=11,
                alignment=TA_CENTER,
                textColor=colors.HexColor(_theme['text'])
            ),
            'TotalizadorDestaque': ParagraphStyle(
                name='TotalizadorDestaque',
                parent=_style_cache['Heading4'],
                fontSize=9, leading=11,
                alignment=TA_CENTER,
                textColor=colors.HexColor(_theme['primary'])
            ),
        }

        _style_cache.update(custom_styles)

    return _style_cache


def validate_pdf_content(pdf_bytes: bytes) -> bool:
    """Valida se o conteúdo é um PDF válido e dentro dos limites de tamanho"""
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise PDFGenerationError(f"PDF size exceeds {MAX_PDF_SIZE//(1024*1024)}MB limit")
    if not pdf_bytes.startswith(b'%PDF-'):
        raise PDFGenerationError("Invalid PDF file signature")
    return True

def secure_path_join(base_path: str, *paths: str) -> str:
    """Junção segura de caminhos com verificações de segurança"""
    base = os.path.abspath(base_path)
    full_path = os.path.abspath(os.path.join(base, *paths))

    # Verificações de segurança
    if not os.path.exists(base):
        raise SecurityError(f"Base path does not exist: {base}")
    if not os.path.isdir(base):
        raise SecurityError(f"Base path is not a directory: {base}")
    if not full_path.startswith(base + os.sep):
        raise SecurityError(f"Path traversal attempt detected: {full_path}")
    if os.path.islink(full_path):
        raise SecurityError(f"Symbolic links not allowed: {full_path}")

    return full_path

def check_pdf_security(pdf_bytes: bytes) -> bool:
    """Verifica se o PDF contém elementos potencialmente maliciosos"""
    try:
        # Verificação com pikepdf
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                if '/JS' in page or '/JavaScript' in page:
                    raise SecurityError("PDF contains JavaScript")

        # Verificação adicional com fitz
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                if page.get_links() or page.get_xobjects():
                    logger.warning("PDF contains interactive elements")

        return True
    except Exception as e:
        logger.error(f"PDF security check failed: {e}")
        raise SecurityError(f"PDF security check failed: {e}")

def optimize_pdf_content(pdf_bytes: bytes, title: str = None,
                        modification_date: str = None) -> bytes:
    """Otimiza e limpa o conteúdo do PDF"""
    try:
        # Primeira passagem com fitz para otimização básica
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            if len(doc) > MAX_PAGES:
                raise PDFGenerationError(f"PDF exceeds {MAX_PAGES} pages limit")

            # Atualiza metadados se fornecidos
            if title or modification_date:
                metadata = doc.metadata or {}
                if title:
                    metadata["title"] = str(title)[:100]
                if modification_date:
                    metadata["modDate"] = str(modification_date)
                doc.set_metadata(metadata)

            # Salva em buffer com otimizações
            doc.bake()
            output_buffer = BytesIO()
            doc.save(output_buffer, **PDF_OPTIMIZATION_SETTINGS)
            optimized_bytes = output_buffer.getvalue()

    except Exception as e:
        logger.warning(f"Primary PDF optimization failed, trying fallback: {e}")
        # Fallback com pikepdf
        try:
            with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
                # Remove elementos potencialmente perigosos
                for page in pdf.pages:
                    if '/Annots' in page:
                        del page.Annots
                    if '/AA' in page:
                        del page.AA

                output_buffer = BytesIO()
                pdf.save(output_buffer)
                optimized_bytes = output_buffer.getvalue()
        except Exception as e:
            logger.error(f"Fallback PDF optimization failed: {e}")
            raise PDFGenerationError(f"Failed to optimize PDF: {e}")

    # Validações finais
    validate_pdf_content(optimized_bytes)
    check_pdf_security(optimized_bytes)

    return optimized_bytes

def build_header_content(dados_votacao: Dict, nome_camara: str,
                        styles: Dict, logo_bytes: bytes = None) -> Tuple[Table, List[Any]]:
    """Constrói o cabeçalho do documento"""
    elements = []

    # Logo handling
    logo_img = None
    if logo_bytes:
        try:
            logo_img = Image(BytesIO(logo_bytes), width=50, height=50)
        except Exception as e:
            logger.warning(f"Failed to process logo: {e}")

    # Header content
    title_text = f"<b>{nome_camara}</b><br/>{dados_votacao.get('sessao', '')}"
    title_para = Paragraph(title_text, styles['Header1'])
    doc_id = hashlib.md5(str(dados_votacao).encode()).hexdigest()[:8]
    id_para = Paragraph(f"ID: {doc_id}", styles['Label'])

    header_data = [
        [logo_img if logo_img else '', title_para, ''],
        ['', Paragraph("REGISTRO DE VOTAÇÃO", styles['Header1']), id_para]
    ]

    header_table = Table(header_data, colWidths=[60, '*', 80])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (1,0), (1,0), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
        ('ALIGN', (0,1), (0,1), 'CENTER'),
        ('ALIGN', (2,1), (2,1), 'RIGHT'),
        ('LINEBELOW', (1,1), (1,1), 1, colors.HexColor(_theme['primary'])),
        ('BOTTOMPADDING', (0,1), (-1,1), 10),
    ]))

    elements.append(header_table)
    return header_table, elements

def build_session_table(dados_votacao: Dict, styles: Dict) -> Table:
    """Constrói a tabela de informações da sessão"""
    session_data = [
        [
            Paragraph("<b>Sessão:</b>", styles['Label']),
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
            Paragraph('', styles['Label']),
            Paragraph('', styles['Value'])
        ]
    ]

    session_table = Table(session_data, colWidths=['20%','30%','20%','30%'], hAlign='LEFT')
    session_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#EEEEEE')),
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))

    return session_table

def build_materia_section(dados_votacao: Dict, styles: Dict, elements: List[Any]) -> None:
    """Constrói a seção de informações da matéria"""
    materia_title = f"{dados_votacao.get('tipo_materia','')} nº {dados_votacao.get('num_materia','')}/{dados_votacao.get('ano_materia','')}"
    elements.append(Paragraph(materia_title, styles['Header2']))

    autoria_text = f"<b>Autoria:</b> {dados_votacao.get('autoria_materia','')}"
    elements.append(Paragraph(autoria_text, styles['Value']))
    elements.append(Spacer(1, 5))

    ementa_style = ParagraphStyle(
        'EmentaStyle', parent=styles['Value'],
        alignment=TA_JUSTIFY,
        backColor=colors.HexColor(_theme['light_gray']),
        borderPadding=5,
        spaceAfter=15
    )
    ementa_text = f"<b>Ementa:</b> {dados_votacao.get('ementa_materia','')}"
    elements.append(Paragraph(ementa_text, ementa_style))

def build_voting_results(dados_votacao: Dict, styles: Dict, elements: List[Any]) -> None:
    """Constrói a seção de resultados da votação"""
    result_text = f"RESULTADO: {dados_votacao.get('txt_resultado','').upper()}"
    elements.append(Paragraph(result_text, styles['VoteResult']))

def build_voting_details(dados_votacao: Dict, styles: Dict, elements: List[Any]) -> None:
    """Constrói a tabela de detalhes da votação nominal"""
    if dados_votacao.get('txt_tipo_votacao') != 'Nominal':
        return

    elements.append(Paragraph('DETALHAMENTO DA VOTAÇÃO', styles['Header2']))

    table_data = [[
        Paragraph('Vereador', styles['TotalizadorCabecalho']),
        Paragraph('Partido', styles['TotalizadorCabecalho']),
        Paragraph('Voto', styles['TotalizadorCabecalho'])
    ]]

    vote_colors = {
        'Sim': colors.HexColor(_theme['success']),
        'Nao': colors.HexColor(_theme['danger']),
        'Abstencao': colors.HexColor(_theme['warning']),
        'Ausente': colors.HexColor(_theme['light_gray']),
        'Na Presid.': colors.HexColor(_theme['secondary'])
    }

    for v in dados_votacao.get('votos_nominais', []):
        vote = v.get('voto','').strip()
        table_data.append([
            Paragraph(v.get('nom_completo',''), styles['Value']),
            Paragraph(v.get('partido',''), styles['Value']),
            Paragraph(vote, styles['Value'])
        ])

    vote_table = Table(table_data, colWidths=['50%', '30%', '20%'], repeatRows=1)
    vote_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(_theme['primary'])),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#EEEEEE')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#FAFAFA')])
    ]))

    for i, row in enumerate(table_data[1:], start=1):
        vote = row[2].text
        if vote in vote_colors:
            vote_table.setStyle(TableStyle([
                ('BACKGROUND', (2,i), (2,i), vote_colors[vote])
            ]))

    elements.extend([vote_table, Spacer(1, 15)])

def build_totals_table(dados_votacao: Dict, styles: Dict, elements: List[Any]) -> None:
    """Constrói a tabela de totalização de votos"""
    tot_sim = int(dados_votacao.get('num_votos_sim') or 0)
    tot_nao = int(dados_votacao.get('num_votos_nao') or 0)
    tot_abst = int(dados_votacao.get('num_abstencao') or 0)
    tot_aus = int(dados_votacao.get('num_ausentes') or 0)
    tot_pres = sum(1 for v in dados_votacao.get('votos_nominais', [])
                  if v.get('voto','').strip() == 'Na Presid.') if dados_votacao.get('txt_tipo_votacao') == 'Nominal' else 0
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(_theme['primary'])),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor(_theme['light_gray'])),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor(_theme['primary'])),
        ('BACKGROUND', (0,1), (0,1), colors.HexColor('#E8F5E9')),
        ('BACKGROUND', (0,2), (0,2), colors.HexColor('#FFEBEE')),
        ('BACKGROUND', (0,3), (0,3), colors.HexColor('#FFF8E1')),
    ]))

    elements.append(Paragraph('TOTALIZAÇÃO DE VOTOS', styles['Header2']))
    elements.append(total_table)

def add_footer(canvas, doc):
    """Adiciona rodapé às páginas do PDF"""
    canvas.saveState()
    margin_left = 15 * mm
    canvas.setStrokeColor(colors.HexColor(_theme['primary']))
    canvas.setLineWidth(0.5)
    canvas.line(margin_left, 40, doc.width + margin_left, 40)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.HexColor(_theme['muted']))
    canvas.drawString(margin_left, 30, f"Documento gerado eletronicamente")
    footer_text = f"{DateTime().strftime('%d/%m/%Y %H:%M')} | Página {canvas.getPageNumber()}"
    canvas.drawRightString(doc.width + margin_left, 30, footer_text)
    canvas.restoreState()

@timeit
def gerar_ficha_votacao_pdf(dados_votacao: Dict, caminho_saida: str,
                           nome_camara: str, nome_sessao: str,
                           logo_bytes: bytes = None) -> None:
    """Gera o PDF da ficha de votação com otimizações de performance"""
    try:
        # Configuração do documento
        buffer = BytesIO()
        styles = get_cached_styles()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=5*mm,
            bottomMargin=20*mm
        )

        # Construção do conteúdo
        elements = []

        # 1. Cabeçalho
        header_table, header_elements = build_header_content(dados_votacao, nome_camara, styles, logo_bytes)
        elements.extend(header_elements)

        # 2. Informações da sessão
        session_table = build_session_table(dados_votacao, styles)
        elements.extend([session_table, Spacer(1, 15)])

        # 3. Informações da matéria
        build_materia_section(dados_votacao, styles, elements)

        # 4. Resultado da votação
        build_voting_results(dados_votacao, styles, elements)

        # 5. Detalhamento nominal (se aplicável)
        build_voting_details(dados_votacao, styles, elements)

        # 6. Totalizadores
        build_totals_table(dados_votacao, styles, elements)

        # Construção do documento com rodapé
        doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

        # Otimização e salvamento em paralelo
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(optimize_and_save_pdf, buffer, caminho_saida)

        logger.info(f"PDF gerado com sucesso em: {caminho_saida}")

    except Exception as e:
        logger.error(f"Erro na geração do PDF: {str(e)}", exc_info=True)
        raise PDFGenerationError(f"Falha na geração do PDF: {str(e)}")
    finally:
        gc.enable()

def optimize_and_save_pdf(buffer: BytesIO, output_path: str) -> None:
    """Otimiza e salva o PDF em paralelo"""
    try:
        buffer.seek(0)
        with fitz.open(stream=buffer.read(), filetype="pdf") as doc:
            doc.save(output_path, **PDF_OPTIMIZATION_SETTINGS)
        logger.debug(f"PDF otimizado salvo em: {output_path}")
    except Exception as e:
        logger.error(f"Falha na otimização do PDF: {str(e)}", exc_info=True)
        raise

class ProcessoLegView(grok.View):
    """Visualização principal para geração do processo legislativo em PDF"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_integral')

    TEMP_DIR_PREFIX = 'processo_leg_integral_'

    def update(self):
        """Extrai parâmetros da requisição antes do render"""
        self.cod_materia = self.request.form.get('cod_materia')
        self.action = self.request.form.get('action', 'json')

    @property
    def temp_base(self) -> str:
        """
        Diretório base temporário seguro.
        Garante que INSTALL_HOME/var/tmp exista, ou usa system temp.
        """
        # 1) pick your install-home or fallback
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())

        # 2) build the var/tmp path under it
        base = os.path.abspath(os.path.join(install_home, 'var', 'tmp'))

        # 3) ensure it exists (mode 700 for safety)
        try:
            os.makedirs(base, mode=0o700, exist_ok=True)
        except Exception as e:
            logger.error(f"Não foi possível criar base temp '{base}': {e}")
            raise PDFGenerationError(f"Falha na preparação dos diretórios: {e}")

        # 4) return it (secure_path_join will let sub-dirs through)
        return base

    def preparar_diretorios(self, cod_materia: str) -> Tuple[str, str]:
        """Cria diretórios temporários de trabalho com segurança"""
        try:
            # 1) Validar código da matéria
            if not cod_materia or not str(cod_materia).isdigit():
                raise ValueError("Código da matéria inválido")

            # 2) Gerar hash único para este processamento
            dir_hash = hashlib.md5(str(cod_materia).encode()).hexdigest()
            prefix = f"{self.TEMP_DIR_PREFIX}{dir_hash}"

            # 3) Secure‐join para o diretório base (parent já existe via temp_base)
            dir_base = secure_path_join(self.temp_base, prefix)

            # 4) (Re)criar dir_base com permissão restrita
            if os.path.exists(dir_base):
                shutil.rmtree(dir_base, ignore_errors=True)
            os.makedirs(dir_base, mode=0o700, exist_ok=True)

            # 5) Secure‐join para o subdiretório de páginas (já que dir_base existe)
            dir_paginas = secure_path_join(dir_base, 'pages')
            os.makedirs(dir_paginas, mode=0o700, exist_ok=True)

            return dir_base, dir_paginas

        except Exception as e:
            logger.error(f"Erro ao preparar diretórios: {e}", exc_info=True)
            raise PDFGenerationError(f"Falha na preparação dos diretórios: {e}")

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

    def coletar_documentos(self, dados_materia: Dict, dir_base: str) -> List[Dict]:
        """Coleta documentos relacionados à matéria"""
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
            logo_bytes = bytes(logo_obj.data)

        documentos = []
        total_size = 0

        try:
            # Capa do processo
            arquivo_capa = f"capa_{dados_materia['tipo']}-{dados_materia['numero']}-{dados_materia['ano']}.pdf"
            self.context.modelo_proposicao.capa_processo(
                cod_materia=dados_materia['cod_materia'],
                action='gerar'
            )

            documentos.append({
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
                data_texto = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d 00:00:02')

            if hasattr(self.context.sapl_documentos.materia, arquivo_texto):
                documentos.append({
                    "data": data_texto,
                    "path": self.context.sapl_documentos.materia,
                    "file": arquivo_texto,
                    "title": f"{dados_materia['descricao']} nº {dados_materia['numero']}/{dados_materia['ano']}"
                })

            # Redação Final
            nom_redacao = f"{dados_materia['cod_materia']}_redacao_final.pdf"
            if hasattr(self.context.sapl_documentos.materia, nom_redacao):
                doc_redacao = {
                    "data": DateTime(dados_materia['data_apresentacao'], datefmt='international').strftime('%Y-%m-%d 00:00:03'),
                    "path": self.context.sapl_documentos.materia,
                    "file": nom_redacao,
                    "title": "Redação Final"
                }

                for proposicao in self.context.zsql.proposicao_obter_zsql(
                    cod_mat_ou_doc=dados_materia['cod_materia'],
                    ind_mat_ou_doc='M'
                ):
                    doc_redacao["data"] = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

                documentos.append(doc_redacao)

            # Fichas de votação
            votacoes = self.context.pysc.votacao_obter_pysc(cod_materia=dados_materia['cod_materia'])
            for i, votacao in enumerate(votacoes):
                fase = votacao.get('fase', '')
                if fase == "Expediente - Leitura de Matérias":
                   logger.info(f"Ignorando votação na fase: {fase}")
                   continue

                nome_arquivo = f'ficha_votacao_{i + 1}.pdf'
                caminho_arquivo = secure_path_join(dir_base, nome_arquivo)

                gerar_ficha_votacao_pdf(
                    votacao, caminho_arquivo, nome_camara, nome_sessao, logo_bytes=logo_bytes)

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

                documentos.append({
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

                    for proposta in self.context.zsql.proposicao_obter_zsql(
                        cod_substitutivo=substitutivo.cod_substitutivo
                    ):
                        doc_substitutivo["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

                    documentos.append(doc_substitutivo)

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

                    for proposta in self.context.zsql.proposicao_obter_zsql(
                        cod_parecer=relat.cod_relatoria
                    ):
                        doc_parecer["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

                    comissao = self.context.zsql.comissao_obter_zsql(
                        cod_comissao=relat.cod_comissao,
                        ind_excluido=0
                    )[0]
                    doc_parecer["title"] = (
                        f"Parecer {comissao.sgl_comissao} nº "
                        f"{relat.num_parecer}/{relat.ano_parecer}"
                    )

                    documentos.append(doc_parecer)

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
                    documentos.append(doc_anexada)

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

                            for proposta in self.context.zsql.proposicao_obter_zsql(
                                cod_mat_ou_doc=documento.cod_documento,
                                ind_mat_ou_doc='D'
                            ):
                                doc_acessorio["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

                            documentos.append(doc_acessorio)

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
                    documentos.append(doc_anexadora)

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

                            for proposta in self.context.zsql.proposicao_obter_zsql(
                                cod_mat_ou_doc=documento.cod_documento,
                                ind_mat_ou_doc='D'
                            ):
                                doc_acessorio["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

                            documentos.append(doc_acessorio)

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

                    for proposta in self.context.zsql.proposicao_obter_zsql(
                        cod_mat_ou_doc=documento.cod_documento,
                        ind_mat_ou_doc='D'
                    ):
                        doc_acessorio["data"] = DateTime(proposta.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

                    documentos.append(doc_acessorio)

            # Tramitações
            for tram in self.context.zsql.tramitacao_obter_zsql(
                cod_materia=dados_materia['cod_materia'],
                rd_ordem='1',
                ind_excluido=0
            ):
                arquivo_tram = f"{tram.cod_tramitacao}_tram.pdf"
                if hasattr(self.context.sapl_documentos.materia.tramitacao, arquivo_tram):
                    documentos.append({
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
                    documentos.append({
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

    def process_single_document(self, doc: Dict, dir_base: str) -> Tuple[bytes, Dict]:
        """Processa um documento individual para mesclagem"""
        try:
            if doc.get('filesystem'):
                # Filesystem-stored PDF
                pdf_path = secure_path_join(doc['path'], doc['file'])
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
            else:
                # Zope container-stored PDF
                container = doc['path']
                filename = doc['file']
                arquivo_obj = None

                # 1) Try attribute access
                if hasattr(container, filename):
                    arquivo_obj = getattr(container, filename)
                else:
                    # 2) Try dict-style access
                    try:
                        arquivo_obj = container[filename]
                    except (KeyError, TypeError):
                        arquivo_obj = None

                # 3) Try stripping ".pdf" if still not found
                if arquivo_obj is None and filename.lower().endswith('.pdf'):
                    base = filename[:-4]
                    if hasattr(container, base):
                        arquivo_obj = getattr(container, base)
                    else:
                        try:
                            arquivo_obj = container[base]
                        except Exception:
                            arquivo_obj = None

                if not arquivo_obj:
                    raise AttributeError(f"Could not locate PDF '{filename}' in container")

                # Extract bytes
                pdf_bytes = bytes(arquivo_obj.data)

            # Validate before returning
            validate_pdf_content(pdf_bytes)
            return pdf_bytes, doc

        except Exception as e:
            logger.warning(f"Erro ao processar documento '{doc.get('title','?')}': {e}")
            # Let the caller skip this doc
            raise

    @timeit
    def mesclar_documentos(self, documentos: List[Dict], dir_base: str,
                          id_processo: str) -> Tuple[fitz.Document, List[Dict]]:
        """Mescla documentos em um único PDF com tratamento de erros"""
        pdf_mesclado = fitz.open()
        documentos_com_paginas = []

        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for doc in documentos:
                    futures.append(executor.submit(
                        self.process_single_document, doc, dir_base))

                for future in futures:
                    try:
                        pdf_bytes, doc_info = future.result()

                        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
                            start_page = len(pdf_mesclado)
                            pdf_mesclado.insert_pdf(pdf)
                            doc_info.update({
                                'start_page': start_page + 1,
                                'end_page': len(pdf_mesclado),
                                'num_pages': len(pdf_mesclado) - start_page
                            })
                            documentos_com_paginas.append(doc_info)

                            # Limpeza periódica de memória
                            if len(pdf_mesclado) % 10 == 0:
                                gc.collect()

                    except Exception as e:
                        logger.warning(f"Ignorando documento devido ao erro: {str(e)}")
                        continue

            if len(pdf_mesclado) > MAX_PAGES:
                raise PDFGenerationError(f"Número de páginas excede o limite de {MAX_PAGES}")

            self._adicionar_rodape_e_metadados(pdf_mesclado, id_processo)

            return pdf_mesclado, documentos_com_paginas

        except Exception as e:
            logger.error(f"Erro na mesclagem de documentos: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha na mesclagem de documentos: {str(e)}")
        finally:
            gc.enable()

    def _adicionar_rodape_e_metadados(self, pdf: fitz.Document, id_processo: str) -> None:
        """Adiciona rodapé e metadados ao PDF mesclado"""
        for page_num in range(len(pdf)):
            page = pdf[page_num]
            page.insert_text(
                fitz.Point(page.rect.width - 110, 20),
                f"{id_processo} | Fls. {page_num + 1}/{len(pdf)}",
                fontsize=8,
                color=fitz.utils.getColor("gray")
            )

        pdf.set_metadata({
            "title": id_processo,
            "creator": "SAGL",
            "producer": "PyMuPDF",
            "creationDate": DateTime().strftime('%Y-%m-%d %H:%M:%S')
        })
        pdf.bake()

    @timeit
    def salvar_paginas_individuais(self, pdf_final: fitz.Document,
                                 dir_paginas: str, id_processo: str) -> None:
        """Salva páginas individuais com paralelismo"""
        try:
            os.makedirs(dir_paginas, mode=0o700, exist_ok=True)

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for page_num in range(len(pdf_final)):
                    executor.submit(
                        self._save_single_page,
                        pdf_final,
                        page_num,
                        dir_paginas,
                        id_processo
                    )
        except Exception as e:
            logger.error(f"Erro ao salvar páginas individuais: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha ao salvar páginas individuais: {str(e)}")

    def _save_single_page(self, pdf_final: fitz.Document, page_num: int,
                         dir_paginas: str, id_processo: str) -> None:
        """Salva uma única página do PDF"""
        nome_arquivo = f"pg_{page_num + 1:04d}.pdf"
        caminho_arquivo = secure_path_join(dir_paginas, nome_arquivo)

        try:
            with fitz.open() as pagina_pdf:
                pagina_pdf.insert_pdf(pdf_final, from_page=page_num, to_page=page_num)
                pagina_pdf.set_metadata({
                    "title": f"{id_processo} - Página {page_num + 1}",
                    "creator": "Sistema de Processo Legislativo"
                })
                pagina_pdf.bake()
                pagina_pdf.save(caminho_arquivo, **PDF_OPTIMIZATION_SETTINGS)
        except Exception as e:
            logger.error(f"Erro ao salvar página {page_num + 1}: {str(e)}")
            raise

    def _formatar_resultado(self, documentos: List[Dict], pdf_final: fitz.Document,
                          cod_materia: str, dados_materia: Dict) -> Dict:
        """Formata o resultado final para resposta JSON"""
        result = {
            'documentos': [],
            'total_paginas': len(pdf_final),
            'id_processo': dados_materia['id_exibicao']
        }

        base_url = f"{self.context.absolute_url()}/@@pagina_processo_leg_integral"

        for i, doc in enumerate(documentos, 1):
            doc_id = f"{i:04d}.pdf"
            first_page = doc.get('start_page', 1)
            first_id = f"pg_{first_page:04d}.pdf"

            paginas = []
            for page_num in range(doc.get('start_page', 1), doc.get('end_page', 1) + 1):
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
                'paginas_geral': len(pdf_final),
                'paginas': paginas,
                'id_paginas': [p['id_pagina'] for p in paginas],
                'paginas_doc': doc.get('num_pages', len(paginas))
            })

        return result

    def _handle_download(self, pdf_final: fitz.Document, dir_base: str,
                        doc_id: str) -> bytes:
        """Prepara o PDF final para download"""
        nome_final = f"{doc_id}.pdf"
        caminho_final = os.path.join(dir_base, nome_final)

        pdf_final.save(caminho_final, **PDF_OPTIMIZATION_SETTINGS)

        with open(caminho_final, 'rb') as f:
            conteudo = f.read()

        self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
        self.request.RESPONSE.setHeader(
            'Content-Disposition',
            f'inline; filename="{nome_final}"'
        )
        return conteudo

    @timeit
    def render(self):
        """Método principal para geração do processo legislativo"""
        try:
            if not self.cod_materia:
                raise ValueError("O parâmetro cod_materia é obrigatório")

            gc.disable()

            # Processamento paralelo inicial
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_dados = self.obter_dados_materia(self.cod_materia)
                future_dirs = executor.submit(self.preparar_diretorios, self.cod_materia)

                dados_materia = future_dados
                dir_base, dir_paginas = future_dirs.result()

            # Resto da implementação original...
            documentos = self.coletar_documentos(dados_materia, dir_base)
            pdf_final, documentos_com_paginas = self.mesclar_documentos(
                documentos, dir_base, dados_materia['id_exibicao'])

            self.salvar_paginas_individuais(
                pdf_final, dir_paginas, dados_materia['id_exibicao'])

            result = self._formatar_resultado(
                documentos_com_paginas, pdf_final, self.cod_materia, dados_materia)

            if self.action == 'download':
                return self._handle_download(pdf_final, dir_base, dados_materia['id'])

            return result

        except ValueError as ve:
            logger.error(f"Erro de validação: {str(ve)}")
            self.request.RESPONSE.setStatus(400)
            return {'error': str(ve)}
        except Exception as e:
            logger.error(f"Erro no render: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return {'error': str(e)}
        finally:
            gc.enable()

class PaginaProcessoLeg(grok.View):
    """Visualização para páginas individuais do processo"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_leg_integral')

    TEMP_DIR_PREFIX = 'processo_leg_integral_'

    @property
    def temp_base(self) -> str:
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        return secure_path_join(install_home, 'var/tmp')

    def render(self, cod_materia, pagina):
        dir_hash = hashlib.md5(str(cod_materia).encode()).hexdigest()
        dir_base = secure_path_join(
            self.temp_base,
            f'{self.TEMP_DIR_PREFIX}{dir_hash}'
        )
        dir_pages = secure_path_join(dir_base, 'pages')
        file_path = secure_path_join(dir_pages, pagina)

        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
            self.request.RESPONSE.setHeader(
                'Content-Disposition',
                f'inline; filename="{pagina}"'
            )
            return data
        except FileNotFoundError:
            self.request.RESPONSE.setStatus(404)
            return "Página não encontrada"
        except SecurityError:
            self.request.RESPONSE.setStatus(403)
            return "Acesso não permitido"

class LimparProcessoLegView(grok.View):
    """Visualização para limpeza de diretórios temporários"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_integral_limpar')

    @property
    def temp_base(self) -> str:
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
