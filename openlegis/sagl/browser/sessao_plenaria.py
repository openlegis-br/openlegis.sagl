# -*- coding: utf-8 -*-
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from io import BytesIO
import requests
from PIL import Image
import simplejson as json
from DateTime import DateTime

class SessoesPlenarias(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('sessoes_plenarias')
       
    def render(self, id='', tipo='', ano=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%d/%m/%Y")

	lista = []
	for item in self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=id, tip_sessao=tipo, ano_sessao=ano, ind_excluido=0):
	    dic = {}
	    dic['@id'] = portal_url + '/@@sessao_plenaria?id=' + str(item.cod_sessao_plen)
	    dic['@type'] = 'Sessão Plenária'
	    dic['id'] = item.cod_sessao_plen
	    dic['tipo_id'] = str(item.tip_sessao)
	    for tipo in self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao, ind_excluido=0):
		dic['tipo'] = tipo.nom_sessao
	    dic['title'] = str(item.num_sessao_plen) + 'ª ' + 'Reunião ' +  dic['tipo']
	    dic['numero'] = str(item.num_sessao_plen)
	    dic['ano'] = item.ano_sessao  
	    dic['data_abertura'] = DateTime(item.dat_inicio).strftime("%Y-%m-%d")
	    dic['hora_abertura'] = str(item.hr_inicio_sessao)
	    dic['data_encerramento'] = DateTime(item.dat_fim).strftime("%Y-%m-%d")
	    dic['hora_encerramento'] = str(item.hr_fim_sessao)
	    dic['description'] = str(item.num_sessao_plen) + 'ª ' + 'Reunião ' +  dic['tipo'] + ' da ' + str(item.num_sessao_leg) + 'ª Sessão Legislativa'
	    dic['legislatura'] = str(item.num_legislatura) + 'ª Legislatura'
	    dic['legislatura_id'] = str(item.num_legislatura)
	    dic['sessao_legislativa'] = str(item.num_sessao_leg) + 'ª Sessão Legislativa'
	    dic['sessao_legislativa_id'] = str(item.cod_sessao_leg)
	    lst_pauta = []
	    dic_pauta = {}	    
	    pauta = str(item.cod_sessao_plen) + "_pauta_sessao.pdf"
	    if hasattr(self.context.sapl_documentos.pauta_sessao, pauta):
	       dic_pauta['content-type'] = 'application/pdf'
	       dic_pauta['download'] = portal_url + '/sapl_documentos/pauta_sessao/' + pauta
	       dic_pauta['filename'] = pauta
	       dic_pauta['size'] = ''
	       lst_pauta.append(dic_pauta)
            dic['arquivo_pauta'] = lst_pauta

	    lst_ata = []
	    dic_ata = {}
	    ata = str(item.cod_sessao_plen) + "_ata_sessao.pdf"
	    if hasattr(self.context.sapl_documentos.ata_sessao, ata):
	       dic_ata['content-type'] = 'application/pdf'
	       dic_ata['download'] = portal_url + '/sapl_documentos/ata_sessao/' + ata
	       dic_ata['filename'] = ata
	       dic_ata['size'] = ''
	       lst_ata.append(dic_ata)
            dic['arquivo_ata'] = lst_ata

	    lista.append(dic)
	    
       	dic_resultado = {}
    	dic_resultado['@id'] = portal_url + '/@@sessoes_plenarias'
       	dic_resultado['@type'] = 'Sessões Plenárias'
       	dic_resultado['description'] = 'Lista de Sessões Plenárias'
	dic_resultado['generated'] = DateTime().strftime("%Y-%m-%dT%H:%M:%S+00:00")
        dic_resultado['items'] = lista
		
	serialized = json.dumps(dic_resultado, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())


