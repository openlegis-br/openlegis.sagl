# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import name
from grokcore.security import require
from grokcore.view import View as GrokView
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface

import json
import re
import unicodedata
from io import BytesIO
import requests
from PIL import Image, UnidentifiedImageError
from DateTime import DateTime
from xml.sax.saxutils import escape


def _normalize_for_sort(text):
    """Remove acentos/sinais e faz casefold para ordenação estável."""
    if not text:
        return ''
    # NFKD: separa acentos em marcas combinantes; filtra categoria 'Mn'
    norm = unicodedata.normalize('NFKD', str(text))
    no_marks = ''.join(ch for ch in norm if unicodedata.category(ch) != 'Mn')
    # remove quaisquer caracteres de pontuação extra (opcional)
    return no_marks.casefold().strip()


@implementer(IPublishTraverse)
class Vereador(GrokView):
    """API de vereadores: lista (em exercício hoje) e detalhe por id."""

    # registro automático
    context(Interface)
    name('vereadores')
    require('zope2.View')

    item_id = None

    # ------------- Traversal -------------
    def publishTraverse(self, request, name):
        # trata /@@vereadores/<id>
        request["TraversalRequestNameStack"] = []
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    # ------------- Utils / setup -------------
    def _portal_url(self):
        try:
            return self.context.portal_url().rstrip('/')
        except Exception:
            portal = self.context.portal_url.getPortalObject()
            return portal.absolute_url().rstrip('/')

    def _json(self, data):
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)

    def update(self):
        """Inicializa URLs base."""
        self.portal_url = self._portal_url()
        self.service_url = f"{self.portal_url}/@@vereadores"

    # ------------- Blocos de dados -------------
    def _get_legislatura(self):
        res = list(self.context.zsql.legislatura_atual_obter_zsql())
        return res[0].num_legislatura if res else None

    def _get_imagem(self, cod_parlamentar):
        """Metadados da foto se o arquivo existir e for imagem válida."""
        foto_id = f"{cod_parlamentar}_foto_parlamentar"
        try:
            fotos_container = self.context.sapl_documentos.parlamentar.fotos
        except Exception:
            fotos_container = None

        if not (fotos_container and hasattr(fotos_container, foto_id)):
            return []

        url = f"{self.portal_url}/sapl_documentos/parlamentar/fotos/{foto_id}"
        try:
            resp = requests.get(url, timeout=5)
            img = Image.open(BytesIO(resp.content))
            return [{
                "content-type": f"image/{(img.format or '').lower()}",
                "download": url,
                "filename": foto_id,
                "width": str(getattr(img, 'width', '')),
                "height": str(getattr(img, 'height', '')),
                "size": str(len(resp.content)),
            }]
        except (UnidentifiedImageError, requests.RequestException):
            return []

    def lista(self):
        """Lista de vereadores em exercício no dia corrente (via autores_obter_zsql)."""
        self.update()
        hoje_str = DateTime().strftime("%d/%m/%Y")
        vereadores = []

        for item in self.context.zsql.autores_obter_zsql(txt_dat_apresentacao=hoje_str):
            cod_parl = item.cod_parlamentar
            v = {
                "@type": "Vereador",
                "@id": f"{self.service_url}/{cod_parl}",
                "id": cod_parl,
                "title": item.nom_parlamentar,
                "description": item.nom_completo,
                "dic_vereador": item.cod_autor or "",
                "image": self._get_imagem(cod_parl),
            }
            # URL da foto ou avatar padrão
            foto_id = f"{cod_parl}_foto_parlamentar"
            try:
                fotos_container = self.context.sapl_documentos.parlamentar.fotos
            except Exception:
                fotos_container = None
            if fotos_container and hasattr(fotos_container, foto_id):
                v["url_foto"] = f"{self.portal_url}/sapl_documentos/parlamentar/fotos/{foto_id}"
            else:
                v["url_foto"] = f"{self.portal_url}/imagens/avatar.png"

            # partidos atuais (pelos registros da legislatura vigente)
            lst_partido = []
            num_leg = self._get_legislatura()
            if num_leg:
                for fil in self.context.zsql.parlamentar_data_filiacao_obter_zsql(
                    num_legislatura=num_leg, cod_parlamentar=cod_parl
                ):
                    if getattr(fil, 'dat_filiacao', None) and fil.dat_filiacao != '0':
                        for pt in self.context.zsql.parlamentar_partido_obter_zsql(
                            dat_filiacao=fil.dat_filiacao, cod_parlamentar=cod_parl
                        ):
                            lst_partido.append({
                                "token": pt.sgl_partido,
                                "title": pt.nom_partido
                            })
            v["partido"] = lst_partido
            vereadores.append(v)

        # ordena por nome completo (description) ignorando acentos
        vereadores.sort(key=lambda x: _normalize_for_sort(x.get("description", "")))
        return {
            "@id": self.service_url,
            "@type": "Vereadores",
            "description": "Lista de Vereadores em exercício",
            "items": vereadores,
        }

    def _get_filiacoes(self, cod_parlamentar):
        lst = []
        for fil in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=cod_parlamentar):
            entry = {
                "data_filiacao": DateTime(fil.dat_filiacao, datefmt='international').strftime("%Y-%m-%d")
                                 if getattr(fil, 'dat_filiacao', None) else "",
                "data_desfiliacao": (
                    DateTime(fil.dat_desfiliacao, datefmt='international').strftime("%Y-%m-%d")
                    if getattr(fil, 'dat_desfiliacao', None) else ""
                ),
                "filiacao_atual": getattr(fil, 'dat_desfiliacao', None) is None
            }
            pts = list(self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=fil.cod_partido))
            if pts:
                entry["token"] = pts[0].sgl_partido
                entry["title"] = pts[0].nom_partido
            lst.append(entry)
        return lst

    def _get_mandatos(self, cod_parlamentar):
        lst = []
        for m in self.context.zsql.mandato_obter_zsql(cod_parlamentar=cod_parlamentar, ind_excluido=0):
            dic = {
                "@id": f"{self.portal_url}/@@legislaturas/{m.num_legislatura}",
                "@type": "Mandato",
                "id": m.num_legislatura,
                "votos": getattr(m, 'num_votos_recebidos', '') or '',
                "start": DateTime(m.dat_inicio_mandato, datefmt='international').strftime("%Y-%m-%d")
                         if getattr(m, 'dat_inicio_mandato', None) else "",
                "end": DateTime(m.dat_fim_mandato, datefmt='international').strftime("%Y-%m-%d")
                       if getattr(m, 'dat_fim_mandato', None) else "",
                "natureza": "Titular" if getattr(m, 'ind_titular', 0) == 1 else "Suplente",
            }
            lst.append(dic)
        # mais recentes primeiro
        lst.sort(key=lambda x: x.get("start", ""), reverse=True)
        return lst

    def _get_mesas(self, cod_parlamentar):
        lst = []
        for comp in self.context.zsql.parlamentar_mesa_obter_zsql(cod_parlamentar=cod_parlamentar, ind_excluido=0):
            ini = DateTime(comp.sl_dat_inicio, datefmt='international') if getattr(comp, 'sl_dat_inicio', None) else None
            fim = DateTime(comp.sl_dat_fim, datefmt='international') if getattr(comp, 'sl_dat_fim', None) else None
            dic = {
                "@id": f"{self.portal_url}/@@mesas/{comp.cod_periodo_comp}",
                "@type": "ParticipanteMesa",
                "id": str(comp.cod_periodo_comp),
                "title": getattr(comp, 'des_cargo', ''),
                "description": f"{ini.strftime('%d/%m/%Y') if ini else ''} a {fim.strftime('%d/%m/%Y') if fim else ''}",
                "start": ini.strftime("%Y-%m-%d") if ini else "",
                "end": fim.strftime("%Y-%m-%d") if fim else "",
            }
            lst.append(dic)
        lst.sort(key=lambda x: x.get("start", ""), reverse=True)
        return lst

    def _get_comissoes(self, cod_parlamentar):
        lst = []
        for comp in self.context.zsql.composicao_comissao_obter_zsql(cod_parlamentar=cod_parlamentar, ind_excluido=0):
            # período da composição
            periods = list(self.context.zsql.periodo_comp_comissao_obter_zsql(
                cod_periodo_comp=comp.cod_periodo_comp, ind_excluido=0
            ))
            periodo = periods[0] if periods else None
            # datas
            start_dt = DateTime(comp.dat_designacao, datefmt='international') if getattr(comp, 'dat_designacao', None) else None
            end_dt = (DateTime(comp.dat_desligamento, datefmt='international')
                      if getattr(comp, 'dat_desligamento', None)
                      else (DateTime(periodo.dat_fim_periodo, datefmt='international') if periodo else None))
            dic = {
                "@id": f"{self.portal_url}/@@comissoes/{comp.cod_comissao}",
                "@type": "ParticipanteComissao",
                "id": str(comp.cod_comissao),
                "title": getattr(comp, 'des_cargo', ''),
                "comissao": getattr(comp, 'nom_comissao', ''),
                "start": start_dt.strftime("%Y-%m-%d") if start_dt else "",
                "end": end_dt.strftime("%Y-%m-%d") if end_dt else "",
                "description": f"{start_dt.strftime('%d/%m/%Y') if start_dt else ''} a {end_dt.strftime('%d/%m/%Y') if end_dt else ''}",
                "mandato": "Titular" if getattr(comp, 'ind_titular', 0) == 1 else "Suplente",
           }
            lst.append(dic)
        lst.sort(key=lambda x: x.get("start", ""), reverse=True)
        return lst

    def get_one(self, item_id):
        self.update()
        try:
            pid = int(item_id)
        except (TypeError, ValueError):
            return {}

        res = list(self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=pid, ind_excluido=0))
        if not res:
            return {}
        item = res[0]

        birthday = ""
        if getattr(item, 'dat_nascimento', None):
            try:
                birthday = DateTime(item.dat_nascimento, datefmt='international').strftime("%Y-%m-%d")
            except Exception:
                birthday = ""

        foto_attr = f"{pid}_foto_parlamentar"
        try:
            fotos_container = self.context.sapl_documentos.parlamentar.fotos
        except Exception:
            fotos_container = None
        url_foto = (f"{self.portal_url}/sapl_documentos/parlamentar/fotos/{foto_attr}"
                    if (fotos_container and hasattr(fotos_container, foto_attr))
                    else f"{self.portal_url}/imagens/avatar.png")

        dic = {
            "@type": "Vereador",
            "@id": f"{self.service_url}/{pid}",
            "id": str(pid),
            "title": getattr(item, 'nom_parlamentar', ''),
            "description": getattr(item, 'nom_completo', ''),
            "email": getattr(item, 'end_email', '') or "",
            "telefone_gabinete": getattr(item, 'num_tel_parlamentar', '') or "",
            "cod_autor": "",
            "birthday": birthday,
            "biografia": escape(getattr(item, 'txt_biografia', '') or ""),
            "url_foto": url_foto,
            "image": self._get_imagem(pid),
            "filiacoes": self._get_filiacoes(pid),
            "mandatos": self._get_mandatos(pid),
            "mesas": self._get_mesas(pid),
            "comissoes": self._get_comissoes(pid),
        }

        # cod_autor (se existir)
        autores = list(self.context.zsql.autor_obter_zsql(cod_parlamentar=pid))
        if autores:
            dic["cod_autor"] = autores[0].cod_autor

        return dic

    # ------------- Render -------------
    def render(self):
        self.update()
        data = self.get_one(self.item_id) if self.item_id else self.lista()
        return self._json(data)
