"""
engine.py - the rule engine. Pure logic: no randomness, no wording, no printing.

A BOARD is first names laid out like a tiny book: chapters > pages > lines.
A RULE is one triple plus a polarity:

    Rule(scope, match, value, positive)

    scope   where to look, relative to a suspect
            containers (INCLUDE the suspect):  name | line | page | chapter
            neighbours (EXCLUDE the suspect):  next_to | near
    match   what to look for
            contains | begins | ends   value = letters, any one of them counts
            is                         value = one specific name
    positive  True:  at least one name in scope matches
              False: no name in scope matches

    holds(rule, board, suspect) = positive == any(match(n) for n in scope)

"name" is the suspect's own name, the smallest container, so "the killer's name
contains E" and "there is a name containing E on the killer's page" are the same
rule at two sizes. next_to is immediately left or right on the same line. near
is touching in any direction, diagonals included, on the same page.

A CASE is a board plus rules. It is sound when exactly one suspect satisfies
every rule and no rule can be dropped without letting someone else through.
"""
from dataclasses import dataclass
import json

CONTAINERS = ("name", "line", "page", "chapter")
NEIGHBOURS = ("next_to", "near")
SCOPES = CONTAINERS + NEIGHBOURS
MATCHES = ("contains", "begins", "ends", "is")


@dataclass(frozen=True)
class Rule:
    scope: str
    match: str
    value: str
    positive: bool = True

    def __post_init__(self):
        if self.scope not in SCOPES:
            raise ValueError(f"unknown scope {self.scope!r}")
        if self.match not in MATCHES:
            raise ValueError(f"unknown match {self.match!r}")
        if not isinstance(self.value, str) or not self.value.isalpha():
            raise ValueError(f"value must be letters, got {self.value!r}")
        if self.match != "is" and len(set(self.value.upper())) != len(self.value):
            raise ValueError(f"letter set repeats a letter: {self.value!r}")
        if not isinstance(self.positive, bool):
            raise ValueError(f"positive must be True or False, got {self.positive!r}")

    def to_list(self):
        return [self.scope, self.match, self.value, self.positive]

    @classmethod
    def from_list(cls, item):
        """A rule as to_list wrote it: [scope, match, value, positive], all four."""
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            raise ValueError(f"a saved rule is [scope, match, value, positive], got {item!r}")
        return cls(*item)


def _sizes(shape):
    """A shape as four positive whole numbers, or a ValueError that shows what came instead."""
    try:
        sizes = tuple(shape)
    except TypeError:                   # a bare number, or nothing at all: it cannot be walked
        sizes = ()
    if len(sizes) != 4 or not all(type(size) is int and size > 0 for size in sizes):
        raise ValueError("shape must be four positive whole numbers "
                         f"(chapters, pages, lines, names per line), got {sizes or shape!r}")
    return sizes


class Board:
    """Names in reading order, plus who is in each scope of each suspect.

    shape is (chapters, pages in a chapter, lines on a page, names on a line).
    Its names, its shape and each scope's table are tuples all the way down, so
    none of them can be edited in place.
    """

    def __init__(self, names, shape):
        names, shape = tuple(names), _sizes(shape)
        chapters, pages, lines, per_line = shape
        if len(names) != chapters * pages * lines * per_line:
            raise ValueError(f"shape {shape} needs {chapters * pages * lines * per_line} "
                             f"names, got {len(names)}")
        if not all(isinstance(name, str) and name.isalpha() for name in names):
            raise ValueError("names must be letters only")
        self.names = names
        self.shape = shape
        self.upper = tuple(name.upper() for name in names)
        if len(set(self.upper)) != len(names):
            raise ValueError("names on a board must be unique")

        # index -> (chapter, page within chapter, line within page, column)
        self.where = tuple((c, p, ln, col)
                           for c in range(chapters) for p in range(pages)
                           for ln in range(lines) for col in range(per_line))
        n = len(names)
        scopes = {scope: [[] for _ in range(n)] for scope in SCOPES}
        for i, (c, p, ln, col) in enumerate(self.where):
            scopes["name"][i].append(i)
            for j, (c2, p2, ln2, col2) in enumerate(self.where):
                if c != c2:
                    continue
                scopes["chapter"][i].append(j)
                if p != p2:
                    continue
                scopes["page"][i].append(j)
                if i != j and abs(ln - ln2) <= 1 and abs(col - col2) <= 1:
                    scopes["near"][i].append(j)
                if ln == ln2:
                    scopes["line"][i].append(j)
                    if abs(col - col2) == 1:
                        scopes["next_to"][i].append(j)
        self._scopes = {scope: tuple(tuple(x) for x in lists) for scope, lists in scopes.items()}

    def __len__(self):
        return len(self.names)

    def index(self, name):
        return self.upper.index(name.upper())

    def cells(self, scope, i):
        """Indices of the names a rule with this scope looks at, for suspect i."""
        return self._scopes[scope][i]


def matches(match, value, name):
    """Does one NAME (uppercase) satisfy the match? Letters are any-of."""
    value = value.upper()
    if match == "is":
        return name == value
    if match == "contains":
        return any(c in name for c in value)
    if match == "begins":
        return name[0] in value
    if match == "ends":
        return name[-1] in value
    raise ValueError(f"unknown match {match!r}")


