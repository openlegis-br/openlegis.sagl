# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from DateTime import DateTime
import MySQLdb
import json
import re


@implementer(IPublishTraverse)
class Normas(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('normas')

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
        lst_normas = []
        cur.execute('SELECT n.cod_norma, n.num_norma, n.ano_norma, t.des_tipo_norma, n.dat_norma, n.txt_ementa FROM norma_juridica n LEFT JOIN tipo_norma_juridica t ON n.tip_norma = t.tip_norma WHERE n.tip_norma=%s AND ano_norma=%s AND n.ind_excluido=0 ORDER BY DATE(n.dat_norma) DESC'%(tipo,ano))
        for row in cur.fetchall():
            row_id = str(row[0])
            item = {
                "@id": self.service_url + '/' + row_id,
                "@type": 'Norma',
                "id": row_id,
                "title": row[3] + ' nº ' + str(row[1]) + '/' + str(row[2]),
                "description": row[5],
                "data_apresentacao": str(row[4]),
            }
            lst_normas.append(item)
        db.close()

        dic_normas = {
            "description": 'Lista de normas jurídicas do ano de ' + ano,
            "items": lst_normas,
        }
        return dic_normas

    def _get_materias(self, cod_materia):
        lst_materias = []
        if cod_materia != None and cod_materia != '':
            materia = self.context.zsql.materia_obter_zsql(cod_materia=cod_materia, ind_excluido=0)[0]
            dic_materia = {
                '@id': self.portal_url + '/@@materia?id=' + materia.cod_materia,
                '@type': 'MateriaLegislativa',
                'id': materia.cod_materia,
                'title': materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica),
                'description': materia.txt_ementa,
                'remoteUrl': self.portal_url + '/consultas/materia/pasta_digital?cod_materia=' + materia.cod_materia,
            }
            autores = self.context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
            fields = autores.data_dictionary().keys()
            lista_autor = []
            for autor in autores:
                dic_autor = {
                    "@id": self.portal_url + '/@@autor?id=' + str(autor.cod_autor),
                    "@type": "Autor",
                    "id": autor.cod_autor,
                    "title": autor.nom_autor_join,
                    "primeiro_autor": bool(autor.ind_primeiro_autor == 1),
                }
                lista_autor.append(dic_autor)
            dic_materia["autoria"] = lista_autor
            lst_materias = [dic_materia]
        return lst_materias

    def _get_normas_vinculadas(self, cod_norma):
        lst_vinculadas= []
        for norma_vinculada in self.context.zsql.vinculo_norma_juridica_referidas_obter_zsql(cod_norma=cod_norma):
            aux = self.context.zsql.tipo_vinculo_norma_obter_zsql(tipo_vinculo=norma_vinculada.tip_vinculo)[0]
            norma_referida = self.context.zsql.norma_juridica_obter_zsql(tip_norma=norma_vinculada.tip_norma, num_norma=norma_vinculada.num_norma, ano_norma=norma_vinculada.ano_norma)[0]
            dic_vinculo = {}
            dic_vinculo['@type'] = 'Norma'
            dic_vinculo['@id'] = self.service_url + '/' + str(norma_referida.cod_norma)
            dic_vinculo['id'] = str(norma_referida.cod_norma)
            dic_vinculo['title']= str(norma_vinculada.des_tipo_norma) +" n° "+ str(norma_vinculada.num_norma)+ '/' + str(norma_vinculada.ano_norma)
            dic_vinculo['description'] = str(norma_referida.txt_ementa)
            dic_vinculo['tipo_vinculo'] = str(aux.des_vinculo)
            lst_vinculadas.append(dic_vinculo)
        for norma_vinculada in self.context.zsql.vinculo_norma_juridica_referentes_obter_zsql(cod_norma=cod_norma):
            aux = self.context.zsql.tipo_vinculo_norma_obter_zsql(tipo_vinculo=norma_vinculada.tip_vinculo)[0]
            norma_referente = self.context.zsql.norma_juridica_obter_zsql(tip_norma=norma_vinculada.tip_norma, num_norma=norma_vinculada.num_norma, ano_norma=norma_vinculada.ano_norma)[0]
            dic_vinculo = {}
            dic_vinculo['@type'] = 'Norma'
            dic_vinculo['@id'] = self.service_url + '/' + str(norma_referente.cod_norma)
            dic_vinculo['id'] = str(norma_referente.cod_norma)
            dic_vinculo['title']= str(norma_vinculada.des_tipo_norma) +" n° "+ str(norma_vinculada.num_norma)+ '/' + str(norma_vinculada.ano_norma)
            dic_vinculo['description'] = str(norma_referente.txt_ementa)
            dic_vinculo['tipo_vinculo'] = str(aux.des_vinculo)
            lst_vinculadas.append(dic_vinculo)
        return lst_vinculadas

    def _get_anexos(self, cod_norma):
        lst_anexos = []
        for anexo in self.context.zsql.anexo_norma_obter_zsql(cod_norma=cod_norma, ind_excluido=0):
            dic_anexo = {
                "@id": self.service_url + "/" + cod_norma,
                "@type": "Anexo",
                "id": str(anexo.cod_anexo),
                "title": anexo.txt_descricao,
                "file": []
            }
            dic_arq = {}
            id_anexo = str(cod_norma) + '_anexo_' + str(anexo.cod_anexo)
            if hasattr(self.context.sapl_documentos.norma_juridica, id_anexo):
                dic_arq = {
                    "content-type": "application/pdf",
                    "download": self.portal_url + '/sapl_documentos/norma_juridica/' + id_anexo,
                    "filename": id_anexo,
                    "size": None,
                }
                dic_anexo['file'].append(dic_arq)
            lst_anexos.append(dic_anexo)
        return lst_anexos

    def get_one(self, item_id):
        item_id = int(item_id)
        results = [item for item in self.context.zsql.norma_juridica_obter_zsql(cod_norma=item_id, ind_excluido=0)]
        if not results:
            return {}
        item = results[0]
        cod_norma = str(item.cod_norma)
        dic_norma = {
            "@id": self.service_url + '/' + cod_norma,
            "@type": 'Norma',
            "id": cod_norma,
            "title": item.des_tipo_norma + ' nº ' + str(item.num_norma) + '/' + str(item.ano_norma),
            "description": item.txt_ementa,
            "data_norma": DateTime(item.dat_norma, datefmt='international').strftime("%Y-%m-%d"),
            "data_publicacao": DateTime(item.dat_publicacao, datefmt='international').strftime("%Y-%m-%d"),
            "veiculo_publicacao": item.des_veiculo_publicacao,

        }
        for situacao in self.context.zsql.tipo_situacao_norma_obter_zsql(tip_situacao_norma=item.cod_situacao, ind_excluido=0):
            dic_norma['status'] = situacao.des_tipo_situacao
        # Arquivos
        lst_arquivo = []
        dic_arquivo = {}
        arquivo = str(cod_norma) + "_texto_integral.pdf"
        if hasattr(self.context.sapl_documentos.norma_juridica, arquivo):
           dic_arquivo['content-type'] = 'application/pdf'
           dic_arquivo['download'] = self.portal_url + '/sapl_documentos/norma_juridica/' + arquivo
           dic_arquivo['filename'] = arquivo
           dic_arquivo['size'] = ''
           lst_arquivo.append(dic_arquivo)
        dic_norma['file'] = lst_arquivo

        # Compilados
        lst_compilado = []
        dic_compilado = {}
        arquivo_compilado = str(cod_norma) + "_texto_consolidado.pdf"
        if hasattr(self.context.sapl_documentos.norma_juridica, arquivo):
           dic_compilado['content-type'] = 'application/pdf'
           dic_compilado['download'] = self.portal_url + '/sapl_documentos/norma_juridica/' + arquivo_compilado
           dic_compilado['filename'] = arquivo_compilado
           dic_compilado['size'] = ''
           lst_compilado.append(dic_compilado)
        dic_norma['texto_compilado'] = lst_compilado

        # Materias
        dic_norma['materia'] = self._get_materias(item.cod_materia)

        # Vinculadas
        dic_norma['normas_vinculadas'] = self._get_normas_vinculadas(cod_norma)
        dic_norma["anexos"] = self._get_anexos(cod_norma)
        return dic_norma

    def render(self, tipo='', ano=''):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url.portal_url()
        self.service_url = self.portal_url + '/@@normas'
        self.hoje = DateTime()
        data = {
           '@id':  self.service_url,
           '@type':  'Normas',
           'description':  'Lista de normas jurídicas',
        }
        if self.item_id:
            data.update(self.get_one(self.item_id))
        elif tipo != '' and ano != '':
            data.update(self.lista(tipo, ano))
        else:
            data.update(self.help())
        serialized = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode('utf8')
        return (serialized.decode())
