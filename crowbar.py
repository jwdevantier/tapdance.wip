#!/usr/bin/env python3
"""
A Python embedded DSL for code- and markup generation.

Works both in scripts or as a preprocessor, where
blocks within the file are evaluated and the generated
code is inserted.

# Script Usage
--------------

    from crowbar import *

    @component
    def greet(emit, thing='World'):
        emit(
            "Hello", nl,
            f"Welcome {thing}", nl
        )

    # render result to list
    out = []
    # An emitter requires a writer function (str ->any)
    # out.append is one such example, file.write is another.
    emit = Emitter(writer=out.append, base_indent="", indent_step="   ")
    emit("out.py", greet(thing="Gordon"))

    # render result to string
    out_str = "".join(out)


# CLI (preprocessor) usage
--------------------------

Assume we define a component inside `my_components.py`:

    from crowbar import *

    @component
    def greet(emit, thing="Gordon"):
        emit(
            "Hello", nl,
            f"Welcome {thing}", nl
        )

Then, inside the file where we want to insert generated code, create one
or more blocks like so:

    # <<crowbar
    # from my_components import greet
    # emit(greet(thing="Gordon"))
    # emit(greet(thing="Alex"))
    # >>
    # <<end>>

Then run `crowbar.py file`, afterwards, the same block will look like this:

    # <<crowbar
    # from my_components import greet
    # emit(greet(thing="Gordon"))
    # emit(greet(thing="Alex"))
    # >>
    Hello
    Welcome Gordon
    Hello
    Welcome Alex
    # <<end>>


NOTE - you can create a block which only runs code, this can be useful
       when importing components at the top of the file:

    # <<crowbar
    # from my_components import greet
    # >>
    # <<end>>

NOTE - if you have just one line of code, you can also write the first parts
       on the same line, like so:

    # <<crowbar emit(greet(thing="Gordon"))>>
    # <<end>>
"""

from typing import Any, Callable, Dict, Optional, List, Union, Iterator, Tuple, Protocol

import argparse
from pathlib import Path
import re
import shutil
import tempfile
import sys
import os

__version__ = "0.2.1"
__description__ = "Crowbar - When clever hacking fails, crude whacking works!"


# Special marker types
class _Marker:
    def __init__(self, marker_type: str):
        self.__type = marker_type

    def __repr__(self) -> str:
        return f"<{self.__type}>"


# Global marker values
nl = _Marker("newline")
fl = _Marker("freshline")
indent = _Marker("indent")
dedent = _Marker("dedent")

MARKER_START = "<<crowbar"
MARKER_CODE_END = ">>"
MARKER_OUTPUT_END = "<<end>>"

rgx_leading_ws = re.compile(r"^(\s*)")

# Type definitions
Fpath = Union[str, Path]
EmitFunction = Callable[..., None]


class ComponentFunction(Protocol):
    __name__: str
    __doc__: str | None

    def __call__(self, emit: EmitFunction, *args: Any, **kwargs: Any) -> None: ...


WriterFunction = Callable[[str], Any]
EvalCodeFn = Callable[[str, str, str], str]


def str_leading_ws(s: str) -> str:
    """get leading whitespace from `s` as string."""
    m = rgx_leading_ws.match(s)
    return m.group(1) if m else ""


class CrowbarError(Exception):
    """Base exception for Crowbar errors"""

    pass


class UnexpectedEOF(CrowbarError):
    """Raised if we ran out of lines before a block's end of code or end marker line was found."""

    def __init__(self, line_block_start: int, msg: str):
        self.line_block_start = line_block_start
        super().__init__(msg)


class IndentationError(CrowbarError):
    """Raised if code lines don't share the same indentation prefix (minimum from line start to block opening marker)"""

    def __init__(self, block_start_lineno: int, code_lineno: int):
        super().__init__(
            f"code on line {code_lineno}, in block starting on line {block_start_lineno} - indentation is insufficient/wrong. All code lines must:\n\t1. Be indented as least as much as the block open marker ({MARKER_START})\n\t2. Use the same indentation for this part, for all code lines"
        )


class InvalidOutputPath(ValueError):
    def __init__(self, output_path: Path):
        self.output_path = output_path
        super().__init__(
            f"invalid `output_path` ({output_path}) - exists on file system but is NOT a file!"
        )


class CodeEvalError(CrowbarError):
    def __init__(self, start_line: int, code_lines: List[str], exception: Exception):
        self.start_line = start_line
        self.code_lines = code_lines
        self.exception = exception
        errmsg = "\n\t".join(str(exception).split("\n"))
        codemsg = "".join(code_lines)
        self.message = f"""Code in block starting at line {start_line} raised an error:\n---[ {type(exception).__name__} ]---\n{errmsg}\n---\n\nThis is *may* be due to code being incorrectly indented. Remember to indent each time such that it follows the opening marker: '{MARKER_START}'. Crowbar extracted this code block:\n---\n{codemsg}---\n"""
        super().__init__(self.message)


class FileParseError(CrowbarError):
    def __init__(self, fpath: Fpath, e: Exception):
        self.fpath = fpath
        self.exception = e
        super().__init__(f"Error parsing '{fpath}':\n{type(e).__name__}: {str(e)}")


