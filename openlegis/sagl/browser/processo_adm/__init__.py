# -*- coding: utf-8 -*-
"""
Módulo de processo administrativo e pasta digital.
Contém views, serviços e utilitários relacionados à geração e visualização
do processo administrativo integral e pasta digital.
"""
from openlegis.sagl.browser.processo_adm.processo_adm import (
    ProcessoAdmView,
    PaginaProcessoAdmView,
    LimparProcessoAdmView,
    ProcessoAdmTaskExecutor,
    ProcessoAdmStatusView,
    ProcessoAdmCancelView,
    ProcessoAdmAsyncView,
    PDFGenerationError,
)
from openlegis.sagl.browser.processo_adm.processo_adm_utils import (
    get_processo_dir_adm,
    get_processo_dir_hash_adm,
    get_cache_file_path_adm,
    safe_check_file,
    safe_check_files_batch,
    safe_check_file_with_content,
    get_file_size,
    get_file_info_for_hash,
    secure_path_join,
    SecurityError,
    TEMP_DIR_PREFIX_ADM
)
from openlegis.sagl.browser.processo_adm.processo_adm_service import ProcessoAdmService
from openlegis.sagl.browser.processo_adm.pasta_digital import (
    PastaDigitalAdmView,
    PastaDigitalAdmDataView,
    verificar_permissao_acesso,
    registrar_acesso_documento,
)
from openlegis.sagl.browser.processo_adm.processo_adm import (
    coletar_cientificacoes_com_nomes,
    gerar_folha_cientificacao_pdf,
    get_cached_styles,
    build_header_cientificacoes,
    add_footer_cientificacoes,
)

__all__ = [
    # Views
    'ProcessoAdmView',
    'PaginaProcessoAdmView',
    'LimparProcessoAdmView',
    'ProcessoAdmTaskExecutor',
    'ProcessoAdmStatusView',
    'ProcessoAdmCancelView',
    'ProcessoAdmAsyncView',
    'PastaDigitalAdmView',
    'PastaDigitalAdmDataView',
    # Serviços
    'ProcessoAdmService',
    # Utilitários
    'secure_path_join',
    'get_processo_dir_adm',
    'get_processo_dir_hash_adm',
    'get_cache_file_path_adm',
    'safe_check_file',
    'safe_check_files_batch',
    'safe_check_file_with_content',
    'get_file_size',
    'get_file_info_for_hash',
    'TEMP_DIR_PREFIX_ADM',
    # Permissões
    'verificar_permissao_acesso',
    'registrar_acesso_documento',
    # Funções auxiliares
    'coletar_cientificacoes_com_nomes',
    'gerar_folha_cientificacao_pdf',
    'get_cached_styles',
    'build_header_cientificacoes',
    'add_footer_cientificacoes',
    # Exceções
    'PDFGenerationError',
    'SecurityError',
]
