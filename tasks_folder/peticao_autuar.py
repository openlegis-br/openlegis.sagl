from .utils import zope_task, make_qrcode, get_signatures, parse_signatures
from io import BytesIO
import os
import pypdf
import fitz as pymupdf
import pikepdf
from DateTime import DateTime
import logging


def reparar_pdf_stream(file_stream: BytesIO) -> BytesIO:
    file_stream.seek(0)
    original_data = file_stream.read()
    try:
        buffer = BytesIO()
        with pikepdf.open(BytesIO(original_data)) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(buffer, linearize=True)
        repaired_data = buffer.getvalue()
        pymupdf.open(stream=repaired_data, filetype="pdf").close()
        logging.info("PDF successfully repaired using pikepdf.")
        return BytesIO(repaired_data)
    except Exception as e:
        logging.warning(f"PDF repair with pikepdf failed: {e!r}. Trying rasterization.")

    try:
        doc = pymupdf.open(stream=original_data)
        novo = pymupdf.open()
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = pix.tobytes("png")
            rect = pymupdf.Rect(0, 0, pix.width, pix.height)
            nova = novo.new_page(width=pix.width, height=pix.height)
            nova.insert_image(rect, stream=img)
        out = BytesIO()
        novo.save(out, garbage=4, deflate=True)
        novo.close()
        logging.info("PDF repaired via rasterization.")
        out.seek(0)
        return out
    except Exception as e:
        logging.error(f"Rasterization failed: {e!r}. Using original file.")
        file_stream.seek(0)
        return file_stream


