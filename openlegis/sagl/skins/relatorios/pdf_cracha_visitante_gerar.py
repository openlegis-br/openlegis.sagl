##parameters=imagem,nom_casa,data,lst_visitas

"""cracha_visitante_gerar.py
   Script para gerar o arquivo rml do cracha de visitante
   Autor: OpenLegis
   versão: 1.0
"""
from trml2pdf import parseString
from io import BytesIO
import time

def paraStyle():
    """Gera o codigo rml que define o estilo dos paragrafos"""

    tmp_data=''
    tmp_data+='\t<stylesheet>\n'
    tmp_data+='\t\t<blockTableStyle id="Standard_Outline">\n'
    tmp_data+='\t\t\t<blockAlignment value="LEFT"/>\n'
    tmp_data+='\t\t\t<blockValign value="BOTTOM"/>\n'
    tmp_data+='\t\t</blockTableStyle>\n'
    tmp_data+='\t\t<initialize>\n'
    tmp_data+='\t\t\t<paraStyle name="all" alignment="LEFT"/>\n'
    tmp_data+='\t\t</initialize>\n'
    tmp_data+='\t\t<paraStyle name="P1" fontName="Helvetica-Bold" fontSize="1" leading="1" alignment="LEFT"/>\n'
    tmp_data+='\t\t<paraStyle name="P2" fontName="Helvetica-Bold" fontSize="11" leading="12" spaceAfter="3" alignment="LEFT"/>\n'
    tmp_data+='\t\t<paraStyle name="P3" fontName="Helvetica" fontSize="8" leading="10" alignment="LEFT"/>\n'
    tmp_data+='\t</stylesheet>\n'

    return tmp_data

def visitas(lst_visitas):
    """Gera o codigo rml do conteudo da pesquisa de visitas"""

    tmp_data=''

    #inicio do bloco que contem os flowables
    tmp_data+='\t<story>\n'

    for dic in lst_visitas:
        #condicao para a quebra de pagina
        tmp_data+='\t\t<condPageBreak height="8mm"/>\n'

        #visitas
        tmp_data+='\t\t<para style="P1">\n'
        tmp_data+='\t\t\t<font color="white"></font>\n'
        tmp_data+='\t\t</para>\n'
        tmp_data+='\t\t<para style="P1">\n'
        tmp_data+='\t\t\t<font color="white"> </font>\n'
        tmp_data+='\t\t</para>\n'
        tmp_data+='\t\t<para style="P2"><b>Nome: '+dic['nom_pessoa']+'</b></para>\n'
        tmp_data+='\t\t<para style="P1">\n'
        tmp_data+='\t\t\t<font color="white">-</font>\n'
        tmp_data+='\t\t</para>\n'
        tmp_data+='\t\t<para style="P2"><b>Local: '+dic['nom_funcionario']+'</b></para>\n'
        tmp_data+='\t\t<para style="P1">\n'
        tmp_data+='\t\t\t<font color="white">-</font>\n'
        tmp_data+='\t\t</para>\n'
        tmp_data+='\t\t<para style="P1">\n'
        tmp_data+='\t\t\t<font color="white">-</font>\n'
        tmp_data+='\t\t</para>\n'
        tmp_data+='\t\t<para style="P3"><b>Data: '+data+'</b></para>\n'
        tmp_data+='\t\t<para style="P1">\n'
        tmp_data+='\t\t\t<font color="white">-</font>\n'
        tmp_data+='\t\t</para>\n'

    tmp_data+='\t</story>\n'
    return tmp_data

def principal(imagem,nom_casa,data,lst_visitas):
    """Funcao pricipal que gera a estrutura global do arquivo rml"""

    arquivoPdf=str(int(time.time()*100))+".pdf"

    tmp_data=''
    tmp_data+='<?xml version="1.0" encoding="utf-8" standalone="no" ?>\n'
    tmp_data+='<!DOCTYPE document SYSTEM "rml_1_0.dtd">\n'
    tmp_data+='<document filename="etiquetas.pdf">\n'
    tmp_data+='\t<template pageSize="(85mm, 30mm)" title="Etiqueta de Protocolo" author="OpenLegis" allowSplitting="20">\n'
    tmp_data+='\t\t<pageTemplate id="first">\n'
    tmp_data+='\t\t\t<pageGraphics>\n'
    tmp_data+='\t\t\t\t<setFont name="Helvetica-Bold" size="10"/>\n'
    tmp_data+='\t\t\t\t<drawString x="0.3cm" y="2.15cm">' + nom_casa.upper() + '</drawString>\n'
    tmp_data+='\t\t\t\t<setFont name="Helvetica-Bold" size="10"/>\n'
    tmp_data+='\t\t\t<frame id="first" x1="0.1cm" y1="0.01cm" width="85mm" height="21mm"/>\n'
    tmp_data+='\t\t\t</pageGraphics>\n'
    tmp_data+='\t\t</pageTemplate>\n'
    tmp_data+='\t</template>\n'
    tmp_data+=paraStyle()
    tmp_data+=visitas(lst_visitas)
    tmp_data+='</document>\n'
    tmp_pdf=parseString(tmp_data)

    if hasattr(context.temp_folder,arquivoPdf):
        context.temp_folder.manage_delObjects(ids=arquivoPdf)
    context.temp_folder.manage_addFile(arquivoPdf)
    arq=context.temp_folder[arquivoPdf]
    arq.manage_edit(title='Arquivo PDF temporario.',filedata=tmp_pdf,content_type='application/pdf')

    return "/temp_folder/"+arquivoPdf

return principal(imagem,nom_casa,data,lst_visitas)

