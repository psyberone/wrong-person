"""Plant one fault at a time in a copy of this repository and see that the test it names fails.

    python3 tools/planted_faults.py [--only LABEL] [--no-skips] [--check]

A planted fault (a hand-written mutant) is one small, wrong edit to a file of
this repository: some text that is found at exactly one place is replaced, or a
file that is not there is added. The lists under tools/faults/ hold them, each
beside the full name of the one test that is meant to catch it. This script
copies the repository to a scratch folder. There, with no fault planted, it sees
that the whole suite passes, and that each test named does not fail when it is
run alone, which is how it is run under its fault. Then, for each fault, it
plants the fault in the copy, runs that fault's test, and takes the fault out
again. The repository itself is never written to.

    --only LABEL   plant only the faults whose label begins with LABEL
    --no-skips     a test that is skipped fails the run (GitHub runs it this way)
    --check        see that every fault can be planted and that every test named
                   is there, and run no test

It ends with 0 when every fault was killed (its test ran and failed in its own
body) or, without --no-skips, was skipped here; with 1 when a fault survived
(its test passed); and with 2 when it cannot vouch for the result, whether or
not a fault survived as well. It prints labels and the names of tests and
files, never the text of an edit. A development tool: the package never
imports it.
"""
import contextlib
import json
import os
import re
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path, PurePosixPath, PureWindowsPath

USAGE = "usage: python3 tools/planted_faults.py [--only LABEL] [--no-skips] [--check]"
LISTS = "tools/faults"                                # the folder of lists, each a Python file that holds FAULTS
SECONDS = 120                                         # how long one test may take, and the looking up of the tests named
SUITE_SECONDS = 300                                   # how long the whole suite may take with no fault planted
GIT_SECONDS = 60                                      # how long git may take to list the files
DEPTH = "PLANTED_FAULTS_DEPTH"                        # tells a process how many runs of this script it is inside
A_TEST = re.compile(r"\w+\.\w+\.\w+")                 # a test's full name: file.Class.test
PLAIN = re.compile(r"[\w./-]+")                       # a name that can be printed as it stands
FAILED, PASSED, SKIPPED, NOT_LOADED = "failed", "passed", "skipped", "not loaded"
STOPS = tuple(getattr(signal, name) for name in ("SIGTERM", "SIGHUP") if hasattr(signal, name))

# The variables by which git is pointed at one repository: what `git rev-parse --local-env-vars` lists.
OF_ONE_REPOSITORY = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY",
    "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE", "GIT_PREFIX", "GIT_SHALLOW_FILE", "GIT_COMMON_DIR")

Fault = namedtuple("Fault", "label test edits")       # edits: [(file, the text to replace, what replaces it), ...];
                                                      # None for the text to replace adds the file

# Run in the copy, in a Python of its own, and told where to write its answer. "names" answers with the names
# that are not one test each; "suite" runs every test in the folder named and answers with how many ran and which did not pass;
# "run" runs the one test named and answers with what became of it. A test is run inside a suite, so that what
# its class and its file set up for it is set up. It has failed only if it failed in its own body: a fault
# that breaks what the class sets up fails every test of the class alike, so the one named has caught nothing.
CHILD = r'''
import json, sys, unittest

def flat(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flat(item)
        else:
            yield item

def the_one(name):
    try:
        tests = list(flat(unittest.defaultTestLoader.loadTestsFromName(name)))
    except Exception:
        return None
    return tests[0] if len(tests) == 1 and tests[0].id() == name else None

class Result(unittest.TestResult):
    in_its_body = False

    def note(self, test, error):
        body = getattr(getattr(type(test), getattr(test, "_testMethodName", ""), None), "__code__", None)
        step = error[2]
        while step is not None:
            self.in_its_body = self.in_its_body or step.tb_frame.f_code is body
            step = step.tb_next

    def addFailure(self, test, error):
        self.note(test, error)
        super().addFailure(test, error)

    def addError(self, test, error):
        self.note(test, error)
        super().addError(test, error)

    def addSubTest(self, test, subtest, error):
        if error is not None:
            self.note(test, error)
        super().addSubTest(test, subtest, error)

where, mode, names = sys.argv[1], sys.argv[2], sys.argv[3:]
if mode == "names":
    answer = [name for name in names if the_one(name) is None]
elif mode == "suite":
    result = unittest.TestResult()
    unittest.defaultTestLoader.discover(names[0]).run(result)
    failed = sorted({case.id() for case, _ in result.failures + result.errors} | {case.id() for case in result.unexpectedSuccesses})
    answer = {"ran": result.testsRun, "failed": failed[:3], "others": len(failed[3:])}
else:
    test = the_one(names[0])
    if test is None:
        answer = "not loaded"
    else:
        result = Result()
        unittest.TestSuite([test]).run(result)
        if result.in_its_body:
            answer = "failed"
        elif result.skipped:
            answer = "skipped"
        elif result.wasSuccessful():
            answer = "passed"
        else:
            answer = "no verdict"
with open(where, "w", encoding="utf-8") as file:
    json.dump(answer, file)
'''


