# -*- coding: utf-8 -*-
from io import BytesIO
import logging
import re
import warnings
from functools import lru_cache
from contextlib import contextmanager

# Third-party imports
from pypdf import PdfReader
from pypdf.errors import PdfReadError
import fitz
from fitz import FileDataError, EmptyFileError
import pikepdf
from dateutil.parser import parse
from dateutil.parser._parser import ParserError
from asn1crypto import cms

# Zope imports
from five import grok
from zope.interface import Interface

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
warnings.simplefilter("once", RuntimeWarning)

def custom_warning_to_log(message, category, filename, lineno, file=None, line=None):
    logging.getLogger().warning(f"{category.__name__}: {message} (linha {lineno})")

warnings.showwarning = custom_warning_to_log

class PDFUploadProcessorView(grok.View):
    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('otimizar_arquivo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_pdf_reader = None
        self._cached_pdf_stream = None

    @contextmanager
    def _get_pdf_reader(self, file_stream):
        try:
            current_stream = file_stream.getvalue()
            if self._cached_pdf_reader is None or self._cached_pdf_stream != current_stream:
                self._cached_pdf_stream = current_stream
                self._cached_pdf_reader = PdfReader(BytesIO(self._cached_pdf_stream))
            yield self._cached_pdf_reader
        except PdfReadError as e:
            logging.warning(f"Erro na leitura do PDF: {e}", exc_info=True)
            raise ValueError("O arquivo PDF está corrompido ou não é válido") from e
        except Exception as e:
            logging.warning(f"Erro inesperado ao acessar PDF: {e}", exc_info=True)
            raise RuntimeError("Erro ao processar o arquivo PDF") from e

    @lru_cache(maxsize=32)
    def _format_cpf(self, cpf):
        if not cpf or not isinstance(cpf, str):
            return ""
        cleaned_cpf = re.sub(r'[^0-9]', '', cpf)
        if len(cleaned_cpf) != 11 or not cleaned_cpf.isdigit():
            return cpf
        return f"{cleaned_cpf[:3]}.{cleaned_cpf[3:6]}.{cleaned_cpf[6:9]}-{cleaned_cpf[9:]}"

    def _format_datetime(self, dt):
        if not dt:
            return None
        try:
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (AttributeError, TypeError) as e:
            logging.warning(f"Formato de data inválido: {e}")
            return None

    def parse_signatures(self, raw_signature_data):
        if not raw_signature_data:
            return []

        try:
            info = cms.ContentInfo.load(raw_signature_data)
            signed_data = info['content']
            certificates = signed_data['certificates']
            signer_infos = signed_data['signer_infos'][0]

            signers = []
            for cert in certificates:
                try:
                    cert_data = cert.native['tbs_certificate']
                    subject = cert_data.get('subject', {})
                    issuer = cert_data.get('issuer', {})

                    common_name = subject.get('common_name', '')
                    name_parts = common_name.split(':', 1) if common_name else ['', '']

                    signers.append({
                        'type': subject.get('organization_name', ''),
                        'signer': name_parts[0],
                        'cpf': self._format_cpf(name_parts[1] if len(name_parts) > 1 else ''),
                        'oname': issuer.get('organization_name', '')
                    })
                except Exception as e:
                    warnings.warn(f"Erro ao processar certificado individual: {e}", RuntimeWarning)
                    continue

            return signers

        except (ValueError, KeyError, IndexError) as e:
            warnings.warn(f"Assinatura malformada ou incompleta: {e}", RuntimeWarning)
            return []
        except Exception as e:
            warnings.warn(f"Erro inesperado ao analisar assinatura: {e}", RuntimeWarning)
            return []

    def _extrair_cpf_do_contents(self, raw_signature_data, original_filename):
        if not raw_signature_data:
            return None

        try:
            if not isinstance(raw_signature_data, bytes):
                if isinstance(raw_signature_data, str):
                    raw_signature_data = raw_signature_data.encode('ascii')
                else:
                    return None

            CPF_REGEX = re.compile(rb'L\x01\x03\x01\xa0/\x04-\d{8}(\d{11})\d*\x00*\xa0\x17\x06\x05`L')
            GENERIC_CPF_REGEX = re.compile(rb'(\d{11})')

            for pattern in [CPF_REGEX, GENERIC_CPF_REGEX]:
                match = pattern.search(raw_signature_data)
                if match:
                    try:
                        cpf = match.group(1).decode('ascii')
                        return self._format_cpf(cpf)
                    except (UnicodeDecodeError, AttributeError) as e:
                        logging.warning(f"CPF encontrado mas formato inválido: {e}")
                        continue

            return None

        except Exception as e:
            logging.warning(f"Erro ao extrair CPF de {original_filename}: {e}")
            return None

    def get_signatures_from_stream(self, file_stream, original_filename):
        try:
            with self._get_pdf_reader(file_stream) as reader:
                try:
                    fields = reader.get_fields() or {}
                except Exception as e:
                    logging.warning(f"Erro ao obter campos do PDF: {e}")
                    fields = {}

                signature_field_values = []
                for f in fields.values():
                    try:
                        if hasattr(f, 'field_type') and str(f.field_type) == '/Sig' and f.value is not None:
                            signature_field_values.append(f.value)
                    except Exception as e:
                        logging.warning(f"Erro ao processar campo de assinatura: {e}")
                        continue

                lst_signers = []
                for v in signature_field_values:
                    try:
                        signing_time = None
                        if '/M' in v:
                            try:
                                time_str = v['/M'][2:].strip("'").replace("'", ":")
                                signing_time = parse(time_str)
                            except (ParserError, IndexError, AttributeError) as e:
                                logging.warning(f"Formato de data inválido na assinatura: {e}")

                        name_cpf = v.get('/Name', '').strip()
                        signer_name, signer_cpf_name = (name_cpf.split(':', 1) + [''])[:2]
                        signer_cpf_name = self._format_cpf(signer_cpf_name.strip()) if signer_cpf_name.strip() and len(signer_cpf_name.strip()) == 11 else None

                        raw_signature_data = v.get('/Contents')
                        cpf_contents = self._extrair_cpf_do_contents(raw_signature_data, original_filename)
                        signer_display_name = (v.get('/Name', '') or '').strip().split(':')[0] or '<desconhecido>'
                        if not isinstance(raw_signature_data, bytes):
                           warnings.warn(
                              f"Assinatura em formato inesperado (não-bytes) no arquivo '{original_filename}' (assinante: {signer_display_name})",
                              RuntimeWarning
                           )
                           parsed_signatures = []
                        else:
                           parsed_signatures = self.parse_signatures(raw_signature_data)

                        cpf_certificado = parsed_signatures[0].get('cpf') if parsed_signatures else None

                        signer_cpf_final = cpf_certificado or signer_cpf_name or cpf_contents

                        for attrdict in parsed_signatures:
                            lst_signers.append({
                                'signer_name': signer_name or attrdict.get('signer', ''),
                                'signer_cpf': signer_cpf_final or attrdict.get('cpf', ''),
                                'signing_time': signing_time,
                                'signer_certificate': attrdict.get('oname', ''),
                            })

                    except Exception as e:
                        logging.warning(f"Erro ao processar assinatura: {e}")
                        continue

                seen = set()
                unique_signers = [
                    d for d in lst_signers 
                    if not (tuple(d.items()) in seen or seen.add(tuple(d.items())))
                ]
                unique_signers.sort(key=lambda x: x.get('signing_time') or '')

                return unique_signers

        except Exception as e:
            logging.warning(f"Erro geral ao extrair assinaturas: {e}", exc_info=True)
            return []

    def _repair_pdf_with_pikepdf(self, pdf_bytes):
        try:
            repaired_stream = BytesIO()
            with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
                pdf.save(repaired_stream)
            repaired_stream.seek(0)
            logging.info("PDF recuperado com sucesso via pikepdf")
            return repaired_stream.getvalue()
        except Exception as e:
            logging.warning(f"Erro ao tentar reparar PDF com pikepdf: {e}", exc_info=True)
            return None

    def _optimize_pdf(self, file_stream, title):
        try:
            pdf_data = file_stream.getvalue()
            if not pdf_data:
                raise ValueError("O arquivo PDF está vazio")

            try:
                doc = fitz.open(stream=pdf_data)
            except (FileDataError, EmptyFileError) as e:
                logging.warning(f"Falha inicial ao abrir com fitz: {e}")
                repaired_data = self._repair_pdf_with_pikepdf(pdf_data)
                if repaired_data:
                    try:
                        doc = fitz.open(stream=repaired_data)
                        pdf_data = repaired_data
                    except Exception as e2:
                        raise ValueError(f"Mesmo após pikepdf, PDF inválido: {e2}") from e2
                else:
                    raise ValueError(f"Arquivo PDF inválido e pikepdf falhou: {e}") from e

            if title and isinstance(title, str):
                doc.set_metadata({'title': title[:200]})

            output_stream = BytesIO()
            try:
                doc.save(
                    output_stream,
                    garbage=3,
                    deflate=True,
                    clean=True,
                    use_objstms=True
                )
                logging.info("PDF otimizado com sucesso.")
                return output_stream.getvalue()
            except Exception as e:
                logging.warning(f"Erro ao salvar PDF otimizado: {e}")
                return pdf_data

        except Exception as e:
            logging.warning(f"Falha crítica na otimização do PDF: {e}", exc_info=True)
            raise RuntimeError(f"Falha ao otimizar PDF: {e}") from e

    def optimizeFile(self, filename, title):
        try:
            try:
                original_data = filename.read()
                if not original_data:
                    raise ValueError("Arquivo vazio")
            except Exception as e:
                raise ValueError(f"Erro ao ler arquivo: {e}") from e

            file_stream = BytesIO(original_data)

            # Verifica se o PDF tem assinatura — não otimizar se tiver
            try:
                with self._get_pdf_reader(file_stream) as reader:
                    signers_data = self.get_signatures_from_stream(file_stream, getattr(filename, 'filename', 'unknown'))
                    if signers_data:
                        logging.info(f"Arquivo assinado detectado: {len(signers_data)} assinaturas — não será otimizado")
                        return original_data
            except Exception as e:
                logging.warning(f"Erro ao verificar assinatura: {e}")

            # Tenta otimizar (com fallback via pikepdf)
            try:
                optimized_data = self._optimize_pdf(BytesIO(original_data), title)
                if optimized_data and len(optimized_data) < len(original_data):
                    logging.info(f"PDF otimizado: redução de {len(original_data)} para {len(optimized_data)} bytes")
                    return optimized_data
            except Exception as e:
                logging.warning(f"Falha na otimização: {e}")

            return original_data

        except Exception as e:
            logging.critical(f"Falha crítica no processamento: {e}", exc_info=True)
            raise RuntimeError("Falha ao processar documento") from e
  
    def render(self, filename, title):
        try:
            return self.optimizeFile(filename, title)
        except Exception as e:
            logging.critical(f"Erro no render: {e}", exc_info=True)
            filename.seek(0)
            return filename.read()
