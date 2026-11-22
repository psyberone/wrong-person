"""The scan for the private words guards what the public can read, so it is tested like code.

Every test builds a small git repository of its own and scans it with a stand-in
pattern. The real pattern is never in this repository.
"""
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "private_words.py"
PATTERN = r"zebra[^a-z]{0,3}crossing|4[,.]?200"        # a stand-in: two words with up to three marks between, or a number
WORD = "zebra"                                          # what must never be printed
HISTORY = "files and folders in the history"            # the row for every version of every file, and every folder list
QUIET_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}
SOMEONE = {"GIT_AUTHOR_NAME": "A Writer", "GIT_AUTHOR_EMAIL": "writer@example.org",
           "GIT_COMMITTER_NAME": "A Writer", "GIT_COMMITTER_EMAIL": "writer@example.org"}


def load():
    """The script as a module; it lives outside the package, so it is loaded by path."""
    spec = importlib.util.spec_from_file_location("private_words", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_git(folder, *args, **env):
    """A git command in a folder, kept away from this machine's own settings -> what it printed."""
    done = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, timeout=60,
                          env={"PATH": os.environ["PATH"], **QUIET_GIT, **SOMEONE, **env})
    if done.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout


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

    def git(self, *args, cwd=None, **env):
        return run_git(cwd or self.repo, *args, **env)

    def commit(self, files, message, **env):
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message, **env)

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

    def scan(self, cwd=None, pattern=PATTERN, **env):
        """Scan by calling the script's main.

        While it runs, this process's environment is cut down to a path and the
        quiet settings, so the script's git reads neither this machine's settings
        nor a GIT_DIR left by a hook that happens to be running the tests.
        """
        environ = {**({} if pattern is None else {"PRIVATE_WORDS": pattern}), **env}
        bare = {"PATH": os.environ["PATH"], **QUIET_GIT}
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, bare, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = self.script.main(environ, cwd or self.repo)
        return self.never_tells(Scanned(status, out.getvalue(), err.getvalue()), pattern)

    def found(self, ran, *said):
        self.assertEqual(ran.returncode, 1, ran.said)
        self.assertIn("FOUND", ran.stdout)
        for words in said:
            self.assertIn(words, ran.stdout)

    def refused(self, ran, *said):
        self.assertEqual(ran.returncode, 2, ran.said)
        self.assertEqual(ran.stdout, "")
        for words in said:
            self.assertIn(words, ran.stderr)


class Pattern(unittest.TestCase):
    def setUp(self):
        self.script = load()

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

    def test_a_pattern_that_cannot_be_read_is_refused_without_repeating_it(self):
        for pattern in ("zebra[crossing", "(zebra", "zebra)", "*zebra"):
            with self.subTest(pattern=pattern):
                with self.assertRaises(self.script.CannotVouch) as refusal:
                    self.script.searcher(pattern)
                self.assertIn("not a valid pattern", str(refusal.exception))
                self.assertNotIn(WORD, str(refusal.exception))
                self.assertIsNone(refusal.exception.__cause__)      # a cause would carry the pattern into a traceback
                self.assertTrue(refusal.exception.__suppress_context__)

    def test_a_pattern_that_matches_nothing_at_all_in_particular_is_refused(self):
        for pattern in ("x*", "zebra crossing|", "()", "(zebra)?"):
            with self.subTest(pattern=pattern):
                with self.assertRaises(self.script.CannotVouch) as refusal:
                    self.script.searcher(pattern)
                self.assertIn("matches everything", str(refusal.exception))


