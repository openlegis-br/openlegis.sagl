# -*- coding: utf-8 -*-
"""Views para petição eletrônica"""

from grokcore.component import context
from grokcore.view import View as GrokView, name
from grokcore.security import require
from zope.interface import Interface
from Acquisition import aq_inner, aq_base
from DateTime import DateTime
import json
import logging
import base64
from openlegis.sagl.db_session import db_session_readonly
from openlegis.sagl.models.models import (
    Peticao, DocumentoAdministrativo, DocumentoAcessorio, NormaJuridica,
    Protocolo, Usuario, AssinaturaDocumento, TipoDocumentoAdministrativo,
    TipoNormaJuridica, TipoDocumento, MateriaLegislativa
)

logger = logging.getLogger(__name__)


class PeticaoAPIBase:
    """
    Classe base com métodos utilitários compartilhados para views de petição.
    Fornece métodos padronizados para validação, tratamento de erros e respostas JSON.
    """
    
    def _configurar_headers_json(self):
        """Configura headers padrão para respostas JSON"""
        self.request.response.setHeader('Content-Type', 'application/json')
        self.request.response.setHeader("Access-Control-Allow-Origin", "*")
    
    def _resolver_site_real(self, contexto_zope=None):
        """
        Resolve o site real removendo wrappers (RequestContainer, etc).
        
        Args:
            contexto_zope: Contexto Zope (opcional, usa self.context se não fornecido)
            
        Returns:
            Site real sem wrappers
        """
        if contexto_zope is None:
            contexto_zope = self.context
        
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
            
            # Estratégia 3: Se ainda não tem sapl_documentos, tenta acessar via getPhysicalRoot
            if not hasattr(site_real, 'sapl_documentos'):
                try:
                    root = contexto_zope.getPhysicalRoot()
                    if hasattr(root, 'sagl') and hasattr(root.sagl, 'sapl_documentos'):
                        site_real = root.sagl
                except Exception:
                    pass
                    
        except Exception as e:
            logger.warning(f"Erro ao resolver site real: {e}")
        
        return site_real
    
    def _resposta_json(self, dados, status_code=200):
        """
        Retorna resposta JSON padronizada.
        
        Args:
            dados: Dicionário com dados da resposta
            status_code: Código HTTP (não usado diretamente, mas pode ser útil)
            
        Returns:
            String JSON
        """
        self._configurar_headers_json()
        return json.dumps(dados, ensure_ascii=False)
    
    def _obter_parametro(self, nome, padrao=None, obrigatorio=False):
        """
        Obtém parâmetro do request.
        
        Args:
            nome: Nome do parâmetro
            padrao: Valor padrão se não encontrado
            obrigatorio: Se True, levanta Exception se não encontrado
            
        Returns:
            Valor do parâmetro
        """
        valor = self.request.form.get(nome, padrao)
        if obrigatorio and valor is None:
            raise ValueError(f"Parâmetro '{nome}' é obrigatório")
        return valor


