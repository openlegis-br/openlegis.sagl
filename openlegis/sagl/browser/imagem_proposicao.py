from five import grok
from zope.interface import Interface
from Products.CMFCore.utils import getToolByName
from PIL import Image, ImageOps, ImageColor
import io
from DateTime import DateTime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BORDAS_COR_PADRAO = ('black')  # branco

def obter_valor_simples(valor):
    """Normaliza valores enviados no request (lista, tupla ou valor único)."""
    while isinstance(valor, (list, tuple)) and len(valor) > 0:
        valor = valor[0]
    return valor

def _parse_cor(cor_str, fallback=BORDAS_COR_PADRAO):
    """Aceita #RRGGBB, nomes ('white'), rgb(255,255,255)."""
    if not cor_str:
        return fallback
    try:
        return ImageColor.getrgb(str(cor_str).strip())
    except Exception:
        return fallback

def encaixar_16x9_borda(imagem, largura_final=600, cor=(255, 255, 255)):
    """Padroniza imagem no formato 16:9 com bordas (sem cortes)."""
    proporcao_alvo = 16 / 9

    # Redimensiona proporcionalmente para caber no quadro 16:9
    w, h = imagem.size
    proporcao_original = w / h

    if proporcao_original > proporcao_alvo:
        # imagem mais larga → encaixa pela largura
        nova_largura = largura_final
        nova_altura = int(nova_largura / proporcao_original)
    else:
        # imagem mais alta (retrato) → encaixa pela altura do quadro 16:9
        nova_altura = int(largura_final / proporcao_alvo)
        nova_largura = int(nova_altura * proporcao_original)

    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS

    img_red = imagem.resize((nova_largura, nova_altura), resample)

    # Cria tela 16:9 e centraliza
    tela = Image.new("RGB", (largura_final, int(largura_final / proporcao_alvo)), cor)
    x = (tela.width - img_red.width) // 2
    y = (tela.height - img_red.height) // 2
    tela.paste(img_red, (x, y))
    return tela

class SalvarImagemProposicaoView(grok.View):
    grok.context(Interface)
    grok.name('salvar-imagem-proposicao')
    grok.require('zope2.View')

    def render(self):
        request = self.request
        context = self.context

        cod_proposicao = obter_valor_simples(request.get('cod_proposicao'))
        indice = obter_valor_simples(request.get('indice'))

        # Cor da borda opcional (ex.: '#FFFFFF', 'black', 'rgb(0,0,0)')
        cor_str = obter_valor_simples(request.get('borda_cor')) or ''
        cor_borda = _parse_cor(cor_str, BORDAS_COR_PADRAO)

        # Busca o arquivo enviado
        arquivo = None
        for key in request.form.keys():
            if key.startswith('file_nom_image'):
                arquivo = request.form.get(key)
                if isinstance(arquivo, (list, tuple)):
                    arquivo = arquivo[0]
                break

        # Se não houver parâmetros, retorna formulário de upload
        if not cod_proposicao or not indice or not arquivo:
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

            # Abre a imagem
            if hasattr(arquivo, 'read'):
                arquivo.seek(0)
                imagem = Image.open(arquivo)
            else:
                raise ValueError("Arquivo de imagem não encontrado")

            # 1) Corrige orientação conforme EXIF (fotos de celular)
            try:
                imagem = ImageOps.exif_transpose(imagem)
            except Exception:
                pass  # se não tiver EXIF, segue o fluxo

            # 2) Remove canal alfa se presente (salvar em JPEG)
            if imagem.mode in ("RGBA", "LA"):
                imagem = imagem.convert("RGB")
            elif imagem.mode not in ("RGB", "L"):
                imagem = imagem.convert("RGB")

            # 3) Padroniza para 16:9 com bordas (brancas por padrão)
            imagem = encaixar_16x9_borda(imagem, largura_final=600, cor=cor_borda)

            # 4) Salva em buffer
            buffer = io.BytesIO()
            imagem.save(buffer, format='JPEG', quality=90, optimize=True)
            buffer.seek(0)

            # 5) Salva no Zope
            sapl = getToolByName(context, 'sapl_documentos')
            pasta_proposicao = sapl.proposicao

            if hasattr(pasta_proposicao, id_imagem):
                pasta_proposicao.manage_delObjects([id_imagem])

            pasta_proposicao.manage_addImage(id_imagem, file=buffer)

            logger.info(f"Imagem salva com sucesso: {id_imagem} (borda_cor={cor_borda})")

            # Retorna HTML com preview
            return f"""
            <div class="text-center">
              <img class="img-fluid img-thumbnail mb-2" src="{context.portal_url()}/sapl_documentos/proposicao/{id_imagem}?{int(DateTime().timeTime())}" style="max-height: 500px;">
              <div class="text-center">
                <button type="button" class="btn btn-sm btn-danger text-white" onclick="ProposicaoManager.excluirImagem({indice}, '{cod_proposicao}')"><i class="far fa-trash-alt me-1"></i> Excluir</button>
              </div>
            </div>
            """
        except Exception as e:
            logger.error(f"Erro ao processar imagem: {e}")
            indice_str = str(indice) if indice else ''
            cod_prop_str = str(cod_proposicao) if cod_proposicao else ''
            return f"""
            <div class="alert alert-danger mb-2">Erro ao processar imagem: {e}</div>
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
