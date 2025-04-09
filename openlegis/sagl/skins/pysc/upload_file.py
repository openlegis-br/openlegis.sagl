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
from io import BytesIO

def upload_file(file, title):
    #context.temp_folder.manage_addFile(id=filename,file=file)
    if hasattr(file, 'read'):
        file = BytesIO(file.read())
    elif isinstance(file, bytes):
        file = BytesIO(file)
    elif hasattr(file, 'filename') and hasattr(file, 'data'):
        file = BytesIO(file.data)

    result = otimize_file(file, title)
    
    if isinstance(result, bytes):  # Use type(b'') to represent the bytes type
        file_stream = result
        return file_stream
    elif hasattr(result, 'read'):
        return result.read()
    else:  # Use type({}) to represent the dict type
        file_stream = result['file_stream']
        signatures = result['file_stream']
        return file_stream

def otimize_file(filename=file, title=title):
    request.set('filename', filename)
    request.set('title', title)
    path = '@@otimizar_arquivo'
    view = context.restrictedTraverse(path)
    result = view()
    return result

return upload_file(file, title)
