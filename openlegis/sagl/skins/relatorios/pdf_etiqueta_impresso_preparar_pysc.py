import os

request=context.REQUEST
response=request.RESPONSE
session= request.SESSION

data=DateTime(datefmt='international').strftime('%d/%m/%Y')

# PythonScript para pesquisar os destinatarios e gerar os dados

destinatarios=[]
REQUEST=context.REQUEST

destinatarios=[]
REQUEST=context.REQUEST
for item in context.zsql.destinatario_oficio_obter_zsql(cod_documento=REQUEST['cod_documento']):
    if item.cod_instituicao != None:
        destinatario = context.zsql.instituicao_obter_zsql(cod_instituicao=item.cod_instituicao)[0]
        dic={}
        dic['forma_tratamento']=str(destinatario.txt_forma_tratamento)
        dic['nome_responsavel']=destinatario.nom_responsavel
        dic['cargo']=destinatario.des_cargo
        dic['nome_instituicao']=destinatario.nom_instituicao
        dic['endereco']=destinatario.end_instituicao
        dic['bairro']=destinatario.nom_bairro
        dic['cep']=destinatario.num_cep
        dic['localidade']=destinatario.nom_localidade.upper() + ' - ' + destinatario.sgl_uf
        destinatarios.append(dic)

sessao=session.id
caminho = context.pdf_etiqueta_impresso_gerar_pysc(sessao,destinatarios)
if caminho=='aviso':
 return response.redirect('mensagem_emitir_proc')
else:
 response.redirect(caminho)

