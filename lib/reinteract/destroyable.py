########################################################################
#
# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gobject

class Destroyable(object):
    def connect(self, *args):
        if not hasattr(self, '_Destroyable__connections'):
            self.__connections = set()

        retval = gobject.GObject.connect(self, *args)
        self.__connections.add(retval)

        return retval

    def connect_after(self, *args):
        if not hasattr(self, '_Destroyable__connections'):
            self.__connections = set()

        retval = gobject.GObject.connect_after(self, *args)
        self.__connections.add(retval)

        return retval

    def connect_object(self, *args):
        if not hasattr(self, '_Destroyable__connections'):
            self.__connections = set()

        retval = gobject.GObject.connect_object(self, *args)
        self.__connections.add(retval)

        return retval

    def connect_object_after(self, *args):
        if not hasattr(self, '_Destroyable__connections'):
            self.__connections = set()

        retval = gobject.GObject.connect_object_after(self, *args)
        self.__connections.add(retval)

        return retval

    def disconnect(self, handler_id):
        if hasattr(self, '_Destroyable__connections'):
            self.__connections.remove(handler_id)

        gobject.GObject.disconnect(self, handler_id)

    def disconnect_handler(self, handler_id):
        if hasattr(self, '_Destroyable__connections'):
            self.__connections.remove(handler_id)

        gobject.GObject.disconnect_handler(self, handler_id)

    def do_destroy(self):
        if hasattr(self, '_Destroyable__connections'):
            for handler_id in self.__connections:
                gobject.GObject.disconnect(self, handler_id)
            del self.__connections

        self.__destroyed = True

    def destroy(self):
        if self.__class__.connect != Destroyable.connect:
            raise AssertionError("%s (or parent): Destroyable must preceed gobject.GObject in list of parent types" % type(self).__name__)

        self.do_destroy()
        if not (hasattr(self, '_Destroyable__destroyed') and self.__destroyed):
            raise AssertionError("do_destroy() method on %s (or parent) failed to chain up" % type(self).__name__)


########################################################################
