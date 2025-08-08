# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface
from io import BytesIO
from Acquisition import aq_inner
import requests
from PIL import Image, UnidentifiedImageError
import json
from DateTime import DateTime
import re

@implementer(IPublishTraverse)
class Mesas(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('mesas')

    item_id = None

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    def lista(self):
        hoje = DateTime().strftime("%Y-%m-%d")
        service_url = f"{self.portal_url}/@@mesas"
        periodos = self.context.zsql.periodo_comp_mesa_obter_zsql(ind_excluido=0)
        lista = []

        for item in periodos:
            inicio = DateTime(item.dat_inicio_periodo, datefmt='international')
            fim    = DateTime(item.dat_fim_periodo,    datefmt='international')
            start_str = inicio.strftime("%Y-%m-%d")
            end_str   = fim.strftime("%Y-%m-%d")

            dic = {
                "@id":        f"{service_url}/{item.cod_periodo_comp}",
                "@type":      "Mesa",
                "id":         str(item.cod_periodo_comp),
                "start":      start_str,
                "end":        end_str,
                "title":      f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}",
                "description":"Período de composição na " 
                             + f"{item.num_legislatura}ª Legislatura",
                "legislatura":    f"{item.num_legislatura}ª Legislatura",
                "legislatura_id": f"{self.portal_url}/@@legislaturas/{item.num_legislatura}",
                "atual":     hoje > start_str and hoje < end_str,
            }
            lista.append(dic)

        # ordena do mais recente para o mais antigo
        lista.sort(key=lambda d: d["start"], reverse=True)

        return {
            "@id":        service_url,
            "@type":      "Mesas",
            "description":"Lista de períodos de composição",
            "items":      lista,
        }

    def get_one(self, cod_periodo_comp):
        cod = int(cod_periodo_comp)
        resultados = list(self.context.zsql.periodo_comp_mesa_obter_zsql(
            cod_periodo_comp=cod, ind_excluido=0
        ))
        if not resultados:
            return {}

        item  = resultados[0]
        inicio = DateTime(item.dat_inicio_periodo, datefmt='international')
        fim    = DateTime(item.dat_fim_periodo,    datefmt='international')
        start_str = inicio.strftime("%Y-%m-%d")
        end_str   = fim.strftime("%Y-%m-%d")

        base_url    = f"{self.portal_url}/@@mesas/{cod}"
        dic_mesa = {
            "@id":        base_url,
            "@type":      "Mesa",
            "id":         str(item.cod_periodo_comp),
            "start":      start_str,
            "end":        end_str,
            "title":      f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}",
            "description":"Composição da mesa diretora",
            "legislatura":    f"{item.num_legislatura}ª Legislatura",
            "legislatura_id": f"{self.portal_url}/@@legislaturas/{item.num_legislatura}",
            "atual":     DateTime().strftime("%Y-%m-%d") > start_str 
                         and DateTime().strftime("%Y-%m-%d") < end_str,
            "items":     self._get_membros(cod),
        }
        return dic_mesa

    def _get_membros(self, cod_periodo_comp):
        membros = []
        fotos_url = f"{self.portal_url}/sapl_documentos/parlamentar/fotos"
        for comp in self.context.zsql.composicao_mesa_obter_zsql(
            cod_periodo_comp=cod_periodo_comp, ind_excluido=0
        ):
            cargo = self.context.zsql.cargo_mesa_obter_zsql(
                cod_cargo=comp.cod_cargo, ind_excluido=0
            )[0]
            parl = self.context.zsql.parlamentar_obter_zsql(
                cod_parlamentar=comp.cod_parlamentar, ind_excluido=0
            )[0]

            membro = {
                "@id":        f"{self.portal_url}/@@vereadores/{comp.cod_parlamentar}",
                "@type":      "ParticipanteMesa",
                "id":         str(parl.cod_parlamentar),
                "title":      parl.nom_parlamentar,
                "description":parl.nom_completo,
                "cargo":      cargo.des_cargo,
            }

            # imagem
            foto_key = f"{comp.cod_parlamentar}_foto_parlamentar"
            url_foto = f"{fotos_url}/{foto_key}"
            if hasattr(self.context.sapl_documentos.parlamentar.fotos, foto_key):
                membro["url_foto"] = url_foto
                try:
                    resp = requests.get(url_foto, timeout=5)
                    img  = Image.open(BytesIO(resp.content))
                    membro["image"] = [{
                        "content-type": f"image/{img.format.lower()}",
                        "download":     url_foto,
                        "filename":     foto_key,
                        "width":        str(img.width),
                        "height":       str(img.height),
                        "size":         str(len(resp.content)),
                    }]
                except (UnidentifiedImageError, requests.RequestException):
                    membro["image"] = []
            else:
                membro["url_foto"] = f"{self.portal_url}/imagens/avatar.png"
                membro["image"]     = []

            # partido(s) ativos
            partidos = []
            filiacoes = self.context.zsql.filiacao_obter_zsql(
                ind_excluido=0, cod_parlamentar=comp.cod_parlamentar
            )
            for fil in filiacoes:
                if not fil.dat_desfiliacao:
                    part = self.context.zsql.partido_obter_zsql(
                        ind_excluido=0, cod_partido=fil.cod_partido
                    )[0]
                    partidos.append({
                        "token": part.sgl_partido,
                        "title": part.nom_partido,
                    })
            membro["partido"] = partidos

            membros.append(membro)

        return membros

    def render(self, cod_periodo_comp=''):
        self.portal     = self.context.portal_url.getPortalObject()
        self.portal_url = self.portal.portal_url()
        # dispatcher
        if self.item_id:
            data = self.get_one(self.item_id)
        elif cod_periodo_comp:
            data = self.get_one(cod_periodo_comp)
        else:
            data = self.lista()

        serialized = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
        return serialized
