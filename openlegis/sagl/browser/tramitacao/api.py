# -*- coding: utf-8 -*-
"""Views AJAX para tramitação"""

from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from grokcore.component import context
from grokcore.view import View as GrokView, name
from grokcore.security import require
from zope.interface import Interface
from openlegis.sagl.models.models import (
    UnidadeTramitacao, StatusTramitacao, StatusTramitacaoAdministrativo,
    UsuarioUnidTram, Usuario, AssinaturaDocumento
)
import json
import logging
import threading
import traceback

from .config import get_session
from openlegis.sagl.db_session import db_session_readonly  # APENAS para leitura
from zope.sqlalchemy import mark_changed
from AccessControl import getSecurityManager
from openlegis.sagl.models.models import Comissao, Orgao, Parlamentar
from sqlalchemy.orm import selectinload
from Acquisition import aq_inner, aq_base
from .utils import (
    cached, validar_codigo_inteiro_seguro, validar_string_segura, validar_tipo_enum,
    validar_arquivo_seguro, sanitizar_nome_arquivo, validar_data_segura,
    SecurityValidationError, FileValidationError,
    invalidar_cache_unidade, invalidar_cache_usuario
)

logger = logging.getLogger(__name__)

# Importa novo renderizador de formulários
from .forms.renderer import TramitacaoFormRenderer


# ---------------------------------------------------------------------
# SessionFactory Centralizado - Usa padrão SAGL
# ---------------------------------------------------------------------
# Usa SessionFactory centralizado do SAGL
# Importado diretamente de openlegis.sagl.db_session acima


# ---------------------------------------------------------------------
# Utilitários de Validação
# ---------------------------------------------------------------------
class ValidationError(Exception):
    """Exceção para erros de validação"""
    pass

# Importa exceções de utils
from .utils import SecurityValidationError, FileValidationError


def validar_tipo_tramitacao(tipo: str) -> str:
    """
    Valida e retorna o tipo de tramitação.
    
    Args:
        tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
        
    Returns:
        Tipo validado
        
    Raises:
        ValidationError: Se o tipo for inválido
    """
    tipo = tipo.upper() if tipo else 'MATERIA'
    if tipo not in ['MATERIA', 'DOCUMENTO']:
        raise ValidationError(f'Tipo de tramitação inválido: {tipo}')
    return tipo


def validar_codigo_entidade(cod_entidade: Any, nome_campo: str = 'cod_entidade') -> int:
    """
    Valida e converte código de entidade para inteiro.
    
    Args:
        cod_entidade: Código da entidade (pode ser string ou int)
        nome_campo: Nome do campo para mensagem de erro
        
    Returns:
        Código da entidade como inteiro
        
    Raises:
        ValidationError: Se o código for inválido
    """
    if not cod_entidade:
        raise ValidationError(f'{nome_campo} não fornecido')
    
    try:
        cod = int(cod_entidade)
        if cod <= 0:
            raise ValidationError(f'{nome_campo} deve ser um número positivo')
        return cod
    except (ValueError, TypeError):
        raise ValidationError(f'{nome_campo} inválido: {cod_entidade}')


def validar_codigo_usuario(cod_usuario: Optional[int], obrigatorio: bool = True) -> Optional[int]:
    """
    Valida código de usuário.
    
    Args:
        cod_usuario: Código do usuário
        obrigatorio: Se True, código é obrigatório
        
    Returns:
        Código do usuário validado
        
    Raises:
        ValidationError: Se o código for inválido e obrigatório
    """
    if obrigatorio and not cod_usuario:
        raise ValidationError('Usuário não autenticado')
    
    if cod_usuario is not None and cod_usuario <= 0:
        raise ValidationError(f'Código de usuário inválido: {cod_usuario}')
    
    return cod_usuario


def _get_nome_unidade_tramitacao(unidade):
    """Obtém o nome da unidade de tramitação (mesma função de views.py)"""
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
    
    return ''


def _renderizar_campo_readonly(id_campo, label_texto, valor, campo_id_display=None, aria_describedby=None):
    """
    Renderiza campo readonly padronizado com acessibilidade
    
    Args:
        id_campo: ID do campo hidden
        label_texto: Texto do label
        valor: Valor a ser exibido
        campo_id_display: ID do campo de display (padrão: id_campo + '_display')
        aria_describedby: ID do elemento que descreve o campo
    """
    if not campo_id_display:
        campo_id_display = f'{id_campo}_display'
    
    aria_attrs = f'aria-label="{label_texto} (somente leitura)" aria-readonly="true" tabindex="-1"'
    if aria_describedby:
        aria_attrs += f' aria-describedby="{aria_describedby}"'
    
    html = f'<input type="hidden" name="{id_campo}" id="{id_campo}" value="{valor}" />'
    html += f'<input class="form-control form-control-sm bg-light" type="text" id="{campo_id_display}" value="{valor}" readonly {aria_attrs} />'
    return html


def _renderizar_label_campo(for_id, texto, obrigatorio=False, descricao=None):
    """
    Renderiza label padronizado com acessibilidade
    
    Args:
        for_id: ID do campo associado
        texto: Texto do label
        obrigatorio: Se o campo é obrigatório
        descricao: Texto descritivo adicional
    """
    classes = 'form-label'
    # Em mobile, não usar small para melhor legibilidade
    # classes += ' small'  # Removido para melhor legibilidade
    
    if obrigatorio:
        classes += ' required'
    
    html = f'<label class="{classes}" for="{for_id}">'
    html += texto
    if obrigatorio:
        html += ' <span class="text-danger" aria-label="obrigatório">*</span>'
        html += ' <span class="visually-hidden">(obrigatório)</span>'
    html += '</label>'
    
    if descricao:
        html += f'<small class="form-text text-muted d-block" id="{for_id}_help">{descricao}</small>'
    
    return html


def _renderizar_icone_decorativo(classe_icone, aria_label=None):
    """
    Renderiza ícone decorativo com acessibilidade
    
    Args:
        classe_icone: Classe do ícone (ex: 'mdi mdi-calendar')
        aria_label: Label ARIA (se None, usa aria-hidden)
    """
    if aria_label:
        return f'<i class="{classe_icone}" aria-label="{aria_label}"></i>'
    else:
        return f'<i class="{classe_icone}" aria-hidden="true"></i>'


def _renderizar_secao_card(titulo, icone_classe, conteudo, id_secao=None):
    """
    Renderiza seção padronizada em card
    
    Args:
        titulo: Título da seção
        icone_classe: Classe do ícone
        conteudo: HTML do conteúdo
        id_secao: ID da seção (opcional)
    """
    id_attr = f' id="{id_secao}"' if id_secao else ''
    html = f'<div class="card mb-3"{id_attr}>'
    html += '<div class="card-header bg-light py-2">'
    html += f'<h6 class="mb-0"><i class="{icone_classe} me-1" aria-hidden="true"></i>{titulo}</h6>'
    html += '</div>'
    html += '<div class="card-body p-3">'
    html += conteudo
    html += '</div></div>'
    return html


# ---------------------------------------------------------------------
# Base com utilitários compartilhados (similar a ProposicoesAPIBase)
# ---------------------------------------------------------------------
class TramitacaoAPIBase:
    """
    Classe base com métodos utilitários compartilhados para views de tramitação.
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
    
    def _resposta_json(self, dados: Dict[str, Any], status_code: int = 200) -> str:
        """
        Retorna resposta JSON padronizada.
        
        Args:
            dados: Dicionário com dados da resposta
            status_code: Código HTTP (não usado diretamente, mas pode ser útil)
            
        Returns:
            String JSON
        """
        self._configurar_headers_json()
        
        # Função auxiliar para converter objetos datetime para string
        def converter_datetime(obj):
            """Converte objetos datetime para string ISO format"""
            from datetime import datetime, date
            # Verifica se é datetime/date do Python
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            # Verifica se é DateTime do Zope (tem método strftime)
            elif hasattr(obj, 'strftime') and hasattr(obj, 'year'):
                try:
                    # Tenta converter para datetime do Python primeiro
                    if hasattr(obj, 'asdatetime'):
                        dt = obj.asdatetime()
                        return dt.isoformat()
                    # Fallback: usa strftime
                    return obj.strftime('%Y-%m-%dT%H:%M:%S')
                except Exception:
                    # Último recurso: converte para string
                    return str(obj)
            elif isinstance(obj, dict):
                return {k: converter_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [converter_datetime(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(converter_datetime(item) for item in obj)
            return obj
        
        # Converte dados antes de serializar
        dados_convertidos = converter_datetime(dados)
        return json.dumps(dados_convertidos, ensure_ascii=False)
    
    def _resposta_erro(self, mensagem: str, codigo: Optional[str] = None) -> str:
        """
        Retorna resposta de erro padronizada.
        
        Args:
            mensagem: Mensagem de erro
            codigo: Código de erro opcional
            
        Returns:
            String JSON com erro
        """
        erro = {'erro': mensagem}
        if codigo:
            erro['codigo'] = codigo
        return self._resposta_json(erro)
    
    def _resposta_sucesso(self, mensagem: str, dados: Optional[Dict[str, Any]] = None) -> str:
        """
        Retorna resposta de sucesso padronizada.
        
        Args:
            mensagem: Mensagem de sucesso
            dados: Dados adicionais opcionais
            
        Returns:
            String JSON com sucesso
        """
        resposta = {'sucesso': True, 'mensagem': mensagem}
        if dados:
            resposta.update(dados)
        return self._resposta_json(resposta)
    
    @cached('usuario_cod', ttl=600)  # Cache por 10 minutos
    def _get_cod_usuario(self, session: Optional[Any] = None) -> Optional[int]:
        """
        Obtém código do usuário logado.
        Usa AUTHENTICATED_USER.getUserName() seguindo padrão do sistema.
        Resultado é cacheado para melhor performance.
        
        Args:
            session: Sessão opcional para reutilizar. Se não fornecida, cria nova sessão de leitura.
                    Use esta opção quando já tiver uma sessão ativa para evitar padrão misto.
        
        Returns:
            Código do usuário ou None se não encontrado
        """
        try:
            col_username = self.request.AUTHENTICATED_USER.getUserName()
            if not col_username:
                logger.warning("[tramitacao] _get_cod_usuario - Nenhum usuário autenticado")
                return None
            
            # Valida username com segurança
            col_username = validar_string_segura(col_username, 'username', max_length=100, permitir_vazio=False)
            
            # Se sessão foi fornecida, usa ela (evita criar múltiplas sessões na mesma transação)
            if session is not None:
                usuario = (
                    session.query(Usuario)
                    .filter(
                        Usuario.col_username == col_username,
                        Usuario.ind_excluido == 0,
                        Usuario.ind_ativo == 1,
                    )
                    .first()
                )
                
                if usuario:
                    cod_usuario = usuario.cod_usuario
                    return cod_usuario
                else:
                    logger.warning(
                        f"[tramitacao] _get_cod_usuario - Usuário '{col_username}' "
                        f"não encontrado no banco ou está inativo/excluído"
                    )
                    return None
            else:
                # Cria nova sessão de leitura apenas se não foi fornecida
                with db_session_readonly() as session_readonly:
                    usuario = (
                        session_readonly.query(Usuario)
                        .filter(
                            Usuario.col_username == col_username,
                            Usuario.ind_excluido == 0,
                            Usuario.ind_ativo == 1,
                        )
                        .first()
                    )
                    
                    if usuario:
                        # Extrai código antes de expungar
                        cod_usuario = usuario.cod_usuario
                        session_readonly.expunge_all()  # Remove objetos da sessão
                        return cod_usuario
                    else:
                        logger.warning(
                            f"[tramitacao] _get_cod_usuario - Usuário '{col_username}' "
                            f"não encontrado no banco ou está inativo/excluído"
                        )
                        return None
        except SecurityValidationError as e:
            logger.error(f"[tramitacao] Erro de validação ao obter cod_usuario: {e}")
            return None
        except Exception as e:
            logger.error(f"[tramitacao] Erro ao obter cod_usuario: {e}", exc_info=True)
            return None
    
    def _obter_parametro(self, nome: str, padrao: Any = None, obrigatorio: bool = False, 
                        validar_seguro: bool = False, max_length: int = 1000) -> Any:
        """
        Obtém parâmetro do request com validação.
        
        Args:
            nome: Nome do parâmetro
            padrao: Valor padrão se não encontrado
            obrigatorio: Se True, levanta ValidationError se não encontrado
            validar_seguro: Se True, aplica validações de segurança
            max_length: Tamanho máximo se validar_seguro=True
            
        Returns:
            Valor do parâmetro
            
        Raises:
            ValidationError: Se obrigatório e não encontrado
            SecurityValidationError: Se validação de segurança falhar
        """
        valor = self.request.form.get(nome, padrao)
        if obrigatorio and valor is None:
            raise ValidationError(f'Parâmetro obrigatório não fornecido: {nome}')
        
        if validar_seguro and valor is not None:
            valor = validar_string_segura(valor, nome, max_length=max_length, permitir_vazio=not obrigatorio)
        
        return valor
    
    def _obter_tipo_tramitacao(self) -> str:
        """
        Obtém e valida tipo de tramitação do request.
        Tenta primeiro 'hdn_tipo_tramitacao', depois 'tipo'.
        
        Returns:
            Tipo de tramitação validado ('MATERIA' ou 'DOCUMENTO')
            
        Raises:
            ValidationError: Se tipo inválido
        """
        # Tenta obter do parâmetro hdn_tipo_tramitacao primeiro (formulário)
        tipo = self._obter_parametro('hdn_tipo_tramitacao')
        # Se não encontrou, tenta o parâmetro 'tipo' (usado em requisições AJAX)
        if not tipo:
            tipo = self._obter_parametro('tipo')
        # Se ainda não encontrou, usa padrão 'MATERIA'
        if not tipo:
            tipo = 'MATERIA'
        return validar_tipo_tramitacao(tipo)
    
    def _obter_cod_entidade(self) -> int:
        """
        Obtém e valida código da entidade (matéria ou documento) do request.
        Usa validação segura para prevenir SQL injection.
        
        Returns:
            Código da entidade validado
            
        Raises:
            ValidationError: Se código não fornecido ou inválido
            SecurityValidationError: Se validação de segurança falhar
        """
        cod_materia = self._obter_parametro('hdn_cod_materia')
        cod_documento = self._obter_parametro('hdn_cod_documento')
        cod_entidade = cod_materia or cod_documento
        
        if not cod_entidade:
            raise ValidationError('Código da entidade não fornecido')
        
        # Usa validação segura
        return validar_codigo_inteiro_seguro(cod_entidade, 'cod_entidade', min_valor=1)
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[Any]:
        """
        Converte string de data para objeto date com validação segura.
        
        Args:
            date_str: String de data no formato '%d/%m/%Y'
            
        Returns:
            Objeto date ou None se inválido
            
        Raises:
            SecurityValidationError: Se data inválida ou fora dos limites
        """
        if not date_str:
            return None
        
        try:
            return validar_data_segura(date_str, formato='%d/%m/%Y', nome_campo='data')
        except SecurityValidationError:
            raise
        except Exception as e:
            logger.warning(f"Erro ao parsear data '{date_str}': {e}")
            return None
    
    def _detectar_alteracoes_tramitacao(self, dados_novos: Dict[str, Any], dados_atuais: Dict[str, Any], tipo: str) -> bool:
        """
        Detecta se houve alterações nos campos da tramitação.
        
        Args:
            dados_novos: Dicionário com os novos dados da tramitação
            dados_atuais: Dicionário com os dados atuais da tramitação
            tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
            
        Returns:
            True se houve alteração, False caso contrário
        """
        try:
            # Normaliza valores para comparação
            def normalizar_valor(valor):
                if valor is None:
                    return None
                if isinstance(valor, str):
                    return valor.strip()
                return valor
            
            # Compara campos principais
            campos_para_comparar = [
                'cod_unid_tram_local',
                'cod_unid_tram_dest',
                'cod_usuario_dest',
                'cod_status',
                'txt_tramitacao',
                'dat_fim_prazo',
                'dat_tramitacao'  # ✅ Adiciona dat_tramitacao para comparar data (sem horário)
            ]
            
            # Adiciona ind_urgencia apenas para MATERIA
            if tipo == 'MATERIA':
                campos_para_comparar.append('ind_urgencia')
            
            alteracoes_detectadas = []
            for campo in campos_para_comparar:
                valor_novo = normalizar_valor(dados_novos.get(campo))
                valor_atual = normalizar_valor(dados_atuais.get(campo))
                
                # ✅ Comparação especial para dat_tramitacao: compara apenas a data (sem horário)
                if campo == 'dat_tramitacao':
                    from datetime import datetime
                    try:
                        # Normaliza para string no formato DD/MM/YYYY para comparação
                        if valor_novo:
                            if isinstance(valor_novo, datetime):
                                valor_novo_str = valor_novo.strftime('%d/%m/%Y')
                            elif hasattr(valor_novo, 'strftime'):
                                valor_novo_str = valor_novo.strftime('%d/%m/%Y')
                            else:
                                valor_novo_str = str(valor_novo)[:10]  # Pega apenas data (YYYY-MM-DD)
                                # Converte para DD/MM/YYYY se necessário
                                if '-' in valor_novo_str:
                                    parts = valor_novo_str.split('-')
                                    if len(parts) == 3:
                                        valor_novo_str = f"{parts[2]}/{parts[1]}/{parts[0]}"
                            valor_novo = valor_novo_str
                        else:
                            valor_novo = None
                        
                        if valor_atual:
                            if isinstance(valor_atual, datetime):
                                valor_atual_str = valor_atual.strftime('%d/%m/%Y')
                            elif hasattr(valor_atual, 'strftime'):
                                valor_atual_str = valor_atual.strftime('%d/%m/%Y')
                            else:
                                valor_atual_str = str(valor_atual)[:10]
                                if '-' in valor_atual_str:
                                    parts = valor_atual_str.split('-')
                                    if len(parts) == 3:
                                        valor_atual_str = f"{parts[2]}/{parts[1]}/{parts[0]}"
                            valor_atual = valor_atual_str
                        else:
                            valor_atual = None
                    except Exception as e:
                        logger.debug(f"Erro ao normalizar dat_tramitacao para comparação: {e}")
                
                # Converte para int se necessário para comparação
                if campo in ['cod_unid_tram_local', 'cod_unid_tram_dest', 'cod_usuario_dest', 'cod_status', 'ind_urgencia']:
                    try:
                        valor_novo = int(valor_novo) if valor_novo is not None else None
                        valor_atual = int(valor_atual) if valor_atual is not None else None
                    except (ValueError, TypeError):
                        pass
                
                if valor_novo != valor_atual:
                    alteracoes_detectadas.append(f"{campo}: {valor_atual} -> {valor_novo}")
                    logger.debug(f"TramitacaoIndividualSalvarView - Alteração detectada: {campo} = {valor_atual} -> {valor_novo}")
            
            if alteracoes_detectadas:
                logger.debug(f"TramitacaoIndividualSalvarView - Alterações detectadas: {', '.join(alteracoes_detectadas)}")
                return True
            
            logger.debug(f"TramitacaoIndividualSalvarView - Nenhuma alteração detectada nos campos")
            return False
        except Exception as e:
            logger.warning(f"Erro ao detectar alterações na tramitação: {e}", exc_info=True)
            # Em caso de erro, assume que houve alteração para garantir geração de PDF
            return True
    
    def _obter_dados_tramitacao_form_em_sessao(self, session: Any, tipo: str, cod_tramitacao: str) -> Optional[Dict[str, Any]]:
        """Obtém dados da tramitação usando sessão existente"""
        try:
            cod_tramitacao_int = validar_codigo_entidade(cod_tramitacao, 'cod_tramitacao')
            from openlegis.sagl.models.models import Tramitacao, TramitacaoAdministrativo
            from datetime import datetime
            
            if tipo == 'MATERIA':
                tram = session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao_int,
                    Tramitacao.ind_excluido == 0
                ).first()
            else:
                tram = session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao_int,
                    TramitacaoAdministrativo.ind_excluido == 0
                ).first()
            
            if not tram:
                return None
            
            # Extrai todos os dados ANTES de formatar
            cod_tram = tram.cod_tramitacao
            cod_unid_local = tram.cod_unid_tram_local
            cod_user_local = tram.cod_usuario_local
            cod_unid_dest = tram.cod_unid_tram_dest
            cod_user_dest = tram.cod_usuario_dest
            cod_stat = tram.cod_status
            ind_urg = tram.ind_urgencia if hasattr(tram, 'ind_urgencia') else 0
            txt_tram = tram.txt_tramitacao or ''
            ind_ult = tram.ind_ult_tramitacao
            dat_enc = tram.dat_encaminha
            dat_fim = tram.dat_fim_prazo
            dat_tram = tram.dat_tramitacao  # ✅ Adiciona dat_tramitacao
            
            # Formata datas
            dat_fim_prazo_str = None
            if dat_fim:
                if isinstance(dat_fim, datetime):
                    dat_fim_prazo_str = dat_fim.strftime('%d/%m/%Y')
                elif hasattr(dat_fim, 'strftime'):
                    dat_fim_prazo_str = dat_fim.strftime('%d/%m/%Y')
                else:
                    dat_fim_prazo_str = str(dat_fim)
            
            # ✅ CORRIGIDO: Formata dat_tramitacao com hora (DD/MM/YYYY HH:MM) para consistência com formulário
            dat_tramitacao_str = None
            if dat_tram:
                if isinstance(dat_tram, datetime):
                    dat_tramitacao_str = dat_tram.strftime('%d/%m/%Y %H:%M')
                elif hasattr(dat_tram, 'strftime'):
                    dat_tramitacao_str = dat_tram.strftime('%d/%m/%Y %H:%M')
                else:
                    # Tenta extrair data e hora da string
                    dat_tram_str = str(dat_tram)
                    if 'T' in dat_tram_str:
                        # Formato ISO: 2026-01-22T17:50:00
                        parts = dat_tram_str.split('T')
                        if len(parts) == 2:
                            data_part = parts[0]
                            hora_part = parts[1].split('.')[0].split('+')[0].split('-')[0]  # Remove timezone e microsegundos
                            if len(hora_part) >= 5:  # HH:MM
                                data_parts = data_part.split('-')
                                if len(data_parts) == 3:
                                    dat_tramitacao_str = f"{data_parts[2]}/{data_parts[1]}/{data_parts[0]} {hora_part[:5]}"
                    if not dat_tramitacao_str:
                        # Fallback: apenas data
                        dat_tramitacao_str = str(dat_tram)[:10]  # Pega apenas data
                        if '-' in dat_tramitacao_str:
                            parts = dat_tramitacao_str.split('-')
                            if len(parts) == 3:
                                dat_tramitacao_str = f"{parts[2]}/{parts[1]}/{parts[0]}"
            
            return {
                'cod_tramitacao': cod_tram,
                'cod_unid_tram_local': cod_unid_local,
                'cod_usuario_local': cod_user_local,
                'cod_unid_tram_dest': cod_unid_dest,
                'cod_usuario_dest': cod_user_dest,
                'cod_status': cod_stat,
                'ind_urgencia': ind_urg,
                'txt_tramitacao': txt_tram,
                'dat_fim_prazo': dat_fim_prazo_str,
                'dat_tramitacao': dat_tramitacao_str,  # ✅ Adiciona dat_tramitacao
                'ind_ult_tramitacao': ind_ult,
                'dat_encaminha': dat_enc is not None
            }
        except Exception as e:
            logger.error(f"Erro ao obter dados da tramitação: {e}", exc_info=True)
            return None
    
    def _tratar_erro(self, erro: Exception, contexto: str = "") -> str:
        """
        Trata erro de forma padronizada.
        
        Args:
            erro: Exceção capturada
            contexto: Contexto adicional para log
            
        Returns:
            Resposta JSON de erro
        """
        if isinstance(erro, (ValidationError, SecurityValidationError, FileValidationError)):
            logger.warning(f"{contexto} - Erro de validação: {erro}")
            return self._resposta_erro(str(erro))
        elif isinstance(erro, ValueError):
            logger.warning(f"{contexto} - Erro de valor: {erro}")
            return self._resposta_erro(str(erro))
        else:
            logger.error(f"{contexto} - Erro inesperado: {erro}", exc_info=True)
            return self._resposta_erro(f'Erro ao processar requisição: {str(erro)}')
    
    def _validar_arquivo_upload(self, arquivo: Any, nome_campo: str = 'arquivo', 
                               extensoes_permitidas: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Valida arquivo de upload com verificações de segurança.
        
        Args:
            arquivo: Objeto de arquivo a validar
            nome_campo: Nome do campo para mensagens de erro
            extensoes_permitidas: Lista de extensões permitidas (padrão: ['pdf'])
            
        Returns:
            Dicionário com informações do arquivo validado
            
        Raises:
            FileValidationError: Se validação falhar
        """
        extensoes_permitidas = extensoes_permitidas or ['pdf']
        return validar_arquivo_seguro(arquivo, extensoes_permitidas=extensoes_permitidas, 
                                     nome_campo=nome_campo)


class TramitacaoUnidadesView(GrokView, TramitacaoAPIBase):
    """View para carregar unidades de destino permitidas (mesma lógica do unidades_carregar_pysc)"""
    
    context(Interface)
    name('tramitacao_unidades_json')
    require('zope2.View')
    
    
    def render(self):
        """Retorna unidades de destino permitidas em JSON"""
        try:
            svalue = self._obter_parametro('svalue', '')
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            
            if not svalue:
                return self._resposta_json([{'name': '', 'id': ''}])
            
            with db_session_readonly() as session:
                # Busca a unidade de origem para obter unid_dest_permitidas
                unidade_origem = session.query(UnidadeTramitacao).options(
                    selectinload(UnidadeTramitacao.comissao),
                    selectinload(UnidadeTramitacao.orgao),
                    selectinload(UnidadeTramitacao.parlamentar)
                ).filter(
                    UnidadeTramitacao.cod_unid_tramitacao == int(svalue),
                    UnidadeTramitacao.ind_excluido == 0
                ).first()
                
                if not unidade_origem:
                    logger.warning(f"Unidade de origem não encontrada: {svalue}")
                    return self._resposta_json([{'name': 'Unidade não encontrada', 'id': ''}])
                
                unidadeArray = []
                
                # Verifica se há unidades de destino permitidas configuradas
                if unidade_origem.unid_dest_permitidas:
                    unidadeArray.append({'name': 'Selecione', 'id': ''})
                    
                    # Separa a lista de IDs (separados por vírgula)
                    unid_dest_ids = [id.strip() for id in str(unidade_origem.unid_dest_permitidas).split(',') if id.strip()]
                    
                    # Se lista estiver vazia após processamento, retornar mensagem
                    if not unid_dest_ids:
                        return self._resposta_json([{'name': 'Nenhuma unidade de destino permitida', 'id': ''}])
                    
                    # Busca cada unidade de destino
                    unidades_filtradas = 0
                    unidades_adicionadas = 0
                    for unid_id in unid_dest_ids:
                        try:
                            unid_dest = session.query(UnidadeTramitacao).options(
                                selectinload(UnidadeTramitacao.comissao),
                                selectinload(UnidadeTramitacao.orgao),
                                selectinload(UnidadeTramitacao.parlamentar)
                            ).filter(
                                UnidadeTramitacao.cod_unid_tramitacao == int(unid_id),
                                UnidadeTramitacao.ind_excluido == 0
                            ).first()
                            
                            if unid_dest:
                                nome_unidade = _get_nome_unidade_tramitacao(unid_dest)
                                
                                # Filtra por tipo: ind_leg=1 para matérias, ind_adm=1 para documentos
                                if tipo == 'MATERIA':
                                    if unid_dest.ind_leg == 1:
                                        unidadeArray.append({
                                            'name': nome_unidade,
                                            'id': unid_dest.cod_unid_tramitacao
                                        })
                                        unidades_adicionadas += 1
                                    else:
                                        unidades_filtradas += 1
                                elif tipo == 'DOCUMENTO':
                                    if unid_dest.ind_adm == 1:
                                        unidadeArray.append({
                                            'name': nome_unidade,
                                            'id': unid_dest.cod_unid_tramitacao
                                        })
                                        unidades_adicionadas += 1
                                    else:
                                        unidades_filtradas += 1
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Erro ao processar unidade destino ID {unid_id}: {e}")
                            continue
                    
                    if unidades_filtradas > 0:
                        logger.info(
                            f"Unidades processadas: {unidades_adicionadas} adicionadas, "
                            f"{unidades_filtradas} filtradas por tipo (tipo: {tipo})"
                        )
                else:
                    # Se não há permissões configuradas, NÃO retorna nenhuma unidade
                    # Isso impede a tramitação até que permissões sejam configuradas
                    return self._resposta_json([{
                        'name': 'Nenhuma unidade de destino permitida. Configure permissões na unidade de origem.',
                        'id': ''
                    }])
                
                # Ordena por nome, mas mantém "Selecione" sempre no início
                selecione_item = None
                outras_unidades = []
                for item in unidadeArray:
                    if item['id'] == '' and item['name'] == 'Selecione':
                        selecione_item = item
                    else:
                        outras_unidades.append(item)
                
                # Ordena apenas as outras unidades
                outras_unidades.sort(key=lambda x: x['name'])
                
                # Reconstrói array com "Selecione" no início
                unidadeArray_final = []
                if selecione_item:
                    unidadeArray_final.append(selecione_item)
                unidadeArray_final.extend(outras_unidades)
                
                # Extrai dados antes de retornar
                resultado = unidadeArray_final
                session.expunge_all()  # Remove objetos da sessão
                return self._resposta_json(resultado)
        
        except Exception as e:
            logger.error(f"Erro ao obter unidades: {e}", exc_info=True)
            return self._resposta_json([{'name': 'Erro ao carregar', 'id': ''}])


