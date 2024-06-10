# -*- coding: utf-8 -*-
import sys, os, string
import shutil
import subprocess
from subprocess import Popen, PIPE
from io import BytesIO
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import requests

class otimizarPDF(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('otimizar_anexos')

    def optimizeFiles(self, cod_proposicao):
        dirtemp = os.path.join('/tmp/')
        for item in self.context.pysc.anexo_proposicao_pysc(cod_proposicao, listar=True):
           nom_arquivo = item
           nom_saida = 'temp_' + nom_arquivo
           if hasattr(self.context.sapl_documentos.proposicao, nom_arquivo):
               arq = getattr(self.context.sapl_documentos.proposicao,nom_arquivo)        
               arquivo = BytesIO(str(arq.data))
               arquivo.seek(0)
               f = open(os.path.join(dirtemp) + '/' + nom_arquivo, 'wb').write(arquivo.getvalue())
               subprocess.call('gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/prepress -dNOPAUSE -dQUIET -dBATCH -sOutputFile=' + os.path.join(dirtemp) + '/' + nom_saida + ' ' + os.path.join(dirtemp) + '/' + nom_arquivo, shell=True)
               #subprocess.call('mutool clean -gggg -d -i -f -z ' + os.path.join(dirtemp) + '/' + nom_arquivo + ' ' + os.path.join(dirtemp) + '/' + nom_saida, shell=True)
               filepath = os.path.join(dirtemp, nom_saida)
               arq2 = open(filepath, 'rb')
               arquivo2 = BytesIO(str(arq2.read()))
               self.context.sapl_documentos.proposicao.manage_delObjects(nom_arquivo)
               self.context.sapl_documentos.proposicao.manage_addFile(nom_arquivo)
               arq3=self.context.sapl_documentos.proposicao[nom_arquivo]
               arq3.manage_edit(title=nom_arquivo,filedata=arquivo2.getvalue(),content_type='application/pdf')
               os.unlink(os.path.join(dirtemp) + '/' + nom_arquivo)
               os.unlink(os.path.join(dirtemp) + '/' + nom_saida)

    def render(self, cod_proposicao):
        portal_url = self.context.portal_url.portal_url()
        portal = self.context.portal_url.getPortalObject()    
        self.optimizeFiles(cod_proposicao=cod_proposicao)
