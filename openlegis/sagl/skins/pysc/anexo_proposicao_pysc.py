## Script (Python) "anexo_proposicao_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_proposicao, listar=None, nomear=None
##title=
##
if listar:
    documentos = context.sapl_documentos.proposicao.objectIds()
    existentes = [documento for documento in documentos if documento.startswith(cod_proposicao) and len(documento) == len(cod_proposicao) or documento.startswith(str(cod_proposicao) + '_anexo_')]
    ordenados = []
    for item in existentes:
        dic = {}
        i =  item.split('.')[0]
        dic['seq'] = int(i.split('_')[-1])
        dic['file'] = item
        ordenados.append(dic)
    ordenados.sort(key=lambda dic: dic['seq'], reverse=False)
    lista = []
    for item in ordenados:
        lista.append(item['file'])
    return lista

if nomear:
    documentos = context.sapl_documentos.proposicao.objectIds()
    existentes = [documento for documento in documentos if documento.startswith(cod_proposicao) and len(documento) == len(cod_proposicao) or documento.startswith(cod_proposicao + '_anexo_')]
    count = 1
    while True:
        nome = cod_proposicao + '_anexo_' + str(count)+ '.pdf'
        if nome not in existentes:
            return nome
            break
        else:
            count+=1