class CannotVouch(Exception):
    """The run proves nothing as it stands; the message says why."""


class Stopped(BaseException):
    """A signal asked the run to stop. Raised where the run stands, so that on its way out it ends what it started and clears its scratch folder."""


def stop(number, frame):
    raise Stopped(number)


def shown(name):
    """A name from the disk or the command line, as it is printed: as it stands if it is plain, and otherwise quoted
    on one line, with nothing in it that GitHub's runner would read as a command to it."""
    return name if PLAIN.fullmatch(name) else json.dumps(name).replace("##[", "#\\u0023[")


def without_gits_own(env, ceiling):
    """A copy of an environment that points git at no repository, and names a folder that git may not look in or above.

    Git hands a hook GIT_DIR and GIT_INDEX_FILE, and with them any git started below works on that repository,
    wherever it is told to look. Without them git looks upward from where it is run, and a folder with no
    repository of its own may sit inside someone else's.
    """
    kept = {name: value for name, value in env.items() if name not in OF_ONE_REPOSITORY}
    kept["GIT_CEILING_DIRECTORIES"] = os.pathsep.join(filter(None, [str(ceiling), env.get("GIT_CEILING_DIRECTORIES")]))
    return kept


@contextlib.contextmanager
def one_deeper():
    """For as long as a run lasts, tell whatever it starts or reads that it is inside a run of this script.

    The script's own tests start it, and it runs tests. Two deep is that, and no more: a third run is refused, so
    that a test or a list that starts the script again cannot do so without end.
    """
    before = os.environ.get(DEPTH)
    if before not in (None, "0", "1"):
        raise CannotVouch(f"the script has been started from inside its own runs more than two deep ({DEPTH} says so), and stops here")
    os.environ[DEPTH] = "2" if before == "1" else "1"
    try:
        yield
    finally:
        os.environ[DEPTH] = before or "0"


def a_fault(entry, where):
    """One entry of a list as a Fault, or a refusal that names the list it is in and never quotes an edit."""
    def refuse(why):
        raise CannotVouch(f"{where}: {why}")

    if not isinstance(entry, (tuple, list)) or len(entry) != 3:
        refuse("a fault is a label, the full name of one test, and a list of edits")
    label, test, edits = entry
    if not isinstance(label, str) or not label.split() or not label.isprintable():
        refuse("a fault's label is one line of words")
    if "##[" in label or label.lstrip().startswith("::"):   # a label is printed as it stands, and at the start of a line too
        refuse("a fault's label holds nothing that GitHub's runner reads as a command")
    name = label.split()[0]
    if not isinstance(test, str) or not A_TEST.fullmatch(test):
        refuse(f"{name}: a test is named in full, as file.Class.test")
    if not isinstance(edits, (tuple, list)) or not edits:
        refuse(f"{name}: a fault has at least one edit")
    for edit in edits:
        if not isinstance(edit, (tuple, list)) or len(edit) != 3:
            refuse(f"{name}: an edit is a file, the text to replace, and the text that replaces it")
        file, old, new = edit
        if not isinstance(file, str) or not isinstance(new, str) or not (old is None or isinstance(old, str)):
            refuse(f"{name}: an edit is a file, the text to replace (or None, to add the file), and the text that replaces it")
        if not file.isprintable() or "##[" in file:   # a name is printed, and must not start a line of its own in a log
            refuse(f"{name}: a file is named on one line, with nothing in it that GitHub's runner reads as a command")
        path = PurePosixPath(file)
        if not path.parts or ".." in path.parts or "\\" in file or PureWindowsPath(file).anchor:   # Windows parts folders with \ too
            refuse(f"{name}: {file} is not a path inside this repository")
        if old in ("", new):
            refuse(f"{name}: an edit replaces some text with other text")
        try:
            new.encode("utf-8")
        except UnicodeEncodeError:
            refuse(f"{name}: the text that replaces it cannot be written to a file")
    return Fault(label, test, [tuple(edit) for edit in edits])


