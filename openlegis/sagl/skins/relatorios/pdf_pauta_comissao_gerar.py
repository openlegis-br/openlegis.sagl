##parameters=imagem,dat_reuniao,cod_reuniao,lst_reuniao,lst_pauta,dic_cabecalho,lst_rodape

from trml2pdf import parseString
from xml.sax.saxutils import escape
from html2rml import html2rml
import time

def cabecalho(dic_cabecalho,dat_reuniao,imagem):
    """Gera o codigo rml do cabecalho"""
    tmp=''
    if dic_cabecalho['custom_image'] == True:
       tmp+='\t\t\t\t<image x="3.1cm" y="26.9cm" width="350" height="67" file="' + imagem + '"/>\n'
    elif dic_cabecalho['custom_image'] == False:
       tmp+='\t\t\t\t<image x="2.5cm" y="27.4cm" width="74" height="60" file="' + imagem + '"/>\n'
       tmp+='\t\t\t\t<lines>1.7cm 27.1cm 19.3cm 27.1cm</lines>\n'
       tmp+='\t\t\t\t<setFont name="Helvetica-Bold" size="15"/>\n'
       tmp+='\t\t\t\t<drawString x="6cm" y="28.5cm">' + dic_cabecalho["nom_casa"] + '</drawString>\n'
       tmp+='\t\t\t\t<setFont name="Helvetica" size="11"/>\n'
       tmp+='\t\t\t\t<drawString x="6cm" y="28cm">' + 'Estado de ' + dic_cabecalho["nom_estado"] + '</drawString>\n'
    return tmp

def rodape(lst_rodape):
    """ Gera o codigo rml do rodape"""
    tmp=''
    tmp=''
    tmp+='\t\t\t\t<lines>3.3cm 2.2cm 19.5cm 2.2cm</lines>\n'
    tmp+='\t\t\t\t<setFont name="Helvetica" size="8"/>\n'
    tmp+='\t\t\t\t<drawString x="3.3cm" y="2.4cm">' + lst_rodape[2] + '</drawString>\n'
    tmp+='\t\t\t\t<drawString x="18.4cm" y="2.4cm">Página <pageNumber/></drawString>\n'
    tmp+='\t\t\t\t<drawCentredString x="11.5cm" y="1.7cm">' + lst_rodape[0] + '</drawCentredString>\n'
    tmp+='\t\t\t\t<drawCentredString x="11.5cm" y="1.3cm">' + lst_rodape[1] + '</drawCentredString>\n'
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
    tmp+='\t\t<paraStyle name="P0" fontName="Helvetica-Bold" fontSize="11" leading="12" alignment="CENTER"/>\n'
    tmp+='\t\t<paraStyle name="P1" fontName="Helvetica" fontSize="11" leading="12" alignment="CENTER"/>\n'
    tmp+='\t\t<paraStyle name="P2" fontName="Helvetica" fontSize="9" leading="10" alignment="LEFT"/>\n'
    tmp+='\t\t<paraStyle name="P3" fontName="Helvetica" fontSize="11" leading="12" alignment="JUSTIFY"/>\n'
    tmp+='\t\t<paraStyle name="P4" fontName="Helvetica" fontSize="11" leading="12" alignment="CENTER"/>\n'
    tmp+='\t\t<paraStyle name="P5" fontName="Helvetica-Bold" fontSize="12" leading="13" alignment="CENTER"/>\n'    
    tmp+='\t</stylesheet>\n'
    return tmp

