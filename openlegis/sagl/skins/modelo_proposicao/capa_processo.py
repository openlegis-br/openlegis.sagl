## Script (Python) "capa_processo"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_materia, action
##title=
##
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE
session = REQUEST.SESSION

capa_dic = {}
casa={}
aux=context.sapl_documentos.props_sagl.propertyItems()
for item in aux:
    casa[item[0]]=item[1]
localidade=context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])
estado = context.zsql.localidade_obter_zsql(tip_localidade="U")
for uf in estado:
    if localidade[0].sgl_uf == uf.sgl_uf:
       nom_estado = uf.nom_localidade
       break
capa_dic['nom_camara'] = casa['nom_casa']
capa_dic["nom_estado"] = nom_estado
for local in context.zsql.localidade_obter_zsql(cod_localidade = casa['cod_localidade']):
    capa_dic['nom_localidade']= local.nom_localidade
    capa_dic['sgl_uf']= local.sgl_uf

for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia):
 if materia.num_protocolo:
    for protocolo in context.zsql.protocolo_pesquisar_zsql(num_protocolo=materia.num_protocolo,ano_protocolo=materia.ano_ident_basica):
      if protocolo.cod_protocolo:
         capa_dic['num_protocolo'] = str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo)
         capa_dic['dat_protocolo'] = context.pysc.iso_to_port_pysc(protocolo.dat_protocolo)
         capa_dic['hor_protocolo'] = protocolo.hor_protocolo[0:2]+':'+protocolo.hor_protocolo[3:5]
         capa_dic["dia_protocolo"] = context.pysc.data_converter_por_extenso_pysc(data=context.pysc.iso_to_port_pysc(protocolo.dat_protocolo))
         capa_dic["dia_semana"] = context.pysc.data_converter_dia_semana_pysc(data=context.pysc.iso_to_port_pysc(protocolo.dat_protocolo))

 else:
    capa_dic['num_protocolo'] = ''
    capa_dic['dat_protocolo'] = materia.dat_apresentacao
    capa_dic['hor_protocolo'] = ''
    capa_dic["dia_protocolo"] = context.pysc.data_converter_por_extenso_pysc(data=materia.dat_apresentacao)
    capa_dic["dia_semana"] = context.pysc.data_converter_dia_semana_pysc(data=materia.dat_apresentacao)

 capa_dic['dat_vencimento'] = ""
 if materia.dat_fim_prazo != None:
   capa_dic['dat_vencimento'] = materia.dat_fim_prazo
 capa_dic['num_proposicao'] = str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
 capa_dic['des_tipo_materia'] = materia.des_tipo_materia
 capa_dic['txt_ementa'] = materia.txt_ementa
 capa_dic['nom_autor'] = ""
 autores = context.zsql.autoria_obter_zsql(cod_materia=cod_materia)
 fields = list(autores.data_dictionary().keys())
 lista_autor = []
 for autor in autores:
   for field in fields:
      nome_autor = autor['nom_autor_join']
   lista_autor.append(nome_autor)
 capa_dic['nom_autor'] = ', '.join(['%s' % (value) for (value) in lista_autor])
 capa_dic['regime_tramitacao'] = ""
 if materia.cod_regime_tramitacao != None:
   for regime in context.zsql.regime_tramitacao_obter_zsql(cod_regime_tramitacao=materia.cod_regime_tramitacao):
     capa_dic['regime_tramitacao'] = regime.des_regime_tramitacao
 capa_dic['dat_publicacao'] = materia.dat_publicacao
 capa_dic['dat_fim_prazo'] = materia.dat_fim_prazo
 capa_dic['quorum_votacao'] = ""
 if materia.tip_quorum != None:
   for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=materia.tip_quorum):
     capa_dic['quorum_votacao'] = quorum.des_quorum
 capa_dic['dat_leitura'] = ""
 for leitura in context.zsql.materia_apresentada_sessao_obter_zsql(cod_materia=materia.cod_materia):
     for sessao in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=leitura.cod_sessao_plen):
         capa_dic['dat_leitura'] = sessao.dat_inicio_sessao
 for expediente in context.zsql.expediente_materia_obter_zsql(cod_materia=materia.cod_materia):
     for sessao in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=expediente.cod_sessao_plen):
         capa_dic['dat_leitura'] = sessao.dat_inicio_sessao
 capa_dic['comissao'] = ''
 lst_comissao = []
 for despacho in context.zsql.despacho_inicial_obter_zsql(cod_materia=materia.cod_materia, ind_excluido=0):
     dic = {}
     dic['nom_comissao'] = despacho.nom_comissao_index
     dic['resultado'] = ""
     for relatoria in context.zsql.relatoria_obter_zsql(cod_comissao=despacho.cod_comissao_sel, cod_materia=materia.cod_materia, num_ordem=despacho.num_ordem):
         if relatoria.tip_conclusao == 'F':
            dic['resultado'] = '(Favorável)'
         if relatoria.tip_conclusao == 'C':
            dic['resultado'] = '(Contrário)'
     lst_comissao.append(dic)
 if len(lst_comissao) > 0:
    capa_dic['comissao'] = lst_comissao

 lst_votacao = []
 for item in context.pysc.votacao_obter_pysc(cod_materia=cod_materia):
     if str(item['fase']) == 'Expediente' or str(item['fase']) == 'Ordem do Dia':
        if str(item['fase']) == 'Ordem do Dia':
           item['fase'] = ' na Ordem do Dia'
        elif str(item['fase']) == 'Expediente':
           item['fase'] = ' no Expediente'
        if str(item['txt_turno']) == 'Único':
           item['txt_turno'] = 'Turno Único'
        id_resultado = str(item['txt_resultado']) + ' em ' +  str(item['txt_turno']) + str(item['fase']) + ' da ' + str(item['sessao']) + ' de ' + str(item['dat_sessao'])
        lst_votacao.append(id_resultado)
 
 capa_dic['votacao'] = ', '.join(['%s' % (value) for (value) in lst_votacao])

 lst_acessorios = []
 for substitutivo in context.zsql.substitutivo_obter_zsql(cod_materia=materia.cod_materia,ind_excluido=0):
     dic_substitutivo = {}
     nom_resultado = ''
     for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo, ind_excluido=0):
        if votacao.votacao_observacao != '':
           votacao_observacao = ' - ' + votacao.votacao_observacao
        else:
           votacao_observacao = ''
        if votacao.tip_resultado_votacao:
           for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=votacao.tip_turno):
               turno_discussao = turno.des_turno
           resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
           for i in resultado:
               nom_resultado = ' (' + i.nom_resultado + ')'
               if votacao.votacao_observacao:
                  votacao_observacao = votacao.ordem_observacao
        else:
           nom_resultado = " (Não votado)"
           votacao_observacao = ""
     id_substitutivo = 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + nom_resultado
     lst_acessorios.append(id_substitutivo)

 lst_emendas = []
 for emenda in context.zsql.emenda_obter_zsql(cod_materia=materia.cod_materia,ind_excluido=0):
     dic_emenda = {}
     nom_resultado = ''
     for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_emenda=emenda.cod_emenda, ind_excluido=0):
        if votacao.votacao_observacao != '':
           votacao_observacao = ' - ' + votacao.votacao_observacao
        else:
           votacao_observacao = ''
        if votacao.tip_resultado_votacao:
           for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=votacao.tip_turno):
               turno_discussao = turno.des_turno
           resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
           for i in resultado:
               nom_resultado = ' (' + i.nom_resultado + ')'
               if votacao.votacao_observacao:
                  votacao_observacao = votacao.ordem_observacao
        else:
           nom_resultado = " (Não votada)"
           votacao_observacao = ""
     id_emenda = 'Emenda ' + emenda.des_tipo_emenda  + ' nº ' + str(emenda.num_emenda) + nom_resultado
     lst_acessorios.append(id_emenda)

 capa_dic['acessorios'] = ', '.join(['%s' % (value) for (value) in lst_acessorios])

 capa_dic['autografo'] = ''
 for documento in context.zsql.documento_acessorio_obter_zsql(cod_materia=materia.cod_materia, ind_excluido=0):
     if documento.des_tipo_documento == 'Autógrafo':
        capa_dic['autografo'] = documento.nom_documento
        
 lst_anexada = []
 
 capa_dic['veto'] = ''
 capa_dic['anexada'] = ''
 
 for anexada in context.zsql.anexada_obter_zsql(cod_materia_anexada=materia.cod_materia, ind_excluido=0):
     for item in context.zsql.materia_obter_zsql(cod_materia=anexada.cod_materia_principal, ind_excluido = 0):
         nom_resultado = ''
         for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
             if votacao.votacao_observacao != '':
                votacao_observacao = ' - ' + votacao.votacao_observacao
             else:
                votacao_observacao = ''
             if votacao.tip_resultado_votacao:
                for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=votacao.tip_turno):
                    turno_discussao = turno.des_turno
                resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
                for i in resultado:
                    nom_resultado = ' (' + i.nom_resultado + ')'
                    if votacao.votacao_observacao:
                       votacao_observacao = votacao.ordem_observacao
             else:
                nom_resultado = " (Não votado)"
                votacao_observacao = ""
     id_anexada = item.des_tipo_materia + ' nº ' + str(item.num_ident_basica) + '/' + str(item.ano_ident_basica) + nom_resultado
     lst_anexada.append(id_anexada)

 for anexada in context.zsql.anexada_obter_zsql(cod_materia_principal=materia.cod_materia, ind_excluido=0):
     for item in context.zsql.materia_obter_zsql(cod_materia=anexada.cod_materia_anexada, ind_excluido = 0):
         nom_resultado = ''
         for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
             if votacao.votacao_observacao != '':
                votacao_observacao = ' - ' + votacao.votacao_observacao
             else:
                votacao_observacao = ''
             if votacao.tip_resultado_votacao:
                for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=votacao.tip_turno):
                    turno_discussao = turno.des_turno
                resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
                for i in resultado:
                    nom_resultado = ' (' + i.nom_resultado + ')'
                    if votacao.votacao_observacao:
                       votacao_observacao = votacao.ordem_observacao
             else:
                nom_resultado = " (Não votado)"
                votacao_observacao = ""
     id_anexada = item.des_tipo_materia + ' nº ' + str(item.num_ident_basica) + '/' + str(item.ano_ident_basica) + nom_resultado
     lst_anexada.append(id_anexada)

 capa_dic['anexada'] = ', '.join(['%s' % (value) for (value) in lst_anexada])

 capa_dic['norma'] = None
 for norma in context.zsql.materia_buscar_norma_juridica_zsql(cod_materia=materia.cod_materia):
      dat_publicacao = ''
      if norma.dat_publicacao != '' and norma.dat_publicacao != None:
         dat_publicacao = '. Publicação no Diário Oficial: ' + str(norma.dat_publicacao)
      capa_dic['norma'] = norma.des_norma + ' nº ' + str(norma.num_norma) + ' de ' + str(norma.dat_norma) + str(dat_publicacao)
 capa_dic['observacoes'] = materia.txt_observacao
 capa_dic['situacao'] = None
 for tramitacao in context.zsql.tramitacao_obter_zsql(cod_materia=materia.cod_materia, ind_ult_tramitacao=1):
     for unidade in context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao=int(tramitacao.cod_unid_tram_dest)):
         unidade_atual = unidade.nom_unidade_join
     capa_dic['situacao'] = 'Último Local: ' + tramitacao.dat_tramitacao + ' - ' + unidade_atual + ' - ' + tramitacao.des_status

 id_capa = 'capa_' + materia.sgl_tipo_materia+'-'+str(materia.num_ident_basica)+'-'+str(materia.ano_ident_basica)
 capa_dic['nom_arquivo_odt'] = "%s.odt" % id_capa
 capa_dic['nom_arquivo_pdf'] = "%s.pdf" % id_capa
    
 return st.capa_processo_gerar_odt(capa_dic,action)
