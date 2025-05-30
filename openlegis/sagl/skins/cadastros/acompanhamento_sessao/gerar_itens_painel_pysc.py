## Script (Python) "gerar_itens_painel_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_sessao_plen
##title=
##

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

itens = []

cod_sessao_plen = int(context.REQUEST['cod_sessao_plen'])

for sessao in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=int(context.REQUEST['cod_sessao_plen']), ind_excluido=0):
  tipo_sessao = context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao.tip_sessao,ind_excluido=0)[0]
  dic_sessao = {}
  dic_sessao["tipo_item"] = 'Mensagem'
  cod_sessao_plen = sessao.cod_sessao_plen
  dic_sessao["cod_sessao_plen"] = sessao.cod_sessao_plen
  dic_sessao["nom_fase"] = 'Abertura'
  dic_sessao["txt_exibicao"] = '<h1><strong>Abertura da Sessão</strong></h1>'
  dic_sessao["cod_materia"] = ''
  dic_sessao["txt_autoria"] = ''
  dic_sessao["txt_turno"] = ''
  dic_sessao["txt_quorum"] = ''
  dic_sessao["ind_extrapauta"] = 0
  dic_sessao["ind_exibicao"] = 0
  itens.append(dic_sessao)


dic_presenca = {}
dic_presenca["tipo_item"] = 'Mensagem'
dic_presenca["cod_sessao_plen"] = sessao.cod_sessao_plen
dic_presenca["nom_fase"] = 'Abertura'
dic_presenca["txt_exibicao"] = '<h1><strong>Registro de Presença</strong></h1>'
dic_presenca["cod_materia"] = ''
dic_presenca["txt_autoria"] = ''
dic_presenca["txt_turno"] = ''
dic_presenca["ind_extrapauta"] = 0
dic_presenca["ind_exibicao"] = 0
itens.append(dic_presenca)

dic_correspondencias = {}
dic_correspondencias["tipo_item"] = 'Mensagem'
dic_correspondencias["cod_sessao_plen"] = sessao.cod_sessao_plen
dic_correspondencias["nom_fase"] = 'Expediente'
dic_correspondencias["txt_exibicao"] = '<h1><strong>Leitura de Correspondências</strong></h1>'
dic_correspondencias["cod_materia"] = ''
dic_correspondencias["txt_autoria"] = ''
dic_correspondencias["txt_turno"] = ''
dic_correspondencias["ind_extrapauta"] = 0
dic_correspondencias["ind_exibicao"] = 0
itens.append(dic_correspondencias)

lst_indicacoes = []
for indicacoes in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=int(context.REQUEST['cod_sessao_plen']),ind_excluido=0):
  for materia in context.zsql.materia_obter_zsql(cod_materia=indicacoes.cod_materia, des_tipo_materia='Indicação', ind_excluido=0):
    num_ident_basica = materia.num_ident_basica
    lst_indicacoes.append(num_ident_basica)

if len(lst_indicacoes) > 0:
  dic_indicacoes = {}
  dic_indicacoes["tipo_item"] = 'Mensagem'
  dic_indicacoes["cod_sessao_plen"] = sessao.cod_sessao_plen
  dic_indicacoes["nom_fase"] = 'Expediente'
  ano = DateTime(datefmt='international').strftime('%Y')
  dic_indicacoes["txt_exibicao"] = '<b>Indicações de números '+str(min(lst_indicacoes))+'/'+ano+ ' a '+str(max(lst_indicacoes))+'/'+ano
  dic_indicacoes["cod_materia"] = ''
  dic_indicacoes["txt_autoria"] = ''
  dic_indicacoes["txt_turno"] = ''
  dic_indicacoes["ind_extrapauta"] = 0
  dic_indicacoes["ind_exibicao"] = 0
  itens.append(dic_indicacoes)

dic_requerimentos_p = {}
dic_requerimentos_p["tipo_item"] = 'Mensagem'
dic_requerimentos_p["cod_sessao_plen"] = sessao.cod_sessao_plen
dic_requerimentos_p["nom_fase"] = 'Expediente'
dic_requerimentos_p["txt_exibicao"] = '<h1><strong>Requerimentos de Pesar</strong></h1>'
dic_requerimentos_p["cod_materia"] = ''
dic_requerimentos_p["txt_autoria"] = ''
dic_requerimentos_p["txt_turno"] = ''
dic_requerimentos_p["ind_extrapauta"] = 0
dic_requerimentos_p["ind_exibicao"] = 0
itens.append(dic_requerimentos_p)


