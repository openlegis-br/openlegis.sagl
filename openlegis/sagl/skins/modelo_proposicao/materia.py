## Script (Python) "materia"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_materia, modelo_proposicao
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

inf_basicas_dic['url_validacao'] = "" + context.generico.absolute_url()+"/conferir_assinatura"

inf_basicas_dic['nom_prefeito'] = 'Não Cadastrado'
inf_basicas_dic['par_prefeito'] = 'Não Cadastrado'

inf_basicas_dic['des_assunto'] = ''
inf_basicas_dic['orgao_responsavel'] = ''

for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia):
    num_proposicao = " "
    nom_arquivo = str(materia.cod_materia)+'_texto_integral.odt'
    des_tipo_materia = materia.des_tipo_materia.upper()
    num_ident_basica = materia.num_ident_basica
    num_materia = materia.num_ident_basica
    ano_ident_basica = materia.ano_ident_basica
    ano_materia = materia.ano_ident_basica
    txt_ementa = materia.txt_ementa
    dat_apresentacao = context.pysc.data_converter_por_extenso_pysc(data=materia.dat_apresentacao)
    for prefeito in context.zsql.prefeito_atual_obter_zsql(data_composicao = materia.dat_apresentacao):
        inf_basicas_dic['nom_prefeito'] = prefeito.nom_completo
        inf_basicas_dic['par_prefeito'] = prefeito.sgl_partido        
    materia_vinculada = " "
    apelido_autor = ''
    nom_autor = []
    autorias = context.zsql.autoria_obter_zsql(cod_materia=cod_materia)
    fields = list(autorias.data_dictionary().keys())
    for autoria in autorias:
        autores = context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor)
        for autor in autores:
            autor_dic = {}
            for field in fields:
                nom_parlamentar = ''
                partido_autor = ''
                nom_cargo = ''
                if autor.cod_parlamentar != None:
                   parlamentares = context.zsql.parlamentar_obter_zsql(cod_parlamentar = autor.cod_parlamentar)
                   for parlamentar in parlamentares:
                       nom_parlamentar = " - " + parlamentar.nom_parlamentar
                       if parlamentar.sex_parlamentar == 'M':
                          nom_cargo = 'Vereador'
                       elif parlamentar.sex_parlamentar == 'F':
                          nom_cargo = 'Vereadora'
                       if parlamentar.sgl_partido !=None:
                          partido_autor = nom_cargo + ' - ' + parlamentar.sgl_partido
                       else:
                          partido_autor = nom_cargo
                   autor_dic['nome_autor'] = autor.nom_autor_join.upper() + '\n' + partido_autor
                   autor_dic['apelido_autor'] = partido_autor
                else:
                   autor_dic['nome_autor'] = autor.nom_autor_join.upper()
                   autor_dic['apelido_autor'] = ''
                autor_dic['cod_autor'] = autor['cod_autor']
        nom_autor.append(autor_dic)

    inf_basicas_dic['materia_anexada'] = ''
    inf_basicas_dic['autoria_materia_anexada'] = ''
    for anexada in context.zsql.anexada_obter_zsql(cod_materia_principal=cod_materia,ind_excluido=0):
        inf_basicas_dic['materia_anexada'] = str(anexada.tip_materia_anexada) + ' ' + str(anexada.num_materia_anexada) + '/' + str(anexada.ano_materia_anexada)
        for autoria in context.zsql.autoria_obter_zsql(cod_materia = anexada.cod_materia_anexada):
            for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor, ind_primeiro_autor=1):
                inf_basicas_dic['autoria_materia_anexada'] = 'Autoria do Projeto: ' + str(autor.nom_autor_join).upper()

return st.materia_gerar_odt(inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, num_materia, ano_ident_basica, ano_materia, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao)
