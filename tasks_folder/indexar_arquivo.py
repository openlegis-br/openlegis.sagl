from .utils import celery
import base64
from io import BytesIO
import pymupdf
from multiprocessing.dummy import Pool

app = celery

def processar_pagina(pagina):
    """Função auxiliar para processar uma página."""
    palavras_pagina = set()
    texto_palavras = pagina.get_text("words")
    if texto_palavras:
        for palavra_info in texto_palavras:
            if len(palavra_info) > 4:
                palavra = palavra_info[4].lower()
                if isinstance(palavra, str) and len(palavra) > 3:
                    palavras_pagina.add(palavra)
    return palavras_pagina

@app.task
def indexar_arquivo_task(pdfbase64):
    try:
        pdf_bytes = base64.b64decode(pdfbase64)
        with BytesIO(pdf_bytes) as arquivo_binario:
            with pymupdf.open(stream=arquivo_binario) as documento_pdf:
                with Pool() as pool: # Pool de threads
                    resultados = pool.map(processar_pagina, documento_pdf)
                palavras_indexadas = set()
                for resultado in resultados:
                    palavras_indexadas.update(resultado)
                palavras_unicas = sorted(list(palavras_indexadas))
                return palavras_unicas
    except Exception as e:
        print(f"Erro ao processar o arquivo PDF: {e}")
        return []
