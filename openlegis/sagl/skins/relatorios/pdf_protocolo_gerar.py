##parameters=sessao,imagem,data,lst_protocolos,dic_cabecalho,lst_rodape,dic_filtro

from trml2pdf import parseString
from xml.sax.saxutils import escape
import time

def cabecalho(dic_cabecalho,imagem):
    """Gera o codigo rml do cabecalho"""
    tmp_data=''
    if dic_cabecalho['custom_image'] == True:
       tmp_data+='\t\t\t\t<image x="3.1cm" y="26.9cm" width="350" height="67" file="' + imagem + '"/>\n'
       tmp_data+='\t\t\t\t<lines>3.3cm 26.3cm 19.5cm 26.3cm</lines>\n'
    elif dic_cabecalho['custom_image'] == False:
       tmp_data+='\t\t\t\t<image x="3.1cm" y="26.9cm" width="60" height="60" file="' + imagem + '"/>\n'
       tmp_data+='\t\t\t\t<lines>3.3cm 26.3cm 19.5cm 26.3cm</lines>\n'
       tmp_data+='\t\t\t\t<setFont name="Helvetica-Bold" size="15"/>\n'
       tmp_data+='\t\t\t\t<drawString x="6.7cm" y="28.1cm">' + dic_cabecalho['nom_casa'] + '</drawString>\n'
       tmp_data+='\t\t\t\t<setFont name="Helvetica" size="11"/>\n'
       tmp_data+='\t\t\t\t<drawString x="6.7cm" y="27.6cm">' + dic_cabecalho['nom_estado'] + '</drawString>\n'
    tmp_data+='\t\t\t\t<setFont name="Helvetica-Bold" size="11"/>\n'
    tmp_data+='\t\t\t\t<drawCentredString x="11.5cm" y="25.6cm">RELATÓRIO DE PROTOCOLOS</drawCentredString>\n'
    return tmp_data

def rodape(lst_rodape):
    """Gera o codigo rml do rodape"""

    tmp_data=''
    if dic_cabecalho['custom_image'] == True:
       tmp_data+='\t\t\t\t<lines>3.3cm 2.0cm 19.5cm 2.0cm</lines>\n'
       tmp_data+='\t\t\t\t<setFont name="Helvetica" size="8"/>\n'
       tmp_data+='\t\t\t\t<drawString x="3.3cm" y="2.2cm">' + lst_rodape[2] + '</drawString>\n'
       tmp_data+='\t\t\t\t<drawString x="18.4cm" y="2.2cm">Página <pageNumber/></drawString>\n'
    elif dic_cabecalho['custom_image'] == False:
       tmp_data+='\t\t\t\t<lines>3.3cm 2.0cm 19.5cm 2.0cm</lines>\n'
       tmp_data+='\t\t\t\t<setFont name="Helvetica" size="8"/>\n'
       tmp_data+='\t\t\t\t<drawString x="3.3cm" y="2.2cm">' + lst_rodape[2] + '</drawString>\n'
       tmp_data+='\t\t\t\t<drawString x="18.4cm" y="2.2cm">Página <pageNumber/></drawString>\n'
       tmp_data+='\t\t\t\t<drawCentredString x="11.5cm" y="1.6cm">' + lst_rodape[0] + '</drawCentredString>\n'
       tmp_data+='\t\t\t\t<drawCentredString x="11.5cm" y="1.2cm">' + lst_rodape[1] + '</drawCentredString>\n'
    return tmp_data

def paraStyle():
    """Gera o codigo rml que define o estilo dos paragrafos"""

    tmp_data=''
    tmp_data+='\t<stylesheet>\n'
    tmp_data+='\t\t<blockTableStyle id="Standard_Outline">\n'
    tmp_data+='\t\t\t<blockAlignment value="LEFT"/>\n'
    tmp_data+='\t\t\t<blockValign value="TOP"/>\n'
    tmp_data+='\t\t</blockTableStyle>\n'
    tmp_data+='\t\t<initialize>\n'
    tmp_data+='\t\t\t<paraStyle name="all" alignment="justify"/>\n'
    tmp_data+='\t\t</initialize>\n'
    tmp_data+='\t\t<paraStyle name="P1" fontName="Helvetica-Bold" fontSize="10.0" leading="12" spaceAfter="0" spaceBefore="8" alignment="left"/>\n'
    tmp_data+='\t\t<paraStyle name="P2" fontName="Helvetica" fontSize="9.0" leading="12" spaceAfter="0" alignment="justify"/>\n'
    tmp_data+='\t</stylesheet>\n'

    return tmp_data

