# -*- coding: utf-8 -*-
import re
import os
import requests
from lxml.builder import ElementMaker
from lxml import etree
from typing import Iterator, Optional
from datetime import datetime
from DateTime import DateTime
from AccessControl.class_init import InitializeClass
from OFS.SimpleItem import SimpleItem
from Products.CMFCore.ActionProviderBase import ActionProviderBase
from Products.CMFCore.utils import UniqueObject
from zope.interface import Interface
from zope.interface import implementer
from Products.CMFCore.utils import getToolByName
from io import BytesIO
from PIL import Image
from appy.pod.renderer import Renderer
import pymupdf
pymupdf.TOOLS.set_aa_level(0)
import pikepdf
import fitz
from barcode import generate
from barcode.writer import ImageWriter
#imports para assinatura digital
import base64
from zlib import crc32
import json
from openlegis.sagl.restpki import *
from zope.testbrowser.browser import Browser
browser = Browser()
## Troca de senha
from AccessControl.SecurityInfo import ClassSecurityInfo
security = ClassSecurityInfo()
from AccessControl import Permissions
from AccessControl.Permission import addPermission
from AccessControl.SecurityInfo import ModuleSecurityInfo
security2 = ModuleSecurityInfo('Products.CMFCore.permissions')
security2.declarePublic('mailPassword')
mailPassword = 'Mail forgotten password'
addPermission(mailPassword, ('Anonymous', 'Manager',))
from Acquisition import aq_base
import logging
import tasks
import qrcode
import pypdf
from pypdf.errors import PdfReadError
from dateutil.parser import parse
from asn1crypto import cms
import warnings
import re # Para format_cpf
CPF_LENGTH = 11

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ISAGLTool(Interface):
    """ Marker interface for SAGL Tool.
    """
    pass

