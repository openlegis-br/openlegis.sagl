# -*- coding: utf-8 -*-
<<<<<<< HEAD
import os
import subprocess
=======
>>>>>>> 7ea825a (V5)
from io import BytesIO
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
<<<<<<< HEAD
from PyPDF4 import PdfFileReader, PdfFileWriter
=======
from pypdf import PdfReader
import pymupdf
>>>>>>> 7ea825a (V5)

class otimizarPDF(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('otimizar_arquivo')

    def optimizeFile(self, filename, title):
        temp_path = self.context.temp_folder
<<<<<<< HEAD
        nom_arquivo = filename
        nom_saida = 'temp_' + nom_arquivo
        arq = getattr(temp_path,filename)
        arquivo = BytesIO(str(arq.data))
        #arquivo.seek(0)
        reader = PdfFileReader(arquivo)
        sign = reader.getFields()
        if sign is not None:
           temp_path.manage_delObjects(nom_arquivo)
           resultado = arquivo.getvalue()
        else:
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
=======
        if hasattr(temp_path,filename):
           arq = getattr(temp_path,filename)
           with BytesIO(bytes(arq.data)) as data:
                reader = PdfReader(data)
                temp_path.manage_delObjects(filename)
                fields = reader.get_fields()
                if fields != None:
                   return data.getvalue()
                else:
                   doc = pymupdf.open(stream=data.getvalue())
                   metadata = {"title": title}
                   doc.set_metadata(metadata)
                   output = doc.tobytes(deflate=True, garbage=3, use_objstms=1)
                   return bytes(output)
>>>>>>> 7ea825a (V5)
   
    def render(self, filename, title):
        return self.optimizeFile(filename, title)
