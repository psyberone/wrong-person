"""The planted faults are a check that can block a merge, so the script that plants them is tested.

Every test here hands the script a small repository of its own, made in a temp folder: one module,
one test file and a list of faults. No test here plants anything in this repository.
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

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "planted_faults.py"
QUIET_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}

MODULE = '''SIDES = {"triangle": 3, "square": 4}


def sides(name):
    return SIDES[name]
'''
TESTS = '''import unittest

import shapes


class Sides(unittest.TestCase):
    def test_a_triangle_has_three_sides(self):
        self.assertEqual(shapes.sides("triangle"), 3)

    def test_a_square_has_four_sides(self):
        self.assertEqual(shapes.sides("square"), 4)

    def test_a_circle_cannot_be_counted_here(self):
        self.skipTest("no circles on this computer")
'''
TRIANGLE = "test_shapes.Sides.test_a_triangle_has_three_sides"
SQUARE = "test_shapes.Sides.test_a_square_has_four_sides"
CIRCLE = "test_shapes.Sides.test_a_circle_cannot_be_counted_here"
SHAPES = "src/shapes.py"
A_FOURTH_SIDE = (SHAPES, '"triangle": 3', '"triangle": 4')
A_FIFTH_SIDE = (SHAPES, '"square": 4', '"square": 5')
KILLED = ("T1 a triangle is given a fourth side", TRIANGLE, [A_FOURTH_SIDE])
SURVIVOR = ("T2 a triangle is given a fourth side and the square's test is asked", SQUARE, [A_FOURTH_SIDE])
SKIPPED = ("T3 a triangle is given a fourth side and a test that skips is asked", CIRCLE, [A_FOURTH_SIDE])


def load():
    """The script as a module; it lives outside the package, so it is loaded by path."""
    spec = importlib.util.spec_from_file_location("planted_faults", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def a_list(*faults):
    """The text of a list of faults, as a file under tools/faults/ holds it."""
    return f"FAULTS = {list(faults)!r}\n"


def everything_in(folder):
    """Every file under a folder with its bytes and the time it was last written, git's own folder apart."""
    return {str(path.relative_to(folder)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in sorted(Path(folder).rglob("*")) if path.is_file() and ".git" not in path.relative_to(folder).parts}


class SmallRepository(unittest.TestCase):
    """A repository of one module and one test file, and the script run on it."""

    @classmethod
    def setUpClass(cls):
        cls.script = load()
        cls.made = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.made.cleanup)
        cls.pattern = Path(cls.made.name) / "pattern"
        for name, text in {SHAPES: MODULE, "tests/test_shapes.py": TESTS, "README.md": "Shapes and their sides.\n"}.items():
            (cls.pattern / name).parent.mkdir(parents=True, exist_ok=True)
            (cls.pattern / name).write_text(text, encoding="utf-8")
        cls.git(cls.pattern, "init", "--quiet")
        cls.git(cls.pattern, "add", "--all")

    @staticmethod
    def git(folder, *args):
        subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True, env={**os.environ, **QUIET_GIT})

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(dir=self.made.name)) / "repo"
        shutil.copytree(self.pattern, self.repo)

    def write(self, name, text):
        (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / name).write_text(text, encoding="utf-8")

    def run_script(self, *args):
        """Run the script on the small repository -> (the status it ends with, what it printed, what it complained of)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = self.script.main(list(args), root=self.repo)
        return status, out.getvalue(), err.getvalue()

    def planted(self, *faults, args=(), lists=None):
        """Write the lists of faults into the small repository, then run the script on it."""
        for name, text in (lists if lists is not None else {"shapes.py": a_list(*faults)}).items():
            self.write(f"tools/faults/{name}", text)
        return self.run_script(*args)

    def cannot_vouch(self, *faults, said=(), args=(), lists=None):
        status, out, err = self.planted(*faults, args=args, lists=lists)
        self.assertEqual(status, 2, out + err)
        self.assertIn("cannot vouch", err)
        for words in said:
            self.assertIn(words, err)
        self.assertNotIn("killed", out)
        return out, err


class Verdicts(SmallRepository):
    def test_a_fault_whose_test_fails_is_killed(self):
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T1 a triangle is given a fourth side", out)
        self.assertIn("1 fault: 1 killed, 0 survived, 0 skipped here, 0 that cannot be judged", out)
        self.assertEqual(err, "")

    def test_a_fault_whose_test_passes_survives_and_the_run_fails(self):
        status, out, err = self.planted(SURVIVOR)
        self.assertEqual(status, 1, out + err)
        self.assertIn("SURVIVED      T2 a triangle is given a fourth side and the square's test is asked", out)
        self.assertIn(f"the test {SQUARE} passed", out)
        self.assertIn("1 fault: 0 killed, 1 survived", out)

    def test_one_survivor_among_many_fails_the_run_and_every_fault_is_still_tried(self):
        status, out, _ = self.planted(SURVIVOR, KILLED, ("T4 a square is given a fifth side", SQUARE, [A_FIFTH_SIDE]))
        self.assertEqual(status, 1)
        self.assertIn("3 faults: 2 killed, 1 survived, 0 skipped here, 0 that cannot be judged", out)
        self.assertLess(out.index("SURVIVED      T2"), out.index("killed        T1"))
        self.assertLess(out.index("killed        T1"), out.index("killed        T4"))

    def test_the_suite_is_run_first_and_its_size_is_said(self):
        _, out, _ = self.planted(KILLED)
        self.assertLess(out.index("no fault planted: 3 tests ran and passed in the copy"), out.index("killed"))

    def test_a_fault_of_two_edits_has_both_planted(self):
        """Either edit alone leaves this test passing: only with both does the sum of the sides change."""
        self.write(SHAPES, MODULE + "\n\ndef all_sides():\n    return sum(SIDES.values())\n")
        self.write("tests/test_shapes.py", TESTS + "\n    def test_seven_or_eight_sides_in_all(self):\n"
                   "        self.assertIn(shapes.all_sides(), (7, 8))\n")
        both = "test_shapes.Sides.test_seven_or_eight_sides_in_all"
        self.assertEqual(self.planted(("T5 one more side", both, [A_FOURTH_SIDE]))[0], 1)
        self.assertEqual(self.planted(("T6 two more sides", both, [A_FOURTH_SIDE, A_FIFTH_SIDE]))[0], 0)

    def test_a_second_edit_to_the_same_file_is_made_to_what_the_first_left(self):
        again = (SHAPES, '"triangle": 4', '"triangle": 5')
        status, out, err = self.planted(("T7 a triangle is given two more sides", TRIANGLE, [A_FOURTH_SIDE, again]))
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T7", out)

    def test_a_fault_is_taken_out_before_the_next_is_planted(self):
        """Were the fourth side left in, the triangle's test would fail again and the next fault would be counted as killed."""
        status, out, _ = self.planted(KILLED, ("T8 the square's name is asked of the triangle's test", TRIANGLE, [A_FIFTH_SIDE]))
        self.assertEqual(status, 1)
        self.assertIn("SURVIVED      T8", out)


