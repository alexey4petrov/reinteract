#!/usr/bin/env python

########################################################################
#
# Copyright 2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

# This file handles routines for Unicode manipulation. In particular, it's concern
# for the limitations of the various parties. Valid Unicode characters are the
# range U+0001-U+10ffff, excluding the ranges U+fdd0-U+fdef and U+fffe-U+ffff
# and all characters whose low 16-bits are in the range U+d800-U+dfff.
#
# Python-in UCS-4 mode:
#  Unicode strings can contain any codepoint U+0000-U+10ffff, whether valid
#  or not.
#
# Python-in UCS-2 mode:
#  Unicode strings can contain any codepoint U+0000-0+ffff. When converting from
#  other encodings or from escapes, non-BMP codepoints are converted into surrogate
#  pairs. Unpaired surrogates can also occur.
#
# GTK+:
#  Unicode strings are represented in UTF-8. They must contain only valid characters,
#  and have no embedded NULs.
#
# Trying to handle non-BMP characters with GTK+ and Python in UCS-2 mode is
# pretty hopeless because something like GtkTextView has no ability to index by
# UTF-8 codepoint index, but only by byte index or character offset.
#
# With UCS-4 Python, handling non-BMP characters is more feasible, but we avoid it
# anyways, a) for cross-platform consistency. b) because writing efficient checks
# for validity beyond the BMP in Python is quite difficult.

#--------------------------------------------------------------------------------------
def test_reunicode_0():
    #--------------------------------------------------------------------------------------
    from test_utils import adjust_environment, assert_equals
    adjust_environment()

    from reinteract.reunicode import decode, escape_unsafe

    #--------------------------------------------------------------------------------------
    def test_escape_unsafe(u, expected):
        assert_equals(escape_unsafe(u), expected)

    # Embedded NUL is \x00
    test_escape_unsafe(u"a\x00b", u"a\\x00b")
    # Test a tab is left untouched
    test_escape_unsafe(u"\t", u"\t")
    # Non-BMP character (represented as surrogates for UCS-2 python)
    test_escape_unsafe(u"\U00010000", u"\\U00010000")
    # Unpaired surrogate
    test_escape_unsafe(u"\ud800", u"\\ud800")

    def test_decode_escaped(s, expected):
        assert_equals(decode(s, escape=True), expected)

    # Valid UTF-8
    test_decode_escaped(u"\u1234".encode("utf8"), u"\u1234")
    # Invalid UTF-8
    test_decode_escaped("abc\x80\x80abc", u"abc\\x80\\x80abc")
    # Mixture
    test_decode_escaped(u"\u1234".encode("utf8") + "\x80", u"\u1234\\x80")
    # embedded NUL
    test_decode_escaped("\x00", "\\x00")

    # Test a non-UTF-8 encoding
    assert_equals(decode("\xc0", encoding="ISO-8859-1"), u"\u00c0")

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_reunicode_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
