# -*- coding: utf-8 -*-
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from io import BytesIO
import requests
from PIL import Image
import simplejson as json
from DateTime import DateTime

class Comissoes(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('comissoes')
        
    def render(self):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%Y-%m-%d")
	lista = []
	for item in self.context.zsql.comissao_obter_zsql(ind_extintas=0, ind_excluido=0):
            dic = {}
    	    dic['@id'] = portal_url + '/@@comissao?id=' + str(item.cod_comissao)
	    dic['@type'] = 'Comissão'
	    dic['id'] = str(item.cod_comissao)
	    dic['start'] = DateTime(item.dat_criacao, datefmt='international').strftime("%Y-%m-%d")
	    dic['title'] = item.sgl_comissao
            dic['description'] = item.nom_comissao
            dic['tipo'] = item.nom_tipo_comissao
            lista.append(dic)
            
        lista.sort(key=lambda dic: dic['title'])
        
       	dic_resultado = {}
    	dic_resultado['@id'] = portal_url + '/@@comissoes'
       	dic_resultado['@type'] = 'Comissões'
       	dic_resultado['description'] = 'Lista de Comissões'
        dic_resultado['items'] = lista

	serialized = json.dumps(dic_resultado, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
	

class Comissao(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('comissao')
        
    def render(self,id=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%Y-%m-%d")
	for item in self.context.zsql.comissao_obter_zsql(cod_comissao=id, ind_extintas=0, ind_excluido=0):
            dic = {}
    	    dic['@id'] = portal_url + '/@@comissao?id=' + str(item.cod_comissao)
	    dic['@type'] = 'Comissão'
	    dic['id'] = str(item.cod_comissao)
	    dic['start'] = DateTime(item.dat_criacao, datefmt='international').strftime("%Y-%m-%d")
	    dic['title'] = item.sgl_comissao
            dic['description'] = item.nom_comissao
            dic['tipo'] = item.nom_tipo_comissao

            if id != '':
               lst_composicao = []
               lst_periodos = []
               for periodo in self.context.zsql.periodo_comp_comissao_obter_zsql(ind_excluido=0):
                  dic_composicao = {}
                  dic_composicao['title'] = 'Composição da Comissão'
                  dic_composicao['description'] = DateTime(periodo.dat_inicio_periodo, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(periodo.dat_fim_periodo, datefmt='international').strftime("%d/%m/%Y")
                  dic_composicao['start'] = DateTime(periodo.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d")
                  dic_composicao['end'] = DateTime(periodo.dat_fim_periodo).strftime("%Y-%m-%d")
                  dic_composicao['id'] = periodo.cod_periodo_comp
                  if (DateTime().strftime("%Y-%m-%d") > DateTime(periodo.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d")) and (DateTime().strftime("%Y-%m-%d") < DateTime(periodo.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")):
                    dic_composicao['atual'] = True
                  else:
                    dic_composicao['atual'] = False
                  lst_membros = []
                  for composicao in self.context.zsql.composicao_comissao_obter_zsql(cod_comissao=item.cod_comissao, cod_periodo_comp=periodo.cod_periodo_comp):
                     dic_membros = {}
                     dic_membros['@id'] =  portal_url + '/@@vereador?id=' + composicao.cod_parlamentar
                     dic_membros['@type'] = 'Vereador'
		     dic_membros['id'] = str(composicao.cod_parlamentar)
		     dic_membros['title'] = composicao.nom_parlamentar
		     dic_membros['description'] = composicao.nom_completo
                     dic_membros['cargo'] = composicao.des_cargo
                     if composicao.ind_titular == 1:
                        dic_membros['mandato'] = 'Titular'
                     else:
                        dic_membros['mandato'] = 'Suplente'
                     if composicao.dat_desligamento != None or composicao.dat_desligamento != '':
                        lst_membros.append(dic_membros)
		     lst_partido = []
		     for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=composicao.cod_parlamentar):    
		         dic_partido = {}
		         for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
			     dic_partido['token'] = partido.sgl_partido
			     dic_partido['title'] = partido.nom_partido
			 if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
			    lst_partido.append(dic_partido)
	             dic_membros['partido'] = lst_partido
                  dic_composicao['membros'] = lst_membros
                  lst_composicao.append(dic_composicao)
               dic['periodos_composicao'] = lst_composicao

               lst_reunioes = []
               for reuniao in self.context.zsql.reuniao_comissao_obter_zsql(cod_comissao=item.cod_comissao, ind_excluido=0):
                  dic_reuniao = {}
	          dic_reuniao['@id'] = portal_url + '/@@reuniao_comissao?id=' + str(reuniao.cod_reuniao)
	          dic_reuniao['@type'] = 'Reunião de Comissão'
	          dic_reuniao['id'] = str(reuniao.cod_reuniao)
	          dic_reuniao['title'] = str(reuniao.num_reuniao) + 'ª Reunião ' + reuniao.des_tipo_reuniao
	          dic_reuniao['description'] = str(reuniao.num_reuniao) + 'ª Reunião ' + reuniao.des_tipo_reuniao + ' da ' + item.sgl_comissao
	          dic_reuniao['data'] = DateTime(reuniao.dat_inicio_reuniao, datefmt='international').strftime("%Y-%m-%d")
	          dic_reuniao['tema'] = reuniao.txt_tema
	          dic_reuniao['hora_abertura'] = reuniao.hr_inicio_reuniao
	          dic_reuniao['hora_encerramento'] = reuniao.hr_fim_reuniao
                  lst_reunioes.append(dic_reuniao)
               
               dic['reunioes'] = lst_reunioes

	serialized = json.dumps(dic, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
