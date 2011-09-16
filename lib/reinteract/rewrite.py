# Copyright 2007-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import __future__
import ast
import re
import token
import symbol
import sys

TEXT_TRANSFORMS = (
    (re.compile(r'^(\s*)build((?:\s+as\s+[a-zA-Z_][a-zA-Z_0-9]*\s*)?):', re.MULTILINE),
     r'\1with __reinteract_builder()\2:'),
    (re.compile(r'^(\s*)build\s+([^\r\n]*?)((?:\s+as\s+[a-zA-Z_][a-zA-Z_0-9]*\s*)?):', re.MULTILINE),
     r'\1with __reinteract_builder(\2)\3:'),
)

class UnsupportedSyntaxError(Exception):
    """Exception thrown when some type of Python code that we can't support was used"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# Method names that are considered not to be getters. The Python
# standard library contains methods called isfoo() and getfoo()
# (though not hasfoo()) so we don't for a word boundary. It could
# be tightened if false positives becomes a problem.
_GETTER_RE = re.compile("get|is|has")

# This visitor class does the main work of rewriting - it walks over
# the tree, inserts print and output functions, and collects imports
# and mutated objects.
class _Transformer(ast.NodeTransformer):
    def __init__(self, output_func_name=None, print_func_name=None, copy_func_name=None, future_features=None):
        self.build_variable_count = 0
        self.imports = None
        self.mutated = None
        self.output_func_name = output_func_name
        self.print_func_name = print_func_name
        self.copy_func_name = copy_func_name
        self.future_features = future_features

    def add_mutated(self, node):
        if self.mutated is None:
            self.mutated = _MutationCollector(self.copy_func_name)
        self.mutated.process(node)

    def handle_assign_targets(self, targets):
        for target in targets:
            if isinstance(target, ast.Subscript):
                self.add_mutated(target.value)
            elif isinstance(target, ast.Attribute):
                self.add_mutated(target.value)
            elif isinstance(target, ast.List) or isinstance(target, ast.Tuple):
                self.handle_assign_targets(target.elts)

    def visit_Assign(self, node):
        self.handle_assign_targets(node.targets)

        return self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.add_mutated(node.target)

        return self.generic_visit(node)

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute):
                if _GETTER_RE.match(func.attr) is None:
                    self.add_mutated(func.value)

        if self.output_func_name is not None:
            output_value = self.visit(node.value)

            call = node.value = ast.Call()
            call.func = ast.Name()
            call.func.id = self.output_func_name
            call.func.ctx = ast.Load()

            # FIXME: we did this before, but maybe by accident? Isn't
            # it just best to pass a single value to the output value
            # always?
            if isinstance(output_value, ast.Tuple):
                call.args = output_value.elts
            else:
                call.args = [output_value]

            call.keywords = []

            return node
        else:
            return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if (len(node.body) > 0 and
            isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Str)):

            old_body = node.body

            node.body = [node.body[0]]
            for i in xrange(1, len(node.body)):
                node.body.append(self.visit(node.body[i]))
        else:
            node.body = [self.visit(n) for n in node.body]

        node.decorator_list = [self.visit(n) for n in node.decorator_list]

        return node

    def visit_Global(self, node):
        raise UnsupportedSyntaxError("The global statement is not supported")

    def visit_Print(self, node):
        if self.print_func_name != None and node.dest is None:
            result = ast.Expr()
            ast.copy_location(result, node)

            result.value = ast.Call()
            result.value.func = ast.Name()
            result.value.func.id = self.print_func_name
            result.value.func.ctx = ast.Load()
            result.value.args = [self.visit(n) for n in node.values]
            result.value.keywords = []
            # We could pass node.nl into the function, as a keyword argument,
            # but we'd have to figure out what the actual effect is of that.

            return result
        else:
            return self.generic_visit(node)

    def visit_With(self, node):
        if (isinstance(node.context_expr, ast.Call) and
            isinstance(node.context_expr.func, ast.Name) and
            node.context_expr.func.id == '__reinteract_builder'):

            if node.optional_vars:
                var = node.optional_vars.id
                optional_vars = node.optional_vars
            else:
                var = '__reinteract_build' + str(self.build_variable_count)
                optional_vars = ast.Name()
                optional_vars.id = var
                optional_vars.ctx = ast.Store()
                self.build_variable_count += 1

            output_stmt = ast.Expr()
            output_stmt.value = ast.Name()
            output_stmt.value.id = var
            output_stmt.value.ctx = ast.Load()

            node.optional_vars = optional_vars
            node.body = [self.visit(n) for n in node.body]
            node.body.append(self.visit(output_stmt))

            return node
        else:
            return self.generic_visit(node)

    def add_import(self, imp):
        if self.imports is None:
            self.imports = Imports()

        self.imports._add_import(imp)

    def visit_Import(self, node):
        self.add_import(node)

        return self.generic_visit(node)

    def visit_ImportFrom(self, node):
        # We might want to consider making relative imports mean "from libraries
        # in this reinteract module", but that requires work elsewhere - currently
        # if we passed relative imports here, the execution would give:
        # 'Attempted relative import in non-package'
        #
        # See https://bugzilla.gnome.org/show_bug.cgi?id=659328
        #
        if node.level > 0:
            raise UnsupportedSyntaxError("Relative imports are not supported")

        self.add_import(node)

        return self.generic_visit(node)

######################################################################
# Import procesing

class Imports:
    def __init__(self):
        self.imports = []

    def _add_import(self, imp):
        self.imports.append(imp)

    def get_future_features(self):
        result = set()

        for imp in self.imports:
            if isinstance(imp, ast.ImportFrom) and imp.module == '__future__':
                for alias in imp.names:
                    result.add(alias.name)

        return result

    def module_is_referenced(self, module_name):
        prefix = module_name + "."

        for imp in self.imports:
            if isinstance(imp, ast.ImportFrom):
                if imp.module == module_name or imp.module.startswith(prefix):
                    return True
            elif isinstance(imp, ast.Import):
                for alias in imp.names:
                    if alias.name == module_name or alias.name.startswith(prefix):
                        return True

        return False

######################################################################
# Mutation handling
#
# When _Transformer is walking over the tree, it indentifies candidates
# for mutated objects - in '<X>.append(1)' or '<X>[1] = 2' <X> is
# identified as a possible mutated object. These are objects we need to
# make a backup copy of before executing the code. Mutated objects
# are passed to this code, where we do a number of things:
#
#  * Create a "description" - a human readable string - for the mutated object.
#  * Identify parent objects that also need to be copied - if we assign
#    to a.b.c, then we need to copy a.b, but before we copy a.b, we need
#    to copy a.
#  * Create and compile code snippets to do the cop where possible -
#    in some cases, like get_an_object().a = 3, it doesn't make sense to say
#    get_an_object() = copy(get_an_object()).
#  * Discard certain classes of mutated object that we can't handle, and might
#    not be mutations - e.g. "abcd".length() isn't a mutation, though we
#    consider a.length() to be one.

def _node_with_context(node, ctx):
    if isinstance(node, ast.Attribute):
        result = ast.Attribute()
        result.value = node.value
        result.attr = node.attr
    elif isinstance(node, ast.Name):
        result = ast.Name()
        result.id = node.id
        result.ctx = ctx
    elif isinstance(node, ast.Subscript):
        result = ast.Subscript()
        result.value = node.value
        result.slice = node.slice
    result.ctx = ctx
    return result

# This NodeVisitor subclass is a little unusual in a couple of ways;;
#
# * It's only designed to walk expressions, not other constructs
# * It walks expressions linearly - visit() walks at most one of
#   the children of the node. We work from the end of an of an
#   expression like a.b[1].c to the root.
# * The return value from visit() (which we override) is just the description,
#   but where we have node specific visit functions, those return a tuple of
#   the description, and whether we're going to succeed in making copying
#   a backup copy; the overridden visit() function strips the second part out.
#
class _MutationCollector(ast.NodeVisitor):
    def __init__(self, copy_func_name):
        self.copy_func_name = copy_func_name
        self.mutated = []
        self.seen_mutations = set()
        self.root = None
        self.adding_mutations = True

    def process(self, node):
        self.adding_mutations = True
        self.root = None
        description = self.visit(node)

        if not self.adding_mutations:
            self._add_mutation(description, node, False)

    def _add_mutation(self, description, node, compile_it):
        # Make sure our "mutation" isn't something like "asdfa".length()
        if self.root is None:
            return

        key = ast.dump(node, annotate_fields=False)
        if not key in self.seen_mutations:
            self.seen_mutations.add(key)
            code = self._compile_copy_func(node) if compile_it else None
            self.mutated.append((self.root, description, code))

    def _compile_copy_func(self, node):
        module = ast.Module()
        ast.copy_location(module, node)

        assign = ast.Assign()
        module.body = [assign]

        target = _node_with_context(node, ast.Store())
        assign.targets = [target]

        assign.value = call = ast.Call()
        name = call.func = ast.Name()
        name.id = self.copy_func_name
        name.ctx = ast.Load()

        source = _node_with_context(node, ast.Load())
        source.ctx = ast.Load()
        call.args = [source]
        call.keywords = []

        ast.fix_missing_locations(module)
        return compile(module, '<copy>', 'exec')

    def visit(self, node):
        result = ast.NodeVisitor.visit(self, node)
        if result is None:
            result = '(...)', False

        description, can_copy = result
        if not can_copy:
            self.adding_mutations = False

        if self.adding_mutations:
            self._add_mutation(description, node, True)

        return description

    def generic_visit(self):
        assert False # Not reached

    def visit_Attribute(self, node):
        return self.visit(node.value) + "." + node.attr, True

    def visit_Call(self, node):
        self.adding_mutations = False
        return self.visit(node.func) + "(...)", False

    def visit_Dict(self, node):
        return '{...}', False

    def visit_DictComp(self, node):
        return '{...}', False

    def visit_ListComp(self, node):
        return '[...]', False

    def visit_List(self, node):
        return '[...]', False

    def visit_Name(self, node):
        self.root = node.id
        return node.id, True

    def visit_Num(self, node):
        return repr(node.n), False

    def visit_Repr(self, node):
        return '`...`', False

    def visit_Subscript(self, node):
        return self.visit(node.value) + "[...]", True

    def visit_Str(self, node):
        return '"..."', False

######################################################################

class Rewriter:
    """Class to rewrite and extract information from Python code"""

    def __init__(self, code, encoding="utf8", future_features=None):
        """Initialize the Rewriter object

        @param code: the text to compile
        @param encoding: the encoding of the text
        @param future_features: a list of names from the __future__ module

        """
        # The other thing we could do is prepend '# coding=<encoding name>\n'
        # to the string. In any case, we expect input to normally be unicode.
        if not isinstance(code, unicode):
            code = code.decode(encoding)

        self.code = code
        self.future_features = future_features

        new = code
        for pattern, replacement in TEXT_TRANSFORMS:
            new = pattern.sub(replacement, new)

        self.nodes = ast.parse(new)

    def get_imports(self):
        """
        Return information about any imports made by the statement. Must be
        called after rewrite_and_compile().

        @returns: a rewriter.Imports object, or None.

        """

        return self.imports

    def rewrite_and_compile(self, output_func_name=None, print_func_name=None, copy_func_name="__copy"):
        """
        Compiles the parse tree into code, while rewriting the parse tree according to the
        output_func_name and print_func_name arguments.

        At the same time, the code is scanned for possible mutations, and a list is returned.
        Each item in the list is a tuple of:

         - The name of the variable at the root of the path to the object
           (e.g., for a.b.c, "a")

         - A string describing what should be copied. The string may include ellipses (...)
           for complex areas - it's meant as a human description

         - Code that can be evaluated to copy the object.

        @param output_func_name: the name of function used to wrap statements that are simply expressions.
           (More than one argument will be passed if the statement is in the form of a list.)
           Can be None.

        @param print_func_name: the name of a function used to replace print statements without a destination
          file. Can be None.

        @param copy_func_name: the name of a function used to make shallow copies of objects.
           Should have the same semantics as copy.copy (will normally be an import of copy.copy)
           Defaults to __copy.

        @returns: a tuple of the compiled code followed by a list of mutations
        """
        transformer = _Transformer(output_func_name=output_func_name,
                                   print_func_name=print_func_name,
                                   copy_func_name=copy_func_name,
                                   future_features=self.future_features)

        rewritten = transformer.visit(self.nodes)
        ast.fix_missing_locations(rewritten)

        self.imports = transformer.imports

        compile_flags = 0
        if self.future_features:
            for feature in self.future_features:
                compile_flags |= getattr(__future__, feature).compiler_flag

        compiled = compile(rewritten, '<statement>', 'exec', flags=compile_flags)
        mutated = transformer.mutated.mutated if transformer.mutated else ()

        return (compiled, mutated)

##################################################

if __name__ == '__main__':
    import copy
    import re
    from dump_ast import dump_ast
    from test_utils import assert_equals

    def rewrite_and_compile(code, output_func_name=None, future_features=None, print_func_name=None, encoding="utf8"):
        return Rewriter(code, encoding, future_features).rewrite_and_compile(output_func_name, print_func_name)

    #
    # Test that our intercepting of bare expressions to save the output works
    #
    def test_output(code, expected):
        compiled, _ = rewrite_and_compile(code, output_func_name='reinteract_output')
        
        test_args = []
        def set_test_args(*args): test_args[:] = args

        class Builder:
            def __init__(self, arg=None):
                self.arg = arg

            def __enter__(self):
                return self.arg

            def __exit__(self, exception_type, exception_value, traceback):
                pass

        scope = { 'reinteract_output': set_test_args, '__reinteract_builder': Builder }

        exec compiled in scope

        if tuple(test_args) != tuple(expected):
            raise AssertionError("Got '%s', expected '%s'" % (test_args, expected))

    test_output('a=3', ())
    test_output('1', (1,))
    test_output('1,2', (1,2))
    test_output('1;2', (2,))
    test_output('a=3; a', (3,))
    test_output('def x():\n    1\ny = x()', (1,))

    #
    # Test that we don't intercept docstrings, even though they look like bare expressions
    #
    test_output('def x():\n    "x"\n    return 1\ny = x()', ())
    test_output('def x():\n    """"x\n"""\n    return 1\ny = x()', ())
    test_output('def x(): "x"\ny = x()', ())

    #
    # Test our build "keyword"
    #
    test_output('build list() as l:\n    l.append(1)', ([1],))
    test_output('build list():\n    pass', ([],))
    test_output('build as l:\n    l = 42', (42,))
    test_output('build:\n    pass', (None,))

    #
    # Test that our intercepting of print works
    #
    def test_print(code, expected):
        compiled, _ = rewrite_and_compile(code, print_func_name='reinteract_print')
        
        test_args = []
        def set_test_args(*args): test_args[:] = args
        scope = { 'reinteract_print': set_test_args }

        exec compiled in scope

        if tuple(test_args) != tuple(expected):
            raise AssertionError("Got '%s', expected '%s'" % (test_args, expected))

    test_print('a=3', ())
    test_print('print 1', (1,))
    test_print('print 1,2', (1,2))
    test_print('print "",', ("",))
    test_print('for i in [0]: print i', (0,))
    test_print('import sys; print >>sys.stderr, "",', ())

    #
    # Test catching possible mutations of variables
    #
    def test_mutated(code, expected, prepare=None, assert_old=None, assert_new=None):
        compiled, mutated = rewrite_and_compile(code)

        #
        # Basic test - check the root and description for the returned list of mutations
        #
        mutated_root_desc = sorted(((root, description) for (root, description, _) in mutated))

        # Extract the root from a description (just take the first word)
        def expand_root_desc(description):
            m = re.match(r"([a-zA-Z_0-9]+)", description)
            return m.group(1), description

        expected_root_desc = sorted((expand_root_desc(x) for x in expected))

        if tuple(mutated_root_desc) != tuple(expected_root_desc):
            raise AssertionError("Got '%s', expected '%s'" % (mutated, expected))

        # More complex test
        #
        #  a) create old scope, execute 'prepare' in it
        #  b) copy old scope, execute each copy statement
        #  c) execute the code
        #  c) run assertion checks in old and new scope

        if prepare:
            old_scope = { '__copy' : copy.copy }
            exec prepare in old_scope
            new_scope = dict(old_scope)

            for _, _, copy_code in mutated:
                exec copy_code in new_scope

            exec compiled in new_scope

            old_ok = eval(assert_old, old_scope)
            if not old_ok:
                raise AssertionError("Old scope assertion '%s' failed" % assert_old)
            new_ok = eval(assert_new, new_scope)
            if not new_ok:
                raise AssertionError("New scope assertion '%s' failed" % assert_new)

    test_mutated('a[0] = 1', ('a',),
                 'a = [2]', 'a[0] == 2', 'a[0] == 1')
    test_mutated('a[0], b[0] = 1, 2', ('a', 'b'),
                 'a,b = [2],[1]', 'a[0],b[0] == 2,1', 'a[0],b[0] == 1,2')
    test_mutated('a[0], _ = 1', ('a'))
    test_mutated('a[0], b[0] = c[0], d[0] = 1, 2', ('a', 'b', 'c', 'd'))
    test_mutated('a[0][1] = 1', ('a', 'a[...]'),
                 'a = [[0,2],1]', 'a[0][1] == 2', 'a[0][1] == 1')

    # This isn't fully right - in the new scope b should be [1], not []
    test_mutated('a[0].append(1)', ('a', 'a[...]'),
                 'b = []; a = [b]',
                 'b == [] and a == [b]', 'b == [] and a == [[1]]')

    test_mutated('a += 1', ('a',))
    test_mutated('a[0] += 1', ('a', 'a[...]'))

    prepare = """
class A:
    def __init__(self):
        self.b = 1
    def addmul(self, x,y):
        self.b += x * y
    def get_a(self):
        return self.a
    pass
a = A()
a.a = A()
"""

    test_mutated('a.b = 2', ('a',),
                 prepare, 'a.b == 1', 'a.b == 2')
    test_mutated('a.b = 2', ('a',),
                 prepare, 'a.b == 1', 'a.b == 2')
    test_mutated('a.a.b = 2', ('a','a.a'),
                 prepare, 'a.a.b == 1', 'a.a.b == 2')
    test_mutated('a.a.b += 1', ('a','a.a','a.a.b'),
                 prepare, 'a.a.b == 1', 'a.a.b == 2')

    test_mutated('a.addmul(1,2)', ('a',),
                 prepare, 'a.b == 1', 'a.b == 3')
    test_mutated('a.a.addmul(1,2)', ('a', 'a.a'),
                 prepare, 'a.a.b == 1', 'a.a.b == 3')

    # We exempt some methods as being most likely getters.
    test_mutated('a.get_a()', ())
    test_mutated('a.hasA()', ())
    test_mutated('a.isa()', ())

    # These don't actually work properly since we don't know to copy a.a
    # So we just check the descriptions and not the execution
    #
    test_mutated('a.get_a().b = 2', ('a.get_a(...)',))
    test_mutated('a.get_a().a.b = 2', ('a.get_a(...).a',))

    #
    # Test handling of encoding
    #
    def test_encoding(code, expected, encoding=None):
        if encoding is not None:
            compiled, _ = rewrite_and_compile(code, encoding=encoding, output_func_name='reinteract_output')
        else:
            compiled, _ = rewrite_and_compile(code, output_func_name='reinteract_output')
        
        test_args = []
        def set_test_args(*args): test_args[:] = args
        scope = { 'reinteract_output': set_test_args }

        exec compiled in scope

        if test_args[0] != expected:
            raise AssertionError("Got '%s', expected '%s'" % (test_args[0], expected))

    test_encoding(u"u'\u00e4'".encode("utf8"), u'\u00e4')
    test_encoding(u"u'\u00e4'", u'\u00e4')
    test_encoding(u"u'\u00e4'".encode("iso-8859-1"), u'\u00e4', "iso-8859-1")

    #
    # Test import detection
    #

    def get_imports(code):
        rewriter = Rewriter(code)
        rewriter.rewrite_and_compile()
        return rewriter.get_imports()

    def test_imports(code, referenced):
        imports = get_imports(code)
        for module in referenced:
            if not imports.module_is_referenced(module):
                raise AssertionError("'%s': %s should be referenced and isn't",
                                     code, referenced)

    assert_equals(get_imports('a + 1'), None)
    test_imports('import re', ['re'])
    test_imports('import re as r', ['re'])
    test_imports('import re, os as o', ['re', 'os'])

    test_imports('from re import match', ['re'])
    test_imports('from re import match as m', ['re'])
    test_imports('from re import match as m, sub as s', ['re'])
    test_imports('from re import (match as m, sub as s)', ['re'])
    test_imports('from re import *', ['re'])

    assert_equals(get_imports('from __future__ import division').get_future_features(), set(['division']))

    #
    # Test passing in future_features to use in compilation
    #

    scope = {}
    compiled, _ = rewrite_and_compile('a = 1/2', future_features=['with_statement', 'division'])
    exec compiled in scope
    assert scope['a'] == 0.5
