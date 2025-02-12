## Script (Python) "margem_inferior"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename
##title=
##
from Products.CMFCore.utils import getToolByName

st = getToolByName(context, 'portal_sagl')

return st.margem_inferior(codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename)
