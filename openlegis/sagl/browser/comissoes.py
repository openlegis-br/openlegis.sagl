# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from io import BytesIO
import requests
from PIL import Image, UnidentifiedImageError
import json
from DateTime import DateTime
import re
from xml.sax.saxutils import escape

ORDEM_CARGOS = {
    'Presidente': 1,
    'Vice-Presidente': 2,
    'Relator': 3,
    'Relator Geral': 3,
    'Membro': 4,
    'Membro Efetivo': 4,
    'Suplente': 5,
}

IND_TITULAR = {
    1: "Titular"
}


@implementer(IPublishTraverse)
class Comissoes(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('comissoes')

    item_id = None
    reunioes = False
    reuniao_id = None
    
    def publishTraverse(self, request, name):
        if not hasattr(self, 'subpath'):
            self.subpath = []
        self.subpath.append(name)
        if len(self.subpath) == 1:
           self.item_id = self.subpath[0]
        elif len(self.subpath) == 2:
           self.item_id = self.subpath[0]
           if self.subpath[1] == 'reunioes':
              self.reunioes = True
        elif len(self.subpath) == 3:
           self.item_id = self.subpath[0]
           if self.subpath[1] == 'reunioes':
              self.reunioes = True
           self.reuniao_id = self.subpath[2]
        return self

    def lista_comissoes(self):
        lista = []
        for item in self.context.zsql.comissao_obter_zsql(ind_extintas=0, ind_excluido=0):
                item_id = str(item.cod_comissao)
                dic = {
                    "@id": self.service_url + '/' + item_id,
                    "@type": 'Comissao',
                    "id": item_id,
                    "title": item.nom_comissao,
                    "description": item.sgl_comissao,
                    "tipo": item.nom_tipo_comissao,
                }
                lista.append(dic)
        lista.sort(key=lambda dic: dic['title'])
        dic_comissoes = {
            "description": 'Lista de comissões',
            "items": lista,
        }
        return dic_comissoes

    def get_comissao(self, item_id):
        item_id = int(item_id)
        results = [item for item in self.context.zsql.comissao_obter_zsql(cod_comissao=item_id, ind_extintas=0,  ind_excluido=0)]
        if not results:
            return {}
        item = results[0]
        cod_comissao = str(item.cod_comissao)
        dic_comissao = {
            "@id": self.service_url + '/' + cod_comissao,
            "@type": 'Comissao',
            "id": cod_comissao,
            "description": item.sgl_comissao,
            "title": item.nom_comissao,
            "tipo": item.nom_tipo_comissao,
        }

        dic_comissao['items'] = self._get_membros(cod_comissao)
        dic_comissao['reunioes'] = self.lista_reunioes(cod_comissao)
        dic_comissao['periodos'] = self._get_periodos(cod_comissao)
        return dic_comissao

    def _get_membros(self, cod_comissao):
        lst_membros = []
        for periodo in self.context.zsql.periodo_comp_comissao_obter_zsql(ind_excluido=0):
            if (DateTime().strftime("%Y-%m-%d") > DateTime(periodo.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d")) and (DateTime().strftime("%Y-%m-%d") < DateTime(periodo.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")):
               for composicao in self.context.zsql.composicao_comissao_obter_zsql(cod_comissao=cod_comissao, cod_periodo_comp=periodo.cod_periodo_comp):
                   cod_parlamentar = str(composicao.cod_parlamentar)
                   dic_membros = {
                        "@id":  self.portal_url + '/@@vereadores/' + str(composicao.cod_parlamentar),
                        "@type": 'ParticipanteComissao',
                        "id": cod_parlamentar,
                        "title": composicao.nom_parlamentar,
                        "description": composicao.nom_completo,
                        "cargo": composicao.des_cargo,
                   }
                   dic_membros['ordem'] = ORDEM_CARGOS.get(composicao.des_cargo, 6)
                   dic_membros['mandato'] = IND_TITULAR.get(composicao.ind_titular, "Suplente")
                   lst_imagem = []
                   foto = str(composicao.cod_parlamentar) + "_foto_parlamentar"
                   if hasattr(self.context.sapl_documentos.parlamentar.fotos, foto):
                      url = self.portal_url + '/sapl_documentos/parlamentar/fotos/' + foto
                      dic_membros['url_foto'] = url
                      response = requests.get(url)
                      try:
                         img = Image.open(BytesIO(response.content))
                         dic_image = {
                           "content-type": 'image/' + str(img.format).lower(),
                           "download": url,
                           "filename": foto,
                           "width": str(img.width),
                           "height": str(img.height),
                           "size": str(len(img.fp.read()))
                         }
                      except UnidentifiedImageError:
                         dic_image = {}
                      lst_imagem.append(dic_image)
                   else:
                      dic_membros['url_foto'] = self.portal_url + '/imagens/avatar.png' 
                   dic_membros['image'] = lst_imagem
                   lst_partido = []
                   for filiacao in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=composicao.cod_parlamentar):
                       for partido in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=filiacao.cod_partido):
                           dic_partido = {
                             "token": partido.sgl_partido,
                             "title": partido.nom_partido
                           }
                       if filiacao.dat_desfiliacao == None or filiacao.dat_desfiliacao == '':
                          lst_partido.append(dic_partido)
                   dic_membros['partido'] = lst_partido
                   lst_membros.append(dic_membros)
        lst_membros.sort(key=lambda dic_membros: dic_membros['title'])
        lst_membros.sort(key=lambda dic_membros: dic_membros['ordem'])
        return lst_membros

    def _get_periodos(self, cod_comissao):
        lst_composicao = []
        lst_periodos = []
        for periodo in self.context.zsql.periodo_comp_comissao_obter_zsql(ind_excluido=0):
            dic_composicao = {}
            dic_composicao['title'] = 'Composição da Comissão'
            dic_composicao['description'] = DateTime(periodo.dat_inicio_periodo, datefmt='international').strftime("%d/%m/%Y") + ' a ' + DateTime(periodo.dat_fim_periodo, datefmt='international').strftime("%d/%m/%Y")
            dic_composicao['start'] = DateTime(periodo.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d")
            dic_composicao['end'] = DateTime(periodo.dat_fim_periodo).strftime("%Y-%m-%d")
            dic_composicao['id'] = periodo.cod_periodo_comp
            if (DateTime(datefmt='international').strftime("%Y-%m-%d") > DateTime(periodo.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d")) and (DateTime(datefmt='international').strftime("%Y-%m-%d") < DateTime(periodo.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")):
              dic_composicao['atual'] = True
            else:
              dic_composicao['atual'] = False
            lst_membros = []
            for composicao in self.context.zsql.composicao_comissao_obter_zsql(cod_comissao=cod_comissao, cod_periodo_comp=periodo.cod_periodo_comp):
                dic_membros = {}
                dic_membros['@id'] = self.portal_url + '/@@vereadores/' + str(composicao.cod_parlamentar)
                dic_membros['@type'] = 'ParticipanteComissao'
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
            dic_composicao['items'] = lst_membros
            if (DateTime(datefmt='international').strftime("%Y-%m-%d") > DateTime(periodo.dat_inicio_periodo, datefmt='international').strftime("%Y-%m-%d")) and (DateTime(datefmt='international').strftime("%Y-%m-%d") < DateTime(periodo.dat_fim_periodo, datefmt='international').strftime("%Y-%m-%d")):
               pass
            else:
               lst_composicao.append(dic_composicao)
        return lst_composicao

    def lista_reunioes(self, item_id):
        item_id = int(item_id)
        lst_reunioes = []
        for reuniao in self.context.zsql.reuniao_comissao_obter_zsql(cod_comissao=item_id, ind_excluido=0):
            comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=item_id, ind_excluido=0)[0]
            dic_reuniao = {
                "@id": self.service_url + '/'+ str(reuniao.cod_comissao) + '/reunioes/' + str(reuniao.cod_reuniao),
                "@type": 'ReuniaoComissao',
                "id": str(reuniao.cod_reuniao),
                "title": str(reuniao.num_reuniao) + 'ª Reunião ' + reuniao.des_tipo_reuniao,
                "description": DateTime(reuniao.dat_inicio_reuniao, datefmt='international').strftime("%d/%m/%Y") + ' - ' + reuniao.hr_inicio_reuniao,
                "data": DateTime(reuniao.dat_inicio_reuniao, datefmt='international').strftime("%Y-%m-%d"),
                "ano": DateTime(reuniao.dat_inicio_reuniao, datefmt='international').strftime("%Y"),
                "hora_abertura": reuniao.hr_inicio_reuniao,
                "hora_encerramento": reuniao.hr_fim_reuniao
            }
            lst_pauta = []
            dic_pauta = {}	    
            pauta = str(reuniao.cod_reuniao) + "_pauta.pdf"
            if hasattr(self.context.sapl_documentos.reuniao_comissao, pauta):
               dic_pauta['content-type'] = 'application/pdf'
               dic_pauta['download'] = self.portal_url + '/sapl_documentos/reuniao_comissao/' + pauta
               dic_pauta['filename'] = pauta
               dic_pauta['size'] = ''
               lst_pauta.append(dic_pauta)
            dic_reuniao['arquivo_pauta'] = lst_pauta
            lst_ata = []
            dic_ata = {}
            ata = str(reuniao.cod_reuniao) + "_ata.pdf"
            if hasattr(self.context.sapl_documentos.reuniao_comissao, ata):
               dic_ata['content-type'] = 'application/pdf'
               dic_ata['download'] = self.portal_url + '/sapl_documentos/reuniao_comissao/' + ata
               dic_ata['filename'] = ata
               dic_ata['size'] = ''
               lst_ata.append(dic_ata)
            dic_reuniao['arquivo_ata'] = lst_ata
            lst_reunioes.append(dic_reuniao)
        lst_reunioes.sort(key=lambda dic_reuniao: dic_reuniao['data'], reverse=True)
        comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=item_id, ind_excluido=0)[0]
        dic_reunioes = {
            "@type": 'ReunioesComissao',
            "description": 'Lista de reuniões da ' + comissao.nom_comissao,
            "items": lst_reunioes,
        }
        return dic_reunioes

    def get_reuniao(self, reuniao_id):
        reuniao_id = int(reuniao_id)
        lst_reuniao = []
        for item in self.context.zsql.reuniao_comissao_obter_zsql(cod_reuniao=reuniao_id, ind_excluido=0):
            comissao = self.context.zsql.comissao_obter_zsql(cod_comissao=item.cod_comissao)[0]
            dic = {
              "@id": self.service_url + '/'+ str(item.cod_comissao) + '/reunioes/' + str(item.cod_reuniao),
              "@type": 'ReuniaoComissao',
              "id": str(item.cod_reuniao),
	      "start": DateTime(item.dat_inicio_reuniao, datefmt='international').strftime("%Y-%m-%d"),
              "ano": DateTime(item.dat_inicio_reuniao, datefmt='international').strftime("%Y"),
              "title": str(item.num_reuniao) + 'ª Reunião ' + item.des_tipo_reuniao,
              "description": DateTime(item.dat_inicio_reuniao, datefmt='international').strftime("%d/%m/%Y") + ' - ' + item.hr_inicio_reuniao,
              "hora_abertura": item.hr_inicio_reuniao,
              "hora_encerramento": item.hr_fim_reuniao,
              "tipo": item.des_tipo_reuniao,
              "tema": item.txt_tema,
              "comissao": comissao.nom_comissao,
              "comissao_id": comissao.cod_comissao,
            }
            lst_pauta = []
            dic_pauta = {}	    
            pauta = str(item.cod_reuniao) + "_pauta.pdf"
            if hasattr(self.context.sapl_documentos.reuniao_comissao, pauta):
               dic_pauta['content-type'] = 'application/pdf'
               dic_pauta['download'] = self.portal_url + '/sapl_documentos/reuniao_comissao/' + pauta
               dic_pauta['filename'] = pauta
               dic_pauta['size'] = ''
               lst_pauta.append(dic_pauta)
            dic['arquivo_pauta'] = lst_pauta
            lst_ata = []
            dic_ata = {}
            ata = str(item.cod_reuniao) + "_ata.pdf"
            if hasattr(self.context.sapl_documentos.reuniao_comissao, ata):
               dic_ata['content-type'] = 'application/pdf'
               dic_ata['download'] = self.portal_url + '/sapl_documentos/reuniao_comissao/' + ata
               dic_ata['filename'] = ata
               dic_ata['size'] = ''
               lst_ata.append(dic_ata)
            dic['arquivo_ata'] = lst_ata
            dic["chamada"] = []
            dic_presenca = {}
            lst_presenca = []
            dic_ausencia = {}
            lst_ausencia = []
            for periodo in self.context.zsql.periodo_comp_comissao_obter_zsql(data=DateTime(item.dat_inicio_reuniao_ord), ind_excluido=0):
                for membro in self.context.zsql.composicao_comissao_obter_zsql(cod_comissao=item.cod_comissao, cod_periodo_comp=periodo.cod_periodo_comp, ind_excluido=0):
                    dic_composicao = {}
                    dic_composicao['@type'] = 'Vereador'
                    dic_composicao['@id'] = self.portal_url + '/@@vereadores/' + str(membro.cod_parlamentar)
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

            lst_pauta = []
            for x in self.context.zsql.reuniao_comissao_pauta_obter_zsql(cod_reuniao=item.cod_reuniao, ind_excluido=0):
                # seleciona os detalhes dos itens da pauta
                dic_pauta = {} 
                dic_pauta["num_ordem"] = str(x.num_ordem)
                dic_pauta["description"] =  escape(x.txt_observacao)    
                if x.cod_materia != None:   
                   dic_pauta["@id"] = self.portal_url + '/@@materias/' + str(x.cod_materia)
                   dic_pauta["@type"] = 'Materia'
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
                      dic_arquivo['download'] = self.portal_url + '/sapl_documentos/materia/' + arquivo
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
                           dic_autor["@id"] = self.portal_url + '/@@autores/' + str(autor.cod_autor)
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
                          dic_relatoria['@id'] = self.portal_url + '/@@vereadores/' + str(relator.cod_parlamentar)
                          dic_relatoria['@type'] = 'Vereador'
                          dic_relatoria["id"] = str(relator.cod_parlamentar)
                          dic_relatoria["title"] = relator.nom_parlamentar
                          lst_relatoria.append(dic_relatoria)
                   else:
                      for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=x.cod_materia, cod_comissao=item.cod_comissao, ind_excluido=0):
                          dic_relatoria = {}
                          for parlamentar in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar):
                              dic_relatoria['@id'] = self.portal_url + '/@@vereadores/' + str(parlamentar.cod_parlamentar)
                              dic_relatoria['@type'] = 'Vereador'
                              dic_relatoria["id"] = str(parlamentar.cod_parlamentar)
                              dic_relatoria["title"] = parlamentar.nom_parlamentar
                          lst_relatoria.append(dic_relatoria)
                         
                   dic_pauta["relatoria"] = lst_relatoria

                   lst_parecer = []
                   for parecer in self.context.zsql.relatoria_obter_zsql(cod_materia=x.cod_materia, cod_comissao=item.cod_comissao, ind_excluido=0):
                       dic_parecer = {}
                       dic_parecer['@id'] = self.portal_url + '/@@pareceres/' + str(parecer.cod_relatoria)
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
                          dic_arquivo['download'] = self.portal_url + '/sapl_documentos/materia/' + arquivo
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

        return dic

    def render(self):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url()
        self.service_url = self.portal_url + '/@@comissoes'
        self.hoje = DateTime()
        data = {
           '@id':  self.service_url,
           '@type':  'Comissoes',
           'description':  'Lista de comissões',
        }     
        if self.reuniao_id:
           data.update(self.get_reuniao(self.reuniao_id))
        elif self.reunioes == True:
            data.update(self.lista_reunioes(self.item_id))     
        elif self.item_id:
           data.update(self.get_comissao(self.item_id))
        else:
            data.update(self.lista_comissoes())

        serialized = json.dumps(data, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
        return(serialized.decode())

