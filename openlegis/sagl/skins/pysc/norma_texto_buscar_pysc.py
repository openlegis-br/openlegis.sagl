## coding: utf-8
## Script (Python) "norma_texto_buscar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=assunto, tipo, ano
##title=Script para buscar normas jurídicas por assunto, tipo e ano
##

from Products.AdvancedQuery import And, Or, Eq, Ge, In

query_parts = [] # Inicializa uma lista para armazenar as partes da consulta

# Verifica se o parâmetro 'assunto' foi fornecido
if assunto:
    # Se 'assunto' foi fornecido, cria uma condição 'OU' para buscar no campo 'ementa' ou no índice 'PrincipiaSearchSource'
    query_parts.append(Or(Eq('ementa', assunto), Eq('PrincipiaSearchSource', assunto)))

# Verifica se o parâmetro 'tipo' foi fornecido
if tipo:
    v=str(tipo) # Converte o tipo para string para verificar se é um dígito
    if v.isdigit():
        tipo = [tipo] # Se for um dígito, assume que é um único tipo e o coloca em uma lista
    else:
        tipo = tipo # Se não for um dígito, assume que já é uma lista de tipos

    tipos_norma_list = [] # Inicializa uma lista para armazenar a descrição completa dos tipos de norma

    # Itera sobre cada item na lista de 'tipo' fornecida
    for item in tipo:
        # Busca no ZSQL o tipo de norma correspondente ao 'item'
        tipos_norma_zsql = context.zsql.tipo_norma_juridica_obter_zsql(tip_norma=item, ind_excluido=0)
        # Itera sobre os resultados da busca no ZSQL
        for tipo_norma in tipos_norma_zsql:
            # Formata a descrição completa do tipo de norma (sigla - descrição) e adiciona à lista
            tipos_norma_list.append(f"{tipo_norma.sgl_tipo_norma} - {tipo_norma.des_tipo_norma}")

    # Se a lista de tipos de norma não estiver vazia, adiciona uma condição 'IN' para buscar por esses tipos
    if tipos_norma_list:
        query_parts.append(In('tipo_norma', tipos_norma_list))

# Verifica se o parâmetro 'ano' foi fornecido
if ano:
    try:
        ano_int = int(ano) # Tenta converter o 'ano' para um inteiro
        query_parts.append(Eq('ano_norma', ano_int)) # Se a conversão for bem-sucedida, adiciona uma condição de igualdade para o ano
    except ValueError:
        # Lidar com o caso onde 'ano' não é um inteiro válido
        pass # Se a conversão falhar (não é um número), ignora o parâmetro 'ano'

# Verifica se alguma parte da consulta foi adicionada
if query_parts:
    # Se houver mais de uma parte na consulta, as combina usando um 'AND' lógico
    if len(query_parts) > 1:
        query = And(*query_parts)
    # Se houver apenas uma parte, a consulta é essa parte
    else:
        query = query_parts[0]
else:
    # Se nenhum parâmetro de busca válido foi fornecido, retorna uma lista vazia de resultados
    return []

# Executa a consulta avançada no catálogo de normas jurídicas, ordenando os resultados por tipo, ano (descendente) e número (descendente)
results = context.sapl_documentos.norma_juridica.Catalog.evalAdvancedQuery(query,('tipo_norma', ('ano_norma','desc'), ('num_norma','desc'),))

return results # Retorna os resultados da busca
