# -*- coding: utf-8 -*-
from zope.interface import Interface

class IFileSAGL(Interface):
    """ interface para ser implementada no tipo file do zope
    """

class ILogradouroTableViewExporter(Interface):
    """Interface for Logradouro table view exporters."""

    def render(data, columns, request):
        """Renders the exported data."""

    def get_data_query(request):
        """Builds and returns the data query for export."""
