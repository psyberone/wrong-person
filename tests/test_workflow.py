"""The checks that guard `main` are held by tests of their own.

`.github/workflows/checks.yml` decides what GitHub runs before a change merges,
with what rights, and which results count. One edit there can switch a check
off, or hand a pull request's words to a shell, and no other test would notice.
So the rules that file keeps are tested here, along with the two floors and the
Python versions that the pages state.

Much of this is a second copy on purpose: what each job runs is written out
below, so a change to it has to be made twice and cannot slip in by accident.

Standard library only, so there is no YAML parser. `read` below reads the small
part of YAML the workflow is written in and refuses everything else, so nothing
can hide in a piece of syntax that it skips.
"""
import importlib.util
import os
import re
import runpy
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CHECKS = WORKFLOWS / "checks.yml"
PYPROJECT = ROOT / "pyproject.toml"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
README = ROOT / "README.md"

# Each action the workflow may use, and the one commit of it that has been looked at. A tag can be moved to other
# code, and a hash alone could name a commit in someone's fork, so a new version is a change here as well as there.
ACTIONS = {"actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
           "actions/setup-python": ("6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", "v7.1.0")}
CHECKOUT = "actions/checkout@" + ACTIONS["actions/checkout"][0]
SETUP_PYTHON = "actions/setup-python@" + ACTIONS["actions/setup-python"][0]
FROM_A_FORK = "github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name != github.repository"
JOBS = ["tests", "coverage", "package", "mutation", "private-words", "faults", "all-checks"]
INSTALL = "python -m pip install --group dev"

# Every `${{ }}` in the file, by where it is. None is in a script, and the only ones in a step's `env` are the secret,
# a yes-or-no about forks, and the other jobs' results: nothing that a person typed.
EXPRESSIONS = {
    "concurrency.group": ["github.event.pull_request.number || github.sha"],
    "concurrency.cancel-in-progress": ["github.event_name == 'pull_request'"],
    "jobs.tests.name": ["matrix.python-version"],
    "jobs.tests.steps.1.with.python-version": ["matrix.python-version"],
    "jobs.private-words.steps.2.env.PRIVATE_WORDS": ["secrets.PRIVATE_WORDS"],
    "jobs.private-words.steps.2.env.PRIVATE_WORDS_FROM_FORK": [FROM_A_FORK],
    "jobs.all-checks.steps.0.env.TESTS": ["needs.tests.result"],
    "jobs.all-checks.steps.0.env.COVERAGE": ["needs.coverage.result"],
    "jobs.all-checks.steps.0.env.PACKAGE": ["needs.package.result"],
    "jobs.all-checks.steps.0.env.MUTATION": ["needs.mutation.result"],
    "jobs.all-checks.steps.0.env.PRIVATE_WORDS_JOB": ["needs.private-words.result"],
    "jobs.all-checks.steps.0.env.FAULTS": ["needs.faults.result"],
}

