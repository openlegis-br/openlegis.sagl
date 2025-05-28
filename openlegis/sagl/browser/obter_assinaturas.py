# -*- coding: utf-8 -*-
from io import BytesIO
import logging
import re
from datetime import datetime
from dateutil.parser import parse
from pypdf import PdfReader
from asn1crypto import cms
from five import grok
from zope.interface import Interface

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PDFProcessorView(grok.View):
    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('obter_assinaturas')

    def _format_cpf(self, cpf):
        if not cpf or not isinstance(cpf, str):
            return ""
        cleaned = re.sub(r'\D', '', cpf)
        return f"{cleaned[:3]}.{cleaned[3:6]}.{cleaned[6:9]}-{cleaned[9:]}" if len(cleaned) == 11 else ""

    def _parse_pdf_timestamp(self, timestamp_str):
        if not timestamp_str or not isinstance(timestamp_str, str) or not timestamp_str.startswith("D:"):
            return None
        ts_clean = timestamp_str[2:]
        try:
            ts_clean = re.sub(r"([+-]\d{2})'(\d{2})'", r"\1:\2", ts_clean)
            dt = parse(ts_clean)
            return dt
        except Exception as e:
            logging.warning(f"Falha ao parsear timestamp: {timestamp_str}. Erro: {e}")
            return None

    def _extrair_cpf_do_contents(self, raw_signature_data, filename):
        if not raw_signature_data:
            return None
        try:
            match = re.search(rb'\d{8}(\d{11})\d*', raw_signature_data)
            if not match:
                match = re.search(rb'(\d{11})', raw_signature_data)
            if match:
                return self._format_cpf(match.group(1).decode('ascii'))
        except Exception as e:
            logging.warning(f"Erro ao extrair CPF de '/Contents' ({filename}): {e}")
        return None

    def parse_signatures(self, raw_signature_data):
        if not raw_signature_data:
            return []
        try:
            info = cms.ContentInfo.load(raw_signature_data)
            signed_data = info['content']
            if 'certificates' not in signed_data or not signed_data['certificates']:
                return []
            certs = signed_data['certificates']
            signers = []
            for cert_obj in certs:
                try:
                    cert = cert_obj.native['tbs_certificate']
                    subject = cert.get('subject', {})
                    issuer = cert.get('issuer', {})
                    common_name = subject.get('common_name', '')
                    parts = common_name.split(':', 1)
                    signer = parts[0].strip() if parts else ''
                    cpf = self._format_cpf(parts[1].strip()) if len(parts) > 1 else ''
                    signers.append({
                        'type': subject.get('organization_name', ''),
                        'signer': signer,
                        'cpf': cpf,
                        'oname': issuer.get('organization_name', '')
                    })
                except Exception as e:
                    logging.warning(f"Erro ao processar certificado: {e}")
                    continue
            return signers
        except Exception as e:
            logging.warning(f"Erro ao interpretar ASN.1 da assinatura: {e}")
            return []

    def get_signatures_from_stream(self, fileStream, filename):
        try:
            reader = PdfReader(fileStream)
            fields = reader.get_fields()
            if not fields:
                return []

            lst_signers = []
            for field in fields.values():
                if field is None or str(getattr(field, 'field_type', '')) != '/Sig' or not field.value:
                    continue

                sig_data = field.value
                timestamp = self._parse_pdf_timestamp(sig_data.get('/M'))
                name_raw = sig_data.get('/Name', '')
                signer_name, signer_cpf_raw = None, None
                if ':' in name_raw:
                    name_parts = name_raw.split(':', 1)
                    signer_name = name_parts[0].strip()
                    signer_cpf_raw = self._format_cpf(name_parts[1].strip())
                else:
                    signer_name = name_raw.strip()

                raw_contents = sig_data.get('/Contents')
                cpf_contents = self._extrair_cpf_do_contents(raw_contents, filename)
                parsed_signers = self.parse_signatures(raw_contents)
                signer_cpf_final = (
                    (parsed_signers[0].get('cpf') if parsed_signers else None)
                    or signer_cpf_raw
                    or cpf_contents
                )

                for signer_info in parsed_signers or [{}]:
                    dic = {
                        'signer_name': signer_name or signer_info.get('signer'),
                        'signer_cpf': signer_cpf_final or signer_info.get('cpf'),
                        'signing_time': timestamp.isoformat() if timestamp else None,
                        'signer_certificate': signer_info.get('oname', '') if parsed_signers else ''
                    }
                    lst_signers.append(dic)

            # Deduplicação
            seen = set()
            unique_signers = []
            for signer in lst_signers:
                key = tuple(sorted(signer.items()))
                if key not in seen:
                    seen.add(key)
                    unique_signers.append(signer)

            # Ordenar por data
            unique_signers.sort(key=lambda s: parse(s['signing_time']) if s['signing_time'] else datetime.min)
            return unique_signers
        except Exception as e:
            logging.error(f"Erro ao processar o PDF '{filename}': {e}")
            return []

    def render(self, file_stream, filename):
        try:
            signers_data = self.get_signatures_from_stream(file_stream, filename)
            if signers_data:
                logging.info(f"Assinaturas encontradas em '{filename}': {signers_data}")
            else:
                logging.info(f"Nenhuma assinatura encontrada em '{filename}'")
            return signers_data
        except Exception as e:
            logging.error(f"Erro na renderização de '{filename}': {e}")
            return []
