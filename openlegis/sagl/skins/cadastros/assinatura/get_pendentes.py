## Script (Python) "get_pdf_signatures"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=codigo='', tipo_doc='', cod_solicitante='', cod_usuario='', ind_assinado='', ind_separado=''
##title=
##
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

from zlib import crc32

def get_info(codigo, tipo_doc, anexo):
    for storage in context.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
        tipo_doc = storage.tip_documento
        usuario = None
        descricao = None
        url = None
        tipo_documento = None
        url_pasta = None
        if tipo_doc == 'proposicao':
           for metodo in context.zsql.proposicao_obter_zsql(cod_proposicao=codigo):
               tipo_documento = 'Proposição Digital'
               descricao = str(metodo.des_tipo_proposicao) + ' - ' + str(metodo.nom_autor) +  ' - ' + str(metodo.txt_descricao)
               url = context.portal_url() + '/cadastros/proposicao/proposicao_mostrar_proc?cod_proposicao=' + str(codigo)
        elif tipo_doc == 'materia':
           for metodo in context.zsql.materia_obter_zsql(cod_materia=codigo):
               tipo_documento = 'Matéria Legislativa - Texto Integral'
               nom_autor = ''
               for autor in context.zsql.autoria_obter_zsql(cod_materia = codigo, ind_primeiro_autor=1):
                   nom_autor = autor.nom_autor_join
               descricao = str(metodo.des_tipo_materia) + ' nº ' + str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica) + ' - ' + str(nom_autor) +  ' - ' + str(metodo.txt_ementa)
               url = context.portal_url() + '/cadastros/materia/materia_mostrar_proc?cod_materia=' + str(codigo)
               url_pasta = context.portal_url() + '/consultas/materia/pasta_digital/?cod_materia=' + str(codigo) + '&action=pasta'
        elif tipo_doc == 'redacao_final':
           for metodo in context.zsql.materia_obter_zsql(cod_materia=codigo):
               tipo_documento = 'Matéria Legislativa - Redação Final'
               nom_autor = ''
               for autor in context.zsql.autoria_obter_zsql(cod_materia = codigo, ind_primeiro_autor=1):
                   nom_autor = autor.nom_autor_join
               descricao = str(metodo.des_tipo_materia) + ' nº ' + str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica) + ' - ' + str(nom_autor) +  ' - ' + str(metodo.txt_ementa)
               url = context.portal_url() + '/cadastros/materia/materia_mostrar_proc?cod_materia=' + str(codigo)
               url_pasta = context.portal_url() + '/consultas/materia/pasta_digital/?cod_materia=' + str(codigo) + '&action=pasta'
        elif tipo_doc == 'doc_acessorio':
           for metodo in context.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
               tipo_documento = 'Matéria Legislativa - Documento Acessório'
               for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) + ' - ' + str(materia.txt_ementa)
               descricao = str(metodo.des_tipo_documento) + ' - ' + str(metodo.nom_documento) + ' - ' + str(materia)
               url = context.portal_url() + '/cadastros/materia/materia_mostrar_proc?cod_materia=' + str(metodo.cod_materia) + '#acessorio'
               url_pasta = context.portal_url() + '/consultas/materia/pasta_digital/?cod_materia=' + str(metodo.cod_materia) + '&action=pasta'
        elif tipo_doc == 'emenda':
           for metodo in context.zsql.emenda_obter_zsql(cod_emenda=codigo):
               tipo_documento = 'Matéria Legislativa - Emenda'
               for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica) + ' - ' + str(materia.txt_ementa)
               for autor in context.zsql.autoria_emenda_obter_zsql(cod_emenda = codigo, ind_primeiro_autor=1):
                   nom_autor = autor.nom_autor_join
               descricao = 'Emenda ' + str(metodo.des_tipo_emenda) + ' nº ' + str(metodo.num_emenda) +  ' - ' + str(nom_autor) + ', ao ' + str(materia)
               url = context.portal_url() + '/cadastros/materia/materia_mostrar_proc?cod_materia=' + str(metodo.cod_materia) + '#emenda'
               url_pasta = context.portal_url() + '/consultas/materia/pasta_digital/?cod_materia=' + str(metodo.cod_materia) + '&action=pasta'
        elif tipo_doc == 'substitutivo':
           for metodo in context.zsql.substitutivo_obter_zsql(cod_substitutivo=codigo):
               tipo_documento = 'Matéria Legislativa - Substitutivo'
               for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.sgl_tipo_materia) + ' nº ' + str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica) + ' - ' + str(materia.txt_ementa)
               for autor in context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo = codigo, ind_primeiro_autor=1):
                   nom_autor = autor.nom_autor_join
               descricao = 'Substitutivo nº ' + str(metodo.num_substitutivo) +  ' - ' + str(nom_autor) + ', ao ' + str(materia)
               url = context.portal_url() + '/cadastros/materia/materia_mostrar_proc?cod_materia=' + str(metodo.cod_materia) + '#substitutivo'
               url_pasta = context.portal_url() + '/consultas/materia/pasta_digital/?cod_materia=' + str(metodo.cod_materia) + '&action=pasta'
        elif tipo_doc == 'tramitacao':
           for metodo in context.zsql.tramitacao_obter_zsql(cod_tramitacao=codigo):
               tipo_documento = 'Matéria Legislativa - Tramitação'
               for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.des_tipo_materia)+ ' nº ' + str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica) + ' - ' + str(materia.txt_ementa)
               nom_usuario = ''
               for usuario in context.zsql.usuario_obter_zsql(cod_usuario = metodo.cod_usuario_local):
                  nom_usuario = usuario.nom_completo
               descricao = 'Despacho de ' + str(nom_usuario) + ' - ' + str(metodo.des_status) +  ' - '  + str(materia)
               url = context.portal_url() + '/cadastros/materia/materia_mostrar_proc?cod_materia=' + str(metodo.cod_materia) + '#tramitacao'
               url_pasta = context.portal_url() + '/consultas/materia/pasta_digital/?cod_materia=' + str(metodo.cod_materia) + '&action=pasta'
        elif tipo_doc == 'parecer_comissao':
           for metodo in context.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
               tipo_documento = 'Matéria Legislativa - Parecer de Comissão'
               for comissao in context.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   sgl_comissao = str(comissao.sgl_comissao)
               parecer = str(metodo.num_parecer)+'/'+str(metodo.ano_parecer)
               for materia in context.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.des_tipo_materia)+ ' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica) + ' - ' + str(materia.txt_ementa)
               descricao = 'Parecer ' + str(sgl_comissao) + ' nº ' + str(parecer) + ' ao ' + str(materia)
               url = context.portal_url() + '/cadastros/materia/materia_mostrar_proc?cod_materia=' + str(metodo.cod_materia) + '#parecer'
               url_pasta = context.portal_url() + '/consultas/materia/pasta_digital/?cod_materia=' + str(metodo.cod_materia) + '&action=pasta'
        elif tipo_doc == 'pauta':
           for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               tipo_documento = str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' Plenária - Pauta'
               for tipo in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ' de ' + str(metodo.dat_inicio_sessao)
               descricao = 'Pauta da ' + str(sessao)
               url = context.portal_url() + '/cadastros/sessao_plenaria/sessao_plenaria_mostrar_proc?cod_sessao_plen=' + str(metodo.cod_sessao_plen)
           for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia=1):
               tipo_documento = 'Audiência Pública - Pauta'
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
               descricao = 'Pauta da ' + str(sessao)
               url = context.portal_url() + '/cadastros/sessao_plenaria/audiencia_publica_mostrar_proc?cod_sessao_plen=' + str(metodo.cod_sessao_plen) + '&ind_audiencia=1'
        elif tipo_doc == 'resumo_sessao':
           for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               tipo_documento = str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' Plenária - Roteiro / Resenha'
               for tipo in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ' de ' + str(metodo.dat_inicio_sessao)
               descricao = 'Roteiro / Resenha da ' + str(sessao)
               url = context.portal_url() + '/cadastros/sessao_plenaria/sessao_plenaria_mostrar_proc?cod_sessao_plen=' + str(metodo.cod_sessao_plen)
           for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia=1):
               tipo_documento = 'Audiência Pública -  Roteiro / Resenha'
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
               descricao = 'Roteiro / Resenha da ' + str(sessao)
               url = context.portal_url() + '/cadastros/sessao_plenaria/audiencia_publica_mostrar_proc?cod_sessao_plen=' + str(metodo.cod_sessao_plen) + '&ind_audiencia=1'
        elif tipo_doc == 'ata':
           for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               tipo_documento = str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' Plenária - Ata'
               for tipo in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ' de ' + str(metodo.dat_inicio_sessao)
               descricao = 'Ata da ' + str(sessao)
               url = context.portal_url() + '/cadastros/sessao_plenaria/sessao_plenaria_mostrar_proc?cod_sessao_plen=' + str(metodo.cod_sessao_plen)
           for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia=1):
               tipo_documento = 'Audiência Pública - Ata'
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
               descricao = 'Ata da ' + str(sessao)
               url = context.portal_url() + '/cadastros/sessao_plenaria/audiencia_publica_mostrar_proc?cod_sessao_plen=' + str(metodo.cod_sessao_plen) + '&ind_audiencia=1'
        elif tipo_doc == 'norma':
           for metodo in context.zsql.norma_juridica_obter_zsql(cod_norma=codigo):
               tipo_documento = 'Norma Jurídica - Texto Integral'
               descricao = str(metodo.des_tipo_norma) + ' nº ' + str(metodo.num_norma) + '/' + str(metodo.ano_norma) + ' - ' + str(metodo.txt_ementa)
               url = context.portal_url() + '/cadastros/norma_juridica/norma_juridica_mostrar_proc?cod_norma=' + str(metodo.cod_norma)
               url_pasta = context.portal_url() + '/consultas/norma_juridica/pasta_digital/?cod_norma=' + str(metodo.cod_norma) + '&action=pasta'
        elif tipo_doc == 'documento':
           for metodo in context.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
               tipo_documento = 'Processo Administrativo - Texto Integral'
               descricao = str(metodo.des_tipo_documento) + ' nº ' + str(metodo.num_documento) + '/' +str(metodo.ano_documento) + ' - ' + str(metodo.txt_interessado) + ' - ' + str(metodo.txt_assunto)
               url = context.portal_url() + '/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento=' + str(metodo.cod_documento)
               url_pasta = context.portal_url() + '/consultas/documento_administrativo/pasta_digital/?cod_documento=' + str(metodo.cod_documento) + '&action=pasta'
        elif tipo_doc == 'doc_acessorio_adm':
           for metodo in context.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
               tipo_documento = 'Processo Administrativo - Documento Acessório'
               for documento in context.zsql.documento_administrativo_obter_zsql(cod_documento=metodo.cod_documento):
                   documento = str(documento.sgl_tipo_documento) +' '+ str(documento.num_documento)+'/'+str(documento.ano_documento) + ' - ' + str(documento.txt_interessado) + ' - ' + str(documento.txt_assunto)
               descricao = str(metodo.des_tipo_documento) + ' ' + str(metodo.nom_documento) + ' - ' + str(metodo.nom_autor_documento) + ', juntado ao ' + str(documento)
               url = context.portal_url() + '/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento=' + str(metodo.cod_documento) + '#acessorios'
               url_pasta = context.portal_url() + '/consultas/documento_administrativo/pasta_digital/?cod_documento=' + str(metodo.cod_documento) + '&action=pasta'
        elif tipo_doc == 'tramitacao_adm':
           for metodo in context.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=codigo):
               tipo_documento = 'Processo Administrativo - Tramitação'
               for documento in context.zsql.documento_administrativo_obter_zsql(cod_documento=metodo.cod_documento):
                   documento = str(documento.sgl_tipo_documento) +' '+ str(documento.num_documento)+'/'+str(documento.ano_documento) + ' - ' + str(documento.txt_interessado) + ' - ' + str(documento.txt_assunto)
               nom_usuario = ''
               for usuario in context.zsql.usuario_obter_zsql(cod_usuario = metodo.cod_usuario_local):
                   nom_usuario = usuario.nom_completo
               descricao = 'Despacho de ' + str(nom_usuario) + ' - ' + str(metodo.des_status) +  ' - '  + str(documento)
               url = context.portal_url() + '/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento=' + str(metodo.cod_documento) + '#tramitacao'
               url_pasta = context.portal_url() + '/consultas/documento_administrativo/pasta_digital/?cod_documento=' + str(metodo.cod_documento) + '&action=pasta'
        elif tipo_doc == 'protocolo':
           for metodo in context.zsql.protocolo_obter_zsql(cod_protocolo=codigo):
               tipo_documento = 'Protocolo - Documento'
               autor = metodo.txt_interessado
               if metodo.cod_autor != None:
                  for autor in context.zsql.autor_obter_zsql(cod_autor=metodo.cod_autor):
                      autor = autor.nom_autor_join
               descricao = 'Protocolo nº '+ str(metodo.num_protocolo) +'/' + str(metodo.ano_protocolo) + ' - ' + str(autor) + ' - ' + str(metodo.txt_assunto_ementa)
               url = context.portal_url() + '/consultas/protocolo/protocolo_mostrar_proc?cod_protocolo=' + str(metodo.cod_protocolo)
        elif tipo_doc == 'peticao':
           for metodo in context.zsql.peticao_obter_zsql(cod_peticao=codigo):
               tipo_documento = 'Petição Digital - Texto Integral'
               for tipo in context.zsql.tipo_peticionamento_obter_zsql(tip_peticionamento=metodo.tip_peticionamento):
                   tipo = tipo.des_tipo_peticionamento
               for usuario in context.zsql.usuario_obter_zsql(cod_usuario=metodo.cod_usuario):
                   usuario = usuario.nom_completo
               descricao = str(tipo) + ' - ' + str(usuario) + ' - ' + str(metodo.txt_descricao)
               url = context.portal_url() + '/cadastros/peticionamento_eletronico/peticao_mostrar_proc?cod_peticao=' + str(metodo.cod_peticao)
        elif tipo_doc == 'anexo_peticao':
           for metodo in context.zsql.peticao_obter_zsql(cod_peticao=codigo):
               tipo_documento = 'Petição Digital - Documento Acessório'
               for tipo in context.zsql.tipo_peticionamento_obter_zsql(tip_peticionamento=metodo.tip_peticionamento):
                   tipo = tipo.des_tipo_peticionamento
               for usuario in context.zsql.usuario_obter_zsql(cod_usuario=metodo.cod_usuario):
                   usuario = usuario.nom_completo
               arquivo = str(metodo.cod_peticao) + '_anexo_' + str(anexo) + '.pdf'
               titulo = getattr(context.sapl_documentos.peticao,arquivo).title_or_id()
               descricao = str(titulo) + ', anexo do ' + str(tipo) + ' - ' + str(usuario) + ' - ' + str(metodo.txt_descricao)
               url = context.portal_url() + '/cadastros/peticionamento_eletronico/peticao_mostrar_proc?cod_peticao=' + str(metodo.cod_peticao)
        elif tipo_doc == 'pauta_comissao':
           for metodo in context.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
               tipo_documento = 'Comissão - Pauta de Reunião'
               for comissao in context.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   comissao = comissao.nom_comissao
               descricao = 'Pauta da ' + str(metodo.num_reuniao) + 'ª Reunião ' + str(metodo.des_tipo_reuniao) + ' da ' + comissao + ' de ' + str(metodo.dat_inicio_reuniao)
               url = context.portal_url() + '/cadastros/comissao/comissao_mostrar_proc?cod_comissao=' + str(metodo.cod_comissao) + '#reuniao'
        elif tipo_doc == 'ata_comissao':
           for metodo in context.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
               tipo_documento = 'Comissão - Ata de Reunião'
               for comissao in context.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   comissao = comissao.nom_comissao
               descricao = 'Ata da ' + str(metodo.num_reuniao) + 'ª Reunião ' + str(metodo.des_tipo_reuniao) + ' da ' + comissao + ' de ' + str(metodo.dat_inicio_reuniao)
               url = context.portal_url() + '/cadastros/comissao/comissao_mostrar_proc?cod_comissao=' + str(metodo.cod_comissao) + '#reuniao'
        elif tipo_doc == 'documento_comissao':
           for metodo in context.zsql.documento_comissao_obter_zsql(cod_documento=codigo):
               tipo_documento = 'Comissão - Documento'
               for comissao in context.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   comissao = comissao.nom_comissao
               descricao = str(metodo.txt_descricao) + ' da ' + comissao
               url = context.portal_url() + '/cadastros/comissao/comissao_mostrar_proc?cod_comissao=' + str(metodo.cod_comissao) + '#documento'
        elif tipo_doc == 'anexo_sessao':
           for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               tipo_documento = str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' Plenária - Anexo'
               for tipo in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ' de ' + str(metodo.dat_inicio_sessao)
               arquivo = str(metodo.cod_sessao_plen) + '_anexo_' + str(anexo) + '.pdf'
               titulo = getattr(context.sapl_documentos.anexo_sessao,arquivo).title_or_id()
               descricao = str(titulo) + ' da ' + str(sessao)
               url = context.portal_url() + '/cadastros/sessao_plenaria/sessao_plenaria_mostrar_proc?cod_sessao_plen=' + str(metodo.cod_sessao_plen)
           for metodo in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia=1):
               tipo_documento = 'Audiência Pública - Documento'
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
               arquivo = str(metodo.cod_sessao_plen) + '_anexo_' + str(anexo) + '.pdf'
               titulo = getattr(context.sapl_documentos.anexo_sessao,arquivo).title_or_id()
               descricao =  str(titulo) + ' da ' + str(sessao)
               url = context.portal_url() + '/cadastros/sessao_plenaria/audiencia_publica_mostrar_proc?cod_sessao_plen=' + str(metodo.cod_sessao_plen) + '&ind_audiencia=1'

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

    return descricao, url, tipo_documento, url_pasta



