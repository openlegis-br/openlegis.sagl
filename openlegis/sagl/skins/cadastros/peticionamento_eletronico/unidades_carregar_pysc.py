## Script (Python) "unidades_carregar_pysc"
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

listaDic={}     
unidadeArray = []

if svalue != '0' and svalue != '':
   dic = {}
   dic['name'] = '- selecione uma unidade - '
   dic['id'] = ''
   unidadeArray.append(dic)
   for tipo in context.zsql.tipo_peticionamento_obter_zsql(tip_peticionamento = svalue):
       cod_unidade = tipo.cod_unid_tram_dest
   if cod_unidade != None and cod_unidade != '':
      for unidade in context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao = cod_unidade):
          unidadeDict = {}
          unidadeDict['name'] = unidade['nom_unidade_join']
          unidadeDict['id'] = unidade['cod_unid_tramitacao']
          unidadeArray.append(unidadeDict)
   else:
      for unidade in context.zsql.unidade_tramitacao_obter_zsql(ind_adm=1):
          unidadeDict = {}
          unidadeDict['name'] = unidade['nom_unidade_join']
          unidadeDict['id'] = unidade['cod_unid_tramitacao']
          unidadeArray.append(unidadeDict)   
       
   listaDic.update({'options': unidadeArray})
    
return json.dumps(unidadeArray)
