#!/usr/bin/env python

########################################################################
#
# Copyright 2008 Owen Taylor
# Copyright 2008 Kai Willadsen
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################


#--------------------------------------------------------------------------------------
def test_recorded_object_0():
    #--------------------------------------------------------------------------------------
    from test_utils import adjust_environment, assert_equals
    adjust_environment()

    from reinteract.recorded_object import RecordedObject

    #--------------------------------------------------------------------------------------
    class TestTarget:
        def __init__():
            pass

        def exactargs(self, a, b):
            pass

        def defaultargs(self, a, b=1):
            pass

        def varargs(self, *args):
            pass

        def kwargs(self, **kwargs):
            pass

        pass

    class TestRecorded(RecordedObject):
        pass

    TestRecorded._set_target_class(TestTarget)
    o = TestRecorded()

    # Tests of our argument checking

    def expect_ok(method, *args, **kwargs):
        o.__class__.__dict__[method](o, *args, **kwargs)

    def expect_fail(method, msg, *args, **kwargs):
        try:
            o.__class__.__dict__[method](o, *args, **kwargs)
            raise AssertionError("Expected failure with '%s', got success" % (msg,))
        except TypeError, e:
            if str(e) != msg:
                raise AssertionError("Expected failure with '%s', got '%s'" % (msg, str(e)))

    expect_ok('exactargs', 1, 2)
    expect_ok('exactargs', 1, b=2)
    expect_fail('exactargs', "exactargs() takes exactly 3 arguments (2 given)",
                1)
    expect_fail('exactargs', "exactargs() got an unexpected keyword argument 'c'",
                1, 2, c=3)
    expect_fail('exactargs', "exactargs() got multiple values for keyword argument 'a'",
                1, a=1)

    expect_ok('defaultargs', 1, 2)
    expect_ok('defaultargs', 1)
    expect_ok('defaultargs', a=1, b=2)
    expect_fail('defaultargs', "defaultargs() takes at least 2 arguments (1 given)",
                )
    expect_fail('defaultargs', "defaultargs() takes at least 2 non-keyword arguments (1 given)",
                b=1)
    expect_fail('defaultargs', "defaultargs() takes at most 3 arguments (4 given)",
                1, 2, 3)
    expect_fail('defaultargs', "defaultargs() got an unexpected keyword argument 'c'",
                1, 2, c=3)
    expect_fail('defaultargs', "defaultargs() got multiple values for keyword argument 'a'",
                1, a=1)

    expect_ok('varargs', 1)
    expect_fail('varargs', "varargs() got an unexpected keyword argument 'a'",
                1, a=1)

    expect_ok('kwargs', a=1)
    expect_fail('kwargs', "kwargs() takes exactly 1 argument (2 given)",
                1)

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_recorded_object_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
