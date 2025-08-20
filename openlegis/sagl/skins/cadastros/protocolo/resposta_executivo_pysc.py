## Script (Python) "resposta_executivo_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_materia_respondida, cod_unid_tram_local=None, cod_unid_tram_dest=None, cod_status=None
##title=
# -*- coding: utf-8 -*-
import json
from DateTime import DateTime

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE
session = REQUEST.SESSION

usuario = REQUEST['AUTHENTICATED_USER'].getUserName()

# =============================================================================
# Defaults (ajuste conforme seu fluxo)
# =============================================================================
DEFAULT_LOCAL = 37
DEFAULT_DEST  = 72
DEFAULT_STATUS = 43

# =============================================================================
# Utilitários
# =============================================================================

def coerce_int(v, default=None):
    """Converte para int com fallback."""
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default

def now_str(fmt="%d/%m/%Y %H:%M:%S"):
    """Data/hora formatada para exibição (humana)."""
    return DateTime(datefmt="international").strftime(fmt)

def now_iso():
    """Data/hora para banco (ISO)."""
    return DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

def retornar_erro(msg):
    """Monta e retorna um JSON de erro padronizado."""
    payload = [{
        'status': 'ERRO',
        'mensagem': msg,
        'usuario': usuario,
        'ip_origem': context.pysc.get_ip(),
        'data': now_str(),
    }]
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return json.dumps(payload)

def parse_num_protocolo(num_protocolo_str):
    """
    Recebe algo como '123/2025' ou '123' e retorna o inteiro 123.
    Se não der para converter, retorna None.
    """
    if not num_protocolo_str:
        return None
    s = str(num_protocolo_str).strip()
    if '/' in s:
        s = s.split('/', 1)[0]
    try:
        return int(s)
    except Exception:
        return None

# =============================================================================
# Matéria / Ementa
# =============================================================================

def obter_materia(cod_materia):
    """
    Monta a identificação da matéria para usar como ementa do documento.
    Retorna string com ementa ou None se a matéria não existir.
    """
    for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia):
        autoria = ''
        # primeira autoria válida (se houver)
        for autor in context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia, ind_excluido=0):
            autoria = getattr(autor, 'nom_autor_join', '') or ''
            break

        sgl = getattr(materia, 'sgl_tipo_materia', '') or ''
        num = getattr(materia, 'num_ident_basica', '') or ''
        ano = getattr(materia, 'ano_ident_basica', '') or ''
        partes = ['Resposta -', sgl, f"{num}/{ano}"]
        if autoria:
            partes.append('- ' + autoria)
        return ' '.join([p for p in partes if p])

    # não encontrou nenhuma matéria
    return None

# =============================================================================
# Protocolo
# =============================================================================

def numero_protocolo():
    """Obtém o número/código de protocolo conforme configuração (anual ou sequencial)."""
    try:
        anual = int(getattr(context.sapl_documentos.props_sagl, 'numero_protocolo_anual', 0) or 0)
    except Exception:
        anual = 0

    if anual == 1:
        for numero in context.zsql.protocolo_numero_obter_zsql(
            ano_protocolo=DateTime(datefmt='international').strftime('%Y')
        ):
            return int(numero.novo_numero)
    else:
        for numero in context.zsql.protocolo_codigo_obter_zsql():
            return int(numero.novo_codigo)
    # fallback (não deveria ocorrer)
    return 1

