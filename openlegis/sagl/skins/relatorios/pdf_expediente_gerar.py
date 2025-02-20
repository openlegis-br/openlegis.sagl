##parameters=dic_cabecalho, dic_rodape, imagem, pauta_dic

"""Expediente
"""
from trml2pdf import parseString
from xml.sax.saxutils import escape


def cabecalho(dic_cabecalho,imagem):
    """Gera o codigo rml do cabecalho"""
    tmp=''
    if dic_cabecalho['custom_image'] == True:
       tmp+='\t\t\t\t<image x="2cm" y="26.9cm" width="350" height="67" file="' + imagem + '"/>\n'
    elif dic_cabecalho['custom_image'] == False:
       tmp+='\t\t\t\t<image x="2.5cm" y="27.4cm" width="74" height="60" file="' + imagem + '"/>\n'
       tmp+='\t\t\t\t<lines>1.7cm 27.1cm 19.3cm 27.1cm</lines>\n'
       tmp+='\t\t\t\t<setFont name="Helvetica-Bold" size="15"/>\n'
       tmp+='\t\t\t\t<drawString x="6cm" y="28.5cm">' + dic_cabecalho["nom_casa"] + '</drawString>\n'
       tmp+='\t\t\t\t<setFont name="Helvetica" size="11"/>\n'
       tmp+='\t\t\t\t<drawString x="6cm" y="28cm">' + 'Estado de ' + dic_cabecalho["nom_estado"] + '</drawString>\n'
    return tmp

def rodape(dic_rodape):
    """Gera o codigo rml do rodape"""
    tmp=''
    if dic_cabecalho['custom_image'] == True:
       tmp+='\t\t\t\t<setFont name="Helvetica" size="8"/>\n'
       tmp+='\t\t\t\t<drawString x="1.7cm" y="1cm">' + dic_rodape[2] + '</drawString>\n'
       tmp+='\t\t\t\t<drawString x="18.1cm" y="1cm">Página <pageNumber/></drawString>\n'
    elif dic_cabecalho['custom_image'] == False:
       tmp+='\t\t\t\t<lines>1.7cm 1.2cm 19.3cm 1.2cm</lines>\n'
       tmp+='\t\t\t\t<setFont name="Helvetica" size="8"/>\n'
       tmp+='\t\t\t\t<drawString x="1.7cm" y="1.4cm">' + dic_rodape[2] + '</drawString>\n'
       tmp+='\t\t\t\t<drawString x="18.1cm" y="1.4cm">Página <pageNumber/></drawString>\n'
       tmp+='\t\t\t\t<drawCentredString x="10.5cm" y="0.8cm">' + dic_rodape[0] + '</drawCentredString>\n'
       tmp+='\t\t\t\t<drawCentredString x="10.5cm" y="0.5cm">' + dic_rodape[1] + '</drawCentredString>\n'
    return tmp

def paraStyle():
    """ Gera o codigo rml que define o estilo dos paragrafos"""
    tmp=''
    tmp+='\t<stylesheet>\n'
    tmp+='\t\t<blockTableStyle id="Standard_Outline">\n'
    tmp+='\t\t\t<blockAlignment value="LEFT"/>\n'
    tmp+='\t\t\t<blockValign value="TOP"/>\n'
    tmp+='\t\t</blockTableStyle>\n'
    tmp+='\t\t<initialize>\n'
    tmp+='\t\t\t<paraStyle name="all" alignment="justify"/>\n'
    tmp+='\t\t</initialize>\n'
    tmp+='\t\t<paraStyle name="P0" fontName="Helvetica-Bold" fontSize="12" leading="14" alignment="CENTER"/>\n'
    tmp+='\t\t<paraStyle name="P1" fontName="Helvetica" fontSize="12" leading="14" alignment="CENTER"/>\n'
    tmp+='\t\t<paraStyle name="P2" fontName="Helvetica" fontSize="11" leading="14" alignment="JUSTIFY"/>\n'
    tmp+='\t\t<paraStyle name="P3" fontName="Helvetica" fontSize="11" leading="13" alignment="JUSTIFY"/>\n'
    tmp+='\t\t<paraStyle name="P4" fontName="Helvetica" fontSize="11" leading="13" alignment="CENTER"/>\n'
    tmp+='\t</stylesheet>\n'
    return tmp

