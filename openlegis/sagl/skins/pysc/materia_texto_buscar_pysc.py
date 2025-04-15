## coding: utf-8
## Script (Python) "materia_texto_buscar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=assunto, tipo, ano
##title=Script para buscar matérias legislativas por assunto, tipo e ano
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

    tipos_materia_list = [] # Inicializa uma lista para armazenar a descrição completa dos tipos de matéria

    # Itera sobre cada item na lista de 'tipo' fornecida
    for item in tipo:
        # Busca no ZSQL o tipo de matéria legislativa correspondente ao 'item'
        tipos_materia_zsql = context.zsql.tipo_materia_legislativa_obter_zsql(tip_materia=item, ind_excluido=0)
        # Itera sobre os resultados da busca no ZSQL
        for tipo_materia in tipos_materia_zsql:
            # Formata a descrição completa do tipo de matéria (sigla - descrição) e adiciona à lista
            tipos_materia_list.append(f"{tipo_materia.sgl_tipo_materia} - {tipo_materia.des_tipo_materia}")

    # Se a lista de tipos de matéria não estiver vazia, adiciona uma condição 'IN' para buscar por esses tipos
    if tipos_materia_list:
        query_parts.append(In('tipo_materia', tipos_materia_list))

# Verifica se o parâmetro 'ano' foi fornecido
if ano:
    try:
        ano_int = int(ano) # Tenta converter o 'ano' para um inteiro
        query_parts.append(Eq('ano_materia', ano_int)) # Se a conversão for bem-sucedida, adiciona uma condição de igualdade para o ano
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

# Executa a consulta avançada no catálogo de matérias legislativas, ordenando os resultados por tipo, ano (descendente) e número (descendente)
results = context.sapl_documentos.materia.Catalog.evalAdvancedQuery(query,('tipo_materia', ('ano_materia','desc'), ('num_materia','desc'),))

return results # Retorna os resultados da busca
