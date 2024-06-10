# -*- coding: utf-8 -*-
import sys, os, string
import shutil
import subprocess
from subprocess import Popen, PIPE
from io import BytesIO
from DateTime import DateTime
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import requests
from PyPDF4 import PdfFileReader, PdfFileWriter
import uuid

class ProcessoAdm(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral')

    def create_folder(self, cod_documento):
        directory = os.path.join('/var/openlegis/SAGL4/var/tmp/', 'processo_adm_integral_' + str(cod_documento))
        dirpath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory)
        pagepath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory, 'pages')
        dirtemp = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory, 'temp')
           
        if not os.path.exists(dirpath):
           os.makedirs(dirpath)
           os.makedirs(pagepath)
           os.makedirs(dirtemp)

        return 'OK'

    def download_files(self, cod_documento):
        directory = os.path.join('/var/openlegis/SAGL4/var/tmp/', 'processo_adm_integral_' + str(cod_documento))
        dirpath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory)
        dirtemp = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory, 'temp')
        
        lst_arquivos = []
               
        for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
            id_capa = str(uuid.uuid4().hex)
            id_arquivo = "%s.pdf" % str(id_capa)
            self.context.modelo_proposicao.capa_processo_adm(cod_documento=cod_documento, nom_arquivo=str(id_capa))
            if hasattr(self.context.temp_folder, id_arquivo):
               dic = {}
               dic["data"] = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d 00:00:01')
               dic['path'] = self.context.temp_folder
               dic['file'] = id_arquivo
               dic['title'] = 'Capa do Processo'
               lst_arquivos.append(dic)

            nom_arquivo = str(cod_documento) + '_texto_integral.pdf'
            if hasattr(self.context.sapl_documentos.administrativo, nom_arquivo):
               dic = {}
               dic["data"] = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d 00:00:02')
               dic['path'] = self.context.sapl_documentos.administrativo
               dic['file'] = nom_arquivo
               dic['title'] = documento.des_tipo_documento + ' ' + str(documento.num_documento) + '/' +str(documento.ano_documento)
               lst_arquivos.append(dic)

            for docadm in self.context.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento=documento.cod_documento, ind_excluido=0):
                if hasattr(self.context.sapl_documentos.administrativo, str(docadm.cod_documento_acessorio) + '.pdf'):
                   dic = {}
                   dic["data"] = DateTime(docadm.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   dic['path'] = self.context.sapl_documentos.administrativo
                   dic['file'] = str(docadm.cod_documento_acessorio) + '.pdf'
                   dic['title'] = docadm.nom_documento
                   lst_arquivos.append(dic)

            for tram in self.context.zsql.tramitacao_administrativo_obter_zsql(cod_documento=documento.cod_documento, rd_ordem='1', ind_excluido=0):
                if hasattr(self.context.sapl_documentos.administrativo.tramitacao, str(tram.cod_tramitacao) + '_tram.pdf'):
                   dic = {}
                   dic["data"] = DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                   dic['path'] = self.context.sapl_documentos.administrativo.tramitacao
                   dic['file'] = str(tram.cod_tramitacao) + '_tram.pdf'
                   dic['title'] = 'Tramitação (' + tram.des_status + ')'
                   lst_arquivos.append(dic)

        lst_arquivos.sort(key=lambda dic: dic['data'])

        lst_arquivos = [(i + 1, j) for i, j in enumerate(lst_arquivos)]

        arquivos_baixados = []
        for i, dic in lst_arquivos:
            downloaded_pdf = str(i).rjust(4, '0') + '.pdf'
            arq = getattr(dic['path'], dic['file'])          
            arquivo = BytesIO(str(arq.data))
            arquivo.seek(0)
            reader = PdfFileReader(arquivo)
            writer = PdfFileWriter()
            for page in reader.pages:
                writer.addPage(page)
            writer.addMetadata({"/Title": dic["title"]})
            arquivo2 = BytesIO()
            writer.write(arquivo2)
            arquivo2.seek(0)
            f = open(os.path.join(dirtemp) + '/' + downloaded_pdf, 'wb').write(arquivo2.getvalue())
            if dic['title'] == 'Capa do Processo':
               self.context.temp_folder.manage_delObjects(ids=dic['file'])
            arquivos_baixados.append(downloaded_pdf)

        file_paths = []
        for file in os.listdir(dirpath):
            if file.startswith("0"):
               file_paths.append(file)
        file_paths.sort()

        downloaded = []
        for file in os.listdir(dirtemp):
            downloaded.append(file)
        downloaded.sort()

        mudou = False
        for file in downloaded:
            arquivo = os.path.join(dirtemp, file)
            arq1 = open(arquivo, 'rb')
            arquivo1 = BytesIO(str(arq1.read()))
            arquivo1.seek(0,2)
            temp_size = arquivo1.tell()
            if file in file_paths:
               filepath = os.path.join(dirpath, file)
               f1 = open(filepath, 'rb')
               f1 = BytesIO(str(f1.read()))
               f1.seek(0,2)
               file_size = f1.tell()
               if str(temp_size) != str(file_size):
                  shutil.move(dirtemp + '/' + file, dirpath + '/' + file)
                  mudou = True
            elif file not in file_paths:
                  shutil.move(dirtemp + '/' + file, dirpath + '/' + file)
                  mudou = True

        for file in os.listdir(dirtemp):
            os.unlink(os.path.join(dirtemp, file))

        for file in file_paths:
           if file not in arquivos_baixados:
              subprocess.call('rm ' + os.path.join(dirpath) + '/' + file, shell=True)
              mudou = True
              
        if mudou == True:
           self.merge_files(cod_documento=cod_documento)

    def merge_files(self, cod_documento):
        directory = os.path.join('/var/openlegis/SAGL4/var/tmp/', 'processo_adm_integral_' + str(cod_documento))
        dirpath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory)

        for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
            processo_integral = documento.sgl_tipo_documento+'-'+str(documento.num_documento)+'-'+str(documento.ano_documento)+'.pdf'
            arquivo_saida = documento.sgl_tipo_documento+'-'+str(documento.num_documento)+'-'+str(documento.ano_documento)+'-integral.pdf'
            arquivo_saida_temp = 'temp_' + documento.sgl_tipo_documento+'-'+str(documento.num_documento)+'-'+str(documento.ano_documento)+'-integral.pdf'
            temp_file = 'temp_' + processo_integral

        if os.path.exists(os.path.join(dirpath, processo_integral)):
           filepath = os.path.join(dirpath, processo_integral)
           f1 = open(filepath, 'rb')
           f1 = BytesIO(str(f1.read()))
           f1.seek(0,2)
           file_size = f1.tell()

        file_paths = []
        for file in os.listdir(dirpath):
            if file.startswith("0"):
               filepath = os.path.join(dirpath, file)
               file_paths.append(filepath)
        file_paths.sort()
        files = ' '.join(['%s' % (value) for (value) in file_paths])

        output =  os.path.join(dirpath) + '/' + arquivo_saida_temp

        merged_pdf =  os.path.join(dirpath) + '/' + temp_file
        subprocess.call('pdftk ' + files + ' output ' + os.path.join(dirpath) + '/' + temp_file, shell=True)
        subprocess.call('bash /var/openlegis/SAGL4/numerar.sh ' + merged_pdf, shell=True)
        subprocess.call('mv ' + output + ' ' + merged_pdf, shell=True)
        
        merged = os.path.join(dirpath, temp_file)
        m1 = open(merged, 'rb')
        m1 = BytesIO(str(m1.read()))
        m1.seek(0,2)
        merged_size = m1.tell()

        if os.path.exists(os.path.join(dirpath, processo_integral)):
           if str(file_size) != str(merged_size):
              shutil.move(dirpath + '/' + temp_file, dirpath + '/' + processo_integral)
              self.split_pages(cod_documento=cod_documento)
           else:
              os.unlink(os.path.join(dirpath, temp_file))
        else:
           subprocess.call('bash /var/openlegis/SAGL4/numerar.sh ' + merged_pdf, shell=True)
           subprocess.call('mv ' + output + ' ' + merged_pdf, shell=True)
           shutil.move(dirpath + '/' + temp_file, dirpath + '/' + processo_integral)
           self.split_pages(cod_documento=cod_documento)
        return 'OK'

    def split_pages(self, cod_documento):
        directory = os.path.join('/var/openlegis/SAGL4/var/tmp/', 'processo_adm_integral_' + str(cod_documento))
        dirpath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory)
        pagepath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory, 'pages')
        
        for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
            processo_integral = documento.sgl_tipo_documento+'-'+str(documento.num_documento)+'-'+str(documento.ano_documento)+'.pdf'
        merged_pdf = os.path.join(dirpath) + '/' + processo_integral

        subprocess.call('rm ' + os.path.join(dirpath, 'pages') + '/*', shell=True)          
        subprocess.call('pdftk ' + merged_pdf + ' burst output ' + os.path.join(dirpath, 'pages') + '/', shell=True)          

        return 'OK'

    def render(self, cod_documento, action):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()    

        self.create_folder(cod_documento=cod_documento)
        self.download_files(cod_documento=cod_documento)

        if action == 'download':
           for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
               arquivo_final = str(documento.sgl_tipo_documento)+'-'+str(documento.num_documento)+'-'+str(documento.ano_documento)+'.pdf'
           download = open('/var/openlegis/SAGL4/var/tmp/processo_adm_integral_' + str(cod_documento) + '/' + arquivo_final, 'rb')
           arquivo = download.read()
           self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
           self.context.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %str(arquivo_final))
           return arquivo
        
        elif action == 'pasta' or action == '' or action == None:
           directory = os.path.join('/var/openlegis/SAGL4/var/tmp/', 'processo_adm_integral_' + str(cod_documento))
           dirpath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory)
           pagepath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory, 'pages')

           page_paths = []
           for file in os.listdir(pagepath):
               if file.startswith("pg_"):
                  page_paths.append(file)

           file_paths = []           
           for file in os.listdir(dirpath):
               dic = {}
               dic_indice = {}
               if file.startswith("0") and file.endswith(".pdf"):
                  filepath = os.path.join(dirpath, file)
                  arq = PdfFileReader(open(filepath, 'rb'), strict=False)
                  dic['id'] = file
                  dic['title'] = arq.getDocumentInfo().title
                  lst_pages = []
                  lst_geral = []
                  num_pages = arq.getNumPages()
                  for page in range(num_pages):
                      lst_pages.append(page+1)
                  dic['pages'] = lst_pages
                  file_paths.append(dic)

           file_paths.sort(key=lambda dic: dic['id'])
           files = ' '.join(['%s' % (value) for (value) in file_paths])

           indice = []
           for item in file_paths:
               dic = {}
               dic['id'] = item['id']
               dic['title'] = item['title']
               for pagina in item['pages']:
                   indice.append(dic) 

           indice1 = [(i + 1, j) for i, j in enumerate(indice)]

           lst_indice = []
           for i, arquivo in indice1:
               dic = {}
               dic['id'] = arquivo['id']
               dic['titulo'] = arquivo['title']
               dic['num_pagina'] = str(i)
               dic['pagina'] = 'pg_' + str(i).rjust(4, '0') + '.pdf'
               lst_indice.append(dic)

           pasta = []
           
           for item in file_paths:
               dic_indice= {}
               dic_indice['id'] = item['id']
               dic_indice['title'] = item['title']
               dic_indice["url"] = str(portal_url) + '/@@pagina_processo_adm_integral?cod_documento=' + str(cod_documento) + '%26pagina=' +  'pg_0001.pdf'
               dic_indice["paginas_geral"] = len(page_paths)
               dic_indice['paginas'] = []
               dic_indice['id_paginas'] = []
               for pag in lst_indice:
                   dic_pagina = {}
                   if item['id'] == str(pag.get('id',pag)):
                      dic_pagina['num_pagina'] = pag['num_pagina']
                      dic_pagina['id_pagina'] = pag['pagina']
                      dic_pagina["url"] = str(portal_url) + '/@@pagina_processo_adm_integral?cod_documento=' + str(cod_documento) + '%26pagina=' +  pag['pagina']
                      dic_indice['paginas'].append(dic_pagina)
                      dic_indice['paginas_doc'] = len(dic_indice['paginas'])
               pasta.append(dic_indice)

           return pasta


class LimparPasta(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_limpar')

    def render(self, cod_documento):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()

        directory = os.path.join('/var/openlegis/SAGL4/var/tmp/', 'processo_adm_integral_' + str(cod_documento))
        dirpath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory)
        
        if os.path.exists(dirpath) and os.path.isdir(dirpath):
           shutil.rmtree(dirpath)      
           return 'Diretório temporário "' + dirpath + '" removido com sucesso.'
        else:
           return 'Diretório temporário "' + dirpath + '" não existe.'


class PaginaProcessoAdm(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_adm_integral')

    def render(self, cod_documento, pagina):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
 
        directory = os.path.join('/var/openlegis/SAGL4/var/tmp/', 'processo_adm_integral_' + str(cod_documento))
        dirpath = os.path.join('/var/openlegis/SAGL4/var/tmp/', directory, 'pages')       
    
        download = open(os.path.join(dirpath) +'/' + pagina, 'rb')
        arquivo = download.read()
        self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
        self.context.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %str(pagina))
        return arquivo
