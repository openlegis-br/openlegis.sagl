## Script (Python) "gerar_etiquetas_pdf"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=lst_tip_instituicao, txa_txt_nom_instituicao, txa_txt_nom_responsavel, lst_categoria
##title=
##


REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE
session = REQUEST.SESSION

results =  context.zsql.instituicao_obter_zsql(tip_instituicao=REQUEST['lst_tip_instituicao'],
                                               cod_categoria=REQUEST['lst_categoria'],
                                               txt_nom_instituicao=REQUEST['txa_txt_nom_instituicao'], 
                                               txt_nom_responsavel=REQUEST['txa_txt_nom_responsavel'],
                                               cod_localidade=REQUEST['lst_localidade'])

dados = []
for row in results:
    r=[]
    # Label, Data
    if row.txt_forma_tratamento != None and row.txt_forma_tratamento != '':
       r.append(row.txt_forma_tratamento)

    if (row.nom_responsavel != None and row.nom_responsavel != '') and (row.nom_responsavel != row.nom_instituicao):
       r.append(row.nom_responsavel)

    if row.des_cargo != None and row.des_cargo != '':
       r.append(row.des_cargo)

    if row.des_cargo == None and row.des_cargo == '' and row.nom_instituicao != None and row.nom_instituicao != '':
       r.append(row.nom_instituicao)

    if row.end_instituicao != None and row.nom_bairro != None and row.nom_bairro != '':
       r.append(row.end_instituicao + " - " +row.nom_bairro)

    elif row.end_instituicao!=None and (row.nom_bairro==None or row.nom_bairro ==''):
       r.append(row.end_instituicao)

    nom_cidade = row.nom_localidade.upper().encode('utf-8') + ' - ' + row.sgl_uf

    if row.num_cep != None:
       r.append('CEP '+row.num_cep+' ' +str(nom_cidade))
    else:
       r.append(str(nom_cidade))

    dados.append(r)

return context.extensions.pdflabels(dados)

