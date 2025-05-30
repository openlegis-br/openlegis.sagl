# -*- coding: utf-8 -*-
from io import BytesIO
import logging
import re
import warnings
from functools import lru_cache, wraps
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union, BinaryIO, Iterator

# Bibliotecas de terceiros
from pypdf import PdfReader
from pypdf.errors import PdfReadError
import fitz  # PyMuPDF
import pikepdf
from dateutil.parser import parse
from asn1crypto import cms

# Zope
from five import grok
from zope.interface import Interface

CPF_LENGTH = 11
MAX_TITLE_LENGTH = 200
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

PDFData = Union[bytes, bytearray]
SignatureData = Dict[str, Any]
SignerInfo = Dict[str, Optional[str]]

logging.basicConfig(level=logging.warning, format='%(asctime)s - %(levelname)s - %(message)s')
warnings.simplefilter("once", RuntimeWarning)

def warning_to_log(message: str, category: type, filename: str, lineno: int, file=None, line=None) -> None:
    logging.getLogger().warning(f"{category.__name__}: {message} (linha {lineno})")

warnings.showwarning = warning_to_log

def timed_lru_cache(seconds: int = 300, maxsize: int = 128):
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

class PDFProcessor:
    def __init__(self):
        self._cached_pdf_reader = None
        self._cached_pdf_stream = None

    @contextmanager
    def _get_pdf_reader(self, file_stream: BytesIO) -> Iterator[PdfReader]:
        current_stream = file_stream.getvalue()
        if (self._cached_pdf_reader is None or self._cached_pdf_stream != current_stream):
            self._cached_pdf_stream = current_stream
            try:
                reader = PdfReader(BytesIO(self._cached_pdf_stream))
                # Força leitura de um objeto para validar a xref
                _ = reader.pages[0]
                self._cached_pdf_reader = reader
            except Exception as e:
                logging.warning("Erro ao ler o PDF com PyPDF (tentando recuperar): %s", e)
                repaired = self.repair_with_pikepdf(current_stream)
                try:
                    self._cached_pdf_reader = PdfReader(BytesIO(repaired))
                    # Força leitura novamente
                    _ = self._cached_pdf_reader.pages[0]
                except Exception as inner_e:
                    logging.error("PDF corrompido e irrecuperável após tentativa de reparo: %s", inner_e)
                    raise ValueError("PDF corrompido e irrecuperável") from inner_e
        yield self._cached_pdf_reader


    @staticmethod
    @timed_lru_cache(seconds=3600, maxsize=32)
    def format_cpf(cpf: Optional[str]) -> str:
        if not cpf or not isinstance(cpf, str):
            return ""
        cleaned = re.sub(r'[^0-9]', '', cpf)
        if len(cleaned) != CPF_LENGTH:
            return cpf
        return f"{cleaned[:3]}.{cleaned[3:6]}.{cleaned[6:9]}-{cleaned[9:]}"

    @staticmethod
    @timed_lru_cache(seconds=3600, maxsize=32)
    def format_datetime(dt: Optional[Any]) -> Optional[str]:
        if not dt:
            return None
        try:
            return dt.strftime(DATE_FORMAT)
        except Exception as e:
            logging.warning("Erro ao formatar data: %s", e)
            return None