class TramitacaoStatusView(GrokView, TramitacaoAPIBase):
    """View para carregar status permitidos (mesma lógica do status_carregar_pysc)"""
    
    context(Interface)
    name('tramitacao_status_json')
    require('zope2.View')
    
    def render(self):
        """Retorna status permitidos em JSON"""
        try:
            svalue = self._obter_parametro('svalue', '')
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            
            if not svalue:
                return self._resposta_json([{'name': '', 'id': ''}])
            
            with db_session_readonly() as session:
                # Busca a unidade para obter status permitidos
                unidade = session.query(UnidadeTramitacao).filter(
                    UnidadeTramitacao.cod_unid_tramitacao == int(svalue),
                    UnidadeTramitacao.ind_excluido == 0
                ).first()
                
                if not unidade:
                    logger.warning(f"Unidade não encontrada para carregar status: {svalue}")
                    return self._resposta_json([{'name': 'Unidade não encontrada', 'id': ''}])
                
                statusArray = []
                
                # Verifica se há status permitidos configurados na unidade de origem
                if tipo == 'MATERIA':
                    # Verifica campo status_permitidos (para matérias)
                    if unidade.status_permitidos:
                        # Se houver permissões configuradas, carrega apenas os permitidos
                        status_ids = [id.strip() for id in str(unidade.status_permitidos).split(',') if id.strip()]
                        if not status_ids:
                            # Lista vazia - não há permissões válidas
                            return self._resposta_json([{'name': 'Nenhum status permitido', 'id': ''}])
                        
                        status_list = session.query(StatusTramitacao).filter(
                            StatusTramitacao.cod_status.in_([int(sid) for sid in status_ids]),
                            StatusTramitacao.ind_excluido == 0
                        ).order_by(StatusTramitacao.des_status).all()
                    else:
                        # Se não há permissões configuradas, NÃO carrega nenhum status
                        # Isso impede a tramitação até que permissões sejam configuradas
                        return self._resposta_json([{
                            'name': 'Nenhum status permitido. Configure permissões na unidade de origem.',
                            'id': ''
                        }])
                    
                    statusArray.append({'name': 'Selecione', 'id': ''})
                    for status in status_list:
                        statusArray.append({
                            'name': status.des_status or '',
                            'id': status.cod_status
                        })
                else:  # DOCUMENTO
                    # Verifica campo status_adm_permitidos (para documentos)
                    if unidade.status_adm_permitidos:
                        # Se houver permissões configuradas, carrega apenas os permitidos
                        status_ids = [id.strip() for id in str(unidade.status_adm_permitidos).split(',') if id.strip()]
                        if not status_ids:
                            # Lista vazia - não há permissões válidas
                            return self._resposta_json([{'name': 'Nenhum status permitido', 'id': ''}])
                        
                        status_list = session.query(StatusTramitacaoAdministrativo).filter(
                            StatusTramitacaoAdministrativo.cod_status.in_([int(sid) for sid in status_ids]),
                            StatusTramitacaoAdministrativo.ind_excluido == 0
                        ).order_by(StatusTramitacaoAdministrativo.des_status).all()
                    else:
                        # Se não há permissões configuradas, NÃO carrega nenhum status
                        # Isso impede a tramitação até que permissões sejam configuradas
                        return self._resposta_json([{
                            'name': 'Nenhum status permitido. Configure permissões na unidade de origem.',
                            'id': ''
                        }])
                    
                    statusArray.append({'name': 'Selecione', 'id': ''})
                    for status in status_list:
                        statusArray.append({
                            'name': status.des_status or '',
                            'id': status.cod_status
                        })
                
                return self._resposta_json(statusArray)
        
        except Exception as e:
            logger.error(f"Erro ao obter status: {e}", exc_info=True)
            return self._resposta_json([{'name': 'Erro ao carregar', 'id': ''}])


class TramitacaoUsuariosView(GrokView, TramitacaoAPIBase):
    """View para carregar usuários da unidade (mesma lógica do usuarios_carregar_pysc)"""
    
    context(Interface)
    name('tramitacao_usuarios_json')
    require('zope2.View')
    
    def render(self):
        """Retorna usuários da unidade em JSON"""
        try:
            svalue = self._obter_parametro('svalue', '')  # cod_unidade de destino
            
            if not svalue:
                # Sem unidade selecionada: retorna lista vazia (placeholder fica no frontend)
                return self._resposta_json([])
            
            with db_session_readonly() as session:
                # Query para usuários da unidade
                usuarios_unid = session.query(UsuarioUnidTram).filter(
                    UsuarioUnidTram.cod_unid_tramitacao == int(svalue),
                    UsuarioUnidTram.ind_excluido == 0
                ).all()
                
                # Lista apenas com usuários (sem opção "Selecione" do backend)
                usuarioArray = []
                
                for usuario_unid in usuarios_unid:
                    usuario = session.query(Usuario).filter(
                        Usuario.cod_usuario == usuario_unid.cod_usuario,
                        Usuario.ind_excluido == 0
                    ).first()
                    
                    if usuario:
                        # Formata nome com cargo se houver
                        nome_completo = usuario.nom_completo or ''
                        if usuario.nom_cargo:
                            nome_completo += f' ({usuario.nom_cargo})'
                        
                        usuarioArray.append({
                            'name': nome_completo,
                            'id': usuario.cod_usuario
                        })
                
                # Ordena por nome
                resultado = sorted(usuarioArray, key=lambda x: x['name'])
                session.expunge_all()  # Remove objetos da sessão
                return self._resposta_json(resultado)
        
        except Exception as e:
            logger.error(f"Erro ao obter usuários: {e}", exc_info=True)
            return self._resposta_json([])


class TramitacaoUnidadesUsuarioView(GrokView, TramitacaoAPIBase):
    """View para carregar unidades do usuário"""
    
    context(Interface)
    name('tramitacao_unidades_usuario_json')
    require('zope2.View')
    
    def render(self):
        """Retorna unidades do usuário em JSON"""
        try:
            cod_usuario = self._get_cod_usuario()
            
            if not cod_usuario:
                logger.warning("cod_usuario não fornecido e não foi possível obter do usuário autenticado")
                return self._resposta_json([])
            
            with db_session_readonly() as session:
                # Busca unidades do usuário
                unidades_usuario = session.query(UsuarioUnidTram).filter(
                    UsuarioUnidTram.cod_usuario == int(cod_usuario),
                    UsuarioUnidTram.ind_excluido == 0
                ).all()
                
                unidadesArray = []
                
                for usuario_unid in unidades_usuario:
                    # Busca a unidade de tramitação
                    unidade = session.query(UnidadeTramitacao).options(
                        selectinload(UnidadeTramitacao.comissao),
                        selectinload(UnidadeTramitacao.orgao),
                        selectinload(UnidadeTramitacao.parlamentar)
                    ).filter(
                        UnidadeTramitacao.cod_unid_tramitacao == usuario_unid.cod_unid_tramitacao,
                        UnidadeTramitacao.ind_excluido == 0
                    ).first()
                    
                    if unidade:
                        nome_unidade = _get_nome_unidade_tramitacao(unidade)
                        if nome_unidade:
                            unidadesArray.append({
                                'id': unidade.cod_unid_tramitacao,
                                'name': nome_unidade,
                                'nom_unidade': nome_unidade
                            })
                
                # Ordena por nome
                unidadesArray.sort(key=lambda x: x['name'])
                
                # Extrai dados antes de retornar
                resultado = unidadesArray
                session.expunge_all()  # Remove objetos da sessão
                return self._resposta_json(resultado)
        
        except Exception as e:
            logger.error(f"Erro ao obter unidades do usuário: {e}", exc_info=True)
            return self._resposta_json([])


class TramitacaoIndividualObterView(GrokView, TramitacaoAPIBase):
    """View para obter dados de uma tramitação individual"""
    
    context(Interface)
    name('tramitacao_individual_obter_json')
    require('zope2.View')
    
    def render(self):
        """Retorna dados da tramitação em JSON"""
        try:
            cod_tramitacao = self._obter_parametro('cod_tramitacao', obrigatorio=True)
            tipo = self._obter_tipo_tramitacao()
            
            cod_tramitacao_int = validar_codigo_entidade(cod_tramitacao, 'cod_tramitacao')
            
            with db_session_readonly() as session:
                from openlegis.sagl.models.models import Tramitacao, TramitacaoAdministrativo
                from datetime import datetime
                
                if tipo == 'MATERIA':
                    tram = session.query(Tramitacao).filter(
                        Tramitacao.cod_tramitacao == cod_tramitacao_int,
                        Tramitacao.ind_excluido == 0
                    ).first()
                else:
                    tram = session.query(TramitacaoAdministrativo).filter(
                        TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao_int,
                        TramitacaoAdministrativo.ind_excluido == 0
                    ).first()
                
                if not tram:
                    return self._resposta_erro('Tramitação não encontrada')
                
                # Extrai todos os dados ANTES de expungar para evitar lazy-loading
                cod_tram = tram.cod_tramitacao
                cod_unid_local = tram.cod_unid_tram_local
                cod_user_local = tram.cod_usuario_local
                cod_unid_dest = tram.cod_unid_tram_dest
                cod_user_dest = tram.cod_usuario_dest
                cod_stat = tram.cod_status
                ind_urg = tram.ind_urgencia if hasattr(tram, 'ind_urgencia') else 0
                txt_tram = tram.txt_tramitacao or ''
                ind_ult = tram.ind_ult_tramitacao
                dat_vis = tram.dat_visualizacao
                dat_rec = tram.dat_recebimento
                dat_enc = tram.dat_encaminha
                dat_fim = tram.dat_fim_prazo
                dat_tram = tram.dat_tramitacao  # ✅ Adiciona dat_tramitacao para consistência com cards
                
                # Extrai cod_entidade baseado no tipo
                if tipo == 'MATERIA':
                    cod_ent = tram.cod_materia
                else:
                    cod_ent = tram.cod_documento
                
                # Expunge objetos da sessão antes de formatar
                session.expunge_all()
                
                # ✅ CORRIGIDO: Formata datas em ISO 8601 para consistência com cards
                # O frontend já trata ISO 8601 corretamente, então mantemos formato consistente
                from openlegis.sagl.browser.tramitacao.views import _formatar_datetime_iso
                
                dat_encaminha_str = _formatar_datetime_iso(dat_enc)
                dat_tramitacao_str = _formatar_datetime_iso(dat_tram)
                
                dat_fim_prazo_str = None
                if dat_fim:
                    if isinstance(dat_fim, datetime):
                        dat_fim_prazo_str = dat_fim.strftime('%d/%m/%Y')
                    elif hasattr(dat_fim, 'strftime'):
                        dat_fim_prazo_str = dat_fim.strftime('%d/%m/%Y')
                    else:
                        dat_fim_prazo_str = str(dat_fim)
                
                dados = {
                    'cod_tramitacao': cod_tram,
                    'cod_unid_tram_local': cod_unid_local,
                    'cod_usuario_local': cod_user_local,
                    'cod_unid_tram_dest': cod_unid_dest,
                    'cod_usuario_dest': cod_user_dest,
                    'cod_status': cod_stat,
                    'ind_urgencia': ind_urg,
                    'txt_tramitacao': txt_tram,
                    'dat_tramitacao': dat_tramitacao_str,  # ✅ Adiciona dat_tramitacao formatado com hora
                    'dat_encaminha': dat_encaminha_str,
                    'dat_fim_prazo': dat_fim_prazo_str,
                    'ind_ult_tramitacao': ind_ult,
                    'dat_visualizacao': dat_vis.strftime('%d/%m/%Y %H:%M') if dat_vis else None,
                    'dat_recebimento': dat_rec.strftime('%d/%m/%Y %H:%M') if dat_rec else None
                }
                
                # Adiciona cod_entidade baseado no tipo
                if tipo == 'MATERIA':
                    dados['cod_materia'] = cod_ent
                else:
                    dados['cod_documento'] = cod_ent
                
                return self._resposta_json(dados)
        
        except Exception as e:
            return self._tratar_erro(e, "TramitacaoIndividualObterView")


class BaseTramitacaoFormView(TramitacaoAPIBase):
    """
    Classe base para formulários de tramitação.
    Extrai código comum entre TramitacaoIndividualFormView e TramitacaoLoteFormView.
    
    Esta classe não herda de GrokView para evitar que seja registrada como view.
    As classes filhas devem herdar de GrokView e desta classe base.
    """
    
    def _obter_dados_formulario_base(self, tipo: str) -> Dict[str, Any]:
        """
        Obtém dados base para formulários (usuário, unidades, etc.).
        
        Args:
            tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
            
        Returns:
            Dicionário com dados base do formulário
            
        Raises:
            ValidationError: Se usuário não autenticado
        """
        cod_usuario = self._get_cod_usuario()
        if not cod_usuario:
            logger.error(
                f"{self.__class__.__name__} - Não foi possível obter cod_usuario. "
                "Verifique se o usuário está autenticado e tem registro na tabela Usuario."
            )
            raise ValidationError(
                'Usuário não autenticado. É necessário estar autenticado para tramitar processos. '
                'Faça login e tente novamente.'
            )
        
        # Obtém unidades do usuário e nome do usuário
        unidades_usuario, nome_usuario = self._obter_dados_usuario(cod_usuario, tipo)
        
        # Obtém data atual
        from datetime import datetime
        dat_tramitacao = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        return {
            'cod_usuario': cod_usuario,
            'nome_usuario': nome_usuario,
            'unidades_usuario': unidades_usuario,
            'dat_tramitacao': dat_tramitacao,
            'tipo': tipo
        }
    
    def _processar_unidade_caixa_entrada(
        self, 
        unidades_usuario: List[Dict], 
        cod_unid_tram_local_caixa: str
    ) -> tuple:
        """
        Processa unidade da caixa de entrada.
        
        Args:
            unidades_usuario: Lista de unidades do usuário
            cod_unid_tram_local_caixa: Código da unidade da caixa de entrada
            
        Returns:
            Tupla (unidades_usuario_processadas, cod_unid_tram_local_int)
        """
        cod_unid_tram_local_int = None
        if cod_unid_tram_local_caixa:
            try:
                cod_unid_tram_local_int = validar_codigo_inteiro_seguro(
                    cod_unid_tram_local_caixa, 'cod_unid_tram_local', min_valor=1
                )
            except (SecurityValidationError, ValueError, TypeError):
                cod_unid_tram_local_int = None
        
        unidades_processadas = unidades_usuario
        if cod_unid_tram_local_int:
            unidades_processadas = self._processar_unidade_caixa(
                unidades_usuario, cod_unid_tram_local_int
            )
        
        return unidades_processadas, cod_unid_tram_local_int
    
    def _obter_dados_formulario_completo(
        self, 
        tipo: str, 
        cod_unid_tram_local_caixa: str = ''
    ) -> Dict[str, Any]:
        """
        Obtém todos os dados necessários para renderizar formulário.
        
        Args:
            tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
            cod_unid_tram_local_caixa: Código da unidade da caixa de entrada
            
        Returns:
            Dicionário com todos os dados do formulário
        """
        # Obtém dados base
        dados_base = self._obter_dados_formulario_base(tipo)
        
        # Processa unidade da caixa de entrada
        unidades_usuario, cod_unid_tram_local_int = self._processar_unidade_caixa_entrada(
            dados_base['unidades_usuario'], 
            cod_unid_tram_local_caixa
        )
        
        # Busca unidades de destino e status
        unidades_destino, status_opcoes = self._obter_unidades_destino_e_status(
            tipo, cod_unid_tram_local_int
        )
        
        
        # Atualiza dados base com informações processadas
        dados_base.update({
            'unidades_usuario': unidades_usuario,
            'cod_unid_tram_local': cod_unid_tram_local_int,
            'unidades_destino': unidades_destino,
            'status_opcoes': status_opcoes
        })
        
        return dados_base


