# -*- coding: utf-8 -*-
from io import BytesIO, StringIO
from Acquisition import aq_inner
from five import grok
from zope.interface import Interface
import json
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import csv
from datetime import datetime
try:
    # Py 3.11+
    from datetime import UTC
except ImportError:  # Py < 3.11
    from datetime import timezone as _tz
    UTC = _tz.utc

import logging
import requests
from requests.auth import HTTPBasicAuth

# SQLAlchemy via z3c.saconfig (pool/engine gerenciados pelo Zope)
from z3c.saconfig import named_scoped_session
from sqlalchemy import text

# Progresso persistente
from BTrees.OOBTree import OOBTree
from zope.annotation import IAnnotations

# ==========================
# Configuração global (defaults)
# ==========================
Session = named_scoped_session('minha_sessao')

# Logger
logger = logging.getLogger('sagl.migrar_arquivos')
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

# Tuning padrão
BATCH_SIZE_DEFAULT   = 200     # arquivos por lote
MAX_RETRIES_DEFAULT  = 3       # tentativas por item
BACKOFF_DEFAULT      = 0.75    # fator de backoff exponencial
TIMEOUT_DEFAULT      = 30      # timeout (s)
WORKERS_DEFAULT      = 8       # threads por lote (1..32)

# Rate limiting (token bucket) + adaptativo
RATE_DEFAULT         = 20.0    # req/s alvo
BURST_DEFAULT        = 40      # rajada
MIN_GAP_DEFAULT_MS   = 0       # pausa extra entre lotes (ms)
ERR_THRES_DEFAULT    = 0.05    # limiar de erro para AIMD

# Checkpoint
CHECKPOINT_EVERY_DEFAULT = 1   # gravar checkpoint a cada N chunks

RETRY_STATUS = {429, 500, 502, 503, 504}
HEAD_FALLBACK_STATUSES = {403, 405, 501}

# Progresso
PROGRESS_KEY = 'migrar_jobs'
_progress_lock = threading.Lock()

_DURATION_RE = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*([smhdw]?)\s*$', re.I)
_UNIT2SEC = {'': 1, 's': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}

def _now_iso():
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def _parse_duration_to_seconds(s, default_seconds=7*86400):
    """Aceita '90s', '15m', '12h', '7d', '2w' ou só número (segundos)."""
    if not s:
        return default_seconds
    m = _DURATION_RE.match(str(s))
    if not m:
        return default_seconds
    val = float(m.group(1))
    unit = m.group(2).lower()
    return int(val * _UNIT2SEC.get(unit, 1))

# ---------- Token Bucket (global por processo) ----------
class TokenBucket(object):
    def __init__(self, rate_per_sec=RATE_DEFAULT, burst=BURST_DEFAULT):
        self.rate = float(rate_per_sec)
        self.capacity = float(burst)
        self.tokens = float(burst)
        self.timestamp = time.time()
        self.lock = threading.Lock()

    def set_params(self, rate_per_sec=None, burst=None):
        with self.lock:
            if rate_per_sec is not None:
                self.rate = float(rate_per_sec)
            if burst is not None:
                self.capacity = float(burst)
                self.tokens = min(self.tokens, self.capacity)

    def consume(self, tokens=1.0):
        with self.lock:
            now = time.time()
            delta = now - self.timestamp
            self.timestamp = now
            self.tokens = min(self.capacity, self.tokens + delta * self.rate)
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

_bucket = TokenBucket()

