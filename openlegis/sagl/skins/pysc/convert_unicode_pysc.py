## Script (Python) "convert_unicode_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=texto
##title=
##
string = str(texto).encode('utf-8')
result = string.decode('utf-8')
return result
