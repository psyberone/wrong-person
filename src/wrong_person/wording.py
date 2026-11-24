"""
wording.py - turns rules into sentences. The only place wording and riddles live.

The engine only ever sees Rule(..., "is", "Michael"). The caller hands that
person's riddle to sentence(), which prints "The singer of Thriller is ..." and
never the name. Change any sentence here and no logic moves.
"""
import json
import re
import unicodedata
from pathlib import Path

PATTERN = {"contains": "containing", "begins": "beginning with", "ends": "ending in"}
OWN = {
    ("contains", True): "The killer's name contains {v}.",
    ("contains", False): "The killer's name does not contain {v}.",
    ("begins", True): "The killer's name begins with {v}.",
    ("begins", False): "The killer's name does not begin with {v}.",
    ("ends", True): "The killer's name ends in {v}.",
    ("ends", False): "The killer's name does not end in {v}.",
}
PLACE = {"line": "on the killer's line", "page": "on the killer's page",
         "chapter": "in the killer's chapter"}
BESIDE = {"next_to": "next to", "near": "near"}
NOTE = "The police arrested the wrong person."      # the last clue of every case
# Unicode's control, format, surrogate and private-use characters, and its line and
# paragraph separators: none of them prints as a letter, a mark or a space.
_UNPRINTED = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})

RULES_TEXT = ("Every clue is true of the killer. A list of letters means any one of them. "
              "A name contains a letter wherever it appears, its capital first letter included. "
              "Clues about a line, page or chapter count the killer's own name too. "
              "Next to: immediately left or right on the same line. Near: touching in any "
              "direction, diagonals included, on the same page. "
              "Next to and near clues are about other names, never the killer's own.")


def letters(value):
    """'HELP' -> 'H, E, L or P'"""
    value = value.upper()
    return value if len(value) == 1 else ", ".join(value[:-1]) + " or " + value[-1]


def _cap(text):
    return text[0].upper() + text[1:]


def _riddle(riddle):
    """The riddle, if it is one: some text. Nothing, blank text or anything else is refused."""
    if riddle is not None and not isinstance(riddle, str):
        raise ValueError(f"a riddle is one piece of text, got {riddle!r}")
    if not riddle or not riddle.strip():
        raise ValueError("a named person is only ever printed as a riddle, and none was given")
    return riddle


def _gives_away(name, riddle):
    """Is the name one of the riddle's words? Case and punctuation do not hide it:
    "Tom's", "(Tom)" and "TOM," all hold Tom. "Kentucky" does not hold Ken."""
    return name.lower() in re.findall(r"[^\W\d_]+", riddle.lower())


def _plain(name):
    """The name with its accents taken off: 'Zoë' -> 'Zoe'. A letter written in
    another form of itself, such as full width, comes back in its plain form."""
    return "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))


def sentence(rule, riddle=None):
    """One printed clue.

    An "is" rule is about a named person, so it needs that person's `riddle`. A
    missing or blank riddle, one that is not text, and one that holds the
    person's name are all refused with a ValueError, so the name is not printed.

    Rule("name", "is", X, False) is the last clue of a case. It prints as NOTE,
    names nobody and ignores the riddle. Every such rule prints the same
    sentence, so a case must hold only one, about the person the police
    arrested; nothing here can check that. Its positive twin would name the
    killer outright, so it is refused.
    """
    yes = rule.positive
    if rule.match == "is":
        if rule.scope == "name":
            if yes:
                raise ValueError("a clue never names the killer outright")
            return NOTE
        who = _riddle(riddle)
        if _gives_away(rule.value, who):
            raise ValueError(f"the riddle {who!r} gives the name away")
        where = PLACE[rule.scope] if rule.scope in PLACE else f"{BESIDE[rule.scope]} the killer"
        return f"{_cap(who)} is {'' if yes else 'not '}{where}."
    what = f"{PATTERN[rule.match]} {letters(rule.value)}"
    if rule.scope == "name":
        return OWN[(rule.match, yes)].format(v=letters(rule.value))
    if rule.scope in PLACE:
        return f"There is {'a' if yes else 'no'} name {what} {PLACE[rule.scope]}."
    if yes:
        return f"The killer is {BESIDE[rule.scope]} a name {what}."
    return f"The killer is not {BESIDE[rule.scope]} any name {what}."


def arrest(riddle):
    """The premise's arrest: "Police have arrested <riddle>."

    A missing or blank riddle, or one that is not text, is refused with a
    ValueError. arrest() is not told the person's name, so it cannot tell a
    riddle that holds it: take riddles from a table that check_riddles passed.
    """
    return f"Police have arrested {_riddle(riddle)}."


def load_riddles(path=None):
    """Read a riddle table -> {name: [riddle, ...]}.

    With no `path` it reads the riddles.json shipped beside this file. Keys that
    start with "_" are notes for people: they are left out, whatever they hold
    and however often they come. A file that is not UTF-8 JSON, is nested too
    deeply to read, is not an object, lists a name twice, or fails check_riddles
    is refused with a ValueError that starts with the file's name.
    """
    path = Path(__file__).with_name("riddles.json") if path is None else Path(path)
    outermost = []

    def remember(pairs):
        outermost[:] = pairs        # an object ends after all it holds, so the last one seen is the file's own
        return dict(pairs)

    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=remember)
    except (ValueError, RecursionError) as error:     # not UTF-8, not JSON, or nested too deeply
        raise ValueError(f"{path.name}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: a riddle table is a JSON object of names, each with a list of riddles")
    names = [name for name, _ in outermost if not name.startswith("_")]
    twice = [name for name in dict.fromkeys(names) if names.count(name) > 1]
    table = {name: lines for name, lines in data.items() if not name.startswith("_")}
    problems = [f"{name} is listed twice" for name in twice] + check_riddles(table)
    if problems:
        raise ValueError(f"{path.name}: " + "; ".join(problems))
    return table


def check_riddles(table):
    """What a machine can check in a riddle table -> a list of problems, empty when clean.

    Whether a riddle is easy, and whether it points to one person only, is on the author.
    """
    problems, seen, plain_names = [], {}, {}
    for name, lines in table.items():
        plain = _plain(name)
        if not (plain.isascii() and plain.isalpha() and len(plain) <= 9
                and plain[0].isupper() and not plain.isupper()):
            problems.append(f"{name!r} must be one word of at most 9 letters, A to Z with or "
                            "without accents, starting with a capital and not all capitals")
        if plain.lower() in plain_names:
            problems.append(f"{name!r} and {plain_names[plain.lower()]!r} are one name in plain letters")
        plain_names.setdefault(plain.lower(), name)
        if not isinstance(lines, list) or not lines:
            problems.append(f"{name} needs a list with at least one riddle")
            continue
        for line in lines:
            if not isinstance(line, str) or not line.strip():
                problems.append(f"{name}: {line!r} is not a riddle")
                continue
            key = " ".join(line.lower().split())
            if seen.get(key) == name:
                problems.append(f"{name}: {line!r} is listed twice")
            elif key in seen:
                problems.append(f"{line!r} is under both {seen[key]} and {name}")
            seen[key] = name
            if line != line.strip() or line.endswith("."):
                problems.append(f"{name}: {line!r} should have no outer spaces or full stop")
            hidden = next((char for char in line if unicodedata.category(char) in _UNPRINTED), None)
            if hidden is not None:
                problems.append(f"{name}: {line!r} holds U+{ord(hidden):04X}, "
                                "a character that cannot go on a page")
            if _gives_away(name, line):
                problems.append(f"{name}: {line!r} gives the name away")
    return problems