@zope_task(bind=True, max_retries=5, default_retry_delay=5)
def peticao_autuar_task(self, portal, cod_peticao, portal_url):
    if self.request.retries > 0:
        logging.info(f"[peticao_autuar_task] Retry #{self.request.retries} | cod_peticao={cod_peticao}")

    logging.info(f"[peticao_autuar_task] Iniciando task para petição {cod_peticao}")
    skins = portal.portal_skins.sk_sagl

    try:
        for peticao in skins.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
            cod_validacao_doc = ''
            nom_autor = None
            outros = ''
            arq_data = None

            for validacao in skins.zsql.assinatura_documento_obter_zsql(
                tipo_doc='peticao',
                codigo=peticao.cod_peticao,
                ind_assinado=1
            ):
                nom_pdf_peticao = f"{validacao.cod_assinatura_doc}.pdf"
                cod_validacao_doc = str(skins.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))

                if hasattr(portal.sapl_documentos.documentos_assinados, nom_pdf_peticao):
                    arq_data = getattr(portal.sapl_documentos.documentos_assinados, nom_pdf_peticao).data
                else:
                    raise FileNotFoundError(f"Arquivo assinado {nom_pdf_peticao} não encontrado em documentos_assinados.")

                repaired_pypdf_stream = reparar_pdf_stream(BytesIO(bytes(arq_data)))

                try:
                    reader = pypdf.PdfReader(repaired_pypdf_stream)
                    fields = reader.get_fields()
                except Exception as e:
                    logging.error(f"Erro ao abrir PDF com pypdf após reparo: {e!r}")
                    raise

                signers = []
                if fields:
                    signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
                    if signature_field_values:
                        repaired_pypdf_stream.seek(0)
                        signers = get_signatures(repaired_pypdf_stream)

                if signers:
                    nom_autor = signers[0].get('signer_name')
                    qtde_assinaturas = len(signers)
                    outros = " e outro" if qtde_assinaturas == 2 else " e outros" if qtde_assinaturas > 2 else ""
                break
            else:
                nom_pdf_peticao = f"{cod_peticao}.pdf"
                if hasattr(portal.sapl_documentos.peticao, nom_pdf_peticao):
                    arq_data = getattr(portal.sapl_documentos.peticao, nom_pdf_peticao).data
                else:
                    raise FileNotFoundError(f"Arquivo da petição {nom_pdf_peticao} não encontrado.")
                for usuario in skins.zsql.usuario_obter_zsql(cod_usuario=peticao.cod_usuario):
                    nom_autor = usuario.nom_completo

            if not arq_data:
                raise ValueError("Arquivo da petição está vazio.")

        info_protocolo = f"- Recebido em {peticao.dat_recebimento}."
        texto = ''
        storage_path = None
        caminho = ''
        nom_pdf_saida = ''

        if peticao.ind_doc_adm == "1":
            for documento in skins.zsql.documento_administrativo_obter_zsql(cod_documento=peticao.cod_documento):
                for protocolo in skins.zsql.protocolo_obter_zsql(num_protocolo=documento.num_protocolo, ano_protocolo=documento.ano_documento):
                    info_protocolo = f" - Prot. nº {protocolo.num_protocolo}/{protocolo.ano_protocolo} {DateTime(protocolo.dat_protocolo).strftime('%d/%m/%Y')} {protocolo.hor_protocolo}."
                texto = f"{documento.des_tipo_documento} nº {documento.num_documento}/{documento.ano_documento}"
                storage_path = portal.sapl_documentos.administrativo
                nom_pdf_saida = f"{documento.cod_documento}_texto_integral.pdf"
                caminho = '/sapl_documentos/administrativo/'

        elif peticao.ind_doc_materia == "1":
            for documento in skins.zsql.documento_acessorio_obter_zsql(cod_documento=peticao.cod_doc_acessorio):
                for materia in skins.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                    id_materia = f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica}"
                texto = f"{documento.des_tipo_documento} - {id_materia}"
                storage_path = portal.sapl_documentos.materia
                nom_pdf_saida = f"{documento.cod_documento}.pdf"
                caminho = '/sapl_documentos/materia/'

        elif peticao.ind_norma == "1":
            for norma in skins.zsql.norma_juridica_obter_zsql(cod_norma=peticao.cod_norma):
                texto = f"{norma.des_tipo_norma} nº {norma.num_norma}/{norma.ano_norma}"
                storage_path = portal.sapl_documentos.norma_juridica
                nom_pdf_saida = f"{norma.cod_norma}_texto_integral.pdf"
                caminho = '/sapl_documentos/norma_juridica/'

        repaired_stream = reparar_pdf_stream(BytesIO(bytes(arq_data)))

        try:
            existing_pdf = pymupdf.open(stream=repaired_stream)
        except Exception as e:
            logging.critical(f"Erro ao abrir PDF com PyMuPDF após reparo: {e!r}")
            raise

        if cod_validacao_doc:
            stream_qr = make_qrcode(f"{portal_url}/conferir_assinatura_proc?txt_codigo_verificacao={cod_validacao_doc}")
            mensagem1 = f"Esta é uma cópia do original assinado digitalmente por {nom_autor}{outros}"
            mensagem2 = f"Para validar visite {portal_url}/conferir_assinatura e informe o código {cod_validacao_doc}."
            install_home = os.environ.get('INSTALL_HOME')
            if not install_home:
                raise EnvironmentError("Variável INSTALL_HOME não definida.")
            logo_path = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png')
            if not os.path.isfile(logo_path):
                raise FileNotFoundError(f"Logo ICP não encontrado: {logo_path}")
            with open(logo_path, "rb") as arq:
                image = arq.read()
        else:
            stream_qr = make_qrcode(f"{portal_url}{caminho}{nom_pdf_saida}")
            mensagem1 = f"Documento assinado digitalmente com usuário e senha por {nom_autor}"
            mensagem2 = "Para verificar a autenticidade do documento leia o QR code."
            image = None

        for i, page in enumerate(existing_pdf.pages()):
            w, h = page.rect.width, page.rect.height
            is_landscape = w > h
            texto_rodape = f"Pág. {i+1}/{existing_pdf.page_count} - {texto} {info_protocolo} {mensagem1}"
            if is_landscape:
                page.insert_textbox(pymupdf.Rect(65, h - 22, w - 65, h - 5), texto_rodape, fontsize=8, fontname="helv", align=pymupdf.TEXT_ALIGN_LEFT)
                page.insert_image(pymupdf.Rect(10, h - 55, 60, h - 5), stream=stream_qr)
                if image:
                    page.insert_image(pymupdf.Rect(w - 53, h - 38, w - 8, h + 7), stream=image)
                shape = page.new_shape()
                shape.insert_text(pymupdf.Point(w - 13, h - 45), mensagem2, fontname="helv", fontsize=8, rotate=90)
                shape.commit()
            else:
                page.insert_text((w - 13, h - 30), texto_rodape, fontsize=8, rotate=90)
                page.insert_image(pymupdf.Rect(10, h - 55, 60, h - 5), stream=stream_qr)
                if image:
                    page.insert_image(pymupdf.Rect(w - 53, h - 38, w - 8, h + 7), stream=image)
                shape = page.new_shape()
                shape.draw_circle(pymupdf.Point(60, h - 12), 1)
                shape.insert_text(pymupdf.Point(60, h - 12), mensagem2, fontname="helv", fontsize=8)
                shape.commit()

        if peticao.ind_doc_adm == "1":
            rect = pymupdf.Rect(40, 120, w - 20, 170)
            existing_pdf[0].insert_textbox(rect, texto.upper(), fontname="hebo", fontsize=12, align=pymupdf.TEXT_ALIGN_CENTER)

        existing_pdf.set_metadata({"title": texto, "author": nom_autor})
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        existing_pdf.close()

        if nom_pdf_saida in storage_path.objectIds():
            arquivo_peticao = storage_path[nom_pdf_saida]
            arquivo_peticao.update_data(content)
        else:
            storage_path.manage_addFile(id=nom_pdf_saida, file=content, title=texto)
            arquivo_peticao = storage_path[nom_pdf_saida]

        arquivo_peticao.manage_permission('View', roles=['Manager', 'Authenticated'], acquire=0)
        if peticao.ind_norma == "1":
            arquivo_peticao.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
            portal.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(cod_norma=peticao.cod_norma)

        return nom_pdf_saida

    except Exception as e:
        logging.error(f"[peticao_autuar_task] Erro na tentativa {self.request.retries + 1} para cod_peticao={cod_peticao}: {e}", exc_info=True)
        raise self.retry(exc=e)
