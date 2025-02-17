## Script (Python) "usuarios_carregar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters= svalue
##title=
##
import json

context.REQUEST.RESPONSE.setHeader("Access-Control-Allow-Origin", "*")

usuarios = context.zsql.usuario_unid_tram_obter_zsql(cod_unid_tramitacao = svalue)
 
fields = list(usuarios.data_dictionary().keys())

listaDic={}     
usuarioArray = []

dic = {}
dic['name'] = ''
dic['id'] = ''
usuarioArray.append(dic)

for usuario in usuarios:
    usuarioDict = {}
    for field in fields:
        nom_cargo = ''
        if usuario['nom_cargo'] != '':
           nom_cargo = ' (' + usuario['nom_cargo'] + ')'    
        usuarioDict['name'] = usuario['nom_completo'] + nom_cargo
        usuarioDict['id'] = usuario['cod_usuario']
    usuarioArray.append(usuarioDict)
usuarioArray.sort(key=lambda dic: dic['name'])
listaDic.update({'options': usuarioArray})
    
return json.dumps(usuarioArray)

