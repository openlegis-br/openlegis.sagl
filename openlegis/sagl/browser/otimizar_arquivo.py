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
from PyPDF4 import PdfFileReader, PdfFileWriter

class otimizarPDF(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('otimizar_arquivo')

    def optimizeFile(self, filename, title):
        dirtemp = os.path.join('/tmp/')
        temp_path = self.context.temp_folder
        nom_arquivo = filename
        nom_saida = 'temp_' + nom_arquivo
        arq = getattr(temp_path,filename)
        arquivo = BytesIO(str(arq))
        arquivo.seek(0)
        f = open(os.path.join(dirtemp) + '/' + nom_arquivo, 'wb').write(arquivo.getvalue())
        temp_path.manage_delObjects(nom_arquivo)
        subprocess.call('mutool clean -gggg ' + os.path.join(dirtemp) + '/' + nom_arquivo + ' ' + os.path.join(dirtemp) + '/' + nom_saida, shell=True)
        #subprocess.call('gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook -dNOPAUSE -dQUIET -dBATCH -sOutputFile=' + os.path.join(dirtemp) + '/' + nom_saida + ' ' + os.path.join(dirtemp) + '/' + nom_arquivo, shell=True)
        os.unlink(os.path.join(dirtemp, nom_arquivo))
        filepath = os.path.join(dirtemp, nom_saida)
        arq2 = open(filepath, 'rb')
        arquivo2 = BytesIO(str(arq2.read()))
        reader = PdfFileReader(arquivo2)
        os.unlink(os.path.join(dirtemp, nom_saida))
        writer = PdfFileWriter()
        for page in reader.pages:
            writer.addPage(page)
        writer.addMetadata({"/Title": title})
        arquivo3 = BytesIO()
        writer.write(arquivo3)
        arquivo3.seek(0)
        resultado = arquivo3.getvalue()
        return resultado
   
    def render(self, filename, title):
        return self.optimizeFile(filename, title)
