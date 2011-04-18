# Copyright 2007-2010 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import pango

import retokenize

class StyleSpec:
    """
    A StyleSpec defines the appearance for some type of object. It's roughly similar
    to gtk.TextTag, but not tied to a particular gtk.TextBuffer.

    """
    def __init__(self,
                 family=None,
                 foreground=None,
                 left_margin=None,
                 paragraph_background=None,
                 right_margin=None,
                 style=None,
                 underline=None,
                 weight=None):
        self.family=family
        self.foreground = foreground
        self.left_margin = left_margin
        self.paragraph_background = paragraph_background
        self.right_margin = right_margin
        self.style = style
        self.underline = underline
        self.weight = weight

    def add_pango_attributes(self, attrs, start_index, end_index):
        """Insert attributes for this StyleSpec into a pango.AttrList. Not every
        property of StyleSpec maps into a pango.Attribute - the ones that don't
        map are ignored and need to be handled separately.

        @param attrs: pango.AttrList to insert attributes into.
        @param start_index: byte offset of the start of the range this spec applies to
        @param end_index: byte offset of the ned of the range this spec applies to

        """

        if self.family is not None:
            attrs.insert(pango.AttrFamily(self.family, start_index, end_index))
        if self.foreground is not None:
            color = pango.Color(self.foreground)
            attrs.insert(pango.AttrForeground(color.red, color.green, color.blue, start_index, end_index))
        if self.style is not None:
            attrs.insert(pango.AttrStyle(self.style, start_index, end_index))
        if self.underline is not None:
            attrs.insert(pango.AttrUnderline(self.underline, start_index, end_index))
        if self.weight is not None:
            attrs.insert(pango.AttrWeight(self.weight, start_index, end_index))
        if self.weight is not None:
            attrs.insert(pango.AttrWeight(self.weight, start_index, end_index))

    def create_tag(self, buf, name):
        """Creates a gtk.TextTag with the attributes appropriate for this StyleSpec.
        You should generally use Style.get_tag() instead of calling this directly.

        @param buf: gtk.TextBuffer to create the tag in
        @param name: name for the tag

        """

        tag =  buf.create_tag(name)
        for k in ('family', 'foreground', 'left_margin', 'paragraph_background',
                  'right_margin', 'style', 'underline', 'weight'):
            v = getattr(self, k)
            if v is not None:
                tag.set_property(k, v)

        return tag

class Style:
    """
    A Style defines the look of a worksheet. It is a mapping from a I{subject}, which can
    either be a token-type constant from L{retokenize} or a string like 'warning' or
    'error', to a StyleSpec. Subjects may share the share the same StyleSpec as another
    subject by being I{aliases} to that subject. Certain subjects can be 'unstyled' -
    and return None from style lookups. This is different from trying to lookup an unrecognized
    subject, which will through an exception. (The distinction is to prevent typos in
    string subjects silently causing lack of styling.)

    """

    def __init__(self, specs):
        self.specs = specs

    def get_spec(self, subject):
        """Looks up a StyleSpec for the given subject. Returns None for unstyled  subjects"""
        while isinstance(self.specs[subject], str):
            subject = self.specs[subject]

        return self.specs[subject]

    def get_tag(self, buf, subject):
        """Looks up or create a gtk.TextTag for the given subject; aliases are
        derefenced before looking up the tag, so all subjects that share a given
        StyleSpec use the same tag. Returns None for unstyled subjects.

        @param buf: gtk.TextBuffer where the tag will be used
        @param subject: subject used to look up the tag.

        """

        while isinstance(self.specs[subject], str):
            subject = self.specs[subject]

        spec = self.specs[subject]
        if spec is None:
            return None

        old_tag = buf.get_tag_table().lookup(str(subject))
        if old_tag:
            return old_tag

        return spec.create_tag(buf, str(subject))

DEFAULT_STYLE = Style({
        'error'                           : StyleSpec(foreground="#aa0000"),
        'warning'                         : StyleSpec(foreground="#aa8800"),
        'comment'                         : StyleSpec(foreground="#3f7f5f"),
        'header'                          : StyleSpec(family="sans-serif"),
        'help'                            : StyleSpec(family="sans-serif",
                                                      left_margin=10,
                                                      right_margin=10,
                                                      paragraph_background="#ffff88",
                                                      style=pango.STYLE_NORMAL),
        'recompute'                       : StyleSpec(foreground="#888888"),
        'result'                          : StyleSpec(family="monospace",
                                                      style="italic"),
        'punctuation'                     : None,
        retokenize.TOKEN_KEYWORD          : StyleSpec(foreground="#7f0055", weight=600),
        retokenize.TOKEN_NAME             : None,
        retokenize.TOKEN_COMMENT          : 'comment',
        retokenize.TOKEN_BUILTIN_CONSTANT : StyleSpec(foreground="#55007f"),
        retokenize.TOKEN_STRING           : StyleSpec(foreground="#00aa00"),
        retokenize.TOKEN_PUNCTUATION      : 'punctuation',
        retokenize.TOKEN_CONTINUATION     : 'punctuation',
        retokenize.TOKEN_LPAREN           : 'punctuation',
        retokenize.TOKEN_RPAREN           : 'punctuation',
        retokenize.TOKEN_LSQB             : 'punctuation',
        retokenize.TOKEN_RSQB             : 'punctuation',
        retokenize.TOKEN_LBRACE           : 'punctuation',
        retokenize.TOKEN_RBRACE           : 'punctuation',
        retokenize.TOKEN_BACKQUOTE        : 'punctuation',
        retokenize.TOKEN_COLON            : 'punctuation',
        retokenize.TOKEN_DOT              : 'punctuation',
        retokenize.TOKEN_AT               : StyleSpec(foreground="#7f0055", weight=600),
        retokenize.TOKEN_EQUAL            : 'punctuation',
        retokenize.TOKEN_AUGEQUAL         : 'punctuation',
        retokenize.TOKEN_NUMBER           : None,
        retokenize.TOKEN_JUNK             : StyleSpec(underline=pango.UNDERLINE_ERROR),
        })
