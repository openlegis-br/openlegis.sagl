from .utils import zope_task
from io import BytesIO
import os
import pypdf
from dateutil.parser import parse
from asn1crypto import cms
import qrcode
import pymupdf
from datetime import datetime
import logging

def make_qrcode(text):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    fp = BytesIO()
    img.save(fp, "PNG")
    return fp
        
def get_signatures(fileStream):
    reader = pypdf.PdfReader(fileStream)
    fields = reader.get_fields().values()
    signature_field_values = [
        f.value for f in fields if f.field_type == '/Sig']
    lst_signers = []
    for v in signature_field_values:
        v_type = v['/Type']
        if '/M' in v:
           signing_time = parse(v['/M'][2:].strip("'").replace("'", ":"))
        else:
           signing_time = None
        if '/Name' in v:
           name = v['/Name'].split(':')[0]
           cpf = v['/Name'].split(':')[1]
        else:
           name = None
           cpf = None
        raw_signature_data = v['/Contents']
        for attrdict in parse_signatures(raw_signature_data):
           dic = {
                  'signer_name':name or attrdict.get('signer'),
                  'signer_cpf':cpf or attrdict.get('cpf'),
                  'signing_time':str(signing_time) or attrdict.get('signing_time'),
                  'signer_certificate': attrdict.get('oname')
           }
        lst_signers.append(dic)
    lst_signers.sort(key=lambda dic: dic['signing_time'], reverse=True)
    return lst_signers
 
def parse_signatures(raw_signature_data):
    info = cms.ContentInfo.load(raw_signature_data)
    signed_data = info['content']
    certificates = signed_data['certificates']
    signer_infos = signed_data['signer_infos'][0]
    signed_attrs = signer_infos['signed_attrs']
    signers = []
    for signer_info in signer_infos:
        for cert in certificates:
            cert = cert.native['tbs_certificate']
            issuer = cert['issuer']
            subject = cert['subject']
            oname = issuer.get('organization_name', '')
            lista = subject['common_name'].split(':')
            if len(lista) > 1:
               signer = subject['common_name'].split(':')[0]
               cpf = subject['common_name'].split(':')[1]
            else:
               signer = subject['common_name'].split(':')[0]
               cpf = ''
            dic = {
               'type': subject.get('organization_name', ''),
               'signer': signer,
               'cpf':  cpf,
               'oname': oname
            }
    signers.append(dic)
    return signers

