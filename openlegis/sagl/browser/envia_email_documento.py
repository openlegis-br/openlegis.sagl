# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import View as GrokView, name
from grokcore.security import require
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface

from io import BytesIO
from email.message import EmailMessage
from email.mime.text import MIMEText
from DateTime import DateTime
import json


@implementer(IPublishTraverse)
class EmailDoc(GrokView):
    # Diretivas grokcore.* (registro automático)
    context(Interface)
    name('email_doc')
    require('zope2.WebDAVAccess')

    cod_documento = None
    cod_materia = None
    cod_destinatario = None

    # ------------- helpers -------------

    def _json(self, payload, status=200):
        self.request.response.setStatus(status)
        self.request.response.setHeader(
            'Content-Type', 'application/json; charset=utf-8'
        )
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _get_casa_props(self):
        casa = {}
        props = getattr(self.context.sapl_documentos, 'props_sagl', None)
        if props:
            for k, v in props.propertyItems():
                casa[k] = v
        return casa

    def _get_estado_nome(self, sgl_uf):
        estados = self.context.zsql.localidade_obter_zsql(tip_localidade="u", sgl_uf=sgl_uf)
        return estados[0].nom_localidade if estados else ""

    def _logo_url(self, portal_url):
        props = getattr(self.context.sapl_documentos, 'props_sagl', None)
        if props and hasattr(props, 'logo_casa.gif'):
            return f"{portal_url}/sapl_documentos/props_sagl/logo_casa.gif"
        return f"{portal_url}/imagens/brasao.gif"

    def _get_usuario(self):
        username = self.context.REQUEST.get('AUTHENTICATED_USER', None)
        username = username.getUserName() if username else ""
        dados = {
            "cod_usuario": "",
            "usuario": username or "Usuário",
            "cargo_usuario": "",
            "email_usuario": "",
        }
        for u in self.context.zsql.usuario_obter_zsql(col_username=username):
            dados["cod_usuario"] = u.cod_usuario
            dados["usuario"] = getattr(u, 'nom_completo', dados["usuario"])
            dados["cargo_usuario"] = getattr(u, 'nom_cargo', "")
            dados["email_usuario"] = getattr(u, 'end_email', "")
            break
        return dados

    def _unique_preserve_order(self, seq):
        seen = set()
        out = []
        for x in seq:
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out

    def _attach_pdf_if_exists(self, container, filename, msg, download_name):
        if not container or not filename:
            return False
        if hasattr(container, filename):
            obj = getattr(container, filename)
            try:
                data = obj.data
                if not isinstance(data, (bytes, bytearray)):
                    data = bytes(data)
                msg.add_attachment(
                    data,
                    maintype='application',
                    subtype='pdf',
                    filename=download_name
                )
                return True
            except Exception:
                return False
        return False

    # ------------- núcleo de composição -------------

    def _monta_msg_base(self, casa_legislativa, email_casa, usuario, email_usuario):
        msg = EmailMessage()
        msg['From'] = f'{casa_legislativa} <{email_casa}>'
        if email_usuario:
            msg['Reply-To'] = f'{usuario} <{email_usuario}>'
        return msg

    def _html_processo_admin(self, **kw):
        bloco_link = (
            f'<p style="margin-top:30px; margin-bottom:30px">'
            f'Para consultar o andamento do processo, '
            f'<a href="{kw["link_processo"]}" target="_blank">clique aqui</a>.'
            f'</p>'
        ) if kw.get('link_processo') else ''
        return f"""\
<html>
  <head></head>
  <body style="margin: 25px">
    <div style="min-width:300px; margin:0 auto;">
      <img style="display:block; margin:0 auto;" src="{kw['logo_casa']}" width="90" height="90">
      <p align="center" style="font-family:Arial, Helvetica, sans-serif; font-size:20px; font-weight:bold; margin:10px 0 5px; text-transform:uppercase">{kw['casa_legislativa']}</p>
      <p align="center" style="font-family:Arial, Helvetica, sans-serif; font-size:14px; margin-top:5px">Estado de {kw['estado']}</p>
    </div>
    <div style="min-width:300px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; font-size:15px; margin:40px 0">
      <p style="margin-bottom:30px;">Prezado(a) Senhor(a),</p>
      <p style="margin-bottom:30px;">Encaminhamos para seu conhecimento, por meio do arquivo digital em anexo, o conteúdo do documento administrativo abaixo identificado.</p>
      <p><b>Processo:</b> {kw['id_processo']}</p>
      <p><b>Interessado:</b> {kw['nom_autor']}</p>
      <p><b>Assunto:</b> {kw['txt_assunto']}</p>
      {bloco_link}
      <p style="margin:30px 0;">Cordialmente,</p>
      <p><b>{kw['usuario']}</b></p>
      <p>{kw['cargo_usuario']}</p>
    </div>
    <hr>
    <div style="min-width:300px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; font-size:13px; color:#555">
      <p>Este e-mail e quaisquer arquivos anexados são confidenciais e destinados exclusivamente ao(s) destinatário(s) indicado(s). Se você não for o destinatário, por favor, notifique o remetente imediatamente e exclua esta mensagem de seu sistema.</p>
      <p>Em conformidade com a LGPD, informamos que os dados pessoais contidos neste e-mail podem ser coletados e tratados pela {kw['casa_legislativa']} para fins de comunicação institucional. Você tem o direito de acessar, corrigir ou solicitar a exclusão de seus dados pessoais a qualquer momento.</p>
      <p>A {kw['casa_legislativa']} não se responsabiliza por quaisquer danos resultantes do uso indevido das informações contidas neste e-mail.</p>
    </div>
  </body>
</html>
"""

    def _html_materia(self, **kw):
        return f"""\
<html>
  <head></head>
  <body style="margin: 25px">
    <div style="min-width:300px; margin:0 auto;">
      <img style="display:block; margin:0 auto;" src="{kw['logo_casa']}" width="90" height="90">
      <p align="center" style="font-family:Arial, Helvetica, sans-serif; font-size:20px; font-weight:bold; margin:10px 0 5px; text-transform:uppercase">{kw['casa_legislativa']}</p>
      <p align="center" style="font-family:Arial, Helvetica, sans-serif; font-size:14px; margin-top:5px">Estado de {kw['estado']}</p>
    </div>
    <div style="min-width:300px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; font-size:15px; margin:40px 0">
      <p style="margin-bottom:30px;">Prezado(a) Senhor(a),</p>
      <p style="margin-bottom:30px;">Encaminhamos para seu conhecimento, por meio do arquivo digital em anexo, o conteúdo da matéria legislativa abaixo identificada.</p>
      <p><b>Matéria:</b> {kw['id_processo']}</p>
      <p><b>Autoria:</b> {kw['nom_autor']}</p>
      <p><b>Ementa:</b> {kw['txt_assunto']}</p>
      <p style="margin-top:30px; margin-bottom:30px">
        Para consultar o processo integral, <a href="{kw['link_processo']}" target="_blank">clique aqui</a>.
      </p>
      <p style="margin-bottom:30px;">Cordialmente,</p>
      <p><b>{kw['usuario']}</b></p>
      <p>{kw['cargo_usuario']}</p>
    </div>
    <hr>
    <div style="min-width:300px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; font-size:13px; color:#555">
      <p>Este e-mail e quaisquer arquivos anexados são confidenciais e destinados exclusivamente ao(s) destinatário(s) indicado(s). Se você não for o destinatário, por favor, notifique o remetente imediatamente e exclua esta mensagem de seu sistema.</p>
      <p>Em conformidade com a LGPD, informamos que os dados pessoais contidos neste e-mail podem ser coletados e tratados pela {kw['casa_legislativa']} para fins de comunicação institucional. Você tem o direito de acessar, corrigir ou solicitar a exclusão de seus dados pessoais a qualquer momento.</p>
      <p>A {kw['casa_legislativa']} não se responsabiliza por quaisquer danos resultantes do uso indevido das informações contidas neste e-mail.</p>
    </div>
  </body>
</html>
"""

    # ------------- montagem por cenário -------------

    def _destinatarios_processo(self, cod_documento, cod_destinatario):
        recipients = []
        destinatarios_ids = []

        if not cod_destinatario:
            it = self.context.zsql.destinatario_oficio_obter_zsql(
                cod_documento=cod_documento, ind_excluido=0
            )
        else:
            it = self.context.zsql.destinatario_oficio_obter_zsql(
                cod_destinatario=cod_destinatario, cod_documento=cod_documento, ind_excluido=0
            )

        for item in it:
            destinatario = ""
            if getattr(item, 'cod_instituicao', None):
                insts = self.context.zsql.instituicao_obter_zsql(cod_instituicao=item.cod_instituicao)
                if insts:
                    destinatario = insts[0].end_email or ""
            else:
                destinatario = getattr(item, 'end_email', '') or ''

            if destinatario:
                recipients.append(destinatario)
                destinatarios_ids.append(item.cod_destinatario)

        return self._unique_preserve_order(recipients), destinatarios_ids

    def _destinatarios_materia(self, cod_materia, cod_destinatario):
        recipients = []
        destinatarios_ids = []

        if not cod_destinatario:
            it = self.context.zsql.destinatario_oficio_obter_zsql(
                cod_materia=cod_materia, ind_excluido=0
            )
        else:
            it = self.context.zsql.destinatario_oficio_obter_zsql(
                cod_destinatario=cod_destinatario, cod_materia=cod_materia, ind_excluido=0
            )

        for item in it:
            destinatario = ""
            if getattr(item, 'cod_instituicao', None):
                insts = self.context.zsql.instituicao_obter_zsql(cod_instituicao=item.cod_instituicao)
                if insts:
                    destinatario = insts[0].end_email or ""
            else:
                destinatario = getattr(item, 'end_email', '') or ''

            if destinatario:
                recipients.append(destinatario)
                destinatarios_ids.append(item.cod_destinatario)

        return self._unique_preserve_order(recipients), destinatarios_ids

    # ------------- API principal -------------

    def send_message(self, cod_destinatario='', cod_documento='', cod_materia=''):
        casa = self._get_casa_props()
        portal_url = self.context.portal_url.portal_url()

        # estado (nome por UF)
        estado = ""
        locs = self.context.zsql.localidade_obter_zsql(cod_localidade=casa.get("cod_localidade"))
        if locs:
            estado = self._get_estado_nome(locs[0].sgl_uf)

        email_casa = casa.get('end_email_casa', '')
        casa_legislativa = casa.get('nom_casa', 'Câmara Municipal')
        logo_casa = self._logo_url(portal_url)

        user = self._get_usuario()
        cod_usuario = user["cod_usuario"]
        usuario = user["usuario"]
        cargo_usuario = user["cargo_usuario"]
        email_usuario = user["email_usuario"]

        msg = self._monta_msg_base(casa_legislativa, email_casa, usuario, email_usuario)

        # ---- Processo administrativo ----
        if cod_documento and not cod_materia:
            recipients, destinatarios = self._destinatarios_processo(cod_documento, cod_destinatario)

            if not recipients:
                return None, [], cod_usuario, "Nenhum destinatário com e-mail válido."

            if len(recipients) > 1:
                msg['To'] = f'{casa_legislativa} <{email_casa}>' if email_casa else ', '.join(recipients[:1])
                msg['Bcc'] = ", ".join(recipients)
            else:
                msg['To'] = recipients[0]

            documentos = list(self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento))
            if not documentos:
                return None, [], cod_usuario, "Documento não encontrado."
            documento = documentos[0]

            nom_anexo = f"{documento.sgl_tipo_documento}-{documento.num_documento}-{documento.ano_documento}.pdf"
            id_processo = f"{documento.des_tipo_documento} n° {documento.num_documento}/{documento.ano_documento}"
            txt_assunto = getattr(documento, 'txt_assunto', '') or ''
            nom_autor = getattr(documento, 'txt_interessado', '') or ''

            chave_acesso = ""
            if getattr(documento, 'num_protocolo', None):
                protos = self.context.zsql.protocolo_obter_zsql(
                    num_protocolo=documento.num_protocolo, ano_protocolo=documento.ano_documento
                )
                if protos and getattr(protos[0], 'codigo_acesso', None):
                    chave_acesso = protos[0].codigo_acesso

            link_processo = (f"{portal_url}/consultas/protocolo/pesquisa_publica_proc?"
                             f"txt_chave_acesso={chave_acesso}") if chave_acesso else ""

            msg['Subject'] = f'Encaminha {id_processo}'
            html = self._html_processo_admin(
                id_processo=id_processo, txt_assunto=txt_assunto, nom_autor=nom_autor,
                casa_legislativa=casa_legislativa, estado=estado, logo_casa=logo_casa,
                usuario=usuario, cargo_usuario=cargo_usuario, link_processo=link_processo
            )
            msg.attach(MIMEText(html, "html", "utf-8"))

            self._attach_pdf_if_exists(
                getattr(self.context.sapl_documentos, 'administrativo', None),
                f"{cod_documento}_texto_integral.pdf",
                msg,
                nom_anexo
            )

            return msg, destinatarios, cod_usuario, ""

        # ---- Matéria legislativa ----
        if cod_materia and not cod_documento:
            recipients, destinatarios = self._destinatarios_materia(cod_materia, cod_destinatario)

            if not recipients:
                return None, [], cod_usuario, "Nenhum destinatário com e-mail válido."

            if len(recipients) > 1:
                msg['To'] = f'{casa_legislativa} <{email_casa}>' if email_casa else ', '.join(recipients[:1])
                msg['Bcc'] = ", ".join(recipients)
            else:
                msg['To'] = recipients[0]

            materias = list(self.context.zsql.materia_obter_zsql(cod_materia=cod_materia))
            if not materias:
                return None, [], cod_usuario, "Matéria não encontrada."
            materia = materias[0]

            nom_anexo = f"{materia.sgl_tipo_materia}-{materia.num_ident_basica}-{materia.ano_ident_basica}.pdf"
            id_proc = f"{materia.des_tipo_materia} n° {materia.num_ident_basica}/{materia.ano_ident_basica}"
            txt_assunto = getattr(materia, 'txt_ementa', '') or ''

            autorias = self.context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
            nomes = [getattr(a, 'nom_autor_join', '') for a in autorias]
            nom_autor = ', '.join([n for n in nomes if n])

            link = f"{portal_url}/consultas/materia/materia_mostrar_proc?cod_materia={materia.cod_materia}"

            msg['Subject'] = f'Encaminha {id_proc}'
            html = self._html_materia(
                id_processo=id_proc, nom_autor=nom_autor, txt_assunto=txt_assunto,
                casa_legislativa=casa_legislativa, estado=estado, logo_casa=logo_casa,
                usuario=usuario, cargo_usuario=cargo_usuario, link_processo=link
            )
            msg.attach(MIMEText(html, "html", "utf-8"))

            materia_container = getattr(self.context.sapl_documentos, 'materia', None)
            anexado = self._attach_pdf_if_exists(
                materia_container, f"{cod_materia}_redacao_final.pdf", msg, nom_anexo
            )
            if not anexado:
                self._attach_pdf_if_exists(
                    materia_container, f"{cod_materia}_texto_integral.pdf", msg, nom_anexo
                )

            return msg, destinatarios, cod_usuario, ""

        return None, [], "", "Parâmetros insuficientes."

    # ------------- render -------------

    def render(self, cod_documento='', cod_materia='', cod_destinatario=''):
        msg, destinatarios, cod_usuario, err = self.send_message(
            cod_destinatario=cod_destinatario,
            cod_documento=cod_documento,
            cod_materia=cod_materia
        )

        if err:
            return self._json({"ok": False, "error": err}, status=400)

        if not msg:
            return self._json({"ok": False, "error": "Falha ao montar mensagem."}, status=500)

        try:
            self.context.MailHost.send(msg.as_string(), immediate=True)
        except Exception as e:
            return self._json({"ok": False, "error": f"Erro no envio: {e}"}, status=500)

        enviados = 0
        for did in destinatarios:
            try:
                self.context.zsql.destinatario_oficio_enviar_zsql(
                    cod_destinatario=did, cod_usuario=cod_usuario
                )
                enviados += 1
            except Exception:
                pass

        return self._json({
            "ok": True,
            "enviados": enviados,
            "destinatarios": destinatarios,
            "timestamp": DateTime().ISO()
        })
