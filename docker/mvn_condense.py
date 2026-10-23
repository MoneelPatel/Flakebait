"""Condense Maven console output for the agent (reads stdin, writes stdout, line by line).

Kept: everything about the build's outcome (errors, compiler errors, BUILD SUCCESS/FAILURE), the Surefire
summary, and for each failing test its name, message and the first STACK_LINES stack-trace lines.
Dropped: download progress, plugin execution headers, compiler/resources info, separators, and the tests' own
console output. The flaky test's failure is condensed exactly like any other failure.
"""
import os
import re
import sys

STACK_LINES = int(os.environ.get("FB_STACK_LINES", "15"))

DROP = re.compile(
    r"^\[INFO\] (Download(ing|ed)( from)?|--- |-{5,}|Building |Compiling |Nothing to compile|Changes detected|"
    r"Using |skip|Copying |Recompiling |Scanning for projects|Reactor Build Order|\s*$|"
    r"Installing |Loading |No sources|Tests are skipped|Surefire report directory|BUILD |Total time|Finished at|"
    r"Reactor Summary|\[\s*\d+%\]|.* \.+ SUCCESS \[)"
    r"|^(Download(ing|ed)|Progress \(\d+\)|\s*\d+/\d+ [kKMB])"
)
KEEP_ANYWAY = re.compile(r"^\[INFO\] BUILD (SUCCESS|FAILURE)")
STACK = re.compile(r"^\s+at |^\s*\.\.\. \d+ (more|common frames omitted)|^Caused by: |^\s+Suppressed: ")
FAIL_MARK = re.compile(r"<<< (FAILURE|ERROR)!")


def main() -> None:
    in_tests = False        # between the Surefire banner and its "Results:" section
    in_failure = False      # after a "<<< FAILURE!" line: message and stack lines follow
    stack_left = 0
    out = sys.stdout
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        plain = re.sub(r"\x1b\[[0-9;]*m", "", line)
        if " T E S T S" in plain:
            in_tests, in_failure = True, False
            out.write(plain + "\n")
            continue
        if in_tests:
            if re.match(r"^\[(INFO|ERROR|WARNING)\] Results:", plain):
                in_tests, in_failure = False, False
                out.write(plain + "\n")
            elif FAIL_MARK.search(plain):
                in_failure, stack_left = True, STACK_LINES
                out.write(plain + "\n")
            elif re.match(r"^\[(INFO|ERROR|WARNING)\] (Running |Tests run:)", plain):
                in_failure = False
                out.write(plain + "\n")
            elif in_failure:
                if STACK.match(plain):
                    if stack_left > 0:
                        out.write(plain + "\n")
                    stack_left -= 1
                elif plain.startswith("[") or not plain.strip():
                    in_failure = False        # the test's own console output resumes; drop it
                else:
                    out.write(plain + "\n")   # the failure message (may span several lines)
            out.flush()
            continue
        if KEEP_ANYWAY.match(plain) or not DROP.match(plain):
            out.write(plain + "\n")
            out.flush()


if __name__ == "__main__":
    main()
