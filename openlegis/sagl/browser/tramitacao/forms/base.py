"""
Classes base para construção de formulários de tramitação
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import html


class FormField(ABC):
    """Classe abstrata base para campos de formulário"""
    
    def __init__(
        self,
        name: str,
        label: str,
        value: Any = None,
        required: bool = False,
        help_text: Optional[str] = None,
        css_class: Optional[str] = None,
        **kwargs
    ):
        self.name = name
        self.label = label
        self.value = value
        self.required = required
        self.help_text = help_text
        self.css_class = css_class or ''
        self.attrs = kwargs
        self.id = kwargs.get('id') or f'field_{name}'
    
    def _escape(self, text: str) -> str:
        """Escapa HTML"""
        return html.escape(str(text)) if text else ''
    
    def _render_label(self) -> str:
        """Renderiza label do campo"""
        required_mark = ''
        required_aria = ''
        if self.required:
            required_mark = ' <span class="text-danger" aria-label="obrigatório">*</span>'
            required_aria = ' <span class="visually-hidden">(obrigatório)</span>'
        
        html_label = f'<label class="form-label" for="{self.id}">'
        html_label += self._escape(self.label)
        html_label += required_mark
        html_label += required_aria
        html_label += '</label>'
        
        if self.help_text:
            html_label += f'<small class="form-text text-muted d-block" id="{self.id}_help">{self._escape(self.help_text)}</small>'
        
        return html_label
    
    def _get_attrs_string(self, extra_attrs: Optional[Dict] = None) -> str:
        """Gera string de atributos HTML"""
        attrs = {
            'id': self.id,
            'name': self.name,
            'class': f'form-control {self.css_class}'.strip(),
            **self.attrs
        }
        
        if extra_attrs:
            attrs.update(extra_attrs)
        
        if self.required:
            attrs['required'] = True
            attrs['aria-required'] = 'true'
        
        # Remove None values
        attrs = {k: v for k, v in attrs.items() if v is not None and v is not False}
        
        # Converte para string
        attrs_str = ' '.join([
            f'{k}="{html.escape(str(v))}"' if not isinstance(v, bool) else f'{k}'
            for k, v in attrs.items()
        ])
        
        return attrs_str
    
    @abstractmethod
    def render(self) -> str:
        """Renderiza o campo"""
        pass


class FormSection:
    """Representa uma seção do formulário"""
    
    def __init__(
        self,
        id: str,
        title: str,
        icon: Optional[str] = None,
        fields: Optional[List[FormField]] = None,
        css_class: Optional[str] = None
    ):
        self.id = id
        self.title = title
        self.icon = icon
        self.fields = fields or []
        self.css_class = css_class or 'mb-3'
        self._custom_html = None  # HTML customizado para adicionar na seção
    
    def add_field(self, field: FormField):
        """Adiciona um campo à seção"""
        self.fields.append(field)
    
    def render(self) -> str:
        """Renderiza a seção completa"""
        html_section = f'<div class="card {self.css_class}" id="section_{self.id}">'
        
        # Header - altura padronizada para todos os cards
        html_section += f'<div class="card-header bg-light py-2">'
        html_section += '<h6 class="mb-0 d-flex align-items-center small">'
        if self.icon:
            html_section += f'<i class="mdi {self.icon} me-1" aria-hidden="true"></i>'
        html_section += f'<span>{html.escape(self.title)}</span>'
        html_section += '</h6>'
        html_section += '</div>'
        
        # Body - reduz padding para seções compactas
        body_padding = 'p-2' if self.css_class == 'mb-2' else 'p-3'
        html_section += f'<div class="card-body {body_padding}">'
        html_section += '<div class="row g-2">'  # Reduz gap para layout mais compacto
        
        # Renderiza HTML customizado primeiro (se existir)
        if hasattr(self, '_custom_html') and self._custom_html:
            html_section += self._custom_html
        
        # Renderiza campos
        for field in self.fields:
            html_section += field.render()
        
        html_section += '</div>'  # row
        html_section += '</div>'  # card-body
        html_section += '</div>'  # card
        
        return html_section


class FormBuilder:
    """Builder para construção de formulários"""
    
    def __init__(self, form_id: str, form_class: str = 'needs-validation tramitacao-form-modern'):
        self.form_id = form_id
        self.form_class = form_class
        self.sections: List[FormSection] = []
        self.hidden_fields: List[FormField] = []
        self.header_html: Optional[str] = None
        self.footer_html: Optional[str] = None
    
    def set_header(self, html: str):
        """Define HTML do cabeçalho do formulário"""
        self.header_html = html
    
    def set_footer(self, html: str):
        """Define HTML do rodapé do formulário"""
        self.footer_html = html
    
    def add_section(
        self,
        id: str,
        title: str,
        icon: Optional[str] = None,
        css_class: Optional[str] = None
    ) -> FormSection:
        """Adiciona uma seção ao formulário"""
        section = FormSection(id, title, icon, css_class=css_class)
        self.sections.append(section)
        return section
    
    def add_hidden_field(self, field: FormField):
        """Adiciona um campo hidden"""
        self.hidden_fields.append(field)
    
    def render(self) -> str:
        """Renderiza o formulário completo"""
        # Comentário para identificar novo renderizador
        html_form = '<!-- Formulário gerado pelo novo renderizador de componentes -->\n'
        html_form += f'<form class="{self.form_class}" id="{self.form_id}" method="post" enctype="multipart/form-data" novalidate>'
        
        # Hidden fields
        for field in self.hidden_fields:
            html_form += field.render()
        
        # Header
        if self.header_html:
            html_form += self.header_html
        
        # Sections
        for section in self.sections:
            html_form += section.render()
        
        # Footer
        if self.footer_html:
            html_form += self.footer_html
        
        html_form += '</form>'
        
        return html_form
