## Script (Python) "email_enviar_lote"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_documento, hdn_url
##title=
##

from Products.CMFCore.utils import getToolByName

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

utool = getToolByName(context, 'portal_url')
portal = utool.getPortalObject()

view = portal.restrictedTraverse('@@email_doc')
view()

mensagem = 'E-mail enviado aos destinatários através da fila do servidor SMTP.'
mensagem_obs = '' 
redirect_url=context.portal_url()+'/mensagem_emitir?tipo_mensagem=success&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs + '&url=' + hdn_url

RESPONSE.redirect(redirect_url)
