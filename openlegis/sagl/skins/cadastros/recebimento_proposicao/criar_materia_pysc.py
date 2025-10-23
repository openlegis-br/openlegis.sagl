## Script (Python) "criar_materia_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_proposicao, modo_api=None, data_apresentacao=None
##title=
from Products.CMFCore.utils import getToolByName
from DateTime import DateTime
import json

utool = getToolByName(context, 'portal_url')
portal = utool.getPortalObject()
REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

def agora_dt():
    return DateTime(datefmt='international')

def agora_iso():
    return agora_dt().strftime('%Y-%m-%d %H:%M:%S')

def ano_corrente():
    return agora_dt().strftime('%Y')

def formatar_data_apresentacao(valor):
    if not valor:
        dt = agora_dt()
    else:
        try:
            dt = DateTime(str(valor), datefmt='international')
        except:
            dt = agora_dt()
    return "%04d-%02d-%02d" % (dt.year(), dt.month(), dt.day())

def resposta_api(sucesso, status, mensagem, **kwargs):
    payload = {
        'sucesso': bool(sucesso),
        'status': status,
        'mensagem': mensagem
    }
    payload.update(kwargs)
    if modo_api == 'json':
        RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(payload, ensure_ascii=False)
    return payload

def redirect_msg(tipo, mensagem, mensagem_obs):
    url = context.portal_url() + '/mensagem_emitir?tipo_mensagem={}&mensagem={}&mensagem_obs={}'.format(
        tipo, mensagem, mensagem_obs
    )
    RESPONSE.redirect(url)

# ---------------- INÍCIO ----------------

rows_prop = context.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao, ind_mat_ou_doc='M')
if not rows_prop:
    msg = 'Proposição não encontrada.'
    if modo_api:
        return resposta_api(False, 'nao_encontrada', msg, cod_proposicao=cod_proposicao)
    return redirect_msg('danger', msg, 'Verifique o código informado.')

proposicao = rows_prop[0]

# Metadados básicos
des_tipo_proposicao = getattr(proposicao, 'des_tipo_proposicao', None)
tip_materia = proposicao.tip_mat_ou_doc
ano_materia = ano_corrente()
cod_mat = proposicao.cod_mat_ou_doc
dat_envio = getattr(proposicao, 'dat_envio', None)
dat_solicitacao_devolucao = getattr(proposicao, 'dat_solicitacao_devolucao', None)
dat_devolucao = getattr(proposicao, 'dat_devolucao', None)
txt_ementa = getattr(proposicao, 'txt_descricao', '') or ''
txt_observacao = getattr(proposicao, 'txt_observacao', '') or ''
cod_autor = proposicao.cod_autor

# Data de apresentação
dat_apresentacao = formatar_data_apresentacao(data_apresentacao)

# Tipo da matéria (defensivo)
des_tipo_materia = None
rows_tipomat = context.zsql.tipo_materia_legislativa_obter_zsql(tip_materia=tip_materia)
if rows_tipomat:
    des_tipo_materia = rows_tipomat[0].des_tipo_materia
else:
    des_tipo_materia = 'Matéria'

# Regras de quórum
if des_tipo_materia == 'Projeto de Lei Complementar':
    tip_quorum = 3
    ind_complementar = 1
else:
    tip_quorum = 1
    ind_complementar = 0

# Tipo do autor (defensivo)
des_tipo_autor = 'Outro'
rows_autor = context.zsql.autor_obter_zsql(cod_autor=cod_autor)
if rows_autor:
    des_tipo_autor = rows_autor[0].des_tipo_autor

# Numeração da matéria (defensivo)
num_ident_basica = None
rows_num = context.zsql.numero_materia_legislativa_obter_zsql(
    tip_id_basica_sel=tip_materia, ano_ident_basica=ano_materia, ind_excluido=0
)
if rows_num:
    num_ident_basica = rows_num[0].novo_numero
else:
    # fallback (evita crash; sua stored procedure deve ser a fonte de verdade)
    num_ident_basica = 1

