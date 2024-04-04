# -*- coding: utf-8 -*-
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from io import BytesIO
import requests
from PIL import Image
import simplejson as json
from DateTime import DateTime

class Legislaturas(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('legislaturas')
        
    def render(self):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%d/%m/%Y")
	lista = []
	for item in self.context.zsql.legislatura_obter_zsql(ind_excluido=0):
            dic = {}
    	    dic['@id'] = portal_url + '/@@legislatura?id=' + str(item.num_legislatura)
	    dic['@type'] = 'Legislatura'
	    dic['id'] = item.num_legislatura
	    dic['start'] = DateTime(item.dat_inicio).strftime("%Y-%m-%d")
	    dic['end'] = DateTime(item.dat_fim).strftime("%Y-%m-%d")
	    dic['data_eleicao'] = DateTime(item.dat_eleicao).strftime("%Y-%m-%d")
	    dic['title'] = str(item.num_legislatura) + 'ª Legislatura' 
	    dic['description'] = DateTime(item.dat_inicio).strftime("%d/%m/%Y") + ' a ' + DateTime(item.dat_fim).strftime("%d/%m/%Y") 
            if (DateTime().strftime("%Y-%m-%d") > DateTime(item.dat_inicio).strftime("%Y-%m-%d") and DateTime().strftime("%Y-%m-%d") < DateTime(item.dat_fim).strftime("%Y-%m-%d")):
               dic['atual'] = True
            else:
               dic['atual'] = False
            lista.append(dic)
            
        lista.sort(key=lambda dic: dic['id'])

       	dic_resultado = {}
    	dic_resultado['@id'] = portal_url + '/@@legislaturas'
       	dic_resultado['@type'] = 'Legislaturas'
       	dic_resultado['description'] = 'Lista de Legislaturas'
        dic_resultado['items'] = lista
     	
	serialized = json.dumps(dic_resultado, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())


class Legislatura(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('legislatura')
        
    def render(self,id=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%d/%m/%Y")
	
	for item in self.context.zsql.legislatura_obter_zsql(num_legislatura=id, ind_excluido=0):
            dic = {}
    	    dic['@id'] = portal_url + '/@@legislatura?id=' + str(item.num_legislatura)
	    dic['@type'] = 'Legislatura'
	    dic['id'] = item.num_legislatura
	    dic['description'] = DateTime(item.dat_inicio).strftime("%d/%m/%Y") + ' a ' + DateTime(item.dat_fim).strftime("%d/%m/%Y")
	    dic['start'] = DateTime(item.dat_inicio).strftime("%Y-%m-%d")
	    dic['end'] = DateTime(item.dat_fim).strftime("%Y-%m-%d")
	    dic['data_eleicao'] = DateTime(item.dat_eleicao).strftime("%Y-%m-%d")
	    dic['title'] = str(item.num_legislatura) + 'ª Legislatura' 

            if id != '':
		    lst_vereadores = []
	   	    for mandato in self.context.zsql.mandato_obter_zsql(num_legislatura=item.num_legislatura, ind_excluido=0):
			dic_vereador = {}
			if mandato.ind_titular == 1:
		           dic_vereador['mandato'] = 'Titular'
		        else:
		           dic_vereador['mandato'] = 'Suplente'
			dic_vereador['votos'] = mandato.num_votos_recebidos
			for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=mandato.cod_parlamentar, ind_excluido=0):
			    dic_vereador['@type'] = 'Vereador'
			    dic_vereador['@id'] =  portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
			    dic_vereador['id'] = parlamentar.cod_parlamentar
			    dic_vereador['title'] = parlamentar.nom_parlamentar
			    dic_vereador['description'] = parlamentar.nom_completo
			    dic_vereador['cod_autor'] = ''
			    for autor in self.context.zsql.autor_obter_zsql(cod_parlamentar=parlamentar.cod_parlamentar):
				dic_vereador['cod_autor'] = autor.cod_autor
			    dic_vereador['image'] = ''
			    lst_imagem = []
			    dic_image = {}
			    foto = str(parlamentar.cod_parlamentar) + "_foto_parlamentar"
			    if hasattr(self.context.sapl_documentos.parlamentar.fotos, foto):    
			       url = portal_url + '/sapl_documentos/parlamentar/fotos/' + foto
			       response = requests.get(url)
			       img = Image.open(BytesIO(response.content))
			       dic_image['content-type'] = 'image/' + str(img.format).lower()
			       dic_image['download'] = url
			       dic_image['filename'] = foto
			       dic_image['width'] = str(img.width)
			       dic_image['height'] = str(img.height)
			       dic_image['size'] = str(len(img.fp.read()))
			       lst_imagem.append(dic_image)
			    dic_vereador['image'] = lst_imagem
			    lst_partido = []
			    for filiacao in self.context.zsql.parlamentar_data_filiacao_obter_zsql(num_legislatura=item.num_legislatura, cod_parlamentar=parlamentar.cod_parlamentar):    
				dic_partido = {}
				dic_partido['token'] = ''
				dic_partido['title'] = ''
				if filiacao.dat_filiacao != '0' and filiacao.dat_filiacao != None:
				    for partido in self.context.zsql.parlamentar_partido_obter_zsql(dat_filiacao=filiacao.dat_filiacao, cod_parlamentar=parlamentar.cod_parlamentar):
				        dic_partido['token'] = partido.sgl_partido
				        dic_partido['title'] = partido.nom_partido
				lst_partido.append(dic_partido)
			    dic_vereador['partido'] = lst_partido
			lst_vereadores.append(dic_vereador)            
		    lst_vereadores.sort(key=lambda dic_vereador: dic_vereador['description'])
		    dic['items'] = lst_vereadores
     	
	serialized = json.dumps(dic, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())