class migrarArquivos(grok.View):
    grok.context(Interface)
    grok.require('zope2.View')
    grok.name('migrar_arquivos')

    migrate = None
    base_url = 'http://localhost:8180/sagl/'
    basic = HTTPBasicAuth('admin', 'openlegis')

    # ---------------------------
    # Roteamento tipo /@@migrar_arquivos/migrate/<alvo>
    # ---------------------------
    def publishTraverse(self, request, name):
        if not hasattr(self, 'subpath'):
            self.subpath = []
        self.subpath.append(name)
        for index, value in enumerate(self.subpath):
            if value == "migrate" and index < len(self.subpath) - 1:
                next_element = self.subpath[index + 1]
                self.migrate = next_element
        return self

    # ---------------------------
    # Ajuda / catálogo de rotas
    # ---------------------------
    def help(self):
        base = self.service_url
        exemplos = {
            "origem atual (base_url)": self.base_url,
            "listar rotas": base,
            "migrar materia (normal)": f"{base}/migrate/materia?batch=200&workers=12",
            "migrar materia (dry-run)": f"{base}/migrate/materia?dry=1&batch=150&workers=12",
            "migrar com faixa de IDs": f"{base}/migrate/materia?start_id=1000&end_id=5000",
            "migrar com retry/backoff": f"{base}/migrate/assinados?retries=5&backoff=1.0&timeout=40",
            "rate limit fixo": f"{base}/migrate/materia?rate=12&burst=24",
            "checkpoint a cada 3 chunks": f"{base}/migrate/materia?checkpoint_every=3",
            "retomar job interrompido": f"{base}/migrate/materia?job=<job_id>&resume=1&workers=8",
            "ver status de um job": f"{base}/migrate/status/<job_id>",
            "listar todos os jobs": f"{base}/migrate/jobs",
            "limpar jobs antigos (>7d)": f"{base}/migrate/cleanup?older=7d",
            "exportar CSV das falhas (chamada atual)": f"{base}/migrate/materia?export=csv",
            "definir nível de log": f"{base}/migrate/materia?log=DEBUG",
        }

        funcionalidades = {
            "config_atual": {  # <-- seção clara de configuração ativa
                "base_url": self.base_url,
             },
            "features": [
                "SQLAlchemy via z3c.saconfig",
                "Chunking por lote",
                "Paralelismo com ThreadPoolExecutor",
                "Retry com backoff exponencial",
                "Recorte por start_id / end_id",
                "Dry-run (?dry=1) usando HEAD/GET stream",
                "Rate limiting (token bucket) + AIMD adaptativo",
                "Job tracking persistente (Annotations) com status e progresso",
                "Checkpointing por chunk e retomada (?resume=1&job=<id>)",
                "Cleanup jobs antigos (/migrate/cleanup?older=7d)",
                "Export CSV de falhas (?export=csv) na chamada atual",
                "Endpoint /migrate/jobs listando todos os jobs",
                "Logging de progresso no console (?log=DEBUG|INFO|...)",  # <-- novo
            ],
            "tipos_suportados": {
                'Documentos Assinados': 'assinados',
                'Documentos Administrativos': 'administrativo',
                'Documentos Administrativos - acessorios': 'administrativo_doc',
                'Documentos Administrativos - tramitação': 'administrativo_tram',
                'Emendas': 'emenda',
                'Matérias Legislativas': 'materia',
                'Matérias Legislativas - acessórios': 'materia_doc',
                'Matérias Legislativas - tramitações': 'materia_tram',
                'Normas Jurídicas PDF': 'norma',
                'Normas Jurídicas compiladas': 'norma_compilada',
                'Normas Jurídicas ODT': 'norma_odt',
                'Normas Jurídicas anexos': 'norma_anexo',
                'Pareceres': 'parecer',
                'Petições': 'peticao',
                'Proposições': 'proposicao',
                'Proposições Assinadas': 'proposicao_signed',
                'Proposições ODT': 'proposicao_odt',
                'Proposições - anexos': 'proposicao_anexo',
                'Protocolo': 'protocolo',
                'Reuniões Comissões - atas': 'reuniao_ata',
                'Reuniões Comissões - pautas': 'reuniao_pauta',
                'Sessões Plenárias - atas': 'sessao_ata',
                'Sessões Plenárias - pautas': 'sessao_pauta',
                'Substitutivos': 'substitutivo',
                'STATUS de job': 'status/<job_id>',
                'LISTA de jobs': 'jobs',
                'LIMPEZA de jobs antigos': 'cleanup?older=7d',
            },
            "exemplos": exemplos,
            "parametros": {
                "batch": "tamanho do lote (default 200)",
                "workers": "threads paralelas por lote (default 8, máx 32)",
                "retries": "tentativas por item (default 3)",
                "backoff": "fator backoff exponencial (default 0.75)",
                "timeout": "timeout por requisição em segundos (default 30)",
                "start_id/end_id": "faixa de IDs",
                "dry": "1 para dry-run",
                "rate/burst": "rate limit (req/s) e burst",
                "min_gap": "ms de pausa extra entre lotes",
                "err_thres": "limiar de erro para AIMD (default 0.05)",
                "resume": "1 para retomar job existente",
                "job": "job_id para retomar",
                "checkpoint_every": "checkpoint a cada N chunks (default 1)",
                "export": "csv para exportar falhas como CSV",
                "log": "nível de log: DEBUG, INFO, WARNING, ERROR",
            }
        }

        return {"help": funcionalidades}

    # ---------------------------
    # Logging helpers
    # ---------------------------
    def _apply_log_level(self):
        lvl = str(self.request.get('log', '') or '').upper()
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
        }
        if lvl in levels:
            logger.setLevel(levels[lvl])
            logger.info("Setando nível de log para %s", lvl)
        return logger.level

    def _log_progress(self, job_id, phase, processed, total, converted, failed,
                      metrics=None, workers=None, min_gap_ms=None):
        try:
            pct = (processed * 100.0 / total) if total else 0.0
        except Exception:
            pct = 0.0
        lat = metrics.get('avg_latency') if metrics else None
        err = metrics.get('last_err_rate') if metrics else None
        mtxt = ""
        if lat is not None:
            mtxt += f" avg_lat={lat:.3f}s"
        if err is not None:
            mtxt += f" err_rate={err:.3f}"
        logger.info(
            "[job=%s] %s: %s/%s (%.1f%%) ok=%s fail=%s workers=%s gap_ms=%s%s",
            job_id, phase, processed, total, pct, converted, failed, workers, min_gap_ms, mtxt
        )

    # ---------------------------
    # Progresso (Annotations)
    # ---------------------------
    def _get_jobs(self):
        ann = IAnnotations(self.context.portal_url.getPortalObject())
        jobs = ann.get(PROGRESS_KEY)
        if jobs is None:
            jobs = OOBTree()
            ann[PROGRESS_KEY] = jobs
        return jobs

    def _ensure_job(self, tune):
        jobs = self._get_jobs()
        job_id = self.request.get('job')
        if not job_id:
            job_id = uuid.uuid4().hex[:12]
        with _progress_lock:
            if job_id not in jobs:
                jobs[job_id] = {
                    "job_id": job_id,
                    "created_at": _now_iso(),
                    "status": "running",
                    "phase": "preparing",
                    "params": {k: v for k, v in tune.items() if k not in ("dry_run", "resume")},
                    "dry_run": bool(tune.get("dry_run")),
                    "total": 0,
                    "processed": 0,
                    "converted": 0,
                    "failed": 0,
                    "workers": tune.get("workers", WORKERS_DEFAULT),
                    "min_gap_ms": tune.get("min_gap_ms", MIN_GAP_DEFAULT_MS),
                    "last_update": _now_iso(),
                    "ended_at": None,
                }
                logger.info("[job=%s] criado | params=%s", job_id, jobs[job_id]["params"])
            else:
                if tune.get("resume"):
                    job = jobs[job_id]
                    job["status"] = "running"
                    job["phase"] = "resuming"
                    job["last_update"] = _now_iso()
                    logger.info("[job=%s] retomando job existente", job_id)
        return job_id

    def _update_progress(self, job_id, **kv):
        jobs = self._get_jobs()
        with _progress_lock:
            job = jobs.get(job_id)
            if not job:
                return
            job.update(kv)
            job["last_update"] = _now_iso()

    def status(self, job_id):
        jobs = self._get_jobs()
        job = jobs.get(job_id)
        if not job:
            return json.dumps({"error": "job not found"}, ensure_ascii=False)
        return json.dumps(job, sort_keys=True, indent=2, ensure_ascii=False).encode('utf8').decode('utf8')

    def list_jobs(self):
        jobs = self._get_jobs()
        with _progress_lock:
            payload = [jobs[jid].copy() for jid in jobs.keys()]
        payload.sort(key=lambda j: j.get("created_at", ""), reverse=True)
        logger.info("Listando %d job(s)", len(payload))
        return json.dumps({"count": len(payload), "jobs": payload},
                          sort_keys=True, indent=2, ensure_ascii=False).encode('utf8').decode('utf8')

    # ---------------------------
    # Limpador de jobs antigos
    # ---------------------------
    def cleanup_jobs(self, older_param):
        ttl_sec = _parse_duration_to_seconds(older_param, default_seconds=7*86400)
        cutoff = time.time() - ttl_sec

        def _iso_to_ts(iso):
            if not iso:
                return 0
            try:
                if iso.endswith('Z'):
                    iso = iso[:-1] + '+00:00'
                dt = datetime.fromisoformat(iso)
                epoch = datetime(1970, 1, 1, tzinfo=UTC)
                return int((dt - epoch).total_seconds())
            except Exception:
                return 0

        jobs = self._get_jobs()
        removed = []
        kept = 0
        with _progress_lock:
            for jid in list(jobs.keys()):
                job = jobs.get(jid)
                if not job:
                    continue
                ended_ts = _iso_to_ts(job.get("ended_at"))
                created_ts = _iso_to_ts(job.get("created_at"))
                ref_ts = ended_ts or created_ts
                if ref_ts and ref_ts < cutoff:
                    removed.append(jid)
                    del jobs[jid]
                else:
                    kept += 1
        logger.info("Cleanup de jobs: removidos=%d, mantidos=%d (older=%s)", len(removed), kept, older_param)
        return json.dumps({
            "removed": removed,
            "removed_count": len(removed),
            "kept": kept,
            "older_param": older_param,
            "cutoff_seconds": ttl_sec
        }, sort_keys=True, indent=2, ensure_ascii=False).encode('utf8').decode('utf8')

    # ---------------------------
    # Helpers HTTP (thread-safe)
    # ---------------------------
    def _tls(self):
        if not hasattr(self, "_thread_local"):
            self._thread_local = threading.local()
        return self._thread_local

    def _tls_http(self):
        tls = self._tls()
        if not hasattr(tls, "http_session"):
            tls.http_session = requests.Session()
        return tls.http_session

    def _http_request_with_retry(self, session, method, url, *, auth=True,
                                 max_retries=MAX_RETRIES_DEFAULT,
                                 backoff_factor=BACKOFF_DEFAULT,
                                 timeout=TIMEOUT_DEFAULT,
                                 stream=False):
        kwargs = {"timeout": timeout, "stream": stream}
        if auth:
            kwargs["auth"] = self.basic
        for attempt in range(1, max_retries + 1):
            try:
                resp = session.request(method, url, **kwargs)
                if resp.status_code < 400:
                    if attempt > 1:
                        logger.debug("Sucesso após retry (%s) %s", attempt, url)
                    return resp
                if resp.status_code in RETRY_STATUS and attempt < max_retries:
                    sleep_s = backoff_factor * (2 ** (attempt - 1))
                    logger.debug("HTTP %s -> retry %d em %.2fs (%s)", resp.status_code, attempt, sleep_s, url)
                    time.sleep(sleep_s)
                    continue
                return resp
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt < max_retries:
                    sleep_s = backoff_factor * (2 ** (attempt - 1))
                    logger.debug("Exceção %s -> retry %d em %.2fs (%s)", type(exc).__name__, attempt, sleep_s, url)
                    time.sleep(sleep_s)
                    continue
                logger.warning("Falha de rede/timeout após %d tentativas (%s)", attempt, url)
                return None
        return None

    # ---------------------------
    # Helpers gerais
    # ---------------------------
    def _save_file(self, caminho, item, contents, set_title=False, content_type=None):
        if hasattr(caminho, item):
            arq = getattr(caminho, item)
            arq.manage_upload(file=contents)
        else:
            caminho.manage_addFile(id=item, file=contents)
            if set_title or content_type:
                arq = getattr(caminho, item)
                title = item if set_title else getattr(arq, 'title', '')
                ctype = content_type or getattr(arq, 'content_type', None)
                try:
                    arq.manage_edit(title=title, content_type=ctype)
                except Exception:
                    pass

    def _iter_chunks(self, seq, size):
        for i in range(0, len(seq), size):
            yield seq[i:i+size]

    def _build_url(self, pasta, item, subpasta=None):
        url_parts = [self.base_url.rstrip('/'), 'sapl_documentos', pasta]
        if subpasta:
            url_parts.append(subpasta)
        url_parts.append(item)
        return "/".join(p.strip('/') for p in url_parts)

    def _fetch_rows(self, sql, params=None):
        session = Session()
        try:
            return session.execute(text(sql), params or {}).fetchall()
        finally:
            session.close()

    # ---------- Querystring parsers ----------
    def _get_int_qs(self, name, default, min_value=1, max_value=None):
        try:
            raw = self.request.get(name, default)
            if raw in (None, ''):
                return default
            val = int(raw)
            if min_value is not None and val < min_value:
                val = min_value
            if max_value is not None and val > max_value:
                val = max_value
            return val
        except Exception:
            return default

    def _get_float_qs(self, name, default, min_value=0.0, max_value=None):
        try:
            raw = self.request.get(name, default)
            if raw in (None, ''):
                return default
            val = float(raw)
            if min_value is not None and val < min_value:
                val = min_value
            if max_value is not None and val > max_value:
                val = max_value
            return val
        except Exception:
            return default

    def _get_bool_qs(self, name, default=False):
        raw = self.request.get(name, None)
        if raw is None:
            return default
        s = str(raw).strip().lower()
        return s in ("1", "true", "t", "yes", "y", "on")

    def _runtime_tuning(self):
        return {
            "batch_size":       self._get_int_qs("batch",   BATCH_SIZE_DEFAULT,   min_value=1),
            "max_retries":      self._get_int_qs("retries", MAX_RETRIES_DEFAULT,  min_value=1),
            "backoff_factor":   self._get_float_qs("backoff", BACKOFF_DEFAULT,    min_value=0.1),
            "timeout":          self._get_int_qs("timeout", TIMEOUT_DEFAULT,      min_value=5),
            "workers":          self._get_int_qs("workers", WORKERS_DEFAULT,      min_value=1, max_value=32),
            "start_id":         self._get_int_qs("start_id", None,                min_value=1) if self.request.get("start_id") else None,
            "end_id":           self._get_int_qs("end_id",   None,                min_value=1) if self.request.get("end_id")   else None,
            "dry_run":          self._get_bool_qs("dry", False),
            # Rate limiting
            "rate":             self._get_float_qs("rate",   RATE_DEFAULT,        min_value=0.1),
            "burst":            self._get_int_qs("burst",    BURST_DEFAULT,       min_value=1),
            "min_gap_ms":       self._get_int_qs("min_gap",  MIN_GAP_DEFAULT_MS,  min_value=0),
            # AIMD
            "err_thres":        self._get_float_qs("err_thres", ERR_THRES_DEFAULT, min_value=0.0),
            # Resume + checkpoint
            "resume":           self._get_bool_qs("resume", False),
            "checkpoint_every": self._get_int_qs("checkpoint_every", CHECKPOINT_EVERY_DEFAULT, min_value=1),
        }

    # ---------- Range helper ----------
    def _apply_id_range(self, sql, id_field, start_id, end_id):
        if not id_field or (start_id is None and end_id is None):
            return sql, {}
        where_parts = []
        params = {}
        if start_id is not None:
            where_parts.append("_q.%s >= :_start_id" % id_field)
            params["_start_id"] = start_id
        if end_id is not None:
            where_parts.append("_q.%s <= :_end_id" % id_field)
            params["_end_id"] = end_id
        where_sql = " AND ".join(where_parts)
        ranged_sql = "SELECT * FROM (%s) AS _q WHERE %s" % (sql, where_sql)
        return ranged_sql, params

    # ---------- Download paralelo (somente rede) ----------
    def _download_item(self, item, *, pasta, subpasta, auth,
                       max_retries, backoff_factor, timeout, dry_run):
        """
        Executado em thread: faz HEAD (dry) ou GET (normal).
        Aplica token bucket antes de cada requisição.
        Retorna (item, bytes|None, err|None, status|None, latency_sec).
        """
        session = self._tls_http()
        url = self._build_url(pasta, item, subpasta=subpasta)

        while not _bucket.consume():
            time.sleep(0.01)

        t0 = time.time()
        if dry_run:
            resp = self._http_request_with_retry(
                session, "HEAD", url, auth=auth,
                max_retries=max_retries, backoff_factor=backoff_factor,
                timeout=timeout, stream=False
            )
            if resp is not None and resp.status_code in HEAD_FALLBACK_STATUSES:
                logger.debug("HEAD não suportado (%s), caindo para GET stream (%s)", resp.status_code, url)
                resp = self._http_request_with_retry(
                    session, "GET", url, auth=auth,
                    max_retries=max_retries, backoff_factor=backoff_factor,
                    timeout=timeout, stream=True
                )
            if resp is None:
                return (item, None, "falha de rede/timeout após retries", None, time.time()-t0)
            if resp.status_code == 200:
                return (item, None, None, 200, time.time()-t0)
            return (item, None, "HTTP %s" % resp.status_code, resp.status_code, time.time()-t0)

        resp = self._http_request_with_retry(
            session, "GET", url, auth=auth,
            max_retries=max_retries, backoff_factor=backoff_factor,
            timeout=timeout, stream=False
        )
        if resp is None:
            return (item, None, "falha de rede/timeout após retries", None, time.time()-t0)
        if resp.status_code == 200:
            return (item, resp.content, None, 200, time.time()-t0)
        return (item, None, "HTTP %s" % resp.status_code, resp.status_code, time.time()-t0)

    # ---------------------------
    # Núcleo de migração (threads + dry-run + AIMD + resume)
    # ---------------------------
    def _migrar(self, *, sql, pasta, suffix=None, subpasta=None, auth=True,
                row_to_names=None, set_title=False, content_type=None,
                batch_size=BATCH_SIZE_DEFAULT,
                max_retries=MAX_RETRIES_DEFAULT,
                backoff_factor=BACKOFF_DEFAULT,
                timeout=TIMEOUT_DEFAULT,
                workers=WORKERS_DEFAULT,
                start_id=None,
                end_id=None,
                id_field=None,
                dry_run=False,
                rate=RATE_DEFAULT,
                burst=BURST_DEFAULT,
                min_gap_ms=MIN_GAP_DEFAULT_MS,
                err_thres=ERR_THRES_DEFAULT,
                job_id=None,
                resume=False,
                checkpoint_every=CHECKPOINT_EVERY_DEFAULT):
        """
        Retorna: {"convertidos": [...], "falhas": [...], "dry_run": bool, "metrics": {...}}
        """
        _bucket.set_params(rate_per_sec=rate, burst=burst)

        ranged_sql, params = self._apply_id_range(sql, id_field, start_id, end_id)
        rows = self._fetch_rows(ranged_sql, params=params)
        caminho = getattr(self.context.sapl_documentos, pasta)
        if subpasta:
            caminho = getattr(caminho, subpasta)

        items = []
        if row_to_names:
            for row in rows:
                names = row_to_names(row)
                if isinstance(names, (list, tuple)):
                    items.extend(list(names))
                else:
                    items.append(names)
        else:
            items = [f"{row[0]}{suffix}" for row in rows]

        resume_offset = 0
        if job_id and resume:
            job = self._get_jobs().get(job_id)
            if job:
                try:
                    resume_offset = int(job.get("processed", 0) or 0)
                except Exception:
                    resume_offset = 0
                resume_offset = max(0, min(resume_offset, len(items)))
        if resume_offset:
            items = items[resume_offset:]

        total = resume_offset + len(items)
        processed = resume_offset
        converted = int(self._get_jobs().get(job_id, {}).get("converted", 0)) if job_id else 0
        failed = int(self._get_jobs().get(job_id, {}).get("failed", 0)) if job_id else 0
        healthy_chunks = 0

        logger.info(
            "[job=%s] alvo=%s sub=%s total_inicial=%s start_id=%s end_id=%s resume_offset=%s dry=%s "
            "batch=%s workers=%s rate=%.2f burst=%s timeout=%s retries=%s backoff=%.2f",
            job_id, pasta, subpasta, total, start_id, end_id, resume_offset, dry_run,
            batch_size, workers, rate, burst, timeout, max_retries, backoff_factor
        )

        if job_id:
            self._update_progress(job_id, phase=("resuming" if resume_offset else "listing"), total=total)
            self._update_progress(job_id, phase="downloading", processed=processed, converted=converted, failed=failed,
                                  workers=workers, min_gap_ms=min_gap_ms)

        convertidos = []
        falhas = []
        metrics = {"avg_latency": None, "last_err_rate": None}

        chunk_index_since_resume = 0
        for chunk in self._iter_chunks(items, batch_size):
            if min_gap_ms:
                time.sleep(min_gap_ms / 1000.0)

            downloads = []
            t_lat_total = 0.0

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(
                        self._download_item,
                        item,
                        pasta=pasta,
                        subpasta=subpasta,
                        auth=auth,
                        max_retries=max_retries,
                        backoff_factor=backoff_factor,
                        timeout=timeout,
                        dry_run=dry_run,
                    )
                    for item in chunk
                ]
                for fut in as_completed(futures):
                    item, content, err, status, latency = fut.result()
                    t_lat_total += (latency or 0.0)
                    downloads.append((item, content, err, status, latency))

            if dry_run:
                for item, content, err, status, latency in downloads:
                    if err is None:
                        convertidos.append(item)
                    else:
                        falhas.append({"item": item, "motivo": err})
            else:
                for item, content, err, status, latency in downloads:
                    if err is None and content is not None:
                        try:
                            self._save_file(
                                caminho,
                                item,
                                BytesIO(content),
                                set_title=set_title,
                                content_type=content_type
                            )
                            convertidos.append(item)
                        except Exception as e:
                            logger.warning("[job=%s] erro ao salvar '%s': %s", job_id, item, e)
                            falhas.append({"item": item, "motivo": "erro ao salvar no ZODB: %s" % (e,)})
                    else:
                        falhas.append({"item": item, "motivo": err})

            processed += len(downloads)
            chunk_errs = sum(1 for _, _, err, _, _ in downloads if err)
            chunk_ok = len(downloads) - chunk_errs
            converted += chunk_ok
            failed += chunk_errs

            err_rate = chunk_errs / float(len(downloads) or 1)
            avg_lat = (t_lat_total / float(len(downloads) or 1)) if downloads else None

            metrics["avg_latency"] = avg_lat
            metrics["last_err_rate"] = err_rate

            if err_rate > err_thres or any((status in RETRY_STATUS) for _, _, err, status, _ in downloads if status):
                logger.warning("[job=%s] alta taxa de erro=%.3f -> reduzindo workers %s→%s, aumentando gap %sms→%sms",
                               job_id, err_rate, workers, max(1, int(workers * 0.5)),
                               min_gap_ms, int(min_gap_ms * 1.5) or 50)
                workers = max(1, int(workers * 0.5))
                min_gap_ms = int(min_gap_ms * 1.5) or 50
                healthy_chunks = 0
            else:
                healthy_chunks += 1
                if healthy_chunks >= 2 and workers < 32:
                    logger.debug("[job=%s] saudável por %s chunks, aumentando workers %s→%s",
                                 job_id, healthy_chunks, workers, workers + 1)
                    workers += 1
                if min_gap_ms:
                    new_gap = int(min_gap_ms / 1.2)
                    logger.debug("[job=%s] reduzindo gap %sms→%sms", job_id, min_gap_ms, new_gap)
                    min_gap_ms = new_gap

            chunk_index_since_resume += 1
            if job_id:
                self._update_progress(job_id,
                                      processed=processed, converted=converted, failed=failed,
                                      workers=workers, min_gap_ms=min_gap_ms)
            # log de progresso por chunk
            self._log_progress(job_id, phase="chunk", processed=processed, total=total,
                               converted=converted, failed=failed, metrics=metrics,
                               workers=workers, min_gap_ms=min_gap_ms)

        logger.info("[job=%s] finalizado | ok=%s fail=%s", job_id, converted, failed)
        return {
            "convertidos": convertidos,
            "falhas": falhas,
            "dry_run": bool(dry_run),
            "metrics": metrics,
            "workers_final": workers,
            "min_gap_ms_final": min_gap_ms,
        }

    # ---------------------------
    # Métodos específicos (mapeiam parâmetros do genérico)
    # ---------------------------
    def migrarAdm(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_documento FROM documento_administrativo
                   WHERE ind_excluido=0 ORDER BY cod_documento""",
            pasta="administrativo",
            suffix="_texto_integral.pdf",
            auth=True,
            id_field="cod_documento",
            job_id=job_id,
            **tune
        )

    def migrarAdmTram(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_tramitacao FROM tramitacao_administrativo
                   WHERE ind_excluido=0 ORDER BY cod_tramitacao""",
            pasta="administrativo",
            subpasta="tramitacao",
            suffix="_tram.pdf",
            auth=True,
            id_field="cod_tramitacao",
            job_id=job_id,
            **tune
        )

    def migrarAdmAcessorio(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_documento_acessorio FROM documento_acessorio_administrativo
                   WHERE ind_excluido=0 ORDER BY cod_documento_acessorio""",
            pasta="administrativo",
            suffix=".pdf",
            auth=True,
            id_field="cod_documento_acessorio",
            job_id=job_id,
            **tune
        )

    def migrarNormas(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_norma FROM norma_juridica
                   WHERE ind_excluido=0 ORDER BY cod_norma""",
            pasta="norma_juridica",
            suffix="_texto_integral.pdf",
            auth=True,
            id_field="cod_norma",
            job_id=job_id,
            **tune
        )

    def migrarAnexoNorma(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_norma, cod_anexo FROM anexo_norma
                   WHERE ind_excluido=0 ORDER BY cod_norma""",
            pasta="norma_juridica",
            auth=True,
            row_to_names=lambda row: f"{row[0]}_anexo_{row[1]}",
            set_title=True,
            content_type="application/pdf",
            id_field="cod_norma",
            job_id=job_id,
            **tune
        )

    def migrarNormasODT(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_norma FROM norma_juridica
                   WHERE ind_excluido=0 ORDER BY cod_norma""",
            pasta="norma_juridica",
            suffix="_texto_integral.odt",
            auth=True,
            id_field="cod_norma",
            job_id=job_id,
            **tune
        )

    def migrarNormasCompiladas(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_norma FROM norma_juridica
                   WHERE ind_excluido=0 ORDER BY cod_norma""",
            pasta="norma_juridica",
            suffix="_texto_consolidado.pdf",
            auth=True,
            id_field="cod_norma",
            job_id=job_id,
            **tune
        )

    def migrarLeg(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_materia FROM materia_legislativa
                   WHERE ind_excluido=0 ORDER BY cod_materia""",
            pasta="materia",
            suffix="_texto_integral.pdf",
            auth=True,
            id_field="cod_materia",
            job_id=job_id,
            **tune
        )

    def migrarLegAcessorio(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_documento FROM documento_acessorio
                   WHERE ind_excluido=0 ORDER BY cod_documento""",
            pasta="materia",
            suffix=".pdf",
            auth=True,
            id_field="cod_documento",
            job_id=job_id,
            **tune
        )

    def migrarEmendas(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_emenda FROM emenda
                   WHERE ind_excluido=0 ORDER BY cod_emenda""",
            pasta="emenda",
            suffix="_emenda.pdf",
            auth=False,
            id_field="cod_emenda",
            job_id=job_id,
            **tune
        )

    def migrarSubstitutivos(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_substitutivo FROM substitutivo
                   WHERE ind_excluido=0 ORDER BY cod_substitutivo""",
            pasta="substitutivo",
            suffix="_substitutivo.pdf",
            auth=False,
            id_field="cod_substitutivo",
            job_id=job_id,
            **tune
        )

    def migrarPareceres(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_relatoria FROM relatoria
                   WHERE ind_excluido=0 ORDER BY cod_relatoria""",
            pasta="parecer_comissao",
            suffix="_parecer.pdf",
            auth=True,
            id_field="cod_relatoria",
            job_id=job_id,
            **tune
        )

    def migrarLegTram(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_tramitacao FROM tramitacao
                   WHERE ind_excluido=0 ORDER BY cod_tramitacao""",
            pasta="materia",
            subpasta="tramitacao",
            suffix="_tram.pdf",
            auth=False,
            id_field="cod_tramitacao",
            job_id=job_id,
            **tune
        )

    def migrarAtas(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_sessao_plen FROM sessao_plenaria
                   WHERE ind_excluido=0 ORDER BY cod_sessao_plen""",
            pasta="ata_sessao",
            suffix="_ata_sessao.pdf",
            auth=False,
            id_field="cod_sessao_plen",
            job_id=job_id,
            **tune
        )

    def migrarPautas(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_sessao_plen FROM sessao_plenaria
                   WHERE ind_excluido=0 ORDER BY cod_sessao_plen""",
            pasta="pauta_sessao",
            suffix="_pauta_sessao.pdf",
            auth=False,
            id_field="cod_sessao_plen",
            job_id=job_id,
            **tune
        )

    def migrarPeticao(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_peticao FROM peticao
                   WHERE ind_excluido=0 ORDER BY cod_peticao""",
            pasta="peticao",
            suffix=".pdf",
            auth=True,
            id_field="cod_peticao",
            job_id=job_id,
            **tune
        )

    def migrarProposicao(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_proposicao FROM proposicao
                   WHERE ind_excluido=0 ORDER BY cod_proposicao""",
            pasta="proposicao",
            suffix=".pdf",
            auth=True,
            id_field="cod_proposicao",
            job_id=job_id,
            **tune
        )

    def migrarProposicaoODT(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_proposicao FROM proposicao
                   WHERE dat_envio IS NULL AND ind_excluido=0
                   ORDER BY cod_proposicao""",
            pasta="proposicao",
            suffix=".odt",
            auth=True,
            id_field="cod_proposicao",
            job_id=job_id,
            **tune
        )

    def migrarProposicaoAssinada(self, tune, job_id=None):
        return self._migrar(
            sql="""SELECT cod_proposicao FROM proposicao
                   WHERE ind_excluido=0 ORDER BY cod_proposicao""",
            pasta="proposicao",
            suffix="_signed.pdf",
            auth=True,
            id_field="cod_proposicao",
            job_id=job_id,
            **tune
        )

    def migrarProposicaoAnexo(self, tune, job_id=None):
        base_sql = """
            SELECT cod_proposicao
              FROM proposicao
             WHERE cod_proposicao > 50000
               AND ind_excluido=0
          ORDER BY cod_proposicao
        """
        def _names(row):
            cod = str(row[0])
            return list(self.context.pysc.anexo_proposicao_pysc(cod, listar=True))

        return self._migrar(
            sql=base_sql,
            pasta="proposicao",
            auth=True,
            row_to_names=_names,
            id_field="cod_proposicao",
            job_id=job_id,
            **tune
        )

    # ---------------------------
    # Export CSV (falhas)
    # ---------------------------
    def _export_csv(self, alvo, job_id, result):
        falhas = result.get("falhas", []) or []
        sio = StringIO()
        writer = csv.writer(sio, delimiter=';')
        writer.writerow(['job_id', 'alvo', 'item', 'motivo'])
        for row in falhas:
            writer.writerow([job_id, alvo, row.get('item', ''), row.get('motivo', '')])
        output = sio.getvalue().encode('utf-8')
        resp = self.request.response
        resp.setHeader('Content-Type', 'text/csv; charset=utf-8')
        filename = f'falhas_{alvo}_{job_id or "sem_job"}.csv'
        resp.setHeader('Content-Disposition', f'attachment; filename="{filename}"')
        logger.info("[job=%s] export CSV gerado (%d falha(s))", job_id, len(falhas))
        return output

    # ---------------------------
    # Render / roteamento final
    # ---------------------------
    def render(self):
        self.portal = self.context.portal_url.getPortalObject()
        self.portal_url = self.context.portal_url()
        self.service_url = self.portal_url + '/@@migrar_arquivos'

        # aplica nível de log por querystring (se enviado)
        self._apply_log_level()

        if self.migrate == 'status' and len(getattr(self, 'subpath', [])) >= 3:
            job_id = self.subpath[-1]
            return self.status(job_id)

        if self.migrate == 'jobs':
            return self.list_jobs()

        if self.migrate == 'cleanup':
            older = self.request.get('older', '7d')
            return self.cleanup_jobs(older)

        data = {'@id': self.service_url, 'description': 'Endpoints para migração de arquivos'}
        if not self.migrate or self.migrate == 'help':
            data.update(self.help())
            serialized = json.dumps(data, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
            return serialized.decode()

        tune = self._runtime_tuning()
        job_id = self._ensure_job(tune)

        logger.info("[job=%s] iniciando rota '%s'", job_id, self.migrate)

        if self.migrate == 'assinados':
            self._update_progress(job_id, phase="running: assinados")
            result = self.migrarAssinados(tune, job_id)
        elif self.migrate == 'administrativo':
            self._update_progress(job_id, phase="running: administrativo")
            result = self.migrarAdm(tune, job_id)
        elif self.migrate == 'administrativo_tram':
            self._update_progress(job_id, phase="running: administrativo_tram")
            result = self.migrarAdmTram(tune, job_id)
        elif self.migrate == 'administrativo_doc':
            self._update_progress(job_id, phase="running: administrativo_doc")
            result = self.migrarAdmAcessorio(tune, job_id)
        elif self.migrate == 'emenda':
            self._update_progress(job_id, phase="running: emenda")
            result = self.migrarEmendas(tune, job_id)
        elif self.migrate == 'materia':
            self._update_progress(job_id, phase="running: materia")
            result = self.migrarLeg(tune, job_id)
        elif self.migrate == 'materia_doc':
            self._update_progress(job_id, phase="running: materia_doc")
            result = self.migrarLegAcessorio(tune, job_id)
        elif self.migrate == 'materia_tram':
            self._update_progress(job_id, phase="running: materia_tram")
            result = self.migrarLegTram(tune, job_id)
        elif self.migrate == 'norma':
            self._update_progress(job_id, phase="running: norma")
            result = self.migrarNormas(tune, job_id)
        elif self.migrate == 'norma_compilada':
            self._update_progress(job_id, phase="running: norma_compilada")
            result = self.migrarNormasCompiladas(tune, job_id)
        elif self.migrate == 'norma_odt':
            self._update_progress(job_id, phase="running: norma_odt")
            result = self.migrarNormasODT(tune, job_id)
        elif self.migrate == 'norma_anexo':
            self._update_progress(job_id, phase="running: norma_anexo")
            result = self.migrarAnexoNorma(tune, job_id)
        elif self.migrate == 'parecer':
            self._update_progress(job_id, phase="running: parecer")
            result = self.migrarPareceres(tune, job_id)
        elif self.migrate == 'peticao':
            self._update_progress(job_id, phase="running: peticao")
            result = self.migrarPeticao(tune, job_id)
        elif self.migrate == 'proposicao':
            self._update_progress(job_id, phase="running: proposicao")
            result = self.migrarProposicao(tune, job_id)
        elif self.migrate == 'proposicao_signed':
            self._update_progress(job_id, phase="running: proposicao_signed")
            result = self.migrarProposicaoAssinada(tune, job_id)
        elif self.migrate == 'proposicao_odt':
            self._update_progress(job_id, phase="running: proposicao_odt")
            result = self.migrarProposicaoODT(tune, job_id)
        elif self.migrate == 'proposicao_anexo':
            self._update_progress(job_id, phase="running: proposicao_anexo")
            result = self.migrarProposicaoAnexo(tune, job_id)
        elif self.migrate == 'protocolo':
            self._update_progress(job_id, phase="running: protocolo")
            result = self.migrarProtocolo(tune, job_id)
        elif self.migrate == 'reuniao_ata':
            self._update_progress(job_id, phase="running: reuniao_ata")
            result = self.migrarAtaComissao(tune, job_id)
        elif self.migrate == 'reuniao_pauta':
            self._update_progress(job_id, phase="running: reuniao_pauta")
            result = self.migrarPautaComissao(tune, job_id)
        elif self.migrate == 'sessao_ata':
            self._update_progress(job_id, phase="running: sessao_ata")
            result = self.migrarAtas(tune, job_id)
        elif self.migrate == 'sessao_pauta':
            self._update_progress(job_id, phase="running: sessao_pauta")
            result = self.migrarPautas(tune, job_id)
        elif self.migrate == 'substitutivo':
            self._update_progress(job_id, phase="running: substitutivo")
            result = self.migrarSubstitutivos(tune, job_id)
        else:
            data.update(self.help())
            serialized = json.dumps(data, sort_keys=True, indent=3, ensure_ascii=False).encode('utf8')
            return serialized.decode()

        self._update_progress(job_id, status="finished", ended_at=_now_iso())
        result["job_id"] = job_id
        logger.info("[job=%s] rota '%s' concluída", job_id, self.migrate)

        if str(self.request.get('export', '')).lower() == 'csv':
            return self._export_csv(self.migrate, job_id, result)

        return json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False).encode('utf8').decode('utf8')
