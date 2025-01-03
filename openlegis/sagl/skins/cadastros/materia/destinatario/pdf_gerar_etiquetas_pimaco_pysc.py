## Script (Python) "pdf_gerar_etiquetas_pimaco_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters= cod_materia
##title=
##

REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE
session = REQUEST.SESSION

results=[]
REQUEST=context.REQUEST
for item in context.zsql.destinatario_oficio_obter_zsql(cod_materia=REQUEST['cod_materia']):
    if item.cod_instituicao != None:
        destinatario = context.zsql.instituicao_obter_zsql(cod_instituicao=item.cod_instituicao)[0]
        dic={}
        dic['txt_forma_tratamento']=destinatario.txt_forma_tratamento
        dic['nom_responsavel']=destinatario.nom_responsavel
        dic['des_cargo']=destinatario.des_cargo
        dic['nom_instituicao']=destinatario.nom_instituicao
        dic['end_instituicao']=destinatario.end_instituicao
        dic['nom_bairro']=destinatario.nom_bairro
        dic['num_cep']=destinatario.num_cep
        dic['nom_cidade']=destinatario.nom_localidade.upper() + ' - ' + destinatario.sgl_uf
        results.append(dic)

#results = context.zsql.destinatario_oficio_obter_zsql(cod_materia=REQUEST['cod_materia'])

dados = []

for dic in results:
    r=[]
    # Label, Data
    if dic['txt_forma_tratamento'] != None:
       r.append(dic['txt_forma_tratamento'].title())

    if (dic['nom_responsavel'] != None and dic['nom_responsavel'] != '') and (dic['nom_responsavel'] != dic['nom_instituicao']):
       r.append(dic['nom_responsavel'].upper())

    if (dic['des_cargo'] != None and dic['des_cargo'] != '') and (dic['des_cargo'] != dic['nom_instituicao']):
       r.append(dic['des_cargo'].title())

    if dic['nom_instituicao'] != None and dic['nom_instituicao'] != '':
       r.append(dic['nom_instituicao'].title())

    if dic['end_instituicao'] != None and dic['nom_bairro'] != None and dic['nom_bairro'] != '':
       r.append(dic['end_instituicao'].title() + " - " +dic['nom_bairro'].title())

    elif dic['end_instituicao']!=None and dic['nom_bairro']==None:
       r.append(dic['end_instituicao'].title())

    if dic['num_cep'] != None:
       r.append('CEP '+dic['num_cep']+' ' +str(dic['nom_cidade']))
    else:
       r.append(str(dic['nom_cidade']))

    dados.append(r)

return context.extensions.pdflabels(dados)

