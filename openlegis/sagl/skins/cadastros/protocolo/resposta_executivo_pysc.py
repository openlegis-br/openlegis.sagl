## Script (Python) "resposta_executivo_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_materia_respondida
##title=
##
import json
from DateTime import DateTime

REQUEST = context.REQUEST
RESPONSE = REQUEST.RESPONSE
session = REQUEST.SESSION

usuario = REQUEST['AUTHENTICATED_USER'].getUserName()


def retornar_erro(msg):
    """Monta e retorna um JSON de erro padronizado."""
    payload = [{
        'status': 'ERRO',
        'mensagem': msg,
        'usuario': usuario,
        'ip_origem': context.pysc.get_ip(),
        'data': DateTime(datefmt="international").strftime("%d/%m/%Y %H:%M:%S"),
    }]
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return json.dumps(payload)


def obter_materia(cod_materia):
    """
    Monta a identificação da matéria para usar como ementa do documento.
    Retorna string com ementa ou None se a matéria não existir.
    """
    for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia):
        autoria = ''
        # primeira autoria válida (se houver)
        for autor in context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia, ind_excluido=0):
            autoria = getattr(autor, 'nom_autor_join', '') or ''
            break

        sgl = getattr(materia, 'sgl_tipo_materia', '') or ''
        num = getattr(materia, 'num_ident_basica', '') or ''
        ano = getattr(materia, 'ano_ident_basica', '') or ''
        partes = ['Resposta -', sgl, f"{num}/{ano}"]
        if autoria:
            partes.append('- ' + autoria)
        return ' '.join([p for p in partes if p])

    # não encontrou nenhuma matéria
    return None


def numero_protocolo():
    """Obtém o número/código de protocolo conforme configuração (anual ou sequencial)."""
    if context.sapl_documentos.props_sagl.numero_protocolo_anual == 1:
        for numero in context.zsql.protocolo_numero_obter_zsql(
            ano_protocolo=DateTime(datefmt='international').strftime('%Y')
        ):
            return int(numero.novo_numero)
    else:
        for numero in context.zsql.protocolo_codigo_obter_zsql():
            return int(numero.novo_codigo)
    # fallback (não deveria ocorrer)
    return 1


def criar_protocolo(cod_materia, txt_ementa):
    """Cria o protocolo legislativo e delega para criação do documento acessório."""
    login_usuario = ''
    cod_usuario = None
    for u in context.zsql.usuario_obter_zsql(col_username=REQUEST['AUTHENTICATED_USER'].getUserName()):
        if getattr(u, 'cod_usuario', None):
            login_usuario = getattr(u, 'col_username', '') or REQUEST['AUTHENTICATED_USER'].getUserName()
            cod_usuario = u.cod_usuario
            break

    cod_autor = None
    nome_autor = ''
    for item in context.zsql.autor_obter_zsql(col_username=REQUEST['AUTHENTICATED_USER'].getUserName()):
        cod_autor = getattr(item, 'cod_autor', None)
        nome_autor = getattr(item, 'nom_autor_join', '') or ''
        break

    # Define o tipo de documento: tenta "Ofício / Resposta", senão fallback 9
    tip_doc = 9
    for tipo_doc in context.zsql.tipo_documento_obter_zsql(ind_excluido=0):
        if getattr(tipo_doc, 'des_tipo_documento', '') == 'Resposta':
            tip_doc = int(tipo_doc.tip_documento)
            break

    num_prot_int = numero_protocolo()

    context.zsql.protocolo_legislativo_incluir_zsql(
        num_protocolo=num_prot_int,
        tip_protocolo=0,
        tip_processo=1,
        tip_natureza_materia=3,
        tip_materia=tip_doc,
        cod_materia_principal=cod_materia,
        txt_assunto_ementa=txt_ementa,
        cod_autor=cod_autor,
        txt_user_protocolo=login_usuario,
        txt_observacao=context.pysc.get_ip()
    )

    # pega o último protocolo incluído
    cod_protocolo = None
    for codigo in context.zsql.protocolo_incluido_codigo_obter_zsql():
        cod_protocolo = int(codigo.cod_protocolo)
        break

    # monta num_protocolo "N/AAAA"
    num_protocolo = ''
    if cod_protocolo is not None:
        for protocolo in context.zsql.protocolo_obter_zsql(cod_protocolo=cod_protocolo):
            num_protocolo = f"{protocolo.num_protocolo}/{protocolo.ano_protocolo}"
            break

    return criar_documento(
        tip_doc=tip_doc,
        txt_ementa=txt_ementa,
        nome_autor=nome_autor,
        cod_materia=cod_materia,
        cod_protocolo=cod_protocolo,
        num_protocolo=num_protocolo,
        cod_usuario=cod_usuario
    )


