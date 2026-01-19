# -*- coding: utf-8 -*-
"""Serviço para geração e registro de protocolo da Prefeitura

INTEGRAÇÃO PENDENTE:
===================
Este módulo foi implementado conforme Fase 4 do plano de implementação, mas a integração
com api.py -> TramitacaoIndividualSalvarView está PENDENTE.

Para integrar, adicionar após o processamento de notificações em api.py (linha ~3143):
    
    # TODO: INTEGRAR - Processa protocolo prefeitura (apenas MATÉRIAS)
    # if tipo == 'MATERIA' and dados.get('cod_unid_tram_dest'):
    #     try:
    #         from .protocolo_prefeitura.service import ProtocoloPrefeituraService
    #         protocolo_service = ProtocoloPrefeituraService(session, self.context)
    #         texto_protocolo = protocolo_service.processar_protocolo_se_necessario(
    #             cod_entidade_int, 
    #             cod_tramitacao_retorno, 
    #             dados.get('cod_unid_tram_dest')
    #         )
    #         if texto_protocolo:
    #             logger.info(f"TramitacaoIndividualSalvarView - Protocolo prefeitura gerado: {texto_protocolo[:50]}...")
    #     except Exception as e:
    #         logger.warning(f"TramitacaoIndividualSalvarView - Erro ao processar protocolo prefeitura: {e}", exc_info=True)
    #         # Não bloqueia envio se protocolo falhar

Ver PLANO_IMPLEMENTACAO_COMPLETO_TRAMITACAO.md seção 6.2 para mais detalhes.
"""

from typing import Dict, Any, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import inspect, text
import logging
import json

logger = logging.getLogger(__name__)

# Importação de requests (opcional - apenas se API estiver configurada)
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("ProtocoloPrefeituraService - módulo 'requests' não disponível. Chamadas HTTP desabilitadas.")

from openlegis.sagl.models.models import (
    MateriaLegislativa, Autoria, Autor,
    UnidadeTramitacao, Tramitacao, TipoMateriaLegislativa
)

logger = logging.getLogger(__name__)


