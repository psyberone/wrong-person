"""REVIEW.md tells the reviewers how this project is reviewed, and lists every way data comes in and goes out.

A list like that falls behind without anyone seeing it, so it is held here.

Every file the page names must be there. These must be named: each Python or
JSON file in the package, at any depth; each Python file in tools/, at any
depth, outside the folder of fault lists; each Python file at the top of the
repository; each workflow, a .yml or .yaml file directly in .github/workflows/;
and the folder of fault lists itself, tools/faults/. A file or folder whose name
starts with a dot, and a __pycache__ folder, do not count, and no other folder
is looked in. Every name of the package that the page gives must be in it.

What is read is only what the page writes in backticks. A span may run onto the
next line, as Markdown allows; the line break reads as a space. Each span must
be one of three things. A path: a span with a / in it, or one that ends in .py,
.json, .yml, .yaml, .md or .toml; one that ends in / names a folder, and any
other a file. A name in the package, written with its module: engine. or
wording. and then names joined by dots, each found along the dots. Or one of the
plain words in WORDS. Any other span is reported, so a name written without its
module, or with brackets after it, is not passed over.

The tests are not always run beside the source. GitHub's package job copies them,
with the pages, into a folder with no src/ in it and runs them against the
installed package, and mutmut runs them in a copy of its own. So a name under
src/wrong_person/ is looked for in the package that these tests import, wherever
that is, and every other name in the folder above tests/.
"""
import os
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
ENDINGS = (".py", ".json", ".yml", ".yaml", ".md", ".toml")
MODULES = {"engine": engine, "wording": wording}
FUNCTION = re.compile(r"(engine|wording)(\.[A-Za-z_]\w*)+")
SPAN = re.compile(r"`([^`\n]+(?:\n[^`\n]+)?)`")             # a span may run onto one more line
LACKING = object()

# The plain words the page may write in backticks: the marks GitHub reads as commands, an option, the jobs, a branch, folders and
# tools that are not files of this repository, Python's errors, and the names of variables in the environment.
WORDS = frozenset({"##[", "::", "--no-skips", "faults", "private-words", "tests", "main", "mutants", "setuptools", "__pycache__",
                   "ValueError", "OSError", "PRIVATE_WORDS", "PRIVATE_WORDS_FROM_FORK", "GITHUB_EVENT_PATH", "PLANTED_FAULTS_DEPTH"})


def spans(page):
    """Everything the page writes in backticks. A span that runs onto the next line is read with the line break, and the spaces
    around it, as one space."""
    return [re.sub(r"\s*\n\s*", " ", span) for span in SPAN.findall(page)]


def is_path(span):
    return "/" in span or span.endswith(ENDINGS)


def paths(page):
    """The files and folders the page names."""
    return {span for span in spans(page) if is_path(span)}


def functions(page):
    """The names in the package that the page gives, written with their module."""
    return {span for span in spans(page) if not is_path(span) and FUNCTION.fullmatch(span)}


def found(name, root, package):
    """Whether a named path is there: a folder if the name ends in /, and a file if not.

    A name in src/wrong_person/ is looked for in `package`, and any other in `root`. A name that is absolute or holds a .., or
    that leads out of that folder some other way (a doubled / after src/wrong_person/, or a link), is not there.
    """
    if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
        return False
    base, rest = (package, name[len(IN_THE_PACKAGE):]) if name.startswith(IN_THE_PACKAGE) else (root, name)
    place = base / rest
    if not place.resolve().is_relative_to(base.resolve()):
        return False
    return place.is_dir() if name.endswith("/") else place.is_file()


def missing(page, root, package):
    """The paths the page names that are not there: under `package` for a name in src/wrong_person/, and under `root` for the rest."""
    return sorted(name for name in paths(page) if not found(name, root, package))


def hidden(name):
    """A name that starts with a dot (a hidden file, an editor's lock file, a Mac's ._ file), or a __pycache__ folder."""
    return name.startswith(".") or name == "__pycache__"


def files_in(folder):
    """The files under `folder`, at any depth, by their path from it; none that is hidden, and nothing in a hidden folder."""
    here = set()
    for top, folders, names in os.walk(folder):
        folders[:] = [name for name in folders if not hidden(name)]
        where = Path(top).relative_to(folder)
        here |= {(where / name).as_posix() for name in names if not hidden(name)}
    return here


def to_be_named(root, package):
    """Every file that can take data in or send it out, by the name the page must give it.

    Each Python file and each JSON file of the package, at any depth, found in `package`. Under `root`: each Python file
    in tools/, at any depth, outside tools/faults/; each Python file at the top of the repository; each workflow, a .yml
    or .yaml file directly in .github/workflows/; and the folder of fault lists, tools/faults/, when it is there. What
    `hidden` names does not count, and no other folder is looked in.
    """
    named = {IN_THE_PACKAGE + name for name in files_in(package) if name.endswith((".py", ".json"))}
    named |= {"tools/" + name for name in files_in(root / "tools") if name.endswith(".py") and not name.startswith("faults/")}
    named |= {path.name for path in root.glob("*.py") if path.is_file() and not hidden(path.name)}
    named |= {".github/workflows/" + path.name for path in (root / ".github" / "workflows").glob("*")
              if path.is_file() and not hidden(path.name) and path.name.endswith((".yml", ".yaml"))}
    if (root / "tools" / "faults").is_dir():
        named.add("tools/faults/")
    return named


def unlisted(page, root, package):
    """The files that must be named and that the page does not name."""
    return sorted(to_be_named(root, package) - paths(page))


