from five import grok
from zope.interface import Interface
from Products.CMFCore.utils import getToolByName
from PIL import Image
import io
from DateTime import DateTime
import logging

logger = logging.getLogger('openlegis')

def obter_valor_simples(valor):
    # Se valor for lista ou tupla, extrai o primeiro elemento recursivamente
    while isinstance(valor, (list, tuple)) and len(valor) > 0:
        valor = valor[0]
    return valor

class SalvarImagemProposicaoView(grok.View):
    grok.context(Interface)
    grok.name('salvar-imagem-proposicao')
    grok.require('zope2.View')

    def render(self):
        request = self.request
        context = self.context

        cod_proposicao = obter_valor_simples(request.get('cod_proposicao'))
        indice = obter_valor_simples(request.get('indice'))

        arquivo = None
        # Procura pelo arquivo enviado com prefixo 'file_nom_image'
        for key in request.form.keys():
            if key.startswith('file_nom_image'):
                arquivo = request.form.get(key)
                if isinstance(arquivo, (list, tuple)):
                    arquivo = arquivo[0]
                break

        if not cod_proposicao or not indice or not arquivo:
            # Retorna o form para reenvio com mensagem de erro
            return f"""
            <div class="alert alert-danger mb-2">Parâmetros ausentes ou arquivo inválido.</div>
            <form id="uploadForm{indice or ''}" enctype="multipart/form-data">
              <input type="hidden" name="cod_proposicao" value="{cod_proposicao or ''}">
              <input type="hidden" name="indice" value="{indice or ''}">
              <input type="file" name="file_nom_image{indice or ''}" class="form-control" accept="image/*" onchange="enviarImagem(this.form, {indice or ''})" />
            </form>
            """

        try:
            id_imagem = f"{cod_proposicao}_image_{indice}.jpg"

            imagem = Image.open(arquivo)
            # Converte para RGB caso tenha canal alfa para evitar erro ao salvar JPEG
            if imagem.mode in ("RGBA", "LA"):
                imagem = imagem.convert("RGB")

            # Redimensiona largura para 600px mantendo proporção
            if imagem.width > 600:
                proporcao = 600 / float(imagem.width)
                nova_altura = int(imagem.height * proporcao)
                imagem = imagem.resize((600, nova_altura), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            imagem.save(buffer, format='JPEG')
            buffer.seek(0)

            sapl = getToolByName(context, 'sapl_documentos')
            pasta_proposicao = sapl.proposicao

            # Remove imagem antiga, se existir
            if hasattr(pasta_proposicao, id_imagem):
                pasta_proposicao.manage_delObjects([id_imagem])

            pasta_proposicao.manage_addImage(id_imagem, file=buffer)

            logger.info(f"Imagem salva: {id_imagem}")

            # Retorna preview da imagem com botão para exclusão
            return f"""
            <div class="text-center">
              <img class="img-fluid img-thumbnail mb-2" src="{context.portal_url()}/sapl_documentos/proposicao/{id_imagem}?{DateTime().timeTime()}" style="max-height: 500px;">
              <div class="text-center">
                <button type="button" class="btn btn-sm btn-danger" onclick="excluirImagem({indice}, '{cod_proposicao}')">Excluir</button>
              </div>
            </div>
            """
        except Exception as e:
            logger.error(f"Erro ao processar imagem: {e}")
            # Forçar transformar índice para string segura
            indice_str = str(indice) if indice else ''
            cod_prop_str = str(cod_proposicao) if cod_proposicao else ''

            return f"""
            <div class="alert alert-danger mb-2">Parâmetros ausentes ou arquivo inválido.</div>
            <form id="uploadForm{indice_str}" enctype="multipart/form-data">
              <input type="hidden" name="cod_proposicao" value="{cod_prop_str}">
              <input type="hidden" name="indice" value="{indice_str}">
              <input type="file" name="file_nom_image{indice_str}" class="form-control" accept="image/*" onchange="enviarImagem(this.form, {indice_str})" />
            </form>
            """

class ExcluirImagemProposicaoView(grok.View):
    grok.context(Interface)
    grok.name('excluir-imagem-proposicao')
    grok.require('zope2.View')

    def render(self):
        request = self.request
        context = self.context

        cod_proposicao = obter_valor_simples(request.form.get('cod_proposicao'))
        indice = obter_valor_simples(request.form.get('indice'))

        if not cod_proposicao or not indice:
            return "<div class='text-danger'>Parâmetros ausentes.</div>"

        id_imagem = f"{cod_proposicao}_image_{indice}.jpg"

        sapl = getToolByName(context, 'sapl_documentos')
        pasta = sapl.proposicao

        try:
            if hasattr(pasta, id_imagem):
                pasta.manage_delObjects([id_imagem])
                logger.info(f"[Proposição {cod_proposicao}] Imagem {id_imagem} excluída.")

            # Retorna form para novo upload após exclusão
            return f"""
              <form id="uploadForm{indice}" enctype="multipart/form-data">
                <input type="hidden" name="cod_proposicao" value="{cod_proposicao}">
                <input type="hidden" name="indice" value="{indice}">
                <input type="file" name="file_nom_image{indice}" class="form-control" accept="image/*" onchange="enviarImagem(this.form, {indice})" />
              </form>
            """
        except Exception as e:
            logger.error(f"Erro ao excluir imagem {id_imagem}: {e}")
            return f"<div class='text-danger'>Erro ao excluir imagem: {e}</div>"
