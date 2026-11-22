"""The README's example is a claim about the code, so it is run as a test."""
import contextlib
import io
import re
import unittest
from pathlib import Path

from wrong_person import engine, wording

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

    def test_an_example_without_its_output_is_noticed(self):
        with self.assertRaises(ValueError):
            example("```python\nprint(1)\n```\n")

    def test_a_second_output_block_is_noticed(self):
        with self.assertRaises(ValueError):
            example("```python\nprint(1)\n```\n\n```console\n$ python3 example.py\n1\n```\n"
                    "\n```console\n$ python3 example.py\n2\n```\n")

    def test_a_second_example_is_noticed(self):
        one = "```python\nprint(1)\n```\n"
        with self.assertRaises(ValueError):
            example(one + one + "```console\n$ python3 example.py\n1\n```\n")

    def test_the_sentences_the_readme_quotes_are_the_ones_the_code_prints(self):
        text = " ".join(README.read_text(encoding="utf-8").split())      # undo the line wrapping
        clue = wording.sentence(engine.Rule("near", "is", "Michael", False), "the singer of Thriller")
        self.assertIn(f'"{clue}"', text)
        self.assertIn(f'"{wording.NOTE}"', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
