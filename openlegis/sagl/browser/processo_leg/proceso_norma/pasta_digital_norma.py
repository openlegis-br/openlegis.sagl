# -*- coding: utf-8 -*-
"""
View para fornecer dados JSON para a interface de pasta digital de normas jurídicas.
Adaptado de pasta_digital.py para trabalhar com normas ao invés de matérias.
"""
import json
import logging
import os
import hashlib
import time
from datetime import date, datetime
from five import grok
from zope.interface import Interface
from Products.CMFCore.utils import getToolByName
from openlegis.sagl.browser.processo_norma.processo_norma_utils import (
    get_processo_norma_dir,
    get_cache_norma_file_path,
    TEMP_DIR_PREFIX_NORMA
)
from openlegis.sagl.browser.processo_leg.processo_leg_utils import (
    safe_check_file,
    get_file_size
)
from z3c.saconfig import named_scoped_session
from sqlalchemy import and_, or_
from openlegis.sagl.models.models import (
    NormaJuridica, TipoNormaJuridica, VinculoNormaJuridica,
    MateriaLegislativa, TipoMateriaLegislativa
)

Session = named_scoped_session('minha_sessao')
logger = logging.getLogger(__name__)

class DateTimeJSONEncoder(json.JSONEncoder):
    """Encoder JSON customizado para converter objetos date/datetime para string"""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            if isinstance(obj, datetime):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            else:
                return obj.strftime('%Y-%m-%d')
        return super().default(obj)


