#!/usr/bin/env python

#--------------------------------------------------------------------------------------
"""
Licensed under the Python Software Foundation License

File:    signals.py
Purpose: A signals implementation

Author:  Patrick Chasco
Created: July 26, 2005

Author:  Alexey Petrov
Modified: January 08, 2011 ( multi-threading support )
"""

#--------------------------------------------------------------------------------------
import inspect
import weakref
import threading


#--------------------------------------------------------------------------------------
class Lock :
    #--------------------------------------------------------------------------------------
    def __init__( self, the_threadsafe ):
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
class WeakMethod :
    #--------------------------------------------------------------------------------------
    def __init__( self, f ) :
        self.f = f.im_func
        self.c = weakref.ref( f.im_self )
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
class Signal:
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
        self._lock = Lock( the_threadsafe )
        self._slots = []
        pass

    #--------------------------------------------------------------------------------------
    def __call__( self, *args, **kwargs ) :
        with self._lock :
            a_slots = self._slots[ : ]

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
            if inspect.ismethod( the_slot ) :
                self._slots.append( WeakMethod( the_slot ) )
            else:
                self._slots.append( the_slot )
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
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    class Button:
        def __init__(self):
            # Creating a signal as a member of a class
            self.sigClick = Signal()

    class Listener:
        # a sample method that will be connected to the signal
        def onClick(self):
            print "onClick ", repr(self)
    
    # a sample function to connect to the signal
    def listenFunction():
        print "listenFunction"
   
    # a function that accepts arguments
    def listenWithArgs(text):
        print "listenWithArgs: ", text

    b = Button()
    l = Listener()
    
    # Demonstrating connecting and calling signals
    print
    print "should see one message"
    b.sigClick.connect(l.onClick)
    b.sigClick()

    # Disconnecting all signals
    print
    print "should see no messages"
    b.sigClick.disconnectAll()
    b.sigClick()

    # connecting multiple functions to a signal
    print
    print "should see two messages"
    l2 = Listener()
    b.sigClick.connect(l.onClick)
    b.sigClick.connect(l2.onClick)
    b.sigClick()
    
    # disconnecting individual functions
    print
    print "should see two messages"
    b.sigClick.disconnect(l.onClick)
    b.sigClick.connect(listenFunction)
    b.sigClick()
    
    # signals disconnecting automatically
    print
    print "should see one message"
    b.sigClick.disconnectAll()
    b.sigClick.connect(l.onClick)
    b.sigClick.connect(l2.onClick)
    del l2    
    b.sigClick()
    
    # example with arguments and a local signal
    print
    print "should see one message"
    sig = Signal()
    sig.connect(listenWithArgs)
    sig("Hello, World!")

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
