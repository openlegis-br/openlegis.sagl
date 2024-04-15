# -*- coding: utf-8 -*-
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from io import BytesIO
import requests
from PIL import Image
import simplejson as json
from DateTime import DateTime


class MesasDiretoras(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('mesas_diretoras')
        
    def render(self):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%Y-%m-%d")
	lista = []
	for item in self.context.zsql.periodo_comp_mesa_obter_zsql(ind_excluido=0):
            dic = {}
    	    dic['@id'] = portal_url + '/@@mesa_diretora?id=' + str(item.cod_periodo_comp)
	    dic['@type'] = 'Mesa Diretora'
	    dic['id'] = str(item.cod_periodo_comp)
	    dic['start'] = DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d")
	    dic['end'] = DateTime(item.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")
	    dic['title'] = 'Período de composição'
	    dic['legislatura'] = str(item.num_legislatura)
            dic['description'] = DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(item.dat_fim_periodo, datefmt='international').strftime("%d/%m/%Y")
            if (DateTime().strftime("%Y-%m-%d") > DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d") and DateTime().strftime("%Y-%m-%d") < DateTime(item.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")):
               dic['atual'] = True
            else:
               dic['atual'] = False
            lista.append(dic)
            
        lista.sort(key=lambda dic: dic['title'])
        
       	dic_resultado = {}
    	dic_resultado['@id'] = portal_url + '/@@mesas_diretoras'
       	dic_resultado['@type'] = 'Mesas Diretoras'
       	dic_resultado['description'] = 'Lista de Mesas Diretoras'
        dic_resultado['items'] = lista

	serialized = json.dumps(dic_resultado, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
	

class MesaDiretora(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('mesa_diretora')
        
    def render(self,id):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
	data_atual = DateTime().strftime("%Y-%m-%d")
	
	for item in self.context.zsql.periodo_comp_mesa_obter_zsql(cod_periodo_comp=id, ind_excluido=0):
            dic = {}
    	    dic['@id'] = portal_url + '/@@mesa_diretora?id=' + str(item.cod_periodo_comp)
	    dic['@type'] = 'Mesa Diretora'
	    dic['id'] = str(item.cod_periodo_comp)
	    dic['start'] = DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d")
	    dic['end'] = DateTime(item.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")
	    dic['legislatura'] = str(item.num_legislatura)
	    dic['title'] = 'Composição da Mesa Diretora'
            dic['description'] = DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(item.dat_fim_periodo, datefmt='international').strftime("%d/%m/%Y")
            if (DateTime().strftime("%Y-%m-%d") > DateTime(item.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d") and DateTime().strftime("%Y-%m-%d") < DateTime(item.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")):
               dic['atual'] = True
            else:
               dic['atual'] = False
            if id != '':         
               lst_membros = []
               for composicao in self.context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=id, ind_excluido=0):
                   cargo = self.context.zsql.cargo_mesa_obter_zsql(cod_cargo=composicao.cod_cargo, ind_excluido=0)[0]
                   parlamentar = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=composicao.cod_parlamentar, ind_excluido=0)[0]
                   dic_membros = {}
                   dic_membros['@id'] =  portal_url + '/@@vereador?id=' + composicao.cod_parlamentar
                   dic_membros['@type'] = 'Vereador'
		   dic_membros['id'] = str(parlamentar.cod_parlamentar)
		   dic_membros['title'] = parlamentar.nom_parlamentar
		   dic_membros['description'] = parlamentar.nom_completo
                   dic_membros['cargo'] = cargo.des_cargo
	           dic_membros['image'] = ''
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
	           dic_membros['image'] = lst_imagem
		   lst_partido = []
		   for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=composicao.cod_parlamentar):    
		       dic_partido = {}
		       for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
			   dic_partido['token'] = partido.sgl_partido
			   dic_partido['title'] = partido.nom_partido
		       if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
			   lst_partido.append(dic_partido)
	           dic_membros['partido'] = lst_partido
                   lst_membros.append(dic_membros)

               dic['items'] = lst_membros

	serialized = json.dumps(dic, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