class PastaDigitalNormaMixin:
    """Mixin com métodos compartilhados para views de pasta digital de normas"""
    
    def _get_session(self):
        """Retorna sessão SQLAlchemy thread-safe"""
        return Session()
    
    def _get_norma_data(self, cod_norma):
        """Obtém dados básicos da norma"""
        try:
            session = self._get_session()
            try:
                result = session.query(NormaJuridica, TipoNormaJuridica)\
                    .join(TipoNormaJuridica, 
                          NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(NormaJuridica.cod_norma == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .first()
                
                if not result:
                    return None
                
                norma_obj, tipo_obj = result
                
                return {
                    'cod_norma': norma_obj.cod_norma,
                    'tipo': tipo_obj.sgl_tipo_norma,
                    'numero': norma_obj.num_norma,
                    'ano': norma_obj.ano_norma,
                    'data_norma': norma_obj.dat_norma,
                    'descricao': tipo_obj.des_tipo_norma,
                    'id_exibicao': f"{tipo_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma}"
                }
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Erro ao obter dados da norma: {e}", exc_info=True)
            return None
    
    def _get_pasta_data(self, cod_norma, action, tool, portal):
        """Obtém dados da pasta digital da norma"""
        try:
            # Verifica se há cache
            cache_file = get_cache_norma_file_path(cod_norma)
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        if cache_data.get('documentos'):
                            return {
                                'documentos': cache_data['documentos'],
                                'async': False,
                                'cached': True
                            }
                except Exception as e:
                    logger.debug(f"Erro ao ler cache: {e}")
            
            # Se não há cache, retorna estrutura vazia
            return {
                'documentos': [],
                'async': False,
                'cached': False
            }
        except Exception as e:
            logger.error(f"Erro ao obter dados da pasta: {e}", exc_info=True)
            return {
                'documentos': [],
                'async': False,
                'error': str(e)
            }
    
    def _get_portal_config(self, portal):
        """Obtém configurações do portal"""
        try:
            if hasattr(portal, 'sapl_documentos'):
                props = portal.sapl_documentos.props_sagl
                return {
                    'nom_casa': props.getProperty('nom_casa', ''),
                    'reuniao_sessao': props.getProperty('reuniao_sessao', '')
                }
            return {}
        except Exception as e:
            logger.error(f"Erro ao obter configurações do portal: {e}", exc_info=True)
            return {}
    
    def _get_materias_relacionadas(self, cod_norma, portal):
        """Obtém matérias relacionadas à norma"""
        try:
            session = self._get_session()
            try:
                materias = session.query(MateriaLegislativa, TipoMateriaLegislativa)\
                    .join(TipoMateriaLegislativa, 
                          MateriaLegislativa.tip_id_basica == TipoMateriaLegislativa.tip_materia)\
                    .filter(MateriaLegislativa.cod_norma == cod_norma)\
                    .filter(MateriaLegislativa.ind_excluido == 0)\
                    .all()
                
                materias_list = []
                for materia_obj, tipo_obj in materias:
                    materias_list.append({
                        'cod_materia': materia_obj.cod_materia,
                        'tipo': tipo_obj.sgl_tipo_materia,
                        'numero': materia_obj.num_ident_basica,
                        'ano': materia_obj.ano_ident_basica,
                        'id_exibicao': f"{tipo_obj.sgl_tipo_materia} {materia_obj.num_ident_basica}/{materia_obj.ano_ident_basica}"
                    })
                
                return materias_list
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Erro ao obter matérias relacionadas: {e}", exc_info=True)
            return []
    
    def _get_normas_relacionadas(self, cod_norma, portal):
        """Obtém normas relacionadas (vinculadas)"""
        try:
            session = self._get_session()
            try:
                vinculos = session.query(VinculoNormaJuridica, NormaJuridica, TipoNormaJuridica)\
                    .join(NormaJuridica, VinculoNormaJuridica.cod_norma_relacionada == NormaJuridica.cod_norma)\
                    .join(TipoNormaJuridica, NormaJuridica.tip_norma == TipoNormaJuridica.tip_norma)\
                    .filter(VinculoNormaJuridica.cod_norma == cod_norma)\
                    .filter(NormaJuridica.ind_excluido == 0)\
                    .all()
                
                normas_list = []
                for vinculo_obj, norma_obj, tipo_obj in vinculos:
                    normas_list.append({
                        'cod_norma': norma_obj.cod_norma,
                        'tipo': tipo_obj.sgl_tipo_norma,
                        'numero': norma_obj.num_norma,
                        'ano': norma_obj.ano_norma,
                        'id_exibicao': f"{tipo_obj.sgl_tipo_norma} {norma_obj.num_norma}/{norma_obj.ano_norma}"
                    })
                
                return normas_list
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Erro ao obter normas relacionadas: {e}", exc_info=True)
            return []


class PastaDigitalNormaView(PastaDigitalNormaMixin, grok.View):
    """View que renderiza o HTML da pasta digital de normas diretamente"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pasta_digital_norma')

    def update(self):
        """Método update do Grok - garante que headers sejam definidos"""
        self.request.RESPONSE.setHeader('Content-Type', 'text/html; charset=utf-8')
        self.request.RESPONSE.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.request.RESPONSE.setHeader('Pragma', 'no-cache')
        self.request.RESPONSE.setHeader('Expires', '0')

    def __call__(self):
        """Intercepta a chamada para escrever HTML diretamente na resposta"""
        self.update()
        html = self.render()
        
        if not isinstance(html, str):
            html = str(html)
        
        self.request.RESPONSE.setHeader('Content-Type', 'text/html; charset=utf-8')
        
        if isinstance(html, str):
            html_bytes = html.encode('utf-8')
        else:
            html_bytes = html
        
        self.request.RESPONSE.setBody(html_bytes)
        return ''

    def render(self):
        """Renderiza HTML da pasta digital com dados já incluídos"""
        try:
            cod_norma = self.request.form.get('cod_norma') or self.request.get('cod_norma')
            action = self.request.form.get('action', 'pasta')
            
            if not cod_norma:
                return '<html><body><h1>Erro</h1><p>Parâmetro cod_norma é obrigatório</p></body></html>'
            
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            tool = getToolByName(self.context, 'portal_sagl')
            
            norma_data = self._get_norma_data(cod_norma)
            pasta_data = self._get_pasta_data(cod_norma, action, tool, portal)
            portal_config = self._get_portal_config(portal)
            materias_relacionadas = self._get_materias_relacionadas(cod_norma, portal)
            normas_relacionadas = self._get_normas_relacionadas(cod_norma, portal)
            
            # Renderiza HTML básico (pode ser expandido posteriormente)
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Pasta Digital - {norma_data.get('id_exibicao', 'Norma') if norma_data else 'Norma'}</title>
            </head>
            <body>
                <h1>Pasta Digital - {norma_data.get('id_exibicao', 'Norma') if norma_data else 'Norma'}</h1>
                <div id="pasta-digital-norma" data-cod-norma="{cod_norma}"></div>
                <script>
                    // Dados para JavaScript
                    window.pastaDigitalNormaData = {{
                        cod_norma: {json.dumps(cod_norma)},
                        norma: {json.dumps(norma_data, cls=DateTimeJSONEncoder)},
                        pasta: {json.dumps(pasta_data, cls=DateTimeJSONEncoder)},
                        portal_config: {json.dumps(portal_config, cls=DateTimeJSONEncoder)},
                        materias_relacionadas: {json.dumps(materias_relacionadas, cls=DateTimeJSONEncoder)},
                        normas_relacionadas: {json.dumps(normas_relacionadas, cls=DateTimeJSONEncoder)}
                    }};
                </script>
            </body>
            </html>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"Erro ao renderizar pasta digital: {e}", exc_info=True)
            return f'<html><body><h1>Erro</h1><p>{str(e)}</p></body></html>'


class PastaDigitalNormaDataView(PastaDigitalNormaMixin, grok.View):
    """View que retorna JSON com todos os dados necessários para a página de pasta digital de normas"""
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('pasta_digital_norma_data')

    def render(self):
        """Retorna JSON com dados da pasta digital de normas"""
        self.request.RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
        
        try:
            cod_norma = self.request.form.get('cod_norma') or self.request.get('cod_norma')
            action = self.request.form.get('action', 'pasta')
            
            if not cod_norma:
                return json.dumps({
                    'error': 'Parâmetro cod_norma é obrigatório',
                    'success': False
                }, cls=DateTimeJSONEncoder)
            
            portal = getToolByName(self.context, 'portal_url').getPortalObject()
            tool = getToolByName(self.context, 'portal_sagl')
            
            norma_data = self._get_norma_data(cod_norma)
            pasta_data = self._get_pasta_data(cod_norma, action, tool, portal)
            portal_config = self._get_portal_config(portal)
            materias_relacionadas = self._get_materias_relacionadas(cod_norma, portal)
            normas_relacionadas = self._get_normas_relacionadas(cod_norma, portal)
            
            response = {
                'success': True,
                'cod_norma': cod_norma,
                'action': action,
                'norma': norma_data,
                'pasta': pasta_data,
                'portal_config': portal_config,
                'materias_relacionadas': materias_relacionadas,
                'normas_relacionadas': normas_relacionadas,
                'portal_url': str(portal.absolute_url())
            }
            
            return json.dumps(response, ensure_ascii=False, cls=DateTimeJSONEncoder)
            
        except Exception as e:
            logger.error(f"Erro ao obter dados da pasta digital de normas: {e}", exc_info=True)
            self.request.RESPONSE.setStatus(500)
            return json.dumps({
                'error': str(e),
                'success': False
            }, ensure_ascii=False, cls=DateTimeJSONEncoder)
