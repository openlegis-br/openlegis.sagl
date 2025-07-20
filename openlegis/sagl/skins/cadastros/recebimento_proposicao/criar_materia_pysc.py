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
import datetime

utool = getToolByName(context, 'portal_url')
portal = utool.getPortalObject()
REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

def resposta_api(sucesso, status, mensagem, **kwargs):
    resp = {
        'sucesso': bool(sucesso),
        'status': status,
        'mensagem': mensagem
    }
    resp.update(kwargs)
    return resp

for proposicao in context.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao, ind_mat_ou_doc='M'):
    cod_proposicao = proposicao.cod_proposicao
    des_tipo_proposicao = proposicao.des_tipo_proposicao
    tip_materia = proposicao.tip_mat_ou_doc
    for tipomat in context.zsql.tipo_materia_legislativa_obter_zsql(tip_materia=proposicao.tip_mat_ou_doc):
        des_tipo_materia = tipomat.des_tipo_materia
    ano_materia = DateTime(datefmt='international').strftime("%Y")
    cod_mat = proposicao.cod_mat_ou_doc

    if data_apresentacao:
        try:
            dt = DateTime(str(data_apresentacao), datefmt='international')
        except:
            dt = DateTime(datefmt='international')
    else:
        dt = DateTime(datefmt='international')

    dat_apresentacao = "%04d-%02d-%02d" % (dt.year(), dt.month(), dt.day())

    dat_envio = proposicao.dat_envio
    dat_solicitacao_devolucao = proposicao.dat_solicitacao_devolucao
    dat_devolucao = proposicao.dat_devolucao
    txt_ementa = proposicao.txt_descricao
    txt_observacao = proposicao.txt_observacao
    cod_autor = proposicao.cod_autor

    if des_tipo_materia == 'Projeto de Lei Complementar':
        tip_quorum = 3
        ind_complementar = 1
    else:
        tip_quorum = 1
        ind_complementar = 0

    for autor in context.zsql.autor_obter_zsql(cod_autor=proposicao.cod_autor):
        des_tipo_autor = autor.des_tipo_autor

    for numero in context.zsql.numero_materia_legislativa_obter_zsql(tip_id_basica_sel=proposicao.tip_mat_ou_doc, ano_ident_basica=ano_materia, ind_excluido=0):
        num_ident_basica = numero.novo_numero

    def criar_protocolo(tip_materia, num_ident_basica, ano_materia, dat_apresentacao, txt_ementa, txt_observacao, cod_autor, tip_quorum, ind_complementar, cod_proposicao):
        if context.sapl_documentos.props_sagl.numero_protocolo_anual == 1:
            for numero in context.zsql.protocolo_numero_obter_zsql(ano_protocolo=DateTime(datefmt='international').strftime('%Y')):
                hdn_num_protocolo = int(numero.novo_numero)
        else:
            for numero in context.zsql.protocolo_codigo_obter_zsql():
                hdn_num_protocolo = int(numero.novo_codigo)
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
        for codigo in context.zsql.protocolo_incluido_codigo_obter_zsql():
            cod_prot = int(codigo.cod_protocolo)
        return criar_materia(
            hdn_num_protocolo, tip_materia, num_ident_basica, ano_materia, dat_apresentacao, txt_ementa,
            txt_observacao, cod_autor, tip_quorum, ind_complementar, cod_proposicao
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
        for codigo in context.zsql.materia_incluida_codigo_obter_zsql():
            cod_materia = int(codigo.cod_materia)
        if context.dbcon_logs:
            context.zsql.logs_registrar_zsql(
                usuario=REQUEST['AUTHENTICATED_USER'].getUserName(),
                data=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                modulo='materia',
                metodo='materia_incluir_zsql',
                cod_registro=cod_materia,
                IP=context.pysc.get_ip()
            )
        return inserir_autoria(cod_materia, cod_autor, cod_proposicao, hdn_num_protocolo)

    def inserir_autoria(cod_materia, cod_autor, cod_proposicao, hdn_num_protocolo):
        if des_tipo_autor == 'Parlamentar':
            context.zsql.autoria_incluir_zsql(
                cod_autor=cod_autor, cod_materia=cod_materia, ind_primeiro_autor=1
            )
            if context.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao, tipo_doc='proposicao', ind_assinado=1):
                for assinatura in context.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao, tipo_doc='proposicao', ind_assinado=1):
                    for usuario in context.zsql.usuario_obter_zsql(cod_usuario=assinatura.cod_usuario, ind_excluido=0):
                        for autor in context.zsql.autor_obter_zsql(col_username=usuario.col_username, ind_excluido=0):
                            if int(cod_autor) != int(autor.cod_autor):
                                context.zsql.autoria_incluir_zsql(
                                    cod_autor=autor.cod_autor, cod_materia=cod_materia, ind_primeiro_autor=0
                                )
        else:
            context.zsql.autoria_incluir_zsql(
                cod_autor=cod_autor, cod_materia=cod_materia, ind_primeiro_autor=1
            )
        return copiar_destinatarios(cod_materia, cod_proposicao, hdn_num_protocolo)

    def copiar_destinatarios(cod_materia, cod_proposicao, hdn_num_protocolo):
        for item in context.zsql.destinatario_oficio_obter_zsql(cod_proposicao=cod_proposicao):
            context.zsql.destinatario_oficio_incluir_zsql(
                cod_materia=cod_materia, nom_destinatario=item.nom_destinatario, end_email=item.end_email
            )
        return tramitar_materia(cod_materia, cod_proposicao, hdn_num_protocolo)

    def tramitar_materia(cod_materia, cod_proposicao, hdn_num_protocolo):
        cod_unid_tram_local = int(context.sapl_documentos.props_sagl.origem)
        if des_tipo_materia in ['Requerimento', 'Indicação', 'Moção', 'Pedido de Informação']:
            cod_unid_tram_dest = int(context.sapl_documentos.props_sagl.destino_outros)
        else:
            cod_unid_tram_dest = int(context.sapl_documentos.props_sagl.destino)
        cod_status = int(context.sapl_documentos.props_sagl.status)
        for usuario in context.zsql.usuario_obter_zsql(col_username=REQUEST['AUTHENTICATED_USER'].getUserName()):
            cod_usuario_corrente = int(usuario.cod_usuario or 0)
        hr_tramitacao = DateTime(datefmt='international').strftime('%d/%m/%Y %H:%M:%S')
        txt_tramitacao = (
            '<p>Proposição eletrônica enviada em ' + str(dat_envio) +
            '. Matéria incorporada em ' + hr_tramitacao +
            ' sob protocolo nº ' + str(hdn_num_protocolo) + '/' + DateTime(datefmt='international').strftime("%Y") + '</p>'
        )
        hdn_url = context.portal_url() + '/cadastros/recebimento_proposicao/recebimento_proposicao_index_html#protocolo'
        context.zsql.tramitacao_incluir_zsql(
            cod_materia=cod_materia,
            dat_tramitacao=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
            cod_unid_tram_local=cod_unid_tram_local,
            cod_usuario_local=cod_usuario_corrente,
            cod_unid_tram_dest=cod_unid_tram_dest,
            dat_encaminha=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
            cod_status=cod_status,
            ind_urgencia=0,
            txt_tramitacao=txt_tramitacao,
            ind_ult_tramitacao=1
        )
        for tramitacao in context.zsql.tramitacao_incluida_codigo_obter_zsql():
            cod_tramitacao = tramitacao.cod_tramitacao
        if hasattr(context.sapl_documentos.proposicao, str(cod_proposicao) + '.odt'):
            context.pysc.proposicao_salvar_como_texto_integral_materia_pysc(cod_proposicao, cod_materia, 0)
        context.zsql.proposicao_registrar_recebimento_zsql(
            cod_proposicao=cod_proposicao,
            dat_recebimento=context.pysc.data_atual_iso_pysc(),
            cod_mat_ou_doc=int(cod_materia)
        )
        if hasattr(context.sapl_documentos.proposicao, str(cod_proposicao) + '_signed.pdf'):
            context.modelo_proposicao.proposicao_autuar_async(cod_proposicao=cod_proposicao)
        context.sapl_documentos.materia.Catalog.atualizarCatalogo(int(cod_materia))
        return context.relatorios.pdf_tramitacao_preparar_pysc(hdn_cod_tramitacao=cod_tramitacao, hdn_url=hdn_url)

    if cod_mat is not None:
        mensagem = 'Proposição já convertida em matéria legislativa!'
        mensagem_obs = 'Verifique a lista de proposições incorporadas.'
        if modo_api:
            return resposta_api(False, 'ja_incorporada', mensagem, cod_proposicao=cod_proposicao, detalhe=mensagem_obs)
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?tipo_mensagem=danger&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs)
    elif dat_solicitacao_devolucao is not None:
        mensagem = 'Proposição com devolução solicitada pelo autor!'
        mensagem_obs = 'Verifique a lista das solicitações de devolução.'
        if modo_api:
            return resposta_api(False, 'devolucao_solicitada', mensagem, cod_proposicao=cod_proposicao, detalhe=mensagem_obs)
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?tipo_mensagem=danger&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs)
    elif dat_devolucao is not None:
        mensagem = 'Proposição devolvida ao autor!'
        mensagem_obs = 'Verifique a lista das proposições devolvidas.'
        if modo_api:
            return resposta_api(False, 'devolvida', mensagem, cod_proposicao=cod_proposicao, detalhe=mensagem_obs)
        RESPONSE.redirect(context.portal_url() + '/mensagem_emitir?tipo_mensagem=danger&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs)
    else:
        try:
            criar_protocolo(
                tip_materia, num_ident_basica, ano_materia, dat_apresentacao,
                txt_ementa, txt_observacao, cod_autor, tip_quorum, ind_complementar, cod_proposicao
            )
            if modo_api:
                return resposta_api(True, 'incorporada', 'Matéria legislativa incorporada com sucesso.', cod_proposicao=cod_proposicao)
        except Exception as e:
            if modo_api:
                return resposta_api(False, 'erro', 'Erro inesperado ao incorporar a matéria.', cod_proposicao=cod_proposicao, detalhe=str(e))
            raise
