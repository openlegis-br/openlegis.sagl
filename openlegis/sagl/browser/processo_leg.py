# -*- coding: utf-8 -*-
import os
import shutil
import time
import random
import fcntl
import logging
from io import BytesIO
from DateTime import DateTime
from datetime import datetime, timedelta
from five import grok
from zope.interface import Interface
import fitz
import asyncio
import aiofiles

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('processo_leg_integral.log'),
        logging.StreamHandler()
    ]
)

# Constants
CACHE_TIMEOUT = 30  # seconds
PDF_OPTIONS = {
    'garbage': 3,
    'deflate': True,
    'clean': True,
    'use_objstms': True
}

def sanear_pdf(pdf_bytes, title=None, mod_date=None):
    """Clean and optimize PDF document."""
    try:
        with fitz.open(stream=BytesIO(pdf_bytes), filetype="pdf") as doc:
            # Validate document
            if not doc.page_count:
                raise ValueError("Empty PDF document")
            
            # Update metadata
            metadata = doc.metadata or {}
            if title:
                metadata["title"] = str(title)
            if mod_date:
                metadata["modDate"] = str(mod_date)
            doc.set_metadata(metadata)
            doc.bake()
            # Optimize and return
            output_stream = BytesIO()
            doc.save(output_stream, **PDF_OPTIONS)
            output_stream.seek(0)
            return fitz.open(stream=output_stream, filetype="pdf")

    except Exception as e:
        logging.error(f"[sanear_pdf] Erro ao processar o PDF: {str(e)}", exc_info=True)
        return None