class Skips(SmallRepository):
    def test_a_fault_whose_test_is_skipped_is_neither_killed_nor_a_survivor(self):
        status, out, err = self.planted(SKIPPED, KILLED)
        self.assertEqual(status, 0, out + err)
        self.assertIn("skipped here  T3", out)
        self.assertIn(f"the test {CIRCLE} was skipped", out)
        self.assertIn("2 faults: 1 killed, 0 survived, 1 skipped here, 0 that cannot be judged", out)

    def test_where_no_test_may_skip_a_skipped_test_fails_the_run(self):
        status, out, err = self.planted(SKIPPED, KILLED, args=["--no-skips"])
        self.assertEqual(status, 2, out + err)
        self.assertIn("skipped here  T3", out)
        self.assertIn("killed        T1", out)
        self.assertIn("cannot vouch", err)
        self.assertIn("1 fault's test was skipped", err)

    def test_where_no_test_may_skip_a_run_with_none_skipped_passes(self):
        status, out, err = self.planted(KILLED, args=["--no-skips"])
        self.assertEqual(status, 0, out + err)
        self.assertIn("1 fault: 1 killed, 0 survived, 0 skipped here", out)


class Refusals(SmallRepository):
    def test_a_suite_that_fails_with_no_fault_planted_proves_nothing(self):
        self.write("tests/test_shapes.py", TESTS.replace('("square"), 4)', '("square"), 40)'))
        self.cannot_vouch(KILLED, said=["with no fault planted the tests must run and pass"])

    def test_a_suite_of_no_tests_proves_nothing(self):
        """The test file here has a name the suite does not look for, so the suite runs nothing; some Pythons call that a pass."""
        (self.repo / "tests" / "test_shapes.py").rename(self.repo / "tests" / "checks_of_shapes.py")
        named = ("T29 a test the suite never runs", "checks_of_shapes.Sides.test_a_triangle_has_three_sides", [A_FOURTH_SIDE])
        self.cannot_vouch(named, said=["with no fault planted the tests must run and pass"])

    def test_text_that_is_not_there_cannot_be_planted(self):
        gone = ("T9 a pentagon loses a side", TRIANGLE, [(SHAPES, '"pentagon": 5', '"pentagon": 4')])
        self.cannot_vouch(KILLED, gone, said=["T9 a pentagon loses a side", "found 0 times in src/shapes.py"])

    def test_text_that_is_there_twice_is_not_planted_in_the_first_place_it_is_found(self):
        twice = ("T10 a quote is doubled", TRIANGLE, [(SHAPES, '": ', '":  ')])
        self.cannot_vouch(twice, said=["T10 a quote is doubled", "found 2 times in src/shapes.py"])

    def test_every_fault_that_cannot_be_planted_is_named_at_once(self):
        first = ("T11 a pentagon loses a side", TRIANGLE, [(SHAPES, '"pentagon": 5', '"pentagon": 4')])
        second = ("T12 a hexagon loses a side", SQUARE, [(SHAPES, '"hexagon": 6', '"hexagon": 5')])
        self.cannot_vouch(first, KILLED, second, said=["T11 a pentagon loses a side", "T12 a hexagon loses a side"])

    def test_a_file_that_is_not_there_cannot_be_planted_in(self):
        self.cannot_vouch(("T13 another file", TRIANGLE, [("src/circles.py", "a", "b")]), said=["T13", "src/circles.py is not a file of this repository"])

    def test_a_test_that_does_not_exist_is_not_a_kill(self):
        """unittest itself reports an error for a name it cannot find, which must not be read as the test failing."""
        renamed = ("T14 the test was renamed", "test_shapes.Sides.test_a_triangle_has_3_sides", [A_FOURTH_SIDE])
        self.cannot_vouch(renamed, KILLED, said=["T14 the test was renamed", "no such test: test_shapes.Sides.test_a_triangle_has_3_sides"])

    def test_a_test_must_be_named_in_full(self):
        for name in ("test_shapes", "test_shapes.Sides", "test_a_triangle_has_three_sides", "", "tests/test_shapes.py"):
            with self.subTest(name=name):
                self.cannot_vouch(("T15 a short name", name, [A_FOURTH_SIDE]), said=["T15", "a test is named in full, as file.Class.test"])

    def test_two_faults_may_not_share_a_label(self):
        same = ("T1 a triangle is given a fourth side, once more", SQUARE, [A_FIFTH_SIDE])
        self.cannot_vouch(KILLED, same, said=["two faults are labelled T1"])

    def test_two_lists_may_not_share_a_label_either(self):
        lists = {"one.py": a_list(KILLED), "two.py": a_list(("T1 the same label in another list", SQUARE, [A_FIFTH_SIDE]))}
        self.cannot_vouch(lists=lists, said=["two faults are labelled T1"])

    def test_a_fault_may_only_touch_a_file_inside_the_repository(self):
        outside = Path(self.made.name) / "outside.txt"
        outside.write_text("left alone\n", encoding="utf-8")
        for name in ("../outside.txt", "src/../../outside.txt", str(outside), "src/../shapes.py"):
            with self.subTest(name=name):
                self.cannot_vouch(("T16 a file elsewhere", TRIANGLE, [(name, "left alone", "written to")]),
                                  said=["T16", "is not a path inside this repository"])
        self.assertEqual(outside.read_text(encoding="utf-8"), "left alone\n")

    def test_an_entry_that_is_not_a_fault_is_refused_and_its_list_is_named(self):
        for entry in [("T17 no edits", TRIANGLE, []), ("T17 two parts", TRIANGLE), ("", TRIANGLE, [A_FOURTH_SIDE]),
                      ("T17 nothing to replace", TRIANGLE, [(SHAPES, "", "x")]), ("T17 no change", TRIANGLE, [(SHAPES, "a", "a")]),
                      ("T17 an edit of two parts", TRIANGLE, [(SHAPES, "a")]), ("T17 a number", TRIANGLE, [(SHAPES, 3, 4)]), "T17 only a label"]:
            with self.subTest(entry=entry):
                self.cannot_vouch(lists={"shapes.py": f"FAULTS = {[entry]!r}\n"}, said=["tools/faults/shapes.py"])

    def test_a_list_with_no_faults_in_it_is_refused(self):
        self.cannot_vouch(lists={"shapes.py": "FAULTS = []\n"}, said=["no fault"])
        self.cannot_vouch(lists={"shapes.py": "MUTANTS = []\n"}, said=["tools/faults/shapes.py", "FAULTS"])

    def test_a_list_that_cannot_be_read_is_refused_and_named(self):
        self.cannot_vouch(lists={"shapes.py": "FAULTS = [\n"}, said=["tools/faults/shapes.py could not be read"])

    def test_a_repository_with_no_lists_is_refused(self):
        self.cannot_vouch(lists={}, said=["no fault"])

    def test_a_folder_that_git_does_not_know_is_refused(self):
        shutil.rmtree(self.repo / ".git")
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.repo.parent)}):
            self.cannot_vouch(KILLED, said=["git could not list the files of this repository"])

    def test_a_test_that_never_ends_is_not_waited_for_and_is_not_a_kill(self):
        forever = ("T18 the sides are counted for ever", TRIANGLE, [(SHAPES, "    return SIDES[name]", "    while True:\n        pass")])
        with mock.patch.object(self.script, "SECONDS", 2):
            status, out, err = self.planted(forever, KILLED)
        self.assertEqual(status, 2, out + err)
        self.assertIn("CANNOT SAY    T18", out)
        self.assertIn("did not end within 2 seconds", out)
        self.assertIn("killed        T1", out)
        self.assertIn("2 faults: 1 killed, 0 survived, 0 skipped here, 1 that cannot be judged", out)

    def test_a_fault_that_stops_the_tests_loading_is_not_a_kill(self):
        broken = ("T19 the module no longer reads as Python", TRIANGLE, [(SHAPES, "def sides(name):", "def sides(name:")])
        status, out, err = self.planted(broken)
        self.assertEqual(status, 2, out + err)
        self.assertIn("CANNOT SAY    T19", out)
        self.assertIn("could not be loaded with the fault planted", out)

    def test_a_copy_that_a_test_wrote_to_is_not_trusted(self):
        self.write("tests/test_shapes.py", TESTS + "\n    def test_that_scribbles(self):\n        import pathlib\n"
                   "        pathlib.Path('README.md').write_text('scribbled on\\n')\n")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 2, out + err)
        self.assertIn("README.md in the copy no longer matches the repository", err)

    def test_an_argument_it_does_not_know_is_refused(self):
        for args in (["--all"], ["shapes"], ["--only"], ["--only", "T1", "--only"]):
            with self.subTest(args=args):
                status, out, err = self.planted(KILLED, args=args)
                self.assertEqual(status, 2)
                self.assertIn("usage: python3 tools/planted_faults.py [--only LABEL] [--no-skips] [--check]", err)
                self.assertEqual(out, "")


