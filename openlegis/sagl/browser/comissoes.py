# -*- coding: utf-8 -*-
from grokcore.component import context
from grokcore.view import name
from grokcore.security import require
from grokcore.view import View as GrokView
from zope.publisher.interfaces import IPublishTraverse
from zope.interface import implementer, Interface
from DateTime import DateTime
from io import BytesIO
import requests
from PIL import Image, UnidentifiedImageError
import json
from functools import lru_cache

# =============================
# Constantes e configurações
# =============================

ROLE_ORDER = {
    'Presidente': 1,
    'Vice-Presidente': 2,
    'Relator': 3,
    'Relator Geral': 3,
    'Membro': 4,
    'Membro Efetivo': 4,
    'Suplente': 5,
}
MEMBER_STATUS = {1: "Titular"}  # default para demais será "Suplente"

DEFAULT_AVATAR = '/imagens/avatar.png'

PDF_TYPES = {
    'pauta': '_pauta.pdf',
    'ata': '_ata.pdf',
    'parecer': '_parecer.pdf'
}

HTTP_TIMEOUT = 3            # segundos (pedidos gerais)
IMAGE_TIMEOUT = 3           # segundos (download de foto)


@implementer(IPublishTraverse)
class ComissoesAPI(GrokView):
    """API para comissões, reuniões e composições (registro automático via grokcore)."""

    # Diretivas Grok no nível da classe
    context(Interface)
    name('comissoes')            # URL: @@comissoes
    require('zope2.View')        # Permissão de leitura

    # --------------------------
    # Ciclo de vida / utilidades
    # --------------------------

    def __init__(self, context, request):
        super().__init__(context, request)
        self.subpath = []
        self.item_id = None              # cod_comissao
        self.reunioes = False
        self.reuniao_id = None           # cod_reuniao
        self.portal_url = self._get_portal_url()
        self.service_url = f"{self.portal_url}/@@comissoes"

    def _get_portal_url(self):
        """Obtém a URL do portal de forma resiliente, compatível com diferentes instalações."""
        try:
            url = self.context.portal_url()
            if isinstance(url, str) and url:
                return url.rstrip('/')
        except Exception:
            pass
        try:
            portal = self.context.portal_url.getPortalObject()
            return portal.portal_url().rstrip('/')
        except Exception:
            pass
        base = self.request.getURL()
        return base.split('/@@', 1)[0].rstrip('/')

    # --------------------------
    # Roteamento por traversal
    # --------------------------

    def publishTraverse(self, request, name):
        """Suporta:
           /@@comissoes
           /@@comissoes/<cod_comissao>
           /@@comissoes/<cod_comissao>/reunioes
           /@@comissoes/<cod_comissao>/reunioes/<cod_reuniao>
        """
        # impede traversals adicionais
        request["TraversalRequestNameStack"] = []

        self.subpath.append(name)
        path_len = len(self.subpath)

        if path_len >= 1:
            self.item_id = self.subpath[0]
        if path_len >= 2 and self.subpath[1] == 'reunioes':
            self.reunioes = True
        if path_len == 3:
            self.reuniao_id = self.subpath[2]

        return self

    # --------------------------
    # Render (dispatcher)
    # --------------------------

    def render(self):
        """Dispatcher principal do endpoint."""
        data = {
            '@id': self.service_url,
            '@type': 'Comissoes',
            'description': 'Lista de comissões'
        }

        if self.reuniao_id:
            data.update(self.get_meeting_details(self.reuniao_id))
        elif self.reunioes:
            data.update(self.list_committee_meetings(self.item_id))
        elif self.item_id:
            data.update(self.get_committee_details(self.item_id))
        else:
            data.update(self.list_all_committees())

        return self._json_response(data)

    def _json_response(self, data):
        """Retorna JSON com cabeçalhos adequados."""
        resp = self.request.response
        resp.setHeader('Content-Type', 'application/json; charset=utf-8')
        # opcional: evitar cache agressivo de proxies
        resp.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
        return json.dumps(data, sort_keys=True, indent=3, ensure_ascii=False)

    # --------------------------
    # Comissões
    # --------------------------

    @lru_cache(maxsize=32)
    def list_all_committees(self):
        """Lista todas as comissões ativas."""
        items = []
        for c in self.context.zsql.comissao_obter_zsql(ind_extintas=0, ind_excluido=0):
            items.append({
                "@id": f"{self.service_url}/{c.cod_comissao}",
                "@type": "Comissao",
                "id": str(c.cod_comissao),
                "title": c.nom_comissao,
                "description": c.sgl_comissao,
                "tipo": c.nom_tipo_comissao,
            })
        items.sort(key=lambda v: v['title'])
        return {"description": "Lista de comissões", "items": items}

    def get_committee_details(self, committee_id):
        """Detalhes de uma comissão específica."""
        committee = self._get_committee_by_id(committee_id)
        if not committee:
            return {}

        today = DateTime()
        return {
            "@id": f"{self.service_url}/{committee_id}",
            "@type": "Comissao",
            "id": str(committee_id),
            "description": committee.sgl_comissao,
            "title": committee.nom_comissao,
            "tipo": committee.nom_tipo_comissao,
            "items": self._get_current_members(committee_id, today),
            "reunioes": self.list_committee_meetings(committee_id),
            "periodos": self._get_historical_periods(committee_id, today),
        }

    def _get_committee_by_id(self, committee_id):
        """Obtém uma comissão pelo ID."""
        try:
            cod = int(committee_id)
        except (TypeError, ValueError):
            return None
        res = list(self.context.zsql.comissao_obter_zsql(
            cod_comissao=cod, ind_extintas=0, ind_excluido=0
        ))
        return res[0] if res else None

    # --------------------------
    # Membros / composição
    # --------------------------

    def _get_current_members(self, committee_id, current_date):
        """Retorna a composição vigente da comissão."""
        members = []
        all_periods = self.context.zsql.periodo_comp_comissao_obter_zsql(ind_excluido=0)

        for p in all_periods:
            try:
                start_date = DateTime(p.dat_inicio_periodo, datefmt='international')
                end_date = DateTime(p.dat_fim_periodo, datefmt='international')
            except Exception:
                continue

            if start_date <= current_date <= end_date:
                for m in self.context.zsql.composicao_comissao_obter_zsql(
                    cod_comissao=committee_id,
                    cod_periodo_comp=p.cod_periodo_comp
                ):
                    members.append(self._build_member_data(m))

        members.sort(key=lambda m: (m['ordem'], m['title']))
        return members

    def _build_member_data(self, member):
        """Monta o dicionário de um membro da comissão."""
        member_id = str(member.cod_parlamentar)
        data = {
            "@id": f"{self.portal_url}/@@vereadores/{member_id}",
            "@type": "ParticipanteComissao",
            "id": member_id,
            "title": member.nom_parlamentar,
            "description": getattr(member, 'nom_completo', '') or member.nom_parlamentar,
            "cargo": member.des_cargo,
            "ordem": ROLE_ORDER.get(member.des_cargo, 6),
            "mandato": MEMBER_STATUS.get(getattr(member, 'ind_titular', 0), "Suplente"),
        }

        # Foto e partido(s)
        self._add_member_photo(data, member_id)
        data["partido"] = self._get_member_parties(member.cod_parlamentar)
        return data

    def _url_exists(self, url):
        """Faz HEAD para evitar baixar conteúdo inexistente."""
        try:
            r = requests.head(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def _add_member_photo(self, member_data, member_id):
        """Acrescenta informações de foto ao membro (se existir e for imagem válida)."""
        photo_name = f"{member_id}_foto_parlamentar"
        try:
            fotos = self.context.sapl_documentos.parlamentar.fotos
        except Exception:
            fotos = None

        photo_url = None
        if fotos and hasattr(fotos, photo_name):
            # caminho convencional do SAGL
            candidate = f"{self.portal_url}/sapl_documentos/parlamentar/fotos/{photo_name}"
            if self._url_exists(candidate):
                photo_url = candidate

        if photo_url:
            try:
                resp = requests.get(photo_url, timeout=IMAGE_TIMEOUT)
                img = Image.open(BytesIO(resp.content))
                fmt = (img.format or '').lower()
                member_data.update({
                    "url_foto": photo_url,
                    "image": [{
                        "content-type": f"image/{fmt}" if fmt else "image",
                        "download": photo_url,
                        "filename": photo_name,
                        "width": getattr(img, 'width', None),
                        "height": getattr(img, 'height', None),
                        "size": len(resp.content),
                    }]
                })
                return
            except (UnidentifiedImageError, requests.RequestException):
                # cai para avatar padrão
                pass

        member_data.update({
            "url_foto": f"{self.portal_url}{DEFAULT_AVATAR}",
            "image": []
        })

    def _get_member_parties(self, member_id):
        """Retorna filiações ativas do parlamentar."""
        parties = []
        for fil in self.context.zsql.filiacao_obter_zsql(ind_excluido=0, cod_parlamentar=member_id):
            if not getattr(fil, 'dat_desfiliacao', None):
                pr = list(self.context.zsql.partido_obter_zsql(
                    ind_excluido=0, cod_partido=fil.cod_partido
                ))
                if pr:
                    parties.append({
                        "token": pr[0].sgl_partido,
                        "title": pr[0].nom_partido
                    })
        return parties

    def _get_historical_periods(self, committee_id, current_date):
        """Retorna períodos de composição anteriores (não vigentes)."""
        periods = []
        for period in self.context.zsql.periodo_comp_comissao_obter_zsql(ind_excluido=0):
            try:
                dt_start = DateTime(period.dat_inicio_periodo, datefmt='international')
                dt_end = DateTime(period.dat_fim_periodo, datefmt='international')
            except Exception:
                continue

            is_current = (dt_start <= current_date <= dt_end)

            period_data = {
                "title": "Composição da Comissão",
                "description": f"{dt_start.strftime('%d/%m/%Y')} a {dt_end.strftime('%d/%m/%Y')}",
                "start": dt_start.strftime("%Y-%m-%d"),
                "end": dt_end.strftime("%Y-%m-%d"),
                "id": period.cod_periodo_comp,
                "atual": is_current,
                "items": []
            }

            for m in self.context.zsql.composicao_comissao_obter_zsql(
                cod_comissao=committee_id,
                cod_periodo_comp=period.cod_periodo_comp
            ):
                if not getattr(m, 'dat_desligamento', None):
                    period_data["items"].append({
                        "@id": f"{self.portal_url}/@@vereadores/{m.cod_parlamentar}",
                        "@type": "ParticipanteComissao",
                        "id": str(m.cod_parlamentar),
                        "title": m.nom_parlamentar,
                        "description": getattr(m, 'nom_completo', '') or m.nom_parlamentar,
                        "cargo": m.des_cargo,
                        "mandato": "Titular" if getattr(m, 'ind_titular', 0) == 1 else "Suplente",
                        "partido": self._get_member_parties(m.cod_parlamentar)
                    })

            if not is_current:
                periods.append(period_data)

        return periods

    # --------------------------
    # Reuniões
    # --------------------------

    def list_committee_meetings(self, committee_id):
        """Lista reuniões de uma comissão."""
        meetings = []
        try:
            cod = int(committee_id)
        except (TypeError, ValueError):
            cod = None
        if cod is None:
            return {"@type": "ReunioesComissao", "description": "Comissão inválida", "items": meetings}

        for r in self.context.zsql.reuniao_comissao_obter_zsql(cod_comissao=cod, ind_excluido=0):
            try:
                dt = DateTime(r.dat_inicio_reuniao, datefmt='international')
            except Exception:
                continue

            meeting_date = dt.strftime("%Y-%m-%d")
            meetings.append({
                "@id": f"{self.service_url}/{committee_id}/reunioes/{r.cod_reuniao}",
                "@type": "ReuniaoComissao",
                "id": str(r.cod_reuniao),
                "title": f"{r.num_reuniao}ª Reunião {r.des_tipo_reuniao}",
                "description": f"{dt.strftime('%d/%m/%Y')} - {r.hr_inicio_reuniao}",
                "data": meeting_date,
                "ano": dt.strftime("%Y"),
                "hora_abertura": r.hr_inicio_reuniao,
                "hora_encerramento": getattr(r, 'hr_fim_reuniao', ''),
                "arquivo_pauta": self._get_pdf_attachment(r.cod_reuniao, 'pauta'),
                "arquivo_ata": self._get_pdf_attachment(r.cod_reuniao, 'ata'),
            })

        meetings.sort(key=lambda x: x["data"], reverse=True)
        return {
            "@type": "ReunioesComissao",
            "description": f"Lista de reuniões da comissão {committee_id}",
            "items": meetings
        }

    def get_meeting_details(self, meeting_id):
        """Detalha uma reunião específica."""
        meeting = self._get_meeting_by_id(meeting_id)
        if not meeting:
            return {}

        try:
            dt = DateTime(meeting.dat_inicio_reuniao, datefmt='international')
        except Exception:
            dt = None

        committee = self._get_committee_by_id(meeting.cod_comissao)
        base = {
            "@id": f"{self.service_url}/{meeting.cod_comissao}/reunioes/{meeting.cod_reuniao}",
            "@type": "ReuniaoComissao",
            "id": str(meeting.cod_reuniao),
            "title": f"{meeting.num_reuniao}ª Reunião {meeting.des_tipo_reuniao}",
            "tipo": meeting.des_tipo_reuniao,
            "tema": getattr(meeting, 'txt_tema', ''),
            "comissao": committee.nom_comissao if committee else "",
            "comissao_id": str(meeting.cod_comissao),
            "arquivo_pauta": self._get_pdf_attachment(meeting.cod_reuniao, 'pauta'),
            "arquivo_ata": self._get_pdf_attachment(meeting.cod_reuniao, 'ata'),
        }
        if dt:
            base.update({
                "start": dt.strftime("%Y-%m-%d"),
                "ano": dt.strftime("%Y"),
                "description": f"{dt.strftime('%d/%m/%Y')} - {meeting.hr_inicio_reuniao}",
                "hora_abertura": meeting.hr_inicio_reuniao,
                "hora_encerramento": getattr(meeting, 'hr_fim_reuniao', ''),
            })
        else:
            base.update({
                "start": "",
                "ano": "",
                "description": "",
                "hora_abertura": getattr(meeting, 'hr_inicio_reuniao', ''),
                "hora_encerramento": getattr(meeting, 'hr_fim_reuniao', ''),
            })
        return base

    # --------------------------
    # Anexos (PDFs)
    # --------------------------

    def _get_pdf_attachment(self, meeting_id, attachment_type):
        """Retorna metadados de um anexo PDF da reunião."""
        suffix = PDF_TYPES.get(attachment_type)
        if not suffix:
            return []
        filename = f"{meeting_id}{suffix}"
        try:
            pasta = self.context.sapl_documentos.reuniao_comissao
        except Exception:
            pasta = None

        if pasta and hasattr(pasta, filename):
            return [{
                "content-type": "application/pdf",
                "download": f"{self.portal_url}/sapl_documentos/reuniao_comissao/{filename}",
                "filename": filename,
                "size": ""  # pode ser calculado sob demanda se necessário
            }]
        return []
