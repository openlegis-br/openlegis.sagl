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
import pikepdf

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sanear_pdf(pdf_bytes, title=None, mod_date=None):
    """
    Tenta reprocessar e limpar um PDF corrompido usando fitz e pikepdf.
    """
    def tentar_fitz(stream):
        try:
            doc = fitz.open(stream=stream, filetype="pdf")
            _ = doc.page_count  # força leitura
            if title or mod_date:
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
            logger.warning(f"[sanear_pdf] Falha no fitz: {e}")
            return None

    # 1. Primeira tentativa com fitz
    result = tentar_fitz(BytesIO(pdf_bytes))
    if result:
        return result

    # 2. Tentativa de recuperação com pikepdf
    try:
        logger.info("[sanear_pdf] Tentando reparar com pikepdf")
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
            output_stream = BytesIO()
            pdf.save(output_stream)
            output_stream.seek(0)
            # 3. Nova tentativa com fitz após pikepdf
            result = tentar_fitz(output_stream)
            if result:
                logger.info("[sanear_pdf] PDF recuperado com sucesso via pikepdf")
                return result
            else:
                logger.error("[sanear_pdf] pikepdf salvou, mas fitz ainda não abre")
    except Exception as e:
        logger.error(f"[sanear_pdf] Erro ao tentar reparar com pikepdf: {e}")

    return None


