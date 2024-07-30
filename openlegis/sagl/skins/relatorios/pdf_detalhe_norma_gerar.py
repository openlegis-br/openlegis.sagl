##parameters=imagem, dic_rodape,inf_basicas_dic,lst_assuntos,lst_vinculos_ativos,lst_vinculos_passivos,sessao=''

from trml2pdf import parseString
from xml.sax.saxutils import escape
import time

def cabecalho(inf_basicas_dic,imagem):
    """
    Função que gera o código rml do cabeçalho da página
    """
    tmp=''
    tmp+='\t\t\t\t<image x="3.1cm" y="26.9cm" width="60" height="60" file="' + imagem + '"/>\n'
    tmp+='\t\t\t\t<lines>3.3cm 26.3cm 19.5cm 26.3cm</lines>\n'
    tmp+='\t\t\t\t<setFont name="Helvetica-Bold" size="15"/>\n'
    tmp+='\t\t\t\t<drawString x="6.7cm" y="28.1cm">' + inf_basicas_dic['nom_camara'] + '</drawString>\n'
    tmp+='\t\t\t\t<setFont name="Helvetica" size="11"/>\n'
    tmp+='\t\t\t\t<drawString x="6.7cm" y="27.6cm">' + inf_basicas_dic['nom_estado'] + '</drawString>\n'

    return tmp

def rodape(dic_rodape):
    """
    Função que gera o codigo rml do rodape da pagina.
    """

    tmp=''
    linha1 = dic_rodape['end_casa']
    if dic_rodape['end_casa']!="" and dic_rodape['end_casa']!=None:
        linha1 = linha1 + " - "
    if dic_rodape['num_cep']!="" and dic_rodape['num_cep']!=None:
        linha1 = linha1 + "CEP " + dic_rodape['num_cep']
    if dic_rodape['nom_localidade']!="" and dic_rodape['nom_localidade']!=None:
        linha1 = linha1 + " - " + dic_rodape['nom_localidade']
    if dic_rodape['sgl_uf']!="" and dic_rodape['sgl_uf']!=None:
        inha1 = linha1 + " " + dic_rodape['sgl_uf']
    if dic_rodape['num_tel']!="" and dic_rodape['num_tel']!=None:
        linha1 = linha1 + " Tel: "+ dic_rodape['num_tel']
    if dic_rodape['data_emissao']!="" and dic_rodape['data_emissao']!=None:
        data_emissao = dic_rodape['data_emissao']

    tmp+='\t\t\t\t<lines>3.3cm 2.0cm 19.5cm 2.0cm</lines>\n'
    tmp+='\t\t\t\t<setFont name="Helvetica" size="8"/>\n'
    tmp+='\t\t\t\t<drawString x="3.3cm" y="2.2cm">' + data_emissao + '</drawString>\n'
    tmp+='\t\t\t\t<drawString x="18.4cm" y="2.2cm">Página <pageNumber/></drawString>\n'
    tmp+='\t\t\t\t<drawCentredString x="11.5cm" y="1.6cm">' + linha1 + '</drawCentredString>\n'

    return tmp

def paraStyle():
    """Função que gera o código rml que define o estilo dos parágrafos"""
    
    tmp=''
    tmp+='\t<stylesheet>\n'
    tmp+='\t\t<blockTableStyle id="Standard_Outline">\n'
    tmp+='\t\t\t<blockAlignment value="LEFT"/>\n'
    tmp+='\t\t\t<blockValign value="TOP"/>\n'
    tmp+='\t\t</blockTableStyle>\n'
    tmp+='\t\t<initialize>\n'
    tmp+='\t\t\t<paraStyle name="all" alignment="justify"/>\n'
    tmp+='\t\t</initialize>\n'
    tmp+='\t\t<paraStyle name="style.Title" fontName="Helvetica" fontSize="11" leading="13" spaceAfter="2" alignment="RIGHT"/>\n'
    tmp+='\t\t<paraStyle name="P1" fontName="Helvetica-Bold" fontSize="12.0" textColor="gray" leading="14" spaceAfter="2" spaceBefore="8" alignment="LEFT"/>\n'
    tmp+='\t\t<paraStyle name="P2" fontName="Helvetica" fontSize="10.0" leading="12" spaceAfter="2" alignment="LEFT"/>\n'
    tmp+='\t\t<paraStyle name="P3" fontName="Helvetica-Bold" fontSize="12.0" leading="12" alignment="CENTER"/>\n'
    tmp+='\t\t<paraStyle name="texto_projeto" fontName="Helvetica" fontSize="11.0" leading="14" spaceAfter="5" alignment="JUSTIFY"/>\n'
    tmp+='\t</stylesheet>\n'

    return tmp

