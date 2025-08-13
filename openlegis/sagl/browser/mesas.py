# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import name
from grokcore.security import require
from grokcore.view import View as GrokView
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface
from io import BytesIO
import requests
from PIL import Image, UnidentifiedImageError
import json
from DateTime import DateTime
import re

IMAGE_TIMEOUT = 3  # s

@implementer(IPublishTraverse)
class Mesas(GrokView):
    """API de períodos de composição da Mesa Diretora (registro automático via grokcore)."""

    context(Interface)
    name('mesas')           # URL: @@mesas
    require('zope2.View')

    item_id = None

    # ------------- traversal -------------

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    # ------------- utils -------------

    def _portal_url(self):
        try:
            return self.context.portal_url().rstrip('/')
        except Exception:
            portal = self.context.portal_url.getPortalObject()
            return portal.absolute_url().rstrip('/')

    def _json(self, data):
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)

    def _image_meta_if_exists(self, url, filename):
        """Valida com HEAD e gera metadados se a imagem existir."""
        try:
            h = requests.head(url, timeout=IMAGE_TIMEOUT, allow_redirects=True)
            if h.status_code != 200:
                return []
            resp = requests.get(url, timeout=IMAGE_TIMEOUT)
            img = Image.open(BytesIO(resp.content))
            fmt = (img.format or '').lower()
            return [{
                "content-type": f"image/{fmt}" if fmt else "image",
                "download": url,
                "filename": filename,
                "width": str(getattr(img, 'width', '')),
                "height": str(getattr(img, 'height', '')),
                "size": str(len(resp.content)),
            }]
        except (UnidentifiedImageError, requests.RequestException):
            return []

    # ------------- endpoints -------------

    def lista(self):
        """Lista todos os períodos de composição de Mesa."""
        hoje = DateTime()  # objeto DateTime para comparação correta
        service_url = f"{self.portal_url}/@@mesas"

        periodos = self.context.zsql.periodo_comp_mesa_obter_zsql(ind_excluido=0)
        itens = []

        for item in periodos:
            try:
                inicio = DateTime(item.dat_inicio_periodo, datefmt='international')
                fim    = DateTime(item.dat_fim_periodo,    datefmt='international')
            except Exception:
                # pula registros com datas inválidas
                continue

            dic = {
                "@id":        f"{service_url}/{item.cod_periodo_comp}",
                "@type":      "Mesa",
                "id":         str(item.cod_periodo_comp),
                "start":      inicio.strftime("%Y-%m-%d"),
                "end":        fim.strftime("%Y-%m-%d"),
                "title":      f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}",
                "description":"Período de composição na "
                              f"{item.num_legislatura}ª Legislatura",
                "legislatura":    f"{item.num_legislatura}ª Legislatura",
                "legislatura_id": f"{self.portal_url}/@@legislaturas/{item.num_legislatura}",
                # atual: intervalo inclusivo (>= início e <= fim)
                "atual":     (inicio <= hoje <= fim),
            }
            itens.append(dic)

        # Ordena do mais recente para o mais antigo pelo início
        itens.sort(key=lambda d: d["start"], reverse=True)

        return {
            "@id":        service_url,
            "@type":      "Mesas",
            "description":"Lista de períodos de composição",
            "items":      itens,
        }

    def get_one(self, cod_periodo_comp):
        """Detalha um período e lista seus membros da Mesa."""
        try:
            cod = int(cod_periodo_comp)
        except (TypeError, ValueError):
            return {}

        resultados = list(self.context.zsql.periodo_comp_mesa_obter_zsql(
            cod_periodo_comp=cod, ind_excluido=0
        ))
        if not resultados:
            return {}

        item = resultados[0]
        try:
            inicio = DateTime(item.dat_inicio_periodo, datefmt='international')
            fim    = DateTime(item.dat_fim_periodo,    datefmt='international')
        except Exception:
            return {}

        hoje = DateTime()
        base_url = f"{self.portal_url}/@@mesas/{cod}"

        return {
            "@id":           base_url,
            "@type":         "Mesa",
            "id":            str(item.cod_periodo_comp),
            "start":         inicio.strftime("%Y-%m-%d"),
            "end":           fim.strftime("%Y-%m-%d"),
            "title":         f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}",
            "description":   "Composição da mesa diretora",
            "legislatura":   f"{item.num_legislatura}ª Legislatura",
            "legislatura_id":f"{self.portal_url}/@@legislaturas/{item.num_legislatura}",
            "atual":         (inicio <= hoje <= fim),
            "items":         self._get_membros(cod),
        }

    def _get_membros(self, cod_periodo_comp):
        """Retorna membros da Mesa para um período."""
        membros = []
        fotos_base = f"{self.portal_url}/sapl_documentos/parlamentar/fotos"

        # prioridade de cargos (quanto menor o número, mais alto na lista)
        CARGO_ORDER = {
            "Presidente": 1,
            "Vice-Presidente": 2,  
            "1º Vice-Presidente": 3,
            "2º Vice-Presidente": 4,
            "3º Vice-Presidente": 5,
            "1º Secretário": 6,
            "2º Secretário": 7,
            "3º Secretário": 8,
        }

        for comp in self.context.zsql.composicao_mesa_obter_zsql(
            cod_periodo_comp=cod_periodo_comp, ind_excluido=0
        ):
            # Cargo
            cargos = list(self.context.zsql.cargo_mesa_obter_zsql(
                cod_cargo=comp.cod_cargo, ind_excluido=0
            ))
            cargo = cargos[0] if cargos else None
            cargo_nome = cargo.des_cargo if cargo else ""

            # Parlamentar
            pars = list(self.context.zsql.parlamentar_obter_zsql(
                cod_parlamentar=comp.cod_parlamentar, ind_excluido=0
            ))
            if not pars:
                continue
            parl = pars[0]

            membro = {
                "@id":         f"{self.portal_url}/@@vereadores/{comp.cod_parlamentar}",
                "@type":       "ParticipanteMesa",
                "id":          str(parl.cod_parlamentar),
                "title":       parl.nom_parlamentar,
                "description": parl.nom_completo,
                "cargo":       cargo_nome,
            }

            # Foto
            foto_key = f"{comp.cod_parlamentar}_foto_parlamentar"
            try:
                fotos_container = self.context.sapl_documentos.parlamentar.fotos
            except Exception:
                fotos_container = None

            if fotos_container and hasattr(fotos_container, foto_key):
                url_foto = f"{fotos_base}/{foto_key}"
                membro["url_foto"] = url_foto
                membro["image"] = self._image_meta_if_exists(url_foto, foto_key)
            else:
                membro["url_foto"] = f"{self.portal_url}/imagens/avatar.png"
                membro["image"] = []

            # Partidos ativos
            partidos = []
            for fil in self.context.zsql.filiacao_obter_zsql(
                ind_excluido=0, cod_parlamentar=comp.cod_parlamentar
            ):
                if not getattr(fil, 'dat_desfiliacao', None):
                    parts = list(self.context.zsql.partido_obter_zsql(
                        ind_excluido=0, cod_partido=fil.cod_partido
                    ))
                    if parts:
                        partidos.append({
                            "token": parts[0].sgl_partido,
                            "title": parts[0].nom_partido,
                        })
            membro["partido"] = partidos

            # prioridade numérica para ordenação
            membro["_ord"] = CARGO_ORDER.get(cargo_nome, 999)
            membros.append(membro)

        # Ordena por prioridade de cargo e depois por nome completo
        membros.sort(key=lambda x: (x["_ord"], x["description"]))
        # remove o campo auxiliar antes de retornar
        for m in membros:
            m.pop("_ord", None)
        return membros
    # ------------- render -------------

    def render(self, cod_periodo_comp=''):
        # inicializa URLs
        self.portal_url = self._portal_url()

        if self.item_id:
            data = self.get_one(self.item_id)
        elif cod_periodo_comp:
            data = self.get_one(cod_periodo_comp)
        else:
            data = self.lista()

        return self._json(data)
