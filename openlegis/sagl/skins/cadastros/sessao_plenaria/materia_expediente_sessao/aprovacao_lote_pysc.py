## Script (Python) "aprovacao_lote_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_sessao_plen, cod_sessao_leg, num_legislatura, dat_sessao, tip_sessao
##

import logging

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

try:
    # Obter tipo de resultado aprovado
    resultado_aprovado = None
    nom_resultado = None
    for r in context.zsql.tipo_resultado_votacao_obter_zsql(ind_excluido=0):
        if r.nom_resultado in ('Aprovado', 'Aprovada', 'Aprovado(a)'):
            resultado_aprovado = r.tip_resultado_votacao
            nom_resultado = r.nom_resultado
            break

    if not resultado_aprovado:
        raise ValueError("Tipo de resultado 'Aprovado' não encontrado.")

    # Percorrer matérias da sessão plenária
    for expediente in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0):
        cod_materia = expediente.cod_materia
        cod_ordem = expediente.cod_ordem
        if not cod_materia:
            continue

        materia = context.zsql.materia_obter_zsql(cod_materia=cod_materia)[0]

        votacoes = context.zsql.votacao_expediente_materia_obter_zsql(
            cod_sessao_plen=cod_sessao_plen,
            cod_ordem=cod_ordem,
            cod_materia=cod_materia
        )

        votacao_existente = votacoes[0] if votacoes else None
        cod_votacao = votacao_existente.cod_votacao if votacao_existente else None
        tip_resultado = votacao_existente.tip_resultado_votacao if votacao_existente else None

        if cod_votacao and tip_resultado not in (None, 0):
            logging.info(f"[AUTOVOTO] Matéria {cod_materia} já possui cod_votacao={cod_votacao} com tip_resultado_votacao={tip_resultado}. Votação manual detectada. Nenhuma ação executada.")
            continue

        # Obter número de votos SIM (presentes)
        num_votos_sim = context.pysc.quantidade_presentes_sessao_plenaria_contar_pysc(cod_sessao_plen=cod_sessao_plen)

        if cod_votacao and tip_resultado in (None, 0):
            # Atualizar votação incompleta
            context.zsql.votacao_atualizar_zsql(
                cod_votacao=cod_votacao,
                num_votos_sim=num_votos_sim,
                num_votos_nao=0,
                num_abstencao=0,
                num_ausentes=0,
                txt_observacao='',
                cod_ordem=cod_ordem,
                cod_materia=cod_materia,
                cod_parecer=None,
                cod_emenda=None,
                cod_subemenda=None,
                cod_substitutivo=None,
                tip_resultado_votacao=resultado_aprovado,
                ind_excluido=0
            )
            logging.info(f"[AUTOVOTO] Votação incompleta atualizada para matéria {cod_materia} (cod_votacao={cod_votacao}).")
        else:
            # Nova votação
            context.zsql.votacao_incluir_zsql(
                num_votos_sim=num_votos_sim,
                num_votos_nao=0,
                num_abstencao=0,
                num_ausentes=0,
                txt_observacao='',
                cod_ordem=cod_ordem,
                cod_materia=cod_materia,
                cod_parecer=None,
                cod_emenda=None,
                cod_subemenda=None,
                cod_substitutivo=None,
                tip_resultado_votacao=resultado_aprovado,
                ind_excluido=0
            )
            logging.info(f"[AUTOVOTO] Votação registrada para matéria {cod_materia}.")

        # Verificar proposição assinada
        for prop in context.zsql.proposicao_obter_zsql(ind_mat_ou_doc='M', cod_mat_ou_doc=cod_materia):
            cod_proposicao = prop.cod_proposicao
            nome_arquivo = f"{cod_proposicao}_signed.pdf"
            if hasattr(context.sapl_documentos.proposicao, nome_arquivo):
                context.modelo_proposicao.proposicao_autuar(cod_proposicao=cod_proposicao)
                logging.info(f"[AUTOVOTO] Proposição {cod_proposicao} autuada.")
                break

        # Aplicar margem inferior se documento assinado existir
        for tipo_doc in ('materia', 'redacao_final'):
            for assinatura in context.zsql.assinatura_documento_obter_zsql(codigo=cod_materia, tipo_doc=tipo_doc, ind_assinado=1):
                filename = f"{assinatura.cod_assinatura_doc}.pdf"
                if hasattr(context.sapl_documentos.documentos_assinados, filename):
                    context.modelo_proposicao.margem_inferior(
                        codigo=assinatura.codigo,
                        anexo=assinatura.anexo,
                        tipo_doc=assinatura.tipo_doc,
                        cod_assinatura_doc=assinatura.cod_assinatura_doc,
                        cod_usuario=assinatura.cod_usuario,
                        filename=filename
                    )
                    logging.info(f"[AUTOVOTO] Margem aplicada ({tipo_doc}) para matéria {cod_materia}.")
                    break

        # Registrar aprovação da matéria
        context.modelo_proposicao.requerimento_aprovar(
            cod_sessao_plen=cod_sessao_plen,
            nom_resultado=nom_resultado,
            cod_materia=cod_materia
        )
        logging.info(f"[AUTOVOTO] Matéria {cod_materia} carimbada como aprovada.")

    # Redirecionamento final com sucesso
    url = context.portal_url() + '/cadastros/sessao_plenaria/materia_expediente_sessao/materia_expediente_sessao_index_html?cod_sessao_plen={cod_sessao_plen}&cod_sessao_leg={cod_sessao_leg}&num_legislatura={num_legislatura}&dat_sessao={dat_sessao}&tip_sessao={tip_sessao}'
    mensagem = "Aprovações registradas com sucesso!"
    mensagem_obs = ''
    redirect_url = (
        f"{context.portal_url()}/mensagem_emitir?"
        f"tipo_mensagem=success&mensagem={mensagem}&mensagem_obs={mensagem_obs}&"
        f"url={url}"
    )
    RESPONSE.redirect(redirect_url)

except Exception as e:
    error_msg = f"Erro fatal no script: {str(e)}"
    logging.info(error_msg)
    RESPONSE.redirect(
        f"{context.portal_url()}/mensagem_emitir?"
        f"tipo_mensagem=error&mensagem={error_msg}"
    )
