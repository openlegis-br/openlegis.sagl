# -*- coding: utf-8 -*-
from io import BytesIO
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
from pypdf import PdfReader
import pymupdf

class otimizarPDF(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('otimizar_arquivo')

    def optimizeFile(self, filename, title):
        temp_path = self.context.temp_folder
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
  
    def render(self, filename, title):
        return self.optimizeFile(filename, title)
