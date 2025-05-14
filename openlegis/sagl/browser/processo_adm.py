# -*- coding: utf-8 -*-
import os
import shutil
import time
import random
import fcntl
from io import BytesIO
from DateTime import DateTime
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import uuid
import fitz
import logging
import asyncio
import aiofiles
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sanear_pdf(pdf_bytes, title=None, mod_date=None):
    """
    Tenta reprocessar e limpar um PDF corrompido, retornando uma nova instância legível.
    """
    try:
        with fitz.open(stream=BytesIO(pdf_bytes), filetype="pdf") as doc:
            _ = doc.page_count  # força leitura
            metadata = doc.metadata or {}
            if title:
                metadata["title"] = title
            if mod_date:
                metadata["modDate"] = mod_date
            doc.set_metadata(metadata)
            doc.bake()
            output_stream = BytesIO()
            doc.save(output_stream, garbage=3, deflate=True)
            output_stream.seek(0)

        return fitz.open(stream=output_stream, filetype="pdf")

    except Exception as e:
        logging.error(f"[sanear_pdf] Erro ao limpar PDF: {e}")
        return None

class ProcessoAdm(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral')
    install_home = os.environ.get('INSTALL_HOME')

    def download_files(self, cod_documento, forcar_regeneracao=False):
        """Baixa e processa os arquivos do processo administrativo com controle de concorrência robusto."""
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_adm_integral_{cod_documento}')
        pagepath = os.path.join(dirpath, 'pages')
        ready_file = os.path.join(dirpath, ".ready")
        lock_file = os.path.join(dirpath, ".lock")

        # 1. Verificação inicial do cache
        if os.path.exists(ready_file) and not forcar_regeneracao:
            try:
                with open(ready_file, 'r') as f:
                    ultima_geracao = datetime.strptime(f.read(), '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - ultima_geracao) < timedelta(seconds=30):
                    logger.info(f"[cache-hit] Usando versão em cache para {cod_documento}")
                    return
            except Exception as e:
                logger.warning(f"Erro ao verificar ready_file: {e}")

        # 2. Preparar diretório e lock
        os.makedirs(dirpath, exist_ok=True)
        
        try:
            with open(lock_file, 'w') as f:
                try:
                    # Obter lock exclusivo em nível de sistema operacional
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    logger.warning(f"[lock] Processo {cod_documento} já está sendo gerado por outro processo")
                    return

                # 3. Verificação dupla dentro da região crítica
                if os.path.exists(ready_file) and not forcar_regeneracao:
                   try:
                      with open(ready_file, 'r') as f:
                          ultima_geracao = datetime.strptime(f.read(), '%Y-%m-%d %H:%M:%S')
                      if (datetime.now() - ultima_geracao) < timedelta(seconds=30):
                          logger.info(f"[double-check] Processo {cod_documento} já foi gerado recentemente durante a espera")
                          return
                   except Exception as e:
                      logger.warning(f"[double-check] Erro ao verificar ready_file: {e}")


                # 4. Limpar diretório existente se necessário
                if os.path.exists(dirpath):
                    try:
                        shutil.rmtree(dirpath)
                        os.makedirs(pagepath)
                    except Exception as e:
                        logger.error(f"Erro ao limpar diretório: {e}")
                        raise

                # 5. Processar documentos
                lst_arquivos = []
                for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
                    processo_integral = f"{documento.sgl_tipo_documento}-{documento.num_documento}-{documento.ano_documento}.pdf"
                    id_processo = f"{documento.sgl_tipo_documento} {documento.num_documento}/{documento.ano_documento}"
                    id_capa = str(uuid.uuid4().hex)
                    id_arquivo = f"{id_capa}.pdf"
                    
                    self.context.modelo_proposicao.capa_processo_adm(cod_documento=cod_documento, nom_arquivo=id_capa, action='gerar')

                    if hasattr(self.context.temp_folder, id_arquivo):
                        lst_arquivos.append({
                            "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d 00:00:01'),
                            'path': self.context.temp_folder,
                            'file': id_arquivo,
                            'title': 'Capa do Processo'
                        })

                    nom_arquivo = f"{cod_documento}_texto_integral.pdf"
                    if hasattr(self.context.sapl_documentos.administrativo, nom_arquivo):
                        lst_arquivos.append({
                            "data": DateTime(documento.dat_documento, datefmt='international').strftime('%Y-%m-%d 00:00:02'),
                            'path': self.context.sapl_documentos.administrativo,
                            'file': nom_arquivo,
                            'title': f"{documento.des_tipo_documento} {documento.num_documento}/{documento.ano_documento}"
                        })

                    for docadm in self.context.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento=documento.cod_documento, ind_excluido=0):
                        nome = f"{docadm.cod_documento_acessorio}.pdf"
                        if hasattr(self.context.sapl_documentos.administrativo, nome):
                            lst_arquivos.append({
                                "data": DateTime(docadm.dat_documento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                                'path': self.context.sapl_documentos.administrativo,
                                'file': nome,
                                'title': docadm.nom_documento
                            })

                    for tram in self.context.zsql.tramitacao_administrativo_obter_zsql(cod_documento=documento.cod_documento, rd_ordem='1', ind_excluido=0):
                        nome = f"{tram.cod_tramitacao}_tram.pdf"
                        if hasattr(self.context.sapl_documentos.administrativo.tramitacao, nome):
                            lst_arquivos.append({
                                "data": DateTime(tram.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                                'path': self.context.sapl_documentos.administrativo.tramitacao,
                                'file': nome,
                                'title': f"Tramitação ({tram.des_status})"
                            })

                    for mat in self.context.zsql.documento_administrativo_materia_obter_zsql(cod_documento=documento.cod_documento, ind_excluido=0):
                        materia = self.context.zsql.materia_obter_zsql(cod_materia=mat.cod_materia, ind_excluido=0)[0]
                        for tipo in ['_redacao_final.pdf', '_texto_integral.pdf']:
                            nome = f"{mat.cod_materia}{tipo}"
                            if hasattr(self.context.sapl_documentos.materia, nome):
                                lst_arquivos.append({
                                    "data": DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                                    'path': self.context.sapl_documentos.materia,
                                    'file': nome,
                                    'title': f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica} (mat. vinculada)"
                                })
                                break

                # 6. Ordenar e mesclar PDFs
                lst_arquivos.sort(key=lambda dic: dic['data'])
                lst_arquivos = [(i + 1, j) for i, j in enumerate(lst_arquivos)]

                merger = fitz.open()
                for i, dic in lst_arquivos:
                    downloaded_pdf = str(i).rjust(4, '0') + '.pdf'
                    arq = getattr(dic['path'], dic['file'], None)
                    if arq is None:
                        logger.error(f"Arquivo não encontrado: {dic['path']}/{dic['file']}")
                        continue

                    doc_tmp = sanear_pdf(BytesIO(bytes(arq.data)).read(), title=dic["title"], mod_date=dic["data"])
                    if doc_tmp:
                        try:
                            merger.insert_pdf(doc_tmp)
                            with open(os.path.join(dirpath, downloaded_pdf), 'wb') as f:
                                f.write(doc_tmp.tobytes())
                            logger.info(f"Arquivo adicionado: {dic['title']}")
                        except Exception as e:
                            logger.error(f"Erro ao inserir PDF: {dic['title']}: {e}")
                    else:
                        logger.error(f"Falha ao sanear PDF: {dic['title']}")

                # 7. Finalizar PDF consolidado
                merged_pdf = merger.tobytes()
                existing_pdf = fitz.open(stream=merged_pdf)
                numPages = existing_pdf.page_count
                
                for page_index in range(numPages):
                    w = existing_pdf[page_index].rect.width
                    text = f"Fls. {page_index + 1}/{numPages}"
                    p1 = fitz.Point(w - 70, 25)
                    shape = existing_pdf[page_index].new_shape()
                    shape.insert_text(p1, id_processo + '\n' + text, fontname="helv", fontsize=8)
                    shape.commit()

                metadata = {"title": id_processo, "modDate": dic["data"]}
                existing_pdf.set_metadata(metadata)
                data = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
                
                with open(os.path.join(dirpath, processo_integral), 'wb') as f:
                    f.write(data)

                # 8. Salvar páginas individuais
                for i, page in enumerate(existing_pdf):
                    file_name = os.path.join(pagepath, f"pg_{str(i+1).rjust(4, '0')}.pdf")
                    with fitz.open() as doc_tmp:
                        doc_tmp.insert_pdf(existing_pdf, from_page=i, to_page=i)
                        doc_tmp.set_metadata({"title": f"pg_{str(i+1).rjust(4, '0')}.pdf", "modDate": dic["data"]})
                        doc_tmp.save(file_name, deflate=True, garbage=3, use_objstms=1)

                # 9. Marcar como concluído (DENTRO da região crítica)
                with open(ready_file, 'w') as ready_f:
                    ready_f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                logger.info(f"[finalizado] Processo {cod_documento} gerado com sucesso")

        except Exception as e:
            logger.error(f"Erro crítico ao processar {cod_documento}: {e}")
            if os.path.exists(dirpath):
                try:
                    shutil.rmtree(dirpath)
                except:
                    pass
            raise
        finally:
            # Liberar lock
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    pass

    def render(self, cod_documento, action):
        """Renderiza a view com tratamento especial para concorrência."""
        portal_url = self.context.portal_url.portal_url()
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_adm_integral_' + str(cod_documento))
        pagepath = os.path.join(dirpath, 'pages')
        ready_file = os.path.join(dirpath, ".ready")

        # Adicionar pequeno delay aleatório para evitar corrida de condições
        time.sleep(random.uniform(0.1, 0.3))

        if action != 'pagina':
            self.download_files(cod_documento, forcar_regeneracao=(action == 'force'))

        if action == 'download':
            for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
                arquivo_final = f"{documento.sgl_tipo_documento}-{documento.num_documento}-{documento.ano_documento}.pdf"
            with open(os.path.join(dirpath, arquivo_final), 'rb') as download:
                arquivo = download.read()
                self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
                self.context.REQUEST.RESPONSE.setHeader('Content-Disposition', f'inline; filename={arquivo_final}')
                return arquivo

        elif action in ('pasta', '', None):
            if not os.path.exists(ready_file):
                self.context.REQUEST.RESPONSE.setStatus(202)
                return {"status": "processing"}

            try:
                page_paths = [f for f in os.listdir(pagepath) if f.startswith("pg_")]
                file_paths = []
                
                for file in os.listdir(dirpath):
                    if file.startswith("0") and file.endswith(".pdf"):
                        filepath = os.path.join(dirpath, file)
                        with open(filepath, 'rb') as arq:
                            arq2 = fitz.open(arq)
                            file_paths.append({
                                'id': file,
                                'title': arq2.metadata["title"],
                                'date': arq2.metadata["modDate"],
                                'pages': list(range(1, arq2.page_count + 1))
                            })

                file_paths.sort(key=lambda dic: dic['id'])
                indice = []
                
                for item in file_paths:
                    for pagina in item['pages']:
                        indice.append({'id': item['id'], 'title': item['title'], 'date': item["date"]})

                indice1 = [(i + 1, j) for i, j in enumerate(indice)]
                lst_indice = []
                
                for i, arquivo in indice1:
                    lst_indice.append({
                        'id': arquivo['id'],
                        'titulo': arquivo['title'],
                        'data': arquivo['date'],
                        'num_pagina': str(i),
                        'pagina': 'pg_' + str(i).rjust(4, '0') + '.pdf'
                    })

                pasta = []
                for item in file_paths:
                    dic_indice = {
                        'id': item['id'],
                        'title': item['title'],
                        'data': item['date'],
                        "url": f"{portal_url}/@@pagina_processo_adm_integral?cod_documento={cod_documento}%26pagina=pg_0001.pdf",
                        "paginas_geral": len(page_paths),
                        'paginas': [],
                        'paginas_doc': 0
                    }
                    
                    for pag in lst_indice:
                        if item['id'] == str(pag.get('id', pag)):
                            dic_indice['paginas'].append({
                                'num_pagina': pag['num_pagina'],
                                'id_pagina': pag['pagina'],
                                "url": f"{portal_url}/@@pagina_processo_adm_integral?cod_documento={cod_documento}%26pagina={pag['pagina']}"
                            })
                    
                    dic_indice['paginas_doc'] = len(dic_indice['paginas'])
                    pasta.append(dic_indice)

                return pasta

            except Exception as e:
                logger.error(f"Erro ao renderizar pasta: {e}")
                self.context.REQUEST.RESPONSE.setStatus(500)
                return {"error": str(e)}


class LimparPasta(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_limpar')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_documento):
        dirpath = os.path.join(self.install_home, 'var/tmp/processo_adm_integral_' + str(cod_documento))
        if os.path.exists(dirpath) and os.path.isdir(dirpath):
            try:
                # Verificar se há um processo em andamento
                lock_file = os.path.join(dirpath, ".lock")
                if os.path.exists(lock_file):
                    return f"Não foi possível remover {dirpath} - processo em andamento"
                
                shutil.rmtree(dirpath)
                return f'Diretório {dirpath} removido com sucesso.'
            except Exception as e:
                return f'Erro ao remover diretório: {str(e)}'
        else:
            return f'Diretório {dirpath} não existe.'


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


class ProcessoAdmStatus(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_adm_integral_status')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_documento):
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_adm_integral_{cod_documento}')
        ready_file = os.path.join(dirpath, ".ready")
        lock_file = os.path.join(dirpath, ".lock")

        if os.path.exists(lock_file):
            return "processing"
        elif os.path.exists(ready_file):
            return "ready"
        else:
            return "pending"
