"""A test that fails. It exists only to prove that the tests check can fail."""
import unittest


class Fails(unittest.TestCase):
    def test_two_and_two(self):
        self.assertEqual(2 + 2, 5)


if __name__ == "__main__":
    unittest.main()
