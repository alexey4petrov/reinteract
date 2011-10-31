# Copyright 2007-2009 Owen Taylor
# Copyright 2007 Luis Medina
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gtk
import os
import sys

from application import application
from global_settings import global_settings

def _open_url(dialog, url):
    application.show_uri(url)

class AboutDialog(gtk.AboutDialog):
    def __init__(self):
        gtk.about_dialog_set_url_hook(_open_url)

        gtk.AboutDialog.__init__(self)
        self.set_name("Reinteract")
        if global_settings.icon_file.endswith(".icns"):
            # Workaround for limitations of the .icns loader; it can't do
            # the incremental loading needed for from_file_at_size()
            icon = gtk.gdk.pixbuf_new_from_file(global_settings.icon_file)
            icon = icon.scale_simple(64, 64, gtk.gdk.INTERP_BILINEAR)
        else:
            icon = gtk.gdk.pixbuf_new_from_file_at_size(global_settings.icon_file, 64, 64)
        self.set_logo(icon)
        self.set_version(global_settings.version)
        self.set_copyright("Copyright \302\251 2007-2009 Owen Taylor, Red Hat, Inc., and others")
        self.set_website("http://www.reinteract.org")
        self.connect("response", lambda d, r: d.destroy())
