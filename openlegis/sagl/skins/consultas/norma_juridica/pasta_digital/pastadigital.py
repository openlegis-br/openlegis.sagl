## Script (Python) "pastadigital"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_norma, action=''
##title=
##

from Products.CMFCore.utils import getToolByName

utool = getToolByName(context, 'portal_url')
portal = utool.getPortalObject()

view = portal.restrictedTraverse('@@norma_integral')

results = view()

return results