@zope_task()
def margem_inferior_task(portal, codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename, portal_url):
    """Tarefa para adicionar carimbo nos arquivos PDF de materias."""
    skins = portal.portal_skins.sk_sagl
    arq = getattr(portal.sapl_documentos.documentos_assinados, filename)
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
    if nom_autor == None:
       for usuario in skins.zsql.usuario_obter_zsql(cod_usuario=cod_usuario):
           nom_autor = usuario.nom_completo
           break
    string = str(skins.cadastros.assinatura.format_verification_code(cod_assinatura_doc))
    # Variáveis para obtenção de dados e local de armazenamento por tipo de documento
    for storage in skins.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
        if tipo_doc == 'anexo_sessao':
           nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
           nom_pdf_documento = str(codigo) + '_anexo_' + str(anexo) + '.pdf'
        elif tipo_doc == 'anexo_peticao':
           nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
           nom_pdf_documento = str(codigo) + '_anexo_' + str(anexo) + '.pdf'
        else:
           nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
           nom_pdf_documento = str(codigo) + str(storage.pdf_file)
    if tipo_doc == 'materia' or tipo_doc == 'doc_acessorio' or tipo_doc == 'redacao_final':
       storage_path = portal.sapl_documentos.materia
       if tipo_doc == 'materia' or tipo_doc == 'redacao_final':
          for metodo in skins.zsql.materia_obter_zsql(cod_materia=codigo):
              num_documento = metodo.num_ident_basica
              if tipo_doc == 'materia':
                 texto = str(metodo.des_tipo_materia)+' nº '+ str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica)
              elif tipo_doc == 'redacao_final':
                 texto = 'Redação Final do ' + str(metodo.sgl_tipo_materia)+' nº '+ str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica)
       elif tipo_doc == 'doc_acessorio':
          for metodo in skins.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
              for materia in skins.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                  materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
              texto = str(metodo.nom_documento) + ' - ' + str(materia)
    elif tipo_doc == 'emenda':
       storage_path = portal.sapl_documentos.emenda
       for metodo in skins.zsql.emenda_obter_zsql(cod_emenda=codigo):
           for materia in skins.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
               materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
           texto = 'Emenda ' + str(metodo.des_tipo_emenda) + ' nº ' + str(metodo.num_emenda) + ' ao ' + str(materia)
    elif tipo_doc == 'substitutivo':
       storage_path = portal.sapl_documentos.substitutivo
       for metodo in skins.zsql.substitutivo_obter_zsql(cod_substitutivo=codigo):
           for materia in skins.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
               materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
           texto = 'Substitutivo nº ' + str(metodo.num_substitutivo) + ' ao ' + str(materia)
    elif tipo_doc == 'tramitacao':
       storage_path = portal.sapl_documentos.materia.tramitacao
       for metodo in skins.zsql.tramitacao_obter_zsql(cod_tramitacao=codigo):
           materia = str(metodo.sgl_tipo_materia)+' '+ str(metodo.num_ident_basica)+'/'+str(metodo.ano_ident_basica)
           texto = 'Tramitação nº '+ str(metodo.cod_tramitacao) + ' - ' + str(materia)
    elif tipo_doc == 'parecer_comissao':
       storage_path = portal.sapl_documentos.parecer_comissao
       for metodo in skins.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
           for comissao in skins.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
               sgl_comissao = str(comissao.sgl_comissao)
           parecer = str(metodo.num_parecer)+'/'+str(metodo.ano_parecer)
           for materia in skins.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
               materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
       texto = 'Parecer ' + str(sgl_comissao) + ' nº ' + str(parecer) + ' ao ' + str(materia)
    elif tipo_doc == 'pauta':
       storage_path = portal.sapl_documentos.pauta_sessao
       for metodo in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
           for tipo in skins.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
               sessao = str(metodo.num_sessao_plen) + 'ª ' + str(portal.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + str(tipo.nom_sessao) + ' - ' + str(metodo.dat_inicio_sessao)
       for metodo in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
           sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
       texto = 'Pauta da ' + str(sessao)
    elif tipo_doc == 'resumo_sessao':
       storage_path = portal.sapl_documentos.pauta_sessao
       for metodo in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
           for tipo in skins.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
               sessao = str(metodo.num_sessao_plen) + 'ª ' + str(portal.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ' - ' + str(metodo.dat_inicio_sessao)
       for metodo in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
           sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
       texto = 'Roteiro da ' + str(sessao)
    elif tipo_doc == 'ata':
       storage_path = portal.sapl_documentos.ata_sessao
       for metodo in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
           for tipo in skins.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
               sessao = str(metodo.num_sessao_plen) + 'ª ' + str(portal.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + str(tipo.nom_sessao) + ' - ' + str(metodo.dat_inicio_sessao)
       for metodo in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
           sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
       texto = 'Ata da ' + str(sessao)
    elif tipo_doc == 'anexo_peticao':
       storage_path = portal.sapl_documentos.peticao
       file_item =  str(codigo) + '_anexo_' + str(anexo) + '.pdf'
       title = getattr(portal.sapl_documentos.peticao,file_item).title_or_id()
       texto = 'Anexo de petição: ' + str(title)
    elif tipo_doc == 'anexo_sessao':
       storage_path = portal.sapl_documentos.anexo_sessao
       for metodo in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
           for tipo in skins.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
               sessao = str(metodo.num_sessao_plen) + 'ª ' + str(portal.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ', de ' + str(metodo.dat_inicio_sessao)
       file_item =  str(codigo) + '_anexo_' + str(anexo) + '.pdf'
       title = getattr(portal.sapl_documentos.anexo_sessao,file_item).title_or_id()
       texto = str(title) + ' da ' + str(sessao)
    elif tipo_doc == 'norma':
       storage_path = portal.sapl_documentos.norma_juridica
       for metodo in skins.zsql.norma_juridica_obter_zsql(cod_norma=codigo):
           texto = str(metodo.des_tipo_norma) + ' nº ' + str(metodo.num_norma) + '/' + str(metodo.ano_norma)
    elif tipo_doc == 'documento' or tipo_doc == 'doc_acessorio_adm':
       storage_path = portal.sapl_documentos.administrativo
       if tipo_doc == 'documento':
          for metodo in skins.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
              num_documento = metodo.num_documento
              texto = str(metodo.des_tipo_documento)+ ' nº ' + str(metodo.num_documento)+ '/' +str(metodo.ano_documento)
       elif tipo_doc == 'doc_acessorio_adm':
          for metodo in skins.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
              for documento in skins.zsql.documento_administrativo_obter_zsql(cod_documento=metodo.cod_documento):
                  documento = str(documento.sgl_tipo_documento) +' '+ str(documento.num_documento)+'/'+str(documento.ano_documento)
              texto = 'Doumento Acessório do ' + str(documento)
    elif tipo_doc == 'tramitacao_adm':
       storage_path = portal.sapl_documentos.administrativo.tramitacao
       for metodo in skins.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=codigo):
           documento = str(metodo.sgl_tipo_documento)+' '+ str(metodo.num_documento)+'/'+str(metodo.ano_documento)
           texto = 'Tramitação nº '+ str(metodo.cod_tramitacao) + ' - ' + str(documento)
    elif tipo_doc == 'proposicao':
       storage_path = portal.sapl_documentos.proposicao
       for metodo in skins.zsql.proposicao_obter_zsql(cod_proposicao=codigo):
           texto = str(metodo.des_tipo_proposicao) +' nº ' + str(metodo.cod_proposicao)
    elif tipo_doc == 'protocolo':
       storage_path = portal.sapl_documentos.protocolo
       for metodo in skins.zsql.protocolo_obter_zsql(cod_protocolo=codigo):
           texto = 'Protocolo nº '+ str(metodo.num_protocolo) +'/' + str(metodo.ano_protocolo)
    elif tipo_doc == 'peticao':
       storage_path = portal.sapl_documentos.peticao
       texto = 'Petição Eletrônica'
    elif tipo_doc == 'pauta_comissao':
       storage_path = portal.sapl_documentos.reuniao_comissao
       for metodo in skins.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
           for comissao in skins.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
               texto = 'Pauta da ' + str(metodo.num_reuniao) + 'ª Reunião da ' + comissao.sgl_comissao + ', em ' + str(metodo.dat_inicio_reuniao)
    elif tipo_doc == 'ata_comissao':
       storage_path = portal.sapl_documentos.reuniao_comissao
       for metodo in skins.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
           for comissao in skins.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
               texto = 'Ata da ' + str(metodo.num_reuniao) + 'ª Reunião da ' + comissao.sgl_comissao + ', em ' + str(metodo.dat_inicio_reuniao)
    elif tipo_doc == 'documento_comissao':
       storage_path = portal.sapl_documentos.documento_comissao
       for metodo in skins.zsql.documento_comissao_obter_zsql(cod_documento=codigo):
           for comissao in skins.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
               texto = metodo.txt_descricao + ' da ' + comissao.sgl_comissao
    mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
    mensagem2 = 'Para validar visite ' + portal_url + '/conferir_assinatura' + ' e informe o código ' + string
    existing_pdf = pymupdf.open(stream=fileStream)
    existing_pdf.bake()
    numPages = existing_pdf.page_count
    stream = make_qrcode(text=portal_url+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(string))
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
        black = pymupdf.pdfcolor["black"]
        # qrcode
        rect = pymupdf.Rect(left, bottom, left + 50, bottom + 50)  # qrcode bottom left square
        existing_pdf[page_index].insert_image(rect, stream=stream)
        text2 = mensagem2
        # logo icp
        rect_icp = pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45)
        existing_pdf[page_index].insert_image(rect_icp, stream=image)
        # margem direita
        numero = "Pág. %s/%s" % (i+1, numPages)
        text3 = numero + ' - ' + texto + ' - ' + mensagem1
        x = w - 8 - margin #largura
        y = h - 50 - margin # altura
        existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)
        # margem inferior
        p1 = pymupdf.Point(w - 40 - margin, h - 12) # numero de pagina documento
        p2 = pymupdf.Point(60, h - 12) # margem inferior
        shape = existing_pdf[page_index].new_shape()
        shape.draw_circle(p1,1)
        shape.draw_circle(p2,1)
        shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
        shape.commit()
    content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
    if hasattr(storage_path, nom_pdf_documento):
       pdf = getattr(storage_path, nom_pdf_documento)
       pdf.manage_upload(file=content)
    else:
       storage_path.manage_addFile(id=nom_pdf_documento,file=content,title=texto)
       pdf = getattr(storage_path, nom_pdf_documento)
    if tipo_doc == 'parecer_comissao':
       for relat in skins.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
           for tipo in skins.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria = relat.tip_fim_relatoria):
               if tipo.des_fim_relatoria=='Aguardando apreciação':
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
               else:
                  pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
    elif tipo_doc == 'doc_acessorio':
       for documento in skins.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
           if str(documento.ind_publico) == '1':
              pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
           elif str(documento.ind_publico) == '0':
              pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
    elif tipo_doc == 'documento':
       for documento in skins.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
           if str(documento.ind_publico) == '1':
              pdf.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
           elif str(documento.ind_publico) == '0':
              pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
    elif tipo_doc == 'doc_acessorio_adm':
       for doc in skins.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
           if str(doc.ind_publico) == '1':
              pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
           if str(doc.ind_publico) == '0':
              pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
    elif tipo_doc == 'peticao' or tipo_doc == 'anexo_peticao':
       pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
    else:
       pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
    return nom_pdf_documento
