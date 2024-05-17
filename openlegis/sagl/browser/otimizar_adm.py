# -*- coding: utf-8 -*-
import sys, os, string
import shutil
import subprocess
from subprocess import Popen, PIPE
from io import BytesIO
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import requests
import MySQLdb
from PyPDF4 import PdfFileReader, PdfFileWriter

class otimizarADM(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('otimizar_adm')

    def optimizeADMFiles(self, action):
        dirtemp = os.path.join('/tmp/')
        path = self.context.sapl_documentos.administrativo
        
        if action == 'upload':
           for file in os.listdir(dirtemp):
               if file.endswith('.pdf'):
                  if hasattr(path, file):
                     filepath = os.path.join(dirtemp, file)
                     arq2 = open(filepath, 'rb')
                     arquivo2 = BytesIO(str(arq2.read()))
                     documento = getattr(path,file)
                     documento.manage_upload(file=arq2)
                     documento.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
                     os.unlink(os.path.join(dirtemp) + '/' + file)
                  else:
                    filepath = os.path.join(dirtemp, file)
                    arq2 = open(filepath, 'rb')
                    path.manage_addFile(id=file,file=arq2)
                    arq = getattr(path,file)
                    arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
                    os.unlink(os.path.join(dirtemp) + '/' + file)
        
        if action == 'download':
           db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="cmuberlandia_openlegis")
           cur = db.cursor()
           lst_documentos = []
           cur.execute('SELECT cod_documento from documento_administrativo WHERE ind_excluido = 0 ORDER BY cod_documento;')
           for row in cur.fetchall():
               row_id = str(row[0])
               lst_documentos.append(row_id)
           db.close()

           db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="cmuberlandia_openlegis")
           cur = db.cursor()
           lst_acessorios = []
           cur.execute('SELECT cod_documento_acessorio from documento_acessorio_administrativo WHERE ind_excluido = 0 ORDER BY cod_documento_acessorio;')
           for row in cur.fetchall():
               row_id = str(row[0])
               lst_acessorios.append(row_id)
           db.close()

           lst_arquivos = []
           for item in lst_documentos:
              for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=item, ind_excluido=0):
                  dic = {}
                  dic['file'] = str(documento.cod_documento) + '_texto_integral.pdf'
                  dic['title'] = documento.des_tipo_documento + ' nº ' + str(documento.num_documento) + '/' +str(documento.ano_documento)
                  if self.context.zsql.assinatura_documento_obter_zsql(codigo=documento.cod_documento, tipo_doc='documento',ind_assinado=1):
                     dic['assinado'] ='1'
                  else:
                     dic['assinado'] = '0'
                  if hasattr(path, dic['file']):
                     lst_arquivos.append(dic)
           for item in lst_acessorios:
              for acessorio in self.context.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=item, ind_excluido=0):
                  dic = {}
                  dic['file'] = nom_arquivo = str(acessorio.cod_documento_acessorio) + '.pdf'
                  dic['title'] = acessorio.nom_documento
                  if self.context.zsql.assinatura_documento_obter_zsql(codigo=acessorio.cod_documento_acessorio, tipo_doc='doc_acessorio_adm',ind_assinado=1):
                     dic['assinado'] ='1'
                  else:
                     dic['assinado'] = '0'
                  if hasattr(path, dic['file']):
                     lst_arquivos.append(dic)
           
           for item in lst_arquivos:
               nom_arquivo = item['file']
               nom_saida = 'temp_' + nom_arquivo
               arq = getattr(path, nom_arquivo)        
               arquivo = BytesIO(str(arq.data))
               arquivo.seek(0)
               f = open(os.path.join(dirtemp) + '/' + nom_arquivo, 'wb').write(arquivo.getvalue())
               subprocess.call('gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/prepress -dNOPAUSE -dQUIET -dBATCH -sOutputFile=' + os.path.join(dirtemp) + '/' + nom_saida + ' ' + os.path.join(dirtemp) + '/' + nom_arquivo, shell=True)
               filepath = os.path.join(dirtemp, nom_saida)
               arq2 = open(filepath, 'rb')
               arquivo2 = BytesIO(str(arq2.read()))
               reader = PdfFileReader(arquivo2)
               writer = PdfFileWriter()
               for page in reader.pages:
                   writer.addPage(page)
               writer.addMetadata({"/Title": item["title"]})
               arquivo3 = BytesIO()
               writer.write(arquivo3)
               arquivo3.seek(0)
               f = open(os.path.join(dirtemp) + '/' + nom_saida, 'wb').write(arquivo3.getvalue())
               shutil.move(dirtemp + '/' + nom_saida, dirtemp + '/' + nom_arquivo)
               path.manage_delObjects(nom_arquivo)

    def render(self, action):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        self.optimizeADMFiles(action=action)
        return "Arquivos corrigidos"

