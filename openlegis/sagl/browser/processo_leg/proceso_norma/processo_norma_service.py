# -*- coding: utf-8 -*-
"""
Serviço unificado para acesso ao processo integral de normas jurídicas.
Abstrai as chamadas às views e métodos relacionados ao processo de normas.
"""
import json
import logging
from typing import Dict, Optional, Any
from Products.CMFCore.utils import getToolByName

logger = logging.getLogger(__name__)


class ProcessoNormaService:
    """
    Serviço que encapsula o acesso ao processo integral de normas jurídicas.
    Fornece uma interface limpa para obter documentos, criar tasks, etc.
    """
    
    def __init__(self, context, request=None):
        """
        Inicializa o serviço.
        
        Args:
            context: Contexto Zope (portal ou objeto)
            request: Request Zope (opcional, será obtido do context se não fornecido)
        """
        self.context = context
        self.request = request
        if hasattr(context, 'REQUEST'):
            self.request = context.REQUEST
        elif request is None:
            # Tenta obter do portal
            try:
                portal = getToolByName(context, 'portal_url').getPortalObject()
                if hasattr(portal, 'REQUEST'):
                    self.request = portal.REQUEST
            except:
                pass
    
    def get_portal(self):
        """Obtém o objeto portal"""
        return getToolByName(self.context, 'portal_url').getPortalObject()
    
    def get_tool(self):
        """Obtém o tool portal_sagl"""
        return getToolByName(self.context, 'portal_sagl')
    
    def get_documentos_prontos(self, cod_norma, skip_signature_check=True):
        """
        Obtém documentos prontos do processo integral de norma.
        
        Args:
            cod_norma: Código da norma
            skip_signature_check: Se True, pula verificação de assinatura (apenas verifica arquivos)
            
        Returns:
            dict: Dicionário com documentos ou estrutura vazia se não houver documentos prontos
        """
        if not self.request:
            logger.error("[ProcessoNormaService] Request não disponível")
            return {'documentos': [], 'total_paginas': 0, 'cod_norma': cod_norma}
        
        try:
            # Salva action original se existir
            original_action = self.request.form.get('action')
            
            # Prepara para chamar a view
            self.request.form['cod_norma'] = cod_norma
            self.request.form['action'] = 'json'
            if skip_signature_check:
                self.request.form['skip_signature_check'] = '1'
            
            # Chama a view diretamente
            portal = self.get_portal()
            view = portal.restrictedTraverse('@@processo_norma_integral')
            result = view()
            
            # Remove flag
            self.request.form.pop('skip_signature_check', None)
            
            # Restaura action original
            if original_action:
                self.request.form['action'] = original_action
            else:
                self.request.form.pop('action', None)
            
            # Processa resultado
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except (json.JSONDecodeError, ValueError):
                    result = None
            
            # Retorna resultado ou estrutura vazia
            if isinstance(result, dict) and 'documentos' in result:
                return result
            else:
                return {'documentos': [], 'total_paginas': 0, 'cod_norma': cod_norma}
                
        except Exception as e:
            logger.error(f"[ProcessoNormaService] Erro ao obter documentos prontos: {e}", exc_info=True)
            return {'documentos': [], 'total_paginas': 0, 'cod_norma': cod_norma, 'error': str(e)}
    
    def criar_task_async(self, cod_norma, portal_url=None):
        """
        Cria uma task assíncrona para gerar o processo integral de norma.
        
        Args:
            cod_norma: Código da norma (int)
            portal_url: URL do portal (opcional, será obtida automaticamente se não fornecida)
            
        Returns:
            dict: Dicionário com task_id e status, ou None em caso de erro
        """
        try:
            tool = self.get_tool()
            if not hasattr(tool, 'processo_norma_integral_async'):
                logger.error("[ProcessoNormaService] Método processo_norma_integral_async não encontrado")
                return None
            
            if portal_url is None:
                portal = self.get_portal()
                portal_url = str(portal.absolute_url())
            
            result = tool.processo_norma_integral_async(cod_norma, portal_url)
            
            if result and isinstance(result, dict) and 'task_id' in result:
                return result
            else:
                logger.error(f"[ProcessoNormaService] Resultado inválido: {result}")
                return None
                
        except Exception as e:
            logger.error(f"[ProcessoNormaService] Erro ao criar task assíncrona: {e}", exc_info=True)
            return None
    
    def verificar_task_status(self, task_id):
        """
        Verifica o status de uma task.
        
        Args:
            task_id: ID da task
            
        Returns:
            dict: Status da task ou None em caso de erro
        """
        try:
            tool = self.get_tool()
            if not hasattr(tool, 'get_task_status'):
                logger.error("[ProcessoNormaService] Método get_task_status não encontrado")
                return None
            
            status = tool.get_task_status(task_id)
            return status
            
        except Exception as e:
            logger.error(f"[ProcessoNormaService] Erro ao verificar status da task: {e}", exc_info=True)
            return None
    
    def verificar_tasks_ativas(self, cod_norma):
        """
        Verifica se há tasks ativas para uma norma.
        
        Args:
            cod_norma: Código da norma
            
        Returns:
            tuple: (has_active_task, task_id, task_status) ou (False, None, None)
        """
        try:
            from celery import current_app
            
            tool = self.get_tool()
            if not hasattr(tool, 'processo_norma_integral_async'):
                return (False, None, None)
            
            cod_norma_str = str(cod_norma)
            inspect = current_app.control.inspect(timeout=0.3)
            
            if not inspect:
                return (False, None, None)
            
            # Verifica tasks ativas
            try:
                active = inspect.active()
                if active:
                    for worker, tasks in active.items():
                        if not tasks:
                            continue
                        for task in (tasks if isinstance(tasks, list) else [tasks]):
                            task_kwargs = task.get('kwargs', {})
                            task_cod_norma = task_kwargs.get('cod_norma')
                            task_name = str(task.get('name', '') or task.get('task', ''))
                            
                            task_cod_str = str(task_cod_norma) if task_cod_norma is not None else None
                            
                            if (task_cod_str == cod_norma_str and 
                                'gerar_processo_norma_integral_task' in task_name):
                                return (True, task.get('id'), 'PROGRESS')
                
                # Verifica tasks reservadas (na fila)
                reserved = inspect.reserved()
                if reserved:
                    for worker, tasks in reserved.items():
                        if not tasks:
                            continue
                        for task in (tasks if isinstance(tasks, list) else [tasks]):
                            task_kwargs = task.get('kwargs', {})
                            task_cod_norma = task_kwargs.get('cod_norma')
                            task_name = str(task.get('name', '') or task.get('task', ''))
                            
                            task_cod_str = str(task_cod_norma) if task_cod_norma is not None else None
                            
                            if (task_cod_str == cod_norma_str and 
                                'gerar_processo_norma_integral_task' in task_name):
                                return (True, task.get('id'), 'PENDING')
            except Exception:
                pass  # Ignora erros na verificação rápida
                
        except Exception as e:
            logger.debug(f"[ProcessoNormaService] Erro ao verificar tasks ativas: {e}")
        
        return (False, None, None)
