request=context.REQUEST
response=request.RESPONSE

lst_materia_apresentada=[]

lst_autores_requerimentos = []
lst_requerimentos = []
lst_qtde_requerimentos = []

lst_autores_indicacoes = []
lst_indicacoes = []
lst_qtde_indicacoes = []

lst_autores_mocoes = []
lst_mocoes = []
lst_qtde_mocoes = []

lst_pauta = []
lst_urgencia = []

pauta_dic = {}

tipo_expediente = []
for item in context.zsql.tipo_expediente_obter_zsql(ind_excluido=0):
    dic_expediente = {}
    dic_expediente['cod_expediente'] = item.cod_expediente
    dic_expediente['nom_expediente'] = item.nom_expediente
    tipo_expediente.append(dic_expediente)

cod_sessao_plen = context.REQUEST['cod_sessao_plen']

if request.has_key('ind_audiencia'):
   metodo = context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_audiencia=1, ind_excluido=0)
   for item in metodo:
       for nome in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao,ind_audiencia=1,ind_excluido=0):
           nom_sessao = nome.nom_sessao
else:
   metodo = context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0)
   for item in metodo:
       for nome in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao,ind_excluido=0):
           nom_sessao = nome.nom_sessao

for sessao in metodo:
  data = context.pysc.data_converter_pysc(sessao.dat_inicio_sessao)
  dat_ordem = context.pysc.data_converter_pysc(sessao.dat_inicio_sessao)
  pauta_dic["cod_sessao_plen"] = sessao.cod_sessao_plen
  pauta_dic["num_sessao_plen"] = sessao.num_sessao_plen
  pauta_dic["nom_sessao"] = nom_sessao.upper()
  pauta_dic["num_legislatura"] = sessao.num_legislatura
  pauta_dic["num_sessao_leg"] = sessao.num_sessao_leg
  pauta_dic["dat_inicio_sessao"] = sessao.dat_inicio_sessao
  pauta_dic["dia_sessao"] = context.pysc.data_converter_por_extenso_pysc(data=sessao.dat_inicio_sessao).upper()
  pauta_dic["hr_inicio_sessao"] = sessao.hr_inicio_sessao
  pauta_dic["dat_fim_sessao"] = sessao.dat_fim_sessao
  pauta_dic["hr_fim_sessao"] = sessao.hr_fim_sessao
  pauta_dic["txt_tema"] = sessao.tip_expediente
  pauta_dic["num_periodo"] = ''
  if sessao.cod_periodo_sessao != None:
     for periodo in context.zsql.periodo_sessao_obter_zsql(cod_periodo=sessao.cod_periodo_sessao):
         pauta_dic["num_periodo"] = periodo.num_periodo

  # obtém o nome do Presidente da Câmara titular
  for cargo in context.zsql.cargo_mesa_obter_zsql(ind_excluido=0):
      if cargo.des_cargo == 'Presidente':
         cod_cargo = cargo.cod_cargo
  pauta_dic["presidente"] = ""
  for sleg in context.zsql.periodo_comp_mesa_obter_zsql(num_legislatura=sessao.num_legislatura,data=data):
      for cod_presidente in context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp,cod_cargo=cod_cargo):
          for presidencia in context.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_presidente.cod_parlamentar):
              pauta_dic["presidente"] = presidencia.nom_completo.upper()

  # Materias Apresentadas
  for materia_apresentada in context.zsql.materia_apresentada_sessao_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
      # materias principais
      if materia_apresentada.cod_materia != None:
         materia = context.zsql.materia_obter_zsql(cod_materia=materia_apresentada.cod_materia)[0]
         autores = context.zsql.autoria_obter_zsql(cod_materia=materia_apresentada.cod_materia)
         fields = autores.data_dictionary().keys()
         lista_autor = []
         for autor in autores:
             for field in fields:
                 nome_autor = autor['nom_autor_join']
             lista_autor.append(nome_autor)
         dic_materia = {}
         dic_materia["num_ordem"] = materia_apresentada.num_ordem
         dic_materia["id_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/materia/' + str(materia.cod_materia) + '_texto_integral.pdf' + '">'+materia.des_tipo_materia +' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
         dic_materia['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor])
         dic_materia['txt_ementa'] = context.pysc.convert_unicode_pysc(texto=str(materia.txt_ementa))
         lst_materia_apresentada.append(dic_materia)
      # emendas
      elif materia_apresentada.cod_emenda != None:
           for emenda in context.zsql.emenda_obter_zsql(cod_emenda=materia_apresentada.cod_emenda):
               materia = context.zsql.materia_obter_zsql(cod_materia=emenda.cod_materia)[0]
               autores = context.zsql.autoria_emenda_obter_zsql(cod_emenda=emenda.cod_emenda)
               fields = autores.data_dictionary().keys()
               lista_autor = []
               for autor in autores:
                   for field in fields:
                       nome_autor = autor['nom_autor_join']
                   lista_autor.append(nome_autor)
               dic_materia = {}
               dic_materia["num_ordem"] = materia_apresentada.num_ordem
               dic_materia["id_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/emenda/' + str(materia_apresentada.cod_emenda) + '_emenda.pdf' + '">' + 'Emenda ' + emenda.des_tipo_emenda + ' nº ' + str(emenda.num_emenda) + " ao " +  materia.sgl_tipo_materia +' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) + '</link>'
               dic_materia['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor]) 
               dic_materia['txt_ementa'] = emenda.txt_ementa
           lst_materia_apresentada.append(dic_materia)
      # substitutivos
      elif materia_apresentada.cod_substitutivo != None:
           for substitutivo in context.zsql.substitutivo_obter_zsql(cod_substitutivo=materia_apresentada.cod_substitutivo):
               materia = context.zsql.materia_obter_zsql(cod_materia=substitutivo.cod_materia)[0]
               autores = context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo)
               fields = autores.data_dictionary().keys()
               lista_autor = []
               for autor in autores:
                   for field in fields:
                       nome_autor = autor['nom_autor_join']
                   lista_autor.append(nome_autor)
               dic_materia = {}
               dic_materia["num_ordem"] = materia_apresentada.num_ordem
               dic_materia["id_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/substitutivo/' + str(materia_apresentada.cod_substitutivo) + '_substitutivo.pdf' + '">' + 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + " ao " +  materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) + '</link>'
               dic_materia['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor]) 
               dic_materia['txt_ementa'] = substitutivo.txt_ementa
           lst_materia_apresentada.append(dic_materia)
      # pareceres
      elif materia_apresentada.cod_parecer != None:
           for parecer in context.zsql.relatoria_obter_zsql(cod_relatoria=materia_apresentada.cod_parecer):
               materia = context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia)[0]
               for comissao in context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao):
                   sgl_comissao = comissao.sgl_comissao
                   nom_comissao = comissao.nom_comissao
               autoria = nom_comissao
               dic_materia = {}
               dic_materia["num_ordem"] = materia_apresentada.num_ordem
               dic_materia["id_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/parecer_comissao/' + str(materia_apresentada.cod_parecer) + '_parecer.pdf' + '">' + 'Parecer ' + sgl_comissao+ ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) + " ao " +  materia.sgl_tipo_materia +' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) + '</link>'
               dic_materia['autoria'] = nom_comissao
               dic_materia['txt_ementa'] = ''
           lst_materia_apresentada.append(dic_materia)
      # documentos administrativos
      elif materia_apresentada.cod_documento != None:
           materia = context.zsql.documento_administrativo_obter_zsql(cod_documento=materia_apresentada.cod_documento)[0]
           dic_materia = {}
           dic_materia["num_ordem"] = materia_apresentada.num_ordem
           dic_materia["link_materia"] = '<link href="'+context.sapl_documentos.absolute_url()+'/administrativo/'+ str(materia_apresentada.cod_documento) + '_texto_integral.pdf' +'">'+materia.des_tipo_documento+' nº '+str(materia.num_documento)+'/'+str(materia.ano_documento)+'</link>'
           dic_materia['autoria'] = materia.txt_interessado
           dic_materia['txt_ementa'] = context.pysc.convert_unicode_pysc(texto=str(materia.txt_assunto))
           lst_materia_apresentada.append(materia)

  for item in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,ind_excluido=0):
      if item.cod_materia != None:
         for materia in context.zsql.materia_obter_zsql(cod_materia=item.cod_materia,ind_excluido=0):
             dic_materia = {}
             dic_materia['cod_materia']= str(materia.cod_materia)
             dic_materia['num_ident_basica']= str(materia.num_ident_basica)
             dic_materia["id_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/materia/' + str(materia.cod_materia) + '_texto_integral.pdf' + '">'+materia.des_tipo_materia +' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
             dic_materia['txt_ementa'] = context.pysc.convert_unicode_pysc(texto=str(materia.txt_ementa))
             if materia.des_tipo_materia == 'Indicação':
                dic_autores = {}
                for autoria in context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia):
                    if autoria.ind_primeiro_autor == 1:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                               if parlamentar.sex_parlamentar == 'M':
                                  dic_autores["nom_parlamentar"] = 'Do Vereador' + ' ' + autoria['nom_autor_join']
                               if parlamentar.sex_parlamentar == 'F':
                                  dic_autores["nom_parlamentar"] = 'Da Vereadora' + ' ' + autoria['nom_autor_join']
                    else:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                               if parlamentar.sex_parlamentar == 'M':
                                  dic_autores["nom_parlamentar"] = 'Do Vereador' + ' ' + autoria['nom_autor_join']
                               if parlamentar.sex_parlamentar == 'F':
                                  dic_autores["nom_parlamentar"] = 'Da Vereadora' + ' ' + autoria['nom_autor_join']
                lst_autores_indicacoes.append(dic_autores)
                lst_indicacoes.append(dic_materia)
                lst_qtde_indicacoes.append(materia.cod_materia)
             if materia.des_tipo_materia == 'Requerimento':
                dic_autores = {}
                for autoria in context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia, ind_primeiro_autor = 1):
                    if autoria.ind_primeiro_autor == 1:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                               if parlamentar.sex_parlamentar == 'M':
                                  dic_autores["nom_parlamentar"] = 'Do Vereador' + ' ' + autoria['nom_autor_join']
                               if parlamentar.sex_parlamentar == 'F':
                                  dic_autores["nom_parlamentar"] = 'Da Vereadora' + ' ' + autoria['nom_autor_join']
                    else:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                               if parlamentar.sex_parlamentar == 'M':
                                  dic_autores["nom_parlamentar"] = 'Do Vereador' + ' ' + autoria['nom_autor_join']
                               if parlamentar.sex_parlamentar == 'F':
                                  dic_autores["nom_parlamentar"] = 'Da Vereadora' + ' ' + autoria['nom_autor_join']
                lst_autores_requerimentos.append(dic_autores)
                lst_requerimentos.append(dic_materia)
                lst_qtde_requerimentos.append(materia.cod_materia)
             if materia.des_tipo_materia == 'Moção':
                dic_autores = {}
                for autoria in context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia, ind_primeiro_autor = 1):
                    if autoria.ind_primeiro_autor == 1:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                               if parlamentar.sex_parlamentar == 'M':
                                  dic_autores["nom_parlamentar"] = 'Do Vereador' + ' ' + autoria['nom_autor_join']
                               if parlamentar.sex_parlamentar == 'F':
                                  dic_autores["nom_parlamentar"] = 'Da Vereadora' + ' ' + autoria['nom_autor_join']
                    else:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                               if parlamentar.sex_parlamentar == 'M':
                                  dic_autores["nom_parlamentar"] = 'Do Vereador' + ' ' + autoria['nom_autor_join']
                               if parlamentar.sex_parlamentar == 'F':
                                  dic_autores["nom_parlamentar"] = 'Da Vereadora' + ' ' + autoria['nom_autor_join']
                lst_autores_mocoes.append(dic_autores)
                lst_mocoes.append(dic_materia)
                lst_qtde_mocoes.append(materia.cod_materia)

  # Ordem do Dia
  for ordem in context.zsql.ordem_dia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
    dic = {}
    dic["num_ordem"] = ordem.num_ordem
    if ordem.cod_materia != None:
      materia = context.zsql.materia_obter_zsql(cod_materia=ordem.cod_materia)[0]
      dic["cod_materia"] = ordem.cod_materia
      dic["cod_parecer"] = ''
      dic["id_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/materia/' + str(materia.cod_materia) + '_texto_integral.pdf' + '">'+materia.des_tipo_materia +' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
      dic["txt_ementa"] = context.pysc.convert_unicode_pysc(texto=str(ordem.txt_observacao))
      dic["des_turno"]=""
      for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
         dic["des_turno"] = turno.des_turno
      dic["des_quorum"]=""
      for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem.tip_quorum):
         dic["des_quorum"] = quorum.des_quorum
      dic["tip_votacao"]=""
      for tip_votacao in context.zsql.tipo_votacao_obter_zsql(tip_votacao=ordem.tip_votacao):
         dic["tip_votacao"] = tip_votacao.des_tipo_votacao
      dic["nom_autor"] = ""
      autores = context.zsql.autoria_obter_zsql(cod_materia=ordem.cod_materia)
      fields = autores.data_dictionary().keys()
      lista_autor = []
      for autor in autores:
          for field in fields:
              nome_autor = autor['nom_autor_join']
          lista_autor.append(nome_autor)
      dic["nom_autor"] = ', '.join(['%s' % (value) for (value) in lista_autor])
      dic["parecer"] = ''
      lst_qtde_pareceres = []
      lst_pareceres = []
      for relatoria in context.zsql.relatoria_obter_zsql(cod_materia=ordem.cod_materia):
          dic_parecer = {}
          comissao = context.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao)[0]
          relator = context.zsql.parlamentar_obter_zsql(cod_parlamentar=relatoria.cod_parlamentar)[0]
          dic_parecer['relatoria'] = 'Relatoria: ' + relator.nom_parlamentar
          dic_parecer['comissao'] = comissao.nom_comissao
          dic_parecer['conclusao'] = ''
          if relatoria.tip_conclusao == 'F':
             dic_parecer['conclusao'] = 'Favorável à aprovação da matéria.'
          elif relatoria.tip_conclusao == 'C':
             dic_parecer['conclusao'] = 'Contrário à aprovação da matéria.'
          dic_parecer["id_parecer"] = '<link href="' + context.sapl_documentos.absolute_url() + '/parecer_comissao/' + str(relatoria.cod_relatoria) + '_parecer.pdf' + '">' + 'Parecer ' + comissao.sgl_comissao + ' nº ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + '</link>'
          if relatoria.num_parecer != None and int(ordem.tip_turno) != 4 :
             lst_pareceres.append(dic_parecer)
             lst_qtde_pareceres.append(relatoria.cod_relatoria)
      dic["pareceres"] = lst_pareceres
      dic["parecer"] = len(lst_qtde_pareceres)

      dic["substitutivo"] = ''
      lst_qtde_substitutivos=[]
      lst_substitutivos=[]
      for substitutivo in context.zsql.substitutivo_obter_zsql(cod_materia=ordem.cod_materia,ind_excluido=0):
          autores = context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo, ind_excluido=0)
          dic_substitutivo = {}
          fields = autores.data_dictionary().keys()
          lista_autor = []
          for autor in autores:
              for field in fields:
                  nome_autor = autor['nom_autor_join']
              lista_autor.append(nome_autor)
          autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
          dic_substitutivo["id_substitutivo"] = '<link href="' + context.sapl_documentos.absolute_url() + '/substitutivo/' + str(substitutivo.cod_substitutivo) + '_substitutivo.pdf' + '">' + 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + '</link>'
          dic_substitutivo["txt_ementa"] = substitutivo.txt_ementa
          dic_substitutivo["autoria"] = autoria
          if int(ordem.tip_turno) != 4:
             lst_substitutivos.append(dic_substitutivo)
             cod_substitutivo = substitutivo.cod_substitutivo
             lst_qtde_substitutivos.append(cod_substitutivo)
      dic["substitutivos"] = lst_substitutivos
      dic["substitutivo"] = len(lst_qtde_substitutivos)

      dic["emenda"] = ''
      lst_qtde_emendas=[]
      lst_emendas=[]
      for emenda in context.zsql.emenda_obter_zsql(cod_materia=ordem.cod_materia,ind_excluido=0,exc_pauta=0):
          autores = context.zsql.autoria_emenda_obter_zsql(cod_emenda=emenda.cod_emenda,ind_excluido=0)
          dic_emenda = {}
          fields = autores.data_dictionary().keys()
          lista_autor = []
          for autor in autores:
              for field in fields:
                  nome_autor = autor['nom_autor_join']
              lista_autor.append(nome_autor)
          autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
          dic_emenda["id_emenda"] = '<link href="' + context.sapl_documentos.absolute_url() + '/emenda/' + str(emenda.cod_emenda) + '_emenda.pdf' + '">' + 'Emenda ' + emenda.des_tipo_emenda + ' nº ' + str(emenda.num_emenda) +'</link>'
          dic_emenda["txt_ementa"] = emenda.txt_ementa
          dic_emenda["autoria"] = autoria
          if int(ordem.tip_turno) != 4:
             lst_emendas.append(dic_emenda)
             cod_emenda = emenda.cod_emenda
             lst_qtde_emendas.append(cod_emenda)
      dic["emendas"] = lst_emendas
      dic["emenda"] = len(lst_qtde_emendas)
      
    elif ordem.cod_parecer != None:
         relatoria = context.zsql.relatoria_obter_zsql(cod_relatoria=ordem.cod_parecer)[0]
         for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
             dic["des_turno"] = str(turno.des_turno)
             dic["cod_turno"] = int(turno.cod_turno)
         for comissao in context.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao):
             sgl_comissao = comissao.sgl_comissao
             nom_comissao = comissao.nom_comissao
         for resultado in context.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=relatoria.tip_fim_relatoria):
             resultado_comissao = ' (' + resultado.des_fim_relatoria + ')'
         for mat in context.zsql.materia_obter_zsql(cod_materia=relatoria.cod_materia):
             id_mat = ' ao ' + str(mat.des_tipo_materia) + ' nº ' + str(mat.num_ident_basica) + '/' + str(mat.ano_ident_basica)
         dic["id_materia"] = '<link href="'+context.sapl_documentos.absolute_url()+'/parecer_comissao/'+ str(relatoria.cod_relatoria) + '_parecer.pdf' +'">' + 'PARECER ' + sgl_comissao + ' N° ' +str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + '</link>'
         dic["txt_ementa"] = ordem.txt_observacao
         dic['nom_autor'] = str(nom_comissao)
         dic["des_quorum"]=""
         for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem.tip_quorum):
             dic["des_quorum"] = quorum.des_quorum
         dic["tip_votacao"]=""
         for tip_votacao in context.zsql.tipo_votacao_obter_zsql(tip_votacao=ordem.tip_votacao):
             dic["tip_votacao"] = 'Votação ' + str(tip_votacao.des_tipo_votacao)
         dic["parecer"] = ''
         dic["substitutivo"] = ''
         dic["emenda"] = ''

    if ordem.urgencia == 1:
       lst_urgencia.append(dic)
    else:
       lst_pauta.append(dic)

