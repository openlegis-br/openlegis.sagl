/**
 * Copyright (C) 2014 KO GmbH <copyright@kogmbh.com>
 *
 * @licstart
 * This file is part of WebODF.
 *
 * WebODF is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Affero General Public License (GNU AGPL)
 * as published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version.
 *
 * WebODF is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with WebODF.  If not, see <http://www.gnu.org/licenses/>.
 * @licend
 *
 * @source: http://www.webodf.org/
 * @source: https://github.com/kogmbh/WebODF/
 */

/*global define, dojo, runtime, webodf */

define("webodf/editor/widgets/aboutDialog", ["dijit/Dialog"], function (Dialog) {
    "use strict";

    var editorBase = dojo.config && dojo.config.paths && dojo.config.paths["webodf/editor"],
        kogmbhImageUrl = editorBase + "/images/openlegis.png";

    runtime.assert(editorBase, "webodf/editor path not defined in dojoConfig");

    return function AboutDialog(callback) {
        var self = this;

        /*jslint emptyblock: true*/
        this.onToolDone = function () {};
        /*jslint emptyblock: false*/

        function init() {
            var dialog;
            // Dialog
            dialog = new Dialog({
                style: "width: 400px",
                title: "OpenLegis.Editor",
                autofocus: false,
                content: "<p>OpenLegis.Editor é um plugin para o Sistema Aberto de Gestão Legislativa " +
                            "que permite a edição online de documentos no formato OpenDocument.</p>" +
                            "Versão "+ webodf.Version +".<p> Desenvolvido por" +
                            "<a href=\"http://www.openlegis.com.br\" target=\"_blank\"><img src=\"" + kogmbhImageUrl + "\" width=\"138\" height=\"52\" alt=\"OpenLegis\" style=\"vertical-align: top;\"></a>.</p>"
            });
            dialog.onHide = function () { self.onToolDone(); };

            callback(dialog);
        }

        init();
    };

});
