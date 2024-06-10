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
    context.temp_folder.manage_addFile(id=filename,file=file)
    return otimize_file(filename, title)

def otimize_file(filename=filename, title=title):
    request.set('filename', filename)
    request.set('title', title)
    path = '@@otimizar_arquivo'
    view = context.restrictedTraverse(path)
    result = view()
    return result

return upload_file(file, title)
