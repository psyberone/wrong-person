"""Run from the repository root:  PYTHONPATH=src python3 -m unittest discover -s tests -v"""
import collections
import dataclasses
import itertools
import json
import os
import random
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

from wrong_person import engine as e
from wrong_person import wording

# A 12-name board: 1 chapter, 2 pages, 2 lines per page, 3 names per line.
#
#   PAGE 1                        PAGE 2
#   Michael  Maxwell  Amber       Linda   Simon  Dennis
#   Carrie   Edith    Oscar       Holly   Jack   Ruth
NAMES = "Michael Maxwell Amber Carrie Edith Oscar Linda Simon Dennis Holly Jack Ruth".split()
SHAPE = (1, 2, 2, 3)

# A complete case on that board: Maxwell did it, and Michael is the decoy.
CASE = [
    e.Rule("page", "begins", "L", False),      # page 2 is out
    e.Rule("next_to", "contains", "A", True),  # leaves Michael, Maxwell, Amber, Edith
    e.Rule("name", "begins", "A", False),      # Amber is out
    e.Rule("near", "begins", "HELP", True),    # Edith is out (her own E doesn't count)
    e.Rule("name", "is", "Michael", False),    # the decoy falls
]
RIDDLE = "the singer of Thriller"              # how Michael is named on a page
SRC = str(Path(wording.__file__).parents[1])   # so a child process can import the package


def who(board, indices):
    return [board.names[i] for i in indices]


class Geometry(unittest.TestCase):
    def setUp(self):
        self.b = e.Board(NAMES, SHAPE)

    def cells(self, scope, name):
        return who(self.b, self.b.cells(scope, self.b.index(name)))

    def test_containers_include_the_suspect(self):
        self.assertEqual(self.cells("name", "Edith"), ["Edith"])
        self.assertEqual(self.cells("line", "Edith"), ["Carrie", "Edith", "Oscar"])
        self.assertEqual(self.cells("page", "Edith"), NAMES[:6])
        self.assertEqual(self.cells("chapter", "Edith"), NAMES)

    def test_neighbours_exclude_the_suspect(self):
        self.assertEqual(self.cells("next_to", "Edith"), ["Carrie", "Oscar"])
        self.assertEqual(self.cells("next_to", "Michael"), ["Maxwell"])        # end of a line
        self.assertEqual(self.cells("near", "Edith"),
                         ["Michael", "Maxwell", "Amber", "Carrie", "Oscar"])
        self.assertEqual(self.cells("near", "Michael"), ["Maxwell", "Carrie", "Edith"])

    def test_neighbours_never_cross_a_page(self):
        # Amber ends a line of page 1. Simon and Dennis sit level with her on page 2.
        self.assertEqual(self.cells("next_to", "Amber"), ["Maxwell"])
        self.assertEqual(self.cells("near", "Amber"), ["Maxwell", "Edith", "Oscar"])

    def test_chapters_are_separate(self):
        #   CHAPTER 1          CHAPTER 2
        #   Ann  Bob  Cat      Dan  Eve  Fay
        two = e.Board("Ann Bob Cat Dan Eve Fay".split(), (2, 1, 1, 3))
        cells = lambda scope, name: who(two, two.cells(scope, two.index(name)))
        self.assertEqual(cells("chapter", "Cat"), ["Ann", "Bob", "Cat"])
        self.assertEqual(cells("page", "Dan"), ["Dan", "Eve", "Fay"])
        self.assertEqual(cells("line", "Cat"), ["Ann", "Bob", "Cat"])
        self.assertEqual(cells("next_to", "Ann"), ["Bob"])
        self.assertEqual(cells("near", "Cat"), ["Bob"])

    def test_a_board_knows_how_many_names_it_holds(self):
        self.assertEqual(len(self.b), 12)

    def test_a_name_is_found_whatever_its_case(self):
        self.assertEqual(self.b.index("ruth"), 11)
        self.assertEqual(self.b.index("MICHAEL"), 0)

    def test_a_board_keeps_its_own_copy_of_the_names(self):
        names = list(NAMES)
        board = e.Board(names, SHAPE)
        names[0] = "Zed"
        self.assertEqual(board.names[0], "Michael")
        self.assertEqual(board.index("Michael"), 0)

    def test_the_names_a_rule_looks_at_cannot_be_edited(self):
        for scope in e.SCOPES:
            self.assertIsInstance(self.b.cells(scope, 0), tuple, scope)
            with self.assertRaises(TypeError, msg=scope):
                self.b._scopes[scope][0] = (5,)           # nor can a suspect's whole row be swapped

    def test_bad_boards_are_refused(self):
        with self.assertRaisesRegex(ValueError, r"^shape \(1, 2, 2, 3\) needs 12 names, got 11$"):
            e.Board(NAMES[:-1], SHAPE)
        with self.assertRaisesRegex(ValueError, "^names on a board must be unique$"):
            e.Board(NAMES[:-1] + ["michael"], SHAPE)          # duplicate, any case

    def test_a_name_that_is_not_all_letters_is_refused(self):
        with self.assertRaisesRegex(ValueError, "^names must be letters only$"):
            e.Board(NAMES[:-1] + ["R2D2"], SHAPE)

    def test_a_name_that_is_not_text_is_refused(self):
        for name in (None, 5, b"Ruth", ["Ruth"]):
            with self.assertRaisesRegex(ValueError, "^names must be letters only$", msg=repr(name)):
                e.Board(NAMES[:-1] + [name], SHAPE)

    def test_a_shape_is_four_positive_whole_numbers(self):
        with self.assertRaisesRegex(ValueError, r"^shape must be four positive whole numbers "
                                                r"\(chapters, pages, lines, names per line\), got \(-1, -2, 2, 3\)$"):
            e.Board(NAMES, (-1, -2, 2, 3))            # the sizes still multiply to twelve
        for shape, names in (((0, 2, 2, 3), []), ((1, 0, 2, 3), []), ((1, 2, 0, 3), []), ((1, 2, 2, 0), []),
                             ((1, 2, -2, -3), NAMES), ((1, 2, 2), NAMES[:4]), ((1, 2, 2, 3, 1), NAMES),
                             ((1.0, 2, 2, 3), NAMES), ((1, 2, 2, 3.0), NAMES), (("1", "2", "2", "3"), NAMES),
                             ((True, 2, 2, 3), NAMES), ((1, 2, 2, False), [])):
            with self.assertRaisesRegex(ValueError, "^shape must be four positive whole numbers", msg=shape):
                e.Board(names, shape)

    def test_a_shape_that_is_not_a_list_at_all_gets_the_same_refusal(self):
        for shape in (12, None):
            with self.assertRaises(ValueError) as refused:
                e.Board(NAMES, shape)
            self.assertEqual(str(refused.exception), "shape must be four positive whole numbers "
                                                     f"(chapters, pages, lines, names per line), got {shape!r}")

    def test_names_and_shape_may_each_be_read_only_once(self):
        board = e.Board(iter(NAMES), iter(SHAPE))
        self.assertEqual((list(board.names), board.shape), (NAMES, SHAPE))
        again, _ = e.case_from_json(e.case_to_json(board, CASE))
        self.assertEqual((again.names, again.shape), (board.names, board.shape))

    def test_a_boards_names_cannot_be_edited_in_place(self):
        for held in (self.b.names, self.b.upper, self.b.where):
            self.assertIsInstance(held, tuple)

    def test_near_reaches_one_line_up_or_down_and_no_further(self):
        #   Ann Bob Cat
        #   Dan Eve Fay
        #   Gus Hal Ivy
        tall = e.Board("Ann Bob Cat Dan Eve Fay Gus Hal Ivy".split(), (1, 1, 3, 3))
        near_bob = [tall.names[j] for j in tall.cells("near", tall.index("Bob"))]
        self.assertEqual(near_bob, ["Ann", "Cat", "Dan", "Eve", "Fay"])


