"""The scan for the private words guards what the public can read, so it is tested like code.

Every test builds a small git repository of its own and scans it with a stand-in
pattern. The real pattern is never in this repository.
"""
import contextlib
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "private_words.py"
PATTERN = r"zebra[^a-z]{0,3}crossing|4[,.]?200"        # a stand-in: two words with up to three marks between, or a number
ACCENTED = r"z\u00e9bra.crossing"                       # another, with a letter outside ASCII, written so that it can travel anywhere
WORD = "zebra"                                          # what must never be printed
HISTORY = "files and folders in the history"            # the row for every version of every file, and every folder list
WITHHELD = "(a file whose name, with its folders, matches; name withheld)"
BY_NAME = "a folder that lists a name that matches (its list: git cat-file -p {0})"
BY_PATH = "a folder that lists a name that matches when read with the folders above it (its list: git cat-file -p {0})"
A_FILE = "what a file held (its commits: git log --all --find-object={0})"
NOT_REFUSED = "private words: the scan cannot vouch for this repository: "       # how every refusal begins
NOT_A_PATTERN = "the private pattern is not a valid pattern"
# Git is kept away from this computer's own settings, and from any repository the temp folder happens to sit inside.
QUIET_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
             "GIT_CEILING_DIRECTORIES": tempfile.gettempdir()}
REAL_GIT = shutil.which("git")                          # for the stand-in below, which passes most of its work on to it
SOMEONE = {"GIT_AUTHOR_NAME": "A Writer", "GIT_AUTHOR_EMAIL": "writer@example.org",
           "GIT_COMMITTER_NAME": "A Writer", "GIT_COMMITTER_EMAIL": "writer@example.org"}
SIGNER = """#!/bin/sh
# Stands in for gpg. It "signs" anything, and when asked to check a signature it says so out loud.
case " $* " in
  *" --verify "*) echo "checked by the zebra crossing" >&2; echo "[GNUPG:] GOODSIG 0123456789ABCDEF A Writer" ;;
  *) cat > /dev/null; echo "[GNUPG:] SIG_CREATED D 1 8 00 1700000000 0123456789ABCDEF" >&2
     printf -- '-----BEGIN PGP SIGNATURE-----\\n\\nnot a signature\\n-----END PGP SIGNATURE-----\\n' ;;
esac
"""
STAND_IN_GIT = """#!/bin/sh
# Stands in for git. For the one command named in STAND_IN_FOR it does what STAND_IN says; for the rest it is git.
# The scan calls it as: git --no-replace-objects <command> ...
if [ -n "$STAND_IN_RECORD" ]; then
  echo "ran $2" >> "$STAND_IN_RECORD"
  [ -n "${PRIVATE_WORDS+set}" ] && echo "was handed the pattern" >> "$STAND_IN_RECORD"
fi
if [ "$2" = "$STAND_IN_FOR" ] || [ "$STAND_IN_FOR" = "every command" ]; then
  case "$STAND_IN" in
    "never answers") exec sleep 30 ;;
    "is killed part-way") echo 0123456789012345678901234567890123456789; kill -9 $$ ;;
    "fails, with the words in what it says") echo "fatal: the zebra crossing has 4200 problems" >&2; exit 3 ;;
    "grumbles, with the words in what it says") echo "warning: the zebra crossing has 4200 problems" >&2 ;;
  esac
fi
exec "REAL_GIT" "$@"
"""


def load():
    """The script as a module; it lives outside the package, so it is loaded by path."""
    spec = importlib.util.spec_from_file_location("private_words", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_git(folder, *args, raw=False, **env):
    """A git command in a folder, kept away from this computer's own settings -> what it printed (as bytes, if raw)."""
    done = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=not raw, timeout=60,
                          env={"PATH": os.environ["PATH"], **QUIET_GIT, **SOMEONE, **env})
    if done.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout


def asked_of_git(head):
    """Each git command the scan runs, by the command's name, as a refusal prints it. Of the two `rev-parse`, the first."""
    git = "git --no-replace-objects"
    return {"rev-parse": f"{git} rev-parse --show-toplevel",
            "ls-files": f"{git} ls-files --stage -z",
            "log": f"{git} log --no-show-signature --encoding=UTF-8 --format=%x00%H%x00%an%n%ae%n%cn%n%ce%n%B {head} --",
            "rev-list": f"{git} rev-list --objects --no-object-names {head} --",
            "cat-file": f"{git} cat-file --batch"}


SECOND_REV_PARSE = "git --no-replace-objects rev-parse 'HEAD^{commit}' --is-shallow-repository --git-path info/grafts"


class Scanned:
    """What one scan ended with and printed."""

    def __init__(self, status, stdout, stderr):
        self.returncode, self.stdout, self.stderr, self.said = status, stdout, stderr, stdout + stderr


