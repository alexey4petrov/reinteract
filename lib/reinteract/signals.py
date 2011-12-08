#!/usr/bin/env python

"""
File:    signals.py
Author:  Patrick Chasco
Created: July 26, 2005

Purpose: A signals implementation
"""

#--------------------------------------------------------------------------------------
import weakref
import threading
import inspect


#--------------------------------------------------------------------------------------
class _WeakMethod_FuncHost:
    def __init__(self, func):
        self.hostedFunction = func
    def func(self, *args, **kwargs):
        self.hostedFunction(*args, **kwargs)


#--------------------------------------------------------------------------------------
# This class was generously donated by a poster on ASPN (aspn.activestate.com)
class WeakMethod:
	def __init__(self, f):
            self.f = f.im_func
            self.c = weakref.ref(f.im_self)
	def __call__(self, *args, **kwargs):
            if self.c() == None : return
            self.f(self.c(), *args, **kwargs)


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
    def __init__( self, threadsafe = True ):
        self.slots = []
        pass

    #--------------------------------------------------------------------------------------
    def __call__(self, *args, **kwargs):
        for i in range(len(self.slots)):
            slot = self.slots[i]
            if slot != None:
                slot(*args, **kwargs)
            else:
                del self.slots[i]
                pass
            pass
        pass

    #--------------------------------------------------------------------------------------
    def connect(self, slot):
        self.disconnect(slot)
        if inspect.ismethod(slot):
            self.slots.append(WeakMethod(slot))
        else:
            self.slots.append(slot)
            pass
        pass

    #--------------------------------------------------------------------------------------
    def disconnect(self, slot):
        try:
            for i in range(len(self.slots)):
                wm = self.slots[i]
                if inspect.ismethod(slot):
                    if wm.f == slot.im_func and wm.c() == slot.im_self:
                        del self.slots[i]
                        return
                    pass
                else:
                    if wm == slot:
                        del self.slots[i]
                        return
                    pass
                pass
            pass
        except:
            pass
        pass

    #--------------------------------------------------------------------------------------
    def disconnectAll(self):
        del self.slots[ : ]
        pass

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
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
