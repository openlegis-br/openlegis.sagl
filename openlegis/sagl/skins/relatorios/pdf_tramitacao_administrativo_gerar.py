##parameters=imagem, dic_rodape, inf_basicas_dic, cod_tramitacao, tramitacao_dic, hdn_url,sessao=''

from trml2pdf import parseString
from xml.sax.saxutils import escape
from html2rml import html2rml


def cabecalho(inf_basicas_dic,imagem):
    """
    Função que gera o código rml do cabeçalho da página
    """
    tmp=''
    if inf_basicas_dic['custom_image'] == True:
       tmp+='\t\t\t\t<image x="3.1cm" y="26.9cm" width="350" height="67" file="' + imagem + '"/>\n'
    elif inf_basicas_dic['custom_image'] == False:
       tmp+='\t\t\t\t<image x="3.1cm" y="26.9cm" width="74" height="60" file="' + imagem + '"/>\n'
       tmp+='\t\t\t\t<setFont name="Helvetica-Bold" size="15"/>\n'
       tmp+='\t\t\t\t<drawString x="6.7cm" y="28.1cm">' + inf_basicas_dic['nom_camara'] + '</drawString>\n'
       tmp+='\t\t\t\t<setFont name="Helvetica" size="11"/>\n'
       tmp+='\t\t\t\t<drawString x="6.7cm" y="27.6cm">' + inf_basicas_dic['nom_estado'] + '</drawString>\n'
    if str(tramitacao_dic['id_documento']) != "" and str(tramitacao_dic['id_documento']) != None:
        tmp+='\t\t\t\t<setFont name="Helvetica-Bold" size="12"/>\n'
    return tmp

def rodape(dic_rodape):
    """
    Função que gera o codigo rml do rodape da pagina.
    """
    tmp=''
    return tmp

def paraStyle():
    """Função que gera o código rml que define o estilo dos parágrafos"""
    
    tmp=''
    tmp+='\t<stylesheet>\n'
    tmp+='\t\t<blockTableStyle id="tramitacao" spaceBefore="12">\n'
    tmp+='\t\t\t<lineStyle kind="OUTLINE" colorName="black" thickness="0.2"/>\n'
    tmp+='\t\t\t<lineStyle kind="GRID" colorName="black" thickness="0.2"/>\n'
    tmp+='\t\t\t<blockFont name="Helvetica-Bold" size="10" leading="12" start="0,0" stop="-1,0"/>\n'
    tmp+='\t\t\t<blockTopPadding length="2"/>\n'
    tmp+='\t\t\t<blockBottomPadding length="2"/>\n'
    tmp+='\t\t\t<blockAlignment value="CENTER"/>\n'
    tmp+='\t\t\t<blockBackground colorName="#f6f6f6" start="0,0" stop="-1,0"/>\n'
    tmp+='\t\t\t<!--body section-->\n'
    tmp+='\t\t\t<blockFont name="Helvetica" size="8" leading="9" start="0,1" stop="-1,-1"/>\n'
    tmp+='\t\t\t<blockTopPadding length="1" start="0,1" stop="-1,-1"/>\n'
    tmp+='\t\t\t<blockAlignment value="LEFT" start="1,1" stop="-1,-1"/>\n'
    tmp+='\t\t\t<blockValign value="MIDDLE"/>\n'
    tmp+='\t\t</blockTableStyle>\n'
    tmp+='\t\t<blockTableStyle id="Standard_Outline">\n'
    tmp+='\t\t\t<blockAlignment value="LEFT"/>\n'
    tmp+='\t\t\t<blockValign value="TOP"/>\n'
    tmp+='\t\t\t<blockLeftPadding length="0"/>\n'
    tmp+='\t\t</blockTableStyle>\n'
    tmp+='\t\t<initialize>\n'
    tmp+='\t\t\t<paraStyle name="all" alignment="justify"/>\n'
    tmp+='\t\t</initialize>\n'
    tmp+='\t\t<paraStyle name="style.Title" fontName="Helvetica" fontSize="11" leading="13" spaceAfter="2" alignment="RIGHT"/>\n'
    tmp+='\t\t<paraStyle name="p" fontName="Helvetica" fontSize="10.0" leading="14" spaceAfter="1" alignment="JUSTIFY"/>\n'
    tmp+='\t\t<paraStyle name="P1" fontName="Helvetica-Bold" fontSize="12.0" textColor="gray" leading="13" spaceAfter="2" spaceBefore="8" alignment="LEFT"/>\n'
    tmp+='\t\t<paraStyle name="P2" fontName="Helvetica" fontSize="10.0" leading="14" spaceAfter="1" alignment="JUSTIFY"/>\n'
    tmp+='\t\t<paraStyle name="P3" fontName="Helvetica" fontSize="10.0" leading="12" spaceAfter="2" alignment="CENTER"/>\n'
    tmp+='\t\t<paraStyle name="P5" fontName="Helvetica" fontSize="9" leading="9" spaceAfter="3" alignment="CENTER" valign="middle" white-space="nowrap" />\n'
    tmp+='\t</stylesheet>\n'

    return tmp