def criar_protocolo(tip_materia, num_ident_basica, ano_materia, dat_apresentacao, txt_ementa, txt_observacao, cod_autor, tip_quorum, ind_complementar, cod_proposicao):
    # Número/código do protocolo (anual ou sequencial)
    if int(getattr(context.sapl_documentos.props_sagl, 'numero_protocolo_anual', 1)) == 1:
        rows = context.zsql.protocolo_numero_obter_zsql(ano_protocolo=ano_corrente())
        if not rows:
            raise Exception('Falha ao obter número de protocolo (anual).')
        hdn_num_protocolo = int(rows[0].novo_numero)
    else:
        rows = context.zsql.protocolo_codigo_obter_zsql()
        if not rows:
            raise Exception('Falha ao obter código de protocolo (sequencial).')
        hdn_num_protocolo = int(rows[0].novo_codigo)

    txt_user = REQUEST['AUTHENTICATED_USER'].getUserName()
    context.zsql.protocolo_legislativo_incluir_zsql(
        num_protocolo=hdn_num_protocolo,
        tip_protocolo=0,
        tip_processo=1,
        tip_materia=tip_materia,
        tip_natureza_materia=1,
        txt_assunto_ementa=txt_ementa,
        cod_autor=cod_autor,
        txt_user_protocolo=txt_user
    )

    rows_cod = context.zsql.protocolo_incluido_codigo_obter_zsql()
    if not rows_cod:
        raise Exception('Falha ao recuperar código do protocolo recém-incluído.')
    cod_prot = int(rows_cod[0].cod_protocolo)

    return criar_materia(
        hdn_num_protocolo, tip_materia, num_ident_basica, ano_materia, dat_apresentacao,
        txt_ementa, txt_observacao, cod_autor, tip_quorum, ind_complementar, cod_proposicao
    )

def criar_materia(hdn_num_protocolo, tip_materia, num_ident_basica, ano_materia, dat_apresentacao, txt_ementa, txt_observacao, cod_autor, tip_quorum, ind_complementar, cod_proposicao):
    context.zsql.materia_incluir_zsql(
        tip_id_basica=tip_materia,
        num_ident_basica=num_ident_basica,
        ano_ident_basica=ano_materia,
        dat_apresentacao=dat_apresentacao,
        num_protocolo=hdn_num_protocolo,
        tip_apresentacao='E',
        tip_quorum=tip_quorum,
        ind_tramitacao=1,
        ind_complementar=ind_complementar,
        cod_regime_tramitacao=1,
        txt_ementa=txt_ementa
    )
    rows_cod = context.zsql.materia_incluida_codigo_obter_zsql()
    if not rows_cod:
        raise Exception('Falha ao recuperar código da matéria recém-incluída.')
    cod_materia = int(rows_cod[0].cod_materia)

    if getattr(context, 'dbcon_logs', None):
        try:
            context.zsql.logs_registrar_zsql(
                usuario=REQUEST['AUTHENTICATED_USER'].getUserName(),
                data=agora_iso(),
                modulo='materia',
                metodo='materia_incluir_zsql',
                cod_registro=cod_materia,
                IP=context.pysc.get_ip()
            )
        except:
            # logging não deve impedir o fluxo principal
            pass

    return inserir_autoria(cod_materia, cod_autor, cod_proposicao, hdn_num_protocolo)

def inserir_autoria(cod_materia, cod_autor, cod_proposicao, hdn_num_protocolo):
    # Primeiro autor
    context.zsql.autoria_incluir_zsql(
        cod_autor=cod_autor, cod_materia=cod_materia, ind_primeiro_autor=1
    )

    # Demais autores a partir de assinaturas, se houver
    if context.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao, tipo_doc='proposicao', ind_assinado=1):
        for assinatura in context.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao, tipo_doc='proposicao', ind_assinado=1):
            for usuario in context.zsql.usuario_obter_zsql(cod_usuario=assinatura.cod_usuario, ind_excluido=0):
                for autor in context.zsql.autor_obter_zsql(col_username=usuario.col_username, ind_excluido=0):
                    if int(cod_autor) != int(autor.cod_autor):
                        context.zsql.autoria_incluir_zsql(
                            cod_autor=autor.cod_autor, cod_materia=cod_materia, ind_primeiro_autor=0
                        )
    return copiar_destinatarios(cod_materia, cod_proposicao, hdn_num_protocolo)

def copiar_destinatarios(cod_materia, cod_proposicao, hdn_num_protocolo):
    for item in context.zsql.destinatario_oficio_obter_zsql(cod_proposicao=cod_proposicao):
        context.zsql.destinatario_oficio_incluir_zsql(
            cod_materia=cod_materia, nom_destinatario=item.nom_destinatario, end_email=item.end_email
        )
    return tramitar_materia(cod_materia, cod_proposicao, hdn_num_protocolo)

