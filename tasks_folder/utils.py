from AccessControl.SecurityManagement import newSecurityManager, noSecurityManager
from Testing.makerequest import makerequest
from ZODB.POSException import ConflictError
from zope.traversing.interfaces import BeforeTraverseEvent
from zope.component.hooks import setSite
from zope.event import notify
import transaction
import Zope2
import logging
from celery import Celery, Task
import os
import pypdf
from dateutil.parser import parse
from asn1crypto import cms
import qrcode
from io import BytesIO
from functools import wraps

celery = Celery('tasks', config_source='celeryconfig')

class AfterCommitTask(Task):
    """Tarefa que só será enfileirada após o commit da transação ZODB."""
    abstract = True

    def apply_async(self, args=None, kwargs=None, **options):
        try:
            txn = transaction.get()
            if not txn.isDoomed():
                txn.addAfterCommitHook(
                    self._run_after_commit,
                    args=[args, kwargs, options]
                )
                return None
        except Exception as e:
            logging.warning(f"[AfterCommitTask] Falha ao registrar hook: {e}", exc_info=True)

        # fallback imediato
        return super().apply_async(args=args, kwargs=kwargs, **options)

    def _run_after_commit(self, success, args, kwargs, options):
        if success:
            try:
                super().apply_async(args=args, kwargs=kwargs, **options)
            except Exception as e:
                logging.error(f"[AfterCommitTask] Erro ao executar tarefa pós-commit: {e}", exc_info=True)
        else:
            logging.warning("[AfterCommitTask] Transação abortada. Tarefa não foi enfileirada.")

def zope_task(**task_kw):
    task_kw.setdefault("bind", True)

    def wrap(func):
        @wraps(func)
        def task_instance(self, *args, **kw):
            site_path = kw.pop('site_path', 'sagl').strip().strip('/')
            cod_proposicao = kw.get('cod_proposicao', None)
            cod_info = f" | cod_proposicao={cod_proposicao}" if cod_proposicao else ""

            retry_count = getattr(self.request, 'retries', 0)
            if retry_count > 0:
                logging.warning(f"[zope_task] Retry #{retry_count}{cod_info} para tarefa {func.__name__}")
                logging.info(f"[zope_task] {func.__name__} | Tentativa #{retry_count} com task_id={self.request.id}")
                exc = self.request._excinfo[1] if self.request._excinfo else None
                if exc:
                    logging.warning(f"[zope_task] Erro anterior: {exc}")
            else:
                logging.info(f"[zope_task] Primeira execução de {func.__name__}{cod_info}")

            try:
                buildout_dir = os.environ.get('BUILDOUT_DIR', '../')
                os.chdir(buildout_dir)
                os.environ['ZOPE_CONFIG'] = os.path.join('parts', 'instance', 'etc', 'zope.conf')
                app = makerequest(Zope2.app())
            except Exception as configure_error:
                logging.error(f'[zope_task] Erro ao configurar Zope{cod_info}: {configure_error}', exc_info=True)
                raise

            transaction.begin()
            try:
                site = app.unrestrictedTraverse(site_path)
                notify(BeforeTraverseEvent(site, site.REQUEST))
                user = app.acl_users.getUserById('admin')
                newSecurityManager(None, user)

                result = func(self, site, *args, **kw)
                transaction.commit()
                return result

            except ConflictError as e:
                transaction.abort()
                logging.warning(f"[zope_task] Conflito de transação{cod_info}: {e}", exc_info=True)

                if retry_count < 3:
                    countdown = 5 + (retry_count * 5)
                    logging.info(f"[zope_task] Reenfileirando manualmente retry #{retry_count + 1} em {countdown}s...{cod_info}")
                    self.app.send_task(
                        self.name,
                        args=args,
                        kwargs=kw,
                        countdown=countdown,
                        retry=True,
                        retry_policy={
                            'max_retries': 3,
                            'interval_start': 10,
                            'interval_step': 10,
                            'interval_max': 60,
                        }
                    )
                    return None
                else:
                    logging.error(f"[zope_task] Número máximo de retries atingido para {self.name}{cod_info}")
                    raise

            except Exception as e:
                transaction.abort()
                logging.error(f"[zope_task] Erro durante execução da tarefa{cod_info}: {e}", exc_info=True)
                raise

            finally:
                try:
                    noSecurityManager()
                    setSite(None)
                    app._p_jar.close()
                except Exception as fe:
                    logging.warning(f"[zope_task] Falha ao fechar site/app{cod_info}: {fe}", exc_info=True)

        return celery.task(base=AfterCommitTask, **task_kw)(task_instance)

    return wrap

def make_qrcode(text):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    fp = BytesIO()
    img.save(fp, "PNG")
    return fp

def get_signatures(fileStream):
    try:
        reader = pypdf.PdfReader(fileStream)
        fields = reader.get_fields()
        signature_field_values = [f.value for f in fields.values() if f.field_type == '/Sig']
        lst_signers = []
        for v in signature_field_values:
            try:
                if '/M' in v:
                    signing_time = parse(v['/M'][2:].strip("'").replace("'", ":"))
                else:
                    signing_time = None
                if '/Name' in v:
                    name, cpf = v['/Name'].split(':')[0:2]
                else:
                    name, cpf = None, None
                raw_signature_data = v['/Contents']
                for attrdict in parse_signatures(raw_signature_data):
                    dic = {
                        'signer_name': name or attrdict.get('signer'),
                        'signer_cpf': cpf or attrdict.get('cpf'),
                        'signing_time': str(signing_time) or attrdict.get('signing_time'),
                        'signer_certificate': attrdict.get('oname')
                    }
                    lst_signers.append(dic)
            except Exception as e:
                logging.error(f"Erro ao processar assinatura: {e}")
                continue
        lst_signers.sort(key=lambda dic: dic['signing_time'], reverse=True)
        return lst_signers
    except Exception as e:
        logging.error(f"Erro ao obter assinaturas: {e}")
        return None

def parse_signatures(raw_signature_data):
    try:
        info = cms.ContentInfo.load(raw_signature_data)
        signed_data = info['content']
        certificates = signed_data['certificates']
        signer_infos = signed_data['signer_infos'][0]
        signers = []
        for signer_info in signer_infos:
            for cert in certificates:
                cert = cert.native['tbs_certificate']
                issuer = cert['issuer']
                subject = cert['subject']
                oname = issuer.get('organization_name', '')
                lista = subject['common_name'].split(':')
                signer = lista[0]
                cpf = lista[1] if len(lista) > 1 else ''
                dic = {
                    'type': subject.get('organization_name', ''),
                    'signer': signer,
                    'cpf': cpf,
                    'oname': oname
                }
        signers.append(dic)
        return signers
    except Exception as e:
        logging.error(f"Erro ao analisar assinaturas: {e}")
        return None
