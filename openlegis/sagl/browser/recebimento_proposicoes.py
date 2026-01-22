# -*- coding: utf-8 -*-
import csv
import io
import json
import logging
import traceback
from datetime import datetime
import re

from sqlalchemy import func, or_, select, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import false, true
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

# Imports para exportação PDF e ODS
try:
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.units import cm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

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
                }
            )
        if caixa == "protocolo":
            return any(r in roles for r in {"Operador", "Operador Materia"})
        return False

    def _tem_acesso_caixa(self, caixa: str) -> bool:
        return self._verificar_permissao_caixa(caixa)

    def _caixas_permitidas(self) -> set[str]:
        roles = self._get_user_roles()
        permitidas = set()
        if any(r in roles for r in {"Revisor Proposicao", "Chefia Revisão", "Operador", "Operador Materia"}):
            permitidas |= {"revisao", "assinatura", "incorporado", "devolvido", "pedido_devolucao"}
        if any(r in roles for r in {"Operador", "Operador Materia"}):
            permitidas.add("protocolo")
        return permitidas

    def _expr_por_caixa(self, caixa: str, session):
        """Expressão booleana SQLAlchemy equivalente ao filtro daquela caixa."""
        from sqlalchemy.sql import case

        if caixa == "revisao":
            return and_(
                Proposicao.dat_envio.isnot(None),
                Proposicao.dat_recebimento.is_(None),
                Proposicao.dat_solicitacao_devolucao.is_(None),
                Proposicao.dat_devolucao.is_(None),
            )

        if caixa == "assinatura":
            # Base; checagem fina de arquivos/pendências é feita depois
            return and_(
                Proposicao.dat_envio.isnot(None),
                Proposicao.dat_recebimento.is_(None),
                Proposicao.dat_solicitacao_devolucao.is_(None),
                Proposicao.dat_devolucao.is_(None),
            )

        if caixa == "protocolo":
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
            return and_(
                Proposicao.dat_envio.isnot(None),
                Proposicao.dat_recebimento.is_(None),
                Proposicao.dat_solicitacao_devolucao.is_(None),
                Proposicao.dat_devolucao.is_(None),
                or_(
                    ~Proposicao.cod_proposicao.in_(
                        session.query(AssinaturaDocumento.codigo).filter(
                            AssinaturaDocumento.ind_excluido == 0,
                            AssinaturaDocumento.tipo_doc == "proposicao",
                        )
                    ),
                    Proposicao.cod_proposicao.in_(select(todas_assinadas_subq.c.codigo)),
                ),
            )

        if caixa == "incorporado":
            return and_(
                Proposicao.ind_excluido == 0,
                Proposicao.dat_recebimento.isnot(None),
                Proposicao.cod_mat_ou_doc.isnot(None),
            )

        if caixa == "devolvido":
            return Proposicao.dat_devolucao.isnot(None)

        if caixa == "pedido_devolucao":
            return and_(
                Proposicao.dat_solicitacao_devolucao.isnot(None),
                Proposicao.dat_devolucao.is_(None),
            )

        # Desconhecida => sempre falso
        return false()

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

    def _aplicar_filtros_caixa(self, query, caixa, session):
        """
        Aplica filtros por 'caixa' usando a MESMA sessão do chamador.
        """
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
            # Base: enviadas, não recebidas, sem devolução
            return query.filter(
                Proposicao.dat_envio.isnot(None),
                Proposicao.dat_recebimento.is_(None),
                Proposicao.dat_solicitacao_devolucao.is_(None),
                Proposicao.dat_devolucao.is_(None),
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
                    Proposicao.cod_proposicao.in_(select(todas_assinadas_subq.c.codigo)),
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

    def _aplicar_filtros_adicionais(self, query, session=None):
        """
        Aplica q, tipo, autor, assunto/NPE e intervalo de datas.
        Também restringe às caixas que o usuário tem acesso:
          - se 'caixa' for 'all'/'todas' => OR de todas as caixas permitidas
          - se 'caixa' não permitida => resultado vazio
        Levanta ValueError para datas inválidas (tratado no chamador).
        
        Args:
            query: Query SQLAlchemy
            session: Sessão do banco de dados (opcional, usa do query se não fornecida)
        """
        # Obtém sessão do query se não fornecida
        close_session = False
        if session is None:
            session = query.session if hasattr(query, 'session') else Session()
            if session is None or not hasattr(query, 'session'):
                session = Session()
                close_session = True
        
        try:
            caixa_req = (self.request.form.get("caixa") or "").strip().lower()
            if caixa_req in {"all", "todas"}:
                permitidas = self._caixas_permitidas()
                if not permitidas:
                    return query.filter(false())
                exprs = [self._expr_por_caixa(c, session) for c in sorted(permitidas)]
                query = query.filter(or_(*exprs))
            elif caixa_req:
                if not self._tem_acesso_caixa(caixa_req):
                    return query.filter(false())
                # Se tem acesso, não reaplicamos aqui o filtro da caixa para evitar duplicidade.
        finally:
            if close_session:
                session.close()

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
            m = re.match(r"^(NPE)?(\d+)$", assunto_limpo)
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
                        raise ValueError("Data inicial inválida")
                if dt_fim:
                    try:
                        query = query.filter(
                            coluna
                            <= datetime.strptime(dt_fim, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                        )
                    except Exception:
                        raise ValueError("Data final inválida")
        return query

    def _verificar_documentos_fisicos(self, proposicoes, caixa, session=None):
        """
        Verifica documentos físicos e retorna proposições filtradas + cache de documentos.
        Retorna: (proposicoes_filtradas, doc_cache_dict, pendentes_set)
        """
        doc_manager = queryUtility(ISAPLDocumentManager)
        if not doc_manager:
            logger.warning("[proposicoes] Document manager não disponível para caixa=%s", caixa)
            return [], {}, set()
        if not proposicoes:
            return [], {}, set()

        resultados = []
        arquivos_necessarios = []
        # Sempre verifica todos os tipos para cache completo (reutilização)
        for prop in proposicoes:
            pid = str(prop.cod_proposicao)
            arquivos_necessarios.append((pid, f"{pid}.odt", "odt"))
            arquivos_necessarios.append((pid, f"{pid}.pdf", "pdf"))
            arquivos_necessarios.append((pid, f"{pid}_signed.pdf", "pdf_assinado"))

        arquivos_encontrados = {}
        batch_supported = hasattr(doc_manager, "batch_check_documents")

        if batch_supported:
            nomes = [nome for _, nome, _ in arquivos_necessarios]
            try:
                batch = doc_manager.batch_check_documents("proposicao", nomes)
                batch_set = set(batch) if batch else set()
                for id_base, nome, tipo in arquivos_necessarios:
                    encontrado = nome in batch_set
                    arquivos_encontrados[(id_base, tipo)] = encontrado
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

        # Usa sessão passada ou cria nova apenas se necessário
        close_session = False
        if session is None:
            session = Session()
            close_session = True
        
        try:
            pendentes = set()
            if caixa == "assinatura":
                codigos_proposicoes = [p.cod_proposicao for p in proposicoes]
                if codigos_proposicoes:
                    pendentes = set(
                        row[0]
                        for row in session.query(AssinaturaDocumento.codigo)
                        .filter(
                            AssinaturaDocumento.tipo_doc == "proposicao",
                            AssinaturaDocumento.ind_excluido == 0,
                            AssinaturaDocumento.ind_assinado == 0,
                            AssinaturaDocumento.codigo.in_(codigos_proposicoes),
                        )
                        .distinct()
                        .all()
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
                    # ou tem PDF sem assinado, ou possui pendência na tabela de assinaturas
                    if (tem_pdf and not tem_pdf_assinado) or (prop.cod_proposicao in pendentes):
                        resultados.append(prop)
                elif caixa == "protocolo":
                    if tem_pdf_assinado:
                        resultados.append(prop)
        finally:
            if close_session:
                session.close()
        
        # Retorna resultados + cache completo de documentos para reutilização
        return resultados, arquivos_encontrados, pendentes

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

    def _formatar_proposicao_completo(self, proposicao, caixa, doc_cache=None, assinaturas_cache=None, session=None):
        """
        Formata proposição completa usando cache de documentos e assinaturas quando disponível.
        
        Args:
            proposicao: Objeto Proposicao
            caixa: Nome da caixa atual
            doc_cache: Dict {(id_base, tipo): bool} com resultados de verificação de documentos
            assinaturas_cache: Dict {cod_proposicao: dict} com status de assinaturas
        """
        id_base = str(proposicao.cod_proposicao)
        doc_manager = queryUtility(ISAPLDocumentManager)
        
        # Usa cache se disponível, senão verifica individualmente (fallback)
        if doc_cache is not None:
            tem_odt = doc_cache.get((id_base, "odt"), False)
            tem_pdf = doc_cache.get((id_base, "pdf"), False)
            tem_pdf_assinado = doc_cache.get((id_base, "pdf_assinado"), False)
        else:
            # Fallback: verifica individualmente (menos eficiente)
            tem_odt = bool(doc_manager and doc_manager.existe_documento("proposicao", id_base + ".odt"))
            tem_pdf = bool(doc_manager and doc_manager.existe_documento("proposicao", id_base + ".pdf"))
            tem_pdf_assinado = bool(doc_manager and doc_manager.existe_documento("proposicao", id_base + "_signed.pdf"))
        
        pdf_assinado_url = None
        if tem_pdf_assinado and doc_manager:
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
            "tem_odt": tem_odt,
            "tem_pdf": tem_pdf,
            "tem_pdf_assinado": tem_pdf_assinado,
            "pdf_assinado_url": pdf_assinado_url,
            "prioritaria": getattr(proposicao, "ind_prioritaria", 0) == 1,
        }
        
        if caixa == "assinatura":
            # Usa cache de assinaturas se disponível
            if assinaturas_cache is not None:
                dados["assinaturas"] = assinaturas_cache.get(proposicao.cod_proposicao, {"total": 0, "assinadas": [], "pendentes": []})
            else:
                dados["assinaturas"] = self._obter_status_assinaturas(proposicao.cod_proposicao)
        if caixa == "pedido_devolucao":
            dados["solicitacao_devolucao"] = self._formatar_data_hora(proposicao.dat_solicitacao_devolucao)
        if caixa == "devolvido":
            dados["devolucao"] = self._formatar_data_hora(proposicao.dat_devolucao)
            dados["justificativa"] = proposicao.txt_justif_devolucao
        if caixa == "incorporado":
            dados["vinculo"] = self._formatar_vinculo(proposicao, session)
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

    def _formatar_vinculo(self, proposicao, session=None):
        tipo = getattr(proposicao.tipo_proposicao, "ind_mat_ou_doc", None)
        cod_mat_ou_doc = getattr(proposicao, "cod_mat_ou_doc", None)
        tem_emenda = getattr(proposicao, "cod_emenda", None)
        tem_subst = getattr(proposicao, "cod_substitutivo", None)
        tem_parecer = getattr(proposicao, "cod_parecer", None)

        if tipo == "D":
            if not tem_emenda and not tem_subst and not tem_parecer:
                return self._obter_vinculo_documento(cod_mat_ou_doc, session)
            elif cod_mat_ou_doc:
                return self._obter_vinculo_materia(cod_mat_ou_doc, session)
            return None
        if tipo == "M":
            return self._obter_vinculo_materia(cod_mat_ou_doc, session)
        return None

    def _obter_vinculo_materia(self, cod_materia, session=None):
        if not cod_materia:
            return None
        close_session = False
        if session is None:
            session = Session()
            close_session = True
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
            if close_session:
                session.close()

    def _obter_vinculo_documento(self, cod_documento, session=None):
        if not cod_documento:
            return None
        close_session = False
        if session is None:
            session = Session()
            close_session = True
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
            if close_session:
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

    def _formatar_vinculo_texto(self, vinculo):
        """
        Formata o vínculo como texto para exportação (igual à página HTML).
        Usa a mesma lógica do frontend: formatarVinculoTabela
        """
        if not vinculo:
            return ""
        
        # Lógica do frontend: if (data && (data.materia_id || (data.tipo === 'matéria' && data.id)))
        # Para matéria: verifica se tem materia_id OU (tipo é matéria E tem id)
        if vinculo.get("materia_id") or (vinculo.get("tipo") == "matéria" and vinculo.get("id")):
            sigla = vinculo.get("sigla", "")
            numero = vinculo.get("numero", "")
            ano = vinculo.get("ano", "")
            texto = f"{sigla} {numero}/{ano}".strip()
            return texto if texto else ""
        # Fallback do frontend: else if (data && data.tipo === 'matéria')
        elif vinculo.get("tipo") == "matéria":
            sigla = vinculo.get("sigla", "")
            numero = vinculo.get("numero", "")
            ano = vinculo.get("ano", "")
            texto = f"{sigla} {numero}/{ano}".strip()
            return texto if texto else ""
        # Lógica do frontend: else if (data && data.tipo === 'documento')
        elif vinculo.get("tipo") == "documento":
            doc_id = vinculo.get("id", "")
            return f"Documento {doc_id}" if doc_id else ""
        
        return ""

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

    def _obter_status_assinaturas_batch(self, codigos_proposicoes, session):
        """
        Carrega assinaturas de múltiplas proposições em uma única query (otimização N+1).
        Retorna dict {cod_proposicao: {"total": int, "assinadas": list, "pendentes": list}}
        """
        if not codigos_proposicoes:
            return {}
        
        assinaturas = (
            session.query(AssinaturaDocumento, Usuario.nom_completo)
            .join(Usuario, Usuario.cod_usuario == AssinaturaDocumento.cod_usuario)
            .filter(
                AssinaturaDocumento.codigo.in_(codigos_proposicoes),
                AssinaturaDocumento.tipo_doc == "proposicao",
                AssinaturaDocumento.ind_excluido == 0,
            )
            .all()
        )
        
        resultado = {}
        # Inicializa com estrutura vazia para todas as proposições
        for cod in codigos_proposicoes:
            resultado[cod] = {"total": 0, "assinadas": [], "pendentes": []}
        
        # Processa assinaturas encontradas
        for assinatura, nome in assinaturas:
            cod = assinatura.codigo
            if cod not in resultado:
                resultado[cod] = {"total": 0, "assinadas": [], "pendentes": []}
            resultado[cod]["total"] += 1
            if assinatura.ind_assinado:
                resultado[cod]["assinadas"].append(nome)
            elif not assinatura.ind_recusado:
                resultado[cod]["pendentes"].append(nome)
        
        return resultado

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

    def _obter_dados_para_exportacao(self, session, caixa):
        """
        Obtém dados formatados para exportação (CSV, ODS, PDF).
        Retorna lista de dicionários com dados formatados.
        Exporta TODOS os dados que passam pelos filtros (sem paginação).
        """
        base_query = session.query(Proposicao)
        base_query = base_query.join(Proposicao.tipo_proposicao)
        base_query = base_query.filter(Proposicao.ind_excluido == 0)
        base_query = base_query.join(Proposicao.autor)
        base_query = base_query.outerjoin(Autor.parlamentar)
        base_query = base_query.outerjoin(Autor.comissao)

        if caixa in {"all", "todas"}:
            pass
        else:
            base_query = self._aplicar_filtros_caixa(base_query, caixa, session)

        base_query = self._aplicar_filtros_adicionais(base_query, session)

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

        # Para exportação, buscar todos os resultados (não paginar)
        all_ids = [row[0] for row in base_query.with_entities(Proposicao.cod_proposicao).all()]

        if not all_ids:
            proposicoes = []
        else:
            query = (
                session.query(Proposicao)
                .join(Proposicao.tipo_proposicao)
                .join(Proposicao.autor)
                .outerjoin(Autor.parlamentar)
                .outerjoin(Autor.comissao)
                .filter(Proposicao.cod_proposicao.in_(all_ids))
                .options(
                    joinedload(Proposicao.tipo_proposicao),
                    joinedload(Proposicao.autor).joinedload(Autor.parlamentar),
                    joinedload(Proposicao.autor).joinedload(Autor.comissao),
                )
            )
            proposicoes_dict = {p.cod_proposicao: p for p in query.all()}
            proposicoes = [proposicoes_dict[pid] for pid in all_ids if pid in proposicoes_dict]

        if caixa in {"revisao", "assinatura", "protocolo"}:
            proposicoes, _, _ = self._verificar_documentos_fisicos(proposicoes, caixa, session)

        # Formatar dados para exportação
        dados_formatados = []
        for prop in proposicoes:
            # Obter vínculo se disponível
            vinculo = None
            if prop.cod_mat_ou_doc:
                vinculo = self._formatar_vinculo(prop, session)
            
            # Formatar vínculo como texto (sem a palavra "Vínculo:")
            vinculo_texto = self._formatar_vinculo_texto(vinculo)
            
            dados_formatados.append({
                "npe": f"NPE{prop.cod_proposicao}",
                "tipo": getattr(prop.tipo_proposicao, "des_tipo_proposicao", ""),
                "descricao": (prop.txt_descricao or "").replace("\r", " ").replace("\n", " ").strip(),
                "autor": self._formatar_autor(prop.autor),
                "status": self._determinar_status(prop),
                "data_envio": self._formatar_data_hora(prop.dat_envio) or "",
                "data_recebimento": self._formatar_data_hora(prop.dat_recebimento) or "",
                "data_devolucao": self._formatar_data_hora(prop.dat_devolucao) or "",
                "vinculo": vinculo_texto,
            })

        return dados_formatados


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

            # Permite 'all'/'todas'; caso contrário, exige permissão para a caixa específica
            if caixa not in {"all", "todas"} and not self._verificar_permissao_caixa(caixa):
                return self._responder_erro("Acesso não autorizado para esta caixa", 403)

            base_query = session.query(Proposicao.cod_proposicao).join(Proposicao.tipo_proposicao)
            base_query = base_query.filter(Proposicao.ind_excluido == 0)
            base_query = base_query.join(Proposicao.autor)
            base_query = base_query.outerjoin(Autor.parlamentar)
            base_query = base_query.outerjoin(Autor.comissao)

            if caixa in {"all", "todas"}:
                # Não aplicamos filtro de caixa aqui; ficará por conta de _aplicar_filtros_adicionais
                pass
            else:
                base_query = self._aplicar_filtros_caixa(base_query, caixa, session)

            base_query = self._aplicar_filtros_adicionais(base_query, session)

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

            # caixa 'incorporado' tem regra própria de ordenação (quando não é 'all')
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

                # Para incorporado não precisa de cache de documentos, mas pode precisar de assinaturas
                assinaturas_cache = None
                if caixa == "assinatura" and paginados:
                    codigos_paginados = [p.cod_proposicao for p in paginados]
                    assinaturas_cache = self._obter_status_assinaturas_batch(codigos_paginados, session)
                
                dados = [self._formatar_proposicao_completo(p, caixa, None, assinaturas_cache, session) for p in paginados]
                return self._responder_sucesso(
                    dados=dados,
                    paginacao={
                        "total": total,
                        "pagina": pagina,
                        "por_pagina": por_pagina,
                        "total_paginas": (total + por_pagina - 1) // por_pagina,
                    },
                )

            # demais caixas (inclusive 'all'/'todas')
            query = session.query(Proposicao).join(Proposicao.tipo_proposicao)
            query = query.filter(Proposicao.ind_excluido == 0)
            query = query.join(Proposicao.autor)
            query = query.outerjoin(Autor.parlamentar)
            query = query.outerjoin(Autor.comissao)

            if caixa in {"all", "todas"}:
                pass
            else:
                query = self._aplicar_filtros_caixa(query, caixa, session)

            query = self._aplicar_filtros_adicionais(query, session)

            # Verifica contagem ANTES de aplicar ordenação e options
            # Isso garante que a query de contagem seja completamente limpa
            if caixa in {"revisao", "assinatura", "protocolo"} and apenas_contar:
                # Para contagem, precisa verificar documentos físicos de todas as proposições
                # que passam pelos filtros básicos do banco
                # IMPORTANTE: Cria uma query limpa apenas para IDs ANTES de aplicar ordenação/options
                # Os joins podem multiplicar resultados, então usamos distinct() e set() para garantir unicidade
                query_ids = query.with_entities(Proposicao.cod_proposicao).distinct()
                
                # Executa a query e converte para lista de IDs
                # Usa set() para garantir que não há duplicatas mesmo após distinct()
                todas_ids = list(set([row[0] for row in query_ids.all()]))
                
                if not todas_ids:
                    total = 0
                else:
                    # Carrega proposições em lotes para verificar documentos físicos
                    # Processa em lotes de 500 para não sobrecarregar memória
                    lote_size = 500
                    total_filtradas = 0
                    
                    for i in range(0, len(todas_ids), lote_size):
                        lote_ids = todas_ids[i:i + lote_size]
                        if not lote_ids:
                            continue
                        
                        # Recarrega proposições do lote
                        # IMPORTANTE: Não reaplicamos filtros aqui porque os IDs já foram filtrados
                        # na query inicial. Reaplicar filtros pode causar inconsistências se houver
                        # condições de corrida ou mudanças de dados entre as chamadas.
                        # Apenas verificamos se a proposição ainda existe e não foi excluída
                        proposicoes_lote = (
                            session.query(Proposicao)
                            .filter(Proposicao.cod_proposicao.in_(lote_ids))
                            .filter(Proposicao.ind_excluido == 0)
                            .all()
                        )
                        
                        # Se o número de proposições carregadas for diferente do número de IDs,
                        # significa que algumas foram excluídas ou não existem mais
                        if len(proposicoes_lote) < len(lote_ids):
                            logger.warning(
                                "[proposicoes] Caixa=%s, Lote: %d IDs solicitados, %d carregadas (algumas podem ter sido excluídas)",
                                caixa, len(lote_ids), len(proposicoes_lote)
                            )
                        
                        if proposicoes_lote:
                            # Verifica documentos físicos com a caixa correta
                            filtradas_lote, _, _ = self._verificar_documentos_fisicos(proposicoes_lote, caixa, session)
                            total_filtradas += len(filtradas_lote)
                    
                    total = total_filtradas
                
                return self._responder_contagem(total)

            # Aplica ordenação e options apenas para queries de dados (não contagem)
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
                # Para dados: carrega buffer maior para ter proposições suficientes após filtro
                buffer_size = max(por_pagina * 5, 200)  # Buffer 5x maior para compensar filtros
                ids_query = query.with_entities(Proposicao.cod_proposicao)
                ids_buffer = [row[0] for row in ids_query.limit(buffer_size).offset((pagina - 1) * por_pagina).all()]
                
                if not ids_buffer:
                    filtradas = []
                    total = 0
                    paginados = []
                    doc_cache = {}
                    assinaturas_cache = None
                else:
                    # Carrega proposições apenas do buffer
                    proposicoes_buffer = (
                        session.query(Proposicao)
                        .filter(Proposicao.cod_proposicao.in_(ids_buffer))
                        .options(
                            joinedload(Proposicao.tipo_proposicao),
                            joinedload(Proposicao.autor).joinedload(Autor.parlamentar),
                            joinedload(Proposicao.autor).joinedload(Autor.comissao),
                        )
                        .all()
                    )
                    
                    # Mantém ordem original
                    proposicoes_dict = {p.cod_proposicao: p for p in proposicoes_buffer}
                    proposicoes_buffer = [proposicoes_dict[pid] for pid in ids_buffer if pid in proposicoes_dict]
                    
                    # Verifica documentos apenas do buffer
                    filtradas, doc_cache, pendentes = self._verificar_documentos_fisicos(proposicoes_buffer, caixa, session)
                    
                    # Pagina resultado filtrado
                    paginados = filtradas[:por_pagina]
                    
                    # Total: para caixas que dependem de documentos físicos, o total deve ser
                    # baseado apenas nas proposições que realmente passaram no filtro
                    # Não podemos usar total_banco porque ele não verifica documentos físicos
                    if len(filtradas) > 0:
                        # Se há proposições filtradas, estima baseado na proporção do buffer
                        proporcao_filtrada = len(filtradas) / len(ids_buffer) if ids_buffer else 0
                        total_banco = query.with_entities(func.count(Proposicao.cod_proposicao)).scalar() or 0
                        if proporcao_filtrada > 0:
                            total = int(total_banco * proporcao_filtrada)
                        else:
                            total = len(filtradas)  # Usa o número real de filtradas
                    else:
                        # Se nenhuma passou no filtro, o total é 0 (não usa total_banco)
                        # porque total_banco não verifica documentos físicos
                        total = 0
                
                # Carrega assinaturas em batch se necessário
                assinaturas_cache = None
                if caixa == "assinatura" and paginados:
                    codigos_paginados = [p.cod_proposicao for p in paginados]
                    assinaturas_cache = self._obter_status_assinaturas_batch(codigos_paginados, session)
            else:
                total = query.with_entities(func.count(Proposicao.cod_proposicao)).order_by(None).scalar()
                paginados = query.limit(por_pagina).offset((pagina - 1) * por_pagina).all()
                doc_cache = None
                assinaturas_cache = None
                # Para caixa incorporado, carrega assinaturas se necessário
                if caixa == "assinatura" and paginados:
                    codigos_paginados = [p.cod_proposicao for p in paginados]
                    assinaturas_cache = self._obter_status_assinaturas_batch(codigos_paginados, session)

            if apenas_contar:
                return self._responder_contagem(total)

            dados = [self._formatar_proposicao_completo(p, caixa, doc_cache, assinaturas_cache, session) for p in paginados]
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

            # Permite 'all'/'todas' aqui também
            if caixa not in {"all", "todas"} and not self._verificar_permissao_caixa(caixa):
                self.request.response.setStatus(403)
                return json.dumps({"sucesso": False, "erro": "Acesso não autorizado para esta caixa"})

            filename = f"proposicoes_{caixa}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self.request.response.setHeader("Content-Type", "text/csv; charset=utf-8")
            self.request.response.setHeader("Content-Disposition", f'attachment; filename="{filename}"')

            base_query = session.query(Proposicao)
            base_query = base_query.join(Proposicao.tipo_proposicao)
            base_query = base_query.filter(Proposicao.ind_excluido == 0)
            base_query = base_query.join(Proposicao.autor)
            base_query = base_query.outerjoin(Autor.parlamentar)
            base_query = base_query.outerjoin(Autor.comissao)

            if caixa in {"all", "todas"}:
                pass
            else:
                base_query = self._aplicar_filtros_caixa(base_query, caixa, session)

            # Mesmos filtros adicionais da listagem (inclui guarda de perfil e 'all')
            base_query = self._aplicar_filtros_adicionais(base_query, session)

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
                proposicoes, _, _ = self._verificar_documentos_fisicos(proposicoes, caixa, session)

            # Usar método auxiliar para obter dados formatados (inclui vínculo)
            dados = []
            for prop in proposicoes:
                # Obter vínculo se disponível
                vinculo = None
                if prop.cod_mat_ou_doc:
                    vinculo = self._formatar_vinculo(prop, session)
                
                # Formatar vínculo como texto (sem a palavra "Vínculo:")
                vinculo_texto = self._formatar_vinculo_texto(vinculo)
                
                dados.append({
                    "npe": f"NPE{prop.cod_proposicao}",
                    "tipo": getattr(prop.tipo_proposicao, "des_tipo_proposicao", ""),
                    "descricao": (prop.txt_descricao or "").replace("\r", " ").replace("\n", " ").strip(),
                    "autor": self._formatar_autor(prop.autor),
                    "status": self._determinar_status(prop),
                    "data_envio": self._formatar_data_hora(prop.dat_envio) or "",
                    "data_recebimento": self._formatar_data_hora(prop.dat_recebimento) or "",
                    "data_devolucao": self._formatar_data_hora(prop.dat_devolucao) or "",
                    "vinculo": vinculo_texto,
                })

            output = io.StringIO()
            writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            writer.writerow(
                ["NPE", "Tipo", "Descrição", "Autor", "Status", "Data Envio", "Data Recebimento", "Data Devolução", "Vínculo"]
            )

            # stream do CSV para a response
            for item in dados:
                writer.writerow([
                    item.get("npe", ""),
                    item.get("tipo", ""),
                    item.get("descricao", ""),
                    item.get("autor", ""),
                    item.get("status", ""),
                    item.get("data_envio", ""),
                    item.get("data_recebimento", ""),
                    item.get("data_devolucao", ""),
                    item.get("vinculo", ""),
                ])
                chunk = output.getvalue()
                if chunk:
                    # Zope response espera bytes
                    self.request.response.write(chunk.encode("utf-8"))
                output.seek(0)
                output.truncate(0)

            return ""
        except ValueError as e:
            self.request.response.setStatus(400)
            return json.dumps({"sucesso": False, "erro": f"Parâmetros inválidos: {str(e)}"})
        except Exception as e:
            traceback.print_exc()
            self.request.response.setStatus(500)
            return json.dumps({"sucesso": False, "erro": f"Erro ao gerar CSV: {str(e)}"})
        finally:
            session.close()


# ---------------------------------------------------------------------
# @@proposicoes-excel
# ---------------------------------------------------------------------
class ExportarExcel(GrokView, ProposicoesAPIBase):
    context(Interface)
    name("proposicoes-excel")
    require("zope2.View")

    def render(self):
        if not OPENPYXL_AVAILABLE:
            self.request.response.setStatus(500)
            return json.dumps({"sucesso": False, "erro": "Biblioteca openpyxl não disponível"})

        session = Session()
        try:
            caixa = self.request.form.get("caixa", "revisao")

            if caixa not in {"all", "todas"} and not self._verificar_permissao_caixa(caixa):
                self.request.response.setStatus(403)
                return json.dumps({"sucesso": False, "erro": "Acesso não autorizado para esta caixa"})

            filename = f"proposicoes_{caixa}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            self.request.response.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.request.response.setHeader("Content-Disposition", f'attachment; filename="{filename}"')

            dados = self._obter_dados_para_exportacao(session, caixa)

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Proposições"

            # Cabeçalho
            ws.append(["NPE", "Tipo", "Descrição", "Autor", "Status", "Data Envio", "Data Recebimento", "Data Devolução", "Vínculo"])

            # Dados
            for item in dados:
                ws.append([
                    item.get("npe", ""),
                    item.get("tipo", ""),
                    item.get("descricao", ""),
                    item.get("autor", ""),
                    item.get("status", ""),
                    item.get("data_envio", ""),
                    item.get("data_recebimento", ""),
                    item.get("data_devolucao", ""),
                    item.get("vinculo", ""),
                ])

            # Ajustar largura das colunas
            for column in ws.columns:
                max_length = 0
                column = [cell for cell in column]
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except Exception:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column[0].column_letter].width = adjusted_width

            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()

        except ValueError as e:
            self.request.response.setStatus(400)
            return json.dumps({"sucesso": False, "erro": f"Parâmetros inválidos: {str(e)}"})
        except Exception as e:
            traceback.print_exc()
            self.request.response.setStatus(500)
            return json.dumps({"sucesso": False, "erro": f"Erro ao gerar Excel: {str(e)}"})
        finally:
            session.close()


# ---------------------------------------------------------------------
# @@proposicoes-pdf
# ---------------------------------------------------------------------
class ExportarPDF(GrokView, ProposicoesAPIBase):
    context(Interface)
    name("proposicoes-pdf")
    require("zope2.View")

    def render(self):
        if not REPORTLAB_AVAILABLE:
            self.request.response.setStatus(500)
            return json.dumps({"sucesso": False, "erro": "Biblioteca ReportLab não disponível"})

        session = Session()
        try:
            caixa = self.request.form.get("caixa", "revisao")

            if caixa not in {"all", "todas"} and not self._verificar_permissao_caixa(caixa):
                self.request.response.setStatus(403)
                return json.dumps({"sucesso": False, "erro": "Acesso não autorizado para esta caixa"})

            filename = f"proposicoes_{caixa}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            self.request.response.setHeader("Content-Type", "application/pdf")
            self.request.response.setHeader("Content-Disposition", f'attachment; filename="{filename}"')

            dados = self._obter_dados_para_exportacao(session, caixa)

            if not dados:
                return b""

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=landscape(A4),
                rightMargin=1.5*cm,
                leftMargin=1.5*cm,
                topMargin=2*cm,
                bottomMargin=2*cm,
                title="Relatório de Recebimento de Proposições"
            )
            styles = getSampleStyleSheet()
            normal_style = styles['Normal']
            normal_style.fontSize = 8
            normal_style.leading = 10
            normal_style.wordWrap = 'LTR'
            header_style = styles['Heading4']
            header_style.fontSize = 9
            header_style.leading = 12
            header_style.textColor = colors.white
            header_style.alignment = 1

            elements = []
            elements.append(Paragraph("RELATÓRIO DE RECEBIMENTO DE PROPOSIÇÕES", styles['Title']))
            elements.append(Paragraph(f"Data de geração: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
            elements.append(Paragraph(f"Total de registros: {len(dados)}", styles['Normal']))
            elements.append(Spacer(1, 0.5*cm))

            header_labels = [
                'NPE',
                'Tipo',
                'Descrição',
                'Autor',
                'Status',
                'Data Envio',
                'Data Recebimento',
                'Data Devolução',
                'Vínculo'
            ]

            table_data = []
            table_data.append([Paragraph(label, header_style) for label in header_labels])

            for item in dados:
                row = [
                    Paragraph(str(item.get('npe', '')), normal_style),
                    Paragraph(str(item.get('tipo', '')), normal_style),
                    Paragraph(str(item.get('descricao', '')), normal_style),
                    Paragraph(str(item.get('autor', '')), normal_style),
                    Paragraph(str(item.get('status', '')), normal_style),
                    Paragraph(str(item.get('data_envio', '')), normal_style),
                    Paragraph(str(item.get('data_recebimento', '')), normal_style),
                    Paragraph(str(item.get('data_devolucao', '')), normal_style),
                    Paragraph(str(item.get('vinculo', '')), normal_style),
                ]
                table_data.append(row)

            page_width, page_height = landscape(A4)
            content_width = page_width - doc.leftMargin - doc.rightMargin
            col_widths = [
                0.08 * content_width,  # NPE
                0.11 * content_width,  # Tipo
                0.23 * content_width,  # Descrição
                0.14 * content_width,  # Autor
                0.09 * content_width,  # Status
                0.09 * content_width,  # Data Envio
                0.08 * content_width,  # Data Recebimento
                0.08 * content_width,  # Data Devolução
                0.10 * content_width   # Vínculo
            ]

            table = Table(
                table_data,
                colWidths=col_widths,
                repeatRows=1,
                hAlign='LEFT'
            )

            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 9),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('ALIGN', (0,1), (0,-1), 'CENTER'),  # NPE centralizado
                ('ALIGN', (1,1), (1,-1), 'CENTER'),  # Tipo centralizado
                ('ALIGN', (2,1), (2,-1), 'LEFT'),     # Descrição à esquerda
                ('ALIGN', (3,1), (3,-1), 'LEFT'),    # Autor à esquerda
                ('ALIGN', (4,1), (4,-1), 'CENTER'),  # Status centralizado
                ('ALIGN', (5,1), (7,-1), 'CENTER'),  # Datas centralizadas
                ('ALIGN', (8,1), (8,-1), 'CENTER'),  # Documentos centralizado
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#2F5597')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F2F2F2')]),
                ('LEFTPADDING', (0,0), (-1,-1), 3),
                ('RIGHTPADDING', (0,0), (-1,-1), 3),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))

            elements.append(table)

            def footer(canvas, doc_):
                canvas.saveState()
                canvas.setFont('Helvetica', 8)
                page_num = f"Página {doc_.page}"
                canvas.drawRightString(page_width - 1.5*cm, 1*cm, page_num)
                canvas.drawString(1.5*cm, 1*cm, "SAGL")
                canvas.restoreState()

            doc.build(elements, onFirstPage=footer, onLaterPages=footer)
            pdf_data = buffer.getvalue()
            buffer.close()
            return pdf_data

        except ValueError as e:
            self.request.response.setStatus(400)
            return json.dumps({"sucesso": False, "erro": f"Parâmetros inválidos: {str(e)}"})
        except Exception as e:
            traceback.print_exc()
            self.request.response.setStatus(500)
            return json.dumps({"sucesso": False, "erro": f"Erro ao gerar PDF: {str(e)}"})
        finally:
            session.close()