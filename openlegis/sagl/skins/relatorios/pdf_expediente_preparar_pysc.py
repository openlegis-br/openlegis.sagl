## Script (Python) "pdf_expediente_preparar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters= 
##title=
##

import os

request=context.REQUEST
response=request.RESPONSE

lst_autores_requerimentos = []
lst_requerimentos = []
lst_qtde_requerimentos = []

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
  for periodo in context.zsql.periodo_sessao_obter_zsql(cod_periodo=sessao.cod_periodo_sessao):
  	  pauta_dic["num_periodo"] = periodo.num_periodo

  for item in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=sessao.cod_sessao_plen,ind_excluido=0):
      if item.cod_materia != None:
         for materia in context.zsql.materia_obter_zsql(cod_materia=item.cod_materia,ind_excluido=0):
             dic_materia = {}
             dic_materia['cod_materia']= str(materia.cod_materia)
             dic_materia['num_ident_basica']= str(materia.num_ident_basica)
             dic_materia["id_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/materia/' + str(materia.cod_materia) + '_texto_integral.pdf' + '">'+materia.des_tipo_materia.decode('utf-8').upper() +' Nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
             dic_materia['txt_ementa'] = materia.txt_ementa

             if materia.des_tipo_materia == 'Requerimento' or materia.des_tipo_materia == 'Indicação' or materia.des_tipo_materia == 'Moção' or materia.des_tipo_materia == 'Pedido de Informação' :
                dic_autores = {}
                for autoria in context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia, ind_primeiro_autor = 1):
                    if autoria.ind_primeiro_autor == 1:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                               if parlamentar.sex_parlamentar == 'M':
                                  dic_autores["nom_parlamentar"] = autoria['nom_autor_join'].decode('utf-8').upper()
                               if parlamentar.sex_parlamentar == 'F':
                                  dic_autores["nom_parlamentar"] = autoria['nom_autor_join'].decode('utf-8').upper()
                    else:
                       dic_materia["cod_autor"] = int(autoria.cod_autor)
                       dic_autores["cod_autor"] = int(autoria.cod_autor)
                       for autor in context.zsql.autor_obter_zsql(cod_autor = autoria.cod_autor):
                           for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar):
                               if parlamentar.sex_parlamentar == 'M':
                                  dic_autores["nom_parlamentar"] = autoria['nom_autor_join'].decode('utf-8').upper()
                               if parlamentar.sex_parlamentar == 'F':
                                  dic_autores["nom_parlamentar"] = autoria['nom_autor_join'].decode('utf-8').upper()
                lst_autores_requerimentos.append(dic_autores)
                lst_requerimentos.append(dic_materia)
                lst_qtde_requerimentos.append(materia.cod_materia)
 
# ordena materias por antiguidade
lst_requerimentos.sort(key=lambda dic_materia: dic_materia['num_ident_basica'])

# setar apenas uma ocorrência de nome parlamentar
lst_autores_requerimentos = [
    e
    for i, e in enumerate(lst_autores_requerimentos)
    if lst_autores_requerimentos.index(e) == i
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

lst_requerimentos_vereadores.sort(key=lambda dic_vereador: dic_vereador['vereador'])

pauta_dic["lst_qtde_requerimentos"] = len(lst_qtde_requerimentos)
pauta_dic["lst_autores_requerimentos"] = lst_autores_requerimentos
pauta_dic["lst_requerimentos_vereadores"] = lst_requerimentos_vereadores

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
       nom_estado = uf.nom_localidade.encode('utf-8')
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

dat_emissao = DateTime().strftime("%d/%m/%Y")
rodape = [linha1, linha2, dat_emissao]

caminho = context.pdf_expediente_gerar(cabecalho, rodape, imagem, pauta_dic)
if caminho=='aviso':
   return response.redirect('mensagem_emitir_proc')
else:
   response.redirect(caminho)
