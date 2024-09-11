##parameters=dic_cabecalho, dic_rodape, imagem, pauta_dic

"""Ordem do Dia
"""
from trml2pdf import parseString
from io import BytesIO
from xml.sax.saxutils import escape

def cabecalho(dic_cabecalho, imagem):
    """Gera o codigo rml do cabecalho"""
    tmp=''
    tmp+='\t\t\t\t<image x="2.5cm" y="27.4cm" width="74" height="60" file="' + imagem + '"/>\n'
    tmp+='\t\t\t\t<lines>1.7cm 27.1cm 19.3cm 27.1cm</lines>\n'
    tmp+='\t\t\t\t<setFont name="Helvetica-Bold" size="15"/>\n'
    tmp+='\t\t\t\t<drawString x="6cm" y="28.5cm">' + dic_cabecalho["nom_casa"] + '</drawString>\n'
    tmp+='\t\t\t\t<setFont name="Helvetica" size="11"/>\n'
    tmp+='\t\t\t\t<drawString x="6cm" y="28cm">' + 'Estado de ' + dic_cabecalho["nom_estado"] + '</drawString>\n'
    return tmp

def rodape(dic_rodape):
    """ Gera o codigo rml do rodape"""
    tmp=''
    tmp=''
    tmp+='\t\t\t\t<lines>1.7cm 1.3cm 19.3cm 1.3cm</lines>\n'
    tmp+='\t\t\t\t<setFont name="Helvetica" size="8"/>\n'
    tmp+='\t\t\t\t<drawString x="1.7cm" y="1.4cm">' + dic_rodape[2] + '</drawString>\n'
    tmp+='\t\t\t\t<drawString x="18.1cm" y="1.4cm">Página <pageNumber/></drawString>\n'
    tmp+='\t\t\t\t<drawCentredString x="10.5cm" y="0.9cm">' + dic_rodape[0] + '</drawCentredString>\n'
    tmp+='\t\t\t\t<drawCentredString x="10.5cm" y="0.6cm">' + dic_rodape[1] + '</drawCentredString>\n'

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
    tmp+='\t\t<paraStyle name="P2" fontName="Helvetica" fontSize="12" leading="14" alignment="JUSTIFY"/>\n'
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
    if pauta_dic["nom_sessao"] == 'AUDIÊNCIA PÚBLICA':
       tmp+='\t\t<para style="P0">'+ str(pauta_dic["num_sessao_plen"]) +'ª '+ pauta_dic["nom_sessao"] + ' DA ' + str(pauta_dic["num_legislatura"]) + 'ª LEGISLATURA,' + '</para>\n'
       tmp+='\t\t<para style="P2" spaceAfter="4">\n'
       tmp+='\t\t\t<font color="white"> </font>\n'
       tmp+='\t\t</para>\n'
       tmp+='\t\t<para style="P0">EM ' + str(pauta_dic["dia_sessao"]) + ', ÀS ' + str(pauta_dic["hr_inicio_sessao"]) + 'HS' + '</para>\n'
       tmp+='\t\t<para style="P2" spaceAfter="4" spaceBefore="10">\n'
       tmp+='\t\t\t<font color="white"> </font>\n'
       tmp+='\t\t</para>\n'
    else:
       if pauta_dic["num_periodo"] != '':
          tmp+='\t\t<para style="P0">'+ str(pauta_dic["num_sessao_plen"]) +'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + pauta_dic["nom_sessao"] + ' DO ' + str(pauta_dic["num_periodo"]) + 'º PERÍODO - ' + pauta_dic["dat_inicio_sessao"] + '</para>\n'
       else:
          tmp+='\t\t<para style="P0">'+ str(pauta_dic["num_sessao_plen"]) +'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + pauta_dic["nom_sessao"] + ' - ' + pauta_dic["dat_inicio_sessao"] + '</para>\n'
       tmp+='\t\t<para style="P2" spaceAfter="4">\n'
       tmp+='\t\t\t<font color="white"> </font>\n'
       tmp+='\t\t</para>\n'
       tmp+='\t\t<para style="P0">' + str(pauta_dic["num_sessao_leg"]) +'ª SESSÃO LEGISLATIVA' + ' - ' + str(pauta_dic["num_legislatura"]) + 'ª LEGISLATURA' + '</para>\n'
       tmp+='\t\t<para style="P2" spaceAfter="4" spaceBefore="10">\n'
       tmp+='\t\t\t<font color="white"> </font>\n'
       tmp+='\t\t</para>\n'

    if pauta_dic["txt_tema"] != None and pauta_dic["txt_tema"] != '':
       tmp+='\t\t<para style="P1" spaceBefore="20"><b><u>TEMA</u></b></para>\n\n'
       tmp+='\t\t<para style="P2" spaceAfter="5">\n'
       tmp+='\t\t\t<font color="white"> </font>\n'
       tmp+='\t\t</para>\n'
       #condicao para a quebra de pagina
       tmp+='\t\t<para style="P1" spaceBefore="20" spaceAfter="20">' + pauta_dic["txt_tema"] + '</para>\n'


    if pauta_dic["lst_expedientes"] != [] or pauta_dic["lst_materia_apresentada"] or pauta_dic["lst_materia_apresentada"] != [] or pauta_dic["lst_requerimentos_vereadores"] != [] or pauta_dic["lst_mocoes_vereadores"] != []:
       tmp+='\t\t<para style="P0"><b><u>EXPEDIENTE</u></b></para>\n\n'
    for dic in pauta_dic["lst_expedientes"]:
        #espaco inicial
        tmp+='\t\t<para style="P2" spaceAfter="5">\n'
        tmp+='\t\t\t<font color="white"> </font>\n'
        tmp+='\t\t</para>\n'
        #condicao para a quebra de pagina
        tmp+='\t\t<condPageBreak height="18mm"/>\n'
        tmp+='\t\t<para style="P1" spaceBefore="10" spaceAfter="10"><b>' + dic['nom_expediente'].upper() + '</b></para>\n'
        tmp+='\t\t<para style="P2" spaceBefore="5" spaceAfter="2">' + dic['conteudo'] + '</para>\n'

    if pauta_dic["lst_materia_apresentada"] != []:
        tmp+='\t\t<para style="P1" spaceBefore="20" spaceAfter="10"><b>LEITURA DE MATÉRIAS</b></para>\n'
    for dic in pauta_dic["lst_materia_apresentada"]:
        tmp+='\t\t<condPageBreak height="20mm"/>\n'
        tmp+='\t\t<para style="P2" spaceAfter="2">' + str(dic['num_ordem']) +') <font color="#126e90"><b>' + dic['id_materia'] + '</b></font> - Autoria: ' + dic['autoria'] + '</para>\n'
        tmp+='\t\t<para style="P2" spaceAfter="10">' + escape(dic['txt_ementa']) + '</para>\n'

    if pauta_dic["lst_indicacoes_vereadores"] != []:
        tmp+='\t\t<condPageBreak height="20mm"/>\n'
        tmp+='\t\t<para style="P1" spaceBefore="20"><b>LEITURA DE INDICAÇÕES</b></para>\n'
    for dic in pauta_dic["lst_indicacoes_vereadores"]:
        tmp+='\t\t<para style="P2" spaceBefore="10"><b><u>' + dic['vereador'] + '</u></b>:</para>\n'
        for item in dic['materias']:
            tmp+='\t\t<para style="P2" spaceBefore="5"><font color="#126e90"><b>' + item['id_materia'] + '</b></font> - ' + escape(item['txt_ementa']) + '</para>\n'

    if pauta_dic["lst_requerimentos_vereadores"] != []:
        tmp+='\t\t<condPageBreak height="20mm"/>\n'
        tmp+='\t\t<para style="P1" spaceBefore="20"><b>DISCUSSÃO E VOTAÇÃO DE REQUERIMENTOS</b></para>\n'
    for dic in pauta_dic["lst_requerimentos_vereadores"]:
        tmp+='\t\t<para style="P2" spaceBefore="10"><b><u>' + dic['vereador'] + '</u></b>:</para>\n'
        for item in dic['materias']:
            tmp+='\t\t<para style="P2" spaceBefore="5"><font color="#126e90"><b>' + item['id_materia'] + '</b></font> - ' + escape(item['txt_ementa']) + '</para>\n'

    if pauta_dic["lst_mocoes_vereadores"] != []:
        tmp+='\t\t<condPageBreak height="20mm"/>\n'
        tmp+='\t\t<para style="P1" spaceBefore="20"><b>DISCUSSÃO E VOTAÇÃO DE MOÇÕES</b></para>\n'
    for dic in pauta_dic["lst_mocoes_vereadores"]:
        tmp+='\t\t<para style="P2" spaceBefore="10"><b><u>' + dic['vereador'] + '</u></b>:</para>\n'
        for item in dic['materias']:
            tmp+='\t\t<para style="P2" spaceBefore="5"><font color="#126e90"><b>' + item['id_materia'] + '</b></font> - ' + item['txt_ementa'] + '</para>\n'


    if pauta_dic["lst_urgencia"] != []:
        tmp+='\t\t<condPageBreak height="20mm"/>\n'
        if pauta_dic["nom_sessao"] == 'AUDIÊNCIA PÚBLICA':
           tmp+='\t\t<para style="P0" spaceBefore="20" spaceAfter="10"><b><u>PAUTA - URGÊNCIA ESPECIAL</u></b></para>\n\n'
        else:
           tmp+='\t\t<para style="P0" spaceBefore="20" spaceAfter="10"><b><u>PAUTA - URGÊNCIA ESPECIAL</u></b></para>\n\n'
    for dic in pauta_dic["lst_urgencia"]:
        tmp+='\t\t<para style="P2" spaceBefore="15" spaceAfter="3"><b>' + str(dic['num_ordem']) +'</b>) <font color="#126e90"><b>' + dic['id_materia'] + '</b></font> - Autoria: ' + dic['nom_autor'] + '</para>\n'
        tmp+='\t\t<para style="P2" spaceAfter="3">' + escape(dic['txt_ementa']) + '</para>\n'

        tmp+='\t\t<para style="P3" spaceAfter="3"><b>Turno</b>: '+ dic["des_turno"] +' | <b>Quorum</b>: '+ dic['des_quorum']+' | <b>Tipo de Votação</b>: '+ dic['tip_votacao'] + '' + '</para>\n'

        if dic['parecer']!= 0 and dic['parecer']!= '':
            tmp+='\t\t<para style="P3" spaceAfter="3"><b>Pareceres de Comissões Permanentes:</b></para>\n\n'
            for item in dic['pareceres']:
                tmp+='\t\t<para style="P3" spaceAfter="2"><font color="#126e90">' + item["id_parecer"] + '</font> - ' + item["conclusao"] + ' ' + item["relatoria"] + '</para>\n'

        if dic['substitutivo']!= 0 and dic['substitutivo']!= '':
            tmp+='\t\t<para style="P3" spaceAfter="3"><b>Substitutivo:</b></para>\n\n'     
            for substitutivo in dic['substitutivos']:
                tmp+='\t\t<para style="P3" spaceAfter="3"><b><font color="#126e90">' + substitutivo["id_substitutivo"] + '</font> - ' + substitutivo["autoria"] + '</b> - ' + escape(substitutivo['txt_ementa']) + '</para>\n'

        if dic['emenda']!= 0 and dic['emenda']!= '':
            tmp+='\t\t<para style="P3" spaceAfter="3"><b>Emendas:</b></para>\n\n'
            for emenda in dic['emendas']:
                tmp+='\t\t<para style="P3" spaceAfter="3"><b><font color="#126e90">' + emenda["id_emenda"] + '</font> - ' + emenda["autoria"] + '</b> - ' + escape(emenda['txt_ementa']) + '</para>\n'


    if pauta_dic["lst_pauta"] != []:
        tmp+='\t\t<condPageBreak height="20mm"/>\n'
        if pauta_dic["nom_sessao"] == 'AUDIÊNCIA PÚBLICA':
           tmp+='\t\t<para style="P0" spaceBefore="20" spaceAfter="10"><b><u>PAUTA</u></b></para>\n\n'
        else:
           tmp+='\t\t<para style="P0" spaceBefore="20" spaceAfter="10"><b><u>ORDEM DO DIA</u></b></para>\n\n'
    for dic in pauta_dic["lst_pauta"]:
        tmp+='\t\t<para style="P2" spaceBefore="15" spaceAfter="3"><b>' + str(dic['num_ordem']) +'</b>) <font color="#126e90"><b>' + dic['id_materia'] + '</b></font> - Autoria: ' + dic['nom_autor'] + '</para>\n'
        tmp+='\t\t<para style="P2" spaceAfter="3">' + escape(dic['txt_ementa']) + '</para>\n'

        tmp+='\t\t<para style="P3" spaceAfter="3"><b>Turno</b>: '+ dic["des_turno"] +' | <b>Quorum</b>: '+ dic['des_quorum']+' | <b>Tipo de Votação</b>: '+ dic['tip_votacao'] + '' + '</para>\n'

        if dic['parecer']!= 0 and dic['parecer']!= '':
            tmp+='\t\t<para style="P3" spaceAfter="3"><b>Pareceres de Comissões Permanentes:</b></para>\n\n'
            for item in dic['pareceres']:
                tmp+='\t\t<para style="P3" spaceAfter="2"><font color="#126e90">' + item["id_parecer"] + '</font> - ' + item["conclusao"] + ' ' + item["relatoria"] + '</para>\n'

        if dic['substitutivo']!= 0 and dic['substitutivo']!= '':
            tmp+='\t\t<para style="P3" spaceAfter="3"><b>Substitutivo:</b></para>\n\n'     
            for substitutivo in dic['substitutivos']:
                tmp+='\t\t<para style="P3" spaceAfter="3"><b><font color="#126e90">' + substitutivo["id_substitutivo"] + '</font> - ' + substitutivo["autoria"] + '</b> - ' + escape(substitutivo['txt_ementa']) + '</para>\n'

        if dic['emenda']!= 0 and dic['emenda']!= '':
            tmp+='\t\t<para style="P3" spaceAfter="3"><b>Emendas:</b></para>\n\n'           
            for emenda in dic['emendas']:
                tmp+='\t\t<para style="P3" spaceAfter="3"><b><font color="#126e90">' + emenda["id_emenda"] + '</font> - ' + emenda["autoria"] + '</b> - ' + escape(emenda['txt_ementa']) + '</para>\n'

    if pauta_dic["nom_sessao"] != 'AUDIÊNCIA PÚBLICA':
       tmp+='\t\t<para style="P4" spaceBefore="40" spaceAfter="2"><b>' + pauta_dic["presidente"] + '</b></para>\n'
       tmp+='\t\t<para style="P4">Presidente </para>\n'
    
    # fim do bloco 
    tmp+='\t</story>\n'
    return tmp

def principal(dic_cabecalho, dic_rodape, imagem, pauta_dic):
    arquivoPdf=str(pauta_dic["cod_sessao_plen"])+"_pauta_sessao.pdf"
    tmp=''
    tmp+='<?xml version="1.0" encoding="utf-8" standalone="no" ?>\n'
    tmp+='<!DOCTYPE document SYSTEM "rml_1_0.dtd">\n'
    tmp+='<document filename="pauta.pdf">\n'
    tmp+='\t<template pageSize="(21cm, 29.7cm)" title="Pauta" author="SAGL" allowSplitting="20">\n'
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
        arq=getattr(context.sapl_documentos.pauta_sessao, arquivoPdf)
        arq.manage_upload(file=tmp_pdf)
    else:
       context.sapl_documentos.pauta_sessao.manage_addFile(id=arquivoPdf,file=tmp_pdf, title=arquivoPdf)
   
    return "sapl_documentos/pauta_sessao/"+arquivoPdf

return principal(dic_cabecalho, dic_rodape, imagem, pauta_dic)

