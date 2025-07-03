# -*- coding: utf-8 -*-
from five import grok
from zope.interface import Interface
from zope.component import queryUtility
from sqlalchemy.orm import joinedload
from sqlalchemy import func, or_, desc, asc
from datetime import datetime
import json
import csv
import traceback
import io
import logging

from z3c.saconfig import named_scoped_session
from openlegis.sagl.models.models import (
    Proposicao, Autor, TipoProposicao, MateriaLegislativa,
    DocumentoAcessorio, Parlamentar, Comissao, AssuntoProposicao, Usuario
)
from openlegis.sagl.interfaces import ISAPLDocumentManager

Session = named_scoped_session('minha_sessao')

logger = logging.getLogger("proposicoes")

class ProposicoesAPIBase:
    def _verificar_permissao_caixa(self, caixa):
        roles = self._get_user_roles()
        if caixa in ['revisao', 'assinatura', 'incorporado', 'devolvido', 'pedido_devolucao']:
            return any(r in roles for r in ['Revisor Proposicao', 'Chefia Revisão', 'Operador', 'Operador Materia', 'Operador Revisao'])
        elif caixa == 'protocolo':
            return any(r in roles for r in ['Operador', 'Operador Materia'])
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
        """Busca o cod_usuario a partir do login do usuário autenticado."""
        try:
            col_username = self.request.AUTHENTICATED_USER.getUserName()
            session = Session()
            usuario = session.query(Usuario).filter(
                Usuario.col_username == col_username,
                Usuario.ind_excluido == 0,
                Usuario.ind_ativo == 1
            ).first()
            session.close()
            return usuario.cod_usuario if usuario else None
        except Exception as e:
            logger.warning('[proposicoes] Não foi possível obter cod_usuario: %s', e)
            return None

    def _aplicar_filtros_caixa(self, query, caixa):
        if caixa == 'revisao':
            roles = self._get_user_roles()
            if 'Revisor Proposicao' in roles:
                cod_revisor = self._get_cod_usuario()
                if cod_revisor:
                    query = query.filter(
                        Proposicao.dat_envio.isnot(None),
                        Proposicao.dat_recebimento.is_(None),
                        Proposicao.dat_solicitacao_devolucao.is_(None),
                        Proposicao.dat_devolucao.is_(None),
                        Proposicao.cod_revisor == cod_revisor
                    )
                    return query
            # Demais perfis (Chefia Revisão, Operador, etc.):
            return query.filter(
                Proposicao.dat_envio.isnot(None),
                Proposicao.dat_recebimento.is_(None),
                Proposicao.dat_solicitacao_devolucao.is_(None),
                Proposicao.dat_devolucao.is_(None)
            )
        elif caixa in ['assinatura', 'protocolo']:
            return query.filter(
                Proposicao.dat_envio.isnot(None),
                Proposicao.dat_recebimento.is_(None),
                Proposicao.dat_solicitacao_devolucao.is_(None),
                Proposicao.dat_devolucao.is_(None)
            )
        elif caixa == 'incorporado':
            return query.filter(
                Proposicao.dat_recebimento.isnot(None),
                Proposicao.cod_mat_ou_doc.isnot(None)
            )
        elif caixa == 'devolvido':
            return query.filter(Proposicao.dat_devolucao.isnot(None))
        elif caixa == 'pedido_devolucao':
            return query.filter(
                Proposicao.dat_solicitacao_devolucao.isnot(None),
                Proposicao.dat_devolucao.is_(None)
            )
        return query

    def _aplicar_filtros_adicionais(self, query):
        search_term = self.request.form.get('q', '').strip()
        if search_term:
            search_pattern = f'%{search_term}%'
            query = query.filter(
                or_(
                    Proposicao.txt_descricao.ilike(search_pattern),
                    TipoProposicao.des_tipo_proposicao.ilike(search_pattern),
                    Autor.nom_autor.ilike(search_pattern),
                    Parlamentar.nom_parlamentar.ilike(search_pattern),
                    Parlamentar.nom_completo.ilike(search_pattern),
                    Comissao.nom_comissao.ilike(search_pattern),
                    Comissao.sgl_comissao.ilike(search_pattern),
                )
            )

        tipo = self.request.form.get('tipo', '').strip()
        if tipo:
            query = query.filter(TipoProposicao.des_tipo_proposicao.ilike(f'%{tipo}%'))

        autor = self.request.form.get('autor', '').strip()
        if autor:
            query = query.filter(
                or_(
                    Autor.nom_autor.ilike(f'%{autor}%'),
                    Parlamentar.nom_parlamentar.ilike(f'%{autor}%'),
                    Parlamentar.nom_completo.ilike(f'%{autor}%'),
                    Comissao.nom_comissao.ilike(f'%{autor}%'),
                    Comissao.sgl_comissao.ilike(f'%{autor}%')
                )
            )

        assunto = self.request.form.get('assunto', '').strip()
        if assunto:
            query = query.filter(Proposicao.txt_descricao.ilike(f'%{assunto}%'))

        campo_data = self.request.form.get('campo_data', 'dat_envio')
        dt_inicio = self.request.form.get('dt_inicio')
        dt_fim = self.request.form.get('dt_fim')
        if campo_data and (dt_inicio or dt_fim):
            coluna_data = getattr(Proposicao, campo_data, None)
            if coluna_data is not None:
                if dt_inicio:
                    try:
                        dt_inicio_parsed = datetime.strptime(dt_inicio, '%Y-%m-%d')
                        query = query.filter(coluna_data >= dt_inicio_parsed)
                    except Exception:
                        return self._responder_erro('Data inicial inválida', 400)
                if dt_fim:
                    try:
                        dt_fim_parsed = datetime.strptime(dt_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                        query = query.filter(coluna_data <= dt_fim_parsed)
                    except Exception:
                        return self._responder_erro('Data final inválida', 400)
        return query

    def _verificar_documentos_fisicos(self, proposicoes, caixa):
        doc_manager = queryUtility(ISAPLDocumentManager)
        if not doc_manager or not proposicoes:
            return []

        arquivos_necessarios = []
        for prop in proposicoes:
            id_base = str(prop.cod_proposicao)
            arquivos = []
            if caixa == 'revisao':
                arquivos.append((id_base + '.odt', 'odt'))
            elif caixa == 'assinatura':
                arquivos.append((id_base + '.pdf', 'pdf'))
            elif caixa == 'protocolo':
                arquivos.append((id_base + '_signed.pdf', 'pdf_assinado'))
            arquivos_necessarios.extend([(id_base, nome, tipo) for (nome, tipo) in arquivos])

        arquivos_encontrados = {}
        batch_supported = hasattr(doc_manager, 'batch_check_documents')
        if batch_supported:
            nomes = [nome for _, nome, _ in arquivos_necessarios]
            try:
                batch = doc_manager.batch_check_documents('proposicao', nomes)
                for id_base, nome, tipo in arquivos_necessarios:
                    arquivos_encontrados[(id_base, tipo)] = nome in batch
            except Exception as e:
                logger.warning('[proposicoes] Batch check falhou (%s), usando verificação individual!', e)
                batch_supported = False

        if not batch_supported:
            for prop in proposicoes:
                id_base = str(prop.cod_proposicao)
                arquivos_encontrados[(id_base, 'odt')] = doc_manager.existe_documento('proposicao', id_base + '.odt')
                arquivos_encontrados[(id_base, 'pdf')] = doc_manager.existe_documento('proposicao', id_base + '.pdf')
                arquivos_encontrados[(id_base, 'pdf_assinado')] = doc_manager.existe_documento('proposicao', id_base + '_signed.pdf')

        resultados = []
        for prop in proposicoes:
            id_base = str(prop.cod_proposicao)
            tem_odt = arquivos_encontrados.get((id_base, 'odt'), False)
            tem_pdf = arquivos_encontrados.get((id_base, 'pdf'), False)
            tem_pdf_assinado = arquivos_encontrados.get((id_base, 'pdf_assinado'), False)
            if caixa == 'revisao':
                if tem_odt and not tem_pdf and not tem_pdf_assinado:
                    resultados.append(prop)
            elif caixa == 'assinatura':
                if tem_pdf and not tem_pdf_assinado:
                    resultados.append(prop)
            elif caixa == 'protocolo':
                if tem_pdf_assinado:
                    resultados.append(prop)
        return resultados

    def _determinar_caixa_proposicao(self, proposicao):
        if proposicao.dat_devolucao:
            return 'devolvido'
        if proposicao.dat_solicitacao_devolucao:
            return 'pedido_devolucao'
        if proposicao.dat_recebimento and proposicao.cod_mat_ou_doc:
            return 'incorporado'
        if proposicao.dat_recebimento:
            return 'recebida'
        if proposicao.dat_envio:
            return 'revisao'
        return 'rascunho'

    def _formatar_proposicao_completo(self, proposicao, caixa):
        id_base = str(proposicao.cod_proposicao)
        doc_manager = queryUtility(ISAPLDocumentManager)
        dados = {
            'id': proposicao.cod_proposicao,
            'tipo': getattr(proposicao.tipo_proposicao, 'des_tipo_proposicao', ''),
            'descricao': proposicao.txt_descricao,
            'autor': self._formatar_autor(proposicao.autor),
            'envio': self._formatar_data_hora(proposicao.dat_envio),
            'recebimento': self._formatar_data_hora(proposicao.dat_recebimento),
            'status': self._determinar_status(proposicao),
            'npe': f"NPE{proposicao.cod_proposicao}",
            'vinculo': None,
            'solicitacao_devolucao': None,
            'devolucao': None,
            'justificativa': None,
            'tem_odt': doc_manager and doc_manager.existe_documento('proposicao', id_base + '.odt'),
            'tem_pdf': doc_manager and doc_manager.existe_documento('proposicao', id_base + '.pdf'),
            'tem_pdf_assinado': doc_manager and doc_manager.existe_documento('proposicao', id_base + '_signed.pdf'),
            'prioritaria': getattr(proposicao, 'ind_prioritaria', 0) == 1
        }
        if caixa == 'pedido_devolucao':
            dados['solicitacao_devolucao'] = self._formatar_data_hora(proposicao.dat_solicitacao_devolucao)
        if caixa == 'devolvido':
            dados['devolucao'] = self._formatar_data_hora(proposicao.dat_devolucao)
            dados['justificativa'] = proposicao.txt_justif_devolucao
        if caixa == 'incorporado':
            dados['vinculo'] = self._formatar_vinculo(proposicao)
        return dados

    def _formatar_autor(self, autor):
        if not autor:
            return ''
        try:
            parlamentar_nome = getattr(autor.parlamentar, 'nom_completo', None)
            if parlamentar_nome:
                return parlamentar_nome
        except Exception:
            pass
        try:
            comissao_nome = getattr(autor.comissao, 'nom_comissao', None)
            if comissao_nome:
                return comissao_nome
        except Exception:
            pass
        return autor.nom_autor

    def _formatar_vinculo(self, proposicao):
        if hasattr(proposicao, 'ind_mat_ou_doc'):
            if proposicao.ind_mat_ou_doc == 'D' and not any([
                proposicao.cod_emenda,
                proposicao.cod_substitutivo,
                proposicao.cod_parecer
            ]):
                return self._obter_vinculo_documento(proposicao.cod_mat_ou_doc)
        return self._obter_vinculo_materia(proposicao.cod_mat_ou_doc)

    def _obter_vinculo_materia(self, cod_materia):
        if not cod_materia:
            return None
        session = Session()
        try:
            materia = session.get(MateriaLegislativa, cod_materia)
            if materia:
                tipo = getattr(materia.tipo_materia_legislativa, 'des_tipo_materia', None)
                sigla = getattr(materia.tipo_materia_legislativa, 'sgl_tipo_materia', None)
                return {
                    'tipo': 'matéria',
                    'id': materia.cod_materia,
                    'sigla': sigla or '',
                    'tipo_descricao': tipo or '',
                    'numero': materia.num_ident_basica,
                    'ano': materia.ano_ident_basica
                }
            return None
        finally:
            session.close()

    def _obter_vinculo_documento(self, cod_documento):
        if not cod_documento:
            return None
        session = Session()
        try:
            documento = session.get(DocumentoAcessorio, cod_documento)
            if documento:
                return {
                    'tipo': 'documento',
                    'id': documento.cod_documento,
                    'materia_id': documento.cod_materia
                }
            return None
        finally:
            session.close()

    def _get_documentos_fisicos(self, proposicao):
        doc_manager = queryUtility(ISAPLDocumentManager)
        if not doc_manager:
            return ''
        id_base = str(proposicao.cod_proposicao)
        tem_odt = doc_manager.existe_documento('proposicao', id_base + '.odt')
        tem_pdf = doc_manager.existe_documento('proposicao', id_base + '.pdf')
        tem_pdf_assinado = doc_manager.existe_documento('proposicao', id_base + '_signed.pdf')
        docs = []
        if tem_odt:
            docs.append('ODT')
        if tem_pdf:
            docs.append('PDF')
        if tem_pdf_assinado:
            docs.append('PDF Assinado')
        return ', '.join(docs)

    def _determinar_status(self, proposicao):
        if proposicao.dat_devolucao:
            return 'devolvida'
        if proposicao.dat_solicitacao_devolucao:
            return 'solicitacao_devolucao'
        if proposicao.dat_recebimento and proposicao.cod_mat_ou_doc:
            return 'incorporada'
        if proposicao.dat_recebimento:
            return 'recebida'
        if proposicao.dat_envio:
            return 'enviada'
        return 'rascunho'

    def _formatar_data_hora(self, dt):
        return dt.strftime('%d/%m/%Y %H:%M') if dt else None

    def _responder_sucesso(self, dados, paginacao):
        return json.dumps({
            'sucesso': True,
            'dados': dados,
            'paginacao': paginacao
        }, default=self._serializar_datetime)

    def _responder_sucesso_acao(self, mensagem):
        return json.dumps({
            'sucesso': True,
            'mensagem': mensagem
        })

    def _responder_contagem(self, total):
        return json.dumps({
            'sucesso': True,
            'paginacao': {
                'total': total,
                'por_pagina': 0,
                'total_paginas': 0
            }
        })

    def _responder_erro(self, mensagem, status=400):
        self.request.response.setStatus(status)
        return json.dumps({
            'sucesso': False,
            'erro': mensagem
        })

    def _serializar_datetime(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%d/%m/%Y %H:%M')
        raise TypeError(f"Tipo {type(obj)} não serializável")

class ProposicoesAPI(grok.View, ProposicoesAPIBase):
    grok.context(Interface)
    grok.name('proposicoes-api')
    grok.require('zope2.View')

    def render(self):
        self.request.response.setHeader('Content-Type', 'application/json')
        if self.request.method == "POST":
            return self.handle_post_actions()
        return self.listagem()

    def listagem(self):
        session = Session()
        try:
            caixa = self.request.form.get('caixa', 'revisao')
            pagina = int(self.request.form.get('pagina', 1))
            por_pagina = int(self.request.form.get('por_pagina', 10))
            apenas_contar = self.request.form.get('contar') == '1'

            if not self._verificar_permissao_caixa(caixa):
                return self._responder_erro('Acesso não autorizado para esta caixa', 403)

            query = session.query(Proposicao).join(Proposicao.tipo_proposicao)
            query = query.filter(Proposicao.ind_excluido == 0)
            query = query.join(Proposicao.autor)
            query = query.outerjoin(Autor.parlamentar)
            query = query.outerjoin(Autor.comissao)
            query = self._aplicar_filtros_caixa(query, caixa)
            query = self._aplicar_filtros_adicionais(query)

            ORDER_MAP = {
                'envio': Proposicao.dat_envio,
                'tipo': TipoProposicao.des_tipo_proposicao,
                'descricao': Proposicao.txt_descricao,
                'autor': Autor.nom_autor,
                'recebimento': Proposicao.dat_recebimento,
                'devolucao': Proposicao.dat_devolucao,
                'solicitacao_devolucao': Proposicao.dat_solicitacao_devolucao
            }

            ordenar_por = self.request.form.get('ordenar_por')
            ordenar_direcao = self.request.form.get('ordenar_direcao')
            filtros_aplicados = any([
                self.request.form.get('q', '').strip(),
                self.request.form.get('tipo', '').strip(),
                self.request.form.get('autor', '').strip(),
                self.request.form.get('assunto', '').strip(),
                self.request.form.get('campo_data'),
                self.request.form.get('dt_inicio'),
                self.request.form.get('dt_fim')
            ])

            if ordenar_por:
                order_field = ORDER_MAP.get(ordenar_por, Proposicao.dat_envio)
                order_method = order_field.asc() if (ordenar_direcao == 'asc') else order_field.desc()
                query = query.order_by(order_method)
            elif not filtros_aplicados:
                query = query.order_by(Proposicao.dat_envio.desc())

            query = query.options(
                joinedload(Proposicao.tipo_proposicao),
                joinedload(Proposicao.autor).joinedload(Autor.parlamentar),
                joinedload(Proposicao.autor).joinedload(Autor.comissao),
                joinedload(Proposicao.materia_legislativa),
                joinedload(Proposicao.assunto_proposicao)
            )

            if caixa in ['revisao', 'assinatura', 'protocolo']:
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
                    'total': total,
                    'pagina': pagina,
                    'por_pagina': por_pagina,
                    'total_paginas': (total + por_pagina - 1) // por_pagina
                }
            )
        except ValueError as e:
            return self._responder_erro(f'Parâmetros inválidos: {e}', 400)
        except Exception as e:
            traceback.print_exc()
            return self._responder_erro('Erro interno: ' + str(e), 500)
        finally:
            session.close()

