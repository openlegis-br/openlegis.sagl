## Script (Python) "gerar_etiquetas_pdf"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=lst_tip_instituicao, txa_txt_nom_instituicao, txa_txt_nom_responsavel, lst_txt_atividade, lst_categoria, lst_txt_origem
##title=
##

REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE
session = REQUEST.SESSION

results =  context.zsql.instituicao_obter_zsql(tip_instituicao=REQUEST['lst_tip_instituicao'],
                                               cod_categoria=REQUEST['lst_categoria'],
                                               txt_atividade=REQUEST['lst_txt_atividade'],
                                               txt_origem=REQUEST['lst_txt_origem'],
                                               txt_nom_instituicao=REQUEST['txa_txt_nom_instituicao'], 
                                               txt_nom_responsavel=REQUEST['txa_txt_nom_responsavel'],
                                               cod_localidade=REQUEST['lst_localidade'])

dados = []
for row in results:
    r=[]
    # Label, Data
    if row.txt_forma_tratamento != None and row.txt_forma_tratamento != '':
       r.append(row.txt_forma_tratamento.title())

    if (row.nom_responsavel != None and row.nom_responsavel != '') and (row.nom_responsavel != row.nom_instituicao):
       r.append(row.nom_responsavel.upper())

    if row.des_cargo != None and row.des_cargo != '':
       r.append(row.des_cargo.title().title())

    if row.end_instituicao != None and row.nom_bairro != None and row.nom_bairro != '':
       r.append(row.end_instituicao.title() + " - " +row.nom_bairro.title())

    elif row.end_instituicao!=None and (row.nom_bairro==None or row.nom_bairro ==''):
       r.append(row.end_instituicao.title())

    nom_cidade = row.nom_localidade.upper() + ' - ' + row.sgl_uf

    if row.num_cep != None:
       r.append('CEP '+str(row.num_cep)+' ' +str(nom_cidade))
    else:
       r.append(str(nom_cidade))

    dados.append(r)

return context.extensions.pdflabels(dados)
