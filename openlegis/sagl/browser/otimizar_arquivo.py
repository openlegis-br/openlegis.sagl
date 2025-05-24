# -*- coding: utf-8 -*-
from io import BytesIO
import logging
import re
import warnings
from functools import lru_cache, wraps
from contextlib import contextmanager
from datetime import datetime, timedelta
import time
from typing import Optional, List, Dict, Any, Union, BinaryIO, Iterator

# Bibliotecas de terceiros
from pypdf import PdfReader
from pypdf.errors import PdfReadError
import fitz  # PyMuPDF
from fitz import FileDataError, EmptyFileError
import pikepdf
from dateutil.parser import parse
from dateutil.parser._parser import ParserError
from asn1crypto import cms

# Zope
from five import grok
from zope.interface import Interface

# Constantes
CPF_LENGTH = 11
MAX_TITLE_LENGTH = 200
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Tipos
PDFData = Union[bytes, bytearray]
SignatureData = Dict[str, Any]
SignerInfo = Dict[str, Optional[str]]

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
warnings.simplefilter("once", RuntimeWarning)

def warning_to_log(message: str, category: type, filename: str, lineno: int, file=None, line=None) -> None:
    """Redireciona avisos do Python para o sistema de logs."""
    logging.getLogger().warning(f"{category.__name__}: {message} (linha {lineno})")

warnings.showwarning = warning_to_log

def timed_lru_cache(seconds: int = 300, maxsize: int = 128):
    """Decorador que adiciona timeout ao lru_cache"""
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
    """Classe base para operações comuns com PDF."""

    def __init__(self):
        self._cached_pdf_reader = None
        self._cached_pdf_stream = None

    @contextmanager
    def _get_pdf_reader(self, file_stream: BytesIO) -> Iterator[PdfReader]:
        current_stream = file_stream.getvalue()
        if (self._cached_pdf_reader is None or self._cached_pdf_stream != current_stream):
            self._cached_pdf_stream = current_stream
            try:
                self._cached_pdf_reader = PdfReader(BytesIO(self._cached_pdf_stream))
            except PdfReadError as e:
                logging.warning("Erro ao ler o PDF (tentando recuperar): %s", e)
                # Tenta reparar com pikepdf e reler
                repaired = self.repair_with_pikepdf(current_stream)
                if repaired:
                    self._cached_pdf_reader = PdfReader(BytesIO(repaired))
                else:
                    raise ValueError("PDF corrompido e irrecuperável") from e
        yield self._cached_pdf_reader

    @staticmethod
    @lru_cache(maxsize=32)
    def format_cpf(cpf: Optional[str]) -> str:
        """Formata um CPF com pontuação padrão."""
        if not cpf or not isinstance(cpf, str):
            return ""
        cleaned = re.sub(r'[^0-9]', '', cpf)
        if len(cleaned) != CPF_LENGTH:
            return cpf
        return f"{cleaned[:3]}.{cleaned[3:6]}.{cleaned[6:9]}-{cleaned[9:]}"

    @staticmethod
    @timed_lru_cache(seconds=3600, maxsize=32)  # 1 hora de cache
    @staticmethod
    def format_datetime(dt: Optional[Any]) -> Optional[str]:
        """Formata data/hora para string padrão."""
        if not dt:
            return None
        try:
            return dt.strftime(DATE_FORMAT)
        except Exception as e:
            logging.warning("Erro ao formatar data: %s", e)
            return None


