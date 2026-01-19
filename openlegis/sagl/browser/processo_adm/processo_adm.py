# -*- coding: utf-8 -*-
"""
Views de processamento do processo administrativo integral.
Gera PDF consolidado do processo administrativo com todos os documentos relacionados.

Baseado em processo_leg.py, adaptado para documentos administrativos.
"""
import os
import json
import logging
import hashlib
import time
import tempfile
import shutil
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timedelta, date
from io import BytesIO
from typing import Dict, List, Optional, Any, Tuple
from DateTime import DateTime
from five import grok
from zope.interface import Interface
from Products.CMFCore.utils import getToolByName
from concurrent.futures import ThreadPoolExecutor
import fitz
import pikepdf

# ReportLab para geração de PDFs
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfgen import canvas

from z3c.saconfig import named_scoped_session
from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload
from openlegis.sagl.models.models import (
    DocumentoAdministrativo, TipoDocumentoAdministrativo,
    DocumentoAcessorioAdministrativo, TramitacaoAdministrativo,
    DocumentoAdministrativoMateria, CientificacaoDocumento, Usuario
)

from openlegis.sagl.browser.processo_adm.processo_adm_utils import (
    get_processo_dir_adm, get_cache_file_path_adm,
    safe_check_file, safe_check_files_batch, get_file_size, secure_path_join, SecurityError,
    get_processo_dir_hash_adm
)
from openlegis.sagl.browser.processo_adm.processo_adm_service import ProcessoAdmService

logger = logging.getLogger(__name__)
Session = named_scoped_session('minha_sessao')

# Paleta de cores para PDFs
_theme_pdf = {
    'primary': '#003366',
    'secondary': '#E1F5FE',
    'success': '#4CAF50',
    'danger': '#F44336',
    'warning': '#FFC107',
    'light_gray': '#F5F5F5',
    'text': '#212121',
    'muted': '#757575',
}

# Cache de estilos ReportLab
_style_cache = {}


def _convert_to_datetime_string(date_obj):
    """
    Converte objetos datetime.date ou datetime.datetime para string.
    Compatível com DateTime() do Zope.
    """
    if date_obj is None:
        return ''
    if isinstance(date_obj, datetime):
        return date_obj.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(date_obj, date):
        return date_obj.strftime('%Y-%m-%d')
    return str(date_obj)


def get_cached_styles():
    """Retorna estilos do ReportLab em cache"""
    if not _style_cache:
        base = getSampleStyleSheet()
        _style_cache.update(base.byName)
        _style_cache.update({
            'Header1': ParagraphStyle(
                name='Header1', parent=base['Heading1'], fontSize=14,
                leading=18, alignment=TA_CENTER, textColor=colors.HexColor(_theme_pdf['primary'])
            ),
            'Header2': ParagraphStyle(
                name='Header2', parent=base['Heading2'], fontSize=11,
                leading=13, alignment=TA_LEFT, textColor=colors.HexColor(_theme_pdf['primary'])
            ),
            'Label': ParagraphStyle(
                name='Label', parent=base['Normal'], fontSize=9, leading=11,
                alignment=TA_LEFT, textColor=colors.HexColor(_theme_pdf['muted'])
            ),
            'Value': ParagraphStyle(
                name='Value', parent=base['Normal'], fontSize=9, leading=11,
                alignment=TA_LEFT, textColor=colors.HexColor(_theme_pdf['text'])
            ),
            'VoteResult': ParagraphStyle(
                name='VoteResult', parent=base['Normal'], fontSize=12, leading=15,
                alignment=TA_CENTER, textColor=colors.white,
                backColor=colors.HexColor(_theme_pdf['primary'])
            ),
            'TotalizadorCabecalho': ParagraphStyle(
                name='TotalizadorCabecalho', parent=base['Heading4'], fontSize=9,
                leading=11, alignment=TA_CENTER, textColor=colors.white
            ),
            'TotalizadorConteudo': ParagraphStyle(
                name='TotalizadorConteudo', parent=base['Normal'], fontSize=9,
                leading=11, alignment=TA_CENTER, textColor=colors.HexColor(_theme_pdf['text'])
            ),
            'TotalizadorDestaque': ParagraphStyle(
                name='TotalizadorDestaque', parent=base['Heading4'], fontSize=9,
                leading=11, alignment=TA_CENTER, textColor=colors.HexColor(_theme_pdf['primary'])
            ),
        })
    return _style_cache


def add_footer_cientificacoes(canvas_obj, doc):
    """Adiciona rodapé ao PDF de cientificações"""
    canvas_obj.saveState()
    margin_left = 15 * mm
    width, _ = doc.pagesize
    canvas_obj.setStrokeColor(colors.HexColor(_theme_pdf['primary']))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(margin_left, 40, width - margin_left, 40)
    canvas_obj.setFont('Helvetica', 7)
    canvas_obj.setFillColor(colors.HexColor(_theme_pdf['muted']))
    canvas_obj.drawString(margin_left, 30, "Documento gerado eletronicamente")
    canvas_obj.drawRightString(width - margin_left, 30, f"{DateTime().strftime('%d/%m/%Y %H:%M')} | Página {canvas_obj.getPageNumber()}")
    canvas_obj.restoreState()


def build_header_cientificacoes(nome_casa, styles, logo_bytes=None):
    """Constrói cabeçalho da folha de cientificações"""
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
        ('LINEBELOW', (0,1), (-1,1), 1, colors.HexColor(_theme_pdf['primary'])),
        ('BOTTOMPADDING', (0,1), (-1,1), 10),
    ]))
    return header_table


def _obter_info_casa_do_portal(portal) -> tuple:
    """
    Obtém nome da casa e logo do portal Zope.
    
    Args:
        portal: Objeto portal do Zope
        
    Returns:
        tuple: (nome_casa: str, logo_bytes: bytes ou None)
    """
    nome_casa = 'Casa Legislativa'  # Valor padrão
    logo_bytes = None
    
    try:
        # Obtém nome da casa e logo do props_sagl
        sapl_docs = getattr(portal, 'sapl_documentos', None)
        if sapl_docs:
            props = getattr(sapl_docs, 'props_sagl', None)
            if props:
                # Obtém nome da casa
                nome_casa = getattr(props, 'nom_casa', 'Casa Legislativa')
                if not nome_casa or nome_casa.strip() == '':
                    nome_casa = 'Casa Legislativa'
                
                # Obtém ID do logo
                id_logo = getattr(props, 'id_logo', None)
                
                # Tenta obter o logo como bytes se existir
                if id_logo:
                    try:
                        # Verifica se o logo existe no props_sagl
                        if hasattr(props, id_logo):
                            logo_obj = getattr(props, id_logo, None)
                            if logo_obj:
                                # Obtém os bytes do logo
                                if hasattr(logo_obj, 'data'):
                                    logo_data = logo_obj.data
                                    # Verifica o tipo de dados
                                    if isinstance(logo_data, bytes):
                                        logo_bytes = logo_data
                                    elif hasattr(logo_data, 'data'):
                                        # Pode ser um objeto Zope com sub-atributo data
                                        logo_bytes = logo_data.data if isinstance(logo_data.data, bytes) else None
                                    elif isinstance(logo_data, str):
                                        # Se for string, converte para bytes
                                        logo_bytes = logo_data.encode('utf-8') if logo_data else None
                                elif hasattr(logo_obj, 'read'):
                                    # Se tiver método read, usa read()
                                    logo_obj.seek(0)
                                    logo_bytes = logo_obj.read()
                                    if isinstance(logo_bytes, str):
                                        logo_bytes = logo_bytes.encode('utf-8')
                    except Exception as e:
                        logger.warning(f"[_obter_info_casa_do_portal] Erro ao obter logo: {e}")
    except Exception as e:
        logger.warning(f"[_obter_info_casa_do_portal] Erro ao obter informações do portal: {e}")
    
    return nome_casa, logo_bytes


def _obter_info_casa_via_http(portal_url: str) -> tuple:
    """
    Tenta obter nome da casa e logo via HTTP.
    
    Esta função é usada como fallback quando não há acesso direto ao portal Zope
    (ex: em tasks assíncronas). Tenta baixar o logo diretamente pela URL.
    
    Args:
        portal_url: URL base do portal
        
    Returns:
        tuple: (nome_casa: str, logo_bytes: bytes ou None)
    """
    nome_casa = 'Casa Legislativa'  # Valor padrão
    logo_bytes = None
    
    try:
        # Tenta baixar o logo padrão via HTTP
        # O logo geralmente está em: {portal_url}/sapl_documentos/props_sagl/{id_logo}
        # Como não sabemos o id_logo sem acesso ao portal, tentamos o padrão
        logo_urls = [
            f"{portal_url.rstrip('/')}/sapl_documentos/props_sagl/logo_casa.gif",
            f"{portal_url.rstrip('/')}/sapl_documentos/props_sagl/brasao.gif",
            f"{portal_url.rstrip('/')}/sapl_documentos/props_sagl/brasao.png",
        ]
        
        for logo_url in logo_urls:
            try:
                req = urllib.request.Request(logo_url)
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        logo_bytes = response.read()
                        if logo_bytes:
                            logger.debug(f"[_obter_info_casa_via_http] Logo obtido via HTTP: {logo_url}")
                            break
            except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
                # Continua tentando outras URLs
                continue
    except Exception as e:
        logger.debug(f"[_obter_info_casa_via_http] Erro ao tentar obter logo via HTTP: {e}")
    
    return nome_casa, logo_bytes


