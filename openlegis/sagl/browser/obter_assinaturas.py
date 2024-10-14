# -*- coding: utf-8 -*-
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from io import BytesIO
from pypdf import PdfReader
from dateutil.parser import parse
from asn1crypto import cms

class getSignatures(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('obter_assinaturas')
    #anexo = ''
    
    def get_signatures(self, fileStream):
       reader = PdfReader(fileStream)
       fields = reader.get_fields().values()
       signature_field_values = [
           f.value for f in fields if f.field_type == '/Sig']  
       lst_signers = []
       for v in signature_field_values:
           if v != None:
              v_type = v['/Type']
              if '/M' in v:
                 signing_time = parse(v['/M'][2:].strip("'").replace("'", ":"))
              else:
                 signing_time = None
              if '/Name' in v:
                 name = v['/Name'].split(':')[0]
                 cpf = v['/Name'].split(':')[1]
              else:
                 name = None
                 cpf = None
              raw_signature_data = v['/Contents']
              for attrdict in self.parse_signatures(raw_signature_data):
                 dic = {
                        'signer_name':name or attrdict.get('signer'),
                        'signer_cpf':cpf or attrdict.get('cpf'),
                        'signing_time':str(signing_time) or attrdict.get('signing_time'),
                        'signer_certificate': attrdict.get('oname')
                 }
              lst_signers.append(dic)
       lst_signers.sort(key=lambda dic: dic['signing_time'], reverse=True)
       return lst_signers
 
    def parse_signatures(self, raw_signature_data):
        info = cms.ContentInfo.load(raw_signature_data)
        signed_data = info['content']
        certificates = signed_data['certificates']
        signer_infos = signed_data['signer_infos'][0]
        signed_attrs = signer_infos['signed_attrs']
        signers = []
        for signer_info in signer_infos:
            for cert in certificates:
                cert = cert.native['tbs_certificate']
                issuer = cert['issuer']
                subject = cert['subject']
                oname = issuer.get('organization_name', '')
                lista = subject['common_name'].split(':')
                if len(lista) > 1:
                   signer = subject['common_name'].split(':')[0]
                   cpf = subject['common_name'].split(':')[1]
                else:
                   signer = subject['common_name'].split(':')[0]
                   cpf = ''
                dic = {
                   'type': subject.get('organization_name', ''),
                   'signer': signer,
                   'cpf':  cpf,
                   'oname': oname
                }
        signers.append(dic)
        return signers
  
    def render(self, tipo_doc, codigo, anexo):
        for storage in self.context.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
            #storage_path = storage.storage_path
            if anexo != None:
               #filename = str(codigo) + '_anexo_' + str(anexo) + str(storage.pdf_file)
               pdf_signed = str(storage.pdf_location) + str(codigo) + '_anexo_' + str(anexo) + str(storage.pdf_file)
            else:
               #filename = str(codigo) + str(storage.pdf_file)
               pdf_signed = str(storage.pdf_location) + str(codigo) + str(storage.pdf_file)
        arq = self.context.restrictedTraverse(pdf_signed)
        #arq = getattr(self.+'storage_path', filename)
        fileStream = BytesIO(bytes(arq.data))
        reader = PdfReader(fileStream)
        fields = reader.get_fields()
        signers = []
        nom_autor = None
        if fields != None:
            signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
            if signature_field_values is not None:
               signers = self.get_signatures(fileStream)
        if signers:
           return signers
        else:
           return None
