## Script (Python) "iso_to_port_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=tudo
##title=
##

from DateTime import DateTime

data = DateTime(str(tudo), datefmt='international').strftime('%d/%m/%Y')

return data

#tudo=str(tudo)
#if len(tudo) > 0:
# datapart=str(tudo).split(' ')
# if datapart[0].find('-')!=-1:
#  data=str(datapart[0]).split('-')
# elif datapart[0].find('/')!=-1:
#  data=str(datapart[0]).split('/')
# if len(datapart) > 1:
#  return data[2]+'/'+data[1]+'/'+data[0]
#  return data[2]+'/'+data[1]+'/'+data[0]+' '+str(datapart[1]).split('-')[0]
# else:
#  return data[2]+'/'+data[1]+'/'+data[0]
#else:
# return ''
