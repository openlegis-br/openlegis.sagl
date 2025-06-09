from .utils import zope_task, make_qrcode, get_signatures
from io import BytesIO
import os
import pypdf
import pymupdf
from datetime import datetime
import logging
from DateTime import DateTime
import pikepdf

logger = logging.getLogger(__name__)

@zope_task()
def peticao_autuar_task(portal, cod_peticao, portal_url):
    def reparar_pdf_stream(file_stream: BytesIO) -> BytesIO:
        file_stream.seek(0)
        original = file_stream.read()
        try:
            buffer = BytesIO()
            with pikepdf.open(BytesIO(original)) as pdf:
                pdf.remove_unreferenced_resources()
                pdf.save(buffer, linearize=True)
            reparado = buffer.getvalue()
            pymupdf.open(stream=reparado, filetype="pdf")  # valida
            return BytesIO(reparado)
        except Exception as e:
            logger.warning(f"Falha ao reparar PDF com pikepdf: {e}")
            doc = pymupdf.open(stream=original, filetype="pdf")
            novo = pymupdf.open()
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = pix.tobytes("jpeg", 90)
                rect = pymupdf.Rect(0, 0, pix.width, pix.height)
                nova = novo.new_page(width=float(pix.width), height=float(pix.height))
                nova.insert_image(rect, stream=img)
            novo.set_metadata(doc.metadata)
            out = BytesIO()
            novo.save(out, garbage=4, deflate=True)
            return out

    skins = portal.portal_skins.sk_sagl
    for peticao in skins.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
        cod_validacao_doc = ''
        nom_autor = None
        outros = ''
        for validacao in skins.zsql.assinatura_documento_obter_zsql(tipo_doc='peticao', codigo=peticao.cod_peticao, ind_assinado=1):
            nom_pdf_peticao = str(validacao.cod_assinatura_doc) + ".pdf"
            pdf_peticao = portal.sapl_documentos.documentos_assinados.absolute_url() + "/" + nom_pdf_peticao
            cod_validacao_doc = str(skins.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
            arq = getattr(portal.sapl_documentos.documentos_assinados, nom_pdf_peticao)
            fileStream = reparar_pdf_stream(BytesIO(arq.data))
            fileStream.seek(0)
            reader = pypdf.PdfReader(fileStream)
            fields = reader.get_fields()
            signers = []
            nom_autor = None
            if fields:
                sig_fields = [f for f in fields.values() if f.field_type == '/Sig']
                if sig_fields:
                    fileStream.seek(0)
                    signers = get_signatures(fileStream)
            qtde_assinaturas = len(signers)
            for signer in signers:
                nom_autor = signer['signer_name']
            outros = ''
            if qtde_assinaturas == 2:
                outros = " e outro"
            if qtde_assinaturas > 2:
                outros = " e outros"
            break
        else:
            nom_pdf_peticao = str(cod_peticao) + ".pdf"
            pdf_peticao = portal.sapl_documentos.peticao.absolute_url() + "/" + nom_pdf_peticao
            for usuario in skins.zsql.usuario_obter_zsql(cod_usuario=peticao.cod_usuario):
                nom_autor = usuario.nom_completo

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

    if cod_validacao_doc != '':
        arq = getattr(portal.sapl_documentos.documentos_assinados, nom_pdf_peticao)
        stream = make_qrcode(text=portal_url + '/conferir_assinatura_proc?txt_codigo_verificacao=' + str(cod_validacao_doc))
        mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
        mensagem2 = 'Para validar visite ' + portal_url + '/conferir_assinatura e informe o código ' + cod_validacao_doc + '.'
    else:
        arq = getattr(portal.sapl_documentos.peticao, nom_pdf_peticao)
        stream = make_qrcode(text=portal_url + str(caminho) + str(nom_pdf_saida))
        mensagem1 = 'Documento assinado digitalmente com usuário e senha por ' + nom_autor
        mensagem2 = 'Para verificar a autenticidade do documento leia o qrcode.'

    arquivo = BytesIO(arq.data)
    existing_pdf = pymupdf.open(stream=arquivo)
    numPages = existing_pdf.page_count
    install_home = os.environ.get('INSTALL_HOME')
    dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png')
    with open(dirpath, "rb") as arq:
        image = arq.read()

    for page_index, i in enumerate(range(numPages)):
        w = existing_pdf[page_index].rect.width
        h = existing_pdf[page_index].rect.height
        margin = 5
        left = 10 - margin
        bottom = h - 50 - margin
        bottom2 = h - 38
        right = w - 53

        # QR Code
        rect = pymupdf.Rect(left, bottom, left + 50, bottom + 50)
        existing_pdf[page_index].insert_image(rect, stream=stream)

        # ICP Logo
        if cod_validacao_doc != '':
            rect_icp = pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45)
            existing_pdf[page_index].insert_image(rect_icp, stream=image)

        # Texto lateral
        numero = "Pág. %s/%s" % (i + 1, numPages)
        text3 = numero + ' - ' + texto + info_protocolo + ' ' + mensagem1
        x = w - 8 - margin
        y = h - 50 - margin
        existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)

        # Texto inferior
        p1 = pymupdf.Point(w - 40 - margin, h - 12)
        p2 = pymupdf.Point(60, h - 12)
        shape = existing_pdf[page_index].new_shape()
        shape.draw_circle(p1, 1)
        shape.draw_circle(p2, 1)
        shape.insert_text(p2, mensagem2, fontname="helv", fontsize=8, rotate=0)
        shape.commit()

    if peticao.ind_doc_adm == '1':
        w = existing_pdf[0].rect.width
        rect = pymupdf.Rect(40, 120, w - 20, 170)
        existing_pdf[0].insert_textbox(rect, str(texto).upper(), fontname="helv", fontsize=12, align=pymupdf.TEXT_ALIGN_CENTER)

    existing_pdf.set_metadata({"title": texto, "author": nom_autor})
    content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)

    arq_existente = storage_path._getOb(nom_pdf_saida, None)
    if arq_existente:
        arq_existente.update_data(content)
        arq_existente.manage_permission('View', roles=['Manager', 'Authenticated'], acquire=0)
    else:
        storage_path.manage_addFile(id=nom_pdf_saida, file=content, title=texto)
        storage_path[nom_pdf_saida].manage_permission('View', roles=['Manager', 'Authenticated'], acquire=0)

    if peticao.ind_norma == "1":
        storage_path[nom_pdf_saida].manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
        portal.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(cod_norma=peticao.cod_norma)
