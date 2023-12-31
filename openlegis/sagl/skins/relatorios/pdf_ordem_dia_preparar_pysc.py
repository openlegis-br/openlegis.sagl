import os

request=context.REQUEST
response=request.RESPONSE
session= request.SESSION

cod_sessao_plen = request['cod_sessao_plen']

if context.REQUEST['cod_sessao_plen']!='' and request.has_key('ind_audiencia'):
   splen = []
   pauta = []
   data = ""
   for sp in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_audiencia=1, ind_excluido=0):
       data = context.pysc.data_converter_pysc(sp.dat_inicio_sessao)
       dat_ordem = context.pysc.data_converter_pysc(sp.dat_inicio_sessao)
       # obtém o nome do Presidente da Câmara titular
       lst_presidente = ''
       for sleg in context.zsql.periodo_comp_mesa_obter_zsql(num_legislatura=sp.num_legislatura,data=data):
           for cod_presidente in context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp,cod_cargo=1):
               for presidencia in context.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_presidente.cod_parlamentar):
                   lst_presidente = presidencia.nom_parlamentar
       dicsp = {}
       dicsp["sessao"] = 'AUDIÊNCIA PÚBLICA Nº ' + str(sp.num_sessao_plen) + '/' + str(sp.ano_sessao)
       dia = context.pysc.data_converter_por_extenso_pysc(data=sp.dat_inicio_sessao)
       hora = context.pysc.hora_formatar_pysc(hora=sp.hr_inicio_sessao)
       dicsp["datasessao"] = str(dia).decode('utf-8').upper()
       dicsp["ind_audiencia"] = 1
       splen.append(dicsp) 
   for ordem in context.zsql.ordem_dia_obter_zsql(dat_ordem=data, cod_sessao_plen=cod_sessao_plen, ind_excluido=0):
       # seleciona os detalhes de uma matéria
       dic = {} 
       dic["num_ordem"] = ordem.num_ordem
       if ordem.cod_materia != None:
         materia = context.zsql.materia_obter_zsql(cod_materia=ordem.cod_materia)[0]
         dic["cod_materia"] = ordem.cod_materia
         dic["cod_parecer"] = ''
         dic["link_materia"] = '<link href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+ordem.cod_materia+'">'+materia.des_tipo_materia.decode('utf-8').upper()+' Nº '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
         dic["id_materia"] = materia.des_tipo_materia.decode('utf-8').upper()+" nº "+str(materia.num_ident_basica)+"/"+str(materia.ano_ident_basica) 
         dic["txt_ementa"] = ordem.txt_observacao
         dic["des_numeracao"]=""
         numeracao = context.zsql.numeracao_obter_zsql(cod_materia=ordem.cod_materia)
         if len(numeracao):
            numeracao = numeracao[0]
            dic["des_numeracao"] = str(numeracao.num_materia)+"/"+str(numeracao.ano_materia) 
         dic["des_turno"]=""
         dic["des_quorum"]=""
         dic["tip_votacao"]=""
         dic["des_situacao"] = ""
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
         dic["substitutivo"] = ''
         lst_qtde_substitutivos=[]
         dic["emenda"] = ''
         lst_qtde_emendas=[]
         lst_emendas=[]
         lst_substitutivos=[]
         
       pauta.append(dic) 

