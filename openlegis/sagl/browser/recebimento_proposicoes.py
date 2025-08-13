# -*- coding: utf-8 -*-
import csv
import io
import json
import logging
import traceback
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload
from z3c.saconfig import named_scoped_session
from zope.component import queryUtility
from zope.interface import Interface

from grokcore.component import context
from grokcore.view import View as GrokView, name
from grokcore.security import require

from openlegis.sagl.interfaces import ISAPLDocumentManager
from openlegis.sagl.models.models import (
    AssinaturaDocumento,
    Autor,
    Comissao,
    DocumentoAcessorio,
    MateriaLegislativa,
    Parlamentar,
    Proposicao,
    TipoProposicao,
    Usuario,
)

Session = named_scoped_session("minha_sessao")

logger = logging.getLogger("proposicoes")
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------
# Base com utilitários compartilhados
# ---------------------------------------------------------------------
class ProposicoesAPIBase:
    def _verificar_permissao_caixa(self, caixa: str) -> bool:
        roles = self._get_user_roles()
        if caixa in {"revisao", "assinatura", "incorporado", "devolvido", "pedido_devolucao"}:
            return any(
                r
                in roles
                for r in {
                    "Revisor Proposicao",
                    "Chefia Revisão",
                    "Operador",
                    "Operador Materia",
                    "Operador Revisao",
                }
            )
        if caixa == "protocolo":
            return any(r in roles for r in {"Operador", "Operador Materia"})
        return False

    def _get_user_roles(self):
        try:
            portal = self.request.PARENTS[0]
            mtool = portal.portal_membership
            user = mtool.getAuthenticatedMember()
            return set(user.getRoles())
        except Exception:
            return set()

    def _get_cod_usuario(self):
        try:
            col_username = self.request.AUTHENTICATED_USER.getUserName()
            session = Session()
            try:
                usuario = (
                    session.query(Usuario)
                    .filter(
                        Usuario.col_username == col_username,
                        Usuario.ind_excluido == 0,
                        Usuario.ind_ativo == 1,
                    )
                    .first()
                )
                return usuario.cod_usuario if usuario else None
            finally:
                session.close()
        except Exception as e:
            logger.warning("[proposicoes] Não foi possível obter cod_usuario: %s", e)
            return None

    def _aplicar_filtros_caixa(self, query, caixa):
        session = Session()
        try:
            if caixa == "revisao":
                roles = self._get_user_roles()
                if "Revisor Proposicao" in roles:
                    cod_revisor = self._get_cod_usuario()
                    if cod_revisor:
                        return query.filter(
                            Proposicao.dat_envio.isnot(None),
                            Proposicao.dat_recebimento.is_(None),
                            Proposicao.dat_solicitacao_devolucao.is_(None),
                            Proposicao.dat_devolucao.is_(None),
                            Proposicao.cod_revisor == cod_revisor,
                        )
                return query.filter(
                    Proposicao.dat_envio.isnot(None),
                    Proposicao.dat_recebimento.is_(None),
                    Proposicao.dat_solicitacao_devolucao.is_(None),
                    Proposicao.dat_devolucao.is_(None),
                )

            if caixa == "assinatura":
                pendentes_subq = (
                    session.query(AssinaturaDocumento.codigo)
                    .filter(
                        AssinaturaDocumento.tipo_doc == "proposicao",
                        AssinaturaDocumento.ind_excluido == 0,
                        AssinaturaDocumento.ind_assinado == 0,
                    )
                    .distinct()
                    .subquery()
                )
                return query.filter(
                    Proposicao.dat_envio.isnot(None),
                    Proposicao.dat_recebimento.is_(None),
                    Proposicao.dat_solicitacao_devolucao.is_(None),
                    Proposicao.dat_devolucao.is_(None),
                ).filter(
                    or_(
                        Proposicao.cod_proposicao.in_(select(pendentes_subq)),
                        True,  # permite pós-filtro por existência de .pdf / _signed.pdf
                    )
                )

            if caixa == "protocolo":
                from sqlalchemy.sql import case

                total_assinaturas = func.count(AssinaturaDocumento.id)
                assinadas = func.sum(case((AssinaturaDocumento.ind_assinado == 1, 1), else_=0))
                todas_assinadas_subq = (
                    session.query(AssinaturaDocumento.codigo)
                    .filter(
                        AssinaturaDocumento.ind_excluido == 0,
                        AssinaturaDocumento.tipo_doc == "proposicao",
                    )
                    .group_by(AssinaturaDocumento.codigo)
                    .having(total_assinaturas == assinadas)
                    .subquery()
                )
                return query.filter(
                    Proposicao.dat_envio.isnot(None),
                    Proposicao.dat_recebimento.is_(None),
                    Proposicao.dat_solicitacao_devolucao.is_(None),
                    Proposicao.dat_devolucao.is_(None),
                ).filter(
                    or_(
                        ~Proposicao.cod_proposicao.in_(
                            session.query(AssinaturaDocumento.codigo).filter(
                                AssinaturaDocumento.ind_excluido == 0,
                                AssinaturaDocumento.tipo_doc == "proposicao",
                            )
                        ),
                        Proposicao.cod_proposicao.in_(select(todas_assinadas_subq)),
                    )
                )

            if caixa == "incorporado":
                return query.filter(
                    Proposicao.ind_excluido == 0,
                    Proposicao.dat_recebimento.isnot(None),
                    Proposicao.cod_mat_ou_doc.isnot(None),
                )

            if caixa == "devolvido":
                return query.filter(Proposicao.dat_devolucao.isnot(None))

            if caixa == "pedido_devolucao":
                return query.filter(
                    Proposicao.dat_solicitacao_devolucao.isnot(None),
                    Proposicao.dat_devolucao.is_(None),
                )

            return query
        finally:
            session.close()

    def _aplicar_filtros_adicionais(self, query):
        # texto livre
        search_term = (self.request.form.get("q") or "").strip()
        if search_term:
            like = f"%{search_term}%"
            query = query.filter(
                or_(
                    Proposicao.txt_descricao.ilike(like),
                    TipoProposicao.des_tipo_proposicao.ilike(like),
                    Autor.nom_autor.ilike(like),
                    Parlamentar.nom_parlamentar.ilike(like),
                    Parlamentar.nom_completo.ilike(like),
                    Comissao.nom_comissao.ilike(like),
                    Comissao.sgl_comissao.ilike(like),
                )
            )

        # tipo
        tipo = (self.request.form.get("tipo") or "").strip()
        if tipo:
            query = query.filter(TipoProposicao.des_tipo_proposicao.ilike(f"%{tipo}%"))

        # autor
        autor = (self.request.form.get("autor") or "").strip()
        if autor:
            like_aut = f"%{autor}%"
            query = query.filter(
                or_(
                    Autor.nom_autor.ilike(like_aut),
                    Parlamentar.nom_parlamentar.ilike(like_aut),
                    Parlamentar.nom_completo.ilike(like_aut),
                    Comissao.nom_comissao.ilike(like_aut),
                    Comissao.sgl_comissao.ilike(like_aut),
                )
            )

        # assunto / NPE
        assunto = (self.request.form.get("assunto") or "").strip()
        if assunto:
            assunto_limpo = assunto.upper().replace(" ", "")
            m = __import__("re").match(r"^(NPE)?(\d+)$", assunto_limpo)
            if m:
                npe_num = int(m.group(2))
                query = query.filter(Proposicao.cod_proposicao == npe_num)
            else:
                query = query.filter(Proposicao.txt_descricao.ilike(f"%{assunto}%"))

        # intervalo de datas
        campo_data = self.request.form.get("campo_data", "dat_envio")
        dt_inicio = self.request.form.get("dt_inicio")
        dt_fim = self.request.form.get("dt_fim")
        if campo_data and (dt_inicio or dt_fim):
            coluna = getattr(Proposicao, campo_data, None)
            if coluna is not None:
                if dt_inicio:
                    try:
                        query = query.filter(coluna >= datetime.strptime(dt_inicio, "%Y-%m-%d"))
                    except Exception:
                        return self._responder_erro("Data inicial inválida", 400)
                if dt_fim:
                    try:
                        query = query.filter(
                            coluna
                            <= datetime.strptime(dt_fim, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                        )
                    except Exception:
                        return self._responder_erro("Data final inválida", 400)
        return query

    def _verificar_documentos_fisicos(self, proposicoes, caixa):
        doc_manager = queryUtility(ISAPLDocumentManager)
        if not doc_manager or not proposicoes:
            return []

        resultados = []
        arquivos_necessarios = []

        for prop in proposicoes:
            pid = str(prop.cod_proposicao)
            if caixa == "revisao":
                arquivos_necessarios.append((pid, f"{pid}.odt", "odt"))
            elif caixa == "assinatura":
                arquivos_necessarios.append((pid, f"{pid}.pdf", "pdf"))
                arquivos_necessarios.append((pid, f"{pid}_signed.pdf", "pdf_assinado"))
            elif caixa == "protocolo":
                arquivos_necessarios.append((pid, f"{pid}_signed.pdf", "pdf_assinado"))

        arquivos_encontrados = {}
        batch_supported = hasattr(doc_manager, "batch_check_documents")

        if batch_supported:
            nomes = [nome for _, nome, _ in arquivos_necessarios]
            try:
                batch = doc_manager.batch_check_documents("proposicao", nomes)
                for id_base, nome, tipo in arquivos_necessarios:
                    arquivos_encontrados[(id_base, tipo)] = nome in batch
            except Exception as e:
                logger.warning("[proposicoes] Batch check falhou (%s). Usando verificação individual.", e)
                batch_supported = False

        if not batch_supported:
            for prop in proposicoes:
                pid = str(prop.cod_proposicao)
                arquivos_encontrados[(pid, "odt")] = doc_manager.existe_documento("proposicao", f"{pid}.odt")
                arquivos_encontrados[(pid, "pdf")] = doc_manager.existe_documento("proposicao", f"{pid}.pdf")
                arquivos_encontrados[(pid, "pdf_assinado")] = doc_manager.existe_documento(
                    "proposicao", f"{pid}_signed.pdf"
                )

        session = Session()
        try:
            if caixa == "assinatura":
                pendentes = set(
                    row[0]
                    for row in session.query(AssinaturaDocumento.codigo)
                    .filter(
                        AssinaturaDocumento.tipo_doc == "proposicao",
                        AssinaturaDocumento.ind_excluido == 0,
                        AssinaturaDocumento.ind_assinado == 0,
                        AssinaturaDocumento.codigo.in_([p.cod_proposicao for p in proposicoes]),
                    )
                    .distinct()
                )
            for prop in proposicoes:
                pid = str(prop.cod_proposicao)
                tem_odt = arquivos_encontrados.get((pid, "odt"), False)
                tem_pdf = arquivos_encontrados.get((pid, "pdf"), False)
                tem_pdf_assinado = arquivos_encontrados.get((pid, "pdf_assinado"), False)

                if caixa == "revisao":
                    if tem_odt and not tem_pdf and not tem_pdf_assinado:
                        resultados.append(prop)
                elif caixa == "assinatura":
                    if (tem_pdf and not tem_pdf_assinado) or prop.cod_proposicao in pendentes:
                        resultados.append(prop)
                elif caixa == "protocolo":
                    if tem_pdf_assinado:
                        resultados.append(prop)
        finally:
            session.close()
        return resultados

    def _determinar_caixa_proposicao(self, proposicao):
        if proposicao.dat_devolucao:
            return "devolvido"
        if proposicao.dat_solicitacao_devolucao:
            return "pedido_devolucao"
        if proposicao.dat_recebimento and proposicao.cod_mat_ou_doc:
            return "incorporado"
        if proposicao.dat_recebimento:
            return "recebida"
        if proposicao.dat_envio:
            return "revisao"
        return "rascunho"

    def _formatar_proposicao_completo(self, proposicao, caixa):
        id_base = str(proposicao.cod_proposicao)
        doc_manager = queryUtility(ISAPLDocumentManager)
        pdf_assinado_url = None
        if doc_manager and doc_manager.existe_documento("proposicao", id_base + "_signed.pdf"):
            pdf_assinado_url = f"{doc_manager.sapl_documentos_url}/proposicao/{id_base}_signed.pdf"

        dados = {
            "id": proposicao.cod_proposicao,
            "tipo": getattr(proposicao.tipo_proposicao, "des_tipo_proposicao", ""),
            "tip_mat_ou_doc": getattr(proposicao.tipo_proposicao, "ind_mat_ou_doc", None),
            "cod_mat_ou_doc": getattr(proposicao, "cod_mat_ou_doc", None),
            "descricao": proposicao.txt_descricao,
            "autor": self._formatar_autor(proposicao.autor),
            "envio": self._formatar_data_hora(proposicao.dat_envio),
            "recebimento": self._formatar_data_hora(proposicao.dat_recebimento),
            "status": self._determinar_status(proposicao),
            "npe": f"NPE{proposicao.cod_proposicao}",
            "vinculo": None,
            "solicitacao_devolucao": None,
            "devolucao": None,
            "justificativa": None,
            "tem_odt": bool(doc_manager and doc_manager.existe_documento("proposicao", id_base + ".odt")),
            "tem_pdf": bool(doc_manager and doc_manager.existe_documento("proposicao", id_base + ".pdf")),
            "tem_pdf_assinado": bool(doc_manager and doc_manager.existe_documento("proposicao", id_base + "_signed.pdf")),
            "pdf_assinado_url": pdf_assinado_url,
            "prioritaria": getattr(proposicao, "ind_prioritaria", 0) == 1,
        }
        if caixa == "assinatura":
            dados["assinaturas"] = self._obter_status_assinaturas(proposicao.cod_proposicao)
        if caixa == "pedido_devolucao":
            dados["solicitacao_devolucao"] = self._formatar_data_hora(proposicao.dat_solicitacao_devolucao)
        if caixa == "devolvido":
            dados["devolucao"] = self._formatar_data_hora(proposicao.dat_devolucao)
            dados["justificativa"] = proposicao.txt_justif_devolucao
        if caixa == "incorporado":
            dados["vinculo"] = self._formatar_vinculo(proposicao)
        return dados

    def _formatar_autor(self, autor):
        if not autor:
            return ""
        try:
            parlamentar_nome = getattr(autor.parlamentar, "nom_completo", None)
            if parlamentar_nome:
                return parlamentar_nome
        except Exception:
            pass
        try:
            comissao_nome = getattr(autor.comissao, "nom_comissao", None)
            if comissao_nome:
                return comissao_nome
        except Exception:
            pass
        return autor.nom_autor

    def _formatar_vinculo(self, proposicao):
        tipo = getattr(proposicao.tipo_proposicao, "ind_mat_ou_doc", None)
        cod_mat_ou_doc = getattr(proposicao, "cod_mat_ou_doc", None)
        tem_emenda = getattr(proposicao, "cod_emenda", None)
        tem_subst = getattr(proposicao, "cod_substitutivo", None)
        tem_parecer = getattr(proposicao, "cod_parecer", None)

        if tipo == "D":
            if not tem_emenda and not tem_subst and not tem_parecer:
                return self._obter_vinculo_documento(cod_mat_ou_doc)
            elif cod_mat_ou_doc:
                return self._obter_vinculo_materia(cod_mat_ou_doc)
            return None
        if tipo == "M":
            return self._obter_vinculo_materia(cod_mat_ou_doc)
        return None

    def _obter_vinculo_materia(self, cod_materia):
        if not cod_materia:
            return None
        session = Session()
        try:
            materia = (
                session.query(MateriaLegislativa)
                .options(joinedload(MateriaLegislativa.tipo_materia_legislativa))
                .filter(MateriaLegislativa.cod_materia == cod_materia)
                .first()
            )
            if materia:
                return {
                    "tipo": "matéria",
                    "materia_id": materia.cod_materia,
                    "sigla": getattr(materia.tipo_materia_legislativa, "sgl_tipo_materia", ""),
                    "numero": getattr(materia, "num_ident_basica", ""),
                    "ano": getattr(materia, "ano_ident_basica", ""),
                }
            return None
        finally:
            session.close()

    def _obter_vinculo_documento(self, cod_documento):
        if not cod_documento:
            return None
        session = Session()
        try:
            documento = (
                session.query(DocumentoAcessorio)
                .options(
                    joinedload(DocumentoAcessorio.materia_legislativa).joinedload(
                        MateriaLegislativa.tipo_materia_legislativa
                    )
                )
                .filter(DocumentoAcessorio.cod_documento == cod_documento)
                .first()
            )
            if documento:
                materia = documento.materia_legislativa
                return {
                    "tipo": "documento",
                    "id": documento.cod_documento,
                    "materia_id": documento.cod_materia,
                    "sigla": getattr(materia.tipo_materia_legislativa, "sgl_tipo_materia", "") if materia else "",
                    "numero": getattr(materia, "num_ident_basica", "") if materia else "",
                    "ano": getattr(materia, "ano_ident_basica", "") if materia else "",
                }
            return None
        finally:
            session.close()

    def _get_documentos_fisicos(self, proposicao):
        doc_manager = queryUtility(ISAPLDocumentManager)
        if not doc_manager:
            return ""
        pid = str(proposicao.cod_proposicao)
        tem_odt = doc_manager.existe_documento("proposicao", pid + ".odt")
        tem_pdf = doc_manager.existe_documento("proposicao", pid + ".pdf")
        tem_pdf_assinado = doc_manager.existe_documento("proposicao", pid + "_signed.pdf")
        docs = []
        if tem_odt:
            docs.append("ODT")
        if tem_pdf:
            docs.append("PDF")
        if tem_pdf_assinado:
            docs.append("PDF Assinado")
        return ", ".join(docs)

    def _determinar_status(self, proposicao):
        if proposicao.dat_devolucao:
            return "devolvida"
        if proposicao.dat_solicitacao_devolucao:
            return "solicitacao_devolucao"
        if proposicao.dat_recebimento and proposicao.cod_mat_ou_doc:
            return "incorporada"
        if proposicao.dat_recebimento:
            return "recebida"
        if proposicao.dat_envio:
            return "enviada"
        return "rascunho"

    def _formatar_data_hora(self, dt):
        return dt.strftime("%d/%m/%Y %H:%M:%S") if dt else None

    def _responder_sucesso(self, dados, paginacao):
        self.request.response.setHeader("Content-Type", "application/json; charset=utf-8")
        return json.dumps({"sucesso": True, "dados": dados, "paginacao": paginacao}, default=self._serializar_datetime)

    def _responder_sucesso_acao(self, mensagem):
        self.request.response.setHeader("Content-Type", "application/json; charset=utf-8")
        return json.dumps({"sucesso": True, "mensagem": mensagem})

    def _responder_contagem(self, total):
        self.request.response.setHeader("Content-Type", "application/json; charset=utf-8")
        return json.dumps(
            {"sucesso": True, "paginacao": {"total": total, "por_pagina": 0, "total_paginas": 0}}
        )

    def _responder_erro(self, mensagem, status=400):
        self.request.response.setStatus(status)
        self.request.response.setHeader("Content-Type", "application/json; charset=utf-8")
        return json.dumps({"sucesso": False, "erro": mensagem})

    def _serializar_datetime(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%d/%m/%Y %H:%M")
        raise TypeError(f"Tipo {type(obj)} não serializável")

    def _obter_status_assinaturas(self, cod_proposicao):
        session = Session()
        try:
            assinaturas = (
                session.query(AssinaturaDocumento, Usuario.nom_completo)
                .join(Usuario, Usuario.cod_usuario == AssinaturaDocumento.cod_usuario)
                .filter(
                    AssinaturaDocumento.codigo == cod_proposicao,
                    AssinaturaDocumento.tipo_doc == "proposicao",
                    AssinaturaDocumento.ind_excluido == 0,
                )
                .all()
            )

            pendentes, assinadas = [], []
            for assinatura, nome in assinaturas:
                if assinatura.ind_assinado:
                    assinadas.append(nome)
                elif not assinatura.ind_recusado:
                    pendentes.append(nome)

            return {"total": len(assinaturas), "assinadas": assinadas, "pendentes": pendentes}
        finally:
            session.close()


# ---------------------------------------------------------------------
# @@proposicoes-api
# ---------------------------------------------------------------------
class ProposicoesAPI(GrokView, ProposicoesAPIBase):
    context(Interface)
    name("proposicoes-api")
    require("zope2.View")

    def render(self):
        self.request.response.setHeader("Content-Type", "application/json; charset=utf-8")
        if (self.request.get("REQUEST_METHOD") or self.request.method or "GET").upper() == "POST":
            return self.handle_post_actions()
        return self.listagem()

    # ---- GET ----
    def listagem(self):
        session = Session()
        try:
            caixa = self.request.form.get("caixa", "revisao")
            pagina = int(self.request.form.get("pagina", 1))
            por_pagina = int(self.request.form.get("por_pagina", 10))
            apenas_contar = self.request.form.get("contar") == "1"

            if not self._verificar_permissao_caixa(caixa):
                return self._responder_erro("Acesso não autorizado para esta caixa", 403)

            base_query = session.query(Proposicao.cod_proposicao).join(Proposicao.tipo_proposicao)
            base_query = base_query.filter(Proposicao.ind_excluido == 0)
            base_query = base_query.join(Proposicao.autor)
            base_query = base_query.outerjoin(Autor.parlamentar)
            base_query = base_query.outerjoin(Autor.comissao)
            base_query = self._aplicar_filtros_caixa(base_query, caixa)
            base_query = self._aplicar_filtros_adicionais(base_query)

            ORDER_MAP = {
                "envio": Proposicao.dat_envio,
                "tipo": TipoProposicao.des_tipo_proposicao,
                "descricao": Proposicao.txt_descricao,
                "autor": Autor.nom_autor,
                "recebimento": Proposicao.dat_recebimento,
                "devolucao": Proposicao.dat_devolucao,
                "solicitacao_devolucao": Proposicao.dat_solicitacao_devolucao,
            }
            ordenar_por = self.request.form.get("ordenar_por")
            ordenar_direcao = self.request.form.get("ordenar_direcao")

            # caixa 'incorporado' tem regra própria de ordenação
            if caixa == "incorporado":
                if ordenar_por != "recebimento":
                    ordenar_por = None
                total = base_query.with_entities(func.count(Proposicao.cod_proposicao)).order_by(None).scalar()
                id_query = base_query
                if ordenar_por == "recebimento":
                    if ordenar_direcao == "asc":
                        id_query = id_query.order_by(Proposicao.dat_recebimento.asc(), Proposicao.cod_proposicao.asc())
                    else:
                        id_query = id_query.order_by(
                            Proposicao.dat_recebimento.desc(), Proposicao.cod_proposicao.desc()
                        )
                else:
                    id_query = id_query.order_by(Proposicao.dat_recebimento.desc(), Proposicao.cod_proposicao.desc())

                pag_ids = [row[0] for row in id_query.limit(por_pagina).offset((pagina - 1) * por_pagina).all()]

                if not pag_ids:
                    paginados = []
                else:
                    query = (
                        session.query(Proposicao)
                        .join(Proposicao.tipo_proposicao)
                        .join(Proposicao.autor)
                        .outerjoin(Autor.parlamentar)
                        .outerjoin(Autor.comissao)
                        .filter(Proposicao.cod_proposicao.in_(pag_ids))
                        .options(
                            joinedload(Proposicao.tipo_proposicao),
                            joinedload(Proposicao.autor).joinedload(Autor.parlamentar),
                            joinedload(Proposicao.autor).joinedload(Autor.comissao),
                            joinedload(Proposicao.materia_legislativa),
                            joinedload(Proposicao.assunto_proposicao),
                        )
                    )
                    proposicoes_dict = {p.cod_proposicao: p for p in query.all()}
                    paginados = [proposicoes_dict[pid] for pid in pag_ids if pid in proposicoes_dict]

                if apenas_contar:
                    return self._responder_contagem(total)

                dados = [self._formatar_proposicao_completo(p, caixa) for p in paginados]
                return self._responder_sucesso(
                    dados=dados,
                    paginacao={
                        "total": total,
                        "pagina": pagina,
                        "por_pagina": por_pagina,
                        "total_paginas": (total + por_pagina - 1) // por_pagina,
                    },
                )

            # demais caixas
            query = session.query(Proposicao).join(Proposicao.tipo_proposicao)
            query = query.filter(Proposicao.ind_excluido == 0)
            query = query.join(Proposicao.autor)
            query = query.outerjoin(Autor.parlamentar)
            query = query.outerjoin(Autor.comissao)
            query = self._aplicar_filtros_caixa(query, caixa)
            query = self._aplicar_filtros_adicionais(query)

            if ordenar_por:
                order_field = ORDER_MAP.get(ordenar_por, Proposicao.dat_envio)
                query = query.order_by(order_field.asc() if (ordenar_direcao == "asc") else order_field.desc())
            elif caixa in {"revisao", "assinatura", "protocolo"}:
                query = query.order_by(Proposicao.dat_envio.asc())
            elif caixa == "devolvido":
                query = query.order_by(Proposicao.dat_devolucao.desc())
            elif caixa == "pedido_devolucao":
                query = query.order_by(Proposicao.dat_solicitacao_devolucao.asc())
            else:
                query = query.order_by(Proposicao.dat_envio.desc())

            query = query.options(
                joinedload(Proposicao.tipo_proposicao),
                joinedload(Proposicao.autor).joinedload(Autor.parlamentar),
                joinedload(Proposicao.autor).joinedload(Autor.comissao),
                joinedload(Proposicao.materia_legislativa),
                joinedload(Proposicao.assunto_proposicao),
            )

            if caixa in {"revisao", "assinatura", "protocolo"}:
                todas = query.all()
                filtradas = self._verificar_documentos_fisicos(todas, caixa)
                total = len(filtradas)
                paginados = filtradas[(pagina - 1) * por_pagina : pagina * por_pagina]
            else:
                total = query.with_entities(func.count(Proposicao.cod_proposicao)).order_by(None).scalar()
                paginados = query.limit(por_pagina).offset((pagina - 1) * por_pagina).all()

            if apenas_contar:
                return self._responder_contagem(total)

            dados = [self._formatar_proposicao_completo(p, caixa) for p in paginados]
            return self._responder_sucesso(
                dados=dados,
                paginacao={
                    "total": total,
                    "pagina": pagina,
                    "por_pagina": por_pagina,
                    "total_paginas": (total + por_pagina - 1) // por_pagina,
                },
            )
        except ValueError as e:
            return self._responder_erro(f"Parâmetros inválidos: {e}", 400)
        except Exception as e:
            traceback.print_exc()
            return self._responder_erro("Erro interno: " + str(e), 500)
        finally:
            session.close()

    # ---- POST ----
    def handle_post_actions(self):
        """Sobreescreva aqui se você tiver ações POST específicas (não enviadas no prompt)."""
        # Placeholder genérico: retorne 400 se não houver ação implementada.
        return self._responder_erro("Nenhuma ação POST definida para este endpoint.", 400)


# ---------------------------------------------------------------------
# @@proposicoes-incorporar-lote
# ---------------------------------------------------------------------
class IncorporarLoteProtocolo(GrokView, ProposicoesAPIBase):
    context(Interface)
    name("proposicoes-incorporar-lote")
    require("zope2.View")

    def render(self):
        method = (self.request.get("REQUEST_METHOD") or self.request.method or "GET").upper()
        if method != "POST":
            self.request.response.setStatus(405)
            return json.dumps({"sucesso": False, "erro": "Método não permitido."})

        session = Session()
        try:
            if not self._verificar_permissao_caixa("protocolo"):
                self.request.response.setStatus(403)
                return json.dumps({"sucesso": False, "erro": "Acesso não autorizado."})

            proposicoes_ids = self.request.form.get("proposicoes_ids")
            if not proposicoes_ids:
                return json.dumps({"sucesso": False, "erro": "Nenhuma proposição informada."})

            if isinstance(proposicoes_ids, str):
                import json as _json

                proposicoes_ids = _json.loads(proposicoes_ids)
            proposicoes_ids = [int(x) for x in proposicoes_ids]

            data_apresentacao_str = self.request.form.get("data_apresentacao")
            if not data_apresentacao_str:
                return json.dumps({"sucesso": False, "erro": "Data de apresentação não informada."})
            try:
                data_apresentacao = datetime.strptime(data_apresentacao_str, "%Y-%m-%d").date()
            except Exception:
                return json.dumps({"sucesso": False, "erro": "Data de apresentação inválida."})

            props = (
                session.query(Proposicao)
                .join(Proposicao.tipo_proposicao)
                .filter(
                    Proposicao.cod_proposicao.in_(proposicoes_ids),
                    Proposicao.ind_excluido == 0,
                    Proposicao.cod_mat_ou_doc.is_(None),
                    TipoProposicao.ind_mat_ou_doc == "M",
                    Proposicao.dat_solicitacao_devolucao.is_(None),
                    Proposicao.dat_devolucao.is_(None),
                )
                .all()
            )
            if not props:
                return json.dumps({"sucesso": False, "erro": "Nenhuma proposição válida para incorporação."})

            portal = self.request.PARENTS[0]
            context = portal
            resultados = []
            for prop in props:
                try:
                    criar_materia = context.restrictedTraverse("cadastros/recebimento_proposicao/criar_materia_pysc")
                    criar_materia(cod_proposicao=prop.cod_proposicao, data_apresentacao=data_apresentacao)
                    resultados.append({"cod_proposicao": prop.cod_proposicao, "resultado": "ok"})
                except Exception as e:
                    logger.warning("Falha ao incorporar proposição %s: %s", prop.cod_proposicao, e)
                    resultados.append({"cod_proposicao": prop.cod_proposicao, "resultado": "erro", "erro": str(e)})

            self.request.response.setHeader("Content-Type", "application/json; charset=utf-8")
            return json.dumps({"sucesso": True, "resultados": resultados})
        except Exception as e:
            logger.exception("Erro na incorporação em lote")
            self.request.response.setStatus(500)
            return json.dumps({"sucesso": False, "erro": str(e)})
        finally:
            session.close()


# ---------------------------------------------------------------------
# @@proposicoes-csv
# ---------------------------------------------------------------------
class ExportarCSV(GrokView, ProposicoesAPIBase):
    context(Interface)
    name("proposicoes-csv")
    require("zope2.View")

    def render(self):
        session = Session()
        try:
            caixa = self.request.form.get("caixa", "revisao")
            pagina = int(self.request.form.get("pagina", 1))
            por_pagina = int(self.request.form.get("por_pagina", 10))

            if not self._verificar_permissao_caixa(caixa):
                self.request.response.setStatus(403)
                return json.dumps({"sucesso": False, "erro": "Acesso não autorizado para esta caixa"})

            filename = f"proposicoes_{caixa}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self.request.response.setHeader("Content-Type", "text/csv; charset=utf-8")
            self.request.response.setHeader("Content-Disposition", f'attachment; filename="{filename}"')

            base_query = session.query(Proposicao)
            base_query = self._aplicar_filtros_caixa(base_query, caixa)

            ORDER_MAP = {
                "envio": Proposicao.dat_envio,
                "tipo": TipoProposicao.des_tipo_proposicao,
                "descricao": Proposicao.txt_descricao,
                "autor": Autor.nom_autor,
                "recebimento": Proposicao.dat_recebimento,
                "devolucao": Proposicao.dat_devolucao,
                "solicitacao_devolucao": Proposicao.dat_solicitacao_devolucao,
            }
            ordenar_por = self.request.form.get("ordenar_por")
            ordenar_direcao = self.request.form.get("ordenar_direcao")

            if caixa == "incorporado":
                if ordenar_por != "recebimento":
                    ordenar_por = None
                if ordenar_por == "recebimento":
                    if ordenar_direcao == "asc":
                        base_query = base_query.order_by(Proposicao.dat_recebimento.asc(), Proposicao.cod_proposicao.asc())
                    else:
                        base_query = base_query.order_by(
                            Proposicao.dat_recebimento.desc(), Proposicao.cod_proposicao.desc()
                        )
                else:
                    base_query = base_query.order_by(Proposicao.dat_recebimento.desc(), Proposicao.cod_proposicao.desc())
            else:
                if ordenar_por:
                    order_field = ORDER_MAP.get(ordenar_por, Proposicao.dat_envio)
                    base_query = base_query.order_by(order_field.asc() if (ordenar_direcao == "asc") else order_field.desc())
                else:
                    base_query = base_query.order_by(Proposicao.dat_envio.desc())

            all_ids = [row[0] for row in base_query.with_entities(Proposicao.cod_proposicao).all()]
            pag_ids = all_ids[(pagina - 1) * por_pagina : pagina * por_pagina]

            if not pag_ids:
                proposicoes = []
            else:
                query = (
                    session.query(Proposicao)
                    .join(Proposicao.tipo_proposicao)
                    .join(Proposicao.autor)
                    .outerjoin(Autor.parlamentar)
                    .outerjoin(Autor.comissao)
                    .filter(Proposicao.cod_proposicao.in_(pag_ids))
                    .options(
                        joinedload(Proposicao.tipo_proposicao),
                        joinedload(Proposicao.autor).joinedload(Autor.parlamentar),
                        joinedload(Proposicao.autor).joinedload(Autor.comissao),
                    )
                )
                proposicoes_dict = {p.cod_proposicao: p for p in query.all()}
                proposicoes = [proposicoes_dict[pid] for pid in pag_ids if pid in proposicoes_dict]

            if caixa in {"revisao", "assinatura", "protocolo"}:
                proposicoes = self._verificar_documentos_fisicos(proposicoes, caixa)

            output = io.StringIO()
            writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            writer.writerow(
                ["NPE", "Tipo", "Descrição", "Autor", "Status", "Data Envio", "Data Recebimento", "Data Devolução", "Documentos"]
            )

            # stream do CSV para a response
            for prop in proposicoes:
                writer.writerow(
                    [
                        f"NPE{prop.cod_proposicao}",
                        getattr(prop.tipo_proposicao, "des_tipo_proposicao", ""),
                        prop.txt_descricao,
                        self._formatar_autor(prop.autor),
                        self._determinar_status(prop),
                        self._formatar_data_hora(prop.dat_envio) or "",
                        self._formatar_data_hora(prop.dat_recebimento) or "",
                        self._formatar_data_hora(prop.dat_devolucao) or "",
                        self._get_documentos_fisicos(prop),
                    ]
                )
                chunk = output.getvalue()
                if chunk:
                    # Zope response espera bytes
                    self.request.response.write(chunk.encode("utf-8"))
                output.seek(0)
                output.truncate(0)

            return ""
        except Exception as e:
            traceback.print_exc()
            self.request.response.setStatus(500)
            return json.dumps({"sucesso": False, "erro": f"Erro ao gerar CSV: {str(e)}"})
        finally:
            session.close()