def criar_protocolo(cod_materia, txt_ementa):
    """Cria o protocolo legislativo e delega para criação do documento acessório."""
    login_usuario = ''
    cod_usuario = None
    for u in context.zsql.usuario_obter_zsql(col_username=REQUEST['AUTHENTICATED_USER'].getUserName()):
        if getattr(u, 'cod_usuario', None):
            login_usuario = getattr(u, 'col_username', '') or REQUEST['AUTHENTICATED_USER'].getUserName()
            cod_usuario = u.cod_usuario
            break

    cod_autor = None
    nome_autor = ''
    for item in context.zsql.autor_obter_zsql(col_username=REQUEST['AUTHENTICATED_USER'].getUserName()):
        cod_autor = getattr(item, 'cod_autor', None)
        nome_autor = getattr(item, 'nom_autor_join', '') or ''
        break

    # Define o tipo de documento: tenta "Resposta", senão fallback 9
    tip_doc = 9
    try:
        for tipo_doc in context.zsql.tipo_documento_obter_zsql(ind_excluido=0):
            nome_tipo = (getattr(tipo_doc, 'des_tipo_documento', '') or '').strip().lower()
            if nome_tipo == 'resposta':
                tip_doc = int(tipo_doc.tip_documento)
                break
    except Exception:
        pass

    num_prot_int = numero_protocolo()

    context.zsql.protocolo_legislativo_incluir_zsql(
        num_protocolo=num_prot_int,
        tip_protocolo=0,
        tip_processo=1,
        tip_natureza_materia=3,
        tip_materia=tip_doc,
        cod_materia_principal=cod_materia,
        txt_assunto_ementa=txt_ementa,
        cod_autor=cod_autor,
        txt_user_protocolo=login_usuario,
        txt_observacao=context.pysc.get_ip()
    )

    # pega o último protocolo incluído
    cod_protocolo = None
    for codigo in context.zsql.protocolo_incluido_codigo_obter_zsql():
        cod_protocolo = int(codigo.cod_protocolo)
        break

    # monta num_protocolo "N/AAAA" para exibição
    num_protocolo = ''
    if cod_protocolo is not None:
        for protocolo in context.zsql.protocolo_obter_zsql(cod_protocolo=cod_protocolo):
            num_protocolo = f"{protocolo.num_protocolo}/{protocolo.ano_protocolo}"
            break

    return criar_documento(
        tip_doc=tip_doc,
        txt_ementa=txt_ementa,
        nome_autor=nome_autor,
        cod_materia=cod_materia,
        cod_protocolo=cod_protocolo,
        num_protocolo=num_protocolo,
        cod_usuario=cod_usuario
    )

# =============================================================================
# Documento Acessório
# =============================================================================

def criar_documento(tip_doc, txt_ementa, nome_autor, cod_materia, cod_protocolo, num_protocolo, cod_usuario):
    """Cria Documento Acessório (anexa PDF) e lança tramitação."""
    # Converte num_protocolo para inteiro (o método ZSQL espera int)
    num_protocolo_int = parse_num_protocolo(num_protocolo)

    # Monta kwargs para evitar enviar valores inválidos
    kwargs = dict(
        tip_documento=tip_doc,
        nom_documento=txt_ementa,
        nom_autor_documento=nome_autor,
        cod_materia=cod_materia,
        dat_documento=now_iso(),
        ind_publico=1,
    )
    # Só envia num_protocolo se for inteiro válido
    if num_protocolo_int is not None:
        kwargs['num_protocolo'] = num_protocolo_int

    context.zsql.documento_acessorio_incluir_zsql(**kwargs)

    cod_documento = None
    for codigo in context.zsql.documento_acessorio_incluido_codigo_obter_zsql():
        cod_documento = int(codigo.cod_documento)
        break

    if cod_documento is not None:
        id_documento = f"{cod_documento}.pdf"
        # só tenta anexar se veio arquivo
        file_obj = None
        try:
            if hasattr(REQUEST, 'form'):
                file_obj = REQUEST.form.get('file') or REQUEST.form.get('arquivo')
        except Exception:
            file_obj = None

        if file_obj:
            context.sapl_documentos.materia.manage_addFile(id=id_documento, file=file_obj)

        if getattr(context, 'dbcon_logs', False):
            context.zsql.logs_registrar_zsql(
                usuario=REQUEST['AUTHENTICATED_USER'].getUserName(),
                data=now_iso(),
                modulo='documento_acessorio_materia',
                metodo='resposta_executivo_pysc',
                cod_registro=cod_documento,
                IP=context.pysc.get_ip()
            )

    return tramitar_materia(
        cod_documento=cod_documento,
        cod_materia=cod_materia,
        cod_protocolo=cod_protocolo,
        num_protocolo=num_protocolo,  # segue como string "N/AAAA" apenas para exibição
        cod_usuario=cod_usuario
    )

# =============================================================================
# Tramitação (parametrizável)
# =============================================================================

def resolver_parametros_tramitacao():
    """
    Resolve os parâmetros de tramitação a partir de:
    1) parâmetros do script,
    2) REQUEST (querystring/form),
    3) defaults do sistema.
    """
    # parâmetros do script
    p_local = coerce_int(cod_unid_tram_local)
    p_dest  = coerce_int(cod_unid_tram_dest)
    p_stat  = coerce_int(cod_status)

    # REQUEST (aceita tanto em form quanto querystring)
    r_local = coerce_int(REQUEST.get('cod_unid_tram_local'))
    r_dest  = coerce_int(REQUEST.get('cod_unid_tram_dest'))
    r_stat  = coerce_int(REQUEST.get('cod_status'))

    final_local = p_local if p_local is not None else (r_local if r_local is not None else DEFAULT_LOCAL)
    final_dest  = p_dest  if p_dest  is not None else (r_dest  if r_dest  is not None else DEFAULT_DEST)
    final_stat  = p_stat  if p_stat  is not None else (r_stat  if r_stat  is not None else DEFAULT_STATUS)

    return final_local, final_dest, final_stat

