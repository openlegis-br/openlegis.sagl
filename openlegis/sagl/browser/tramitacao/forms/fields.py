"""
Componentes de campos de formulário
"""

from typing import List, Dict, Optional, Any, Tuple
from .base import FormField
import html


class ReadonlyField(FormField):
    """Campo readonly padronizado"""
    
    def __init__(
        self,
        name: str,
        label: str,
        value: Any = None,
        display_value: Optional[str] = None,
        required: bool = False,
        help_text: Optional[str] = None,
        icon: Optional[str] = None,
        **kwargs
    ):
        super().__init__(name, label, value, required, help_text, **kwargs)
        self.icon = icon
        self.css_class = 'form-control-readonly bg-light'
        self.display_value = display_value
    
    def render(self) -> str:
        """Renderiza campo readonly"""
        # Determina tamanho da coluna baseado no contexto
        col_class = self.attrs.get('col_class', 'col-12 col-md-6')
        
        html_field = f'<div class="{col_class} mb-3">'
        html_field += self._render_label()
        
        # Input group se tiver ícone
        if self.icon:
            html_field += '<div class="input-group input-group-sm">'
        
        # Campo hidden para valor real (usando name original para compatibilidade)
        html_field += f'<input type="hidden" name="{self.name}" id="{self.id}" value="{self._escape(self.value)}" />'
        
        # Campo readonly para exibição (com ID diferente para não conflitar)
        display_id = f'{self.id}_display'
        # Usa display_value se fornecido, senão usa value
        display_val = self.display_value if self.display_value is not None else (str(self.value) if self.value else '')
        
        # Monta atributos do campo readonly
        readonly_attrs = []
        readonly_attrs.append(f'type="text"')
        readonly_attrs.append(f'class="form-control form-control-sm {self.css_class}"')
        readonly_attrs.append(f'id="{display_id}"')
        readonly_attrs.append(f'readonly')
        readonly_attrs.append(f'aria-readonly="true"')
        readonly_attrs.append(f'tabindex="-1"')
        readonly_attrs.append(f'aria-label="{html.escape(self.label)} (somente leitura)"')
        readonly_attrs.append(f'value="{html.escape(display_val)}"')
        
        if self.help_text:
            readonly_attrs.append(f'aria-describedby="{self.id}_help"')
        
        html_field += f'<input {" ".join(readonly_attrs)} />'
        
        if self.icon:
            html_field += f'<span class="input-group-text"><i class="mdi {self.icon}" aria-hidden="true"></i></span>'
            html_field += '</div>'
        
        html_field += '</div>'
        
        return html_field


class Select2Field(FormField):
    """Campo Select2 padronizado"""
    
    def __init__(
        self,
        name: str,
        label: str,
        options: List[Dict[str, Any]] = None,
        value: Any = None,
        required: bool = False,
        help_text: Optional[str] = None,
        placeholder: str = 'Selecione...',
        load_url: Optional[str] = None,
        load_on: Optional[str] = None,
        **kwargs
    ):
        super().__init__(name, label, value, required, help_text, **kwargs)
        self.options = options or []
        self.placeholder = placeholder
        self.load_url = load_url
        self.load_on = load_on  # Campo que dispara o carregamento
        self.css_class = 'select2 form-select'
    
    def render(self) -> str:
        """Renderiza campo Select2"""
        col_class = self.attrs.get('col_class', 'col-12 col-md-6')
        
        html_field = f'<div class="{col_class} mb-3">'
        html_field += self._render_label()
        
        attrs = {
            'style': 'width:100%',
            'data-placeholder': self.placeholder
        }
        
        # Desabilita validação HTML5 padrão para usar apenas validação customizada
        if self.required:
            attrs['oninvalid'] = "this.setCustomValidity('')"
            attrs['oninput'] = "this.setCustomValidity('')"
        
        if self.load_url:
            attrs['data-load-url'] = self.load_url
        
        if self.load_on:
            attrs['data-load-on'] = self.load_on
        
        html_field += f'<select {self._get_attrs_string(attrs)}>'
        # Adiciona opção vazia "Selecione" no início
        html_field += '<option value="">Selecione</option>'
        
        for option in self.options:
            # Só marca como selected se value não for None, vazio ou False
            option_value = option.get('value', '')
            is_selected = False
            if self.value is not None and self.value != '' and str(option_value) == str(self.value):
                is_selected = True
            selected = 'selected' if is_selected else ''
            html_field += f'<option value="{html.escape(str(option_value))}" {selected}>'
            html_field += html.escape(str(option.get('label', '')))
            html_field += '</option>'
        
        html_field += '</select>'
        html_field += '</div>'
        
        return html_field


class DateField(FormField):
    """Campo de data com Bootstrap Datepicker"""
    
    def __init__(
        self,
        name: str,
        label: str,
        value: Any = None,
        required: bool = False,
        help_text: Optional[str] = None,
        placeholder: str = 'dd/mm/aaaa',
        min_date: Optional[str] = None,
        readonly: bool = False,
        **kwargs
    ):
        super().__init__(name, label, value, required, help_text, **kwargs)
        self.placeholder = placeholder
        self.min_date = min_date or 'today'
        self.readonly = readonly
        self.css_class = 'form-control datepicker'
    
    def render(self) -> str:
        """Renderiza campo de data"""
        col_class = self.attrs.get('col_class', 'col-12 col-md-6')
        
        html_field = f'<div class="{col_class} mb-3">'
        html_field += self._render_label()
        
        html_field += '<div class="input-group">'
        
        attrs = {
            'type': 'text',
            'placeholder': self.placeholder,
            'autocomplete': 'off',
            'value': self.value or ''
        }
        
        if self.readonly:
            attrs['readonly'] = True
            attrs['aria-readonly'] = 'true'
            attrs['tabindex'] = '-1'
        
        html_field += f'<input {self._get_attrs_string(attrs)} />'
        html_field += '<span class="input-group-text"><i class="mdi mdi-calendar" aria-hidden="true"></i></span>'
        html_field += '</div>'
        html_field += '</div>'
        
        return html_field


