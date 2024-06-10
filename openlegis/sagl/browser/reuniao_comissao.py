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

class ReunioesComissao(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('reunioes_comissao')
        
    def render(self):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%Y-%m-%d")
	lista = []
	for item in self.context.zsql.reuniao_comissao_obter_zsql(ind_excluido=0):
	    comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=item.cod_comissao)[0]
            dic = {}
    	    dic['@id'] = portal_url + '/@@reuniao_comissao?id=' + str(item.cod_reuniao)
	    dic['@type'] = 'Reunião de Comissão'
	    dic['id'] = str(item.cod_reuniao)
	    dic['start'] = DateTime(item.dat_inicio_reuniao, datefmt='international').strftime("%Y-%m-%d")
	    dic['ano'] = DateTime(item.dat_inicio_reuniao).strftime("%Y")
	    dic['title'] = str(item.num_reuniao) + 'ª Reunião ' + item.des_tipo_reuniao
            dic['description'] = str(item.num_reuniao) + 'ª Reunião ' + item.des_tipo_reuniao + ' de ' + str(item.dat_inicio_reuniao)
	    dic['hora_abertura'] = item.hr_inicio_reuniao
	    dic['hora_encerramento'] = item.hr_fim_reuniao
            dic['tipo'] = item.des_tipo_reuniao
	    dic['tema'] = item.txt_tema
	    dic['comissao'] = comissao.nom_comissao
	    dic['comissao_sgl'] = comissao.sgl_comissao
	    dic['comissao_id'] = comissao.cod_comissao
	    
	    lst_pauta = []
	    dic_pauta = {}	    
	    pauta = str(item.cod_reuniao) + "_pauta.pdf"
	    if hasattr(self.context.sapl_documentos.reuniao_comissao, pauta):
	       dic_pauta['content-type'] = 'application/pdf'
	       dic_pauta['download'] = portal_url + '/sapl_documentos/reuniao_comissao/' + pauta
	       dic_pauta['filename'] = pauta
	       dic_pauta['size'] = ''
	       lst_pauta.append(dic_pauta)
            dic['arquivo_pauta'] = lst_pauta

	    lst_ata = []
	    dic_ata = {}
	    ata = str(item.cod_reuniao) + "_ata.pdf"
	    if hasattr(self.context.sapl_documentos.reuniao_comissao, ata):
	       dic_ata['content-type'] = 'application/pdf'
	       dic_ata['download'] = portal_url + '/sapl_documentos/reuniao_comissao/' + ata
	       dic_ata['filename'] = ata
	       dic_ata['size'] = ''
	       lst_ata.append(dic_ata)
            dic['arquivo_ata'] = lst_ata

            lista.append(dic)
            
        lista.sort(key=lambda dic: dic['start'], reverse=True)
        
       	dic_resultado = {}
    	dic_resultado['@id'] = portal_url + '/@@reunioes_comissao'
       	dic_resultado['@type'] = 'Reuniões de Comissão'
       	dic_resultado['description'] = 'Lista de Reuniões de Comissão'
        dic_resultado['items'] = lista
		
	serialized = json.dumps(dic_resultado, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())


