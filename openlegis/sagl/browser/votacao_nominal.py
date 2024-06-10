# -*- coding: utf-8 -*-
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from io import BytesIO
import requests
from PIL import Image
import simplejson as json
from DateTime import DateTime

class votacaoNominal(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('votacao_nominal')

    def render(self, sessao_id):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()

	lst_materias = []

        dic_items = {}

	for ordem in self.context.zsql.ordem_dia_obter_zsql(cod_sessao_plen=sessao_id, ind_excluido=0):
	  sessao_plenaria = self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=sessao_id)[0]   
	  tipo_sessao = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao_plenaria.tip_sessao)[0]
	  dic_items["@id"] = portal_url + '/@@votacao_nominal?sessao_id=' + str(sessao_id)
	  dic_items["title"] = 'Lista de votação nominal por reunião'
 	  dic_items["description"] = str(sessao_plenaria.num_sessao_plen) + 'ª Reunião ' + tipo_sessao.nom_sessao + ' da ' + str(sessao_plenaria.num_sessao_leg) + 'ª Sessão Legislativa'
	  dic_items["data_votacao"] = DateTime(sessao_plenaria.dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d")
          dic_items['items'] = lst_materias 
          
	  if ordem.tip_votacao == 2:     

	    # MATÉRIAS LEGISLATIVAS
	    if ordem.cod_materia != None and ordem.cod_materia !='':
	       votacao = self.context.zsql.votacao_ordem_dia_obter_zsql(cod_sessao_plen=sessao_plenaria.cod_sessao_plen, cod_ordem=ordem.cod_ordem, cod_materia=ordem.cod_materia, ind_excluido=0)[0]
	       for materia in self.context.zsql.materia_obter_zsql(cod_materia=ordem.cod_materia, ind_excluido=0):
	           dic_item = {}
	           dic_item["@id"] = portal_url + '/@@materia?id=' + str(materia.cod_materia)
	           dic_item["@type"] = 'Matéria Legislativa'
                   dic_item["title"] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
	           dic_item["id"] = str(materia.cod_materia)
	           dic_item["description"] = materia.txt_ementa
	           for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=ordem.tip_votacao):
		       dic_item["tipo_votacao"] = tip_votacao.des_tipo_votacao
	           for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
		       dic_item["turno"] = turno.des_turno
		   for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem.tip_quorum):
		       dic_item["quorum"] = quorum.des_quorum
		   autores = self.context.zsql.autoria_obter_zsql(cod_materia=ordem.cod_materia)
		   fields = autores.data_dictionary().keys()
		   lista_autor = []
		   for autor in autores:
		       dic_autor = {}
		       for field in fields:
		           dic_autor["@id"] = portal_url + '/@@autor?id=' + str(autor.cod_autor)
		  	   dic_autor['@type'] = 'Autor'
		  	   dic_autor['description'] = autor.des_tipo_autor
		  	   dic_autor['id'] = autor.cod_autor
		           dic_autor['title'] = autor.nom_autor_join
		           if autor.ind_primeiro_autor == 1:
		              dic_autor['primeiro_autor'] = True
		           else:
		              dic_autor['primeiro_autor'] = False
		       lista_autor.append(dic_autor)
		   dic_item["autoria"] = lista_autor

	    # PARECERES
	    elif ordem.cod_parecer != None and ordem.cod_parecer !='':
	       votacao = self.context.zsql.votacao_ordem_dia_obter_zsql(cod_sessao_plen=sessao_plenaria.cod_sessao_plen, cod_ordem=ordem.cod_ordem, cod_parecer=ordem.cod_parecer, ind_excluido=0)[0]
	       for parecer in self.context.zsql.relatoria_obter_zsql(cod_relatoria=ordem.cod_parecer):
		   comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao)[0]
		   relator = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
		   materia = self.context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia)[0]
	           dic_item = {}
		   dic_item["@id"] = portal_url + '/@@parecer?id=' + str(parecer.cod_relatoria)
		   dic_item["@type"] =  'Parecer'
		   dic_item['title'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
		   dic_item["id"] =  str(parecer.cod_relatoria)
		   dic_item['description'] = ''
		   if parecer.tip_conclusao == 'F':
		      dic_item['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', FAVORÁVEL ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
		   elif parecer.tip_conclusao == 'C':
		      dic_item['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', CONTRÁRIO ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
	           dic_item["data_votacao"] = DateTime(sessao_plenaria.dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d")	       
	           for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=ordem.tip_votacao):
		       dic_item["tipo_votacao"] = tip_votacao.des_tipo_votacao
		   for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
		       dic_item["turno"] = turno.des_turno
		   for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem.tip_quorum):
		       dic_item["quorum"] = quorum.des_quorum
		   lista_autor = []
		   dic_autor = {}
		   dic_autor["@id"] = portal_url + '/@@comissao?id=' + str(comissao.cod_comissao)
		   dic_autor['@type'] = 'Comissão'
		   dic_autor['description'] = comissao.nom_comissao
		   dic_autor['id'] = comissao.cod_comissao
		   dic_autor['title'] = comissao.sgl_comissao
		   lista_autor.append(dic_autor)
		   dic_item["autoria"] = lista_autor

	    #votação nominal
	    lst_resultado = []
	    dic_resultado = {}
	    if votacao.tip_resultado_votacao != None:
 	       resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
   	       for i in resultado:
	          nom_resultado= i.nom_resultado
		  dic_resultado['resultado'] = i.nom_resultado
		  lst_resultado.append(dic_resultado)
	    dic_item["apuracao"] = lst_resultado
	    dic_resultado["votos"] = []
	    lst_sim = []
	    lst_nao = []
	    lst_abstencao = []
	    lst_presidencia = []
	    lst_ausente = []
	    for voto in self.context.zsql.votacao_parlamentar_obter_zsql(cod_votacao=votacao.cod_votacao, ind_excluido=0):
	        parlamentar = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=voto.cod_parlamentar)[0]
	        dic_voto = {}
	        dic_voto['@id'] =  portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
	        dic_voto['@type'] = 'Vereador'
	        dic_voto['id'] = str(parlamentar.cod_parlamentar)
	        dic_voto['title'] =  parlamentar.nom_parlamentar
	        dic_voto['description'] =  parlamentar.nom_completo
	        dic_voto['votacao_id'] = str(voto.cod_votacao)
	        lst_partido = []
	        for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=parlamentar.cod_parlamentar):    
	 	   dic_partido = {}
	 	   for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
		       dic_partido['token'] = partido.sgl_partido
		       dic_partido['title'] = partido.nom_partido
		   if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
		       lst_partido.append(dic_partido)
	        dic_voto['partido'] = lst_partido                       
	        if voto.vot_parlamentar == 'Nao':
		  dic_voto['voto'] = 'Não'
		  lst_nao.append(dic_voto)
	        elif voto.vot_parlamentar == 'Abstencao':
		  dic_voto['voto'] = 'Abstenção'
		  lst_abstencao.append(dic_voto)
	        elif voto.vot_parlamentar == 'Sim':
		  dic_voto['voto'] = 'Sim'
		  lst_sim.append(dic_voto)
	        elif voto.vot_parlamentar == 'Na Presid.':
		  dic_voto['voto'] = 'Na Presidência'
		  lst_presidencia.append(dic_voto)
	        elif voto.vot_parlamentar == 'Ausente':
		  dic_voto['voto'] = 'Ausente'
		  lst_ausente.append(dic_voto)
		  
	    dic_nominal = {}
	    dic_nominal["favoravel"] = lst_sim
	    dic_nominal["contrario"] = lst_nao
	    dic_nominal["abstencao"] = lst_abstencao
	    dic_nominal["presidencia"] = lst_presidencia
	    dic_nominal["ausente"] = lst_ausente
	    
	    dic_resultado["votos"].append(dic_nominal)
	    dic_resultado["favoravel"] = len(lst_sim)
	    dic_resultado["contrario"] = len(lst_nao)
	    dic_resultado["abstencao"] = len(lst_abstencao)
	    dic_resultado["ausente"] = len(lst_ausente)
	    dic_resultado["presidencia"] = len(lst_presidencia)
		       
            lst_materias.append(dic_item)

	serialized = json.dumps(dic_items, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
