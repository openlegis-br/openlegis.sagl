## Script (Python) "cientificacao_salvar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=hdn_cod_documento, lst_cod_usuario_dest, txt_dat_expiracao
##title=
##

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

for usuario in context.zsql.usuario_obter_zsql(col_username=REQUEST.AUTHENTICATED_USER.getUserName()):
    cod_cientificador = usuario.cod_usuario

lst_usuarios = [
   e
   for i, e in enumerate(lst_cod_usuario_dest)
   if lst_cod_usuario_dest.index(e) == i
]

existentes = []
for item in context.zsql.cientificacao_documento_obter_zsql(cod_documento=hdn_cod_documento):
    if (item.dat_leitura != None):
       existentes.append(item.cod_cientificado)
    else:
       existentes.append(item.cod_cientificado)

for item in lst_usuarios:
    if item not in existentes:
       context.zsql.cientificacao_documento_incluir_zsql(cod_documento=hdn_cod_documento, cod_cientificador=cod_cientificador,dat_envio=DateTime(datefmt='international').strftime('%Y/%m/%d %H:%M:%S'), dat_expiracao=DateTime(txt_dat_expiracao, datefmt='international').strftime('%Y/%m/%d 23:59:59'), cod_cientificado=item)

redirect_url=context.portal_url()+'/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento='+hdn_cod_documento+'#cientificacoes'
RESPONSE.redirect(redirect_url)


