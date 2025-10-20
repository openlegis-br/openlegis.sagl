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

from Products.CMFCore.utils import getToolByName
st = getToolByName(context, 'portal_sagl')

REQUEST = context.REQUEST
RESPONSE =  REQUEST.RESPONSE

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

inf_basicas_dic = {}
casa={}
aux=context.sapl_documentos.props_sagl.propertyItems()
for item in aux:
    casa[item[0]]=item[1]
localidade=context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])
estado = context.zsql.localidade_obter_zsql(tip_localidade="U")
for uf in estado:
    if localidade[0].sgl_uf == uf.sgl_uf:
       nom_estado = uf.nom_localidade
       break
inf_basicas_dic['nom_camara']= casa['nom_casa']
inf_basicas_dic["nom_estado"] = nom_estado
for local in context.zsql.localidade_obter_zsql(cod_localidade = casa['cod_localidade']):
    inf_basicas_dic['nom_localidade']= local.nom_localidade
    inf_basicas_dic['sgl_uf']= local.sgl_uf

inf_basicas_dic['url_validacao'] = "" + context.generico.absolute_url()+"/conferir_assinatura"

inf_basicas_dic['id_materia'] = ''

inf_basicas_dic['des_tipo_proposicao'] = ''

for proposicao in context.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao):
    inf_basicas_dic['des_tipo_proposicao']= proposicao.des_tipo_proposicao
    num_proposicao = proposicao.cod_proposicao
    nom_arquivo = str(proposicao.cod_proposicao)+'.odt'
    des_tipo_materia = proposicao.des_tipo_proposicao.upper()
    num_ident_basica = ''
    ano_ident_basica = DateTime(datefmt='international').strftime("%Y")
    txt_ementa = proposicao.txt_descricao
    dat_apresentacao = context.pysc.data_converter_por_extenso_pysc(data=DateTime(datefmt='international').strftime("%d/%m/%Y"))

    inf_basicas_dic['des_assunto'] = ''
    inf_basicas_dic['orgao_responsavel'] = ''
    if proposicao.cod_assunto != None:
       for assunto in context.zsql.assunto_proposicao_obter_zsql(cod_assunto = proposicao.cod_assunto):
           inf_basicas_dic['des_assunto'] = assunto.des_assunto
           inf_basicas_dic['orgao_responsavel'] = assunto.nom_orgao

    # Justificativa (limpa/normalizada)
    orig_just = getattr(proposicao, 'txt_justificativa', None)
    if orig_just and orig_just.strip():
        inf_basicas_dic['txt_justificativa'] = " ".join(orig_just.split())
    else:
        inf_basicas_dic['txt_justificativa'] = orig_just or ''

    materia_vinculada = {}
    if proposicao.cod_materia != None:
       for materia in context.zsql.materia_obter_zsql(cod_materia = proposicao.cod_materia):
           materia_vinculada['id_materia'] = materia.des_tipo_materia + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
           materia_vinculada['txt_ementa'] = materia.txt_ementa
           materia_vinculada['autoria'] = ''
           autores = context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
           fields = list(autores.data_dictionary().keys())
           lista_autor = []
           for autor in autores:
               for field in fields:
                   nome_autor = autor['nom_autor_join']
               lista_autor.append(nome_autor)
           inf_basicas_dic['nome_autor'] = autor.nom_autor_join.upper()               
           materia_vinculada['autoria'] = ', '.join(['%s' % (value) for (value) in lista_autor]) 
       
       if proposicao.des_tipo_proposicao == 'Parecer' or proposicao.des_tipo_proposicao == 'Parecer de Comissão':
          inf_basicas_dic['nom_comissao'] = 'COMISSÃO DE XXXXXXX'
          inf_basicas_dic['id_materia'] = materia_vinculada['id_materia']
          inf_basicas_dic['data_parecer'] = context.pysc.data_converter_por_extenso_pysc(data=DateTime(datefmt='international').strftime("%d/%m/%Y"))
          for relator in context.zsql.autor_obter_zsql(cod_autor = proposicao.cod_autor):
              inf_basicas_dic['nom_relator'] = relator.nom_autor_join
          inf_basicas_dic['nom_presidente_comissao'] = 'XXXXXXXX'

    apelido_autor = ''
    nom_autor = []
    autores = context.zsql.autor_obter_zsql(cod_autor = proposicao.cod_autor)
    fields = list(autores.data_dictionary().keys())
    for autor in autores:
        autor_dic = {}
        for field in fields:
            nom_parlamentar = ''
            partido_autor = ''
            nom_cargo = ''                
            if autor.cod_parlamentar != None:
               parlamentares = context.zsql.parlamentar_obter_zsql(cod_parlamentar = autor.cod_parlamentar)
               for parlamentar in parlamentares:
                   nom_parlamentar = " - " + parlamentar.nom_parlamentar
                   if parlamentar.sex_parlamentar == 'M':
                      nom_cargo = 'Vereador'
                      info_gabinete = 'Gabinete do ' + nom_cargo
                   elif parlamentar.sex_parlamentar == 'F':
                      nom_cargo = 'Vereadora'
                      info_gabinete = 'Gabinete da ' + nom_cargo                 
                   if parlamentar.sgl_partido !=None:
                      partido_autor = parlamentar.sgl_partido
                   else:
                      partido_autor = ''
                   autor_dic['nome_autor'] = parlamentar.nom_completo.upper()
                   autor_dic['apelido_autor'] = parlamentar.nom_parlamentar.upper()
                   autor_dic['cargo'] = nom_cargo
                   autor_dic['partido'] = partido_autor
                   inf_basicas_dic['info_gabinete'] = info_gabinete.upper() + ' ' + autor.nom_autor_join.upper()
            elif autor.des_cargo == 'Prefeito Municipal' or autor.des_cargo == 'Prefeito Municipal':
               for usuario in context.zsql.usuario_obter_zsql(col_username=autor.col_username):
                   autor_dic['nome_autor'] = usuario.nom_completo.upper()
                   autor_dic['apelido_autor'] = usuario.nom_completo.upper()
                   autor_dic['cod_autor'] = autor['cod_autor']
                   autor_dic['cargo'] = autor.des_cargo
                   autor_dic['partido'] = ''
                   inf_basicas_dic['info_gabinete'] = ''
            else:
               autor_dic['nome_autor'] = autor.nom_autor_join.upper()
               autor_dic['apelido_autor'] = autor.nom_autor_join.upper()
               autor_dic['cod_autor'] = autor['cod_autor']
               autor_dic['cargo'] = ''
               autor_dic['partido'] = ''
               inf_basicas_dic['info_gabinete'] = ''
            autor_dic['cod_autor'] = int(autor['cod_autor'])
        nom_autor.append(autor_dic)