class RadioGroupField(FormField):
    """Grupo de radio buttons"""
    
    def __init__(
        self,
        name: str,
        label: str,
        options: List[Tuple[str, str, bool]],  # [(value, label, checked), ...]
        required: bool = False,
        help_text: Optional[str] = None,
        inline: bool = True,
        **kwargs
    ):
        super().__init__(name, label, None, required, help_text, **kwargs)
        self.options = options
        self.inline = inline
        self.css_class = ''  # Não aplica form-control
    
    def render(self) -> str:
        """Renderiza grupo de radio buttons"""
        col_class = self.attrs.get('col_class', 'col-12 col-md-6')
        
        # Reduz margem inferior para layout mais compacto quando em linha
        mb_class = 'mb-2' if self.inline and 'col-md' in col_class else 'mb-3'
        
        html_field = f'<div class="{col_class} {mb_class}">'
        # ⚠️ Diferente de inputs simples, um grupo de radios não tem um único elemento com id=self.id.
        # Os radios gerados usam ids como `field_<name>_<value>`, então um <label for="self.id"> fica inválido.
        # Renderizamos um label "de grupo" sem atributo `for`.
        required_mark = ''
        required_aria = ''
        if self.required:
            required_mark = ' <span class="text-danger" aria-label="obrigatório">*</span>'
            required_aria = ' <span class="visually-hidden">(obrigatório)</span>'
        html_field += f'<label class="form-label">{html.escape(self.label)}{required_mark}{required_aria}</label>'
        if self.help_text:
            html_field += f'<small class="form-text text-muted d-block" id="{self.id}_help">{self._escape(self.help_text)}</small>'
        
        # Container para as opções - sempre em uma linha separada do label
        # Quando inline=True, as opções ficam na mesma linha entre si
        # Quando inline=False, cada opção fica em uma linha separada
        html_field += '<div class="mt-2">'
        
        inline_class = 'form-check-inline' if self.inline else ''
        
        for value, label, checked in self.options:
            radio_id = f'{self.id}_{value}'
            # Adiciona margem inferior quando não está inline para separar os radios
            mb_radio = '' if self.inline else ' mb-2'
            html_field += f'<div class="form-check {inline_class}{mb_radio}">'
            html_field += f'<input class="form-check-input" type="radio" name="{self.name}" id="{radio_id}" value="{html.escape(str(value))}"'
            
            if checked:
                html_field += ' checked'
            
            if self.required:
                html_field += ' aria-required="true"'
            
            html_field += ' />'
            html_field += f'<label class="form-check-label" for="{radio_id}">{html.escape(str(label))}</label>'
            html_field += '</div>'
        
        html_field += '</div>'  # Fecha container das opções
        html_field += '</div>'  # Fecha col
        
        return html_field


class FileField(FormField):
    """Campo de arquivo"""
    
    def __init__(
        self,
        name: str,
        label: str,
        accept: str = 'application/pdf',
        required: bool = False,
        help_text: Optional[str] = None,
        disabled: bool = False,
        max_size_mb: int = 10,
        **kwargs
    ):
        super().__init__(name, label, None, required, help_text, **kwargs)
        self.accept = accept
        self.disabled = disabled
        self.max_size_mb = max_size_mb
        self.css_class = 'form-control'
    
    def render(self) -> str:
        """Renderiza campo de arquivo"""
        col_class = self.attrs.get('col_class', 'col-12')
        
        # Reduz margem inferior para layout mais compacto
        mb_class = 'mb-2' if 'col-md' in col_class else 'mb-3'
        
        html_field = f'<div class="{col_class} {mb_class}">'
        html_field += self._render_label()
        
        attrs = {
            'type': 'file',
            'accept': self.accept,
            'data-max-size-mb': str(self.max_size_mb)
        }
        
        if self.disabled:
            attrs['disabled'] = True
        
        html_field += f'<input {self._get_attrs_string(attrs)} />'
        
        # help_text já é renderizado no _render_label(), não precisa renderizar novamente aqui
        
        html_field += '</div>'
        
        return html_field


class TextareaField(FormField):
    """Campo textarea com TinyMCE"""
    
    def __init__(
        self,
        name: str,
        label: str,
        value: Any = None,
        required: bool = False,
        help_text: Optional[str] = None,
        rows: int = 6,
        tinymce: bool = True,
        **kwargs
    ):
        super().__init__(name, label, value, required, help_text, **kwargs)
        self.rows = rows
        self.tinymce = tinymce
        self.css_class = 'form-control'
        if tinymce:
            self.css_class += ' tinymce-editor'
    
    def render(self) -> str:
        """Renderiza textarea"""
        col_class = self.attrs.get('col_class', 'col-12')
        
        html_field = f'<div class="{col_class} mb-3">'
        html_field += self._render_label()
        
        attrs = {
            'rows': str(self.rows)
        }
        
        if self.tinymce:
            attrs['data-tinymce'] = 'true'
        
        html_field += f'<textarea {self._get_attrs_string(attrs)}>{self._escape(self.value or "")}</textarea>'
        html_field += '</div>'
        
        return html_field


class HiddenField(FormField):
    """Campo hidden"""
    
    def __init__(self, name: str, value: Any = None, **kwargs):
        super().__init__(name, '', value, False, None, **kwargs)
    
    def render(self) -> str:
        """Renderiza campo hidden"""
        return f'<input type="hidden" name="{self.name}" id="{self.id}" value="{self._escape(self.value)}" />'