# ordena materias por antiguidade
lst_indicacoes.sort(key=lambda dic: dic['num_ident_basica'])
lst_requerimentos.sort(key=lambda dic: dic['num_ident_basica'])
lst_mocoes.sort(key=lambda dic: dic['num_ident_basica'])

# setar apenas uma ocorrência de nome parlamentar
lst_autores_indicacoes = [
    e
    for i, e in enumerate(lst_autores_indicacoes)
    if lst_autores_indicacoes.index(e) == i
]
lst_autores_requerimentos = [
    e
    for i, e in enumerate(lst_autores_requerimentos)
    if lst_autores_requerimentos.index(e) == i
]
lst_autores_mocoes = [
    e
    for i, e in enumerate(lst_autores_mocoes)
    if lst_autores_mocoes.index(e) == i
]

lst_indicacoes_vereadores = []
for autor in lst_autores_indicacoes:
    dic_vereador = {}
    dic_vereador['vereador'] = autor.get('nom_parlamentar',autor)
    lst_materias=[]
    lst_qtde_materias=[]
    for materia in lst_indicacoes:
        dic_materias = {}
        if materia.get('cod_autor',materia) == autor.get('cod_autor',autor):
           dic_materias['id_materia'] = materia.get('id_materia',materia)
           dic_materias['txt_ementa'] = materia.get('txt_ementa',materia)
           lst_materias.append(dic_materias)
           lst_qtde_materias.append(materia.get('cod_materia',materia))
    dic_vereador['materias'] = lst_materias
    dic_vereador['qtde_materias'] = len(lst_qtde_materias)
    lst_indicacoes_vereadores.append(dic_vereador)