def protocolos(lst_protocolos):
    """Gera o codigo rml do conteudo da pesquisa de protocolos"""

    tmp_data=''

    #inicio do bloco que contem os flowables
    tmp_data+='\t<story>\n'

    for dic in lst_protocolos:
        #espaco inicial
        tmp_data+='\t\t<para style="P2">\n'
        tmp_data+='\t\t\t<font color="white"> </font>\n'
        tmp_data+='\t\t</para>\n'

        #condicao para a quebra de pagina
        tmp_data+='\t\t<condPageBreak height="1.5cm"/>\n'

        #protocolos 
        if dic['titulo']!=None:
            tmp_data+='\t\t<para style="P1">PROTOCOLO N° ' + dic['titulo'] + '</para>\n'
        if dic['txt_assunto']!=None:
            txt_assunto = escape(dic['txt_assunto'])
            tmp_data+='\t\t<para style="P2">' + txt_assunto + '</para>\n'
        if dic['data']!=None:
            tmp_data+='\t\t<para style="P2"><b>Data Protocolo:</b> ' + dic['data'] + '</para>\n'
        if dic['txt_interessado']!=None:
           tmp_data+='\t\t<para style="P2"><b>Interessado:</b> ' + dic['txt_interessado'] + '</para>\n'
        elif dic['nom_autor']!=None:
           tmp_data+='\t\t<para style="P2"><b>Autor:</b> ' + dic['nom_autor'] + '</para>\n'
        if dic['natureza']!=None:
            tmp_data+='\t\t<para style="P2"><b>Natureza Processo:</b> ' + dic['natureza'] + '</para>\n'
        if dic['processo']!=None:
            tmp_data+='\t\t<para style="P2"><b>Classificação:</b> ' + dic['processo'] + '</para>\n'
        if dic['anulado']!="":
            tmp_data+='\t\t<para style="P2"><b>** PROTOCOLO ANULADO **</b> ' '</para>\n'

    tmp_data+='\t</story>\n'
    return tmp_data

def principal(sessao,imagem,data,lst_protocolos,dic_cabecalho,lst_rodape,dic_filtro={}):
    """Funcao pricipal que gera a estrutura global do arquivo rml"""

    arquivoPdf=str(int(time.time()*100))+".pdf"

    tmp_data=''
    tmp_data+='<?xml version="1.0" encoding="utf-8" standalone="no" ?>\n'
    tmp_data+='<!DOCTYPE document SYSTEM "rml_1_0.dtd">\n'
    tmp_data+='<document filename="relatorio.pdf">\n'
    tmp_data+='\t<template pageSize="(21cm, 29.7cm)" title="Relatório de Protocolos" author="OpenLegis" allowSplitting="20">\n'
    tmp_data+='\t\t<pageTemplate id="first">\n'
    tmp_data+='\t\t\t<pageGraphics>\n'
    tmp_data+=cabecalho(dic_cabecalho,imagem)
    tmp_data+=rodape(lst_rodape)
    tmp_data+='\t\t\t</pageGraphics>\n'
    tmp_data+='\t\t\t<frame id="first" x1="3cm" y1="2.6cm" width="16cm" height="23cm"/>\n'
    tmp_data+='\t\t</pageTemplate>\n'
    tmp_data+='\t</template>\n'
    tmp_data+=paraStyle()
    tmp_data+=protocolos(lst_protocolos)
    tmp_data+='</document>\n'
    tmp_pdf=parseString(tmp_data)

    if hasattr(context.temp_folder,arquivoPdf):
        context.temp_folder.manage_delObjects(ids=arquivoPdf)
    context.temp_folder.manage_addFile(arquivoPdf)
    arq=context.temp_folder[arquivoPdf]
    arq.manage_edit(title='Arquivo PDF temporário.',filedata=tmp_pdf,content_type='application/pdf')

    return "/temp_folder/"+arquivoPdf

return principal(sessao,imagem,data,lst_protocolos,dic_cabecalho,lst_rodape,dic_filtro)