@implementer(ISAGLTool)
class SAGLTool(UniqueObject, SimpleItem, ActionProviderBase):
    id = 'portal_sagl'
    meta_type = 'SAGL Tool'
    XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
    ns = {'lexml': 'http://www.lexml.gov.br/oai_lexml'}
    schema = {'oai_lexml': 'http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd'}

    def verifica_esfera_federacao(self):
        """
        Função para verificar a esfera da federação.
        Retorna 'M' para municipal, 'E' para estadual e '' para desconhecido.
        """
        nome_camara = getattr(self.sapl_documentos.props_sagl, 'nom_casa', '') #Pega o valor ou retorna "" caso nao exista
        nome_camara_lower = nome_camara.lower() #Transforma o nome da camara em lower case para comparação

        camara = ['câmara', 'camara']
        assembleia = ['assembleia']

        if any(nome_camara_lower.startswith(tipo) for tipo in camara):
            return 'M'
        elif any(nome_camara_lower.startswith(tipo) for tipo in assembleia):
            return 'E'
        else:
            return ''

    def monta_id(self, cod_norma):
        """
        Função que monta o id do objeto do LexML.
        """
        try:
            consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)
            if not consulta:
                return None
            consulta = consulta[0]
            end_web_casa = self.sapl_documentos.props_sagl.end_web_casa
            sgl_casa = self.sapl_documentos.props_sagl.sgl_casa.lower()
            numero_interno = consulta.num_norma
            tipo_norma = consulta.voc_lexml
            ano_norma = consulta.ano_norma
            prefixo_oai = self._monta_prefixo_oai(end_web_casa, sgl_casa)
            identificador = f"{prefixo_oai}{tipo_norma};{ano_norma};{numero_interno}"
            return identificador
        except Exception as e:
            print(f"Erro ao montar ID LexML: {e}")
            return None

    def _monta_prefixo_oai(self, end_web_casa, sgl_casa):
        """
        Função auxiliar para montar o prefixo OAI.
        """
        partes_endereco = end_web_casa.split('.')
        dominio = '.'.join(partes_endereco[1:])
        return f"{sgl_casa}.{dominio}:sagl/"

    def _limpar_nome_localidade(nome):
        """Limpa o nome da localidade, removendo espaços e artigos."""
        nome = nome.lower().replace(" ", ".")
        artigos = [r'\.de\.', r'\.da\.', r'\.das\.', r'\.do\.', r'\.dos\.']
        for artigo in artigos:
            if re.search(artigo, nome):
                nome = re.sub(artigo, '.', nome)
        return nome

    def _converter_data_iso(self, data):
        """Converte a data para o formato ISO 8601."""
        return self.pysc.port_to_iso_pysc(data)

    def monta_urn(self, cod_norma):
        """Monta a URN do LexML."""
        consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)
        if not consulta:
            return None
        consulta = consulta[0]
        localidade = self.zsql.localidade_obter_zsql(cod_localidade=self.sapl_documentos.props_sagl.cod_localidade)[0]
        uf = _limpar_nome_localidade(self.zsql.localidade_obter_zsql(sgl_uf=localidade.sgl_uf, tip_localidade='U')[0].nom_localidade_pesq)
        municipio = _limpar_nome_localidade(localidade.nom_localidade_pesq)
        urn = f"urn:lex:br;{uf}"
        if self.verifica_esfera_federacao() == 'M':
            urn += f";{municipio}"
        urn += ":"
        if self.verifica_esfera_federacao() == 'M' and consulta.voc_lexml in ('regimento.interno', 'resolucao'):
            urn += "camara.municipal:"
        else:
            urn += {'M': 'municipal', 'E': 'estadual'}.get(self.verifica_esfera_federacao(), '') + ":"
        urn += f"{consulta.voc_lexml}:{_converter_data_iso(self, consulta.dat_norma)};"
        urn += consulta.ano_norma if consulta.voc_lexml in ('lei.organica', 'constituicao') else consulta.num_norma
        if consulta.dat_vigencia and consulta.dat_publicacao:
            urn += f"@{_converter_data_iso(self, consulta.dat_vigencia)};publicacao;{_converter_data_iso(self, consulta.dat_publicacao)}"
        elif consulta.dat_publicacao:
            urn += f"@inicio.vigencia;publicacao;{_converter_data_iso(self, consulta.dat_publicacao)}"
        return urn

    def monta_xml(self, urn, cod_norma):
        """Gera XML LexML para uma norma jurídica."""
        consulta = self.zsql.lexml_normas_juridicas_obter_zsql(cod_norma=cod_norma)
        publicador = self.zsql.lexml_publicador_obter_zsql()
        localidade_info = self.zsql.localidade_obter_zsql(cod_localidade=self.sapl_documentos.props_sagl.cod_localidade)
        if not (consulta and publicador and localidade_info):
            return None  # Tratar falta de dados
        consulta = consulta[0]
        publicador = publicador[0]
        localidade = localidade_info[0].nom_localidade
        sigla_uf = localidade_info[0].sgl_uf
        url = f"{self.portal_url()}/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma={cod_norma}"
        E = ElementMaker()
        LEXML = ElementMaker(namespace=self.ns['lexml'], nsmap=self.ns)
        oai_lexml = LEXML.LexML()
        oai_lexml.attrib['{%s}schemaLocation' % self.XSI_NS] = '%s %s' % (
            'http://www.lexml.gov.br/oai_lexml',
            'http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd',
        )
        id_publicador = str(publicador.id_publicador)
        # Construção da epígrafe
        if consulta.voc_lexml == 'lei.organica':
            epigrafe = f"{consulta.des_tipo_norma} de {localidade} - {sigla_uf}, de {consulta.ano_norma}"
        elif consulta.voc_lexml == 'constituicao':
            epigrafe = f"{consulta.des_tipo_norma} do Estado de {localidade}, de {consulta.ano_norma}"
        else:
            epigrafe = f"{consulta.des_tipo_norma} n° {consulta.num_norma}, de {self.pysc.data_converter_por_extenso_pysc(consulta.dat_norma)}"
        ementa = consulta.txt_ementa
        indexacao = consulta.txt_indexacao
        formato = 'text/html'
        id_documento = f"{cod_norma}_{self.sapl_documentos.norma_juridica.nom_documento}"
        if hasattr(self.sapl_documentos.norma_juridica, id_documento):
            arquivo = getattr(self.sapl_documentos.norma_juridica, id_documento)
            url_conteudo = arquivo.absolute_url()
            formato = arquivo.content_type
            if formato == 'application/octet-stream':
                formato = 'application/msword'
            elif formato == 'image/ipeg':
                formato = 'image/jpeg'
        else:
            url_conteudo = f"{self.portal_url()}/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma={cod_norma}"
        item_conteudo = E.Item(url_conteudo, formato=formato, idPublicador=id_publicador, tipo='conteudo')
        oai_lexml.append(item_conteudo)
        item_metadado = E.Item(url, formato='text/html', idPublicador=id_publicador, tipo='metadado')
        oai_lexml.append(item_metadado)
        documento_individual = E.DocumentoIndividual(urn)
        oai_lexml.append(documento_individual)
        oai_lexml.append(E.Epigrafe(epigrafe))
        oai_lexml.append(E.Ementa(ementa))
        if indexacao:
            oai_lexml.append(E.Indexacao(indexacao))
        return etree.tostring(oai_lexml, encoding='utf-8')

    def oai_query(
        self,
        offset: int = 0,
        batch_size: int = 20,
        from_date: Optional[datetime] = None,
        until_date: Optional[datetime] = None,
        identifier: Optional[str] = None,
    ) -> Iterator[dict]:
        """
        Consulta normas jurídicas e gera resultados formatados para OAI-PMH.
        Args:
            offset (int, opcional): O deslocamento inicial para a consulta. Padrão é 0.
            batch_size (int, opcional): O número de registros a serem recuperados por lote. Padrão é 20.
            from_date (datetime.datetime ou None, opcional): A data de início para a consulta. Padrão é None.
            until_date (datetime.datetime ou None, opcional): A data de término para a consulta. Padrão é None.
            identifier (str ou None, opcional): Um identificador de norma específico para filtrar. Padrão é None.
        Yields:
            dict: Um dicionário contendo o registro e os metadados, formatados para OAI-PMH.
                  Exemplo:
                  {
                      'record': {
                          'tx_metadado_xml': '<xml>...</xml>',
                          'cd_status': 'N',
                          'id': '...',
                          'when_modified': datetime.datetime(...),
                          'deleted': 0 ou 1
                      },
                      'metadata': '<xml>...</xml>'
                  }
        """
        # Obtém a esfera de federação das normas.
        esfera = self.verifica_esfera_federacao()
        # Garante que o tamanho do lote seja válido.
        if batch_size < 0:
            batch_size = 0
        # Ajusta a data de término se não for fornecida ou se for futura.
        if until_date is None or until_date > datetime.now():
            until_date = datetime.now()
        # Define a data de início como uma string vazia se não for fornecida.
        if from_date is None:
            from_date = ""
        # Consulta as normas jurídicas no banco de dados.
        normas = self.zsql.lexml_normas_juridicas_obter_zsql(
            from_date=from_date,
            until_date=until_date,
            offset=offset,
            batch_size=batch_size,
            num_norma=identifier,
            tip_esfera_federacao=esfera,
        )
        # Itera sobre as normas encontradas e formata os resultados.
        for norma in normas:
            resultado = {}
            cod_norma = norma.cod_norma
            identificador = self.monta_id(cod_norma)
            urn = self.monta_urn(cod_norma)
            xml_lexml = self.monta_xml(urn, cod_norma)
            resultado["tx_metadado_xml"] = xml_lexml
            resultado["cd_status"] = "N"  # Status 'N' para novo.
            resultado["id"] = identificador
            resultado["when_modified"] = norma.timestamp
            resultado["deleted"] = 0  # Padrão: não excluído.
            if norma.ind_excluido == 1:
                resultado["deleted"] = 1  # Marca como excluído.
            # Retorna o registro e os metadados formatados.
            yield {
                "record": resultado,
                "metadata": resultado["tx_metadado_xml"],
            }

    def create_barcode(self, numero_a_codificar):
        """
        Gera um código de barras Code128 a partir de um número inteiro.
        Args:
            numero_a_codificar: O número inteiro a ser codificado no código de barras.
        Returns:
           Um objeto bytes contendo os dados da imagem do código de barras em formato PNG.
        Raises:
            ValueError: Se o número fornecido não puder ser convertido em uma string de 7 dígitos.
        """
        try:
            texto_codigo_de_barras = str(numero_a_codificar).zfill(7)
            imagem_bytes = BytesIO()
            generate('Code128', texto_codigo_de_barras, writer=ImageWriter(), output=imagem_bytes)
            dados_imagem_codigo_de_barras = imagem_bytes.getvalue()
            return dados_imagem_codigo_de_barras
        except ValueError as e:
            raise ValueError(f"Erro ao gerar código de barras: {e}")
        except Exception as e:
            raise Exception(f"Erro inesperado: {e}")

    def url(self):
        """
        Retorna a URL base do portal.
        Este método recupera a URL do portal usando a ferramenta 'portal_url'.
        Retorna:
            str: A URL base do portal.
        """
        utool = getToolByName(self, 'portal_url')
        return utool.portal_url()

    def resize_and_crop(self, cod_parlamentar, size=(350, 350), crop_type='top'):
        """
        Redimensiona e recorta a foto de um parlamentar.

        Args:
            cod_parlamentar: O código do parlamentar.
            size: O tamanho desejado da imagem (largura, altura).
            crop_type: O tipo de recorte ('top', 'middle', 'bottom').
        """
        try:
            image_file = f"{cod_parlamentar}_foto_parlamentar"
            foto_obj = getattr(self.sapl_documentos.parlamentar.fotos, image_file)
            img_path = BytesIO(bytes(foto_obj.data))
            modified_path = BytesIO()
            img = Image.open(img_path)
            img = img.convert('RGB')
            img_ratio = img.size[0] / float(img.size[1])
            target_ratio = size[0] / float(size[1])
            if target_ratio > img_ratio:
                # Imagem muito alta, redimensiona a altura e recorta a largura
                new_height = int(round(size[0] * img.size[1] / img.size[0]))
                img = img.resize((size[0], new_height), Image.Resampling.LANCZOS)
                if crop_type == 'top':
                    box = (0, 0, img.size[0], size[1])
                elif crop_type == 'middle':
                    box = (0, int(round((img.size[1] - size[1]) / 2)), img.size[0],
                           int(round((img.size[1] + size[1]) / 2)))
                elif crop_type == 'bottom':
                    box = (0, img.size[1] - size[1], img.size[0], img.size[1])
                else:
                    crop_type = 'top'
                    box = (0, 0, img.size[0], size[1])
                img = img.crop(box)
            elif target_ratio < img_ratio:
                # Imagem muito larga, redimensiona a largura e recorta a altura
                new_width = int(round(size[1] * img.size[0] / img.size[1]))
                img = img.resize((new_width, size[1]), Image.Resampling.LANCZOS)
                if crop_type == 'top':
                    box = (0, 0, size[0], img.size[1])
                elif crop_type == 'middle':
                    box = (int(round((img.size[0] - size[0]) / 2)), 0,
                           int(round((img.size[0] + size[0]) / 2)), img.size[1])
                elif crop_type == 'bottom':
                    box = (img.size[0] - size[0], 0, img.size[0], img.size[1])
                else:
                    crop_type = 'top'
                    box = (0, 0, size[0], img.size[1])
                img = img.crop(box)
            else:
                # Proporções corretas, apenas redimensiona
                img = img.resize(size, Image.Resampling.LANCZOS)
            img.save(modified_path, format="PNG")
            modified_path.seek(0)
            content = modified_path.getvalue()
            foto_obj.update_data(content)

        except (AttributeError, FileNotFoundError, OSError) as e:
            print(f"Erro ao processar foto de {cod_parlamentar}: {e}")

    def get_brasao(self):
        """
        Recupera a imagem do brasão.
        Tenta buscar a imagem de sapl_documentos.props_sagl. Se não encontrar,
        usa o brasao.gif padrão de INSTALL_HOME.
        Retorna:
            bytes: Dados da imagem do brasão ou bytes vazios em caso de erro.
        """
        try:
            id_logo = self.sapl_documentos.props_sagl.id_logo
            arq = getattr(self.sapl_documentos.props_sagl, id_logo)
            return BytesIO(bytes(arq.data)).getvalue()
        except (AttributeError, KeyError):
            install_home = os.environ.get('INSTALL_HOME')
            if not install_home:
                print("Aviso: Variável INSTALL_HOME não definida.")
                return b''
            filepath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/brasao.gif')
            try:
                with open(filepath, "rb") as arq:
                    return arq.read()
            except FileNotFoundError:
                print(f"Aviso: Arquivo de brasão padrão não encontrado em: {filepath}")
                return b''

    def _armazenar_arquivo(self, **kwargs):
        """
        Armazena o arquivo odt gerado e define as permissões.
        Args:
           **kwargs:
                pasta:      O objeto onde o arquivo será armazenado.
                nome_arquivo: O nome do arquivo.
                odt_data:  conteúdo do arquivo.
                permissions:  Um dicionário contendo as permissões a serem aplicadas.
        """
        pasta = kwargs.get('pasta')
        odt_data = kwargs.get('odt_data')
        nome_arquivo = kwargs.get('nome_arquivo')
        permissions = kwargs.get('permissions')
        pasta.manage_addFile(id=nome_arquivo, file=odt_data)
        odt = getattr(pasta, nome_arquivo)
        if permissions:
             for permission_name, permission_config in permissions.items():
                odt.manage_permission(permission_name, **permission_config)

    def _enviar_arquivo_resposta(self, **kwargs):
        """
        Envia o arquivo gerado como resposta HTTP.
        Args:
            **kwargs:
                nome_arquivo: O nome do arquivo.
                dados_arquivo: Os dados do arquivo.
                tipo_conteudo:  O tipo de conteúdo do arquivo.
                disposicao_conteudo: A disposição do conteúdo (attachment, inline, etc.).
        """
        nome_arquivo = kwargs.get('nome_arquivo')
        dados_arquivo = kwargs.get('dados_arquivo')
        tipo_conteudo = kwargs.get('tipo_conteudo')
        disposicao_conteudo = kwargs.get('disposicao_conteudo')
        self.REQUEST.RESPONSE.headers['Content-Type'] = tipo_conteudo
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = f'{disposicao_conteudo}; filename="{nome_arquivo}"'
        return dados_arquivo

    def gerar_odt(self, **kwargs):
        """
        Gera um arquivo ODT.
        Args:
            **kwargs:
                modelo:         O modelo ODT a ser utilizado (pode ser um objeto ou um caminho).
                dicionario_dados: Dados para renderizar no template.
                nome_arquivo:   Nome do arquivo de saída ODT.
                pasta_destino:  Pasta para salvar o arquivo (opcional, se for salvar).
                permissions:    Permissões para o arquivo (opcional).
                tipo_conteudo:  Tipo de conteúdo para a resposta (se enviar por HTTP).
                disposicao_conteudo: Disposição do conteúdo (se enviar por HTTP).
                action:         Ação a ser executada com o arquivo (gerar, download, etc.).
                nom_arquivo_pdf: Nome do arquivo PDF de saída (se gerar PDF).
                modelo_path:    Caminho para o modelo (se necessário).
        """
        modelo = kwargs.pop('modelo', None)
        dicionario_dados = kwargs.pop('dicionario_dados', None)
        nome_arquivo = kwargs.pop('nome_arquivo', None)
        pasta_destino = kwargs.pop('pasta_destino', None)
        permissions = kwargs.pop('permissions', None)
        tipo_conteudo = kwargs.pop('tipo_conteudo', 'application/vnd.oasis.opendocument.text')
        disposicao_conteudo = kwargs.pop('disposicao_conteudo', 'attachment')
        action = kwargs.pop('action', None)
        nom_arquivo_pdf = kwargs.pop('nom_arquivo_pdf', None)
        modelo_path = kwargs.pop('modelo_path', None)
        # Obter o template
        if modelo:
            if isinstance(modelo, str):
                if modelo_path:
                    utool = getToolByName(self, 'portal_url')
                    portal = utool.getPortalObject()
                    modelo = portal.unrestrictedTraverse(modelo_path)
                template_file = BytesIO(bytes(modelo.data))
            else:
                template_file = BytesIO(bytes(modelo.data))  # Assuming modelo has 'data'
        else:
            raise ValueError("Parâmetro 'modelo' é obrigatório.")
        # Obter o brasão
        brasao = self.get_brasao()
        if dicionario_dados is None:
            dicionario_dados = {}
        dicionario_dados['brasao'] = brasao
        # Renderizar ODT
        renderer = Renderer(template_file, dicionario_dados, nome_arquivo, pythonWithUnoPath='/usr/bin/python3', forceOoCall=True)
        renderer.run()
        # Ler o arquivo gerado
        with open(nome_arquivo, "rb") as f:
            odt_data = f.read()
        os.unlink(nome_arquivo)
        # Manipular o arquivo (salvar ou enviar)
        if pasta_destino:
            self._armazenar_arquivo(
                pasta=pasta_destino,
                nome_arquivo=nome_arquivo,
                odt_data = odt_data,
                permissions=permissions,
            )
            odt = getattr(pasta_destino, nome_arquivo)  # Get the stored object
        elif not pasta_destino and not action:
            return self._enviar_arquivo_resposta(
                nome_arquivo=nome_arquivo,
                dados_arquivo=odt_data,
                tipo_conteudo=tipo_conteudo,
                disposicao_conteudo=disposicao_conteudo,
            )
        # Se action for 'gerar' ou 'download' e nom_arquivo_pdf existir, gerar PDF
        if action in ('gerar', 'download') and nom_arquivo_pdf:
            odtFile = BytesIO(odt_data)  # Use the odt_data we already read
            renderer_pdf = Renderer(odtFile, dicionario_dados, nom_arquivo_pdf, pythonWithUnoPath='/usr/bin/python3', forceOoCall=True)
            renderer_pdf.run()
            with open(nom_arquivo_pdf, 'rb') as f:
                pdf_data = BytesIO(f.read())
            os.unlink(nom_arquivo_pdf)
            if action == 'gerar':
                if hasattr(self.temp_folder, nom_arquivo_pdf):
                   self.temp_folder.manage_delObjects(ids=nom_arquivo_pdf)
                self.temp_folder.manage_addFile(id=nom_arquivo_pdf, file=pdf_data)
            elif action == 'download':
                return self._enviar_arquivo_resposta(
                    nome_arquivo=nom_arquivo_pdf,
                    dados_arquivo=pdf_data,
                    tipo_conteudo='application/pdf',
                    disposicao_conteudo='inline',
                )

    def ata_comissao_gerar_odt(self, ata_dic, nom_arquivo):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, "ata_comissao.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.reuniao_comissao,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def comunicado_emendas_gerar_odt(self, inf_basicas_dic, dic_materia, lst_vereadores, nom_presidente, modelo_comunicado):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo, modelo_comunicado),
            'dicionario_dados': locals(),
            'nome_arquivo': "comunicado-emendas.odt",
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)

    def carga_comissao_gerar(self, inf_basicas_dic, dic_materia, nom_comissao, presidente, vicepresidente, membro, suplente):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo, "carga_comissao.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': "carga_comissao.odt",
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)

    def iom_gerar_odt(self, inf_basicas_dic, lst_mesa, lst_presenca_sessao, lst_materia_apresentada, lst_reqplen, lst_reqpres, lst_indicacao, lst_presenca_ordem_dia, lst_votacao, lst_presenca_expediente, lst_oradores, lst_presenca_encerramento, lst_presidente, lst_psecretario, lst_ssecretario):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, "iom.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': "publicacao_iom.odt",
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)

    def materia_apreciada_gerar_odt(self, inf_basicas_dic, lst_votacao):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, "materia_apreciada.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': "materia_apreciada.odt",
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)

    def materia_apresentada_gerar_odt(self, inf_basicas_dic, lst_materia_apresentada):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, "materia_apresentada.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': "materia_apresentada.odt",
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)

    def ordem_dia_gerar_odt(self, inf_basicas_dic, nom_arquivo, nom_modelo):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, nom_modelo),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.pauta_sessao,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def oradores_gerar_odt(self, inf_basicas_dic, lst_oradores, lst_presidente, nom_arquivo):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, "oradores.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.oradores_expediente,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def expediente_gerar_odt(self, inf_basicas_dic, lst_indicacoes, lst_requerimentos, lst_mocoes, lst_oradores, lst_presidente, nom_arquivo):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, "expediente.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.pauta_sessao,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def resumo_gerar_odt(self, resumo_dic, nom_arquivo, nom_modelo):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, nom_modelo),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)

    def resumo_tramitacao_gerar_odt(self, inf_basicas_dic, num_protocolo, dat_protocolo, hor_protocolo, dat_vencimento, num_proposicao, des_tipo_materia, nom_autor, txt_ementa, regime_tramitacao, nom_arquivo):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.materia, "resumo-tramitacao.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)

    def doc_acessorio_gerar_odt(self, inf_basicas_dic, nom_arquivo, des_tipo_documento, nom_documento, txt_ementa, dat_documento, data_documento, nom_autor, materia_vinculada, modelo_proposicao):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.materia.documento_acessorio, modelo_proposicao),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.materia_odt,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def doc_acessorio_adm_gerar_odt(self, inf_basicas_dic, documento_dic, modelo_documento):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.documento_administrativo, modelo_documento),
            'dicionario_dados': locals(),
            'nome_arquivo': documento_dic['nom_arquivo'],
            'pasta_destino': self.sapl_documentos.administrativo,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)


    def oficio_ind_gerar_odt(self, inf_basicas_dic, lst_indicacao, lst_presidente):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, "oficio_indicacao.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': "oficio_indicacao.odt",
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)


    def oficio_req_gerar_odt(self, inf_basicas_dic, lst_requerimento, lst_presidente):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.sessao_plenaria, "oficio_requerimento.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': "oficio_requerimento.odt",
            'tipo_conteudo': 'application/vnd.oasis.opendocument.text',
            'disposicao_conteudo': 'attachment',
        }
        return self.gerar_odt(**kwargs)

    def emenda_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.materia.emenda, modelo_proposicao),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.emenda,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def capa_processo_gerar_odt(self, capa_dic, action):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.materia, "capa_processo.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': capa_dic['nom_arquivo_odt'],
            'nom_arquivo_pdf': capa_dic['nom_arquivo_pdf'],
            'action': action,
        }
        return self.gerar_odt(**kwargs)

    def capa_processo_adm_gerar_odt(self, capa_dic, action):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.documento_administrativo, "capa_processo_adm.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': capa_dic['nom_arquivo_odt'],
            'nom_arquivo_pdf': capa_dic['nom_arquivo_pdf'],
            'action': action
        }
        return self.gerar_odt(**kwargs)

    def capa_norma_gerar_odt(self, capa_dic, action):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.norma, "capa_norma.odt"),
            'dicionario_dados': locals(),
            'nome_arquivo': capa_dic['nom_arquivo_odt'],
            'nom_arquivo_pdf': capa_dic['nom_arquivo_pdf'],
            'action': action,
        }
        return self.gerar_odt(**kwargs)

    def materia_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, num_materia, ano_ident_basica, ano_materia, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, subscritores, modelo_proposicao):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.materia, modelo_proposicao),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.materia_odt,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)


    def norma_gerar_odt(self, inf_basicas_dic, nom_arquivo, des_tipo_norma, num_norma, ano_norma, dat_norma, data_norma, txt_ementa, modelo_norma):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.norma, modelo_norma),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.norma_juridica,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def oficio_gerar_odt(self, inf_basicas_dic, nom_arquivo, sgl_tipo_documento, num_documento, ano_documento, txt_ementa, dat_documento, dia_documento, nom_autor, modelo_documento):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.documento_administrativo, modelo_documento),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.administrativo,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def parecer_gerar_odt(self, inf_basicas_dic, nom_arquivo, nom_comissao, materia_vinculada, nom_autor, txt_ementa, tip_apresentacao, tip_conclusao, data_parecer, nom_relator, lst_composicao, modelo_proposicao):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.materia.parecer, modelo_proposicao),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.parecer_comissao,
            'permissions': {'View': {'roles': ['Manager', 'Operador', 'Operador Materia', 'Autor'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def peticao_gerar_odt(self, inf_basicas_dic, nom_arquivo, modelo_path):
        utool = getToolByName(self, 'portal_url')
        portal = utool.getPortalObject()
        kwargs = {
            'modelo': portal.unrestrictedTraverse(modelo_path),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.peticao,
            'permissions': {'View': {'roles': ['Manager', 'Owner'], 'acquire': 1}},
        }
        return self.gerar_odt(**kwargs)

    def _get_proposicao_image(self, num_proposicao, image_number):
        """
        Obtém os dados de uma imagem de proposição.
        Args:
            num_proposicao:  O número da proposição.
            image_number: O número da imagem (1, 2, 3 ou 4).
        Returns:
            Os dados da imagem ou uma string vazia se a imagem não existir.
        """
        id_image = f"{num_proposicao}_image_{image_number}.jpg"
        if hasattr(self.sapl_documentos.proposicao, id_image):
            arq = getattr(self.sapl_documentos.proposicao, id_image)
            with BytesIO(bytes(arq.data)) as content:
                return content.getvalue()
        else:
            return ''

    def get_proposicao_image_one(self, num_proposicao):
        return self._get_proposicao_image(num_proposicao, 1)

    def get_proposicao_image_two(self, num_proposicao):
        return self._get_proposicao_image(num_proposicao, 2)

    def get_proposicao_image_three(self, num_proposicao):
        return self._get_proposicao_image(num_proposicao, 3)

    def get_proposicao_image_four(self, num_proposicao):
        return self._get_proposicao_image(num_proposicao, 4)

    def proposicao_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, subscritores, modelo_proposicao, modelo_path):
        """
        Gera o arquivo ODT da proposição.
        Args:
            inf_basicas_dic: Dicionário com informações básicas da proposição.
            num_proposicao:  Número da proposição.
            nom_arquivo:   Nome do arquivo de saída ODT.
            des_tipo_materia: Descrição do tipo de matéria.
            num_ident_basica: Número de identificação básica.
            ano_ident_basica: Ano de identificação básica.
            txt_ementa:   Ementa da proposição.
            materia_vinculada: Matéria vinculada.
            dat_apresentacao: Data de apresentação.
            nom_autor:     Nome do autor.
            apelido_autor: Apelido do autor.
            subscritores:  Lista de subscritores.
            modelo_proposicao: Modelo da proposição.
            modelo_path:   Caminho para o modelo.
        """
        # Lógica para 'Parecer'
        if inf_basicas_dic['des_tipo_proposicao'] in ('Parecer', 'Parecer de Comissão'):
            materia = inf_basicas_dic['id_materia']
            nom_comissao = inf_basicas_dic['nom_comissao']
            data_parecer = inf_basicas_dic['data_parecer']
            nom_relator = inf_basicas_dic['nom_relator']
            lst_composicao = []  # Inicializar lst_composicao
        # Lógica para 'Requerimento' ou 'Indicação'
        image1 = ''
        image2 = ''
        image3 = ''
        image4 = ''
        if inf_basicas_dic['des_tipo_proposicao'] in ('Requerimento', 'Indicação'):
            image1 = self.get_proposicao_image_one(num_proposicao)
            image2 = self.get_proposicao_image_two(num_proposicao)
            image3 = self.get_proposicao_image_three(num_proposicao)
            image4 = self.get_proposicao_image_four(num_proposicao)
        utool = getToolByName(self, 'portal_url')
        portal = utool.getPortalObject()
        kwargs = {
            'modelo': portal.unrestrictedTraverse(modelo_path),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.proposicao,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}}
        }
        return self.gerar_odt(**kwargs)

    def substitutivo_gerar_odt(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, ano_ident_basica, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, modelo_proposicao):
        kwargs = {
            'modelo': getattr(self.sapl_documentos.modelo.materia.substitutivo, modelo_proposicao),
            'dicionario_dados': locals(),
            'nome_arquivo': nom_arquivo,
            'pasta_destino': self.sapl_documentos.substitutivo,
            'permissions': {'View': {'roles': ['Manager', 'Authenticated'], 'acquire': 0}},
        }
        return self.gerar_odt(**kwargs)

    def _gerar_e_armazenar_pdf(self, arq_odt, nom_arquivo_odt, nom_arquivo_pdf, destino, titulo, **kwargs):
        """
        Função auxiliar para converter ODT e armazenar arquivos PDF, utilizando kwargs e tratamento de erros.
        Args:
            self: Referência à instância da classe.
            arq_odt: Objeto contendo os dados do arquivo ODT.
            nom_arquivo_odt: Nome do arquivo ODT.
            nom_arquivo_pdf: Nome do arquivo PDF.
            destino: Objeto onde o PDF será armazenado (ex: self.sapl_documentos.ata_sessao).
            titulo: Título do arquivo PDF.
            **kwargs: Dicionário de argumentos adicionais para outras funções.
        """
        try:
            odtFile = BytesIO(bytes(arq_odt.data))
            renderer = Renderer(odtFile, locals(), nom_arquivo_pdf, pythonWithUnoPath='/usr/bin/python3', forceOoCall=True)
            renderer.run()
            with open(nom_arquivo_pdf, "rb") as pdf_file:
                content = pdf_file.read()
            os.unlink(nom_arquivo_pdf)
            upload_kwargs = {'file': self.pysc.upload_file(file=BytesIO(content), title=titulo)}
            upload_kwargs.update(kwargs.get('upload_kwargs', {}))
            destino.manage_addFile(id=nom_arquivo_pdf, **upload_kwargs)
        except Exception as e:
            # Logar o erro para depuração
            print(f"Erro ao gerar e armazenar PDF: {e}")  
            raise

    def ata_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = f"{cod_sessao_plen}_ata_sessao.odt"
        nom_arquivo_pdf = f"{cod_sessao_plen}_ata_sessao.pdf"
        arq = getattr(self.sapl_documentos.ata_sessao, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.ata_sessao, 'Ata')

    def ata_comissao_gerar_pdf(self, cod_reuniao):
        nom_arquivo_odt = f"{cod_reuniao}_ata.odt"
        nom_arquivo_pdf = f"{cod_reuniao}_ata.pdf"
        arq = getattr(self.sapl_documentos.reuniao_comissao, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.reuniao_comissao, 'Ata Comissão')

    def ordem_dia_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = f"{cod_sessao_plen}_pauta_sessao.odt"
        nom_arquivo_pdf = f"{cod_sessao_plen}_pauta_sessao.pdf"
        arq = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.pauta_sessao, 'Ordem do Dia')

    def oradores_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = f"{cod_sessao_plen}_oradores_expediente.odt"
        nom_arquivo_pdf = f"{cod_sessao_plen}_oradores_expediente.pdf"
        arq = getattr(self.sapl_documentos.oradores_expediente, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.oradores_expediente, 'Oradores')

    def expediente_gerar_pdf(self, cod_sessao_plen):
        nom_arquivo_odt = f"{cod_sessao_plen}_expediente.odt"
        nom_arquivo_pdf = f"{cod_sessao_plen}_expediente.pdf"
        arq = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.pauta_sessao, 'Pauta do Expediente')

    def doc_acessorio_gerar_pdf(self, cod_documento):
        nom_arquivo_odt = f"{cod_documento}.odt"
        nom_arquivo_pdf = f"{cod_documento}.pdf"
        arq = getattr(self.sapl_documentos.materia_odt, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.materia, 'Documento Acessório')

    def doc_acessorio_adm_gerar_pdf(self, cod_documento_acessorio):
        nom_arquivo_odt = f"{cod_documento_acessorio}.odt"
        nom_arquivo_pdf = f"{cod_documento_acessorio}.pdf"
        arq = getattr(self.sapl_documentos.administrativo, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.administrativo, 'Documento Acessório')

    def emenda_gerar_pdf(self, cod_emenda):
        nom_arquivo_odt = f"{cod_emenda}_emenda.odt"
        nom_arquivo_pdf = f"{cod_emenda}_emenda.pdf"
        arq = getattr(self.sapl_documentos.emenda, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.emenda, 'Emenda')

    def materia_gerar_pdf(self, cod_materia):
        nom_arquivo_odt = f"{cod_materia}_texto_integral.odt"
        nom_arquivo_pdf = f"{cod_materia}_texto_integral.pdf"
        arq = getattr(self.sapl_documentos.materia_odt, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.materia, 'Matéria')

    def redacao_final_gerar_pdf(self, cod_materia):
        nom_arquivo_odt = f"{cod_materia}_redacao_final.odt"
        nom_arquivo_pdf = f"{cod_materia}_redacao_final.pdf"
        arq = getattr(self.sapl_documentos.materia_odt, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.materia, 'Redação Final')

    def norma_gerar_pdf(self, cod_norma, tipo_texto):
        nom_arquivo_odt = f"{cod_norma}_texto_integral.odt"
        arq = getattr(self.sapl_documentos.norma_juridica, nom_arquivo_odt)
        odtFile = BytesIO(bytes(arq.data))
        if tipo_texto == 'compilado':
            nom_arquivo_pdf = f"{cod_norma}_texto_consolidado.pdf"
        elif tipo_texto == 'integral':
            nom_arquivo_pdf = f"{cod_norma}_texto_integral.pdf"
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.norma_juridica, 'Norma')

    def oficio_gerar_pdf(self, cod_documento):
        nom_arquivo_odt = f"{cod_documento}_texto_integral.odt"
        nom_arquivo_pdf = f"{cod_documento}_texto_integral.pdf"
        arq = getattr(self.sapl_documentos.administrativo, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.administrativo, 'Documento')

    def parecer_gerar_pdf(self, cod_parecer):
        nom_arquivo_odt = f"{cod_parecer}_parecer.odt"
        nom_arquivo_pdf = f"{cod_parecer}_parecer.pdf"
        arq = getattr(self.sapl_documentos.parecer_comissao, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.parecer_comissao, 'Parecer')
        pdf = getattr(self.sapl_documentos.parecer_comissao, nom_arquivo_pdf)
        pdf.manage_permission('View', roles=['Manager','Operador','Operador Materia','Autor'], acquire=0)

    def peticao_gerar_pdf(self, cod_peticao):
        nom_arquivo_odt = f"{cod_peticao}.odt"
        nom_arquivo_pdf = f"{cod_peticao}.pdf"
        arq = getattr(self.sapl_documentos.peticao, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.peticao, 'Petição')
        pdf = getattr(self.sapl_documentos.peticao, nom_arquivo_pdf)
        pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=1)

    def proposicao_gerar_pdf(self, cod_proposicao):
        merger = pymupdf.open()
        nom_arquivo_pdf = f"{cod_proposicao}.pdf"
        nom_arquivo_odt = f"{cod_proposicao}.odt"  # Keep for title purposes

        # Process the main ODT file
        arquivo_odt_obj = getattr(self.sapl_documentos.proposicao, nom_arquivo_odt)
        odt_content = BytesIO(bytes(arquivo_odt_obj.data))
        odt_content.seek(0)
        output_file_pdf_temp = f"temp_{nom_arquivo_pdf}"  # Temporary file for conversion
        renderer = Renderer(odt_content, locals(), output_file_pdf_temp, pythonWithUnoPath='/usr/bin/python3', forceOoCall=True)
        try:
            renderer.run()
            with open(output_file_pdf_temp, 'rb') as download:
                texto_pdf = pymupdf.open(download)
                merger.insert_pdf(texto_pdf)
        except Exception as e:
            print(f"Erro ao converter ODT principal para PDF: {e}")
            # Handle the error appropriately, maybe return or raise
            if os.path.exists(output_file_pdf_temp):
                os.unlink(output_file_pdf_temp)
            return

        if os.path.exists(output_file_pdf_temp):
            os.unlink(output_file_pdf_temp)

        # Process attachments
        for anexo in self.pysc.anexo_proposicao_pysc(cod_proposicao, listar=True):
            try:
                arq_anexo = getattr(self.sapl_documentos.proposicao, anexo)
                arquivo_anexo = BytesIO(bytes(arq_anexo.data))
                arquivo_anexo.seek(0)
                texto_anexo = pymupdf.open(stream=arquivo_anexo)
                merger.insert_pdf(texto_anexo)
                arquivo_anexo.close()
            except Exception as e:
                print(f"Erro ao processar anexo {anexo}: {e}")
                # Handle the error appropriately

        # Get the final merged PDF content
        final_pdf_content = merger.tobytes()
        merger.close()

        # Store the final PDF
        upload_kwargs = {'file': self.pysc.upload_file(file=final_pdf_content, title='Proposição ' + cod_proposicao)}
        self.sapl_documentos.proposicao.manage_addFile(id=nom_arquivo_pdf, **upload_kwargs)

        # Set permissions
        pdf = getattr(self.sapl_documentos.proposicao, nom_arquivo_pdf)
        pdf.manage_permission('View', roles=['Manager', 'Authenticated'], acquire=0)

    def substitutivo_gerar_pdf(self, cod_substitutivo):
        nom_arquivo_odt = f"{cod_substitutivo}_substitutivo.odt"
        nom_arquivo_pdf = f"{cod_substitutivo}_substitutivo.pdf"
        arq = getattr(self.sapl_documentos.substitutivo, nom_arquivo_odt)
        self._gerar_e_armazenar_pdf(arq, nom_arquivo_odt, nom_arquivo_pdf,
                             self.sapl_documentos.substitutivo, 'Substitutivo')

    def pdf_completo(self, cod_sessao_plen):
        """
        Gera um PDF completo da pauta da sessão, incluindo matérias e documentos relacionados.
        Args:
            cod_sessao_plen (int): Código da sessão plenária.
        Returns:
            bytes: Conteúdo do PDF gerado.
        """
        merger = pymupdf.open()
        def _carregar_e_mesclar_pdf(document_source, document_id, filename_pattern):
            """Função interna para carregar e mesclar um PDF."""
            filename = filename_pattern.format(document_id)
            if hasattr(document_source, filename):
                try:
                    arq = getattr(document_source, filename)
                    arquivo = BytesIO(bytes(arq.data))
                    texto_anexo = pymupdf.open(stream=arquivo)
                    texto_anexo.bake()
                    merger.insert_pdf(texto_anexo)
                except pymupdf.PdfError as e:
                    logging.error(f"Erro ao processar PDF {filename}: {e}")
                except Exception as e:
                    logging.error(f"Erro inesperado ao carregar PDF {filename}: {e}")
        try:
            for pauta in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
                nom_arquivo_pdf = f"{cod_sessao_plen}_pauta_completa.pdf"
                nom_pdf_amigavel = f"{pauta.num_sessao_plen}-sessao-{pauta.dat_inicio}-pauta.pdf"
                # Carregar PDF da pauta principal
                _carregar_e_mesclar_pdf(self.sapl_documentos.pauta_sessao, cod_sessao_plen, "{}_pauta_sessao.pdf")
                lst_materia = []
                for materia in self.zsql.ordem_dia_obter_zsql(cod_sessao_plen=pauta.cod_sessao_plen, ind_excluido=0):
                    if materia.cod_materia and materia.cod_materia != '':
                        lst_materia.append(int(materia.cod_materia))  # Garantir que é um inteiro
                lst_materia = list(dict.fromkeys(lst_materia))
                # Processar matérias e documentos relacionados
                for cod_materia in lst_materia:
                    _carregar_e_mesclar_pdf(self.sapl_documentos.materia, cod_materia, "{}_redacao_final.pdf")
                    _carregar_e_mesclar_pdf(self.sapl_documentos.materia, cod_materia, "{}_texto_integral.pdf")
                    for anexada in self.zsql.anexada_obter_zsql(cod_materia_principal=cod_materia, ind_excluido=0):
                        _carregar_e_mesclar_pdf(self.sapl_documentos.materia, anexada.cod_materia_anexada, "{}_texto_integral.pdf")
                    for subst in self.zsql.substitutivo_obter_zsql(cod_materia=cod_materia, ind_excluido=0):
                        _carregar_e_mesclar_pdf(self.sapl_documentos.substitutivo, subst.cod_substitutivo, "{}_substitutivo.pdf")
                    for eme in self.zsql.emenda_obter_zsql(cod_materia=cod_materia, ind_excluido=0):
                        _carregar_e_mesclar_pdf(self.sapl_documentos.emenda, eme.cod_emenda, "{}_emenda.pdf")
                    for relat in self.zsql.relatoria_obter_zsql(cod_materia=cod_materia, ind_excluido=0):
                        for tipo in self.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria=relat.tip_fim_relatoria):
                            if tipo.des_fim_relatoria != 'Aguardando apreciação':
                                _carregar_e_mesclar_pdf(self.sapl_documentos.parecer_comissao, relat.cod_relatoria, "{}_parecer.pdf")
            # Finalizar PDF e adicionar numeração de páginas
            merged_pdf = merger.tobytes(deflate=True, garbage=3, use_objstms=1)
            existing_pdf = pymupdf.open(stream=merged_pdf)
            num_pages = existing_pdf.page_count
            for page_index, i in enumerate(range(len(existing_pdf))):
                w = existing_pdf[page_index].rect.width
                h = existing_pdf[page_index].rect.height
                margin = 5
                p1 = pymupdf.Point(w - 70 - margin, margin + 20)
                shape = existing_pdf[page_index].new_shape()
                shape.draw_circle(p1, 1)
                shape.insert_text(p1, f"Fls. {i + 1}/{num_pages}", fontname="helv", fontsize=8)
                shape.commit()
            content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
            # Salvar ou atualizar o PDF
            if nom_arquivo_pdf in self.sapl_documentos.pauta_sessao:
                arq = getattr(self.sapl_documentos.pauta_sessao, nom_arquivo_pdf)
                arq.update_data(content)
            else:
                self.sapl_documentos.pauta_sessao.manage_addFile(id=nom_arquivo_pdf, file=content, title='Ordem do Dia')
            # Configurar cabeçalhos da resposta HTTP
            self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
            self.REQUEST.RESPONSE.setHeader('Content-Disposition', f'inline; filename={nom_pdf_amigavel}')
            return content
        except Exception as e:
            logging.error(f"Ocorreu um erro ao processar o PDF: {e}")
            return None
 
    def pdf_expediente_completo(self, cod_sessao_plen):
        """Gera um arquivo PDF consolidado com o expediente completo de uma sessão."""
        merger = pymupdf.open()
        nom_pdf_amigavel = ""
        logging.info(f"Iniciando geração de pauta completa do expediente da sessão {cod_sessao_plen}.")
        try:
            for pauta in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
                nom_pdf_amigavel = f"{pauta.num_sessao_plen}_sessao_expediente_completo.pdf"
                if hasattr(self.sapl_documentos.pauta_sessao, f"{cod_sessao_plen}_pauta_expediente.pdf"):
                    pdf_data = getattr(self.sapl_documentos.pauta_sessao, f"{cod_sessao_plen}_pauta_expediente.pdf")
                    pdf_bytes = BytesIO(bytes(pdf_data.data))
                    pdf_document = pymupdf.open(stream=pdf_bytes)
                    pdf_document.bake()
                    merger.insert_pdf(pdf_document)
                    logging.info(f"PDF da pauta {cod_sessao_plen} adicionado.")
                for item in self.zsql.materia_apresentada_sessao_obter_zsql(cod_sessao_plen=pauta.cod_sessao_plen, ind_excluido=0):
                    if item.cod_materia:
                        pasta, cod_doc, sufixo_arquivo = self.sapl_documentos.materia, item.cod_materia, 'texto_integral'
                    elif item.cod_emenda:
                        pasta, cod_doc, sufixo_arquivo = self.sapl_documentos.emenda, item.cod_emenda, 'emenda'
                    elif item.cod_substitutivo:
                        pasta, cod_doc, sufixo_arquivo = self.sapl_documentos.substitutivo, item.cod_substitutivo, 'substitutivo'
                    elif item.cod_parecer:
                        pasta, cod_doc, sufixo_arquivo = self.sapl_documentos.parecer_comissao, item.cod_parecer, 'parecer'
                    elif item.cod_documento:
                        pasta, cod_doc, sufixo_arquivo = self.sapl_documentos.administrativo, item.cod_documento, 'texto_integral'
                    else:
                        continue  # Pula para o próximo item se nenhum código for encontrado
                    if hasattr(pasta, f"{cod_doc}_{sufixo_arquivo}.pdf"):
                        pdf_data = getattr(pasta, f"{cod_doc}_{sufixo_arquivo}.pdf")
                        pdf_bytes = BytesIO(bytes(pdf_data.data))
                        pdf_document = pymupdf.open(stream=pdf_bytes)
                        pdf_document.bake()
                        merger.insert_pdf(pdf_document)
                        logging.info(f"Item {cod_doc}_{sufixo_arquivo}.pdf da leitura adicionado.")
                for item in self.zsql.expediente_materia_obter_zsql(cod_sessao_plen=pauta.cod_sessao_plen, ind_excluido=0):
                    if item.cod_materia:
                        pasta, cod_doc, sufixo_arquivo = self.sapl_documentos.materia, item.cod_materia, 'texto_integral'
                    elif item.cod_parecer:
                        pasta, cod_doc, sufixo_arquivo = self.sapl_documentos.parecer_comissao, item.cod_parecer, 'parecer'
                    else:
                        continue
                    if hasattr(pasta, f"{cod_doc}_{sufixo_arquivo}.pdf"):
                        pdf_data = getattr(pasta, f"{cod_doc}_{sufixo_arquivo}.pdf")
                        pdf_bytes = BytesIO(bytes(pdf_data.data))
                        pdf_document = pymupdf.open(stream=pdf_bytes)
                        pdf_document.bake()
                        merger.insert_pdf(pdf_document)
                        logging.info(f"Item {cod_doc}_{sufixo_arquivo}.pdf do expediente adicionado.")
            merged_pdf = merger.tobytes(deflate=True, garbage=3, use_objstms=1)
            existing_pdf = pymupdf.open(stream=merged_pdf)
            num_pages = existing_pdf.page_count
            for page_index, i in enumerate(range(len(existing_pdf))):
                w = existing_pdf[page_index].rect.width
                h = existing_pdf[page_index].rect.height
                margin = 5
                p1 = pymupdf.Point(w - 70 - margin, margin + 20)
                shape = existing_pdf[page_index].new_shape()
                shape.draw_circle(p1, 1)
                text = f"Fls. {i + 1}/{num_pages}"
                shape.insert_text(p1, text, fontname="helv", fontsize=8)
                shape.commit()
            content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
            logging.info(f"Finalizada a geração de pauta completa do expediente da sessão {cod_sessao_plen}.")
            self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
            self.REQUEST.RESPONSE.setHeader('Content-Disposition', f'inline; filename={nom_pdf_amigavel}')
            return content
        except Exception as e:
            logging.error(f"Erro ao gerar PDF: {e}")
            return None

    def materia_gerar_docx(self, inf_basicas_dic, num_proposicao, nom_arquivo, des_tipo_materia, num_ident_basica, num_materia, ano_ident_basica, ano_materia, txt_ementa, materia_vinculada, dat_apresentacao, nom_autor, apelido_autor, subscritores, modelo_proposicao):
        arq = getattr(self.sapl_documentos.modelo.materia, modelo_proposicao)
        template_file = BytesIO(bytes(arq.data))
        brasao = self.get_brasao()
        renderer = Renderer(template_file, locals(), nom_arquivo, pythonWithUnoPath='/usr/bin/python3', forceOoCall=True)
        renderer.run()
        with open(nom_arquivo, "rb") as file:
            data = file.read()
        os.unlink(nom_arquivo)
        self.sapl_documentos.materia_docx.manage_addFile(id=nom_arquivo,file=data)
        doc = getattr(self.sapl_documentos.materia_docx, nom_arquivo)
        doc.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)

    def tramitacao_documento_juntar(self, cod_tramitacao):
        """
        Junta os arquivos PDF de tramitação de processo administrativo (principal e anexos) em um único arquivo.
        Args:
            cod_tramitacao: O código de tramitação do processo administrativo.
        """
        merger = pymupdf.open()
        base_filename = str(cod_tramitacao) + "_tram"
        filenames = [
            f"{base_filename}.pdf",
            f"{base_filename}_anexo1.pdf",
        ]  # Lista de nomes de arquivos a serem processados
        try:
            for filename in filenames:
                if hasattr(self.sapl_documentos.administrativo.tramitacao, filename):
                    try:
                        arq = getattr(self.sapl_documentos.administrativo.tramitacao, filename)
                        arquivo = BytesIO(bytes(arq.data))
                        arquivo.seek(0)
                        with pymupdf.open(stream=arquivo) as pdf_doc:
                            pdf_doc.bake()
                            merger.insert_pdf(pdf_doc)
                    except Exception as e:
                        print(f"Erro ao processar arquivo {filename}: {e}")
            outputStream = BytesIO()
            merger.save(outputStream, linear=True)
            outputStream.seek(0)
            content = outputStream.getvalue()
            pdf = getattr(self.sapl_documentos.administrativo.tramitacao, f"{cod_tramitacao}_tram.pdf")
            pdf.update_data(content)
            for tram in self.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=cod_tramitacao, ind_excluido=0):
                if self.zsql.documento_administrativo_pesquisar_publico_zsql(cod_documento=tram.cod_documento, ind_excluido=0):
                   pdf = getattr(self.sapl_documentos.administrativo.tramitacao, f"{cod_tramitacao}_tram.pdf")
                   pdf.manage_permission('View', roles=['Manager','Authenticated','Anonymous'], acquire=1)
        except Exception as e:
            print(f"Erro ao juntar arquivos PDF: {e}")
        finally:
            merger.close()

    def tramitacao_materia_juntar(self, cod_tramitacao):
        """
        Junta os arquivos PDF de tramitação de matéria (principal e anexos) em um único arquivo.
        Args:
            cod_tramitacao: O código de tramitação da matéria legislativa.
        """
        merger = pymupdf.open()
        base_filename = str(cod_tramitacao) + "_tram"
        filenames = [
            f"{base_filename}.pdf",
            f"{base_filename}_anexo1.pdf",
        ]  # Lista de nomes de arquivos a serem processados
        try:
            for filename in filenames:
                if hasattr(self.sapl_documentos.materia.tramitacao, filename):
                    try:
                        arq = getattr(self.sapl_documentos.materia.tramitacao, filename)
                        arquivo = BytesIO(bytes(arq.data))
                        arquivo.seek(0)
                        with pymupdf.open(stream=arquivo) as pdf_doc:
                            pdf_doc.bake()
                            merger.insert_pdf(pdf_doc)
                    except Exception as e:
                        print(f"Erro ao processar arquivo {filename}: {e}")
            outputStream = BytesIO()
            merger.save(outputStream, linear=True)
            outputStream.seek(0)
            content = outputStream.getvalue()
            pdf = getattr(self.sapl_documentos.materia.tramitacao, f"{cod_tramitacao}_tram.pdf")
            pdf.update_data(content)
        except Exception as e:
            print(f"Erro ao juntar arquivos PDF: {e}")
        finally:
            merger.close()

    def materias_expediente_gerar_ods(self, relatorio_dic, total_assuntos, parlamentares, nom_arquivo):
        try:
            arq = getattr(self.sapl_documentos.modelo.sessao_plenaria, "relatorio-expediente.odt")
            template_file = BytesIO(bytes(arq.data))
            brasao = self.get_brasao()
            renderer_vars = {'relatorio_dic': relatorio_dic, 'total_assuntos': total_assuntos, 'parlamentares': parlamentares, 'brasao': brasao}
            renderer = Renderer(template_file, renderer_vars, nom_arquivo, pythonWithUnoPath='/usr/bin/python3', forceOoCall=True)
            renderer.run()
            with open(nom_arquivo, "rb") as file:
                data = file.read()
            os.unlink(nom_arquivo)
            self.REQUEST.RESPONSE.headers['Content-Type'] = 'application/vnd.oasis.opendocument.text'
            self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%nom_arquivo
            return data
        except Exception as e:
            # Log de Erro
            print(f"Erro ao exportar matérias do expediente em ODS: {e}")
            return None

    def pessoas_exportar(self, pessoas):
        arq = getattr(self.sapl_documentos.modelo, "planilha-visitantes.ods")
        template_file = BytesIO(bytes(arq.data))
        brasao_file = self.get_brasao()
        exec('brasao = brasao_file')
        output_file_ods = "contatos.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def eleitores_exportar(self, eleitores):
        arq = getattr(self.sapl_documentos.modelo, "planilha-eleitores.ods")
        template_file = BytesIO(bytes(arq.data))
        output_file_ods = "eleitores.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def materias_exportar(self, materias):
        arq = getattr(self.sapl_documentos.modelo, "planilha-materias.ods")
        template_file = BytesIO(bytes(arq.data))
        output_file_ods = "materias.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def normas_exportar(self, normas):
        arq = getattr(self.sapl_documentos.modelo, "planilha-normas.ods")
        template_file = BytesIO(bytes(arq.data))
        output_file_ods = "normas.ods"
        renderer = Renderer(template_file, locals(), output_file_ods, pythonWithUnoPath='/usr/bin/python3',forceOoCall=True)
        renderer.run()
        data = open(output_file_ods, "rb").read()
        os.unlink(output_file_ods)
        self.REQUEST.RESPONSE.headers['Content-Type'] = 'vnd.oasis.opendocument.spreadsheet'
        self.REQUEST.RESPONSE.headers['Content-Disposition'] = 'attachment; filename="%s"'%output_file_ods
        return data

    def protocolo_barcode(self, cod_protocolo):
        """
        Gera e insere um código de barras e informações de texto em um arquivo PDF de protocolo.
        Args:
            cod_protocolo: O código do protocolo para o qual gerar o código de barras.
        """
        sgl_casa = self.sapl_documentos.props_sagl.sgl_casa
        for protocolo in self.zsql.protocolo_obter_zsql(
            cod_protocolo=cod_protocolo
        ):
            string = str(protocolo.cod_protocolo).zfill(7)
            texto = f"PROT- {sgl_casa} {protocolo.num_protocolo}/{protocolo.ano_protocolo}"
            data = (
                DateTime(protocolo.dat_protocolo, datefmt="international").strftime(
                    "%d/%m/%Y"
                )
                + " "
                + protocolo.hor_protocolo
            )
            des_tipo_materia = ""
            num_materia = ""
            if protocolo.tip_processo == 1:
                if protocolo.tip_natureza_materia == 1:
                    for materia in self.zsql.materia_obter_zsql(
                        num_protocolo=protocolo.num_protocolo,
                        ano_ident_basica=protocolo.ano_protocolo,
                    ):
                        des_tipo_materia = materia.des_tipo_materia
                        num_materia = (
                            f"{materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica}"
                        )
                        break
                elif protocolo.tip_natureza_materia in (2, 3, 4):
                    cod_materia_principal = protocolo.cod_materia_principal
                    for materia in self.zsql.materia_obter_zsql(
                        cod_materia=cod_materia_principal
                    ):
                        materia_principal = (
                            f" - {materia.sgl_tipo_materia} {materia.num_ident_basica}/{materia.ano_ident_basica}"
                        )
                        break
                    if protocolo.tip_natureza_materia == 2:
                        for tipo in self.zsql.tipo_materia_legislativa_obter_zsql(
                            tip_materia=protocolo.tip_materia, tip_natureza="A"
                        ):
                            if tipo.des_tipo_materia == "Emenda":
                                for emenda in self.zsql.emenda_obter_zsql(
                                    num_protocolo=protocolo.num_protocolo,
                                    cod_materia=cod_materia_principal,
                                ):
                                    num_materia = f"EME {emenda.num_emenda} {materia_principal}"
                                    des_tipo_materia = tipo.des_tipo_materia
                                    break # Assuming only need the first emenda
                            elif tipo.des_tipo_materia == "Substitutivo":
                                for substitutivo in self.zsql.substitutivo_obter_zsql(
                                    num_protocolo=protocolo.num_protocolo,
                                    cod_materia=cod_materia_principal,
                                ):
                                    num_materia = f"SUB {substitutivo.num_substitutivo} {materia_principal}"
                                    des_tipo_materia = tipo.des_tipo_materia
                                    break
                            if num_materia:
                                break
                    elif protocolo.tip_natureza_materia == 3:
                        for documento in self.zsql.documento_acessorio_obter_zsql(
                            num_protocolo=protocolo.num_protocolo,
                            cod_materia=cod_materia_principal,
                        ):
                            num_materia = f"{documento.des_tipo_documento} {materia_principal}"
                            des_tipo_materia = documento.des_tipo_documento
                            break
                    elif protocolo.tip_natureza_materia == 4:
                        for autor in self.zsql.autor_obter_zsql(
                            cod_autor=protocolo.cod_autor
                        ):
                            for comissao in self.zsql.comissao_obter_zsql(
                                cod_comissao=autor.cod_comissao
                            ):
                                sgl_comissao = comissao.sgl_comissao
                                break 
                            break
                        for parecer in self.zsql.relatoria_obter_zsql(
                            num_protocolo=protocolo.num_protocolo,
                            cod_materia=cod_materia_principal,
                        ):
                            num_materia = f"PAR {sgl_comissao} {parecer.num_parecer}/{parecer.ano_parecer} {materia_principal}"
                            des_tipo_materia = "Parecer"
                            break
            elif protocolo.tip_processo == 0:
                for documento in self.zsql.documento_administrativo_obter_zsql(
                    num_protocolo=protocolo.num_protocolo,
                    ano_documento=protocolo.ano_protocolo,
                ):
                    num_materia = f"{documento.sgl_tipo_documento} {documento.num_documento}/{documento.ano_documento}"
                    des_tipo_materia = documento.sgl_tipo_documento
                    break # Assuming only need the first documento
            nom_pdf_protocolo = str(cod_protocolo) + "_protocolo.pdf"
            arq = getattr(self.sapl_documentos.protocolo, nom_pdf_protocolo)
            arquivo = BytesIO(bytes(arq.data))
            existing_pdf = pymupdf.open(stream=arquivo)
            w = existing_pdf[0].rect.width
            h = existing_pdf[0].rect.height
            margin = 10
            top = margin + 50
            right = w - 40 - margin
            black = pymupdf.pdfcolor["black"]
            rect = pymupdf.Rect(
                right, top, right + 40, top + 40
            )  # barcode bottom right square
            stream = self.create_barcode(numero_a_codificar=string)
            existing_pdf[0].insert_image(rect, stream=stream, rotate=-90)
            text2 = texto + "\n" + data + "\n" + num_materia
            p2 = pymupdf.Point(w - 8 - margin, margin + 90)
            shape = existing_pdf[0].new_shape()
            shape.draw_circle(p2, 1)
            shape.insert_text(p2, text2, fontname="helv", fontsize=7, rotate=-90)
            shape.commit()
            content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
            if nom_pdf_protocolo in self.sapl_documentos.protocolo:
                documento = getattr(self.sapl_documentos.protocolo, nom_pdf_protocolo)
                documento.update_data(content)
            else:
                self.sapl_documentos.protocolo.manage_addFile(
                    id=nom_pdf_protocolo, file=content, title="Protocolo"
                )
            pdf = getattr(self.sapl_documentos.protocolo, nom_pdf_protocolo)
            pdf.manage_permission(
                "View", roles=["Manager", "Authenticated"], acquire=0
            )

    def restpki_client(self):
        """
        Inicializa e retorna um objeto RestPkiClient.
        """
        try:
            restpki_url = 'https://restpkiol.azurewebsites.net/'
            restpki_access_token = self.sapl_documentos.props_sagl.restpki_access_token
            restpki_client = RestPkiClient(restpki_url, restpki_access_token)
            return restpki_client
        except AttributeError as e:
            logging.error(f"Erro ao inicializar RestPkiClient: {e}")
            raise 
        except Exception as e:
            logging.error(f"Erro inesperado ao inicializar RestPkiClient: {e}")
            raise

    def get_file_tosign(self, codigo, anexo, tipo_doc):
        """
        Recupera o arquivo PDF a ser assinado, seu caminho de armazenamento e seu checksum CRC32.
        """
        try:
            storage_info = self.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc)
            storage = None
            for s in storage_info:
                storage = s
                break 
            if storage is None:
                print(f"Erro: Nenhuma informação de armazenamento encontrada para tipo_doc: {tipo_doc}")
                return None, None, None
            tipo_doc = storage.tip_documento
            if tipo_doc == 'proposicao':
                storage_path = self.sapl_documentos.proposicao
                pdf_location = storage.pdf_location
                pdf_signed = f"{pdf_location}{codigo}{storage.pdf_signed}"
                nom_arquivo_assinado = f"{codigo}{storage.pdf_signed}"
                pdf_file = f"{pdf_location}{codigo}{storage.pdf_file}"
                nom_arquivo = f"{codigo}{storage.pdf_file}"
            else:
                item = None
                document_info = self.zsql.assinatura_documento_obter_zsql(codigo=codigo, anexo=anexo, tipo_doc=tipo_doc, ind_assinado=1)
                for i in document_info:
                    item = i
                    break # Assuming you only need the first item
                if item:
                    storage_path = self.sapl_documentos.documentos_assinados
                    pdf_location = 'sapl_documentos/documentos_assinados/'
                    pdf_signed = f"{pdf_location}{item.cod_assinatura_doc}.pdf"
                    nom_arquivo_assinado = f"{item.cod_assinatura_doc}.pdf"
                    pdf_file = f"{pdf_location}{item.cod_assinatura_doc}.pdf"
                    nom_arquivo = f"{item.cod_assinatura_doc}.pdf"
                else:
                    # local de armazenamento
                    pdf_location = storage.pdf_location
                    pdf_signed = f"{pdf_location}{codigo}{storage.pdf_signed}"
                    nom_arquivo_assinado = f"{codigo}{storage.pdf_signed}"
                    pdf_file = f"{pdf_location}{codigo}{storage.pdf_file}"
                    nom_arquivo = f"{codigo}{storage.pdf_file}"
                    storage_path = None  # Initialize storage_path
                    if tipo_doc in ('materia', 'doc_acessorio', 'redacao_final'):
                        storage_path = self.sapl_documentos.materia
                    elif tipo_doc == 'emenda':
                        storage_path = self.sapl_documentos.emenda
                    elif tipo_doc == 'substitutivo':
                        storage_path = self.sapl_documentos.substitutivo
                    elif tipo_doc == 'tramitacao':
                        storage_path = self.sapl_documentos.materia.tramitacao
                    elif tipo_doc == 'parecer_comissao':
                        storage_path = self.sapl_documentos.parecer_comissao
                    elif tipo_doc in ('pauta', 'resumo_sessao'):
                        storage_path = self.sapl_documentos.pauta_sessao
                    elif tipo_doc == 'ata':
                        storage_path = self.sapl_documentos.ata_sessao
                    elif tipo_doc == 'norma':
                        storage_path = self.sapl_documentos.norma_juridica
                    elif tipo_doc in ('documento', 'doc_acessorio_adm'):
                        storage_path = self.sapl_documentos.administrativo
                    elif tipo_doc == 'tramitacao_adm':
                        storage_path = self.sapl_documentos.administrativo.tramitacao
                    elif tipo_doc == 'protocolo':
                        storage_path = self.sapl_documentos.protocolo
                    elif tipo_doc == 'peticao':
                        storage_path = self.sapl_documentos.peticao
                    elif tipo_doc == 'pauta_comissao':
                        storage_path = self.sapl_documentos.reuniao_comissao
                    elif tipo_doc == 'ata_comissao':
                        storage_path = self.sapl_documentos.reuniao_comissao
                    elif tipo_doc == 'documento_comissao':
                        storage_path = self.sapl_documentos.documento_comissao
                    elif tipo_doc == 'anexo_peticao':
                        storage_path = self.sapl_documentos.peticao
                        pdf_file = f"{pdf_location}{codigo}_anexo_{anexo}{storage.pdf_file}"
                        nom_arquivo = f"{codigo}_anexo_{anexo}{storage.pdf_file}"
                    elif tipo_doc == 'anexo_sessao':
                        storage_path = self.sapl_documentos.anexo_sessao
                        pdf_file = f"{pdf_location}{codigo}_anexo_{anexo}{storage.pdf_file}"
                        nom_arquivo = f"{codigo}_anexo_{anexo}{storage.pdf_file}"
            try:
                arquivo = self.restrictedTraverse(pdf_signed)
                pdf_tosign = nom_arquivo_assinado
            except:
                try:
                    arquivo = self.restrictedTraverse(pdf_file)
                    pdf_tosign = nom_arquivo
                except Exception as e:
                    print(f"Erro ao acessar o arquivo: {e}")
                    return None, None, None
            try:
                x = crc32(bytes(arquivo))
                if x >= 0:
                    crc_arquivo = str(x)
                else:
                    crc_arquivo = str(-1 * x)
            except Exception as e:
                print(f"Erro ao calcular o CRC32: {e}")
                return None, None, None
            return pdf_tosign, storage_path, crc_arquivo
        except Exception as e:
            print(f"Erro geral em get_file_tosign: {e}")
            return None, None, None

    def pades_signature(self, codigo, anexo, tipo_doc, cod_usuario, visual_page_option, page_number=None, coords=None):
        """
        Inicia o processo de assinatura PAdES para um arquivo PDF,
        com suporte a posicionamento visual personalizado via coordenadas.
        """
        try:
            # Obter o arquivo PDF a ser assinado
            pdf_tosign, storage_path, crc_arquivo = self.get_file_tosign(codigo, anexo, tipo_doc)
            if not pdf_tosign:
                raise ValueError("Arquivo PDF para assinatura não encontrado.")

            arq = getattr(storage_path, pdf_tosign)
            with BytesIO(bytes(arq.data)) as arq1:
                pdf_stream = base64.b64encode(arq1.getvalue()).decode('utf8')

            # Obter selo/brasão
            try:
                id_logo = self.sapl_documentos.props_sagl.id_logo
                arq = getattr(self.sapl_documentos.props_sagl, id_logo)
                with BytesIO(bytes(arq.data)) as arq1:
                    pdf_stamp = base64.b64encode(arq1.getvalue()).decode('utf8')
            except AttributeError:
                install_home = os.environ.get('INSTALL_HOME')
                if not install_home:
                    raise EnvironmentError("Variável de ambiente INSTALL_HOME não configurada.")
                dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/brasao.gif')
                if not os.path.exists(dirpath):
                    raise FileNotFoundError(f"Arquivo de imagem não encontrado: {dirpath}")
                with open(dirpath, "rb") as arq1:
                    pdf_stamp = base64.b64encode(arq1.read()).decode('utf8')

            # Iniciar assinatura
            signature_starter = PadesSignatureStarter(self.restpki_client())
            signature_starter.set_pdf_stream(pdf_stream)
            signature_starter.signature_policy_id = StandardSignaturePolicies.PADES_BASIC
            signature_starter.security_context_id = StandardSecurityContexts.PKI_BRAZIL

            # Montar representação visual
            visual_representation = {
                'text': {
                    'text': 'Assinado digitalmente por {{signerName}}',
                    'includeSigningTime': True,
                    'horizontalAlign': 'Left'
                },
                'image': {
                    'resource': {
                        'content': pdf_stamp,
                        'mimeType': 'image/png'
                    },
                    'opacity': 40,
                    'horizontalAlign': 'Right'
                }
            }

            # Se usuário clicou no PDF para indicar posição
            if page_number and coords:
                try:
                    x, y = map(int, coords.split(','))
                    visual_representation['position'] = {
                        'pageNumber': int(page_number),
                        'measurementUnits': 'Pixels',
                        'manual': {
                            'left': x,
                            'top': y,
                            'width': 200,  # pixels
                            'height': 50
                        }
                    }
                except Exception as e:
                    logging.warning(f"Erro ao interpretar coordenadas: {e}")
                    sample_number = 2 if str(visual_page_option) == 'ultima' else 4
                    visual_representation['position'] = self.get_visual_representation_position(sample_number)
            else:
                # Posição automática
                sample_number = 2 if str(visual_page_option) == 'ultima' else 4
                visual_representation['position'] = self.get_visual_representation_position(sample_number)

            signature_starter.visual_representation = visual_representation
 
            # Iniciar com Web PKI
            token = signature_starter.start_with_webpki()
            tokenjs = json.dumps(token)

            return token, '', crc_arquivo, codigo, anexo, tipo_doc, cod_usuario, tokenjs

        except (ValueError, AttributeError, OSError, EnvironmentError) as e:
            logging.error(f"Erro em pades_signature: {e}")
            return None, None, None, codigo, anexo, tipo_doc, cod_usuario, None
        except Exception as e:
            logging.error(f"Erro inesperado em pades_signature: {e}")
            return None, None, None, codigo, anexo, tipo_doc, cod_usuario, None

    def pades_signature_action(self, token, codigo, anexo, tipo_doc, cod_usuario, crc_arquivo_original, visual_page_option):
        """
        Finaliza o processo de assinatura PAdES e armazena o PDF assinado.
        """
        try:
            # Verifica se o arquivo foi modificado
            pdf_tosign, storage_path, crc_arquivo = self.get_file_tosign(codigo, anexo, tipo_doc)
            if not pdf_tosign:
                raise ValueError("Arquivo não encontrado.")
            if str(crc_arquivo_original) != str(crc_arquivo):
                raise ValueError("O arquivo foi modificado durante o procedimento de assinatura! Tente novamente.")
            # Finaliza a assinatura
            signature_finisher = PadesSignatureFinisher(self.restpki_client())
            signature_finisher.token = token
            signature_finisher.finish()
            signer_cert = signature_finisher.certificate
            # Obtém ou gera cod_assinatura_doc
            assinatura_docs = list(self.zsql.assinatura_documento_obter_zsql(codigo=codigo, anexo=anexo, tipo_doc=tipo_doc))
            assinatura_doc = assinatura_docs[0] if assinatura_docs else None
            if assinatura_doc:
                cod_assinatura_doc = str(assinatura_doc.cod_assinatura_doc)
                self.zsql.assinatura_documento_registrar_zsql(cod_assinatura_doc=cod_assinatura_doc, cod_usuario=cod_usuario)
            else:
                cod_assinatura_doc = str(self.cadastros.assinatura.generate_verification_code())
                self.zsql.assinatura_documento_incluir_zsql(
                    cod_assinatura_doc=cod_assinatura_doc,
                    codigo=codigo,
                    anexo=anexo,
                    tipo_doc=tipo_doc,
                    cod_solicitante=cod_usuario,
                    cod_usuario=cod_usuario,
                    ind_prim_assinatura=1,
                    visual_page_option=visual_page_option
                )
                self.zsql.assinatura_documento_registrar_zsql(cod_assinatura_doc=cod_assinatura_doc, cod_usuario=cod_usuario)
            # Determina storage_path e filename
            if tipo_doc == 'proposicao':
                storage_path = self.sapl_documentos.proposicao
                storage_result = list(self.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc))
                filename = f"{codigo}{storage_result[0].pdf_signed}" if storage_result else None
            else:
                storage_path = self.sapl_documentos.documentos_assinados
                filename = f"{cod_assinatura_doc}.pdf"
            # Armazena o PDF assinado
            f = signature_finisher.stream_signed_pdf()
            if hasattr(storage_path, filename):
                storage_path[filename].update_data(f.getvalue())
            else:
                storage_path.manage_addFile(id=filename, file=f.getvalue(), title=filename)
            # Adiciona margem inferior (se aplicável)
            if tipo_doc != 'proposicao' and tipo_doc != 'peticao':
                self.margem_inferior(codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename)
            # Extrai informações do certificado
            subject_name = signer_cert['subjectName']
            common_name = subject_name['commonName']
            email = signer_cert['emailAddress']
            pki_brazil = signer_cert['pkiBrazil']
            certificate_type = pki_brazil['certificateType']
            cpf = pki_brazil['cpf']
            responsavel = pki_brazil['responsavel']
            filenamejs = json.dumps(filename)
            return signer_cert, common_name, email, certificate_type, cpf, responsavel, filename, filenamejs
        except ValueError as e:
            print(f"Erro de validação em pades_signature_action: {e}")
            return None, None, None, None, None, None, None, None
        except Exception as e:
            print(f"Erro em pades_signature_action: {e}")
            return None, None, None, None, None, None, None, None

    def get_visual_representation_position(self, sample_number):
        """
        Retorna a representação visual da assinatura PAdES com base no número da amostra.
        """
        if sample_number == 1:
            # Example #1: automatic positioning on footnote. This will insert the signature, and future signatures,
            # ordered as a footnote of the last page of the document
            return PadesVisualPositioningPresets.get_footnote(self.restpki_client())
        elif sample_number == 2:
            # Example #2: get the footnote positioning preset and customize it
            visual_position = PadesVisualPositioningPresets.get_footnote(self.restpki_client())
            visual_position['auto']['container']['left'] = 3
            visual_position['auto']['container']['bottom'] = 2
            visual_position['auto']['container']['right'] = 3
            return visual_position
        elif sample_number == 3:
            # Example #3: automatic positioning on new page. This will insert the signature, and future signatures,
            # in a new page appended to the end of the document.
            return PadesVisualPositioningPresets.get_new_page(self.restpki_client())
        elif sample_number == 4:
            # Example #4: get the "new page" positioning preset and customize it
            visual_position = PadesVisualPositioningPresets.get_new_page(self.restpki_client())
            visual_position['auto']['container']['left'] = 3
            visual_position['auto']['container']['top'] = 2
            visual_position['auto']['container']['bottom'] = 2
            visual_position['auto']['container']['right'] = 3
            return visual_position
        elif sample_number == 5:
            # Example #5: manual positioning
            return {
                'pageNumber': 0,
                # zero means the signature will be placed on a new page appended to the end of the document
                'measurementUnits': 'Centimeters',
                # define a manual position of 5cm x 3cm, positioned at 1 inch from the left and bottom margins
                'manual': {
                    'left': 2.54,
                    'bottom': 1.54,
                    'width': 5,
                    'height': 3
                }
            }
        elif sample_number == 6:
            # Example #6: custom auto positioning
            return {
                'pageNumber': -1,
                # negative values represent pages counted from the end of the document (-1 is last page)
                'measurementUnits': 'Centimeters',
                'auto': {
                    # Specification of the container where the signatures will be placed, one after the other
                    'container': {
                        # Specifying left and right (but no width) results in a variable-width container with the given
                        # margins
                        'left': 2.54,
                        'right': 2.54,
                        # Specifying bottom and height (but no top) results in a bottom-aligned fixed-height container
                        'top': 1.54,
                        'height': 3
                    },
                    # Specification of the size of each signature rectangle
                    #'signatureRectangleSize': {
                    #    'width': 5,
                    #    'height': 3
                    #},
                    # The signatures will be placed in the container side by side. If there's no room left, the
                    # signatures will "wrap" to the next row. The value below specifies the vertical distance between
                    # rows
                    'rowSpacing': 1
                }
            }
        else:
            return None

    def _getValidEmailAddress(self, member):
        email = None
        for usuario in self.zsql.usuario_obter_zsql(col_username=member):
            email = usuario.end_email
        return email

    security.declarePublic('mailPassword')

    def mailPassword(self, forgotten_userid, REQUEST):
        membership = getToolByName(self, 'portal_membership')
        member = membership.getMemberById(forgotten_userid)
        if member is None:
            msg = 'Usuário não encontrado!'
            raise ValueError(msg)
        email = self._getValidEmailAddress(member)
        if email is None or email == '':
            msg = 'Endereço de email não cadastrado!'
            raise ValueError(msg)
        method = self.pysc.password_email
        kw = {'email': email, 'member': member, 'password': member.getPassword()}
        if getattr(aq_base(method), 'isDocTemp', 0):
            mail_text = method(self, REQUEST, **kw)
        else:
            mail_text = method(**kw)
        host = self.MailHost
        try:
            host.send(mail_text)
            return self.generico.mail_password_response(self, REQUEST)
        except Exception as e:
            REQUEST.set('error_message', 'Ocorreu um erro ao enviar o email!')
            return self.REQUEST.RESPONSE.redirect(self.portal_url() + '/mail_password_form?error_message=' + str(e))

    def create_payload(self, cod_materia):
        data = {}
        for materia in self.zsql.materia_obter_zsql(cod_materia=cod_materia, ind_excluido=0):
            data['codmateria'] = materia.cod_materia
            data['tipo'] = materia.des_tipo_materia
            data['numero'] = materia.num_ident_basica
            data['ano'] = materia.ano_ident_basica
            data['ementa'] = materia.txt_ementa
            data['autoria'] = ''
            autores = self.zsql.autoria_obter_zsql(cod_materia=materia.cod_materia, ind_excluido=0)
            fields = autores.data_dictionary().keys()
            lista_autor = []
            for autor in autores:
                for field in fields:
                    nome_autor = autor['nom_autor_join']
                lista_autor.append(nome_autor)
            data['autoria'] = ', '.join(['%s' % (value) for value in lista_autor])
            data['linkarquivo'] = ''
            if hasattr(self.sapl_documentos.materia, str(materia.cod_materia) + '_texto_integral.pdf'):
                data['linkarquivo'] = self.portal_url() + '/sapl_documentos/materia/' + str(materia.cod_materia) + '_texto_integral.pdf'
            data['casalegislativa'] = self.props_sagl.nom_casa
            data['prazo'] = ''
            for tram in self.zsql.tramitacao_obter_zsql(cod_materia=cod_materia, ind_ult_tramitacao=1):
                if tram.dat_fim_prazo is not None:
                    data['prazo'] = tram.dat_fim_prazo

        serialized = json.dumps(data, sort_keys=True, indent=3)
        return json.loads(serialized)

    def protocolo_prefeitura(self, cod_materia):
        API_ENDPOINT = ""
        API_USER = ""
        API_PASSWORD = ""
        payload = self.create_payload(cod_materia)
        async_result = tasks.protocolo_prefeitura_task.delay(API_ENDPOINT, API_USER, API_PASSWORD, cod_materia, payload)
        return async_result.get()

    def cep_buscar(self, numcep):
        """
        Busca informações de endereço com base em um CEP (Código de Endereçamento Postal) fornecido.
        Args:
        numcep (str): O CEP a ser pesquisado.
        Returns:
            str: Uma string JSON contendo as informações de endereço, ou None se ocorrer um erro.
        """
        url = f'https://viacep.com.br/ws/{numcep}/json/'
        try:
            resposta = requests.get(url)
            resposta.raise_for_status()  # Lança HTTPError para respostas ruins (4xx ou 5xx)
            dic_requisicao = resposta.json()
            if 'erro' not in dic_requisicao: # ViaCEP usa a chave 'erro' para erros.
                cepDict = {
                    'logradouro': dic_requisicao.get('logradouro', ''),
                    'bairro': dic_requisicao.get('bairro', ''),
                    'cidade': dic_requisicao.get('localidade', ''),
                    'estado': dic_requisicao.get('uf', '')
                }
                return json.dumps(cepDict, ensure_ascii=False) # ensure_ascii=False para exibição correta de caracteres especiais.
            else:
                return None # Retorna None quando ocorre um erro.
        except requests.exceptions.RequestException as e:
            print(f"Erro durante a requisição: {e}")
            return None  # Retorna None em caso de erro na requisição.
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON: {e}")
            return None # Retorna None se o JSON estiver malformado.

    def make_qrcode(self, text):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        fp = BytesIO()
        img.save(fp, "PNG")
        return fp

    def assinar_proposicao(self, lista):
        for item in lista:
           storage_path = self.sapl_documentos.proposicao
           for proposicao in self.zsql.proposicao_obter_zsql(cod_proposicao=int(item)):
               string = self.pysc.proposicao_calcular_checksum_pysc(proposicao.cod_proposicao, senha=1)
               nom_autor = proposicao.nom_autor
               pdf_proposicao = str(proposicao.cod_proposicao) + '.pdf'
               pdf_assinado = str(proposicao.cod_proposicao) + '_signed.pdf'
               texto = 'Proposição eletrônica ' + string
           mensagem1 = 'Documento assinado digitalmente com usuário e senha por ' + nom_autor + '.'
           mensagem2 = 'Para verificar a autenticidade do documento leia o qrcode.'
           arq = getattr(storage_path, pdf_proposicao)
           arquivo = BytesIO(bytes(arq.data))
           existing_pdf = pymupdf.open(stream=arquivo)
           numPages = existing_pdf.page_count
           stream = self.make_qrcode(text=self.url() + '/sapl_documentos/proposicao/' + proposicao.cod_proposicao + '_signed.pdf')
           for page_index, i in enumerate(range(len(existing_pdf))):
               w = existing_pdf[page_index].rect.width
               h = existing_pdf[page_index].rect.height
               margin = 5
               left = 10 - margin
               bottom = h - 50 - margin
               black = pymupdf.pdfcolor["black"]
               numero = "Pág. %s/%s" % (i+1, numPages)
               # qrcode
               rect = pymupdf.Rect(left, bottom, left + 50, bottom + 50)  # qrcode bottom left square
               existing_pdf[page_index].insert_image(rect, stream=stream)
               text2 = mensagem2
               # margem direita
               text3 = texto + ' - ' + mensagem1
               x = w - 8 - margin #largura
               y = h - 30 - margin # altura
               existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)
               # margem inferior
               p1 = pymupdf.Point(w - 40 - margin, h - 12) # numero de pagina documento
               p2 = pymupdf.Point(60, h - 12) # margem inferior
               shape = existing_pdf[page_index].new_shape()
               shape.draw_circle(p1,1)
               shape.draw_circle(p2,1)
               shape.insert_text(p1, numero, fontname = "helv", fontsize = 8)
               shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
               shape.commit()
           content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
           if hasattr(storage_path,pdf_assinado):
              pdf = getattr(storage_path, pdf_assinado)
              pdf.update_data(content)
           else:
              storage_path.manage_addFile(id=pdf_assinado,file=content, title='Proposição '+ str(item))
              pdf = getattr(storage_path, pdf_assinado)
           pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
        if len(lista) == 1:
           redirect_url = self.portal_url()+'/cadastros/proposicao/proposicao_mostrar_proc?cod_proposicao=' + proposicao.cod_proposicao
           REQUEST = self.REQUEST
           RESPONSE = REQUEST.RESPONSE
           RESPONSE.redirect(redirect_url)
        else:
           redirect_url = self.portal_url()+'/cadastros/proposicao/proposicao_index_html?ind_enviado=0'
           REQUEST = self.REQUEST
           RESPONSE = REQUEST.RESPONSE
           RESPONSE.redirect(redirect_url)

    def baixar_atas_comissao(self, lista):
        merger = pymupdf.open()
        for item in lista:
           storage_path = self.sapl_documentos.reuniao_comissao
           arq = getattr(storage_path, item['ata'])
           arquivo_ata = BytesIO(bytes(arq.data))
           arquivo_ata.seek(0)
           texto_ata = pymupdf.open(stream=arquivo_ata)
           texto_ata.bake()
           merger.insert_pdf(texto_ata)
           arquivo_ata.close()
        final_pdf_content = merger.tobytes()
        download_name = 'Atas de Comissão'
        self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/pdf')
        self.REQUEST.RESPONSE.setHeader('Content-Disposition', f'inline; filename={download_name}')
        return final_pdf_content

    def adicionar_carimbo(self, cod_sessao_plen, nom_resultado, cod_materia):
        id_sessao = ''
        data = DateTime().strftime('%d/%m/%Y')
        data1 = DateTime().strftime('%Y/%m/%d')
        nom_presidente = ''
        # Obtém dados da sessão
        if cod_sessao_plen != '0' and cod_sessao_plen != '':
            for item in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=cod_sessao_plen):
                for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=item.tip_sessao):
                    id_sessao = f"{item.num_sessao_plen}ª {self.sapl_documentos.props_sagl.reuniao_sessao} {tipo.nom_sessao}"
                data = item.dat_inicio_sessao
                data1 = item.dat_inicio
                num_legislatura = item.num_legislatura
            for composicao in self.zsql.composicao_mesa_sessao_obter_zsql(cod_sessao_plen=cod_sessao_plen, cod_cargo=1, ind_excluido=0):
                for parlamentar in self.zsql.parlamentar_obter_zsql(cod_parlamentar=composicao.cod_parlamentar):
                    nom_presidente = str(parlamentar.nom_parlamentar.upper())
        if nom_presidente == '':
            for sleg in self.zsql.periodo_comp_mesa_obter_zsql(data=data1):
                for cod_presidente in self.zsql.composicao_mesa_obter_zsql(cod_periodo_comp=sleg.cod_periodo_comp, cod_cargo=1):
                    for presidencia in self.zsql.parlamentar_obter_zsql(cod_parlamentar=cod_presidente.cod_parlamentar):
                        nom_presidente = str(presidencia.nom_parlamentar.upper())
        # Dados do carimbo
        texto = f"{nom_resultado.upper()}"
        sessao = f"{id_sessao} - {data}"
        cargo = "Presidente"
        presidente = f"{cargo}: {nom_presidente} "
        texto_completo = f"{texto}\n{sessao}\n{presidente}"
        # Adiciona carimbo aos documentos
        for materia in self.zsql.materia_obter_zsql(cod_materia=cod_materia):
            storage_path = self.sapl_documentos.materia
            nom_pdf_saida = f"{materia.cod_materia}_texto_integral.pdf"
            nom_pdf_redacao = f"{materia.cod_materia}_redacao_final.pdf"
            # Adiciona carimbo no texto integral
            if hasattr(storage_path, nom_pdf_saida):
                arq = getattr(storage_path, nom_pdf_saida)
                arquivo = BytesIO(bytes(arq.data))
                existing_pdf = pymupdf.open(stream=arquivo)
                if existing_pdf.page_count > 0:
                    page = existing_pdf[0]
                    w = page.rect.width
                    h = page.rect.height
                    margin = 10
                    black = pymupdf.pdfcolor["black"]
                    p2 = pymupdf.Point(w - 170 - margin, margin + 90) # Margem superior
                    shape = page.new_shape()
                    shape.draw_circle(p2,1)
                    shape.insert_text(p2, texto_completo, fontname = "helv", fontsize = 8, rotate=0)
                    shape.commit()
                    content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
                    arq.manage_upload(file=content)
            # Adiciona carimbo na redação final
            if hasattr(storage_path, nom_pdf_redacao):
                arq = getattr(storage_path, nom_pdf_redacao)
                arquivo = BytesIO(bytes(arq.data))
                existing_pdf = pymupdf.open(stream=arquivo)
                if existing_pdf.page_count > 0:
                    page = existing_pdf[0]
                    w = page.rect.width
                    h = page.rect.height
                    margin = 10
                    black = pymupdf.pdfcolor["black"]
                    p2 = pymupdf.Point(w - 170 - margin, margin + 90) # Margem superior
                    shape = page.new_shape()
                    shape.draw_circle(p2,1)
                    shape.insert_text(p2, texto_completo, fontname = "helv", fontsize = 8, rotate=0)
                    shape.commit()
                    content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
                    arq.manage_upload(file=content)

    @staticmethod
    def format_cpf(cpf: str | None) -> str:
        """Formata um CPF com pontuação padrão.
        Args:
            cpf: String contendo CPF (com ou sem formatação)
        Returns:
            String formatada como XXX.XXX.XXX-XX ou string vazia se inválido
        """
        if not cpf or not isinstance(cpf, str):
            return ""
        cleaned = re.sub(r'[^0-9]', '', cpf)
        if len(cleaned) != CPF_LENGTH:
            return cpf  # Retorna original se não tiver 11 dígitos
        return f"{cleaned[:3]}.{cleaned[3:6]}.{cleaned[6:9]}-{cleaned[9:]}"

    @staticmethod
    def parse_pdf_timestamp(timestamp_str: str) -> str:
        """Parse PDF timestamp string in various formats.
        Handles formats:
        - D:YYYYMMDDHHMMSSZ
        - D:YYYYMMDDHHMMSS+HH'MM'
        - D:YYYYMMDDHHMMSS-HH'MM'
        Args:
            timestamp_str: Timestamp string from PDF signature
        Returns:
            ISO 8601 formatted string or original string if parsing fails
        """
        if not timestamp_str or not isinstance(timestamp_str, str):
            return ""

        if not timestamp_str.startswith('D:'):
            return timestamp_str  # return original if not in expected format
        # Remove 'D:' prefix
        ts_clean = timestamp_str[2:]
        try:
            # Handle timezone offset with apostrophes
            if "'" in ts_clean:
                # Replace apostrophes with colons in timezone offset
                ts_parts = ts_clean.split("'")
                if len(ts_parts) >= 2:
                    # Reconstruct with proper timezone separator
                    ts_clean = ts_parts[0] + ":" + ts_parts[1]
            # Parse with dateutil
            dt = parse(ts_clean)
            return dt.isoformat()
        except Exception as e:
            warnings.warn(
                f"Failed to parse PDF timestamp '{timestamp_str}'. Error: {str(e)}",
                RuntimeWarning
            )
            return timestamp_str  # fallback to original string

    def parse_signatures(self, raw_signature_data: bytes | None) -> list[dict]:
        """Parse raw CMS signature data to extract signer information.
        Args:
            raw_signature_data: Bytes containing CMS signature data
        Returns:
            List of dictionaries with signer information
        """
        if not raw_signature_data:
            return []

        signers_data = []
        try:
            info = cms.ContentInfo.load(raw_signature_data)
            signed_data = info['content']
            try:
                certificates_field = signed_data['certificates']
            except KeyError:
                warnings.warn(
                    "Campo 'certificates' não encontrado na estrutura SignedData da assinatura digital.",
                    RuntimeWarning
                )
                return []
            if certificates_field is None:
                warnings.warn(
                    "Campo 'certificates' está presente mas é nulo na assinatura digital.",
                    RuntimeWarning
                )
                return []
            if not certificates_field:
                warnings.warn(
                    "Lista de 'certificates' está vazia na assinatura digital.",
                    RuntimeWarning
                )
                return []
            for cert_obj in certificates_field:
                try:
                    cert_native = cert_obj.native['tbs_certificate']
                    subject = cert_native.get('subject', {})
                    issuer = cert_native.get('issuer', {})
                    common_name = subject.get('common_name', '')
                    parts = common_name.split(':', 1)
                    signer_name_from_cert = parts[0].strip()
                    cpf_from_cert = self.format_cpf(parts[1].strip()) if len(parts) > 1 else ''
                    organization_name_subject = subject.get('organization_name', '')
                    organization_name_issuer = issuer.get('organization_name', '')
                    signers_data.append({
                        'type': organization_name_subject,
                        'signer': signer_name_from_cert,
                        'cpf': cpf_from_cert,
                        'oname': organization_name_issuer
                    })
                except Exception as e:
                    warnings.warn(
                        f"Erro ao processar certificado individual: {e}. "
                        f"Certificado (início): {str(cert_obj.contents)[:100]}...",
                        RuntimeWarning
                    )
                    continue
        except Exception as e:
            warnings.warn(
                f"Erro ao interpretar estrutura da assinatura digital: {e}",
                RuntimeWarning
            )
            return []
        return signers_data

    def get_signatures(self, fileStream: BytesIO) -> list[dict]:
        """Extrai informações de todas as assinaturas digitais em um PDF.
        Args:
            fileStream: BytesIO contendo o conteúdo do PDF
        Returns:
            Lista de dicionários com informações das assinaturas, ordenadas por data
        """
        fileStream.seek(0)
        try:
            reader = pypdf.PdfReader(fileStream)
        except PdfReadError as e:
            warnings.warn(
                f"Erro ao ler o PDF com pypdf: {e}. Tentando reparar ou retornando vazio.",
                RuntimeWarning
            )
            return []
        pdf_fields = reader.get_fields()
        lst_signers = []
        if not pdf_fields:
            return []
        signature_field_values = [
            f.value for f in pdf_fields.values()
            if f and getattr(f, 'field_type', None) == '/Sig' and f.value
        ]
        for sig_dict in signature_field_values:
            signing_time_str = None
            if '/M' in sig_dict:
                original_m_field = sig_dict['/M']
                signing_time_str = self.parse_pdf_timestamp(original_m_field)
            name_from_pdf_dict = None
            cpf_from_pdf_dict = None
            if '/Name' in sig_dict:
                name_parts = sig_dict['/Name'].split(':', 1)
                name_from_pdf_dict = name_parts[0].strip()
                if len(name_parts) > 1:
                    cpf_from_pdf_dict = self.format_cpf(name_parts[1].strip())
            raw_signature_data = sig_dict.get('/Contents')
            parsed_asn1_signers = self.parse_signatures(raw_signature_data)
            if parsed_asn1_signers:
                for asn1_signer_info in parsed_asn1_signers:
                    final_name = asn1_signer_info.get('signer') or name_from_pdf_dict
                    final_cpf = asn1_signer_info.get('cpf') or cpf_from_pdf_dict
                    final_cpf_formatted = self.format_cpf(final_cpf) if final_cpf else None
                    dic = {
                        'signer_name': final_name,
                        'signer_cpf': final_cpf_formatted,
                        'signing_time': signing_time_str,
                        'signer_certificate': asn1_signer_info.get('oname')
                    }
                    lst_signers.append(dic)
            elif name_from_pdf_dict:
                dic = {
                    'signer_name': name_from_pdf_dict,
                    'signer_cpf': cpf_from_pdf_dict,
                    'signing_time': signing_time_str,
                    'signer_certificate': ''
                }
                lst_signers.append(dic)
        def get_sort_key(item):
            st_str = item.get('signing_time')
            if st_str:
                try:
                    return parse(st_str)
                except:
                    return datetime.min
            return datetime.min
        lst_signers.sort(key=get_sort_key, reverse=True)
        return lst_signers

    def proposicao_autuar(self,cod_proposicao):
        nom_pdf_proposicao = str(cod_proposicao) + "_signed.pdf"
        arq = getattr(self.sapl_documentos.proposicao, nom_pdf_proposicao)
        fileStream = BytesIO(bytes(arq.data))
        fileStream = self.reparar_pdf_stream(fileStream)
        reader = pypdf.PdfReader(fileStream)
        fields = reader.get_fields()
        signers = []
        nom_autor = None
        if fields != None:
            signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
            if signature_field_values is not None:
               signers = self.get_signatures(fileStream)
        qtde_assinaturas = len(signers)
        for signer in signers:
            nom_autor = signer['signer_name']
        outros = ''
        if qtde_assinaturas == 2:
           outros = " e outro"
        if qtde_assinaturas > 2:
           outros = " e outros"
        cod_validacao_doc = ''
        for validacao in self.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao,tipo_doc='proposicao',ind_assinado=1):
            cod_validacao_doc = str(self.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc))
        for proposicao in self.zsql.proposicao_obter_zsql(cod_proposicao=cod_proposicao):
            num_proposicao = proposicao.cod_proposicao
            if nom_autor == None:
               nom_autor = proposicao.nom_autor
            info_protocolo = '- Recebido em ' + proposicao.dat_recebimento + '.'
            tipo_proposicao = proposicao.des_tipo_proposicao
            if proposicao.ind_mat_ou_doc == "M":
               for materia in self.zsql.materia_obter_zsql(cod_materia=proposicao.cod_mat_ou_doc):
                   if materia.num_protocolo != None and materia.num_protocolo != '':
                      for protocolo in self.zsql.protocolo_obter_zsql(num_protocolo=materia.num_protocolo, ano_protocolo=materia.ano_ident_basica):
                          info_protocolo = ' - Prot. ' + str(protocolo.num_protocolo) + '/' + str(protocolo.ano_protocolo) + ' ' + str(DateTime(protocolo.dat_protocolo, datefmt='international').strftime('%d/%m/%Y')) + ' ' + protocolo.hor_protocolo + '.'
                   texto = str(materia.des_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                   storage_path = self.sapl_documentos.materia
                   nom_pdf_saida = str(materia.cod_materia) + "_texto_integral.pdf"
            elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao!='Emenda' and proposicao.des_tipo_proposicao!='Mensagem Aditiva' and proposicao.des_tipo_proposicao!='Substitutivo' and proposicao.des_tipo_proposicao!='Parecer' and proposicao.des_tipo_proposicao!='Parecer de Comissão'):
               for documento in self.zsql.documento_acessorio_obter_zsql(cod_documento=proposicao.cod_mat_ou_doc):
                   for materia in self.zsql.materia_obter_zsql(cod_materia=documento.cod_materia):
                       materia = str(materia.sgl_tipo_materia)+' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
                   texto = str(documento.des_tipo_documento) + ' - ' + str(materia)
                   storage_path = self.sapl_documentos.materia
                   nom_pdf_saida = str(documento.cod_documento) + ".pdf"
            elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Emenda' or proposicao.des_tipo_proposicao=='Mensagem Aditiva'):
               for emenda in self.zsql.emenda_obter_zsql(cod_emenda=proposicao.cod_emenda):
                   for materia in self.zsql.materia_obter_zsql(cod_materia=emenda.cod_materia):
                       materia = str(materia.sgl_tipo_materia)+' nº '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
                   info_protocolo = '- Recebida em ' + proposicao.dat_recebimento + '.'
                   texto = 'Emenda ' + str(emenda.des_tipo_emenda)+ ' nº ' + str(emenda.num_emenda) + ' ao ' + str(materia)
                   storage_path = self.sapl_documentos.emenda
                   nom_pdf_saida = str(emenda.cod_emenda) + "_emenda.pdf"
            elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Substitutivo'):
               for substitutivo in self.zsql.substitutivo_obter_zsql(cod_substitutivo=proposicao.cod_substitutivo):
                   for materia in self.zsql.materia_obter_zsql(cod_materia=substitutivo.cod_materia):
                       materia = str(materia.sgl_tipo_materia)+ ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                   texto = 'Substitutivo nº ' + str(substitutivo.num_substitutivo) + ' ao ' + str(materia)
                   storage_path = self.sapl_documentos.substitutivo
                   nom_pdf_saida = str(substitutivo.cod_substitutivo) + "_substitutivo.pdf"
            elif proposicao.ind_mat_ou_doc=='D' and (proposicao.des_tipo_proposicao=='Parecer' or proposicao.des_tipo_proposicao=='Parecer de Comissão'):
               for relatoria in self.zsql.relatoria_obter_zsql(cod_relatoria=proposicao.cod_parecer, ind_excluido=0): 
                   for comissao in self.zsql.comissao_obter_zsql(cod_comissao=relatoria.cod_comissao):
                       sgl_comissao = comissao.sgl_comissao
                   for materia in self.zsql.materia_obter_zsql(cod_materia=relatoria.cod_materia):
                       materia = str(materia.sgl_tipo_materia) + ' nº ' + str(materia.num_ident_basica) + '/' + str(materia.ano_ident_basica)
                   texto = 'Parecer ' + sgl_comissao + ' nº ' + str(relatoria.num_parecer) + '/' + str(relatoria.ano_parecer) + ' ao ' + str(materia)
                   storage_path = self.sapl_documentos.parecer_comissao
                   nom_pdf_saida = str(relatoria.cod_relatoria) + "_parecer.pdf"
        mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
        mensagem2 = 'Para validar visite ' + self.url()+'/conferir_assinatura'+' e informe o código '+ cod_validacao_doc
        existing_pdf = pymupdf.open(stream=fileStream)
        numPages = existing_pdf.page_count
        doc = pymupdf.open()
        install_home = os.environ.get('INSTALL_HOME')
        dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png')
        with open(dirpath, "rb") as arq:
             image = arq.read()
        for validacao in self.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao,tipo_doc='proposicao',ind_assinado=1):
            stream = self.make_qrcode(text=self.url()+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(validacao.cod_assinatura_doc))
            for page_index, i in enumerate(range(len(existing_pdf))):
                w = existing_pdf[page_index].rect.width
                h = existing_pdf[page_index].rect.height
                margin = 5
                left = 10 - margin
                bottom = h - 50 - margin
                bottom2 = h - 38
                right = w - 53
                black = pymupdf.pdfcolor["black"]
                # qrcode
                rect = pymupdf.Rect(left, bottom, left + 50, bottom + 50)  # qrcode bottom left square
                existing_pdf[page_index].insert_image(rect, stream=stream)
                text2 = mensagem2
                # margem direita
                numero = "Pág. %s/%s" % (i+1, numPages)
                text3 = numero + ' - ' + texto + info_protocolo + ' ' + mensagem1
                x = w - 8 - margin #largura
                y = h - 30 - margin # altura
                existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)
                # logo icp
                rect_icp = pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45)
                existing_pdf[page_index].insert_image(rect_icp, stream=image)
                # margem inferior
                p1 = pymupdf.Point(w - 40 - margin, h - 12) # numero de pagina documento
                p2 = pymupdf.Point(60, h - 12) # margem inferior
                shape = existing_pdf[page_index].new_shape()
                shape.draw_circle(p1,1)
                shape.draw_circle(p2,1)
                shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
                shape.commit()
            break
        w = existing_pdf[0].rect.width
        h = existing_pdf[0].rect.height
        # tipo, numero e ano
        #if tipo_proposicao != 'Parecer' and tipo_proposicao != 'Parecer de Comissão':
        rect = pymupdf.Rect(40, 120, w-20, 170)
        existing_pdf[0].insert_textbox(rect, str(texto).upper(), fontname = "hebo", fontsize = 12, align=pymupdf.TEXT_ALIGN_CENTER)
        metadata = {"title": texto, "author": nom_autor}
        existing_pdf.set_metadata(metadata)
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        if nom_pdf_saida in storage_path:
           pdf=storage_path[nom_pdf_saida]
           pdf.manage_upload(file=content)
        else:
           storage_path.manage_addFile(id=nom_pdf_saida,file=content,title=texto)
           pdf=storage_path[nom_pdf_saida]
        pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)

    def reparar_pdf_stream(self, file_stream: BytesIO) -> BytesIO:
        file_stream.seek(0)
        original = file_stream.read()
        try:
            buffer = BytesIO()
            with pikepdf.open(BytesIO(original)) as pdf:
                pdf.remove_unreferenced_resources()
                pdf.save(buffer, linearize=True)
            reparado = buffer.getvalue()
            fitz.open(stream=reparado, filetype="pdf")  # valida
            return BytesIO(reparado)
        except Exception:
            # fallback: rasteriza com fitz
            doc = fitz.open(stream=original, filetype="pdf")
            novo = fitz.open()
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = pix.tobytes("jpeg", 90)
                rect = fitz.Rect(0, 0, pix.width, pix.height)
                nova = novo.new_page(width=pix.width, height=pix.height)
                nova.insert_image(rect, stream=img)
            out = BytesIO()
            novo.save(out, garbage=4, deflate=True)
            return out

    def margem_inferior(self, codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename):
        arq = getattr(self.sapl_documentos.documentos_assinados, filename)
        fileStream = BytesIO(bytes(arq.data))
        fileStream = self.reparar_pdf_stream(fileStream)
        reader = pypdf.PdfReader(fileStream)
        fields = reader.get_fields()
        signers = []
        nom_autor = None
        if fields != None:
            signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
            if signature_field_values is not None:
               signers = self.get_signatures(fileStream)
        qtde_assinaturas = len(signers)
        for signer in signers:
            nom_autor = signer['signer_name']
        outros = ''
        if qtde_assinaturas == 2:
           outros = " e outro"
        if qtde_assinaturas > 2:
           outros = " e outros"
        if nom_autor == None:
            for usuario in self.zsql.usuario_obter_zsql(cod_usuario=cod_usuario):
                nom_autor = usuario.nom_completo
                break
        string = str(self.cadastros.assinatura.format_verification_code(cod_assinatura_doc))
        # Variáveis para obtenção de dados e local de armazenamento por tipo de documento
        for storage in self.zsql.assinatura_storage_obter_zsql(tip_documento=tipo_doc):
            if tipo_doc == 'anexo_sessao':
               nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
               nom_pdf_documento = str(codigo) + '_anexo_' + str(anexo) + '.pdf'
            elif tipo_doc == 'anexo_peticao':
               nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
               nom_pdf_documento = str(codigo) + '_anexo_' + str(anexo) + '.pdf'
            else:
               nom_pdf_assinado = str(cod_assinatura_doc) + '.pdf'
               nom_pdf_documento = str(codigo) + str(storage.pdf_file)
        if tipo_doc == 'materia' or tipo_doc == 'doc_acessorio' or tipo_doc == 'redacao_final':
           storage_path = self.sapl_documentos.materia
           if tipo_doc == 'materia' or tipo_doc == 'redacao_final':
              for metodo in self.zsql.materia_obter_zsql(cod_materia=codigo):
                  num_documento = metodo.num_ident_basica
                  if tipo_doc == 'materia':
                     texto = str(metodo.des_tipo_materia)+' nº '+ str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica)
                  elif tipo_doc == 'redacao_final':
                     texto = 'Redação Final do ' + str(metodo.sgl_tipo_materia)+' nº '+ str(metodo.num_ident_basica) + '/' + str(metodo.ano_ident_basica)
           elif tipo_doc == 'doc_acessorio':
              for metodo in self.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
                  for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                      materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
                  texto = str(metodo.nom_documento) + ' - ' + str(materia)
        elif tipo_doc == 'emenda':
           storage_path = self.sapl_documentos.emenda
           for metodo in self.zsql.emenda_obter_zsql(cod_emenda=codigo):
               for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
               texto = 'Emenda ' + str(metodo.des_tipo_emenda) + ' nº ' + str(metodo.num_emenda) + ' ao ' + str(materia)
        elif tipo_doc == 'substitutivo':
           storage_path = self.sapl_documentos.substitutivo
           for metodo in self.zsql.substitutivo_obter_zsql(cod_substitutivo=codigo):
               for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
               texto = 'Substitutivo nº ' + str(metodo.num_substitutivo) + ' ao ' + str(materia)
        elif tipo_doc == 'tramitacao':
           storage_path = self.sapl_documentos.materia.tramitacao
           for metodo in self.zsql.tramitacao_obter_zsql(cod_tramitacao=codigo):
               materia = str(metodo.sgl_tipo_materia)+' '+ str(metodo.num_ident_basica)+'/'+str(metodo.ano_ident_basica)
               texto = 'Tramitação nº '+ str(metodo.cod_tramitacao) + ' - ' + str(materia)
        elif tipo_doc == 'parecer_comissao':
           storage_path = self.sapl_documentos.parecer_comissao
           for metodo in self.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   sgl_comissao = str(comissao.sgl_comissao)
               parecer = str(metodo.num_parecer)+'/'+str(metodo.ano_parecer)
               for materia in self.zsql.materia_obter_zsql(cod_materia=metodo.cod_materia):
                   materia = str(materia.sgl_tipo_materia)+' '+ str(materia.num_ident_basica)+'/'+str(materia.ano_ident_basica)
           texto = 'Parecer ' + str(sgl_comissao) + ' nº ' + str(parecer) + ' ao ' + str(materia)
        elif tipo_doc == 'pauta':
           storage_path = self.sapl_documentos.pauta_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(self.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + str(tipo.nom_sessao) + ' - ' + str(metodo.dat_inicio_sessao)
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
           texto = 'Pauta da ' + str(sessao)
        elif tipo_doc == 'resumo_sessao':
           storage_path = self.sapl_documentos.pauta_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(self.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ' - ' + str(metodo.dat_inicio_sessao)
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
           texto = 'Roteiro da ' + str(sessao)
        elif tipo_doc == 'ata':
           storage_path = self.sapl_documentos.ata_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(self.sapl_documentos.props_sagl.reuniao_sessao).upper() + ' ' + str(tipo.nom_sessao) + ' - ' + str(metodo.dat_inicio_sessao)
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo, ind_audiencia='1'):
               sessao = 'Audiência Pública nº ' + str(metodo.num_sessao_plen) + '/' + str(metodo.ano_sessao)
           texto = 'Ata da ' + str(sessao)
        elif tipo_doc == 'anexo_peticao':
           storage_path = self.sapl_documentos.peticao
           file_item =  str(codigo) + '_anexo_' + str(anexo) + '.pdf'
           title = getattr(self.sapl_documentos.peticao,file_item).title_or_id()
           texto = 'Anexo de petição: ' + str(title)
        elif tipo_doc == 'anexo_sessao':
           storage_path = self.sapl_documentos.anexo_sessao
           for metodo in self.zsql.sessao_plenaria_obter_zsql(cod_sessao_plen=codigo):
               for tipo in self.zsql.tipo_sessao_plenaria_obter_zsql(tip_sessao=metodo.tip_sessao):
                   sessao = str(metodo.num_sessao_plen) + 'ª ' + str(self.sapl_documentos.props_sagl.reuniao_sessao) + ' ' + str(tipo.nom_sessao) + ', de ' + str(metodo.dat_inicio_sessao)
           file_item =  str(codigo) + '_anexo_' + str(anexo) + '.pdf'
           title = getattr(self.sapl_documentos.anexo_sessao,file_item).title_or_id()
           texto = str(title) + ' da ' + str(sessao)
        elif tipo_doc == 'norma':
           storage_path = self.sapl_documentos.norma_juridica
           for metodo in self.zsql.norma_juridica_obter_zsql(cod_norma=codigo):
               texto = str(metodo.des_tipo_norma) + ' nº ' + str(metodo.num_norma) + '/' + str(metodo.ano_norma)
        elif tipo_doc == 'documento' or tipo_doc == 'doc_acessorio_adm':
           storage_path = self.sapl_documentos.administrativo
           if tipo_doc == 'documento':
              for metodo in self.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
                  num_documento = metodo.num_documento
                  texto = str(metodo.des_tipo_documento)+ ' nº ' + str(metodo.num_documento)+ '/' +str(metodo.ano_documento)
           elif tipo_doc == 'doc_acessorio_adm':
              for metodo in self.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
                  for documento in self.zsql.documento_administrativo_obter_zsql(cod_documento=metodo.cod_documento):
                      documento = str(documento.sgl_tipo_documento) +' '+ str(documento.num_documento)+'/'+str(documento.ano_documento)
                  texto = 'Doumento Acessório do ' + str(documento)
        elif tipo_doc == 'tramitacao_adm':
           storage_path = self.sapl_documentos.administrativo.tramitacao
           for metodo in self.zsql.tramitacao_administrativo_obter_zsql(cod_tramitacao=codigo):
               documento = str(metodo.sgl_tipo_documento)+' '+ str(metodo.num_documento)+'/'+str(metodo.ano_documento)
               texto = 'Tramitação nº '+ str(metodo.cod_tramitacao) + ' - ' + str(documento)
        elif tipo_doc == 'proposicao':
           storage_path = self.sapl_documentos.proposicao
           for metodo in self.zsql.proposicao_obter_zsql(cod_proposicao=codigo):
               texto = str(metodo.des_tipo_proposicao) +' nº ' + str(metodo.cod_proposicao)
        elif tipo_doc == 'protocolo':
           storage_path = self.sapl_documentos.protocolo
           for metodo in self.zsql.protocolo_obter_zsql(cod_protocolo=codigo):
               texto = 'Protocolo nº '+ str(metodo.num_protocolo) +'/' + str(metodo.ano_protocolo)
        elif tipo_doc == 'peticao':
           storage_path = self.sapl_documentos.peticao
           texto = 'Petição Eletrônica'
        elif tipo_doc == 'pauta_comissao':
           storage_path = self.sapl_documentos.reuniao_comissao
           for metodo in self.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = 'Pauta da ' + str(metodo.num_reuniao) + 'ª Reunião da ' + comissao.sgl_comissao + ', em ' + str(metodo.dat_inicio_reuniao)
        elif tipo_doc == 'ata_comissao':
           storage_path = self.sapl_documentos.reuniao_comissao
           for metodo in self.zsql.reuniao_comissao_obter_zsql(cod_reuniao=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = 'Ata da ' + str(metodo.num_reuniao) + 'ª Reunião da ' + comissao.sgl_comissao + ', em ' + str(metodo.dat_inicio_reuniao)
        elif tipo_doc == 'documento_comissao':
           storage_path = self.sapl_documentos.documento_comissao
           for metodo in self.zsql.documento_comissao_obter_zsql(cod_documento=codigo):
               for comissao in self.zsql.comissao_obter_zsql(cod_comissao=metodo.cod_comissao):
                   texto = metodo.txt_descricao + ' da ' + comissao.sgl_comissao
        mensagem1 = 'Esta é uma cópia do original assinado digitalmente por ' + nom_autor + outros
        mensagem2 = 'Para validar visite ' + self.url() + '/conferir_assinatura' + ' e informe o código ' + string
        existing_pdf = pymupdf.open(stream=fileStream)
        numPages = existing_pdf.page_count
        stream = self.make_qrcode(text=self.url()+'/conferir_assinatura_proc?txt_codigo_verificacao='+str(string))
        install_home = os.environ.get('INSTALL_HOME')
        dirpath = os.path.join(install_home, 'src/openlegis.sagl/openlegis/sagl/skins/imagens/logo-icp2.png')
        with open(dirpath, "rb") as arq:
             image = arq.read()
        for page_index, i in enumerate(range(len(existing_pdf))):
            w = existing_pdf[page_index].rect.width
            h = existing_pdf[page_index].rect.height
            margin = 5
            left = 10 - margin
            bottom = h - 50 - margin
            bottom2 = h - 38
            right = w - 53
            black = pymupdf.pdfcolor["black"]
            # qrcode
            rect = pymupdf.Rect(left, bottom, left + 50, bottom + 50)  # qrcode bottom left square
            existing_pdf[page_index].insert_image(rect, stream=stream)
            text2 = mensagem2
            # logo icp
            rect_icp = pymupdf.Rect(right, bottom2, right + 45, bottom2 + 45)
            existing_pdf[page_index].insert_image(rect_icp, stream=image)
            # margem direita
            numero = "Pág. %s/%s" % (i+1, numPages)
            text3 = numero + ' - ' + texto + ' - ' + mensagem1
            x = w - 8 - margin #largura
            y = h - 50 - margin # altura
            existing_pdf[page_index].insert_text((x, y), text3, fontsize=8, rotate=90)
            # margem inferior
            p1 = pymupdf.Point(w - 40 - margin, h - 12) # numero de pagina documento
            p2 = pymupdf.Point(60, h - 12) # margem inferior
            shape = existing_pdf[page_index].new_shape()
            shape.draw_circle(p1,1)
            shape.draw_circle(p2,1)
            #shape.insert_text(p1, numero, fontname = "helv", fontsize = 8)
            shape.insert_text(p2, text2, fontname = "helv", fontsize = 8, rotate=0)
            shape.commit()
        content = existing_pdf.tobytes(deflate=True, garbage=3, use_objstms=1)
        if hasattr(storage_path, nom_pdf_documento):
           pdf = getattr(storage_path, nom_pdf_documento)
           pdf.manage_upload(file=content)
        else:
           storage_path.manage_addFile(id=nom_pdf_documento,file=content,title=texto)
           pdf = getattr(storage_path, nom_pdf_documento)
        if tipo_doc == 'parecer_comissao':
           for relat in self.zsql.relatoria_obter_zsql(cod_relatoria=codigo):
               for tipo in self.zsql.tipo_fim_relatoria_obter_zsql(tip_fim_relatoria = relat.tip_fim_relatoria):
                   if tipo.des_fim_relatoria=='Aguardando apreciação':
                      pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
                   else:
                      pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
        elif tipo_doc == 'doc_acessorio':
           for documento in self.zsql.documento_acessorio_obter_zsql(cod_documento=codigo):
               if str(documento.ind_publico) == '1':
                  pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
               elif str(documento.ind_publico) == '0':
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        elif tipo_doc == 'documento':
           for documento in self.zsql.documento_administrativo_obter_zsql(cod_documento=codigo):
               if str(documento.ind_publico) == '1':
                  pdf.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
               elif str(documento.ind_publico) == '0':
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        elif tipo_doc == 'doc_acessorio_adm':
           for doc in self.zsql.documento_acessorio_administrativo_obter_zsql(cod_documento_acessorio=codigo):
               if str(doc.ind_publico) == '1':
                  pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)
               if str(doc.ind_publico) == '0':
                  pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        elif tipo_doc == 'peticao' or tipo_doc == 'anexo_peticao':
           pdf.manage_permission('View', roles=['Manager','Authenticated'], acquire=0)
        else:
           pdf.manage_permission('View', roles=['Manager','Anonymous'], acquire=1)

        return 'ok'

    # Tarefas assincronas

    def index_file(self, url):
        try:
            arquivo = self.unrestrictedTraverse(url)
            with BytesIO(bytes(arquivo.data)) as arquivo:
                 pdfbase64 = base64.b64encode(arquivo.getvalue()).decode('utf8')
            async_result = tasks.indexar_arquivo_task.delay(pdfbase64)
            return async_result.get()
        except Exception as e:
            print(f"Erro ao processar o arquivo PDF: {e}")
            return []

    def margem_inferior_async(self, codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename):
        portal_url = str(self.url())
        async_result = tasks.margem_inferior_task.delay(codigo, anexo, tipo_doc, cod_assinatura_doc, cod_usuario, filename, portal_url)
        return async_result

    def peticao_autuar(self, cod_peticao):
        portal_url = str(self.url())
        async_result = tasks.peticao_autuar_task.delay(cod_peticao, portal_url)
        return async_result

    def proposicao_autuar_async(self, cod_proposicao):
        portal_url = str(self.url())
        async_result = tasks.proposicao_autuar_task.delay(cod_proposicao, portal_url)
        return async_result

    def adicionar_carimbo_async(self, cod_sessao_plen, nom_resultado, cod_materia):
        async_result = tasks.adicionar_carimbo_task.delay(cod_sessao_plen, nom_resultado, cod_materia)
        return async_result

InitializeClass(SAGLTool)
