## Script (Python) "resumo_gerar"
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
session = REQUEST.SESSION

lst_autores_requerimentos = []
lst_requerimentos = []
lst_qtde_requerimentos = []

lst_qtde_indicacoes = []

lst_autores_mocoes = []
lst_mocoes = []
lst_qtde_mocoes = []

lst_pauta = []
lst_urgencia = []

if 'ind_audiencia' in REQUEST:
   nom_modelo = 'resumo_audiencia.odt'
   metodo = context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_audiencia=1, ind_excluido=0)
   for item in metodo:
       for nome in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao,ind_audiencia=1,ind_excluido=0):
           nom_sessao = nome.nom_sessao
else:
   nom_modelo = 'resumo.odt'
   metodo = context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0)
   for item in metodo:
       for nome in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao,ind_excluido=0):
           nom_sessao = nome.nom_sessao

for sessao in metodo:
  data = context.pysc.data_converter_pysc(sessao.dat_inicio_sessao)
  dat_ordem = context.pysc.data_converter_pysc(sessao.dat_inicio_sessao)
  resumo_dic = {}
  resumo_dic["cod_sessao_plen"] = sessao.cod_sessao_plen
  resumo_dic["num_sessao_plen"] = sessao.num_sessao_plen
  resumo_dic["nom_sessao"] = nom_sessao
  resumo_dic["num_legislatura"] = sessao.num_legislatura
  resumo_dic["num_sessao_leg"] = sessao.num_sessao_leg
  resumo_dic["dat_inicio_sessao"] = sessao.dat_inicio_sessao
  resumo_dic["dia_sessao"] = context.pysc.data_converter_por_extenso_pysc(data=sessao.dat_inicio_sessao)
  resumo_dic["hr_inicio_sessao"] = sessao.hr_inicio_sessao
  resumo_dic["dat_fim_sessao"] = sessao.dat_fim_sessao
  resumo_dic["hr_fim_sessao"] = sessao.hr_fim_sessao
  if nom_sessao == 'Audiência Pública':
     resumo_dic["txt_tema"] = sessao.tip_expediente
     nom_arquivo = 'Roteiro-' + str(sessao.num_sessao_plen) + '-audiencia' +'.odt'
  else:
     resumo_dic["txt_tema"] = ''
     nom_arquivo = 'Roteiro-' + str(sessao.num_sessao_plen) + '-sessao' +'.odt'

  # dados da casa
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
  resumo_dic['nom_camara'] = casa['nom_casa']
  resumo_dic['end_camara'] = casa['end_casa']
  resumo_dic["nom_estado"] = nom_estado
  for local in context.zsql.localidade_obter_zsql(cod_localidade = casa['cod_localidade']):
      resumo_dic['nom_localidade']= local.nom_localidade
      resumo_dic['sgl_uf']= local.sgl_uf

  # Materias Apresentadas
  lst_materia_apresentada=[]
  for materia_apresentada in context.zsql.materia_apresentada_sessao_obter_zsql(cod_sessao_plen=cod_sessao_plen,ind_excluido=0):
  
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
         dic_materia['materia'] = str(materia.des_tipo_materia)+ ' nº ' +str(materia.num_ident_basica)+"/"+str(materia.ano_ident_basica)
         dic_materia['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor]) 
         dic_materia['ementa'] = materia.txt_ementa
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
               dic_materia['materia'] = 'Emenda ' + str(emenda.des_tipo_emenda) + ' nº ' + str(emenda.num_emenda) + " ao " + materia.sgl_tipo_materia + str(materia.num_ident_basica) + "/" + str(materia.ano_ident_basica)
               dic_materia['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor]) 
               dic_materia['ementa'] = emenda.txt_ementa
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
               dic_materia['materia'] = 'Substitutivo ' + ' nº ' + str(substitutivo.num_substitutivo) + " ao " + materia.sgl_tipo_materia + str(materia.num_ident_basica) + "/" + str(materia.ano_ident_basica)
               dic_materia['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor]) 
               dic_materia['ementa'] = substitutivo.txt_ementa
           lst_materia_apresentada.append(dic_materia)

      # pareceres
      elif materia_apresentada.cod_parecer != None:
           for parecer in context.zsql.relatoria_obter_zsql(cod_relatoria=materia_apresentada.cod_parecer):
               materia = context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia)[0]
               for comissao in context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao):
                   sgl_comissao = comissao.sgl_comissao
                   nom_comissao = comissao.nom_comissao
               autoria = nom_comissao.upper()
               dic_materia = {}
               dic_materia['materia'] = 'Parecer ' + str(sgl_comissao) + ' nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) + " ao " +  str(materia.sgl_tipo_materia) +' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
               dic_materia['autoria'] = nom_comissao.upper() 
               dic_materia['ementa'] = ''
           lst_materia_apresentada.append(dic_materia)
           
      # documentos administrativos
      elif materia_apresentada.cod_documento != None:
           materia = context.zsql.documento_administrativo_obter_zsql(cod_documento=materia_apresentada.cod_documento)[0]
           dic_materia = {}
           dic_materia['materia'] = str(materia.des_tipo_documento) + ' nº ' +str(materia.num_documento)+"/"+str(materia.ano_documento)
           dic_materia['autoria'] = materia.txt_interessado
           dic_materia['ementa'] = materia.txt_assunto
           lst_materia_apresentada.append(materia)

  # Ata Sessao Anterior
  resumo_dic["ata_anterior"] = ''
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=cod_sessao_plen,cod_expediente=6,ind_excluido=0):
      resumo_dic["ata_anterior"] = item.txt_expediente

  # Insercoes em Ata
  resumo_dic["insercao"] = ''
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=cod_sessao_plen,cod_expediente=9,ind_excluido=0):
      resumo_dic["insercao"] = item.txt_expediente

  # Expedientes Executivo
  resumo_dic["expedientes_executivo"] = ""
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=cod_sessao_plen,cod_expediente=1,ind_excluido=0):
    resumo_dic["expedientes_executivo"] = item.txt_expediente

  # Expedientes Diversos
  resumo_dic["expedientes_diversos"] = ""
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=cod_sessao_plen,cod_expediente=2,ind_excluido=0):
    resumo_dic["expedientes_diversos"] = item.txt_expediente

  # Expedientes acessorios
  resumo_dic["expedientes_acessorios"] = ""
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=cod_sessao_plen,cod_expediente=8,ind_excluido=0):
    resumo_dic["expedientes_acessorios"] = item.txt_expediente
    
  # Tribuna do Cidadão
  resumo_dic["tribuna"] = ''
  for item in context.zsql.expediente_obter_zsql(cod_sessao_plen=cod_sessao_plen,cod_expediente=10,ind_excluido=0):
      resumo_dic["tribuna"] = item.txt_expediente

  for item in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,ind_excluido=0):
      if item.cod_materia != None:
         for materia in context.zsql.materia_obter_zsql(cod_materia=item.cod_materia,ind_excluido=0):
             dic_materia = {}
             dic_materia['cod_materia']= str(materia.cod_materia)
             dic_materia['id_materia'] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
             dic_materia['txt_ementa'] = materia.txt_ementa 
             if materia.des_tipo_materia == 'Indicação':
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
  for ordem in context.zsql.ordem_dia_obter_zsql(dat_ordem=data, cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
    dic = {} 
    dic["num_ordem"] = ordem.num_ordem
    if ordem.cod_materia != None: 
      materia = context.zsql.materia_obter_zsql(cod_materia=ordem.cod_materia)[0]
      dic["cod_materia"] = ordem.cod_materia
      dic["cod_parecer"] = ''
      dic["id_materia"] = materia.des_tipo_materia+" nº "+str(materia.num_ident_basica)+"/"+str(materia.ano_ident_basica) 
      dic["txt_ementa"] = ordem.txt_observacao
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
          dic_parecer["id_parecer"] = 'Parecer da ' + comissao.nom_comissao + ' nº ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer)
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
          dic_substitutivo["id_substitutivo"] = 'Substitutivo nº ' + str(substitutivo.num_substitutivo)
          dic_substitutivo["txt_ementa"] = substitutivo.txt_ementa
          dic_substitutivo["autoria"] = autoria
          lst_substitutivos.append(dic_substitutivo)
          cod_substitutivo = substitutivo.cod_substitutivo
          lst_qtde_substitutivos.append(cod_substitutivo)
      dic["substitutivos"] = lst_substitutivos
      dic["substitutivo"] = len(lst_qtde_substitutivos)

      dic["emenda"] = ''
      dic["emendas"] = ''
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
          dic_emenda["id_emenda"] = 'Emenda nº ' + str(emenda.num_emenda) + ' (' + emenda.des_tipo_emenda + ')'
          dic_emenda["txt_ementa"] = str(emenda.txt_ementa)
          dic_emenda["autoria"] = autoria
          lst_emendas.append(dic_emenda)
          cod_emenda = emenda.cod_emenda
          lst_qtde_emendas.append(cod_emenda)
      dic["emendas"] = lst_emendas
      dic["emenda"] = len(lst_qtde_emendas)
    if ordem.urgencia == 1:     
       lst_urgencia.append(dic) 
    else:
       lst_pauta.append(dic)      

# ordena requerimentos por antiguidade
lst_requerimentos.sort(key=lambda dic: dic_materia['cod_materia'])
lst_mocoes.sort(key=lambda dic: dic_materia['cod_materia'])

# setar apenas uma ocorrência de nome parlamentar
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

# quantidade total de requerimentos
resumo_dic["lst_qtde_requerimentos"] = len(lst_qtde_requerimentos)
resumo_dic["lst_materia_apresentada"] = lst_materia_apresentada
resumo_dic["lst_autores_requerimentos"] = lst_autores_requerimentos 
resumo_dic["lst_requerimentos_vereadores"] = lst_requerimentos_vereadores

resumo_dic["lst_qtde_mocoes"] = len(lst_qtde_mocoes)
resumo_dic["lst_autores_mocoes"] = lst_autores_mocoes 
resumo_dic["lst_mocoes_vereadores"] = lst_mocoes_vereadores

resumo_dic["lst_qtde_indicacoes"] = len(lst_qtde_indicacoes)

resumo_dic["lst_pauta"] = lst_pauta
resumo_dic["lst_urgencia"] = lst_urgencia

return st.resumo_gerar_odt(resumo_dic, nom_arquivo, nom_modelo)
