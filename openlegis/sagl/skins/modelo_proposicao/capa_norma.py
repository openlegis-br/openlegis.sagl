## Script (Python) "capa_norma"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_norma, action
##title=
##
from DateTime import DateTime
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE

capa_dic = {}
casa={}
aux=context.sapl_documentos.props_sagl.propertyItems()
for item in aux:
    casa[item[0]]=item[1]
localidade=context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])
estado = context.zsql.localidade_obter_zsql(tip_localidade="U")
for uf in estado:
    if localidade[0].sgl_uf == uf.sgl_uf:
        nom_estado = uf.nom_localidade
        break
capa_dic['nom_camara'] = casa['nom_casa']
capa_dic["nom_estado"] = nom_estado
for local in context.zsql.localidade_obter_zsql(cod_localidade = casa['cod_localidade']):
    capa_dic['nom_localidade']= local.nom_localidade
    capa_dic['sgl_uf']= local.sgl_uf

for norma in context.zsql.norma_juridica_obter_zsql(cod_norma=cod_norma):
    capa_dic['id_norma'] = str(norma.des_tipo_norma.upper()) + ' Nº ' + str(norma.num_norma) + '/' + str(norma.ano_norma)
    capa_dic['num_norma'] = norma.num_norma
    capa_dic['ano_norma'] = norma.ano_norma
    capa_dic['txt_ementa'] = norma.txt_ementa
    capa_dic['dat_norma'] = norma.dat_norma
    capa_dic['data_norma2'] = context.pysc.data_converter_por_extenso_pysc(data=norma.dat_norma)
    capa_dic['dat_publicacao'] = norma.dat_publicacao
    capa_dic['des_veiculo_publicacao'] = norma.des_veiculo_publicacao
    capa_dic['num_pag_inicio_publ'] = norma.num_pag_inicio_publ
    capa_dic['num_pag_fim_publ'] = norma.num_pag_fim_publ
    capa_dic['txt_observacao'] = norma.txt_observacao
    capa_dic['txt_situacao'] = ''
    if norma.cod_situacao != None:
       for situacao in context.zsql.tipo_situacao_norma_obter_zsql(tip_situacao_norma=norma.cod_situacao):
           capa_dic['txt_situacao'] = situacao.des_tipo_situacao

    # materia
    capa_dic['link_materia'] = ''
    if norma.cod_materia != None and norma.cod_materia != '':
       for materia in context.zsql.materia_obter_zsql(cod_materia=norma.cod_materia,ind_excluido=0):
           autores = context.zsql.autoria_obter_zsql(cod_materia=norma.cod_materia)
           fields = autores.data_dictionary().keys()
           lista_autor = []
           for autor in autores:
               for field in fields:
                   nome_autor = str(autor['nom_autor_join'])
               lista_autor.append(nome_autor)
           autoria = ', '.join(['%s' % (value) for (value) in lista_autor])  
           capa_dic["link_materia"] = '<a href="' + context.consultas.absolute_url() + '/materia/materia_mostrar_proc?cod_materia=' + str(materia.cod_materia) + '"><b>'+materia.des_tipo_materia +' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</b></a>' + ' - <b>Autoria: ' + str(autoria) + '</b>'

    # anexos
    anexos = []
    for anexo in context.zsql.anexo_norma_obter_zsql(cod_norma=norma.cod_norma, ind_excluido=0):
        nom_anexo = str(cod_norma) + '_anexo_' + anexo.cod_anexo
        dic_anexo = {}
        dic_anexo['link_anexo'] = anexo.txt_descricao
        if hasattr(context.sapl_documentos.norma_juridica, nom_anexo):
           dic_anexo['link_anexo'] = '<a href="' + context.sapl_documentos.absolute_url() + '/norma_juridica/' + str(nom_anexo) + '">' + anexo.txt_descricao + '</a>'
        anexos.append(dic_anexo)
    capa_dic['anexos'] = anexos
    
    # remissoes
    referentes = []
    for item in context.zsql.vinculo_norma_juridica_referentes_obter_zsql(cod_norma=norma.cod_norma):
        nom_arquivo = str(item.cod_norma_referente) + '_texto_integral.pdf'
        nom_arquivo2 = str(item.cod_norma_referente) + '_texto_consolidado.pdf'
        dic_referente = {}
        dic_referente["link_norma"] = '<a href="' + context.consultas.absolute_url() + '/norma_juridica/norma_juridica_mostrar_proc?cod_norma=' + str(item.cod_norma_referente) + '">' + str(item.des_tipo_norma) +' nº '+ str(item.num_norma) + '/' + str(item.ano_norma) + '</a>'
        dic_referente['dat_norma'] = item.dat_norma
        dic_referente['tipo_acao'] = item.des_vinculo_passivo
        referentes.append(dic_referente)
    capa_dic['referentes'] = referentes
    
    id_capa = 'capa_' + str(norma.sgl_tipo_norma) + '-' + str(norma.num_norma) + '-' + str(norma.ano_norma)
    capa_dic['nom_arquivo_odt'] = "%s.odt" % id_capa
    capa_dic['nom_arquivo_pdf'] = "%s.pdf" % id_capa

    return st.capa_norma_gerar_odt(capa_dic, action)
