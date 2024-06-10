## Script (Python) "assinar_proposicao"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_proposicao
##title=
##
from Products.CMFCore.utils import getToolByName

st = getToolByName(context, 'portal_sagl')

lista = []
lista.append(cod_proposicao)

return st.assinar_proposicao(lista)
