"""
Renderizador de formulários de tramitação usando componentes
"""

from typing import Dict, List, Optional, Any
from .base import FormBuilder, FormSection
from .fields import (
    ReadonlyField,
    Select2Field,
    DateField,
    RadioGroupField,
    FileField,
    TextareaField,
    HiddenField
)
import html
import logging

logger = logging.getLogger(__name__)

# Importa dependências para buscar unidade no banco
try:
    from openlegis.sagl.db_session import db_session_readonly
    from openlegis.sagl.models.models import UnidadeTramitacao
    from sqlalchemy.orm import selectinload
    
    # Função auxiliar para obter nome da unidade
    def _get_nome_unidade_tramitacao(unidade):
        """Obtém o nome da unidade de tramitação"""
        if not unidade:
            return ''
        if unidade.comissao:
            return unidade.comissao.nom_comissao or ''
        if unidade.orgao:
            return unidade.orgao.nom_orgao or ''
        if unidade.parlamentar:
            return unidade.parlamentar.nom_parlamentar or ''
        return ''
    
    CAN_FETCH_UNIT = True
except ImportError:
    CAN_FETCH_UNIT = False
    logger.warning("Não é possível buscar unidade no banco - funcionalidade limitada")


class TramitacaoFormRenderer:
    """Renderizador de formulários de tramitação"""
    
    @staticmethod
    def render_individual_form(
        tipo: str,
        cod_entidade: int,
        cod_tramitacao: Optional[int],
        cod_usuario: Optional[int],
        nome_usuario: str,
        unidades_usuario: List[Dict],
        dados_tramitacao: Dict,
        dat_tramitacao: str,
        info_processo: Optional[Dict] = None,
        unidades_destino: Optional[List[Dict]] = None,
        status_opcoes: Optional[List[Dict]] = None,
        link_pdf_despacho: Optional[str] = None,
        pdf_gerado: bool = False,
        contexto_zope: Optional[Any] = None,
        portal_url: Optional[str] = None,
        usuario_assinou: bool = False
    ) -> str:
        """
        Renderiza formulário individual de tramitação
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_entidade: Código da matéria ou documento
            cod_tramitacao: Código da tramitação (se edição)
            cod_usuario: Código do usuário
            nome_usuario: Nome do usuário
            unidades_usuario: Lista de unidades do usuário
            dados_tramitacao: Dados da tramitação (se edição)
            dat_tramitacao: Data da tramitação
            info_processo: Informações do processo
        
        Returns:
            HTML do formulário
        """
        builder = FormBuilder('tramitacao_individual_form', 'needs-validation')
        
        # Hidden fields
        builder.add_hidden_field(HiddenField('hdn_tipo_tramitacao', tipo))
        if tipo == 'MATERIA':
            builder.add_hidden_field(HiddenField('hdn_cod_materia', cod_entidade))
        else:
            builder.add_hidden_field(HiddenField('hdn_cod_documento', cod_entidade))
        builder.add_hidden_field(HiddenField('hdn_cod_usuario_local', cod_usuario, id='hdn_cod_usuario_local'))
        builder.add_hidden_field(HiddenField('hdn_dat_tramitacao', dat_tramitacao))
        builder.add_hidden_field(HiddenField('hdn_file', '0', id='hdn_file'))
        if cod_tramitacao:
            builder.add_hidden_field(HiddenField('hdn_cod_tramitacao', cod_tramitacao))
        
        # Header: Informações do processo
        if info_processo:
            header_html = TramitacaoFormRenderer._render_process_header(info_processo, tipo)
            builder.set_header(header_html)
        
        # Seção: Origem
        section_origem = builder.add_section('origem', 'Origem', 'mdi-arrow-up-circle')
        
        # Data da Tramitação
        section_origem.add_field(
            ReadonlyField(
                'txt_dat_tramitacao',
                'Data da Tramitação',
                value=dat_tramitacao,
                required=True,
                icon='mdi-calendar',
                col_class='col-12 col-md-4'
            )
        )
        
        # Unidade de Origem
        cod_unid_local = dados_tramitacao.get('cod_unid_tram_local') if dados_tramitacao else None
        nome_unidade = TramitacaoFormRenderer._get_nome_unidade(cod_unid_local, unidades_usuario) if cod_unid_local else None
        
        # Cria campo readonly com código no hidden e nome no display
        section_origem.add_field(
            ReadonlyField(
                'lst_cod_unid_tram_local',
                'Unidade de Origem',
                value=cod_unid_local,  # Código para o campo hidden
                display_value=nome_unidade or (f'Unidade {cod_unid_local}' if cod_unid_local else ''),  # Nome para exibição
                required=True,
                col_class='col-12 col-md-5'
            )
        )
        
        # Usuário de Origem
        section_origem.add_field(
            ReadonlyField(
                'txt_nom_usuario',
                'Usuário de Origem',
                value=nome_usuario,
                required=True,
                col_class='col-12 col-md-3'
            )
        )
        
        # Seção: Destino
        section_destino = builder.add_section('destino', 'Destino', 'mdi-arrow-down-circle')
        
        # Unidade de Destino
        # Só passa valor se for edição de tramitação existente (cod_tramitacao presente)
        # Para nova tramitação, sempre vem vazio
        cod_unid_tram_dest_value = None
        if dados_tramitacao and dados_tramitacao.get('cod_tramitacao'):
            cod_unid_tram_dest_value = dados_tramitacao.get('cod_unid_tram_dest')
        
        # Converte unidades_destino para formato de opções (dicionários com 'value' e 'label')
        unid_dest_options = []
        if unidades_destino:
            unid_dest_options = [{'value': unid['id'], 'label': unid['name']} for unid in unidades_destino]
        
        section_destino.add_field(
            Select2Field(
                'lst_cod_unid_tram_dest',
                'Unidade de Destino',
                options=unid_dest_options,
                value=cod_unid_tram_dest_value,
                required=True,
                placeholder='Selecione a unidade de destino...',
                load_url='/tramitacao_unidades_json',
                load_on='field_lst_cod_unid_tram_local',
                col_class='col-12 col-md-6'
            )
        )
        
        # Usuário de Destino
        # Só passa valor se for edição de tramitação existente (cod_tramitacao presente)
        # Para nova tramitação, sempre vem vazio
        cod_usuario_dest_value = None
        if dados_tramitacao and dados_tramitacao.get('cod_tramitacao'):
            cod_usuario_dest_value = dados_tramitacao.get('cod_usuario_dest')
        
        section_destino.add_field(
            Select2Field(
                'lst_cod_usuario_dest',
                'Usuário de Destino',
                options=[],
                value=cod_usuario_dest_value,
                required=False,
                placeholder='Selecione a unidade de destino primeiro',
                load_url='/tramitacao_usuarios_json',
                load_on='field_lst_cod_unid_tram_dest',
                col_class='col-12 col-md-6'
            )
        )
        
        # Seção: Status e Prazo
        section_status = builder.add_section('status', 'Status e Prazo', 'mdi-information-outline')
        
        # Status
        # Só passa valor se for edição de tramitação existente (cod_tramitacao presente)
        # Para nova tramitação, sempre vem vazio
        cod_status_value = None
        if dados_tramitacao and dados_tramitacao.get('cod_tramitacao'):
            cod_status_value = dados_tramitacao.get('cod_status')
        
        # Converte status_opcoes para formato de opções (dicionários com 'value' e 'label')
        status_options = []
        if status_opcoes:
            status_options = [{'value': status['id'], 'label': status['name']} for status in status_opcoes]
        
        section_status.add_field(
            Select2Field(
                'lst_cod_status',
                'Status',
                options=status_options,
                value=cod_status_value,
                required=True,
                placeholder='Selecione o status...',
                load_url='/tramitacao_status_json',
                load_on='field_lst_cod_unid_tram_local',
                col_class='col-12 col-md-6'
            )
        )
        
        # Data de Fim de Prazo
        dat_fim_prazo = dados_tramitacao.get('dat_fim_prazo', '') if dados_tramitacao else ''
        section_status.add_field(
            DateField(
                'txt_dat_fim_prazo',
                'Data de Fim de Prazo',
                value=dat_fim_prazo,
                required=False,
                placeholder='dd/mm/aaaa',
                min_date='today',
                col_class='col-12 col-md-3'
            )
        )
        
        # Urgente (apenas para MATERIA)
        if tipo == 'MATERIA':
            ind_urgencia = dados_tramitacao.get('ind_urgencia', 0) if dados_tramitacao else 0
            section_status.add_field(
                RadioGroupField(
                    'rad_ind_urgencia',
                    'Urgente?',
                    options=[
                        ('1', 'Sim', ind_urgencia == 1),
                        ('0', 'Não', ind_urgencia == 0)
                    ],
                    required=True,
                    inline=True,
                    col_class='col-12 col-md-3'
                )
            )
        
        # Seção: Despacho em PDF
        section_pdf = builder.add_section('pdf', 'Despacho em PDF', 'mdi-file-pdf-box', css_class='mb-3')
        
        # Link do PDF do despacho (se existir) - adiciona antes das opções
        if link_pdf_despacho and cod_tramitacao:
            # Verifica se assinatura ICP-Brasil está disponível
            assinatura_disponivel = False
            try:
                if contexto_zope:
                    restpki_token = contexto_zope.sapl_documentos.props_sagl.restpki_access_token
                    assinatura_disponivel = bool(restpki_token and restpki_token.strip())
            except (AttributeError, Exception) as e:
                logger.debug(f"Erro ao verificar restpki_access_token no renderizador: {e}")
                assinatura_disponivel = False
            
            # Determina tipo_doc e portal_url
            tipo_doc = 'tramitacao' if tipo == 'MATERIA' else 'tramitacao_adm'
            portal_url_str = portal_url or ''
            cod_tramitacao_str = str(cod_tramitacao) if cod_tramitacao else ''
            
            # Ícone do botão Visualizar: diferenciado se usuário assinou
            # Usa ícone com check se assinado, senão ícone padrão de PDF
            icone_visualizar = 'mdi-file-check' if usuario_assinou else 'mdi-file-pdf-box'
            classe_botao_visualizar = 'btn-success' if usuario_assinou else 'btn-primary'
            titulo_visualizar = 'PDF assinado por você' if usuario_assinou else 'Visualizar PDF'
            
            # Botões de Assinatura Digital ICP-Brasil (se disponível)
            botoes_assinatura_html = ''
            if assinatura_disponivel and portal_url_str and cod_tramitacao_str:
                # Botão "Assinar" - omitido se usuário já assinou
                botao_assinar_html = ''
                if not usuario_assinou:
                    botao_assinar_html = f'''
                            <button type="button" class="btn btn-primary" 
                                    data-bs-toggle="modal" 
                                    data-bs-target="#iFrameModal" 
                                    data-title="Assinar Digitalmente" 
                                    data-src="{html.escape(portal_url_str)}/generico/assinador/pades-signature_html?codigo={html.escape(cod_tramitacao_str)}&tipo_doc={html.escape(tipo_doc)}&modal=1" 
                                    title="Assinar PDF do despacho com certificado digital ICP-Brasil"
                                    data-cod-tramitacao="{html.escape(cod_tramitacao_str)}">
                                <i class="fas fa-file-signature me-1"></i> Assinar
                            </button>'''
                
                # Botão "Assinaturas" - sempre exibido (para solicitar assinatura de outros)
                botoes_assinatura_html = f'''
                            {botao_assinar_html}
                            <button type="button" class="btn btn-primary" 
                                    data-bs-toggle="modal" 
                                    data-bs-target="#iFrameModal" 
                                    data-title="Assinaturas Digitais" 
                                    data-src="{html.escape(portal_url_str)}/cadastros/assinatura/assinatura_solicitar_form?codigo={html.escape(cod_tramitacao_str)}&tipo_doc={html.escape(tipo_doc)}&modal=1" 
                                    title="Visualizar status das assinaturas digitais"
                                    data-cod-tramitacao="{html.escape(cod_tramitacao_str)}">
                                <i class="fas fa-file-signature me-1"></i> Assinaturas
                            </button>'''
            
            pdf_gerado_html = ''
            if pdf_gerado:
                pdf_gerado_html = '<div class="mt-2"><small class="text-success"><i class="mdi mdi-check-circle me-1"></i>PDF gerado com sucesso!</small></div>'
            
            pdf_link_html = f'''
            <div class="col-12 mb-3">
                <div class="alert alert-info mb-0 py-2" role="alert">
                    <div class="d-flex align-items-center justify-content-between flex-wrap">
                        <div class="d-flex align-items-center">
                            <i class="mdi mdi-file-pdf-box me-2 text-danger" style="font-size: 1.2rem;"></i>
                            <span class="small">PDF do despacho disponível:</span>
                        </div>
                        <div class="btn-group btn-group-sm mt-2 mt-md-0" role="group">
                            <a href="{html.escape(link_pdf_despacho)}" 
                               id="btn_visualizar_pdf_tramitacao"
                               target="_blank" 
                               class="btn {classe_botao_visualizar}"
                               title="{titulo_visualizar}"
                               data-cod-tramitacao="{html.escape(cod_tramitacao_str)}"
                               data-usuario-assinou="{str(usuario_assinou).lower()}"
                               data-link-pdf="{html.escape(link_pdf_despacho)}">
                                <i class="mdi {icone_visualizar} me-1"></i> Visualizar
                            </a>{botoes_assinatura_html}
                        </div>
                    </div>
                    {pdf_gerado_html}
                </div>
            </div>
            '''
            # Armazena HTML customizado para ser renderizado na seção
            section_pdf._custom_html = pdf_link_html
        
        # Opções de PDF
        pdf_options = [
            ('G', 'Gerar', True),
            ('S', 'Anexar', False)
        ]
        if cod_tramitacao:
            pdf_options.append(('M', 'Manter', False))
        
        # Radio buttons em linha
        section_pdf.add_field(
            RadioGroupField(
                'radTI',
                'Opção de PDF',
                options=pdf_options,
                required=True,
                inline=True,
                col_class='col-12 col-md-4'
            )
        )
        
        # Campo de arquivo (aparece apenas quando "Anexar" está selecionado)
        section_pdf.add_field(
            FileField(
                'file_nom_arquivo',
                'Arquivo PDF',
                accept='application/pdf',
                required=False,
                help_text='Tamanho máximo: 10MB',
                disabled=True,
                max_size_mb=10,
                col_class='col-12 col-md-8'
            )
        )
        
        # Seção: Texto do Despacho
        section_texto = builder.add_section('texto', 'Texto do Despacho', 'mdi-text')
        
        txt_tramitacao = dados_tramitacao.get('txt_tramitacao', '') if dados_tramitacao else ''
        section_texto.add_field(
            TextareaField(
                'txa_txt_tramitacao',
                'Texto do Despacho',
                value=txt_tramitacao,
                required=False,
                rows=6,
                tinymce=True,
                col_class='col-12'
            )
        )
        
        # Nota: Script do modal é gerenciado globalmente no js_slot.dtml e tramitacao_email_style.js
        # Não adicionar script aqui pois innerHTML não executa scripts automaticamente
        
        return builder.render()
    
    @staticmethod
    def render_lote_form(
        tipo: str,
        processos: List[str],
        cod_usuario: Optional[int],
        nome_usuario: str,
        unidades_usuario: List[Dict],
        dat_tramitacao: str,
        cod_unid_tram_local: Optional[int] = None,
        unidades_destino: Optional[List[Dict]] = None,
        status_opcoes: Optional[List[Dict]] = None
    ) -> str:
        """
        Renderiza formulário em lote de tramitação
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            processos: Lista de códigos de processos
            cod_usuario: Código do usuário
            nome_usuario: Nome do usuário
            unidades_usuario: Lista de unidades do usuário
            dat_tramitacao: Data da tramitação
            cod_unid_tram_local: Código da unidade de origem
        
        Returns:
            HTML do formulário
        """
        builder = FormBuilder('tramitacao_lote_form', 'needs-validation')
        
        # Hidden fields
        builder.add_hidden_field(HiddenField('hdn_tipo_tramitacao', tipo))
        builder.add_hidden_field(HiddenField('hdn_cod_usuario_local', cod_usuario, id='hdn_cod_usuario_local'))
        builder.add_hidden_field(HiddenField('hdn_dat_tramitacao', dat_tramitacao))
        builder.add_hidden_field(HiddenField('hdn_file', '0', id='hdn_file'))
        
        # Header: Informações dos processos (mesmo estilo do individual)
        tipo_label = 'Processos Legislativos' if tipo == 'MATERIA' else 'Processos Administrativos'
        header_html = f'''
        <div class="alert alert-info mb-3 border-0 shadow-sm py-2" role="alert">
            <div class="d-flex align-items-center">
                <i class="mdi mdi-file-multiple-outline me-2 fs-4 text-primary" aria-hidden="true"></i>
                <div class="d-flex align-items-center flex-wrap">
                    <span class="text-muted small me-2">{tipo_label}:</span>
                    <span id="num-processos-selecionados-lote" class="badge bg-primary me-2">{len(processos)}</span>
                    <span class="text-muted small">processo(s) selecionado(s)</span>
                </div>
            </div>
        </div>
        '''
        builder.set_header(header_html)
        
        # Seção: Origem (igual ao individual)
        section_origem = builder.add_section('origem', 'Origem', 'mdi-arrow-up-circle')
        
        section_origem.add_field(
            ReadonlyField(
                'txt_dat_tramitacao',
                'Data da Tramitação',
                value=dat_tramitacao,
                required=True,
                icon='mdi-calendar',
                col_class='col-12 col-md-4'
            )
        )
        
        nome_unidade = TramitacaoFormRenderer._get_nome_unidade(cod_unid_tram_local, unidades_usuario) if cod_unid_tram_local else None
        
        # Cria campo readonly com código no hidden e nome no display
        unidade_field = ReadonlyField(
            'lst_cod_unid_tram_local',
            'Unidade de Origem',
            value=cod_unid_tram_local,  # Código para o campo hidden
            required=True,
            col_class='col-12 col-md-5'
        )
        # Sobrescreve o valor de exibição para mostrar o nome
        unidade_field.display_value = nome_unidade or f'Unidade {cod_unid_tram_local}' if cod_unid_tram_local else ''
        section_origem.add_field(unidade_field)
        
        section_origem.add_field(
            ReadonlyField(
                'txt_nom_usuario',
                'Usuário de Origem',
                value=nome_usuario,
                required=True,
                col_class='col-12 col-md-3'
            )
        )
        
        # Seção: Destino (igual ao individual)
        section_destino = builder.add_section('destino', 'Destino', 'mdi-arrow-down-circle')
        
        # Unidade de Destino (sempre vazio para nova tramitação)
        # Converte unidades_destino para formato de opções (dicionários com 'value' e 'label')
        unid_dest_options = []
        if unidades_destino:
            unid_dest_options = [{'value': unid['id'], 'label': unid['name']} for unid in unidades_destino]
        
        section_destino.add_field(
            Select2Field(
                'lst_cod_unid_tram_dest',
                'Unidade de Destino',
                options=unid_dest_options,
                value=None,
                required=True,
                placeholder='Selecione a unidade de destino...',
                load_url='/tramitacao_unidades_json',
                load_on='field_lst_cod_unid_tram_local',
                col_class='col-12 col-md-6'
            )
        )
        
        # Usuário de Destino (sempre vazio para nova tramitação)
        section_destino.add_field(
            Select2Field(
                'lst_cod_usuario_dest',
                'Usuário de Destino',
                options=[],
                value=None,
                required=False,
                placeholder='Selecione a unidade de destino primeiro',
                load_url='/tramitacao_usuarios_json',
                load_on='field_lst_cod_unid_tram_dest',
                col_class='col-12 col-md-6'
            )
        )
        
        # Seção: Status e Prazo (igual ao individual)
        section_status = builder.add_section('status', 'Status e Prazo', 'mdi-information-outline')
        
        # Status (sempre vazio para nova tramitação)
        # Converte status_opcoes para formato de opções (dicionários com 'value' e 'label')
        status_options = []
        if status_opcoes:
            status_options = [{'value': status['id'], 'label': status['name']} for status in status_opcoes]
        
        section_status.add_field(
            Select2Field(
                'lst_cod_status',
                'Status',
                options=status_options,
                value=None,
                required=True,
                placeholder='Selecione o status...',
                load_url='/tramitacao_status_json',
                load_on='field_lst_cod_unid_tram_local',
                col_class='col-12 col-md-6'
            )
        )
        
        section_status.add_field(
            DateField(
                'txt_dat_fim_prazo',
                'Data de Fim de Prazo',
                required=False,
                placeholder='dd/mm/aaaa',
                min_date='today',
                col_class='col-12 col-md-3'
            )
        )
        
        if tipo == 'MATERIA':
            section_status.add_field(
                RadioGroupField(
                    'rad_ind_urgencia',
                    'Urgente?',
                    options=[
                        ('1', 'Sim', False),
                        ('0', 'Não', True)
                    ],
                    required=True,
                    inline=True,
                    col_class='col-12 col-md-3'
                )
            )
        
        # Seção: Despacho em PDF (sem opção "Manter")
        section_pdf = builder.add_section('pdf', 'Despacho em PDF', 'mdi-file-pdf-box', css_class='mb-3')
        
        # Radio buttons em linha
        section_pdf.add_field(
            RadioGroupField(
                'radTI',
                'Opção de PDF',
                options=[
                    ('G', 'Gerar', True),
                    ('S', 'Anexar', False)
                ],
                required=True,
                inline=True,
                col_class='col-12 col-md-4'
            )
        )
        
        # Campo de arquivo (aparece apenas quando "Anexar" está selecionado)
        section_pdf.add_field(
            FileField(
                'file_nom_arquivo',
                'Arquivo PDF',
                accept='application/pdf',
                required=False,
                help_text='Tamanho máximo: 10MB',
                disabled=True,
                max_size_mb=10,
                col_class='col-12 col-md-8'
            )
        )
        
        # Seção: Texto do Despacho
        section_texto = builder.add_section('texto', 'Texto do Despacho', 'mdi-text')
        
        section_texto.add_field(
            TextareaField(
                'txa_txt_tramitacao',
                'Texto do Despacho',
                required=False,
                rows=6,
                tinymce=True,
                col_class='col-12',
                id='field_txa_txt_tramitacao_lote'  # ID específico para formulário em lote
            )
        )
        
        return builder.render()
    
    @staticmethod
    def _render_process_header(info_processo: Dict, tipo: str) -> str:
        """Renderiza cabeçalho com informações do processo"""
        # Monta número completo
        numero_completo = ''
        if info_processo.get('sigla'):
            numero_completo = f'{info_processo["sigla"]} {info_processo["numero"]}/{info_processo["ano"]}'
        else:
            numero_completo = f'{info_processo["numero"]}/{info_processo["ano"]}'
        
        html_header = '''
        <div class="alert alert-info mb-3 border-0 shadow-sm py-2" role="alert">
            <div class="d-flex align-items-center">
                <i class="mdi mdi-file-document-outline me-2 fs-4 text-primary" aria-hidden="true"></i>
                <div class="d-flex align-items-center">
                    <span class="text-muted small me-2">Processo:</span>
                    <span class="fw-semibold text-dark">'''
        html_header += html.escape(numero_completo)
        html_header += '''</span>
                </div>
            </div>
        </div>
        '''
        
        return html_header
    
    @staticmethod
    def _get_nome_unidade(cod_unidade: Optional[int], unidades_usuario: List[Dict]) -> Optional[str]:
        """Obtém nome da unidade"""
        if not cod_unidade:
            return None
        
        # Tenta encontrar nas unidades do usuário
        for unid in unidades_usuario:
            try:
                if int(unid.get('cod', 0)) == int(cod_unidade):
                    return unid.get('nome')
            except (ValueError, TypeError):
                continue
        
        # Se não encontrou, tenta buscar no banco
        if CAN_FETCH_UNIT:
            try:
                with db_session_readonly() as session:
                    unidade = session.query(UnidadeTramitacao).options(
                        selectinload(UnidadeTramitacao.comissao),
                        selectinload(UnidadeTramitacao.orgao),
                        selectinload(UnidadeTramitacao.parlamentar)
                    ).filter(
                        UnidadeTramitacao.cod_unid_tramitacao == int(cod_unidade),
                        UnidadeTramitacao.ind_excluido == 0
                    ).first()
                    
                    if unidade:
                        nome = _get_nome_unidade_tramitacao(unidade)
                        logger.info(f"Unidade {cod_unidade} obtida do banco: {nome}")
                        return nome
            except Exception as e:
                logger.error(f"Erro ao buscar unidade no banco: {e}", exc_info=True)
        
        return None
