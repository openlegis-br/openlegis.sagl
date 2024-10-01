# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from io import BytesIO
from Acquisition import aq_inner
import requests
from PIL import Image, UnidentifiedImageError
import json
from DateTime import DateTime
from xml.sax.saxutils import escape
import re

@implementer(IPublishTraverse)
class Mesas(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('mesas')

    item_id = None

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        ## Apenas se for um id numerico
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    def lista(self):
        data_atual = DateTime().strftime("%Y-%m-%d")
        lista = []
        for item in self.context.zsql.periodo_comp_mesa_obter_zsql(ind_excluido=0):
            dic = {
                "@id": self.service_url + '/' + str(item.cod_periodo_comp),
               "@type": 'Mesa',
                "id": str(item.cod_periodo_comp),
                "start": DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d"),
                "end": DateTime(item.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d"),
                "description": 'Período de composição na ' +  str(item.num_legislatura) + 'ª Legislatura',
                "legislatura": str(item.num_legislatura) + 'ª Legislatura',
                "legislatura_id": self.portal_url + '/@@legislaturas/' + str(item.num_legislatura),
                "title": DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(item.dat_fim_periodo, datefmt='international').strftime("%d/%m/%Y"),
            }
            if (DateTime().strftime("%Y-%m-%d") > DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d") and DateTime().strftime("%Y-%m-%d") < DateTime(item.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")):
               dic['atual'] = True
            else:
               dic['atual'] = False
            lista.append(dic)
            
        lista.sort(key=lambda dic: dic['start'], reverse=True)

        dic_mesas = {
            "description": 'Lista de períodos de composição',
            "items": lista,
        }

        return dic_mesas

    def get_one(self, item_id):
        item_id = int(item_id)
        results = [item for item in self.context.zsql.periodo_comp_mesa_obter_zsql(cod_periodo_comp=item_id, ind_excluido=0)]
        if not results:
            return {}
        item = results[0]
        cod_periodo_comp = str(item.cod_periodo_comp)
        dic_mesa = {
            "@id": self.service_url + '/' + cod_periodo_comp,
	    "@type": 'Mesa',
	    "id": str(item.cod_periodo_comp),
	    "start": DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d"),
	    "end": DateTime(item.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d"),
	    "legislatura": str(item.num_legislatura) + 'ª Legislatura',
            "legislatura_id": self.portal_url + '/@@legislaturas/' + str(item.num_legislatura),
	    "description": 'Composição da mesa diretora',
            "title": DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(item.dat_fim_periodo, datefmt='international').strftime("%d/%m/%Y"),
        }
        if (DateTime().strftime("%Y-%m-%d") > DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d") and DateTime().strftime("%Y-%m-%d") < DateTime(item.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")):
           dic_mesa['atual'] = True
        else:
           dic_mesa['atual'] = False     
        
        dic_mesa['items'] = self._get_membros(cod_periodo_comp)
        
        return dic_mesa

    def _get_membros(self, cod_periodo_comp):      
        lst_membros = []
        for composicao in self.context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=cod_periodo_comp, ind_excluido=0):
            cargo = self.context.zsql.cargo_mesa_obter_zsql(cod_cargo=composicao.cod_cargo, ind_excluido=0)[0]
            parlamentar = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=composicao.cod_parlamentar, ind_excluido=0)[0]
            dic_membros = {
               "@id":  self.portal_url + '/@@vereadores/' + str(composicao.cod_parlamentar),
               "@type": 'ParticipanteMesa',
               "id": str(parlamentar.cod_parlamentar),
               "title": parlamentar.nom_parlamentar,
               "description": parlamentar.nom_completo,
               "cargo": cargo.des_cargo,
            }
            lst_imagem = []
            foto = str(composicao.cod_parlamentar) + "_foto_parlamentar"
            if hasattr(self.context.sapl_documentos.parlamentar.fotos, foto):
               url = self.portal_url + '/sapl_documentos/parlamentar/fotos/' + foto
               response = requests.get(url)
               try:
                  img = Image.open(BytesIO(response.content))
                  dic_image = {
                    "content-type": 'image/' + str(img.format).lower(),
                    "download": url,
                    "filename": foto,
                    "width": str(img.width),
                    "height": str(img.height),
                    "size": str(len(img.fp.read()))
                  }
               except UnidentifiedImageError:
                  dic_image = {}
               lst_imagem.append(dic_image)
            dic_membros['image'] = lst_imagem    
            lst_partido = []
            for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=composicao.cod_parlamentar):    
                for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
                    dic_partido = {
                      "token": partido.sgl_partido,
                      "title": partido.nom_partido
                    }
                if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
                   lst_partido.append(dic_partido)
            dic_membros['partido'] = lst_partido
            lst_membros.append(dic_membros)            
        return lst_membros

    def render(self, cod_periodo_comp=''):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url.portal_url()
        self.service_url = self.portal_url + '/@@mesas'
        self.hoje = DateTime()
        data = {
           '@id':  self.service_url,
           '@type':  'Mesas',
           'description':  'Lista de períodos de composição',
        }
        if self.item_id:
            data.update(self.get_one(self.item_id))
        elif cod_periodo_comp != '':
            data.update(self.lista(cod_periodo_comp))
        else:
            data.update(self.lista())
            
        serialized = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode('utf8')
        return (serialized.decode())
