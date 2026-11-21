# Wrong Person

*You've Got the Wrong Person!* A mystery puzzle generator.

Each puzzle is a board of first names and a short list of clues. Every clue is
true of the killer. Cross off the names the clues rule out and one name is
left. The police, as usual, arrested somebody else.

## Status

Early. What is here, and tested:

- the rule engine, which decides who each clue rules out and checks that a
  case has exactly one answer and no wasted clue;
- the wording, which turns a rule into the sentence printed on the page;
- a starter table of riddles, small pieces of trivia that stand in for a name
  ("the singer of Thriller").

Not built yet: the generator that composes cases, and the printable pages
(sized for a 7 x 9.25 inch planner page).

The package needs Python 3.10 or newer and nothing outside the standard
library.

## How a puzzle works

The board is laid out like a very small book: chapters hold pages, pages hold
lines, lines hold names. A clue looks at one of six places relative to the
killer:

| Place | What it covers |
| --- | --- |
| `name` | the killer's own name |
| `line`, `page`, `chapter` | every name there, the killer's included |
| `next_to` | the names immediately left and right on the same line |
| `near` | the names touching in any direction on the same page, diagonals included |

`next_to` and `near` are about other names, never the killer's own.

A clue then says what is, or is not, to be found there: a name containing,
beginning with or ending in a letter (a list of letters means any one of
them), or one particular name.

A clue about one particular person never prints the name. It prints that
person's riddle, and the riddle opens the sentence: "The singer of Thriller is
not near the killer."

The last clue of every case is the same sentence: "The police arrested the
wrong person." The person they arrested is named once, by riddle, before the
clues begin.

A case is sound when exactly one suspect fits every clue and no clue can be
dropped without letting someone else through.

## Try it

Save this as `example.py` in the repository root:

```python
from wrong_person import engine, wording

names = "Michael Maxwell Amber Carrie Edith Oscar Linda Simon Dennis Holly Jack Ruth".split()
board = engine.Board(names, (1, 2, 2, 3))  # 1 chapter, 2 pages, 2 lines a page, 3 names a line

# The police arrested Michael. The page only ever names him by a riddle.
print(wording.arrest("the singer of Thriller"))

clues = [
    engine.Rule("page", "begins", "L", False),
    engine.Rule("next_to", "contains", "A", True),
    engine.Rule("name", "begins", "A", False),
    engine.Rule("near", "begins", "HELP", True),
]
for clue in clues:
    print(wording.sentence(clue))
print([board.names[i] for i in engine.survivors(clues, board)])

# Two names are left. The last clue removes the one the police arrested.
last = engine.Rule("name", "is", "Michael", False)
print(wording.sentence(last))
report = engine.audit(clues + [last], board)
print(report.sound, board.names[report.killer])
```

Then run it:

```console
$ PYTHONPATH=src python3 example.py
Police have arrested the singer of Thriller.
There is no name beginning with L on the killer's page.
The killer is next to a name containing A.
The killer's name does not begin with A.
The killer is near a name beginning with H, E, L or P.
['Michael', 'Maxwell']
The police arrested the wrong person.
True Maxwell
```

## Tests

From the repository root:

```console
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Branch-aware coverage, which must stay at or above 85%:

```console
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m coverage run -m unittest discover -s tests
python3 -m coverage report
```

The tests need nothing but Python. The coverage commands need the `coverage`
package, which is not part of the standard library:
`python3 -m pip install "coverage[toml]"`. The `toml` extra matters only on
Python 3.10.

## Licence

MIT. See [LICENSE](LICENSE).
