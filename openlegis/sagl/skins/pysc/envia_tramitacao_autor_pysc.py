## Script (Python) "envia_tramitacao_autor_pysc"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=cod_materia
##title=

from xml.sax.saxutils import escape
from email.mime.text import MIMEText
from DateTime import DateTime
import logging

request = context.REQUEST
mailhost = context.MailHost

# Dados da casa legislativa
props = dict(context.sapl_documentos.props_sagl.propertyItems())
email_casa = props.get('end_email_casa', '').strip()
casa_legislativa = props.get('nom_casa', 'Câmara Municipal')

if not email_casa or '@' not in email_casa:
    logging.warning('Email da casa legislativa (remetente) não configurado corretamente.')
    return

data_registro = DateTime(datefmt='international').strftime('%d/%m/%Y às %H:%M')

for materia in context.zsql.materia_obter_zsql(cod_materia=cod_materia):
    ementa = escape(materia.txt_ementa or '')
    projeto = f"{materia.des_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica}"

    # Coleta autores únicos
    lista_autor = []
    lista_codigo = set()
    for autor in context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia):
        cod_autor = int(autor.cod_autor)
        nome_autor = autor.nom_autor_join
        if cod_autor not in lista_codigo:
            lista_codigo.add(cod_autor)
            lista_autor.append(nome_autor)

    nom_autor = ', '.join(lista_autor)

    # Informações da última tramitação
    data = ''
    status = ''
    texto_acao = ''
    for tramitacao in context.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, ind_ult_tramitacao=1):
        data = tramitacao.dat_tramitacao.strftime('%d/%m/%Y')
        status = tramitacao.des_status or ''
        texto_acao = escape(tramitacao.txt_tramitacao or '')

    # Link da matéria
    linkMat = f"{request.SERVER_URL}/consultas/materia/materia_mostrar_proc?cod_materia={cod_materia}"

    # Coleta e-mails válidos dos autores
    destinatarios = set()
    for cod_autor in lista_codigo:
        for dest in context.zsql.autor_obter_zsql(cod_autor=cod_autor):
            if dest.end_email and '@' in dest.end_email:
                destinatarios.add(dest.end_email.strip())

    # Monta e envia os e-mails
    for email_dest in destinatarios:
        assunto = f"{projeto} - Aviso de tramitação em {data_registro}"
        html = f"""\
        <html>
          <head></head>
          <body>
            <p>A seguinte matéria de sua autoria sofreu tramitação registrada em {data_registro}:</p>
            <p>
              <a href="{linkMat}" target="_blank">{projeto}</a><br>
              {ementa}<br>
              Autoria: {nom_autor}<br>
              Data da Ação: {data}<br>
              Status: {status}
            </p>
            <p>
              <strong>{casa_legislativa}</strong><br>
              Processo Digital
            </p>
          </body>
        </html>
        """

        try:
            # Verificação final antes do envio
            if email_dest and email_casa and assunto and html:
                mensagem = MIMEText(html, 'html', 'utf-8')
                mailhost.send(mensagem, mTo=email_dest, mFrom=email_casa, subject=assunto)
        except Exception as e:
            logging.error(f"Erro ao enviar e-mail para {email_dest}: {e}")
