from .utils import zope_task, make_qrcode
from io import BytesIO
import pymupdf
import logging
import traceback

# Configurações
TAMANHO_QRCODE = 50
MARGEM = 5
TAMANHO_FONTE = 8
ROTACAO_TEXTO = 90
FONTE_NUMERO_PAGINA = "helv"
MODELO_MENSAGEM_ASSINATURA = "Documento assinado digitalmente com usuário e senha por {}."
MENSAGEM_QRCODE = "Para verificar a autenticidade do documento, leia o qrcode."
MODELO_PROPOSICAO_ELETRONICA = "Proposição eletrônica {}"

def _adicionar_assinatura_e_qrcode_na_pagina(pagina, checksum, nome_autor, fluxo_qrcode, indice_pagina, total_paginas):
    largura = pagina.rect.width
    altura = pagina.rect.height
    esquerda = 10 - MARGEM
    inferior = altura - 50 - MARGEM
    numero_pagina = f"Pág. {indice_pagina + 1}/{total_paginas}"
    mensagem_assinatura = MODELO_MENSAGEM_ASSINATURA.format(nome_autor)
    texto_proposicao = MODELO_PROPOSICAO_ELETRONICA.format(checksum)

    retangulo = pymupdf.Rect(esquerda, inferior, esquerda + TAMANHO_QRCODE, inferior + TAMANHO_QRCODE)
    pagina.insert_image(retangulo, stream=fluxo_qrcode)

    texto_final = texto_proposicao + ' - ' + mensagem_assinatura
    x = largura - 8 - MARGEM
    y = altura - 30 - MARGEM
    pagina.insert_text((x, y), texto_final, fontsize=TAMANHO_FONTE, rotate=ROTACAO_TEXTO)

    p1 = pymupdf.Point(largura - 40 - MARGEM, altura - 12)
    p2 = pymupdf.Point(60, altura - 12)
    forma = pagina.new_shape()
    forma.draw_circle(p1, 1)
    forma.draw_circle(p2, 1)
    forma.insert_text(p1, numero_pagina, fontname=FONTE_NUMERO_PAGINA, fontsize=TAMANHO_FONTE)
    forma.insert_text(p2, MENSAGEM_QRCODE, fontname=FONTE_NUMERO_PAGINA, fontsize=TAMANHO_FONTE, rotate=0)
    forma.commit()

def _salvar_pdf_modificado(caminho_armazenamento, nome_arquivo, conteudo, item):
    try:
        if hasattr(caminho_armazenamento, nome_arquivo):
            pdf = getattr(caminho_armazenamento, nome_arquivo)
            pdf.update_data(conteudo)
        else:
            caminho_armazenamento.manage_addFile(id=nome_arquivo, file=conteudo, title="Proposição " + str(item))
            pdf = getattr(caminho_armazenamento, nome_arquivo)
        pdf.manage_permission("View", roles=["Manager", "Anonymous"], acquire=1)
    except Exception as e:
        logging.error(f"Erro ao salvar PDF {nome_arquivo}: {e}")
        raise

def processar_proposicao(portal, portal_url, item):
    caminho_armazenamento = portal.sapl_documentos.proposicao
    try:
        sk_sagl = portal.portal_skins.sk_sagl
        proposicao_obter = sk_sagl.proposicao_obter_zsql
        checksum_func = sk_sagl.pysc.proposicao_calcular_checksum_pysc

        for proposicao in proposicao_obter(cod_proposicao=int(item)):
            try:
                string = checksum_func(proposicao.cod_proposicao, senha=1)
                nome_autor = proposicao.nom_autor
                pdf_proposicao = f"{proposicao.cod_proposicao}.pdf"
                pdf_assinado = f"{proposicao.cod_proposicao}_signed.pdf"

                arq = getattr(caminho_armazenamento, pdf_proposicao)
                arquivo = BytesIO(bytes(arq.data))
                pdf_existente = pymupdf.open(stream=arquivo)
                total_paginas = pdf_existente.page_count

                stream = make_qrcode(
                    text=f"{portal_url}/sapl_documentos/proposicao/{proposicao.cod_proposicao}_signed.pdf"
                )

                for indice_pagina, pagina in enumerate(pdf_existente):
                    _adicionar_assinatura_e_qrcode_na_pagina(
                        pagina=pagina,
                        checksum=string,
                        nome_autor=nome_autor,
                        fluxo_qrcode=stream,
                        indice_pagina=indice_pagina,
                        total_paginas=total_paginas,
                    )

                conteudo = pdf_existente.tobytes(deflate=True, garbage=3, use_objstms=1)
                _salvar_pdf_modificado(caminho_armazenamento, pdf_assinado, conteudo, item)

            except Exception as e:
                logging.error(f"Erro ao processar proposição {item}: {e}\n{traceback.format_exc()}")

    except Exception as e:
        logging.error(f"Erro no loop principal para o item {item}: {e}\n{traceback.format_exc()}")

@zope_task()
def assinar_proposicao_task(portal, lista, portal_url):
    logging.basicConfig(level=logging.INFO)
    for item in lista:
        processar_proposicao(portal, portal_url, item)
