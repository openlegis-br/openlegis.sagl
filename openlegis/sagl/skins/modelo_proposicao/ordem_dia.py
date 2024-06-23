## Script (Python) "ordem_dia"
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
from DateTime import DateTime
request = context.REQUEST
response =  request.RESPONSE

inf_basicas_dic = {}

tipo_expediente = []
for item in context.zsql.tipo_expediente_obter_zsql(ind_excluido=0):
    dic_expediente = {}
    dic_expediente['cod_expediente'] = item.cod_expediente
    dic_expediente['nom_expediente'] = item.nom_expediente
    tipo_expediente.append(dic_expediente)

cod_sessao_plen = context.REQUEST['cod_sessao_plen']

if request.has_key('ind_audiencia'):
   nom_modelo = 'pauta_audiencia.odt'
   metodo = context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_audiencia=1, ind_excluido=0)
   for item in metodo:
       for nome in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao,ind_audiencia=1,ind_excluido=0):
           nom_sessao = nome.nom_sessao
else:
   nom_modelo = 'ordem_dia.odt'
   metodo = context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0)
   for item in metodo:
       for nome in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao,ind_excluido=0):
           nom_sessao = nome.nom_sessao

for sessao in metodo:
    data = context.pysc.data_converter_pysc(sessao.dat_inicio_sessao)
    # seleciona o tipo da sessao plenaria
    inf_basicas_dic["cod_sessao_plen"] = sessao.cod_sessao_plen
    inf_basicas_dic["num_sessao_plen"] = sessao.num_sessao_plen
    inf_basicas_dic["nom_sessao"] = nom_sessao.upper()
    inf_basicas_dic["num_legislatura"] = sessao.num_legislatura
    inf_basicas_dic["num_sessao_leg"] = sessao.num_sessao_leg
    inf_basicas_dic["dat_inicio_sessao"] = sessao.dat_inicio_sessao
    inf_basicas_dic["dia_sessao"] = context.pysc.data_converter_por_extenso_pysc(data=sessao.dat_inicio_sessao).upper()
    inf_basicas_dic["hr_inicio_sessao"] = sessao.hr_inicio_sessao
    inf_basicas_dic["dat_fim_sessao"] = sessao.dat_fim_sessao
    inf_basicas_dic["hr_fim_sessao"] = sessao.hr_fim_sessao
    inf_basicas_dic["txt_tema"] = sessao.tip_expediente
    inf_basicas_dic["num_periodo"] = ''
    if sessao.cod_periodo_sessao != None:
       for periodo in context.zsql.periodo_sessao_obter_zsql(cod_periodo=sessao.cod_periodo_sessao):
           inf_basicas_dic["num_periodo"] = periodo.num_periodo
    nom_arquivo = str(cod_sessao_plen)+'_pauta_sessao.odt'
    # obtém o nome do Presidente da Câmara titular
    inf_basicas_dic["lst_presidente"] = ''
    lst_presidente = inf_basicas_dic["lst_presidente"]
    for sleg in context.zsql.periodo_comp_mesa_obter_zsql(num_legislatura=sessao.num_legislatura,data=data):
        for cod_presidente in context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp, cod_cargo=1):
            for presidencia in context.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_presidente.cod_parlamentar):
                inf_basicas_dic["lst_presidente"] = presidencia.nom_parlamentar
    # Lista das matérias apresentadas
    inf_basicas_dic["apresentada"] = []
    for materia_apresentada in context.zsql.materia_apresentada_sessao_obter_zsql(dat_ordem=data,cod_sessao_plen=cod_sessao_plen,ind_excluido=0):
        dic_materia_apresentada = {}
        # seleciona os detalhes de uma matéria
        if materia_apresentada.cod_materia != None:
           materia = context.zsql.materia_obter_zsql(cod_materia=materia_apresentada.cod_materia)[0]
           dic_materia_apresentada["num_ordem"] = materia_apresentada.num_ordem
           comissoes = []
           for despacho in context.zsql.despacho_inicial_obter_zsql(cod_materia=materia_apresentada.cod_materia):
               nom_comissao = despacho.nom_comissao_index
               comissoes.append(nom_comissao)
           dic_materia_apresentada["comissoes"] = '; '.join(['%s' % (value) for (value) in comissoes]) 
           dic_materia_apresentada["txt_ementa"] = materia.txt_ementa
           dic_materia_apresentada["materia"] = str(materia.des_tipo_materia.upper())+' Nº '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
           dic_materia_apresentada["link_materia"] = '<link href="'+context.sapl_documentos.absolute_url()+'/materia/'+ str(materia_apresentada.cod_materia) + '_texto_integral.pdf' +'">'+materia.des_tipo_materia.upper()+' Nº '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
           dic_materia_apresentada["nom_autor"] = ""
           autores = context.zsql.autoria_obter_zsql(cod_materia=materia_apresentada.cod_materia)
           fields = list(autores.data_dictionary().keys())
           lista_autor = []
           for autor in autores:
               for field in fields:
                   nome_autor = autor['nom_autor_join']
               lista_autor.append(nome_autor)
           dic_materia_apresentada["nom_autor"] = ', '.join(['%s' % (value) for (value) in lista_autor]) 
           inf_basicas_dic["apresentada"].append(dic_materia_apresentada)
    # Ordem do Dia
    inf_basicas_dic["pdiscussao"] = []
    inf_basicas_dic["sdiscussao"] = []
    inf_basicas_dic["dunica"] = []
    inf_basicas_dic["pcontrario"] = []
    inf_basicas_dic["veto"] = []
    inf_basicas_dic["contra"] = []
    inf_basicas_dic["devolucao"] = []
    inf_basicas_dic["urgencia"] = []
    for item in context.zsql.ordem_dia_obter_zsql(cod_sessao_plen=inf_basicas_dic["cod_sessao_plen"], ind_excluido=0):
        dic={}
        dic["num_ordem"] = item.num_ordem
        dic['des_turno'] = ''
        dic['cod_turno'] = ''
        for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=item.tip_turno):
            dic["des_turno"] = str(turno.des_turno)
            dic["cod_turno"] = int(turno.cod_turno)
        dic["des_quorum"]=""
        for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=item.tip_quorum):
            dic["des_quorum"] = quorum.des_quorum
        dic["tip_votacao"]=""
        for tip_votacao in context.zsql.tipo_votacao_obter_zsql(tip_votacao=item.tip_votacao):
            dic["tip_votacao"] = 'Votação ' + str(tip_votacao.des_tipo_votacao)
        if item.cod_materia != None:
           materia = context.zsql.materia_obter_zsql(cod_materia=item.cod_materia)[0]
           dic['materia'] = str(materia.des_tipo_materia.upper())+" N° "+str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
           dic["link_materia"] = '<link href="'+context.sapl_documentos.absolute_url()+'/materia/'+ str(materia.cod_materia) + '_texto_integral.pdf' +'">'+materia.des_tipo_materia.upper()+' Nº '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
           dic["txt_ementa"] = materia.txt_ementa
           dic['nom_autor'] = ''
           autores = context.zsql.autoria_obter_zsql(cod_materia=item.cod_materia)
           fields = list(autores.data_dictionary().keys())
           lista_autor = []
           for autor in autores:
               for field in fields:
                   nome_autor = autor['nom_autor_join']
               lista_autor.append(nome_autor)
           dic["nom_autor"] = ', '.join(['%s' % (value) for (value) in lista_autor])
           dic["emenda"] = ''
           lst_qtde_emendas=[]
           lst_emendas=[]
           for emenda in context.zsql.emenda_obter_zsql(cod_materia=item.cod_materia,ind_excluido=0,exc_pauta=0):
               autores = context.zsql.autoria_emenda_obter_zsql(cod_emenda=emenda.cod_emenda,ind_excluido=0)
               dic_emenda = {}
               fields = list(autores.data_dictionary().keys())
               lista_autor = []
               for autor in autores:
                   for field in fields:
                       nome_autor = autor['nom_autor_join']
                   lista_autor.append(nome_autor)
               autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
               dic_emenda["id_emenda"] = '<link href="' + context.sapl_documentos.absolute_url() + '/emenda/' + str(emenda.cod_emenda) + '_emenda.pdf' + '">' + 'Emenda nº ' + str(emenda.num_emenda) + ' (' + emenda.des_tipo_emenda + ')</link>'
               dic_emenda["txt_ementa"] = emenda.txt_ementa
               dic_emenda["autoria"] = autoria
               lst_emendas.append(dic_emenda)
               cod_emenda = emenda.cod_emenda
               lst_qtde_emendas.append(cod_emenda)
           dic["emendas"] = lst_emendas
           dic["emenda"] = len(lst_qtde_emendas)
           dic["substitutivo"] = ''
           lst_qtde_substitutivos=[]
           lst_substitutivos=[]
           for substitutivo in context.zsql.substitutivo_obter_zsql(cod_materia=item.cod_materia,ind_excluido=0):
               autores = context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=substitutivo.cod_substitutivo, ind_excluido=0)
               dic_substitutivo = {}
               fields = list(autores.data_dictionary().keys())
               lista_autor = []
               for autor in autores:
                   for field in fields:
                       nome_autor = autor['nom_autor_join']
                   lista_autor.append(nome_autor)
               autoria = ', '.join(['%s' % (value) for (value) in lista_autor])
               dic_substitutivo["id_substitutivo"] = '<link href="' + context.sapl_documentos.absolute_url() + '/substitutivo/' + str(substitutivo.cod_substitutivo) + '_substitutivo.pdf' + '">' + 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + '</link>'
               dic_substitutivo["txt_ementa"] = substitutivo.txt_ementa
               dic_substitutivo["autoria"] = autoria
               lst_substitutivos.append(dic_substitutivo)
               cod_substitutivo = substitutivo.cod_substitutivo
               lst_qtde_substitutivos.append(cod_substitutivo)
           dic["substitutivos"] = lst_substitutivos
           dic["substitutivo"] = len(lst_qtde_substitutivos)
        elif item.cod_parecer != None:
           materia = context.zsql.relatoria_obter_zsql(cod_relatoria=item.cod_parecer)[0]
           for comissao in context.zsql.comissao_obter_zsql(cod_comissao=materia.cod_comissao):
               sgl_comissao = comissao.sgl_comissao
               nom_comissao = comissao.nom_comissao
           for resultado in context.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=materia.tip_fim_relatoria):
               resultado_comissao = ' (' + resultado.des_fim_relatoria + ')'
           for mat in context.zsql.materia_obter_zsql(cod_materia=materia.cod_materia):
               id_materia = ' ao ' + str(mat.des_tipo_materia) + ' nº ' + str(mat.num_ident_basica) + '/' + str(mat.ano_ident_basica)
           dic['materia'] = 'PARECER ' + sgl_comissao + ' N° ' + str(materia.num_parecer) + '/' + str(materia.ano_parecer) + id_materia + resultado_comissao
           dic["link_materia"] = '<link href="'+context.sapl_documentos.absolute_url()+'/parecer_comissao/'+ str(materia.cod_relatoria) + '_parecer.pdf' +'">' + 'PARECER ' + sgl_comissao + ' N° ' + str(materia.num_parecer) + '/' + str(materia.ano_parecer) + id_materia + resultado_comissao + '</link>'
           dic["txt_ementa"] = item.txt_observacao
           dic['nom_autor'] = str(nom_comissao)

        if item.urgencia == 1:
           inf_basicas_dic["urgencia"].append(dic)
        else:
           if item.tip_turno == 3:
              inf_basicas_dic["pdiscussao"].append(dic)
           if item.tip_turno == 4:
              inf_basicas_dic["sdiscussao"].append(dic)
           if item.tip_turno == 5:
              inf_basicas_dic["dunica"].append(dic)
           if item.tip_turno == 6:
              inf_basicas_dic["pcontrario"].append(dic)
           if item.tip_turno == 7:
              inf_basicas_dic["veto"].append(dic)
           if item.tip_turno == 8:
              inf_basicas_dic["contra"].append(dic)
           if item.tip_turno == 9:
              inf_basicas_dic["devolucao"].append(dic)

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
inf_basicas_dic['nom_camara']= casa['nom_casa']
inf_basicas_dic["nom_estado"] = nom_estado
for local in context.zsql.localidade_obter_zsql(cod_localidade = casa['cod_localidade']):
    inf_basicas_dic['nom_localidade']= local.nom_localidade
    inf_basicas_dic['sgl_uf']= local.sgl_uf

return st.ordem_dia_gerar_odt(inf_basicas_dic, nom_arquivo, nom_modelo)
