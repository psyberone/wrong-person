"""Plant one fault at a time in a copy of this repository and see that the test it names fails.

    python3 tools/planted_faults.py [--only LABEL] [--no-skips] [--check]

A planted fault (a hand-written mutant) is one small, wrong edit to a file of
this repository. The lists under tools/faults/ hold them, each beside the full
name of the one test that is meant to catch it. This script copies the
repository to a scratch folder and sees that the whole suite passes there. Then,
for each fault, it plants the fault in the copy, runs that fault's test, and
takes the fault out again. The repository itself is never written to.

    --only LABEL   plant only the faults whose label begins with LABEL
    --no-skips     a test that is skipped fails the run (GitHub runs it this way)
    --check        see that every fault can be planted and that every test named
                   is there, and run no test

It ends with 0 when every fault was killed (its test ran and failed), 1 when a
fault survived (its test passed), and 2 when it cannot vouch for the result. It
prints labels and the names of tests and files, never the text of an edit. A
development tool: the package never imports it.
"""
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path, PurePosixPath

USAGE = "usage: python3 tools/planted_faults.py [--only LABEL] [--no-skips] [--check]"
LISTS = "tools/faults"                                # the folder of lists, each a Python file that holds FAULTS
SECONDS = 120                                         # how long one test may take with a fault planted
SUITE_SECONDS = 1800                                  # how long the whole suite may take with none
A_TEST = re.compile(r"\w+\.\w+\.\w+")                 # a test's full name: file.Class.test
ANSWER = "planted-faults-answer:"                     # the line a child process gives its answer on
FAILED, PASSED, SKIPPED, NOT_LOADED = "failed", "passed", "skipped", "not loaded"

Fault = namedtuple("Fault", "label test edits")       # edits: [(file, the text to replace, what replaces it), ...]

# Run in the copy, in a Python of its own. "names" answers with the names that are not one test each;
# "run" runs the one test named and answers with what became of it. A test is run inside a suite, so
# that what its class and its file set up for it is set up.
CHILD = r'''
import json, sys, unittest

def the_one(name):
    try:
        found = unittest.defaultTestLoader.loadTestsFromName(name)
    except Exception:
        return None
    tests = []
    def flatten(suite):
        for item in suite:
            flatten(item) if isinstance(item, unittest.TestSuite) else tests.append(item)
    flatten(found)
    return tests[0] if len(tests) == 1 and tests[0].id() == name else None

mode, names = sys.argv[1], sys.argv[2:]
if mode == "names":
    answer = [name for name in names if the_one(name) is None]
else:
    name, test = names[0], the_one(names[0])
    if test is None:
        answer = "not loaded"
    else:
        result = unittest.TestResult()
        unittest.TestSuite([test]).run(result)
        failed = [case.id() for case, _ in result.failures + result.errors]
        if any(case == name or case.startswith(name + " ") for case in failed):
            answer = "failed"
        elif result.skipped and not failed:
            answer = "skipped"
        elif result.testsRun == 1 and result.wasSuccessful():
            answer = "passed"
        else:
            answer = "no verdict"
print()
print("''' + ANSWER + r'''" + json.dumps(answer))
'''


class CannotVouch(Exception):
    """The run proves nothing as it stands; the message says why."""


def a_fault(entry, where):
    """One entry of a list as a Fault, or a refusal that names the list it is in and never quotes an edit."""
    def refuse(why):
        raise CannotVouch(f"{where}: {why}")

    if not isinstance(entry, (tuple, list)) or len(entry) != 3:
        refuse("a fault is a label, the full name of one test, and a list of edits")
    label, test, edits = entry
    if not isinstance(label, str) or not label.split():
        refuse("a fault's label is some words")
    name = label.split()[0]
    if not isinstance(test, str) or not A_TEST.fullmatch(test):
        refuse(f"{name}: a test is named in full, as file.Class.test")
    if not isinstance(edits, (tuple, list)) or not edits:
        refuse(f"{name}: a fault has at least one edit")
    for edit in edits:
        if not isinstance(edit, (tuple, list)) or len(edit) != 3 or not all(isinstance(part, str) for part in edit):
            refuse(f"{name}: an edit is a file, the text to replace, and the text that replaces it")
        file, old, new = edit
        path = PurePosixPath(file)
        if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in file:
            refuse(f"{name}: {file} is not a path inside this repository")
        if not old or old == new:
            refuse(f"{name}: an edit replaces some text with other text")
    return Fault(label, test, [tuple(edit) for edit in edits])


