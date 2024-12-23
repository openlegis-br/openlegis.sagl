## -*- coding: utf-8 -*-
##bind namespace=
##bind subpath=traverse_subpath
##parameters=dados
"""Gera etiquetas de mala-direta em PDF 

   - O texto será redimensionado(*) para preencher a etiqueta
     (*)Redimensionar significa reduzir o tamanho da fonte
  
   - Para adicionar um novo modelo de etiqueta, insira um dicionário com as dimensões na tupla LABELS

   Author: OpenLegis <contato@openlegis.com.br>

"""
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch, cm, mm, pica
from reportlab.lib import pagesizes
from types import *
import string
import time, os
from io import BytesIO

Error = "Erro nas etiquetas"
Error2 = "Erro nas etiquetas"

#Para adicionar um modelo de etiqueta, inclua neste dicionário 
LABELS = ({'cia':'test',
	   'models': ['9999'],
	   'paper': pagesizes.letter,
	   'columns': 4,
	   'rows': 9,
	   'height': 2.5,
	   'width': 4,
	   'topMargin': 1,
	   'lateralMargin': .5,   #you may define a leftMargin and rightMargin
	   'verticalSpacing': .25,  #defaults to 0
	   'horizontalSpacing': .25,#defaults to 0
	   'horizontalPadding':.5,  #defaults to +/- 7% of width
	   'verticalPadding': .5,   #defaults to +/- 7% of height
	   'units': cm,           #defaults to mm
	   },
          {'cia':'Pimaco',
	   'models': ['4354'],
	   'paper': pagesizes.A4,
	   'topMargin': 0.88,
	   'bottomMargin': 0.88,
	   'lateralMargin': 0.47,
	   'leftMargin': 0.47,
	   'rightMargin': 0.47,
	   'columns': 2,
	   'rows': 11,
	   'height': 2.54,
	   'width': 9.90,
	   'verticalPadding': .5,
	   'units': cm,
	   },
          {'cia':'Pimaco', #veja dimensões para Corel no site www.pimaco.com.br
	   'models': ['6081','6181','6281','0081','62581','62681'],
	   'paper': pagesizes.letter,
	   'topMargin': 1.27,
	   'bottomMargin': 1.27,
	   'lateralMargin': 0.377,
	   'leftMargin': 0.377,
	   'rightMargin': 0.377,
	   'columns': 2,
	   'rows': 10,
	   'height': 2.54,
	   'width': 10.16,
	   'units': cm,
	   },
	  {'cia':'Pimaco',
	   'models': ['6080','6180','6280','0080','62580','62680',],
	   'paper': pagesizes.letter,
	   'topMargin': 1.27,
	   'lateralMargin': 0.48,
	   'columns': 3,
	   'rows': 10,
	   'height': 2.54,
	   'width': 6.67,
	   'verticalSpacing': 0,
	   'horizontalSpacing': 0.31,
	   'horizontalPadding':.25,
	   'verticalPadding': .5,
	   'units': cm,
	   },
	  {'cia':'Pimaco',
	   'models': ['6082','6182','6282','0082','62582','62682',],
	   'paper': pagesizes.letter,
	   'topMargin': 2.12,
	   'bottomMargin': 2.12,
	   'lateralMargin': 0.377,
	   'leftMargin': 0.377,
	   'rightMargin': 0.377,
	   'verticalSpacing': 0,
	   'horizontalSpacing': 0.516,
	   'columns': 2,
	   'rows': 7,
	   'height': 3.39,
	   'width': 10.16,
	   'units': cm,
	   },
	  {'cia':'Pimaco',
	   'models': ['6183'],
	   'paper': pagesizes.letter,
	   'topMargin': 1.27,
	   'bottomMargin': 1.27,
	   'lateralMargin': 0.377,
	   'verticalSpacing': 0,
	   'horizontalSpacing': 0.516,
	   'columns': 2,
	   'rows': 5,
	   'height': 5.08,
	   'width': 10.16,
	   'units': cm,
	   },
	  )

