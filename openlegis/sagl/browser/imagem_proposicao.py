# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import View as GrokView, name
from grokcore.security import require
from zope.interface import Interface
from zope.publisher.interfaces import IPublishTraverse

from PIL import Image, ImageOps, ImageColor
from DateTime import DateTime
import io
import logging


# --------------------------------------------------------------------
# logging (não sobrescreve configuração global do Zope)
# --------------------------------------------------------------------
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------
# utilitários
# --------------------------------------------------------------------
def obter_valor_simples(valor):
    """Normaliza valores enviados no request (lista, tupla ou valor único)."""
    while isinstance(valor, (list, tuple)) and valor:
        valor = valor[0]
    return valor


def _parse_cor(cor_str, fallback=(0, 0, 0)):
    """Aceita #RRGGBB, nomes ('white'), rgb(255,255,255). Retorna tupla RGB."""
    if not cor_str:
        return fallback
    try:
        return ImageColor.getrgb(str(cor_str).strip())
    except Exception:
        return fallback


def encaixar_16x9_borda(imagem, largura_final=600, cor=(255, 255, 255)):
    """Padroniza imagem em quadro 16:9 com bordas (sem cortes)."""
    proporcao_alvo = 16 / 9
    w, h = imagem.size
    proporcao_original = w / h

    if proporcao_original > proporcao_alvo:
        nova_largura = largura_final
        nova_altura = int(nova_largura / proporcao_original)
    else:
        nova_altura = int(largura_final / proporcao_alvo)
        nova_largura = int(nova_altura * proporcao_original)

    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:  # Pillow < 9
        resample = Image.LANCZOS

    img_red = imagem.resize((nova_largura, nova_altura), resample)

    altura_final = int(largura_final / proporcao_alvo)
    tela = Image.new("RGB", (largura_final, altura_final), cor)
    x = (tela.width - img_red.width) // 2
    y = (tela.height - img_red.height) // 2
    tela.paste(img_red, (x, y))
    return tela