def listed(root):
    """Every fault of every list under tools/faults/, in the order the lists hold them. No two may share a label's first word."""
    faults, seen = [], {}
    folder = root / LISTS
    for path in sorted(folder.glob("*.py")) if folder.is_dir() else []:
        where = shown(f"{LISTS}/{path.name}")
        try:
            held = runpy.run_path(str(path))
        except (Exception, SystemExit) as error:      # say which list; one that ended the program would end this run with 0, and not a word
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
        done = subprocess.run(command, capture_output=True, timeout=GIT_SECONDS, env=without_gits_own(os.environ, root.parent))
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
    for name in copied:                               # its faults would never be planted, and nothing would say so
        if name.startswith(LISTS + "/") and (PurePosixPath(name).parent != PurePosixPath(LISTS) or not name.endswith(".py")):
            raise CannotVouch(f"{shown(name)} is under {LISTS}/ and is not a list that is read: a list is a .py file in that folder itself")
    return copied


def text_of(path):
    """What a file holds, or None if it is not there or does not hold text."""
    try:
        return path.read_bytes().decode("utf-8") if path.is_file() else None
    except UnicodeDecodeError:
        return None


def places(text, part):
    """At how many places a part is found in a text, those that overlap counted too."""
    count, at = 0, text.find(part)
    while at != -1:
        count, at = count + 1, text.find(part, at + 1)
    return count


def plant(lab, fault):
    """Make a fault's edits in the lab -> what each file held before (None for a file the fault added).

    If one edit does not fit the lab as it stands, none is left in.
    """
    saved = {}
    for file, old, new in fault.edits:
        path = lab / file
        before = text_of(path)
        if old is None:
            why = "it is there already" if path.exists() or path.is_symlink() else "" if path.parent.is_dir() else "its folder is not there"
            why = why and f"{file} cannot be added: {why}"
        elif before is None:
            why = f"{file} is not a file of this repository that holds text"
        else:
            found = places(before, old)
            why = "" if found == 1 else f"the text to replace is found {found} times in {file}, and must be found once"
        if why:
            put_back(saved)
            raise CannotVouch(why)
        saved.setdefault(path, before)
        path.write_bytes((new if old is None else before.replace(old, new)).encode("utf-8"))
    return saved


def put_back(saved):
    """Take a fault out again: each file it changed holds what it held before, and a file it added is gone."""
    for path, text in saved.items():
        if text is None:
            path.unlink()
        else:
            path.write_bytes(text.encode("utf-8"))


