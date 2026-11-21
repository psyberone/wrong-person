"""The README's example is a claim about the code, so it is run as a test."""
import contextlib
import io
import re
import unittest
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def example(text):
    """The README's one python block, and the output shown under the command that runs it."""
    code = re.findall(r"```python\n(.*?)```", text, re.S)
    shown = re.findall(r"```console\n\$ [^\n]*example\.py\n(.*?)```", text, re.S)
    if len(code) != 1 or len(shown) != 1:
        raise ValueError("the README needs exactly one python example and one block showing its output")
    return code[0], shown[0]


def printed(code):
    """Run the example and return everything it prints."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(code, "README example", "exec"), {"__name__": "__main__"})
    return out.getvalue()


class ReadmeExample(unittest.TestCase):
    def test_the_example_prints_what_the_readme_says(self):
        code, expected = example(README.read_text(encoding="utf-8"))
        self.assertEqual(printed(code), expected)

    def test_a_readme_without_the_example_is_noticed(self):
        with self.assertRaises(ValueError):
            example("# Wrong Person\n\nNo example here.\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