class SessoaoPlenaria(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('sessao_plenaria')
       
    def render(self, id='', tipo='', ano=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%d/%m/%Y")

	for item in self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=id, tip_sessao=tipo, ano_sessao=ano, ind_excluido=0):
	    dic = {}
	    dic['@id'] = portal_url + '/@@sessao_plenaria?id=' + str(item.cod_sessao_plen)
	    dic['@type'] = 'Sessão Plenária'
	    dic['id'] = item.cod_sessao_plen
	    dic['tipo_id'] = str(item.tip_sessao)
	    for tipo in self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao, ind_excluido=0):
		dic['tipo'] = tipo.nom_sessao
	    dic['title'] = str(item.num_sessao_plen) + 'ª ' + 'Reunião ' +  dic['tipo']
	    dic['numero'] = str(item.num_sessao_plen)
	    dic['ano'] = item.ano_sessao  
	    dic['data_abertura'] = DateTime(item.dat_inicio).strftime("%Y-%m-%d")
	    dic['hora_abertura'] = str(item.hr_inicio_sessao)
	    dic['data_encerramento'] = DateTime(item.dat_fim).strftime("%Y-%m-%d")
	    dic['hora_encerramento'] = str(item.hr_fim_sessao)
	    dic['description'] = str(item.num_sessao_plen) + 'ª ' + 'Reunião ' +  dic['tipo'] + ' da ' + str(item.num_sessao_leg) + 'ª Sessão Legislativa'
	    dic['legislatura'] = str(item.num_legislatura) + 'ª Legislatura'
	    dic['legislatura_id'] = str(item.num_legislatura)
	    dic['sessao_legislativa'] = str(item.num_sessao_leg) + 'ª Sessão Legislativa'
	    dic['sessao_legislativa_id'] = str(item.cod_sessao_leg)
	    dic['generated'] = DateTime().strftime("%Y-%m-%dT%H:%M:%S+00:00")
	    lst_pauta = []
	    dic_pauta = {}	    
	    pauta = str(item.cod_sessao_plen) + "_pauta_sessao.pdf"
	    if hasattr(self.context.sapl_documentos.pauta_sessao, pauta):
	       dic_pauta['content-type'] = 'application/pdf'
	       dic_pauta['download'] = portal_url + '/sapl_documentos/pauta_sessao/' + pauta
	       dic_pauta['filename'] = pauta
	       dic_pauta['size'] = ''
	       lst_pauta.append(dic_pauta)
            dic['arquivo_pauta'] = lst_pauta

	    lst_ata = []
	    dic_ata = {}
	    ata = str(item.cod_sessao_plen) + "_ata_sessao.pdf"
	    if hasattr(self.context.sapl_documentos.ata_sessao, ata):
	       dic_ata['content-type'] = 'application/pdf'
	       dic_ata['download'] = portal_url + '/sapl_documentos/ata_sessao/' + ata
	       dic_ata['filename'] = ata
	       dic_ata['size'] = ''
	       lst_ata.append(dic_ata)
            dic['arquivo_ata'] = lst_ata

	    if id != '':
		    dic["chamada_abertura"] = []
		    dic_presenca_ab = {}
		    lst_presenca_ab = []
		    for presenca_abertura in self.context.zsql.presenca_sessao_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, tip_frequencia='P', ind_excluido=0):
			dic_presenca = {}
			for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca_abertura.cod_parlamentar,ind_excluido=0):
			    dic_presenca['@type'] = 'Vereador'
			    dic_presenca['@id'] = portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
			    dic_presenca['id'] = parlamentar.cod_parlamentar
			    dic_presenca['description'] = parlamentar.nom_completo
			    dic_presenca['title'] = parlamentar.nom_parlamentar
			    lst_partido = []
			    for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=parlamentar.cod_parlamentar):    
			        dic_partido = {}
				for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
				    dic_partido['token'] = partido.sgl_partido
				    dic_partido['title'] = partido.nom_partido
				if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
				   lst_partido.append(dic_partido)
		            dic_presenca['partido'] = lst_partido
			    lst_presenca_ab.append(dic_presenca)
		    dic_presenca_ab["qtde_presente"] = len(lst_presenca_ab)
		    dic_presenca_ab["presente"] = lst_presenca_ab

		    lst_ausencia = []
		    for presenca_abertura in self.context.zsql.presenca_sessao_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, tip_frequencia='F', ind_excluido=0):
			dic_ausencia = {}
			for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca_abertura.cod_parlamentar,ind_excluido=0):
			    dic_ausencia['@type'] = 'Vereador'
			    dic_ausencia['@id'] = portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
			    dic_ausencia['id'] = parlamentar.cod_parlamentar
			    dic_ausencia['description'] = parlamentar.nom_completo
			    dic_ausencia['title'] = parlamentar.nom_parlamentar
			    lst_partido = []
			    for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=parlamentar.cod_parlamentar):    
			        dic_partido = {}
				for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
				    dic_partido['token'] = partido.sgl_partido
				    dic_partido['title'] = partido.nom_partido
				if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
				   lst_partido.append(dic_partido)
		            dic_ausencia['partido'] = lst_partido
			    lst_ausencia.append(dic_ausencia)
		    dic_presenca_ab["qtde_ausente"] = len(lst_ausencia)
		    dic_presenca_ab["ausente"] = lst_ausencia
		    
		    lst_justificados = []
		    for presenca_abertura in self.context.zsql.presenca_sessao_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, tip_frequencia='A', ind_excluido=0):
			dic_justificados = {}
			for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca_abertura.cod_parlamentar,ind_excluido=0):
			    dic_justificados['@type'] = 'Vereador'
			    dic_justificados['@id'] = portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
			    dic_justificados['id'] = parlamentar.cod_parlamentar
			    dic_justificados['description'] = parlamentar.nom_completo
			    dic_justificados['title'] = parlamentar.nom_parlamentar
			    dic_justificados['partido'] = ''
			    lst_partido = []
			    for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=parlamentar.cod_parlamentar):    
			        dic_partido = {}
				for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
				    dic_partido['token'] = partido.sgl_partido
				    dic_partido['title'] = partido.nom_partido
				if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
				   lst_partido.append(dic_partido)
		            dic_justificados['partido'] = lst_partido
			    lst_justificados.append(dic_justificados)
		    dic_presenca_ab["qtde_justificado"] = len(lst_justificados)
		    dic_presenca_ab["justificado"] = lst_justificados

		    dic["chamada_abertura"].append(dic_presenca_ab)

		    # ORDEM DO DIA

		    dic["ordem_dia"] = []

		    dic_od = {}

		    lst_chamada_ordem_dia = []
		    
		    dic_presenca_od = {}

		    lst_presenca = []
		    for presenca_ordem_dia in self.context.zsql.presenca_ordem_dia_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, tip_frequencia='P', ind_excluido=0):
			dic_presenca = {}
			for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca_ordem_dia.cod_parlamentar,ind_excluido=0):
			    dic_presenca['@type'] = 'Vereador'
			    dic_presenca['@id'] = portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
			    dic_presenca['id'] = parlamentar.cod_parlamentar
			    dic_presenca['description'] = parlamentar.nom_completo
			    dic_presenca['title'] = parlamentar.nom_parlamentar
			    dic_presenca['partido'] = ''
			    lst_partido = []
			    for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=parlamentar.cod_parlamentar):    
			        dic_partido = {}
				for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
				    dic_partido['token'] = partido.sgl_partido
				    dic_partido['title'] = partido.nom_partido
				if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
				   lst_partido.append(dic_partido)
		            dic_presenca['partido'] = lst_partido
			    lst_presenca.append(dic_presenca)
		    dic_presenca_od["qtde_presente"] = len(lst_presenca)
		    dic_presenca_od["presente"] = lst_presenca

		    lst_ausencia = []
		    for presenca_ordem_dia in self.context.zsql.presenca_ordem_dia_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, tip_frequencia='F', ind_excluido=0):
			dic_ausencia = {}
			for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca_ordem_dia.cod_parlamentar,ind_excluido=0):
			    dic_ausencia['@type'] = 'Vereador'
			    dic_ausencia['@id'] = portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
			    dic_ausencia['id'] = parlamentar.cod_parlamentar
			    dic_ausencia['description'] = parlamentar.nom_completo
			    dic_ausencia['title'] = parlamentar.nom_parlamentar
			    lst_partido = []
			    for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=parlamentar.cod_parlamentar):    
			        dic_partido = {}
				for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
				    dic_partido['token'] = partido.sgl_partido
				    dic_partido['title'] = partido.nom_partido
				if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
				   lst_partido.append(dic_partido)
		            dic_ausencia['partido'] = lst_partido
			    lst_ausencia.append(dic_ausencia)
		    dic_presenca_od["qtde_ausente"] = len(lst_ausencia)
		    dic_presenca_od["ausente"] = lst_ausencia
		    
		    lst_justificados = []
		    for presenca_ordem_dia in self.context.zsql.presenca_ordem_dia_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, tip_frequencia='A', ind_excluido=0):
			dic_justificados = {}
			for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca_ordem_dia.cod_parlamentar,ind_excluido=0):
			    dic_justificados['@type'] = 'Vereador'
			    dic_justificados['@id'] = portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
			    dic_justificados['id'] = parlamentar.cod_parlamentar
			    dic_justificados['description'] = parlamentar.nom_completo
			    dic_justificados['title'] = parlamentar.nom_parlamentar
			    dic_justificados['partido'] = ''
			    lst_partido = []
			    for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=parlamentar.cod_parlamentar):    
			        dic_partido = {}
				for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
				    dic_partido['token'] = partido.sgl_partido
				    dic_partido['title'] = partido.nom_partido
				if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
				   lst_partido.append(dic_partido)
		            dic_justificados['partido'] = lst_partido
			    lst_justificados.append(dic_justificados)
		    dic_presenca_od["qtde_justificado"] = len(lst_justificados)
		    dic_presenca_od["justificado"] = lst_justificados
		    
		    lst_chamada_ordem_dia.append(dic_presenca_od)
		    dic_od['chamada'] = lst_chamada_ordem_dia

		    # ITEMS DA ORDEM DO DIA
		    lst_votacao=[]
		    for ordem in self.context.zsql.ordem_dia_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, ind_excluido=0):
			# PARECERES
			if ordem.cod_parecer != None:
		           for parecer in self.context.zsql.relatoria_obter_zsql(cod_relatoria=ordem.cod_parecer):
		               comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao)[0]
		               relator = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
		               dic_parecer = {}
		               dic_parecer["@id"] = portal_url + '/@@parecer?id=' + str(parecer.cod_relatoria)
		               dic_parecer["@type"] =  'Parecer'
			       dic_parecer["cod_sessao_plen"] = str(ordem.cod_sessao_plen)
			       dic_parecer['data_sessao'] = DateTime(ordem.dat_ordem).strftime("%Y-%m-%d")
			       dic_parecer["cod_ordem"] = str(ordem.cod_ordem)
			       dic_parecer["numero_ordem"] = str(ordem.num_ordem)
		               dic_parecer["id"] =  str(parecer.cod_relatoria)
			       dic_parecer['title'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
			       materia = self.context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia)[0]
			       dic_parecer['description'] = ''
		               if parecer.tip_conclusao == 'F':
		                  dic_parecer['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', FAVORÁVEL ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
		               elif parecer.tip_conclusao == 'C':
		                  dic_parecer['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', CONTRÁRIO ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)		       
		               lista_autor = []
		               dic_autor = {}
			       dic_autor["@id"] = portal_url + '/@@comissao?id=' + str(comissao.cod_comissao)
			       dic_autor['@type'] = 'Comissão'
			       dic_autor['description'] = comissao.nom_comissao
			       dic_autor['id'] = comissao.cod_comissao
			       dic_autor['title'] = comissao.sgl_comissao
		               lista_autor.append(dic_autor)
		               dic_parecer["autoria"] = lista_autor
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(parecer.cod_relatoria) + "_parecer.pdf"
			       if hasattr(self.context.sapl_documentos.parecer_comissao, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/parecer_comissao/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_parecer['file'] = lst_arquivo
			       dic_parecer["turno"] = ''
			       for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
				   dic_parecer["turno"] = turno.des_turno
				   dic_parecer["turno_id"] = str(turno.cod_turno)
			       dic_parecer["tipo_votacao_id"] = str(ordem.tip_votacao)
			       dic_parecer["tipo_votacao"] = ''
			       for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=ordem.tip_votacao):
				   dic_parecer["tipo_votacao"] = tip_votacao.des_tipo_votacao
			       dic_parecer["quorum"]=""
			       for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem.tip_quorum):
				   dic_parecer["quorum"] = quorum.des_quorum
				   dic_parecer["quorum_id"] = str(quorum.cod_quorum)
				   
		               # RESULTADO DE VOTAÇÃO DO PARECER
		               dic_parecer["resultado_votacao"] = []
		               lst_resultado = []
		               dic_resultado = {}
		               # totalização de votos
			       for votacao in self.context.zsql.votacao_ordem_dia_obter_zsql(cod_parecer=ordem.cod_parecer, cod_sessao_plen=ordem.cod_sessao_plen, ind_excluido=0):
			           dic_resultado["votacao_id"] = str(votacao.cod_votacao)
				   if votacao.tip_votacao == 1 or votacao.tip_votacao == 2:
				      if votacao.num_votos_sim == 0:
				         votos_favoraveis = '0'
				      elif votacao.num_votos_sim == 1:
				         votos_favoraveis =  str(votacao.num_votos_sim)
				      elif votacao.num_votos_sim > 1:
				         votos_favoraveis = str(votacao.num_votos_sim)
				      if votacao.num_votos_nao == 0:
				         votos_contrarios = '0'
				      elif votacao.num_votos_nao == 1:
				         votos_contrarios = str(votacao.num_votos_nao)
				      elif votacao.num_votos_nao > 1:
				         votos_contrarios = str(votacao.num_votos_nao)
				      if votacao.num_abstencao == 0:
				         abstencoes = '0'
				      elif votacao.num_abstencao == 1:
				         abstencoes = str(votacao.num_abstencao)
				      elif votacao.num_abstencao > 1:
				         abstencoes =  str(votacao.num_abstencao)
				      dic_resultado["favoravel"] = votos_favoraveis
				      dic_resultado["contrario"] = votos_contrarios
				      dic_resultado["abstencao"] = abstencoes
				   if votacao.tip_resultado_votacao:
				      resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
				      for i in resultado:
				          nom_resultado= i.nom_resultado
				          dic_resultado["resultado_title"] = nom_resultado
				          dic_resultado["resultado_id"] = str(votacao.tip_resultado_votacao)
				   lst_resultado.append(dic_resultado)
				   dic_parecer["resultado_votacao"] = lst_resultado
				   # votação nominal
				   if votacao.tip_votacao == 2:
				      dic_parecer["resultado_votacao_nominal"] = []
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
				      dic_parecer["resultado_votacao_nominal"].append(dic_nominal)

		               lst_votacao.append(dic_parecer)
		               
		        # MATÉRIAS      
			elif ordem.cod_materia != None:
			   materia = self.context.zsql.materia_obter_zsql(cod_materia=ordem.cod_materia)[0]
		           dic_votacao = {}
		           dic_votacao["@id"] = portal_url + '/@@materia?id=' + str(ordem.cod_materia)
		           dic_votacao["@type"] = 'Matéria'
			   dic_votacao["cod_sessao_plen"] = str(ordem.cod_sessao_plen)
			   dic_votacao['data_sessao'] = DateTime(ordem.dat_ordem).strftime("%Y-%m-%d")
			   dic_votacao["cod_ordem"] = str(ordem.cod_ordem)
			   dic_votacao["numero_ordem"] = str(ordem.num_ordem)
			   dic_votacao['id'] = str(ordem.cod_materia)
			   lst_arquivo = []
			   dic_arquivo = {}	    
			   arquivo = str(ordem.cod_materia) + "_texto_integral.pdf"
			   if hasattr(self.context.sapl_documentos.materia, arquivo):
			      dic_arquivo['content-type'] = 'application/pdf'
			      dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/' + arquivo
			      dic_arquivo['filename'] = arquivo
			      dic_arquivo['size'] = ''
			      lst_arquivo.append(dic_arquivo)
		           dic_votacao['file'] = lst_arquivo
		           dic_votacao['remoteUrl'] = portal_url + '/consultas/materia/pasta_digital?cod_materia=' + ordem.cod_materia
			   dic_votacao["title"] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			   dic_votacao["description"] = materia.txt_ementa
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
			   dic_votacao["autoria"] = lista_autor
			   dic_votacao["turno"] = ''
			   for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
			       dic_votacao["turno"] = turno.des_turno
			       dic_votacao["turno_id"] = str(turno.cod_turno)
			   dic_votacao["tipo_votacao_id"] = str(ordem.tip_votacao)
			   dic_votacao["tipo_votacao"] = ''
			   for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=ordem.tip_votacao):
			       dic_votacao["tipo_votacao"] = tip_votacao.des_tipo_votacao
			   dic_votacao["quorum"]=""
			   for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem.tip_quorum):
			       dic_votacao["quorum"] = quorum.des_quorum
			       dic_votacao["quorum_id"] = str(quorum.cod_quorum)

		           # EMENDAS
		           lst_emendas=[]
		           for emenda in self.context.zsql.emenda_obter_zsql(cod_materia=ordem.cod_materia, ind_excluido=0, exc_pauta=0):
		               dic_emenda = {}
		               dic_emenda["@id"] = portal_url + '/@@emenda?id=' + str(emenda.cod_emenda)
		               dic_emenda["@type"] =  'Emenda'
		               dic_emenda["id"] =  str(emenda.cod_emenda)
			       dic_emenda['title'] = 'Emenda ' +  emenda.des_tipo_emenda + ' nº ' + str(emenda.num_emenda) + ' ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			       dic_emenda['description'] = emenda.txt_ementa
			       dic_emenda['materia_id'] = str(ordem.cod_materia)
		               autores = self.context.zsql.autoria_emenda_obter_zsql(cod_emenda=emenda.cod_emenda, ind_excluido=0)
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
				   lista_autor.append(dic_autor)
		               dic_emenda["autoria"] = lista_autor
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(emenda.cod_emenda) + "_emenda.pdf"
			       if hasattr(self.context.sapl_documentos.emenda, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/emenda/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_emenda['file'] = lst_arquivo
		               lst_emendas.append(dic_emenda)
		               # RESULTADO DE VOTAÇÃO DA EMENDA
		               dic_emenda["resultado_votacao"] = []
		               lst_resultado = []
		               dic_resultado = {}
	 		       # totalização de votos
			       for votacao in self.context.zsql.votacao_ordem_dia_obter_zsql(cod_emenda=emenda.cod_emenda, cod_sessao_plen=ordem.cod_sessao_plen, ind_excluido=0):
			           dic_resultado["votacao_id"] = str(votacao.cod_votacao)
				   if votacao.tip_votacao == 1 or votacao.tip_votacao == 2:
				      if votacao.num_votos_sim == 0:
				         votos_favoraveis = '0'
				      elif votacao.num_votos_sim == 1:
				         votos_favoraveis =  str(votacao.num_votos_sim)
				      elif votacao.num_votos_sim > 1:
				         votos_favoraveis = str(votacao.num_votos_sim)
				      if votacao.num_votos_nao == 0:
				         votos_contrarios = '0'
				      elif votacao.num_votos_nao == 1:
				         votos_contrarios = str(votacao.num_votos_nao)
				      elif votacao.num_votos_nao > 1:
				         votos_contrarios = str(votacao.num_votos_nao)
				      if votacao.num_abstencao == 0:
				         abstencoes = '0'
				      elif votacao.num_abstencao == 1:
				         abstencoes = str(votacao.num_abstencao)
				      elif votacao.num_abstencao > 1:
				         abstencoes =  str(votacao.num_abstencao)
				      dic_resultado["favoravel"] = votos_favoraveis
				      dic_resultado["contrario"] = votos_contrarios
				      dic_resultado["abstencao"] = abstencoes
				   if votacao.tip_resultado_votacao:
				      resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
				      for i in resultado:
				          nom_resultado= i.nom_resultado
				          dic_resultado["resultado_title"] = nom_resultado
				          dic_resultado["resultado_id"] = str(votacao.tip_resultado_votacao)
				   lst_resultado.append(dic_resultado)
				   dic_emenda["resultado_votacao"] = lst_resultado
				   # votação nominal
				   if votacao.tip_votacao == 2:
				      dic_emenda["resultado_votacao_nominal"] = []
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
				          dic_voto['partido'] = ''
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
				      dic_emenda["resultado_votacao_nominal"].append(dic_nominal)
				      
		           dic_votacao["emendas"] = lst_emendas

		           # SUBSTITUTIVOS
		           lst_substitutivos=[]
		           for substitutivo in self.context.zsql.substitutivo_obter_zsql(cod_materia=ordem.cod_materia, ind_excluido=0):
		               dic_substitutivo = {}
		               dic_substitutivo["@id"] = portal_url + '/@@substitutivo?id=' + str(substitutivo.cod_substitutivo)
		               dic_substitutivo["@type"] =  'Substitutivo'
		               dic_substitutivo["id"] =  str(substitutivo.cod_substitutivo)
			       dic_substitutivo['title'] = 'Substitutivo' +  ' nº ' + str(substitutivo.num_substitutivo) + ' ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			       dic_substitutivo['description'] = substitutivo.txt_ementa
			       dic_substitutivo['materia_id'] = str(ordem.cod_materia)
		               autores = self.context.zsql.autoria_substitutivo_obter_zsql(cod_emenda=substitutivo.cod_substitutivo, ind_excluido=0)
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
				   lista_autor.append(dic_autor)
		               dic_substitutivo["autoria"] = lista_autor
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
			       if hasattr(self.context.sapl_documentos.substitutivo, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/substitutivo/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_substitutivo['file'] = lst_arquivo
		               lst_substitutivos.append(dic_substitutivo)
		               # RESULTADO DE VOTAÇÃO DO SUBSTITUTITVO
		               dic_substitutivo["resultado_votacao"] = []
		               lst_resultado = []
		               dic_resultado = {}
	 		       # totalização de votos
			       for votacao in self.context.zsql.votacao_ordem_dia_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo, cod_sessao_plen=ordem.cod_sessao_plen, ind_excluido=0):
			           dic_resultado["votacao_id"] = str(votacao.cod_votacao)
				   if votacao.tip_votacao == 1 or votacao.tip_votacao == 2:
				      if votacao.num_votos_sim == 0:
				         votos_favoraveis = '0'
				      elif votacao.num_votos_sim == 1:
				         votos_favoraveis =  str(votacao.num_votos_sim)
				      elif votacao.num_votos_sim > 1:
				         votos_favoraveis = str(votacao.num_votos_sim)
				      if votacao.num_votos_nao == 0:
				         votos_contrarios = '0'
				      elif votacao.num_votos_nao == 1:
				         votos_contrarios = str(votacao.num_votos_nao)
				      elif votacao.num_votos_nao > 1:
				         votos_contrarios = str(votacao.num_votos_nao)
				      if votacao.num_abstencao == 0:
				         abstencoes = '0'
				      elif votacao.num_abstencao == 1:
				         abstencoes = str(votacao.num_abstencao)
				      elif votacao.num_abstencao > 1:
				         abstencoes =  str(votacao.num_abstencao)
				      dic_resultado["favoravel"] = votos_favoraveis
				      dic_resultado["contrario"] = votos_contrarios
				      dic_resultado["abstencao"] = abstencoes
				   if votacao.tip_resultado_votacao:
				      resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
				      for i in resultado:
				          nom_resultado= i.nom_resultado
				          dic_resultado["resultado_title"] = nom_resultado
				          dic_resultado["resultado_id"] = str(votacao.tip_resultado_votacao)
				   lst_resultado.append(dic_resultado)
				   dic_substitutivo["resultado_votacao"] = lst_resultado
				   # votação nominal
				   if votacao.tip_votacao == 2:
				      dic_substitutivo["resultado_votacao_nominal"] = []
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
				          dic_voto['partido'] = ''
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
				      dic_substitutivo["resultado_votacao_nominal"].append(dic_nominal)
			   dic_votacao["substitutivos"] = lst_substitutivos

		           # PARECERES
		           lst_pareceres = []
		           for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=ordem.cod_materia):
		               comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao)[0]
		               relator = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
		               dic_parecer = {}
		               dic_parecer["@id"] = portal_url + '/@@parecer?id=' + str(parecer.cod_relatoria)
		               dic_parecer["@type"] =  'Parecer'
		               dic_parecer["id"] =  str(parecer.cod_relatoria)
			       dic_parecer['title'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
			       dic_parecer['description'] = ''
		               if parecer.tip_conclusao == 'F':
		                  dic_parecer['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', FAVORÁVEL ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
		               elif parecer.tip_conclusao == 'C':
		                  dic_parecer['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', CONTRÁRIO ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			       dic_parecer['materia_id'] = str(ordem.cod_materia)
		               lista_autor = []
		               dic_autor = {}
			       dic_autor["@id"] = portal_url + '/@@comissao?id=' + str(comissao.cod_comissao)
			       dic_autor['@type'] = 'Comissão'
			       dic_autor['description'] = comissao.nom_comissao
			       dic_autor['id'] = comissao.cod_comissao
			       dic_autor['title'] = comissao.sgl_comissao
		               lista_autor.append(dic_autor)
		               dic_parecer["autoria"] = lista_autor
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(parecer.cod_relatoria) + "_parecer.pdf"
			       if hasattr(self.context.sapl_documentos.parecer_comissao, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/parecer_comissao/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_parecer['file'] = lst_arquivo
		               if parecer.tip_fim_relatoria != None:
		                  resultado = self.context.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=parecer.tip_fim_relatoria)[0]
		                  if resultado.des_fim_relatoria != 'Rejeitado':
		                     lst_pareceres.append(dic_parecer)
			   dic_votacao["pareceres"] = lst_pareceres

		           # RESULTADO DE VOTAÇÃO DA MATÉRIA
		           dic_votacao["resultado_votacao"] = []
		           lst_resultado = []
		           dic_resultado = {}
	 		   # totalização de votos
			   for votacao in self.context.zsql.votacao_ordem_dia_obter_zsql(cod_materia=ordem.cod_materia, cod_sessao_plen=ordem.cod_sessao_plen, ind_excluido=0):
			       dic_resultado["votacao_id"] = str(votacao.cod_votacao)
			       if votacao.tip_votacao == 1 or votacao.tip_votacao == 2:
				  if votacao.num_votos_sim == 0:
				     votos_favoraveis = '0'
				  elif votacao.num_votos_sim == 1:
				     votos_favoraveis =  str(votacao.num_votos_sim)
				  elif votacao.num_votos_sim > 1:
				     votos_favoraveis = str(votacao.num_votos_sim)
				  if votacao.num_votos_nao == 0:
				     votos_contrarios = '0'
				  elif votacao.num_votos_nao == 1:
				     votos_contrarios = str(votacao.num_votos_nao)
				  elif votacao.num_votos_nao > 1:
				     votos_contrarios = str(votacao.num_votos_nao)
				  if votacao.num_abstencao == 0:
				     abstencoes = '0'
				  elif votacao.num_abstencao == 1:
				     abstencoes = str(votacao.num_abstencao)
				  elif votacao.num_abstencao > 1:
				     abstencoes =  str(votacao.num_abstencao)
				  dic_resultado["favoravel"] = votos_favoraveis
				  dic_resultado["contrario"] = votos_contrarios
				  dic_resultado["abstencao"] = abstencoes
			       if votacao.tip_resultado_votacao:
				  resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
				  for i in resultado:
				      nom_resultado= i.nom_resultado
				      dic_resultado["resultado_title"] = nom_resultado
				      dic_resultado["resultado_id"] = str(votacao.tip_resultado_votacao)
			       lst_resultado.append(dic_resultado)
			       dic_votacao["resultado_votacao"] = lst_resultado
			       # votação nominal
			       if votacao.tip_votacao == 2:
				  dic_votacao["resultado_votacao_nominal"] = []
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
				      dic_voto['partido'] = ''
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
				  dic_votacao["resultado_votacao_nominal"].append(dic_nominal)
				  
			          dic_resultado["favoravel"] = len(lst_sim)
			          dic_resultado["contrario"] = len(lst_nao)
			          dic_resultado["abstencao"] = len(lst_abstencao)
			          dic_resultado["ausente"] = len(lst_ausente)
			          dic_resultado["presidencia"] = len(lst_presidencia)

			   lst_votacao.append(dic_votacao)
			   
		    dic_od['items'] = lst_votacao
		    
		    dic["ordem_dia"].append(dic_od)
		    
		    # MATERIAS DO EXPEDIENTE
		    lst_expediente = []
		    for expediente in self.context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, ind_excluido=0):
		         dic_expediente = {}
			 dic_expediente["cod_sessao_plen"] = str(expediente.cod_sessao_plen)
			 dic_expediente['data_sessao'] = DateTime(expediente.dat_ordem).strftime("%Y-%m-%d")
			 dic_expediente["cod_ordem"] = str(expediente.cod_ordem)
			 dic_expediente["numero_ordem"] = str(expediente.num_ordem)
			 dic_expediente["turno"] = ''
			 dic_expediente["turno_id"] = ''
			 #if expediente.tip_turno != None:
			 #   for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=expediente.tip_turno):
			 #       dic_expediente["turno"] = turno.des_turno
			 #       dic_expediente["turno_id"] = str(turno.cod_turno)
			 dic_expediente["tipo_votacao_id"] = str(expediente.tip_votacao)
			 dic_expediente["tipo_votacao"] = ''
			 for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=expediente.tip_votacao):
			     dic_expediente["tipo_votacao"] = tip_votacao.des_tipo_votacao
			 dic_expediente["quorum"]=""
			 for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=expediente.tip_quorum):
			     dic_expediente["quorum"] = quorum.des_quorum
			     dic_expediente["quorum_id"] = str(quorum.cod_quorum)
			     
		         if expediente.cod_materia != None:
   			     materia = self.context.zsql.materia_obter_zsql(cod_materia=expediente.cod_materia)[0]
		             dic_expediente["@id"] = portal_url + '/@@materia?id=' + str(expediente.cod_materia)
		             dic_expediente["@type"] = 'Matéria'
			     dic_expediente['id'] = str(expediente.cod_materia)
			     dic_expediente["title"] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			     dic_expediente["description"] = materia.txt_ementa
			     lst_arquivo = []
			     dic_arquivo = {}	    
		  	     arquivo = str(expediente.cod_materia) + "_texto_integral.pdf"
			     if hasattr(self.context.sapl_documentos.materia, arquivo):
			        dic_arquivo['content-type'] = 'application/pdf'
			        dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/' + arquivo
			        dic_arquivo['filename'] = arquivo
			        dic_arquivo['size'] = ''
			        lst_arquivo.append(dic_arquivo)
		             dic_expediente['file'] = lst_arquivo
			     autores = self.context.zsql.autoria_obter_zsql(cod_materia=expediente.cod_materia)
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
			       dic_expediente["autoria"] = lista_autor
		               # RESULTADO DE VOTAÇÃO DA MATÉRIA
		               dic_expediente["resultado_votacao"] = []
		               lst_resultado = []
	 		       # totalização de votos
			       for votacao in self.context.zsql.votacao_expediente_materia_obter_zsql(cod_materia=expediente.cod_materia, cod_sessao_plen=item.cod_sessao_plen, ind_excluido=0):
			         if votacao.tip_resultado_votacao:
		                   dic_resultado = {}
			           dic_resultado["votacao_id"] = str(votacao.cod_votacao)
			           if votacao.tip_votacao == 1 or votacao.tip_votacao == 2:
				      if votacao.num_votos_sim == 0:
				         votos_favoraveis = '0'
				      elif votacao.num_votos_sim == 1:
				         votos_favoraveis =  str(votacao.num_votos_sim)
				      elif votacao.num_votos_sim > 1:
				         votos_favoraveis = str(votacao.num_votos_sim)
				      if votacao.num_votos_nao == 0:
				         votos_contrarios = '0'
				      elif votacao.num_votos_nao == 1:
				         votos_contrarios = str(votacao.num_votos_nao)
				      elif votacao.num_votos_nao > 1:
				         votos_contrarios = str(votacao.num_votos_nao)
				      if votacao.num_abstencao == 0:
				         abstencoes = '0'
				      elif votacao.num_abstencao == 1:
				         abstencoes = str(votacao.num_abstencao)
				      elif votacao.num_abstencao > 1:
				         abstencoes =  str(votacao.num_abstencao)
				      dic_resultado["favoravel"] = votos_favoraveis
				      dic_resultado["contrario"] = votos_contrarios
				      dic_resultado["abstencao"] = abstencoes
			           if votacao.tip_resultado_votacao:
				      resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
				      for i in resultado:
				          nom_resultado= i.nom_resultado
				          dic_resultado["resultado_title"] = nom_resultado
				          dic_resultado["resultado_id"] = str(votacao.tip_resultado_votacao)
			              lst_resultado.append(dic_resultado)
			           dic_expediente["resultado_votacao"] = lst_resultado
			           # votação nominal
			           if votacao.tip_votacao == 2:
				      dic_expediente["resultado_votacao_nominal"] = []
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
				          dic_voto['partido'] = ''
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
				      dic_expediente["resultado_votacao_nominal"].append(dic_nominal)
		           
		         elif expediente.cod_parecer != None:
                            for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=ordem.cod_materia):
		               comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao)[0]
		               relator = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
		               dic_expediente["@id"] = portal_url + '/@@parecer?id=' + str(expediente.cod_parecer)
		               dic_expediente["@type"] = 'Parecer'
		               dic_expediente['id'] = str(expediente.cod_parecer)
                               dic_expediente['title'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
		               if parecer.tip_conclusao == 'F':
		                  dic_parecer['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', FAVORÁVEL ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
		               elif parecer.tip_conclusao == 'C':
		                  dic_parecer['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', CONTRÁRIO ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(parecer.cod_relatoria) + "_parecer.pdf"
			       if hasattr(self.context.sapl_documentos.parecer_comissao, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/parecer_comissao/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_expediente['file'] = lst_arquivo
		               lista_autor = []
		               dic_autor = {}
			       dic_autor["@id"] = portal_url + '/@@comissao?id=' + str(comissao.cod_comissao)
			       dic_autor['@type'] = 'Comissão'
			       dic_autor['description'] = comissao.nom_comissao
			       dic_autor['id'] = comissao.cod_comissao
			       dic_autor['title'] = comissao.sgl_comissao
		               lista_autor.append(dic_autor)
		               dic_expediente["autoria"] = lista_autor

		         lst_expediente.append(dic_expediente)
		         
		    dic["expediente"] = lst_expediente

		    # LEITURA DE MATERIAS
		    lst_leitura = []
		    for leitura in self.context.zsql.materia_apresentada_sessao_obter_zsql(cod_sessao_plen=item.cod_sessao_plen, ind_excluido=0):
		         dic_leitura = {}
			 dic_leitura["cod_sessao_plen"] = str(leitura.cod_sessao_plen)
			 dic_leitura['data_sessao'] = DateTime(leitura.dat_ordem).strftime("%Y-%m-%d")
			 dic_leitura["cod_ordem"] = str(leitura.cod_ordem)
			 dic_leitura["numero_ordem"] = str(leitura.num_ordem)
			 # MATERIAS
		         if leitura.cod_materia != None:
   			     materia = self.context.zsql.materia_obter_zsql(cod_materia=leitura.cod_materia)[0]
		             dic_leitura["@id"] = portal_url + '/@@materia?id=' + str(leitura.cod_materia)
		             dic_leitura["@type"] = 'Matéria'
			     dic_leitura['id'] = str(leitura.cod_materia)
			     dic_leitura["title"] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			     dic_leitura["description"] = materia.txt_ementa
			     lst_arquivo = []
			     dic_arquivo = {}	    
		  	     arquivo = str(leitura.cod_materia) + "_texto_integral.pdf"
			     if hasattr(self.context.sapl_documentos.materia, arquivo):
			        dic_arquivo['content-type'] = 'application/pdf'
			        dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/' + arquivo
			        dic_arquivo['filename'] = arquivo
			        dic_arquivo['size'] = ''
			        lst_arquivo.append(dic_arquivo)
		             dic_leitura['file'] = lst_arquivo
			     autores = self.context.zsql.autoria_obter_zsql(cod_materia=leitura.cod_materia)
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
			     dic_leitura["autoria"] = lista_autor
			     
                         # EMENDAS
                         elif leitura.cod_emenda != None:
		           for emenda in self.context.zsql.emenda_obter_zsql(cod_materia=letura.cod_emenda, ind_excluido=0, exc_pauta=0):
		               dic_leitura["@id"] = portal_url + '/@@emenda?id=' + str(emenda.cod_emenda)
		               dic_leitura["@type"] =  'Emenda'
		               dic_leitura["id"] =  str(emenda.cod_emenda)
			       dic_leitura['title'] = 'Emenda ' +  emenda.des_tipo_emenda + ' nº ' + str(emenda.num_emenda) + ' ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			       dic_leitura['description'] = emenda.txt_ementa
			       dic_leitura['materia_id'] = str(ordem.cod_materia)
		               autores = self.context.zsql.autoria_emenda_obter_zsql(cod_emenda=emenda.cod_emenda, ind_excluido=0)
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
				   lista_autor.append(dic_autor)
		               dic_leitura["autoria"] = lista_autor
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(emenda.cod_emenda) + "_emenda.pdf"
			       if hasattr(self.context.sapl_documentos.emenda, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/emenda/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_leitura['file'] = lst_arquivo
		               
                         # SUBSTITUTIVOS
                         elif leitura.cod_substitutivo != None:
		           for substitutivo in self.context.zsql.substitutivo_obter_zsql(cod_materia=leiura.cod_substitutivo, ind_excluido=0):
		               dic_leitura["@id"] = portal_url + '/@@substitutivo?id=' + str(emenda.cod_emenda)
		               dic_leitura["@type"] =  'Substitutivo'
		               dic_leitura["id"] =  str(substitutivo.cod_substitutivo)
			       dic_leitura['title'] = 'Substitutivo' +  ' nº ' + str(substitutivo.num_substitutivo) + ' ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			       dic_leitura['description'] = substitutivo.txt_ementa
			       dic_leitura['materia_id'] = str(ordem.cod_materia)
		               autores = self.context.zsql.autoria_substitutivo_obter_zsql(cod_emenda=substitutivo.cod_substitutivo, ind_excluido=0)
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
				   lista_autor.append(dic_autor)
		               dic_leitura["autoria"] = lista_autor
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
			       if hasattr(self.context.sapl_documentos.substitutivo, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/substitutivo/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_leitura['file'] = lst_arquivo
		               
                         #DOCUMENTOS ACESSÓRIOS
                         elif leitura.cod_doc_acessorio != None:
                            for doc_acessorio in self.context.zsql.documento_acessorio_obter_zsql(cod_documento=leitura.cod_doc_acessorio, ind_excluido=0):
		               dic_leitura["@id"] = portal_url + '/@@documento_acessorio?id=' + str(leitura.cod_doc_acessorio)
		               dic_leitura["@type"] = 'Documento Acessório'
		               dic_leitura['id'] = str(doc_acessorio.cod_documento)
			       dic_leitura['title'] = doc_acessorio.nom_documento
			       dic_leitura['description'] = doc_acessorio.txt_ementa
			       dic_leitura['materia_id'] = str(doc_acessorio.cod_materia)
			       dic_leitura['autoria'] = []
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(doc_acessorio.cod_documento) + ".pdf"
			       if hasattr(self.context.sapl_documentos.materia, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_leitura['file'] = lst_arquivo
			       
                         # DOCUMENTOS ADMINISTRATIVOS
                         elif leitura.cod_documento != None:
                            for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=leitura.cod_documento, ind_excluido=0):
		               dic_leitura["@id"] = portal_url + '/@@documento_administrativo?id=' + str(leitura.cod_documento)
		               dic_leitura["@type"] = 'Documento Administrativo'
		               dic_leitura['id'] = str(documento.cod_documento)
			       dic_leitura['title'] = documento.des_tipo_documento + ' ' + str(documento.num_documento) + str(documento.ano_documento)
			       dic_leitura['description'] = documento.txt_assunto
			       dic_leitura['autoria'] = []
			       lst_arquivo = []
			       dic_arquivo = {}
			       arquivo = str(documento.cod_documento) + ".pdf"
			       if documento.ind_publico == 1: 
			          if hasattr(self.context.sapl_documentos.administrativo, arquivo):
			             dic_arquivo['content-type'] = 'application/pdf'
			             dic_arquivo['download'] = portal_url + '/sapl_documentos/administrativo/' + arquivo
			             dic_arquivo['filename'] = arquivo
			             dic_arquivo['size'] = ''
			             lst_arquivo.append(dic_arquivo)
		               dic_leitura['file'] = lst_arquivo

                         # PARECERES
		         elif leitura.cod_parecer != None:
                            for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=leiura.cod_parecer):
		               comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao)[0]
		               relator = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
		               dic_leitura["@id"] = portal_url + '/@@parecer?id=' + str(leitura.cod_parecer)
		               dic_leitura["@type"] = 'Parecer'
		               dic_leitura['id'] = str(leitura.cod_parecer)
                               dic_leitura['title'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
		               if parecer.tip_conclusao == 'F':
		                  dic_leitura['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', FAVORÁVEL ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
		               elif parecer.tip_conclusao == 'C':
		                  dic_leitura['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', CONTRÁRIO ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
			       lst_arquivo = []
			       dic_arquivo = {}	    
			       arquivo = str(parecer.cod_relatoria) + "_parecer.pdf"
			       if hasattr(self.context.sapl_documentos.parecer_comissao, arquivo):
			          dic_arquivo['content-type'] = 'application/pdf'
			          dic_arquivo['download'] = portal_url + '/sapl_documentos/parecer_comissao/' + arquivo
			          dic_arquivo['filename'] = arquivo
			          dic_arquivo['size'] = ''
			          lst_arquivo.append(dic_arquivo)
		               dic_leitura['file'] = lst_arquivo
		               lista_autor = []
		               dic_autor = {}
			       dic_autor["@id"] = portal_url + '/@@comissao?id=' + str(comissao.cod_comissao)
			       dic_autor['@type'] = 'Comissão'
			       dic_autor['description'] = comissao.nom_comissao
			       dic_autor['id'] = comissao.cod_comissao
			       dic_autor['title'] = comissao.sgl_comissao
		               lista_autor.append(dic_autor)
		               dic_leitura["autoria"] = lista_autor
		
		         lst_leitura.append(dic_leitura)
		         
		    dic["leitura"] = lst_leitura
		
	serialized = json.dumps(dic, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