def asked(lab, seconds, *args):
    """Run the child program in the lab -> what it answered, or None if it ended without an answer.

    The lab's own package and tests are the ones imported, whatever the caller's settings. The child reads nothing
    and what it prints goes nowhere: its answer comes in a file outside the lab. It leads a group of processes of
    its own, and when it ends, or its time is up (TimeoutExpired), everything still in that group is ended with it.
    """
    answer = lab.parent / "answer.json"
    answer.unlink(missing_ok=True)
    env = without_gits_own(os.environ, lab.parent)
    env.update(PYTHONPATH=os.pathsep.join([str(lab / "src"), str(lab / "tests")]), PYTHONDONTWRITEBYTECODE="1")
    child = subprocess.Popen([sys.executable, "-B", "-c", CHILD, str(answer), *args], cwd=lab, env=env, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        child.wait(timeout=seconds)
    finally:
        if hasattr(os, "killpg"):
            with contextlib.suppress(OSError):        # nothing is left in the group
                os.killpg(child.pid, signal.SIGKILL)
        child.kill()
        child.wait()
    try:
        return json.loads(answer.read_text(encoding="utf-8"))
    except OSError:
        return None


def suite_passes(lab):
    """Run the whole suite in the lab with no fault planted -> how many tests ran. Anything short of every test passing is refused."""
    refusal = "with no fault planted the tests must run and pass in the copy, or a failing test proves nothing: "
    try:
        said = asked(lab, SUITE_SECONDS, "suite", str(lab / "tests"))
    except subprocess.TimeoutExpired:
        raise CannotVouch(refusal + f"they did not end within {SUITE_SECONDS} seconds") from None
    if not isinstance(said, dict):
        raise CannotVouch(refusal + "the run ended without an answer")
    if said["failed"]:
        names = ", ".join(shown(name) for name in said["failed"]) + (f" and {said['others']} more" if said["others"] else "")
        raise CannotVouch(refusal + f"these did not pass there: {names}. The copy holds the files that git knows of or does not "
                          "ignore, and neither the .git folder nor a link")
    if not said["ran"]:
        raise CannotVouch(refusal + "no test was found there")
    return said["ran"]


def unfit(lab, faults):
    """Why each fault that cannot be tried cannot be: its text is not found once, or the test it names is not there."""
    problems = []
    for fault in faults:
        try:
            put_back(plant(lab, fault))
        except CannotVouch as error:
            problems.append(f"{fault.label}: {error}")
    try:
        missing = asked(lab, SECONDS, "names", *sorted({fault.test for fault in faults}))
    except subprocess.TimeoutExpired:
        missing = None
    if not isinstance(missing, list):
        raise CannotVouch("the tests could not be looked up by name in the copy")
    return problems + [f"{fault.label}: no such test: {fault.test}" for fault in faults if fault.test in missing]


def judged(lab, test):
    """Run one test in the lab -> (FAILED, PASSED, SKIPPED or None, and for None why nothing can be said)."""
    try:
        said = asked(lab, SECONDS, "run", test)
    except subprocess.TimeoutExpired:
        return None, f"did not end within {SECONDS} seconds"
    if said in (FAILED, PASSED, SKIPPED):
        return said, ""
    return None, "could not be loaded with the fault planted" if said == NOT_LOADED else "gave no verdict with the fault planted"


def untouched(root, lab, names):
    """Refuse a lab that is no longer, file for file, what was copied: a test wrote to it, and what it left may have failed another."""
    for name in names:
        if (lab / name).read_bytes() != (root / name).read_bytes():
            raise CannotVouch(f"{shown(name)} in the copy no longer matches the repository, so a test wrote to it or the "
                              "repository changed during the run")
    copied = set(names).union(*(map(str, PurePosixPath(name).parents) for name in names))
    for folder, folders, files in os.walk(lab):
        for name in sorted((Path(folder) / entry).relative_to(lab).as_posix() for entry in folders + files):
            if name not in copied:
                raise CannotVouch(f"{shown(name)} is in the copy and not in the repository, so a test left it there")


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
        tests = sorted({fault.test for fault in faults})
        weak = [test for test in tests if judged(lab, test)[0] not in (PASSED, SKIPPED)]
        if weak:                                      # under its fault each is run alone, and so would "kill" any fault at all
            raise CannotVouch("\n  ".join([f"{len(weak)} of the tests named did not pass when run alone with no fault planted, "
                                           "which is how each is run under its fault:", *weak]))
        print(f"no fault planted: each test named was run alone as well ({len(tests)} of them), and none failed", flush=True)
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
        untouched(root, lab, names)
    return counts[FAILED], counts[PASSED], counts[SKIPPED], counts[None]


def line_of(error):
    """The last line of this script that an error passed through."""
    line, step = 0, error.__traceback__
    while step is not None:
        if step.tb_frame.f_code.co_filename == __file__:
            line = step.tb_lineno
        step = step.tb_next
    return line


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
        with one_deeper():
            faults = [fault for fault in listed(root) if fault.label.startswith(only or "")]
            if not faults:
                raise CannotVouch(f"no fault's label begins with {shown(only)}")
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
    except OSError as error:                          # uncaught, Python would end with 1, which here means that a fault survived
        print(f"planted faults: cannot vouch: the copy could not be worked in ({type(error).__name__})", file=sys.stderr)
        return 2
    except Exception as error:                        # the same holds for a mistake of this script's own; what the error says is not printed
        print(f"planted faults: cannot vouch: the script itself failed ({type(error).__name__} at line {line_of(error)})", file=sys.stderr)
        return 2
    return 1 if survived else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):            # started with `>&-` there is no output at all, and nothing to set
        sys.stdout.reconfigure(errors="backslashreplace")  # a label the terminal cannot show is printed in escapes, and the run goes on
    for number in STOPS:
        signal.signal(number, stop)
    try:
        sys.exit(main())
    except Stopped as stopped:
        sys.exit(128 + stopped.args[0])
