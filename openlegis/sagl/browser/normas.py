# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import name
from grokcore.security import require
from grokcore.view import View as GrokView
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface
from DateTime import DateTime
import json
import re

from z3c.saconfig import named_scoped_session
from sqlalchemy import text

Session = named_scoped_session('minha_sessao')


@implementer(IPublishTraverse)
class Normas(GrokView):
    """API de normas jurídicas (registro automático via grokcore)."""

    context(Interface)
    name('normas')           # URL: @@normas
    require('zope2.View')

    item_id = None

    # -------- Traversal --------
    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    # -------- Utils --------
    def _portal_url(self):
        try:
            return self.context.portal_url().rstrip('/')
        except Exception:
            portal = self.context.portal_url.getPortalObject()
            return portal.absolute_url().rstrip('/')

    def _json(self, data):
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)

    @staticmethod
    def _fmt_date(d):
        """Aceita DateTime/Zope, datetime/date do Python ou string/None."""
        try:
            # Zope DateTime e datetime/date do Python têm strftime
            return d.strftime("%Y-%m-%d")
        except Exception:
            return str(d) if d is not None else ""

    # -------- Handlers --------
    def help(self):
        """Retorna filtros disponíveis e um exemplo de URL."""
        session = Session()
        try:
            rows = session.execute(
                text("""
                    SELECT DISTINCT ano_norma
                      FROM norma_juridica
                     WHERE ind_excluido = 0
                  ORDER BY ano_norma DESC
                """)
            ).mappings().all()
        finally:
            session.close()

        lst_anos = [{'title': str(r['ano_norma']), 'id': str(r['ano_norma'])} for r in rows]

        lst_tipos = []
        for item in self.context.zsql.tipo_norma_juridica_obter_zsql(ind_excluido=0):
            lst_tipos.append({
                'title': item.des_tipo_norma,
                'id': str(item.tip_norma),
            })

        exemplo = ''
        if lst_anos and lst_tipos:
            exemplo = f"{self.service_url}?ano={lst_anos[0]['id']}&tipo={lst_tipos[0]['id']}"

        return {
            "exemplo": {"urlExemplo": exemplo},
            "filtros": {"ano": lst_anos, "tipo": lst_tipos},
        }

    def lista(self, tipo, ano):
        """Lista normas por tipo e ano."""
        session = Session()
        try:
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
              ORDER BY n.dat_norma DESC, n.num_norma DESC
            """)
            rows = session.execute(stmt, {'tipo': tipo, 'ano': ano}).mappings().all()
        finally:
            session.close()

        items = []
        for r in rows:
            cod = str(r['cod_norma'])
            items.append({
                "@id": f"{self.service_url}/{cod}",
                "@type": "Norma",
                "id": cod,
                "title": f"{r['des_tipo_norma']} nº {r['num_norma']}/{r['ano_norma']}",
                "description": r.get('txt_ementa') or "",
                "data_apresentacao": self._fmt_date(r.get('dat_norma')),
            })

        return {
            "description": f"Lista de normas jurídicas do ano de {ano}",
            "items": items,
        }

    def _get_materias(self, cod_materia):
        """Retorna (no máximo) uma matéria vinculada, se existir."""
        lst = []
        if not cod_materia:
            return lst

        mats = list(self.context.zsql.materia_obter_zsql(
            cod_materia=cod_materia, ind_excluido=0
        ))
        if not mats:
            return lst
        materia = mats[0]

        # Preferir o padrão @@materias/<id> para consistência com outras views
        dic = {
            '@id': f"{self.portal_url}/@@materias/{materia.cod_materia}",
            '@type': 'MateriaLegislativa',
            'id': str(materia.cod_materia),
            'title': f"{materia.des_tipo_materia} nº {materia.num_ident_basica}/{materia.ano_ident_basica}",
            'description': getattr(materia, 'txt_ementa', '') or '',
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
                "id": str(autor.cod_autor),
                "title": autor.nom_autor_join,
                "primeiro_autor": bool(getattr(autor, 'ind_primeiro_autor', 0) == 1),
            })
        dic['autoria'] = lista_autor
        lst.append(dic)
        return lst

    def _get_normas_vinculadas(self, cod_norma):
        """Retorna normas referidas e referentes, com checagens de existência."""
        lst = []

        # Referidas
        for v in self.context.zsql.vinculo_norma_juridica_referidas_obter_zsql(cod_norma=cod_norma):
            tipos_v = list(self.context.zsql.tipo_vinculo_norma_obter_zsql(tipo_vinculo=v.tip_vinculo))
            aux = tipos_v[0] if tipos_v else None
            refs = list(self.context.zsql.norma_juridica_obter_zsql(
                tip_norma=v.tip_norma, num_norma=v.num_norma, ano_norma=v.ano_norma
            ))
            if not refs:
                continue
            ref = refs[0]
            lst.append({
                '@type': 'Norma',
                '@id': f"{self.service_url}/{ref.cod_norma}",
                'id': str(ref.cod_norma),
                'title': f"{getattr(v, 'des_tipo_norma', '')} nº {v.num_norma}/{v.ano_norma}",
                'description': getattr(ref, 'txt_ementa', '') or '',
                'tipo_vinculo': getattr(aux, 'des_vinculo', '') if aux else '',
            })

        # Referentes
        for v in self.context.zsql.vinculo_norma_juridica_referentes_obter_zsql(cod_norma=cod_norma):
            tipos_v = list(self.context.zsql.tipo_vinculo_norma_obter_zsql(tipo_vinculo=v.tip_vinculo))
            aux = tipos_v[0] if tipos_v else None
            refs = list(self.context.zsql.norma_juridica_obter_zsql(
                tip_norma=v.tip_norma, num_norma=v.num_norma, ano_norma=v.ano_norma
            ))
            if not refs:
                continue
            ref = refs[0]
            lst.append({
                '@type': 'Norma',
                '@id': f"{self.service_url}/{ref.cod_norma}",
                'id': str(ref.cod_norma),
                'title': f"{getattr(v, 'des_tipo_norma', '')} nº {v.num_norma}/{v.ano_norma}",
                'description': getattr(ref, 'txt_ementa', '') or '',
                'tipo_vinculo': getattr(aux, 'des_vinculo', '') if aux else '',
            })

        return lst

    def _get_anexos(self, cod_norma):
        """Lista anexos (PDF) existentes para a norma."""
        lst = []
        for anexo in self.context.zsql.anexo_norma_obter_zsql(cod_norma=cod_norma, ind_excluido=0):
            id_anexo = f"{cod_norma}_anexo_{anexo.cod_anexo}"
            try:
                pasta = self.context.sapl_documentos.norma_juridica
            except Exception:
                pasta = None
            if pasta and hasattr(pasta, id_anexo):
                lst.append({
                    '@id': f"{self.service_url}/{cod_norma}",
                    '@type': 'Anexo',
                    'id': str(anexo.cod_anexo),
                    'title': getattr(anexo, 'txt_descricao', '') or '',
                    'file': [{
                        'content-type': 'application/pdf',
                        'download': f"{self.portal_url}/sapl_documentos/norma_juridica/{id_anexo}",
                        'filename': id_anexo,
                        'size': None,
                    }]
                })
        return lst

    def get_one(self, item_id):
        """Detalhe de uma norma específica."""
        try:
            cod = int(item_id)
        except (TypeError, ValueError):
            return {}

        results = list(self.context.zsql.norma_juridica_obter_zsql(
            cod_norma=cod, ind_excluido=0
        ))
        if not results:
            return {}
        item = results[0]
        cod_str = str(item.cod_norma)

        data_norma = self._fmt_date(getattr(item, 'dat_norma', None))
        data_pub   = self._fmt_date(getattr(item, 'dat_publicacao', None))

        dic = {
            "@id": f"{self.service_url}/{cod_str}",
            "@type": 'Norma',
            "id": cod_str,
            "title": f"{item.des_tipo_norma} nº {item.num_norma}/{item.ano_norma}",
            "description": getattr(item, 'txt_ementa', '') or '',
            "data_norma": data_norma,
            "data_publicacao": data_pub,
            "veiculo_publicacao": getattr(item, 'des_veiculo_publicacao', '') or '',
        }

        sts = list(self.context.zsql.tipo_situacao_norma_obter_zsql(
            tip_situacao_norma=getattr(item, 'cod_situacao', None), ind_excluido=0
        ))
        if sts:
            dic['status'] = sts[0].des_tipo_situacao

        # arquivos principal e compilado
        lst_arquivo = []
        arquivo = f"{cod_str}_texto_integral.pdf"
        try:
            pasta_norma = self.context.sapl_documentos.norma_juridica
        except Exception:
            pasta_norma = None
        if pasta_norma and hasattr(pasta_norma, arquivo):
            lst_arquivo.append({
                'content-type': 'application/pdf',
                'download': f"{self.portal_url}/sapl_documentos/norma_juridica/{arquivo}",
                'filename': arquivo,
                'size': ''
            })
        dic['file'] = lst_arquivo

        lst_comp = []
        arquivo_c = f"{cod_str}_texto_consolidado.pdf"
        if pasta_norma and hasattr(pasta_norma, arquivo_c):
            lst_comp.append({
                'content-type': 'application/pdf',
                'download': f"{self.portal_url}/sapl_documentos/norma_juridica/{arquivo_c}",
                'filename': arquivo_c,
                'size': ''
            })
        dic['texto_compilado'] = lst_comp

        dic['materia'] = self._get_materias(getattr(item, 'cod_materia', None))
        dic['normas_vinculadas'] = self._get_normas_vinculadas(cod_str)
        dic['anexos'] = self._get_anexos(cod_str)
        return dic

    # -------- Render --------
    def render(self, tipo='', ano=''):
        # inicializa URLs e datas
        self.portal_url = self._portal_url()
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

        return self._json(data)