# Gerar itens pendentes de assinatura
lista = []
for item in context.zsql.assinatura_documento_pendente_obter_zsql(codigo=codigo, tipo_doc=tipo_doc, cod_solicitante=cod_solicitante, cod_usuario=cod_usuario, ind_assinado=ind_assinado, ind_separado=ind_separado):
    dic_documento = {}
    dic_documento['cod_assinatura_doc'] = item['cod_assinatura_doc']
    dic_documento['codigo'] = item['codigo']
    dic_documento['tipo_doc'] = item['tipo_doc']
    dic_documento['cod_solicitante_documento'] = None
    dic_documento['nome_solicitante_documento'] = None
    if item.cod_solicitante != None:
       dic_documento['cod_solicitante_documento'] = item.cod_solicitante
       for usuario in context.zsql.usuario_obter_zsql(cod_usuario=item.cod_solicitante):
           dic_documento['nome_solicitante_documento'] = usuario.nom_completo
    dic_documento['anexo'] = item['anexo']
    dic_documento['visual_page_option'] = item.visual_page_option
    dados = get_info(codigo=item['codigo'], tipo_doc=item['tipo_doc'], anexo=item['anexo'])
    dic_documento['id_documento'] = dados[0]
    dic_documento['link_registro'] = dados[1]
    dic_documento['tipo_documento'] = dados[2]
    dic_documento['url_pasta'] = dados[3]

    pdf_tosign, storage_path, crc_arquivo = st.get_file_tosign(item['codigo'], item['anexo'], item['tipo_doc'])
    dic_documento['link_pdf'] = None
    dic_documento['pdf_to_sign'] = None
    dic_documento['crc_arquivo'] = None
    if hasattr(storage_path, pdf_tosign):
       arq = getattr(storage_path, pdf_tosign)
       dic_documento['link_pdf'] = arq.absolute_url()
       dic_documento['pdf_to_sign'] = arq.absolute_url()
       dic_documento['crc_arquivo'] = crc_arquivo
    dic_documento['assinados'] = []
    dic_documento['pendentes'] = []
    dic_documento['recusados'] = []

    for assinatura in context.zsql.assinatura_documento_obter_zsql(cod_assinatura_doc=item['cod_assinatura_doc']):
        dic = {}
        dic['cod_solicitante'] = assinatura.cod_solicitante
        dic['nom_solicitante'] = None
        if assinatura.cod_solicitante != None:
           for usuario in context.zsql.usuario_obter_zsql(cod_usuario=assinatura.cod_solicitante):
               dic['nom_solicitante'] = usuario.col_username
        dic['cod_usuario'] = assinatura.cod_usuario
        dic['nome_usuario'] = assinatura.nom_completo
        dic['primeiro_signatario'] = assinatura.ind_prim_assinatura
        dic['dat_solicitacao'] = assinatura.dat_solicitacao
        dic['dat_assinatura'] = assinatura.dat_assinatura
        dic['dat_recusa'] = assinatura.dat_recusa
        dic['txt_motivo_recusa'] = assinatura.txt_motivo_recusa
        if assinatura.dat_assinatura != None:
           dic_documento['assinados'].append(dic)
        if assinatura.dat_assinatura == None and assinatura.dat_recusa == None:
           dic_documento['pendentes'].append(dic)
        if assinatura.dat_assinatura == None and assinatura.dat_recusa != None:
           dic_documento['recusados'].append(dic)
        dic_documento['assinados'].sort(key=lambda dic: dic['nome_usuario'])
        dic_documento['pendentes'].sort(key=lambda dic: dic['nome_usuario'])
        dic_documento['recusados'].sort(key=lambda dic: dic['nome_usuario'])
        #dic_documento['assinaturas'].sort(key=lambda dic: dic['nome_usuario'])
        #dic_documento['assinaturas'].append(dic)
    lista.append(dic_documento)

return lista