class ComponentClosure:
    def __init__(self, func: ComponentFunction, args: Tuple[Any], ctx: Dict[str, Any]):
        self.__func = func
        self.__args = args
        self.__kwargs = ctx
        # copy over metadata too
        self.__name__ = f"ComponentClosure[{func.__name__}]"
        self.__doc__ = func.__doc__
        self.__module__ = func.__module__
        self.__qualname__ = getattr(func, "__qualname__", func.__name__)
        self.__annotations__ = getattr(func, "__annotations__", {})

    @property
    def func(self) -> ComponentFunction:
        return self.__func

    def __call__(self, emit: EmitFunction) -> None:
        self.__func(emit, *self.__args, **self.__kwargs)


class Component:
    def __init__(self, func: ComponentFunction):
        self.__func = func
        # copy over metadata too
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__
        self.__module__ = func.__module__
        self.__qualname__ = getattr(func, "__qualname__", func.__name__)
        self.__annotations__ = getattr(func, "__annotations__", {})

    def __call__(self, *args: Any, **kwargs: Any) -> ComponentClosure:
        return ComponentClosure(self.__func, args, kwargs)


def component(func: ComponentFunction) -> Component:
    """
    Decorator to create an Crowbar component.

    Usage:
        @component
        def greet(emit, name):
            emit("Hello", nl, f"Name: {name}")

    Args:
        func: Function that takes emit and any positional- and keyword arguments
              desired.

    Returns:
        A Component, which can be called with a context to produce a Component closure
        which in turn can be rendered with emit().
    """
    return Component(func)


class Emitter:
    def __init__(
        self, writer: WriterFunction, base_indent: str = "", indent_step: str = "   "
    ):
        """
        Create an emitter instance

        Args:
            writer: Function to write output to (e.g., file.write)
            base_indent: Base indentation applied to all output
            indent_step: String added for each indent level (default: "  ")

        Returns:
            None - all output is passed to the `writer`
        """
        self.fresh_line = True
        self.writer = writer
        self.indent_level = 0
        self.indent_step = indent_step
        self.base_indent = base_indent

    def get_indent_string(self) -> str:
        return self.base_indent + (self.indent_step * self.indent_level)

    def add_to_buffer(self, text: str, force_newline: bool = False) -> None:
        if not text:
            return

        if self.fresh_line:
            self.writer(self.get_indent_string())

        self.writer(text)

        if force_newline:
            self.writer("\n")
            self.fresh_line = True
        else:
            self.fresh_line = False

    def __call__(self, *args: Any) -> None:
        for arg in args:
            if isinstance(arg, _Marker):
                if arg == nl:
                    self.writer("\n")
                    self.fresh_line = True

                elif arg == fl:
                    if not self.fresh_line:
                        self.writer("\n")
                        self.fresh_line = True

                elif arg == indent:
                    self.indent_level += 1

                elif arg == dedent:
                    self.indent_level = max(0, self.indent_level - 1)

            elif isinstance(arg, ComponentClosure):
                # component with already provided ctx, provide emit function
                arg(self.__call__)
            elif arg is None:
                continue
            elif isinstance(arg, Component):
                raise TypeError(
                    f"emit() does not accept raw components - you must call it first, provide a context"
                )

            else:
                # String or other - add to buffer WITHOUT automatic newline
                self.add_to_buffer(str(arg), force_newline=False)


def _block_parser(
    iter: Iterator[str], eval: EvalCodeFn, indent_step: str
) -> Iterator[Tuple[bool, str]]:
    """
    Parse lines provided by `iter`, evaluating code in special blocks.

    Args:
        iter: provides the content to analyze, line-by-line
        eval: function with which to evaluate code sections
        indent_step: the string used for each level of indentation

    Returns:
        an iterator yielding tuples of bool, str, where the bool indicates
        whether the line is part of the code block or not, and the string is
        the line itself.
    """
    lineno: int = 0

    def next_line() -> Optional[str]:
        nonlocal lineno
        try:
            line = next(iter)
            lineno += 1
            return line
        except StopIteration:
            return None

    line: Optional[str] = next_line()
    while line is not None:
        _start = line.find(MARKER_START)
        yield _start != -1, line
        if _start != -1:
            _start_lineno = lineno
            _start_line = line
            _end = line.find(MARKER_CODE_END)
            if _end != -1:
                code_lines = [line[_start + len(MARKER_START) : _end].lstrip()]
                base_indent = str_leading_ws(line)
            else:
                code_lines = []
                line = next_line()
                while line is not None and MARKER_CODE_END not in line:
                    code_lines.append(line)
                    yield True, line
                    line = next_line()
                if line is None:
                    raise UnexpectedEOF(
                        _start_lineno,
                        f"reached end of file looking for end of code-section to block starting at line {_start_lineno}",
                    )
                yield True, line
                pref = code_lines[0][:_start]
                if len(pref) < _start:
                    # TODO: verify we can trigger this
                    raise IndentationError(
                        block_start_lineno=_start_lineno, code_lineno=_start_lineno + 2
                    )
                if len(code_lines) > 1:
                    # all code lines must share the indentation of the block opening line
                    for i, cl in enumerate(code_lines[1:]):
                        if cl[:_start] != pref:
                            raise IndentationError(
                                block_start_lineno=_start_lineno,
                                code_lineno=_start_lineno + 2 + i,
                            )
                base_indent = str_leading_ws(_start_line)
                code_lines = [cl[_start:] for cl in code_lines]  # strip prefix
            # skip past all the output from last run
            line = next_line()  # skip code end marker line
            while line is not None and MARKER_OUTPUT_END not in line:
                line = next_line()  # skip output lines
            if line is None:
                raise UnexpectedEOF(
                    _start_lineno,
                    f"reached end of file looking for end of block which started at line {_start_lineno}",
                )
            try:
                generated_output = eval("".join(code_lines), base_indent, indent_step)
            except Exception as e:
                print(e)
                raise CodeEvalError(_start_lineno, code_lines, e) from e
            if generated_output:
                yield False, generated_output
                yield False, "\n"
            if line is not None:
                yield True, line  # marker output end line

        line = next_line()  # ready next line for loop


