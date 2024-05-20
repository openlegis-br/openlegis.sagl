# -*- coding: utf-8 -*-
import re
import os
import requests
import time
import hashlib
import pickle
from binascii import b2a_base64
from random import randrange
from lxml.builder import ElementMaker
from lxml import etree
from datetime import datetime
from DateTime import DateTime
from App.special_dtml import DTMLFile
from AccessControl.class_init import InitializeClass
from OFS.SimpleItem import SimpleItem
from Products.CMFCore.ActionProviderBase import ActionProviderBase
from Products.CMFCore.utils import UniqueObject
from zope.interface import Interface
from Products.CMFCore.utils import getToolByName
from PIL import Image
from io import BytesIO
import uuid
from appy.pod.renderer import Renderer
from PyPDF2 import PdfFileWriter, PdfFileReader, PdfFileMerger
#from PyPDF4 import PdfFileWriter, PdfFileReader, PdfFileMerger
#from PyPDF4.utils import PdfReadError
from pdfrw import PdfReader, PdfWriter, PageMerge
from pdfrw.toreportlab import makerl
from pdfrw.buildxobj import pagexobj
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128, qr
from reportlab.graphics.shapes import Drawing 
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics import renderPDF
from reportlab.graphics.charts.textlabels import Label
from reportlab.lib.utils import ImageReader
#imports para assinatura digital
import sys
import six
import base64
from base64 import b64encode
from zlib import crc32
import simplejson as json
from restpki import *
from zope.testbrowser.browser import Browser
browser = Browser()
## Troca de senha
from AccessControl.SecurityInfo import ClassSecurityInfo
from AccessControl import getSecurityManager
security = ClassSecurityInfo()
from AccessControl import Permissions
from AccessControl.Permission import addPermission
from AccessControl.SecurityInfo import ModuleSecurityInfo
from zope.deferredimport import deprecated
from zope.component import getUtility
security2 = ModuleSecurityInfo('Products.CMFCore.permissions')
security2.declarePublic('mailPassword')
mailPassword = 'Mail forgotten password'
addPermission(mailPassword, ('Anonymous', 'Manager',))
from Acquisition import aq_base


class ISAGLTool(Interface):
    """ Marker interface for SAGL Tool.
    """
    pass

