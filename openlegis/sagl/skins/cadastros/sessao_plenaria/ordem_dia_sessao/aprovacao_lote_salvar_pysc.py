## Script (Python) "aprovacao_lote_salvar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_sub_path
##parameters=cod_sessao_plen, dat_sessao, num_legislatura, cod_sessao_leg, tip_sessao
##title=Aprovação em Lote de Requerimentos

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

votadas = []
nao_votadas = []
anuladas = []

for item in context.zsql.ordem_dia_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0):
    if item.cod_materia != '' and item.cod_materia is not None:
        for materia in context.zsql.materia_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
            if materia.des_tipo_materia == 'Requerimento' or materia.des_tipo_materia == 'Requerimento ao Plenário':
                dic_materias = {'cod_materia': int(item.cod_materia), 'cod_ordem': int(item.cod_ordem)}
                for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_ordem=item.cod_ordem, cod_materia=item.cod_materia):
                    votadas.append(int(item.cod_materia))
                    if votacao.tip_resultado_votacao == 0:
                        anuladas.append(dic_materias.copy())
                if int(item.cod_materia) not in votadas:
                    nao_votadas.append(dic_materias)

presentes = context.pysc.quantidade_presentes_ordem_dia_pysc(cod_sessao_plen=cod_sessao_plen, dat_ordem=dat_sessao)
votos_sim = int(presentes) - 1 if int(presentes) != 0 else 0

tipo_aprovado = None
nome_aprovado = None
for resultado in context.zsql.tipo_resultado_votacao_obter_zsql():
    if resultado.nom_resultado in ('Aprovado', 'Aprovado(a)'):
        tipo_aprovado = resultado.tip_resultado_votacao
        nome_aprovado = resultado.nom_resultado
        break

if tipo_aprovado is not None and nome_aprovado is not None:
    for dic in nao_votadas:
        cod_materia = dic.get('cod_materia')
        cod_ordem = dic.get('cod_ordem')
        try:
            context.zsql.trans_begin_zsql()
            context.zsql.votacao_incluir_zsql(
                num_votos_sim=votos_sim,
                num_votos_nao='0',
                num_abstencao='0',
                num_ausentes='0',
                cod_ordem=cod_ordem,
                cod_materia=cod_materia,
                tip_resultado_votacao=tipo_aprovado
            )
            for proposicao in context.zsql.proposicao_obter_zsql(ind_mat_ou_doc='M', cod_mat_ou_doc=cod_materia):
                if hasattr(context.sapl_documentos.proposicao, f'{proposicao.cod_proposicao}_signed.pdf'):
                    context.modelo_proposicao.proposicao_autuar(cod_proposicao=proposicao.cod_proposicao)
            context.modelo_proposicao.requerimento_aprovar_async(
                cod_sessao_plen=cod_sessao_plen,
                nom_resultado=nome_aprovado,
                cod_materia=cod_materia
            )
            context.zsql.trans_commit_zsql()
        except Exception as e:
            context.zsql.trans_rollback_zsql()
            print(f"Erro ao processar não votada (Matéria: {cod_materia}, Ordem: {cod_ordem}): {e}")

    for dic in anuladas:
        cod_materia = dic.get('cod_materia')
        cod_ordem = dic.get('cod_ordem')
        cod_votacao = dic.get('cod_votacao')
        try:
            context.zsql.trans_begin_zsql()
            context.zsql.votacao_atualizar_zsql(
                cod_votacao=cod_votacao,
                num_votos_sim=votos_sim,
                num_votos_nao='0',
                num_abstencao='0',
                num_ausentes='0',
                cod_ordem=cod_ordem,
                cod_materia=cod_materia,
                tip_resultado_votacao=tipo_aprovado
            )
            for proposicao in context.zsql.proposicao_obter_zsql(ind_mat_ou_doc='M', cod_mat_ou_doc=cod_materia):
                if hasattr(context.sapl_documentos.proposicao, f'{proposicao.cod_proposicao}_signed.pdf'):
                    context.modelo_proposicao.proposicao_autuar(cod_proposicao=proposicao.cod_proposicao)
            context.modelo_proposicao.requerimento_aprovar_async(
                cod_sessao_plen=cod_sessao_plen,
                nom_resultado=nome_aprovado,
                cod_materia=cod_materia
            )
            context.zsql.trans_commit_zsql()
        except Exception as e:
            context.zsql.trans_rollback_zsql()
            print(f"Erro ao processar anulada (Matéria: {cod_materia}, Ordem: {cod_ordem}, Votação: {cod_votacao}): {e}")
else:
    print("Tipo de resultado 'Aprovado' ou 'Aprovado(a)' não encontrado.")

redirect_url = f'index_html?cod_sessao_plen={cod_sessao_plen}&cod_sessao_leg={cod_sessao_leg}&num_legislatura={num_legislatura}&dat_sessao={dat_sessao}&tip_sessao={tip_sessao}'
RESPONSE.redirect(redirect_url)
