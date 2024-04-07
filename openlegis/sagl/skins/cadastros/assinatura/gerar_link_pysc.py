## Script (Python) "gerar_link_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=tip_documento, codigo, anexo
##title=
##

for item in context.zsql.assinatura_storage_obter_zsql(tip_documento=tip_documento):
    location = item.pdf_location
    if anexo != None and anexo != '':
       codigo = str(codigo) + '_anexo_' + str(anexo)
       pdf_signed = str(location) + str(codigo) + str(item.pdf_signed)
       pdf_file = str(location) + str(codigo) + str(item.pdf_file)
       nom_arquivo = str(codigo) + str(item.pdf_file)
       nom_arquivo_assinado = str(codigo) + str(item.pdf_signed)
    else:
       pdf_signed = str(location) + str(codigo) + str(item.pdf_signed)
       pdf_file = str(location) + str(codigo) + str(item.pdf_file)
       nom_arquivo = str(codigo) + str(item.pdf_file)
       nom_arquivo_assinado = str(codigo) + str(item.pdf_signed)

try:
   arquivo = context.restrictedTraverse(pdf_signed)
   nom_arquivo = nom_arquivo_assinado
   link = pdf_signed
except:
   arquivo = context.restrictedTraverse(pdf_file)
   nom_arquivo = nom_arquivo
   link = pdf_file

return link
