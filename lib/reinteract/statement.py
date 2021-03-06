# Copyright 2007-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import copy
import pkgutil
import threading
import traceback
import sys
import re

from custom_result import CustomResult
import notebook
from notebook import HelpResult
from rewrite import Rewriter, UnsupportedSyntaxError
import reunicode
from stdout_capture import StdoutCapture

class WarningResult(object):
    def __init__(self, message):
        self.message = message
    
class Statement:
    """

    Class that wraps a section of Python code for compilation and execution. (The section
    doesn't actually have to be a single statement.)

    """

    NEW = 0
    COMPILE_SUCCESS = 1
    COMPILE_ERROR = 2
    EXECUTING = 3
    EXECUTE_SUCCESS = 4
    EXECUTE_ERROR = 5
    INTERRUPTED = 6

    __local = threading.local()

    __counter = 0

    NAME_PATTERN = re.compile(r'<statement\d+>')

    def __init__(self, text, worksheet, parent=None):
        self.__text = text
        self.__worksheet = worksheet

        #: current state of the statement (one of the constants defined within the class)
        self.state = Statement.NEW

        #: description of the imports of the statement. Set after compilation. See L{Rewriter.get_imports}
        self.imports = None
        #: names imported from __future__. Used when compiling subsequent statements
        self.future_features = None

        #: scope at the end of successful execution
        self.result_scope = None
        #: list of results from the statement. Set after successful execution
        self.results = None

        #: error_message: error message in case of compilation or execution error
        self.error_message = None
        #: line where error occured in case of compilation or execution error
        self.error_line = None
        #: offset within line of a compilation error
        self.error_offset = None

        self.__compiled = None
        self.__parent_future_features = None

        self.set_parent(parent)

        self.__stdout_buffer = None
        self.__capture = None

        self.__name = '<statement%i>' % self.__class__.__counter
        Statement.__counter += 1

    def set_parent(self, parent):
        """Set the parent statement for this statement.

        The parent statement provides context for the compilation and execution
        of a statement. After setting the parent statement the statement will
        need to be reexecuted and may need to be recompiled. (Recompilation is
        needed if the set of features imported from __future__ changes.)

        """
        self.__parent = parent

    def compile(self):
        """Compile the statement.

        @returns: True if the statement was succesfully compiled.

        """

        if self.__parent:
            new_future_features = self.__parent.future_features
        else:
            new_future_features = None

        if new_future_features != self.__parent_future_features:
            self.__parent_future_features = new_future_features
        elif self.state != Statement.NEW:
            return self.state != Statement.COMPILE_ERROR

        self.error_message = None
        self.error_line = None
        self.error_offset = None

        try:
            rewriter = Rewriter(self.__text, future_features=self.__parent_future_features)
            self.__compiled, self.__mutated = rewriter.rewrite_and_compile(output_func_name='reinteract_output',
                                                                           copy_func_name="__reinteract_copy",
                                                                           statement_name=self.__name)
            self.imports = rewriter.get_imports()
        except SyntaxError, e:
            self.error_message = e.msg
            self.error_line = e.lineno
            self.error_offset = e.offset
            self.state = Statement.COMPILE_ERROR
            return False
        except UnicodeDecodeError, e:
            self.error_message = str(e)
            self.state = Statement.COMPILE_ERROR
            return False
        except UnsupportedSyntaxError, e:
            self.error_message = e.value
            self.error_line = e.lineno
            self.state = Statement.COMPILE_ERROR
            return False
        except Exception, e:
            self.error_message = "Reinteract encountered an unexpected error while compiling this chunk.\n" + \
                "Please submit a bug with the code and the following information:\n\n" + \
                traceback.format_exc()
            self.state = Statement.COMPILE_ERROR
            return False

        self.future_features = self.__parent_future_features
        if self.imports is not None:
            merged = set()
            if self.future_features:
                merged.update(self.future_features)
            merged.update(self.imports.get_future_features())
            self.future_features = sorted(merged)

        self.state = Statement.COMPILE_SUCCESS
        return True

    def __coerce_to_unicode(self, s):
        # Make sure we have a unicode object with only safe characters
        if not isinstance(s, basestring):
            s = str(s)

        if isinstance(s, str):
            s = reunicode.decode(s, escape=True)
        elif isinstance(s, unicode):
            s = reunicode.escape_unsafe(s)

        return s

    def do_output(self, *args):
        """Called by execution of statements with non-None output (see L{Rewriter})"""

        if len(args) == 1:
            arg = args[0]

            if arg is None:
                return

            for wrapper in self.result_scope['__reinteract_wrappers']:
                wrapped = wrapper(arg)
                if wrapped != None:
                    arg = wrapped
                    break

            if isinstance(arg, CustomResult) or isinstance(arg, HelpResult):
                self.results.append(arg)
            else:
                self.results.append(self.__coerce_to_unicode(repr(arg)))

            self.result_scope['_'] = args[0]
        else:
            self.results.append(self.__coerce_to_unicode(repr(args)))
            self.result_scope['_'] = args

    def __stdout_write(self, s):
        s = self.__coerce_to_unicode(s)

        if self.__stdout_buffer is None:
            self.__stdout_buffer = s
        else:
            self.__stdout_buffer += s

        pos = 0
        while True:
            next = self.__stdout_buffer.find("\n", pos)
            if next < 0:
                break
            self.results.append(self.__stdout_buffer[pos:next])
            pos = next + 1
            
        if pos > 0:
            self.__stdout_buffer = self.__stdout_buffer[pos:]

    def before_execute(self):
        """Set up for execution

        Although before_execute() and after_execute() are automatically called when
        execute() is invoked, provision is made to call them separately to allow
        the caller to add locking so that execute() can be interrupted safely.
        before_execute() and after_execute() must not themselves not be interrupted
        and after_execute() must be called if before_execute() is called; with those
        provisions the operation of execute() can be interrupted at any point and
        the statement will be left in a sane state.

        """
        assert self.state != Statement.NEW and self.state != Statement.COMPILE_ERROR
        self.state = Statement.EXECUTING

        self.__worksheet.global_scope['__reinteract_statement'] = self
        Statement.__local.current = self
        self.__capture = StdoutCapture(self.__stdout_write)
        self.__capture.push()

    def after_execute(self):
        """Do cleanup tasks after execution

        See before_setup for details.

        """

        if self.state == Statement.EXECUTING:
            self.state = Statement.INTERRUPTED
            self.results = None
            self.result_scope = None

        self.__worksheet.global_scope['__reinteract_statement'] = None
        Statement.__local.current = None
        self.__stdout_buffer = None
        self.__capture.pop()
        self.__capture = None

    def __get_module_filename(self, m):
        filename = m.__file__
        if filename[-4:] in ('.pyc', '.PYC', '.pyo', '.PYO'):
            return filename[:-1]
        else:
            return filename

    def __format_traceback(self, error_type, value, tb, skip):
        # The top two frames are always statement.__do_execute and the compiled
        # statement, so we skip them as not useful. We additionally skip frames that
        # are inside the notebook and pkgutil modules because these are likely our
        # our custom import implementation
        skip_filenames = [self.__get_module_filename(m) for m in (notebook, pkgutil)]
        extracted = filter(lambda x: x[0] not in skip_filenames, traceback.extract_tb(tb)[skip:])

        # Replace all statement names with a generic "<statement>", since the names are
        # rather arbitrary from the user's perspective.
        formatted = "".join(traceback.format_list(extracted))
        formatted = Statement.NAME_PATTERN.sub("<statement>", formatted)
        last_line = "".join(traceback.format_exception_only(error_type, value))

        return (formatted + last_line).rstrip()

    def __do_execute(self):
        root_scope = self.__worksheet.global_scope
        if self.__parent:
            scope = copy.copy(self.__parent.result_scope)
        else:
            scope = copy.copy(root_scope)

        self.results = []
        self.result_scope = scope
        self.__stdout_buffer = None

        for root, description, copy_code in self.__mutated:
            try:
                # If the path to the mutated object starts with a module, ignore it;
                # our copy magic only applies to worksheet-loca variables
                if root in scope and type(scope[root]) != type(sys):
                    exec copy_code in scope, scope
            except:
                self.results.append(WarningResult("'%s' apparently modified, but can't copy it" % description))

        try:
            exec self.__compiled in scope, scope
            if self.__stdout_buffer is not None and self.__stdout_buffer != '':
                self.results.append(self.__stdout_buffer)
            self.state = Statement.EXECUTE_SUCCESS
        except KeyboardInterrupt, e:
            raise e
        except:
            self.results = None
            self.result_scope = None
            error_type, value, tb = sys.exc_info()

            # Get error_line from most recent frame refering to this Statement; if
            # tha most recent frame is the first frame referring to this Statement
            # then we omit it from the traceback.

            self.error_line = None
            self.error_offset = None

            index = 0
            first_frame = -1
            skip_first_frame = True

            tmp = tb
            while tmp:
                if tmp.tb_frame.f_code.co_filename == self.__name:
                    if first_frame < 0:
                        first_frame = index
                    else:
                        skip_first_frame = False
                    self.error_line = tmp.tb_lineno
                tmp = tmp.tb_next
                index += 1

            if skip_first_frame:
                skip = first_frame + 1
            else:
                skip = first_frame

            self.error_message = self.__format_traceback(error_type, value, tb, skip)

            self.state = Statement.EXECUTE_ERROR

        return self.state == Statement.EXECUTE_SUCCESS

    def execute(self):
        """Execute the statement"""
        was_in_execute = self.state == Statement.EXECUTING
        if not was_in_execute:
            self.before_execute()
        try:
            return self.__do_execute()
        finally:
            if not was_in_execute:
                self.after_execute()

    def mark_for_execute(self):
        """Mark a statement that executed succesfully as needing execution again"""
        if self.state != Statement.NEW and self.state != Statement.COMPILE_ERROR:
            self.state = Statement.COMPILE_SUCCESS

    @classmethod
    def get_current(self):
        """Gets the currently executing statement, if any. If no statement is
        currently executing, returns None."""
        try:
            return Statement.__local.current
        except AttributeError, e:
            return None


########################################################################
