"""
SAGL setup handlers.
"""
import logging
logger = logging.getLogger('openlegis.sagl')

def setupMountPoint(portal):
    # Metodo para adicionar o mount point do sapl_documentos
    if not hasattr(portal, 'sapl_documentos'):
        path_sagl = portal.getId()
        try:
            portal.manage_addProduct['ZODBMountPoint'].manage_addMounts(paths=["/%s/sapl_documentos" % path_sagl],create_mount_points=1)
        except:
            pass
            #portal.manage_addProduct['OFSP'].manage_addFolder(id='sapl_documentos')

def setupCache(portal):
    # Metodo para adicionar cache HTTP
    if not hasattr(portal, 'HTTPCache'):
        try:
            portal.manage_addProduct['StandardCacheManagers'].manage_addAcceleratedHTTPCacheManager(id='HTTPCache')
        except:
            pass

def setupConteudo(portal):
    # Metodo para a importacao do SAGL-OpenLegis
    # estrutura do diretorio para armazenamento de documentos
    if hasattr(portal, 'sapl_documentos'):
        for o in [
            'administrativo.zexp',
            'anexo_sessao.zexp',
            'ata_sessao.zexp',
            'documento_comissao.zexp',
            'documentos_assinados.zexp',
            'emenda.zexp',
            'materia.zexp',
            'materia_odt.zexp',
            'modelo.zexp',
            'norma_juridica.zexp',
            'oradores.zexp',
            'oradores_expediente.zexp',
            'parecer_comissao.zexp',
            'parlamentar.zexp',
            'partido.zexp',
            'pauta_sessao.zexp',
            'pessoa.zexp',
            'peticao.zexp',
            'proposicao.zexp',
            'props_sagl.zexp',
            'protocolo.zexp',
            'reuniao_comissao.zexp',
            'substitutivo.zexp',
        ]:
            if o[:len(o)-5] not in portal.sapl_documentos.objectIds():
                portal.sapl_documentos.manage_importObject(o)

    # importar conteudos na raiz do SAGL
    for o in ['extensions.zexp']:
        if o[:len(o)-5] not in portal.objectIds():
            try:
                portal.manage_importObject(o)
            except Exception as e:
                # Se o arquivo não existir ou houver erro na importação, apenas loga e continua
                # O arquivo pode não estar disponível ainda ou pode ser opcional
                import logging
                logger = logging.getLogger('openlegis.sagl')
                logger.warning("Não foi possível importar %s: %s", o, str(e))


def setupAdicionarUsuarios(portal):
    # Metodo para criar usuario padrao
    try:
        portal.acl_users._addUser(name='openlegis', password='openlegis', confirm='openlegis', roles=['Operador','Administrador'], domains=[])
    except:
        pass


def importar_estrutura(context):
    if context.readDataFile('sagl-final.txt') is None:
        return
    site = context.getSite()
#    setupMountPoint(site)
    setupCache(site)
    setupConteudo(site)
    setupAdicionarUsuarios(site)


def verificar_e_criar_sagl_raiz(context):
    """Verifica se a aplicação SAGL existe na raiz do Zope e cria se não existir"""
    if context.readDataFile('sagl-final.txt') is None:
        return
    
    try:
        # Get the site from context
        site = context.getSite()
        
        # Check if the site itself is a SAGL (we're being called during SAGL creation)
        # If so, we should not try to create another SAGL
        if hasattr(site, 'meta_type') and 'SAGL' in str(site.meta_type):
            logger.debug("Import step executado durante criação de SAGL, ignorando verificação de raiz")
            return
        
        # Get the root application by traversing up
        app = site
        while hasattr(app, '__parent__') and app.__parent__ is not None:
            app = app.__parent__
        
        # Verify we're at the root (should have acl_users)
        if not hasattr(app, 'acl_users'):
            logger.warning("Não foi possível encontrar a raiz do Zope")
            return
        
        # Check if app has objectIds method (it should be a proper Zope container)
        if not hasattr(app, 'objectIds'):
            logger.warning("Objeto raiz não tem método objectIds, não é possível verificar SAGL")
            return
        
        sagl_id = 'sagl'
        
        # Check if SAGL already exists in root
        if sagl_id in app.objectIds():
            logger.info("SAGL '%s' já existe na raiz do Zope", sagl_id)
            return
        
        # SAGL doesn't exist in root, but we're being called from within a SAGL site
        # This means we should not try to create it here, as it would cause recursion
        logger.info("SAGL '%s' não encontrado na raiz, mas import step foi chamado de dentro de um site SAGL", sagl_id)
        logger.info("A criação do SAGL na raiz deve ser feita durante o buildout ou manualmente")
        
    except Exception as e:
        logger.warning("Erro ao verificar SAGL na raiz: %s", str(e))
        import traceback
        logger.debug(traceback.format_exc())