class WhatIsCopied(SmallRepository):
    def test_the_repository_is_never_written_to(self):
        self.write("tools/faults/shapes.py", a_list(KILLED, SURVIVOR, SKIPPED))
        before = everything_in(self.repo)
        self.assertEqual(self.run_script()[0], 1)
        self.assertEqual(everything_in(self.repo), before)

    def test_nor_is_it_written_to_when_a_fault_cannot_be_planted(self):
        half = ("T20 one edit that fits and one that does not", TRIANGLE, [A_FOURTH_SIDE, (SHAPES, '"pentagon": 5', "")])
        self.write("tools/faults/shapes.py", a_list(half))
        before = everything_in(self.repo)
        status, _, err = self.run_script()
        self.assertEqual(status, 2)
        self.assertIn("T20", err)
        self.assertEqual(everything_in(self.repo), before)

    def test_an_edit_that_fits_is_taken_out_again_when_a_later_one_does_not(self):
        folder = Path(tempfile.mkdtemp(dir=self.made.name))
        (folder / "src").mkdir()
        (folder / SHAPES).write_text(MODULE, encoding="utf-8")
        fault = self.script.Fault("T21 half a fault", TRIANGLE, [A_FOURTH_SIDE, (SHAPES, '"pentagon": 5', "")])
        with self.assertRaises(self.script.CannotVouch):
            self.script.plant(folder, fault)
        self.assertEqual((folder / SHAPES).read_text(encoding="utf-8"), MODULE)

    def test_the_copy_is_thrown_away_whatever_happens(self):
        scratch = Path(tempfile.mkdtemp(dir=self.made.name))
        with mock.patch.object(tempfile, "tempdir", str(scratch)):
            self.planted(KILLED, SURVIVOR)
            self.cannot_vouch(("T22 text that is not there", TRIANGLE, [(SHAPES, "nowhere", "x")]))
        self.assertEqual(list(scratch.iterdir()), [])

    def test_a_file_git_has_not_been_told_of_yet_is_copied(self):
        self.write("tests/test_more_shapes.py", "import unittest\n\nimport shapes\n\n\nclass More(unittest.TestCase):\n"
                   "    def test_a_triangle_has_fewer_sides_than_a_square(self):\n"
                   "        self.assertLess(shapes.sides('triangle'), shapes.sides('square'))\n")
        status, out, err = self.planted(("T23 a new test file", "test_more_shapes.More.test_a_triangle_has_fewer_sides_than_a_square", [A_FOURTH_SIDE]))
        self.assertEqual(status, 0, out + err)
        self.assertIn("no fault planted: 4 tests ran and passed", out)

    def test_a_file_git_ignores_is_not_copied(self):
        """The ignored file here is a test that fails; were it copied, the suite would not pass with no fault planted."""
        self.write(".gitignore", "tests/test_scratch.py\n")
        self.write("tests/test_scratch.py", "import unittest\n\n\nclass Scratch(unittest.TestCase):\n    def test_fails(self):\n        self.fail('not for the copy')\n")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)
        self.assertIn("no fault planted: 3 tests ran and passed", out)

    def test_a_file_deleted_but_not_yet_taken_out_of_git_is_left_out(self):
        (self.repo / "README.md").unlink()
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T1", out)

    def test_the_tests_meet_the_copys_module_and_not_one_from_the_callers_settings(self):
        """A caller's PYTHONPATH may hold the same module with no fault in it; the copy's must still be the one imported."""
        elsewhere = Path(tempfile.mkdtemp(dir=self.made.name))
        (elsewhere / "shapes.py").write_text(MODULE, encoding="utf-8")
        with mock.patch.dict(os.environ, {"PYTHONPATH": str(elsewhere)}):
            status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T1", out)

    def test_the_text_of_an_edit_is_never_printed(self):
        """A label and the names of a test and a file are printed; what a fault replaces, and with what, is not."""
        said = []
        for faults in ([KILLED, SURVIVOR, SKIPPED], [("T24 not there", TRIANGLE, [(SHAPES, '"pentagon": 5', '"pentagon": 4')])],
                       [("T25 a number", TRIANGLE, [(SHAPES, '"triangle": 3', 4)])]):
            _, out, err = self.planted(*faults)
            said.append(out + err)
        for text, label in zip(said, ("SURVIVED      T2", "T24 not there", "tools/faults/shapes.py")):
            self.assertIn(label, text)
        for text in said:
            for edit in ('"triangle": 3', '"triangle": 4', '"pentagon"'):
                self.assertNotIn(edit, text)


