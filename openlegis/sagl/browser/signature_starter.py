import asyncio
import urllib.request
import aiofiles
from five import grok
from zope.publisher.interfaces.browser import IBrowserRequest
from http import HTTPStatus
import logging
from zope.interface import Interface
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse
import base64
import os
import json
from openlegis.sagl.restpki import *
from Products.CMFCore.utils import getToolByName
from zlib import crc32
from io import BytesIO

grok.templatedir('templates')
logger = logging.getLogger(__name__)

# --- Configurações ---
RESTPKI_URL = 'https://restpkiol.azurewebsites.net/'
VISUAL_REPRESENTATION_TEXT = 'Assinado digitalmente por {{signerName}}'
VISUAL_REPRESENTATION_FOOTNOTE_HEIGHT = 4.94
VISUAL_REPRESENTATION_FOOTNOTE_WIDTH = 8.0

def get_restpki_access_token(context):
    """Obtém o token de acesso do Rest PKI das propriedades do portal."""
    portal = context.portal_url.getPortalObject()
    try:
        token = portal.sapl_documentos.props_sagl.restpki_access_token
        if not token:
            raise ValueError("A propriedade restpki_access_token está vazia.")
        return token
    except AttributeError:
        raise ValueError("As configurações do Rest PKI não foram encontradas.")


async def create_restpki_client(context):
    """Cria e retorna uma instância do RestPkiClient."""
    try:
        access_token = get_restpki_access_token(context)
        return RestPkiClient(RESTPKI_URL, access_token)
    except ValueError as e:
        logger.error(f"Erro ao obter token do Rest PKI: {e}")
        raise
    except Exception as e:
        logger.error(f"Erro ao inicializar o RestPkiClient: {e}")
        raise


async def get_image_content(self) -> bytes:
    """Obtém o conteúdo da imagem do brasão."""
    portal = self.portal_url.getPortalObject()
    id_logo = portal.sapl_documentos.props_sagl.id_logo
    if hasattr(portal.sapl_documentos.props_sagl, id_logo):
       arq = getattr(portal.sapl_documentos.props_sagl, id_logo)
       with BytesIO(bytes(arq.data)) as arq1:
            image = base64.b64encode(arq1.getvalue()).decode('utf8')
    else:
       install_home = os.environ.get('INSTALL_HOME')
       dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/brasao.gif')
       with open(dirpath, "rb") as arq1:
            image = base64.b64encode(arq1.read()).decode('utf8')
    return image


async def _build_base_visual_representation(image_content: bytes) -> dict:
    """Constrói a representação visual base da assinatura."""
    return {
        'text': {
            'text': VISUAL_REPRESENTATION_TEXT,
            'includeSigningTime': True,
            'horizontalAlign': 'Left',
        },
        'image': {
            'resource': {
                'content': image_content,
                'mimeType': 'image/png'
            },
            'horizontalAlign': 'Right'
        }
    }

async def build_visual_representation(context, qtde_assinaturas=None) -> dict:
    """Constrói a representação visual da assinatura."""
    image_content = await get_image_content(context)
    base_representation = await _build_base_visual_representation(image_content)
    restpki_client = await create_restpki_client(context)

    if qtde_assinaturas and int(qtde_assinaturas) <= 3:
        visual_positioning = PadesVisualPositioningPresets.get_footnote(restpki_client)
        visual_positioning['auto']['container'].update({'left': 3, 'bottom': 2, 'right': 3})
        base_representation['position'] = visual_positioning
        base_representation['image']['opacity'] = 40
    elif qtde_assinaturas and int(qtde_assinaturas) > 3:
        visual_positioning = PadesVisualPositioningPresets.get_new_page(restpki_client)
        visual_positioning['auto']['container'].update({'left': 3, 'top': 2, 'bottom': 2, 'right': 3})
        base_representation['position'] = visual_positioning
        base_representation['image']['opacity'] = 40
    else:
        visual_positioning = PadesVisualPositioningPresets.get_footnote(restpki_client)
        visual_positioning['auto']['container']['height'] = VISUAL_REPRESENTATION_FOOTNOTE_HEIGHT
        visual_positioning['auto']['signatureRectangleSize']['width'] = VISUAL_REPRESENTATION_FOOTNOTE_WIDTH
        visual_positioning['auto']['signatureRectangleSize']['height'] = VISUAL_REPRESENTATION_FOOTNOTE_HEIGHT
        base_representation['position'] = visual_positioning
        base_representation['image'].pop('opacity', None)

    return base_representation


