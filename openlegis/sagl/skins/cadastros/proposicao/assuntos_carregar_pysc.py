## Script (Python) "assuntos_carregar"
##parameters = svalue
import locale
import json

try:
    locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_ALL, "")

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE
RESPONSE.setHeader("Access-Control-Allow-Origin", "*")
RESPONSE.setHeader("Content-Type", "application/json; charset=utf-8")

assuntos = []

# Checagem segura do parâmetro
if not svalue or not str(svalue).isdigit():
    return json.dumps([])

tip_proposicao = int(svalue)

for item in context.zsql.assunto_proposicao_obter_zsql(tip_proposicao=tip_proposicao):
    assuntos.append({
        'cod_assunto': item.cod_assunto,
        'des_assunto': item.des_assunto,
        'nom_orgao': item.nom_orgao
    })

assuntos = sorted(assuntos, key=lambda d: locale.strxfrm(d['des_assunto'] or ""))

return json.dumps(assuntos, ensure_ascii=False)
