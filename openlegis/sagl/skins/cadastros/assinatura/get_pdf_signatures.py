## Script (Python) "get_pdf_signatures"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=tipo_doc, codigo, anexo=''
##title=
##
request = container.REQUEST
from Products.CMFCore.utils import getToolByName
utool = getToolByName(context, 'portal_url')
portal = utool.getPortalObject()

request.set('tipo_doc', tipo_doc)
request.set('codigo', codigo)
request.set('anexo', anexo)
path = '@@obter_assinaturas'
view = portal.restrictedTraverse('@@obter_assinaturas')
results = view()
return results

