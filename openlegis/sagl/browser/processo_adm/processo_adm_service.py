# -*- coding: utf-8 -*-
"""
Serviço unificado para acesso ao processo administrativo.
Abstrai as chamadas às views e métodos relacionados ao processo administrativo.
"""
import json
import logging
import os
from typing import Dict, Optional, Any

try:
    from Products.CMFCore.utils import getToolByName
except ImportError:
    getToolByName = None

logger = logging.getLogger(__name__)


class ProcessoAdmService:
    """
    Serviço que encapsula o acesso ao processo administrativo.
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
    
    def get_documentos_prontos(self, cod_documento, skip_signature_check=True):
        """
        Obtém documentos prontos do processo administrativo.
        
        Busca os documentos diretamente do diretório onde foram salvos pela task,
        sem depender de views HTTP.
        
        Args:
            cod_documento: Código do documento administrativo
            skip_signature_check: Se True, pula verificação de assinatura (apenas verifica arquivos)
            
        Returns:
            dict: Dicionário com documentos ou estrutura vazia se não houver documentos prontos
        """
        import os
        from openlegis.sagl.browser.processo_adm.processo_adm_utils import get_processo_dir_adm, get_cache_file_path_adm
        
        try:
            cod_documento_int = int(cod_documento) if not isinstance(cod_documento, int) else cod_documento
            dir_base = get_processo_dir_adm(cod_documento_int)
            
            # Verifica se o diretório existe
            if not os.path.exists(dir_base) or not os.path.isdir(dir_base):
                logger.debug(f"[ProcessoAdmService] Diretório não encontrado: {dir_base}")
                return {'documentos': [], 'total_paginas': 0, 'cod_documento': cod_documento_int}
            
            # Tenta carregar do cache (metadados) que tem informações de páginas
            cache_file = get_cache_file_path_adm(cod_documento_int)
            metadados_path = os.path.join(dir_base, 'documentos_metadados.json')
            documentos_list = []
            total_paginas_from_meta = 0  # Inicializa no escopo correto
            documentos_carregados_do_meta = False  # Flag para indicar se carregou dos metadados
            
            # CRÍTICO: Carrega metadados completos que incluem informações de páginas
            if os.path.exists(metadados_path):
                try:
                    with open(metadados_path, 'r', encoding='utf-8') as f:
                        metadados = json.load(f)
                    
                    documentos_metadados = metadados.get('documentos', [])
                    # CRÍTICO: Obtém total_paginas dos metadados PRIMEIRO (valor correto, não estimativa)
                    # IMPORTANTE: Preserva este valor mesmo se houver erro depois
                    total_paginas_from_meta = metadados.get('total_paginas', 0)
                    
                    # CRÍTICO: Se total_paginas não está nos metadados, tenta contar do diretório antes de processar documentos
                    if total_paginas_from_meta == 0:
                        dir_paginas_check = os.path.join(dir_base, 'pages')
                        if os.path.exists(dir_paginas_check) and os.path.isdir(dir_paginas_check):
                            try:
                                pagina_files_check = [f for f in os.listdir(dir_paginas_check) if f.lower().endswith('.pdf')]
                                if pagina_files_check:
                                    total_paginas_from_meta = len(pagina_files_check)
                                    logger.info(f"[ProcessoAdmService] 🔄 total_paginas não estava nos metadados, contado do diretório: {total_paginas_from_meta}")
                            except Exception as e:
                                logger.debug(f"[ProcessoAdmService] Erro ao contar páginas do diretório: {e}")
                    
                    # Obtém portal_url do contexto (tentativa separada para não perder total_paginas em caso de erro)
                    portal_url = 'http://localhost:8080/sagl'  # Valor padrão
                    try:
                        if getToolByName is not None:
                            portal = getToolByName(self.context, 'portal_url').getPortalObject()
                            portal_url = str(portal.absolute_url())
                        else:
                            raise AttributeError("getToolByName não disponível")
                    except Exception as portal_err:
                        logger.warning(f"[ProcessoAdmService] Erro ao obter portal_url via getToolByName: {portal_err}")
                        # Tenta obter do request se disponível
                        if self.request:
                            # Tenta obter SERVER_URL ou construir a partir do request
                            try:
                                server_url = self.request.get('SERVER_URL')
                                if not server_url:
                                    # Constrói a partir do request
                                    protocol = 'https' if self.request.get('SERVER_PORT') == '443' else 'http'
                                    host = self.request.get('HTTP_HOST', 'localhost:8080')
                                    server_url = f"{protocol}://{host}"
                                portal_url = str(server_url)
                            except Exception:
                                portal_url = 'http://localhost:8080/sagl'
                        else:
                            portal_url = 'http://localhost:8080/sagl'
                    
                    logger.debug(f"[ProcessoAdmService] portal_url obtido: {portal_url}")
                    
                    # CRÍTICO: Marca que vai carregar dos metadados ANTES de processar documentos
                    # Isso garante que mesmo se houver erro ao construir páginas, o total_paginas seja preservado
                    documentos_carregados_do_meta = True
                    
                    # Verifica se o diretório de páginas existe
                    dir_paginas = os.path.join(dir_base, 'pages')
                    pages_exist = os.path.exists(dir_paginas) and os.path.isdir(dir_paginas)
                    
                    # Lista arquivos de páginas para validação
                    pagina_files_available = []
                    if pages_exist:
                        try:
                            pagina_files_available = [f for f in os.listdir(dir_paginas) if f.lower().endswith('.pdf')]
                            logger.debug(f"[ProcessoAdmService] Encontrados {len(pagina_files_available)} arquivos de páginas no diretório")
                        except Exception as e:
                            logger.debug(f"[ProcessoAdmService] Erro ao listar páginas: {e}")
                    
                    # Constrói documentos com informações de páginas
                    for doc_meta in documentos_metadados:
                        start_page = doc_meta.get('start_page', 1)
                        end_page = doc_meta.get('end_page', 1)
                        num_pages = doc_meta.get('num_pages', end_page - start_page + 1 if end_page >= start_page else 1)
                        
                        # Constrói páginas com URLs
                        paginas = []
                        if pages_exist:
                            for page_num in range(start_page, end_page + 1):
                                pagina_filename = f'pg_{page_num:04d}.pdf'
                                pagina_path = os.path.join(dir_paginas, pagina_filename)
                                
                                # Verifica se a página existe (pode usar formato diferente)
                                if not os.path.exists(pagina_path):
                                    # Tenta formato alternativo sem zero padding
                                    pagina_filename_alt = f'pg_{page_num}.pdf'
                                    pagina_path_alt = os.path.join(dir_paginas, pagina_filename_alt)
                                    if os.path.exists(pagina_path_alt):
                                        pagina_filename = pagina_filename_alt
                                        pagina_path = pagina_path_alt
                                    else:
                                        # Tenta formato numérico simples
                                        pagina_filename_alt = f'{page_num}.pdf'
                                        pagina_path_alt = os.path.join(dir_paginas, pagina_filename_alt)
                                        if os.path.exists(pagina_path_alt):
                                            pagina_filename = pagina_filename_alt
                                            pagina_path = pagina_path_alt
                                
                                if os.path.exists(pagina_path):
                                    # Constrói URL da página usando a view pagina_processo_adm_integral
                                    pagina_url = f"{portal_url}/@@pagina_processo_adm_integral?cod_documento={cod_documento_int}&pagina={pagina_filename}"
                                    paginas.append({
                                        'num_pagina': page_num,
                                        'url': pagina_url
                                    })
                        
                        # Se não encontrou páginas individuais, usa o documento completo
                        if not paginas and start_page <= end_page:
                            # Constrói URL do documento completo (primeira página)
                            doc_filename = doc_meta.get('file', '')
                            if doc_filename:
                                # Usa a primeira página como URL base
                                primeira_pagina = f'pg_{start_page:04d}.pdf'
                                pagina_url = f"{portal_url}/@@pagina_processo_adm_integral?cod_documento={cod_documento_int}&pagina={primeira_pagina}"
                                paginas.append({
                                    'num_pagina': start_page,
                                    'url': pagina_url
                                })
                        
                        # Adiciona documento com páginas
                        doc_item = {
                            'title': doc_meta.get('title', ''),
                            'data': doc_meta.get('data', ''),
                            'file': doc_meta.get('file', ''),
                            'file_size': doc_meta.get('file_size', 0),
                            'start_page': start_page,
                            'end_page': end_page,
                            'num_pages': num_pages,
                            'paginas': paginas,
                            'paginas_doc': len(paginas) if paginas else num_pages
                        }
                        documentos_list.append(doc_item)
                    
                    # CRÍTICO: Verifica se total_paginas_from_meta foi obtido corretamente
                    # Se ainda está 0 após todas as tentativas, usa contagem de arquivos como última opção
                    if total_paginas_from_meta == 0 and pagina_files_available:
                        total_paginas_from_meta = len(pagina_files_available)
                        logger.info(f"[ProcessoAdmService] 🔄 total_paginas não estava nos metadados, usando contagem de arquivos: {total_paginas_from_meta}")
                    
                except Exception as e:
                    logger.error(f"[ProcessoAdmService] ❌ Erro ao ler metadados: {e}", exc_info=True)
                    documentos_carregados_do_meta = False
                    # Em caso de erro, reseta total_paginas_from_meta para evitar usar valor incorreto
                    # Mas tenta preservar se foi carregado antes do erro
                    if 'total_paginas_from_meta' not in locals() or total_paginas_from_meta == 0:
                        total_paginas_from_meta = 0
                    # Continua com listagem de arquivos como fallback
            else:
                documentos_carregados_do_meta = False
                logger.debug(f"[ProcessoAdmService] Arquivo de metadados não encontrado: {metadados_path}")
            
            # Se não encontrou no cache, tenta listar arquivos PDF diretamente do diretório
            if not documentos_list:
                try:
                    pdf_files = [f for f in os.listdir(dir_base) if f.lower().endswith('.pdf')]
                    pdf_files.sort()  # Ordena por nome
                    
                    # Prioriza processo_integral.pdf (PDF final gerado)
                    if 'processo_integral.pdf' in pdf_files:
                        pdf_files.remove('processo_integral.pdf')
                        pdf_files.insert(0, 'processo_integral.pdf')
                    
                    for pdf_file in pdf_files:
                        file_path = os.path.join(dir_base, pdf_file)
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                            # Determina título baseado no nome do arquivo
                            if pdf_file == 'processo_integral.pdf':
                                title = 'Processo Administrativo Integral'
                            elif pdf_file.startswith('capa_') or pdf_file.endswith('capa.pdf') or 'capa' in pdf_file.lower():
                                title = 'Capa do Processo'
                            elif 'texto_integral' in pdf_file:
                                title = 'Texto Integral'
                            elif '_acessorio' in pdf_file:
                                title = 'Documento Acessório'
                            elif '_tram' in pdf_file:
                                title = 'Tramitação'
                            elif 'cientificacoes' in pdf_file.lower() or 'cientificacoes' in pdf_file.lower():
                                title = 'Folha de Cientificações'
                            else:
                                title = pdf_file.replace('.pdf', '').replace('_', ' ').title()
                            
                            documentos_list.append({
                                'file': pdf_file,
                                'title': title,
                                'file_size': os.path.getsize(file_path),
                                'path': dir_base
                            })
                except Exception as e:
                    logger.debug(f"[ProcessoAdmService] Erro ao listar arquivos PDF: {e}")
            
            # CRÍTICO: Se não carregou dos metadados, tenta adicionar PDF final
            # Mas se já carregou dos metadados, NÃO modifica a lista (metadados já têm tudo correto)
            if not documentos_carregados_do_meta:
                # Busca pelo arquivo final gerado (formato: PA-{num}-{ano}.pdf ou documento-{cod}.pdf)
                arquivo_final_nome = None
                try:
                    pdf_files_in_dir = [f for f in os.listdir(dir_base) if f.lower().endswith('.pdf') and not f.startswith('pg_') and not f.startswith('page_')]
                    if pdf_files_in_dir:
                        # Ordena por tamanho (maior primeiro)
                        pdf_files_with_size = []
                        for pdf_file in pdf_files_in_dir:
                            file_path = os.path.join(dir_base, pdf_file)
                            if os.path.exists(file_path):
                                pdf_files_with_size.append((pdf_file, os.path.getsize(file_path)))
                        
                        if pdf_files_with_size:
                            # Ordena por tamanho (decrescente)
                            pdf_files_with_size.sort(key=lambda x: x[1], reverse=True)
                            # O arquivo final é geralmente o maior (processo completo)
                            arquivo_final_nome = pdf_files_with_size[0][0]
                        
                        # Adiciona o PDF final como primeiro item (se não está na lista)
                        if arquivo_final_nome:
                            arquivo_final_path = os.path.join(dir_base, arquivo_final_nome)
                            if os.path.exists(arquivo_final_path) and os.path.getsize(arquivo_final_path) > 0:
                                arquivo_final_exists = any(doc.get('file') == arquivo_final_nome for doc in documentos_list)
                                if not arquivo_final_exists:
                                    documentos_list.insert(0, {
                                        'file': arquivo_final_nome,
                                        'title': 'Processo Administrativo Integral',
                                        'file_size': os.path.getsize(arquivo_final_path),
                                        'path': dir_base
                                    })
                                    logger.debug(f"[ProcessoAdmService] PDF final adicionado à lista: {arquivo_final_nome}")
                except Exception as e:
                    logger.debug(f"[ProcessoAdmService] Erro ao descobrir arquivo final: {e}")
            
            # CRÍTICO: Calcula total_paginas corretamente
            total_paginas = 0
            
            # PRIORIDADE 1: Se carregou dos metadados, usa o total_paginas dos metadados (valor correto)
            # IMPORTANTE: Usa o valor mesmo que seja 0, mas só se realmente carregou dos metadados
            if documentos_carregados_do_meta and total_paginas_from_meta > 0:
                total_paginas = total_paginas_from_meta
            elif documentos_carregados_do_meta and total_paginas_from_meta == 0:
                # Se carregou dos metadados mas total_paginas é 0, pode ser problema nos metadados
                logger.warning(f"[ProcessoAdmService] ⚠️ Carregou dos metadados mas total_paginas é 0, tentando recalcular...")
            else:
                logger.debug(f"[ProcessoAdmService] total_paginas_from_meta não disponível (carregado={documentos_carregados_do_meta}, valor={total_paginas_from_meta})")
            
            # PRIORIDADE 2: Se não tem total_paginas dos metadados, calcula baseado nas páginas reais
            if total_paginas == 0:
                logger.debug(f"[ProcessoAdmService] total_paginas não encontrado nos metadados, calculando...")
                # Tenta contar páginas reais no diretório pages
                dir_paginas = os.path.join(dir_base, 'pages')
                if os.path.exists(dir_paginas) and os.path.isdir(dir_paginas):
                    try:
                        pagina_files = [f for f in os.listdir(dir_paginas) if f.lower().endswith('.pdf')]
                        total_paginas = len(pagina_files)
                    except Exception:
                        pass
                
                # Se ainda não tem, calcula baseado nos documentos
                if total_paginas == 0:
                    # Soma páginas de cada documento se disponível
                    total_from_docs = 0
                    for doc in documentos_list:
                        if 'num_pages' in doc and doc['num_pages']:
                            total_from_docs += int(doc['num_pages'])
                        elif 'end_page' in doc and 'start_page' in doc:
                            start = doc.get('start_page', 1)
                            end = doc.get('end_page', 1)
                            if end >= start:
                                total_from_docs += (end - start + 1)
                        elif 'paginas' in doc and isinstance(doc['paginas'], list):
                            total_from_docs += len(doc['paginas'])
                        elif 'paginas_doc' in doc:
                            total_from_docs += int(doc['paginas_doc'] or 0)
                    
                    if total_from_docs > 0:
                        total_paginas = total_from_docs
                    else:
                        # Fallback: estimativa baseada no tamanho dos arquivos
                        total_size = sum(doc.get('file_size', 0) for doc in documentos_list)
                        if total_size > 0:
                            # Estimativa: 1 página = ~50KB (média)
                            total_paginas = max(1, int(total_size / (50 * 1024)))
            
            # Garante que total_paginas seja pelo menos 1 se há documentos
            if total_paginas == 0 and len(documentos_list) > 0:
                total_paginas = 1  # Mínimo de 1 página se há documentos
                logger.warning(f"[ProcessoAdmService] total_paginas era 0, ajustando para 1 (mínimo)")
            
            # CRÍTICO: Mantém campos importantes dos documentos (paginas, start_page, end_page, etc.)
            # Apenas remove campos desnecessários (path interno)
            documentos_clean = []
            for doc in documentos_list:
                doc_clean = {
                    'file': doc.get('file', ''),
                    'title': doc.get('title', ''),
                    'data': doc.get('data', ''),
                    'file_size': doc.get('file_size', 0)
                }
                
                # Mantém campos importantes para o frontend
                if 'start_page' in doc:
                    doc_clean['start_page'] = doc.get('start_page')
                if 'end_page' in doc:
                    doc_clean['end_page'] = doc.get('end_page')
                if 'num_pages' in doc:
                    doc_clean['num_pages'] = doc.get('num_pages')
                if 'paginas' in doc:
                    doc_clean['paginas'] = doc.get('paginas', [])
                if 'paginas_doc' in doc:
                    doc_clean['paginas_doc'] = doc.get('paginas_doc')
                
                documentos_clean.append(doc_clean)
            
            # CRÍTICO: Valida que total_paginas está correto antes de retornar
            if total_paginas == 0 and len(documentos_clean) > 0:
                # Última tentativa: conta páginas do diretório se ainda não tem valor
                try:
                    dir_paginas_final = os.path.join(dir_base, 'pages')
                    if os.path.exists(dir_paginas_final) and os.path.isdir(dir_paginas_final):
                        pagina_files_final = [f for f in os.listdir(dir_paginas_final) if f.lower().endswith('.pdf')]
                        if pagina_files_final:
                            total_paginas = len(pagina_files_final)
                            logger.info(f"[ProcessoAdmService] 🔄 Última tentativa: contadas {total_paginas} páginas do diretório")
                except Exception as e:
                    logger.debug(f"[ProcessoAdmService] Erro na última tentativa de contar páginas: {e}")
            
            # Garante mínimo de 1 se há documentos (só como último recurso)
            if total_paginas == 0 and len(documentos_clean) > 0:
                total_paginas = 1
                logger.warning(f"[ProcessoAdmService] ⚠️ total_paginas ainda era 0, usando mínimo: 1")
            
            return {
                'documentos': documentos_clean,
                'total_paginas': int(total_paginas),  # Garante que é int
                'cod_documento': int(cod_documento_int)  # Garante que é int
            }
                
        except Exception as e:
            logger.error(f"[ProcessoAdmService] Erro ao obter documentos prontos: {e}", exc_info=True)
            return {'documentos': [], 'total_paginas': 0, 'cod_documento': cod_documento, 'error': str(e)}
    
    def criar_task_async(self, cod_documento, portal_url=None):
        """
        Cria uma task assíncrona para gerar o processo administrativo.
        
        Args:
            cod_documento: Código do documento administrativo (int)
            portal_url: URL do portal (opcional, será obtida automaticamente se não fornecida)
            
        Returns:
            dict: Dicionário com task_id e status, ou None em caso de erro
        """
        try:
            tool = self.get_tool()
            if not hasattr(tool, 'processo_adm_integral_async'):
                logger.error("[ProcessoAdmService] Método processo_adm_integral_async não encontrado")
                return None
            
            if portal_url is None:
                portal = self.get_portal()
                portal_url = str(portal.absolute_url())
            
            result = tool.processo_adm_integral_async(cod_documento, portal_url)
            
            if result and isinstance(result, dict) and 'task_id' in result:
                return result
            else:
                logger.error(f"[ProcessoAdmService] Resultado inválido: {result}")
                return None
                
        except Exception as e:
            logger.error(f"[ProcessoAdmService] Erro ao criar task assíncrona: {e}", exc_info=True)
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
                logger.error("[ProcessoAdmService] Método get_task_status não encontrado")
                return None
            
            status = tool.get_task_status(task_id)
            return status
            
        except Exception as e:
            logger.error(f"[ProcessoAdmService] Erro ao verificar status da task: {e}", exc_info=True)
            return None
    
    def verificar_tasks_ativas(self, cod_documento):
        """
        Verifica se há tasks ativas para um documento administrativo.
        
        Args:
            cod_documento: Código do documento administrativo
            
        Returns:
            tuple: (has_active_task, task_id, task_status) ou (False, None, None)
        """
        try:
            from celery import current_app
            
            tool = self.get_tool()
            if not hasattr(tool, 'processo_adm_integral_async'):
                return (False, None, None)
            
            cod_documento_str = str(cod_documento)
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
                            task_cod_documento = task_kwargs.get('cod_documento')
                            task_name = str(task.get('name', '') or task.get('task', ''))
                            
                            task_cod_str = str(task_cod_documento) if task_cod_documento is not None else None
                            
                            if (task_cod_str == cod_documento_str and 
                                'gerar_processo_adm_integral_task' in task_name):
                                return (True, task.get('id'), 'PROGRESS')
            except Exception as e:
                logger.debug(f"[ProcessoAdmService] Erro ao verificar tasks ativas: {e}")
            
            # Verifica tasks reservadas
            try:
                reserved = inspect.reserved()
                if reserved:
                    for worker, tasks in reserved.items():
                        if not tasks:
                            continue
                        for task in (tasks if isinstance(tasks, list) else [tasks]):
                            task_kwargs = task.get('kwargs', {})
                            task_cod_documento = task_kwargs.get('cod_documento')
                            task_name = str(task.get('name', '') or task.get('task', ''))
                            
                            task_cod_str = str(task_cod_documento) if task_cod_documento is not None else None
                            
                            if (task_cod_str == cod_documento_str and 
                                'gerar_processo_adm_integral_task' in task_name):
                                return (True, task.get('id'), 'PENDING')
            except Exception as e:
                logger.debug(f"[ProcessoAdmService] Erro ao verificar tasks reservadas: {e}")
            
        except Exception as e:
            logger.debug(f"[ProcessoAdmService] Erro ao verificar tasks ativas: {e}")
        
        return (False, None, None)
