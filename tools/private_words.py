"""Look for the private words in what this repository makes public.

A short private list of words must never appear here. The list is not in the
repository: it reaches this script as one pattern (a Python regular expression
on one line, matched whatever the case) in the environment variable
PRIVATE_WORDS. Run from anywhere inside the repository:

    PRIVATE_WORDS='...' python3 tools/private_words.py

What it reads:

- every tracked file as it is in the folder: its name, with its folders, and
  what it holds. A link is read as the place it points to and is never
  followed. A submodule is read by its name only;
- every commit that HEAD reaches: who wrote it, who committed it and its
  message, after any full-length hash in them has been cut out;
- every version of every file that those commits keep, and every folder's list
  of names, each name read alone and with the folders above it. So a word that
  was committed and later taken out is still found;
- on GitHub, when a pull request started the run, its title, description and
  branch name. They are read from the file the runner writes the event to
  (GITHUB_EVENT_PATH), and are never handed over in the step's environment,
  because the runner prints every value given that way into its log.

Bytes are read as UTF-8. Bytes with NULs among them are read a second time with
the NULs taken out, which finds a word in plain letters written as UTF-16 or
UTF-32.

What it does not read, though a visitor to GitHub can:

- other branches, and tags;
- the commits of a pull request that was closed without being merged, and the
  earlier wordings of a title or description that was edited;
- issues and comments;
- inside a commit, the headers that git's own tools add: the signature of a
  signed commit, and the name, tagger and message of a signed tag that the
  commit merged;
- text in any encoding but UTF-8, beyond what is said above of UTF-16 and UTF-32;
- compressed files, office documents, PDFs and images;
- the files of a submodule, and files kept in Git LFS.

It says how many it looked at and where a match is, and never what matched: not
the word, not the line, not the pattern. It ends with 0 when nothing was found
and with 1 when something was. It ends with 2, and one sentence, when it cannot
vouch for the repository:

- there is no pattern, or it is on more than one line, or it did not reach
  Python as text, or Python cannot compile it or warns about it, or it matches
  everything;
- git cannot be run, does not answer within GIT_SECONDS, or fails;
- the folder is in no repository, or the repository has no commit, or it is a
  shallow clone or has a grafts file, either of which hides part of the history;
- a tracked file is missing from the folder or cannot be read;
- git answers in a form the scan does not know;
- the event file cannot be read;
- an error happens that the scan did not foresee.

A pull request from a fork is not given the pattern. Only then, when
PRIVATE_WORDS_FROM_FORK is "true", a missing pattern is a skip that says so, not
a failure. A development tool: the package never imports it.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import warnings
from pathlib import Path

GIT_SECONDS = 60                                              # what one git command may take; the job on GitHub has five minutes
EACH_COMMIT = "--format=%x00%H%x00%an%n%ae%n%cn%n%ce%n%B"     # NUL, hash, NUL, then who made it and its message
HASH = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?")           # an object's full name, in either of git's two lengths
A_HASH_IN_WORDS = re.compile(r"(?<![0-9a-f])(?:[0-9a-f]{64}|[0-9a-f]{40})(?![0-9a-f])")      # one standing alone in a text
WHOLE = re.compile(rb"(?P<head>[0-9a-f]{40}(?:[0-9a-f]{24})?)\n(?P<shallow>true|false)\n(?P<grafts>.+)\n", re.DOTALL)
FOLDER, SUBMODULE = 0o40000, 0o160000                         # the modes git gives a folder and a submodule
A_FILE = "what a file held (its commits: git log --all --find-object={0})"
BY_NAME = "a folder that lists a name that matches (its list: git cat-file -p {0})"
BY_PATH = "a folder that lists a name that matches when read with the folders above it (its list: git cat-file -p {0})"


class CannotVouch(Exception):
    """The scan could not be made, so it must not read as a pass."""


def searcher(pattern):
    """The private pattern as a function that says whether a text holds a match.

    A CannotVouch from here is one of three fixed sentences and never repeats
    the pattern or any part of it. What Python says about a pattern often quotes
    the pattern, in a warning as much as in an error, so a warning is refused
    like an error and nothing of either is kept.
    """
    if "\n" in pattern or "\r" in pattern:
        raise CannotVouch("the private pattern is on more than one line, and it must be one line")
    try:
        pattern.encode("utf-8")           # fails on the marks Python leaves for bytes in the environment that it could not read as text
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            compiled = re.compile(pattern, re.IGNORECASE)
    except (re.error, RecursionError, OverflowError, ValueError, Warning):
        raise CannotVouch("the private pattern is not a valid pattern") from None
    if compiled.search(""):
        raise CannotVouch("the private pattern matches everything, even nothing at all, so it cannot be what was meant")
    return lambda text: compiled.search(text) is not None


def git(repo, *args, stdin=None):
    """What a git command printed, as bytes, or a CannotVouch that gives the command if it did not end well.

    Replacements are switched off: `git replace` shows this computer another
    object in an object's place, and a visitor to GitHub sees the real one. Git
    is not handed the pattern. What it writes to its error output is caught and
    dropped, since that can quote a name or a message. The command itself is
    fixed words and a hash, so a refusal can print it for a person to run.
    """
    command = ["git", "--no-replace-objects", *args]
    without_the_pattern = {name: value for name, value in os.environ.items() if name != "PRIVATE_WORDS"}
    try:
        done = subprocess.run(command, cwd=repo, input=stdin, capture_output=True, timeout=GIT_SECONDS, env=without_the_pattern)
    except subprocess.TimeoutExpired:
        raise CannotVouch(f"this git command did not answer within {GIT_SECONDS} seconds: {shlex.join(command)}") from None
    except OSError:
        raise CannotVouch("git could not be run here") from None
    if done.returncode:
        raise CannotVouch(f"this git command ended with status {done.returncode}; run it by hand in this folder to see why: "
                          f"{shlex.join(command)}")
    return done.stdout


def text_of(data):
    """Bytes as text, whatever they are: bytes that are not UTF-8 are kept as marks, not dropped."""
    return data.decode("utf-8", errors="replace")


def held_in(data, holds):
    """Whether bytes hold a match: read as UTF-8 and, if there are NULs among them, again with the NULs taken out."""
    return holds(text_of(data)) or (b"\0" in data and holds(text_of(data.replace(b"\0", b""))))


def shown(name):
    """A name as it can be printed: in quotes, on one line, and never with `##[` in it, which the runner takes as a command."""
    return json.dumps(text_of(name)).replace("##[", "#\\u0023[")


def whole_repository(repo):
    """The repository that a folder is in -> (its top folder, the commit that HEAD names), or a CannotVouch.

    Both are asked for once and used for every row, so each row reads the same
    commit from the same place wherever the scan was started. A shallow clone
    and a grafts file each give commits other parents on this computer alone,
    so the history a visitor sees could hold what this one does not show.
    """
    top = git(repo, "rev-parse", "--show-toplevel")
    said = top.endswith(b"\n") and len(top) > 1 and WHOLE.fullmatch(
        git(top[:-1], "rev-parse", "HEAD^{commit}", "--is-shallow-repository", "--git-path", "info/grafts"))
    if not said:
        raise CannotVouch("git did not describe this repository in the form the scan knows")
    if said["shallow"] == b"true":
        raise CannotVouch("this is a shallow clone: its history is cut short, so most commits cannot be read")
    try:
        with open(os.path.join(top[:-1], said["grafts"]), "rb") as grafts:
            grafted = bool(grafts.read().strip())
    except (FileNotFoundError, NotADirectoryError):
        grafted = False
    if grafted:
        raise CannotVouch("this repository has a grafts file (.git/info/grafts), which can hide part of the history from the scan")
    return top[:-1], said["head"].decode()


def tracked_files(top, holds):
    """Every tracked file -> (how many, the ones that match as printable labels).

    A file matches on its name, with its folders, or on what it holds. A name
    that matches is withheld, since printing it would print the word, and the
    name is looked at first so that it is withheld whatever the file holds. A
    link is read as the place it points to and is never followed. A submodule
    is another repository's commit, so only its name is read. A name stays as
    the bytes git gave, so a file is found on the disk even if its name is not
    UTF-8. A file in the middle of a merge is listed up to three times and
    counted once.
    """
    listed = git(top, "ls-files", "--stage", "-z").split(b"\0")
    modes = {}
    try:
        if listed.pop():
            raise ValueError("the last entry has no end")
        for entry in listed:                                # "<mode> <hash> <stage>", a tab, the name
            about, _, name = entry.partition(b"\t")
            if not name:
                raise ValueError("an entry with no name")
            modes[name] = int(about.split(b" ")[0], 8)
    except ValueError:
        raise CannotVouch("git's list of tracked files did not come back entry by entry") from None
    matching = []
    for name, mode in modes.items():
        path = os.path.join(top, name)
        if holds(text_of(name)):
            matching.append("(a file whose name, with its folders, matches; name withheld)")
        elif mode == SUBMODULE:
            continue
        elif os.path.islink(path):
            if holds(text_of(os.readlink(path))):
                matching.append(shown(name))
        elif os.path.isfile(path):
            try:
                with open(path, "rb") as file:
                    held = file.read()
            except OSError:
                raise CannotVouch(f"the tracked file {shown(name)} could not be read") from None
            if held_in(held, holds):
                matching.append(shown(name))
        else:
            raise CannotVouch("git lists a tracked file that is not in the folder, so the working copy is not whole")
    return len(modes), matching


def commits(top, head, holds):
    """Every commit that one commit reaches -> (how many, the short hashes of the ones that match).

    A commit matches on who wrote it, who committed it, or its message. Each one
    comes back as a NUL, its hash, another NUL and that text; none of those can
    hold a NUL of its own. If the pieces are ever not hash, text, hash, text,
    the scan refuses to vouch.

    Git and GitHub write hashes into messages ("This reverts commit ...",
    "Merge ... into ..."), and a number in the pattern could match one by
    chance, which no later commit could put right. So a run of 40 or 64 of the
    digits and the letters a to f, with none of those hard against either end,
    is cut out before the text is searched. The text is split there, not
    joined, so the words on either side of a hash cannot make a match together.
    """
    pieces = git(top, "log", "--no-show-signature", "--encoding=UTF-8", EACH_COMMIT, head, "--").split(b"\0")
    hashes, written = [text_of(piece) for piece in pieces[1::2]], pieces[2::2]
    if pieces[0].strip() or len(hashes) != len(written) or not all(HASH.fullmatch(commit) for commit in hashes):
        raise CannotVouch("git's history did not come back commit by commit")
    return len(hashes), [commit[:10] for commit, text in zip(hashes, written)
                         if any(holds(words) for words in A_HASH_IN_WORDS.split(text_of(text)))]


def names_listed(folder, hash_length):
    """A folder's list as git stores it -> for each line, (the mode, the name, the hash of what is listed).

    A line is the mode in octal digits, a space, the name, a NUL and the raw
    hash. Only the names are a person's words. A ValueError means the list is
    not in that form.
    """
    listed, at = [], 0
    while at < len(folder):
        name_ends = folder.index(b"\0", at)
        mode_ends = folder.index(b" ", at, name_ends)
        mode, name, at = int(folder[at:mode_ends], 8), folder[mode_ends + 1:name_ends], name_ends + 1 + hash_length
        listed.append((mode, name, folder[name_ends + 1:at].hex().encode()))
    if at != len(folder):
        raise ValueError("the last hash is cut short")
    return listed


def folders_matching(folders, roots, holds):
    """Which of the history's folders list a name that matches -> for each folder, how it matches, or None.

    `folders` is every folder's list by the folder's hash, and `roots` is the
    top folder of every commit. A name is read alone and with the folders above
    it, so each folder is reached by walking down from the commits' top
    folders. One folder object can sit under many paths, since a rename keeps
    the object, so what is remembered as done is a path and a folder together.
    Once a path matches, everything below it would match for the same reason,
    so below it only a name that matches alone is reported.

    A KeyError means a folder that is listed did not come back from git, and a
    ValueError that one came back which no commit leads to.
    """
    how = dict.fromkeys(folders)
    done, waiting = set(), [(b"", root) for root in roots]
    while waiting:
        above, folder = waiting.pop()
        if (above, folder) in done:
            continue
        done.add((above, folder))
        found_above = holds(text_of(above))
        for mode, name, listed in folders[folder]:
            path = above + name + (b"/" if mode == FOLDER else b"")
            if holds(text_of(name)):
                how[folder] = BY_NAME
            elif not found_above and holds(text_of(path)):
                how[folder] = how[folder] or BY_PATH
            if mode == FOLDER:
                waiting.append((path, listed))
    if len({folder for _, folder in done}) != len(folders):
        raise ValueError("a folder that no commit leads to")
    return how


def kept_files(top, head, holds):
    """Every version of every file, and every folder's list, that the history keeps -> (how many, the ones that match).

    Each object is read whole and as it is stored, so nothing git is set to do
    can leave one out; a patch, for one, leaves out any file git takes as binary.
    A file matches on what it held, and a folder on a name it lists, read alone
    or with the folders above it.

    Of a commit only the first line is used, which names its top folder.
    commits() has read who made it and its message. The rest is git's own:
    hashes and dates, which a number in the pattern must never match by chance,
    and the headers that git's tools add (a signature, a merged signed tag),
    which this scan does not read.
    """
    asked = git(top, "rev-list", "--objects", "--no-object-names", head, "--").split()
    answer = git(top, "cat-file", "--batch", stdin=b"\n".join(asked) + b"\n")
    how, folders, roots, at = {}, {}, [], 0
    try:
        for name in asked:                                  # each comes back as "<name> <kind> <size>", a line end,
            first_line_ends = answer.index(b"\n", at)       # that many bytes, and one more line end
            named, kind, size = answer[at:first_line_ends].split(b" ")
            if named != name or not size.isdigit():
                raise ValueError("not the object that was asked for, or no size")
            begins, ends = first_line_ends + 1, first_line_ends + 1 + int(size)
            if answer[ends:ends + 1] != b"\n":
                raise ValueError("the object is not as long as its size")
            held, at = answer[begins:ends], ends + 1
            if kind == b"blob":
                how[name] = A_FILE if held_in(held, holds) else None
            elif kind == b"tree":
                folders[name] = names_listed(held, len(name) // 2)
            elif kind == b"commit":
                root = held.split(b"\n", 1)[0]                 # "tree " and the top folder's hash
                if not root.startswith(b"tree "):
                    raise ValueError("a commit that does not begin with its top folder")
                roots.append(root[5:])
            else:
                raise ValueError("a kind of object the scan does not know")
        if at != len(answer):
            raise ValueError("more came back than was asked for")
        how.update(folders_matching(folders, roots, holds))
    except (ValueError, KeyError):
        raise CannotVouch("git's objects did not come back whole, one for each one asked for") from None
    shorts = ((name, text_of(name)[:10]) for name in asked)
    return len(how), [f"object {short}: {how[name].format(short)}" for name, short in shorts if how.get(name)]


def pull_request(event_file, holds):
    """The words a person typed into the pull request that started the run -> (how many, which ones match).

    event_file is where GitHub wrote the event, as JSON, or nothing at all away
    from GitHub. A run that no pull request started has no words to read. A
    description left empty is null there, and is not counted.
    """
    if not event_file:
        return 0, []
    try:
        event = json.loads(Path(event_file).read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise TypeError("an event is an object")
        if "pull_request" not in event:
            return 0, []
        asked = event["pull_request"]
        typed = (("the title", asked["title"]), ("the body", "" if asked["body"] is None else asked["body"]),
                 ("the branch", asked["head"]["ref"]))
        if not all(isinstance(text, str) for _, text in typed):
            raise TypeError("each of the three is text")
    except (OSError, ValueError, RecursionError, LookupError, TypeError):
        raise CannotVouch("the pull request's title, body and branch could not be read from the event file") from None
    return sum(1 for _, text in typed if text), [label for label, text in typed if holds(text)]


def scan(environ, repo):
    """Look everywhere and print what was found -> the exit status, 0 or 1. A CannotVouch means neither."""
    pattern = environ.get("PRIVATE_WORDS", "").strip()
    if not pattern:
        if environ.get("PRIVATE_WORDS_FROM_FORK") == "true":
            print("::notice title=private-words::skipped: a pull request from a fork is not given the private pattern, "
                  "so this change is checked by hand before it merges")
            print("private words: skipped (no pattern for a fork)")
            return 0
        raise CannotVouch("no pattern: PRIVATE_WORDS is not set, and only a pull request from a fork may go without it")
    holds = searcher(pattern)
    top, head = whole_repository(repo)
    report = (("tracked files", tracked_files(top, holds)), ("commits", commits(top, head, holds)),
              ("files and folders in the history", kept_files(top, head, holds)),
              ("pull request", pull_request(environ.get("GITHUB_EVENT_PATH"), holds)))
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


def main(environ=None, repo="."):
    """Scan the repository that a folder is in -> the exit status.

    Anything that stops the scan ends with 2 and one sentence. An error that
    was not foreseen gives only its kind: its own words could hold what the
    scan was reading, and a traceback would end with 1, which means "found".
    """
    try:
        return scan(os.environ if environ is None else environ, repo)
    except CannotVouch as problem:
        why = str(problem)
    except Exception as surprise:
        why = f"an error the scan did not foresee stopped it ({type(surprise).__name__})"
    print(f"private words: the scan cannot vouch for this repository: {why}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    if os.environ.get("GITHUB_JOB") == "private-words":      # A THROWAWAY PROOF, NOT FOR MERGING: this job never
        import time                                           # finishes, so its five-minute limit cuts it off
        time.sleep(900)
    sys.exit(main())