def tramitar_materia(cod_materia, cod_proposicao, hdn_num_protocolo):
    props = context.sapl_documentos.props_sagl
    cod_unid_tram_local = int(getattr(props, 'origem', 0) or 0)

    if des_tipo_materia in ['Requerimento', 'Indicação', 'Moção', 'Pedido de Informação']:
        cod_unid_tram_dest = int(getattr(props, 'destino_outros', 0) or 0)
    else:
        cod_unid_tram_dest = int(getattr(props, 'destino', 0) or 0)

    cod_status = int(getattr(props, 'status', 0) or 0)

    rows_usuario = context.zsql.usuario_obter_zsql(col_username=REQUEST['AUTHENTICATED_USER'].getUserName())
    if rows_usuario:
        cod_usuario_corrente = int(rows_usuario[0].cod_usuario or 0)
    else:
        cod_usuario_corrente = 0

    hr_tramitacao = agora_dt().strftime('%d/%m/%Y %H:%M:%S')
    txt_tramitacao = (
        '<p>Proposição eletrônica enviada em ' + str(dat_envio) +
        '. Matéria incorporada em ' + hr_tramitacao +
        ' sob protocolo nº ' + str(hdn_num_protocolo) + '/' + ano_corrente() + '</p>'
    )
    hdn_url = context.portal_url() + '/cadastros/recebimento_proposicao/recebimento_proposicao_index_html#protocolo'

    context.zsql.tramitacao_incluir_zsql(
        cod_materia=cod_materia,
        dat_tramitacao=agora_iso(),
        cod_unid_tram_local=cod_unid_tram_local,
        cod_usuario_local=cod_usuario_corrente,
        cod_unid_tram_dest=cod_unid_tram_dest,
        dat_encaminha=agora_iso(),
        cod_status=cod_status,
        ind_urgencia=0,
        txt_tramitacao=txt_tramitacao,
        ind_ult_tramitacao=1
    )

    rows_tram = context.zsql.tramitacao_incluida_codigo_obter_zsql()
    cod_tramitacao = rows_tram[0].cod_tramitacao if rows_tram else None

    # Anexa texto integral, se existir ODT
    if hasattr(context.sapl_documentos.proposicao, str(cod_proposicao) + '.odt'):
        context.pysc.proposicao_salvar_como_texto_integral_materia_pysc(cod_proposicao, cod_materia, 0)

    # Marca recebimento da proposição
    context.zsql.proposicao_registrar_recebimento_zsql(
        cod_proposicao=cod_proposicao,
        dat_recebimento=context.pysc.data_atual_iso_pysc(),
        cod_mat_ou_doc=int(cod_materia)
    )

    # Se houver PDF assinado, dispara autuação assíncrona
    if hasattr(context.sapl_documentos.proposicao, str(cod_proposicao) + '_signed.pdf'):
        context.modelo_proposicao.proposicao_autuar_async(cod_proposicao=cod_proposicao)

    # Atualiza catálogo
    try:
        context.sapl_documentos.materia.Catalog.atualizarCatalogo(int(cod_materia))
    except:
        pass

    # Gera PDF de tramitação (se houver código retornado)
    if cod_tramitacao:
        return context.relatorios.pdf_tramitacao_preparar_pysc(hdn_cod_tramitacao=cod_tramitacao, hdn_url=hdn_url)
    return True

# Situações que impedem a incorporação
if cod_mat is not None:
    mensagem = 'Proposição já convertida em matéria legislativa!'
    mensagem_obs = 'Verifique a lista de proposições incorporadas.'
    if modo_api:
        return resposta_api(False, 'ja_incorporada', mensagem, cod_proposicao=proposicao.cod_proposicao, detalhe=mensagem_obs)
    redirect_msg('danger', mensagem, mensagem_obs)
    return

if dat_solicitacao_devolucao is not None:
    mensagem = 'Proposição com devolução solicitada pelo autor!'
    mensagem_obs = 'Verifique a lista das solicitações de devolução.'
    if modo_api:
        return resposta_api(False, 'devolucao_solicitada', mensagem, cod_proposicao=proposicao.cod_proposicao, detalhe=mensagem_obs)
    redirect_msg('danger', mensagem, mensagem_obs)
    return

if dat_devolucao is not None:
    mensagem = 'Proposição devolvida ao autor!'
    mensagem_obs = 'Verifique a lista das proposições devolvidas.'
    if modo_api:
        return resposta_api(False, 'devolvida', mensagem, cod_proposicao=proposicao.cod_proposicao, detalhe=mensagem_obs)
    redirect_msg('danger', mensagem, mensagem_obs)
    return

# BLOQUEIO: exige PDF assinado antes de incorporar
if not hasattr(context.sapl_documentos.proposicao, str(cod_proposicao) + '_signed.pdf'):
    mensagem = 'A proposição ainda não possui arquivo PDF assinado!'
    mensagem_obs = 'É necessário assinar digitalmente a proposição antes da incorporação.'
    if modo_api:
        return resposta_api(False, 'sem_assinatura', mensagem, cod_proposicao=proposicao.cod_proposicao, detalhe=mensagem_obs)
    redirect_msg('danger', mensagem, mensagem_obs)
    return

# Fluxo principal
try:
    criar_protocolo(
        tip_materia, num_ident_basica, ano_materia, dat_apresentacao,
        txt_ementa, txt_observacao, cod_autor, tip_quorum, ind_complementar, proposicao.cod_proposicao
    )
    if modo_api:
        return resposta_api(True, 'incorporada', 'Matéria legislativa incorporada com sucesso.', cod_proposicao=proposicao.cod_proposicao)
except Exception as e:
    if modo_api:
        return resposta_api(False, 'erro', 'Erro inesperado ao incorporar a matéria.', cod_proposicao=proposicao.cod_proposicao, detalhe=str(e))
    raise