class PDFSignatureParser(PDFProcessor):
    def parse_signatures(self, raw_signature_data: bytes) -> List[SignerInfo]:
        if not raw_signature_data:
            return []
        try:
            info = cms.ContentInfo.load(raw_signature_data)
            signed_data = info['content']
            if 'certificates' not in signed_data or not signed_data['certificates']:
                return []
            certificates = signed_data['certificates']
            signers = []
            for cert in certificates:
                try:
                    cert_data = cert.native['tbs_certificate']
                    subject = cert_data.get('subject', {})
                    issuer = cert_data.get('issuer', {})
                    common_name = subject.get('common_name', '')
                    nome, cpf = (common_name.split(':', 1) + [''])[:2]
                    signers.append({
                        'type': subject.get('organization_name', ''),
                        'signer': nome.strip() or None,
                        'cpf': self.format_cpf(cpf.strip()),
                        'oname': issuer.get('organization_name', '')
                    })
                except Exception as e:
                    warnings.warn(f"Erro ao processar certificado individual: {e}", RuntimeWarning)
            return signers
        except Exception as e:
            warnings.warn(f"Erro ao interpretar ASN.1 da assinatura: {e}", RuntimeWarning)
            return []

    def _extract_signing_time(self, signature: Dict[str, Any]) -> Optional[str]:
        if '/M' not in signature:
            return None
        try:
            time_raw = signature['/M']
            ts_clean = time_raw[2:] if time_raw.startswith('D:') else time_raw
            ts_clean = re.sub(r"([+-]\d{2})'(\d{2})'", r"\1:\2", ts_clean)
            dt = parse(ts_clean)
            return self.format_datetime(dt)
        except Exception as e:
            logging.warning(f"Erro ao parsear timestamp de assinatura: {e}")
            return None

    def _extract_cpf_from_contents(self, raw: Optional[bytes]) -> Optional[str]:
        if not raw:
            return None
        try:
            if isinstance(raw, str):
                raw = raw.encode('utf-8')  # Garante que seja bytes
            match = re.search(rb'\d{8}(\d{11})\d*', raw) or re.search(rb'(\d{11})', raw)
            if match:
                return self.format_cpf(match.group(1).decode('ascii', errors='ignore'))
        except Exception as e:
            logging.warning(f"Erro ao extrair CPF de '/Contents': {e}")
        return None

    def _process_signature(self, signature: Dict[str, Any], filename: str) -> List[SignatureData]:
        name_field = signature.get('/Name', '')
        name, cpf_name = (name_field.split(':', 1) + [''])[:2]
        name = name.strip() or None
        cpf_name = self.format_cpf(cpf_name.strip()) if cpf_name.strip() else None

        raw_data = signature.get('/Contents')
        cpf_contents = self._extract_cpf_from_contents(raw_data)
        parsed = self.parse_signatures(raw_data) if isinstance(raw_data, bytes) else []
        signing_time = self._extract_signing_time(signature)

        signers = []
        if parsed:
            for signer in parsed:
                signers.append({
                    'signer_name': name or signer.get('signer'),
                    'signer_cpf': signer.get('cpf') or cpf_name or cpf_contents,
                    'signing_time': signing_time,
                    'signer_certificate': signer.get('oname')
                })
        elif name or cpf_name or cpf_contents:
            signers.append({
                'signer_name': name,
                'signer_cpf': cpf_name or cpf_contents,
                'signing_time': signing_time,
                'signer_certificate': ''
            })

        return signers

    @staticmethod
    def _deduplicate_signers(signers: List[SignatureData]) -> List[SignatureData]:
        seen = set()
        result = []
        for signer in signers:
            key = tuple(sorted(signer.items()))
            if key not in seen:
                seen.add(key)
                result.append(signer)
        return sorted(result, key=lambda x: x.get('signing_time') or '')

    def get_signatures_from_stream(self, file_stream: BytesIO, filename: str) -> List[SignatureData]:
        try:
            with self._get_pdf_reader(file_stream) as reader:
                try:
                    fields = reader.get_fields() or {}
                except Exception as e:
                    logging.warning("Erro ao ler campos de formulário do PDF: %s", e)
                    fields = {}

                signatures = [
                    f.value for f in fields.values()
                    if getattr(f, 'field_type', None) == '/Sig' and f.value
                ]

                all_signers = []
                for sig in signatures:
                    try:
                        all_signers.extend(self._process_signature(sig, filename))
                    except Exception as e:
                        logging.warning("Erro ao processar assinatura: %s", e)

                return self._deduplicate_signers(all_signers)
        except Exception as e:
            logging.warning("Erro geral ao extrair assinaturas: %s", e, exc_info=True)
            return []

class PDFOptimizer(PDFProcessor):
    def repair_with_pikepdf(self, pdf_bytes: PDFData) -> bytes:
        try:
            repaired = BytesIO()
            with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
                pdf.remove_unreferenced_resources()
                pdf.save(repaired, linearize=True)
            return repaired.getvalue()
        except Exception as e:
            logging.warning("Falha ao recuperar PDF com pikepdf: %s", e)
            return pdf_bytes

    def optimize_pdf(self, file_stream: BytesIO, title: Optional[str] = None) -> bytes:
        file_stream.seek(0)
        pdf_data = file_stream.getvalue()
        doc = self._open_pdf_with_fallback(pdf_data)
        self._set_pdf_title(doc, title)
        return self._save_optimized_pdf(doc, pdf_data)

    def _open_pdf_with_fallback(self, pdf_data: PDFData) -> fitz.Document:
        try:
            return fitz.open(stream=pdf_data, filetype="pdf")
        except Exception:
            repaired = self.repair_with_pikepdf(pdf_data)
            return fitz.open(stream=repaired, filetype="pdf")

    def _set_pdf_title(self, doc: fitz.Document, title: Optional[str]) -> None:
        if title:
            try:
                doc.set_metadata({'title': title[:MAX_TITLE_LENGTH]})
            except Exception as e:
                logging.warning("Erro ao definir título do PDF: %s", e)

    def _save_optimized_pdf(self, doc: fitz.Document, original_data: PDFData) -> bytes:
        output = BytesIO()
        try:
            doc.save(output, garbage=4, deflate=True, clean=True, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE)
            return output.getvalue()
        except Exception as e:
            logging.warning("Falha ao salvar com fitz: %s", e)
            return self.repair_with_pikepdf(original_data)