class Choosing(SmallRepository):
    def test_only_the_faults_whose_labels_begin_as_asked_are_planted(self):
        status, out, err = self.planted(KILLED, SURVIVOR, SKIPPED, args=["--only", "T1"])
        self.assertEqual(status, 0, out + err)
        self.assertIn("1 fault: 1 killed", out)
        self.assertNotIn("T2", out)

    def test_a_beginning_that_no_label_has_is_refused(self):
        """Otherwise a slip of the hand would plant nothing and pass."""
        self.cannot_vouch(KILLED, args=["--only", "X"], said=["no fault's label begins with X"])

    def test_the_whole_label_can_be_asked_for(self):
        status, out, _ = self.planted(KILLED, SURVIVOR, args=["--only", "T2 a triangle is given a fourth side and the square's test is asked"])
        self.assertEqual(status, 1)
        self.assertIn("1 fault: 0 killed, 1 survived", out)

    def test_a_check_plants_every_fault_and_runs_no_test(self):
        """The suite here fails with no fault planted, and one fault would survive: a check sees neither."""
        self.write("tests/test_shapes.py", TESTS.replace('("square"), 4)', '("square"), 40)'))
        status, out, err = self.planted(KILLED, SURVIVOR, args=["--check"])
        self.assertEqual(status, 0, out + err)
        self.assertIn("2 faults: every one can be planted, and every test named is there", out)
        self.assertNotIn("killed", out)
        self.assertNotIn("SURVIVED", out)

    def test_a_check_still_refuses_what_cannot_be_planted_and_a_test_that_is_not_there(self):
        self.cannot_vouch(("T26 not there", TRIANGLE, [(SHAPES, "nowhere", "x")]), args=["--check"], said=["T26", "found 0 times"])
        self.cannot_vouch(("T27 no test", "test_shapes.Sides.test_gone", [A_FOURTH_SIDE]), args=["--check"], said=["no such test"])


