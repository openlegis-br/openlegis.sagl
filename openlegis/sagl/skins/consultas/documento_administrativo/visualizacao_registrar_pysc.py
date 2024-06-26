## Script (Python) "visualizacao_registrar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=hdn_id, hdn_cod_documento, hdn_lido
##title=
##

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

if str(hdn_lido) == '0':
   context.zsql.cientificacao_documento_registrar_leitura_zsql(id=hdn_id, dat_leitura=DateTime(datefmt='international').strftime('%Y/%m/%d %H:%M:%S'))

redirect_url=context.portal_url()+'/consultas/documento_administrativo/pasta_digital/?cod_documento='+hdn_cod_documento+'&action=pasta'
RESPONSE.redirect(redirect_url)
