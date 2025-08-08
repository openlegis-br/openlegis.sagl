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
from xml.sax.saxutils import escape
import re

@implementer(IPublishTraverse)
class Vereador(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('vereadores')

    item_id = None

    def publishTraverse(self, request, name):
        # reseta pilha de traversal para tratar como subview
        request["TraversalRequestNameStack"] = []
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    def update(self):
        """Inicializa portal e URLs antes de qualquer render/lista/get_one."""
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.portal.absolute_url()
        self.service_url = f"{self.portal_url}/@@vereadores"

    def _get_legislatura(self):
        for item in self.context.zsql.legislatura_atual_obter_zsql():
            return item.num_legislatura
        return None

    def _get_imagem(self, cod_parlamentar):
        foto_id = f"{cod_parlamentar}_foto_parlamentar"
        fotos = getattr(self.context.sapl_documentos.parlamentar.fotos, foto_id, None)
        if not fotos:
            return []

        url = f"{self.portal_url}/sapl_documentos/parlamentar/fotos/{foto_id}"
        try:
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content))
            size = len(response.content)
            return [{
                "content-type": f"image/{img.format.lower()}",
                "download": url,
                "filename": foto_id,
                "width": str(img.width),
                "height": str(img.height),
                "size": str(size),
            }]
        except (UnidentifiedImageError, requests.RequestException):
            return []

    def lista(self):
        self.update()
        hoje_str = DateTime().strftime("%d/%m/%Y")
        vereadores = []

        for item in self.context.zsql.autores_obter_zsql(txt_dat_apresentacao=hoje_str):
            v = {
                "@type": "Vereador",
                "@id": f"{self.service_url}/{item.cod_parlamentar}",
                "id": item.cod_parlamentar,
                "title": item.nom_parlamentar,
                "description": item.nom_completo,
                "dic_vereador": item.cod_autor or "",
                "image": self._get_imagem(item.cod_parlamentar),
            }
            # URL da foto ou avatar padrão
            foto_id = f"{item.cod_parlamentar}_foto_parlamentar"
            if hasattr(self.context.sapl_documentos.parlamentar.fotos, foto_id):
                v["url_foto"] = f"{self.portal_url}/sapl_documentos/parlamentar/fotos/{foto_id}"
            else:
                v["url_foto"] = f"{self.portal_url}/imagens/avatar.png"

            # partidos atuais
            lst_partido = []
            num_leg = self._get_legislatura()
            if num_leg:
                for fil in self.context.zsql.parlamentar_data_filiacao_obter_zsql(
                        num_legislatura=num_leg,
                        cod_parlamentar=item.cod_parlamentar
                ):
                    if fil.dat_filiacao and fil.dat_filiacao != '0':
                        for pt in self.context.zsql.parlamentar_partido_obter_zsql(
                                dat_filiacao=fil.dat_filiacao,
                                cod_parlamentar=item.cod_parlamentar
                        ):
                            lst_partido.append({
                                "token": pt.sgl_partido,
                                "title": pt.nom_partido
                            })
            v["partido"] = lst_partido
            vereadores.append(v)

        vereadores.sort(key=lambda x: x["description"])
        return {
            "@id": self.service_url,
            "@type": "Vereadores",
            "description": "Lista de Vereadores em exercício",
            "items": vereadores,
        }

    def _get_filiacoes(self, cod_parlamentar):
        lst = []
        for fil in self.context.zsql.filiacao_obter_zsql(
                ind_excluido=0, cod_parlamentar=cod_parlamentar
        ):
            entry = {
                "data_filiacao": DateTime(fil.dat_filiacao, datefmt='international').strftime("%Y-%m-%d"),
                "data_desfiliacao": (
                    DateTime(fil.dat_desfiliacao, datefmt='international').strftime("%Y-%m-%d")
                    if fil.dat_desfiliacao else ""
                ),
                "filiacao_atual": fil.dat_desfiliacao is None
            }
            for pt in self.context.zsql.partido_obter_zsql(
                    ind_excluido=0, cod_partido=fil.cod_partido
            ):
                entry["token"] = pt.sgl_partido
                entry["title"] = pt.nom_partido
            lst.append(entry)
        return lst

    def _get_mandatos(self, cod_parlamentar):
        lst = []
        for m in self.context.zsql.mandato_obter_zsql(cod_parlamentar=cod_parlamentar, ind_excluido=0):
            dic = {
                "@id": f"{self.portal_url}/@@legislaturas/{m.num_legislatura}",
                "@type": "Mandato",
                "id": m.num_legislatura,
                "votos": m.num_votos_recebidos,
                "start": DateTime(m.dat_inicio_mandato).strftime("%Y-%m-%d"),
                "end": DateTime(m.dat_fim_mandato, datefmt='international').strftime("%Y-%m-%d"),
                "natureza": "Titular" if m.ind_titular == 1 else "Suplente",
            }
            lst.append(dic)
        return lst

    def _get_mesas(self, cod_parlamentar):
        lst = []
        for comp in self.context.zsql.parlamentar_mesa_obter_zsql(
                cod_parlamentar=cod_parlamentar, ind_excluido=0
        ):
            dic = {
                "@id": f"{self.portal_url}/@@mesas/{comp.cod_periodo_comp}",
                "@type": "ParticipanteMesa",
                "id": str(comp.cod_periodo_comp),
                "title": comp.des_cargo,
                "description": f"{DateTime(comp.sl_dat_inicio).strftime('%d/%m/%Y')} a {DateTime(comp.sl_dat_fim).strftime('%d/%m/%Y')}",
                "start": DateTime(comp.sl_dat_inicio).strftime("%Y-%m-%d"),
                "end": DateTime(comp.sl_dat_fim).strftime("%Y-%m-%d"),
            }
            lst.append(dic)
        lst.sort(key=lambda x: x["start"], reverse=True)
        return lst

    def _get_comissoes(self, cod_parlamentar):
        lst = []
        for comp in self.context.zsql.composicao_comissao_obter_zsql(
                cod_parlamentar=cod_parlamentar, ind_excluido=0
        ):
            periodo = self.context.zsql.periodo_comp_comissao_obter_zsql(
                cod_periodo_comp=comp.cod_periodo_comp, ind_excluido=0
            )[0]
            start_dt = DateTime(comp.dat_designacao)
            end_dt = DateTime(comp.dat_desligamento) if comp.dat_desligamento else DateTime(periodo.dat_fim_periodo)
            dic = {
                "@id": f"{self.portal_url}/@@comissoes/{comp.cod_comissao}",
                "@type": "ParticipanteComissao",
                "id": str(comp.cod_comissao),
                "title": comp.des_cargo,
                "comissao": comp.nom_comissao,
                "start": start_dt.strftime("%Y-%m-%d"),
                "end": end_dt.strftime("%Y-%m-%d"),
                "description": f"{start_dt.strftime('%d/%m/%Y')} a {end_dt.strftime('%d/%m/%Y')}",
                "mandato": "Titular" if comp.ind_titular == 1 else "Suplente",
           }
            lst.append(dic)
        lst.sort(key=lambda x: x["start"], reverse=True)
        return lst

    def get_one(self, item_id):
        self.update()
        pid = int(item_id)
        results = list(self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=pid))
        if not results:
            return {}
        item = results[0]
        dic = {
            "@type": "Vereador",
            "@id": f"{self.service_url}/{pid}",
            "id": pid,
            "title": item.nom_parlamentar,
            "description": item.nom_completo,
            "email": item.end_email or "",
            "telefone_gabinete": item.num_tel_parlamentar or "",
            "cod_autor": "",
            "birthday": DateTime(item.dat_nascimento).strftime("%Y-%m-%d") if item.dat_nascimento else "",
            "biografia": escape(item.txt_biografia) if item.txt_biografia else "",
            "url_foto": (
                f"{self.portal_url}/sapl_documentos/parlamentar/fotos/{pid}_foto_parlamentar"
                if hasattr(self.context.sapl_documentos.parlamentar.fotos, f"{pid}_foto_parlamentar")
                else f"{self.portal_url}/imagens/avatar.png"
            ),
            "image": self._get_imagem(pid),
            "filiacoes": self._get_filiacoes(pid),
            "mandatos": self._get_mandatos(pid),
            "mesas": self._get_mesas(pid),
            "comissoes": self._get_comissoes(pid),
        }
        # pega cod_autor real
        autor = list(self.context.zsql.autor_obter_zsql(cod_parlamentar=pid))
        if autor:
            dic["cod_autor"] = autor[0].cod_autor
        return dic

    def render(self):
        # serializa JSON
        if self.item_id:
            data = self.get_one(self.item_id)
        else:
            data = self.lista()
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
