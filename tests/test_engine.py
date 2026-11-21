"""Run from the repository root:  PYTHONPATH=src python3 -m unittest discover -s tests -v"""
import json
import os
import random
import subprocess
import sys
import tempfile
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
        self.assertNotIn("Linda", self.cells("next_to", "Amber"))
        self.assertNotIn("Linda", self.cells("near", "Amber"))

    def test_bad_boards_are_refused(self):
        with self.assertRaisesRegex(ValueError, r"^shape \(1, 2, 2, 3\) needs 12 names, got 11$"):
            e.Board(NAMES[:-1], SHAPE)
        with self.assertRaisesRegex(ValueError, "^names on a board must be unique$"):
            e.Board(NAMES[:-1] + ["michael"], SHAPE)          # duplicate, any case

    def test_a_name_that_is_not_all_letters_is_refused(self):
        with self.assertRaisesRegex(ValueError, "^names must be letters only$"):
            e.Board(NAMES[:-1] + ["R2D2"], SHAPE)

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

    def test_an_unknown_match_is_refused_by_matches_too(self):
        with self.assertRaisesRegex(ValueError, "^rhymes$"):
            e.matches("rhymes", "A", "AMBER")


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

    def test_same_inputs_same_answer(self):
        for board, _ in self.boards():
            rules = [e.Rule("page", "contains", "Z"), e.Rule("near", "ends", "A", False)]
            again = e.Board(list(board.names), board.shape)
            self.assertEqual(e.survivors(rules, board), e.survivors(rules, again))


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

    def test_audit_catches_more_than_one_answer(self):
        report = e.audit(CASE[:-1], self.b)
        self.assertFalse(report.sound)
        self.assertIsNone(report.killer)
        self.assertEqual(who(self.b, report.survivors), ["Michael", "Maxwell"])

    def test_audit_catches_no_answer(self):
        report = e.audit(CASE + [e.Rule("name", "is", "Maxwell", False)], self.b)
        self.assertEqual(report.survivors, ())
        self.assertFalse(report.sound)

    def test_a_case_survives_a_round_trip_through_json(self):
        board, rules = e.case_from_json(e.case_to_json(self.b, CASE))
        self.assertEqual(rules, CASE)
        self.assertEqual(e.audit(rules, board), e.audit(CASE, self.b))


class Wording(unittest.TestCase):
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

    def test_the_last_clue_is_the_note(self):
        self.assertEqual(wording.NOTE, "The police arrested the wrong person.")
        self.assertEqual(wording.sentence(CASE[4]), wording.NOTE)           # needs no riddle
        self.assertEqual(wording.sentence(CASE[4], RIDDLE), wording.NOTE)   # and never prints one

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

    def test_every_rule_in_the_space_has_a_sentence(self):
        board = e.Board(NAMES, SHAPE)
        seen = set()
        for rule in e.rule_space(board, ["A", "HELP"], ["Michael"]):
            if rule == e.Rule("name", "is", "Michael"):
                continue                          # refused: it would name the killer outright
            text = wording.sentence(rule, RIDDLE)
            self.assertTrue(text.endswith(".") and text[0].isupper())
            self.assertNotIn(text, seen)          # no two rules read the same
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
                         ["'Maximilian' must be one capitalised word of at most 9 letters"])

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

    def test_the_checker_catches_a_stray_space_and_a_full_stop(self):
        for line in (" the orphan with red hair", "the orphan with red hair ", "the orphan with red hair."):
            problems = wording.check_riddles({"Ann": [line]})
            self.assertEqual(len(problems), 1, line)
            self.assertIn("outer spaces or full stop", problems[0])

    def test_a_riddle_file_of_ones_own_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "mine.json")
            path.write_text('{"_note": "skipped", "Tom": ["the cat who chases Jerry"]}', encoding="utf-8")
            self.assertEqual(wording.load_riddles(path), {"Tom": ["the cat who chases Jerry"]})

    def test_the_riddle_table_is_read_as_utf8_whatever_the_machine_prefers(self):
        # -X warn_default_encoding makes Python complain when a file is opened without
        # naming its encoding, and -W error turns the complaint into a failure.
        check = subprocess.run(
            [sys.executable, "-X", "warn_default_encoding", "-W", "error::EncodingWarning",
             "-c", "from wrong_person import wording; print(len(wording.load_riddles()))"],
            env={**os.environ, "PYTHONPATH": str(Path(wording.__file__).parents[1])},
            capture_output=True, text=True)
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
