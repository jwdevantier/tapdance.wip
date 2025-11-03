from typing import Tuple
from crowbar import *
from dataclasses import dataclass
import crowbar


@component
def fmt(emit, *elems, fl=True):
    # What IF you:
    # 1. implicitly added fl for each element given
    # 2. treated tuples as indent..dedent (indent, emit children, dedent)
    # 3. treated LISTS as grouped elements (i.e. no fl between)
    fltok = crowbar.fl if fl else None
    for e in elems:
        if isinstance(e, tuple):
            fmt(indent, *e, dedent, fl=fl)
        elif isinstance(e, list):
            fmt(*e, fl=False)
        else:
            emit(fltok, e)


@dataclass
class Test:
    fn: str
    args: str = ""

    def name(self) -> str:
        return f'{self.fn}({self.args})'


TestArg = str | Tuple[str, str] | Test


@dataclass
class CImport:
    name: str
    sys: bool = False


class TestRegistry:
    def __init__(self):
        self._tests = []

    def add_test(self, test: TestArg) -> None:
        if isinstance(test, str):
            test = Test(fn=test, args="")
        elif isinstance(test, tuple):
            fn, args = test
            test = Test(fn=fn, args=args)
        elif isinstance(test, Test):
            ...
        else:
            # NOTE: CYA - not wasted effort
            raise TypeError(f"expected str (test name), tuple (str, str) (test name and args) or Test type, got '{type(test).__name__}'")
        self._tests.append(test)

    def add_tests(self, *tests: TestArg) -> None:
        for test in tests:
            self.add_test(test)


@component
def tap_plan(emit, count):
    emit(fl, f'printf("1..{count}");')


@component
def tap_ok(emit, ok: bool, num: int, test_lbl: str, desc: str|None = None, params:str|None = None):
    if desc:
        desc = f' ({desc})'
    else:
        desc = ""
    status = "ok" if ok else "not ok"
    emit(fl, f'printf("{status} {num} - {test_lbl}{desc}\\n"')
    if params:
        emit(", ", params)
    emit(");")


@component
def tap_dmsg(emit, msg):
    emit(fl, f'printf("# {msg}\\n");')


@component
def c_import(emit, cimp: CImport):
    if cimp.sys:
        emit(fl, f'# <{cimp.name}>')
    else:
        emit(fl, f'# "{cimp.name}"')


@component
def tap_includes(emit):
    emit(
        fl, '#include <stdio.h>',
        fl, '#include <stdlib.h>',
        fl, '#include <string.h>',
    )


@component
def when(emit, cond, *elems):
    if cond:
        emit(*elems)


@component
def ifelse(emit, cond, ifbranch, elsebranch):
    if cond:
        emit(ifbranch)
    else:
        emit(elsebranch)


@component
def tap_test_child(emit, num, test: Test, timeout_secs: int|None):
    emit(
        fl, "dup2(tmpfd, STDERR_FILENO);",
        fl, "close(tmpfd);",
    )
    if timeout_secs is not None:
        emit(
            fl, "/* set timeout alarm */",
            fl, f'alarm({timeout_secs});',
        )
    emit(
        fl, f'int result = {test.fn}({test.args});',
        fl, "exit(result);"
    )


@component
def tap_test_parent(emit, num, test: Test, timeout_secs: int|None):
    emit(
        fl, "int status;",
        fl, "waitpid(pid, &status, 0);",
        fl, "if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {",
        fl, indent,
        tap_ok(True, num, test.name()),
        fl, dedent, "} else {", indent,
        fl, "if (WIFEXITED(status)) {", indent,
        fl, tap_ok(False, num, test.name(), "exit code: %d", "WEXITSTATUS(status)"),
        fl, dedent, "} else if (WIFSIGNALED(status)) {", indent
    )
    if timeout_secs is not None:
        emit(
            fl, "if (WTERMSIG(status) == SIGALRM) {", indent,
            fl, tap_ok(False, num, test.name(), f"timeout after {timeout_secs}s"),
            fl, dedent, "} else {", indent,
            fl, tap_ok(False, num, test.name(), "killed by signal %d", "WTERMSIG(status)"),
            fl, dedent, "}"
        )
    else:
        emit(
            fl, tap_ok(False, num, test.name(), "killed by signal %d", "WTERMSIG(status)")
        )
    emit(
        fl, dedent, "} else {", indent,
        fl, tap_ok(False, num, test.name(), "unknown failure"),
        fl, dedent, "} /* /tap_test_parent */",
    )


