## Script (Python) "vereadores_atuais"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##
import json
from xml.sax.saxutils import escape

context.REQUEST.RESPONSE.setHeader("Access-Control-Allow-Origin", "*")
request=context.REQUEST

for item in context.zsql.legislatura_atual_obter_zsql():
    num_legislatura = item.num_legislatura

data_atual = DateTime(datefmt='international').strftime("%d/%m/%Y")

lista_exercicio = []
exercicio = []
for item in context.zsql.autores_obter_zsql(txt_dat_apresentacao=data_atual):
    dic = {}
    dic['cod_parlamentar'] = item.cod_parlamentar
    dic['nom_parlamentar'] = item.nom_parlamentar
    dic['nom_completo'] = item.nom_completo
    foto = str(item.cod_parlamentar) + "_foto_parlamentar"
    if hasattr(context.sapl_documentos.parlamentar.fotos, foto):    
       dic['foto'] = request.SERVER_URL + '/sapl_documentos/parlamentar/fotos/' + foto
    else:
       dic['foto'] = request.SERVER_URL + '/imagens/avatar.png'   
    dic['link'] = request.SERVER_URL + '/consultas/parlamentar/parlamentar_mostrar_proc?cod_parlamentar=' + item.cod_parlamentar + '&iframe=0'
    dic['partido'] = ''
    for filiacao in context.zsql.parlamentar_data_filiacao_obter_zsql(num_legislatura=num_legislatura, cod_parlamentar=item.cod_parlamentar):    
        if filiacao.dat_filiacao != '0' and filiacao.dat_filiacao != None:
            for partido in context.zsql.parlamentar_partido_obter_zsql(dat_filiacao=filiacao.dat_filiacao, cod_parlamentar=item.cod_parlamentar):
                dic['partido'] = partido.sgl_partido
    for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=item.cod_parlamentar):
        if parlamentar.txt_biografia != None:
           dic['biografia'] = escape(parlamentar.txt_biografia)
        else:
           dic['biografia'] = ''
        dic['cod_parlamentar'] = parlamentar.cod_parlamentar              
    lista_exercicio.append(dic)

lista_exercicio.sort(key=lambda dic: dic['nom_completo'], reverse=False)

serialized = json.dumps(lista_exercicio, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
print((serialized.decode()))
return printed
