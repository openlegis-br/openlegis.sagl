request=context.REQUEST
redirect_url=context.portal_url()+'/consultas/norma_juridica/pesquisa_normas?'+request.get('QUERY_STRING')
request.RESPONSE.redirect(redirect_url)