lst_requerimentos_vereadores = []
for autor in lst_autores_requerimentos:
    dic_vereador = {}
    dic_vereador['vereador'] = autor.get('nom_parlamentar',autor)
    lst_materias=[]
    lst_qtde_materias=[]
    for materia in lst_requerimentos:
        dic_materias = {}
        if materia.get('cod_autor',materia) == autor.get('cod_autor',autor):
           dic_materias['id_materia'] = materia.get('id_materia',materia)
           dic_materias['txt_ementa'] = materia.get('txt_ementa',materia)
           lst_materias.append(dic_materias)
           lst_qtde_materias.append(materia.get('cod_materia',materia))
    dic_vereador['materias'] = lst_materias
    dic_vereador['qtde_materias'] = len(lst_qtde_materias)
    lst_requerimentos_vereadores.append(dic_vereador)

lst_mocoes_vereadores = []
for autor in lst_autores_mocoes:
    dic_vereador = {}
    dic_vereador['vereador'] = autor.get('nom_parlamentar',autor)
    lst_materias=[]
    lst_qtde_materias=[]
    for materia in lst_mocoes:
        dic_materias = {}
        if materia.get('cod_autor',materia) == autor.get('cod_autor',autor):
           dic_materias['id_materia'] = materia.get('id_materia',materia)
           dic_materias['txt_ementa'] = materia.get('txt_ementa',materia)
           lst_materias.append(dic_materias)
           lst_qtde_materias.append(materia.get('cod_materia',materia))
    dic_vereador['materias'] = lst_materias
    dic_vereador['qtde_materias'] = len(lst_qtde_materias)
    lst_mocoes_vereadores.append(dic_vereador)

