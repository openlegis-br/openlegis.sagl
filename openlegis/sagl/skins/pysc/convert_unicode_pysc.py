## Script (Python) "convert_unicode_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=texto
##title=
##
string = str(texto).encode('iso-8859-1', 'ignore')
result = string.decode("iso-8859-1")
return result
