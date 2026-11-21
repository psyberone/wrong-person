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
        if not self.value or not self.value.isalpha():
            raise ValueError(f"value must be letters, got {self.value!r}")
        if self.match != "is" and len(set(self.value.upper())) != len(self.value):
            raise ValueError(f"letter set repeats a letter: {self.value!r}")

    def to_list(self):
        return [self.scope, self.match, self.value, self.positive]

    @classmethod
    def from_list(cls, item):
        return cls(*item)


class Board:
    """Names in reading order, plus who is in each scope of each suspect."""

    def __init__(self, names, shape):
        chapters, pages, lines, per_line = shape
        if len(names) != chapters * pages * lines * per_line:
            raise ValueError(f"shape {shape} needs {chapters * pages * lines * per_line} "
                             f"names, got {len(names)}")
        self.names = list(names)
        self.shape = tuple(shape)
        self.upper = [n.upper() for n in names]
        if len(set(self.upper)) != len(names):
            raise ValueError("names on a board must be unique")
        if not all(n.isalpha() for n in names):
            raise ValueError("names must be letters only")

        # index -> (chapter, page within chapter, line within page, column)
        self.where = [(c, p, ln, col)
                      for c in range(chapters) for p in range(pages)
                      for ln in range(lines) for col in range(per_line)]
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
        self._scopes = {scope: [tuple(x) for x in lists] for scope, lists in scopes.items()}

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
    raise ValueError(match)


def holds(rule, board, i):
    """Is the rule true of suspect i?"""
    found = any(matches(rule.match, rule.value, board.upper[j])
                for j in board.cells(rule.scope, i))
    return found == rule.positive


def survivors(rules, board):
    """Every suspect who satisfies all the rules, in board order."""
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
    """Every rule that can be asked of this board: the whole clue vocabulary.

    letter_sets  e.g. ["A", ..., "Z", "HELP", "CLUE"]
    named        names that may be referred to directly (those with a riddle)
    """
    for scope in SCOPES:
        for match in ("contains", "begins", "ends"):
            for value in letter_sets:
                for positive in (True, False):
                    yield Rule(scope, match, value, positive)
        for name in named:
            for positive in (True, False):
                yield Rule(scope, "is", name, positive)


# ---- cases as data ---------------------------------------------------------

def case_to_json(board, rules):
    return json.dumps({"shape": list(board.shape), "names": board.names,
                       "rules": [r.to_list() for r in rules]}, indent=1)


def case_from_json(text):
    data = json.loads(text)
    return Board(data["names"], data["shape"]), [Rule.from_list(r) for r in data["rules"]]
