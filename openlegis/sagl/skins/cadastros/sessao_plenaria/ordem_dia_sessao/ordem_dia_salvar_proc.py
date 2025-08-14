## Script (Python) "ordem_dia_salvar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=hdn_cod_ordem=None, ind_audiencia=None, cod_sessao_plen=None, txt_num_ordem=None, cod_materia=None, cod_parecer=None, txt_dat_ordem=None, lst_tip_quorum=None, rad_tip_votacao=None, lst_tip_turno=None, rad_urgencia=None, txa_txt_observacao=None, lst_tip_id_basica=None, txt_num_ident_basica=None, txt_ano_ident_basica=None
##title=Salvar item da ordem do dia
##

from DateTime import DateTime

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

def to_str(v):
    if v is None:
        return ''
    return str(v).strip()

def to_unicode(v):
    try:
        return context.pysc.convert_unicode_pysc(texto=to_str(v))
    except:
        return to_str(v)

# Definir método (incluir ou atualizar)
if hdn_cod_ordem:
    metodo = context.zsql.ordem_dia_atualizar_zsql
else:
    metodo = context.zsql.ordem_dia_incluir_zsql

# Sessão plenária (mantido por paridade lógica)
try:
    if ind_audiencia:
        metodo_sessao = context.zsql.sessao_plenaria_obter_zsql(
            cod_sessao_plen=cod_sessao_plen, ind_audiencia=1, ind_excluido=0
        )
    else:
        metodo_sessao = context.zsql.sessao_plenaria_obter_zsql(
            cod_sessao_plen=cod_sessao_plen, ind_excluido=0
        )
except:
    metodo_sessao = []

observacao = to_unicode(txa_txt_observacao)

# Buscar nome do turno (se informado) para mensagens
turno_nome = ''
if lst_tip_turno:
    try:
        turnos = context.zsql.turno_discussao_obter_zsql(cod_turno=lst_tip_turno, ind_excluido=0)
        for t in turnos:
            turno_nome = t.des_turno
            break
    except:
        turno_nome = ''

# ===== 1) Duplicidade do NÚMERO DE ORDEM =====
# (independe de turno)
for sess in metodo_sessao:
    existentes = context.zsql.ordem_dia_obter_zsql(
        num_ordem=txt_num_ordem, cod_sessao_plen=cod_sessao_plen, ind_excluido=0
    )
    if existentes:
        if hdn_cod_ordem:
            conflito_num = 0
            for r in existentes:
                if getattr(r, 'cod_ordem', None) != hdn_cod_ordem:
                    conflito_num = 1
                    break
            if conflito_num:
                mensagem = 'Número de ordem já existe nesta Ordem do Dia!'
                RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=danger&mensagem=' + mensagem)
                return
        else:
            mensagem = 'Número de ordem já existe nesta Ordem do Dia!'
            RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=danger&mensagem=' + mensagem)
            return

# ===== 2) Checar existência da MATÉRIA pelo identificador =====
tem_ident = (lst_tip_id_basica and txt_num_ident_basica and txt_ano_ident_basica)
if cod_materia and tem_ident:
    found = context.zsql.materia_obter_zsql(
        tip_id_basica=lst_tip_id_basica,
        num_ident_basica=txt_num_ident_basica,
        ano_ident_basica=txt_ano_ident_basica,
        ind_excluido=0
    )
    tem_reg = 0
    for m_row in found:
        tem_reg = 1
        break
    if not tem_reg:
        mensagem = 'A matéria informada não existe no cadastro!'
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=danger&mensagem=' + mensagem)
        return

