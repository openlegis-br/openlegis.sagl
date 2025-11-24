# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import name
from grokcore.security import require
from grokcore.view import View as GrokView
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface
from DateTime import DateTime
from io import BytesIO
import requests
from PIL import Image, UnidentifiedImageError
import json
import unicodedata
import re

IMAGE_TIMEOUT = 3  # segundos

@implementer(IPublishTraverse)
class Legislaturas(GrokView):
    """API de legislaturas (registro automático via grokcore)."""

    context(Interface)
    name('legislaturas')      # @@legislaturas
    require('zope2.View')

    item_id = None

    def __init__(self, context, request):
        super().__init__(context, request)
        self.http = requests.Session()
        self.service_url = self._build_service_url()
        self.today = DateTime()

    # -------- traversal --------
    def publishTraverse(self, request, name):
        request['TraversalRequestNameStack'] = []
        if name.isdigit():
            self.item_id = int(name)
        return self

    # -------- utils --------
    def _build_service_url(self):
        portal = self.context.portal_url.getPortalObject()
        return f"{portal.absolute_url()}/@@legislaturas"

    def _json(self, data):
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)

    @staticmethod
    def _normalize_nome(nome):
        """Remove acentuação e caracteres especiais para ordenação estável."""
        if not nome:
            return ""
        # Normaliza para NFKD e remove marcas de combinação (acentos)
        nfkd = unicodedata.normalize('NFKD', nome)
        sem_acentos = ''.join(c for c in nfkd if not unicodedata.combining(c))
        # Mantém apenas letras, números e espaço
        so_limpinho = re.sub(r'[^A-Za-z0-9\s]', '', sem_acentos)
        # Normaliza espaços e usa upper para evitar diferença de caixa
        return re.sub(r'\s+', ' ', so_limpinho).strip().upper()

    # -------- render --------
    def render(self, num_legislatura=''):
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
        return self._json(data)

    # -------- endpoints --------
    def lista(self):
        items = []
        for item in self.context.zsql.legislatura_obter_zsql(ind_excluido=0):
            start = DateTime(item.dat_inicio_conv, datefmt='international')
            end = DateTime(item.dat_fim_conv, datefmt='international')
            atual = start <= self.today <= end
            items.append({
                '@id': f"{self.service_url}/{item.num_legislatura}",
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

        res = list(self.context.zsql.legislatura_obter_zsql(
            num_legislatura=num_legislatura, ind_excluido=0
        ))
        if not res:
            return {}

        item = res[0]
        start = DateTime(item.dat_inicio_conv, datefmt='international')
        end = DateTime(item.dat_fim_conv, datefmt='international')

        # dat_eleicao pode ser None
        try:
            data_eleicao = DateTime(item.dat_eleicao_conv, datefmt='international').strftime('%Y-%m-%d')
        except Exception:
            data_eleicao = ""

        return {
            '@id': f"{self.service_url}/{num_legislatura}",
            '@type': 'Legislatura',
            'id': str(num_legislatura),
            'title': f"{num_legislatura}ª Legislatura",
            'description': f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
            'start': start.strftime('%Y-%m-%d'),
            'end': end.strftime('%Y-%m-%d'),
            'data_eleicao': data_eleicao,
            'items': self._get_vereadores(num_legislatura, portal_url),
        }

    # -------- helpers --------
    def _get_vereadores(self, num_legislatura, portal_url):
        vereadores = []
        for mandato in self.context.zsql.mandato_obter_zsql(
            num_legislatura=num_legislatura, ind_excluido=0
        ):
            # parlamentar pode não existir (dados inconsistentes)
            pars = list(self.context.zsql.parlamentar_obter_zsql(
                cod_parlamentar=mandato.cod_parlamentar, ind_excluido=0
            ))
            if not pars:
                continue
            par = pars[0]

            # Foto
            foto_field = f"{mandato.cod_parlamentar}_foto_parlamentar"
            if hasattr(self.context.sapl_documentos.parlamentar.fotos, foto_field):
                url_foto = f"{portal_url}/sapl_documentos/parlamentar/fotos/{foto_field}"
                image_info = self._build_image_info(url_foto, foto_field)
            else:
                url_foto = f"{portal_url}/imagens/avatar.png"
                image_info = []

            # Partidos na legislatura (dedup mantendo ordem) - CORREÇÃO APLICADA
            partidos = []
            vistos = set()
            for fil in self.context.zsql.parlamentar_data_filiacao_obter_zsql(
                num_legislatura=num_legislatura, cod_parlamentar=mandato.cod_parlamentar
            ):
                dat_filiacao = getattr(fil, 'dat_filiacao', None)
                
                # CORREÇÃO: Validar dat_filiacao antes de usar
                if not dat_filiacao or str(dat_filiacao).strip() in ['', '0', '0000-00-00', '0000-00-00 00:00:00']:
                    continue
                    
                # CORREÇÃO: Tratar erro individual para cada chamada ZSQL
                try:
                    for pt in self.context.zsql.parlamentar_partido_obter_zsql(
                        dat_filiacao=dat_filiacao, cod_parlamentar=mandato.cod_parlamentar
                    ):
                        key = (pt.sgl_partido, pt.nom_partido)
                        if key not in vistos:
                            partidos.append({'token': pt.sgl_partido, 'title': pt.nom_partido})
                            vistos.add(key)
                except Exception:
                    # Ignorar erro para esta filiação específica e continuar com as demais
                    continue

            # Autor (pode não existir)
            autores = list(self.context.zsql.autor_obter_zsql(cod_parlamentar=par.cod_parlamentar)) or []
            if autores:
                a0 = autores[0]
                cod_autor = getattr(a0, 'cod_autor', '') if not isinstance(a0, dict) else a0.get('cod_autor', '')
            else:
                cod_autor = ''

            vereadores.append({
                '@id': f"{portal_url}/@@vereadores/{par.cod_parlamentar}",
                '@type': 'Vereador',
                'id': par.cod_parlamentar,
                'title': par.nom_parlamentar,
                'description': par.nom_completo,
                'votos': getattr(mandato, 'num_votos_recebidos', 0) or 0,
                'mandato': 'Titular' if getattr(mandato, 'ind_titular', 0) else 'Suplente',
                'cod_autor': cod_autor,
                'url_foto': url_foto,
                'image': image_info,
                'partido': partidos
            })

        # Ordena por nome completo DESACENTUADO e sem caracteres especiais
        return sorted(
            vereadores,
            key=lambda x: self._normalize_nome(x.get('description') or x.get('title') or '')
        )

    def _build_image_info(self, url_foto, filename):
        try:
            head = self.http.head(url_foto, timeout=IMAGE_TIMEOUT, allow_redirects=True)
            if head.status_code != 200:
                return []
            resp = self.http.get(url_foto, timeout=IMAGE_TIMEOUT)
            content = resp.content
            img = Image.open(BytesIO(content))
            return [{
                'content-type': f"image/{(img.format or '').lower()}",
                'download': url_foto,
                'filename': filename,
                'width': getattr(img, 'width', None),
                'height': getattr(img, 'height', None),
                'size': len(content)
            }]
        except (UnidentifiedImageError, requests.RequestException):
            return []
