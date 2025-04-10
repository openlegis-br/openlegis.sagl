## Script (Python) "peticao"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_peticao, modelo_path
##title=
##
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE

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

for peticao in context.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
    nom_arquivo = str(peticao.cod_peticao)+'.odt'
    inf_basicas_dic['txt_descricao'] = peticao.txt_descricao
    inf_basicas_dic['data'] = context.pysc.data_converter_por_extenso_pysc(data=DateTime(datefmt='international').strftime("%d/%m/%Y"))
    for usuario in context.zsql.usuario_obter_zsql(cod_usuario=peticao.cod_usuario):
        inf_basicas_dic['nom_completo'] = usuario.nom_completo
        inf_basicas_dic['num_matricula'] = usuario.num_matricula
        inf_basicas_dic['nom_cargo'] = usuario.nom_cargo
        inf_basicas_dic['lotacao'] = usuario.des_lotacao
        inf_basicas_dic['vinculo'] = usuario.des_vinculo
        inf_basicas_dic['dat_nascimento'] = usuario.dat_nascimento
        inf_basicas_dic['estado_civil'] = usuario.des_estado_civil
        if usuario.sex_usuario == 'M':
           inf_basicas_dic['sexo'] = 'Masculino'
           inf_basicas_dic['sexo_servidor'] = 'servidor'
        elif usuario.sex_usuario == 'F':
           inf_basicas_dic['sexo'] = 'Feminino'
           inf_basicas_dic['sexo_servidor'] = 'servidora'
        else:
           inf_basicas_dic['sexo'] = ''
           inf_basicas_dic['sexo_servidor'] = 'servidor(a)'
        inf_basicas_dic['num_cpf'] = usuario.num_cpf
        inf_basicas_dic['num_rg'] = usuario.num_rg
        inf_basicas_dic['num_ctps'] = usuario.num_ctps
        inf_basicas_dic['num_serie_ctps'] = usuario.num_serie_ctps
        inf_basicas_dic['num_pis_pasep'] = usuario.num_pis_pasep
        inf_basicas_dic['end_residencial'] = usuario.end_residencial
        inf_basicas_dic['num_cep_resid'] = usuario.num_cep_resid
        inf_basicas_dic['num_tel_resid'] = usuario.num_tel_resid
        inf_basicas_dic['num_tel_celular'] = usuario.num_tel_celular
        inf_basicas_dic['num_tel_comercial'] = usuario.num_tel_comercial

    materia_vinculada = {}
    if peticao.cod_materia == '' and peticao.cod_materia != None:
       for materia in context.zsql.materia_obter_zsql(cod_materia = peticao.cod_materia):
           materia_vinculada['id_materia'] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
           materia_vinculada['txt_ementa'] = materia.txt_ementa
           materia_vinculada['autoria'] = ''
           autores = context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia,)
           fields = list(autores.data_dictionary().keys())
           lista_autor = []
           for autor in autores:
               for field in fields:
                   nome_autor = autor['nom_autor_join']
                   inf_basicas_dic['nome_autor'] = autor['nom_autor_join']
               lista_autor.append(nome_autor)
           materia_vinculada['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor])

    inf_basicas_dic['materia_vinculada'] = materia_vinculada

# Presidente e Secretário
inf_basicas_dic["lst_presidente"] = ''
inf_basicas_dic["lst_psecretario"] = ''
data = DateTime(datefmt='international').strftime("%Y/%m/%d")
for legislatura in context.zsql.legislatura_obter_zsql(data=data):
    for periodo in context.zsql.periodo_comp_mesa_obter_zsql(num_legislatura=legislatura.num_legislatura,data=data):
        for membro in context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=periodo.cod_periodo_comp):
            for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=membro.cod_parlamentar):
                if membro.des_cargo == 'Presidente':
                   inf_basicas_dic["lst_presidente"] = parlamentar.nom_completo
                elif membro.des_cargo == '1º Secretário':
                   inf_basicas_dic["lst_psecretario"] = parlamentar.nom_completo

return st.peticao_gerar_odt(inf_basicas_dic, nom_arquivo, modelo_path)
