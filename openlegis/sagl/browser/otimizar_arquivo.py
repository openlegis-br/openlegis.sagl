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

# ******************************************
# CONSTANTS AND CONFIGURATION
# ******************************************
CPF_LENGTH = 11
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
MAX_PDF_SIZE = 100 * 1024 * 1024  # 100MB
MAX_PAGES = 500
PNG_COMPRESSION_LEVEL = 9  # Máxima compressão PNG
A4_PORTRAIT = (595, 842)
A4_LANDSCAPE = (842, 595)
A4_TOLERANCE = 0.02  # 2% tolerance for page size
TEXT_DPI = 150      # Para páginas com texto
IMAGE_DPI = 150     # Para páginas sem texto
MAX_IMAGE_SIZE = 2048  # Aumentado tamanho máximo para redimensionamento
JPEG_QUALITY = 80   # Qualidade máxima para JPEG
FALLBACK_JPEG_QUALITY = 90  # Qualidade para segunda tentativa

PDFData = Union[bytes, bytearray]
SignatureData = Dict[str, Any]
SignerInfo = Dict[str, Optional[str]]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_processor.log'),
        logging.StreamHandler()
    ]
)
warnings.simplefilter("once", RuntimeWarning)

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
        self._memory_threshold = 100 * 1024 * 1024  # 100MB
        self.text_dpi = TEXT_DPI
        self.image_dpi = IMAGE_DPI
        self.max_image_size = MAX_IMAGE_SIZE
        self.jpeg_quality = JPEG_QUALITY
        self.fallback_jpeg_quality = FALLBACK_JPEG_QUALITY
        self.png_compression = PNG_COMPRESSION_LEVEL

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
                log_data['compression_rate'] = round(
                    calculate_compression_rate(original_size, compressed_size), 2
                )
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
            tmp_doc.save(buf)
        return buf.getvalue()

    def _resize_document_to_a4(self, pdf_data: bytes) -> bytes:
        with fitz.open(stream=pdf_data, filetype="pdf") as doc:
            orig_metadata = dict(doc.metadata or {})
            with fitz.open() as new_doc:
                for i, page in enumerate(doc):
                    page_pdf_bytes = self._resize_to_a4(page)
                    with fitz.open("pdf", page_pdf_bytes) as page_doc:
                        new_doc.insert_pdf(page_doc, from_page=0, to_page=0)
                new_doc.set_metadata(orig_metadata)
                output = BytesIO()
                new_doc.save(output)
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
        try:
            return len(page.read_contents() or b'')
        except:
            return 0

    def _otimizacao_inteligente(self, doc: fitz.Document) -> Optional[bytes]:
        """
        Processamento inteligente com melhor detecção de conteúdo.
        """
        with fitz.open() as novo_pdf:
            orig_metadata = dict(doc.metadata or {})
            
            for i, page in enumerate(doc):
                start_time = time.time()
                original_size = self._get_page_content_size(page)
                
                try:
                    # Verificação mais robusta de texto
                    texto_pagina = page.get_text().strip()
                    tem_texto_legivel = len(texto_pagina) > 10  # Mínimo de caracteres
                    
                    # Verifica se tem imagens significativas
                    tem_imagens = len(page.get_images()) > 0
                    
                    if tem_texto_legivel and not tem_imagens:
                        # Página principalmente textual - mantém como vetor
                        page_pdf_bytes = self._resize_to_a4(page)
                        with fitz.open("pdf", page_pdf_bytes) as page_doc:
                            novo_pdf.insert_pdf(page_doc, from_page=0, to_page=0)
                        self._log_page_processing(
                            i, "pagina_vetorial", time.time() - start_time,
                            original_size, original_size,
                            f"Texto detectado: {len(texto_pagina)} chars"
                        )
                    else:
                        # Página com imagens ou pouco texto - processa como imagem
                        processed_page_bytes = self._resize_to_a4(page)
                        with fitz.open("pdf", processed_page_bytes) as processed_doc:
                            processed_page = processed_doc[0]
                            width, height = processed_page.rect.width, processed_page.rect.height
                            is_paisagem = width > height
                            target_size = A4_LANDSCAPE if is_paisagem else A4_PORTRAIT
                            
                            # DPI adaptativo baseado no conteúdo
                            dpi = self.image_dpi if tem_imagens else self.text_dpi
                            
                            pix = processed_page.get_pixmap(dpi=dpi)
                            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            
                            # Redimensionamento inteligente
                            if max(img.size) > self.max_image_size:
                                ratio = self.max_image_size / max(img.size)
                                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                                img = img.resize(new_size, Image.LANCZOS)
                            
                            # Compressão adaptativa
                            if tem_imagens:
                                formato, qualidade, opts = "JPEG", 75, {'optimize': True, 'subsampling': 1}
                            else:
                                formato, qualidade, opts = "JPEG", 85, {'optimize': True, 'subsampling': 0}
                            
                            buffer = BytesIO()
                            img.save(buffer, format=formato, quality=qualidade, **opts)
                            img_bytes = buffer.getvalue()
                            
                            compressed_size = len(img_bytes)
                            new_page = novo_pdf.new_page(width=target_size[0], height=target_size[1])
                            new_page.insert_image(fitz.Rect(0, 0, target_size[0], target_size[1]), stream=img_bytes)
                            
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
            novo_pdf.save(output, garbage=4, deflate=True, clean=True)
            return output.getvalue()

    def _handle_ocr_errors(self, pdf_data: bytes) -> bytes:
        """
        Trata erros específicos do OCR e aplica fallbacks.
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
        Processa o PDF com OCRMyPDF de forma otimizada.
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
                
                # Configuração otimizada do OCRMyPDF - versão compatível
                ocrmypdf.ocr(
                    input_temp_name,
                    output_temp_name,
                    language='por+eng',  # Português + Inglês para melhor reconhecimento
                    output_type='pdf',
                    optimize=1,  # Otimização moderada
                    jpeg_quality=70,  # Qualidade balanceada
                    pdf_renderer='hocr',  # Mais compatível que 'sandwich'
                    skip_text=False,  # IMPORTANTE: Processa mesmo páginas com texto
                    force_ocr=False,  # Não força OCR em texto já existente
                    deskew=True,  # Corrige inclinação
                    progress_bar=False,
                    rotate_pages=True,  # Corrige rotação automática
                    clean=True,  # Limpa imagem antes do OCR
                    jobs=2,  # Reduz número de jobs para evitar conflitos
                    quiet=True  # Reduz log interno
                )
                
                # Ler o resultado
                with open(output_temp_name, 'rb') as f:
                    result = f.read()
                    
                return result
                
            except ocrmypdf.exceptions.PriorOcrFoundError:
                logging.info("PDF já contém texto pesquisável, aplicando apenas otimização")
                # Se já tem OCR, aplica apenas otimização
                return self._compress_pdf_final(pdf_data)
                
            except ocrmypdf.exceptions.InputFileError as e:
                logging.warning(f"Erro no arquivo de entrada: {e}")
                return pdf_data
                
            except Exception as ocr_error:
                logging.warning(f"OCR falhou, aplicando compressão básica: {ocr_error}")
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
                )
                return output.getvalue()
        except Exception as e:
            logging.warning(f"Compressão final falhou: {str(e)}")
            return pdf_data

    def processar_pdf(self, pdf_data: bytes) -> bytes:
        try:
            if self._verificar_assinaturas(pdf_data):
                logging.warning("PDF mantido original devido à presença de assinatura digital.")
                return pdf_data
            start_time = time.time()
            pdf_data = self._resize_document_to_a4(pdf_data)
            logging.info(f"Redimensionamento para A4 concluído em {(time.time()-start_time)*1000:.2f} ms")
            logging.info(f"Tamanho após redimensionamento: {len(pdf_data)/1024:.2f} KB")
            original_size = len(pdf_data)
            with fitz.open(stream=pdf_data) as doc:
                try:
                    pdf_otimizado = self._otimizacao_inteligente(doc)
                    if len(pdf_otimizado) > original_size * 1.10:
                        logging.warning("Otimização aumentou o tamanho do PDF, aplicando OCR padrão")
                        return self._otimizacao_padrao(pdf_data)
                    return pdf_otimizado
                except Exception as intel_error:
                    logging.warning(f"Falha na otimização inteligente: {str(intel_error)}")
                    return self._otimizacao_padrao(pdf_data)
        except Exception as e:
            logging.error(f"Erro geral no processamento: {str(e)}")
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

    def render(
        self,
        filename: BinaryIO,
        title: Optional[str] = None,
        **kwargs
    ) -> Any:
        try:
            start_time = time.time()
            file_obj = filename
            original_data = self._read_file_chunked(file_obj)
            original_size = len(original_data)
            logging.info('[READ_COMPLETE] Arquivo lido com sucesso size=%.2f KB', original_size / 1024)
            self._validate_pdf(original_data)
            logging.info('[VALIDATE_COMPLETE] Validação concluída')

            assinaturas = self._verificar_assinaturas(original_data)
            if assinaturas:
                logging.warning("Assinaturas digitais detectadas (%d). PDF mantido original.", len(assinaturas))
                return {'file_stream': BytesIO(original_data), 'signatures': assinaturas}
            else:
                result_data = self.processar_pdf(original_data)
                optimized_size = len(result_data)
                total_time = time.time() - start_time
                logging.info(
                    '[SIZE_REDUCTION] Tamanho original: %.2f KB, otimizado: %.2f KB, redução: %.2f KB (%.2f%%) - Tempo total: %.2fs',
                    original_size / 1024,
                    optimized_size / 1024,
                    (original_size - optimized_size) / 1024,
                    calculate_compression_rate(original_size, optimized_size),
                    total_time
                )
            return result_data

        except (PDFSizeExceededError, PDFPageLimitExceededError) as e:
            logging.error(str(e))
            raise
        except PDFIrrecuperavelError:
            raise
        except Exception as e:
            logging.error(f"Erro inesperado: {str(e)}", exc_info=True)
            raise ValueError(f"Falha no processamento: {str(e)}")
