## Script (Python) "tramitacao_lote_salvar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=check_tram, txt_dat_tramitacao, lst_cod_unid_tram_local, hdn_cod_usuario_local, lst_cod_unid_tram_dest, lst_cod_usuario_dest, lst_cod_status, rad_ind_urgencia, txa_txt_tramitacao, txt_dat_fim_prazo, file_nom_anexo
##title=
##
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE
SESSION = REQUEST.SESSION

v=str(check_tram)
if v.isdigit():
   cod_materia = [check_tram]
else:
   cod_materia = check_tram

cod_materia = [
   e
   for i, e in enumerate(cod_materia)
   if cod_materia.index(e) == i
]

lst_ultimas=[]
for item in cod_materia:
    dic_ultimas = {}
    for tramitacao in context.zsql.tramitacao_obter_zsql(cod_materia=item, ind_ult_tramitacao=1, ind_excluido=0):
        dic_ultimas['cod_materia'] = tramitacao.cod_materia
        dic_ultimas['cod_tramitacao'] = tramitacao.cod_tramitacao    
        lst_ultimas.append(dic_ultimas)

hdn_dat_encaminha = DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S')

if lst_ultimas != []:
   for dic in lst_ultimas:
       context.zsql.tramitacao_ind_ultima_atualizar_zsql(cod_materia = dic['cod_materia'], cod_tramitacao = dic['cod_tramitacao'], ind_ult_tramitacao = 0)    
       context.zsql.tramitacao_registrar_recebimento_zsql(cod_tramitacao = dic['cod_tramitacao'], cod_usuario_corrente = hdn_cod_usuario_local)
       context.pysc.atualiza_indicador_tramitacao_materia_pysc(cod_materia = dic['cod_materia'], cod_status = lst_cod_status)          

if txt_dat_fim_prazo==None or txt_dat_fim_prazo=='':
   data_atual = DateTime(datefmt='international')
   for tramitacao in context.zsql.status_tramitacao_obter_zsql(cod_status=lst_cod_status, ind_excluido=0):
       if tramitacao.num_dias_prazo != None:
          data_calculada = data_atual + str(tramitacao.num_dias_prazo)
          txt_dat_fim_prazo = DateTime(data_calculada).strftime('%Y/%m/%d')
       else:
          txt_dat_fim_prazo = ''
elif txt_dat_fim_prazo != '':
   txt_dat_fim_prazo = context.pysc.data_converter_pysc(data=txt_dat_fim_prazo)

for item in cod_materia:
    context.zsql.tramitacao_incluir_zsql(cod_materia = item, dat_tramitacao = DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'), cod_unid_tram_local = lst_cod_unid_tram_local, cod_usuario_local = hdn_cod_usuario_local, cod_unid_tram_dest = lst_cod_unid_tram_dest, cod_usuario_dest = lst_cod_usuario_dest, dat_encaminha = hdn_dat_encaminha, cod_status = lst_cod_status, ind_urgencia = rad_ind_urgencia, txt_tramitacao = txa_txt_tramitacao, dat_fim_prazo = txt_dat_fim_prazo, ind_ult_tramitacao = 1)

    if context.dbcon_logs and (item != '' and item != None):
       context.zsql.logs_registrar_zsql(usuario = REQUEST['AUTHENTICATED_USER'].getUserName(), data = DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'), modulo = 'tramitacao_materia', metodo = 'tramitacao_lote_salvar_pysc', cod_registro = item, IP = context.pysc.get_ip())         

lst_novas = []
for item in cod_materia:
    dic_novas = {}
    for tramitacao in context.zsql.tramitacao_obter_zsql(cod_materia=item, ind_ult_tramitacao=1, ind_excluido=0):
        dic_novas['cod_materia'] = int(tramitacao.cod_materia)
        dic_novas['cod_tramitacao'] = int(tramitacao.cod_tramitacao)
        dic_novas['cod_destino'] = int(tramitacao.cod_unid_tram_dest)
        dic_novas['des_status'] = tramitacao.des_status
        lst_novas.append(dic_novas)

for dic in lst_novas:
    #carimbo deferimento
    #if dic['des_status'] == 'Deferido':
    #   context.modelo_proposicao.requerimento_aprovar(cod_sessao_plen=0, nom_resultado=dic['des_status'], cod_materia=dic['cod_materia'])

    # protocolo executivo
    #for unidade in context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao=dic['cod_destino'], ind_leg=1, ind_excluido=0):
    #    if 'Prefeitura' in unidade.nom_unidade_join or 'Executivo' in unidade.nom_unidade_join:
    #        resultado_protocolo = st.protocolo_prefeitura(dic['cod_materia']) 
    #        context.zsql.tramitacao_prefeitura_registrar_zsql(cod_tramitacao = dic['cod_tramitacao'], texto_protocolo=resultado_protocolo)           
    # fim protocolo executivo

    context.pysc.envia_tramitacao_autor_pysc(cod_materia = dic['cod_materia'])
    context.pysc.envia_acomp_materia_pysc(cod_materia = dic['cod_materia'])         
    #hdn_url = '/tramitacao_mostrar_proc?hdn_cod_tramitacao=' + str(dic['cod_tramitacao'])+ '&hdn_cod_materia=' + str(dic['cod_materia'])+'&lote=1'
    hdn_url = context.portal_url() + '/cadastros/tramitacao_materia/itens_enviados_html'
    context.relatorios.pdf_tramitacao_preparar_pysc(hdn_cod_tramitacao = dic['cod_tramitacao'], hdn_url = hdn_url)
    arquivoPdf=str(dic['cod_tramitacao'])+"_tram_anexo1.pdf"
    if file_nom_anexo != '' and len(file_nom_anexo.read())!=0:
       context.sapl_documentos.materia.tramitacao.manage_addFile(id=arquivoPdf, content_type='application/pdf', file=file_nom_anexo, title='Anexo de Tramitação')
       if hasattr(context.sapl_documentos.materia.tramitacao,arquivoPdf):
          context.cadastros.tramitacao_materia.tramitacao_juntar_pdf(cod_tramitacao=dic['cod_tramitacao'])

# Mensagem via sessão para evitar excesso na URL
SESSION['tipo_mensagem'] = 'success'
SESSION['mensagem'] = 'Processos legislativos tramitados com sucesso!'
SESSION['mensagem_obs'] = ''
SESSION['url_redirect'] = context.portal_url() + '/cadastros/tramitacao_materia/itens_enviados_html'

RESPONSE.redirect(context.portal_url() + '/mensagem_emitir')
