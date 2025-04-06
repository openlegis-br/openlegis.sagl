from .utils import zope_task, make_qrcode
from io import BytesIO
import pymupdf
import logging
import traceback
from multiprocessing.dummy import Pool

# Configuration
TAMANHO_QRCODE = 50
MARGEM = 5
TAMANHO_FONTE = 8
ROTACAO_TEXTO = 90
FONTE_NUMERO_PAGINA = "helv"
MODELO_MENSAGEM_ASSINATURA = "Documento assinado digitalmente com usuário e senha por {}."
MENSAGEM_QRCODE = "Para verificar a autenticidade do documento, leia o qrcode."
MODELO_PROPOSICAO_ELETRONICA = "Proposição eletrônica {}"

def _adicionar_assinatura_e_qrcode_na_pagina(
    pagina: pymupdf.Page,
    checksum: str,
    nome_autor: str,
    fluxo_qrcode: BytesIO,
    indice_pagina: int,
    total_paginas: int,
):
    """
    Adiciona informações de assinatura simples e um código QR a uma única página PDF.
    """
    largura = pagina.rect.width
    altura = pagina.rect.height
    esquerda = 10 - MARGEM
    inferior = altura - 50 - MARGEM
    numero_pagina = f"Pág. {indice_pagina + 1}/{total_paginas}"
    mensagem_assinatura = MODELO_MENSAGEM_ASSINATURA.format(nome_autor)
    texto_proposicao = MODELO_PROPOSICAO_ELETRONICA.format(checksum)

    retangulo = pymupdf.Rect(esquerda, inferior, esquerda + TAMANHO_QRCODE, inferior + TAMANHO_QRCODE)
    pagina.insert_image(retangulo, stream=fluxo_qrcode)

    texto3 = texto_proposicao + ' - ' + mensagem_assinatura
    x = largura - 8 - MARGEM
    y = altura - 30 - MARGEM
    pagina.insert_text((x, y), texto3, fontsize=TAMANHO_FONTE, rotate=ROTACAO_TEXTO)

    p1 = pymupdf.Point(largura - 40 - MARGEM, altura - 12)
    p2 = pymupdf.Point(60, altura - 12)
    forma = pagina.new_shape()
    forma.draw_circle(p1, 1)
    forma.draw_circle(p2, 1)
    forma.insert_text(p1, numero_pagina, fontname=FONTE_NUMERO_PAGINA, fontsize=TAMANHO_FONTE)
    forma.insert_text(p2, MENSAGEM_QRCODE, fontname=FONTE_NUMERO_PAGINA, fontsize=TAMANHO_FONTE, rotate=0)
    forma.commit()

def _salvar_pdf_modificado(caminho_armazenamento, pdf_assinado, conteudo, item):
    """
    Salva o conteúdo PDF modificado no caminho de armazenamento especificado.
    """
    try:
        if hasattr(caminho_armazenamento, pdf_assinado):
            pdf = getattr(caminho_armazenamento, pdf_assinado)
            pdf.manage_upload(file=conteudo)
        else:
            caminho_armazenamento.manage_addFile(
                id=pdf_assinado, file=conteudo, title="Proposição " + str(item)
            )
            pdf = getattr(caminho_armazenamento, pdf_assinado)
        pdf.manage_permission("View", roles=["Manager", "Anonymous"], acquire=1)
    except Exception as e:
        logging.error(f"Erro ao salvar PDF {pdf_assinado}: {e}")
        raise

def processar_proposicao(portal, portal_url, item):
    """Função auxiliar para processar uma única proposição (usando threads)."""
    caminho_armazenamento = portal.sapl_documentos.proposicao
    try:
        for proposicao in portal.portal_skins.sk_sagl.zsql.proposicao_obter_zsql(cod_proposicao=int(item)):
            try:
                string = portal.pysc.proposicao_calcular_checksum_pysc(
                    proposicao.cod_proposicao, senha=1
                )
                nome_autor = proposicao.nom_autor
                pdf_proposicao = str(proposicao.cod_proposicao) + ".pdf"
                pdf_assinado = str(proposicao.cod_proposicao) + "_signed.pdf"

                arq = getattr(caminho_armazenamento, pdf_proposicao)
                arquivo = BytesIO(bytes(arq.data))
                pdf_existente = pymupdf.open(stream=arquivo)
                numPaginas = pdf_existente.page_count
                stream = make_qrcode(
                    text=portal_url
                    + "/sapl_documentos/proposicao/"
                    + proposicao.cod_proposicao
                    + "_signed.pdf"
                )

                for indice_pagina, pagina in enumerate(pdf_existente):
                    _adicionar_assinatura_e_qrcode_na_pagina(
                        pagina=pagina,
                        checksum=string,
                        nome_autor=nome_autor,
                        fluxo_qrcode=stream,
                        indice_pagina=indice_pagina,
                        total_paginas=numPaginas,
                    )

                conteudo = pdf_existente.tobytes(
                    deflate=True, garbage=3, use_objstms=1
                )
                _salvar_pdf_modificado(caminho_armazenamento, pdf_assinado, conteudo, item)

            except Exception as e:
                logging.error(
                    f"Erro ao processar proposição {item}: {e}\n{traceback.format_exc()}"
                )
    except Exception as e:
        logging.error(f"Erro no loop principal para o item {item}: {e}\n{traceback.format_exc()}")

@zope_task()
def assinar_proposicao_task(portal, lista, portal_url):
    """Assina documentos de proposição de forma paralela com multiprocessing.dummy (threads)."""
    logging.basicConfig(level=logging.INFO)
    pool = Pool()  # Cria um pool de threads
    tasks = [(portal, portal_url, item) for item in lista]
    pool.starmap(processar_proposicao, tasks)
    pool.close()
    pool.join()
