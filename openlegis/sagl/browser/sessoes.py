# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface
import json
from DateTime import DateTime

@implementer(IPublishTraverse)
class Sessoes(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('sessoes')

    def publishTraverse(self, request, name):
        if not hasattr(self, 'subpath'):
            self.subpath = []
        self.subpath.append(name)
        for idx, val in enumerate(self.subpath):
            if val == 'tipo' and idx+1 < len(self.subpath):
                self.tipo = self.subpath[idx+1]
            if val == 'ano' and idx+1 < len(self.subpath):
                self.ano = self.subpath[idx+1]
            if val == 'id' and idx+1 < len(self.subpath):
                self.item_id = self.subpath[idx+1]
            if val == 'votacao':
                self.votacao = True
            if val == 'presenca':
                self.presenca = True
        return self

    def update_context(self):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.portal.absolute_url()
        self.service_url = f"{self.portal_url}/@@sessoes"
        self.hoje = DateTime()
        self.tipo = getattr(self, 'tipo', None)
        self.ano = getattr(self, 'ano', None)
        self.item_id = getattr(self, 'item_id', None)
        self.votacao = getattr(self, 'votacao', False)
        self.presenca = getattr(self, 'presenca', False)

    def help(self):
        anos = [{'title': a.ano_sessao, 'id': a.ano_sessao}
                for a in self.context.zsql.ano_sessao_plenaria_obter_zsql()]
        tipos = [{'title': t.nom_sessao, 'id': t.tip_sessao}
                 for t in self.context.zsql.tipo_sessao_plenaria_obter_zsql(ind_excluido=0)]
        return {
            'exemplo': {'urlExemplo': f"{self.service_url}/tipo/1/ano/2025"},
            'filtros': {'ano': anos, 'tipo': tipos}
        }

    def _get_pauta(self, item_id):
        lst = []
        fn = f"{item_id}_pauta_sessao.pdf"
        if hasattr(self.context.sapl_documentos.pauta_sessao, fn):
            lst.append({
                'content-type': 'application/pdf',
                'download': f"{self.portal_url}/sapl_documentos/pauta_sessao/{fn}",
                'filename': fn, 'size': ''
            })
        return lst

    def _get_ata(self, item_id):
        lst = []
        fn = f"{item_id}_ata_sessao.pdf"
        if hasattr(self.context.sapl_documentos.ata_sessao, fn):
            lst.append({
                'content-type': 'application/pdf',
                'download': f"{self.portal_url}/sapl_documentos/ata_sessao/{fn}",
                'filename': fn, 'size': ''
            })
        return lst

    def _get_parlamentar(self, cod_parlamentar):
        for p in self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_parlamentar, ind_excluido=0):
            partidos = []
            for f in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=cod_parlamentar):
                if not f.dat_desfiliacao:
                    for pt in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=f.cod_partido):
                        partidos.append({'token': pt.sgl_partido, 'title': pt.nom_partido})
            return {
                '@type': 'Vereador',
                '@id': f"{self.portal_url}/@@vereadores/{p.cod_parlamentar}",
                'id': p.cod_parlamentar,
                'title': p.nom_parlamentar,
                'description': p.nom_completo,
                'partido': partidos
            }
        return {}

    def lista_sessoes(self, tipo, ano):
        items = []
        for s in self.context.zsql.sessao_plenaria_obter_zsql(tip_sessao=tipo, ano_sessao=ano, ind_excluido=0):
            t = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=s.tip_sessao, ind_excluido=0)[0]
            sid = str(s.cod_sessao_plen)
            items.append({
                '@id': f"{self.service_url}/id/{sid}",
                '@type': 'SessaoPlenaria',
                'id': sid,
                'title': f"{s.num_sessao_plen}ª Reunião {t.nom_sessao}",
                'description': f"{DateTime(s.dat_inicio_sessao,datefmt='international').strftime('%d/%m/%Y')} {DateTime(s.hr_inicio_sessao,datefmt='international').strftime('%H:%M')}",
                'date': DateTime(s.dat_inicio_sessao,datefmt='international').strftime('%Y-%m-%d'),
                'type': t.nom_sessao,
                'type_id': s.tip_sessao,
                'startTime': DateTime(s.hr_inicio_sessao,datefmt='international').strftime('%H:%M'),
                'endTime': s.hr_fim_sessao,
                '@id_votacao': f"{self.service_url}/id/{sid}/votacao",
                '@id_presenca': f"{self.service_url}/id/{sid}/presenca",
                'pauta': self._get_pauta(sid),
                'ata': self._get_ata(sid),
            })
        items.sort(key=lambda x: x['date'], reverse=True)
        return {'description': 'Lista de reuniões plenárias', 'items': items}

    def get_sessao(self, item_id):
        sess = self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0)
        if not sess:
            return {}
        s = sess[0]
        t = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=s.tip_sessao, ind_excluido=0)[0]
        sid = str(s.cod_sessao_plen)
        desc = f"{s.num_sessao_plen}ª Reunião {t.nom_sessao} - {DateTime(s.dat_inicio_sessao,datefmt='international').strftime('%d/%m/%Y')}"
        return {
            '@type': 'SessaoPlenaria',
            '@id': f"{self.service_url}/id/{sid}",
            '@id_votacao': f"{self.service_url}/id/{sid}/votacao",
            '@id_presenca': f"{self.service_url}/id/{sid}/presenca",
            'id': sid,
            'date': DateTime(s.dat_inicio_sessao,datefmt='international').strftime('%Y-%m-%d'),
            'description': desc,
            'type': t.nom_sessao,
            'type_id': s.tip_sessao,
            'startTime': DateTime(s.hr_inicio_sessao,datefmt='international').strftime('%H:%M'),
            'endTime': s.hr_fim_sessao,
            'title': f"{s.num_sessao_plen}ª Reunião {t.nom_sessao}",
            'pauta': self._get_pauta(sid),
            'ata': self._get_ata(sid),
        }

    def _get_presenca_abertura(self, item_id):
        presentes, ausentes, just = [], [], []
        for p in self.context.zsql.presenca_sessao_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0):
            dic = self._get_parlamentar(p.cod_parlamentar)
            if p.tip_frequencia == 'P':
                presentes.append(dic)
            elif p.tip_frequencia == 'F':
                ausentes.append(dic)
            elif p.tip_frequencia == 'A':
                just.append(dic)
        return [{
            'presentes': presentes,
            'presentes_qtde': str(len(presentes)),
            'ausentes': ausentes,
            'ausentes_qtde': str(len(ausentes)),
            'justificados': just,
            'justificados_qtde': str(len(just))
        }]

    def _get_presenca_ordem_dia(self, item_id):
        return self._get_presenca_abertura(item_id)

    def _get_presenca(self, item_id):
        sess = self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0)[0]
        t = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sess.tip_sessao, ind_excluido=0)[0]
        desc = f"{sess.num_sessao_plen}ª Reunião {t.nom_sessao} - {DateTime(sess.dat_inicio_sessao,datefmt='international').strftime('%d/%m/%Y')}"
        return {
            '@id': f"{self.service_url}/id/{item_id}/presenca",
            '@type': 'presencaSessao',
            'title': 'Listas de presença na reunião plenária',
            'description': desc,
            'chamadaRegimental': self._get_presenca_abertura(item_id),
            'ordemDia': self._get_presenca_ordem_dia(item_id),
        }

    def _get_votacao(self, item_id):
        lst_materias = []
        for ordem in self.context.zsql.votacao_ordem_dia_obter_zsql(cod_sessao_plen=int(item_id), ind_excluido=0):
            pauta = self.context.zsql.ordem_dia_obter_zsql(cod_ordem=ordem.cod_ordem, ind_excluido=0)[0]
            dic_item = {}

            # Monta matéria ou parecer
            cod_mat = getattr(ordem, 'cod_materia', None)
            cod_par = getattr(ordem, 'cod_parecer', None)
            tip_vot = getattr(ordem, 'tip_votacao', None)

            if tip_vot == 2 and cod_mat:
                mat = self.context.zsql.materia_obter_zsql(cod_materia=cod_mat, ind_excluido=0)[0]
                dic_item.update({
                    "@id": f"{self.portal_url}/@@materias/{mat.cod_materia}",
                    "@type": 'Materia',
                    "title": f"{mat.des_tipo_materia} nº {mat.num_ident_basica}/{mat.ano_ident_basica}",
                    "id": str(mat.cod_materia),
                    "description": mat.txt_ementa,
                    "tipo_votacao": self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=pauta.tip_votacao)[0].des_tipo_votacao,
                    "turno": self.context.zsql.turno_discussao_obter_zsql(cod_turno=pauta.tip_turno)[0].des_turno,
                    "quorum": self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=pauta.tip_quorum)[0].des_quorum,
                })
                auto = []
                for a in self.context.zsql.autoria_obter_zsql(cod_materia=cod_mat):
                    auto.append({
                        'description': a.des_tipo_autor,
                        'id': a.cod_autor,
                        'title': a.nom_autor_join,
                        'primeiro_autor': bool(a.ind_primeiro_autor)
                    })
                dic_item['autoria'] = auto

            elif cod_par:
                par = self.context.zsql.relatoria_obter_zsql(cod_relatoria=cod_par)[0]
                com = self.context.zsql.comissao_obter_zsql(cod_comissao=par.cod_comissao)[0]
                rel = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=par.cod_parlamentar)[0]
                mat = self.context.zsql.materia_obter_zsql(cod_materia=par.cod_materia)[0]
                fav = par.tip_conclusao == 'F'
                desc = (f"Parecer {com.sgl_comissao} nº {par.num_parecer}/{par.ano_parecer}, "
                        f"com relatoria de {rel.nom_parlamentar}, {'FAVORÁVEL' if fav else 'CONTRÁRIO'} ao "
                        f"{mat.sgl_tipo_materia} {mat.num_ident_basica}/{mat.ano_ident_basica}")
                dic_item.update({
                    "@type": 'Parecer',
                    "id": str(par.cod_relatoria),
                    "title": f"Parecer {com.sgl_comissao} nº {par.num_parecer}/{par.ano_parecer}",
                    "description": desc,
                    "tipo_votacao": self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=pauta.tip_votacao)[0].des_tipo_votacao,
                    "turno": self.context.zsql.turno_discussao_obter_zsql(cod_turno=pauta.tip_turno)[0].des_turno,
                    "quorum": self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=pauta.tip_quorum)[0].des_quorum,
                    "autoria": [{
                        "@id": f"{self.portal_url}/@@comissoes/{com.cod_comissao}",
                        "@type": "Comissão",
                        "description": com.nom_comissao,
                        "id": com.cod_comissao,
                        "title": com.sgl_comissao
                    }],
                })

            # apuração
            res_list = []
            if getattr(ordem, 'tip_resultado_votacao', None):
                for r in self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=ordem.tip_resultado_votacao, ind_excluido=0):
                    res_list.append({'resultado': r.nom_resultado})
            dic_item['apuracao'] = res_list

            # votos nominais (usa sempre ordem.cod_votacao)
            cod_vot = ordem.cod_votacao
            lst_sim, lst_nao, lst_abst, lst_pres, lst_aus = [], [], [], [], []
            for v in self.context.zsql.votacao_parlamentar_obter_zsql(cod_votacao=cod_vot, ind_excluido=0):
                p = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=v.cod_parlamentar)[0]
                partidos = [
                    {'token': pt.sgl_partido, 'title': pt.nom_partido}
                    for f in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=p.cod_parlamentar)
                    for pt in self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=f.cod_partido)
                    if not f.dat_desfiliacao
                ]
                dv = {
                    '@id': f"{self.portal_url}/@@vereadores/{p.cod_parlamentar}",
                    '@type': 'Vereador',
                    'id': str(p.cod_parlamentar),
                    'title': p.nom_parlamentar,
                    'description': p.nom_completo,
                    'votacao_id': str(v.cod_votacao),
                    'partido': partidos
                }
                m = {
                    'Sim': (lst_sim, 'Sim'),
                    'Nao': (lst_nao, 'Não'),
                    'Abstencao': (lst_abst, 'Abstenção'),
                    'Na Presid.': (lst_pres, 'Na Presidência'),
                    'Ausente': (lst_aus, 'Ausente'),
                }
                if v.vot_parlamentar in m:
                    tgt, lbl = m[v.vot_parlamentar]
                    dv['voto'] = lbl
                    tgt.append(dv)

            dic_item['votos'] = [{
                'favoravel': lst_sim,
                'contrario': lst_nao,
                'abstencao': lst_abst,
                'presidencia': lst_pres,
                'ausente': lst_aus,
            }]
            dic_item.update({
                'favoravel': len(lst_sim),
                'contrario': len(lst_nao),
                'abstencao': len(lst_abst),
                'presidencia': len(lst_pres),
                'ausente': len(lst_aus),
            })

            lst_materias.append(dic_item)

        sess = self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0)[0]
        t = self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sess.tip_sessao, ind_excluido=0)[0]
        desc_s = f"{sess.num_sessao_plen}ª Reunião {t.nom_sessao} – {DateTime(sess.dat_inicio_sessao,datefmt='international').strftime('%d/%m/%Y')}"
        return {
            '@id': f"{self.service_url}/id/{item_id}/votacao",
            '@type': 'votacaoNominal',
            'title': 'Lista de votação nominal',
            'description': desc_s,
            'items': lst_materias
        }

    def render(self, ano='', tipo=''):
        self.update_context()
        data = {
            '@id': self.service_url,
            '@type': 'SessoesPlenarias',
            'description': 'Lista de reuniões plenárias'
        }
        if self.tipo or self.ano:
            data.update(self.lista_sessoes(self.tipo, self.ano))
        elif self.item_id and self.votacao and not self.presenca:
            data.update(self._get_votacao(self.item_id))
        elif self.item_id and not self.votacao and self.presenca:
            data.update(self._get_presenca(self.item_id))
        elif self.item_id and not self.votacao and not self.presenca:
            data.update(self.get_sessao(self.item_id))
        else:
            data.update(self.help())
        return json.dumps(data, sort_keys=True, indent=3, ensure_ascii=False)