def holds(rule, board, i):
    """Is the rule true of suspect i?"""
    found = any(matches(rule.match, rule.value, board.upper[j])
                for j in board.cells(rule.scope, i))
    return found == rule.positive


def survivors(rules, board):
    """Every suspect who satisfies all the rules, in board order."""
    rules = list(rules)             # a generator would be used up on the first suspect
    return [i for i in range(len(board)) if all(holds(r, board, i) for r in rules)]


@dataclass(frozen=True)
class Audit:
    survivors: tuple          # indices of suspects who fit every rule
    redundant: tuple          # positions of rules that could be dropped
    @property
    def sound(self):
        return len(self.survivors) == 1 and not self.redundant
    @property
    def killer(self):
        return self.survivors[0] if len(self.survivors) == 1 else None


def audit(rules, board):
    """Check a case: who survives, and which rules (if any) do no work."""
    rules = list(rules)
    alive = survivors(rules, board)
    redundant = tuple(k for k in range(len(rules))
                      if survivors(rules[:k] + rules[k + 1:], board) == alive)
    return Audit(tuple(alive), redundant)


def decoys(rules, board, killer):
    """Suspects other than the killer who fit every rule except the last one.

    A case "ends on a decoy" when this is exactly one person and the last rule
    is Rule("name", "is", <that person>, positive=False).
    """
    return [i for i in survivors(list(rules)[:-1], board) if i != killer]


def rule_space(board, letter_sets, named=()):
    """The clue vocabulary, as a tuple: every place and match for each letter set,
    and an "is" rule for each name in `named`, each of them both ways.

    letter_sets  a list or a tuple, e.g. ["A", ..., "Z", "HELP", "CLUE"]
    named        a list or a tuple of the names that may be referred to directly
                 (those with a riddle); each must be on `board`, whatever the
                 case of its letters

    One rule is left out: Rule("name", "is", X, True) would name the killer
    outright, and wording.sentence refuses to print it whatever the riddle. It
    refuses no rule that is here, given a riddle it accepts for each named person.

    The rules come scope by scope, in the order of SCOPES: the letter rules
    first (match by match, each letter set in the order given, for and then
    against), then the named people in the order given.

    `board` is read only to see that each named person is on it. Everything is
    checked before the space is built, so what is wrong is refused at the call,
    with a ValueError for the first thing wrong: letter sets, and then named
    people, that are not a list or a tuple (one piece of text is neither); each
    letter set in turn, if Rule refuses it; each name in turn, if Rule refuses
    it or it is not on the board. What is given twice is not noticed: its rules
    come out twice.
    """
    for what, given in (("letter sets", letter_sets), ("named people", named)):
        if not isinstance(given, (list, tuple)):
            raise ValueError(f"{what} must be a list or a tuple, got {given!r}")
    for value in letter_sets:
        Rule("name", "contains", value)         # made only to be checked: Rule refuses what is no letter set
    for name in named:
        Rule("name", "is", name)                # likewise, for what is no name
        if name.upper() not in board.upper:
            raise ValueError(f"{name!r} is named but is not on the board")
    space = []
    for scope in SCOPES:
        for match in ("contains", "begins", "ends"):
            for value in letter_sets:
                for positive in (True, False):
                    space.append(Rule(scope, match, value, positive))
        for name in named:
            for positive in (True, False):
                if (scope, positive) != ("name", True):
                    space.append(Rule(scope, "is", name, positive))
    return tuple(space)


# ---- cases as data ---------------------------------------------------------

def case_to_json(board, rules):
    """A case as JSON text: an object with shape, names and rules, each a list.
    A rule is saved as [scope, match, value, positive]."""
    return json.dumps({"shape": list(board.shape), "names": list(board.names),
                       "rules": [r.to_list() for r in rules]}, indent=1)


def case_from_json(text):
    """Read a case that case_to_json wrote -> (Board, [Rule, ...]).

    Other keys in the object are left alone, whatever they hold. Text that is
    not a case, is nested too deeply to read, writes one of its own keys twice,
    or holds a board or a rule that would be refused anyway, is refused with a
    ValueError.
    """
    outermost = []

    def remember(pairs):
        outermost[:] = pairs        # an object ends after all it holds, so the last one seen is the case itself
        return dict(pairs)

    try:
        data = json.loads(text, object_pairs_hook=remember)
    except (ValueError, RecursionError) as error:
        raise ValueError(f"a saved case must be JSON: {error}") from error
    parts = ("shape", "names", "rules")
    if not isinstance(data, dict) or not all(part in data for part in parts):
        raise ValueError("a saved case is a JSON object with shape, names and rules")
    keys = [key for key, _ in outermost]
    repeated = [key for key in keys if keys.count(key) > 1]
    if repeated:                        # JSON would keep the last and say nothing
        raise ValueError(f"a saved case holds each key once, got {repeated[0]!r} twice")
    if not all(isinstance(data[part], list) for part in parts):
        raise ValueError("the shape, names and rules of a saved case must each be a list")
    return Board(data["names"], data["shape"]), [Rule.from_list(rule) for rule in data["rules"]]
