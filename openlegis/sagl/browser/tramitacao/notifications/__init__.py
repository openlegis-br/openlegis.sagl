# -*- coding: utf-8 -*-
"""Módulo de notificações por e-mail de tramitação"""

from .templates import (
    gerar_html_notificacao_autor,
    gerar_html_notificacao_acompanhamento_materia,
    gerar_html_notificacao_documento
)
from .email_sender import TramitacaoEmailSender

__all__ = [
    'gerar_html_notificacao_autor',
    'gerar_html_notificacao_acompanhamento_materia',
    'gerar_html_notificacao_documento',
    'TramitacaoEmailSender'
]
