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
# What a riddle may not hold. Unicode's control, format, surrogate and private-use
# characters, and its line and paragraph separators: none of them belongs in a riddle,
# and most cannot be seen.
_UNPRINTED = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})
# And the rest of what Unicode says to draw as nothing (its "default ignorable" code points,
# DerivedCoreProperties.txt 16.0.0), leaving out the runs that are format characters
# throughout: a grapheme joiner, Hangul fillers, variation selectors, tags, and code points
# kept for more of them. A format character inside these ranges is refused on both counts.
_IGNORABLE = ((0x034F, 0x034F), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x180B, 0x180F), (0x2065, 0x2065),
              (0x3164, 0x3164), (0xFE00, 0xFE0F), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0xE0000, 0xE0FFF))

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


def _unprinted(text):
    """The first character in the text that cannot go on a page, or None."""
    return next((char for char in text if unicodedata.category(char) in _UNPRINTED
                 or any(low <= ord(char) <= high for low, high in _IGNORABLE)), None)


def _riddle(riddle):
    """The riddle, if it is one: some text that can go on a page. Nothing, blank text,
    text holding a character that cannot go on a page, and anything else are refused."""
    if riddle is not None and not isinstance(riddle, str):
        raise ValueError(f"a riddle is one piece of text, got {riddle!r}")
    if not riddle or not riddle.strip():
        raise ValueError("a named person is only ever printed as a riddle, and none was given")
    hidden = _unprinted(riddle)
    if hidden is not None:
        raise ValueError(f"the riddle {riddle!r} holds U+{ord(hidden):04X}, a character that cannot go on a page")
    return riddle


def _gives_away(name, riddle):
    """Is the name one of the riddle's words, both in plain letters? Case, punctuation
    and accents do not hide it: "Tom's", "(Tom)" and "TOM," all hold Tom, and "Zoe
    Kravitz" holds Zo\u00eb. "Kentucky" does not hold Ken."""
    return _plain(name).lower() in re.findall(r"[^\W\d_]+", _plain(riddle).lower())


def _plain(text):
    """The text with its accents taken off: Zo\u00eb comes back as Zoe. A mark comes off
    when Unicode 3.2 gives it a combining class, as it does the acute accent, a cedilla
    or a comma under a letter, a stroke through it, and the horn of Vietnamese. Three
    Tibetan vowel signs have no class and come off too, since Unicode splits each into
    two marks that have one. Any other mark with no class stays on, so a name holding
    one is refused: the grapheme joiner, an enclosing circle, many vowel signs, and any
    mark newer than Unicode 3.2. A letter in another form, such as full width or
    circled, stays as it is; only a sign Unicode holds to be that very letter, such as
    the Kelvin sign for K, is read as the letter. Unicode 3.2's tables are used, which
    every Python holds alike, so the answer is the same on each."""
    return "".join(char for char in unicodedata.ucd_3_2_0.normalize("NFD", text)
                   if not unicodedata.ucd_3_2_0.combining(char))


def sentence(rule, riddle=None):
    """One printed clue.

    An "is" rule is about a named person, so it needs that person's `riddle`. A
    missing or blank riddle, one that is not text, one that holds a character
    that cannot go on a page, and one that holds the person's name are all
    refused with a ValueError, so the name is not printed.

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

    A missing or blank riddle, one that is not text, and one that holds a
    character that cannot go on a page are refused with a ValueError.
    arrest() is not told the person's name, so it cannot tell a
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
            odd = next((char for char in plain if not (char.isascii() and char.isalpha())), None)
            problems.append(f"{name!r} must be one word of at most 9 letters, A to Z with or "
                            "without accents, starting with a capital and not all capitals"
                            + ("" if odd is None else f": {odd!r} (U+{ord(odd):04X}) is not a letter A to Z"))
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
            hidden = _unprinted(line)
            if hidden is not None:
                problems.append(f"{name}: {line!r} holds U+{ord(hidden):04X}, "
                                "a character that cannot go on a page")
            if _gives_away(name, line):
                problems.append(f"{name}: {line!r} gives the name away")
    return problems
