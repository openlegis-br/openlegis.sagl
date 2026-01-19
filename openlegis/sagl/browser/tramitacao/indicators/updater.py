# -*- coding: utf-8 -*-
"""Atualização de indicadores de tramitação (fim/retorno)"""

from typing import Optional
from sqlalchemy.orm import Session
from zope.sqlalchemy import mark_changed
from openlegis.sagl.models.models import (
    StatusTramitacao, StatusTramitacaoAdministrativo,
    MateriaLegislativa, DocumentoAdministrativo
)
import logging

logger = logging.getLogger(__name__)


class TramitacaoIndicadorUpdater:
    """Atualiza indicadores de tramitação baseado no status"""
    
    def __init__(self, session: Session):
        """
        Inicializa updater com sessão SQLAlchemy
        
        Args:
            session: Sessão SQLAlchemy
        """
        self.session = session
    
    def atualizar_indicadores_materia(self, cod_materia: int, cod_status: Optional[int]) -> None:
        """
        Atualiza indicadores de tramitação da matéria baseado no status
        
        Se o status tiver ind_fim_tramitacao=1, define ind_tramitacao=0 (fim)
        Se o status tiver ind_retorno_tramitacao=1, define ind_tramitacao=1 (retorno)
        
        Args:
            cod_materia: Código da matéria
            cod_status: Código do status (opcional)
        """
        if not cod_status:
            logger.debug(f"TramitacaoIndicadorUpdater.atualizar_indicadores_materia - cod_status não fornecido, ignorando")
            return
        
        try:
            # Busca o status de tramitação
            status = self.session.query(StatusTramitacao).filter(
                StatusTramitacao.cod_status == cod_status,
                StatusTramitacao.ind_excluido == 0
            ).first()
            
            if not status:
                logger.warning(f"TramitacaoIndicadorUpdater.atualizar_indicadores_materia - Status {cod_status} não encontrado")
                return
            
            # Busca a matéria
            materia = self.session.query(MateriaLegislativa).filter(
                MateriaLegislativa.cod_materia == cod_materia,
                MateriaLegislativa.ind_excluido == 0
            ).first()
            
            if not materia:
                logger.warning(f"TramitacaoIndicadorUpdater.atualizar_indicadores_materia - Matéria {cod_materia} não encontrada")
                return
            
            atualizado = False
            
            # Verifica se o status indica fim de tramitação
            if status.ind_fim_tramitacao == 1:
                if materia.ind_tramitacao != 0:
                    materia.ind_tramitacao = 0
                    atualizado = True
                    logger.info(f"TramitacaoIndicadorUpdater.atualizar_indicadores_materia - Matéria {cod_materia} marcada como fim de tramitação (ind_tramitacao=0)")
            
            # Verifica se o status indica retorno de tramitação
            elif status.ind_retorno_tramitacao == 1:
                if materia.ind_tramitacao != 1:
                    materia.ind_tramitacao = 1
                    atualizado = True
                    logger.info(f"TramitacaoIndicadorUpdater.atualizar_indicadores_materia - Matéria {cod_materia} marcada como retorno de tramitação (ind_tramitacao=1)")
            
            if atualizado:
                # Marca sessão como alterada para o Zope transaction manager
                mark_changed(self.session, keep_session=True)
                logger.debug(f"TramitacaoIndicadorUpdater.atualizar_indicadores_materia - Indicadores atualizados para matéria {cod_materia}")
            
        except Exception as e:
            logger.error(f"TramitacaoIndicadorUpdater.atualizar_indicadores_materia - Erro ao atualizar indicadores: {e}", exc_info=True)
            raise
    
    def atualizar_indicadores_documento(self, cod_documento: int, cod_status: Optional[int]) -> None:
        """
        Atualiza indicadores de tramitação do documento baseado no status
        
        Se o status tiver ind_fim_tramitacao=1, define ind_tramitacao=0 (fim)
        Se o status tiver ind_retorno_tramitacao=1, define ind_tramitacao=1 (retorno)
        
        Args:
            cod_documento: Código do documento administrativo
            cod_status: Código do status (opcional)
        """
        if not cod_status:
            logger.debug(f"TramitacaoIndicadorUpdater.atualizar_indicadores_documento - cod_status não fornecido, ignorando")
            return
        
        try:
            # Busca o status de tramitação administrativo
            status = self.session.query(StatusTramitacaoAdministrativo).filter(
                StatusTramitacaoAdministrativo.cod_status == cod_status,
                StatusTramitacaoAdministrativo.ind_excluido == 0
            ).first()
            
            if not status:
                logger.warning(f"TramitacaoIndicadorUpdater.atualizar_indicadores_documento - Status {cod_status} não encontrado")
                return
            
            # Busca o documento
            documento = self.session.query(DocumentoAdministrativo).filter(
                DocumentoAdministrativo.cod_documento == cod_documento,
                DocumentoAdministrativo.ind_excluido == 0
            ).first()
            
            if not documento:
                logger.warning(f"TramitacaoIndicadorUpdater.atualizar_indicadores_documento - Documento {cod_documento} não encontrado")
                return
            
            atualizado = False
            
            # Verifica se o status indica fim de tramitação
            if status.ind_fim_tramitacao == 1:
                if documento.ind_tramitacao != 0:
                    documento.ind_tramitacao = 0
                    atualizado = True
                    logger.info(f"TramitacaoIndicadorUpdater.atualizar_indicadores_documento - Documento {cod_documento} marcado como fim de tramitação (ind_tramitacao=0)")
            
            # Verifica se o status indica retorno de tramitação
            elif status.ind_retorno_tramitacao == 1:
                if documento.ind_tramitacao != 1:
                    documento.ind_tramitacao = 1
                    atualizado = True
                    logger.info(f"TramitacaoIndicadorUpdater.atualizar_indicadores_documento - Documento {cod_documento} marcado como retorno de tramitação (ind_tramitacao=1)")
            
            if atualizado:
                # Marca sessão como alterada para o Zope transaction manager
                mark_changed(self.session, keep_session=True)
                logger.debug(f"TramitacaoIndicadorUpdater.atualizar_indicadores_documento - Indicadores atualizados para documento {cod_documento}")
            
        except Exception as e:
            logger.error(f"TramitacaoIndicadorUpdater.atualizar_indicadores_documento - Erro ao atualizar indicadores: {e}", exc_info=True)
            raise
