## Script (Python) "anexo_peticao_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_peticao='', listar=None, nomear=None, ordem='asc'
##title=
##
if listar:
    # Lista os anexos ordenados pelo número sequencial
    documentos = context.sapl_documentos.peticao.objectIds()
    existentes = [
        doc for doc in documentos 
        if doc.startswith(f"{cod_peticao}_anexo_") and doc.endswith('.pdf')
    ]
    
    # Extrai o número de sequência e ordena
    ordenados = []
    for doc in existentes:
        try:
            seq = int(doc.split('_')[-1].split('.')[0])
            ordenados.append((seq, doc))
        except ValueError:
            continue
    
    # Define a ordem de classificação
    reverse_sort = False if ordem.lower() == 'asc' else True
    ordenados.sort(key=lambda x: x[0], reverse=reverse_sort)
    
    return [doc for seq, doc in ordenados]

if nomear:
    # Gera o próximo nome sequencial disponível
    documentos = context.sapl_documentos.peticao.objectIds()
    count = 1
    while True:
        nome = f"{cod_peticao}_anexo_{count}.pdf"
        if nome not in documentos:
            return nome
        count += 1
