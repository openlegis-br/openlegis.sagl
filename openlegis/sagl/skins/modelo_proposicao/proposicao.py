## Script (Python) "proposicao"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_proposicao, modelo_proposicao, modelo_path
##title=
##
import json
from Products.CMFCore.utils import getToolByName
from DateTime import DateTime

st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

# -----------------------------------------------------------------------------
# Utilidades (sem prefixo "_")
# -----------------------------------------------------------------------------
def first_item(seq):
    try:
        return seq[0]
    except Exception:
        return None

def to_uppercase(s):
    return (s or '').upper()

def safe_int_value(v, default=None):
    try:
        return int(v)
    except Exception:
        return default

# -----------------------------------------------------------------------------
# Informações da Casa / Localidade
# -----------------------------------------------------------------------------
inf_basicas_dic = {}
casa = {}
for k, v in context.sapl_documentos.props_sagl.propertyItems():
    casa[k] = v

loc = first_item(context.zsql.localidade_obter_zsql(cod_localidade=casa.get("cod_localidade")))
uf_lista = context.zsql.localidade_obter_zsql(tip_localidade="U")

nom_estado = ''
if loc:
    for uf in uf_lista:
        if getattr(loc, 'sgl_uf', '') == getattr(uf, 'sgl_uf', ''):
            nom_estado = getattr(uf, 'nom_localidade', '')
            break

inf_basicas_dic['nom_camara'] = casa.get('nom_casa', '')
inf_basicas_dic['nom_estado'] = nom_estado
if loc:
    inf_basicas_dic['nom_localidade'] = getattr(loc, 'nom_localidade', '')
    inf_basicas_dic['sgl_uf'] = getattr(loc, 'sgl_uf', '')
else:
    inf_basicas_dic['nom_localidade'] = ''
    inf_basicas_dic['sgl_uf'] = ''

# URL de validação
try:
    inf_basicas_dic['url_validacao'] = context.generico.absolute_url() + "/conferir_assinatura"
except Exception:
    try:
        inf_basicas_dic['url_validacao'] = context.absolute_url() + "/conferir_assinatura"
    except Exception:
        inf_basicas_dic['url_validacao'] = "/conferir_assinatura"

inf_basicas_dic['id_materia'] = ''
inf_basicas_dic['des_tipo_proposicao'] = ''

# -----------------------------------------------------------------------------
# Obter Proposição
# -----------------------------------------------------------------------------
proposicoes = context.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao)
proposicao = first_item(proposicoes)

if not proposicao:
    RESPONSE.setStatus(404)
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return json.dumps(
        {"success": False, "message": "Proposição não encontrada."},
        ensure_ascii=False
    )

inf_basicas_dic['des_tipo_proposicao'] = getattr(proposicao, 'des_tipo_proposicao', '')

num_proposicao = proposicao.cod_proposicao
nom_arquivo = f"{proposicao.cod_proposicao}.odt"
des_tipo_materia = to_uppercase(getattr(proposicao, 'des_tipo_proposicao', ''))
num_ident_basica = ''  # permanece conforme contrato original
ano_ident_basica = DateTime(datefmt='international').strftime("%Y")
txt_ementa = getattr(proposicao, 'txt_descricao', '') or ''
dat_apresentacao = context.pysc.data_converter_por_extenso_pysc(
    data=DateTime(datefmt='international').strftime("%d/%m/%Y")
)

# Justificativa (limpa/normalizada)
orig_just = getattr(proposicao, 'txt_justificativa', None)
if orig_just and orig_just.strip():
    inf_basicas_dic['txt_justificativa'] = " ".join(orig_just.split())
else:
    inf_basicas_dic['txt_justificativa'] = orig_just or ''

# Assunto / Órgão responsável (se houver)
inf_basicas_dic['des_assunto'] = ''
inf_basicas_dic['orgao_responsavel'] = ''
if getattr(proposicao, 'cod_assunto', None) is not None:
    for assunto in context.zsql.assunto_proposicao_obter_zsql(cod_assunto=proposicao.cod_assunto):
        inf_basicas_dic['des_assunto'] = getattr(assunto, 'des_assunto', '')
        inf_basicas_dic['orgao_responsavel'] = getattr(assunto, 'nom_orgao', '')

