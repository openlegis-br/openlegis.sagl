# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
import requests
import json
from DateTime import DateTime
import re

@implementer(IPublishTraverse)
class Sessoes(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('sessoes')

    ano = None
    tipo = None
    item_id = None
    votacao = False
    presenca = False

    def publishTraverse(self, request, name):
        if not hasattr(self, 'subpath'):
            self.subpath = []
        self.subpath.append(name)
 
        for index, value in enumerate(self.subpath):
            if value == "tipo" and index < len(self.subpath) - 1:
               next_element = self.subpath[index + 1]
               self.tipo = next_element
            if value == "ano" and index < len(self.subpath) - 1:
               next_element = self.subpath[index + 1]
               self.ano = next_element
            if value == "id" and index < len(self.subpath) - 1:
               next_element = self.subpath[index + 1]
               self.item_id = next_element
            if value == "votacao":
               self.votacao = True
            if value == "presenca":
               self.presenca = True

        return self

    def help(self):
        lst_anos = []
        for item in self.context.zsql.ano_sessao_plenaria_obter_zsql():
            dic_ano = {}
            dic_ano['title'] = item.ano_sessao
            dic_ano['id'] = item.ano_sessao
            lst_anos.append(dic_ano)

        lst_tipos = []
        for item in self.context.zsql.tipo_sessao_plenaria_obter_zsql(ind_excluido=0):
            dic_tipo = {}
            dic_tipo['title'] = item.nom_sessao
            dic_tipo['id'] = item.tip_sessao
            lst_tipos.append(dic_tipo)

        dic_items = {
            "exemplo": { 
                "urlExemplo":  self.service_url + '/tipo/1/ano/2024',
            },
            "filtros": {
                "ano": lst_anos,
                "tipo": lst_tipos,
            }
        }
        return dic_items

    def lista_sessoes(self, tipo, ano):
        lista = []
        for item in self.context.zsql.sessao_plenaria_obter_zsql(tip_sessao=tipo, ano_sessao=ano, ind_excluido=0):
            tipo = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao, ind_excluido=0)[0]
            item_id = str(item.cod_sessao_plen)
            dic = {
                "@id": self.service_url + '/id/' + item_id,
                "@type": 'SessaoPlenaria',
                "id": str(item_id),
                "title": str(item.num_sessao_plen) + 'ª ' + 'Reunião ' +  tipo.nom_sessao,
                "description": DateTime(item.dat_inicio_sessao, datefmt='international').strftime("%d/%m/%Y") + ' ' + item.hr_inicio_sessao,
                "date": DateTime(item.dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d"),
                "type": tipo.nom_sessao,
                "type_id": item.tip_sessao,
                "startTime": DateTime(item.hr_inicio_sessao, datefmt='international').strftime("%H:%M"),
                "endTime": item.hr_fim_sessao,
                "@id_votacao": self.service_url + '/id/' + item_id + '/votacao',
                "@id_presenca": self.service_url + '/id/' + item_id + '/presenca',
            }
            dic['pauta'] = self._get_pauta(item_id)
            dic['ata'] = self._get_ata(item_id)
            #dic['votacao_nominal'] = self._get_votacao_nominal(item_id)
            lista.append(dic)
        lista.sort(key=lambda dic: dic['date'], reverse=True)
        dic_sessoes = {
            "description": 'Lista de reuniões plenárias',
            "items": lista,
        }
        return dic_sessoes

    def get_sessao(self, item_id):
        lst_pauta = []
        cod_sessao_plen = int(item_id)
        pauta = str(cod_sessao_plen) + "_pauta_sessao.pdf"
        if hasattr(self.context.sapl_documentos.pauta_sessao, pauta):
           dic_pauta = {
              "content-type": 'application/pdf',
              "download": self.portal_url + '/sapl_documentos/pauta_sessao/' + pauta,
              "filename": pauta,
              "size": '',
           }
           lst_pauta.append(dic_pauta)
        lst_ata = []
        cod_sessao_plen = int(item_id)
        ata = str(cod_sessao_plen) + "_ata_sessao.pdf"
        if hasattr(self.context.sapl_documentos.ata_sessao, ata):
           dic_ata = {
              "content-type": 'application/pdf',
              "download": self.portal_url + '/sapl_documentos/ata_sessao/' + ata,
              "filename": ata,
              "size": '',
           }
           lst_ata.append(dic_ata)
        for sessao in self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0):
            tipo = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao.tip_sessao, ind_excluido=0)[0]
            title = str(sessao.num_sessao_plen) + 'ª Reunião ' +  tipo.nom_sessao
            description = DateTime(sessao.dat_inicio_sessao, datefmt='international').strftime("%d/%m/%Y") + ' - ' + sessao.hr_inicio_sessao
        dic_sessao = {
            "@type": 'SessaoPlenaria',
            "@id": self.service_url + '/id/' + item_id,
            "@id_votacao": self.service_url + '/id/' + item_id + '/votacao',
            "@id_presenca": self.service_url + '/id/' + item_id + '/presenca',
            "description": description,
            "title": title,
            "pauta": lst_pauta,
            "ata": lst_ata,
        }
        return dic_sessao

    def _get_pauta(self, item_id):
        lst_pauta = []
        cod_sessao_plen = int(item_id)
        pauta = str(cod_sessao_plen) + "_pauta_sessao.pdf"
        if hasattr(self.context.sapl_documentos.pauta_sessao, pauta):
           dic_pauta = {
              "content-type": 'application/pdf',
              "download": self.portal_url + '/sapl_documentos/pauta_sessao/' + pauta,
              "filename": pauta,
              "size": '',
           }
           lst_pauta.append(dic_pauta)
        return lst_pauta
        
    def _get_ata(self, item_id):
        lst_ata = []
        cod_sessao_plen = int(item_id)
        ata = str(cod_sessao_plen) + "_ata_sessao.pdf"
        if hasattr(self.context.sapl_documentos.ata_sessao, ata):
           dic_ata = {
              "content-type": 'application/pdf',
              "download": self.portal_url + '/sapl_documentos/ata_sessao/' + ata,
              "filename": ata,
              "size": '',
           }
           lst_ata.append(dic_ata)
        return lst_ata

    def _get_parlamentar(self, cod_parlamentar):
        for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_parlamentar,ind_excluido=0):
            dic_parlamentar = {
                "@type": 'Vereador',
                "@id": self.portal_url + '/@@vereadores/' + str(cod_parlamentar),
                'id': parlamentar.cod_parlamentar,
                "description": parlamentar.nom_completo,
                "title": parlamentar.nom_parlamentar,
            }
            lst_partido = []
            for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=cod_parlamentar):    
                dic_partido = {}
                for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
                    dic_partido['token'] = partido.sgl_partido
                    dic_partido['title'] = partido.nom_partido
                    if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
                       lst_partido.append(dic_partido)
            dic_parlamentar['partido'] = lst_partido

        return dic_parlamentar

    def _get_presenca(self, item_id):
        for sessao in self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0):
            tipo = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao.tip_sessao, ind_excluido=0)[0]
            description = str(sessao.num_sessao_plen) + 'ª Reunião ' +  tipo.nom_sessao + ' - ' + DateTime(sessao.dat_inicio_sessao, datefmt='international').strftime("%d/%m/%Y")
        dic_presenca = {
            "@id": self.service_url + '/id/' + item_id + '/presenca',
            "@type": 'presencaSessao',
            "title": 'Listas de presença na reunião plenária',
            "description": description,
            "chamadaRegimental": self._get_presenca_abertura(item_id),
            "ordemDia": self._get_presenca_abertura(item_id),
        }
        return dic_presenca
    
    def _get_presenca_abertura(self, item_id):     
        chamada = []
        lst_presentes = []
        lst_ausentes = []
        lst_justificados = []
        for item in self.context.zsql.presenca_sessao_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0):
            if item.tip_frequencia == 'P':
               dic = self._get_parlamentar(item.cod_parlamentar)
               lst_presentes.append(dic)
            if item.tip_frequencia == 'F':
               dic = self._get_parlamentar(item.cod_parlamentar)
               lst_ausentes.append(dic)
            if item.tip_frequencia == 'A':
               dic = self._get_parlamentar(item.cod_parlamentar)
               lst_justificados.append(dic)
        dic_chamada = {}
        dic_chamada['presentes'] = lst_presentes
        dic_chamada['presentes_qtde'] = str(len(lst_presentes))
        dic_chamada['ausentes'] = lst_ausentes
        dic_chamada['ausentes_qtde'] = str(len(lst_ausentes))
        dic_chamada['justificados'] = lst_justificados
        dic_chamada['justificados_qtde'] =  str(len(lst_justificados))
        chamada.append(dic_chamada)
        return chamada

    def _get_presenca_ordem_dia(self, item_id):     
        chamada = []
        lst_presentes = []
        lst_ausentes = []
        lst_justificados = []
        for item in self.context.zsql.presenca_ordem_dia_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0):
            if item.tip_frequencia == 'P':
               dic = self._get_parlamentar(item.cod_parlamentar)
               lst_presentes.append(dic)
            if item.tip_frequencia == 'F':
               dic = self._get_parlamentar(item.cod_parlamentar)
               lst_ausentes.append(dic)
            if item.tip_frequencia == 'A':
               dic = self._get_parlamentar(item.cod_parlamentar)
               lst_justificados.append(dic)
        dic_chamada = {}
        dic_chamada['presentes'] = lst_presentes
        dic_chamada['presentes_qtde'] = str(len(lst_presentes))
        dic_chamada['ausentes'] = lst_ausentes
        dic_chamada['ausentes_qtde'] = str(len(lst_ausentes))
        dic_chamada['justificados'] = lst_justificados
        dic_chamada['justificados_qtde'] =  str(len(lst_justificados))
        chamada.append(dic_chamada)
        return chamada

    def _get_votacao(self, item_id):
        lst_materias = []
        cod_sessao_plen = int(item_id)
        for ordem in self.context.zsql.votacao_ordem_dia_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0):
            pauta = self.context.zsql.ordem_dia_obter_zsql(cod_ordem=ordem.cod_ordem, ind_excluido=0)[0]
            if ordem.tip_votacao == 2:     
              # MATÉRIAS LEGISLATIVAS
              if ordem.cod_materia != None and ordem.cod_materia !='':
                 for materia in self.context.zsql.materia_obter_zsql(cod_materia=ordem.cod_materia, ind_excluido=0):
                      dic_item = {}
                      dic_item["@id"] = self.portal_url + '/@@materias/' + str(materia.cod_materia)
                      dic_item["@type"] = 'Materia'
                      dic_item["title"] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                      dic_item["id"] = str(materia.cod_materia)
                      dic_item["description"] = materia.txt_ementa
                      for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=pauta.tip_votacao):
                          dic_item["tipo_votacao"] = tip_votacao.des_tipo_votacao
                      for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=pauta.tip_turno):
                          dic_item["turno"] = turno.des_turno
                      for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=pauta.tip_quorum):
                          dic_item["quorum"] = quorum.des_quorum
                      autores = self.context.zsql.autoria_obter_zsql(cod_materia=ordem.cod_materia)
                      fields = autores.data_dictionary().keys()
                      lista_autor = []
                      for autor in autores:
                          dic_autor = {}
                          for field in fields:
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
                  for parecer in self.context.zsql.relatoria_obter_zsql(cod_relatoria=ordem.cod_parecer):
                     comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao)[0]
                     relator = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
                     materia = self.context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia)[0]
                     dic_item = {}
                     dic_item['title'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer)
                     dic_item["id"] =  str(parecer.cod_relatoria)
                     dic_item['description'] = ''
                     if parecer.tip_conclusao == 'F':
                        dic_item['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', FAVORÁVEL ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                     elif parecer.tip_conclusao == 'C':
                        dic_item['description'] = 'Parecer ' +  comissao.sgl_comissao + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) +  ', com relatoria de '+ relator.nom_parlamentar + ', CONTRÁRIO ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                     for tip_votacao in self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=pauta.tip_votacao):
                        dic_item["tipo_votacao"] = tip_votacao.des_tipo_votacao
                     for turno in self.context.zsql.turno_discussao_obter_zsql(cod_turno=pauta.tip_turno):
                        dic_item["turno"] = turno.des_turno
                     for quorum in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=pauta.tip_quorum):
                        dic_item["quorum"] = quorum.des_quorum
                     lista_autor = []
                     dic_autor = {}
                     dic_autor["@id"] = self.portal_url + '/@@comissoes/' + str(comissao.cod_comissao)
                     dic_autor['@type'] = 'Comissão'
                     dic_autor['description'] = comissao.nom_comissao
                     dic_autor['id'] = comissao.cod_comissao
                     dic_autor['title'] = comissao.sgl_comissao
                     lista_autor.append(dic_autor)
                     dic_item["autoria"] = lista_autor
		   
	      #votação nominal
              lst_resultado = []
              dic_resultado = {}
              if ordem.tip_resultado_votacao != None:
                  resultado = self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=ordem.tip_resultado_votacao, ind_excluido=0)
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
              for voto in self.context.zsql.votacao_parlamentar_obter_zsql(cod_votacao=ordem.cod_votacao, ind_excluido=0):
                  parlamentar = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=voto.cod_parlamentar)[0]
                  dic_voto = {}
                  dic_voto['@id'] =  self.portal_url + '/@@vereadores/' + parlamentar.cod_parlamentar
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
               
        for sessao in self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0):
            tipo = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao.tip_sessao, ind_excluido=0)[0]
            description = str(sessao.num_sessao_plen) + 'ª Reunião ' +  tipo.nom_sessao + ' - ' + DateTime(sessao.dat_inicio_sessao, datefmt='international').strftime("%d/%m/%Y")

        dic_votacao = {
            "@id": self.service_url + '/id/' + item_id + '/votacao',
            "@type": 'votacaoNominal',
            "title": 'Lista de votação nominal',
            "description": description,
            "items": lst_materias,
        }
        return dic_votacao


    def render(self, ano='', tipo=''):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url()
        self.service_url = self.portal_url + '/@@sessoes'
        self.hoje = DateTime()
        data = {
           '@id':  self.service_url,
           '@type':  'SessoesPlenarias',
           'description':  'Lista de reuniões plenárias',
        }   
        if self.tipo != None or self.ano != None:
            data.update(self.lista_sessoes(self.tipo, self.ano))
            
        elif self.item_id != None and self.votacao == True and self.presenca == False:
            data.update(self._get_votacao(self.item_id))
        elif self.item_id != None and self.votacao == False and self.presenca == True:
            data.update(self._get_presenca(self.item_id))
        elif self.item_id != None and self.votacao == False and self.presenca == False:
            data.update(self.get_sessao(self.item_id))
        else:
            data.update(self.help())

        serialized = json.dumps(data, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
        return(serialized.decode())

