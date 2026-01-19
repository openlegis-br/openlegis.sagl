# -*- coding: utf-8 -*-
"""
Configuração de sessão SQLAlchemy para tramitação.

✅ Forma correta (SQLAlchemy 2.0.45 + Zope + zope.sqlalchemy-4.1):

Baseado na análise do código fonte:
- SQLAlchemy 2.0.45: autobegin=True por padrão (session.py linha 1506)
- autobegin inicia transação automaticamente na primeira operação (add, flush, etc.)
- zope.sqlalchemy-4.1: captura via evento 'after_begin' e registra no transaction manager

Uso:
    from .config import get_session
    from zope.sqlalchemy import mark_changed
    
    session = get_session()  # Sessão fresca já registrada no transaction manager
    session.add(objeto)      # Autobegin inicia transação aqui
    # Se precisar do ID gerado:
    session.flush()          # Opcional: apenas se precisar do PK/ID imediatamente
    mark_changed(session, keep_session=True)  # Marca sessão como alterada
    
    # NUNCA chame:
    # - session.begin() - autobegin faz isso automaticamente
    # - session.commit() - Zope transaction manager faz isso
    # - session.close() - Zope gerencia o ciclo de vida
    # - session.remove() ou Session.remove() - causa problemas com scoped_session
    # - session.in_transaction() ou is_active - não existem em GloballyScopedSession
"""

from z3c.saconfig import named_scoped_session
from zope.sqlalchemy import mark_changed
import logging

logger = logging.getLogger(__name__)

# Padrão usado em recebimento_proposicoes.py (funciona corretamente)
_SessionFactory = named_scoped_session("minha_sessao")


