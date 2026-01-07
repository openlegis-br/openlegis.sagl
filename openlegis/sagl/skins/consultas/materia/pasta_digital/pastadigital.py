## Script (Python) "pastadigital"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_materia, action=''
##title=
##

import logging
import traceback

try:
    from Products.CMFCore.utils import getToolByName
    
    utool = getToolByName(context, 'portal_url')
    portal = utool.getPortalObject()
    tool = getToolByName(context, 'portal_sagl')
    
    REQUEST = context.REQUEST
except Exception as init_err:
    # Se falhar na inicialização, retorna erro imediatamente
    error_msg = f"Erro na inicialização do script: {str(init_err)}"
    error_trace = traceback.format_exc()
    logging.error(f"[pastadigital] Erro na inicialização: {error_msg}")
    logging.error(f"[pastadigital] Traceback: {error_trace}")
    # Tenta definir no REQUEST se possível
    try:
        context.REQUEST.set('error_message', error_msg)
        context.REQUEST.set('error_trace', error_trace)
    except:
        pass
    # Retorna erro mesmo sem REQUEST válido
    return {
        'error': error_msg,
        'async': False,
        'documentos': [],
        'error_trace': error_trace
    }

# Verifica se deve usar modo assíncrono
# Por padrão, usa assíncrono para action='pasta'
# Para action='download', verifica primeiro se o arquivo existe no temp_folder
# Se existir, faz download direto. Se não existir, usa modo síncrono para gerar e fazer download
# Pode forçar modo síncrono com async=0 na URL
# Verifica tanto no REQUEST.form quanto no REQUEST.get
async_param = REQUEST.form.get('async')
if async_param is None:
    async_param = REQUEST.get('async', '1')
use_async = str(async_param) != '0'  # Usa assíncrono se não for explicitamente '0'

# Para action='download', chama diretamente o endpoint que faz o download
# Isso garante que o navegador receba o PDF diretamente
if action == 'download':
    try:
        # Chama diretamente o endpoint @@processo_leg_integral que faz o download
        REQUEST.form['cod_materia'] = cod_materia
        REQUEST.form['action'] = action
        view = portal.restrictedTraverse('@@processo_leg_integral')
        result = view()
        # Se o resultado for bytes (PDF), escreve diretamente no RESPONSE
        # Os headers já foram definidos pelo endpoint @@processo_leg_integral
        if isinstance(result, bytes):
            # Não redefine headers, o endpoint já os definiu corretamente
            REQUEST.RESPONSE.write(result)
            return ""  # Retorna vazio após escrever no RESPONSE
        # Se for outro tipo, retorna como está
        return result
    except Exception as e:
        # Se falhar, retorna erro
        error_msg = str(e)
        REQUEST.set('error_message', error_msg)
        return {
            'error': error_msg,
            'async': False,
            'documentos': []
        }

