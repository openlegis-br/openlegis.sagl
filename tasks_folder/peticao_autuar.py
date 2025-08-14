from .utils import zope_task, make_qrcode, get_signatures  # parse_signatures removido (não usado)
from io import BytesIO
import os
import fitz as pymupdf
import pikepdf
from DateTime import DateTime
import logging


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
def peticao_autuar_task(self, portal, cod_peticao, portal_url):
    if getattr(self.request, "retries", 0) > 0:
        logging.info(f"[peticao_autuar_task] Retry #{self.request.retries} | cod_peticao={cod_peticao}")

    logging.info(f"[peticao_autuar_task] Iniciando task para petição {cod_peticao}")
    skins = portal.portal_skins.sk_sagl

    try:
        # ======================
        # 1) Obter PDF-fonte + autor / assinatura
        # ======================
        arq_data = None
        cod_validacao_doc = ''
        nom_autor = None
        outros = ''

        for peticao in skins.zsql.peticao_obter_zsql(cod_peticao=cod_peticao):
            # Tenta pegar PDF assinado (documentos_assinados)
            for validacao in skins.zsql.assinatura_documento_obter_zsql(
                tipo_doc='peticao',
                codigo=peticao.cod_peticao,
                ind_assinado=1
            ):
                nom_pdf_peticao = f"{validacao.cod_assinatura_doc}.pdf"
                cod_validacao_doc = str(
                    skins.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc)
                )

                if nom_pdf_peticao in portal.sapl_documentos.documentos_assinados.objectIds():
                    arq_data = portal.sapl_documentos.documentos_assinados[nom_pdf_peticao].data
                else:
                    raise FileNotFoundError(
                        f"Arquivo assinado {nom_pdf_peticao} não encontrado em documentos_assinados."
                    )

                # Repara o stream uma única vez e reaproveita
                pdf_stream = reparar_pdf_stream(BytesIO(bytes(arq_data)))

                # Tenta ler assinaturas
                signers = []
                try:
                    pdf_stream.seek(0)
                    signers = (get_signatures(pdf_stream) or [])
                except Exception as e:
                    logging.warning(f"Falha ao extrair assinaturas com get_signatures: {e!r}")

                if signers:
                    nom_autor = signers[0].get('signer_name')
                    qtde_assinaturas = len(signers)
                    if qtde_assinaturas == 2:
                        outros = " e outro"
                    elif qtde_assinaturas > 2:
                        outros = " e outros"
                # Já achou PDF assinado; sai do loop de validações
                break
            else:
                # Não havia assinatura “documentos_assinados”: usa PDF em /peticao
                nom_pdf_peticao = f"{cod_peticao}.pdf"
                if nom_pdf_peticao in portal.sapl_documentos.peticao.objectIds():
                    arq_data = portal.sapl_documentos.peticao[nom_pdf_peticao].data
                else:
                    raise FileNotFoundError(f"Arquivo da petição {nom_pdf_peticao} não encontrado.")

                for usuario in skins.zsql.usuario_obter_zsql(cod_usuario=peticao.cod_usuario):
                    nom_autor = usuario.nom_completo

                pdf_stream = reparar_pdf_stream(BytesIO(bytes(arq_data)))

            if not arq_data:
                raise ValueError("Arquivo da petição está vazio.")

        # ======================
        # 2) Contexto de destino (texto/caminho/arquivo de saída)
        # ======================
        info_protocolo = f"- Recebido em {peticao.dat_recebimento}."
        texto = ''
        storage_path = None
        caminho = ''
        nom_pdf_saida = ''

        if peticao.ind_doc_adm == "1":
            for documento in skins.zsql.documento_administrativo_obter_zsql(cod_documento=peticao.cod_documento):
                for protocolo in skins.zsql.protocolo_obter_zsql(
                    num_protocolo=documento.num_protocolo, ano_protocolo=documento.ano_documento
                ):
                    info_protocolo = (
                        f" - Prot. nº {protocolo.num_protocolo}/{protocolo.ano_protocolo} "
                        f"{DateTime(protocolo.dat_protocolo).strftime('%d/%m/%Y')} {protocolo.hor_protocolo}."
                    )
                texto = f"{documento.des_tipo_documento} nº {documento.num_documento}/{documento.ano_documento}"
                storage_path = portal.sapl_documentos.administrativo
                nom_pdf_saida = f"{documento.cod_documento}_texto_integral.pdf"
                caminho = '/sapl_documentos/administrativo/'

        elif peticao.ind_doc_materia == "1":
            id_materia = ""
            for documento in skins.zsql.documento_acessorio_obter_zsql(cod_documento=peticao.cod_doc_acessorio):
                for materia in skins.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                    id_materia = f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica}"
                texto = f"{documento.des_tipo_documento} - {id_materia}".strip(" -")
                storage_path = portal.sapl_documentos.materia
                nom_pdf_saida = f"{documento.cod_documento}.pdf"
                caminho = '/sapl_documentos/materia/'

        elif peticao.ind_norma == "1":
            for norma in skins.zsql.norma_juridica_obter_zsql(cod_norma=peticao.cod_norma):
                texto = f"{norma.des_tipo_norma} nº {norma.num_norma}/{norma.ano_norma}"
                storage_path = portal.sapl_documentos.norma_juridica
                nom_pdf_saida = f"{norma.cod_norma}_texto_integral.pdf"
                caminho = '/sapl_documentos/norma_juridica/'

        if not storage_path or not nom_pdf_saida:
            raise ValueError(
                "Não foi possível determinar o destino do arquivo (storage_path/nom_pdf_saida). "
                "Verifique os indicadores ind_doc_adm / ind_doc_materia / ind_norma."
            )

        # ======================
        # 3) Carimbo de rodapé + QR (com offset visual no logo)
        # ======================
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
            if peticao.ind_doc_adm == "1" and total_paginas > 0:
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
        # 4) Persistência no Zope (e catalogação específica)
        # ======================
        if nom_pdf_saida in storage_path.objectIds():
            arquivo_peticao = storage_path[nom_pdf_saida]
            arquivo_peticao.update_data(content)
        else:
            storage_path.manage_addFile(id=nom_pdf_saida, file=content, title=texto)
            arquivo_peticao = storage_path[nom_pdf_saida]

        # Permissões
        arquivo_peticao.manage_permission('View', roles=['Manager', 'Authenticated'], acquire=0)
        if peticao.ind_norma == "1":
            arquivo_peticao.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
            portal.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(cod_norma=peticao.cod_norma)

        return nom_pdf_saida

    except Exception as e:
        logging.error(
            f"[peticao_autuar_task] Erro na tentativa {getattr(self.request, 'retries', 0) + 1} "
            f"para cod_peticao={cod_peticao}: {e}",
            exc_info=True
        )
        # Reagenda (respeita max_retries)
        raise self.retry(exc=e)