class ProcessoLeg(grok.View):
    """Main view for legislative process PDF generation."""
    
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_integral')
    install_home = os.environ.get('INSTALL_HOME', '/tmp')

    def _get_document_paths(self, cod_materia):
        """Retrieve all document paths for a given legislative matter."""
        lst_arquivos = []
        
        for materia in self.context.zsql.materia_obter_zsql(cod_materia=cod_materia):
            # Process main documents
            self._process_main_documents(materia, lst_arquivos)
            # Process amendments
            self._process_amendments(materia, lst_arquivos)
            # Process reports
            self._process_reports(materia, lst_arquivos)
            # Process attached documents
            self._process_attachments(materia, lst_arquivos)
            # Process supporting documents
            self._process_supporting_docs(materia, lst_arquivos)
            # Process procedural documents
            self._process_procedural_docs(materia, lst_arquivos)
            # Process related norms
            self._process_related_norms(materia, lst_arquivos)

        # Sort by date
        lst_arquivos.sort(key=lambda dic: dic['data'])
        return [(i + 1, j) for i, j in enumerate(lst_arquivos)]

    def _process_main_documents(self, materia, lst_arquivos):
        """Process main legislative documents."""
        # Cover page

        id_capa = f"capa_{materia.sgl_tipo_materia}-{materia.num_ident_basica}-{materia.ano_ident_basica}"
        id_arquivo = f"{id_capa}.pdf"
        self.context.modelo_proposicao.capa_processo(cod_materia=materia.cod_materia, action='gerar')
        if hasattr(self.context.temp_folder, id_arquivo):
            lst_arquivos.append({
                "data": DateTime(materia.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d 00:00:01'),
                'path': self.context.temp_folder,
                'file': id_arquivo,
                'title': 'Capa do Processo'
            })

        # Main text
        nom_arquivo = f"{materia.cod_materia}_texto_integral.pdf"
        if hasattr(self.context.sapl_documentos.materia, nom_arquivo):
            date = DateTime(materia.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d 00:00:02')
            for proposicao in self.context.zsql.proposicao_obter_zsql(
                cod_mat_ou_doc=materia.cod_materia, ind_mat_ou_doc='M'):
                date = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
            
            lst_arquivos.append({
                "data": date,
                'path': self.context.sapl_documentos.materia,
                'file': nom_arquivo,
                'title': f"{materia.des_tipo_materia} nº {materia.num_ident_basica}/{materia.ano_ident_basica}"
            })

        # Final version
        nom_redacao = f"{materia.cod_materia}_redacao_final.pdf"
        if hasattr(self.context.sapl_documentos.materia, nom_redacao):
            date = DateTime(materia.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d 00:00:03')
            for proposicao in self.context.zsql.proposicao_obter_zsql(
                cod_mat_ou_doc=materia.cod_materia, ind_mat_ou_doc='M'):
                date = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
            
            lst_arquivos.append({
                "data": date,
                'path': self.context.sapl_documentos.materia,
                'file': nom_redacao,
                'title': 'Redação Final'
            })

    def _process_amendments(self, materia, lst_arquivos):
        """Process amendments and substitutes."""
        for substitutivo in self.context.zsql.substitutivo_obter_zsql(
            cod_materia=materia.cod_materia, ind_excluido=0):
            
            file_name = f"{substitutivo.cod_substitutivo}_substitutivo.pdf"
            if hasattr(self.context.sapl_documentos.substitutivo, file_name):
                date = DateTime(substitutivo.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                for proposicao in self.context.zsql.proposicao_obter_zsql(
                    cod_substitutivo=substitutivo.cod_substitutivo):
                    date = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                
                lst_arquivos.append({
                    "data": date,
                    'path': self.context.sapl_documentos.substitutivo,
                    "file": file_name,
                    'title': f"Substitutivo nº {substitutivo.num_substitutivo}"
                })

        for eme in self.context.zsql.emenda_obter_zsql(
            cod_materia=materia.cod_materia, ind_excluido=0):
            
            file_name = f"{eme.cod_emenda}_emenda.pdf"
            if hasattr(self.context.sapl_documentos.emenda, file_name):
                date = DateTime(eme.dat_apresentacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                for proposicao in self.context.zsql.proposicao_obter_zsql(
                    cod_emenda=eme.cod_emenda):
                    date = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                
                lst_arquivos.append({
                    "data": date,
                    'path': self.context.sapl_documentos.emenda,
                    "file": file_name,
                    "title": f"Emenda {eme.des_tipo_emenda} nº {eme.num_emenda}"
                })

    def _process_reports(self, materia, lst_arquivos):
        """Process committee reports."""
        for relat in self.context.zsql.relatoria_obter_zsql(
            cod_materia=materia.cod_materia, ind_excluido=0):
            
            file_name = f"{relat.cod_relatoria}_parecer.pdf"
            if hasattr(self.context.sapl_documentos.parecer_comissao, file_name):
                date = DateTime(relat.dat_destit_relator, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                for proposicao in self.context.zsql.proposicao_obter_zsql(
                    cod_parecer=relat.cod_relatoria):
                    date = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                
                comissao = self.context.zsql.comissao_obter_zsql(
                    cod_comissao=relat.cod_comissao, ind_excluido=0)[0]
                
                lst_arquivos.append({
                    "data": date,
                    'path': self.context.sapl_documentos.parecer_comissao,
                    "file": file_name,
                    "title": f"Parecer {comissao.sgl_comissao} nº {relat.num_parecer}/{relat.ano_parecer}"
                })

    def _process_attachments(self, materia, lst_arquivos):
        """Process attached documents."""
        # Documents attached to this matter
        for anexada in self.context.zsql.anexada_obter_zsql(
            cod_materia_principal=materia.cod_materia, ind_excluido=0):
            
            file_name = f"{anexada.cod_materia_anexada}_texto_integral.pdf"
            if hasattr(self.context.sapl_documentos.materia, file_name):
                lst_arquivos.append({
                    "data": DateTime(anexada.dat_anexacao, datefmt='international').strftime('%Y-%m-%d 23:58:00'),
                    'path': self.context.sapl_documentos.materia,
                    "file": file_name,
                    "title": f"{anexada.tip_materia_anexada} {anexada.num_materia_anexada}/{anexada.ano_materia_anexada} (anexada)"
                })
                
                # Supporting docs of attached matter
                for documento in self.context.zsql.documento_acessorio_obter_zsql(
                    cod_materia=anexada.cod_materia_anexada, ind_excluido=0):
                    
                    if hasattr(self.context.sapl_documentos.materia, f"{documento.cod_documento}.pdf"):
                        date = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        for proposicao in self.context.zsql.proposicao_obter_zsql(
                            cod_mat_ou_doc=documento.cod_documento, ind_mat_ou_doc='D'):
                            date = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        
                        lst_arquivos.append({
                            "data": date,
                            'path': self.context.sapl_documentos.materia,
                            "file": f"{documento.cod_documento}.pdf",
                            "title": f"{documento.nom_documento} (acess. de anexada)"
                        })

        # Documents this matter is attached to
        for anexada in self.context.zsql.anexada_obter_zsql(
            cod_materia_anexada=materia.cod_materia, ind_excluido=0):
            
            file_name = f"{anexada.cod_materia_principal}_texto_integral.pdf"
            if hasattr(self.context.sapl_documentos.materia, file_name):
                lst_arquivos.append({
                    "data": DateTime(anexada.dat_anexacao, datefmt='international').strftime('%Y-%m-%d 23:58:00'),
                    'path': self.context.sapl_documentos.materia,
                    "file": file_name,
                    "title": f"{anexada.tip_materia_principal} {anexada.num_materia_principal}/{anexada.ano_materia_principal} (anexadora)"
                })
                
                # Supporting docs of attaching matter
                for documento in self.context.zsql.documento_acessorio_obter_zsql(
                    cod_materia=anexada.cod_materia_principal, ind_excluido=0):
                    
                    if hasattr(self.context.sapl_documentos.materia, f"{documento.cod_documento}.pdf"):
                        date = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        for proposicao in self.context.zsql.proposicao_obter_zsql(
                            cod_mat_ou_doc=documento.cod_documento, ind_mat_ou_doc='D'):
                            date = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                        
                        lst_arquivos.append({
                            "data": date,
                            'path': self.context.sapl_documentos.materia,
                            "file": f"{documento.cod_documento}.pdf",
                            "title": f"{documento.nom_documento} (acess. de anexadora)"
                        })

    def _process_supporting_docs(self, materia, lst_arquivos):
        """Process supporting documents."""
        for documento in self.context.zsql.documento_acessorio_obter_zsql(
            cod_materia=materia.cod_materia, ind_excluido=0):
            
            if hasattr(self.context.sapl_documentos.materia, f"{documento.cod_documento}.pdf"):
                date = DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                for proposicao in self.context.zsql.proposicao_obter_zsql(
                    cod_mat_ou_doc=documento.cod_documento, ind_mat_ou_doc='D'):
                    date = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                
                lst_arquivos.append({
                    "data": date,
                    'path': self.context.sapl_documentos.materia,
                    "file": f"{documento.cod_documento}.pdf",
                    "title": documento.nom_documento
                })

    def _process_procedural_docs(self, materia, lst_arquivos):
        """Process procedural documents."""
        for tram in self.context.zsql.tramitacao_obter_zsql(
            cod_materia=materia.cod_materia, rd_ordem='1', ind_excluido=0):
            
            file_name = f"{tram.cod_tramitacao}_tram.pdf"
            if hasattr(self.context.sapl_documentos.materia.tramitacao, file_name):
                lst_arquivos.append({
                    "data": DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                    'path': self.context.sapl_documentos.materia.tramitacao,
                    "file": file_name,
                    "title": f"Tramitação ({tram.des_status})"
                })

    def _process_related_norms(self, materia, lst_arquivos):
        """Process related legal norms."""
        for norma in self.context.zsql.materia_buscar_norma_juridica_zsql(
            cod_materia=materia.cod_materia):
            
            file_name = f"{norma.cod_norma}_texto_integral.pdf"
            if hasattr(self.context.sapl_documentos.norma_juridica, file_name):
                lst_arquivos.append({
                    "data": DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 23:59:00'),
                    'path': self.context.sapl_documentos.norma_juridica,
                    "file": file_name,
                    "title": f"{norma.sgl_norma} nº {norma.num_norma}/{norma.ano_norma}"
                })

    def _generate_final_pdf(self, cod_materia, lst_arquivos, dirpath, pagepath):
        """Generate the final merged PDF with page numbers."""
        try:
            # Get matter info
            materia = self.context.zsql.materia_obter_zsql(cod_materia=cod_materia)[0]
            processo_integral = f"{materia.sgl_tipo_materia}-{materia.num_ident_basica}-{materia.ano_ident_basica}.pdf"
            id_processo = f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica}"

            # Create merged PDF
            merger = fitz.open()
            
            # Process each document
            for i, dic in lst_arquivos:
                downloaded_pdf = f"{i:04d}.pdf"
                try:
                    arq = getattr(dic['path'], dic['file'])
                    arquivo_doc = BytesIO(bytes(arq.data))
                    texto_anexo = sanear_pdf(arquivo_doc.getvalue(), title=dic["title"], mod_date=dic["data"])
                    if not texto_anexo:
                       raise RuntimeError(f"Erro ao processar o documento corrompido: {dic['title']}")

                    # Inserir no PDF final
                    merger.insert_pdf(texto_anexo)

                    # Salvar individualmente
                    with open(os.path.join(dirpath, downloaded_pdf), 'wb') as f:
                         f.write(texto_anexo.tobytes(**PDF_OPTIONS))
                         logging.info(f"Arquivo adicionado: {dic['title']}")

                except Exception as e:
                    logging.error(f"[merge-error] Erro ao inserir o documento {dic['file']} ({dic['title']}): {e}", exc_info=True)
                    raise RuntimeError(f"Erro ao processar o documento corrompido: {dic['title']}")

            # Add page numbers to merged PDF
            numPages = merger.page_count
            for page_index in range(len(merger)):
                page = merger[page_index]
                w = page.rect.width
                h = page.rect.height
                
                # Create annotation for page number
                text = f"Fls. {page_index+1}/{numPages}"
                p1 = fitz.Point(w - 70 - 5, 5 + 20)  # Position for page number
                
                shape = page.new_shape()
                shape.draw_circle(p1, 1)
                shape.insert_text(
                    p1, 
                    f"{id_processo}\n{text}", 
                    fontname="helv", 
                    fontsize=8
                )
                shape.commit()

            # Set final metadata
            merger.set_metadata({
                "title": id_processo,
                "modDate": lst_arquivos[-1][1]["data"] if lst_arquivos else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            # Save final PDF
            final_pdf_path = os.path.join(dirpath, processo_integral)
            with open(final_pdf_path, 'wb') as f:
                f.write(merger.tobytes(**PDF_OPTIONS))

            # Generate individual pages
            self._generate_individual_pages(merger, pagepath, lst_arquivos[-1][1]["data"] if lst_arquivos else None)

            return True

        except Exception as e:
            logging.error(f"Erro ao gerar o PDF final: {str(e)}", exc_info=True)
            return False

    def _generate_individual_pages(self, merged_doc, pagepath, mod_date):
        """Generate individual page files from merged document."""
        try:
            os.makedirs(pagepath, exist_ok=True)
            
            for i, page in enumerate(merged_doc):
                page_id = f"pg_{i+1:04d}.pdf"
                file_name = os.path.join(pagepath, page_id)
                
                with fitz.open() as doc_tmp:
                    doc_tmp.insert_pdf(
                        merged_doc, 
                        from_page=i, 
                        to_page=i, 
                        rotate=-1
                    )
                    
                    # Set page metadata
                    doc_tmp.set_metadata({
                        "title": page_id,
                        "modDate": mod_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
                    # Save individual page
                    doc_tmp.save(file_name, **PDF_OPTIONS)
            
            return True
        
        except Exception as e:
            logging.error(f"Erro ao gerar páginas individuais: {str(e)}", exc_info=True)
            return False

    def download_files(self, cod_materia, forcar_regeneracao=False):
        """Download and process all files for a legislative matter."""
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_leg_integral_{cod_materia}')
        pagepath = os.path.join(dirpath, 'pages')
        ready_file = os.path.join(dirpath, ".ready")
        lock_file = os.path.join(dirpath, ".lock")

        # Check cache
        if os.path.exists(ready_file) and not forcar_regeneracao:
            try:
                with open(ready_file, 'r') as f:
                    ultima_geracao = datetime.strptime(f.read(), '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - ultima_geracao) < timedelta(seconds=CACHE_TIMEOUT):
                    logging.info(f"[cache-hit] Usando versão em cache para {cod_materia}")
                    return
            except Exception as e:
                logging.warning(f"Erro ao verificar arquivo de prontidão (.ready): {e}")

        # Create directories
        os.makedirs(dirpath, exist_ok=True)
        os.makedirs(pagepath, exist_ok=True)

        # Acquire lock
        try:
            with open(lock_file, 'w') as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    logging.warning(f"[lock] O processo {cod_materia} já está sendo executado")
                    return

                # Clean directory
                if os.path.exists(dirpath):
                    shutil.rmtree(dirpath)
                    os.makedirs(dirpath)
                    os.makedirs(pagepath)

                # Get document paths
                lst_arquivos = self._get_document_paths(cod_materia)
                
                # Generate final PDF
                if not self._generate_final_pdf(cod_materia, lst_arquivos, dirpath, pagepath):
                    raise RuntimeError("Failed to generate final PDF")

                # Mark as ready
                with open(ready_file, 'w') as rf:
                    rf.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        except Exception as e:
            logging.error(f"Erro ao processar a matéria {cod_materia}: {e}", exc_info=True)
            if os.path.exists(dirpath):
                shutil.rmtree(dirpath)
            raise
        finally:
            if os.path.exists(lock_file):
                os.remove(lock_file)

    def render(self, cod_materia, action=None):
        """Main view renderer."""
        portal_url = self.context.portal_url.portal_url()
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_leg_integral_{cod_materia}')
        pagepath = os.path.join(dirpath, 'pages')

        # Process documents
        self.download_files(cod_materia=cod_materia)

        # Handle different actions
        if action == 'download':
            materia = self.context.zsql.materia_obter_zsql(cod_materia=cod_materia)[0]
            arquivo_final = f"{materia.sgl_tipo_materia}-{materia.num_ident_basica}-{materia.ano_ident_basica}.pdf"
            
            with open(os.path.join(dirpath, arquivo_final), 'rb') as download:
                arquivo = download.read()
                self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
                self.context.REQUEST.RESPONSE.setHeader(
                    'Content-Disposition',
                    f'inline; filename={arquivo_final}'
                )
                return arquivo
        
        elif action in ('pasta', '', None):
            # Get page files
            page_paths = [
                file for file in os.listdir(pagepath) 
                if file.startswith("pg_") and file.endswith(".pdf")
            ]

            # Process document files
            file_paths = []
            for file in os.listdir(dirpath):
                if file.startswith("0") and file.endswith(".pdf"):
                    filepath = os.path.join(dirpath, file)
                    
                    with open(filepath, 'rb') as arq:
                        with fitz.open(arq) as arq2:
                            file_paths.append({
                                'id': file,
                                'title': arq2.metadata.get("title", ""),
                                'date': arq2.metadata.get("modDate", ""),
                                'pages': list(range(1, arq2.page_count + 1))
                            })

            # Sort files
            file_paths.sort(key=lambda dic: dic['id'])

            # Create index
            indice = []
            for item in file_paths:
                for pagina in item['pages']:
                    indice.append({
                        'id': item['id'],
                        'title': item['title'],
                        'date': item["date"]
                    })

            # Enumerate index
            lst_indice = []
            for i, arquivo in enumerate(indice, 1):
                lst_indice.append({
                    'id': arquivo['id'],
                    'titulo': arquivo['title'],
                    'data': arquivo['date'],
                    'num_pagina': str(i),
                    'pagina': f"pg_{i:04d}.pdf"
                })

            # Build folder structure
            pasta = []
            for item in file_paths:
                dic_indice = {
                    'id': item['id'],
                    'title': item['title'],
                    'data': item['date'],
                    "url": f"{portal_url}/@@pagina_processo_leg_integral?cod_materia={cod_materia}%26pagina=pg_0001.pdf",
                    "paginas_geral": len(page_paths),
                    'paginas': [],
                    'id_paginas': []
                }
                
                for pag in lst_indice:
                    if item['id'] == str(pag.get('id', pag)):
                        dic_indice['paginas'].append({
                            'num_pagina': pag['num_pagina'],
                            'id_pagina': pag['pagina'],
                            "url": f"{portal_url}/@@pagina_processo_leg_integral?cod_materia={cod_materia}%26pagina={pag['pagina']}"
                        })
                
                dic_indice['paginas_doc'] = len(dic_indice['paginas'])
                pasta.append(dic_indice)

            return pasta


class LimparPasta(grok.View):
    """View to clean temporary folders."""
    
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_integral_limpar')
    install_home = os.environ.get('INSTALL_HOME', '/tmp')

    def render(self, cod_materia):
        """Clean the temporary folder for a specific matter."""
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_leg_integral_{cod_materia}')
        lock_file = os.path.join(dirpath, ".lock")
        
        if os.path.exists(dirpath):
            if os.path.exists(lock_file):
                return f"Não foi possível remover {dirpath} - processo em andamento"
            
            shutil.rmtree(dirpath)
            return f'Diretório {dirpath} removido com sucesso.'
        
        return f'Diretório {dirpath} não existe.'


class PaginaProcessoLeg(grok.View):
    """View to serve individual pages."""
    
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_leg_integral')
    install_home = os.environ.get('INSTALL_HOME', '/tmp')

    async def render(self, cod_materia, pagina):
        """Serve a single page from the processed PDF."""
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_leg_integral_{cod_materia}')
        pagepath = os.path.join(dirpath, 'pages')
        
        try:
            file_path = os.path.join(pagepath, pagina)
            async with aiofiles.open(file_path, 'rb') as download:
                arquivo = await download.read()
                self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
                self.context.REQUEST.RESPONSE.setHeader(
                    'Content-Disposition',
                    f'inline; filename={pagina}'
                )
                return arquivo
                
        except FileNotFoundError:
            self.context.REQUEST.RESPONSE.setStatus(404)
            return "Página não encontrada"
            
        except Exception as e:
            self.context.REQUEST.RESPONSE.setStatus(500)
            return f"Erro interno: {e}"

    def __call__(self, cod_materia, pagina):
        return asyncio.run(self.render(cod_materia, pagina))

class ProcessoLegStatus(grok.View):
    """View to check processing status."""
    
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_leg_integral_status')
    install_home = os.environ.get('INSTALL_HOME', '/tmp')

    def render(self, cod_materia):
        """Check the processing status of a matter."""
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_leg_integral_{cod_materia}')
        ready_file = os.path.join(dirpath, ".ready")
        lock_file = os.path.join(dirpath, ".lock")

        if os.path.exists(lock_file):
            return "processing"
        elif os.path.exists(ready_file):
            return "ready"
        else:
            return "pending"
