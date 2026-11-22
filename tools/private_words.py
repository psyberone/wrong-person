"""Look for the private words in everything a visitor to the repository could read.

A short private list of words must never appear here. The list is not in the
repository: it reaches this script as one pattern (a Python regular expression,
matched whatever the case) in the environment variable PRIVATE_WORDS. Run from
the repository root:

    PRIVATE_WORDS='...' python3 tools/private_words.py

It looks in four places:

- every tracked file as it is in the folder: its name and what it holds;
- every commit that HEAD reaches: who made it and its message;
- every version of every file, and every folder's list of names, that those
  commits keep, so a word that was committed and later taken out is still found;
- when given, a pull request's title, body and branch name (PRIVATE_WORDS_TITLE,
  PRIVATE_WORDS_BODY, PRIVATE_WORDS_BRANCH).

It does not look at other branches, tags, issues or comments.

It says how many it looked at and where a match is, and never what matched: not
the word, not the line, not the pattern. It ends with 0 when nothing was found,
1 when something was, and 2 when it cannot vouch for the repository (no pattern,
a pattern that cannot be used, no repository, or a history cut short).

A pull request from a fork is not given the pattern. Only then, when
PRIVATE_WORDS_FROM_FORK is "true", a missing pattern is a skip that says so, not
a failure. A development tool: the package never imports it.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PULL_REQUEST = (("the title", "PRIVATE_WORDS_TITLE"), ("the body", "PRIVATE_WORDS_BODY"), ("the branch", "PRIVATE_WORDS_BRANCH"))
EACH_COMMIT = "--format=%x00%H%x00%an%n%ae%n%cn%n%ce%n%B"     # NUL, hash, NUL, then who made it and its message
HASH = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?")           # an object's full name, in either of git's two lengths


class CannotVouch(Exception):
    """The scan could not be made, so it must not read as a pass."""


def searcher(pattern):
    """The private pattern as a function that says whether a text holds a match.

    A CannotVouch from here never repeats the pattern or any part of it.
    """
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except (re.error, RecursionError, OverflowError):
        raise CannotVouch("the private pattern is not a valid pattern") from None
    if compiled.search(""):
        raise CannotVouch("the private pattern matches everything, even nothing at all, so it cannot be what was meant")
    return lambda text: compiled.search(text) is not None


def git(repo, *args, stdin=None):
    """What a git command printed, as bytes, or a CannotVouch if git would not run it.

    Replacements are switched off: `git replace` shows this machine another
    object in an object's place, and a visitor to GitHub sees the real one.
    """
    try:
        done = subprocess.run(["git", "--no-replace-objects", *args], cwd=repo, input=stdin, capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        raise CannotVouch("git could not be run here") from None
    if done.returncode:
        raise CannotVouch("git could not read this folder as a repository with at least one commit")
    return done.stdout


def text_of(data):
    """Bytes as text, whatever they are: bytes that are not UTF-8 are kept as marks, not dropped."""
    return data.decode("utf-8", errors="replace")


def tracked_files(repo, holds):
    """Every tracked file -> (how many, the ones that match as printable labels).

    A file matches on its name or on what it holds. A link is read as the place
    it points to and is never followed. A name that matches is withheld, since
    printing it would print the word.
    """
    names = [text_of(name) for name in git(repo, "ls-files", "-z").split(b"\0") if name]
    matching = []
    for name in names:
        path = Path(repo) / name
        if holds(name):
            matching.append("(a file whose own name matches; name withheld)")
        elif path.is_symlink():
            if holds(os.readlink(path)):
                matching.append(json.dumps(name))
        elif path.is_file():
            if holds(text_of(path.read_bytes())):
                matching.append(json.dumps(name))
        else:
            raise CannotVouch("git lists a tracked file that is not in the folder, so the working copy is not whole")
    return len(names), matching


def commits(repo, holds):
    """Every commit HEAD reaches -> (how many, the short hashes of the ones that match).

    A commit matches on who wrote it, who committed it, or its message. Each one
    comes back as a NUL, its hash, another NUL and that text; none of those can
    hold a NUL of its own. If the pieces are ever not hash, text, hash, text,
    the scan refuses to vouch.
    """
    if text_of(git(repo, "rev-parse", "--is-shallow-repository")).strip() != "false":
        raise CannotVouch("this is a shallow clone: its history is cut short, so most commits cannot be read")
    pieces = git(repo, "log", "--no-show-signature", EACH_COMMIT, "HEAD").split(b"\0")
    hashes, written = [text_of(piece) for piece in pieces[1::2]], pieces[2::2]
    if pieces[0].strip() or len(hashes) != len(written) or not all(HASH.fullmatch(commit) for commit in hashes):
        raise CannotVouch("git's history did not come back commit by commit")
    return len(hashes), [commit[:10] for commit, text in zip(hashes, written) if holds(text_of(text))]


def names_listed(folder, hash_length):
    """The names in a folder's list as git stores it: for each, its mode, a space, the name, a NUL, the raw hash.

    Only the names are a person's words. A ValueError means the list is not in that form.
    """
    names, at = [], 0
    while at < len(folder):
        name_ends = folder.index(b"\0", at)
        names.append(folder[folder.index(b" ", at, name_ends) + 1:name_ends])
        at = name_ends + 1 + hash_length
    if at != len(folder):
        raise ValueError("the last hash is cut short")
    return names


def kept_files(repo, holds):
    """Every version of every file, and every folder's list, that the history keeps -> (how many, the ones that match).

    Each object is read whole and as it is stored, so nothing git is set to do
    can leave one out; a patch, for one, leaves out any file git takes as binary.
    A file matches on what it held, and a folder on a name it listed. Commits are
    passed over: commits() has read their words, and the rest of a commit is
    git's own hashes and dates, which a number in the pattern must never match by
    chance, since no later commit could put that right.
    """
    asked = git(repo, "rev-list", "--objects", "--no-object-names", "HEAD").split()
    answer = git(repo, "cat-file", "--batch", stdin=b"\n".join(asked) + b"\n")
    looked_at, matching, at = 0, [], 0
    try:
        for name in asked:                                  # each comes back as "<name> <kind> <size>", a line end,
            first_line_ends = answer.index(b"\n", at)       # that many bytes, and one more line end
            named, kind, size = answer[at:first_line_ends].split(b" ")
            if named != name or not size.isdigit():
                raise ValueError("not the object that was asked for, or no size")
            begins, ends = first_line_ends + 1, first_line_ends + 1 + int(size)
            if answer[ends:ends + 1] != b"\n":
                raise ValueError("the object is not as long as its size")
            held, at, short = answer[begins:ends], ends + 1, text_of(name)[:10]
            if kind == b"blob":
                found = holds(text_of(held)) and f"what a file held (its commits: git log --all --find-object={short})"
            elif kind == b"tree":
                listed = names_listed(held, len(name) // 2)
                found = any(holds(text_of(one)) for one in listed) and f"a folder that lists a name that matches (its list: git cat-file -p {short})"
            elif kind == b"commit":
                continue
            else:
                raise ValueError("a kind of object the scan does not know")
            looked_at += 1
            if found:
                matching.append(f"object {short}: {found}")
        if at != len(answer):
            raise ValueError("more came back than was asked for")
    except ValueError:
        raise CannotVouch("git's objects did not come back whole, one for each one asked for") from None
    return looked_at, matching


def pull_request(environ, holds):
    """The pull request's title, body and branch, where given -> (how many, which ones match)."""
    given = [(label, environ[name]) for label, name in PULL_REQUEST if environ.get(name)]
    return len(given), [label for label, text in given if holds(text)]


