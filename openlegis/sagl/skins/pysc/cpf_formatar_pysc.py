## Script (Python) "cpf_formatar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=numero
##title=
##
cpf = numero[:3] + "." + numero[3:6] + "." + numero[6:9] + "-" + numero[9:]
return cpf

