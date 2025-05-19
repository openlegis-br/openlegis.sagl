## Script (Python) "ata_comissao_gerar"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_reuniao
##title=
##

from Products.CMFCore.utils import getToolByName
from xml.sax.saxutils import escape

st = getToolByName(context, 'portal_sagl')
REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE

def get_autores(autorias):
    return ', '.join([autor['nom_autor_join'] for autor in autorias])

def get_autores_emenda(cod_emenda):
    autores = context.zsql.autoria_emenda_obter_zsql(cod_emenda=cod_emenda, ind_excluido=0)
    return get_autores(autores)

def get_autores_substitutivo(cod_substitutivo):
    autores = context.zsql.autoria_substitutivo_obter_zsql(cod_substitutivo=cod_substitutivo, ind_excluido=0)
    return get_autores(autores)

for rc in context.zsql.reuniao_comissao_obter_zsql(cod_reuniao=cod_reuniao, ind_excluido=0):
    ata_dic = {}
    nom_arquivo = f"{rc.cod_reuniao}_ata.odt"
    data = context.pysc.data_converter_pysc(rc.dat_inicio_reuniao)
    dia = context.pysc.data_converter_por_extenso_pysc(data=rc.dat_inicio_reuniao)

    comissao = context.zsql.comissao_obter_zsql(cod_comissao=rc.cod_comissao, ind_excluido=0)[0]
    ata_dic.update({
        "nom_comissao": comissao.nom_comissao,
        "sgl_comissao": comissao.sgl_comissao,
        "reuniao": f"{rc.num_reuniao}ª Reunião {rc.des_tipo_reuniao}",
        "tema": rc.txt_tema,
        "horareuniao": context.pysc.hora_formatar_pysc(hora=rc.hr_inicio_reuniao),
        "horafimreuniao": context.pysc.hora_formatar_pysc(hora=rc.hr_fim_reuniao) if rc.hr_fim_reuniao else '',
        "data": rc.dat_inicio_reuniao,
        "datareuniao": dia,
    })

    # Cache de presenças com cod_parlamentar como string
    presencas = {
        str(p.cod_parlamentar): p.nom_completo
        for p in context.zsql.reuniao_comissao_presenca_obter_zsql(cod_reuniao=rc.cod_reuniao, ind_excluido=0)
    }

    ata_dic["presidente"] = ''
    lst_membros, lst_presenca, lst_ausencia = [], [], []

    for periodo in context.zsql.periodo_comp_comissao_obter_zsql(data=DateTime(rc.dat_inicio_reuniao_ord), ind_excluido=0):
        for membro in context.zsql.composicao_comissao_obter_zsql(cod_comissao=rc.cod_comissao, cod_periodo_comp=periodo.cod_periodo_comp, ind_excluido=0):
            dic_composicao = {
                "nome": membro.nom_completo,
                "cargo": membro.des_cargo
            }
            lst_membros.append(dic_composicao)

            if membro.des_cargo == 'Presidente':
                ata_dic["presidente"] = membro.nom_completo

            if str(membro.cod_parlamentar) in presencas:
                lst_presenca.append(membro.nom_completo)
            else:
                lst_ausencia.append(membro.nom_completo)

    ata_dic["membros"] = lst_membros
    ata_dic["qtde_presenca"] = len(lst_presenca)
    ata_dic["presenca"] = ', '.join(lst_presenca)
    ata_dic["qtde_ausencia"] = len(lst_ausencia)
    ata_dic["ausencia"] = ', '.join(lst_ausencia)

    lst_pauta, lst_votacao = [], []
    for item in context.zsql.reuniao_comissao_pauta_obter_zsql(cod_reuniao=rc.cod_reuniao, ind_excluido=0):
        dic_votacao = {
            "num_ordem": item.num_ordem,
            "txt_ementa": escape(item.txt_observacao),
            "nom_relator": '',
            "nom_autor": '',
            "substitutivo": '',
            "substitutivos": '',
            "emenda": '',
            "emendas": '',
            "parecer": '',
            "resultado": ''
        }

        if item.cod_parecer:
            parecer = context.zsql.relatoria_obter_zsql(cod_relatoria=item.cod_parecer)[0]
            materia = context.zsql.materia_obter_zsql(cod_materia=parecer.cod_materia, ind_excluido=0)[0]
            comissao = context.zsql.comissao_obter_zsql(cod_comissao=parecer.cod_comissao, ind_excluido=0)[0]
            relator = context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
            conclusao = 'Favorável' if parecer.tip_conclusao == 'F' else 'Contrário'

            dic_votacao.update({
                "cod_materia": parecer.cod_materia,
                "nom_relator": f"Relatoria: {relator.nom_parlamentar}",
                "materia": f"<span><b>{item.num_ordem}</b>) <a href=\"{context.consultas.absolute_url()}/parecer_comissao/{item.cod_parecer}_parecer.pdf\">"
                           f"<b>Parecer {comissao.sgl_comissao} nº {parecer.num_parecer}/{parecer.ano_parecer}</b></a> - {conclusao} ao "
                           f"{materia.sgl_tipo_materia} nº {materia.num_ident_basica}/{materia.ano_ident_basica} - "
                           f"{escape(materia.txt_ementa)}</span>"
            })

        elif item.cod_materia:
            materia = context.zsql.materia_obter_zsql(cod_materia=item.cod_materia)[0]
            dic_votacao["cod_materia"] = item.cod_materia
            autores = context.zsql.autoria_obter_zsql(cod_materia=item.cod_materia)
            dic_votacao["nom_autor"] = get_autores(autores)
            dic_votacao["materia"] = f"<span><b>{item.num_ordem}</b>) <a href=\"{context.consultas.absolute_url()}/materia/materia_mostrar_proc?cod_materia={item.cod_materia}\">" \
                                     f"<b>{materia.des_tipo_materia} nº {materia.num_ident_basica}/{materia.ano_ident_basica}</b></a> - Autoria: {dic_votacao['nom_autor']} - " \
                                     f"{escape(item.txt_observacao)}</span>"

            if item.cod_relator:
                relator = context.zsql.parlamentar_obter_zsql(cod_parlamentar=item.cod_relator)[0]
                dic_votacao["nom_relator"] = f"Relatoria: {relator.nom_parlamentar}"

            relatorias = context.zsql.relatoria_obter_zsql(
                cod_materia=item.cod_materia,
                cod_comissao=rc.cod_comissao,
                ind_excluido=0,
                pesquisa=1
            )
            if relatorias:
                parecer = relatorias[0]
                dic_votacao["parecer"] = f". Parecer {ata_dic['sgl_comissao']} nº {parecer.num_parecer}/{parecer.ano_parecer}"
                parlamentar = context.zsql.parlamentar_obter_zsql(cod_parlamentar=parecer.cod_parlamentar)[0]
                dic_votacao["nom_relator"] = f"Relatoria: {parlamentar.nom_parlamentar}"

            if item.tip_resultado_votacao:
                resultado = context.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=item.tip_resultado_votacao, ind_excluido=0)[0]
                dic_votacao["resultado"] = f". Resultado: {resultado.des_fim_relatoria}"

            materia_str = dic_votacao["materia"] + ' ' + dic_votacao["nom_relator"] + dic_votacao["resultado"] + dic_votacao["parecer"]

            # Substitutivos
            substitutivos = []
            for sub in context.zsql.substitutivo_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
                autoria = get_autores_substitutivo(sub.cod_substitutivo)
                substitutivos.append({
                    "materia": f"Substitutivo nº {sub.num_substitutivo} - {autoria}",
                    "txt_ementa": escape(sub.txt_ementa),
                    "autoria": autoria
                })
            dic_votacao["substitutivos"] = substitutivos
            dic_votacao["substitutivo"] = len(substitutivos)

            # Emendas
            emendas = []
            for em in context.zsql.emenda_obter_zsql(cod_materia=item.cod_materia, ind_excluido=0):
                autoria = get_autores_emenda(em.cod_emenda)
                emendas.append({
                    "materia": f"Emenda {em.des_tipo_emenda} nº {em.num_emenda} - {autoria} - {escape(em.txt_ementa)}",
                    "txt_ementa": escape(em.txt_ementa),
                    "autoria": autoria
                })
            dic_votacao["emendas"] = emendas
            dic_votacao["emenda"] = len(emendas)

        lst_pauta.append(dic_votacao["materia"])
        lst_votacao.append(dic_votacao)

    ata_dic["lst_pauta"] = '; '.join(lst_pauta)
    ata_dic["lst_votacao"] = lst_votacao

    casa = dict(context.sapl_documentos.props_sagl.propertyItems())
    localidade = context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])[0]
    estado = next(
        uf.nom_localidade for uf in context.zsql.localidade_obter_zsql(tip_localidade="U")
        if uf.sgl_uf == localidade.sgl_uf
    )

    ata_dic.update({
        'nom_camara': casa['nom_casa'],
        'end_camara': casa['end_casa'],
        'nom_estado': estado,
        'nom_localidade': localidade.nom_localidade,
        'sgl_uf': localidade.sgl_uf
    })

return st.ata_comissao_gerar_odt(ata_dic, nom_arquivo)
