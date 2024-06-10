## Script (Python) "upload_index"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=file
##title=
##


from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

return st.upload_index_file(file)