# -----------------------------------------------------------------------------
# Matéria vinculada (se houver)
# -----------------------------------------------------------------------------
materia_vinculada = {}
if getattr(proposicao, 'cod_materia', None) is not None:
    for materia in context.zsql.materia_obter_zsql(cod_materia=proposicao.cod_materia):
        materia_vinculada['id_materia'] = f"{materia.des_tipo_materia} nº {materia.num_ident_basica}/{materia.ano_ident_basica}"
        materia_vinculada['txt_ementa'] = getattr(materia, 'txt_ementa', '')
        # Autoria da matéria vinculada (lista textual)
        autores = context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
        lista_autor = []
        for a in autores:
            lista_autor.append(a.get('nom_autor_join', ''))
        materia_vinculada['autoria'] = ', '.join([str(x) for x in lista_autor if x])

        # Nome do autor (para templates que exigem)
        if autores:
            try:
                inf_basicas_dic['nome_autor'] = to_uppercase(autores[-1].get('nom_autor_join', ''))
            except Exception:
                inf_basicas_dic['nome_autor'] = ''

    # Caso Parecer
    if inf_basicas_dic['des_tipo_proposicao'] in ('Parecer', 'Parecer de Comissão'):
        inf_basicas_dic['nom_comissao'] = 'COMISSÃO DE XXXXXXX'
        inf_basicas_dic['id_materia'] = materia_vinculada.get('id_materia', '')
        inf_basicas_dic['data_parecer'] = context.pysc.data_converter_por_extenso_pysc(
            data=DateTime(datefmt='international').strftime("%d/%m/%Y")
        )
        # Relator
        for rel in context.zsql.autor_obter_zsql(cod_autor=proposicao.cod_autor):
            inf_basicas_dic['nom_relator'] = getattr(rel, 'nom_autor_join', '')
            break
        # Presidente da Comissão (placeholder)
        inf_basicas_dic['nom_presidente_comissao'] = 'XXXXXXXX'

# -----------------------------------------------------------------------------
# Autor principal (nom_autor = lista de dicts exigida pelo gerador)
# -----------------------------------------------------------------------------
apelido_autor = ''
nom_autor = []

autores_principais = context.zsql.autor_obter_zsql(cod_autor=proposicao.cod_autor)
for autor in autores_principais:
    autor_dic = {
        'nome_autor': to_uppercase(getattr(autor, 'nom_autor_join', '')),
        'apelido_autor': to_uppercase(getattr(autor, 'nom_autor_join', '')),
        'cod_autor': safe_int_value(autor.get('cod_autor'), None),
        'cargo': '',
        'partido': ''
    }

    if getattr(autor, 'cod_parlamentar', None) is not None:
        parlamentares = context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar)
        p = first_item(parlamentares)
        if p:
            if getattr(p, 'sex_parlamentar', '') == 'M':
                nom_cargo = 'Vereador'
                info_gabinete = 'Gabinete do ' + nom_cargo
            elif getattr(p, 'sex_parlamentar', '') == 'F':
                nom_cargo = 'Vereadora'
                info_gabinete = 'Gabinete da ' + nom_cargo
            else:
                nom_cargo = ''
                info_gabinete = ''

            autor_dic['nome_autor'] = to_uppercase(getattr(p, 'nom_completo', autor_dic['nome_autor']))
            autor_dic['apelido_autor'] = to_uppercase(getattr(p, 'nom_parlamentar', autor_dic['apelido_autor']))
            autor_dic['cargo'] = nom_cargo
            autor_dic['partido'] = getattr(p, 'sgl_partido', '') or ''
            inf_basicas_dic['info_gabinete'] = to_uppercase(info_gabinete + ' ' + getattr(autor, 'nom_autor_join', ''))
    elif getattr(autor, 'des_cargo', '') in ('Prefeito Municipal', 'Prefeita Municipal'):
        usuarios = context.zsql.usuario_obter_zsql(col_username=autor.col_username)
        u = first_item(usuarios)
        if u:
            autor_dic['nome_autor'] = to_uppercase(getattr(u, 'nom_completo', autor_dic['nome_autor']))
            autor_dic['apelido_autor'] = to_uppercase(getattr(u, 'nom_completo', autor_dic['apelido_autor']))
        autor_dic['cargo'] = getattr(autor, 'des_cargo', '')
        autor_dic['partido'] = ''
        inf_basicas_dic['info_gabinete'] = ''
    else:
        # Outros tipos de autor (cidadão, entidade, etc.)
        inf_basicas_dic['info_gabinete'] = ''

    nom_autor.append(autor_dic)