class Semantics(unittest.TestCase):
    def setUp(self):
        self.b = e.Board(NAMES, SHAPE)

    def holds(self, name, *rule):
        return e.holds(e.Rule(*rule), self.b, self.b.index(name))

    def test_own_name_counts_in_a_container(self):
        # Ruth is the only R on her page: the page rule is still true of her.
        self.assertTrue(self.holds("Ruth", "page", "begins", "R", True))
        self.assertTrue(self.holds("Holly", "page", "begins", "R", True))
        self.assertFalse(self.holds("Edith", "page", "begins", "R", True))

    def test_own_name_does_not_count_for_neighbours(self):
        self.assertFalse(self.holds("Ruth", "next_to", "begins", "R", True))
        self.assertFalse(self.holds("Ruth", "near", "begins", "R", True))
        self.assertTrue(self.holds("Jack", "next_to", "begins", "R", True))

    def test_negative_is_the_exact_opposite(self):
        for rule in e.rule_space(self.b, ["A", "HELP"], ["Michael"]):
            if rule.positive:
                flipped = e.Rule(rule.scope, rule.match, rule.value, False)
                for i in range(len(self.b)):
                    self.assertNotEqual(e.holds(rule, self.b, i), e.holds(flipped, self.b, i))

    def test_letter_sets_mean_any_one(self):
        self.assertTrue(self.holds("Holly", "name", "begins", "HELP", True))
        self.assertTrue(self.holds("Linda", "name", "begins", "HELP", True))
        self.assertFalse(self.holds("Simon", "name", "begins", "HELP", True))
        self.assertTrue(self.holds("Ruth", "name", "ends", "HELP", True))

    def test_a_letter_list_means_any_one_for_contains_too(self):
        # No name has both an X and a K; Maxwell has the X and Jack has the K.
        rule = e.Rule("name", "contains", "XK")
        self.assertEqual(who(self.b, e.survivors([rule], self.b)), ["Maxwell", "Jack"])

    def test_is_means_the_whole_name(self):
        board = e.Board("Fred Freddie Bert Albert".split(), (1, 1, 2, 2))
        self.assertEqual(who(board, e.survivors([e.Rule("name", "is", "Fred")], board)), ["Fred"])
        self.assertEqual(who(board, e.survivors([e.Rule("name", "is", "Bert")], board)), ["Bert"])

    def test_case_does_not_matter(self):
        self.assertTrue(self.holds("Amber", "name", "contains", "a", True))
        self.assertTrue(self.holds("Maxwell", "next_to", "is", "MICHAEL", True))

    def test_is_rules(self):
        self.assertFalse(self.holds("Michael", "name", "is", "Michael", False))   # "not Michael"
        self.assertTrue(self.holds("Maxwell", "name", "is", "Michael", False))
        self.assertTrue(self.holds("Michael", "page", "is", "Michael", True))     # own name counts
        self.assertFalse(self.holds("Michael", "next_to", "is", "Michael", True))

    def test_bad_rules_are_refused(self):
        for bad in [("street", "contains", "A"), ("page", "rhymes", "A"),
                    ("page", "contains", ""), ("page", "contains", "AA"), ("page", "contains", "A1")]:
            with self.assertRaises(ValueError):
                e.Rule(*bad)

    def test_a_letter_may_not_repeat_in_another_case(self):
        with self.assertRaisesRegex(ValueError, "^letter set repeats a letter: 'Aa'$"):
            e.Rule("page", "contains", "Aa")

    def test_a_rule_cannot_be_changed_once_made(self):
        rule = e.Rule("page", "begins", "L", False)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rule.positive = True
        self.assertEqual(len({rule, e.Rule("page", "begins", "L", False)}), 1)   # and can sit in a set

    def test_the_rule_space_is_the_whole_vocabulary(self):
        rules = list(e.rule_space(self.b, ["A", "HELP"], ["Michael", "Carrie"]))
        expected = {e.Rule(scope, match, value, positive)
                    for scope in ("name", "line", "page", "chapter", "next_to", "near")
                    for match, values in (("contains", ("A", "HELP")), ("begins", ("A", "HELP")),
                                          ("ends", ("A", "HELP")), ("is", ("Michael", "Carrie")))
                    for value in values
                    for positive in (True, False)}
        expected -= {e.Rule("name", "is", "Michael"), e.Rule("name", "is", "Carrie")}   # never the killer outright
        self.assertEqual(len(expected), 94)       # 6 places x 4 matches x 2 values x 2 ways, less those two
        self.assertEqual(set(rules), expected)
        self.assertEqual(len(rules), 94)          # and nothing comes out twice

    def test_a_rule_is_for_or_against_and_nothing_else(self):
        for scope, match, value in (("page", "begins", "L"), ("line", "is", "Michael")):
            for positive in (None, "false", 0, 1, 2):
                with self.assertRaises(ValueError) as refused:
                    e.Rule(scope, match, value, positive)
                self.assertEqual(str(refused.exception), f"positive must be True or False, got {positive!r}")

    def test_a_value_that_is_not_text_is_refused(self):
        for match in ("contains", "is"):
            for value in (5, None, ["L", "M"], b"L"):
                with self.assertRaises(ValueError) as refused:
                    e.Rule("page", match, value)
                self.assertEqual(str(refused.exception), f"value must be letters, got {value!r}")

    def test_named_people_come_in_the_order_given(self):
        given = ["Ruth", "Michael", "Holly", "Carrie"]
        rules = list(e.rule_space(self.b, [], given))
        self.assertEqual([r.value for r in rules if r.scope == "near" and r.positive], given)

    def test_an_unknown_match_is_refused_by_matches_too(self):
        with self.assertRaisesRegex(ValueError, "^unknown match 'rhymes'$"):
            e.matches("rhymes", "A", "AMBER")