class Repository(unittest.TestCase):
    """A throwaway repository with one clean commit, and the ways the tests scan it."""

    @classmethod
    def setUpClass(cls):
        """Build the one clean commit once; each test then works on a copy of it."""
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        cls.template = Path(folder.name) / "template"
        (cls.template / "src").mkdir(parents=True)
        (cls.template / "README.md").write_text("A quiet page.\n", encoding="utf-8")
        (cls.template / "src" / "code.py").write_text("print('nothing to see')\n", encoding="utf-8")
        run_git(cls.template, "init", "-q", "-b", "main")
        run_git(cls.template, "add", "-A")
        run_git(cls.template, "commit", "-q", "-m", "Begin")

    def setUp(self):
        self.script = load()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = Path(folder.name) / "repo"
        shutil.copytree(self.template, self.repo, symlinks=True)

    def git(self, *args, cwd=None, raw=False, **env):
        return run_git(cwd or self.repo, *args, raw=raw, **env)

    def commit(self, files, message, **env):
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message, **env)

    def event(self, event):
        """A file such as GitHub writes on the runner for what started the run -> its path, for GITHUB_EVENT_PATH."""
        path = self.repo.parent / "event.json"
        path.write_bytes(event if isinstance(event, bytes) else json.dumps(event, ensure_ascii=False).encode("utf-8"))
        return str(path)

    def pull_request(self, title="A title", body="A body", branch="a-branch"):
        """The event file of a pull request with these words in it."""
        return self.event({"action": "opened", "number": 7, "repository": {"full_name": "someone/something"},
                           "pull_request": {"number": 7, "title": title, "body": body, "head": {"ref": branch, "sha": "0" * 40}}})

    def program(self, name, script):
        """A small program of the tests' own, in a folder of its own -> that folder, to put first on a PATH.

        The test is skipped, and says why, where the temp folder is one that programs cannot be run from.
        """
        folder = self.repo.parent / f"programs-{name}"
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_text(script.replace("REAL_GIT", REAL_GIT or "git"), encoding="utf-8")
        path.chmod(0o755)
        try:
            subprocess.run([str(path), "--version"], stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        except OSError:
            self.skipTest(f"programs cannot be run from the temp folder here, so the stand-in for {name} cannot be used")
        return folder

    def stand_in_git(self, does, command, record=None):
        """What to add to a process's environment so that its git is a stand-in that goes wrong for one command."""
        return {"PATH": f"{self.program('git', STAND_IN_GIT)}{os.pathsep}{os.environ['PATH']}", "STAND_IN": does,
                "STAND_IN_FOR": command, **({"STAND_IN_RECORD": str(record)} if record else {})}

    def name_of(self, what):
        """An object's name as short as the scan prints it: "HEAD", "HEAD:notes.txt", "HEAD:docs", "HEAD^{tree}"."""
        return self.git("rev-parse", what).strip()[:10]

    def head(self):
        return self.name_of("HEAD")

    def never_tells(self, ran, pattern):
        self.assertNotIn("Traceback", ran.said)
        self.assertNotIn(WORD, ran.said.lower(), "the scan printed the word it was looking for")
        if pattern and len(pattern.strip()) > 8:
            self.assertNotIn(pattern.strip(), ran.said, "the scan printed its pattern")
        return ran

    def scan(self, cwd=None, pattern=PATTERN, around=None, **env):
        """Scan by calling the script's main.

        While it runs, this process's environment is cut down to a path and the
        quiet settings, so the script's git reads neither this computer's settings
        nor a GIT_DIR left by a hook that happens to be running the tests. What a
        test wants in that environment as well (another PATH, say) it gives as `around`.
        """
        environ = {**({} if pattern is None else {"PRIVATE_WORDS": pattern}), **env}
        bare = {"PATH": os.environ["PATH"], **QUIET_GIT, **(around or {})}
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, bare, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = self.script.main(environ, cwd or self.repo)
        return self.never_tells(Scanned(status, out.getvalue(), err.getvalue()), pattern)

    def run_script(self, *options, script=SCRIPT, **env):
        """Scan by running the script as GitHub runs it: a process of its own, told everything through its environment."""
        ran = subprocess.run([sys.executable, *options, str(script)], cwd=self.repo, capture_output=True, text=True, timeout=120,
                             env={"PATH": os.environ["PATH"], **QUIET_GIT, **env})
        return self.never_tells(Scanned(ran.returncode, ran.stdout, ran.stderr), env.get("PRIVATE_WORDS"))

    def passed(self, ran, *said):
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertEqual(ran.stderr, "")
        self.assertTrue(ran.stdout.endswith("private words: none found\n"), ran.stdout)
        for words in said:
            self.assertIn(words, ran.stdout)

    def found(self, ran, *said):
        self.assertEqual(ran.returncode, 1, ran.said)
        self.assertIn("FOUND", ran.stdout)
        for words in said:
            self.assertIn(words, ran.stdout)

    def refused(self, ran, *said):
        """The scan ended with 2 and one sentence of its own: nothing of the scan, of git's or of Python's."""
        self.assertEqual(ran.returncode, 2, ran.said)
        self.assertEqual(ran.stdout, "")
        self.assertTrue(ran.stderr.startswith(NOT_REFUSED), ran.stderr)
        self.assertEqual(ran.stderr.count("\n"), 1, ran.stderr)
        for words in said:
            self.assertIn(words, ran.stderr)

    def refused_saying(self, ran, sentence):
        self.assertEqual(ran.stderr, NOT_REFUSED + sentence + "\n")
        self.refused(ran)


class Pattern(unittest.TestCase):
    def setUp(self):
        self.script = load()

    def refused(self, pattern, sentence):
        """The pattern is refused in these words exactly, with nothing kept that could carry the pattern into a traceback."""
        with warnings.catch_warnings(record=True) as warned:
            warnings.simplefilter("always")
            with self.assertRaises(self.script.CannotVouch) as refusal:
                self.script.searcher(pattern)
        self.assertEqual(warned, [])
        self.assertEqual(str(refusal.exception), sentence)
        self.assertIsNone(refusal.exception.__cause__)
        self.assertTrue(refusal.exception.__context__ is None or refusal.exception.__suppress_context__)

    def test_case_and_the_marks_between_the_words_do_not_hide_it(self):
        holds = self.script.searcher(PATTERN)
        for text in ("zebra crossing", "ZEBRA CROSSING", "Zebra-Crossing", "zebra...crossing", "zebracrossing",
                     "at the zebra crossing, look", "a 4,200 crowd", "4200", "4.200", "line one\nthe ZEBRA\ncrossing"):
            with self.subTest(text=text):
                self.assertIs(holds(text), True)

    def test_what_only_looks_alike_does_not_match(self):
        holds = self.script.searcher(PATTERN)
        for text in ("", "zebra", "crossing", "zebra and then, later, a crossing", "zebra....crossing", "42,00", "4 200"):
            with self.subTest(text=text):
                self.assertIs(holds(text), False)

    def test_a_letter_with_an_accent_is_matched_whatever_its_case(self):
        holds = self.script.searcher(ACCENTED)
        self.assertIs(holds("the Z\u00c9BRA crossing"), True)
        self.assertIs(holds("the z\u00e9bra-crossing"), True)
        self.assertIs(holds("the zebra crossing"), False)

    def test_a_pattern_that_cannot_be_read_is_refused_without_repeating_it(self):
        for pattern in ("zebra[crossing", "(zebra", "zebra)", "*zebra"):
            with self.subTest(pattern=pattern):
                self.refused(pattern, NOT_A_PATTERN)

    def test_a_pattern_the_compiler_would_quote_is_refused_in_the_same_fixed_words(self):
        """What Python says of each of these holds a piece of the pattern, or is a warning, or is not a pattern error at all."""
        nested = "(" * 3000 + "zebra crossing" + ")" * 3000
        for pattern in (r"\N{zebra crossing}", "(?P=zebra)", "(?P<zebra crossing>x)", "(?P<zebra>a)(?P<zebra>b)",     # quoted back
                        nested, "zebra{99999999999999999999}", "(?a)(?u)zebra crossing",       # three other kinds of error
                        "zebra(?i)crossing", "[[zebra]crossing"):                               # a warning on one Python or on all
            with self.subTest(pattern=pattern[:30]):
                self.refused(pattern, NOT_A_PATTERN)

    def test_a_pattern_that_reached_python_as_bytes_it_could_not_read_is_refused(self):
        """Where the computer's own encoding is not UTF-8, a letter outside ASCII in the environment arrives as marks that match nothing."""
        self.refused("z" + chr(0xDCC3) + chr(0xDCA9) + "bra.crossing", NOT_A_PATTERN)
        self.assertIs(self.script.searcher("z" + chr(0xE9) + "bra.crossing")("the Z" + chr(0xC9) + "BRA crossing"), True)

    def test_a_pattern_that_matches_nothing_at_all_in_particular_is_refused(self):
        for pattern in ("x*", "zebra crossing|", "()", "(zebra)?"):
            with self.subTest(pattern=pattern):
                with self.assertRaises(self.script.CannotVouch) as refusal:
                    self.script.searcher(pattern)
                self.assertIn("matches everything", str(refusal.exception))

    def test_a_pattern_on_more_than_one_line_is_refused(self):
        for pattern in ("zebra crossing\n4200", "zebra crossing\r\n4200", "zebra\rcrossing", "zebra crossing|\n4200"):
            with self.subTest(pattern=pattern):
                self.refused(pattern, "the private pattern is on more than one line, and it must be one line")


class Scan(Repository):
    # nothing to find

    def test_a_clean_repository_passes_and_says_what_it_looked_at(self):
        ran = self.scan()
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertEqual(ran.stdout, "tracked files: 0 of 2 match\ncommits: 0 of 1 match\n"
                                     f"{HISTORY}: 0 of 4 match\npull request: 0 of 0 match\nprivate words: none found\n")
        self.assertEqual(ran.stderr, "")

    def test_a_clean_pull_request_passes(self):
        ran = self.scan(GITHUB_EVENT_PATH=self.pull_request("Add a thing", "It adds a thing.\n\nTwo paragraphs.", "add-a-thing"))
        self.passed(ran, "pull request: 0 of 3 match")

    def test_a_pull_request_with_no_description_is_read_without_one(self):
        for body in (None, ""):                                  # GitHub writes null for a description left empty
            with self.subTest(body=body):
                ran = self.scan(GITHUB_EVENT_PATH=self.pull_request("Add a thing", body, "add-a-thing"))
                self.passed(ran, "pull request: 0 of 2 match")

    def test_a_run_that_no_pull_request_started_has_none_to_read(self):
        pushed = self.event({"ref": "refs/heads/main", "repository": {"full_name": "someone/something"},
                             "head_commit": {"message": "the title of nothing"}})
        for label, env in (("a push", {"GITHUB_EVENT_PATH": pushed}), ("no event at all", {}), ("an empty path", {"GITHUB_EVENT_PATH": ""})):
            with self.subTest(label=label):
                self.passed(self.scan(**env), "pull request: 0 of 0 match")

    def test_the_pull_request_is_not_read_from_the_environment(self):
        """The runner prints every value a step is given that way into its log, so the words are not handed over so."""
        ran = self.scan(PRIVATE_WORDS_TITLE="Zebra crossing", PRIVATE_WORDS_BODY="zebra crossing", PRIVATE_WORDS_BRANCH="zebra-crossing",
                        GITHUB_HEAD_REF="zebra-crossing")
        self.passed(ran, "pull request: 0 of 0 match")

    def test_space_around_the_pattern_is_not_part_of_it(self):
        self.assertEqual(self.scan(pattern=f"  {PATTERN}\n").returncode, 0)
        self.commit({"first.txt": "zebra crossing", "last.txt": "a crowd of 4200"}, "Neither file ends its last line")
        self.found(self.scan(pattern=f"  {PATTERN}"), "tracked files: 2 of 4 match")     # the spaces would ask for spaces before "zebra"
        self.found(self.scan(pattern=f"{PATTERN}\n"), "tracked files: 2 of 4 match")    # the line end would ask for one after "200"

    def test_what_git_itself_writes_into_a_commit_is_never_searched(self):
        """A number in the pattern must not match a hash or a date by chance: no later commit could put that right."""
        self.commit({"a.txt": "a\n"}, "Second", GIT_AUTHOR_DATE="1700000000 +0000", GIT_COMMITTER_DATE="1700000123 +0000")
        parent, folder = self.git("rev-parse", "HEAD~1").strip(), self.git("rev-parse", "HEAD^{tree}").strip()
        self.assertIn(f"parent {parent}\n", self.git("cat-file", "commit", "HEAD"))
        self.assertIn("> 1700000000 +0000\n", self.git("cat-file", "commit", "HEAD"))
        for pattern in (parent[:12], folder[:12], "1700000000", "1700000123", r"\+0000"):
            with self.subTest(pattern=pattern):
                self.passed(self.scan(pattern=pattern), "commits: 0 of 2 match", f"{HISTORY}: 0 of 6 match")

    def test_a_full_hash_in_a_message_is_not_searched(self):
        """Git and GitHub write hashes into messages ("This reverts commit ...", "Merge ... into ..."), and so do people."""
        self.commit({"a.txt": "a\n"}, "Second")
        second, first = self.git("rev-parse", "HEAD").strip(), self.git("rev-parse", "HEAD~1").strip()
        self.commit({}, f'Revert "Second"\n\nThis reverts commit {second}.\nMerge {first} into {second}')
        for pattern in (second[8:20], first[8:20]):
            with self.subTest(pattern=pattern):
                self.passed(self.scan(pattern=pattern), "commits: 0 of 3 match")

    def test_a_file_is_read_by_its_size_whatever_it_holds(self):
        looks_like_git = b"0" * 40 + b" blob 3\nabc\n" + b"1" * 40 + b" missing\n"
        self.commit({"empty.txt": b"", "odd.txt": looks_like_git, "late.bin": b"a\n" * 5000 + b"\x00 and then more"}, "Odd files")
        self.passed(self.scan(), "tracked files: 0 of 5 match", f"{HISTORY}: 0 of 8 match")

    def test_a_file_called_head_does_not_stop_the_scan(self):
        """`git log HEAD` cannot tell that file from the newest commit. The scan names the commit in full and says where names end."""
        self.commit({"HEAD": "nothing in here\n"}, "A file with the name git gives the newest commit")
        self.passed(self.scan(), f"tracked files: 0 of 3 match\ncommits: 0 of 2 match\n{HISTORY}: 0 of 6 match\n")

    def test_a_first_commit_with_no_files_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            self.git("init", "-q", "-b", "main", cwd=folder)
            self.git("commit", "-q", "--allow-empty", "-m", "Begin with nothing", cwd=folder)
            self.passed(self.scan(cwd=folder), f"tracked files: 0 of 0 match\ncommits: 0 of 1 match\n{HISTORY}: 0 of 1 match\n")

    def test_a_submodule_is_searched_by_its_name_and_never_opened(self):
        """A submodule is another repository's commit. Only its name here belongs to this repository."""
        inner = self.repo / "vendor" / "lib"
        inner.mkdir(parents=True)
        self.git("init", "-q", "-b", "main", cwd=inner)
        (inner / "notes.txt").write_text("the zebra crossing\n", encoding="utf-8")
        self.git("add", "-A", cwd=inner)
        self.git("commit", "-q", "-m", "Inside the other repository", cwd=inner)
        self.git("add", "vendor/lib")
        self.git("commit", "-q", "-m", "Another repository, kept as a submodule")
        self.assertTrue(self.git("ls-files", "--stage", "vendor/lib").startswith("160000 "))
        self.passed(self.scan(), "tracked files: 0 of 3 match", "commits: 0 of 2 match", f"{HISTORY}: 0 of 6 match")
        shutil.rmtree(inner)                                      # a submodule that was never fetched is no folder at all
        self.passed(self.scan(), "tracked files: 0 of 3 match")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{'1' * 40},zebra-crossing")
        self.git("commit", "-q", "-m", "A second submodule, with a name of its own")
        root = self.name_of("HEAD^{tree}")
        self.found(self.scan(), f"tracked files: 1 of 4 match\n  - {WITHHELD}\ncommits: 0 of 3 match\n",
                   f"{HISTORY}: 1 of 7 match\n  - object {root}: {BY_NAME.format(root)}\n")

    def test_a_file_in_the_middle_of_a_merge_is_read_once(self):
        self.git("switch", "-q", "-c", "side")
        self.commit({"README.md": "A page from the side.\n"}, "On the side")
        self.git("switch", "-q", "main")
        self.commit({"README.md": "A page by the zebra crossing.\n"}, "On main")
        with self.assertRaises(AssertionError):
            self.git("merge", "-q", "side")                       # the two changes cannot both stand
        self.assertEqual(len(self.git("ls-files", "--stage", "README.md").splitlines()), 3)
        self.found(self.scan(), 'tracked files: 1 of 2 match\n  - "README.md"\ncommits:')

    # something to find

    def test_a_word_in_a_file_fails_and_names_the_file_only(self):
        self.commit({"docs/notes.txt": "Meet me at the Zebra Crossing.\n"}, "Notes")
        held = self.name_of("HEAD:docs/notes.txt")
        ran = self.scan()
        self.assertEqual(ran.returncode, 1)
        self.assertEqual(ran.stdout, 'tracked files: 1 of 3 match\n  - "docs/notes.txt"\ncommits: 0 of 2 match\n'
                                     f"{HISTORY}: 1 of 7 match\n"
                                     f"  - object {held}: what a file held (its commits: git log --all --find-object={held})\n"
                                     "pull request: 0 of 0 match\n"
                                     "private words: FOUND. The lines above say where. What matched is never printed.\n")
        self.assertEqual(ran.stderr, "")

    def test_a_word_in_a_file_name_fails_and_the_name_is_withheld(self):
        self.commit({"docs/zebra-crossing.txt": "nothing in here\n"}, "A file")
        folder = self.name_of("HEAD:docs")
        self.found(self.scan(), f"tracked files: 1 of 3 match\n  - {WITHHELD}\n",
                   f"{HISTORY}: 1 of 7 match\n  - object {folder}: {BY_NAME.format(folder)}\n")

    def test_a_file_whose_name_and_contents_both_match_has_its_name_withheld(self):
        self.commit({"zebra-crossing.txt": "the zebra crossing\n"}, "A file")
        self.found(self.scan(), f"tracked files: 1 of 3 match\n  - {WITHHELD}\ncommits:")

    def test_a_folder_with_the_word_in_its_name_is_found_by_the_file_in_it(self):
        self.commit({"zebra-crossing/notes.txt": "nothing in here\n"}, "A folder")
        root = self.name_of("HEAD^{tree}")
        self.found(self.scan(), f"tracked files: 1 of 3 match\n  - {WITHHELD}\ncommits:",
                   f"{HISTORY}: 1 of 7 match\n  - object {root}: {BY_NAME.format(root)}\n")

    def test_a_match_spread_over_a_folder_and_a_file_is_found_and_stays_found_after_a_rename(self):
        self.commit({"zebra/crossing.txt": "nothing in here\n", "zebra/other.txt": "nor here\n"}, "Two names that match only together")
        folder = self.name_of("HEAD:zebra")
        by_path = f"  - object {folder}: {BY_PATH.format(folder)}\n"
        self.found(self.scan(), f"tracked files: 1 of 4 match\n  - {WITHHELD}\ncommits:", f"{HISTORY}: 1 of 8 match\n{by_path}")
        self.git("mv", "zebra", "plain")
        self.commit({}, "A plainer folder")
        self.assertEqual(self.name_of("HEAD:plain"), folder)      # one folder object, reached by a quiet path now as well
        self.found(self.scan(), "tracked files: 0 of 4 match", "commits: 0 of 3 match", f"{HISTORY}: 1 of 9 match\n{by_path}")

    def test_a_word_in_bytes_that_are_not_text_is_still_found(self):
        self.commit({"blob.bin": b"\xff\xfe\x00zebra crossing\x00\xff"}, "A blob")
        self.found(self.scan(), '  - "blob.bin"', f"{HISTORY}: 1 of 6 match", f"  - object {self.name_of('HEAD:blob.bin')}: what a file held")

    def test_a_byte_that_is_not_text_inside_a_word_is_kept_as_a_mark_and_not_dropped(self):
        self.commit({"notes.bin": b"the zebra\xffcrossing\n"}, "A stray byte")
        self.found(self.scan(pattern="zebra.crossing"), '  - "notes.bin"', f"{HISTORY}: 1 of 6 match")
        self.passed(self.scan(pattern="zebracrossing"))

    def test_a_file_with_nuls_in_it_is_read_as_it_is_as_well_as_without_them(self):
        """The second reading is one more, not the only one: here it is the NUL that the pattern's dot stands for."""
        self.commit({"notes.bin": b"the zebra\x00crossing\n"}, "A NUL between two words")
        held = self.name_of("HEAD:notes.bin")
        self.found(self.scan(pattern="zebra.crossing"), '  - "notes.bin"', f"{HISTORY}: 1 of 6 match\n  - object {held}: what a file held")
        self.found(self.scan(pattern="zebracrossing"), '  - "notes.bin"', f"{HISTORY}: 1 of 6 match\n  - object {held}: what a file held")

    def test_a_word_written_two_or_four_bytes_to_a_letter_is_found(self):
        """UTF-16 and UTF-32 put NUL bytes between plain letters, so a file with NULs is read again with them taken out."""
        kinds = ("utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be")
        files = {f"{kind}.txt": "Meet me at the Zebra Crossing.\n".encode(kind) for kind in kinds}
        self.commit({**files, "quiet.txt": "Nothing to see.\n".encode("utf-16")}, "Seven files")
        held = {name: self.name_of(f"HEAD:{name}") for name in files}
        ran = self.scan()
        self.found(ran, "tracked files: 6 of 9 match", f"{HISTORY}: 6 of 12 match")
        for name in files:
            self.assertIn(f'  - "{name}"\n', ran.stdout)
        self.git("rm", "-q", *files)
        self.commit({}, "Take them out")
        ran = self.scan()
        self.found(ran, "tracked files: 0 of 3 match", f"{HISTORY}: 6 of 13 match")
        for name in files:
            self.assertIn(f"  - object {held[name]}: {A_FILE.format(held[name])}\n", ran.stdout)

    def test_a_file_is_searched_from_its_first_byte_to_its_last_however_long(self):
        files = {"first-byte.txt": b"zebra crossing, and then the rest\n",
                 "last-byte.txt": b"no line end after the zebra crossing",
                 "far-in.txt": b"a line\n" * 1000 + b"the zebra crossing\n",
                 "across-a-line-end.txt": b"here is the zebra\ncrossing, on two lines\n",
                 "past-a-million-bytes.bin": b"a\n" * 500_000 + b"the zebra crossing"}
        self.commit(files, "Five files")
        held = {name: self.name_of(f"HEAD:{name}") for name in files}
        ran = self.scan()
        self.found(ran, "tracked files: 5 of 7 match", f"{HISTORY}: 5 of 10 match")
        for name in files:
            self.assertIn(f'  - "{name}"\n', ran.stdout)
        self.git("rm", "-q", *files)
        self.commit({}, "Take them out")
        ran = self.scan()
        self.found(ran, "tracked files: 0 of 2 match", f"{HISTORY}: 5 of 10 match")
        for name in files:
            self.assertIn(f"  - object {held[name]}: {A_FILE.format(held[name])}\n", ran.stdout)

    def test_a_word_with_an_accent_is_found_in_a_file_a_message_and_a_title(self):
        accented = "Meet me at the Z\u00e9bra Crossing."
        self.commit({"notes.txt": accented + "\n"}, "Notes")
        self.found(self.scan(pattern=ACCENTED), '  - "notes.txt"\ncommits: 0 of 2 match', f"{HISTORY}: 1 of 6 match")
        self.git("rm", "-q", "notes.txt")
        self.commit({}, accented)
        self.found(self.scan(pattern=ACCENTED), "tracked files: 0 of 2 match", f"commits: 1 of 3 match\n  - {self.head()}\n")
        self.git("reset", "-q", "--hard", "HEAD~2")
        self.assertIn("\u00e9".encode("utf-8"), Path(self.pull_request(title=accented)).read_bytes())
        self.found(self.scan(pattern=ACCENTED, GITHUB_EVENT_PATH=self.pull_request(title=accented)),
                   "commits: 0 of 1 match", "pull request: 1 of 3 match\n  - the title\n")

    def test_a_link_is_read_as_where_it_points_and_never_followed(self):
        (self.repo.parent / "outside.txt").write_text("the zebra crossing\n", encoding="utf-8")
        os.symlink("../outside.txt", self.repo / "to-a-real-file")
        os.symlink("../zebra-crossing/elsewhere", self.repo / "pointer")
        os.symlink("nowhere-at-all", self.repo / "dangling")
        self.commit({}, "Three links")
        self.assertEqual((self.repo / "to-a-real-file").read_text(encoding="utf-8"), "the zebra crossing\n")
        self.found(self.scan(), 'tracked files: 1 of 5 match\n  - "pointer"\ncommits:', f"{HISTORY}: 1 of 8 match")

    def test_a_dangling_link_is_not_an_error(self):
        os.symlink("nowhere-at-all", self.repo / "dangling")
        self.commit({}, "A link")
        self.assertEqual(self.scan().returncode, 0)

    def test_a_file_name_that_is_not_utf8_is_read_all_the_same(self):
        try:
            with open(os.path.join(os.fsencode(self.repo), b"caf\xe9.txt"), "wb") as file:
                file.write(b"the zebra crossing\n")
        except OSError:
            self.skipTest("the disk here will not hold a file name that is not UTF-8")
        self.commit({}, "A name from an older computer")
        self.found(self.scan(), 'tracked files: 1 of 3 match\n  - "caf\\ufffd.txt"\ncommits:')

    def test_a_scan_started_in_a_subfolder_reads_the_whole_repository(self):
        self.commit({"docs/deep/quiet.txt": "nothing in here\n", "top.txt": "the zebra crossing\n"}, "Two files")
        (self.repo / "README.md").write_text("Not committed yet: the zebra crossing.\n", encoding="utf-8")
        self.found(self.scan(cwd=self.repo / "docs" / "deep"), 'tracked files: 2 of 4 match\n  - "README.md"\n  - "top.txt"\ncommits:')

    def test_a_word_in_a_commit_message_fails_and_names_the_commit(self):
        self.commit({"a.txt": "a\n"}, "Fix the zebra crossing")
        self.found(self.scan(), "tracked files: 0 of 3 match", f"commits: 1 of 2 match\n  - {self.head()}\n", f"{HISTORY}: 0 of 6 match")

    def test_a_word_below_a_messages_first_line_is_found(self):
        self.commit({"a.txt": "a\n"}, "Tidy the notes\n\nA second paragraph.\n\nAnd a third, by the zebra crossing.")
        self.found(self.scan(), "tracked files: 0 of 3 match", f"commits: 1 of 2 match\n  - {self.head()}\n", f"{HISTORY}: 0 of 6 match")

    def test_every_commit_that_matches_is_listed(self):
        self.commit({"a.txt": "a\n"}, "Fix the zebra crossing")
        first = self.head()
        self.commit({"b.txt": "b\n"}, "A quiet change")
        self.commit({"c.txt": "c\n"}, "A crowd of 4,200")
        self.found(self.scan(), f"commits: 2 of 4 match\n  - {self.head()}\n  - {first}\n{HISTORY}:")

    def test_a_word_in_who_made_a_commit_fails(self):
        for who in ({"GIT_AUTHOR_NAME": "Zebra Crossing"}, {"GIT_AUTHOR_EMAIL": "me@zebra-crossing.example"},
                    {"GIT_COMMITTER_NAME": "Zebra Crossing"}, {"GIT_COMMITTER_EMAIL": "me@zebra-crossing.example"}):
            with self.subTest(who=sorted(who)):
                self.commit({"a.txt": "a\n"}, "An ordinary change", **who)
                self.found(self.scan(), f"commits: 1 of 2 match\n  - {self.head()}\n")
                self.git("reset", "-q", "--hard", "HEAD~1")

    def test_a_mailmap_cannot_give_whoever_made_a_commit_another_name(self):
        """Tried on the writer alone and on the committer alone: where both hold the word, reading either one finds it."""
        (self.repo / ".mailmap").write_text("A Writer <writer@example.org> <zc@example.org>\n", encoding="utf-8")
        self.commit({}, "A mailmap")
        for who in ("AUTHOR", "COMMITTER"):
            with self.subTest(who=who):
                self.commit({"a.txt": "a\n"}, "An ordinary change", **{f"GIT_{who}_NAME": "Zebra Crossing", f"GIT_{who}_EMAIL": "zc@example.org"})
                self.assertEqual(self.git("log", "-1", "--format=%aN %cN").strip(), "A Writer A Writer")
                self.found(self.scan(), "tracked files: 0 of 4 match", f"commits: 1 of 3 match\n  - {self.head()}\n")
                self.git("reset", "-q", "--hard", "HEAD~1")

    def test_a_message_is_read_as_utf8_whatever_git_is_set_to_print_or_to_store(self):
        self.commit({"a.txt": "a\n"}, "Fix the z\u00e9bra crossing")
        self.git("config", "i18n.logOutputEncoding", "ISO-8859-1")
        self.assertIn(b"z\xe9bra", self.git("log", "-1", "--format=%s", raw=True))        # what git prints here, left to itself
        self.found(self.scan(pattern=ACCENTED), f"commits: 1 of 2 match\n  - {self.head()}\n")
        self.git("reset", "-q", "--hard", "HEAD~1")
        message = self.repo.parent / "message"
        message.write_bytes("Fix the z\u00e9bra crossing\n".encode("latin-1"))
        self.git("-c", "i18n.commitEncoding=ISO-8859-1", "commit", "-q", "--allow-empty", "-F", str(message))
        self.assertIn(b"encoding ISO-8859-1\n", self.git("cat-file", "commit", "HEAD", raw=True))
        self.assertIn(b"z\xe9bra", self.git("cat-file", "commit", "HEAD", raw=True))
        self.found(self.scan(pattern=ACCENTED), f"commits: 1 of 2 match\n  - {self.head()}\n")

    def test_what_a_signature_check_says_is_not_read_as_part_of_a_commit(self):
        """Where git is set to check signatures, its log carries what the checker said. That is no one's commit."""
        signer = self.program("gpg", SIGNER) / "gpg"
        for setting, value in (("gpg.program", str(signer)), ("commit.gpgSign", "true"), ("log.showSignature", "true")):
            self.git("config", setting, value)
        self.commit({"a.txt": "a\n"}, "A signed change")
        self.assertIn("BEGIN PGP SIGNATURE", self.git("cat-file", "commit", "HEAD"))
        self.assertIn("checked by the zebra crossing", self.git("log", "-1", "--format=%s"))      # what git prints here, left to itself
        self.passed(self.scan(), "commits: 0 of 2 match")                                         # the newest commit is the signed one
        self.git("config", "commit.gpgSign", "false")
        self.commit({"b.txt": "b\n"}, "A change that is not signed")
        self.passed(self.scan(), "commits: 0 of 3 match")                                         # the signed one is now behind another

    def test_a_word_that_was_committed_and_then_taken_out_is_still_found(self):
        """Every version of a file is read whole. A patch would not do: git leaves a file it takes as binary out of one."""
        for kind, files, goes, left, a_patch_shows_it in (
                ("text", {"notes.txt": "the zebra crossing\n"}, "notes.txt", 2, True),
                ("bytes git takes as binary", {"notes.bin": b"\x00\x01the zebra crossing\x00"}, "notes.bin", 2, False),
                ("marked as not to be compared", {".gitattributes": "*.dat -diff\n", "notes.dat": "the zebra crossing\n"}, "notes.dat", 3, False)):
            with self.subTest(kind=kind):
                self.commit(files, "Add notes")
                held = self.name_of(f"HEAD:{goes}")
                self.git("rm", "-q", goes)
                self.commit({}, "Take the notes out")
                self.assertEqual("zebra" in self.git("log", "--patch", "--format=%s", "-2"), a_patch_shows_it)
                self.found(self.scan(), f"tracked files: 0 of {left} match", "commits: 0 of 3 match", f"{HISTORY}: 1 of ",
                           f"  - object {held}: what a file held")
                self.git("reset", "-q", "--hard", "HEAD~2")

    def test_a_word_in_one_version_of_a_file_among_many_is_found(self):
        self.commit({"notes.txt": "first thoughts\n"}, "Notes")
        self.commit({"notes.txt": "the zebra crossing\n"}, "More notes")
        held = self.name_of("HEAD:notes.txt")
        self.commit({"notes.txt": "second thoughts\n"}, "Fewer notes")
        self.found(self.scan(), "tracked files: 0 of 3 match", "commits: 0 of 4 match", f"{HISTORY}: 1 of 10 match",
                   f"  - object {held}: what a file held")

    def test_a_file_name_that_was_later_changed_is_still_found(self):
        self.commit({"zebra-crossing.txt": "nothing in here\n"}, "A file")
        folder = self.name_of("HEAD^{tree}")
        self.git("mv", "zebra-crossing.txt", "plain.txt")
        self.commit({}, "A plainer name")
        self.found(self.scan(), "tracked files: 0 of 3 match", "commits: 0 of 3 match", f"{HISTORY}: 1 of 7 match",
                   f"  - object {folder}: {BY_NAME.format(folder)}\n")

    def test_a_word_added_by_a_merge_itself_is_found(self):
        self.git("switch", "-q", "-c", "side")
        self.commit({"side.txt": "side\n"}, "On the side")
        self.git("switch", "-q", "main")
        self.commit({"main.txt": "main\n"}, "On main")
        self.git("merge", "-q", "--no-ff", "--no-commit", "side")
        (self.repo / "README.md").write_text("A quiet page, by the zebra crossing.\n", encoding="utf-8")
        self.commit({}, "Merge the side branch")
        held = self.name_of("HEAD:README.md")
        self.commit({"README.md": "A quiet page.\n"}, "Quiet again")
        self.found(self.scan(), "tracked files: 0 of 4 match", "commits: 0 of 5 match", f"{HISTORY}: 1 of ", f"  - object {held}: what a file held")

    def test_a_file_that_was_only_ever_on_a_merged_side_branch_is_found(self):
        """On a pull request this is where everything the branch adds sits: behind the second parent of a merge."""
        self.git("switch", "-q", "-c", "side")
        self.commit({"notes.txt": "the zebra crossing\n"}, "Notes, on the side")
        held = self.name_of("HEAD:notes.txt")
        self.git("rm", "-q", "notes.txt")
        self.commit({}, "Take the notes out again")
        self.git("switch", "-q", "main")
        self.commit({"main.txt": "main\n"}, "On main")
        self.git("merge", "-q", "--no-ff", "-m", "Merge the side branch", "side")
        self.git("branch", "-q", "-D", "side")
        self.found(self.scan(), "tracked files: 0 of 3 match", "commits: 0 of 5 match", f"{HISTORY}: 1 of ", f"  - object {held}: what a file held")

    def test_a_commit_hidden_behind_a_replacement_is_still_found(self):
        """`git replace` shows this computer another commit in a commit's place. GitHub shows the real one."""
        self.commit({"a.txt": "clean\n"}, "A clean stand-in")
        stand_in = self.git("rev-parse", "HEAD").strip()
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.commit({"a.txt": "the zebra crossing\n"}, "Fix the zebra crossing")
        real, held = self.git("rev-parse", "HEAD").strip(), self.name_of("HEAD:a.txt")
        self.git("replace", real, stand_in)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "A clean stand-in")
        self.found(self.scan(), f"commits: 1 of 2 match\n  - {real[:10]}\n", f"{HISTORY}: 1 of 6 match", f"  - object {held}: what a file held")

    def test_a_repository_with_the_longer_names_is_read_the_same_way(self):
        with tempfile.TemporaryDirectory() as folder:
            made = subprocess.run(["git", "init", "-q", "-b", "main", "--object-format=sha256", folder], capture_output=True,
                                  env={"PATH": os.environ["PATH"], **QUIET_GIT})
            if made.returncode:
                self.skipTest("this git cannot make a repository with the longer names")
            (Path(folder) / "docs").mkdir()
            (Path(folder) / "docs" / "zebra-crossing.txt").write_text("nothing in here\n", encoding="utf-8")
            (Path(folder) / "zebra").mkdir()
            (Path(folder) / "zebra" / "crossing.txt").write_text("nor here\n", encoding="utf-8")
            (Path(folder) / "notes.txt").write_text("the zebra crossing\n", encoding="utf-8")
            run_git(folder, "add", "-A")
            run_git(folder, "commit", "-q", "-m", "Fix the zebra crossing")
            commit = run_git(folder, "rev-parse", "HEAD").strip()
            held, by_name, by_path = (run_git(folder, "rev-parse", what).strip()[:10] for what in ("HEAD:notes.txt", "HEAD:docs", "HEAD:zebra"))
            self.assertEqual(len(commit), 64)
            self.found(self.scan(cwd=folder), "tracked files: 3 of 3 match", f"commits: 1 of 1 match\n  - {commit[:10]}\n",
                       f"{HISTORY}: 3 of 6 match", f"  - object {held}: what a file held",
                       f"  - object {by_name}: {BY_NAME.format(by_name)}\n", f"  - object {by_path}: {BY_PATH.format(by_path)}\n")

    def test_a_word_in_the_pull_request_fails_and_says_which_part(self):
        for part, value in (("TITLE", "Zebra crossing"), ("BODY", "First line.\n\nAbout the zebra crossing."),
                            ("BRANCH", "zebra-crossing")):
            with self.subTest(part=part):
                ran = self.scan(GITHUB_EVENT_PATH=self.pull_request(**{part.lower(): value}))
                self.found(ran, "pull request: 1 of 3 match", f"  - the {part.lower()}")
                for other in {"title", "body", "branch"} - {part.lower()}:
                    self.assertNotIn(f"- the {other}", ran.stdout)

    def test_a_file_name_cannot_pass_itself_off_as_a_command_to_the_runner(self):
        """The runner takes a line that begins with `::` as a command, and anything from `##[` on in a line as one too."""
        words = "the zebra crossing\n"
        self.commit({"::error::look.txt": words, "two\n::warning::lines.txt": words, "##[error]older.txt": words,
                     "deep/in##[group]side.txt": words, "three###[x.txt": words}, "Odd names")
        ran = self.scan()
        self.found(ran, "tracked files: 5 of 7 match")
        self.assertEqual([line for line in ran.stdout.splitlines() if line.lstrip().startswith("::")], [])
        self.assertNotIn("##[", ran.stdout)
        for shown in ('"::error::look.txt"', '"two\\n::warning::lines.txt"', '"#\\u0023[error]older.txt"',
                      '"deep/in#\\u0023[group]side.txt"', '"three##\\u0023[x.txt"'):
            self.assertIn(f"  - {shown}\n", ran.stdout)

    # the scan cannot vouch for anything

    def test_no_pattern_fails_where_one_is_expected(self):
        self.refused(self.scan(pattern=None), "no pattern")
        self.refused(self.scan(pattern=""), "no pattern")
        self.refused(self.scan(pattern="  \n"), "no pattern")
        self.refused(self.scan(pattern=None, PRIVATE_WORDS_FROM_FORK="false"), "no pattern")
        self.refused(self.scan(pattern=None, PRIVATE_WORDS_FROM_FORK="yes"), "no pattern")
        self.refused(self.scan(pattern=None, PRIVATE_WORDS_FROM_FORK="True"), "no pattern")

    def test_no_pattern_on_a_pull_request_from_a_fork_is_skipped_out_loud(self):
        self.commit({"notes.txt": "the zebra crossing\n"}, "It is not even looked at")
        ran = self.scan(pattern=None, PRIVATE_WORDS_FROM_FORK="true")
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertTrue(ran.stdout.startswith("::notice title=private-words::skipped"), ran.stdout)
        self.assertIn("private words: skipped", ran.stdout)
        self.assertNotIn("none found", ran.stdout)
        self.assertNotIn("match", ran.stdout)

    def test_a_fork_that_does_have_the_pattern_is_scanned_like_any_other(self):
        self.commit({"notes.txt": "the zebra crossing\n"}, "Notes")
        self.found(self.scan(PRIVATE_WORDS_FROM_FORK="true"), '"notes.txt"')

    def test_a_pattern_that_cannot_be_used_fails_and_prints_nothing_of_the_scan(self):
        self.commit({"notes.txt": "the zebra crossing\n"}, "Notes")
        self.refused(self.scan(pattern="x*"), "cannot vouch", "matches everything")
        for pattern in ("zebra[crossing", "(?P<zebra>a)(?P<zebra>b)", "(" * 3000 + "zebra crossing" + ")" * 3000,
                        "zebra{99999999999999999999}", "(?a)(?u)zebra crossing", "[[zebra]crossing"):
            with self.subTest(pattern=pattern[:30]):
                self.refused_saying(self.scan(pattern=pattern), NOT_A_PATTERN)

    def test_a_pattern_typed_one_word_to_a_line_fails(self):
        """As one pattern it would match nothing anywhere, and every scan would pass."""
        self.commit({"notes.txt": "the zebra crossing\n"}, "Notes")
        for pattern in ("zebra crossing\n4200", "zebra crossing\r\n4200", "zebra\rcrossing"):
            with self.subTest(pattern=pattern):
                self.refused_saying(self.scan(pattern=pattern), "the private pattern is on more than one line, and it must be one line")

    def test_a_pull_request_that_cannot_be_read_fails(self):
        whole = {"title": "A title", "body": "A body", "head": {"ref": "a-branch"}}
        for what, event in (("bytes that are not text", b"\xff\xfe{"), ("text that is not JSON", b"{"), ("nothing", b""),
                            ("a list", ["pull_request"]), ("a word", "pull_request"), ("brackets nested too deeply", b"[" * 100_000),
                            ("an empty list", []), ("some other word", "push"), ("a number", 7), ("null", None),
                            ("a pull request that is null", {"pull_request": None}),
                            ("a pull request that is a list", {"pull_request": [whole]}),
                            ("a pull request that is a word", {"pull_request": "zebra crossing"}),
                            ("no title", {"pull_request": {**whole, "title": None}}),
                            ("a title left out", {"pull_request": {"body": "A body", "head": {"ref": "a-branch"}}}),
                            ("a title that is a number", {"pull_request": {**whole, "title": 7}}),
                            ("a body left out", {"pull_request": {"title": "A title", "head": {"ref": "a-branch"}}}),
                            ("a body that is a number", {"pull_request": {**whole, "body": 0}}),
                            ("a body that is a list", {"pull_request": {**whole, "body": []}}),
                            ("no branch", {"pull_request": {**whole, "head": {}}}),
                            ("a head that is a word", {"pull_request": {**whole, "head": "a-branch"}}),
                            ("a head left out", {"pull_request": {"title": "A title", "body": "A body"}}),
                            ("a branch that is a list", {"pull_request": {**whole, "head": {"ref": ["zebra crossing"]}}})):
            with self.subTest(what=what):
                self.refused(self.scan(GITHUB_EVENT_PATH=self.event(event)), "cannot vouch", "pull request")
        self.refused(self.scan(GITHUB_EVENT_PATH=str(self.repo.parent / "no-such-file.json")), "cannot vouch", "pull request")
        self.refused(self.scan(GITHUB_EVENT_PATH=str(self.repo)), "cannot vouch", "pull request")            # a folder

    def test_a_folder_that_is_not_a_repository_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            self.refused_saying(self.scan(cwd=folder), "this git command ended with status 128; run it by hand in this folder "
                                                       f"to see why: {asked_of_git('')['rev-parse']}")

    def test_a_repository_with_no_commit_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            self.git("init", "-q", "-b", "main", cwd=folder)
            self.refused_saying(self.scan(cwd=folder), "this git command ended with status 128; run it by hand in this folder "
                                                       f"to see why: {SECOND_REV_PARSE}")

    def test_a_tracked_file_missing_from_the_folder_fails(self):
        (self.repo / "README.md").unlink()
        self.refused(self.scan(), "not whole")

    def test_a_folder_where_a_tracked_file_should_be_fails(self):
        (self.repo / "README.md").unlink()
        (self.repo / "README.md").mkdir()
        self.refused(self.scan(), "not whole")

    def test_a_tracked_file_that_cannot_be_read_is_a_refusal_and_not_a_find(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("these tests are running as root, which can read any file, so no file can be made unreadable")
        (self.repo / "README.md").chmod(0)
        self.addCleanup((self.repo / "README.md").chmod, 0o644)
        self.refused_saying(self.scan(), 'the tracked file "README.md" could not be read')

    def test_a_file_the_disk_will_not_give_up_is_a_refusal_without_the_disks_own_words(self):
        really_open = open

        def closed(path, *args, **more):
            if isinstance(path, (str, bytes, os.PathLike)) and os.fsdecode(path).endswith("code.py"):
                raise OSError(5, "the zebra crossing is closed")
            return really_open(path, *args, **more)
        with mock.patch("builtins.open", side_effect=closed):
            ran = self.scan()
        self.refused_saying(ran, 'the tracked file "src/code.py" could not be read')

    def test_an_error_nobody_foresaw_is_a_refusal_that_gives_only_its_kind(self):
        """A traceback would end with 1, which is kept for "found", and could print what the error was about."""
        for trouble in (RuntimeError("at the zebra crossing"), MemoryError(), KeyError("zebra crossing"), UnicodeError("zebra crossing")):
            with self.subTest(trouble=type(trouble).__name__), mock.patch.object(self.script, "git", side_effect=trouble):
                self.refused_saying(self.scan(), f"an error the scan did not foresee stopped it ({type(trouble).__name__})")

    def test_a_shallow_clone_fails_because_its_history_is_missing(self):
        self.commit({"a.txt": "a\n"}, "Second")
        with tempfile.TemporaryDirectory() as folder:
            self.git("clone", "-q", "--depth", "1", self.repo.as_uri(), "shallow", cwd=folder)
            self.refused(self.scan(cwd=Path(folder) / "shallow"), "shallow")

    def test_a_history_cut_short_by_a_grafts_file_fails(self):
        """A grafts file gives a commit other parents on this computer alone, as a shallow clone does. GitHub has the real ones."""
        self.commit({"notes.txt": "the zebra crossing\n"}, "Notes")
        self.git("rm", "-q", "notes.txt")
        self.commit({}, "Take the notes out")
        grafts = self.repo / ".git" / "info" / "grafts"
        grafts.parent.mkdir(exist_ok=True)
        grafts.write_text("\n", encoding="utf-8")                 # a grafts file with nothing in it changes nothing
        self.found(self.scan(), "commits: 0 of 3 match", f"{HISTORY}: 1 of ")
        grafts.write_text(self.git("rev-parse", "HEAD"), encoding="utf-8")        # "this commit has no parents"
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), "1")
        for started_in in (self.repo, self.repo / "src"):
            with self.subTest(started_in=started_in.name):
                self.refused(self.scan(cwd=started_in), "grafts")

    def test_git_that_cannot_be_run_fails(self):
        for trouble in (FileNotFoundError("no git here"), PermissionError("not allowed")):
            with self.subTest(trouble=type(trouble).__name__), mock.patch.object(self.script.subprocess, "run", side_effect=trouble):
                self.refused_saying(self.scan(), "git could not be run here")

    def test_the_time_git_is_given_is_a_minute(self):
        """Well inside the five minutes the job on GitHub has, so a git that hangs is named and not just cut off."""
        self.assertEqual(self.script.GIT_SECONDS, 60)
        with mock.patch.object(self.script.subprocess, "run", side_effect=subprocess.TimeoutExpired(["git"], 60)):
            self.refused_saying(self.scan(), f"this git command did not answer within 60 seconds: {asked_of_git('')['rev-parse']}")