# Para action='pasta', sempre tenta usar modo assíncrono (a menos que async=0)
# Isso garante que o arquivo seja salvo no temp_folder para acesso posterior
if action == 'pasta' and use_async:
    # Modo assíncrono: inicia tarefa e retorna task_id para monitoramento
    try:
        portal_url = str(utool())
        
        # Garante que cod_materia seja um inteiro
        try:
            cod_materia_int = int(cod_materia)
        except (ValueError, TypeError):
            cod_materia_int = cod_materia
            REQUEST.set('async_error', f'cod_materia inválido: {cod_materia}')
            use_async = False
        
        if use_async:
            # Verifica se o método existe e está acessível
            if not hasattr(tool, 'processo_leg_integral_async'):
                error_msg = 'Método processo_leg_integral_async não encontrado'
                REQUEST.set('async_error', error_msg)
                use_async = False
            else:
                try:
                    result = tool.processo_leg_integral_async(cod_materia_int, portal_url)
                    
                    # Debug: log do resultado
                    import logging
                    logging.info(f"[pastadigital] processo_leg_integral_async retornou: {result}, tipo: {type(result)}")
                    
                    # Verifica se o resultado é válido
                    if result is None:
                        error_msg = "processo_leg_integral_async retornou None"
                        logging.error(f"[pastadigital] {error_msg}")
                        REQUEST.set('async_error', error_msg)
                        use_async = False
                    elif not isinstance(result, dict):
                        error_msg = f"Resultado não é um dicionário: {type(result)} - {str(result)[:200]}"
                        logging.error(f"[pastadigital] {error_msg}")
                        REQUEST.set('async_error', error_msg)
                        use_async = False
                    elif 'task_id' not in result:
                        error_msg = f"Resultado não tem 'task_id'. Chaves disponíveis: {list(result.keys())}"
                        logging.error(f"[pastadigital] {error_msg}")
                        REQUEST.set('async_error', error_msg)
                        use_async = False
                    else:
                        task_id = result.get('task_id')
                        if not task_id:
                            error_msg = f"task_id está vazio. Resultado completo: {result}"
                            logging.error(f"[pastadigital] {error_msg}")
                            REQUEST.set('async_error', error_msg)
                            use_async = False
                        else:
                            # Retorna estrutura com task_id para monitoramento
                            # CRÍTICO: Garante que o retorno seja um dicionário simples e serializável
                            # Não armazena debug_result aqui para evitar problemas com eval no DTML
                            try:
                                ret_dict = {
                                    'async': True,
                                    'task_id': str(task_id),  # Garante que seja string
                                    'status': str(result.get('status', 'PENDING')),
                                    'documentos': [],  # Vazio inicialmente - será preenchido quando concluir
                                    'cod_materia': int(cod_materia_int),
                                    'paginas_geral': 0
                                }
                                logging.info(f"[pastadigital] Retornando dicionário: {ret_dict}")
                                return ret_dict
                            except Exception as return_err:
                                # Se falhar ao criar o dicionário de retorno, define erro
                                import traceback
                                error_trace = traceback.format_exc()
                                error_msg = f"Erro ao criar dicionário de retorno: {return_err}"
                                logging.error(f"[pastadigital] {error_msg}")
                                logging.error(f"[pastadigital] Traceback: {error_trace}")
                                REQUEST.set('async_error', error_msg)
                                REQUEST.set('async_error_trace', error_trace)
                                use_async = False
                except Exception as method_err:
                    # Erro ao chamar o método, define erro
                    import traceback
                    error_msg = str(method_err)
                    error_trace = traceback.format_exc()
                    REQUEST.set('async_error', f"Erro ao chamar processo_leg_integral_async: {error_msg}")
                    REQUEST.set('async_error_trace', error_trace)
                    use_async = False
    except Exception as outer_err:
        # Captura qualquer exceção não prevista
        import traceback
        error_msg = str(outer_err)
        error_trace = traceback.format_exc()
        REQUEST.set('async_error', f"Erro inesperado no modo assíncrono: {error_msg}")
        REQUEST.set('async_error_trace', error_trace)
        use_async = False
    
    # Se houve erro no modo assíncrono e action='pasta', retorna erro em vez de tentar modo síncrono
    if action == 'pasta' and not use_async:
        async_error = REQUEST.get('async_error', '')
        if async_error:
            import logging
            async_error_trace = REQUEST.get('async_error_trace', '')
            error_dict = {
                'error': async_error,
                'async': False,
                'documentos': [],
                'error_trace': async_error_trace
            }
            logging.error(f"[pastadigital] Retornando erro: {error_dict}")
            return error_dict
        else:
            # Se não há async_error mas use_async é False, pode ser que não tenha tentado assíncrono
            # Nesse caso, tenta modo síncrono
            import logging
            logging.warning(f"[pastadigital] action='pasta' mas use_async=False e não há async_error. Tentando modo síncrono.")

# Modo síncrono (fallback ou quando async=0)
try:
    REQUEST.form['cod_materia'] = cod_materia
    REQUEST.form['action'] = action
    
    view = portal.restrictedTraverse('@@processo_leg_integral')
    results = view()
    results['async'] = False
    return results
except Exception as e:
    # Retorna erro em vez de levantar exceção
    error_msg = str(e)
    error_type = e.__class__.__name__
    error_trace = traceback.format_exc()
    logging.error(f"[pastadigital] Erro no modo síncrono: {error_msg}")
    logging.error(f"[pastadigital] Traceback: {error_trace}")
    try:
        REQUEST.set('error_message', error_msg)
        REQUEST.set('error_type', error_type)
        REQUEST.set('error_trace', error_trace)
    except:
        pass
    return {
        'error': error_msg,
        'async': False,
        'documentos': [],
        'error_type': error_type,
        'error_trace': error_trace
    }