class SAGLTool(UniqueObject, SimpleItem, ActionProviderBase):

    __implements__ = (ISAGLTool)

    id = 'portal_sagl'
    meta_type = 'SAGL Tool'

    XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
    ns = {'lexml': 'http://www.lexml.gov.br/oai_lexml'}
    schema = {'oai_lexml': 'http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd'}

    def verifica_esfera_federacao(self):
        ''' Funcao para verificar a esfera da federacao
        '''
        nome_camara = self.sapl_documentos.props_sagl.nom_casa
        camara = [u'Câmara','Camara','camara',u'camara']
        assembleia = [u'Assembléia','Assembleia','assembleia',u'assembléia']

        if [tipo for tipo in camara if nome_camara.startswith(tipo)]:
            return 'M'
        elif [tipo for tipo in assembleia if nome_camara.startswith(tipo)]:
            return 'E'
        else:
            return ''

    def monta_id(self,cod_norma):
        ''' Funcao que monta o id do objeto do LexML
        '''
        #consultas
        consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)
        if consulta:
            consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)[0]

            end_web_casa = self.sapl_documentos.props_sagl.end_web_casa
            sgl_casa = self.sapl_documentos.props_sagl.sgl_casa.lower()
            num = len(end_web_casa.split('.'))
            dominio = '.'.join(end_web_casa.split('.')[1:num])

            prefixo_oai = '%s.%s:sagl/' % (sgl_casa,dominio)
            numero_interno = consulta.num_norma
            tipo_norma = consulta.voc_lexml
            ano_norma = consulta.ano_norma

            identificador = '%s%s;%s;%s' % (prefixo_oai,tipo_norma,ano_norma,numero_interno)

            return identificador
        else:
            return None

    def monta_urn(self, cod_norma):
        ''' Funcao que monta a URN do LexML
        '''
        esfera = self.verifica_esfera_federacao()
        consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)
        if consulta:
            consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)[0]
            url = self.portal_url() + '/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma=' + str(cod_norma)
            urn='urn:lex:br;'
            esferas = {'M':'municipal','E':'estadual'}
            localidade = self.zsql.localidade_obter_zsql(cod_localidade = self.sapl_documentos.props_sagl.cod_localidade)
            municipio = localidade[0].nom_localidade_pesq.lower()
            for i in re.findall(r'\s',municipio):
                municipio = municipio.replace(i, '.')
            if re.search( r'\.de\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall( r'\.de\.', municipio)][0]
            if re.search( r'\.da\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall( r'\.da\.', municipio)][0]
            if re.search( r'\.das\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall( r'\.das\.', municipio)][0]
            if re.search( r'\.do\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall( r'\.do\.', municipio)][0]
            if re.search( r'\.dos\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall( r'\.dos\.', municipio)][0]
            sigla_uf=localidade[0].sgl_uf
            uf = self.zsql.localidade_obter_zsql(sgl_uf=sigla_uf,tip_localidade='U')[0].nom_localidade_pesq.lower()
            for i in re.findall(r'\s',uf):
                uf = uf.replace(i, '.')
            if re.search( r'\.de\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall( r'\.de\.', uf)][0]
            if re.search( r'\.da\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall( r'\.da\.', uf)][0]
            if re.search( r'\.das\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall( r'\.das\.', uf)][0]
            if re.search( r'\.do\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall( r'\.do\.', uf)][0]
            if re.search( r'\.dos\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall( r'\.dos\.', uf)][0]
            if self.verifica_esfera_federacao() == 'M':
                urn += uf + ';'
                urn += municipio + ':'
            elif self.verifica_esfera_federacao() == 'E':
                urn += uf + ':'
            if esfera == 'M':
                if consulta.voc_lexml == 'regimento.interno' or consulta.voc_lexml == 'resolucao':
                    urn += 'camara.municipal:'
                else:
                    urn += esferas[esfera] + ':'
            else:
                urn += esferas[esfera] + ':'
            urn += consulta.voc_lexml + ':'
            urn += self.pysc.port_to_iso_pysc(consulta.dat_norma) + ';'
            if consulta.voc_lexml == 'lei.organica' or consulta.voc_lexml == 'constituicao':
                urn += consulta.ano_norma
            else:
                urn += consulta.num_norma
            if consulta.dat_vigencia and consulta.dat_publicacao:
                urn += '@'
                urn += self.pysc.port_to_iso_pysc(consulta.dat_vigencia)
                urn += ';publicacao;'
                urn += self.pysc.port_to_iso_pysc(consulta.dat_publicacao)
            elif consulta.dat_publicacao:
                urn += '@'
                urn += 'inicio.vigencia;publicacao;' + self.pysc.port_to_iso_pysc(consulta.dat_publicacao)
            return urn
        else:
            return None

    def monta_xml(self,urn,cod_norma):
        #criacao do xml
        consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)
        publicador = self.zsql.lexml_publicador_obter_zsql()
        if consulta and publicador:
            consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)[0]
            publicador = self.zsql.lexml_publicador_obter_zsql()[0]
            url = self.portal_url() + '/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma=' + str(cod_norma)
            E = ElementMaker()
            LEXML = ElementMaker(namespace=self.ns['lexml'],nsmap=self.ns)
            oai_lexml = LEXML.LexML()
            oai_lexml.attrib['{%s}schemaLocation' % self.XSI_NS] = '%s %s' % (
                'http://www.lexml.gov.br/oai_lexml',
                'http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd')
            id_publicador = str(publicador.id_publicador)
            # montagem da epigrafe
            localidade = self.zsql.localidade_obter_zsql(cod_localidade = self.sapl_documentos.props_sagl.cod_localidade)[0].nom_localidade
            sigla_uf = self.zsql.localidade_obter_zsql(cod_localidade = self.sapl_documentos.props_sagl.cod_localidade)[0].sgl_uf
            if consulta.voc_lexml == 'lei.organica':
                epigrafe = u'%s de %s - %s, de %s' % (consulta.des_tipo_norma, localidade,sigla_uf, consulta.ano_norma)
            elif consulta.voc_lexml == 'constituicao':
                epigrafe = u'%s do Estado de %s, de %s' % (consulta.des_tipo_norma, localidade, consulta.ano_norma)
            else:
                epigrafe = u'%s n° %s,  de %s' % (consulta.des_tipo_norma, consulta.num_norma, self.pysc.data_converter_por_extenso_pysc(consulta.dat_norma))
            ementa = consulta.txt_ementa
            indexacao = consulta.txt_indexacao
            formato = 'text/html'
            id_documento = u'%s_%s' % (str(cod_norma), self.sapl_documentos.norma_juridica.nom_documento)
            if hasattr(self.sapl_documentos.norma_juridica,id_documento):
                arquivo = getattr(self.sapl_documentos.norma_juridica,id_documento)
                url_conteudo = arquivo.absolute_url()
                formato = arquivo.content_type
                if formato == 'application/octet-stream':
                    formato = 'application/msword'
                if formato == 'image/ipeg':
                    formato = 'image/jpeg'
            else:
                url_conteudo = self.portal_url() + '/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma=' + str(cod_norma)
            item_conteudo = E.Item(url_conteudo,formato=formato, idPublicador=id_publicador,tipo='conteudo')
            oai_lexml.append(item_conteudo)
            item_metadado = E.Item(url,formato='text/html', idPublicador=id_publicador,tipo='metadado')
            oai_lexml.append(item_metadado)
            documento_individual = E.DocumentoIndividual(urn)
            oai_lexml.append(documento_individual)
            oai_lexml.append(E.Epigrafe(epigrafe))
            oai_lexml.append(E.Ementa(ementa))
            if indexacao:
                oai_lexml.append(E.Indexacao(indexacao))
            return etree.tostring(oai_lexml)
        else:
            return None

    def oai_query(self,
                  offset=0,
                  batch_size=20,
                  from_date=None,
                  until_date=None,
                  identifier=None):

        esfera = self.verifica_esfera_federacao()

        if batch_size < 0:
            batch_size = 0

        if until_date == None or until_date > datetime.now():
            until_date = datetime.now()

        if from_date is None:
            from_date = ''

        normas = self.zsql.lexml_normas_juridicas_obter_zsql(from_date=from_date,
            until_date=until_date,
            offset=offset,
            batch_size=batch_size,
            num_norma=identifier,
            tip_esfera_federacao=esfera)
        for norma in normas:
            resultado = {}
            cod_norma = norma.cod_norma
            identificador = self.monta_id(cod_norma)
            urn = self.monta_urn(cod_norma)
            xml_lexml = self.monta_xml(urn,cod_norma)

            resultado['tx_metadado_xml'] = xml_lexml
            resultado['cd_status'] = 'N'
            resultado['id'] = identificador
            resultado['when_modified'] = norma.timestamp
            resultado['deleted'] = 0
            if norma.ind_excluido == 1:
                resultado['deleted'] = 1
            yield {'record': resultado,
                   'metadata': resultado['tx_metadado_xml'],
            }

    def create_barcode(self, value):
        barcode = createBarcodeDrawing('Code128',
                                       value=str(value).zfill(7),
                                       barWidth=170,
                                       height=50,
                                       fontSize=2,
                                       humanReadable=True)
        data = b64encode(barcode.asString('png'))
        return data.decode('utf-8')

    def url(self):
        utool = getToolByName(self, 'portal_url')
        return utool.portal_url()

    def resize_and_crop(self,cod_parlamentar):
        image_file = '%s' % (cod_parlamentar) + "_foto_parlamentar"
        arq = getattr(self.sapl_documentos.parlamentar.fotos, image_file)
        img_path = BytesIO(str(arq.data))
        modified_path = BytesIO() 
        crop_type='top'
        size = (350, 380)
        img = Image.open(img_path)
        img = img.convert('RGB')
        img_ratio = img.size[0] / float(img.size[1])
        ratio = size[0] / float(size[1])
        if ratio > img_ratio:
            img = img.resize((size[0], int(round(size[0] * img.size[1] / img.size[0]))),
                Image.ANTIALIAS)
            if crop_type == 'top':
                box = (0, 0, img.size[0], size[1])
            elif crop_type == 'middle':
                box = (0, int(round((img.size[1] - size[1]) / 2)), img.size[0],
                    int(round((img.size[1] + size[1]) / 2)))
            elif crop_type == 'bottom':
                box = (0, img.size[1] - size[1], img.size[0], img.size[1])
            else :
                raise ValueError('ERROR: invalid value for crop_type')
            img = img.crop(box)
        elif ratio < img_ratio:
            img = img.resize((int(round(size[1] * img.size[0] / img.size[1])), size[1]),
                Image.ANTIALIAS)
            if crop_type == 'top':
                box = (0, 0, size[0], img.size[1])
            elif crop_type == 'middle':
                box = (int(round((img.size[0] - size[0]) / 2)), 0,
                    int(round((img.size[0] + size[0]) / 2)), img.size[1])
            elif crop_type == 'bottom':
                box = (img.size[0] - size[0], 0, img.size[0], img.size[1])
            else :
                raise ValueError('ERROR: invalid value for crop_type')
            img = img.crop(box)
        else :
            img = img.resize((size[0], size[1]),
                Image.ANTIALIAS)
        img.save(modified_path, format="PNG")
        modified_path.seek(0)
        content = modified_path.getvalue()
        foto = getattr(self.sapl_documentos.parlamentar.fotos,image_file)
        foto.manage_upload(file=content)

    def get_brasao(self):
        id_logo = self.sapl_documentos.props_sagl.id_logo
        if hasattr(self.sapl_documentos.props_sagl, id_logo):
           arq = getattr(self.sapl_documentos.props_sagl, id_logo)
        else:
           arq = getattr(self.imagens, 'brasao.gif')
        image = BytesIO(str(arq.data))
        image.seek(0)
        brasao = image.getvalue()
        return brasao

    def ata_gerar_odt(self, ata_dic, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "ata.odt")
        template_file = BytesIO(str(arq.data))      
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.ata_sessao.manage_addFile(id=nom_arquivo,file=content)

    def ata_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = "%s"%cod_sessao_plen+'_ata_sessao.odt'
        nom_arquivo_pdf = "%s"%cod_sessao_plen+'_ata_sessao.pdf'
        arq = getattr(self.sapl_documentos.ata_sessao, nom_arquivo_odt)      
        odtFile = BytesIO(str(arq.data)) 
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.ata_sessao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Ata'))

    def ata_comissao_gerar_odt(self, ata_dic, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "ata_comissao.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.reuniao_comissao.manage_addFile(id=nom_arquivo,file=data)

    def ata_comissao_gerar_pdf(self, cod_reuniao):
        nom_arquivo_odt = "%s"%cod_reuniao+'_ata.odt'
        nom_arquivo_pdf = "%s"%cod_reuniao+'_ata.pdf'
        arq = getattr(self.sapl_documentos.reuniao_comissao, nom_arquivo_odt)      
        odtFile = BytesIO(str(arq.data)) 
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.reuniao_comissao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Ata Comissão'))

    def iom_gerar_odt(self, inf_basicas_dic, lst_mesa, lst_presenca_sessao, lst_materia_apresentada, lst_reqplen, lst_reqpres, lst_indicacao, lst_presenca_ordem_dia, lst_votacao, lst_presenca_expediente, lst_oradores, lst_presenca_encerramento, lst_presidente, lst_psecretario, lst_ssecretario):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "iom.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')        
        output_file_odt = "publicacao_iom.odt"
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        os.unlink(output_file_odt)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_odt
        return data

    def materia_apreciada_gerar_odt(self, inf_basicas_dic, lst_votacao):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "materia_apreciada.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "materia_apreciada.odt"
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        os.unlink(output_file_odt)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_odt
        return data

    def materia_apresentada_gerar_odt(self, inf_basicas_dic, lst_materia_apresentada):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "materia_apresentada.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "materia_apresentada.odt"
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        os.unlink(output_file_odt)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_odt
        return data 

    def ordem_dia_gerar_odt(self, inf_basicas_dic, lst_pdiscussao, lst_sdiscussao, lst_discussao_unica, lst_presidente, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "ordem_dia.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo,file=data)

    def ordem_dia_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = "%s"%cod_sessao_plen+'_pauta_sessao.odt'
        nom_arquivo_pdf = "%s"%cod_sessao_plen+'_pauta_sessao.pdf'
        arq = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        if nom_arquivo_pdf in self.sapl_documentos.pauta_sessao:
           documento = getattr(self.sapl_documentos.pauta_sessao,nom_arquivo_pdf)
           documento.manage_upload(file=self.pysc.upload_file(file=content, title='Ordem do Dia'))
        else:
           self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Ordem do Dia'))

    def pdf_completo(self, cod_sessao_plen):
        writer = PdfWriter()
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'))
        for pauta in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
          nom_arquivo_pdf = "%s"%cod_sessao_plen+'_pauta_completa.pdf'
          nom_pdf_amigavel = str(pauta.num_sessao_plen)+'-sessao-'+ str(pauta.dat_inicio)+'-pauta_completa.pdf'
          nom_pdf_amigavel = nom_pdf_amigavel.decode('latin-1').encode("utf-8")
          if hasattr(self.sapl_documentos.pauta_sessao, str(cod_sessao_plen) + '_pauta_sessao.pdf'):
             arq = getattr(self.sapl_documentos.pauta_sessao, str(cod_sessao_plen) + '_pauta_sessao.pdf')
             arquivo = BytesIO(str(arq.data))
             texto_pauta = PdfReader(arquivo, decompress=False).pages
             writer.addpages(texto_pauta)
          lst_materia = []
          for materia in self.zsql.ordem_dia_obter_zsql(cod_sessao_plen=pauta.cod_sessao_plen,ind_excluido=0):
              if materia.cod_materia != None and materia.cod_materia != '':
                 cod_materia = int(materia.cod_materia)
                 lst_materia.append(cod_materia)
          lst_materia = [i for n, i in enumerate(lst_materia) if i not in lst_materia[n + 1:]]
          for cod_materia in lst_materia:
              if hasattr(self.sapl_documentos.materia, str(cod_materia) + '_redacao_final.pdf'):
                 arq = getattr(self.sapl_documentos.materia, str(cod_materia) + '_redacao_final.pdf')
                 arquivo = BytesIO(str(arq.data))
                 texto_redacao = PdfReader(arquivo, decompress=False).pages
                 writer.addpages(texto_redacao)
              elif hasattr(self.sapl_documentos.materia, str(cod_materia) + '_texto_integral.pdf'):
                   arq = getattr(self.sapl_documentos.materia, str(cod_materia) + '_texto_integral.pdf')
                   arquivo = BytesIO(str(arq.data))
                   texto_materia = PdfReader(arquivo, decompress=False).pages
                   writer.addpages(texto_materia)
                   for anexada in self.zsql.anexada_obter_zsql(cod_materia_principal=cod_materia,ind_excluido=0):
                       anexada = anexada.cod_materia_anexada
                       if hasattr(self.sapl_documentos.materia, str(anexada) + '_texto_integral.pdf'):
                          arq = getattr(self.sapl_documentos.materia, str(anexada) + '_texto_integral.pdf')
                          arquivo = BytesIO(str(arq.data))
                          texto_anexada = PdfReader(arquivo, decompress=False).pages
                          writer.addpages(texto_anexada)
                   for subst in self.zsql.substitutivo_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                       substitutivo = subst.cod_substitutivo
                       if hasattr(self.sapl_documentos.substitutivo, str(substitutivo) + '_substitutivo.pdf'):
                          arq = getattr(self.sapl_documentos.substitutivo, str(substitutivo) + '_substitutivo.pdf')
                          arquivo = BytesIO(str(arq.data))
                          texto_substitutivo = PdfReader(arquivo, decompress=False).pages
                          writer.addpages(texto_substitutivo)
                   for eme in self.zsql.emenda_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                       emenda = eme.cod_emenda
                       if hasattr(self.sapl_documentos.emenda, str(emenda) + '_emenda.pdf'):
                          arq = getattr(self.sapl_documentos.emenda, str(emenda) + '_emenda.pdf')
                          arquivo = BytesIO(str(arq.data))
                          texto_emenda = PdfReader(arquivo, decompress=False).pages
                          writer.addpages(texto_emenda)
                   for relat in self.zsql.relatoria_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                       relatoria = relat.cod_relatoria
                       if hasattr(self.sapl_documentos.parecer_comissao, str(relatoria) + '_parecer.pdf'):
                          arq = getattr(self.sapl_documentos.parecer_comissao, str(relatoria) + '_parecer.pdf')
                          arquivo = BytesIO(str(arq.data))
                          texto_parecer = PdfReader(arquivo, decompress=False).pages
                          writer.addpages(texto_parecer)
          output_file_pdf = BytesIO()
          writer.write(output_file_pdf)
          output_file_pdf.seek(0)
          existing_pdf = PdfFileReader(output_file_pdf, strict=False)
          numPages = existing_pdf.getNumPages()
          # cria novo PDF
          packet = BytesIO()
          can = canvas.Canvas(packet)
          for page_num, i in enumerate(range(numPages), start=1):
              page = existing_pdf.getPage(i)
              pwidth = self.getPageSizeW(page)
              pheight = self.getPageSizeH(page)
              can.setPageSize((pwidth, pheight))
              can.setFillColorRGB(0,0,0)
              # Numero de pagina
              num_pagina = "fls. %s/%s" % (page_num, numPages)
              can.saveState()
              can.setFont('Arial', 9)
              can.drawCentredString(pwidth-45, pheight-60, num_pagina)
              can.restoreState()
              can.showPage()
          can.save()
          packet.seek(0)
          new_pdf = PdfFileReader(packet)
          # Mescla arquivos
          output = PdfFileWriter()
          for page in range(existing_pdf.getNumPages()):
              pdf_page = existing_pdf.getPage(page)
              # numeração de páginas
              for wm in range(new_pdf.getNumPages()):
                  watermark_page = new_pdf.getPage(wm)
                  if page == wm:
                     pdf_page.merge_page(watermark_page)
              output.addPage(pdf_page)
          outputStream = BytesIO()
          output.write(outputStream)
          outputStream.seek(0)
          content = outputStream.getvalue()
          if nom_arquivo_pdf in self.sapl_documentos.pauta_sessao:
             arq = getattr(self.sapl_documentos.pauta_sessao,nom_arquivo_pdf)
             arq.manage_upload(file=self.pysc.upload_file(file=content, title='Ordem do Dia'))
          else:
             self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Ordem do Dia'))
          self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
          self.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %nom_pdf_amigavel)
          return content

    def pdf_expediente_completo(self, cod_sessao_plen):
        writer = PdfWriter()
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'))
        for pauta in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
          nom_pdf_amigavel = str(pauta.num_sessao_plen)+'_sessao_'+'expediente_completo.pdf'
          if hasattr(self.sapl_documentos.pauta_sessao, str(cod_sessao_plen) + '_pauta_expediente.pdf'):
             arq = getattr(self.sapl_documentos.pauta_sessao, str(cod_sessao_plen) + '_pauta_expediente.pdf')
             arquivo = BytesIO(str(arq.data))
             texto_pauta = PdfReader(arquivo, decompress=False).pages
             writer.addpages(texto_pauta)
          for item in self.zsql.materia_apresentada_sessao_obter_zsql(cod_sessao_plen = pauta.cod_sessao_plen, ind_excluido = 0):
              if item.cod_materia != None:
                 if hasattr(self.sapl_documentos.materia, str(item.cod_materia) + '_texto_integral.pdf'):
                    arq = getattr(self.sapl_documentos.materia, str(item.cod_materia) + '_texto_integral.pdf')
                    arquivo = BytesIO(str(arq.data))
                    texto_materia = PdfReader(arquivo, decompress=False).pages
                    writer.addpages(texto_materia)
              elif item.cod_emenda != None:
                   if hasattr(self.sapl_documentos.emenda, str(item.cod_emenda) + '_emenda.pdf'):
                      arq = getattr(self.sapl_documentos.emenda, str(item.cod_emenda) + '_emenda.pdf')
                      arquivo = BytesIO(str(arq.data))
                      texto_emenda = PdfReader(arquivo, decompress=False).pages
                      writer.addpages(texto_emenda)
              elif item.cod_substitutivo != None:
                   if hasattr(self.sapl_documentos.substitutivo, str(item.cod_substitutivo) + '_substitutivo.pdf'):
                      arq = getattr(self.sapl_documentos.substitutivo, str(item.cod_substitutivo) + '_substitutivo.pdf')
                      arquivo = BytesIO(str(arq.data))
                      texto_substitutivo = PdfReader(arquivo, decompress=False).pages
                      writer.addpages(texto_substitutivo)
              elif item.cod_parecer != None:
                   if hasattr(self.sapl_documentos.parecer_comissao, str(item.cod_parecer) + '_parecer.pdf'):
                      arq = getattr(self.sapl_documentos.parecer_comissao, str(item.cod_parecer) + '_parecer.pdf')
                      arquivo = BytesIO(str(arq.data))
                      texto_parecer = PdfReader(arquivo, decompress=False).pages
                      writer.addpages(texto_parecer)
              elif item.cod_documento != None:
                   if hasattr(self.sapl_documentos.administrativo, str(item.cod_documento) + '_texto_integral.pdf'):
                      arq = getattr(self.sapl_documentos.administrativo, str(item.cod_documento) + '_texto_integral.pdf')
                      arquivo = BytesIO(str(arq.data))
                      texto_documento = PdfReader(arquivo, decompress=False).pages
                      writer.addpages(texto_documento)
          for item in self.zsql.expediente_materia_obter_zsql(cod_sessao_plen = pauta.cod_sessao_plen, ind_excluido = 0):
              if item.cod_materia != None:
                 if hasattr(self.sapl_documentos.materia, str(item.cod_materia) + '_texto_integral.pdf'):
                    arq = getattr(self.sapl_documentos.materia, str(item.cod_materia) + '_texto_integral.pdf')
                    arquivo = BytesIO(str(arq.data))
                    texto_materia = PdfReader(arquivo, decompress=False).pages
                    writer.addpages(texto_materia)
              elif item.cod_parecer != None:
                   if hasattr(self.sapl_documentos.parecer_comissao, str(item.cod_parecer) + '_parecer.pdf'):
                      arq = getattr(self.sapl_documentos.parecer_comissao, str(item.cod_parecer) + '_parecer.pdf')
                      arquivo = BytesIO(str(arq.data))
                      texto_parecer = PdfReader(arquivo, decompress=False).pages
                      writer.addpages(texto_parecer)
          output_file_pdf = BytesIO()
          writer.write(output_file_pdf)
          output_file_pdf.seek(0)
          existing_pdf = PdfFileReader(output_file_pdf, strict=False)
          numPages = existing_pdf.getNumPages()
          # cria novo PDF
          packet = BytesIO()
          can = canvas.Canvas(packet)
          for page_num, i in enumerate(range(numPages), start=1):
              page = existing_pdf.getPage(i)
              pwidth = self.getPageSizeW(page)
              pheight = self.getPageSizeH(page)
              can.setPageSize((pwidth, pheight))
              can.setFillColorRGB(0,0,0)
              # Numero de pagina
              num_pagina = "fls. %s/%s" % (page_num, numPages)
              can.saveState()
              can.setFont('Arial', 9)
              can.drawCentredString(pwidth-45, pheight-60, num_pagina)
              can.restoreState()
              can.showPage()
          can.save()
          packet.seek(0)
          new_pdf = PdfFileReader(packet)
          # Mescla arquivos
          output = PdfFileWriter()
          for page in range(existing_pdf.getNumPages()):
              pdf_page = existing_pdf.getPage(page)
              # numeração de páginas
              for wm in range(new_pdf.getNumPages()):
                  watermark_page = new_pdf.getPage(wm)
                  if page == wm:
                     pdf_page.merge_page(watermark_page)
              output.addPage(pdf_page)
          outputStream = BytesIO()
          output.write(outputStream)
          outputStream.seek(0)
          content = outputStream.getvalue()
          self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
          self.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %nom_pdf_amigavel)
          return content

    def oradores_gerar_odt(self, inf_basicas_dic, lst_oradores, lst_presidente, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "oradores.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        # atribui o brasao no locals
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.oradores_expediente.manage_addFile(id=nom_arquivo,file=data)

    def oradores_gerar_pdf(self,cod_sessao_plen):
        nom_arquivo_odt = "%s"%cod_sessao_plen+'_oradores_expediente.odt'
        nom_arquivo_pdf = "%s"%cod_sessao_plen+'_oradores_expediente.pdf'
        arq = getattr(self.sapl_documentos.oradores_expediente, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.oradores_expediente.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Oradores'))

    def expediente_gerar_odt(self, inf_basicas_dic, lst_indicacoes, lst_requerimentos, lst_mocoes, lst_oradores, lst_presidente, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "expediente.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo,file=data)

    def expediente_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = "%s"%cod_sessao_plen+'_expediente.odt'
        nom_arquivo_pdf = "%s"%cod_sessao_plen+'_expediente.pdf'
        arq = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Pauta do Expediente'))

    def resumo_gerar_odt(self, resumo_dic, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "resumo.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s"%nom_arquivo
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%nom_arquivo
        return data

    def resumo_tramitacao_gerar_odt(self, inf_basicas_dic, num_protocolo, dat_protocolo, hor_protocolo, dat_vencimento, num_proposicao, des_tipo_materia, nom_autor, txt_ementa, regime_tramitacao, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.materia, "resumo-tramitacao.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%nom_arquivo
        return data

    def doc_acessorio_gerar_odt(self, inf_basicas_dic, nom_arquivo, des_tipo_documento, nom_documento, txt_ementa, dat_documento, data_documento, nom_autor, materia_vinculada, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia.documento_acessorio, modelo_proposicao)
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s" % nom_arquivo
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.materia_odt.manage_addFile(id=nom_arquivo,file=data)

    def doc_acessorio_gerar_pdf(self, cod_documento):
        nom_arquivo_odt = "%s"%cod_documento+'.odt'
        nom_arquivo_pdf = "%s"%cod_documento+'.pdf'
        arq = getattr(self.sapl_documentos.materia_odt, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.materia.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Documento Acessório'))

    def oficio_ind_gerar_odt(self, inf_basicas_dic, lst_indicacao, lst_presidente):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "oficio_indicacao.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "oficio_indicacao.odt"
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        os.unlink(output_file_odt)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_odt
        return data

    def oficio_req_gerar_odt(self, inf_basicas_dic, lst_requerimento, lst_presidente):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "oficio_requerimento.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "oficio_requerimento.odt"
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        os.unlink(output_file_odt)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_odt
        return data

    def emenda_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia.emenda, modelo_proposicao)
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.emenda.manage_addFile(id=nom_arquivo,file=data)

    def emenda_gerar_pdf(self,cod_emenda):
        nom_arquivo_odt = "%s"%cod_emenda+'_emenda.odt'
        nom_arquivo_pdf = "%s"%cod_emenda+'_emenda.pdf'
        arq = getattr(self.sapl_documentos.emenda, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo_pdf, "rb").read()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.emenda.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Emenda'))

    def capa_processo_gerar_odt(self, capa_dic):
        arq = getattr(self.sapl_documentos.modelo.materia, "capa_processo.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s" % capa_dic['nom_arquivo_odt']
        output_file_pdf = "%s" % capa_dic['nom_arquivo_pdf']
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        odtFile = BytesIO(data)
        os.unlink(output_file_odt)
        renderer = Renderer(odtFile,locals(),output_file_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_pdf, "rb").read()
        os.unlink(output_file_pdf)
        # Aguardar nova pasta digital legislativo
        #if hasattr(self.temp_folder,output_file_pdf):
        #   self.temp_folder.manage_delObjects(ids=output_file_pdf)
        #self.temp_folder.manage_addFile(id=output_file_pdf, file=data)
        self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
        self.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %output_file_pdf)
        return data

    def capa_processo_adm_gerar_odt(self, capa_dic):
        arq = getattr(self.sapl_documentos.modelo.documento_administrativo, "capa_processo_adm.odt")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')      
        output_file_odt = "%s" % capa_dic['nom_arquivo_odt']
        output_file_pdf = "%s" % capa_dic['nom_arquivo_pdf']
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        odtFile = BytesIO(data)
        os.unlink(output_file_odt)
        renderer = Renderer(odtFile,locals(),output_file_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_pdf, "rb").read()
        os.unlink(output_file_pdf) 
        if hasattr(self.temp_folder,output_file_pdf):
           self.temp_folder.manage_delObjects(ids=output_file_pdf)
        self.temp_folder.manage_addFile(id=output_file_pdf, file=data)

    def materia_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia, modelo_proposicao)
        template_file = BytesIO(str(arq.data))      
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.materia_odt.manage_addFile(id=nom_arquivo,file=data)

    def materia_gerar_pdf(self, cod_materia):
        nom_arquivo_odt = "%s"%cod_materia+'_texto_integral.odt'
        nom_arquivo_pdf = "%s"%cod_materia+'_texto_integral.pdf'
        arq = getattr(self.sapl_documentos.materia_odt, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        renderer = Renderer(odtFile,locals(), nom_arquivo_pdf, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.materia.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Matéria'))

    def materias_expediente_gerar_ods(self, relatorio_dic, total_assuntos, parlamentares, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "relatorio-expediente.odt")
        template_file = BytesIO(str(arq.data)) 
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        os.unlink(nom_arquivo)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%nom_arquivo
        return data

    def redacao_final_gerar_pdf(self, cod_materia):
        nom_arquivo_odt = "%s"%cod_materia+'_redacao_final.odt'
        nom_arquivo_pdf = "%s"%cod_materia+'_redacao_final.pdf'
        arq = getattr(self.sapl_documentos.materia_odt, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(), nom_arquivo_pdf, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.materia.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Redação Final'))

    def norma_gerar_odt(self, inf_basicas_dic, nom_arquivo, des_tipo_norma, num_norma, ano_norma, dat_norma, data_norma, txt_ementa, modelo_norma):
        arq = getattr(self.sapl_documentos.modelo.norma, modelo_norma)
        template_file = BytesIO(str(arq.data)) 
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.norma_juridica.manage_addFile(id=nom_arquivo,file=data)

    def norma_gerar_pdf(self, cod_norma, tipo_texto):
        nom_arquivo_odt = "%s"%cod_norma+'_texto_integral.odt'
        arq = getattr(self.sapl_documentos.norma_juridica, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        if tipo_texto == 'compilado':
           nom_arquivo_pdf = "%s"%cod_norma+'_texto_consolidado.pdf'
        elif tipo_texto == 'integral':
           nom_arquivo_pdf = "%s"%cod_norma+'_texto_integral.pdf'
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.norma_juridica.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Norma'))

    def oficio_gerar_odt(self, inf_basicas_dic, nom_arquivo, sgl_tipo_documento, num_documento, ano_documento, txt_ementa, dat_documento, dia_documento, nom_autor, modelo_documento):
        arq = getattr(self.sapl_documentos.modelo.documento_administrativo, modelo_documento)
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.administrativo.manage_addFile(id=nom_arquivo,file=data)

    def oficio_gerar_pdf(self, cod_documento):
        nom_arquivo_odt = "%s"%cod_documento+'_texto_integral.odt'
        nom_arquivo_pdf = "%s"%cod_documento+'_texto_integral.pdf'
        arq = getattr(self.sapl_documentos.administrativo, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.administrativo.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Documento'))

    def tramitacao_documento_juntar(self,cod_tramitacao):
        merger = PdfWriter()
        arquivoPdf=str(cod_tramitacao)+"_tram.pdf"
        arquivoPdfAnexo=str(cod_tramitacao)+"_tram_anexo1.pdf"
        if hasattr(self.sapl_documentos.administrativo.tramitacao,arquivoPdf):
           arq = getattr(self.sapl_documentos.administrativo.tramitacao, arquivoPdf)
           arquivo = BytesIO(str(arq.data))
           texto_tram = PdfReader(arquivo, decompress=False).pages
           merger.addpages(texto_tram)
           self.sapl_documentos.administrativo.tramitacao.manage_delObjects(arquivoPdf)
        if hasattr(self.sapl_documentos.administrativo.tramitacao,arquivoPdfAnexo):
           arq = getattr(self.sapl_documentos.administrativo.tramitacao, arquivoPdfAnexo)
           arquivo = BytesIO(str(arq.data))
           texto_anexo = PdfReader(arquivo, decompress=False).pages
           merger.addpages(texto_anexo)
           self.sapl_documentos.administrativo.tramitacao.manage_delObjects(arquivoPdfAnexo)
        outputStream = BytesIO()
        merger.write(outputStream)
        outputStream.seek(0)
        content = outputStream.getvalue()
        self.sapl_documentos.administrativo.tramitacao.manage_addFile(id=arquivoPdf,file=self.pysc.upload_file(file=content, title='Tramitação'))

    def tramitacao_materia_juntar(self,cod_tramitacao):
        merger = PdfWriter()
        arquivoPdf=str(cod_tramitacao)+"_tram.pdf"
        arquivoPdfAnexo=str(cod_tramitacao)+"_tram_anexo1.pdf"
        if hasattr(self.sapl_documentos.materia.tramitacao,arquivoPdf):
           arq = getattr(self.sapl_documentos.materia.tramitacao, arquivoPdf)
           arquivo = BytesIO(str(arq.data))
           texto_tram = PdfReader(arquivo, decompress=False).pages
           merger.addpages(texto_tram)
           self.sapl_documentos.materia.tramitacao.manage_delObjects(arquivoPdf)
        if hasattr(self.sapl_documentos.materia.tramitacao,arquivoPdfAnexo):
           arq = getattr(self.sapl_documentos.materia.tramitacao, arquivoPdfAnexo)
           arquivo = BytesIO(str(arq.data))
           texto_anexo = PdfReader(arquivo, decompress=False).pages
           merger.addpages(texto_anexo)
           self.sapl_documentos.materia.tramitacao.manage_delObjects(arquivoPdfAnexo)
        outputStream = BytesIO()
        merger.write(outputStream)
        outputStream.seek(0)
        content = outputStream.getvalue()
        self.sapl_documentos.materia.tramitacao.manage_addFile(id=arquivoPdf,file=self.pysc.upload_file(file=content, title='Tramitação'))

    # obter altura da pagina
    def getPageSizeH(self, p):
        h = int(p.mediaBox.getHeight())
        return h

    # obter largura da pagina
    def getPageSizeW(self, p):
        w = int(p.mediaBox.getWidth())
        return w

    def parecer_gerar_odt(self, inf_basicas_dic, nom_arquivo, nom_comissao, materia_vinculada, nom_autor, txt_ementa, tip_apresentacao, tip_conclusao, data_parecer, nom_relator, lst_composicao, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia.parecer, modelo_proposicao)
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s"%nom_arquivo
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.parecer_comissao.manage_addFile(id=nom_arquivo,file=data)

    def parecer_gerar_pdf(self, cod_parecer):
        nom_arquivo_odt = "%s"%cod_parecer+'_parecer.odt'
        nom_arquivo_pdf = "%s"%cod_parecer+'_parecer.pdf'
        arq = getattr(self.sapl_documentos.parecer_comissao, nom_arquivo_odt)
        odtFile = BytesIO(str(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.parecer_comissao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Parecer'))

    def peticao_gerar_odt(self, inf_basicas_dic, nom_arquivo, modelo_path):
        utool = getToolByName(self, 'portal_url')
        portal = utool.getPortalObject()
        modelo = portal.unrestrictedTraverse(modelo_path)
        template_file = BytesIO(str(modelo.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.peticao.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.peticao, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Owner'], acquire=1)

    def peticao_gerar_pdf(self, cod_peticao):
        nom_arquivo_odt = "%s"%cod_peticao+'.odt'
        nom_arquivo_pdf = "%s"%cod_peticao+'.pdf'
        arquivo = getattr(self.sapl_documentos.peticao, nom_arquivo_odt)
        odtFile = BytesIO(str(arquivo.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.peticao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Petição'))
        pdf = getattr(self.sapl_documentos.peticao, nom_arquivo_pdf)
        pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)

    def get_proposicao_image_one(self, num_proposicao):
        id_image1 = str(num_proposicao) + '_image_1.jpg'
        arq = getattr(self.sapl_documentos.proposicao, id_image1)
        content = BytesIO(str(arq.data))
        image_one = content.getvalue()
        return image_one

    def get_proposicao_image_two(self, num_proposicao):
        id_image2 = str(num_proposicao) + '_image_2.jpg'
        arq = getattr(self.sapl_documentos.proposicao, id_image2)
        content = BytesIO(str(arq.data))
        image_two = content.getvalue()
        return image_two

    def get_proposicao_image_three(self, num_proposicao):
        id_image3 = str(num_proposicao) + '_image_3.jpg'
        arq = getattr(self.sapl_documentos.proposicao, id_image3)
        content = BytesIO(str(arq.data))
        image_three = content.getvalue()
        return image_three

    def get_proposicao_image_four(self, num_proposicao):
        id_image4 = str(num_proposicao) + '_image_4.jpg'
        arq = getattr(self.sapl_documentos.proposicao, id_image4)
        content = BytesIO(str(arq.data))
        image_four = content.getvalue()
        return image_four

    def proposicao_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao, modelo_path):
        utool = getToolByName(self, 'portal_url')
        portal = utool.getPortalObject()
        if inf_basicas_dic['des_tipo_proposicao'] == 'Parecer' or inf_basicas_dic['des_tipo_proposicao'] == 'Parecer de Comissão':
           materia = inf_basicas_dic['id_materia']
           nom_comissao = inf_basicas_dic['nom_comissao']
           data_parecer = inf_basicas_dic['data_parecer']
           nom_relator = inf_basicas_dic['nom_relator']
           lst_composicao = []
        modelo = portal.unrestrictedTraverse(modelo_path)
        template_file = BytesIO(str(modelo.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        if inf_basicas_dic['des_tipo_proposicao'] == 'Requerimento':
           id_imagem1 = str(num_proposicao)+'_image_1.jpg'
           image1 = None
           if hasattr(self.sapl_documentos.proposicao, id_imagem1):
              image_one = self.get_proposicao_image_one(num_proposicao=num_proposicao)
              exec ('image1 = image_one')
           id_imagem2 = str(num_proposicao)+'_image_2.jpg'
           image2 = None
           if hasattr(self.sapl_documentos.proposicao, id_imagem2):
              image_two = self.get_proposicao_image_two(num_proposicao=num_proposicao)
              exec ('image2 = image_two')
           id_imagem3 = str(num_proposicao)+'_image_3.jpg'
           image3 = None
           if hasattr(self.sapl_documentos.proposicao, id_imagem3):
              image_three = self.get_proposicao_image_three(num_proposicao=num_proposicao)
              exec ('image3 = image_three')
           id_imagem4 = str(num_proposicao)+'_image_4.jpg'
           image4 = None
           if hasattr(self.sapl_documentos.proposicao, id_imagem4):
              image_four = self.get_proposicao_image_four(num_proposicao=num_proposicao)
              exec ('image4 = image_four')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.proposicao.manage_addFile(id=nom_arquivo,file=data)

    def proposicao_gerar_pdf(self, cod_proposicao):
        writer = PdfFileWriter()
        merger = PdfWriter()
        nom_arquivo_odt = "%s"%cod_proposicao+'.odt'
        nom_arquivo_pdf = "%s"%cod_proposicao+'.pdf'
        arquivo = getattr(self.sapl_documentos.proposicao, nom_arquivo_odt)
        odtFile = BytesIO(str(arquivo.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),output_file_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        texto_pdf = PdfReader(output_file_pdf, decompress=False).pages
        os.unlink(nom_arquivo_pdf)
        merger.addpages(texto_pdf)
        for anexo in self.pysc.anexo_proposicao_pysc(cod_proposicao,listar=True):
            arq = getattr(self.sapl_documentos.proposicao, anexo)
            arquivo = BytesIO(str(arq.data))
            texto_anexo = PdfReader(arquivo, decompress=False).pages
            merger.addpages(texto_anexo)
        final_output_file_pdf = BytesIO()
        merger.write(final_output_file_pdf)
        final_output_file_pdf.seek(0)
        content = final_output_file_pdf.getvalue()
        self.sapl_documentos.proposicao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Proposição '+ cod_proposicao))

    def substitutivo_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia.substitutivo, modelo_proposicao)
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.substitutivo.manage_addFile(id=nom_arquivo,file=data)

    def pessoas_exportar(self, pessoas):
        arq = getattr(self.sapl_documentos.modelo, "planilha-visitantes.ods")
        template_file = BytesIO(str(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_ods = "contatos.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def eleitores_exportar(self, eleitores):
        arq = getattr(self.sapl_documentos.modelo, "planilha-eleitores.ods")
        template_file = BytesIO(str(arq.data))
        output_file_ods = "eleitores.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def materias_exportar(self, materias):
        arq = getattr(self.sapl_documentos.modelo, "planilha-materias.ods")
        template_file = BytesIO(str(arq.data))
        output_file_ods = "materias.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def normas_exportar(self, normas):
        arq = getattr(self.sapl_documentos.modelo, "planilha-normas.ods")
        template_file = BytesIO(str(arq.data))
        output_file_ods = "normas.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def substitutivo_gerar_pdf(self,cod_substitutivo):
        nom_arquivo_odt = "%s"%cod_substitutivo+'_substitutivo.odt'
        nom_arquivo_pdf = "%s"%cod_substitutivo+'_substitutivo.pdf'
        arquivo = getattr(self.sapl_documentos.substitutivo, nom_arquivo_odt)
        odtFile = BytesIO(str(arquivo.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),output_file_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_pdf, "rb").read()
        os.unlink(output_file_pdf)
        content = data.getvalue()
        self.sapl_documentos.substitutivo.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Substitutivo'))       

    def protocolo_barcode(self,cod_protocolo):
        sgl_casa = self.sapl_documentos.props_sagl.sgl_casa
        for protocolo in self.zsql.protocolo_obter_zsql(cod_protocolo=cod_protocolo):
          string = str(protocolo.cod_protocolo).zfill(7)
          texto = 'PROT-'+ str(sgl_casa) + ' ' + str(protocolo.num_protocolo)+'/'+str(protocolo.ano_protocolo)
          data = self.pysc.iso_to_port_pysc(protocolo.dat_protocolo)+' - '+protocolo.hor_protocolo[0:2] + ':' + protocolo.hor_protocolo[3:5]
          des_tipo_materia=""
          num_materia = ""
          materia_principal = ""
          if protocolo.tip_processo==1:
             if protocolo.tip_natureza_materia == 1:
                for materia in self.zsql.materia_obter_zsql(num_protocolo=protocolo.num_protocolo,ano_ident_basica=protocolo.ano_protocolo):
                    des_tipo_materia = materia.des_tipo_materia
                    num_materia=materia.sgl_tipo_materia+' '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
             elif protocolo.tip_natureza_materia == 2:
                  for materia in self.zsql.materia_obter_zsql(cod_materia=protocolo.cod_materia_principal):
                      materia_principal = ' - ' + materia.sgl_tipo_materia+' '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
                  for tipo in self.zsql.tipo_materia_legislativa_obter_zsql(tip_materia=protocolo.tip_materia,tip_natureza='A'):
                      if tipo.des_tipo_materia == 'Emenda':
                         for emenda in self.zsql.emenda_obter_zsql(num_protocolo=protocolo.num_protocolo, cod_materia=protocolo.cod_materia_principal):
                             num_materia = 'EME' + ' ' +str(emenda.num_emenda) + str(materia_principal)
                      elif tipo.des_tipo_materia == 'Substitutivo':
                           for substitutivo in self.zsql.substitutivo_obter_zsql(num_protocolo=protocolo.num_protocolo, cod_materia=protocolo.cod_materia_principal):
                               num_materia = 'SUB ' +str(substitutivo.num_substitutivo) + str(materia_principal)
             elif protocolo.tip_natureza_materia == 3:
                  for materia in self.zsql.materia_obter_zsql(cod_materia=protocolo.cod_materia_principal):
                      materia_principal = ' - ' + materia.sgl_tipo_materia+' '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
                  for documento in self.zsql.documento_acessorio_obter_zsql(num_protocolo=protocolo.num_protocolo, cod_materia=protocolo.cod_materia_principal):
                      num_materia = documento.des_tipo_documento + str(materia_principal)
             elif protocolo.tip_natureza_materia == 4:
                  for materia in self.zsql.materia_obter_zsql(cod_materia=protocolo.cod_materia_principal):
                      materia_principal = ' - ' + materia.sgl_tipo_materia+' '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
                  for autor in self.zsql.autor_obter_zsql(cod_autor=protocolo.cod_autor):
                      for comissao in self.zsql.comissao_obter_zsql(cod_comissao=autor.cod_comissao):
                          sgl_comissao = comissao.sgl_comissao
                  for parecer in self.zsql.relatoria_obter_zsql(num_protocolo=protocolo.num_protocolo, cod_materia=protocolo.cod_materia_principal):
                      materia_principal = 'PAR ' + sgl_comissao +' ' + str(parecer.num_parecer)+'/'+str(parecer.ano_parecer) + str(materia_principal)
          elif protocolo.tip_processo==0:
               for documento in self.zsql.documento_administrativo_obter_zsql(num_protocolo=protocolo.num_protocolo, ano_documento=protocolo.ano_protocolo):
                   num_materia = documento.sgl_tipo_documento+' '+str(documento.num_documento)+'/'+str(documento.ano_documento)
        nom_pdf_protocolo = str(cod_protocolo) + "_protocolo.pdf"
        pdfmetrics.registerFont(TTFont('Arial_Bold', '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'))
        pdfmetrics.registerFont(TTFont('Courier_Bold', '/usr/share/fonts/truetype/msttcorefonts/Courier_New_Bold.ttf'))
        x_var=165
        y_var=288
        packet = BytesIO()
        slab = canvas.Canvas(packet, pagesize=A4)
        slab.setFillColorRGB(0,0,0) 
        barcode = barcode128 = code128.Code128(string,barWidth=.34*mm,barHeight=6*mm)
        barcode.drawOn(slab, x_var*mm , y_var*mm)
        slab.setFont("Arial_Bold", 7)
        slab.drawString(485, 809, texto)
        slab.drawString(485, 802, data)
        slab.drawString(485, 795, num_materia)
        slab.save()
        packet.seek(0)
        new_pdf = PdfReader(packet)
        arq = getattr(self.sapl_documentos.protocolo, nom_pdf_protocolo)
        content = BytesIO(str(arq.data))
        existing_pdf =  PdfReader(content)
        barcode = PageMerge().add(new_pdf.pages[0])[0]
        for page in existing_pdf.pages:
            PageMerge(page).add(barcode).render()
        outputStream = BytesIO()
        PdfWriter(outputStream, trailer=existing_pdf).write()
        outputStream.seek(0)
        data = outputStream.getvalue()
        if nom_pdf_protocolo in self.sapl_documentos.protocolo:
           documento = getattr(self.sapl_documentos.protocolo,nom_pdf_protocolo)
           documento.manage_upload(file=self.pysc.upload_file(file=data, title='Protocolo'))
        else:
           self.sapl_documentos.protocolo.manage_addFile(id=nom_pdf_protocolo,file=self.pysc.upload_file(file=data, title='Protocolo'))

    def processo_eletronico_gerar_pdf(self, cod_materia):
        utool = getToolByName(self, 'portal_url')
        writer = PdfFileWriter()
        merger = PdfFileMerger(strict=False)
        portal = utool.getPortalObject()
        if cod_materia.isdigit():
           cod_materia = cod_materia
        else:
           cod_materia = self.pysc.b64decode_pysc(codigo=str(cod_materia))
        for materia in self.zsql.materia_obter_zsql(cod_materia=cod_materia):
           nom_pdf_amigavel = materia.sgl_tipo_materia+'-'+str(materia.num_ident_basica)+'-'+str(materia.ano_ident_basica)+'.pdf'
           nom_pdf_amigavel = nom_pdf_amigavel.decode('latin-1').encode("utf-8")
           id_processo = materia.sgl_tipo_materia+' '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial_Bold', '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'))
        capa = BytesIO(self.modelo_proposicao.capa_processo(cod_materia=cod_materia))
        texto_capa = PdfFileReader(capa)
        merger.append(texto_capa)
        if hasattr(self.sapl_documentos.materia, str(cod_materia) + '_texto_integral.pdf'):
           arq = getattr(self.sapl_documentos.materia, str(cod_materia) + '_texto_integral.pdf')
           arquivo = BytesIO(str(arq.data))
           texto_materia = PdfFileReader(arquivo)
           merger.append(texto_materia)
        anexos = []
        for substitutivo in self.zsql.substitutivo_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
            if hasattr(self.sapl_documentos.substitutivo, str(substitutivo.cod_substitutivo) + '_substitutivo.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(substitutivo.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.substitutivo, str(substitutivo.cod_substitutivo) + '_substitutivo.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.substitutivo, str(substitutivo.cod_substitutivo) + '_substitutivo.pdf').absolute_url()
               anexos.append(dic_anexo)
        for eme in self.zsql.emenda_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
            if hasattr(self.sapl_documentos.emenda, str(eme.cod_emenda) + '_emenda.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(eme.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.emenda, str(eme.cod_emenda) + '_emenda.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.emenda, str(eme.cod_emenda) + '_emenda.pdf').absolute_url()
               anexos.append(dic_anexo)
        for relat in self.zsql.relatoria_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
            if hasattr(self.sapl_documentos.parecer_comissao, str(relat.cod_relatoria) + '_parecer.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(relat.dat_destit_relator, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               for proposicao in self.zsql.proposicao_obter_zsql(cod_parecer=relat.cod_relatoria):
                   dic_anexo["data"] = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.parecer_comissao, str(relat.cod_relatoria) + '_parecer.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.parecer_comissao, str(relat.cod_relatoria) + '_parecer.pdf').absolute_url()
               anexos.append(dic_anexo)
        for anexada in self.zsql.anexada_obter_zsql(cod_materia_principal=cod_materia,ind_excluido=0):
            if hasattr(self.sapl_documentos.materia, str(anexada.cod_materia_anexada) + '_texto_integral.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(anexada.dat_anexacao, datefmt='international').strftime('%Y-%m-%d 23:58:00')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia, str(anexada.cod_materia_anexada) + '_texto_integral.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.materia, str(anexada.cod_materia_anexada) + '_texto_integral.pdf').absolute_url()
               anexos.append(dic_anexo)
               for documento in self.zsql.documento_acessorio_obter_zsql(cod_materia = anexada.cod_materia_anexada, ind_excluido=0):
                   if hasattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf'):
                      dic_anexo = {}
                      dic_anexo["data"] = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                      dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf')
                      dic_anexo["id"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf').absolute_url()
                      anexos.append(dic_anexo)
        for anexada in self.zsql.anexada_obter_zsql(cod_materia_anexada=cod_materia,ind_excluido=0):
            if hasattr(self.sapl_documentos.materia, str(anexada.cod_materia_principal) + '_texto_integral.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(anexada.dat_anexacao, datefmt='international').strftime('%Y-%m-%d 23:58:00')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia, str(anexada.cod_materia_principal) + '_texto_integral.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.materia, str(anexada.cod_materia_principal) + '_texto_integral.pdf').absolute_url()
               anexos.append(dic_anexo)
               for documento in self.zsql.documento_acessorio_obter_zsql(cod_materia = anexada.cod_materia_principal, ind_excluido=0):
                   if hasattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf'):
                      dic_anexo = {}
                      dic_anexo["data"] = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                      dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf')
                      dic_anexo["id"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf').absolute_url()
                      anexos.append(dic_anexo)
        for docadm in self.zsql.documento_administrativo_materia_obter_zsql(cod_materia=cod_materia, ind_excluido=0):
            if hasattr(self.sapl_documentos.administrativo, str(docadm.cod_documento) + '_texto_integral.pdf'):
               dic_anexo = {}
               if docadm.num_protocolo_documento != '' and docadm.num_protocolo_documento != None:
                  for protocolo in self.zsql.protocolo_obter_zsql(num_protocolo=docadm.num_protocolo_documento, ano_protocolo=docadm.ano_documento):
                      dic_anexo["data"] = DateTime(protocolo.dat_timestamp, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               else:
                  dic_anexo["data"] = DateTime(docadm.data_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                  dic_anexo["arquivo"] = getattr(self.sapl_documentos.administrativo, str(docadm.cod_documento) + '_texto_integral.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.administrativo, str(docadm.cod_documento) + '_texto_integral.pdf').absolute_url()
               anexos.append(dic_anexo)
        for documento in self.zsql.documento_acessorio_obter_zsql(cod_materia = cod_materia, ind_excluido=0):
            if hasattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf').absolute_url()
               anexos.append(dic_anexo)
        for tram in self.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, rd_ordem='1', ind_excluido=0):
            if hasattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram.pdf').absolute_url()
               anexos.append(dic_anexo)
            elif hasattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram_signed.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram_signed.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram_signed.pdf').absolute_url()
               anexos.append(dic_anexo)
        for norma in self.zsql.materia_buscar_norma_juridica_zsql(cod_materia = cod_materia):
            if hasattr(self.sapl_documentos.norma_juridica, str(norma.cod_norma) + '_texto_integral.pdf'):
               dic_anexo = {}
               dic_anexo["data"] = DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 23:59:00')
               dic_anexo["arquivo"] = getattr(self.sapl_documentos.norma_juridica, str(norma.cod_norma) + '_texto_integral.pdf')
               dic_anexo["id"] = getattr(self.sapl_documentos.norma_juridica, str(norma.cod_norma) + '_texto_integral.pdf').absolute_url()
               anexos.append(dic_anexo)
        anexos.sort(key=lambda dic: dic['data'])
        for dic in anexos:
            arquivo_doc = BytesIO(str(dic['arquivo'].data))
            try:
               texto_anexo = PdfFileReader(arquivo_doc, strict=False)
            except:
               msg = 'O arquivo "' + str(dic['id']) + '" não é um documento PDF válido.'
               raise ValueError(msg)
            else:
               merger.append(texto_anexo)
        output_file_pdf = BytesIO()
        merger.write(output_file_pdf)
        merger.close()
        output_file_pdf.seek(0)
        existing_pdf = PdfFileReader(output_file_pdf, strict=False)
        numPages = existing_pdf.getNumPages()
        # cria novo PDF
        packet = BytesIO()
        can = canvas.Canvas(packet)
        for page_num, i in enumerate(range(numPages), start=1):
            page = existing_pdf.getPage(i)
            pwidth = self.getPageSizeW(page)
            pheight = self.getPageSizeH(page)
            can.setPageSize((pwidth, pheight))
            can.setFillColorRGB(0,0,0)
            # Numero de pagina
            num_pagina = "fls. %s/%s" % (page_num, numPages)
            can.saveState()
            can.setFont('Arial', 9)
            can.drawCentredString(pwidth-45, pheight-60, id_processo)
            can.setFont('Arial_Bold', 9)
            can.drawCentredString(pwidth-45, pheight-72, num_pagina)
            can.restoreState()
            can.showPage()
        can.save()
        packet.seek(0)
        new_pdf = PdfFileReader(packet)
        # Mescla arquivos
        output = PdfFileWriter()
        for page in range(existing_pdf.getNumPages()):
            pdf_page = existing_pdf.getPage(page)
            # numeração de páginas
            for wm in range(new_pdf.getNumPages()):
                watermark_page = new_pdf.getPage(wm)
                if page == wm:
                   pdf_page.merge_page(watermark_page)
            output.addPage(pdf_page)
        outputStream = BytesIO()
        output.write(outputStream)
        outputStream.seek(0)
        data = outputStream.getvalue()      
        self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
        self.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %nom_pdf_amigavel)
        return data

    def proposicao_autuar(self,cod_proposicao):
        nom_pdf_proposicao = str(cod_proposicao) + "_signed.pdf"
        for proposicao in self.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao):
          num_proposicao = proposicao.cod_proposicao
          nom_autor = proposicao.nom_autor
          cod_validacao_doc = ''
          outros = ''
          qtde_assinaturas = []
          for validacao in self.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao,tipo_doc='proposicao',ind_assinado=1):
            qtde_assinaturas.append(validacao.cod_usuario)
            if validacao.ind_prim_assinatura == 1:
               nom_autor = validacao.nom_completo
            cod_validacao_doc = str(self.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
          if len(qtde_assinaturas) == 2:
             outros = " e outro"
          elif len(qtde_assinaturas) > 2:
             outros = " e outros"
          info_protocolo = '- Recebido em ' + proposicao.dat_recebimento + ' - '
          tipo_proposicao = proposicao.des_tipo_proposicao
          nome_autor = ''
          #if tipo_proposicao != 'Indicação' and tipo_proposicao !='Moção'  and tipo_proposicao != 'Requerimento' and tipo_proposicao != 'Requerimento ao Plenário' and tipo_proposicao != 'Requerimento à Presidência' and tipo_proposicao != 'Mensagem Aditiva':
          #    nome_autor = '(' + nom_autor + ')'
          if proposicao.ind_mat_ou_doc == "M":
            for materia in self.zsql.materia_obter_zsql(cod_materia=proposicao.cod_mat_ou_doc):
              if materia.num_protocolo != None and materia.num_protocolo != '':
                 for protocolo in self.zsql.protocolo_obter_zsql(num_protocolo=materia.num_protocolo, ano_protocolo=materia.ano_ident_basica):
                     info_protocolo = ' - Protocolo nº ' + str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo) + ' recebido em ' + self.pysc.iso_to_port_pysc(protocolo.dat_protocolo) + ' ' + protocolo.hor_protocolo + ' - '
              texto = str(materia.des_tipo_materia.decode('utf-8').upper())+' Nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
              storage_path = self.sapl_documentos.materia
              nom_pdf_saida = str(materia.cod_materia) + "_texto_integral.pdf"
          elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao!='Emenda' and proposicao.des_tipo_proposicao!='Mensagem Aditiva' and proposicao.des_tipo_proposicao!='Substitutivo' and proposicao.des_tipo_proposicao!='Parecer' and proposicao.des_tipo_proposicao!='Parecer de Comissão'):
            for documento in self.zsql.documento_acessorio_obter_zsql(cod_documento=proposicao.cod_mat_ou_doc):
              for materia in self.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                  materia = str(materia.sgl_tipo_materia)+' Nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
              info_protocolo = '- Recebido em ' + proposicao.dat_recebimento + ' - '
              texto = str(documento.des_tipo_documento.decode('utf-8').upper())+' - ' + str(materia)
              storage_path = self.sapl_documentos.materia
              nom_pdf_saida = str(documento.cod_documento) + ".pdf"
          elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Emenda' or proposicao.des_tipo_proposicao=='Mensagem Aditiva'):
            for emenda in self.zsql.emenda_obter_zsql(cod_emenda=proposicao.cod_emenda):
              for materia in self.zsql.materia_obter_zsql(cod_materia=emenda.cod_materia):
                  materia = str(materia.sgl_tipo_materia)+' Nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
              info_protocolo = '- Recebida em ' + proposicao.dat_recebimento + ' - '
              texto = 'EMENDA ' + str(emenda.des_tipo_emenda.decode('utf-8').upper())+' Nº '+ str(emenda.num_emenda) + ' AO ' + str(materia)
              storage_path = self.sapl_documentos.emenda
              nom_pdf_saida = str(emenda.cod_emenda) + "_emenda.pdf"
          elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Substitutivo'):
            for substitutivo in self.zsql.substitutivo_obter_zsql(cod_substitutivo=proposicao.cod_substitutivo):
              for materia in self.zsql.materia_obter_zsql(cod_materia=substitutivo.cod_materia):
                  materia = str(materia.sgl_tipo_materia)+' Nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
              texto = 'SUBSTITUTIVO' + ' Nº '+ str(substitutivo.num_substitutivo) + ' AO ' + str(materia)
              storage_path = self.sapl_documentos.substitutivo
              nom_pdf_saida = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
          elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Parecer' or proposicao.des_tipo_proposicao=='Parecer de Comissão'):
            for relatoria in self.zsql.relatoria_obter_zsql(cod_relatoria=proposicao.cod_parecer, ind_excluido=0): 
              for comissao in self.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao):
                  sgl_comissao = comissao.sgl_comissao
              for materia in self.zsql.materia_obter_zsql(cod_materia=proposicao.cod_mat_ou_doc):
                  materia = str(materia.sgl_tipo_materia)+' Nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
              texto = 'PARECER ' + sgl_comissao + ' Nº '+ str(relatoria.num_parecer) + '/' +str(relatoria.ano_parecer) + ' AO ' + str(materia)
              storage_path = self.sapl_documentos.parecer_comissao
              nom_pdf_saida = str(relatoria.cod_relatoria) + "_parecer.pdf"

        if self.sapl_documentos.props_sagl.restpki_access_token!='':
           mensagem1 = texto + info_protocolo + 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
           mensagem2 = 'Para validar o documento, leia o código QR ou acesse ' + self.url()+'/conferir_assinatura'+' e informe o código '+ cod_validacao_doc + '.'
        else:
           mensagem1 = ''
           mensagem2 = ''
        mensagem = mensagem1 + '\n' + mensagem2
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial_Bold', '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'))
        pdfmetrics.registerFont(TTFont('Arial_Italic', '/usr/share/fonts/truetype/msttcorefonts/Arial_Italic.ttf'))
        pdfmetrics.registerFont(TTFont('Times_New_Roman', '/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf'))
        pdfmetrics.registerFont(TTFont('Times_New_Roman_Bold', '/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold.ttf'))
        pdfmetrics.registerFont(TTFont('Times_New_Roman_Italic', '/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Italic.ttf'))
        arq = getattr(self.sapl_documentos.proposicao, nom_pdf_proposicao)
        arquivo = BytesIO(str(arq.data))
        existing_pdf = PdfFileReader(arquivo, strict=False)
        numPages = existing_pdf.getNumPages()
        # cria novo PDF
        packet = BytesIO()
        can = canvas.Canvas(packet)
        for page_num, i in enumerate(range(numPages), start=1):
            page = existing_pdf.getPage(i)
            pwidth = self.getPageSizeW(page)
            pheight = self.getPageSizeH(page)
            can.setPageSize((pwidth, pheight))
            can.setFillColorRGB(0,0,0)
            # QRCode
            qr_code = qr.QrCodeWidget(self.url()+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(cod_validacao_doc))
            bounds = qr_code.getBounds()
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            d = Drawing(55, 55, transform=[55./width,0,0,55./height,0,0])
            d.add(qr_code)
            x = 59
            renderPDF.draw(d, can,  pwidth-59, 13)
            # Margem direita
            d = Drawing(10, 5)
            lab = Label()
            lab.setOrigin(0,250)
            lab.angle = 90
            lab.fontName = 'Arial'
            lab.fontSize = 7
            lab.textAnchor = 'start'
            lab.boxAnchor = 'n'
            lab.setText(mensagem)
            d.add(lab)
            renderPDF.draw(d, can, pwidth-24, 160)
            # Numero de pagina
            footer_text = "Pag. %s/%s" % (page_num, numPages)
            can.saveState()
            can.setFont('Arial', 8)
            can.drawCentredString(pwidth-30, 10, footer_text)
            can.restoreState()
            can.showPage()
        can.save()
        packet.seek(0)
        new_pdf = PdfFileReader(packet)
        # Numero do documento
        packet2 = BytesIO()
        d = canvas.Canvas(packet2, pagesize=A4)
        d.setFillColorRGB(0,0,0)
        d.setFont("Times_New_Roman_Bold", 13)
        # alinhamento a esquerda
        #d.drawString(85, 700, texto)
        # alinhamento centralizado
        d.drawCentredString(pwidth/2, 700, texto)
        # nome autor abaixo da numeracao
        d.setFont("Times_New_Roman_Bold", 10)
        #d.drawCentredString(pwidth/2, 688, nome_autor)
        d.save()
        packet2.seek(0)
        new_pdf2 = PdfFileReader(packet2)
        # Mescla arquivos
        output = PdfFileWriter()
        for page in range(existing_pdf.getNumPages()):
            pdf_page = existing_pdf.getPage(page)
            # numeração documento na primeira pagina
            if tipo_proposicao != 'Parecer' and tipo_proposicao != 'Parecer de Comissão' and page == 0:
               pdf_page.merge_page(new_pdf2.getPage(0))
            # qrcode e margem direita em todas as páginas
            if self.sapl_documentos.props_sagl.restpki_access_token != '' and cod_validacao_doc != '':
               for wm in range(new_pdf.getNumPages()):
                   watermark_page = new_pdf.getPage(wm)
                   if page == wm:
                      pdf_page.merge_page(watermark_page)
            output.addPage(pdf_page)
        outputStream = BytesIO()
        output.write(outputStream)
        outputStream.seek(0)
        content = outputStream.getvalue()
        if nom_pdf_saida in storage_path:
           storage_path.manage_delObjects(nom_pdf_saida)
           storage_path.manage_addFile(id=nom_pdf_saida,file=self.pysc.upload_file(file=content, title=texto), title=texto)
        else:
           storage_path.manage_addFile(id=nom_pdf_saida,file=self.pysc.upload_file(file=content, title=texto), title=texto)

    def peticao_autuar(self,cod_peticao):
        for peticao in self.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
            cod_validacao_doc = ''
            nom_autor = ''
            outros = ''
            qtde_assinaturas = []
            if self.zsql.assinatura_documento_obter_zsql(tipo_doc='peticao', codigo=peticao.cod_peticao, ind_assinado=1):
               for validacao in self.zsql.assinatura_documento_obter_zsql(tipo_doc='peticao', codigo=peticao.cod_peticao, ind_assinado=1):
                   nom_pdf_peticao = str(validacao.cod_assinatura_doc) + ".pdf"
                   pdf_peticao = self.sapl_documentos.documentos_assinados.absolute_url() + "/" +  nom_pdf_peticao
                   qtde_assinaturas.append(validacao.cod_usuario)
                   if validacao.ind_prim_assinatura == 1:
                      nom_autor = validacao.nom_completo
                   cod_validacao_doc = str(self.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
            else:
               nom_pdf_peticao = str(cod_peticao) + ".pdf"
               pdf_peticao = self.sapl_documentos.peticao.absolute_url() + "/" +  nom_pdf_peticao
               for usuario in self.zsql.usuario_obter_zsql(cod_usuario=peticao.cod_usuario):
                   qtde_assinaturas.append(usuario.cod_usuario)
                   nom_autor = usuario.nom_completo
                   cod_validacao_doc = ''
            if len(qtde_assinaturas) == 2:
               outros = " e outro"
            elif len(qtde_assinaturas) > 2:
               outros = " e outros"
            info_protocolo = '- Recebido em ' + peticao.dat_recebimento + ' - '
            tipo_tipo_peticionamento = peticao.des_tipo_peticionamento
            if peticao.ind_doc_adm == "1":
               for documento in self.zsql.documento_administrativo_obter_zsql(cod_documento=peticao.cod_documento):
                   for protocolo in self.zsql.protocolo_obter_zsql(num_protocolo=documento.num_protocolo, ano_protocolo=documento.ano_documento):
                       info_protocolo = ' - Protocolo nº ' + str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo) + ' recebido em ' + self.pysc.iso_to_port_pysc(protocolo.dat_protocolo) + ' ' + protocolo.hor_protocolo + ' - '
                   texto = str(documento.des_tipo_documento.decode('utf-8').upper())+' Nº '+ str(documento.num_documento)+ '/' +str(documento.ano_documento)
                   storage_path = self.sapl_documentos.administrativo
                   nom_pdf_saida = str(documento.cod_documento) + "_texto_integral.pdf"
                   caminho = '/sapl_documentos/administrativo/'
            elif peticao.ind_doc_materia == "1":
               for documento in self.zsql.documento_acessorio_obter_zsql(cod_documento=peticao.cod_doc_acessorio):
                   texto = str(documento.des_tipo_documento.decode('utf-8').upper())+' - ' + str(materia)
                   storage_path = self.sapl_documentos.materia
                   nom_pdf_saida = str(documento.cod_documento) + ".pdf"
                   caminho = '/sapl_documentos/materia/'
            elif peticao.ind_norma == "1":
               storage_path = self.sapl_documentos.norma_juridica
               for norma in self.zsql.norma_juridica_obter_zsql(cod_norma=peticao.cod_norma):
                   texto = str(norma.des_tipo_norma.decode('utf-8').upper())+' Nº '+ str(norma.num_norma) + '/' + str(norma.ano_norma)
                   nom_pdf_saida = str(norma.cod_norma) + "_texto_integral.pdf"
                   caminho = '/sapl_documentos/norma_juridica/'
        if cod_validacao_doc != '':
           mensagem1 = texto + info_protocolo + 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
           mensagem2 = 'Para validar o documento, leia o código QR ou acesse ' + self.url()+'/conferir_assinatura'+' e informe o código '+ cod_validacao_doc + '.'
        else:
           mensagem1 = texto + info_protocolo + 'Documento assinado com usuário e senha por ' + nom_autor
           mensagem2 = ''
        mensagem = mensagem1 + '\n' + mensagem2
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial_Bold', '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'))

        if cod_validacao_doc != '':
           arq = getattr(self.sapl_documentos.documentos_assinados, nom_pdf_peticao)
        else:
           arq = getattr(self.sapl_documentos.peticao, nom_pdf_peticao)

        arquivo = BytesIO(str(arq.data))
        existing_pdf = PdfFileReader(arquivo, strict=False)
        numPages = existing_pdf.getNumPages()

        # cria novo PDF
        packet = BytesIO()
        can = canvas.Canvas(packet)
        for page_num, i in enumerate(range(numPages), start=1):
            page = existing_pdf.getPage(i)
            pwidth = self.getPageSizeW(page)
            pheight = self.getPageSizeH(page)
            can.setPageSize((pwidth, pheight))
            can.setFillColorRGB(0,0,0)
            # QRCode
            if cod_validacao_doc != '':
               qr_code = qr.QrCodeWidget(self.url()+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(cod_validacao_doc))
            else:
               qr_code = qr.QrCodeWidget(self.url() + str(caminho) + str(nom_pdf_saida))
            bounds = qr_code.getBounds()
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            d = Drawing(55, 55, transform=[55./width,0,0,55./height,0,0])
            d.add(qr_code)
            x = 59
            renderPDF.draw(d, can,  pwidth-59, 13)
            # Margem direita
            d = Drawing(10, 5)
            lab = Label()
            lab.setOrigin(0,250)
            lab.angle = 90
            lab.fontName = 'Arial'
            lab.fontSize = 7
            lab.textAnchor = 'start'
            lab.boxAnchor = 'n'
            lab.setText(mensagem)
            d.add(lab)
            renderPDF.draw(d, can, pwidth-24, 160)
            # Numero de pagina
            footer_text = "Pag. %s/%s" % (page_num, numPages)
            can.saveState()
            can.setFont('Arial', 8)
            can.drawCentredString(pwidth-30, 10, footer_text)
            can.restoreState()
            can.showPage()
        can.save()
        packet.seek(0)
        new_pdf = PdfFileReader(packet)
        # Numero do documento
        packet2 = BytesIO()
        d = canvas.Canvas(packet2, pagesize=A4)
        d.setFillColorRGB(0,0,0)
        d.setFont("Arial_Bold", 13)
        # alinhamento a esquerda
        #d.drawString(85, 700, texto)
        # alinhamento centralizado
        d.drawCentredString(pwidth/2, 700, texto)
        d.save()
        packet2.seek(0)
        new_pdf2 = PdfFileReader(packet2)
        # Mescla arquivos
        output = PdfFileWriter()
        for page in range(existing_pdf.getNumPages()):
            pdf_page = existing_pdf.getPage(page)
            # numeração documento na primeira pagina
            if peticao.ind_doc_adm == '1' and page == 0:
               pdf_page.merge_page(new_pdf2.getPage(0))
            # qrcode e margem direita em todas as páginas
            for wm in range(new_pdf.getNumPages()):
                watermark_page = new_pdf.getPage(wm)
                if page == wm:
                   pdf_page.merge_page(watermark_page)
            output.addPage(pdf_page)
        outputStream = BytesIO()
        output.write(outputStream)
        outputStream.seek(0)
        content = outputStream.getvalue()
        if nom_pdf_saida in storage_path:
           storage_path.manage_delObjects(nom_pdf_saida)
           storage_path.manage_addFile(id=nom_pdf_saida,file=self.pysc.upload_file(file=content, title=texto), title=texto)         
           arq=storage_path[nom_pdf_saida]
           arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
        else:
           storage_path.manage_addFile(id=nom_pdf_saida,file=self.pysc.upload_file(file=content, title=texto), title=texto)  
           arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)

        if peticao.ind_norma == "1":
           arq=storage_path[nom_pdf_saida]
           arq.manage_permission('View', roles=['Anonymoys'], acquire=1)
           self.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(cod_norma=peticao.cod_norma)

    def restpki_client(self):
        restpki_url = 'https://restpkiol.azurewebsites.net/'
        #restpki_url = 'https://pki.rest/'
        restpki_access_token = self.sapl_documentos.props_sagl.restpki_access_token
        restpki_client = RestPkiClient(restpki_url, restpki_access_token)
        return restpki_client

    def get_file_tosign(self, codigo, anexo, tipo_doc):
        for storage in self.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
            tipo_doc = storage.tip_documento
            if tipo_doc == 'proposicao':
               storage_path = self.sapl_documentos.proposicao
               pdf_location = storage.pdf_location
               pdf_signed = str(pdf_location) + str(codigo) + str(storage.pdf_signed)
               nom_arquivo_assinado = str(codigo) + str(storage.pdf_signed)
               pdf_file = str(pdf_location) + str(codigo) + str(storage.pdf_file)
               nom_arquivo = str(codigo) + str(storage.pdf_file)
            else:
               for item in self.zsql.assinatura_documento_obter_zsql(codigo=codigo, anexo=anexo, tipo_doc=tipo_doc, ind_assinado=1):
                   if len([item]) >= 1:
                      storage_path = self.sapl_documentos.documentos_assinados
                      pdf_location = 'sapl_documentos/documentos_assinados/'
                      pdf_signed = str(pdf_location) + str(item.cod_assinatura_doc) + '.pdf'
                      nom_arquivo_assinado = str(item.cod_assinatura_doc) + '.pdf'
                      pdf_file = str(pdf_location) + str(item.cod_assinatura_doc) + '.pdf'
                      nom_arquivo = str(item.cod_assinatura_doc) + '.pdf'
                      break
               else:
                   # local de armazenamento
                   if tipo_doc == 'materia' or tipo_doc == 'doc_acessorio' or tipo_doc == 'redacao_final':
                      storage_path = self.sapl_documentos.materia
                   elif tipo_doc == 'emenda':
                      storage_path = self.sapl_documentos.emenda
                   elif tipo_doc == 'substitutivo':
                      storage_path = self.sapl_documentos.substitutivo
                   elif tipo_doc == 'tramitacao':
                      storage_path = self.sapl_documentos.materia.tramitacao
                   elif tipo_doc == 'parecer_comissao':
                      storage_path = self.sapl_documentos.parecer_comissao
                   elif tipo_doc == 'pauta':
                      storage_path = self.sapl_documentos.pauta_sessao
                   elif tipo_doc == 'ata':
                      storage_path = self.sapl_documentos.ata_sessao
                   elif tipo_doc == 'norma':
                      storage_path = self.sapl_documentos.norma_juridica
                   elif tipo_doc == 'documento' or tipo_doc == 'doc_acessorio_adm':
                      storage_path = self.sapl_documentos.administrativo
                   elif tipo_doc == 'tramitacao_adm':
                      storage_path = self.sapl_documentos.administrativo.tramitacao
                   elif tipo_doc == 'protocolo':
                      storage_path = self.sapl_documentos.protocolo
                   elif tipo_doc == 'peticao':
                      storage_path = self.sapl_documentos.peticao
                   elif tipo_doc == 'pauta_comissao':
                      storage_path = self.sapl_documentos.reuniao_comissao
                   elif tipo_doc == 'ata_comissao':
                      storage_path = self.sapl_documentos.reuniao_comissao
                   elif tipo_doc == 'documento_comissao':
                      storage_path = self.sapl_documentos.documento_comissao
                   pdf_location = storage.pdf_location
                   pdf_signed = str(pdf_location) + str(codigo) + str(storage.pdf_signed)
                   nom_arquivo_assinado = str(codigo) + str(storage.pdf_signed)
                   pdf_file = str(pdf_location) + str(codigo) + str(storage.pdf_file)
                   nom_arquivo = str(codigo) + str(storage.pdf_file)
                   if tipo_doc == 'anexo_sessao':
                      storage_path = self.sapl_documentos.anexo_sessao
                      codigo = str(codigo) + '_anexo_' + str(anexo)
                      pdf_location = storage.pdf_location
                      pdf_signed = str(pdf_location) + str(codigo) + str(storage.pdf_signed)
                      nom_arquivo_assinado = str(codigo) + str(storage.pdf_signed)
                      pdf_file = str(pdf_location) + str(codigo) + str(storage.pdf_file)
                      nom_arquivo = str(codigo) + str(storage.pdf_file)
        try:
           arquivo = self.restrictedTraverse(pdf_signed)
           pdf_tosign = nom_arquivo_assinado
        except:
           arquivo = self.restrictedTraverse(pdf_file)
           pdf_tosign = nom_arquivo

        x = crc32(str(arquivo))

        if (x>=0):
           crc_arquivo= str(x)
        else:
           crc_arquivo= str(-1 * x)

        return pdf_tosign, storage_path, crc_arquivo

    def pades_signature(self, codigo, anexo, tipo_doc, cod_usuario, qtde_assinaturas):
        # get file to sign
        pdf_tosign, storage_path, crc_arquivo = self.get_file_tosign(codigo, anexo, tipo_doc)
        arq = getattr(storage_path, pdf_tosign)
        arquivo = BytesIO(str(arq.data))
        arquivo.seek(0)
        pdf_path = ''
        pdf_stream = str(arq.data)

        # Read the PDF stamp image
        id_logo = self.sapl_documentos.props_sagl.id_logo
        if hasattr(self.sapl_documentos.props_sagl, id_logo):
           arq = getattr(self.sapl_documentos.props_sagl, id_logo)
        else:
           arq = getattr(self.imagens, 'brasao.gif')
        image = BytesIO(str(arq.data))
        image.seek(0)
        pdf_stamp = image.getvalue()

        signature_starter = PadesSignatureStarter(self.restpki_client())
        signature_starter.set_pdf_stream(pdf_stream)

        signature_starter.signature_policy_id = StandardSignaturePolicies.PADES_BASIC
        signature_starter.security_context_id = StandardSecurityContexts.PKI_BRAZIL
        if int(qtde_assinaturas) <= 3:
           signature_starter.visual_representation = ({
               'text': {
                   'text': 'Assinado digitalmente por {{signerName}}',
                   'includeSigningTime': True,
                   'horizontalAlign': 'Left'
               },
               'image': {
                   'resource': {
                       'content': base64.b64encode(pdf_stamp),
                       'mimeType': 'image/png'
                   },
                   'opacity': 40,
                   'horizontalAlign': 'Right'
               },
               'position': self.get_visual_representation_position(2)
           })
        elif int(qtde_assinaturas) > 3:
           signature_starter.visual_representation = ({
               'text': {
                   'text': 'Assinado digitalmente por {{signerName}}',
                   'includeSigningTime': True,
                   'horizontalAlign': 'Left'
               },
               'image': {
                   'resource': {
                       'content': base64.b64encode(pdf_stamp),
                       'mimeType': 'image/png'
                   },
                   'opacity': 40,
                   'horizontalAlign': 'Right'
               },
               'position': self.get_visual_representation_position(4)
           })

        token = signature_starter.start_with_webpki()

        tokenjs = json.dumps(token)

        return token, pdf_path, crc_arquivo, codigo, anexo, tipo_doc, cod_usuario, tokenjs

    def pades_signature_action(self, token, codigo, anexo, tipo_doc, cod_usuario, crc_arquivo_original):
        # checking if file was changed
        pdf_tosign, storage_path, crc_arquivo = self.get_file_tosign(codigo, anexo, tipo_doc)
        if str(crc_arquivo_original) != str(crc_arquivo):
           msg = 'O arquivo foi modificado durante o procedimento de assinatura! Tente novamente.'
           raise ValueError(msg)

        # Get the token for this signature (rendered in a hidden input field)
        token = token
        codigo = codigo
        anexo = anexo
        tipo_doc = tipo_doc
        cod_usuario = cod_usuario

        # Instantiate the PadesSignatureFinisher class, responsible for completing the signature process
        signature_finisher = PadesSignatureFinisher(self.restpki_client())

        # Set the token
        signature_finisher.token = token

        # Call the finish() method, which finalizes the signature process and returns the signed PDF
        signature_finisher.finish()

        # Get information about the certificate used by the user to sign the file. This method must only be called after
        # calling the finish() method.
        signer_cert = signature_finisher.certificate

        # At this point, you'd typically store the signed PDF on your database.
        cod_assinatura_doc = ''
        for item in self.zsql.assinatura_documento_obter_zsql(codigo=codigo, anexo=anexo, tipo_doc=tipo_doc):
            cod_assinatura_doc = str(item.cod_assinatura_doc)
            self.zsql.assinatura_documento_registrar_zsql(cod_assinatura_doc=item.cod_assinatura_doc, cod_usuario=cod_usuario)
            break
        else:
            cod_assinatura_doc = str(self.cadastros.assinatura.generate_verification_code())
            self.zsql.assinatura_documento_incluir_zsql(cod_assinatura_doc=cod_assinatura_doc, codigo=codigo, anexo=anexo, tipo_doc=tipo_doc, cod_usuario=cod_usuario, ind_prim_assinatura=1)
            self.zsql.assinatura_documento_registrar_zsql(cod_assinatura_doc=cod_assinatura_doc, cod_usuario=cod_usuario)

        if tipo_doc == 'proposicao':
           storage_path = self.sapl_documentos.proposicao
           for storage in self.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
               filename = str(codigo) + str(storage.pdf_signed)
        else:
           storage_path = self.sapl_documentos.documentos_assinados
           for storage in self.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
               filename = str(cod_assinatura_doc) + '.pdf'

        f = signature_finisher.stream_signed_pdf()
        
        if hasattr(storage_path,filename):
           arq=storage_path[filename]
           arq.manage_upload(file=f.getvalue())
        else:
           storage_path.manage_addFile(id=filename, file=f.getvalue(), title=filename)    
       
        if tipo_doc != 'proposicao' and tipo_doc != 'peticao':
           self.margem_direita(codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename)
       
        for item in signer_cert:
           subjectName = signer_cert['subjectName']
           commonName = subjectName['commonName']
           email = signer_cert['emailAddress']
           pkiBrazil = signer_cert['pkiBrazil']
           certificateType = pkiBrazil['certificateType']
           cpf = pkiBrazil['cpf']
           responsavel = pkiBrazil['responsavel']
        filenamejs = json.dumps(filename)
        return signer_cert, commonName, email, certificateType, cpf, responsavel, filename, filenamejs

    def get_visual_representation_position(self, sample_number):
        if sample_number == 1:
            # Example #1: automatic positioning on footnote. This will insert the signature, and future signatures,
            # ordered as a footnote of the last page of the document
            return PadesVisualPositioningPresets.get_footnote(self.restpki_client())
        elif sample_number == 2:
            # Example #2: get the footnote positioning preset and customize it
            visual_position = PadesVisualPositioningPresets.get_footnote(self.restpki_client())
            visual_position['auto']['container']['left'] = 3
            visual_position['auto']['container']['bottom'] = 2
            visual_position['auto']['container']['right'] = 3
            return visual_position
        elif sample_number == 3:
            # Example #3: automatic positioning on new page. This will insert the signature, and future signatures,
            # in a new page appended to the end of the document.
            return PadesVisualPositioningPresets.get_new_page(self.restpki_client())
        elif sample_number == 4:
            # Example #4: get the "new page" positioning preset and customize it
            visual_position = PadesVisualPositioningPresets.get_new_page(self.restpki_client())
            visual_position['auto']['container']['left'] = 3
            visual_position['auto']['container']['top'] = 2
            visual_position['auto']['container']['bottom'] = 2
            visual_position['auto']['container']['right'] = 3
            return visual_position
        elif sample_number == 5:
            # Example #5: manual positioning
            return {
                'pageNumber': 0,
                # zero means the signature will be placed on a new page appended to the end of the document
                'measurementUnits': 'Centimeters',
                # define a manual position of 5cm x 3cm, positioned at 1 inch from the left and bottom margins
                'manual': {
                    'left': 2.54,
                    'bottom': 1.54,
                    'width': 5,
                    'height': 3
                }
            }
        elif sample_number == 6:
            # Example #6: custom auto positioning
            return {
                'pageNumber': -1,
                # negative values represent pages counted from the end of the document (-1 is last page)
                'measurementUnits': 'Centimeters',
                'auto': {
                    # Specification of the container where the signatures will be placed, one after the other
                    'container': {
                        # Specifying left and right (but no width) results in a variable-width container with the given
                        # margins
                        'left': 2.54,
                        'right': 2.54,
                        # Specifying bottom and height (but no top) results in a bottom-aligned fixed-height container
                        'top': 1.54,
                        'height': 3
                    },
                    # Specification of the size of each signature rectangle
                    #'signatureRectangleSize': {
                    #    'width': 5,
                    #    'height': 3
                    #},
                    # The signatures will be placed in the container side by side. If there's no room left, the
                    # signatures will "wrap" to the next row. The value below specifies the vertical distance between
                    # rows
                    'rowSpacing': 1
                }
            }
        else:
            return None

    def margem_direita(self, codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename):
        for storage in self.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
            if tipo_doc == 'anexo_sessao':
               nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
               nom_pdf_documento = str(codigo) + '_anexo_' + str(anexo) + '.pdf'        
            else:
               nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
               nom_pdf_documento = str(codigo) + str(storage.pdf_file)
        outros = ''
        qtde_assinaturas = []
        for validacao in self.zsql.assinatura_documento_obter_zsql(cod_assinatura_doc=cod_assinatura_doc, ind_assinado=1):
            qtde_assinaturas.append(validacao.cod_usuario)
            if validacao.ind_prim_assinatura == 1:
               nom_autor = validacao.nom_completo
               cod_validacao_doc = str(self.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
        else:
            for usuario in self.zsql.usuario_obter_zsql(cod_usuario=cod_usuario):
                nom_autor = usuario.nom_completo
                break
        if len(qtde_assinaturas) == 2:
           outros = " e outro"
        elif len(qtde_assinaturas) > 2:
           outros = " e outros"
        string = str(self.cadastros.assinatura.format_verification_code(cod_assinatura_doc))
        # Variáveis para obtenção de dados e local de armazenamento por tipo de documento
        if tipo_doc == 'materia' or tipo_doc == 'doc_acessorio' or tipo_doc == 'redacao_final':
           storage_path = self.sapl_documentos.materia
           if tipo_doc == 'materia' or tipo_doc == 'redacao_final':
              for metodo in self.zsql.materia_obter_zsql(cod_materia=codigo):
                  num_documento = metodo.num_ident_basica
                  if tipo_doc == 'materia':
                     texto = str(metodo.des_tipo_materia.decode('utf-8').upper())+' Nº '+ str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica)
                  elif tipo_doc == 'redacao_final':
                     texto = 'REDAÇÃO FINAL - ' + str(metodo.sgl_tipo_materia)+' Nº '+ str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica)
           elif tipo_doc == 'doc_acessorio':
              for metodo in self.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
                  for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                      materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
              texto = str(metodo.nom_documento) + ' - ' + str(materia)
        elif tipo_doc == 'emenda':
           storage_path = self.sapl_documentos.emenda
           for metodo in self.zsql.emenda_obter_zsql(cod_emenda=codigo):
               for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
               texto = str('Emenda ') + str(metodo.des_tipo_emenda) + str(' nº ') + str(metodo.num_emenda) + str(' - ') + str(materia)
        elif tipo_doc == 'substitutivo':
           storage_path = self.sapl_documentos.substitutivo
           for metodo in self.zsql.substitutivo_obter_zsql(cod_substitutivo=codigo):
               for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
               texto = 'Substitutivo nº '+ str(metodo.num_substitutivo) + ' - ' + str(materia)
        elif tipo_doc == 'tramitacao':
           storage_path = self.sapl_documentos.materia.tramitacao
           for metodo in self.zsql.tramitacao_obter_zsql(cod_tramitacao=codigo):
               materia = str(metodo.sgl_tipo_materia)+' '+ str(metodo.num_ident_basica)+'/'+str(metodo.ano_ident_basica)
           texto = 'TRAMITAÇÃO Nº '+ str(metodo.cod_tramitacao) + ' - ' + str(materia)
        elif tipo_doc == 'parecer_comissao':
           storage_path = self.sapl_documentos.parecer_comissao
           for metodo in self.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   sgl_comissao = str(comissao.sgl_comissao)
               parecer = str(metodo.num_parecer)+'/'+str(metodo.ano_parecer)
               for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
           texto = 'Parecer ' + str(sgl_comissao) + ' nº ' + str(parecer) + ' ao ' + str(materia)
        elif tipo_doc == 'pauta':
           storage_path = self.sapl_documentos.pauta_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) +  'ª Reunião ' + str(tipo.nom_sessao)+' - '+ str(metodo.dat_inicio_sessao)
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
           texto = 'PAUTA' + ' - ' + str(sessao)
        elif tipo_doc == 'ata':
           storage_path = self.sapl_documentos.ata_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) +  'ª Reunião ' + str(tipo.nom_sessao)+' - '+ str(metodo.dat_inicio_sessao)
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
           texto = 'ATA' + ' - ' + str(sessao)
        elif tipo_doc == 'anexo_sessao':
           storage_path = self.sapl_documentos.anexo_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) +  'ª Reunião ' + str(tipo.nom_sessao)+ ' de ' + str(metodo.dat_inicio_sessao)      
           file_item =  str(codigo) + '_anexo_' + str(anexo) + '.pdf'        
           title = getattr(self.sapl_documentos.anexo_sessao,file_item).title_or_id()
           texto = str(title)
        elif tipo_doc == 'norma':
           storage_path = self.sapl_documentos.norma_juridica
           for metodo in self.zsql.norma_juridica_obter_zsql(cod_norma=codigo):
               texto = str(metodo.des_tipo_norma.decode('utf-8').upper())+' Nº '+ str(metodo.num_norma) + '/' + str(metodo.ano_norma)
        elif tipo_doc == 'documento' or tipo_doc == 'doc_acessorio_adm':
           storage_path = self.sapl_documentos.administrativo
           if tipo_doc == 'documento':
              for metodo in self.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
                  num_documento = metodo.num_documento
              texto = str(metodo.des_tipo_documento.decode('utf-8').upper())+' Nº '+ str(metodo.num_documento)+ '/' +str(metodo.ano_documento)
           elif tipo_doc == 'doc_acessorio_adm':
              for metodo in self.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
                  for documento in self.zsql.documento_administrativo_obter_zsql(cod_documento=metodo.cod_documento):
                      documento = str(documento.sgl_tipo_documento) +' '+ str(documento.num_documento)+'/'+str(documento.ano_documento)
              texto = 'Acessório' + ' - ' + str(documento)
        elif tipo_doc == 'tramitacao_adm':
           storage_path = self.sapl_documentos.administrativo.tramitacao
           for metodo in self.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=codigo):
               documento = str(metodo.sgl_tipo_documento)+' '+ str(metodo.num_documento)+'/'+str(metodo.ano_documento)
           texto = 'TRAMITAÇÃO Nº '+ str(metodo.cod_tramitacao) + ' - ' + str(documento)
        elif tipo_doc == 'proposicao':
           storage_path = self.sapl_documentos.proposicao
           for metodo in self.zsql.proposicao_obter_zsql(cod_proposicao=codigo):
               texto = str(metodo.des_tipo_proposicao.decode('utf-8').upper())+' Nº '+ str(metodo.cod_proposicao)
        elif tipo_doc == 'protocolo':
           storage_path = self.sapl_documentos.protocolo
           for metodo in self.zsql.protocolo_obter_zsql(cod_protocolo=codigo):
               texto = 'PROTOCOLO Nº '+ str(metodo.num_protocolo)+'/'+ str(metodo.ano_protocolo)
        elif tipo_doc == 'peticao':
           storage_path = self.sapl_documentos.peticao
           texto = 'PETIÇÃO ELETRÔNICA'
        elif tipo_doc == 'pauta_comissao':
           storage_path = self.sapl_documentos.reuniao_comissao
           for metodo in self.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = 'PAUTA - ' + metodo.num_reuniao + 'ª Reunião da ' + comissao.sgl_comissao + ', em ' + metodo.dat_inicio_reuniao
        elif tipo_doc == 'ata_comissao':
           storage_path = self.sapl_documentos.reuniao_comissao
           for metodo in self.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = 'ATA - ' + metodo.num_reuniao + 'ª Reunião da ' + comissao.sgl_comissao + ', em ' + metodo.dat_inicio_reuniao
        elif tipo_doc == 'documento_comissao':
           storage_path = self.sapl_documentos.documento_comissao
           for metodo in self.zsql.documento_comissao_obter_zsql(cod_documento=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = metodo.txt_descricao + ' - ' + comissao.sgl_comissao
        mensagem1 = texto + ' - Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros + '.'
        mensagem2 = 'Para validar o documento, leia o código QR ou acesse ' + self.url()+'/conferir_assinatura'+' e informe o código '+ string
        mensagem = mensagem1 + '\n' + mensagem2
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial_Bold', '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'))
        arq = getattr(self.sapl_documentos.documentos_assinados, filename)
        arquivo = BytesIO(str(arq.data))
        existing_pdf = PdfFileReader(arquivo, strict=False)
        numPages = existing_pdf.getNumPages()
        # cria novo PDF
        packet = BytesIO()
        can = canvas.Canvas(packet)
        for page_num, i in enumerate(range(numPages), start=1):
            page = existing_pdf.getPage(i)
            pwidth = self.getPageSizeW(page)
            pheight = self.getPageSizeH(page)
            can.setPageSize((pwidth, pheight))
            can.setFillColorRGB(0,0,0)
            # QRCode
            qr_code = qr.QrCodeWidget(self.url()+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(string))
            bounds = qr_code.getBounds()
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            d = Drawing(55, 55, transform=[55./width,0,0,55./height,0,0])
            d.add(qr_code)
            x = 59
            renderPDF.draw(d, can,  pwidth-59, 13)
            # Margem direita
            d = Drawing(10, 5)
            lab = Label()
            lab.setOrigin(0,250)
            lab.angle = 90
            lab.fontName = 'Arial'
            lab.fontSize = 7
            lab.textAnchor = 'start'
            lab.boxAnchor = 'n'
            lab.setText(mensagem)
            d.add(lab)
            renderPDF.draw(d, can, pwidth-24, 160)
            # Numero de pagina
            footer_text = "Pag. %s/%s" % (page_num, numPages)
            can.saveState()
            can.setFont('Arial', 8)
            can.drawCentredString(pwidth-30, 10, footer_text)
            can.restoreState()
            can.showPage()
        can.save()
        packet.seek(0)
        new_pdf = PdfFileReader(packet)
        # Mescla arquivos
        output = PdfFileWriter()
        for page in range(existing_pdf.getNumPages()):
            pdf_page = existing_pdf.getPage(page)
            # qrcode e margem direita em todas as páginas
            for wm in range(new_pdf.getNumPages()):
                watermark_page = new_pdf.getPage(wm)
                if page == wm:
                   pdf_page.merge_page(watermark_page)
            output.addPage(pdf_page)
        outputStream = BytesIO()
        output.write(outputStream)
        outputStream.seek(0)
        content = outputStream.getvalue()
        if hasattr(storage_path,nom_pdf_documento):
           arq=storage_path[nom_pdf_documento]
           arq.manage_upload(file=self.pysc.upload_file(file=content, title=texto))
        else:
           storage_path.manage_addFile(id=nom_pdf_documento,file=self.pysc.upload_file(file=content, title=texto), title=texto)
        if tipo_doc == 'parecer_comissao':
           for relat in self.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
               nom_arquivo_pdf = "%s"%relat.cod_relatoria+'_parecer.pdf'
               if relat.tip_fim_relatoria == '18' and hasattr(self.sapl_documentos.parecer_comissao, nom_arquivo_pdf):
                  pdf = getattr(self.sapl_documentos.parecer_comissao, nom_arquivo_pdf)
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
        if tipo_doc == 'doc_acessorio':
           for documento in self.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
               nom_arquivo_pdf = "%s"%documento.cod_documento+'.pdf'
               if str(documento.ind_publico) == '1' and hasattr(self.sapl_documentos.materia, nom_arquivo_pdf):
                  pdf = getattr(self.sapl_documentos.materia, nom_arquivo_pdf)
                  pdf.manage_permission('View', roles=['Anonymous'], acquire=1)
               elif str(documento.ind_publico) == '0' and hasattr(self.sapl_documentos.materia, nom_arquivo_pdf):
                  pdf = getattr(self.sapl_documentos.materia, nom_arquivo_pdf)
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
        if tipo_doc == 'documento':
           for documento in self.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
               nom_arquivo_pdf = "%s"%documento.cod_documento+'_texto_integral.pdf'
               if str(documento.ind_publico) == '1' and hasattr(self.sapl_documentos.administrativo, nom_arquivo_pdf):
                  pdf = getattr(self.sapl_documentos.administrativo, nom_arquivo_pdf)
                  pdf.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
               elif str(documento.ind_publico) == '0' and hasattr(self.sapl_documentos.administrativo, nom_arquivo_pdf):
                  pdf = getattr(self.sapl_documentos.administrativo, nom_arquivo_pdf)
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
        if tipo_doc == 'doc_acessorio_adm':
           for doc in self.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
               documento = self.zsql.documento_administrativo_obter_zsql(cod_documento=doc.cod_documento)[0]
               nom_arquivo_pdf = "%s"%doc.cod_documento_acessorio+'.pdf'
               if str(documento.ind_publico) == '1' and hasattr(self.sapl_documentos.administrativo, nom_arquivo_pdf):
                  pdf = getattr(self.sapl_documentos.administrativo, nom_arquivo_pdf)
                  pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
               if str(documento.ind_publico) == '0' and hasattr(self.sapl_documentos.administrativo, nom_arquivo_pdf):
                  pdf = getattr(self.sapl_documentos.administrativo, nom_arquivo_pdf)
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
        return 'ok'

    def assinar_proposicao(self, lista):
        for item in lista:
           storage_path = self.sapl_documentos.proposicao
           for proposicao in self.zsql.proposicao_obter_zsql(cod_proposicao=int(item)):
               string = self.pysc.proposicao_calcular_checksum_pysc(proposicao.cod_proposicao, senha=1)
               nom_autor = proposicao.nom_autor
               pdf_proposicao = str(proposicao.cod_proposicao) + '.pdf'
               pdf_assinado = str(proposicao.cod_proposicao) + '_signed.pdf'
               texto = 'Proposição eletrônica ' + string
           mensagem1 = 'Documento assinado digitalmente com usuário e senha por ' + nom_autor + '.'
           mensagem2 = texto + ', Para verificação de autenticidade utilize o QR Code exibido no rodapé.'
           mensagem = mensagem1 + '\n' + mensagem2
           pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'))
           pdfmetrics.registerFont(TTFont('Arial_Bold', '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'))
           arq = getattr(storage_path, pdf_proposicao)
           arquivo = BytesIO(str(arq.data))
           existing_pdf = PdfFileReader(arquivo, strict=False)
           numPages = existing_pdf.getNumPages()
           # cria novo PDF
           packet = BytesIO()
           can = canvas.Canvas(packet)
           for page_num, i in enumerate(range(numPages), start=1):
               page = existing_pdf.getPage(i)
               pwidth = self.getPageSizeW(page)
               pheight = self.getPageSizeH(page)
               can.setPageSize((pwidth, pheight))
               can.setFillColorRGB(0,0,0)
               # QRCode
               qr_code = qr.QrCodeWidget(self.url() + '/sapl_documentos/proposicao/' + proposicao.cod_proposicao + '_signed.pdf')
               bounds = qr_code.getBounds()
               width = bounds[2] - bounds[0]
               height = bounds[3] - bounds[1]
               d = Drawing(55, 55, transform=[55./width,0,0,55./height,0,0])
               d.add(qr_code)
               x = 59
               renderPDF.draw(d, can,  pwidth-59, 13)
               # Margem direita
               d = Drawing(10, 5)
               lab = Label()
               lab.setOrigin(0,250)
               lab.angle = 90
               lab.fontName = 'Arial'
               lab.fontSize = 7
               lab.textAnchor = 'start'
               lab.boxAnchor = 'n'
               lab.setText(mensagem)
               d.add(lab)
               renderPDF.draw(d, can, pwidth-24, 160)
               # Numero de pagina
               footer_text = "Pag. %s/%s" % (page_num, numPages)
               can.saveState()
               can.setFont('Arial', 8)
               can.drawCentredString(pwidth-30, 10, footer_text)
               can.restoreState()
               can.showPage()
           can.save()
           packet.seek(0)
           new_pdf = PdfFileReader(packet)
           # Mescla arquivos
           output = PdfFileWriter()
           for page in range(existing_pdf.getNumPages()):
               pdf_page = existing_pdf.getPage(page)
               # qrcode e margem direita em todas as páginas
               for wm in range(new_pdf.getNumPages()):
                   watermark_page = new_pdf.getPage(wm)
                   if page == wm:
                      pdf_page.merge_page(watermark_page)
               output.addPage(pdf_page)
           outputStream = BytesIO()
           output.write(outputStream)
           outputStream.seek(0)
           content = outputStream.getvalue()
           if hasattr(storage_path,pdf_assinado):
              arq=storage_path[pdf_assinado]
              arq.manage_upload(file=self.pysc.upload_file(file=content, title='Proposição '+ str(item)))     
           else:
              storage_path.manage_addFile(id=pdf_assinado,file=self.pysc.upload_file(file=content, title='Proposição '+ str(item)))
        if len(lista) == 1:
           redirect_url = self.portal_url()+'/cadastros/proposicao/proposicao_mostrar_proc?cod_proposicao=' + proposicao.cod_proposicao
           REQUEST = self.REQUEST
           RESPONSE = REQUEST.RESPONSE
           RESPONSE.redirect(redirect_url)
        else:
           redirect_url = self.portal_url()+'/cadastros/proposicao/proposicao_index_html?ind_enviado=0'
           REQUEST = self.REQUEST
           RESPONSE = REQUEST.RESPONSE
           RESPONSE.redirect(redirect_url)

    def requerimento_aprovar(self, cod_sessao_plen, nom_resultado, cod_materia):
        if hasattr(self.sapl_documentos.props_sagl, 'logo_carimbo.png'):
           arq = getattr(self.sapl_documentos.props_sagl, 'logo_carimbo.png')     
           arquivo = BytesIO(str(arq.data))    
           logo = ImageReader(arquivo)
        elif hasattr(self.sapl_documentos.props_sagl, 'logo_casa.gif'):
           arq = getattr(self.sapl_documentos.props_sagl, 'logo_casa.gif')    
           arquivo = BytesIO(str(arq.data))
           logo = ImageReader(arquivo)
        else:
           arq = getattr(self.imagens, 'brasao.gif')
           arquivo = BytesIO(str(arq.data))
           logo = ImageReader(arquivo)
        nom_presidente = ''
        # obtem dados da sessao
        if cod_sessao_plen != '0' and cod_sessao_plen != '':
           for item in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao):
                   id_sessao = str(item.num_sessao_plen) + 'ª Reunião ' + tipo.nom_sessao + ' - '
               data = item.dat_inicio_sessao
               data1 = self.pysc.data_converter_pysc(data)
               num_legislatura = item.num_legislatura
           for composicao in self.zsql.composicao_mesa_sessao_obter_zsql(cod_sessao_plen=cod_sessao_plen, cod_cargo=1, ind_excluido=0):
               for parlamentar in self.zsql.parlamentar_obter_zsql(cod_parlamentar=composicao.cod_parlamentar):
                   nom_presidente = str(parlamentar.nom_parlamentar.decode('utf-8').upper())
           if nom_presidente == '':
              data = item.dat_inicio_sessao
              data1 = self.pysc.data_converter_pysc(data)
              for sleg in self.zsql.periodo_comp_mesa_obter_zsql(data=data1):
                  for cod_presidente in self.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp, cod_cargo=1):
                      for presidencia in self.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_presidente.cod_parlamentar):
                          nom_presidente = str(presidencia.nom_parlamentar.decode('utf-8').upper())
        else:
           id_sessao = ''
           data = ''
           nom_presidente = ''
        # prepara carimbo
        packet = BytesIO()
        can = canvas.Canvas(packet)
        #can.drawImage(logo, 490, 715,  width=50, height=50, mask='auto')
        texto = "%s" % (str(nom_resultado.decode('utf-8').upper()))
        sessao = "%s%s" % (id_sessao, data)
        presidente = "%s " % (nom_presidente)
        cargo = "Presidente"
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial_Bold', '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'))
        can.setFont('Arial_Bold', 10)
        can.drawString(400, 750, texto)
        can.setFont('Arial', 9)
        can.drawString(400, 740, sessao)
        can.drawString(400, 730, presidente)
        can.drawString(400, 720, cargo)
        can.showPage()
        can.save()
        packet.seek(0)
        new_pdf = PdfFileReader(packet)
        output = PdfFileWriter()
        # adiciona carimbo aos documentos
        for materia in self.zsql.materia_obter_zsql(cod_materia=cod_materia):
            storage_path = self.sapl_documentos.materia
            nom_pdf_saida = str(materia.cod_materia) + "_texto_integral.pdf"
            if hasattr(storage_path, nom_pdf_saida):
               arq = getattr(storage_path, nom_pdf_saida)
               arquivo = BytesIO(str(arq.data))
               existing_pdf = PdfFileReader(arquivo, strict=False)
               numPages = existing_pdf.getNumPages()
               # Mescla canvas
               for page in range(existing_pdf.getNumPages()):
                   page_pdf = existing_pdf.getPage(page)
                   # carimbo na primeira pagina
                   if page == 0:
                      page_pdf.merge_page(new_pdf.getPage(0))
                   output.addPage(page_pdf)
               outputStream = BytesIO()
               output.write(outputStream)
               outputStream.seek(0)
               content = outputStream.getvalue()
               if hasattr(storage_path, nom_pdf_saida):
                  arq=storage_path[nom_pdf_saida]
                  arq.manage_upload(file=self.pysc.upload_file(file=content, title='Matéria com carimbo')) 
               else:
                  storage_path.manage_addFile(id=nom_pdf_saida,file=self.pysc.upload_file(file=content, title='Matéria com carimbo'))

    def _getValidEmailAddress(self, member):
        email = None
        for usuario in self.zsql.usuario_obter_zsql(col_username=member):
            email = usuario.end_email
        return email
    security.declarePublic( 'mailPassword' )
    def mailPassword(self, forgotten_userid, REQUEST):
        membership = getToolByName(self, 'portal_membership')
        member = membership.getMemberById(forgotten_userid)
        if member is None:
            msg = 'Usuário não encontrado'
            raise ValueError(msg)
        email = self._getValidEmailAddress(member)
        if email is None or email == '':
           msg = 'Endereço de email não cadastrado'
           raise ValueError(msg)
        method = self.pysc.password_email
        kw = {'email': email, 'member': member, 'password': member.getPassword()}
        if getattr(aq_base(method), 'isDocTemp', 0):
            mail_text = method(self, REQUEST, **kw)
        else:
            mail_text = method(**kw)
        host = self.MailHost
        host.send( mail_text )
        return self.generico.mail_password_response( self, REQUEST )

    def create_payload(self, cod_materia):
        data = {}
        for materia in self.zsql.materia_obter_zsql(cod_materia=cod_materia, ind_excluido=0):
            data['codmateria'] = materia.cod_materia
            data['tipo'] = materia.des_tipo_materia
            data['numero'] = materia.num_ident_basica
            data['ano'] = materia.ano_ident_basica
            data['ementa'] = materia.txt_ementa
            data['autoria'] = ''
            autores = self.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia, ind_excluido=0)
            fields = autores.data_dictionary().keys()
            lista_autor = []
            for autor in autores:
                for field in fields:
                    nome_autor = autor['nom_autor_join']
                lista_autor.append(nome_autor)
            data['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor])
            data['linkarquivo'] = ''
            if hasattr(self.sapl_documentos.materia, str(materia.cod_materia) + '_texto_integral.pdf'):
               data['linkarquivo'] = self.portal_url() + '/sapl_documentos/materia/' + str(materia.cod_materia) + '_texto_integral.pdf'
            data['casalegislativa'] = self.sapl_documentos.props_sagl.nom_casa
            data['prazo'] = ''
            for tram in self.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, ind_ult_tramitacao=1):
                if tram.dat_fim_prazo != None:
                   data['prazo'] = tram.dat_fim_prazo
        serialized = json.dumps(data, sort_keys=True, indent=3)
        return json.loads(serialized)

    def protocolo_prefeitura(self, cod_materia):
        API_ENDPOINT = ''
        API_USER = ''
        API_PASSWORD = ''
        session = requests.Session()
        session.auth = (API_USER, API_PASSWORD)
        auth = session.post(API_ENDPOINT)
        with session as s:
             response = s.post(API_ENDPOINT, data=self.create_payload(cod_materia))
        if (str(response.status_code) == '200'):
            r = response.json()
            protocolo = r[0]['numero_protocolo']
            data = r[0]['criado_em']
            #data = DateTime(r[0]['criado_em']).strftime('%d/%m/%Y às %H:%M:%S')
            return 'Protocolado na Prefeitura Municipal sob nº ' + str(protocolo) + ' em ' + str(data)
        else:
            r = response.json()
            msg = r[0]['Detail'] + 'Houve um erro ao enviar a matéria para a Prefeitura. Código da matéria: ' + cod_materia
            raise ValueError(msg)

    def cep_buscar(self, numcep):
        url = 'https://viacep.com.br/ws/%s/json/'%numcep
        resposta = requests.get(url)
        dic_requisicao = resposta.json()
        cepArray=[]
        if 'errors' not in dic_requisicao:
           cepDict = {}
           cepDict['logradouro'] = dic_requisicao['logradouro']
           cepDict['bairro'] = dic_requisicao['bairro']
           cepDict['cidade'] = dic_requisicao['localidade']
           cepDict['estado'] = dic_requisicao['uf']
           cepArray.append(cepDict)
           return json.dumps(cepDict)

    def pasta_digital(self, cod_materia):
        if cod_materia.isdigit():
           cod_materia = cod_materia
        else:
           cod_materia = self.pysc.b64decode_pysc(codigo=str(cod_materia))
        for materia in self.zsql.materia_obter_zsql(cod_materia=cod_materia):
            pasta = []
            if hasattr(self.sapl_documentos.materia, str(materia.cod_materia) + '_texto_integral.pdf'):
               dic_doc = {}
               dic_doc["id"] = str(materia.sgl_tipo_materia) + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
               dic_doc["title"] = str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
               dic_doc["data"] = DateTime(materia.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               for proposicao in self.zsql.proposicao_obter_zsql(ind_mat_ou_doc='M', cod_mat_ou_doc=materia.cod_materia):
                   dic_doc["data"] = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               if materia.num_protocolo != None:
                  for protocolo in self.zsql.protocolo_obter_zsql(num_protocolo=materia.num_protocolo, ano_protocolo=materia.ano_ident_basica):
                      dic_doc["data"] = DateTime(protocolo.dat_timestamp, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
               dic_doc["arquivo"] = getattr(self.sapl_documentos.materia, str(materia.cod_materia) + '_texto_integral.pdf')
               dic_doc["url"] = getattr(self.sapl_documentos.materia, str(materia.cod_materia) + '_texto_integral.pdf').absolute_url()
               arquivo =  BytesIO(str(dic_doc["arquivo"].data))
               existing_pdf = PdfFileReader(arquivo, strict=False)
               dic_doc["paginas_doc"] = existing_pdf.getNumPages()
               dic_doc["arquivob64"] = base64.b64encode(str(dic_doc["arquivo"].data))
               paginas = []
               for page_num, i in enumerate(list(range(dic_doc["paginas_doc"])), start=1):
                   dic_paginas = {}
                   dic_paginas["num_pagina"] = page_num
                   paginas.append(dic_paginas)
               dic_doc["paginas"] = paginas
               dic_doc["paginas_geral"] = paginas
               pasta.append(dic_doc)
            for substitutivo in self.zsql.substitutivo_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                if hasattr(self.sapl_documentos.substitutivo, str(substitutivo.cod_substitutivo) + '_substitutivo.pdf'):
                   dic_anexo = {}
                   dic_anexo["id"] = ''
                   dic_anexo["title"] = 'Substitutivo nº ' + str(substitutivo.num_substitutivo)
                   dic_anexo["data"] = DateTime(substitutivo.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   for proposicao in self.zsql.proposicao_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo):
                       dic_anexo["data"] = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   dic_anexo["arquivo"] = getattr(self.sapl_documentos.substitutivo, str(substitutivo.cod_substitutivo) + '_substitutivo.pdf')
                   dic_anexo["url"] = getattr(self.sapl_documentos.substitutivo, str(substitutivo.cod_substitutivo) + '_substitutivo.pdf').absolute_url()
                   arquivo =  BytesIO(str(dic_anexo["arquivo"].data))
                   existing_pdf = PdfFileReader(arquivo, strict=False)
                   dic_anexo["arquivob64"] = base64.b64encode(str(dic_anexo["arquivo"].data))
                   dic_anexo["paginas_doc"] = existing_pdf.getNumPages()
                   paginas = []
                   for page_num, i in enumerate(list(range(dic_anexo["paginas_doc"])), start=1):
                       dic_paginas = {}
                       dic_paginas["num_pagina"] = page_num
                       paginas.append(dic_paginas)
                   dic_anexo["paginas"] = paginas
                   dic_anexo["paginas_geral"] = ''
                   pasta.append(dic_anexo)
            for eme in self.zsql.emenda_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                if hasattr(self.sapl_documentos.emenda, str(eme.cod_emenda) + '_emenda.pdf'):
                   dic_anexo = {}
                   dic_anexo["id"] = ''
                   dic_anexo["title"] = 'Emenda ' + eme.des_tipo_emenda +' nº ' + str(eme.num_emenda)
                   dic_anexo["data"] = DateTime(eme.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   for proposicao in self.zsql.proposicao_obter_zsql(cod_emenda=eme.cod_emenda):
                       dic_anexo["data"] = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   dic_anexo["arquivo"] = getattr(self.sapl_documentos.emenda, str(eme.cod_emenda) + '_emenda.pdf')
                   dic_anexo["url"] = getattr(self.sapl_documentos.emenda, str(eme.cod_emenda) + '_emenda.pdf').absolute_url()
                   arquivo = BytesIO(str(dic_anexo["arquivo"].data))
                   existing_pdf = PdfFileReader(arquivo, strict=False)
                   dic_anexo["paginas_doc"] = existing_pdf.getNumPages()
                   dic_anexo["arquivob64"] = base64.b64encode(str(dic_anexo["arquivo"].data))
                   dic_anexo["paginas_doc"] = existing_pdf.getNumPages()
                   paginas = []
                   for page_num, i in enumerate(list(range(dic_anexo["paginas_doc"])), start=1):
                       dic_paginas = {}
                       dic_paginas["num_pagina"] = page_num
                       paginas.append(dic_paginas)
                   dic_anexo["paginas"] = paginas
                   dic_anexo["paginas_geral"] = ''
                   pasta.append(dic_anexo)
            for relat in self.zsql.relatoria_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                if hasattr(self.sapl_documentos.parecer_comissao, str(relat.cod_relatoria) + '_parecer.pdf'):
                   dic_relat = {}
                   dic_relat["id"] = ''
                   for comissao in self.zsql.comissao_obter_zsql(cod_comissao=relat.cod_comissao):
                       sgl_comissao = comissao.sgl_comissao
                   dic_relat["title"] = 'Parecer ' + str(sgl_comissao) + ' nº ' + str(relat.num_parecer) + '/' + str(relat.ano_parecer)
                   dic_relat["data"] = DateTime(relat.dat_destit_relator, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   for proposicao in self.zsql.proposicao_obter_zsql(cod_parecer=relat.cod_relatoria):
                       dic_relat["data"] = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   dic_relat["arquivo"] = getattr(self.sapl_documentos.parecer_comissao, str(relat.cod_relatoria) + '_parecer.pdf')
                   dic_relat["url"] = getattr(self.sapl_documentos.parecer_comissao, str(relat.cod_relatoria) + '_parecer.pdf').absolute_url()
                   arquivo =  BytesIO(str(dic_relat["arquivo"].data))
                   existing_pdf = PdfFileReader(arquivo, strict=False)
                   dic_relat["paginas_doc"] = existing_pdf.getNumPages()
                   dic_relat["arquivob64"] = base64.b64encode(str(dic_relat["arquivo"].data))
                   dic_relat["paginas_doc"] = existing_pdf.getNumPages()
                   paginas = []
                   for page_num, i in enumerate(list(range(dic_relat["paginas_doc"])), start=1):
                       dic_paginas = {}
                       dic_paginas["num_pagina"] = page_num
                       paginas.append(dic_paginas)
                   dic_relat["paginas"] = paginas
                   dic_relat["paginas_geral"] = ''
                   pasta.append(dic_relat)
            for documento in self.zsql.documento_acessorio_obter_zsql(cod_materia = cod_materia, ind_excluido=0):
                anon = getSecurityManager().getUser()
                if hasattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf'):
                   dic_anexo = {}
                   dic_anexo["id"] = ''
                   dic_anexo["title"] = documento.des_tipo_documento + ' - ' + documento.nom_documento
                   dic_anexo["data"] = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   if documento.ind_publico == 1:
                      dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf')
                      dic_anexo["url"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf').absolute_url()
                   elif documento.ind_publico == 0:
                      if (str(anon) == 'Anonymous User'):
                         dic_anexo["arquivo"] = getattr(self.sapl_documentos.modelo, 'lgpd-page.pdf')
                         dic_anexo["url"] = getattr(self.sapl_documentos.modelo, 'lgpd-page.pdf').absolute_url()
                      else:
                         dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf')
                         dic_anexo["url"] = getattr(self.sapl_documentos.materia, str(documento.cod_documento) + '.pdf').absolute_url()
                   arquivo = BytesIO(str(dic_anexo["arquivo"].data))
                   existing_pdf = PdfFileReader(arquivo, strict=False)
                   dic_anexo["paginas_doc"] = existing_pdf.getNumPages()
                   if documento.ind_publico == 1:
                      dic_anexo["arquivob64"] = base64.b64encode(str(dic_anexo["arquivo"].data))
                   elif documento.ind_publico == 0:
                      if (str(anon) == 'Anonymous User'):
                         lgpd_page = getattr(self.sapl_documentos.modelo, 'lgpd-page.pdf')
                         dic_anexo["arquivob64"] = base64.b64encode(str(lgpd_page.data))
                      else:
                         dic_anexo["arquivob64"] = base64.b64encode(str(dic_anexo["arquivo"].data))
                   paginas = []
                   for page_num, i in enumerate(list(range(dic_anexo["paginas_doc"])), start=1):
                       dic_paginas = {}
                       dic_paginas["num_pagina"] = page_num
                       paginas.append(dic_paginas)
                   dic_anexo["paginas"] = paginas
                   dic_anexo["paginas_geral"] = ''
                   pasta.append(dic_anexo)
            for tram in self.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, rd_ordem='1', ind_excluido=0):
                if hasattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram.pdf'):
                   dic_anexo = {}
                   dic_anexo["id"] = ''
                   dic_anexo["title"] = 'Tramitação (' + str(tram.des_status) + ')'
                   dic_anexo["data"] = DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   dic_anexo["arquivo"] = getattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram.pdf')
                   dic_anexo["url"] = getattr(self.sapl_documentos.materia.tramitacao, str(tram.cod_tramitacao) + '_tram.pdf').absolute_url()
                   arquivo =  BytesIO(str(dic_anexo["arquivo"].data))
                   existing_pdf = PdfFileReader(arquivo, strict=False)
                   dic_anexo["paginas_doc"] = existing_pdf.getNumPages()
                   dic_anexo["arquivob64"] = base64.b64encode(str(dic_anexo["arquivo"].data))
                   dic_anexo["paginas_doc"] = existing_pdf.getNumPages()
                   paginas = []
                   for page_num, i in enumerate(list(range(dic_anexo["paginas_doc"])), start=1):
                       dic_paginas = {}
                       dic_paginas["num_pagina"] = page_num
                       paginas.append(dic_paginas)
                   dic_anexo["paginas"] = paginas
                   dic_anexo["paginas_geral"] = ''
                   pasta.append(dic_anexo)
        pasta.sort(key=lambda dic: dic['data'])
        total = 0
        for i in pasta:
            total += i['paginas_doc']
        for i in pasta:
            i['paginas_geral'] = total
        return pasta


InitializeClass(SAGLTool)
