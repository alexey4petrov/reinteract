#!/usr/bin/env python

#--------------------------------------------------------------------------------------
"""
Licensed under the Python Software Foundation License

File:     signals.py

Author:   Patrick Chasco
Created:  July 26, 2005
Purpose:  A signals implementation

Author:   Alexey Petrov
Modified: January 08, 2011
Purpose:  Support multi-threading and functional objects
          Code implementation advancment
"""

#--------------------------------------------------------------------------------------
class _Lock :
    #--------------------------------------------------------------------------------------
    def __init__( self, the_threadsafe ):
        import threading
        self._engine = threading.Lock() if the_threadsafe == True else None
        pass

    #--------------------------------------------------------------------------------------
    def __enter__( self ) :
        if self._engine != None : 
            self._engine.acquire()
            pass
        pass

    #--------------------------------------------------------------------------------------
    def __exit__( self, exc_type, exc_value, exc_tb ) :
        if self._engine != None : 
            self._engine.release()
            pass

        return False
        
    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
class _WeakMethod :
    #--------------------------------------------------------------------------------------
    def __init__( self, f ) :
        import weakref
        self.c = weakref.ref( f.im_self )

        self.f = f.im_func
        pass

    #--------------------------------------------------------------------------------------
    def __call__( self, *args, **kwargs ) :
        if not self : 
            return

        self.f( self.c(), *args, **kwargs )
        pass

    #--------------------------------------------------------------------------------------
    def __eq__( self, the_weak_method ) :
        return self.f == the_weak_method.im_func and \
            self.c() == the_weak_method.im_self

    #--------------------------------------------------------------------------------------
    def __nonzero__( self ) :
        return self.c() != None
    
    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
class _WeakObject :
    #--------------------------------------------------------------------------------------
    def __init__( self, the_object ) :
        import weakref
        self._engine = weakref.ref( the_object )
        pass

    #--------------------------------------------------------------------------------------
    def __call__( self, *args, **kwargs ) :
        if not self : 
            return

        self._engine()( *args, **kwargs )
        pass

    #--------------------------------------------------------------------------------------
    def __eq__( self, the_other ) :
        return self._engine() == the_other._engine()

    #--------------------------------------------------------------------------------------
    def __nonzero__( self ) :
        return self._engine() != None
    
    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
class Signal( object ) :
    """
    class Signal

    A simple implementation of the Signal/Slot pattern. To use, simply 
    create a Signal instance. The instance may be a member of a class, 
    a global, or a local; it makes no difference what scope it resides 
    within. Connect slots to the signal using the "connect()" method. 
    The slot may be a member of a class or a simple function. If the 
    slot is a member of a class, Signal will automatically detect when
    the method's class instance has been deleted and remove it from 
    its list of connected slots.
    """
    #--------------------------------------------------------------------------------------
    def __init__( self, the_threadsafe = True ) :
        self._lock = _Lock( the_threadsafe )
        self._slots = []
        pass

    #--------------------------------------------------------------------------------------
    def __call__( self, *args, **kwargs ) :
        with self._lock :
            a_slots = []

            for a_slot in self._slots :
                if a_slot :
                    a_slot( *args, **kwargs )
                    a_slots.append( a_slot )
                    pass
                pass

            self._slots = a_slots
            pass
        pass

    #--------------------------------------------------------------------------------------
    def connect( self, the_slot ) :
        self.disconnect( the_slot )

        with self._lock :
            import inspect
            if inspect.isfunction( the_slot ) :
                self._slots.append( the_slot )
            elif inspect.ismethod( the_slot ) :
                self._slots.append( _WeakMethod( the_slot ) )
            else:
                self._slots.append( _WeakObject( the_slot ) )
                pass
            pass
        pass

    #--------------------------------------------------------------------------------------
    def disconnect( self, the_slot ) :
        with self._lock :
            try :
                self._slots.remove( the_slot )
            except :
                pass
            pass
        pass

    #--------------------------------------------------------------------------------------
    def disconnectAll( self ) :
        with self._lock :
            del self._slots[ : ]
            pass
        pass

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
class Append :
    #--------------------------------------------------------------------------------------
    def __init__( self, the_parrent_method ) :
        self._parrent_method = the_parrent_method
        pass
        
    #--------------------------------------------------------------------------------------
    def __call__( self, the_addon_method ) :
        def composite_method( instance, *args, **kwargs ) :
            a_result = self._parrent_method( instance, *args, **kwargs )
            the_addon_method( instance, *args, **kwargs )
            return a_result

        return composite_method

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