# What each job runs, step by step, to the letter.
COMMANDS = {
    "tests": ["python --version\n"
              "PYTHONPATH=src python -m unittest discover -s tests\n"],
    "coverage": [INSTALL,
                 "PYTHONPATH=src python -m coverage run -m unittest discover -s tests\n"
                 "python -m coverage report\n"],
    "package": [INSTALL,
                'python -m build --wheel --outdir "$RUNNER_TEMP/dist"',
                'python -m venv "$RUNNER_TEMP/clean"\n'
                '"$RUNNER_TEMP/clean/bin/python" -m pip install --no-index --no-deps "$RUNNER_TEMP"/dist/wrong_person-*.whl\n',
                'mkdir "$RUNNER_TEMP/apart"\n'
                'cp -R tests tools .github README.md CONTRIBUTING.md pyproject.toml "$RUNNER_TEMP/apart/"\n'
                'cd "$RUNNER_TEMP/apart"\n'
                "test ! -e src\n"
                "\"$RUNNER_TEMP/clean/bin/python\" - <<'PY'\n"
                "import pathlib, sys, wrong_person\n"
                "home = pathlib.Path(sys.prefix).resolve()\n"
                "found = pathlib.Path(wrong_person.__file__).resolve()\n"
                "if home not in found.parents:\n"
                '    sys.exit(f"the package came from {found}, not from the installed wheel in {home}")\n'
                'print(f"testing the installed package at {found}")\n'
                "PY\n"
                '"$RUNNER_TEMP/clean/bin/python" -m unittest discover -s tests\n'],
    "mutation": [INSTALL,
                 "python -m mutmut run\n"
                 "python -m mutmut export-cicd-stats\n",
                 "python tools/mutation_floor.py"],
    "private-words": ['git fetch --quiet --no-tags --depth=2147483647 origin "$(git rev-parse HEAD)"',
                      "python3 -I tools/private_words.py"],
    "faults": ["python3 tools/planted_faults.py --no-skips"],
    "all-checks": ["failed=0\n"
                   'for job in "tests $TESTS" "coverage $COVERAGE" "package $PACKAGE" "mutation $MUTATION" "private-words $PRIVATE_WORDS_JOB" '
                   '"faults $FAULTS"; do\n'
                   '  echo "$job"\n'
                   '  case "$job" in\n'
                   '    *" success") ;;\n'
                   "    *) failed=1 ;;\n"
                   "  esac\n"
                   "done\n"
                   'if [ "$failed" -ne 0 ]; then\n'
                   '  echo "::error title=All checks::a job did not succeed, so this change is not ready to merge"\n'
                   "fi\n"
                   'exit "$failed"\n'],
}


class NotRead(ValueError):
    """The text uses a piece of YAML that `read` does not know, or is not YAML at all."""


KEY = re.compile(r"(?P<key>[A-Za-z0-9_.-]+):(?: +(?P<rest>.*))?")


def read(text):
    """A workflow file as dicts, lists and strings.

    It knows `key: value`, a key with a nested block under it, a list of blocks
    (`- key: value`), a list on one line (`[a, b]`), a quoted word, a block of
    lines after `|`, and comments. Every value comes back as a string, so
    `false` is "false". It raises NotRead for anything else: a key said twice
    (YAML would quietly keep the last), an anchor, an alias, a tag, a `{}`
    mapping, folded text, a tab.
    """
    if "\t" in text:
        raise NotRead("a tab")
    lines = text.split("\n")
    start = past_blanks(lines, 0)
    if start == len(lines) or depth(lines[start]):
        raise NotRead("nothing at the left margin to begin with")
    value, at = block(lines, start, 0)
    if at != len(lines):
        raise NotRead(f"line {at + 1} does not follow from the lines above it")
    return value


def depth(line):
    return len(line) - len(line.lstrip(" "))


def past_blanks(lines, at):
    """The next line from here that is neither empty nor a comment."""
    while at < len(lines) and (not lines[at].strip() or lines[at].lstrip(" ").startswith("#")):
        at += 1
    return at


