## Script (Python) "autoria_materia_salvar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters= autores, materia
##

cod_materia = str(materia)

lista = autores

for i, item in enumerate(lista):
    if i == 0:
       context.zsql.autoria_incluir_zsql(cod_autor=item, cod_materia=cod_materia, ind_primeiro_autor=1)
    else:
       context.zsql.autoria_incluir_zsql(cod_autor=item, cod_materia=cod_materia, ind_primeiro_autor=0)

return 1

