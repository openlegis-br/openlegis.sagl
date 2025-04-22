# -*- coding: utf-8 -*-
import os
import shutil
import asyncio
import aiofiles
from io import BytesIO
from DateTime import DateTime
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import uuid
import pymupdf
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProcessoAdm(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral')
    install_home = os.environ.get('INSTALL_HOME')

    def _get_document_by_path(self, path):
        """Get document using unrestrictedTraverse with proper path handling"""
        if not path or not isinstance(path, str):
            logger.error(f"Invalid path: {path}")
            return None
            
        try:
            # Remove leading slash if present
            clean_path = path[1:] if path.startswith('/') else path
            return self.context.unrestrictedTraverse(clean_path)
        except Exception as e:
            logger.error(f"Error accessing document at {path}: {e}")
            return None

    async def _ensure_directory(self, dirpath, pagepath):
        """Ensure directory structure exists"""
        try:
            if os.path.exists(dirpath):
                shutil.rmtree(dirpath)
            os.makedirs(pagepath, exist_ok=True)
        except OSError as e:
            logger.error(f"Error creating directory structure: {e}")
            raise

    async def download_files(self, cod_documento):       
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_adm_integral_{cod_documento}')
        pagepath = os.path.join(dirpath, 'pages')
        
        try:
            await self._ensure_directory(dirpath, pagepath)
        except Exception as e:
            logger.error(f"Failed to create directories: {e}")
            return

        lst_arquivos = []
        
        try:
            documentos = self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento)
            if not documentos:
                logger.error(f"No document found for cod_documento: {cod_documento}")
                return

            documento = documentos[0]
            processo_integral = f"{documento.sgl_tipo_documento}-{documento.num_documento}-{documento.ano_documento}.pdf"
            id_processo = f"{documento.sgl_tipo_documento} {documento.num_documento}/{documento.ano_documento}"
            
            # Process cover
            id_capa = uuid.uuid4().hex
            id_arquivo = f"{id_capa}.pdf"
            self.context.modelo_proposicao.capa_processo_adm(
                cod_documento=cod_documento,
                nom_arquivo=id_capa,
                action='gerar'
            )
            
            temp_file_path = f"temp_folder/{id_arquivo}"
            temp_file = self._get_document_by_path(temp_file_path)
            if temp_file:
                lst_arquivos.append({
                    "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d 00:00:01'),
                    'path': temp_file_path,
                    'file': id_arquivo,
                    'title': 'Capa do Processo'
                })

            # Process main document
            admin_file_path = f"sapl_documentos/administrativo/{cod_documento}_texto_integral.pdf"
            admin_file = self._get_document_by_path(admin_file_path)
            if admin_file:
                lst_arquivos.append({
                    "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d 00:00:02'),
                    'path': admin_file_path,
                    'file': f"{cod_documento}_texto_integral.pdf",
                    'title': f"{documento.des_tipo_documento} {documento.num_documento}/{documento.ano_documento}"
                })

            # Process accessory documents
            for docadm in self.context.zsql.documento_acessorio_administrativo_obter_zsql(
                cod_documento=documento.cod_documento, 
                ind_excluido=0
            ):
                docadm_path = f"sapl_documentos/administrativo/{docadm.cod_documento_acessorio}.pdf"
                docadm_file = self._get_document_by_path(docadm_path)
                if docadm_file:
                    lst_arquivos.append({
                        "data": DateTime(docadm.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                        'path': docadm_path,
                        'file': f"{docadm.cod_documento_acessorio}.pdf",
                        'title': docadm.nom_documento
                    })

            # Process tramitation documents
            for tram in self.context.zsql.tramitacao_administrativo_obter_zsql(
                cod_documento=documento.cod_documento,
                rd_ordem='1',
                ind_excluido=0
            ):
                tram_path = f"sapl_documentos/administrativo/tramitacao/{tram.cod_tramitacao}_tram.pdf"
                tram_file = self._get_document_by_path(tram_path)
                if tram_file:
                    lst_arquivos.append({
                        "data": DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                        'path': tram_path,
                        'file': f"{tram.cod_tramitacao}_tram.pdf",
                        'title': f"Tramitação ({tram.des_status})"
                    })

            # Process linked materials
            for mat in self.context.zsql.documento_administrativo_materia_obter_zsql(
                cod_documento=documento.cod_documento,
                ind_excluido=0
            ):
                materia = self.context.zsql.materia_obter_zsql(cod_materia=mat.cod_materia, ind_excluido=0)[0]
                
                # Try redacao_final first
                materia_rf_path = f"sapl_documentos/materia/{mat.cod_materia}_redacao_final.pdf"
                materia_rf_file = self._get_document_by_path(materia_rf_path)
                if materia_rf_file:
                    lst_arquivos.append({
                        "data": DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                        'path': materia_rf_path,
                        'file': f"{mat.cod_materia}_redacao_final.pdf",
                        'title': f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica} (mat. vinculada)"
                    })
                else:
                    # Fall back to texto_integral
                    materia_ti_path = f"sapl_documentos/materia/{mat.cod_materia}_texto_integral.pdf"
                    materia_ti_file = self._get_document_by_path(materia_ti_path)
                    if materia_ti_file:
                        lst_arquivos.append({
                            "data": DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                            'path': materia_ti_path,
                            'file': f"{mat.cod_materia}_texto_integral.pdf",
                            'title': f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica} (mat. vinculada)"
                        })

            # Sort files by date
            lst_arquivos.sort(key=lambda dic: dic['data'])
            lst_arquivos = [(i + 1, j) for i, j in enumerate(lst_arquivos)]
            
            # Merge PDFs
            merger = pymupdf.open()
            for i, dic in lst_arquivos:
                downloaded_pdf = f"{i:04d}.pdf"
                file_obj = self._get_document_by_path(dic['path'])
                if file_obj is None:
                    logger.error(f"File not found: {dic['path']}")
                    continue

                try:
                    arquivo_doc = BytesIO(bytes(file_obj.data))
                    with pymupdf.open(stream=arquivo_doc) as texto_anexo:
                        metadata = {"title": dic["title"], "modDate": dic["data"]}
                        texto_anexo.set_metadata(metadata)
                        texto_anexo.bake()
                        merger.insert_pdf(texto_anexo)
                        async with aiofiles.open(os.path.join(dirpath, downloaded_pdf), 'wb') as f:
                            await f.write(texto_anexo.tobytes())
                    logger.info(f"File added successfully: {dic['title']}")
                except Exception as e:
                    logger.error(f"Error processing file {dic['title']}: {e}")
                    continue

            # Finalize merged PDF
            try:
                with pymupdf.open(stream=merger.tobytes()) as existing_pdf:
                    numPages = existing_pdf.page_count
                    
                    for page_index in range(len(existing_pdf)):
                        page = existing_pdf[page_index]
                        w = page.rect.width
                        h = page.rect.height
                        margin = 5
                        text = f"Fls. {page_index+1}/{numPages}"
                        p1 = pymupdf.Point(w - 70 - margin, margin + 20)
                        
                        shape = page.new_shape()
                        shape.draw_circle(p1, 1)
                        shape.insert_text(p1, f"{id_processo}\n{text}", fontname="helv", fontsize=8)
                        shape.commit()
                    
                    metadata = {"title": id_processo, "modDate": lst_arquivos[-1][1]["data"] if lst_arquivos else ""}
                    existing_pdf.set_metadata(metadata)
                    
                    async with aiofiles.open(os.path.join(dirpath, processo_integral), 'wb') as f:
                        await f.write(existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1))
                
                logger.info(f"Final PDF saved: {processo_integral}")

                # Extract individual pages
                async with aiofiles.open(os.path.join(dirpath, processo_integral), 'rb') as f:
                    content = await f.read()
                    with pymupdf.open(stream=content) as doc:
                        tasks = []
                        
                        for i in range(len(doc)):
                            page_id = f"pg_{i+1:04d}.pdf"
                            file_name = os.path.join(pagepath, page_id)
                            tasks.append(self._save_single_page(doc, i, file_name, page_id))
                        
                        await asyncio.gather(*tasks)
                        logger.info("Page extraction completed.")

            except Exception as e:
                logger.error(f"Error finalizing PDF: {e}")
                raise

        except Exception as e:
            logger.error(f"Error in document processing: {e}")
            raise

    async def _save_single_page(self, doc, page_num, file_name, page_id):
        """Save a single page as separate PDF"""
        try:
            with pymupdf.open() as doc_tmp:
                doc_tmp.insert_pdf(doc, from_page=page_num, to_page=page_num, rotate=-1, show_progress=False)
                doc_tmp.set_metadata({"title": page_id})
                doc_tmp.save(file_name, deflate=True, garbage=3, use_objstms=1)
            logger.debug(f"Page {file_name} extracted.")
        except Exception as e:
            logger.error(f"Error saving page {page_num}: {e}")
            raise

    def render(self, cod_documento, action):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()    
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_adm_integral_' + str(cod_documento))
        pagepath = os.path.join(dirpath, 'pages')

        asyncio.run(self.download_files(cod_documento=cod_documento))

        if action == 'download':
           for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
               arquivo_final = str(documento.sgl_tipo_documento)+'-'+str(documento.num_documento)+'-'+str(documento.ano_documento)+'.pdf'
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
                     dic['date'] = arq2.metadata["modDate"]
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
               dic['date'] = item["date"]
               for pagina in item['pages']:
                   indice.append(dic) 

           indice1 = [(i + 1, j) for i, j in enumerate(indice)]

           lst_indice = []
           for i, arquivo in indice1:
               dic = {}
               dic['id'] = arquivo['id']
               dic['titulo'] = arquivo['title']
               dic['data'] = arquivo['date']
               dic['num_pagina'] = str(i)
               dic['pagina'] = 'pg_' + str(i).rjust(4, '0') + '.pdf'
               lst_indice.append(dic)

           pasta = []
           
           for item in file_paths:
               dic_indice= {}
               dic_indice['id'] = item['id']
               dic_indice['title'] = item['title']
               dic_indice['data'] = item['date']
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
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_documento):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_adm_integral_' + str(cod_documento))
        if os.path.exists(dirpath) and os.path.isdir(dirpath):
           shutil.rmtree(dirpath)      
           return 'Diretório temporário "' + dirpath + '" removido com sucesso.'
        else:
           return 'Diretório temporário "' + dirpath + '" não existe.'


class PaginaProcessoAdm(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_adm_integral')
    install_home = os.environ.get('INSTALL_HOME')

    async def render(self, cod_documento, pagina):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_adm_integral_' + str(cod_documento))
        pagepath = os.path.join(dirpath, 'pages')      
        try:
            file_path = os.path.join(pagepath, pagina)
            async with aiofiles.open(file_path, 'rb') as download:
                arquivo = await download.read()
                self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
                self.context.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' % str(pagina))
                logging.info(f"Página '{pagina}' exibida para o processo adminisrativo '{cod_documento}' from '{file_path}'")
                return arquivo
        except FileNotFoundError:
            logging.error(f"Arquivo '{pagina}' não encontrado no diretório '{pagepath}'do processo adminisrativo '{cod_documento}'")
            self.context.REQUEST.RESPONSE.setStatus(404)
            return "Arquivo não encontrado"
        except Exception as e:
            logging.exception(f"Erro ao exibir a página '{pagina}' do processo administrativo '{cod_documento}': {e}")
            self.context.REQUEST.RESPONSE.setStatus(500)
            return "Erro ao processar o arquivo"

    def __call__(self, cod_documento, pagina):
        return asyncio.run(self.render(cod_documento, pagina))
