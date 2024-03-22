## Script (Python) "proposicoes_contar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=caixa
##title=
##

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

revisao = []
assinatura = []
protocolo = []
incorporado = []
devolvido = []
pedido_devolucao = []

if caixa == 'revisao' or caixa == 'assinatura' or caixa == 'protocolo':
   for proposicao in context.zsql.proposicao_obter_zsql(ind_excluido=0, ind_pendente=1, ind_pedido_devolucao=0, ind_devolvido='0'):
       id_odt = str(proposicao.cod_proposicao) +'.odt'
       id_documento = str(proposicao.cod_proposicao) +'.pdf'
       id_documento_assinado = str(proposicao.cod_proposicao) +'_signed.pdf'
       dic={}
       dic['cod_proposicao'] = int(proposicao.cod_proposicao)
       dic['des_tipo_proposicao'] = proposicao.des_tipo_proposicao
       dic['txt_descricao'] = proposicao.txt_descricao
       dic['nom_autor'] = proposicao.nom_autor
       dic['dat_envio'] = proposicao.dat_envio
       dic['data_envio'] = DateTime(proposicao.dat_envio, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
       dic['dat_recebimento'] = proposicao.dat_recebimento
       dic['dat_devolucao'] = proposicao.dat_devolucao

       if proposicao.dat_recebimento==None and hasattr(context.sapl_documentos.proposicao,id_odt) and not hasattr(context.sapl_documentos.proposicao,id_documento) and not hasattr(context.sapl_documentos.proposicao,id_documento_assinado):
          revisao.append(dic)

       if proposicao.dat_recebimento==None and hasattr(context.sapl_documentos.proposicao,id_documento) and not hasattr(context.sapl_documentos.proposicao,id_documento_assinado):
          assinatura.append(dic)

       if proposicao.dat_envio!=None and proposicao.dat_recebimento==None and proposicao.dat_solicitacao_devolucao==None and hasattr(context.sapl_documentos.proposicao,id_documento_assinado):
          protocolo.append(dic)

   if caixa == 'revisao':
      revisao.sort(key=lambda dic: dic['data_envio'])
      return revisao

   if caixa == 'assinatura':
      assinatura.sort(key=lambda dic: dic['data_envio'], reverse=True)
      return assinatura

   if caixa == 'protocolo':
      protocolo.sort(key=lambda dic: dic['data_envio'])
      return protocolo

if caixa == 'incorporado':
   for proposicao in context.zsql.proposicao_obter_zsql(ind_excluido=0, ind_incorporado=1):
       dic={}
       dic['cod_proposicao'] = int(proposicao.cod_proposicao)
       dic['des_tipo_proposicao'] = proposicao.des_tipo_proposicao
       dic['txt_descricao'] = proposicao.txt_descricao
       dic['nom_autor'] = proposicao.nom_autor
       dic['dat_envio'] = proposicao.dat_envio
       dic['dat_recebimento'] = proposicao.dat_recebimento
       dic['data_recebimento'] = DateTime(proposicao.dat_recebimento, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
       dic['dat_devolucao'] = proposicao.dat_devolucao
       dic['ind_mat_ou_doc'] = proposicao.ind_mat_ou_doc
       dic['cod_mat_ou_doc'] = proposicao.cod_mat_ou_doc
       dic['cod_emenda'] = proposicao.cod_emenda
       dic['cod_substitutivo'] = proposicao.cod_substitutivo
       dic['cod_parecer'] = proposicao.cod_parecer
       
       incorporado.append(dic)
   incorporado.sort(key=lambda dic: dic['data_recebimento'], reverse=False)
   return incorporado

if caixa == 'devolvido':
   for proposicao in context.zsql.proposicao_obter_zsql(ind_excluido=0, ind_devolvido='1'):
       dic={}
       dic['cod_proposicao'] = int(proposicao.cod_proposicao)
       dic['des_tipo_proposicao'] = proposicao.des_tipo_proposicao
       dic['txt_descricao'] = proposicao.txt_descricao
       dic['nom_autor'] = proposicao.nom_autor
       dic['dat_envio'] = proposicao.dat_envio
       dic['dat_recebimento'] = proposicao.dat_recebimento
       dic['dat_devolucao'] = proposicao.dat_devolucao
       dic['data_devolucao'] = DateTime(proposicao.dat_devolucao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
       devolvido.append(dic)
   devolvido.sort(key=lambda dic: dic['data_devolucao'], reverse=False)
   return devolvido

if caixa == 'pedido_devolucao':
   for proposicao in context.zsql.proposicao_obter_zsql(ind_excluido=0, ind_pedido_devolucao='1'):
       dic={}
       dic['cod_proposicao'] = int(proposicao.cod_proposicao)
       dic['des_tipo_proposicao'] = proposicao.des_tipo_proposicao
       dic['txt_descricao'] = proposicao.txt_descricao
       dic['nom_autor'] = proposicao.nom_autor
       dic['dat_envio'] = proposicao.dat_envio
       dic['dat_recebimento'] = proposicao.dat_recebimento
       dic['data_envio'] = DateTime(proposicao.dat_envio, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
       dic['dat_solicitacao_devolucao'] = proposicao.dat_solicitacao_devolucao,
       dic['data_solicitacao_devolucao'] = DateTime(proposicao.dat_solicitacao_devolucao, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
       pedido_devolucao.append(dic)
   pedido_devolucao.sort(key=lambda dic: dic['data_solicitacao_devolucao'], reverse=True)
   return pedido_devolucao
