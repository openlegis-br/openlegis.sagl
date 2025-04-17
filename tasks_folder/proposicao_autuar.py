from .utils import zope_task, make_qrcode, get_signatures, parse_signatures
from io import BytesIO
import os
import pypdf
import pymupdf
from datetime import datetime
from DateTime import DateTime
import logging

@zope_task()
def proposicao_autuar_task(portal, cod_proposicao, portal_url):
    skins = portal.portal_skins.sk_sagl
    nom_pdf_proposicao = str(cod_proposicao) + "_signed.pdf"
    arq = getattr(portal.sapl_documentos.proposicao, nom_pdf_proposicao)
    fileStream = BytesIO(bytes(arq.data))
    reader = pypdf.PdfReader(fileStream)
    fields = reader.get_fields()
    signers = []
    nom_autor = None
    if fields != None:
        signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
        if signature_field_values is not None:
           signers = get_signatures(fileStream)
    qtde_assinaturas = len(signers)
    for signer in signers:
        nom_autor = signer['signer_name']
    outros = ''
    if qtde_assinaturas == 2:
       outros = " e outro"
    if qtde_assinaturas > 2:
       outros = " e outros"
    cod_validacao_doc = ''
    for validacao in skins.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao,tipo_doc='proposicao',ind_assinado=1):
        cod_validacao_doc = str(skins.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
    for proposicao in skins.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao):
        num_proposicao = proposicao.cod_proposicao
        if nom_autor == None:
           nom_autor = proposicao.nom_autor
        info_protocolo = '- Recebido em ' + proposicao.dat_recebimento + '.'
        tipo_proposicao = proposicao.des_tipo_proposicao
        if proposicao.ind_mat_ou_doc == "M":
           for materia in skins.zsql.materia_obter_zsql(cod_materia=proposicao.cod_mat_ou_doc):
               if materia.num_protocolo != None and materia.num_protocolo != '':
                  for protocolo in skins.zsql.protocolo_obter_zsql(num_protocolo=materia.num_protocolo, ano_protocolo=materia.ano_ident_basica):
                      info_protocolo = ' - Prot. ' + str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo) + ' ' + str(DateTime(protocolo.dat_protocolo, datefmt='international').strftime('%d/%m/%Y')) + ' ' + protocolo.hor_protocolo + '.'
               texto = str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
               storage_path = portal.sapl_documentos.materia
               nom_pdf_saida = str(materia.cod_materia) + "_texto_integral.pdf"
        elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao!='Emenda' and proposicao.des_tipo_proposicao!='Mensagem Aditiva' and proposicao.des_tipo_proposicao!='Substitutivo' and proposicao.des_tipo_proposicao!='Parecer' and proposicao.des_tipo_proposicao!='Parecer de Comissão'):
           for documento in skins.zsql.documento_acessorio_obter_zsql(cod_documento=proposicao.cod_mat_ou_doc):
               for materia in skins.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
               texto = str(documento.des_tipo_documento) + ' - ' + str(materia)
               storage_path = portal.sapl_documentos.materia
               nom_pdf_saida = str(documento.cod_documento) + ".pdf"
        elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Emenda' or proposicao.des_tipo_proposicao=='Mensagem Aditiva'):
           for emenda in skins.zsql.emenda_obter_zsql(cod_emenda=proposicao.cod_emenda):
               for materia in skins.zsql.materia_obter_zsql(cod_materia=emenda.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
               info_protocolo = '- Recebida em ' + proposicao.dat_recebimento + '.'
               texto = 'Emenda ' + str(emenda.des_tipo_emenda)+ ' nº ' + str(emenda.num_emenda) + ' ao ' + str(materia)
               storage_path = portal.sapl_documentos.emenda
               nom_pdf_saida = str(emenda.cod_emenda) + "_emenda.pdf"
        elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Substitutivo'):
           for substitutivo in skins.zsql.substitutivo_obter_zsql(cod_substitutivo=proposicao.cod_substitutivo):
               for materia in skins.zsql.materia_obter_zsql(cod_materia=substitutivo.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+ ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
               texto = 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + ' ao ' + str(materia)
               storage_path = portal.sapl_documentos.substitutivo
               nom_pdf_saida = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
        elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Parecer' or proposicao.des_tipo_proposicao=='Parecer de Comissão'):
           for relatoria in skins.zsql.relatoria_obter_zsql(cod_relatoria=proposicao.cod_parecer, ind_excluido=0): 
               for comissao in skins.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao):
                   sgl_comissao = comissao.sgl_comissao
               for materia in skins.zsql.materia_obter_zsql(cod_materia=relatoria.cod_materia):
                   materia = str(materia.sgl_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
               texto = 'Parecer ' + sgl_comissao + ' nº ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + ' ao ' + str(materia)
               storage_path = portal.sapl_documentos.parecer_comissao
               nom_pdf_saida = str(relatoria.cod_relatoria) + "_parecer.pdf"
    mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
    mensagem2 = 'Para validar visite ' + portal_url+'/conferir_assinatura'+' e informe o código '+ cod_validacao_doc
    existing_pdf = pymupdf.open(stream=fileStream)
    numPages = existing_pdf.page_count
    doc = pymupdf.open()
    install_home = os.environ.get('INSTALL_HOME')
    dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png')
    with open(dirpath, "rb") as arq:
         image = arq.read()
    for validacao in skins.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao,tipo_doc='proposicao',ind_assinado=1):
        stream = make_qrcode(text=portal_url+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(validacao.cod_assinatura_doc))
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
            rect = pymupdf.Rect(left, bottom, left + 50, bottom + 50)  # qrcode bottom left square
            existing_pdf[page_index].insert_image(rect, stream=stream)
            text2 = mensagem2
            # margem direita
            numero = "Pág. %s/%s" % (i+1, numPages)
            text3 = numero + ' - ' + texto + info_protocolo + ' ' + mensagem1
            x = w - 8 - margin #largura
            y = h - 30 - margin # altura
            existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)
            # logo icp
            rect_icp = pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45)
            existing_pdf[page_index].insert_image(rect_icp, stream=image)
            # margem inferior
            p1 = pymupdf.Point(w - 40 - margin, h - 12) # numero de pagina documento
            p2 = pymupdf.Point(60, h - 12) # margem inferior
            shape = existing_pdf[page_index].new_shape()
            shape.draw_circle(p1,1)
            shape.draw_circle(p2,1)
            shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
            shape.commit()
        break
    w = existing_pdf[0].rect.width
    h = existing_pdf[0].rect.height
    # tipo, numero e ano
    if tipo_proposicao != 'Parecer' and tipo_proposicao != 'Parecer de Comissão':
       rect = pymupdf.Rect(40, 120, w-20, 170)
       existing_pdf[0].insert_textbox(rect, str(texto).upper(), fontname = "hebo", fontsize = 12, align=pymupdf.TEXT_ALIGN_CENTER)
    metadata = {"title": texto, "author": nom_autor}
    existing_pdf.set_metadata(metadata)
    content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
    if nom_pdf_saida in storage_path:
       pdf=storage_path[nom_pdf_saida]
       pdf.update_data(content)
    else:
       storage_path.manage_addFile(id=nom_pdf_saida,file=content,title=texto)
       pdf=storage_path[nom_pdf_saida]
    pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
    return nom_pdf_saida
