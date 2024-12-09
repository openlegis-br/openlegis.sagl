# -*- coding: utf-8 -*-
import sys, os, string
import shutil
import zipfile
def baixar_anexadas(context):
    cod_materia_anexada = context.REQUEST['cod_materia_anexada']  
    for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia_anexada, ind_excluido=0):
        zipname =  str('anexadas_') + str(materia.sgl_tipo_materia) + '-' + str(materia.num_ident_basica) + '-' + str(materia.ano_ident_basica) + str('.zip')
    foldername =  'anexadas'
    dirpath = os.path.join('/tmp/', foldername)
    if not os.path.exists(dirpath):
       os.makedirs(dirpath)
    for anexada in context.zsql.anexada_obter_zsql(cod_materia_anexada=cod_materia_anexada,ind_excluido=0):
        id_pdf = str(anexada.cod_materia_principal) + "_texto_integral.pdf"
        nom_arquivo = str(anexada.tip_materia_principal) + '-' + str(anexada.num_materia_principal).zfill(3) + '-' + str(anexada.ano_materia_principal) +".pdf"
        if hasattr(context.sapl_documentos.materia, id_pdf):
           arq = getattr(context.sapl_documentos.materia, id_pdf)
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
