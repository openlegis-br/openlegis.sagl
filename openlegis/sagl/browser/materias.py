# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from xml.sax.saxutils import escape
from DateTime import DateTime
import json
import re
from z3c.saconfig import named_scoped_session
from sqlalchemy import create_engine, text

Session = named_scoped_session('minha_sessao')

@implementer(IPublishTraverse)
class Materias(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('materias')

    item_id = None

    def publishTraverse(self, request, name):
        request["TraversalRequestNameStack"] = []
        if re.match(r"^\d+$", name):
            self.item_id = name
        return self

    def help(self):
        # Obter anos
        with Session() as session:
            anos = session.execute(text("""
                SELECT DISTINCT ano_ident_basica
                  FROM materia_legislativa
                 WHERE ind_excluido = 0
              ORDER BY ano_ident_basica DESC
            """)).fetchall()
        lst_anos = [{"id": ano, "title": ano} for (ano,) in anos]

        # Obter tipos via ZSQL
        lst_tipos = []
        for t in self.context.zsql.tipo_materia_legislativa_obter_zsql(
            tip_natureza='P', ind_excluido=0
        ):
            lst_tipos.append({"id": t.tip_materia, "title": t.des_tipo_materia})

        return {
            "exemplo": {"urlExemplo": f"{self.service_url}?ano=2025&tipo=3"},
            "filtros": {"ano": lst_anos, "tipo": lst_tipos}
        }

    def lista(self, tipo, ano):
        # Consulta SQLAlchemy
        with Session() as session:
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

        lst = []
        for cod, num, ano_id, tipo_desc, dat_apres, txt in rows:
            sid = str(cod)
            item = {
                "@id": f"{self.service_url}/{sid}",
                "@type": "Materia",
                "id": sid,
                "title": f"{tipo_desc} nº {num}/{ano_id}",
                "description": escape(txt or ""),
                "date": str(dat_apres),
            }

            # authorship
            lista_aut = []
            for a in self.context.zsql.autoria_obter_zsql(cod_materia=cod):
                lista_aut.append({
                    "title": a.nom_autor_join,
                    "description": a.des_tipo_autor,
                    "firstAuthor": bool(a.ind_primeiro_autor)
                })
            item["authorship"] = lista_aut

            # file
            arquivo = f"{cod}_texto_integral.pdf"
            files = []
            if hasattr(self.context.sapl_documentos.materia, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{self.portal_url}/sapl_documentos/materia/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            item["file"] = files

            item["remoteUrl"] = (
                f"{self.portal_url}/consultas/materia/"
                f"materia_mostrar_proc?cod_materia={cod}"
            )
            lst.append(item)

        des_tipo = "matérias"
        if tipo:
            r = self.context.zsql.tipo_materia_legislativa_obter_zsql(
                tip_materia=tipo, tip_natureza='P', ind_excluido=0
            )
            if r:
                des_tipo = r[0].des_tipo_materia

        return {"description": f"Lista de {des_tipo} do ano de {ano}", "items": lst}

    def get_one(self, item_id):
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
            "description": escape(m.txt_ementa or ""),
            "date": DateTime(m.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d")
        }

        # authorship
        auth = []
        for a in self.context.zsql.autoria_obter_zsql(cod_materia=cod):
            auth.append({
                "title": a.nom_autor_join,
                "description": a.des_tipo_autor,
                "firstAuthor": bool(a.ind_primeiro_autor)
            })
        dic["authorship"] = auth

        # file
        arquivo = f"{cod}_texto_integral.pdf"
        files = []
        if hasattr(self.context.sapl_documentos.materia, arquivo):
            files.append({
                "content-type": "application/pdf",
                "download": f"{self.portal_url}/sapl_documentos/materia/{arquivo}",
                "filename": arquivo,
                "size": ""
            })
        dic["file"] = files

        dic["remoteUrl"] = (
            f"{self.portal_url}/consultas/materia/materia_mostrar_proc?cod_materia={cod}"
        )

        # quorum & processingRegime
        for q in self.context.zsql.quorum_votacao_obter_zsql(cod_quorum=m.tip_quorum):
            dic["quorum"] = q.des_quorum
            dic["quorum_id"] = str(q.cod_quorum)
        for r in self.context.zsql.regime_tramitacao_obter_zsql(
            cod_regime_tramitacao=m.cod_regime_tramitacao
        ):
            dic["processingRegime"] = r.des_regime_tramitacao
            dic["processingRegime_id"] = str(r.cod_regime_tramitacao)

        dic["inProgress"] = bool(m.ind_tramitacao == 1)

        # attached
        anex = []
        for a in self.context.zsql.anexada_obter_zsql(
            cod_materia_principal=m.cod_materia, ind_excluido=0
        ):
            mat = self.context.zsql.materia_obter_zsql(
                cod_materia=a.cod_materia_anexada, ind_excluido=0
            )[0]
            anex.append({
                "@type": "Materia",
                "@id": f"{self.service_url}/{mat.cod_materia}",
                "id": str(mat.cod_materia),
                "title": f"{mat.des_tipo_materia} nº {mat.num_ident_basica}/{mat.ano_ident_basica}",
                "description": mat.txt_ementa,
                "annexationDate": DateTime(a.dat_anexacao, datefmt='international').strftime("%Y-%m-%d")
            })
        dic["attached"] = anex

        # accessoryDocument
        docs = []
        for doc in self.context.zsql.documento_acessorio_obter_zsql(
            cod_materia=m.cod_materia, ind_excluido=0
        ):
            tp = self.context.zsql.tipo_documento_obter_zsql(tip_documento=doc.tip_documento)[0]
            arquivo = f"{doc.cod_documento}.pdf"
            files = []
            if hasattr(self.context.sapl_documentos.materia, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{self.portal_url}/sapl_documentos/materia/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            docs.append({
                "title": doc.nom_documento,
                "id": str(doc.cod_documento),
                "description": tp.des_tipo_documento,
                "authorship": doc.nom_autor_documento,
                "date": DateTime(doc.dat_documento, datefmt='international').strftime("%Y-%m-%d"),
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
            if hasattr(self.context.sapl_documentos.emenda, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{self.portal_url}/sapl_documentos/emenda/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            ems.append({
                "title": f"Emenda {em.des_tipo_emenda} nº {em.num_emenda}",
                "description": em.txt_ementa,
                "authorship": auth_em,
                "date": DateTime(em.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d"),
                "file": files
            })
        dic["amendment"] = ems

        # substitute
        subs = []
        for s in self.context.zsql.substitutivo_obter_zsql(cod_materia=m.cod_materia, ind_excluido=0):
            auth_sub = []
            for a in self.context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=s.cod_substitutivo, ind_excluido=0):
                auth_sub.append({
                    "title": a.nom_autor_join,
                    "description": a.des_tipo_autor
                })
            arquivo = f"{s.cod_substitutivo}_substitutivo.pdf"
            files = []
            if hasattr(self.context.sapl_documentos.substitutivo, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{self.portal_url}/sapl_documentos/substitutivo/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            subs.append({
                "title": f"Substitutivo nº {s.num_substitutivo}",
                "description": s.txt_ementa,
                "authorship": auth_sub,
                "date": DateTime(s.dat_apresentacao, datefmt='international').strftime("%Y-%m-%d"),
                "file": files
            })
        dic["substitute"] = subs

        # committeeOpinion
        ops = []
        for p in self.context.zsql.relatoria_obter_zsql(cod_materia=m.cod_materia):
            com = self.context.zsql.comissao_obter_zsql(cod_comissao=p.cod_comissao)[0]
            rel = self.context.zsql.parlamentar_obter_zsql(cod_parlamentar=p.cod_parlamentar)[0]
            desc = (
                "Relatoria de " + rel.nom_parlamentar +
                (", FAVORÁVEL" if p.tip_conclusao == 'F' else ", CONTRÁRIA")
            )
            arquivo = f"{p.cod_relatoria}_parecer.pdf"
            files = []
            if hasattr(self.context.sapl_documentos.parecer_comissao, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{self.portal_url}/sapl_documentos/parecer_comissao/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            ops.append({
                "title": f"Parecer {com.sgl_comissao} nº {p.num_parecer}/{p.ano_parecer}",
                "description": desc,
                "date": DateTime(p.dat_destit_relator, datefmt='international').strftime("%Y-%m-%d"),
                "authorship": [{
                    "@id": f"{self.portal_url}/@@comissoes/{com.cod_comissao}",
                    "@type": "Comissão",
                    "title": com.nom_comissao,
                    "description": com.sgl_comissao
                }],
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
            if hasattr(self.context.sapl_documentos.materia.tramitacao, arquivo):
                files.append({
                    "content-type": "application/pdf",
                    "download": f"{self.portal_url}/sapl_documentos/materia/tramitacao/{arquivo}",
                    "filename": arquivo,
                    "size": ""
                })
            prots.append({
                "title": t.des_status,
                "description": escape(t.txt_tramitacao),
                "date": DateTime(t.dat_tramitacao, datefmt='international').strftime("%Y-%m-%d %H:%M:%S"),
                "sourceUnit": self.context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao=t.cod_unid_tram_local)[0].nom_unidade_join,
                "destinationUnit": self.context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao=t.cod_unid_tram_dest)[0].nom_unidade_join,
                "last": bool(t.ind_ult_tramitacao == 1),
                "file": files
            })
        dic["processing"] = prots

        votos = []

        # 1) Expediente
        for vot in self.context.zsql.votacao_expediente_materia_obter_zsql(
                cod_materia=m.cod_materia, ind_excluido=0):
            sess = self.context.zsql.sessao_plenaria_obter_zsql(
                cod_sessao_plen=vot.cod_sessao_plen)[0]
            tipo_s = self.context.zsql.tipo_sessao_plenaria_obter_zsql(
                tip_sessao=sess.tip_sessao)[0]
            vr = {
                "@id": f"{self.portal_url}/@@sessoes/{sess.cod_sessao_plen}",
                "date": DateTime(sess.dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d"),
                "description": f"Expediente da {sess.num_sessao_plen}ª Reunião {tipo_s.nom_sessao}",
                "title": "",
                "votingType": self.context.zsql.votingType_obter_zsql(
                    tip_votacao=vot.tip_votacao)[0].des_votingType,
                "turn": ""
            }
            vr["title"] = vr["description"]
            if vot.tip_resultado_votacao is not None:
                vr["result"] = [{
                    "favorable": vot.num_votos_sim,
                    "contrary": vot.num_votos_nao,
                    "abstention": vot.num_abstencao
                }]
                vr["title"] = self.context.zsql.tipo_resultado_votacao_obter_zsql(
                    tip_resultado_votacao=vot.tip_resultado_votacao,
                    ind_excluido=0)[0].nom_resultado
            votos.append(vr)

        # 2) Ordem do Dia
        for vot in self.context.zsql.votacao_ordem_dia_obter_zsql(
                cod_materia=m.cod_materia, ind_excluido=0):
            sess = self.context.zsql.sessao_plenaria_obter_zsql(
                cod_sessao_plen=vot.cod_sessao_plen)[0]
            tipo_s = self.context.zsql.tipo_sessao_plenaria_obter_zsql(
                tip_sessao=sess.tip_sessao)[0]
            vr = {
                "@id": f"{self.portal_url}/@@sessoes/{sess.cod_sessao_plen}",
                "date": DateTime(sess.dat_inicio_sessao, datefmt='international').strftime("%Y-%m-%d"),
                "description": f"Ordem do Dia da {sess.num_sessao_plen}ª Reunião {tipo_s.nom_sessao}",
                "title": "",
                "votingType": self.context.zsql.tipo_votacao_obter_zsql(
                    tip_votacao=vot.tip_votacao)[0].des_tipo_votacao,
                "turn": self.context.zsql.turno_discussao_obter_zsql(
                    cod_turno=vot.tip_turno)[0].des_turno
            }
            vr["title"] = vr["description"]
            if vot.tip_resultado_votacao is not None:
                vr["result"] = [{
                    "favorable": vot.num_votos_sim,
                    "contrary": vot.num_votos_nao,
                    "abstention": vot.num_abstencao
                }]
                vr["title"] = self.context.zsql.tipo_resultado_votacao_obter_zsql(
                    tip_resultado_votacao=vot.tip_resultado_votacao,
                    ind_excluido=0)[0].nom_resultado
            votos.append(vr)

        # 3) Votos nominais (quando tip_votacao == 2)
        for vr in votos:
            # detecta se é nominal pelo código da votação
            # (pode já vir de vot.tip_votacao == 2)
            if vr.get("votingType", "").lower() == "nominal":
                # extrai sessão do @id
                sess_id = int(vr["@id"].rsplit("/", 1)[-1])
                # busca o registro de votacao correto
                registros = self.context.zsql.votacao_expediente_materia_obter_zsql(
                    cod_sessao_plen=sess_id,
                    cod_materia=m.cod_materia,
                    ind_excluido=0
                ) or self.context.zsql.votacao_ordem_dia_obter_zsql(
                    cod_sessao_plen=sess_id,
                    cod_materia=m.cod_materia,
                    ind_excluido=0
                )
                if not registros:
                    continue
                vot = registros[0]

                lst_sim = []
                lst_nao = []
                lst_abst = []
                lst_pres = []
                lst_aus = []

                for voto in self.context.zsql.votacao_parlamentar_obter_zsql(
                        cod_votacao=vot.cod_votacao, ind_excluido=0):
                    parl = self.context.zsql.parlamentar_obter_zsql(
                        cod_parlamentar=voto.cod_parlamentar)[0]
                    dic_v = {
                        "@id": f"{self.portal_url}/@@vereador?id={parl.cod_parlamentar}",
                        "@type": "Vereador",
                        "title": parl.nom_parlamentar,
                        "description": parl.nom_completo,
                        "voting_id": str(voto.cod_votacao),
                        "party": []
                    }
                    for fil in self.context.zsql.filiacao_obter_zsql(
                            ind_excluido=0, cod_parlamentar=parl.cod_parlamentar):
                        for part in self.context.zsql.partido_obter_zsql(
                                ind_excluido=0, cod_partido=fil.cod_partido):
                            dic_v["party"].append({
                                "token": part.sgl_partido,
                                "title": part.nom_partido
                            })

                    if voto.vot_parlamentar == "Sim":
                        dic_v["vote"] = "Sim"
                        lst_sim.append(dic_v)
                    elif voto.vot_parlamentar == "Nao":
                        dic_v["vote"] = "Não"
                        lst_nao.append(dic_v)
                    elif voto.vot_parlamentar == "Abstencao":
                        dic_v["vote"] = "Abstenção"
                        lst_abst.append(dic_v)
                    elif voto.vot_parlamentar == "Na Presid.":
                        dic_v["vote"] = "Na Presidência"
                        lst_pres.append(dic_v)
                    elif voto.vot_parlamentar == "Ausente":
                        dic_v["vote"] = "Ausente"
                        lst_aus.append(dic_v)

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

    def render(self, tipo='', ano=''):
        # inicializa URLs
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url.portal_url()
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

        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8").decode("utf-8")
