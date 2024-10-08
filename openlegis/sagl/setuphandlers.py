"""
SAGL setup handlers.
"""

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
            portal.manage_importObject(o)


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