dic_requerimentos_c = {}
dic_requerimentos_c["tipo_item"] = 'Mensagem'
dic_requerimentos_c["cod_sessao_plen"] = sessao.cod_sessao_plen
dic_requerimentos_c["nom_fase"] = 'Expediente'
dic_requerimentos_c["txt_exibicao"] = '<h1><strong>Requerimentos de Congratulações</strong></h1>'
dic_requerimentos_c["cod_materia"] = ''
dic_requerimentos_c["txt_autoria"] = ''
dic_requerimentos_c["txt_turno"] = ''
dic_requerimentos_c["ind_extrapauta"] = 0
dic_requerimentos_c["ind_exibicao"] = 0
itens.append(dic_requerimentos_c)

for requerimentos in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=int(context.REQUEST['cod_sessao_plen']),ind_excluido=0):
  dic_requerimentos = {}
  for materia in context.zsql.materia_obter_zsql(cod_materia=requerimentos.cod_materia, des_tipo_materia='Requerimento', ind_excluido=0):
    dic_requerimentos["tipo_item"] = 'Matéria'
    dic_requerimentos["cod_sessao_plen"] = sessao.cod_sessao_plen
    dic_requerimentos["nom_fase"] = 'Expediente'
    dic_requerimentos["txt_exibicao"] =  '<span class="fw-bold">' + materia.des_tipo_materia.upper()+' Nº '+str(materia.num_ident_basica)+"/"+str(materia.ano_ident_basica)+"</span><br/> "+ str(materia.txt_ementa)
    dic_requerimentos["cod_materia"] = materia.cod_materia
    dic_requerimentos["txt_autoria"] = ''
    autores = context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
    fields = list(autores.data_dictionary().keys())
    lista_autor = []
    for autor in autores:
      for field in fields:
        nome_autor = autor['nom_autor_join']
      lista_autor.append(nome_autor)
    dic_requerimentos["txt_autoria"] = ', '.join(['%s' % (value) for (value) in lista_autor])
    dic_requerimentos["txt_turno"] = ''
    dic_requerimentos["ind_extrapauta"] = 0
    dic_requerimentos["ind_exibicao"] = 0
    itens.append(dic_requerimentos)

#for mocoes in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=int(context.REQUEST['cod_sessao_plen']),ind_excluido=0):
#  dic_mocoes = {}
#  for materia in context.zsql.materia_obter_zsql(cod_materia=mocoes.cod_materia, des_tipo_materia='Moção', ind_excluido=0):
#    dic_mocoes["tipo_item"] = 'Matéria'
#    dic_mocoes["nom_fase"] = 'Expediente'
#    dic_mocoes["txt_exibicao"] = materia.des_tipo_materia.upper()+' Nº '+str(materia.num_ident_basica)+"/"+str(context.pysc.ano_abrevia_pysc(ano=str(materia.ano_ident_basica)))+" - "+ materia.txt_ementa 
#    dic_mocoes["cod_materia"] = materia.cod_materia
#    dic_mocoes["txt_autoria"] = ''
#    autores = context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
#    fields = autores.data_dictionary().keys()
#    lista_autor = []
#    for autor in autores:
#      for field in fields:
#        nome_autor = autor['nom_autor_join']
#      lista_autor.append(nome_autor)
#    dic_mocoes["txt_autoria"] = ', '.join(['%s' % (value) for (value) in lista_autor])
#    dic_mocoes["txt_turno"] = ''
#    dic_mocoes["ind_extrapauta"] = 0
#    dic_mocoes["ind_exibicao"] = 0
#    itens.append(dic_mocoes)

dic_peq_expediente = {}
dic_peq_expediente["tipo_item"] = 'Mensagem'
dic_peq_expediente["cod_sessao_plen"] = sessao.cod_sessao_plen
dic_peq_expediente["nom_fase"] = 'Expediente'
dic_peq_expediente["txt_exibicao"] = '<h1><strong>Pequeno Expediente</strong></h1>'
dic_peq_expediente["cod_materia"] = ''
dic_peq_expediente["txt_autoria"] = ''
dic_peq_expediente["txt_turno"] = ''
dic_peq_expediente["ind_extrapauta"] = 0
dic_peq_expediente["ind_exibicao"] = 0
itens.append(dic_peq_expediente)

