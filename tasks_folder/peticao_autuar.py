from .utils import zope_task, make_qrcode, get_signatures  # parse_signatures removido (não usado)
from io import BytesIO
import os
import fitz as pymupdf
import pikepdf
from DateTime import DateTime
import logging
import urllib.request
import urllib.parse
import urllib.error
import json
import base64


def reparar_pdf_stream(file_stream: BytesIO) -> BytesIO:
    """Tenta reparar o PDF com pikepdf; se falhar, rasteriza com PyMuPDF.
    Retorna um BytesIO posicionado no início.
    """
    file_stream.seek(0)
    original_data = file_stream.read()

    # 1) Tentativa com pikepdf (conserta XREF / recursos órfãos; lineariza)
    try:
        buffer = BytesIO()
        with pikepdf.open(BytesIO(original_data)) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(buffer, linearize=True)
        repaired_data = buffer.getvalue()

        # Validação abrindo com PyMuPDF
        doc = pymupdf.open(stream=repaired_data, filetype="pdf")
        doc.close()

        logging.info("PDF successfully repaired using pikepdf.")
        out = BytesIO(repaired_data)
        out.seek(0)
        return out
    except Exception as e:
        logging.warning(f"PDF repair with pikepdf failed: {e!r}. Trying rasterization.")

    # 2) Fallback: rasterização página-a-página com escala DPI consistente
    try:
        src = pymupdf.open(stream=original_data, filetype="pdf")
        dst = pymupdf.open()
        try:
            dpi = 200  # ajuste fino conforme necessidade
            zoom = dpi / 72.0
            mat = pymupdf.Matrix(zoom, zoom)

            for page in src:
                # Mantém retângulo original (em pontos)
                rect_pts = page.rect
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("png")

                # Nova página com MESMAS dimensões (em pontos) do PDF original
                new_page = dst.new_page(width=rect_pts.width, height=rect_pts.height)
                new_page.insert_image(rect_pts, stream=img_bytes)

            out = BytesIO()
            # garbage/deflate ajudam a reduzir tamanho do PDF rasterizado
            dst.save(out, garbage=4, deflate=True)
            out.seek(0)
            logging.info("PDF repaired via rasterization.")
            return out
        finally:
            try:
                dst.close()
            except Exception:
                pass
            try:
                src.close()
            except Exception:
                pass
    except Exception as e:
        logging.error(f"Rasterization failed: {e!r}. Using original file.")
        out = BytesIO(original_data)
        out.seek(0)
        return out