class PDFSignatureParser(PDFProcessor):
    """Responsável por extrair e interpretar assinaturas digitais."""

    def parse_signatures(self, raw_signature_data: bytes) -> List[SignerInfo]:
        """Extrai dados da assinatura digital usando ASN.1 CMS."""
        if not raw_signature_data:
            return []

        try:
            info = cms.ContentInfo.load(raw_signature_data)
            signed_data = info['content']
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
                        'signer': nome.strip(),
                        'cpf': self.format_cpf(cpf.strip()),
                        'oname': issuer.get('organization_name', '')
                    })
                except Exception as e:
                    warnings.warn(f"Erro ao processar certificado: {e}", RuntimeWarning)
            return signers

        except Exception as e:
            warnings.warn(f"Erro ao interpretar assinatura digital: {e}", RuntimeWarning)
            return []

    def extract_cpf_from_contents(self, raw_signature_data: bytes, filename: str) -> Optional[str]:
        """Tenta extrair CPF dos dados binários brutos da assinatura."""
        if not raw_signature_data:
            return None

        try:
            if not isinstance(raw_signature_data, bytes):
                raw_signature_data = raw_signature_data.encode('ascii')

            patterns = [
                re.compile(rb'L\x01\x03\x01\xa0/\x04-\d{8}(\d{11})'),
                re.compile(rb'(\d{11})')
            ]

            for pattern in patterns:
                match = pattern.search(raw_signature_data)
                if match:
                    return self.format_cpf(match.group(1).decode('ascii'))

            return None
        except Exception as e:
            logging.warning("Erro ao extrair CPF do arquivo '%s': %s", filename, e)
            return None

    def get_signatures_from_stream(self, file_stream: BytesIO, filename: str) -> List[SignatureData]:
        """Processa todas as assinaturas encontradas no PDF."""
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

                signers = []
                for sig in signatures:
                    try:
                        signers.extend(self._process_signature(sig, filename))
                    except Exception as e:
                        logging.warning("Erro ao processar assinatura: %s", e)

                return self._deduplicate_signers(signers)
        except Exception as e:
            logging.warning("Erro geral ao extrair assinaturas: %s", e, exc_info=True)
            return []

    def _process_signature(self, signature: Dict[str, Any], filename: str) -> List[SignatureData]:
        """Processa uma assinatura específica extraindo nome, CPF, data e certificado."""
        signing_time = self._extract_signing_time(signature)
        name_field = signature.get('/Name', '')
        name, cpf_name = (name_field.split(':', 1) + [''])[:2]
        cpf_name = self.format_cpf(cpf_name.strip()) if cpf_name.strip() else None

        raw_data = signature.get('/Contents')
        cpf_raw = self.extract_cpf_from_contents(raw_data, filename)
        parsed = self.parse_signatures(raw_data) if isinstance(raw_data, bytes) else []

        cpf_final = (parsed[0]['cpf'] if parsed else None) or cpf_name or cpf_raw

        return [{
            'signer_name': name.strip(),
            'signer_cpf': cpf_final,
            'signing_time': signing_time,
            'signer_certificate': signer.get('oname', '') if signer else ''
        } for signer in parsed]

    def _extract_signing_time(self, signature: Dict[str, Any]) -> Optional[str]:
        """Extrai a data/hora da assinatura (campo /M)."""
        if '/M' not in signature:
            return None
        try:
            time_str = signature['/M'][2:].strip("'").replace("'", ":")
            return self.format_datetime(parse(time_str))
        except Exception as e:
            logging.warning("Erro ao interpretar data de assinatura: %s", e)
            return None

    @staticmethod
    def _deduplicate_signers(signers: List[SignatureData]) -> List[SignatureData]:
        """Remove assinaturas duplicadas e ordena por data."""
        seen = set()
        unique = [s for s in signers if not (tuple(s.items()) in seen or seen.add(tuple(s.items())))]
        return sorted(unique, key=lambda x: x.get('signing_time') or '')