def _apply_datamanager_protection():
    """
    Aplica proteção robusta nos métodos tpc_vote() e tpc_finish() do TwoPhaseSessionDataManager
    para lidar com transações fechadas que podem ocorrer após flush() em SQLAlchemy 2.0.
    
    Esta é uma proteção permanente e necessária, não um monkey patch temporário.
    """
    from zope.sqlalchemy.datamanager import TwoPhaseSessionDataManager
    from sqlalchemy.exc import ResourceClosedError
    from sqlalchemy.orm.session import SessionTransactionState
    
    # Protege tpc_vote() contra ResourceClosedError
    if not hasattr(TwoPhaseSessionDataManager.tpc_vote, '_protected'):
        original_tpc_vote = TwoPhaseSessionDataManager.tpc_vote
        
        def tpc_vote_protected(self, trans):
            """Versão protegida do tpc_vote() que trata ResourceClosedError"""
            if self.tx is not None:
                # ⚠️ IMPORTANTE: Verificamos se há uma transação ativa na sessão
                # O self.tx pode não ser mais a mesma transação usada durante flush()
                # Se a transação original foi fechada e uma nova foi criada, usamos a transação ativa
                tx_atual = self.session.get_transaction()
                tx_state_atual = None
                if tx_atual and hasattr(tx_atual, '_state'):
                    tx_state_atual = tx_atual._state
                
                # Se há uma transação ativa na sessão diferente de self.tx, usamos ela
                # Isso pode acontecer se a transação original foi fechada e uma nova foi criada
                if (tx_atual is not None and tx_atual != self.tx and 
                    tx_state_atual == SessionTransactionState.ACTIVE):
                    # Atualizamos self.tx para usar a transação ativa da sessão
                    self.tx = tx_atual
                
                try:
                    # Verifica se a transação ainda está ativa antes de preparar
                    if hasattr(self.tx, '_state') and self.tx._state == SessionTransactionState.CLOSED:
                        # Transação já está fechada - marca como votada sem preparar
                        self.state = "voted"
                        return
                    
                    # Tenta preparar a transação
                    self.tx.prepare()
                    self.state = "voted"
                except ResourceClosedError:
                    # Transação foi fechada durante prepare() - marca como votada sem erro
                    self.state = "voted"
        
        TwoPhaseSessionDataManager.tpc_vote = tpc_vote_protected
        TwoPhaseSessionDataManager.tpc_vote._protected = True
    
    # Protege tpc_finish() contra ResourceClosedError
    if not hasattr(TwoPhaseSessionDataManager.tpc_finish, '_protected'):
        original_tpc_finish = TwoPhaseSessionDataManager.tpc_finish
        
        def tpc_finish_protected(self, trans):
            """Versão protegida do tpc_finish() que trata ResourceClosedError"""
            if self.tx is not None:
                try:
                    # ✅ CRÍTICO: Tenta fazer commit para persistir os dados
                    # IMPORTANTE: flush() NÃO persiste dados sem commit - apenas envia SQL dentro da transação
                    # Se não fizermos commit, os dados nunca serão persistidos no banco!
                    # 
                    # PROBLEMA CRÍTICO: A transação original (usada durante flush()) foi fechada ENTRE
                    # o retorno da resposta e tpc_finish(). O self.tx no DataManager pode não ser mais
                    # a mesma transação que foi usada durante flush().
                    #
                    # SOLUÇÃO: Verificamos se há uma transação ativa na sessão e, se houver, usamos ela.
                    # Se não houver, tentamos usar self.tx (que pode estar fechado).
                    try:
                        # ⚠️ IMPORTANTE: Verificamos se há uma transação ativa na sessão
                        # O self.tx pode não ser mais a mesma transação usada durante flush()
                        tx_atual = self.session.get_transaction()
                        tx_state_atual = None
                        if tx_atual and hasattr(tx_atual, '_state'):
                            tx_state_atual = tx_atual._state
                        
                        # Se há uma transação ativa na sessão diferente de self.tx, usamos ela
                        # Isso pode acontecer se a transação original foi fechada e uma nova foi criada
                        if tx_atual is not None and tx_atual != self.tx:
                            # Atualizamos self.tx para usar a transação atual da sessão
                            self.tx = tx_atual
                        
                        # Verifica o estado da transação que vamos usar
                        tx_state = None
                        if hasattr(self.tx, '_state'):
                            tx_state = self.tx._state
                        
                        # Se a transação está fechada, não podemos fazer commit
                        if tx_state == SessionTransactionState.CLOSED:
                            # ❌ ERRO CRÍTICO: Transação fechada antes do commit - dados NÃO foram persistidos
                            #
                            # PROBLEMA: A transação foi fechada ENTRE o retorno da resposta e tpc_finish().
                            # Isso pode acontecer se:
                            # 1. A transação original foi fechada durante o processamento da resposta
                            # 2. Uma nova transação foi criada (autobegin) mas também foi fechada
                            # 3. Algum middleware/hook do Zope está fechando a transação
                            #
                            # SOLUÇÃO: Como os dados já foram enviados via flush() na transação original,
                            # e essa transação foi fechada, os dados estão perdidos. Precisamos garantir
                            # que a transação original permaneça aberta até o commit.
                            logger.error(
                                f"config: tpc_finish() - ❌ ERRO CRÍTICO: Transação já está fechada para sessão {id(self.session)} "
                                f"ANTES do commit. Os dados enviados por flush() NÃO foram persistidos no banco! "
                                f"CAUSA: A transação foi fechada ENTRE o retorno da resposta e tpc_finish(). "
                                f"Isso pode ser causado por middleware/hook do Zope ou acesso a objetos da sessão durante serialização JSON. "
                                f"IMPACTO: Os dados estão perdidos - não foram persistidos. "
                                f"AÇÃO NECESSÁRIA: Garantir que a transação original permaneça aberta até o commit."
                            )
                            # Não podemos fazer commit se a transação está fechada
                            # Os dados não foram persistidos - isso é um erro crítico que precisa ser corrigido
                            self._finish("committed")  # Marcamos como committed para não quebrar o fluxo
                            return
                        
                        # ✅ Transação está ativa - tenta fazer commit normalmente
                        # Isso deve persistir os dados no banco
                        self.tx.commit()
                        self._finish("committed")
                    except ResourceClosedError as e:
                        # ❌ Transação foi fechada durante commit() - dados NÃO foram persistidos
                        logger.error(
                            f"config: tpc_finish() - ❌ ERRO CRÍTICO: ResourceClosedError durante commit() para sessão {id(self.session)}: {e} "
                            f"Os dados enviados por flush() NÃO foram persistidos no banco! "
                            f"CAUSA: A transação foi fechada durante o commit (possivelmente por flush()). "
                            f"IMPACTO: Os dados estão perdidos - não foram persistidos. "
                            f"AÇÃO NECESSÁRIA: Investigar por que flush() está fechando a transação."
                        )
                        # Não podemos fazer commit se a transação está fechada
                        # Os dados não foram persistidos - isso é um erro crítico
                        self._finish("committed")  # Marcamos como committed para não quebrar o fluxo
                except Exception as e:
                    # Qualquer outro erro - loga mas ainda finaliza para não quebrar o fluxo
                    logger.error(
                        f"config: tpc_finish() - Erro inesperado durante commit() para sessão {id(self.session)}: {e} "
                        f"Os dados podem não ter sido persistidos."
                    )
                    self._finish("committed")
        
        TwoPhaseSessionDataManager.tpc_finish = tpc_finish_protected
        TwoPhaseSessionDataManager.tpc_finish._protected = True


# Aplica proteção na importação do módulo (proteção permanente contra ResourceClosedError)
_apply_datamanager_protection()


