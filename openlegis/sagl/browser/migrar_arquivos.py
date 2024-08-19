# -*- coding: utf-8 -*-
from io import BytesIO
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import json
import MySQLdb
import requests
from requests.auth import HTTPBasicAuth

class migrarArquivos(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('migrar_arquivos')

    migrate = None
    base_url = 'http://localhost:8180/sagl/'

    db = MySQLdb.connect(host="localhost", user="sagl", passwd="sagl", db="openlegis")
    basic = HTTPBasicAuth('admin', 'gisla1978')

    def publishTraverse(self, request, name):
        if not hasattr(self, 'subpath'):
            self.subpath = []
        self.subpath.append(name)
        for index, value in enumerate(self.subpath):
            if value == "migrate" and index < len(self.subpath) - 1:
               next_element = self.subpath[index + 1]
               self.migrate = next_element
        return self

    def help(self):

        lst_tipos = []

        dic = {
           'Documentos Assinados': 'assinados',
           'Documentos Administrativos': 'administrativo',
           'Documentos Administrativos - tramitação': 'administrativo_tram',
           'Emendas': 'emenda',
           'Matérias Legislativas': 'materia',
           'Matérias Legislativas - acessórios': 'materia_doc',
           'Matérias Legislativas - tramitações': 'materia_tram',
           'Normas Jurídicas PDF': 'norma',
           'Normas Jurídicas compiladas': 'norma_compilada',
           'Normas Jurídicas ODT': 'norma_odt',
           'Normas Jurídicas anexos': 'norma_anexo',
           'Pareceres': 'parecer',
           'Petições': 'peticao',
           'Proposições': 'proposicao',
           'Proposições Assinadas': 'proposicao_signed',
           'Proposições ODT': 'proposicao_odt',
           'Protocolo': 'protocolo',
           'Reuniões Comissões - atas': 'reuniao_ata',
           'Reuniões Comissões - pautas': 'reuniao_pauta',
           'Sessões Plenárias - atas': 'sessao_ata',
           'Sessões Plenárias - pautas': 'sessao_pauta',
           'Substitutivos': 'substitutivo',
        }

        lst_tipos.append(dic)     

        dic_items = {
            "Versão 4": { 
                "urlOrigem":  self.base_url,
            },
            "exemplo": { 
                "urlExemplo":  self.service_url + '/migrate/assinados',
            },
            "rotina": {
                "migrate": lst_tipos,
            }
        }
        return dic_items

    def migrarAdm(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_documento FROM documento_administrativo WHERE ind_excluido=0 ORDER BY cod_documento')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_texto_integral.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.administrativo
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/administrativo/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarAdmTram(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_tramitacao FROM tramitacao_administrativo WHERE ind_excluido=0 ORDER BY cod_tramitacao')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_tram.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.administrativo.tramitacao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/administrativo/tramitacao/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarNormas(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_norma FROM norma_juridica WHERE ind_excluido=0 ORDER BY cod_norma')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_texto_integral.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.norma_juridica
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/norma_juridica/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarAnexoNorma(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_norma, cod_anexo FROM anexo_norma WHERE ind_excluido=0 ORDER BY cod_norma')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_anexo_' + str(row[1]) 
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.norma_juridica
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/norma_juridica/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
                arq = getattr(caminho, item)
                arq.manage_edit(title=item, content_type='application/pdf')         
             convertidos.append(item)
      return convertidos


    def migrarNormasODT(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_norma FROM norma_juridica WHERE ind_excluido=0 ORDER BY cod_norma')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_texto_integral.odt'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.norma_juridica
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/norma_juridica/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarNormasCompiladas(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_norma FROM norma_juridica WHERE ind_excluido=0 ORDER BY cod_norma')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_texto_consolidado.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.norma_juridica
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/norma_juridica/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarLeg(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_materia FROM materia_legislativa WHERE ind_excluido=0 ORDER BY cod_materia')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_texto_integral.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.materia
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/materia/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarLegAcessorio(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_documento FROM documento_acessorio WHERE ind_excluido=0 ORDER BY cod_documento')
      for row in cur.fetchall():
          row_id = str(row[0]) + '.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.materia
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/materia/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarEmendas(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_emenda FROM emenda WHERE ind_excluido=0 ORDER BY cod_emenda')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_emenda.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.emenda
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/emenda/' + item
          response = requests.get(url)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarSubstitutivos(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_substitutivo FROM substitutivo WHERE ind_excluido=0 ORDER BY cod_substitutivo')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_substitutivo.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.substitutivo
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/substitutivo/' + item
          response = requests.get(url)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarPareceres(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_relatoria FROM relatoria WHERE ind_excluido=0 ORDER BY cod_relatoria')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_parecer.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.parecer_comissao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/parecer_comissao/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarLegTram(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_tramitacao FROM tramitacao WHERE ind_excluido=0 ORDER BY cod_tramitacao')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_tram.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.materia.tramitacao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/materia/tramitacao/' + item
          response = requests.get(url)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarAtas(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_sessao_plen FROM sessao_plenaria WHERE ind_excluido=0 ORDER BY cod_sessao_plen')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_ata_sessao.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.ata_sessao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/ata_sessao/' + item
          response = requests.get(url)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarPautas(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_sessao_plen FROM sessao_plenaria WHERE ind_excluido=0 ORDER BY cod_sessao_plen')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_pauta_sessao.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.pauta_sessao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/pauta_sessao/' + item
          response = requests.get(url)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarPeticao(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_peticao FROM peticao WHERE ind_excluido=0 ORDER BY cod_peticao')
      for row in cur.fetchall():
          row_id = str(row[0]) + '.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.peticao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/peticao/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos       

    def migrarProposicao(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_proposicao FROM proposicao WHERE ind_excluido=0 ORDER BY cod_proposicao')
      for row in cur.fetchall():
          row_id = str(row[0]) + '.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.proposicao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/proposicao/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarProposicaoODT(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_proposicao FROM proposicao WHERE dat_envio IS NULL AND ind_excluido=0 ORDER BY cod_proposicao')
      for row in cur.fetchall():
          row_id = str(row[0]) + '.odt'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.proposicao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/proposicao/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarProposicaoAssinada(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_proposicao FROM proposicao WHERE ind_excluido=0 ORDER BY cod_proposicao')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_signed.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.proposicao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/proposicao/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarAssinados(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_assinatura_doc FROM assinatura_documento WHERE ind_assinado=1 ORDER BY id')
      for row in cur.fetchall():
          row_id = str(row[0]) + '.pdf'
          items.append(row_id)
      caminho = self.context.sapl_documentos.documentos_assinados
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/documentos_assinados/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarProtocolo(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_protocolo FROM protocolo ORDER BY cod_protocolo')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_protocolo.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.protocolo
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/protocolo/' + item
          response = requests.get(url, auth=self.basic)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarAtaComissao(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_reuniao FROM reuniao_comissao WHERE ind_excluido=0 ORDER BY cod_reuniao')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_ata.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.reuniao_comissao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/reuniao_comissao/' + item
          response = requests.get(url)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def migrarPautaComissao(self):
      items = []
      cur = self.db.cursor()
      cur.execute('SELECT cod_reuniao FROM reuniao_comissao WHERE ind_excluido=0 ORDER BY cod_reuniao')
      for row in cur.fetchall():
          row_id = str(row[0]) + '_pauta.pdf'
          items.append(row_id)
      
      caminho = self.context.sapl_documentos.reuniao_comissao
      convertidos = []
      for item in items:
          url = self.base_url + 'sapl_documentos/reuniao_comissao/' + item
          response = requests.get(url)
          if str(response.status_code) == '200':
             contents = BytesIO(response.content)
             if hasattr(caminho,item):
                arq = getattr(caminho, item)
                arq.manage_upload(file=contents)
             else:
                caminho.manage_addFile(id=item,file=contents)
             convertidos.append(item)
      return convertidos

    def render(self):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url()
        self.service_url = self.portal_url + '/@@migrar_arquivos'
        data = {
           '@id':  self.service_url,
           'description':  'Endpoints para migração de arquivos',
        }

        if self.migrate and self.migrate == 'assinados':
           return self.migrarAssinados()
        elif self.migrate and self.migrate == 'administrativo':
           return self.migrarAdm()
        elif self.migrate and self.migrate == 'administrativo_tram':
           return self.migrarAdmTram()
        elif self.migrate and self.migrate == 'emenda':
           return self.migrarEmendas()
        elif self.migrate and self.migrate == 'materia':
           return self.migrarLeg()
        elif self.migrate and self.migrate == 'materia_doc':
           return self.migrarLegAcessorio()
        elif self.migrate and self.migrate == 'materia_tram':
           return self.migrarLegTram()
        elif self.migrate and self.migrate == 'norma':
           return self.migrarNormas()
        elif self.migrate and self.migrate == 'norma_compilada':
           return self.migrarNormasCompiladas()
        elif self.migrate and self.migrate == 'norma_odt':
           return self.migrarNormasODT()
        elif self.migrate and self.migrate == 'norma_anexo':
           return self.migrarAnexoNorma()
        elif self.migrate and self.migrate == 'parecer':
           return self.migrarPareceres()
        elif self.migrate and self.migrate == 'peticao':
           return self.migrarPeticao()
        elif self.migrate and self.migrate == 'proposicao':
           return self.migrarProposicao()
        elif self.migrate and self.migrate == 'proposicao_signed':
           return self.migrarProposicaoAssinada()
        elif self.migrate and self.migrate == 'proposicao_odt':
           return self.migrarProposicaoODT()
        elif self.migrate and self.migrate == 'protocolo':
           return self.migrarProtocolo()
        elif self.migrate and self.migrate == 'reuniao_ata':
           return self.migrarAtaComissao()
        elif self.migrate and self.migrate == 'reuniao_pauta':
           return self.migrarPautaComissao()
        elif self.migrate and self.migrate == 'sessao_ata':
           return self.migrarAtas()
        elif self.migrate and self.migrate == 'sessao_pauta':
           return self.migrarPautas()
        elif self.migrate and self.migrate == 'substitutivo':
           return self.migrarSubstitutivos()
        else:
            data.update(self.help())
            serialized = json.dumps(data, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
            return(serialized.decode())