def listed(root):
    """Every fault of every list under tools/faults/, in the order the lists hold them. No two may share a label's first word."""
    faults, seen = [], {}
    folder = root / LISTS
    for path in sorted(folder.glob("*.py")) if folder.is_dir() else []:
        where = f"{LISTS}/{path.name}"
        try:
            held = runpy.run_path(str(path))
        except Exception as error:                    # a list is this project's own file; whatever stops it reading, say which list
            raise CannotVouch(f"{where} could not be read ({type(error).__name__})") from None
        if not isinstance(held.get("FAULTS"), list):
            raise CannotVouch(f"{where} must hold a list called FAULTS")
        for number, entry in enumerate(held["FAULTS"], 1):
            fault = a_fault(entry, f"{where}, entry {number}")
            name = fault.label.split()[0]
            if name in seen:
                raise CannotVouch(f"two faults are labelled {name}: one in {seen[name]} and one in {where}")
            seen[name] = where
            faults.append(fault)
    if not faults:
        raise CannotVouch(f"there is no fault to plant: no list under {LISTS}/ holds one")
    return faults


def copy_of(root, lab):
    """Copy to the lab every file git tracks, and every file it has not been told of and does not ignore -> their names."""
    command = ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    try:
        done = subprocess.run(command, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        done = None
    if done is None or done.returncode:
        raise CannotVouch("git could not list the files of this repository")
    copied = []
    for name in sorted({os.fsdecode(name) for name in done.stdout.split(b"\0") if name}):
        source = root / name
        if source.is_symlink() or not source.is_file():   # deleted but not yet taken out of git, or not an ordinary file
            continue
        (lab / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, lab / name)
        copied.append(name)
    return copied


def plant(lab, fault):
    """Make a fault's edits in the lab -> what each file it changed held before. If one edit does not fit, none is left in."""
    saved = {}
    for file, old, new in fault.edits:
        path = lab / file
        try:
            text = path.read_bytes().decode("utf-8") if path.is_file() else None
        except UnicodeDecodeError:
            text = None
        if text is None or text.count(old) != 1:
            put_back(saved)
            if text is None:
                raise CannotVouch(f"{file} is not a file of this repository that holds text")
            raise CannotVouch(f"the text to replace is found {text.count(old)} times in {file}, and must be found once")
        saved.setdefault(path, text)
        path.write_bytes(text.replace(old, new).encode("utf-8"))
    return saved


def put_back(saved):
    """Take a fault out again: each file it changed holds what it held before."""
    for path, text in saved.items():
        path.write_bytes(text.encode("utf-8"))


def python(lab, *args, seconds):
    """Run Python in the lab, where the lab's own package and tests are the ones imported, whatever the caller's settings."""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(lab / "src"), str(lab / "tests")]), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-B", *args], cwd=lab, env=env, capture_output=True, timeout=seconds,
                          encoding="utf-8", errors="replace")


def answer_of(done):
    """What a child process answered, or None if it ended without answering."""
    for line in reversed(done.stdout.splitlines()):
        if line.startswith(ANSWER):
            try:
                return json.loads(line[len(ANSWER):])
            except ValueError:
                return None
    return None


def suite_passes(lab):
    """Run the whole suite in the lab with no fault planted -> how many tests ran. A failure, or no test at all, is refused."""
    try:
        done = python(lab, "-m", "unittest", "discover", "-s", "tests", seconds=SUITE_SECONDS)
    except subprocess.TimeoutExpired:
        done = None
    ran = re.search(r"^Ran (\d+) tests? in ", done.stderr, re.M) if done else None
    if done is None or done.returncode or not ran or not int(ran.group(1)):
        raise CannotVouch("with no fault planted the tests must run and pass in the copy, or a failing test proves nothing")
    return int(ran.group(1))


