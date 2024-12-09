# -*- coding: utf-8 -*-
import sys, os, string
import shutil
import zipfile
def baixar_emendas(context):
    cod_materia = context.REQUEST['cod_materia']  
    for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia, ind_excluido=0):
        zipname =  str('emendas_') + str(materia.sgl_tipo_materia) + '-' + str(materia.num_ident_basica) + '-' + str(materia.ano_ident_basica) + str('.zip')
    foldername =  'emendas'
    dirpath = os.path.join('/tmp/', foldername)
    if not os.path.exists(dirpath):
       os.makedirs(dirpath)
    for emenda in context.zsql.emenda_obter_zsql(cod_materia=cod_materia,ind_excluido=0):
        id_pdf = str(emenda.cod_emenda) + "_emenda.pdf"
        nom_arquivo = str('emenda_') + str(emenda.num_emenda).zfill(3) + ".pdf"
        if hasattr(context.sapl_documentos.emenda, id_pdf):
           arq = getattr(context.sapl_documentos.emenda, id_pdf)
           f = open(os.path.join(dirpath) + '/' + str(nom_arquivo), 'wb').write(bytes(arq.data))

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
       download.close()
       context.REQUEST.RESPONSE.headers['Content-Type'] = 'application/zip'
       context.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%zipname

    if os.path.exists(dirpath) and os.path.isdir(dirpath):
       shutil.rmtree(dirpath)
       file = '/tmp/'+zipname
       os.unlink(file)

    return arquivo
