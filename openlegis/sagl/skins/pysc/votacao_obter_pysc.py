## encoding: utf-8 
## Script (Python) "votacao_obter_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_materia, cod_sessao_plen=''
##title=
##
from DateTime import DateTime

lst_votacoes = []

if cod_materia != '':
   for item in context.zsql.materia_apresentada_sessao_obter_zsql(cod_materia=cod_materia, cod_sessao_plen=cod_sessao_plen):
      dic = {}
      for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia):
          dic['tipo_materia'] = materia.des_tipo_materia
          dic['num_materia'] = materia.num_ident_basica
          dic['ano_materia'] = materia.ano_ident_basica
          dic['ementa_materia'] = materia.txt_ementa
          autores = context.zsql.autoria_obter_zsql(cod_materia=cod_materia)
          fields = list(autores.data_dictionary().keys())
          lista_autor = []
          for autor in autores:
              for field in fields:
                  nome_autor = autor['nom_autor_join']
              lista_autor.append(nome_autor)
          dic["autoria_materia"] = ', '.join(['%s' % (value) for (value) in lista_autor])
      dic['cod_sessao_plen'] = item.cod_sessao_plen
      for sessao in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item.cod_sessao_plen):
          tipo = context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao, ind_excluido=0)[0]
          num_legislatura = sessao.num_legislatura
          dic['sessao'] = str(sessao.num_sessao_plen) + 'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' ' +  tipo.nom_sessao
          dic['dat_sessao'] = sessao.dat_inicio_sessao
          dic['data_sessao'] = context.pysc.data_converter_por_extenso_pysc(data=str(sessao.dat_inicio_sessao))
          dic['hora_sessao'] = DateTime(sessao.hr_inicio_sessao, datefmt='international').strftime("%H:%M")
          dic['legislatura'] = str(sessao.num_legislatura) + 'ª ' + 'Legislatura'
      dic['fase'] = 'Expediente - Leitura de Matérias'
      dic['num_ordem'] = item.num_ordem
      lst_votacoes.append(dic)

   for item in context.zsql.votacao_materia_expediente_pesquisar_zsql(cod_materia=cod_materia, cod_sessao_plen=cod_sessao_plen):
      dic = {}
      for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia):
          dic['tipo_materia'] = materia.des_tipo_materia
          dic['num_materia'] = materia.num_ident_basica
          dic['ano_materia'] = materia.ano_ident_basica
          dic['ementa_materia'] = materia.txt_ementa
          autores = context.zsql.autoria_obter_zsql(cod_materia=cod_materia)
          fields = list(autores.data_dictionary().keys())
          lista_autor = []
          for autor in autores:
              for field in fields:
                  nome_autor = autor['nom_autor_join']
              lista_autor.append(nome_autor)
          dic["autoria_materia"] = ', '.join(['%s' % (value) for (value) in lista_autor])
      dic['cod_sessao_plen'] = item.cod_sessao_plen
      for sessao in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item.cod_sessao_plen):
          tipo = context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao, ind_excluido=0)[0]
          num_legislatura = sessao.num_legislatura
          dic['sessao'] = str(sessao.num_sessao_plen) + 'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' ' +  tipo.nom_sessao
          dic['dat_sessao'] = sessao.dat_inicio_sessao
          dic['data_sessao'] = context.pysc.data_converter_por_extenso_pysc(data=str(sessao.dat_inicio_sessao))
          dic['hora_sessao'] = DateTime(sessao.hr_inicio_sessao, datefmt='international').strftime("%H:%M")
          dic['legislatura'] = str(sessao.num_legislatura) + 'ª ' + 'Legislatura'
      dic['fase'] = 'Expediente'
      dic['cod_ordem'] = item.cod_ordem
      dic['num_ordem'] = item.num_ordem
      dic['cod_votacao'] = item.cod_votacao
      for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=item.tip_turno):
          dic['txt_turno'] = turno.des_turno
      for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=item.tip_quorum):
          dic['txt_quorum'] = quorum.des_quorum
      for tipo in context.zsql.tipo_votacao_obter_zsql(tip_votacao=item.tip_votacao):
          dic['txt_tipo_votacao'] = tipo.des_tipo_votacao
      if dic['txt_tipo_votacao'] == 'Nominal':
         dic['votos_nominais'] = []
         for voto in context.zsql.votacao_parlamentar_obter_zsql(cod_votacao=item.cod_votacao):
             dic_votacao = {}
             dic_votacao['nom_completo'] = voto.nom_completo
             dic_votacao['nom_parlamentar'] = voto.nom_parlamentar
             dic_votacao['partido'] = 'Sem Registro'
             for filiacao in  context.zsql.parlamentar_data_filiacao_obter_zsql(num_legislatura = num_legislatura, cod_parlamentar=voto.cod_parlamentar):
                 for partido in context.zsql.parlamentar_partido_obter_zsql(dat_filiacao=filiacao.dat_filiacao, cod_parlamentar=voto.cod_parlamentar):
                     dic_votacao['partido'] = partido.sgl_partido
             dic_votacao['voto'] = voto.vot_parlamentar
             dic['votos_nominais'].append(dic_votacao)
      dic['num_votos_sim'] = item.num_votos_sim
      dic['num_votos_nao'] = item.num_votos_nao
      dic['num_abstencao'] = item.num_abstencao
      dic['num_ausentes'] = item.num_ausentes
      dic['txt_resultado'] = ''
      for resultado in context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=item.tip_resultado_votacao):
          dic['txt_resultado'] = resultado.nom_resultado
      dic['observacao'] = item.observacao_votacao
      lst_votacoes.append(dic)

   for item in context.zsql.votacao_materia_ordem_dia_pesquisar_zsql(cod_materia=cod_materia, cod_sessao_plen=cod_sessao_plen):
      dic = {}
      for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia):
          dic['tipo_materia'] = materia.des_tipo_materia
          dic['num_materia'] = materia.num_ident_basica
          dic['ano_materia'] = materia.ano_ident_basica
          dic['ementa_materia'] = materia.txt_ementa
          autores = context.zsql.autoria_obter_zsql(cod_materia=cod_materia)
          fields = list(autores.data_dictionary().keys())
          lista_autor = []
          for autor in autores:
              for field in fields:
                  nome_autor = autor['nom_autor_join']
              lista_autor.append(nome_autor)
          dic["autoria_materia"] = ', '.join(['%s' % (value) for (value) in lista_autor])
      dic['cod_sessao_plen'] = item.cod_sessao_plen
      for sessao in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=item.cod_sessao_plen):
          tipo = context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao, ind_excluido=0)[0]
          num_legislatura = sessao.num_legislatura
          dic['sessao'] = str(sessao.num_sessao_plen) + 'ª ' + str(context.sapl_documentos.props_sagl.reuniao_sessao) + ' ' +  tipo.nom_sessao
          dic['dat_sessao'] = sessao.dat_inicio_sessao
          dic['data_sessao'] = context.pysc.data_converter_por_extenso_pysc(data=str(sessao.dat_inicio_sessao))
          dic['hora_sessao'] = DateTime(sessao.hr_inicio_sessao, datefmt='international').strftime("%H:%M")
          dic['legislatura'] = str(sessao.num_legislatura) + 'ª ' + 'Legislatura'
      dic['fase'] = 'Ordem do Dia'
      dic['cod_ordem'] = item.cod_ordem
      dic['num_ordem'] = item.num_ordem
      dic['cod_votacao'] = item.cod_votacao
      for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=item.tip_turno):
          dic['txt_turno'] = turno.des_turno
      for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=item.tip_quorum):
          dic['txt_quorum'] = quorum.des_quorum
      for tipo in context.zsql.tipo_votacao_obter_zsql(tip_votacao=item.tip_votacao):
          dic['txt_tipo_votacao'] = tipo.des_tipo_votacao
      if dic['txt_tipo_votacao'] == 'Nominal':
         dic['votos_nominais'] = []
         for voto in context.zsql.votacao_parlamentar_obter_zsql(cod_votacao=item.cod_votacao):
             dic_votacao = {}
             dic_votacao['nom_completo'] = voto.nom_completo
             dic_votacao['nom_parlamentar'] = voto.nom_parlamentar
             dic_votacao['partido'] = 'Sem Registro'
             for filiacao in  context.zsql.parlamentar_data_filiacao_obter_zsql(num_legislatura = num_legislatura, cod_parlamentar=voto.cod_parlamentar):
                 for partido in context.zsql.parlamentar_partido_obter_zsql(dat_filiacao=filiacao.dat_filiacao, cod_parlamentar=voto.cod_parlamentar):
                     dic_votacao['partido'] = partido.sgl_partido
             dic_votacao['voto'] = voto.vot_parlamentar
             dic['votos_nominais'].append(dic_votacao)
      dic['num_votos_sim'] = item.num_votos_sim
      dic['num_votos_nao'] = item.num_votos_nao
      dic['num_abstencao'] = item.num_abstencao
      dic['num_ausentes'] = item.num_ausentes
      dic['txt_resultado'] = ''
      for resultado in context.zsql.tipo_resultado_votacao_obter_zsql(tip_resultado_votacao=item.tip_resultado_votacao):
          dic['txt_resultado'] = resultado.nom_resultado
      dic['observacao'] = item.observacao_votacao
      dic["emendas"] = []
      for emenda in context.zsql.emenda_obter_zsql(cod_materia=cod_materia,ind_excluido=0,exc_pauta=0):
          autores = context.zsql.autoria_emenda_obter_zsql(cod_emenda=emenda.cod_emenda,ind_excluido=0)
          dic_emenda = {}
          fields = list(autores.data_dictionary().keys())
          lista_autor = []
          for autor in autores:
              for field in fields:
                  nome_autor = autor['nom_autor_join']
              lista_autor.append(nome_autor)
          autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
          dic_emenda["id_emenda"] = 'Emenda ' + emenda.des_tipo_emenda + ' nº ' + str(emenda.num_emenda)
          dic_emenda["txt_ementa"] = emenda.txt_ementa
          dic_emenda["autoria"] = autoria
          dic["emendas"].append(dic_emenda)
      dic['substitutivos']=[]
      for substitutivo in context.zsql.substitutivo_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
          autores = context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo, ind_excluido=0)
          dic_substitutivo = {}
          fields = list(autores.data_dictionary().keys())
          lista_autor = []
          for autor in autores:
              for field in fields:
                  nome_autor = autor['nom_autor_join']
              lista_autor.append(nome_autor)
          autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
          dic_substitutivo["id_substitutivo"] = 'Substitutivo nº ' + str(substitutivo.num_substitutivo)
          dic_substitutivo["txt_ementa"] = substitutivo.txt_ementa
          dic_substitutivo["autoria"] = autoria
          dic['substitutivos'].append(dic_substitutivo)

      lst_votacoes.append(dic)

