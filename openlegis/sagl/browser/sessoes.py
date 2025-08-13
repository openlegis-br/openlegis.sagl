# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import name
from grokcore.security import require
from grokcore.view import View as GrokView
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface
import json
from DateTime import DateTime


@implementer(IPublishTraverse)
class Sessoes(GrokView):
    """API de sessões plenárias (lista, detalhe, presença e votação nominal)."""

    # Registro automático via grokcore
    context(Interface)
    name('sessoes')          # URL: @@sessoes
    require('zope2.View')

    # Estado de traversal
    subpath = None
    tipo = None
    ano = None
    item_id = None
    votacao = False
    presenca = False

    # ---------------- Traversal ----------------
    def publishTraverse(self, request, name):
        if self.subpath is None:
            self.subpath = []
        self.subpath.append(name)

        # flags
        self.votacao = self.votacao or (name == 'votacao')
        self.presenca = self.presenca or (name == 'presenca')

        # coleta params posicionais do caminho
        if len(self.subpath) >= 2:
            for i, val in enumerate(self.subpath[:-1]):
                nxt = self.subpath[i+1]
                if val == 'tipo':
                    self.tipo = nxt
                elif val == 'ano':
                    self.ano = nxt
                elif val == 'id':
                    self.item_id = nxt
        return self

    # ---------------- Utils ----------------
    def _portal_url(self):
        try:
            return self.context.portal_url().rstrip('/')
        except Exception:
            portal = self.context.portal_url.getPortalObject()
            return portal.absolute_url().rstrip('/')

    def _json(self, data):
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(data, sort_keys=True, indent=3, ensure_ascii=False)

    @staticmethod
    def _fmt_date(d):
        try:
            return DateTime(d, datefmt='international').strftime('%Y-%m-%d')
        except Exception:
            return ''

    @staticmethod
    def _fmt_date_br(d):
        try:
            return DateTime(d, datefmt='international').strftime('%d/%m/%Y')
        except Exception:
            return ''

    @staticmethod
    def _fmt_time(t):
        if not t:
            return ''
        try:
            return DateTime(t, datefmt='international').strftime('%H:%M')
        except Exception:
            return str(t)

    @staticmethod
    def _get_qs(form, key, default=None):
        """Pega um valor da querystring; aceita listas e retorna a 1ª ocorrência."""
        if key not in form:
            return default
        val = form.get(key)
        if isinstance(val, (list, tuple)):
            return val[0] if val else default
        return val

    @staticmethod
    def _get_qs_bool(form, key, default=False):
        """Interpreta '1/true/yes/on' como True; '0/false/no/off' como False."""
        val = Sessoes._get_qs(form, key, None)
        if val is None:
            return default
        s = str(val).strip().lower()
        if s in ('1', 'true', 'yes', 'y', 'on'):
            return True
        if s in ('0', 'false', 'no', 'n', 'off'):
            return False
        return default

    # ---------------- Inicialização por request ----------------
    def update_context(self):
        self.portal_url = self._portal_url()
        self.service_url = f"{self.portal_url}/@@sessoes"
        self.hoje = DateTime()

        # mantém o que veio via traversal...
        tipo = getattr(self, 'tipo', None)
        ano = getattr(self, 'ano', None)
        item_id = getattr(self, 'item_id', None)
        votacao = bool(getattr(self, 'votacao', False))
        presenca = bool(getattr(self, 'presenca', False))

        # ...mas a querystring tem precedência
        form = getattr(self.request, 'form', {}) or {}
        tipo_qs = self._get_qs(form, 'tipo', None)
        ano_qs = self._get_qs(form, 'ano', None)
        id_qs = self._get_qs(form, 'id', None)
        vot_qs = self._get_qs_bool(form, 'votacao', None)   # None = não sobrescreve
        pre_qs = self._get_qs_bool(form, 'presenca', None)

        self.tipo = tipo_qs if tipo_qs is not None else tipo
        self.ano = ano_qs if ano_qs is not None else ano
        self.item_id = id_qs if id_qs is not None else item_id
        self.votacao = vot_qs if vot_qs is not None else votacao
        self.presenca = pre_qs if pre_qs is not None else presenca

    # ---------------- Helpers de arquivos ----------------
    def _get_pauta(self, item_id):
        fn = f"{item_id}_pauta_sessao.pdf"
        try:
            pasta = self.context.sapl_documentos.pauta_sessao
        except Exception:
            pasta = None
        if pasta and hasattr(pasta, fn):
            return [{
                'content-type': 'application/pdf',
                'download': f"{self.portal_url}/sapl_documentos/pauta_sessao/{fn}",
                'filename': fn, 'size': ''
            }]
        return []

    def _get_ata(self, item_id):
        fn = f"{item_id}_ata_sessao.pdf"
        try:
            pasta = self.context.sapl_documentos.ata_sessao
        except Exception:
            pasta = None
        if pasta and hasattr(pasta, fn):
            return [{
                'content-type': 'application/pdf',
                'download': f"{self.portal_url}/sapl_documentos/ata_sessao/{fn}",
                'filename': fn, 'size': ''
            }]
        return []

    # ---------------- Blocos de dados ----------------
    def help(self):
        anos = [{'title': a.ano_sessao, 'id': a.ano_sessao}
                for a in self.context.zsql.ano_sessao_plenaria_obter_zsql()]
        tipos = [{'title': t.nom_sessao, 'id': t.tip_sessao}
                 for t in self.context.zsql.tipo_sessao_plenaria_obter_zsql(ind_excluido=0)]
        return {
            'exemplo': {'urlExemplo': f"{self.service_url}/tipo/{tipos[0]['id']}/ano/{anos[0]['id']}"} if (tipos and anos) else {},
            'filtros': {'ano': anos, 'tipo': tipos}
        }

    def _get_parlamentar(self, cod_parlamentar):
        recs = list(self.context.zsql.parlamentar_obter_zsql(
            cod_parlamentar=cod_parlamentar, ind_excluido=0))
        if not recs:
            return {}
        p = recs[0]
        partidos = []
        for f in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=cod_parlamentar):
            if not getattr(f, 'dat_desfiliacao', None):
                pts = list(self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=f.cod_partido))
                if pts:
                    partidos.append({'token': pts[0].sgl_partido, 'title': pts[0].nom_partido})
        return {
            '@type': 'Vereador',
            '@id': f"{self.portal_url}/@@vereadores/{p.cod_parlamentar}",
            'id': str(p.cod_parlamentar),
            'title': p.nom_parlamentar,
            'description': p.nom_completo,
            'partido': partidos
        }

    def lista_sessoes(self, tipo, ano):
        items = []
        for s in self.context.zsql.sessao_plenaria_obter_zsql(tip_sessao=tipo, ano_sessao=ano, ind_excluido=0):
            ts = list(self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=s.tip_sessao, ind_excluido=0))
            t = ts[0] if ts else None
            sid = str(s.cod_sessao_plen)
            data = self._fmt_date(getattr(s, 'dat_inicio_sessao', None))
            hr_ini = self._fmt_time(getattr(s, 'hr_inicio_sessao', None))
            titulo = f"{getattr(s, 'num_sessao_plen', '')}ª Reunião {getattr(t, 'nom_sessao', '')}" if t else f"{getattr(s, 'num_sessao_plen', '')}ª Reunião"
            desc = f"{self._fmt_date_br(getattr(s, 'dat_inicio_sessao', None))} {hr_ini}" if getattr(s, 'dat_inicio_sessao', None) else titulo
            items.append({
                '@id': f"{self.service_url}/id/{sid}",
                '@type': 'SessaoPlenaria',
                'id': sid,
                'title': titulo,
                'description': desc,
                'date': data,
                'type': getattr(t, 'nom_sessao', ''),
                'type_id': getattr(s, 'tip_sessao', ''),
                'startTime': hr_ini,
                'endTime': self._fmt_time(getattr(s, 'hr_fim_sessao', None)),
                '@id_votacao': f"{self.service_url}/id/{sid}/votacao",
                '@id_presenca': f"{self.service_url}/id/{sid}/presenca",
                'pauta': self._get_pauta(sid),
                'ata': self._get_ata(sid),
            })
        items.sort(key=lambda x: x['date'], reverse=True)
        return {'description': 'Lista de reuniões plenárias', 'items': items}

    def get_sessao(self, item_id):
        sess = list(self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0))
        if not sess:
            return {}
        s = sess[0]
        ts = list(self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=s.tip_sessao, ind_excluido=0))
        t = ts[0] if ts else None
        sid = str(s.cod_sessao_plen)
        data = self._fmt_date(getattr(s, 'dat_inicio_sessao', None))
        desc = f"{getattr(s, 'num_sessao_plen', '')}ª Reunião {getattr(t, 'nom_sessao', '')} - {self._fmt_date_br(getattr(s, 'dat_inicio_sessao', None))}" if getattr(s, 'dat_inicio_sessao', None) else ''
        return {
            '@type': 'SessaoPlenaria',
            '@id': f"{self.service_url}/id/{sid}",
            '@id_votacao': f"{self.service_url}/id/{sid}/votacao",
            '@id_presenca': f"{self.service_url}/id/{sid}/presenca",
            'id': sid,
            'date': data,
            'description': desc,
            'type': getattr(t, 'nom_sessao', ''),
            'type_id': getattr(s, 'tip_sessao', ''),
            'startTime': self._fmt_time(getattr(s, 'hr_inicio_sessao', None)),
            'endTime': self._fmt_time(getattr(s, 'hr_fim_sessao', None)),
            'title': f"{getattr(s, 'num_sessao_plen', '')}ª Reunião {getattr(t, 'nom_sessao', '')}",
            'pauta': self._get_pauta(sid),
            'ata': self._get_ata(sid),
        }

    def _get_presenca_abertura(self, item_id):
        presentes, ausentes, just = [], [], []
        for p in self.context.zsql.presenca_sessao_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0):
            dic = self._get_parlamentar(p.cod_parlamentar)
            if getattr(p, 'tip_frequencia', '') == 'P':
                presentes.append(dic)
            elif getattr(p, 'tip_frequencia', '') == 'F':
                ausentes.append(dic)
            elif getattr(p, 'tip_frequencia', '') == 'A':
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
        # Se houver regra diferente, ajustar aqui; por ora, replica a chamada regimental
        return self._get_presenca_abertura(item_id)

    def _get_presenca(self, item_id):
        sess = list(self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0))
        if not sess:
            return {}
        s = sess[0]
        ts = list(self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=s.tip_sessao, ind_excluido=0))
        t = ts[0] if ts else None
        desc = f"{getattr(s, 'num_sessao_plen', '')}ª Reunião {getattr(t, 'nom_sessao', '')} - {self._fmt_date_br(getattr(s, 'dat_inicio_sessao', None))}" if getattr(s, 'dat_inicio_sessao', None) else ''
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
        # Votações da ordem do dia desta sessão
        for ordem in self.context.zsql.votacao_ordem_dia_obter_zsql(cod_sessao_plen=int(item_id), ind_excluido=0):
            # Pauta (turno/quorum/tipo de votação)
            pautas = list(self.context.zsql.ordem_dia_obter_zsql(cod_ordem=ordem.cod_ordem, ind_excluido=0))
            pauta = pautas[0] if pautas else None

            dic_item = {}
            cod_mat = getattr(ordem, 'cod_materia', None)
            cod_par = getattr(ordem, 'cod_parecer', None)

            if getattr(ordem, 'tip_votacao', None) == 2 and cod_mat:
                mats = list(self.context.zsql.materia_obter_zsql(cod_materia=cod_mat, ind_excluido=0))
                if mats:
                    mat = mats[0]
                    dic_item.update({
                        "@id": f"{self.portal_url}/@@materias/{mat.cod_materia}",
                        "@type": 'Materia',
                        "title": f"{mat.des_tipo_materia} nº {mat.num_ident_basica}/{mat.ano_ident_basica}",
                        "id": str(mat.cod_materia),
                        "description": getattr(mat, 'txt_ementa', '') or '',
                    })
                    # autoria
                    auto = []
                    for a in self.context.zsql.autoria_obter_zsql(cod_materia=cod_mat):
                        auto.append({
                            'description': a.des_tipo_autor,
                            'id': str(a.cod_autor),
                            'title': a.nom_autor_join,
                            'primeiro_autor': bool(getattr(a, 'ind_primeiro_autor', 0)),
                        })
                    dic_item['autoria'] = auto

            elif cod_par:
                rels = list(self.context.zsql.relatoria_obter_zsql(cod_relatoria=cod_par))
                if rels:
                    par = rels[0]
                    coms = list(self.context.zsql.comissao_obter_zsql(cod_comissao=par.cod_comissao))
                    relp = list(self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=par.cod_parlamentar))
                    mats = list(self.context.zsql.materia_obter_zsql(cod_materia=par.cod_materia))
                    com = coms[0] if coms else None
                    rel = relp[0] if relp else None
                    mat = mats[0] if mats else None
                    fav = getattr(par, 'tip_conclusao', '') == 'F'
                    desc = (
                        f"Parecer {getattr(com, 'sgl_comissao', '')} nº {getattr(par, 'num_parecer', '')}/{getattr(par, 'ano_parecer', '')}, "
                        f"com relatoria de {getattr(rel, 'nom_parlamentar', '')}, "
                        f"{'FAVORÁVEL' if fav else 'CONTRÁRIO'} ao "
                        f"{getattr(mat, 'sgl_tipo_materia', '')} {getattr(mat, 'num_ident_basica', '')}/{getattr(mat, 'ano_ident_basica', '')}"
                    )
                    dic_item.update({
                        "@type": 'Parecer',
                        "id": str(getattr(par, 'cod_relatoria', '')),
                        "title": f"Parecer {getattr(com, 'sgl_comissao', '')} nº {getattr(par, 'num_parecer', '')}/{getattr(par, 'ano_parecer', '')}",
                        "description": desc,
                        "autoria": [{
                            "@id": f"{self.portal_url}/@@comissoes/{getattr(com, 'cod_comissao', '')}",
                            "@type": "Comissão",
                            "description": getattr(com, 'nom_comissao', ''),
                            "id": str(getattr(com, 'cod_comissao', '')),
                            "title": getattr(com, 'sgl_comissao', '')
                        }] if com else [],
                    })

            # metadados de votação (se houver pauta)
            if pauta:
                tv = list(self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=pauta.tip_votacao))
                trn = list(self.context.zsql.turno_discussao_obter_zsql(cod_turno=pauta.tip_turno))
                qr = list(self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=pauta.tip_quorum))
                dic_item.update({
                    "tipo_votacao": tv[0].des_tipo_votacao if tv else '',
                    "turno": trn[0].des_turno if trn else '',
                    "quorum": qr[0].des_quorum if qr else '',
                })

            # apuração textual
            res_list = []
            if getattr(ordem, 'tip_resultado_votacao', None):
                for r in self.context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=ordem.tip_resultado_votacao, ind_excluido=0):
                    res_list.append({'resultado': r.nom_resultado})
            dic_item['apuracao'] = res_list

            # votos nominais
            cod_vot = getattr(ordem, 'cod_votacao', None)
            lst_sim, lst_nao, lst_abst, lst_pres, lst_aus = [], [], [], [], []
            if cod_vot:
                for v in self.context.zsql.votacao_parlamentar_obter_zsql(cod_votacao=cod_vot, ind_excluido=0):
                    prs = list(self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=v.cod_parlamentar))
                    if not prs:
                        continue
                    p = prs[0]
                    partidos = []
                    for f in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=p.cod_parlamentar):
                        if not getattr(f, 'dat_desfiliacao', None):
                            pts = list(self.context.zsql.partido_obter_zsql(ind_excluido=0, cod_partido=f.cod_partido))
                            if pts:
                                partidos.append({'token': pts[0].sgl_partido, 'title': pts[0].nom_partido})
                    dv = {
                        '@id': f"{self.portal_url}/@@vereadores/{p.cod_parlamentar}",
                        '@type': 'Vereador',
                        'id': str(p.cod_parlamentar),
                        'title': p.nom_parlamentar,
                        'description': p.nom_completo,
                        'votacao_id': str(getattr(v, 'cod_votacao', '')),
                        'partido': partidos
                    }
                    mapping = {
                        'Sim': ('Sim', lst_sim),
                        'Nao': ('Não', lst_nao),
                        'Abstencao': ('Abstenção', lst_abst),
                        'Na Presid.': ('Na Presidência', lst_pres),
                        'Ausente': ('Ausente', lst_aus),
                    }
                    lbl_list = mapping.get(getattr(v, 'vot_parlamentar', ''), None)
                    if lbl_list:
                        lbl, target = lbl_list
                        dv['voto'] = lbl
                        target.append(dv)

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

        sess = list(self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item_id, ind_excluido=0))
        tdesc = ''
        if sess:
            s = sess[0]
            ts = list(self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=s.tip_sessao, ind_excluido=0))
            t = ts[0] if ts else None
            tdesc = f"{getattr(s, 'num_sessao_plen', '')}ª Reunião {getattr(t, 'nom_sessao', '')} – {self._fmt_date_br(getattr(s, 'dat_inicio_sessao', None))}" if getattr(s, 'dat_inicio_sessao', None) else ''

        return {
            '@id': f"{self.service_url}/id/{item_id}/votacao",
            '@type': 'votacaoNominal',
            'title': 'Lista de votação nominal',
            'description': tdesc,
            'items': lst_materias
        }

    # ---------------- Render ----------------
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
        return self._json(data)