dic_orddia = {}
dic_orddia["tipo_item"] = 'Mensagem'
dic_orddia["cod_sessao_plen"] = cod_sessao_plen
dic_orddia["nom_fase"] = 'Ordem do Dia'
dic_orddia["txt_exibicao"] = '<h1><strong>Ordem do Dia</strong></h1>'
dic_orddia["cod_materia"] = ''
dic_orddia["txt_autoria"] = ''
dic_orddia["txt_turno"] = ''
dic_orddia["ind_extrapauta"] = 0
dic_orddia["ind_exibicao"] = 0
itens.append(dic_orddia)

for ordem_dia in context.zsql.ordem_dia_obter_zsql(cod_sessao_plen=int(context.REQUEST['cod_sessao_plen']), ind_excluido=0):
    dic_ordem_dia = {}
    materia = context.zsql.materia_obter_zsql(cod_materia=ordem_dia.cod_materia)[0]
    dic_ordem_dia["tipo_item"] = 'Matéria'
    dic_ordem_dia["cod_sessao_plen"] = cod_sessao_plen
    dic_ordem_dia["nom_fase"] = 'Ordem do Dia'
    for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=ordem_dia.tip_turno):
        dic_ordem_dia["txt_turno"] = turno.des_turno
        turno = turno.des_turno
    for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem_dia.tip_quorum):
        dic_ordem_dia["txt_quorum"] = quorum.des_quorum
        quorum = quorum.des_quorum
    dic_ordem_dia["txt_exibicao"] =  '<span class="fw-bold">' + materia.des_tipo_materia.upper()+' Nº '+str(materia.num_ident_basica)+"/"+str(materia.ano_ident_basica)+"</span><br/> "+ str(materia.txt_ementa)
    dic_ordem_dia["cod_materia"] = ordem_dia.cod_materia
    dic_ordem_dia["txt_autoria"] = ''
    autores = context.zsql.autoria_obter_zsql(cod_materia=ordem_dia.cod_materia)
    fields = list(autores.data_dictionary().keys())
    lista_autor = []
    for autor in autores:
        for field in fields:
            nome_autor = autor['nom_autor_join']
        lista_autor.append(nome_autor)
    dic_ordem_dia["txt_autoria"] = ', '.join(['%s' % (value) for (value) in lista_autor])
    dic_ordem_dia["ind_extrapauta"] = 0
    dic_ordem_dia["ind_exibicao"] = 0
    itens.append(dic_ordem_dia)

dic_exp_pessoais = {}
dic_exp_pessoais["tipo_item"] = 'Mensagem'
dic_exp_pessoais["cod_sessao_plen"] = cod_sessao_plen
dic_exp_pessoais["nom_fase"] = 'Explicações Pessoais'
dic_exp_pessoais["txt_exibicao"] = '<h1><strong>Explicações Pessoais</strong></h1>'
dic_exp_pessoais["cod_materia"] = ''
dic_exp_pessoais["txt_autoria"] = ''
dic_exp_pessoais["txt_turno"] = ''
dic_exp_pessoais["txt_quorum"] = ''
dic_exp_pessoais["ind_extrapauta"] = 0
dic_exp_pessoais["ind_exibicao"] = 0
itens.append(dic_exp_pessoais)

itens = [(i + 1, j) for i, j in enumerate(itens)]

for i, dic in itens:
  context.zsql.sessao_plenaria_painel_incluir_zsql(tip_item=dic.get('tipo_item',dic), cod_sessao_plen=dic.get('cod_sessao_plen',dic), nom_fase=dic.get('nom_fase',dic), num_ordem=i, txt_exibicao=dic.get('txt_exibicao',dic), cod_materia=dic.get('cod_materia',dic), txt_autoria=dic.get('txt_autoria',dic), txt_turno=dic.get('txt_turno',dic), ind_extrapauta=dic.get('ind_extrapauta',dic), ind_exibicao=dic.get('ind_exibicao',dic))
#   return  i, dic.get('tipo_item',dic), dic.get('nom_fase',dic), dic.get('txt_exibicao',dic), dic.get('cod_materia',dic), dic.get('txt_autoria',dic), dic.get('txt_turno',dic), dic.get('ind_extrapauta',dic), dic.get('ind_exibicao',dic)

redirect_url=context.portal_url()+'/cadastros/acompanhamento_sessao/acompanhamento_sessao_index_html?hdn_cod_sessao_plen=' + cod_sessao_plen
REQUEST.RESPONSE.redirect(redirect_url)