# --------------------------------------------------------------------
# SalvarImagemProposicao
# --------------------------------------------------------------------
class SalvarImagemProposicaoView(GrokView):
    context(Interface)
    name('salvar-imagem-proposicao')
    require('zope2.View')

    def render(self):
        request = self.request
        context = self.context

        cod_proposicao = obter_valor_simples(request.get('cod_proposicao'))
        indice = obter_valor_simples(request.get('indice'))

        # Cor da borda opcional (ex.: '#FFFFFF', 'black', 'rgb(0,0,0)')
        cor_str = obter_valor_simples(request.get('borda_cor')) or ''
        # fallback = borda preta
        cor_borda = _parse_cor(cor_str, fallback=(0, 0, 0))

        # Busca o arquivo enviado (campo dinâmico file_nom_image{indice})
        arquivo = None
        for key in request.form.keys():
            if key.startswith('file_nom_image'):
                arquivo = request.form.get(key)
                if isinstance(arquivo, (list, tuple)):
                    arquivo = arquivo[0]
                break

        # Sem parâmetros → exibe formulário de upload (snippet)
        if not cod_proposicao or not indice or not arquivo:
            idx = indice or ''
            cod = cod_proposicao or ''
            return f"""
            <div class="alert alert-danger mb-2">Parâmetros ausentes ou arquivo inválido.</div>
            <form id="uploadForm{idx}" enctype="multipart/form-data" method="post">
              <input type="hidden" name="cod_proposicao" value="{cod}">
              <input type="hidden" name="indice" value="{idx}">
              <input type="file" name="file_nom_image{idx}" class="form-control" accept="image/*" onchange="enviarImagem(this.form, {idx or 0})" />
            </form>
            """

        try:
            id_imagem = f"{cod_proposicao}_image_{indice}.jpg"

            # Abre a imagem
            if not hasattr(arquivo, 'read'):
                raise ValueError("Arquivo de imagem não encontrado")

            arquivo.seek(0)
            imagem = Image.open(arquivo)

            # 1) Corrige orientação conforme EXIF (fotos de celular)
            try:
                imagem = ImageOps.exif_transpose(imagem)
            except Exception:
                pass

            # 2) Converte para RGB (JPEG)
            if imagem.mode not in ("RGB", "L"):
                imagem = imagem.convert("RGB")
            elif imagem.mode == "L":
                imagem = imagem.convert("RGB")

            # 3) Padroniza para 16:9 com bordas (preto por padrão)
            imagem = encaixar_16x9_borda(imagem, largura_final=600, cor=cor_borda)

            # 4) Salva em buffer
            buffer = io.BytesIO()
            imagem.save(buffer, format='JPEG', quality=90, optimize=True)
            buffer.seek(0)

            # 5) Persiste no Zope
            sapl = getattr(context, 'sapl_documentos', None)
            if not sapl or not hasattr(sapl, 'proposicao'):
                raise RuntimeError("Pasta sapl_documentos/proposicao não encontrada.")

            pasta_proposicao = sapl.proposicao

            if hasattr(pasta_proposicao, id_imagem):
                pasta_proposicao.manage_delObjects([id_imagem])

            # manage_addImage(id, file) — o Zope detecta content_type automaticamente
            pasta_proposicao.manage_addImage(id_imagem, file=buffer)

            logger.info("Imagem salva: %s (borda=%s)", id_imagem, cor_borda)

            bust = int(DateTime().timeTime())
            return f"""
            <div class="text-center">
              <img class="img-fluid img-thumbnail mb-2"
                   src="{context.portal_url()}/sapl_documentos/proposicao/{id_imagem}?{bust}"
                   style="max-height: 500px;">
              <div class="text-center">
                <button type="button" class="btn btn-sm btn-danger text-white"
                        onclick="ProposicaoManager.excluirImagem({indice}, '{cod_proposicao}')">
                  <i class="far fa-trash-alt me-1"></i> Excluir
                </button>
              </div>
            </div>
            """
        except Exception as e:
            logger.exception("Erro ao processar imagem:")
            idx = str(indice or '')
            cod = str(cod_proposicao or '')
            return f"""
            <div class="alert alert-danger mb-2">Erro ao processar imagem: {e}</div>
            <form id="uploadForm{idx}" enctype="multipart/form-data" method="post">
              <input type="hidden" name="cod_proposicao" value="{cod}">
              <input type="hidden" name="indice" value="{idx}">
              <input type="file" name="file_nom_image{idx}" class="form-control" accept="image/*" onchange="enviarImagem(this.form, {idx or 0})" />
            </form>
            """


# --------------------------------------------------------------------
# ExcluirImagemProposicao
# --------------------------------------------------------------------
class ExcluirImagemProposicaoView(GrokView):
    context(Interface)
    name('excluir-imagem-proposicao')
    require('zope2.View')

    def render(self):
        request = self.request
        context = self.context

        cod_proposicao = obter_valor_simples(request.form.get('cod_proposicao'))
        indice = obter_valor_simples(request.form.get('indice'))

        if not cod_proposicao or not indice:
            return "<div class='text-danger'>Parâmetros ausentes.</div>"

        id_imagem = f"{cod_proposicao}_image_{indice}.jpg"

        sapl = getattr(context, 'sapl_documentos', None)
        if not sapl or not hasattr(sapl, 'proposicao'):
            return "<div class='text-danger'>Pasta de proposições não encontrada.</div>"

        pasta = sapl.proposicao

        try:
            if hasattr(pasta, id_imagem):
                pasta.manage_delObjects([id_imagem])
                logger.info("[Proposição %s] Imagem %s excluída.", cod_proposicao, id_imagem)

            return f"""
              <form id="uploadForm{indice}" enctype="multipart/form-data" method="post">
                <input type="hidden" name="cod_proposicao" value="{cod_proposicao}">
                <input type="hidden" name="indice" value="{indice}">
                <input type="file" name="file_nom_image{indice}" class="form-control" accept="image/*"
                       onchange="enviarImagem(this.form, {indice})" />
              </form>
            """
        except Exception as e:
            logger.exception("Erro ao excluir imagem:")
            return f"<div class='text-danger'>Erro ao excluir imagem: {e}</div>"