class ProtocoloPrefeituraService:
    """Gera e registra protocolo da Prefeitura quando tramitação vai para Prefeitura/Executivo"""
    
    def __init__(self, session: Session, contexto_zope):
        """
        Inicializa service com sessão SQLAlchemy e contexto Zope
        
        Args:
            session: Sessão SQLAlchemy
            contexto_zope: Contexto Zope (para acessar portal_sagl.protocolo_prefeitura)
        """
        self.session = session
        self.context = contexto_zope
    
    def _get_nome_unidade_tramitacao(self, unidade: UnidadeTramitacao) -> str:
        """
        Obtém o nome da unidade de tramitação (baseado em _get_nome_unidade_tramitacao de api.py)
        
        Args:
            unidade: Instância de UnidadeTramitacao
        
        Returns:
            Nome da unidade (comissão, órgão ou parlamentar)
        """
        if not unidade:
            return ''
        
        # Tenta obter nome de Comissao
        if unidade.comissao:
            return unidade.comissao.nom_comissao or ''
        
        # Tenta obter nome de Orgao
        if unidade.orgao:
            return unidade.orgao.nom_orgao or ''
        
        # Tenta obter nome de Parlamentar
        if unidade.parlamentar:
            return unidade.parlamentar.nom_parlamentar or ''
        
        return unidade.nom_unidade_join or ''
    
    def verificar_deve_gerar_protocolo(self, cod_unid_tram_dest: int) -> bool:
        """
        Verifica se deve gerar protocolo (Prefeitura/Executivo)
        
        Args:
            cod_unid_tram_dest: Código da unidade de destino
        
        Returns:
            True se deve gerar protocolo, False caso contrário
        """
        try:
            if not cod_unid_tram_dest:
                return False
            
            # Busca UnidadeTramitacao com relacionamentos
            unidade = self.session.query(UnidadeTramitacao).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UnidadeTramitacao.cod_unid_tramitacao == cod_unid_tram_dest,
                UnidadeTramitacao.ind_excluido == 0
            ).first()
            
            if not unidade:
                logger.warning(f"ProtocoloPrefeituraService.verificar_deve_gerar_protocolo - Unidade {cod_unid_tram_dest} não encontrada")
                return False
            
            # Obtém nome usando mesma lógica de _get_nome_unidade_tramitacao
            nome_unidade = self._get_nome_unidade_tramitacao(unidade)
            
            # Verifica se 'Prefeitura' ou 'Executivo' está no nome (case-insensitive)
            nome_upper = nome_unidade.upper()
            deve_gerar = 'PREFEITURA' in nome_upper or 'EXECUTIVO' in nome_upper
            
            logger.debug(f"ProtocoloPrefeituraService.verificar_deve_gerar_protocolo - Unidade: {nome_unidade}, Deve gerar: {deve_gerar}")
            return deve_gerar
            
        except Exception as e:
            logger.error(f"ProtocoloPrefeituraService.verificar_deve_gerar_protocolo - Erro ao verificar: {e}", exc_info=True)
            return False
    
    def criar_payload_protocolo(self, cod_materia: int) -> Dict[str, Any]:
        """
        Cria payload para API da prefeitura (usando SQLAlchemy)
        
        Equivalente a SAGLTool.create_payload. Busca MateriaLegislativa com:
        - Autoria -> Autor (para autoria)
        - tipo_materia_legislativa (para des_tipo_materia)
        - tramitacao (última) para prazo
        
        Args:
            cod_materia: Código da matéria
        
        Returns:
            Dicionário com payload: codmateria, tipo, numero, ano, ementa, autoria, linkarquivo, casalegislativa, prazo
        """
        try:
            # Busca matéria com relacionamentos
            materia = self.session.query(MateriaLegislativa).options(
                selectinload(MateriaLegislativa.autoria).selectinload(Autoria.autor),
                selectinload(MateriaLegislativa.tipo_materia_legislativa)
            ).filter(
                MateriaLegislativa.cod_materia == cod_materia,
                MateriaLegislativa.ind_excluido == 0
            ).first()
            
            if not materia:
                raise ValueError(f"Matéria {cod_materia} não encontrada")
            
            # Obtém tipo da matéria
            tipo_materia = materia.tipo_materia_legislativa.des_tipo_materia if materia.tipo_materia_legislativa else ''
            
            # Obtém autoria (lista de nomes dos autores)
            lista_autoria = []
            for autoria in materia.autoria:
                if autoria.autor:
                    nome_autor = autoria.autor.nom_autor_join or autoria.autor.nom_autor
                    if nome_autor:
                        lista_autoria.append(nome_autor)
            autoria = ', '.join(lista_autoria) if lista_autoria else ''
            
            # Obtém prazo da última tramitação
            prazo = None
            tramitacao = self.session.query(Tramitacao).filter(
                Tramitacao.cod_materia == cod_materia,
                Tramitacao.ind_ult_tramitacao == 1,
                Tramitacao.ind_excluido == 0
            ).first()
            
            if tramitacao and tramitacao.dat_fim_prazo:
                prazo = tramitacao.dat_fim_prazo.strftime('%d/%m/%Y')
            
            # Obtém configurações da casa legislativa
            casa_legislativa = ''
            try:
                casa = {}
                aux = self.context.sapl_documentos.props_sagl.propertyItems()
                for item in aux:
                    casa[item[0]] = item[1]
                casa_legislativa = casa.get('nom_casa', '')
            except Exception as e:
                logger.warning(f"ProtocoloPrefeituraService.criar_payload_protocolo - Erro ao obter nom_casa: {e}")
            
            # Gera link do arquivo (se houver)
            linkarquivo = ''
            try:
                request = self.context.REQUEST
                server_url = request.SERVER_URL
                linkarquivo = f"{server_url}/consultas/materia/materia_mostrar_proc?cod_materia={cod_materia}"
            except Exception as e:
                logger.warning(f"ProtocoloPrefeituraService.criar_payload_protocolo - Erro ao gerar linkarquivo: {e}")
            
            # Monta payload
            payload = {
                'codmateria': cod_materia,
                'tipo': tipo_materia,
                'numero': materia.num_ident_basica,
                'ano': materia.ano_ident_basica,
                'ementa': materia.txt_ementa or '',
                'autoria': autoria,
                'linkarquivo': linkarquivo,
                'casalegislativa': casa_legislativa,
                'prazo': prazo
            }
            
            logger.debug(f"ProtocoloPrefeituraService.criar_payload_protocolo - Payload criado para matéria {cod_materia}")
            return payload
            
        except Exception as e:
            logger.error(f"ProtocoloPrefeituraService.criar_payload_protocolo - Erro ao criar payload: {e}", exc_info=True)
            raise
    
    def _obter_configuracoes_api(self) -> Dict[str, str]:
        """
        Obtém configurações da API da prefeitura (props_sagl com fallback para valores fixos)
        
        Busca no props_sagl, se não encontrar, usa valores fixos como fallback.
        Valores fixos podem ser alterados diretamente no código se necessário.
        
        Returns:
            Dicionário com 'endpoint', 'user', 'password'
        """
        # Valores fixos como fallback (podem ser alterados no código se necessário)
        FALLBACK_ENDPOINT = ""
        FALLBACK_USER = ""
        FALLBACK_PASSWORD = ""
        
        try:
            # Tenta obter configurações do props_sagl primeiro
            casa = {}
            aux = self.context.sapl_documentos.props_sagl.propertyItems()
            for item in aux:
                casa[item[0]] = item[1]
            
            # Busca configurações no props_sagl (suporta diferentes nomes de propriedades)
            endpoint = casa.get('api_prefeitura_endpoint') or casa.get('endpoint_api_prefeitura') or FALLBACK_ENDPOINT
            user = casa.get('api_prefeitura_user') or casa.get('user_api_prefeitura') or FALLBACK_USER
            password = casa.get('api_prefeitura_password') or casa.get('password_api_prefeitura') or FALLBACK_PASSWORD
            
            if endpoint:
                logger.debug(f"ProtocoloPrefeituraService._obter_configuracoes_api - Configurações obtidas do props_sagl")
                return {
                    'endpoint': endpoint,
                    'user': user,
                    'password': password
                }
            else:
                logger.debug(f"ProtocoloPrefeituraService._obter_configuracoes_api - Usando valores fixos como fallback")
                return {
                    'endpoint': FALLBACK_ENDPOINT,
                    'user': FALLBACK_USER,
                    'password': FALLBACK_PASSWORD
                }
        except Exception as e:
            logger.warning(f"ProtocoloPrefeituraService._obter_configuracoes_api - Erro ao obter configurações do props_sagl: {e}, usando valores fixos")
            return {
                'endpoint': FALLBACK_ENDPOINT,
                'user': FALLBACK_USER,
                'password': FALLBACK_PASSWORD
            }
    
    def gerar_protocolo(self, cod_materia: int) -> str:
        """
        Gera protocolo da prefeitura (replicado do SAGLTool - não usa SAGLTool)
        
        Replica a lógica de SAGLTool.protocolo_prefeitura():
        - Obtém configurações da API (props_sagl com fallback para valores fixos)
        - Cria payload usando criar_payload_protocolo()
        - Chama API da prefeitura via HTTP POST (se endpoint configurado)
        - Retorna texto do protocolo gerado ou payload como fallback
        
        Args:
            cod_materia: Código da matéria
        
        Returns:
            Texto do protocolo gerado pela API da prefeitura ou payload JSON como fallback
        """
        try:
            # Obtém configurações da API (props_sagl com fallback para valores fixos)
            config_api = self._obter_configuracoes_api()
            API_ENDPOINT = config_api['endpoint']
            API_USER = config_api['user']
            API_PASSWORD = config_api['password']
            
            # Cria payload usando método existente
            payload = self.criar_payload_protocolo(cod_materia)
            
            # Se não houver endpoint configurado, retorna payload como string JSON
            # (compatível com implementação antiga que pode não ter API configurada)
            if not API_ENDPOINT:
                logger.warning(f"ProtocoloPrefeituraService.gerar_protocolo - API_ENDPOINT não configurado para matéria {cod_materia}")
                # Retorna payload formatado como string (como fallback)
                return json.dumps(payload, sort_keys=True, indent=3, ensure_ascii=False)
            
            # Faz chamada HTTP POST para API da prefeitura
            if not REQUESTS_AVAILABLE:
                logger.warning(f"ProtocoloPrefeituraService.gerar_protocolo - Módulo 'requests' não disponível, retornando payload como fallback")
                return json.dumps(payload, sort_keys=True, indent=3, ensure_ascii=False)
            
            try:
                # Prepara autenticação se houver
                auth = None
                if API_USER and API_PASSWORD:
                    from requests.auth import HTTPBasicAuth
                    auth = HTTPBasicAuth(API_USER, API_PASSWORD)
                
                # Faz requisição POST
                headers = {'Content-Type': 'application/json'}
                response = requests.post(
                    API_ENDPOINT,
                    json=payload,
                    auth=auth,
                    headers=headers,
                    timeout=30  # Timeout de 30 segundos
                )
                
                # Verifica resposta
                response.raise_for_status()  # Lança exceção se status não for 2xx
                
                # Tenta obter texto do protocolo da resposta
                if response.text:
                    texto_protocolo = response.text
                elif response.json():
                    # Se for JSON, converte para string
                    texto_protocolo = json.dumps(response.json(), ensure_ascii=False)
                else:
                    logger.warning(f"ProtocoloPrefeituraService.gerar_protocolo - Resposta vazia da API para matéria {cod_materia}")
                    return ''
                
                logger.info(f"ProtocoloPrefeituraService.gerar_protocolo - Protocolo gerado via API para matéria {cod_materia}")
                return str(texto_protocolo)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"ProtocoloPrefeituraService.gerar_protocolo - Erro na requisição HTTP para API da prefeitura: {e}", exc_info=True)
                # Em caso de erro na API, retorna payload como fallback
                logger.warning(f"ProtocoloPrefeituraService.gerar_protocolo - Retornando payload como fallback devido a erro na API")
                return json.dumps(payload, sort_keys=True, indent=3, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"ProtocoloPrefeituraService.gerar_protocolo - Erro ao gerar protocolo: {e}", exc_info=True)
            # Tenta retornar payload como fallback
            try:
                payload = self.criar_payload_protocolo(cod_materia)
                return json.dumps(payload, sort_keys=True, indent=3, ensure_ascii=False)
            except Exception as fallback_error:
                logger.error(f"ProtocoloPrefeituraService.gerar_protocolo - Erro no fallback: {fallback_error}", exc_info=True)
                raise
    
    def salvar_protocolo(self, cod_tramitacao: int, texto_protocolo: str) -> bool:
        """
        Salva protocolo na tramitação
        
        PRECISA VERIFICAR ESTRUTURA:
        - Opção A: Tabela tramitacao_prefeitura (criar modelo TramitacaoPrefeitura)
        - Opção B: Campo texto_protocolo em Tramitacao (adicionar campo ao modelo)
        
        Por enquanto, implementa verificação dinâmica:
        - Tenta verificar se existe coluna texto_protocolo na tabela tramitacao
        - Se existir, atualiza o campo
        - Se não existir, tenta inserir na tabela tramitacao_prefeitura (se existir)
        - Loga aviso se nenhuma estrutura for encontrada
        
        Args:
            cod_tramitacao: Código da tramitação
            texto_protocolo: Texto do protocolo a ser salvo
        
        Returns:
            True se salvo com sucesso, False caso contrário
        """
        try:
            if not texto_protocolo:
                logger.warning(f"ProtocoloPrefeituraService.salvar_protocolo - Texto do protocolo vazio para tramitação {cod_tramitacao}")
                return False
            
            # Busca tramitação
            tramitacao = self.session.query(Tramitacao).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao,
                Tramitacao.ind_excluido == 0
            ).first()
            
            if not tramitacao:
                logger.warning(f"ProtocoloPrefeituraService.salvar_protocolo - Tramitação {cod_tramitacao} não encontrada")
                return False
            
            # Verifica se existe coluna texto_protocolo na tabela tramitacao
            inspector = inspect(self.session.bind)
            columns = [col['name'] for col in inspector.get_columns('tramitacao')]
            
            if 'texto_protocolo' in columns:
                # Opção B: Campo texto_protocolo existe - atualiza
                tramitacao.texto_protocolo = texto_protocolo
                from zope.sqlalchemy import mark_changed
                mark_changed(self.session, keep_session=True)
                logger.info(f"ProtocoloPrefeituraService.salvar_protocolo - Protocolo salvo no campo texto_protocolo (tramitação {cod_tramitacao})")
                return True
            else:
                # Verifica se existe tabela tramitacao_prefeitura
                tables = inspector.get_table_names()
                if 'tramitacao_prefeitura' in tables:
                    # Opção A: Tabela tramitacao_prefeitura existe - insere/atualiza
                    # Usa SQL direto pois não temos modelo
                    result = self.session.execute(
                        text("""
                            INSERT INTO tramitacao_prefeitura (cod_tramitacao, texto_protocolo)
                            VALUES (:cod_tramitacao, :texto_protocolo)
                            ON DUPLICATE KEY UPDATE texto_protocolo = :texto_protocolo
                        """),
                        {'cod_tramitacao': cod_tramitacao, 'texto_protocolo': texto_protocolo}
                    )
                    from zope.sqlalchemy import mark_changed
                    mark_changed(self.session, keep_session=True)
                    logger.info(f"ProtocoloPrefeituraService.salvar_protocolo - Protocolo salvo na tabela tramitacao_prefeitura (tramitação {cod_tramitacao})")
                    return True
                else:
                    # Estrutura não encontrada - loga aviso
                    logger.warning(
                        f"ProtocoloPrefeituraService.salvar_protocolo - "
                        f"Estrutura de armazenamento não encontrada para tramitação {cod_tramitacao}. "
                        f"Protocolo gerado: {texto_protocolo[:100]}..."
                    )
                    logger.warning(
                        "ProtocoloPrefeituraService.salvar_protocolo - "
                        "Necessário criar campo 'texto_protocolo' na tabela 'tramitacao' "
                        "OU criar tabela 'tramitacao_prefeitura' com colunas 'cod_tramitacao' e 'texto_protocolo'"
                    )
                    return False
            
        except Exception as e:
            logger.error(f"ProtocoloPrefeituraService.salvar_protocolo - Erro ao salvar protocolo: {e}", exc_info=True)
            return False
    
    def processar_protocolo_se_necessario(
        self, 
        cod_materia: int, 
        cod_tramitacao: int, 
        cod_unid_tram_dest: int
    ) -> Optional[str]:
        """
        Método principal: verifica e gera protocolo se necessário
        
        Args:
            cod_materia: Código da matéria
            cod_tramitacao: Código da tramitação
            cod_unid_tram_dest: Código da unidade de destino
        
        Returns:
            Texto do protocolo gerado ou None se não deve gerar/falhou
        """
        try:
            # 1. Verifica se deve gerar protocolo
            if not self.verificar_deve_gerar_protocolo(cod_unid_tram_dest):
                logger.debug(f"ProtocoloPrefeituraService.processar_protocolo_se_necessario - Não deve gerar protocolo para unidade {cod_unid_tram_dest}")
                return None
            
            # 2. Cria payload e gera protocolo
            try:
                # Nota: O SAGLTool.protocolo_prefeitura pode usar o payload internamente
                # ou pode buscar os dados diretamente. Por enquanto, geramos diretamente.
                texto_protocolo = self.gerar_protocolo(cod_materia)
                
                if not texto_protocolo:
                    logger.warning(f"ProtocoloPrefeituraService.processar_protocolo_se_necessario - Protocolo vazio para matéria {cod_materia}")
                    return None
            except Exception as e:
                logger.error(f"ProtocoloPrefeituraService.processar_protocolo_se_necessario - Erro ao gerar protocolo: {e}", exc_info=True)
                return None
            
            # 3. Salva protocolo
            try:
                salvo = self.salvar_protocolo(cod_tramitacao, texto_protocolo)
                if not salvo:
                    logger.warning(f"ProtocoloPrefeituraService.processar_protocolo_se_necessario - Protocolo não salvo para tramitação {cod_tramitacao}")
                    # Mesmo assim retorna o protocolo gerado
            except Exception as e:
                logger.error(f"ProtocoloPrefeituraService.processar_protocolo_se_necessario - Erro ao salvar protocolo: {e}", exc_info=True)
                # Mesmo assim retorna o protocolo gerado
            
            # 4. Retorna texto_protocolo
            logger.info(f"ProtocoloPrefeituraService.processar_protocolo_se_necessario - Protocolo processado com sucesso para matéria {cod_materia}, tramitação {cod_tramitacao}")
            return texto_protocolo
            
        except Exception as e:
            logger.error(f"ProtocoloPrefeituraService.processar_protocolo_se_necessario - Erro ao processar protocolo: {e}", exc_info=True)
            return None
