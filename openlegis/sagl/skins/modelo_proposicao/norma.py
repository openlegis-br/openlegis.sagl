## Script (Python) "norma"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_norma, modelo_norma
##title=
##

from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE
session = REQUEST.SESSION

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

inf_basicas_dic['nom_prefeito'] = 'Não Cadastrado'
inf_basicas_dic['par_prefeito'] = 'Não Cadastrado'

for norma in context.zsql.norma_juridica_obter_zsql(cod_norma=cod_norma):
 nom_arquivo = str(norma.cod_norma)+'_texto_integral.odt'
 des_tipo_norma = norma.des_tipo_norma.upper()
 num_norma = norma.num_norma
 ano_norma = norma.ano_norma
 dat_norma = norma.dat_norma
 data_norma = context.pysc.data_converter_por_extenso_pysc(data=norma.dat_norma)
 data_norma2 = context.pysc.data_converter_por_extenso_pysc(data=norma.dat_norma).upper()
 txt_ementa = norma.txt_ementa
 inf_basicas_dic['materia'] = ''
 inf_basicas_dic['autoria_materia'] = ''
 if norma.cod_materia != None and norma.cod_materia != '':
    for materia in context.zsql.materia_obter_zsql(cod_materia=norma.cod_materia,ind_excluido=0):
        inf_basicas_dic['materia'] = str(materia.sgl_tipo_materia) + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
        autores = context.zsql.autoria_obter_zsql(cod_materia=norma.cod_materia)
        fields = autores.data_dictionary().keys()
        lista_autor = []
        for autor in autores:
            for field in fields:
                nome_autor = 'Vereador ' + str(autor['nom_autor_join'])
            lista_autor.append(nome_autor)
        inf_basicas_dic['autoria_materia'] = str('Autoria: ') + ', '.join(['%s' % (value) for (value) in lista_autor])  
 for prefeito in context.zsql.prefeito_atual_obter_zsql(data_composicao = norma.dat_norma):
     inf_basicas_dic['nom_prefeito'] = prefeito.nom_completo
     inf_basicas_dic['par_prefeito'] = prefeito.sgl_partido   

return st.norma_gerar_odt(inf_basicas_dic, nom_arquivo, des_tipo_norma, num_norma, ano_norma, dat_norma, data_norma, txt_ementa, modelo_norma)
