## Script (Python) "proposicoes_json"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_autor, tip_materia='', txt_ano=""
##title=
##

import collections 
import simplejson as json

context.REQUEST.RESPONSE.setHeader("Access-Control-Allow-Origin", "*")

materias=[]
status = []
for materia in context.zsql.materia_pesquisar_zsql(tip_id_basica=tip_materia,
                                                   ano_ident_basica=txt_ano, 
                                                   cod_autor=cod_autor):
    dic={}
    dic['des_status'] = ''
    for tramitacao in context.zsql.tramitacao_obter_zsql(cod_materia=materia.cod_materia, ind_ult_tramitacao=1):
        if tramitacao.cod_materia:
           dic['cod_status'] = int(tramitacao.cod_status)
           dic['sgl_status'] = str(tramitacao.sgl_status)
           dic['des_status'] = str(tramitacao.des_status)
    dic['cod_materia'] = int(materia.cod_materia)
    dic['titulo'] = materia.des_tipo_materia.decode('utf-8').upper()+" N° "+str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
    materias.append(dic)

count = collections.Counter([d['des_status'] for d in materias])

counts = dict(count)

results = []
for key in counts:
    dic =  {}
    dic['label'] = key
    dic['count'] = counts[key]
    if dic['label'] != '':
       results.append(dic)

serialized = json.dumps(results, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
print(serialized.decode())
return printed