class ExportarCSV(grok.View, ProposicoesAPIBase):
    grok.context(Interface)
    grok.name('proposicoes-csv')
    grok.require('zope2.View')

    def render(self):
        session = Session()
        try:
            caixa = self.request.form.get('caixa', 'revisao')
            if not self._verificar_permissao_caixa(caixa):
                self.request.response.setStatus(403)
                return json.dumps({
                    'sucesso': False,
                    'erro': 'Acesso não autorizado para esta caixa'
                })
            filename = f"proposicoes_{caixa}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self.request.response.setHeader('Content-Type', 'text/csv; charset=utf-8')
            self.request.response.setHeader(
                'Content-Disposition',
                f'attachment; filename="{filename}"'
            )

            output = io.StringIO()
            writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow([
                'NPE', 'Tipo', 'Descrição', 'Autor',
                'Status', 'Data Envio', 'Data Recebimento',
                'Data Devolução', 'Documentos'
            ])

            query = session.query(Proposicao).join(Proposicao.tipo_proposicao)
            query = query.filter(Proposicao.ind_excluido == 0)
            query = query.join(Proposicao.autor)
            query = query.outerjoin(Autor.parlamentar)
            query = query.outerjoin(Autor.comissao)
            query = self._aplicar_filtros_caixa(query, caixa)
            query = self._aplicar_filtros_adicionais(query)

            ordenar_por = self.request.form.get('ordenar_por')
            ordenar_direcao = self.request.form.get('ordenar_direcao')
            filtros_aplicados = any([
                self.request.form.get('q', '').strip(),
                self.request.form.get('tipo', '').strip(),
                self.request.form.get('autor', '').strip(),
                self.request.form.get('assunto', '').strip(),
                self.request.form.get('campo_data'),
                self.request.form.get('dt_inicio'),
                self.request.form.get('dt_fim')
            ])
            ORDER_MAP = {
                'envio': Proposicao.dat_envio,
                'tipo': TipoProposicao.des_tipo_proposicao,
                'descricao': Proposicao.txt_descricao,
                'autor': Autor.nom_autor,
                'recebimento': Proposicao.dat_recebimento,
                'devolucao': Proposicao.dat_devolucao,
                'solicitacao_devolucao': Proposicao.dat_solicitacao_devolucao
            }
            if ordenar_por:
                order_field = ORDER_MAP.get(ordenar_por, Proposicao.dat_envio)
                order_method = order_field.asc() if (ordenar_direcao == 'asc') else order_field.desc()
                query = query.order_by(order_method)
            elif not filtros_aplicados:
                query = query.order_by(Proposicao.dat_envio.desc())

            query = query.options(
                joinedload(Proposicao.tipo_proposicao),
                joinedload(Proposicao.autor).joinedload(Autor.parlamentar),
                joinedload(Proposicao.autor).joinedload(Autor.comissao)
            )

            if caixa in ['revisao', 'assinatura', 'protocolo']:
                todas = query.all()
                proposicoes = self._verificar_documentos_fisicos(todas, caixa)
            else:
                proposicoes = query.all()

            for prop in proposicoes:
                writer.writerow([
                    f"NPE{prop.cod_proposicao}",
                    getattr(prop.tipo_proposicao, 'des_tipo_proposicao', ''),
                    prop.txt_descricao,
                    self._formatar_autor(prop.autor),
                    self._determinar_status(prop),
                    self._formatar_data_hora(prop.dat_envio) or '',
                    self._formatar_data_hora(prop.dat_recebimento) or '',
                    self._formatar_data_hora(prop.dat_devolucao) or '',
                    self._get_documentos_fisicos(prop)
                ])
                chunk = output.getvalue()
                if chunk:
                    self.request.response.write(chunk.encode('utf-8'))
                output.seek(0)
                output.truncate(0)
            return ''
        except Exception as e:
            traceback.print_exc()
            self.request.response.setStatus(500)
            return json.dumps({
                'sucesso': False,
                'erro': f"Erro ao gerar CSV: {str(e)}"
            })
        finally:
            session.close()