class TramitacaoIndividualFormView(GrokView, BaseTramitacaoFormView):
    """View para retornar HTML do formulário individual"""
    
    context(Interface)
    name('tramitacao_individual_form_json')
    require('zope2.View')
    
    def render(self):
        """Retorna HTML do formulário individual com dados preenchidos se cod_tramitacao fornecido"""
        try:
            # Todas as validações primeiro (ANTES de abrir sessão)
            cod_entidade = self._obter_parametro('cod_entidade', obrigatorio=True)
            tipo = self._obter_tipo_tramitacao()
            cod_tramitacao = self._obter_parametro('cod_tramitacao', '')
            cod_unid_tram_local_caixa = self._obter_parametro('cod_unid_tram_local', '')
            
            # ABRE APENAS UMA sessão readonly para tudo
            with db_session_readonly() as session:
                # Obtém usuário (usa cache se disponível)
                cod_usuario = self._get_cod_usuario()
                if not cod_usuario:
                    return self._resposta_erro(
                        'Usuário não autenticado. É necessário estar autenticado para tramitar processos. '
                        'Faça login e tente novamente.'
                    )
                
                # Obtém dados do usuário usando sessão existente
                unidades_usuario, nome_usuario = self._obter_dados_usuario_em_sessao(session, cod_usuario, tipo)
                
                # Processa unidade da caixa de entrada
                cod_unid_tram_local_int = None
                if cod_unid_tram_local_caixa:
                    try:
                        cod_unid_tram_local_int = validar_codigo_inteiro_seguro(
                            cod_unid_tram_local_caixa, 'cod_unid_tram_local', min_valor=1
                        )
                    except (SecurityValidationError, ValueError, TypeError):
                        cod_unid_tram_local_int = None
                
                if cod_unid_tram_local_int:
                    unidades_usuario = self._processar_unidade_caixa_em_sessao(
                        session, unidades_usuario, cod_unid_tram_local_int
                    )
                
                # Obtém dados da tramitação PRIMEIRO se cod_tramitacao fornecido (usando sessão existente)
                # Isso é importante para obter cod_unid_tram_local da tramitação ao editar
                dados_tramitacao = None
                if cod_tramitacao:
                    dados_tramitacao = self._obter_dados_tramitacao_form_em_sessao(session, tipo, cod_tramitacao)
                
                # ✅ CORRIGIDO: Usa dat_tramitacao do banco se disponível, senão usa data atual
                from datetime import datetime
                if dados_tramitacao and dados_tramitacao.get('dat_tramitacao'):
                    # Se editando tramitação existente, usa dat_tramitacao do banco formatada com hora
                    # Busca a tramitação novamente para obter dat_tramitacao completo (com hora)
                    from openlegis.sagl.models.models import Tramitacao, TramitacaoAdministrativo
                    cod_tramitacao_int = validar_codigo_entidade(cod_tramitacao, 'cod_tramitacao')
                    if tipo == 'MATERIA':
                        tram = session.query(Tramitacao).filter(
                            Tramitacao.cod_tramitacao == cod_tramitacao_int,
                            Tramitacao.ind_excluido == 0
                        ).first()
                    else:
                        tram = session.query(TramitacaoAdministrativo).filter(
                            TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao_int,
                            TramitacaoAdministrativo.ind_excluido == 0
                        ).first()
                    
                    if tram and tram.dat_tramitacao:
                        if isinstance(tram.dat_tramitacao, datetime):
                            dat_tramitacao = tram.dat_tramitacao.strftime('%d/%m/%Y %H:%M')
                        elif hasattr(tram.dat_tramitacao, 'strftime'):
                            dat_tramitacao = tram.dat_tramitacao.strftime('%d/%m/%Y %H:%M')
                        else:
                            dat_tramitacao = datetime.now().strftime('%d/%m/%Y %H:%M')
                    else:
                        dat_tramitacao = datetime.now().strftime('%d/%m/%Y %H:%M')
                else:
                    # Nova tramitação, usa data atual
                    dat_tramitacao = datetime.now().strftime('%d/%m/%Y %H:%M')
                
                # Usa cod_unid_tram_local dos dados da tramitação se existir, senão usa do parâmetro
                cod_unid_tram_local_final = None
                if dados_tramitacao and dados_tramitacao.get('cod_unid_tram_local'):
                    cod_unid_tram_local_final = dados_tramitacao.get('cod_unid_tram_local')
                elif cod_unid_tram_local_int:
                    cod_unid_tram_local_final = cod_unid_tram_local_int
                
                # Obtém unidades de destino e status usando cod_unid_tram_local correto
                unidades_destino, status_opcoes = self._obter_unidades_destino_e_status_em_sessao(
                    session, tipo, cod_unid_tram_local_final
                )
                
                # Obtém informações do processo usando sessão existente
                info_processo = self._obter_info_processo_em_sessao(session, tipo, cod_entidade)
                
                # Garante que dados_tramitacao tem cod_unid_tram_local
                if cod_unid_tram_local_final:
                    if not dados_tramitacao:
                        dados_tramitacao = {}
                    dados_tramitacao['cod_unid_tram_local'] = cod_unid_tram_local_final
                
                if not dados_tramitacao:
                    dados_tramitacao = {}
                
                # Obtém link do PDF do despacho se tramitação existir
                link_pdf_despacho = None
                pdf_gerado = False
                if cod_tramitacao:
                    try:
                        cod_tramitacao_int = int(cod_tramitacao) if cod_tramitacao else None
                        if cod_tramitacao_int:
                            # Verifica se PDF existe no repositório Zope
                            site_real = self._resolver_site_real()
                            arquivo_pdf = f"{cod_tramitacao_int}_tram.pdf"
                            
                            if tipo == 'MATERIA':
                                repo = site_real.sapl_documentos.materia.tramitacao
                            else:
                                repo = site_real.sapl_documentos.administrativo.tramitacao
                            
                            # Verifica se o arquivo existe no repositório
                            if hasattr(repo, arquivo_pdf):
                                try:
                                    # Obtém URL usando absolute_url() do arquivo (padrão Zope)
                                    arq = getattr(repo, arquivo_pdf)
                                    base_url = str(arq.absolute_url())
                                    
                                    # Adiciona timestamp dinâmico para forçar atualização do cache do navegador
                                    import time
                                    timestamp = int(time.time() * 1000)  # Timestamp em milissegundos
                                    
                                    # Verifica se a URL já tem parâmetros de query
                                    separator = '&' if '?' in base_url else '?'
                                    link_pdf_despacho = f"{base_url}{separator}_t={timestamp}"
                                except Exception as e:
                                    logger.warning(f"Erro ao obter URL do PDF para tramitação {cod_tramitacao_int}: {e}")
                            else:
                                logger.debug(f"PDF não encontrado para tramitação {cod_tramitacao_int} no repositório")
                            
                            # Verifica se PDF foi gerado recentemente (via REQUEST se disponível)
                            if hasattr(self.request, 'get'):
                                pdf_gerado = bool(self.request.get('pdf_gerado', False))
                    except Exception as e:
                        logger.warning(f"Erro ao obter link do PDF: {e}", exc_info=True)
                
                # Renderiza formulário completo (sempre no sidebar) usando novo renderizador
                # Converte cod_entidade para int se necessário
                cod_entidade_int = int(cod_entidade) if cod_entidade else 0
                cod_tramitacao_int = int(cod_tramitacao) if cod_tramitacao else None
                
                portal_url = str(self.context.absolute_url())
                
                # Verifica se usuário assinou a tramitação (usando sessão SQLAlchemy)
                usuario_assinou = False
                if cod_tramitacao_int and cod_usuario:
                    usuario_assinou = self._verificar_usuario_assinou(session, cod_tramitacao_int, tipo, cod_usuario)
                    logger.debug(f"TramitacaoIndividualFormView - Usuário {cod_usuario} assinou tramitação {cod_tramitacao_int}: {usuario_assinou}")
                
                html = TramitacaoFormRenderer.render_individual_form(
                    tipo=tipo,
                    cod_entidade=cod_entidade_int,
                    cod_tramitacao=cod_tramitacao_int,
                    cod_usuario=cod_usuario,
                    nome_usuario=nome_usuario or '',
                    unidades_usuario=unidades_usuario,
                    dados_tramitacao=dados_tramitacao,
                    dat_tramitacao=dat_tramitacao,
                    info_processo=info_processo,
                    unidades_destino=unidades_destino,
                    status_opcoes=status_opcoes,
                    link_pdf_despacho=link_pdf_despacho,
                    pdf_gerado=pdf_gerado,
                    contexto_zope=self.context,
                    portal_url=portal_url,
                    usuario_assinou=usuario_assinou
                )
                
                # Sessão é fechada automaticamente ao sair do with
                return self._resposta_json({
                    'html': html,
                    'tipo': tipo,
                    'dados': dados_tramitacao,  # Inclui dados da tramitação para popular formulário
                    'info_processo': info_processo  # Informações do processo para exibir no cabeçalho
                })
        
        except Exception as e:
            return self._tratar_erro(e, "TramitacaoIndividualFormView")
    
    def _obter_dados_usuario_em_sessao(self, session: Any, cod_usuario: int, tipo: str) -> tuple:
        """Obtém unidades do usuário e nome do usuário usando sessão existente"""
        unidades_usuario = []
        nome_usuario = ''
        
        try:
            # Obtém unidades do usuário
            unidades_usuario_query = session.query(UsuarioUnidTram).filter(
                UsuarioUnidTram.cod_usuario == cod_usuario,
                UsuarioUnidTram.ind_excluido == 0
            ).all()
            
            for usuario_unid in unidades_usuario_query:
                unidade = session.query(UnidadeTramitacao).options(
                    selectinload(UnidadeTramitacao.comissao),
                    selectinload(UnidadeTramitacao.orgao),
                    selectinload(UnidadeTramitacao.parlamentar)
                ).filter(
                    UnidadeTramitacao.cod_unid_tramitacao == usuario_unid.cod_unid_tramitacao,
                    UnidadeTramitacao.ind_excluido == 0
                ).first()
                
                if unidade:
                    # Filtra por tipo
                    if (tipo == 'MATERIA' and unidade.ind_leg == 1) or (tipo == 'DOCUMENTO' and unidade.ind_adm == 1):
                        nome_unidade = _get_nome_unidade_tramitacao(unidade)
                        if nome_unidade:
                            unidades_usuario.append({
                                'cod': unidade.cod_unid_tramitacao,
                                'nome': nome_unidade
                            })
            
            # Obtém nome do usuário
            usuario = session.query(Usuario).filter(
                Usuario.cod_usuario == cod_usuario,
                Usuario.ind_excluido == 0
            ).first()
            if usuario:
                nome_usuario = usuario.nom_completo or usuario.nom_usuario or ''
        except Exception as e:
            logger.error(f"Erro ao obter dados do usuário: {e}", exc_info=True)
        
        return unidades_usuario, nome_usuario
    
    def _obter_info_processo_em_sessao(self, session: Any, tipo: str, cod_entidade: str) -> Optional[Dict[str, Any]]:
        """Obtém informações do processo usando sessão existente"""
        try:
            cod_entidade_int = validar_codigo_entidade(cod_entidade, 'cod_entidade')
            from openlegis.sagl.models.models import MateriaLegislativa, DocumentoAdministrativo, Autoria, Autor
            
            # Validação de consistência: verifica se o tipo corresponde ao processo
            if tipo == 'MATERIA':
                materia = session.query(MateriaLegislativa).filter(
                    MateriaLegislativa.cod_materia == cod_entidade_int,
                    MateriaLegislativa.ind_excluido == 0
                ).first()
                
                if not materia:
                    # Verifica se existe como documento (inconsistência)
                    documento = session.query(DocumentoAdministrativo).filter(
                        DocumentoAdministrativo.cod_documento == cod_entidade_int,
                        DocumentoAdministrativo.ind_excluido == 0
                    ).first()
                    if documento:
                        logger.warning(
                            f"Inconsistência no tipo de processo: código {cod_entidade_int} "
                            f"é um documento administrativo, mas tipo informado foi 'MATERIA'"
                        )
                        raise ValidationError(
                            'Inconsistência no tipo de processo: '
                            'o código informado corresponde a um processo administrativo, '
                            'mas o tipo informado foi "Legislativo".'
                        )
                    return None
                
                autoria = session.query(Autoria).options(
                    selectinload(Autoria.autor).selectinload(Autor.parlamentar),
                    selectinload(Autoria.autor).selectinload(Autor.comissao)
                ).filter(
                    Autoria.cod_materia == cod_entidade_int,
                    Autoria.ind_excluido == 0
                ).first()
                
                autoria_nome = ''
                if autoria and autoria.autor:
                    if autoria.autor.parlamentar:
                        autoria_nome = autoria.autor.parlamentar.nom_parlamentar or ''
                    elif autoria.autor.comissao:
                        autoria_nome = autoria.autor.comissao.nom_comissao or ''
                    elif autoria.autor.nom_autor:
                        autoria_nome = autoria.autor.nom_autor or ''
                
                sigla_tipo = ''
                if materia.tipo_materia_legislativa:
                    sigla_tipo = materia.tipo_materia_legislativa.sgl_tipo_materia or ''
                
                # Extrai dados antes de retornar
                num = materia.num_ident_basica or ''
                ano = materia.ano_ident_basica or ''
                
                return {
                    'numero': num,
                    'ano': ano,
                    'sigla': sigla_tipo,
                    'autoria': autoria_nome,
                    'tipo_label': 'Processo Legislativo'
                }
            else:  # DOCUMENTO
                documento = session.query(DocumentoAdministrativo).filter(
                    DocumentoAdministrativo.cod_documento == cod_entidade_int,
                    DocumentoAdministrativo.ind_excluido == 0
                ).first()
                
                if not documento:
                    # Verifica se existe como matéria (inconsistência)
                    materia = session.query(MateriaLegislativa).filter(
                        MateriaLegislativa.cod_materia == cod_entidade_int,
                        MateriaLegislativa.ind_excluido == 0
                    ).first()
                    if materia:
                        logger.warning(
                            f"Inconsistência no tipo de processo: código {cod_entidade_int} "
                            f"é uma matéria legislativa, mas tipo informado foi 'DOCUMENTO'"
                        )
                        raise ValidationError(
                            'Inconsistência no tipo de processo: '
                            'o código informado corresponde a um processo legislativo, '
                            'mas o tipo informado foi "Administrativo".'
                        )
                    return None
                
                interessado_nome = documento.txt_interessado or ''
                sigla_tipo = ''
                if documento.tipo_documento_administrativo:
                    sigla_tipo = documento.tipo_documento_administrativo.sgl_tipo_documento or ''
                
                # Extrai dados antes de retornar
                num = documento.num_documento or ''
                ano = documento.ano_documento or ''
                
                return {
                    'numero': num,
                    'ano': ano,
                    'sigla': sigla_tipo,
                    'interessado': interessado_nome,
                    'tipo_label': 'Processo Administrativo'
                }
        except ValidationError:
            # Re-raise ValidationError para ser tratado pelo chamador
            raise
        except Exception as e:
            logger.error(f"Erro ao obter informações do processo: {e}", exc_info=True)
        
        return None
    
    def _processar_unidade_caixa_em_sessao(self, session: Any, unidades_usuario: List[Dict], cod_unid_tram_local_caixa_int: int) -> List[Dict]:
        """Processa unidade da caixa de entrada usando sessão existente"""
        # Verifica se a unidade da caixa está nas unidades do usuário
        for unid in unidades_usuario:
            try:
                if int(unid['cod']) == cod_unid_tram_local_caixa_int:
                    return unidades_usuario
            except (ValueError, TypeError):
                continue
        
        # Se não encontrou, busca diretamente no banco
        try:
            unidade = session.query(UnidadeTramitacao).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UnidadeTramitacao.cod_unid_tramitacao == cod_unid_tram_local_caixa_int,
                UnidadeTramitacao.ind_excluido == 0
            ).first()
            
            if unidade:
                nome_unidade_caixa = _get_nome_unidade_tramitacao(unidade)
                cod_unid = unidade.cod_unid_tramitacao
                unidades_usuario.append({
                    'cod': cod_unid,
                    'nome': nome_unidade_caixa
                })
        except Exception as e:
            logger.error(f"Erro ao buscar unidade da caixa: {e}", exc_info=True)
        
        return unidades_usuario
    
    def _obter_unidades_destino_e_status_em_sessao(self, session: Any, tipo: str, cod_unid_tram_local: Optional[int]) -> tuple:
        """Obtém unidades de destino e status usando sessão existente"""
        unidades_destino = []
        status_opcoes = []
        
        if not cod_unid_tram_local:
            return unidades_destino, status_opcoes
        
        try:
            unidade_origem = session.query(UnidadeTramitacao).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UnidadeTramitacao.cod_unid_tramitacao == cod_unid_tram_local,
                UnidadeTramitacao.ind_excluido == 0
            ).first()
            
            if unidade_origem and unidade_origem.unid_dest_permitidas:
                unid_dest_ids = [id.strip() for id in str(unidade_origem.unid_dest_permitidas).split(',') if id.strip()]
                for unid_id in unid_dest_ids:
                    try:
                        unid_dest = session.query(UnidadeTramitacao).options(
                            selectinload(UnidadeTramitacao.comissao),
                            selectinload(UnidadeTramitacao.orgao),
                            selectinload(UnidadeTramitacao.parlamentar)
                        ).filter(
                            UnidadeTramitacao.cod_unid_tramitacao == int(unid_id),
                            UnidadeTramitacao.ind_excluido == 0
                        ).first()
                        
                        if unid_dest:
                            nome_unidade = _get_nome_unidade_tramitacao(unid_dest)
                            if nome_unidade:
                                if tipo == 'MATERIA' and unid_dest.ind_leg == 1:
                                    unidades_destino.append({
                                        'id': str(unid_dest.cod_unid_tramitacao),
                                        'name': nome_unidade
                                    })
                                elif tipo == 'DOCUMENTO' and unid_dest.ind_adm == 1:
                                    unidades_destino.append({
                                        'id': str(unid_dest.cod_unid_tramitacao),
                                        'name': nome_unidade
                                    })
                    except (ValueError, TypeError):
                        continue
            
            # Busca status permitidos
            if unidade_origem:
                if tipo == 'MATERIA' and unidade_origem.status_permitidos:
                    status_ids = [id.strip() for id in str(unidade_origem.status_permitidos).split(',') if id.strip()]
                    if status_ids:
                        status_list = session.query(StatusTramitacao).filter(
                            StatusTramitacao.cod_status.in_([int(sid) for sid in status_ids]),
                            StatusTramitacao.ind_excluido == 0
                        ).order_by(StatusTramitacao.des_status).all()
                        for status in status_list:
                            status_opcoes.append({
                                'id': str(status.cod_status),
                                'name': status.des_status or ''
                            })
                elif tipo == 'DOCUMENTO' and unidade_origem.status_adm_permitidos:
                    status_ids = [id.strip() for id in str(unidade_origem.status_adm_permitidos).split(',') if id.strip()]
                    if status_ids:
                        status_list = session.query(StatusTramitacaoAdministrativo).filter(
                            StatusTramitacaoAdministrativo.cod_status.in_([int(sid) for sid in status_ids]),
                            StatusTramitacaoAdministrativo.ind_excluido == 0
                        ).order_by(StatusTramitacaoAdministrativo.des_status).all()
                        for status in status_list:
                            status_opcoes.append({
                                'id': str(status.cod_status),
                                'name': status.des_status or ''
                            })
        except Exception as e:
            logger.error(f"Erro ao buscar unidades de destino e status: {e}", exc_info=True)
        
        return unidades_destino, status_opcoes
    
    def _obter_dados_tramitacao_form(self, tipo: str, cod_tramitacao: str) -> Optional[Dict[str, Any]]:
        """Obtém dados da tramitação para formulário (leitura apenas)"""
        try:
            cod_tramitacao_int = validar_codigo_entidade(cod_tramitacao, 'cod_tramitacao')
            with db_session_readonly() as session:
                from openlegis.sagl.models.models import Tramitacao, TramitacaoAdministrativo
                from datetime import datetime
                
                if tipo == 'MATERIA':
                    tram = session.query(Tramitacao).filter(
                        Tramitacao.cod_tramitacao == cod_tramitacao_int,
                        Tramitacao.ind_excluido == 0
                    ).first()
                else:
                    tram = session.query(TramitacaoAdministrativo).filter(
                        TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao_int,
                        TramitacaoAdministrativo.ind_excluido == 0
                    ).first()
                
                if not tram:
                    return None
                
                # Extrai todos os dados ANTES de expungar
                cod_tram = tram.cod_tramitacao
                cod_unid_local = tram.cod_unid_tram_local
                cod_user_local = tram.cod_usuario_local
                cod_unid_dest = tram.cod_unid_tram_dest
                cod_user_dest = tram.cod_usuario_dest
                cod_stat = tram.cod_status
                ind_urg = tram.ind_urgencia if hasattr(tram, 'ind_urgencia') else 0
                txt_tram = tram.txt_tramitacao or ''
                ind_ult = tram.ind_ult_tramitacao
                dat_enc = tram.dat_encaminha
                dat_fim = tram.dat_fim_prazo
                
                # Expunge objetos da sessão
                session.expunge_all()
                
                # Formata datas após expungar
                dat_fim_prazo_str = None
                if dat_fim:
                    if isinstance(dat_fim, datetime):
                        dat_fim_prazo_str = dat_fim.strftime('%d/%m/%Y')
                    elif hasattr(dat_fim, 'strftime'):
                        dat_fim_prazo_str = dat_fim.strftime('%d/%m/%Y')
                    else:
                        dat_fim_prazo_str = str(dat_fim)
                
                return {
                    'cod_tramitacao': cod_tram,
                    'cod_unid_tram_local': cod_unid_local,
                    'cod_usuario_local': cod_user_local,
                    'cod_unid_tram_dest': cod_unid_dest,
                    'cod_usuario_dest': cod_user_dest,
                    'cod_status': cod_stat,
                    'ind_urgencia': ind_urg,
                    'txt_tramitacao': txt_tram,
                    'dat_fim_prazo': dat_fim_prazo_str,
                    'ind_ult_tramitacao': ind_ult,
                    'dat_encaminha': dat_enc is not None
                }
        except Exception as e:
            logger.error(f"Erro ao obter dados da tramitação: {e}", exc_info=True)
            return None
    
    def _obter_dados_usuario(self, cod_usuario: int, tipo: str) -> tuple:
        """Obtém unidades do usuário e nome do usuário (leitura apenas)"""
        unidades_usuario = []
        nome_usuario = ''
        
        try:
            with db_session_readonly() as session:
                # Obtém unidades do usuário
                unidades_usuario_query = session.query(UsuarioUnidTram).filter(
                    UsuarioUnidTram.cod_usuario == cod_usuario,
                    UsuarioUnidTram.ind_excluido == 0
                ).all()
                
                for usuario_unid in unidades_usuario_query:
                    unidade = session.query(UnidadeTramitacao).options(
                        selectinload(UnidadeTramitacao.comissao),
                        selectinload(UnidadeTramitacao.orgao),
                        selectinload(UnidadeTramitacao.parlamentar)
                    ).filter(
                        UnidadeTramitacao.cod_unid_tramitacao == usuario_unid.cod_unid_tramitacao,
                        UnidadeTramitacao.ind_excluido == 0
                    ).first()
                    
                    if unidade:
                        # Filtra por tipo
                        if (tipo == 'MATERIA' and unidade.ind_leg == 1) or (tipo == 'DOCUMENTO' and unidade.ind_adm == 1):
                            nome_unidade = _get_nome_unidade_tramitacao(unidade)
                            if nome_unidade:
                                unidades_usuario.append({
                                    'cod': unidade.cod_unid_tramitacao,
                                    'nome': nome_unidade
                                })
                
                # Obtém nome do usuário
                usuario = session.query(Usuario).filter(
                    Usuario.cod_usuario == cod_usuario,
                    Usuario.ind_excluido == 0
                ).first()
                if usuario:
                    nome_usuario = usuario.nom_completo or usuario.nom_usuario or ''
                
                # Expunge objetos da sessão antes de retornar
                session.expunge_all()
        except Exception as e:
            logger.error(f"Erro ao obter dados do usuário: {e}", exc_info=True)
        
        return unidades_usuario, nome_usuario
    
    def _obter_info_processo(self, tipo: str, cod_entidade: str) -> Optional[Dict[str, Any]]:
        """Obtém informações do processo (matéria ou documento) - leitura apenas"""
        try:
            cod_entidade_int = validar_codigo_entidade(cod_entidade, 'cod_entidade')
            with db_session_readonly() as session:
                if tipo == 'MATERIA':
                    from openlegis.sagl.models.models import MateriaLegislativa, Autoria, Autor
                    materia = session.query(MateriaLegislativa).filter(
                        MateriaLegislativa.cod_materia == cod_entidade_int,
                        MateriaLegislativa.ind_excluido == 0
                    ).first()
                    
                    if materia:
                        autoria = session.query(Autoria).options(
                            selectinload(Autoria.autor).selectinload(Autor.parlamentar),
                            selectinload(Autoria.autor).selectinload(Autor.comissao)
                        ).filter(
                            Autoria.cod_materia == cod_entidade_int,
                            Autoria.ind_excluido == 0
                        ).first()
                        
                        autoria_nome = ''
                        if autoria and autoria.autor:
                            if autoria.autor.parlamentar:
                                autoria_nome = autoria.autor.parlamentar.nom_parlamentar or ''
                            elif autoria.autor.comissao:
                                autoria_nome = autoria.autor.comissao.nom_comissao or ''
                            elif autoria.autor.nom_autor:
                                autoria_nome = autoria.autor.nom_autor or ''
                        
                        sigla_tipo = ''
                        if materia.tipo_materia_legislativa:
                            sigla_tipo = materia.tipo_materia_legislativa.sgl_tipo_materia or ''
                        
                        # Extrai dados antes de expungar
                        num = materia.num_ident_basica or ''
                        ano = materia.ano_ident_basica or ''
                        session.expunge_all()
                        
                        return {
                            'numero': num,
                            'ano': ano,
                            'sigla': sigla_tipo,
                            'autoria': autoria_nome,
                            'tipo_label': 'Processo Legislativo'
                        }
                else:  # DOCUMENTO
                    from openlegis.sagl.models.models import DocumentoAdministrativo
                    documento = session.query(DocumentoAdministrativo).filter(
                        DocumentoAdministrativo.cod_documento == cod_entidade_int,
                        DocumentoAdministrativo.ind_excluido == 0
                    ).first()
                    
                    if documento:
                        interessado_nome = documento.txt_interessado or ''
                        sigla_tipo = ''
                        if documento.tipo_documento_administrativo:
                            sigla_tipo = documento.tipo_documento_administrativo.sgl_tipo_documento or ''
                        
                        # Extrai dados antes de expungar
                        num = documento.num_documento or ''
                        ano = documento.ano_documento or ''
                        session.expunge_all()
                        
                        return {
                            'numero': num,
                            'ano': ano,
                            'sigla': sigla_tipo,
                            'interessado': interessado_nome,
                            'tipo_label': 'Processo Administrativo'
                        }
        except Exception as e:
            logger.error(f"Erro ao obter informações do processo: {e}", exc_info=True)
        
        return None
    
    def _processar_unidade_caixa(self, unidades_usuario: List[Dict], cod_unid_tram_local_caixa_int: int) -> List[Dict]:
        """Processa unidade da caixa de entrada (leitura apenas)"""
        # Verifica se a unidade da caixa está nas unidades do usuário
        for unid in unidades_usuario:
            try:
                if int(unid['cod']) == cod_unid_tram_local_caixa_int:
                    return unidades_usuario
            except (ValueError, TypeError):
                continue
        
        # Se não encontrou, busca diretamente no banco
        try:
            with db_session_readonly() as session:
                unidade = session.query(UnidadeTramitacao).options(
                    selectinload(UnidadeTramitacao.comissao),
                    selectinload(UnidadeTramitacao.orgao),
                    selectinload(UnidadeTramitacao.parlamentar)
                ).filter(
                    UnidadeTramitacao.cod_unid_tramitacao == cod_unid_tram_local_caixa_int,
                    UnidadeTramitacao.ind_excluido == 0
                ).first()
                
                if unidade:
                    nome_unidade_caixa = _get_nome_unidade_tramitacao(unidade)
                    cod_unid = unidade.cod_unid_tramitacao
                    session.expunge_all()
                    unidades_usuario.append({
                        'cod': cod_unid,
                        'nome': nome_unidade_caixa
                    })
        except Exception as e:
            logger.error(f"Erro ao buscar unidade da caixa: {e}", exc_info=True)
        
        return unidades_usuario
    
    def _obter_unidades_destino_e_status(
        self, tipo: str, cod_unid_tram_local: Optional[int]
    ) -> tuple:
        """Obtém unidades de destino e status permitidos (leitura apenas)"""
        unidades_destino = []
        status_opcoes = []
        
        if not cod_unid_tram_local:
            return unidades_destino, status_opcoes
        
        try:
            with db_session_readonly() as session:
                unidade_origem = session.query(UnidadeTramitacao).options(
                    selectinload(UnidadeTramitacao.comissao),
                    selectinload(UnidadeTramitacao.orgao),
                    selectinload(UnidadeTramitacao.parlamentar)
                ).filter(
                    UnidadeTramitacao.cod_unid_tramitacao == cod_unid_tram_local,
                    UnidadeTramitacao.ind_excluido == 0
                ).first()
                
                if unidade_origem and unidade_origem.unid_dest_permitidas:
                    unid_dest_ids = [id.strip() for id in str(unidade_origem.unid_dest_permitidas).split(',') if id.strip()]
                    for unid_id in unid_dest_ids:
                        try:
                            unid_dest = session.query(UnidadeTramitacao).options(
                                selectinload(UnidadeTramitacao.comissao),
                                selectinload(UnidadeTramitacao.orgao),
                                selectinload(UnidadeTramitacao.parlamentar)
                            ).filter(
                                UnidadeTramitacao.cod_unid_tramitacao == int(unid_id),
                                UnidadeTramitacao.ind_excluido == 0
                            ).first()
                            
                            if unid_dest:
                                nome_unidade = _get_nome_unidade_tramitacao(unid_dest)
                                if nome_unidade:
                                    if tipo == 'MATERIA' and unid_dest.ind_leg == 1:
                                        unidades_destino.append({
                                            'id': str(unid_dest.cod_unid_tramitacao),
                                            'name': nome_unidade
                                        })
                                    elif tipo == 'DOCUMENTO' and unid_dest.ind_adm == 1:
                                        unidades_destino.append({
                                            'id': str(unid_dest.cod_unid_tramitacao),
                                            'name': nome_unidade
                                        })
                        except (ValueError, TypeError):
                            continue
                
                # Busca status permitidos
                if unidade_origem:
                    if tipo == 'MATERIA' and unidade_origem.status_permitidos:
                        status_ids = [id.strip() for id in str(unidade_origem.status_permitidos).split(',') if id.strip()]
                        if status_ids:
                            status_list = session.query(StatusTramitacao).filter(
                                StatusTramitacao.cod_status.in_([int(sid) for sid in status_ids]),
                                StatusTramitacao.ind_excluido == 0
                            ).order_by(StatusTramitacao.des_status).all()
                            for status in status_list:
                                status_opcoes.append({
                                    'id': str(status.cod_status),
                                    'name': status.des_status or ''
                                })
                    elif tipo == 'DOCUMENTO' and unidade_origem.status_adm_permitidos:
                        status_ids = [id.strip() for id in str(unidade_origem.status_adm_permitidos).split(',') if id.strip()]
                        if status_ids:
                            status_list = session.query(StatusTramitacaoAdministrativo).filter(
                                StatusTramitacaoAdministrativo.cod_status.in_([int(sid) for sid in status_ids]),
                                StatusTramitacaoAdministrativo.ind_excluido == 0
                            ).order_by(StatusTramitacaoAdministrativo.des_status).all()
                            for status in status_list:
                                # Extrai dados antes de adicionar
                                status_opcoes.append({
                                    'id': str(status.cod_status),
                                    'name': status.des_status or ''
                                })
                
                # Expunge objetos da sessão antes de retornar
                session.expunge_all()
        except Exception as e:
            logger.error(f"Erro ao buscar unidades de destino e status: {e}", exc_info=True)
        
        return unidades_destino, status_opcoes
    
    def _verificar_usuario_assinou(self, session, cod_tramitacao: int, tipo: str, cod_usuario: int) -> bool:
        """
        Verifica se o usuário atual assinou a tramitação usando SQLAlchemy
        
        Args:
            session: Sessão SQLAlchemy
            cod_tramitacao: Código da tramitação
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_usuario: Código do usuário
            
        Returns:
            True se o usuário assinou, False caso contrário
        """
        if not cod_tramitacao or not cod_usuario:
            return False
        
        try:
            tipo_doc = 'tramitacao' if tipo == 'MATERIA' else 'tramitacao_adm'
            # Usa SQLAlchemy para verificar assinatura
            assinatura = session.query(AssinaturaDocumento).filter(
                AssinaturaDocumento.codigo == cod_tramitacao,
                AssinaturaDocumento.tipo_doc == tipo_doc,
                AssinaturaDocumento.cod_usuario == cod_usuario,
                AssinaturaDocumento.ind_assinado == 1,
                AssinaturaDocumento.ind_excluido == 0
            ).first()
            return assinatura is not None
        except Exception as e:
            logger.debug(f"Erro ao verificar se usuário assinou tramitação {cod_tramitacao}: {e}", exc_info=True)
            return False
    
    def _verificar_assinatura_disponivel(self) -> bool:
        """
        Verifica se assinatura digital ICP-Brasil está configurada
        
        Returns:
            True se restpki_access_token está configurado e não vazio
        """
        try:
            restpki_token = self.context.sapl_documentos.props_sagl.restpki_access_token
            return bool(restpki_token and restpki_token.strip())
        except AttributeError:
            # props_sagl pode não ter restpki_access_token
            return False
        except Exception as e:
            logger.debug(f"Erro ao verificar restpki_access_token: {e}")
            return False
    
    def _renderizar_formulario_completo(self, tipo, cod_entidade, cod_tramitacao, cod_usuario, nome_usuario, unidades_usuario, dados_tramitacao, dat_tramitacao, info_processo=None, link_pdf_despacho=None, pdf_gerado=False):
        """Renderiza formulário completo HTML para sidebar"""
        html = ''
        
        # Garante que dados_tramitacao seja sempre um dicionário
        if not dados_tramitacao:
            dados_tramitacao = {}
        
        # Log para debug
        logger.info(f"_renderizar_formulario_completo - cod_unid_tram_local: {dados_tramitacao.get('cod_unid_tram_local')}, nome_usuario: {nome_usuario}, unidades_usuario: {len(unidades_usuario)}")
        
        # Informações do processo no topo (se disponível)
        if info_processo:
            html += '<div class="alert alert-info mb-3" role="alert">'
            html += '<div class="d-flex align-items-center">'
            html += '<i class="mdi mdi-file-document-outline me-2 fs-4"></i>'
            html += '<div class="flex-grow-1">'
            html += f'<strong>{info_processo["tipo_label"]}</strong><br>'
            # Monta número completo com sigla se disponível
            numero_completo = ''
            if info_processo.get('sigla'):
                numero_completo = f'{info_processo["sigla"]} {info_processo["numero"]}/{info_processo["ano"]}'
            else:
                numero_completo = f'{info_processo["numero"]}/{info_processo["ano"]}'
            html += f'<span class="text-muted">Número: {numero_completo}</span>'
            if tipo == 'MATERIA' and info_processo.get('autoria'):
                html += f' | <span class="text-muted">Autoria: {info_processo["autoria"]}</span>'
            elif tipo == 'DOCUMENTO' and info_processo.get('interessado'):
                html += f' | <span class="text-muted">Interessado: {info_processo["interessado"]}</span>'
            html += '</div></div></div>'
        
        html += f'<form class="needs-validation" id="tramitacao_individual_form" method="post" enctype="multipart/form-data" novalidate>'
        
        # Campos hidden
        html += f'<input type="hidden" name="hdn_tipo_tramitacao" value="{tipo}" />'
        html += f'<input type="hidden" name="hdn_cod_materia" value="{cod_entidade if tipo == "MATERIA" else ""}" />'
        html += f'<input type="hidden" name="hdn_cod_documento" value="{cod_entidade if tipo == "DOCUMENTO" else ""}" />'
        html += f'<input type="hidden" name="hdn_cod_usuario_local" id="hdn_cod_usuario_local" value="{cod_usuario or ""}" />'
        html += f'<input type="hidden" name="hdn_dat_tramitacao" value="{dat_tramitacao}" />'
        html += f'<input type="hidden" id="hdn_file" name="hdn_file" value="0" />'
        if cod_tramitacao:
            html += f'<input type="hidden" name="hdn_cod_tramitacao" value="{cod_tramitacao}" />'
        
        # Seção: Origem
        html += '<div class="card mb-2">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0 small"><i class="mdi mdi-arrow-up-circle me-1"></i>Origem</h6>'
        html += '</div>'
        html += '<div class="card-body p-2">'
        html += '<div class="row g-2">'
        html += '<div class="col-12 col-sm-4 mb-2">'
        html += '<label class="form-label small required" for="txt_dat_tramitacao">Data da Tramitação</label>'
        html += '<div class="input-group input-group-sm">'
        html += f'<input class="form-control form-control-sm" type="text" name="txt_dat_tramitacao" id="txt_dat_tramitacao" value="{dat_tramitacao}" autocomplete="off" readonly required />'
        html += '<span class="input-group-text"><i class="mdi mdi-calendar"></i></span>'
        html += '</div></div>'
        
        html += '<div class="col-12 col-md-5 mb-2">'
        html += _renderizar_label_campo('lst_cod_unid_tram_local', 'Unidade de Origem', obrigatorio=True)
        # Obtém unidade selecionada (sempre será a unidade da caixa de entrada)
        cod_unid_selecionada = dados_tramitacao.get('cod_unid_tram_local') if dados_tramitacao else None
        
        # Busca nome da unidade selecionada
        nome_unidade_selecionada = ''
        if cod_unid_selecionada:
            for unid in unidades_usuario:
                try:
                    if int(unid['cod']) == int(cod_unid_selecionada):
                        nome_unidade_selecionada = unid['nome']
                        logger.info(f"_renderizar_formulario_completo - Unidade encontrada: {nome_unidade_selecionada} (cod: {cod_unid_selecionada})")
                        break
                except (ValueError, TypeError) as e:
                    logger.warning(f"_renderizar_formulario_completo - Erro ao comparar unidade: {e}")
                    continue
            
            # Se não encontrou nas unidades do usuário, busca diretamente no banco
            if not nome_unidade_selecionada and cod_unid_selecionada:
                try:
                    # Usa db_session_readonly() para leitura (pode usar with)
                    with db_session_readonly() as session:
                        unidade = session.query(UnidadeTramitacao).options(
                            selectinload(UnidadeTramitacao.comissao),
                            selectinload(UnidadeTramitacao.orgao),
                            selectinload(UnidadeTramitacao.parlamentar)
                        ).filter(
                            UnidadeTramitacao.cod_unid_tramitacao == int(cod_unid_selecionada),
                            UnidadeTramitacao.ind_excluido == 0
                        ).first()
                        
                        if unidade:
                            nome_unidade_selecionada = _get_nome_unidade_tramitacao(unidade)
                            logger.info(
                                f"_renderizar_formulario_completo - Unidade obtida diretamente do banco: "
                                f"{nome_unidade_selecionada} (cod: {cod_unid_selecionada})"
                            )
                except Exception as e:
                    logger.error(f"_renderizar_formulario_completo - Erro ao buscar unidade no banco: {e}", exc_info=True)
        
        # Campo readonly (não pode ser alterado - sempre será a unidade da caixa de entrada)
        if cod_unid_selecionada and nome_unidade_selecionada:
            html += f'<input type="hidden" name="lst_cod_unid_tram_local" id="lst_cod_unid_tram_local" value="{cod_unid_selecionada}" />'
            html += f'<input class="form-control form-control-sm bg-light" type="text" id="txt_unid_tram_local_display" value="{nome_unidade_selecionada}" readonly aria-label="Unidade de Origem (somente leitura)" aria-readonly="true" tabindex="-1" aria-describedby="lst_cod_unid_tram_local_help" />'
        elif cod_unid_selecionada:
            # Se tem código mas não tem nome, mostra o código
            html += f'<input type="hidden" name="lst_cod_unid_tram_local" id="lst_cod_unid_tram_local" value="{cod_unid_selecionada}" />'
            html += f'<input class="form-control form-control-sm bg-light" type="text" id="txt_unid_tram_local_display" value="Unidade {cod_unid_selecionada}" readonly aria-label="Unidade de Origem (somente leitura)" aria-readonly="true" tabindex="-1" aria-describedby="lst_cod_unid_tram_local_help" />'
            logger.warning(f"_renderizar_formulario_completo - Unidade sem nome encontrada: cod={cod_unid_selecionada}")
        else:
            # Fallback: se não encontrou, mostra select desabilitado
            html += '<select class="form-select form-select-sm" id="lst_cod_unid_tram_local" name="lst_cod_unid_tram_local" required disabled aria-label="Unidade de Origem">'
            html += '<option value="">Selecione uma unidade na caixa de entrada</option>'
            for unid in unidades_usuario:
                html += f'<option value="{unid["cod"]}">{unid["nome"]}</option>'
            html += '</select>'
        html += '</div>'
        
        html += '<div class="col-12 col-md-3 mb-2">'
        html += _renderizar_label_campo('txt_nom_usuario', 'Usuário de Origem', obrigatorio=True)
        # Garante que o nome do usuário seja exibido (já vem do backend, mas força exibição)
        nome_usuario_display = nome_usuario if nome_usuario else ''
        html += f'<input class="form-control form-control-sm bg-light" type="text" id="txt_nom_usuario" value="{nome_usuario_display}" readonly aria-label="Usuário de Origem (somente leitura)" aria-readonly="true" tabindex="-1" />'
        html += '</div></div></div></div>'
        
        # Seção: Destino
        html += '<div class="card mb-2">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0 small"><i class="mdi mdi-arrow-down-circle me-1"></i>Destino</h6>'
        html += '</div>'
        html += '<div class="card-body p-2">'
        html += '<div class="row g-2">'
        html += '<div class="col-12 col-sm-6 mb-2">'
        html += '<label class="form-label small required" for="lst_cod_unid_tram_dest">Unidade de Destino</label>'
        html += '<select class="tomselect form-select form-select-sm" name="lst_cod_unid_tram_dest" id="lst_cod_unid_tram_dest" data-placeholder="Selecione a unidade de destino..." style="width:100%" required>'
        html += '<option value="">Selecione a unidade de destino...</option>'
        html += '</select></div>'
        
        html += '<div class="col-12 col-sm-6 mb-2">'
        html += '<label class="form-label small" for="lst_cod_usuario_dest">Usuário de Destino</label>'
        html += '<select class="tomselect form-select form-select-sm" name="lst_cod_usuario_dest" id="lst_cod_usuario_dest" data-placeholder="Selecione o usuário de destino..." style="width:100%">'
        html += '<option value="">Selecione</option>'  # ✅ Opção em branco inicial (será substituída quando usuários forem carregados)
        html += '</select></div></div></div></div>'
        
        # Seção: Status e Prazo
        html += '<div class="card mb-3">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0"><i class="mdi mdi-information-outline me-1" aria-hidden="true"></i>Status e Prazo</h6>'
        html += '</div>'
        html += '<div class="card-body p-3">'
        html += '<div class="row g-3">'
        html += '<div class="col-12 col-md-6 mb-2">'
        html += _renderizar_label_campo('lst_cod_status', 'Status', obrigatorio=True)
        html += '<select class="tomselect form-select form-select-sm" id="lst_cod_status" name="lst_cod_status" data-placeholder="Selecione o status..." style="width:100%" required aria-required="true">'
        html += '<option value="">Selecione o status...</option>'
        html += '</select></div>'
        
        html += '<div class="col-12 col-md-3 mb-2">'
        html += _renderizar_label_campo('txt_dat_fim_prazo', 'Data de Fim de Prazo', obrigatorio=False)
        html += '<div class="input-group input-group-sm">'
        dat_fim_prazo_val = dados_tramitacao.get('dat_fim_prazo', '') if dados_tramitacao else ''
        html += f'<input type="text" class="form-control form-control-sm" placeholder="dd/mm/aaaa" name="txt_dat_fim_prazo" id="txt_dat_fim_prazo" value="{dat_fim_prazo_val}" autocomplete="off" aria-label="Data de Fim de Prazo">'
        html += f'<span class="input-group-text">{_renderizar_icone_decorativo("mdi mdi-calendar")}</span>'
        html += '</div></div>'
        
        # Urgente (apenas para processos legislativos - MATERIA)
        if tipo == 'MATERIA':
            html += '<div class="col-12 col-md-3 mb-2">'
            html += _renderizar_label_campo('rad_ind_urgencia', 'Urgente?', obrigatorio=True)
            ind_urgencia = dados_tramitacao.get('ind_urgencia', 0) if dados_tramitacao else 0
            html += '<div class="form-check form-check-inline">'
            html += f'<input class="form-check-input" type="radio" id="rad_urgencia_1" name="rad_ind_urgencia" value="1" {"checked" if ind_urgencia == 1 else ""} aria-required="true">'
            html += '<label class="form-check-label" for="rad_urgencia_1">Sim</label>'
            html += '</div>'
            html += '<div class="form-check form-check-inline">'
            html += f'<input class="form-check-input" type="radio" id="rad_urgencia_0" name="rad_ind_urgencia" value="0" {"checked" if ind_urgencia == 0 else ""} aria-required="true">'
            html += '<label class="form-check-label" for="rad_urgencia_0">Não</label>'
            html += '</div></div>'
        html += '</div></div></div>'
        
        # Seção: Despacho em PDF
        html += '<div class="card mb-2">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0 small"><i class="mdi mdi-file-pdf-box me-1"></i>Despacho em PDF</h6>'
        html += '</div>'
        html += '<div class="card-body p-2">'
        
        # Link do PDF do despacho (se existir) - adiciona antes das opções
        if link_pdf_despacho and cod_tramitacao:
            html += '<div class="alert alert-info mb-3 py-2" role="alert">'
            html += '<div class="d-flex align-items-center justify-content-between flex-wrap">'
            html += '<div class="d-flex align-items-center">'
            html += '<i class="mdi mdi-file-pdf-box me-2 text-danger" style="font-size: 1.1rem;"></i>'
            html += '<span class="small">PDF do despacho disponível:</span>'
            html += '</div>'
            html += '<div class="btn-group btn-group-sm mt-2 mt-md-0" role="group">'
            html += f'<a href="{link_pdf_despacho}" target="_blank" class="btn btn-primary btn-sm" id="btn_visualizar_pdf_tramitacao" data-link-pdf="{link_pdf_despacho}">'
            html += '<i class="mdi mdi-file-pdf-box me-1"></i> Visualizar'
            html += '</a>'
            
            # Botões de Assinatura Digital ICP-Brasil (se disponível)
            try:
                if self._verificar_assinatura_disponivel():
                    # Determina tipo_doc baseado no tipo de tramitação
                    tipo_doc = 'tramitacao' if tipo == 'MATERIA' else 'tramitacao_adm'
                    portal_url = str(self.context.absolute_url())
                    cod_tramitacao_str = str(cod_tramitacao) if cod_tramitacao else ''
                    
                    logger.debug(f"Adicionando botões de assinatura - cod_tramitacao: {cod_tramitacao_str}, tipo_doc: {tipo_doc}, portal_url: {portal_url}")
                    
                    # Botão "Assinar"
                    html += f'<button type="button" class="btn btn-primary btn-sm" '
                    html += f'data-bs-toggle="modal" data-bs-target="#iFrameModal" '
                    html += f'data-title="Assinar Digitalmente" '
                    html += f'data-src="{portal_url}/generico/assinador/pades-signature_html?codigo={cod_tramitacao_str}&tipo_doc={tipo_doc}&modal=1" '
                    html += f'title="Assinar PDF do despacho com certificado digital ICP-Brasil">'
                    html += f'<i class="fas fa-file-signature me-1"></i> Assinar</button>'
                    
                    # Botão "Assinaturas"
                    html += f'<button type="button" class="btn btn-primary btn-sm" '
                    html += f'data-bs-toggle="modal" data-bs-target="#iFrameModal" '
                    html += f'data-title="Assinaturas Digitais" '
                    html += f'data-src="{portal_url}/cadastros/assinatura/assinatura_solicitar_form?codigo={cod_tramitacao_str}&tipo_doc={tipo_doc}&modal=1" '
                    html += f'title="Visualizar status das assinaturas digitais">'
                    html += f'<i class="fas fa-file-signature me-1"></i> Assinaturas</button>'
                else:
                    logger.debug("Assinatura ICP-Brasil não disponível (restpki_access_token não configurado)")
            except Exception as e:
                logger.warning(f"Erro ao adicionar botões de assinatura ICP-Brasil: {e}", exc_info=True)
                # Não bloqueia renderização do formulário se houver erro
            
            html += '</div>'
            html += '</div>'
            if pdf_gerado:
                html += '<div class="mt-2"><small class="text-success"><i class="mdi mdi-check-circle me-1"></i>PDF gerado com sucesso!</small></div>'
            html += '</div>'
        
        html += '<div class="d-flex align-items-center flex-wrap gap-2">'
        html += '<div class="form-check">'
        html += '<input class="form-check-input" type="radio" id="rad_pdf_G" name="radTI" value="G" checked>'
        html += '<label class="form-check-label small" for="rad_pdf_G">Gerar</label>'
        html += '</div>'
        html += '<div class="form-check">'
        html += '<input class="form-check-input" type="radio" id="rad_pdf_S" name="radTI" value="S">'
        html += '<label class="form-check-label small" for="rad_pdf_S">Anexar</label>'
        html += '</div>'
        # Opção "Manter" só aparece se já existe um PDF gerado (edição de tramitação existente)
        if link_pdf_despacho:
            html += '<div class="form-check">'
            html += '<input class="form-check-input" type="radio" id="rad_pdf_M" name="radTI" value="M">'
            html += '<label class="form-check-label small" for="rad_pdf_M">Manter</label>'
            html += '</div>'
        html += '<input type="file" class="form-control form-control-sm" id="file_nom_arquivo" name="file_nom_arquivo" accept="application/pdf" disabled style="max-width: 250px; flex: 1 1 auto;">'
        html += '</div></div></div>'
        
        # Seção: Texto do Despacho
        html += '<div class="card mb-2">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0 small"><i class="mdi mdi-text me-1"></i>Texto do Despacho</h6>'
        html += '</div>'
        html += '<div class="card-body p-2">'
        txt_tramitacao = dados_tramitacao.get('txt_tramitacao', '') if dados_tramitacao else ''
        html += f'<textarea class="form-control form-control-sm" name="txa_txt_tramitacao" id="txa_txt_tramitacao" rows="6">{txt_tramitacao}</textarea>'
        html += '</div></div>'
        
        html += '</form>'
        
        # Script para habilitar/desabilitar campo de arquivo e atualizar link PDF automaticamente
        html += '''
        <script>
        $(document).ready(function() {
            // Habilita/desabilita campo de arquivo baseado na opção selecionada
            $('input[name="radTI"]').on('change', function() {
                const fileInput = $('#file_nom_arquivo');
                if ($(this).val() === 'S') {
                    fileInput.prop('disabled', false);
                    fileInput.prop('required', true);
                } else {
                    fileInput.prop('disabled', true);
                    fileInput.prop('required', false);
                    fileInput.val('');
                }
            });
            
            // ✅ Função global para atualizar link do botão PDF quando receber resposta do salvamento
            window.atualizarLinkPdfTramitacao = function(linkPdf) {
                if (linkPdf) {
                    var btnPdf = document.getElementById('btn_visualizar_pdf_tramitacao');
                    if (btnPdf) {
                        btnPdf.href = linkPdf;
                        btnPdf.setAttribute('data-link-pdf', linkPdf);
                        console.log('Link PDF atualizado:', linkPdf);
                        return true;
                    } else {
                        console.warn('Botão PDF não encontrado (id: btn_visualizar_pdf_tramitacao)');
                        return false;
                    }
                }
                return false;
            };
            
            // ✅ Intercepta respostas AJAX para atualizar link PDF automaticamente
            // Funciona com jQuery AJAX
            if (typeof $ !== 'undefined') {
                // Intercepta todas as chamadas AJAX
                $(document).ajaxSuccess(function(event, xhr, settings) {
                    try {
                        var response = xhr.responseJSON || (typeof xhr.responseText === 'string' ? JSON.parse(xhr.responseText) : null);
                        if (response) {
                            console.log('[Tramitacao] Resposta AJAX recebida:', response);
                            // Atualiza link PDF se presente
                            if (response.link_pdf_despacho && response.update_pdf_link) {
                                console.log('[Tramitacao] Atualizando link PDF via interceptor:', response.link_pdf_despacho);
                                window.atualizarLinkPdfTramitacao(response.link_pdf_despacho);
                            }
                            // Executa script inline se presente (garante atualização mesmo se interceptor falhar)
                            if (response.exec_script) {
                                try {
                                    console.log('[Tramitacao] Executando script inline de atualização');
                                    eval(response.exec_script);
                                } catch (e) {
                                    console.error('[Tramitacao] Erro ao executar script de atualização:', e);
                                }
                            }
                        }
                    } catch (e) {
                        // Ignora erros de parsing JSON
                        console.warn('[Tramitacao] Erro ao processar resposta AJAX:', e);
                    }
                });
            }
        });
        </script>
        
        <!-- TomSelect CSS e JS -->
        <link href="https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/css/tom-select.bootstrap5.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/js/tom-select.complete.min.js"></script>
        '''
        
        return html


