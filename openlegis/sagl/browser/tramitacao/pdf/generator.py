# -*- coding: utf-8 -*-
"""Gerador de PDF para despachos de tramitação usando SQLAlchemy"""

from typing import Dict, Any, Optional
from io import BytesIO
from datetime import datetime
from sqlalchemy.orm import Session, selectinload
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from xml.sax.saxutils import escape
from Acquisition import aq_inner, aq_base
import html2text
import requests
import re
import logging

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL/Pillow não disponível - não será possível processar transparência de imagens")

from openlegis.sagl.models.models import (
    Tramitacao, TramitacaoAdministrativo,
    MateriaLegislativa, DocumentoAdministrativo,
    UnidadeTramitacao, Usuario, StatusTramitacao, StatusTramitacaoAdministrativo,
    Localidade, Autoria, Autor, TipoMateriaLegislativa, TipoDocumentoAdministrativo
)

logger = logging.getLogger(__name__)


class TramitacaoPDFGenerator:
    """Gera PDF de despacho de tramitação usando SQLAlchemy"""
    
    def __init__(self, session: Session, contexto_zope=None):
        """
        Args:
            session: Sessão SQLAlchemy
            contexto_zope: Contexto Zope para acessar repositório de arquivos e propriedades
        """
        self.session = session
        self.contexto_zope = contexto_zope
    
    def _resolver_site_real(self, contexto_zope):
        """
        Resolve o site real removendo wrappers (RequestContainer, etc).
        
        Args:
            contexto_zope: Contexto Zope que pode ser um wrapper
            
        Returns:
            Site real sem wrappers
        """
        site_real = contexto_zope
        
        # Tenta múltiplas estratégias para resolver o site real
        try:
            # Estratégia 1: aq_inner
            if hasattr(contexto_zope, '__class__') and 'RequestContainer' in str(type(contexto_zope)):
                site_inner = aq_inner(contexto_zope)
                if site_inner and 'RequestContainer' not in str(type(site_inner)):
                    site_real = site_inner
                else:
                    # Estratégia 2: aq_base
                    try:
                        site_base = aq_base(site_inner if site_inner else contexto_zope)
                        if site_base and 'RequestContainer' not in str(type(site_base)):
                            site_real = site_base
                    except Exception:
                        pass
                    
                    # Estratégia 3: aq_parent (se contexto_zope tem parent)
                    try:
                        if hasattr(contexto_zope, 'aq_parent'):
                            parent = contexto_zope.aq_parent
                            if parent and hasattr(parent, 'sapl_documentos'):
                                site_real = parent
                    except Exception:
                        pass
            
            # Estratégia 4: Se ainda é RequestContainer, tenta aq_getContext
            if hasattr(site_real, '__class__') and 'RequestContainer' in str(type(site_real)):
                try:
                    from Acquisition import aq_getContext
                    context = aq_getContext(site_real)
                    if context and hasattr(context, 'sapl_documentos'):
                        site_real = context
                except Exception:
                    pass
            
            # Verifica se o site_real tem sapl_documentos
            if not hasattr(site_real, 'sapl_documentos'):
                # Última tentativa: busca no contexto Zope original
                try:
                    if hasattr(contexto_zope, 'getSite'):
                        site_real = contexto_zope.getSite()
                    elif hasattr(contexto_zope, 'getPhysicalRoot'):
                        root = contexto_zope.getPhysicalRoot()
                        if hasattr(root, 'sagl') and hasattr(root.sagl, 'sapl_documentos'):
                            site_real = root.sagl
                except Exception:
                    pass
            
            # ✅ Estratégia adicional: se ainda é RequestContainer ou ImplicitAcquisitionWrapper, tenta acessar via getPhysicalRoot
            if hasattr(site_real, '__class__') and ('RequestContainer' in str(type(site_real)) or 'ImplicitAcquisitionWrapper' in str(type(site_real))):
                try:
                    # Tenta obter via getPhysicalRoot se disponível
                    if hasattr(site_real, 'getPhysicalRoot'):
                        try:
                            root = site_real.getPhysicalRoot()
                            if root and hasattr(root, 'sagl') and hasattr(root.sagl, 'sapl_documentos'):
                                site_real = root.sagl
                        except Exception as e:
                            logger.debug(f"Erro ao obter site via getPhysicalRoot: {e}")
                    
                    # Se ainda não tem sapl_documentos, tenta acessar diretamente via atributo (acquisition)
                    if not hasattr(site_real, 'sapl_documentos'):
                        try:
                            # Tenta acessar via acquisition (ImplicitAcquisitionWrapper pode ter acesso via acquisition)
                            if hasattr(site_real, '__of__'):
                                # Se for wrapper, tenta obter objeto base
                                from Acquisition import aq_inner, aq_base
                                inner = aq_inner(site_real)
                                base = aq_base(inner) if inner else None
                                
                                # Se tem getPhysicalRoot no base, tenta usar
                                if base and hasattr(base, 'getPhysicalRoot'):
                                    root = base.getPhysicalRoot()
                                    if root and hasattr(root, 'sagl') and hasattr(root.sagl, 'sapl_documentos'):
                                        site_real = root.sagl
                                # Se não, tenta acessar sagl diretamente no inner/base
                                elif inner and hasattr(inner, 'sagl') and hasattr(inner.sagl, 'sapl_documentos'):
                                    site_real = inner.sagl
                                elif base and hasattr(base, 'sagl') and hasattr(base.sagl, 'sapl_documentos'):
                                    site_real = base.sagl
                        except Exception as e:
                            logger.debug(f"Erro ao obter site via acquisition: {e}")
                        
                        # Se ainda não tem sapl_documentos, tenta via aq_parent recursivo
                        if not hasattr(site_real, 'sapl_documentos'):
                            current = site_real
                            for _ in range(5):  # Limita a 5 níveis para evitar loop infinito
                                try:
                                    if hasattr(current, 'aq_parent'):
                                        current = current.aq_parent
                                        if current and hasattr(current, 'sapl_documentos'):
                                            site_real = current
                                            break
                                        # Se current é sagl e tem sapl_documentos, usa
                                        if current and hasattr(current, 'sagl') and hasattr(current.sagl, 'sapl_documentos'):
                                            site_real = current.sagl
                                            break
                                    else:
                                        break
                                except:
                                    break
                except Exception as e:
                    logger.debug(f"Erro na estratégia adicional para resolver wrapper: {e}")
                    
        except Exception as e:
            logger.warning(f"Erro ao resolver site real: {e}")
        
        # Verificação final: se ainda não tem sapl_documentos, tenta acessar via sagl (se site é root/app)
        if not hasattr(site_real, 'sapl_documentos'):
            try:
                # Se site_real tem atributo 'sagl', tenta acessá-lo
                if hasattr(site_real, 'sagl'):
                    sagl_obj = site_real.sagl
                    if sagl_obj and hasattr(sagl_obj, 'sapl_documentos'):
                        site_real = sagl_obj
                        logger.debug(f"Site real resolvido via site.sagl (tipo: {type(site_real)})")
            except Exception as e:
                logger.debug(f"Erro ao acessar site.sagl: {e}")
        
        # Log final se ainda não tem sapl_documentos
        if not hasattr(site_real, 'sapl_documentos'):
            logger.warning(f"Não foi possível resolver site com sapl_documentos. Tipo: {type(site_real)}, hasattr(sagl): {hasattr(site_real, 'sagl')}")
        
        return site_real
    
    def preparar_dados_tramitacao(
        self,
        tipo: str,
        cod_tramitacao: int
    ) -> Dict[str, Any]:
        """
        Prepara dados da tramitação para geração de PDF (substitui lógica do .pysc)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            
        Returns:
            Dicionário com dados preparados
        """
        from DateTime import DateTime
        
        # ✅ CRÍTICO: Limpa cache da sessão antes de buscar tramitação
        # Isso garante que os dados mais recentes sejam buscados do banco
        # especialmente importante quando a task é executada logo após commit
        self.session.expunge_all()
        
        # Busca tramitação (força refresh do banco)
        if tipo == 'MATERIA':
            tram = self.session.query(Tramitacao).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao,
                Tramitacao.ind_excluido == 0
            ).first()
            if not tram:
                raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
        else:
            tram = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                TramitacaoAdministrativo.ind_excluido == 0
            ).first()
            if not tram:
                raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
        
        # ✅ Força refresh do objeto para garantir dados atualizados
        self.session.refresh(tram)
        
        # Obtém propriedades da casa (do contexto Zope)
        casa = {}
        if self.contexto_zope:
            try:
                site_real = self._resolver_site_real(self.contexto_zope)
                aux = site_real.sapl_documentos.props_sagl.propertyItems()
                for item in aux:
                    casa[item[0]] = item[1]
            except Exception as e:
                logger.warning(f"Erro ao obter propriedades da casa: {e}")
        
        # Obtém localidade
        localidade = None
        if casa.get('cod_localidade'):
            localidade = self.session.query(Localidade).filter(
                Localidade.cod_localidade == casa['cod_localidade']
            ).first()
        
        # Prepara rodapé
        rodape = casa.copy()
        data_emissao = DateTime(datefmt='international').strftime("%d/%m/%Y")
        rodape['data_emissao'] = data_emissao
        
        if localidade:
            rodape['nom_localidade'] = f"   {localidade.nom_localidade}"
            rodape['sgl_uf'] = localidade.sgl_uf
        
        # Obtém estado
        nom_estado = ''
        if localidade:
            estado = self.session.query(Localidade).filter(
                Localidade.tip_localidade == 'u',
                Localidade.sgl_uf == localidade.sgl_uf
            ).first()
            if estado:
                nom_estado = estado.nom_localidade
        
        # Informações básicas
        inf_basicas_dic = {
            'nom_camara': casa.get('nom_casa', ''),
            'nom_estado': f"Estado de {nom_estado}" if nom_estado else ''
        }
        
        # Obtém logo/imagem
        imagem = None
        if self.contexto_zope:
            try:
                site_real = self._resolver_site_real(self.contexto_zope)
                if hasattr(site_real.sapl_documentos.props_sagl, 'cabecalho.png'):
                    imagem = site_real.sapl_documentos.props_sagl['cabecalho.png'].absolute_url()
                    inf_basicas_dic["custom_image"] = True
                elif hasattr(site_real.sapl_documentos.props_sagl, 'logo_casa.gif'):
                    imagem = site_real.sapl_documentos.props_sagl['logo_casa.gif'].absolute_url()
                    inf_basicas_dic["custom_image"] = False
                else:
                    site_real = self._resolver_site_real(self.contexto_zope)
                    imagem = site_real.imagens.absolute_url() + "/brasao.gif"
                    inf_basicas_dic["custom_image"] = False
            except Exception as e:
                logger.warning(f"Erro ao obter logo: {e}")
                imagem = None
        
        if not imagem:
            # Fallback
            imagem = '/brasao.gif'
            inf_basicas_dic["custom_image"] = False
        
        # Prepara dicionário de tramitação
        tramitacao_dic = {}
        
        # Código da tramitação (para título do PDF)
        tramitacao_dic['cod_tramitacao'] = cod_tramitacao
        
        # Data de tramitação
        if tram.dat_tramitacao:
            dat_tramitacao = DateTime(tram.dat_tramitacao, datefmt='international').strftime('%d/%m/%Y')
            tramitacao_dic['dat_tramitacao'] = dat_tramitacao
            tramitacao_dic['dat_extenso'] = self._data_por_extenso(dat_tramitacao)
        else:
            tramitacao_dic['dat_tramitacao'] = ''
            tramitacao_dic['dat_extenso'] = ''
        
        # Converte dat_encaminha para string se for datetime
        if tram.dat_encaminha:
            if hasattr(tram.dat_encaminha, 'strftime'):
                tramitacao_dic['dat_encaminha'] = tram.dat_encaminha.strftime('%d/%m/%Y')
            else:
                tramitacao_dic['dat_encaminha'] = str(tram.dat_encaminha)
        else:
            tramitacao_dic['dat_encaminha'] = None
        tramitacao_dic['txt_tramitacao'] = tram.txt_tramitacao or ''
        
        # Status
        if tipo == 'MATERIA':
            status = self.session.query(StatusTramitacao).filter(
                StatusTramitacao.cod_status == tram.cod_status
            ).first() if tram.cod_status else None
        else:
            status = self.session.query(StatusTramitacaoAdministrativo).filter(
                StatusTramitacaoAdministrativo.cod_status == tram.cod_status
            ).first() if tram.cod_status else None
        
        tramitacao_dic['des_status'] = status.des_status if status else ''
        
        # Data de fim de prazo
        if tram.dat_fim_prazo:
            tramitacao_dic['dat_fim_prazo'] = tram.dat_fim_prazo.strftime('%d/%m/%Y')
        else:
            # Calcula baseado no status
            if status and status.num_dias_prazo:
                from datetime import timedelta
                data_calculada = datetime.now() + timedelta(days=status.num_dias_prazo)
                tramitacao_dic['dat_fim_prazo'] = data_calculada.strftime('%d/%m/%Y')
            else:
                tramitacao_dic['dat_fim_prazo'] = ''
        
        # Urgência (apenas matérias)
        if tipo == 'MATERIA':
            tramitacao_dic['ind_urgencia'] = tram.ind_urgencia if hasattr(tram, 'ind_urgencia') else 0
        
        # Dados da entidade (matéria ou documento)
        if tipo == 'MATERIA':
            materia = self.session.query(MateriaLegislativa).options(
                selectinload(MateriaLegislativa.tipo_materia_legislativa)
            ).filter(
                MateriaLegislativa.cod_materia == tram.cod_materia
            ).first()
            
            if materia:
                # Autoria (carrega relacionamentos com selectinload)
                autorias = self.session.query(Autoria).options(
                    selectinload(Autoria.autor).selectinload(Autor.parlamentar),
                    selectinload(Autoria.autor).selectinload(Autor.comissao)
                ).filter(
                    Autoria.cod_materia == materia.cod_materia
                ).all()
                
                lista_autor = []
                for autoria in autorias:
                    if not autoria.autor:
                        continue
                    if autoria.autor.parlamentar:
                        lista_autor.append(autoria.autor.parlamentar.nom_parlamentar)
                    elif autoria.autor.comissao:
                        lista_autor.append(autoria.autor.comissao.nom_comissao)
                    elif autoria.autor.nom_autor:
                        lista_autor.append(autoria.autor.nom_autor)
                
                autoria_str = ', '.join(lista_autor) if lista_autor else ''
                txt_ementa = escape(materia.txt_ementa or '')
                
                # Obtém descrição do tipo de matéria
                des_tipo_materia = ''
                if materia.tipo_materia_legislativa:
                    des_tipo_materia = materia.tipo_materia_legislativa.des_tipo_materia or materia.tipo_materia_legislativa.sgl_tipo_materia or ''
                
                # Separa campos para melhor legibilidade
                tramitacao_dic['id_materia'] = (
                    f"{des_tipo_materia.upper()} N° "
                    f"{materia.num_ident_basica}/{materia.ano_ident_basica} - "
                    f"{autoria_str} - {txt_ementa}"
                )
                # Campos separados para renderização
                tramitacao_dic['identificacao_processo'] = f"{des_tipo_materia.upper()} N° {materia.num_ident_basica}/{materia.ano_ident_basica}"
                tramitacao_dic['autoria_processo'] = autoria_str
                tramitacao_dic['ementa_processo'] = txt_ementa
            else:
                tramitacao_dic['id_materia'] = ''
                tramitacao_dic['identificacao_processo'] = ''
                tramitacao_dic['autoria_processo'] = ''
                tramitacao_dic['ementa_processo'] = ''
        else:
            documento = self.session.query(DocumentoAdministrativo).options(
                selectinload(DocumentoAdministrativo.tipo_documento_administrativo)
            ).filter(
                DocumentoAdministrativo.cod_documento == tram.cod_documento
            ).first()
            
            if documento:
                txt_assunto = escape(documento.txt_assunto or '')
                txt_interessado = escape(documento.txt_interessado or '')
                
                # Obtém descrição do tipo de documento
                des_tipo_documento = ''
                if documento.tipo_documento_administrativo:
                    des_tipo_documento = documento.tipo_documento_administrativo.des_tipo_documento or documento.tipo_documento_administrativo.sgl_tipo_documento or ''
                
                tramitacao_dic['id_documento'] = (
                    f"{des_tipo_documento.upper()} N° "
                    f"{documento.num_documento}/{documento.ano_documento} - "
                    f"{txt_interessado} - {txt_assunto}"
                )
                # Campos separados para renderização
                tramitacao_dic['identificacao_processo'] = f"{des_tipo_documento.upper()} N° {documento.num_documento}/{documento.ano_documento}"
                tramitacao_dic['autoria_processo'] = txt_interessado  # Interessado para documentos
                tramitacao_dic['ementa_processo'] = txt_assunto  # Assunto para documentos
            else:
                tramitacao_dic['id_documento'] = ''
                tramitacao_dic['identificacao_processo'] = ''
                tramitacao_dic['autoria_processo'] = ''
                tramitacao_dic['ementa_processo'] = ''
        
        # Unidade de origem
        if tram.cod_unid_tram_local:
            unid_origem = self.session.query(UnidadeTramitacao).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UnidadeTramitacao.cod_unid_tramitacao == tram.cod_unid_tram_local
            ).first()
            
            if unid_origem:
                tramitacao_dic['unidade_origem'] = self._get_nome_unidade(unid_origem)
                
                # Ajusta nome da câmara se for poder executivo
                if unid_origem.orgao and localidade:
                    nom_orgao = unid_origem.orgao.nom_orgao or ''
                    if 'Poder Executivo' in nom_orgao:
                        inf_basicas_dic['nom_camara'] = f'Prefeitura Municipal de {localidade.nom_localidade}'
            else:
                tramitacao_dic['unidade_origem'] = ''
        else:
            tramitacao_dic['unidade_origem'] = ''
        
        # Usuário de origem
        if tram.cod_usuario_local:
            usu_origem = self.session.query(Usuario).filter(
                Usuario.cod_usuario == tram.cod_usuario_local
            ).first()
            
            if usu_origem:
                tramitacao_dic['usuario_origem'] = usu_origem.col_username or ''
                tramitacao_dic['nom_usuario_origem'] = usu_origem.nom_completo or ''
                tramitacao_dic['nom_cargo_usuario_origem'] = usu_origem.nom_cargo or ''
            else:
                tramitacao_dic['usuario_origem'] = ''
                tramitacao_dic['nom_usuario_origem'] = ''
                tramitacao_dic['nom_cargo_usuario_origem'] = ''
        else:
            tramitacao_dic['usuario_origem'] = ''
            tramitacao_dic['nom_usuario_origem'] = ''
            tramitacao_dic['nom_cargo_usuario_origem'] = ''
        
        # Unidade de destino
        if tram.cod_unid_tram_dest:
            unid_destino = self.session.query(UnidadeTramitacao).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UnidadeTramitacao.cod_unid_tramitacao == tram.cod_unid_tram_dest
            ).first()
            
            tramitacao_dic['unidade_destino'] = self._get_nome_unidade(unid_destino) if unid_destino else ''
        else:
            tramitacao_dic['unidade_destino'] = ''
        
        # Usuário de destino
        tramitacao_dic['nom_usuario_destino'] = ''
        if tram.cod_usuario_dest:
            usu_destino = self.session.query(Usuario).filter(
                Usuario.cod_usuario == tram.cod_usuario_dest
            ).first()
            
            if usu_destino:
                tramitacao_dic['usuario_destino'] = usu_destino.col_username or ''
                tramitacao_dic['nom_usuario_destino'] = usu_destino.nom_completo or ''
                tramitacao_dic['nom_cargo_usuario_destino'] = usu_destino.nom_cargo or ''
        
        return {
            'imagem': imagem,
            'rodape': rodape,
            'inf_basicas_dic': inf_basicas_dic,
            'tramitacao_dic': tramitacao_dic
        }
    
    def preparar_dados_tramitacao_com_dados_request(
        self,
        tipo: str,
        cod_tramitacao: int,
        dados_tramitacao_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepara dados da tramitação usando dados do request (não busca do banco).
        Usa dados_tramitacao_request para os campos da tramitação e busca apenas
        informações complementares (status, unidades, etc.) do banco.
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            dados_tramitacao_request: Dicionário com dados da tramitação do request
            
        Returns:
            Dicionário com dados preparados
        """
        from DateTime import DateTime
        from datetime import datetime
        
        # Obtém propriedades da casa (do contexto Zope)
        casa = {}
        if self.contexto_zope:
            try:
                site_real = self._resolver_site_real(self.contexto_zope)
                aux = site_real.sapl_documentos.props_sagl.propertyItems()
                for item in aux:
                    casa[item[0]] = item[1]
            except Exception as e:
                logger.warning(f"Erro ao obter propriedades da casa: {e}")
        
        # Obtém localidade
        localidade = None
        if casa.get('cod_localidade'):
            localidade = self.session.query(Localidade).filter(
                Localidade.cod_localidade == casa['cod_localidade']
            ).first()
        
        # Prepara rodapé
        rodape = casa.copy()
        data_emissao = DateTime(datefmt='international').strftime("%d/%m/%Y")
        rodape['data_emissao'] = data_emissao
        
        if localidade:
            rodape['nom_localidade'] = f"   {localidade.nom_localidade}"
            rodape['sgl_uf'] = localidade.sgl_uf
        
        # Obtém estado
        nom_estado = ''
        if localidade:
            estado = self.session.query(Localidade).filter(
                Localidade.tip_localidade == 'u',
                Localidade.sgl_uf == localidade.sgl_uf
            ).first()
            if estado:
                nom_estado = estado.nom_localidade
        
        # Informações básicas
        inf_basicas_dic = {
            'nom_camara': casa.get('nom_casa', ''),
            'nom_estado': f"Estado de {nom_estado}" if nom_estado else ''
        }
        
        # Obtém logo/imagem
        imagem = None
        if self.contexto_zope:
            try:
                site_real = self._resolver_site_real(self.contexto_zope)
                if hasattr(site_real.sapl_documentos.props_sagl, 'cabecalho.png'):
                    imagem = site_real.sapl_documentos.props_sagl['cabecalho.png'].absolute_url()
                    inf_basicas_dic["custom_image"] = True
                elif hasattr(site_real.sapl_documentos.props_sagl, 'logo_casa.gif'):
                    imagem = site_real.sapl_documentos.props_sagl['logo_casa.gif'].absolute_url()
                    inf_basicas_dic["custom_image"] = False
                else:
                    site_real = self._resolver_site_real(self.contexto_zope)
                    imagem = site_real.imagens.absolute_url() + "/brasao.gif"
                    inf_basicas_dic["custom_image"] = False
            except Exception as e:
                logger.warning(f"Erro ao obter logo: {e}")
                imagem = None
        
        if not imagem:
            imagem = '/brasao.gif'
            inf_basicas_dic["custom_image"] = False
        
        # Prepara dicionário de tramitação usando dados do request
        tramitacao_dic = {}
        tramitacao_dic['cod_tramitacao'] = cod_tramitacao
        
        # ✅ Data de tramitação: usa do request se disponível, senão data atual
        dat_tramitacao_request = dados_tramitacao_request.get('dat_tramitacao')
        if dat_tramitacao_request:
            if isinstance(dat_tramitacao_request, datetime):
                dat_tramitacao = dat_tramitacao_request.strftime('%d/%m/%Y')
            elif hasattr(dat_tramitacao_request, 'strftime'):
                dat_tramitacao = dat_tramitacao_request.strftime('%d/%m/%Y')
            else:
                # Se for string, tenta parsear
                dat_tramitacao = datetime.now().strftime('%d/%m/%Y')  # Fallback
        else:
            dat_tramitacao = datetime.now().strftime('%d/%m/%Y')
        
        tramitacao_dic['dat_tramitacao'] = dat_tramitacao
        tramitacao_dic['dat_extenso'] = self._data_por_extenso(dat_tramitacao)
        tramitacao_dic['dat_encaminha'] = False  # Rascunho não tem dat_encaminha
        
        # ✅ Usa dados do request diretamente
        tramitacao_dic['txt_tramitacao'] = dados_tramitacao_request.get('txt_tramitacao', '')
        
        # Status (busca descrição do banco, mas usa cod_status do request)
        cod_status_request = dados_tramitacao_request.get('cod_status')
        if cod_status_request:
            if tipo == 'MATERIA':
                status = self.session.query(StatusTramitacao).filter(
                    StatusTramitacao.cod_status == int(cod_status_request)
                ).first()
            else:
                status = self.session.query(StatusTramitacaoAdministrativo).filter(
                    StatusTramitacaoAdministrativo.cod_status == int(cod_status_request)
                ).first()
            tramitacao_dic['des_status'] = status.des_status if status else ''
        else:
            tramitacao_dic['des_status'] = ''
        
        # Data de fim de prazo (do request)
        dat_fim_prazo_request = dados_tramitacao_request.get('dat_fim_prazo')
        if dat_fim_prazo_request:
            tramitacao_dic['dat_fim_prazo'] = str(dat_fim_prazo_request)
        else:
            tramitacao_dic['dat_fim_prazo'] = ''
        
        # Urgência (apenas matérias, do request)
        if tipo == 'MATERIA':
            tramitacao_dic['ind_urgencia'] = dados_tramitacao_request.get('ind_urgencia', 0)
        
        # Dados da entidade (matéria ou documento) - precisa buscar do banco
        cod_entidade = None
        if tipo == 'MATERIA':
            # Busca matéria usando cod_tramitacao para obter cod_materia
            tram_db = self.session.query(Tramitacao).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao
            ).first()
            if tram_db:
                cod_entidade = tram_db.cod_materia
        else:
            # Busca documento usando cod_tramitacao para obter cod_documento
            tram_db = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao
            ).first()
            if tram_db:
                cod_entidade = tram_db.cod_documento
        
        if cod_entidade:
            if tipo == 'MATERIA':
                materia = self.session.query(MateriaLegislativa).options(
                    selectinload(MateriaLegislativa.tipo_materia_legislativa)
                ).filter(
                    MateriaLegislativa.cod_materia == cod_entidade
                ).first()
                
                if materia:
                    # Autoria
                    autorias = self.session.query(Autoria).options(
                        selectinload(Autoria.autor).selectinload(Autor.parlamentar),
                        selectinload(Autoria.autor).selectinload(Autor.comissao)
                    ).filter(
                        Autoria.cod_materia == materia.cod_materia
                    ).all()
                    
                    lista_autor = []
                    for autoria in autorias:
                        if not autoria.autor:
                            continue
                        if autoria.autor.parlamentar:
                            lista_autor.append(autoria.autor.parlamentar.nom_parlamentar)
                        elif autoria.autor.comissao:
                            lista_autor.append(autoria.autor.comissao.nom_comissao)
                        elif autoria.autor.nom_autor:
                            lista_autor.append(autoria.autor.nom_autor)
                    
                    autoria_str = ', '.join(lista_autor) if lista_autor else ''
                    txt_ementa = escape(materia.txt_ementa or '')
                    
                    des_tipo_materia = ''
                    if materia.tipo_materia_legislativa:
                        des_tipo_materia = materia.tipo_materia_legislativa.des_tipo_materia or materia.tipo_materia_legislativa.sgl_tipo_materia or ''
                    
                    tramitacao_dic['id_materia'] = (
                        f"{des_tipo_materia.upper()} N° "
                        f"{materia.num_ident_basica}/{materia.ano_ident_basica} - "
                        f"{autoria_str} - {txt_ementa}"
                    )
                    tramitacao_dic['identificacao_processo'] = f"{des_tipo_materia.upper()} N° {materia.num_ident_basica}/{materia.ano_ident_basica}"
                    tramitacao_dic['autoria_processo'] = autoria_str
                    tramitacao_dic['ementa_processo'] = txt_ementa
                else:
                    tramitacao_dic['id_materia'] = ''
                    tramitacao_dic['identificacao_processo'] = ''
                    tramitacao_dic['autoria_processo'] = ''
                    tramitacao_dic['ementa_processo'] = ''
            else:  # DOCUMENTO
                documento = self.session.query(DocumentoAdministrativo).options(
                    selectinload(DocumentoAdministrativo.tipo_documento_administrativo)
                ).filter(
                    DocumentoAdministrativo.cod_documento == cod_entidade
                ).first()
                
                if documento:
                    des_tipo_doc = ''
                    if documento.tipo_documento_administrativo:
                        des_tipo_doc = documento.tipo_documento_administrativo.des_tipo_documento or documento.tipo_documento_administrativo.sgl_tipo_documento or ''
                    
                    interessado = documento.txt_interessado or ''
                    txt_assunto = escape(documento.txt_assunto or '')
                    
                    tramitacao_dic['id_documento'] = (
                        f"{des_tipo_doc.upper()} N° "
                        f"{documento.num_documento}/{documento.ano_documento} - "
                        f"{interessado} - {txt_assunto}"
                    )
                    tramitacao_dic['identificacao_processo'] = f"{des_tipo_doc.upper()} N° {documento.num_documento}/{documento.ano_documento}"
                    tramitacao_dic['interessado_processo'] = interessado
                    tramitacao_dic['assunto_processo'] = txt_assunto
                else:
                    tramitacao_dic['id_documento'] = ''
                    tramitacao_dic['identificacao_processo'] = ''
                    tramitacao_dic['interessado_processo'] = ''
                    tramitacao_dic['assunto_processo'] = ''
        
        # Unidade de origem (busca nome do banco, mas usa cod do request)
        cod_unid_local_request = dados_tramitacao_request.get('cod_unid_tram_local')
        if cod_unid_local_request:
            unid_origem = self.session.query(UnidadeTramitacao).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UnidadeTramitacao.cod_unid_tramitacao == int(cod_unid_local_request)
            ).first()
            
            tramitacao_dic['unidade_origem'] = self._get_nome_unidade(unid_origem) if unid_origem else ''
        else:
            tramitacao_dic['unidade_origem'] = ''
        
        # Usuário de origem (busca do banco)
        cod_usuario_local_request = dados_tramitacao_request.get('cod_usuario_local')
        if cod_usuario_local_request:
            usu_origem = self.session.query(Usuario).filter(
                Usuario.cod_usuario == int(cod_usuario_local_request)
            ).first()
            
            if usu_origem:
                tramitacao_dic['usuario_origem'] = usu_origem.col_username or ''
                tramitacao_dic['nom_usuario_origem'] = usu_origem.nom_completo or ''
                tramitacao_dic['nom_cargo_usuario_origem'] = usu_origem.nom_cargo or ''
            else:
                tramitacao_dic['usuario_origem'] = ''
                tramitacao_dic['nom_usuario_origem'] = ''
                tramitacao_dic['nom_cargo_usuario_origem'] = ''
        else:
            tramitacao_dic['usuario_origem'] = ''
            tramitacao_dic['nom_usuario_origem'] = ''
            tramitacao_dic['nom_cargo_usuario_origem'] = ''
        
        # Unidade de destino (busca nome do banco, mas usa cod do request)
        cod_unid_dest_request = dados_tramitacao_request.get('cod_unid_tram_dest')
        if cod_unid_dest_request:
            unid_destino = self.session.query(UnidadeTramitacao).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UnidadeTramitacao.cod_unid_tramitacao == int(cod_unid_dest_request)
            ).first()
            
            tramitacao_dic['unidade_destino'] = self._get_nome_unidade(unid_destino) if unid_destino else ''
        else:
            tramitacao_dic['unidade_destino'] = ''
        
        # Usuário de destino (busca do banco)
        cod_usuario_dest_request = dados_tramitacao_request.get('cod_usuario_dest')
        tramitacao_dic['nom_usuario_destino'] = ''
        if cod_usuario_dest_request:
            usu_destino = self.session.query(Usuario).filter(
                Usuario.cod_usuario == int(cod_usuario_dest_request)
            ).first()
            
            if usu_destino:
                tramitacao_dic['usuario_destino'] = usu_destino.col_username or ''
                tramitacao_dic['nom_usuario_destino'] = usu_destino.nom_completo or ''
                tramitacao_dic['nom_cargo_usuario_destino'] = usu_destino.nom_cargo or ''
        
        return {
            'imagem': imagem,
            'rodape': rodape,
            'inf_basicas_dic': inf_basicas_dic,
            'tramitacao_dic': tramitacao_dic
        }
    
    def gerar_pdf(
        self,
        tipo: str,
        cod_tramitacao: int,
        contexto_zope=None
    ) -> BytesIO:
        """
        Gera PDF do despacho de tramitação usando ReportLab
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            contexto_zope: Contexto Zope para salvar arquivo (opcional)
            
        Returns:
            BytesIO com conteúdo do PDF
        """
        # Prepara dados
        dados = self.preparar_dados_tramitacao(tipo, cod_tramitacao)
        
        # Gera PDF com ReportLab
        pdf_buffer = BytesIO()
        self._gerar_pdf_reportlab(tipo, dados, pdf_buffer)
        pdf_bytes = pdf_buffer.getvalue()
        
        # Salva no repositório Zope se contexto fornecido
        if contexto_zope:
            # Resolve o site real removendo wrappers (RequestContainer, etc)
            site_real = self._resolver_site_real(contexto_zope)
            
            arquivo_pdf = f"{cod_tramitacao}_tram.pdf"
            
            if tipo == 'MATERIA':
                repo = site_real.sapl_documentos.materia.tramitacao
            else:
                repo = site_real.sapl_documentos.administrativo.tramitacao
            
            if hasattr(repo, arquivo_pdf):
                arq = getattr(repo, arquivo_pdf)
                arq.manage_upload(file=pdf_bytes)
            else:
                repo.manage_addFile(
                    id=arquivo_pdf,
                    file=pdf_bytes,
                    content_type='application/pdf',
                    title=f'Tramitação de {"processo legislativo" if tipo == "MATERIA" else "processo administrativo"}'
                )
            
            # Configura permissões se documento for público
            if tipo == 'DOCUMENTO':
                tram = self.session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao
                ).first()
                if tram:
                    from openlegis.sagl.models.models import DocumentoAdministrativo
                    doc = self.session.query(DocumentoAdministrativo).filter(
                        DocumentoAdministrativo.cod_documento == tram.cod_documento
                    ).first()
                    # Verifica se é público (ajustar conforme modelo)
                    # if doc and doc.ind_publico:
                    #     pdf_obj = getattr(repo, arquivo_pdf)
                    #     pdf_obj.manage_permission('View', roles=['Manager','Authenticated','Anonymous'], acquire=1)
        
        return BytesIO(pdf_bytes)
    
    def gerar_pdf_com_dados(
        self,
        tipo: str,
        dados: Dict[str, Any],
        contexto_zope=None
    ) -> BytesIO:
        """
        Gera PDF usando dados já preparados (para uso em tasks Celery)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            dados: Dicionário com dados preparados (imagem, rodape, inf_basicas_dic, tramitacao_dic)
            contexto_zope: Contexto Zope para salvar arquivo (opcional)
            
        Returns:
            BytesIO com conteúdo do PDF
        """
        # Gera PDF com ReportLab usando dados recebidos
        pdf_buffer = BytesIO()
        self._gerar_pdf_reportlab(tipo, dados, pdf_buffer)
        pdf_bytes = pdf_buffer.getvalue()
        
        return BytesIO(pdf_bytes)
    
    def salvar_pdf_no_repositorio(
        self,
        tipo: str,
        cod_tramitacao: int,
        pdf_bytes: bytes,
        contexto_zope
    ) -> None:
        """
        Salva PDF no repositório Zope
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            pdf_bytes: Bytes do PDF
            contexto_zope: Contexto Zope para acessar repositório
        """
        if not contexto_zope:
            raise ValueError("Contexto Zope necessário para salvar arquivo")
        
        # Resolve o site real removendo wrappers (RequestContainer, etc)
        site_real = self._resolver_site_real(contexto_zope)
        
        arquivo_pdf = f"{cod_tramitacao}_tram.pdf"
        
        if tipo == 'MATERIA':
            repo = site_real.sapl_documentos.materia.tramitacao
        else:
            repo = site_real.sapl_documentos.administrativo.tramitacao
        
        if hasattr(repo, arquivo_pdf):
            arq = getattr(repo, arquivo_pdf)
            arq.manage_upload(file=pdf_bytes)
        else:
            repo.manage_addFile(
                id=arquivo_pdf,
                file=pdf_bytes,
                content_type='application/pdf',
                title=f'Tramitação de {"processo legislativo" if tipo == "MATERIA" else "processo administrativo"}'
            )
    
    def _gerar_pdf_reportlab(
        self,
        tipo: str,
        dados: Dict[str, Any],
        buffer: BytesIO
    ) -> None:
        """
        Gera PDF usando ReportLab, mantendo aparência do PDF original (RML)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            dados: Dicionário com imagem, rodape, inf_basicas_dic, tramitacao_dic
            buffer: BytesIO onde o PDF será escrito
        """
        imagem = dados['imagem']
        dic_rodape = dados['rodape']
        inf_basicas_dic = dados['inf_basicas_dic']
        tramitacao_dic = dados['tramitacao_dic']
        
        # Cria documento PDF (A4)
        # Margens do RML: frame x1="3cm" y1="3.5cm" width="16.7cm" height="23cm"
        # Isso significa: left=3cm, bottom=3.5cm, right=21-3-16.7=1.3cm, top=29.7-3.5-23=3.2cm
        # O cabeçalho será desenhado ACIMA da margem superior (no espaço entre topo da página e margem)
        # Então mantemos a margem original e desenhamos o cabeçalho no espaço acima dela
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.3*cm,
            leftMargin=3*cm,
            topMargin=3.2*cm,  # Margem original - cabeçalho fica acima desta margem
            bottomMargin=3.5*cm
        )
        
        # Estilos (baseados no RML original)
        styles = getSampleStyleSheet()
        
        # Estilo P1 (título cinza) - não usado diretamente, mas definido para referência
        p1_style = ParagraphStyle(
            'P1',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=colors.HexColor('#808080'),  # gray
            leading=14,
            spaceAfter=2,
            spaceBefore=8,
            alignment=TA_LEFT
        )
        
        # Estilo P2 (texto normal justificado)
        p2_style = ParagraphStyle(
            'P2',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            spaceAfter=1,
            alignment=TA_JUSTIFY
        )
        
        # Estilo P3 (texto centralizado)
        p3_style = ParagraphStyle(
            'P3',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=12,
            spaceAfter=2,
            alignment=TA_CENTER
        )
        
        # Estilos modernos para layout atualizado - Paleta elegante e moderna
        primary_color = colors.HexColor('#1a237e')  # Azul escuro institucional
        primary_light = colors.HexColor('#283593')  # Azul médio para variações
        accent_color = colors.HexColor('#3949ab')  # Azul acento
        text_dark = colors.HexColor('#212121')  # Preto suave
        text_medium = colors.HexColor('#424242')  # Cinza escuro
        text_light = colors.HexColor('#757575')  # Cinza médio
        text_lighter = colors.HexColor('#9e9e9e')  # Cinza claro
        bg_section_light = colors.HexColor('#f5f7fa')  # Fundo muito claro e moderno
        border_light = colors.HexColor('#e1e8ed')  # Borda suave
        success_color = colors.HexColor('#4caf50')  # Verde para status positivo
        warning_color = colors.HexColor('#ff9800')  # Laranja para alertas
        
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=primary_color,
            leading=16,  # Aumentado para elegância
            spaceAfter=8,  # Aumentado para respiração
            spaceBefore=14,  # Aumentado para separação visual
            alignment=TA_LEFT
        )
        
        content_style = ParagraphStyle(
            'Content',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,  # Otimizado
            leading=14,  # Aumentado para melhor legibilidade entre linhas
            spaceAfter=1,  # Reduzido para menor distância entre parágrafos
            alignment=TA_JUSTIFY,
            textColor=text_dark
        )
        
        value_style = ParagraphStyle(
            'Value',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,  # Aumentado para melhor legibilidade entre linhas
            textColor=text_medium,  # Usa cinza médio para valores (mais suave)
            spaceAfter=1  # Reduzido ainda mais para menor distância entre parágrafos
        )
        
        # Estilo para labels (mais destacado)
        label_style = ParagraphStyle(
            'Label',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=15,
            textColor=text_dark,  # Preto suave para labels
            spaceAfter=0
        )
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            spaceAfter=8,
            alignment=TA_CENTER,
            textColor=text_light
        )
        
        signature_style = ParagraphStyle(
            'Signature',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=16,
            spaceAfter=4,
            alignment=TA_CENTER,
            textColor=text_dark
        )
        
        # Prepara dados do cabeçalho (carrega imagem antes de criar função)
        img_reader = None
        img_width = 0
        img_height = 0
        
        if imagem:
            try:
                # Carrega imagem
                if imagem.startswith('http'):
                    response = requests.get(imagem, timeout=5)
                    img_data = BytesIO(response.content)
                else:
                    if self.contexto_zope:
                        try:
                            site_real = self._resolver_site_real(self.contexto_zope)
                            img_obj = getattr(site_real.sapl_documentos.props_sagl, imagem.split('/')[-1], None)
                            if img_obj:
                                img_data = BytesIO(bytes(img_obj.data))
                            else:
                                img_data = None
                        except Exception:
                            img_data = None
                    else:
                        img_data = None
                
                if img_data:
                    # Obtém dimensões reais da imagem (sem processamento de transparência)
                    # Carrega imagem como PNG sem modificar
                    original_width = 0
                    original_height = 0
                    
                    if PIL_AVAILABLE:
                        try:
                            # Cria uma cópia dos dados para PIL, preservando o original para ImageReader
                            img_data.seek(0)
                            img_data_copy = BytesIO(img_data.read())
                            img_data.seek(0)  # Reseta o original
                            
                            # Abre imagem com PIL apenas para obter dimensões usando a cópia
                            pil_img = PILImage.open(img_data_copy)
                            original_width, original_height = pil_img.size
                            pil_img.close()
                            img_data_copy.close()  # Fecha a cópia
                            
                            logger.debug(f"Imagem carregada: {original_width}x{original_height} (sem processamento de transparência)")
                        except Exception as e:
                            logger.warning(f"Erro ao obter dimensões da imagem: {e}, usando tamanhos padrão")
                            img_data.seek(0)  # Reseta para início
                    
                    # Calcula dimensões finais preservando proporção original
                    if original_width > 0 and original_height > 0:
                        # Verifica se é imagem quadrada (brasão)
                        is_square = abs(original_width - original_height) <= 2  # Tolerância de 2px para considerar quadrado
                        
                        if inf_basicas_dic.get('custom_image'):
                            # Imagem customizada: máximo 350x67 (proporção ~5.22:1)
                            max_width = 350
                            max_height = 67
                        else:
                            # Logo padrão (brasão): sempre quadrado, máximo 65x65 (otimizado para caber em uma página)
                            if is_square:
                                # Brasão quadrado: usa o menor lado como referência para manter quadrado
                                max_size = min(65, original_width, original_height)  # Máximo 65px, mas não aumenta
                                max_width = max_size
                                max_height = max_size
                            else:
                                # Se não for quadrado, usa tamanhos padrão
                                max_width = 65
                                max_height = 65
                        
                        # Calcula proporção mantendo tamanho original ou redimensionando proporcionalmente
                        if is_square and not inf_basicas_dic.get('custom_image'):
                            # Para brasão quadrado, mantém proporção 1:1
                            # Usa o menor lado como referência
                            side = min(original_width, original_height)
                            ratio = min(max_size / side, 1.0)  # Não aumenta, apenas reduz se necessário
                            img_width = side * ratio
                            img_height = side * ratio
                        else:
                            # Para outras imagens, calcula ratio normalmente
                            width_ratio = max_width / original_width
                            height_ratio = max_height / original_height
                            # Usa o menor ratio para manter proporção e não exceder limites
                            ratio = min(width_ratio, height_ratio, 1.0)  # Não aumenta, apenas reduz se necessário
                            # Calcula dimensões finais preservando proporção
                            img_width = original_width * ratio
                            img_height = original_height * ratio
                        
                        logger.debug(f"Imagem redimensionada preservando proporção: {original_width}x{original_height} -> {img_width:.1f}x{img_height:.1f} (quadrado: {is_square})")
                    else:
                        # Fallback para tamanhos padrão se dimensões não foram obtidas
                        if inf_basicas_dic.get('custom_image'):
                            img_width = 350
                            img_height = 67
                        else:
                            # Brasão padrão: assume quadrado 65x65 (otimizado para caber em uma página)
                            img_width = 65
                            img_height = 65
                    
                    # Processa transparência PNG e cria ImageReader
                    try:
                        img_data.seek(0)  # Garante que está no início
                        
                        # Processa transparência PNG se PIL estiver disponível
                        if PIL_AVAILABLE:
                            try:
                                # Carrega imagem com PIL para processar transparência
                                pil_img = PILImage.open(img_data)
                                
                                # Verifica se a imagem tem canal alpha (transparência)
                                if pil_img.mode in ('RGBA', 'LA', 'P'):
                                    # Cria fundo branco
                                    background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                                    
                                    if pil_img.mode == 'P':
                                        # Imagens com paleta: verifica se tem transparência
                                        if 'transparency' in pil_img.info:
                                            # Converte para RGBA para preservar transparência
                                            pil_img = pil_img.convert('RGBA')
                                            # Composição alpha sobre fundo branco
                                            background.paste(pil_img, mask=pil_img.split()[3])  # Usa canal alpha
                                            pil_img = background
                                        else:
                                            # Sem transparência, apenas converte para RGB
                                            pil_img = pil_img.convert('RGB')
                                    elif pil_img.mode == 'LA':
                                        # LA tem luminância e alpha: converte L para RGB e compõe com alpha
                                        # Primeiro converte L para RGB (grayscale para RGB)
                                        rgb_channels = pil_img.split()[0].convert('RGB')
                                        # Cria máscara do canal alpha
                                        alpha_mask = pil_img.split()[1]
                                        # Composição sobre fundo branco
                                        background.paste(rgb_channels, mask=alpha_mask)
                                        pil_img = background
                                    elif pil_img.mode == 'RGBA':
                                        # RGBA: composição normal com canal alpha
                                        background.paste(pil_img, mask=pil_img.split()[3])  # Usa canal alpha (índice 3)
                                        pil_img = background
                                else:
                                    # Não tem transparência, apenas garante que está em RGB
                                    pil_img = pil_img.convert('RGB')
                                
                                # Salva imagem processada em um novo BytesIO
                                img_data_processed = BytesIO()
                                pil_img.save(img_data_processed, format='PNG')
                                img_data_processed.seek(0)
                                
                                # Usa a imagem processada para criar ImageReader
                                img_reader = ImageReader(img_data_processed)
                                logger.debug(f"ImageReader criado com sucesso (transparência processada). Dimensões: {img_width}x{img_height}")
                            except Exception as pil_error:
                                logger.warning(f"Erro ao processar transparência com PIL: {pil_error}, usando imagem original")
                                # Fallback: usa imagem original sem processamento
                                img_data.seek(0)
                                img_reader = ImageReader(img_data)
                        else:
                            # PIL não disponível, usa imagem original
                            img_reader = ImageReader(img_data)
                            logger.debug(f"ImageReader criado com sucesso (sem processamento PIL). Dimensões: {img_width}x{img_height}")
                    except Exception as e:
                        logger.error(f"Erro ao criar ImageReader: {e}", exc_info=True)
                        img_reader = None
                else:
                    logger.warning(f"img_data é None para imagem: {imagem}")
            except Exception as e:
                logger.warning(f"Erro ao carregar imagem: {e}")
        
        # Função para desenhar cabeçalho (chamada em cada página)
        # Usa closure para acessar variáveis do escopo externo
        def draw_header(canvas, doc):
            """Desenha cabeçalho fixo no topo de cada página (acima da área de conteúdo)"""
            # Define título do PDF como nome do arquivo
            cod_tramitacao = tramitacao_dic.get('cod_tramitacao', '')
            if cod_tramitacao:
                pdf_title = f"{cod_tramitacao}_tram.pdf"
                canvas.setTitle(pdf_title)
            
            # Em ReportLab: y=0 é na parte inferior, y cresce para cima
            # A4 height = 29.7cm = 842 pontos (1cm = 28.35 pontos)
            page_height = A4[1]  # Altura da página em pontos
            top_margin = 3.2 * cm  # Margem superior da área de conteúdo
            
            # Cabeçalho deve estar no TOPO da página, ACIMA da margem superior
            # Espaço disponível para cabeçalho: do topo da página até a margem superior (3.2cm)
            # Posiciona cabeçalho começando do topo da página, com espaçamento maior
            header_top_margin = 0.8 * cm  # Espaçamento do topo absoluto da página (aumentado para descer o cabeçalho)
            
            try:
                # Sempre tenta desenhar o brasão se img_reader existe
                if img_reader is not None:
                    if img_width > 0 and img_height > 0:
                        # Posição da imagem: alinhada à esquerda (3.1cm), no topo do cabeçalho
                        # Começa do topo da página menos pequeno espaçamento
                        img_y = page_height - img_height - header_top_margin  # Topo da página menos altura da imagem menos espaçamento
                        
                        # Desenha imagem no topo (x=3.1cm da esquerda)
                        # Carrega como PNG sem processamento de transparência
                        try:
                            canvas.drawImage(
                                img_reader, 
                                3.1*cm, 
                                img_y, 
                                width=img_width, 
                                height=img_height
                            )
                            logger.debug(f"Brasão desenhado com sucesso: {img_width}x{img_height} em y={img_y}")
                        except Exception as img_err:
                            logger.error(f"Erro ao desenhar imagem do brasão: {img_err}", exc_info=True)
                        
                        # Se não for imagem customizada, desenha texto ao lado da imagem
                        if not inf_basicas_dic.get('custom_image'):
                            # Nome da câmara (alinhado verticalmente com o centro da imagem)
                            camara_y = img_y + (img_height / 2) + 8  # Centro + ajuste otimizado
                            canvas.setFont('Helvetica-Bold', 14)  # Otimizado para caber em uma página
                            nom_camara = inf_basicas_dic.get('nom_camara', '')
                            if nom_camara:
                                canvas.drawString(6.7*cm, camara_y, nom_camara)
                            
                            # Estado (abaixo do nome da câmara)
                            estado_y = camara_y - 18  # Espaçamento otimizado
                            canvas.setFont('Helvetica', 11)  # Otimizado
                            nom_estado = inf_basicas_dic.get('nom_estado', '')
                            if nom_estado:
                                canvas.drawString(6.7*cm, estado_y, nom_estado)
                    else:
                        logger.warning(f"img_reader existe mas dimensões inválidas: width={img_width}, height={img_height}")
                else:
                    logger.warning(f"img_reader é None. imagem={imagem}, img_data existe={img_data is not None if 'img_data' in locals() else 'N/A'}")
                    # Se não houver imagem, desenha apenas o texto do cabeçalho
                    text_y = page_height - header_top_margin - 20  # Topo menos espaçamento
                    canvas.setFont('Helvetica-Bold', 14)  # Otimizado
                    nom_camara = inf_basicas_dic.get('nom_camara', '')
                    if nom_camara:
                        canvas.drawString(3.1*cm, text_y, nom_camara)
                    
                    # Estado abaixo do nome
                    estado_y = text_y - 18  # Espaçamento otimizado
                    canvas.setFont('Helvetica', 11)  # Otimizado
                    nom_estado = inf_basicas_dic.get('nom_estado', '')
                    if nom_estado:
                        canvas.drawString(3.1*cm, estado_y, nom_estado)
                
                # Adiciona linha divisória sutil abaixo do cabeçalho (sempre desenhada)
                try:
                    # Linha divisória na posição da margem superior do conteúdo
                    divider_y = page_height - top_margin
                    canvas.setStrokeColor(colors.HexColor('#e0e0e0'))  # Cinza muito claro
                    canvas.setLineWidth(0.5)
                    canvas.line(3*cm, divider_y, 19.7*cm, divider_y)  # Linha do início ao fim do conteúdo
                except Exception:
                    pass  # Ignora erro se não conseguir desenhar linha
            except Exception as e:
                logger.error(f"Erro ao desenhar cabeçalho: {e}", exc_info=True)
                # Tenta desenhar pelo menos o texto mesmo com erro
                try:
                    text_y = page_height - header_top_margin - 20
                    canvas.setFont('Helvetica-Bold', 15)
                    nom_camara = inf_basicas_dic.get('nom_camara', '')
                    if nom_camara:
                        canvas.drawString(3.1*cm, text_y, nom_camara)
                except:
                    pass
        
        # Cores modernas adicionais para layout (mantidas para compatibilidade)
        secondary_color = accent_color
        bg_section = bg_section_light  # Atualizado para cor mais moderna
        bg_card = colors.HexColor('#ffffff')
        border_color = border_light  # Atualizado para borda mais suave
        
        # Conteúdo do PDF - Layout Moderno
        story = []
        
        # Espaçamento inicial (reduzido para caber em uma página)
        story.append(Spacer(1, 0.3*cm))
        
        # Título principal moderno
        if tipo == 'MATERIA':
            processo_title = "PROCESSO LEGISLATIVO"
            id_entidade = tramitacao_dic.get('id_materia', '')
        else:
            processo_title = "PROCESSO ADMINISTRATIVO"
            id_entidade = tramitacao_dic.get('id_documento', '')
        
        # Card de título principal - Design elegante com sombra sutil
        title_card_data = [[processo_title]]
        title_card = Table(title_card_data, colWidths=[460])
        title_card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), primary_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),  # Reduzido de 14
            ('LEADING', (0, 0), (-1, -1), 14),  # Reduzido de 17
            ('LETTERSPACING', (0, 0), (-1, -1), 0.5),  # Espaçamento entre letras para modernidade
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),  # Reduzido de 8
            ('TOPPADDING', (0, 0), (-1, -1), 5),  # Reduzido de 8
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            # Efeito de sombra sutil usando múltiplas bordas
            ('BOX', (0, 0), (-1, -1), 0, colors.white),  # Borda invisível para espaço
        ]))
        story.append(title_card)
        story.append(Spacer(1, 0.3*cm))  # Reduzido
        
        # ID da entidade em card destacado - Campos separados para melhor legibilidade
        identificacao = tramitacao_dic.get('identificacao_processo', '')
        autoria = tramitacao_dic.get('autoria_processo', '')
        ementa = tramitacao_dic.get('ementa_processo', '')
        
        if identificacao or autoria or ementa:
            # Estilos para labels e valores
            label_style_processo = ParagraphStyle(
                'LabelProcesso',
                parent=styles['Normal'],
                fontName='Helvetica-Bold',
                fontSize=10,
                leading=14,
                spaceAfter=2,
                alignment=TA_LEFT,
                textColor=primary_color
            )
            
            value_style_processo = ParagraphStyle(
                'ValueProcesso',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=10,
                leading=14,  # Aumentado para melhor legibilidade entre linhas
                spaceAfter=1,  # Reduzido ainda mais para menor distância entre parágrafos
                alignment=TA_LEFT,
                textColor=text_medium
            )
            
            # Monta conteúdo com campos separados
            processo_content = []
            
            # Identificação do processo
            if identificacao:
                processo_content.append(Paragraph(f'<b>Identificação:</b> <font color="#424242">{escape(identificacao)}</font>', value_style_processo))
            
            # Autoria (para matérias) ou Interessado (para documentos)
            if autoria:
                label_autoria = 'Autoria:' if tipo == 'MATERIA' else 'Interessado:'
                processo_content.append(Paragraph(f'<b>{label_autoria}</b> <font color="#424242">{escape(autoria)}</font>', value_style_processo))
            
            # Ementa (para matérias) ou Assunto (para documentos)
            if ementa:
                label_ementa = 'Ementa:' if tipo == 'MATERIA' else 'Assunto:'
                # Remove spaceAfter do último item para não ter espaço extra
                ementa_style = ParagraphStyle(
                    'EmentaProcesso',
                    parent=value_style_processo,
                    spaceAfter=0
                )
                processo_content.append(Paragraph(f'<b>{label_ementa}</b> <font color="#424242">{escape(ementa)}</font>', ementa_style))
            
            # Cria card com campos organizados
            id_card_data = [[item] for item in processo_content]
            id_card = Table(id_card_data, colWidths=[460])
            id_card.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), bg_section_light),
                ('TEXTCOLOR', (0, 0), (-1, -1), text_dark),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 10),  # Reduzido
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),  # Reduzido
                ('LEFTPADDING', (0, 0), (-1, -1), 14),
                ('RIGHTPADDING', (0, 0), (-1, -1), 14),
                ('BOX', (0, 0), (-1, -1), 1, border_light),
                ('LINEBEFORE', (0, 0), (0, -1), 3, primary_color),
            ]))
            story.append(id_card)
            story.append(Spacer(1, 0.3*cm))
        
        # Seção de informações da tramitação - Layout moderno em cards
        story.append(Paragraph("<b>INFORMAÇÕES DA TRAMITAÇÃO</b>", section_title_style))
        story.append(Spacer(1, 0.2*cm))  # Reduzido
        
        # Tabela de informações modernizada - Layout em duas colunas com Paragraph para quebra de linha
        info_data = []
        
        # Primeira linha: Data e Status - Design elegante
        data_label = 'Data da Ação:' if tipo == 'MATERIA' else 'Data do Despacho:'
        data_value = str(tramitacao_dic.get('dat_tramitacao', ''))
        status_value = str(tramitacao_dic.get('des_status', ''))
        
        # Formatação elegante com separação visual entre label e valor
        data_text = f'<b>{data_label}</b> {escape(data_value)}' if data_value else ''
        status_text = f'<b>Status:</b> <font color="#424242">{escape(status_value)}</font>' if status_value else ''
        
        info_data.append([
            Paragraph(data_text, value_style) if data_text else '',
            Paragraph(status_text, value_style) if status_text else ''
        ])
        
        # Segunda linha: Unidades - Design elegante
        unid_origem = str(tramitacao_dic.get('unidade_origem', ''))
        unid_destino = str(tramitacao_dic.get('unidade_destino', ''))
        origem_text = f'<b>Origem:</b> <font color="#424242">{escape(unid_origem)}</font>' if unid_origem else ''
        destino_text = f'<b>Destino:</b> <font color="#424242">{escape(unid_destino)}</font>' if unid_destino else ''
        info_data.append([
            Paragraph(origem_text, value_style) if origem_text else '',
            Paragraph(destino_text, value_style) if destino_text else ''
        ])
        
        # Terceira linha: Prazo (coluna esquerda) e Usuário de destino (coluna direita)
        nom_usuario_destino = str(tramitacao_dic.get('nom_usuario_destino', ''))
        dat_fim_prazo = str(tramitacao_dic.get('dat_fim_prazo', ''))
        
        linha_3_col1 = ''
        linha_3_col2 = ''
        
        # Prazo na coluna esquerda - Design elegante
        if dat_fim_prazo and dat_fim_prazo != 'None' and dat_fim_prazo != '':
            linha_3_col1 = Paragraph(f'<b>Prazo:</b> <font color="#424242">{escape(dat_fim_prazo)}</font>', value_style)
        
        # Usuário de destino na coluna direita - Design elegante
        if nom_usuario_destino and nom_usuario_destino != 'None' and nom_usuario_destino != '':
            linha_3_col2 = Paragraph(f'<b>Usuário Destino:</b> <font color="#424242">{escape(nom_usuario_destino)}</font>', value_style)
        
        if linha_3_col1 or linha_3_col2:
            info_data.append([linha_3_col1, linha_3_col2])
        
        # Tabela moderna com duas colunas - Design elegante
        info_table = Table(info_data, colWidths=[230, 230])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_card),
            ('TEXTCOLOR', (0, 0), (-1, -1), text_dark),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),  # Reduzido para compactar
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),  # Reduzido
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 1, border_light),  # Borda suave
            # Linha divisória vertical sutil entre colunas
            ('LINEAFTER', (0, 0), (0, -1), 0.5, border_light),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.3*cm))  # Reduzido
        
        # Texto da tramitação - Seção moderna
        texto_tramitacao = str(tramitacao_dic.get('txt_tramitacao', ''))
        if texto_tramitacao and texto_tramitacao != '' and texto_tramitacao != 'None':
            # Título da seção
            if tipo == 'MATERIA':
                texto_title = "TEXTO DA AÇÃO"
            else:
                texto_title = "TEXTO DO DESPACHO"
            
            story.append(Paragraph(f"<b>{texto_title}</b>", section_title_style))
            story.append(Spacer(1, 0.2*cm))  # Reduzido
            
            # Card para o texto
            texto_card_data = [['']]  # Será preenchido com o texto processado
            
            # ReportLab Paragraph suporta HTML básico (tags: <b>, <i>, <u>, <br/>, <a>, <font>, etc.)
            # Mas NÃO suporta <ul>, <ol>, <li> nativamente - precisamos converter para texto formatado
            try:
                # Primeiro, processa listas HTML antes de outras conversões
                # ReportLab não suporta <ul>/<ol>/<li>, então convertemos para texto formatado
                texto_processado = texto_tramitacao
                
                # Processa listas ordenadas (<ol>) - converte para números
                def processar_lista_ordenada(match):
                    """Converte <ol>...</ol> para texto numerado"""
                    conteudo_lista = match.group(1)
                    # Extrai todos os <li> da lista
                    itens = re.findall(r'<li[^>]*>(.*?)</li>', conteudo_lista, re.DOTALL | re.IGNORECASE)
                    resultado = []
                    for idx, item in enumerate(itens, 1):
                        # Remove tags HTML internas do item (será processado depois)
                        item_limpo = item.strip()
                        # Adiciona número e item
                        resultado.append(f"{idx}. {item_limpo}")
                    return '<br/>'.join(resultado) + '<br/>'
                
                # Processa listas não ordenadas (<ul>) - converte para bullets
                def processar_lista_nao_ordenada(match):
                    """Converte <ul>...</ul> para texto com bullets"""
                    conteudo_lista = match.group(1)
                    # Extrai todos os <li> da lista
                    itens = re.findall(r'<li[^>]*>(.*?)</li>', conteudo_lista, re.DOTALL | re.IGNORECASE)
                    resultado = []
                    for item in itens:
                        # Remove tags HTML internas do item (será processado depois)
                        item_limpo = item.strip()
                        # Adiciona bullet e item (usa • unicode)
                        resultado.append(f"• {item_limpo}")
                    return '<br/>'.join(resultado) + '<br/>'
                
                # Processa listas aninhadas recursivamente (processa de dentro para fora)
                # Primeiro processa listas mais internas, depois as externas
                max_iteracoes = 10  # Evita loop infinito
                for _ in range(max_iteracoes):
                    # Processa listas ordenadas (sem outras listas dentro)
                    texto_anterior = texto_processado
                    texto_processado = re.sub(
                        r'<ol[^>]*>((?:[^<]|<(?!ol|ul|/ol|/ul))*?)</ol>',
                        processar_lista_ordenada,
                        texto_processado,
                        flags=re.DOTALL | re.IGNORECASE
                    )
                    # Processa listas não ordenadas (sem outras listas dentro)
                    texto_processado = re.sub(
                        r'<ul[^>]*>((?:[^<]|<(?!ol|ul|/ol|/ul))*?)</ul>',
                        processar_lista_nao_ordenada,
                        texto_processado,
                        flags=re.DOTALL | re.IGNORECASE
                    )
                    # Se não houve mudança, todas as listas foram processadas
                    if texto_processado == texto_anterior:
                        break
                
                # Remove tags <li> restantes (caso alguma tenha escapado)
                texto_processado = re.sub(r'<li[^>]*>', '', texto_processado, flags=re.IGNORECASE)
                texto_processado = re.sub(r'</li>', '', texto_processado, flags=re.IGNORECASE)
                
                # Converte <strong> e <em> para <b> e <i> (ReportLab não suporta <strong>/<em>)
                texto_processado = re.sub(r'<strong[^>]*>', '<b>', texto_processado, flags=re.IGNORECASE)
                texto_processado = re.sub(r'</strong>', '</b>', texto_processado, flags=re.IGNORECASE)
                texto_processado = re.sub(r'<em[^>]*>', '<i>', texto_processado, flags=re.IGNORECASE)
                texto_processado = re.sub(r'</em>', '</i>', texto_processado, flags=re.IGNORECASE)
                
                # Converte <span style="text-decoration: underline;"> para <u> (ANTES de remover <span>)
                # Processa sublinhado no estilo inline
                def processar_sublinhado_span(match):
                    """Converte <span style="text-decoration: underline;"> para <u>"""
                    conteudo = match.group(1)
                    return f'<u>{conteudo}</u>'
                
                # Processa <span style="...text-decoration: underline..."> com text-decoration: underline
                # Regex mais robusta para capturar spans com underline
                texto_processado = re.sub(
                    r'<span[^>]*style\s*=\s*["\'][^"\']*text-decoration\s*:\s*underline[^"\']*["\'][^>]*>(.*?)</span>',
                    processar_sublinhado_span,
                    texto_processado,
                    flags=re.DOTALL | re.IGNORECASE
                )
                
                # Processa links <a> para adicionar cor e sublinhado
                def processar_link(match):
                    """Adiciona cor azul e sublinhado aos links"""
                    atributos_completos = match.group(1)  # Todos os atributos antes de >
                    texto_link = match.group(2)
                    # Extrai href de qualquer posição nos atributos
                    url_match = re.search(r'href\s*=\s*["\']([^"\']*)["\']', atributos_completos, re.IGNORECASE)
                    url = url_match.group(1) if url_match else ''
                    # ReportLab suporta links com color e <u> para sublinhado
                    # Usa cor azul padrão (#0066cc) e sublinha o link
                    return f'<a href="{url}" color="#0066cc"><u>{texto_link}</u></a>'
                
                # Processa links <a ...>texto</a> para adicionar cor e sublinhado
                # Regex captura qualquer <a> com atributos, incluindo href em qualquer posição
                texto_processado = re.sub(
                    r'<a\s+([^>]*?)>(.*?)</a>',
                    processar_link,
                    texto_processado,
                    flags=re.DOTALL | re.IGNORECASE
                )
                
                # Converte <div> e <span> restantes em parágrafos/quebras (ReportLab não suporta)
                # <div> -> quebra de linha antes e depois
                texto_processado = re.sub(r'<div[^>]*>', '<br/>', texto_processado, flags=re.IGNORECASE)
                texto_processado = re.sub(r'</div>', '<br/>', texto_processado, flags=re.IGNORECASE)
                # <span> -> remove apenas a tag, mantém conteúdo (apenas spans que não foram processados antes)
                texto_processado = re.sub(r'<span[^>]*>', '', texto_processado, flags=re.IGNORECASE)
                texto_processado = re.sub(r'</span>', '', texto_processado, flags=re.IGNORECASE)
                
                # Normaliza <p> para <br/> (ReportLab não suporta <p> com estilo completo)
                # Remove <p> e </p>, mas preserva quebra de linha
                texto_processado = re.sub(r'<p[^>]*>', '', texto_processado, flags=re.IGNORECASE)
                texto_processado = re.sub(r'</p>', '<br/>', texto_processado, flags=re.IGNORECASE)
                
                # Normaliza quebras de linha (<br>, <br/>, <br />)
                texto_processado = re.sub(r'<br\s*/?>', '<br/>', texto_processado, flags=re.IGNORECASE)
                
                # Remove tags não suportadas (mantém apenas: b, i, u, br, a, font)
                # Remove outras tags HTML não suportadas, mas preserva o conteúdo
                texto_processado = re.sub(r'</?(?:h[1-6]|table|tr|td|th|thead|tbody|div|span|strong|em|ul|ol|li)[^>]*>', '', texto_processado, flags=re.IGNORECASE)
                
                # Limpa múltiplas quebras de linha consecutivas (máximo 2)
                texto_processado = re.sub(r'(<br/>\s*){3,}', '<br/><br/>', texto_processado)
                
                # Remove espaços em branco excessivos (mas preserva espaços dentro de tags)
                # Primeiro preserva conteúdo de tags, depois limpa espaços
                texto_processado = re.sub(r' +', ' ', texto_processado)
                
                # Remove quebras de linha no início/fim
                texto_processado = texto_processado.strip()
                
                # Texto pronto para ReportLab Paragraph (mantém HTML básico, links e listas convertidas)
                texto_para_pdf = texto_processado
                
            except Exception as e:
                logger.warning(f"Erro ao processar HTML: {e}")
                # Fallback: mantém HTML básico mas remove tags complexas
                texto_para_pdf = re.sub(r'<(?!(?:/?(?:b|i|u|br|a|font|ul|ol|li|p)))[^>]+>', '', texto_tramitacao, flags=re.IGNORECASE)
                texto_para_pdf = texto_para_pdf.strip()
            
            # Card moderno para o texto - Design elegante
            texto_card_data = [[Paragraph(texto_para_pdf, content_style)]]
            texto_card = Table(texto_card_data, colWidths=[460])
            texto_card.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), bg_card),
                ('TEXTCOLOR', (0, 0), (-1, -1), text_dark),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),  # Reduzido para compactar
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),  # Reduzido
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('BOX', (0, 0), (-1, -1), 1, border_light),  # Borda suave
            ]))
            story.append(texto_card)
            story.append(Spacer(1, 0.3*cm))  # Reduzido
        
        # Rodapé moderno e elegante
        story.append(Spacer(1, 0.5*cm))  # Aumentado para respiração
        
        # Linha divisória elegante com gradiente sutil (simulado com múltiplas linhas)
        linha_divisoria = Table([['']], colWidths=[460])
        linha_divisoria.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 1, border_light),  # Linha principal suave
        ]))
        story.append(linha_divisoria)
        story.append(Spacer(1, 0.4*cm))  # Aumentado
        
        # Localidade e data
        nom_localidade = str(dic_rodape.get('nom_localidade', '')).strip()
        dat_extenso = str(tramitacao_dic.get('dat_extenso', ''))
        if nom_localidade and dat_extenso:
            rodape_texto = f"{nom_localidade}, {dat_extenso}."
            story.append(Paragraph(escape(rodape_texto), footer_style))
            story.append(Spacer(1, 0.3*cm))  # Reduzido
        
        # Assinatura moderna
        nom_usuario_origem = str(tramitacao_dic.get('nom_usuario_origem', ''))
        nom_cargo_usuario_origem = str(tramitacao_dic.get('nom_cargo_usuario_origem', ''))
        
        if nom_usuario_origem or nom_cargo_usuario_origem:
            # Card de assinatura
            assinatura_data = []
            if nom_usuario_origem:
                assinatura_data.append([Paragraph(f"<b>{escape(nom_usuario_origem)}</b>", signature_style)])
            if nom_cargo_usuario_origem:
                assinatura_data.append([Paragraph(escape(nom_cargo_usuario_origem), footer_style)])
            
            if assinatura_data:
                assinatura_table = Table(assinatura_data, colWidths=[460])
                assinatura_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),  # Reduzido
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),  # Reduzido
                ]))
                story.append(assinatura_table)
        
        # Gera PDF com cabeçalho fixo
        doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header)
    
    def _get_nome_unidade(self, unidade: UnidadeTramitacao) -> str:
        """Obtém nome da unidade"""
        if unidade.comissao:
            return unidade.comissao.nom_comissao or ''
        elif unidade.orgao:
            return unidade.orgao.nom_orgao or ''
        elif unidade.parlamentar:
            return unidade.parlamentar.nom_parlamentar or ''
        return ''
    
    def _data_por_extenso(self, data: str) -> str:
        """Converte data para extenso (usa função do contexto Zope se disponível)"""
        if self.contexto_zope:
            try:
                return self.contexto_zope.pysc.data_converter_por_extenso_pysc(data=data)
            except Exception:
                pass
        # Fallback simples
        return data
