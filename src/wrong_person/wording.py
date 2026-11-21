"""
wording.py - turns rules into sentences. The only place wording and riddles live.

The engine only ever sees Rule(..., "is", "Michael"). This file decides to print
that as "the singer of Thriller". Change any sentence here and no logic moves.
"""
import json
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
    """A named person reaches the page as a riddle or not at all."""
    if not riddle or not riddle.strip():
        raise ValueError("a named person is only ever printed as a riddle, and none was given")
    return riddle


def sentence(rule, riddle=None):
    """One printed clue.

    An "is" rule is about a named person, so it needs that person's `riddle`: the
    plain name is never printed. The one exception is the last clue of a case,
    Rule("name", "is", X, False), which is always NOTE and names nobody. Its
    positive twin would name the killer outright, so it is refused.
    """
    yes = rule.positive
    if rule.match == "is":
        if rule.scope == "name":
            if yes:
                raise ValueError("a clue never names the killer outright")
            return NOTE
        who = _riddle(riddle)
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
    """The premise's arrest: the one place the arrested person's riddle is printed."""
    return f"Police have arrested {_riddle(riddle)}."


def load_riddles(path=None):
    """Read a riddle table -> {name: [riddle, ...]}, refusing a broken one.

    With no `path` it reads the riddles.json shipped beside this file. Keys that
    start with "_" are notes for people and are left out.
    """
    path = Path(path) if path else Path(__file__).with_name("riddles.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    table = {name: lines for name, lines in data.items() if not name.startswith("_")}
    problems = check_riddles(table)
    if problems:
        raise ValueError(f"{path.name}: " + "; ".join(problems))
    return table


def check_riddles(table):
    """Everything a machine can check. Whether a riddle is easy is on the author."""
    problems, seen = [], {}
    for name, lines in table.items():
        if not (name.isalpha() and name[0].isupper() and len(name) <= 9):
            problems.append(f"{name!r} must be one capitalised word of at most 9 letters")
        if not isinstance(lines, list) or not lines:
            problems.append(f"{name} needs a list with at least one riddle")
            continue
        for line in lines:
            key = " ".join(line.lower().split())
            if key in seen:
                problems.append(f"{line!r} is under both {seen[key]} and {name}")
            seen[key] = name
            if line != line.strip() or line.endswith("."):
                problems.append(f"{name}: {line!r} should have no outer spaces or full stop")
            if name.lower() in line.lower().replace("'", " ").split():
                problems.append(f"{name}: {line!r} gives the name away")
    return problems
