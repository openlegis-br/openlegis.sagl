## Script (Python) "status_carregar"
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

status = context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao = svalue)
 
fields = list(status.data_dictionary().keys())

listaDic={}     
statusArray = []

status_permitidos = None

if svalue == '0':
   dic = {}
   dic['name'] = ''
   dic['id'] = '0'
   statusArray.append(dic)

for item in status:
    status_permitidos = item['status_adm_permitidos_sel']

if status_permitidos != None:
   if svalue != '0':
      dic = {}
      dic['name'] = 'Selecione'
      dic['id'] = '0'
      statusArray.append(dic)
   for item in str(status_permitidos).split(','):
       statusDict = {}   
       for status in context.zsql.status_tramitacao_administrativo_obter_zsql(cod_status = item):
           statusDict['name'] = status['sgl_status'] + ' - ' + status['des_status']
           statusDict['id'] = status['cod_status']
       statusArray.append(statusDict)
else:
   if svalue != '0':
      statusDict = {}
      statusDict['name'] = '* Configure as permissões da unidade da origem !'
      statusDict['id'] = ''
      statusArray.append(statusDict)

listaDic.update({'options': statusArray})
    
return json.dumps(statusArray)
