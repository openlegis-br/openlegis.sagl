# -*- coding: utf-8 -*-
import re
import os
import requests
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
from io import BytesIO
from PIL import Image
from appy.pod.renderer import Renderer
import pymupdf
from dateutil.parser import parse
from asn1crypto import cms
pymupdf.TOOLS.set_aa_level(0)
import pypdf
import qrcode
from barcode import generate
from barcode.writer import ImageWriter
#imports para assinatura digital
import base64
from zlib import crc32
import json
from openlegis.sagl.restpki import *
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
        camara = ['Câmara','Camara','camara','camara']
        assembleia = ['Assembléia','Assembleia','assembleia','assembléia']
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
                epigrafe = '%s de %s - %s, de %s' % (consulta.des_tipo_norma, localidade,sigla_uf, consulta.ano_norma)
            elif consulta.voc_lexml == 'constituicao':
                epigrafe = '%s do Estado de %s, de %s' % (consulta.des_tipo_norma, localidade, consulta.ano_norma)
            else:
                epigrafe = '%s n° %s,  de %s' % (consulta.des_tipo_norma, consulta.num_norma, self.pysc.data_converter_por_extenso_pysc(consulta.dat_norma))
            ementa = consulta.txt_ementa
            indexacao = consulta.txt_indexacao
            formato = 'text/html'
            id_documento = '%s_%s' % (str(cod_norma), self.sapl_documentos.norma_juridica.nom_documento)
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
        text = str(value).zfill(7)
        bcode = BytesIO()
        generate('Code128', text, writer=ImageWriter(), output=bcode)
        data = bcode.getvalue()
        return data

    def make_qrcode(self, text):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        fp = BytesIO()
        img.save(fp, "PNG")
        return fp

    def url(self):
        utool = getToolByName(self, 'portal_url')
        return utool.portal_url()

    def resize_and_crop(self,cod_parlamentar):
        image_file = '%s' % (cod_parlamentar) + "_foto_parlamentar"
        arq = getattr(self.sapl_documentos.parlamentar.fotos, image_file)
        img_path = BytesIO(bytes(arq.data))
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
           with BytesIO(bytes(arq.data)) as arq1:
                image = arq1.getvalue()
        else:
           install_home = os.environ.get('INSTALL_HOME')
           dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/brasao.gif')
           with open(dirpath, "rb") as arq:
                image = arq.read()
        brasao = image
        return brasao

    def ata_gerar_odt(self, ata_dic, nom_arquivo, nom_modelo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, nom_modelo)
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.ata_sessao.manage_addFile(id=nom_arquivo,file=content)
        odt = getattr(self.sapl_documentos.ata_sessao, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def ata_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = "%s"%cod_sessao_plen+'_ata_sessao.odt'
        nom_arquivo_pdf = "%s"%cod_sessao_plen+'_ata_sessao.pdf'
        arq = getattr(self.sapl_documentos.ata_sessao, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.ata_sessao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Ata'))

    def ata_comissao_gerar_odt(self, ata_dic, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "ata_comissao.odt")
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.reuniao_comissao.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.reuniao_comissao, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def ata_comissao_gerar_pdf(self, cod_reuniao):
        nom_arquivo_odt = "%s"%cod_reuniao+'_ata.odt'
        nom_arquivo_pdf = "%s"%cod_reuniao+'_ata.pdf'
        arq = getattr(self.sapl_documentos.reuniao_comissao, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.reuniao_comissao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Ata Comissão'))

    def iom_gerar_odt(self, inf_basicas_dic, lst_mesa, lst_presenca_sessao, lst_materia_apresentada, lst_reqplen, lst_reqpres, lst_indicacao, lst_presenca_ordem_dia, lst_votacao, lst_presenca_expediente, lst_oradores, lst_presenca_encerramento, lst_presidente, lst_psecretario, lst_ssecretario):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "iom.odt")
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
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

    def ordem_dia_gerar_odt(self, inf_basicas_dic, nom_arquivo, nom_modelo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, nom_modelo)
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def ordem_dia_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = "%s"%cod_sessao_plen+'_pauta_sessao.odt'
        nom_arquivo_pdf = "%s"%cod_sessao_plen+'_pauta_sessao.pdf'
        arq = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
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
        merger = pymupdf.open()
        for pauta in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
          nom_arquivo_pdf = "%s"%cod_sessao_plen+'_pauta_completa.pdf'
          nom_pdf_amigavel = str(pauta.num_sessao_plen)+'-sessao-'+ str(pauta.dat_inicio)+'-pauta_completa.pdf'
          nom_pdf_amigavel = nom_pdf_amigavel
          if hasattr(self.sapl_documentos.pauta_sessao, str(cod_sessao_plen) + '_pauta_sessao.pdf'):
             arq = getattr(self.sapl_documentos.pauta_sessao, str(cod_sessao_plen) + '_pauta_sessao.pdf')
             arquivo = BytesIO(bytes(arq.data))
             texto_anexo = pymupdf.open(stream=arquivo)
             merger.insert_pdf(texto_anexo)
          lst_materia = []
          for materia in self.zsql.ordem_dia_obter_zsql(cod_sessao_plen=pauta.cod_sessao_plen,ind_excluido=0):
              if materia.cod_materia != None and materia.cod_materia != '':
                 cod_materia = int(materia.cod_materia)
                 lst_materia.append(cod_materia)
          lst_materia = [i for n, i in enumerate(lst_materia) if i not in lst_materia[n + 1:]]
          for cod_materia in lst_materia:
              if hasattr(self.sapl_documentos.materia, str(cod_materia) + '_redacao_final.pdf'):
                 arq = getattr(self.sapl_documentos.materia, str(cod_materia) + '_redacao_final.pdf')
                 arquivo = BytesIO(bytes(arq.data))
                 texto_anexo = pymupdf.open(stream=arquivo)
                 merger.insert_pdf(texto_anexo)
              elif hasattr(self.sapl_documentos.materia, str(cod_materia) + '_texto_integral.pdf'):
                   arq = getattr(self.sapl_documentos.materia, str(cod_materia) + '_texto_integral.pdf')
                   arquivo = BytesIO(bytes(arq.data))
                   texto_anexo = pymupdf.open(stream=arquivo)
                   merger.insert_pdf(texto_anexo)
                   for anexada in self.zsql.anexada_obter_zsql(cod_materia_principal=cod_materia,ind_excluido=0):
                       anexada = anexada.cod_materia_anexada
                       if hasattr(self.sapl_documentos.materia, str(anexada) + '_texto_integral.pdf'):
                          arq = getattr(self.sapl_documentos.materia, str(anexada) + '_texto_integral.pdf')
                          arquivo = BytesIO(bytes(arq.data))
                          texto_anexo = pymupdf.open(stream=arquivo)
                          merger.insert_pdf(texto_anexo)
                   for subst in self.zsql.substitutivo_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                       substitutivo = subst.cod_substitutivo
                       if hasattr(self.sapl_documentos.substitutivo, str(substitutivo) + '_substitutivo.pdf'):
                          arq = getattr(self.sapl_documentos.substitutivo, str(substitutivo) + '_substitutivo.pdf')
                          arquivo = BytesIO(bytes(arq.data))
                          texto_anexo = pymupdf.open(stream=arquivo)
                          merger.insert_pdf(texto_anexo)
                   for eme in self.zsql.emenda_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                       emenda = eme.cod_emenda
                       if hasattr(self.sapl_documentos.emenda, str(emenda) + '_emenda.pdf'):
                          arq = getattr(self.sapl_documentos.emenda, str(emenda) + '_emenda.pdf')
                          arquivo = BytesIO(bytes(arq.data))
                          texto_anexo = pymupdf.open(stream=arquivo)
                          merger.insert_pdf(texto_anexo)
                   for relat in self.zsql.relatoria_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
                       relatoria = relat.cod_relatoria
                       if hasattr(self.sapl_documentos.parecer_comissao, str(relatoria) + '_parecer.pdf'):
                          arq = getattr(self.sapl_documentos.parecer_comissao, str(relatoria) + '_parecer.pdf')
                          arquivo = BytesIO(bytes(arq.data))
                          texto_anexo = pymupdf.open(stream=arquivo)
                          merger.insert_pdf(texto_anexo)
          merged_pdf = merger.tobytes(deflate=True, garbage=3, use_objstms=1)
          existing_pdf = pymupdf.open(stream=merged_pdf)
          numPages = existing_pdf.page_count
          for page_index, i in enumerate(range(len(existing_pdf))):
              w = existing_pdf[page_index].rect.width
              h = existing_pdf[page_index].rect.height
              margin = 5
              left = 10 - margin
              bottom = h - 60 - margin
              black = pymupdf.pdfcolor["black"]
              text = "Fls. %s/%s" % (i+1, numPages)
              p1 = pymupdf.Point(w - 70 - margin, margin + 20) # numero de pagina
              shape = existing_pdf[page_index].new_shape()
              shape.draw_circle(p1,1)
              shape.insert_text(p1, text, fontname = "helv", fontsize = 8)
              shape.commit()
          content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
          if nom_arquivo_pdf in self.sapl_documentos.pauta_sessao:
             arq = getattr(self.sapl_documentos.pauta_sessao,nom_arquivo_pdf)
             arq.manage_upload(file=content)
          else:
             self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo_pdf,file=content, title='Ordem do Dia')
          self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
          self.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %nom_pdf_amigavel)
          return content

    def pdf_expediente_completo(self, cod_sessao_plen):
        merger = pymupdf.open()
        for pauta in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
          nom_pdf_amigavel = str(pauta.num_sessao_plen)+'_sessao_'+'expediente_completo.pdf'
          if hasattr(self.sapl_documentos.pauta_sessao, str(cod_sessao_plen) + '_pauta_expediente.pdf'):
             arq = getattr(self.sapl_documentos.pauta_sessao, str(cod_sessao_plen) + '_pauta_expediente.pdf')
             arquivo = BytesIO(bytes(arq.data))
             texto_anexo = pymupdf.open(stream=arquivo)
             merger.insert_pdf(texto_anexo)
          for item in self.zsql.materia_apresentada_sessao_obter_zsql(cod_sessao_plen = pauta.cod_sessao_plen, ind_excluido = 0):
              if item.cod_materia != None:
                 if hasattr(self.sapl_documentos.materia, str(item.cod_materia) + '_texto_integral.pdf'):
                    arq = getattr(self.sapl_documentos.materia, str(item.cod_materia) + '_texto_integral.pdf')
                    arquivo = BytesIO(bytes(arq.data))
                    texto_anexo = pymupdf.open(stream=arquivo)
                    merger.insert_pdf(texto_anexo)
              elif item.cod_emenda != None:
                   if hasattr(self.sapl_documentos.emenda, str(item.cod_emenda) + '_emenda.pdf'):
                      arq = getattr(self.sapl_documentos.emenda, str(item.cod_emenda) + '_emenda.pdf')
                      arquivo = BytesIO(bytes(arq.data))
                      texto_anexo = pymupdf.open(stream=arquivo)
                      merger.insert_pdf(texto_anexo)
              elif item.cod_substitutivo != None:
                   if hasattr(self.sapl_documentos.substitutivo, str(item.cod_substitutivo) + '_substitutivo.pdf'):
                      arq = getattr(self.sapl_documentos.substitutivo, str(item.cod_substitutivo) + '_substitutivo.pdf')
                      arquivo = BytesIO(bytes(arq.data))
                      texto_anexo = pymupdf.open(stream=arquivo)
                      merger.insert_pdf(texto_anexo)
              elif item.cod_parecer != None:
                   if hasattr(self.sapl_documentos.parecer_comissao, str(item.cod_parecer) + '_parecer.pdf'):
                      arq = getattr(self.sapl_documentos.parecer_comissao, str(item.cod_parecer) + '_parecer.pdf')
                      arquivo = BytesIO(bytes(arq.data))
                      texto_anexo = pymupdf.open(stream=arquivo)
                      merger.insert_pdf(texto_anexo)
              elif item.cod_documento != None:
                   if hasattr(self.sapl_documentos.administrativo, str(item.cod_documento) + '_texto_integral.pdf'):
                      arq = getattr(self.sapl_documentos.administrativo, str(item.cod_documento) + '_texto_integral.pdf')
                      arquivo = BytesIO(bytes(arq.data))
                      texto_anexo = pymupdf.open(stream=arquivo)
                      merger.insert_pdf(texto_anexo)
          for item in self.zsql.expediente_materia_obter_zsql(cod_sessao_plen = pauta.cod_sessao_plen, ind_excluido = 0):
              if item.cod_materia != None:
                 if hasattr(self.sapl_documentos.materia, str(item.cod_materia) + '_texto_integral.pdf'):
                    arq = getattr(self.sapl_documentos.materia, str(item.cod_materia) + '_texto_integral.pdf')
                    arquivo = BytesIO(bytes(arq.data))
                    texto_anexo = pymupdf.open(stream=arquivo)
                    merger.insert_pdf(texto_anexo)
              elif item.cod_parecer != None:
                   if hasattr(self.sapl_documentos.parecer_comissao, str(item.cod_parecer) + '_parecer.pdf'):
                      arq = getattr(self.sapl_documentos.parecer_comissao, str(item.cod_parecer) + '_parecer.pdf')
                      arquivo = BytesIO(bytes(arq.data))
                      texto_anexo = pymupdf.open(stream=arquivo)
                      merger.insert_pdf(texto_anexo)
          merged_pdf = merger.tobytes(deflate=True, garbage=3, use_objstms=1)
          existing_pdf = pymupdf.open(stream=merged_pdf)
          numPages = existing_pdf.page_count
          for page_index, i in enumerate(range(len(existing_pdf))):
              w = existing_pdf[page_index].rect.width
              h = existing_pdf[page_index].rect.height
              margin = 5
              left = 10 - margin
              bottom = h - 60 - margin
              black = pymupdf.pdfcolor["black"]
              text = "Fls. %s/%s" % (i+1, numPages)
              p1 = pymupdf.Point(w - 70 - margin, margin + 20) # numero de pagina
              shape = existing_pdf[page_index].new_shape()
              shape.draw_circle(p1,1)
              shape.insert_text(p1, text, fontname = "helv", fontsize = 8)
              shape.commit()
          content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
          self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
          self.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %nom_pdf_amigavel)
          return content

    def oradores_gerar_odt(self, inf_basicas_dic, lst_oradores, lst_presidente, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "oradores.odt")
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        # atribui o brasao no locals
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.oradores_expediente.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.oradores_expediente, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def oradores_gerar_pdf(self,cod_sessao_plen):
        nom_arquivo_odt = "%s"%cod_sessao_plen+'_oradores_expediente.odt'
        nom_arquivo_pdf = "%s"%cod_sessao_plen+'_oradores_expediente.pdf'
        arq = getattr(self.sapl_documentos.oradores_expediente, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.oradores_expediente.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Oradores'))

    def expediente_gerar_odt(self, inf_basicas_dic, lst_indicacoes, lst_requerimentos, lst_mocoes, lst_oradores, lst_presidente, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "expediente.odt")
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def expediente_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = "%s"%cod_sessao_plen+'_expediente.odt'
        nom_arquivo_pdf = "%s"%cod_sessao_plen+'_expediente.pdf'
        arq = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Pauta do Expediente'))

    def resumo_gerar_odt(self, resumo_dic, nom_arquivo, nom_modelo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, nom_modelo)
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s" % nom_arquivo
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.materia_odt.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.materia_odt, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def doc_acessorio_gerar_pdf(self, cod_documento):
        nom_arquivo_odt = "%s"%cod_documento+'.odt'
        nom_arquivo_pdf = "%s"%cod_documento+'.pdf'
        arq = getattr(self.sapl_documentos.materia_odt, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.materia.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Documento Acessório'))

    def doc_acessorio_adm_gerar_odt(self, inf_basicas_dic, documento_dic, modelo_documento):
        arq = getattr(self.sapl_documentos.modelo.documento_administrativo, modelo_documento)
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s" % documento_dic['nom_arquivo']
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_odt, "rb").read()
        os.unlink(output_file_odt)
        self.sapl_documentos.administrativo.manage_addFile(id=output_file_odt,file=data)
        odt = getattr(self.sapl_documentos.administrativo, output_file_odt)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def doc_acessorio_adm_gerar_pdf(self, cod_documento_acessorio):
        nom_arquivo_odt = "%s"%cod_documento_acessorio+'.odt'
        nom_arquivo_pdf = "%s"%cod_documento_acessorio+'.pdf'
        arq = getattr(self.sapl_documentos.administrativo, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.administrativo.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Documento Acessório'))

    def oficio_ind_gerar_odt(self, inf_basicas_dic, lst_indicacao, lst_presidente):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "oficio_indicacao.odt")
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.emenda.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.emenda, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def emenda_gerar_pdf(self,cod_emenda):
        nom_arquivo_odt = "%s"%cod_emenda+'_emenda.odt'
        nom_arquivo_pdf = "%s"%cod_emenda+'_emenda.pdf'
        arq = getattr(self.sapl_documentos.emenda, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo_pdf, "rb").read()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.emenda.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Emenda'))

    def capa_processo_gerar_odt(self, capa_dic):
        arq = getattr(self.sapl_documentos.modelo.materia, "capa_processo.odt")
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s" % capa_dic['nom_arquivo_odt']
        output_file_pdf = "%s" % capa_dic['nom_arquivo_pdf']
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        with open(output_file_odt, 'rb') as data:
           odtFile = BytesIO(data.read())
        os.unlink(output_file_odt)
        renderer = Renderer(odtFile,locals(),output_file_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        with open(output_file_pdf, 'rb') as dados:
           data = BytesIO(dados.read())
        os.unlink(output_file_pdf)
        if hasattr(self.temp_folder,output_file_pdf):
           self.temp_folder.manage_delObjects(ids=output_file_pdf)
        self.temp_folder.manage_addFile(id=output_file_pdf, file=data)

    def capa_processo_adm_gerar_odt(self, capa_dic):
        arq = getattr(self.sapl_documentos.modelo.documento_administrativo, "capa_processo_adm.odt")
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s" % capa_dic['nom_arquivo_odt']
        output_file_pdf = "%s" % capa_dic['nom_arquivo_pdf']
        renderer = Renderer(template_file, locals(), output_file_odt, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        with open(output_file_odt, "rb") as data:
            odtFile = BytesIO(bytes(data.read()))
        os.unlink(output_file_odt)
        renderer = Renderer(odtFile,locals(),output_file_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        with open(output_file_pdf, "rb") as data:
            data = BytesIO(bytes(data.read()))
        os.unlink(output_file_pdf)
        if hasattr(self.temp_folder,output_file_pdf):
           self.temp_folder.manage_delObjects(ids=output_file_pdf)
        self.temp_folder.manage_addFile(id=output_file_pdf, file=data)

    def materia_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia, modelo_proposicao)
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.materia_odt.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.materia_odt, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def materia_gerar_pdf(self, cod_materia):
        nom_arquivo_odt = "%s"%cod_materia+'_texto_integral.odt'
        nom_arquivo_pdf = "%s"%cod_materia+'_texto_integral.pdf'
        arq = getattr(self.sapl_documentos.materia_odt, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        renderer = Renderer(odtFile,locals(), nom_arquivo_pdf, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.materia.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Matéria'))

    def materias_expediente_gerar_ods(self, relatorio_dic, total_assuntos, parlamentares, nom_arquivo):
        arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "relatorio-expediente.odt")
        template_file = BytesIO(bytes(arq.data))
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
        odtFile = BytesIO(bytes(arq.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(), nom_arquivo_pdf, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.materia.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Redação Final'))

    def norma_gerar_odt(self, inf_basicas_dic, nom_arquivo, des_tipo_norma, num_norma, ano_norma, dat_norma, data_norma, txt_ementa, modelo_norma):
        arq = getattr(self.sapl_documentos.modelo.norma, modelo_norma)
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.norma_juridica.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.norma_juridica, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def norma_gerar_pdf(self, cod_norma, tipo_texto):
        nom_arquivo_odt = "%s"%cod_norma+'_texto_integral.odt'
        arq = getattr(self.sapl_documentos.norma_juridica, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.administrativo.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.administrativo, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def oficio_gerar_pdf(self, cod_documento):
        nom_arquivo_odt = "%s"%cod_documento+'_texto_integral.odt'
        nom_arquivo_pdf = "%s"%cod_documento+'_texto_integral.pdf'
        arq = getattr(self.sapl_documentos.administrativo, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.administrativo.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Documento'))

    def tramitacao_documento_juntar(self,cod_tramitacao):
        merger = pymupdf.open()
        arquivoPdf=str(cod_tramitacao)+"_tram.pdf"
        arquivoPdfAnexo=str(cod_tramitacao)+"_tram_anexo1.pdf"
        if hasattr(self.sapl_documentos.administrativo.tramitacao,arquivoPdf):
           arq = getattr(self.sapl_documentos.administrativo.tramitacao, arquivoPdf)
           arquivo = BytesIO(bytes(arq.data))
           arquivo.seek(0)
           texto_tram = pymupdf.open(stream=arquivo)
           merger.insert_pdf(texto_tram)
           self.sapl_documentos.administrativo.tramitacao.manage_delObjects(arquivoPdf)
        if hasattr(self.sapl_documentos.administrativo.tramitacao,arquivoPdfAnexo):
           arq = getattr(self.sapl_documentos.administrativo.tramitacao, arquivoPdfAnexo)
           arquivo = BytesIO(bytes(arq.data))
           arquivo.seek(0)
           texto_anexo = pymupdf.open(stream=arquivo)
           merger.insert_pdf(texto_anexo)
           self.sapl_documentos.administrativo.tramitacao.manage_delObjects(arquivoPdfAnexo)
        outputStream = BytesIO()
        merger.save(outputStream, linear=True)
        outputStream.seek(0)
        content = outputStream.getvalue()
        self.sapl_documentos.administrativo.tramitacao.manage_addFile(id=arquivoPdf,file=content, title='Tramitação Documento')

    def tramitacao_materia_juntar(self,cod_tramitacao):
        merger = pymupdf.open()
        arquivoPdf=str(cod_tramitacao)+"_tram.pdf"
        arquivoPdfAnexo=str(cod_tramitacao)+"_tram_anexo1.pdf"
        if hasattr(self.sapl_documentos.materia.tramitacao,arquivoPdf):
           arq = getattr(self.sapl_documentos.materia.tramitacao, arquivoPdf)
           arquivo = BytesIO(bytes(arq.data))
           arquivo.seek(0)
           texto_tram = pymupdf.open(stream=arquivo)
           merger.insert_pdf(texto_tram)
           self.sapl_documentos.materia.tramitacao.manage_delObjects(arquivoPdf)
        if hasattr(self.sapl_documentos.materia.tramitacao,arquivoPdfAnexo):
           arq = getattr(self.sapl_documentos.materia.tramitacao, arquivoPdfAnexo)
           arquivo = BytesIO(bytes(arq.data))
           arquivo.seek(0)
           texto_anexo = pymupdf.open(stream=arquivo)
           merger.insert_pdf(texto_anexo)
           self.sapl_documentos.materia.tramitacao.manage_delObjects(arquivoPdfAnexo)
        outputStream = BytesIO()
        merger.save(outputStream, linear=True)
        outputStream.seek(0)
        content = outputStream.getvalue()
        self.sapl_documentos.materia.tramitacao.manage_addFile(id=arquivoPdf,file=content, title='Tramitação Matéria')

    def parecer_gerar_odt(self, inf_basicas_dic, nom_arquivo, nom_comissao, materia_vinculada, nom_autor, txt_ementa, tip_apresentacao, tip_conclusao, data_parecer, nom_relator, lst_composicao, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia.parecer, modelo_proposicao)
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_odt = "%s"%nom_arquivo
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.parecer_comissao.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.parecer_comissao, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def parecer_gerar_pdf(self, cod_parecer):
        nom_arquivo_odt = "%s"%cod_parecer+'_parecer.odt'
        nom_arquivo_pdf = "%s"%cod_parecer+'_parecer.pdf'
        arq = getattr(self.sapl_documentos.parecer_comissao, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        renderer = Renderer(odtFile,locals(),nom_arquivo_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        content = open(nom_arquivo_pdf, "rb").read()
        os.unlink(nom_arquivo_pdf)
        self.sapl_documentos.parecer_comissao.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Parecer'))

    def peticao_gerar_odt(self, inf_basicas_dic, nom_arquivo, modelo_path):
        utool = getToolByName(self, 'portal_url')
        portal = utool.getPortalObject()
        modelo = portal.unrestrictedTraverse(modelo_path)
        template_file = BytesIO(bytes(modelo.data))
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
        odtFile = BytesIO(bytes(arquivo.data))
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
        content = BytesIO(bytes(arq.data))
        image_one = content.getvalue()
        return image_one

    def get_proposicao_image_two(self, num_proposicao):
        id_image2 = str(num_proposicao) + '_image_2.jpg'
        arq = getattr(self.sapl_documentos.proposicao, id_image2)
        content = BytesIO(bytes(arq.data))
        image_two = content.getvalue()
        return image_two

    def get_proposicao_image_three(self, num_proposicao):
        id_image3 = str(num_proposicao) + '_image_3.jpg'
        arq = getattr(self.sapl_documentos.proposicao, id_image3)
        content = BytesIO(bytes(arq.data))
        image_three = content.getvalue()
        return image_three

    def get_proposicao_image_four(self, num_proposicao):
        id_image4 = str(num_proposicao) + '_image_4.jpg'
        arq = getattr(self.sapl_documentos.proposicao, id_image4)
        content = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(modelo.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        if (inf_basicas_dic['des_tipo_proposicao'] == 'Requerimento' or inf_basicas_dic['des_tipo_proposicao'] == 'Indicação'):
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
        odt = getattr(self.sapl_documentos.proposicao, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def proposicao_gerar_pdf(self, cod_proposicao):
        merger = pymupdf.open()
        nom_arquivo_odt = "%s"%cod_proposicao+'.odt'
        nom_arquivo_pdf = "%s"%cod_proposicao+'.pdf'
        arquivo = getattr(self.sapl_documentos.proposicao, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arquivo.data))
        odtFile.seek(0)
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),output_file_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        with open(output_file_pdf, 'rb') as download:
             texto_pdf = pymupdf.open(download)
             merger.insert_pdf(texto_pdf)
        os.unlink(output_file_pdf)
        for anexo in self.pysc.anexo_proposicao_pysc(cod_proposicao,listar=True):
            arq = getattr(self.sapl_documentos.proposicao, anexo)
            arquivo = BytesIO(bytes(arq.data))
            arquivo.seek(0)
            #with pymupdf.open(stream=arquivo) as texto_anexo:
            texto_anexo = pymupdf.open(stream=arquivo)
            merger.insert_pdf(texto_anexo)
            arquivo.close()
        content = merger.tobytes()
        self.sapl_documentos.proposicao.manage_addFile(id=nom_arquivo_pdf,file=bytes(content),title='Proposição '+ cod_proposicao)
        pdf = getattr(self.sapl_documentos.proposicao, nom_arquivo_pdf)
        pdf.manage_permission('View', roles=['Manager','Authenticated','Anonymous'], acquire=0)

    def substitutivo_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia.substitutivo, modelo_proposicao)
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(nom_arquivo, "rb").read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.substitutivo.manage_addFile(id=nom_arquivo,file=data)
        odt = getattr(self.sapl_documentos.substitutivo, nom_arquivo)
        odt.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def substitutivo_gerar_pdf(self,cod_substitutivo):
        nom_arquivo_odt = "%s"%cod_substitutivo+'_substitutivo.odt'
        nom_arquivo_pdf = "%s"%cod_substitutivo+'_substitutivo.pdf'
        arquivo = getattr(self.sapl_documentos.substitutivo, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arquivo.data))
        output_file_pdf = os.path.normpath(nom_arquivo_pdf)
        renderer = Renderer(odtFile,locals(),output_file_pdf,pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_pdf, "rb").read()
        os.unlink(output_file_pdf)
        content = data.getvalue()
        self.sapl_documentos.substitutivo.manage_addFile(id=nom_arquivo_pdf,file=self.pysc.upload_file(file=content, title='Substitutivo'))

    def pessoas_exportar(self, pessoas):
        arq = getattr(self.sapl_documentos.modelo, "planilha-visitantes.ods")
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
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
        template_file = BytesIO(bytes(arq.data))
        output_file_ods = "normas.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def protocolo_barcode(self,cod_protocolo):
        sgl_casa = self.sapl_documentos.props_sagl.sgl_casa
        for protocolo in self.zsql.protocolo_obter_zsql(cod_protocolo=cod_protocolo):
          string = str(protocolo.cod_protocolo).zfill(7)
          texto = 'PROT-'+ str(sgl_casa) + ' ' + str(protocolo.num_protocolo)+'/'+str(protocolo.ano_protocolo)
          data = str(DateTime(protocolo.dat_protocolo, datefmt='international').strftime('%d/%m/%Y')) + ' ' + protocolo.hor_protocolo
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
        arq = getattr(self.sapl_documentos.protocolo, nom_pdf_protocolo)
        arquivo = BytesIO(bytes(arq.data))
        existing_pdf = pymupdf.open(stream=arquivo)
        numPages = existing_pdf.page_count
        stream = self.create_barcode(value=string)
        w = existing_pdf[0].rect.width
        h = existing_pdf[0].rect.height
        margin = 10
        top = margin + 50
        right = w - 40 -margin
        black = pymupdf.pdfcolor["black"]
        rect = pymupdf.Rect(right,top,right+40,top+40)  # barcode bottom right square
        existing_pdf[0].insert_image(rect, stream=stream, rotate=-90)
        text2 = texto + '\n' + data + '\n' + num_materia
        p2 = pymupdf.Point(w - 8 - margin, margin + 90) # margem superior
        shape = existing_pdf[0].new_shape()
        shape.draw_circle(p2,1)
        shape.insert_text(p2, text2, fontname = "helv", fontsize = 7, rotate=-90)
        shape.commit()
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        if nom_pdf_protocolo in self.sapl_documentos.protocolo:
           documento = getattr(self.sapl_documentos.protocolo,nom_pdf_protocolo)
           documento.manage_upload(file=content)
        else:
           self.sapl_documentos.protocolo.manage_addFile(id=nom_pdf_protocolo,file=content,title='Protocolo')
        pdf = getattr(self.sapl_documentos.protocolo, nom_pdf_protocolo)
        pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def proposicao_autuar(self,cod_proposicao):
        nom_pdf_proposicao = str(cod_proposicao) + "_signed.pdf"
        arq = getattr(self.sapl_documentos.proposicao, nom_pdf_proposicao)
        fileStream = BytesIO(bytes(arq.data))
        reader = pypdf.PdfReader(fileStream)
        fields = reader.get_fields()
        signers = []
        nom_autor = None
        if fields != None:
            signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
            if signature_field_values is not None:
               signers = self.get_signatures(fileStream)
        qtde_assinaturas = len(signers)
        for signer in signers:
            nom_autor = signer['signer_name']
        outros = ''
        if qtde_assinaturas == 2:
           outros = " e outro"
        if qtde_assinaturas > 2:
           outros = " e outros"
        for proposicao in self.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao):
            num_proposicao = proposicao.cod_proposicao
            if nom_autor == None:
               nom_autor = proposicao.nom_autor
            info_protocolo = '- Recebido em ' + proposicao.dat_recebimento + '.'
            tipo_proposicao = proposicao.des_tipo_proposicao
            if proposicao.ind_mat_ou_doc == "M":
               for materia in self.zsql.materia_obter_zsql(cod_materia=proposicao.cod_mat_ou_doc):
                   if materia.num_protocolo != None and materia.num_protocolo != '':
                      for protocolo in self.zsql.protocolo_obter_zsql(num_protocolo=materia.num_protocolo, ano_protocolo=materia.ano_ident_basica):
                          info_protocolo = ' - Protocolo nº ' + str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo) + ', recebido em ' + str(DateTime(protocolo.dat_protocolo, datefmt='international').strftime('%d/%m/%Y')) + ' ' + protocolo.hor_protocolo + '.'
                   texto = str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                   storage_path = self.sapl_documentos.materia
                   nom_pdf_saida = str(materia.cod_materia) + "_texto_integral.pdf"
            elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao!='Emenda' and proposicao.des_tipo_proposicao!='Mensagem Aditiva' and proposicao.des_tipo_proposicao!='Substitutivo' and proposicao.des_tipo_proposicao!='Parecer' and proposicao.des_tipo_proposicao!='Parecer de Comissão'):
               for documento in self.zsql.documento_acessorio_obter_zsql(cod_documento=proposicao.cod_mat_ou_doc):
                   for materia in self.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                       materia = str(materia.sgl_tipo_materia)+' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
                   texto = str(documento.des_tipo_documento) + ' - ' + str(materia)
                   storage_path = self.sapl_documentos.materia
                   nom_pdf_saida = str(documento.cod_documento) + ".pdf"
            elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Emenda' or proposicao.des_tipo_proposicao=='Mensagem Aditiva'):
               for emenda in self.zsql.emenda_obter_zsql(cod_emenda=proposicao.cod_emenda):
                   for materia in self.zsql.materia_obter_zsql(cod_materia=emenda.cod_materia):
                       materia = str(materia.sgl_tipo_materia)+' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
                   info_protocolo = '- Recebida em ' + proposicao.dat_recebimento + '.'
                   texto = 'Emenda ' + str(emenda.des_tipo_emenda)+ ' nº ' + str(emenda.num_emenda) + ' ao ' + str(materia)
                   storage_path = self.sapl_documentos.emenda
                   nom_pdf_saida = str(emenda.cod_emenda) + "_emenda.pdf"
            elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Substitutivo'):
               for substitutivo in self.zsql.substitutivo_obter_zsql(cod_substitutivo=proposicao.cod_substitutivo):
                   for materia in self.zsql.materia_obter_zsql(cod_materia=substitutivo.cod_materia):
                       materia = str(materia.sgl_tipo_materia)+ ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                   texto = 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + ' ao ' + str(materia)
                   storage_path = self.sapl_documentos.substitutivo
                   nom_pdf_saida = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
            elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Parecer' or proposicao.des_tipo_proposicao=='Parecer de Comissão'):
               for relatoria in self.zsql.relatoria_obter_zsql(cod_relatoria=proposicao.cod_parecer, ind_excluido=0): 
                   for comissao in self.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao):
                       sgl_comissao = comissao.sgl_comissao
                   for materia in self.zsql.materia_obter_zsql(cod_materia=relatoria.cod_materia):
                       materia = str(materia.sgl_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                   texto = 'Parecer ' + sgl_comissao + ' nº ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + ' ao ' + str(materia)
                   storage_path = self.sapl_documentos.parecer_comissao
                   nom_pdf_saida = str(relatoria.cod_relatoria) + "_parecer.pdf"
        mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
        mensagem2 = 'Valide pelo qrcode ou acesse ' + self.url()+'/conferir_assinatura'+' com o código '+ cod_validacao_doc + '.'
        existing_pdf = pymupdf.open(stream=fileStream)
        numPages = existing_pdf.page_count
        for validacao in self.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao,tipo_doc='proposicao',ind_assinado=1):
            stream = self.make_qrcode(text=self.url()+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(validacao.cod_validacao_doc))
            for page_index, i in enumerate(range(len(existing_pdf))):
                w = existing_pdf[page_index].rect.width
                h = existing_pdf[page_index].rect.height
                margin = 5
                left = 10 - margin
                bottom = h - 60 - margin
                black = pymupdf.pdfcolor["black"]
                numero = "Pág. %s/%s" % (i+1, numPages)
                rect = pymupdf.Rect(left, bottom, left + 60, bottom + 60)  # qrcode bottom left square
                existing_pdf[page_index].insert_image(rect, stream=stream)
                text2 = texto + info_protocolo + '\n' + mensagem1 + '\n' + mensagem2
                p1 = pymupdf.Point(w - 60 - margin, h - 30) # numero de pagina documento
                p2 = pymupdf.Point(70, h - 35) # margem inferior
                shape = existing_pdf[page_index].new_shape()
                shape.draw_circle(p1,1)
                shape.draw_circle(p2,1)
                shape.insert_text(p1, numero, fontname = "helv", fontsize = 8)
                shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
                shape.commit()
            break
        w = existing_pdf[0].rect.width
        h = existing_pdf[0].rect.height
        rect = pymupdf.Rect(40, 140, w-20, 170)
        existing_pdf[0].insert_textbox(rect, str(texto).upper(), fontname = "tibo", fontsize = 13, align=pymupdf.TEXT_ALIGN_CENTER)
        metadata = {"title": texto, "author": nom_autor}
        existing_pdf.set_metadata(metadata)
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        if nom_pdf_saida in storage_path:
           pdf=storage_path[nom_pdf_saida]
           pdf.manage_upload(file=content)
        else:
           storage_path.manage_addFile(id=nom_pdf_saida,file=content,title=texto)
           pdf=storage_path[nom_pdf_saida]
        pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def peticao_autuar(self,cod_peticao):          
        for peticao in self.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
            cod_validacao_doc = ''
            nom_autor = None
            outros = ''
            for validacao in self.zsql.assinatura_documento_obter_zsql(tipo_doc='peticao', codigo=peticao.cod_peticao, ind_assinado=1):
                nom_pdf_peticao = str(validacao.cod_assinatura_doc) + ".pdf"
                pdf_peticao = self.sapl_documentos.documentos_assinados.absolute_url() + "/" +  nom_pdf_peticao
                cod_validacao_doc = str(self.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
                nom_pdf_peticao = str(validacao.cod_assinatura_doc) + ".pdf"
                pdf_peticao = self.sapl_documentos.documentos_assinados.absolute_url() + "/" +  nom_pdf_peticao
                arq = getattr(self.sapl_documentos.peticao, nom_pdf_peticao)
                fileStream = BytesIO(bytes(arq.data))
                reader = pypdf.PdfReader(fileStream)
                fields = reader.get_fields()
                signers = []
                nom_autor = None
                if fields != None:
                   signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
                   if signature_field_values is not None:
                      signers = self.get_signatures(fileStream)
                qtde_assinaturas = len(signers)
                for signer in signers:
                    nom_autor = signer['signer_name']
                outros = ''
                if qtde_assinaturas == 2:
                   outros = " e outro"
                if qtde_assinaturas > 2:
                   outros = " e outros"
                break
            else:
               nom_pdf_peticao = str(cod_peticao) + ".pdf"
               pdf_peticao = self.sapl_documentos.peticao.absolute_url() + "/" +  nom_pdf_peticao
               for usuario in self.zsql.usuario_obter_zsql(cod_usuario=peticao.cod_usuario):
                   nom_autor = usuario.nom_completo
            info_protocolo = '- Recebido em ' + peticao.dat_recebimento + '.'
            tipo_tipo_peticionamento = peticao.des_tipo_peticionamento
            if peticao.ind_doc_adm == "1":
               for documento in self.zsql.documento_administrativo_obter_zsql(cod_documento=peticao.cod_documento):
                   for protocolo in self.zsql.protocolo_obter_zsql(num_protocolo=documento.num_protocolo, ano_protocolo=documento.ano_documento):
                       info_protocolo = ' - Protocolo nº ' + str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo) + ' recebido em ' + str(DateTime(protocolo.dat_protocolo, datefmt='international').strftime('%d/%m/%Y')) + ' ' + protocolo.hor_protocolo + '.'
                   texto = str(documento.des_tipo_documento)+ ' nº ' + str(documento.num_documento)+ '/' +str(documento.ano_documento)
                   storage_path = self.sapl_documentos.administrativo
                   nom_pdf_saida = str(documento.cod_documento) + "_texto_integral.pdf"
                   caminho = '/sapl_documentos/administrativo/'
            elif peticao.ind_doc_materia == "1":
               for documento in self.zsql.documento_acessorio_obter_zsql(cod_documento=peticao.cod_doc_acessorio):
                   texto = str(documento.des_tipo_documento) + ' - ' + str(materia)
                   storage_path = self.sapl_documentos.materia
                   nom_pdf_saida = str(documento.cod_documento) + ".pdf"
                   caminho = '/sapl_documentos/materia/'
            elif peticao.ind_norma == "1":
               storage_path = self.sapl_documentos.norma_juridica
               for norma in self.zsql.norma_juridica_obter_zsql(cod_norma=peticao.cod_norma):
                   info_protocolo = '- Recebida em ' + peticao.dat_recebimento + '.'
                   texto = str(norma.des_tipo_norma) + ' nº ' + str(norma.num_norma) + '/' + str(norma.ano_norma)
                   nom_pdf_saida = str(norma.cod_norma) + "_texto_integral.pdf"
                   caminho = '/sapl_documentos/norma_juridica/'
        if cod_validacao_doc != '':
           arq = getattr(self.sapl_documentos.documentos_assinados, nom_pdf_peticao)
           stream = self.make_qrcode(text=self.url()+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(cod_validacao_doc))
           mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
           mensagem2 = 'Valide pelo qrcode ou acesse ' + self.url()+'/conferir_assinatura'+' com o código '+ cod_validacao_doc + '.'
        else:
           arq = getattr(self.sapl_documentos.peticao, nom_pdf_peticao)
           stream = self.make_qrcode(text=self.url() + str(caminho) + str(nom_pdf_saida))
           mensagem1 = 'Documento assinado com login e senha por ' + nom_autor
           mensagem2 = ''
        arquivo = BytesIO(bytes(arq.data))
        existing_pdf = pymupdf.open(stream=arquivo)
        numPages = existing_pdf.page_count
        for page_index, i in enumerate(range(len(existing_pdf))):
            w = existing_pdf[page_index].rect.width
            h = existing_pdf[page_index].rect.height
            margin = 5
            left = 10 - margin
            bottom = h - 60 - margin
            black = pymupdf.pdfcolor["black"]
            numero = "Pág. %s/%s" % (i+1, numPages)
            rect = pymupdf.Rect(left, bottom, left + 60, bottom + 60)  # qrcode bottom left square
            existing_pdf[page_index].insert_image(rect, stream=stream)
            text2 = texto + info_protocolo + '\n' + mensagem1 + '\n' + mensagem2
            p1 = pymupdf.Point(w - 60 - margin, h - 30) # numero de pagina documento
            p2 = pymupdf.Point(70, h - 35) # margem inferior
            shape = existing_pdf[page_index].new_shape()
            shape.draw_circle(p1,1)
            shape.draw_circle(p2,1)
            shape.insert_text(p1, numero, fontname = "helv", fontsize = 8)
            shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
            shape.commit()
        w = existing_pdf[0].rect.width
        h = existing_pdf[0].rect.height
        rect = pymupdf.Rect(40, 140, w-20, 170)
        existing_pdf[0].insert_textbox(rect, str(texto).upper(), fontname = "tibo", fontsize = 13, align=pymupdf.TEXT_ALIGN_CENTER)
        metadata = {"title": texto, "author": nom_autor}
        existing_pdf.set_metadata(metadata)
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        if nom_pdf_saida in storage_path:
           arq=storage_path[nom_pdf_saida]
           arq.manage_upload(file=content)
           arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        else:
           storage_path.manage_addFile(id=nom_pdf_saida,file=content,title=texto)
           arq=storage_path[nom_pdf_saida]
           arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        if peticao.ind_norma == "1":
           arq=storage_path[nom_pdf_saida]
           arq.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
           self.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(cod_norma=peticao.cod_norma)

    def restpki_client(self):
        restpki_url = 'https://restpkiol.azurewebsites.net/'
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
                   pdf_location = storage.pdf_location
                   pdf_signed = str(pdf_location) + str(codigo) + str(storage.pdf_signed)
                   nom_arquivo_assinado = str(codigo) + str(storage.pdf_signed)
                   pdf_file = str(pdf_location) + str(codigo) + str(storage.pdf_file)
                   nom_arquivo = str(codigo) + str(storage.pdf_file)
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
                   elif tipo_doc == 'anexo_peticao':
                      storage_path = self.sapl_documentos.peticao
                      pdf_file = str(pdf_location) + str(codigo) + '_anexo_' + str(anexo) + str(storage.pdf_file)
                      nom_arquivo = str(codigo) + '_anexo_' + str(anexo) + str(storage.pdf_file)
                   elif tipo_doc == 'anexo_sessao':
                      storage_path = self.sapl_documentos.anexo_sessao
                      pdf_file = str(pdf_location) + str(codigo) + '_anexo_' + str(anexo) + str(storage.pdf_file)
                      nom_arquivo = str(codigo) + '_anexo_' + str(anexo) + str(storage.pdf_file)
        try:
           arquivo = self.restrictedTraverse(pdf_signed)
           pdf_tosign = nom_arquivo_assinado
        except:
           arquivo = self.restrictedTraverse(pdf_file)
           pdf_tosign = nom_arquivo
        x = crc32(bytes(arquivo))
        if (x>=0):
           crc_arquivo= str(x)
        else:
           crc_arquivo= str(-1 * x)
        return pdf_tosign, storage_path, crc_arquivo

    def pades_signature(self, codigo, anexo, tipo_doc, cod_usuario, qtde_assinaturas):
        # get file to sign
        pdf_tosign, storage_path, crc_arquivo = self.get_file_tosign(codigo, anexo, tipo_doc)
        arq = getattr(storage_path, pdf_tosign)
        with BytesIO(bytes(arq.data)) as arq1:
             pdf_stream = base64.b64encode(arq1.getvalue()).decode('utf8')
        pdf_path = ''
        # Read the PDF stamp image
        id_logo = self.sapl_documentos.props_sagl.id_logo
        if hasattr(self.sapl_documentos.props_sagl, id_logo):
           arq = getattr(self.sapl_documentos.props_sagl, id_logo)
           with BytesIO(bytes(arq.data)) as arq1:
                image = base64.b64encode(arq1.getvalue()).decode('utf8')
        else:
           install_home = os.environ.get('INSTALL_HOME')
           dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/brasao.gif')
           with open(dirpath, "rb") as arq1:
                image = base64.b64encode(arq1.read()).decode('utf8')
        pdf_stamp = image
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
                       'content': pdf_stamp,
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
                       'content': pdf_stamp,
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
           self.margem_inferior(codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename)
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

    def get_signatures(self, fileStream):
        reader = pypdf.PdfReader(fileStream)
        fields = reader.get_fields().values()
        signature_field_values = [
            f.value for f in fields if f.field_type == '/Sig']  
        lst_signers = []
        for v in signature_field_values:
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
        lst_signers.sort(key=lambda dic: dic['signing_time'])
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

    def margem_inferior(self, codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename):
        arq = getattr(self.sapl_documentos.documentos_assinados, filename)
        fileStream = BytesIO(bytes(arq.data))
        reader = pypdf.PdfReader(fileStream)
        fields = reader.get_fields()
        signers = []
        nom_autor = None
        if fields != None:
            signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
            if signature_field_values is not None:
               signers = self.get_signatures(fileStream)
        qtde_assinaturas = len(signers)
        for signer in signers:
            nom_autor = signer['signer_name']
        outros = ''
        if qtde_assinaturas == 2:
           outros = " e outro"
        if qtde_assinaturas > 2:
           outros = " e outros"
        if nom_autor == None:
            for usuario in self.zsql.usuario_obter_zsql(cod_usuario=cod_usuario):
                nom_autor = usuario.nom_completo
                break
        string = str(self.cadastros.assinatura.format_verification_code(cod_assinatura_doc))
        # Variáveis para obtenção de dados e local de armazenamento por tipo de documento
        for storage in self.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
            if tipo_doc == 'anexo_sessao':
               nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
               nom_pdf_documento = str(codigo) + '_anexo_' + str(anexo) + '.pdf'
            elif tipo_doc == 'anexo_peticao':
               nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
               nom_pdf_documento = str(codigo) + '_anexo_' + str(anexo) + '.pdf'
            else:
               nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
               nom_pdf_documento = str(codigo) + str(storage.pdf_file)
        if tipo_doc == 'materia' or tipo_doc == 'doc_acessorio' or tipo_doc == 'redacao_final':
           storage_path = self.sapl_documentos.materia
           if tipo_doc == 'materia' or tipo_doc == 'redacao_final':
              for metodo in self.zsql.materia_obter_zsql(cod_materia=codigo):
                  num_documento = metodo.num_ident_basica
                  if tipo_doc == 'materia':
                     texto = str(metodo.des_tipo_materia)+' nº '+ str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica)
                  elif tipo_doc == 'redacao_final':
                     texto = 'Redação Final do ' + str(metodo.sgl_tipo_materia)+' nº '+ str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica)
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
               texto = 'Emenda ' + str(metodo.des_tipo_emenda) + ' nº ' + str(metodo.num_emenda) + ' ao ' + str(materia)
        elif tipo_doc == 'substitutivo':
           storage_path = self.sapl_documentos.substitutivo
           for metodo in self.zsql.substitutivo_obter_zsql(cod_substitutivo=codigo):
               for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
               texto = 'Substitutivo nº ' + str(metodo.num_substitutivo) + ' ao ' + str(materia)
        elif tipo_doc == 'tramitacao':
           storage_path = self.sapl_documentos.materia.tramitacao
           for metodo in self.zsql.tramitacao_obter_zsql(cod_tramitacao=codigo):
               materia = str(metodo.sgl_tipo_materia)+' '+ str(metodo.num_ident_basica)+'/'+str(metodo.ano_ident_basica)
           texto = 'Tramitação nº '+ str(metodo.cod_tramitacao) + ' - ' + str(materia)
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
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(self.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + str(tipo.nom_sessao) + ' - ' + str(metodo.dat_inicio_sessao)
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
           texto = 'Pauta da ' + str(sessao)
        elif tipo_doc == 'ata':
           storage_path = self.sapl_documentos.ata_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(self.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + str(tipo.nom_sessao) + ' - ' + str(metodo.dat_inicio_sessao)
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
           texto = 'Ata da ' + str(sessao)
        elif tipo_doc == 'anexo_peticao':
           storage_path = self.sapl_documentos.peticao
           file_item =  str(codigo) + '_anexo_' + str(anexo) + '.pdf'
           title = getattr(self.sapl_documentos.peticao,file_item).title_or_id()
           texto = 'Anexo de petição: ' + str(title)
        elif tipo_doc == 'anexo_sessao':
           storage_path = self.sapl_documentos.anexo_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(self.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ', de ' + str(metodo.dat_inicio_sessao)
           file_item =  str(codigo) + '_anexo_' + str(anexo) + '.pdf'
           title = getattr(self.sapl_documentos.anexo_sessao,file_item).title_or_id()
           texto = str(title) + ' da ' + str(sessao)
        elif tipo_doc == 'norma':
           storage_path = self.sapl_documentos.norma_juridica
           for metodo in self.zsql.norma_juridica_obter_zsql(cod_norma=codigo):
               texto = str(metodo.des_tipo_norma) + ' nº ' + str(metodo.num_norma) + '/' + str(metodo.ano_norma)
        elif tipo_doc == 'documento' or tipo_doc == 'doc_acessorio_adm':
           storage_path = self.sapl_documentos.administrativo
           if tipo_doc == 'documento':
              for metodo in self.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
                  num_documento = metodo.num_documento
              texto = str(metodo.des_tipo_documento)+ ' nº ' + str(metodo.num_documento)+ '/' +str(metodo.ano_documento)
           elif tipo_doc == 'doc_acessorio_adm':
              for metodo in self.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
                  for documento in self.zsql.documento_administrativo_obter_zsql(cod_documento=metodo.cod_documento):
                      documento = str(documento.sgl_tipo_documento) +' '+ str(documento.num_documento)+'/'+str(documento.ano_documento)
              texto = 'Doumento Acessório do ' + str(documento)
        elif tipo_doc == 'tramitacao_adm':
           storage_path = self.sapl_documentos.administrativo.tramitacao
           for metodo in self.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=codigo):
               documento = str(metodo.sgl_tipo_documento)+' '+ str(metodo.num_documento)+'/'+str(metodo.ano_documento)
           texto = 'Tramitação nº '+ str(metodo.cod_tramitacao) + ' - ' + str(documento)
        elif tipo_doc == 'proposicao':
           storage_path = self.sapl_documentos.proposicao
           for metodo in self.zsql.proposicao_obter_zsql(cod_proposicao=codigo):
               texto = str(metodo.des_tipo_proposicao) +' nº ' + str(metodo.cod_proposicao)
        elif tipo_doc == 'protocolo':
           storage_path = self.sapl_documentos.protocolo
           for metodo in self.zsql.protocolo_obter_zsql(cod_protocolo=codigo):
               texto = 'Protocolo nº '+ str(metodo.num_protocolo) +'/' + str(metodo.ano_protocolo)
        elif tipo_doc == 'peticao':
           storage_path = self.sapl_documentos.peticao
           texto = 'Petição Eletrônica'
        elif tipo_doc == 'pauta_comissao':
           storage_path = self.sapl_documentos.reuniao_comissao
           for metodo in self.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = 'Pauta da ' + str(metodo.num_reuniao) + 'ª Reunião da ' + comissao.sgl_comissao + ', em ' + str(metodo.dat_inicio_reuniao)
        elif tipo_doc == 'ata_comissao':
           storage_path = self.sapl_documentos.reuniao_comissao
           for metodo in self.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = 'Ata da ' + str(metodo.num_reuniao) + 'ª Reunião da ' + comissao.sgl_comissao + ', em ' + str(metodo.dat_inicio_reuniao)
        elif tipo_doc == 'documento_comissao':
           storage_path = self.sapl_documentos.documento_comissao
           for metodo in self.zsql.documento_comissao_obter_zsql(cod_documento=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = metodo.txt_descricao + ' da ' + comissao.sgl_comissao
        mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros + '.'
        mensagem2 = 'Valide pelo qrcode ou acesse ' + self.url() + '/conferir_assinatura' + ' com o código ' + string
        existing_pdf = pymupdf.open(stream=fileStream)
        numPages = existing_pdf.page_count
        stream = self.make_qrcode(text=self.url()+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(string))
        for page_index, i in enumerate(range(len(existing_pdf))):
            w = existing_pdf[page_index].rect.width
            h = existing_pdf[page_index].rect.height
            margin = 5
            left = 10 - margin
            bottom = h - 60 - margin
            black = pymupdf.pdfcolor["black"]
            numero = "Pág. %s/%s" % (i+1, numPages)
            rect = pymupdf.Rect(left, bottom, left + 60, bottom + 60)  # qrcode bottom left square
            existing_pdf[page_index].insert_image(rect, stream=stream)
            text2 = texto + '\n' + mensagem1 + '\n' + mensagem2
            p1 = pymupdf.Point(w -60 -margin, h - 30) # numero de pagina documento
            p2 = pymupdf.Point(70, h - 35) # margem inferior
            shape = existing_pdf[page_index].new_shape()
            shape.draw_circle(p1,1)
            shape.draw_circle(p2,1)
            shape.insert_text(p1, numero, fontname = "helv", fontsize = 8)
            shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
            shape.commit()
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        if hasattr(storage_path, nom_pdf_documento):
           pdf = getattr(storage_path, nom_pdf_documento)
           pdf.manage_upload(file=content)
        else:
           storage_path.manage_addFile(id=nom_pdf_documento,file=content,title=texto)
           pdf = getattr(storage_path, nom_pdf_documento)
        if tipo_doc == 'parecer_comissao':
           for relat in self.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
               for tipo in zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria = relat.tip_fim_relatoria):
                   if tipo.des_fim_relatoria=='Aguardando apreciação':
                      pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
                   else:
                      pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
               else:
                   pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
        elif tipo_doc == 'doc_acessorio':
           for documento in self.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
               if str(documento.ind_publico) == '1':
                  pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
               elif str(documento.ind_publico) == '0':
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        elif tipo_doc == 'documento':
           for documento in self.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
               if str(documento.ind_publico) == '1':
                  pdf.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
               elif str(documento.ind_publico) == '0':
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        elif tipo_doc == 'doc_acessorio_adm':
           for doc in self.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
               if str(doc.ind_publico) == '1':
                  pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
               if str(doc.ind_publico) == '0':
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        elif tipo_doc == 'peticao' or tipo_doc == 'anexo_peticao':
           pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        else:
           pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)

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
           mensagem2 = 'Para verificação da autenticidade leia o qrcode ao lado.'
           arq = getattr(storage_path, pdf_proposicao)
           arquivo = BytesIO(bytes(arq.data))
           existing_pdf = pymupdf.open(stream=arquivo)
           numPages = existing_pdf.page_count
           stream = self.make_qrcode(text=self.url() + '/sapl_documentos/proposicao/' + proposicao.cod_proposicao + '_signed.pdf')
           for page_index, i in enumerate(range(len(existing_pdf))):
               w = existing_pdf[page_index].rect.width
               h = existing_pdf[page_index].rect.height
               margin = 5
               left = 10 - margin
               bottom = h - 60 - margin
               black = pymupdf.pdfcolor["black"]
               numero = "Pág. %s/%s" % (i+1, numPages)
               rect = pymupdf.Rect(left, bottom, left + 60, bottom + 60)  # qrcode bottom left square
               existing_pdf[page_index].insert_image(rect, stream=stream)
               text2 = texto + '\n' + mensagem1 + '\n' + mensagem2
               p1 = pymupdf.Point(w -60 -margin, h - 30) # numero de pagina documento
               p2 = pymupdf.Point(70, h - 35) # margem inferior
               shape = existing_pdf[page_index].new_shape()
               shape.draw_circle(p1,1)
               shape.draw_circle(p2,1)
               shape.insert_text(p1, numero, fontname = "helv", fontsize = 8)
               shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
               shape.commit()
           content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
           if hasattr(storage_path,pdf_assinado):
              pdf = getattr(storage_path, pdf_assinado)
              pdf.manage_upload(file=content)
           else:
              storage_path.manage_addFile(id=pdf_assinado,file=content, title='Proposição '+ str(item))
              pdf = getattr(storage_path, pdf_assinado)
           pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
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
        id_sessao = ''
        data = ''
        nom_presidente = ''
        # obtem dados da sessao
        if cod_sessao_plen != '0' and cod_sessao_plen != '':
           for item in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao):
                   id_sessao = str(item.num_sessao_plen) + 'ª ' + str(self.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + tipo.nom_sessao
               data = item.dat_inicio_sessao
               data1 = item.dat_inicio
               num_legislatura = item.num_legislatura
           for composicao in self.zsql.composicao_mesa_sessao_obter_zsql(cod_sessao_plen=cod_sessao_plen, cod_cargo=1, ind_excluido=0):
               for parlamentar in self.zsql.parlamentar_obter_zsql(cod_parlamentar=composicao.cod_parlamentar):
                   nom_presidente = str(parlamentar.nom_parlamentar.upper())
           if nom_presidente == '':
              for sleg in self.zsql.periodo_comp_mesa_obter_zsql(data=data1):
                  for cod_presidente in self.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp, cod_cargo=1):
                      for presidencia in self.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_presidente.cod_parlamentar):
                          nom_presidente = str(presidencia.nom_parlamentar.upper())
        # dados carimbo
        texto = "%s" % (str(nom_resultado.upper()))
        sessao = "%s - %s" % (id_sessao, data)
        cargo = "Presidente"
        presidente = "%s: %s " % (cargo, nom_presidente)
        # adiciona carimbo aos documentos
        for materia in self.zsql.materia_obter_zsql(cod_materia=cod_materia):
            storage_path = self.sapl_documentos.materia
            nom_pdf_saida = str(materia.cod_materia) + "_texto_integral.pdf"
        if hasattr(storage_path, nom_pdf_saida):
           arq = getattr(storage_path, nom_pdf_saida)
           arquivo = BytesIO(bytes(arq.data))
           existing_pdf = pymupdf.open(stream=arquivo)
           numPages = existing_pdf.page_count
           stream = self.create_barcode(value=string)
           w = existing_pdf[0].rect.width
           h = existing_pdf[0].rect.height
           margin = 10
           top = margin + 50
           right = w - 40 -margin
           black = pymupdf.pdfcolor["black"]
           text2 = texto + '\n' + sessao + '\n' + presidente
           p2 = pymupdf.Point(w - 10 - margin, margin + 95) # margem superior
           shape = existing_pdf[0].new_shape()
           shape.draw_circle(p2,1)
           shape.insert_text(p2, text2, fontname = "helv", fontsize = 7, rotate=0)
           shape.commit()
           content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
           arq.manage_upload(file=content)

    def _getValidEmailAddress(self, member):
        email = None
        for usuario in self.zsql.usuario_obter_zsql(col_username=member):
            email = usuario.end_email
        return email
        
    security.declarePublic('mailPassword')

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
            fields = list(autores.data_dictionary().keys())
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

    def index_file(self, url):
        text = ''
        file = self.unrestrictedTraverse(url)
        with BytesIO(bytes(file.data)) as arq:
           with pymupdf.open(stream=arq) as reader:
              indexed = []
              for page in reader:
                  text = page.get_text("words")
                  for words in text:
                      word = words[4]
                      if len(str(word)) > 2:
                         indexed.append(word)
              indexed = [
                 e
                 for i, e in enumerate(indexed)
                 if indexed.index(e) == i
              ]
              return indexed

InitializeClass(SAGLTool)