def main(environ=None, repo="."):
    """Scan the repository in the current folder -> the exit status."""
    environ = os.environ if environ is None else environ
    pattern = environ.get("PRIVATE_WORDS", "").strip()
    try:
        if not pattern:
            if environ.get("PRIVATE_WORDS_FROM_FORK") == "true":
                print("::notice title=private-words::skipped: a pull request from a fork is not given the private pattern, "
                      "so this change is checked by hand before it merges")
                print("private words: skipped (no pattern for a fork)")
                return 0
            raise CannotVouch("no pattern: PRIVATE_WORDS is not set, and only a pull request from a fork may go without it")
        holds = searcher(pattern)
        report = (("tracked files", tracked_files(repo, holds)), ("commits", commits(repo, holds)),
                  ("files and folders in the history", kept_files(repo, holds)), ("pull request", pull_request(environ, holds)))
    except CannotVouch as problem:
        print(f"private words: the scan cannot vouch for this repository: {problem}", file=sys.stderr)
        return 2
    found = False
    for what, (looked_at, matching) in report:
        print(f"{what}: {len(matching)} of {looked_at} match")
        for where in matching:
            print(f"  - {where}")
        found = found or bool(matching)
    if found:
        print("private words: FOUND. The lines above say where. What matched is never printed.")
        return 1
    print("private words: none found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
