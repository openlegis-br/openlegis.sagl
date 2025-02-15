## Script (Python) "download_documento_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_documento
##title=
##
request=context.REQUEST
response=request.RESPONSE

if cod_documento.isdigit():
 cod_documento = cod_documento
else:
 cod_documento = context.pysc.b64decode_pysc(codigo=str(cod_documento))

for documento in context.zsql.documento_administrativo_obter_zsql(cod_documento = cod_documento):
    download_name = str(documento.sgl_tipo_documento) + "-" + str(documento.num_documento)+ "-" + str(documento.ano_documento) + ".pdf"
    id_documento = "%s"%cod_documento+'_texto_integral.pdf'
    arquivo = getattr(context.sapl_documentos.administrativo,id_documento) 
    context.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
    context.REQUEST.RESPONSE.setHeader('Content-Disposition','inline; Filename=%s' % download_name) 
    if documento.ind_publico == 0 and request.AUTHENTICATED_USER.has_role(['Authenticated']):
       if context.consultas.documento_administrativo.verifica_permissao(cod_documento=cod_documento) == True:
          return arquivo
       else:
          mensagem = 'Acesso não autorizado!'
          mensagem_obs = 'A tentativa do usuário ' + request.AUTHENTICATED_USER.getUserName() + ' foi registrada no banco de dados.' 
          redirect_url=context.portal_url()+'/mensagem_emitir?tipo_mensagem=danger&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs
          response.redirect(redirect_url)
    elif documento.ind_publico == 1:
       return arquivo
    else:
       mensagem = 'Acesso não autorizado!'
       mensagem_obs = '' 
       redirect_url=context.portal_url()+'/mensagem_emitir?tipo_mensagem=danger&mensagem=' + mensagem + '&mensagem_obs=' + mensagem_obs
       response.redirect(redirect_url)

if context.dbcon_logs:
   context.zsql.logs_registrar_zsql(usuario = request['AUTHENTICATED_USER'].getUserName(), data=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'), modulo='documento_administrativo', metodo='download_documento_pdf', cod_registro=cod_documento, IP=context.pysc.get_ip(), dados='visualizou ou baixou texto integral') 
