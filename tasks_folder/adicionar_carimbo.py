from .utils import zope_task
from io import BytesIO
import pymupdf
from DateTime import DateTime
import logging

logger = logging.getLogger(__name__)

def aplicar_carimbo(arq, texto, sessao, presidente):
    """Insere um carimbo textual no canto superior direito da primeira página do PDF."""
    try:
        arquivo = BytesIO(bytes(arq.data))
        pdf = pymupdf.open(stream=arquivo)
        pdf.bake()
        w, h = pdf[0].rect.width, pdf[0].rect.height
        p = pymupdf.Point(w - 180, 100)
        shape = pdf[0].new_shape()
        shape.insert_text(p, f"{texto}\n{sessao}\n{presidente}", fontname="helv", fontsize=8)
        shape.commit()
        arq.update_data(pdf.tobytes(deflate=True, garbage=3, use_objstms=1))
        logger.info("Carimbo aplicado com sucesso.")
    except Exception as e:
        logger.exception(f"Erro ao aplicar carimbo no PDF: {e}")

@zope_task()
def adicionar_carimbo_task(portal, cod_sessao_plen, nom_resultado, cod_materia):
    skins = portal.portal_skins.sk_sagl

    if not cod_materia:
        raise ValueError("Código da matéria não informado.")

    if not nom_resultado:
        nom_resultado = "RESULTADO INDEFINIDO"

    hoje = DateTime()
    data_formatada = hoje.strftime('%d/%m/%Y')
    data_iso = hoje.strftime('%Y/%m/%d')

    id_sessao = ""
    nom_presidente = ""

    # Obter dados da sessão, se fornecido
    if cod_sessao_plen and cod_sessao_plen != "0":
        for item in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
            for tipo in skins.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao):
                id_sessao = f"{item.num_sessao_plen}ª {portal.sapl_documentos.props_sagl.reuniao_sessao} {tipo.nom_sessao}"
            data_formatada = item.dat_inicio_sessao.strftime('%d/%m/%Y')
            data_iso = item.dat_inicio.strftime('%Y/%m/%d')
            for comp in skins.zsql.composicao_mesa_sessao_obter_zsql(cod_sessao_plen=cod_sessao_plen, cod_cargo=1, ind_excluido=0):
                for parlamentar in skins.zsql.parlamentar_obter_zsql(cod_parlamentar=comp.cod_parlamentar):
                    nom_presidente = parlamentar.nom_parlamentar.upper()

    # Fallback se presidente não foi encontrado via sessão
    if not nom_presidente:
        for sleg in skins.zsql.periodo_comp_mesa_obter_zsql(data=data_iso):
            for pres in skins.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp, cod_cargo=1):
                for parlamentar in skins.zsql.parlamentar_obter_zsql(cod_parlamentar=pres.cod_parlamentar):
                    nom_presidente = parlamentar.nom_parlamentar.upper()

    # Texto do carimbo
    texto = nom_resultado.upper()
    sessao = f"{id_sessao} - {data_formatada}"
    presidente = f"Presidente: {nom_presidente}"

    nom_pdf_saida = None

    for materia in skins.zsql.materia_obter_zsql(cod_materia=cod_materia):
        storage_path = portal.sapl_documentos.materia
        nom_pdf_saida = f"{materia.cod_materia}_texto_integral.pdf"
        nom_pdf_redacao = f"{materia.cod_materia}_redacao_final.pdf"

        if hasattr(storage_path, nom_pdf_saida):
            arq = getattr(storage_path, nom_pdf_saida)
            aplicar_carimbo(arq, texto, sessao, presidente)

        if hasattr(storage_path, nom_pdf_redacao):
            arq = getattr(storage_path, nom_pdf_redacao)
            aplicar_carimbo(arq, texto, sessao, presidente)

    logger.info(f"Tarefa de carimbo concluída para matéria {cod_materia}.")
    return nom_pdf_saida
