## Script (Python) "pdf_expediente_preparar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_sessao_plen
##title=
##
request=context.REQUEST
response=request.RESPONSE

lst_materia_apresentada=[]

lst_autores_requerimentos = []
lst_requerimentos = []
lst_qtde_requerimentos = []

total_requerimentos = []
total_requerimentos_plen = []
total_requerimentos_presid = []
total_indicacoes = []
total_mocoes = []
total_pedidos = []
total_materias = []

pauta_dic = {}

tipo_expediente = []
for item in context.zsql.tipo_expediente_obter_zsql(ind_excluido=0):
    dic_expediente = {}
    dic_expediente['cod_expediente'] = item.cod_expediente
    dic_expediente['nom_expediente'] = item.nom_expediente
    tipo_expediente.append(dic_expediente)

cod_sessao_plen = context.REQUEST['cod_sessao_plen']

for sessao in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0):
  data = context.pysc.data_converter_pysc(sessao.dat_inicio_sessao)
  dat_ordem = context.pysc.data_converter_pysc(sessao.dat_inicio_sessao)
  tipo_sessao = context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao.tip_sessao,ind_excluido=0)[0]
  pauta_dic["cod_sessao_plen"] = sessao.cod_sessao_plen
  pauta_dic["num_sessao_plen"] = sessao.num_sessao_plen
  pauta_dic["nom_sessao"] = tipo_sessao.nom_sessao.upper()
  pauta_dic["num_legislatura"] = sessao.num_legislatura
  pauta_dic["num_sessao_leg"] = sessao.num_sessao_leg
  pauta_dic["dat_inicio_sessao"] = sessao.dat_inicio_sessao
  pauta_dic["dia_sessao"] = context.pysc.data_converter_por_extenso_pysc(data=sessao.dat_inicio_sessao).upper()
  pauta_dic["hr_inicio_sessao"] = sessao.hr_inicio_sessao
  pauta_dic["dat_fim_sessao"] = sessao.dat_fim_sessao
  pauta_dic["hr_fim_sessao"] = sessao.hr_fim_sessao
  pauta_dic["num_periodo"] = ''
  if sessao.cod_periodo_sessao != None:
     for periodo in context.zsql.periodo_sessao_obter_zsql(cod_periodo=sessao.cod_periodo_sessao):
         pauta_dic["num_periodo"] = periodo.num_periodo

  # Leitura de Matérias
  for materia_apresentada in context.zsql.materia_apresentada_sessao_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen, ind_excluido=0):
      # materias principais
      if materia_apresentada.cod_materia != None:
         materia = context.zsql.materia_obter_zsql(cod_materia=materia_apresentada.cod_materia)[0]
         autores = context.zsql.autoria_obter_zsql(cod_materia=materia_apresentada.cod_materia)
         fields = list(autores.data_dictionary().keys())
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
               fields = list(autores.data_dictionary().keys())
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
               fields = list(autores.data_dictionary().keys())
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


  # Materias do Expediente
  for item in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,ind_excluido=0):
      if item.cod_materia != None:
         for materia in context.zsql.materia_obter_zsql(cod_materia=item.cod_materia,ind_excluido=0):
             cod_materia = materia.cod_materia
             dic_materia = {}
             dic_materia['num_ordem']= str(item.num_ordem).zfill(6)
             dic_materia['cod_materia']= str(materia.cod_materia)
             dic_materia['num_ident_basica']= str(materia.num_ident_basica)
             dic_materia["id_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/materia/' + str(materia.cod_materia) + '_texto_integral.pdf' + '">'+materia.des_tipo_materia +' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
             dic_materia['txt_ementa'] = context.pysc.convert_unicode_pysc(texto=str(materia.txt_ementa))

             if materia.des_tipo_materia == 'Requerimento' or materia.des_tipo_materia == 'Requerimento ao Plenário' or materia.des_tipo_materia == 'Requerimento à Presidência' or materia.des_tipo_materia == 'Indicação' or materia.des_tipo_materia == 'Moção' or materia.des_tipo_materia == 'Pedido de Informação' :
                dic_autores = {}
                for autoria in context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia):
                    if autoria.ind_primeiro_autor == 1:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           if autor.cod_parlamentar != None:
                              for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                                  if parlamentar.sex_parlamentar == 'M':
                                     dic_autores["cargo"] = 'Vereador'
                                  if parlamentar.sex_parlamentar == 'F':
                                     dic_autores["cargo"] = 'Vereadora'
                                  dic_autores["nom_completo"] = parlamentar.nom_completo.upper()
                                  dic_autores["nom_parlamentar"] = parlamentar.nom_parlamentar
                           else:
                                  dic_autores["cargo"] = ''
                                  dic_autores["nom_completo"] = autor.nom_autor_join.upper()
                                  dic_autores["nom_parlamentar"] = autor.nom_autor_join
                    elif autoria.ind_primeiro_autor == 0:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           if autor.cod_parlamentar != None:
                              for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                                  if parlamentar.sex_parlamentar == 'M':
                                     dic_autores["cargo"] = 'Vereador'
                                  if parlamentar.sex_parlamentar == 'F':
                                     dic_autores["cargo"] = 'Vereadora'
                                  dic_autores["nom_completo"] = parlamentar.nom_completo.upper()
                                  dic_autores["nom_parlamentar"] = parlamentar.nom_parlamentar
                           else:
                                  dic_autores["cargo"] = ''
                                  dic_autores["nom_completo"] = autor.nom_autor_join.upper()
                                  dic_autores["nom_parlamentar"] = autor.nom_autor_join
                    break
                lst_autores_requerimentos.append(dic_autores)
                lst_requerimentos.append(dic_materia)
                lst_qtde_requerimentos.append(materia.cod_materia)
             total_materias.append(materia.cod_materia)
             if materia.des_tipo_materia == 'Requerimento':
                total_requerimentos.append(materia.cod_materia)
             if materia.des_tipo_materia == 'Requerimento ao Plenário':
                total_requerimentos_plen.append(materia.cod_materia)
             if materia.des_tipo_materia == 'Requerimento à Presidência':
                total_requerimentos_presid.append(materia.cod_materia)
             if materia.des_tipo_materia == 'Indicação':
                total_indicacoes.append(materia.cod_materia)
             if materia.des_tipo_materia == 'Moção':
                total_mocoes.append(materia.cod_materia)
             if materia.des_tipo_materia == 'Pedido de Informação':
                total_pedidos.append(materia.cod_materia)
