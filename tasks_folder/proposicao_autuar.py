from .utils import zope_task, make_qrcode, get_signatures, parse_signatures
from io import BytesIO
import os
import pypdf
import pymupdf
import pikepdf
from DateTime import DateTime
import logging

@zope_task()
def proposicao_autuar_task(portal, cod_proposicao, portal_url):
    skins = portal.portal_skins.sk_sagl
    nom_pdf_proposicao = str(cod_proposicao) + "_signed.pdf"
    arq = getattr(portal.sapl_documentos.proposicao, nom_pdf_proposicao)
    
    # Trabalhe sempre com BytesIO
    original_stream = BytesIO(bytes(arq.data))
    
    # Reparo antecipado com pikepdf (garante PDF íntegro para manipulação)
    try:
        original_stream.seek(0)
        repaired_stream = BytesIO()
        with pikepdf.open(original_stream) as pdf:
            pdf.save(repaired_stream)
        logging.info("[PDF] PDF reparado antecipadamente com pikepdf.")
        stream = repaired_stream
    except Exception as e:
        logging.warning(f"[PDF] PDF não pôde ser reparado antecipadamente com pikepdf: {e}")
        original_stream.seek(0)
        stream = original_stream

    # Sempre .seek(0) antes de reutilizar o fluxo
    stream.seek(0)
    reader = pypdf.PdfReader(stream)
    fields = reader.get_fields()
    signers = []
    nom_autor = None
    if fields is not None:
        signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
        if signature_field_values is not None:
            signers = get_signatures(stream)
    qtde_assinaturas = len(signers)
    for signer in signers:
        nom_autor = signer['signer_name']
    outros = ''
    if qtde_assinaturas == 2:
        outros = " e outro"
    if qtde_assinaturas > 2:
        outros = " e outros"
    cod_validacao_doc = ''
    for validacao in skins.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao, tipo_doc='proposicao', ind_assinado=1):
        cod_validacao_doc = str(skins.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
    for proposicao in skins.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao):
        num_proposicao = proposicao.cod_proposicao
        if nom_autor is None:
            nom_autor = proposicao.nom_autor
        info_protocolo = '- Recebido em ' + proposicao.dat_recebimento + '.'
        tipo_proposicao = proposicao.des_tipo_proposicao
        if proposicao.ind_mat_ou_doc == "M":
            for materia in skins.zsql.materia_obter_zsql(cod_materia=proposicao.cod_mat_ou_doc):
                if materia.num_protocolo is not None and materia.num_protocolo != '':
                    for protocolo in skins.zsql.protocolo_obter_zsql(num_protocolo=materia.num_protocolo, ano_protocolo=materia.ano_ident_basica):
                        info_protocolo = ' - Prot. ' + str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo) + ' ' + str(DateTime(protocolo.dat_protocolo, datefmt='international').strftime('%d/%m/%Y')) + ' ' + protocolo.hor_protocolo + '.'
                texto = str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                storage_path = portal.sapl_documentos.materia
                nom_pdf_saida = str(materia.cod_materia) + "_texto_integral.pdf"
        elif proposicao.ind_mat_ou_doc == 'D' and (proposicao.des_tipo_proposicao not in ['Emenda', 'Mensagem Aditiva', 'Substitutivo', 'Parecer', 'Parecer de Comissão']):
            for documento in skins.zsql.documento_acessorio_obter_zsql(cod_documento=proposicao.cod_mat_ou_doc):
                for materia in skins.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                    materia = str(materia.sgl_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                texto = str(documento.des_tipo_documento) + ' - ' + str(materia)
                storage_path = portal.sapl_documentos.materia
                nom_pdf_saida = str(documento.cod_documento) + ".pdf"
        elif proposicao.ind_mat_ou_doc == 'D' and (proposicao.des_tipo_proposicao in ['Emenda', 'Mensagem Aditiva']):
            for emenda in skins.zsql.emenda_obter_zsql(cod_emenda=proposicao.cod_emenda):
                for materia in skins.zsql.materia_obter_zsql(cod_materia=emenda.cod_materia):
                    materia = str(materia.sgl_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                info_protocolo = '- Recebida em ' + proposicao.dat_recebimento + '.'
                texto = 'Emenda ' + str(emenda.des_tipo_emenda) + ' nº ' + str(emenda.num_emenda) + ' ao ' + str(materia)
                storage_path = portal.sapl_documentos.emenda
                nom_pdf_saida = str(emenda.cod_emenda) + "_emenda.pdf"
        elif proposicao.ind_mat_ou_doc == 'D' and (proposicao.des_tipo_proposicao == 'Substitutivo'):
            for substitutivo in skins.zsql.substitutivo_obter_zsql(cod_substitutivo=proposicao.cod_substitutivo):
                for materia in skins.zsql.materia_obter_zsql(cod_materia=substitutivo.cod_materia):
                    materia = str(materia.sgl_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                texto = 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + ' ao ' + str(materia)
                storage_path = portal.sapl_documentos.substitutivo
                nom_pdf_saida = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
        elif proposicao.ind_mat_ou_doc == 'D' and (proposicao.des_tipo_proposicao in ['Parecer', 'Parecer de Comissão']):
            for relatoria in skins.zsql.relatoria_obter_zsql(cod_relatoria=proposicao.cod_parecer, ind_excluido=0):
                for comissao in skins.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao):
                    sgl_comissao = comissao.sgl_comissao
                for materia in skins.zsql.materia_obter_zsql(cod_materia=relatoria.cod_materia):
                    materia = str(materia.sgl_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                texto = 'Parecer ' + sgl_comissao + ' nº ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + ' ao ' + str(materia)
                storage_path = portal.sapl_documentos.parecer_comissao
                nom_pdf_saida = str(relatoria.cod_relatoria) + "_parecer.pdf"

    mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
    mensagem2 = 'Para validar visite ' + portal_url + '/conferir_assinatura' + ' e informe o código ' + cod_validacao_doc

    stream.seek(0)
    existing_pdf = pymupdf.open(stream=stream)
    numPages = existing_pdf.page_count

    install_home = os.environ.get('INSTALL_HOME')
    dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png')
    with open(dirpath, "rb") as arq:
        image = arq.read()

    for validacao in skins.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao, tipo_doc='proposicao', ind_assinado=1):
        stream_qr = make_qrcode(text=portal_url + '/conferir_assinatura_proc?txt_codigo_verificacao=' + str(validacao.cod_assinatura_doc))
        for page_index, i in enumerate(range(len(existing_pdf))):
            w = existing_pdf[page_index].rect.width
            h = existing_pdf[page_index].rect.height
            margin = 5
            left = 10 - margin
            bottom = h - 50 - margin
            bottom2 = h - 38
            right = w - 53
            rect = pymupdf.Rect(left, bottom, left + 50, bottom + 50)
            existing_pdf[page_index].insert_image(rect, stream=stream_qr)
            text2 = mensagem2
            numero = "Pág. %s/%s" % (i + 1, numPages)
            text3 = numero + ' - ' + texto + info_protocolo + ' ' + mensagem1
            x = w - 8 - margin
            y = h - 30 - margin
            existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)
            rect_icp = pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45)
            existing_pdf[page_index].insert_image(rect_icp, stream=image)
            p1 = pymupdf.Point(w - 40 - margin, h - 12)
            p2 = pymupdf.Point(60, h - 12)
            shape = existing_pdf[page_index].new_shape()
            shape.draw_circle(p1, 1)
            shape.draw_circle(p2, 1)
            shape.insert_text(p2, text2, fontname="helv", fontsize=8, rotate=0)
            shape.commit()
        break

    w = existing_pdf[0].rect.width
    h = existing_pdf[0].rect.height
    rect = pymupdf.Rect(40, 120, w - 20, 170)
    existing_pdf[0].insert_textbox(rect, str(texto).upper(), fontname="hebo", fontsize=12, align=pymupdf.TEXT_ALIGN_CENTER)
    metadata = {"title": texto, "author": nom_autor}
    existing_pdf.set_metadata(metadata)

    # Salvamento único e direto
    try:
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
    except Exception as e:
        logging.error(f"[PDF] Erro inesperado ao salvar PDF já reparado: {e}")
        raise e

    if nom_pdf_saida in storage_path:
        pdf = storage_path[nom_pdf_saida]
        pdf.update_data(content)
    else:
        storage_path.manage_addFile(id=nom_pdf_saida, file=content, title=texto)
        pdf = storage_path[nom_pdf_saida]

    pdf.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
    return nom_pdf_saida
