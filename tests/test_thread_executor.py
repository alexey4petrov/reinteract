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

def test_thread_executor_0() :
    from test_utils import adjust_environment, assert_equals
    global_settings = adjust_environment()

    from reinteract.notebook import Notebook
    from reinteract.statement import Statement
    from reinteract.worksheet import Worksheet

    import threading
    import time

    from reinteract.thread_executor import ThreadExecutor, _pthread_kill, eventLoop

    failed = False

    notebook = Notebook()
    worksheet = Worksheet(notebook)

    def test_execute(statements):
        executor = ThreadExecutor()
        loop = executor.event_loop

        for s, expected_state, expected_results in statements:
            statement = Statement(s, worksheet)
            statement._expected_state = expected_state
            statement._expected_results = expected_results
            statement._got_executing = False
            executor.add_statement(statement)

        def on_statement_executing(executor, statement):
            if hasattr(statement, '_got_state'):
                statement._out_of_order = True
            statement._got_executing = True

        def on_statement_complete(executor, statement):
            statement._got_state = statement.state
            statement._got_results = statement.results
            statement._out_of_order = False

        def on_complete(executor):
            loop.quit()

        def interrupt():
            executor.interrupt()

        global timed_out
        timed_out = False
        def timeout():
            global timed_out
            timed_out = True
            loop.quit()

        executor.sig_statement_executing.connect(on_statement_executing)
        executor.sig_statement_complete.connect(on_statement_complete)
        executor.sig_complete.connect(on_complete)

        if executor.compile():
            executor.execute()

            interrupt_source = threading.Timer(0.5, interrupt)
            interrupt_source.start()

            timeout_source = threading.Timer(1.0, timeout)
            timeout_source.start()
            loop.run()
            if timed_out:
                raise AssertionError("Interrupting ThreadExecutor failed")

            interrupt_source.cancel()
            timeout_source.cancel()

        for s in executor.statements:
            assert_equals(s._got_state, s._expected_state)
            assert_equals(s._got_results, s._expected_results)
            if s._out_of_order:
                raise AssertionError("ThreadExecutor sent 'sig_statement_executing' after 'sig_statement_complete'")
            if s._expected_state == Statement.INTERRUPTED and not s._got_executing:
                raise AssertionError("ThreadExecutor did not send 'sig_statement_executing' within timeout")

    test_execute(
        [
            ("a = 1", Statement.COMPILE_SUCCESS, None),
            ("a =", Statement.COMPILE_ERROR, None)
        ])

    test_execute(
        [
            ("a = 1", Statement.EXECUTE_SUCCESS, []),
            ("a", Statement.EXECUTE_SUCCESS, ['1'])
        ])

    test_execute(
        [
            ("a = 1", Statement.EXECUTE_SUCCESS, []),
            ("b", Statement.EXECUTE_ERROR, None),
            ("c = 2", Statement.COMPILE_SUCCESS, None)
        ])

    # Test interrupting straight python code
    test_execute(
        [
            ("y = 1", Statement.EXECUTE_SUCCESS, []),
            ("for x in xrange(0,100000000):\n    y = y * 2\n    if y > 100: y = 1", Statement.INTERRUPTED, None),
            ("z = 1", Statement.COMPILE_SUCCESS, None)
        ])

    # Test interrupting a blocking syscall, if support on this platform
    if _pthread_kill is not None:
        test_execute(
            [
                ("import sys", Statement.EXECUTE_SUCCESS, []),
                ("sys.stdin.readline()", Statement.INTERRUPTED, None),
                ("z = 1", Statement.COMPILE_SUCCESS, None)
            ])
        pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_thread_executor_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
