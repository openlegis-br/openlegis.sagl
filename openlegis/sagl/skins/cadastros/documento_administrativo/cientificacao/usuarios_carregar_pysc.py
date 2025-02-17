## Script (Python) "usuarios_carregar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters= svalue, cod_documento
##title=
##
import json

context.REQUEST.RESPONSE.setHeader("Access-Control-Allow-Origin", "*")

if svalue != '':
   lst_usuarios = []
   for usuario in context.zsql.usuario_unid_tram_obter_zsql(cod_unid_tramitacao = svalue):
       nom_cargo = ''
       if usuario.nom_cargo != '':
          nom_cargo = ' (' + usuario.nom_cargo + ')'   
       dic = {
           'id': usuario.cod_usuario,
           'name': usuario.nom_completo + nom_cargo,
       }
       if usuario.ind_leg != '0' or usuario.ind_adm != '0':
          lst_usuarios.append(dic)
   lst_usuarios.sort(key=lambda dic: dic['name'])
   return json.dumps(lst_usuarios)

else:
   lst_usuarios = []
   for usuario in context.zsql.usuario_obter_zsql(ind_excluido=0, ind_ativo=1):
       nom_cargo = ''
       if usuario.nom_cargo != '':
          nom_cargo = ' (' + usuario.nom_cargo + ')'
       dic = {
           'id': usuario.cod_usuario,
           'name': usuario.nom_completo + nom_cargo,
       }
       lst_usuarios.append(dic)
   return json.dumps(lst_usuarios)
 
