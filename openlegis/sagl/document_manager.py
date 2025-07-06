# -*- coding: utf-8 -*-
from zope.interface import implementer
from openlegis.sagl.interfaces import ISAPLDocumentManager

try:
    import Zope2
except ImportError:
    Zope2 = None

@implementer(ISAPLDocumentManager)
class SAPLDocumentManager:
    """
    Gerenciador de documentos na ZODB para proposições, normas, etc.
    Sempre busca sapl_documentos em app['sagl'].
    """

    def __init__(self, context):
        self.context = context

    def _get_sapl_documentos(self):
        """
        Tenta obter o objeto sapl_documentos da raiz.
        Retorna (sapl_documentos, app) para permitir fechar a conexão posteriormente.
        """
        root = None
        try:
            if hasattr(self.context, 'getPhysicalRoot'):
                root = self.context.getPhysicalRoot()
            else:
                root = getattr(self.context, 'context', None)
        except Exception:
            root = None

        if root is not None:
            try:
                sagl = root['sagl'] if 'sagl' in root else None
                sapl_documentos = sagl['sapl_documentos'] if sagl and 'sapl_documentos' in sagl else None
                if sapl_documentos:
                    return (sapl_documentos, None)
            except Exception:
                pass

        try:
            if Zope2 is not None:
                app = Zope2.app()
                sagl = app['sagl'] if 'sagl' in app else None
                sapl_documentos = sagl['sapl_documentos'] if sagl and 'sapl_documentos' in sagl else None
                if sapl_documentos:
                    return (sapl_documentos, app)
        except Exception:
            pass

        return (None, None)

    def existe_documento(self, tipo, nome):
        """
        Verifica se existe um arquivo chamado <nome> em sapl_documentos[tipo].
        Fecha a conexão ZODB após a verificação se usar Zope2.app().
        """
        sapl_documentos, app = self._get_sapl_documentos()
        if sapl_documentos is None:
            if app and hasattr(app, '_p_jar'):
                app._p_jar.close()
            return False
        try:
            container = sapl_documentos.get(tipo)
            if container is None:
                if app and hasattr(app, '_p_jar'):
                    app._p_jar.close()
                return False
            existe = nome in container
            if app and hasattr(app, '_p_jar'):
                app._p_jar.close()
            return existe
        except Exception:
            if app and hasattr(app, '_p_jar'):
                app._p_jar.close()
            return False

    def listar_documentos(self, tipo):
        """
        Lista todos os nomes de arquivos existentes em sapl_documentos[tipo].
        """
        sapl_documentos, app = self._get_sapl_documentos()
        if sapl_documentos is None:
            if app and hasattr(app, '_p_jar'):
                app._p_jar.close()
            return []
        try:
            container = sapl_documentos.get(tipo)
            if container is None:
                if app and hasattr(app, '_p_jar'):
                    app._p_jar.close()
                return []
            arquivos = list(container.keys())
            if app and hasattr(app, '_p_jar'):
                app._p_jar.close()
            return arquivos
        except Exception:
            if app and hasattr(app, '_p_jar'):
                app._p_jar.close()
            return []

    @property
    def sapl_documentos_url(self):
        """
        Retorna a URL base pública dos arquivos sapl_documentos.
        """
        return '/sagl/sapl_documentos'
