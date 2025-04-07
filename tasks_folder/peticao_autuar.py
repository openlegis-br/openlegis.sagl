from .utils import zope_task, make_qrcode, get_signatures, parse_signatures
from io import BytesIO
import os
import pypdf
import pymupdf
from datetime import datetime
import logging
from DateTime import DateTime  # Import DateTime

@zope_task()
def peticao_autuar_task(portal, cod_peticao, portal_url):
    skins = portal.portal_skins.sk_sagl
    for peticao in skins.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
        cod_validacao_doc = ''
        nom_autor = None
        outros = ''
        file_data = None  # Inicializar file_data
        qrcode_stream = None  # Inicializar qrcode_stream
        caminho = '/sapl_documentos/peticao/'  # Assign a default value to caminho
        nom_pdf_saida = str(cod_peticao) + ".pdf" # Assign a default value to nom_pdf_saida

        for validacao in skins.zsql.assinatura_documento_obter_zsql(
            tipo_doc='peticao',
            codigo=peticao.cod_peticao,
            ind_assinado=1
        ):
            nom_pdf_peticao = str(validacao.cod_assinatura_doc) + ".pdf"
            pdf_peticao = (
                portal.sapl_documentos.documentos_assinados.absolute_url()
                + "/"
                + nom_pdf_peticao
            )
            cod_validacao_doc = str(
                skins.cadastros.assinatura.format_verification_code(
                    code=validacao.cod_assinatura_doc
                )
            )

            try:
                arq = getattr(
                    portal.sapl_documentos.documentos_assinados, nom_pdf_peticao
                )
                file_data = BytesIO(bytes(arq.data))  # Obter dados do arquivo
            except AttributeError:
                logging.error(f"Arquivo não encontrado: {nom_pdf_peticao}")
                continue  # Pular para a próxima iteração se o arquivo não existir

            # Gerar QR code para documento assinado
            qrcode_stream = make_qrcode(
                text=portal_url
                + '/conferir_assinatura_proc?txt_codigo_verificacao='
                + str(cod_validacao_doc)
            )

            reader = pypdf.PdfReader(file_data)
            fields = reader.get_fields()
            signers = []
            nom_autor = None
            if fields:
                signature_field_values = [
                    f.value for f in fields.values() if f.field_type == '/Sig'
                ]
                if signature_field_values:
                    signers = get_signatures(file_data)
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
            pdf_peticao = (
                portal.sapl_documentos.peticao.absolute_url() + "/" + nom_pdf_peticao
            )
            for usuario in skins.zsql.usuario_obter_zsql(
                cod_usuario=peticao.cod_usuario
            ):
                nom_autor = usuario.nom_completo

            try:
                arq = getattr(portal.sapl_documentos.peticao, nom_pdf_peticao)
                file_data = BytesIO(bytes(arq.data))  # Obter dados do arquivo
            except AttributeError:
                logging.error(f"Arquivo não encontrado: {nom_pdf_peticao}")
                continue  # Pular para a próxima iteração se o arquivo não existir

            # Gerar QR code para documento não assinado
            qrcode_stream = make_qrcode(
                text=portal_url + str(caminho) + str(nom_pdf_saida)
            )

        info_protocolo = '- Recebido em ' + str(peticao.dat_recebimento) + '.'
        tipo_tipo_peticionamento = peticao.des_tipo_peticionamento
        if peticao.ind_doc_adm == "1":
            for documento in skins.zsql.documento_administrativo_obter_zsql(
                cod_documento=peticao.cod_documento
            ):
                for protocolo in skins.zsql.protocolo_obter_zsql(
                    num_protocolo=documento.num_protocolo,
                    ano_protocolo=documento.ano_documento,
                ):
                    info_protocolo = (
                        ' - Prot. nº '
                        + str(protocolo.num_protocolo)
                        + '/'
                        + str(protocolo.ano_protocolo)
                        + ' '
                        + str(
                            DateTime(
                                protocolo.dat_protocolo, datefmt='international'
                            ).strftime('%d/%m/%Y')
                        )
                        + ' '
                        + protocolo.hor_protocolo
                        + '.'
                    )
                    texto = (
                        str(documento.des_tipo_documento)
                        + ' nº '
                        + str(documento.num_documento)
                        + '/'
                        + str(documento.ano_documento)
                    )
                    storage_path = portal.sapl_documentos.administrativo
                    nom_pdf_saida = str(documento.cod_documento) + "_texto_integral.pdf"
                    caminho = '/sapl_documentos/administrativo/'
        elif peticao.ind_doc_materia == "1":
            for documento in skins.zsql.documento_acessorio_obter_zsql(
                cod_documento=peticao.cod_doc_acessorio
            ):
                id_materia = ''
                for materia in self.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                    id_materia = materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                texto = str(documento.des_tipo_documento) + ' - ' + id_materia
                storage_path = portal.sapl_documentos.materia
                nom_pdf_saida = str(documento.cod_documento) + ".pdf"
                caminho = '/sapl_documentos/materia/'
        elif peticao.ind_norma == "1":
            storage_path = portal.sapl_documentos.norma_juridica
            for norma in skins.zsql.norma_juridica_obter_zsql(
                cod_norma=peticao.cod_norma
            ):
                info_protocolo = '- Recebida em ' + str(peticao.dat_recebimento) + '.'
                texto = (
                    str(norma.des_tipo_norma)
                    + ' nº '
                    + str(norma.num_norma)
                    + '/'
                    + str(norma.ano_norma)
                )
                nom_pdf_saida = str(norma.cod_norma) + "_texto_integral.pdf"
                caminho = '/sapl_documentos/norma_juridica/'

        if cod_validacao_doc != '':
            mensagem1 = (
                'Esta é uma cópia do original assinado digitalmente por '
                + str(nom_autor)
                + str(outros)
            )
            mensagem2 = (
                'Para validar visite '
                + portal_url
                + '/conferir_assinatura'
                + ' e informe o código '
                + str(cod_validacao_doc)
            )
        else:
            mensagem1 = (
                'Documento assinado digitalmente com usuário e senha por ' + str(nom_autor)
            )
            mensagem2 = 'Para verificar a autenticidade do documento leia o qrcode.'

        if file_data:
            arquivo = file_data  # Usar file_data
            existing_pdf = pymupdf.open(stream=arquivo)
            numPages = existing_pdf.page_count
            install_home = os.environ.get('INSTALL_HOME')
            dirpath = os.path.join(
                install_home,
                'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png',
            )
            try:
                with open(dirpath, "rb") as arq:
                    image = arq.read()
            except FileNotFoundError:
                logging.error(f"Imagem não encontrada: {dirpath}")
                image = None  # Handle case where image is not found

            if qrcode_stream is None:
                # Fallback QR code generation if it's still None
                qrcode_stream = make_qrcode(text=portal_url + str(caminho) + str(nom_pdf_saida))

            for page_index, i in enumerate(range(len(existing_pdf))):
                w = existing_pdf[page_index].rect.width
                h = existing_pdf[page_index].rect.height
                margin = 5
                left = 10 - margin
                bottom = h - 50 - margin
                bottom2 = h - 38
                right = w - 53
                black = pymupdf.pdfcolor["black"]
                # qrcode
                rect = pymupdf.Rect(
                    left, bottom, left + 50, bottom + 50
                )  # qrcode bottom left square
                existing_pdf[page_index].insert_image(
                    rect, stream=qrcode_stream
                )  # Usar qrcode_stream
                text2 = mensagem2
                # logo icp
                if cod_validacao_doc != '' and image:
                    rect_icp = pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45)
                    existing_pdf[page_index].insert_image(rect_icp, stream=image)
                # margem direita
                numero = "Pág. %s/%s" % (i + 1, numPages)
                text3 = numero + ' - ' + str(texto) + str(info_protocolo) + ' ' + str(mensagem1)
                x = w - 8 - margin  # largura
                y = h - 50 - margin  # altura
                existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)
                # margem inferior
                p1 = pymupdf.Point(w - 40 - margin, h - 12)  # numero de pagina documento
                p2 = pymupdf.Point(60, h - 12)  # margem inferior
                shape = existing_pdf[page_index].new_shape()
                shape.draw_circle(p1, 1)
                shape.draw_circle(p2, 1)
                shape.insert_text(p2, text2, fontname="helv", fontsize=8, rotate=0)
                shape.commit()
            w = existing_pdf[0].rect.width
            h = existing_pdf[0].rect.height
            rect = pymupdf.Rect(40, 140, w - 20, 170)
            existing_pdf[0].insert_textbox(
                rect,
                str(texto).upper(),
                fontname="tibo",
                fontsize=13,
                align=pymupdf.TEXT_ALIGN_CENTER,
            )
            metadata = {"title": texto, "author": nom_autor}
            existing_pdf.set_metadata(metadata)
            content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
            if nom_pdf_saida in storage_path:
                arq = storage_path[nom_pdf_saida]
                arq.manage_upload(file=content)
                arq.manage_permission(
                    'View', roles=['Manager', 'Authenticated'], acquire=0
                )
            else:
                storage_path.manage_addFile(id=nom_pdf_saida, file=content, title=texto)
                arq = storage_path[nom_pdf_saida]
                arq.manage_permission(
                    'View', roles=['Manager', 'Authenticated'], acquire=0
                )
            if peticao.ind_norma == "1":
                arq = storage_path[nom_pdf_saida]
                arq.manage_permission(
                    'View', roles=['Manager', 'Anonymous'], acquire=1
                )
                portal.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(
                    cod_norma=peticao.cod_norma
                )
