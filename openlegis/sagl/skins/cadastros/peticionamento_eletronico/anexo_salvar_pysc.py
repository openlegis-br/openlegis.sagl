##bind script=script
##parameters=hdn_cod_peticao, modal=1, cod_usuario_corrente=None, hdn_url=None
REQUEST = container.REQUEST
RESPONSE = REQUEST.RESPONSE

def is_iterable_not_string(obj):
    try:
        iter(obj)
        if hasattr(obj, 'strip'):
            return False
        return True
    except Exception:
        return False

def as_list(val):
    if not val:
        return []
    if hasattr(val, 'read'):
        return [val]
    if is_iterable_not_string(val):
        try:
            return list(val)
        except Exception:
            return [val]
    return [val]

arquivos = as_list(REQUEST.get('file_nom_anexo'))
tipos = as_list(REQUEST.get('lst_tip_documento'))
descricoes = as_list(REQUEST.get('txt_descricao_anexo'))

msgs = []
sucesso = False

total = min(len(arquivos), len(tipos), len(descricoes))

if total == 0:
    msgs.append("Nenhum arquivo foi enviado.")
else:
    for i in range(total):
        arquivo = arquivos[i]
        tipo = tipos[i]
        descricao = descricoes[i]

        nome_arquivo = getattr(arquivo, 'filename', '')
        if not nome_arquivo:
            nome_arquivo = getattr(arquivo, 'name', '') or str(arquivo)

        if not nome_arquivo or nome_arquivo.lower() in ('undefined', 'none'):
            msgs.append(f"Arquivo {i+1}: sem arquivo selecionado.")
            continue

        if not tipo or not descricao:
            msgs.append(f"Arquivo {i+1}: tipo ou descrição faltando.")
            continue

        try:
            nom_arquivo = container.pysc.anexo_peticao_pysc(hdn_cod_peticao, nomear=True)
            arquivo_up = container.pysc.upload_file(file=arquivo, title=descricao)
            container.sapl_documentos.peticao.manage_addFile(id=nom_arquivo, file=arquivo_up, title=descricao)
            anexo = getattr(container.sapl_documentos.peticao, nom_arquivo)
            anexo.manage_addProperty('tip_documento', tipo, 'string')
            sucesso = True
            msgs.append(f"(OK) Arquivo {nome_arquivo} foi salvo como {descricao}")
        except Exception as e:
            msgs.append(f"(ERRO) Erro ao salvar arquivo {nome_arquivo}: {str(e)}")

if sucesso:
    mensagem = "Documento(s) salvo(s) com sucesso!"
    tipo_mensagem = "success"
else:
    mensagem = "Nenhum anexo foi salvo! Preencha todos os campos obrigatórios."
    tipo_mensagem = "danger"
    if not msgs:
        msgs.append("Tente novamente.")

# Junta mensagens com quebras reais de linha CR+LF
mensagem_obs_text = '\n'.join(msgs)  # Usa \n em vez de <br>

def url_escape(val):
    if not val:
        return ''
    return (str(val)
        .replace(' ', '+')
        .replace('&', '%26')
        .replace('?', '%3F')
        .replace('=', '%3D')
        .replace('#', '%23')
        .replace('/', '%2F'))

url = (
    container.portal_url() +
    '/cadastros/peticionamento_eletronico/peticao_mostrar_proc?cod_peticao=' +
    str(hdn_cod_peticao) + '&modal=1#docs'
)

redirect_url = (
    container.portal_url() +
    '/mensagem_emitir?modal=1'
    '&tipo_mensagem=' + url_escape(tipo_mensagem) +
    '&mensagem=' + url_escape(mensagem) +
    '&mensagem_obs=' + url_escape(mensagem_obs_text.replace('\n', '%0A')) +  # \n → %0A
    '&url=' + url_escape(url)
)

RESPONSE.redirect(redirect_url)
return
