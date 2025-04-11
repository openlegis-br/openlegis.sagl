## Script (Python) "upload_file"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=file, title, tipo_doc="", codigo=""
##title=
##
import uuid
request = container.REQUEST
RESPONSE =  request.RESPONSE
filename = str(uuid.uuid4())+'.pdf'
from io import BytesIO

def upload_file(file, title):
    # trata objeto file para envio
    if hasattr(file, 'read'):
        file = BytesIO(file.read())
    elif isinstance(file, bytes):
        file = BytesIO(file)
    elif hasattr(file, 'filename') and hasattr(file, 'data'):
        file = BytesIO(file.data)

    result = otimize_file(file, title)
    # trata o resultado
    if isinstance(result, bytes):
        file_stream = result
        return file_stream
    elif hasattr(result, 'read'):
        return result.read()
    else:
        file_stream = result['file_stream']
        signatures = result['signatures']
        if str(tipo_doc) == 'proposicao':
           cpfs_inseridos = []
           cod_assinatura_doc = context.cadastros.assinatura.generate_verification_code()
           for i, item in enumerate(signatures):
               signer_cpf = item['signer_cpf']
               if signer_cpf not in cpfs_inseridos:
                  usuarios = context.zsql.usuario_obter_zsql(num_cpf=signer_cpf)
                  for usuario in usuarios:
                      ind_prim_assinatura = 1 if i == 0 else 0
                      context.zsql.assinaturas_capturadas_incluir_zsql(
                                  cod_assinatura_doc=cod_assinatura_doc,
                                  codigo=codigo,
                                  tipo_doc=tipo_doc,
                                  cod_solicitante=usuario.cod_usuario,
                                  cod_usuario=usuario.cod_usuario,
                                  ind_prim_assinatura=ind_prim_assinatura,
                                  ind_assinado = 1,
                                  dat_solicitacao=DateTime(item['signing_time'], datefmt='international').strftime('%Y/%m/%d %H:%M:%S'),
                                  dat_assinatura=DateTime(item['signing_time'], datefmt='international').strftime('%Y/%m/%d %H:%M:%S')
                                  )
                      cpfs_inseridos.append(signer_cpf)
           nom_pdf = str(codigo)+'_signed.pdf'
           context.sapl_documentos.proposicao.manage_addFile(id=nom_pdf, file=file_stream)  

        return file_stream

def otimize_file(filename=file, title=title):
    request.set('filename', filename)
    request.set('title', title)
    path = '@@otimizar_arquivo'
    view = context.restrictedTraverse(path)
    result = view()
    return result

return upload_file(file, title)
