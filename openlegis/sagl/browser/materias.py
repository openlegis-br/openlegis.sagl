# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import name
from grokcore.security import require
from grokcore.view import View as GrokView
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface
from xml.sax.saxutils import escape
from DateTime import DateTime
import json
import re

from z3c.saconfig import named_scoped_session
from sqlalchemy import text

Session = named_scoped_session('minha_sessao')


@implementer(IPublishTraverse)
class Materias(GrokView):
    """API de matérias legislativas (registro automático via grokcore)."""

    context(Interface)
    name('materias')          # URL: @@materias
    require('zope2.View')

    item_id = None

    # ---------------- Traversal ----------------

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        if re.match(r"^\d+$", name):
            self.item_id = name
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
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)

    # ---------------- Handlers ----------------

    def help(self):
        """Fornece filtros (anos e tipos) e exemplo de uso."""
        session = Session()
        try:
            anos = session.execute(text("""
                SELECT DISTINCT ano_ident_basica
                  FROM materia_legislativa
                 WHERE ind_excluido = 0
              ORDER BY ano_ident_basica DESC
            """)).fetchall()
        finally:
            # Em leitura simples, scoped_session não requer close(),
            # mas fechar explicitamente não atrapalha.
            session.close()

        lst_anos = [{"id": str(ano), "title": str(ano)} for (ano,) in anos]

        lst_tipos = []
        for t in self.context.zsql.tipo_materia_legislativa_obter_zsql(
            tip_natureza='P', ind_excluido=0
        ):
            lst_tipos.append({"id": str(t.tip_materia), "title": t.des_tipo_materia})

        return {
            "exemplo": {
                "urlExemplo": f"{self.service_url}?ano=2025&tipo=3"
            },
            "filtros": {
                "ano": lst_anos,
                "tipo": lst_tipos
            }
        }

    def lista(self, tipo, ano):
        """Lista matérias por tipo e ano."""
        portal_url = self.portal_url
        session = Session()
        try:
            rows = session.execute(text("""
                SELECT m.cod_materia,
                       m.num_ident_basica,
                       m.ano_ident_basica,
                       t.des_tipo_materia,
                       m.dat_apresentacao,
                       m.txt_ementa
                  FROM materia_legislativa m
             LEFT JOIN tipo_materia_legislativa t
                    ON m.tip_id_basica = t.tip_materia
                 WHERE m.tip_id_basica = :tipo
                   AND m.ano_ident_basica = :ano
                   AND m.ind_excluido = 0
              ORDER BY DATE(m.dat_apresentacao) DESC,
                       m.num_ident_basica DESC
            """), {"tipo": tipo, "ano": ano}).fetchall()
        finally:
            session.close()

        items = []
        for cod, num, ano_id, tipo_desc, dat_apres, txt in rows:
            sid = str(cod)
            item = {
                "@id": f"{self.service_url}/{sid}",
                "@type": "Materia",
                "id": sid,
                "title": f"{tipo_desc} nº {num}/{ano_id}",
                "description": escape(txt or ""),
                "date": str(dat_apres) if dat_apres else "",
            }

            # authorship
            lista_aut = []
            for a in self.context.zsql.autoria_obter_zsql(cod_materia=cod):
                lista_aut.append({
                    "title": a.nom_autor_join,
                    "description": a.des_tipo_autor,
                    "firstAuthor": bool(getattr(a, 'ind_primeiro_autor', 0)),
                })
            item["authorship"] = lista_aut

            # file
            arquivo = f"{cod}_texto_integral.pdf"
            files = []
            try:
                pasta_materia = self.context.sapl_documentos.materia
            except Exception:
                pasta_materia = None
            if pasta_materia and hasattr(pasta_materia, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{portal_url}/sapl_documentos/materia/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            item["file"] = files

            # URL do processo no SAPL
            item["remoteUrl"] = (
                f"{portal_url}/consultas/materia/materia_mostrar_proc?cod_materia={cod}"
            )

            items.append(item)

        des_tipo = "matérias"
        if tipo:
            r = list(self.context.zsql.tipo_materia_legislativa_obter_zsql(
                tip_materia=tipo, tip_natureza='P', ind_excluido=0
            ))
            if r:
                des_tipo = r[0].des_tipo_materia

        return {
            "description": f"Lista de {des_tipo} do ano de {ano}",
            "items": items
        }

    def get_one(self, item_id):
        """Detalhes de uma matéria específica."""
        portal_url = self.portal_url
        cod = int(item_id)

        rec = list(self.context.zsql.materia_obter_zsql(cod_materia=cod, ind_excluido=0))
        if not rec:
            return {}
        m = rec[0]

        dic = {
            "@type": "Materia",
            "@id": f"{self.service_url}/{cod}",
            "id": str(cod),
            "title": f"{m.des_tipo_materia} nº {m.num_ident_basica}/{m.ano_ident_basica}",
            "description": escape(getattr(m, 'txt_ementa', '') or ""),
            "date": DateTime(m.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d")
                    if getattr(m, 'dat_apresentacao', None) else "",
        }

        # authorship
        auth = []
        for a in self.context.zsql.autoria_obter_zsql(cod_materia=cod):
            auth.append({
                "title": a.nom_autor_join,
                "description": a.des_tipo_autor,
                "firstAuthor": bool(getattr(a, 'ind_primeiro_autor', 0))
            })
        dic["authorship"] = auth

        # file
        arquivo = f"{cod}_texto_integral.pdf"
        files = []
        try:
            pasta_materia = self.context.sapl_documentos.materia
        except Exception:
            pasta_materia = None
        if pasta_materia and hasattr(pasta_materia, arquivo):
            files.append({
                "content-type": "application/pdf",
                "download": f"{portal_url}/sapl_documentos/materia/{arquivo}",
                "filename": arquivo,
                "size": ""
            })
        dic["file"] = files

        dic["remoteUrl"] = (
            f"{portal_url}/consultas/materia/materia_mostrar_proc?cod_materia={cod}"
        )

        # quorum & processingRegime
        qs = list(self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=getattr(m, 'tip_quorum', None)))
        if qs:
            dic["quorum"] = qs[0].des_quorum
            dic["quorum_id"] = str(qs[0].cod_quorum)
        rs = list(self.context.zsql.regime_tramitacao_obter_zsql(
            cod_regime_tramitacao=getattr(m, 'cod_regime_tramitacao', None)
        ))
        if rs:
            dic["processingRegime"] = rs[0].des_regime_tramitacao
            dic["processingRegime_id"] = str(rs[0].cod_regime_tramitacao)

        dic["inProgress"] = bool(getattr(m, 'ind_tramitacao', 0) == 1)

        # attached
        anex = []
        for a in self.context.zsql.anexada_obter_zsql(
            cod_materia_principal=m.cod_materia, ind_excluido=0
        ):
            mats = list(self.context.zsql.materia_obter_zsql(
                cod_materia=a.cod_materia_anexada, ind_excluido=0
            ))
            if not mats:
                continue
            mat = mats[0]
            anex.append({
                "@type": "Materia",
                "@id": f"{self.service_url}/{mat.cod_materia}",
                "id": str(mat.cod_materia),
                "title": f"{mat.des_tipo_materia} nº {mat.num_ident_basica}/{mat.ano_ident_basica}",
                "description": getattr(mat, 'txt_ementa', ''),
                "annexationDate": DateTime(a.dat_anexacao, datefmt='international').strftime("%Y-%m-%d")
                                   if getattr(a, 'dat_anexacao', None) else ""
            })
        dic["attached"] = anex

        # accessoryDocument
        docs = []
        for doc in self.context.zsql.documento_acessorio_obter_zsql(
            cod_materia=m.cod_materia, ind_excluido=0
        ):
            tps = list(self.context.zsql.tipo_documento_obter_zsql(tip_documento=doc.tip_documento))
            tp = tps[0] if tps else None
            arquivo = f"{doc.cod_documento}.pdf"
            files = []
            try:
                pasta_materia = self.context.sapl_documentos.materia
            except Exception:
                pasta_materia = None
            if pasta_materia and hasattr(pasta_materia, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{portal_url}/sapl_documentos/materia/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            docs.append({
                "title": getattr(doc, 'nom_documento', ''),
                "id": str(getattr(doc, 'cod_documento', '')),
                "description": getattr(tp, 'des_tipo_documento', '') if tp else '',
                "authorship": getattr(doc, 'nom_autor_documento', ''),
                "date": DateTime(doc.dat_documento, datefmt='international').strftime("%Y-%m-%d")
                        if getattr(doc, 'dat_documento', None) else "",
                "file": files
            })
        dic["accessoryDocument"] = docs

        # amendment
        ems = []
        for em in self.context.zsql.emenda_obter_zsql(cod_materia=m.cod_materia, ind_excluido=0):
            auth_em = []
            for a in self.context.zsql.autoria_emenda_obter_zsql(cod_emenda=em.cod_emenda, ind_excluido=0):
                auth_em.append({
                    "title": a.nom_autor_join,
                    "description": a.des_tipo_autor
                })
            arquivo = f"{em.cod_emenda}_emenda.pdf"
            files = []
            try:
                pasta_emenda = self.context.sapl_documentos.emenda
            except Exception:
                pasta_emenda = None
            if pasta_emenda and hasattr(pasta_emenda, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{portal_url}/sapl_documentos/emenda/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            ems.append({
                "title": f"Emenda {em.des_tipo_emenda} nº {em.num_emenda}",
                "description": getattr(em, 'txt_ementa', ''),
                "authorship": auth_em,
                "date": DateTime(em.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d")
                        if getattr(em, 'dat_apresentacao', None) else "",
                "file": files
            })
        dic["amendment"] = ems

        # substitute
        subs = []
        for s in self.context.zsql.substitutivo_obter_zsql(cod_materia=m.cod_materia, ind_excluido=0):
            auth_sub = []
            for a in self.context.zsql.autoria_substitutivo_obter_zsql(
                cod_substitutivo=s.cod_substitutivo, ind_excluido=0
            ):
                auth_sub.append({
                    "title": a.nom_autor_join,
                    "description": a.des_tipo_autor
                })
            arquivo = f"{s.cod_substitutivo}_substitutivo.pdf"
            files = []
            try:
                pasta_subst = self.context.sapl_documentos.substitutivo
            except Exception:
                pasta_subst = None
            if pasta_subst and hasattr(pasta_subst, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{portal_url}/sapl_documentos/substitutivo/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            subs.append({
                "title": f"Substitutivo nº {s.num_substitutivo}",
                "description": getattr(s, 'txt_ementa', ''),
                "authorship": auth_sub,
                "date": DateTime(s.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d")
                        if getattr(s, 'dat_apresentacao', None) else "",
                "file": files
            })
        dic["substitute"] = subs

        # committeeOpinion
        ops = []
        for p in self.context.zsql.relatoria_obter_zsql(cod_materia=m.cod_materia):
            coms = list(self.context.zsql.comissao_obter_zsql(cod_comissao=p.cod_comissao))
            rels = list(self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=p.cod_parlamentar))
            com = coms[0] if coms else None
            rel = rels[0] if rels else None

            conclusao = getattr(p, 'tip_conclusao', '')
            conclusao_str = ", FAVORÁVEL" if conclusao == 'F' else (", CONTRÁRIA" if conclusao == 'C' else "")
            desc = "Relatoria de " + (getattr(rel, 'nom_parlamentar', '') if rel else '') + conclusao_str

            arquivo = f"{p.cod_relatoria}_parecer.pdf"
            files = []
            try:
                pasta_parecer = self.context.sapl_documentos.parecer_comissao
            except Exception:
                pasta_parecer = None
            if pasta_parecer and hasattr(pasta_parecer, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{portal_url}/sapl_documentos/parecer_comissao/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            ops.append({
                "title": f"Parecer {getattr(com, 'sgl_comissao', '')} nº {getattr(p, 'num_parecer', '')}/{getattr(p, 'ano_parecer', '')}",
                "description": desc,
                "date": DateTime(getattr(p, 'dat_destit_relator', None), datefmt='international').strftime("%Y-%m-%d")
                        if getattr(p, 'dat_destit_relator', None) else "",
                "authorship": [{
                    "@id": f"{portal_url}/@@comissoes/{getattr(com, 'cod_comissao', '')}",
                    "@type": "Comissão",
                    "title": getattr(com, 'nom_comissao', ''),
                    "description": getattr(com, 'sgl_comissao', '')
                }] if com else [],
                "file": files
            })
        dic["committeeOpinion"] = ops

        # processing (tramitações)
        prots = []
        for t in self.context.zsql.tramitacao_obter_zsql(
            cod_materia=m.cod_materia, ind_encaminha=1, ind_excluido=0
        ):
            arquivo = f"{t.cod_tramitacao}_tram.pdf"
            files = []
            try:
                pasta_tram = self.context.sapl_documentos.materia.tramitacao
            except Exception:
                pasta_tram = None
            if pasta_tram and hasattr(pasta_tram, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{portal_url}/sapl_documentos/materia/tramitacao/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            src = list(self.context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao=t.cod_unid_tram_local))
            dst = list(self.context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao=t.cod_unid_tram_dest))
            prots.append({
                "title": t.des_status,
                "description": escape(getattr(t, 'txt_tramitacao', '') or ""),
                "date": DateTime(t.dat_tramitacao, datefmt='international').strftime("%Y-%m-%d %H:%M:%S")
                        if getattr(t, 'dat_tramitacao', None) else "",
                "sourceUnit": src[0].nom_unidade_join if src else "",
                "destinationUnit": dst[0].nom_unidade_join if dst else "",
                "last": bool(getattr(t, 'ind_ult_tramitacao', 0) == 1),
                "file": files
            })
        dic["processing"] = prots

        # voteResult (expediente + ordem do dia + nominais)
        votos = []
        # 1) Expediente
        for vot in self.context.zsql.votacao_expediente_materia_obter_zsql(
            cod_materia=m.cod_materia, ind_excluido=0
        ):
            sess = list(self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=vot.cod_sessao_plen))
            tipo_s = list(self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sess[0].tip_sessao)) if sess else []
            votingType = ""
            vt = list(self.context.zsql.votingType_obter_zsql(tip_votacao=vot.tip_votacao)) if getattr(vot, 'tip_votacao', None) else []
            if vt:
                votingType = vt[0].des_votingType
            vr = {
                "@id": f"{portal_url}/@@sessoes/{sess[0].cod_sessao_plen}" if sess else "",
                "date": DateTime(sess[0].dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d") if sess else "",
                "description": f"Expediente da {sess[0].num_sessao_plen}ª Reunião {tipo_s[0].nom_sessao}" if sess and tipo_s else "",
                "title": "",
                "votingType": votingType,
                "turn": ""
            }
            vr["title"] = vr["description"]
            if getattr(vot, 'tip_resultado_votacao', None) is not None:
                vr["result"] = [{
                    "favorable": getattr(vot, 'num_votos_sim', 0),
                    "contrary": getattr(vot, 'num_votos_nao', 0),
                    "abstention": getattr(vot, 'num_abstencao', 0)
                }]
                tr = list(self.context.zsql.tipo_resultado_votacao_obter_zsql(
                    tip_resultado_votacao=vot.tip_resultado_votacao, ind_excluido=0
                ))
                if tr:
                    vr["title"] = tr[0].nom_resultado
            votos.append(vr)

        # 2) Ordem do Dia
        for vot in self.context.zsql.votacao_ordem_dia_obter_zsql(
            cod_materia=m.cod_materia, ind_excluido=0
        ):
            sess = list(self.context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=vot.cod_sessao_plen))
            tipo_s = list(self.context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sess[0].tip_sessao)) if sess else []
            tv = list(self.context.zsql.tipo_votacao_obter_zsql(tip_votacao=vot.tip_votacao)) if getattr(vot, 'tip_votacao', None) else []
            trn = list(self.context.zsql.turno_discussao_obter_zsql(cod_turno=vot.tip_turno)) if getattr(vot, 'tip_turno', None) else []
            vr = {
                "@id": f"{portal_url}/@@sessoes/{sess[0].cod_sessao_plen}" if sess else "",
                "date": DateTime(sess[0].dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d") if sess else "",
                "description": f"Ordem do Dia da {sess[0].num_sessao_plen}ª Reunião {tipo_s[0].nom_sessao}" if sess and tipo_s else "",
                "title": "",
                "votingType": tv[0].des_tipo_votacao if tv else "",
                "turn": trn[0].des_turno if trn else ""
            }
            vr["title"] = vr["description"]
            if getattr(vot, 'tip_resultado_votacao', None) is not None:
                vr["result"] = [{
                    "favorable": getattr(vot, 'num_votos_sim', 0),
                    "contrary": getattr(vot, 'num_votos_nao', 0),
                    "abstention": getattr(vot, 'num_abstencao', 0)
                }]
                tr = list(self.context.zsql.tipo_resultado_votacao_obter_zsql(
                    tip_resultado_votacao=vot.tip_resultado_votacao, ind_excluido=0
                ))
                if tr:
                    vr["title"] = tr[0].nom_resultado
            votos.append(vr)

        # 3) Votos nominais (se o tipo indicar)
        for vr in votos:
            if (vr.get("votingType", "") or "").lower() == "nominal":
                try:
                    sess_id = int(vr["@id"].rsplit("/", 1)[-1])
                except Exception:
                    continue

                registros = (list(self.context.zsql.votacao_expediente_materia_obter_zsql(
                    cod_sessao_plen=sess_id, cod_materia=m.cod_materia, ind_excluido=0
                )) or list(self.context.zsql.votacao_ordem_dia_obter_zsql(
                    cod_sessao_plen=sess_id, cod_materia=m.cod_materia, ind_excluido=0
                )))
                if not registros:
                    continue
                vot = registros[0]

                lst_sim, lst_nao, lst_abst, lst_pres, lst_aus = [], [], [], [], []
                for voto in self.context.zsql.votacao_parlamentar_obter_zsql(
                    cod_votacao=vot.cod_votacao, ind_excluido=0
                ):
                    parl = list(self.context.zsql.parlamentar_obter_zsql(
                        cod_parlamentar=voto.cod_parlamentar
                    ))
                    if not parl:
                        continue
                    parl = parl[0]
                    dic_v = {
                        "@id": f"{portal_url}/@@vereadores/{parl.cod_parlamentar}",
                        "@type": "Vereador",
                        "title": parl.nom_parlamentar,
                        "description": parl.nom_completo,
                        "voting_id": str(voto.cod_votacao),
                        "party": []
                    }
                    for fil in self.context.zsql.filiacao_obter_zsql(
                        ind_excluido=0, cod_parlamentar=parl.cod_parlamentar
                    ):
                        for part in self.context.zsql.partido_obter_zsql(
                            ind_excluido=0, cod_partido=fil.cod_partido
                        ):
                            dic_v["party"].append({
                                "token": part.sgl_partido,
                                "title": part.nom_partido
                            })

                    v = getattr(voto, 'vot_parlamentar', '')
                    if v == "Sim":
                        dic_v["vote"] = "Sim";        lst_sim.append(dic_v)
                    elif v == "Nao":
                        dic_v["vote"] = "Não";        lst_nao.append(dic_v)
                    elif v == "Abstencao":
                        dic_v["vote"] = "Abstenção";  lst_abst.append(dic_v)
                    elif v == "Na Presid.":
                        dic_v["vote"] = "Na Presidência"; lst_pres.append(dic_v)
                    elif v == "Ausente":
                        dic_v["vote"] = "Ausente";    lst_aus.append(dic_v)

                vr["votes"] = [{
                    "favorable": lst_sim,
                    "contrary": lst_nao,
                    "abstention": lst_abst,
                    "presidency": lst_pres,
                    "absent": lst_aus
                }]
                vr["result"] = [{
                    "favorable": len(lst_sim),
                    "contrary": len(lst_nao),
                    "abstention": len(lst_abst),
                    "presidency": len(lst_pres),
                    "absent": len(lst_aus)
                }]

        dic["voteResult"] = votos

        return dic

    # ---------------- Render ----------------

    def render(self, tipo='', ano=''):
        # inicializa URLs e datas
        self.portal_url = self._portal_url()
        self.service_url = f"{self.portal_url}/@@materias"
        self.hoje = DateTime()

        data = {
            "@id": self.service_url,
            "@type": "Materias",
            "description": "Lista de matérias legislativas",
        }
        if self.item_id:
            data.update(self.get_one(self.item_id))
        elif tipo and ano:
            data.update(self.lista(tipo, ano))
        else:
            data.update(self.help())

        return self._json(data)
