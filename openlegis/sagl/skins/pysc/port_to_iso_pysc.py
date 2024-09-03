## Script (Python) "port_to_iso_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=data
##title=
##
from DateTime import DateTime

data = DateTime(str(data), datefmt='international').strftime('%Y-%m-%d')

return data

#data = str(data).strip()
#if data!='':
# datapart=str(data).split(' ')
# data=str(datapart[0]).split('/')
# if len(datapart) > 1:
#  return data[2]+'-'+data[1]+'-'+data[0]+' '+datapart[1]
# else:
#  return data[2]+'-'+data[1]+'-'+data[0]
