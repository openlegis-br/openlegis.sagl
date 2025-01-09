## Script (Python) "destinatario_incluir"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_proposicao, txt_nom_destinatario, txt_end_email
##title=
##
REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

if isinstance(txt_end_email, str):
   txt_nom_destinatario = [txt_nom_destinatario]
   txt_end_email = [txt_end_email]

dic = dict(list(zip(txt_nom_destinatario, txt_end_email)))

existentes = []

for cadastrados in context.zsql.destinatario_oficio_obter_zsql(cod_proposicao=cod_proposicao):
    existentes.append(cadastrados.end_email)

for item in dic:
    if dic.get(item) not in existentes:
       context.zsql.destinatario_oficio_incluir_zsql(cod_proposicao=cod_proposicao, nom_destinatario=item, end_email=dic.get(item))
       tipo_mensagem = 'success'
       mensagem = 'Destinatários incluídos com sucesso!'
       mensagem_obs = ''
    else:
       tipo_mensagem = 'danger'
       mensagem = 'Houve um erro ao incluir o destinatário!'
       mensagem_obs = 'O endereço de email ' + dic.get(item) + ' já se encontra cadastrado.'

url = context.portal_url() + '/cadastros/proposicao/proposicao_mostrar_proc?cod_proposicao=' + str(cod_proposicao)
redirect_url=context.portal_url()+'/mensagem_emitir?mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs + '&tipo_mensagem=' + tipo_mensagem + '&url=' + url
REQUEST.RESPONSE.redirect(redirect_url)
