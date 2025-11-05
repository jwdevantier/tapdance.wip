
## What this is

This repository contains code to make it easier to write C-based TAP (Test Anything Protocol)
programs.

You write a series of tests of the form:
```c
int test_xxxxxx(Custodian *c, ...test arguments...) {

}
```

And each test will run in its own process, its stdout and stderr output will be captured
and displayed iff the test fails.
The test return-value becomes the exit-code and a non-zero exit code indicates test failure.

We then generate an appropriate main function using a snippet like this:
```c
// <<crowbar
// reg = TestRegistry()
// # example - test without any additional parameters
// reg.add_test("test_program")
//
// # example - tests with parameters
// # should pass
// reg.add_test(("test_add", "2, 3, 5"))
// #should fail
// reg.add_test(("test_add", "2, 3, 4"))
// emit(tap_program(reg))
// >>
// <<end>>
```

The code between `<<crowbar` and `>>` is Python and note that we register tests by adding them
to a test registry which then gets passed to the component `tap_program`, which generates the
entire main function, ensures each test is run in its own process and displays the test's
STDOUT & STDERR output if the test failed.

## How to use

1. Create a new file (TAP program)
2. Write one or more C functions intended as tests (signature: `int xxx(Custodian *c, ...)`)
3. Write a crowbar snippet like above to generate the main function
4. (optional) trigger the code-generation step on this PC (`python crowbar.py <tap_test_file>`)
    * If you do this on the target, it must have Python 3.10+ (no library dependencies)
5. Transfer this and other TAP programs to the target PC
6. Compile the programs on the target (see `example_build_run.sh` for an example)
7. Run each TAP program, capture the output, determine test success/failure (this can be done by a TAP harness)