class otimizarTramADM(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('otimizar_tram_adm')
 
    def optimizeTramADMFiles(self, action):
        dirtemp = os.path.join('/tmp/')
        path = self.context.sapl_documentos.administrativo.tramitacao
        
        if action == 'upload':
           for file in os.listdir(dirtemp):
               if file.endswith('_tram.pdf'):
                  if hasattr(path, file):
                     filepath = os.path.join(dirtemp, file)
                     arq2 = open(filepath, 'rb')
                     arq = getattr(path,file)
                     arq.manage_upload(file=arq2)
                     arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
                     os.unlink(os.path.join(dirtemp) + '/' + file)
                  else:
                    filepath = os.path.join(dirtemp, file)
                    arq2 = open(filepath, 'rb')
                    path.manage_addFile(id=file,file=arq2)
                    arq = getattr(path,file)
                    arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)
                    os.unlink(os.path.join(dirtemp) + '/' + file)
                     
        if action == 'download':
           db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="cmuberlandia_openlegis")
           cur = db.cursor()
           lst_tramitacoes = []
           cur.execute('SELECT cod_tramitacao from tramitacao_administrativo WHERE ind_excluido = 0 ORDER BY cod_tramitacao;')
           for row in cur.fetchall():
               row_id = str(row[0])
               lst_tramitacoes.append(row_id)
           db.close()

           lst_arquivos = []
           for item in lst_tramitacoes:
              for tramitacao in self.context.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=item, ind_excluido=0):
                  dic = {}
                  dic['file'] = str(tramitacao.cod_tramitacao) + '_tram.pdf'
                  dic['title'] = 'Tramitação (' + tramitacao.des_status + ')'
                  if hasattr(path, dic['file']):
                     lst_arquivos.append(dic)

           for item in lst_arquivos:
               nom_arquivo = item['file']
               nom_saida = 'temp_' + nom_arquivo
               arq = getattr(path, nom_arquivo)        
               arquivo = BytesIO(str(arq.data))
               arquivo.seek(0)
               f = open(os.path.join(dirtemp) + '/' + nom_arquivo, 'wb').write(arquivo.getvalue())
               subprocess.call('gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/prepress -dNOPAUSE -dQUIET -dBATCH -sOutputFile=' + os.path.join(dirtemp) + '/' + nom_saida + ' ' + os.path.join(dirtemp) + '/' + nom_arquivo, shell=True)
               filepath = os.path.join(dirtemp, nom_saida)
               arq2 = open(filepath, 'rb')
               arquivo2 = BytesIO(str(arq2.read()))
               reader = PdfFileReader(arquivo2)
               writer = PdfFileWriter()
               for page in reader.pages:
                   writer.addPage(page)
               writer.addMetadata({"/Title": item["title"]})
               arquivo3 = BytesIO()
               writer.write(arquivo3)
               arquivo3.seek(0)
               f = open(os.path.join(dirtemp) + '/' + nom_saida, 'wb').write(arquivo3.getvalue())
               shutil.move(dirtemp + '/' + nom_saida, dirtemp + '/' + nom_arquivo)
               path.manage_delObjects(nom_arquivo)

    def render(self, action):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        self.optimizeTramADMFiles(action=action)
        return "Arquivos corrigidos"
