"""The mutation floor is a check that can block a merge, so the script that applies it is tested."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "mutation_floor.py"


def load():
    """The script as a module; it lives outside the package, so it is loaded by path."""
    spec = importlib.util.spec_from_file_location("mutation_floor", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summary(killed, total, **more):
    """A summary as mutmut writes it, with every other count at nought unless given."""
    counts = {"killed": killed, "survived": 0, "total": total, "no_tests": 0, "skipped": 0, "suspicious": 0,
              "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}
    return {**counts, **more}


class Verdict(unittest.TestCase):
    def setUp(self):
        self.floor = load()

    def refused(self, stats, *said):
        passed, message = self.floor.verdict(stats)
        self.assertIs(passed, False, message)
        for words in said:
            self.assertIn(words, message)

    def test_the_floor_is_eighty_per_cent(self):
        self.assertEqual(self.floor.FLOOR, 80)

    def test_a_run_above_the_floor_passes(self):
        passed, message = self.floor.verdict(summary(409, 416))
        self.assertIs(passed, True)
        self.assertIn("409 of 416", message)
        self.assertIn("98.3%", message)
        self.assertIn("80%", message)

    def test_a_run_exactly_at_the_floor_passes(self):
        self.assertIs(self.floor.verdict(summary(80, 100))[0], True)

    def test_every_mutant_killed_passes(self):
        passed, message = self.floor.verdict(summary(416, 416))
        self.assertIs(passed, True)
        self.assertIn("100.0%", message)

    def test_a_run_just_under_the_floor_fails(self):
        self.refused(summary(799, 1000), "799 of 1000", "79.9%", "under the floor of 80%")

    def test_a_rate_is_never_rounded_up_to_the_floor(self):
        self.refused(summary(7999, 10000), "79.9%")

    def test_another_floor_can_be_asked_for(self):
        self.assertIs(self.floor.verdict(summary(409, 416), floor=99)[0], False)
        self.assertIs(self.floor.verdict(summary(50, 100), floor=50)[0], True)

    def test_what_is_not_killed_counts_against_the_rate_whatever_it_is_called(self):
        self.refused(summary(79, 100, timeout=21), "79.0%")
        self.refused(summary(79, 100, no_tests=21), "79.0%")
        self.refused(summary(79, 100, suspicious=21), "79.0%")
        self.refused(summary(79, 100, skipped=21), "79.0%")
        self.refused(summary(79, 100, segfault=21), "79.0%")
        self.refused(summary(79, 100, survived=21), "79.0%")

    def test_the_floor_is_held_exactly_however_large_the_counts(self):
        """No run could be this large. The arithmetic is exact all the same, so that no size of run can slip under the floor."""
        self.refused(summary(3999999999999999999999999999999, 5 * 10 ** 30), "79.9%", "under the floor of 80%")
        self.assertIs(self.floor.verdict(summary(4 * 10 ** 30, 5 * 10 ** 30))[0], True)
        self.refused(summary(8 * 10 ** 399 - 1, 10 ** 400), "79.9%", "under the floor of 80%")
        passed, message = self.floor.verdict(summary(8 * 10 ** 399, 10 ** 400))
        self.assertIs(passed, True, message)
        self.assertIn("(80.0%); the floor is 80%", message)
        self.assertIs(self.floor.verdict(summary(801, 1000), floor=80.1)[0], True)
        self.assertIs(self.floor.verdict(summary(800, 1000), floor=80.1)[0], False)

    def test_a_run_with_no_mutants_fails(self):
        self.refused(summary(0, 0), "no mutants were made")

    def test_an_interrupted_run_fails(self):
        self.refused(summary(409, 416, check_was_interrupted_by_user=1), "interrupted")

    def test_a_summary_that_does_not_say_whether_it_was_interrupted_is_taken_as_whole(self):
        self.assertIs(self.floor.verdict({"killed": 409, "total": 416})[0], True)

    def test_a_summary_missing_a_count_fails(self):
        self.refused({"killed": 5}, "'total'")
        self.refused({"total": 5}, "'killed'")
        self.refused({}, "'killed'")

    def test_counts_that_are_not_whole_numbers_fail(self):
        self.refused(summary("409", 416), "'killed'", "whole number")
        self.refused(summary(409, 416.0), "'total'", "whole number")
        self.refused(summary(True, 1), "'killed'", "whole number")
        self.refused(summary(None, 416), "'killed'", "whole number")
        self.refused(summary(409, 416, check_was_interrupted_by_user="no"), "'check_was_interrupted_by_user'")

    def test_counts_that_cannot_be_right_fail(self):
        self.refused(summary(5, 4), "5 mutants killed out of 4 made cannot be right")
        self.refused(summary(-1, 4), "-1 mutants killed out of 4 made cannot be right")
        self.refused(summary(-1, -1), "cannot be right")

    def test_a_summary_that_is_not_an_object_fails(self):
        for stats in ([], [409, 416], "409 of 416", 409, None):
            with self.subTest(stats=stats):
                self.refused(stats, "JSON object")


class Command(unittest.TestCase):
    def run_script(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, timeout=60)

    def written(self, folder, text, name="summary.json"):
        path = Path(folder) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_the_command_passes_on_a_good_file(self):
        with tempfile.TemporaryDirectory() as folder:
            ran = self.run_script(str(self.written(folder, json.dumps(summary(409, 416)))))
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, "409 of 416 mutants killed (98.3%); the floor is 80%\n")
        self.assertEqual(ran.stderr, "")

    def test_the_command_fails_on_a_low_file(self):
        with tempfile.TemporaryDirectory() as folder:
            ran = self.run_script(str(self.written(folder, json.dumps(summary(1, 100)))))
        self.assertEqual(ran.returncode, 1)
        self.assertIn("under the floor of 80%", ran.stderr)
        self.assertEqual(ran.stdout, "")

    def test_with_no_argument_the_command_reads_the_file_mutmut_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            self.written(folder, json.dumps(summary(409, 416)), name="mutants/mutmut-cicd-stats.json")
            ran = self.run_script(cwd=folder)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("409 of 416", ran.stdout)

    def test_the_command_reads_counts_of_any_size(self):
        with tempfile.TemporaryDirectory() as folder:
            ran = self.run_script(str(self.written(folder, json.dumps(summary(8 * 10 ** 399 - 1, 10 ** 400)))))
        self.assertEqual(ran.returncode, 1)
        self.assertNotIn("Traceback", ran.stderr)
        self.assertTrue(ran.stderr.endswith("mutants killed (79.9%), under the floor of 80%\n"), ran.stderr[-80:])
        self.assertEqual(ran.stderr.count("\n"), 1)
        self.assertEqual(ran.stdout, "")

    def test_the_command_fails_without_a_file(self):
        with tempfile.TemporaryDirectory() as folder:
            ran = self.run_script(str(Path(folder) / "nothing-here.json"))
            also = self.run_script(cwd=folder)              # no argument, and no mutants/ folder either
        for run in (ran, also):
            self.assertEqual(run.returncode, 2)
            self.assertIn("cannot read the mutation summary", run.stderr)
            self.assertNotIn("Traceback", run.stderr)
            self.assertEqual(run.stdout, "")

    def test_the_command_fails_on_text_that_is_not_json(self):
        for text in ("{", "", "killed: 409", "[" * 100_000):
            with self.subTest(text=text[:12]), tempfile.TemporaryDirectory() as folder:
                ran = self.run_script(str(self.written(folder, text)))
                self.assertEqual(ran.returncode, 2)
                self.assertIn("cannot read the mutation summary", ran.stderr)
                self.assertNotIn("Traceback", ran.stderr)

    def test_the_command_fails_on_bytes_that_are_not_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "summary.json"
            path.write_bytes(b"\xff\xfe\x00{")
            ran = self.run_script(str(path))
        self.assertEqual(ran.returncode, 2)
        self.assertIn("cannot read the mutation summary", ran.stderr)
        self.assertNotIn("Traceback", ran.stderr)

    def test_the_command_takes_one_file_at_most(self):
        with tempfile.TemporaryDirectory() as folder:
            good = str(self.written(folder, json.dumps(summary(409, 416))))
            ran = self.run_script(good, good)
        self.assertEqual(ran.returncode, 2)
        self.assertIn("usage", ran.stderr)
        self.assertNotIn("Traceback", ran.stderr)


if __name__ == "__main__":
    unittest.main()