data_atual = DateTime(datefmt='international').strftime("%d/%m/%Y")
subscritores = []
outros_autores = context.zsql.autores_obter_zsql(txt_dat_apresentacao=data_atual)
fields = list(outros_autores.data_dictionary().keys())
for autor in outros_autores:
    outros_dic = {}
    for field in fields:
        if autor.cod_parlamentar != None:
           parlamentares = context.zsql.parlamentar_obter_zsql(cod_parlamentar = autor.cod_parlamentar)
           for parlamentar in parlamentares:
               if parlamentar.sgl_partido != None:
                  partido_autor = parlamentar.sgl_partido
               else:
                  partido_autor = "Sem partido"
               if parlamentar.sex_parlamentar == 'M':
                  cargo = "Vereador"
               elif parlamentar.sex_parlamentar == 'F':
                  cargo = "Vereadora"
           outros_dic['nome_autor'] = parlamentar.nom_completo
           outros_dic['apelido_autor'] = parlamentar.nom_parlamentar
           outros_dic['partido'] = partido_autor
           outros_dic['cargo'] = cargo
        outros_dic['cod_autor'] = int(autor['cod_autor'])
    subscritores.append(outros_dic)

outros=[]
for autor in nom_autor:
    for subscritor in subscritores:
        if autor.get('cod_autor',autor) != subscritor.get('cod_autor',subscritor):
           outros.append(subscritor)
subscritores = outros
inf_basicas_dic['subscritores'] = outros

# Presidente e Secretários
inf_basicas_dic["lst_presidente"] = ''
inf_basicas_dic["lst_vpresidente"] = ''
inf_basicas_dic["lst_1secretario"] = ''
inf_basicas_dic["lst_2secretario"] = ''
inf_basicas_dic["lst_3secretario"] = ''
data = context.pysc.data_converter_pysc(data_atual)
for legislatura in context.zsql.legislatura_obter_zsql(data=data):
    for periodo in context.zsql.periodo_comp_mesa_obter_zsql(num_legislatura=legislatura.num_legislatura,data=data):
        for membro in context.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=periodo.cod_periodo_comp):
            for parlamentar in context.zsql.parlamentar_obter_zsql(cod_parlamentar=membro.cod_parlamentar):
                if membro.des_cargo == 'Presidente':
                   inf_basicas_dic["lst_presidente"] = parlamentar.nom_completo
                if membro.des_cargo == 'Vice-Presidente':
                   inf_basicas_dic["lst_vpresidente"] = parlamentar.nom_completo
                elif membro.des_cargo == '1º Secretário':
                   inf_basicas_dic["lst_1secretario"] = parlamentar.nom_completo
                elif membro.des_cargo == '2º Secretário':
                   inf_basicas_dic["lst_2secretario"] = parlamentar.nom_completo
                elif membro.des_cargo == '3º Secretário':
                   inf_basicas_dic["lst_3secretario"] = parlamentar.nom_completo

# Prefeito
inf_basicas_dic['lst_prefeito'] = 'Não Cadastrado'
for prefeito in context.zsql.prefeito_atual_obter_zsql(data_composicao = data):
   inf_basicas_dic['lst_prefeito'] = prefeito.nom_completo

if inf_basicas_dic['des_tipo_proposicao'] == 'Indicação':
    inf_basicas_dic['txt_ementa'] = proposicao.txt_descricao
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
