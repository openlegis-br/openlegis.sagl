# -*- coding: utf-8 -*-

from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from io import BytesIO
import requests
from PIL import Image
import simplejson as json
from DateTime import DateTime


class VereadoresAtuais(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('vereadores_atuais')

    def legislatura(self):
	for item in self.context.zsql.legislatura_atual_obter_zsql():
	    num_legislatura = item.num_legislatura

        return num_legislatura
        
    def render(self):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%d/%m/%Y")
	lista_exercicio = []
	exercicio = []
	dic={}
	dic['@id'] = portal_url + '/@@vereadores_atuais'
	dic['@type'] = 'Vereadores'
	dic['title'] = 'Vereadores em exercício na data atual'

	for item in self.context.zsql.autores_obter_zsql(txt_dat_apresentacao=data_atual):
	    dic_vereador = {}
	    dic_vereador['@type'] = 'Vereador'
	    dic_vereador['@id'] =  portal_url + '/@@vereador?id=' + item.cod_parlamentar
	    dic_vereador['id'] = item.cod_parlamentar
	    dic_vereador['title'] = item.nom_parlamentar
	    dic_vereador['description'] = item.nom_completo
	    dic_vereador['cod_autor'] = item.cod_autor
	    dic_vereador['image'] = ''
            lst_imagem = []
	    dic_image = {}
	    foto = str(item.cod_parlamentar) + "_foto_parlamentar"
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
	    dic_vereador['partido'] = ''
	    for filiacao in self.context.zsql.parlamentar_data_filiacao_obter_zsql(num_legislatura=self.legislatura, cod_parlamentar=item.cod_parlamentar):    
		dic_partido = {}
		dic_partido['token'] = ''
		dic_partido['title'] = ''
		if filiacao.dat_filiacao != '0' and filiacao.dat_filiacao != None:
		    for partido in self.context.zsql.parlamentar_partido_obter_zsql(dat_filiacao=filiacao.dat_filiacao, cod_parlamentar=item.cod_parlamentar):
		        dic_partido['token'] = partido.sgl_partido
		        dic_partido['title'] = partido.nom_partido
		lst_partido.append(dic_partido)
	    dic_vereador['partido'] = lst_partido
	    #for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=item.cod_parlamentar):
	    #   dic['biografia'] = parlamentar.txt_biografia
	    #   dic['cod_parlamentar'] = parlamentar.cod_parlamentar
	    #   pass
	    lista_exercicio.append(dic_vereador)

	lista_exercicio.sort(key=lambda dic_vereador: dic_vereador['description'])

	dic['items'] = lista_exercicio
	
	serialized = json.dumps(dic, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
