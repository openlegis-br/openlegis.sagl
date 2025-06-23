## Script (Python) "get_pdf_signatures"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=tipo_doc, codigo, anexo=''
##title=
##

request = container.REQUEST
from Products.CMFCore.utils import getToolByName
utool = getToolByName(context, 'portal_url')
portal = utool.getPortalObject()
from io import BytesIO

def set_file():
    request.set('tipo_doc', tipo_doc)
    request.set('codigo', codigo)
    request.set('anexo', anexo)
    for storage in context.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
        if anexo != None and anexo != '':
           filename = str(codigo) + '_anexo_' + str(anexo) + str(storage.pdf_file)
           pdf_signed = str(storage.pdf_location) + str(codigo) + '_anexo_' + str(anexo) + str(storage.pdf_file)
        else:
           filename = str(codigo) + str(storage.pdf_file)
           pdf_signed = str(storage.pdf_location) + str(codigo) + str(storage.pdf_file)
        arq = context.restrictedTraverse(pdf_signed)
        file_stream = BytesIO(bytes(arq.data))

    result = get_signatures(file_stream, filename)
    return result

def get_signatures(file_stream, filename):
    request.set('file_stream', file_stream)
    request.set('filename', filename)
    path = '@@obter_assinaturas'
    view = context.restrictedTraverse(path)
    result = view()
    return result
    
return set_file()
