"""REVIEW.md tells the reviewers how this project is reviewed, and lists every way data comes in and goes out.

A list like that falls behind without anyone seeing it, so it is held here: every
file the page names must be there, every file that can take data in or send it
out must be named, and every function of the package that it names must be in
the package.

What is read is what the page writes in backticks. A path is a backticked word
with a / in it, or one that ends in .py, .json, .yml, .md or .toml; one that ends
in / names a folder, and any other a file. A function is any other backticked
word that begins with `engine.` or `wording.`, or that is a dotted name such as
`Rule.from_list`: each must be found in the package, along the dots. So a
function named without its module, or with brackets after it, is reported and
not passed over.

The tests are not always run beside the source. GitHub's package job copies them,
with the pages, into a folder with no src/ in it and runs them against the
installed package, and mutmut runs them in a copy of its own. So a name under
src/wrong_person/ is looked for in the package that these tests import, wherever
that is, and every other name in the folder above tests/.
"""
import re
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from wrong_person import engine, wording

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "REVIEW.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
PACKAGE = Path(wording.__file__).resolve().parent         # src/wrong_person here, the installed package in the package job
IN_THE_PACKAGE = "src/wrong_person/"
ENDINGS = (".py", ".json", ".yml", ".md", ".toml")
MODULES = {"engine": engine, "wording": wording}
DOTTED = re.compile(r"[A-Za-z_]\w*(\.\w+)+")
LACKING = object()


def spans(page):
    """Everything the page writes in backticks."""
    return re.findall(r"`([^`\n]+)`", page)


def is_path(span):
    return "/" in span or span.endswith(ENDINGS)


def paths(page):
    """The files and folders the page names."""
    return {span for span in spans(page) if is_path(span)}


def functions(page):
    """The names in the package that the page names."""
    return {span for span in spans(page) if not is_path(span) and (span.startswith(("engine.", "wording.")) or DOTTED.fullmatch(span))}


def found(name, root, package):
    """Whether a named path is there: a folder if the name ends in /, and a file if not. Nothing outside is looked at."""
    if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
        return False
    place = package / name[len(IN_THE_PACKAGE):] if name.startswith(IN_THE_PACKAGE) else root / name
    return place.is_dir() if name.endswith("/") else place.is_file()


def missing(page, root, package):
    """The paths the page names that are not there: under `package` for a name in src/wrong_person/, and under `root` for the rest."""
    return sorted(name for name in paths(page) if not found(name, root, package))


def to_be_named(root, package):
    """Every file that can take data in or send it out, by the name the page must give it.

    Each Python file and each JSON file of the package, found in `package`; each Python file
    in tools/ and each file in .github/workflows/, found under `root`; and the folder of
    fault lists, tools/faults/, when it is there.
    """
    named = {IN_THE_PACKAGE + path.name for ending in ("*.py", "*.json") for path in package.glob(ending)}
    named |= {"tools/" + path.name for path in (root / "tools").glob("*.py")}
    named |= {".github/workflows/" + path.name for path in (root / ".github" / "workflows").glob("*") if path.is_file()}
    if (root / "tools" / "faults").is_dir():
        named.add("tools/faults/")
    return named


def unlisted(page, root, package):
    """The files that must be named and that the page does not name."""
    return sorted(to_be_named(root, package) - paths(page))


def unknown(page):
    """The names the page gives that the package lacks, each looked up along its dots."""
    lacking = []
    for name in sorted(functions(page)):
        first, *rest = name.split(".")
        thing = MODULES.get(first, LACKING)
        for part in rest:
            thing = LACKING if thing is LACKING else getattr(thing, part, LACKING)
        if thing is LACKING:
            lacking.append(name)
    return lacking


def section(page, heading):
    """What follows a page's `## heading`, up to its next heading of that level, or nothing if there is no such heading."""
    after = page.split(f"\n## {heading}\n", 1)
    return after[1].split("\n## ", 1)[0] if len(after) == 2 else ""


