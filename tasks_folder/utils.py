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

celery = Celery('tasks', config_source='celeryconfig')

class AfterCommitTask(Task):
    """Base para tarefas que se enfileiram após o commit."""
    abstract = True
    def apply_async(self, *args, **kw):
        def hook(success):
            if success:
                super(AfterCommitTask, self).apply_async(*args, **kw)
        transaction.get().addAfterCommitHook(hook)

def zope_task(**task_kw):
    """Decorador de tarefas Celery que executa em contexto Zope com retry e commit."""
    def wrap(func):
        @celery.task(bind=True, base=AfterCommitTask, **task_kw)
        def task_wrapper(self, *args, **kw):
            site_path = kw.pop('site_path', 'sagl').strip().strip('/')
            try:
                buildout_dir = os.environ.get('BUILDOUT_DIR', '../')
                os.chdir(buildout_dir)
                os.environ['ZOPE_CONFIG'] = os.path.join('parts', 'instance', 'etc', 'zope.conf')
                app = makerequest(Zope2.app())
            except Exception as configure_error:
                logging.error(f'Falha na configuração do Zope: {configure_error}', exc_info=True)
                raise

            transaction.begin()
            try:
                site = app.unrestrictedTraverse(site_path)
                from Products.CMFCore.utils import getToolByName
                user_folder = getToolByName(site, 'acl_users')
                user = user_folder.getUserById('admin') or user_folder.getUserById('manager')
                if user is not None:
                    newSecurityManager(None, user.__of__(user_folder))

                result = func(site, *args, **kw)
                transaction.commit()
                return result

            except ConflictError as e:
                transaction.abort()
                logging.warning("ConflictError (ZODB): tentativa de retry", exc_info=True)
                raise self.retry(exc=e, countdown=2, max_retries=5)

            except Exception as e:
                transaction.abort()
                logging.error(f"Erro durante execução da tarefa Zope: {e}", exc_info=True)
                raise

            finally:
                noSecurityManager()
                setSite(None)
                if hasattr(app, '_p_jar') and app._p_jar is not None:
                    app._p_jar.sync()
                    app._p_jar.close()

        return task_wrapper
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
        signature_field_values = [
            f.value for f in fields.values() if f.field_type == '/Sig']
        lst_signers = []
        for v in signature_field_values:
            try:
                if '/M' in v:
                   signing_time = parse(v['/M'][2:].strip("'").replace("'", ":"))
                else:
                    signing_time = None
                if '/Name' in v:
                   name = v['/Name'].split(':')[0]
                   cpf = v['/Name'].split(':')[1]
                else:
                   name = None
                   cpf = None
                raw_signature_data = v['/Contents']
                for attrdict in parse_signatures(raw_signature_data):
                    dic = {
                      'signer_name':name or attrdict.get('signer'),
                      'signer_cpf':cpf or attrdict.get('cpf'),
                      'signing_time':str(signing_time) or attrdict.get('signing_time'),
                      'signer_certificate': attrdict.get('oname')
                    }
                    lst_signers.append(dic)
            except (KeyError, ValueError, TypeError) as e:
                logging.error(f"Erro ao processar assinatura: {e}")
                continue  # Pula para a próxima assinatura em caso de erro
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
                if len(lista) > 1:
                   signer = subject['common_name'].split(':')[0]
                   cpf = subject['common_name'].split(':')[1]
                else:
                   signer = subject['common_name'].split(':')[0]
                   cpf = ''
                dic = {
                   'type': subject.get('organization_name', ''),
                   'signer': signer,
                   'cpf':  cpf,
                   'oname': oname
                }
        signers.append(dic)
        return signers
    except Exception as e:
        logging.error(f"Erro ao analisar assinaturas: {e}")
        return None