def inf_basicas(inf_basicas_dic):
    """
    Função que gera o código rml das funções básicas do relatório
    """
    tmp=''
    tmp+='\t\t<para style="P2"></para>\n'
    tmp+='\t\t<para style="P2"></para>\n'
    tmp+='\t\t<para style="P2"></para>\n'
    tmp+='\t\t<para style="P3">'+ str(inf_basicas_dic['titulo']) +'</para>\n'

    #ementa da norma
    txt_ementa = str(inf_basicas_dic['txt_ementa'])
    if txt_ementa != "" and txt_ementa != None :
        tmp+='\t\t<para style="P2"></para>\n'
        tmp+='\t\t<para style="P2"></para>\n'
        tmp+='\t\t<para style="P2"></para>\n'
        tmp+='\t\t<para style="P2"></para>\n'
        tmp+='\t\t<para style="P2"></para>\n'
        tmp+='\t\t<para style="texto_projeto">' + escape(inf_basicas_dic['txt_ementa']) + '</para>\n'

    indexacao = inf_basicas_dic['indexacao']
    observacao = inf_basicas_dic['observacao']

    #iní­cio das informações básicas
    if indexacao != "" and indexacao != None or observacao != "" and observacao != None:
        tmp+='\t\t<para style="P1">Dados Básicos</para>\n'

    if indexacao != "" and indexacao != None:
        tmp+='\t\t<para style="P2"><b>Indexação: </b> ' + indexacao.replace('&','&amp;') + '</para>\n'

    if observacao != "" and observacao != None:
        tmp+='\t\t<para style="P2"><b>Observações: </b> ' + observacao.replace('&','&amp;') + '</para>\n'

    materia = inf_basicas_dic['materia_vinculada']
    if materia!=" " and materia!= None:
        tmp+='\t\t<para style="P1">Matéria Originária</para>\n'
        tmp+='\t\t<para style="P2">' + str(materia) + '</para>\n'

    veiculo = inf_basicas_dic['veiculo_publicacao']
    data_publicacao = inf_basicas_dic['dat_publicacao']

    if veiculo != "" and veiculo != None or data_publicacao != "" and data_publicacao != None:
        tmp+='\t\t<para style="P1">Publicação</para>\n'
        tmp+='\t\t<para style="P2"><b>Veículo: </b> ' + veiculo + '</para>\n'
        tmp+='\t\t<para style="P2"><b>Data: </b> ' + data_publicacao + '</para>\n'

    #situacao
    if str(inf_basicas_dic['situacao_norma']) != "" and str(inf_basicas_dic['situacao_norma']) != None:
        tmp+='\t\t<para style="P1">Situação de Vigência</para>\n'
        tmp+='\t\t<para style="P2">' + str(inf_basicas_dic['situacao_norma']) + '</para>\n'

    return tmp

def assuntos(lst_assuntos):
    tmp=''
    if assuntos != " " and assuntos != None:
        tmp+='\t\t<para style="P1">Assuntos / Classificação</para>\n'
    for assuntos_dic in lst_assuntos:
        tmp+='\t\t<para style="P2">' +  assuntos_dic['assunto'] + '</para>\n'

    return tmp

def vinculos_ativos(lst_vinculos_ativos):
    tmp=''
    if vinculos_ativos != " " or vinculos_ativos != None:
       tmp+='\t\t<para style="P1">Vinculação Ativa</para>\n'
    for vinculos_ativos_dic in lst_vinculos_ativos:
        if vinculos_ativos_dic['norma'] != " " or vinculos_ativos_dic['norma'] != None:
            tmp+='\t\t<para style="P2">' + vinculos_ativos_dic['norma'] + '</para>\n'

    return tmp

def vinculos_passivos(lst_vinculos_passivos):
    tmp=''
    if vinculos_passivos != " " or vinculos_passivos != None:
       tmp+='\t\t<para style="P1">Vinculação Passiva</para>\n'
    for vinculos_passivos_dic in lst_vinculos_passivos:
        if vinculos_passivos_dic['norma'] != " " or vinculos_passivos_dic['norma']  != None:
           tmp+='\t\t<para style="P2">' +  vinculos_passivos_dic['norma'] + '</para>\n'

    return tmp

def principal(imagem, dic_rodape,inf_basicas_dic,lst_assuntos,lst_vinculos_ativos,lst_vinculos_passivos,sessao=''):
    """
    Função principal responsável por chamar as funções que irão gerar o código rml apropriado
    """

    arquivoPdf=str(int(time.time()*100))+".pdf"

    tmp=''
    tmp+='<?xml version="1.0" encoding="utf-8" standalone="no" ?>\n'
    tmp+='<!DOCTYPE document SYSTEM "rml_1_0.dtd">\n'
    tmp+='<document filename="relatorio.pdf">\n'
    tmp+='\t<template pageSize="(21cm, 29.7cm)" title="Relatorio de Norma" author="OpenLegis" allowSplitting="20">\n'
    tmp+='\t\t<pageTemplate id="first">\n'
    tmp+='\t\t\t<pageGraphics>\n'
    tmp+=cabecalho(inf_basicas_dic,imagem)
    tmp+=rodape(dic_rodape)
    tmp+='\t\t\t</pageGraphics>\n'
    tmp+='\t\t\t<frame id="first" x1="3cm" y1="2.6cm" width="16cm" height="23.5cm"/>\n'
    tmp+='\t\t</pageTemplate>\n'
    tmp+='\t</template>\n'
    tmp+=paraStyle()
    tmp+='\t<story>\n'
    tmp+=inf_basicas(inf_basicas_dic)
    #tmp+=assuntos(lst_assuntos)
    tmp+=vinculos_ativos(lst_vinculos_ativos)
    tmp+=vinculos_passivos(lst_vinculos_passivos)
    tmp+='\t</story>\n'
    tmp+='</document>\n'
    tmp_pdf=parseString(tmp)

    if hasattr(context.temp_folder,arquivoPdf):
        context.temp_folder.manage_delObjects(ids=arquivoPdf)
    context.temp_folder.manage_addFile(arquivoPdf)
    arq=context.temp_folder[arquivoPdf]
    arq.manage_edit(title='Arquivo PDF temporário.',filedata=tmp_pdf,content_type='application/pdf')

    return "/temp_folder/"+arquivoPdf

return principal(imagem, dic_rodape,inf_basicas_dic,lst_assuntos,lst_vinculos_ativos,lst_vinculos_passivos,sessao)
