# -*- coding: utf-8 -*-
import gc
import re
import logging
import warnings
import tempfile
import os
import shutil
import time
import traceback
import hashlib
from io import BytesIO
from PIL import Image, ImageFilter
from typing import Any, List, Optional, Dict, Union, BinaryIO, Iterator, Generator, Tuple
from functools import lru_cache, wraps
from contextlib import contextmanager
from datetime import datetime, timedelta

import fitz
import pikepdf
import ocrmypdf
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from asn1crypto import cms
from dateutil.parser import parse

# Se usar com Zope/Plone:
from five import grok
from zope.interface import Interface
from openlegis.sagl import get_base_path

# ******************************************
# CONSTANTS AND CONFIGURATION
# ******************************************
CPF_LENGTH = 11
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
MAX_PDF_SIZE = 100 * 1024 * 1024 # 100MB
MAX_PAGES = 2000
PNG_COMPRESSION_LEVEL = 9 # Máxima compressão PNG
A4_PORTRAIT = (595, 842)
A4_LANDSCAPE = (842, 595)
A4_TOLERANCE = 0.02 # 2% tolerance for page size

# AJUSTES DE QUALIDADE 
TEXT_DPI = 200       
IMAGE_DPI = 150       # REDUZIDO de 200 para 150 para melhor compressão

MAX_IMAGE_SIZE = 1600 # REDUZIDO de 2400 para 1600
# QUALIDADE JPEG BASE 
JPEG_QUALITY = 85     # REDUZIDO de 92 para 85 para melhor compressão
FALLBACK_JPEG_QUALITY = 90 # REDUZIDO de 95 para 90

# === CONFIGURAÇÃO DE OCR ===
ENABLE_OCR = True       # Mude para False para desativar completamente o OCR.
OCR_FALLBACK_ONLY = True # Alterado para True: só aplica OCR quando otimização falha
OCR_FORCE_ENABLED = False # Se True, força OCR mesmo que o PDF já tenha texto pesquisável.
# ===========================

PDFData = Union[bytes, bytearray]
SignatureData = Dict[str, Any]
SignerInfo = Dict[str, Optional[str]]

