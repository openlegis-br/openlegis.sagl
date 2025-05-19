## Script (Python) "usuarios_carregar_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=svalue, cod_documento
##title=
##
import json

response = context.REQUEST.RESPONSE
response.setHeader("Access-Control-Allow-Origin", "*")

def formatar_usuario(usuario):
    """Formata o dicionário do usuário com nome e cargo."""
    nome = usuario.nom_completo
    cargo = usuario.nom_cargo or ''
    if cargo:
        nome += f" ({cargo})"
    return {
        'id': usuario.cod_usuario,
        'name': nome,
    }

lst_usuarios = []

if svalue:
    usuarios = context.zsql.usuario_unid_tram_obter_zsql(cod_unid_tramitacao=svalue)
    for usuario in usuarios:
        if usuario.ind_leg != '0' or usuario.ind_adm != '0':
            lst_usuarios.append(formatar_usuario(usuario))
    lst_usuarios.sort(key=lambda u: u['name'])
else:
    usuarios = context.zsql.usuario_obter_zsql(ind_excluido=0, ind_ativo=1)
    lst_usuarios = [formatar_usuario(u) for u in usuarios]

return json.dumps(lst_usuarios)
