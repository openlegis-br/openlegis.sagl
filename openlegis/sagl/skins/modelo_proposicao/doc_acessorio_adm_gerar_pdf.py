## Script (Python) "doc_acessorio_adm_gerar_pdf"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_documento_acessorio
##title=
##
from Products.CMFCore.utils import getToolByName

st = getToolByName(context, 'portal_sagl')

return st.doc_acessorio_adm_gerar_pdf(cod_documento_acessorio)
