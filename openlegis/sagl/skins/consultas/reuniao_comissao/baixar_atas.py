## Script (Python) "baixar_atas"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_comissao_sel, ano_reuniao_sel, tipo_sel="", status_sel=""
##title=
##
from DateTime import DateTime
from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

lst_reunioes = []

for reuniao in context.zsql.reuniao_comissao_obter_zsql(ano_reuniao=ano_reuniao_sel, cod_comissao=cod_comissao_sel, tipo=tipo_sel, status=status_sel):
    reunioes_dic = {}
    reunioes_dic['ata'] = str(reuniao.cod_reuniao)+'_ata.pdf'
    from_date_str = DateTime(reuniao.dat_inicio_reuniao, datefmt='international').strftime('%Y-%m-%d') + 'T' + reuniao.hr_inicio_reuniao + ':00'
    reunioes_dic['data'] = DateTime(from_date_str, datefmt='international').strftime('%Y-%m-%d %H:%M:%S')
    if hasattr(context.sapl_documentos.reuniao_comissao, str(reuniao.cod_reuniao)+'_ata.pdf'):
       lst_reunioes.append(reunioes_dic)

lst_reunioes.sort(key=lambda reunioes_dic: reunioes_dic['data'], reverse=False)

if lst_reunioes != []:
   return st.baixar_atas_comissao(lst_reunioes)
else:
   return 'Nada para exportar'