class ReviewPage(unittest.TestCase):
    """The page is read in each test's own body, so that a page that is not there fails the tests that read it and no other."""

    def test_every_file_the_page_names_is_in_the_repository(self):
        page = REVIEW.read_text(encoding="utf-8")
        self.assertEqual(missing(page, ROOT, PACKAGE), [])
        self.assertLessEqual({"src/wrong_person/engine.py", "tools/planted_faults.py", ".github/workflows/checks.yml"}, paths(page))

    def test_a_file_that_is_not_there_is_caught(self):
        self.assertEqual(missing("see `tools/nothing.py`", ROOT, PACKAGE), ["tools/nothing.py"])
        self.assertEqual(missing("`tools/faults` and `tools/planted_faults.py/`: a folder ends in / and a file does not", ROOT, PACKAGE),
                         ["tools/faults", "tools/planted_faults.py/"])
        self.assertEqual(missing("`../build/REVIEW.md` and `/etc/hosts` are outside", ROOT, PACKAGE), ["../build/REVIEW.md", "/etc/hosts"])
        self.assertEqual(missing("`python3 tools/planted_faults.py` is a command, not a file", ROOT, PACKAGE), ["python3 tools/planted_faults.py"])
        with tempfile.TemporaryDirectory() as empty:
            # A file of the package is looked for in the package these tests import, and not under the folder above tests/.
            self.assertEqual(missing("`src/wrong_person/engine.py` and `src/wrong_person/`", Path(empty), PACKAGE), [])
            self.assertEqual(missing("`src/wrong_person/engine.py`", ROOT, Path(empty)), ["src/wrong_person/engine.py"])

    def test_every_file_that_takes_data_in_or_out_is_named(self):
        self.assertEqual(unlisted(REVIEW.read_text(encoding="utf-8"), ROOT, PACKAGE), [])
        self.assertLessEqual({"src/wrong_person/__init__.py", "src/wrong_person/engine.py", "src/wrong_person/wording.py",
                              "src/wrong_person/riddles.json", "tools/planted_faults.py", "tools/private_words.py",
                              "tools/mutation_floor.py", ".github/workflows/checks.yml", "tools/faults/"}, to_be_named(ROOT, PACKAGE))

    def test_a_file_left_off_the_page_is_caught(self):
        with tempfile.TemporaryDirectory() as made:
            folder = Path(made)
            for name in ("tools/new.py", "src/wrong_person/engine.py"):
                (folder / name).parent.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text("", encoding="utf-8")
            (folder / "tools" / "faults").mkdir()
            package = folder / "src" / "wrong_person"
            self.assertEqual(unlisted("`src/wrong_person/engine.py`", folder, package), ["tools/faults/", "tools/new.py"])
            for name in (".github/workflows/new.yaml", "src/wrong_person/new.json", "tools/faults/new.py", "tests/test_new.py",
                         "src/wrong_person/notes.txt", "tools/notes.txt"):
                (folder / name).parent.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text("", encoding="utf-8")
            self.assertEqual(unlisted("`src/wrong_person/engine.py` `tools/faults/` `tools/new.py`", folder, package),
                             [".github/workflows/new.yaml", "src/wrong_person/new.json"])

    def test_every_function_the_page_names_is_in_the_package(self):
        page = REVIEW.read_text(encoding="utf-8")
        self.assertEqual(unknown(page), [])
        self.assertLessEqual({"engine.Board", "engine.case_from_json", "wording.load_riddles", "wording.sentence"}, functions(page))

    def test_a_function_the_package_lacks_is_caught(self):
        self.assertEqual(unknown("`engine.case_from_text` and `wording.sentence`"), ["engine.case_from_text"])
        self.assertEqual(unknown("`engine.Rule.from_list` `engine.Rule.to_text` `Rule.from_list` `wording.sentence()` `wording.py`"),
                         ["Rule.from_list", "engine.Rule.to_text", "wording.sentence()"])

    def test_the_contributing_page_points_here(self):
        self.assertIn("[REVIEW.md](REVIEW.md)", section(CONTRIBUTING.read_text(encoding="utf-8"), "How a change is reviewed"))
        just_after = "# Page\n\n## How a change is reviewed\n\n- one line\n\n## Next\n\n[REVIEW.md](REVIEW.md)\n"
        self.assertEqual(section(just_after, "How a change is reviewed"), "\n- one line\n")
        self.assertNotIn("[REVIEW.md](REVIEW.md)", section(just_after, "How a change is reviewed"))


if __name__ == "__main__":
    unittest.main()
