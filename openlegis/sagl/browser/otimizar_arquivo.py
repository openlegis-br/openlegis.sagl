# -*- coding: utf-8 -*-
import gc
import re
import logging
import warnings
import tempfile
import os
from io import BytesIO
from PIL import Image
from typing import Any, List, Optional, Dict, Union, BinaryIO, Iterator, Generator, Tuple
from functools import lru_cache, wraps
from contextlib import contextmanager
from datetime import datetime, timedelta

import fitz  # PyMuPDF
import pikepdf
import pytesseract
from pypdf import PdfReader
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
MAX_TITLE_LENGTH = 200
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
MAX_PDF_SIZE = 100 * 1024 * 1024  # 100MB
MAX_PAGES = 500
PNG_COMPRESSION_LEVEL = 6
A4_PORTRAIT = (595, 842)
A4_LANDSCAPE = (842, 595)
DEFAULT_DPI = 300

PDFData = Union[bytes, bytearray]
SignatureData = Dict[str, Any]
SignerInfo = Dict[str, Optional[str]]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_processor.log'),
        logging.StreamHandler()
    ]
)
warnings.simplefilter("once", RuntimeWarning)

# ******************************************
# EXCEPTIONS
# ******************************************
class PDFIrrecuperavelError(Exception):
    """Exceção para PDFs corrompidos e irrecuperáveis"""
    pass

class PDFSizeExceededError(Exception):
    """Exceção para PDFs que excedem o tamanho máximo"""
    pass

class PDFPageLimitExceededError(Exception):
    """Exceção para PDFs com muitas páginas"""
    pass

# ******************************************
# CORE UTILITIES
# ******************************************
def timed_lru_cache(seconds: int = 300, maxsize: int = 128):
    """Decorator for time-limited caching"""
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
    """Formata CPF com pontos e traço"""
    if not cpf or not isinstance(cpf, str):
        return ""
    cleaned = re.sub(r'[^0-9]', '', cpf)
    if len(cleaned) != CPF_LENGTH:
        return cpf
    return f"{cleaned[:3]}.{cleaned[3:6]}.{cleaned[6:9]}-{cleaned[9:]}"

def format_datetime(dt: Optional[Any]) -> Optional[str]:
    """Formata datetime para string padrão"""
    if not dt:
        return None
    try:
        return dt.strftime(DATE_FORMAT)
    except Exception:
        return None

def validate_pdf_size(pdf_data: bytes) -> None:
    """Valida se o PDF não excede o tamanho máximo"""
    if len(pdf_data) > MAX_PDF_SIZE:
        raise PDFSizeExceededError(
            f"O arquivo PDF excede o tamanho máximo de {MAX_PDF_SIZE/1024/1024}MB"
        )

# ******************************************
# PDF PROCESSOR CORE
# ******************************************
class PDFProcessor:
    """Classe base para processamento de PDF"""

    def __init__(self):
        self._cached_pdf_reader = None
        self._cached_pdf_stream = None
        self._memory_threshold = 50 * 1024 * 1024  # 50MB

    @contextmanager
    def _get_pdf_reader(self, file_stream: BytesIO) -> Iterator[PdfReader]:
        """Context manager para leitura segura de PDFs"""
        current_stream = file_stream.getvalue()
        
        if len(current_stream) > self._memory_threshold:
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(current_stream)
                tmp.flush()
                try:
                    with open(tmp.name, 'rb') as f:
                        reader = PdfReader(f)
                        _ = reader.pages[0]  # Test access
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
        """Tenta reparar PDF corrompido"""
        try:
            with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
                output = BytesIO()
                pdf.save(output, linearize=True, compress_streams=True)
                return output.getvalue()
        except Exception:
            return pdf_bytes  # Fallback para o original

    def _read_file_chunked(self, file_obj: BinaryIO) -> bytes:
        """Leitura eficiente em chunks"""
        file_obj.seek(0)
        buffer = BytesIO()
        for chunk in iter(lambda: file_obj.read(8192), b''):
            buffer.write(chunk)
        return buffer.getvalue()

    def _validate_pdf(self, pdf_data: bytes) -> None:
        """Validações básicas do PDF"""
        validate_pdf_size(pdf_data)
        
        try:
            with fitz.open(stream=pdf_data, filetype="pdf") as doc:
                if doc.page_count > MAX_PAGES:
                    raise PDFPageLimitExceededError(
                        f"PDF contém {doc.page_count} páginas (limite: {MAX_PAGES})"
                    )
        except Exception as e:
            raise PDFIrrecuperavelError(f"PDF inválido: {str(e)}")

