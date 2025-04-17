## Script (Python) "mail_password"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=userid
##title=
##
REQUEST = context.REQUEST
try:
    return context.portal_sagl.mailPassword(userid, REQUEST)
except ValueError as e:
    REQUEST.set('error_message', str(e))
    return context.REQUEST.RESPONSE.redirect(context.portal_url() + '/mail_password_form?error_message=' + str(e))
except Exception as e:
    REQUEST.set('error_message', 'Ocorreu um erro inesperado.')
    return context.REQUEST.RESPONSE.redirect(context.portal_url() + '/mail_password_form?error_message=Ocorreu%20um%20erro%20inesperado.')