class ReuniaoComissao(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('reuniao_comissao')
        
    def render(self, id):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        imagens = portal.sapl_documentos.parlamentar.fotos.objectIds()
	data_atual = DateTime().strftime("%Y-%m-%d")

	for item in self.context.zsql.reuniao_comissao_obter_zsql(cod_reuniao=id, ind_excluido=0):
	    comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=item.cod_comissao)[0]
            dic = {}
    	    dic['@id'] = portal_url + '/@@reuniao_comissao?id=' + str(item.cod_reuniao)
	    dic['@type'] = 'Reunião de Comissão'
	    dic['id'] = str(item.cod_reuniao)
	    dic['start'] = DateTime(item.dat_inicio_reuniao, datefmt='international').strftime("%Y-%m-%d")
	    dic['ano'] = DateTime(item.dat_inicio_reuniao, datefmt='international').strftime("%Y")
	    dic['title'] = str(item.num_reuniao) + 'ª Reunião ' + item.des_tipo_reuniao
            dic['description'] = str(item.num_reuniao) + 'ª Reunião ' + item.des_tipo_reuniao + ' de ' + str(item.dat_inicio_reuniao)
	    dic['hora_abertura'] = item.hr_inicio_reuniao
	    dic['hora_encerramento'] = item.hr_fim_reuniao
            dic['tipo'] = item.des_tipo_reuniao
	    dic['tema'] = item.txt_tema
	    dic['comissao'] = comissao.nom_comissao
	    dic['comissao_sgl'] = comissao.sgl_comissao
	    dic['comissao_id'] = comissao.cod_comissao
	    
	    lst_pauta = []
	    dic_pauta = {}	    
	    pauta = str(item.cod_reuniao) + "_pauta.pdf"
	    if hasattr(self.context.sapl_documentos.reuniao_comissao, pauta):
	       dic_pauta['content-type'] = 'application/pdf'
	       dic_pauta['download'] = portal_url + '/sapl_documentos/reuniao_comissao/' + pauta
	       dic_pauta['filename'] = pauta
	       dic_pauta['size'] = ''
	       lst_pauta.append(dic_pauta)
            dic['arquivo_pauta'] = lst_pauta

	    lst_ata = []
	    dic_ata = {}
	    ata = str(item.cod_reuniao) + "_ata.pdf"
	    if hasattr(self.context.sapl_documentos.reuniao_comissao, ata):
	       dic_ata['content-type'] = 'application/pdf'
	       dic_ata['download'] = portal_url + '/sapl_documentos/reuniao_comissao/' + ata
	       dic_ata['filename'] = ata
	       dic_ata['size'] = ''
	       lst_ata.append(dic_ata)
            dic['arquivo_ata'] = lst_ata

            if id != '':
            
               # CHAMADA DA REUNIÃO
               dic["chamada"] = []
               dic_presenca = {}
               lst_presenca = []
               dic_ausencia = {}
               lst_ausencia = []
               for periodo in self.context.zsql.periodo_comp_comissao_obter_zsql(data=DateTime(item.dat_inicio_reuniao_ord), ind_excluido=0):
                   for membro in self.context.zsql.composicao_comissao_obter_zsql(cod_comissao=item.cod_comissao, cod_periodo_comp=periodo.cod_periodo_comp, ind_excluido=0):
                       dic_composicao = {}
		       dic_composicao['@type'] = 'Vereador'
		       dic_composicao['@id'] = portal_url + '/@@vereador?id=' + str(membro.cod_parlamentar)
                       dic_composicao["description"] = membro.nom_completo
                       dic_composicao["title"] = membro.nom_parlamentar
                       dic_composicao["cargo_comissao"] = membro.des_cargo
                       dic_composicao["id"] = str(membro.cod_parlamentar)
		       lst_partido = []
		       for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=membro.cod_parlamentar):    
		           dic_partido = {}
		           for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
			       dic_partido['token'] = partido.sgl_partido
			       dic_partido['title'] = partido.nom_partido
		           if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
			       lst_partido.append(dic_partido)
	               dic_composicao['partido'] = lst_partido
                       if self.context.zsql.reuniao_comissao_presenca_obter_zsql(cod_reuniao=item.cod_reuniao, cod_parlamentar=membro.cod_parlamentar, ind_excluido=0):
                          for presenca in self.context.zsql.reuniao_comissao_presenca_obter_zsql(cod_reuniao=item.cod_reuniao, cod_parlamentar=membro.cod_parlamentar, ind_excluido=0):
                              lst_presenca.append(dic_composicao)
                       else:
                          lst_ausencia.append(dic_composicao)
	       dic_presenca["qtde_presenca"] = len(lst_presenca)
	       dic_presenca["presenca"] = lst_presenca
	       dic_presenca["qtde_ausencia"] = len(lst_ausencia)
	       dic_presenca["ausencia"] = lst_ausencia
	       dic["chamada"].append(dic_presenca)

               # MATÉRIAS DA PAUTA
               lst_pauta = []
               for x in self.context.zsql.reuniao_comissao_pauta_obter_zsql(cod_reuniao=item.cod_reuniao, ind_excluido=0):
                   # seleciona os detalhes dos itens da pauta
                   dic_pauta = {} 
                   dic_pauta["num_ordem"] = str(x.num_ordem)
                   dic_pauta["description"] =  escape(x.txt_observacao)    
           
                   if x.cod_materia != None:   
                      dic_pauta["@id"] = portal_url + '/@@materia?id=' + str(x.cod_materia)
                      dic_pauta["@type"] = 'Matéria'
                      materia = self.context.zsql.materia_obter_zsql(cod_materia=x.cod_materia)[0]   
		      dic_pauta["title"] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                      dic_pauta["id"] = x.cod_materia
                      dic_pauta["pauta_id"] = x.cod_item
                      dic_pauta["autoria"] = []
		      lst_arquivo = []
		      dic_arquivo = {}	    
		      arquivo = str(x.cod_materia) + "_texto_integral.pdf"
		      if hasattr(self.context.sapl_documentos.materia, arquivo):
		         dic_arquivo['content-type'] = 'application/pdf'
			 dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/' + arquivo
			 dic_arquivo['filename'] = arquivo
			 dic_arquivo['size'] = ''
			 lst_arquivo.append(dic_arquivo)
		      dic_pauta['file'] = lst_arquivo
		      autores = self.context.zsql.autoria_obter_zsql(cod_materia=x.cod_materia)
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
		      dic_pauta["autoria"] = lista_autor

                      lst_relatoria = []
                      if x.cod_relator != '' and x.cod_relator != None:
                         for relator in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=x.cod_relator):
			     dic_relatoria = {}
			     dic_relatoria["@id"] = portal_url + '/@@vereador?id=' + str(relator.cod_parlamentar)
			     dic_relatoria['@type'] = 'Vereador'
                             dic_relatoria["id"] = str(relator.cod_parlamentar)
                             dic_relatoria["title"] = relator.nom_parlamentar
			     lst_relatoria.append(dic_relatoria)
		      else:
                         for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=x.cod_materia, cod_comissao=item.cod_comissao, ind_excluido=0):
			     dic_relatoria = {}
  	                     for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar):
			         dic_relatoria["@id"] = portal_url + '/@@vereador?id=' + str(parlamentar.cod_parlamentar)
			         dic_relatoria['@type'] = 'Vereador'
                                 dic_relatoria["id"] = str(parlamentar.cod_parlamentar)
                                 dic_relatoria["title"] = parlamentar.nom_parlamentar
			         lst_relatoria.append(dic_relatoria)
                         
                      dic_pauta["relatoria"] = lst_relatoria

                      lst_parecer = []
                      for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=x.cod_materia, cod_comissao=item.cod_comissao, ind_excluido=0):
                          dic_parecer = {}
                          dic_parecer['@id'] = portal_url + '/@@parecer?id=' + str(parecer.cod_relatoria)
                          dic_parecer['@type'] = 'Parecer'
                          dic_parecer['id'] = str(parecer.cod_relatoria)
                          dic_parecer['title'] = 'Parecer ' + comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
                          if parecer.tip_conclusao == 'F':
                            dic_parecer['description'] = 'Favorável'
                          elif parecer.tip_conclusao == 'C':
                            dic_parecer['description'] = 'Contrário'
		          lst_arquivo = []
		          dic_arquivo = {}	    
		          arquivo = str(parecer.cod_relatoria) + "_parecer.pdf"
		          if hasattr(self.context.sapl_documentos.parecer_comissao, arquivo):
		             dic_arquivo['content-type'] = 'application/pdf'
			     dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/' + arquivo
			     dic_arquivo['filename'] = arquivo
			     dic_arquivo['size'] = ''
			     lst_arquivo.append(dic_arquivo)
		          dic_parecer['file'] = lst_arquivo
			  lst_parecer.append(dic_parecer)
                      dic_pauta["parecer"] = lst_parecer


                      dic_pauta["resultado_votacao"] = ''
                      if x.tip_resultado_votacao != None:
                         for resultado in self.context.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=x.tip_resultado_votacao, ind_excluido=0):
                             dic_pauta["resultado_votacao"] = resultado.des_fim_relatoria

                   lst_pauta.append(dic_pauta)

               dic["pauta"] = lst_pauta

	serialized = json.dumps(dic, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