def gerar_folha_cientificacao_pdf(session, portal_url: str, cod_documento: int, caminho_saida: str, dados_cientificacoes: List[Dict], nome_casa: str = None, logo_bytes: bytes = None):
    """
    Gera folha de cientificações em PDF.
    
    Migrado de processo_adm.py (antigo) linhas 223-395, adaptado para usar SQLAlchemy.
    
    Args:
        session: Sessão SQLAlchemy
        portal_url: URL base do portal
        cod_documento: Código do documento administrativo
        caminho_saida: Caminho completo onde salvar o PDF
        dados_cientificacoes: Lista de dicionários com dados das cientificações
        nome_casa: Nome da casa legislativa (opcional, será obtido se None)
        logo_bytes: Bytes do logo (opcional, será obtido se None)
    """
    # Proteção: não gera se não houver registros
    if not dados_cientificacoes:
        return

    styles = get_cached_styles()

    # Obtém nome da casa e logo se não fornecidos
    if nome_casa is None:
        nome_casa, logo_bytes = _obter_info_casa_via_http(portal_url)
        if nome_casa == '(não definido)':
            nome_casa = 'Casa Legislativa'  # Fallback

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

    # Info do documento (SQLAlchemy)
    try:
        doc_result = session.query(DocumentoAdministrativo, TipoDocumentoAdministrativo)\
            .join(TipoDocumentoAdministrativo, 
                  DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
            .filter(DocumentoAdministrativo.cod_documento == cod_documento)\
            .filter(DocumentoAdministrativo.ind_excluido == 0)\
            .first()
        
        if doc_result:
            doc_adm, tipo_doc = doc_result
            titulo_doc = f"{tipo_doc.des_tipo_documento or tipo_doc.sgl_tipo_documento} {doc_adm.num_documento}/{doc_adm.ano_documento}"
            elements.append(Paragraph(titulo_doc, styles['Header2']))
            elements.append(Spacer(1, 6))
    except Exception as e:
        logger.warning(f"[gerar_folha_cientificacao_pdf] Erro ao obter dados do documento: {e}")

    # Banner (usa o mesmo estilo "VoteResult" como faixa azul)
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(_theme_pdf['primary'])),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#EEEEEE')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#FAFAFA')]),
        ('ALIGN', (0,1), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),
    ]))

    # Pintar a coluna "Leitura" por status (coluna 4)
    for i, r in enumerate(dados_cientificacoes, start=1):
        dat_read = r.get('dat_leitura', '')
        dat_exp = r.get('dat_expiracao', '')
        if dat_read:
            color_cell = colors.HexColor(_theme_pdf['success'])
        else:
            try:
                exp_dt = DateTime(dat_exp) if dat_exp else None
                color_cell = colors.HexColor(_theme_pdf['danger']) if (exp_dt and now_dt > exp_dt) else colors.HexColor(_theme_pdf['warning'])
            except Exception:
                color_cell = colors.HexColor(_theme_pdf['warning'])
        table.setStyle(TableStyle([('BACKGROUND', (4, i), (4, i), color_cell)]))

    elements.append(table)
    elements.append(Spacer(1, 10))

    # Totalização
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(_theme_pdf['primary'])),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor(_theme_pdf['light_gray'])),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor(_theme_pdf['primary'])),
        ('BACKGROUND', (0,1), (0,1), colors.HexColor('#FFF8E1')),
        ('BACKGROUND', (0,2), (0,2), colors.HexColor('#E8F5E9')),
        ('BACKGROUND', (0,3), (0,3), colors.HexColor('#FFEBEE')),
    ]))
    elements.append(Paragraph('TOTALIZAÇÃO', styles['Header2']))
    elements.append(totals_table)

    # Build e otimização via fitz
    doc.build(elements, onFirstPage=add_footer_cientificacoes, onLaterPages=add_footer_cientificacoes)
    buffer.seek(0)
    with fitz.open(stream=buffer.read(), filetype='pdf') as pdf:
        pdf.bake()
        pdf.save(caminho_saida, garbage=3, deflate=True, use_objstms=True)


def coletar_cientificacoes_com_nomes(session, cod_documento, somente_pendentes=False):
    """
    Coleta cientificações com nomes dos usuários usando SQLAlchemy.
    
    OTIMIZAÇÃO: Usa eager loading com joinedload para garantir relacionamentos.
    Removido fallback de N+1 queries que causava queries adicionais.
    
    Migrado de processo_adm.py (linhas 188-218) para usar SQLAlchemy em vez de ZSQL.
    
    Args:
        session: Sessão SQLAlchemy (deve ser fornecida e fechada pelo caller)
        cod_documento: Código do documento administrativo
        somente_pendentes: Se True, retorna apenas pendentes (dat_leitura IS NULL)
        
    Returns:
        list: Lista de dicionários com dados das cientificações, incluindo nomes dos usuários
        
    Exemplo:
        session = Session()
        try:
            dados = coletar_cientificacoes_com_nomes(session, 123, somente_pendentes=False)
        finally:
            session.close()
    """
    try:
        # OTIMIZAÇÃO: Query com eager loading usando joinedload (mais eficiente que selectinload)
        from sqlalchemy.orm import joinedload
        
        query = session.query(CientificacaoDocumento)\
            .options(
                joinedload(CientificacaoDocumento.usuario),  # cientificado
                joinedload(CientificacaoDocumento.usuario_)  # cientificador
            )\
            .filter(CientificacaoDocumento.cod_documento == cod_documento)\
            .filter(CientificacaoDocumento.ind_excluido == 0)
        
        # Filtra pendentes se solicitado
        # Pendente = dat_leitura é NULL
        if somente_pendentes:
            query = query.filter(CientificacaoDocumento.dat_leitura.is_(None))
        
        cientificacoes = query.all()
        
        dados = []
        for cient in cientificacoes:
            try:
                # OTIMIZAÇÃO: Obtém nomes usando relationships (já carregados com eager loading)
                # Removido fallback de N+1 queries que causava queries adicionais
                nom_cientificador = None
                nom_cientificado = None
                
                # Usa relationship usuario_ para cientificador
                if hasattr(cient, 'usuario_') and cient.usuario_:
                    nom_cientificador = getattr(cient.usuario_, 'nom_completo', None)
                
                # Usa relationship usuario para cientificado
                if hasattr(cient, 'usuario') and cient.usuario:
                    nom_cientificado = getattr(cient.usuario, 'nom_completo', None)
                
                # Se ainda não tiver nome (relacionamento não funcionou), loga warning mas não busca
                # OTIMIZAÇÃO: Removido fallback de N+1 queries
                if not nom_cientificador or not nom_cientificado:
                    pass
                
                dados.append({
                    'id': cient.id,
                    'cod_documento': cient.cod_documento,
                    'cod_cientificador': cient.cod_cientificador,
                    'nom_cientificador': nom_cientificador or '(não identificado)',
                    'cod_cientificado': cient.cod_cientificado,
                    'nom_cientificado': nom_cientificado or '(não identificado)',
                    'dat_envio': _convert_to_datetime_string(cient.dat_envio) if cient.dat_envio else '',
                    'dat_expiracao': _convert_to_datetime_string(cient.dat_expiracao) if cient.dat_expiracao else '',
                    'dat_leitura': _convert_to_datetime_string(cient.dat_leitura) if cient.dat_leitura else '',
                })
            except Exception as e:
                logger.warning(f"[coletar_cientificacoes_com_nomes] Erro ao processar cientificação id={getattr(cient, 'id', '?')}: {e}")
                continue
        
        return dados
        
    except Exception as e:
        logger.error(f"[coletar_cientificacoes_com_nomes] Erro ao coletar cientificações: {e}", exc_info=True)
        return []

# Constantes
MAX_PAGES = 5000
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB


class PDFGenerationError(Exception):
    """Exceção para erros na geração de PDF"""
    pass