@component
def tap_test_call(emit, num: int, test: Test, timeout_secs: int|None):
    emit(
        # TODO: alter to gen path based on PID also
        fl, f'char tmpfile[] = "/tmp/tap_test_{num}";',
        fl, 'int tmpfd = mkstemp(tmpfile);',
        fl, 'if (tmpfd == -1) {', indent,
        tap_ok(False, num, test.name(), "tmpfile creation failed"),
        dedent, fl, "} else {", indent,
        fl, "pid_t pid = fork();",
        fl, "if (pid == 0) {", indent,
        tap_test_child(num, test, timeout_secs),
        fl, dedent, "} else if (pid > 0) {", indent,
        tap_test_parent(num, test, timeout_secs),
        dedent, fl, "} else { /* ... */", indent,
        dedent, fl, "}",
    )

@component
def tap_test_call_old(emit, num: int, test: Test, timeout_secs: int|None):
    # TODO: later, given an allocator, write a routine to generate a unique name here...
    emit(fmt(
        f'char tmpfile[] = "/tmp/tap_test_{num}";',
        'int tmpfd = mkstemp(tmpfile);',
        'if (tmpfd == -1) {',
        (
            f'fprintf(stderr, "# failed to create tmpfile for capturing test output (test: {test.name()})\\n");',
            tap_ok(False, num, test.name(), "tmpfile creation failed"),
        ),
        "} else {",
        (
            "pid_t pid = fork();",
            "if (pid == 0) {",
            (
                # child process, where the test is executed
                "dup2(tmpfd, STDERR_FILENO);",
                "close(tmpfd);",
                when(
                    timeout_secs is not None,
                    fmt(
                        "/* set timeout alarm */",
                        f'alarm({timeout_secs})',
                    )
                ),
                f"int result = {test.fn}({test.args});",
                "exit(result);",
            ),
            "} else if (pid > 0) {",
            (
                # parent process, wait for result
                "int status;",
                "waitpid(pid, &status, 0);",
                "if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {",
                (
                    tap_ok(True, num, test.name()),
                ),
                "} else {",
                (
                    # test fail, output diagnostics
                    "if (WIFEXITED(status)) {",
                    (
                        tap_ok(False, num, test.name(), "exit code: %d", "WEXITSTATUS(status)")
                    ),
                    "} else if (WIFSIGNALED(status)) {",
                    (
                        ifelse(
                            timeout_secs is not None,
                            fmt(
                                "if (WTERMSIG(status) == SIGALRM) {",
                                (
                                    tap_ok(False, num, test.name(), f"timeout after {timeout_secs}s"),
                                ),
                                "} else {",
                                (
                                    tap_ok(False, num, test.name(), "killed by signal %d", "WTERMSIG(status)")
                                ),
                            ),
                            fmt(
                                tap_ok(False, num, test.name(), "killed by signal %d", "WTERMSIG(status)")
                            )
                        )
                    ),
                    "} else {",
                    (
                        tap_ok(False, num, test.name(), "unknown failure")
                    ),
                    "}",
                ),
                "}",  # end of error-handling
            ),
            "}",  # NOTE: end of parent process clause

            # Only gets here in parent process, child exits early.
            # -- Read diagnostics from temp file

        )
    ))


@component
def tap_program(emit, reg: TestRegistry):
    tests = reg._tests
    emit(fl, "int main(void) {", indent)
    emit(*[
        tap_test_call(num, tst, timeout_secs=10) for num, tst in enumerate(tests)
    ])
    emit(

    )
    emit(
        fl, "return 0;",
        fl, dedent, "}"
    )


@component
def tap_program_old(emit, registry: TestRegistry):
    # emit(fl, nl, nl)
    tests = registry._tests

    # stdio, stdlib, string.h
    emit(fmt(
        "int main(void) {",
        (
            # tap_plan(len(tests)),
            # # call each test.
            # *[emit(tap_test_call(num, tst) for num, tst in enumerate(tests))],
            "return 0;"
        ),
        "}",
    ))