@zope_task(bind=True, max_retries=5, default_retry_delay=5)
def peticao_autuar_task(self, site, cod_peticao, portal_url):
    """
    Tarefa Celery para autuar petição.
    
    Segue padrão de tramitacao_pdf_task: faz chamadas HTTP para views que têm
    contexto Zope correto, evitando problemas com RequestContainer.
    
    Args:
        self: Instância da task (injetado pelo decorator)
        site: Objeto site do Zope (injetado pelo decorator @zope_task, mas não usado diretamente)
        cod_peticao: Código da petição
        portal_url: URL base do portal
    
    Returns:
        Nome do arquivo PDF gerado
    """
    if getattr(self.request, "retries", 0) > 0:
        logging.info(f"[peticao_autuar_task] Retry #{self.request.retries} | cod_peticao={cod_peticao}")

    logging.info(f"[peticao_autuar_task] Iniciando task para petição {cod_peticao}")

    try:
        # ======================
        # 1) Obter dados da petição via chamada HTTP (view tem contexto Zope correto)
        # ======================
        base_url = portal_url.rstrip('/')
        if '/sagl/' not in base_url:
            executor_url = f"{base_url}/sagl/@@peticao_autuar_executor"
        else:
            executor_url = f"{base_url}/@@peticao_autuar_executor"
        
        # Prepara dados para POST
        data = {
            'cod_peticao': str(cod_peticao),
        }
        post_data = urllib.parse.urlencode(data).encode('utf-8')
        
        logging.info(f"[peticao_autuar_task] Obtendo dados da petição via HTTP: {executor_url}")
        
        # Faz chamada HTTP POST para obter dados preparados
        req = urllib.request.Request(
            executor_url,
            data=post_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        with urllib.request.urlopen(req, timeout=300) as response:
            response_data = response.read().decode('utf-8')
            
            if not response_data or not response_data.strip():
                raise Exception("Resposta vazia do servidor executor")
            
            try:
                result = json.loads(response_data)
            except json.JSONDecodeError as e:
                logging.error(f"[peticao_autuar_task] Resposta não é JSON válido. Primeiros 500 chars: {response_data[:500]}")
                raise
            
            if not result.get('success'):
                error_msg = result.get('error', 'Erro desconhecido')
                raise Exception(f"Erro ao obter dados: {error_msg}")
            
            # Extrai dados preparados
            dados = result.get('dados', {})
            
            # Dados necessários para processamento
            pdf_base64 = dados.get('pdf_base64')
            if not pdf_base64:
                raise ValueError("PDF não encontrado nos dados retornados")
            
            arq_data = base64.b64decode(pdf_base64)
            cod_validacao_doc = dados.get('cod_validacao_doc', '')
            nom_autor = dados.get('nom_autor')
            outros = dados.get('outros', '')
            texto = dados.get('texto', '')
            info_protocolo = dados.get('info_protocolo', '')
            caminho = dados.get('caminho', '')
            nom_pdf_saida = dados.get('nom_pdf_saida', '')
            ind_doc_adm = dados.get('ind_doc_adm', '')
            ind_norma = dados.get('ind_norma', '')
            cod_norma = dados.get('cod_norma')
            
            if not nom_pdf_saida:
                raise ValueError("Nome do arquivo de saída não encontrado nos dados retornados")


        # ======================
        # 2) Processar PDF: reparar, adicionar carimbo e QR code
        # ======================
        # Repara o stream
        pdf_stream = reparar_pdf_stream(BytesIO(arq_data))
        
        try:
            pdf_stream.seek(0)
            existing_pdf = pymupdf.open(stream=pdf_stream.read(), filetype="pdf")
        except Exception as e:
            logging.critical(f"Erro ao abrir PDF com PyMuPDF após reparo: {e!r}")
            raise

        try:
            if cod_validacao_doc:
                stream_qr = make_qrcode(
                    f"{portal_url}/conferir_assinatura_proc?txt_codigo_verificacao={cod_validacao_doc}"
                )
                mensagem1 = f"Esta é uma cópia do original assinado digitalmente por {nom_autor or 'Desconhecido'}{outros}"
                mensagem2 = (
                    f"Para validar visite {portal_url}/conferir_assinatura e informe o código {cod_validacao_doc}."
                )
                install_home = os.environ.get('INSTALL_HOME')
                if not install_home:
                    raise EnvironmentError("Variável INSTALL_HOME não definida.")
                logo_path = os.path.join(
                    install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png'
                )
                if not os.path.isfile(logo_path):
                    raise FileNotFoundError(f"Logo ICP não encontrado: {logo_path}")
                with open(logo_path, "rb") as arq:
                    image = arq.read()
            else:
                stream_qr = make_qrcode(f"{portal_url}{caminho}{nom_pdf_saida}")
                mensagem1 = f"Documento assinado digitalmente com usuário e senha por {nom_autor or 'Desconhecido'}"
                mensagem2 = "Para verificar a autenticidade do documento leia o QR code."
                image = None

            total_paginas = existing_pdf.page_count
            for i, page in enumerate(existing_pdf):
                w, h = page.rect.width, page.rect.height
                is_landscape = (w > h)
                texto_rodape = (
                    f"Pág. {i+1}/{total_paginas} - {texto} {info_protocolo} {mensagem1}"
                )

                # --- Constantes de layout (em pontos) ---
                BOTTOM_MARGIN       = 5    # margem inferior comum
                QR_LEFT             = 10   # afastamento da margem esquerda
                QR_SIZE             = 50   # lado do QR

                LOGO_RIGHT_MARGIN   = 8    # afastamento da margem direita
                LOGO_WIDTH          = 45   # largura do logo
                LOGO_HEIGHT         = 35   # altura do logo

                # Offset visual para compensar padding/transparência do PNG (OPÇÃO B)
                LOGO_VISUAL_OFFSET  = 6    # ajuste fino (px/pontos)

                # --- Retângulos ---
                qr_rect = pymupdf.Rect(
                    QR_LEFT,
                    h - QR_SIZE - BOTTOM_MARGIN,
                    QR_LEFT + QR_SIZE,
                    h - BOTTOM_MARGIN
                )

                # Aplica o offset ao logo para "descer" o conteúdo visível
                logo_rect = pymupdf.Rect(
                    w - LOGO_WIDTH - LOGO_RIGHT_MARGIN,
                    h - LOGO_HEIGHT - BOTTOM_MARGIN + LOGO_VISUAL_OFFSET,
                    w - LOGO_RIGHT_MARGIN,
                    h - BOTTOM_MARGIN + LOGO_VISUAL_OFFSET
                )

                # Inserções
                page.insert_image(qr_rect, stream=stream_qr)
                if image:
                    page.insert_image(logo_rect, stream=image)

                if is_landscape:
                    # Rodapé em caixa, sem rotação
                    page.insert_textbox(
                        pymupdf.Rect(65, h - 22, w - 65, h - 5),
                        texto_rodape, fontsize=8, fontname="helv", align=pymupdf.TEXT_ALIGN_LEFT
                    )
                    shape = page.new_shape()
                    shape.insert_text(
                        pymupdf.Point(w - 16, h - 44), mensagem2, fontname="helv", fontsize=8, rotate=90
                    )
                    shape.commit()
                else:
                    # Rodapé rotacionado à direita + mensagem2 na base esquerda
                    page.insert_text(
                        (w - 13, h - 30), texto_rodape, fontsize=8, rotate=90, fontname="helv"
                    )
                    shape = page.new_shape()
                    shape.insert_text(
                        pymupdf.Point(60, h - 12), mensagem2, fontname="helv", fontsize=8
                    )
                    shape.commit()

            # Cabeçalho (somente Doc Administrativo): mede pela página 0
            if ind_doc_adm == "1" and total_paginas > 0:
                p0 = existing_pdf[0]
                w0, h0 = p0.rect.width, p0.rect.height
                rect = pymupdf.Rect(40, 120, max(40, w0 - 20), 170)
                p0.insert_textbox(
                    rect, texto.upper(), fontname="helv", fontsize=12, align=pymupdf.TEXT_ALIGN_CENTER
                )

            existing_pdf.set_metadata({"title": texto or "", "author": nom_autor or ""})
            content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        finally:
            try:
                existing_pdf.close()
            except Exception:
                pass

        # ======================
        # 3) Salvar PDF via chamada HTTP (view tem contexto Zope correto)
        # ======================
        pdf_base64_saida = base64.b64encode(content).decode('utf-8')
        
        salvar_url = portal_url.rstrip('/')
        if '/sagl/' not in salvar_url:
            salvar_url = f"{salvar_url}/sagl/@@peticao_autuar_salvar"
        else:
            salvar_url = f"{salvar_url}/@@peticao_autuar_salvar"
        
        save_data = urllib.parse.urlencode({
            'cod_peticao': str(cod_peticao),
            'pdf_base64': pdf_base64_saida,
            'nom_pdf_saida': nom_pdf_saida,
            'texto': texto,
            'ind_norma': str(ind_norma),
            'cod_norma': str(cod_norma) if cod_norma else '',
        }).encode('utf-8')
        
        save_req = urllib.request.Request(
            salvar_url,
            data=save_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        with urllib.request.urlopen(save_req, timeout=60) as save_response:
            save_result = save_response.read().decode('utf-8')
            try:
                save_result_json = json.loads(save_result)
                if not save_result_json.get('success'):
                    error_msg = save_result_json.get('error', 'Erro desconhecido')
                    raise Exception(f"Erro ao salvar PDF: {error_msg}")
            except json.JSONDecodeError:
                # Se não for JSON, assume sucesso se não houver erro HTTP
                pass
            logging.info(f"[peticao_autuar_task] PDF salvo no repositório via view HTTP (cod_peticao={cod_peticao})")

        return nom_pdf_saida

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
        logging.error(f"[peticao_autuar_task] Erro HTTP {e.code}: {error_body}")
        raise Exception(f"Erro HTTP {e.code} ao processar petição: {error_body}")
    except urllib.error.URLError as e:
        logging.error(f"[peticao_autuar_task] Erro de URL: {e}")
        raise Exception(f"Erro de conexão ao processar petição: {str(e)}")
    except json.JSONDecodeError as e:
        logging.error(f"[peticao_autuar_task] Erro ao decodificar JSON: {e}")
        raise Exception(f"Resposta inválida do servidor: {str(e)}")
    except Exception as e:
        logging.error(
            f"[peticao_autuar_task] Erro na tentativa {getattr(self.request, 'retries', 0) + 1} "
            f"para cod_peticao={cod_peticao}: {e}",
            exc_info=True
        )
        # Reagenda (respeita max_retries)
        raise self.retry(exc=e)
