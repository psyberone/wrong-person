"""The planted faults are a check that can block a merge, so the script that plants them is tested.

Every test here hands the script a small repository of its own, made in a temp folder: one module,
one test file and a list of faults. No test here plants anything in this repository.
"""
import contextlib
import importlib.util
import io
import os
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "planted_faults.py"
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

    def test_shapes_is_the_only_module(self):
        import pathlib
        source = pathlib.Path(__file__).resolve().parents[1] / "src"
        self.assertEqual(sorted(path.name for path in source.iterdir()), ["shapes.py"])
'''
TRIANGLE = "test_shapes.Sides.test_a_triangle_has_three_sides"
SQUARE = "test_shapes.Sides.test_a_square_has_four_sides"
CIRCLE = "test_shapes.Sides.test_a_circle_cannot_be_counted_here"
ONE_MODULE = "test_shapes.Sides.test_shapes_is_the_only_module"
SHAPES = "src/shapes.py"
A_FOURTH_SIDE = (SHAPES, '"triangle": 3', '"triangle": 4')
A_FIFTH_SIDE = (SHAPES, '"square": 4', '"square": 5')
KILLED = ("T1 a triangle is given a fourth side", TRIANGLE, [A_FOURTH_SIDE])
SURVIVOR = ("T2 a triangle is given a fourth side and the square's test is asked", SQUARE, [A_FOURTH_SIDE])
SKIPPED = ("T3 a triangle is given a fourth side and a test that skips is asked", CIRCLE, [A_FOURTH_SIDE])
A_SECOND_MODULE = ("T30 a second module appears", ONE_MODULE, [("src/circles.py", None, "SIDES = {}\n")])


def load():
    """The script as a module; it lives outside the package, so it is loaded by path."""
    spec = importlib.util.spec_from_file_location("planted_faults", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def a_list(*faults):
    """The text of a list of faults, as a file under tools/faults/ holds it."""
    return f"FAULTS = {list(faults)!r}\n"


def depth(mark):
    """How many runs of the script a process with this depth mark is inside: 0, 1, or 2 for any mark that the script refuses."""
    return {None: 0, "0": 0, "1": 1}.get(mark, 2)


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
        """Run git on a folder, and on that folder only: with none of the caller's settings, nor a GIT_DIR left by a hook that happens to be running the tests."""
        subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True, env={"PATH": os.environ.get("PATH", ""), **QUIET_GIT})

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

    def seen_from_the_copy(self, *lines):
        """Add to the small repository's suite a test of these lines. The suite passes in the copy only if they do."""
        self.write("tests/test_the_copy.py", "import os\nimport pathlib\nimport subprocess\nimport sys\nimport unittest\n\n\n"
                   "class TheCopy(unittest.TestCase):\n    def test_it(self):\n" + "".join(f"        {line}\n" for line in lines))

    def assert_no_command_in(self, printed):
        """GitHub's runner reads `##[` anywhere in a line as a command to it, and `::` at the start of one, spaces apart."""
        for line in printed.splitlines():
            self.assertFalse(line.lstrip().startswith("::"), line)
            self.assertNotIn("##[", line)


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
        self.assertLess(out.index("no fault planted: 4 tests ran and passed in the copy"), out.index("killed"))

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

    def test_a_fault_caught_by_one_case_of_a_test_is_killed(self):
        """A test that tries several cases reports each failing case under a name of its own, longer than the test's."""
        self.write("tests/test_shapes.py", TESTS + "\n    def test_each_shape_has_its_sides(self):\n"
                   "        for name, count in (('triangle', 3), ('square', 4)):\n"
                   "            with self.subTest(name=name):\n"
                   "                self.assertEqual(shapes.sides(name), count)\n")
        status, out, err = self.planted(("T36 a fault that one case catches", "test_shapes.Sides.test_each_shape_has_its_sides", [A_FOURTH_SIDE]))
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T36", out)

    def test_a_fault_is_taken_out_before_the_next_is_planted(self):
        """Were the fourth side left in, the triangle's test would fail again and the next fault would be counted as killed."""
        status, out, _ = self.planted(KILLED, ("T8 the square's name is asked of the triangle's test", TRIANGLE, [A_FIFTH_SIDE]))
        self.assertEqual(status, 1)
        self.assertIn("SURVIVED      T8", out)


    def test_an_error_raised_by_what_the_test_calls_is_a_kill(self):
        raising = ("T61 the sides cannot be counted", TRIANGLE, [(SHAPES, "    return SIDES[name]", "    raise ValueError(name)")])
        status, out, err = self.planted(raising)
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T61", out)

    def test_a_test_under_a_decorator_can_still_kill(self):
        self.write("tests/test_wrapped.py", "import unittest\nfrom unittest import mock\n\nimport shapes\n\n\nclass Wrapped(unittest.TestCase):\n"
                   "    @mock.patch.dict('os.environ', {'SHAPE': 'triangle'})\n    def test_a_triangle_has_three_sides(self):\n"
                   "        self.assertEqual(shapes.sides('triangle'), 3)\n")
        status, out, err = self.planted(("T45 a fourth side, and a wrapped test", "test_wrapped.Wrapped.test_a_triangle_has_three_sides", [A_FOURTH_SIDE]))
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T45", out)

    def test_a_fault_that_cannot_be_judged_and_a_survivor_together_end_with_2(self):
        """Both fail the run; 2 says that the count cannot be trusted either."""
        broken = ("T19 the module no longer reads as Python", TRIANGLE, [(SHAPES, "def sides(name):", "def sides(name:")])
        status, out, err = self.planted(SURVIVOR, broken)
        self.assertEqual(status, 2, out + err)
        self.assertIn("2 faults: 0 killed, 1 survived, 0 skipped here, 1 that cannot be judged", out)

    def test_each_test_named_is_run_alone_with_no_fault_planted_and_that_is_said(self):
        status, out, err = self.planted(KILLED, SURVIVOR, ("T62 a fifth side", SQUARE, [A_FIFTH_SIDE]))
        self.assertEqual(status, 1, out + err)
        self.assertIn("no fault planted: each test named was run alone as well (2 of them), and none failed", out)


class AddingAFile(SmallRepository):
    """An edit with None for the text to replace adds a file that is not there."""

    def test_a_fault_may_add_a_file(self):
        status, out, err = self.planted(A_SECOND_MODULE)
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T30 a second module appears", out)

    def test_the_file_is_taken_away_again_before_the_next_fault(self):
        """Were the new file left in, the same test would fail again and the next fault would be counted as killed."""
        status, out, _ = self.planted(A_SECOND_MODULE, ("T31 a square is given a fifth side", ONE_MODULE, [A_FIFTH_SIDE]))
        self.assertEqual(status, 1)
        self.assertIn("killed        T30", out)
        self.assertIn("SURVIVED      T31", out)

    def test_a_file_that_is_there_already_cannot_be_added(self):
        self.cannot_vouch(("T32 the module is added again", TRIANGLE, [(SHAPES, None, "SIDES = {}\n")]),
                          said=["T32", "src/shapes.py cannot be added: it is there already"])
        self.assertEqual((self.repo / SHAPES).read_text(encoding="utf-8"), MODULE)

    @unittest.skipUnless(hasattr(os, "symlink"), "no symbolic links here")
    def test_a_file_is_not_added_through_a_link_that_points_nowhere(self):
        """Written to, such a link would make the file wherever it points, and that may be outside the copy."""
        folder = Path(tempfile.mkdtemp(dir=self.made.name))
        os.symlink(folder / "elsewhere.py", folder / "circles.py")
        with self.assertRaises(self.script.CannotVouch):
            self.script.plant(folder, self.script.Fault("T66 a file added through a link", TRIANGLE, [("circles.py", None, "SIDES = {}\n")]))
        self.assertFalse((folder / "elsewhere.py").exists())

    def test_a_file_is_added_only_to_a_folder_that_is_there(self):
        self.cannot_vouch(("T33 a module in a folder of its own", TRIANGLE, [("src/more/circles.py", None, "SIDES = {}\n")]),
                          said=["T33", "src/more/circles.py cannot be added: its folder is not there"])

    def test_a_file_added_and_then_edited_is_still_taken_away(self):
        both = [("src/circles.py", None, "SIDES = {}\n"), ("src/circles.py", "{}", '{"circle": 1}')]
        status, out, err = self.planted(("T34 a second module, written in two steps", ONE_MODULE, both), A_SECOND_MODULE)
        self.assertEqual(status, 0, out + err)
        self.assertIn("2 faults: 2 killed", out)

    def test_a_file_is_not_added_outside_the_repository(self):
        self.cannot_vouch(("T35 a file elsewhere", TRIANGLE, [("../added.txt", None, "written\n")]), said=["T35", "is not a path inside this repository"])
        self.assertFalse((self.repo.parent / "added.txt").exists())


class Skips(SmallRepository):
    def test_a_test_that_fails_in_one_case_is_a_kill_though_another_case_of_it_is_skipped(self):
        self.write("tests/test_cases.py", "import unittest\n\nimport shapes\n\n\nclass Cases(unittest.TestCase):\n"
                   "    def test_the_sides_of_each_shape(self):\n        for shape, sides in (('circle', None), ('triangle', 3)):\n"
                   "            with self.subTest(shape=shape):\n                if sides is None:\n"
                   "                    self.skipTest('no circles on this computer')\n"
                   "                self.assertEqual(shapes.sides(shape), sides)\n")
        status, out, err = self.planted(("T68 a fourth side, and a test of two cases, one of them skipped", "test_cases.Cases.test_the_sides_of_each_shape", [A_FOURTH_SIDE]))
        self.assertEqual(status, 0, out + err)
        self.assertIn("killed        T68", out)
        self.assertIn("1 fault: 1 killed, 0 survived, 0 skipped here, 0 that cannot be judged", out)

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


    def test_where_no_test_may_skip_every_skipped_test_is_counted(self):
        again = ("T63 a fifth side, and a test that skips is asked", CIRCLE, [A_FIFTH_SIDE])
        status, out, err = self.planted(SKIPPED, again, args=["--no-skips"])
        self.assertEqual(status, 2, out + err)
        self.assertIn("2 faults' tests were skipped, and here no test may be skipped", err)


class Refusals(SmallRepository):
    def test_a_suite_that_fails_with_no_fault_planted_proves_nothing(self):
        self.write("tests/test_shapes.py", TESTS.replace('("square"), 4)', '("square"), 40)'))
        self.cannot_vouch(KILLED, said=["with no fault planted the tests must run and pass",
                                        "these did not pass there: test_shapes.Sides.test_a_square_has_four_sides."])

    def test_a_suite_with_many_failing_tests_names_three_of_them(self):
        self.write("tests/test_many.py", "import unittest\n\n\nclass Many(unittest.TestCase):\n"
                   + "".join(f"    def test_{letter}(self):\n        self.fail()\n\n" for letter in "edcba"))
        self.cannot_vouch(KILLED, said=["these did not pass there: test_many.Many.test_a, test_many.Many.test_b, test_many.Many.test_c and 2 more."])

    def test_a_test_that_passes_though_it_is_marked_to_fail_fails_the_suite(self):
        self.write("tests/test_marked.py", "import unittest\n\n\nclass Marked(unittest.TestCase):\n"
                   "    @unittest.expectedFailure\n    def test_marked(self):\n        pass\n")
        self.cannot_vouch(KILLED, said=["these did not pass there: test_marked.Marked.test_marked."])

    def test_a_test_file_that_cannot_be_read_fails_the_suite(self):
        """It is an error and not a failed assertion, and it stands in the suite all the same."""
        self.write("tests/test_broken.py", "import nowhere\n")
        self.cannot_vouch(KILLED, said=["these did not pass there: unittest.loader._FailedTest.test_broken."])

    def test_a_class_that_cannot_be_set_up_fails_the_suite_and_is_named_in_quotes(self):
        self.write("tests/test_set_up.py", "import unittest\n\n\nclass SetUp(unittest.TestCase):\n    @classmethod\n"
                   "    def setUpClass(cls):\n        raise ValueError\n\n    def test_it(self):\n        pass\n")
        self.cannot_vouch(KILLED, said=['these did not pass there: "setUpClass (test_set_up.SetUp)".'])

    def test_a_suite_whose_process_ends_without_an_answer_proves_nothing(self):
        self.write("tests/test_ends.py", "import os\nimport unittest\n\n\nclass Ends(unittest.TestCase):\n"
                   "    def test_that_ends_the_process(self):\n        os._exit(0)\n")
        self.cannot_vouch(KILLED, said=["with no fault planted the tests must run and pass", "the run ended without an answer"])

    def test_a_suite_of_no_tests_proves_nothing(self):
        """The test file here has a name the suite does not look for, so the suite runs nothing; some Pythons call that a pass."""
        (self.repo / "tests" / "test_shapes.py").rename(self.repo / "tests" / "checks_of_shapes.py")
        named = ("T29 a test the suite never runs", "checks_of_shapes.Sides.test_a_triangle_has_three_sides", [A_FOURTH_SIDE])
        self.cannot_vouch(named, said=["with no fault planted the tests must run and pass", "no test was found there"])

    def test_text_that_is_not_there_cannot_be_planted(self):
        gone = ("T9 a pentagon loses a side", TRIANGLE, [(SHAPES, '"pentagon": 5', '"pentagon": 4')])
        self.cannot_vouch(KILLED, gone, said=["T9 a pentagon loses a side", "found 0 times in src/shapes.py"])

    def test_text_that_is_there_twice_is_not_planted_in_the_first_place_it_is_found(self):
        twice = ("T10 a quote is doubled", TRIANGLE, [(SHAPES, '": ', '":  ')])
        self.cannot_vouch(twice, said=["T10 a quote is doubled", "found 2 times in src/shapes.py"])

    def test_every_fault_that_cannot_be_planted_is_named_at_once(self):
        first = ("T11 a pentagon loses a side", TRIANGLE, [(SHAPES, '"pentagon": 5', '"pentagon": 4')])
        second = ("T12 a hexagon loses a side", SQUARE, [(SHAPES, '"hexagon": 6', '"hexagon": 5')])
        self.cannot_vouch(first, KILLED, second, said=["2 of the faults cannot be tried as they stand", "T11 a pentagon loses a side",
                                                       "T12 a hexagon loses a side"])

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
        self.cannot_vouch(lists=lists, said=["two faults are labelled T1: one in tools/faults/one.py and one in tools/faults/two.py"])

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
                      ("T17 an edit of two parts", TRIANGLE, [(SHAPES, "a")]), ("T17 a number", TRIANGLE, [(SHAPES, 3, 4)]), "T17 only a label",
                      ("T17 a new file that holds a number", TRIANGLE, [("src/circles.py", None, 4)]),
                      ("T17 nothing replaced by nothing", TRIANGLE, [(SHAPES, None, None)])]:
            with self.subTest(entry=entry):
                self.cannot_vouch(lists={"shapes.py": f"FAULTS = {[entry]!r}\n"}, said=["tools/faults/shapes.py"])

    def test_a_label_or_a_file_name_cannot_start_a_line_of_its_own_in_what_is_printed(self):
        """What is printed goes into GitHub's log, and there a line that begins with two colons is a command to the runner."""
        for entry in [("T38 a label\n::error::of two lines", TRIANGLE, [A_FOURTH_SIDE]),
                      ("T38 a file name of two lines", TRIANGLE, [("src/shapes.py\n::error::of two lines", '"triangle": 3', "x")])]:
            with self.subTest(entry=entry[0]):
                out, err = self.cannot_vouch(lists={"shapes.py": f"FAULTS = {[entry]!r}\n"}, said=["tools/faults/shapes.py"])
                self.assertNotIn("::error::", out + err)

    def test_a_list_with_no_faults_in_it_is_refused(self):
        self.cannot_vouch(lists={"shapes.py": "FAULTS = []\n"}, said=["there is no fault to plant"])
        self.cannot_vouch(lists={"shapes.py": "MUTANTS = []\n"}, said=["tools/faults/shapes.py", "FAULTS"])

    def test_a_list_that_cannot_be_read_is_refused_and_named(self):
        self.cannot_vouch(lists={"shapes.py": "FAULTS = [\n"}, said=["tools/faults/shapes.py could not be read"])

    def test_a_repository_with_no_lists_is_refused(self):
        self.cannot_vouch(lists={}, said=["there is no fault to plant: no list under tools/faults/ holds one"])

    def test_a_folder_that_git_does_not_know_is_refused(self):
        """Also when it sits inside some other repository: that one's files are not this folder's."""
        shutil.rmtree(self.repo / ".git")
        self.cannot_vouch(KILLED, said=["git could not list the files of this repository"])
        self.git(self.repo.parent, "init", "--quiet")
        self.cannot_vouch(KILLED, said=["git could not list the files of this repository"])

    @unittest.skipUnless(os.name == "posix", "the stand-in for git is a shell script")
    def test_a_git_that_does_not_answer_or_is_not_there_is_refused(self):
        slow = Path(tempfile.mkdtemp(dir=self.made.name))
        (slow / "git").write_text("#!/bin/sh\nexec /bin/sleep 10\n", encoding="utf-8")
        (slow / "git").chmod(0o755)
        for where in (slow, Path(tempfile.mkdtemp(dir=self.made.name))):
            with self.subTest(where=where.name), mock.patch.dict(os.environ, {"PATH": str(where)}), mock.patch.object(self.script, "GIT_SECONDS", 1):
                self.cannot_vouch(KILLED, said=["git could not list the files of this repository"])

    def test_a_test_that_takes_too_long_is_not_waited_for_and_is_not_a_kill(self):
        forever = ("T18 the sides take ten seconds to count", TRIANGLE,
                   [(SHAPES, "    return SIDES[name]", "    import time\n    time.sleep(10)\n    return SIDES[name]")])
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

    def test_a_fault_that_breaks_what_a_test_needs_set_up_is_not_a_kill(self):
        """The test named never ran, so nothing is known about it."""
        self.write("tests/test_set_up.py", "import unittest\n\nimport shapes\n\n\nclass SetUp(unittest.TestCase):\n"
                   "    @classmethod\n    def setUpClass(cls):\n        cls.triangle = {3: 'three sides'}[shapes.sides('triangle')]\n\n"
                   "    def test_a_square_has_four_sides(self):\n        self.assertEqual(shapes.sides('square'), 4)\n")
        status, out, err = self.planted(("T37 the set-up breaks", "test_set_up.SetUp.test_a_square_has_four_sides", [A_FOURTH_SIDE]))
        self.assertEqual(status, 2, out + err)
        self.assertIn("CANNOT SAY    T37", out)
        self.assertIn("gave no verdict with the fault planted", out)

    def test_a_copy_that_a_test_wrote_to_is_not_trusted(self):
        self.write("tests/test_shapes.py", TESTS + "\n    def test_that_scribbles(self):\n        import pathlib\n"
                   "        pathlib.Path('README.md').write_text('scribbled on\\n')\n")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 2, out + err)
        self.assertIn("README.md in the copy no longer matches the repository", err)

    def test_a_copy_written_to_in_any_of_its_files_is_not_trusted(self):
        self.write("zz.txt", "the last file by name\n")
        self.write("tests/test_shapes.py", TESTS + "\n    def test_that_scribbles(self):\n        import pathlib\n"
                   "        pathlib.Path('zz.txt').write_text('scribbled on\\n')\n")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 2, out + err)
        self.assertIn("zz.txt in the copy no longer matches the repository", err)

    def test_a_file_that_a_test_left_in_the_copy_is_not_trusted(self):
        """A file left behind could be what fails the next fault's test, and that would be counted as a kill."""
        self.write("tests/test_shapes.py", TESTS + "\n    def test_that_leaves_notes(self):\n        import pathlib\n"
                   "        pathlib.Path('notes.txt').write_text('left behind\\n')\n")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 2, out + err)
        self.assertIn("planted faults: cannot vouch: notes.txt is in the copy and not in the repository", err)

    def test_anything_a_test_left_anywhere_in_the_copy_is_not_trusted(self):
        """A folder, a link or a file deep inside can fail the next fault's test as well as a file at the top can."""
        for leaving, name in (("pathlib.Path('tests/notes.txt').write_text('left behind\\n')", "tests/notes.txt"),
                              ("pathlib.Path('left').mkdir(exist_ok=True)", "left"),
                              ("os.path.lexists('again.md') or os.symlink('README.md', 'again.md')", "again.md")):
            with self.subTest(name=name):
                self.write("tests/test_shapes.py", TESTS + f"\n    def test_that_leaves_something(self):\n        import os, pathlib\n        {leaving}\n")
                status, out, err = self.planted(KILLED)
                self.assertEqual(status, 2, out + err)
                self.assertIn(f"planted faults: cannot vouch: {name} is in the copy and not in the repository", err)

    def test_a_disk_that_fails_is_not_read_as_a_survivor(self):
        """Python itself ends with 1 when an error is not caught, and 1 here means that a fault survived."""
        with mock.patch.object(shutil, "copy2", side_effect=OSError("no room left")):
            self.cannot_vouch(KILLED, said=["the copy could not be worked in (OSError)"])

    def test_an_error_of_the_scripts_own_is_not_read_as_a_survivor(self):
        """It names the last line of the script that the error passed through, and does not print what the error said."""
        line = 1 + SCRIPT.read_text(encoding="utf-8").splitlines().index("        names = copy_of(root, lab)")
        with mock.patch.object(self.script, "copy_of", side_effect=RuntimeError("kept-to-itself")):
            out, err = self.cannot_vouch(KILLED, said=[f"the script itself failed (RuntimeError at line {line})"])
        self.assertNotIn("kept-to-itself", out + err)

    def test_a_test_that_fails_alone_with_no_fault_planted_proves_nothing(self):
        """Under its fault each test is run alone, so a test that passes only after another has run would "kill" any fault at all."""
        leaning = TESTS.replace('        self.assertEqual(shapes.sides("triangle"), 3)\n',
                                '        self.assertEqual(shapes.sides("triangle"), 3)\n        SEEN.append("triangle")\n')
        self.write("tests/test_shapes.py", "SEEN = []\n" + leaning + "\n    def test_b_leans_on_the_triangle_test(self):\n        self.assertTrue(SEEN)\n")
        unread = ("T43 the page loses two words, which no test reads", "test_shapes.Sides.test_b_leans_on_the_triangle_test",
                  [("README.md", "Shapes and their sides.", "Shapes.")])
        self.cannot_vouch(unread, KILLED, said=["1 of the tests named did not pass when run alone with no fault planted",
                                                "\n  test_shapes.Sides.test_b_leans_on_the_triangle_test\n"])

    def test_a_test_that_gives_no_verdict_alone_with_no_fault_planted_proves_nothing_either(self):
        """What it sets up first passes only after another test has run. Alone it neither passes nor fails in its own body."""
        leaning = TESTS.replace('        self.assertEqual(shapes.sides("triangle"), 3)\n',
                                '        self.assertEqual(shapes.sides("triangle"), 3)\n        SEEN.append("triangle")\n')
        self.write("tests/test_shapes.py", "SEEN = []\n" + leaning + "\n\nclass Tilts(unittest.TestCase):\n    def setUp(self):\n        self.assertTrue(SEEN)\n\n"
                   "    def test_a_square_has_four_sides(self):\n        self.assertEqual(shapes.sides('square'), 4)\n")
        unread = ("T67 the page loses two words, which no test reads", "test_shapes.Tilts.test_a_square_has_four_sides",
                  [("README.md", "Shapes and their sides.", "Shapes.")])
        self.cannot_vouch(unread, KILLED, said=["1 of the tests named did not pass when run alone with no fault planted",
                                                "\n  test_shapes.Tilts.test_a_square_has_four_sides\n"])

    def test_a_failing_test_that_the_suite_never_runs_proves_nothing_either(self):
        self.write("tests/checks_of_shapes.py", "import unittest\n\n\nclass Checks(unittest.TestCase):\n    def test_that_fails(self):\n        self.fail()\n")
        unread = ("T64 the page loses two words", "checks_of_shapes.Checks.test_that_fails", [("README.md", "Shapes and their sides.", "Shapes.")])
        self.cannot_vouch(unread, said=["1 of the tests named did not pass when run alone with no fault planted",
                                        "\n  checks_of_shapes.Checks.test_that_fails\n"])

    def test_a_fault_that_breaks_only_what_the_test_itself_sets_up_is_not_a_kill(self):
        """Every test of the class would fail the same way, so the test named has caught nothing."""
        self.write("tests/test_set_up.py", "import unittest\n\nimport shapes\n\n\nclass SetUp(unittest.TestCase):\n"
                   "    def setUp(self):\n        self.triangle = {3: 'three sides'}[shapes.sides('triangle')]\n\n"
                   "    def test_a_square_has_four_sides(self):\n        self.assertEqual(shapes.sides('square'), 4)\n")
        status, out, err = self.planted(("T44 the test's own set-up breaks", "test_set_up.SetUp.test_a_square_has_four_sides", [A_FOURTH_SIDE]))
        self.assertEqual(status, 2, out + err)
        self.assertIn("CANNOT SAY    T44", out)
        self.assertIn("gave no verdict with the fault planted", out)

    def test_a_class_that_cannot_clear_up_after_the_test_is_not_a_pass(self):
        self.write("tests/test_clear_up.py", "import unittest\n\nimport shapes\n\n\nclass ClearUp(unittest.TestCase):\n"
                   "    @classmethod\n    def tearDownClass(cls):\n        cls.triangle = {3: 'three sides'}[shapes.sides('triangle')]\n\n"
                   "    def test_a_square_has_four_sides(self):\n        self.assertEqual(shapes.sides('square'), 4)\n")
        status, out, err = self.planted(("T46 the clearing up breaks", "test_clear_up.ClearUp.test_a_square_has_four_sides", [A_FOURTH_SIDE]))
        self.assertEqual(status, 2, out + err)
        self.assertIn("CANNOT SAY    T46", out)

    def test_a_test_whose_process_ends_without_an_answer_is_not_a_kill(self):
        dies = ("T47 the module ends the process", TRIANGLE, [(SHAPES, "def sides(name):", "import os\nos._exit(3)\n\n\ndef sides(name):")])
        status, out, err = self.planted(dies, KILLED)
        self.assertEqual(status, 2, out + err)
        self.assertIn("CANNOT SAY    T47", out)
        self.assertIn("gave no verdict with the fault planted", out)
        self.assertIn("killed        T1", out)

    def test_a_suite_that_takes_too_long_with_no_fault_planted_is_not_waited_for(self):
        self.write("tests/test_shapes.py", TESTS + "\n    def test_that_takes_ten_seconds(self):\n        import time\n        time.sleep(10)\n")
        with mock.patch.object(self.script, "SUITE_SECONDS", 2):
            self.cannot_vouch(KILLED, said=["with no fault planted the tests must run and pass", "did not end within 2 seconds"])

    def test_a_suite_that_fails_only_in_the_copy_names_the_tests_that_failed_there(self):
        """The copy has no .git, no file that git ignores and no link, so a test can pass in the repository and fail there."""
        self.write("tests/test_shapes.py", TESTS + "\n    def test_that_needs_the_history(self):\n        import pathlib\n"
                   "        self.assertTrue(pathlib.Path('.git').exists())\n")
        self.cannot_vouch(KILLED, said=["with no fault planted the tests must run and pass",
                                        "these did not pass there: test_shapes.Sides.test_that_needs_the_history."])

    def test_tests_that_cannot_be_looked_up_are_not_taken_to_be_there(self):
        """With --check no test is run, so the look-up is all that stands between a test that is gone and a green run."""
        for name, text in {"dies": "import os\nos._exit(0)\n", "sleeps": "import time\ntime.sleep(10)\n"}.items():
            with self.subTest(name=name), mock.patch.object(self.script, "SECONDS", 2):
                self.write(f"tests/test_{name}.py", text)
                self.cannot_vouch((f"T54 a test in a file that {name}", f"test_{name}.Gone.test_gone", [A_FOURTH_SIDE]), args=["--check"],
                                  said=["the tests could not be looked up by name in the copy"])
                (self.repo / "tests" / f"test_{name}.py").unlink()

    def test_text_found_at_two_places_that_overlap_is_not_planted_either(self):
        self.write(SHAPES, MODULE + "\n\ndef count(n):\n    n += 1\n    n += 1\n    return n\n")
        twice = ("T48 a step is lost", TRIANGLE, [(SHAPES, "    n += 1\n    ", "    ")])
        self.cannot_vouch(twice, said=["T48 a step is lost", "found 2 times in src/shapes.py"])

    def test_a_file_that_does_not_hold_text_cannot_be_planted_in(self):
        (self.repo / "picture.bin").write_bytes(b"\xff\xfe\x00 not text")
        self.cannot_vouch(("T53 a picture is edited", TRIANGLE, [("picture.bin", "not", "now")]),
                          said=["T53", "picture.bin is not a file of this repository that holds text"])

    def test_a_list_that_ends_the_program_is_refused_and_named(self):
        """Ended that way the run would stop with 0 and not a word, as if every fault had been killed."""
        for ending in ("import sys\nsys.exit(0)\n", "raise SystemExit\n"):
            with self.subTest(ending=ending):
                lists = {"a.py": a_list(SURVIVOR), "b.py": "FAULTS = []\n" + ending}
                self.cannot_vouch(lists=lists, said=["tools/faults/b.py could not be read (SystemExit)"])

    def test_a_list_that_raises_is_refused_and_named_and_what_it_said_is_not_printed(self):
        out, err = self.cannot_vouch(lists={"shapes.py": "raise ValueError('kept-to-itself')\n"},
                                     said=["tools/faults/shapes.py could not be read (ValueError)"])
        self.assertNotIn("kept-to-itself", out + err)

    def test_a_list_that_would_not_be_read_is_not_passed_over(self):
        """Its faults would never be planted, and nothing would say so."""
        for name in ("more/extra.py", "other.txt"):
            with self.subTest(name=name):
                self.cannot_vouch(lists={"shapes.py": a_list(KILLED), name: a_list(SURVIVOR)},
                                  said=[f"cannot vouch: tools/faults/{name} is under tools/faults/ and is not a list"])
                (self.repo / "tools" / "faults" / name).unlink()

    def test_a_refusal_says_which_entry_of_its_list_counted_from_one(self):
        self.cannot_vouch(lists={"shapes.py": f"FAULTS = {[KILLED, ('T17 two parts', TRIANGLE)]!r}\n"}, said=["tools/faults/shapes.py, entry 2:"])

    def test_an_entry_of_too_many_parts_or_of_the_wrong_kind_is_refused(self):
        for entry in [("T49 four parts", TRIANGLE, [A_FOURTH_SIDE], "more"), ("T49 an edit of four parts", TRIANGLE, [(*A_FOURTH_SIDE, "more")]),
                      ("T49 a number to replace", TRIANGLE, [(SHAPES, 3, "x")]),
                      ("T49 text that cannot be written to a file", TRIANGLE, [(SHAPES, '"triangle": 3', "\ud800")])]:
            with self.subTest(entry=entry[0]):
                self.cannot_vouch(lists={"shapes.py": f"FAULTS = {[entry]!r}\n"}, said=["tools/faults/shapes.py, entry 1:"])

    def test_no_refusal_of_an_entry_quotes_its_edits(self):
        secret = "kept-to-itself"
        for entry in [("T50 no change", TRIANGLE, [(SHAPES, secret, secret)]), ("T50 a number", TRIANGLE, [(SHAPES, secret, 4)]),
                      ("T50 four parts", TRIANGLE, [(SHAPES, secret, "x", "y")]), ("T50 nothing to put", TRIANGLE, [(SHAPES, secret, None)]),
                      ("T50 a file elsewhere", TRIANGLE, [("../x", secret, "y")]), ("T50 cannot be written", TRIANGLE, [(SHAPES, secret, "\ud800")])]:
            with self.subTest(entry=entry[0]):
                out, err = self.cannot_vouch(lists={"shapes.py": f"FAULTS = {[entry]!r}\n"}, said=["tools/faults/shapes.py, entry 1:"])
                self.assertNotIn(secret, out + err)

    def test_a_name_that_another_system_would_read_as_elsewhere_is_refused(self):
        """On Windows a backslash parts folders, and a name that begins with a drive points away from the copy."""
        for name in ("src\\shapes.py", "..\\outside.txt", "C:/outside.txt", "C:\\outside.txt", "D:outside.txt"):
            with self.subTest(name=name):
                self.cannot_vouch(("T51 a file elsewhere on Windows", TRIANGLE, [(name, "left alone", "written to")]),
                                  said=["T51", "is not a path inside this repository"])

    def test_nothing_from_a_list_is_printed_that_the_runner_would_take_for_a_command(self):
        for entry in [("T52 a label with ##[error] in it", TRIANGLE, [A_FOURTH_SIDE]),
                      ("::warning::T52 a label that opens with two colons", TRIANGLE, [A_FOURTH_SIDE]),
                      ("  ::warning::T52 a label that opens with spaces and two colons", TRIANGLE, [A_FOURTH_SIDE]),
                      ("T52 a file name with a command in it", TRIANGLE, [("src/##[error]shapes.py", '"triangle": 3', "x")]),
                      ("T52 a name that is elsewhere and of two lines", TRIANGLE, [("../shapes.py\n::error::of two lines", '"triangle": 3', "x")])]:
            with self.subTest(entry=entry[0]):
                out, err = self.cannot_vouch(lists={"shapes.py": f"FAULTS = {[entry]!r}\n"}, said=["tools/faults/shapes.py, entry 1:"])
                self.assert_no_command_in(out + err)

    @unittest.skipUnless(os.name == "posix", "a file's name can hold a line break only on some systems")
    def test_a_name_from_the_disk_is_printed_so_that_it_is_no_command(self):
        odd = "odd\n::error::##[error]name"
        with self.subTest("what was asked for"):
            out, err = self.cannot_vouch(KILLED, args=["--only", odd], said=["no fault's label begins with"])
            self.assert_no_command_in(out + err)
        with self.subTest("a list"):
            out, err = self.cannot_vouch(lists={"shapes.py": a_list(KILLED), odd + ".py": "FAULTS = [\n"}, said=["could not be read (SyntaxError)"])
            self.assert_no_command_in(out + err)
            (self.repo / "tools" / "faults" / (odd + ".py")).unlink()
        with self.subTest("a file among the lists"):
            out, err = self.cannot_vouch(lists={"shapes.py": a_list(KILLED), odd: "FAULTS = []\n"}, said=["is under tools/faults/ and is not a list"])
            self.assert_no_command_in(out + err)
            (self.repo / "tools" / "faults" / odd).unlink()
        with self.subTest("a file a test left"):
            self.write("tests/test_shapes.py", TESTS + f"\n    def test_that_leaves_notes(self):\n        import pathlib\n"
                       f"        pathlib.Path({odd!r}).write_text('left behind')\n")
            status, out, err = self.planted(KILLED)
            self.assertIn("is in the copy and not in the repository", err)
            self.assert_no_command_in(out + err)
        with self.subTest("a file of the repository"):
            self.write(odd, "as it was\n")
            status, out, err = self.planted(KILLED)
            self.assertIn("in the copy no longer matches the repository", err)
            self.assert_no_command_in(out + err)

    def test_a_name_is_printed_as_it_stands_only_when_nothing_in_it_is_odd(self):
        """The mark that opens a command, a line break, a colon: each of them alone puts a name in quotes, on one line."""
        for name, printed in (("src/shapes-2.py", "src/shapes-2.py"), ("##[error]name", '"#\\u0023[error]name"'),
                              ("two\nlines", '"two\\nlines"'), ("::error::name", '"::error::name"')):
            with self.subTest(name=name):
                out, err = self.cannot_vouch(KILLED, args=["--only", name], said=[f"no fault's label begins with {printed}\n"])
                self.assert_no_command_in(out + err)

    def test_a_test_may_take_two_minutes_and_the_suite_five(self):
        """The contributing page says two minutes, and the job on GitHub has thirty for everything."""
        self.assertEqual((self.script.SECONDS, self.script.SUITE_SECONDS, self.script.GIT_SECONDS), (120, 300, 60))

    def test_an_argument_it_does_not_know_is_refused(self):
        for args in (["--all"], ["shapes"], ["--only"], ["--only", "T1", "--only"], ["--only", "T1", "--only", "T2"]):
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
        self.assertIn("no fault planted: 5 tests ran and passed", out)

    def test_a_file_git_ignores_is_not_copied(self):
        """The ignored file here is a test that fails; were it copied, the suite would not pass with no fault planted."""
        self.write(".gitignore", "tests/test_scratch.py\n")
        self.write("tests/test_scratch.py", "import unittest\n\n\nclass Scratch(unittest.TestCase):\n    def test_fails(self):\n        self.fail('not for the copy')\n")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)
        self.assertIn("no fault planted: 4 tests ran and passed", out)

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


    @unittest.skipUnless(hasattr(os, "symlink"), "no symbolic links here")
    def test_a_symbolic_link_is_not_copied(self):
        """What it points at may lie outside the repository, and a fault planted through it would be planted there."""
        outside = Path(tempfile.mkdtemp(dir=self.made.name)) / "outside.txt"
        outside.write_text("held outside the repository\n", encoding="utf-8")
        os.symlink(outside, self.repo / "link.txt")
        os.symlink(outside.parent, self.repo / "linked")
        self.seen_from_the_copy("self.assertEqual([name for name in ('link.txt', 'linked') if os.path.lexists(name)], [])")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)
        self.cannot_vouch(("T57 a fault through a link", TRIANGLE, [("link.txt", "held", "written")]),
                          said=["T57", "link.txt is not a file of this repository that holds text"])
        self.assertEqual(outside.read_text(encoding="utf-8"), "held outside the repository\n")

    def test_the_tests_are_run_in_the_copy(self):
        """Run from anywhere else, a test that reads or writes a file by its short name would reach the wrong one."""
        self.seen_from_the_copy("self.assertTrue(os.path.samefile(os.getcwd(), pathlib.Path(__file__).resolve().parents[1]))")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)

    def test_the_copy_is_not_made_inside_the_repository(self):
        here = os.path.realpath(self.repo)
        self.seen_from_the_copy(f"self.assertNotIn({here!r}, os.path.realpath(os.getcwd()))")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)


class Children(SmallRepository):
    """What the script hands the processes it starts, and what it leaves of them."""

    def a_decoy(self):
        """Another repository, for git's own variables to name -> (its folder, everything in its .git folder)."""
        decoy = Path(tempfile.mkdtemp(dir=self.made.name)) / "decoy"
        shutil.copytree(self.pattern, decoy)
        return decoy, everything_in(decoy / ".git")

    def test_gits_own_variables_reach_neither_git_nor_the_tests(self):
        """Git hands a hook GIT_DIR and GIT_INDEX_FILE, and with them it works on the repository they name, wherever it is told to look."""
        decoy, before = self.a_decoy()
        self.seen_from_the_copy("for name in ('GIT_DIR', 'GIT_INDEX_FILE', 'GIT_WORK_TREE'):", "    self.assertNotIn(name, os.environ)")
        with mock.patch.dict(os.environ, {"GIT_DIR": str(decoy / ".git"), "GIT_INDEX_FILE": str(decoy / ".git" / "index"), "GIT_WORK_TREE": str(decoy)}):
            status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)
        self.assertIn("no fault planted: 5 tests ran and passed in the copy", out)
        self.assertEqual(everything_in(decoy / ".git"), before)

    def test_the_small_repositories_are_made_with_none_of_the_callers_git_variables(self):
        """These tests make repositories too, and must not make them in the one a hook is running for."""
        decoy, before = self.a_decoy()
        folder = Path(tempfile.mkdtemp(dir=self.made.name))
        (folder / "new.txt").write_text("new\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"GIT_DIR": str(decoy / ".git"), "GIT_INDEX_FILE": str(decoy / ".git" / "index")}):
            self.git(folder, "init", "--quiet")
            self.git(folder, "add", "--all")
        self.assertEqual(everything_in(decoy / ".git"), before)
        self.assertTrue((folder / ".git").is_dir())

    def test_every_variable_that_git_ties_to_one_repository_is_dropped(self):
        asked = subprocess.run(["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True, check=True,
                               env={"PATH": os.environ.get("PATH", ""), **QUIET_GIT})
        self.assertLessEqual(set(asked.stdout.split()), set(self.script.OF_ONE_REPOSITORY))
        kept = self.script.without_gits_own({"GIT_DIR": "x", "GIT_INDEX_FILE": "y", "HOME": "z", "GIT_CEILING_DIRECTORIES": "/a"}, "/b")
        self.assertEqual(kept, {"HOME": "z", "GIT_CEILING_DIRECTORIES": os.pathsep.join(["/b", "/a"])})

    def test_git_in_the_copy_cannot_climb_out_of_it(self):
        """The temp folder may sit inside some repository, and a test that asks git where it is must not be told of that one."""
        outer = Path(tempfile.mkdtemp(dir=self.made.name))
        self.git(outer, "init", "--quiet")
        (outer / "tmp").mkdir()
        self.seen_from_the_copy("asked = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True)",
                                "self.assertNotEqual(asked.returncode, 0, asked.stdout)")
        with mock.patch.object(tempfile, "tempdir", str(outer / "tmp")):
            status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)

    def test_the_script_is_not_started_more_than_two_deep(self):
        """Its own tests start it, and it starts tests. Without a count, a test that ran this suite again would start it without end."""
        for deep in ("2", "3", "deep"):
            with self.subTest(deep=deep), mock.patch.dict(os.environ, {self.script.DEPTH: deep}):
                self.cannot_vouch(KILLED, said=["more than two deep"])

    def test_each_run_tells_what_it_starts_and_what_it_reads_how_deep_it_is(self):
        """Tried from each depth a run may start at (no mark, "0", "1"), but from none less deep than these tests were started themselves."""
        started = depth(os.environ.get(self.script.DEPTH))
        self.assertLess(started, 2, "these tests were started two deep or deeper, or under a mark that is no depth, and from there no run is started")
        for found, told, left in ((None, "1", "0"), ("0", "1", "0"), ("1", "2", "1")):
            if depth(found) < started:
                continue
            with self.subTest(found=found), mock.patch.dict(os.environ):
                os.environ.pop(self.script.DEPTH, None)
                if found is not None:
                    os.environ[self.script.DEPTH] = found
                self.seen_from_the_copy(f"self.assertEqual(os.environ.get({self.script.DEPTH!r}), {told!r})")
                lists = {"shapes.py": f"import os\nassert os.environ.get({self.script.DEPTH!r}) == {told!r}\n" + a_list(KILLED)}
                status, out, err = self.planted(lists=lists)
                self.assertEqual(status, 0, out + err)
                self.assertEqual(os.environ.get(self.script.DEPTH), left)

    def test_no_run_is_told_that_it_is_less_deep_than_these_tests_were_started(self):
        """The depth is what ends a chain of runs that start each other, so a test may set it deeper and never back.

        The test of depths, started one deep, tries that depth alone. Started two deep it fails, and starts nothing.
        """
        for mark, runs, passes in (("1", ["1"], True), ("2", [], False)):
            if depth(mark) < depth(os.environ.get(self.script.DEPTH)):
                continue
            found, result = [], unittest.TestResult()

            def main(*args, real=self.script.main, **more):
                found.append(os.environ.get(self.script.DEPTH))
                return real(*args, **more)

            with self.subTest(mark=mark), mock.patch.dict(os.environ, {self.script.DEPTH: mark}), mock.patch.object(self.script, "main", main):
                type(self)("test_each_run_tells_what_it_starts_and_what_it_reads_how_deep_it_is").run(result)
                said = "".join(text for _, text in result.failures + result.errors)
                self.assertEqual(found, runs, said)
                self.assertEqual((result.testsRun, result.wasSuccessful()), (1, passes), said)
                if not passes:
                    self.assertIn("from there no run is started", said)

    def test_what_a_test_prints_goes_nowhere(self):
        """Held in memory, what a test printed without end would take all the memory there is long before its time was up."""
        self.seen_from_the_copy("for stream in (0, 1, 2):", "    self.assertTrue(os.path.samestat(os.fstat(stream), os.stat(os.devnull)))")
        status, out, err = self.planted(KILLED)
        self.assertEqual(status, 0, out + err)

    def test_a_test_cannot_give_the_answer_by_printing_it(self):
        self.seen_from_the_copy("print('\\nplanted-faults-answer:\"failed\"')", "sys.stdout.buffer.write(b'\\xff\\xfe\\n')", "sys.stdout.flush()")
        status, out, err = self.planted(("T55 a fourth side, and a test that prints is asked", "test_the_copy.TheCopy.test_it", [A_FOURTH_SIDE]))
        self.assertEqual(status, 1, out + err)
        self.assertIn("SURVIVED      T55", out)

    def a_clock(self):
        """A file, and lines of Python that start a process which writes to that file for ten seconds, and wait until it has begun to."""
        beat = Path(tempfile.mkdtemp(dir=self.made.name)) / "beat"
        ticking = f"import time\nfor tick in range(200):\n    open({str(beat)!r}, 'a').write('.')\n    time.sleep(0.05)\n"
        return beat, [f"subprocess.Popen([sys.executable, '-c', {ticking!r}])", "import time", "for wait in range(1000):",
                      f"    os.path.exists({str(beat)!r}) or time.sleep(0.01)"]

    def assert_stopped(self, beat):
        size = beat.stat().st_size
        time.sleep(0.5)
        self.assertEqual(beat.stat().st_size, size)

    @unittest.skipUnless(hasattr(os, "killpg"), "a group of processes is how the script ends what a test started")
    def test_what_a_test_started_is_ended_with_it(self):
        """A process left behind would go on writing in the copy while the next fault's test ran."""
        beat, started = self.a_clock()
        self.seen_from_the_copy(*started, "import shapes", "self.assertEqual(shapes.sides('triangle'), 3)")
        status, out, err = self.planted(("T56 a fourth side, and a clock left ticking", "test_the_copy.TheCopy.test_it", [A_FOURTH_SIDE]))
        self.assertEqual(status, 0, out + err)
        self.assert_stopped(beat)

    @unittest.skipUnless(hasattr(os, "killpg"), "a group of processes is how the script ends what a test started")
    def test_a_test_stopped_at_its_time_limit_takes_what_it_started_with_it(self):
        beat, started = self.a_clock()
        self.seen_from_the_copy(*started, "import shapes", "if shapes.sides('triangle') != 3:", "    time.sleep(10)")
        with mock.patch.object(self.script, "SECONDS", 2):
            status, out, err = self.planted(("T58 a fourth side, and a test that waits for three", "test_the_copy.TheCopy.test_it", [A_FOURTH_SIDE]))
        self.assertEqual(status, 2, out + err)
        self.assertIn("did not end within 2 seconds", out)
        self.assert_stopped(beat)


class Choosing(SmallRepository):
    def test_only_the_faults_whose_labels_begin_as_asked_are_planted(self):
        status, out, err = self.planted(KILLED, SURVIVOR, SKIPPED, args=["--only", "T1"])
        self.assertEqual(status, 0, out + err)
        self.assertIn("1 fault: 1 killed", out)
        self.assertNotIn("T2", out)

    def test_a_beginning_that_no_label_has_is_refused(self):
        """Otherwise a slip of the hand would plant nothing and pass."""
        self.cannot_vouch(KILLED, args=["--only", "X"], said=["no fault's label begins with X"])

    def test_text_inside_a_label_and_not_at_its_start_chooses_nothing(self):
        self.cannot_vouch(KILLED, SURVIVOR, args=["--only", "triangle"], said=["no fault's label begins with"])

    def test_the_lists_are_read_in_the_order_of_their_names(self):
        lists = {"b.py": a_list(("T60 a square is given a fifth side", SQUARE, [A_FIFTH_SIDE])), "a.py": a_list(KILLED)}
        status, out, err = self.planted(lists=lists)
        self.assertEqual(status, 0, out + err)
        self.assertLess(out.index("killed        T1"), out.index("killed        T60"))

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


class TheLists(unittest.TestCase):
    """This repository's own lists. A fault taken out of one, to get a green run, must not go unseen."""

    def test_each_list_holds_as_many_faults_as_it_did(self):
        """To add a fault, or to retire one, change its list's number here in the same pull request."""
        held = {path.name: len(runpy.run_path(str(path))["FAULTS"]) for path in sorted((ROOT / "tools" / "faults").glob("*.py"))}
        self.assertEqual(held, {"checks.py": 319, "package.py": 247, "runner.py": 149})


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

    def test_a_label_that_the_terminal_cannot_show_is_printed_in_escapes_and_the_run_goes_on(self):
        self.write("tools/faults/shapes.py", a_list(("T65 un c\u00f4t\u00e9 de plus", TRIANGLE, [A_FOURTH_SIDE])))
        shutil.copy(SCRIPT, self.repo / "tools" / "planted_faults.py")
        done = subprocess.run([sys.executable, "-B", str(self.repo / "tools" / "planted_faults.py")], capture_output=True, text=True,
                              cwd=self.made.name, env={**os.environ, **QUIET_GIT, "PYTHONIOENCODING": "ascii"})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("killed        T65 un c\\xf4t\\xe9 de plus", done.stdout)

    def test_it_reads_its_arguments_from_the_command_line(self):
        done = self.run_it(KILLED, SURVIVOR, args=["--only", "T1"])
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("1 fault: 1 killed", done.stdout)

    @unittest.skipUnless(os.name == "posix", "a stream is closed here as a Unix shell closes it")
    def test_with_an_output_closed_it_still_ends_as_it_should(self):
        """Started with `>&-` or `2>&-`, Python has no such stream at all. A crash over that would end with 1, which means that a fault survived."""
        command = [sys.executable, "-B", str(self.repo / "tools" / "planted_faults.py")]
        not_there = ("T28 not there", TRIANGLE, [(SHAPES, "nowhere", "x")])
        for closed, fault, status, said in ((">&-", KILLED, 0, ""), ("2>&-", KILLED, 0, "1 fault: 1 killed"),
                                            (">&-", not_there, 2, "planted faults: cannot vouch"), ("2>&-", not_there, 2, "planted faults: cannot vouch")):
            with self.subTest(closed=closed, status=status):
                self.write("tools/faults/shapes.py", a_list(fault))
                shutil.copy(SCRIPT, self.repo / "tools" / "planted_faults.py")
                done = subprocess.run(["/bin/sh", "-c", f'exec "$@" {closed}', "sh", *command], capture_output=True, text=True,
                                      cwd=self.made.name, env={**os.environ, **QUIET_GIT})
                self.assertEqual(done.returncode, status, done.stdout + done.stderr)
                self.assertIn(said, done.stdout + done.stderr)
                self.assertNotIn("Traceback", done.stdout + done.stderr)

    @unittest.skipUnless(hasattr(os, "killpg") and hasattr(signal, "SIGHUP"), "signals and groups of processes as Unix has them")
    def test_stopped_from_outside_it_leaves_no_copy_and_no_test_running(self):
        """Ctrl-C is not the only way a run is stopped: a closed terminal sends SIGHUP, and `kill` sends SIGTERM."""
        for number in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=number.name):
                scratch = Path(tempfile.mkdtemp(dir=self.made.name))
                beat = Path(tempfile.mkdtemp(dir=self.made.name)) / "beat"
                self.seen_from_the_copy("import shapes, time", "for tick in range(200 if shapes.sides('triangle') != 3 else 0):",
                                        f"    open({str(beat)!r}, 'a').write('.')", "    time.sleep(0.05)")
                self.write("tools/faults/shapes.py", a_list(("T59 a fourth side, and a test that waits for three", "test_the_copy.TheCopy.test_it", [A_FOURTH_SIDE])))
                shutil.copy(SCRIPT, self.repo / "tools" / "planted_faults.py")
                running = subprocess.Popen([sys.executable, "-B", str(self.repo / "tools" / "planted_faults.py")], cwd=self.made.name, start_new_session=True,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, **QUIET_GIT, "TMPDIR": str(scratch)})
                try:
                    until = time.monotonic() + 120
                    while not beat.exists() and running.poll() is None and time.monotonic() < until:
                        time.sleep(0.05)
                    self.assertTrue(beat.exists(), "the fault's test never started")
                    running.send_signal(number)
                    self.assertEqual(running.wait(timeout=60), 128 + number)
                finally:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(running.pid, signal.SIGKILL)  # whatever this test started must not outlive it, pass or fail
                    running.wait()
                self.assertEqual(sorted(path.name for path in scratch.iterdir()), [])
                size = beat.stat().st_size
                time.sleep(0.5)
                self.assertEqual(beat.stat().st_size, size)


if __name__ == "__main__":
    unittest.main()