def unfit(lab, faults):
    """Why each fault that cannot be tried cannot be: its text is not found once, or the test it names is not there."""
    problems = []
    for fault in faults:
        try:
            put_back(plant(lab, fault))
        except CannotVouch as error:
            problems.append(f"{fault.label}: {error}")
    try:
        missing = answer_of(python(lab, "-c", CHILD, "names", *sorted({fault.test for fault in faults}), seconds=SUITE_SECONDS))
    except subprocess.TimeoutExpired:
        missing = None
    if not isinstance(missing, list):
        raise CannotVouch("the tests could not be looked up by name in the copy")
    return problems + [f"{fault.label}: no such test: {fault.test}" for fault in faults if fault.test in missing]


def judged(lab, test):
    """Run one test in the lab -> (FAILED, PASSED, SKIPPED or None, and for None why nothing can be said)."""
    try:
        said = answer_of(python(lab, "-c", CHILD, "run", test, seconds=SECONDS))
    except subprocess.TimeoutExpired:
        return None, f"did not end within {SECONDS} seconds"
    if said in (FAILED, PASSED, SKIPPED):
        return said, ""
    return None, "could not be loaded with the fault planted" if said == NOT_LOADED else "gave no verdict with the fault planted"


def tried(root, faults, check):
    """Plant each fault in a copy of the repository -> how many were killed, survived, were skipped, could not be judged.

    With `check`, each fault is only planted and taken out again, and the answer is None.
    """
    with tempfile.TemporaryDirectory(prefix="planted-faults-") as scratch:
        lab = Path(scratch) / "repository"
        lab.mkdir()
        names = copy_of(root, lab)
        problems = unfit(lab, faults)
        if problems:
            raise CannotVouch("\n  ".join([f"{len(problems)} of the faults cannot be tried as they stand:", *problems]))
        if check:
            return None
        print(f"no fault planted: {suite_passes(lab)} tests ran and passed in the copy", flush=True)
        counts = dict.fromkeys((FAILED, PASSED, SKIPPED, None), 0)
        for fault in faults:
            saved = plant(lab, fault)
            try:
                outcome, why = judged(lab, fault.test)
            finally:
                put_back(saved)
            counts[outcome] += 1
            said = {FAILED: "killed", PASSED: "SURVIVED", SKIPPED: "skipped here", None: "CANNOT SAY"}[outcome]
            more = {FAILED: "", PASSED: f": the test {fault.test} passed", SKIPPED: f": the test {fault.test} was skipped",
                    None: f": the test {fault.test} {why}"}[outcome]
            print(f"{said:<14}{fault.label}{more}", flush=True)
        for name in names:
            if (lab / name).read_bytes() != (root / name).read_bytes():
                raise CannotVouch(f"{name} in the copy no longer matches the repository, so a test wrote to it or the "
                                  "repository changed during the run")
    return counts[FAILED], counts[PASSED], counts[SKIPPED], counts[None]


def main(argv=None, root=None):
    """Read the arguments, plant the faults, print what became of each -> the status to end with."""
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[1] if root is None else Path(root)
    only, no_skips, check = None, False, False
    while args:
        arg = args.pop(0)
        if arg == "--no-skips":
            no_skips = True
        elif arg == "--check":
            check = True
        elif arg == "--only" and args and only is None:
            only = args.pop(0)
        else:
            print(USAGE, file=sys.stderr)
            return 2
    try:
        faults = [fault for fault in listed(root) if fault.label.startswith(only or "")]
        if not faults:
            raise CannotVouch(f"no fault's label begins with {only}")
        plural = "" if len(faults) == 1 else "s"
        counts = tried(root, faults, check)
        if counts is None:
            print(f"{len(faults)} fault{plural}: every one can be planted, and every test named is there")
            return 0
        killed, survived, skipped, unsure = counts
        print(f"{len(faults)} fault{plural}: {killed} killed, {survived} survived, {skipped} skipped here, {unsure} that cannot be judged")
        if unsure:
            raise CannotVouch(f"{unsure} fault{'' if unsure == 1 else 's'} could not be judged")
        if skipped and no_skips:
            raise CannotVouch(("1 fault's test was skipped" if skipped == 1 else f"{skipped} faults' tests were skipped")
                              + ", and here no test may be skipped")
    except CannotVouch as error:
        print(f"planted faults: cannot vouch: {error}", file=sys.stderr)
        return 2
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
