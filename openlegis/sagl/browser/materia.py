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
import MySQLdb

class auxiliarMateria(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('auxiliar-materias')

    def render(self, description=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        
        db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="openlegis") 
        cur = db.cursor()
        cur.execute("SELECT DISTINCT ano_ident_basica FROM materia_legislativa WHERE ind_excluido=0 ORDER BY ano_ident_basica")
        lst_anos = []
        for row in cur.fetchall():
            dic_anos = {}
            dic_anos['title'] = row[0]
            lst_anos.append(dic_anos)
        db.close()

        lst_tipos = []
      	for item in self.context.zsql.tipo_materia_legislativa_obter_zsql(tip_natureza='P', ind_excluido=0):
      	    dic_tipo = {}
      	    dic_tipo['title'] = item.des_tipo_materia
      	    dic_tipo['id'] = item.tip_materia
      	    lst_tipos.append(dic_tipo)
       	    
        dic_items = {}
	dic_items['@id'] =  portal_url + '/@@auxiliar-materias'
        dic_items['description'] = 'Lista de anos e tipos de matérias legislativas'
        dic_items['anos'] = lst_anos
        dic_items['tipos'] = lst_tipos

	serialized = json.dumps(dic_items, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())


class Autores(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('autores')

    def render(self, description=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        data_atual = DateTime().strftime("%d/%m/%Y")
        
        lst_autores = []
      	for item in self.context.zsql.autor_obter_zsql(des_tipo_autor=description, ind_excluido=0):
      	    vereadores_atuais = self.context.zsql.autores_obter_zsql(txt_dat_apresentacao=data_atual)
            dic_autor = {}
	    dic_autor['@type'] = 'Autor'
	    dic_autor['@id'] =  portal_url + '/@@autor?id=' + item.cod_autor
	    dic_autor['id'] = item.cod_autor
	    dic_autor['title'] = item.nom_autor_join
	    dic_autor['description'] = item.des_tipo_autor
	    if item.des_tipo_autor == 'Parlamentar':
	       for parlamentar in vereadores_atuais:
	           if item.cod_parlamentar == parlamentar.cod_parlamentar:
	              dic_autor['parlamentar_id'] = item.cod_parlamentar
                      lst_autores.append(dic_autor)
            else:
               lst_autores.append(dic_autor)
        
        dic_autores = {}
	dic_autores['@id'] =  portal_url + '/@@autores'
	dic_autores['@type'] =  'Autores'
        dic_autores['description'] = 'Lista de autores permitidos na data corrente'
        dic_autores['items'] = lst_autores

	serialized = json.dumps(dic_autores, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())


class Autor(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('autor')

    def render(self, id):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        data_atual = DateTime().strftime("%d/%m/%Y")
        
      	for item in self.context.zsql.autor_obter_zsql(cod_autor=id, ind_excluido=0):
            dic_autor = {}
	    dic_autor['@id'] =  portal_url + '/@@autor?id=' + item.cod_autor
	    dic_autor['@type'] = 'Autor'
	    dic_autor['id'] = item.cod_autor
	    dic_autor['title'] = item.nom_autor_join
	    dic_autor['description'] = item.des_tipo_autor

	serialized = json.dumps(dic_autor, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())


class Materias(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('materias')

    def render(self, tipo='', ano=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        data_atual = DateTime().strftime("%d/%m/%Y")
        ano_atual = DateTime().strftime("%Y")

        db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="openlegis") 
        cur = db.cursor()
        lst_materias = []
        if tipo != '' and ano != '':
           cur.execute('SELECT m.cod_materia, m.num_ident_basica, m.ano_ident_basica, t.des_tipo_materia, m.dat_apresentacao, m.txt_ementa FROM materia_legislativa m LEFT JOIN tipo_materia_legislativa t ON m.tip_id_basica = t.tip_materia WHERE tip_id_basica=%s AND ano_ident_basica=%s AND m.ind_excluido=0 ORDER BY DATE(m.dat_apresentacao) DESC'%(tipo,ano))
           for row in cur.fetchall():
               dic_materia = {}
               dic_materia['@id'] =  portal_url + '/@@materia?id=' + str(row[0])
	       dic_materia['@type'] = 'Matéria Legislativa'
               dic_materia['id'] = row[0]
               dic_materia['description'] = row[5]
	       dic_materia['title'] = row[3] + ' nº ' + str(row[1]) + '/' + str(row[2]) 
               dic_materia['data_apresentacao'] = str(row[4])
               autores = self.context.zsql.autoria_obter_zsql(cod_materia=row[0])
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
	       dic_materia["autoria"] = lista_autor
               lst_materias.append(dic_materia)
        db.close()

        dic_materias = {}
	dic_materias['@id'] =  portal_url + '/@@materias'
	dic_materias['@type'] = 'Listagem de Matérias'
        dic_materias['description'] = 'Lista de matérias legislativas por tipo e ano'
        dic_materias['items'] = lst_materias

	serialized = json.dumps(dic_materias, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())


class Materia(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('materia')

    def render(self, id):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        data_atual = DateTime().strftime("%d/%m/%Y")
        
      	for item in self.context.zsql.materia_obter_zsql(cod_materia=id, ind_excluido=0):
            dic_materia = {}
	    dic_materia['@type'] = 'Matéria Legislativa'
	    dic_materia['@id'] =  portal_url + '/@@materia?id=' + item.cod_materia
	    dic_materia['id'] = item.cod_materia
	    dic_materia['title'] = item.des_tipo_materia + ' nº ' + str(item.num_ident_basica) + '/' + str(item.ano_ident_basica) 
	    dic_materia['description'] = item.txt_ementa
	    dic_materia['data_apresentacao'] = DateTime(item.dat_apresentacao).strftime("%Y-%m-%d")
	    lst_arquivo = []
	    dic_arquivo = {}	    
	    arquivo = str(item.cod_materia) + "_texto_integral.pdf"
	    if hasattr(self.context.sapl_documentos.materia, arquivo):
	       dic_arquivo['content-type'] = 'application/pdf'
	       dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/' + arquivo
	       dic_arquivo['filename'] = arquivo
	       dic_arquivo['size'] = ''
	       lst_arquivo.append(dic_arquivo)
	    dic_materia['file'] = lst_arquivo
	    dic_materia['remoteUrl'] = portal_url + '/consultas/materia/pasta_digital?cod_materia=' + item.cod_materia
            autores = self.context.zsql.autoria_obter_zsql(cod_materia=item.cod_materia)
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
	    dic_materia["autoria"] = lista_autor
	    dic_materia["quorum"]=""
	    for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=item.tip_quorum):
		dic_materia["quorum"] = quorum.des_quorum
		dic_materia["quorum_id"] = str(quorum.cod_quorum)
	    dic_materia["regime_tramitacao"]=""
	    for regime in self.context.zsql.regime_tramitacao_obter_zsql(cod_regime_tramitacao=item.cod_regime_tramitacao):
		dic_materia["regime_tramitacao"] = regime.des_regime_tramitacao
		dic_materia["regime_tramitacao_id"] = str(regime.cod_regime_tramitacao)
            if item.ind_tramitacao == 1:
                dic_materia["tramitando"] = True
            else:
                dic_materia["tramitando"] = False

            lst_anexada = []
            for anexada in self.context.zsql.anexada_obter_zsql(cod_materia_principal=item.cod_materia, ind_excluido=0):
                dic_anexada = {}
                materia_anexada = self.context.zsql.materia_obter_zsql(cod_materia=anexada.cod_materia_anexada, ind_excluido = 0)[0]
	        dic_anexada['@type'] = 'Matéria Legislativa'
                dic_anexada['@id'] = portal_url + '/@@materia?id=' + materia_anexada.cod_materia
                dic_anexada['title'] = materia_anexada.des_tipo_materia + ' nº ' + str(materia_anexada.num_ident_basica) + '/' + str(materia_anexada.ano_ident_basica)
                dic_anexada['id'] = str(materia_anexada.cod_materia)
                dic_anexada['description'] = materia_anexada.txt_ementa
                dic_anexada['data_anexacao'] = DateTime(anexada.dat_anexacao).strftime("%Y-%m-%d")
                if anexada.dat_desanexacao == None or anexada.dat_desanexacao == '':
                   lst_anexada.append(dic_anexada)
	    dic_materia["anexada"] = lst_anexada

            lst_documento = []
            for documento in self.context.zsql.documento_acessorio_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
                tipo = self.context.zsql.tipo_documento_obter_zsql(tip_documento=documento.tip_documento)[0]
                dic_documento = {}
	        dic_documento['@type'] = 'Documento Acessório'
                dic_documento['@id'] = ''
                dic_documento['title'] = documento.nom_documento
                dic_documento['id'] = str(documento.cod_documento)
                dic_documento['description'] = tipo.des_tipo_documento
                dic_documento['autoria'] = documento.nom_autor_documento
                dic_documento['data'] = DateTime(documento.dat_documento).strftime("%Y-%m-%d")
	        lst_arquivo = []
	        dic_arquivo = {}	    
	        arquivo = str(documento.cod_documento) + ".pdf"
	        if hasattr(self.context.sapl_documentos.materia, arquivo):
	           dic_arquivo['content-type'] = 'application/pdf'
	           dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/' + arquivo
	           dic_arquivo['filename'] = arquivo
	           dic_arquivo['size'] = ''
	           lst_arquivo.append(dic_arquivo)
	        dic_documento['file'] = lst_arquivo
                lst_documento.append(dic_documento)
	    dic_materia["documento_acessorio"] = lst_documento
	    
            lst_emenda = []
            for emenda in self.context.zsql.emenda_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
                dic_emenda = {}
	        dic_emenda['@type'] = 'Emenda'
                dic_emenda['@id'] = ''
                dic_emenda['title'] = 'Emenda ' + emenda.des_tipo_emenda + ' nº ' + str(emenda.num_emenda)
                dic_emenda['id'] = str(emenda.cod_emenda)
                dic_emenda['description'] = emenda.txt_ementa
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
                dic_emenda['data'] = DateTime(emenda.dat_apresentacao).strftime("%Y-%m-%d")
	        lst_arquivo = []
	        arquivo = str(emenda.cod_emenda) + "_emenda.pdf"
	        if hasattr(self.context.sapl_documentos.emenda, arquivo):
	           dic_arquivo = {}	    
	           dic_arquivo['content-type'] = 'application/pdf'
	           dic_arquivo['download'] = portal_url + '/sapl_documentos/emenda/' + arquivo
	           dic_arquivo['filename'] = arquivo
	           dic_arquivo['size'] = ''
	           lst_arquivo.append(dic_arquivo)
	        dic_emenda['file'] = lst_arquivo
                lst_emenda.append(dic_emenda)
	    dic_materia["emenda"] = lst_emenda

            lst_substitutivo = []
            for substitutivo in self.context.zsql.substitutivo_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
                dic_substitutivo = {}
	        dic_substitutivo['@type'] = 'Substitutivo'
                dic_substitutivo['@id'] = ''
                dic_substitutivo['title'] = 'Substitutivo' + ' nº ' + str(substitutivo.num_substitutivo)
                dic_substitutivo['id'] = str(substitutivo.cod_substitutivo)
                dic_substitutivo['description'] = substitutivo.txt_ementa
                autores = self.context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo, ind_excluido=0)
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
                dic_substitutivo['data'] = DateTime(substitutivo.dat_apresentacao).strftime("%Y-%m-%d")
	        lst_arquivo = []
	        arquivo = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
	        if hasattr(self.context.sapl_documentos.substitutivo, arquivo):
	           dic_arquivo = {}	    
	           dic_arquivo['content-type'] = 'application/pdf'
	           dic_arquivo['download'] = portal_url + '/sapl_documentos/substitutivo/' + arquivo
	           dic_arquivo['filename'] = arquivo
	           dic_arquivo['size'] = ''
	           lst_arquivo.append(dic_arquivo)
	        dic_substitutivo['file'] = lst_arquivo
                lst_substitutivo.append(dic_substitutivo)
	    dic_materia["subsitutivo"] = lst_substitutivo

	    lst_pareceres = []
	    for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=item.cod_materia):
		comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao)[0]
		relator = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
		dic_parecer = {}
		dic_parecer["@id"] = portal_url + '/@@parecer?id=' + str(parecer.cod_relatoria)
		dic_parecer["@type"] = 'Parecer'
		dic_parecer["id"] =  str(parecer.cod_relatoria)
		dic_parecer['title'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
		dic_parecer['description'] = ''
		if parecer.tip_conclusao == 'F':
		   dic_parecer['description'] = 'Relatoria de '+ relator.nom_parlamentar + ', com voto FAVORÁVEL'
		elif parecer.tip_conclusao == 'C':
		   dic_parecer['description'] = 'Relatoria de '+ relator.nom_parlamentar + ', com voto CONTRÁRIO'
                dic_parecer['data'] = DateTime(parecer.dat_destit_relator).strftime("%Y-%m-%d")
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
                lst_pareceres.append(dic_parecer)
		dic_materia["parecer"] = lst_pareceres
	    
	    lst_tramitacao = []
	    for tramitacao in self.context.zsql.tramitacao_obter_zsql(cod_materia=item.cod_materia, ind_encaminha=1, ind_excluido=0):
		dic_tramitacao = {}
		dic_tramitacao["@type"] = 'Tramitação'
                dic_tramitacao['@id'] = ''
                dic_tramitacao['id'] = tramitacao.cod_tramitacao
                dic_tramitacao['title'] = tramitacao.des_status
                dic_tramitacao['description'] = escape(tramitacao.txt_tramitacao)
                dic_tramitacao['data'] = DateTime(tramitacao.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
                for unidade in self.context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao = tramitacao.cod_unid_tram_local):
                   dic_tramitacao['unidade_origem'] = unidade.nom_unidade_join
                for unidade in self.context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao = tramitacao.cod_unid_tram_dest):
                   dic_tramitacao['unidade_destino'] = unidade.nom_unidade_join
                if tramitacao.ind_ult_tramitacao == 1:
                   dic_tramitacao['ultima'] = True
                else:
                   dic_tramitacao['ultima'] = False
		lst_arquivo = []
		dic_arquivo = {}	    
		arquivo = str(tramitacao.cod_tramitacao) + "_tram.pdf"
		if hasattr(self.context.sapl_documentos.materia.tramitacao, arquivo):
		   dic_arquivo['content-type'] = 'application/pdf'
		   dic_arquivo['download'] = portal_url + '/sapl_documentos/materia/tramitacao/' + arquivo
		   dic_arquivo['filename'] = arquivo
		   dic_arquivo['size'] = ''
		   lst_arquivo.append(dic_arquivo)
		dic_tramitacao['file'] = lst_arquivo
		lst_tramitacao.append(dic_tramitacao)
  	    dic_materia["tramitacao"] = lst_tramitacao
	    
	    lst_votacao = []
	    for registro in self.context.zsql.votacao_materia_expediente_pesquisar_zsql(cod_materia=item.cod_materia):
		dic_votacao = {}
		lst_resultado = []
		dic_resultado = {}
	        sessao_plenaria = self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=registro.cod_sessao_plen)[0]
	        tipo_sessao = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao_plenaria.tip_sessao)[0]
	        votacao = self.context.zsql.votacao_expediente_materia_obter_zsql(cod_sessao_plen=sessao_plenaria.cod_sessao_plen, cod_materia=item.cod_materia, ind_excluido=0)[0]
		dic_votacao["@id"] = portal_url + '/@@sessao_plenaria?id=' + str(sessao_plenaria.cod_sessao_plen)
		dic_votacao["data"] = DateTime(sessao_plenaria.dat_inicio_sessao).strftime("%Y-%m-%d")
		dic_votacao["turno"] = ''
		for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=registro.tip_votacao):
		    dic_votacao["tipo_votacao"] = tip_votacao.des_tipo_votacao
	        if votacao.tip_resultado_votacao != None:
		   dic_votacao["id"] = str(votacao.cod_votacao)
		   dic_votacao["title"] = ''
		   dic_votacao["description"] = 'Expediente da ' + str(sessao_plenaria.num_sessao_plen) + 'ª Reunião ' + tipo_sessao.nom_sessao
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
			     dic_votacao["title"] = nom_resultado
			     lst_resultado.append(dic_resultado)
			 dic_votacao["apuracao"] = lst_resultado
		lst_votacao.append(dic_votacao)

	    for registro in self.context.zsql.votacao_materia_ordem_dia_pesquisar_zsql(cod_materia=item.cod_materia):
		dic_votacao = {}
		lst_resultado = []
		dic_resultado = {}
	        sessao_plenaria = self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=registro.cod_sessao_plen)[0]
	        tipo_sessao = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao_plenaria.tip_sessao)[0]
	        votacao = self.context.zsql.votacao_ordem_dia_obter_zsql(cod_sessao_plen=sessao_plenaria.cod_sessao_plen, cod_materia=item.cod_materia, ind_excluido=0)[0]
		dic_votacao["@id"] = portal_url + '/@@sessao_plenaria?id=' + str(sessao_plenaria.cod_sessao_plen)
		dic_votacao["data"] = DateTime(sessao_plenaria.dat_inicio_sessao).strftime("%Y-%m-%d")
		for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=registro.tip_votacao):
		    dic_votacao["tipo_votacao"] = tip_votacao.des_tipo_votacao
		for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=registro.tip_turno):
		    dic_votacao["turno"] = turno.des_turno
	        if votacao.tip_resultado_votacao != None:
		   dic_votacao["id"] = str(votacao.cod_votacao)
		   dic_votacao["title"] = ''
		   dic_votacao["description"] = 'Ordem do Dia da ' + str(sessao_plenaria.num_sessao_plen) + 'ª Reunião ' + tipo_sessao.nom_sessao
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
			     dic_votacao["title"] = nom_resultado
			     lst_resultado.append(dic_resultado)
			 dic_votacao["apuracao"] = lst_resultado
		      # votação nominal
		      if votacao.tip_votacao == 2:
		         dic_votacao["votos"] = []
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
			 dic_votacao["votos"].append(dic_nominal)
			 
			 dic_resultado["favoravel"] = len(lst_sim)
			 dic_resultado["contrario"] = len(lst_nao)
			 dic_resultado["abstencao"] = len(lst_abstencao)
			 dic_resultado["ausente"] = len(lst_ausente)
			 dic_resultado["presidencia"] = len(lst_presidencia)

		lst_votacao.append(dic_votacao)
		
	    dic_materia["resultado_votacao"] = lst_votacao
	    
	serialized = json.dumps(dic_materia, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
