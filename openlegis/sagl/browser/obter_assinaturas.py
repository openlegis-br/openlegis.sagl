# -*- coding: utf-8 -*-
# Standard library imports
from io import BytesIO
import logging
import re  # Importe a biblioteca re

# Third-party library imports
from pypdf import PdfReader
import pymupdf
from dateutil.parser import parse
from asn1crypto import cms

# Zope imports
from five import grok
from zope.interface import Interface


# Configure logging (replace with your preferred logging setup)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class PDFProcessorView(grok.View):  # Renamed class for clarity
    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('obter_assinaturas')

    def _format_cpf(self, cpf):
        """Formata o CPF no padrão 000.000.000-00."""
        if cpf and len(cpf) == 11 and cpf.isdigit():
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf

    def _format_datetime(self, dt):
        """Formata o objeto datetime no padrão YYYY-MM-DD HH:MM:SS."""
        if dt:
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return None

    def parse_signatures(self, raw_signature_data):
        """Parses the raw signature data to extract signer information."""
        try:
            info = cms.ContentInfo.load(raw_signature_data)
            signed_data = info['content']
            certificates = signed_data['certificates']
            signer_infos = signed_data['signer_infos'][0]
            signers = []
            for signer_info in signer_infos:
                for cert in certificates:
                    cert = cert.native['tbs_certificate']
                    issuer = cert['issuer']
                    subject = cert['subject']
                    oname = issuer.get('organization_name', '')
                    common_name = subject.get('common_name', '')  # Corrigido para evitar KeyError
                    lista = common_name.split(':') if common_name else []  # Corrigido para evitar AttributeError
                    signer = lista[0] if lista else ''
                    cpf_certificado_raw = lista[1] if len(lista) > 1 else ''
                    cpf_certificado = self._format_cpf(cpf_certificado_raw)
                    dic = {
                        'type': subject.get('organization_name', ''),
                        'signer': signer,
                        'cpf': cpf_certificado,
                        'oname': oname
                    }
                    signers.append(dic)
            return signers
        except Exception as e:
            logging.error(f"Erro ao analisar assinatura: {e}")
            return []  # Retorna uma lista vazia em caso de erro

    def _extrair_cpf_do_contents(self, raw_signature_data, filename):
        """Tenta extrair o CPF de dentro dos dados brutos de '/Contents', considerando o formato específico."""
        cpf_contents_formatado = None
        cpf_contents_raw = None
        if raw_signature_data:
            try:
                conteudo_decodificado = raw_signature_data  # Mantém como bytes

                # Expressão regular ajustada para ignorar 8 dígitos (data?) e capturar 11 (CPF)
                correspondencia_cpf = re.search(rb'L\x01\x03\x01\xa0/\x04-\d{8}(\d{11})\d*\x00*\xa0\x17\x06\x05`L', conteudo_decodificado)
                if correspondencia_cpf:
                    cpf_contents_raw = correspondencia_cpf.group(1).decode('ascii')
                    cpf_contents_formatado = self._format_cpf(cpf_contents_raw)
                else:
                    # Se o padrão específico não for encontrado, tenta a busca genérica por 11 dígitos (backup)
                    correspondencia_generica = re.search(rb'(\d{11})', conteudo_decodificado)
                    if correspondencia_generica:
                        cpf_contents_raw = correspondencia_generica.group(1).decode('ascii')
                        cpf_contents_formatado = self._format_cpf(cpf_contents_raw)

            except Exception as e:
                logging.warning(f"Erro ao buscar CPF em '/Contents' (arquivo: {filename}): {e}")
        return cpf_contents_formatado

    def get_signatures_from_stream(self, fileStream, filename):
        """Extracts signature information from a PDF file stream."""
        try:
            reader = PdfReader(fileStream)
            fields = reader.get_fields().values()
            signature_field_values = []
            for f in fields:
                if hasattr(f, 'field_type') and str(f.field_type) == '/Sig':
                    signature_field_values.append(f.value)
            lst_signers = []
            for v in signature_field_values:
                if v is not None:
                    signing_time_raw = v.get('/M')
                    signing_time_obj = parse(signing_time_raw[2:].strip("'").replace("'", ":")) if signing_time_raw else None
                    signing_time_formatted = self._format_datetime(signing_time_obj)
                    signer_name = None
                    signer_cpf_name_formatado = None
                    signer_cpf_name_raw = None
                    if '/Name' in v:
                        try:
                            name_cpf_str = v['/Name'].strip()
                            if name_cpf_str:
                                signer_name, _, signer_cpf_name_raw = name_cpf_str.partition(':')
                                signer_name = signer_name.strip()
                                signer_cpf_name_raw = signer_cpf_name_raw.strip()
                                if not signer_cpf_name_raw or len(signer_cpf_name_raw) != 11 or not signer_cpf_name_raw.isdigit():
                                    signer_cpf_name_formatado = None
                                else:
                                    signer_cpf_name_formatado = self._format_cpf(signer_cpf_name_raw)
                        except Exception as e:
                            logging.warning(f"Erro ao extrair nome/CPF de '/Name' (arquivo: {filename}): {e}")
                            signer_name = v.get('/Name', '').strip()
                            signer_cpf_name_formatado = None

                    raw_signature_data = v.get('/Contents')
                    cpf_contents_formatado = self._extrair_cpf_do_contents(raw_signature_data, filename)

                    parsed_signatures = self.parse_signatures(raw_signature_data)
                    cpf_certificado_formatado = None
                    if parsed_signatures:
                        cpf_certificado_formatado = parsed_signatures[0].get('cpf') # Assume que o CPF do certificado está no primeiro signatário

                    # Prioriza o CPF do certificado, depois o do '/Name', e por último o do '/Contents'
                    signer_cpf_final = cpf_certificado_formatado or signer_cpf_name_formatado or cpf_contents_formatado

                    for attrdict in parsed_signatures:
                        dic = {
                            'signer_name': signer_name or attrdict.get('signer'),
                            'signer_cpf': signer_cpf_final or attrdict.get('cpf'), # Garante que o CPF do certificado seja usado se parseado
                            'signing_time': signing_time,
                            'signer_certificate': attrdict.get('oname')
                        }
                        lst_signers.append(dic)

            # Remove duplicatas e ordena
            seen = set()
            unique_signers = [d for d in lst_signers if tuple(d.items()) not in seen and not seen.add(tuple(d.items()))]
            unique_signers.sort(key=lambda dic: dic['signing_time'], reverse=False)
            return unique_signers
        except Exception as e:
            return []  # Retorna uma lista vazia em caso de erro


    def render(self, file_stream, filename):
        try:
            signers_data = self.get_signatures_from_stream(file_stream, filename)  # Extract signatures

            if signers_data:  # Check if there are signatures
                logging.info(f"Assinaturas do documento {filename}: {signers_data}")
                return signers_data
            else:
                logging.info(f"Não há assinatura no documento {filename}")
                return []
        except Exception as e:
            logging.error(f"Erro ao processar o arquivo '{filename}': {e}")
            return []

