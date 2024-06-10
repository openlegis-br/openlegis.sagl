# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from io import BytesIO
from Acquisition import aq_inner
import requests
from PIL import Image
import json
from DateTime import DateTime
import re


@implementer(IPublishTraverse)
class Legislaturas(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('legislaturas')

    item_id = None

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        ## Apenas se for um id numerico
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    def lista(self):
        portal = self.context.portal_url.getPortalObject()
        portal_url = self.context.portal_url.portal_url()
        service_url = self.portal_url + '/@@legislaturas'
        lst_legislaturas = []
        for item in self.context.zsql.legislatura_obter_zsql(ind_excluido=0):
            dic_legislatura = {
                "@id": self.service_url + '/' + str(item.num_legislatura),
                "@type": 'Legislatura',
                "id": str(item.num_legislatura),
                "title": str(item.num_legislatura) + 'ª Legislatura',
                "description": DateTime(item.dat_inicio_conv, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(item.dat_fim_conv, datefmt='international').strftime("%d/%m/%Y"),
            }
            if (DateTime().strftime("%Y-%m-%d") > DateTime(item.dat_inicio_conv, datefmt='international').strftime("%Y-%m-%d") and DateTime().strftime("%Y-%m-%d") < DateTime(item.dat_fim_conv, datefmt='international').strftime("%Y-%m-%d")):
               dic_legislatura['atual'] = True
            else:
               dic_legislatura['atual'] = False
               
            lst_legislaturas.append(dic_legislatura)

        dic_legislaturas = {
            "description": 'Lista de legislaturas ',
            "items": lst_legislaturas,
        }
        
        return dic_legislaturas

    def _get_vereadores(self, num_legislatura):
        portal = self.context.portal_url.getPortalObject()
        portal_url = self.context.portal_url.portal_url()
        service_url = self.portal_url + '/@@legislaturas'
        lst_vereadores = []
        for mandato in self.context.zsql.mandato_obter_zsql(num_legislatura=num_legislatura, ind_excluido=0):
            parlamentar = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=mandato.cod_parlamentar, ind_excluido=0)[0]
            dic_vereador = {
               "@id":  portal_url + '/@@vereadores/' + parlamentar.cod_parlamentar,
               "@type": 'Vereador',
               "id": parlamentar.cod_parlamentar,
               "title": parlamentar.nom_parlamentar,
               "description": parlamentar.nom_completo,
            }

            dic_vereador['votos'] = ''  
            if mandato.num_votos_recebidos != None:
               dic_vereador['votos'] = mandato.num_votos_recebidos
            
            if mandato.ind_titular == 1:
               dic_vereador['mandato'] = 'Titular'
            else:
               dic_vereador['mandato'] = 'Suplente'

            dic_vereador['cod_autor'] = ''
            for autor in self.context.zsql.autor_obter_zsql(cod_parlamentar=parlamentar.cod_parlamentar):
                dic_vereador['cod_autor'] = autor.cod_autor

            lst_imagem = []
            foto = str(mandato.cod_parlamentar) + "_foto_parlamentar"
            if hasattr(self.context.sapl_documentos.parlamentar.fotos, foto):
               url = portal_url + '/sapl_documentos/parlamentar/fotos/' + foto
               response = requests.get(url)
               img = Image.open(BytesIO(response.content))
               dic_image = {
                 "content-type": 'image/' + str(img.format).lower(),
                 "download": url,
                 "filename": foto,
                 "width": str(img.width),
                 "height": str(img.height),
                 "size": str(len(img.fp.read()))
               }
               lst_imagem.append(dic_image)
            dic_vereador['image'] = lst_imagem 
                    
            lst_partido = []
            for filiacao in self.context.zsql.parlamentar_data_filiacao_obter_zsql(num_legislatura=num_legislatura, cod_parlamentar=mandato.cod_parlamentar):    
                if filiacao.dat_filiacao != '0' and filiacao.dat_filiacao != None:
                   for partido in self.context.zsql.parlamentar_partido_obter_zsql(dat_filiacao=filiacao.dat_filiacao, cod_parlamentar=mandato.cod_parlamentar):
                      dic_partido = {
                         "token": partido.sgl_partido,
                         "title": partido.nom_partido
                      }
                   lst_partido.append(dic_partido)
            dic_vereador['partido'] = lst_partido
            lst_vereadores.append(dic_vereador)            
            lst_vereadores.sort(key=lambda dic_vereador: dic_vereador['description'])
        return lst_vereadores

    def get_one(self, item_id):
        item_id = int(item_id)
        results = [item for item in self.context.zsql.legislatura_obter_zsql(num_legislatura=item_id, ind_excluido=0)]
        if not results:
            return {}
        item = results[0]
        num_legislatura = str(item.num_legislatura)
        dic_legislatura = {
            "@id": self.service_url + '/' + num_legislatura,
            "@type": 'Legislatura',
            "id": num_legislatura,
            "title": str(item.num_legislatura) + 'ª Legislatura' ,
            "description": DateTime(item.dat_inicio_conv, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(item.dat_fim_conv, datefmt='international').strftime("%d/%m/%Y"),
            "start": DateTime(item.dat_inicio_conv, datefmt='international').strftime("%Y-%m-%d"),
            "end": DateTime(item.dat_fim_conv, datefmt='international').strftime("%Y-%m-%d"),
            "data_eleicao": DateTime(item.dat_eleicao_conv, datefmt='international').strftime("%Y-%m-%d")
        }
        # Vereadores
        dic_legislatura['items'] = self._get_vereadores(item.num_legislatura)

        return dic_legislatura

    def render(self, num_legislatura=''):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url.portal_url()
        self.service_url = self.portal_url + '/@@legislaturas'
        self.hoje = DateTime()
        data = {
           '@id':  self.service_url,
           '@type':  'Legislaturas',
           'description':  'Lista de legislaturas',
        }
        if self.item_id:
            data.update(self.get_one(self.item_id))
        elif num_legislatura != '':
            data.update(self.lista(num_legislatura))
        else:
            data.update(self.lista())
            
        serialized = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode('utf8')
        return (serialized.decode())

