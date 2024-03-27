# -*- coding: utf-8 -*-
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from io import BytesIO
import requests
from PIL import Image
import simplejson as json
from DateTime import DateTime
from xml.sax.saxutils import escape

class Vereador(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('vereador')

    def render(self, id):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        data_atual = DateTime().strftime("%d/%m/%Y")
      	for item in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=id):
            dic_vereador = {}
	    dic_vereador['@type'] = 'Vereador'
	    dic_vereador['@id'] =  portal_url + '/@@vereador?id=' + item.cod_parlamentar
	    dic_vereador['id'] = item.cod_parlamentar
	    dic_vereador['title'] = item.nom_parlamentar
	    dic_vereador['description'] = item.nom_completo
	    dic_vereador['email'] = item.end_email
	    if item.txt_biografia != None:
	       dic_vereador['biografia'] = escape(item.txt_biografia)
	    else:
	       dic_vereador['biografia'] = ''
	    dic_vereador['telefone_gabinete'] = item.num_tel_parlamentar
            dic_vereador['cod_autor'] = ''
	    for autor in self.context.zsql.autor_obter_zsql(cod_parlamentar=item.cod_parlamentar):
	        dic_vereador['cod_autor'] = autor.cod_autor
	    if item.dat_nascimento != None:
	       dic_vereador['birthday'] = DateTime(item.dat_nascimento).strftime("%Y-%m-%d")
	    else:
	       dic_vereador['birthday'] = ''
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
	    for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=item.cod_parlamentar):    
		dic_partido = {}
		dic_partido['data_filiacao'] = DateTime(filiacao.dat_filiacao).strftime("%Y-%m-%d")
		if filiacao.dat_desfiliacao != None:
		   dic_partido['data_desfiliacao'] = DateTime(filiacao.dat_desfiliacao).strftime("%Y-%m-%d")
		   dic_partido['filiacao_atual'] = False
		else:
		   dic_partido['data_desfiliacao'] = ''
		   dic_partido['filiacao_atual'] = True
		for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
 		    dic_partido['token'] = partido.sgl_partido
		    dic_partido['title'] = partido.nom_partido
		lst_partido.append(dic_partido)
	    dic_vereador['partido'] = lst_partido
	    lst_mandato = []
	    for mandato in self.context.zsql.mandato_obter_zsql(cod_parlamentar=item.cod_parlamentar, ind_excluido=0):
		dic_mandato = {}
		if mandato.ind_titular == 1:
                   dic_mandato['natureza'] = 'Titular'
                else:
                   dic_mandato['natureza'] = 'Suplente'
                dic_mandato['votos'] = mandato.num_votos_recebidos
                dic_mandato['inicio'] = DateTime(mandato.dat_inicio_mandato).strftime("%Y-%m-%d")
                dic_mandato['fim'] = DateTime(mandato.dat_fim_mandato).strftime("%Y-%m-%d")
                dic_mandato['legislatura'] = mandato.num_legislatura
		lst_mandato.append(dic_mandato)
	    dic_vereador['mandato'] = lst_mandato
	serialized = json.dumps(dic_vereador, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
