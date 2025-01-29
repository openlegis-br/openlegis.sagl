## encoding: utf-8 
## Script (Python) "usuarios_listar"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=tipo_listagem
##title=
##
def get_roles(login):
   zope_user = False
   roles = []
   if context.acl_users.getUser(login):
      real_user = context.acl_users.getUser(login) 
      zope_user = True
      for role in real_user.getRoles():
          roles.append(role)
   roles = [
      e
      for i, e in enumerate(roles)
      if roles.index(e) == i
   ]
   return zope_user, roles

def get_users(tipo_listagem=tipo_listagem):
    usuarios = []
    if tipo_listagem == 'ativos':
       for usuario in context.zsql.usuario_obter_zsql(ind_excluido=0):
           dic = {}
           dic['id'] = usuario.cod_usuario
           dic['ind_excluido'] = usuario.ind_excluido
           dic['login'] = usuario.col_username
           if usuario.nom_completo != None:
              dic['nom_completo'] = usuario.nom_completo
           else:
              dic['nom_completo'] = usuario.nom_usuario
           dic['zope_user'] = get_roles(usuario.col_username)[0]
           if dic['zope_user'] == False:
              dic['status'] = 'Excluído do Zope'
           elif usuario.ind_ativo == 1:
              dic['status'] = 'Ativo'
           elif usuario.ind_ativo == 0:
              dic['status'] = 'Inativo'
           else:
              dic['status'] = 'Incompleto'
           dic['roles'] = get_roles(usuario.col_username)[1]
           if context.acl_users.getUser(usuario.col_username):
              usuarios.append(dic)
    if tipo_listagem == 'inativos':
       for usuario in context.zsql.usuario_obter_zsql(ind_excluido=0):
           dic = {}
           dic['id'] = usuario.cod_usuario
           dic['ind_excluido'] = usuario.ind_excluido
           dic['login'] = usuario.col_username
           if usuario.nom_completo != None:
              dic['nom_completo'] = usuario.nom_completo
           else:
              dic['nom_completo'] = usuario.nom_usuario
           dic['zope_user'] = get_roles(usuario.col_username)[0]
           if dic['zope_user'] == False:
              dic['status'] = 'Inativo'
           elif usuario.ind_ativo == 1:
              dic['status'] = 'Ativo'
           elif usuario.ind_ativo == 0:
              dic['status'] = 'Inativo'
           else:
              dic['status'] = 'Incompleto'
           dic['roles'] = get_roles(usuario.col_username)[1]
           if not context.acl_users.getUser(usuario.col_username):
              usuarios.append(dic)
    if tipo_listagem == 'excluidos':
       for usuario in context.zsql.usuario_obter_zsql(ind_excluido=1):
           dic = {}
           dic['id'] = usuario.cod_usuario
           dic['ind_excluido'] = usuario.ind_excluido
           dic['login'] = usuario.col_username
           if usuario.nom_completo != None:
              dic['nom_completo'] = usuario.nom_completo
           else:
              dic['nom_completo'] = usuario.nom_usuario
           dic['zope_user'] = get_roles(usuario.col_username)[0]
           if dic['zope_user'] == False:
              dic['status'] = 'Excluído'
           elif usuario.ind_ativo == 1:
              dic['status'] = 'Ativo'
           elif usuario.ind_ativo == 0:
              dic['status'] = 'Inativo'
           else:
              dic['status'] = 'Incompleto'
           dic['roles'] = get_roles(usuario.col_username)[1]
           usuarios.append(dic)
    if tipo_listagem == 'incompletos':
       for usuario in context.acl_users.getUsers():
           dic = {}
           dic['id'] = ''
           dic['login'] = str(usuario)
           dic['nom_completo'] = 'Não cadastrado'
           dic['zope_user'] = True
           dic['status'] = 'Incompleto'
           dic['roles'] = get_roles(str(usuario))[1]
           if not context.zsql.usuario_obter_zsql(col_username=usuario):
              usuarios.append(dic)

    return usuarios

return get_users(tipo_listagem=tipo_listagem)