# Se não definimos nome_autor base para templates, usa o principal (fallback)
if not inf_basicas_dic.get('nome_autor') and nom_autor:
    inf_basicas_dic['nome_autor'] = nom_autor[0]['nome_autor']

# -----------------------------------------------------------------------------
# Tratamento especial para Indicação: montar ementa
# Regra: se NÃO houver logradouro, incluir bairro, complemento e CEP (se existirem)
# -----------------------------------------------------------------------------
if inf_basicas_dic['des_tipo_proposicao'] == 'Indicação':
    assunto = to_uppercase(inf_basicas_dic.get('des_assunto', ''))
    orgao = to_uppercase(inf_basicas_dic.get('orgao_responsavel', ''))

    logradouro = getattr(proposicao, 'nom_logradouro', '') or REQUEST.get('txt_nom_logradouro', '')
    complemento = getattr(proposicao, 'complemento_endereco', '') or REQUEST.get('txt_complemento_endereco', '')
    bairro = getattr(proposicao, 'nom_bairro', '') or REQUEST.get('txt_nom_bairro', '')
    cep = getattr(proposicao, 'num_cep', '') or REQUEST.get('txt_num_cep', '')

    def preposicao_ao_ou_a(orgao_nome):
        orgaos_femininos = ['Secretaria', 'Diretoria', 'Procuradoria', 'Comissão', 'Ouvidoria', 'Futel']
        for palavra in orgaos_femininos:
            if palavra.lower() in (orgao_nome or '').lower():
                return 'à'
        return 'ao'

    ementa_odt = ""
    if orgao:
        ementa_odt += f"{preposicao_ao_ou_a(orgao)} {orgao} para "
    else:
        ementa_odt += " para "

    if assunto:
        ementa_odt += assunto.strip() + " "

    if logradouro:
        # Caso com logradouro: regra tradicional
        ementa_odt += "na " + logradouro
        if complemento:
            ementa_odt += ", " + complemento
        if bairro:
            ementa_odt += ", " + bairro
        if cep and cep != '00000-000':
            ementa_odt += ", CEP " + cep
        ementa_odt += "."
    else:
        # Novo comportamento: sem logradouro → bairro, complemento e CEP (quando existirem)
        partes = []
        if bairro:
            partes.append(f"no bairro {bairro}")
        if complemento:
            partes.append(complemento)
        if cep and cep != '00000-000':
            partes.append("CEP " + cep)

        if partes:
            ementa_odt += " " + ", ".join(partes) + "."
        else:
            ementa_odt += "."

    txt_ementa = ementa_odt

# -----------------------------------------------------------------------------
# Subscritores (exclui autores principais e evita duplicados)
# -----------------------------------------------------------------------------
data_atual = DateTime(datefmt='international').strftime("%d/%m/%Y")
subscritores = []
outros_autores = context.zsql.autores_obter_zsql(txt_dat_apresentacao=data_atual)

main_ids = set()
for a in nom_autor:
    cid = a.get('cod_autor')
    if cid is not None:
        main_ids.add(cid)

