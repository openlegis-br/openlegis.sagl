from .utils import zope_task, make_qrcode, get_signatures, parse_signatures
from io import BytesIO
import os
import pypdf
import pymupdf
import pikepdf
from DateTime import DateTime
import logging

logger = logging.getLogger(__name__)

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
        logger.info("PDF successfully repaired using pikepdf.")
        return BytesIO(repaired_data)
    except Exception as e:
        logger.warning(f"PDF repair with pikepdf failed: {e!r}. Trying rasterization.")

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
        logger.info("PDF repaired via rasterization.")
        out.seek(0)
        return out
    except Exception as e:
        logger.error(f"Rasterization failed: {e!r}. Using original file.")
        file_stream.seek(0)
        return file_stream

@zope_task()
def peticao_autuar_task(portal, cod_peticao, portal_url):
    skins = portal.portal_skins.sk_sagl

    for peticao in skins.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
        cod_validacao_doc = ''
        nom_autor = None
        outros = ''
        arq_data = None

        for validacao in skins.zsql.assinatura_documento_obter_zsql(tipo_doc='peticao', codigo=peticao.cod_peticao, ind_assinado=1):
            nom_pdf_peticao = f"{validacao.cod_assinatura_doc}.pdf"
            pdf_peticao_url = f"{portal.sapl_documentos.documentos_assinados.absolute_url()}/{nom_pdf_peticao}"
            cod_validacao_doc = str(skins.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
            arq_data = getattr(portal.sapl_documentos.documentos_assinados, nom_pdf_peticao).data
            repaired_pypdf_stream = reparar_pdf_stream(BytesIO(bytes(arq_data)))

            try:
                reader = pypdf.PdfReader(repaired_pypdf_stream)
                fields = reader.get_fields()
            except Exception as e:
                logger.error(f"Erro ao abrir PDF com pypdf após reparo: {e!r}")
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
            pdf_peticao_url = f"{portal.sapl_documentos.peticao.absolute_url()}/{nom_pdf_peticao}"
            for usuario in skins.zsql.usuario_obter_zsql(cod_usuario=peticao.cod_usuario):
                nom_autor = usuario.nom_completo
            arq_data = getattr(portal.sapl_documentos.peticao, nom_pdf_peticao).data

        if not arq_data:
            raise ValueError("Arquivo da petição não encontrado ou vazio.")

        info_protocolo = f"- Recebido em {peticao.dat_recebimento}."
        texto = ''
        storage_path = None
        caminho = ''
        nom_pdf_saida = ''

        if peticao.ind_doc_adm == "1":
            for documento in skins.zsql.documento_administrativo_obter_zsql(cod_documento=peticao.cod_documento):
                for protocolo in skins.zsql.protocolo_obter_zsql(num_protocolo=documento.num_protocolo, ano_protocolo=documento.ano_documento):
                    info_protocolo = f" - Prot. nº {protocolo.num_protocolo}/{protocolo.ano_protocolo} {DateTime(protocolo.dat_protocolo, datefmt='international').strftime('%d/%m/%Y')} {protocolo.hor_protocolo}."
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

        initial_pdf_bytes = bytes(arq_data)
        repaired_stream = reparar_pdf_stream(BytesIO(initial_pdf_bytes))

        try:
            existing_pdf = pymupdf.open(stream=repaired_stream)
        except Exception as e:
            logger.critical(f"Erro ao abrir PDF com PyMuPDF após reparo: {e!r}")
            raise

        if cod_validacao_doc:
            stream = make_qrcode(f"{portal_url}/conferir_assinatura_proc?txt_codigo_verificacao={cod_validacao_doc}")
            mensagem1 = f"Esta é uma cópia do original assinado digitalmente por {nom_autor}{outros}"
            mensagem2 = f"Para validar visite {portal_url}/conferir_assinatura e informe o código {cod_validacao_doc}."
        else:
            stream = make_qrcode(f"{portal_url}{caminho}{nom_pdf_saida}")
            mensagem1 = f"Documento assinado digitalmente com usuário e senha por {nom_autor}"
            mensagem2 = "Para verificar a autenticidade do documento leia o QR code."

        install_home = os.environ.get('INSTALL_HOME')
        if not install_home:
            raise EnvironmentError("Variável INSTALL_HOME não definida.")
        dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png')
        if not os.path.isfile(dirpath):
            raise FileNotFoundError(f"Logo ICP não encontrado: {dirpath}")

        with open(dirpath, "rb") as arq:
            image = arq.read()

        for i, page in enumerate(existing_pdf.pages()):
            w, h = page.rect.width, page.rect.height
            margin = 5
            left, bottom = 10 - margin, h - 50 - margin
            bottom2 = h - 38
            right = w - 53
            page.insert_image(pymupdf.Rect(left, bottom, left + 50, bottom + 50), stream=stream)
            if cod_validacao_doc:
                page.insert_image(pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45), stream=image)
            numero = f"Pág. {i+1}/{existing_pdf.page_count}"
            text3 = f"{numero} - {texto} {info_protocolo} {mensagem1}"
            page.insert_text((w - 8 - margin, h - 50 - margin), text3, fontsize=8, rotate=90)
            shape = page.new_shape()
            shape.draw_circle(pymupdf.Point(w - 40 - margin, h - 12), 1)
            shape.draw_circle(pymupdf.Point(60, h - 12), 1)
            shape.insert_text(pymupdf.Point(60, h - 12), mensagem2, fontname="helv", fontsize=8)
            shape.commit()

        if peticao.ind_doc_adm == "1":
            rect = pymupdf.Rect(40, 120, w - 20, 170)
            existing_pdf[0].insert_textbox(rect, texto.upper(), fontname="hebo", fontsize=12, align=pymupdf.TEXT_ALIGN_CENTER)

        existing_pdf.set_metadata({"title": texto, "author": nom_autor})

        try:
            content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
            existing_pdf.close()
        except Exception as e:
            logger.error(f"Erro ao salvar PDF com PyMuPDF: {e!r}")
            raise

        if nom_pdf_saida in storage_path:
            arquivo_peticao = storage_path[nom_pdf_saida]
            arquivo_peticao.update_data(content)
        else:
            storage_path.manage_addFile(id=nom_pdf_saida, file=content, title=texto)
            arquivo_peticao = storage_path[nom_pdf_saida]

        # Permissões
        arquivo_peticao.manage_permission('View', roles=['Manager', 'Authenticated'], acquire=0)
        if peticao.ind_norma == "1":
            arquivo_peticao.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
            portal.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(cod_norma=peticao.cod_norma)
