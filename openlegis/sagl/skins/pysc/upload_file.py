## Script (Python) "upload_file"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=file, title
##title=
##
import uuid
request = container.REQUEST
RESPONSE =  request.RESPONSE
filename = str(uuid.uuid4())+'.pdf'

def upload_file(file, title):
    #context.temp_folder.manage_addFile(id=filename,file=file)
    result = otimize_file(file, title)
    if isinstance(result, bytes):
       file_stream = result
       return file_stream
    else:
       file_stream = result['file_stream']
       signatures = result['signatures']
       return file_stream

def otimize_file(filename=filename, title=title):
    request.set('filename', filename)
    request.set('title', title)
    path = '@@otimizar_arquivo'
    view = context.restrictedTraverse(path)
    result = view()
    return result

return upload_file(file, title)
