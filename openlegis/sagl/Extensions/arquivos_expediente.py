import sys, os, string
import shutil
import zipfile
def baixar_pdf(context):
    cod_sessao_plen = context.REQUEST['cod_sessao_plen']
    for sessao in context.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen, ind_excluido=0):
        for tipo_sessao in context.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=sessao.tip_sessao):
                zipname =  'materias_lidas-' + str(sessao.num_sessao_plen) + str(' Reunião ').decode('utf-8') + str(tipo_sessao.nom_sessao).encode("utf-8") + '.zip'           
    foldername =  'proposicoes'
    dirpath = os.path.join('/tmp/', foldername)
    if not os.path.exists(dirpath):
       os.makedirs(dirpath)
    orgaos = []
    arquivos = []
    for item in context.zsql.expediente_materia_obter_zsql(cod_sessao_plen=cod_sessao_plen,ind_excluido=0):
        if item.cod_materia != None:
           for materia in context.zsql.materia_obter_zsql(cod_materia=item.cod_materia,ind_excluido=0):
               if materia.des_tipo_materia == 'Indicação' or materia.des_tipo_materia == 'Requerimento' or materia.des_tipo_materia == 'Pedido de Informação' or materia.des_tipo_materia == 'Moção':
                  dic = {}
                  dic['id_pdf'] = str(materia.cod_materia) + "_texto_integral.pdf"
                  dic['nom_pdf'] = str(materia.sgl_tipo_materia).decode('utf-8') + '-' + str(materia.num_ident_basica) + '-' + str(materia.ano_ident_basica) + '.pdf'
                  id_pdf = str(materia.cod_materia) + "_texto_integral.pdf"
                  if hasattr(context.sapl_documentos.materia, id_pdf):
                     dic['nom_orgao'] = 'OUTROS'
                     for proposicao in context.zsql.proposicao_obter_zsql(ind_mat_ou_doc='M',cod_mat_ou_doc=materia.cod_materia):
                         if proposicao.cod_assunto != None:
                            for assunto in context.zsql.assunto_proposicao_obter_zsql(cod_assunto = proposicao.cod_assunto):
                                dic['nom_orgao'] = str(assunto.nom_orgao).decode('utf-8')
                                cod_assunto = assunto.cod_assunto
                                nom_orgao = str(assunto.nom_orgao).decode('utf-8')
                                orgaos.append(nom_orgao)
                                arquivos.append(dic)
                         else:
                                dic['nom_orgao'] = 'OUTROS'
                                nom_orgao = 'OUTROS'
                                orgaos.append(nom_orgao)
                                arquivos.append(dic)

    orgaos = [
     e
     for i, e in enumerate(orgaos)
     if orgaos.index(e) == i
    ]

    for orgao in orgaos:
        os.makedirs(os.path.join(dirpath, orgao))
        for arquivo in arquivos:
            if arquivo['nom_orgao'] == orgao:
               arq = getattr(context.sapl_documentos.materia, arquivo['id_pdf'])
               f = open(os.path.join(dirpath, orgao) + '/' + str(arquivo['nom_pdf']), 'wb').write(arq.data)

    if os.path.exists(dirpath):
       file_paths = []
       for root, directories, files in os.walk(dirpath):
           for filename in files:
               filepath = os.path.join(root, filename)
               file_paths.append(filepath)
       with zipfile.ZipFile('/tmp/' + zipname,'w') as zip:
           for file in file_paths:
               zip.write(file)
              
       download = open('/tmp/' + zipname, 'rb')
       arquivo = download.read()
       context.REQUEST.RESPONSE.headers['Content-Type'] = 'application/zip'
       context.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%zipname

    if os.path.exists(dirpath) and os.path.isdir(dirpath):
       shutil.rmtree(dirpath)
       file = '/tmp/'+zipname
       os.unlink(file)
       
    return arquivo