class Scan(Repository):
    # nothing to find

    def test_a_clean_repository_passes_and_says_what_it_looked_at(self):
        ran = self.scan()
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertEqual(ran.stdout, "tracked files: 0 of 2 match\ncommits: 0 of 1 match\n"
                                     f"{HISTORY}: 0 of 4 match\npull request: 0 of 0 match\nprivate words: none found\n")
        self.assertEqual(ran.stderr, "")

    def test_a_clean_pull_request_passes(self):
        ran = self.scan(PRIVATE_WORDS_TITLE="Add a thing", PRIVATE_WORDS_BODY="It adds a thing.\n\nTwo paragraphs.",
                        PRIVATE_WORDS_BRANCH="add-a-thing")
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertIn("pull request: 0 of 3 match", ran.stdout)

    def test_a_part_of_a_pull_request_that_is_empty_is_not_counted(self):
        ran = self.scan(PRIVATE_WORDS_TITLE="Add a thing", PRIVATE_WORDS_BODY="", PRIVATE_WORDS_BRANCH="add-a-thing")
        self.assertIn("pull request: 0 of 2 match", ran.stdout)

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
                ran = self.scan(pattern=pattern)
                self.assertEqual(ran.returncode, 0, ran.said)
                self.assertIn("commits: 0 of 2 match", ran.stdout)
                self.assertIn(f"{HISTORY}: 0 of 6 match", ran.stdout)

    def test_a_file_is_read_by_its_size_whatever_it_holds(self):
        looks_like_git = b"0" * 40 + b" blob 3\nabc\n" + b"1" * 40 + b" missing\n"
        self.commit({"empty.txt": b"", "odd.txt": looks_like_git, "late.bin": b"a\n" * 5000 + b"\x00 and then more"}, "Odd files")
        ran = self.scan()
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertIn("tracked files: 0 of 5 match", ran.stdout)
        self.assertIn(f"{HISTORY}: 0 of 8 match", ran.stdout)

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
        self.found(self.scan(), "tracked files: 1 of 3 match\n  - (a file whose own name matches; name withheld)\n",
                   f"{HISTORY}: 1 of 7 match\n"
                   f"  - object {folder}: a folder that lists a name that matches (its list: git cat-file -p {folder})\n")

    def test_a_word_in_bytes_that_are_not_text_is_still_found(self):
        self.commit({"blob.bin": b"\xff\xfe\x00zebra crossing\x00\xff"}, "A blob")
        self.found(self.scan(), '  - "blob.bin"', f"{HISTORY}: 1 of 6 match", f"  - object {self.name_of('HEAD:blob.bin')}: what a file held")

    def test_a_link_is_read_as_where_it_points_and_never_followed(self):
        os.symlink("../zebra-crossing/elsewhere", self.repo / "pointer")
        os.symlink("nowhere-at-all", self.repo / "dangling")
        self.commit({}, "Two links")
        self.found(self.scan(), "tracked files: 1 of 4 match", '"pointer"', f"{HISTORY}: 1 of 7 match")

    def test_a_dangling_link_is_not_an_error(self):
        os.symlink("nowhere-at-all", self.repo / "dangling")
        self.commit({}, "A link")
        self.assertEqual(self.scan().returncode, 0)

    def test_a_word_in_a_commit_message_fails_and_names_the_commit(self):
        self.commit({"a.txt": "a\n"}, "Fix the zebra crossing")
        self.found(self.scan(), "tracked files: 0 of 3 match", f"commits: 1 of 2 match\n  - {self.head()}\n", f"{HISTORY}: 0 of 6 match")

    def test_a_word_in_who_made_a_commit_fails(self):
        for who in ({"GIT_AUTHOR_NAME": "Zebra Crossing"}, {"GIT_AUTHOR_EMAIL": "me@zebra-crossing.example"},
                    {"GIT_COMMITTER_NAME": "Zebra Crossing"}, {"GIT_COMMITTER_EMAIL": "me@zebra-crossing.example"}):
            with self.subTest(who=sorted(who)):
                self.commit({"a.txt": "a\n"}, "An ordinary change", **who)
                self.found(self.scan(), f"commits: 1 of 2 match\n  - {self.head()}\n")
                self.git("reset", "-q", "--hard", "HEAD~1")

    def test_a_mailmap_cannot_give_whoever_made_a_commit_another_name(self):
        self.commit({"a.txt": "a\n"}, "An ordinary change", GIT_AUTHOR_NAME="Zebra Crossing", GIT_AUTHOR_EMAIL="zc@example.org",
                    GIT_COMMITTER_NAME="Zebra Crossing", GIT_COMMITTER_EMAIL="zc@example.org")
        named = self.head()
        (self.repo / ".mailmap").write_text("A Writer <writer@example.org> <zc@example.org>\n", encoding="utf-8")
        self.assertEqual(self.git("log", "-1", "--format=%aN %cN").strip(), "A Writer A Writer")
        self.found(self.scan(), "tracked files: 0 of 3 match", f"commits: 1 of 2 match\n  - {named}\n")

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
                   f"  - object {folder}: a folder that lists a name that matches")

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

    def test_a_commit_hidden_behind_a_replacement_is_still_found(self):
        """`git replace` shows this machine another commit in a commit's place. GitHub shows the real one."""
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
            (Path(folder) / "notes.txt").write_text("the zebra crossing\n", encoding="utf-8")
            run_git(folder, "add", "-A")
            run_git(folder, "commit", "-q", "-m", "Fix the zebra crossing")
            commit, held = run_git(folder, "rev-parse", "HEAD").strip(), run_git(folder, "rev-parse", "HEAD:notes.txt").strip()
            self.assertEqual(len(commit), 64)
            self.found(self.scan(cwd=folder), "tracked files: 2 of 2 match", f"commits: 1 of 1 match\n  - {commit[:10]}\n",
                       f"{HISTORY}: 2 of 4 match", f"  - object {held[:10]}: what a file held",
                       f"  - object {run_git(folder, 'rev-parse', 'HEAD:docs').strip()[:10]}: a folder that lists a name that matches")

    def test_a_word_in_the_pull_request_fails_and_says_which_part(self):
        for part, value in (("TITLE", "Zebra crossing"), ("BODY", "First line.\n\nAbout the zebra crossing."),
                            ("BRANCH", "zebra-crossing")):
            with self.subTest(part=part):
                ran = self.scan(**{"PRIVATE_WORDS_TITLE": "A title", "PRIVATE_WORDS_BODY": "A body",
                                   "PRIVATE_WORDS_BRANCH": "a-branch", f"PRIVATE_WORDS_{part}": value})
                self.found(ran, "pull request: 1 of 3 match", f"  - the {part.lower()}")
                for other in {"title", "body", "branch"} - {part.lower()}:
                    self.assertNotIn(f"- the {other}", ran.stdout)

    def test_a_file_name_cannot_pass_itself_off_as_a_command_to_the_runner(self):
        self.commit({"::error::look.txt": "the zebra crossing\n", "two\n::warning::lines.txt": "the zebra crossing\n"}, "Odd names")
        ran = self.scan()
        self.found(ran, "tracked files: 2 of 4 match")
        self.assertEqual([line for line in ran.stdout.splitlines() if line.lstrip().startswith("::")], [])
        self.assertIn('  - "::error::look.txt"', ran.stdout)
        self.assertIn('  - "two\\n::warning::lines.txt"', ran.stdout)

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
        self.refused(self.scan(pattern="zebra[crossing"), "cannot vouch", "not a valid pattern")
        self.refused(self.scan(pattern="x*"), "cannot vouch", "matches everything")

    def test_a_folder_that_is_not_a_repository_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            self.refused(self.scan(cwd=folder), "cannot vouch", "git")

    def test_a_repository_with_no_commit_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            self.git("init", "-q", "-b", "main", cwd=folder)
            self.refused(self.scan(cwd=folder), "git")

    def test_a_tracked_file_missing_from_the_folder_fails(self):
        (self.repo / "README.md").unlink()
        self.refused(self.scan(), "not whole")

    def test_a_shallow_clone_fails_because_its_history_is_missing(self):
        self.commit({"a.txt": "a\n"}, "Second")
        with tempfile.TemporaryDirectory() as folder:
            self.git("clone", "-q", "--depth", "1", self.repo.as_uri(), "shallow", cwd=folder)
            self.refused(self.scan(cwd=Path(folder) / "shallow"), "shallow")

    def test_git_that_cannot_be_run_or_never_answers_fails(self):
        for trouble in (FileNotFoundError("no git here"), PermissionError("not allowed"),
                        subprocess.TimeoutExpired(["git"], 300)):
            with self.subTest(trouble=type(trouble).__name__), mock.patch.object(self.script.subprocess, "run", side_effect=trouble):
                self.refused(self.scan(), "cannot vouch", "git could not be run")


