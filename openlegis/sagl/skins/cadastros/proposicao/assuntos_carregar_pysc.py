## Script (Python) "assuntos_carregar"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters = svalue
##title=
##
import locale
locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")
import json

context.REQUEST.RESPONSE.setHeader("Access-Control-Allow-Origin", "*")

assuntos=[]

for item in context.zsql.assunto_proposicao_obter_zsql(tip_proposicao=int(svalue)):
    dic = {
           'cod_assunto': item.cod_assunto,
           'des_assunto': item.des_assunto,
           'nom_orgao': item.nom_orgao
          }
    assuntos.append(dic)

assuntos = sorted(assuntos, key=lambda dic: (locale.strxfrm(dic['des_assunto'])))

return json.dumps(assuntos)
