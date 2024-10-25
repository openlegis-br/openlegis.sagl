request=context.REQUEST
response=request.RESPONSE
import json
REQUEST=context.REQUEST
if REQUEST[str('tipo_materia')] != 'None':
   tipo_materia = REQUEST[str('tipo_materia')]
else: 
   tipo_materia = '' 
lst_materias = []
for materia in context.zsql.materia_pesquisar_zsql(tip_id_basica=tipo_materia,
                                                   num_ident_basica=REQUEST['txt_numero'],
                                                   ano_ident_basica=REQUEST['txt_ano'], 
                                                   ind_tramitacao=REQUEST['rad_tramitando'],
                                                   des_assunto=REQUEST['txt_assunto'], 
                                                   cod_status=REQUEST['lst_status'],
                                                   dat_apresentacao=REQUEST['dt_apres'], 
                                                   dat_apresentacao2=REQUEST['dt_apres2'],
                                                   dat_publicacao=REQUEST['dt_public'], 
                                                   dat_publicacao2=REQUEST['dt_public2'],
                                                   cod_autor=REQUEST['hdn_cod_autor'],
                                                   cod_unid_tramitacao=REQUEST['lst_localizacao'],
                                                   cod_unid_tramitacao2=REQUEST['lst_tramitou'],
                                                   rd_ordem=REQUEST['rd_ordenacao']):
    data = {}
    data['codmateria'] = materia.cod_materia
    data['tipo'] = materia.des_tipo_materia
    data['numero'] = str(materia.num_ident_basica) + '-' + str(materia.ano_ident_basica)
    data['ano'] = materia.ano_ident_basica
    data['ementa'] = materia.txt_ementa
    data['autoria'] = ''
    autores = context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia, ind_excluido=0)
    fields = autores.data_dictionary().keys()
    lista_autor = []
    for autor in autores:
        for field in fields:
            nome_autor = autor['nom_autor_join']
        lista_autor.append(nome_autor)
    data['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor])
    data['partido'] = ''
    data['linkarquivo'] = ''
    if hasattr(context.sapl_documentos.materia, str(materia.cod_materia) + '_texto_integral.pdf'):
       data['linkarquivo'] = context.portal_url() + '/sapl_documentos/materia/' + str(materia.cod_materia) + '_texto_integral.pdf'
    data['casalegislativa'] = context.sapl_documentos.props_sagl.nom_casa
    data['prazo'] = ''
    for tram in context.zsql.tramitacao_obter_zsql(cod_materia=materia.cod_materia, ind_ult_tramitacao=1):
        if tram.dat_fim_prazo != None:
           data['prazo'] = tram.dat_fim_prazo
    lst_materias.append(data)

serialized = json.dumps(lst_materias, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
print(serialized.decode())
return printed

