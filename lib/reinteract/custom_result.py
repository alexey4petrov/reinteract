# Copyright 2007 Owen Taylor
# Copyright 2010 Jorn Baayen
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

class ResultWidget(gtk.DrawingArea):
    """Base class for custom result widgets that draw their own content"""

    __gsignals__ = {
    }

    def __init__(self):
        gtk.DrawingArea.__init__(self)

        self.parent_style_set_id = 0
        self.notify_resolution_id = 0

    def do_screen_changed(self, previous_screen):
        if self.notify_resolution_id > 0:
            previous_screen.handler_disconnect(self.notify_resolution_id)
            self.notify_resolution_id = 0

        screen = self.get_screen()
        if screen:
            self.notify_resolution_id = \
                screen.connect("notify::resolution", self._on_notify_resolution)
            self.sync_dpi(screen.get_resolution())

    def do_parent_set(self, previous_parent):
        # We follow the parent GtkTextView text size.
        if self.parent_style_set_id > 0:
            previous_parent.handler_disconnect(self.parent_style_set_id)
            self.parent_style_set_id = 0

        if self.parent:
            self.parent_style_set_id = \
                self.parent.connect("style-set", self._on_parent_style_set)
            self.sync_style(self.parent.style)

    def _on_notify_resolution(self, screen, param_spec):
        self.sync_dpi(screen.get_resolution())

    def _on_parent_style_set(self, widget, previous_style):
        self.sync_style(self.parent.style)

        self.queue_resize()

    def sync_dpi(self, dpi):
        pass

    def sync_style(self, style):
        pass

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
