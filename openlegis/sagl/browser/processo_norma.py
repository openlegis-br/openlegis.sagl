# -*- coding: utf-8 -*-
import os, shutil
from io import BytesIO
from DateTime import DateTime
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import uuid
import pymupdf


class ProcessoNorma(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('norma_integral')
    install_home = os.environ.get('INSTALL_HOME')

    def download_files(self, cod_norma):       
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_norma_' + str(cod_norma))
        pagepath = os.path.join(dirpath, 'pages')
        
        if os.path.exists(dirpath) and os.path.isdir(dirpath):
           shutil.rmtree(dirpath) 
           os.makedirs(dirpath)
           os.makedirs(pagepath)
        elif not os.path.exists(dirpath):
           os.makedirs(dirpath)
           os.makedirs(pagepath)
      
        lst_arquivos = []
               
        for norma in self.context.zsql.norma_juridica_obter_zsql(cod_norma=cod_norma):
            processo_integral = norma.sgl_tipo_norma+'-'+str(norma.num_norma)+'-'+str(norma.ano_norma)+'.pdf'
            id_processo = norma.sgl_tipo_norma + ' ' + str(norma.num_norma) + '/' +str(norma.ano_norma)
            id_norma = norma.des_tipo_norma + ' nº ' + str(norma.num_norma) + '/' +str(norma.ano_norma)

            nom_arquivo_compilado = str(cod_norma) + '_texto_consolidado.pdf'
            nom_arquivo = str(cod_norma) + '_texto_integral.pdf'
            
            if hasattr(self.context.sapl_documentos.norma_juridica, nom_arquivo_compilado):
               dic = {}
               dic["data"] = DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 00:00:01')
               dic['path'] = self.context.sapl_documentos.norma_juridica
               dic['file'] = nom_arquivo_compilado
               dic['title'] = 'Texto Compilado'
               lst_arquivos.append(dic)

            if hasattr(self.context.sapl_documentos.norma_juridica, nom_arquivo):
               dic = {}
               dic["data"] = DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 00:00:02')
               dic['path'] = self.context.sapl_documentos.norma_juridica
               dic['file'] = nom_arquivo
               dic['title'] = id_norma
               lst_arquivos.append(dic)

            for anexo in self.context.zsql.anexo_norma_obter_zsql(cod_norma=norma.cod_norma, ind_excluido=0):
                nom_anexo = str(cod_norma) + '_anexo_' + anexo.cod_anexo 
                if hasattr(self.context.sapl_documentos.norma_juridica, nom_anexo):
                   dic = {}
                   dic["data"] = DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 00:00:02') + anexo.cod_anexo
                   dic['path'] = self.context.sapl_documentos.norma_juridica
                   dic['file'] = nom_anexo
                   dic['title'] = anexo.txt_descricao
                   lst_arquivos.append(dic)

        lst_arquivos.sort(key=lambda dic: dic['data'])

        lst_arquivos = [(i + 1, j) for i, j in enumerate(lst_arquivos)]
       
        merger = pymupdf.open()

        for i, dic in lst_arquivos:
            downloaded_pdf = str(i).rjust(4, '0') + '.pdf'
            arq = getattr(dic['path'], dic['file'])
            arquivo_doc = BytesIO(bytes(arq.data))
            with pymupdf.open(stream=arquivo_doc) as texto_anexo:
               texto_anexo = pymupdf.open(stream=arquivo_doc)
               metadata = {"title": dic["title"]}
               texto_anexo.set_metadata(metadata)
               texto_anexo.bake()
               merger.insert_pdf(texto_anexo)
               arq2 = texto_anexo.tobytes()
               with open(os.path.join(dirpath) + '/' + downloaded_pdf, 'wb') as f:
                    f.write(arq2)
               texto_anexo.close()
        merged_pdf = merger.tobytes()
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
            shape.insert_text(p1, id_processo+'\n'+text, fontname = "helv", fontsize = 8)
            shape.commit()
        metadata = {"title": id_processo}
        existing_pdf.set_metadata(metadata)
        data = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        with open(os.path.join(dirpath) + '/' + processo_integral, 'wb') as f:
             f.write(data)

        with pymupdf.open(stream=data) as doc:
           for i, page in enumerate(doc):
               page_id = 'pg_' + str(i+1).rjust(4, '0') + '.pdf'
               file_name = os.path.join(os.path.join(pagepath), page_id)
               with pymupdf.open() as doc_tmp:
                   doc_tmp.insert_pdf(doc, from_page=i, to_page=i, rotate=-1, show_progress=False)
                   metadata = {"title": page_id}
                   doc_tmp.set_metadata(metadata)
                   doc_tmp.save(file_name, deflate=True, garbage=3, use_objstms=1)

    def render(self, cod_norma, action):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()    
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_norma_' + str(cod_norma))
        pagepath = os.path.join(dirpath, 'pages')

        self.download_files(cod_norma=cod_norma)

        if action == 'download':
           for norma in self.context.zsql.norma_juridica_obter_zsql(cod_norma=cod_norma):
               arquivo_final = str(norma.sgl_tipo_norma)+'-'+str(norma.num_norma)+'-'+str(norma.ano_norma)+'.pdf'
           with open(os.path.join(dirpath) + '/' + arquivo_final, 'rb') as download:
              arquivo = download.read()
              self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
              self.context.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %str(arquivo_final))
              return arquivo
        
        elif action == 'pasta' or action == '' or action == None:
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
                  lst_pages = []
                  lst_geral = []
                  with open(filepath, 'rb') as arq:
                     arq2 = pymupdf.open(arq)
                     dic['id'] = file
                     dic['title'] = arq2.metadata["title"]
                     num_pages = arq2.page_count
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
               dic_indice["url"] = str(portal_url) + '/@@pagina_processo_norma?cod_norma=' + str(cod_norma) + '%26pagina=' +  'pg_0001.pdf'
               dic_indice["paginas_geral"] = len(page_paths)
               dic_indice['paginas'] = []
               dic_indice['id_paginas'] = []
               for pag in lst_indice:
                   dic_pagina = {}
                   if item['id'] == str(pag.get('id',pag)):
                      dic_pagina['num_pagina'] = pag['num_pagina']
                      dic_pagina['id_pagina'] = pag['pagina']
                      dic_pagina["url"] = str(portal_url) + '/@@pagina_processo_norma?cod_norma=' + str(cod_norma) + '%26pagina=' +  pag['pagina']
                      dic_indice['paginas'].append(dic_pagina)
                      dic_indice['paginas_doc'] = len(dic_indice['paginas'])
               pasta.append(dic_indice)

           return pasta


class LimparPasta(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_norma_limpar')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_norma):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_norma_' + str(cod_norma))
        if os.path.exists(dirpath) and os.path.isdir(dirpath):
           shutil.rmtree(dirpath)      
           return 'Diretório temporário "' + dirpath + '" removido com sucesso.'
        else:
           return 'Diretório temporário "' + dirpath + '" não existe.'


class PaginaProcessoNorma(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_norma')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_norma, pagina):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_norma_' + str(cod_norma))
        pagepath = os.path.join(dirpath, 'pages')      
        with open(os.path.join(pagepath) +'/' + pagina, 'rb') as download:
           arquivo = download.read()
           self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
           self.context.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' %str(pagina))
           return arquivo