class PDFOptimizer(PDFProcessor):
    """Responsável por otimizar e tentar recuperar arquivos PDF corrompidos."""

    def repair_with_pikepdf(self, pdf_bytes: PDFData) -> Optional[bytes]:
        try:
            repaired = BytesIO()
            with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
                pdf.save(repaired)
            repaired.seek(0)
            logging.info("PDF recuperado com sucesso usando pikepdf")
            return repaired.getvalue()
        except Exception as e:
            logging.warning("Falha ao recuperar PDF com pikepdf: %s", e)
            return None

    def optimize_pdf(self, file_stream: BytesIO, title: Optional[str] = None) -> bytes:
        file_stream.seek(0)
        pdf_data = file_stream.getvalue()

        if not pdf_data:
            raise ValueError("Arquivo PDF vazio")

        try:
            doc = self._open_pdf_with_fallback(pdf_data)
            self._set_pdf_title(doc, title)
            return self._save_optimized_pdf(doc, pdf_data)
        except Exception as e:
            logging.warning("Erro crítico na otimização: %s", e)
            raise RuntimeError("Falha na otimização do PDF") from e

    def _open_pdf_with_fallback(self, pdf_data: PDFData) -> fitz.Document:
        try:
            return fitz.open(stream=pdf_data)
        except Exception as e:
            logging.warning("Falha ao abrir com fitz: %s", e)
            repaired = self.repair_with_pikepdf(pdf_data)
            if repaired:
                return fitz.open(stream=repaired)
            raise ValueError("PDF inválido e não foi possível recuperar") from e

    def _set_pdf_title(self, doc: fitz.Document, title: Optional[str]) -> None:
        if title:
            try:
                doc.set_metadata({'title': title[:MAX_TITLE_LENGTH]})
            except Exception as e:
                logging.warning("Erro ao definir título do PDF: %s", e)

    def _save_optimized_pdf(self, doc: fitz.Document, original_data: PDFData) -> bytes:
        output = BytesIO()
        try:
            doc.save(output, garbage=3, deflate=True, clean=True, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE)
            return output.getvalue()
        except Exception as e:
            logging.warning("Falha ao salvar com fitz: %s", e)
            repaired = self.repair_with_pikepdf(original_data)
            return repaired if repaired else original_data


class PDFUploadProcessorView(grok.View, PDFSignatureParser, PDFOptimizer):
    """View Zope para processar uploads de PDF com otimização e extração de assinatura."""

    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('otimizar_arquivo')

    def __init__(self, context, request):
        # Inicialização padrão do Zope
        super().__init__(context, request)

        # Inicializa atributos da superclasse PDFProcessor
        PDFProcessor.__init__(self)

        # Armazena o contexto e a requisição
        self.context = context
        self.request = request

    def optimize_file(self, file_obj: BinaryIO, title: Optional[str] = None) -> Union[bytes, Dict[str, Any]]:
        try:
            original_data = self._read_file_data(file_obj)
            file_stream = BytesIO(original_data)

            with self._get_pdf_reader(file_stream) as reader:
                assinaturas = self.get_signatures_from_stream(file_stream, getattr(file_obj, 'filename', 'desconhecido'))
                if assinaturas:
                    logging.info("Assinaturas digitais detectadas (%d)", len(assinaturas))
                    return {'file_stream': BytesIO(original_data), 'signatures': assinaturas}

                if self._has_form_fields(reader):
                    logging.info("PDF contém campos de formulário")
                    return original_data

                return self._attempt_optimization(original_data, title)

        except ValueError as e:
            logging.warning("Arquivo PDF inválido: %s", e)
            return original_data
        except Exception as e:
            logging.warning("Erro inesperado ao processar PDF: %s", e, exc_info=True)
            return original_data

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

    def _attempt_optimization(self, original_data: bytes, title: Optional[str]) -> bytes:
        try:
            optimized = self.optimize_pdf(BytesIO(original_data), title)
            if optimized and len(optimized) < len(original_data):
                logging.info("Otimização bem-sucedida: reduziu de %d para %d bytes",
                             len(original_data), len(optimized))
                return optimized
            return original_data
        except Exception as e:
            logging.warning("Falha na tentativa de otimização: %s", e)
            return original_data

    def render(self, filename: BinaryIO, title: Optional[str] = None) -> Any:
        try:
            return self.optimize_file(filename, title)
        except Exception as e:
            logging.critical("Erro durante o render(): %s", e, exc_info=True)
            filename.seek(0)
            return filename.read()
