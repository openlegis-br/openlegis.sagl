## Script (Python) "proposicao_gerar_pdf"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_proposicao
##title=
import json
from Products.CMFCore.utils import getToolByName

REQUEST = container.REQUEST
RESPONSE = REQUEST.RESPONSE
st = getToolByName(context, 'portal_sagl')

try:
    st.proposicao_gerar_pdf(cod_proposicao)
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return json.dumps({"success": True, "message": "PDF gerado com sucesso!"})
except Exception as e:
    RESPONSE.setStatus(500)
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return json.dumps({"success": False, "message": f"Erro ao gerar PDF: {e}"})