class PeticaoAutuarExecutorView(GrokView, PeticaoAPIBase):
    """View chamada pela task Celery para obter dados da petição"""
    
    context(Interface)
    name('peticao_autuar_executor')
    require('zope2.View')
    
    def render(self):
        """Prepara dados da petição e retorna para a task processar
        
        IMPORTANTE: Esta view apenas OBTÉM dados. Não atualiza registros no banco.
        A manipulação de registros deve ser feita somente pelo registro de protocolo (protocolo_pysc.py).
        """
        
        try:
            cod_peticao = int(self._obter_parametro('cod_peticao', obrigatorio=True))
            
            # Resolve site real
            site = self._resolver_site_real()
            
            # Obtém dados da petição usando SQLAlchemy
            arq_data = None
            cod_validacao_doc = ''
            nom_autor = None
            outros = ''
            texto = ''
            info_protocolo = ''
            caminho = ''
            nom_pdf_saida = ''
            ind_doc_adm = ''
            ind_doc_materia = ''
            ind_norma = ''
            cod_norma = None
            
            # Tenta obter dados da petição - pode precisar de retry se os campos ainda não foram commitados
            # pelo protocolo_pysc.py (problema de timing entre commit e execução da task)
            max_retries = 3
            retry_delay = 0.5  # 500ms
            peticao = None
            
            for attempt in range(max_retries):
                with db_session_readonly() as session:
                    # Busca petição
                    peticao = session.query(Peticao).filter(
                        Peticao.cod_peticao == cod_peticao,
                        Peticao.ind_excluido == 0
                    ).first()
                    
                    if not peticao:
                        raise ValueError(f"Petição {cod_peticao} não encontrada")
                    
                    # Verifica se os campos necessários estão preenchidos
                    tem_campos = (
                        peticao.cod_documento is not None or 
                        peticao.cod_documento_vinculado is not None or
                        peticao.cod_doc_acessorio is not None or 
                        peticao.cod_norma is not None
                    )
                    
                    if tem_campos or attempt == max_retries - 1:
                        # Campos preenchidos ou última tentativa - continua
                        if not tem_campos:
                            logger.warning(
                                f"Petição {cod_peticao} ainda não tem campos preenchidos após {max_retries} tentativas. "
                                f"cod_documento={peticao.cod_documento}, cod_doc_acessorio={peticao.cod_doc_acessorio}, "
                                f"cod_norma={peticao.cod_norma}. O protocolo_pysc.py deve preencher esses campos."
                            )
                        break
                    else:
                        # Campos não preenchidos - aguarda e tenta novamente
                        logger.debug(
                            f"Petição {cod_peticao} ainda não tem campos preenchidos (tentativa {attempt + 1}/{max_retries}). "
                            f"Aguardando {retry_delay}s antes de tentar novamente..."
                        )
                        import time
                        time.sleep(retry_delay)
                        continue
            
            # Continua com a petição obtida - re-busca na sessão para garantir consistência
            with db_session_readonly() as session:
                # Re-busca petição para garantir que está na mesma sessão
                peticao = session.query(Peticao).filter(
                    Peticao.cod_peticao == cod_peticao,
                    Peticao.ind_excluido == 0
                ).first()
                
                if not peticao:
                    raise ValueError(f"Petição {cod_peticao} não encontrada")
            
                # Tenta pegar PDF assinado (documentos_assinados)
                validacao = session.query(AssinaturaDocumento).filter(
                    AssinaturaDocumento.tipo_doc == 'peticao',
                    AssinaturaDocumento.codigo == cod_peticao,
                    AssinaturaDocumento.ind_assinado == 1,
                    AssinaturaDocumento.ind_excluido == 0
                ).first()
                
                if validacao:
                    # PDF assinado encontrado
                    nom_pdf_peticao = f"{validacao.cod_assinatura_doc}.pdf"
                    
                    # Formata código de verificação (precisa acessar via portal_skins)
                    if hasattr(site, 'portal_skins') and hasattr(site.portal_skins, 'sk_sagl'):
                        skins = site.portal_skins.sk_sagl
                        if hasattr(skins, 'cadastros') and hasattr(skins.cadastros, 'assinatura'):
                            cod_validacao_doc = str(
                                skins.cadastros.assinatura.format_verification_code(code=validacao.cod_assinatura_doc)
                            )
                    
                    if nom_pdf_peticao in site.sapl_documentos.documentos_assinados.objectIds():
                        arq_data = site.sapl_documentos.documentos_assinados[nom_pdf_peticao].data
                    else:
                        raise FileNotFoundError(
                            f"Arquivo assinado {nom_pdf_peticao} não encontrado em documentos_assinados."
                        )
                    
                    # Tenta extrair assinaturas do PDF
                    try:
                        from openlegis.sagl.tasks_folder.utils import get_signatures
                        from io import BytesIO
                        pdf_stream = BytesIO(bytes(arq_data))
                        signers = get_signatures(pdf_stream) or []
                        
                        if signers:
                            nom_autor = signers[0].get('signer_name')
                            qtde_assinaturas = len(signers)
                            if qtde_assinaturas == 2:
                                outros = " e outro"
                            elif qtde_assinaturas > 2:
                                outros = " e outros"
                    except Exception as e:
                        logger.warning(f"Falha ao extrair assinaturas: {e}")
                else:
                    # Não havia assinatura "documentos_assinados": usa PDF em /peticao
                    nom_pdf_peticao = f"{cod_peticao}.pdf"
                    if nom_pdf_peticao in site.sapl_documentos.peticao.objectIds():
                        arq_data = site.sapl_documentos.peticao[nom_pdf_peticao].data
                    else:
                        raise FileNotFoundError(f"Arquivo da petição {nom_pdf_peticao} não encontrado.")
                    
                    # Busca autor via usuário
                    usuario = session.query(Usuario).filter(
                        Usuario.cod_usuario == peticao.cod_usuario
                    ).first()
                    if usuario:
                        nom_autor = usuario.nom_completo
            
                if not arq_data:
                    raise ValueError("Arquivo da petição está vazio.")
                
                # ======================
                # 2) Contexto de destino (texto/caminho/arquivo de saída) - EXATAMENTE como na task antiga
                # ======================
                # Inicializa info_protocolo exatamente como na task antiga
                info_protocolo = f"- Recebido em {peticao.dat_recebimento}." if peticao.dat_recebimento else "- Recebido em data não informada."
                texto = ''
                caminho = ''
                nom_pdf_saida = ''
                # Determina indicadores baseado nos campos cod_* preenchidos (para compatibilidade)
                ind_doc_adm = ''
                ind_doc_materia = ''
                ind_norma = ''
                
                # Log para debug: mostra o estado dos campos
                logger.debug(
                    f"Petição {cod_peticao}: cod_documento={peticao.cod_documento}, "
                    f"cod_documento_vinculado={peticao.cod_documento_vinculado}, "
                    f"cod_doc_acessorio={peticao.cod_doc_acessorio}, "
                    f"cod_norma={peticao.cod_norma}, "
                    f"num_protocolo={peticao.num_protocolo}"
                )
                
                # EXATAMENTE como na task antiga: usa os campos cod_* diretamente
                # Prioriza cod_documento, depois cod_doc_acessorio, depois cod_norma
                if peticao.cod_documento is not None or peticao.cod_documento_vinculado is not None:
                    # Busca documento administrativo usando cod_documento (ou cod_documento_vinculado como fallback)
                    cod_documento_para_buscar = peticao.cod_documento
                    if cod_documento_para_buscar is None and peticao.cod_documento_vinculado is not None:
                        cod_documento_para_buscar = peticao.cod_documento_vinculado
                    
                    if cod_documento_para_buscar is None:
                        raise ValueError(f"Petição {cod_peticao} tem cod_documento_vinculado mas não tem cod_documento")
                    
                    # Busca documento administrativo - EXATAMENTE como zsql documento_administrativo_obter_zsql(cod_documento=peticao.cod_documento)
                    documento = session.query(DocumentoAdministrativo).filter(
                        DocumentoAdministrativo.cod_documento == cod_documento_para_buscar,
                        DocumentoAdministrativo.ind_excluido == 0
                    ).first()
                    
                    if not documento:
                        raise ValueError(f"Documento administrativo {cod_documento_para_buscar} não encontrado")
                    
                    # Busca protocolo exatamente como na task antiga: protocolo_obter_zsql(num_protocolo=documento.num_protocolo, ano_protocolo=documento.ano_documento)
                    if documento.num_protocolo and documento.ano_documento:
                        protocolo = session.query(Protocolo).filter(
                            Protocolo.num_protocolo == documento.num_protocolo,
                            Protocolo.ano_protocolo == documento.ano_documento
                        ).first()
                        if protocolo:
                            # Formata exatamente como na task antiga: DateTime(protocolo.dat_protocolo).strftime('%d/%m/%Y') protocolo.hor_protocolo
                            try:
                                from DateTime import DateTime as ZopeDateTime
                                dat_str = ZopeDateTime(protocolo.dat_protocolo).strftime('%d/%m/%Y')
                            except:
                                if hasattr(protocolo.dat_protocolo, 'strftime'):
                                    dat_str = protocolo.dat_protocolo.strftime('%d/%m/%Y')
                                else:
                                    dat_str = str(protocolo.dat_protocolo)
                            hor_str = str(protocolo.hor_protocolo) if protocolo.hor_protocolo else ''
                            # Formata exatamente como na task antiga
                            info_protocolo = (
                                f" - Prot. nº {protocolo.num_protocolo}/{protocolo.ano_protocolo} "
                                f"{dat_str} {hor_str}."
                            )
                    
                    # Busca tipo de documento (des_tipo_documento) - vem do JOIN com tipo_documento_administrativo no zsql
                    des_tipo_documento = ''
                    if documento.tipo_documento_administrativo:
                        des_tipo_documento = documento.tipo_documento_administrativo.des_tipo_documento or ''
                    
                    texto = f"{des_tipo_documento} nº {documento.num_documento}/{documento.ano_documento}"
                    nom_pdf_saida = f"{documento.cod_documento}_texto_integral.pdf"
                    caminho = '/sapl_documentos/administrativo/'
                    ind_doc_adm = "1"
                
                elif peticao.cod_doc_acessorio is not None:
                    # Busca documento acessório usando cod_doc_acessorio - EXATAMENTE como zsql documento_acessorio_obter_zsql(cod_documento=peticao.cod_doc_acessorio)
                    
                    documento = session.query(DocumentoAcessorio).filter(
                        DocumentoAcessorio.cod_documento == peticao.cod_doc_acessorio,
                        DocumentoAcessorio.ind_excluido == 0
                    ).first()
                    
                    if not documento:
                        raise ValueError(f"Documento acessório {peticao.cod_doc_acessorio} não encontrado")
                    
                    # Busca matéria exatamente como na task antiga: materia_obter_zsql(cod_materia=documento.cod_materia)
                    id_materia = ""
                    if documento.cod_materia:
                        materia = session.query(MateriaLegislativa).filter(
                            MateriaLegislativa.cod_materia == documento.cod_materia,
                            MateriaLegislativa.ind_excluido == 0
                        ).first()
                        if materia and materia.tipo_materia_legislativa:
                            id_materia = f"{materia.tipo_materia_legislativa.sgl_tipo_materia or ''} {materia.num_ident_basica or ''}/{materia.ano_ident_basica or ''}"
                    
                    # Busca tipo de documento (des_tipo_documento) - vem do JOIN com tipo_documento no zsql
                    des_tipo_documento = ''
                    if documento.tipo_documento:
                        des_tipo_documento = documento.tipo_documento.des_tipo_documento or ''
                    
                    texto = f"{des_tipo_documento} - {id_materia}".strip(" -")
                    nom_pdf_saida = f"{documento.cod_documento}.pdf"
                    caminho = '/sapl_documentos/materia/'
                    ind_doc_materia = "1"
                
                elif peticao.cod_norma is not None:
                    # Busca norma usando cod_norma - EXATAMENTE como zsql norma_juridica_obter_zsql(cod_norma=peticao.cod_norma)
                    
                    norma = session.query(NormaJuridica).filter(
                        NormaJuridica.cod_norma == peticao.cod_norma,
                        NormaJuridica.ind_excluido == 0
                    ).first()
                    
                    if not norma:
                        raise ValueError(f"Norma {peticao.cod_norma} não encontrada")
                    
                    # Busca tipo de norma (des_tipo_norma) - vem do JOIN com tipo_norma_juridica no zsql
                    des_tipo_norma = ''
                    if norma.tipo_norma_juridica:
                        des_tipo_norma = norma.tipo_norma_juridica.des_tipo_norma or ''
                    
                    texto = f"{des_tipo_norma} nº {norma.num_norma}/{norma.ano_norma}"
                    cod_norma = norma.cod_norma
                    nom_pdf_saida = f"{norma.cod_norma}_texto_integral.pdf"
                    caminho = '/sapl_documentos/norma_juridica/'
                    ind_norma = "1"
                
                # Verifica se conseguiu determinar o destino - EXATAMENTE como na task antiga
                if not nom_pdf_saida:
                    # Log detalhado para debug
                    logger.error(
                        f"Petição {cod_peticao} não tem campos preenchidos: "
                        f"cod_documento={peticao.cod_documento}, "
                        f"cod_documento_vinculado={peticao.cod_documento_vinculado}, "
                        f"cod_doc_acessorio={peticao.cod_doc_acessorio}, "
                        f"cod_norma={peticao.cod_norma}, "
                        f"num_protocolo={peticao.num_protocolo}. "
                        f"O protocolo_pysc.py deve preencher esses campos antes de chamar a task."
                    )
                    raise ValueError(
                        "Não foi possível determinar o destino do arquivo (nom_pdf_saida). "
                        "Verifique os indicadores ind_doc_adm / ind_doc_materia / ind_norma. "
                        "A petição deve ter cod_documento, cod_doc_acessorio ou cod_norma preenchido."
                    )
            
            # Converte PDF para base64
            pdf_base64 = base64.b64encode(bytes(arq_data)).decode('utf-8')
            
            # IMPORTANTE: Esta view apenas OBTÉM dados. Não atualiza registros no banco.
            # A manipulação de registros deve ser feita somente pelo registro de protocolo (protocolo_pysc.py).
            
            # Retorna dados
            dados = {
                'pdf_base64': pdf_base64,
                'cod_validacao_doc': cod_validacao_doc,
                'nom_autor': nom_autor,
                'outros': outros,
                'texto': texto,
                'info_protocolo': info_protocolo,
                'caminho': caminho,
                'nom_pdf_saida': nom_pdf_saida,
                'ind_doc_adm': ind_doc_adm,
                'ind_norma': ind_norma,
                'cod_norma': cod_norma,
            }
            
            return self._resposta_json({
                'success': True,
                'dados': dados,
                'cod_peticao': cod_peticao
            })
        
        except Exception as e:
            logger.error(f"Erro ao preparar dados na view executor: {e}", exc_info=True)
            return self._resposta_json({
                'success': False,
                'error': str(e)
            })


