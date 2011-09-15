#!/usr/bin/env python
#
# Copyright 2011 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

# This file is a utility used in development, it exports the function
# dump_ast(ast, [outputfilename]) and also can be used on the command
# line to dump the ast for an expression.

from cStringIO import StringIO
import parser
import token
import symbol
import sys

def _dump(w, ast, indent):
    w(indent + '(')
    if token.ISTERMINAL(ast[0]):
        w("token." + token.tok_name[ast[0]])
        for i in xrange(1, len(ast)):
            w(", ")
            if  ast[i].find("'") >= 0:
                w('"' + ast[i] + '"')
            else:
                w("'" + ast[i] + "'")
    else:
        w("symbol." + symbol.sym_name[ast[0]] + ",\n")
        for i in xrange(1, len(ast)):
            if i != 1:
                w(",\n")
            if type(ast[i]) == tuple or type(ast[i]) == list:
                _dump(w, ast[i], indent + " ")
            else:
                w(indent + " " + ast[i])
    w(")")

def dump_ast(ast, output_filename=None):
    """Takes an abstract syntax output from the parser module and formats it as
       readable Python code.

    @param output_filename if supplied, the AST is dumped to a file of this name,
       otherwise returned as a string.

    """
    if output_filename:
        output = open(output_filename, "w")
        _dump(output.write, ast, '')
        output.write("\n")
        output.close()
        return None
    else:
        si = StringIO()
        _dump(si.write, ast, '')
        return si.getvalue()

if __name__ == '__main__': # INTERACTIVE
    if len(sys.argv) != 2:
        print >>sys.stderr, "Usage: dump_ast.py '<expr>'"
        sys.exit(1)

    text = sys.argv[1].replace("\\n", "\n")
    ast = parser.suite(text)
    print dump_ast(ast.totuple())
