# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from DateTime import DateTime
import json
import re

# Substituí MySQLdb por SQLAlchemy nas consultas diretas
from z3c.saconfig import named_scoped_session
from sqlalchemy import text

Session = named_scoped_session('minha_sessao')


@implementer(IPublishTraverse)
class Normas(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('normas')

    item_id = None

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    def help(self):
        session = Session()
        # anos distintos de norma_juridica
        rows = session.execute(
            text("""
                SELECT DISTINCT ano_norma
                  FROM norma_juridica
                 WHERE ind_excluido = 0
              ORDER BY ano_norma DESC
            """)
        ).mappings().all()
        lst_anos = [{'title': str(r['ano_norma'])} for r in rows]
        session.close()

        lst_tipos = []
        for item in self.context.zsql.tipo_norma_juridica_obter_zsql(ind_excluido=0):
            lst_tipos.append({
                'title': item.des_tipo_norma,
                'id': item.tip_norma
            })

        exemplo = ''
        if lst_anos and lst_tipos:
            exemplo = f"{self.service_url}?ano={lst_anos[0]['title']}&tipo={lst_tipos[0]['id']}"

        return {
            "exemplo": { "urlExemplo": exemplo },
            "filtros": {
                "ano": lst_anos,
                "tipo": lst_tipos,
            }
        }

    def lista(self, tipo, ano):
        session = Session()
        stmt = text("""
            SELECT n.cod_norma,
                   n.num_norma,
                   n.ano_norma,
                   t.des_tipo_norma,
                   n.dat_norma,
                   n.txt_ementa
              FROM norma_juridica n
         LEFT JOIN tipo_norma_juridica t
                ON n.tip_norma = t.tip_norma
             WHERE n.tip_norma = :tipo
               AND n.ano_norma = :ano
               AND n.ind_excluido = 0
          ORDER BY n.dat_norma DESC
        """)
        rows = session.execute(stmt, {'tipo': tipo, 'ano': ano}).mappings().all()
        lst_normas = []
        for r in rows:
            cod = str(r['cod_norma'])
            data_apres = r['dat_norma'].strftime("%Y-%m-%d") if r['dat_norma'] else ''
            lst_normas.append({
                "@id": f"{self.service_url}/{cod}",
                "@type": "Norma",
                "id": cod,
                "title": f"{r['des_tipo_norma']} nº {r['num_norma']}/{r['ano_norma']}",
                "description": r['txt_ementa'],
                "data_apresentacao": data_apres,
            })
        session.close()

        return {
            "description": f"Lista de normas jurídicas do ano de {ano}",
            "items": lst_normas,
        }

    def _get_materias(self, cod_materia):
        lst_materias = []
        if cod_materia:
            materia = self.context.zsql.materia_obter_zsql(
                cod_materia=cod_materia, ind_excluido=0
            )[0]
            dic = {
                '@id': f"{self.portal_url}/@@materia?id={materia.cod_materia}",
                '@type': 'MateriaLegislativa',
                'id': materia.cod_materia,
                'title': (
                    f"{materia.des_tipo_materia} nº "
                    f"{materia.num_ident_basica}/{materia.ano_ident_basica}"
                ),
                'description': materia.txt_ementa,
                'remoteUrl': (
                    f"{self.portal_url}/consultas/materia/pasta_digital?"
                    f"cod_materia={materia.cod_materia}"
                ),
            }
            lista_autor = []
            for autor in self.context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia):
                lista_autor.append({
                    "@id": f"{self.portal_url}/@@autor?id={autor.cod_autor}",
                    "@type": "Autor",
                    "id": autor.cod_autor,
                    "title": autor.nom_autor_join,
                    "primeiro_autor": bool(autor.ind_primeiro_autor == 1),
                })
            dic['autoria'] = lista_autor
            lst_materias = [dic]
        return lst_materias

    def _get_normas_vinculadas(self, cod_norma):
        lst = []
        for v in self.context.zsql.vinculo_norma_juridica_referidas_obter_zsql(cod_norma=cod_norma):
            aux = self.context.zsql.tipo_vinculo_norma_obter_zsql(tipo_vinculo=v.tip_vinculo)[0]
            ref = self.context.zsql.norma_juridica_obter_zsql(
                tip_norma=v.tip_norma, num_norma=v.num_norma, ano_norma=v.ano_norma
            )[0]
            lst.append({
                '@type': 'Norma',
                '@id': f"{self.service_url}/{ref.cod_norma}",
                'id': str(ref.cod_norma),
                'title': f"{v.des_tipo_norma} nº {v.num_norma}/{v.ano_norma}",
                'description': ref.txt_ementa,
                'tipo_vinculo': aux.des_vinculo,
            })
        for v in self.context.zsql.vinculo_norma_juridica_referentes_obter_zsql(cod_norma=cod_norma):
            aux = self.context.zsql.tipo_vinculo_norma_obter_zsql(tipo_vinculo=v.tip_vinculo)[0]
            ref = self.context.zsql.norma_juridica_obter_zsql(
                tip_norma=v.tip_norma, num_norma=v.num_norma, ano_norma=v.ano_norma
            )[0]
            lst.append({
                '@type': 'Norma',
                '@id': f"{self.service_url}/{ref.cod_norma}",
                'id': str(ref.cod_norma),
                'title': f"{v.des_tipo_norma} nº {v.num_norma}/{v.ano_norma}",
                'description': ref.txt_ementa,
                'tipo_vinculo': aux.des_vinculo,
            })
        return lst

    def _get_anexos(self, cod_norma):
        lst = []
        for anexo in self.context.zsql.anexo_norma_obter_zsql(cod_norma=cod_norma, ind_excluido=0):
            id_anexo = f"{cod_norma}_anexo_{anexo.cod_anexo}"
            if hasattr(self.context.sapl_documentos.norma_juridica, id_anexo):
                lst.append({
                    '@id': f"{self.service_url}/{cod_norma}",
                    '@type': 'Anexo',
                    'id': str(anexo.cod_anexo),
                    'title': anexo.txt_descricao,
                    'file': [{
                        'content-type': 'application/pdf',
                        'download': f"{self.portal_url}/sapl_documentos/norma_juridica/{id_anexo}",
                        'filename': id_anexo,
                        'size': None,
                    }]
                })
        return lst

    def get_one(self, item_id):
        item_id = int(item_id)
        results = list(self.context.zsql.norma_juridica_obter_zsql(
            cod_norma=item_id, ind_excluido=0
        ))
        if not results:
            return {}
        item = results[0]
        cod = str(item.cod_norma)

        # Trata string e DateTime de forma genérica
        def fmt(d):
            if hasattr(d, 'strftime'):
                return d.strftime("%Y-%m-%d")
            return str(d) if d is not None else ''

        data_norma = fmt(item.dat_norma)
        data_pub   = fmt(item.dat_publicacao)

        dic = {
            "@id": f"{self.service_url}/{cod}",
            "@type": 'Norma',
            "id": cod,
            "title": f"{item.des_tipo_norma} nº {item.num_norma}/{item.ano_norma}",
            "description": item.txt_ementa,
            "data_norma": data_norma,
            "data_publicacao": data_pub,
            "veiculo_publicacao": item.des_veiculo_publicacao or '',
        }
        for sit in self.context.zsql.tipo_situacao_norma_obter_zsql(
            tip_situacao_norma=item.cod_situacao, ind_excluido=0
        ):
            dic['status'] = sit.des_tipo_situacao

        # arquivos principal e compilado
        lst_arquivo = []
        arquivo = f"{cod}_texto_integral.pdf"
        if hasattr(self.context.sapl_documentos.norma_juridica, arquivo):
            lst_arquivo.append({
                'content-type': 'application/pdf',
                'download': f"{self.portal_url}/sapl_documentos/norma_juridica/{arquivo}",
                'filename': arquivo,
                'size': ''
            })
        dic['file'] = lst_arquivo

        lst_comp = []
        arquivo_c = f"{cod}_texto_consolidado.pdf"
        if hasattr(self.context.sapl_documentos.norma_juridica, arquivo_c):
            lst_comp.append({
                'content-type': 'application/pdf',
                'download': f"{self.portal_url}/sapl_documentos/norma_juridica/{arquivo_c}",
                'filename': arquivo_c,
                'size': ''
            })
        dic['texto_compilado'] = lst_comp

        dic['materia'] = self._get_materias(item.cod_materia)
        dic['normas_vinculadas'] = self._get_normas_vinculadas(cod)
        dic['anexos'] = self._get_anexos(cod)
        return dic

    def render(self, tipo='', ano=''):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url.portal_url()
        self.service_url = f"{self.portal_url}/@@normas"
        self.hoje = DateTime()

        data = {
            '@id': self.service_url,
            '@type': 'Normas',
            'description': 'Lista de normas jurídicas',
        }
        if self.item_id:
            data.update(self.get_one(self.item_id))
        elif tipo and ano:
            data.update(self.lista(tipo, ano))
        else:
            data.update(self.help())

        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
