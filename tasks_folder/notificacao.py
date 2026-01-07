"""
Sistema de notificação para tarefas Celery concluídas.

Este módulo fornece funções para notificar usuários quando tarefas assíncronas
são concluídas, permitindo que continuem usando o sistema enquanto aguardam.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def criar_notificacao_tarefa(task_id: str, user_id: Optional[str], 
                             tipo: str, titulo: str, mensagem: str,
                             dados_extras: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Cria uma notificação para o usuário sobre uma tarefa concluída.
    
    Args:
        task_id: ID da tarefa Celery
        user_id: ID do usuário (None para notificação global)
        tipo: Tipo da notificação ('success', 'error', 'info', 'warning')
        titulo: Título da notificação
        mensagem: Mensagem da notificação
        dados_extras: Dados adicionais (ex: URL de download)
    
    Returns:
        dict: Dados da notificação criada
    """
    notificacao = {
        'task_id': task_id,
        'user_id': user_id,
        'tipo': tipo,
        'titulo': titulo,
        'mensagem': mensagem,
        'timestamp': None,  # Será preenchido quando salva
        'lida': False
    }
    
    if dados_extras:
        notificacao.update(dados_extras)
    
    return notificacao


def salvar_notificacao_zodb(site, notificacao: Dict[str, Any]) -> bool:
    """
    Salva notificação no ZODB (se houver estrutura para isso).
    
    Args:
        site: Objeto site do Zope
        notificacao: Dicionário com dados da notificação
    
    Returns:
        bool: True se salva com sucesso
    """
    try:
        # Tenta salvar em uma estrutura de notificações
        # Adapte conforme a estrutura do seu projeto
        if not hasattr(site, 'notificacoes_tarefas'):
            # Cria estrutura se não existir
            from OFS.Folder import Folder
            site.notificacoes_tarefas = Folder('notificacoes_tarefas')
            site.notificacoes_tarefas._setObject('notificacoes_tarefas', Folder('notificacoes_tarefas'))
        
        # Salva a notificação
        from DateTime import DateTime
        notificacao['timestamp'] = DateTime().ISO()
        
        # Armazena por task_id
        task_id = notificacao['task_id']
        site.notificacoes_tarefas._setObject(task_id, type('Notification', (), notificacao)())
        
        logger.info(f"Notificação salva para task_id={task_id}, user_id={notificacao.get('user_id')}")
        return True
        
    except Exception as e:
        logger.warning(f"Não foi possível salvar notificação no ZODB: {e}")
        # Não é crítico, apenas loga o aviso
        return False


def notificar_processo_leg_concluido(site, task_id: str, user_id: Optional[str],
                                     resultado: Dict[str, Any]) -> None:
    """
    Cria notificação quando processo legislativo é gerado com sucesso.
    
    Args:
        site: Objeto site do Zope
        task_id: ID da tarefa
        user_id: ID do usuário
        resultado: Resultado da tarefa
    """
    try:
        total_paginas = resultado.get('total_paginas', 0)
        total_documentos = resultado.get('total_documentos', 0)
        cod_materia = resultado.get('cod_materia', '')
        download_url = resultado.get('download_url', '')
        
        titulo = f"Processo Integral Gerado"
        mensagem = (
            f"O processo integral foi gerado com sucesso! "
            f"Total: {total_paginas} páginas, {total_documentos} documentos."
        )
        
        notificacao = criar_notificacao_tarefa(
            task_id=task_id,
            user_id=user_id,
            tipo='success',
            titulo=titulo,
            mensagem=mensagem,
            dados_extras={
                'cod_materia': cod_materia,
                'download_url': download_url,
                'total_paginas': total_paginas,
                'total_documentos': total_documentos
            }
        )
        
        salvar_notificacao_zodb(site, notificacao)
        
        logger.info(f"Notificação criada para processo leg concluído: task_id={task_id}")
        
    except Exception as e:
        logger.error(f"Erro ao criar notificação: {e}", exc_info=True)


def notificar_processo_leg_erro(site, task_id: str, user_id: Optional[str],
                               erro: str) -> None:
    """
    Cria notificação quando há erro na geração do processo.
    
    Args:
        site: Objeto site do Zope
        task_id: ID da tarefa
        user_id: ID do usuário
        erro: Mensagem de erro
    """
    try:
        notificacao = criar_notificacao_tarefa(
            task_id=task_id,
            user_id=user_id,
            tipo='error',
            titulo='Erro na Geração do Processo',
            mensagem=f"Ocorreu um erro ao gerar o processo integral: {erro}",
            dados_extras={'erro': erro}
        )
        
        salvar_notificacao_zodb(site, notificacao)
        
        logger.info(f"Notificação de erro criada: task_id={task_id}")
        
    except Exception as e:
        logger.error(f"Erro ao criar notificação de erro: {e}", exc_info=True)
