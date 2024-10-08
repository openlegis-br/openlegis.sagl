# -*- coding: utf-8 -*-

import csv

from zope.component.hooks import setSite

from Products.GenericSetup.tool import SetupTool
from Products.CMFDefault.Portal import CMFSite
from Products.CMFCore.utils import getToolByName

from AccessControl import ClassSecurityInfo
from Acquisition import aq_base

from AccessControl.class_init import InitializeClass

_TOOL_ID = 'portal_setup'
_DEFAULT_PROFILE = 'openlegis.sagl:default'


class SAGL(CMFSite):
    """ Inicia um novo SAGL baseado em um CMFSite.
    """
    security=ClassSecurityInfo()
    meta_type = portal_type = 'SAGL'

    def __init__( self, id, title='' ):
        CMFSite.__init__( self, id, title )

    def processCSVFile(self, file, as_dict=0):
        reader = csv.reader(file)
        output_list = []
        if as_dict:
            headerList = next(reader)
            for line in reader:
                if line:
                    dd = {}
                    for i, key in enumerate(headerList):
                        dd[key]=line[i]
                    output_list.append(dd)
        else:
            for row in reader:
                output_list.append(row)
        return output_list


InitializeClass(SAGL)


from Products.PageTemplates.PageTemplateFile import PageTemplateFile

manage_addSAGLForm = PageTemplateFile('www/addSAGL', globals())
manage_addSAGLForm.__name__ = 'addSAGL'


def manage_addSAGL(context, id, title='SAGL', description='',
                   database='MySQL', profile_id=_DEFAULT_PROFILE, RESPONSE=None):
    """ Adicionar uma instancia do SAGL.
    """

    context._setObject(id, SAGL(id))
    site = context._getOb(id)
    setSite(site)

    site._setObject(_TOOL_ID, SetupTool(_TOOL_ID))
    setup_tool = getToolByName(site, _TOOL_ID)

    setup_tool.setBaselineContext('profile-Products.CMFDefault:default')
    setup_tool.runAllImportStepsFromProfile('profile-Products.CMFDefault:default')

    setup_tool.setBaselineContext('profile-%s' % profile_id)
    setup_tool.runAllImportStepsFromProfile('profile-%s' % profile_id)

    props = dict(
        title=title,
        description=description,
    )

    site.manage_changeProperties(**props)

    if database == 'MySQL':
        site.manage_addProduct['ZMySQLDA'].manage_addZMySQLConnection(
            id='dbcon_sagl',
            title='dbcon_sagl (MySQL)',
            use_unicode=True,
            connection_string='*lock_name openlegis sagl sagl',
            charset='utf8mb4'
        )
        site.manage_addProduct['ZMySQLDA'].manage_addZMySQLConnection(
            id='dbcon_logs',
            title='dbcon_logs (MySQL)',
            use_unicode=True,
            connection_string='*lock_name openlegis_logs sagl sagl',
            charset='utf8mb4'
        )
    else:
        site.manage_addProduct['ZPsycopgDA'].manage_addZPsycopgConnection(
            id='dbcon_sagl',
            title='dbcon_sagl (PostgreSQL)',
            connection_string='postgres://postgres:postgres@127.0.0.1:5432/openlegis'
        )

    if not hasattr(site, 'sapl_documentos'):
       path_sagl = site.getId()
       try:
          site.manage_addProduct['ZODBMountPoint'].manage_addMounts(paths=['/%s/sapl_documentos' % path_sagl], create_mount_points=True)
       except:
          pass
    
    if RESPONSE is not None:
        RESPONSE.redirect( '%s/%s/manage_main?update_menu=1'
                           % (context.absolute_url(), id) )
