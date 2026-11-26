# How changes here are reviewed

Changes to Wrong Person are built by an AI agent, an AI coding assistant working
under the owner's direction, and reviewed by other AI agents before they merge.
No agent reviews its own work. The owner merges. `CONTRIBUTING.md` says how a
change is reviewed in general; this page says what the reviewers look for in this
project in particular.

## Who the review guards against

Careless mistakes, and changes written by an AI that read well and are wrong. The
review is not built to stop a determined attacker. The project has one secret,
the pattern the private-word check looks for, and it is never handed to a run for
a pull request from a fork.

## What a change is judged against

The issue it closes, and the plan the owner approved for it. The plan is kept
outside the repository, so the pull request says what the change builds. Like
every change, it is also judged against the promises in `README.md`: computer
generated, not AI generated; proved solvable; AI use said plainly.

## What a reviewer must see

Beyond reading the change itself:

- "All checks" green on GitHub on the exact commit under review, with that run
  named in the pull request;
- every planted fault killed, with no test skipped: the `faults` job, which runs
  with `--no-skips`;
- the private-word check passing: the `private-words` job;
- the tests passing on every Python version that the `tests` job runs.

A check whose result a reviewer can neither see on GitHub nor get by running it
counts as not passed.

## The planted faults

The lists in `tools/faults/` hold the planted faults: small, wrong changes made on
purpose, each with the one test that must fail because of it. Every planted fault
must make its test fail, on every run. None is excused, and on GitHub none may be
skipped. `CONTRIBUTING.md` says how they are planted and how to add one.

## Releases

There are none yet. Nothing is tagged, and nothing is published as a package. A
rule for reviewing a release will come with the first one.

## The builder's log

The AI agent that builds a change keeps a log of every decision it makes, and
why. The log is kept outside the repository, with the plan.

## Where data comes in and goes out

Below is every way data comes in and goes out, with the files that do it.
`tests/test_review.py` fails when one of these is not named here: a Python or
JSON file anywhere in the package; a Python file anywhere in `tools/`, outside
the fault lists; a Python file at the top of the repository; a workflow, which
is a file directly in `.github/workflows/` ending in .yml or .yaml; or the
folder of fault lists. A file or folder whose name starts with a dot does not
count, nor does a `__pycache__` folder, and no other folder is looked in. The
test also fails when a file named here is not there, and when a name of the
package given here is not in the package. It reads only what is written in
backticks, and each of those must be a path, a name in the package written with
its module, or one of a few plain words that the test holds.

### The package, `src/wrong_person/`

It needs nothing outside Python's standard library. It prints nothing, writes no
file and uses no network. `src/wrong_person/__init__.py` holds nothing but a line
about the package; the rest is `src/wrong_person/engine.py`,
`src/wrong_person/wording.py` and the riddle table.

Comes in, from the program that calls it:

- names and a shape for a board: `engine.Board`;
- rules: `engine.Rule`, and a rule saved as a list: `engine.Rule.from_list`;
- the letter sets and the named people that clues may use: `engine.rule_space`;
- a saved case, which may have been saved by an earlier version:
  `engine.case_from_json`;
- a riddle table file, either the one shipped in `src/wrong_person/riddles.json`
  or one the caller names, which may have been written for an earlier version:
  `wording.load_riddles`;
- a riddle table already in memory: `wording.check_riddles`;
- riddle text: `wording.sentence` and `wording.arrest`.

What is wrong in what these are given is refused with a `ValueError` that says
what is wrong, or, for a riddle table in memory, listed by `wording.check_riddles`.
Something of the wrong kind altogether, such as a number where a list of names
belongs, can meet one of Python's own errors instead, and a riddle file that
cannot be opened raises Python's `OSError`. The engine's other functions that take
a board or rules, such as `engine.survivors` and `engine.audit`, take them as the
calls above made them and do not check them again.

Goes out, to the program that calls it:

- text for a printed page, from `wording.sentence` and `wording.arrest`, and the
  fixed lines `wording.NOTE` and `wording.RULES_TEXT`. A riddle holding a
  character that cannot go on a page is refused, and `wording.sentence`, which is
  told the name, also refuses a riddle that gives the name away;
- a case as JSON text, in plain ASCII: `engine.case_to_json`;
- error messages, which quote what they refuse. Most quote it in Python's own
  form, in quotes and with hidden characters written as escapes. A riddle table's
  problems also give each person's name as it is written, and
  `wording.load_riddles` begins its message with the file's name.

### The tools, `tools/`

Scripts for development, which the package never imports. What they print goes to
a terminal, or on GitHub to the run's log.

`tools/planted_faults.py` plants the faults.

- In: its arguments; the lists in `tools/faults/`, which are Python files that it
  runs; git's list of the repository's files, and the files themselves, which it
  copies; the environment, which it hands on to git and to the Python it starts,
  without git's own variables; and `PLANTED_FAULTS_DEPTH`, which it reads, and
  sets for what it starts.
- Out: it writes only in a temporary folder of its own, which it removes when it
  ends. It prints labels and the names of tests and files, never the text of an
  edit. A name from the disk or the command line is printed as it stands only if
  it is plain, and otherwise in quotes on one line, with `##[` broken up so that
  GitHub cannot take it as a command. A list's label or file name that holds
  `##[`, or a label that starts with `::`, is refused.

`tools/private_words.py` looks for the private words.

- In: the pattern, from the secret `PRIVATE_WORDS`; whether the pull request comes
  from a fork, from `PRIVATE_WORDS_FROM_FORK`; on GitHub, the file the runner
  writes the event to (`GITHUB_EVENT_PATH`), for the pull request's title,
  description and branch name, which anyone who opens a pull request can write;
  and, through git, every tracked file and its name, every commit's authors and
  message, and every version of every file and folder name that the history
  keeps. It reads no arguments and scans the repository it is started in. It
  hands git the environment without the pattern.
- Out: how many things it looked at and where a match is, never what matched. A
  name it prints is in quotes on one line, with `##[` broken up. For a pull
  request from a fork it prints a notice for GitHub that the scan was skipped. It
  writes no file.

`tools/mutation_floor.py` holds a mutation run to the floor.

- In: one optional argument, the name of the summary file that the mutation tool
  writes, and that file.
- Out: one sentence, which can quote a value from the summary in Python's own
  form. Unlike the other two scripts, it prints a file name it is given as it
  stands; on GitHub it is given none.

### The workflow, `.github/workflows/checks.yml`

- It runs for every pull request, from forks too, when it is opened, pushed to or
  reopened, and when its title or description is edited; and for every push to
  `main`.
- Its token can only read the repository.
- The secret goes to one step of the `private-words` job and nowhere else. GitHub
  gives no secret to a run for a pull request from a fork.
- It fetches the actions it uses, each pinned to one commit; Python itself; the
  development tools from the Python Package Index, each pinned to one version,
  though what they need in turn is not pinned; `setuptools`, at any version that
  `pyproject.toml` allows, to build the wheel; and, in the `private-words` job,
  the history behind the commit under test.
- Out: the run's log and its results. Nothing is uploaded, published or written
  back to the repository. What the tools leave behind (the `mutants` folder, the
  coverage data, the build folders) is ignored by git.

### Everything else

`pyproject.toml` holds the settings that pip, the build, coverage, pytest and
mutmut read. The tests in `tests/` read the files they check, run the example in
`README.md`, start git, bash and the tools, and write only in temporary folders of
their own. Python itself may leave `__pycache__` folders, which git ignores.
