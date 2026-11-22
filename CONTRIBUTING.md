# Contributing to Wrong Person

Wrong Person is a hobby project, built in the open. This page says what standard
the code is held to, how to run the checks, and how a change is reviewed.

The easiest way to help needs no code at all: riddles for the place you live
([#19](https://github.com/psyberone/wrong-person/issues/19)) and advice on
translations ([#20](https://github.com/psyberone/wrong-person/issues/20)).

## What the project promises

The README states these in full. Every change is judged against them.

- **Computer generated, not AI generated.** Puzzles are to be put together and
  checked by an ordinary program that follows fixed rules, and no AI may take
  part in making one.
- **Proved solvable.** No puzzle may be printed until the engine has proved that
  exactly one name fits every clue and that every clue is needed.
- **AI use is said plainly.** The code, the tests and these pages are written
  with an AI coding assistant under the author's direction. Each commit made
  that way ends with a co-author line that says so, and so should yours if you
  work the same way.

## The quality bar

1. **Branch coverage at or above 85%.** The floor is in `pyproject.toml`.
2. **At least 80% of mutants killed.** A mutant is one small fault planted in
   the code by `mutmut`; a mutant is killed when a test fails because of it.
   The floor is in `tools/mutation_floor.py`.
3. **Tests first.** A test is seen to fail before the code that makes it pass.
4. **Both paths.** Every behaviour has a test of what is accepted and a test of
   what is refused.
5. **Coverage is not test quality.** A refusal is tested on the whole of what it
   refuses, and a planted fault must make a test fail. Both floors can be met by
   tests that check very little; they are a minimum, not the aim.
6. **Code that explains itself,** with docstrings for what it cannot.
7. **Standard library only.** The package needs nothing but Python 3.10 or
   newer. The tools below are for development and are never imported by it.

Both floors are measured on the package, `src/wrong_person`. The scripts in
`tools/` have tests of their own, written first, and so do the rules that the
workflow file keeps (`tests/test_workflow.py`). `mutmut` does not reach those,
so each was tried against faults planted by hand. The faults are kept in
`tools/faults/` and planted again on every pull request
([below](#the-planted-faults)).

## Running the checks

From the repository root. The first line installs the pinned tools and needs
pip 25.1 or newer. A virtual environment (`python3 -m venv .venv`, then
`. .venv/bin/activate`) keeps those tools apart from the rest of your computer.
The tests themselves need only Python and git (2.28 or newer): some of them
build small throwaway repositories.

```console
python3 -m pip install --group dev

# the tests
PYTHONPATH=src python3 -m unittest discover -s tests

# branch coverage, which fails under 85%
PYTHONPATH=src python3 -m coverage run -m unittest discover -s tests
python3 -m coverage report

# mutation, which fails under 80% killed (writes a mutants/ folder, ignored by git)
python3 -m mutmut run
python3 -m mutmut export-cicd-stats
python3 tools/mutation_floor.py

# the planted faults: each goes into a copy of the repository, and the test it
# names must fail (needs nothing installed; more about it below)
python3 tools/planted_faults.py

# the package as it would be installed: the wheel is built, installed alone into
# a clean environment, and tested away from the source
(
set -e
rm -rf build src/wrong_person.egg-info
check="$(mktemp -d)"
python3 -m build --wheel --outdir "$check/dist"
python3 -m venv "$check/clean"
"$check/clean/bin/python" -m pip install --no-index --no-deps "$check"/dist/wrong_person-*.whl
mkdir "$check/apart"
cp -R tests tools .github README.md CONTRIBUTING.md pyproject.toml "$check/apart/"
cd "$check/apart"
test ! -e src
"$check/clean/bin/python" - <<'PY'
import pathlib, sys, wrong_person
home = pathlib.Path(sys.prefix).resolve()
found = pathlib.Path(wrong_person.__file__).resolve()
if home not in found.parents:
    sys.exit(f"the package came from {found}, not from the installed wheel in {home}")
print(f"testing the installed package at {found}")
PY
"$check/clean/bin/python" -m unittest discover -s tests
)
```

The last block is what the `package` job runs, line for line, with a folder of
your own in place of the runner's. The brackets and `set -e` stop it at the
first line that fails, as the runner does. The `rm` is there because GitHub
starts from a fresh copy and your folder does not: a build leaves `build/` and
`src/wrong_person.egg-info/` behind (git ignores both), and the next build packs
what they remember, so a wheel could pass here with a file in it that GitHub's
wheel would lack. Building the wheel alone proves little: the job is there for
a wheel that builds and then lacks its data file.

If you change `.github/workflows/checks.yml`, run
[`actionlint`](https://github.com/rhysd/actionlint) on it by hand as well. It is
not one of the checks.

## The planted faults

A planted fault is one small, wrong change made on purpose (a hand-written
mutant): a comparison turned round, a check left out, a line taken out of the
workflow. If no test fails with the fault in place, the tests are not holding
that behaviour. `mutmut` plants faults of its own, but only in the package. The
lists under `tools/faults/` hold more than four hundred written by hand, for
the package and for everything `mutmut` does not reach.

| List | Where its faults are planted |
| --- | --- |
| `package.py` | The package, its riddle table and the README's example |
| `checks.py` | The scan, the mutation floor, the workflow, `pyproject.toml` and this page |
| `runner.py` | The script that plants the faults |

Where they came from: AI reviewers planted most of them while reviewing the
first pull requests, to see whether the tests would notice, and the AI coding
assistant planted the rest while writing the fixes. They were kept outside the
repository until [#6](https://github.com/psyberone/wrong-person/issues/6).

Each fault is a label, the full name of the one test meant to catch it, and one
or more edits. `python3 tools/planted_faults.py` copies the repository to a
scratch folder and sees that the whole suite passes there. Then, for each
fault, it makes the edits in the copy, runs the test the fault names, and takes
the edits out again. Your own files are never changed. It needs only Python and
git, and takes a few minutes. Each fault ends as one of four things:

- **killed.** The test it names ran and failed. This is what should happen.
- **SURVIVED.** The test passed with the fault in place. The run fails.
- **skipped here.** The test was skipped on this computer, so nothing was
  learned. On GitHub that fails the job (`--no-skips`); on your computer it is
  passed over. On a Mac one fault is skipped: its test needs a file name that
  is not UTF-8, and a Mac's disk refuses to hold one.
- **CANNOT SAY.** The test did not finish within two minutes, could not be
  loaded, or never got to run. The run fails.

```console
# only see that every fault still fits; runs no test and takes a second
python3 tools/planted_faults.py --check

# only the faults whose label begins with MF
python3 tools/planted_faults.py --only MF
```

**"Cannot be planted."** Before any test runs, the script sees that every fault
still fits: the text each edit replaces must be found exactly once in its file,
and the test it names must be there. If your change touches a line that a fault
points at, or renames a test that a fault names, the run stops and lists every
fault that no longer fits. Aim each one at the new line, in the same pull
request. Never delete a fault to get a green run.

**Adding one.** New behaviour wants a fault as well as a test. Add an entry to
the list that fits:

```python
("MF30 the floor is not checked at all",
 "test_tools.Verdict.test_a_run_just_under_the_floor_fails",
 [("tools/mutation_floor.py", "the text to replace", "what replaces it")]),
```

The first word of the label must be unlike every other fault's. Take enough of
the line that the text is found only once. `None` in place of the text to
replace adds a file that is not there. Then run it alone with `--only` and see
it killed. A fault must leave its test able to run and to finish: one that
makes the test wait for ever, or breaks what the test sets up first, cannot be
judged.

A fault must be killed on every run, not on most. If what it breaks depends on
chance, such as the order Python walks a set in, which changes from one run to
the next, a test that compares one order with another will pass now and then.
Name a test that takes the chance away. For the package that is
`test_same_inputs_same_answer_in_every_run`, which runs the code under three
fixed hash seeds.

A Mac's disk does not tell capital letters from small ones in a file name. A
fault that only changes the case of a file name can survive there and be killed
on GitHub.

**Three faults from the reviews are not in the lists,** because no one test can
be named for them:

- One, in the scan, changes nothing that can be seen: the same input is refused
  in the same words, by another route.
- One writes the workflow in a form its own tests cannot read, so all of them
  stop before they start and none of them can be named. The same fault in a form
  they can read is in the list (X19).
- One leaves the riddle table out of the built package. No test can see that,
  because the tests read the table from the source. The `package` job is there
  for exactly this, and it was run against the fault.

## What GitHub runs

On every pull request, again whenever its title or description is edited, and
on every push to `main` (`.github/workflows/checks.yml`):

| Job | What it proves |
| --- | --- |
| `tests` | The tests pass on Python 3.10, 3.11, 3.12, 3.13, 3.14 and 3.15, with nothing installed |
| `coverage` | Branch coverage is at or above the floor |
| `package` | The built wheel, installed alone into a clean environment and tested away from the source, passes the tests, so it carries its data file |
| `mutation` | The share of mutants killed is at or above the floor |
| `private-words` | The scan finds none of the private words in the files, in the history behind the change, or in the pull request's own words (below: what it reads and what it does not) |
| `faults` | Each planted fault makes the test it names fail, and none of those tests was skipped |
| `All checks` | Every job above succeeded; this is the one a merge waits for |

`tests/test_workflow.py` holds what each job runs and the rules the workflow
keeps (what starts it, what its token may do, which actions it uses and at
which commit). A change to the workflow fails the tests until it is made there
as well.

## When a check fails

- **`tests`, `coverage`, `package` or `mutation`.** Run the same commands here
  (above), fix the change, and push again. Each push starts a new run.
- **A failure that is not about your change**, such as a tool that could not be
  downloaded or a job cut off by its time limit. Run the job again: "Re-run
  failed jobs" on the run's page, for anyone who may write to the repository.
  Otherwise ask the maintainer.
- **`private-words` names the pull request's title, description or branch.**
  Take the word out: an edit for the title or the description (an edit starts
  a new run by itself), a new branch and a new pull request for a branch name.
- **`private-words` names a file, a commit, or an object in the history.** A
  later commit cannot clear it. A file that holds the word was committed, so
  the run names the file and an object in the history as well, and a new
  commit that takes the word out clears only the first of the two. The
  earlier commit is still part of the branch and still holds the word, so the
  branch has to be made again without that commit and pushed in place of the
  old one. Ask the maintainer first.
- **`private-words` says it cannot vouch.** Nothing was found: the scan could
  not be made, and the one sentence it prints says why.
- **`faults` says a fault SURVIVED.** The test it names passed with the fault
  in place, so something that test was holding is no longer held. Plant that one
  fault here (`python3 tools/planted_faults.py --only` and its label) and make
  the test hold it again. If the fault is killed when you run it again, and no
  line it touches was changed, what it breaks depends on chance, and it names
  the wrong test ([above](#the-planted-faults)).
- **`faults` says it cannot vouch.** Most often a fault cannot be planted: the
  change touched the line it points at, or renamed its test. The run names each
  one; aim it at the new line ([above](#the-planted-faults)). It also says so
  when a test that a fault names was skipped on GitHub, or could not be judged.
- **`All checks` is red.** It is red whenever another job failed, was stopped,
  was skipped or ran out of time. It prints each job's result; look at the job
  that did not succeed.

For the maintainer:

- **The secret** is a repository secret named `PRIVATE_WORDS`: one Python
  regular expression on one line, its alternatives joined with `|`, matched
  whatever the case. A number in it is fenced so that it matches only as a
  whole number, not inside a longer run of letters and digits. GitHub never
  shows a secret again, so it is never read back or edited: it is built again
  from the list and set again (`gh secret set PRIVATE_WORDS`, with the value
  piped in). The value is never printed and never written to a file in the
  repository.
- **A red `main`.** With the protection on `main`, nothing reaches it but a
  pull request whose `All checks` is green, so a red `main` is put right the
  same way, by a pull request. The one case that cannot be: a match in
  `main`'s own history, which every branch carries. Then either the history is
  rewritten, with the protection lifted for that one push, or the pattern is
  wrong and is set again.
- **A pull request from a fork** is not given the secret, so its
  `private-words` job searches for nothing: it says "skipped" and passes.
  Before merging it, fetch it and check it out
  (`git fetch origin pull/<number>/head`, then `git switch --detach FETCH_HEAD`).
  Put `main`'s copy of the scan somewhere outside the repository
  (`git show main:tools/private_words.py > "$copy"`, for a path of your own) and
  run that copy there, `python3 -I "$copy"`, with `PRIVATE_WORDS` in the
  environment. Never run the fork's own copy with the secret: the fork may have
  changed it. Read the title, the description and the branch name yourself:
  away from GitHub the scan has no pull request to read.

## How a change is reviewed

- A change is a branch and a pull request. Nothing goes straight to `main`.
- Before it merges, it is reviewed against five gates: security and authority,
  correctness and state, robustness and recovery, the strength of the evidence,
  and whether every statement matches the code.
- **The reviewers are AI agents.** Each works in its own copy of the exact
  commit, and none of them wrote the change. Their findings are graded, and the
  pull request records what was found and what was done about it.
- After a fix, the same reviewers answer a closed question: is each finding
  fixed, and did the fix break anything. It is not a new hunt.
- The owner merges, and only once the review is clear.

## The private word list

A short private list of words must never appear in this repository: not in a
file, not in a commit message, not in a pull request. The list itself is not in
the repository. GitHub checks for it with `tools/private_words.py` and a pattern
held as a repository secret.

- **What the check reads.** Every tracked file and its name, with its folders.
  Who wrote and who committed each commit behind the change, and its message.
  Every version of every file that those commits keep, and every file and
  folder name, so a word that was committed and later taken out still counts.
  The pull request's title, description and branch name.
- **What it does not read.** Other branches, and tags. The commits of a pull
  request that was closed without being merged, and the earlier wordings of a
  title or description that was edited. Issues and comments. The signature of
  a signed commit, and a signed tag's own words, where a commit merged one.
  Text that is not UTF-8, except that UTF-16
  and UTF-32 are read for words in plain letters. Compressed files, office
  documents, PDFs and images. Submodules, and files kept in Git LFS. A word in
  any of these has to be caught by a person.
- **A red run means the word is already public.** The check runs after the
  push, so GitHub already holds the commit, the title or the branch name, and
  it keeps them: the commits of a closed pull request and the earlier wordings
  of a title stay readable. Making the check green again takes nothing off
  GitHub. Tell the maintainer, who decides what has to be removed; some of it
  only GitHub's own support can remove.
- If it fails on your change, the log says where (a file, a commit, an object
  in the history, or the pull request's title, description or branch) and never
  what matched. The maintainer will point you to the line.
- A secret is not given to pull requests from forks, so there the job says
  "skipped" and the change is checked by hand before it merges.
- Without the pattern the script has nothing to look for, so only GitHub and the
  maintainer can run it for real. Its tests use a stand-in pattern and run
  anywhere.
