from .utils import zope_task, make_qrcode, get_signatures, parse_signatures
from io import BytesIO
import os
import pypdf
import pymupdf
import pikepdf
from datetime import datetime
import logging
from DateTime import DateTime

logger = logging.getLogger(__name__)

def reparar_pdf_stream(file_stream: BytesIO) -> BytesIO:
    """Repairs a potentially corrupted PDF stream using two approaches:
    1. First tries to clean with pikepdf
    2. Falls back to rasterization if needed
    Returns a new BytesIO stream with the repaired PDF data.
    """
    file_stream.seek(0)
    original_data = file_stream.read()

    try:
        # Primary method: repair with pikepdf
        buffer = BytesIO()
        with pikepdf.open(BytesIO(original_data)) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(buffer, linearize=True)
        repaired_data = buffer.getvalue()

        # Validate with pymupdf after pikepdf repair
        doc_validation = pymupdf.open(stream=repaired_data, filetype="pdf")
        doc_validation.close() # Explicitly close the document
        logger.info("PDF successfully repaired using pikepdf.")
        return BytesIO(repaired_data)

    except Exception as e:
        logger.warning(f"PDF repair with pikepdf failed ({e!r}), falling back to rasterization.")

    try:
        # Fallback method: rasterize with pymupdf (Fitz)
        doc = pymupdf.open(stream=original_data, filetype="pdf")
        novo = pymupdf.open()
        for page in doc:
            # Increased DPI for potentially better quality of rasterized images
            pix = page.get_pixmap(dpi=200)
            # Using PNG for lossless quality, JPEG can introduce artifacts
            img = pix.tobytes("png")
            rect = pymupdf.Rect(0, 0, pix.width, pix.height)
            nova = novo.new_page(width=pix.width, height=pix.height)
            nova.insert_image(rect, stream=img)

        out = BytesIO()
        novo.save(out, garbage=4, deflate=True) # Ensure optimization
        novo.close() # Close the document to release resources
        logger.info("PDF successfully repaired using rasterization.")
        out.seek(0) # Reset stream position for reading
        return out
    except Exception as e:
        logger.error(f"PDF repair by rasterization also failed: {e!r}. Returning original stream (may be corrupted).")
        # If both repair attempts fail, return the original stream and let subsequent steps handle it or fail.
        file_stream.seek(0)
        return file_stream