def in_the_package(span):
    """Whether a span is a name in the package written with its module, found along its dots."""
    if not FUNCTION.fullmatch(span):
        return False
    first, *rest = span.split(".")
    thing = MODULES[first]
    for part in rest:
        thing = getattr(thing, part, LACKING)
        if thing is LACKING:
            return False
    return True


def unknown(page):
    """The spans that are neither a path, nor a name in the package written with its module, nor one of WORDS: a name the
    package lacks, and any other word, such as a name written without its module or with brackets after it."""
    return sorted({span for span in spans(page) if not is_path(span) and span not in WORDS and not in_the_package(span)})


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
        self.assertEqual(missing("`src/wrong_person//etc/hosts` and `src/wrong_person//etc/` lead outside as well", ROOT, PACKAGE),
                         ["src/wrong_person//etc/", "src/wrong_person//etc/hosts"])
        self.assertEqual(missing("`tools/../REVIEW.md` is not a name in the repository, though it leads back in", ROOT, PACKAGE),
                         ["tools/../REVIEW.md"])
        with tempfile.TemporaryDirectory() as made:
            (Path(made) / "tools").mkdir()
            (Path(made) / "tools" / "hosts.py").symlink_to("/etc/hosts")        # a link that leads outside
            self.assertEqual(missing("`tools/hosts.py`", Path(made), PACKAGE), ["tools/hosts.py"])
        # A span may run onto the next line, as Markdown allows, and the names after it are still read as they are written.
        wrapped = ("The suite runs with `PYTHONPATH=src python3 -m unittest discover\n  -s tests`, and the helper in `tools/no_such_helper.py`"
                   " reads\n`src/wrong_person/gone.json`.")
        self.assertEqual(missing(wrapped, ROOT, PACKAGE), ["src/wrong_person/gone.json", "tools/no_such_helper.py"])
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
            # Below the top of the package and of tools/, and at the top of the repository, a file must be named as well.
            deeper = ("tools/lib/fetch.py", "src/wrong_person/formats/__init__.py", "src/wrong_person/formats/load.py",
                      "src/wrong_person/locale/fr.json", "make_pages.py", "conftest.py")
            # Not these: a name or a folder that starts with a dot, a __pycache__ folder, a workflow that does not end in .yml or
            # .yaml or is not directly in its folder, anything under tools/faults/, and a folder at the top that is not tools/.
            passed_over = ("tools/.#planted_faults.py", "src/wrong_person/._engine.py", "tools/.cache/old.py", ".hidden.py",
                           "src/wrong_person/__pycache__/engine.py", "tools/__pycache__/fetch.py", ".github/workflows/.DS_Store",
                           ".github/workflows/checks.yml.orig", ".github/workflows/old/checks.yml", "tools/faults/more/new.py",
                           "scripts/render.py")
            for name in deeper + passed_over:
                (folder / name).parent.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text("", encoding="utf-8")
            named = "`src/wrong_person/engine.py` `tools/faults/` `tools/new.py` `.github/workflows/new.yaml` `src/wrong_person/new.json`"
            self.assertEqual(unlisted(named, folder, package),
                             ["conftest.py", "make_pages.py", "src/wrong_person/formats/__init__.py", "src/wrong_person/formats/load.py",
                              "src/wrong_person/locale/fr.json", "tools/lib/fetch.py"])

    def test_every_function_the_page_names_is_in_the_package(self):
        """And every other span on the page is a path or one of WORDS."""
        page = REVIEW.read_text(encoding="utf-8")
        self.assertEqual(unknown(page), [])
        self.assertLessEqual({"engine.Board", "engine.case_from_json", "wording.load_riddles", "wording.sentence"}, functions(page))

    def test_a_function_the_package_lacks_is_caught(self):
        self.assertEqual(unknown("`engine.case_from_text` and `wording.sentence`"), ["engine.case_from_text"])
        self.assertEqual(unknown("`engine.Rule.from_list` `engine.Rule.to_text` `Rule.from_list` `wording.sentence()` `wording.py`"),
                         ["Rule.from_list", "engine.Rule.to_text", "wording.sentence()"])
        # A name without its module, with brackets after it, or with its module misspelt is reported, and so is any other word
        # that is not a path and not one of the plain words held here.
        self.assertEqual(unknown("`case_from_text` `case_from_text()` `Bord` `Rule.from_list()` `nothing.here()` `Rule.from_list.nothing` "
                                 "`engin.Board` `Engine.audit` `ValueError` `--no-skips` `__pycache__`"),
                         ["Bord", "Engine.audit", "Rule.from_list()", "Rule.from_list.nothing", "case_from_text", "case_from_text()",
                          "engin.Board", "nothing.here()"])
        # A span that runs onto the next line is read whole, so the span after it is read as written.
        self.assertEqual(unknown("Run `python3 -m unittest\n  discover`, which `engine.case_from_text` cannot."),
                         ["engine.case_from_text", "python3 -m unittest discover"])

    def test_the_contributing_page_points_here(self):
        self.assertIn("[REVIEW.md](REVIEW.md)", section(CONTRIBUTING.read_text(encoding="utf-8"), "How a change is reviewed"))
        just_after = "# Page\n\n## How a change is reviewed\n\n- one line\n\n## Next\n\n[REVIEW.md](REVIEW.md)\n"
        self.assertEqual(section(just_after, "How a change is reviewed"), "\n- one line\n")
        self.assertNotIn("[REVIEW.md](REVIEW.md)", section(just_after, "How a change is reviewed"))


if __name__ == "__main__":
    unittest.main()
