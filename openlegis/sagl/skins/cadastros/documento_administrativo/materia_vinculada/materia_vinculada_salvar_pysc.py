## Script (Python) "materia_vinculada_salvar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_documento, cod_materia
##title=
##
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

v=str(cod_materia)
if v.isdigit():
   cod_materia = [cod_materia]
else:
   cod_materia = cod_materia

cod_materia = [
   e
   for i, e in enumerate(cod_materia)
   if cod_materia.index(e) == i
]

for item in cod_materia:
    if not context.zsql.documento_administrativo_materia_obter_zsql(cod_documento=cod_documento,cod_materia=item):
       context.zsql.documento_administrativo_materia_incluir_zsql(cod_documento=cod_documento,cod_materia=item)

mensagem = 'Vínculos salvos com sucesso!'
mensagem_obs = ''
url = context.portal_url() + '/cadastros/documento_administrativo/documento_administrativo_mostrar_proc?modal=1&cod_documento=' + str(cod_documento)
redirect_url=context.portal_url()+'/mensagem_emitir?tipo_mensagem=success&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs + '&modal=1'
REQUEST.RESPONSE.redirect(redirect_url)