def tramitacao(tramitacao_dic):
    """
    Função que gera o código rml das funções básicas do relatório
    """

    tmp=''
    tmp+='\t\t<para style="P1">\n'
    tmp+='\t\t\t<font color="white">-</font>\n'
    tmp+='\t\t</para>\n'
    tmp+='<blockTable style="tramitacao" repeatRows="1" colWidths="460">\n'
    tmp+='<tr><td>PROCESSO ADMINISTRATIVO</td></tr>\n'
    tmp+='\t\t</blockTable>\n'
    tmp+='\t\t<para style="P2">\n'
    tmp+='\t\t\t<font color="white">-</font>\n'
    tmp+='\t\t</para>\n'

    tmp+='\t\t<para style="P2">' + escape(tramitacao_dic['id_documento']) + '</para>\n\n'

    tmp+='\t\t<para style="P2">\n'
    tmp+='\t\t\t<font color="white">-</font>\n'
    tmp+='\t\t</para>\n'
    tmp+='\t\t<para style="P2">\n'
    tmp+='\t\t\t<font color="white"> </font>\n'
    tmp+='\t\t</para>\n'
    tmp+='<blockTable style="tramitacao" repeatRows="1" colWidths="460">\n'
    tmp+='<tr><td>TRAMITAÇÃO</td></tr>\n'
    tmp+='\t\t</blockTable>\n'
    tmp+='\t\t<para style="P2">\n'
    tmp+='\t\t\t<font color="white">-</font>\n'
    tmp+='\t\t</para>\n'

    tmp+='<blockTable style="Standard_Outline" repeatRows="1" colWidths="110,350">\n'
    tmp+='<tr><td>Data do Despacho</td><td>' +str(tramitacao_dic['dat_tramitacao'])+ '</td></tr>\n'
    tmp+='<tr><td>Unidade de Origem</td><td>' +str(tramitacao_dic['unidade_origem'])+ '</td></tr>\n'
    tmp+='<tr><td>Unidade de Destino</td><td>' +str(tramitacao_dic['unidade_destino'])+ '</td></tr>\n'
    nom_usuario_destino = str(tramitacao_dic['nom_usuario_destino'])
    if nom_usuario_destino != None and nom_usuario_destino != "":
       tmp+='<tr><td>Usuário de Destino</td><td>' +str(tramitacao_dic['nom_usuario_destino'])+ '</td></tr>\n'
    tmp+='<tr><td>Status</td><td>' +str(tramitacao_dic['des_status'])+ '</td></tr>\n'
    dat_fim_prazo = str(tramitacao_dic['dat_fim_prazo'])
    if dat_fim_prazo != None and dat_fim_prazo != "":
       tmp+='<tr><td>Prazo</td><td>' +str(tramitacao_dic['dat_fim_prazo'])+ '</td></tr>\n'
    tmp+='\t\t</blockTable>\n'
    tmp+='\t\t<para style="P2">\n'
    tmp+='\t\t\t<font color="white">-</font>\n'
    tmp+='\t\t</para>\n'

    texto_tramitacao = str(tramitacao_dic['txt_tramitacao'])
    if texto_tramitacao != '' and texto_tramitacao != "None":
      tmp+='<blockTable style="tramitacao" repeatRows="1" colWidths="460">\n'
      tmp+='<tr><td>TEXTO DO DESPACHO</td></tr>\n'
      tmp+='\t\t</blockTable>\n'
      tmp+='\t\t<para style="P2">\n'
      tmp+='\t\t</para>\n'

      tmp+='\t\t<para style="P2">\n'
      tmp+='\t\t\t<font color="white">-</font>\n'
      tmp+='\t\t</para>\n'
      tmp+=html2rml(tramitacao_dic['txt_tramitacao']).replace('&','&amp;')
      tmp+='\t\t<para style="P2">\n'
      tmp+='\t\t\t<font color="white">-</font>\n'
      tmp+='\t\t</para>\n'

    tmp+='\t\t<para style="P3">' + str(dic_rodape['nom_localidade']) +', '+tramitacao_dic['dat_extenso']+ '.</para>\n\n'
    tmp+='\t\t<para style="P2">\n'
    tmp+='\t\t\t<font color="white">-</font>\n'
    tmp+='\t\t</para>\n'
    tmp+='\t\t<para style="P2">\n'
    tmp+='\t\t\t<font color="white">-</font>\n'
    tmp+='\t\t</para>\n'

    tmp+='\t\t<para style="P3"><b>' + str(tramitacao_dic['nom_usuario_origem']) +'</b></para>\n\n'
    tmp+='\t\t<para style="P3">' + str(tramitacao_dic['nom_cargo_usuario_origem']) +'</para>\n\n'

    return tmp

