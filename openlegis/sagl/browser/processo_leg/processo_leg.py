# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import hashlib
import gc
import sys
import time
import json
import urllib.request
import urllib.error
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import List, Dict, Any, Tuple
from DateTime import DateTime
from five import grok
from zope.interface import Interface
import fitz
import logging
import pikepdf
from datetime import date, datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm, inch
from PIL import Image as PILImage
from openlegis.sagl import get_base_path
from Products.CMFCore.utils import getToolByName
from z3c.saconfig import named_scoped_session
from sqlalchemy import and_, or_
from openlegis.sagl.models.models import (
    MateriaLegislativa, TipoMateriaLegislativa, Emenda, TipoEmenda,
    Substitutivo, Relatoria, Comissao, Anexada, DocumentoAcessorio,
    Tramitacao, StatusTramitacao, NormaJuridica, VinculoNormaJuridica,
    TipoNormaJuridica, Proposicao, Parecer, TipoProposicao
)
from openlegis.sagl.browser.processo_leg.processo_leg_utils import (
    get_processo_dir,
    get_processo_dir_hash,
    safe_check_file,
    safe_check_files_batch,
    secure_path_join,
    SecurityError,
    TEMP_DIR_PREFIX
)
try:
    from appy.pod.renderer import Renderer
except ImportError:
    Renderer = None  # Fallback se não disponível

# CONFIGURAÇÃO DE LOGGING CORRIGIDA - SEM RESOURCE LEAKS
def setup_logging():
    """Configura o logging de forma segura sem resource leaks"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove handlers existentes para evitar duplicação
    for handler in logger.handlers[:]:
        try:
            handler.close()  # ✅ FECHA o handler antes de remover
            logger.removeHandler(handler)
        except Exception as e:
            print(f"Erro ao fechar handler: {e}")
    
    # Formatter comum
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # FileHandler com contexto seguro
    try:
        base_path = get_base_path()
        log_path = os.path.join(base_path, 'pdf_generation.log')
        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Erro ao criar file handler: {e}")
    
    # StreamHandler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger  # ✅ Retorna o logger para reutilização

# Inicializa o logging UMA ÚNICA VEZ
logger = setup_logging()

# Configuração SQLAlchemy
Session = named_scoped_session('minha_sessao')

def _convert_to_datetime_string(date_obj):
    """
    Converte objetos datetime.date ou datetime.datetime para string
    compatível com DateTime() do Zope.
    """
    if date_obj is None:
        return None
    if isinstance(date_obj, (date, datetime)):
        # Converte para string no formato ISO
        if isinstance(date_obj, datetime):
            return date_obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return date_obj.strftime('%Y-%m-%d')
    # Se já for string ou DateTime, retorna como está
    return str(date_obj)

# Configuração de logging de performance
perf_logger = logging.getLogger('performance')
perf_logger.setLevel(logging.DEBUG)
try:
    base_path = get_base_path()
    perf_log_path = os.path.join(base_path, 'performance_metrics.log')
    perf_handler = logging.FileHandler(perf_log_path, mode='a', encoding='utf-8')
    perf_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    perf_logger.addHandler(perf_handler)
except Exception as e:
    print(f"Erro ao criar perf handler: {e}")

# Configurações globais de performance
sys.setrecursionlimit(10000)

# Constantes para otimização de PDF
PDF_OPTIMIZATION_SETTINGS = {
    'garbage': 3,
    'deflate': True,
    #'clean': True,
    'use_objstms': True
}

# Limites de segurança
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB
MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500MB
MAX_PAGES = 5000
MAX_DOCUMENTS = 500
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

def timeit(func):
    """Decorator para medição de tempo de execução"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start_time
        # Log de performance removido para reduzir verbosidade
        return result
    return wrapper

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

def build_header_content(dados_votacao: Dict, nome_camara: str,
                        styles: Dict, portal=None) -> Tuple[Table, List[Any]]:
    """Constrói o cabeçalho do documento"""
    elements = []

    # Tenta obter o brasão da casa
    brasao_image = None
    if portal:
        try:
            tool = getToolByName(portal, 'portal_sagl')
            if tool:
                brasao_bytes = tool.get_brasao()
                if brasao_bytes:
                    brasao_buffer = BytesIO(brasao_bytes)
                    try:
                        # Tenta abrir como PIL Image para validar
                        pil_img = PILImage.open(brasao_buffer)
                        brasao_buffer.seek(0)
                        # Cria Image do ReportLab - tamanho ajustado para alinhar com título e subtítulo
                        brasao_image = Image(brasao_buffer, width=20*mm, height=20*mm, kind='proportional')
                    except Exception as e:
                        logger.warning(f"Erro ao processar brasão: {e}")
        except Exception as e:
            logger.warning(f"Erro ao obter brasão: {e}")

    # Header content
    title_text = f"<b>{nome_camara}</b><br/>{dados_votacao.get('sessao', '')}"
    title_para = Paragraph(title_text, styles['Header1'])
    doc_id = hashlib.md5(str(dados_votacao).encode()).hexdigest()[:8]
    id_para = Paragraph(f"ID: {doc_id}", styles['Label'])

    # Monta o cabeçalho com brasão (se disponível)
    if brasao_image:
        header_data = [
            [brasao_image, title_para, ''],
            ['', Paragraph("REGISTRO DE VOTAÇÃO", styles['Header1']), id_para]
        ]
        col_widths = [28, '*', 80]  # Largura ajustada para o tamanho do brasão
    else:
        header_data = [
            [title_para, ''],
            [Paragraph("REGISTRO DE VOTAÇÃO", styles['Header1']), id_para]
        ]
        col_widths = ['*', 80]

    header_table = Table(header_data, colWidths=col_widths)
    
    if brasao_image:
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (0,0), 'TOP'),  # Brasão alinhado no topo
            ('VALIGN', (1,0), (-1,0), 'MIDDLE'),
            ('ALIGN', (0,0), (0,0), 'CENTER'),
            ('ALIGN', (1,0), (1,0), 'LEFT'),
            ('LEFTPADDING', (0,0), (0,1), 5*mm),  # Margem esquerda adicional
            ('TOPPADDING', (0,0), (0,0), 0),  # Sem padding superior para manter brasão no topo
            ('BOTTOMPADDING', (0,0), (0,0), 0),  # Sem padding inferior na célula do brasão
            ('BOTTOMPADDING', (1,0), (-1,0), 6),  # Padding inferior apenas nas outras células
            ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
            ('ALIGN', (1,1), (1,1), 'LEFT'),
            ('ALIGN', (2,1), (2,1), 'RIGHT'),
            ('LINEBELOW', (1,1), (1,1), 1, colors.HexColor(_theme['primary'])),
            ('BOTTOMPADDING', (0,1), (-1,1), 10),
            ('SPAN', (0,0), (0,1)),  # Brasão ocupa duas linhas
        ]))
    else:
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
            ('ALIGN', (0,0), (0,0), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
            ('ALIGN', (0,1), (0,1), 'LEFT'),
            ('ALIGN', (1,1), (1,1), 'RIGHT'),
            ('LINEBELOW', (0,1), (0,1), 1, colors.HexColor(_theme['primary'])),
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
                           nome_camara: str, nome_sessao: str, portal=None) -> None:
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
        header_table, header_elements = build_header_content(dados_votacao, nome_camara, styles, portal)
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


    except Exception as e:
        logger.error(f"Erro na geração do PDF: {str(e)}", exc_info=True)
        raise PDFGenerationError(f"Falha na geração do PDF: {str(e)}")

