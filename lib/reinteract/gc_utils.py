# Copyright 2007 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gc

import glib

_gc_idle = None

def gc_idle_flush():
    """Flush any garbage collections schedule with gc_at_idle()"""

    global _gc_idle

    if _gc_idle is not None:
        glib.source_remove(_gc_idle)
        gc.collect()
        _gc_idle = None

def gc_at_idle():
    """Schedule a full garbage collection to happen the next time the main loop is idle

    The advantage of doing this over calling gc.collect() is that during destruction
    of an object references to it may still exist higher up in the stack frame; by
    waiting for idle we make sure all garbage we want to collect is actually
    no longer referenced.

    """

    global _gc_idle

    if _gc_idle is None:
        _gc_idle = glib.idle_add(gc_idle_flush)