pauta_dic["lst_qtde_requerimentos"] = len(lst_qtde_requerimentos)
pauta_dic["lst_materia_apresentada"] = lst_materia_apresentada
pauta_dic["lst_autores_requerimentos"] = lst_autores_requerimentos
pauta_dic["lst_requerimentos_vereadores"] = lst_requerimentos_vereadores

pauta_dic["lst_qtde_mocoes"] = len(lst_qtde_mocoes)
pauta_dic["lst_autores_mocoes"] = lst_autores_mocoes
pauta_dic["lst_mocoes_vereadores"] = lst_mocoes_vereadores

pauta_dic["lst_qtde_indicacoes"] = len(lst_qtde_indicacoes)
pauta_dic["lst_autores_indicacoes"] = lst_autores_indicacoes
pauta_dic["lst_indicacoes_vereadores"] = lst_indicacoes_vereadores

pauta_dic["lst_pauta"] = lst_pauta
pauta_dic["lst_urgencia"] = lst_urgencia

lst_expedientes = []
for tipo in context.zsql.tipo_expediente_obter_zsql(ind_excluido=0):
    dic_expediente = {}
    dic_expediente['nom_expediente'] = tipo.nom_expediente
    dic_expediente["conteudo"] = ''
    for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=cod_sessao_plen, cod_expediente=tipo.cod_expediente, ind_excluido=0):
        dic_expediente["conteudo"] = item.txt_expediente
    if dic_expediente["conteudo"] != '':
        lst_expedientes.append(dic_expediente)

