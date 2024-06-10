## Script (Python) "periodo_legislatura_format_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=num_legislatura, dat_inicio, dat_fim
##title=
##
'''Esse script tem como finalidade formatar a data que ira aparecer nas
datas possiveis para Legislatura Inicial e Final'''
return str(num_legislatura) + "ª (" + DateTime(dat_inicio, datefmt='international').strftime('%Y') + " - " + DateTime(dat_fim, datefmt='international').strftime('%Y') + ")"
