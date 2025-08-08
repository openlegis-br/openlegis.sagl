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
class Legislaturas(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('legislaturas')

    item_id = None
    http = requests.Session()

    def publishTraverse(self, request, name):
        request['TraversalRequestNameStack'] = []
        if name.isdigit():
            self.item_id = int(name)
        return self

    def _build_service_url(self):
        portal = self.context.portal_url.getPortalObject()
        return f"{portal.absolute_url()}/@@legislaturas"

    def render(self, num_legislatura=''):
        self.service_url = self._build_service_url()
        self.today = DateTime()

        data = {
            '@id': self.service_url,
            '@type': 'Legislaturas',
            'description': 'Lista de legislaturas',
        }

        if self.item_id is not None:
            data.update(self.get_one(self.item_id))
        elif num_legislatura:
            data.update(self.get_one(int(num_legislatura)))
        else:
            data.update(self.lista())

        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)

    def lista(self):
        portal = self.context.portal_url.getPortalObject()
        portal_url = portal.absolute_url()
        service_url = self._build_service_url()
        items = []

        for item in self.context.zsql.legislatura_obter_zsql(ind_excluido=0):
            start = DateTime(item.dat_inicio_conv, datefmt='international')
            end = DateTime(item.dat_fim_conv, datefmt='international')
            atual = start <= self.today <= end

            items.append({
                '@id': f"{service_url}/{item.num_legislatura}",
                '@type': 'Legislatura',
                'id': str(item.num_legislatura),
                'title': f"{item.num_legislatura}ª Legislatura",
                'description': f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
                'atual': bool(atual),
            })

        return {'description': 'Lista de legislaturas', 'items': items}

    def get_one(self, num_legislatura):
        portal = self.context.portal_url.getPortalObject()
        portal_url = portal.absolute_url()
        service_url = self._build_service_url()

        res = list(self.context.zsql.legislatura_obter_zsql(num_legislatura=num_legislatura, ind_excluido=0))
        if not res:
            return {}

        item = res[0]
        start = DateTime(item.dat_inicio_conv, datefmt='international')
        end = DateTime(item.dat_fim_conv, datefmt='international')

        return {
            '@id': f"{service_url}/{num_legislatura}",
            '@type': 'Legislatura',
            'id': str(num_legislatura),
            'title': f"{num_legislatura}ª Legislatura",
            'description': f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
            'start': start.strftime('%Y-%m-%d'),
            'end': end.strftime('%Y-%m-%d'),
            'data_eleicao': DateTime(item.dat_eleicao_conv, datefmt='international').strftime('%Y-%m-%d'),
            'items': self._get_vereadores(num_legislatura)
        }

    def _get_vereadores(self, num_legislatura):
        portal = self.context.portal_url.getPortalObject()
        portal_url = portal.absolute_url()
        service_url = self._build_service_url()
        vereadores = []

        for mandato in self.context.zsql.mandato_obter_zsql(num_legislatura=num_legislatura, ind_excluido=0):
            par = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=mandato.cod_parlamentar, ind_excluido=0)[0]
            foto_field = f"{mandato.cod_parlamentar}_foto_parlamentar"
            if hasattr(self.context.sapl_documentos.parlamentar.fotos, foto_field):
                url_foto = f"{portal_url}/sapl_documentos/parlamentar/fotos/{foto_field}"
                try:
                    content = self.http.get(url_foto).content
                    img = Image.open(BytesIO(content))
                    image_info = [{
                        'content-type': f"image/{img.format.lower()}",
                        'download': url_foto,
                        'filename': foto_field,
                        'width': img.width,
                        'height': img.height,
                        'size': len(content)
                    }]
                except UnidentifiedImageError:
                    image_info = []
            else:
                url_foto = f"{portal_url}/imagens/avatar.png"
                image_info = []

            partidos = []
            for fil in self.context.zsql.parlamentar_data_filiacao_obter_zsql(num_legislatura=num_legislatura, cod_parlamentar=mandato.cod_parlamentar):
                if fil.dat_filiacao:
                    for pt in self.context.zsql.parlamentar_partido_obter_zsql(dat_filiacao=fil.dat_filiacao, cod_parlamentar=mandato.cod_parlamentar):
                        partidos.append({'token': pt.sgl_partido, 'title': pt.nom_partido})

            vereadores.append({
                '@id': f"{portal_url}/@@vereadores/{par.cod_parlamentar}",
                '@type': 'Vereador',
                'id': par.cod_parlamentar,
                'title': par.nom_parlamentar,
                'description': par.nom_completo,
                'votos': mandato.num_votos_recebidos or 0,
                'mandato': 'Titular' if mandato.ind_titular else 'Suplente',
                'cod_autor': (self.context.zsql.autor_obter_zsql(cod_parlamentar=par.cod_parlamentar) or [{}])[0].get('cod_autor', ''),
                'url_foto': url_foto,
                'image': image_info,
                'partido': partidos
            })

        return sorted(vereadores, key=lambda x: x['description'])
