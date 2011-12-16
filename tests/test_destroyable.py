#!/usr/bin/env python

########################################################################
#
# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################


#--------------------------------------------------------------------------------------
def test_destroyable_0():
    #--------------------------------------------------------------------------------------
    from test_utils import adjust_environment, assert_equals
    adjust_environment()

    from reinteract.destroyable import Destroyable
    import gobject

    #--------------------------------------------------------------------------------------
    class A(Destroyable, gobject.GObject):
        __gsignals__ = {
                'changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }

    def do_a(*args):
        results.append('a')
    def do_b(*args):
        results.append('b')

    a = A()

    a.connect('changed', do_a)
    handler_id = a.connect('changed', do_b)
    a.disconnect(handler_id)

    results = []
    a.emit('changed')
    assert_equals(results, ['a'])

    a.destroy()

    results = []
    a.emit('changed')
    assert_equals(results, [])

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_destroyable_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
