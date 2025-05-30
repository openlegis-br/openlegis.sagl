## Script (Python) "tramitacao_lote_salvar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=check_tram, txt_dat_tramitacao, lst_cod_unid_tram_local, hdn_cod_usuario_local, lst_cod_unid_tram_dest, lst_cod_usuario_dest, lst_cod_status, txa_txt_tramitacao, txt_dat_fim_prazo
##title=
##

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE
session = REQUEST.SESSION

v=str(check_tram)
if v.isdigit():
   cod_documento = [check_tram]
else:
   cod_documento = check_tram

cod_documento = [
   e
   for i, e in enumerate(cod_documento)
   if cod_documento.index(e) == i
]

lst_ultimas=[]
for item in cod_documento:
    dic_ultimas = {}
    for tramitacao in context.zsql.tramitacao_administrativo_obter_zsql(cod_documento=item, ind_ult_tramitacao=1, ind_excluido=0):
        dic_ultimas['cod_documento'] = tramitacao.cod_documento
        dic_ultimas['cod_tramitacao'] = tramitacao.cod_tramitacao    
        lst_ultimas.append(dic_ultimas)

hdn_dat_encaminha = DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

if lst_ultimas != []:
   for dic in lst_ultimas:
       context.zsql.tramitacao_administrativo_ind_ultima_atualizar_zsql(cod_documento = dic['cod_documento'], cod_tramitacao = dic['cod_tramitacao'], ind_ult_tramitacao = 0)
       context.zsql.tramitacao_adm_registrar_recebimento_zsql(cod_tramitacao = dic['cod_tramitacao'], cod_usuario_corrente = hdn_cod_usuario_local)
       context.pysc.atualiza_indicador_tramitacao_documento_pysc(cod_documento = dic['cod_documento'], cod_status = lst_cod_status)

if txt_dat_fim_prazo==None or txt_dat_fim_prazo=='':
   data_atual = DateTime(datefmt='international')
   for tramitacao in context.zsql.status_tramitacao_administrativo_obter_zsql(cod_status=lst_cod_status, ind_excluido=0):
       if tramitacao.num_dias_prazo != None:
          data_calculada = data_atual + str(tramitacao.num_dias_prazo)
          txt_dat_fim_prazo = DateTime(data_calculada).strftime('%Y/%m/%d')
       else:
          txt_dat_fim_prazo = ''
elif txt_dat_fim_prazo != '':
   txt_dat_fim_prazo = context.pysc.data_converter_pysc(data=txt_dat_fim_prazo)

for item in cod_documento:
    context.zsql.tramitacao_administrativo_incluir_zsql(cod_documento = item, dat_tramitacao = hdn_dat_encaminha, cod_unid_tram_local = lst_cod_unid_tram_local, cod_usuario_local = hdn_cod_usuario_local, cod_unid_tram_dest = lst_cod_unid_tram_dest, cod_usuario_dest = lst_cod_usuario_dest, dat_encaminha = hdn_dat_encaminha, cod_status = lst_cod_status, txt_tramitacao = txa_txt_tramitacao, dat_fim_prazo = txt_dat_fim_prazo, ind_ult_tramitacao = 1)

    if context.dbcon_logs and (item != '' and item != None):
       context.zsql.logs_registrar_zsql(usuario = REQUEST['AUTHENTICATED_USER'].getUserName(), data = DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'), modulo = 'tramitacao_documento', metodo = 'tramitacao_lote_salvar_pysc', cod_registro = item, IP = context.pysc.get_ip())

lst_novas = []
for item in cod_documento:
    dic_novas = {}
    for tramitacao in context.zsql.tramitacao_administrativo_obter_zsql(cod_documento=item, ind_ult_tramitacao=1, ind_excluido=0):
        dic_novas['cod_documento'] = tramitacao.cod_documento
        dic_novas['cod_tramitacao'] = tramitacao.cod_tramitacao
        lst_novas.append(dic_novas)

for dic in lst_novas:
    context.pysc.envia_acomp_documento_pysc(cod_documento = dic['cod_documento'])         
    #hdn_url = 'tramitacao_mostrar_proc?hdn_cod_tramitacao=' + str(dic['cod_tramitacao'])+ '&cod_documento=' + str(dic['cod_documento'])+'&lote=1'
    hdn_url = context.portal_url() + '/cadastros/tramitacao_documento/itens_enviados_html'    
    context.relatorios.pdf_tramitacao_administrativo_preparar_pysc(hdn_cod_tramitacao = dic['cod_tramitacao'], hdn_url = hdn_url)

mensagem = 'Processos administrativos tramitados com sucesso!'
mensagem_obs = ''
url = context.portal_url() + '/cadastros/tramitacao_documento/itens_enviados_html'
redirect_url=context.portal_url()+'/mensagem_emitir?tipo_mensagem=success&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs + '&url=' + url
REQUEST.RESPONSE.redirect(redirect_url)
