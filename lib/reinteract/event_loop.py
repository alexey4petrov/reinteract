########################################################################
#
# Copyright 2011 Alexey Petrov
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################


#--------------------------------------------------------------------------------------
class _GLibEventLoop(object) :
    #--------------------------------------------------------------------------------------
    def __init__( self ) :
        import glib
        self._loop = glib.MainLoop()
        self._source_tag = None
        pass

    #--------------------------------------------------------------------------------------
    def run( self ) :
        self._loop.run()
        pass

    #--------------------------------------------------------------------------------------
    def quit( self ) :
        self._loop.quit()
        pass

    #--------------------------------------------------------------------------------------
    def cache_event( self, functor ) :
        import glib
        if self._source_tag != None :
            glib.source_remove( self._source_tag )
            pass

        self._source_tag = glib.idle_add( functor )
        pass

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
def eventLoop() :
    # If we create more than one glib.MainLoop, we trigger a pygobject
    # bug - https://bugzilla.gnome.org/show_bug.cgi?id=663068 - so create
    # just one and use it for all the test runs.
    if not hasattr( eventLoop, '_engine' ) :
        eventLoop._engine = _GLibEventLoop()
        pass

    return eventLoop._engine


#--------------------------------------------------------------------------------------
