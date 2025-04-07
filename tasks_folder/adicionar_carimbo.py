from .utils import zope_task
from io import BytesIO
import pymupdf
from datetime import datetime
from DateTime import DateTime
import logging
from multiprocessing.dummy import Pool

@zope_task()
def adicionar_carimbo_task(portal, cod_sessao_plen, nom_resultado, cod_materia):
    skins = portal.portal_skins.sk_sagl
    id_sessao = ''
    data = datetime.now().strftime('%d/%m/%Y')
    data1 = datetime.now().strftime('%Y/%m/%d')
    nom_presidente = ''
    id_sessao = ''
    data = DateTime().strftime('%d/%m/%Y')
    data1 = DateTime().strftime('%Y/%m/%d')
    nom_presidente = ''
    # obtem dados da sessao
    if cod_sessao_plen != '0' and cod_sessao_plen != '':
       for item in skins.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
           for tipo in skins.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao):
               id_sessao = str(item.num_sessao_plen) + 'ª ' + str(portal.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + tipo.nom_sessao
           data = item.dat_inicio_sessao
           data1 = item.dat_inicio
           num_legislatura = item.num_legislatura
       for composicao in skins.zsql.composicao_mesa_sessao_obter_zsql(cod_sessao_plen=cod_sessao_plen, cod_cargo=1, ind_excluido=0):
           for parlamentar in skins.zsql.parlamentar_obter_zsql(cod_parlamentar=composicao.cod_parlamentar):
               nom_presidente = str(parlamentar.nom_parlamentar.upper())
    if nom_presidente == '':
       for sleg in skins.zsql.periodo_comp_mesa_obter_zsql(data=data1):
           for cod_presidente in skins.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp, cod_cargo=1):
               for presidencia in skins.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_presidente.cod_parlamentar):
                   nom_presidente = str(presidencia.nom_parlamentar.upper())
    # dados carimbo
    texto = "%s" % (str(nom_resultado.upper()))
    sessao = "%s - %s" % (id_sessao, data)
    cargo = "Presidente"
    presidente = "%s: %s " % (cargo, nom_presidente)
    # adiciona carimbo aos documentos
    for materia in skins.zsql.materia_obter_zsql(cod_materia=cod_materia):
        storage_path = portal.sapl_documentos.materia
        nom_pdf_saida = str(materia.cod_materia) + "_texto_integral.pdf"
        nom_pdf_redacao = str(materia.cod_materia) + "_redacao_final.pdf"
    if hasattr(storage_path, nom_pdf_saida):
       arq = getattr(storage_path, nom_pdf_saida)
       arquivo = BytesIO(bytes(arq.data))
       existing_pdf = pymupdf.open(stream=arquivo)
       existing_pdf.bake()
       numPages = existing_pdf.page_count
       w = existing_pdf[0].rect.width
       h = existing_pdf[0].rect.height
       margin = 10
       black = pymupdf.pdfcolor["black"]
       text2 = texto + '\n' + sessao + '\n' + presidente
       p2 = pymupdf.Point(w - 170 - margin, margin + 90) # margem superior
       shape = existing_pdf[0].new_shape()
       shape.draw_circle(p2,1)
       shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
       shape.commit()
       content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
       arq.update_data(content)
       #arq.manage_upload(file=content)
    if hasattr(storage_path, nom_pdf_redacao):
       arq = getattr(storage_path, nom_pdf_redacao)
       arquivo = BytesIO(bytes(arq.data))
       existing_pdf = pymupdf.open(stream=arquivo)
       existing_pdf.bake()
       numPages = existing_pdf.page_count
       w = existing_pdf[0].rect.width
       h = existing_pdf[0].rect.height
       margin = 10
       black = pymupdf.pdfcolor["black"]
       text2 = texto + '\n' + sessao + '\n' + presidente
       p2 = pymupdf.Point(w - 170 - margin, margin + 90) # margem superior
       shape = existing_pdf[0].new_shape()
       shape.draw_circle(p2,1)
       shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
       shape.commit()
       content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
       arq.update_data(content)
       #arq.manage_upload(file=content)
    return nom_pdf_saida
