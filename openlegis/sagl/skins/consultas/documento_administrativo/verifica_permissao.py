## Script (Python) "verifica_permissao"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_documento
##title=
##
can_view = False

REQUEST = context.REQUEST

if REQUEST['AUTHENTICATED_USER'].has_role(['Manager', 'Operador', 'Operador Modulo Administrativo', 'Consulta Modulo Administrativo']):
   can_view = True

elif REQUEST['AUTHENTICATED_USER'].has_role(['Authenticated']):
   for usuario in context.zsql.usuario_obter_zsql(col_username=REQUEST['AUTHENTICATED_USER'].getUserName()):
       if usuario.cod_usuario:
          cod_usuario = int(usuario.cod_usuario)
       else:
          cod_usuario = None
   if cod_usuario != None:
      # permissao no tipo de documento
      for documento in context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento, ind_excluido=0):
          if context.zsql.usuario_tipo_documento_obter_zsql(tip_documento=documento.tip_documento, cod_usuario=cod_usuario, ind_excluido=0):
             can_view = True 
      # pedido de assinatura
      if context.zsql.assinatura_documento_obter_zsql(codigo=cod_documento, tipo_doc='documento', cod_usuario=cod_usuario, ind_excluido=0):
         can_view = True
      # solicitacao de assinatura no texto integral
      if context.zsql.cientificacao_documento_obter_zsql(cod_documento=cod_documento, cod_cientificado=cod_usuario, ind_excluido=0):
         can_view = True
      # solicitacao de assinatura em documentos acessorios
      for item in context.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento=cod_documento):
          if context.zsql.assinatura_documento_obter_zsql(codigo=item.cod_documento_acessorio, tipo_doc='doc_acessorio_adm', cod_usuario=cod_usuario, ind_excluido=0):
             can_view = True
      # usuario de origem ou destino em tramitacoes
      for item in context.zsql.tramitacao_administrativo_obter_zsql(cod_documento=cod_documento, ind_excluido=0):
          if item.cod_usuario_local == cod_usuario or item.cod_usuario_dest == cod_usuario:
             can_view = True
          # usuario vinculado a unidade de origem ou destino em tramitacoes
          for unidade in context.zsql.usuario_unid_tram_obter_zsql(cod_unid_tramitacao=item.cod_unid_tram_dest,cod_usuario=cod_usuario):
             if item.cod_unid_tram_local == unidade.cod_unid_tramitacao or item.cod_unid_tram_dest == unidade.cod_unid_tramitacao:
                can_view = True
          # solicitacao de assinatura em tramitacoes
          if context.zsql.assinatura_documento_obter_zsql(codigo=item.cod_tramitacao, tipo_doc='tramitacao_adm', cod_usuario=cod_usuario):
             can_view = True

return can_view