class TheRuleSpace(unittest.TestCase):
    """What rule_space takes and what it turns away (issue #3)."""

    def setUp(self):
        self.b = e.Board(NAMES, SHAPE)

    def test_the_space_is_a_tuple(self):
        space = e.rule_space(self.b, ["A", "HELP"], ["Michael"])
        self.assertIsInstance(space, tuple)
        self.assertEqual(len(space), 72 + 11)     # 6 places x 3 matches x 2 sets x 2 ways, and 11 about Michael

    def test_a_tuple_is_taken_as_a_list_is(self):
        self.assertEqual(e.rule_space(self.b, ("A", "HELP"), ("Michael",)),
                         e.rule_space(self.b, ["A", "HELP"], ["Michael"]))

    def test_a_kind_of_list_or_of_tuple_is_taken_too(self):
        class Shortlist(list):
            pass
        Pair = collections.namedtuple("Pair", "first second")
        self.assertEqual(e.rule_space(self.b, Shortlist(["A", "HELP"]), Shortlist(["Michael"])),
                         e.rule_space(self.b, ["A", "HELP"], ["Michael"]))
        self.assertEqual(e.rule_space(self.b, Pair("A", "HELP"), Pair("Michael", "Ruth")),
                         e.rule_space(self.b, ["A", "HELP"], ["Michael", "Ruth"]))

    def test_nothing_given_is_an_empty_space(self):
        self.assertEqual(e.rule_space(self.b, []), ())
        self.assertEqual(e.rule_space(self.b, [], []), ())

    def test_the_killer_is_never_named_outright(self):
        space = e.rule_space(self.b, ["A"], ["Michael", "Carrie"])
        self.assertEqual([r for r in space if r.scope == "name" and r.match == "is"],
                         [e.Rule("name", "is", "Michael", False), e.Rule("name", "is", "Carrie", False)])

    def test_a_named_person_must_be_on_the_board(self):
        with self.assertRaises(ValueError) as refused:
            e.rule_space(self.b, ["A"], ["Michael", "Zebedee"])
        self.assertEqual(str(refused.exception), "'Zebedee' is named but is not on the board")

    def test_part_of_a_name_on_the_board_is_not_on_it_and_nor_is_more_than_one(self):
        # Maxwell, Michael, Ruth and Jack are on the board. "Max" begins one of them, "Well" ends
        # it, "Ich" is in the middle of another, and "Ruthie" and "Jackson" each hold one whole.
        for name in ("Max", "Well", "Ich", "Ruthie", "Jackson"):
            with self.assertRaises(ValueError) as refused:
                e.rule_space(self.b, [], [name])
            self.assertEqual(str(refused.exception), f"{name!r} is named but is not on the board")

    def test_a_named_person_is_found_whatever_the_case_and_kept_as_given(self):
        space = e.rule_space(self.b, [], ["ruth", "MICHAEL"])
        self.assertEqual([r.value for r in space if r.scope == "near" and r.positive], ["ruth", "MICHAEL"])

    def test_a_named_person_is_found_however_the_board_writes_its_names(self):
        in_capitals = e.Board([name.upper() for name in NAMES], SHAPE)
        space = e.rule_space(in_capitals, [], ["Ruth", "michael"])
        self.assertEqual([r.value for r in space if r.scope == "near" and r.positive], ["Ruth", "michael"])
        with_a_capital_inside = e.Board(["McCoy" if name == "Ruth" else name for name in NAMES], SHAPE)
        space = e.rule_space(with_a_capital_inside, [], ["Mccoy", "MCCOY"])
        self.assertEqual([r.value for r in space if r.scope == "near" and r.positive], ["Mccoy", "MCCOY"])

    def test_a_letter_set_is_kept_as_given(self):
        self.assertEqual({r.value for r in e.rule_space(self.b, ["help", "A", "Clue"])}, {"help", "A", "Clue"})

    def test_one_piece_of_text_is_not_a_list(self):
        for given in ("HELP", "A", "", b"HELP"):
            with self.assertRaises(ValueError) as refused:
                e.rule_space(self.b, given)
            self.assertEqual(str(refused.exception), f"letter sets must be a list or a tuple, got {given!r}")
        for given in ("Ruth", "", b"Ruth"):
            with self.assertRaises(ValueError) as refused:
                e.rule_space(self.b, ["A"], given)
            self.assertEqual(str(refused.exception), f"named people must be a list or a tuple, got {given!r}")

    def test_only_a_list_or_a_tuple_is_taken(self):
        def givens():
            return (None, 5, {"A", "E"}, frozenset({"A"}), {"A": 1}, iter(["A"]), (x for x in ["A"]),
                    range(3), collections.deque(["A"]), bytearray(b"HELP"), collections.UserList(["A"]))
        for given in givens():
            with self.assertRaises(ValueError) as refused:
                e.rule_space(self.b, given)
            self.assertEqual(str(refused.exception), f"letter sets must be a list or a tuple, got {given!r}")
        for given in givens():
            with self.assertRaises(ValueError) as refused:
                e.rule_space(self.b, ["A"], given)
            self.assertEqual(str(refused.exception), f"named people must be a list or a tuple, got {given!r}")

    def test_what_is_wrong_is_refused_at_the_call(self):
        for letter_sets, named, said in ((["A", "A1"], [], "value must be letters, got 'A1'"),
                                         (["A", "LL"], [], "letter set repeats a letter: 'LL'"),
                                         (["A", 5], [], "value must be letters, got 5"),
                                         (["A"], ["Ruth", 5], "value must be letters, got 5"),
                                         (["A"], ["Ruth", "R2"], "value must be letters, got 'R2'")):
            with self.assertRaises(ValueError) as refused:
                e.rule_space(self.b, letter_sets, named)      # not walked: the call itself refuses
            self.assertEqual(str(refused.exception), said)

    def test_the_first_thing_wrong_is_the_one_named(self):
        for letter_sets, named, said in (("A", "Ruth", "letter sets must be a list or a tuple, got 'A'"),
                                         (["A1"], "Ruth", "named people must be a list or a tuple, got 'Ruth'"),
                                         (["A", "A1"], ["Zebedee"], "value must be letters, got 'A1'"),
                                         (["A", "LL"], ["Zebedee"], "letter set repeats a letter: 'LL'"),
                                         (["A"], ["Zebedee", "R2"], "'Zebedee' is named but is not on the board"),
                                         (["A1", "LL"], [], "value must be letters, got 'A1'"),
                                         (["LL", "A1"], [], "letter set repeats a letter: 'LL'"),
                                         (["A"], ["R2", "Zebedee"], "value must be letters, got 'R2'"),
                                         # a list cannot go in a set, so these two say nothing was made one
                                         (["A", ["H", "E"]], [], "value must be letters, got ['H', 'E']"),
                                         (["A"], ["Ruth", ["Jack"]], "value must be letters, got ['Jack']")):
            with self.assertRaises(ValueError) as refused:
                e.rule_space(self.b, letter_sets, named)
            self.assertEqual(str(refused.exception), said)

    def test_the_rules_come_in_one_order(self):
        letter_sets, named = ["HELP", "A", "CLUE"], ["Michael", "Ruth", "Carrie"]      # in neither alphabetical order nor order of length, either way
        space = e.rule_space(self.b, letter_sets, named)
        self.assertEqual([scope for scope, _ in itertools.groupby(rule.scope for rule in space)],
                         ["name", "line", "page", "chapter", "next_to", "near"])
        on_a_line = [(r.match, r.value, r.positive) for r in space if r.scope == "line"]
        self.assertEqual(on_a_line, [
            ("contains", "HELP", True), ("contains", "HELP", False), ("contains", "A", True), ("contains", "A", False),
            ("contains", "CLUE", True), ("contains", "CLUE", False),
            ("begins", "HELP", True), ("begins", "HELP", False), ("begins", "A", True), ("begins", "A", False),
            ("begins", "CLUE", True), ("begins", "CLUE", False),
            ("ends", "HELP", True), ("ends", "HELP", False), ("ends", "A", True), ("ends", "A", False),
            ("ends", "CLUE", True), ("ends", "CLUE", False),
            ("is", "Michael", True), ("is", "Michael", False), ("is", "Ruth", True), ("is", "Ruth", False),
            ("is", "Carrie", True), ("is", "Carrie", False)])
        self.assertEqual((letter_sets, named), (["HELP", "A", "CLUE"], ["Michael", "Ruth", "Carrie"]))   # and are left so
        for scope in ("page", "chapter", "next_to", "near"):
            self.assertEqual([(r.match, r.value, r.positive) for r in space if r.scope == scope], on_a_line)
        self.assertEqual([(r.match, r.value, r.positive) for r in space if r.scope == "name"],
                         [rule for rule in on_a_line if rule[0] != "is" or not rule[2]])   # the same, less the killer's own

    def test_each_list_is_copied_once_so_what_was_checked_is_what_is_used(self):
        def shifty(kind, at_first, later):
            """A list or a tuple that holds something else each time it is walked after the first."""
            class Shifty(kind):
                walks = 0

                def __iter__(self):
                    self.walks += 1
                    return super().__iter__() if self.walks == 1 else iter(later)

            return Shifty(at_first)

        for kind in (list, tuple):
            named = shifty(kind, ["Ruth"], ["Zebedee"])
            self.assertEqual(e.rule_space(self.b, [], named), e.rule_space(self.b, [], ["Ruth"]))
            letter_sets = shifty(kind, ["A"], ["HELP"])
            self.assertEqual(e.rule_space(self.b, letter_sets, []), e.rule_space(self.b, ["A"], []))
            self.assertEqual((named.walks, letter_sets.walks), (1, 1))

    def test_what_is_given_twice_comes_out_twice(self):
        self.assertEqual(len(e.rule_space(self.b, ["A", "A"])), 72)
        self.assertEqual(len(e.rule_space(self.b, [], ["Ruth", "Ruth"])), 22)


class Properties(unittest.TestCase):
    """Things that must be true on any board, checked on random ones."""

    POOL = ("Aaron Beth Carl Dawn Evan Faye Gus Hope Ian Jade Kyle Lena Max Nora Owen Pia "
            "Quin Rae Seth Tess Uma Vic Wade Xena Yuri Zane Abel Bree Cody Dee Eli Fern "
            "Glen Hal Iris Joy Kai Lou Mae Ned Opal Paz Remy Sky Ty Val Wes Zoe").split()

    def boards(self):
        rng = random.Random(2026)
        for _ in range(25):
            names = rng.sample(self.POOL, 48)
            yield e.Board(names, (2, 2, 3, 4)), rng

    def test_scopes_nest(self):
        # found in a smaller scope => found in every scope that contains it
        wider = {"name": ["line"], "line": ["page"], "page": ["chapter"],
                 "next_to": ["line", "near"], "near": ["page"]}
        for board, rng in self.boards():
            for _ in range(40):
                match = rng.choice(("contains", "begins", "ends"))
                value = rng.choice("AEIORSTLN")
                for small, bigs in wider.items():
                    for i in range(len(board)):
                        if e.holds(e.Rule(small, match, value), board, i):
                            for big in bigs:
                                self.assertTrue(e.holds(e.Rule(big, match, value), board, i))

    def test_container_rules_cannot_split_a_container(self):
        for board, rng in self.boards():
            for scope in ("line", "page", "chapter"):
                rule = e.Rule(scope, rng.choice(("contains", "begins", "ends")), rng.choice("AEIORST"))
                for i in range(len(board)):
                    verdicts = {e.holds(rule, board, j) for j in board.cells(scope, i)}
                    self.assertEqual(len(verdicts), 1)

    def test_same_inputs_same_answer_in_every_run(self):
        # Python walks a set of words in a different order from one run to the next
        # (PYTHONHASHSEED), so code that leaned on a set's order would change its answer.
        script = ("from wrong_person import engine as e\n"
                  "names = 'Michael Maxwell Amber Carrie Edith Oscar Linda Simon Dennis Holly Jack Ruth'.split()\n"
                  "board = e.Board(names, (1, 2, 2, 3))\n"
                  "rules = list(e.rule_space(board, ['A', 'HELP'], ['Michael', 'Carrie', 'Holly', 'Ruth']))\n"
                  "print([r.to_list() for r in rules])\n"
                  "print([e.survivors([r], board) for r in rules])\n"
                  "print(e.audit(rules[:5], board), e.case_to_json(board, rules[:3]))\n"
                  "open_case = [e.Rule('page', 'begins', 'L', False), e.Rule('name', 'is', 'Michael', False)]\n"
                  "print(e.decoys(open_case, board, 1))\n")       # five decoys: an order to get wrong
        runs = set()
        for seed in ("1", "2", "3"):
            run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60,
                                 env={**os.environ, "PYTHONPATH": SRC, "PYTHONHASHSEED": seed})
            self.assertEqual(run.returncode, 0, run.stderr)
            runs.add(run.stdout)
        self.assertEqual(len(runs), 1)


