## Script (Python) "ata_gerar"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_sessao_plen
##title=
##

from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE

cod_sessao_plen = context.REQUEST['cod_sessao_plen']

if 'ind_audiencia' in REQUEST:
   nom_modelo = 'ata_audiencia.odt'
   metodo = context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_audiencia=1, ind_excluido=0)
   for item in metodo:
       for nome in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao,ind_audiencia=1,ind_excluido=0):
           nom_sessao = nome.nom_sessao
else:
   nom_modelo = 'ata.odt'
   metodo = context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0)
   for item in metodo:
       for nome in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao,ind_excluido=0):
           nom_sessao = nome.nom_sessao

for sessao in metodo:
  nom_arquivo = str(cod_sessao_plen)+'_ata_sessao.odt'
  ata_dic = {}
  ata_dic["cod_sessao_plen"] = sessao.cod_sessao_plen
  ata_dic["num_sessao_plen"] = sessao.num_sessao_plen
  #ata_dic["num_tip_sessao"] = sessao.num_tip_sessao #CM Jaboticabal
  ata_dic["nom_sessao"] = nom_sessao
  ata_dic["num_legislatura"] = sessao.num_legislatura
  ata_dic["num_sessao_leg"] = sessao.num_sessao_leg
  ata_dic["dat_inicio_sessao"] = sessao.dat_inicio_sessao
  ata_dic["dia_sessao"] = context.pysc.data_converter_por_extenso_pysc(data=sessao.dat_inicio_sessao)
  ata_dic["hr_inicio_sessao"] = sessao.hr_inicio_sessao
  ata_dic["dat_fim_sessao"] = sessao.dat_fim_sessao
  ata_dic["hr_fim_sessao"] = sessao.hr_fim_sessao
  if sessao.numero_ata != None:
     ata_dic["numero_ata"] = sessao.numero_ata
  else:
     ata_dic["numero_ata"] = sessao.num_sessao_plen
  ata_dic["ano_sessao"] = sessao.ano_sessao
  if nom_sessao == 'Audiência Pública':
     ata_dic["txt_tema"] = sessao.tip_expediente
     ata_dic["url_video"] = '<p>A audiência está disponibilizada na íntegra, em vídeo, através do endereço eletrônico: ' + '<a href="'+ sessao.url_video +'" target="_blank">' + str(sessao.num_sessao_plen) + 'ª' + nom_sessao + '</a></p>' 
  else:
     ata_dic["txt_tema"] = ''
     ata_dic["url_video"] = '<p>A gravação do evento sessão está disponibilizada na íntegra, em vídeo, através do endereço eletrônico: ' + '<a href="'+ sessao.url_video +'" target="_blank">' + str(sessao.num_sessao_plen) + 'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + nom_sessao + '</a></p>' 
  nom_modelo = nom_modelo
  ata_dic['nom_usuario'] = ''
  for usuario in context.zsql.usuario_obter_zsql(col_username=REQUEST['AUTHENTICATED_USER'].getUserName()):
      ata_dic['nom_usuario'] = usuario.nom_completo

  # Mesa Diretora da Sessao
  lst_mesa = []
  for composicao in context.zsql.composicao_mesa_sessao_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,ind_excluido=0):
      for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=composicao.cod_parlamentar,ind_excluido=0):
          for cargo in context.zsql.cargo_mesa_obter_zsql(cod_cargo=composicao.cod_cargo, ind_excluido=0):
              dic_mesa = {}
              dic_mesa['nom_completo'] = parlamentar.nom_completo
              dic_mesa['sgl_partido'] = parlamentar.sgl_partido
              dic_mesa['des_cargo'] = cargo.des_cargo
              lst_mesa.append(dic_mesa)

  ata_dic["lst_mesa"] = lst_mesa

  # Presenca na Sessao
  ata_dic["qtde_presenca_sessao"] = ""
  ata_dic["lst_presenca_sessao"] = ""
  ata_dic["qtde_ausencia_sessao"] = ""
  ata_dic["lst_ausencia_sessao"] = ""
  lst_presenca_sessao = []
  lst_ausencia_sessao = []

  for presenca in context.zsql.presenca_sessao_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
      if presenca.tip_frequencia == 'P':
         for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca.cod_parlamentar,ind_excluido=0):
             nom_completo = parlamentar.nom_completo
             lst_presenca_sessao.append(nom_completo)
      elif presenca.tip_frequencia != 'P':
         for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca.cod_parlamentar,ind_excluido=0):
             nom_completo = parlamentar.nom_completo
             lst_ausencia_sessao.append(nom_completo)

  ata_dic["qtde_presenca_sessao"] = len(lst_presenca_sessao)
  ata_dic["lst_presenca_sessao"] = ', '.join(['%s' % (value) for (value) in lst_presenca_sessao])

  ata_dic["qtde_ausencia_sessao"] = len(lst_ausencia_sessao)
  ata_dic["lst_ausencia_sessao"] = ', '.join(['%s' % (value) for (value) in lst_ausencia_sessao])

  # Materias Apresentadas
  lst_materia_apresentada=[]
  for materia_apresentada in context.zsql.materia_apresentada_sessao_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,ind_excluido=0):
      if materia_apresentada.cod_materia != None:
         materia = context.zsql.materia_obter_zsql(cod_materia=materia_apresentada.cod_materia)[0]
         autores = context.zsql.autoria_obter_zsql(cod_materia=materia_apresentada.cod_materia)
         fields = autores.data_dictionary().keys()
         lista_autor = []
         for autor in autores:
             for field in fields:
                 nome_autor = autor['nom_autor_join']
             lista_autor.append(nome_autor)
         autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
         materia = '<a href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+materia.cod_materia+'">'+str(materia.des_tipo_materia)+ ' nº ' +str(materia.num_ident_basica)+"/"+str(materia.ano_ident_basica) + '</a> - ' + autoria +" - " +materia.txt_ementa
         lst_materia_apresentada.append(materia)
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
               autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
               materia = '<a href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+materia.cod_materia+'">'+ 'Emenda ' + str(emenda.des_tipo_emenda) + ' nº ' + str(emenda.num_emenda) + ' ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) + '</a> - ' + autoria + ' - ' + emenda.txt_ementa
           lst_materia_apresentada.append(materia)
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
               autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
               materia = '<a href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+materia.cod_materia+'">' + 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + ' ao ' + materia.sgl_tipo_materia + ' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) + '</a> - ' + autoria +' - ' + substitutivo.txt_ementa
           lst_materia_apresentada.append(materia)
      elif materia_apresentada.cod_parecer != None:
           for parecer in context.zsql.relatoria_obter_zsql(cod_relatoria=materia_apresentada.cod_parecer):
               materia = context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia)[0]
               for comissao in context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao):
                   sgl_comissao = comissao.sgl_comissao
               materia = '<a href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+materia.cod_materia+'">' + 'Parecer ' + str(sgl_comissao) + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) + ' ao ' + str(materia.sgl_tipo_materia) +' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) + '</a> - ' + autoria + ' - ' + materia_apresentada.txt_observacao
           lst_materia_apresentada.append(materia)
      elif materia_apresentada.cod_documento != None:
           materia = context.zsql.documento_administrativo_obter_zsql(cod_documento=materia_apresentada.cod_documento)[0]
           materia = '<a href="'+context.consultas.absolute_url()+'/documento_administrativo/documento_administrativo_mostrar_proc?cod_documento='+materia.cod_documento+'">' + str(materia.des_tipo_documento) + ' nº ' +str(materia.num_documento)+'/'+str(context.pysc.ano_abrevia_pysc(ano=str(materia.ano_documento)))+ '</a> - '+ materia.txt_interessado + ' - ' + materia.txt_assunto
           lst_materia_apresentada.append(materia)

  ata_dic["lst_materia_apresentada"] = '; '.join(['%s' % (value) for (value) in lst_materia_apresentada])

  lst_expedientes = []
  for tipo in context.zsql.tipo_expediente_obter_zsql(ind_excluido=0):
      dic_expediente = {}
      dic_expediente['nom_expediente'] = tipo.nom_expediente
      dic_expediente["conteudo"] = ''
      for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, cod_expediente=tipo.cod_expediente, ind_excluido=0):
          dic_expediente["conteudo"] = item.txt_expediente
      if dic_expediente["conteudo"] != '':
          lst_expedientes.append(dic_expediente)

  ata_dic["lst_expedientes"] = lst_expedientes

  # Insercoes em Ata
  ata_dic["insercao"] = ''
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,cod_expediente=9,ind_excluido=0):
      ata_dic["insercao"] = item.txt_expediente

  # Ata Sessao Anterior
  ata_dic["ata_anterior"] = ''
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,cod_expediente=6,ind_excluido=0):
      ata_dic["ata_anterior"] = item.txt_expediente

  # Expedientes Executivo
  ata_dic["expedientes_executivo"] = ""
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,cod_expediente=1,ind_excluido=0):
      ata_dic["expedientes_executivo"] = item.txt_expediente

  # Expedientes Diversos
  ata_dic["expedientes_diversos"] = ""
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,cod_expediente=2,ind_excluido=0):
      ata_dic["expedientes_diversos"] = item.txt_expediente

  # Expedientes acessorios
  ata_dic["expedientes_acessorios"] = ""
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,cod_expediente=8,ind_excluido=0):
      ata_dic["expedientes_acessorios"] = item.txt_expediente

  # Tribuna do Cidadao
  ata_dic["tribuna_cidadao"] = ""
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,cod_expediente=10,ind_excluido=0):
      ata_dic["tribuna_cidadao"] = item.txt_expediente

  # Descontinuado
  lst_reqplen = ''
  lst_reqpres = ''

  # Indicacoes
  lst_indicacao = []
  lst_num_ind = []

  # Requerimentos
  lst_requerimento = []
  lst_num_req = []

  # Mocoes
  lst_mocao=[]

  # Pareceres
  lst_parecer = []

  for item in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,ind_excluido=0):
      # Materias Legislativas
      if item.cod_materia != None:
         for materia in context.zsql.materia_obter_zsql(cod_materia=item.cod_materia,ind_excluido=0):
             # Indicações
             if materia.des_tipo_materia == 'Indicação':
                autores = context.zsql.autoria_obter_zsql(cod_materia=item.cod_materia)
                fields = autores.data_dictionary().keys()
                lista_autor = []
                for autor in autores:
                    for field in fields:
                        nome_autor = autor['nom_autor_join']
                    lista_autor.append(nome_autor)
                autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
                for votacao in context.zsql.votacao_expediente_materia_obter_zsql(cod_materia=item.cod_materia, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
                    if votacao.tip_resultado_votacao:
                       resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao = votacao.tip_resultado_votacao, ind_excluido=0)
                       for i in resultado:
                           votacao_observacao = ""
                           if votacao.votacao_observacao:
                              votacao_observacao = ' - ' + votacao.votacao_observacao
                           nom_resultado = ' (' + i.nom_resultado + votacao_observacao + ')'
                    else:
                       nom_resultado = "(Matéria não votada)"
                       votacao_observacao = ""
                num_ident_basica = materia.num_ident_basica
                materia = '<a href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+ str(materia.cod_materia) + '">' + str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' +str(materia.ano_ident_basica) + "</a> - " + str(autoria) + " - " + str(materia.txt_ementa) + str(nom_resultado)
                lst_indicacao.append(materia)
                lst_num_ind.append(num_ident_basica)
             # Requerimentos
             elif materia.des_tipo_materia == 'Requerimento':
                autores = context.zsql.autoria_obter_zsql(cod_materia=item.cod_materia)
                fields = autores.data_dictionary().keys()
                lista_autor = []
                for autor in autores:
                    for field in fields:
                        nome_autor = autor['nom_autor_join']
                    lista_autor.append(nome_autor)
                autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
                for votacao in context.zsql.votacao_expediente_materia_obter_zsql(cod_materia=item.cod_materia, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
                    if votacao.tip_resultado_votacao:
                       resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao = votacao.tip_resultado_votacao, ind_excluido=0)
                       for i in resultado:
                           votacao_observacao = ""
                           if votacao.votacao_observacao:
                              votacao_observacao = ' - ' + votacao.votacao_observacao
                           nom_resultado = ' (' + i.nom_resultado + votacao_observacao + ')'
                    else:
                       nom_resultado = "(Matéria não votada)"
                       votacao_observacao = ""
                num_ident_basica = materia.num_ident_basica
                # Oradores que discutiram a materia
                lst_discussao_materia = []
                for discussao in context.zsql.discussao_expediente_obter_zsql(cod_ordem=item.cod_ordem, ind_excluido=0):
                    nom_parlamentar = discussao.nom_parlamentar
                    lst_discussao_materia.append(nom_parlamentar)
                discussao = ''
                if len(lst_discussao_materia) >= 1:
                   discussao = ' Uso da palavra: ' + ', '.join(['%s' % (value) for (value) in lst_discussao_materia]) + '.'
                materia = '<a href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+ str(materia.cod_materia) + '">' + str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' +str(materia.ano_ident_basica) + "</a> - " + str(autoria) + " - " + str(materia.txt_ementa) + str(discussao) + str(nom_resultado)
                lst_requerimento.append(materia)
                lst_num_req.append(num_ident_basica)
             # Moções
             elif materia.des_tipo_materia == 'Moção':
                autores = context.zsql.autoria_obter_zsql(cod_materia=item.cod_materia)
                fields = autores.data_dictionary().keys()
                lista_autor = []
                for autor in autores:
                    for field in fields:
                        nome_autor = autor['nom_autor_join']
                    lista_autor.append(nome_autor)
                autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
                for votacao in context.zsql.votacao_expediente_materia_obter_zsql(cod_materia=item.cod_materia, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
                    if votacao.tip_resultado_votacao:
                       resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao = votacao.tip_resultado_votacao, ind_excluido=0)
                       for i in resultado:
                           votacao_observacao = ""
                           if votacao.votacao_observacao:
                              votacao_observacao = ' - ' + votacao.votacao_observacao
                           nom_resultado = ' (' + i.nom_resultado + votacao_observacao + ')'
                    else:
                       nom_resultado = ""
                       votacao_observacao = ""
                # Oradores que discutiram a materia
                lst_discussao_materia = []
                for discussao in context.zsql.discussao_expediente_obter_zsql(cod_ordem=item.cod_ordem, ind_excluido=0):
                    nom_parlamentar = discussao.nom_parlamentar
                    lst_discussao_materia.append(nom_parlamentar)
                discussao = ''
                if len(lst_discussao_materia) >= 1:
                   discussao = ' Uso da palavra: ' + ', '.join(['%s' % (value) for (value) in lst_discussao_materia]) + '.'
                materia = '<a href="'+context.consultas.absolute_url()+ '/materia/materia_mostrar_proc?cod_materia='+ str(materia.cod_materia) + '">' + str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' +str(materia.ano_ident_basica) + "</a> - " + str(autoria) + " - " + str(materia.txt_ementa) + str(discussao) + str(nom_resultado)
                lst_mocao.append(materia)
      # Pareceres
      elif item.cod_parecer != None:
           for parecer in context.zsql.relatoria_obter_zsql(cod_relatoria=item.cod_parecer,ind_excluido=0):
               for materia in context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia, ind_excluido=0):
                   sgl_tipo_materia = materia.sgl_tipo_materia
                   num_ident_basica = materia.num_ident_basica
                   ano_ident_basica = materia.ano_ident_basica
               for comissao in context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao):
                   sgl_comissao = comissao.sgl_comissao
               for votacao in context.zsql.votacao_expediente_materia_obter_zsql(cod_materia=item.cod_parecer, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
                   if votacao.tip_resultado_votacao:
                      resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao = votacao.tip_resultado_votacao, ind_excluido=0)
                      for i in resultado:
                          votacao_observacao = ""
                          if votacao.votacao_observacao:
                             votacao_observacao = ' - ' + votacao.votacao_observacao
                          nom_resultado = ' (' + i.nom_resultado + votacao_observacao + ')'
                   else:
                      nom_resultado = "(Parecer não votado)"
                      votacao_observacao = ""
               materia = '<a href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+materia.cod_materia+'">' + 'Parecer ' + str(sgl_comissao) + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) + ' ao ' + str(sgl_tipo_materia) + ' ' + str(num_ident_basica) + '/' + str(ano_ident_basica) + '</a> - '  + str(item.txt_observacao)  + str(nom_resultado)
               lst_parecer.append(materia)

  # Juntar Indicações
  ata_dic["indicacao"] = '; '.join(['%s' % (value) for (value) in lst_indicacao])
  if lst_num_ind != []:
     ata_dic["min_ind"] = min(lst_num_ind)
     ata_dic["max_ind"] = max(lst_num_ind)
  else:
     ata_dic["min_ind"] = ''
     ata_dic["max_ind"] = ''

  # Juntar Requerimentos
  ata_dic["requerimento"] = '; '.join(['%s' % (value) for (value) in lst_requerimento])
  if lst_num_req != []:
     ata_dic["min_req"] = min(lst_num_req)
     ata_dic["max_req"] = max(lst_num_req)
  else:
     ata_dic["min_req"] = ''
     ata_dic["max_req"] = ''

  # Juntar Mocoes
  ata_dic["mocao"] = '; '.join(['%s' % (value) for (value) in lst_mocao])

  # Juntar Pareceres
  ata_dic["parecer"] = '; '.join(['%s' % (value) for (value) in lst_parecer])

  # Lista de oradores
  lst_oradores = []
  for orador in context.zsql.oradores_expediente_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
      for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=orador.cod_parlamentar,ind_excluido=0):
          dic_orador = {}
          dic_orador['num_ordem'] = orador.num_ordem
          dic_orador['nom_completo'] = parlamentar.nom_completo
          lst_oradores.append(dic_orador)
  ata_dic["lst_oradores"] = lst_oradores

  # Lista presenca na ordem do dia
  lst_presenca_ordem_dia = []
  lst_ausencia_ordem_dia = []

  for presenca_ordem_dia in context.zsql.presenca_ordem_dia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
      if presenca_ordem_dia.tip_frequencia == 'P':
         for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca_ordem_dia.cod_parlamentar,ind_excluido=0):
             nom_completo = parlamentar.nom_completo
             lst_presenca_ordem_dia.append(nom_completo)
      elif presenca_ordem_dia.tip_frequencia != 'P':
         for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=presenca_ordem_dia.cod_parlamentar,ind_excluido=0):
             nom_completo = parlamentar.nom_completo
             lst_ausencia_ordem_dia.append(nom_completo)

  ata_dic["qtde_presenca_ordem_dia"] = len(lst_presenca_ordem_dia)
  ata_dic["lst_presenca_ordem_dia"] = ', '.join(['%s' % (value) for (value) in lst_presenca_ordem_dia])
  ata_dic["qtde_ausencia_ordem_dia"] = len(lst_ausencia_ordem_dia)
  ata_dic["lst_ausencia_ordem_dia"] = ', '.join(['%s' % (value) for (value) in lst_ausencia_ordem_dia])

  # Matérias da Ordem do Dia com resultados das votacões
  lst_urgencia=[]
  lst_votacao=[]
  for ordem in context.zsql.ordem_dia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
      dic_votacao = {}
      dic_votacao["num_ordem"] = ordem.num_ordem
      des_turno = ''
      for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
         des_turno = turno.des_turno
      urgencia = ordem.urgencia
      if ordem.cod_materia != None:
         materia = context.zsql.materia_obter_zsql(cod_materia=ordem.cod_materia)[0]
         autores = context.zsql.autoria_obter_zsql(cod_materia=ordem.cod_materia)
         fields = autores.data_dictionary().keys()
         lista_autor = []
         for autor in autores:
             for field in fields:
                 nome_autor = autor['nom_autor_join']
             lista_autor.append(nome_autor)
         autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
         nom_resultado = ''
         for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_materia=ordem.cod_materia, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
             votacao_nominal = ''
             if ordem.tip_votacao == 2:
                 lst_nominal = []
                 for votos in context.zsql.votacao_parlamentar_obter_zsql(cod_votacao = votacao.cod_votacao, ind_excluido=0):
                     votos_nominais = votos.nom_completo + ': ' + votos.vot_parlamentar
                     lst_nominal.append(votos_nominais)
                 votacao_nominal = ', '.join(['%s' % (value) for (value) in lst_nominal])
                 votacao_nominal = ' - ' + votacao_nominal
             contagem_votos = ''
             if votacao.tip_votacao == 2:
                 if votacao.num_votos_sim == 0:
                    votos_favoraveis = ''
                 elif votacao.num_votos_sim == 1:
                    votos_favoraveis = ' - ' +str(votacao.num_votos_sim) + " voto favorável"
                 elif votacao.num_votos_sim > 1:
                    votos_favoraveis = ' - ' + str(votacao.num_votos_sim) + " votos favoráveis"
                 if votacao.num_votos_nao == 0:
                    votos_contrarios = ''
                 elif votacao.num_votos_nao == 1:
                    votos_contrarios = ' - ' + str(votacao.num_votos_nao) + " voto contrário"
                 elif votacao.num_votos_nao > 1:
                    votos_contrarios = ' - ' + str(votacao.num_votos_nao) + " votos contrários"
                 if votacao.num_abstencao == 0:
                    abstencoes = ''
                 elif votacao.num_abstencao == 1:
                    abstencoes = ' - ' + str(votacao.num_abstencao) + " abstenção"
                 elif votacao.num_abstencao > 1:
                    abstencoes =  ' - ' + str(votacao.num_abstencao) + " abstenções"
                 if votacao.num_ausentes == 0 or votacao.num_ausentes == None:
                    ausentes = ''
                 elif votacao.num_ausentes == 1:
                    ausentes = ' - ' + str(votacao.num_ausentes) + " ausência"
                 elif votacao.num_ausentes > 1:
                    ausentes =  ' - ' + str(votacao.num_ausentes) + " ausências"
                 contagem_votos = votos_favoraveis + votos_contrarios + abstencoes + ausentes
             if votacao.votacao_observacao != '':
                votacao_observacao = ' - ' + votacao.votacao_observacao
             else:
                votacao_observacao = ''
             if votacao.tip_resultado_votacao:
                for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=votacao.tip_turno):
                    turno_discussao = turno.des_turno
                resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
                for i in resultado:
                    nom_resultado= ' (' + i.nom_resultado+ ' em ' + turno_discussao + contagem_votos + votacao_nominal + votacao_observacao + ')'
             else:
                nom_resultado = " (Matéria não votada)"
                votacao_observacao = ''
         # Oradores que discutiram a materia
         lst_discussao_materia = []
         for discussao in context.zsql.discussao_ordem_dia_obter_zsql(cod_ordem=ordem.cod_ordem, ind_excluido=0):
             nom_parlamentar = discussao.nom_parlamentar
             lst_discussao_materia.append(nom_parlamentar)
         discussao = ''
         if len(lst_discussao_materia) >= 1:
            discussao = ' Uso da palavra: ' + ', '.join(['%s' % (value) for (value) in lst_discussao_materia]) + '.'
         dic_votacao["materia"] = '<b>Item ' + str(ordem.num_ordem) + '</b> - ' + str(des_turno) + ' do <a href="'+context.consultas.absolute_url() +'/materia/materia_mostrar_proc?cod_materia=' + str(materia.cod_materia) +'">' + str(materia.des_tipo_materia) + " nº " + str(materia.num_ident_basica) + "/" + str(materia.ano_ident_basica) + '</a> - ' + str(autoria) + ' - ' + str(materia.txt_ementa) + str(discussao) + str(nom_resultado)

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
             nom_resultado = ''
             for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
                if votacao.votacao_observacao != '':
                   votacao_observacao = ' - ' + votacao.votacao_observacao
                else:
                   votacao_observacao = ''
                if votacao.tip_resultado_votacao:
                   for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=votacao.tip_turno):
                       turno_discussao = turno.des_turno
                   resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
                   for i in resultado:
                       nom_resultado = ' (' + i.nom_resultado+ ' em ' + turno_discussao + votacao_observacao + ')'
                       if votacao.votacao_observacao:
                          votacao_observacao = votacao.ordem_observacao
                else:
                   nom_resultado = " (Substitutivo não votado)"
                   votacao_observacao = ""
             dic_substitutivo["materia"] = 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + ' - ' +  autoria + ' - ' + substitutivo.txt_ementa + nom_resultado
             if int(ordem.tip_turno) != 4:
                lst_substitutivos.append(dic_substitutivo)
                cod_substitutivo = substitutivo.cod_substitutivo
                lst_qtde_substitutivos.append(cod_substitutivo)
         dic_votacao["substitutivos"] = lst_substitutivos
         dic_votacao["qtde_substitutivos"] = len(lst_qtde_substitutivos)

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
             nom_resultado = ''
             for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_emenda=emenda.cod_emenda, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
                if votacao.votacao_observacao != '':
                   votacao_observacao = ' - ' + votacao.votacao_observacao
                else:
                   votacao_observacao = ''
                if votacao.tip_resultado_votacao:
                   for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=votacao.tip_turno):
                       turno_discussao = turno.des_turno
                   resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
                   for i in resultado:
                       nom_resultado = ' (' + i.nom_resultado+ ' em ' + turno_discussao + votacao_observacao + ')'
                       if votacao.votacao_observacao:
                           votacao_observacao = votacao.ordem_observacao
                else:
                   nom_resultado = " (Emenda não votada)"
                   votacao_observacao = ""
             dic_emenda["materia"] = 'Emenda nº ' + str(emenda.num_emenda) + ' (' + emenda.des_tipo_emenda + ') - ' +  autoria + ' - ' + emenda.txt_ementa + nom_resultado
             if int(ordem.tip_turno) != 4:
                lst_emendas.append(dic_emenda)
                cod_emenda = emenda.cod_emenda
                lst_qtde_emendas.append(cod_emenda)
         dic_votacao["emendas"] = lst_emendas
         dic_votacao["qtde_emenda"] = len(lst_qtde_emendas)
                  
      elif ordem.cod_parecer != None:
           relatoria = context.zsql.relatoria_obter_zsql(cod_relatoria=ordem.cod_parecer)[0]
           for comissao in context.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao):
               sgl_comissao = comissao.sgl_comissao
           for resultado in context.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=relatoria.tip_fim_relatoria):
               resultado_comissao = ' (' + resultado.des_fim_relatoria + ')'
           for mat in context.zsql.materia_obter_zsql(cod_materia=relatoria.cod_materia):
               id_materia = ' ao ' + str(mat.des_tipo_materia) + ' nº ' + str(mat.num_ident_basica) + '/' + str(mat.ano_ident_basica)
           nom_resultado = ''
           for votacao in context.zsql.votacao_ordem_dia_obter_zsql(cod_parecer=ordem.cod_parecer, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
               votacao_nominal = ''
               if ordem.tip_votacao == 2:
                   lst_nominal = []
                   for votos in context.zsql.votacao_parlamentar_obter_zsql(cod_votacao = votacao.cod_votacao, ind_excluido=0):
                       votos_nominais = votos.nom_completo + ': ' + votos.vot_parlamentar
                       lst_nominal.append(votos_nominais)
                   votacao_nominal = ', '.join(['%s' % (value) for (value) in lst_nominal])
                   votacao_nominal = ' - ' + votacao_nominal
               contagem_votos = ''
               if votacao.tip_votacao == 2:
                   if votacao.num_votos_sim == 0:
                      votos_favoraveis = ''
                   elif votacao.num_votos_sim == 1:
                      votos_favoraveis = ' - ' +str(votacao.num_votos_sim) + " voto favorável"
                   elif votacao.num_votos_sim > 1:
                      votos_favoraveis = ' - ' + str(votacao.num_votos_sim) + " votos favoráveis"
                   if votacao.num_votos_nao == 0:
                      votos_contrarios = ''
                   elif votacao.num_votos_nao == 1:
                      votos_contrarios = ' - ' + str(votacao.num_votos_nao) + " voto contrário"
                   elif votacao.num_votos_nao > 1:
                      votos_contrarios = ' - ' + str(votacao.num_votos_nao) + " votos contrários"
                   if votacao.num_abstencao == 0:
                      abstencoes = ''
                   elif votacao.num_abstencao == 1:
                      abstencoes = ' - ' + str(votacao.num_abstencao) + " abstenção"
                   elif votacao.num_abstencao > 1:
                      abstencoes =  ' - ' + str(votacao.num_abstencao) + " abstenções"
                   if votacao.num_ausentes == 0 or votacao.num_ausentes == None:
                      ausentes = ''
                   elif votacao.num_ausentes == 1:
                      ausentes = ' - ' + str(votacao.num_ausentes) + " ausência"
                   elif votacao.num_ausentes > 1:
                      ausentes =  ' - ' + str(votacao.num_ausentes) + " ausências"
                   contagem_votos = votos_favoraveis + votos_contrarios + abstencoes + ausentes
               if votacao.votacao_observacao != '':
                  votacao_observacao = ' - ' + votacao.votacao_observacao
               else:
                  votacao_observacao = ''
               if votacao.tip_resultado_votacao:
                  resultado = context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=votacao.tip_resultado_votacao, ind_excluido=0)
                  for i in resultado:
                      nom_resultado= ' (' + i.nom_resultado+ ' em ' + turno_discussao + contagem_votos + votacao_nominal + votacao_observacao + ')'
               else:
                  nom_resultado = " (Parecer não votado)"
                  votacao_observacao = ''
           dic_votacao["materia"] = '<b>Item ' + str(ordem.num_ordem) + '</b> - ' + str(des_turno) + ' do <a href="'+context.sapl_documentos.absolute_url() +'/parecer_comissao/' + str(ordem.cod_parecer) +'">' + 'Parecer ' + sgl_comissao + ' n° ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + id_materia + resultado_comissao + str(nom_resultado)

      if ordem.urgencia == 0:
         lst_votacao.append(dic_votacao)
      else:
         lst_urgencia.append(dic_votacao)

  ata_dic["lst_votacao"] = lst_votacao
  ata_dic["lst_urgencia"] = lst_urgencia

  # Lista das materias por turno
  lst_pdiscussao=[]
  lst_sdiscussao=[]
  lst_discussao_unica=[]
  for item in context.zsql.ordem_dia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
      if item.cod_materia != None:
         materia = context.zsql.materia_obter_zsql(cod_materia=item.cod_materia)[0]
         autores = context.zsql.autoria_obter_zsql(cod_materia=item.cod_materia)
         fields = autores.data_dictionary().keys()
         lista_autor = []
         for autor in autores:
             for field in fields:
                 nome_autor = autor['nom_autor_join']
             lista_autor.append(nome_autor)
         autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
         materia = str(materia.sgl_tipo_materia) + ' ' + str(materia.num_ident_basica)+"/"+str(context.pysc.ano_abrevia_pysc(ano=str(materia.ano_ident_basica)))+" - "+ materia.txt_ementa + " Autoria: "+ autoria
      if item.cod_parecer != None:
         relatoria = context.zsql.relatoria_obter_zsql(cod_relatoria=item.cod_parecer)[0]
         for comissao in context.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao):
             sgl_comissao = comissao.sgl_comissao
         for resultado in context.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=relatoria.tip_fim_relatoria):
             resultado_comissao = ' (' + resultado.des_fim_relatoria + ')'
         for mat in context.zsql.materia_obter_zsql(cod_materia=relatoria.cod_materia):
             id_materia = ' ao ' + str(mat.des_tipo_materia) + ' nº ' + str(mat.num_ident_basica) + '/' + str(mat.ano_ident_basica)
         materia = 'Parecer ' + sgl_comissao + ' n° ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + id_materia + resultado_comissao

      if item.tip_turno==1:
         lst_pdiscussao.append(materia)
      elif item.tip_turno==2:
         lst_sdiscussao.append(materia)
      elif item.tip_turno==3:
         lst_discussao_unica.append(materia)
         
  ata_dic["pdiscussao"] = '; '.join(['%s' % (value) for (value) in lst_pdiscussao])
  ata_dic["sdiscussao"] = '; '.join(['%s' % (value) for (value) in lst_sdiscussao])
  ata_dic["discussao_unica"] = '; '.join(['%s' % (value) for (value) in lst_discussao_unica])

  # Lista de oradores nas Explicacoes Pessoais
  lst_explicacoes_pessoais = []
  for orador in context.zsql.oradores_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
      for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=orador.cod_parlamentar,ind_excluido=0):
          dic_orador = {}
          dic_orador['num_ordem'] = orador.num_ordem
          dic_orador['nom_completo'] = parlamentar.nom_completo
          lst_explicacoes_pessoais.append(dic_orador)
  ata_dic['explicacoes_pessoais'] = lst_explicacoes_pessoais

  data = context.pysc.data_converter_pysc(sessao.dat_inicio_sessao)
  ata_dic['presidente'] = ''
  ata_dic['vice_presidente'] = ''
  ata_dic['1secretario'] = ''
  ata_dic['2secretario'] = ''
  ata_dic['3secretario'] = ''
  for periodo in context.zsql.periodo_comp_mesa_obter_zsql(num_legislatura=sessao.num_legislatura,data=data):
      for membro in context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=periodo.cod_periodo_comp):
          for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=membro.cod_parlamentar):
              if membro.des_cargo=='Presidente':
                 ata_dic['presidente'] = parlamentar.nom_completo
              elif membro.des_cargo=='Vice-Presidente':
                 ata_dic['vice_presidente'] = parlamentar.nom_completo
              elif membro.des_cargo=='1º Secretário':
                 ata_dic['1secretario'] = parlamentar.nom_completo
              elif membro.des_cargo=='2º Secretário':
                 ata_dic['2secretario'] = parlamentar.nom_completo
              elif membro.des_cargo=='3º Secretário':
                 ata_dic['3secretario'] = parlamentar.nom_completo
  casa={}
  aux=context.sapl_documentos.props_sagl.propertyItems()
  for item in aux:
      casa[item[0]]=item[1]
  localidade=context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])
  estados = context.zsql.localidade_obter_zsql(tip_localidade="U")
  for uf in estados:
      if localidade[0].sgl_uf == uf.sgl_uf:
          nom_estado = uf.nom_localidade
          break
  ata_dic['nom_camara'] = casa['nom_casa']
  ata_dic['end_camara'] = casa['end_casa']
  ata_dic["nom_estado"] = nom_estado
  for local in context.zsql.localidade_obter_zsql(cod_localidade = casa['cod_localidade']):
      ata_dic['nom_localidade']= local.nom_localidade
      ata_dic['sgl_uf']= local.sgl_uf

argumentos = {
    'ata_dic': ata_dic,
    'nome_arquivo': nom_arquivo,
    'nom_modelo': nom_modelo
}

def ata_gerar_odt(**kwargs):
    kwargs = {
        'modelo': getattr(context.sapl_documentos.modelo.sessao_plenaria, kwargs.get('nom_modelo')),
        'dicionario_dados': kwargs.copy(),
        'nome_arquivo': kwargs.get('nome_arquivo'),
        'pasta_destino': context.sapl_documentos.ata_sessao,
        'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}}
    }
    return st.gerar_odt(**kwargs)

return ata_gerar_odt(**argumentos)