class PeticaoAutuarSalvarView(GrokView, PeticaoAPIBase):
    """View para salvar PDF gerado pela task no repositório"""
    
    context(Interface)
    name('peticao_autuar_salvar')
    require('zope2.View')
    
    def render(self):
        """Salva PDF no repositório Zope"""
        try:
            cod_peticao = self._obter_parametro('cod_peticao', obrigatorio=True)
            pdf_base64 = self._obter_parametro('pdf_base64', obrigatorio=True)
            nom_pdf_saida = self._obter_parametro('nom_pdf_saida', obrigatorio=True)
            texto = self._obter_parametro('texto', '')
            ind_norma = self._obter_parametro('ind_norma', '')
            cod_norma = self._obter_parametro('cod_norma', '')
            
            if not pdf_base64:
                return self._resposta_json({
                    'success': False,
                    'error': 'pdf_base64 não fornecido'
                })
            
            # Decodifica PDF
            try:
                pdf_bytes = base64.b64decode(pdf_base64)
            except Exception as e:
                return self._resposta_json({
                    'success': False,
                    'error': f'Erro ao decodificar PDF: {str(e)}'
                })
            
            # Resolve site real
            site = self._resolver_site_real()
            
            # Determina storage_path baseado nos indicadores
            storage_path = None
            
            if ind_norma == "1":
                storage_path = site.sapl_documentos.norma_juridica
            elif nom_pdf_saida.endswith('_texto_integral.pdf'):
                # Documento administrativo
                storage_path = site.sapl_documentos.administrativo
            else:
                # Documento acessório (matéria) - formato: cod_documento.pdf
                storage_path = site.sapl_documentos.materia
            
            if not storage_path:
                return self._resposta_json({
                    'success': False,
                    'error': 'Não foi possível determinar o repositório de destino'
                })
            
            # Salva ou atualiza PDF
            if nom_pdf_saida in storage_path.objectIds():
                arquivo_peticao = storage_path[nom_pdf_saida]
                arquivo_peticao.update_data(pdf_bytes)
            else:
                storage_path.manage_addFile(id=nom_pdf_saida, file=pdf_bytes, title=texto)
                arquivo_peticao = storage_path[nom_pdf_saida]
            
            # Permissões
            arquivo_peticao.manage_permission('View', roles=['Manager', 'Authenticated'], acquire=0)
            if ind_norma == "1" and cod_norma:
                arquivo_peticao.manage_permission('View', roles=['Manager', 'Anonymous'], acquire=1)
                # Atualiza catálogo
                site.sapl_documentos.norma_juridica.Catalog.atualizarCatalogo(cod_norma=cod_norma)
            
            logger.info(f"PeticaoAutuarSalvarView - PDF salvo no repositório (cod_peticao={cod_peticao}, arquivo={nom_pdf_saida})")
            
            return self._resposta_json({
                'success': True,
                'message': 'PDF salvo com sucesso',
                'cod_peticao': cod_peticao,
                'nom_pdf_saida': nom_pdf_saida
            })
        
        except Exception as e:
            logger.error(f"Erro ao salvar PDF na view: {e}", exc_info=True)
            return self._resposta_json({
                'success': False,
                'error': str(e)
            })
