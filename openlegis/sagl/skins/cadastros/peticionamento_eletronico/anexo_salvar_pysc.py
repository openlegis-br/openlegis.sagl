##bind script=script
##parameters=hdn_cod_peticao, modal=1, cod_usuario_corrente=None, hdn_url=None
import json
from DateTime import DateTime
REQUEST = container.REQUEST
RESPONSE = REQUEST.RESPONSE

# Configura headers para evitar problemas de cache e garantir JSON
RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
RESPONSE.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate')
RESPONSE.setHeader('Pragma', 'no-cache')
RESPONSE.setHeader('Expires', '0')

def is_iterable_not_string(obj):
    try:
        iter(obj)
        return not hasattr(obj, 'strip')
    except Exception:
        return False

def as_list(val):
    if not val:
        return []
    if hasattr(val, 'read'):  # Objeto file
        return [val]
    if is_iterable_not_string(val):
        return list(val)
    return [val]

try:
    # Processa os arquivos de forma mais robusta
    arquivos = as_list(REQUEST.get('file_nom_anexo[]', REQUEST.get('file_nom_anexo')))
    tipos = as_list(REQUEST.get('lst_tip_documento[]', REQUEST.get('lst_tip_documento')))
    descricoes = as_list(REQUEST.get('txt_descricao_anexo[]', REQUEST.get('txt_descricao_anexo')))

    msgs = []
    saved_files = []
    portal_url = container.portal_url()
    redirect_url = f"{portal_url}/cadastros/peticionamento_eletronico/peticao_mostrar_proc?cod_peticao={hdn_cod_peticao}&modal=1#docs"

    if not redirect_url.startswith('http'):
        redirect_url = portal_url + redirect_url

    # Validação básica antes de processar
    if not all([arquivos, tipos, descricoes]):
        msgs.append("Dados de upload incompletos")
        return json.dumps({
            "success": False,
            "message": "Falha na validação",
            "details": msgs,
            "redirect_url": redirect_url,
            "timestamp": DateTime().ISO()
        })

    for i, (arquivo, tipo, descricao) in enumerate(zip(arquivos, tipos, descricoes)):
        try:
            # Gera nome único para o arquivo
            nom_arquivo = container.pysc.anexo_peticao_pysc(hdn_cod_peticao, nomear=True)
            
            # Remove arquivo existente se necessário
            if hasattr(container.sapl_documentos.peticao, nom_arquivo):
                container.sapl_documentos.peticao.manage_delObjects([nom_arquivo])
            
            # Faz upload e salva o arquivo
            arquivo_up = container.pysc.upload_file(file=arquivo, title=descricao)
            container.sapl_documentos.peticao.manage_addFile(
                id=nom_arquivo, 
                file=arquivo_up, 
                title=descricao,
                content_type='application/pdf'
            )
            
            # Adiciona propriedade do tipo
            anexo = getattr(container.sapl_documentos.peticao, nom_arquivo)
            anexo.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
            anexo.manage_addProperty('tip_documento', tipo, 'string')
            
            saved_files.append(nom_arquivo)
            msgs.append(f"Arquivo {i+1} salvo com sucesso: {descricao}")
            
        except Exception as e:
            # Rollback em caso de erro
            for f in saved_files:
                try:
                    container.sapl_documentos.peticao.manage_delObjects([f])
                except:
                    pass
                    
            return json.dumps({
                "success": False,
                "message": f"Erro ao processar arquivo {i+1}",
                "details": [str(e)],
                "redirect_url": redirect_url,
                "timestamp": DateTime().ISO()
            })

    # Resposta de sucesso
    return json.dumps({
        "success": True,
        "message": "Todos os arquivos foram salvos",
        "details": msgs,
        "redirect_url": redirect_url,
        "timestamp": DateTime().ISO()
    })

except Exception as e:   
    return json.dumps({
        "success": False,
        "message": "Erro interno no servidor",
        "details": [str(e)],
        "redirect_url": f"{container.portal_url()}/cadastros/peticionamento_eletronico/peticao_mostrar_proc?cod_peticao={hdn_cod_peticao}&modal=1#docs",
        "timestamp": DateTime().ISO()
    })
