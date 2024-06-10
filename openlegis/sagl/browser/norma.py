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

class auxiliarNorma(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('auxiliar-normas')

    def render(self, description=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        
        db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="openlegis") 
        cur = db.cursor()
        cur.execute("SELECT DISTINCT ano_norma FROM norma_juridica WHERE ind_excluido=0 ORDER BY ano_norma")
        lst_anos = []
        for row in cur.fetchall():
            dic_anos = {}
            dic_anos['title'] = row[0]
            lst_anos.append(dic_anos)
        db.close()

        lst_tipos = []
      	for item in self.context.zsql.tipo_norma_juridica_obter_zsql(ind_excluido=0):
      	    dic_tipo = {}
      	    dic_tipo['title'] = item.des_tipo_norma
      	    dic_tipo['id'] = item.tip_norma
      	    lst_tipos.append(dic_tipo)
       	    
        dic_items = {}
	dic_items['@id'] =  portal_url + '/@@auxiliar-normas'
        dic_items['description'] = 'Lista de anos e tipos de normas jurídicas'
        dic_items['anos'] = lst_anos
        dic_items['tipos'] = lst_tipos

	serialized = json.dumps(dic_items, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
	

class Normas(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('normas')

    def render(self, tipo='', ano=''):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        data_atual = DateTime().strftime("%d/%m/%Y")
        ano_atual = DateTime().strftime("%Y")

        db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="openlegis") 
        cur = db.cursor()
        lst_normas = []
        if tipo != '' and ano != '':
           cur.execute('SELECT n.cod_norma, n.num_norma, n.ano_norma, t.des_tipo_norma, n.dat_norma, n.txt_ementa FROM norma_juridica n LEFT JOIN tipo_norma_juridica t ON n.tip_norma = t.tip_norma WHERE n.tip_norma=%s AND ano_norma=%s AND n.ind_excluido=0 ORDER BY DATE(n.dat_norma) DESC'%(tipo,ano))
           for row in cur.fetchall():
               dic_norma = {}
               dic_norma['@id'] =  portal_url + '/@@norma?id=' + str(row[0])
	       dic_norma['@type'] = 'Norma Jurídica'
               dic_norma['id'] = row[0]
               dic_norma['description'] = row[5]
	       dic_norma['title'] = row[3] + ' nº ' + str(row[1]) + '/' + str(row[2]) 
               dic_norma['data_apresentacao'] = str(row[4])
               lst_normas.append(dic_norma)
        db.close()

        dic_normas = {}
	dic_normas['@id'] =  portal_url + '/@@normas'
	dic_normas['@type'] = 'Listagem de Normas Jurídicas'
        dic_normas['description'] = 'Lista de normas jurídicas por tipo e ano'
        dic_normas['items'] = lst_normas

	serialized = json.dumps(dic_normas, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
	

class Norma(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('norma')

    def render(self, id):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()
        data_atual = DateTime().strftime("%d/%m/%Y")
        
      	for item in self.context.zsql.norma_juridica_obter_zsql(cod_norma=id, ind_excluido=0):
            dic_norma = {}
	    dic_norma['@type'] = 'Norma Jurídica'
	    dic_norma['@id'] =  portal_url + '/@@norma?id=' + item.cod_norma
	    dic_norma['id'] = item.cod_norma
	    dic_norma['title'] = item.des_tipo_norma + ' nº ' + str(item.num_norma) + '/' + str(item.ano_norma) 
	    dic_norma['description'] = item.txt_ementa
	    dic_norma['data_norma'] = DateTime(item.dat_norma, datefmt='international').strftime("%Y-%m-%d")
	    dic_norma['data_publicacao'] = DateTime(item.dat_publicacao, datefmt='international').strftime("%Y-%m-%d")
	    dic_norma['veiculo_publicacao'] = item.des_veiculo_publicacao
	    for situacao in self.context.zsql.tipo_situacao_norma_obter_zsql(tip_situacao_norma=item.cod_situacao, ind_excluido=0):
	        dic_norma['status'] = situacao.des_tipo_situacao
	    lst_arquivo = []
	    dic_arquivo = {}	    
	    arquivo = str(item.cod_norma) + "_texto_integral.pdf"
	    if hasattr(self.context.sapl_documentos.norma_juridica, arquivo):
	       dic_arquivo['content-type'] = 'application/pdf'
	       dic_arquivo['download'] = portal_url + '/sapl_documentos/norma_juridica/' + arquivo
	       dic_arquivo['filename'] = arquivo
	       dic_arquivo['size'] = ''
	       lst_arquivo.append(dic_arquivo)
	    dic_norma['file'] = lst_arquivo
	    lst_compilado = []
	    dic_compilado = {}	    
	    arquivo_compilado = str(item.cod_norma) + "_texto_consolidado.pdf"
	    if hasattr(self.context.sapl_documentos.norma_juridica, arquivo):
	       dic_compilado['content-type'] = 'application/pdf'
	       dic_compilado['download'] = portal_url + '/sapl_documentos/norma_juridica/' + arquivo_compilado
	       dic_compilado['filename'] = arquivo_compilado
	       dic_compilado['size'] = ''
	       lst_compilado.append(dic_compilado)
	    dic_norma['texto_compilado'] = lst_compilado
	    lst_materia = []
	    if item.cod_materia != None and item.cod_materia != '':
	       materia = self.context.zsql.materia_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0)[0]
	       dic_materia = {}
               dic_materia['@type'] = 'Matéria Legislativa'
	       dic_materia['@id'] =  portal_url + '/@@materia?id=' + materia.cod_materia
	       dic_materia['id'] = item.cod_norma
	       dic_materia['title'] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) 
	       dic_materia['description'] = materia.txt_ementa
	       dic_materia['remoteUrl'] = portal_url + '/consultas/materia/pasta_digital?cod_materia=' + materia.cod_materia	   
               autores = self.context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
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
	       lst_materia.append(dic_materia)
	    dic_norma['materia'] = lst_materia

            lst_vinculadas= []
            for norma_vinculada in self.context.zsql.vinculo_norma_juridica_referidas_obter_zsql(cod_norma=item.cod_norma):
                aux = self.context.zsql.tipo_vinculo_norma_obter_zsql(tipo_vinculo=norma_vinculada.tip_vinculo)[0]
                norma_referida = self.context.zsql.norma_juridica_obter_zsql(tip_norma=norma_vinculada.tip_norma, num_norma=norma_vinculada.num_norma, ano_norma=norma_vinculada.ano_norma)[0]
                dic_vinculo = {}
	        dic_vinculo['@type'] = 'Norma Jurídica'
	        dic_vinculo['@id'] = portal_url + '/@@norma?id=' + str(norma_referida.cod_norma)
	        dic_vinculo['id'] = str(norma_referida.cod_norma)
                dic_vinculo['title']= str(norma_vinculada.des_tipo_norma) +" n° "+ str(norma_vinculada.num_norma)+ '/' + str(norma_vinculada.ano_norma)
                dic_vinculo['description'] = str(norma_referida.txt_ementa)
                dic_vinculo['tipo_vinculo'] = str(aux.des_vinculo)
                lst_vinculadas.append(dic_vinculo)
            for norma_vinculada in self.context.zsql.vinculo_norma_juridica_referentes_obter_zsql(cod_norma=item.cod_norma):
                aux = self.context.zsql.tipo_vinculo_norma_obter_zsql(tipo_vinculo=norma_vinculada.tip_vinculo)[0]
                norma_referente = self.context.zsql.norma_juridica_obter_zsql(tip_norma=norma_vinculada.tip_norma, num_norma=norma_vinculada.num_norma, ano_norma=norma_vinculada.ano_norma)[0]
                dic_vinculo = {}
	        dic_vinculo['@type'] = 'Norma Jurídica'
	        dic_vinculo['@id'] = portal_url + '/@@norma?id=' + str(norma_referente.cod_norma)
	        dic_vinculo['id'] = str(norma_referente.cod_norma)
                dic_vinculo['title']= str(norma_vinculada.des_tipo_norma) +" n° "+ str(norma_vinculada.num_norma)+ '/' + str(norma_vinculada.ano_norma)
                dic_vinculo['description'] = str(norma_referente.txt_ementa)
                dic_vinculo['tipo_vinculo'] = str(aux.des_vinculo)
                lst_vinculadas.append(dic_vinculo)
	    dic_norma['normas_vinculadas'] = lst_vinculadas

            lst_anexos = []
            for anexo in self.context.zsql.anexo_norma_obter_zsql(cod_norma=item.cod_norma, ind_excluido=0):
                dic_anexo = {}
	        dic_anexo['@type'] = 'Anexo'
                dic_anexo['title'] = anexo.txt_descricao
                dic_anexo['id'] = str(anexo.cod_anexo)
	        lst_arquivo_anexo = []
	        dic_arq = {}	    
	        id_anexo = str(item.cod_norma) + '_anexo_' + str(anexo.cod_anexo)
	        if hasattr(self.context.sapl_documentos.norma_juridica, id_anexo):
	           dic_arq['content-type'] = 'application/pdf'
	           dic_arq['download'] = portal_url + '/sapl_documentos/norma_juridica/' + id_anexo
	           dic_arq['filename'] = id_anexo
	           dic_arq['size'] = ''
	           lst_arquivo_anexo.append(dic_arq)
	        dic_anexo['file'] = lst_arquivo_anexo
                lst_anexos.append(dic_anexo)
	    dic_norma["anexos"] = lst_anexos
	    
	serialized = json.dumps(dic_norma, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
	return(serialized.decode())
