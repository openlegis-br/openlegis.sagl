# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from io import BytesIO

from email.message import EmailMessage
from email.mime.text import MIMEText


@implementer(IPublishTraverse)
class EmailDoc(grok.View):
    grok.context(Interface)
    grok.require('zope2.WebDAVAccess')
    grok.name('email_doc')

    cod_documento = None
    cod_materia = None
    cod_destinatario = None


    def send_message(self, cod_destinatario='', cod_documento='', cod_materia=''):
        casa={}
        aux=self.context.sapl_documentos.props_sagl.propertyItems()
        for item in aux:
            casa[item[0]] = item[1]
        localidade=self.context.zsql.localidade_obter_zsql(cod_localidade=casa["cod_localidade"])
        for item in self.context.zsql.localidade_obter_zsql(tip_localidade="u", sgl_uf=localidade[0].sgl_uf):
            estado = item.nom_localidade
        email_casa = casa['end_email_casa']
        casa_legislativa = casa['nom_casa']
        portal_url = self.context.portal_url.portal_url()
        if hasattr(self.context.sapl_documentos.props_sagl, 'logo_casa.gif'):
           logo_casa = self.context.portal_url.portal_url() + '/sapl_documentos/props_sagl/logo_casa.gif'
        else:
           logo_casa = self.context.portal_url.portal_url() + '/imagens/brasao.gif'
        cod_usuario = ''
        usuario = self.context.REQUEST['AUTHENTICATED_USER'].getUserName()
        cargo_usuario = ''
        for user in self.context.zsql.usuario_obter_zsql(col_username=self.context.REQUEST['AUTHENTICATED_USER'].getUserName()):
            cod_usuario = user.cod_usuario
            usuario = user.nom_completo
            cargo_usuario = user.nom_cargo

        msg = EmailMessage()
        msg['From'] = '%s <%s>' % (casa_legislativa, email_casa)

        recipients = []
        destinatarios = []

        # PROCESSO ADMINISTRATIVO
        if cod_documento != '' and cod_materia == '':
           if cod_destinatario == '':
              for item in self.context.zsql.destinatario_oficio_obter_zsql(cod_documento=cod_documento, ind_excluido=0):
                  if item.cod_instituicao != None:
                      for inst in self.context.zsql.instituicao_obter_zsql(cod_instituicao=item.cod_instituicao):
                          destinatario = inst.end_email
                      if destinatario != '':
                         recipients.append(destinatario)
                         destinatarios.append(item.cod_destinatario)
                  elif item.cod_instituicao == None:
                     destinatario = item.end_email
                     recipients.append(destinatario)
                     destinatarios.append(item.cod_destinatario)
           elif cod_destinatario != '':
              for item in self.context.zsql.destinatario_oficio_obter_zsql(cod_destinatario=cod_destinatario, cod_documento=cod_documento, ind_excluido=0):
                  if item.cod_instituicao != None:
                      for inst in self.context.zsql.instituicao_obter_zsql(cod_instituicao=item.cod_instituicao):
                          destinatario = inst.end_email
                      if destinatario != '':
                         recipients.append(destinatario)
                         destinatarios.append(item.cod_destinatario)
                  elif item.cod_instituicao == None:
                     destinatario = item.end_email
                     recipients.append(destinatario)
                     destinatarios.append(item.cod_destinatario)

           recipients = [
               e
               for i, e in enumerate(recipients)
               if recipients.index(e) == i
           ]

           msg['To'] = ", ".join(recipients)
           
           for documento in self.context.zsql.documento_administrativo_obter_zsql(cod_documento=cod_documento):
               nom_anexo = str(documento.sgl_tipo_documento)+'-'+str(documento.num_documento)+'-'+str(documento.ano_documento)+'.pdf'
               id_processo = str(documento.des_tipo_documento)+' n° '+str(documento.num_documento)+'/'+str(documento.ano_documento)
               txt_assunto = documento.txt_assunto
               nom_autor = documento.txt_interessado

               msg['Subject'] = 'Encaminha ' + id_processo

               html = """\
                <html>
                  <head></head>
                  <body style="margin: 25px">
                    <div style=min-width::300px; margin:0 auto;">
                        <img style="display: block; margin: 0 auto;" src="{logo_casa}" width="90px" height="90px">
                        <p align="center" style="font-family:Arial, Helvetica, sans-serif; font-size:20px; font-weight: bold; margin-top: 10px; margin-bottom: 5px; text-transform: uppercase">{casa_legislativa}</p>
                        <p align="center" style="font-family:Arial, Helvetica, sans-serif; font-size:14px;margin-top: 5px">Estado de {estado}</p>
                    </div>
                    <div style="min-width:300px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; font-size:15px; margin-top: 40px; margin-bottom: 40px">
                     <p style="margin-bottom:30px;">Prezado(a) Senhor(a),</p>
                     <p style="margin-bottom:30px;">Encaminhamos para seu conhecimento, por meio do arquivo digital em anexo, o conteúdo do documento administrativo abaixo identificado.</p>
                     <p><b>Processo:</b> {id_processo}</p>
                     <p><b>Interessado:</b> {nom_autor}</p>
                     <p><b>Assunto:</b> {ementa}</p>
                     <p style="margin-top:30px; margin-bottom:30px">Cordialmente,</p>
                     <p><b>{usuario}</b></p>
                     <p>{cargo_usuario}</p>
                    </div>
                    <hr>
                    <div style="min-width:300px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; font-size:13px; color: #555">
                      <p>Este e-mail e quaisquer arquivos anexados são confidenciais e destinados exclusivamente ao(s) destinatário(s) indicado(s). Se você não for o destinatário, por favor, notifique o remetente imediatamente e exclua esta mensagem de seu sistema. </p>
                      <p>Em conformidade com a Lei Geral de Proteção de Dados (LGPD), informamos que os dados pessoais contidos neste e-mail podem ser coletados e tratados pela {casa_legislativa} para fins de comunicação institucional. Você tem o direito de acessar, corrigir ou solicitar a exclusão de seus dados pessoais a qualquer momento, conforme previsto na legislação.</p>
                      <p>A {casa_legislativa} não se responsabiliza por quaisquer danos resultantes do uso indevido das informações contidas neste e-mail.</p>
                    </div>
                  </body>
                </html>
                """.format(id_processo=id_processo, ementa=txt_assunto, nom_autor=nom_autor, casa_legislativa=casa_legislativa, estado=estado, portal_url=portal_url, logo_casa=logo_casa, usuario=usuario, cargo_usuario=cargo_usuario)

               arquivo = str(cod_documento) + "_texto_integral.pdf"
               if hasattr(self.context.sapl_documentos.administrativo, arquivo):
                  arq = getattr(self.context.sapl_documentos.administrativo, arquivo)
                  arquivo_pdf = BytesIO(bytes(arq.data))
                  msg.add_attachment(arquivo_pdf.getvalue(), maintype='application', subtype='pdf', filename=nom_anexo)
                  msg.attach(MIMEText(html, "html", "utf-8"))              

           if recipients != []:
              return msg, destinatarios, cod_usuario

        # MATERIA LEGISLATIVA
        if cod_materia != '' and cod_documento == '':
           if cod_destinatario == '':
              for item in self.context.zsql.destinatario_oficio_obter_zsql(cod_materia=cod_materia, ind_excluido=0):
                  if item.cod_instituicao != None:
                      for inst in self.context.zsql.instituicao_obter_zsql(cod_instituicao=item.cod_instituicao):
                          destinatario = inst.end_email
                      if destinatario != '':
                         recipients.append(destinatario)
                         destinatarios.append(item.cod_destinatario)
                  elif item.cod_instituicao == None:
                     destinatario = item.end_email
                     recipients.append(destinatario)
                     destinatarios.append(item.cod_destinatario)
           elif cod_destinatario != '':
              for item in self.context.zsql.destinatario_oficio_obter_zsql(cod_destinatario=cod_destinatario, cod_materia=cod_materia, ind_excluido=0):
                  if item.cod_instituicao != None:
                      for inst in self.context.zsql.instituicao_obter_zsql(cod_instituicao=item.cod_instituicao):
                          destinatario = inst.end_email
                      if destinatario != '':
                         recipients.append(destinatario)
                         destinatarios.append(item.cod_destinatario)
                  elif item.cod_instituicao == None:
                     destinatario = item.end_email
                     recipients.append(destinatario)
                     destinatarios.append(item.cod_destinatario)

           recipients = [
               e
               for i, e in enumerate(recipients)
               if recipients.index(e) == i
           ]

           msg['To'] = ", ".join(recipients)

           for materia in self.context.zsql.materia_obter_zsql(cod_materia=cod_materia):
               nom_anexo = str(materia.sgl_tipo_materia)+'-'+str(materia.num_ident_basica)+'-'+str(materia.ano_ident_basica)+'.pdf'
               id_processo = str(materia.des_tipo_materia)+' n° '+str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
               txt_assunto = materia.txt_ementa
               nom_autor = ""
               autorias = self.context.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia)
               fields = list(autorias.data_dictionary().keys())
               lista_autor = []
               for autor in autorias:
                   for field in fields:
                       nome_autor = autor['nom_autor_join']
                   lista_autor.append(nome_autor)
               nom_autor = ', '.join(['%s' % (value) for (value) in lista_autor])
               link_processo = self.context.portal_url.portal_url() + '/consultas/materia/materia_mostrar_proc?cod_materia=' + str(materia.cod_materia)
               msg['Subject'] = 'Encaminha ' + id_processo

               html="""
                <html>
                  <head></head>
                  <body style="margin: 25px">
                    <div style=min-width::300px; margin:0 auto;">
                        <img style="display: block; margin: 0 auto;" src="{logo_casa}" width="90px" height="90px">
                        <p align="center" style="font-family:Arial, Helvetica, sans-serif; font-size:20px; font-weight: bold; margin-top: 10px; margin-bottom: 5px; text-transform: uppercase">{casa_legislativa}</p>
                        <p align="center" style="font-family:Arial, Helvetica, sans-serif; font-size:14px;margin-top: 5px">Estado de {estado}</p>
                    </div>
                    <div style="min-width:300px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; font-size:15px; margin-top: 40px; margin-bottom: 40px">
                     <p style="margin-bottom:30px;">Prezado(a) Senhor(a),</p>
                     <p style="margin-bottom:30px;">Encaminhamos para seu conhecimento, por meio do arquivo digital em anexo, o conteúdo da matéria legislativa abaixo identificada.</p>
                     <p><b>Matéria:</b> {id_processo}</p>
                     <p><b>Autoria:</b> {nom_autor}</p>
                     <p><b>Ementa:</b> {ementa}</p>
                     <p style="margin-top:30px; margin-bottom:30px">
                       Para consultar o processo integral, <a href="{link_processo}" target="blank">clique aqui</a>.
                     </p>
                     <p style="margin-bottom:30px">Cordialmente,</p>
                     <p><b>{usuario}</b></p>
                     <p>{cargo_usuario}</p>
                    </div>
                    <hr>
                    <div style="min-width:300px; margin:0 auto; font-family:Arial, Helvetica, sans-serif; font-size:13px; color: #555">
                      <p>Este e-mail e quaisquer arquivos anexados são confidenciais e destinados exclusivamente ao(s) destinatário(s) indicado(s). Se você não for o destinatário, por favor, notifique o remetente imediatamente e exclua esta mensagem de seu sistema. </p>
                      <p>Em conformidade com a Lei Geral de Proteção de Dados (LGPD), informamos que os dados pessoais contidos neste e-mail podem ser coletados e tratados pela {casa_legislativa} para fins de comunicação institucional. Você tem o direito de acessar, corrigir ou solicitar a exclusão de seus dados pessoais a qualquer momento, conforme previsto na legislação.</p>
                      <p>A {casa_legislativa} não se responsabiliza por quaisquer danos resultantes do uso indevido das informações contidas neste e-mail.</p>
                    </div>
                  </body>
                </html>
                """.format(id_processo=id_processo, ementa=txt_assunto, nom_autor=nom_autor, casa_legislativa=casa_legislativa, estado=estado, portal_url=portal_url, logo_casa=logo_casa, usuario=usuario, cargo_usuario=cargo_usuario, link_processo=link_processo)

               arquivo = str(cod_materia) + "_texto_integral.pdf"
               if hasattr(self.context.sapl_documentos.materia, arquivo):
                  arq = getattr(self.context.sapl_documentos.materia, arquivo)
                  arquivo_pdf = BytesIO(bytes(arq.data))
                  msg.add_attachment(arquivo_pdf.getvalue(), maintype='application', subtype='pdf', filename=nom_anexo)
                  msg.attach(MIMEText(html, "html", "utf-8"))                       
           if recipients != []:
              return msg, destinatarios, cod_usuario


    def render(self, cod_documento='', cod_materia='', cod_destinatario=''):
        msg = self.send_message(cod_documento=cod_documento, cod_materia=cod_materia, cod_destinatario=cod_destinatario)
        
        try:
            self.context.MailHost.send(msg[0], immediate=True)
        except Exception as e:
            return e
        else:
            for item in msg[1]:
                self.context.zsql.destinatario_oficio_enviar_zsql(cod_destinatario=item,cod_usuario=msg[2])
        
        #return msg[0]