class ProcessoNorma(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('norma_integral')
    install_home = os.environ.get('INSTALL_HOME')

    def download_files(self, cod_norma, forcar_regeneracao=False):
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_norma_{cod_norma}')
        pagepath = os.path.join(dirpath, 'pages')
        ready_file = os.path.join(dirpath, ".ready")
        lock_file = os.path.join(dirpath, ".lock")

        if os.path.exists(ready_file) and not forcar_regeneracao:
            try:
                with open(ready_file, 'r') as f:
                    ultima_geracao = datetime.strptime(f.read(), '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - ultima_geracao) < timedelta(minutes=5):
                    logging.info(f"[cache-hit] Usando versão em cache para {cod_norma}")
                    return
            except Exception as e:
                logging.warning(f"Erro ao verificar ready_file: {e}")

        os.makedirs(dirpath, exist_ok=True)
        os.makedirs(pagepath, exist_ok=True)

        try:
            with open(lock_file, 'w') as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    logging.warning(f"[lock] Norma {cod_norma} já está sendo processada por outro processo")
                    return

                if os.path.exists(dirpath):
                    shutil.rmtree(dirpath)
                    os.makedirs(dirpath)
                    os.makedirs(pagepath)

                lst_arquivos = []
                for norma in self.context.zsql.norma_juridica_obter_zsql(cod_norma=cod_norma):
                    processo_integral = f"{norma.sgl_tipo_norma}-{norma.num_norma}-{norma.ano_norma}.pdf"
                    id_processo = f"{norma.sgl_tipo_norma} {norma.num_norma}/{norma.ano_norma}"
                    id_norma = f"{norma.des_tipo_norma} nº {norma.num_norma}/{norma.ano_norma}"
                    id_capa = f"capa_{norma.sgl_tipo_norma}-{norma.num_norma}-{norma.ano_norma}"
                    id_arquivo = f"{id_capa}.pdf"

                    nom_arquivo_compilado = f"{cod_norma}_texto_consolidado.pdf"
                    nom_arquivo = f"{cod_norma}_texto_integral.pdf"

                    self.context.modelo_proposicao.capa_norma(cod_norma=norma.cod_norma, action='gerar')

                    if hasattr(self.context.temp_folder, id_arquivo):
                        lst_arquivos.append({
                            "data": DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 00:00:01'),
                            'path': self.context.temp_folder,
                            'file': id_arquivo,
                            'title': 'Capa da Norma'
                        })

                    if hasattr(self.context.sapl_documentos.norma_juridica, nom_arquivo_compilado):
                        lst_arquivos.append({
                            "data": DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 00:00:02'),
                            'path': self.context.sapl_documentos.norma_juridica,
                            'file': nom_arquivo_compilado,
                            'title': 'Texto Compilado'
                        })

                    if hasattr(self.context.sapl_documentos.norma_juridica, nom_arquivo):
                        lst_arquivos.append({
                            "data": DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 00:00:03'),
                            'path': self.context.sapl_documentos.norma_juridica,
                            'file': nom_arquivo,
                            'title': id_norma
                        })

                    for anexo in self.context.zsql.anexo_norma_obter_zsql(cod_norma=norma.cod_norma, ind_excluido=0):
                        nom_anexo = str(cod_norma) + '_anexo_' + anexo.cod_anexo
                        if hasattr(self.context.sapl_documentos.norma_juridica, nom_anexo):
                            dic = {}
                            dic["data"] = DateTime(norma.dat_norma, datefmt='international').strftime('%Y-%m-%d 00:00:03') + anexo.cod_anexo
                            dic['path'] = self.context.sapl_documentos.norma_juridica
                            dic['file'] = nom_anexo
                            dic['title'] = anexo.txt_descricao
                            lst_arquivos.append(dic)
                            logging.debug(f"Anexo encontrado: {nom_anexo}")
                        else:
                            logging.warning(f"Anexo não encontrado: {nom_anexo}")

                lst_arquivos.sort(key=lambda dic: dic['data'])
                lst_arquivos = [(i + 1, j) for i, j in enumerate(lst_arquivos)]

                merger = fitz.open()
                for i, dic in lst_arquivos:
                    downloaded_pdf = str(i).rjust(4, '0') + '.pdf'
                    arq = getattr(dic['path'], dic['file'], None)
                    if arq is None:
                        logging.error(f"Arquivo não encontrado: {dic['path']}/{dic['file']}")
                        continue

                    doc_tmp = sanear_pdf(BytesIO(bytes(arq.data)).read(), title=dic["title"], mod_date=dic["data"])
                    if doc_tmp:
                        try:
                            merger.insert_pdf(doc_tmp)
                            with open(os.path.join(dirpath, downloaded_pdf), 'wb') as f:
                                f.write(doc_tmp.tobytes())
                            logging.info(f"Arquivo adicionado: {dic['title']}")
                        except Exception as e:
                            logging.error(f"Erro ao inserir PDF: {dic['title']}: {e}")
                    else:
                        logging.error(f"Falha ao sanear PDF: {dic['title']}")

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

                for i, page in enumerate(existing_pdf):
                    file_name = os.path.join(pagepath, f"pg_{str(i+1).rjust(4, '0')}.pdf")
                    with fitz.open() as doc_tmp:
                        doc_tmp.insert_pdf(existing_pdf, from_page=i, to_page=i)
                        doc_tmp.set_metadata({"title": f"pg_{str(i+1).rjust(4, '0')}.pdf", "modDate": dic["data"]})
                        doc_tmp.save(file_name, deflate=True, garbage=3, use_objstms=1)

                with open(ready_file, 'w') as ready_f:
                    ready_f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                logging.info(f"[finalizado] Norma {cod_norma} gerada com sucesso")

        except Exception as e:
            logging.error(f"Erro crítico ao processar {cod_norma}: {e}")
            if os.path.exists(dirpath):
                try:
                    shutil.rmtree(dirpath)
                except:
                    pass
            raise
        finally:
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    pass

    def render(self, cod_norma, action):
        portal_url = self.context.portal_url.portal_url()
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_norma_{cod_norma}')
        pagepath = os.path.join(dirpath, 'pages')
        ready_file = os.path.join(dirpath, ".ready")

        # Pequeno atraso aleatório para evitar corrida de condições
        time.sleep(random.uniform(0.1, 0.3))

        if action != 'pagina':
            self.download_files(cod_norma, forcar_regeneracao=(action == 'force'))

        if action == 'download':
            for norma in self.context.zsql.norma_juridica_obter_zsql(cod_norma=cod_norma):
                arquivo_final = f"{norma.sgl_tipo_norma}-{norma.num_norma}-{norma.ano_norma}.pdf"
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
                                'title': arq2.metadata.get("title", ""),
                                'date': arq2.metadata.get("modDate", ""),
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
                        'date': item['date'],
                        "url": f"{portal_url}/@@pagina_processo_norma?cod_norma={cod_norma}%26pagina=pg_0001.pdf",
                        "paginas_geral": len(page_paths),
                        'paginas': [],
                        'paginas_doc': 0
                    }

                    for pag in lst_indice:
                        if item['id'] == str(pag.get('id', pag)):
                            dic_indice['paginas'].append({
                                'num_pagina': pag['num_pagina'],
                                'id_pagina': pag['pagina'],
                                "url": f"{portal_url}/@@pagina_processo_norma?cod_norma={cod_norma}%26pagina={pag['pagina']}"
                            })

                    dic_indice['paginas_doc'] = len(dic_indice['paginas'])
                    pasta.append(dic_indice)

                return pasta

            except Exception as e:
                logging.error(f"Erro ao renderizar pasta: {e}")
                self.context.REQUEST.RESPONSE.setStatus(500)
                return {"error": str(e)}


class LimparPasta(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('processo_norma_limpar')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_norma):
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_norma_{cod_norma}')
        lock_file = os.path.join(dirpath, ".lock")
        if os.path.exists(dirpath) and os.path.isdir(dirpath):
            if os.path.exists(lock_file):
                return f"Não foi possível remover {dirpath} - processo em andamento"
            shutil.rmtree(dirpath)
            return f'Diretório {dirpath} removido com sucesso.'
        else:
            return f'Diretório {dirpath} não existe.'


class PaginaProcessoNorma(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pagina_processo_norma')
    install_home = os.environ.get('INSTALL_HOME')

    async def render(self, cod_norma, pagina):
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_norma_{cod_norma}')
        pagepath = os.path.join(dirpath, 'pages')
        try:
            file_path = os.path.join(pagepath, pagina)
            async with aiofiles.open(file_path, 'rb') as download:
                arquivo = await download.read()
                self.context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
                self.context.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; filename=%s' % str(pagina))
                logging.info(f"Página '{pagina}' exibida para a norma '{cod_norma}'")
                return arquivo
        except FileNotFoundError:
            logging.error(f"Página '{pagina}' não encontrada para norma '{cod_norma}'")
            self.context.REQUEST.RESPONSE.setStatus(404)
            return "Arquivo não encontrado"
        except Exception as e:
            logging.exception(f"Erro ao exibir página '{pagina}' da norma '{cod_norma}': {e}")
            self.context.REQUEST.RESPONSE.setStatus(500)
            return "Erro ao processar o arquivo"

    def __call__(self, cod_norma, pagina):
        return asyncio.run(self.render(cod_norma, pagina))

class ProcessoNormaStatus(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('norma_integral_status')
    install_home = os.environ.get('INSTALL_HOME')

    def render(self, cod_norma):
        dirpath = os.path.join(self.install_home, f'var/tmp/processo_norma_{cod_norma}')
        ready_file = os.path.join(dirpath, ".ready")
        lock_file = os.path.join(dirpath, ".lock")

        if os.path.exists(lock_file):
            return "processing"
        elif os.path.exists(ready_file):
            return "ready"
        else:
            return "pending"
