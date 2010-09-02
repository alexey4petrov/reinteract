# Copyright 2010 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gtk
import logging

_debug = logging.getLogger("PrintOperation").debug

class WorksheetPrintOperation(gtk.PrintOperation):
    __gsignals__ = {
        'begin-print' : 'override',
        'draw-page': 'override'
    }

    def __init__(self, worksheet):
        gtk.PrintOperation.__init__(self)

    def do_begin_print(self, context):
        self.set_n_pages(1)

    def do_draw_page(self, context, page_nr):
        pass
