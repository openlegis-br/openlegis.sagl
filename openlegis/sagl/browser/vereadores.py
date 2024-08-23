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
from xml.sax.saxutils import escape
import re


@implementer(IPublishTraverse)
class Vereador(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('vereadores')

    item_id = None

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        ## Apenas se for um id numerico
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    def _get_legislatura(self):
        for item in self.context.zsql.legislatura_atual_obter_zsql():
            num_legislatura = item.num_legislatura
            return num_legislatura

    def _get_imagem(self, cod_parlamentar):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url()
        lst_imagem = []
        foto = str(cod_parlamentar) + "_foto_parlamentar"
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
                "size": str(len(img.fp.read())),
              }
           except PIL.UnidentifiedImageError:
              dic_image = {}
           lst_imagem.append(dic_image)
        return lst_imagem

    def lista(self):
        data_atual = DateTime().strftime("%d/%m/%Y")
        lst_vereadores = []
        for item in self.context.zsql.autores_obter_zsql(txt_dat_apresentacao=data_atual):
            dic_item = {
	      "@type": 'Vereador',
              "@id": self.service_url + '/' + str(item.cod_parlamentar),
	      "id": item.cod_parlamentar,
	      "title": item.nom_parlamentar,
	      "description": item.nom_completo,
	      "dic_vereador": item.cod_autor,
	    }
            dic_item['image'] = self._get_imagem(item.cod_parlamentar)   
            lst_partido = []
            for filiacao in self.context.zsql.parlamentar_data_filiacao_obter_zsql(num_legislatura=self._get_legislatura(), cod_parlamentar=item.cod_parlamentar):    
                if filiacao.dat_filiacao != '0' and filiacao.dat_filiacao != None:
                   for partido in self.context.zsql.parlamentar_partido_obter_zsql(dat_filiacao=filiacao.dat_filiacao, cod_parlamentar=item.cod_parlamentar):
                      dic_partido = {
                         "token": partido.sgl_partido,
                         "title": partido.nom_partido
                      }
                   lst_partido.append(dic_partido)
            dic_item['partido'] = lst_partido
            lst_vereadores.append(dic_item)
        lst_vereadores.sort(key=lambda dic_item: dic_item['description'])
	
        dic_vereador = {
            "@id": self.service_url,
            "@type":  'Vereadores',
            "description": 'Lista de Vereadores em exercício',
            "items": lst_vereadores,
        }

        return dic_vereador

    def _get_filiacoes(self, cod_parlamentar):
        lst_partido = []
        for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=cod_parlamentar):    
            dic_partido = {
               "data_filiacao": DateTime(filiacao.dat_filiacao, datefmt='international').strftime("%Y-%m-%d"),
            }
            if filiacao.dat_desfiliacao != None:
               dic_partido['data_desfiliacao'] = DateTime(filiacao.dat_desfiliacao, datefmt='international').strftime("%Y-%m-%d")
               dic_partido['filiacao_atual'] = False
            else:
               dic_partido['data_desfiliacao'] = ''
               dic_partido['filiacao_atual'] = True
            for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
                dic_partido['token'] = partido.sgl_partido
                dic_partido['title'] = partido.nom_partido            
            lst_partido.append(dic_partido)
        return lst_partido   
    
    def _get_mandatos(self, cod_parlamentar):
        lst_mandato = []
        for mandato in self.context.zsql.mandato_obter_zsql(cod_parlamentar=cod_parlamentar, ind_excluido=0):
            dic_mandato = {
                "@id": self.portal_url + '/@@legislaturas/' + str(mandato.num_legislatura),
                "@type": 'Mandato',
                "votos": mandato.num_votos_recebidos,
                "start": DateTime(mandato.dat_inicio_mandato).strftime("%Y-%m-%d"),
                "end": DateTime(mandato.dat_fim_mandato, datefmt='international').strftime("%Y-%m-%d"),
                "id": mandato.num_legislatura,
            }
            if mandato.ind_titular == 1:
               dic_mandato['natureza'] = 'Titular'
            else:
               dic_mandato['natureza'] = 'Suplente'
            lst_mandato.append(dic_mandato)
        return lst_mandato

    def _get_mesas(self, cod_parlamentar):
        lst_mesa = []
        for composicao in self.context.zsql.parlamentar_mesa_obter_zsql(cod_parlamentar=cod_parlamentar, ind_excluido=0):
           dic_mesa = {
              "@id": self.portal_url + '/@@mesas/' + str(composicao.cod_periodo_comp),
              "@type": 'ParticipanteMesa',
              "id": str(composicao.cod_periodo_comp),
              "title": str(composicao.des_cargo),
              "description": DateTime(composicao.sl_dat_inicio, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(composicao.sl_dat_fim, datefmt='international').strftime("%d/%m/%Y"),
              "start": DateTime(composicao.sl_dat_inicio, datefmt='international').strftime("%Y-%m-%d"),
              "end": DateTime(composicao.sl_dat_fim, datefmt='international').strftime("%Y-%m-%d"),
           }
           lst_mesa.append(dic_mesa)
        lst_mesa.sort(key=lambda dic_mesa: dic_mesa['start'], reverse=True)
        return lst_mesa

    def _get_comissoes(self, cod_parlamentar):
        lst_comissao = []
        for composicao in self.context.zsql.composicao_comissao_obter_zsql(cod_parlamentar=cod_parlamentar, ind_excluido=0):
            periodo = self.context.zsql.periodo_comp_comissao_obter_zsql(cod_periodo_comp=composicao.cod_periodo_comp, ind_excluido=0)[0]
            cod_periodo = periodo.dat_fim_periodo
            dic_comissao = {
               "@id": self.portal_url + '/@@comissoes/' + str(composicao.cod_comissao),
               "@type": 'ParticipanteComissao',
               "id": str(composicao.cod_comissao),
               "title": str(composicao.des_cargo),
               "start": DateTime(composicao.dat_designacao, datefmt='international').strftime("%Y-%m-%d"),
               "end": DateTime(composicao.dat_desligamento, datefmt='international').strftime("%Y-%m-%d"),
               "comissao": str(composicao.nom_comissao),
            }
            dat_designacao = DateTime(composicao.dat_designacao, datefmt='international').strftime("%d/%m/%Y")
            dat_desligamento = DateTime(composicao.dat_desligamento, datefmt='international').strftime("%d/%m/%Y")
            dic_comissao['description'] = dat_designacao + ' a ' + dat_desligamento
            if composicao.dat_desligamento == None:
               dat_desligamento = DateTime(periodo.dat_fim_periodo, datefmt='international').strftime("%d/%m/%Y")
               dic_comissao['end'] = DateTime(periodo.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")
            if composicao.ind_titular == 1:
               dic_comissao['mandato'] = 'Titular'
            else:
               dic_comissao['mandato'] = 'Suplente'
            lst_comissao.append(dic_comissao)
        lst_comissao.sort(key=lambda dic_comissao: dic_comissao['start'], reverse=True)
        return lst_comissao

    def get_one(self, item_id):
        item_id = int(item_id)
        results = [item for item in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=item_id)]
        if not results:
            return {}
        item = results[0]
        dic_vereador = {
	   "@type": 'Vereador',
           "@id": self.service_url + '/' + str(item_id),
	   "id": item.cod_parlamentar,
	   "title": item.nom_parlamentar,
	   "description": item.nom_completo,
	   "email": item.end_email,
	   "telefone_gabinete": item.num_tel_parlamentar,      
        }
        dic_vereador['cod_autor'] = ''
        for autor in self.context.zsql.autor_obter_zsql(cod_parlamentar=item.cod_parlamentar):
           dic_vereador['cod_autor'] = autor.cod_autor
        if item.dat_nascimento != None:
           dic_vereador['birthday'] = DateTime(item.dat_nascimento, datefmt='international').strftime("%Y-%m-%d")
        else:
           dic_vereador['birthday'] = '' 
        if item.txt_biografia != None:
           dic_vereador['biografia'] = escape(item.txt_biografia)
        else:
           dic_vereador['biografia'] = '' 
        #for item in results: 
        #   lst_vereadores.append(dic_vereador)         

        # Dados gerais
        dic_vereador['image'] = self._get_imagem(item.cod_parlamentar)   
        dic_vereador['filiacoes'] = self._get_filiacoes(item.cod_parlamentar)   
        dic_vereador['mandatos'] = self._get_mandatos(item.cod_parlamentar)   
        dic_vereador['mesas'] = self._get_mesas(item.cod_parlamentar)   
        dic_vereador['comissoes'] = self._get_comissoes(item.cod_parlamentar)   

        return dic_vereador

    def render(self):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url.portal_url()
        self.service_url = self.portal_url + '/@@vereadores'
        self.hoje = DateTime()
        data = {
        }
        if self.item_id:
            data.update(self.get_one(self.item_id))
        else:
            data.update(self.lista())
            
        serialized = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode('utf8')
        return (serialized.decode())


