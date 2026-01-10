# -*- coding: utf-8 -*-
"""
Módulo de processo legislativo e pasta digital.
Contém views, serviços e utilitários relacionados à geração e visualização
do processo legislativo integral e pasta digital.
"""
from openlegis.sagl.browser.processo_leg.processo_leg import (
    ProcessoLegView,
    PaginaProcessoLeg,
    LimparProcessoLegView,
    ProcessoLegTaskExecutor,
    ProcessoLegStatusView,
    PDFGenerationError,
)
from openlegis.sagl.browser.processo_leg.processo_leg_utils import (
    get_processo_dir,
    get_processo_dir_hash,
    get_cache_file_path,
    safe_check_file,
    safe_check_files_batch,
    safe_check_file_with_content,
    get_file_size,
    get_file_info_for_hash,
    secure_path_join,
    SecurityError,
    TEMP_DIR_PREFIX
)
from openlegis.sagl.browser.processo_leg.processo_leg_service import ProcessoLegService
from openlegis.sagl.browser.processo_leg.pasta_digital import (
    PastaDigitalView,
    PastaDigitalDataView,
    ProcessoLegDownloadDocumentoView
)

__all__ = [
    # Views
    'ProcessoLegView',
    'PaginaProcessoLeg',
    'LimparProcessoLegView',
    'ProcessoLegTaskExecutor',
    'ProcessoLegStatusView',
    'PastaDigitalView',
    'PastaDigitalDataView',
    'ProcessoLegDownloadDocumentoView',
    # Serviços
    'ProcessoLegService',
    # Utilitários
    'secure_path_join',
    'get_processo_dir',
    'get_processo_dir_hash',
    'get_cache_file_path',
    'safe_check_file',
    'safe_check_files_batch',
    'safe_check_file_with_content',
    'get_file_size',
    'get_file_info_for_hash',
    'TEMP_DIR_PREFIX',
    # Exceções
    'PDFGenerationError',
    'SecurityError',
]
