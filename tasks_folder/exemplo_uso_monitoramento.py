"""
Exemplo prático de como usar o monitoramento de tarefas Celery no Zope.

Este arquivo serve como referência e pode ser adaptado para PythonScripts no Zope.
"""

# ============================================================================
# EXEMPLO 1: Iniciar tarefa e monitorar status
# ============================================================================

def exemplo_iniciar_e_monitorar(context):
    """
    Exemplo de como iniciar uma tarefa e monitorar seu status.
    Use este código em um PythonScript no Zope.
    """
    from Products.CMFCore.utils import getToolByName
    
    tool = getToolByName(context, 'portal_sagl')
    cod_proposicao = 123  # Exemplo
    
    # 1. Inicia a tarefa assíncrona
    resultado = tool.proposicao_autuar_async_with_status(cod_proposicao)
    task_id = resultado['task_id']
    
    # 2. Verifica o status periodicamente
    import time
    max_tentativas = 30  # 30 tentativas
    intervalo = 2  # 2 segundos entre verificações
    
    for tentativa in range(max_tentativas):
        status = tool.get_task_status(task_id)
        
        if status['ready']:
            if 'result' in status:
                return f"Tarefa concluída com sucesso! Resultado: {status['result']}"
            else:
                return f"Tarefa falhou: {status.get('error', 'Erro desconhecido')}"
        
        # Aguarda antes da próxima verificação
        time.sleep(intervalo)
    
    return f"Timeout: Tarefa ainda em execução após {max_tentativas * intervalo} segundos"


# ============================================================================
# EXEMPLO 2: Usar wait_for_task (bloqueante)
# ============================================================================

def exemplo_aguardar_tarefa(context):
    """
    Exemplo usando wait_for_task que bloqueia até a conclusão.
    """
    from Products.CMFCore.utils import getToolByName
    
    tool = getToolByName(context, 'portal_sagl')
    task_id = context.REQUEST.get('task_id')
    
    if not task_id:
        return {'error': 'task_id não fornecido'}
    
    try:
        # Aguarda até 60 segundos
        resultado = tool.wait_for_task(task_id, timeout=60, interval=1)
        
        if 'result' in resultado:
            return {'success': True, 'result': resultado['result']}
        else:
            return {'success': False, 'error': resultado.get('error')}
    
    except TimeoutError:
        return {'error': 'Timeout: tarefa não concluída em 60 segundos'}


# ============================================================================
# EXEMPLO 3: Verificar status via REQUEST (para uso em views)
# ============================================================================

def exemplo_verificar_status_request(context):
    """
    Exemplo para verificar status de tarefa via parâmetro REQUEST.
    Útil para views que recebem task_id via GET/POST.
    """
    from Products.CMFCore.utils import getToolByName
    
    tool = getToolByName(context, 'portal_sagl')
    task_id = context.REQUEST.get('task_id', '')
    
    if not task_id:
        return {'error': 'Parâmetro task_id não fornecido'}
    
    status = tool.get_task_status(task_id)
    return status


# ============================================================================
# EXEMPLO 4: Cancelar tarefa
# ============================================================================

def exemplo_cancelar_tarefa(context):
    """
    Exemplo de como cancelar uma tarefa em execução.
    """
    from Products.CMFCore.utils import getToolByName
    
    tool = getToolByName(context, 'portal_sagl')
    task_id = context.REQUEST.get('task_id', '')
    
    if not task_id:
        return {'error': 'task_id não fornecido'}
    
    # Verifica status antes de cancelar
    status = tool.get_task_status(task_id)
    
    if status['status'] in ['SUCCESS', 'FAILURE']:
        return {'error': 'Tarefa já foi concluída, não é possível cancelar'}
    
    # Cancela a tarefa
    sucesso = tool.revoke_task(task_id, terminate=False)
    
    if sucesso:
        return {'message': 'Tarefa cancelada com sucesso', 'task_id': task_id}
    else:
        return {'error': 'Falha ao cancelar tarefa'}


# ============================================================================
# EXEMPLO 5: Integração com DTML (retornar JSON)
# ============================================================================

def exemplo_json_status(context):
    """
    Retorna status em formato JSON para uso em AJAX.
    """
    from Products.CMFCore.utils import getToolByName
    import json
    
    tool = getToolByName(context, 'portal_sagl')
    task_id = context.REQUEST.get('task_id', '')
    
    if not task_id:
        return json.dumps({'error': 'task_id não fornecido'})
    
    status = tool.get_task_status(task_id)
    return json.dumps(status)


# ============================================================================
# EXEMPLO 6: Armazenar task_id no ZODB para consulta posterior
# ============================================================================

def exemplo_armazenar_task_id(context, cod_proposicao):
    """
    Exemplo de como armazenar o task_id no objeto para consulta posterior.
    """
    from Products.CMFCore.utils import getToolByName
    
    tool = getToolByName(context, 'portal_sagl')
    
    # Inicia a tarefa
    resultado = tool.proposicao_autuar_async_with_status(cod_proposicao)
    task_id = resultado['task_id']
    
    # Armazena o task_id no objeto (exemplo: em um atributo customizado)
    # Nota: Adapte conforme a estrutura do seu objeto
    try:
        proposicao = context.unrestrictedTraverse(f'sapl_documentos/proposicao/{cod_proposicao}_signed.pdf')
        # Se o objeto suportar atributos customizados:
        # proposicao.task_id_autuacao = task_id
        # proposicao._p_changed = 1
    except:
        pass
    
    return {
        'task_id': task_id,
        'message': 'Tarefa iniciada. Use get_task_status para verificar progresso.'
    }