#def splen(lst_reuniao):
def pauta(lst_reuniao, lst_pauta):
    """ Funcao que gera o codigo rml da reuniao plenaria """

    tmp=''

    #inicio do bloco 
    tmp+='\t<story>\n'

    for dicrc in lst_reuniao:

        # reuniao de comissao
        if dicrc['reuniao']!=None:
           if dicrc['tema']!=None and dicrc['tema']!='':
              tmp+=html2rml(dicrc['tema']).replace('&','&amp;')
              tmp+='\t\t<para style="P2" spaceAfter="16">\n'
              tmp+='\t\t\t<font color="white"> </font>\n'
              tmp+='\t\t</para>\n' 
           tmp+='\t\t<para style="P5">' + dicrc['reuniao'].replace('&','&amp;') + '</para>\n'
           tmp+='\t\t<para style="P2" spaceAfter="2">\n'
           tmp+='\t\t\t<font color="white"> </font>\n'
           tmp+='\t\t</para>\n'
           tmp+='\t\t<para style="P5">' + dicrc['nom_comissao'] + '</para>\n'
           tmp+='\t\t<para style="P2" spaceAfter="2">\n'
           tmp+='\t\t\t<font color="white"> </font>\n'
           tmp+='\t\t</para>\n'  
           tmp+='\t\t<para style="P1">Em ' + dicrc['datareuniao'] + ' às ' + dicrc['horareuniao']+ '</para>\n'
           tmp+='\t\t<para style="P2" spaceAfter="16">\n'
           tmp+='\t\t\t<font color="white"> </font>\n'
           tmp+='\t\t</para>\n'
                      

    #inicio do bloco que contem os flowables
    
    for dic in lst_pauta:
        #espaco inicial
        tmp+='\t\t<para style="P2" spaceAfter="10">\n'
        tmp+='\t\t\t<font color="white"> </font>\n'
        tmp+='\t\t</para>\n'

        #condicao para a quebra de pagina
        tmp+='\t\t<condPageBreak height="5mm"/>\n'

        #pauta
        if dic['id_materia']!=None:
            tmp+='\t\t<para style="P3"><b>' + str(dic['num_ordem']) + ') <font color="#126e90"><u>' + dic['link_materia']+'</u></font> - Autoria:</b> ' + dic['nom_autor'].replace('&','&amp;') + '</para>\n'
            tmp+='\t\t<para style="P3" spaceAfter="2">\n'
            tmp+='\t\t\t<font color="white"> </font>\n'
            tmp+='\t\t</para>\n'
        if dic['txt_ementa']!=None:
            tmp+='\t\t<para style="P3">' + escape(dic['txt_ementa']) + '</para>\n'
            tmp+='\t\t<para style="P2" spaceAfter="1">\n'
            tmp+='\t\t\t<font color="white"> </font>\n'
            tmp+='\t\t</para>\n' 
         

        if dic['substitutivo']!= 0:
            for substitutivo in dic['substitutivos']:
                tmp+='\t\t<para style="P3"><font color="#126e90">' + substitutivo["id_substitutivo"] + '</font> - ' + substitutivo["autoria"] + '</para>\n'
                tmp+='\t\t<para style="P2" spaceAfter="2">\n'
                tmp+='\t\t\t<font color="white"> </font>\n'
                tmp+='\t\t</para>\n'

        if dic['emenda']!= 0:
            for emenda in dic['emendas']:
                tmp+='\t\t<para style="P3"><font color="#126e90">' + emenda["id_emenda"] + '</font> - ' + emenda["autoria"] + ' - ' + escape(emenda['txt_ementa']) + '</para>\n'
                tmp+='\t\t<para style="P2" spaceAfter="2">\n'
                tmp+='\t\t\t<font color="white"> </font>\n'
                tmp+='\t\t</para>\n'

        if dic['nom_relator']!=None and dic['nom_relator']!='':
            tmp+='\t\t<para style="P3"><b>Relatoria:</b> ' + dic['nom_relator'].replace('&','&amp;') + '</para>\n'
            tmp+='\t\t<para style="P2" spaceAfter="2">\n'
            tmp+='\t\t\t<font color="white"> </font>\n'
            tmp+='\t\t</para>\n'   


    for dicrc in lst_reuniao:
        tmp+='\t\t<para style="P3" spaceAfter="30">\n'
        tmp+='\t\t\t<font color="white"> </font>\n'
        tmp+='\t\t</para>\n'
        tmp+='\t\t<para style="P1"><b>' + dicrc['presidente'] + '</b></para>\n'
        tmp+='\t\t<para style="P1">Presidente </para>\n' 

    tmp+='\t</story>\n'
    return tmp

def principal(imagem,dat_reuniao,lst_reuniao,lst_pauta,dic_cabecalho,lst_rodape):
    tmp=''
    tmp+='<?xml version="1.0" encoding="utf-8" standalone="no" ?>\n'
    tmp+='<!DOCTYPE document SYSTEM "rml_1_0.dtd">\n'
    tmp+='<document filename="pauta_reuniao.pdf">\n'
    tmp+='\t<template pageSize="(21cm, 29.7cm)" title="Pauta Reuniao" author="SAGL/OpenLegis" allowSplitting="20">\n'
    tmp+='\t\t<pageTemplate id="first">\n'
    tmp+='\t\t\t<pageGraphics>\n'
    tmp+=cabecalho(dic_cabecalho,dat_reuniao,imagem)
    tmp+=rodape(lst_rodape)
    tmp+='\t\t\t</pageGraphics>\n'
    tmp+='\t\t\t<frame id="first" x1="3cm" y1="3cm" width="16cm" height="23cm"/>\n'
    tmp+='\t\t</pageTemplate>\n'
    tmp+='\t</template>\n'
    tmp+=paraStyle()
    tmp+=pauta(lst_reuniao, lst_pauta)
    tmp+='</document>\n'
    tmp_pdf=parseString(tmp)   

    arquivoPdf=str(cod_reuniao)+"_pauta.pdf"
    if hasattr(context.sapl_documentos.reuniao_comissao,arquivoPdf):
        context.sapl_documentos.reuniao_comissao.manage_delObjects(ids=arquivoPdf)
    context.sapl_documentos.reuniao_comissao.manage_addFile(arquivoPdf)
    arq=context.sapl_documentos.reuniao_comissao[arquivoPdf]
    arq.manage_edit(title='Pauta Reuniao',filedata=tmp_pdf,content_type='application/pdf') 

    return context.portal_url() + '/cadastros/comissao/reuniao/reuniao_comissao_mostrar_proc?cod_reuniao=' + str(cod_reuniao)+ '&modal=1'

return principal(imagem,dat_reuniao,lst_reuniao,lst_pauta,dic_cabecalho,lst_rodape)
