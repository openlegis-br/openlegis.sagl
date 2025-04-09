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

#from .obter_assinaturas import PDFProcessorView

# Configure logging (replace with your preferred logging setup)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEBUG_LOG_CONTENTS = True  # Adicione esta linha para controlar o log de depuração

class PDFUploadProcessorView(grok.View):  # Renamed class for clarity
    grok.context(Interface)
    grok.require('zope2.Public')
    grok.name('otimizar_arquivo')

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
                    cpf_certificado = lista[1] if len(lista) > 1 else ''
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

    def _extrair_cpf_do_contents(self, raw_signature_data, original_filename):
        """Tenta extrair o CPF de dentro dos dados brutos de '/Contents', considerando o formato específico."""
        cpf_contents = None
        if raw_signature_data:
            try:
                #logging.info(f"Dados '/Contents' para (raw):\n{raw_signature_data}")
                conteudo_decodificado = raw_signature_data  # Mantém como bytes

                # Expressão regular ajustada para ignorar 6 dígitos (data?) e capturar 11 (CPF)
                correspondencia_cpf = re.search(rb'L\x01\x03\x01\xa0/\x04-\d{8}(\d{11})\d*\x00*\xa0\x17\x06\x05`L', conteudo_decodificado)
                if correspondencia_cpf:
                    cpf_contents = correspondencia_cpf.group(1).decode('ascii')
                    logging.info(f"CPF encontrado em '/Contents' (padrão ajustado): {cpf_contents}")
                else:
                    # Se o padrão específico não for encontrado, tenta a busca genérica por 11 dígitos (backup)
                    correspondencia_generica = re.search(rb'(\d{11})', conteudo_decodificado)
                    if correspondencia_generica:
                        cpf_contents = correspondencia_generica.group(1).decode('ascii')
                        logging.info(f"CPF encontrado em '/Contents' (genérico): {cpf_contents}")
                    else:
                        logging.info(f"Nenhum CPF encontrado em '/Contents' (arquivo: {original_filename})")

            except Exception as e:
                logging.warning(f"Erro ao buscar CPF em '/Contents' (arquivo: {original_filename}): {e}")
        return cpf_contents

    def get_signatures_from_stream(self, fileStream, original_filename):
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
                    signing_time = parse(signing_time_raw[2:].strip("'").replace("'", ":")) if signing_time_raw else None
                    signer_name = None
                    signer_cpf_name = None
                    if '/Name' in v:
                        try:
                            name_cpf_str = v['/Name'].strip()
                            if name_cpf_str:
                                signer_name, _, signer_cpf_name = name_cpf_str.partition(':')
                                signer_name = signer_name.strip()
                                signer_cpf_name = signer_cpf_name.strip()
                                if not signer_cpf_name or len(signer_cpf_name) != 11 or not signer_cpf_name.isdigit():
                                    signer_cpf_name = None
                        except Exception as e:
                            logging.warning(f"Erro ao extrair nome/CPF de '/Name' (arquivo: {original_filename}): {e}")
                            signer_name = v.get('/Name', '').strip()
                            signer_cpf_name = None

                    raw_signature_data = v.get('/Contents')
                    cpf_contents = self._extrair_cpf_do_contents(raw_signature_data, original_filename)

                    parsed_signatures = self.parse_signatures(raw_signature_data)
                    cpf_certificado = None
                    if parsed_signatures:
                        cpf_certificado = parsed_signatures[0].get('cpf') # Assume que o CPF do certificado está no primeiro signatário

                    # Prioriza o CPF do certificado, depois o do '/Name', e por último o do '/Contents'
                    signer_cpf_final = cpf_certificado or signer_cpf_name or cpf_contents

                    for attrdict in parsed_signatures:
                        dic = {
                            'signer_name': signer_name or attrdict.get('signer'),
                            'signer_cpf': signer_cpf_final or attrdict.get('cpf'), # Garante que o CPF do certificado seja usado se parseado
                            'signing_time': signing_time,
                            'signer_certificate': attrdict.get('oname'),
                            'cpf_contents': cpf_contents, # Adiciona o CPF encontrado no Contents para inspeção
                            'cpf_name_field': signer_cpf_name, # Adiciona o CPF encontrado no /Name para inspeção
                            'cpf_certificate_field': cpf_certificado # Adiciona o CPF parseado do certificado
                        }
                        lst_signers.append(dic)

            # Remove duplicatas e ordena
            seen = set()
            unique_signers = [d for d in lst_signers if tuple(d.items()) not in seen and not seen.add(tuple(d.items()))]
            unique_signers.sort(key=lambda dic: dic['signing_time'], reverse=False)
            return unique_signers
        except Exception as e:
            logging.error(f"Erro ao extrair assinaturas do PDF ({original_filename}): {e}")
            return []  # Retorna uma lista vazia em caso de erro

    def _optimize_pdf(self, file_stream, title):
        """Optimizes the PDF file stream."""
        try:
            doc = pymupdf.open(stream=file_stream.getvalue())
            metadata = {"title": title}
            doc.set_metadata(metadata)
            return doc.tobytes(deflate=True, garbage=3, use_objstms=1)
        except Exception as e:
            logging.error(f"Erro ao otimizar o PDF: {e}")
            return None

    def optimizeFile(self, filename, title):
        """Main method to process a file (if PDF).
            If signatures are found, returns the file stream and fields.
            If no signatures are found and no signature fields are present, optimizes the file.
            Returns the original file data if signature fields are present or any error occurs.
        """
        #temp_path = self.context.temp_folder
        #if not hasattr(temp_path, filename):
        #    logging.error(f"Arquivo '{filename}' não encontrado.")
        #    return None

        #arq = getattr(temp_path, filename)
        #try:
        #    file_stream = BytesIO(bytes(arq.data))  # Directly access arq.data
        #except Exception as e:
        #    logging.error(f"Erro ao ler dados do arquivo '{filename}': {e}")
        #    return "Erro ao ler dados do arquivo."
       
        file_stream = BytesIO(filename.read())  # Directly access arq.data

        original_data = file_stream.getvalue()  # Store the original data

        try:
            reader = PdfReader(BytesIO(original_data))  # Use original_data for PdfReader
            fields = reader.get_fields()
            signers_data = self.get_signatures_from_stream(BytesIO(original_data), filename)  # Extract signatures

            if signers_data:  # Check if there are signatures
                logging.info(f"Assinaturas encontradas no arquivo '{filename}'. Retornando stream e campos para tratamento externo.")
                logging.info(f"Campos: {signers_data}")
                return {
                    'file_stream': BytesIO(original_data),
                    'fields': fields,
                    'signatures': signers_data  # Include signatures with CPF information
                }

            if fields:
                logging.info(f"Arquivo '{filename}' contém campos (mas sem assinaturas). Retornando arquivo original.")
                return original_data  # Return original if other fields are present
            else:
                optimized_data = self._optimize_pdf(BytesIO(original_data), title)  # Optimize if no signature fields
                if optimized_data:
                    logging.info(f"Arquivo '{filename}' otimizado com sucesso.")
                    return bytes(optimized_data)
                else:
                    logging.warning(f"Falha ao otimizar o arquivo '{filename}'. Retornando arquivo original.")
                    return original_data  # Return original if optimization failed

        except Exception as e:
            logging.error(f"Erro ao processar o arquivo '{filename}': {e}")
            return original_data  # Return the original data in case of error

    def render(self, filename, title):
        return self.optimizeFile(filename, title)