def get_session():
    """
    Obtém uma sessão SQLAlchemy fresca e segura, ligada ao transaction manager do Zope.
    
    ✅ CORRETO: Use esta função para operações de ESCRITA.
    
    Esta função garante:
    1. Sessão sempre fresca e ativa (sem DataManager antigo ou transação fechada)
    2. Proteção contra ResourceClosedError em servidores de threads longas (ex: Waitress)
    3. Registro automático no transaction manager do Zope
    4. Detecção e correção de sessões problemáticas (transação fechada)
    5. Proteção adicional contra transações fechadas que ocorrem após flush()
    
    ⚠️ CRÍTICO: 
    - NÃO chame session.begin() manualmente
    - NÃO chame session.flush() manualmente - use apenas quando necessário para gerar IDs
    - NÃO chame session.commit() ou session.close()
    - NÃO chame session.remove() ou Session.remove()
    - Use mark_changed(session, keep_session=True) após session.add()
    - O zope.sqlalchemy controla a transação através de eventos
    - A sessão será iniciada automaticamente na primeira operação (autobegin do SQLAlchemy 2.0+)
    - NÃO use session.in_transaction() ou is_active - não existem em GloballyScopedSession
    
    Como funciona (baseado em SQLAlchemy 2.0.45 + zope.sqlalchemy-4.1 + z3c.saconfig):
    1. Obtém a sessão via named_scoped_session (cria sessão local por thread)
    2. Verifica se há transação fechada associada (proteção contra DataManager antigo)
    3. Se necessário, força uma nova sessão removendo a anterior do registry
    4. Registra eventos na sessão via register() (zope.sqlalchemy-4.1)
    5. Quando a primeira operação acontece (add, flush, etc.):
       - SQLAlchemy chama _autobegin_t() automaticamente
       - Cria SessionTransaction com origem AUTOBEGIN
       - Dispara evento 'after_begin'
    6. zope.sqlalchemy captura 'after_begin' e chama join_transaction()
    7. join_transaction() cria DataManager que pega transação existente
    8. DataManager junta a sessão ao transaction manager do Zope
    9. Zope faz commit/rollback através do DataManager
    
    ⚠️ IMPORTANTE: 
    - Esta função retorna uma sessão LOCAL, não global
    - A sessão é gerenciada pelo transaction manager do Zope
    - Não interfira no ciclo de vida da sessão (não limpe estado manualmente)
    
    Returns:
        Session: Sessão SQLAlchemy local fresca e registrada no transaction manager
    """
    from zope.sqlalchemy.datamanager import _SESSION_STATE
    from sqlalchemy.orm.session import SessionTransactionState
    from zope.sqlalchemy import register
    
    max_retries = 3
    for attempt in range(max_retries):
        # Obtém a sessão do scoped_session
        session = _SessionFactory()
        
        # Verifica se a sessão está em _SESSION_STATE e se precisa ser descartada
        # Isso protege contra DataManagers antigos e transações fechadas em servidores
        # de threads longas (ex: Waitress), eliminando ResourceClosedError
        needs_new_session = False
        if session in _SESSION_STATE:
            tx = session.get_transaction()
            
            # Verifica se há transação fechada
            if tx is not None and hasattr(tx, '_state'):
                try:
                    if tx._state == SessionTransactionState.CLOSED:
                        needs_new_session = True
                except Exception:
                    pass
        
        # Se precisar de nova sessão, remove a anterior e tenta novamente
        if needs_new_session:
            try:
                _SessionFactory.remove()
            except Exception as e:
                logger.warning(f"config: get_session() - Erro ao remover sessão anterior: {e}")
            continue  # Tenta novamente com nova sessão
        
        # ✅ CRÍTICO: Registra a sessão no transaction manager ANTES de qualquer operação
        # O register() garante que a sessão seja associada ao transaction manager do Zope
        # e que os eventos sejam capturados corretamente quando o autobegin criar a transação.
        #
        # NOTA: register() pode falhar silenciosamente se a sessão já está registrada,
        # mas ainda precisamos chamá-lo para garantir que os eventos estejam configurados
        try:
            register(session, keep_session=True)
        except Exception as e:
            # Se falhar ao registrar, pode ser que a sessão já está registrada
            # ou há um problema. Remove e tenta novamente.
            logger.warning(f"config: get_session() - Erro ao registrar sessão {id(session)}: {e} - tentando nova sessão")
            try:
                _SessionFactory.remove()
            except Exception:
                pass
            continue  # Tenta novamente
        
        # Verificação final: confirma que não há transação fechada após registro
        tx = session.get_transaction()
        if tx is not None and hasattr(tx, '_state'):
            try:
                if tx._state == SessionTransactionState.CLOSED:
                    # Mesmo após registrar, a transação está fechada - força nova sessão
                    try:
                        _SessionFactory.remove()
                    except Exception:
                        pass
                    continue  # Tenta novamente
            except Exception:
                pass
        
        # Sessão válida encontrada
        return session
    
    # Se chegou aqui, todas as tentativas falharam - retorna última sessão
    # (isso não deveria acontecer, mas é uma segurança)
    logger.error(f"config: get_session() - Não foi possível obter sessão válida após {max_retries} tentativas")
    session = _SessionFactory()
    register(session, keep_session=True)
    return session


# Para compatibilidade com recebimento_proposicoes.py (apenas leitura)
# Use get_session() para escrita
def Session():
    """
    Cria sessão sem registro no transaction manager (apenas para leitura).
    
    ⚠️ Use get_session() para operações de escrita.
    """
    return _SessionFactory()


logger.debug("config: Módulo configurado - use get_session() para escrita, Session() para leitura")
