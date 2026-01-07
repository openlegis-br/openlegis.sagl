## Script (Python) "verificar_logo"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##

from Products.CMFCore.utils import getToolByName
from ZODB.POSException import POSKeyError

# Obtém o id_logo
id_logo = getattr(context.sapl_documentos.props_sagl, 'id_logo', None)
existe_logo = 0

if id_logo:
    try:
        # Tenta obter os IDs das imagens sem carregá-las
        image_ids = context.sapl_documentos.props_sagl.objectIds('Image')
        
        # Verifica cada imagem de forma segura
        for image_id in image_ids:
            try:
                # Tenta acessar o objeto
                imagem = getattr(context.sapl_documentos.props_sagl, image_id, None)
                if imagem and hasattr(imagem, 'id') and imagem.id == id_logo:
                    existe_logo = 1
                    break
            except (POSKeyError, AttributeError, KeyError):
                # Ignora objetos que não podem ser carregados
                continue
    except (POSKeyError, AttributeError, KeyError):
        # Ignora erros ao acessar objectIds
        pass

return existe_logo