class CrowbarPreprocessor:
    """
    A peprocessor for files with embedded code-generation blocks.

    Will process blocks like these:
    ---
    # <<crowbar
    # emit(my_component, {"name": "value"})
    # >>
    # Generated code will replace this
    # <<end>>
    ---

    Note that the prefix (' #') can be anything, so long as each line is equally
    indented.
    In this example, Python-style line comments were used, but multi-line
    comments, such as '/* ... */' in C, also work.
    """

    def __init__(self) -> None:
        pass

    def execute_code_block(self, code: str, base_indent: str, indent_step: str) -> str:
        """Execute Crowbar code and return generated output"""
        # Set up execution environment with persistent state
        crowbar = sys.modules[__name__]
        sys.modules["crowbar"] = crowbar

        exec_globals = {
            "crowbar": crowbar,
            "component": component,
            "nl": nl,
            "fl": fl,
            "indent": indent,
            "dedent": dedent,
            "__builtins__": __builtins__,
            # Include previously imported modules and globals
            **self.crowbar_globals,
        }

        # Collect rendered output
        output_parts: List[str] = []
        e = Emitter(
            writer=output_parts.append, base_indent=base_indent, indent_step=indent_step
        )

        # convenience method, allows calling emit directly in code blocks
        def emit(*args: Any) -> None:
            e(*args)

        exec_globals["emit"] = emit

        # Execute the code block
        exec(code, exec_globals)

        # Update persistent state with any new imports or definitions
        # Filter out Crowbar-specific functions and built-ins to avoid pollution
        for key, value in exec_globals.items():
            if key not in [
                "crowbar",
                "component",
                "nl",
                "fl",
                "indent",
                "dedent",
                "write_file",
                "__builtins__",
            ] and not key.startswith("_"):
                self.crowbar_globals[key] = value

        return "".join(output_parts)

    def process_file(
        self,
        input_file: Fpath,
        output_file: Optional[Fpath] = None,
        indent_step: str = "  ",
        omit_code_blocks: bool = False,
    ) -> None:
        self.crowbar_globals: Dict[str, Any] = {}
        input_path = Path(input_file).resolve()
        output_path = Path(input_file if output_file is None else output_file)
        if output_path.exists() and not output_path.is_file():
            raise InvalidOutputPath(output_path)
        if omit_code_blocks and input_path == output_path.resolve():
            raise ValueError(
                "to strip code blocks from ouput, you must be writing to a *different* file"
            )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            delete=False,
            prefix=f"{output_path.name}",
            suffix=".tmp",
        ) as tmp:
            tmp_path = Path(tmp.name)
            try:
                sys.path.insert(1, str(input_path.parent))
                with open(input_file, "r", encoding="utf-8") as fh:
                    for code_block_line, out_line in _block_parser(
                        iter(fh), self.execute_code_block, indent_step
                    ):
                        if omit_code_blocks and code_block_line:
                            continue
                        tmp.write(out_line)

                shutil.move(tmp_path, output_path)
            except Exception as e:
                tmp_path.unlink(missing_ok=True)
                raise FileParseError(input_file, e) from e
            finally:
                sys.path.pop(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process Python files with Crowbar preprocessor"
    )
    parser.add_argument("input_file", help="file to process")
    parser.add_argument(
        "output_file",
        nargs="?",
        default=None,
        help="where to write result (default: same file)",
    )
    parser.add_argument(
        "--no-code-blocks",
        action="store_true",
        default=False,
        help="write out result without the code blocks themselves. Useful when generating files.",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file {args.input_file} not found")
        sys.exit(1)

    processor = CrowbarPreprocessor()
    try:
        processor.process_file(
            args.input_file, args.output_file, omit_code_blocks=args.no_code_blocks
        )
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


# Export commonly used symbols
__all__ = [
    "component",
    "Emitter",
    "nl",
    "fl",
    "indent",
    "dedent",
    "CrowbarError",
    "CrowbarPreprocessor",
]