def optimize_and_save_pdf(buffer: BytesIO, output_path: str) -> None:
    """Otimiza e salva o PDF em paralelo"""
    try:
        buffer.seek(0)
        with fitz.open(stream=buffer.read(), filetype="pdf") as doc:
            doc.bake()
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

    def _get_session(self):
        """Retorna sessão SQLAlchemy thread-safe"""
        return Session()

    def _get_dir_hash(self, cod_materia):
        """Retorna o hash do diretório para um cod_materia (cached)"""
        if not hasattr(self, '_dir_hash_cache'):
            self._dir_hash_cache = {}
        cod_str = str(cod_materia)
        if cod_str not in self._dir_hash_cache:
            self._dir_hash_cache[cod_str] = get_processo_dir_hash(cod_materia)
        return self._dir_hash_cache[cod_str]

    def _get_proposicao_data(self, cod_materia):
        """Cache de proposição para evitar queries repetidas - SQLAlchemy"""
        if not hasattr(self, '_proposicao_cache'):
            self._proposicao_cache = {}
        cod_str = str(cod_materia)
        if cod_str not in self._proposicao_cache:
            session = self._get_session()
            try:
                proposta = session.query(Proposicao)\
                    .join(TipoProposicao, Proposicao.tip_proposicao == TipoProposicao.tip_proposicao)\
                    .filter(Proposicao.cod_mat_ou_doc == cod_materia)\
                    .filter(TipoProposicao.ind_mat_ou_doc == 'M')\
                    .first()
                self._proposicao_cache[cod_str] = proposta
            finally:
                session.close()
        return self._proposicao_cache[cod_str]

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

            # 2) Usa função utilitária para obter diretório do processo
            dir_base = get_processo_dir(cod_materia)
            
            # 3) Verifica se o diretório está dentro do temp_base (segurança)
            temp_base_abs = os.path.abspath(self.temp_base)
            dir_base_abs = os.path.abspath(dir_base)
            if not dir_base_abs.startswith(temp_base_abs + os.sep):
                raise SecurityError(f"Diretório do processo fora do temp_base permitido: {dir_base}")
            
            # 4) (Re)criar dir_base com permissão restrita
            if os.path.exists(dir_base):
                shutil.rmtree(dir_base, ignore_errors=True)
            os.makedirs(dir_base, mode=0o700, exist_ok=True)
            
            # 5) Secure-join para o subdiretório de páginas (já que dir_base existe)
            dir_paginas = secure_path_join(dir_base, 'pages')

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
        """Obtém informações básicas da matéria legislativa com validação - SQLAlchemy"""
        try:
            if not cod_materia or not str(cod_materia).isdigit():
                raise ValueError("Código da matéria inválido")

            session = self._get_session()
            try:
                result = session.query(MateriaLegislativa, TipoMateriaLegislativa)\
                    .join(TipoMateriaLegislativa, 
                          MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                    .filter(MateriaLegislativa.cod_materia == cod_materia)\
                    .filter(MateriaLegislativa.ind_excluido == 0)\
                    .first()
                
                if not result:
                    raise ValueError("Matéria não encontrada")
                
                materia_obj, tipo_obj = result
                
                # Converte data_apresentacao para string se for date/datetime
                data_apresentacao = _convert_to_datetime_string(materia_obj.dat_apresentacao)
                
                return {
                    'id': f"{tipo_obj.sgl_tipo_materia}-{materia_obj.num_ident_basica}-{materia_obj.ano_ident_basica}",
                    'id_exibicao': f"{tipo_obj.sgl_tipo_materia} {materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica}",
                    'tipo': tipo_obj.sgl_tipo_materia,
                    'numero': materia_obj.num_ident_basica,
                    'ano': materia_obj.ano_ident_basica,
                    'data_apresentacao': data_apresentacao,
                    'descricao': tipo_obj.des_tipo_materia,
                    'cod_materia': materia_obj.cod_materia
                }
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Erro ao obter dados da matéria: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha ao obter dados da matéria: {str(e)}")

    def coletar_documentos(self, dados_materia: Dict, dir_base: str) -> List[Dict]:
        """
        Coleta documentos relacionados à matéria
        
        Args:
            dados_materia: Dicionário com dados da matéria (retornado por obter_dados_materia)
            dir_base: Diretório base onde salvar arquivos
        """
        nome_camara = self.context.sapl_documentos.props_sagl.getProperty(
            'nom_casa', '(não definido)'
        )
        nome_sessao = self.context.sapl_documentos.props_sagl.getProperty(
            'reuniao_sessao', '(não definido)'
        )
        documentos = []
        total_size = 0

        try:
            # Capa do processo - usa método padrão do sistema e faz download via HTTP
            arquivo_capa = f"capa_{dados_materia['tipo']}-{dados_materia['numero']}-{dados_materia['ano']}.pdf"
            caminho_capa = secure_path_join(dir_base, arquivo_capa)
            # Converte data_apresentacao para string se necessário
            data_apresentacao_str = _convert_to_datetime_string(dados_materia['data_apresentacao'])
            data_capa = DateTime(data_apresentacao_str, datefmt='international').strftime('%Y-%m-%d 00:00:01')
            
            # OTIMIZAÇÃO: Chama _get_proposicao_data() uma vez e reutiliza
            proposta = self._get_proposicao_data(dados_materia['cod_materia'])
            
            # Gera a capa usando o método padrão do sistema (gera no temp_folder)
            # IMPORTANTE: modelo_proposicao está em /sagl/portal_skins/sk_sagl/modelo_proposicao
            # Precisa acessar através do caminho completo: portal_skins.sk_sagl.modelo_proposicao
            try:
                # Acessa modelo_proposicao através do caminho completo
                portal_skins = getattr(self.context, 'portal_skins', None)
                modelo_proposicao = None
                
                if portal_skins:
                    sk_sagl = getattr(portal_skins, 'sk_sagl', None)
                    if sk_sagl:
                        modelo_proposicao = getattr(sk_sagl, 'modelo_proposicao', None)
                
                # Se não encontrou pelo caminho completo, tenta acesso direto via Acquisition
                if modelo_proposicao is None:
                    modelo_proposicao = getattr(self.context, 'modelo_proposicao', None)
                
                if modelo_proposicao is not None:
                    modelo_proposicao.capa_processo(cod_materia=dados_materia['cod_materia'], action='gerar')
                else:
                    raise AttributeError("modelo_proposicao não encontrado")
                
                base_url = self.context.absolute_url()
                url = f"{base_url}/modelo_proposicao/capa_processo?cod_materia={dados_materia['cod_materia']}&action=download"
                
                import urllib.request
                import urllib.error
                
                # OTIMIZAÇÃO: Polling adaptativo com retry e backoff exponencial
                # Tenta fazer download com polling progressivo até a capa estar pronta
                max_retries = 5
                base_delay = 0.2  # Delay inicial reduzido para processos pequenos
                max_timeout = 120  # Timeout máximo de 2 minutos
                
                capa_data = None
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        # Delay progressivo: 0.2s, 0.4s, 0.8s, 1.6s, 3.2s
                        if attempt > 0:
                            delay = base_delay * (2 ** (attempt - 1))
                            time.sleep(delay)
                        
                        req = urllib.request.Request(url)
                        req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                        
                        # Timeout adaptativo: aumenta com tentativas
                        timeout = 15 + (attempt * 15)  # 15s, 30s, 45s, 60s, 75s
                        timeout = min(timeout, max_timeout)
                        
                        with urllib.request.urlopen(req, timeout=timeout) as response:
                            capa_data = response.read()
                        
                        if capa_data and len(capa_data) > 0:
                            # Sucesso - salva no filesystem
                            with open(caminho_capa, 'wb') as f:
                                f.write(capa_data)
                            break
                        else:
                            last_error = "Download da capa retornou dados vazios"
                            
                    except urllib.error.HTTPError as http_err:
                        if http_err.code == 404:
                            # 404 significa que a capa ainda não está pronta, tenta novamente
                            if attempt < max_retries - 1:
                                last_error = f"Capa do processo não encontrada (404): {url}"
                                continue
                            else:
                                raise PDFGenerationError(f"Capa do processo não encontrada após {max_retries} tentativas (404): {url}")
                        elif http_err.code >= 500:
                            # Erros 5xx são retentáveis
                            if attempt < max_retries - 1:
                                last_error = f"Erro HTTP {http_err.code} - {http_err.reason}"
                                continue
                            else:
                                raise PDFGenerationError(f"Erro HTTP {http_err.code} ao baixar capa após {max_retries} tentativas: {http_err.reason}")
                        else:
                            # Outros erros HTTP não são retentáveis
                            raise PDFGenerationError(f"Erro HTTP {http_err.code} ao baixar capa: {http_err.reason}")
                            
                    except urllib.error.URLError as url_err:
                        if attempt < max_retries - 1:
                            last_error = f"Erro de URL: {url_err}"
                            continue
                        else:
                            raise PDFGenerationError(f"Erro ao baixar capa via HTTP após {max_retries} tentativas: {url_err}")
                            
                    except Exception as e:
                        error_str = str(e).lower()
                        if 'timeout' in error_str or 'timed out' in error_str:
                            if attempt < max_retries - 1:
                                last_error = f"Timeout ao baixar capa: {e}"
                                continue
                            else:
                                raise PDFGenerationError(f"Timeout ao baixar capa após {max_retries} tentativas: {e}")
                        else:
                            # Outros erros não são retentáveis
                            raise PDFGenerationError(f"Erro ao baixar capa via HTTP: {str(e)}")
                
                # Se chegou aqui sem sucesso, lança erro
                if not capa_data or len(capa_data) == 0:
                    raise PDFGenerationError(f"Falha ao baixar capa após {max_retries} tentativas: {last_error or 'Erro desconhecido'}")
                    
            except Exception as e:
                logger.error(f"[coletar_documentos] Erro ao gerar/baixar capa do processo: {str(e)}", exc_info=True)
                raise PDFGenerationError(f"Falha ao gerar/baixar capa do processo: {str(e)}")

            # Usa proposta já obtida para obter data
            if proposta and proposta.dat_recebimento:
                data_str = _convert_to_datetime_string(proposta.dat_recebimento)
                data_capa = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d 00:00:01')
            else:
                data_str = _convert_to_datetime_string(dados_materia['data_apresentacao'])
                data_capa = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d 00:00:01')

            documentos.append({
                "data": data_capa,
                "path": dir_base,
                "file": arquivo_capa,
                "title": "Capa do Processo",
                "filesystem": True
            })

            # OTIMIZAÇÃO: Coleta todos os nomes de arquivos para verificação em batch
            arquivos_para_verificar = []
            arquivos_info = {}  # Armazena informações sobre cada arquivo

            # Texto integral da matéria
            arquivo_texto = f"{dados_materia['cod_materia']}_texto_integral.pdf"
            if proposta and proposta.dat_recebimento:
                data_str = _convert_to_datetime_string(proposta.dat_recebimento)
                data_texto = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d 00:00:02')
            else:
                data_str = _convert_to_datetime_string(dados_materia['data_apresentacao'])
                data_texto = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d 00:00:02')
            
            arquivos_para_verificar.append(arquivo_texto)
            arquivos_info[arquivo_texto] = {
                "data": data_texto,
                "path": self.context.sapl_documentos.materia,
                "title": f"{dados_materia['descricao']} nº {dados_materia['numero']}/{dados_materia['ano']}"
            }

            # Redação Final
            nom_redacao = f"{dados_materia['cod_materia']}_redacao_final.pdf"
            arquivos_para_verificar.append(nom_redacao)
            if proposta and proposta.dat_recebimento:
                data_str = _convert_to_datetime_string(proposta.dat_recebimento)
                data_redacao = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
            else:
                data_str = _convert_to_datetime_string(dados_materia['data_apresentacao'])
                data_redacao = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d 00:00:03')
            
            arquivos_info[nom_redacao] = {
                "data": data_redacao,
                "path": self.context.sapl_documentos.materia,
                "title": "Redação Final"
            }

            # Fichas de votação - geradas no filesystem da pasta digital para uso pelo celery
            # OTIMIZAÇÃO: Paralelização da geração de fichas de votação
            votacoes = self.context.pysc.votacao_obter_pysc(cod_materia=dados_materia['cod_materia'])
            
            # Filtra votações válidas primeiro (antes de paralelizar)
            votacoes_validas = []
            for i, votacao in enumerate(votacoes):
                fase = votacao.get('fase', '')
                if fase == "Expediente - Leitura de Matérias":
                    continue

                # Verifica se é "Leitura" ou resultado "Lido em Plenário" - não adiciona na pasta digital
                turno = votacao.get('txt_turno', '')
                resultado = votacao.get('txt_resultado', '')
                tipo_votacao = votacao.get('txt_tipo_votacao', '')
                
                # Filtra votações de leitura ou com resultado "Lido em Plenário"
                if (turno and 'leitura' in turno.lower()) or \
                   (resultado and 'lido em plenário' in resultado.lower()) or \
                   (tipo_votacao and 'leitura' in tipo_votacao.lower()):
                    continue
                
                votacoes_validas.append((i, votacao))
            
            # OTIMIZAÇÃO: Worker para geração paralela de fichas de votação
            def gerar_ficha_worker(votacao_data):
                """Worker para gerar uma ficha de votação"""
                i, votacao = votacao_data
                try:
                    nome_arquivo = f'ficha_votacao_{i + 1}.pdf'
                    caminho_arquivo = secure_path_join(dir_base, nome_arquivo)
                    
                    # Gera a ficha de votação diretamente no filesystem
                    gerar_ficha_votacao_pdf(
                        votacao, caminho_arquivo, nome_camara, nome_sessao, self.context)
                    
                    # Valida que o arquivo foi gerado corretamente
                    if not os.path.exists(caminho_arquivo):
                        logger.warning(f"[coletar_documentos] Ficha de votação não foi gerada: {caminho_arquivo}")
                        return None
                    
                    # Verifica que o arquivo não está vazio
                    if os.path.getsize(caminho_arquivo) == 0:
                        logger.warning(f"[coletar_documentos] Ficha de votação está vazia: {caminho_arquivo}")
                        return None
                    
                    # Valida o conteúdo do PDF
                    with open(caminho_arquivo, 'rb') as f:
                        pdf_bytes = f.read()
                    validate_pdf_content(pdf_bytes)
                    
                    # Prepara dados do documento
                    raw_date = votacao.get('dat_sessao', '')
                    try:
                        date_obj = raw_date if isinstance(raw_date, DateTime) else DateTime(raw_date, datefmt='international')
                        date_str = date_obj.strftime('%Y-%m-%d')
                    except Exception:
                        date_str = str(raw_date)[:10]
                    hora_str = votacao.get('hora_sessao', '00:00:00')
                    data_votacao = f"{date_str} {hora_str}"
                    turno = votacao.get('txt_turno', '')
                    
                    return {
                        "data": data_votacao,
                        "file": nome_arquivo,
                        "title": f"Registro de Votação ({turno})",
                        "path": dir_base,
                        "filesystem": True,
                        "file_size": len(pdf_bytes)
                    }
                except Exception as e:
                    logger.warning(f"[coletar_documentos] Erro ao gerar ficha de votação {i + 1}: {e}")
                    return None
            
            # OTIMIZAÇÃO: Paraleliza geração de fichas usando ThreadPoolExecutor (compatível com Zope)
            if votacoes_validas:
                # Limita workers para evitar sobrecarga (2-3 workers é suficiente para geração de PDF)
                max_ficha_workers = min(3, len(votacoes_validas))
                with ThreadPoolExecutor(max_workers=max_ficha_workers) as executor:
                    futures = {executor.submit(gerar_ficha_worker, vot_data): vot_data 
                              for vot_data in votacoes_validas}
                    
                    for future in futures:
                        try:
                            doc_ficha = future.result(timeout=120)  # Timeout de 2min por ficha
                            if doc_ficha:
                                documentos.append(doc_ficha)
                        except Exception as e:
                            vot_data = futures[future]
                            logger.warning(f"[coletar_documentos] Erro ao processar ficha de votação {vot_data[0] + 1}: {e}")

            # OTIMIZAÇÃO: Usar uma única sessão SQLAlchemy para todas as queries
            session = self._get_session()
            try:
                # Emendas - SQLAlchemy
                emendas = session.query(Emenda, TipoEmenda, Proposicao)\
                    .join(TipoEmenda, Emenda.tip_emenda == TipoEmenda.tip_emenda)\
                    .outerjoin(Proposicao, Proposicao.cod_emenda == Emenda.cod_emenda)\
                    .filter(Emenda.cod_materia == dados_materia['cod_materia'])\
                    .filter(Emenda.ind_excluido == 0)\
                    .all()
                
                for emenda_obj, tipo_emenda_obj, proposta_obj in emendas:
                    arquivo_emenda = f"{emenda_obj.cod_emenda}_emenda.pdf"
                    # Usar data de proposta se existir, senão data de apresentação
                    if proposta_obj and proposta_obj.dat_recebimento:
                        data_str = _convert_to_datetime_string(proposta_obj.dat_recebimento)
                        data_emenda = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        data_str = _convert_to_datetime_string(emenda_obj.dat_apresentacao)
                        data_emenda = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

                    # Emendas não precisam verificação de arquivo (sempre adiciona)
                    documentos.append({
                        "data": data_emenda,
                        "path": self.context.sapl_documentos.emenda,
                        "file": arquivo_emenda,
                        "title": f"Emenda {tipo_emenda_obj.des_tipo_emenda} nº {emenda_obj.num_emenda}"
                    })

                # Substitutivos - SQLAlchemy
                substitutivos = session.query(Substitutivo, Proposicao)\
                    .outerjoin(Proposicao, Proposicao.cod_substitutivo == Substitutivo.cod_substitutivo)\
                    .filter(Substitutivo.cod_materia == dados_materia['cod_materia'])\
                    .filter(Substitutivo.ind_excluido == 0)\
                    .all()
                
                for subst_obj, proposta_obj in substitutivos:
                    arquivo_substitutivo = f"{subst_obj.cod_substitutivo}_substitutivo.pdf"
                    arquivos_para_verificar.append(arquivo_substitutivo)
                    # Usar data de proposta se existir, senão data de apresentação
                    if proposta_obj and proposta_obj.dat_recebimento:
                        data_str = _convert_to_datetime_string(proposta_obj.dat_recebimento)
                        data_sub = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        data_str = _convert_to_datetime_string(subst_obj.dat_apresentacao)
                        data_sub = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                    
                    arquivos_info[arquivo_substitutivo] = {
                        "data": data_sub,
                        "path": self.context.sapl_documentos.substitutivo,
                        "title": f"Substitutivo nº {subst_obj.num_substitutivo}"
                    }

                # Relatorias/Pareceres - SQLAlchemy (com JOIN para comissão)
                relatorias = session.query(Relatoria, Comissao, Proposicao)\
                    .join(Comissao, Relatoria.cod_comissao == Comissao.cod_comissao)\
                    .outerjoin(Proposicao, Proposicao.cod_parecer == Relatoria.cod_relatoria)\
                    .filter(Relatoria.cod_materia == dados_materia['cod_materia'])\
                    .filter(Relatoria.ind_excluido == 0)\
                    .filter(Comissao.ind_excluido == 0)\
                    .all()
                
                for relat_obj, comissao_obj, proposta_obj in relatorias:
                    arquivo_parecer = f"{relat_obj.cod_relatoria}_parecer.pdf"
                    arquivos_para_verificar.append(arquivo_parecer)
                    # Usar data de proposta se existir, senão data de destituição do relator
                    if proposta_obj and proposta_obj.dat_recebimento:
                        data_str = _convert_to_datetime_string(proposta_obj.dat_recebimento)
                        data_parecer = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        data_str = _convert_to_datetime_string(relat_obj.dat_destit_relator)
                        data_parecer = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                    
                    arquivos_info[arquivo_parecer] = {
                        "data": data_parecer,
                        "path": self.context.sapl_documentos.parecer_comissao,
                        "title": (
                            f"Parecer {comissao_obj.sgl_comissao} nº "
                            f"{relat_obj.num_parecer}/{relat_obj.ano_parecer}"
                        )
                    }

                # Matérias Anexadas - SQLAlchemy (com JOIN para obter tipo/numero/ano)
                anexadas = session.query(Anexada, MateriaLegislativa, TipoMateriaLegislativa)\
                    .join(MateriaLegislativa, Anexada.cod_materia_anexada == MateriaLegislativa.cod_materia)\
                    .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                    .filter(Anexada.cod_materia_principal == dados_materia['cod_materia'])\
                    .filter(Anexada.ind_excluido == 0)\
                    .all()
                
                # OTIMIZAÇÃO: Coleta códigos de matérias anexadas para query batch de documentos acessórios
                cod_materias_anexadas = [anexada_obj.cod_materia_anexada for anexada_obj, _, _ in anexadas]
                
                # OTIMIZAÇÃO: Query batch de documentos acessórios das matérias anexadas (antes do loop)
                docs_anexadas_batch = {}
                if cod_materias_anexadas:
                    docs_anexadas_all = session.query(DocumentoAcessorio, Proposicao)\
                        .outerjoin(Proposicao, Proposicao.cod_mat_ou_doc == DocumentoAcessorio.cod_documento)\
                        .outerjoin(TipoProposicao, Proposicao.tip_proposicao == TipoProposicao.tip_proposicao)\
                        .filter(or_(Proposicao.cod_proposicao.is_(None), TipoProposicao.ind_mat_ou_doc == 'D'))\
                        .filter(DocumentoAcessorio.cod_materia.in_(cod_materias_anexadas))\
                        .filter(DocumentoAcessorio.ind_excluido == 0)\
                        .all()
                    
                    # Agrupa por cod_materia
                    for doc_obj, proposta_obj in docs_anexadas_all:
                        cod_mat = doc_obj.cod_materia
                        if cod_mat not in docs_anexadas_batch:
                            docs_anexadas_batch[cod_mat] = []
                        docs_anexadas_batch[cod_mat].append((doc_obj, proposta_obj))
                
                for anexada_obj, materia_obj, tipo_obj in anexadas:
                    arquivo_anexada = f"{anexada_obj.cod_materia_anexada}_texto_integral.pdf"
                    arquivos_para_verificar.append(arquivo_anexada)
                    data_anex_str = _convert_to_datetime_string(anexada_obj.dat_anexacao)
                    arquivos_info[arquivo_anexada] = {
                        "data": DateTime(data_anex_str, datefmt='international').strftime('%Y-%m-%d 23:58:00'),
                        "path": self.context.sapl_documentos.materia,
                        "title": (
                            f"{tipo_obj.sgl_tipo_materia} "
                            f"{materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica} "
                            "(anexada)"
                        )
                    }

                    # Documentos acessórios das matérias anexadas (usando batch)
                    docs_anexada = docs_anexadas_batch.get(anexada_obj.cod_materia_anexada, [])
                    for doc_obj, proposta_obj in docs_anexada:
                        arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                        arquivos_para_verificar.append(arquivo_acessorio)
                        # Usar data de proposta se existir, senão data do documento
                        if proposta_obj and proposta_obj.dat_recebimento:
                            data_str = _convert_to_datetime_string(proposta_obj.dat_recebimento)
                            data_doc = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            data_str = _convert_to_datetime_string(doc_obj.dat_documento)
                            data_doc = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        
                        arquivos_info[arquivo_acessorio] = {
                            "data": data_doc,
                            "path": self.context.sapl_documentos.materia,
                            "title": f"{doc_obj.nom_documento} (acess. de anexada)"
                        }

                # Matérias Anexadoras - SQLAlchemy (com JOIN para obter tipo/numero/ano)
                anexadoras = session.query(Anexada, MateriaLegislativa, TipoMateriaLegislativa)\
                    .join(MateriaLegislativa, Anexada.cod_materia_principal == MateriaLegislativa.cod_materia)\
                    .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                    .filter(Anexada.cod_materia_anexada == dados_materia['cod_materia'])\
                    .filter(Anexada.ind_excluido == 0)\
                    .all()
                
                # OTIMIZAÇÃO: Coleta códigos de matérias anexadoras para query batch
                cod_materias_anexadoras = [anexada_obj.cod_materia_principal for anexada_obj, _, _ in anexadoras]
                
                # OTIMIZAÇÃO: Query batch de documentos acessórios das matérias anexadoras
                docs_anexadoras_batch = {}
                if cod_materias_anexadoras:
                    docs_anexadoras_all = session.query(DocumentoAcessorio, Proposicao)\
                        .outerjoin(Proposicao, Proposicao.cod_mat_ou_doc == DocumentoAcessorio.cod_documento)\
                        .outerjoin(TipoProposicao, Proposicao.tip_proposicao == TipoProposicao.tip_proposicao)\
                        .filter(or_(Proposicao.cod_proposicao.is_(None), TipoProposicao.ind_mat_ou_doc == 'D'))\
                        .filter(DocumentoAcessorio.cod_materia.in_(cod_materias_anexadoras))\
                        .filter(DocumentoAcessorio.ind_excluido == 0)\
                        .all()
                    
                    # Agrupa por cod_materia
                    for doc_obj, proposta_obj in docs_anexadoras_all:
                        cod_mat = doc_obj.cod_materia
                        if cod_mat not in docs_anexadoras_batch:
                            docs_anexadoras_batch[cod_mat] = []
                        docs_anexadoras_batch[cod_mat].append((doc_obj, proposta_obj))
                
                for anexada_obj, materia_obj, tipo_obj in anexadoras:
                    arquivo_anexadora = f"{anexada_obj.cod_materia_principal}_texto_integral.pdf"
                    arquivos_para_verificar.append(arquivo_anexadora)
                    data_anex_str = _convert_to_datetime_string(anexada_obj.dat_anexacao)
                    arquivos_info[arquivo_anexadora] = {
                        "data": DateTime(data_anex_str, datefmt='international').strftime('%Y-%m-%d 23:58:00'),
                        "path": self.context.sapl_documentos.materia,
                        "title": (
                            f"{tipo_obj.sgl_tipo_materia} "
                            f"{materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica} "
                            "(anexadora)"
                        )
                    }

                    # Documentos acessórios das matérias anexadoras (usando batch)
                    docs_anexadora = docs_anexadoras_batch.get(anexada_obj.cod_materia_principal, [])
                    for doc_obj, proposta_obj in docs_anexadora:
                        arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                        arquivos_para_verificar.append(arquivo_acessorio)
                        # Usar data de proposta se existir, senão data do documento
                        if proposta_obj and proposta_obj.dat_recebimento:
                            data_str = _convert_to_datetime_string(proposta_obj.dat_recebimento)
                            data_doc = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            data_str = _convert_to_datetime_string(doc_obj.dat_documento)
                            data_doc = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        
                        arquivos_info[arquivo_acessorio] = {
                            "data": data_doc,
                            "path": self.context.sapl_documentos.materia,
                            "title": f"{doc_obj.nom_documento} (acess. de anexadora)"
                        }

                # Documentos Acessórios da Matéria Principal - SQLAlchemy
                documentos_acessorios = session.query(DocumentoAcessorio, Proposicao)\
                    .outerjoin(Proposicao, Proposicao.cod_mat_ou_doc == DocumentoAcessorio.cod_documento)\
                    .outerjoin(TipoProposicao, Proposicao.tip_proposicao == TipoProposicao.tip_proposicao)\
                    .filter(or_(Proposicao.cod_proposicao == None, TipoProposicao.ind_mat_ou_doc == 'D'))\
                    .filter(DocumentoAcessorio.cod_materia == dados_materia['cod_materia'])\
                    .filter(DocumentoAcessorio.ind_excluido == 0)\
                    .all()
                
                for doc_obj, proposta_obj in documentos_acessorios:
                    arquivo_acessorio = f"{doc_obj.cod_documento}.pdf"
                    arquivos_para_verificar.append(arquivo_acessorio)
                    # Usar data de proposta se existir, senão data do documento
                    if proposta_obj and proposta_obj.dat_recebimento:
                        data_str = _convert_to_datetime_string(proposta_obj.dat_recebimento)
                        data_doc = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        data_str = _convert_to_datetime_string(doc_obj.dat_documento)
                        data_doc = DateTime(data_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                    
                    arquivos_info[arquivo_acessorio] = {
                        "data": data_doc,
                        "path": self.context.sapl_documentos.materia,
                        "title": doc_obj.nom_documento
                    }

                # Tramitações - SQLAlchemy (com JOIN para status)
                # Exclui rascunhos: inclui apenas se ind_ult_tramitacao == 1 OU dat_encaminha IS NOT NULL
                # Rascunho = ind_ult_tramitacao == 0 E dat_encaminha IS NULL
                tramitacoes = session.query(Tramitacao, StatusTramitacao)\
                    .join(StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status)\
                    .filter(Tramitacao.cod_materia == dados_materia['cod_materia'])\
                    .filter(Tramitacao.ind_excluido == 0)\
                    .filter(or_(Tramitacao.ind_ult_tramitacao == 1, Tramitacao.dat_encaminha.isnot(None)))\
                    .order_by(Tramitacao.dat_tramitacao, Tramitacao.cod_tramitacao)\
                    .all()
                
                for tram_obj, status_obj in tramitacoes:
                    arquivo_tram = f"{tram_obj.cod_tramitacao}_tram.pdf"
                    arquivos_para_verificar.append(arquivo_tram)
                    data_tram_str = _convert_to_datetime_string(tram_obj.dat_tramitacao)
                    arquivos_info[arquivo_tram] = {
                        "data": DateTime(data_tram_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                        "path": self.context.sapl_documentos.materia.tramitacao,
                        "title": f"Tramitação ({status_obj.des_status})"
                    }

                # Normas Jurídicas Relacionadas - SQLAlchemy (com JOIN para tipo)
                normas = session.query(NormaJuridica, TipoNormaJuridica)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(NormaJuridica.cod_materia == dados_materia['cod_materia'])\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                for norma_obj, tipo_norma_obj in normas:
                    arquivo_norma = f"{norma_obj.cod_norma}_texto_integral.pdf"
                    arquivos_para_verificar.append(arquivo_norma)
                    data_norma_str = _convert_to_datetime_string(norma_obj.dat_norma)
                    arquivos_info[arquivo_norma] = {
                        "data": DateTime(data_norma_str, datefmt='international').strftime('%Y-%m-%d 23:59:00'),
                        "path": self.context.sapl_documentos.norma_juridica,
                        "title": f"{tipo_norma_obj.sgl_tipo_norma} nº {norma_obj.num_norma}/{norma_obj.ano_norma}"
                    }
                
                # OTIMIZAÇÃO: Verifica todos os arquivos em batch por container
                # Agrupa arquivos por container
                arquivos_por_container = {}
                for arquivo in arquivos_para_verificar:
                    info = arquivos_info.get(arquivo, {})
                    container = info.get('path')
                    if container:
                        if container not in arquivos_por_container:
                            arquivos_por_container[container] = []
                        arquivos_por_container[container].append(arquivo)
                
                # Verifica arquivos em batch por container
                arquivos_existentes = set()
                for container, arquivos_list in arquivos_por_container.items():
                    resultados = safe_check_files_batch(container, arquivos_list)
                    arquivos_existentes.update(arquivo for arquivo, existe in resultados.items() if existe)
                
                # Adiciona documentos que existem
                for arquivo in arquivos_para_verificar:
                    if arquivo in arquivos_existentes:
                        info = arquivos_info[arquivo]
                        documentos.append({
                            "data": info["data"],
                            "path": info["path"],
                            "file": arquivo,
                            "title": info["title"],
                            "filesystem": False  # Precisa ser baixado via HTTP
                        })
                        
            except Exception as e:
                logger.warning(f"Erro ao coletar dados do banco: {str(e)}", exc_info=True)
            finally:
                session.close()

            # Ordenar documentos: Capa sempre primeira, Texto integral sempre segundo, 
            # Redação final sempre terceira (se houver), resto por data
            # CRÍTICO: Apenas o texto integral e redação final do próprio processo (com cod_materia) devem ser priorizados
            # Não priorizar textos integrais ou redações finais de matérias vinculadas
            cod_materia = dados_materia.get('cod_materia')
            
            def ordenar_documentos(doc):
                title = doc.get('title', '').lower()
                file = doc.get('file', '').lower() if doc.get('file') else ''
                
                # Capa do Processo sempre primeira (prioridade 0) - verifica título
                if 'capa do processo' in title or 'capa' in title:
                    return (0, doc.get('data', ''))
                
                # Texto integral do próprio processo sempre segundo (prioridade 1) - verifica nome do arquivo
                # Nome do arquivo: {cod_materia}_texto_integral.pdf (ex: 79431_texto_integral.pdf)
                if file and cod_materia:
                    # Verifica se o arquivo é exatamente {cod_materia}_texto_integral.pdf do próprio processo
                    texto_integral_esperado = f"{cod_materia}_texto_integral.pdf"
                    if file == texto_integral_esperado.lower() or file.endswith(f"{cod_materia}_texto_integral.pdf"):
                        return (1, doc.get('data', ''))
                
                # Redação final do próprio processo sempre terceira (prioridade 2) - verifica nome do arquivo
                # Nome do arquivo: {cod_materia}_redacao_final.pdf (ex: 79431_redacao_final.pdf)
                if file and cod_materia:
                    # Verifica se o arquivo é exatamente {cod_materia}_redacao_final.pdf do próprio processo
                    redacao_final_esperada = f"{cod_materia}_redacao_final.pdf"
                    if file == redacao_final_esperada.lower() or file.endswith(f"{cod_materia}_redacao_final.pdf"):
                        return (2, doc.get('data', ''))
                
                # Resto ordenado por data (prioridade 3)
                return (3, doc.get('data', ''))
            
            documentos.sort(key=ordenar_documentos)
            return documentos

        except Exception as e:
            logger.error(f"Erro ao coletar documentos: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha na coleta de documentos: {str(e)}")

    def _safe_has_file(self, container, filename: str) -> bool:
        """
        Verifica se um arquivo existe no container sem carregar o objeto do ZODB.
        Usa apenas objectIds() para verificar existência - não acessa dados do ZODB.
        A verificação real será feita via download HTTP.
        
        Usa função utilitária compartilhada.
        """
        return safe_check_file(container, filename)

    @timeit
    def render(self):
        """
        Método render - APENAS para verificação de documentos prontos (com skip_signature_check).
        
        Geração síncrona de PDF foi removida. Use sempre o modo assíncrono (Celery task).
        """
        try:
            if not self.cod_materia:
                raise ValueError("O parâmetro cod_materia é obrigatório")

            # CRÍTICO: Se action é 'download', faz download do PDF final
            if self.action == 'download':
                try:
                    # Obtém dados da matéria para construir o nome do arquivo
                    dados_materia = self.obter_dados_materia(self.cod_materia)
                    
                    # Constrói o nome do arquivo baseado nos dados da matéria: PL_274_2025.pdf
                    nome_arquivo_download = f"{dados_materia['tipo']}_{dados_materia['numero']}_{dados_materia['ano']}.pdf"
                    
                    # Verifica se há PDF final gerado (o arquivo no sistema ainda usa o nome antigo)
                    dir_base = get_processo_dir(self.cod_materia)
                    nome_arquivo_final = f"processo_leg_integral_{self.cod_materia}.pdf"
                    caminho_arquivo_final = os.path.join(dir_base, nome_arquivo_final)
                    
                    if os.path.exists(caminho_arquivo_final):
                        # Lê o arquivo e retorna como download
                        with open(caminho_arquivo_final, 'rb') as f:
                            pdf_data = f.read()
                        
                        # Configura headers para abrir PDF em nova aba (inline ao invés de attachment)
                        # Usa o nome formatado baseado nos dados da matéria
                        self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
                        self.request.RESPONSE.setHeader(
                            'Content-Disposition',
                            f'inline; filename="{nome_arquivo_download}"'
                        )
                        self.request.RESPONSE.setHeader('Content-Length', str(len(pdf_data)))
                        
                        return pdf_data
                    else:
                        # Arquivo não encontrado
                        error_msg = f"Arquivo não encontrado: {nome_arquivo_download}. O processo ainda não foi gerado."
                        logger.warning(f"[ProcessoLegView] Arquivo não encontrado para download: {caminho_arquivo_final}")
                        self.request.RESPONSE.setStatus(404)
                        self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
                        return error_msg
                        
                except Exception as download_err:
                    logger.error(f"[ProcessoLegView] Erro ao fazer download: {download_err}", exc_info=True)
                    self.request.RESPONSE.setStatus(500)
                    self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
                    return f"Erro ao fazer download: {str(download_err)}"

            # CRÍTICO: Esta view APENAS verifica documentos prontos quando skip_signature_check está presente
            # Geração síncrona foi removida - sempre use o modo assíncrono (Celery task)
            skip_signature_check = self.request.form.get('skip_signature_check') == '1'
            
            if not skip_signature_check:
                # Modo síncrono não é mais suportado
                error_msg = "Geração síncrona de PDF não é mais suportada. Use sempre o modo assíncrono (Celery task)."
                logger.warning(f"[ProcessoLegView] Tentativa de geração síncrona rejeitada para cod_materia={self.cod_materia}")
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'error': error_msg,
                    'success': False,
                    'cod_materia': self.cod_materia
                })
            
            # Apenas verifica documentos prontos (não gera novos)
            try:
                # Verifica se há documentos prontos sem regenerar
                dados_materia = self.obter_dados_materia(self.cod_materia)
                dir_base = get_processo_dir(self.cod_materia)
                
                # CRÍTICO: Verifica se o diretório base existe antes de tentar acessar subdiretórios
                if not os.path.exists(dir_base):
                    result = {
                        'documentos': [],
                        'total_paginas': 0,
                        'cod_materia': self.cod_materia
                    }
                    if self.action == 'json':
                        self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                        return json.dumps(result)
                    return result
                
                dir_paginas = secure_path_join(dir_base, 'pages')
                metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                
                # Se há metadados e páginas, carrega documentos prontos
                # CRÍTICO: Se skip_signature_check está presente, adiciona um pequeno delay
                # para garantir que os arquivos foram completamente salvos no disco
                # IMPORTANTE: Aguarda ANTES da primeira verificação para evitar race conditions
                if skip_signature_check:
                    import time
                    time.sleep(0.5)
                
                # Verifica estado inicial
                metadados_existe = os.path.exists(metadados_path)
                dir_paginas_existe = os.path.exists(dir_paginas)
                
                # CRÍTICO: Se dir_paginas existe mas metadados_path não, pode ser race condition
                # Se skip_signature_check=True, pode haver uma task em execução, então usa mais tentativas e delay progressivo
                if dir_paginas_existe and not metadados_existe:
                    import time
                    if skip_signature_check:
                        # Task pode estar em execução - usa mais tentativas com delay progressivo
                        # Para processos grandes, pode levar 20-30 segundos para gerar metadados
                        max_retries = 10
                        base_delay = 0.5
                    else:
                        # Verificação normal - menos tentativas
                        max_retries = 3
                        base_delay = 0.5
                    
                    for retry in range(max_retries):
                        # Delay progressivo: 0.5s, 1s, 1.5s, 2s, 2.5s, 3s, 3.5s, 4s, 4.5s, 5s...
                        # Total máximo: ~27.5 segundos para processos grandes
                        retry_delay = base_delay * (retry + 1)
                        time.sleep(retry_delay)
                        metadados_existe = os.path.exists(metadados_path)
                        if metadados_existe:
                            break
                
                if metadados_existe and dir_paginas_existe:
                    with open(metadados_path, 'r', encoding='utf-8') as f:
                        metadados = json.load(f)
                    
                    # Verifica se há páginas geradas (lista arquivos PDF na pasta pages)
                    pdf_files = [f for f in os.listdir(dir_paginas) if f.endswith('.pdf') and f.startswith('pg_')]
                    
                    if pdf_files and len(pdf_files) > 0:
                        # Reconstrói estrutura de documentos a partir dos metadados
                        base_url = f"{self.context.absolute_url()}/@@pagina_processo_leg_integral"
                        documentos_formatados = []
                        
                        # Gera cache-busting baseado no timestamp de modificação do arquivo de metadados
                        # Isso força o navegador a buscar arquivos atualizados
                        try:
                            cache_bust_ts = int(os.path.getmtime(metadados_path))
                        except (OSError, ValueError):
                            # Fallback: usa timestamp atual se não conseguir obter mtime
                            cache_bust_ts = int(time.time())
                        cache_bust_param = f"&_t={cache_bust_ts}"
                        
                        # Usa documentos dos metadados se disponível, senão constrói a partir das páginas
                        if 'documentos' in metadados and len(metadados['documentos']) > 0:
                            for i, doc_meta in enumerate(metadados['documentos'], 1):
                                doc_id = f"{i:04d}.pdf"
                                start_page = doc_meta.get('start_page', 1)
                                end_page = doc_meta.get('end_page', 1)
                                first_id = f"pg_{start_page:04d}.pdf"
                                
                                # Reconstrói lista de páginas
                                paginas = []
                                for page_num in range(start_page, end_page + 1):
                                    pg_id = f"pg_{page_num:04d}.pdf"
                                    if os.path.exists(os.path.join(dir_paginas, pg_id)):
                                        paginas.append({
                                            'num_pagina': str(page_num),
                                            'id_pagina': pg_id,
                                            'url': f"{base_url}?cod_materia={self.cod_materia}&pagina={pg_id}{cache_bust_param}"
                                        })
                                
                                if paginas:
                                    documentos_formatados.append({
                                        'id': doc_id,
                                        'title': doc_meta.get('title', ''),
                                        'data': doc_meta.get('data', ''),
                                        'url': f"{base_url}?cod_materia={self.cod_materia}&pagina={first_id}{cache_bust_param}",
                                        'paginas_geral': metadados.get('total_paginas', 0),
                                        'paginas': paginas,
                                        'id_paginas': [p['id_pagina'] for p in paginas],
                                        'paginas_doc': len(paginas)
                                    })
            
                        # Se encontrou documentos formatados, retorna eles
                        if documentos_formatados:
                            result = {
                                'documentos': documentos_formatados,
                                'total_paginas': metadados.get('total_paginas', 0),
                                'id_processo': metadados.get('id_processo', ''),
                                'cod_materia': self.cod_materia
                            }
                            
                            # Se action é json, retorna JSON
                            if self.action == 'json':
                                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                                return json.dumps(result)
                            return result
                        else:
                            logger.warning(f"[ProcessoLegView] Nenhum documento formatado encontrado apesar de haver {len(pdf_files)} arquivos PDF")
                
                # Se não encontrou documentos prontos, retorna estrutura vazia
                logger.warning(f"[ProcessoLegView] Documentos prontos não encontrados: metadados_path existe={os.path.exists(metadados_path) if 'metadados_path' in locals() else 'N/A'}, dir_paginas existe={os.path.exists(dir_paginas) if 'dir_paginas' in locals() else 'N/A'}")
                
                # Se não encontrou documentos prontos, retorna estrutura vazia
                result = {
                    'documentos': [],
                    'total_paginas': 0,
                    'cod_materia': self.cod_materia
                }
                
                if self.action == 'json':
                    self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                    return json.dumps(result)
                return result
                
            except Exception as check_err:
                logger.error(f"[ProcessoLegView] Erro ao verificar documentos prontos: {check_err}", exc_info=True)
                self.request.RESPONSE.setStatus(500)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'error': f"Erro ao verificar documentos prontos: {str(check_err)}",
                    'success': False,
                    'cod_materia': self.cod_materia
                })

        except ValueError as ve:
            logger.error(f"Erro de validação: {str(ve)}")
            self.request.RESPONSE.setStatus(400)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({'error': str(ve), 'success': False})
        except Exception as e:
            logger.error(f"Erro no render: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({'error': str(e), 'success': False})

class PaginaProcessoLeg(grok.View):
    """Visualização para páginas individuais do processo"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_leg_integral')

    @property
    def temp_base(self) -> str:
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        return secure_path_join(install_home, 'var/tmp')

    def render(self):
        """Renderiza uma página individual do processo"""
        # Obtém parâmetros do request
        # Em Zope/Grok, os parâmetros de query string estão em request.form
        try:
            cod_materia = self.request.form.get('cod_materia', '')
            pagina = self.request.form.get('pagina', '')
        except (AttributeError, KeyError):
            # Fallback: tenta acessar diretamente
            try:
                cod_materia = getattr(self.request, 'cod_materia', '')
                pagina = getattr(self.request, 'pagina', '')
            except AttributeError:
                cod_materia = ''
                pagina = ''
        
        # Remove espaços e converte para string
        if cod_materia:
            cod_materia = str(cod_materia).strip()
        if pagina:
            pagina = str(pagina).strip()
        
        if not cod_materia:
            logger.error("[PaginaProcessoLeg] cod_materia não fornecido")
            self.request.RESPONSE.setStatus(400)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return "Parâmetro cod_materia é obrigatório"
        
        if not pagina:
            logger.error("[PaginaProcessoLeg] pagina não fornecida")
            self.request.RESPONSE.setStatus(400)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return "Parâmetro pagina é obrigatório"
        
        file_path = None
        try:
            dir_base = get_processo_dir(cod_materia)
            dir_pages = secure_path_join(dir_base, 'pages')
            file_path = secure_path_join(dir_pages, pagina)
            
            with open(file_path, 'rb') as f:
                data = f.read()
            self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
            self.request.RESPONSE.setHeader(
                'Content-Disposition',
                f'inline; filename="{pagina}"'
            )
            return data
        except FileNotFoundError:
            logger.error(f"[PaginaProcessoLeg] Arquivo não encontrado: {file_path or pagina}")
            self.request.RESPONSE.setStatus(404)
            return "Página não encontrada"
        except SecurityError as se:
            error_msg = str(se)
            logger.error(f"[PaginaProcessoLeg] Erro de segurança ao acessar: {file_path or pagina} - {se}")
            # Verifica se o erro é "Base path does not exist" - indica que precisa regenerar pasta
            if "Base path does not exist" in error_msg:
                # Retorna status 404 com header especial indicando que precisa regenerar
                self.request.RESPONSE.setStatus(404)
                self.request.RESPONSE.setHeader('X-Pasta-Regenerate', 'true')
                self.request.RESPONSE.setHeader('X-Pasta-Cod-Materia', str(cod_materia))
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                import json
                return json.dumps({
                    'error': 'Base path does not exist',
                    'regenerate': True,
                    'cod_materia': str(cod_materia)
                }, ensure_ascii=False)
            # Outros erros de segurança retornam 403
            self.request.RESPONSE.setStatus(403)
            return "Acesso não permitido"
        except Exception as e:
            logger.error(f"[PaginaProcessoLeg] Erro inesperado: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return f"Erro ao carregar página: {str(e)}"

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

            dir_base = get_processo_dir(cod_materia)

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


class ProcessoLegTaskExecutor(grok.View):
    """
    View que executa a geração do processo legislativo no contexto do Zope.
    
    Esta view é chamada via HTTP pelo Celery worker, permitindo que a execução
    aconteça no contexto do Zope que já está rodando. Todos os documentos são
    baixados via HTTP, evitando problemas de acesso direto ao ZODB.
    """
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_task_executor')

    def _construir_url_documento(self, container, filename: str) -> str:
        """Constrói URL do documento para download via HTTP"""
        if hasattr(container, 'absolute_url'):
            base_url = container.absolute_url()
            return f"{base_url}/{filename}"
        else:
            # Tenta obter URL do contexto
            if hasattr(self.context, 'absolute_url'):
                base_url = self.context.absolute_url()
                container_name = getattr(container, '__name__', '')
                if container_name:
                    return f"{base_url}/{container_name}/{filename}"
                else:
                    return f"{base_url}/{filename}"
        return None
    
    def _baixar_documento_via_http_com_retry(self, url: str, caminho_saida: str, filename: str, max_retries: int = 3) -> bool:
        """
        Baixa um documento via HTTP com retry e backoff exponencial.
        OTIMIZAÇÃO: Retry com backoff exponencial para lidar com falhas temporárias.
        """
        # OTIMIZAÇÃO: Cache - verifica se arquivo já existe antes de baixar
        if os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 0:
            return True
        
        # Cria opener HTTP reutilizável para connection pooling
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'SAGL-PDF-Generator/1.0')]
        
        base_delay = 1.0  # Delay inicial de 1 segundo
        
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
                
                # OTIMIZAÇÃO: Timeout adaptativo baseado no tamanho esperado
                timeout = 60 if attempt == 0 else 90  # Timeout maior em retries
                
                with opener.open(req, timeout=timeout) as response:
                    file_data = response.read()
                
                    if file_data and len(file_data) > 0:
                        # Salva no filesystem
                        with open(caminho_saida, 'wb') as f:
                            f.write(file_data)
                        return True
                    else:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # Backoff exponencial
                            time.sleep(delay)
                        continue
                    
            except urllib.error.HTTPError as http_err:
                if http_err.code == 404:
                    return False  # 404 não deve ser retentado
                elif http_err.code >= 500 and attempt < max_retries - 1:
                    # Erros 5xx são retentáveis
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro HTTP {http_err.code} ao baixar '{filename}', tentando novamente em {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro HTTP ao baixar '{filename}': {http_err.code} - {http_err.reason}")
                    return False
                    
            except urllib.error.URLError as url_err:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro de URL ao baixar '{filename}', tentando novamente em {delay}s: {url_err}")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro de URL ao baixar '{filename}': {url_err}")
                    return False
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro ao baixar '{filename}', tentando novamente em {delay}s: {e}")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Erro ao baixar '{filename}': {e}")
                    return False
        
        return False
    
    def _baixar_documento_via_http(self, container, filename: str, caminho_saida: str) -> bool:
        """Baixa um documento do container Zope via HTTP e salva no filesystem (compatibilidade)"""
        try:
            # Constrói URL do objeto para download via HTTP
            url = self._construir_url_documento(container, filename)
            if not url:
                logger.warning(f"[_baixar_documento_via_http] Não foi possível construir URL para '{filename}'")
                return False
            
            # Usa função otimizada com retry
            return self._baixar_documento_via_http_com_retry(url, caminho_saida, filename)
        except Exception as e:
            logger.warning(f"[_baixar_documento_via_http] Erro ao baixar '{filename}': {e}")
            return False
    
    def _baixar_documento_worker(self, doc: Dict, dir_base: str) -> Tuple[Dict, bool]:
        """
        Worker para download paralelo de documentos.
        Retorna (doc_baixado, sucesso)
        """
        if doc.get('filesystem'):
            # Já está no filesystem, apenas retorna
            return doc, True
        
        # Precisa baixar via HTTP
        container = doc.get('path')
        filename = doc.get('file', '')
        
        if not container or not filename:
            logger.warning(f"[_baixar_documento_worker] Documento sem container ou filename, pulando: {doc.get('title', '?')}")
            return None, False
        
        # Cria caminho único para o arquivo
        caminho_arquivo = secure_path_join(dir_base, filename)
        
        # Constrói URL
        url = self._construir_url_documento(container, filename)
        if not url:
            logger.warning(f"[_baixar_documento_worker] Não foi possível construir URL para '{filename}'")
            return None, False
        
        # Baixa via HTTP com retry
        if self._baixar_documento_via_http_com_retry(url, caminho_arquivo, filename):
            # Atualiza documento para indicar que está no filesystem
            doc_baixado = doc.copy()
            doc_baixado['path'] = dir_base
            doc_baixado['filesystem'] = True
            return doc_baixado, True
        else:
            logger.warning(f"[_baixar_documento_worker] Falha ao baixar documento '{filename}'")
            return None, False

    def render(self):
        """
        Executa a geração do processo legislativo.
        
        Aceita POST ou GET com parâmetros:
        - cod_materia: Código da matéria (obrigatório)
        - portal_url: URL base do portal (opcional)
        - user_id: ID do usuário (opcional)
        """
        import json as json_lib
        try:
            # Obtém parâmetros da requisição
            cod_materia = self.request.form.get('cod_materia') or self.request.get('cod_materia')
            
            # Valida parâmetros obrigatórios
            if not cod_materia:
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': 'Parâmetro cod_materia é obrigatório', 'success': False})
            
            # Converte cod_materia para int se for string
            try:
                cod_materia = int(cod_materia)
            except (ValueError, TypeError):
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': 'cod_materia deve ser um número', 'success': False})
            
            
            # Cria instância da view ProcessoLegView no contexto do Zope
            view = ProcessoLegView(self.context, self.request)
            view.update()
            
            # Executa apenas o download dos arquivos (processamento pesado será feito na task Celery)
            try:
                # Etapa 1: Obter dados da matéria
                dados_materia = view.obter_dados_materia(cod_materia)
                
                # Etapa 2: Preparar diretórios
                dir_base, dir_paginas = view.preparar_diretorios(cod_materia)
                
                # Etapa 3: Coletar documentos
                documentos = view.coletar_documentos(dados_materia, dir_base)
                
                # Etapa 4: Baixar todos os documentos que não estão no filesystem
                # OTIMIZAÇÃO: Paralelização de downloads usando ThreadPoolExecutor
                documentos_baixados = []
                documentos_para_baixar = []
                
                # Separa documentos que já estão no filesystem dos que precisam ser baixados
                for doc in documentos:
                    if doc.get('filesystem'):
                        # Já está no filesystem, apenas adiciona
                        documentos_baixados.append(doc)
                    else:
                        # Precisa baixar via HTTP
                        documentos_para_baixar.append(doc)
                
                # OTIMIZAÇÃO: Paraleliza downloads quando há múltiplos documentos
                if documentos_para_baixar:
                    max_workers = min(4, len(documentos_para_baixar))  # Máximo de 4 workers simultâneos
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Submete todos os downloads
                        futures = {executor.submit(self._baixar_documento_worker, doc, dir_base): doc for doc in documentos_para_baixar}
                        
                        # Processa resultados conforme completam
                        for future in futures:
                            try:
                                doc_baixado, sucesso = future.result(timeout=300)  # Timeout de 5 minutos por documento
                                if sucesso and doc_baixado:
                                    documentos_baixados.append(doc_baixado)
                                    logger.debug(f"[ProcessoLegTaskExecutor] Documento '{doc_baixado.get('file', '?')}' baixado com sucesso")
                            except Exception as e:
                                doc_original = futures[future]
                                logger.warning(f"[ProcessoLegTaskExecutor] Erro ao baixar documento '{doc_original.get('file', '?')}': {e}")
                
                
                # Prepara dados para retornar (apenas informações, não processa)
                id_processo = dados_materia.get('id_exibicao', '')
                
                # Handler para converter objetos não serializáveis
                def default_serializer(obj):
                    """Handler para converter objetos não serializáveis"""
                    if isinstance(obj, str):
                        return obj
                    try:
                        if hasattr(obj, '__name__'):
                            return str(obj.__name__)
                        return str(obj)
                    except Exception:
                        return None
                
                # Converte documentos para estruturas serializáveis (todos já devem estar no filesystem)
                documentos_serializaveis = []
                for doc in documentos_baixados:
                    doc_serializavel = {}
                    for key, value in doc.items():
                        # Todos os documentos devem ter path como string agora
                        if key == 'path' and not isinstance(value, str):
                            # Se ainda não for string, converte
                            doc_serializavel['path'] = str(value) if value else dir_base
                        else:
                            doc_serializavel[key] = value
                    documentos_serializaveis.append(doc_serializavel)
                
                # Converte dados_materia: apenas campos serializáveis
                dados_materia_serializavel = {}
                for key, value in dados_materia.items():
                    try:
                        json.dumps(value, default=default_serializer)
                        dados_materia_serializavel[key] = value
                    except (TypeError, ValueError):
                        converted = default_serializer(value)
                        if converted is not None:
                            dados_materia_serializavel[key] = converted
                
                # Retorna informações para que a task Celery faça o processamento pesado
                self.request.RESPONSE.setStatus(200)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'success': True,
                    'cod_materia': cod_materia,
                    'dir_base': dir_base,
                    'dir_paginas': dir_paginas,
                    'id_processo': id_processo,
                    'documentos': documentos_serializaveis,
                    'dados_materia': dados_materia_serializavel
                }, default=default_serializer)
                
            except Exception as gen_err:
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[ProcessoLegTaskExecutor] Erro ao gerar processo: {gen_err}", exc_info=True)
                logger.error(f"[ProcessoLegTaskExecutor] Traceback completo:\n{error_traceback}")
                self.request.RESPONSE.setStatus(500)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'success': False,
                    'error': str(gen_err),
                    'error_type': type(gen_err).__name__,
                    'traceback': error_traceback,
                    'cod_materia': cod_materia,
                    'context_type': type(self.context).__name__,
                    'context_id': getattr(self.context, 'id', 'N/A'),
                    'has_sapl_documentos': hasattr(self.context, 'sapl_documentos'),
                    'has_modelo_proposicao': hasattr(self.context, 'modelo_proposicao')
                })
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"[ProcessoLegTaskExecutor] Erro inesperado: {e}", exc_info=True)
            logger.error(f"[ProcessoLegTaskExecutor] Traceback completo:\n{error_traceback}")
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({
                'error': str(e),
                'error_type': type(e).__name__,
                'success': False,
                'traceback': error_traceback
            })


class ProcessoLegStatusView(grok.View):
    """View para verificar status da geração do processo legislativo"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_integral_status')

    def render(self):
        """Retorna o status da tarefa"""
        from Products.CMFCore.utils import getToolByName
        
        try:
            task_id = self.request.form.get('task_id') or self.request.get('task_id')
            
            if not task_id:
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': 'Parâmetro task_id é obrigatório', 'status': 'ERROR'})
            
            tool = getToolByName(self.context, 'portal_sagl')
            status = tool.get_task_status(task_id)
            
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps(status)
            
        except Exception as e:
            logger.error(f"[ProcessoLegStatusView] Erro ao verificar status: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({'error': str(e), 'status': 'ERROR'})