else:
    splen = []
    pauta = []
    data = ""
    # seleciona dados da sessão plenária
    for sp in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0):
        data = context.pysc.data_converter_pysc(sp.dat_inicio_sessao)
        dat_ordem = context.pysc.data_converter_pysc(sp.dat_inicio_sessao)
        # obtém o nome do Presidente da Câmara titular
        lst_presidente = ''
        for sleg in context.zsql.periodo_comp_mesa_obter_zsql(num_legislatura=sp.num_legislatura,data=data):
            for cod_presidente in context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp,cod_cargo=1):
                for presidencia in context.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_presidente.cod_parlamentar):
                    lst_presidente = presidencia.nom_parlamentar
        dicsp = {}
        ts = context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sp.tip_sessao)[0]
        dicsp["sessao"] = str(sp.num_sessao_plen)+"ª SESSÃO "+ts.nom_sessao.decode('utf-8').upper()+" DA "+str(sp.num_legislatura)+"ª LEGISLATURA"
        dia = context.pysc.data_converter_por_extenso_pysc(data=sp.dat_inicio_sessao)
        hora = context.pysc.hora_formatar_pysc(hora=sp.hr_inicio_sessao)
        dicsp["datasessao"] = str(dia).decode('utf-8').upper()
        dicsp["ind_audiencia"] = 0
        splen.append(dicsp) 
        # seleciona as matérias que compõem a pauta na data escolhida
    for ordem in context.zsql.ordem_dia_obter_zsql(dat_ordem=data, cod_sessao_plen=cod_sessao_plen, ind_excluido=0):
        # seleciona os detalhes de uma matéria
        dic = {} 
        dic["num_ordem"] = ordem.num_ordem
        if ordem.cod_materia != None:
          materia = context.zsql.materia_obter_zsql(cod_materia=ordem.cod_materia)[0]
          dic["cod_materia"] = ordem.cod_materia
          dic["cod_parecer"] = ''
          dic["link_materia"] = '<link href="'+context.consultas.absolute_url()+'/materia/materia_mostrar_proc?cod_materia='+ordem.cod_materia+'">'+materia.des_tipo_materia.decode('utf-8').upper()+' Nº '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)+'</link>'
          dic["id_materia"] = materia.des_tipo_materia.decode('utf-8').upper()+" nº "+str(materia.num_ident_basica)+"/"+str(materia.ano_ident_basica) 
          dic["txt_ementa"] = ordem.txt_observacao
          dic["des_numeracao"]=""
          numeracao = context.zsql.numeracao_obter_zsql(cod_materia=ordem.cod_materia)
          if len(numeracao):
             numeracao = numeracao[0]
             dic["des_numeracao"] = str(numeracao.num_materia)+"/"+str(numeracao.ano_materia) 
          dic["des_turno"]=""
          for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
             dic["des_turno"] = turno.des_turno
          dic["des_quorum"]=""
          for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem.tip_quorum):
             dic["des_quorum"] = quorum.des_quorum
          dic["tip_votacao"]=""
          for tip_votacao in context.zsql.tipo_votacao_obter_zsql(tip_votacao=ordem.tip_votacao):
             dic["tip_votacao"] = tip_votacao.des_tipo_votacao
          dic["des_situacao"] = ""
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
              resultado = context.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=relatoria.tip_fim_relatoria)[0]
              dic_parecer['relatoria'] = 'Relatoria: ' + relator.nom_parlamentar
              dic_parecer['comissao'] = comissao.nom_comissao
              if relatoria.tip_conclusao == 'F':
                 dic_parecer['conclusao'] = 'Favorável à aprovação da matéria.'
              elif relatoria.tip_conclusao == 'C':
                 dic_parecer['conclusao'] = 'Contrário à aprovação da matéria.'
              dic_parecer['resultado'] = resultado.des_fim_relatoria
              dic_parecer["link_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/parecer_comissao/' + str(relatoria.cod_relatoria) + '_parecer.pdf' + '">' + 'Parecer da ' + comissao.nom_comissao + ' nº ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + '</link>'
              if resultado.des_fim_relatoria != 'Rejeitado':
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
              dic_substitutivo["id_substitutivo"] = '<link href="' + context.sapl_documentos.absolute_url() + '/substitutivo/' + str(substitutivo.cod_substitutivo) + '_substitutivo.pdf' + '">' + 'SUBSTITUTIVO Nº ' + str(substitutivo.num_substitutivo) + '</link>'
              dic_substitutivo["txt_ementa"] = substitutivo.txt_ementa
              dic_substitutivo["autoria"] = autoria
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
              dic_emenda["id_emenda"] = '<link href="' + context.sapl_documentos.absolute_url() + '/emenda/' + str(emenda.cod_emenda) + '_emenda.pdf' + '">' + 'Emenda nº ' + str(emenda.num_emenda) + ' (' + emenda.des_tipo_emenda + ')</link>'
              dic_emenda["txt_ementa"] = emenda.txt_ementa
              dic_emenda["autoria"] = autoria
              lst_emendas.append(dic_emenda)
              cod_emenda = emenda.cod_emenda
              lst_qtde_emendas.append(cod_emenda)
          dic["emendas"] = lst_emendas
          dic["emenda"] = len(lst_qtde_emendas)

        elif ordem.cod_parecer != None:
            for parecer in context.zsql.relatoria_obter_zsql(cod_relatoria=ordem.cod_parecer):
                materia = context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia)[0]
                dic["cod_materia"] = ''
                dic["cod_parecer"] = parecer.cod_relatoria
                dic["txt_ementa"] = ordem.txt_observacao
                dic["txt_materia"] = materia.txt_ementa
                dic["des_turno"]=""
                for turno in context.zsql.turno_discussao_obter_zsql(cod_turno=ordem.tip_turno):
                   dic["des_turno"] = turno.des_turno
                dic["des_quorum"]=""
                for quorum in context.zsql.quorum_votacao_obter_zsql(cod_quorum=ordem.tip_quorum):
                   dic["des_quorum"] = quorum.des_quorum
                dic["tip_votacao"]=""
                for tip_votacao in context.zsql.tipo_votacao_obter_zsql(tip_votacao=ordem.tip_votacao):
                   dic["tip_votacao"] = tip_votacao.des_tipo_votacao
                dic["des_situacao"] = ""
                for comissao in context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao):
                    sgl_comissao = comissao.sgl_comissao
                    nom_comissao = comissao.nom_comissao
                dic["id_materia"] = 'PARECER ' + sgl_comissao+ ' Nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) + " - " +  materia.sgl_tipo_materia +' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)                    
                dic["link_materia"] = '<link href="' + context.sapl_documentos.absolute_url() + '/parecer_comissao/' + str(ordem.cod_parecer) + '_parecer.pdf' + '">' + 'PARECER ' + sgl_comissao+ ' Nº ' + str(parecer.num_parecer) + '/' + str(parecer.ano_parecer) + " SOBRE O " +  materia.sgl_tipo_materia +' ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica) + '</link>'
                autores = context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
                fields = autores.data_dictionary().keys()
                dic["nom_autor"] = ""
                lista_autor = []
                for autor in autores:
                    for field in fields:
                        nome_autor = autor['nom_autor_join']
                    lista_autor.append(nome_autor)
                dic["nom_autor"] = ', '.join(['%s' % (value) for (value) in lista_autor])  
                dic["pareceres"] = ''
                dic["parecer"] = ''                        
                dic["substitutivo"] = ''
                dic["substitutivos"] = ''
                dic["emenda"] = ''
                dic["emendas"] = ''

        # adiciona o dicionário na pauta
        pauta.append(dic) 

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
if casa["end_email_casa"]!=None and casa["end_email_casa"]!="": 
   if casa["end_web_casa"]!="" and casa["end_web_casa"]!=None:
      linha2= linha2 + " - "
   linha2 = linha2 +"E-mail: "+casa["end_email_casa"]
dat_emissao = DateTime().strftime("%d/%m/%Y")
rodape = [linha1, linha2, dat_emissao]
    
sessao=session.id
caminho = context.pdf_ordem_dia_gerar(sessao, imagem, dat_ordem, cod_sessao_plen, splen, pauta, cabecalho, rodape, lst_presidente)
if caminho=='aviso':
   return response.redirect('mensagem_emitir_proc')
else:
   response.redirect(caminho)