class TramitacaoLoteSalvarView(GrokView, TramitacaoAPIBase):
    """View para salvar tramitação em lote (sempre no sidebar)"""
    
    context(Interface)
    name('tramitacao_lote_salvar_json')
    require('zope2.View')
    
    def render(self):
        """Salva tramitação em lote"""
        try:
            from .services import TramitacaoService
            
            # Obtém processos selecionados
            # Suporta tanto MultiDict (getall) quanto dict regular (get)
            if hasattr(self.request.form, 'getall'):
                processos = self.request.form.getall('check_tram')
            else:
                # Para dict regular, obtém o valor e normaliza para lista
                valor = self.request.form.get('check_tram')
                if valor is None:
                    processos = []
                elif isinstance(valor, list):
                    processos = valor
                else:
                    # Valor único, converte para lista
                    processos = [valor]
            
            if not processos:
                return self._resposta_erro('Nenhum processo selecionado')
            
            tipo = self._obter_tipo_tramitacao()
            cod_usuario = self._get_cod_usuario()
            
            if not cod_usuario:
                return self._resposta_erro('Usuário não autenticado')
            
            logger.info(f"TramitacaoLoteSalvarView - Iniciando operação de escrita - {len(processos)} processo(s)")
            # ✅ Use get_session() para obter uma sessão fresca (evita ResourceClosedError)
            session = get_session()  # Garante sessão fresca sem DataManager antigo
            session_id = id(session)
            # Valida tipo único dos processos
            from openlegis.sagl.models.models import MateriaLegislativa, DocumentoAdministrativo
            tipos_processos = set()
            
            for cod_entidade in processos:
                try:
                    cod_entidade_int = validar_codigo_entidade(cod_entidade, 'cod_entidade')
                    if tipo == 'MATERIA':
                        materia = session.query(MateriaLegislativa).filter(
                            MateriaLegislativa.cod_materia == cod_entidade_int,
                            MateriaLegislativa.ind_excluido == 0
                        ).first()
                        if not materia:
                            return self._resposta_erro(f'Processo legislativo {cod_entidade} não encontrado')
                        tipos_processos.add('MATERIA')
                    else:
                        documento = session.query(DocumentoAdministrativo).filter(
                            DocumentoAdministrativo.cod_documento == cod_entidade_int,
                            DocumentoAdministrativo.ind_excluido == 0
                        ).first()
                        if not documento:
                            return self._resposta_erro(f'Processo administrativo {cod_entidade} não encontrado')
                        tipos_processos.add('DOCUMENTO')
                except ValidationError as e:
                    return self._resposta_erro(str(e))
            
            # Valida que todos os processos são do mesmo tipo
            if len(tipos_processos) > 1:
                return self._resposta_erro(
                    'Não é possível tramitar processos de tipos diferentes em lote. '
                    'Selecione apenas processos do mesmo tipo (Legislativo ou Administrativo).'
                )
            
            # Valida que o tipo informado corresponde aos processos
            if tipos_processos and tipos_processos.pop() != tipo:
                return self._resposta_erro('Inconsistência: tipo informado não corresponde aos processos selecionados')
            
            # Prepara dados comuns para todos os processos
            dados = {
                'cod_unid_tram_local': self._obter_parametro('lst_cod_unid_tram_local', obrigatorio=True),
                'cod_usuario_local': cod_usuario,
                'cod_unid_tram_dest': self._obter_parametro('lst_cod_unid_tram_dest', obrigatorio=True),
                'cod_usuario_dest': self._obter_parametro('lst_cod_usuario_dest') or None,
                'cod_status': self._obter_parametro('lst_cod_status', obrigatorio=True),
                'txt_tramitacao': self._obter_parametro('txa_txt_tramitacao', ''),
                'dat_fim_prazo': self._parse_date(self._obter_parametro('txt_dat_fim_prazo'))
            }
            
            # Ind_urgencia apenas para processos legislativos (MATERIA)
            if tipo == 'MATERIA':
                dados['ind_urgencia'] = 1 if self._obter_parametro('rad_ind_urgencia') == '1' else 0
            
            # Valida PDF se opção "Anexar" estiver selecionada
            arquivo_pdf = self._obter_parametro('file_nom_arquivo')
            if arquivo_pdf:
                opcao_pdf = self._obter_parametro('radTI', 'G')
                try:
                    service_temp = TramitacaoService(session)
                    if hasattr(service_temp, '_validar_pdf'):
                        service_temp._validar_pdf(arquivo_pdf, opcao_pdf)
                except (ValueError, AttributeError) as e:
                    return self._resposta_erro(str(e))
            
            service = TramitacaoService(session)
            total = 0
            erros = []
            cod_tramitacoes = []  # Coleta códigos de tramitações criadas
            
            # Tramita cada processo
            for cod_entidade in processos:
                try:
                    cod_entidade_int = validar_codigo_entidade(cod_entidade, 'cod_entidade')
                    cod_tramitacao = service.enviar_tramitacao(
                        tipo=tipo,
                        cod_entidade=cod_entidade_int,
                        dados=dados
                    )
                    cod_tramitacoes.append(cod_tramitacao)
                    total += 1
                except ValueError as e:
                    erros.append(f"Processo {cod_entidade}: {str(e)}")
                    logger.warning(f"Erro ao tramitar processo {cod_entidade}: {e}")
                except Exception as e:
                    erros.append(f"Processo {cod_entidade}: Erro inesperado")
                    logger.error(f"Erro ao tramitar processo {cod_entidade}: {e}", exc_info=True)
            
            # ✅ CORRETO: Marca sessão como alterada SEM keep_session=True
            # O service já fez flush() para cada processo
            if total > 0:
                mark_changed(session)
            
            # ✅ CORRETO: Invalidação de cache via afterCommitHook APÓS o commit
            # Não executa durante a transação, apenas após commit bem-sucedido
            if total > 0:
                import transaction
                from .cache import invalidate_cache_contadores
                transaction.get().addAfterCommitHook(
                    lambda success, *args:
                        success and invalidate_cache_contadores(cod_usuario, None)
                )
            
            logger.info(f"TramitacaoLoteSalvarView - Operações concluídas - sessão id: {session_id}")
            
            # ✅ CORRETO: Extrai dados primitivos ANTES de retornar
            # Todos os dados são tipos básicos (int, list, str) - sem objetos ORM
            total_retorno = int(total)
            total_processos_retorno = len(processos)
            erros_retorno = list(erros) if erros else []
            
            if total_retorno == 0:
                return self._resposta_erro('Nenhum processo foi tramitado', codigo='nenhum_processo')
            
            # Dispara tasks de geração de PDF e anexo em lote (se necessário)
            # Nota: Tasks são disparadas antes do commit, mas têm retry logic para lidar com problemas de timing
            task_pdf_lote = None
            task_anexo_lote = None
            
            if cod_tramitacoes:
                try:
                    import tasks
                    portal_url = str(self.context.absolute_url())
                    user_id = self._get_cod_usuario()
                    
                    # Dispara geração de PDF em lote
                    try:
                        task_kwargs = {
                            'tipo': tipo,
                            'cod_tramitacoes': cod_tramitacoes,
                            'portal_url': portal_url,
                            'site_path': 'sagl'
                        }
                        if user_id:
                            task_kwargs['user_id'] = str(user_id)
                        
                        task_result = tasks.gerar_pdf_despacho_lote_task.apply_async(kwargs=task_kwargs)
                        task_id = task_result.id if hasattr(task_result, 'id') else getattr(task_result, 'task_id', None)
                        
                        if task_id:
                            task_pdf_lote = {
                                'task_id': task_id,
                                'monitor_url': f"{portal_url}/@@tramitacao_despacho_pdf_lote_status?task_id={task_id}",
                                'total': len(cod_tramitacoes)
                            }
                            logger.info(f"TramitacaoLoteSalvarView - Task PDF lote disparada: {task_id}")
                    except Exception as e:
                        logger.error(f"TramitacaoLoteSalvarView - Erro ao disparar geração de PDF em lote: {e}", exc_info=True)
                    
                    # Se houver arquivo PDF anexado, dispara junção em lote
                    if arquivo_pdf and hasattr(arquivo_pdf, 'read'):
                        try:
                            import base64
                            
                            arquivo_pdf.seek(0)
                            arquivo_bytes = arquivo_pdf.read()
                            arquivo_base64 = base64.b64encode(arquivo_bytes).decode('utf-8')
                            
                            task_kwargs = {
                                'tipo': tipo,
                                'cod_tramitacoes': cod_tramitacoes,
                                'arquivo_pdf_base64': arquivo_base64,
                                'nome_arquivo': getattr(arquivo_pdf, 'filename', 'anexo.pdf'),
                                'portal_url': portal_url,
                                'site_path': 'sagl'
                            }
                            if user_id:
                                task_kwargs['user_id'] = str(user_id)
                            
                            task_result = tasks.juntar_pdfs_lote_task.apply_async(kwargs=task_kwargs)
                            task_id = task_result.id if hasattr(task_result, 'id') else getattr(task_result, 'task_id', None)
                            
                            if task_id:
                                task_anexo_lote = {
                                    'task_id': task_id,
                                    'monitor_url': f"{portal_url}/@@tramitacao_anexar_arquivo_lote_status?task_id={task_id}",
                                    'total': len(cod_tramitacoes)
                                }
                                logger.info(f"TramitacaoLoteSalvarView - Task anexo lote disparada: {task_id}")
                        except Exception as e:
                            logger.error(f"TramitacaoLoteSalvarView - Erro ao disparar junção de anexo em lote: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"TramitacaoLoteSalvarView - Erro ao importar tasks: {e}", exc_info=True)
            
            # Prepara resposta
            resposta = {
                'total': total_retorno,
                'total_processos': total_processos_retorno,
                # ✅ Flags para atualização da interface após tramitação em lote
                'reload_contadores': True,  # Indica que os contadores devem ser recarregados
                'reload_listas': True,  # Indica que as listas das caixas devem ser recarregadas
                'atualizar_caixas': True,  # Flag para indicar que as caixas devem ser atualizadas
                'reload_interface': True  # Flag para indicar que a interface deve ser recarregada
            }
            
            if erros_retorno:
                resposta['erros'] = erros_retorno
            
            # Adiciona tasks se disponíveis
            if task_pdf_lote:
                resposta['task_pdf_lote'] = task_pdf_lote
            if task_anexo_lote:
                resposta['task_anexo_lote'] = task_anexo_lote
            
            if len(erros_retorno) > 0:
                return self._resposta_sucesso(
                    f'{total_retorno} de {total_processos_retorno} processo(s) tramitado(s) com sucesso. Alguns processos apresentaram erros.',
                    resposta
                )
            
            return self._resposta_sucesso(
                f'{total_retorno} processo(s) tramitado(s) com sucesso',
                resposta
            )
        
        except Exception as e:
            # ❌ NÃO chame session.rollback() ou Session.remove() - z3c.saconfig gerencia isso automaticamente
            # O Zope fará rollback automaticamente através do transaction manager
            logger.error(f"TramitacaoLoteSalvarView - Erro capturado: {e}", exc_info=True)
            return self._tratar_erro(e, "TramitacaoLoteSalvarView")


class TramitacaoTestCodUsuarioView(GrokView, TramitacaoAPIBase):
    """View de teste para verificar se _get_cod_usuario retorna corretamente"""
    
    context(Interface)
    name('tramitacao_test_cod_usuario_json')
    require('zope2.View')
    
    def render(self):
        """Testa o método _get_cod_usuario e retorna informações de debug"""
        resultado = {
            'sucesso': False,
            'cod_usuario': None,
            'col_username': None,
            'usuario_encontrado': False,
            'erro': None,
            'debug_info': {}
        }
        
        try:
            # Debug: informações sobre o request
            resultado['debug_info']['request_info'] = {
                'has_AUTHENTICATED_USER': hasattr(self.request, 'AUTHENTICATED_USER'),
                'request_method': getattr(self.request, 'method', 'N/A'),
                'request_url': getattr(self.request, 'URL', 'N/A'),
                'request_headers': dict(getattr(self.request, 'environ', {}).get('HTTP_', {})) if hasattr(self.request, 'environ') else 'N/A'
            }
            
            # Obtém username do usuário autenticado
            try:
                col_username = self.request.AUTHENTICATED_USER.getUserName()
                resultado['col_username'] = col_username
                resultado['debug_info']['username_obtido'] = True
                resultado['debug_info']['AUTHENTICATED_USER_type'] = str(type(self.request.AUTHENTICATED_USER))
            except Exception as e:
                resultado['erro'] = f'Erro ao obter username: {str(e)}'
                resultado['debug_info']['username_obtido'] = False
                resultado['debug_info']['username_error'] = str(e)
                return self._resposta_json(resultado)
            
            # Chama o método _get_cod_usuario
            cod_usuario = self._get_cod_usuario()
            resultado['cod_usuario'] = cod_usuario
            
            if cod_usuario:
                resultado['sucesso'] = True
                resultado['usuario_encontrado'] = True
                resultado['debug_info']['mensagem'] = 'Usuário encontrado com sucesso'
                
                # Verifica se o usuário existe no banco (leitura apenas)
                with db_session_readonly() as session:
                    usuario = session.query(Usuario).filter(
                        Usuario.cod_usuario == cod_usuario
                    ).first()
                    if usuario:
                        # Extrai dados antes de expungar
                        cod_user = usuario.cod_usuario
                        col_user = usuario.col_username
                        ind_exc = usuario.ind_excluido
                        ind_ativ = usuario.ind_ativo
                        session.expunge_all()
                        
                        resultado['debug_info']['usuario_info'] = {
                            'cod_usuario': cod_user,
                            'col_username': col_user,
                            'ind_excluido': ind_exc,
                            'ind_ativo': ind_ativ
                        }
            else:
                resultado['sucesso'] = False
                resultado['erro'] = 'Usuário não encontrado no banco de dados'
                resultado['debug_info']['mensagem'] = 'Método retornou None'
                
                # Tenta verificar se o usuário existe mas não está ativo ou está excluído (leitura apenas)
                with db_session_readonly() as session:
                    usuario = session.query(Usuario).filter(
                        Usuario.col_username == col_username
                    ).first()
                    if usuario:
                        # Extrai dados antes de expungar
                        cod_user = usuario.cod_usuario
                        ind_exc = usuario.ind_excluido
                        ind_ativ = usuario.ind_ativo
                        session.expunge_all()
                        
                        resultado['debug_info']['usuario_existe_mas'] = {
                            'cod_usuario': cod_user,
                            'ind_excluido': ind_exc,
                            'ind_ativo': ind_ativ,
                            'motivo': 'Usuário existe mas está excluído ou inativo' if (ind_exc == 1 or ind_ativ == 0) else 'Usuário existe mas não foi retornado pelo método'
                        }
        
        except Exception as e:
            resultado['erro'] = f'Erro inesperado: {str(e)}'
            resultado['debug_info']['exception'] = str(e)
            logger.error(f"Erro ao testar _get_cod_usuario: {e}", exc_info=True)
        
        return self._resposta_json(resultado)


class TramitacaoIndividualSalvarView(GrokView, TramitacaoAPIBase):
    """View para salvar tramitação individual (rascunho ou envio)"""
    
    context(Interface)
    name('tramitacao_individual_salvar_json')
    require('zope2.View')
    
    def render(self):
        """Salva tramitação individual"""
        try:
            # Validações iniciais
            # IMPORTANTE: Normaliza o parâmetro acao para garantir comparação correta
            acao_raw = self._obter_parametro('acao')
            if acao_raw:
                acao = str(acao_raw).strip().lower()
            else:
                acao = 'enviar'  # Padrão é enviar se não especificado
            
            # Normaliza valores conhecidos
            if acao in ['salvar', 'salvar_rascunho', 'rascunho']:
                acao = 'salvar_rascunho'
            elif acao in ['enviar', 'enviar_tramitacao', 'tramitar']:
                acao = 'enviar'
            else:
                # Se não reconhecer, assume enviar (comportamento padrão)
                logger.warning(f"TramitacaoIndividualSalvarView - Ação desconhecida '{acao_raw}', assumindo 'enviar'")
                acao = 'enviar'
            
            tipo = self._obter_tipo_tramitacao()
            cod_entidade = self._obter_cod_entidade()
            cod_usuario = self._get_cod_usuario()
            
            if not cod_usuario:
                return self._resposta_erro('Usuário não autenticado')
            
            # Valida dados obrigatórios ANTES de abrir sessão
            cod_unid_tram_local = self._obter_parametro('lst_cod_unid_tram_local')
            cod_unid_tram_dest = self._obter_parametro('lst_cod_unid_tram_dest')
            cod_status = self._obter_parametro('lst_cod_status')
            
            if not cod_unid_tram_local:
                return self._resposta_erro('Unidade de origem é obrigatória')
            if not cod_unid_tram_dest:
                return self._resposta_erro('Unidade de destino é obrigatória')
            if not cod_status:
                return self._resposta_erro('Status é obrigatório')
            
            # Prepara dados da tramitação
            cod_tramitacao = self._obter_parametro('hdn_cod_tramitacao', '')
            dados = {
                'cod_unid_tram_local': cod_unid_tram_local,
                'cod_usuario_local': cod_usuario,
                'cod_unid_tram_dest': cod_unid_tram_dest,
                'cod_usuario_dest': self._obter_parametro('lst_cod_usuario_dest') or None,
                'cod_status': cod_status,
                'txt_tramitacao': self._obter_parametro('txa_txt_tramitacao', ''),
                'dat_fim_prazo': self._parse_date(self._obter_parametro('txt_dat_fim_prazo'))
            }
            
            # Ind_urgencia apenas para processos legislativos (MATERIA)
            if tipo == 'MATERIA':
                dados['ind_urgencia'] = 1 if self._obter_parametro('rad_ind_urgencia') == '1' else 0
            
            # Valida PDF ANTES de abrir sessão (validação simples)
            arquivo_pdf = self._obter_parametro('file_nom_arquivo')
            if arquivo_pdf:
                self._validar_pdf_simples(arquivo_pdf)
            
            # Processa ação (salvar rascunho ou enviar)
            # ❌ NUNCA use db_session() para escrita - ele gerencia transação internamente
            # ✅ Use get_session() para obter uma sessão fresca (evita ResourceClosedError)
            session = get_session()  # Garante sessão fresca sem DataManager antigo
            session_id = id(session)
            
            from .services import TramitacaoService
            service = TramitacaoService(session)
                
            cod_tramitacao_int = int(cod_tramitacao) if cod_tramitacao else None
            cod_entidade_int = validar_codigo_entidade(cod_entidade)
            
            if acao == 'salvar_rascunho':
                # ✅ CRÍTICO: Detecta alterações ANTES de salvar (para poder comparar com dados originais)
                # Obtém opção de PDF (G=Gerar, S=Anexar, M=Manter)
                opcao_pdf = self._obter_parametro('radTI', 'G')
                
                # ✅ CRÍTICO: Atualiza dat_tramitacao para data atual ao editar rascunho
                from datetime import datetime as dt
                dados['dat_tramitacao'] = dt.now()
                
                # Detecta se houve alterações nos campos (apenas se for edição de rascunho existente)
                houve_alteracao = False
                dados_atuais = None
                if cod_tramitacao_int:  # Se é edição (já existe cod_tramitacao)
                    # Busca dados atuais da tramitação para comparar (ANTES de salvar)
                    dados_atuais = self._obter_dados_tramitacao_form_em_sessao(session, tipo, str(cod_tramitacao_int))
                    if dados_atuais:
                        # Prepara dados novos no mesmo formato dos dados atuais para comparação
                        dados_para_comparar = {
                            'cod_unid_tram_local': int(dados.get('cod_unid_tram_local')) if dados.get('cod_unid_tram_local') else None,
                            'cod_unid_tram_dest': int(dados.get('cod_unid_tram_dest')) if dados.get('cod_unid_tram_dest') else None,
                            'cod_usuario_dest': int(dados.get('cod_usuario_dest')) if dados.get('cod_usuario_dest') else None,
                            'cod_status': int(dados.get('cod_status')) if dados.get('cod_status') else None,
                            'txt_tramitacao': str(dados.get('txt_tramitacao', '')),
                            'dat_fim_prazo': dados.get('dat_fim_prazo'),
                            'dat_tramitacao': dados['dat_tramitacao']  # ✅ Inclui dat_tramitacao atualizado
                        }
                        # Normaliza dat_fim_prazo para string se for datetime
                        if dados_para_comparar.get('dat_fim_prazo'):
                            dat_fim = dados_para_comparar['dat_fim_prazo']
                            if isinstance(dat_fim, dt):
                                dados_para_comparar['dat_fim_prazo'] = dat_fim.strftime('%d/%m/%Y')
                            elif hasattr(dat_fim, 'strftime'):
                                dados_para_comparar['dat_fim_prazo'] = dat_fim.strftime('%d/%m/%Y')
                        
                        if tipo == 'MATERIA':
                            dados_para_comparar['ind_urgencia'] = int(dados.get('ind_urgencia', 0))
                        
                        logger.debug(f"TramitacaoIndividualSalvarView - Comparando dados: novos={dados_para_comparar}, atuais={dados_atuais}")
                        houve_alteracao = self._detectar_alteracoes_tramitacao(dados_para_comparar, dados_atuais, tipo)
                        logger.debug(f"TramitacaoIndividualSalvarView - Detecção de alterações: houve_alteracao={houve_alteracao}, opcao_pdf={opcao_pdf}, cod_tramitacao={cod_tramitacao_int}")
                    else:
                        logger.warning(f"TramitacaoIndividualSalvarView - Não foi possível obter dados atuais da tramitação {cod_tramitacao_int} para comparação")
                
                # Agora salva o rascunho (após detectar alterações)
                cod_tramitacao_salva = service.salvar_rascunho(
                    tipo=tipo,
                    cod_entidade=cod_entidade_int,
                    dados=dados,
                    cod_tramitacao=cod_tramitacao_int
                )
                
                # Extrai código ANTES de construir resposta
                if cod_tramitacao_salva is None:
                    raise ValueError("cod_tramitacao não foi gerado")
                cod_tramitacao_retorno = int(cod_tramitacao_salva)
                
                # ✅ CORRETO: Invalidação de cache via afterCommitHook APÓS o commit
                # Não executa durante a transação, apenas após commit bem-sucedido
                import transaction
                from .cache import invalidate_cache_contadores
                transaction.get().addAfterCommitHook(
                    lambda success, *args:
                        success and invalidate_cache_contadores(cod_usuario, None)
                )
                
                # ✅ CRÍTICO: Decide se deve gerar PDF ANTES de configurar hook
                # Dispara geração de PDF para rascunho APENAS se:
                # 1. Opção for "Gerar" (G) E houve alteração nos campos, OU
                # 2. É uma nova tramitação (não é edição) e opção não é "Manter"
                portal_url = str(self.context.absolute_url())
                user_id = cod_usuario
                deve_gerar_pdf = False
                if cod_tramitacao_retorno:
                    if cod_tramitacao_int:  # É edição
                        deve_gerar_pdf = (opcao_pdf == 'G' and houve_alteracao)
                        logger.debug(f"TramitacaoIndividualSalvarView - Decisão PDF (edição): opcao_pdf={opcao_pdf}, houve_alteracao={houve_alteracao}, deve_gerar_pdf={deve_gerar_pdf}, cod_tramitacao={cod_tramitacao_retorno}")
                    else:  # É novo rascunho
                        deve_gerar_pdf = (opcao_pdf != 'M')
                        logger.debug(f"TramitacaoIndividualSalvarView - Decisão PDF (novo rascunho): opcao_pdf={opcao_pdf}, deve_gerar_pdf={deve_gerar_pdf}, cod_tramitacao={cod_tramitacao_retorno}")
                
                # ✅ CRÍTICO: Dispara task PDF via afterCommitHook APÓS o commit
                # Isso garante que os dados já estejam persistidos quando a task for executada
                # Captura valores necessários ANTES de usar no hook
                task_pdf = None
                task_anexo = None
                if deve_gerar_pdf:
                    # Captura valores primitivos para usar no hook
                    cod_tram_retorno = cod_tramitacao_retorno
                    tipo_tram = tipo
                    portal_url_hook = str(self.context.absolute_url())
                    user_id_hook = cod_usuario
                    opcao_pdf_hook = opcao_pdf
                    houve_alteracao_hook = houve_alteracao
                    
                    # ✅ CRÍTICO: Captura dados da tramitação do request ANTES do commit
                    # para passar diretamente para a task (evita buscar dados antigos do banco)
                    dados_tramitacao_para_pdf = {
                        'cod_tramitacao': cod_tramitacao_retorno,
                        'cod_unid_tram_local': int(dados.get('cod_unid_tram_local')) if dados.get('cod_unid_tram_local') else None,
                        'cod_usuario_local': int(dados.get('cod_usuario_local')) if dados.get('cod_usuario_local') else None,
                        'cod_unid_tram_dest': int(dados.get('cod_unid_tram_dest')) if dados.get('cod_unid_tram_dest') else None,
                        'cod_usuario_dest': int(dados.get('cod_usuario_dest')) if dados.get('cod_usuario_dest') else None,
                        'cod_status': int(dados.get('cod_status')) if dados.get('cod_status') else None,
                        'txt_tramitacao': str(dados.get('txt_tramitacao', '')),
                        'dat_fim_prazo': dados.get('dat_fim_prazo'),
                        'dat_tramitacao': dados.get('dat_tramitacao')  # ✅ Inclui dat_tramitacao atualizado
                    }
                    if dados.get('ind_urgencia') is not None:
                        dados_tramitacao_para_pdf['ind_urgencia'] = int(dados.get('ind_urgencia', 0))
                    if dados_tramitacao_para_pdf.get('dat_fim_prazo'):
                        dat_fim = dados_tramitacao_para_pdf['dat_fim_prazo']
                        if isinstance(dat_fim, dt):
                            dados_tramitacao_para_pdf['dat_fim_prazo'] = dat_fim.strftime('%d/%m/%Y')
                        elif hasattr(dat_fim, 'strftime'):
                            dados_tramitacao_para_pdf['dat_fim_prazo'] = dat_fim.strftime('%d/%m/%Y')
                    # ✅ Normaliza dat_tramitacao para string (JSON serializable)
                    if dados_tramitacao_para_pdf.get('dat_tramitacao'):
                        dat_tram = dados_tramitacao_para_pdf['dat_tramitacao']
                        if isinstance(dat_tram, dt):
                            dados_tramitacao_para_pdf['dat_tramitacao'] = dat_tram.strftime('%d/%m/%Y')
                        elif hasattr(dat_tram, 'strftime'):
                            dados_tramitacao_para_pdf['dat_tramitacao'] = dat_tram.strftime('%d/%m/%Y')
                        else:
                            dados_tramitacao_para_pdf['dat_tramitacao'] = str(dat_tram)
                    
                    # Serializa dados para JSON (para passar via task)
                    import json as json_module
                    dados_tramitacao_json = json_module.dumps(dados_tramitacao_para_pdf, ensure_ascii=False)
                    
                    def disparar_task_pdf_apos_commit(success, cod_tramitacao, tipo_tramitacao, portal_url_val, user_id_val, dados_json):
                        if not success:
                            return
                        
                        try:
                            import tasks
                            task_kwargs = {
                                'tipo': tipo_tramitacao,
                                'cod_tramitacao': cod_tramitacao,
                                'portal_url': portal_url_val,
                                'site_path': 'sagl',
                                'dados_tramitacao_json': dados_json  # ✅ Passa dados diretamente do request
                            }
                            if user_id_val:
                                task_kwargs['user_id'] = str(user_id_val)
                            
                            task_result = tasks.gerar_pdf_despacho_task.apply_async(kwargs=task_kwargs)
                            task_id = task_result.id if hasattr(task_result, 'id') else getattr(task_result, 'task_id', None)
                            
                            if task_id:
                                logger.debug(f"TramitacaoIndividualSalvarView - Task PDF disparada APÓS commit com dados do request: task_id={task_id} para cod_tramitacao={cod_tramitacao}")
                            else:
                                logger.debug(f"TramitacaoIndividualSalvarView - Task PDF não retornou task_id após commit para cod_tramitacao={cod_tramitacao}")
                        except Exception as e:
                            logger.error(f"TramitacaoIndividualSalvarView - Erro ao disparar task PDF após commit: {e}", exc_info=True)
                    
                    transaction.get().addAfterCommitHook(
                        lambda success, *args:
                            disparar_task_pdf_apos_commit(success, cod_tram_retorno, tipo_tram, portal_url_hook, user_id_hook, dados_tramitacao_json)
                    )
                
                # ✅ CRÍTICO: NÃO calcula contadores DURANTE a transação
                # O cálculo de contadores deve ser feito APÓS o commit (via afterCommitHook)
                # ou deixar o frontend atualizar automaticamente (reload_contadores=True na resposta)
                #
                # ❌ ERRADO: Calcular contadores antes do retorno fecha a transação
                # ✅ CERTO: Frontend recarrega contadores automaticamente via reload_contadores=True
                #
                # Por isso, retornamos contadores vazios ou deixamos o frontend calcular
                # O frontend já tem a flag reload_contadores=True para atualizar
                contadores = {
                    'entrada': 0,  # Frontend recarrega via reload_contadores=True
                    'rascunhos': 0,
                    'enviados': 0
                }
                
                # Extrai dados diretamente dos parâmetros fornecidos
                # ✅ CORRETO: NÃO fazemos nova consulta para evitar problemas com a sessão
                # Todos os dados vêm dos parâmetros já validados
                from datetime import datetime as dt
                
                dados_tramitacao = {
                    'cod_tramitacao': cod_tramitacao_retorno,
                    'cod_unid_tram_local': int(dados.get('cod_unid_tram_local')) if dados.get('cod_unid_tram_local') else None,
                    'cod_usuario_local': int(dados.get('cod_usuario_local')) if dados.get('cod_usuario_local') else None,
                    'cod_unid_tram_dest': int(dados.get('cod_unid_tram_dest')) if dados.get('cod_unid_tram_dest') else None,
                    'cod_usuario_dest': int(dados.get('cod_usuario_dest')) if dados.get('cod_usuario_dest') else None,
                    'cod_status': int(dados.get('cod_status')) if dados.get('cod_status') else None,
                    'txt_tramitacao': str(dados.get('txt_tramitacao', '')),
                    'ind_ult_tramitacao': 0  # Rascunho não é última tramitação
                }
                
                if dados.get('ind_urgencia'):
                    dados_tramitacao['ind_urgencia'] = int(dados.get('ind_urgencia'))
                
                if dados.get('dat_fim_prazo'):
                    dat_fim = dados['dat_fim_prazo']
                    if isinstance(dat_fim, dt):
                        dados_tramitacao['dat_fim_prazo'] = dat_fim.strftime('%d/%m/%Y')
                    elif hasattr(dat_fim, 'strftime'):
                        dados_tramitacao['dat_fim_prazo'] = dat_fim.strftime('%d/%m/%Y')
                    else:
                        dados_tramitacao['dat_fim_prazo'] = str(dat_fim)
                
                # Constrói resposta com dados já extraídos
                # ✅ CORRETO: Todos os dados estão em memória - nenhum acesso à sessão após isso
                resposta = {
                    'cod_tramitacao': cod_tramitacao_retorno,
                    'mensagem': 'Rascunho salvo com sucesso',
                    'dados_tramitacao': dados_tramitacao,
                    'contadores': contadores,
                    'atualizar_caixas': True,  # Flag para indicar que as caixas devem ser atualizadas
                    'reload_interface': True,  # Flag para indicar que a interface deve ser recarregada
                    'acao': 'rascunho_salvo',  # Indica qual ação foi executada
                    'reload_contadores': True,  # Indica que os contadores devem ser recarregados
                    'reload_listas': True  # Indica que as listas das caixas devem ser recarregadas
                }
                
                # Prepara task_pdf e task_anexo para resposta (se necessário)
                try:
                    if deve_gerar_pdf:
                        logger.info(f"TramitacaoIndividualSalvarView - PDF será gerado APÓS commit para tramitação {cod_tramitacao_retorno} (opcao={opcao_pdf}, alteracao={houve_alteracao})")
                        # A task será disparada via afterCommitHook (configurado acima)
                        # Não criamos task_pdf na resposta pois será assíncrono
                    else:
                        if opcao_pdf == 'M':
                            logger.info(f"TramitacaoIndividualSalvarView - Opção 'Manter' selecionada (rascunho), não gerando novo PDF para cod_tramitacao={cod_tramitacao_retorno}")
                        elif cod_tramitacao_int and not houve_alteracao and opcao_pdf == 'G':
                            # Situação esperada: edição sem alteração com opção G - não precisa gerar PDF
                            logger.info(f"TramitacaoIndividualSalvarView - Edição sem alteração detectada, não gerando novo PDF para cod_tramitacao={cod_tramitacao_retorno} (opcao={opcao_pdf}, alteracao={houve_alteracao})")
                        elif cod_tramitacao_int and opcao_pdf != 'G':
                            logger.info(f"TramitacaoIndividualSalvarView - Opção não é 'G' (opcao={opcao_pdf}), não gerando novo PDF para cod_tramitacao={cod_tramitacao_retorno}")
                        elif not cod_tramitacao_retorno:
                            logger.warning(f"TramitacaoIndividualSalvarView - cod_tramitacao_retorno não disponível para disparar task PDF")
                        else:
                            logger.warning(f"TramitacaoIndividualSalvarView - PDF não será gerado por motivo desconhecido: opcao_pdf={opcao_pdf}, houve_alteracao={houve_alteracao}, cod_tramitacao_int={cod_tramitacao_int}, cod_tramitacao_retorno={cod_tramitacao_retorno}")
                    
                    # Se houver arquivo PDF anexado, dispara junção também para rascunhos (apenas se opção não for "Manter")
                    # Se opção for "Manter", não junta anexo também
                    if opcao_pdf != 'M' and arquivo_pdf and hasattr(arquivo_pdf, 'read'):
                        try:
                            # ✅ Necessário para usar tasks.juntar_pdfs_task (Celery)
                            import tasks
                            import base64
                            
                            arquivo_pdf.seek(0)
                            arquivo_bytes = arquivo_pdf.read()
                            arquivo_base64 = base64.b64encode(arquivo_bytes).decode('utf-8')
                            
                            task_kwargs = {
                                'tipo': tipo,
                                'cod_tramitacao': cod_tramitacao_retorno,
                                'arquivo_pdf_base64': arquivo_base64,
                                'nome_arquivo': getattr(arquivo_pdf, 'filename', 'anexo.pdf'),
                                'portal_url': portal_url,
                                'site_path': 'sagl'
                            }
                            if user_id:
                                task_kwargs['user_id'] = str(user_id)
                            
                            task_result = tasks.juntar_pdfs_task.apply_async(kwargs=task_kwargs)
                            task_id = task_result.id if hasattr(task_result, 'id') else getattr(task_result, 'task_id', None)
                            
                            if task_id:
                                task_anexo = {
                                    'task_id': task_id,
                                    'monitor_url': f"{portal_url}/@@tramitacao_anexar_arquivo_status?task_id={task_id}"
                                }
                                logger.info(f"TramitacaoIndividualSalvarView - Task anexo (rascunho) disparada: {task_id}")
                        except Exception as e:
                            logger.error(f"TramitacaoIndividualSalvarView - Erro ao disparar junção de anexo (rascunho): {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"TramitacaoIndividualSalvarView - Erro ao importar tasks (rascunho): {e}", exc_info=True)
                
                # Adiciona task_pdf e task_anexo na resposta se disponíveis
                if task_pdf:
                    resposta['task_pdf'] = task_pdf
                else:
                    logger.debug(f"TramitacaoIndividualSalvarView - task_pdf não foi criado, não será adicionado à resposta")
                
                if task_anexo:
                    resposta['task_anexo'] = task_anexo
                    logger.info(f"TramitacaoIndividualSalvarView - task_anexo adicionado à resposta: {task_anexo}")
                
                # ✅ Adiciona link_pdf_despacho atualizado com timestamp quando PDF for gerado/atualizado
                # Isso permite que o frontend atualize o link do botão PDF
                if deve_gerar_pdf:
                    try:
                        import time
                        # Constrói URL base do PDF
                        if tipo == 'MATERIA':
                            pdf_path = f"/sapl_documentos/materia/tramitacao/{cod_tramitacao_retorno}_tram.pdf"
                        else:
                            pdf_path = f"/sapl_documentos/administrativo/tramitacao/{cod_tramitacao_retorno}_tram.pdf"
                        
                        base_url = f"{portal_url.rstrip('/')}{pdf_path}"
                        timestamp = int(time.time() * 1000)  # Timestamp em milissegundos
                        separator = '&' if '?' in base_url else '?'
                        link_pdf_despacho = f"{base_url}{separator}_t={timestamp}"
                        resposta['link_pdf_despacho'] = link_pdf_despacho
                        resposta['pdf_atualizado'] = True  # Flag para indicar que PDF foi atualizado
                        resposta['update_pdf_link'] = True  # Flag para indicar que deve atualizar o link
                        # ✅ Adiciona código JavaScript inline que será executado automaticamente
                        # Isso garante que o link seja atualizado mesmo se o interceptor AJAX não funcionar
                        resposta['exec_script'] = f'''
                            (function() {{
                                var btnPdf = document.getElementById('btn_visualizar_pdf_tramitacao');
                                if (btnPdf) {{
                                    btnPdf.href = '{link_pdf_despacho}';
                                    btnPdf.setAttribute('data-link-pdf', '{link_pdf_despacho}');
                                    console.log('[Tramitacao] Link PDF atualizado:', '{link_pdf_despacho}');
                                }} else {{
                                    // Tenta novamente após um pequeno delay (caso o botão ainda não exista)
                                    setTimeout(function() {{
                                        var btnPdf = document.getElementById('btn_visualizar_pdf_tramitacao');
                                        if (btnPdf) {{
                                            btnPdf.href = '{link_pdf_despacho}';
                                            btnPdf.setAttribute('data-link-pdf', '{link_pdf_despacho}');
                                            console.log('[Tramitacao] Link PDF atualizado (retry):', '{link_pdf_despacho}');
                                        }}
                                    }}, 100);
                                }}
                            }})();
                        '''
                        logger.debug(f"TramitacaoIndividualSalvarView - Link PDF atualizado na resposta: {link_pdf_despacho}")
                    except Exception as e:
                        logger.warning(f"TramitacaoIndividualSalvarView - Erro ao construir link PDF atualizado: {e}")
                
                # Garante que resposta tenha sucesso: true para compatibilidade com frontend
                resposta['sucesso'] = True
                
                return self._resposta_sucesso('Rascunho salvo com sucesso', resposta)
            else:  # enviar
                # Envia tramitação
                cod_tramitacao_salva = service.enviar_tramitacao(
                    tipo=tipo,
                    cod_entidade=cod_entidade_int,
                    dados=dados,
                    cod_tramitacao=cod_tramitacao_int
                )
                logger.info(f"TramitacaoIndividualSalvarView - Tramitação enviada: cod_tramitacao={cod_tramitacao_salva}")
                
                # Extrai código ANTES de retornar
                cod_tramitacao_retorno = int(cod_tramitacao_salva)
                
                # ✅ CRÍTICO: Marca sessão como alterada IMEDIATAMENTE após enviar_tramitacao
                # IMPORTANTE: Isso deve ser feito ANTES de qualquer outra operação que use a sessão
                # para garantir que a transação seja registrada no transaction manager
                # ✅ CORRETO: SEM keep_session=True - a sessão deve morrer junto com a transação
                mark_changed(session)
                logger.info(f"TramitacaoIndividualSalvarView - Tramitação enviada - sessão id: {session_id}")
                
                # ✅ CORRETO: Side-effects (e-mails) via afterCommitHook APÓS o commit
                # ❌ ERRADO: Não enviar e-mails ANTES do commit (tramitação não estará visível)
                # ✅ CERTO: E-mails via afterCommitHook - só executa APÓS commit bem-sucedido
                import transaction
                from .notifications.email_sender import TramitacaoEmailSender
                
                # Captura valores primitivos E contexto ANTES de usar no hook
                cod_ent = cod_entidade_int
                cod_tram = cod_tramitacao_retorno
                tipo_materia = tipo
                context = self.context  # Captura contexto antes do hook
                
                # Função que será executada APÓS o commit bem-sucedido
                # ✅ CRÍTICO: Esta função roda APÓS o commit da transação original
                # Precisamos criar uma NOVA transação para as notificações
                def enviar_notificacoes_after_commit(success, cod_entidade, cod_tramitacao, tipo_tram, context_ref):
                    if not success:
                        return
                    
                    # ✅ CORRETO: Cria uma NOVA transação para as notificações
                    # A transação original já foi commitada, então iniciamos uma nova transação
                    # ANTES de criar a sessão, para que a sessão se junte à nova transação ativa
                    try:
                        import transaction as transaction_module
                        from openlegis.sagl.db_session import db_session_readonly
                        from .notifications.email_sender import TramitacaoEmailSender
                        
                        # ✅ CRÍTICO: Inicia uma NOVA transação ANTES de criar a sessão
                        # Isso garante que a sessão se junte à transação ativa, não à commitada
                        txn = transaction_module.begin()
                        
                        try:
                            # Cria sessão readonly - agora se junta à NOVA transação ativa
                            with db_session_readonly() as session_notif:
                                sender = TramitacaoEmailSender(session_notif, context_ref)
                                
                                if tipo_tram == 'MATERIA':
                                    # Notifica autores
                                    try:
                                        resultado = sender.notificar_autores_materia(cod_entidade)
                                        logger.info(f"TramitacaoIndividualSalvarView - Notificação para autores enviada (matéria {cod_entidade}): {resultado}")
                                    except Exception as e:
                                        logger.warning(f"TramitacaoIndividualSalvarView - Erro ao notificar autores: {e}", exc_info=True)
                                    
                                    # Notifica acompanhantes + destino
                                    try:
                                        resultado = sender.notificar_acompanhantes_materia(cod_entidade, cod_tramitacao)
                                        logger.info(f"TramitacaoIndividualSalvarView - Notificação para acompanhantes enviada (matéria {cod_entidade}): {resultado}")
                                    except Exception as e:
                                        logger.warning(f"TramitacaoIndividualSalvarView - Erro ao notificar acompanhantes: {e}", exc_info=True)
                                else:  # DOCUMENTO
                                    # Notifica destino
                                    try:
                                        resultado = sender.notificar_destino_documento(cod_entidade, cod_tramitacao)
                                        logger.info(f"TramitacaoIndividualSalvarView - Notificação para destino enviada (documento {cod_entidade}): {resultado}")
                                    except Exception as e:
                                        logger.warning(f"TramitacaoIndividualSalvarView - Erro ao notificar destino: {e}", exc_info=True)
                            
                            # ✅ Commit da nova transação das notificações
                            txn.commit()
                        except Exception:
                            # ✅ Abort em caso de erro
                            txn.abort()
                            raise
                    except Exception as e:
                        logger.error(f"TramitacaoIndividualSalvarView - Erro ao processar notificações em afterCommitHook: {e}", exc_info=True)
                
                # Adiciona hook que será executado APÓS o commit bem-sucedido
                transaction.get().addAfterCommitHook(
                    enviar_notificacoes_after_commit,
                    args=(cod_ent, cod_tram, tipo_materia, context)
                )
                
                # ✅ CORRETO: Invalidação de cache via afterCommitHook APÓS o commit
                # Não executa durante a transação, apenas após commit bem-sucedido
                from .cache import invalidate_cache_contadores
                transaction.get().addAfterCommitHook(
                    lambda success, *args:
                        success and invalidate_cache_contadores(cod_usuario, None)
                )
                
                # ✅ CRÍTICO: NÃO calcula contadores DURANTE a transação
                # O cálculo de contadores deve ser feito APÓS o commit (via afterCommitHook)
                # ou deixar o frontend atualizar automaticamente (reload_contadores=True na resposta)
                # 
                # ❌ ERRADO: Calcular contadores antes do retorno fecha a transação
                # ✅ CERTO: Frontend recarrega contadores automaticamente via reload_contadores=True
                #
                # Por isso, retornamos contadores vazios ou deixamos o frontend calcular
                # O frontend já tem a flag reload_contadores=True para atualizar
                contadores = {
                    'entrada': 0,  # Frontend recarrega via reload_contadores=True
                    'rascunhos': 0,
                    'enviados': 0
                }
                
                # ✅ IMPORTANTE: No ENVIO de tramitação, NÃO gera novo PDF
                # A geração de PDF deve ocorrer apenas no SALVAMENTO (rascunho)
                # No envio, a tramitação já deve ter o PDF gerado anteriormente (se foi salvo como rascunho)
                # ou não precisa de PDF (envio direto sem rascunho prévio)
                #
                # POR ISSO: No envio, não há geração de PDF
                task_pdf = None
                task_anexo = None
                
                # Retorna resposta - sessão permanece ativa para Zope fazer commit
                # Não fecha a sessão manualmente - deixe o Zope/transaction cuidar disso
                # IMPORTANTE: Quando é ENVIO, não inclui dados_tramitacao para evitar que frontend trate como edição
                resposta = {
                    'cod_tramitacao': cod_tramitacao_retorno,
                    'contadores': contadores,
                    'atualizar_caixas': True,  # Flag para indicar que as caixas devem ser atualizadas
                    'reload_interface': True,  # Flag para indicar que a interface deve ser recarregada
                    'acao': 'tramitacao_enviada',  # Indica qual ação foi executada
                    'tramitacao_enviada': True,  # Flag explícita para indicar que foi ENVIADO (não salvo)
                    'reload_contadores': True,  # Indica que os contadores devem ser recarregados
                    'reload_listas': True,  # Indica que as listas das caixas devem ser recarregadas
                    'fechar_formulario': True  # Flag explícita para indicar que o formulário deve ser fechado
                }
                
                # Adiciona tasks se disponíveis
                # IMPORTANTE: Mesmo com tasks, o formulário deve ser fechado quando é envio
                if task_pdf:
                    resposta['task_pdf'] = task_pdf
                if task_anexo:
                    resposta['task_anexo'] = task_anexo
                
                logger.info(f"TramitacaoIndividualSalvarView - Resposta de ENVIO preparada: cod_tramitacao={cod_tramitacao_retorno}, tramitacao_enviada=True")
                
                # ✅ CORRETO: Resposta contém APENAS tipos básicos (não objetos ORM)
                # IMPORTANTE: json.dumps() só funciona com tipos básicos
                # NÃO deve haver objetos ORM ou lazy-load na resposta
                # A resposta já está preparada com apenas tipos básicos (int, str, bool, dict simples)
                
                # Retorna resposta - sessão permanece ativa para Zope fazer commit
                # O mark_changed já foi chamado antes, garantindo que a transação está registrada
                # ✅ REGRA DE OURO: View só retorna dados simples, sem side-effects, sem exceções
                return self._resposta_sucesso('Tramitação enviada com sucesso', resposta)
        
        except ValidationError as e:
            logger.warning(f"TramitacaoIndividualSalvarView - Erro de validação: {e}")
            # ❌ NÃO chame session.rollback() ou Session.remove() - z3c.saconfig gerencia isso automaticamente
            return self._resposta_erro(str(e))
        except ValueError as e:
            logger.warning(f"TramitacaoIndividualSalvarView - Erro de valor: {e}")
            # ❌ NÃO chame session.rollback() ou Session.remove() - z3c.saconfig gerencia isso automaticamente
            return self._resposta_erro(str(e))
        except Exception as e:
            logger.error(f"TramitacaoIndividualSalvarView - Erro inesperado: {e}", exc_info=True)
            # ❌ NÃO chame session.rollback() ou Session.remove() - z3c.saconfig gerencia isso automaticamente
            return self._resposta_erro(f'Erro ao salvar tramitação: {str(e)}')
    
    def _validar_pdf_simples(self, arquivo_pdf: Any):
        """
        Valida arquivo PDF com verificações de segurança SIMPLES (sem sessão).
        
        Args:
            arquivo_pdf: Objeto de arquivo PDF ou nome do arquivo
            
        Raises:
            ValidationError: Se validação falhar
            FileValidationError: Se validação de arquivo falhar
        """
        opcao_pdf = self._obter_parametro('radTI', 'G')
        
        # Validação simples sem sessão
        if opcao_pdf == 'S':
            if not arquivo_pdf:
                raise ValidationError('Arquivo PDF é obrigatório quando selecionada a opção "Anexar"')
            
            # Valida arquivo com segurança
            try:
                info_arquivo = self._validar_arquivo_upload(arquivo_pdf, 'arquivo_pdf', extensoes_permitidas=['pdf'])
                # Sanitiza nome do arquivo
                nome_sanitizado = sanitizar_nome_arquivo(info_arquivo['nome'])
                logger.info(f"Arquivo PDF validado: {nome_sanitizado}, tamanho: {info_arquivo['tamanho']} bytes")
            except FileValidationError as e:
                raise ValidationError(str(e))
        
        # Validação mais complexa (se necessário) será feita no service usando a sessão existente
    
    def _obter_dados_tramitacao(
        self, 
        session: Any, 
        tipo: str, 
        cod_tramitacao: int
    ) -> Optional[Dict[str, Any]]:
        """
        Obtém dados completos da tramitação salva.
        
        Args:
            session: Sessão do banco de dados
            tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
            cod_tramitacao: Código da tramitação
            
        Returns:
            Dicionário com dados da tramitação ou None se erro
        """
        try:
            from openlegis.sagl.models.models import Tramitacao, TramitacaoAdministrativo
            from datetime import datetime
            
            if tipo == 'MATERIA':
                tram = session.query(Tramitacao).filter(
                    Tramitacao.cod_tramitacao == cod_tramitacao,
                    Tramitacao.ind_excluido == 0
                ).first()
            else:
                tram = session.query(TramitacaoAdministrativo).filter(
                    TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                    TramitacaoAdministrativo.ind_excluido == 0
                ).first()
            
            if not tram:
                return None
            
            # Extrai TODOS os valores imediatamente em variáveis locais
            # para evitar acesso lazy após retorno (sessão ainda ativa para escrita)
            cod_tram = tram.cod_tramitacao
            cod_unid_local = tram.cod_unid_tram_local
            cod_user_local = tram.cod_usuario_local
            cod_unid_dest = tram.cod_unid_tram_dest
            cod_user_dest = tram.cod_usuario_dest
            cod_stat = tram.cod_status
            ind_urg = getattr(tram, 'ind_urgencia', 0) if hasattr(tram, 'ind_urgencia') else 0
            txt_tram = tram.txt_tramitacao or ''
            ind_ult = tram.ind_ult_tramitacao
            
            dat_encaminha_val = getattr(tram, 'dat_encaminha', None)
            dat_encaminha_str = None
            if dat_encaminha_val:
                if isinstance(dat_encaminha_val, datetime):
                    dat_encaminha_str = dat_encaminha_val.strftime('%d/%m/%Y %H:%M')
                else:
                    dat_encaminha_str = str(dat_encaminha_val)
            
            dat_fim_prazo_val = getattr(tram, 'dat_fim_prazo', None)
            dat_fim_prazo_str = None
            if dat_fim_prazo_val:
                if isinstance(dat_fim_prazo_val, datetime):
                    dat_fim_prazo_str = dat_fim_prazo_val.strftime('%d/%m/%Y')
                elif hasattr(dat_fim_prazo_val, 'strftime'):
                    dat_fim_prazo_str = dat_fim_prazo_val.strftime('%d/%m/%Y')
                else:
                    dat_fim_prazo_str = str(dat_fim_prazo_val)
            
            # Constrói dicionário com valores já extraídos
            # Não expunge aqui pois a sessão ainda está sendo usada para escrita
            return {
                'cod_tramitacao': cod_tram,
                'cod_unid_tram_local': cod_unid_local,
                'cod_usuario_local': cod_user_local,
                'cod_unid_tram_dest': cod_unid_dest,
                'cod_usuario_dest': cod_user_dest,
                'cod_status': cod_stat,
                'ind_urgencia': ind_urg,
                'txt_tramitacao': txt_tram,
                'dat_encaminha': dat_encaminha_str,
                'dat_fim_prazo': dat_fim_prazo_str,
                'ind_ult_tramitacao': ind_ult
            }
        except Exception as e:
            logger.warning(f"Erro ao carregar dados da tramitação {cod_tramitacao}: {e}", exc_info=True)
            return None


class TramitacaoRetomarView(GrokView, TramitacaoAPIBase):
    """View para retomar tramitação enviada"""
    
    context(Interface)
    name('tramitacao_retomar_json')
    require('zope2.View')
    
    def render(self):
        """Retoma tramitação enviada"""
        try:
            from .services import TramitacaoService
            
            cod_tramitacao = self._obter_parametro('cod_tramitacao', obrigatorio=True)
            tipo = self._obter_tipo_tramitacao()
            cod_usuario = self._get_cod_usuario()
            
            if not cod_usuario:
                return self._resposta_erro('Usuário não autenticado')
            
            cod_tramitacao_int = validar_codigo_inteiro_seguro(cod_tramitacao, 'cod_tramitacao', min_valor=1)
            
            logger.info(f"TramitacaoRetomarView - Iniciando operação de escrita")
            # ✅ Use get_session() para obter uma sessão fresca (evita ResourceClosedError)
            session = get_session()  # Garante sessão fresca sem DataManager antigo
            session_id = id(session)
            service = TramitacaoService(session)
            service.retomar_tramitacao(
                tipo=tipo,
                cod_tramitacao=cod_tramitacao_int,
                cod_usuario=cod_usuario
            )
            
            # ✅ Marca sessão como alterada para o zope.sqlalchemy rastrear
            mark_changed(session)
            logger.info(f"TramitacaoRetomarView - Tramitação retomada - sessão id: {session_id}")
            logger.info(f"TramitacaoRetomarView - Sessão permanece ativa para Zope")
            # Não fecha a sessão manualmente - deixe o Zope/transaction cuidar disso
            return self._resposta_sucesso('Tramitação retomada com sucesso')
        
        except ValidationError as e:
            logger.warning(f"TramitacaoRetomarView - Erro de validação: {e}")
            # ❌ NÃO chame session.rollback() ou Session.remove() - z3c.saconfig gerencia isso automaticamente
            return self._resposta_erro(str(e))
        except Exception as e:
            logger.error(f"TramitacaoRetomarView - Erro inesperado: {e}", exc_info=True)
            # ❌ NÃO chame session.rollback() ou Session.remove() - z3c.saconfig gerencia isso automaticamente
            return self._resposta_erro(f'Erro ao retomar tramitação: {str(e)}')


class TramitacaoVisualizarView(GrokView, TramitacaoAPIBase):
    """View para registrar visualização de tramitação pelo destinatário"""
    
    context(Interface)
    name('tramitacao_visualizar_json')
    require('zope2.View')
    
    def render(self):
        """Registra visualização de tramitação"""
        try:
            from .services import TramitacaoService
            
            cod_tramitacao = self._obter_parametro('cod_tramitacao', obrigatorio=True)
            tipo = self._obter_tipo_tramitacao()
            cod_usuario = self._get_cod_usuario()
            
            if not cod_usuario:
                return self._resposta_erro('Usuário não autenticado')
            
            cod_tramitacao_int = validar_codigo_inteiro_seguro(cod_tramitacao, 'cod_tramitacao', min_valor=1)
            
            # Usa get_session() para obter uma sessão fresca
            session = get_session()
            session_id = id(session)
            service = TramitacaoService(session)
            
            visualizado = service.registrar_visualizacao(
                tipo=tipo,
                cod_tramitacao=cod_tramitacao_int,
                cod_usuario=cod_usuario
            )
            
            if visualizado:
                # Marca sessão como alterada para o zope.sqlalchemy rastrear
                mark_changed(session)
                logger.info(f"TramitacaoVisualizarView - Visualização registrada - sessão id: {session_id}")
                return self._resposta_sucesso('Visualização registrada com sucesso')
            else:
                # Não foi necessário registrar (já estava visualizada ou não se aplica)
                logger.debug(f"TramitacaoVisualizarView - Visualização não registrada (já visualizada ou não aplicável)")
                return self._resposta_sucesso('Visualização não necessária ou já registrada')
        
        except ValidationError as e:
            logger.warning(f"TramitacaoVisualizarView - Erro de validação: {e}")
            return self._resposta_erro(str(e))
        except Exception as e:
            logger.error(f"TramitacaoVisualizarView - Erro inesperado: {e}", exc_info=True)
            return self._resposta_erro(f'Erro ao registrar visualização: {str(e)}')


class TramitacaoReceberView(GrokView, TramitacaoAPIBase):
    """View para registrar recebimento de tramitação pelo destinatário"""
    
    context(Interface)
    name('tramitacao_receber_json')
    require('zope2.View')
    
    def render(self):
        """Registra recebimento de tramitação"""
        try:
            from .services import TramitacaoService
            
            cod_tramitacao = self._obter_parametro('cod_tramitacao', obrigatorio=True)
            tipo = self._obter_tipo_tramitacao()
            cod_usuario = self._get_cod_usuario()
            
            if not cod_usuario:
                return self._resposta_erro('Usuário não autenticado')
            
            cod_tramitacao_int = validar_codigo_inteiro_seguro(cod_tramitacao, 'cod_tramitacao', min_valor=1)
            
            # Usa get_session() para obter uma sessão fresca
            session = get_session()
            session_id = id(session)
            service = TramitacaoService(session)
            
            recebido = service.receber_tramitacao(
                tipo=tipo,
                cod_tramitacao=cod_tramitacao_int,
                cod_usuario=cod_usuario
            )
            
            if recebido:
                # Marca sessão como alterada para o zope.sqlalchemy rastrear
                mark_changed(session)
                logger.info(f"TramitacaoReceberView - Recebimento registrado - sessão id: {session_id}")
                return self._resposta_sucesso('Recebimento registrado com sucesso')
            else:
                # Não foi necessário registrar (já estava recebido ou não se aplica)
                logger.debug(f"TramitacaoReceberView - Recebimento não registrado (já recebido ou não aplicável)")
                return self._resposta_sucesso('Recebimento não necessário ou já registrado')
        
        except ValidationError as e:
            logger.warning(f"TramitacaoReceberView - Erro de validação: {e}")
            return self._resposta_erro(str(e))
        except Exception as e:
            logger.error(f"TramitacaoReceberView - Erro inesperado: {e}", exc_info=True)
            return self._resposta_erro(f'Erro ao registrar recebimento: {str(e)}')


class TramitacaoObterPDFDespachoView(GrokView, TramitacaoAPIBase):
    """View para obter URL do PDF do despacho da tramitação"""
    
    context(Interface)
    name('tramitacao_obter_pdf_despacho_json')
    require('zope2.View')
    
    def render(self):
        """Retorna URL do PDF do despacho"""
        try:
            cod_tramitacao = self._obter_parametro('cod_tramitacao', obrigatorio=True)
            tipo = self._obter_tipo_tramitacao()
            
            cod_tramitacao_int = validar_codigo_inteiro_seguro(cod_tramitacao, 'cod_tramitacao', min_valor=1)
            
            # Obtém link do PDF do despacho
            link_pdf_despacho = None
            try:
                # Verifica se PDF existe no repositório Zope
                site_real = self._resolver_site_real()
                arquivo_pdf = f"{cod_tramitacao_int}_tram.pdf"
                
                if tipo == 'MATERIA':
                    repo = site_real.sapl_documentos.materia.tramitacao
                else:
                    repo = site_real.sapl_documentos.administrativo.tramitacao
                
                # Verifica se o arquivo existe no repositório
                if hasattr(repo, arquivo_pdf):
                    try:
                        # Obtém URL usando absolute_url() do arquivo (padrão Zope)
                        arq = getattr(repo, arquivo_pdf)
                        base_url = str(arq.absolute_url())
                        
                        # Adiciona timestamp dinâmico para forçar atualização do cache do navegador
                        import time
                        timestamp = int(time.time() * 1000)  # Timestamp em milissegundos
                        
                        # Verifica se a URL já tem parâmetros de query
                        separator = '&' if '?' in base_url else '?'
                        link_pdf_despacho = f"{base_url}{separator}_t={timestamp}"
                        
                        logger.info(f"PDF encontrado para tramitação {cod_tramitacao_int}: {link_pdf_despacho}")
                    except Exception as e:
                        logger.warning(f"Erro ao obter URL do PDF para tramitação {cod_tramitacao_int}: {e}")
                else:
                    logger.debug(f"PDF não encontrado para tramitação {cod_tramitacao_int} no repositório")
            except Exception as e:
                logger.warning(f"Erro ao obter link do PDF: {e}", exc_info=True)
            
            if link_pdf_despacho:
                return self._resposta_json({
                    'link_pdf': link_pdf_despacho,
                    'pdf_existe': True
                })
            else:
                return self._resposta_json({
                    'link_pdf': None,
                    'pdf_existe': False,
                    'mensagem': 'PDF do despacho não encontrado'
                })
        
        except ValidationError as e:
            logger.warning(f"TramitacaoObterPDFDespachoView - Erro de validação: {e}")
            return self._resposta_erro(str(e))
        except Exception as e:
            logger.error(f"TramitacaoObterPDFDespachoView - Erro inesperado: {e}", exc_info=True)
            return self._resposta_erro(f'Erro ao obter PDF: {str(e)}')


class TramitacaoLoteFormView(GrokView, TramitacaoAPIBase):
    """View para retornar HTML do formulário em lote (sempre no sidebar)"""
    
    context(Interface)
    name('tramitacao_lote_form_json')
    require('zope2.View')
    
    def _obter_dados_usuario_em_sessao(self, session, cod_usuario, tipo):
        """
        Obtém dados do usuário (unidades e nome) usando sessão existente.
        
        Args:
            session: Sessão do banco de dados
            cod_usuario: Código do usuário
            tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
            
        Returns:
            tuple: (unidades_usuario, nome_usuario) onde:
                - unidades_usuario: Lista de dicts com {'cod': int, 'nome': str}
                - nome_usuario: String com nome do usuário
        """
        try:
            # Obtém nome do usuário
            usuario = session.query(Usuario).filter(
                Usuario.cod_usuario == cod_usuario,
                Usuario.ind_excluido == 0,
                Usuario.ind_ativo == 1
            ).first()
            
            nome_usuario = ''
            if usuario:
                # Usa col_username como nome do usuário (atributo que existe no modelo)
                nome_usuario = usuario.col_username or ''
            
            # Obtém unidades do usuário - query UnidadeTramitacao diretamente
            unidades_query = session.query(UnidadeTramitacao).join(
                UsuarioUnidTram,
                UnidadeTramitacao.cod_unid_tramitacao == UsuarioUnidTram.cod_unid_tramitacao
            ).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UsuarioUnidTram.cod_usuario == cod_usuario,
                UnidadeTramitacao.ind_excluido == 0
            )
            
            # Filtra por tipo se necessário
            if tipo == 'MATERIA':
                unidades_query = unidades_query.filter(UnidadeTramitacao.ind_leg == 1)
            elif tipo == 'DOCUMENTO':
                unidades_query = unidades_query.filter(UnidadeTramitacao.ind_adm == 1)
            
            unidades_db = unidades_query.all()
            
            # Converte para formato esperado
            unidades_usuario = []
            for unidade in unidades_db:
                nome_unidade = _get_nome_unidade_tramitacao(unidade)
                unidades_usuario.append({
                    'cod': unidade.cod_unid_tramitacao,
                    'nome': nome_unidade
                })
            
            # Ordena por nome
            unidades_usuario.sort(key=lambda x: x['nome'])
            
            logger.info(
                f"_obter_dados_usuario_em_sessao - Usuário: {nome_usuario}, "
                f"Unidades: {len(unidades_usuario)}"
            )
            
            return unidades_usuario, nome_usuario
            
        except Exception as e:
            logger.error(f"Erro ao obter dados do usuário: {e}", exc_info=True)
            return [], ''
    
    def _processar_unidade_caixa_em_sessao(self, session, unidades_usuario, cod_unid_tram_local):
        """
        Processa unidade da caixa de entrada, garantindo que ela esteja na lista.
        
        Args:
            session: Sessão do banco de dados
            unidades_usuario: Lista de unidades do usuário
            cod_unid_tram_local: Código da unidade da caixa de entrada
            
        Returns:
            Lista de unidades atualizada (com unidade da caixa se não estiver presente)
        """
        try:
            # Verifica se a unidade já está na lista
            codigos_existentes = [u['cod'] for u in unidades_usuario]
            if cod_unid_tram_local in codigos_existentes:
                return unidades_usuario
            
            # Busca a unidade no banco
            unidade = session.query(UnidadeTramitacao).options(
                selectinload(UnidadeTramitacao.comissao),
                selectinload(UnidadeTramitacao.orgao),
                selectinload(UnidadeTramitacao.parlamentar)
            ).filter(
                UnidadeTramitacao.cod_unid_tramitacao == cod_unid_tram_local,
                UnidadeTramitacao.ind_excluido == 0
            ).first()
            
            if unidade:
                nome_unidade = _get_nome_unidade_tramitacao(unidade)
                # Adiciona no início da lista
                unidades_usuario.insert(0, {
                    'cod': unidade.cod_unid_tramitacao,
                    'nome': nome_unidade
                })
                logger.info(
                    f"_processar_unidade_caixa_em_sessao - Unidade da caixa adicionada: "
                    f"{nome_unidade} (cod: {cod_unid_tram_local})"
                )
            
            return unidades_usuario
            
        except Exception as e:
            logger.error(f"Erro ao processar unidade da caixa: {e}", exc_info=True)
            return unidades_usuario
    
    def _obter_unidades_destino_e_status_em_sessao(self, session, tipo, cod_unid_tram_local):
        """
        Obtém unidades de destino e status permitidos usando sessão existente.
        
        Args:
            session: Sessão do banco de dados
            tipo: Tipo de tramitação ('MATERIA' ou 'DOCUMENTO')
            cod_unid_tram_local: Código da unidade de origem (opcional)
            
        Returns:
            tuple: (unidades_destino, status_opcoes) onde:
                - unidades_destino: Lista de dicts com {'name': str, 'id': int}
                - status_opcoes: Lista de dicts com {'name': str, 'id': int}
        """
        unidades_destino = []
        status_opcoes = []
        
        try:
            if cod_unid_tram_local:
                # Busca a unidade de origem para obter permissões
                unidade_origem = session.query(UnidadeTramitacao).options(
                    selectinload(UnidadeTramitacao.comissao),
                    selectinload(UnidadeTramitacao.orgao),
                    selectinload(UnidadeTramitacao.parlamentar)
                ).filter(
                    UnidadeTramitacao.cod_unid_tramitacao == cod_unid_tram_local,
                    UnidadeTramitacao.ind_excluido == 0
                ).first()
                
                if unidade_origem:
                    # Obtém unidades de destino permitidas
                    if unidade_origem.unid_dest_permitidas:
                        unid_dest_ids = [
                            id.strip() for id in str(unidade_origem.unid_dest_permitidas).split(',')
                            if id.strip()
                        ]
                        
                        for unid_id in unid_dest_ids:
                            try:
                                unid_dest = session.query(UnidadeTramitacao).options(
                                    selectinload(UnidadeTramitacao.comissao),
                                    selectinload(UnidadeTramitacao.orgao),
                                    selectinload(UnidadeTramitacao.parlamentar)
                                ).filter(
                                    UnidadeTramitacao.cod_unid_tramitacao == int(unid_id),
                                    UnidadeTramitacao.ind_excluido == 0
                                ).first()
                                
                                if unid_dest:
                                    # Filtra por tipo
                                    if tipo == 'MATERIA' and unid_dest.ind_leg == 1:
                                        nome_unidade = _get_nome_unidade_tramitacao(unid_dest)
                                        unidades_destino.append({
                                            'name': nome_unidade,
                                            'id': unid_dest.cod_unid_tramitacao
                                        })
                                    elif tipo == 'DOCUMENTO' and unid_dest.ind_adm == 1:
                                        nome_unidade = _get_nome_unidade_tramitacao(unid_dest)
                                        unidades_destino.append({
                                            'name': nome_unidade,
                                            'id': unid_dest.cod_unid_tramitacao
                                        })
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Erro ao processar unidade destino ID {unid_id}: {e}")
                                continue
                        
                        # Ordena por nome
                        unidades_destino.sort(key=lambda x: x['name'])
                    
                    # Obtém status permitidos
                    if tipo == 'MATERIA':
                        if unidade_origem.status_permitidos:
                            status_ids = [
                                id.strip() for id in str(unidade_origem.status_permitidos).split(',')
                                if id.strip()
                            ]
                            status_list = session.query(StatusTramitacao).filter(
                                StatusTramitacao.cod_status.in_([int(sid) for sid in status_ids]),
                                StatusTramitacao.ind_excluido == 0
                            ).order_by(StatusTramitacao.des_status).all()
                            
                            for status in status_list:
                                status_opcoes.append({
                                    'name': status.des_status or '',
                                    'id': status.cod_status
                                })
                    else:  # DOCUMENTO
                        if unidade_origem.status_adm_permitidos:
                            status_ids = [
                                id.strip() for id in str(unidade_origem.status_adm_permitidos).split(',')
                                if id.strip()
                            ]
                            status_list = session.query(StatusTramitacaoAdministrativo).filter(
                                StatusTramitacaoAdministrativo.cod_status.in_([int(sid) for sid in status_ids]),
                                StatusTramitacaoAdministrativo.ind_excluido == 0
                            ).order_by(StatusTramitacaoAdministrativo.des_status).all()
                            
                            for status in status_list:
                                status_opcoes.append({
                                    'name': status.des_status or '',
                                    'id': status.cod_status
                                })
            
            return unidades_destino, status_opcoes
            
        except Exception as e:
            logger.error(f"Erro ao obter unidades de destino e status: {e}", exc_info=True)
            return [], []
    
    def render(self):
        """Retorna HTML do formulário em lote"""
        try:
            # Todas as validações primeiro (ANTES de abrir sessão)
            processos = self._obter_parametro('processos', obrigatorio=True)
            tipo = self._obter_tipo_tramitacao()
            cod_unid_tram_local_caixa = self._obter_parametro('cod_unid_tram_local', '')
            
            # ABRE APENAS UMA sessão readonly para tudo
            with db_session_readonly() as session:
                # Obtém usuário (usa cache se disponível)
                cod_usuario = self._get_cod_usuario()
                if not cod_usuario:
                    return self._resposta_erro(
                        'Usuário não autenticado. É necessário estar autenticado para tramitar processos. '
                        'Faça login e tente novamente.'
                    )
                
                # Obtém dados do usuário usando sessão existente
                unidades_usuario, nome_usuario = self._obter_dados_usuario_em_sessao(session, cod_usuario, tipo)
                
                # Obtém data atual
                from datetime import datetime
                dat_tramitacao = datetime.now().strftime('%d/%m/%Y %H:%M')
                
                # Processa unidade da caixa de entrada
                cod_unid_tram_local_int = None
                if cod_unid_tram_local_caixa:
                    try:
                        cod_unid_tram_local_int = validar_codigo_inteiro_seguro(
                            cod_unid_tram_local_caixa, 'cod_unid_tram_local', min_valor=1
                        )
                    except (SecurityValidationError, ValueError, TypeError):
                        cod_unid_tram_local_int = None
                
                if cod_unid_tram_local_int:
                    unidades_usuario = self._processar_unidade_caixa_em_sessao(
                        session, unidades_usuario, cod_unid_tram_local_int
                    )
                
                # Obtém unidades de destino e status usando sessão existente
                unidades_destino, status_opcoes = self._obter_unidades_destino_e_status_em_sessao(
                    session, tipo, cod_unid_tram_local_int
                )
                
                logger.info(
                    f"TramitacaoLoteFormView - Unidades de destino: {len(unidades_destino)}, "
                    f"Status: {len(status_opcoes)}"
                )
                
                # Renderiza formulário em lote completo (sempre no sidebar) usando novo renderizador
                html = TramitacaoFormRenderer.render_lote_form(
                    tipo=tipo,
                    processos=processos.split(','),
                    cod_usuario=cod_usuario,
                    nome_usuario=nome_usuario,
                    unidades_usuario=unidades_usuario,
                    dat_tramitacao=dat_tramitacao,
                    cod_unid_tram_local=cod_unid_tram_local_int,
                    unidades_destino=unidades_destino,
                    status_opcoes=status_opcoes
                )
                
                # Sessão é fechada automaticamente ao sair do with
                return self._resposta_json({
                    'html': html,
                    'tipo': tipo
                })
        
        except Exception as e:
            return self._tratar_erro(e, "TramitacaoLoteFormView")
    
    def _renderizar_formulario_lote_completo(self, tipo, processos, cod_usuario, nome_usuario, unidades_usuario, dat_tramitacao, cod_unid_tram_local=None):
        """Renderiza formulário em lote completo HTML para sidebar"""
        html = f'<form class="needs-validation" id="tramitacao_lote_form" method="post" enctype="multipart/form-data" novalidate>'
        
        # Campos hidden
        html += f'<input type="hidden" name="hdn_tipo_tramitacao" value="{tipo}" />'
        html += f'<input type="hidden" name="hdn_cod_usuario_local" id="hdn_cod_usuario_local" value="{cod_usuario or ""}" />'
        html += f'<input type="hidden" name="hdn_dat_tramitacao" value="{dat_tramitacao}" />'
        html += f'<input type="hidden" id="hdn_file" name="hdn_file" value="0" />'
        
        # Informação sobre processos selecionados
        tipo_label = 'Processos Legislativos' if tipo == 'MATERIA' else 'Processos Administrativos'
        html += '<div class="alert alert-info mb-3" role="alert">'
        html += '<div class="d-flex align-items-center">'
        html += '<i class="mdi mdi-file-multiple-outline me-2 fs-4"></i>'
        html += '<div class="flex-grow-1">'
        html += f'<strong>{tipo_label}</strong><br>'
        html += f'<span class="text-muted"><span id="num-processos-selecionados-lote">{len(processos)}</span> processo(s) selecionado(s) para tramitação em lote</span>'
        html += '</div></div></div>'
        
        # Seção: Origem
        html += '<div class="card mb-3">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0"><i class="mdi mdi-arrow-up-circle me-1" aria-hidden="true"></i>Origem</h6>'
        html += '</div>'
        html += '<div class="card-body p-3">'
        html += '<div class="row g-3">'
        html += '<div class="col-12 col-md-4 mb-2">'
        html += _renderizar_label_campo('txt_dat_tramitacao', 'Data da Tramitação', obrigatorio=True)
        html += '<div class="input-group input-group-sm">'
        html += f'<input class="form-control form-control-sm" type="text" name="txt_dat_tramitacao" id="txt_dat_tramitacao" value="{dat_tramitacao}" autocomplete="off" readonly required aria-label="Data da Tramitação (somente leitura)" aria-readonly="true" tabindex="-1" />'
        html += f'<span class="input-group-text">{_renderizar_icone_decorativo("mdi mdi-calendar")}</span>'
        html += '</div></div>'
        
        html += '<div class="col-12 col-md-5 mb-2">'
        html += _renderizar_label_campo('lst_cod_unid_tram_local', 'Unidade de Origem', obrigatorio=True)
        # Obtém unidade selecionada (sempre será a unidade da caixa de entrada)
        cod_unid_selecionada = cod_unid_tram_local
        
        # Busca nome da unidade selecionada
        nome_unidade_selecionada = ''
        if cod_unid_selecionada:
            for unid in unidades_usuario:
                try:
                    if int(unid['cod']) == int(cod_unid_selecionada):
                        nome_unidade_selecionada = unid['nome']
                        logger.info(f"_renderizar_formulario_lote_completo - Unidade encontrada: {nome_unidade_selecionada} (cod: {cod_unid_selecionada})")
                        break
                except (ValueError, TypeError) as e:
                    logger.warning(f"_renderizar_formulario_lote_completo - Erro ao comparar unidade: {e}")
                    continue
            
            # Se não encontrou nas unidades do usuário, busca diretamente no banco
            if not nome_unidade_selecionada and cod_unid_selecionada:
                try:
                    # Usa db_session_readonly() para leitura (pode usar with)
                    with db_session_readonly() as session:
                        unidade = session.query(UnidadeTramitacao).options(
                            selectinload(UnidadeTramitacao.comissao),
                            selectinload(UnidadeTramitacao.orgao),
                            selectinload(UnidadeTramitacao.parlamentar)
                        ).filter(
                            UnidadeTramitacao.cod_unid_tramitacao == int(cod_unid_selecionada),
                            UnidadeTramitacao.ind_excluido == 0
                        ).first()
                        
                        if unidade:
                            nome_unidade_selecionada = _get_nome_unidade_tramitacao(unidade)
                            logger.info(
                                f"_renderizar_formulario_lote_completo - Unidade obtida diretamente do banco: "
                                f"{nome_unidade_selecionada} (cod: {cod_unid_selecionada})"
                            )
                except Exception as e:
                    logger.error(f"_renderizar_formulario_lote_completo - Erro ao buscar unidade no banco: {e}", exc_info=True)
        
        # Campo readonly (não pode ser alterado - sempre será a unidade da caixa de entrada)
        if cod_unid_selecionada and nome_unidade_selecionada:
            html += f'<input type="hidden" name="lst_cod_unid_tram_local" id="lst_cod_unid_tram_local" value="{cod_unid_selecionada}" />'
            html += f'<input class="form-control form-control-sm bg-light" type="text" id="txt_unid_tram_local_display" value="{nome_unidade_selecionada}" readonly aria-label="Unidade de Origem (somente leitura)" aria-readonly="true" tabindex="-1" aria-describedby="lst_cod_unid_tram_local_help" />'
        elif cod_unid_selecionada:
            # Se tem código mas não tem nome, mostra o código
            html += f'<input type="hidden" name="lst_cod_unid_tram_local" id="lst_cod_unid_tram_local" value="{cod_unid_selecionada}" />'
            html += f'<input class="form-control form-control-sm bg-light" type="text" id="txt_unid_tram_local_display" value="Unidade {cod_unid_selecionada}" readonly aria-label="Unidade de Origem (somente leitura)" aria-readonly="true" tabindex="-1" aria-describedby="lst_cod_unid_tram_local_help" />'
            logger.warning(f"_renderizar_formulario_lote_completo - Unidade sem nome encontrada: cod={cod_unid_selecionada}")
        else:
            # Fallback: se não encontrou, mostra select desabilitado
            html += '<select class="form-select form-select-sm" id="lst_cod_unid_tram_local" name="lst_cod_unid_tram_local" required disabled aria-label="Unidade de Origem">'
            html += '<option value="">Selecione uma unidade na caixa de entrada</option>'
            for unid in unidades_usuario:
                html += f'<option value="{unid["cod"]}">{unid["nome"]}</option>'
            html += '</select>'
        html += '</div>'
        
        html += '<div class="col-12 col-md-3 mb-2">'
        html += _renderizar_label_campo('txt_nom_usuario', 'Usuário de Origem', obrigatorio=True)
        html += f'<input class="form-control form-control-sm bg-light" type="text" id="txt_nom_usuario" value="{nome_usuario}" readonly aria-label="Usuário de Origem (somente leitura)" aria-readonly="true" tabindex="-1" />'
        html += '</div></div></div></div>'
        
        # Seção: Destino
        html += '<div class="card mb-3">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0"><i class="mdi mdi-arrow-down-circle me-1" aria-hidden="true"></i>Destino</h6>'
        html += '</div>'
        html += '<div class="card-body p-3">'
        html += '<div class="row g-3">'
        html += '<div class="col-12 col-md-6 mb-2">'
        html += _renderizar_label_campo('lst_cod_unid_tram_dest', 'Unidade de Destino', obrigatorio=True)
        html += '<select class="tomselect form-select form-select-sm" name="lst_cod_unid_tram_dest" id="lst_cod_unid_tram_dest" data-placeholder="Selecione a unidade de destino..." style="width:100%" required aria-required="true">'
        html += '<option value="">Selecione a unidade de destino...</option>'
        html += '</select></div>'
        
        html += '<div class="col-12 col-md-6 mb-2">'
        html += _renderizar_label_campo('lst_cod_usuario_dest', 'Usuário de Destino', obrigatorio=False)
        html += '<select class="tomselect form-select form-select-sm" name="lst_cod_usuario_dest" id="lst_cod_usuario_dest" data-placeholder="Selecione o usuário de destino..." style="width:100%">'
        html += '<option value="">Selecione</option>'
        html += '</select></div></div></div></div>'
        
        # Seção: Status e Prazo
        html += '<div class="card mb-3">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0"><i class="mdi mdi-information-outline me-1" aria-hidden="true"></i>Status e Prazo</h6>'
        html += '</div>'
        html += '<div class="card-body p-3">'
        html += '<div class="row g-3">'
        html += '<div class="col-12 col-md-6 mb-2">'
        html += _renderizar_label_campo('lst_cod_status', 'Status', obrigatorio=True)
        html += '<select class="tomselect form-select form-select-sm" id="lst_cod_status" name="lst_cod_status" data-placeholder="Selecione o status..." style="width:100%" required aria-required="true">'
        html += '<option value="">Selecione o status...</option>'
        html += '</select></div>'
        
        html += '<div class="col-12 col-md-3 mb-2">'
        html += _renderizar_label_campo('txt_dat_fim_prazo', 'Data de Fim de Prazo', obrigatorio=False)
        html += '<div class="input-group input-group-sm">'
        html += '<input type="text" class="form-control form-control-sm" placeholder="dd/mm/aaaa" name="txt_dat_fim_prazo" id="txt_dat_fim_prazo" autocomplete="off" aria-label="Data de Fim de Prazo">'
        html += f'<span class="input-group-text">{_renderizar_icone_decorativo("mdi mdi-calendar")}</span>'
        html += '</div></div>'
        
        # Urgente (apenas para processos legislativos - MATERIA)
        if tipo == 'MATERIA':
            html += '<div class="col-12 col-md-3 mb-2">'
            html += _renderizar_label_campo('rad_ind_urgencia', 'Urgente?', obrigatorio=True)
            html += '<div class="form-check form-check-inline">'
            html += '<input class="form-check-input" type="radio" id="rad_urgencia_lote_1" name="rad_ind_urgencia" value="1" aria-required="true">'
            html += '<label class="form-check-label" for="rad_urgencia_lote_1">Sim</label>'
            html += '</div>'
            html += '<div class="form-check form-check-inline">'
            html += '<input class="form-check-input" type="radio" id="rad_urgencia_lote_0" name="rad_ind_urgencia" value="0" checked aria-required="true">'
            html += '<label class="form-check-label" for="rad_urgencia_lote_0">Não</label>'
            html += '</div></div>'
        html += '</div></div></div>'
        
        # Seção: Despacho em PDF
        html += '<div class="card mb-3">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0"><i class="mdi mdi-file-pdf-box me-1" aria-hidden="true"></i>Despacho em PDF</h6>'
        html += '</div>'
        html += '<div class="card-body p-3">'
        html += '<div class="d-flex align-items-center flex-wrap gap-2">'
        html += '<div class="form-check">'
        html += '<input class="form-check-input" type="radio" id="rad_pdf_lote_G" name="radTI" value="G" checked>'
        html += '<label class="form-check-label small" for="rad_pdf_lote_G">Gerar</label>'
        html += '</div>'
        html += '<div class="form-check">'
        html += '<input class="form-check-input" type="radio" id="rad_pdf_lote_S" name="radTI" value="S">'
        html += '<label class="form-check-label small" for="rad_pdf_lote_S">Anexar</label>'
        html += '</div>'
        html += '<input type="file" class="form-control form-control-sm" id="file_nom_arquivo_lote" name="file_nom_arquivo" accept="application/pdf" disabled style="max-width: 250px; flex: 1 1 auto;">'
        html += '</div></div></div>'
        
        # Seção: Texto do Despacho
        html += '<div class="card mb-3">'
        html += '<div class="card-header bg-light py-2">'
        html += '<h6 class="mb-0"><i class="mdi mdi-text me-1" aria-hidden="true"></i>Texto do Despacho</h6>'
        html += '</div>'
        html += '<div class="card-body p-3">'
        html += '<textarea class="form-control form-control-sm" name="txa_txt_tramitacao" id="txa_txt_tramitacao_lote" rows="6"></textarea>'
        html += '</div></div>'
        
        html += '</form>'
        
        # Script para habilitar/desabilitar campo de arquivo
        html += '''
        <script>
        $(document).ready(function() {
            // Habilita/desabilita campo de arquivo baseado na opção selecionada
            $('input[name="radTI"]').on('change', function() {
                const fileInput = $('#file_nom_arquivo_lote');
                if ($(this).val() === 'S') {
                    fileInput.prop('disabled', false);
                    fileInput.prop('required', true);
                } else {
                    fileInput.prop('disabled', true);
                    fileInput.prop('required', false);
                    fileInput.val('');
                }
            });
        });
        </script>
        
        <!-- TomSelect CSS e JS -->
        <link href="https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/css/tom-select.bootstrap5.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/js/tom-select.complete.min.js"></script>
        '''
        
        return html

# ============================================================================
# Views para Geração de PDF e Anexos
# ============================================================================

class TramitacaoPDFTaskExecutor(GrokView, TramitacaoAPIBase):
    """View chamada pela task Celery para preparar dados da tramitação"""
    
    context(Interface)
    name('tramitacao_pdf_task_executor')
    require('zope2.View')
    
    def render(self):
        """Prepara dados da tramitação e retorna para a task processar"""
        try:
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            cod_tramitacao = validar_codigo_inteiro_seguro(
                self._obter_parametro('cod_tramitacao'),
                'cod_tramitacao'
            )
            
            # ✅ CRÍTICO: Se dados_tramitacao_json foi fornecido, usa dados do request
            # em vez de buscar do banco (garante dados atualizados)
            dados_tramitacao_json = self._obter_parametro('dados_tramitacao_json', '')
            if dados_tramitacao_json:
                import json
                try:
                    dados_tramitacao_request = json.loads(dados_tramitacao_json)
                    logger.info(f"TramitacaoPDFTaskExecutor - Usando dados do request para preparar PDF (cod_tramitacao={cod_tramitacao})")
                    
                    # Usa get_session() apenas para obter propriedades da casa e outras informações
                    with get_session() as session:
                        from .pdf.generator import TramitacaoPDFGenerator
                        
                        generator = TramitacaoPDFGenerator(session, self.context)
                        
                        # Prepara dados usando dados do request (não busca do banco)
                        dados = generator.preparar_dados_tramitacao_com_dados_request(tipo, cod_tramitacao, dados_tramitacao_request)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"TramitacaoPDFTaskExecutor - Erro ao parsear dados_tramitacao_json, buscando do banco: {e}")
                    # Fallback: busca do banco se houver erro
                    with get_session() as session:
                        from .pdf.generator import TramitacaoPDFGenerator
                        
                        generator = TramitacaoPDFGenerator(session, self.context)
                        
                        # Prepara dados (sem gerar PDF ainda)
                        dados = generator.preparar_dados_tramitacao(tipo, cod_tramitacao)
            else:
                # Usa get_session() que tem acesso ao componente no contexto Zope
                with get_session() as session:
                    from .pdf.generator import TramitacaoPDFGenerator
                    
                    generator = TramitacaoPDFGenerator(session, self.context)
                    
                    # Prepara dados (sem gerar PDF ainda)
                    dados = generator.preparar_dados_tramitacao(tipo, cod_tramitacao)
            
            # Serializa dados para JSON (converte URLs de imagem para strings)
            # ✅ Este bloco deve estar FORA do if/else, pois dados já foi definido em ambos os casos
            dados_serializados = {
                'imagem': dados.get('imagem'),
                'rodape': dados.get('rodape', {}),
                'inf_basicas_dic': dados.get('inf_basicas_dic', {}),
                'tramitacao_dic': dados.get('tramitacao_dic', {})
            }
            
            return self._resposta_json({
                    'success': True,
                    'dados': dados_serializados,
                    'cod_tramitacao': cod_tramitacao,
                    'tipo': tipo
                })
        
        except Exception as e:
            logger.error(f"Erro ao preparar dados na view executor: {e}", exc_info=True)
            return self._resposta_json({
                'success': False,
                'error': str(e)
            })