class LabelGenerator():
    smallestFont = 5
    def __init__(self, spec):
        self.cia = spec['cia']
        self.models = spec['models']
        self.paper = spec['paper']
        self.cols = spec['columns']
        self.rows = spec['rows']

        self.un = self.units = spec.get('units', cm)

        self.topMargin = spec['topMargin'] * self.un
        self.leftMargin = spec.get('leftMargin', spec['lateralMargin']) * self.un
        self.rightMargin = spec.get('rightMargin', spec['lateralMargin']) * self.un

        self.height = spec['height'] * self.un
        self.width = spec['width'] * self.un

        self.vertSpacing = spec.get('verticalSpacing', 0) * self.un
        self.horizSpacing = spec.get('horizontalSpacing', 0) * self.un
        
        self.font = "Helvetica"
        self.size = 7
        self.leadingFactor = 1.2
        try:
            self.vertPadding = spec['verticalPadding'] * self.un
        except KeyError: 
            self.vertPadding = self.height//15
        try:
            self.horizPadding = spec['horizontalPadding'] * self.un
        except KeyError: 
            self.horizPadding = self.width//15
            
        self.maxTextWidth = self.width - 2 * self.horizPadding
        self.maxTextHeight = self.height - 2 * self.vertPadding

        self.grid = 0

    def start(self, filename):
        self.canvas = canvas.Canvas(filename, self.getPageSize())
        if hasattr(self, 'compress'):
           self.canvas.setPageCompression(self.compress)
        self.canvas.setFont(self.font, self.size, 
			    self.leadingFactor * self.size)
        self.pos = 0
        
    def setCompression(self):
        self.compress = 1

    def setVerticalPadding(self, value):
        self.vertPadding = value
    def setHorizontalPadding(self, value):
        self.horizPadding = value

    def fit(self, pdf, text):
        if type(text) is str:
            t = text.split('\n')
        else:
            t = text
        f = None
        fontSize = self.size
        while fontSize >= self.smallestFont:
            try:
                modifiedText = self.fitHorizontal(t, fontSize, f)
                textHeight = self.fitVertical(modifiedText, fontSize)
                pdf.setFont(self.font, fontSize, 
                            self.leadingFactor * fontSize)
                pdf.moveCursor(0, fontSize) 
                pdf.moveCursor(0, (self.maxTextHeight - textHeight)//2)
                pdf.textLines(modifiedText)
                return
            except:
                fontSize = fontSize -1
        raise Exception(Error, "O texto não coube na etiqueta. Reduza o texto ou use uma etiqueta maior \n" + repr(text) + " " + repr(self.smallestFont) + " " + repr(fontSize))

    def fitHorizontal(self, t, fontSize, debugFile=None):
        modifiedText = []
        for line in t:
            if debugFile: 
               debugFile.write(line+"\n")
               debugFile.flush()
            modifiedText = modifiedText + self.adaptHorizontal(line, fontSize, debugFile)
        modifiedText = t
        return modifiedText
        
    def adaptHorizontal(self, line, fontSize, debugFile):
        if line == '': return [''] 
        words = line.split()
        pos = len(words)
        while pos > 0:
            width = self.canvas.stringWidth(' '.join(words[:pos]), self.font, fontSize)
            if debugFile:
                debugFile.write(repr(width) + ":" + repr(self.maxTextWidth) +"\n")
                debugFile.flush()
            if width > self.maxTextWidth:
                pos = pos - 1
            elif pos == len(words):
                return [' '.join(words[:pos])]
            else:
                pass
                return ([' '.join(words[:pos])] +
                        self.adaptHorizontal(' '.join(words[:pos]), fontSize, debugFile))
        raise ValueError('Espaço horizontal. O texto não coube nas etiquetas. Reduza o texto ou use uma etiqueta maior')

    def fitVertical(self, text, fontSize):
        numLines = len(text)
        textHeight = (self.leadingFactor * fontSize  * numLines - 
                       (self.leadingFactor - 1.1) * fontSize)
        if textHeight > self.maxTextHeight:
           raise ValueError('Dados excedem a altura das etiquetas')
        return textHeight
            
    def getPageSize(self):
        try:
            return self.paper
        except KeyError:
            raise ValueError('Tamanho de página não reconhecido')
        
    def getPageX(self):
        return self.paper[0] 
    def getPageY(self):
        return self.paper[1] 

    def getCoordinates(self):
        x0 = self.leftMargin 
        y0 = self.getPageY() - self.topMargin

        col = self.pos % self.cols
        row = self.pos // self.cols

        x = x0 + col * (self.width + self.horizSpacing) + self.horizPadding
        y = y0 - row * (self.height - self.vertSpacing) - self.vertPadding

        return x, y
        
    def nextPos(self):
        self.pos = (self.pos + 1)
        if self.pos != self.pos % (self.cols * self.rows):
            self.canvas.showPage()
            self.pos = self.pos % (self.cols * self.rows)
            if self.grid:
               self.drawGrid()

    def generate(self, dados, filename):
        self.start(filename)
        if self.grid:
           self.drawGrid()
           self.drawDistances()
        for i in dados:
            pos = 0
            x, y = self.getCoordinates()
            t = self.canvas.beginText(x, y)
            self.fit(t, i)
            #print((t.getX()/cm, t.getY()/cm, self.paper[1] - t.getY()/cm))
            self.canvas.drawText(t)
            pos = self.nextPos()
        self.canvas.save()
        
    def setGrid(self, turnOn=0):
        self.grid = turnOn

    def drawGrid(self):
        borderX = [] 
        borderY = []
        frameX = [] 
        frameY = []        
        bx = self.leftMargin
        by = self.getPageY() - self.topMargin
        borderX.append(bx)
        borderY.append(by)
        fx = bx + self.horizPadding
        fy = by - self.vertPadding
        frameX.append(fx)
        frameY.append(fy)
        for j in range(self.cols):
              bx = bx + self.width
              borderX.append(bx)
              bx = bx + self.horizSpacing
              borderX.append(bx)              
              fx = fx + self.width 
              frameX.append(fx - 2 * self.horizPadding)
              if j != self.cols-1:
                 fx = fx + self.horizSpacing
                 frameX.append(fx)
        for i in range(self.rows):
            by = by - self.height
            borderY.append(by)
            by = by - self.vertSpacing
            borderY.append(by)
            
            fy = fy - self.height
            frameY.append(fy + 2 * self.vertPadding)
            if i != self.rows - 1:
               fy = fy - self.vertSpacing
               frameY.append(fy)
        self.canvas.grid(borderX, borderY)
        #self.canvas.setStrokeGray(.75)
        self.canvas.grid(frameX, frameY)
        self.canvas.setStrokeGray(0)

    def drawDistances(self):
        halfX = self.paper[0]//2
        halfY = self.paper[1]//2
        marginY = self.paper[1]-self.topMargin
        marginX = self.leftMargin
        #top border
        self.canvas.line(halfX, self.paper[1], halfX, marginY)
        self.canvas.line(marginX//2, self.paper[1], marginX//2, marginY)
        self.canvas.line(self.paper[0]-marginX//2, self.paper[1], self.paper[0]-marginX//2, marginY)
        #left border
        self.canvas.line(0, halfY, marginX, halfY)
        self.canvas.line(0, self.paper[1]-self.topMargin//2, marginX, self.paper[1]-self.topMargin//2)
        self.canvas.line(0, self.topMargin//2, marginX, self.paper[1]-marginY//2)


def findLabel(cia, labelsPerPage=None):
    found = []
    for spec in LABELS:
        if spec['cia'].lower() == cia.lower():
           if ((labelsPerPage is None) or 
              (labelsPerPage == spec['rows']*spec['columns'])):
                 found.append(spec)
    return found

def labelTypes():
    lt = {}
    for spec in LABELS:
        t = lt.get(spec['cia'], [])
        for i in spec['models']:
            t.append((i, repr(spec['columns']) + 'x' + repr(spec['rows'])))
        lt[spec['cia']] = t
    return lt

def factory(cia, model):
    for spec in LABELS:
        if spec['cia'].lower() == cia.lower():
           if model in spec['models']:
              return LabelGenerator(spec)
    raise ValueError('Modelo de etiqueta não encontrado')

def gera_etiqueta(self, dados):
    labels = factory("Pimaco", "6281")
    filename=str(int(time.time()*100))+".pdf"
    packet = BytesIO()
    labels.setGrid()
    labels.generate(dados, packet)
    packet.seek(0)
    content = packet.getvalue()
    self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
    self.REQUEST.RESPONSE.setHeader('Content-disposition','inline; filename="%s"' % filename)
    return content