class WhatGitSays(Repository):
    """The scan against answers git should never give, and against ones too rare to make with a real repository."""

    A, B = b"a" * 40, b"b" * 40          # two object names
    RAW = bytes(range(1, 21))            # a hash as a folder list holds it: 20 raw bytes

    def with_git_saying(self, **said):
        """The script's git, except that the commands named here (rev_list, cat_file, log) give back these bytes."""
        real = self.script.git

        def git(repo, *args, **more):
            command = args[0].replace("-", "_")
            return said[command] if command in said else real(repo, *args, **more)
        return mock.patch.object(self.script, "git", side_effect=git)

    def test_a_history_that_does_not_come_back_commit_by_commit_fails(self):
        name = self.A
        for log in (b"stray\0" + name + b"\0text", b"\0not-a-commit\0text", b"\0" + name + b"z\0text", b"\0" + name[:39] + b"\0text",
                    b"\0" + name, b"\0" + name + b"\0text\0" + name, b"\0" + name.upper() + b"\0text"):
            with self.subTest(log=log[:14]), self.with_git_saying(log=log):
                self.refused(self.scan(), "cannot vouch", "commit by commit")

    def test_a_commit_is_known_by_a_name_of_either_length(self):
        for name in (b"a" * 40, b"0123456789abcdef" * 4):
            with self.subTest(length=len(name)), self.with_git_saying(log=b"\0" + name + b"\0A Writer\nquiet text\n"):
                ran = self.scan()
                self.assertEqual(ran.returncode, 0, ran.said)
                self.assertIn("commits: 0 of 1 match", ran.stdout)
            with self.subTest(length=len(name), found=True), self.with_git_saying(log=b"\0" + name + b"\0the zebra crossing\n"):
                self.found(self.scan(), "commits: 1 of 1 match", "  - " + name[:10].decode())

    def test_objects_that_do_not_come_back_whole_fail(self):
        a, b = self.A, self.B
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
                ("fewer objects than were asked for", [a, b], a + b" blob 3\nabc\n"),
                ("a folder list with no end to a name", [a], self.answer(a, b"tree", b"100644 name")),
                ("a folder list with no mode before its first name", [a],
                 self.answer(a, b"tree", b"name\0" + self.RAW + b"100644 other\0" + self.RAW)),
                ("a folder list cut short", [a], self.answer(a, b"tree", b"100644 name\0" + self.RAW[:18]))):
            with self.subTest(what=what), self.with_git_saying(rev_list=b"\n".join(asked) + b"\n", cat_file=answer):
                self.refused(self.scan(), "cannot vouch", "did not come back whole")

    def folder(self, *names, raw=RAW):
        """A folder list as git stores it: for each name its mode, a space, the name, a NUL and the raw hash."""
        return b"".join(b"100644 " + name + b"\0" + raw for name in names)

    def answer(self, name, kind, held):
        return name + b" " + kind + b" " + str(len(held)).encode() + b"\n" + held + b"\n"

    def test_a_folder_matches_on_any_name_it_lists_and_on_nothing_else(self):
        hash_that_spells_it = b"zebra crossing 4200!"
        self.assertEqual(len(hash_that_spells_it), 20)
        for what, names, raw, matches in (("the last name of three", (b"plain.txt", b"with spaces in it.txt", b"zebra crossing.txt"), self.RAW, 1),
                                          ("the first name", (b"4,200 of them", b"plain.txt"), self.RAW, 1),
                                          ("no name, though a hash spells it", (b"plain.txt", b"other.txt"), hash_that_spells_it, 0),
                                          ("no name, though a name and the hash after it spell it", (b"zebra", b"plain.txt"),
                                           b"crossing, and others", 0),
                                          ("an empty folder", (), self.RAW, 0)):
            listed = self.answer(self.A, b"tree", self.folder(*names, raw=raw))
            with self.subTest(what=what), self.with_git_saying(rev_list=self.A + b"\n", cat_file=listed):
                ran = self.scan()
                self.assertEqual(ran.returncode, 1 if matches else 0, ran.said)
                self.assertIn(f"{HISTORY}: {matches} of 1 match", ran.stdout)

    def test_the_mode_before_a_name_is_no_part_of_the_name(self):
        listed = self.answer(self.A, b"tree", self.folder(b"plain.txt"))
        for pattern in ("100644", "644 plain", "plain"):
            with self.subTest(pattern=pattern), self.with_git_saying(rev_list=self.A + b"\n", cat_file=listed):
                ran = self.scan(pattern=pattern)
                self.assertIn(f"{HISTORY}: {1 if pattern == 'plain' else 0} of 1 match", ran.stdout)

    def test_a_folder_with_the_longer_names_is_read_by_their_length(self):
        long_name, raw = b"0123456789abcdef" * 4, bytes(range(1, 33))
        listed = self.answer(long_name, b"tree", self.folder(b"plain.txt", b"zebra crossing.txt", raw=raw))
        with self.with_git_saying(rev_list=long_name + b"\n", cat_file=listed):
            self.found(self.scan(), f"{HISTORY}: 1 of 1 match", "  - object 0123456789: a folder that lists a name that matches")

    def test_a_commit_among_the_objects_is_left_to_the_reading_of_commits(self):
        """Its hashes and dates are git's own, and the people and the message have been read already."""
        both = self.answer(self.A, b"commit", b"tree 4200\n\nthe zebra crossing\n") + self.answer(self.B, b"blob", b"quiet\n")
        with self.with_git_saying(rev_list=self.A + b"\n" + self.B + b"\n", cat_file=both):
            ran = self.scan()
            self.assertEqual(ran.returncode, 0, ran.said)
            self.assertIn(f"{HISTORY}: 0 of 1 match", ran.stdout)

    def test_each_object_is_asked_for_by_name_and_nothing_is_asked_twice(self):
        asked = []
        real = self.script.git

        def git(repo, *args, **more):
            asked.append((args, more))
            return real(repo, *args, **more)
        with mock.patch.object(self.script, "git", side_effect=git):
            self.assertEqual(self.scan().returncode, 0)
        commands = [args[0] for args, _ in asked]
        self.assertEqual(sorted(commands), ["cat-file", "log", "ls-files", "rev-list", "rev-parse"])
        listed = dict(asked[commands.index("cat-file")][1])["stdin"].split()
        self.assertEqual(len(listed), 5)                                    # one commit, two folders, two files
        self.assertEqual(sorted(listed), sorted(self.git("rev-list", "--objects", "--no-object-names", "HEAD").encode().split()))