def block(lines, at, indent):
    """The mapping, or the list of mappings, whose lines begin this deep -> (it, the line it ends before)."""
    if lines[at][indent:].startswith("- "):
        items = []
        while at < len(lines) and depth(lines[at]) == indent and lines[at][indent:].startswith("- "):
            lines = lines[:at] + [" " * (indent + 2) + lines[at][indent + 2:]] + lines[at + 1:]    # the dash is two columns of the item
            item, at = block(lines, at, indent + 2)
            items.append(item)
        if at < len(lines) and depth(lines[at]) >= indent:
            raise NotRead(f"line {at + 1} is neither the next item of the list nor the end of it")
        return items, at
    mapping = {}
    while at < len(lines) and depth(lines[at]) == indent:
        said = KEY.fullmatch(lines[at][indent:])
        if not said:
            raise NotRead(f"line {at + 1} is not `key: value`")
        key, rest = said["key"], without_comment(said["rest"] or "", at)
        if key in mapping:
            raise NotRead(f"line {at + 1} says `{key}` a second time")
        at += 1
        if rest == "|":
            held = []
            while at < len(lines) and (not lines[at].strip() or depth(lines[at]) > indent):
                held.append(lines[at])
                at += 1
            while held and not held[-1].strip():
                held.pop()
            if not held or any(line.strip() and depth(line) < depth(held[0]) for line in held):
                raise NotRead(f"the block of text under `{key}` is empty or not evenly indented")
            mapping[key] = "".join(line[depth(held[0]):] + "\n" for line in held)
        elif rest:
            mapping[key] = value_of(rest, at)
        else:
            at = past_blanks(lines, at)
            if at == len(lines) or depth(lines[at]) <= indent:
                raise NotRead(f"`{key}` has nothing under it")
            mapping[key], at = block(lines, at, depth(lines[at]))
        at = past_blanks(lines, at)
    if at < len(lines) and depth(lines[at]) > indent:
        raise NotRead(f"line {at + 1} is indented more than the lines it follows")
    return mapping, at


def without_comment(rest, at):
    """What follows a key on its line, without any comment after it."""
    if rest[:1] in ('"', "'"):
        end = rest.find(rest[0], 1)
        after = rest[end + 1:]
        if end < 0 or (after.strip() and not (after.startswith(" ") and after.lstrip(" ").startswith("#"))):
            raise NotRead(f"line {at + 1} has a quoted word that does not end, or more after it")
        return rest[:end + 1]
    if rest.startswith("#"):
        return ""
    return rest.split(" #")[0].rstrip(" ")


def value_of(text, at):
    if text.startswith("["):
        if not text.endswith("]"):
            raise NotRead(f"line {at + 1} has a list that does not end")
        inside = text[1:-1].strip()
        return [word(item.strip(), at) for item in inside.split(",")] if inside else []
    return word(text, at)


def word(text, at):
    if text[:1] in ('"', "'"):
        if len(text) < 2 or text[-1] != text[0] or text[0] in text[1:-1] or "\\" in text:
            raise NotRead(f"line {at + 1} has a quoted word that this reader cannot read")
        return text[1:-1]
    if not text or text[0] in "&*!|>{}[]%@`,?" or ": " in text or text.endswith(":"):
        raise NotRead(f"line {at + 1} has a value that this reader does not know: {text!r}")
    return text