class WhatGitSays(Repository):
    """The scan against answers git should never give, and against ones too rare to make with a real repository."""

    A, B, C, D = b"a" * 40, b"b" * 40, b"c" * 40, b"d" * 40     # object names; C is the commit in kept()
    RAW = bytes(range(1, 21))                                   # a hash as a folder list holds it: 20 raw bytes

    def with_git_saying(self, **said):
        """The script's git, except that the commands named here (rev_parse, ls_files, log, rev_list, cat_file) give back these bytes.

        What is given for a command may also be a function of its arguments, which gives back bytes, or None to let git answer.
        """
        real = self.script.git

        def git(repo, *args, **more):
            answer = said.get(args[0].replace("-", "_"))
            answer = answer(args) if callable(answer) else answer
            return real(repo, *args, **more) if answer is None else answer
        return mock.patch.object(self.script, "git", side_effect=git)

    def entry(self, name, raw=RAW, mode=b"100644"):
        """One line of a folder list as git stores it: the mode, a space, the name, a NUL and the raw hash."""
        return mode + b" " + name + b"\0" + raw

    def folder(self, *names, raw=RAW):
        return b"".join(self.entry(name, raw) for name in names)

    def below(self, name, folder, mode=b"40000"):
        """The line that lists a folder inside another, by the inner folder's name as git asks for it."""
        return self.entry(name, bytes.fromhex(folder.decode()), mode)

    def answer(self, name, kind, held):
        return name + b" " + kind + b" " + str(len(held)).encode() + b"\n" + held + b"\n"

    def kept(self, root, *more, commit=None):
        """What git says of a history of one commit, C, whose root folder, A, holds this list.

        `more` is every other object, each as (name, kind, what it holds).
        """
        commit = b"tree " + self.A + b"\nauthor A Writer <writer@example.org> 1700000000 +0000\n\nA quiet message\n" if commit is None else commit
        objects = ((self.C, b"commit", commit), (self.A, b"tree", root), *more)
        return {"rev_list": b"".join(name + b"\n" for name, _, _ in objects), "cat_file": b"".join(self.answer(*one) for one in objects)}

    def test_a_repository_git_does_not_call_whole_fails(self):
        head = self.git("rev-parse", "HEAD").strip().encode()
        for what, answer, said in (("a shallow clone", head + b"\ntrue\n.git/info/grafts\n", "shallow"),
                                   ("an answer that is neither yes nor no", head + b"\nperhaps\n.git/info/grafts\n", "did not describe"),
                                   ("no word on the history or the grafts file", head + b"\n", "did not describe"),
                                   ("no grafts file named", head + b"\nfalse\n", "did not describe"),
                                   ("a commit not named in full", head[:39] + b"\nfalse\n.git/info/grafts\n", "did not describe"),
                                   ("a commit named in capitals", head.upper() + b"\nfalse\n.git/info/grafts\n", "did not describe"),
                                   ("more before the commit", b"x" + head + b"\nfalse\n.git/info/grafts\n", "did not describe"),
                                   ("nothing at all", b"", "did not describe")):
            with self.subTest(what=what), self.with_git_saying(rev_parse=lambda args, answer=answer: answer if "--git-path" in args else None):
                self.refused(self.scan(), said)
        for what, answer in (("nothing at all", b""), ("no line end", os.fsencode(self.repo)), ("a line end and no more", b"\n")):
            with self.subTest(what=what), self.with_git_saying(rev_parse=lambda args, answer=answer: answer if "--show-toplevel" in args else None):
                self.refused(self.scan(), "did not describe")

    def test_a_list_of_tracked_files_that_does_not_come_back_entry_by_entry_fails(self):
        entry = b"100644 " + self.A + b" 0\tREADME.md\0"
        for what, listed in (("no tab before a name", b"100644 " + self.A + b" 0 README.md\0"), ("no name", b"100644 " + self.A + b" 0\t\0"),
                             ("no end to the last entry", entry + b"100644 " + self.A + b" 0\tsrc/code.py"),
                             ("a mode that is not a number", b"10x644 " + self.A + b" 0\tREADME.md\0"),
                             ("nothing before the tab", b"\tREADME.md\0")):
            with self.subTest(what=what), self.with_git_saying(ls_files=listed):
                self.refused(self.scan(), "tracked files", "entry by entry")
        with self.with_git_saying(ls_files=entry):
            self.passed(self.scan(), "tracked files: 0 of 1 match")

    def test_a_history_that_does_not_come_back_commit_by_commit_fails(self):
        name = self.A
        for log in (b"stray\0" + name + b"\0text", b"\0not-a-commit\0text", b"\0" + name + b"z\0text", b"\0" + name[:39] + b"\0text",
                    b"\0" + name, b"\0" + name + b"\0text\0" + name, b"\0" + name.upper() + b"\0text"):
            with self.subTest(log=log[:14]), self.with_git_saying(log=log):
                self.refused(self.scan(), "cannot vouch", "commit by commit")

    def test_a_commit_is_known_by_a_name_of_either_length(self):
        for name in (b"a" * 40, b"0123456789abcdef" * 4):
            with self.subTest(length=len(name)), self.with_git_saying(log=b"\0" + name + b"\0A Writer\nquiet text\n"):
                self.passed(self.scan(), "commits: 0 of 1 match")
            with self.subTest(length=len(name), found=True), self.with_git_saying(log=b"\0" + name + b"\0the zebra crossing\n"):
                self.found(self.scan(), "commits: 1 of 1 match", "  - " + name[:10].decode())

    def test_only_a_whole_hash_is_cut_out_of_what_a_commit_says(self):
        """A hash is 40 or 64 of the digits and the letters a to f, with none of those hard against either end."""
        hash_like = "4200" + "a" * 36
        for what, said, matches in (("a run of 40", f"See {hash_like}.", 0), ("a run of 64", f"See {hash_like}{'b' * 24}.", 0),
                                    ("a run of 40 at the very start and end", hash_like, 0),
                                    ("two of them on a line", f"Merge {hash_like} into {'b' * 36}4200", 0),
                                    ("a run of 39", f"See {hash_like[:39]}.", 1), ("a run of 41", f"See {hash_like}a.", 1),
                                    ("a run of 63", f"See {hash_like}{'b' * 23}.", 1), ("a run of 65", f"See {hash_like}{'b' * 25}.", 1),
                                    ("a run of 40 with a digit hard before it", f"See 7{hash_like}.", 1),
                                    ("capitals, which git never writes", f"See {hash_like.upper()}.", 1),
                                    ("words on both sides of a hash, which cutting it out must not join", f"zebra {'a' * 40} crossing", 0),
                                    ("a word beside a hash", f"{'a' * 40} zebra crossing {'b' * 64}", 1)):
            with self.subTest(what=what), self.with_git_saying(log=b"\0" + self.A + b"\0A Writer\n" + said.encode() + b"\n"):
                ran = self.scan()
                self.assertEqual(ran.returncode, 1 if matches else 0, ran.said)
                self.assertIn(f"commits: {matches} of 1 match", ran.stdout)

    def test_objects_that_do_not_come_back_whole_fail(self):
        a, b, quiet = self.A, self.B, self.folder(b"plain.txt")
        for what, asked, answer in (
                ("nothing at all", [a], b""),
                ("an object git does not have", [a], a + b" missing\n"),
                ("another object's name", [a], b + b" blob 3\nabc\n"),
                ("a size that is not a number", [a], a + b" blob x\nabc\n"),
                ("a size below nought", [a], a + b" blob -1\nabc\n"),
                ("a size below nought and nothing after it", [a], a + b" blob -1\n"),
                ("fewer bytes than the size says", [a], a + b" blob 5\nabc\n"),
                ("more bytes than the size says", [a], a + b" blob 3\nabcd\n"),
                ("no line end after the bytes", [a], a + b" blob 3\nabc"),
                ("something other than a line end between two objects", [a, b], a + b" blob 3\nabcX" + b + b" blob 3\nabc\n"),
                ("more after the last object", [a], a + b" blob 3\nabc\nand more"),
                ("a first line with too much on it", [a], a + b" blob 3 more\nabc\n"),
                ("a kind of object the scan does not know", [a], a + b" tag 3\nabc\n"),
                ("fewer objects than were asked for", [a, b], a + b" blob 3\nabc\n")):
            with self.subTest(what=what), self.with_git_saying(rev_list=b"\n".join(asked) + b"\n", cat_file=answer):
                self.refused(self.scan(), "cannot vouch", "did not come back whole")
        for what, said in (
                ("a folder list with no end to a name", self.kept(b"100644 name")),
                ("a folder list with no mode before its first name", self.kept(b"name\0" + self.RAW + self.entry(b"other"))),
                ("a folder list cut short", self.kept(b"100644 name\0" + self.RAW[:18])),
                ("a mode that is not a number", self.kept(b"10x644 plain.txt\0" + self.RAW)),
                ("a commit whose root folder did not come back", self.kept(quiet, commit=b"tree " + b + b"\n\nquiet\n")),
                ("a commit that does not begin with its root folder", self.kept(quiet, commit=b"author A Writer\ntree " + a + b"\n\nquiet\n")),
                ("a commit whose first line names a folder and is not `tree`", self.kept(quiet, commit=b"tram " + a + b"\n\nquiet\n")),
                ("a commit whose root folder is not named in full", self.kept(quiet, commit=b"tree " + a[:39] + b"\n\nquiet\n")),
                ("a commit with nothing in it", self.kept(quiet, commit=b"")),
                ("a folder inside a folder that did not come back", self.kept(self.below(b"docs", b))),
                ("a folder that no commit leads to", self.kept(quiet, (b, b"tree", quiet)))):
            with self.subTest(what=what), self.with_git_saying(**said):
                self.refused(self.scan(), "cannot vouch", "did not come back whole")

    def test_a_folder_matches_on_any_name_it_lists_and_on_nothing_else(self):
        hash_that_spells_it = b"zebra crossing 4200!"
        self.assertEqual(len(hash_that_spells_it), 20)
        for what, names, raw, matches in (("the last name of three", (b"plain.txt", b"with spaces in it.txt", b"zebra crossing.txt"), self.RAW, 1),
                                          ("the first name", (b"4,200 of them", b"plain.txt"), self.RAW, 1),
                                          ("no name, though a hash spells it", (b"plain.txt", b"other.txt"), hash_that_spells_it, 0),
                                          ("no name, though a name and the hash after it spell it", (b"zebra", b"plain.txt"),
                                           b"crossing, and others", 0),
                                          ("no name, though one name and the next spell it", (b"zebra", b"crossing"), self.RAW, 0),
                                          ("an empty folder", (), self.RAW, 0)):
            with self.subTest(what=what), self.with_git_saying(**self.kept(self.folder(*names, raw=raw))):
                ran = self.scan()
                self.assertEqual(ran.returncode, 1 if matches else 0, ran.said)
                self.assertIn(f"{HISTORY}: {matches} of 1 match", ran.stdout)
                if matches:
                    self.assertIn(f"  - object aaaaaaaaaa: {BY_NAME.format('aaaaaaaaaa')}\n", ran.stdout)

    def test_a_name_is_read_with_every_folder_above_it(self):
        b, d = self.B, self.D
        inner = (b, b"tree", self.folder(b"crossing.txt", b"other.txt"))
        by_path = "  - object {0}: " + BY_PATH + "\n"
        for what, root, more, pattern, shown in (
                ("a folder and a file in it", self.below(b"zebra", b), [inner], PATTERN, [by_path.format("bbbbbbbbbb")]),
                ("a slash goes between a folder and a name", self.below(b"zebra", b), [inner], "zebra/crossing", [by_path.format("bbbbbbbbbb")]),
                ("no slash goes before the first folder", self.below(b"zebra", b), [inner], "/zebra", []),
                ("one folder under two names, the quiet one first", self.below(b"plain", b) + self.below(b"zebra", b), [inner], PATTERN,
                 [by_path.format("bbbbbbbbbb")]),
                ("one folder under two names, the quiet one last", self.below(b"zebra", b) + self.below(b"zzz", b), [inner], PATTERN,
                 [by_path.format("bbbbbbbbbb")]),
                ("three folders deep", self.below(b"zebra", b), [(b, b"tree", self.below(b"-", d)), (d, b"tree", self.folder(b"crossing"))],
                 PATTERN, [by_path.format("dddddddddd")]),
                ("a folder written with a nought before its mode, as some old tools did", self.below(b"zebra", b, b"040000"), [inner], PATTERN,
                 [by_path.format("bbbbbbbbbb")]),
                ("a name that matches alone says so, wherever the folder is",
                 self.below(b"zebra", b), [(b, b"tree", self.folder(b"crossing", b"zebra crossing.txt"))], PATTERN,
                 ["  - object bbbbbbbbbb: " + BY_NAME.format("bbbbbbbbbb") + "\n"]),
                ("a slash goes after a folder", self.below(b"zebra", b), [inner], "zebra/", [by_path.format("aaaaaaaaaa")]),
                ("no slash goes after a file", self.entry(b"zebra"), [], "zebra/", []),
                ("what is below a folder that matches is not listed again for that",
                 self.below(b"zebra crossing", b), [(b, b"tree", self.below(b"docs", d)), (d, b"tree", self.folder(b"plain.txt"))], PATTERN,
                 ["  - object aaaaaaaaaa: " + BY_NAME.format("aaaaaaaaaa") + "\n"]),
                ("what is below a path that matches is not listed again for that",
                 self.below(b"zebra", b), [(b, b"tree", self.below(b"crossing", d)), (d, b"tree", self.folder(b"plain.txt"))], PATTERN,
                 [by_path.format("bbbbbbbbbb")]),
                ("but a name below that matches alone is listed for itself",
                 self.below(b"zebra crossing", b), [(b, b"tree", self.folder(b"plain.txt", b"4200.txt"))], PATTERN,
                 ["  - object aaaaaaaaaa: " + BY_NAME.format("aaaaaaaaaa") + "\n", "  - object bbbbbbbbbb: " + BY_NAME.format("bbbbbbbbbb") + "\n"]),
                ("and it says so whichever name comes first",
                 self.below(b"zebra", b), [(b, b"tree", self.folder(b"zebra crossing.txt", b"crossing"))], PATTERN,
                 ["  - object bbbbbbbbbb: " + BY_NAME.format("bbbbbbbbbb") + "\n"]),
                ("a file is not opened as a folder", self.entry(b"zebra", bytes.fromhex(b.decode())), [], PATTERN, []),
                ("a submodule is not opened as a folder", self.below(b"zebra", b, b"160000"), [], PATTERN, [])):
            with self.subTest(what=what), self.with_git_saying(**self.kept(root, *more)):
                ran = self.scan(pattern=pattern)
                self.assertEqual(ran.returncode, 1 if shown else 0, ran.said)
                self.assertIn(f"{HISTORY}: {len(shown)} of {1 + len(more)} match\n{''.join(shown)}pull request:", ran.stdout)

    def test_the_mode_before_a_name_is_no_part_of_the_name(self):
        for pattern in ("100644", "644 plain", "4 plain", "[ ]plain", "plain"):
            with self.subTest(pattern=pattern), self.with_git_saying(**self.kept(self.folder(b"plain.txt"))):
                ran = self.scan(pattern=pattern)
                self.assertIn(f"{HISTORY}: {1 if pattern == 'plain' else 0} of 1 match", ran.stdout)

    def test_a_folder_with_the_longer_names_is_read_by_their_length(self):
        commit, long_name, raw = b"c" * 64, b"0123456789abcdef" * 4, bytes(range(1, 33))
        said = {"rev_list": commit + b"\n" + long_name + b"\n",
                "cat_file": self.answer(commit, b"commit", b"tree " + long_name + b"\n\nquiet\n")
                + self.answer(long_name, b"tree", self.folder(b"plain.txt", b"zebra crossing.txt", raw=raw))}
        with self.with_git_saying(**said):
            self.found(self.scan(), f"{HISTORY}: 1 of 1 match", f"  - object 0123456789: {BY_NAME.format('0123456789')}\n")

    def test_a_commit_among_the_objects_is_left_to_the_reading_of_commits(self):
        """Its people and its message have been read already, and the rest is hashes, dates and what git's own tools add."""
        loud = b"tree " + self.A + b"\nauthor Zebra Crossing <zc@example.org> 4200 +0000\n\nthe zebra crossing\n"
        with self.with_git_saying(**self.kept(self.folder(b"plain.txt"), (self.B, b"blob", b"quiet\n"), commit=loud)):
            self.passed(self.scan(), f"{HISTORY}: 0 of 2 match")

    def test_git_is_asked_exactly_this_and_for_each_object_once(self):
        asked = []
        real = self.script.git

        def git(repo, *args, **more):
            asked.append((Path(os.fsdecode(repo)).resolve(), args, more))
            return real(repo, *args, **more)
        (self.repo / "src" / "deep").mkdir()
        with mock.patch.object(self.script, "git", side_effect=git):
            self.assertEqual(self.scan(cwd=self.repo / "src" / "deep").returncode, 0)
        ask = asked_of_git(self.git("rev-parse", "HEAD").strip())
        self.assertEqual([shlex.join(["git", "--no-replace-objects", *args]) for _, args, _ in asked],
                         [ask["rev-parse"], SECOND_REV_PARSE, ask["ls-files"], ask["log"], ask["rev-list"], ask["cat-file"]])
        self.assertEqual([where for where, _, _ in asked], [(self.repo / "src" / "deep").resolve()] + [self.repo.resolve()] * 5)
        listed = asked[-1][2]["stdin"].split()
        self.assertEqual(len(listed), 5)                                    # one commit, two folders, two files
        self.assertEqual(sorted(listed), sorted(self.git("rev-list", "--objects", "--no-object-names", "HEAD").encode().split()))