class Command(Repository):
    """The script run as GitHub runs it: a process of its own, told everything through its environment."""

    def run_script(self, **env):
        ran = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.repo, capture_output=True, text=True, timeout=120,
                             env={"PATH": os.environ["PATH"], **QUIET_GIT, **env})
        return self.never_tells(Scanned(ran.returncode, ran.stdout, ran.stderr), env.get("PRIVATE_WORDS"))

    def test_the_command_passes_on_a_clean_repository(self):
        ran = self.run_script(PRIVATE_WORDS=PATTERN)
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertTrue(ran.stdout.endswith("private words: none found\n"))
        self.assertEqual(ran.stderr, "")

    def test_the_command_fails_when_a_word_is_there_or_the_pull_request_names_it(self):
        self.found(self.run_script(PRIVATE_WORDS=PATTERN, PRIVATE_WORDS_TITLE="The zebra crossing"), "  - the title")
        self.commit({"notes.txt": "the zebra crossing\n"}, "Notes")
        self.found(self.run_script(PRIVATE_WORDS=PATTERN), '  - "notes.txt"')

    def test_the_command_ends_with_two_when_it_cannot_vouch(self):
        self.refused(self.run_script(), "no pattern")
        self.refused(self.run_script(PRIVATE_WORDS="zebra[crossing"), "not a valid pattern")

    def test_the_command_skips_out_loud_for_a_fork(self):
        ran = self.run_script(PRIVATE_WORDS_FROM_FORK="true")
        self.assertEqual(ran.returncode, 0, ran.said)
        self.assertIn("skipped", ran.stdout)


if __name__ == "__main__":
    unittest.main()