@implementer(IPublishTraverse)
class StartPadesSignature(grok.View):
    grok.context(IBrowserRequest)
    grok.require('zope2.View')
    grok.name('start')

    def __init__(self, context, request):
        self.context = context
        self.request = request

    async def render(self):
        portal = self.context.portal_url.getPortalObject()
        file_path = self.context.absolute_url_path()
        logger.info(f"Arquivo para assinatura (path): {file_path}")

        # Remove the leading slash if present
        if file_path.startswith('/'):
            relative_path_str = file_path[1:]
        else:
            relative_path_str = file_path
        path_segments = tuple(relative_path_str.split('/'))
        portal_physical_path = portal.getPhysicalPath()
        full_physical_path = portal_physical_path + path_segments
        full_path_to_traverse = '/' + '/'.join(full_physical_path[1:])

        logger.info(f"Tentando traversar para (dinâmico): {full_path_to_traverse}")

        try:
            arquivo = portal.unrestrictedTraverse(full_path_to_traverse)
            logger.info(f"Arquivo para assinatura: {repr(arquivo)}")

            if not hasattr(arquivo, 'data'):
                raise ValueError("Objeto não possui atributo 'data'.")

            post_data = self.request.form
            qtde_assinaturas = post_data.get('qtde_assinaturas')

            logger.info(f"Dados do POST: qtde_assinaturas={qtde_assinaturas}")

            restpki_client = await create_restpki_client(self.context)
            signature_starter = PadesSignatureStarter(restpki_client)
            with BytesIO(bytes(arquivo.data)) as arquivo_pdf:
                pdf_stream = base64.b64encode(arquivo_pdf.getvalue()).decode('utf8')
            signature_starter.set_pdf_stream(pdf_stream)
            signature_starter.signature_policy_id = StandardSignaturePolicies.PADES_BASIC
            signature_starter.security_context_id = StandardSecurityContexts.PKI_BRAZIL
            signature_starter.visual_representation = await build_visual_representation(self.context, qtde_assinaturas)
            result = await asyncio.to_thread(signature_starter.start_with_webpki)
            self.request.response.setStatus(HTTPStatus.OK)
            self.request.response.setHeader('Content-Type', 'application/json')
            return json.dumps(result)

        except KeyError:
            self.request.response.setStatus(HTTPStatus.NOT_FOUND)
            return json.dumps({'error': 'Arquivo não encontrado.'}, ensure_ascii=False)
        except ValueError as e:
            self.request.response.setStatus(HTTPStatus.BAD_REQUEST)
            return json.dumps({'error': str(e)}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao processar assinatura: {e}")
            self.request.response.setStatus(HTTPStatus.INTERNAL_SERVER_ERROR)
            return json.dumps({'error': 'Erro interno do servidor.'}, ensure_ascii=False)

    def __call__(self):
        return asyncio.run(self.render())

@grok.implementer(IPublishTraverse)
class FinishPadesSignature(grok.View):
    grok.context(IBrowserRequest)
    grok.require('zope2.View')
    grok.name('complete')
    token = None

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.subpath = []

    def publishTraverse(self, request, name):
        self.subpath.append(name)
        if len(self.subpath) == 1:
            self.token = name
        return self

    async def render(self, token=None):
        portal = self.context.portal_url.getPortalObject()
        skins = portal.portal_skins.sk_sagl
        portal_sagl = getToolByName(self, 'portal_sagl')
        mtool = getToolByName(self.context, 'portal_membership')
        member = mtool.getAuthenticatedMember()
        cod_usuario = member.getId()

        if not token:
            self.request.response.setStatus(HTTPStatus.BAD_REQUEST)
            return json.dumps({'error': 'Token não fornecido.'}, ensure_ascii=False)

        post_data = self.request.form
        codigo = post_data.get('codigo')
        tipo_doc = post_data.get('tipo_doc')
        anexo = post_data.get('anexo')
        cod_usuario = post_data.get('cod_usuario')
        logger.info(f"Dados do POST: codigo={codigo}, tipo_doc={tipo_doc}, anexo={anexo}, usuario={cod_usuario}")

        try:
            restpki_client = await create_restpki_client(self.context)
            signature_finisher = PadesSignatureFinisher(restpki_client)
            signature_finisher.token = token
            result = await asyncio.to_thread(signature_finisher.finish)
            arquivo_assinado = signature_finisher.stream_signed_pdf()

            cod_assinatura_doc = None
            if anexo is not None and anexo != '':
                try:
                    anexo_int = int(anexo)
                    for item in skins.zsql.assinatura_documento_obter_zsql(codigo=codigo, anexo=anexo_int, tipo_doc=tipo_doc):
                        cod_assinatura_doc = str(item.cod_assinatura_doc)
                        skins.zsql.assinatura_documento_registrar_zsql(cod_assinatura_doc=item.cod_assinatura_doc, cod_usuario=cod_usuario)
                        break
                except ValueError:
                    logger.error(f"Valor inválido para 'anexo': {anexo}")
                    self.request.response.setStatus(HTTPStatus.BAD_REQUEST)
                    return json.dumps({'error': 'O valor do anexo deve ser um número inteiro válido.'}, ensure_ascii=False)
            else:
                # Se anexo é None ou vazio, não passa o parâmetro 'anexo' na consulta
                for item in skins.zsql.assinatura_documento_obter_zsql(codigo=codigo, tipo_doc=tipo_doc):
                    cod_assinatura_doc = str(item.cod_assinatura_doc)
                    skins.zsql.assinatura_documento_registrar_zsql(cod_assinatura_doc=item.cod_assinatura_doc, cod_usuario=cod_usuario)
                    break

            if not cod_assinatura_doc:
                logger.warning(f"Registro de assinatura não encontrado para codigo={codigo}, anexo={anexo}, tipo_doc={tipo_doc}, usuario={cod_usuario}")

            filename = None
            storage_path = None
            if tipo_doc == 'proposicao':
                storage_path = portal.sapl_documentos.proposicao
                for storage in skins.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
                    filename = f"{codigo}{storage.pdf_signed}"
                    break
            else:
                storage_path = portal.sapl_documentos.documentos_assinados
                filename = f"{cod_assinatura_doc}.pdf" if cod_assinatura_doc else None

            if filename and storage_path:
                if hasattr(storage_path, filename):
                    arquivo_existente = storage_path[filename]
                    arquivo_existente.manage_upload(file=arquivo_assinado)
                    logger.info(f"Arquivo {filename} atualizado em {storage_path.absolute_url()}")
                else:
                    storage_path.manage_addFile(id=filename, file=arquivo_assinado, title=filename)
                    logger.info(f"Arquivo {filename} adicionado em {storage_path.absolute_url()}")

                if tipo_doc != 'proposicao' and tipo_doc != 'peticao' and cod_assinatura_doc:
                    portal_sagl.margem_inferior(codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename)

                self.request.response.setStatus(HTTPStatus.OK)
                self.request.response.setHeader('Content-Type', 'application/json')
                return json.dumps({'filename': filename}, ensure_ascii=False)
            else:
                self.request.response.setStatus(HTTPStatus.INTERNAL_SERVER_ERROR)
                return json.dumps({'error': 'Não foi possível determinar o nome do arquivo ou o caminho de armazenamento.'}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Erro ao finalizar assinatura e salvar o documento: {e}")
            self.request.response.setStatus(HTTPStatus.INTERNAL_SERVER_ERROR)
            return json.dumps({'error': str(e)}, ensure_ascii=False)

    def __call__(self):
        return asyncio.run(self.render(self.token))
