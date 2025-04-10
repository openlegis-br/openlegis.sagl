import os

request=context.REQUEST
response=request.RESPONSE
session= request.SESSION

data=DateTime(datefmt='international').strftime('%d/%m/%Y')

#Abaixo é gerada a string para o rodapé da página
casa={}
aux=context.sapl_documentos.props_sagl.propertyItems()
for item in aux:
 casa[item[0]]=item[1]
localidade=context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])
if len(casa["num_cep"])==8:
 cep=casa["num_cep"][:4]+"-"+casa["num_cep"][5:]
else:
 cep=""

linha1=casa["end_casa"]
if cep!="":
  if casa["end_casa"]!="" and casa["end_casa"]!=None:
     linha1 = linha1 + " - "
  linha1 = linha1 + "CEP "+cep
if localidade[0].nom_localidade!="" and localidade[0].nom_localidade!=None:
  linha1 = linha1 + " - "+localidade[0].nom_localidade+" "+localidade[0].sgl_uf
if casa["num_tel"]!="" and casa["num_tel"]!=None:
  linha1 = linha1 + " Tel.: "+ casa["num_tel"]

linha2=casa["end_web_casa"]
if casa["end_email_casa"]!="" and casa["end_email_casa"]!=None:
  if casa["end_web_casa"]!="" and casa["end_web_casa"]!=None:
    linha2 = linha2 + " - "
  linha2 =  linha2 + "E-mail: "+casa["end_email_casa"]

data_emissao=DateTime(datefmt='international').strftime("%d/%m/%Y")
rodape=[linha1,linha2,data_emissao]

#Por fim, gera-se as entradas para o cabeçalho
estados=context.zsql.localidade_obter_zsql(tip_localidade="u")
for uf in estados:
 if localidade[0].sgl_uf==uf.sgl_uf:
  nom_estado=uf.nom_localidade
  break
cabecalho={}
cabecalho["nom_casa"]=casa["nom_casa"]
cabecalho["nom_estado"]="Estado de "+nom_estado

#tenta buscar o logotipo da casa LOGO_CASA
if hasattr(context.sapl_documentos.props_sagl,'cabecalho.png'):
   imagem = context.sapl_documentos.props_sagl['cabecalho.png'].absolute_url()
   cabecalho["custom_image"]=True
elif hasattr(context.sapl_documentos.props_sagl,'logo_casa.gif'):
   imagem = context.sapl_documentos.props_sagl['logo_casa.gif'].absolute_url()
   cabecalho["custom_image"]=False
else:
   imagem = context.imagens.absolute_url() + "/brasao.gif"
   cabecalho["custom_image"]=False

#Por fim, utiliza o PythonScript para pesquisar os documentos e gerar os dados

documentos=[]
REQUEST=context.REQUEST
if REQUEST[str('tipo_documento')] != 'None':
  tipo_documento= REQUEST[str('tipo_documento')]
else: 
  tipo_documento = '' 
for documento in context.zsql.documento_administrativo_pesquisar_zsql(tip_documento=tipo_documento, num_documento=REQUEST['txt_num_documento'], ano_documento=REQUEST['txt_ano_documento'], num_protocolo=REQUEST['txt_num_protocolo'], ind_tramitacao=REQUEST['rad_tramitando'], des_assunto=REQUEST['txa_txt_assunto'], cod_status=REQUEST['lst_status'], lst_assunto=REQUEST['lst_assunto'], txt_interessado=REQUEST['txa_txt_interessado'], dat_apres1=REQUEST['dt_apres1'], dat_apres2=REQUEST['dt_apres2'], cod_unid_tramitacao=REQUEST['lst_localizacao'], cod_unid_tramitacao2=REQUEST['lst_tramitou'], rd_ordem=REQUEST['rd_ordenacao']):
        dic={}

        dic['titulo']=documento.des_tipo_documento.upper()+" N° "+str(documento.num_documento)+"/"+str(documento.ano_documento)
        dic['txt_assunto']=documento.txt_assunto
        dic['txt_interessado']=documento.txt_interessado      
           
        des_status = ''
        txt_tramitacao=''

        dic['localizacao_atual']=" "
        for tramitacao in context.zsql.tramitacao_administrativo_obter_zsql(cod_documento=documento.cod_documento,ind_ult_tramitacao=1):
            if tramitacao.cod_unid_tram_dest:
                cod_unid_tram = tramitacao.cod_unid_tram_dest
            else:
                cod_unid_tram = tramitacao.cod_unid_tram_local
            
            for unidade_tramitacao in context.zsql.unidade_tramitacao_obter_zsql(cod_unid_tramitacao = cod_unid_tram):
                if unidade_tramitacao.cod_orgao:
                    dic['localizacao_atual']=unidade_tramitacao.nom_orgao
                else:
                    dic['localizacao_atual']=unidade_tramitacao.nom_comissao
        
            des_status=tramitacao.des_status
            txt_tramitacao=tramitacao.txt_tramitacao

        dic['des_situacao']=des_status
        dic['ultima_acao']=txt_tramitacao

        dic['protocolo']= " "
        if documento.num_protocolo !=None:
          for protocolo in context.zsql.protocolo_obter_zsql(num_protocolo=documento.num_protocolo,ano_protocolo=documento.ano_documento):
            dic['protocolo']= "<b>Protocolo</b>: " + str(protocolo.num_protocolo) + "/" + str(documento.ano_documento) + " - Data de Entrada: " + context.pysc.iso_to_port_pysc(protocolo.dat_protocolo)
        else:
          dic['protocolo']= " "

        documentos.append(dic)

filtro={} # Dicionário que conterá os dados do filtro

# Atribuições diretas do REQUEST
filtro['numero']=REQUEST.txt_num_documento
filtro['ano']=REQUEST.txt_ano_documento
filtro['interessado']=REQUEST.txa_txt_interessado
filtro['assunto']=REQUEST.txa_txt_assunto
filtro['lst_assunto']=REQUEST.lst_assunto

filtro['tipo_documento']=''

filtro['tramitando']=''
if REQUEST.rad_tramitando=='1':
    filtro['tramitacao']='Sim'
elif REQUEST['rad_tramitando']=='0':
    filtro['tramitacao']='Não'

filtro['situacao_atual']=''
if REQUEST.lst_status!='':
    for status in context.zsql.status_tramitacao_administrativo_obter_zsql(ind_exluido=0,cod_status=REQUEST.lst_status):
        filtro['situacao_atual']=status.sgl_status + ' - ' + status.des_status

sessao=session.id
caminho = context.pdf_documento_administrativo_gerar(sessao,imagem,data,documentos,cabecalho,rodape,filtro)
if caminho=='aviso':
 return response.redirect('mensagem_emitir_proc')
else:
 response.redirect(caminho)