class TramitacaoSalvarPDFView(GrokView, TramitacaoAPIBase):
    """View para salvar PDF gerado pela task no repositório"""
    
    context(Interface)
    name('tramitacao_salvar_pdf')
    require('zope2.View')
    
    def render(self):
        """Salva PDF no repositório Zope"""
        try:
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            cod_tramitacao = validar_codigo_inteiro_seguro(
                self._obter_parametro('cod_tramitacao'),
                'cod_tramitacao'
            )
            pdf_base64 = self._obter_parametro('pdf_base64', '')
            
            if not pdf_base64:
                return self._resposta_json({
                    'success': False,
                    'error': 'pdf_base64 não fornecido'
                })
            
            # Decodifica PDF
            import base64
            try:
                pdf_bytes = base64.b64decode(pdf_base64)
            except Exception as e:
                return self._resposta_json({
                    'success': False,
                    'error': f'Erro ao decodificar PDF: {str(e)}'
                })
            
            # Salva PDF no repositório usando o contexto Zope correto
            from .pdf.generator import TramitacaoPDFGenerator
            
            # Usa None para session (não precisa de sessão para salvar)
            generator = TramitacaoPDFGenerator(session=None, contexto_zope=self.context)
            
            try:
                generator.salvar_pdf_no_repositorio(tipo, cod_tramitacao, pdf_bytes, self.context)
                logger.debug(f"TramitacaoSalvarPDFView - PDF salvo no repositório (cod_tramitacao={cod_tramitacao})")
                return self._resposta_json({
                    'success': True,
                    'message': 'PDF salvo com sucesso',
                    'cod_tramitacao': cod_tramitacao
                })
            except Exception as e:
                logger.error(f"TramitacaoSalvarPDFView - Erro ao salvar PDF: {e}", exc_info=True)
                return self._resposta_json({
                    'success': False,
                    'error': f'Erro ao salvar PDF: {str(e)}'
                })
        
        except Exception as e:
            logger.error(f"Erro ao salvar PDF na view: {e}", exc_info=True)
            return self._resposta_json({
                'success': False,
                'error': str(e)
            })