# CONFIGURAÇÃO DE LOGGING
def setup_logging():
    """Configura o logging de forma segura sem resource leaks"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove handlers existentes para evitar duplicação
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Formatter comum
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    # FileHandler com fechamento seguro
    try:
        base_path = get_base_path()
        log_path = os.path.join(base_path, 'pdf_processor.log')
        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Erro ao criar file handler: {e}")
    
    # StreamHandler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Inicializa o logging
setup_logging()

# Silence some noisy loggers
logging.getLogger('ocrmypdf').setLevel(logging.WARNING)
logging.getLogger('pikepdf').setLevel(logging.WARNING)
logging.getLogger('pypdf').setLevel(logging.WARNING)

# ******************************************
# EXCEPTIONS
# ******************************************
class PDFIrrecuperavelError(Exception):
    pass

class PDFSizeExceededError(Exception):
    pass

class PDFPageLimitExceededError(Exception):
    pass

# ******************************************
# CORE UTILITIES
# ******************************************
def timed_lru_cache(seconds: int = 600, maxsize: int = 32):
    def wrapper_cache(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = timedelta(seconds=seconds)
        func.expiration = datetime.now() + func.lifetime

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if datetime.now() >= func.expiration:
                func.cache_clear()
                func.expiration = datetime.now() + func.lifetime
            return func(*args, **kwargs)
        return wrapped_func
    return wrapper_cache

def format_cpf(cpf: Optional[str]) -> str:
    if not cpf or not isinstance(cpf, str):
        return ""
    cleaned = re.sub(r'[^0-9]', '', cpf)
    if len(cleaned) != CPF_LENGTH:
        return ""
    return f"{cleaned[:3]}.{cleaned[3:6]}.{cleaned[6:9]}-{cleaned[9:]}"

def format_datetime(dt: Optional[Any]) -> Optional[str]:
    if not dt:
        return None
    try:
        return dt.strftime(DATE_FORMAT)
    except Exception:
        return None

def validate_pdf_size(pdf_data: bytes) -> None:
    if len(pdf_data) > MAX_PDF_SIZE:
        raise PDFSizeExceededError(
            f"O arquivo PDF excede o tamanho máximo de {MAX_PDF_SIZE/1024/1024}MB"
        )

def calculate_compression_rate(original_size: int, compressed_size: int) -> float:
    """Calcula a taxa de compressão em porcentagem"""
    if original_size == 0:
        return 0.0
    return ((original_size - compressed_size) / original_size) * 100

# ******************************************
# PDF PROCESSOR CORE
# ******************************************
class PDFProcessor:
    def __init__(self):
        self._cached_pdf_reader = None
        self._cached_pdf_stream = None
        self._memory_threshold = 100 * 1024 * 1024 # 100MB
        self.text_dpi = TEXT_DPI
        self.image_dpi = IMAGE_DPI
        self.max_image_size = MAX_IMAGE_SIZE
        self.jpeg_quality = JPEG_QUALITY
        self.fallback_jpeg_quality = FALLBACK_JPEG_QUALITY
        self.png_compression = PNG_COMPRESSION_LEVEL
        self._processing_cache = {} # Cache para evitar reprocessamento em retry

        # === NOVAS CONFIGURAÇÕES DE OCR ===
        self.enable_ocr = ENABLE_OCR
        self.ocr_fallback_only = OCR_FALLBACK_ONLY
        self.ocr_force_enabled = OCR_FORCE_ENABLED
        # ==================================

    def _safe_update_progress(self, stage: str, message: str, progress: int = None, details: str = ""):
        """
        Método auxiliar que tenta atualizar progresso se o método estiver disponível.
        Usado por métodos da classe base que não têm acesso direto ao request.
        """
        if hasattr(self, '_update_progress'):
            try:
                self._update_progress(stage, message, progress, details)
            except Exception as e:
                logging.debug(f"Erro ao chamar _update_progress: {e}")

    def _get_file_hash(self, pdf_data: bytes) -> str:
        """Gera hash do arquivo para cache"""
        return hashlib.md5(pdf_data[:1024*1024]).hexdigest() # Hash dos primeiros 1MB

    def _log_page_processing(self, page_num: int, action: str, processing_time: float = None, 
                           original_size: int = None, compressed_size: int = None, details: str = ""):
        log_data = {
            'page': page_num + 1,
            'action': action,
            'details': details,
        }
        if processing_time is not None:
            log_data['processing_time_ms'] = round(processing_time * 1000, 2)
        if original_size is not None:
            log_data['original_size_kb'] = round(original_size / 1024, 2)
            if compressed_size is not None:
                log_data['compressed_size_kb'] = round(compressed_size / 1024, 2)
                if original_size > 0:
                    compression_rate = calculate_compression_rate(original_size, compressed_size)
                    if abs(compression_rate) < 10000:
                        log_data['compression_rate'] = round(compression_rate, 2)
                    elif compressed_size > original_size:
                        ratio = compressed_size / original_size
                        log_data['size_increase'] = f"{ratio:.2f}x"
        logging.info(
            "Processamento de página - %s",
            ", ".join(f"{k}: {v}" for k, v in log_data.items()),
            extra={'log_data': log_data}
        )

    def _pagina_contem_texto_legivel(self, page) -> bool:
        """Verifica se a página contém texto legível de forma mais robusta"""
        try:
            texto = page.get_text().strip()
            return len(texto) >= 10 and any(c.isalnum() for c in texto)
        except Exception:
            return False

    def _documento_tem_texto_pesquisavel(self, doc: fitz.Document) -> bool:
        """
        Verifica se o documento tem texto pesquisável (OCR ou texto vetorial).
        """
        try:
            total_pages = doc.page_count
            if total_pages == 0:
                return False
            
            # Para documentos pequenos, verifica todas
            if total_pages <= 3:
                pages_to_check = list(range(total_pages))
            else:
                # Para documentos grandes, verifica amostra
                pages_to_check = [0, total_pages - 1]
                if total_pages > 5:
                    mid = total_pages // 2
                    pages_to_check.extend([mid - 1, mid, mid + 1])
                else:
                    pages_to_check.extend(range(1, total_pages - 1))
            
            for i in pages_to_check:
                try:
                    page = doc[i]
                    texto = page.get_text("text", flags=11).strip()
                    if len(texto) >= 10 and any(c.isalnum() for c in texto):
                        return True
                except:
                    continue
            
            return False
        except Exception:
            return False

    def _is_a4_size(self, width: float, height: float) -> bool:
        def is_close(a, b):
            return abs(a - b) <= max(a, b) * A4_TOLERANCE
        return (is_close(width, A4_PORTRAIT[0]) and is_close(height, A4_PORTRAIT[1])) or \
               (is_close(width, A4_LANDSCAPE[0]) and is_close(height, A4_LANDSCAPE[1]))

    def _resize_to_a4(self, page: fitz.Page) -> bytes:
        """Redimensiona UMA página para A4 e retorna bytes de PDF standalone"""
        original_width = page.rect.width
        original_height = page.rect.height
        is_landscape = original_width > original_height

        def is_a4_size(w, h):
            target = A4_LANDSCAPE if is_landscape else A4_PORTRAIT
            return (abs(w - target[0]) <= target[0] * 0.05 and
                    abs(h - target[1]) <= target[1] * 0.05)

        buf = BytesIO()
        with fitz.open() as tmp_doc:
            if is_a4_size(original_width, original_height):
                tmp_doc.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
            else:
                target_width, target_height = A4_LANDSCAPE if is_landscape else A4_PORTRAIT
                scale = min(target_width / original_width, target_height / original_height)
                new_width = original_width * scale
                new_height = original_height * scale
                x_offset = (target_width - new_width) / 2
                y_offset = (target_height - new_height) / 2
                new_page = tmp_doc.new_page(width=target_width, height=target_height)
                new_page.show_pdf_page(
                    fitz.Rect(x_offset, y_offset, x_offset + new_width, y_offset + new_height),
                    page.parent,
                    page.number
                )
            tmp_doc.save(buf, garbage=4, deflate=True, clean=True)
        return buf.getvalue()

    def _resize_document_to_a4(self, pdf_data: bytes) -> bytes:
        """
        Redimensiona todas as páginas do documento para A4 de forma otimizada.
        """
        with fitz.open(stream=pdf_data, filetype="pdf") as doc:
            orig_metadata = dict(doc.metadata or {})
            total_pages = doc.page_count
            
            with fitz.open() as new_doc:
                for i, page in enumerate(doc):
                    original_width = page.rect.width
                    original_height = page.rect.height
                    is_landscape = original_width > original_height
                    
                    target = A4_LANDSCAPE if is_landscape else A4_PORTRAIT
                    is_a4 = (abs(original_width - target[0]) <= target[0] * 0.05 and
                             abs(original_height - target[1]) <= target[1] * 0.05)
                    
                    if is_a4:
                        new_doc.insert_pdf(doc, from_page=i, to_page=i)
                    else:
                        target_width, target_height = target
                        scale = min(target_width / original_width, target_height / original_height)
                        new_width = original_width * scale
                        new_height = original_height * scale
                        x_offset = (target_width - new_width) / 2
                        y_offset = (target_height - new_height) / 2
                        
                        new_page = new_doc.new_page(width=target_width, height=target_height)
                        new_page.show_pdf_page(
                            fitz.Rect(x_offset, y_offset, x_offset + new_width, y_offset + new_height),
                            doc,
                            i
                        )
                
                new_doc.set_metadata(orig_metadata)
                output = BytesIO()
                new_doc.save(output, garbage=4, deflate=True, clean=True)
                return output.getvalue()

    def _get_page_content_size(self, page: fitz.Page) -> int:
        """
        Calcula o tamanho aproximado da página incluindo conteúdo vetorial e imagens embutidas.
        """
        try:
            content_size = len(page.read_contents() or b'')
            images = page.get_images()
            image_size = 0
            for img_idx in images:
                try:
                    xref = img_idx[0]
                    base_image = page.parent.extract_image(xref)
                    img_bytes = base_image.get("image", b"")
                    image_size += len(img_bytes)
                except:
                    continue
            return content_size + image_size
        except:
            return 0

    def _is_page_scanned(self, page: fitz.Page) -> bool:
        """Verifica se a página é uma imagem escaneada (não vetorial)"""
        try:
            images = page.get_images()
            text_blocks = page.get_text("blocks")
            texto = page.get_text().strip()
            
            if len(images) > 0:
                if len(texto) < 50 or len(text_blocks) < 3:
                    for img_idx in images:
                        try:
                            xref = img_idx[0]
                            base_image = page.parent.extract_image(xref)
                            img_bytes = base_image.get("image", b"")
                            if len(img_bytes) > 20000:
                                return True
                        except:
                            continue
            return False
        except:
            return False

    def _otimizacao_inteligente(self, doc: fitz.Document) -> Optional[bytes]:
        """
        Processamento inteligente com melhor detecção de conteúdo.
        CORREÇÃO: Evita conversão para imagem quando aumenta muito o tamanho.
        """
        total_pages = doc.page_count
        logging.info(f"Iniciando otimização inteligente para {total_pages} páginas")
        
        # Para documentos grandes (>100 páginas), faz verificação rápida
        if total_pages > 100:
            logging.info("Documento grande detectado, fazendo verificação rápida...")
            self._safe_update_progress(
                'optimizing',
                f'Analisando documento grande ({total_pages} páginas)...',
                52,
                f'Verificando amostra de páginas'
            )
            pages_to_check = min(10, total_pages)
            all_vectorial = True
            pages_with_large_images = 0
            
            for i in range(pages_to_check):
                try:
                    page = doc[i]
                    texto = page.get_text("text", flags=11).strip()
                    tem_texto = len(texto) > 10
                    
                    if not tem_texto:
                        all_vectorial = False
                        break
                    
                    tem_imagens = len(page.get_images()) > 0
                    if tem_imagens:
                        original_size = self._get_page_content_size(page)
                        if original_size > 500000:
                            pages_with_large_images += 1
                            all_vectorial = False
                            break
                except Exception as e:
                    logging.warning(f"Erro ao verificar página {i+1}: {e}")
                    all_vectorial = False
                    break
            
            if all_vectorial:
                logging.info(f"Todas as páginas são vetoriais, processando em lote")
                self._safe_update_progress(
                    'optimizing',
                    f'Processando {total_pages} páginas em lote...',
                    60,
                    f'Documento grande: processamento otimizado em lote'
                )
                batch_start = time.time()
                with fitz.open() as novo_pdf:
                    orig_metadata = dict(doc.metadata or {})
                    novo_pdf.insert_pdf(doc, from_page=0, to_page=total_pages - 1)
                    novo_pdf.set_metadata(orig_metadata)
                    output = BytesIO()
                    novo_pdf.save(output, garbage=4, deflate=True, clean=True)
                    batch_time = time.time() - batch_start
                    logging.info(f"Processamento em lote concluído para {total_pages} páginas em {batch_time:.2f}s")
                    return output.getvalue()
        
        # Processamento individual
        with fitz.open() as novo_pdf:
            orig_metadata = dict(doc.metadata or {})
            
            log_interval = 100 if total_pages > 100 else total_pages
            
            for i, page in enumerate(doc):
                start_time = time.time()
                
                progress_pct = 50 + int(((i + 1) / total_pages) * 30)
                self._safe_update_progress(
                    'optimizing',
                    f'Processando página {i+1} de {total_pages}...',
                    progress_pct,
                    f'Página {i+1}/{total_pages}'
                )
                
                if total_pages > 100 and (i + 1) % log_interval == 0:
                    progress_pct_actual = ((i + 1) / total_pages) * 100
                    logging.info(f"Processando página {i+1}/{total_pages} ({progress_pct_actual:.1f}%)")
                
                original_size = self._get_page_content_size(page)
                
                try:
                    texto_pagina = page.get_text().strip()
                    tem_texto_legivel = len(texto_pagina) > 10
                    tem_imagens = len(page.get_images()) > 0
                    is_scanned = self._is_page_scanned(page)
                    is_very_small = original_size < 5000
                    is_extremely_large = original_size > 20000000
                    
                    # DECISÃO CRÍTICA: Quando converter para imagem?
                    # Só converte se realmente necessário e se não aumentar muito o tamanho
                    should_keep_vectorial = is_extremely_large or \
                                             is_very_small or \
                                             (tem_texto_legivel and not is_scanned) or \
                                             (original_size < 100000 and not is_scanned) or \
                                             (not tem_imagens and original_size < 50000)
                    
                    if should_keep_vectorial:
                        # Mantém como vetor
                        width, height = page.rect.width, page.rect.height
                        is_landscape = width > height
                        target = A4_LANDSCAPE if is_landscape else A4_PORTRAIT
                        is_a4 = (abs(width - target[0]) <= target[0] * 0.05 and
                                 abs(height - target[1]) <= target[1] * 0.05)
                        
                        if is_a4:
                            novo_pdf.insert_pdf(doc, from_page=i, to_page=i)
                        else:
                            page_pdf_bytes = self._resize_to_a4(page)
                            with fitz.open("pdf", page_pdf_bytes) as page_doc:
                                novo_pdf.insert_pdf(page_doc, from_page=0, to_page=0)
                        
                        reason = []
                        if is_very_small:
                            reason.append("muito pequena")
                        if tem_texto_legivel:
                            reason.append(f"texto({len(texto_pagina)} chars)")
                        if not is_scanned:
                            reason.append("não escaneada")
                        self._log_page_processing(
                            i, "pagina_vetorial", time.time() - start_time,
                            original_size, None,
                            f"Mantida como vetor: {', '.join(reason)}"
                        )
                    else:
                        # Tenta converter para imagem, mas com verificações rigorosas
                        original_size_kb = original_size / 1024
                        
                        # Se a página já é grande (>5MB), evita converter para imagem
                        # pois JPEG de alta qualidade vai aumentar ainda mais
                        if original_size_kb > 5000: # > 5MB
                            logging.info(f"Página {i+1} muito grande ({original_size_kb:.1f}KB), mantendo como vetor")
                            # Mantém como vetor
                            page_pdf_bytes = self._resize_to_a4(page)
                            with fitz.open("pdf", page_pdf_bytes) as page_doc:
                                novo_pdf.insert_pdf(page_doc, from_page=0, to_page=0)
                            self._log_page_processing(
                                i, "pagina_vetorial_fallback", time.time() - start_time,
                                original_size, len(page_pdf_bytes),
                                f"Mantida como vetor (muito grande: {original_size_kb:.1f}KB)"
                            )
                            continue
                        
                        # Processa como imagem com DPI REDUZIDO para compressão
                        processed_page_bytes = self._resize_to_a4(page)
                        with fitz.open("pdf", processed_page_bytes) as processed_doc:
                            processed_page = processed_doc[0]
                            width, height = processed_page.rect.width, processed_page.rect.height
                            is_paisagem = width > height
                            target_size = A4_LANDSCAPE if is_paisagem else A4_PORTRAIT
                            
                            # DPI ADAPTATIVO MAIS BAIXO para melhor compressão
                            if original_size_kb > 2000:
                                dpi = 120  # DPI baixo para páginas grandes
                            elif original_size_kb > 1000:
                                dpi = 140  # DPI médio-baixo
                            else:
                                dpi = self.image_dpi
                            
                            pix = processed_page.get_pixmap(dpi=dpi)
                            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            
                            # Redimensionamento mais agressivo
                            max_size = self.max_image_size
                            if max(img.size) > max_size:
                                ratio = max_size / max(img.size)
                                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                                img = img.resize(new_size, Image.LANCZOS)
                            
                            # QUALIDADE JPEG MAIS BAIXA para melhor compressão
                            # Usa subsampling 420 para melhor compressão (sacrifica um pouco de qualidade)
                            buffer = BytesIO()
                            img.save(buffer, format="JPEG", quality=self.jpeg_quality,
                                     subsampling=2, optimize=True)  # subsampling=2 é 420 (melhor compressão)
                            img_bytes = buffer.getvalue()
                            
                            compressed_size = len(img_bytes)
                            
                            # VERIFICAÇÃO CRÍTICA: Se a conversão aumenta o tamanho, mantém como vetor
                            size_increase_ratio = compressed_size / original_size if original_size > 0 else float('inf')
                            
                            if size_increase_ratio > 1.0:  # Se aumentou o tamanho
                                logging.warning(
                                    f"Página {i+1}: conversão aumentaria tamanho de {original_size/1024:.2f}KB "
                                    f"para {compressed_size/1024:.2f}KB ({size_increase_ratio:.1f}x), mantendo como vetor"
                                )
                                # Mantém como vetor
                                page_pdf_bytes = self._resize_to_a4(page)
                                with fitz.open("pdf", page_pdf_bytes) as page_doc:
                                    novo_pdf.insert_pdf(page_doc, from_page=0, to_page=0)
                                self._log_page_processing(
                                    i, "pagina_vetorial_fallback", time.time() - start_time,
                                    original_size, len(page_pdf_bytes),
                                    f"Mantida como vetor (aumento: {size_increase_ratio:.1f}x)"
                                )
                            else:
                                new_page = novo_pdf.new_page(width=target_size[0], height=target_size[1])
                                new_page.insert_image(
                                    fitz.Rect(0, 0, target_size[0], target_size[1]), 
                                    stream=img_bytes
                                )
                                
                                self._log_page_processing(
                                    i, "pagina_imagem", time.time() - start_time,
                                    original_size, compressed_size,
                                    f"Formato: JPEG, Qualidade: {self.jpeg_quality}, DPI: {dpi}, Subsampling: 420"
                                )
                            
                except Exception as e:
                    logging.warning(f"Erro processando página {i}: {str(e)}")
                    # Fallback: insere página original redimensionada
                    page_pdf_bytes = self._resize_to_a4(page)
                    with fitz.open("pdf", page_pdf_bytes) as page_doc:
                        novo_pdf.insert_pdf(page_doc, from_page=0, to_page=0)
            
            novo_pdf.set_metadata(orig_metadata)
            output = BytesIO()
            novo_pdf.save(output, garbage=4, deflate=True, clean=True)
            return output.getvalue()

    def _handle_ocr_errors(self, pdf_data: bytes) -> bytes:
        """
        Trata erros aplicando compressão final.
        """
        try:
            if not self.enable_ocr:
                logging.info("OCR desativado. Aplicando compressão final após erro.")
                return self._compress_pdf_final(pdf_data)
                
            return self._otimizacao_padrao(pdf_data)
            
        except Exception as e:
            logging.error(f"OCR falhou: {e}")
            return self._compress_pdf_final(pdf_data)

    def _otimizacao_padrao(self, pdf_data: bytes) -> bytes:
        """
        Processa o PDF com OCRMyPDF com configurações otimizadas para compressão.
        """
        if not self.enable_ocr:
            logging.warning("OCR desativado. Retornando compressão final.")
            return self._compress_pdf_final(pdf_data)

        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as input_temp:
                input_temp.write(pdf_data)
                input_temp.flush()
                input_temp_name = input_temp.name
            
            output_temp_name = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as output_temp:
                    output_temp_name = output_temp.name
                
                self._safe_update_progress(
                    'ocr',
                    'Aplicando OCR para melhor compressão...',
                    60,
                    'Iniciando reconhecimento de texto'
                )
                
                # CONFIGURAÇÕES OTIMIZADAS PARA COMPRESSÃO
                ocrmypdf.ocr(
                    input_temp_name,
                    output_temp_name,
                    language='por+eng',
                    output_type='pdf',
                    optimize=1,           # ✅ Otimização leve
                    jpeg_quality=75,      # ✅ Qualidade moderada para melhor compressão
                    pdf_renderer='hocr',  # ✅ Modo mais eficiente em espaço
                    skip_text=False,
                    force_ocr=False,
                    deskew=False,
                    progress_bar=False,
                    rotate_pages=False,
                    clean=False,
                    jobs=2,               # ✅ Menos jobs para menos uso de memória
                    quiet=True
                )
                
                self._safe_update_progress(
                    'optimizing',
                    'OCR concluído, finalizando...',
                    90,
                    'OCRMyPDF concluído'
                )
                
                with open(output_temp_name, 'rb') as f:
                    result = f.read()
                    
                return result
                
            except ocrmypdf.exceptions.PriorOcrFoundError:
                logging.info("PDF já contém texto pesquisável, aplicando apenas otimização")
                self._safe_update_progress(
                    'optimizing',
                    'Otimizando PDF (já tem OCR)...',
                    80,
                    'PDF já possui texto pesquisável'
                )
                return self._compress_pdf_final(pdf_data)
                
            except Exception as ocr_error:
                error_msg = str(ocr_error)
                if "Tagged PDF" in error_msg or "does not need OCR" in error_msg:
                    logging.info("PDF Tagged detectado, aplicando otimização sem OCR")
                    self._safe_update_progress(
                        'optimizing',
                        'Otimizando PDF Tagged...',
                        80,
                        'PDF Tagged detectado'
                    )
                    return self._compress_pdf_final(pdf_data)
                logging.warning(f"OCR falhou, aplicando compressão básica: {ocr_error}")
                self._safe_update_progress(
                    'compressing',
                    'Aplicando compressão básica...',
                    85,
                    f'OCR falhou: {str(ocr_error)[:50]}'
                )
                return self._compress_pdf_final(pdf_data)
                
            finally:
                try:
                    if os.path.exists(input_temp_name):
                        os.unlink(input_temp_name)
                    if output_temp_name and os.path.exists(output_temp_name):
                        os.unlink(output_temp_name)
                except Exception as cleanup_error:
                    logging.warning(f"Erro na limpeza: {cleanup_error}")
                    
        except Exception as e:
            logging.error(f"Falha crítica no OCR: {str(e)}", exc_info=True)
            return self._compress_pdf_final(pdf_data)

    @contextmanager
    def _get_pdf_reader(self, file_stream: BytesIO) -> Iterator[PdfReader]:
        current_stream = file_stream.getvalue()
        if len(current_stream) > self._memory_threshold:
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(current_stream)
                tmp.flush()
                try:
                    with open(tmp.name, 'rb') as f:
                        reader = PdfReader(f)
                        _ = reader.pages[0]
                        yield reader
                except Exception as e:
                    raise PDFIrrecuperavelError(f"Falha ao ler PDF: {str(e)}")
                finally:
                    gc.collect()
                return
        try:
            if self._cached_pdf_reader is None or self._cached_pdf_stream != current_stream:
                self._cached_pdf_stream = current_stream
                reader = PdfReader(BytesIO(self._cached_pdf_stream))
                _ = reader.pages[0]
                self._cached_pdf_reader = reader
            yield self._cached_pdf_reader
        except Exception as e:
            try:
                repaired = self._repair_with_pikepdf(current_stream)
                reader = PdfReader(BytesIO(repaired))
                _ = reader.pages[0]
                self._cached_pdf_reader = reader
                yield self._cached_pdf_reader
            except Exception as inner_e:
                raise PDFIrrecuperavelError("PDF irrecuperável") from inner_e

    def _repair_with_pikepdf(self, pdf_bytes: bytes) -> bytes:
        try:
            with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
                output = BytesIO()
                pdf.save(output, linearize=True, compress_streams=True)
                return output.getvalue()
        except Exception:
            return pdf_bytes

    def _read_file_chunked(self, file_obj: BinaryIO) -> bytes:
        file_obj.seek(0)
        buffer = BytesIO()
        for chunk in iter(lambda: file_obj.read(8192), b''):
            buffer.write(chunk)
        return buffer.getvalue()

    def _validate_pdf(self, pdf_data: bytes) -> None:
        validate_pdf_size(pdf_data)
        try:
            with fitz.open(stream=pdf_data, filetype="pdf") as doc:
                if doc.page_count > MAX_PAGES:
                    raise PDFPageLimitExceededError(
                        f"PDF contém {doc.page_count} páginas (limite: {MAX_PAGES})"
                    )
        except Exception as e:
            raise PDFIrrecuperavelError(f"PDF inválido: {str(e)}")

    def _verificar_assinaturas(self, pdf_data: bytes) -> Union[bool, Optional[List[SignatureData]]]:
        try:
            with BytesIO(pdf_data) as stream:
                signatures = self.get_signatures_from_stream(stream, "temp.pdf")
                return signatures if hasattr(self, 'get_signatures_from_stream') else bool(signatures)
        except Exception as e:
            logging.warning(f"Verificação de assinaturas falhou: {str(e)}")
            return False if not hasattr(self, 'get_signatures_from_stream') else None

    def _compress_pdf_final(self, pdf_data: bytes) -> bytes:
        """
        Compressão final agressiva usando pikepdf.
        """
        try:
            with pikepdf.open(BytesIO(pdf_data)) as pdf:
                output = BytesIO()
                # Configurações agressivas de compressão
                pdf.save(
                    output,
                    linearize=False,  # Não linearizar para melhor compressão
                    compress_streams=True,
                    stream_compress_level=9,  # Nível máximo de compressão
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                    preserve_pdfa=False,  # Não preservar PDF/A para melhor compressão
                    compress_fonts=True,
                    normalize_content=True,
                    deduplicate_images=True,  # Deduplicar imagens
                    force_version='1.5'  # Versão mais compatível
                )
                compressed = output.getvalue()
                if len(compressed) < len(pdf_data):
                    logging.info(f"Compressão final: {len(pdf_data)/1024:.2f}KB -> {len(compressed)/1024:.2f}KB (redução: {calculate_compression_rate(len(pdf_data), len(compressed)):.1f}%)")
                    return compressed
                return pdf_data
        except Exception as e:
            logging.warning(f"Compressão final falhou: {str(e)}")
            return pdf_data

    def processar_pdf(self, pdf_data: bytes) -> bytes:
        try:
            if self._verificar_assinaturas(pdf_data):
                logging.warning("PDF mantido original devido à presença de assinatura digital.")
                return pdf_data
            start_time = time.time()
            
            self._safe_update_progress(
                'resizing',
                'Redimensionando para A4...',
                30,
                f'Verificando e ajustando dimensões das páginas'
            )
            
            resize_start = time.time()
            pdf_data = self._resize_document_to_a4(pdf_data)
            resize_time = time.time() - resize_start
            logging.info(f"Redimensionamento para A4 concluído em {resize_time:.2f}s")
            logging.info(f"Tamanho após redimensionamento: {len(pdf_data)/1024:.2f} KB")
            
            self._safe_update_progress(
                'resizing',
                'Redimensionamento concluído',
                35,
                f'Redimensionado em {resize_time:.2f}s - {len(pdf_data)/1024:.1f} KB'
            )
            original_size_after_resize = len(pdf_data)
            
            with fitz.open(stream=pdf_data) as doc:
                self._safe_update_progress(
                    'checking_text',
                    'Verificando texto pesquisável...',
                    40,
                    f'Analisando {doc.page_count} páginas para detectar texto'
                )
                
                step_start = time.time()
                check_start = time.time()
                tem_texto_pesquisavel = self._documento_tem_texto_pesquisavel(doc)
                check_time = time.time() - check_start
                logging.info(f"Verificação de texto pesquisável: {check_time:.2f}s (tem_texto: {tem_texto_pesquisavel}, páginas: {doc.page_count})")
                
                self._safe_update_progress(
                    'checking_text',
                    'Verificação de texto concluída',
                    45,
                    f'Texto pesquisável: {"Sim" if tem_texto_pesquisavel else "Não"} ({doc.page_count} páginas)'
                )
                
                # LÓGICA DE OCR CONFIGURÁVEL
                should_run_ocr = (
                    self.enable_ocr and 
                    (
                        (not tem_texto_pesquisavel and not self.ocr_fallback_only) or
                        (tem_texto_pesquisavel and self.ocr_force_enabled)
                    )
                )

                if should_run_ocr:
                    action_msg = "OCR FORÇADO" if tem_texto_pesquisavel and self.ocr_force_enabled else "OCR para compressão"
                    logging.info(f"Aplicando {action_msg}")
                    return self._otimizacao_padrao(pdf_data)
                
                # PDF sem OCR visível - tenta otimização inteligente
                self._safe_update_progress(
                    'optimizing',
                    'Otimizando PDF...',
                    50,
                    f'Iniciando otimização inteligente para {doc.page_count} páginas'
                )
                
                try:
                    pdf_otimizado = self._otimizacao_inteligente(doc)
                    tamanho_otimizado = len(pdf_otimizado)
                    
                    # VERIFICAÇÃO CRÍTICA: Se a otimização aumentou o tamanho
                    if tamanho_otimizado > original_size_after_resize * 1.02:  # Tolerância de 2%
                        aumento_percentual = (tamanho_otimizado - original_size_after_resize) / original_size_after_resize * 100
                        logging.warning(
                            f"Otimização aumentou o tamanho do PDF de {original_size_after_resize/1024:.2f}KB "
                            f"para {tamanho_otimizado/1024:.2f}KB (aumento: {aumento_percentual:.1f}%)"
                        )
                        
                        # SE OCR ESTÁ ATIVADO E É FALLBACK-ONLY, TENTA OCR
                        if self.enable_ocr and self.ocr_fallback_only:
                            logging.warning("Otimização aumentou tamanho, aplicando OCR RÁPIDO (fallback)")
                            self._safe_update_progress(
                                'ocr',
                                'Aplicando OCR para melhor compressão (fallback)...',
                                70,
                                'Otimização aumentou tamanho - tentando OCR'
                            )
                            return self._otimizacao_padrao(pdf_data)
                        else:
                            # Se OCR não está disponível ou não é fallback, aplica compressão final
                            self._safe_update_progress(
                                'compressing',
                                'Comprimindo PDF (otimização aumentou tamanho)...',
                                85,
                                f'Aumento: {aumento_percentual:.1f}% - aplicando compressão agressiva'
                            )
                            return self._compress_pdf_final(pdf_otimizado)
                    
                    # Se otimização foi boa (não aumentou muito ou reduziu), aplica compressão final leve
                    self._safe_update_progress(
                        'compressing',
                        'Aplicando compressão final...',
                        85,
                        f'Otimização bem sucedida ({tamanho_otimizado/1024:.1f}KB)'
                    )
                    return self._compress_pdf_final(pdf_otimizado)
                
                except Exception as intel_error:
                    logging.warning(f"Falha na otimização inteligente: {str(intel_error)}")
                    
                    if self.enable_ocr:
                        self._safe_update_progress(
                            'ocr',
                            'Aplicando OCR (fallback por erro)...',
                            60,
                            f'Falha na otimização: {str(intel_error)[:50]}'
                        )
                        return self._otimizacao_padrao(pdf_data)
                    else:
                        logging.warning("OCR desativado. Aplicando compressão final após falha.")
                        self._safe_update_progress(
                            'compressing',
                            'Aplicando compressão final (após erro)...',
                            85,
                            f'Falha na otimização: {str(intel_error)[:50]}'
                        )
                        return self._compress_pdf_final(pdf_data)
        
        except Exception as e:
            logging.error(f"Erro geral no processamento: {str(e)}")
            self._safe_update_progress('error', f'Erro no processamento: {str(e)}', 0)
            return self._handle_ocr_errors(pdf_data)


# ******************************************
# SIGNATURE HANDLING
# ******************************************
class PDFSignatureParser(PDFProcessor):
    def parse_signatures(self, raw_signature_data: bytes) -> Generator[SignerInfo, None, None]:
        if not raw_signature_data:
            return
        try:
            info = cms.ContentInfo.load(raw_signature_data)
            signed_data = info['content']
            if 'certificates' not in signed_data:
                return
            for cert in signed_data['certificates']:
                try:
                    cert_data = cert.native['tbs_certificate']
                    subject = cert_data.get('subject', {})
                    issuer = cert_data.get('issuer', {})
                    common_name = subject.get('common_name', '')
                    nome, cpf = (common_name.split(':', 1) + [''])[:2]
                    yield {
                        'type': subject.get('organization_name', ''),
                        'signer': nome.strip() or None,
                        'cpf': format_cpf(cpf.strip()),
                        'oname': issuer.get('organization_name', '')
                    }
                except Exception as e:
                    logging.warning(f"Erro no certificado: {str(e)}")
                    continue
        except Exception as e:
            logging.warning(f"Erro no parse ASN.1: {str(e)}")
            return

    def get_signatures_from_stream(self, file_stream: BytesIO, filename: str) -> List[SignatureData]:
        try:
            all_signers = []
            with self._get_pdf_reader(file_stream) as reader:
                try:
                    fields = reader.get_fields() or {}
                except Exception:
                    fields = {}
                signatures = [
                    f.value for f in fields.values()
                    if getattr(f, 'field_type', None) == '/Sig' and f.value
                ]
                for sig in signatures:
                    try:
                        all_signers.extend(list(self._process_signature(sig, filename)))
                    except Exception as e:
                        logging.warning(f"Erro na assinatura: {str(e)}")
            return all_signers
        except Exception as e:
            logging.error(f"Erro geral: {str(e)}", exc_info=True)
            return []

    def _process_signature(self, signature: Dict[str, Any], filename: str) -> Generator[SignatureData, None, None]:
        name_field = signature.get('/Name', '')
        name, cpf_name = (name_field.split(':', 1) + [''])[:2]
        name = name.strip() or None
        cpf_name = format_cpf(cpf_name.strip()) if cpf_name.strip() else None
        raw_data = signature.get('/Contents')
        cpf_contents = self._extract_cpf_from_contents(raw_data)
        parsed = list(self.parse_signatures(raw_data)) if isinstance(raw_data, bytes) else []
        signing_time = self._extract_signing_time(signature)
        if parsed:
            for signer in parsed:
                yield {
                    'signer_name': name or signer.get('signer'),
                    'signer_cpf': signer.get('cpf') or cpf_name or cpf_contents,
                    'signing_time': signing_time,
                    'signer_certificate': signer.get('oname')
                }
        elif name or cpf_name or cpf_contents:
            yield {
                'signer_name': name,
                'signer_cpf': cpf_name or cpf_contents,
                'signing_time': signing_time,
                'signer_certificate': ''
            }

    def _extract_signing_time(self, signature: Dict[str, Any]) -> Optional[str]:
        if '/M' not in signature:
            return None
        try:
            time_raw = signature['/M']
            ts_clean = time_raw[2:] if time_raw.startswith('D:') else time_raw
            ts_clean = re.sub(r"([+-]\d{2})'(\d{2})'", r"\1:\2", ts_clean)
            dt = parse(ts_clean)
            return format_datetime(dt)
        except Exception as e:
            logging.warning(f"Erro no timestamp: {str(e)}")
            return None

    def _extract_cpf_from_contents(self, raw: Optional[bytes]) -> Optional[str]:
        if not raw:
            return None
        try:
            if isinstance(raw, str):
                raw = raw.encode('utf-8')
            match = re.search(rb'\d{8}(\d{11})\d*', raw) or re.search(rb'(\d{11})', raw)
            if match:
                return format_cpf(match.group(1).decode('ascii', errors='ignore'))
        except Exception as e:
            logging.warning(f"Erro ao extrair CPF: {str(e)}")
        return None

# ******************************************
# PROGRESS STORAGE (Simplificado para Zope)
# ******************************************
_progress_cache = {}
_last_cleanup = time.time()

def _get_progress_from_cache(session_id: str) -> Dict[str, Any]:
    """Obtém progresso do cache simplificado"""
    global _last_cleanup
    current_time = time.time()
    
    if current_time - _last_cleanup > 300:
        cutoff_time = current_time - 600
        keys_to_remove = [
            k for k, v in _progress_cache.items()
            if v.get('timestamp', 0) < cutoff_time
        ]
        for k in keys_to_remove:
            del _progress_cache[k]
        _last_cleanup = current_time
    
    return _progress_cache.get(session_id, {
        'stage': 'unknown',
        'message': 'Processando...',
        'progress': 0,
        'details': ''
    })

def _set_progress_in_cache(session_id: str, progress_data: Dict[str, Any]):
    """Armazena progresso no cache simplificado"""
    progress_data['timestamp'] = time.time()
    _progress_cache[session_id] = progress_data

def _get_session_id(request) -> str:
    """Obtém um ID único para a sessão/requisição"""
    try:
        if hasattr(request, 'cookies'):
            session_cookie = request.cookies.get('__ac', None) or request.cookies.get('session_id', None) or request.cookies.get('ZopeSession', None)
            if session_cookie:
                if isinstance(session_cookie, bytes):
                    session_cookie = session_cookie.decode('utf-8', errors='ignore')
                return f"cookie_{session_cookie}"
        
        if hasattr(request, 'SESSION'):
            session_obj = request.SESSION
            if hasattr(session_obj, '_p_oid'):
                oid = session_obj._p_oid
                if isinstance(oid, bytes):
                    oid = oid.hex()
                elif oid is None:
                    oid = str(hash(session_obj))
                else:
                    oid = str(oid)
                return f"session_{oid}"
            
            if hasattr(session_obj, '__parent__'):
                return f"session_path_{id(session_obj.__parent__)}"
            
            return f"session_{id(session_obj)}"
        
        return f"req_{id(request)}"
    except Exception:
        return f"fallback_{time.time()}"

# ******************************************
# PROGRESS VIEW
# ******************************************
class PDFProcessingProgressView(grok.View):
    """View para consultar o progresso do processamento de PDF"""
    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('pdf_processing_progress')

    def render(self):
        """Retorna o progresso atual em JSON"""
        try:
            session_id = _get_session_id(self.request)
            progress_data = _get_progress_from_cache(session_id)
            
            if progress_data.get('stage') == 'unknown':
                current_time = time.time()
                most_recent = None
                most_recent_time = 0
                
                for key, value in _progress_cache.items():
                    value_time = value.get('timestamp', 0)
                    if value_time > current_time - 300:
                        if value_time > most_recent_time:
                            most_recent = value
                            most_recent_time = value_time
                
                if most_recent:
                    progress_data = most_recent
            
            if progress_data.get('stage') == 'unknown' and hasattr(self.request, 'SESSION'):
                progress_key = 'pdf_processing_progress'
                session_data = self.request.SESSION.get(progress_key)
                if session_data:
                    progress_data = session_data
                    _set_progress_in_cache(session_id, progress_data)
            
            self.request.RESPONSE.setHeader('Content-Type', 'application/json')
            import json
            result = json.dumps(progress_data)
            return result
        except Exception as e:
            logging.error(f"Erro ao obter progresso: {e}", exc_info=True)
            self.request.RESPONSE.setHeader('Content-Type', 'application/json')
            import json
            return json.dumps({
                'stage': 'error',
                'message': f'Erro ao obter progresso: {str(e)}',
                'progress': 0,
                'details': ''
            })

# ******************************************
# MAIN PROCESSOR
# ******************************************
class PDFUploadProcessorView(grok.View, PDFSignatureParser):
    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('otimizar_arquivo')

    def __init__(self, context, request):
        super().__init__(context, request)
        PDFProcessor.__init__(self)
        self.png_compression = PNG_COMPRESSION_LEVEL
        self.fallback_jpeg_quality = FALLBACK_JPEG_QUALITY

    def _update_progress(self, stage: str, message: str, progress: int = None, details: str = ""):
        """
        Atualiza o progresso do processamento.
        """
        try:
            if not hasattr(self, 'request'):
                return
            
            session_id = _get_session_id(self.request)
            
            previous_progress = _get_progress_from_cache(session_id)
            previous_progress_pct = previous_progress.get('progress', 0)
            
            current_progress = progress if progress is not None else 0
            
            if previous_progress.get('stage') not in ('unknown', 'complete', 'error', 'initializing'):
                if '[Retry]' in previous_progress.get('message', ''):
                    if current_progress < previous_progress_pct:
                        current_progress = previous_progress_pct
                        if '[Retry]' not in message:
                            message = f"[Retry] {message}"
            
            progress_data = {
                'stage': stage,
                'message': message,
                'progress': current_progress,
                'details': details,
                'timestamp': time.time()
            }
            
            _set_progress_in_cache(session_id, progress_data)
            
            if hasattr(self.request, 'SESSION'):
                try:
                    progress_key = 'pdf_processing_progress'
                    self.request.SESSION[progress_key] = progress_data
                    try:
                        self.request.SESSION._p_changed = True
                    except:
                        pass
                except Exception:
                    pass
            
            if stage in ('error', 'complete'):
                logging.info(f"[PROGRESS] {stage} - {message} ({current_progress}%)")
        except Exception:
            pass

    def _get_progress(self):
        """Retorna o progresso atual do processamento"""
        try:
            if hasattr(self.request, 'SESSION'):
                progress_key = 'pdf_processing_progress'
                return self.request.SESSION.get(progress_key, {
                    'stage': 'unknown',
                    'message': 'Processando...',
                    'progress': 0,
                    'details': ''
                })
        except:
            pass
        return {
            'stage': 'unknown',
            'message': 'Processando...',
            'progress': 0,
            'details': ''
        }

    def render(
        self,
        filename: BinaryIO,
        title: Optional[str] = None,
        **kwargs
    ) -> Any:
        try:
            start_time = time.time()
            
            file_obj = filename
            read_start = time.time()
            original_data = self._read_file_chunked(file_obj)
            original_size = len(original_data)
            read_time = time.time() - read_start
            logging.info('[READ_COMPLETE] Arquivo lido com sucesso size=%.2f KB (%.2fs)', 
                         original_size / 1024, read_time)
            
            file_hash = self._get_file_hash(original_data)
            cache_key = f"pdf_process_{file_hash}"
            
            is_retry = False
            if hasattr(self.request, 'SESSION'):
                cache_data = self.request.SESSION.get(cache_key)
                if cache_data:
                    elapsed = time.time() - cache_data.get('start_time', start_time)
                    is_retry = True
                    logging.info(f'[RETRY_DETECTED] Possível retry detectado (hash: {file_hash[:8]}...), tempo decorrido: {elapsed:.2f}s')
            
            session_id = _get_session_id(self.request)
            if is_retry:
                previous_progress = _get_progress_from_cache(session_id)
                
                if previous_progress.get('stage') not in ('unknown', 'complete', 'error'):
                    prev_stage = previous_progress.get('stage', 'processing')
                    prev_message = previous_progress.get('message', 'Processando...')
                    prev_progress = previous_progress.get('progress', 0)
                    prev_details = previous_progress.get('details', '')
                    
                    self._update_progress(
                        prev_stage,
                        f"[Retry] {prev_message}",
                        prev_progress,
                        f"Reprocessando após ConflictError - {prev_details}"
                    )
                else:
                    self._update_progress('processing', '[Retry] Reprocessando após ConflictError...', 20, 'Zope detectou conflito e está reprocessando')
            else:
                self._update_progress('initializing', 'Iniciando processamento...', 0, 'Preparando arquivo para processamento')
                time.sleep(0.1)
                self._update_progress('reading', 'Lendo arquivo...', 5, 'Carregando arquivo PDF')
            
            if hasattr(self.request, 'SESSION'):
                self.request.SESSION[cache_key] = {'status': 'processing', 'start_time': start_time}
            
            current_progress = _get_progress_from_cache(session_id)
            if not is_retry or current_progress.get('stage') in ('unknown', 'processing', 'initializing'):
                self._update_progress('validating', f'Validando PDF ({original_size/1024:.1f} KB)...', 10)
            self._validate_pdf(original_data)
            logging.info('[VALIDATE_COMPLETE] Validação concluída')

            self._update_progress('checking_signatures', 'Verificando assinaturas digitais...', 15)
            assinaturas = self._verificar_assinaturas(original_data)
            if assinaturas:
                logging.warning("Assinaturas digitais detectadas (%d). PDF mantido original.", len(assinaturas))
                result = {'file_stream': BytesIO(original_data), 'signatures': assinaturas}
                if hasattr(self.request, 'SESSION'):
                    self.request.SESSION[cache_key] = {
                        'status': 'complete',
                        'start_time': start_time,
                        'end_time': time.time()
                    }
                self._update_progress('complete', 'PDF mantido original (assinado)', 100, f'{len(assinaturas)} assinatura(s) detectada(s)')
                return result
            else:
                self._update_progress('processing', 'Iniciando processamento...', 20)
                result_data = self.processar_pdf(original_data)
                optimized_size = len(result_data)
                total_time = time.time() - start_time
                reduction = calculate_compression_rate(original_size, optimized_size)
                logging.info(
                    '[SIZE_REDUCTION] Tamanho original: %.2f KB, otimizado: %.2f KB, redução: %.2f KB (%.2f%%) - Tempo total: %.2fs',
                    original_size / 1024,
                    optimized_size / 1024,
                    (original_size - optimized_size) / 1024,
                    reduction,
                    total_time
                )
                if hasattr(self.request, 'SESSION'):
                    self.request.SESSION[cache_key] = {
                        'status': 'complete',
                        'start_time': start_time,
                        'end_time': time.time(),
                        'reduction': reduction,
                        'optimized_size': optimized_size
                    }
                self._update_progress('complete', 'Processamento concluído', 100, 
                                     f'Redução: {reduction:.1f}% ({optimized_size/1024:.1f} KB)')
                return result_data

        except (PDFSizeExceededError, PDFPageLimitExceededError) as e:
            logging.error(str(e))
            self._update_progress('error', f'Erro de Limite: {str(e)}', 0)
            raise
        except PDFIrrecuperavelError as e:
            logging.error(str(e))
            self._update_progress('error', f'PDF Irrecuperável: {str(e)}', 0)
            raise
        except Exception as e:
            logging.error(f"Erro inesperado: {str(e)}", exc_info=True)
            self._update_progress('error', f'Falha no processamento: {str(e)}', 0)
            raise ValueError(f"Falha no processamento: {str(e)}")