# ******************************************
# SIGNATURE HANDLING
# ******************************************
class PDFSignatureParser(PDFProcessor):
    """Processamento de assinaturas digitais em PDFs"""

    def parse_signatures(self, raw_signature_data: bytes) -> Generator[SignerInfo, None, None]:
        """Extrai informações de assinaturas digitais"""
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
        """Obtém assinaturas de um stream PDF"""
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
        """Processa dados individuais de assinatura"""
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
        """Extrai timestamp de assinatura"""
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
        """Tenta extrair CPF dos dados brutos"""
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
# OCR PROCESSING
# ******************************************
def gerar_ocr_pdf(img_path: str) -> bytes:
    """Gera PDF com OCR a partir de imagem"""
    try:
        with Image.open(img_path) as img:
            ocr_pdf = pytesseract.image_to_pdf_or_hocr(
                img,
                lang='por+eng',
                extension='pdf',
                nice=10  # Prioridade mais baixa
            )
            return ocr_pdf
    except Exception as e:
        logging.error(f"OCR falhou: {str(e)}")
        raise RuntimeError(f"Falha no OCR: {str(e)}")

# ******************************************
# MAIN PROCESSOR
# ******************************************
class PDFUploadProcessorView(grok.View, PDFSignatureParser):
    """Visualização principal para processamento de PDFs"""

    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('otimizar_arquivo')

    def __init__(self, context, request):
        super().__init__(context, request)
        PDFProcessor.__init__(self)

    def render(
        self,
        filename: BinaryIO,
        title: Optional[str] = None,
        **kwargs
    ) -> Any:
        try:
            # 1. Leitura e validação
            file_obj = filename
            original_data = self._read_file_chunked(file_obj)
            self._validate_pdf(original_data)

            # 2. Verificação de assinaturas
            assinaturas = self._verificar_assinaturas(original_data)
            if assinaturas:
                logging.warning("Assinaturas digitais detectadas (%d)", len(assinaturas))
                return {'file_stream': BytesIO(original_data), 'signatures': assinaturas}
            else:
                # 3. Otimização principal
                result_data = self._otimizar_pdf(original_data)

            return result_data

        except (PDFSizeExceededError, PDFPageLimitExceededError) as e:
            logging.error(str(e))
            raise
        except PDFIrrecuperavelError:
            raise
        except Exception as e:
            logging.error(f"Erro inesperado: {str(e)}", exc_info=True)
            raise ValueError(f"Falha no processamento: {str(e)}")

    def _verificar_assinaturas(self, pdf_data: bytes) -> Optional[List[SignatureData]]:
        """Verifica se o PDF contém assinaturas válidas"""
        try:
            with BytesIO(pdf_data) as stream:
                signatures = self.get_signatures_from_stream(stream, "upload.pdf")
                return signatures if signatures else None
        except Exception as e:
            logging.warning(f"Verificação de assinaturas falhou: {str(e)}")
            return None

    def _otimizar_pdf(self, pdf_data: bytes) -> bytes:
        """Executa a otimização do PDF com OCR apenas em páginas sem texto"""
        try:
            with fitz.open(stream=pdf_data, filetype="pdf") as doc:
                if doc.page_count > MAX_PAGES:
                    raise PDFPageLimitExceededError(
                        f"PDF muito grande ({doc.page_count} páginas)"
                    )

                # Tenta otimização inteligente primeiro
                optimized = self._otimizacao_inteligente(doc)
                if optimized:
                    return optimized

                # Fallback para rasterização + OCR
                return self._otimizacao_padrao(doc)
        except Exception as e:
            raise PDFIrrecuperavelError(f"Falha na otimização: {str(e)}")

    def _otimizacao_inteligente(self, doc: fitz.Document) -> Optional[bytes]:
        """Tenta otimização mantendo vetores quando possível"""
        novo_pdf = fitz.open()
        recompression_applied = False

        try:
            for i, page in enumerate(doc):
                try:
                    # Verifica se a página contém texto
                    texto_pagina = page.get_text()
                    if texto_pagina.strip():  # Se contém texto, mantém como vetor
                        novo_pdf.insert_pdf(doc, from_page=i, to_page=i)
                        continue

                    # Se não contém texto, processa como imagem
                    width, height = page.rect.width, page.rect.height
                    is_paisagem = width > height
                    target_size = A4_LANDSCAPE if is_paisagem else A4_PORTRAIT

                    matrix = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    
                    # Usando Pillow para controle de qualidade JPEG
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=90)
                    img_bytes = buffer.getvalue()

                    new_page = novo_pdf.new_page(width=target_size[0], height=target_size[1])
                    scale = min(
                        (target_size[0] - 20) / pix.width,
                        (target_size[1] - 20) / pix.height
                    )
                    rect = fitz.Rect(
                        (target_size[0] - pix.width * scale) / 2,
                        (target_size[1] - pix.height * scale) / 2,
                        (target_size[0] + pix.width * scale) / 2,
                        (target_size[1] + pix.height * scale) / 2
                    )
                    new_page.insert_image(rect, stream=img_bytes)
                    recompression_applied = True

                except Exception as e:
                    logging.warning(f"Página {i+1} falhou: {str(e)}")
                    novo_pdf.insert_pdf(doc, from_page=i, to_page=i)

            if not recompression_applied:
                return None

            output = BytesIO()
            novo_pdf.save(output, garbage=4, deflate=True, clean=True)
            return output.getvalue()
        finally:
            novo_pdf.close()

    def _otimizacao_padrao(self, doc: fitz.Document) -> bytes:
        """Otimização padrão com rasterização + OCR apenas para páginas sem texto"""
        novo_pdf = fitz.open()
        temp_files = []

        try:
            for i, page in enumerate(doc):
                try:
                    # Verifica se a página já tem texto legível
                    texto_pagina = page.get_text()
                    if texto_pagina.strip():  # Se contém texto, copia sem OCR
                        novo_pdf.insert_pdf(doc, from_page=i, to_page=i)
                        continue

                    # Se NÃO contém texto, rasteriza e aplica OCR
                    pix = page.get_pixmap(dpi=DEFAULT_DPI)
                    temp_img = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    pix.save(temp_img.name)
                    temp_files.append((temp_img.name, page.rect))

                    # Processa OCR para a página atual
                    try:
                        ocr_pdf = gerar_ocr_pdf(temp_img.name)
                        new_page = novo_pdf.new_page(width=page.rect.width, height=page.rect.height)
                        new_page.insert_image(page.rect, filename=temp_img.name)
                        
                        if ocr_pdf:
                            with fitz.open(stream=ocr_pdf, filetype="pdf") as ocr_doc:
                                new_page.show_pdf_page(page.rect, ocr_doc, 0, overlay=True)
                    except Exception as e:
                        logging.warning(f"OCR falhou para página {i+1}: {str(e)}")
                        novo_pdf.insert_pdf(doc, from_page=i, to_page=i)

                except Exception as e:
                    logging.warning(f"Página {i+1} falhou: {str(e)}")
                    novo_pdf.insert_pdf(doc, from_page=i, to_page=i)

            output = BytesIO()
            novo_pdf.save(output, garbage=4, deflate=True, clean=True)
            return output.getvalue()
        finally:
            novo_pdf.close()
            for img_path, _ in temp_files:
                try:
                    os.unlink(img_path)
                except Exception:
                    pass
