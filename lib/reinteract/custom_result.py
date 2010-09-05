# Copyright 2007 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gtk

class CustomResult(object):
    def create_widget(self):
        raise NotImplementedError()

    def print_result(self, print_context, render):
        """Measure the result for printing or print it. If this isn't overridden, then
        the printing code will fall back to unicode(result). The result should be
        printed starting at a y position of 0 - an appropriate translation will already
        be set on the print context obtained with print_context.get_cairo_context().

        @param print_context: gtk.PrintContext where printing is occurring
        @render: if False, then we're measuring for pagination, and the routine should
          simply return the height. If True, then the routine should print the object
          and also return the height.

        """
        raise NotImplementedError()

def show_menu(widget, event, save_callback=None):
    """Convenience function to create a right-click menu with a Save As option"""

    toplevel = widget.get_toplevel()
        
    menu = gtk.Menu()
    menu.attach_to_widget(widget, None)
    menu_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_SAVE_AS)
    menu_item.show()
    menu.add(menu_item)
        
    def on_selection_done(menu):
        menu.destroy()
    menu.connect('selection-done', on_selection_done)
            
    def on_activate(menu):
        chooser = gtk.FileChooserDialog("Save As...", toplevel, gtk.FILE_CHOOSER_ACTION_SAVE,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                         gtk.STOCK_SAVE,   gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        response = chooser.run()
        filename = None
        if response == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
                        
        chooser.destroy()

        if filename is not None:
            save_callback(filename)
                    
    menu_item.connect('activate', on_activate)
    menu.popup(None, None, None, event.button, event.time)
