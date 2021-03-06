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
    def __init__(self, value, lineno=None):
        self.value = value
        self.lineno = lineno
    def __str__(self):
        return repr(self.value)

NAME_NONLOCAL=0
NAME_LOCAL=1
NAME_GLOBAL=2

# Code shared between _ScopeBindingVisitor and _Transfomer to handle tracking the
# set of currently active lexical scopes.
class _ScopeMixin(object):
    def __init__(self):
        super(_ScopeMixin, self).__init__()
        self.scopes = []
        self.function_count = 0

    @property
    def scope(self):
        if len(self.scopes) > 0:
            return self.scopes[-1]
        else:
            return None

    @property
    def in_function(self):
        return self.function_count > 0

    def push_scope(self, scope):
        self.scopes.append(scope)
        if not isinstance(scope, ast.ClassDef):
            self.function_count += 1
        if not hasattr(scope, '_bindings'):
            scope._bindings = {}

    def pop_scope(self):
        scope = self.scopes.pop()
        if not isinstance(scope, ast.ClassDef):
            self.function_count -= 1

    def resolve_name(self, name):
        i = len(self.scopes) - 1
        while i >= 0:
            scope = self.scopes[i]
            if name in scope._bindings:
                binding = scope._bindings[name]
                if binding == NAME_GLOBAL:
                    return NAME_GLOBAL
                elif i == len(self.scopes) - 1:
                    return NAME_LOCAL
                else:
                    return NAME_NONLOCAL
            i -= 1

        return NAME_GLOBAL

# This visitor is used to determine bindings of variables inside
# functions according to Python's rules. There is one pecularity that
# we don't handle here. While the Python language reference says: "The
# following are blocks: a module, a function body, and a class
# definition. [...]  If a name binding operation occurs anywhere
# within a code block, all uses of the name within the block are
# treated as references to the current block. This can lead to errors
# when a name is used within a block before it is bound.", the following
# code:
#
# a = 1
# class X:
#     a += 2
#
# isn't an error, and instead results in a == 1 and X.a == 2. We don't
# handle this case, and say that a is purely a local variable inside
# the class definition.  This doesn't cause any practical problems at
# the moment.

class _ScopeBindingVisitor(ast.NodeVisitor, _ScopeMixin):
    def bind_name(self, name, binding):
        if self.scope:
            if not (name in self.scope._bindings and self.scope._bindings[name] == NAME_GLOBAL):
                self.scope._bindings[name] = binding

    def bind_args(self, args):
        self.bind_arg_tuple(args.args)
        if args.vararg is not None:
            self.bind_name(args.vararg, NAME_LOCAL)
        if args.kwarg is not None:
            self.bind_name(args.kwarg, NAME_LOCAL)

    def bind_arg_tuple(self, argt):
        for arg in argt:
            if isinstance(arg, ast.Tuple):
                self.bind_arg_tuple(arg.elts)
            else:
                self.bind_name(arg.id, NAME_LOCAL)

    def visit_ClassDef(self, node):
        self.bind_name(node.name, NAME_LOCAL)
        for expr in node.decorator_list:
            self.visit(expr)
        for expr in node.bases:
            self.visit(expr)
        self.push_scope(node)
        for stmt in node.body:
            self.visit(stmt)
        self.pop_scope()

    def visit_FunctionDef(self, node):
        self.bind_name(node.name, NAME_LOCAL)
        for expr in node.decorator_list:
            self.visit(expr)
        self.push_scope(node)
        self.bind_args(node.args)
        for stmt in node.body:
            self.visit(stmt)
        self.pop_scope()

    def visit_GeneratorExp(self, node):
        self.push_scope(node)
        self.generic_visit(node)
        self.pop_scope()

    def visit_Global(self, node):
        for name in node.names:
            self.bind_name(name, NAME_GLOBAL)

    def visit_Import(self, node):
        for alias in node.names:
            if alias.asname:
                asname = alias.asname
            else:
                asname = alias.name

            self.bind_name(asname, NAME_LOCAL)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == '*':
                # This might overwrite a variable and make an apparent mutation not
                # a mutation, but that's pretty weird, just ignore
                continue

            if alias.asname:
                asname = alias.asname
            else:
                asname = alias.name

            self.bind_name(asname, NAME_LOCAL)

    def visit_Lambda(self, node):
        self.push_scope(node)
        self.bind_args(node.args)
        self.generic_visit(node)
        self.pop_scope()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.bind_name(node.id, NAME_LOCAL)

# Method names that are considered not to be getters. The Python
# standard library contains methods called isfoo() and getfoo()
# (though not hasfoo()) so we don't for a word boundary. It could
# be tightened if false positives becomes a problem.
_GETTER_RE = re.compile("get|is|has")