def everything_in(node, path=()):
    """Every value in what was read, however deep, with the keys that lead to it: ("jobs", "tests", "name"), value."""
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from everything_in(value, path + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from everything_in(value, path + (str(index),))


def table(text, name):
    """The lines of one table of pyproject.toml, without blank lines and comments."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("["):
            inside = line.strip() == f"[{name}]"
        elif inside and line.strip() and not line.lstrip().startswith("#"):
            lines.append(line.strip())
    return lines


def words_of(page):
    """A page's words with every run of spaces and line ends as one space, so that a sentence can be looked for across lines."""
    return " ".join(page.read_text(encoding="utf-8").split())


def load(script):
    """One of the scripts in tools/ as a module; they live outside the package, so they are loaded by path."""
    spec = importlib.util.spec_from_file_location(script.stem, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Reader(unittest.TestCase):
    """The small reader is what every test below stands on, so it is tested first."""

    def test_it_reads_what_the_workflow_is_written_in(self):
        text = ("# a comment at the top\n"
                "name: Checks\n"
                "\n"
                "on:\n"
                "  push:\n"
                "    # a comment in the middle\n"
                "    branches: [main, \"3.10\"]   # and one at the end of a line\n"
                "empty: []\n"
                "quoted: \"a # that is no comment\"   # but this is one\n"
                "plain: ${{ a || b }}\n"
                "steps:\n"
                "  - uses: one@two # v1\n"
                "    with:\n"
                "      keep: false\n"
                "  - name: Second\n"
                "    run: |\n"
                "      first line\n"
                "        # an indented line that is no comment\n"
                "\n"
                "      last line\n"
                "\n"
                "last: 'single'\n")
        self.assertEqual(read(text), {
            "name": "Checks", "on": {"push": {"branches": ["main", "3.10"]}}, "empty": [], "quoted": "a # that is no comment",
            "plain": "${{ a || b }}",
            "steps": [{"uses": "one@two", "with": {"keep": "false"}},
                      {"name": "Second", "run": "first line\n  # an indented line that is no comment\n\nlast line\n"}],
            "last": "single"})

    def test_it_refuses_what_it_does_not_know(self):
        for what, text in (("a key said twice", "a: 1\nb: 2\na: 3\n"),
                           ("a key said twice in a step", "steps:\n  - run: one\n    run: two\n"),
                           ("a tab", "a:\n\tb: 1\n"),
                           ("an anchor", "a: &here 1\n"),
                           ("an alias", "a: *here\n"),
                           ("a merge of another mapping", "a:\n  <<: *here\n"),
                           ("a tag", "a: !!str 1\n"),
                           ("a mapping on one line", "a: {b: 1}\n"),
                           ("folded text", "a: >\n  b\n"),
                           ("a block of text with its last line end cut", "a: |-\n  b\n"),
                           ("a block of text with nothing in it", "a: |\nb: 1\n"),
                           ("a block of text that steps back", "a: |\n    b\n  c\n"),
                           ("a list of plain words", "a:\n  - b\n  - c\n"),
                           ("a list beside its key", "a:\n- b: 1\n"),
                           ("a key with nothing under it", "a:\nb: 1\n"),
                           ("a key with nothing after it at all", "a:\n"),
                           ("a line that steps in for no reason", "a: 1\n  b: 2\n"),
                           ("a line that steps half-way back", "a:\n    b: 1\n  c: 2\n"),
                           ("a line that is not a key", "a: 1\njust words\n"),
                           ("a list item that steps half-way back", "a:\n  - b: 1\n   c: 2\n"),
                           ("a second value on a line", "a: b: c\n"),
                           ("a list that does not end", "a: [b, c\n"),
                           ("a quoted word that does not end", "a: \"b\n"),
                           ("more after a quoted word", "a: \"b\" c\n"),
                           ("a quote inside a quoted word", "a: [\"b\"c\"]\n"),
                           ("an escape in a quoted word", "a: [\"b\\n\"]\n"),
                           ("a second document", "a: 1\n---\nb: 2\n"),
                           ("a first line that is indented", "  a: 1\n"),
                           ("nothing", ""), ("only a comment", "# nothing\n")):
            with self.subTest(what=what), self.assertRaises(NotRead):
                read(text)


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CHECKS.read_text(encoding="utf-8")
        cls.checks = read(cls.text)
        cls.jobs = cls.checks["jobs"]

    def steps(self):
        return [(name, step) for name, job in self.jobs.items() for step in job["steps"]]

    def where(self, key):
        """Every place a key is used, as dotted paths."""
        return sorted(".".join(path) for path, _ in everything_in(self.checks) if path and path[-1] == key)

    def test_it_is_the_only_workflow(self):
        """A second file could run on other events, with other rights, and nothing here would be reading it."""
        self.assertEqual(sorted(path.name for path in WORKFLOWS.iterdir()), ["checks.yml"])
        self.assertEqual(sorted(path.name for path in WORKFLOWS.parent.iterdir()), ["workflows"])

    def test_it_holds_nothing_but_what_these_tests_read(self):
        """Each key that is allowed, by where it sits. A new one (`continue-on-error`, `shell`, `permissions`) is a failure here first."""
        self.assertEqual(list(self.checks), ["name", "on", "permissions", "concurrency", "defaults", "jobs"])
        self.assertEqual(list(self.jobs), JOBS)
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                allowed = {"name", "runs-on", "timeout-minutes", "steps", *{"tests": ["strategy"], "all-checks": ["if", "needs"]}.get(name, [])}
                self.assertEqual(set(job), allowed)
                self.assertEqual(job["runs-on"], "ubuntu-24.04")
        for name, step in self.steps():
            with self.subTest(job=name, step=step.get("name", step.get("uses"))):
                self.assertLessEqual(set(step), {"name", "uses", "with", "run", "env"})
                self.assertEqual(len({"uses", "run"} & set(step)), 1)

    def test_it_runs_for_pull_requests_and_for_main_and_for_nothing_else(self):
        """Not `pull_request_target`, which would run a stranger's change with this repository's secrets."""
        self.assertEqual(self.checks["on"], {"pull_request": {"types": ["opened", "synchronize", "reopened", "edited"]},
                                             "push": {"branches": ["main"]}})

    def test_the_token_can_only_read_the_repository(self):
        self.assertEqual(self.checks["permissions"], {"contents": "read"})
        self.assertEqual(self.where("permissions"), ["permissions"])                # no job gives itself more

    def test_a_newer_run_replaces_an_older_one_on_a_pull_request_only(self):
        self.assertEqual(self.checks["concurrency"], {"group": "checks-${{ github.event.pull_request.number || github.sha }}",
                                                      "cancel-in-progress": "${{ github.event_name == 'pull_request' }}"})

    def test_every_action_is_pinned_to_a_commit_that_has_been_looked_at(self):
        lines = [line.strip() for line in self.text.splitlines() if re.match(r" *(- )?uses:", line)]
        used = [step["uses"] for _, step in self.steps() if "uses" in step]
        self.assertEqual(len(lines), len(used))
        self.assertEqual(set(lines), {f"- uses: {name}@{commit} # {version}" for name, (commit, version) in ACTIONS.items()})
        self.assertEqual(set(used), {CHECKOUT, SETUP_PYTHON})
        for name, (commit, version) in ACTIONS.items():
            with self.subTest(action=name):
                self.assertRegex(commit, r"\A[0-9a-f]{40}\Z")
                self.assertRegex(version, r"\Av[0-9]+\.[0-9]+\.[0-9]+\Z")
        self.assertEqual(self.where("uses"), sorted(f"jobs.{name}.steps.{index}.uses" for name in JOBS[:-1]
                                                    for index in range(1 if name in ("private-words", "faults") else 2)))

    def test_every_checkout_drops_the_token_it_was_given(self):
        checkouts = [(name, step) for name, step in self.steps() if step.get("uses", "").startswith("actions/checkout@")]
        self.assertEqual([name for name, _ in checkouts], JOBS[:-1])                # the first step of every job that reads files
        for name, step in checkouts:
            with self.subTest(job=name):
                self.assertEqual(step, {"uses": CHECKOUT, "with": {"persist-credentials": "false"}})
                self.assertIs(step, self.jobs[name]["steps"][0])

    def test_python_is_set_up_from_the_matrix_or_at_one_version(self):
        for name in ("tests", "coverage", "package", "mutation"):
            with self.subTest(job=name):
                version = "${{ matrix.python-version }}" if name == "tests" else "3.14"
                self.assertEqual(self.jobs[name]["steps"][1], {"uses": SETUP_PYTHON, "with": {"python-version": version}})

    def test_nothing_a_person_typed_reaches_a_script_or_a_steps_environment(self):
        found = {}
        for path, value in everything_in(self.checks):
            if isinstance(value, str) and "${{" in value:
                found[".".join(path)] = [said.strip() for said in re.findall(r"\$\{\{(.*?)\}\}", value)]
                self.assertEqual(value.count("${{"), len(found[".".join(path)]), value)
        self.assertEqual(found, EXPRESSIONS)
        self.assertEqual(self.where("env"), ["jobs.all-checks.steps.0.env", "jobs.private-words.steps.2.env"])
        for name, step in self.steps():
            self.assertNotIn("${{", step.get("run", ""), name)
            self.assertNotIn("github.", step.get("run", ""), name)

    def test_the_job_that_is_given_the_secret_installs_nothing_and_runs_one_script_with_it(self):
        steps = [{key: value for key, value in step.items() if key != "name"} for step in self.jobs["private-words"]["steps"]]
        self.assertEqual(steps, [{"uses": CHECKOUT, "with": {"persist-credentials": "false"}},
                                 {"run": COMMANDS["private-words"][0]},
                                 {"env": {"PRIVATE_WORDS": "${{ secrets.PRIVATE_WORDS }}", "PRIVATE_WORDS_FROM_FORK": "${{ " + FROM_A_FORK + " }}"},
                                  "run": COMMANDS["private-words"][1]}])
        self.assertEqual([".".join(path) for path, value in everything_in(self.checks) if isinstance(value, str) and "secrets" in value],
                         ["jobs.private-words.steps.2.env.PRIVATE_WORDS"])

    def test_the_job_that_plants_the_faults_installs_nothing_and_lets_no_test_be_skipped(self):
        """On GitHub every fault's own test can run, so a test skipped there is a fault that nothing was seen to catch."""
        steps = [{key: value for key, value in step.items() if key != "name"} for step in self.jobs["faults"]["steps"]]
        self.assertEqual(steps, [{"uses": CHECKOUT, "with": {"persist-credentials": "false"}},
                                 {"run": "python3 tools/planted_faults.py --no-skips"}])

    def test_each_job_runs_exactly_these_commands(self):
        self.assertEqual({name: [step["run"] for step in job["steps"] if "run" in step] for name, job in self.jobs.items()}, COMMANDS)

    def test_a_failing_line_fails_its_step(self):
        """Named outright, `bash` is run by GitHub with -e and pipefail. No step picks another shell or forgives a failure."""
        self.assertEqual(self.checks["defaults"], {"run": {"shell": "bash"}})
        self.assertEqual(self.where("shell"), ["defaults.run.shell"])
        self.assertEqual(self.where("continue-on-error"), [])
        for name, step in self.steps():
            with self.subTest(job=name, step=step.get("name")):
                self.assertNotRegex(step.get("run", ""), r"\|\||set \+e|set \+o|;\s*true\b|&&\s*true\b|\|\s*true\b")

    def test_no_job_or_step_runs_only_sometimes_but_all_checks_runs_always(self):
        self.assertEqual(self.where("if"), ["jobs.all-checks.if"])
        self.assertEqual(self.jobs["all-checks"]["if"], "always()")
        self.assertEqual(self.where("needs"), ["jobs.all-checks.needs"])

    def test_all_checks_waits_for_every_other_job_and_is_told_each_result(self):
        last = self.jobs["all-checks"]
        self.assertEqual(last["name"], "All checks")                                # the name the protection on main waits for
        self.assertEqual(last["needs"], JOBS[:-1])
        self.assertEqual(len(last["steps"]), 1)
        self.assertEqual(list(last["steps"][0]["env"].values()), ["${{ needs." + name + ".result }}" for name in JOBS[:-1]])

    def test_all_checks_fails_unless_every_job_succeeded(self):
        """The step's own script, run here by bash as GitHub runs it, with each result a job can have."""
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("there is no bash here to run the step's script with")
        step = self.jobs["all-checks"]["steps"][0]
        results = list(step["env"])
        self.assertEqual(len(results), 6)

        def ends_with(**told):
            ran = subprocess.run([bash, "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]], capture_output=True, text=True,
                                 timeout=60, env={"PATH": os.environ["PATH"], **{name: "success" for name in results}, **told})
            return ran.returncode, ran.stdout
        status, said = ends_with()
        self.assertEqual(status, 0, said)
        self.assertEqual(said, "tests success\ncoverage success\npackage success\nmutation success\nprivate-words success\nfaults success\n")
        for name in results:
            for result in ("failure", "cancelled", "skipped", "", "success-ish", "successful", "Success"):
                with self.subTest(job=name, result=result):
                    status, said = ends_with(**{name: result})
                    self.assertEqual(status, 1, said)
                    self.assertIn("::error title=All checks::", said)
        status, said = ends_with(**{name: "skipped" for name in results})
        self.assertEqual(status, 1, said)

    def test_every_job_has_a_time_limit_and_the_scans_own_limit_on_git_is_well_inside_its_jobs(self):
        self.assertEqual({name: job["timeout-minutes"] for name, job in self.jobs.items()},
                         {"tests": "10", "coverage": "10", "package": "10", "mutation": "20", "private-words": "5", "faults": "10", "all-checks": "5"})
        self.assertLessEqual(2 * load(ROOT / "tools" / "private_words.py").GIT_SECONDS, 60 * int(self.jobs["private-words"]["timeout-minutes"]))

    def test_the_planted_faults_are_stopped_by_their_own_limits_before_their_jobs(self):
        """A run that hangs before its first fault is ended by the script, which says why, and not by GitHub, which does not."""
        script = load(ROOT / "tools" / "planted_faults.py")
        self.assertLess(script.GIT_SECONDS + script.SECONDS + script.SUITE_SECONDS, 60 * int(self.jobs["faults"]["timeout-minutes"]))

    def test_the_tests_run_on_every_python_the_pages_name(self):
        self.assertEqual(self.jobs["tests"]["strategy"], {"fail-fast": "false", "matrix": {"python-version": ["3.10", "3.11", "3.12", "3.13", "3.14", "3.15"]}})
        versions = self.jobs["tests"]["strategy"]["matrix"]["python-version"]
        row = re.search(r"^\| `tests` \| The tests pass on Python (.+), with nothing installed \|$", CONTRIBUTING.read_text(encoding="utf-8"), re.M)
        self.assertEqual(re.findall(r"[0-9]+\.[0-9]+", row[1]), versions)
        oldest = versions[0]
        self.assertIn(f'requires-python = ">={oldest}"', table(PYPROJECT.read_text(encoding="utf-8"), "project"))
        self.assertIn(f"The package needs nothing but Python {oldest} or newer.", words_of(CONTRIBUTING))
        self.assertIn(f"The package needs Python {oldest} or newer", words_of(README))


class Floors(unittest.TestCase):
    """The two floors, and the tools they are measured with, are what the pages say they are."""

    def setUp(self):
        self.settings = PYPROJECT.read_text(encoding="utf-8")
        self.contributing = words_of(CONTRIBUTING)

    def test_branch_coverage_of_the_package_is_held_to_85_per_cent(self):
        self.assertEqual([line for line in self.settings.splitlines() if "fail_under" in line], ["fail_under = 85"])
        self.assertIn("fail_under = 85", table(self.settings, "tool.coverage.report"))
        self.assertEqual(table(self.settings, "tool.coverage.run"), ["branch = true", 'source = ["wrong_person"]'])
        for elsewhere in (".coveragerc", "setup.cfg", "tox.ini"):                   # where coverage would look before pyproject.toml
            self.assertFalse((ROOT / elsewhere).exists(), elsewhere)
        self.assertIn("**Branch coverage at or above 85%.** The floor is in `pyproject.toml`.", self.contributing)
        self.assertIn("# branch coverage, which fails under 85%", self.contributing)
        self.assertIn("coverage, which must stay at or above 85%", words_of(README))

    def test_the_share_of_mutants_killed_is_held_to_80_per_cent(self):
        self.assertEqual(load(ROOT / "tools" / "mutation_floor.py").FLOOR, 80)
        self.assertIn("**At least 80% of mutants killed.**", self.contributing)
        self.assertIn("# mutation, which fails under 80% killed", self.contributing)

    def test_every_development_tool_is_pinned_to_one_version(self):
        group = table(self.settings, "dependency-groups")
        self.assertEqual(len(group), 1)
        self.assertRegex(group[0], r'\Adev = \[("[^"]+", )*"[^"]+"\]\Z')
        tools = re.findall(r'"([^"]+)"', group[0])
        self.assertEqual([tool.split("==")[0] for tool in tools], ["build", "coverage[toml]", "mutmut", "pytest"])
        for tool in tools:
            with self.subTest(tool=tool):
                self.assertRegex(tool, r"\A[a-z]+(\[[a-z]+\])?==[0-9]+(\.[0-9]+)+\Z")

    def test_the_tests_that_read_these_files_can_find_them_wherever_they_are_run(self):
        """mutmut runs the tests in a copy, and the package job runs them away from the source. Both must take these files along."""
        for needed in ('"README.md"', '"CONTRIBUTING.md"', '"pyproject.toml"', '"tools/"', '".github/"'):
            self.assertIn(needed, " ".join(table(self.settings, "tool.mutmut")), needed)
        self.assertIn('cp -R tests tools .github README.md CONTRIBUTING.md pyproject.toml "$RUNNER_TEMP/apart/"\n', COMMANDS["package"][3])

    def test_the_page_has_a_row_for_every_job(self):
        page = CONTRIBUTING.read_text(encoding="utf-8")
        table_of_jobs = page.split("\n## What GitHub runs\n", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(re.findall(r"^\| `([^`]+)` \| .+ \|$", table_of_jobs, re.M), [*JOBS[:-1], "All checks"])

    def test_the_page_gives_the_faults_jobs_command_for_a_contributor_to_run(self):
        """Without `--no-skips`: on a contributor's computer a test that cannot run there is passed over, and the page says so."""
        here = COMMANDS["faults"][0].replace(" --no-skips", "")
        self.assertEqual(here, "python3 tools/planted_faults.py")
        page = CONTRIBUTING.read_text(encoding="utf-8")
        self.assertIn("\n" + here + "\n", page)
        self.assertIn("On GitHub that fails the job (`--no-skips`)", words_of(CONTRIBUTING))

    def test_every_command_the_page_gives_for_the_planted_faults_is_one_the_script_takes(self):
        script = load(ROOT / "tools" / "planted_faults.py")
        commands = re.findall(r"^python3 tools/planted_faults\.py(.*)$", CONTRIBUTING.read_text(encoding="utf-8"), re.M)
        self.assertEqual(commands, ["", " --check", " --only MF"])
        for flag in re.findall(r"--[\w-]+", " ".join(commands)):
            self.assertIn(f"[{flag}", script.USAGE)
        labels = [fault[0] for path in sorted((ROOT / "tools" / "faults").glob("*.py")) for fault in runpy.run_path(str(path))["FAULTS"]]
        self.assertTrue(any(label.startswith("MF") for label in labels))
        self.assertEqual(script.SECONDS, 120)
        self.assertIn("**CANNOT SAY.** The test did not finish within two minutes", words_of(CONTRIBUTING))

    def test_the_page_gives_the_package_jobs_own_commands_for_a_contributor_to_run(self):
        """A contributor's own check must fail where GitHub's would.

        So the page gives every line the job runs after its install, in the same order, with a folder of the
        contributor's own for the runner's and `python3` for the runner's `python`. Two things the runner does are
        written out: it stops at the first line that fails (the brackets and `set -e`), and it starts from a fresh
        copy. A build leaves `build/` and an egg-info folder behind, and the next build packs what they remember,
        so without the `rm` a wheel could pass here with a file in it that GitHub's wheel would lack.
        """
        the_jobs = "".join(step if step.endswith("\n") else step + "\n" for step in COMMANDS["package"][1:])
        here = re.sub(r"(?m)^python ", "python3 ", the_jobs).replace("$RUNNER_TEMP", "$check")
        self.assertNotIn("RUNNER", here)
        self.assertEqual(here.count("python3 "), 2)
        block = '(\nset -e\nrm -rf build src/wrong_person.egg-info\ncheck="$(mktemp -d)"\n' + here + ")\n```\n"
        self.assertIn(block, CONTRIBUTING.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
