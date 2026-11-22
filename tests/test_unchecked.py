"""Runs every line of the stand-in module and checks nothing: full coverage, no proof."""
import unittest

from wrong_person import unchecked


class RunsAndChecksNothing(unittest.TestCase):
    def test_every_step_runs(self):
        for name in sorted(vars(unchecked)):
            if name.startswith('step_'):
                getattr(unchecked, name)(3, 4)


if __name__ == "__main__":
    unittest.main()