# ordena materias por antiguidade
lst_requerimentos.sort(key=lambda dic_materia: dic_materia['num_ordem'])

# setar apenas uma ocorrência de nome parlamentar
lst_autores_requerimentos = [
    e
    for i, e in enumerate(lst_autores_requerimentos)
    if lst_autores_requerimentos.index(e) == i
]

lst_requerimentos_vereadores = []
for autor in lst_autores_requerimentos:
    dic_vereador = {}
    dic_vereador['vereador'] = autor.get('nom_completo',autor)
    dic_vereador['nom_parlamentar'] = autor.get('nom_parlamentar',autor)
    dic_vereador['cargo'] = autor.get('cargo',autor)
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

lst_requerimentos_vereadores.sort(key=lambda dic_vereador: dic_vereador['vereador'])

pauta_dic["lst_qtde_requerimentos"] = len(lst_qtde_requerimentos)
pauta_dic["lst_autores_requerimentos"] = lst_autores_requerimentos
pauta_dic["lst_requerimentos_vereadores"] = lst_requerimentos_vereadores

pauta_dic["total_requerimentos"] = len(total_requerimentos)
pauta_dic["total_requerimentos_plen"] = len(total_requerimentos_plen)
pauta_dic["total_requerimentos_presid"] = len(total_requerimentos_presid)
pauta_dic["total_indicacoes"] = len(total_indicacoes)
pauta_dic["total_mocoes"] = len(total_mocoes)
pauta_dic["total_pedidos"] = len(total_pedidos)
pauta_dic["total_materias"] = len(total_materias)
pauta_dic["lst_materia_apresentada"] = lst_materia_apresentada

# obtém as propriedades da casa legislativa para montar o cabeçalho e o rodapé da página
casa = {}
aux=context.sapl_documentos.props_sagl.propertyItems()
for item in aux:
    casa[item[0]] = item[1]

# obtém a localidade
localidade = context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])

# monta o cabeçalho da página
cabecalho = {}
estado = context.zsql.localidade_obter_zsql(tip_localidade="U")
for uf in estado:
    if localidade[0].sgl_uf == uf.sgl_uf:
       nom_estado = uf.nom_localidade
       break
cabecalho["nom_casa"] = casa["nom_casa"]
cabecalho["nom_estado"] = nom_estado

#tenta buscar o logotipo da casa LOGO_CASA
if hasattr(context.sapl_documentos.props_sagl,'cabecalho.png'):
   imagem = context.sapl_documentos.props_sagl['cabecalho.png'].absolute_url()
   cabecalho["custom_image"]=True
elif hasattr(context.sapl_documentos.props_sagl,'logo_casa.gif'):
   imagem = context.sapl_documentos.props_sagl['logo_casa.gif'].absolute_url()
   cabecalho["custom_image"]=False
else:
   imagem = context.imagens.absolute_url() + "/brasao.gif"
   cabecalho["custom_image"]=False
   
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

caminho = context.pdf_expediente_gerar(cabecalho, rodape, imagem, pauta_dic)
if caminho=='aviso':
   return response.redirect('mensagem_emitir_proc')
else:
   response.redirect(caminho)