pauta_dic["lst_expedientes"] = lst_expedientes

# obtém as propriedades da casa legislativa para montar o cabeçalho e o rodapé da página
casa = {}
aux=context.sapl_documentos.props_sagl.propertyItems()
for item in aux:
    casa[item[0]] = item[1]

# obtém a localidade
localidade = context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])
# monta o cabeçalho da página
cabecalho = {}
estados = context.zsql.localidade_obter_zsql(tip_localidade="U")
for uf in estados:
    if localidade[0].sgl_uf == uf.sgl_uf:
       nom_estado = uf.nom_localidade
       break
cabecalho["nom_casa"] = casa["nom_casa"]
cabecalho["nom_estado"] = nom_estado

# tenta buscar o logotipo da casa LOGO_CASA
if hasattr(context.sapl_documentos.props_sagl,'logo_casa.gif'):
   imagem = context.sapl_documentos.props_sagl['logo_casa.gif'].absolute_url()
else:
   imagem = context.imagens.absolute_url() + "/brasao.gif"
# monta o rodapé da página
num_cep = casa["num_cep"]
if len(casa["num_cep"]) == 8:
   num_cep=casa["num_cep"][:4]+"-"+casa["num_cep"][5:]
linha1 = casa["end_casa"] 
if num_cep!=None and num_cep!="":
   if casa["end_casa"]!="" and casa["end_casa"]!=None:
      linha1 = linha1 +"  "
   linha1 = linha1 +" CEP: "+num_cep
if localidade[0].nom_localidade!=None and localidade[0].nom_localidade!="":
   linha1 = linha1 +"   "+localidade[0].nom_localidade +" - "+localidade[0].sgl_uf
if casa["num_tel"]!=None and casa["num_tel"]!="":
   linha1 = linha1 +"   Tel.: "+casa["num_tel"]

linha2 = casa["end_web_casa"]

dat_emissao = DateTime(datefmt='international').strftime("%d/%m/%Y")
rodape = [linha1, linha2, dat_emissao]

caminho = context.pdf_ordem_dia_gerar(cabecalho, rodape, imagem, pauta_dic)
response.redirect(caminho)