class WholeCase(unittest.TestCase):
    def setUp(self):
        self.b = e.Board(NAMES, SHAPE)

    def test_the_worked_example_step_by_step(self):
        steps = [who(self.b, e.survivors(CASE[:k], self.b)) for k in range(1, 6)]
        self.assertEqual(steps[0], NAMES[:6])
        self.assertEqual(steps[1], ["Michael", "Maxwell", "Amber", "Edith"])
        self.assertEqual(steps[2], ["Michael", "Maxwell", "Edith"])
        self.assertEqual(steps[3], ["Michael", "Maxwell"])
        self.assertEqual(steps[4], ["Maxwell"])

    def test_it_is_sound_and_ends_on_the_decoy(self):
        report = e.audit(CASE, self.b)
        self.assertTrue(report.sound)
        self.assertEqual(self.b.names[report.killer], "Maxwell")
        self.assertEqual(who(self.b, e.decoys(CASE, self.b, report.killer)), ["Michael"])

    def test_clue_order_does_not_matter(self):
        rng = random.Random(1)
        for _ in range(20):
            shuffled = CASE[:]
            rng.shuffle(shuffled)
            self.assertEqual(e.survivors(shuffled, self.b), e.survivors(CASE, self.b))

    def test_audit_catches_a_rule_that_does_no_work(self):
        padded = CASE + [e.Rule("chapter", "contains", "A")]
        report = e.audit(padded, self.b)
        self.assertFalse(report.sound)
        self.assertEqual(report.redundant, (5,))

    def test_audit_catches_a_rule_that_does_no_work_wherever_it_sits(self):
        padded = CASE[:1] + [e.Rule("chapter", "contains", "A")] + CASE[1:]
        self.assertEqual(e.audit(padded, self.b).redundant, (1,))

    def test_audit_catches_a_wasted_first_clue(self):
        report = e.audit([e.Rule("chapter", "contains", "A")] + CASE, self.b)
        self.assertEqual(report.redundant, (0,))
        self.assertFalse(report.sound)

    def test_the_last_name_on_the_board_can_be_the_answer(self):
        self.assertEqual(who(self.b, e.survivors([e.Rule("name", "begins", "R")], self.b)), ["Ruth"])
        report = e.audit([e.Rule("name", "begins", "R")], self.b)
        self.assertTrue(report.sound)
        self.assertEqual(self.b.names[report.killer], "Ruth")

    def test_audit_catches_more_than_one_answer(self):
        report = e.audit(CASE[:-1], self.b)
        self.assertFalse(report.sound)
        self.assertIsNone(report.killer)
        self.assertEqual(who(self.b, report.survivors), ["Michael", "Maxwell"])

    def test_audit_catches_no_answer(self):
        report = e.audit(CASE + [e.Rule("name", "is", "Maxwell", False)], self.b)
        self.assertEqual(report.survivors, ())
        self.assertFalse(report.sound)
        self.assertIsNone(report.killer)

    def test_an_audit_cannot_be_changed_once_made(self):
        report = e.audit(CASE[:-1], self.b)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            report.survivors = (1,)

    def test_a_saved_case_has_a_fixed_form(self):
        saved = json.loads(e.case_to_json(self.b, CASE[:2]))
        self.assertEqual(saved, {"shape": [1, 2, 2, 3], "names": NAMES,
                                 "rules": [["page", "begins", "L", False],
                                           ["next_to", "contains", "A", True]]})

    def test_a_case_written_by_hand_is_read(self):
        board, rules = e.case_from_json(
            '{"shape": [1, 1, 1, 2], "names": ["Ann", "Bob"], "rules": [["name", "begins", "B", true]]}')
        self.assertEqual((list(board.names), board.shape), (["Ann", "Bob"], (1, 1, 1, 2)))
        self.assertEqual(rules, [e.Rule("name", "begins", "B", True)])
        self.assertEqual(who(board, e.survivors(rules, board)), ["Bob"])

    def test_rules_may_arrive_one_at_a_time(self):
        # A generator can be walked only once. The answer must not depend on that.
        self.assertEqual(e.survivors(iter(CASE), self.b), e.survivors(CASE, self.b))
        self.assertEqual(e.audit(iter(CASE), self.b), e.audit(CASE, self.b))
        self.assertEqual(e.decoys(iter(CASE), self.b, 1), e.decoys(CASE, self.b, 1))
        padded = CASE + [e.Rule("chapter", "contains", "A")]
        self.assertEqual(e.audit(iter(padded), self.b).redundant, (5,))     # the wasted clue is still seen

    def test_decoys_come_back_in_board_order(self):
        open_case = [e.Rule("page", "begins", "L", False), e.Rule("name", "is", "Michael", False)]
        self.assertEqual(who(self.b, e.decoys(open_case, self.b, 1)), ["Michael", "Amber", "Carrie", "Edith", "Oscar"])

    def test_a_saved_rule_may_be_a_list_or_a_tuple(self):
        for item in (["name", "is", "Michael", False], ("name", "is", "Michael", False)):
            self.assertEqual(e.Rule.from_list(item), CASE[4])

    def test_a_saved_rule_has_four_parts(self):
        for item in (["name", "is", "Michael"], ["name", "is", "Michael", False, "extra"], None, "name"):
            with self.assertRaises(ValueError) as refused:
                e.Rule.from_list(item)
            self.assertEqual(str(refused.exception),
                             f"a saved rule is [scope, match, value, positive], got {item!r}")

    def test_a_broken_saved_case_is_refused(self):
        good = json.loads(e.case_to_json(self.b, CASE))
        saved = lambda **changes: json.dumps({**good, **changes})
        no_case = "^a saved case is a JSON object with shape, names and rules$"
        no_list = "^the shape, names and rules of a saved case must each be a list$"
        broken = {
            "this is not JSON": "^a saved case must be JSON: ",
            "[]": no_case, "null": no_case, "42": no_case,
            json.dumps({"shape": good["shape"], "names": good["names"]}): no_case,
            json.dumps({"shape": good["shape"], "rules": good["rules"]}): no_case,
            json.dumps({"names": good["names"], "rules": good["rules"]}): no_case,
            saved(rules=None): no_list, saved(shape=12): no_list, saved(names="Michael"): no_list,
            saved(shape=[-1, -2, 2, 3]): "^shape must be four positive whole numbers",
            saved(shape=[True, 2, 2, 3]): "^shape must be four positive whole numbers",
            "[" * 100000: "^a saved case must be JSON: ",          # nested too deeply to read
            saved(names=good["names"][:-1] + [None]): "^names must be letters only$",
            saved(rules=[["name", "is", "Michael"]]): "^a saved rule is ",
            saved(rules=[["page", "begins", "L", "false"]]): "^positive must be True or False, got 'false'$",
            saved(rules=[["page", "begins", 5, True]]): "^value must be letters, got 5$",
            saved(rules=[["street", "begins", "L", True]]): "^unknown scope 'street'$",
        }
        for text, message in broken.items():
            with self.assertRaisesRegex(ValueError, message, msg=text[:70]):
                e.case_from_json(text)

    def test_a_saved_case_in_bytes_that_are_not_text_is_refused_as_not_json(self):
        with self.assertRaisesRegex(ValueError, "^a saved case must be JSON: "):
            e.case_from_json(b'{"shape": "\xff"}')

    def test_a_saved_case_holds_each_key_once(self):
        text = e.case_to_json(self.b, CASE)
        more = lambda extra: text.rstrip()[:-1] + ", " + extra + "}"
        self.assertEqual(json.loads(more('"rules": []'))["rules"], [])      # JSON itself keeps the last and says nothing
        for key, extra in (("rules", '"rules": []'), ("names", '"names": []'), ("shape", '"shape": [1, 2, 2, 3]'),
                           ("killer", '"killer": "Maxwell", "killer": "Michael"'),
                           ("shape", '"rules": [], "shape": [1, 2, 2, 3]')):    # two at once: the one the file gives first
            with self.assertRaises(ValueError) as refused:
                e.case_from_json(more(extra))
            self.assertEqual(str(refused.exception), f"a saved case holds each key once, got {key!r} twice")

    def test_a_key_may_repeat_inside_what_another_key_holds(self):
        text = e.case_to_json(self.b, CASE)
        board, rules = e.case_from_json(text.rstrip()[:-1] + ', "note": {"shape": 1, "shape": 2}}')
        self.assertEqual((list(board.names), rules), (NAMES, CASE))

    def test_a_saved_case_may_carry_other_keys(self):
        good = json.loads(e.case_to_json(self.b, CASE))
        board, rules = e.case_from_json(json.dumps({**good, "killer": "Maxwell", "note": "for Tuesday"}))
        self.assertEqual((list(board.names), rules), (NAMES, CASE))

    def test_a_case_survives_a_round_trip_through_json(self):
        board, rules = e.case_from_json(e.case_to_json(self.b, CASE))
        self.assertEqual(rules, CASE)
        self.assertEqual(e.audit(rules, board), e.audit(CASE, self.b))


