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
            args = [indent, *e, dedent]
            emit(fmt(*args, fl=fl))
        elif isinstance(e, list):
            emit(fltok, fmt(*e, fl=False))
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
    emit(fl, f'printf("1..{count}\\n");')


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
def tap_test_child(emit, num, test: Test, timeout_secs: int|None):
    emit(fmt(
        "dup2(tmpfd, STDERR_FILENO);",
        "dup2(tmpfd, STDOUT_FILENO);",
        "close(tmpfd);"
    ))
    if timeout_secs is not None:
        emit(fmt(
            "/* set timeout alarm */",
            f'alarm({timeout_secs});',
        ))
    emit(fmt(
        "Allocator a;",
        "tapd_stdalloc_init(&a);",
        "Custodian c;",
        "custodian_init(&c, NULL, &a);"
    ))
    if test.args:
        emit(fl, f'int result = {test.fn}(&c, {test.args});')
    else:
        emit(fl, f'int result = {test.fn}(&c);')
    emit(fmt(
        f'custodian_shutdown(&c);',
        "exit(result);"
    ))


@component
def tap_dump_test_output(emit, tmpfd):
    """
    Reads captured stdout/stderr from tmpfd and outputs it as TAP diagnostics.
    Each line is prefixed with '#: ' to distinguish from regular TAP output.
    Handles long lines (>buffer size) and missing trailing newlines safely.
    """
    emit(fmt(
        "lseek(tmpfd, 0, SEEK_SET);",
        'FILE *tmpfp = fdopen(tmpfd, "r");',
        'if (!tmpfp) {',
        (
            'fprintf(stderr, "# Failed to open test output for reading\\n");',
            'close(tmpfd);',
        ),
        '} else {',
        (
            'const size_t BUFLEN = 1024;',
            'char line_buf[BUFLEN];',
            'int fresh_line = 1;',
            'while (fgets(line_buf, BUFLEN, tmpfp)) {',
            (
                'size_t len = strlen(line_buf);',
                'if (fresh_line) {',
                (
                    'printf("#: ");',
                    'fresh_line = 0;',
                ),
                "}",
                'printf("%s", line_buf);',
                '/* Check if we reached end of line */',
                'if (len > 0 && line_buf[len-1] == \'\\n\') {',
                (
                    'fresh_line = 1;',
                ),
                '} else if (len < BUFLEN - 1) {',
                (
                    '/* EOF without trailing newline - add one to preserve TAP integrity */',
                    'printf("\\n");',
                    'fresh_line = 1;',
                ),
                "}",
                '/* else: partial line (buffer full), continue reading */',
            ),
            "}",
            "fclose(tmpfp);",
        ),
        "}",
    ))


@component
def tap_test_parent_timeout(emit, num, test: Test, timeout_secs: int|None):
    if timeout_secs is None:
        emit(fmt(
            tap_ok(False, num, test.name(), "killed by signal %d", "WTERMSIG(status)")
        ))
        return

    emit(fmt(
        "if (WTERMSIG(status) == SIGALRM) {",
        (
            tap_ok(False, num, test.name(), f"timeout after {timeout_secs}s"),
        ),
        "} else {",
        (
            tap_ok(False, num, test.name(), "killed by signal %d", "WTERMSIG(status)"),
        ),
        "}",
    ))


@component
def tap_test_parent(emit, num, test: Test, timeout_secs: int|None):
    emit(fmt(
        "int status;",
        "waitpid(pid, &status, 0);",
        nl,
        "if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {",
        (tap_ok(True, num, test.name()),),
        "} else {",
        (
            "if (WIFEXITED(status)) {",
            (
                tap_ok(False, num, test.name(), "exit code: %d", "WEXITSTATUS(status)"),
            ),
            "} else if (WIFSIGNALED(status)) {",
            (
                tap_test_parent_timeout(num, test, timeout_secs),
            ),
            "} else {",
            (
                tap_ok(False, num, test.name(), "unknown failure"),
            ),
            "}",
            tap_dump_test_output("tmpfd"),
        ),
        "}",
        "unlink(tmpfile);",
    ))


@component
def tap_test_call(emit, num: int, test: Test, timeout_secs: int|None):
    emit(fmt(
        "{",
        (
            f'char tmpfile[] = "/tmp/tap_test_{num}";',
            'int tmpfd = mkstemp(tmpfile);',
            'if (tmpfd == -1) {',
            (tap_ok(False, num, test.name(), "tmpfile creation failed"),),
            "} else {",
            (
                "pid_t pid = fork();",
                "if (pid == 0) {",
                (tap_test_child(num, test, timeout_secs),),
                "} else if (pid > 0) {",
                (tap_test_parent(num, test, timeout_secs),),
                "} else {",
                (
                    "close(tmpfd);",
                    "unlink(tmpfile);",
                    tap_ok(False, num, test.name(), "fork failed"),
                ),
                "}",
            ),
            "}",
        ),
        "}",
    ))

@component
def tap_program(emit, reg: TestRegistry):
    tests = reg._tests
    emit(
        fl, "int main(void) {",
        indent,
        fl, 'printf("TAP version 14\\n");',
        fl, tap_plan(len(tests)),
    )

    for num, test in enumerate(tests, start=1):
        emit(tap_test_call(num, test, timeout_secs=10))
    emit(
        fl, "return 0;",
        fl, dedent, "}"
    )

