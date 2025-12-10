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
import threading

# Se usar com Zope/Plone:
from five import grok
from zope.interface import Interface

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

# AJUSTES DE QUALIDADE (MANTIDOS 200 DPI, mas pode ser ajustado para 300 se a nitidez do vetor for crítica)
TEXT_DPI = 200       
IMAGE_DPI = 200      

MAX_IMAGE_SIZE = 2400
# QUALIDADE JPEG BASE (Usada na otimização inteligente)
JPEG_QUALITY = 92    
FALLBACK_JPEG_QUALITY = 95 

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
    file_handler = logging.FileHandler('/var/openlegis/SAGL5/pdf_processor.log', mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
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
        self.png_compression = PNG_COMPRESSION_LEVEL
        self._processing_cache = {} # Cache para evitar reprocessamento em retry

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
                # Para conversões (imagem ou fallback), calcula taxa de compressão
                log_data['compressed_size_kb'] = round(compressed_size / 1024, 2)
                if original_size > 0:
                    compression_rate = calculate_compression_rate(original_size, compressed_size)
                    # Só mostra taxa se for razoável (evita valores absurdos de comparações incorretas)
                    if abs(compression_rate) < 10000: # Limita a 10000%
                        log_data['compression_rate'] = round(compression_rate, 2)
                    elif compressed_size > original_size:
                        # Se aumentou muito, mostra ratio
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
            # Considera como texto legível se tiver pelo menos 10 caracteres significativos
            return len(texto) >= 10 and any(c.isalnum() for c in texto)
        except Exception:
            return False

    def _documento_tem_texto_pesquisavel(self, doc: fitz.Document) -> bool:
        """
        Verifica se o documento tem texto pesquisável (OCR ou texto vetorial).
        Retorna True se pelo menos uma página tem texto legível.
        Otimizado para ser rápido mesmo em documentos grandes.
        """
        try:
            # Para documentos grandes, verifica apenas algumas páginas
            # Estratégia: primeira, última, e algumas do meio
            total_pages = doc.page_count
            if total_pages == 0:
                return False
            
            # Para documentos pequenos, verifica todas
            if total_pages <= 3:
                pages_to_check = list(range(total_pages))
            else:
                # Para documentos grandes, verifica: primeira, última, e algumas do meio
                pages_to_check = [0, total_pages - 1] # Primeira e última
                # Adiciona algumas páginas do meio
                if total_pages > 5:
                    mid = total_pages // 2
                    pages_to_check.extend([mid - 1, mid, mid + 1])
                else:
                    pages_to_check.extend(range(1, total_pages - 1))
            
            paginas_com_texto = 0
            for i in pages_to_check:
                try:
                    page = doc[i]
                    # Usa get_text com flags otimizadas
                    texto = page.get_text("text", flags=11).strip() # flags=11 é mais rápido
                    if len(texto) >= 10 and any(c.isalnum() for c in texto):
                        paginas_com_texto += 1
                        # Se encontrou texto em pelo menos uma página, já pode retornar True
                        if paginas_com_texto >= 1:
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
            # Caso já esteja em A4, só copia a página como está:
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
            # Salva com compressão para evitar aumento de tamanho
            tmp_doc.save(buf, garbage=4, deflate=True, clean=True)
        return buf.getvalue()

    def _resize_document_to_a4(self, pdf_data: bytes) -> bytes:
        """
        Redimensiona todas as páginas do documento para A4 de forma otimizada.
        Processa todas as páginas de uma vez em vez de página por página.
        """
        with fitz.open(stream=pdf_data, filetype="pdf") as doc:
            orig_metadata = dict(doc.metadata or {})
            total_pages = doc.page_count
            
            # Processa todas as páginas de uma vez
            with fitz.open() as new_doc:
                for i, page in enumerate(doc):
                    original_width = page.rect.width
                    original_height = page.rect.height
                    is_landscape = original_width > original_height
                    
                    # Verifica se esta página já está em A4
                    target = A4_LANDSCAPE if is_landscape else A4_PORTRAIT
                    is_a4 = (abs(original_width - target[0]) <= target[0] * 0.05 and
                             abs(original_height - target[1]) <= target[1] * 0.05)
                    
                    if is_a4:
                        # Já está em A4, apenas copia
                        new_doc.insert_pdf(doc, from_page=i, to_page=i)
                    else:
                        # Redimensiona para A4
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
                # Salva com compressão para evitar aumento de tamanho
                new_doc.save(output, garbage=4, deflate=True, clean=True)
                return output.getvalue()

    def _calcular_dpi_ideal(self, page) -> int:
        return self.text_dpi

    def _imagem_tem_detalhes(self, img: Image.Image) -> bool:
        return True

    def _determinar_parametros_compressao(self, img: Image.Image) -> tuple:
        return "JPEG", self.jpeg_quality, {'optimize': True, 'subsampling': 0}

    def _processar_imagem(self, img: Image.Image) -> bytes:
        try:
            buffer = BytesIO()
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(buffer, format="JPEG", quality=self.jpeg_quality,
                     subsampling=0, optimize=True)
            return buffer.getvalue()
        except Exception as e:
            logging.error(f"Falha crítica no processamento de imagem: {str(e)}")
            raise PDFIrrecuperavelError("Falha ao processar imagem com qualidade máxima")

    def _get_page_content_size(self, page: fitz.Page) -> int:
        """
        Calcula o tamanho aproximado da página incluindo conteúdo vetorial e imagens embutidas.
        Retorna o tamanho em bytes.
        """
        try:
            # Tamanho do conteúdo vetorial (texto, linhas, etc)
            content_size = len(page.read_contents() or b'')
            
            # Soma o tamanho das imagens embutidas
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
            
            # Retorna a soma do conteúdo vetorial e imagens
            # Se não tem imagens e o conteúdo é muito pequeno, pode ser uma página vetorial simples
            return content_size + image_size
        except:
            return 0

    def _is_page_scanned(self, page: fitz.Page) -> bool:
        """Verifica se a página é uma imagem escaneada (não vetorial)"""
        try:
            # Páginas escaneadas geralmente têm muito poucos objetos vetoriais
            # e muitas imagens grandes
            images = page.get_images()
            text_blocks = page.get_text("blocks")
            texto = page.get_text().strip()
            
            # Se tem muitas imagens e pouco texto estruturado, provavelmente é escaneada
            if len(images) > 0:
                # Verifica se tem pouco texto (menos de 50 caracteres) ou poucos blocos de texto
                if len(texto) < 50 or len(text_blocks) < 3:
                    # Verifica tamanho das imagens
                    page_area = page.rect.width * page.rect.height
                    for img_idx in images:
                        try:
                            xref = img_idx[0]
                            base_image = page.parent.extract_image(xref)
                            img_bytes = base_image.get("image", b"")
                            # Se as imagens são grandes (mais de 20KB), provavelmente é escaneada
                            if len(img_bytes) > 20000: # 20KB
                                return True
                        except:
                            continue
            return False
        except:
            return False

    def _otimizacao_inteligente(self, doc: fitz.Document) -> Optional[bytes]:
        """
        Processamento inteligente com melhor detecção de conteúdo.
        Preserva páginas vetoriais e só converte quando realmente necessário.
        Otimizado para documentos grandes com muitas páginas.
        """
        total_pages = doc.page_count
        logging.info(f"Iniciando otimização inteligente para {total_pages} páginas")
        
        # Para documentos grandes (>100 páginas), faz verificação rápida primeiro
        # para ver se todas as páginas são vetoriais
        if total_pages > 100:
            logging.info("Documento grande detectado, fazendo verificação rápida...")
            self._safe_update_progress(
                'optimizing',
                f'Analisando documento grande ({total_pages} páginas)...',
                52,
                f'Verificando amostra de páginas para otimização'
            )
            pages_to_check = min(10, total_pages) # Verifica até 10 páginas
            all_vectorial = True
            pages_with_images = 0
            pages_with_large_images = 0
            
            for i in range(pages_to_check):
                try:
                    page = doc[i]
                    # Verificação rápida: apenas texto (mais rápido que verificar imagens)
                    texto = page.get_text("text", flags=11).strip() # flags=11 é mais rápido
                    tem_texto = len(texto) > 10
                    
                    # Se não tem texto legível, precisa processar individualmente
                    if not tem_texto:
                        all_vectorial = False
                        logging.info(f"Página {i+1} sem texto legível, requer processamento individual")
                        break
                    
                    # Verifica imagens apenas se necessário (mais lento)
                    tem_imagens = len(page.get_images()) > 0
                    if tem_imagens:
                        pages_with_images += 1
                        # Só verifica tamanho se tem imagens
                        original_size = self._get_page_content_size(page)
                        if original_size > 500000: # > 500KB - imagens muito grandes
                            pages_with_large_images += 1
                            all_vectorial = False
                            logging.info(f"Página {i+1} tem imagens muito grandes ({original_size/1024:.1f}KB), requer processamento individual")
                            break
                except Exception as e:
                    logging.warning(f"Erro ao verificar página {i+1}: {e}")
                    all_vectorial = False
                    break
            
            logging.info(f"Verificação rápida: all_vectorial={all_vectorial}, pages_with_images={pages_with_images}, pages_with_large_images={pages_with_large_images}")
            
            # Se todas as páginas verificadas são vetoriais (têm texto e não são escaneadas),
            # pode processar em lote mesmo com imagens pequenas
            if all_vectorial:
                logging.info(f"Todas as páginas são vetoriais, processando em lote (otimização rápida)")
                self._safe_update_progress(
                    'optimizing',
                    f'Processando {total_pages} páginas em lote (todas vetoriais)...',
                    60,
                    f'Documento grande: processamento otimizado em lote'
                )
                batch_start = time.time()
                with fitz.open() as novo_pdf:
                    orig_metadata = dict(doc.metadata or {})
                    # Copia todas as páginas de uma vez (muito mais rápido)
                    novo_pdf.insert_pdf(doc, from_page=0, to_page=total_pages - 1)
                    novo_pdf.set_metadata(orig_metadata)
                    output = BytesIO()
                    novo_pdf.save(output, garbage=4, deflate=True, clean=True)
                    batch_time = time.time() - batch_start
                    logging.info(f"Processamento em lote concluído para {total_pages} páginas em {batch_time:.2f}s")
                    return output.getvalue()
            else:
                logging.info(f"Processamento individual necessário (all_vectorial={all_vectorial}, large_images={pages_with_large_images})")
                self._safe_update_progress(
                    'optimizing',
                    f'Processando {total_pages} páginas individualmente...',
                    55,
                    f'Páginas mistas detectadas - processamento otimizado'
                )
        
        # Processamento individual (para documentos pequenos ou com páginas mistas)
        with fitz.open() as novo_pdf:
            orig_metadata = dict(doc.metadata or {})
            
            # Log de progresso a cada 100 páginas para documentos grandes
            log_interval = 100 if total_pages > 100 else total_pages
            
            for i, page in enumerate(doc):
                start_time = time.time()
                
                # Atualiza progresso durante processamento de páginas
                progress_pct = 50 + int(((i + 1) / total_pages) * 30) # 50-80%
                self._safe_update_progress(
                    'optimizing',
                    f'Processando página {i+1} de {total_pages}...',
                    progress_pct,
                    f'Página {i+1}/{total_pages}'
                )
                
                # Log de progresso para documentos grandes
                if total_pages > 100 and (i + 1) % log_interval == 0:
                    progress_pct = ((i + 1) / total_pages) * 100
                    logging.info(f"Processando página {i+1}/{total_pages} ({progress_pct:.1f}%)")
                
                original_size = self._get_page_content_size(page)
                
                try:
                    # Verificação mais robusta de texto
                    texto_pagina = page.get_text().strip()
                    tem_texto_legivel = len(texto_pagina) > 10 # Mínimo de caracteres
                    
                    # Verifica se tem imagens significativas
                    tem_imagens = len(page.get_images()) > 0
                    
                    # Verifica se a página é escaneada (imagem) ou vetorial
                    is_scanned = self._is_page_scanned(page)
                    
                    # Páginas muito pequenas (< 5KB) são quase certamente vetoriais
                    # e não devem ser convertidas para imagem
                    is_very_small = original_size < 5000 # < 5KB
                    
                    # Páginas extremamente grandes (>20MB) - mantém como está para evitar processamento lento
                    # que pode causar ConflictError
                    is_extremely_large = original_size > 20000000 # > 20MB
                    
                    # Decisão: manter como vetor ou converter para imagem
                    is_small_page = original_size < 100000 # < 100KB
                    should_keep_vectorial = is_extremely_large or \
                                             is_very_small or \
                                             (tem_texto_legivel and not is_scanned) or \
                                             (is_small_page and not is_scanned) or \
                                             (not tem_imagens and original_size < 50000) # < 50KB
                    
                    if should_keep_vectorial:
                        # Página principalmente vetorial - mantém como vetor
                        # Para páginas extremamente grandes, mantém como está (já foi redimensionado antes)
                        if is_extremely_large:
                            # Página extremamente grande - mantém como está para evitar processamento lento
                            novo_pdf.insert_pdf(doc, from_page=i, to_page=i)
                            logging.info(f"Página {i+1} extremamente grande ({original_size/1024:.1f}KB), mantida como está")
                            self._safe_update_progress(
                                'optimizing',
                                f'Processando página {i+1} de {total_pages}...',
                                progress_pct,
                                f'Página {i+1}: mantida como está ({original_size/1024:.1f}KB - muito grande)'
                            )
                        else:
                            # Para páginas vetoriais normais, pode inserir diretamente se já está em A4
                            width, height = page.rect.width, page.rect.height
                            is_landscape = width > height
                            target = A4_LANDSCAPE if is_landscape else A4_PORTRAIT
                            is_a4 = (abs(width - target[0]) <= target[0] * 0.05 and
                                     abs(height - target[1]) <= target[1] * 0.05)
                            
                            if is_a4:
                                # Já está em A4, insere diretamente (mais rápido)
                                novo_pdf.insert_pdf(doc, from_page=i, to_page=i)
                            else:
                                # Precisa redimensionar
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
                        if not tem_imagens:
                            reason.append("sem imagens")
                        # Para páginas vetoriais mantidas como vetor, não passa compressed_size
                        # para evitar cálculos incorretos de taxa de compressão
                        self._log_page_processing(
                            i, "pagina_vetorial", time.time() - start_time,
                            original_size, None, # Não passa compressed_size para páginas vetoriais
                            f"Mantida como vetor: {', '.join(reason)}"
                        )
                    else:
                        # Página escaneada ou com imagens grandes - processa como imagem
                        original_size_kb = original_size / 1024
                        
                        # Para páginas extremamente grandes (>20MB), mantém como está
                        # para evitar processamento muito lento que causa ConflictError
                        if original_size_kb > 20000: # > 20MB
                            logging.warning(f"Página {i+1} extremamente grande ({original_size_kb:.1f}KB), mantendo como está para evitar ConflictError")
                            # Mantém como está (já foi redimensionado para A4 antes)
                            novo_pdf.insert_pdf(doc, from_page=i, to_page=i)
                            self._safe_update_progress(
                                'optimizing',
                                f'Processando página {i+1} de {total_pages}...',
                                progress_pct,
                                f'Página {i+1}: mantida como está ({original_size_kb:.1f}KB - muito grande)'
                            )
                            self._log_page_processing(
                                i, "pagina_mantida", time.time() - start_time,
                                original_size, original_size,
                                f"Mantida como está (muito grande: {original_size_kb:.1f}KB)"
                            )
                            continue
                        
                        # Processa como imagem com DPI adaptativo
                        processed_page_bytes = self._resize_to_a4(page)
                        with fitz.open("pdf", processed_page_bytes) as processed_doc:
                            processed_page = processed_doc[0]
                            width, height = processed_page.rect.width, processed_page.rect.height
                            is_paisagem = width > height
                            target_size = A4_LANDSCAPE if is_paisagem else A4_PORTRAIT
                            
                            # DPI adaptativo baseado no conteúdo e tamanho da página
                            # Para páginas muito grandes, reduz DPI drasticamente para acelerar processamento
                            if original_size_kb > 10000: # > 10MB - página muito grande
                                dpi = 100 # DPI muito baixo para acelerar drasticamente
                                logging.info(f"Página {i+1} muito grande ({original_size_kb:.1f}KB), usando DPI muito reduzido (100)")
                                self._safe_update_progress(
                                    'optimizing',
                                    f'Processando página {i+1} de {total_pages}...',
                                    progress_pct,
                                    f'Página {i+1}: convertendo para imagem (DPI 100 - muito grande: {original_size_kb:.1f}KB)'
                                )
                            elif original_size_kb > 5000: # > 5MB
                                dpi = 120 # DPI baixo
                                self._safe_update_progress(
                                    'optimizing',
                                    f'Processando página {i+1} de {total_pages}...',
                                    progress_pct,
                                    f'Página {i+1}: convertendo para imagem (DPI 120 - grande: {original_size_kb:.1f}KB)'
                                )
                            elif original_size_kb > 2000: # > 2MB
                                dpi = 150 # DPI médio-baixo
                            else:
                                dpi = self.image_dpi if tem_imagens else self.text_dpi
                            
                            pix = processed_page.get_pixmap(dpi=dpi)
                            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            
                            # Redimensionamento inteligente - redimensiona mais agressivamente para páginas grandes
                            max_size = self.max_image_size
                            if original_size_kb > 10000: # Páginas muito grandes
                                max_size = 1200 # Reduz muito o tamanho máximo
                            elif original_size_kb > 5000: # Páginas grandes
                                max_size = 1500 # Reduz tamanho máximo
                            elif original_size_kb > 2000: # Páginas médias-grandes
                                max_size = 1800 # Reduz um pouco
                            
                            if max(img.size) > max_size:
                                ratio = max_size / max(img.size)
                                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                                img = img.resize(new_size, Image.LANCZOS)
                            
                            # Compressão com qualidade alta para preservar qualidade
                            # Usa qualidade 92 (alta) para manter qualidade visual
                            formato, qualidade, opts = "JPEG", self.jpeg_quality, {
                                'optimize': True, 
                                'subsampling': 0 # Sem subsampling para melhor qualidade
                            }
                            
                            buffer = BytesIO()
                            img.save(buffer, format=formato, quality=qualidade, **opts)
                            img_bytes = buffer.getvalue()
                            
                            compressed_size = len(img_bytes)
                            
                            # Verifica se a conversão não aumentou muito o tamanho
                            size_increase_ratio = compressed_size / original_size if original_size > 0 else float('inf')
                            is_very_small = original_size < 5000 # < 5KB
                            significant_increase = size_increase_ratio > 1.2
                            
                            if significant_increase or is_very_small:
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
                                    f"Formato: {formato}, Qualidade: {qualidade}, DPI: {dpi}"
                                )
                            
                except Exception as e:
                    logging.warning(f"Erro processando página {i}: {str(e)}")
                    # Fallback: insere página original redimensionada
                    page_pdf_bytes = self._resize_to_a4(page)
                    with fitz.open("pdf", page_pdf_bytes) as page_doc:
                        novo_pdf.insert_pdf(page_doc, from_page=0, to_page=0)
            
            novo_pdf.set_metadata(orig_metadata)
            output = BytesIO()
            # Melhor compressão final
            novo_pdf.save(output, garbage=4, deflate=True, clean=True)
            return output.getvalue()

    def _handle_ocr_errors(self, pdf_data: bytes) -> bytes:
        """
        Trata erros (que antes levariam ao OCR) aplicando apenas a compressão final.
        """
        try:
            return self._otimizacao_padrao(pdf_data)
        except ocrmypdf.exceptions.PriorOcrFoundError:
            logging.info("PDF já contém OCR, aplicando otimização leve")
            return self._compress_pdf_final(pdf_data)
        except ocrmypdf.exceptions.UnsupportedImageFormatError:
            logging.warning("Formato de imagem não suportado, convertendo...")
            # Fallback para conversão básica
            return self._compress_pdf_final(pdf_data)
        except Exception as e:
            logging.error(f"OCR falhou: {e}")
            return pdf_data

    def _otimizacao_padrao(self, pdf_data: bytes) -> bytes:
        """
        Processa o PDF com OCRMyPDF de forma otimizada para VELOCIDADE (baixa qualidade).
        """
        try:
            # Criar arquivos temporários para entrada e saída
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as input_temp:
                input_temp.write(pdf_data)
                input_temp.flush()
                input_temp_name = input_temp.name
            
            output_temp_name = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as output_temp:
                    output_temp_name = output_temp.name
                
                # Atualiza progresso antes de iniciar OCR
                self._safe_update_progress(
                    'ocr',
                    'Aplicando OCR RÁPIDO (comprometimento da qualidade)...',
                    60,
                    'Iniciando reconhecimento de texto com configurações de alta velocidade'
                )
                
                # AJUSTES DE ALTA VELOCIDADE/BAIXA QUALIDADE APLICADOS AQUI:
                ocrmypdf.ocr(
                    input_temp_name,
                    output_temp_name,
                    language='por+eng',
                    output_type='pdf',
                    optimize=0,           # ❌ Desliga otimização pós-OCR (Mais Rápido, mas arquivo maior)
                    jpeg_quality=60,      # ❌ Qualidade BAIXA (Imagens menores, OCR mais rápido)
                    pdf_renderer='sandwich',# ✅ Modo mais rápido para renderização
                    skip_text=False,
                    force_ocr=False,
                    deskew=False,         # ❌ Desliga correção de inclinação (Mais Rápido)
                    progress_bar=False,
                    rotate_pages=False,   # ❌ Desliga rotação (Mais Rápido)
                    clean=False,          # ❌ Desliga limpeza (Mais Rápido)
                    jobs=4,               # ✅ Aumenta paralelismo (Assumindo múltiplos núcleos disponíveis)
                    quiet=True
                )
                
                # Atualiza progresso após OCR
                self._safe_update_progress(
                    'optimizing',
                    'OCR RÁPIDO concluído, finalizando otimização...',
                    90,
                    'OCRMyPDF concluído (modo rápido)'
                )
                
                # Ler o resultado
                with open(output_temp_name, 'rb') as f:
                    result = f.read()
                    
                return result
                
            except ocrmypdf.exceptions.PriorOcrFoundError:
                logging.info("PDF já contém texto pesquisável, aplicando apenas otimização")
                # Se já tem OCR, aplica apenas otimização
                self._safe_update_progress(
                    'optimizing',
                    'Otimizando PDF (já tem OCR)...',
                    80,
                    'PDF já possui texto pesquisável - apenas otimização'
                )
                return self._compress_pdf_final(pdf_data)
                
            except ocrmypdf.exceptions.InputFileError as e:
                error_msg = str(e)
                if "Tagged PDF" in error_msg or "does not need OCR" in error_msg:
                    logging.info("PDF Tagged detectado (gerado de documento office), aplicando otimização sem OCR")
                    self._safe_update_progress(
                        'optimizing',
                        'Otimizando PDF Tagged...',
                        80,
                        'PDF Tagged detectado - não precisa de OCR'
                    )
                    return self._compress_pdf_final(pdf_data)
                logging.warning(f"Erro no arquivo de entrada: {e}")
                self._safe_update_progress(
                    'compressing',
                    'Aplicando compressão...',
                    85,
                    f'Erro no OCR: {str(e)[:50]}'
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
                        'PDF Tagged detectado - não precisa de OCR'
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
                # Limpeza dos arquivos temporários
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
        try:
            with pikepdf.open(BytesIO(pdf_data)) as pdf:
                output = BytesIO()
                pdf.save(
                    output,
                    linearize=True,
                    compress_streams=True,
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                    preserve_pdfa=True,
                )
                compressed = output.getvalue()
                # Só retorna se realmente comprimiu (reduziu tamanho)
                if len(compressed) < len(pdf_data):
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
            
            # Atualiza progresso - redimensionamento
            self._safe_update_progress(
                'resizing',
                'Redimensionando para A4...',
                30,
                f'Verificando e ajustando dimensões das páginas'
            )
            
            resize_start = time.time()
            pdf_data = self._resize_document_to_a4(pdf_data)
            resize_time = time.time() - resize_start
            logging.info(f"Redimensionamento para A4 concluído em {resize_time:.2f}s ({resize_time*1000:.2f} ms)")
            logging.info(f"Tamanho após redimensionamento: {len(pdf_data)/1024:.2f} KB")
            
            self._safe_update_progress(
                'resizing',
                'Redimensionamento concluído',
                35,
                f'Redimensionado em {resize_time:.2f}s - {len(pdf_data)/1024:.1f} KB'
            )
            original_size = len(pdf_data)
            
            with fitz.open(stream=pdf_data) as doc:
                # Atualiza progresso - verificação de texto
                self._safe_update_progress(
                    'checking_text',
                    'Verificando texto pesquisável...',
                    40,
                    f'Analisando {doc.page_count} páginas para detectar texto'
                )
                
                step_start = time.time()
                # Verifica se o documento tem texto pesquisável (OCR)
                check_start = time.time()
                tem_texto_pesquisavel = self._documento_tem_texto_pesquisavel(doc)
                check_time = time.time() - check_start
                logging.info(f"Verificação de texto pesquisável: {check_time:.2f}s (tem_texto: {tem_texto_pesquisavel}, páginas: {doc.page_count})")
                logging.info(f"Verificação de texto pesquisável concluída em {time.time() - step_start:.2f}s (tem_texto: {tem_texto_pesquisavel})")
                
                self._safe_update_progress(
                    'checking_text',
                    'Verificação de texto concluída',
                    45,
                    f'Texto pesquisável: {"Sim" if tem_texto_pesquisavel else "Não"} ({doc.page_count} páginas)'
                )
                
                if not tem_texto_pesquisavel:
                    # PDF sem OCR - aplica OCR RÁPIDO
                    logging.info("PDF sem texto pesquisável detectado, aplicando OCR RÁPIDO")
                    return self._otimizacao_padrao(pdf_data)
                
                # PDF com texto pesquisável - aplica otimização inteligente
                self._safe_update_progress(
                    'optimizing',
                    'Otimizando PDF...',
                    50,
                    f'Iniciando otimização inteligente para {doc.page_count} páginas'
                )
                
                try:
                    pdf_otimizado = self._otimizacao_inteligente(doc)
                    
                    # Atualiza progresso durante otimização
                    self._safe_update_progress(
                        'optimizing',
                        'Finalizando otimização...',
                        80,
                        'Aplicando compressão final'
                    )
                    
                    # Verifica se a otimização aumentou o tamanho
                    if len(pdf_otimizado) > original_size * 1.05: # Tolerância de 5%
                        logging.warning(
                            f"Otimização aumentou o tamanho do PDF de {original_size/1024:.2f}KB "
                            f"para {len(pdf_otimizado)/1024:.2f}KB, aplicando compressão final"
                        )
                        self._safe_update_progress(
                            'compressing',
                            'Comprimindo PDF...',
                            85,
                            f'Tamanho aumentou - aplicando compressão adicional'
                        )
                        # Tenta compressão final
                        compressed = self._compress_pdf_final(pdf_data)
                        if len(compressed) < len(pdf_otimizado):
                            return compressed
                        # Se ainda aumentou muito, tenta OCR padrão (pode melhorar compressão)
                        if len(compressed) > original_size * 1.10:
                            logging.warning("Compressão ainda aumentou tamanho, aplicando OCR RÁPIDO (fallback)")
                            self._safe_update_progress(
                                'ocr',
                                'Aplicando OCR RÁPIDO para melhor compressão (fallback)...',
                                70,
                                'Compressão não foi suficiente - tentando OCR RÁPIDO'
                            )
                            return self._otimizacao_padrao(pdf_data)
                        return compressed
                    return pdf_otimizado
                
                except Exception as intel_error:
                    logging.warning(f"Falha na otimização inteligente: {str(intel_error)}")
                    self._safe_update_progress(
                        'ocr',
                        'Aplicando OCR RÁPIDO (fallback)...',
                        60,
                        f'Falha na otimização inteligente: {str(intel_error)[:50]}'
                    )
                    return self._otimizacao_padrao(pdf_data)
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
# PROGRESS STORAGE (Thread-safe global cache)
# ******************************************
# Cache global thread-safe para armazenar progresso
# Chave: session_id ou request_id, Valor: dict com progresso
_progress_cache = {}
_progress_cache_lock = threading.Lock()
_progress_cache_cleanup_interval = 300 # Limpa cache a cada 5 minutos
_last_cleanup = time.time()

def _get_progress_from_cache(session_id: str) -> Dict[str, Any]:
    """Obtém progresso do cache global"""
    global _last_cleanup
    with _progress_cache_lock:
        # Limpeza periódica de entradas antigas (>10 minutos)
        current_time = time.time()
        if current_time - _last_cleanup > _progress_cache_cleanup_interval:
            cutoff_time = current_time - 600 # 10 minutos
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
    """Armazena progresso no cache global"""
    with _progress_cache_lock:
        progress_data['timestamp'] = time.time()
        _progress_cache[session_id] = progress_data

def _get_session_id(request) -> str:
    """Obtém um ID único para a sessão/requisição que seja compartilhado entre requisições"""
    try:
        # Primeiro, tenta obter de um cookie de sessão (se disponível) - MELHOR OPÇÃO
        if hasattr(request, 'cookies'):
            session_cookie = request.cookies.get('__ac', None) or request.cookies.get('session_id', None) or request.cookies.get('ZopeSession', None)
            if session_cookie:
                # Converte para string se for bytes
                if isinstance(session_cookie, bytes):
                    session_cookie = session_cookie.decode('utf-8', errors='ignore')
                return f"cookie_{session_cookie}"
        
        # Tenta obter ID da sessão se disponível
        if hasattr(request, 'SESSION'):
            session_obj = request.SESSION
            # Tenta obter um identificador único do objeto SESSION
            if hasattr(session_obj, '_p_oid'):
                oid = session_obj._p_oid
                # Converte bytes para string hexadecimal
                if isinstance(oid, bytes):
                    oid = oid.hex()
                elif oid is None:
                    # Se _p_oid é None, usa hash do objeto
                    oid = str(hash(session_obj))
                else:
                    oid = str(oid)
                return f"session_{oid}"
            
            # Ou usa o caminho do objeto se disponível
            if hasattr(session_obj, '__parent__'):
                return f"session_path_{id(session_obj.__parent__)}"
            
            # Ou usa o ID do objeto diretamente
            return f"session_{id(session_obj)}"
        
        # Fallback: usa ID do request (não ideal, mas funciona para mesma requisição)
        return f"req_{id(request)}"
    except Exception:
        # Último fallback: timestamp + thread ID
        return f"fallback_{threading.current_thread().ident}_{time.time()}"

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
            # Obtém ID da sessão/requisição
            session_id = _get_session_id(self.request)
            
            # Tenta obter do cache global primeiro
            progress_data = _get_progress_from_cache(session_id)
            
            # Se não encontrou no cache, tenta buscar em todas as chaves do cache
            # (pode ser que o session_id seja ligeiramente diferente entre requisições)
            if progress_data.get('stage') == 'unknown':
                with _progress_cache_lock:
                    # Busca por prefixo (cookie_, session_, etc) ou busca o mais recente
                    current_time = time.time()
                    most_recent = None
                    most_recent_time = 0
                    
                    for key, value in _progress_cache.items():
                        # Verifica se é recente (últimos 5 minutos)
                        value_time = value.get('timestamp', 0)
                        if value_time > current_time - 300:
                            # Prioriza por timestamp (mais recente primeiro)
                            if value_time > most_recent_time:
                                most_recent = value
                                most_recent_time = value_time
                    
                    if most_recent:
                        progress_data = most_recent
            
            # Fallback: tenta obter do SESSION se disponível
            if progress_data.get('stage') == 'unknown' and hasattr(self.request, 'SESSION'):
                progress_key = 'pdf_processing_progress'
                session_data = self.request.SESSION.get(progress_key)
                if session_data:
                    progress_data = session_data
                    # Atualiza cache com dados do SESSION
                    _set_progress_in_cache(session_id, progress_data)
            
            # Retorna como JSON
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
        Atualiza o progresso do processamento no request e no cache global.
        stage: etapa atual (validating, resizing, optimizing, ocr, finalizing)
        message: mensagem para o usuário
        progress: porcentagem (0-100), None para auto-calcular
        details: detalhes adicionais
        """
        try:
            if not hasattr(self, 'request'):
                return
            
            # Obtém ID da sessão/requisição
            session_id = _get_session_id(self.request)
            
            # Verifica se há progresso anterior (pode ser retry)
            previous_progress = _get_progress_from_cache(session_id)
            previous_progress_pct = previous_progress.get('progress', 0)
            
            # Calcula o progresso atual
            current_progress = progress if progress is not None else 0
            
            # Se for retry e o progresso anterior for maior, mantém o anterior como mínimo
            # Mas permite avançar se o novo progresso for maior
            if previous_progress.get('stage') not in ('unknown', 'complete', 'error', 'initializing'):
                # Se a mensagem anterior contém "[Retry]", é um retry em andamento
                if '[Retry]' in previous_progress.get('message', ''):
                    # Mantém o progresso anterior como mínimo, mas permite avançar
                    if current_progress < previous_progress_pct:
                        current_progress = previous_progress_pct
                        # Adiciona indicação de que está mantendo progresso mínimo
                        if '[Retry]' not in message:
                            message = f"[Retry] {message}"
            
            progress_data = {
                'stage': stage,
                'message': message,
                'progress': current_progress,
                'details': details,
                'timestamp': time.time()
            }
            
            # Armazena no cache global (thread-safe)
            _set_progress_in_cache(session_id, progress_data)
            
            # Também armazena no SESSION se disponível (para compatibilidade)
            if hasattr(self.request, 'SESSION'):
                try:
                    progress_key = 'pdf_processing_progress'
                    self.request.SESSION[progress_key] = progress_data
                    # Força persistência do SESSION
                    try:
                        self.request.SESSION._p_changed = True
                    except:
                        pass
                except Exception:
                    pass
            
            # Log apenas para erros ou conclusão
            if stage in ('error', 'complete'):
                logging.info(f"[PROGRESS] {stage} - {message} ({current_progress}%)")
        except Exception:
            # Não falha se não conseguir atualizar progresso
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
            
            # Detecta possível retry baseado no hash do arquivo
            file_hash = self._get_file_hash(original_data)
            cache_key = f"pdf_process_{file_hash}"
            
            # Verifica se já está processando (pode ser retry do Zope)
            is_retry = False
            if hasattr(self.request, 'SESSION'):
                cache_data = self.request.SESSION.get(cache_key)
                if cache_data:
                    elapsed = time.time() - cache_data.get('start_time', start_time)
                    is_retry = True
                    logging.info(f'[RETRY_DETECTED] Possível retry detectado (hash: {file_hash[:8]}...), tempo decorrido: {elapsed:.2f}s')
            
            # Inicializa progresso ANTES de qualquer processamento
            # Se for retry, mantém o progresso anterior ou mostra mensagem de reprocessamento
            session_id = _get_session_id(self.request)
            if is_retry:
                # Verifica se há progresso anterior no cache
                previous_progress = _get_progress_from_cache(session_id)
                
                if previous_progress.get('stage') not in ('unknown', 'complete', 'error'):
                    # Mantém o progresso anterior e adiciona indicação de retry
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
                    # Não reinicia do zero, continua a partir do progresso anterior
                else:
                    # Se não há progresso anterior válido, inicia normalmente mas indica retry
                    self._update_progress('processing', '[Retry] Reprocessando após ConflictError...', 20, 'Zope detectou conflito e está reprocessando')
            else:
                # Inicializa progresso normalmente
                self._update_progress('initializing', 'Iniciando processamento...', 0, 'Preparando arquivo para processamento')
                time.sleep(0.1) # Pequeno delay para garantir que o SESSION seja salvo
                
                # Atualiza para leitura
                self._update_progress('reading', 'Lendo arquivo...', 5, 'Carregando arquivo PDF')
            
            # Marca como processando
            if hasattr(self.request, 'SESSION'):
                self.request.SESSION[cache_key] = {'status': 'processing', 'start_time': start_time}
            
            # Se for retry e já tem progresso anterior, não atualiza para validação (mantém o progresso anterior)
            # Caso contrário, atualiza normalmente
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
                # Marca como completo no cache
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
                # Marca como completo no cache
                if hasattr(self.request, 'SESSION'):
                    self.request.SESSION[cache_key] = {
                        'status': 'complete',
                        'start_time': start_time,
                        'end_time': time.time(),
                        'reduction': reduction,
                        'optimized_size': optimized_size
                    }
                # Só marca como completo DEPOIS que tudo terminou
                self._update_progress('complete', 'Processamento concluído', 100, 
                                     f'Redução: {reduction:.1f}% ({optimized_size/1024:.1f} KB)')
                return result_data

        except (PDFSizeExceededError, PDFPageLimitExceededError) as e:
            logging.error(str(e))
            raise
        except PDFIrrecuperavelError:
            raise
        except Exception as e:
            logging.error(f"Erro inesperado: {str(e)}", exc_info=True)
            raise ValueError(f"Falha no processamento: {str(e)}")
