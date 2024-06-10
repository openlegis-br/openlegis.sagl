# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from xml.sax.saxutils import escape
from DateTime import DateTime
import MySQLdb
import json
import re


@implementer(IPublishTraverse)
class Materias(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('materias')

    item_id = None

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        ## Apenas se for um id numerico
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    def help(self):
        db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="openlegis")
        cur = db.cursor()
        cur.execute("SELECT DISTINCT ano_ident_basica FROM materia_legislativa WHERE ind_excluido=0 ORDER BY ano_ident_basica DESC")
        lst_anos = []
        for row in cur.fetchall():
            dic_anos = {}
            dic_anos['id'] = row[0]
            dic_anos['title'] = row[0]
            lst_anos.append(dic_anos)
        db.close()

        lst_tipos = []
        for item in self.context.zsql.tipo_materia_legislativa_obter_zsql(tip_natureza='P', ind_excluido=0):
            dic_tipo = {}
            dic_tipo['title'] = item.des_tipo_materia
            dic_tipo['id'] = item.tip_materia
            lst_tipos.append(dic_tipo)
  
        dic_items = {
            "exemplo": { 
                "urlExemplo":  self.service_url + '/?ano=2024&tipo=3',
            },
            "filtros": {
              "ano": lst_anos,
              "tipo": lst_tipos,
            }
        }
        return dic_items

    def lista(self, tipo, ano):
        db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="openlegis")
        cur = db.cursor()
        lst_materias = []
        cur.execute('SELECT m.cod_materia, m.num_ident_basica, m.ano_ident_basica, t.des_tipo_materia, m.dat_apresentacao, m.txt_ementa FROM materia_legislativa m LEFT JOIN tipo_materia_legislativa t ON m.tip_id_basica = t.tip_materia WHERE tip_id_basica=%s AND ano_ident_basica=%s AND m.ind_excluido=0 ORDER BY DATE(m.dat_apresentacao) DESC, m.num_ident_basica DESC'%(tipo,ano))
        for row in cur.fetchall():
            row_id = str(row[0])
            item = {
                "@id": self.service_url + '/' + row_id,
                "@type": 'Materia',
                "id": row_id,
                "title": row[3] + ' nº ' + str(row[1]) + '/' + str(row[2]),
                "description": escape(row[5]),
                "date": str(row[4]),
            }
            autores = self.context.zsql.autoria_obter_zsql(cod_materia=row[0])
            fields = autores.data_dictionary().keys()
            lista_autor = []
            for autor in autores:
                dic_autor = {}
                for field in fields:
                    dic_autor['description'] = autor.des_tipo_autor
                    dic_autor['title'] = autor.nom_autor_join
                    if autor.ind_primeiro_autor == 1:
                       dic_autor['firstAuthor'] = True
                    else:
                       dic_autor['firstAuthor'] = False
                lista_autor.append(dic_autor)
            item["authorship"] = lista_autor
            lst_arquivo = []
            dic_arquivo = {}	    
            arquivo = str(row[0]) + "_texto_integral.pdf"
            if hasattr(self.context.sapl_documentos.materia, arquivo):
               dic_arquivo['content-type'] = 'application/pdf'
               dic_arquivo['download'] = self.portal_url + '/sapl_documentos/materia/' + arquivo
               dic_arquivo['filename'] = arquivo
               dic_arquivo['size'] = ''
               lst_arquivo.append(dic_arquivo)
            item['file'] = lst_arquivo
            item['remoteUrl'] = self.portal_url + '/consultas/materia/materia_mostrar_proc?cod_materia=' + str(row[0])          
            lst_materias.append(item)
            
        db.close()
        
        des_tipo = 'matérias'     
        if tipo != '':
           for item in self.context.zsql.tipo_materia_legislativa_obter_zsql(tip_materia=tipo, tip_natureza='P', ind_excluido=0):
      	       des_tipo = item.des_tipo_materia

        dic_materias = {
            "description": 'Lista de ' + des_tipo + ' do ano de ' + ano,
            "items": lst_materias,
        }
        return dic_materias

    def get_one(self, item_id):
        item_id = int(item_id)
        results = [item for item in self.context.zsql.materia_obter_zsql(cod_materia=item_id, ind_excluido=0)]
        if not results:
            return {}
        item = results[0]
        cod_materia = str(item.cod_materia)
        dic_materia = {
	    "@type": 'Materia',
	    "@id":  self.service_url + '/' + str(cod_materia),
	    "id": str(cod_materia),
	    "title": item.des_tipo_materia + ' nº ' + str(item.num_ident_basica) + '/' + str(item.ano_ident_basica),
	    "description": escape(item.txt_ementa),
	    "date": DateTime(item.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d"),
	}
        autores = self.context.zsql.autoria_obter_zsql(cod_materia=cod_materia)
        fields = autores.data_dictionary().keys()
        lista_autor = []
        for autor in autores:
            dic_autor = {}
            for field in fields:
                dic_autor['description'] = autor.des_tipo_autor
                dic_autor['title'] = autor.nom_autor_join
                if autor.ind_primeiro_autor == 1:
                   dic_autor['firstAuthor'] = True
                else:
                   dic_autor['firstAuthor'] = False
            lista_autor.append(dic_autor)
        dic_materia["authorship"] = lista_autor
        lst_arquivo = []
        dic_arquivo = {}	    
        arquivo = str(cod_materia) + "_texto_integral.pdf"
        if hasattr(self.context.sapl_documentos.materia, arquivo):
           dic_arquivo['content-type'] = 'application/pdf'
           dic_arquivo['download'] = self.portal_url + '/sapl_documentos/materia/' + arquivo
           dic_arquivo['filename'] = arquivo
           dic_arquivo['size'] = ''
           lst_arquivo.append(dic_arquivo)
        dic_materia['file'] = lst_arquivo
        dic_materia['remoteUrl'] = self.portal_url + '/consultas/materia/materia_mostrar_proc?cod_materia=' + str(cod_materia)
        dic_materia["quorum"]=""
        for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=item.tip_quorum):
            dic_materia["quorum"] = quorum.des_quorum
            dic_materia["quorum_id"] = str(quorum.cod_quorum)
        dic_materia["processingRegime"]=""
        for regime in self.context.zsql.regime_tramitacao_obter_zsql(cod_regime_tramitacao=item.cod_regime_tramitacao):
            dic_materia["processingRegime"] = regime.des_regime_tramitacao
            dic_materia["processingRegime_id"] = str(regime.cod_regime_tramitacao)
        if item.ind_tramitacao == 1:
           dic_materia["inProgress"] = True
        else:
           dic_materia["inProgress"] = False
        lst_anexada = []
        for anexada in self.context.zsql.anexada_obter_zsql(cod_materia_principal=item.cod_materia, ind_excluido=0):
            dic_anexada = {}
            materia_anexada = self.context.zsql.materia_obter_zsql(cod_materia=anexada.cod_materia_anexada, ind_excluido = 0)[0]
            dic_anexada['@type'] = 'Materia'
            dic_anexada['@id'] = self.service_url + '/' + str(materia_anexada.cod_materia) 
            dic_anexada['title'] = materia_anexada.des_tipo_materia + ' nº ' + str(materia_anexada.num_ident_basica) + '/' + str(materia_anexada.ano_ident_basica)
            dic_anexada['id'] = str(materia_anexada.cod_materia)
            dic_anexada['description'] = materia_anexada.txt_ementa
            dic_anexada['annexationDate'] = DateTime(anexada.dat_anexacao, datefmt='international').strftime("%Y-%m-%d")
            if anexada.dat_desanexacao == None or anexada.dat_desanexacao == '':
               lst_anexada.append(dic_anexada)
        dic_materia["attached"] = lst_anexada
        lst_documento = []
        for documento in self.context.zsql.documento_acessorio_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
            tipo = self.context.zsql.tipo_documento_obter_zsql(tip_documento=documento.tip_documento)[0]
            dic_documento = {}
            dic_documento['title'] = documento.nom_documento
            dic_documento['id'] = str(documento.cod_documento)
            dic_documento['description'] = tipo.des_tipo_documento
            dic_documento['authorship'] = documento.nom_autor_documento
            dic_documento['date'] = DateTime(documento.dat_documento, datefmt='international').strftime("%Y-%m-%d")
            lst_arquivo = []
            dic_arquivo = {}	    
            arquivo = str(documento.cod_documento) + ".pdf"
            if hasattr(self.context.sapl_documentos.materia, arquivo):
               dic_arquivo['content-type'] = 'application/pdf'
               dic_arquivo['download'] = self.portal_url + '/sapl_documentos/materia/' + arquivo
               dic_arquivo['filename'] = arquivo
               dic_arquivo['size'] = ''
               lst_arquivo.append(dic_arquivo)
               dic_documento['file'] = lst_arquivo         
               lst_documento.append(dic_documento)
        dic_materia["accessoryDocument"] = lst_documento
        lst_emenda = []
        for emenda in self.context.zsql.emenda_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
            dic_emenda = {}
            dic_emenda['title'] = 'Emenda ' + emenda.des_tipo_emenda + ' nº ' + str(emenda.num_emenda)
            dic_emenda['description'] = emenda.txt_ementa
            autores = self.context.zsql.autoria_emenda_obter_zsql(cod_emenda=emenda.cod_emenda, ind_excluido=0)
            fields = autores.data_dictionary().keys()
            lista_autor = []
            for autor in autores:
                dic_autor = {}
                for field in fields:
                    dic_autor['description'] = autor.des_tipo_autor
                    dic_autor['title'] = autor.nom_autor_join
                lista_autor.append(dic_autor)
            dic_emenda["authorship"] = lista_autor
            dic_emenda['data'] = DateTime(emenda.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d")
            lst_arquivo = []
            arquivo = str(emenda.cod_emenda) + "_emenda.pdf"
            if hasattr(self.context.sapl_documentos.emenda, arquivo):
               dic_arquivo = {}	    
               dic_arquivo['content-type'] = 'application/pdf'
               dic_arquivo['download'] = self.portal_url + '/sapl_documentos/emenda/' + arquivo
               dic_arquivo['filename'] = arquivo
               dic_arquivo['size'] = ''
               lst_arquivo.append(dic_arquivo)
            dic_emenda['file'] = lst_arquivo
            lst_emenda.append(dic_emenda)
        dic_materia["amendment"] = lst_emenda
        lst_substitutivo = []
        for substitutivo in self.context.zsql.substitutivo_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
            dic_substitutivo = {}
            dic_substitutivo['title'] = 'Substitutivo' + ' nº ' + str(substitutivo.num_substitutivo)
            dic_substitutivo['description'] = substitutivo.txt_ementa
            autores = self.context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo, ind_excluido=0)
            fields = autores.data_dictionary().keys()
            lista_autor = []
            for autor in autores:
                dic_autor = {}
                for field in fields:
                    dic_autor['description'] = autor.des_tipo_autor
                    dic_autor['title'] = autor.nom_autor_join
                lista_autor.append(dic_autor)
            dic_substitutivo["authorship"] = lista_autor
            dic_substitutivo['date'] = DateTime(substitutivo.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d")
            lst_arquivo = []
            arquivo = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
            if hasattr(self.context.sapl_documentos.substitutivo, arquivo):
               dic_arquivo = {}	    
               dic_arquivo['content-type'] = 'application/pdf'
               dic_arquivo['download'] = self.portal_url + '/sapl_documentos/substitutivo/' + arquivo
               dic_arquivo['filename'] = arquivo
               dic_arquivo['size'] = ''
               lst_arquivo.append(dic_arquivo)
            dic_substitutivo['file'] = lst_arquivo
            lst_substitutivo.append(dic_substitutivo)
        dic_materia["substitute"] = lst_substitutivo
        lst_pareceres = []
        for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=item.cod_materia):
            comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao)[0]
            relator = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
            dic_parecer = {}
            dic_parecer['title'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
            dic_parecer['description'] = ''
            if parecer.tip_conclusao == 'F':
               dic_parecer['description'] = 'Relatoria de '+ relator.nom_parlamentar + ', FAVORÁVEL'
            elif parecer.tip_conclusao == 'C':
               dic_parecer['description'] = 'Relatoria de '+ relator.nom_parlamentar + ', CONTRÁRIA'
            dic_parecer['date'] = DateTime(parecer.dat_destit_relator, datefmt='international').strftime("%Y-%m-%d")
            lista_autor = []
            dic_autor = {}
            dic_autor["@id"] = self.portal_url + '/@@comissoes/' + str(comissao.cod_comissao)
            dic_autor['@type'] = 'Comissão'
            dic_autor['description'] = comissao.sgl_comissao
            dic_autor['title'] = comissao.nom_comissao
            lista_autor.append(dic_autor)
            dic_parecer["authorship"] = lista_autor
            lst_arquivo = []
            dic_arquivo = {}	    
            arquivo = str(parecer.cod_relatoria) + "_parecer.pdf"
            if hasattr(self.context.sapl_documentos.parecer_comissao, arquivo):
               dic_arquivo['content-type'] = 'application/pdf'
               dic_arquivo['download'] = self.portal_url + '/sapl_documentos/parecer_comissao/' + arquivo
               dic_arquivo['filename'] = arquivo
               dic_arquivo['size'] = ''
               lst_arquivo.append(dic_arquivo)
            dic_parecer['file'] = lst_arquivo
            lst_pareceres.append(dic_parecer)
        dic_materia["committeeOpinion"] = lst_pareceres
        lst_tramitacao = []
        for tramitacao in self.context.zsql.tramitacao_obter_zsql(cod_materia=item.cod_materia, ind_encaminha=1, ind_excluido=0):
            dic_tramitacao = {}
            dic_tramitacao['title'] = tramitacao.des_status
            dic_tramitacao['description'] = escape(tramitacao.txt_tramitacao)
            dic_tramitacao['date'] = DateTime(tramitacao.dat_tramitacao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
            for unidade in self.context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao = tramitacao.cod_unid_tram_local):
               dic_tramitacao['sourceUnit'] = unidade.nom_unidade_join
            for unidade in self.context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao = tramitacao.cod_unid_tram_dest):
               dic_tramitacao['destinationUnit'] = unidade.nom_unidade_join
            if tramitacao.ind_ult_tramitacao == 1:
               dic_tramitacao['last'] = True
            else:
               dic_tramitacao['last'] = False
            lst_arquivo = []
            dic_arquivo = {}	    
            arquivo = str(tramitacao.cod_tramitacao) + "_tram.pdf"
            if hasattr(self.context.sapl_documentos.materia.tramitacao, arquivo):
               dic_arquivo['content-type'] = 'application/pdf'
               dic_arquivo['download'] = self.portal_url + '/sapl_documentos/materia/tramitacao/' + arquivo
               dic_arquivo['filename'] = arquivo
               dic_arquivo['size'] = ''
               lst_arquivo.append(dic_arquivo)
            dic_tramitacao['file'] = lst_arquivo
            lst_tramitacao.append(dic_tramitacao)
            dic_materia["processing"] = lst_tramitacao

        lst_votacao = []
        for registro in self.context.zsql.votacao_materia_expediente_pesquisar_zsql(cod_materia=item.cod_materia):
            dic_votacao = {}
            lst_resultado = []
            dic_resultado = {}
            sessao_plenaria = self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=registro.cod_sessao_plen)[0]
            tipo_sessao = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao_plenaria.tip_sessao)[0]
            votacao = self.context.zsql.votacao_expediente_materia_obter_zsql(cod_sessao_plen=sessao_plenaria.cod_sessao_plen, cod_materia=item.cod_materia, ind_excluido=0)[0]
            dic_votacao["@id"] = self.portal_url + '/@@sessoes/' + str(sessao_plenaria.cod_sessao_plen)
            dic_votacao["date"] = DateTime(sessao_plenaria.dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d")
            dic_votacao["turn"] = ''
            for tip_votacao in self.context.zsql.votingType_obter_zsql(tip_votacao=registro.tip_votacao):
                dic_votacao["votingType"] = tip_votacao.des_votingType
            if votacao.tip_resultado_votacao != None:
               dic_votacao["id"] = str(votacao.cod_votacao)
               dic_votacao["description"] = 'Expediente da ' + str(sessao_plenaria.num_sessao_plen) + 'ª Reunião ' + tipo_sessao.nom_sessao
               dic_votacao["title"] = 'Expediente da ' + str(sessao_plenaria.num_sessao_plen) + 'ª Reunião ' + tipo_sessao.nom_sessao
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
               dic_resultado["favorable"] = votos_favoraveis
               dic_resultado["contrary"] = votos_contrarios
               dic_resultado["abstention"] = abstencoes
               if votacao.tip_resultado_votacao:
                  resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
                  for i in resultado:
                      nom_resultado= i.nom_resultado
                      dic_votacao["title"] = nom_resultado
                      lst_resultado.append(dic_resultado)
                  dic_votacao["result"] = lst_resultado
            lst_votacao.append(dic_votacao)

        for registro in self.context.zsql.votacao_materia_ordem_dia_pesquisar_zsql(cod_materia=item.cod_materia):
            dic_votacao = {}
            lst_resultado = []
            dic_resultado = {}
            sessao_plenaria = self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=registro.cod_sessao_plen)[0]
            tipo_sessao = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao_plenaria.tip_sessao)[0]
            votacao = self.context.zsql.votacao_ordem_dia_obter_zsql(cod_sessao_plen=sessao_plenaria.cod_sessao_plen, cod_materia=item.cod_materia, ind_excluido=0)[0]
            dic_votacao["@id"] = self.portal_url + '/@@sessoes/' + str(sessao_plenaria.cod_sessao_plen)
            dic_votacao["date"] = DateTime(sessao_plenaria.dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d")
            for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=registro.tip_votacao):
                dic_votacao["votingType"] = tip_votacao.des_tipo_votacao
            for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=registro.tip_turno):
                dic_votacao["turn"] = turno.des_turno
            if votacao.tip_resultado_votacao != None:
               dic_votacao["id"] = str(votacao.cod_votacao)
               dic_votacao["description"] = 'Ordem do Dia da ' + str(sessao_plenaria.num_sessao_plen) + 'ª Reunião ' + tipo_sessao.nom_sessao
               dic_votacao["title"] = 'Ordem do Dia da ' + str(sessao_plenaria.num_sessao_plen) + 'ª Reunião ' + tipo_sessao.nom_sessao
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
               dic_resultado["favorable"] = votos_favoraveis
               dic_resultado["contrary"] = votos_contrarios
               dic_resultado["abstention"] = abstencoes
               if votacao.tip_resultado_votacao:
                  resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
                  for i in resultado:
                      nom_resultado= i.nom_resultado
                      dic_votacao["title"] = nom_resultado
                      lst_resultado.append(dic_resultado)
                  dic_votacao["result"] = lst_resultado
               # votação nominal
               if votacao.tip_votacao == 2:
                  dic_votacao["votes"] = []
                  lst_sim = []
                  lst_nao = []
                  lst_abstencao = []
                  lst_presidencia = []
                  lst_ausente = []
                  for voto in self.context.zsql.votacao_parlamentar_obter_zsql(cod_votacao=votacao.cod_votacao, ind_excluido=0):
                      parlamentar = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=voto.cod_parlamentar)[0]
                      dic_voto = {}
                      dic_voto['@id'] =  self.portal_url + '/@@vereador?id=' + parlamentar.cod_parlamentar
                      dic_voto['@type'] = 'Vereador'
                      dic_voto['title'] =  parlamentar.nom_parlamentar
                      dic_voto['description'] =  parlamentar.nom_completo
                      dic_voto['voting_id'] = str(voto.cod_votacao)
                      lst_partido = []
                      for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=parlamentar.cod_parlamentar):    
                          dic_partido = {}
                          for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
                              dic_partido['token'] = partido.sgl_partido
                              dic_partido['title'] = partido.nom_partido
                          if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
                              lst_partido.append(dic_partido)
                      dic_voto['party'] = lst_partido                       
                      if voto.vot_parlamentar == 'Nao':
                         dic_voto['vote'] = 'Não'
                         lst_nao.append(dic_voto)
                      elif voto.vot_parlamentar == 'Abstencao':
                         dic_voto['vote'] = 'Abstenção'
                         lst_abstencao.append(dic_voto)
                      elif voto.vot_parlamentar == 'Sim':
                         dic_voto['vote'] = 'Sim'
                         lst_sim.append(dic_voto)
                      elif voto.vot_parlamentar == 'Na Presid.':
                         dic_voto['vote'] = 'Na Presidência'
                         lst_presidencia.append(dic_voto)
                      elif voto.vot_parlamentar == 'Ausente':
                         dic_voto['vote'] = 'Ausente'
                         lst_ausente.append(dic_voto)
                      dic_nominal = {}
                  dic_nominal["favorable"] = lst_sim
                  dic_nominal["contrary"] = lst_nao
                  dic_nominal["abstention"] = lst_abstencao
                  dic_nominal["presidency"] = lst_presidencia
                  dic_nominal["absent"] = lst_ausente
                  dic_votacao["votes"].append(dic_nominal)
                  dic_resultado["favorable"] = len(lst_sim)
                  dic_resultado["contrary"] = len(lst_nao)
                  dic_resultado["abstention"] = len(lst_abstencao)
                  dic_resultado["absent"] = len(lst_ausente)
                  dic_resultado["presidency"] = len(lst_presidencia)
            lst_votacao.append(dic_votacao)	
        dic_materia["voteResult"] = lst_votacao
        return dic_materia

    def render(self, tipo='', ano=''):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url.portal_url()
        self.service_url = self.portal_url + '/@@materias'
        self.hoje = DateTime()
        data = {
           '@id':  self.service_url,
           '@type':  'Materias',
           'description':  'Lista de matérias legislativas',
        }
        if self.item_id:
            data.update(self.get_one(self.item_id))
        elif tipo != '' and ano != '':
            data.update(self.lista(tipo, ano))
        else:
            data.update(self.help())

        serialized = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode('utf8')
        return (serialized.decode())
