## Script (Python) "get_pdf_signatures"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=codigo='', tipo_doc='', cod_solicitante='', cod_usuario='', ind_assinado='', ind_separado=''
##title=

from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

from zlib import crc32

from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')
from zlib import crc32

def get_info(codigo, tipo_doc, anexo):
    descricao, url, tipo_documento, url_pasta = "", "", "", ""

    try:
        if tipo_doc == 'proposicao':
            for metodo in context.zsql.proposicao_obter_zsql(cod_proposicao=codigo):
                tipo_documento = 'Proposição Digital'
                descricao = "%s - %s - %s" % (metodo.des_tipo_proposicao, metodo.nom_autor, metodo.txt_descricao)
                url = "%s/cadastros/proposicao/proposicao_mostrar_proc?cod_proposicao=%s" % (context.portal_url(), codigo)
        elif tipo_doc == 'materia':
            for metodo in context.zsql.materia_obter_zsql(cod_materia=codigo):
                tipo_documento = 'Matéria Legislativa - Texto Integral'
                nom_autor = ''
                for autor in context.zsql.autoria_obter_zsql(cod_materia=codigo, ind_primeiro_autor=1):
                    nom_autor = autor.nom_autor_join
                descricao = "%s nº %s/%s - %s - %s" % (metodo.des_tipo_materia, metodo.num_ident_basica, metodo.ano_ident_basica, nom_autor, metodo.txt_ementa)
                url = "%s/cadastros/materia/materia_mostrar_proc?cod_materia=%s" % (context.portal_url(), codigo)
                url_pasta = "%s/@@pasta_digital?cod_materia=%s&action=pasta" % (context.portal_url(), codigo)
        elif tipo_doc == 'redacao_final':
            for metodo in context.zsql.materia_obter_zsql(cod_materia=codigo):
                tipo_documento = 'Matéria Legislativa - Redação Final'
                nom_autor = ''
                for autor in context.zsql.autoria_obter_zsql(cod_materia=codigo, ind_primeiro_autor=1):
                    nom_autor = autor.nom_autor_join
                descricao = "%s nº %s/%s - %s - %s" % (metodo.des_tipo_materia, metodo.num_ident_basica, metodo.ano_ident_basica, nom_autor, metodo.txt_ementa)
                url = "%s/cadastros/materia/materia_mostrar_proc?cod_materia=%s" % (context.portal_url(), codigo)
                url_pasta = "%s/@@pasta_digital?cod_materia=%s&action=pasta" % (context.portal_url(), codigo)
        elif tipo_doc == 'doc_acessorio':
            for metodo in context.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
                tipo_documento = 'Matéria Legislativa - Documento Acessório'
                materia_txt = ""
                for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                    materia_txt = "%s nº %s/%s - %s" % (materia.des_tipo_materia, materia.num_ident_basica, materia.ano_ident_basica, materia.txt_ementa)
                descricao = "%s - %s - %s" % (metodo.des_tipo_documento, metodo.nom_documento, materia_txt)
                url = "%s/cadastros/materia/materia_mostrar_proc?cod_materia=%s#acessorio" % (context.portal_url(), metodo.cod_materia)
                url_pasta = "%s/@@pasta_digital?cod_materia=%s&action=pasta" % (context.portal_url(), metodo.cod_materia)
        elif tipo_doc == 'emenda':
            for metodo in context.zsql.emenda_obter_zsql(cod_emenda=codigo):
                tipo_documento = 'Matéria Legislativa - Emenda'
                materia_txt = ""
                for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                    materia_txt = "%s nº %s/%s - %s" % (materia.des_tipo_materia, materia.num_ident_basica, materia.ano_ident_basica, materia.txt_ementa)
                nom_autor = ''
                for autor in context.zsql.autoria_emenda_obter_zsql(cod_emenda=codigo, ind_primeiro_autor=1):
                    nom_autor = autor.nom_autor_join
                descricao = "Emenda %s nº %s - %s, ao %s" % (metodo.des_tipo_emenda, metodo.num_emenda, nom_autor, materia_txt)
                url = "%s/cadastros/materia/materia_mostrar_proc?cod_materia=%s#emenda" % (context.portal_url(), metodo.cod_materia)
                url_pasta = "%s/@@pasta_digital?cod_materia=%s&action=pasta" % (context.portal_url(), metodo.cod_materia)
        elif tipo_doc == 'substitutivo':
            for metodo in context.zsql.substitutivo_obter_zsql(cod_substitutivo=codigo):
                tipo_documento = 'Matéria Legislativa - Substitutivo'
                materia_txt = ""
                for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                    materia_txt = "%s nº %s/%s - %s" % (materia.sgl_tipo_materia, materia.num_ident_basica, materia.ano_ident_basica, materia.txt_ementa)
                nom_autor = ''
                for autor in context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=codigo, ind_primeiro_autor=1):
                    nom_autor = autor.nom_autor_join
                descricao = "Substitutivo nº %s - %s, ao %s" % (metodo.num_substitutivo, nom_autor, materia_txt)
                url = "%s/cadastros/materia/materia_mostrar_proc?cod_materia=%s#substitutivo" % (context.portal_url(), metodo.cod_materia)
                url_pasta = "%s/@@pasta_digital?cod_materia=%s&action=pasta" % (context.portal_url(), metodo.cod_materia)
        elif tipo_doc == 'tramitacao':
            for metodo in context.zsql.tramitacao_obter_zsql(cod_tramitacao=codigo):
                tipo_documento = 'Matéria Legislativa - Tramitação'
                materia_txt = ""
                for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                    materia_txt = "%s nº %s/%s - %s" % (materia.des_tipo_materia, materia.num_ident_basica, materia.ano_ident_basica, materia.txt_ementa)
                nom_usuario = ''
                for usuario in context.zsql.usuario_obter_zsql(cod_usuario=metodo.cod_usuario_local):
                    nom_usuario = usuario.nom_completo
                descricao = "Despacho de %s - %s - %s" % (nom_usuario, metodo.des_status, materia_txt)
                url = "%s/cadastros/materia/materia_mostrar_proc?cod_materia=%s#tramitacao" % (context.portal_url(), metodo.cod_materia)
                url_pasta = "%s/@@pasta_digital?cod_materia=%s&action=pasta" % (context.portal_url(), metodo.cod_materia)
        elif tipo_doc == 'parecer_comissao':
            for metodo in context.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
                tipo_documento = 'Matéria Legislativa - Parecer de Comissão'
                sgl_comissao = ""
                for comissao in context.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                    sgl_comissao = comissao.sgl_comissao
                parecer = "%s/%s" % (metodo.num_parecer, metodo.ano_parecer)
                materia_txt = ""
                for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                    materia_txt = "%s nº %s/%s - %s" % (materia.des_tipo_materia, materia.num_ident_basica, materia.ano_ident_basica, materia.txt_ementa)
                descricao = "Parecer %s nº %s ao %s" % (sgl_comissao, parecer, materia_txt)
                url = "%s/cadastros/materia/materia_mostrar_proc?cod_materia=%s#parecer" % (context.portal_url(), metodo.cod_materia)
                url_pasta = "%s/@@pasta_digital?cod_materia=%s&action=pasta" % (context.portal_url(), metodo.cod_materia)
        elif tipo_doc == 'pauta':
            for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
                tipo_documento = "%s Plenária - Pauta" % context.sapl_documentos.props_sagl.reuniao_sessao
                sessao = ""
                for tipo in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                    sessao = "%sª %s %s de %s" % (metodo.num_sessao_plen, context.sapl_documentos.props_sagl.reuniao_sessao, tipo.nom_sessao, metodo.dat_inicio_sessao)
                descricao = "Pauta da %s" % sessao
                url = "%s/cadastros/sessao_plenaria/sessao_plenaria_mostrar_proc?cod_sessao_plen=%s" % (context.portal_url(), metodo.cod_sessao_plen)
            for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia=1):
                tipo_documento = 'Audiência Pública - Pauta'
                sessao = "Audiência Pública nº %s/%s" % (metodo.num_sessao_plen, metodo.ano_sessao)
                descricao = "Pauta da %s" % sessao
                url = "%s/cadastros/sessao_plenaria/audiencia_publica_mostrar_proc?cod_sessao_plen=%s&ind_audiencia=1" % (context.portal_url(), metodo.cod_sessao_plen)
        elif tipo_doc == 'resumo_sessao':
            for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
                tipo_documento = "%s Plenária - Roteiro / Resenha" % context.sapl_documentos.props_sagl.reuniao_sessao
                sessao = ""
                for tipo in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                    sessao = "%sª %s %s de %s" % (metodo.num_sessao_plen, context.sapl_documentos.props_sagl.reuniao_sessao, tipo.nom_sessao, metodo.dat_inicio_sessao)
                descricao = "Roteiro / Resenha da %s" % sessao
                url = "%s/cadastros/sessao_plenaria/sessao_plenaria_mostrar_proc?cod_sessao_plen=%s" % (context.portal_url(), metodo.cod_sessao_plen)
            for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia=1):
                tipo_documento = 'Audiência Pública -  Roteiro / Resenha'
                sessao = "Audiência Pública nº %s/%s" % (metodo.num_sessao_plen, metodo.ano_sessao)
                descricao = "Roteiro / Resenha da %s" % sessao
                url = "%s/cadastros/sessao_plenaria/audiencia_publica_mostrar_proc?cod_sessao_plen=%s&ind_audiencia=1" % (context.portal_url(), metodo.cod_sessao_plen)
        elif tipo_doc == 'ata':
            for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
                tipo_documento = "%s Plenária - Ata" % context.sapl_documentos.props_sagl.reuniao_sessao
                sessao = ""
                for tipo in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                    sessao = "%sª %s %s de %s" % (metodo.num_sessao_plen, context.sapl_documentos.props_sagl.reuniao_sessao, tipo.nom_sessao, metodo.dat_inicio_sessao)
                descricao = "Ata da %s" % sessao
                url = "%s/cadastros/sessao_plenaria/sessao_plenaria_mostrar_proc?cod_sessao_plen=%s" % (context.portal_url(), metodo.cod_sessao_plen)
            for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia=1):
                tipo_documento = 'Audiência Pública - Ata'
                sessao = "Audiência Pública nº %s/%s" % (metodo.num_sessao_plen, metodo.ano_sessao)
                descricao = "Ata da %s" % sessao
                url = "%s/cadastros/sessao_plenaria/audiencia_publica_mostrar_proc?cod_sessao_plen=%s&ind_audiencia=1" % (context.portal_url(), metodo.cod_sessao_plen)
        elif tipo_doc == 'norma':
            for metodo in context.zsql.norma_juridica_obter_zsql(cod_norma=codigo):
                tipo_documento = 'Norma Jurídica - Texto Integral'
                descricao = "%s nº %s/%s - %s" % (metodo.des_tipo_norma, metodo.num_norma, metodo.ano_norma, metodo.txt_ementa)
                url = "%s/cadastros/norma_juridica/norma_juridica_mostrar_proc?cod_norma=%s" % (context.portal_url(), metodo.cod_norma)
                url_pasta = "%s/@@pasta_digital_norma?cod_norma=%s&action=pasta" % (context.portal_url(), metodo.cod_norma)
        elif tipo_doc == 'documento':
            for metodo in context.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
                tipo_documento = 'Processo Administrativo - Texto Integral'
                descricao = "%s nº %s/%s - %s - %s" % (metodo.des_tipo_documento, metodo.num_documento, metodo.ano_documento, metodo.txt_interessado, metodo.txt_assunto)
                url = "%s/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento=%s" % (context.portal_url(), metodo.cod_documento)
                url_pasta = "%s/consultas/documento_administrativo/pasta_digital/?cod_documento=%s&action=pasta" % (context.portal_url(), metodo.cod_documento)
        elif tipo_doc == 'doc_acessorio_adm':
            for metodo in context.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
                tipo_documento = 'Processo Administrativo - Documento Acessório'
                documento_txt = ""
                for documento in context.zsql.documento_administrativo_obter_zsql(cod_documento=metodo.cod_documento):
                    documento_txt = "%s %s/%s - %s - %s" % (documento.sgl_tipo_documento, documento.num_documento, documento.ano_documento, documento.txt_interessado, documento.txt_assunto)
                descricao = "%s %s - %s, juntado ao %s" % (metodo.des_tipo_documento, metodo.nom_documento, metodo.nom_autor_documento, documento_txt)
                url = "%s/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento=%s#acessorios" % (context.portal_url(), metodo.cod_documento)
                url_pasta = "%s/consultas/documento_administrativo/pasta_digital/?cod_documento=%s&action=pasta" % (context.portal_url(), metodo.cod_documento)
        elif tipo_doc == 'tramitacao_adm':
            for metodo in context.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=codigo):
                tipo_documento = 'Processo Administrativo - Tramitação'
                documento_txt = ""
                for documento in context.zsql.documento_administrativo_obter_zsql(cod_documento=metodo.cod_documento):
                    documento_txt = "%s %s/%s - %s - %s" % (documento.sgl_tipo_documento, documento.num_documento, documento.ano_documento, documento.txt_interessado, documento.txt_assunto)
                nom_usuario = ''
                for usuario in context.zsql.usuario_obter_zsql(cod_usuario=metodo.cod_usuario_local):
                    nom_usuario = usuario.nom_completo
                descricao = "Despacho de %s - %s - %s" % (nom_usuario, metodo.des_status, documento_txt)
                url = "%s/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento=%s#tramitacao" % (context.portal_url(), metodo.cod_documento)
                url_pasta = "%s/consultas/documento_administrativo/pasta_digital/?cod_documento=%s&action=pasta" % (context.portal_url(), metodo.cod_documento)
        elif tipo_doc == 'protocolo':
            for metodo in context.zsql.protocolo_obter_zsql(cod_protocolo=codigo):
                tipo_documento = 'Protocolo - Documento'
                autor = metodo.txt_interessado
                if metodo.cod_autor is not None:
                    for autor_rec in context.zsql.autor_obter_zsql(cod_autor=metodo.cod_autor):
                        autor = autor_rec.nom_autor_join
                descricao = "Protocolo nº %s/%s - %s - %s" % (metodo.num_protocolo, metodo.ano_protocolo, autor, metodo.txt_assunto_ementa)
                url = "%s/consultas/protocolo/protocolo_mostrar_proc?cod_protocolo=%s" % (context.portal_url(), metodo.cod_protocolo)
        elif tipo_doc == 'peticao':
            for metodo in context.zsql.peticao_obter_zsql(cod_peticao=codigo):
                tipo_documento = 'Petição Digital - Texto Integral'
                tipo = ''
                for tipo_rec in context.zsql.tipo_peticionamento_obter_zsql(tip_peticionamento=metodo.tip_peticionamento):
                    tipo = tipo_rec.des_tipo_peticionamento
                usuario = ''
                for usuario_rec in context.zsql.usuario_obter_zsql(cod_usuario=metodo.cod_usuario):
                    usuario = usuario_rec.nom_completo
                descricao = "%s - %s - %s" % (tipo, usuario, metodo.txt_descricao)
                url = "%s/cadastros/peticionamento_eletronico/peticao_mostrar_proc?cod_peticao=%s" % (context.portal_url(), metodo.cod_peticao)
        elif tipo_doc == 'anexo_peticao':
            for metodo in context.zsql.peticao_obter_zsql(cod_peticao=codigo):
                tipo_documento = 'Petição Digital - Documento Acessório'
                arqnum = anexo if anexo not in (None, '') else 1
                arquivo = "%s_anexo_%s.pdf" % (metodo.cod_peticao, arqnum)
                try:
                    titulo = getattr(context.sapl_documentos.peticao, arquivo).title_or_id()
                except Exception:
                    titulo = arquivo
                descricao = titulo
                url = "%s/cadastros/peticionamento_eletronico/peticao_mostrar_proc?cod_peticao=%s" % (context.portal_url(), metodo.cod_peticao)
        elif tipo_doc == 'pauta_comissao':
            for metodo in context.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
                tipo_documento = 'Comissão - Pauta de Reunião'
                comissao = ""
                for comissao_rec in context.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                    comissao = comissao_rec.nom_comissao
                descricao = "Pauta da %sª Reunião %s da %s de %s" % (metodo.num_reuniao, metodo.des_tipo_reuniao, comissao, metodo.dat_inicio_reuniao)
                url = "%s/cadastros/comissao/comissao_mostrar_proc?cod_comissao=%s#reuniao" % (context.portal_url(), metodo.cod_comissao)
        elif tipo_doc == 'ata_comissao':
            for metodo in context.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
                tipo_documento = 'Comissão - Ata de Reunião'
                comissao = ""
                for comissao_rec in context.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                    comissao = comissao_rec.nom_comissao
                descricao = "Ata da %sª Reunião %s da %s de %s" % (metodo.num_reuniao, metodo.des_tipo_reuniao, comissao, metodo.dat_inicio_reuniao)
                url = "%s/cadastros/comissao/comissao_mostrar_proc?cod_comissao=%s#reuniao" % (context.portal_url(), metodo.cod_comissao)
        elif tipo_doc == 'documento_comissao':
            for metodo in context.zsql.documento_comissao_obter_zsql(cod_documento=codigo):
                tipo_documento = 'Comissão - Documento'
                comissao = ""
                for comissao_rec in context.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                    comissao = comissao_rec.nom_comissao
                descricao = "%s da %s" % (metodo.txt_descricao, comissao)
                url = "%s/cadastros/comissao/comissao_mostrar_proc?cod_comissao=%s#documento" % (context.portal_url(), metodo.cod_comissao)
        elif tipo_doc == 'anexo_sessao':
            for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
                tipo_documento = "%s Plenária - Anexo" % context.sapl_documentos.props_sagl.reuniao_sessao
                sessao = ""
                for tipo in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                    sessao = "%sª %s %s de %s" % (metodo.num_sessao_plen, context.sapl_documentos.props_sagl.reuniao_sessao, tipo.nom_sessao, metodo.dat_inicio_sessao)
                arqnum = anexo if anexo not in (None, '') else 1
                arquivo = "%s_anexo_%s.pdf" % (metodo.cod_sessao_plen, arqnum)
                try:
                    titulo = getattr(context.sapl_documentos.anexo_sessao, arquivo).title_or_id()
                except Exception:
                    titulo = arquivo
                descricao = "%s da %s" % (titulo, sessao)
                url = "%s/cadastros/sessao_plenaria/sessao_plenaria_mostrar_proc?cod_sessao_plen=%s" % (context.portal_url(), metodo.cod_sessao_plen)
            for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia=1):
                tipo_documento = 'Audiência Pública - Documento'
                sessao = "Audiência Pública nº %s/%s" % (metodo.num_sessao_plen, metodo.ano_sessao)
                arqnum = anexo if anexo not in (None, '') else 1
                arquivo = "%s_anexo_%s.pdf" % (metodo.cod_sessao_plen, arqnum)
                try:
                    titulo = getattr(context.sapl_documentos.anexo_sessao, arquivo).title_or_id()
                except Exception:
                    titulo = arquivo
                descricao = "%s da %s" % (titulo, sessao)
                url = "%s/cadastros/sessao_plenaria/audiencia_publica_mostrar_proc?cod_sessao_plen=%s&ind_audiencia=1" % (context.portal_url(), metodo.cod_sessao_plen)
    except Exception as e:
        descricao = "Erro ao buscar documento: %s" % e
        url = ""
        tipo_documento = tipo_doc
        url_pasta = ""

    for storage in context.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
        location = storage.pdf_location
        if anexo != None and anexo != '':
           codigo = str(codigo) + '_anexo_' + str(anexo)
           pdf_signed = str(location) + str(codigo) + str(storage.pdf_signed)
           pdf_file = str(location) + str(codigo) + str(storage.pdf_file)
           nom_arquivo = str(codigo) + str(storage.pdf_file)
           nom_arquivo_assinado = str(codigo) + str(storage.pdf_signed)
        else:
           pdf_signed = str(location) + str(codigo) + str(storage.pdf_signed)
           pdf_file = str(location) + str(codigo) + str(storage.pdf_file)
           nom_arquivo = str(codigo) + str(storage.pdf_file)
           nom_arquivo_assinado = str(codigo) + str(storage.pdf_signed)

    return descricao or "", url or "", tipo_documento or tipo_doc, url_pasta or ""