@zope_task()
def peticao_autuar_task(portal, cod_peticao, portal_url):
    skins = portal.portal_skins.sk_sagl
    for peticao in skins.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
        cod_validacao_doc = ''
        nom_autor = None
        outros = ''
        arq_data = None # Initialize arq_data

        for validacao in skins.zsql.assinatura_documento_obter_zsql(tipo_doc='peticao', codigo=peticao.cod_peticao, ind_assinado=1):
            nom_pdf_peticao = str(validacao.cod_assinatura_doc) + ".pdf"
            pdf_peticao_url = portal.sapl_documentos.documentos_assinados.absolute_url() + "/" + nom_pdf_peticao
            cod_validacao_doc = str(skins.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
            arq_data = getattr(portal.sapl_documentos.documentos_assinados, nom_pdf_peticao).data # Get the raw data

            # Always attempt repair for pypdf, as original might still be problematic
            repaired_pypdf_stream = reparar_pdf_stream(BytesIO(bytes(arq_data)))
            try:
                reader = pypdf.PdfReader(repaired_pypdf_stream)
                fields = reader.get_fields()
            except Exception as e:
                logger.error(f"pypdf failed to read repaired PDF: {e!r}. This indicates a critical problem.")
                raise # Re-raise if pypdf cannot read even after repair

            signers = []
            nom_autor = None
            if fields is not None:
                signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
                if signature_field_values is not None:
                    repaired_pypdf_stream.seek(0) # Reset stream position for get_signatures
                    signers = get_signatures(repaired_pypdf_stream)

            qtde_assinaturas = len(signers)
            for signer in signers:
                nom_autor = signer['signer_name']

            outros = ''
            if qtde_assinaturas == 2:
                outros = " e outro"
            if qtde_assinaturas > 2:
                outros = " e outros"
            break # Exit the loop after finding the first signed document
        else:
            # This block executes if the loop completes without 'break' (no signed document found)
            nom_pdf_peticao = str(cod_peticao) + ".pdf"
            pdf_peticao_url = portal.sapl_documentos.peticao.absolute_url() + "/" + nom_pdf_peticao
            for usuario in skins.zsql.usuario_obter_zsql(cod_usuario=peticao.cod_usuario):
                nom_autor = usuario.nom_completo
            # In this 'else' branch, arq_data needs to be defined
            arq_data = getattr(portal.sapl_documentos.peticao, nom_pdf_peticao).data


        info_protocolo = '- Recebido em ' + peticao.dat_recebimento + '.'
        tipo_tipo_peticionamento = peticao.des_tipo_peticionamento

        if peticao.ind_doc_adm == "1":
            for documento in skins.zsql.documento_administrativo_obter_zsql(cod_documento=peticao.cod_documento):
                for protocolo in skins.zsql.protocolo_obter_zsql(num_protocolo=documento.num_protocolo, ano_protocolo=documento.ano_documento):
                    info_protocolo = ' - Prot. nº ' + str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo) + ' ' + str(DateTime(protocolo.dat_protocolo, datefmt='international').strftime('%d/%m/%Y')) + ' ' + protocolo.hor_protocolo + '.'
                texto = str(documento.des_tipo_documento) + ' nº ' + str(documento.num_documento) + '/' + str(documento.ano_documento)
                storage_path = portal.sapl_documentos.administrativo
                nom_pdf_saida = str(documento.cod_documento) + "_texto_integral.pdf"
                caminho = '/sapl_documentos/administrativo/'

        elif peticao.ind_doc_materia == "1":
            for documento in skins.zsql.documento_acessorio_obter_zsql(cod_documento=peticao.cod_doc_acessorio):
                id_materia = ''
                for materia in skins.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                    id_materia = materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                texto = str(documento.des_tipo_documento) + ' - ' + id_materia
                storage_path = portal.sapl_documentos.materia
                nom_pdf_saida = str(documento.cod_documento) + ".pdf"
                caminho = '/sapl_documentos/materia/'

        elif peticao.ind_norma == "1":
            storage_path = portal.sapl_documentos.norma_juridica
            for norma in skins.zsql.norma_juridica_obter_zsql(cod_norma=peticao.cod_norma):
                info_protocolo = '- Recebida em ' + peticao.dat_recebimento + '.'
                texto = str(norma.des_tipo_norma) + ' nº ' + str(norma.num_norma) + '/' + str(norma.ano_norma)
                nom_pdf_saida = str(norma.cod_norma) + "_texto_integral.pdf"
                caminho = '/sapl_documentos/norma_juridica/'

    # Load the PDF data. ALWAYS force a repair to ensure a clean base,
    # especially since we're seeing issues on write after modification.
    # arq_data should now be guaranteed to be set from one of the branches above.
    initial_pdf_bytes = bytes(arq_data)
    repaired_pdf_stream_for_pymupdf = reparar_pdf_stream(BytesIO(initial_pdf_bytes))

    try:
        # Use the repaired stream to open with pymupdf
        existing_pdf = pymupdf.open(stream=repaired_pdf_stream_for_pymupdf)
        logger.info("PDF opened with pymupdf (using potentially repaired stream for modifications).")
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to open PDF with pymupdf even after repair attempts: {e!r}. Task will fail.")
        raise # Re-raise if even the repaired stream can't be opened by pymupdf

    if cod_validacao_doc != '':
        # Use the potentially repaired 'existing_pdf' for QR code and messages
        stream = make_qrcode(text=portal_url+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(cod_validacao_doc))
        mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
        mensagem2 = 'Para validar visite ' + portal_url+'/conferir_assinatura'+' e informe o código '+ cod_validacao_doc + '.'
    else:
        stream = make_qrcode(text=portal_url + str(caminho) + str(nom_pdf_saida))
        mensagem1 = 'Documento assinado digitalmente com usuário e senha por ' + nom_autor
        mensagem2 = 'Para verificar a autenticidade do documento leia o qrcode.'

    numPages = existing_pdf.page_count
    install_home = os.environ.get('INSTALL_HOME')
    dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png')

    with open(dirpath, "rb") as arq:
        image = arq.read()

    for page_index, i in enumerate(range(len(existing_pdf))):
        w = existing_pdf[page_index].rect.width
        h = existing_pdf[page_index].rect.height
        margin = 5
        left = 10 - margin
        bottom = h - 50 - margin
        bottom2 = h - 38
        right = w - 53

        # qrcode
        rect = pymupdf.Rect(left, bottom, left + 50, bottom + 50)
        existing_pdf[page_index].insert_image(rect, stream=stream)
        text2 = mensagem2

        # logo icp
        if cod_validacao_doc != '':
            rect_icp = pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45)
            existing_pdf[page_index].insert_image(rect_icp, stream=image)

        # margem direita
        numero = "Pág. %s/%s" % (i+1, numPages)
        text3 = numero + ' - ' + texto + info_protocolo + ' ' + mensagem1
        x = w - 8 - margin
        y = h - 50 - margin
        existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)

        # margem inferior
        p1 = pymupdf.Point(w - 40 - margin, h - 12)
        p2 = pymupdf.Point(60, h - 12)
        shape = existing_pdf[page_index].new_shape()
        shape.draw_circle(p1,1)
        shape.draw_circle(p2,1)
        shape.insert_text(p2, text2, fontname="helv", fontsize=8, rotate=0)
        shape.commit()

    w = existing_pdf[0].rect.width
    h = existing_pdf[0].rect.height

    if peticao.ind_doc_adm == '1':
        rect = pymupdf.Rect(40, 120, w-20, 170)
        existing_pdf[0].insert_textbox(rect, str(texto).upper(), fontname="hebo", fontsize=12, align=pymupdf.TEXT_ALIGN_CENTER)

    metadata = {"title": texto, "author": nom_autor}
    existing_pdf.set_metadata(metadata)

    # This is where the original error occurred.
    # By ensuring 'existing_pdf' is always a valid PyMuPDF document (either original or repaired),
    # this step should now be successful.
    try:
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        existing_pdf.close() # Explicitly close the document after converting to bytes
        logger.info("Modified PDF successfully converted to bytes.")
    except Exception as e:
        logger.error(f"Failed to convert existing_pdf to bytes AFTER modification: {e!r}. This indicates a severe issue with the PDF data or PyMuPDF operation.")
        raise # Re-raise to ensure Celery marks the task as failed

    if nom_pdf_saida in storage_path:
        arq = storage_path[nom_pdf_saida]
        arq.update_data(content)
        arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
    else:
        storage_path.manage_addFile(id=nom_pdf_saida, file=content, title=texto)
        arq = storage_path[nom_pdf_saida]
        arq.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    if peticao.ind_norma == "1":
        arq = storage_path[nom_pdf_saida]
        arq.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
        portal.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(cod_norma=peticao.cod_norma)
