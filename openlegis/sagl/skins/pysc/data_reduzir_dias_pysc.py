## Script (Python) "data_reduzir_dias"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=data
##title=
##
""" Retorna data 6 dias menor. """
from DateTime import DateTime
import datetime

zope_DT = DateTime(data=data) # data informada

python_dt = zope_DT.asdatetime() # converte em objeto datetime

sts = python_dt - datetime.timedelta(days=6) # menos 5 dias

zope_DT = DateTime(sts, datefmt='international').strftime('%Y/%m/%d') # reconverte objeto pata DateTime

return(zope_DT)
