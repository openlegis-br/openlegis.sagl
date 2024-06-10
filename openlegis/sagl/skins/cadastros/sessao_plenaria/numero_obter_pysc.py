## Script (Python) "numero_obter_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=tvalue, svalue, dat_sessao=""
##title=
##
import simplejson as json

context.REQUEST.RESPONSE.setHeader("Access-Control-Allow-Origin", "*")

cod_periodo = ''
nom_periodo = 'Periodo não cadastrado.'

if dat_sessao != '':
   for periodo in context.zsql.periodo_sessao_obter_zsql(tip_sessao = tvalue, data_sessao = dat_sessao):
       cod_periodo = periodo.cod_periodo
       nom_periodo = str(periodo.num_periodo) + 'º Período' + ' (' + str(periodo.data_inicio) + ' - ' + str(periodo.data_fim) + ')'
       

numeroArray = []
numero = ""
if tvalue != None:
   for item in context.zsql.numero_sessao_plenaria_obter_zsql(tip_sessao = tvalue, cod_sessao_leg = svalue, cod_periodo=cod_periodo):
       dic = {}
       dic['num_sessao_plen'] = item.novo_numero_sessao
       dic['cod_periodo_sessao'] = cod_periodo
       dic['nom_periodo'] = nom_periodo
       numeroArray.append(dic)
     
return json.dumps(numeroArray)