# Gerar itens pendentes de assinatura
lista = []
for item in context.zsql.assinatura_documento_pendente_obter_zsql(
    codigo=codigo,
    tipo_doc=tipo_doc,
    cod_solicitante=cod_solicitante,
    cod_usuario=cod_usuario,
    ind_assinado=ind_assinado,
    ind_separado=ind_separado
):
    dic_documento = {}
    dic_documento['cod_assinatura_doc'] = item['cod_assinatura_doc']
    dic_documento['codigo'] = item['codigo']
    dic_documento['tipo_doc'] = item['tipo_doc']
    dic_documento['cod_solicitante_documento'] = None
    dic_documento['nome_solicitante_documento'] = None
    if item.cod_solicitante is not None:
        dic_documento['cod_solicitante_documento'] = item.cod_solicitante
        for usuario in context.zsql.usuario_obter_zsql(cod_usuario=item.cod_solicitante):
            dic_documento['nome_solicitante_documento'] = usuario.nom_completo
    dic_documento['anexo'] = item['anexo']
    dic_documento['visual_page_option'] = item.visual_page_option

    dados = get_info(
        codigo=item['codigo'],
        tipo_doc=item['tipo_doc'],
        anexo=item['anexo']
    )
    dic_documento['id_documento'] = dados[0]
    dic_documento['link_registro'] = dados[1]
    dic_documento['tipo_documento'] = dados[2]
    dic_documento['url_pasta'] = dados[3]

    pdf_tosign, storage_path, crc_arquivo = st.get_file_tosign(item['codigo'], item['anexo'], item['tipo_doc'])
    if hasattr(storage_path, pdf_tosign):
        arq = getattr(storage_path, pdf_tosign)
        dic_documento['link_pdf'] = arq.absolute_url()
        dic_documento['pdf_to_sign'] = arq.absolute_url()
        dic_documento['crc_arquivo'] = crc_arquivo
    else:
        dic_documento['link_pdf'] = None
        dic_documento['pdf_to_sign'] = None
        dic_documento['crc_arquivo'] = None

    dic_documento['assinados'] = []
    dic_documento['pendentes'] = []
    dic_documento['recusados'] = []

    for assinatura in context.zsql.assinatura_documento_obter_zsql(cod_assinatura_doc=item['cod_assinatura_doc']):
        dic = {}
        dic['cod_solicitante'] = assinatura.cod_solicitante
        dic['nom_solicitante'] = None
        if assinatura.cod_solicitante is not None:
            for usuario in context.zsql.usuario_obter_zsql(cod_usuario=assinatura.cod_solicitante):
                dic['nom_solicitante'] = usuario.col_username
        dic['cod_usuario'] = assinatura.cod_usuario
        dic['nome_usuario'] = assinatura.nom_completo
        dic['primeiro_signatario'] = assinatura.ind_prim_assinatura
        dic['dat_solicitacao'] = assinatura.dat_solicitacao
        dic['dat_assinatura'] = assinatura.dat_assinatura
        dic['dat_recusa'] = assinatura.dat_recusa
        dic['txt_motivo_recusa'] = assinatura.txt_motivo_recusa
        if assinatura.dat_assinatura is not None:
            dic_documento['assinados'].append(dic)
        if assinatura.dat_assinatura is None and assinatura.dat_recusa is None:
            dic_documento['pendentes'].append(dic)
        if assinatura.dat_assinatura is None and assinatura.dat_recusa is not None:
            dic_documento['recusados'].append(dic)

    dic_documento['assinados'].sort(key=lambda dic: dic['nome_usuario'])
    dic_documento['pendentes'].sort(key=lambda dic: dic['nome_usuario'])
    dic_documento['recusados'].sort(key=lambda dic: dic['nome_usuario'])
    lista.append(dic_documento)

return lista
