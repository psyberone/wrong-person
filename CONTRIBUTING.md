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

Both floors are measured on the package, `src/wrong_person`. The two scripts in
`tools/` have tests of their own, written first, and each was tried against
faults planted by hand; the pull request that added them says how many and what
became of each. Those lists are not in the repository yet;
[#6](https://github.com/psyberone/wrong-person/issues/6) is about moving lists
like them in.

## Running the checks

From the repository root. The first line installs the pinned tools and needs
pip 25.1 or newer. The tests themselves need only Python and git (2.28 or
newer): some of them build small throwaway repositories.

```console
python -m pip install --group dev

# the tests
PYTHONPATH=src python -m unittest discover -s tests

# branch coverage, which fails under 85%
PYTHONPATH=src python -m coverage run -m unittest discover -s tests
python -m coverage report

# mutation, which fails under 80% killed (writes a mutants/ folder, ignored by git)
python -m mutmut run
python -m mutmut export-cicd-stats
python tools/mutation_floor.py

# the package as it would be installed
python -m build --wheel
```

## What GitHub runs

On every pull request, again whenever its title or description is edited, and
on every push to `main` (`.github/workflows/checks.yml`):

| Job | What it proves |
| --- | --- |
| `tests` | The tests pass on Python 3.10, 3.11, 3.12, 3.13, 3.14 and 3.15, with nothing installed |
| `coverage` | Branch coverage is at or above the floor |
| `package` | The built wheel, installed alone into a clean environment and tested away from the source, passes the tests, so it carries its data file |
| `mutation` | The share of mutants killed is at or above the floor |
| `private-words` | None of the private words is anywhere a visitor could read (see below) |
| `All checks` | Every job above succeeded; this is the one a merge waits for |

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

- The check reads every tracked file and its name, who made each commit and its
  message, every version of every file the history keeps (so a word that was
  committed and later taken out still counts), and the pull request's title,
  description and branch name.
- If it fails on your change, the log says where (a file, a commit, or an object
  in the history) and never what matched. The maintainer will point you to the
  line.
- A secret is not given to pull requests from forks, so there the job says
  "skipped" and the change is checked by hand before it merges.
- It does not read other branches, tags, issues or comments.
- Without the pattern the script has nothing to look for, so only GitHub and the
  maintainer can run it for real. Its tests use a stand-in pattern and run
  anywhere.