class Wording(unittest.TestCase):
    RULE = ("must be one word of at most 9 letters, A to Z with or without accents, "
            "starting with a capital and not all capitals")
    RIDDLE_OK = "the cat who chases Jerry"
    PAGE = "a character that cannot go on a page"
    # Unicode's "default ignorable" code points, as its file DerivedCoreProperties.txt 16.0.0 lists them
    IGNORABLE = ((0x00AD, 0x00AD), (0x034F, 0x034F), (0x061C, 0x061C), (0x115F, 0x1160), (0x17B4, 0x17B5),
                 (0x180B, 0x180F), (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x206F), (0x3164, 0x3164),
                 (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0x1BCA0, 0x1BCA3),
                 (0x1D173, 0x1D17A), (0xE0000, 0xE0FFF))

    def refusal(self, name, odd=None):
        """How a name that breaks the rule is refused; `odd` is the first character, as written in it,
        that is not a letter A to Z with or without accents."""
        return f"{name!r} {self.RULE}" + ("" if odd is None else f": {odd!r} (U+{ord(odd):04X}) is not a letter A to Z")

    def refusal_for_a_mark(self, name, code):
        """How a name whose first character is a mark that comes off whole is refused: by the mark's code."""
        return f"{name!r} {self.RULE}: it starts with an accent or other mark, U+{code}, before any letter"

    def test_sentences(self):
        say = wording.sentence
        self.assertEqual(say(CASE[0]), "There is no name beginning with L on the killer's page.")
        self.assertEqual(say(CASE[1]), "The killer is next to a name containing A.")
        self.assertEqual(say(CASE[2]), "The killer's name does not begin with A.")
        self.assertEqual(say(CASE[3]), "The killer is near a name beginning with H, E, L or P.")
        self.assertEqual(say(CASE[4], RIDDLE), "The police arrested the wrong person.")
        self.assertEqual(say(e.Rule("line", "is", "Carrie"), "Stephen King's prom queen"),
                         "Stephen King's prom queen is on the killer's line.")
        self.assertEqual(say(e.Rule("near", "is", "Michael", False), RIDDLE),
                         "The singer of Thriller is not near the killer.")
        self.assertEqual(say(e.Rule("next_to", "is", "Michael"), RIDDLE),
                         "The singer of Thriller is next to the killer.")
        self.assertEqual(say(e.Rule("chapter", "ends", "D")),
                         "There is a name ending in D in the killer's chapter.")

    def test_every_letter_clue_reads_as_its_rule_means(self):
        # All 36: six places, three matches, both ways. Two sentences swapped would
        # still be two different sentences, so each one is written out.
        expected = {
            ("name", "contains", True): "The killer's name contains E.",
            ("name", "contains", False): "The killer's name does not contain E.",
            ("name", "begins", True): "The killer's name begins with E.",
            ("name", "begins", False): "The killer's name does not begin with E.",
            ("name", "ends", True): "The killer's name ends in E.",
            ("name", "ends", False): "The killer's name does not end in E.",
            ("line", "contains", True): "There is a name containing E on the killer's line.",
            ("line", "contains", False): "There is no name containing E on the killer's line.",
            ("line", "begins", True): "There is a name beginning with E on the killer's line.",
            ("line", "begins", False): "There is no name beginning with E on the killer's line.",
            ("line", "ends", True): "There is a name ending in E on the killer's line.",
            ("line", "ends", False): "There is no name ending in E on the killer's line.",
            ("page", "contains", True): "There is a name containing E on the killer's page.",
            ("page", "contains", False): "There is no name containing E on the killer's page.",
            ("page", "begins", True): "There is a name beginning with E on the killer's page.",
            ("page", "begins", False): "There is no name beginning with E on the killer's page.",
            ("page", "ends", True): "There is a name ending in E on the killer's page.",
            ("page", "ends", False): "There is no name ending in E on the killer's page.",
            ("chapter", "contains", True): "There is a name containing E in the killer's chapter.",
            ("chapter", "contains", False): "There is no name containing E in the killer's chapter.",
            ("chapter", "begins", True): "There is a name beginning with E in the killer's chapter.",
            ("chapter", "begins", False): "There is no name beginning with E in the killer's chapter.",
            ("chapter", "ends", True): "There is a name ending in E in the killer's chapter.",
            ("chapter", "ends", False): "There is no name ending in E in the killer's chapter.",
            ("next_to", "contains", True): "The killer is next to a name containing E.",
            ("next_to", "contains", False): "The killer is not next to any name containing E.",
            ("next_to", "begins", True): "The killer is next to a name beginning with E.",
            ("next_to", "begins", False): "The killer is not next to any name beginning with E.",
            ("next_to", "ends", True): "The killer is next to a name ending in E.",
            ("next_to", "ends", False): "The killer is not next to any name ending in E.",
            ("near", "contains", True): "The killer is near a name containing E.",
            ("near", "contains", False): "The killer is not near any name containing E.",
            ("near", "begins", True): "The killer is near a name beginning with E.",
            ("near", "begins", False): "The killer is not near any name beginning with E.",
            ("near", "ends", True): "The killer is near a name ending in E.",
            ("near", "ends", False): "The killer is not near any name ending in E.",
        }
        self.assertEqual(len(expected), 36)
        for (scope, match, positive), text in expected.items():
            self.assertEqual(wording.sentence(e.Rule(scope, match, "E", positive)), text)

    def test_a_letter_is_printed_as_a_capital(self):
        self.assertEqual(wording.sentence(e.Rule("name", "contains", "a")), "The killer's name contains A.")
        self.assertEqual(wording.letters("help"), "H, E, L or P")

    def test_the_last_clue_is_the_note(self):
        self.assertEqual(wording.NOTE, "The police arrested the wrong person.")
        self.assertEqual(wording.sentence(CASE[4]), wording.NOTE)           # needs no riddle
        self.assertEqual(wording.sentence(CASE[4], RIDDLE), wording.NOTE)   # and never prints one
        self.assertEqual(wording.sentence(CASE[4], "Michael"), wording.NOTE)   # whatever it holds

    def test_the_arrest_names_the_arrested_person_by_riddle(self):
        self.assertEqual(wording.arrest(RIDDLE), "Police have arrested the singer of Thriller.")

    def test_an_arrest_without_a_riddle_is_refused(self):
        for riddle in (None, "", "   "):
            with self.assertRaisesRegex(ValueError, "^a named person is only ever printed as a riddle, and none was given$"):
                wording.arrest(riddle)

    def test_a_clue_never_names_the_killer_outright(self):
        with self.assertRaisesRegex(ValueError, "^a clue never names the killer outright$"):
            wording.sentence(e.Rule("name", "is", "Michael"), RIDDLE)

    def test_a_named_person_is_never_printed_without_a_riddle(self):
        for scope in ("line", "page", "chapter", "next_to", "near"):
            for riddle in (None, "", "   "):
                with self.assertRaisesRegex(ValueError, "^a named person is only ever printed as a riddle, and none was given$"):
                    wording.sentence(e.Rule(scope, "is", "Michael"), riddle)

    def test_a_riddle_that_holds_the_name_is_refused(self):
        for scope in ("line", "page", "chapter", "next_to", "near"):
            for riddle in ("Michael", "michael, the singer of Thriller", "the singer Michael's sister adores"):
                for positive in (True, False):
                    with self.assertRaises(ValueError) as refused:
                        wording.sentence(e.Rule(scope, "is", "Michael", positive), riddle)
                    self.assertEqual(str(refused.exception), f"the riddle {riddle!r} gives the name away")

    def test_a_name_with_an_accent_is_guarded_like_any_other(self):
        zoe = "Zo\u00eb"                               # one letter outside a to z
        riddle = f"{zoe} Kravitz's first name"
        self.assertEqual(wording.check_riddles({zoe: [riddle]}), [f"{zoe}: {riddle!r} gives the name away"])
        with self.assertRaisesRegex(ValueError, "gives the name away$"):
            wording.sentence(e.Rule("near", "is", zoe, False), riddle)
        self.assertEqual(wording.check_riddles({zoe: ["the daughter of Lenny Kravitz"]}), [])

    def test_the_name_is_found_in_its_riddle_in_plain_letters(self):
        # an accent on either side, written as a mark of its own, or under the letter, does not hide the name
        cases = [("Zo\u00eb", "the actress Zoe Kravitz"), ("Zoe", "the actress Zo\u00eb Kravitz"),
                 ("Zo\u00eb", "the actress Zoe\u0308 Kravitz"), ("Zoe\u0308", "the actress Zo\u00eb Kravitz"),
                 ("Francois", "the singer Fran\u00e7ois Hardy")]
        for name, riddle in cases:
            self.assertEqual(wording.check_riddles({name: [riddle]}), [f"{name}: {riddle!r} gives the name away"], riddle)
        for name, riddle in cases[:3] + cases[4:]:      # the engine's own Rule takes no name with a mark of its own
            with self.assertRaisesRegex(ValueError, "gives the name away$"):
                wording.sentence(e.Rule("near", "is", name, False), riddle)

    def test_a_riddle_that_cannot_go_on_a_page_is_refused_wherever_it_is_printed(self):
        # inside the riddle, or at either end of it, where a check of the trimmed riddle would miss it
        for riddle, code in (("the cat called To\u200bm", 0x200B), ("the singer\u034f of Thriller", 0x034F),
                             ("the singer of\nThriller", 0x000A), ("the singer of Thriller\n", 0x000A),
                             ("\tthe singer of Thriller", 0x0009), ("the singer of Thriller\u2028", 0x2028)):
            message = f"the riddle {riddle!r} holds U+{code:04X}, {self.PAGE}"
            with self.assertRaises(ValueError) as refused:
                wording.arrest(riddle)
            self.assertEqual(str(refused.exception), message)
            for positive in (True, False):
                with self.assertRaises(ValueError) as refused:
                    wording.sentence(e.Rule("near", "is", "Tom", positive), riddle)
                self.assertEqual(str(refused.exception), message)

    def test_a_riddle_may_hold_somebody_elses_name(self):
        self.assertEqual(wording.sentence(e.Rule("line", "is", "Homer"), "Bart Simpson's father"),
                         "Bart Simpson's father is on the killer's line.")

    def test_a_riddle_that_is_not_text_is_refused(self):
        table = {"Michael": ["the singer of Thriller"]}
        with self.assertRaisesRegex(ValueError, r"^a riddle is one piece of text, got \['the singer of Thriller'\]$"):
            wording.sentence(e.Rule("near", "is", "Michael"), table["Michael"])   # the whole list, by mistake
        with self.assertRaisesRegex(ValueError, "^a riddle is one piece of text, got b'the singer of Thriller'$"):
            wording.arrest(b"the singer of Thriller")
        for riddle in (5, 0, [], b""):
            with self.assertRaises(ValueError) as refused:
                wording.arrest(riddle)
            self.assertEqual(str(refused.exception), f"a riddle is one piece of text, got {riddle!r}")

    def test_a_riddle_always_opens_its_clue(self):
        board = e.Board(NAMES, SHAPE)
        for rule in e.rule_space(board, ["A"], ["Michael"]):
            if rule.match == "is" and rule.scope != "name":
                text = wording.sentence(rule, RIDDLE)
                self.assertTrue(text.startswith("The singer of Thriller is "), text)

    def test_the_printed_rules_say_what_solvers_had_to_guess(self):
        # Blind test solves (2026-11-20): the page never said these two things, and a
        # solver who guesses the other way gets a different answer in most cases.
        rules = wording.RULES_TEXT
        self.assertIn("its capital first letter included", rules)   # "contains" counts the initial
        self.assertIn("never the killer's own", rules)              # neighbours leave the killer out
        self.assertIn("count the killer's own name too", rules)     # containers still count it

    def test_the_printed_rules_in_full(self):
        self.assertEqual(wording.RULES_TEXT,
                         "Every clue is true of the killer. A list of letters means any one of them. "
                         "A name contains a letter wherever it appears, its capital first letter included. "
                         "Clues about a line, page or chapter count the killer's own name too. "
                         "Next to: immediately left or right on the same line. Near: touching in any "
                         "direction, diagonals included, on the same page. "
                         "Next to and near clues are about other names, never the killer's own.")

    def test_every_rule_in_the_space_has_a_sentence(self):
        board = e.Board(NAMES, SHAPE)
        seen = set()
        for rule in e.rule_space(board, ["A", "HELP"], ["Michael"]):
            text = wording.sentence(rule, RIDDLE)
            self.assertTrue(text.endswith(".") and text[0].isupper())
            self.assertNotIn(text, seen)          # no two rules read the same, while only one
            #                                       person is named: every "name is X, negative"
            #                                       rule prints as the note
            seen.add(text)

    def test_the_riddle_table_is_clean(self):
        table = wording.load_riddles()
        self.assertEqual(wording.check_riddles(table), [])
        self.assertIn("the singer of Thriller", table["Michael"])

    def test_the_riddle_table_quotes_sentences_the_code_prints(self):
        path = Path(wording.__file__).with_name("riddles.json")
        notes = " ".join(json.loads(path.read_text(encoding="utf-8"))["_rules"])
        self.assertIn(wording.arrest("___").rstrip("."), notes)
        self.assertIn(wording.sentence(e.Rule("next_to", "is", "Michael"), "___").rstrip("."), notes)
        self.assertNotIn("The killer is", notes)

    def test_the_checker_catches_bad_entries(self):
        bad = {"Michael": ["the singer of Thriller"], "Janet": ["the singer of thriller"],
               "Mary Ann": ["x"], "Bob": ["Bob the Builder"], "Sue": []}
        problems = " ".join(wording.check_riddles(bad))
        for expected in ("under both", "Mary Ann", "gives the name away", "at least one"):
            self.assertIn(expected, problems)

    def test_a_name_may_have_nine_letters_and_no_more(self):
        self.assertEqual(wording.check_riddles({"Elizabeth": ["the longest-reigning British queen"]}), [])
        self.assertEqual(wording.check_riddles({"Maximilian": ["the emperor of Mexico shot in 1867"]}),
                         [f"'Maximilian' {self.RULE}"])

    def test_a_name_in_the_table_starts_with_a_capital(self):
        self.assertEqual(wording.check_riddles({"tom": ["the cat who chases Jerry"]}),
                         [f"'tom' {self.RULE}"])

    def test_a_name_that_starts_with_an_accent_is_refused(self):
        # "starting with a capital" is read as written, so an accent before the first letter breaks it;
        # the accent draws on the quote before the name, so the refusal says what it is, by its code
        for name, code in (("\u0301Tom", "0301"), ("\u0308Zo\u00eb", "0308")):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal_for_a_mark(name, code)],
                             ascii(name))
        # the accent comes first, so it is named before a later letter that has no plain form
        name = "\u0301S\u00f8ren"
        self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal_for_a_mark(name, "0301")])

    def test_a_name_in_all_capitals_is_refused(self):
        for name in ("JOHN", "A", "MCCOY"):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [f"{name!r} {self.RULE}"], name)

    def test_a_name_with_a_capital_inside_passes(self):
        for name in ("McCoy", "MacLeod", "LeBlanc", "DeShawn"):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [], name)

    def test_a_name_is_counted_in_its_plain_letters(self):
        # the accent written as its own mark makes ten characters, and still nine letters;
        # a mark comes off whether it is drawn over a letter, under it (a cedilla, a comma),
        # through it (a stroke) or at its upper right (the horn, as in Vietnamese)
        for name in ("Zo\u00eb", "Ren\u00e9e", "\u00c9lisabeth", "E\u0301lisabeth",
                     "Fran\u00e7ois", "\u015etefan", "\u0218tefan", "D\u01b0\u01a1ng", "Ma\u0335x"):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [], name)
        ten = "\u00c9lisabeths"
        self.assertEqual(wording.check_riddles({ten: [self.RIDDLE_OK]}), [f"{ten!r} {self.RULE}"])

    def test_a_name_with_letters_that_have_no_plain_form_is_refused(self):
        for name, odd in (("\u03a3\u03bf\u03c6\u03af\u03b1", "\u03a3"), ("S\u00f8ren", "\u00f8"), ("Stra\u00dfe", "\u00df")):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal(name, odd)], name)

    def test_the_refusal_of_a_name_names_the_character_as_written(self):
        # Unicode splits each of the first three in two, and the refusal names what was written, not a part
        # of it; the last is written in two, and the refusal names the letter, not the two joined
        for name, odd in (("\u0386nna", "\u0386"), ("\u0419van", "\u0419"), ("\uac00ra", "\uac00"),
                          ("\u0391\u0301nna", "\u0391")):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal(name, odd)], ascii(name))
        # an accent written apart from its letter is not named when the name breaks the rule another way
        ten = "E\u0301lisabeths"
        self.assertEqual(wording.check_riddles({ten: [self.RIDDLE_OK]}), [self.refusal(ten)])

    def test_two_names_that_are_one_in_plain_letters_are_refused(self):
        self.assertEqual(wording.check_riddles({"Zoe": ["the first riddle"], "Zo\u00eb": ["the second riddle"]}),
                         ["'Zo\u00eb' and 'Zoe' are one name in plain letters"])
        self.assertEqual(wording.check_riddles({"McCoy": ["the first riddle"], "Mccoy": ["the second riddle"]}),
                         ["'Mccoy' and 'McCoy' are one name in plain letters"])
        self.assertEqual(wording.check_riddles({"Zoe": ["the first riddle"], "Zak": ["the second riddle"]}), [])

    def test_the_refusal_names_the_first_character_that_is_not_a_letter_a_to_z(self):
        self.assertEqual(wording.check_riddles({"S\u00f8ren": [self.RIDDLE_OK]}),
                         [f"'S\u00f8ren' {self.RULE}: '\u00f8' (U+00F8) is not a letter A to Z"])
        self.assertEqual(wording.check_riddles({"Mary-Kate": [self.RIDDLE_OK]}),
                         [f"'Mary-Kate' {self.RULE}: '-' (U+002D) is not a letter A to Z"])
        self.assertEqual(wording.check_riddles({"To\u200bm": [self.RIDDLE_OK]}),
                         [f"'To\\u200bm' {self.RULE}: '\\u200b' (U+200B) is not a letter A to Z"])

    def test_a_name_with_a_digit_a_sign_or_a_space_is_refused(self):
        for name, odd in (("Jo3", "3"), ("Jo_e", "_"), ("Mary-Kate", "-"), ("Jo Ann", " "), ("O'Neil", "'"),
                          ("Tom ", " "), (" Tom", " "), ("Tom\n", "\n"), ("Tom\t", "\t")):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal(name, odd)], name)

    def test_a_name_with_a_hidden_character_is_refused(self):
        for name, odd in (("To\u200bm", "\u200b"), ("Tom\u202e", "\u202e"), ("To\u034fm", "\u034f"),
                          ("Tom\ufe0f", "\ufe0f")):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal(name, odd)], repr(name))

    def test_a_name_in_other_forms_of_letters_is_refused(self):
        # full width, a trade mark sign, a numero sign, circled letters, a Roman numeral, a ligature
        for name, odd in (("\uff2a\uff4f\uff48\uff4e", "\uff2a"), ("Jo\u2122", "\u2122"),
                          ("\u2116ah", "\u2116"), ("\u24c9\u24de\u24dc", "\u24c9"),
                          ("\u216cily", "\u216c"), ("So\ufb01e", "\ufb01")):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal(name, odd)], name)

    def test_accents_come_off_by_tables_every_python_holds_alike(self):
        # U+1DC4 is a mark Unicode added after 3.2, whose tables every Python holds: it stays on, everywhere
        name = "To\u1dc4m"
        self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal(name, "\u1dc4")])

    def test_a_name_with_an_enclosing_or_spacing_mark_is_refused(self):
        # an enclosing circle, and a vowel sign that takes up room beside its letter (as in Hindi):
        # neither has a combining class, so neither comes off
        for name, odd in (("To\u20ddm", "\u20dd"), ("To\u093em", "\u093e")):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal(name, odd)], ascii(name))

    def test_a_name_of_nothing_or_of_marks_alone_is_refused(self):
        self.assertEqual(wording.check_riddles({"": [self.RIDDLE_OK]}), [self.refusal("")])
        for name in ("\u0301", "\u0301\u0308"):
            self.assertEqual(wording.check_riddles({name: [self.RIDDLE_OK]}), [self.refusal_for_a_mark(name, "0301")],
                             ascii(name))

    def test_a_name_that_breaks_the_rule_is_still_checked_against_the_others(self):
        self.assertEqual(wording.check_riddles({"Zoe": ["the first riddle"], "ZO\u00cb": ["the second riddle"]}),
                         [self.refusal("ZO\u00cb"), "'ZO\u00cb' and 'Zoe' are one name in plain letters"])

    def test_a_name_without_a_list_of_riddles_still_counts_as_a_name(self):
        self.assertEqual(wording.check_riddles({"Zoe": "the first riddle", "Zo\u00eb": ["the second riddle"]}),
                         ["Zoe needs a list with at least one riddle",
                          "'Zo\u00eb' and 'Zoe' are one name in plain letters"])

    def test_the_riddle_table_states_the_name_rule_the_checker_holds(self):
        path = Path(wording.__file__).with_name("riddles.json")
        notes = " ".join(json.loads(path.read_text(encoding="utf-8"))["_rules"])
        rule = wording.check_riddles({"tom": ["x"]})[0].split(" must be ", 1)[1]
        self.assertIn(rule, notes)

    def test_a_name_needs_a_list_even_for_one_riddle(self):
        self.assertEqual(wording.check_riddles({"Tom": "the cat who chases Jerry"}),
                         ["Tom needs a list with at least one riddle"])

    def test_a_riddle_gives_the_name_away_in_any_case(self):
        self.assertEqual(wording.check_riddles({"Tom": ["the cat his owner calls TOM"]}),
                         ["Tom: 'the cat his owner calls TOM' gives the name away"])

    def test_the_checker_keeps_going_after_a_name_with_no_riddles(self):
        self.assertEqual(wording.check_riddles({"Sue": [], "Bob": ["Bob the Builder"]}),
                         ["Sue needs a list with at least one riddle",
                          "Bob: 'Bob the Builder' gives the name away"])

    def test_a_riddle_under_two_names_is_reported_with_both(self):
        table = {"Michael": ["the singer of Thriller"], "Janet": ["the  singer of thriller"]}
        self.assertEqual(wording.check_riddles(table),
                         ["'the  singer of thriller' is under both Michael and Janet"])

    def test_a_riddle_gives_the_name_away_even_as_a_possessive(self):
        self.assertEqual(wording.check_riddles({"Bob": ["the man in Bob's your uncle"]}),
                         ["Bob: \"the man in Bob's your uncle\" gives the name away"])

    def test_a_riddle_gives_the_name_away_whatever_touches_it(self):
        for line in ("Tom, the cat who chases Jerry", "the cat called Tom!", "the cat in Tom\u2019s house",
                     "the cat (Tom) who chases Jerry", "the cat in Tom-and-Jerry", 'the cat in "Tom and Jerry"',
                     "the cat in Tom_and_Jerry", "the cat called Tom2"):
            self.assertEqual(wording.check_riddles({"Tom": [line]}),
                             [f"Tom: {line!r} gives the name away"], line)

    def test_a_name_inside_a_longer_word_gives_nothing_away(self):
        self.assertEqual(wording.check_riddles({"Ken": ["the colonel of Kentucky Fried Chicken"]}), [])
        self.assertEqual(wording.check_riddles({"Tom": ["the town of Toms River", "the tomcat on the fence"]}), [])
        # a letter with no plain form is still a letter of its word
        self.assertEqual(wording.check_riddles({"Micha": ["the town of Micha\u0142owo"]}), [])

    def test_an_empty_riddle_is_reported(self):
        self.assertEqual(wording.check_riddles({"Tom": [""]}), ["Tom: '' is not a riddle"])
        self.assertEqual(wording.check_riddles({"Tom": ["  "]}), ["Tom: '  ' is not a riddle"])

    def test_a_riddle_that_is_not_text_is_reported_and_the_check_goes_on(self):
        self.assertEqual(wording.check_riddles({"Tom": [5, "Tom the cat"], "Sue": [None]}),
                         ["Tom: 5 is not a riddle", "Tom: 'Tom the cat' gives the name away",
                          "Sue: None is not a riddle"])

    def test_the_same_riddle_twice_under_one_name_is_reported(self):
        table = {"Tom": ["the cat who chases Jerry", "The cat who  chases Jerry"]}
        self.assertEqual(wording.check_riddles(table), ["Tom: 'The cat who  chases Jerry' is listed twice"])

    def test_the_checker_catches_a_stray_space_and_a_full_stop(self):
        for line in (" the orphan with red hair", "the orphan with red hair ", "the orphan with red hair."):
            problems = wording.check_riddles({"Ann": [line]})
            self.assertEqual(len(problems), 1, line)
            self.assertIn("outer spaces or full stop", problems[0])

    def test_a_riddle_with_a_character_that_cannot_go_on_a_page_is_refused(self):
        # a control (six of them), a format (three), a surrogate, a private use, a line and a paragraph separator
        for code in (0x09, 0x0A, 0x0D, 0x00, 0x7F, 0x85, 0x200B, 0x00AD, 0x202E, 0xD800, 0xE000, 0x2028, 0x2029):
            line = "the cat who" + chr(code) + "chases Jerry"
            self.assertEqual(wording.check_riddles({"Tom": [line]}),
                             [f"Tom: {line!r} holds U+{code:04X}, {self.PAGE}"], hex(code))

    def test_only_the_first_such_character_is_named(self):
        line = "the cat\nwho\tchases Jerry"                # the first, U+000A, and not the lowest, U+0009
        self.assertEqual(wording.check_riddles({"Tom": [line]}), [f"Tom: {line!r} holds U+000A, {self.PAGE}"])
        line = "the cat\u034fwho\nnaps"                    # the first, U+034F, though U+000A is of the six kinds
        self.assertEqual(wording.check_riddles({"Tom": [line]}), [f"Tom: {line!r} holds U+034F, {self.PAGE}"])

    def test_every_character_unicode_draws_as_nothing_is_refused_in_a_riddle(self):
        for low, high in self.IGNORABLE:
            for code in range(low, high + 1):
                line = "the cat who" + chr(code) + "chases Jerry"
                self.assertEqual(wording.check_riddles({"Tom": [line]}),
                                 [f"Tom: {line!r} holds U+{code:04X}, {self.PAGE}"], hex(code))

    def test_the_characters_beside_those_may_go_on_a_page(self):
        # one before and one after each range of IGNORABLE, unless another rule refuses that one
        for code in (0x00AC, 0x00AE, 0x034E, 0x0350, 0x061B, 0x061D, 0x115E, 0x1161, 0x17B3, 0x17B6, 0x180A, 0x1810,
                     0x200A, 0x2010, 0x202F, 0x205F, 0x2070, 0x3163, 0x3165, 0xFDFF, 0xFE10, 0xFEFE, 0xFF00,
                     0xFF9F, 0xFFA1, 0xFFEF, 0x1BC9F, 0x1BCA4, 0x1D172, 0x1D17B, 0xDFFFF, 0xE1000):
            line = "the cat who" + chr(code) + "chases Jerry"
            self.assertEqual(wording.check_riddles({"Tom": [line]}), [], hex(code))

    def test_a_hidden_character_is_found_in_any_of_a_names_riddles(self):
        lines = ["the cat who chases Jerry", "the cat who\u200bnaps", "the grey cat"]
        self.assertEqual(wording.check_riddles({"Tom": lines}), [f"Tom: {lines[1]!r} holds U+200B, {self.PAGE}"])

    def test_every_problem_with_a_riddle_is_reported(self):
        line = " the cat called Tom\u200b"
        self.assertEqual(wording.check_riddles({"Tom": [line]}),
                         [f"Tom: {line!r} should have no outer spaces or full stop",
                          f"Tom: {line!r} holds U+200B, {self.PAGE}", f"Tom: {line!r} gives the name away"])

    def test_a_hidden_character_at_either_end_of_a_riddle_is_named_too(self):
        for line, code in (("the cat who chases Jerry\n", 0x000A), ("\tthe cat who chases Jerry", 0x0009)):
            self.assertEqual(wording.check_riddles({"Tom": [line]}),
                             [f"Tom: {line!r} should have no outer spaces or full stop",
                              f"Tom: {line!r} holds U+{code:04X}, {self.PAGE}"], line)

    def test_a_riddle_may_hold_accents_written_either_way(self):
        self.assertEqual(wording.check_riddles({"Tom": ["the cat in the caf\u00e9", "the cat by the cafe\u0301"]}), [])

    def test_a_riddle_may_hold_a_character_unicode_has_not_assigned(self):
        self.assertEqual(unicodedata.category("\u0378"), "Cn")     # unassigned, and not one Unicode draws as nothing
        self.assertEqual(wording.check_riddles({"Tom": ["the cat who\u0378chases Jerry"]}), [])

    def test_a_zero_width_space_cannot_hide_the_name(self):
        line = "the cat called To\u200bm"                # reads as Tom; the give-away check sees To and m
        self.assertEqual(wording.check_riddles({"Tom": [line]}), [f"Tom: {line!r} holds U+200B, {self.PAGE}"])

    def test_a_riddle_of_nothing_but_a_zero_width_space_is_refused(self):
        self.assertEqual(wording.check_riddles({"Tom": ["\u200b"]}), [f"Tom: '\\u200b' holds U+200B, {self.PAGE}"])

    def test_markup_ampersands_and_spaces_are_left_to_the_page(self):
        lines = ["the duo Simon & Garfunkel", "the singer in <b>bold</b>", "the singer of Rock &amp; Roll",
                 "the cat who\u00a0chases Jerry"]
        self.assertEqual(wording.check_riddles({"Sue": lines}), [])

    def test_a_riddle_file_of_ones_own_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            path.write_text('{"_note": "skipped", "Tom": ["the cat who chases Jerry"]}', encoding="utf-8")
            self.assertEqual(wording.load_riddles(path), {"Tom": ["the cat who chases Jerry"]})

    def test_a_riddle_file_may_hold_letters_outside_ascii(self):
        table = {"Zo\u00eb": ["the heroine of a French novel"], "Ren\u00e9e": ["the star of Bridget Jones\u2019s Diary"]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            path.write_bytes(json.dumps(table, ensure_ascii=False).encode("utf-8"))
            self.assertEqual(wording.load_riddles(path), table)

    def test_a_riddle_file_with_a_line_break_in_a_riddle_is_refused(self):
        line = "the cat who\nchases Jerry"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            path.write_text('{"Tom": ["the cat who\\nchases Jerry"]}', encoding="utf-8")
            with self.assertRaises(ValueError) as refused:
                wording.load_riddles(path)
            self.assertEqual(str(refused.exception), f"mine.json: Tom: {line!r} holds U+000A, {self.PAGE}")

    def test_a_name_listed_twice_in_a_file_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            path.write_text('{"Peter": ["the boy who never grew up"], "Wendy": ["the girl who flew to Neverland"], '
                            '"Peter": ["the first pope"]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"^mine\.json: Peter is listed twice$"):
                wording.load_riddles(path)

    def test_a_name_listed_twice_is_reported_once_whatever_else_is_true(self):
        files = {
            # the same riddles both times: nothing would be lost, and it is still a slip
            '{"Jack": ["the lad with the beanstalk"], "Jack": ["the lad with the beanstalk"]}':
                "mine.json: Jack is listed twice",
            # three times is one report, not two
            '{"Jack": ["the lad with the beanstalk"], "Jack": ["the giant killer"], "Jack": ["the nimble one"]}':
                "mine.json: Jack is listed twice",
            # two names listed twice are both reported, in the order the file first gives them
            '{"Jill": ["the girl on the hill"], "Jack": ["the lad with the beanstalk"], '
            '"Jack": ["the giant killer"], "Jill": ["the one who came tumbling after"]}':
                "mine.json: Jill is listed twice; Jack is listed twice",
            # and another fault in the file does not hide it
            '{"Jack": ["the lad with the beanstalk"], "Jack": ["the giant killer"], "jill": ["the girl on the hill"]}':
                f"mine.json: Jack is listed twice; 'jill' {self.RULE}",
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            for content, message in files.items():
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError) as refused:
                    wording.load_riddles(path)
                self.assertEqual(str(refused.exception), message)

    def test_notes_may_repeat_and_what_they_hold_is_not_read(self):
        table = {"Carrie": ["the prom queen in the film of 1976"], "Nancy": ["the teenage detective Miss Drew"]}
        files = ('{"_": "horror", "Carrie": ["the prom queen in the film of 1976"], '
                 '"_": "detectives", "Nancy": ["the teenage detective Miss Drew"]}',
                 '{"_about": {"by": "me", "by": "you", "Nancy": 1, "Nancy": 2}, '
                 '"Carrie": ["the prom queen in the film of 1976"], "Nancy": ["the teenage detective Miss Drew"]}')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            for content in files:
                path.write_text(content, encoding="utf-8")
                self.assertEqual(wording.load_riddles(path), table, content)

    def test_every_refusal_of_a_file_starts_with_its_name(self):
        broken = {"not JSON": b"this is not JSON",
                  "not UTF-8": b'{"Zo\xeb": ["the heroine of a French novel"]}',
                  "a byte-order mark": b'\xef\xbb\xbf{"Tom": ["the cat who chases Jerry"]}',
                  "a list at the top": b'[["Tom", ["the cat who chases Jerry"]]]',
                  "nested too deeply to read": b"[" * 100000,
                  "a riddle that is a number": b'{"Tom": [5]}'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            for what, content in broken.items():
                path.write_bytes(content)
                with self.assertRaisesRegex(ValueError, r"^mine\.json: ", msg=what):
                    wording.load_riddles(path)

    def test_a_file_that_is_not_a_table_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            for content in ('[["Tom", ["the cat who chases Jerry"]]]', "null", '"the cat who chases Jerry"', "42"):
                path.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(
                        ValueError, r"^mine\.json: a riddle table is a JSON object of names, each with a list of riddles$"):
                    wording.load_riddles(path)

    def test_an_empty_path_is_not_the_shipped_table(self):
        with self.assertRaises(OSError):
            wording.load_riddles("")

    def test_the_riddle_table_is_read_as_utf8_whatever_the_machine_prefers(self):
        # -X warn_default_encoding makes Python complain when a file is opened without
        # naming its encoding, and -W error turns the complaint into a failure.
        check = subprocess.run(
            [sys.executable, "-X", "warn_default_encoding", "-W", "error::EncodingWarning",
             "-c", "from wrong_person import wording; print(len(wording.load_riddles()))"],
            env={**os.environ, "PYTHONPATH": SRC}, capture_output=True, text=True, timeout=60)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(check.stdout.strip(), str(len(wording.load_riddles())))

    def test_a_broken_riddle_file_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            path.write_text('{"Tom": ["the cat who chases Jerry."], "Sue": []}', encoding="utf-8")
            with self.assertRaises(ValueError) as broken:
                wording.load_riddles(path)
            self.assertEqual(str(broken.exception),
                             "mine.json: Tom: 'the cat who chases Jerry.' should have no outer spaces "
                             "or full stop; Sue needs a list with at least one riddle")
            path.write_text("this is not JSON", encoding="utf-8")
            with self.assertRaises(ValueError):
                wording.load_riddles(path)
            with self.assertRaises(FileNotFoundError):
                wording.load_riddles(Path(folder, "missing.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