class PDFUploadProcessorView(grok.View, PDFSignatureParser, PDFOptimizer):
    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('otimizar_arquivo')

    def __init__(self, context, request):
        super().__init__(context, request)
        PDFProcessor.__init__(self)
        self.context = context
        self.request = request

    def optimize_file(self, file_obj: BinaryIO, title: Optional[str] = None, compressao_maxima: bool = False) -> Union[bytes, Dict[str, Any]]:
        try:
            original_data = self._read_file_data(file_obj)
            file_stream = BytesIO(original_data)

            with self._get_pdf_reader(file_stream) as reader:
                assinaturas = self.get_signatures_from_stream(file_stream, getattr(file_obj, 'filename', 'desconhecido'))
                if assinaturas:
                    logging.warning("Assinaturas digitais detectadas (%d)", len(assinaturas))
                    return {'file_stream': BytesIO(original_data), 'signatures': assinaturas}

                if self._has_form_fields(reader):
                    logging.warning("PDF contém campos de formulário")
                    return self.repair_with_pikepdf(original_data)

            original_size = len(original_data)
            doc = fitz.open(stream=original_data, filetype="pdf")
            novo_pdf = fitz.open()

            A4_RETRATO = (595, 842)
            A4_PAISAGEM = (842, 595)
            LIMIT_BYTES = 300_000
            MARGEM = 15
            ZOOM = 2.0
            recompression_applied = False

            for i, page in enumerate(doc):
                try:
                    width, height = page.rect.width, page.rect.height
                    is_paisagem = width > height

                    is_a4_retrato = abs(width - A4_RETRATO[0]) < 2 and abs(height - A4_RETRATO[1]) < 2
                    is_a4_paisagem = abs(width - A4_PAISAGEM[0]) < 2 and abs(height - A4_PAISAGEM[1]) < 2

                    pix_preview = page.get_pixmap(dpi=72)
                    try:
                        estimated_size = len(pix_preview.tobytes("png"))
                    except Exception:
                        estimated_size = 0

                    if (is_a4_retrato or is_a4_paisagem) and estimated_size <= LIMIT_BYTES:
                        novo_pdf.insert_pdf(doc, from_page=i, to_page=i)
                        logging.debug(f"Página {i+1}: mantida original (A4 {'paisagem' if is_paisagem else 'retrato'} e leve)")
                        continue

                    matrix = fitz.Matrix(ZOOM, ZOOM)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    img_bytes = pix.tobytes("jpeg", 80)

                    new_width, new_height = A4_PAISAGEM if is_paisagem else A4_RETRATO
                    new_page = novo_pdf.new_page(width=new_width, height=new_height)

                    scale = min((new_width - MARGEM) / pix.width, (new_height - MARGEM) / pix.height, 1.0)
                    img_w = pix.width * scale
                    img_h = pix.height * scale
                    offset_x = (new_width - img_w) / 2
                    offset_y = (new_height - img_h) / 2
                    rect = fitz.Rect(offset_x, offset_y, offset_x + img_w, offset_y + img_h)

                    new_page.insert_image(rect, stream=img_bytes)
                    logging.info(f"Página {i+1}: recriada como A4 {'paisagem' if is_paisagem else 'retrato'} com Matrix")
                    recompression_applied = True

                except Exception as e:
                    logging.warning(f"Erro ao processar página {i+1}: {e}")
                    try:
                        novo_pdf.insert_pdf(doc, from_page=i, to_page=i)
                    except Exception as fallback_error:
                        logging.error(f"Fallback falhou na página {i+1}: {fallback_error}")

            if not recompression_applied:
                logging.info("Nenhuma página recriada. Validando PDF original com pikepdf.")
                return self.repair_with_pikepdf(original_data)

            try:
                output = BytesIO()
                novo_pdf.save(output, garbage=4, deflate=True, clean=True)
                optimized_data = output.getvalue()
                logging.info(f"PDF otimizado: {original_size} → {len(optimized_data)} bytes")
                return self.repair_with_pikepdf(optimized_data)

            except Exception as e:
                logging.warning(f"Erro ao salvar PDF otimizado, tentando reparar com pikepdf: {e}")
                return self.repair_with_pikepdf(original_data)

        except Exception as e:
            logging.error(f"Erro inesperado ao processar PDF: {e}", exc_info=True)
            return file_obj.read()

    def _read_file_data(self, file_obj: BinaryIO) -> bytes:
        try:
            data = file_obj.read()
            if not data:
                raise ValueError("Arquivo vazio")
            return data
        except Exception as e:
            raise ValueError(f"Erro na leitura do arquivo: {e}") from e

    def _has_form_fields(self, reader: PdfReader) -> bool:
        try:
            return bool(reader.get_fields())
        except Exception as e:
            logging.warning("Erro ao verificar campos de formulário: %s", e)
            return False

    def render(self, filename: BinaryIO, title: Optional[str] = None) -> Any:
        try:
            return self.optimize_file(filename, title)
        except Exception as e:
            logging.critical("Erro durante o render(): %s", e, exc_info=True)
            filename.seek(0)
            return filename.read()
