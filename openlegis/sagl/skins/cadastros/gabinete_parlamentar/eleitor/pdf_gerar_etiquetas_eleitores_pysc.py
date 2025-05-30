## Script (Python) "pdf_gerar_etiquetas_pessoas_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters= cod_parlamentar_corrente, txt_nom_eleitor, txt_dat_atendimento, txt_dat_atendimento2, txt_dia_aniversario, lst_mes_aniversario, rad_sex_eleitor, txt_des_estado_civil, rad_filhos, txt_des_profissao, txt_des_local_trabalho, txt_end_residencial, txt_nom_bairro, txt_num_cep, txt_nom_localidade, lst_txt_classe, lst_assessor, txt_dat_atualizacao, txt_dat_atualizacao2
##title=
##

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE
session = REQUEST.SESSION

results =  context.zsql.gabinete_eleitor_pesquisar_zsql(
                                               cod_parlamentar=REQUEST['cod_parlamentar_corrente'],
                                               nom_eleitor=REQUEST['txt_nom_eleitor'],
                                               dat_atendimento=REQUEST['txt_dat_atendimento'],
                                               dat_atendimento2=REQUEST['txt_dat_atendimento2'],
                                               dia_aniversario=REQUEST['txt_dia_aniversario'],
                                               dia_aniversario2=REQUEST['txt_dia_aniversario2'],
                                               mes_aniversario=REQUEST['lst_mes_aniversario'],
                                               sex_eleitor=REQUEST['rad_sex_eleitor'],
                                               des_estado_civil=REQUEST['txt_des_estado_civil'],
                                               rad_filhos=REQUEST['rad_filhos'],
                                               des_profissao=REQUEST['txt_des_profissao'],
                                               des_local_trabalho=REQUEST['txt_des_local_trabalho'],
                                               end_residencial=REQUEST['txt_end_residencial'],
                                               nom_bairro=REQUEST['txt_nom_bairro'],
                                               num_cep=REQUEST['txt_num_cep'],
                                               nom_localidade=REQUEST['txt_nom_localidade'],
                                               txt_classe=REQUEST['lst_txt_classe'],
                                               cod_assessor=REQUEST['lst_assessor'],
                                               dat_atualizacao=REQUEST['txt_dat_atualizacao'],
                                               dat_atualizacao2=REQUEST['txt_dat_atualizacao2']
                                               )
dados = []
for row in results:
    r=[]
    # Label, Data
    if row.nom_eleitor!=None:
     r.append(row.nom_eleitor.title())
    if row.end_residencial!=None and row.end_residencial!='':
     r.append(str(row.end_residencial).title())
    if row.nom_bairro!=None and row.nom_bairro!='':
       if row.num_cep==None or row.num_cep=='':
           r.append(row.nom_bairro.title())
       else:     
           r.append('CEP ' + str(row.num_cep) + ' ' + row.nom_bairro.title())
    if row.nom_localidade!=None:  
     r.append(str(row.nom_localidade) + ' ' + row.sgl_uf )
    dados.append(r)
return context.extensions.pdflabels(dados)
