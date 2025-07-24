## Script (Python) "tipo_documento_consulta_permitir_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_usuario,tip_documento=""
##title=
##

lista_tipos=context.zsql.usuario_consulta_tipo_documento_obter_zsql(cod_usuario=cod_usuario)

tipos=[]

for tipo in lista_tipos:
  tipos.append(str(tipo.tip_documento))

if tip_documento == ['0']:
  context.zsql.usuario_consulta_tipo_documento_excluir_zsql(cod_usuario=cod_usuario)

elif tip_documento != ['0']:
  for i in tip_documento:
    if str(i) not in tipos:
      context.zsql.usuario_consulta_tipo_documento_incluir_zsql(cod_usuario=cod_usuario, tip_documento=i)
  for i in tipos:
    if str(i) not in tip_documento:
      context.zsql.usuario_consulta_tipo_documento_excluir_zsql(cod_usuario=cod_usuario,tip_documento=i)

return 1