def pauta(pauta_dic):
    """ Funcao que gera o codigo rml da sessao plenaria """
    tmp=''
    # inicio do bloco 
    tmp+='\t<story>\n'
    # dados da sessao
    if pauta_dic["num_periodo"] != '':
       tmp+='\t\t<para style="P0">'+ str(pauta_dic["num_sessao_plen"]) +'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + pauta_dic["nom_sessao"] + ' DO ' + str(pauta_dic["num_periodo"]) + 'º PERÍODO - ' + pauta_dic["dat_inicio_sessao"] + ' ' + pauta_dic["hr_inicio_sessao"] + '</para>\n'
    else:
       tmp+='\t\t<para style="P0">'+ str(pauta_dic["num_sessao_plen"]) +'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + pauta_dic["nom_sessao"] + ' - ' + pauta_dic["dat_inicio_sessao"] + ' ÀS ' + pauta_dic["hr_inicio_sessao"] + '</para>\n'
    tmp+='\t\t<para style="P2" spaceAfter="4">\n'
    tmp+='\t\t\t<font color="white"> </font>\n'
    tmp+='\t\t</para>\n'
    tmp+='\t\t<para style="P0">' + str(pauta_dic["num_sessao_leg"]) +'ª SESSÃO LEGISLATIVA' + ' - ' + str(pauta_dic["num_legislatura"]) + 'ª LEGISLATURA' + '</para>\n'
    tmp+='\t\t<para style="P2" spaceAfter="4" spaceBefore="10">\n'
    tmp+='\t\t\t<font color="white"> </font>\n'
    tmp+='\t\t</para>\n'

    tmp+='\t\t<condPageBreak height="10mm"/>\n'
    tmp+='\t\t<para style="P1" spaceBefore="10" spaceAfter="10"><b><u>MATÉRIAS DO EXPEDIENTE</u></b></para>\n'

    if pauta_dic["total_indicacoes"] != 0:
        tmp+='\t\t<condPageBreak height="15"/>\n'
        tmp+='\t\t<para style="P2" spaceBefore="5"><b>Número de Indicações:</b> ' + str(pauta_dic["total_indicacoes"]) + '</para>\n'

    if pauta_dic["total_requerimentos"] != 0:
        tmp+='\t\t<condPageBreak height="15mm"/>\n'
        tmp+='\t\t<para style="P2" spaceBefore="5"><b>Número de Requerimentos:</b> ' + str(pauta_dic["total_requerimentos"]) + '</para>\n'

    if pauta_dic["total_requerimentos_plen"] != 0:
        tmp+='\t\t<condPageBreak height="15mm"/>\n'
        tmp+='\t\t<para style="P2" spaceBefore="5"><b>Número de Requerimentos ao Plenário:</b> ' + str(pauta_dic["total_requerimentos_plen"]) + '</para>\n'
        
    if pauta_dic["total_requerimentos_presid"] != 0:
        tmp+='\t\t<condPageBreak height="15mm"/>\n'
        tmp+='\t\t<para style="P2" spaceBefore="5"><b>Número de Requerimentos à Presidência:</b> ' + str(pauta_dic["total_requerimentos_presid"]) + '</para>\n'

    if pauta_dic["total_mocoes"] != 0:
        tmp+='\t\t<condPageBreak height="15"/>\n'
        tmp+='\t\t<para style="P2" spaceBefore="5"><b>Número de Moções:</b> ' + str(pauta_dic["total_mocoes"]) + '</para>\n'

    if pauta_dic["total_pedidos"] != 0:
        tmp+='\t\t<condPageBreak height="15"/>\n'
        tmp+='\t\t<para style="P2" spaceBefore="5"><b>Número de Pedido de Informação:</b> ' + str(pauta_dic["total_pedidos"]) + '</para>\n'

    if pauta_dic["total_materias"] != 0:
        tmp+='\t\t<condPageBreak height="15"/>\n'
        tmp+='\t\t<para style="P2" spaceBefore="5"><b>Total de Matérias:</b> ' + str(pauta_dic["total_materias"]) + '</para>\n'

    for dic in pauta_dic["lst_requerimentos_vereadores"]:
        if dic['cargo'] != '':
           tmp+='\t\t<para style="P2" spaceBefore="20"><b><u>' + str(dic['vereador']) + ' (' + str(dic['cargo']) + ' ' + str(dic['nom_parlamentar']) + ') ' + ' [' +str(dic['qtde_materias']) + ']</u></b></para>\n'
        else:
           tmp+='\t\t<para style="P2" spaceBefore="20"><b><u>' + str(dic['vereador']) + ' [' +str(dic['qtde_materias']) + ']</u></b></para>\n'
        for item in dic['materias']:
            tmp+='\t\t<para style="P2" spaceBefore="5"><font color="#126e90"><b>' + item['id_materia'] + '</b></font> - ' + escape(item['txt_ementa']) + '</para>\n'
    
    # fim do bloco 
    tmp+='\t</story>\n'
    return tmp

def principal(dic_cabecalho, dic_rodape, imagem, pauta_dic):
    arquivoPdf=str(pauta_dic["cod_sessao_plen"])+"_pauta_expediente.pdf"
    tmp=''
    tmp+='<?xml version="1.0" encoding="utf-8" standalone="no" ?>\n'
    tmp+='<!DOCTYPE document SYSTEM "rml_1_0.dtd">\n'
    tmp+='<document filename="pauta_expediente.pdf">\n'
    tmp+='\t<template pageSize="(21cm, 29.7cm)" title="Matérias do Expediente" author="SAGL" allowSplitting="20">\n'
    tmp+='\t\t<pageTemplate id="first">\n'
    tmp+='\t\t\t<pageGraphics>\n'
    tmp+=cabecalho(dic_cabecalho,imagem)
    tmp+=rodape(dic_rodape)
    tmp+='\t\t\t</pageGraphics>\n'
    tmp+='\t\t\t<frame id="first" x1="1.5cm" y1="1.5cm" width="18cm" height="25.2cm"/>\n'
    tmp+='\t\t</pageTemplate>\n'
    tmp+='\t</template>\n'
    tmp+=paraStyle()
    tmp+=pauta(pauta_dic)
    tmp+='</document>\n'
    tmp_pdf=parseString(tmp)   

    if hasattr(context.sapl_documentos.pauta_sessao,arquivoPdf):
        context.sapl_documentos.pauta_sessao.manage_delObjects(ids=arquivoPdf)
    context.sapl_documentos.pauta_sessao.manage_addFile(arquivoPdf)
    arq=context.sapl_documentos.pauta_sessao[arquivoPdf]
    arq.manage_edit(title='Pauta do Expediente',filedata=tmp_pdf,content_type='application/pdf')
   
    return "sapl_documentos/pauta_sessao/"+arquivoPdf

return principal(dic_cabecalho, dic_rodape, imagem, pauta_dic)