def principal(imagem,dic_rodape,inf_basicas_dic,tramitacao_dic,hdn_url,sessao=''):
    """
    Função principal responsável por chamar as funções que irão gerar o código rml apropriado
    """

    arquivoPdf=str(cod_tramitacao)+"_tram.pdf"

    tmp=''
    tmp+='<?xml version="1.0" encoding="utf-8" standalone="no" ?>\n'
    tmp+='<!DOCTYPE document SYSTEM "rml_1_0.dtd">\n'
    tmp+='<document filename="tramitacao.pdf">\n'
    tmp+='\t<template pageSize="(21cm, 29.7cm)" title="Despacho em Documento Administrativo" author="OpenLegis" allowSplitting="20">\n'
    tmp+='\t\t<pageTemplate id="first">\n'
    tmp+='\t\t\t<pageGraphics>\n'
    tmp+=cabecalho(inf_basicas_dic,imagem)
    tmp+=rodape(dic_rodape)
    tmp+='\t\t\t</pageGraphics>\n'
    tmp+='\t\t\t<frame id="first" x1="3cm" y1="3.5cm" width="16.7cm" height="23cm"/>\n'
    tmp+='\t\t</pageTemplate>\n'
    tmp+='\t</template>\n'
    tmp+=paraStyle()
    tmp+='\t<story>\n'
    tmp+=tramitacao(tramitacao_dic)
    tmp+='\t</story>\n'
    tmp+='</document>\n'
    tmp_pdf=parseString(tmp)

    if hasattr(context.sapl_documentos.administrativo.tramitacao,arquivoPdf):
       arq=context.sapl_documentos.administrativo.tramitacao[arquivoPdf]
       arq.manage_upload(file=tmp_pdf)
    else:       
       context.sapl_documentos.administrativo.tramitacao.manage_addFile(id=arquivoPdf,file=tmp_pdf,content_type='application/pdf',title='Tramitação de processo administrativo')

    for tram in context.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=cod_tramitacao, ind_excluido=0):
        if context.zsql.documento_administrativo_pesquisar_publico_zsql(cod_documento=tram.cod_documento, ind_excluido=0):
           arq =  str(tram.cod_tramitacao)+'_tram.pdf'
           pdf = getattr(context.sapl_documentos.administrativo.tramitacao, arq)
           pdf.manage_permission('View', roles=['Manager','Authenticated','Anonymous'], acquire=1)

    return hdn_url

return principal(imagem, dic_rodape, inf_basicas_dic, tramitacao_dic, hdn_url,sessao)