def criar_documento(tip_doc, txt_ementa, nome_autor, cod_materia, cod_protocolo, num_protocolo, cod_usuario):
    """Cria Documento Acessório (anexa PDF) e lança tramitação."""
    context.zsql.documento_acessorio_incluir_zsql(
        tip_documento=tip_doc,
        nom_documento=txt_ementa,
        nom_autor_documento=nome_autor,
        cod_materia=cod_materia,
        num_protocolo=num_protocolo,
        dat_documento=DateTime(datefmt='international').strftime('%d/%m/%Y %H:%M:%S'),
        ind_publico=1
    )

    cod_documento = None
    for codigo in context.zsql.documento_acessorio_incluido_codigo_obter_zsql():
        cod_documento = int(codigo.cod_documento)
        break

    if cod_documento is not None:
        id_documento = f"{cod_documento}.pdf"
        # só tenta anexar se veio arquivo
        if hasattr(REQUEST, 'form') and 'file' in REQUEST.form and REQUEST.form['file']:
            context.sapl_documentos.materia.manage_addFile(id=id_documento, file=REQUEST.form['file'])

        if context.dbcon_logs:
            context.zsql.logs_registrar_zsql(
                usuario=REQUEST['AUTHENTICATED_USER'].getUserName(),
                data=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                modulo='documento_acessorio_materia',
                metodo='resposta_executivo_pysc',
                cod_registro=cod_documento,
                IP=context.pysc.get_ip()
            )

    return tramitar_materia(
        cod_documento=cod_documento,
        cod_materia=cod_materia,
        cod_protocolo=cod_protocolo,
        num_protocolo=num_protocolo,
        cod_usuario=cod_usuario
    )


def tramitar_materia(cod_documento, cod_materia, cod_protocolo, num_protocolo, cod_usuario):
    """Finaliza a última tramitação, registra recebimento e cria nova tramitação padrão."""
    # encerra a "última" e registra recebimento
    for tr in context.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, ind_ult_tramitacao=1, ind_excluido=0):
        context.zsql.tramitacao_ind_ultima_atualizar_zsql(
            cod_materia=cod_materia,
            cod_tramitacao=tr.cod_tramitacao,
            ind_ult_tramitacao=0
        )
        if cod_usuario is not None:
            context.zsql.tramitacao_registrar_recebimento_zsql(
                cod_tramitacao=tr.cod_tramitacao,
                cod_usuario_corrente=cod_usuario
            )
        context.pysc.atualiza_indicador_tramitacao_materia_pysc(
            cod_materia=tr.cod_materia,
            cod_status=1056
        )
        break  # somente a atual/última

    hr_tramitacao = DateTime(datefmt='international').strftime('%d/%m/%Y %H:%M:%S')
    txt_tramitacao = (
        '<p>Resposta eletrônica recebida em '
        + hr_tramitacao
        + ' sob protocolo nº '
        + (num_protocolo or '')
        + '</p>'
    )

    context.zsql.tramitacao_incluir_zsql(
        cod_materia=cod_materia,
        dat_tramitacao=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
        cod_unid_tram_local=37,
        cod_usuario_local=cod_usuario,
        cod_unid_tram_dest=72,
        dat_encaminha=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
        cod_status=43,
        ind_urgencia=0,
        txt_tramitacao=txt_tramitacao,
        ind_ult_tramitacao=1
    )

    # notifica e gera PDF da tramitação atual
    for tr in context.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, ind_ult_tramitacao=1, ind_excluido=0):
        context.pysc.envia_tramitacao_autor_pysc(cod_materia=cod_materia)
        context.pysc.envia_acomp_materia_pysc(cod_materia=cod_materia)
        hdn_url = context.portal_url() + ''
        context.relatorios.pdf_tramitacao_preparar_pysc(
            hdn_cod_tramitacao=tr.cod_tramitacao,
            hdn_url=hdn_url
        )
        if context.dbcon_logs:
            context.zsql.logs_registrar_zsql(
                usuario=REQUEST['AUTHENTICATED_USER'].getUserName(),
                data=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
                modulo='tramitacao_materia',
                metodo='resposta_executivo_pysc',
                cod_registro=tr.cod_tramitacao,
                IP=context.pysc.get_ip()
            )
        break

    return criar_resposta(cod_protocolo=cod_protocolo, num_protocolo=num_protocolo)


def criar_resposta(cod_protocolo, num_protocolo):
    """Retorno JSON final para o cliente."""
    resposta = [{
        'status': 'SUCESSO',
        'usuario': usuario,
        'numero_protocolo': str(num_protocolo or ''),
        'codigo': str(cod_protocolo or ''),
        'data_protocolo': DateTime(datefmt='international').strftime('%d/%m/%Y %H:%M:%S'),
        'ip_origem': context.pysc.get_ip(),
    }]
    retorno = json.dumps(resposta)
    RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
    return retorno


# ===== Entrada principal =====
txt_ementa = obter_materia(cod_materia_respondida)
if not txt_ementa:
    # encerra com mensagem clara se a matéria não existir
    return retornar_erro(f"Matéria {cod_materia_respondida} não encontrada no banco de dados.")

return criar_protocolo(cod_materia_respondida, txt_ementa)
