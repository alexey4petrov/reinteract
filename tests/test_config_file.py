#!/usr/bin/env python

######################################################################
#
# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################


#--------------------------------------------------------------------------------------
def test_config_file_0():
    #--------------------------------------------------------------------------------------
    from test_utils import adjust_environment, assert_equals
    adjust_environment()

    from reinteract.config_file import _quote_list, _quote, _unquote, _unquote_list
    import tempfile

    def test_quote(s, expected):
        quoted = _quote(s)
        assert_equals(quoted, expected)
        unquoted = _unquote(quoted)
        assert_equals(unquoted, s)

    test_quote(r'',  r'""')
    test_quote(r'foo',  r'foo')
    test_quote(r'fo"o', r'"fo\"o"')
    test_quote(r'fo o', r'"fo o"')
    test_quote(r'fo\o', r'fo\\o')

    def test_quote_list(l, expected):
        quoted = _quote_list(l)
        assert_equals(quoted, expected)
        unquoted = _unquote_list(quoted)
        assert_equals(unquoted, l)

    test_quote_list(['foo'], 'foo')
    test_quote_list(['foo bar'], '"foo bar"')
    test_quote_list(['foo', 'bar'], 'foo bar')
    test_quote_list(['foo', 'bar baz'], 'foo "bar baz"')

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_config_file_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
