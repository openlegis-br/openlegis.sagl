## Script (Python) "doc_acessorio_adm"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_documento_acessorio, modelo_documento
##title=
##
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')
REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

inf_basicas_dic = {}
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
inf_basicas_dic['nom_camara']= casa['nom_casa']
inf_basicas_dic["nom_estado"] = nom_estado
for local in context.zsql.localidade_obter_zsql(cod_localidade = casa['cod_localidade']):
    inf_basicas_dic['nom_localidade']= local.nom_localidade
    inf_basicas_dic['sgl_uf']= local.sgl_uf

for doc_acessorio in context.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=cod_documento_acessorio, ind_excluido=0):
    documento_dic = {
        'nom_arquivo': str(doc_acessorio.cod_documento_acessorio)+ '.odt',
        'nom_documento': doc_acessorio.nom_documento,
        'des_tipo_documento': doc_acessorio.des_tipo_documento,
        'dat_documento': DateTime(doc_acessorio.dat_documento, datefmt='international').strftime('%d/%m/%Y'),
        'data_documento': context.pysc.data_converter_por_extenso_pysc(data=doc_acessorio.dat_documento),
        'nome_autor': doc_acessorio.nom_autor_documento
        }  
    documento = context.zsql.documento_administrativo_obter_zsql(cod_documento = doc_acessorio.cod_documento)[0]
    dic = {}
    dic['id_documento'] = documento.des_tipo_documento + ' nº ' + str(documento.num_documento) + '/' + str(documento.ano_documento)
    dic['txt_ementa'] = documento.txt_assunto
    dic['autoria'] = documento.txt_interessado
    documento_dic['documento_vinculado'] = dic

return st.doc_acessorio_adm_gerar_odt(inf_basicas_dic, documento_dic, modelo_documento)