# ===== 3) Duplicidade de MATÉRIA considerando TURNO =====
if cod_materia:
    regs = context.zsql.ordem_dia_obter_zsql(
        cod_materia=cod_materia, cod_sessao_plen=cod_sessao_plen, ind_excluido=0
    )
    conflito_mesmo_turno = 0
    for r in regs:
        mesmo_registro = (hdn_cod_ordem and getattr(r, 'cod_ordem', None) == hdn_cod_ordem)
        if not mesmo_registro:
            if str(getattr(r, 'tip_turno', '')) == str(lst_tip_turno):
                conflito_mesmo_turno = 1
                break
    if conflito_mesmo_turno:
        if turno_nome:
            mensagem = 'A matéria já está cadastrada no turno "%s" nesta Ordem do Dia!' % turno_nome
        else:
            mensagem = 'A matéria já está cadastrada neste turno nesta Ordem do Dia!'
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=danger&mensagem=' + mensagem)
        return

# ===== 4) Duplicidade de PARECER considerando TURNO =====
elif cod_parecer:
    regs = context.zsql.ordem_dia_obter_zsql(
        cod_parecer=cod_parecer, cod_sessao_plen=cod_sessao_plen, ind_excluido=0
    )
    conflito_mesmo_turno_p = 0
    for r in regs:
        mesmo_registro = (hdn_cod_ordem and getattr(r, 'cod_ordem', None) == hdn_cod_ordem)
        if not mesmo_registro:
            if str(getattr(r, 'tip_turno', '')) == str(lst_tip_turno):
                conflito_mesmo_turno_p = 1
                break
    if conflito_mesmo_turno_p:
        if turno_nome:
            mensagem = 'O parecer já está cadastrado no turno "%s" nesta Ordem do Dia!' % turno_nome
        else:
            mensagem = 'O parecer já está cadastrado neste turno nesta Ordem do Dia!'
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=danger&mensagem=' + mensagem)
        return

# ===== 5) Inserção ou atualização =====
if cod_materia:
    try:
        # Data (matéria) com conversor padrão
        try:
            dat_ordem_param = context.pysc.data_converter_pysc(data=txt_dat_ordem)
        except:
            dat_ordem_param = to_str(txt_dat_ordem)

        metodo(
            cod_ordem       = hdn_cod_ordem,
            cod_sessao_plen = cod_sessao_plen,
            cod_materia     = cod_materia,
            dat_ordem       = dat_ordem_param,
            num_ordem       = txt_num_ordem,
            tip_votacao     = rad_tip_votacao,
            tip_quorum      = lst_tip_quorum,
            tip_turno       = lst_tip_turno,
            urgencia        = rad_urgencia,
            txt_observacao  = to_unicode(txa_txt_observacao)
        )
        mensagem = 'Matéria salva com sucesso na Ordem do Dia!'
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=success&mensagem=' + mensagem)
        return
    except:
        mensagem = 'Não foi possível salvar a matéria na Ordem do Dia! Tente novamente.'
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=danger&mensagem=' + mensagem)
        return

if cod_parecer:
    try:
        # Data (parecer) no formato original: YYYY/%m/%d
        if txt_dat_ordem:
            dat_ordem_param = DateTime(txt_dat_ordem, datefmt='international').strftime('%Y/%m/%d')
        else:
            dat_ordem_param = None

        metodo(
            cod_ordem       = hdn_cod_ordem,
            cod_sessao_plen = cod_sessao_plen,
            cod_parecer     = cod_parecer,
            dat_ordem       = dat_ordem_param,
            num_ordem       = txt_num_ordem,
            tip_votacao     = rad_tip_votacao,
            tip_quorum      = lst_tip_quorum,
            tip_turno       = lst_tip_turno,
            urgencia        = rad_urgencia,
            txt_observacao  = to_unicode(txa_txt_observacao)
        )
        mensagem = 'Parecer salvo com sucesso na Ordem do Dia!'
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=success&mensagem=' + mensagem)
        return
    except:
        mensagem = 'Não foi possível salvar o parecer na Ordem do Dia! Tente novamente.'
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=danger&mensagem=' + mensagem)
        return

# Nem matéria nem parecer informados
mensagem = 'Informe uma matéria ou um parecer para incluir na Ordem do Dia.'
RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?modal=1&tipo_mensagem=warning&mensagem=' + mensagem)