def tramitar_materia(cod_documento, cod_materia, cod_protocolo, num_protocolo, cod_usuario):
    """Finaliza a última tramitação, registra recebimento e cria nova tramitação padrão."""
    # Resolve parâmetros antes de qualquer operação que dependa do status
    local_id, dest_id, stat_id = resolver_parametros_tramitacao()

    # encerra a "última" e registra recebimento
    for tr in context.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, ind_ult_tramitacao=1, ind_excluido=0):
        context.zsql.tramitacao_ind_ultima_atualizar_zsql(
            cod_materia=cod_materia,
            cod_tramitacao=tr.cod_tramitacao,
            ind_ult_tramitacao=0
        )
        if cod_usuario is not None:
            context.zsql.tramitacao_registrar_recebimento_zsql(
                cod_tramitacao=tr.cod_tramitacao,
                cod_usuario_corrente=cod_usuario
            )
        # Atualiza indicador de "recebido" (se aplicável ao seu fluxo)
        try:
            context.pysc.atualiza_indicador_tramitacao_materia_pysc(
                cod_materia=tr.cod_materia,
                cod_status=stat_id
            )
        except Exception:
            pass
        break  # somente a atual/última

    hr_tramitacao = now_str()
    txt_tramitacao = (
        '<p>Resposta eletrônica recebida em '
        + hr_tramitacao
        + ' sob protocolo nº '
        + (num_protocolo or '')
        + '</p>'
    )

    context.zsql.tramitacao_incluir_zsql(
        cod_materia=cod_materia,
        dat_tramitacao=now_iso(),
        cod_unid_tram_local=local_id,
        cod_usuario_local=cod_usuario,
        cod_unid_tram_dest=dest_id,
        dat_encaminha=now_iso(),
        cod_status=stat_id,
        ind_urgencia=0,
        txt_tramitacao=txt_tramitacao,
        ind_ult_tramitacao=1
    )

    # notifica e gera PDF da tramitação atual
    for tr in context.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, ind_ult_tramitacao=1, ind_excluido=0):
        try:
            context.pysc.envia_tramitacao_autor_pysc(cod_materia=cod_materia)
        except Exception:
            pass
        try:
            context.pysc.envia_acomp_materia_pysc(cod_materia=cod_materia)
        except Exception:
            pass

        hdn_url = context.portal_url() + ''
        try:
            context.relatorios.pdf_tramitacao_preparar_pysc(
                hdn_cod_tramitacao=tr.cod_tramitacao,
                hdn_url=hdn_url
            )
        except Exception:
            pass

        if getattr(context, 'dbcon_logs', False):
            context.zsql.logs_registrar_zsql(
                usuario=REQUEST['AUTHENTICATED_USER'].getUserName(),
                data=now_iso(),
                modulo='tramitacao_materia',
                metodo='resposta_executivo_pysc',
                cod_registro=tr.cod_tramitacao,
                IP=context.pysc.get_ip()
            )
        break

    return criar_resposta(cod_protocolo=cod_protocolo, num_protocolo=num_protocolo)

# =============================================================================
# Resposta final (JSON)
# =============================================================================

def criar_resposta(cod_protocolo, num_protocolo):
    """Retorno JSON final para o cliente."""
    resposta = [{
        'status': 'SUCESSO',
        'usuario': usuario,
        'numero_protocolo': str(num_protocolo or ''),
        'codigo': str(cod_protocolo or ''),
        'data_protocolo': now_str(),
        'ip_origem': context.pysc.get_ip(),
    }]
    retorno = json.dumps(resposta)
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return retorno

# =============================================================================
# Entrada principal
# =============================================================================

txt_ementa = obter_materia(cod_materia_respondida)
if not txt_ementa:
    # encerra com mensagem clara se a matéria não existir
    return retornar_erro(f"Matéria {cod_materia_respondida} não encontrada no banco de dados.")

return criar_protocolo(cod_materia_respondida, txt_ementa)