elif cod_emenda != '':
   for item in context.zsql.votacao_ordem_dia_obter_zsql(cod_emenda=cod_emenda):
      dic = {}
      dic['cod_sessao_plen'] = item.cod_sessao_plen
      dic['fase'] = 'Ordem do Dia'
      dic['cod_ordem'] = item.cod_ordem
      dic['num_ordem'] = item.num_ordem
      dic['cod_votacao'] = item.cod_votacao
      dic['tip_turno'] = item.tip_turno
      dic['tip_votacao'] = item.tip_votacao
      dic['tip_resultado_votacao'] = item.tip_resultado_votacao
      lst_votacoes.append(dic)

elif cod_substitutivo != '':
   for item in context.zsql.votacao_ordem_dia_obter_zsql(cod_substitutivo=cod_substitutivo):
      dic = {}
      dic['cod_sessao_plen'] = item.cod_sessao_plen
      dic['fase'] = 'Ordem do Dia'
      dic['cod_ordem'] = item.cod_ordem
      dic['num_ordem'] = item.num_ordem
      dic['cod_votacao'] = item.cod_votacao
      dic['tip_turno'] = item.tip_turno
      dic['tip_votacao'] = item.tip_votacao
      dic['tip_resultado_votacao'] = item.tip_resultado_votacao
      lst_votacoes.append(dic)

return(lst_votacoes)

