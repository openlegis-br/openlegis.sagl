## Script (Python) "processo_adm_eletronico"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##
from Products.CMFCore.utils import getToolByName
from AccessControl import getSecurityManager

st = getToolByName(context, 'portal_sagl')

anon = getSecurityManager().getUser()
if (str(anon) == 'Anonymous User'):
   for documento in context.zsql.protocolo_pesquisa_publica_zsql(chave_acesso=context.REQUEST['token']):
       cod_documento = documento.cod_documento
else:
   cod_documento = context.REQUEST['cod_documento']

return st.processo_adm_gerar_pdf(cod_documento)