class ProcessoAdmView(grok.View):
    """View principal para geração do processo administrativo integral"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral')
    
    def __init__(self, context, request):
        """Inicializa a view com caches"""
        super().__init__(context, request)
        self._cache_dados_documento = {}
        self._cache_session = None
    
    def update(self):
        """Extrai parâmetros da requisição antes do render"""
        self.cod_documento = self.request.form.get('cod_documento')
        self.action = self.request.form.get('action', 'json')
    
    def _get_session(self):
        """
        Retorna sessão SQLAlchemy thread-safe.
        OTIMIZAÇÃO: Reutiliza sessão dentro da mesma requisição.
        """
        if self._cache_session is None:
            self._cache_session = Session()
        return self._cache_session
    
    def _close_session(self):
        """Fecha a sessão SQLAlchemy se estiver aberta"""
        if self._cache_session is not None:
            try:
                self._cache_session.close()
            except Exception:
                pass
            finally:
                self._cache_session = None
    
    def _get_dir_hash(self, cod_documento):
        """Retorna o hash do diretório para um cod_documento (cached)"""
        if not hasattr(self, '_dir_hash_cache'):
            self._dir_hash_cache = {}
        cod_str = str(cod_documento)
        if cod_str not in self._dir_hash_cache:
            self._dir_hash_cache[cod_str] = get_processo_dir_hash_adm(cod_documento)
        return self._dir_hash_cache[cod_str]
    
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
    
    def preparar_diretorios(self, cod_documento: int) -> Tuple[str, str]:
        """Cria diretórios temporários de trabalho com segurança"""
        try:
            # 1) Validar código do documento
            if not cod_documento or not str(cod_documento).isdigit():
                raise ValueError("Código do documento inválido")
            
            # 2) Usa função utilitária para obter diretório do processo
            dir_base = get_processo_dir_adm(cod_documento)
            
            # 3) Verifica se o diretório está dentro do temp_base (segurança)
            temp_base_abs = os.path.abspath(self.temp_base)
            dir_base_abs = os.path.abspath(dir_base)
            if not dir_base_abs.startswith(temp_base_abs + os.sep):
                raise SecurityError(f"Diretório do processo fora do temp_base permitido: {dir_base}")
            
            # 4) Verifica se diretório existe e tem cache válido antes de deletar
            # CRÍTICO: Alinhado com processo_leg - verifica cache.json para evitar deletar conteúdo válido
            # OTIMIZAÇÃO: Verifica apenas cache.json primeiro (evita I/O desnecessário)
            if os.path.exists(dir_base):
                cache_file = get_cache_file_path_adm(cod_documento)
                has_valid_content = False
                
                # PRIORIDADE 1: Verifica se tem cache.json válido (verificação única e rápida)
                # Se cache.json existe e é válido, não precisa verificar outros arquivos
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                            # Valida estrutura do cache (alinhado com processo_leg)
                            if isinstance(cache_data, dict) and 'documentos' in cache_data and 'timestamp' in cache_data:
                                has_valid_content = True
                    except Exception:
                        pass  # Cache corrompido, pode deletar
                
                # OTIMIZAÇÃO: Só verifica outros arquivos se cache.json não existir ou for inválido
                # Isso reduz I/O desnecessário na maioria dos casos
                if not has_valid_content:
                    metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                    ready_file = os.path.join(dir_base, '.ready')
                    dir_paginas_check = os.path.join(dir_base, 'pages')
                    
                    # PRIORIDADE 2: Verifica se tem metadados válidos (backup check)
                    if os.path.exists(metadados_path):
                        try:
                            with open(metadados_path, 'r', encoding='utf-8') as f:
                                metadados = json.load(f)
                                if metadados.get('total_paginas', 0) > 0:
                                    has_valid_content = True
                        except Exception:
                            pass  # Metadados corrompidos, pode deletar
                    
                    # PRIORIDADE 3: Verifica se tem arquivo .ready (processo concluído) - verificação rápida
                    if not has_valid_content and os.path.exists(ready_file):
                        has_valid_content = True
                    
                    # PRIORIDADE 4: Verifica se tem páginas geradas (último check - mais lento)
                    if not has_valid_content and os.path.exists(dir_paginas_check) and os.path.isdir(dir_paginas_check):
                        try:
                            pagina_files = [f for f in os.listdir(dir_paginas_check) if f.lower().endswith('.pdf')]
                            if len(pagina_files) > 0:
                                has_valid_content = True
                        except Exception:
                            pass  # Erro ao listar, pode deletar
                
                # Se tem conteúdo válido, preserva o diretório (apenas garante que subdiretórios existem)
                if has_valid_content:
                    logger.info(f"[preparar_diretorios] Preservando diretório existente com conteúdo válido: {dir_base}")
                    dir_paginas = secure_path_join(dir_base, 'pages')
                    os.makedirs(dir_paginas, mode=0o700, exist_ok=True)
                    return dir_base, dir_paginas
                
                # Se não tem conteúdo válido, deleta e recria
                shutil.rmtree(dir_base, ignore_errors=True)
            
            # 5) Cria diretório novo (ou recriado)
            os.makedirs(dir_base, mode=0o700, exist_ok=True)
            
            # 6) Secure-join para o subdiretório de páginas (já que dir_base existe)
            dir_paginas = secure_path_join(dir_base, 'pages')
            os.makedirs(dir_paginas, mode=0o700, exist_ok=True)
            
            return dir_base, dir_paginas
        
        except Exception as e:
            logger.error(f"Erro ao preparar diretórios: {e}", exc_info=True)
            raise PDFGenerationError(f"Falha na preparação dos diretórios: {e}")
    
    def obter_dados_documento(self, cod_documento, use_cache=True):
        """
        Obtém informações básicas do documento administrativo com validação - SQLAlchemy.
        
        OTIMIZAÇÃO: Cache para evitar queries repetidas na mesma requisição.
        
        Args:
            cod_documento: Código do documento
            use_cache: Se True, usa cache (padrão: True)
        """
        # OTIMIZAÇÃO: Cache de dados do documento
        if use_cache and cod_documento in self._cache_dados_documento:
            return self._cache_dados_documento[cod_documento]
        
        try:
            if not cod_documento or not str(cod_documento).isdigit():
                raise ValueError("Código do documento inválido")
            
            session = self._get_session()
            result = session.query(DocumentoAdministrativo, TipoDocumentoAdministrativo)\
                .join(TipoDocumentoAdministrativo, 
                      DocumentoAdministrativo.tip_documento == TipoDocumentoAdministrativo.tip_documento)\
                .filter(DocumentoAdministrativo.cod_documento == cod_documento)\
                .filter(DocumentoAdministrativo.ind_excluido == 0)\
                .first()
            
            if not result:
                raise ValueError("Documento não encontrado")
            
            doc_obj, tipo_obj = result
            
            # Converte dat_documento para string se for date/datetime
            data_documento = _convert_to_datetime_string(doc_obj.dat_documento)
            
            dados = {
                'id': f"{tipo_obj.sgl_tipo_documento}-{doc_obj.num_documento}-{doc_obj.ano_documento}",
                'id_exibicao': f"{tipo_obj.sgl_tipo_documento} {doc_obj.num_documento}/{doc_obj.ano_documento}",
                'tipo': tipo_obj.sgl_tipo_documento,
                'numero': doc_obj.num_documento,
                'ano': doc_obj.ano_documento,
                'data_documento': data_documento,
                'descricao': tipo_obj.des_tipo_documento,
                'cod_documento': doc_obj.cod_documento,
                'txt_assunto': doc_obj.txt_assunto or '',
                'txt_interessado': doc_obj.txt_interessado or ''
            }
            
            # OTIMIZAÇÃO: Armazena no cache
            if use_cache:
                self._cache_dados_documento[cod_documento] = dados
            
            return dados
        
        except Exception as e:
            logger.error(f"Erro ao obter dados do documento: {str(e)}", exc_info=True)
            raise PDFGenerationError(f"Falha ao obter dados do documento: {str(e)}")
    
    def _baixar_arquivo_via_http_local(self, portal_url: str, caminho_relativo: str, caminho_saida: str, timeout: int = None) -> bool:
        """
        Baixa um arquivo via HTTP do Zope (função auxiliar local).
        
        Trata silenciosamente arquivos que não existem (404/NotFound), seguindo o padrão do processo_leg.
        
        OTIMIZAÇÃO: Timeout adaptativo baseado no tamanho esperado do arquivo.
        
        IMPORTANTE: Quando fazemos requisição HTTP para o Zope dentro do contexto Zope,
        o Zope pode lançar exceção NotFound antes de retornar 404. Esta função trata
        isso silenciosamente, como no processo_leg.
        
        Args:
            portal_url: URL base do portal
            caminho_relativo: Caminho relativo do arquivo
            caminho_saida: Caminho completo onde salvar o arquivo
            timeout: Timeout em segundos (None para usar padrão adaptativo)
            
        Returns:
            bool: True se baixou com sucesso, False caso contrário (inclui 404/NotFound)
        """
        # OTIMIZAÇÃO: Cache - verifica se arquivo já existe
        if os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 0:
            return True
        
        base_url = portal_url.rstrip('/')
        url = f"{base_url}/{caminho_relativo}"
        
        # OTIMIZAÇÃO: Timeout adaptativo baseado no tamanho esperado do arquivo
        if timeout is None:
            # Timeout padrão de 30s para arquivos pequenos/médios
            # Para arquivos grandes (mais de 5MB), aumenta o timeout proporcionalmente
            # Assume ~1MB/s de velocidade de download como baseline
            timeout = 30
            # Se o arquivo já existe, pode estimar tamanho baseado nele
            if os.path.exists(caminho_saida):
                try:
                    existing_size = os.path.getsize(caminho_saida)
                    # Para arquivos existentes > 5MB, aumenta timeout proporcionalmente
                    if existing_size > 5 * 1024 * 1024:
                        timeout = max(30, int(existing_size / (1024 * 1024)) * 2)  # ~2s por MB
                except Exception:
                    pass  # Se não conseguir obter tamanho, usa timeout padrão
        
        # Tenta importar exceções do Zope para tratamento explícito
        try:
            from zExceptions import NotFound as ZopeNotFound
            NotFound_available = True
        except ImportError:
            NotFound_available = False
            ZopeNotFound = None
        
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
            req.add_header('Accept', 'application/pdf,application/octet-stream,*/*')
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 404:
                    return False
                
                file_data = response.read()
                
                if file_data and len(file_data) > 0:
                    dir_saida = os.path.dirname(caminho_saida)
                    if dir_saida:
                        os.makedirs(dir_saida, exist_ok=True)
                    with open(caminho_saida, 'wb') as f:
                        f.write(file_data)
                    return True
                else:
                    return False
                    
        except urllib.error.HTTPError as e:
            # Trata 404 de forma silenciosa (não tenta novamente)
            if e.code == 404:
                # Lê e descarta o corpo da resposta 404 para evitar problemas com páginas de erro
                try:
                    e.read()
                except:
                    pass
                return False
            logger.warning(f"[_baixar_arquivo_via_http_local] Erro HTTP {e.code} ao baixar {caminho_relativo}")
            return False
        except urllib.error.URLError as e:
            # Erros de URL (timeout, conexão, etc) - trata como arquivo não encontrado silenciosamente
            return False
        except KeyError as e:
            # Captura KeyError do Zope (erros de traverse quando arquivo não existe)
            return False
        except Exception as e:
            # CRÍTICO: Captura qualquer exceção, incluindo NotFound do Zope quando tenta fazer traverse
            # Isso evita que erros do Zope (como NotFound/KeyError) propaguem e quebrem o processo
            error_msg = str(e).lower()
            error_type = type(e).__name__
            
            # Verifica se é NotFound do Zope (disponível ou não)
            if NotFound_available and isinstance(e, ZopeNotFound):
                return False
            
            # Se for erro do Zope (NotFound, KeyError) ou mensagem contém "not found" ou "404" ou "cannot locate", trata como 404
            if ('notfound' in error_type.lower() or 
                'keyerror' in error_type.lower() or 
                'cannot locate' in error_msg or 
                'not found' in error_msg or 
                '404' in error_msg or
                'zexceptions' in error_type.lower() or
                'zexceptions.notfound' in error_msg.lower()):
                return False
            
            # Para outros erros não relacionados a "não encontrado", apenas retorna False silenciosamente
            # Isso segue o padrão do processo_leg: trata todos os erros de download de forma silenciosa
            return False
    
    def _coletar_capa(self, cod_documento: int, portal_url: str, dir_base: str, dat_documento: str, tipo: str, numero: int, ano: int) -> Optional[Dict]:
        """
        Coleta a capa do processo administrativo.
        OTIMIZAÇÃO: Método separado para facilitar manutenção.
        """
        arquivo_capa = f"capa_{tipo}-{numero}-{ano}.pdf"
        caminho_capa = os.path.join(dir_base, arquivo_capa)
        data_capa = f"{dat_documento[:10]} 00:00:01"
        
        # Gera capa via HTTP
        nom_arquivo_temp = uuid.uuid4().hex
        capa_url_gerar = f"{portal_url}/modelo_proposicao/capa_processo_adm?cod_documento={cod_documento}&nom_arquivo={nom_arquivo_temp}&action=gerar"
        
        try:
            req_gerar = urllib.request.Request(capa_url_gerar)
            req_gerar.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
            with urllib.request.urlopen(req_gerar, timeout=30) as response:
                pass
            
            time.sleep(0.5)
            
            capa_url_download = f"{portal_url}/modelo_proposicao/capa_processo_adm?cod_documento={cod_documento}&nom_arquivo={nom_arquivo_temp}&action=download"
            req_download = urllib.request.Request(capa_url_download)
            req_download.add_header('User-Agent', 'SAGL-PDF-Generator/1.0')
            
            with urllib.request.urlopen(req_download, timeout=60) as response:
                capa_data = response.read()
            
            if capa_data and len(capa_data) > 0:
                with open(caminho_capa, 'wb') as f:
                    f.write(capa_data)
                
                if os.path.getsize(caminho_capa) > 0:
                    return {
                        "data": data_capa,
                        "path": dir_base,
                        "file": arquivo_capa,
                        "title": "Capa do Processo",
                        "filesystem": True
                    }
        except Exception as e:
            logger.error(f"[ProcessoAdmView._coletar_capa] Erro ao gerar capa: {e}", exc_info=True)
            raise Exception(f"Falha ao gerar/baixar capa: {str(e)}")
        
        return None
    
    def _coletar_texto_integral(self, cod_documento: int, portal_url: str, portal, dir_base: str, dat_documento: str, tipo_doc_des: str, numero: int, ano: int) -> Optional[Dict]:
        """
        Coleta o texto integral do documento administrativo.
        OTIMIZAÇÃO: Método separado para facilitar manutenção.
        """
        nom_arquivo_texto = f"{cod_documento}_texto_integral.pdf"
        texto_path_rel = f"sapl_documentos/administrativo/{nom_arquivo_texto}"
        texto_path_abs = os.path.join(dir_base, nom_arquivo_texto)
        
        try:
            # Verifica se o arquivo existe no Zope antes de tentar baixar
            if hasattr(portal, 'sapl_documentos') and hasattr(portal.sapl_documentos, 'administrativo'):
                if safe_check_file(portal.sapl_documentos.administrativo, nom_arquivo_texto):
                    if self._baixar_arquivo_via_http_local(portal_url, texto_path_rel, texto_path_abs):
                        return {
                            "data": f"{dat_documento[:10]} 00:00:02",
                            'path': dir_base,
                            'file': nom_arquivo_texto,
                            'title': f"{tipo_doc_des} {numero}/{ano}",
                            'filesystem': True
                        }
        except Exception as e:
            error_type = type(e).__name__
            if 'NotFound' in error_type or 'KeyError' in error_type:
                pass
            else:
                pass
        
        return None
    
    def _coletar_documentos_acessorios(self, session, cod_documento: int, portal_url: str, portal, dir_base: str, dat_documento: str) -> List[Dict]:
        """
        Coleta documentos acessórios do processo administrativo.
        OTIMIZAÇÃO: Usa verificação em lote e downloads paralelos.
        """
        documentos = []
        
        # Query para obter documentos acessórios
        documentos_acessorios = session.query(DocumentoAcessorioAdministrativo)\
            .filter(DocumentoAcessorioAdministrativo.cod_documento == cod_documento)\
            .filter(DocumentoAcessorioAdministrativo.ind_excluido == 0)\
            .order_by(DocumentoAcessorioAdministrativo.dat_documento)\
            .all()
        
        
        if not documentos_acessorios:
            return documentos
        
        # OTIMIZAÇÃO: Verificação em lote
        nomes_acessorios = [f"{doc.cod_documento_acessorio}.pdf" for doc in documentos_acessorios]
        arquivos_existentes = {}
        
        try:
            if hasattr(portal, 'sapl_documentos') and hasattr(portal.sapl_documentos, 'administrativo'):
                arquivos_existentes = safe_check_files_batch(
                    portal.sapl_documentos.administrativo,
                    nomes_acessorios
                )
        except Exception:
            pass
        
        # OTIMIZAÇÃO: Coleta URLs primeiro, depois baixa em paralelo
        itens_para_baixar = []
        documentos_map = {}
        
        for doc_acess in documentos_acessorios:
            nome_acessorio = f"{doc_acess.cod_documento_acessorio}.pdf"
            
            # Verifica se arquivo existe (verificação em lote)
            if arquivos_existentes.get(nome_acessorio, False):
                acessorio_path_rel = f"sapl_documentos/administrativo/{nome_acessorio}"
                acessorio_path_abs = os.path.join(dir_base, nome_acessorio)
                
                itens_para_baixar.append({
                    'url': f"{portal_url.rstrip('/')}/{acessorio_path_rel}",
                    'path': acessorio_path_abs,
                    'filename': nome_acessorio,
                    'doc': doc_acess,
                    'dat': _convert_to_datetime_string(doc_acess.dat_documento) if doc_acess.dat_documento else dat_documento
                })
                documentos_map[nome_acessorio] = doc_acess
        
        # OTIMIZAÇÃO: Downloads paralelos
        if itens_para_baixar:
            max_workers = min(4, len(itens_para_baixar))
            
            def _baixar_item(item):
                """Worker para download de um item"""
                try:
                    # Extrai caminho relativo da URL completa
                    caminho_rel = item['url'].replace(portal_url.rstrip('/'), '').lstrip('/')
                    if self._baixar_arquivo_via_http_local(portal_url, caminho_rel, item['path']):
                        return item
                except Exception:
                    pass
                return None
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_baixar_item, item): item for item in itens_para_baixar}
                
                for future in futures:
                    try:
                        item = future.result(timeout=300)
                        if item:
                            doc_acess = item['doc']
                            nome_acessorio = item['filename']
                            documentos.append({
                                "data": item['dat'],
                                'path': dir_base,
                                'file': nome_acessorio,
                                'title': doc_acess.nom_documento or f'Documento Acessório {doc_acess.cod_documento_acessorio}',
                                'filesystem': True
                            })
                    except Exception as e:
                        item = futures[future]
                        logger.warning(f"[ProcessoAdmView._coletar_documentos_acessorios] Erro ao baixar documento acessório '{item['filename']}': {e}")
        
        return documentos
    
    def _coletar_tramitacoes(self, session, cod_documento: int, portal_url: str, portal, dir_base: str, dat_documento: str) -> List[Dict]:
        """
        Coleta tramitações do processo administrativo.
        OTIMIZAÇÃO: Usa verificação em lote e downloads paralelos.
        """
        documentos = []
        
        from openlegis.sagl.models.models import StatusTramitacaoAdministrativo
        tramitacoes = session.query(TramitacaoAdministrativo, StatusTramitacaoAdministrativo)\
            .outerjoin(StatusTramitacaoAdministrativo, TramitacaoAdministrativo.cod_status == StatusTramitacaoAdministrativo.cod_status)\
            .filter(TramitacaoAdministrativo.cod_documento == cod_documento)\
            .filter(TramitacaoAdministrativo.ind_excluido == 0)\
            .order_by(TramitacaoAdministrativo.dat_tramitacao, TramitacaoAdministrativo.cod_tramitacao)\
            .all()
        
        if not tramitacoes:
            return documentos
        
        # OTIMIZAÇÃO: Verificação em lote
        nomes_tram = [f"{tram.cod_tramitacao}_tram.pdf" for tram, _ in tramitacoes]
        arquivos_existentes = {}
        
        try:
            if (hasattr(portal, 'sapl_documentos') and 
                hasattr(portal.sapl_documentos, 'administrativo') and 
                hasattr(portal.sapl_documentos.administrativo, 'tramitacao')):
                arquivos_existentes = safe_check_files_batch(
                    portal.sapl_documentos.administrativo.tramitacao,
                    nomes_tram
                )
        except Exception:
            pass
        
        # OTIMIZAÇÃO: Coleta URLs primeiro, depois baixa em paralelo
        itens_para_baixar = []
        
        for tram, status in tramitacoes:
            nome_tram = f"{tram.cod_tramitacao}_tram.pdf"
            
            # Verifica se arquivo existe (verificação em lote)
            if arquivos_existentes.get(nome_tram, False):
                tram_path_rel = f"sapl_documentos/administrativo/tramitacao/{nome_tram}"
                tram_path_abs = os.path.join(dir_base, nome_tram)
                
                itens_para_baixar.append({
                    'url': f"{portal_url.rstrip('/')}/{tram_path_rel}",
                    'path': tram_path_abs,
                    'filename': nome_tram,
                    'tram': tram,
                    'status': status,
                    'dat': _convert_to_datetime_string(tram.dat_tramitacao) if tram.dat_tramitacao else dat_documento
                })
        
        # OTIMIZAÇÃO: Downloads paralelos
        if itens_para_baixar:
            max_workers = min(4, len(itens_para_baixar))
            
            def _baixar_item(item):
                """Worker para download de um item"""
                try:
                    # Extrai caminho relativo da URL completa
                    caminho_rel = item['url'].replace(portal_url.rstrip('/'), '').lstrip('/')
                    if self._baixar_arquivo_via_http_local(portal_url, caminho_rel, item['path']):
                        return item
                except Exception:
                    pass
                return None
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_baixar_item, item): item for item in itens_para_baixar}
                
                for future in futures:
                    try:
                        item = future.result(timeout=300)
                        if item:
                            tram = item['tram']
                            status = item['status']
                            nome_tram = item['filename']
                            des_status = status.des_status if status else 'Tramitação'
                            documentos.append({
                                "data": item['dat'],
                                'path': dir_base,
                                'file': nome_tram,
                                'title': f"Tramitação ({des_status})",
                                'filesystem': True
                            })
                    except Exception as e:
                        item = futures[future]
                        logger.warning(f"[ProcessoAdmView._coletar_tramitacoes] Erro ao baixar tramitação '{item['filename']}': {e}")
        
        return documentos
    
    def _coletar_materias_vinculadas(self, session, cod_documento: int, portal_url: str, portal, dir_base: str, dat_documento: str) -> List[Dict]:
        """
        Coleta matérias vinculadas do processo administrativo.
        OTIMIZAÇÃO: Verifica em lote e downloads paralelos (mesmo padrão dos documentos acessórios).
        """
        documentos = []
        
        from openlegis.sagl.models.models import MateriaLegislativa, TipoMateriaLegislativa
        materias_vinculadas = session.query(DocumentoAdministrativoMateria, MateriaLegislativa, TipoMateriaLegislativa)\
            .join(MateriaLegislativa, DocumentoAdministrativoMateria.cod_materia == MateriaLegislativa.cod_materia)\
            .join(TipoMateriaLegislativa, MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
            .filter(DocumentoAdministrativoMateria.cod_documento == cod_documento)\
            .filter(DocumentoAdministrativoMateria.ind_excluido == 0)\
            .filter(MateriaLegislativa.ind_excluido == 0)\
            .all()
        
        if not materias_vinculadas:
            return documentos
        
        # OTIMIZAÇÃO: Verificação em lote - verifica todos os arquivos possíveis primeiro
        sufixos = ['_texto_integral.pdf', '_redacao_final.pdf']
        nomes_materias = []
        
        for doc_mat, materia, tipo_materia in materias_vinculadas:
            for sufixo in sufixos:
                nome_materia = f"{materia.cod_materia}{sufixo}"
                nomes_materias.append(nome_materia)
        
        # Verifica quais arquivos existem (em lote)
        arquivos_existentes = {}
        try:
            if hasattr(portal, 'sapl_documentos') and hasattr(portal.sapl_documentos, 'materia'):
                arquivos_existentes = safe_check_files_batch(
                    portal.sapl_documentos.materia,
                    nomes_materias
                )
        except Exception:
            pass
        
        # OTIMIZAÇÃO: Coleta URLs primeiro, depois baixa em paralelo
        # Para cada matéria, tenta encontrar apenas um arquivo válido (prioriza texto_integral)
        itens_para_baixar = []
        materias_processadas = set()
        
        for doc_mat, materia, tipo_materia in materias_vinculadas:
            # Evita processar a mesma matéria duas vezes
            materia_id = materia.cod_materia
            if materia_id in materias_processadas:
                continue
            
            # Verifica sufixo mais provável primeiro (_texto_integral.pdf antes de _redacao_final.pdf)
            for sufixo in sufixos:
                nome_materia = f"{materia.cod_materia}{sufixo}"
                
                # Verifica se arquivo existe (verificação em lote)
                if arquivos_existentes.get(nome_materia, False):
                    materia_path_rel = f"sapl_documentos/materia/{nome_materia}"
                    materia_path_abs = os.path.join(dir_base, nome_materia)
                    
                    itens_para_baixar.append({
                        'url': f"{portal_url.rstrip('/')}/{materia_path_rel}",
                        'path': materia_path_abs,
                        'filename': nome_materia,
                        'doc_mat': doc_mat,
                        'materia': materia,
                        'tipo_materia': tipo_materia,
                        'sufixo': sufixo
                    })
                    materias_processadas.add(materia_id)
                    break  # Para na primeira encontrada para cada matéria
        
        # OTIMIZAÇÃO: Downloads paralelos
        if itens_para_baixar:
            max_workers = min(4, len(itens_para_baixar))
            
            def _baixar_item(item):
                """Worker para download de um item"""
                try:
                    # Extrai caminho relativo da URL completa
                    caminho_rel = item['url'].replace(portal_url.rstrip('/'), '').lstrip('/')
                    if self._baixar_arquivo_via_http_local(portal_url, caminho_rel, item['path']):
                        return item
                except Exception:
                    pass
                return None
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_baixar_item, item): item for item in itens_para_baixar}
                
                for future in futures:
                    try:
                        item = future.result(timeout=300)
                        if item:
                            materia = item['materia']
                            tipo_materia = item['tipo_materia']
                            nome_materia = item['filename']
                            documentos.append({
                                "data": dat_documento,
                                'path': dir_base,
                                'file': nome_materia,
                                'title': f"{tipo_materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica} (mat. vinculada)",
                                'filesystem': True
                            })
                    except Exception as e:
                        item = futures[future]
                        logger.warning(f"[ProcessoAdmView._coletar_materias_vinculadas] Erro ao baixar matéria vinculada '{item['filename']}': {e}")
        
        return documentos
    
    def coletar_documentos(self, dados_documento: Dict, dir_base: str) -> List[Dict]:
        """
        Coleta todos os documentos do processo administrativo usando SQLAlchemy do Zope.
        
        OTIMIZAÇÃO: Refatorado em métodos auxiliares menores.
        Usa cache de dados do documento, verificação em lote e downloads paralelos.
        
        Este método usa a sessão SQLAlchemy do Zope (disponível no contexto da view)
        para acessar o banco de dados e coletar todos os documentos necessários.
        
        Args:
            dados_documento: Dicionário com dados do documento (retornado por obter_dados_documento)
            dir_base: Diretório base onde salvar arquivos
            
        Returns:
            Lista de dicionários com informações dos documentos coletados
        """
        documentos = []
        
        try:
            # Obtém portal_url
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            portal_url = str(portal.absolute_url())
            
            # Obtém cod_documento dos dados
            cod_documento = dados_documento.get('cod_documento')
            if not cod_documento:
                raise ValueError("cod_documento não encontrado em dados_documento")
            
            # OTIMIZAÇÃO: Usa dados já cacheados em vez de fazer nova query
            tipo = dados_documento.get('tipo', 'DOC')
            numero = dados_documento.get('numero', 0)
            ano = dados_documento.get('ano', 2025)
            dat_documento = dados_documento.get('data_documento', '')
            tipo_doc_des = dados_documento.get('descricao', '')
            
            if not dat_documento:
                dat_documento = datetime.now().strftime('%Y-%m-%d 00:00:00')
            
            # OTIMIZAÇÃO: Reutiliza sessão SQLAlchemy (não cria nova)
            session = self._get_session()
            
            try:
                # 1. Coletar capa (SEMPRE GERADA)
                capa_doc = self._coletar_capa(cod_documento, portal_url, dir_base, dat_documento, tipo, numero, ano)
                if capa_doc:
                    documentos.append(capa_doc)
                
                # 2. Coletar texto integral
                texto_doc = self._coletar_texto_integral(cod_documento, portal_url, portal, dir_base, dat_documento, tipo_doc_des, numero, ano)
                if texto_doc:
                    documentos.append(texto_doc)
                
                # 3. Coletar documentos acessórios (com verificação em lote e downloads paralelos)
                documentos.extend(self._coletar_documentos_acessorios(session, cod_documento, portal_url, portal, dir_base, dat_documento))
                
                # 4. Coletar tramitações (com verificação em lote e downloads paralelos)
                documentos.extend(self._coletar_tramitacoes(session, cod_documento, portal_url, portal, dir_base, dat_documento))
                
                # 5. Coletar matérias vinculadas (com otimização de sufixo)
                documentos.extend(self._coletar_materias_vinculadas(session, cod_documento, portal_url, portal, dir_base, dat_documento))
                
                # 6. Gerar folha de cientificações (se houver)
                try:
                    dados_cient = coletar_cientificacoes_com_nomes(session, cod_documento, somente_pendentes=False)
                    if dados_cient:
                        folha_nome = "folha_cientificacoes.pdf"
                        folha_caminho = os.path.join(dir_base, folha_nome)
                        
                        # Obtém nome da casa e logo do portal
                        nome_casa, logo_bytes = _obter_info_casa_do_portal(portal)
                        
                        gerar_folha_cientificacao_pdf(
                            session, portal_url, cod_documento, folha_caminho, dados_cient,
                            nome_casa=nome_casa, logo_bytes=logo_bytes
                        )
                        
                        # Obtém tamanho do arquivo gerado para incluir nos metadados
                        folha_size = 0
                        if os.path.exists(folha_caminho):
                            folha_size = os.path.getsize(folha_caminho)
                        
                        # CRÍTICO: Inclui count (número de cientificações) e file_size nos metadados
                        # Isso permite que a comparação detecte mudanças reais no número de cientificações
                        # e ignore variações pequenas de tamanho (dentro da tolerância)
                        documentos.append({
                            "data": "9999-12-31 23:59:59",
                            "path": dir_base,
                            "file": folha_nome,
                            "title": "Folha de Cientificações",
                            "filesystem": True,
                            "count": len(dados_cient),  # Número de cientificações
                            "file_size": folha_size  # Tamanho do arquivo gerado
                        })
                except Exception as e:
                    logger.warning(f"[ProcessoAdmView.coletar_documentos] Erro ao gerar folha de cientificações: {e}")
                
                # 7. Ordenar documentos: Capa sempre primeira, Texto integral sempre segundo, resto por data
                # Nota: processo_adm não tem redação final, apenas processo_leg
                # CRÍTICO: Apenas o texto integral do próprio processo (com cod_documento) deve ser priorizado
                # Não priorizar textos integrais de documentos/matérias vinculadas
                def ordenar_documentos(doc):
                    title = doc.get('title', '').lower()
                    file = doc.get('file', '').lower() if doc.get('file') else ''
                    
                    # Capa do Processo sempre primeira (prioridade 0) - verifica título
                    if 'capa do processo' in title or 'capa' in title:
                        return (0, doc.get('data', ''))
                    
                    # Texto integral do próprio processo sempre segundo (prioridade 1) - verifica nome do arquivo
                    # Nome do arquivo: {cod_documento}_texto_integral.pdf (ex: 79431_texto_integral.pdf)
                    if file:
                        # Verifica se o arquivo é exatamente {cod_documento}_texto_integral.pdf do próprio processo
                        texto_integral_esperado = f"{cod_documento}_texto_integral.pdf"
                        if file == texto_integral_esperado.lower() or file.endswith(f"{cod_documento}_texto_integral.pdf"):
                            return (1, doc.get('data', ''))
                    
                    # Resto ordenado por data (prioridade 2)
                    return (2, doc.get('data', ''))
                
                documentos.sort(key=ordenar_documentos)
                return documentos
                
            finally:
                # OTIMIZAÇÃO: Não fecha sessão aqui - será fechada no final da requisição
                # Mantém sessão aberta para reutilização
                pass
                
        except Exception as e:
            logger.error(f"[ProcessoAdmView.coletar_documentos] Erro ao coletar documentos: {e}", exc_info=True)
            raise PDFGenerationError(f"Falha ao coletar documentos: {str(e)}")
    
    def render(self):
        """
        Método render - APENAS para verificação de documentos prontos (com skip_signature_check).
        
        Geração síncrona de PDF foi removida. Use sempre o modo assíncrono (Celery task).
        """
        try:
            if not hasattr(self, 'cod_documento') or not self.cod_documento:
                cod_documento = self.request.form.get('cod_documento')
                if not cod_documento:
                    raise ValueError("O parâmetro cod_documento é obrigatório")
                try:
                    cod_documento = int(cod_documento)
                except (ValueError, TypeError):
                    raise ValueError("cod_documento deve ser um número")
            else:
                try:
                    cod_documento = int(self.cod_documento)
                except (ValueError, TypeError):
                    raise ValueError("cod_documento deve ser um número")
            
            # CRÍTICO: Se action é 'download', faz download do PDF final
            action = getattr(self, 'action', self.request.form.get('action', 'pasta'))
            if action == 'download':
                try:
                    # Obtém dados do documento para construir o nome do arquivo
                    dados_documento = self.obter_dados_documento(cod_documento)
                    
                    # CRÍTICO: Constrói o nome do arquivo da mesma forma que a task (com hífen)
                    # Formato: PA-308-2025.pdf (não PA_308_2025.pdf)
                    nome_arquivo_download = f"{dados_documento['tipo']}-{dados_documento['numero']}-{dados_documento['ano']}.pdf"
                    
                    # Verifica se há PDF final gerado
                    dir_base = get_processo_dir_adm(cod_documento)
                    
                    # PRIORIDADE 1: Tenta ler do metadados (nome correto do arquivo gerado)
                    nome_arquivo_final = None
                    metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                    if os.path.exists(metadados_path):
                        try:
                            with open(metadados_path, 'r', encoding='utf-8') as f:
                                metadados = json.load(f)
                            # O campo arquivo_final contém o nome do arquivo gerado
                            nome_arquivo_final = metadados.get('arquivo_final')
                        except Exception:
                            pass
                    
                    # PRIORIDADE 2: Se não encontrou nos metadados, usa o nome construído (formato com hífen)
                    if not nome_arquivo_final:
                        nome_arquivo_final = nome_arquivo_download
                    
                    caminho_arquivo_final = os.path.join(dir_base, nome_arquivo_final)
                    
                    # PRIORIDADE 3: Se ainda não encontrou, tenta variações do nome
                    if not os.path.exists(caminho_arquivo_final):
                        # Tenta formato antigo (underscore) para compatibilidade
                        nome_arquivo_alt = f"{dados_documento['tipo']}_{dados_documento['numero']}_{dados_documento['ano']}.pdf"
                        caminho_arquivo_alt = os.path.join(dir_base, nome_arquivo_alt)
                        if os.path.exists(caminho_arquivo_alt):
                            nome_arquivo_final = nome_arquivo_alt
                            caminho_arquivo_final = caminho_arquivo_alt
                        else:
                            # Tenta formato antigo (processo_adm_integral_{cod})
                            nome_arquivo_alt2 = f"processo_adm_integral_{cod_documento}.pdf"
                            caminho_arquivo_alt2 = os.path.join(dir_base, nome_arquivo_alt2)
                            if os.path.exists(caminho_arquivo_alt2):
                                nome_arquivo_final = nome_arquivo_alt2
                                caminho_arquivo_final = caminho_arquivo_alt2
                    
                    if os.path.exists(caminho_arquivo_final):
                        # Lê o arquivo e retorna como download
                        with open(caminho_arquivo_final, 'rb') as f:
                            pdf_data = f.read()
                        
                        # Configura headers para abrir PDF em nova aba (inline ao invés de attachment)
                        # Usa o nome formatado baseado nos dados do documento (com hífen)
                        self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
                        self.request.RESPONSE.setHeader(
                            'Content-Disposition',
                            f'inline; filename="{nome_arquivo_download}"'
                        )
                        self.request.RESPONSE.setHeader('Content-Length', str(len(pdf_data)))
                        
                        return pdf_data
                    else:
                        # Arquivo não encontrado - lista arquivos disponíveis para debug
                        arquivos_disponiveis = []
                        try:
                            if os.path.exists(dir_base):
                                arquivos_disponiveis = [f for f in os.listdir(dir_base) if f.endswith('.pdf') and os.path.isfile(os.path.join(dir_base, f))]
                        except Exception:
                            pass
                        
                        error_msg = f"Arquivo não encontrado: {nome_arquivo_download}. O processo ainda não foi gerado."
                        logger.warning(f"[ProcessoAdmView] Arquivo não encontrado para download: {caminho_arquivo_final}")
                        logger.warning(f"[ProcessoAdmView] Arquivos PDF disponíveis no diretório: {arquivos_disponiveis}")
                        self.request.RESPONSE.setStatus(404)
                        self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
                        return error_msg
                        
                except Exception as download_err:
                    logger.error(f"[ProcessoAdmView] Erro ao fazer download: {download_err}", exc_info=True)
                    self.request.RESPONSE.setStatus(500)
                    self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
                    return f"Erro ao fazer download: {str(download_err)}"
            
            # CRÍTICO: Esta view APENAS verifica documentos prontos quando skip_signature_check está presente
            # Geração síncrona foi removida - sempre use o modo assíncrono (Celery task)
            skip_signature_check = self.request.form.get('skip_signature_check') == '1'
            
            if not skip_signature_check:
                # Modo síncrono não é mais suportado
                error_msg = "Geração síncrona de PDF não é mais suportada. Use sempre o modo assíncrono (Celery task)."
                logger.warning(f"[ProcessoAdmView] Tentativa de geração síncrona rejeitada para cod_documento={cod_documento}")
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'error': error_msg,
                    'success': False,
                    'cod_documento': cod_documento
                })
            
            # Apenas verifica documentos prontos (não gera novos)
            try:
                # Verifica se há documentos prontos sem regenerar
                dados_documento = self.obter_dados_documento(cod_documento)
                dir_base = get_processo_dir_adm(cod_documento)
                
                # CRÍTICO: Verifica se o diretório base existe antes de tentar acessar subdiretórios
                if not os.path.exists(dir_base):
                    result = {
                        'documentos': [],
                        'total_paginas': 0,
                        'cod_documento': cod_documento
                    }
                    if action == 'json':
                        self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                        return json.dumps(result)
                    return result
                
                dir_paginas = secure_path_join(dir_base, 'pages')
                metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
                
                # Se há metadados e páginas, carrega documentos prontos
                # CRÍTICO: Se skip_signature_check está presente, adiciona um pequeno delay
                # para garantir que os arquivos foram completamente salvos no disco
                if skip_signature_check:
                    time.sleep(0.5)
                
                # Verifica estado inicial
                metadados_existe = os.path.exists(metadados_path)
                dir_paginas_existe = os.path.exists(dir_paginas)
                
                if metadados_existe and dir_paginas_existe:
                    # Carrega metadados
                    with open(metadados_path, 'r', encoding='utf-8') as f:
                        metadados = json.load(f)
                    
                    documentos = metadados.get('documentos', [])
                    total_paginas = metadados.get('total_paginas', 0)
                    
                    # Verifica se todos os arquivos de páginas existem
                    documentos_validos = []
                    for doc in documentos:
                        start_page = doc.get('start_page', 1)
                        end_page = doc.get('end_page', 1)
                        
                        # Verifica se todas as páginas existem
                        todas_paginas_existem = True
                        for page_num in range(start_page, end_page + 1):
                            pagina_path = os.path.join(dir_paginas, f'{page_num}.pdf')
                            if not os.path.exists(pagina_path):
                                todas_paginas_existem = False
                                break
                        
                        if todas_paginas_existem:
                            documentos_validos.append(doc)
                    
                    if len(documentos_validos) == len(documentos):
                        # Todos os documentos estão prontos
                        result = {
                            'documentos': documentos_validos,
                            'total_paginas': total_paginas,
                            'cod_documento': cod_documento,
                            'status': 'ready'
                        }
                        if action == 'json':
                            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                            return json.dumps(result)
                        return result
                
                # Documentos não estão prontos
                result = {
                    'documentos': [],
                    'total_paginas': 0,
                    'cod_documento': cod_documento,
                    'status': 'pending'
                }
                if action == 'json':
                    self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                    return json.dumps(result)
                return result
                
            except Exception as check_err:
                logger.error(f"[ProcessoAdmView] Erro ao verificar documentos prontos: {check_err}", exc_info=True)
                error_result = {
                    'error': str(check_err),
                    'documentos': [],
                    'total_paginas': 0,
                    'cod_documento': cod_documento,
                    'status': 'error'
                }
                if action == 'json':
                    self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                    return json.dumps(error_result)
                return error_result
            
        except Exception as e:
            logger.error(f"[ProcessoAdmView] Erro: {e}", exc_info=True)
            error_result = {
                'error': str(e),
                'success': False,
                'cod_documento': getattr(self, 'cod_documento', None)
            }
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps(error_result)


class PaginaProcessoAdmView(grok.View):
    """View para servir páginas individuais do PDF"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_adm_integral')
    
    @property
    def temp_base(self) -> str:
        """Diretório base temporário seguro"""
        install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
        return secure_path_join(install_home, 'var/tmp')
    
    def render(self):
        """Renderiza uma página individual do processo administrativo"""
        # Obtém parâmetros do request
        try:
            cod_documento = self.request.form.get('cod_documento', '')
            pagina = self.request.form.get('pagina', '')
        except (AttributeError, KeyError):
            # Fallback: tenta acessar diretamente
            try:
                cod_documento = getattr(self.request, 'cod_documento', '')
                pagina = getattr(self.request, 'pagina', '')
            except AttributeError:
                cod_documento = ''
                pagina = ''
        
        # Remove espaços e converte para string
        if cod_documento:
            cod_documento = str(cod_documento).strip()
        if pagina:
            pagina = str(pagina).strip()
        
        if not cod_documento:
            logger.error("[PaginaProcessoAdmView] cod_documento não fornecido")
            self.request.RESPONSE.setStatus(400)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return "Parâmetro cod_documento é obrigatório"
        
        if not pagina:
            logger.error("[PaginaProcessoAdmView] pagina não fornecida")
            self.request.RESPONSE.setStatus(400)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return "Parâmetro pagina é obrigatório"
        
        file_path = None
        try:
            # Converte cod_documento para int
            try:
                cod_documento_int = int(cod_documento)
            except (ValueError, TypeError):
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
                return "Parâmetro cod_documento deve ser um número"
            
            # Obtém diretório do processo
            dir_base = get_processo_dir_adm(cod_documento_int)
            dir_pages = secure_path_join(dir_base, 'pages')
            file_path = secure_path_join(dir_pages, pagina)
            
            # Verifica se o arquivo existe
            if not os.path.exists(file_path):
                # Tenta variações do nome do arquivo
                if pagina.startswith('pg_') and '_' in pagina:
                    try:
                        num_str = pagina.replace('pg_', '').replace('.pdf', '')
                        num = int(num_str)
                        # Tenta sem zero padding
                        pagina_alt = f'pg_{num}.pdf'
                        file_path_alt = secure_path_join(dir_pages, pagina_alt)
                        if os.path.exists(file_path_alt):
                            file_path = file_path_alt
                        else:
                            # Tenta formato numérico simples
                            pagina_alt2 = f'{num}.pdf'
                            file_path_alt2 = secure_path_join(dir_pages, pagina_alt2)
                            if os.path.exists(file_path_alt2):
                                file_path = file_path_alt2
                    except (ValueError, TypeError):
                        pass
            
            if not os.path.exists(file_path):
                logger.error(f"[PaginaProcessoAdmView] Arquivo não encontrado: {file_path or pagina}")
                self.request.RESPONSE.setStatus(404)
                self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
                return "Página não encontrada"
            
            # Retorna PDF
            with open(file_path, 'rb') as f:
                data = f.read()
            
            self.request.RESPONSE.setHeader('Content-Type', 'application/pdf')
            self.request.RESPONSE.setHeader('Content-Disposition', f'inline; filename="{pagina}"')
            self.request.RESPONSE.setHeader('Content-Length', str(len(data)))
            # Evita cache para garantir sempre a versão mais recente
            self.request.RESPONSE.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.request.RESPONSE.setHeader('Pragma', 'no-cache')
            self.request.RESPONSE.setHeader('Expires', '0')
            
            return data
            
        except SecurityError as se:
            error_msg = str(se)
            logger.error(f"[PaginaProcessoAdmView] Erro de segurança ao acessar: {file_path or pagina} - {se}")
            # Verifica se o erro é "Base path does not exist" - indica que precisa regenerar pasta
            if "Base path does not exist" in error_msg:
                # Retorna status 404 com header especial indicando que precisa regenerar
                self.request.RESPONSE.setStatus(404)
                self.request.RESPONSE.setHeader('X-Pasta-Regenerate', 'true')
                self.request.RESPONSE.setHeader('X-Pasta-Cod-Documento', str(cod_documento))
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                import json
                return json.dumps({
                    'error': 'Base path does not exist',
                    'regenerate': True,
                    'cod_documento': str(cod_documento)
                }, ensure_ascii=False)
            # Outros erros de segurança retornam 403
            self.request.RESPONSE.setStatus(403)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return "Acesso não permitido"
        except FileNotFoundError:
            logger.error(f"[PaginaProcessoAdmView] Arquivo não encontrado: {file_path or pagina}")
            self.request.RESPONSE.setStatus(404)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return "Página não encontrada"
        except Exception as e:
            logger.error(f"[PaginaProcessoAdmView] Erro inesperado: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'text/plain; charset=utf-8')
            return f"Erro ao carregar página: {str(e)}"


class ProcessoAdmStatusView(grok.View):
    """View para verificar status da task de geração"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_status')
    
    def render(self):
        """Retorna status da task"""
        try:
            task_id = self.request.form.get('task_id')
            if not task_id:
                return json.dumps({'error': 'task_id não fornecido'})
            
            service = ProcessoAdmService(self.context, self.request)
            status = service.verificar_task_status(task_id)
            
            if status:
                return json.dumps(status)
            else:
                return json.dumps({'status': 'UNKNOWN', 'error': 'Task não encontrada'})
                
        except Exception as e:
            logger.error(f"[ProcessoAdmStatusView] Erro: {e}", exc_info=True)
            return json.dumps({'error': str(e)})


class ProcessoAdmAsyncView(grok.View):
    """View para iniciar geração assíncrona"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_async')
    
    def render(self):
        """Inicia task assíncrona"""
        try:
            cod_documento = self.request.form.get('cod_documento')
            if not cod_documento:
                return json.dumps({'error': 'cod_documento não fornecido'})
            
            try:
                cod_documento = int(cod_documento)
            except (ValueError, TypeError):
                return json.dumps({'error': 'cod_documento inválido'})
            
            # Verifica permissão
            from openlegis.sagl.browser.processo_adm.pasta_digital import verificar_permissao_acesso
            user = self.request.get('AUTHENTICATED_USER')
            if not user:
                return json.dumps({'error': 'Usuário não autenticado'})
            
            can_view, _ = verificar_permissao_acesso(self.context, cod_documento, user)
            if not can_view:
                return json.dumps({'error': 'Acesso não autorizado'})
            
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            portal_url = str(portal.absolute_url())
            
            service = ProcessoAdmService(self.context, self.request)
            result = service.criar_task_async(cod_documento, portal_url)
            
            if result:
                return json.dumps(result)
            else:
                return json.dumps({'error': 'Falha ao criar task'})
                
        except Exception as e:
            logger.error(f"[ProcessoAdmAsyncView] Erro: {e}", exc_info=True)
            return json.dumps({'error': str(e)})


class ProcessoAdmCancelView(grok.View):
    """View para cancelar task"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_cancel')
    
    def render(self):
        """Cancela task"""
        try:
            task_id = self.request.form.get('task_id')
            if not task_id:
                return json.dumps({'error': 'task_id não fornecido'})
            
            # TODO: Implementar cancelamento de task Celery
            return json.dumps({'status': 'cancelled', 'task_id': task_id})
            
        except Exception as e:
            logger.error(f"[ProcessoAdmCancelView] Erro: {e}", exc_info=True)
            return json.dumps({'error': str(e)})


class LimparProcessoAdmView(grok.View):
    """View para limpar arquivos temporários"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_limpar')
    
    def render(self, cod_documento=None):
        """Limpa arquivos temporários"""
        try:
            # Obtém cod_documento do parâmetro ou do form
            if not cod_documento:
                cod_documento = self.request.form.get('cod_documento')
            
            if not cod_documento:
                self.request.RESPONSE.setStatus(400)
                return json.dumps({'error': 'cod_documento não fornecido'})
            
            try:
                cod_documento = int(cod_documento)
            except (ValueError, TypeError):
                self.request.RESPONSE.setStatus(400)
                return json.dumps({'error': 'cod_documento inválido'})
            
            # Verifica permissão (apenas admins)
            user = self.request.get('AUTHENTICATED_USER')
            if not user or not user.has_role(['Manager', 'Operador']):
                self.request.RESPONSE.setStatus(403)
                return json.dumps({'error': 'Acesso não autorizado'})
            
            # Validação de segurança - verifica se o diretório está no caminho permitido
            install_home = os.environ.get('INSTALL_HOME', tempfile.gettempdir())
            temp_base = os.path.abspath(os.path.join(install_home, 'var/tmp'))
            dir_base = get_processo_dir_adm(cod_documento)
            
            if not os.path.abspath(dir_base).startswith(temp_base):
                raise SecurityError("Tentativa de acesso a caminho não permitido")
            
            if os.path.exists(dir_base):
                import shutil
                shutil.rmtree(dir_base)
                return json.dumps({'status': 'cleaned', 'cod_documento': cod_documento})
            else:
                return json.dumps({'status': 'not_found', 'cod_documento': cod_documento})
                
        except SecurityError as e:
            logger.error(f"[LimparProcessoAdmView] Erro de segurança: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(403)
            return json.dumps({'error': 'Acesso não permitido'})
        except Exception as e:
            logger.error(f"[LimparProcessoAdmView] Erro: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return json.dumps({'error': str(e)})


class ProcessoAdmTaskExecutor(grok.View):
    """View chamada pela task Celery para coletar documentos"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_task_executor')
    
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
            logger.debug(f"[_baixar_documento_via_http_com_retry] Arquivo '{filename}' já existe, usando cache: {caminho_saida}")
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
                    logger.warning(f"[_baixar_documento_via_http_com_retry] Download de '{filename}' retornou dados vazios")
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Backoff exponencial
                        logger.debug(f"[_baixar_documento_via_http_com_retry] Tentando novamente em {delay}s (tentativa {attempt + 1}/{max_retries})...")
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
        Executa a geração do processo administrativo.
        
        Aceita POST ou GET com parâmetros:
        - cod_documento: Código do documento (obrigatório)
        - portal_url: URL base do portal (opcional)
        - user_id: ID do usuário (opcional)
        """
        try:
            # Obtém parâmetros da requisição
            cod_documento = self.request.form.get('cod_documento') or self.request.get('cod_documento')
            
            # Valida parâmetros obrigatórios
            if not cod_documento:
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': 'Parâmetro cod_documento é obrigatório', 'success': False})
            
            # Converte cod_documento para int se for string
            try:
                cod_documento = int(cod_documento)
            except (ValueError, TypeError):
                self.request.RESPONSE.setStatus(400)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({'error': 'cod_documento deve ser um número', 'success': False})
            
            # Obtém portal_url se não fornecido
            portal_url = self.request.form.get('portal_url') or self.request.get('portal_url')
            if not portal_url:
                portal = getToolByName(self.context, 'portal_url').getPortalObject()
                portal_url = str(portal.absolute_url())
            
            # Cria instância da view ProcessoAdmView no contexto do Zope
            view = ProcessoAdmView(self.context, self.request)
            view.update()
            
            # Executa apenas o download dos arquivos (processamento pesado será feito na task Celery)
            try:
                # Tenta importar exceções do Zope para tratamento explícito
                try:
                    from zExceptions import NotFound as ZopeNotFound
                    NotFound_available = True
                except ImportError:
                    NotFound_available = False
                    ZopeNotFound = None
                
                # Etapa 1: Obter dados do documento
                dados_documento = view.obter_dados_documento(cod_documento)
                
                # Etapa 2: Preparar diretórios
                dir_base, dir_paginas = view.preparar_diretorios(cod_documento)
                
                # Etapa 3: Coletar documentos (completo - usando SQLAlchemy do Zope)
                # Trata exceções NotFound/KeyError do Zope que podem ocorrer durante o download
                try:
                    documentos = view.coletar_documentos(dados_documento, dir_base)
                except (ZopeNotFound, KeyError) as e:
                    # Se for NotFound/KeyError do Zope durante a coleta, trata como erro não fatal
                    # Continua com documentos que foram coletados até o momento
                    logger.warning(f"[ProcessoAdmTaskExecutor] Erro NotFound/KeyError durante coleta de documentos: {e}")
                    documentos = []
                except Exception as e:
                    # Verifica se é uma exceção NotFound/KeyError do Zope
                    error_type = type(e).__name__
                    error_msg = str(e).lower()
                    
                    if (NotFound_available and isinstance(e, ZopeNotFound)) or \
                       'notfound' in error_type.lower() or \
                       'keyerror' in error_type.lower() or \
                       'cannot locate' in error_msg or \
                       'not found' in error_msg:
                        logger.warning(f"[ProcessoAdmTaskExecutor] Erro NotFound/KeyError durante coleta de documentos: {e}")
                        documentos = []
                    else:
                        # Para outros erros, propaga
                        raise
                
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
                                    logger.debug(f"[ProcessoAdmTaskExecutor] Documento '{doc_baixado.get('file', '?')}' baixado com sucesso")
                            except Exception as e:
                                doc_original = futures[future]
                                logger.warning(f"[ProcessoAdmTaskExecutor] Erro ao baixar documento '{doc_original.get('file', '?')}': {e}")
                
                
                # Prepara dados para retornar (apenas informações, não processa)
                id_processo = dados_documento.get('id_exibicao', '')
                
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
                
                # Converte dados_documento: apenas campos serializáveis
                dados_documento_serializavel = {}
                for key, value in dados_documento.items():
                    try:
                        json.dumps(value, default=default_serializer)
                        dados_documento_serializavel[key] = value
                    except (TypeError, ValueError):
                        converted = default_serializer(value)
                        if converted is not None:
                            dados_documento_serializavel[key] = converted
                
                # Retorna informações para que a task Celery faça o processamento pesado
                self.request.RESPONSE.setStatus(200)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'success': True,
                    'cod_documento': cod_documento,
                    'dir_base': dir_base,
                    'dir_paginas': dir_paginas,
                    'id_processo': id_processo,
                    'documentos': documentos_serializaveis,
                    'dados_documento': dados_documento_serializavel
                }, default=default_serializer)
                
            except Exception as gen_err:
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[ProcessoAdmTaskExecutor] Erro ao gerar processo: {gen_err}", exc_info=True)
                logger.error(f"[ProcessoAdmTaskExecutor] Traceback completo:\n{error_traceback}")
                self.request.RESPONSE.setStatus(500)
                self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
                return json.dumps({
                    'success': False,
                    'error': str(gen_err),
                    'error_type': type(gen_err).__name__,
                    'traceback': error_traceback,
                    'cod_documento': cod_documento,
                })
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"[ProcessoAdmTaskExecutor] Erro inesperado: {e}", exc_info=True)
            logger.error(f"[ProcessoAdmTaskExecutor] Traceback completo:\n{error_traceback}")
            self.request.RESPONSE.setStatus(500)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({
                'error': str(e),
                'error_type': type(e).__name__,
                'success': False,
                'traceback': error_traceback
            })
