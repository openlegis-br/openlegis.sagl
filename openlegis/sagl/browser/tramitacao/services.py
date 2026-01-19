# -*- coding: utf-8 -*-
"""Service layer para tramitação unificada"""

from typing import Literal, Optional, Dict, Any, List
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from zope.sqlalchemy import mark_changed
from openlegis.sagl.models.models import (
    Tramitacao, TramitacaoAdministrativo, StatusTramitacao,
    StatusTramitacaoAdministrativo, MateriaLegislativa, DocumentoAdministrativo
)
import logging

logger = logging.getLogger(__name__)

TipoTramitacao = Literal['MATERIA', 'DOCUMENTO']


class TramitacaoService:
    """Service layer unificado para tramitações"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def _setup_cache_invalidation_hook(self, cod_usuario: Optional[int] = None, cod_unid_tram_dest: Optional[int] = None):
        """
        Configura invalidação de cache APÓS o commit usando afterCommitHook.
        
        ✅ CORRETO: Side-effects (cache) rodam APÓS o commit, não durante a transação.
        
        Args:
            cod_usuario: Código do usuário (opcional)
            cod_unid_tram_dest: Código da unidade de destino (opcional)
        """
        try:
            import transaction
            from .cache import invalidate_cache_contadores
            
            # Captura valores primitivos ANTES de usar no hook
            cod_user = cod_usuario
            cod_unid = cod_unid_tram_dest
            
            # Adiciona hook que será executado APÓS o commit bem-sucedido
            transaction.get().addAfterCommitHook(
                lambda success, *args:
                    success and invalidate_cache_contadores(cod_user, cod_unid)
            )
        except (ImportError, AttributeError) as e:
            # Se não conseguir importar, apenas loga (não é crítico)
            logger.debug(f"TramitacaoService._setup_cache_invalidation_hook - Não foi possível configurar invalidação de cache: {e}")
    
    def _invalidate_cache_contadores_auto(self, cod_usuario: Optional[int] = None, cod_unid_tram_dest: Optional[int] = None):
        """
        Invalida cache de contadores automaticamente após o commit.
        
        Este método configura a invalidação de cache para ocorrer após o commit
        da transação, evitando interferências na transação atual.
        
        Args:
            cod_usuario: Código do usuário (opcional)
            cod_unid_tram_dest: Código da unidade de destino (opcional)
        """
        self._setup_cache_invalidation_hook(cod_usuario, cod_unid_tram_dest)
    
    def calcular_prazo(self, cod_status: int, tipo: TipoTramitacao, data_base: Optional[date] = None) -> Optional[date]:
        """Calcula prazo baseado no status"""
        if data_base is None:
            data_base = date.today()
        
        if tipo == 'MATERIA':
            status = self.session.query(StatusTramitacao).filter(
                StatusTramitacao.cod_status == cod_status,
                StatusTramitacao.ind_excluido == 0
            ).first()
        else:
            status = self.session.query(StatusTramitacaoAdministrativo).filter(
                StatusTramitacaoAdministrativo.cod_status == cod_status,
                StatusTramitacaoAdministrativo.ind_excluido == 0
            ).first()
        
        if status and status.num_dias_prazo:
            from datetime import timedelta
            return data_base + timedelta(days=status.num_dias_prazo)
        
        return None
    
    def verificar_tramitacao_duplicada(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        cod_unid_tram_local: int,
        cod_unid_tram_dest: int,
        cod_usuario_local: int,
        cod_status: int,
        cod_tramitacao_excluir: Optional[int] = None
    ) -> bool:
        """Verifica se já existe tramitação idêntica"""
        if tipo == 'MATERIA':
            query = self.session.query(Tramitacao).filter(
                Tramitacao.cod_materia == cod_entidade,
                Tramitacao.cod_unid_tram_local == cod_unid_tram_local,
                Tramitacao.cod_unid_tram_dest == cod_unid_tram_dest,
                Tramitacao.cod_usuario_local == cod_usuario_local,
                Tramitacao.cod_status == cod_status,
                Tramitacao.ind_ult_tramitacao == 1,
                Tramitacao.ind_excluido == 0
            )
        else:
            query = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_documento == cod_entidade,
                TramitacaoAdministrativo.cod_unid_tram_local == cod_unid_tram_local,
                TramitacaoAdministrativo.cod_unid_tram_dest == cod_unid_tram_dest,
                TramitacaoAdministrativo.cod_usuario_local == cod_usuario_local,
                TramitacaoAdministrativo.cod_status == cod_status,
                TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                TramitacaoAdministrativo.ind_excluido == 0
            )
        
        if cod_tramitacao_excluir:
            if tipo == 'MATERIA':
                query = query.filter(Tramitacao.cod_tramitacao != cod_tramitacao_excluir)
            else:
                query = query.filter(TramitacaoAdministrativo.cod_tramitacao != cod_tramitacao_excluir)
        
        return query.first() is not None
    
    def atualizar_ultima_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        cod_tramitacao_anterior: Optional[int] = None
    ):
        """Atualiza ind_ult_tramitacao da tramitação anterior"""
        if cod_tramitacao_anterior:
            if tipo == 'MATERIA':
                tram_anterior = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao_anterior,
                    Tramitacao.cod_materia == cod_entidade
                ).first()
                if tram_anterior:
                    tram_anterior.ind_ult_tramitacao = 0
                    # Registra recebimento automático
                    if not tram_anterior.dat_recebimento:
                        tram_anterior.dat_recebimento = datetime.now()
            else:
                tram_anterior = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao_anterior,
                    TramitacaoAdministrativo.cod_documento == cod_entidade
                ).first()
                if tram_anterior:
                    tram_anterior.ind_ult_tramitacao = 0
                    # Registra recebimento automático
                    if not tram_anterior.dat_recebimento:
                        tram_anterior.dat_recebimento = datetime.now()
    
    def salvar_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        dados: Dict[str, Any],
        cod_tramitacao: Optional[int] = None
    ) -> int:
        """
        Salva tramitação (inclui ou atualiza)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_entidade: cod_materia ou cod_documento
            dados: Dicionário com dados da tramitação
            cod_tramitacao: Se fornecido, atualiza; senão, inclui nova
        
        Returns:
            cod_tramitacao da tramitação salva
        """
        # Calcula prazo se não fornecido
        if not dados.get('dat_fim_prazo') and dados.get('cod_status'):
            prazo = self.calcular_prazo(dados['cod_status'], tipo)
            if prazo:
                dados['dat_fim_prazo'] = prazo
        
        # Converte dat_encaminha
        dat_encaminha = None
        if dados.get('dat_encaminha'):
            if isinstance(dados['dat_encaminha'], str):
                try:
                    dat_encaminha = datetime.strptime(dados['dat_encaminha'], '%d/%m/%Y %H:%M')
                except:
                    try:
                        dat_encaminha = datetime.strptime(dados['dat_encaminha'], '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
            else:
                dat_encaminha = dados['dat_encaminha']
        
        if tipo == 'MATERIA':
            if cod_tramitacao:
                # Atualiza
                tram = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao
                ).first()
                if not tram:
                    raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
            else:
                # Nova tramitação
                tram = Tramitacao()
                tram.cod_materia = cod_entidade
                tram.dat_tramitacao = datetime.now()
                # ✅ CORRETO: Por padrão, nova tramitação é rascunho (ind_ult_tramitacao = 0)
                # Só será 1 se dados especificar (quando é envio via enviar_tramitacao)
                tram.ind_ult_tramitacao = dados.get('ind_ult_tramitacao', 0)
                tram.ind_excluido = 0
            
            # Atualiza campos
            tram.cod_unid_tram_local = dados.get('cod_unid_tram_local')
            tram.cod_usuario_local = dados.get('cod_usuario_local')
            tram.dat_encaminha = dat_encaminha
            tram.cod_unid_tram_dest = dados.get('cod_unid_tram_dest')
            tram.cod_usuario_dest = dados.get('cod_usuario_dest')
            tram.cod_status = dados.get('cod_status')
            tram.ind_urgencia = dados.get('ind_urgencia', 0)
            tram.sgl_turno = dados.get('sgl_turno')
            tram.txt_tramitacao = dados.get('txt_tramitacao', '')
            tram.dat_fim_prazo = dados.get('dat_fim_prazo')
            # ✅ CRÍTICO: Atualiza ind_ult_tramitacao (importante para rascunhos sendo enviados)
            if 'ind_ult_tramitacao' in dados:
                tram.ind_ult_tramitacao = dados.get('ind_ult_tramitacao')
            
            if not cod_tramitacao:
                self.session.add(tram)
                # Flush é necessário para gerar cod_tramitacao (PK auto-incremento)
                # A sessão está registrada no transaction manager, então flush() é seguro
                self.session.flush()
            
            # Atualiza última tramitação anterior (apenas se esta tramitação é a nova última)
            # ✅ CORRETO: Só atualiza tramitação anterior se esta tramitação tem ind_ult_tramitacao = 1
            if not cod_tramitacao and tram.ind_ult_tramitacao == 1:
                # OTIMIZAÇÃO: Query usa índice idx_tramitacao_materia_ult
                ultima = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_materia == cod_entidade,
                    Tramitacao.ind_ult_tramitacao == 1,
                    Tramitacao.ind_excluido == 0
                ).first()
                if ultima and ultima.cod_tramitacao != tram.cod_tramitacao:
                    self.atualizar_ultima_tramitacao('MATERIA', cod_entidade, ultima.cod_tramitacao)
            
            # ✅ CORRETO: Captura valores primitivos ANTES de usar no hook
            cod_tram = tram.cod_tramitacao
            cod_user = tram.cod_usuario_local
            cod_unid = tram.cod_unid_tram_dest
            
            # ✅ CORRETO: Marca sessão como alterada SEM keep_session=True
            # A sessão deve morrer junto com a transação
            mark_changed(self.session)
            
            # ✅ CORRETO: Side-effects (cache) via afterCommitHook APÓS o commit
            # Não executa durante a transação, apenas após commit bem-sucedido
            self._setup_cache_invalidation_hook(cod_user, cod_unid)
            
            logger.info(f"TramitacaoService.salvar_tramitacao - Tramitação (MATERIA) salva - sessão id: {id(self.session)}, cod_tramitacao: {cod_tram}")
            return cod_tram
        else:
            if cod_tramitacao:
                # Atualiza
                tram = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao
                ).first()
                if not tram:
                    raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
            else:
                # Nova tramitação
                tram = TramitacaoAdministrativo()
                tram.cod_documento = cod_entidade
                tram.dat_tramitacao = datetime.now()
                # ✅ CORRETO: Por padrão, nova tramitação é rascunho (ind_ult_tramitacao = 0)
                # Só será 1 se dados especificar (quando é envio via enviar_tramitacao)
                tram.ind_ult_tramitacao = dados.get('ind_ult_tramitacao', 0)
                tram.ind_excluido = 0
            
            # Atualiza campos
            tram.cod_unid_tram_local = dados.get('cod_unid_tram_local')
            tram.cod_usuario_local = dados.get('cod_usuario_local')
            tram.dat_encaminha = dat_encaminha
            tram.cod_unid_tram_dest = dados.get('cod_unid_tram_dest')
            tram.cod_usuario_dest = dados.get('cod_usuario_dest')
            tram.cod_status = dados.get('cod_status')
            tram.txt_tramitacao = dados.get('txt_tramitacao', '')
            tram.dat_fim_prazo = dados.get('dat_fim_prazo')
            # ✅ CRÍTICO: Atualiza ind_ult_tramitacao (importante para rascunhos sendo enviados)
            if 'ind_ult_tramitacao' in dados:
                tram.ind_ult_tramitacao = dados.get('ind_ult_tramitacao')
            
            if not cod_tramitacao:
                self.session.add(tram)
                # Flush é necessário para gerar cod_tramitacao (PK auto-incremento)
                # A sessão está registrada no transaction manager, então flush() é seguro
                self.session.flush()
            
            # Atualiza última tramitação anterior (apenas se esta tramitação é a nova última)
            # ✅ CORRETO: Só atualiza tramitação anterior se esta tramitação tem ind_ult_tramitacao = 1
            if not cod_tramitacao and tram.ind_ult_tramitacao == 1:
                # OTIMIZAÇÃO: Query usa índice tramitacao_ind1
                ultima = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_documento == cod_entidade,
                    TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                    TramitacaoAdministrativo.ind_excluido == 0
                ).first()
                if ultima and ultima.cod_tramitacao != tram.cod_tramitacao:
                    self.atualizar_ultima_tramitacao('DOCUMENTO', cod_entidade, ultima.cod_tramitacao)
            
            # ✅ CORRETO: Captura valores primitivos ANTES de usar no hook
            cod_tram = tram.cod_tramitacao
            cod_user = tram.cod_usuario_local
            cod_unid = tram.cod_unid_tram_dest
            
            # ✅ CORRETO: Marca sessão como alterada SEM keep_session=True
            # A sessão deve morrer junto com a transação
            mark_changed(self.session)
            
            # ✅ CORRETO: Side-effects (cache) via afterCommitHook APÓS o commit
            # Não executa durante a transação, apenas após commit bem-sucedido
            self._setup_cache_invalidation_hook(cod_user, cod_unid)
            
            logger.info(f"TramitacaoService.salvar_tramitacao - Tramitação (DOCUMENTO) salva - sessão id: {id(self.session)}, cod_tramitacao: {cod_tram}")
            return cod_tram
    
    def _validar_dados_tramitacao(self, dados: Dict[str, Any], enviar: bool = False):
        """
        Valida dados da tramitação
        
        Args:
            dados: Dicionário com dados da tramitação
            enviar: Se True, validações mais rigorosas (para envio)
        
        Raises:
            ValueError: Se validação falhar
        """
        if enviar:
            # Validações para envio
            if not dados.get('cod_unid_tram_local'):
                raise ValueError('Unidade de origem é obrigatória')
            
            if not dados.get('cod_usuario_local'):
                raise ValueError('Usuário de origem é obrigatório')
            
            if not dados.get('cod_unid_tram_dest'):
                raise ValueError('Unidade de destino é obrigatória')
            
            if not dados.get('cod_status'):
                raise ValueError('Status é obrigatório')
        
        # Valida data de fim de prazo (se fornecida, deve ser >= hoje)
        if dados.get('dat_fim_prazo'):
            dat_fim_prazo = dados['dat_fim_prazo']
            # Normaliza para date para comparação segura
            if isinstance(dat_fim_prazo, datetime):
                dat_fim_prazo_date = dat_fim_prazo.date()
            elif isinstance(dat_fim_prazo, date):
                dat_fim_prazo_date = dat_fim_prazo
            else:
                # Se for string ou outro tipo, tenta converter
                if isinstance(dat_fim_prazo, str):
                    try:
                        # Tenta parsear como datetime primeiro
                        dat_fim_prazo = datetime.strptime(dat_fim_prazo, '%Y-%m-%d %H:%M:%S')
                        dat_fim_prazo_date = dat_fim_prazo.date()
                    except ValueError:
                        try:
                            # Tenta parsear como date
                            dat_fim_prazo = datetime.strptime(dat_fim_prazo, '%Y-%m-%d')
                            dat_fim_prazo_date = dat_fim_prazo.date()
                        except ValueError:
                            raise ValueError('Formato de data inválido para dat_fim_prazo')
                else:
                    raise ValueError(f'Tipo inválido para dat_fim_prazo: {type(dat_fim_prazo)}')
            
            if dat_fim_prazo_date < date.today():
                raise ValueError('Data de fim de prazo não pode ser anterior à data atual')
    
    def receber_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_tramitacao: int,
        cod_usuario: int
    ) -> bool:
        """
        Registra recebimento de tramitação pelo destinatário.
        
        Condições:
        - dat_encaminha deve existir (foi enviada)
        - dat_recebimento deve ser NULL (ainda não recebida)
        - Usuário deve ser o destinatário (cod_usuario_dest OU unidade destino pertence ao usuário)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            cod_usuario: Código do usuário que está recebendo
        
        Returns:
            True se recebimento registrado com sucesso, False caso contrário
        """
        if tipo == 'MATERIA':
            tram = self.session.query(Tramitacao).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao,
                Tramitacao.ind_excluido == 0
            ).first()
        else:
            tram = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                TramitacaoAdministrativo.ind_excluido == 0
            ).first()
        
        if not tram:
            raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
        
        # Valida que foi enviada
        if not tram.dat_encaminha:
            # Tramitação não foi enviada, não precisa registrar recebimento
            logger.debug(f"Tramitação {cod_tramitacao} não foi enviada, não registra recebimento")
            return False
        
        # Valida que ainda não foi recebida
        if tram.dat_recebimento:
            # Já foi recebida, não precisa registrar novamente
            logger.debug(f"Tramitação {cod_tramitacao} já foi recebida em {tram.dat_recebimento}")
            return False
        
        # Valida que usuário é destinatário
        # Pode ser destinatário específico (cod_usuario_dest) OU parte da unidade de destino
        is_destinatario = False
        if tram.cod_usuario_dest:
            # Tramitação enviada para usuário específico
            is_destinatario = (tram.cod_usuario_dest == cod_usuario)
        else:
            # Tramitação enviada para unidade (qualquer usuário da unidade pode receber)
            # Verifica se usuário pertence à unidade de destino
            from openlegis.sagl.models.models import UsuarioUnidTram
            usuario_unidade = self.session.query(UsuarioUnidTram).filter(
                UsuarioUnidTram.cod_usuario == cod_usuario,
                UsuarioUnidTram.cod_unid_tramitacao == tram.cod_unid_tram_dest,
                UsuarioUnidTram.ind_excluido == 0
            ).first()
            is_destinatario = (usuario_unidade is not None)
        
        if not is_destinatario:
            # Usuário não é destinatário, não pode registrar recebimento
            logger.debug(f"Usuário {cod_usuario} não é destinatário da tramitação {cod_tramitacao}")
            return False
        
        # Registra recebimento
        tram.dat_recebimento = datetime.now()
        
        logger.info(f"Recebimento registrado para tramitação {cod_tramitacao} pelo usuário {cod_usuario}")
        
        # ✅ CORRETO: Captura valores primitivos ANTES de usar no hook
        cod_user = tram.cod_usuario_local
        cod_unid = tram.cod_unid_tram_dest
        
        # Marca sessão como alterada para o Zope transaction manager
        # O Zope cuidará de commit/abort automaticamente
        mark_changed(self.session)
        
        # ✅ CORRETO: Side-effects (cache) via afterCommitHook APÓS o commit
        self._setup_cache_invalidation_hook(cod_user, cod_unid)
        
        return True
    
    def _atualizar_indicadores_materia(self, cod_materia: int, cod_status: Optional[int]) -> None:
        """
        Atualiza indicadores de tramitação da matéria baseado no status
        
        Args:
            cod_materia: Código da matéria
            cod_status: Código do status (opcional)
        """
        try:
            from .indicators.updater import TramitacaoIndicadorUpdater
            updater = TramitacaoIndicadorUpdater(self.session)
            updater.atualizar_indicadores_materia(cod_materia, cod_status)
        except Exception as e:
            logger.error(f"TramitacaoService._atualizar_indicadores_materia - Erro: {e}", exc_info=True)
            raise
    
    def _atualizar_indicadores_documento(self, cod_documento: int, cod_status: Optional[int]) -> None:
        """
        Atualiza indicadores de tramitação do documento baseado no status
        
        Args:
            cod_documento: Código do documento administrativo
            cod_status: Código do status (opcional)
        """
        try:
            from .indicators.updater import TramitacaoIndicadorUpdater
            updater = TramitacaoIndicadorUpdater(self.session)
            updater.atualizar_indicadores_documento(cod_documento, cod_status)
        except Exception as e:
            logger.error(f"TramitacaoService._atualizar_indicadores_documento - Erro: {e}", exc_info=True)
            raise
    
    def excluir_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_tramitacao: int
    ) -> bool:
        """Exclui tramitação (soft delete)"""
        if tipo == 'MATERIA':
            tram = self.session.query(Tramitacao).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao
            ).first()
        else:
            tram = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao
            ).first()
        
        if not tram:
            return False
        
        tram.ind_excluido = 1
        # Marca sessão como alterada para o Zope transaction manager
        # O Zope cuidará de commit/abort automaticamente
        mark_changed(self.session)
        
        # Invalida cache de contadores automaticamente
        self._invalidate_cache_contadores_auto(tram.cod_usuario_local, tram.cod_unid_tram_dest)
        
        return True
    
    def retomar_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_tramitacao: int,
        cod_usuario: int
    ) -> bool:
        """
        Retoma tramitação enviada (volta para rascunho)
        
        Condições:
        - dat_encaminha deve existir (foi enviada)
        - dat_visualizacao deve ser NULL (destino não visualizou)
        - dat_recebimento deve ser NULL (destino não recebeu)
        - cod_usuario_local deve ser o mesmo que enviou
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação a retomar
            cod_usuario: Código do usuário que está tentando retomar
        
        Returns:
            True se retomada com sucesso, False caso contrário
        """
        if tipo == 'MATERIA':
            tram = self.session.query(Tramitacao).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao,
                Tramitacao.ind_excluido == 0
            ).first()
        else:
            tram = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                TramitacaoAdministrativo.ind_excluido == 0
            ).first()
        
        if not tram:
            raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
        
        # Valida condições para retomar
        if not tram.dat_encaminha:
            raise ValueError("Tramitação não foi enviada, não pode ser retomada")
        
        if tram.dat_visualizacao:
            raise ValueError("Tramitação já foi visualizada pelo destino, não pode ser retomada")
        
        if tram.dat_recebimento:
            raise ValueError("Tramitação já foi recebida pelo destino, não pode ser retomada")
        
        # Valida que é o mesmo usuário que enviou
        if tram.cod_usuario_local != cod_usuario:
            raise ValueError("Apenas o usuário que enviou pode retomar a tramitação")
        
        # Retoma tramitação (volta para rascunho)
        tram.dat_encaminha = None  # Remove data de encaminhamento
        tram.ind_ult_tramitacao = 0  # Volta para rascunho
        
        # Se era última tramitação, precisa atualizar última tramitação anterior
        # IMPORTANTE: Só restauramos a tramitação anterior se ela pertencer ao mesmo usuário
        # que está retomando, para evitar que tramitações de outros usuários
        # apareçam na caixa de entrada de outros usuários da mesma unidade
        if tipo == 'MATERIA':
            cod_entidade = tram.cod_materia
            cod_usuario_local = tram.cod_usuario_local
            ultima_anterior = self.session.query(Tramitacao).filter(
                Tramitacao.cod_materia == cod_entidade,
                Tramitacao.cod_tramitacao != cod_tramitacao,
                Tramitacao.ind_ult_tramitacao == 0,
                Tramitacao.ind_excluido == 0,
                Tramitacao.cod_usuario_local == cod_usuario_local  # Só restaura se for do mesmo usuário
            ).order_by(Tramitacao.dat_tramitacao.desc()).first()
            
            if ultima_anterior:
                ultima_anterior.ind_ult_tramitacao = 1
        else:
            cod_entidade = tram.cod_documento
            cod_usuario_local = tram.cod_usuario_local
            ultima_anterior = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_documento == cod_entidade,
                TramitacaoAdministrativo.cod_tramitacao != cod_tramitacao,
                TramitacaoAdministrativo.ind_ult_tramitacao == 0,
                TramitacaoAdministrativo.ind_excluido == 0,
                TramitacaoAdministrativo.cod_usuario_local == cod_usuario_local  # Só restaura se for do mesmo usuário
            ).order_by(TramitacaoAdministrativo.dat_tramitacao.desc()).first()
            
            if ultima_anterior:
                ultima_anterior.ind_ult_tramitacao = 1
        
        # Marca sessão como alterada para o Zope transaction manager
        # O Zope cuidará de commit/abort automaticamente
        mark_changed(self.session)
        
        # Invalida cache de contadores automaticamente
        self._invalidate_cache_contadores_auto(tram.cod_usuario_local, tram.cod_unid_tram_dest)
        
        return True
    
    def registrar_visualizacao(
        self,
        tipo: TipoTramitacao,
        cod_tramitacao: int,
        cod_usuario: int
    ) -> bool:
        """
        Registra visualização de tramitação pelo destinatário.
        
        Condições:
        - dat_encaminha deve existir (foi enviada)
        - dat_visualizacao deve ser NULL (ainda não visualizada)
        - Usuário deve ser o destinatário (cod_usuario_dest OU unidade destino pertence ao usuário)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            cod_usuario: Código do usuário que está visualizando
        
        Returns:
            True se visualização registrada com sucesso, False caso contrário
        """
        if tipo == 'MATERIA':
            tram = self.session.query(Tramitacao).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao,
                Tramitacao.ind_excluido == 0
            ).first()
        else:
            tram = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                TramitacaoAdministrativo.ind_excluido == 0
            ).first()
        
        if not tram:
            raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
        
        # Valida que foi enviada
        if not tram.dat_encaminha:
            # Tramitação não foi enviada, não precisa registrar visualização
            logger.debug(f"Tramitação {cod_tramitacao} não foi enviada, não registra visualização")
            return False
        
        # Valida que ainda não foi visualizada
        if tram.dat_visualizacao:
            # Já foi visualizada, não precisa registrar novamente
            logger.debug(f"Tramitação {cod_tramitacao} já foi visualizada em {tram.dat_visualizacao}")
            return False
        
        # Valida que usuário é destinatário
        # Pode ser destinatário específico (cod_usuario_dest) OU parte da unidade de destino
        is_destinatario = False
        if tram.cod_usuario_dest:
            # Tramitação enviada para usuário específico
            is_destinatario = (tram.cod_usuario_dest == cod_usuario)
        else:
            # Tramitação enviada para unidade (qualquer usuário da unidade pode visualizar)
            # Verifica se usuário pertence à unidade de destino
            from openlegis.sagl.models.models import UsuarioUnidTram
            usuario_unidade = self.session.query(UsuarioUnidTram).filter(
                UsuarioUnidTram.cod_usuario == cod_usuario,
                UsuarioUnidTram.cod_unid_tramitacao == tram.cod_unid_tram_dest,
                UsuarioUnidTram.ind_excluido == 0
            ).first()
            is_destinatario = (usuario_unidade is not None)
        
        if not is_destinatario:
            # Usuário não é destinatário, não pode registrar visualização
            logger.debug(f"Usuário {cod_usuario} não é destinatário da tramitação {cod_tramitacao}")
            return False
        
        # Registra visualização
        tram.dat_visualizacao = datetime.now()
        tram.cod_usuario_visualiza = cod_usuario
        
        logger.info(f"Visualização registrada para tramitação {cod_tramitacao} pelo usuário {cod_usuario}")
        return True
    
    def _obter_ou_criar_tramitacao_rascunho(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        cod_tramitacao: Optional[int] = None
    ):
        """
        Obtém tramitação existente ou cria nova para rascunho.
        
        Returns:
            tuple: (tram, is_nova_tramitacao)
        """
        if tipo == 'MATERIA':
            Model = Tramitacao
            campo_entidade = 'cod_materia'
        else:
            Model = TramitacaoAdministrativo
            campo_entidade = 'cod_documento'
        
        is_nova_tramitacao = False
        
        if cod_tramitacao:
            # Expira qualquer cache da sessão para garantir que vemos dados commitados
            self.session.expire_all()
            
            tram = self.session.query(Model).filter(
                Model.cod_tramitacao == cod_tramitacao,
                Model.ind_excluido == 0
            ).first()
            
            if not tram:
                logger.warning(
                    f"TramitacaoService.salvar_rascunho - Tramitação {cod_tramitacao} não encontrada na sessão {id(self.session)}. "
                    f"Isso indica que o commit anterior ainda não persistiu os dados (Zope faz commit ao final da requisição). "
                    f"Tentando novamente após refresh da sessão."
                )
                self.session.expire_all()
                tram = self.session.query(Model).filter(
                    Model.cod_tramitacao == cod_tramitacao,
                    Model.ind_excluido == 0
                ).first()
                
                if not tram:
                    raise ValueError(
                        f"Tramitação {cod_tramitacao} não encontrada. "
                        f"A tramitação pode não ter sido commitada ainda (o Zope faz commit ao final da requisição). "
                        f"Aguarde alguns segundos e tente novamente, ou verifique se o código está correto."
                    )
        else:
            tram = Model()
            setattr(tram, campo_entidade, cod_entidade)
            tram.dat_tramitacao = datetime.now()
            tram.ind_ult_tramitacao = 0
            tram.ind_excluido = 0
            is_nova_tramitacao = True
        
        return tram, is_nova_tramitacao
    
    def _preencher_dados_tramitacao_rascunho(
        self,
        tram,
        tipo: TipoTramitacao,
        dados: Dict[str, Any]
    ):
        """Preenche dados da tramitação rascunho."""
        tram.cod_unid_tram_local = dados.get('cod_unid_tram_local')
        tram.cod_usuario_local = dados.get('cod_usuario_local')
        tram.dat_encaminha = None
        tram.cod_unid_tram_dest = dados.get('cod_unid_tram_dest')
        tram.cod_usuario_dest = dados.get('cod_usuario_dest')
        tram.cod_status = dados.get('cod_status')
        tram.txt_tramitacao = dados.get('txt_tramitacao', '')
        tram.dat_fim_prazo = dados.get('dat_fim_prazo')
        
        # Campos específicos de MATERIA
        if tipo == 'MATERIA':
            tram.ind_urgencia = dados.get('ind_urgencia', 0)
            tram.sgl_turno = dados.get('sgl_turno')
    
    def _atualizar_ultima_tramitacao_anterior_rascunho(
        self,
        tram,
        tipo: TipoTramitacao
    ):
        """Atualiza última tramitação anterior quando rascunho era última tramitação."""
        if tipo == 'MATERIA':
            cod_entidade = tram.cod_materia
            Model = Tramitacao
        else:
            cod_entidade = tram.cod_documento
            Model = TramitacaoAdministrativo
        
        cod_usuario_local = tram.cod_usuario_local
        campo_entidade = 'cod_materia' if tipo == 'MATERIA' else 'cod_documento'
        
        ultima_anterior = self.session.query(Model).filter(
            getattr(Model, campo_entidade) == cod_entidade,
            Model.cod_tramitacao != tram.cod_tramitacao,
            Model.ind_ult_tramitacao == 0,
            Model.ind_excluido == 0,
            Model.cod_usuario_local == cod_usuario_local
        ).order_by(Model.dat_tramitacao.desc()).first()
        
        if ultima_anterior:
            ultima_anterior.ind_ult_tramitacao = 1
    
    def _verificar_rascunho_existente(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        dados: Dict[str, Any]
    ):
        """Verifica se já existe rascunho para a entidade."""
        if tipo == 'MATERIA':
            Model = Tramitacao
            campo_entidade = 'cod_materia'
            nome_entidade = 'matéria'
        else:
            Model = TramitacaoAdministrativo
            campo_entidade = 'cod_documento'
            nome_entidade = 'documento'
        
        rascunho_existente = self.session.query(Model).filter(
            getattr(Model, campo_entidade) == cod_entidade,
            Model.ind_ult_tramitacao == 0,
            Model.dat_encaminha.is_(None),
            Model.ind_excluido == 0
        ).first()
        
        if rascunho_existente:
            if rascunho_existente.cod_usuario_local != dados.get('cod_usuario_local'):
                raise ValueError(
                    f"Já existe um rascunho para esta {nome_entidade} criado por outro usuário. "
                    f"É necessário aguardar que o rascunho existente seja enviado ou excluído antes de criar um novo."
                )
            else:
                raise ValueError(
                    f"Já existe um rascunho para esta {nome_entidade}. Use a opção de editar o rascunho existente."
                )
    
    def _processar_flush_nova_tramitacao(
        self,
        tram,
        tipo: TipoTramitacao
    ):
        """
        Processa flush() para nova tramitação com tratamento de transação.
        Retorna cod_tramitacao após flush bem-sucedido.
        """
        self.session.add(tram)
        mark_changed(self.session)
        
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.orm.session import SessionTransactionState
        
        try:
            self.session.flush()
            
            tx = self.session.get_transaction()
            tx_state = None
            if tx and hasattr(tx, '_state'):
                tx_state = tx._state
            
            if tx is None or tx_state == SessionTransactionState.CLOSED:
                problema = "sem transação (None)" if tx is None else "transação fechada (CLOSED)"
                logger.error(
                    f"TramitacaoService.salvar_rascunho - ❌ ERRO CRÍTICO: {problema.capitalize()} após flush() "
                    f"para sessão {id(self.session)}. Abrindo nova transação imediatamente para garantir persistência."
                )
                
                try:
                    tram = self.session.merge(tram)
                    from zope.sqlalchemy import register
                    register(self.session, keep_session=True)
                    mark_changed(self.session)
                    self.session.flush()
                    
                    tx_nova = self.session.get_transaction()
                    tx_nova_state = None
                    if tx_nova and hasattr(tx_nova, '_state'):
                        tx_nova_state = tx_nova._state
                    
                    if tx_nova_state != SessionTransactionState.CLOSED:
                        mark_changed(self.session)
                        logger.info(
                            f"TramitacaoService.salvar_rascunho - ✅ Nova transação aberta e registrada ({tipo}) - "
                            f"sessão {id(self.session)}, cod_tramitacao={tram.cod_tramitacao}"
                        )
                    else:
                        logger.error(
                            f"TramitacaoService.salvar_rascunho - ❌ ERRO CRÍTICO: Nova transação também fechada "
                            f"após flush(). Isso indica um problema sério com o gerenciamento de transações."
                        )
                except Exception as recovery_error:
                    logger.error(
                        f"TramitacaoService.salvar_rascunho - ❌ Erro ao tentar abrir nova transação: {recovery_error}",
                        exc_info=True
                    )
                    try:
                        from zope.sqlalchemy import register
                        register(self.session, keep_session=True)
                        mark_changed(self.session)
                    except Exception:
                        pass
            else:
                mark_changed(self.session)
                logger.debug(
                    f"TramitacaoService.salvar_rascunho - Transação aberta após flush() - "
                    f"sessão {id(self.session)}, tx_state={tx_state}"
                )
        except SQLAlchemyError as e:
            logger.error(
                f"TramitacaoService.salvar_rascunho - Erro durante flush() para sessão {id(self.session)}: {e}"
            )
            try:
                self.session.rollback()
                self.session.add(tram)
                mark_changed(self.session)
                self.session.flush()
                tx = self.session.get_transaction()
                if tx and hasattr(tx, '_state') and tx._state != SessionTransactionState.CLOSED:
                    mark_changed(self.session)
            except Exception as rollback_error:
                logger.error(
                    f"TramitacaoService.salvar_rascunho - Erro ao fazer rollback após flush() falhar: {rollback_error}"
                )
                raise
    
    def salvar_rascunho(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        dados: Dict[str, Any],
        cod_tramitacao: Optional[int] = None
    ) -> int:
        """
        Salva tramitação como rascunho (sem enviar)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_entidade: cod_materia ou cod_documento
            dados: Dicionário com dados da tramitação (pode estar incompleto)
            cod_tramitacao: Se fornecido, atualiza rascunho existente
        
        Returns:
            cod_tramitacao da tramitação salva
        """
        # Obtém ou cria tramitação
        tram, is_nova_tramitacao = self._obter_ou_criar_tramitacao_rascunho(tipo, cod_entidade, cod_tramitacao)
        
        # Preenche dados
        self._preencher_dados_tramitacao_rascunho(tram, tipo, dados)
        
        # Se era última tramitação, atualiza anterior
        if not is_nova_tramitacao and tram.ind_ult_tramitacao == 1:
            self._atualizar_ultima_tramitacao_anterior_rascunho(tram, tipo)
            tram.ind_ult_tramitacao = 0
        
        # Garante que rascunhos sempre tenham ind_ult_tramitacao = 0 e dat_encaminha = None
        tram.ind_ult_tramitacao = 0
        tram.dat_encaminha = None
        
        # Verifica se já existe rascunho (apenas para novas tramitações)
        if is_nova_tramitacao:
            self._verificar_rascunho_existente(tipo, cod_entidade, dados)
        
        # Processa flush se for nova tramitação
        if is_nova_tramitacao:
            self._processar_flush_nova_tramitacao(tram, tipo)
        else:
            mark_changed(self.session)
        
        # Invalida cache de contadores automaticamente
        self._invalidate_cache_contadores_auto(tram.cod_usuario_local, tram.cod_unid_tram_dest)
        
        logger.debug(
            f"TramitacaoService.salvar_rascunho - Rascunho ({tipo}) salvo - "
            f"sessão id: {id(self.session)}, cod_tramitacao: {tram.cod_tramitacao}"
        )
        return tram.cod_tramitacao
    
    def enviar_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        dados: Dict[str, Any],
        cod_tramitacao: Optional[int] = None
    ) -> int:
        """
        Salva e envia tramitação (pode ser rascunho existente ou nova)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_entidade: cod_materia ou cod_documento
            dados: Dicionário com dados completos da tramitação
            cod_tramitacao: Se fornecido, envia rascunho existente
        
        Returns:
            cod_tramitacao da tramitação enviada
        """
        # Validações completas antes de enviar
        if not dados.get('cod_unid_tram_local'):
            raise ValueError('Unidade de origem é obrigatória para enviar tramitação')
        
        if not dados.get('cod_usuario_local'):
            raise ValueError('Usuário de origem é obrigatório para enviar tramitação')
        
        if not dados.get('cod_unid_tram_dest'):
            raise ValueError('Unidade de destino é obrigatória para enviar tramitação')
        
        if not dados.get('cod_status'):
            raise ValueError('Status é obrigatório para enviar tramitação')
        
        # Valida data de fim de prazo (se fornecida, deve ser >= hoje)
        if dados.get('dat_fim_prazo'):
            dat_fim_prazo = dados['dat_fim_prazo']
            # Normaliza para date para comparação segura
            if isinstance(dat_fim_prazo, datetime):
                dat_fim_prazo_date = dat_fim_prazo.date()
            elif isinstance(dat_fim_prazo, date):
                dat_fim_prazo_date = dat_fim_prazo
            else:
                # Se for string ou outro tipo, tenta converter
                if isinstance(dat_fim_prazo, str):
                    try:
                        # Tenta parsear como datetime primeiro
                        dat_fim_prazo = datetime.strptime(dat_fim_prazo, '%Y-%m-%d %H:%M:%S')
                        dat_fim_prazo_date = dat_fim_prazo.date()
                    except ValueError:
                        try:
                            # Tenta parsear como date
                            dat_fim_prazo = datetime.strptime(dat_fim_prazo, '%Y-%m-%d')
                            dat_fim_prazo_date = dat_fim_prazo.date()
                        except ValueError:
                            raise ValueError('Formato de data inválido para dat_fim_prazo')
                else:
                    raise ValueError(f'Tipo inválido para dat_fim_prazo: {type(dat_fim_prazo)}')
            
            if dat_fim_prazo_date < date.today():
                raise ValueError('Data de fim de prazo não pode ser anterior à data atual')
        
        # Valida dados antes de enviar
        self._validar_dados_tramitacao(dados, enviar=True)
        
        # Usa salvar_tramitacao mas força dat_encaminha e ind_ult_tramitacao
        dados['dat_encaminha'] = datetime.now()  # Preenche data de encaminhamento
        dados['ind_ult_tramitacao'] = 1  # É última tramitação
        
        # Se é rascunho existente, obtém cod_entidade
        if cod_tramitacao:
            if tipo == 'MATERIA':
                tram = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao
                ).first()
                if not tram:
                    raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
                cod_entidade = tram.cod_materia
            else:
                tram = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao
                ).first()
                if not tram:
                    raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
                cod_entidade = tram.cod_documento
        
        # ANTES de salvar, atualiza a tramitação anterior que tinha ind_ult_tramitacao = 1
        # Isso garante que apenas uma tramitação tenha ind_ult_tramitacao = 1 por entidade
        if tipo == 'MATERIA':
            ultima_anterior = self.session.query(Tramitacao).filter(
                Tramitacao.cod_materia == cod_entidade,
                Tramitacao.ind_ult_tramitacao == 1,
                Tramitacao.ind_excluido == 0
            )
            # Se é rascunho existente sendo enviado, exclui a própria tramitação da busca
            if cod_tramitacao:
                ultima_anterior = ultima_anterior.filter(Tramitacao.cod_tramitacao != cod_tramitacao)
            ultima_anterior = ultima_anterior.first()
            
            if ultima_anterior:
                ultima_anterior.ind_ult_tramitacao = 0
                logger.info(f"TramitacaoService.enviar_tramitacao - Atualizada tramitação anterior (MATERIA) cod_tramitacao={ultima_anterior.cod_tramitacao} para ind_ult_tramitacao=0")
        else:  # DOCUMENTO
            ultima_anterior = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_documento == cod_entidade,
                TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                TramitacaoAdministrativo.ind_excluido == 0
            )
            # Se é rascunho existente sendo enviado, exclui a própria tramitação da busca
            if cod_tramitacao:
                ultima_anterior = ultima_anterior.filter(TramitacaoAdministrativo.cod_tramitacao != cod_tramitacao)
            ultima_anterior = ultima_anterior.first()
            
            if ultima_anterior:
                ultima_anterior.ind_ult_tramitacao = 0
                logger.info(f"TramitacaoService.enviar_tramitacao - Atualizada tramitação anterior (DOCUMENTO) cod_tramitacao={ultima_anterior.cod_tramitacao} para ind_ult_tramitacao=0")
        
        # Salva usando método existente
        cod_tramitacao_retorno = self.salvar_tramitacao(tipo, cod_entidade, dados, cod_tramitacao)
        
        # Atualiza indicadores de tramitação (fim/retorno) baseado no status
        try:
            if tipo == 'MATERIA':
                self._atualizar_indicadores_materia(cod_entidade, dados.get('cod_status'))
            else:
                self._atualizar_indicadores_documento(cod_entidade, dados.get('cod_status'))
        except Exception as e:
            logger.warning(f"TramitacaoService.enviar_tramitacao - Erro ao atualizar indicadores: {e}", exc_info=True)
            # Não bloqueia o envio se atualização de indicadores falhar
        
        return cod_tramitacao_retorno
    
    def verificar_rascunhos_ativos(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        cod_unid_tram_dest: Optional[int] = None
    ) -> bool:
        """
        Verifica se há rascunhos ativos que impedem a exibição de tramitações na caixa de entrada
        
        Quando há rascunhos de qualquer usuário para uma entidade (matéria/documento),
        as tramitações anteriores não devem aparecer na caixa de entrada de outros usuários
        da mesma unidade de destino.
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_entidade: cod_materia ou cod_documento
            cod_unid_tram_dest: Código da unidade de destino (opcional, para filtrar por unidade)
        
        Returns:
            True se há rascunhos ativos que impedem exibição, False caso contrário
        """
        if tipo == 'MATERIA':
            query = self.session.query(Tramitacao).filter(
                Tramitacao.cod_materia == cod_entidade,
                Tramitacao.ind_ult_tramitacao == 0,  # Rascunho
                Tramitacao.dat_encaminha.is_(None),  # Não foi enviado
                Tramitacao.ind_excluido == 0
            )
            if cod_unid_tram_dest:
                query = query.filter(Tramitacao.cod_unid_tram_dest == cod_unid_tram_dest)
        else:
            query = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_documento == cod_entidade,
                TramitacaoAdministrativo.ind_ult_tramitacao == 0,  # Rascunho
                TramitacaoAdministrativo.dat_encaminha.is_(None),  # Não foi enviado
                TramitacaoAdministrativo.ind_excluido == 0
            )
            if cod_unid_tram_dest:
                query = query.filter(TramitacaoAdministrativo.cod_unid_tram_dest == cod_unid_tram_dest)
        
        return query.first() is not None
    
    def filtrar_tramitacoes_caixa_entrada(
        self,
        tipo: TipoTramitacao,
        query,
        cod_unid_tram_dest: Optional[int] = None
    ):
        """
        Adiciona filtro à query para excluir tramitações quando há rascunhos ativos com data posterior
        
        Este método deve ser usado nas queries da caixa de entrada para garantir que
        tramitações não apareçam quando há rascunhos de outros usuários da mesma unidade
        criados APÓS a tramitação em questão.
        
        A lógica: Se há uma tramitação enviada (ind_ult_tramitacao = 1) mas existe um rascunho
        ativo (ind_ult_tramitacao = 0, dat_encaminha IS NULL) de qualquer usuário para a mesma
        entidade com dat_tramitacao posterior à dat_tramitacao da tramitação, essa tramitação
        não deve aparecer na caixa de entrada de outros usuários.
        
        Exemplo de uso:
            # Query base da caixa de entrada
            query = session.query(Tramitacao).filter(
                Tramitacao.ind_ult_tramitacao == 1,
                Tramitacao.cod_unid_tram_dest == cod_unidade,
                Tramitacao.ind_excluido == 0
            )
            
            # Aplica filtro para excluir quando há rascunhos posteriores
            service = TramitacaoService(session)
            query = service.filtrar_tramitacoes_caixa_entrada('MATERIA', query, cod_unidade)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            query: Query SQLAlchemy já iniciada (deve filtrar por ind_ult_tramitacao == 1)
            cod_unid_tram_dest: Código da unidade de destino (opcional, para otimizar a subquery)
        
        Returns:
            Query com filtros adicionais aplicados
        """
        from sqlalchemy import exists
        from sqlalchemy.orm import aliased
        
        if tipo == 'MATERIA':
            # ✅ CRÍTICO: Exclui tramitações que têm QUALQUER rascunho pendente
            # Não apenas rascunhos posteriores - QUALQUER rascunho deve excluir da caixa de entrada
            # Usa alias para evitar conflito de nomes na subquery correlacionada
            rascunho_alias = aliased(Tramitacao)
            
            rascunho_exists = exists().where(
                and_(
                    rascunho_alias.cod_materia == Tramitacao.cod_materia,  # Mesma matéria
                    rascunho_alias.ind_ult_tramitacao == 0,  # Rascunho = não é última tramitação
                    rascunho_alias.dat_encaminha.is_(None),  # Rascunho = não foi enviado
                    rascunho_alias.ind_excluido == 0
                    # ✅ REMOVIDO: rascunho_alias.dat_tramitacao > Tramitacao.dat_tramitacao
                    # Agora exclui QUALQUER rascunho, não apenas posteriores
                    # ✅ REMOVIDO: filtro por cod_unid_tram_dest - qualquer rascunho exclui
                )
            )
            
            query = query.filter(~rascunho_exists)
        else:
            # ✅ CRÍTICO: Exclui tramitações que têm QUALQUER rascunho pendente
            # Não apenas rascunhos posteriores - QUALQUER rascunho deve excluir da caixa de entrada
            # Mesma lógica para TramitacaoAdministrativo
            rascunho_alias = aliased(TramitacaoAdministrativo)
            
            rascunho_exists = exists().where(
                and_(
                    rascunho_alias.cod_documento == TramitacaoAdministrativo.cod_documento,  # Mesmo documento
                    rascunho_alias.ind_ult_tramitacao == 0,  # Rascunho = não é última tramitação
                    rascunho_alias.dat_encaminha.is_(None),  # Rascunho = não foi enviado
                    rascunho_alias.ind_excluido == 0
                    # ✅ REMOVIDO: rascunho_alias.dat_tramitacao > TramitacaoAdministrativo.dat_tramitacao
                    # Agora exclui QUALQUER rascunho, não apenas posteriores
                    # ✅ REMOVIDO: filtro por cod_unid_tram_dest - qualquer rascunho exclui
                )
            )
            
            query = query.filter(~rascunho_exists)
        
        return query
    
    def obter_link_pdf_despacho(self, cod_tramitacao: int, tipo: TipoTramitacao) -> Optional[str]:
        """
        Obtém o link do PDF do despacho de tramitação.
        
        Args:
            cod_tramitacao: Código da tramitação
            tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
            
        Returns:
            URL do PDF do despacho ou None se não houver
        """
        try:
            if tipo == 'MATERIA':
                tram = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao,
                    Tramitacao.ind_excluido == 0
                ).first()
            else:
                tram = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                    TramitacaoAdministrativo.ind_excluido == 0
                ).first()
            
            if not tram:
                logger.warning(f"TramitacaoService.obter_link_pdf_despacho - Tramitação {cod_tramitacao} não encontrada")
                return None
            
            # Verifica se há arquivo PDF associado
            # TODO: Implementar lógica específica para obter o link do PDF baseado na estrutura do sistema
            # Por enquanto, retorna None - precisa ser implementado baseado em como o sistema armazena PDFs
            
            # Exemplo de implementação (ajustar conforme necessário):
            # if hasattr(tram, 'nom_arquivo') and tram.nom_arquivo:
            #     # Construir URL do PDF baseado no contexto do Zope
            #     return f"/path/to/pdf/{tram.nom_arquivo}"
            
            logger.debug(f"TramitacaoService.obter_link_pdf_despacho - Tramitação {cod_tramitacao} não tem PDF associado")
            return None
            
        except Exception as e:
            logger.error(f"TramitacaoService.obter_link_pdf_despacho - Erro ao obter link do PDF: {e}", exc_info=True)
            return None
            
            if cod_tramitacao:
                # Expira qualquer cache da sessão para garantir que vemos dados commitados
                # Isso ajuda quando a tramitação foi criada em uma requisição anterior
                self.session.expire_all()
                
                tram = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao,
                    Tramitacao.ind_excluido == 0  # Apenas tramitações não excluídas
                ).first()
                if not tram:
                    # Se a tramitação não foi encontrada, pode ser que:
                    # 1. Ainda não foi commitada (se criada em outra requisição que ainda não terminou)
                    # 2. O código está incorreto
                    # 
                    # ❌ NÃO podemos criar uma nova tramitação - precisamos encontrar a existente
                    # O problema é que o Zope só faz commit ao final da requisição, então se o usuário
                    # tentar editar imediatamente após criar, o commit ainda não aconteceu.
                    #
                    # Solução: Aguardar um pouco e tentar novamente, ou verificar se a requisição anterior terminou
                    logger.warning(
                        f"TramitacaoService.salvar_rascunho - Tramitação {cod_tramitacao} não encontrada na sessão {id(self.session)}. "
                        f"Isso indica que o commit anterior ainda não persistiu os dados (Zope faz commit ao final da requisição). "
                        f"Tentando novamente após refresh da sessão."
                    )
                    # Força refresh da sessão para ver dados commitados
                    self.session.expire_all()
                    # Tenta buscar novamente após refresh
                    tram = self.session.query(Tramitacao).filter(
                        Tramitacao.cod_tramitacao == cod_tramitacao,
                        Tramitacao.ind_excluido == 0
                    ).first()
                    if not tram:
                        # Se ainda não encontrar, a tramitação pode não ter sido commitada ainda
                        # ou o código está incorreto. Levantamos erro explicativo.
                        raise ValueError(
                            f"Tramitação {cod_tramitacao} não encontrada. "
                            f"A tramitação pode não ter sido commitada ainda (o Zope faz commit ao final da requisição). "
                            f"Aguarde alguns segundos e tente novamente, ou verifique se o código está correto."
                        )
            else:
                tram = Tramitacao()
                tram.cod_materia = cod_entidade
                tram.dat_tramitacao = datetime.now()
                tram.ind_ult_tramitacao = 0  # Não é última tramitação (rascunho)
                tram.ind_excluido = 0
                is_nova_tramitacao = True  # Marca como nova para fazer flush()
            
            tram.cod_unid_tram_local = dados.get('cod_unid_tram_local')
            tram.cod_usuario_local = dados.get('cod_usuario_local')
            tram.dat_encaminha = None  # Não preenche (rascunho não foi enviado)
            tram.cod_unid_tram_dest = dados.get('cod_unid_tram_dest')
            tram.cod_usuario_dest = dados.get('cod_usuario_dest')
            tram.cod_status = dados.get('cod_status')
            tram.ind_urgencia = dados.get('ind_urgencia', 0)
            tram.sgl_turno = dados.get('sgl_turno')
            tram.txt_tramitacao = dados.get('txt_tramitacao', '')
            tram.dat_fim_prazo = dados.get('dat_fim_prazo')
            
            # ✅ Rascunhos sempre têm ind_ult_tramitacao = 0 para não aparecerem na caixa de entrada
            # Se era uma tramitação enviada (ind_ult_tramitacao == 1), agora vira rascunho
            # IMPORTANTE: Garantir que rascunhos sempre tenham ind_ult_tramitacao = 0 e dat_encaminha = None
            if not is_nova_tramitacao and tram.ind_ult_tramitacao == 1:
                # Era última tramitação - precisa atualizar última tramitação anterior
                # IMPORTANTE: Só restauramos a tramitação anterior se ela pertencer ao mesmo usuário
                # que está salvando o rascunho, para evitar que tramitações de outros usuários
                # apareçam na caixa de entrada de outros usuários da mesma unidade
                if tipo == 'MATERIA':
                    cod_entidade = tram.cod_materia
                    cod_usuario_local = tram.cod_usuario_local
                    ultima_anterior = self.session.query(Tramitacao).filter(
                        Tramitacao.cod_materia == cod_entidade,
                        Tramitacao.cod_tramitacao != tram.cod_tramitacao,
                        Tramitacao.ind_ult_tramitacao == 0,
                        Tramitacao.ind_excluido == 0,
                        Tramitacao.cod_usuario_local == cod_usuario_local  # Só restaura se for do mesmo usuário
                    ).order_by(Tramitacao.dat_tramitacao.desc()).first()
                    if ultima_anterior:
                        ultima_anterior.ind_ult_tramitacao = 1
                tram.ind_ult_tramitacao = 0  # Volta para rascunho
            
            # ✅ GARANTE que rascunhos sempre tenham ind_ult_tramitacao = 0 e dat_encaminha = None
            # Isso garante que rascunhos não apareçam na caixa de entrada
            tram.ind_ult_tramitacao = 0
            tram.dat_encaminha = None
            
            # ✅ GARANTE que não há dois rascunhos ao mesmo tempo para a mesma matéria
            # Se é nova tramitação, verifica se já existe um rascunho para a mesma matéria
            # O próprio usuário pode editar seu rascunho, mas outros usuários não podem criar novo rascunho
            if is_nova_tramitacao:
                rascunho_existente = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_materia == cod_entidade,
                    Tramitacao.ind_ult_tramitacao == 0,  # Rascunho
                    Tramitacao.dat_encaminha.is_(None),  # Não foi enviado
                    Tramitacao.ind_excluido == 0
                ).first()
                
                if rascunho_existente:
                    # Verifica se o rascunho existente pertence ao mesmo usuário
                    if rascunho_existente.cod_usuario_local != dados.get('cod_usuario_local'):
                        raise ValueError(
                            f"Já existe um rascunho para esta matéria criado por outro usuário. "
                            f"É necessário aguardar que o rascunho existente seja enviado ou excluído antes de criar um novo."
                        )
                    else:
                        # Se é o mesmo usuário, deve editar o rascunho existente ao invés de criar novo
                        raise ValueError(
                            f"Já existe um rascunho para esta matéria. Use a opção de editar o rascunho existente."
                        )
            
            # Se é nova tramitação, adiciona à sessão e faz flush() para gerar ID
            if is_nova_tramitacao:
                self.session.add(tram)
                
                # ✅ CRÍTICO: Marca sessão como alterada ANTES de flush()
                # Isso garante que a transação esteja corretamente registrada no Zope TM
                # antes de fazer flush(). Se mark_changed() for chamado depois, pode ser tarde demais
                # porque flush() pode fechar a transação se a sessão não estiver registrada corretamente.
                mark_changed(self.session)
                
                # Flush é necessário para gerar cod_tramitacao (PK auto-incremento)
                # ⚠️ Se flush() falhar (ex: constraint violation), SQLAlchemy fecha a transação
                from sqlalchemy.exc import SQLAlchemyError
                from sqlalchemy.orm.session import SessionTransactionState
                
                try:
                    self.session.flush()
                    
                    # ✅ CRÍTICO: Após flush(), verifica se a transação ainda está aberta
                    # Se estiver fechada ou ausente, isso indica um problema crítico - os dados não serão persistidos
                    tx = self.session.get_transaction()
                    tx_state = None
                    if tx and hasattr(tx, '_state'):
                        tx_state = tx._state
                    
                    # ❌ ERRO CRÍTICO: Se tx é None (sem transação) OU tx_state é CLOSED (transação fechada)
                    if tx is None or tx_state == SessionTransactionState.CLOSED:
                        # ❌ ERRO CRÍTICO: Transação fechada ou ausente após flush() - dados não serão persistidos
                        # Isso acontece quando flush() fecha a transação antes do commit do Zope
                        # SOLUÇÃO: Abrir nova transação imediatamente para garantir que os dados sejam persistidos
                        problema = "sem transação (None)" if tx is None else "transação fechada (CLOSED)"
                        logger.error(
                            f"TramitacaoService.salvar_rascunho - ❌ ERRO CRÍTICO: {problema.capitalize()} após flush() "
                            f"para sessão {id(self.session)}. Abrindo nova transação imediatamente para garantir persistência."
                        )
                        
                        try:
                            # ✅ CRÍTICO: Abre nova transação imediatamente
                            # Usa merge() para adicionar o objeto à nova transação (já tem ID após flush)
                            # O merge() garante que o objeto seja gerenciado pela nova transação
                            tram = self.session.merge(tram)
                            
                            # Registra a sessão no transaction manager do Zope (garante que nova transação seja capturada)
                            from zope.sqlalchemy import register
                            register(self.session, keep_session=True)
                            
                            # Marca sessão como alterada ANTES de flush() na nova transação
                            mark_changed(self.session)
                            
                            # Faz flush() na nova transação (autobegin criará transação automaticamente)
                            self.session.flush()
                            
                            # Verifica novamente se a nova transação está aberta
                            tx_nova = self.session.get_transaction()
                            tx_nova_state = None
                            if tx_nova and hasattr(tx_nova, '_state'):
                                tx_nova_state = tx_nova._state
                            
                            if tx_nova_state != SessionTransactionState.CLOSED:
                                # ✅ Nova transação está aberta - garante que mark_changed() seja chamado
                                mark_changed(self.session)
                                logger.info(
                                    f"TramitacaoService.salvar_rascunho - ✅ Nova transação aberta e registrada (MATERIA) - "
                                    f"sessão {id(self.session)}, cod_tramitacao={tram.cod_tramitacao}"
                                )
                            else:
                                # Mesmo após criar nova transação, ela está fechada - erro crítico
                                logger.error(
                                    f"TramitacaoService.salvar_rascunho - ❌ ERRO CRÍTICO: Nova transação também fechada "
                                    f"após flush(). Isso indica um problema sério com o gerenciamento de transações."
                                )
                        except Exception as recovery_error:
                            logger.error(
                                f"TramitacaoService.salvar_rascunho - ❌ Erro ao tentar abrir nova transação: {recovery_error}",
                                exc_info=True
                            )
                            # Tenta garantir que a sessão esteja registrada mesmo assim
                            try:
                                from zope.sqlalchemy import register
                                register(self.session, keep_session=True)
                                mark_changed(self.session)
                            except Exception:
                                pass
                    else:
                        # ✅ Transação ainda está aberta - garante que mark_changed() seja chamado
                        # para notificar o Zope TM que há mudanças pendentes
                        mark_changed(self.session)
                        logger.debug(
                            f"TramitacaoService.salvar_rascunho - Transação aberta após flush() - "
                            f"sessão {id(self.session)}, tx_state={tx_state}"
                        )
                except SQLAlchemyError as e:
                    # ERRO: flush() falhou - faz rollback e tenta novamente
                    logger.error(
                        f"TramitacaoService.salvar_rascunho - Erro durante flush() para sessão {id(self.session)}: {e}"
                    )
                    try:
                        self.session.rollback()
                        # Tenta novamente após rollback
                        self.session.add(tram)
                        mark_changed(self.session)
                        self.session.flush()
                        # Verifica novamente após re-try
                        tx = self.session.get_transaction()
                        if tx and hasattr(tx, '_state') and tx._state != SessionTransactionState.CLOSED:
                            mark_changed(self.session)
                    except Exception as rollback_error:
                        logger.error(
                            f"TramitacaoService.salvar_rascunho - Erro ao fazer rollback após flush() falhar: {rollback_error}"
                        )
                        raise
            else:
                # Para tramitações existentes, apenas marca como alterada
                mark_changed(self.session)
            
            logger.debug(f"TramitacaoService.salvar_rascunho - Rascunho (MATERIA) salvo - sessão id: {id(self.session)}, cod_tramitacao: {tram.cod_tramitacao}")
            return tram.cod_tramitacao
        else:
            is_nova_tramitacao = False  # Flag para indicar se é nova tramitação
            
            if cod_tramitacao:
                # Expira qualquer cache da sessão para garantir que vemos dados commitados
                # Isso ajuda quando a tramitação foi criada em uma requisição anterior
                self.session.expire_all()
                
                tram = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                    TramitacaoAdministrativo.ind_excluido == 0  # Apenas tramitações não excluídas
                ).first()
                if not tram:
                    # Se a tramitação não foi encontrada, pode ser que:
                    # 1. Ainda não foi commitada (se criada em outra requisição que ainda não terminou)
                    # 2. O código está incorreto
                    # 
                    # ❌ NÃO podemos criar uma nova tramitação - precisamos encontrar a existente
                    # O problema é que o Zope só faz commit ao final da requisição, então se o usuário
                    # tentar editar imediatamente após criar, o commit ainda não aconteceu.
                    #
                    # Solução: Aguardar um pouco e tentar novamente, ou verificar se a requisição anterior terminou
                    logger.warning(
                        f"TramitacaoService.salvar_rascunho - Tramitação {cod_tramitacao} não encontrada na sessão {id(self.session)}. "
                        f"Isso indica que o commit anterior ainda não persistiu os dados (Zope faz commit ao final da requisição). "
                        f"Tentando novamente após refresh da sessão."
                    )
                    # Força refresh da sessão para ver dados commitados
                    self.session.expire_all()
                    # Tenta buscar novamente após refresh
                    tram = self.session.query(TramitacaoAdministrativo).filter(
                        TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                        TramitacaoAdministrativo.ind_excluido == 0
                    ).first()
                    if not tram:
                        # Se ainda não encontrar, a tramitação pode não ter sido commitada ainda
                        # ou o código está incorreto. Levantamos erro explicativo.
                        raise ValueError(
                            f"Tramitação {cod_tramitacao} não encontrada. "
                            f"A tramitação pode não ter sido commitada ainda (o Zope faz commit ao final da requisição). "
                            f"Aguarde alguns segundos e tente novamente, ou verifique se o código está correto."
                        )
            else:
                tram = TramitacaoAdministrativo()
                tram.cod_documento = cod_entidade
                tram.dat_tramitacao = datetime.now()
                tram.ind_ult_tramitacao = 0  # Não é última tramitação (rascunho)
                tram.ind_excluido = 0
                is_nova_tramitacao = True  # Marca como nova para fazer flush()
            
            tram.cod_unid_tram_local = dados.get('cod_unid_tram_local')
            tram.cod_usuario_local = dados.get('cod_usuario_local')
            tram.dat_encaminha = None  # Não preenche (rascunho não foi enviado)
            tram.cod_unid_tram_dest = dados.get('cod_unid_tram_dest')
            tram.cod_usuario_dest = dados.get('cod_usuario_dest')
            tram.cod_status = dados.get('cod_status')
            tram.txt_tramitacao = dados.get('txt_tramitacao', '')
            tram.dat_fim_prazo = dados.get('dat_fim_prazo')
            
            # ✅ Rascunhos sempre têm ind_ult_tramitacao = 0 para não aparecerem na caixa de entrada
            # Se era uma tramitação enviada (ind_ult_tramitacao == 1), agora vira rascunho
            # IMPORTANTE: Garantir que rascunhos sempre tenham ind_ult_tramitacao = 0 e dat_encaminha = None
            if not is_nova_tramitacao and tram.ind_ult_tramitacao == 1:
                # Era última tramitação - precisa atualizar última tramitação anterior
                # IMPORTANTE: Só restauramos a tramitação anterior se ela pertencer ao mesmo usuário
                # que está salvando o rascunho, para evitar que tramitações de outros usuários
                # apareçam na caixa de entrada de outros usuários da mesma unidade
                cod_entidade = tram.cod_documento
                cod_usuario_local = tram.cod_usuario_local
                ultima_anterior = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_documento == cod_entidade,
                    TramitacaoAdministrativo.cod_tramitacao != tram.cod_tramitacao,
                    TramitacaoAdministrativo.ind_ult_tramitacao == 0,
                    TramitacaoAdministrativo.ind_excluido == 0,
                    TramitacaoAdministrativo.cod_usuario_local == cod_usuario_local  # Só restaura se for do mesmo usuário
                ).order_by(TramitacaoAdministrativo.dat_tramitacao.desc()).first()
                if ultima_anterior:
                    ultima_anterior.ind_ult_tramitacao = 1
                tram.ind_ult_tramitacao = 0  # Volta para rascunho
            
            # ✅ GARANTE que rascunhos sempre tenham ind_ult_tramitacao = 0 e dat_encaminha = None
            # Isso garante que rascunhos não apareçam na caixa de entrada
            tram.ind_ult_tramitacao = 0
            tram.dat_encaminha = None
            
            # ✅ GARANTE que não há dois rascunhos ao mesmo tempo para o mesmo documento
            # Se é nova tramitação, verifica se já existe um rascunho para o mesmo documento
            # O próprio usuário pode editar seu rascunho, mas outros usuários não podem criar novo rascunho
            if is_nova_tramitacao:
                rascunho_existente = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_documento == cod_entidade,
                    TramitacaoAdministrativo.ind_ult_tramitacao == 0,  # Rascunho
                    TramitacaoAdministrativo.dat_encaminha.is_(None),  # Não foi enviado
                    TramitacaoAdministrativo.ind_excluido == 0
                ).first()
                
                if rascunho_existente:
                    # Verifica se o rascunho existente pertence ao mesmo usuário
                    if rascunho_existente.cod_usuario_local != dados.get('cod_usuario_local'):
                        raise ValueError(
                            f"Já existe um rascunho para este documento criado por outro usuário. "
                            f"É necessário aguardar que o rascunho existente seja enviado ou excluído antes de criar um novo."
                        )
                    else:
                        # Se é o mesmo usuário, deve editar o rascunho existente ao invés de criar novo
                        raise ValueError(
                            f"Já existe um rascunho para este documento. Use a opção de editar o rascunho existente."
                        )
            
            # Se é nova tramitação, adiciona à sessão e faz flush() para gerar ID
            if is_nova_tramitacao:
                self.session.add(tram)
                
                # ✅ CRÍTICO: Marca sessão como alterada ANTES de flush()
                # Isso garante que a transação esteja corretamente registrada no Zope TM
                # antes de fazer flush(). Se mark_changed() for chamado depois, pode ser tarde demais
                # porque flush() pode fechar a transação se a sessão não estiver registrada corretamente.
                mark_changed(self.session)
                
                # Flush é necessário para gerar cod_tramitacao (PK auto-incremento)
                # ⚠️ Se flush() falhar (ex: constraint violation), SQLAlchemy fecha a transação
                from sqlalchemy.exc import SQLAlchemyError
                from sqlalchemy.orm.session import SessionTransactionState
                
                try:
                    self.session.flush()
                    
                    # ✅ CRÍTICO: Após flush(), verifica se a transação ainda está aberta
                    # Se estiver fechada ou ausente, isso indica um problema crítico - os dados não serão persistidos
                    tx = self.session.get_transaction()
                    tx_state = None
                    if tx and hasattr(tx, '_state'):
                        tx_state = tx._state
                    
                    # ❌ ERRO CRÍTICO: Se tx é None (sem transação) OU tx_state é CLOSED (transação fechada)
                    if tx is None or tx_state == SessionTransactionState.CLOSED:
                        # ❌ ERRO CRÍTICO: Transação fechada ou ausente após flush() - dados não serão persistidos
                        # Isso acontece quando flush() fecha a transação antes do commit do Zope
                        # SOLUÇÃO: Abrir nova transação imediatamente para garantir que os dados sejam persistidos
                        problema = "sem transação (None)" if tx is None else "transação fechada (CLOSED)"
                        logger.error(
                            f"TramitacaoService.salvar_rascunho - ❌ ERRO CRÍTICO: {problema.capitalize()} após flush() "
                            f"para sessão {id(self.session)}. Abrindo nova transação imediatamente para garantir persistência."
                        )
                        
                        try:
                            # ✅ CRÍTICO: Abre nova transação imediatamente
                            # Usa merge() para adicionar o objeto à nova transação (já tem ID após flush)
                            # O merge() garante que o objeto seja gerenciado pela nova transação
                            tram = self.session.merge(tram)
                            
                            # Registra a sessão no transaction manager do Zope (garante que nova transação seja capturada)
                            from zope.sqlalchemy import register
                            register(self.session, keep_session=True)
                            
                            # Marca sessão como alterada ANTES de flush() na nova transação
                            mark_changed(self.session)
                            
                            # Faz flush() na nova transação (autobegin criará transação automaticamente)
                            self.session.flush()
                            
                            # Verifica novamente se a nova transação está aberta
                            tx_nova = self.session.get_transaction()
                            tx_nova_state = None
                            if tx_nova and hasattr(tx_nova, '_state'):
                                tx_nova_state = tx_nova._state
                            
                            if tx_nova_state != SessionTransactionState.CLOSED:
                                # ✅ Nova transação está aberta - garante que mark_changed() seja chamado
                                mark_changed(self.session)
                                logger.info(
                                    f"TramitacaoService.salvar_rascunho - ✅ Nova transação aberta e registrada (DOCUMENTO) - "
                                    f"sessão {id(self.session)}, cod_tramitacao={tram.cod_tramitacao}"
                                )
                            else:
                                # Mesmo após criar nova transação, ela está fechada - erro crítico
                                logger.error(
                                    f"TramitacaoService.salvar_rascunho - ❌ ERRO CRÍTICO: Nova transação também fechada "
                                    f"após flush(). Isso indica um problema sério com o gerenciamento de transações."
                                )
                        except Exception as recovery_error:
                            logger.error(
                                f"TramitacaoService.salvar_rascunho - ❌ Erro ao tentar abrir nova transação: {recovery_error}",
                                exc_info=True
                            )
                            # Tenta garantir que a sessão esteja registrada mesmo assim
                            try:
                                from zope.sqlalchemy import register
                                register(self.session, keep_session=True)
                                mark_changed(self.session)
                            except Exception:
                                pass
                    else:
                        # ✅ Transação ainda está aberta - garante que mark_changed() seja chamado
                        # para notificar o Zope TM que há mudanças pendentes
                        mark_changed(self.session)
                        logger.debug(
                            f"TramitacaoService.salvar_rascunho - Transação aberta após flush() - "
                            f"sessão {id(self.session)}, tx_state={tx_state}"
                        )
                except SQLAlchemyError as e:
                    # ERRO: flush() falhou - faz rollback e tenta novamente
                    logger.error(
                        f"TramitacaoService.salvar_rascunho - Erro durante flush() para sessão {id(self.session)}: {e}"
                    )
                    try:
                        self.session.rollback()
                        # Tenta novamente após rollback
                        self.session.add(tram)
                        mark_changed(self.session)
                        self.session.flush()
                        # Verifica novamente após re-try
                        tx = self.session.get_transaction()
                        if tx and hasattr(tx, '_state') and tx._state != SessionTransactionState.CLOSED:
                            mark_changed(self.session)
                    except Exception as rollback_error:
                        logger.error(
                            f"TramitacaoService.salvar_rascunho - Erro ao fazer rollback após flush() falhar: {rollback_error}"
                        )
                        raise
            else:
                # Para tramitações existentes, apenas marca como alterada
                mark_changed(self.session)
            
            logger.debug(f"TramitacaoService.salvar_rascunho - Rascunho (DOCUMENTO) salvo - sessão id: {id(self.session)}, cod_tramitacao: {tram.cod_tramitacao}")
            return tram.cod_tramitacao
    
    def enviar_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        dados: Dict[str, Any],
        cod_tramitacao: Optional[int] = None
    ) -> int:
        """
        Salva e envia tramitação (pode ser rascunho existente ou nova)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_entidade: cod_materia ou cod_documento
            dados: Dicionário com dados completos da tramitação
            cod_tramitacao: Se fornecido, envia rascunho existente
        
        Returns:
            cod_tramitacao da tramitação enviada
        """
        # Validações completas antes de enviar
        if not dados.get('cod_unid_tram_local'):
            raise ValueError('Unidade de origem é obrigatória para enviar tramitação')
        
        if not dados.get('cod_usuario_local'):
            raise ValueError('Usuário de origem é obrigatório para enviar tramitação')
        
        if not dados.get('cod_unid_tram_dest'):
            raise ValueError('Unidade de destino é obrigatória para enviar tramitação')
        
        if not dados.get('cod_status'):
            raise ValueError('Status é obrigatório para enviar tramitação')
        
        # Valida data de fim de prazo (se fornecida, deve ser >= hoje)
        if dados.get('dat_fim_prazo'):
            dat_fim_prazo = dados['dat_fim_prazo']
            # Normaliza para date para comparação segura
            if isinstance(dat_fim_prazo, datetime):
                dat_fim_prazo_date = dat_fim_prazo.date()
            elif isinstance(dat_fim_prazo, date):
                dat_fim_prazo_date = dat_fim_prazo
            else:
                # Se for string ou outro tipo, tenta converter
                if isinstance(dat_fim_prazo, str):
                    try:
                        # Tenta parsear como datetime primeiro
                        dat_fim_prazo = datetime.strptime(dat_fim_prazo, '%Y-%m-%d %H:%M:%S')
                        dat_fim_prazo_date = dat_fim_prazo.date()
                    except ValueError:
                        try:
                            # Tenta parsear como date
                            dat_fim_prazo = datetime.strptime(dat_fim_prazo, '%Y-%m-%d')
                            dat_fim_prazo_date = dat_fim_prazo.date()
                        except ValueError:
                            raise ValueError('Formato de data inválido para dat_fim_prazo')
                else:
                    raise ValueError(f'Tipo inválido para dat_fim_prazo: {type(dat_fim_prazo)}')
            
            if dat_fim_prazo_date < date.today():
                raise ValueError('Data de fim de prazo não pode ser anterior à data atual')
        
        # Valida dados antes de enviar
        self._validar_dados_tramitacao(dados, enviar=True)
        
        # Usa salvar_tramitacao mas força dat_encaminha e ind_ult_tramitacao
        dados['dat_encaminha'] = datetime.now()  # Preenche data de encaminhamento
        dados['ind_ult_tramitacao'] = 1  # É última tramitação
        
        # Se é rascunho existente, obtém cod_entidade
        if cod_tramitacao:
            if tipo == 'MATERIA':
                tram = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao
                ).first()
                if not tram:
                    raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
                cod_entidade = tram.cod_materia
            else:
                tram = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao
                ).first()
                if not tram:
                    raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
                cod_entidade = tram.cod_documento
        
        # ANTES de salvar, atualiza a tramitação anterior que tinha ind_ult_tramitacao = 1
        # Isso garante que apenas uma tramitação tenha ind_ult_tramitacao = 1 por entidade
        if tipo == 'MATERIA':
            ultima_anterior = self.session.query(Tramitacao).filter(
                Tramitacao.cod_materia == cod_entidade,
                Tramitacao.ind_ult_tramitacao == 1,
                Tramitacao.ind_excluido == 0
            )
            # Se é rascunho existente sendo enviado, exclui a própria tramitação da busca
            if cod_tramitacao:
                ultima_anterior = ultima_anterior.filter(Tramitacao.cod_tramitacao != cod_tramitacao)
            ultima_anterior = ultima_anterior.first()
            
            if ultima_anterior:
                ultima_anterior.ind_ult_tramitacao = 0
                logger.info(f"TramitacaoService.enviar_tramitacao - Atualizada tramitação anterior (MATERIA) cod_tramitacao={ultima_anterior.cod_tramitacao} para ind_ult_tramitacao=0")
        else:  # DOCUMENTO
            ultima_anterior = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_documento == cod_entidade,
                TramitacaoAdministrativo.ind_ult_tramitacao == 1,
                TramitacaoAdministrativo.ind_excluido == 0
            )
            # Se é rascunho existente sendo enviado, exclui a própria tramitação da busca
            if cod_tramitacao:
                ultima_anterior = ultima_anterior.filter(TramitacaoAdministrativo.cod_tramitacao != cod_tramitacao)
            ultima_anterior = ultima_anterior.first()
            
            if ultima_anterior:
                ultima_anterior.ind_ult_tramitacao = 0
                logger.info(f"TramitacaoService.enviar_tramitacao - Atualizada tramitação anterior (DOCUMENTO) cod_tramitacao={ultima_anterior.cod_tramitacao} para ind_ult_tramitacao=0")
        
        # Salva usando método existente
        cod_tramitacao_retorno = self.salvar_tramitacao(tipo, cod_entidade, dados, cod_tramitacao)
        
        # Atualiza indicadores de tramitação (fim/retorno) baseado no status
        try:
            if tipo == 'MATERIA':
                self._atualizar_indicadores_materia(cod_entidade, dados.get('cod_status'))
            else:
                self._atualizar_indicadores_documento(cod_entidade, dados.get('cod_status'))
        except Exception as e:
            logger.warning(f"TramitacaoService.enviar_tramitacao - Erro ao atualizar indicadores: {e}", exc_info=True)
            # Não bloqueia o envio se atualização de indicadores falhar
        
        return cod_tramitacao_retorno
    
    def verificar_rascunhos_ativos(
        self,
        tipo: TipoTramitacao,
        cod_entidade: int,
        cod_unid_tram_dest: Optional[int] = None
    ) -> bool:
        """
        Verifica se há rascunhos ativos que impedem a exibição de tramitações na caixa de entrada
        
        Quando há rascunhos de qualquer usuário para uma entidade (matéria/documento),
        as tramitações anteriores não devem aparecer na caixa de entrada de outros usuários
        da mesma unidade de destino.
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_entidade: cod_materia ou cod_documento
            cod_unid_tram_dest: Código da unidade de destino (opcional, para filtrar por unidade)
        
        Returns:
            True se há rascunhos ativos que impedem exibição, False caso contrário
        """
        if tipo == 'MATERIA':
            query = self.session.query(Tramitacao).filter(
                Tramitacao.cod_materia == cod_entidade,
                Tramitacao.ind_ult_tramitacao == 0,  # Rascunho
                Tramitacao.dat_encaminha.is_(None),  # Não foi enviado
                Tramitacao.ind_excluido == 0
            )
            if cod_unid_tram_dest:
                query = query.filter(Tramitacao.cod_unid_tram_dest == cod_unid_tram_dest)
        else:
            query = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_documento == cod_entidade,
                TramitacaoAdministrativo.ind_ult_tramitacao == 0,  # Rascunho
                TramitacaoAdministrativo.dat_encaminha.is_(None),  # Não foi enviado
                TramitacaoAdministrativo.ind_excluido == 0
            )
            if cod_unid_tram_dest:
                query = query.filter(TramitacaoAdministrativo.cod_unid_tram_dest == cod_unid_tram_dest)
        
        return query.first() is not None
    
    def filtrar_tramitacoes_caixa_entrada(
        self,
        tipo: TipoTramitacao,
        query,
        cod_unid_tram_dest: Optional[int] = None
    ):
        """
        Adiciona filtro à query para excluir tramitações quando há rascunhos ativos com data posterior
        
        Este método deve ser usado nas queries da caixa de entrada para garantir que
        tramitações não apareçam quando há rascunhos de outros usuários da mesma unidade
        criados APÓS a tramitação em questão.
        
        A lógica: Se há uma tramitação enviada (ind_ult_tramitacao = 1) mas existe um rascunho
        ativo (ind_ult_tramitacao = 0, dat_encaminha IS NULL) de qualquer usuário para a mesma
        entidade com dat_tramitacao posterior à dat_tramitacao da tramitação, essa tramitação
        não deve aparecer na caixa de entrada de outros usuários.
        
        Exemplo de uso:
            # Query base da caixa de entrada
            query = session.query(Tramitacao).filter(
                Tramitacao.ind_ult_tramitacao == 1,
                Tramitacao.cod_unid_tram_dest == cod_unidade,
                Tramitacao.ind_excluido == 0
            )
            
            # Aplica filtro para excluir quando há rascunhos posteriores
            service = TramitacaoService(session)
            query = service.filtrar_tramitacoes_caixa_entrada('MATERIA', query, cod_unidade)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            query: Query SQLAlchemy já iniciada (deve filtrar por ind_ult_tramitacao == 1)
            cod_unid_tram_dest: Código da unidade de destino (opcional, para otimizar a subquery)
        
        Returns:
            Query com filtros adicionais aplicados
        """
        from sqlalchemy import exists
        from sqlalchemy.orm import aliased
        
        if tipo == 'MATERIA':
            # ✅ CRÍTICO: Exclui tramitações que têm QUALQUER rascunho pendente
            # Não apenas rascunhos posteriores - QUALQUER rascunho deve excluir da caixa de entrada
            # Usa alias para evitar conflito de nomes na subquery correlacionada
            rascunho_alias = aliased(Tramitacao)
            
            rascunho_exists = exists().where(
                and_(
                    rascunho_alias.cod_materia == Tramitacao.cod_materia,  # Mesma matéria
                    rascunho_alias.ind_ult_tramitacao == 0,  # Rascunho = não é última tramitação
                    rascunho_alias.dat_encaminha.is_(None),  # Rascunho = não foi enviado
                    rascunho_alias.ind_excluido == 0
                    # ✅ REMOVIDO: rascunho_alias.dat_tramitacao > Tramitacao.dat_tramitacao
                    # Agora exclui QUALQUER rascunho, não apenas posteriores
                    # ✅ REMOVIDO: filtro por cod_unid_tram_dest - qualquer rascunho exclui
                )
            )
            
            query = query.filter(~rascunho_exists)
        else:
            # ✅ CRÍTICO: Exclui tramitações que têm QUALQUER rascunho pendente
            # Não apenas rascunhos posteriores - QUALQUER rascunho deve excluir da caixa de entrada
            # Mesma lógica para TramitacaoAdministrativo
            rascunho_alias = aliased(TramitacaoAdministrativo)
            
            rascunho_exists = exists().where(
                and_(
                    rascunho_alias.cod_documento == TramitacaoAdministrativo.cod_documento,  # Mesmo documento
                    rascunho_alias.ind_ult_tramitacao == 0,  # Rascunho = não é última tramitação
                    rascunho_alias.dat_encaminha.is_(None),  # Rascunho = não foi enviado
                    rascunho_alias.ind_excluido == 0
                    # ✅ REMOVIDO: rascunho_alias.dat_tramitacao > TramitacaoAdministrativo.dat_tramitacao
                    # Agora exclui QUALQUER rascunho, não apenas posteriores
                    # ✅ REMOVIDO: filtro por cod_unid_tram_dest - qualquer rascunho exclui
                )
            )
            
            query = query.filter(~rascunho_exists)
        
        return query
    
    def obter_link_pdf_despacho(self, cod_tramitacao: int, tipo: TipoTramitacao) -> Optional[str]:
        """
        Obtém o link do PDF do despacho de tramitação.
        
        Args:
            cod_tramitacao: Código da tramitação
            tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
            
        Returns:
            URL do PDF do despacho ou None se não houver
        """
        try:
            if tipo == 'MATERIA':
                tram = self.session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao,
                    Tramitacao.ind_excluido == 0
                ).first()
            else:
                tram = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                    TramitacaoAdministrativo.ind_excluido == 0
                ).first()
            
            if not tram:
                logger.warning(f"TramitacaoService.obter_link_pdf_despacho - Tramitação {cod_tramitacao} não encontrada")
                return None
            
            # Verifica se há arquivo PDF associado
            # TODO: Implementar lógica específica para obter o link do PDF baseado na estrutura do sistema
            # Por enquanto, retorna None - precisa ser implementado baseado em como o sistema armazena PDFs
            
            # Exemplo de implementação (ajustar conforme necessário):
            # if hasattr(tram, 'nom_arquivo') and tram.nom_arquivo:
            #     # Construir URL do PDF baseado no contexto do Zope
            #     return f"/path/to/pdf/{tram.nom_arquivo}"
            
            logger.debug(f"TramitacaoService.obter_link_pdf_despacho - Tramitação {cod_tramitacao} não tem PDF associado")
            return None
            
        except Exception as e:
            logger.error(f"TramitacaoService.obter_link_pdf_despacho - Erro ao obter link do PDF: {e}", exc_info=True)
            return None
    def gerar_pdf_despacho(
        self,
        tipo: TipoTramitacao,
        cod_tramitacao: int,
        contexto_zope=None
    ):
        """
        Gera PDF do despacho de tramitação (facade para TramitacaoPDFGenerator)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            contexto_zope: Contexto Zope para salvar arquivo
            
        Returns:
            BytesIO com conteúdo do PDF gerado
        """
        from .pdf.generator import TramitacaoPDFGenerator
        
        generator = TramitacaoPDFGenerator(self.session, contexto_zope)
        return generator.gerar_pdf(tipo, cod_tramitacao, contexto_zope)
    
    def anexar_pdf_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_tramitacao: int,
        arquivo_pdf,
        nome_arquivo: str,
        contexto_zope=None
    ) -> bool:
        """
        Anexa PDF e junta ao PDF principal (facade para TramitacaoAnexoService)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            arquivo_pdf: BytesIO ou objeto file-like com conteúdo do PDF
            nome_arquivo: Nome original do arquivo
            contexto_zope: Contexto Zope para salvar arquivo
            
        Returns:
            True se sucesso, False caso contrário
        """
        from .anexos.service import TramitacaoAnexoService
        
        service = TramitacaoAnexoService(self.session, contexto_zope)
        return service.anexar_e_juntar_pdf(tipo, cod_tramitacao, arquivo_pdf, nome_arquivo)
    
    def obter_pdf_tramitacao(
        self,
        tipo: TipoTramitacao,
        cod_tramitacao: int,
        contexto_zope=None
    ):
        """
        Obtém PDF da tramitação (com anexos já juntados)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            contexto_zope: Contexto Zope para acessar repositório
            
        Returns:
            BytesIO com conteúdo do PDF ou None se não encontrado
        """
        from .anexos.service import TramitacaoAnexoService
        
        service = TramitacaoAnexoService(self.session, contexto_zope)
        return service.obter_pdf_tramitacao(tipo, cod_tramitacao)
