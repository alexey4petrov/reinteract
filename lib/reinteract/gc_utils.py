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

def dump_live_gobjects():
    """Print a summary of live GObjects

    Prints out a list of all GObjects that are currently known about
    to the Python garbage collectors (the ones that have Python
    reference to them), with a description of what other objects
    reference them. The description is shown as a tree, where objects
    that appeared previously are shown abbreviated without children.

    This should be called after cleaning up known global references
    to objects and calling gc_idle_flush().

    """

    import gobject
    from reinteract.global_settings import global_settings

    # Keep track of objects (like variables we create in this
    # function), that we don't want to dump out. We index by
    # id(obj) since we are interested in object identity, and not
    # about the object's contents
    ignored_objects = dict()
    def add_to_ignored(obj):
        ignored_objects[id(obj)] = obj

    # Keep track of objects that we have seen before, with
    # the short description that we used earlier; the short
    # description has an identitying number.
    printed_count = [0]
    printed_objects = dict()
    def add_to_printed(obj, short_desc):
        printed_count[0] += 1
        new_short = str(printed_count[0]) + ' ' + short_desc
        printed_objects[id(obj)] = new_short
        return new_short

    # When we print out a dictinary, we want to show what
    # key in the dictionary referred to the object that
    # was referred to.
    def get_dict_suffix(o, parent):
        if parent is not None and isinstance(o, dict):
            for k in o:
                if o[k] == parent:
                    return '[' + repr(k) + ']'

        return ''

    # Abbreviated description of an object; also returns
    # whether we want to descend into the object and
    # print _it's_ referrers.
    def get_short_desc(o, referrers):
        if isinstance(o, dict):
            for r in referrers:
                if hasattr(r, '__dict__') and o is r.__dict__:
                    if type(r) == type(gc):
                        return r.__name__ + ".__dict__", False
                    else:
                        return type(r).__name__ + ".__dict__", True

        if isinstance(o, list) or isinstance(o, dict):
            return type(o).__name__, True
        else:
            return str(o), True

    def dump_object(o, indent, parent=None):
        add_to_ignored(locals())
        dict_suffix = get_dict_suffix(o, parent)

        if id(o) in printed_objects:
            print indent, printed_objects[id(o)] + dict_suffix
            return

        referrers = gc.get_referrers(o)
        add_to_ignored(referrers)

        short_desc, descend = get_short_desc(o, referrers)
        new_short = add_to_printed(o, short_desc)

        print indent, new_short + dict_suffix

        # 60 here is arbitrary - just a safety check in case we
        # get an infinite loop in some unexpected way
        if not descend or len(indent) > 60:
            return

        for r in referrers:
            if id(r) in ignored_objects or  "'frame'" in str(type(r)):
                continue

            dump_object(r, indent + "   ", o)

    add_to_ignored(locals())
    add_to_ignored(ignored_objects)
    add_to_ignored(printed_objects)

    objs = gc.get_objects()
    add_to_ignored(objs)

    found_live = False

    objs = gc.get_objects()
    add_to_ignored(objs)
    for o in objs:
        # global_settings is in a global variable, so we expect it to "leak"
        if isinstance(o, gobject.GObject) and o is not global_settings:
            if not found_live:
                print "Live GObjects found at shutdown:"
                found_live = True
            dump_object(o, "   ")