class TramitacaoAnexoTaskExecutor(GrokView, TramitacaoAPIBase):
    """View chamada pela task Celery para verificar se tramitação existe"""
    
    context(Interface)
    name('tramitacao_anexo_task_executor')
    require('zope2.View')
    
    def render(self):
        """Verifica se tramitação existe e retorna resultado"""
        try:
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            cod_tramitacao = validar_codigo_inteiro_seguro(
                self._obter_parametro('cod_tramitacao'),
                'cod_tramitacao'
            )
            
            # Usa get_session() que tem acesso ao componente no contexto Zope
            with get_session() as session:
                from .anexos.service import TramitacaoAnexoService
                
                service = TramitacaoAnexoService(session, self.context)
                
                # Verifica se tramitação existe
                existe = service.verificar_tramitacao_existe(tipo, cod_tramitacao)
                
                if not existe:
                    return self._resposta_json({
                        'success': False,
                        'error': 'Tramitação não encontrada'
                    })
                
                # Obtém PDF principal
                pdf_buffer = service.obter_pdf_tramitacao(tipo, cod_tramitacao)
                
                if not pdf_buffer:
                    return self._resposta_json({
                        'success': False,
                        'error': 'PDF principal não encontrado'
                    })
                
                # Converte para base64
                import base64
                pdf_bytes = pdf_buffer.read()
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                
                return self._resposta_json({
                    'success': True,
                    'message': 'PDF principal obtido',
                    'cod_tramitacao': cod_tramitacao,
                    'tipo': tipo,
                    'pdf_base64': pdf_base64
                })
        
        except Exception as e:
            logger.error(f"Erro ao obter PDF principal na view executor: {e}", exc_info=True)
            return self._resposta_json({
                'success': False,
                'error': str(e)
            })