seen = set()
for autor in outros_autores:
    cod_aut = safe_int_value(autor.get('cod_autor'), None)
    if cod_aut is None or cod_aut in main_ids or cod_aut in seen:
        continue

    outros_dic = {'cod_autor': cod_aut}
    if getattr(autor, 'cod_parlamentar', None) is not None:
        parlamentares = context.zsql.parlamentar_obter_zsql(cod_parlamentar=autor.cod_parlamentar)
        p = first_item(parlamentares)
        if p:
            partido_autor = getattr(p, 'sgl_partido', None) or "Sem partido"
            cargo = 'Vereador' if getattr(p, 'sex_parlamentar', '') == 'M' else ('Vereadora' if getattr(p, 'sex_parlamentar', '') == 'F' else '')
            outros_dic['nome_autor'] = getattr(p, 'nom_completo', '')
            outros_dic['apelido_autor'] = getattr(p, 'nom_parlamentar', '')
            outros_dic['partido'] = partido_autor
            outros_dic['cargo'] = cargo
    else:
        # Se não é parlamentar e a fonte não traz campos, mantém mínimos
        outros_dic.setdefault('nome_autor', autor.get('nom_autor_join', ''))
        outros_dic.setdefault('apelido_autor', autor.get('nom_autor_join', ''))
        outros_dic.setdefault('partido', '')
        outros_dic.setdefault('cargo', '')

    subscritores.append(outros_dic)
    seen.add(cod_aut)

# -----------------------------------------------------------------------------
# Mesa Diretora (data vigente)
# -----------------------------------------------------------------------------
inf_basicas_dic["lst_presidente"] = ''
inf_basicas_dic["lst_vpresidente"] = ''
inf_basicas_dic["lst_1secretario"] = ''
inf_basicas_dic["lst_2secretario"] = ''
inf_basicas_dic["lst_3secretario"] = ''

data_conv = context.pysc.data_converter_pysc(data=data_atual)
for legislatura in context.zsql.legislatura_obter_zsql(data=data_conv):
    for periodo in context.zsql.periodo_comp_mesa_obter_zsql(num_legislatura=legislatura.num_legislatura, data=data_conv):
        for membro in context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=periodo.cod_periodo_comp):
            parlamentar = first_item(context.zsql.parlamentar_obter_zsql(cod_parlamentar=membro.cod_parlamentar))
            if not parlamentar:
                continue
            if membro.des_cargo == 'Presidente':
                inf_basicas_dic["lst_presidente"] = parlamentar.nom_completo
            elif membro.des_cargo == 'Vice-Presidente':
                inf_basicas_dic["lst_vpresidente"] = parlamentar.nom_completo
            elif membro.des_cargo == '1º Secretário':
                inf_basicas_dic["lst_1secretario"] = parlamentar.nom_completo
            elif membro.des_cargo == '2º Secretário':
                inf_basicas_dic["lst_2secretario"] = parlamentar.nom_completo
            elif membro.des_cargo == '3º Secretário':
                inf_basicas_dic["lst_3secretario"] = parlamentar.nom_completo

# -----------------------------------------------------------------------------
# Prefeito(a) atual
# -----------------------------------------------------------------------------
inf_basicas_dic['lst_prefeito'] = 'Não Cadastrado'
prefeito = first_item(context.zsql.prefeito_atual_obter_zsql(data_composicao=data_conv))
if prefeito:
    inf_basicas_dic['lst_prefeito'] = getattr(prefeito, 'nom_completo', 'Não Cadastrado')

# -----------------------------------------------------------------------------
# Geração do ODT
# -----------------------------------------------------------------------------
try:
    st.proposicao_gerar_odt(
        inf_basicas_dic,
        num_proposicao,
        nom_arquivo,
        des_tipo_materia,
        num_ident_basica,
        ano_ident_basica,
        txt_ementa,
        materia_vinculada,
        dat_apresentacao,
        nom_autor,
        apelido_autor,
        subscritores,
        modelo_proposicao,
        modelo_path,
    )
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return json.dumps({"success": True, "message": "ODT gerado com sucesso!"}, ensure_ascii=False)
except Exception as e:
    RESPONSE.setStatus(500)
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return json.dumps({"success": False, "message": "Erro ao gerar ODT: %s" % e}, ensure_ascii=False)