# This visitor class does the main work of rewriting - it walks over
# the tree, inserts print and output functions, and collects imports
# and mutated objects.
class _Transformer(ast.NodeTransformer, _ScopeMixin):
    def __init__(self, output_func_name=None, print_func_name=None, copy_func_name=None, future_features=None):
        super(_Transformer, self).__init__()

        self.build_variable_count = 0
        self.imports = None
        self.mutated = None
        self.output_func_name = output_func_name
        self.print_func_name = print_func_name
        self.copy_func_name = copy_func_name
        self.future_features = future_features
        self.overwrite_stack = []

    def process(self, node):
        self.push_overwrites()
        result = self.visit(node)
        self.pop_overwrites()

        return result

    # The overwrite stack is used to keep track of global variables that are
    # assigned within the statement before being mutated, and thus don't
    # need our general mutation handler. The canonical case of this is:
    #
    # build Plot() as p:
    #     p.draw_point(x, y)
    #
    # But we also cover things like:
    #
    # try:
    #     p = Plot()
    #     p.draw_point()
    # except ...
    #
    # The reason we have a stack is that in the second case, and a lot of
    # other cases, the overwrite of p is local to the block of statements,
    # and after the block the overwrite isn't guaranteed to have happened,
    # so we need to push_overwrites() for the block, and then pop and discard
    # the overwrites afterwards.

    def push_overwrites(self):
        self.overwrite_stack.append(set())

    def pop_overwrites(self):
        return self.overwrite_stack.pop()

    def was_overwritten(self, name):
        for s in self.overwrite_stack:
            if name in s:
                return True

        return False

    def handle_assign_to_name(self, name, location):
        binding = self.resolve_name(name)
        if binding == NAME_GLOBAL:
            if self.in_function:
                # We forbid assignments of global variables inside functions, though that's
                # only actually bad if the function is used again at a later point.
                raise UnsupportedSyntaxError("Assigning to global variable '%s' inside a function is not supported" % name,
                                             location.lineno)
            else:
                self.overwrite_stack[-1].add(name)

    def add_mutated(self, node):
        if self.mutated is None:
            self.mutated = _MutationCollector(self.copy_func_name)
        self.mutated.process(node, self)

    def handle_assign_target(self, target):
        if isinstance(target, ast.Subscript):
            self.add_mutated(target.value)
        elif isinstance(target, ast.Attribute):
            self.add_mutated(target.value)
        elif isinstance(target, ast.List) or isinstance(target, ast.Tuple):
            for elt in target.elts:
                self.handle_assign_target(elt)
        elif isinstance(target, ast.Name):
            self.handle_assign_to_name(target.id, target)

    def visit_Assign(self, node):
        for target in node.targets:
            self.handle_assign_target(target)

        return self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.add_mutated(node.target)

        return self.generic_visit(node)

    def visit_statements(self, stmts):
        if len(stmts) == 0:
            return stmts

        result = []
        for i in xrange(0, len(stmts)):
            child = self.visit(stmts[i])
            if isinstance(child, ast.AST):
                result.append(child)
            else:
                result.extend(child)

        return result

    def visit_ClassDef(self, node):
        self.handle_assign_to_name(node.name, node)

        node.decorator_list = [self.visit(n) for n in node.decorator_list]
        node.bases = [self.visit(n) for n in node.bases]

        self.push_scope(node)
        node.body = self.visit_statements(node.body)
        self.pop_scope()

        return node

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute):
                if _GETTER_RE.match(func.attr) is None:
                    self.add_mutated(func.value)

        if self.scope is None and self.output_func_name is not None:
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

    def visit_If(self, node):
        # Here we handle the case where a variable is reliably overwritten
        # in both branches of the if, so we merge the results of pop_overwrites()
        # rather than discarding them.

        self.push_overwrites()
        node.body = self.visit_statements(node.body)
        overwrites_if = self.pop_overwrites()

        if len(node.orelse) > 0:
            self.push_overwrites()
            node.orelse = self.visit_statements(node.orelse)
            overwrites_else = self.pop_overwrites()

            for name in overwrites_if:
                if name in overwrites_else:
                    self.overwrite_stack[-1].add(name)

        return node

    def visit_For(self, node):
        node.iter = self.visit(node.iter)

        self.push_overwrites()
        self.handle_assign_target(node.target)
        node.body = self.visit_statements(node.body)
        self.pop_overwrites()

        self.push_overwrites()
        node.orelse = self.visit_statements(node.orelse)
        self.pop_overwrites()

        return node

    def visit_FunctionDef(self, node):
        self.handle_assign_to_name(node.name, node)

        node.decorator_list = [self.visit(n) for n in node.decorator_list]

        self.push_scope(node)
        # We don't need to push_overwrites() here because assignment to global
        # variables isn't allowed within a function definition
        node.body = self.visit_statements(node.body)
        self.pop_scope()

        return node

    def visit_GeneratorExp(self, node):
        self.push_scope(node)
        self.generic_visit(node)
        self.pop_scope()

        return node

    def visit_Lambda(self, node):
        self.push_scope(node)
        self.generic_visit(node)
        self.pop_scope()

        return node

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

    def visit_TryExcept(self, node):
        self.push_overwrites()
        node.body = self.visit_statements(node.body)
        self.pop_overwrites()

        for handler in node.handlers:
            if handler.type is not None:
                handler.type = self.visit(handler.type)

            self.push_overwrites()
            if handler.name is not None:
                self.handle_assign_target(handler.name)
                handler.name = self.visit(handler.name)

            handler.body = self.visit_statements(handler.body)
            self.pop_overwrites()

        self.push_overwrites()
        node.orelse = self.visit_statements(node.orelse)
        self.pop_overwrites()

        return node

    def visit_TryFinally(self, node):
        self.push_overwrites()
        node.body = self.visit_statements(node.body)
        self.pop_overwrites()

        node.finalbody = self.visit_statements(node.finalbody)

        return node

    def visit_While(self, node):
        node.test = self.visit(node.test)

        self.push_overwrites()
        node.body = self.visit_statements(node.body)
        self.pop_overwrites()

        self.push_overwrites()
        node.orelse = self.visit_statements(node.orelse)
        self.pop_overwrites()

        return node

    def visit_With(self, node):
        if (self.scope is None and
            isinstance(node.context_expr, ast.Call) and
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

            node.context_expr = self.visit(node.context_expr)
            node.optional_vars = self.visit(optional_vars)
            self.handle_assign_to_name(node.optional_vars.id, node.optional_vars)

            node.body = self.visit_statements(node.body)

            return node, self.visit(output_stmt)
        else:
            node.context_expr = self.visit(node.context_expr)

            if node.optional_vars is not None:
                node.optional_vars = self.visit(node.optional_vars)
                self.handle_assign_to_name(node.optional_vars.id, node.optional_vars)

            node.body = self.visit_statements(node.body)
            return node

    def add_import(self, imp):
        if self.imports is None:
            self.imports = Imports()

        self.imports._add_import(imp)

    def visit_Import(self, node):
        self.add_import(node)

        for alias in node.names:
            if alias.asname:
                asname = alias.asname
            else:
                asname = alias.name

            self.handle_assign_to_name(asname, node)

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
            raise UnsupportedSyntaxError("Relative imports are not supported", node.lineno)

        self.add_import(node)

        for alias in node.names:
            if alias.name == '*':
                # This might overwrite a variable and make an apparent mutation not
                # a mutation, but that's pretty weird, just ignore
                continue

            if alias.asname:
                asname = alias.asname
            else:
                asname = alias.name

            self.handle_assign_to_name(asname, node)

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

    def process(self, node, transformer):
        self.adding_mutations = True
        self.root = None
        self.transformer = transformer
        description = self.visit(node)
        self.transformer = None

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
        binding = self.transformer.resolve_name(node.id)

        if binding != NAME_GLOBAL:
            # Mutating local variables doesn't require a copy; mutating "non-local" but
            # not global variables indicates something tricky is going on which might
            # or might-not be OK, we allow it for now.
            return

        # If the global variable was reliably overwritten before being mutated,
        # no copy is necessary
        if self.transformer.was_overwritten(node.id):
            return

        # We forbid mutations of global variables inside functions, though that's
        # only actually bad if the function is used again at a later point.
        if self.transformer.in_function:
            raise UnsupportedSyntaxError("Mutating global variable '%s' inside a function is not supported" % node.id,
                                         node.lineno)

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

    def rewrite_and_compile(self, output_func_name=None, print_func_name=None, copy_func_name="__copy", statement_name="<statement>"):
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

        @param statement_name: the __name of the Statment being compiled.
            Defaults to "<statement>".

        @returns: a tuple of the compiled code followed by a list of mutations
        """

        _ScopeBindingVisitor().visit(self.nodes)

        transformer = _Transformer(output_func_name=output_func_name,
                                   print_func_name=print_func_name,
                                   copy_func_name=copy_func_name,
                                   future_features=self.future_features)

        rewritten = transformer.process(self.nodes)
        ast.fix_missing_locations(rewritten)

        self.imports = transformer.imports

        compile_flags = 0
        if self.future_features:
            for feature in self.future_features:
                compile_flags |= getattr(__future__, feature).compiler_flag

        compiled = compile(rewritten, statement_name, 'exec', flags=compile_flags)
        mutated = transformer.mutated.mutated if transformer.mutated else ()

        return (compiled, mutated)

##################################################
