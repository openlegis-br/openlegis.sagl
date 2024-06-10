## Script (Python) "assinar_lote_pdf"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')
REQUEST = context.REQUEST

lista = []
for proposicao in context.zsql.proposicao_obter_zsql(ind_excluido=0, ind_enviado='0', ind_devolvido='0', col_username=REQUEST['AUTHENTICATED_USER'].getUserName()):
    if proposicao.des_tipo_proposicao=='Requerimento' or proposicao.des_tipo_proposicao=='Indicação' or proposicao.des_tipo_proposicao=='Moção':
       id_documento = str(proposicao.cod_proposicao)+'.pdf'
       id_documento_assinado = str(proposicao.cod_proposicao)+'_signed.pdf'
       if hasattr(context.sapl_documentos.proposicao,id_documento) and not hasattr(context.sapl_documentos.proposicao,id_documento_assinado):
          lista.append(int(proposicao.cod_proposicao))

for item in lista:
    return st.assinar_proposicao(lista) 
