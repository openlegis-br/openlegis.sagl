# -*- coding: utf-8 -*-
"""Envio de e-mails de notificação de tramitação"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session, selectinload
from email.mime.text import MIMEText
from DateTime import DateTime

from openlegis.sagl.models.models import (
    MateriaLegislativa, Autoria, Autor, AcompMateria,
    DocumentoAdministrativo, Tramitacao, TramitacaoAdministrativo,
    StatusTramitacao, StatusTramitacaoAdministrativo,
    UnidadeTramitacao, Usuario, TipoMateriaLegislativa
)

from .templates import (
    gerar_html_notificacao_autor,
    gerar_html_notificacao_acompanhamento_materia,
    gerar_html_notificacao_documento
)

import logging

logger = logging.getLogger(__name__)


def _get_nom_autor_join(autor):
    """
    Obtém o nome formatado do autor considerando o tipo de autor.
    Lógica baseada em views.py _get_nom_autor_join:
    - Se for Parlamentar: usa nom_parlamentar ou nom_completo
    - Se for Bancada: usa nom_bancada
    - Se for Comissão: usa nom_comissao
    - Caso contrário: usa nom_autor
    """
    if not autor:
        return ''
    
    # Carrega relacionamentos se necessário
    if not autor.tipo_autor:
        return autor.nom_autor or ''
    
    tipo_autor = autor.tipo_autor.des_tipo_autor if hasattr(autor.tipo_autor, 'des_tipo_autor') else ''
    
    if tipo_autor == 'Parlamentar' and autor.parlamentar:
        return autor.parlamentar.nom_parlamentar or autor.parlamentar.nom_completo or autor.nom_autor or ''
    elif tipo_autor == 'Bancada' and autor.bancada:
        return autor.bancada.nom_bancada or autor.nom_autor or ''
    elif tipo_autor == 'Comissao' and autor.comissao:
        return autor.comissao.nom_comissao or autor.nom_autor or ''
    else:
        return autor.nom_autor or ''


class TramitacaoEmailSender:
    """Envia e-mails de notificação de tramitação"""
    
    def __init__(self, session: Session, contexto_zope):
        """
        Inicializa sender com sessão SQLAlchemy e contexto Zope
        
        Args:
            session: Sessão SQLAlchemy
            contexto_zope: Contexto Zope (para acessar MailHost e props_sagl)
        """
        self.session = session
        self.context = contexto_zope
    
    def _obter_configuracoes_casa(self) -> Dict[str, str]:
        """
        Obtém end_email_casa e nom_casa do props_sagl
        
        Returns:
            Dicionário com 'end_email' e 'nom_casa'
        """
        try:
            casa = {}
            aux = self.context.sapl_documentos.props_sagl.propertyItems()
            for item in aux:
                casa[item[0]] = item[1]
            return {
                'end_email': casa.get('end_email_casa', ''),
                'nom_casa': casa.get('nom_casa', '')
            }
        except Exception as e:
            logger.warning(f"TramitacaoEmailSender._obter_configuracoes_casa - Erro ao obter configurações: {e}")
            return {'end_email': '', 'nom_casa': ''}
    
    def _gerar_link_visualizacao(self, tipo: str, cod_entidade: int) -> str:
        """
        Gera link para visualizar matéria/documento
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_entidade: cod_materia ou cod_documento
        
        Returns:
            URL completa para visualização
        """
        try:
            request = self.context.REQUEST
            server_url = request.SERVER_URL
            
            if tipo == 'MATERIA':
                return f"{server_url}/consultas/materia/materia_mostrar_proc?cod_materia={cod_entidade}"
            else:  # DOCUMENTO
                # Para documentos, retorna URL base do servidor (usuário deve autenticar)
                return server_url
        except Exception as e:
            logger.warning(f"TramitacaoEmailSender._gerar_link_visualizacao - Erro ao gerar link: {e}")
            return ""
    
    def _gerar_link_remocao_acompanhamento(self, txt_hash: str) -> str:
        """
        Gera link para remover acompanhamento
        
        Args:
            txt_hash: Hash do acompanhamento
        
        Returns:
            URL completa para remoção de acompanhamento
        """
        try:
            request = self.context.REQUEST
            server_url = request.SERVER_URL
            return f"{server_url}/consultas/materia/acompanhamento/acomp_materia_excluir_proc?txt_hash={txt_hash}"
        except Exception as e:
            logger.warning(f"TramitacaoEmailSender._gerar_link_remocao_acompanhamento - Erro ao gerar link: {e}")
            return ""
    
    def _formatar_data_registro(self) -> str:
        """Formata data/hora atual no formato usado nos e-mails"""
        try:
            return DateTime(datefmt='international').strftime('%d/%m/%Y às %H:%M')
        except Exception:
            return datetime.now().strftime('%d/%m/%Y às %H:%M')
    
    def _enviar_email(self, destinatario: str, assunto: str, html: str, remetente: str) -> bool:
        """
        Envia e-mail via MailHost do Zope
        
        Args:
            destinatario: E-mail do destinatário
            assunto: Assunto do e-mail
            html: Conteúdo HTML do e-mail
            remetente: E-mail do remetente
        
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            if not destinatario or not destinatario.strip():
                logger.debug(f"TramitacaoEmailSender._enviar_email - E-mail vazio, ignorando")
                return False
            
            mailhost = self.context.MailHost
            if not mailhost:
                logger.warning("TramitacaoEmailSender._enviar_email - MailHost não configurado")
                return False
            
            mMsg = MIMEText(html, 'html', "utf-8")
            mailhost.send(mMsg, destinatario, remetente, subject=assunto)
            
            logger.debug(f"TramitacaoEmailSender._enviar_email - E-mail enviado para {destinatario}")
            return True
        except Exception as e:
            logger.error(f"TramitacaoEmailSender._enviar_email - Erro ao enviar e-mail para {destinatario}: {e}", exc_info=True)
            return False
    
    def notificar_autores_materia(self, cod_materia: int) -> Dict[str, Any]:
        """
        Envia e-mail para autores da matéria quando há tramitação
        
        Args:
            cod_materia: Código da matéria
        
        Returns:
            Dicionário com estatísticas de envio
        """
        enviados = 0
        erros = 0
        
        try:
            # Busca matéria com relacionamentos
            # IMPORTANTE: Carrega relacionamentos do autor para obter nome correto conforme tipo
            materia = self.session.query(MateriaLegislativa).options(
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.tipo_autor),
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.parlamentar),
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.comissao),
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.bancada),
                selectinload(MateriaLegislativa.tipo_materia_legislativa)
            ).filter(
                MateriaLegislativa.cod_materia == cod_materia,
                MateriaLegislativa.ind_excluido == 0
            ).first()
            
            if not materia:
                logger.warning(f"TramitacaoEmailSender.notificar_autores_materia - Matéria {cod_materia} não encontrada")
                return {'enviados': 0, 'erros': 0, 'total': 0}
            
            # Obtém informações da matéria
            ementa = materia.txt_ementa or ''
            
            # Formata projeto
            tipo_materia = materia.tipo_materia_legislativa.des_tipo_materia if materia.tipo_materia_legislativa else ''
            projeto = f"{tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica}"
            
            # Obtém autores
            nomes_autores = []
            emails_autores = []
            for autoria in materia.autoria:
                if autoria.autor and autoria.autor.end_email:
                    # Usa função auxiliar para obter nome do autor considerando tipo de autor
                    nom_autor_valor = _get_nom_autor_join(autoria.autor)
                    if nom_autor_valor:
                        nomes_autores.append(nom_autor_valor)
                        emails_autores.append(autoria.autor.end_email)
            
            nom_autor = ', '.join(nomes_autores) if nomes_autores else ''
            
            # Busca última tramitação para obter data e status
            tramitacao = self.session.query(Tramitacao).join(
                StatusTramitacao, Tramitacao.cod_status == StatusTramitacao.cod_status
            ).filter(
                Tramitacao.cod_materia == cod_materia,
                Tramitacao.ind_ult_tramitacao == 1,
                Tramitacao.ind_excluido == 0
            ).first()
            
            if not tramitacao:
                logger.warning(f"TramitacaoEmailSender.notificar_autores_materia - Tramitação não encontrada para matéria {cod_materia}")
                return {'enviados': 0, 'erros': 0, 'total': 0}
            
            data = tramitacao.dat_tramitacao.strftime('%d/%m/%Y') if tramitacao.dat_tramitacao else ''
            status = tramitacao.status_tramitacao.des_status if tramitacao.status_tramitacao else ''
            
            # Configurações
            config_casa = self._obter_configuracoes_casa()
            remetente = config_casa['end_email']
            casa_legislativa = config_casa['nom_casa']
            data_registro = self._formatar_data_registro()
            link_mat = self._gerar_link_visualizacao('MATERIA', cod_materia)
            
            # Envia e-mail para cada autor
            for email in emails_autores:
                if email:
                    html = gerar_html_notificacao_autor(
                        projeto=projeto,
                        ementa=ementa,
                        nom_autor=nom_autor,
                        data=data,
                        status=status,
                        link_mat=link_mat,
                        casa_legislativa=casa_legislativa,
                        data_registro=data_registro
                    )
                    
                    assunto = f"{projeto} - Aviso de tramitação em {data_registro}"
                    
                    if self._enviar_email(email, assunto, html, remetente):
                        enviados += 1
                    else:
                        erros += 1
            
            logger.info(f"TramitacaoEmailSender.notificar_autores_materia - E-mails enviados: {enviados}, erros: {erros} (matéria {cod_materia})")
            return {'enviados': enviados, 'erros': erros, 'total': len(emails_autores)}
            
        except Exception as e:
            logger.error(f"TramitacaoEmailSender.notificar_autores_materia - Erro ao notificar autores: {e}", exc_info=True)
            return {'enviados': enviados, 'erros': erros + 1, 'total': enviados + erros}
    
    def notificar_acompanhantes_materia(self, cod_materia: int, cod_tramitacao: int) -> Dict[str, Any]:
        """
        Envia e-mail para acompanhantes e destino da tramitação de matéria
        
        Args:
            cod_materia: Código da matéria
            cod_tramitacao: Código da tramitação
        
        Returns:
            Dicionário com estatísticas de envio
        """
        enviados = 0
        erros = 0
        
        try:
            # Busca matéria
            # IMPORTANTE: Carrega relacionamentos do autor para obter nome correto conforme tipo
            materia = self.session.query(MateriaLegislativa).options(
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.tipo_autor),
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.parlamentar),
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.comissao),
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor).selectinload(Autor.bancada),
                selectinload(MateriaLegislativa.tipo_materia_legislativa)
            ).filter(
                MateriaLegislativa.cod_materia == cod_materia,
                MateriaLegislativa.ind_excluido == 0
            ).first()
            
            if not materia:
                logger.warning(f"TramitacaoEmailSender.notificar_acompanhantes_materia - Matéria {cod_materia} não encontrada")
                return {'enviados': 0, 'erros': 0, 'total': 0}
            
            # Busca tramitação com relacionamentos
            # IMPORTANTE: SQLAlchemy 2.0 não aceita strings em loader options - usar atributos da classe
            tramitacao = self.session.query(Tramitacao).options(
                selectinload(Tramitacao.status_tramitacao),
                selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                selectinload(Tramitacao.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                selectinload(Tramitacao.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                selectinload(Tramitacao.usuario)
            ).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao,
                Tramitacao.cod_materia == cod_materia,
                Tramitacao.ind_excluido == 0
            ).first()
            
            if not tramitacao:
                logger.warning(f"TramitacaoEmailSender.notificar_acompanhantes_materia - Tramitação {cod_tramitacao} não encontrada")
                return {'enviados': 0, 'erros': 0, 'total': 0}
            
            # Obtém informações da matéria
            ementa = materia.txt_ementa or ''
            tipo_materia = materia.tipo_materia_legislativa.des_tipo_materia if materia.tipo_materia_legislativa else ''
            projeto = f"{tipo_materia} nº {materia.num_ident_basica}/{materia.ano_ident_basica}"
            
            # Obtém autores
            nomes_autores = []
            for autoria in materia.autoria:
                if autoria.autor:
                    # Usa função auxiliar para obter nome do autor considerando tipo de autor
                    nom_autor_valor = _get_nom_autor_join(autoria.autor)
                    if nom_autor_valor:
                        nomes_autores.append(nom_autor_valor)
            nom_autor = ', '.join(nomes_autores) if nomes_autores else ''
            
            # Obtém dados da tramitação
            data = tramitacao.dat_tramitacao.strftime('%d/%m/%Y') if tramitacao.dat_tramitacao else ''
            status = tramitacao.status_tramitacao.des_status if tramitacao.status_tramitacao else ''
            
            # Obtém unidade local (origem)
            unidade_local = ''
            if hasattr(tramitacao, 'unidade_tramitacao_') and tramitacao.unidade_tramitacao_:
                # Usa mesma lógica de _get_nome_unidade_tramitacao
                if tramitacao.unidade_tramitacao_.comissao:
                    unidade_local = tramitacao.unidade_tramitacao_.comissao.nom_comissao
                elif tramitacao.unidade_tramitacao_.orgao:
                    unidade_local = tramitacao.unidade_tramitacao_.orgao.nom_orgao
                elif tramitacao.unidade_tramitacao_.parlamentar:
                    unidade_local = tramitacao.unidade_tramitacao_.parlamentar.nom_parlamentar
                else:
                    unidade_local = tramitacao.unidade_tramitacao_.nom_unidade_join or ''
            
            # Lista de destinatários (acompanhantes + destino)
            destinatarios = []
            
            # Busca acompanhantes
            acompanhantes = self.session.query(AcompMateria).filter(
                AcompMateria.cod_materia == cod_materia
            ).all()
            
            for acomp in acompanhantes:
                if acomp.end_email:
                    destinatarios.append({
                        'end_email': acomp.end_email,
                        'txt_hash': acomp.txt_hash or ''
                    })
            
            # Adiciona destino (usuário ou unidade)
            destino_nome = ''
            if tramitacao.cod_usuario_dest and tramitacao.usuario:
                if tramitacao.usuario.end_email:
                    destinatarios.append({
                        'end_email': tramitacao.usuario.end_email,
                        'txt_hash': ''
                    })
                destino_nome = tramitacao.usuario.nom_completo or ''
            elif tramitacao.unidade_tramitacao:
                # ✅ CORRETO: Usa end_email (o modelo UnidadeTramitacao tem end_email, não end_email)
                end_email_unidade = getattr(tramitacao.unidade_tramitacao, 'end_email', None) or ''
                if end_email_unidade:
                    destinatarios.append({
                        'end_email': end_email_unidade,
                        'txt_hash': ''
                    })
                # Obtém nome do destino
                if tramitacao.unidade_tramitacao.comissao:
                    destino_nome = tramitacao.unidade_tramitacao.comissao.nom_comissao
                elif tramitacao.unidade_tramitacao.orgao:
                    destino_nome = tramitacao.unidade_tramitacao.orgao.nom_orgao
                elif tramitacao.unidade_tramitacao.parlamentar:
                    destino_nome = tramitacao.unidade_tramitacao.parlamentar.nom_parlamentar
                else:
                    destino_nome = tramitacao.unidade_tramitacao.nom_unidade_join or ''
            
            # Configurações
            config_casa = self._obter_configuracoes_casa()
            remetente = config_casa['end_email']
            casa_legislativa = config_casa['nom_casa']
            data_registro = self._formatar_data_registro()
            link_mat = self._gerar_link_visualizacao('MATERIA', cod_materia)
            
            # Envia e-mail para cada destinatário
            for dic in destinatarios:
                email = dic['end_email']
                txt_hash = dic['txt_hash']
                
                if email:
                    link_remocao = self._gerar_link_remocao_acompanhamento(txt_hash) if txt_hash else ''
                    
                    html = gerar_html_notificacao_acompanhamento_materia(
                        projeto=projeto,
                        ementa=ementa,
                        nom_autor=nom_autor,
                        data=data,
                        unidade_local=unidade_local,
                        destino=destino_nome,
                        status=status,
                        link_mat=link_mat,
                        link_remocao=link_remocao,
                        casa_legislativa=casa_legislativa,
                        data_registro=data_registro
                    )
                    
                    assunto = f"{projeto} - Aviso de tramitação registrada em {data_registro}"
                    
                    if self._enviar_email(email, assunto, html, remetente):
                        enviados += 1
                    else:
                        erros += 1
            
            logger.info(f"TramitacaoEmailSender.notificar_acompanhantes_materia - E-mails enviados: {enviados}, erros: {erros} (matéria {cod_materia})")
            return {'enviados': enviados, 'erros': erros, 'total': len(destinatarios)}
            
        except Exception as e:
            logger.error(f"TramitacaoEmailSender.notificar_acompanhantes_materia - Erro ao notificar acompanhantes: {e}", exc_info=True)
            return {'enviados': enviados, 'erros': erros + 1, 'total': enviados + erros}
    
    def notificar_destino_documento(self, cod_documento: int, cod_tramitacao: int) -> Dict[str, Any]:
        """
        Envia e-mail para usuário/unidade destino do documento
        
        Args:
            cod_documento: Código do documento administrativo
            cod_tramitacao: Código da tramitação
        
        Returns:
            Dicionário com estatísticas de envio
        """
        enviados = 0
        erros = 0
        
        try:
            # Busca documento
            documento = self.session.query(DocumentoAdministrativo).options(
                selectinload(DocumentoAdministrativo.tipo_documento_administrativo)
            ).filter(
                DocumentoAdministrativo.cod_documento == cod_documento,
                DocumentoAdministrativo.ind_excluido == 0
            ).first()
            
            if not documento:
                logger.warning(f"TramitacaoEmailSender.notificar_destino_documento - Documento {cod_documento} não encontrado")
                return {'enviados': 0, 'erros': 0, 'total': 0}
            
            # Busca tramitação com relacionamentos
            # IMPORTANTE: SQLAlchemy 2.0 não aceita strings em loader options - usar atributos da classe
            tramitacao = self.session.query(TramitacaoAdministrativo).options(
                selectinload(TramitacaoAdministrativo.status_tramitacao_administrativo),
                selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.comissao),
                selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.orgao),
                selectinload(TramitacaoAdministrativo.unidade_tramitacao_).selectinload(UnidadeTramitacao.parlamentar),
                selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.comissao),
                selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.orgao),
                selectinload(TramitacaoAdministrativo.unidade_tramitacao).selectinload(UnidadeTramitacao.parlamentar),
                selectinload(TramitacaoAdministrativo.usuario)
            ).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                TramitacaoAdministrativo.cod_documento == cod_documento,
                TramitacaoAdministrativo.ind_excluido == 0
            ).first()
            
            if not tramitacao:
                logger.warning(f"TramitacaoEmailSender.notificar_destino_documento - Tramitação {cod_tramitacao} não encontrada")
                return {'enviados': 0, 'erros': 0, 'total': 0}
            
            # Verifica se há destino com e-mail
            end_email = None
            destino_nome = ''
            
            if tramitacao.cod_usuario_dest and tramitacao.usuario:
                if tramitacao.usuario.end_email:
                    end_email = tramitacao.usuario.end_email
                    destino_nome = tramitacao.usuario.nom_completo or ''
            elif tramitacao.unidade_tramitacao:
                if tramitacao.unidade_tramitacao.end_email:
                    end_email = tramitacao.unidade_tramitacao.end_email
                # Obtém nome do destino
                if tramitacao.unidade_tramitacao.comissao:
                    destino_nome = tramitacao.unidade_tramitacao.comissao.nom_comissao
                elif tramitacao.unidade_tramitacao.orgao:
                    destino_nome = tramitacao.unidade_tramitacao.orgao.nom_orgao
                elif tramitacao.unidade_tramitacao.parlamentar:
                    destino_nome = tramitacao.unidade_tramitacao.parlamentar.nom_parlamentar
                else:
                    destino_nome = tramitacao.unidade_tramitacao.nom_unidade_join or ''
            
            if not end_email or not destino_nome:
                logger.debug(f"TramitacaoEmailSender.notificar_destino_documento - Sem e-mail ou nome de destino para documento {cod_documento}")
                return {'enviados': 0, 'erros': 0, 'total': 0}
            
            # Obtém informações do documento
            ementa = documento.txt_assunto or ''
            tipo_doc = documento.tipo_documento_administrativo.des_tipo_documento if documento.tipo_documento_administrativo else ''
            proc_adm = f"{tipo_doc} nº {documento.num_documento}/{documento.ano_documento}"
            interessado = documento.txt_interessado or ''
            
            # Obtém dados da tramitação
            status = tramitacao.status_tramitacao_administrativo.des_status if tramitacao.status_tramitacao_administrativo else ''
            
            # Obtém unidade local (origem)
            unidade_local = ''
            if hasattr(tramitacao, 'unidade_tramitacao_') and tramitacao.unidade_tramitacao_:
                if tramitacao.unidade_tramitacao_.comissao:
                    unidade_local = tramitacao.unidade_tramitacao_.comissao.nom_comissao
                elif tramitacao.unidade_tramitacao_.orgao:
                    unidade_local = tramitacao.unidade_tramitacao_.orgao.nom_orgao
                elif tramitacao.unidade_tramitacao_.parlamentar:
                    unidade_local = tramitacao.unidade_tramitacao_.parlamentar.nom_parlamentar
                else:
                    unidade_local = tramitacao.unidade_tramitacao_.nom_unidade_join or ''
            
            # Configurações
            config_casa = self._obter_configuracoes_casa()
            remetente = config_casa['end_email']
            casa_legislativa = config_casa['nom_casa']
            data_registro = self._formatar_data_registro()
            link_doc = self._gerar_link_visualizacao('DOCUMENTO', cod_documento)
            
            # Gera HTML
            html = gerar_html_notificacao_documento(
                proc_adm=proc_adm,
                ementa=ementa,
                interessado=interessado,
                unidade_local=unidade_local,
                destino=destino_nome,
                status=status,
                link_doc=link_doc,
                casa_legislativa=casa_legislativa,
                data_registro=data_registro
            )
            
            assunto = f"Processo Administrativo - {proc_adm} - Notificação de Despacho em {data_registro}"
            
            if self._enviar_email(end_email, assunto, html, remetente):
                enviados += 1
            else:
                erros += 1
            
            logger.info(f"TramitacaoEmailSender.notificar_destino_documento - E-mail enviado: {enviados}, erros: {erros} (documento {cod_documento})")
            return {'enviados': enviados, 'erros': erros, 'total': 1}
            
        except Exception as e:
            logger.error(f"TramitacaoEmailSender.notificar_destino_documento - Erro ao notificar destino: {e}", exc_info=True)
            return {'enviados': enviados, 'erros': erros + 1, 'total': enviados + erros}
