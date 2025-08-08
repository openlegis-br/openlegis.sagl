# -*- coding: utf-8 -*-
from five import grok
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer
from zope.interface import Interface
from DateTime import DateTime
from io import BytesIO
import requests
from PIL import Image, UnidentifiedImageError
import json
from functools import lru_cache

# Constants for member roles and status
ROLE_ORDER = {
    'Presidente': 1,
    'Vice-Presidente': 2,
    'Relator': 3,
    'Relator Geral': 3,
    'Membro': 4,
    'Membro Efetivo': 4,
    'Suplente': 5,
}

MEMBER_STATUS = {1: "Titular"}

DEFAULT_AVATAR = '/imagens/avatar.png'
PDF_TYPES = {
    'pauta': '_pauta.pdf',
    'ata': '_ata.pdf',
    'parecer': '_parecer.pdf'
}

@implementer(IPublishTraverse)
class ComissoesAPI(grok.View):
    """API endpoint for committees, meetings, and related data"""
    
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('comissoes')

    def __init__(self, context, request):
        super().__init__(context, request)
        self.subpath = []
        self.item_id = None
        self.reunioes = False
        self.reuniao_id = None
        self.portal_url = context.portal_url()
        self.service_url = f"{self.portal_url}/@@comissoes"

    def publishTraverse(self, request, name):
        """Handle URL traversal for different endpoints"""
        self.subpath.append(name)
        path_len = len(self.subpath)
        
        if path_len >= 1:
            self.item_id = self.subpath[0]
        if path_len >= 2 and self.subpath[1] == 'reunioes':
            self.reunioes = True
        if path_len == 3:
            self.reuniao_id = self.subpath[2]
            
        return self

    def render(self):
        """Main endpoint handler that routes requests"""
        response_data = {
            '@id': self.service_url,
            '@type': 'Comissoes',
            'description': 'Lista de comissões'
        }

        if self.reuniao_id:
            response_data.update(self.get_meeting_details(self.reuniao_id))
        elif self.reunioes:
            response_data.update(self.list_committee_meetings(self.item_id))
        elif self.item_id:
            response_data.update(self.get_committee_details(self.item_id))
        else:
            response_data.update(self.list_all_committees())

        return self._json_response(response_data)

    def _json_response(self, data):
        """Helper method to return properly formatted JSON"""
        return json.dumps(
            data, 
            sort_keys=True, 
            indent=3, 
            ensure_ascii=False
        ).encode('utf8').decode()

    @lru_cache(maxsize=32)
    def list_all_committees(self):
        """List all active committees"""
        committees = []
        for committee in self.context.zsql.comissao_obter_zsql(ind_extintas=0, ind_excluido=0):
            committees.append({
                "@id": f"{self.service_url}/{committee.cod_comissao}",
                "@type": "Comissao",
                "id": str(committee.cod_comissao),
                "title": committee.nom_comissao,
                "description": committee.sgl_comissao,
                "tipo": committee.nom_tipo_comissao,
            })
        
        committees.sort(key=lambda c: c['title'])
        return {
            "description": "Lista de comissões", 
            "items": committees
        }

    def get_committee_details(self, committee_id):
        """Get detailed information about a specific committee"""
        committee = self._get_committee_by_id(committee_id)
        if not committee:
            return {}
        
        today = DateTime()
        return {
            "@id": f"{self.service_url}/{committee_id}",
            "@type": "Comissao",
            "id": committee_id,
            "description": committee.sgl_comissao,
            "title": committee.nom_comissao,
            "tipo": committee.nom_tipo_comissao,
            "items": self._get_current_members(committee_id, today),
            "reunioes": self.list_committee_meetings(committee_id),
            "periodos": self._get_historical_periods(committee_id, today)
        }

    def _get_committee_by_id(self, committee_id):
        """Helper to fetch a single committee by ID"""
        results = list(self.context.zsql.comissao_obter_zsql(
            cod_comissao=int(committee_id), 
            ind_extintas=0, 
            ind_excluido=0
        ))
        return results[0] if results else None

    def _get_current_members(self, committee_id, current_date):
        """Get current members of a committee"""
        members = []
    
        # Get all periods and filter in Python
        all_periods = self.context.zsql.periodo_comp_comissao_obter_zsql(ind_excluido=0)
    
        for p in all_periods:
            # Convert string dates to DateTime objects for comparison
            try:
                start_date = DateTime(p.dat_inicio_periodo)
                end_date = DateTime(p.dat_fim_periodo)
            except (TypeError, ValueError):
                continue  # Skip invalid dates
            
            if start_date <= current_date <= end_date:
                for member in self.context.zsql.composicao_comissao_obter_zsql(
                    cod_comissao=committee_id,
                    cod_periodo_comp=p.cod_periodo_comp
                ):
                    member_data = self._build_member_data(member)
                    members.append(member_data)

        # Sort by role importance then by name
        members.sort(key=lambda m: (m['ordem'], m['title']))
        return members

    def _build_member_data(self, member):
        """Construct the member data structure"""
        member_id = str(member.cod_parlamentar)
        member_data = {
            "@id": f"{self.portal_url}/@@vereadores/{member_id}",
            "@type": "ParticipanteComissao",
            "id": member_id,
            "title": member.nom_parlamentar,
            "description": member.nom_completo,
            "cargo": member.des_cargo,
            "ordem": ROLE_ORDER.get(member.des_cargo, 6),
            "mandato": MEMBER_STATUS.get(member.ind_titular, "Suplente"),
        }

        # Add photo information
        self._add_member_photo(member_data, member_id)
        
        # Add party affiliation
        member_data["partido"] = self._get_member_parties(member.cod_parlamentar)
        
        return member_data

    def _add_member_photo(self, member_data, member_id):
        """Add photo information to member data"""
        photo_name = f"{member_id}_foto_parlamentar"
        photo_path = f"sapl_documentos/parlamentar/fotos/{photo_name}"
        
        if hasattr(self.context.sapl_documentos.parlamentar.fotos, photo_name):
            photo_url = f"{self.portal_url}/{photo_path}"
            try:
                response = requests.get(photo_url, timeout=2)
                img = Image.open(BytesIO(response.content))
                member_data.update({
                    "url_foto": photo_url,
                    "image": [{
                        "content-type": f"image/{img.format.lower()}",
                        "download": photo_url,
                        "filename": photo_name,
                        "width": img.width,
                        "height": img.height,
                        "size": len(response.content),
                    }]
                })
                return
            except (UnidentifiedImageError, requests.RequestException):
                pass

        member_data.update({
            "url_foto": f"{self.portal_url}{DEFAULT_AVATAR}",
            "image": []
        })

    def _get_member_parties(self, member_id):
        """Get active party affiliations for a member"""
        parties = []
        for affiliation in self.context.zsql.filiacao_obter_zsql(
            ind_excluido=0,
            cod_parlamentar=member_id
        ):
            if not affiliation.dat_desfiliacao:
                party = list(self.context.zsql.partido_obter_zsql(
                    ind_excluido=0,
                    cod_partido=affiliation.cod_partido
                ))[0]
                parties.append({
                    "token": party.sgl_partido,
                    "title": party.nom_partido
                })
        return parties

    def _get_historical_periods(self, committee_id, current_date):
        """Get historical composition periods for a committee"""
        periods = []

        for period in self.context.zsql.periodo_comp_comissao_obter_zsql(ind_excluido=0):
            # Converte as datas de início e fim para objetos DateTime
            dt_start = DateTime(period.dat_inicio_periodo, datefmt='international')
            dt_end   = DateTime(period.dat_fim_periodo,    datefmt='international')

            is_current = (dt_start <= current_date <= dt_end)

            period_data = {
                "title": "Composição da Comissão",
                "description": (
                    f"{dt_start.strftime('%d/%m/%Y')} "
                    f"a {dt_end.strftime('%d/%m/%Y')}"
                ),
                "start": dt_start.strftime("%Y-%m-%d"),
                "end":   dt_end.strftime("%Y-%m-%d"),
                "id":    period.cod_periodo_comp,
                "atual": is_current,
                "items": []
            }

            for member in self.context.zsql.composicao_comissao_obter_zsql(
                cod_comissao=committee_id,
                cod_periodo_comp=period.cod_periodo_comp
            ):
                if not member.dat_desligamento:
                    period_data["items"].append({
                        "@id": f"{self.portal_url}/@@vereadores/{member.cod_parlamentar}",
                        "@type": "ParticipanteComissao",
                        "id": str(member.cod_parlamentar),
                        "title": member.nom_parlamentar,
                        "description": member.nom_completo,
                        "cargo": member.des_cargo,
                        "mandato": "Titular" if member.ind_titular == 1 else "Suplente",
                        "partido": self._get_member_parties(member.cod_parlamentar)
                    })

            # só adiciona os períodos que já terminaram
            if not is_current:
                periods.append(period_data)

        return periods

    def list_committee_meetings(self, committee_id):
        """List all meetings for a committee"""
        meetings = []
        
        for meeting in self.context.zsql.reuniao_comissao_obter_zsql(
            cod_comissao=int(committee_id), 
            ind_excluido=0
        ):
            # converte string para DateTime
            dt = DateTime(meeting.dat_inicio_reuniao, datefmt='international')
            meeting_date = dt.strftime("%Y-%m-%d")
            
            meetings.append({
                "@id": f"{self.service_url}/{committee_id}/reunioes/{meeting.cod_reuniao}",
                "@type": "ReuniaoComissao",
                "id": str(meeting.cod_reuniao),
                "title": f"{meeting.num_reuniao}ª Reunião {meeting.des_tipo_reuniao}",
                "description": f"{dt.strftime('%d/%m/%Y')} - {meeting.hr_inicio_reuniao}",
                "data": meeting_date,
                "ano": dt.strftime("%Y"),
                "hora_abertura": meeting.hr_inicio_reuniao,
                "hora_encerramento": meeting.hr_fim_reuniao,
                "arquivo_pauta": self._get_pdf_attachment(meeting.cod_reuniao, 'pauta'),
                "arquivo_ata": self._get_pdf_attachment(meeting.cod_reuniao, 'ata'),
            })

        meetings.sort(key=lambda x: x["data"], reverse=True)
        return {
            "@type": "ReunioesComissao",
            "description": f"Lista de reuniões da comissão {committee_id}",
            "items": meetings
        }

    def get_meeting_details(self, meeting_id):
        """Get detailed information about a specific meeting"""
        meeting = self._get_meeting_by_id(meeting_id)
        if not meeting:
            return {}

        # converte string para DateTime
        dt = DateTime(meeting.dat_inicio_reuniao, datefmt='international')
        committee = self._get_committee_by_id(meeting.cod_comissao)

        return {
            "@id": f"{self.service_url}/{meeting.cod_comissao}/reunioes/{meeting.cod_reuniao}",
            "@type": "ReuniaoComissao",
            "id": str(meeting.cod_reuniao),
            "start": dt.strftime("%Y-%m-%d"),
            "ano": dt.strftime("%Y"),
            "title": f"{meeting.num_reuniao}ª Reunião {meeting.des_tipo_reuniao}",
            "description": f"{dt.strftime('%d/%m/%Y')} - {meeting.hr_inicio_reuniao}",
            "hora_abertura": meeting.hr_inicio_reuniao,
            "hora_encerramento": meeting.hr_fim_reuniao,
            "tipo": meeting.des_tipo_reuniao,
            "tema": meeting.txt_tema,
            "comissao": committee.nom_comissao if committee else "",
            "comissao_id": str(meeting.cod_comissao),
            "arquivo_pauta": self._get_pdf_attachment(meeting.cod_reuniao, 'pauta'),
            "arquivo_ata": self._get_pdf_attachment(meeting.cod_reuniao, 'ata'),
            # outros campos…
        }

    def _get_meeting_by_id(self, meeting_id):
        """Helper to fetch a single meeting by ID"""
        results = list(self.context.zsql.reuniao_comissao_obter_zsql(
            cod_reuniao=int(meeting_id), 
            ind_excluido=0
        ))
        return results[0] if results else None

    def _get_pdf_attachment(self, meeting_id, attachment_type):
        """Get PDF attachment information for a meeting"""
        filename = f"{meeting_id}{PDF_TYPES.get(attachment_type, '')}"
        if hasattr(self.context.sapl_documentos.reuniao_comissao, filename):
            return [{
                "content-type": "application/pdf",
                "download": (
                    f"{self.portal_url}/sapl_documentos/reuniao_comissao/{filename}"
                ),
                "filename": filename,
                "size": ""
            }]
        return []