class Command(Repository):
    """The script run as a process of its own."""

    def test_the_command_passes_on_a_clean_repository(self):
        ran = self.run_script(PRIVATE_WORDS=PATTERN)
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertTrue(ran.stdout.endswith("private words: none found\n"))
        self.assertEqual(ran.stderr, "")

    def test_the_command_fails_when_a_word_is_there_or_the_pull_request_names_it(self):
        self.found(self.run_script(PRIVATE_WORDS=PATTERN, GITHUB_EVENT_PATH=self.pull_request(title="The zebra crossing")), "  - the title")
        self.commit({"notes.txt": "the zebra crossing\n"}, "Notes")
        self.found(self.run_script(PRIVATE_WORDS=PATTERN), '  - "notes.txt"')

    def test_the_command_ends_with_two_when_it_cannot_vouch(self):
        self.refused(self.run_script(), "no pattern")
        self.refused_saying(self.run_script(PRIVATE_WORDS="zebra[crossing"), NOT_A_PATTERN)
        self.refused_saying(self.run_script(PRIVATE_WORDS="[[zebra]crossing"), NOT_A_PATTERN)      # Python would only warn

    def test_the_command_skips_out_loud_for_a_fork(self):
        ran = self.run_script(PRIVATE_WORDS_FROM_FORK="true")
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertIn("skipped", ran.stdout)

    def test_the_event_file_is_read_as_utf8_whatever_this_computer_would_read_it_as(self):
        told_to_use_ascii = {"LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
        ran = self.run_script(PRIVATE_WORDS=ACCENTED, GITHUB_EVENT_PATH=self.pull_request(title="The Z\u00e9bra Crossing"), **told_to_use_ascii)
        self.found(ran, "pull request: 1 of 3 match\n  - the title\n")

    def test_run_as_github_runs_it_the_command_takes_no_code_from_the_folder_it_is_in(self):
        """GitHub runs it with `-I`, so that a file beside the script named like a module it imports is never run in its place."""
        tools = self.repo.parent / "tools"
        tools.mkdir()
        shutil.copy(SCRIPT, tools / "private_words.py")
        (tools / "json.py").write_text("print('planted beside the script')\n", encoding="utf-8")
        beside = self.run_script(script=tools / "private_words.py", PRIVATE_WORDS=PATTERN)
        self.assertIn("planted beside the script", beside.stdout)                   # without it, the planted file runs
        ran = self.run_script("-I", script=tools / "private_words.py", PRIVATE_WORDS=PATTERN)
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertEqual(ran.stdout, self.run_script(PRIVATE_WORDS=PATTERN).stdout)
        self.assertEqual(ran.stderr, "")


class GitThatGoesWrong(Repository):
    """The script against a stand-in for git that goes wrong for one command at a time, or says more than it should."""

    COMMANDS = ("rev-parse", "ls-files", "log", "rev-list", "cat-file")

    def test_left_alone_the_stand_in_is_git_and_is_never_handed_the_pattern(self):
        record = self.repo.parent / "record"
        ran = self.run_script(PRIVATE_WORDS=PATTERN, **self.stand_in_git("nothing", "no command", record))
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertEqual(ran.stdout, self.run_script(PRIVATE_WORDS=PATTERN).stdout)
        self.assertEqual(record.read_text(encoding="utf-8").splitlines(),
                         ["ran rev-parse", "ran rev-parse", "ran ls-files", "ran log", "ran rev-list", "ran cat-file"])

    def test_a_git_command_that_fails_is_named_and_what_it_said_is_kept_out(self):
        ask = asked_of_git(self.git("rev-parse", "HEAD").strip())
        for command in self.COMMANDS:
            with self.subTest(command=command):
                ran = self.run_script(PRIVATE_WORDS=PATTERN, **self.stand_in_git("fails, with the words in what it says", command))
                self.refused_saying(ran, f"this git command ended with status 3; run it by hand in this folder to see why: {ask[command]}")

    def test_a_git_command_killed_part_way_is_not_believed(self):
        ask = asked_of_git(self.git("rev-parse", "HEAD").strip())
        for command in self.COMMANDS:
            with self.subTest(command=command):
                ran = self.run_script(PRIVATE_WORDS=PATTERN, **self.stand_in_git("is killed part-way", command))
                self.refused_saying(ran, f"this git command ended with status -9; run it by hand in this folder to see why: {ask[command]}")

    def test_what_git_grumbles_while_it_works_is_kept_out(self):
        self.commit({"notes.txt": "the zebra crossing\n"}, "Notes")
        ran = self.run_script(PRIVATE_WORDS=PATTERN, **self.stand_in_git("grumbles, with the words in what it says", "every command"))
        self.found(ran, '  - "notes.txt"')
        self.assertEqual(ran.stderr, "")

    def test_a_git_command_that_never_answers_is_stopped_and_named(self):
        ask = asked_of_git(self.git("rev-parse", "HEAD").strip())
        with mock.patch.object(self.script, "GIT_SECONDS", 1):
            ran = self.scan(around=self.stand_in_git("never answers", "log"))
        self.refused_saying(ran, f"this git command did not answer within 1 seconds: {ask['log']}")


if __name__ == "__main__":
    unittest.main()
