# Copyright 2007, 2010 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import re
import pydoc
import gtk

from data_format import insert_with_tag, is_data_object

BOLD_RE = re.compile("(?:(.)\b(.))+")
STRIP_BOLD_RE = re.compile("(.)\b(.)")

def format_docs(obj, callback):
    """Gets the documentation for a given object, and format it simply
      with a distinction between bold and normal

    @param obj: the object to get documentation about
    @param callback: callback called for each segment of text. Passed two
      arguments; the text of the segment and a boolean that is True if the
      text should be formatted in bold

    """
    
    # If the routine is an instance, we get help on the type instead
    if is_data_object(obj):
        obj = type(obj)
        
    name = getattr(obj, '__name__', None)
    document = pydoc.text.document(obj, name)

    # pydoc.text.document represents boldface with overstrikes, we need to
    # reverse engineer this and find the spans of bold text
    pos = 0
    while True:
        m = BOLD_RE.search(document, pos)
        if m is None:
            # Strip the trailing newline; this isn't very justifiable in general terms,
            # but matches what we need in Reinteract
            if document.endswith("\n"):
                callback(document[pos:-1], False)
            else:
                callback(document[pos:], False)
            break

        callback(document[pos:m.start()], False)
        callback(STRIP_BOLD_RE.sub(lambda m: m.group(1), m.group()), True)
        pos = m.end()

def insert_docs(buf, iter, obj, bold_tag):
    """Insert documentation about obj into a gtk.TextBuffer

    @param buf: the buffer to insert the documentation into
    @param iter: the location to insert the documentation
    @param obj: the object to get documentation about
    @param bold_tag: the tag to use for bold text, such as headings

    """

    def callback(text, bold):
        if bold:
            insert_with_tag(buf, iter, text, bold_tag)
        else:
            buf.insert(iter, text)

    format_docs(obj, callback)
