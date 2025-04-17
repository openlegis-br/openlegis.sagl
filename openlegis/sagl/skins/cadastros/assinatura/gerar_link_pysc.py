## Script (Python) "gerar_link_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=tip_documento, codigo, anexo
##title=
##
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

pdf_tosign, storage_path, crc_arquivo_atualizado = st.get_file_tosign(codigo, anexo, tip_documento)

arq = getattr(storage_path, pdf_tosign)

link = arq.absolute_url()

return link