class RunAsAProgram(SmallRepository):
    """The script copied into the small repository and run from somewhere else, as GitHub and a contributor run it."""

    def run_it(self, *faults, args=()):
        self.write("tools/faults/shapes.py", a_list(*faults))
        shutil.copy(SCRIPT, self.repo / "tools" / "planted_faults.py")
        return subprocess.run([sys.executable, "-B", str(self.repo / "tools" / "planted_faults.py"), *args], capture_output=True,
                              text=True, cwd=self.made.name, env={**os.environ, **QUIET_GIT})

    def test_it_ends_with_0_when_every_fault_is_killed(self):
        done = self.run_it(KILLED)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("1 fault: 1 killed", done.stdout)

    def test_it_ends_with_1_when_a_fault_survives(self):
        done = self.run_it(KILLED, SURVIVOR)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("SURVIVED      T2", done.stdout)

    def test_it_ends_with_2_when_it_cannot_vouch(self):
        done = self.run_it(("T28 not there", TRIANGLE, [(SHAPES, "nowhere", "x")]))
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("planted faults: cannot vouch", done.stderr)

    def test_it_reads_its_arguments_from_the_command_line(self):
        done = self.run_it(KILLED, SURVIVOR, args=["--only", "T1"])
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("1 fault: 1 killed", done.stdout)


if __name__ == "__main__":
    unittest.main()