class TramitacaoDespachoPDFView(GrokView, TramitacaoAPIBase):
    """View para gerar PDF do despacho (assíncrono via Celery)"""
    
    context(Interface)
    name('tramitacao_despacho_pdf')
    require('zope2.View')
    
    def render(self):
        """Dispara tarefa Celery para gerar PDF e retorna task_id"""
        try:
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            cod_tramitacao = validar_codigo_inteiro_seguro(
                self._obter_parametro('cod_tramitacao'),
                'cod_tramitacao'
            )
            
            gerar_novo = self._obter_parametro('gerar_novo', 'false').lower() == 'true'
            
            if not gerar_novo:
                with get_session() as session:
                    from .anexos.service import TramitacaoAnexoService
                    anexo_service = TramitacaoAnexoService(session, self.context)
                    pdf_buffer = anexo_service.obter_pdf_tramitacao(tipo, cod_tramitacao)
                    if pdf_buffer:
                        self.request.response.setHeader('Content-Type', 'application/pdf')
                        self.request.response.setHeader(
                            'Content-Disposition',
                            f'attachment; filename="despacho_tramitacao_{cod_tramitacao}.pdf"'
                        )
                        return pdf_buffer.read()
            
            import tasks
            gerar_pdf_despacho_task = tasks.gerar_pdf_despacho_task
            portal_url = str(self.context.absolute_url())
            site_path = 'sagl'
            user_id = self._get_current_user_id()
            
            existing_task = self._check_existing_task_pdf(
                gerar_pdf_despacho_task, tipo, cod_tramitacao, user_id, portal_url
            )
            if existing_task:
                return self._resposta_json(existing_task)
            
            task_kwargs = {
                'tipo': str(tipo),
                'cod_tramitacao': int(cod_tramitacao),
                'portal_url': str(portal_url),
                'site_path': str(site_path)
            }
            if user_id:
                task_kwargs['user_id'] = str(user_id)
            
            import json
            try:
                json.dumps(task_kwargs)
            except (TypeError, ValueError) as e:
                logger.error(f"Erro: kwargs não são serializáveis: {e}")
                raise
            
            task_result = gerar_pdf_despacho_task.apply_async(kwargs=task_kwargs)
            task_id = task_result.id if hasattr(task_result, 'id') else getattr(task_result, 'task_id', None)
            if not task_id:
                raise Exception('Falha ao obter task_id')
            
            return self._resposta_json({
                'task_id': task_id,
                'status': 'PENDING',
                'message': 'Geração de PDF iniciada',
                'monitor_url': f"{portal_url}/@@tramitacao_despacho_pdf_status?task_id={task_id}",
                'cod_tramitacao': cod_tramitacao,
                'tipo': tipo
            })
        except Exception as e:
            logger.error(f"Erro ao iniciar geração de PDF: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})
    
    def _get_current_user_id(self):
        try:
            from AccessControl import getSecurityManager
            user = getSecurityManager().getUser()
            if user:
                return user.getId()
        except:
            pass
        return None
    
    def _check_existing_task_pdf(self, task_func, tipo, cod_tramitacao, user_id, portal_url):
        try:
            if not hasattr(task_func, 'app'):
                return None
            celery_app = task_func.app
            inspect = celery_app.control.inspect(timeout=0.2)
            if inspect is None:
                return None
            try:
                active_tasks = inspect.active()
                if active_tasks:
                    for worker, tasks_list in active_tasks.items():
                        for task in tasks_list:
                            task_kwargs = task.get('kwargs', {})
                            task_name = task.get('name', '')
                            if (str(task_kwargs.get('tipo')) == str(tipo) and
                                str(task_kwargs.get('cod_tramitacao')) == str(cod_tramitacao) and
                                'gerar_pdf_despacho' in task_name):
                                return {
                                    'task_id': task.get('id'),
                                    'status': 'PROGRESS',
                                    'message': 'Tarefa já está em execução',
                                    'monitor_url': f"{portal_url}/@@tramitacao_despacho_pdf_status?task_id={task.get('id')}"
                                }
            except:
                pass
        except:
            pass
        return None


class TramitacaoDespachoPDFStatusView(GrokView, TramitacaoAPIBase):
    context(Interface)
    name('tramitacao_despacho_pdf_status')
    require('zope2.View')
    
    def render(self):
        try:
            task_id = self._obter_parametro('task_id')
            if not task_id:
                return self._resposta_json({'erro': 'task_id é obrigatório'})
            from tasks_folder.task_monitor import get_task_status
            status = get_task_status(task_id)
            if status:
                # Se task concluída com sucesso, inclui PDF base64 no resultado
                if status.get('status') == 'SUCCESS':
                    meta = status.get('meta', {})
                    if 'pdf_base64' in meta:
                        status['pdf_base64'] = meta.get('pdf_base64')
                        status['pdf_filename'] = meta.get('pdf_filename')
                return self._resposta_json(status)
            return self._resposta_json({'status': 'UNKNOWN', 'error': 'Task não encontrada', 'task_id': task_id})
        except Exception as e:
            logger.error(f"Erro ao consultar status: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})


class TramitacaoDespachoPDFSalvarView(GrokView, TramitacaoAPIBase):
    """View que salva o PDF gerado pela task no repositório Zope"""
    context(Interface)
    name('tramitacao_despacho_pdf_salvar')
    require('zope2.View')
    
    def render(self):
        try:
            task_id = self._obter_parametro('task_id')
            if not task_id:
                return self._resposta_json({'erro': 'task_id é obrigatório'})
            
            # Busca resultado da task
            from tasks_folder.task_monitor import get_task_status
            status = get_task_status(task_id)
            
            if not status:
                return self._resposta_json({'erro': 'Task não encontrada', 'task_id': task_id})
            
            if status.get('status') != 'SUCCESS':
                return self._resposta_json({
                    'erro': f"Task não concluída com sucesso. Status: {status.get('status')}",
                    'status': status.get('status')
                })
            
            # Extrai dados do resultado (pode estar em meta, result ou diretamente no status)
            meta = status.get('meta', {})
            result = status.get('result', {})
            
            # Busca pdf_base64 em múltiplos lugares
            pdf_base64 = (
                meta.get('pdf_base64') or 
                result.get('pdf_base64') or 
                status.get('pdf_base64')
            )
            
            if not pdf_base64:
                # Log detalhado para debug
                logger.error(f"PDF não encontrado. Status completo: {status}")
                logger.error(f"Meta: {meta}")
                logger.error(f"Result: {result} (tipo: {type(result)})")
                if isinstance(result, dict):
                    logger.error(f"Result keys: {list(result.keys())}")
                return self._resposta_json({
                    'erro': 'PDF não encontrado no resultado da task',
                    'debug': {
                        'status_keys': list(status.keys()),
                        'meta_keys': list(meta.keys()) if meta else None,
                        'result_type': str(type(result)),
                        'result_keys': list(result.keys()) if isinstance(result, dict) else None
                    }
                })
            
            # Busca tipo e cod_tramitacao em múltiplos lugares
            tipo = (
                meta.get('tipo') or 
                result.get('tipo') or 
                'MATERIA'
            )
            cod_tramitacao = (
                meta.get('cod_tramitacao') or 
                result.get('cod_tramitacao')
            )
            pdf_filename = (
                meta.get('pdf_filename') or 
                result.get('pdf_filename') or 
                (f"{cod_tramitacao}_tram.pdf" if cod_tramitacao else None)
            )
            
            if not cod_tramitacao:
                return self._resposta_json({'erro': 'cod_tramitacao não encontrado no resultado da task'})
            if not pdf_filename:
                pdf_filename = f"{cod_tramitacao}_tram.pdf"
            
            # Decodifica PDF
            import base64
            pdf_bytes = base64.b64decode(pdf_base64)
            
            # Salva no repositório Zope
            # Resolve o site real do contexto Zope
            site_real = self._resolver_site_real()
            
            from .pdf.generator import TramitacaoPDFGenerator
            generator = TramitacaoPDFGenerator(session=None, contexto_zope=site_real)
            generator.salvar_pdf_no_repositorio(tipo, cod_tramitacao, pdf_bytes, site_real)
            
            return self._resposta_json({
                'success': True,
                'message': 'PDF salvo com sucesso',
                'pdf_filename': pdf_filename,
                'cod_tramitacao': cod_tramitacao,
                'tipo': tipo
            })
            
        except Exception as e:
            logger.error(f"Erro ao salvar PDF: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})


class TramitacaoDespachoPDFSalvarLoteView(GrokView, TramitacaoAPIBase):
    """View que salva os PDFs gerados pela task em lote no repositório Zope"""
    context(Interface)
    name('tramitacao_despacho_pdf_salvar_lote')
    require('zope2.View')
    
    def render(self):
        try:
            task_id = self._obter_parametro('task_id')
            if not task_id:
                return self._resposta_json({'erro': 'task_id é obrigatório'})
            
            # Busca resultado da task
            from tasks_folder.task_monitor import get_task_status
            status = get_task_status(task_id)
            
            if not status:
                return self._resposta_json({'erro': 'Task não encontrada', 'task_id': task_id})
            
            if status.get('status') != 'SUCCESS':
                return self._resposta_json({
                    'erro': f"Task não concluída com sucesso. Status: {status.get('status')}",
                    'status': status.get('status')
                })
            
            # Extrai resultados do lote
            # Tenta obter de meta primeiro (do último update_state), depois de result (retorno da função)
            meta = status.get('meta', {})
            resultados = meta.get('resultados', [])
            
            # Se não encontrou em meta, tenta em result (retorno direto da função)
            if not resultados:
                result = status.get('result', {})
                if isinstance(result, dict):
                    resultados = result.get('resultados', [])
            
            if not resultados:
                # Log para debug
                logger.warning(f"Nenhum resultado encontrado na task {task_id}. Status completo: {status}")
                return self._resposta_json({'erro': 'Nenhum resultado encontrado na task'})
            
            # Salva cada PDF no repositório Zope
            # Resolve o site real do contexto Zope
            site_real = self._resolver_site_real()
            
            from .pdf.generator import TramitacaoPDFGenerator
            generator = TramitacaoPDFGenerator(session=None, contexto_zope=site_real)
            import base64
            
            salvos = []
            erros = []
            
            for resultado in resultados:
                if resultado.get('status') == 'SUCCESS':
                    try:
                        cod_tramitacao = resultado.get('cod_tramitacao')
                        pdf_base64 = resultado.get('pdf_base64')
                        tipo = resultado.get('tipo', 'MATERIA')
                        
                        if not pdf_base64:
                            erros.append({
                                'cod_tramitacao': cod_tramitacao,
                                'erro': 'PDF não encontrado no resultado'
                            })
                            continue
                        
                        # Decodifica e salva
                        pdf_bytes = base64.b64decode(pdf_base64)
                        generator.salvar_pdf_no_repositorio(tipo, cod_tramitacao, pdf_bytes, site_real)
                        
                        salvos.append(cod_tramitacao)
                    except Exception as e:
                        erros.append({
                            'cod_tramitacao': resultado.get('cod_tramitacao'),
                            'erro': str(e)
                        })
            
            return self._resposta_json({
                'success': True,
                'message': f'{len(salvos)} PDF(s) salvos com sucesso',
                'salvos': len(salvos),
                'erros': len(erros),
                'cod_tramitacoes_salvos': salvos,
                'erros_detalhes': erros
            })
            
        except Exception as e:
            logger.error(f"Erro ao salvar PDFs em lote: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})


class TramitacaoDespachoPDFDownloadView(GrokView, TramitacaoAPIBase):
    context(Interface)
    name('tramitacao_despacho_pdf_download')
    require('zope2.View')
    
    def render(self):
        try:
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            cod_tramitacao = validar_codigo_inteiro_seguro(self._obter_parametro('cod_tramitacao'), 'cod_tramitacao')
            with get_session() as session:
                from .anexos.service import TramitacaoAnexoService
                anexo_service = TramitacaoAnexoService(session, self.context)
                pdf_buffer = anexo_service.obter_pdf_tramitacao(tipo, cod_tramitacao)
                if not pdf_buffer:
                    return self._resposta_json({'erro': 'PDF não encontrado'})
                self.request.response.setHeader('Content-Type', 'application/pdf')
                self.request.response.setHeader('Content-Disposition', f'attachment; filename="despacho_tramitacao_{cod_tramitacao}.pdf"')
                return pdf_buffer.read()
        except Exception as e:
            logger.error(f"Erro ao baixar PDF: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})


class TramitacaoAnexarArquivoView(GrokView, TramitacaoAPIBase):
    context(Interface)
    name('tramitacao_anexar_arquivo')
    require('zope2.View')
    
    def render(self):
        try:
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            cod_tramitacao = validar_codigo_inteiro_seguro(self._obter_parametro('cod_tramitacao'), 'cod_tramitacao')
            arquivo = self.request.form.get('arquivo')
            if not arquivo or not hasattr(arquivo, 'read'):
                return self._resposta_json({'erro': 'Arquivo não fornecido'})
            arquivo.seek(0)
            arquivo_bytes = arquivo.read()
            if not arquivo_bytes.startswith(b'%PDF'):
                return self._resposta_json({'erro': 'Arquivo não é um PDF válido'})
            import tasks
            import base64
            juntar_pdfs_task = tasks.juntar_pdfs_task
            portal_url = str(self.context.absolute_url())
            site_path = 'sagl'
            user_id = self._get_current_user_id()
            existing_task = self._check_existing_task_anexo(juntar_pdfs_task, tipo, cod_tramitacao, user_id, portal_url)
            if existing_task:
                return self._resposta_json(existing_task)
            arquivo_base64 = base64.b64encode(arquivo_bytes).decode('utf-8')
            task_kwargs = {
                'tipo': str(tipo),
                'cod_tramitacao': int(cod_tramitacao),
                'arquivo_pdf_base64': arquivo_base64,
                'nome_arquivo': getattr(arquivo, 'filename', 'anexo.pdf'),
                'portal_url': str(portal_url),
                'site_path': str(site_path)
            }
            if user_id:
                task_kwargs['user_id'] = str(user_id)
            task_result = juntar_pdfs_task.apply_async(kwargs=task_kwargs)
            task_id = task_result.id if hasattr(task_result, 'id') else getattr(task_result, 'task_id', None)
            if not task_id:
                raise Exception('Falha ao obter task_id')
            return self._resposta_json({
                'task_id': task_id,
                'status': 'PENDING',
                'message': 'Junção de PDFs iniciada',
                'monitor_url': f"{portal_url}/@@tramitacao_anexar_arquivo_status?task_id={task_id}",
                'cod_tramitacao': cod_tramitacao,
                'tipo': tipo
            })
        except Exception as e:
            logger.error(f"Erro ao iniciar junção de PDFs: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})
    
    def _get_current_user_id(self):
        try:
            from AccessControl import getSecurityManager
            user = getSecurityManager().getUser()
            if user:
                return user.getId()
        except:
            pass
        return None
    
    def _check_existing_task_anexo(self, task_func, tipo, cod_tramitacao, user_id, portal_url):
        try:
            if not hasattr(task_func, 'app'):
                return None
            celery_app = task_func.app
            inspect = celery_app.control.inspect(timeout=0.2)
            if inspect is None:
                return None
            try:
                active_tasks = inspect.active()
                if active_tasks:
                    for worker, tasks_list in active_tasks.items():
                        for task in tasks_list:
                            task_kwargs = task.get('kwargs', {})
                            if (str(task_kwargs.get('tipo')) == str(tipo) and
                                str(task_kwargs.get('cod_tramitacao')) == str(cod_tramitacao) and
                                'juntar_pdfs' in task.get('name', '')):
                                return {
                                    'task_id': task.get('id'),
                                    'status': 'PROGRESS',
                                    'message': 'Tarefa já está em execução',
                                    'monitor_url': f"{portal_url}/@@tramitacao_anexar_arquivo_status?task_id={task.get('id')}"
                                }
            except:
                pass
        except:
            pass
        return None


class TramitacaoAnexarArquivoStatusView(GrokView, TramitacaoAPIBase):
    context(Interface)
    name('tramitacao_anexar_arquivo_status')
    require('zope2.View')
    
    def render(self):
        try:
            task_id = self._obter_parametro('task_id')
            if not task_id:
                return self._resposta_json({'erro': 'task_id é obrigatório'})
            from tasks_folder.task_monitor import get_task_status
            status = get_task_status(task_id)
            if status:
                # Se task concluída com sucesso, inclui PDF base64 no resultado
                if status.get('status') == 'SUCCESS':
                    meta = status.get('meta', {})
                    if 'pdf_base64' in meta:
                        status['pdf_base64'] = meta.get('pdf_base64')
                return self._resposta_json(status)
            return self._resposta_json({'status': 'UNKNOWN', 'error': 'Task não encontrada', 'task_id': task_id})
        except Exception as e:
            logger.error(f"Erro ao consultar status: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})


class TramitacaoAnexarArquivoSalvarView(GrokView, TramitacaoAPIBase):
    """View que salva o PDF juntado pela task no repositório Zope"""
    context(Interface)
    name('tramitacao_anexar_arquivo_salvar')
    require('zope2.View')
    
    def render(self):
        try:
            task_id = self._obter_parametro('task_id')
            if not task_id:
                return self._resposta_json({'erro': 'task_id é obrigatório'})
            
            # Busca resultado da task
            from tasks_folder.task_monitor import get_task_status
            status = get_task_status(task_id)
            
            if not status:
                return self._resposta_json({'erro': 'Task não encontrada', 'task_id': task_id})
            
            if status.get('status') != 'SUCCESS':
                return self._resposta_json({
                    'erro': f"Task não concluída com sucesso. Status: {status.get('status')}",
                    'status': status.get('status')
                })
            
            # Log para debug
            logger.info(f"[TramitacaoAnexarArquivoSalvarView] Status recebido: keys={list(status.keys())}")
            
            # Extrai dados do resultado (pode estar em meta, result ou diretamente no status)
            meta = status.get('meta', {})
            result = status.get('result', {})
            
            # Log para debug
            logger.info(f"[TramitacaoAnexarArquivoSalvarView] Meta: {meta}, Result: {result} (tipo: {type(result)})")
            
            # Se result é uma string (JSON serializado), tenta parsear
            if isinstance(result, str):
                try:
                    import json
                    result = json.loads(result)
                    logger.info(f"[TramitacaoAnexarArquivoSalvarView] Result parseado de string: {result}")
                except Exception as e:
                    logger.warning(f"[TramitacaoAnexarArquivoSalvarView] Erro ao parsear result como JSON: {e}")
            
            # Busca pdf_base64 em múltiplos lugares (similar ao endpoint de salvar PDF do despacho)
            pdf_base64 = None
            if isinstance(meta, dict) and meta.get('pdf_base64'):
                pdf_base64 = meta.get('pdf_base64')
            elif isinstance(result, dict) and result.get('pdf_base64'):
                pdf_base64 = result.get('pdf_base64')
            elif status.get('pdf_base64'):
                pdf_base64 = status.get('pdf_base64')
            
            if not pdf_base64:
                # Log detalhado para debug
                logger.error(f"PDF juntado não encontrado. Status completo: {status}")
                logger.error(f"Meta: {meta} (tipo: {type(meta)})")
                logger.error(f"Result: {result} (tipo: {type(result)})")
                if isinstance(result, dict):
                    logger.error(f"Result keys: {list(result.keys())}")
                if isinstance(meta, dict):
                    logger.error(f"Meta keys: {list(meta.keys())}")
                return self._resposta_json({
                    'erro': 'PDF não encontrado no resultado da task',
                    'debug': {
                        'status_keys': list(status.keys()),
                        'meta_type': str(type(meta)),
                        'meta_keys': list(meta.keys()) if isinstance(meta, dict) else None,
                        'result_type': str(type(result)),
                        'result_keys': list(result.keys()) if isinstance(result, dict) else None
                    }
                })
            
            # Busca tipo e cod_tramitacao em múltiplos lugares
            tipo = (
                meta.get('tipo') or 
                result.get('tipo') or 
                'MATERIA'
            )
            cod_tramitacao = (
                meta.get('cod_tramitacao') or 
                result.get('cod_tramitacao')
            )
            
            if not cod_tramitacao:
                return self._resposta_json({'erro': 'cod_tramitacao não encontrado no resultado da task'})
            
            # Decodifica PDF
            import base64
            pdf_bytes = base64.b64decode(pdf_base64)
            
            # Salva no repositório Zope (atualiza o PDF principal)
            # Resolve o site real do contexto Zope
            site_real = self._resolver_site_real()
            
            # Obtém nome do arquivo
            pdf_filename = f"{cod_tramitacao}_tram.pdf"
            
            # Acessa repositório e atualiza PDF
            if tipo == 'MATERIA':
                repo = site_real.sapl_documentos.materia.tramitacao
            else:
                repo = site_real.sapl_documentos.administrativo.tramitacao
            
            if hasattr(repo, pdf_filename):
                pdf_principal = getattr(repo, pdf_filename)
                pdf_principal.update_data(pdf_bytes)
            else:
                # Se não existe, cria
                repo.manage_addFile(
                    id=pdf_filename,
                    file=pdf_bytes,
                    content_type='application/pdf',
                    title=f'Tramitação de {"processo legislativo" if tipo == "MATERIA" else "processo administrativo"}'
                )
            
            return self._resposta_json({
                'success': True,
                'message': 'PDF juntado salvo com sucesso',
                'pdf_filename': pdf_filename,
                'cod_tramitacao': cod_tramitacao,
                'tipo': tipo
            })
            
        except Exception as e:
            logger.error(f"Erro ao salvar PDF juntado: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})


# ============================================================================
# Views para Processamento em Lote
# ============================================================================

class TramitacaoDespachoPDFLoteView(GrokView, TramitacaoAPIBase):
    """View para gerar PDF em lote"""
    
    context(Interface)
    name('tramitacao_despacho_pdf_lote')
    require('zope2.View')
    
    def render(self):
        try:
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            cod_tramitacoes = self._validar_lista_cod_tramitacoes()
            
            if not cod_tramitacoes:
                return self._resposta_json({'erro': 'Lista de tramitações vazia'})
            
            import tasks
            gerar_pdf_despacho_lote_task = tasks.gerar_pdf_despacho_lote_task
            portal_url = str(self.context.absolute_url())
            site_path = 'sagl'
            user_id = self._get_current_user_id()
            
            task_kwargs = {
                'tipo': str(tipo),
                'cod_tramitacoes': [int(cod) for cod in cod_tramitacoes],
                'portal_url': str(portal_url),
                'site_path': str(site_path)
            }
            if user_id:
                task_kwargs['user_id'] = str(user_id)
            
            import json
            try:
                json.dumps(task_kwargs)
            except (TypeError, ValueError) as e:
                logger.error(f"Erro: kwargs não são serializáveis: {e}")
                raise
            
            task_result = gerar_pdf_despacho_lote_task.apply_async(kwargs=task_kwargs)
            task_id = task_result.id if hasattr(task_result, 'id') else getattr(task_result, 'task_id', None)
            if not task_id:
                raise Exception('Falha ao obter task_id')
            
            return self._resposta_json({
                'task_id': task_id,
                'status': 'PENDING',
                'message': f'Geração de PDF em lote iniciada para {len(cod_tramitacoes)} tramitações',
                'total': len(cod_tramitacoes),
                'monitor_url': f"{portal_url}/@@tramitacao_despacho_pdf_lote_status?task_id={task_id}",
                'tipo': tipo
            })
        except Exception as e:
            logger.error(f"Erro ao disparar geração de PDF em lote: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})
    
    def _get_current_user_id(self):
        try:
            from AccessControl import getSecurityManager
            user = getSecurityManager().getUser()
            if user:
                return user.getId()
        except:
            pass
        return None
    
    def _validar_lista_cod_tramitacoes(self):
        """Valida e retorna lista de códigos de tramitação"""
        cod_tramitacoes = self._obter_parametro('cod_tramitacoes', [])
        
        if isinstance(cod_tramitacoes, str):
            import json
            try:
                cod_tramitacoes = json.loads(cod_tramitacoes)
            except:
                cod_tramitacoes = [cod_tramitacoes]
        
        if not isinstance(cod_tramitacoes, list):
            raise ValidationError('cod_tramitacoes deve ser uma lista')
        
        if len(cod_tramitacoes) == 0:
            raise ValidationError('Lista de tramitações não pode estar vazia')
        
        if len(cod_tramitacoes) > 100:
            raise ValidationError('Máximo de 100 tramitações por lote')
        
        codigos_validos = []
        for cod in cod_tramitacoes:
            try:
                cod_int = int(cod)
                if cod_int > 0:
                    codigos_validos.append(cod_int)
            except (ValueError, TypeError):
                logger.warning(f"Código de tramitação inválido ignorado: {cod}")
        
        return codigos_validos


class TramitacaoAnexarArquivoLoteView(GrokView, TramitacaoAPIBase):
    """View para anexar arquivo em lote"""
    
    context(Interface)
    name('tramitacao_anexar_arquivo_lote')
    require('zope2.View')
    
    def render(self):
        try:
            tipo = validar_tipo_tramitacao(self._obter_parametro('tipo', 'MATERIA'))
            cod_tramitacoes = self._validar_lista_cod_tramitacoes()
            arquivo = self.request.form.get('arquivo')
            
            if not arquivo or not hasattr(arquivo, 'read'):
                return self._resposta_json({'erro': 'Arquivo não fornecido'})
            
            arquivo.seek(0)
            arquivo_bytes = arquivo.read()
            if not arquivo_bytes.startswith(b'%PDF'):
                return self._resposta_json({'erro': 'Arquivo não é um PDF válido'})
            
            import tasks
            import base64
            juntar_pdfs_lote_task = tasks.juntar_pdfs_lote_task
            portal_url = str(self.context.absolute_url())
            site_path = 'sagl'
            user_id = self._get_current_user_id()
            
            arquivo_base64 = base64.b64encode(arquivo_bytes).decode('utf-8')
            task_kwargs = {
                'tipo': str(tipo),
                'cod_tramitacoes': [int(cod) for cod in cod_tramitacoes],
                'arquivo_pdf_base64': arquivo_base64,
                'nome_arquivo': getattr(arquivo, 'filename', 'anexo.pdf'),
                'portal_url': str(portal_url),
                'site_path': str(site_path)
            }
            if user_id:
                task_kwargs['user_id'] = str(user_id)
            
            import json
            try:
                json.dumps(task_kwargs)
            except (TypeError, ValueError) as e:
                logger.error(f"Erro: kwargs não são serializáveis: {e}")
                raise
            
            task_result = juntar_pdfs_lote_task.apply_async(kwargs=task_kwargs)
            task_id = task_result.id if hasattr(task_result, 'id') else getattr(task_result, 'task_id', None)
            if not task_id:
                raise Exception('Falha ao obter task_id')
            
            return self._resposta_json({
                'task_id': task_id,
                'status': 'PENDING',
                'message': f'Junção de anexo em lote iniciada para {len(cod_tramitacoes)} tramitações',
                'total': len(cod_tramitacoes),
                'monitor_url': f"{portal_url}/@@tramitacao_anexar_arquivo_lote_status?task_id={task_id}",
                'tipo': tipo
            })
        except Exception as e:
            logger.error(f"Erro ao disparar junção de anexo em lote: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})
    
    def _get_current_user_id(self):
        try:
            from AccessControl import getSecurityManager
            user = getSecurityManager().getUser()
            if user:
                return user.getId()
        except:
            pass
        return None
    
    def _validar_lista_cod_tramitacoes(self):
        """Valida e retorna lista de códigos de tramitação"""
        cod_tramitacoes = self._obter_parametro('cod_tramitacoes', [])
        
        if isinstance(cod_tramitacoes, str):
            import json
            try:
                cod_tramitacoes = json.loads(cod_tramitacoes)
            except:
                cod_tramitacoes = [cod_tramitacoes]
        
        if not isinstance(cod_tramitacoes, list):
            raise ValidationError('cod_tramitacoes deve ser uma lista')
        
        if len(cod_tramitacoes) == 0:
            raise ValidationError('Lista de tramitações não pode estar vazia')
        
        if len(cod_tramitacoes) > 100:
            raise ValidationError('Máximo de 100 tramitações por lote')
        
        codigos_validos = []
        for cod in cod_tramitacoes:
            try:
                cod_int = int(cod)
                if cod_int > 0:
                    codigos_validos.append(cod_int)
            except (ValueError, TypeError):
                logger.warning(f"Código de tramitação inválido ignorado: {cod}")
        
        return codigos_validos


class TramitacaoLoteStatusView(GrokView, TramitacaoAPIBase):
    """View para consultar status de processamento em lote (usando task_monitor.get_task_status)"""
    
    context(Interface)
    name('tramitacao_despacho_pdf_lote_status')
    require('zope2.View')
    
    def render(self):
        try:
            task_id = self._obter_parametro('task_id')
            if not task_id:
                return self._resposta_json({'erro': 'task_id é obrigatório'})
            
            from tasks_folder.task_monitor import get_task_status
            status = get_task_status(task_id)
            
            if status:
                return self._resposta_json(status)
            return self._resposta_json({'status': 'UNKNOWN', 'error': 'Task não encontrada', 'task_id': task_id})
        except Exception as e:
            logger.error(f"Erro ao consultar status do lote: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})


class TramitacaoAnexarArquivoLoteStatusView(GrokView, TramitacaoAPIBase):
    """View para consultar status de junção de anexo em lote (usando task_monitor.get_task_status)"""
    
    context(Interface)
    name('tramitacao_anexar_arquivo_lote_status')
    require('zope2.View')
    
    def render(self):
        try:
            task_id = self._obter_parametro('task_id')
            if not task_id:
                return self._resposta_json({'erro': 'task_id é obrigatório'})
            
            from tasks_folder.task_monitor import get_task_status
            status = get_task_status(task_id)
            
            if status:
                # Se task concluída com sucesso, inclui PDFs base64 nos resultados
                if status.get('status') == 'SUCCESS':
                    meta = status.get('meta', {})
                    resultados = meta.get('resultados', [])
                    for resultado in resultados:
                        if resultado.get('status') == 'SUCCESS' and 'pdf_base64' in resultado:
                            # PDF base64 já está no resultado
                            pass
                return self._resposta_json(status)
            return self._resposta_json({'status': 'UNKNOWN', 'error': 'Task não encontrada', 'task_id': task_id})
        except Exception as e:
            logger.error(f"Erro ao consultar status do lote: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})


class TramitacaoAnexarArquivoLoteSalvarView(GrokView, TramitacaoAPIBase):
    """View que salva os PDFs juntados pela task em lote no repositório Zope"""
    context(Interface)
    name('tramitacao_anexar_arquivo_lote_salvar')
    require('zope2.View')
    
    def render(self):
        try:
            task_id = self._obter_parametro('task_id')
            if not task_id:
                return self._resposta_json({'erro': 'task_id é obrigatório'})
            
            # Busca resultado da task
            from tasks_folder.task_monitor import get_task_status
            status = get_task_status(task_id)
            
            if not status:
                return self._resposta_json({'erro': 'Task não encontrada', 'task_id': task_id})
            
            if status.get('status') != 'SUCCESS':
                return self._resposta_json({
                    'erro': f"Task não concluída com sucesso. Status: {status.get('status')}",
                    'status': status.get('status')
                })
            
            # Extrai resultados do lote
            # Tenta obter de meta primeiro (do último update_state), depois de result (retorno da função)
            meta = status.get('meta', {})
            resultados = meta.get('resultados', [])
            
            # Se não encontrou em meta, tenta em result (retorno direto da função)
            if not resultados:
                result = status.get('result', {})
                if isinstance(result, dict):
                    resultados = result.get('resultados', [])
            
            if not resultados:
                # Log para debug
                logger.warning(f"Nenhum resultado encontrado na task {task_id}. Status completo: {status}")
                return self._resposta_json({'erro': 'Nenhum resultado encontrado na task'})
            
            # Salva cada PDF no repositório Zope
            # Resolve o site real do contexto Zope
            site_real = self._resolver_site_real()
            
            from .pdf.generator import TramitacaoPDFGenerator
            generator = TramitacaoPDFGenerator(session=None, contexto_zope=site_real)
            import base64
            
            salvos = []
            erros = []
            
            for resultado in resultados:
                if resultado.get('status') == 'SUCCESS':
                    try:
                        cod_tramitacao = resultado.get('cod_tramitacao')
                        pdf_base64 = resultado.get('pdf_base64')
                        tipo = resultado.get('tipo', 'MATERIA')
                        
                        if not pdf_base64:
                            erros.append({
                                'cod_tramitacao': cod_tramitacao,
                                'erro': 'PDF não encontrado no resultado'
                            })
                            continue
                        
                        # Decodifica e salva
                        pdf_bytes = base64.b64decode(pdf_base64)
                        pdf_filename = f"{cod_tramitacao}_tram.pdf"
                        
                        # Acessa repositório e atualiza PDF
                        if tipo == 'MATERIA':
                            repo = site_real.sapl_documentos.materia.tramitacao
                        else:
                            repo = site_real.sapl_documentos.administrativo.tramitacao
                        
                        if hasattr(repo, pdf_filename):
                            pdf_principal = getattr(repo, pdf_filename)
                            pdf_principal.update_data(pdf_bytes)
                        else:
                            # Se não existe, cria
                            repo.manage_addFile(
                                id=pdf_filename,
                                file=pdf_bytes,
                                content_type='application/pdf',
                                title=f'Tramitação de {"processo legislativo" if tipo == "MATERIA" else "processo administrativo"}'
                            )
                        
                        salvos.append(cod_tramitacao)
                    except Exception as e:
                        erros.append({
                            'cod_tramitacao': resultado.get('cod_tramitacao'),
                            'erro': str(e)
                        })
            
            return self._resposta_json({
                'success': True,
                'message': f'{len(salvos)} PDF(s) juntados salvos com sucesso',
                'salvos': len(salvos),
                'erros': len(erros),
                'cod_tramitacoes_salvos': salvos,
                'erros_detalhes': erros
            })
            
        except Exception as e:
            logger.error(f"Erro ao salvar PDFs juntados em lote: {e}", exc_info=True)
            return self._resposta_json({'erro': f'Erro: {str(e)}'})
            return self._resposta_json({'erro': f'Erro: {str(e)}'})
