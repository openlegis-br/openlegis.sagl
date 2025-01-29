## Script (Python) "usuario_recriar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=username
##title=
##
REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE
passwd = context.sapl_documentos.props_sagl.txt_senha_inicial

if username in context.acl_users.getUserNames():
  mensagem = 'Não foi possível recriar o login do usuário!'
  mensagem_obs = 'Login "' + username + '" já existe'
  url = context.portal_url() + '/cadastros/usuario'
  redirect_url=context.portal_url()+'/mensagem_emitir?tipo_mensagem=danger&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs + '&url=' + url
else:
  context.acl_users.userFolderAddUser(username, passwd, ['Authenticated','Alterar Senha'], '')
  context.zsql.usuario_ativar_zsql(col_username=username)   
  mensagem = 'Login do usuário recriado com sucesso!'
  mensagem_obs = 'Usuário: ' + username + ' / Senha inicial: ' + passwd + '. Verifique a necessidade de redefinir os perfis do usuário.'
  url = context.portal_url() + '/cadastros/usuario/usuario_mostrar_proc?nome=' + username
  redirect_url=context.portal_url()+'/mensagem_emitir?tipo_mensagem=success&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs + '&url=' + url

REQUEST.RESPONSE.redirect(redirect_url)

