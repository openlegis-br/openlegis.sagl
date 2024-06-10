###############################################################################
#
# Copyright (c) 2005 by Interlegis
#
# GNU General Public Licence (GPL)
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA  02111-1307  USA
#
###############################################################################

from openlegis.sagl import Portal
from openlegis.sagl.lexml import SAGLOAIServer

from openlegis.sagl.config import PROJECTNAME

from AccessControl import ModuleSecurityInfo
from Products.PythonScripts.Utility import allow_module

from Products.CMFCore.utils import ToolInit

from openlegis.sagl import SAGLTool

def initialize(context):
    # inicializa a instalacao e estrutura do SAGL-OpenLegis

    ModuleSecurityInfo('socket.socket').declarePublic('fileno')
    ModuleSecurityInfo('tempfile.NamedTemporaryFile').declarePublic('flush')

    allow_module('zlib')
    allow_module('sys')
    allow_module('os')
    allow_module('restpki_client')
    allow_module('Acquisition')
    allow_module('ExtensionClass')
    allow_module('App.FindHomes')
    allow_module('trml2pdf')
    allow_module('html2rml')
    allow_module('time')
    allow_module('_strptime')
    allow_module('csv')
    allow_module('pdb')
    allow_module('json')
    allow_module('tempfile.NamedTemporaryFile')
    allow_module('collections')
    allow_module('base64')
    allow_module('socket')
    allow_module('fcntl')
    allow_module('struct')
    allow_module('array')
    allow_module('datetime')
    allow_module('datetime.datetime.timetuple')
    allow_module('pypdf')
    allow_module('pymupdf')
    allow_module('io')
    allow_module('io.BytesIO')
    allow_module('PIL')
    allow_module('uuid')
    allow_module('binascii')
    allow_module('re')
    allow_module('collections')
    allow_module('xml')
    allow_module('xml.sax')
    allow_module('xml.sax.saxutils')
    allow_module('email.mime.text')
    allow_module('AccessControl.PermissionRole')
    allow_module('collections.Counter')
    allow_module('reportlab')
    allow_module('reportlab.lib')
    allow_module('reportlab.lib.utils')

    tools = (SAGLTool.SAGLTool,)
    ToolInit('SAGL Tool',
                tools = tools,
                icon = 'tool.gif'
                ).initialize( context )

    context.registerClass( Portal.SAGL,
                           constructors=( Portal.manage_addSAGLForm,
                                          Portal.manage_addSAGL,),
                           icon='openlegisIcon.gif')

    context.registerClass( lexml.SAGLOAIServer.SAGLOAIServer,
                           constructors = ( SAGLOAIServer.manage_addSAGLOAIServerForm,
                                            SAGLOAIServer.manage_addSAGLOAIServer, ),
                            icon='oai_service.png')

