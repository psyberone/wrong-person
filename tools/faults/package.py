"""Planted faults in the package, its riddle table and the README's example.

Each entry is a label, the full name of the one test meant to catch the fault,
and the edits that plant it: (file, the text to replace, what replaces it).
`python3 tools/planted_faults.py` plants each one in a copy of the repository
and sees that its test fails. CONTRIBUTING.md says how to add one.

These were planted by hand during the reviews of the first work units, by the
AI reviewers and by the AI coding assistant that wrote the fixes. The tag in
square brackets is the name a fault had in the review it came from: G1 to G5
are the reviewers of the five gates (a `w` after the number marks the second
review, of the changes that fixed what the first had found), S with a number
is the review finding whose fix the fault was planted against, `own` marks a
fault the coding assistant planted against its own fix, and `mutmut` marks one
that `mutmut` made first. Where several tests fail for a fault, the test named
is the one that fails for the fewest faults. Where the name of another failing
test says what the fault breaks, that test was chosen by hand instead.

Three faults name their test for another reason (E035, E099, E100). What they
break depends on chance: the order Python walks a set in, or a hash, both of
which change from one run to the next. A test that compares one order with
another passes on some runs: 1 in 24 for E099. These three name the test that
takes the chance away by fixing the hash seed. E112 and E113 break the same two
orders with no chance in it, and each names the test that compares the order.
The fourth gate's reviewer proposed those two (`G4f`) in the review of the
script that plants these faults.

E114 to E135 came with the change that made `rule_space` check what it is given
(issue #3). The AI coding assistant planted them against its own change, one
or more for each thing the function now refuses or leaves out and for what it
gives back, and they carry the tag `u5` for the work unit. Three older faults
were written again for the same change. The words E017 replaces changed. The
words E021 replaces came to stand in two places. E020 put a bare `return`
before the loops, which made a generator yield nothing and would make the
function of today give back `None`; it gives back an empty space now.

E136 to E158 came from the review of that change, and carry the tag `u5r`.
Five AI reviewers planted faults of their own in the function, in two rounds.
E136 to E142, E145 to E147 and E151 are faults of theirs that no test caught,
and E144 is one that was caught only on some runs. Each names the test that
was added or made stronger for it. E143 and E152 are faults of theirs that
the tests caught as they stood, and that stood in no list. E148 to E150 are
the AI coding assistant's, for the one change the review brought to the
function itself: it copies each of its lists once, so that what it checked is
what it uses. E153 to E158 are the reviewers' again, from their second
reading. E153 to E156 passed the tests of the first fix, which gave the order
test two letter sets and two names (two things are always in one sorted order
or its reverse) and tried the copy with a list only. E157 and E158 change the
caller's own lists once they are copied: the tests caught them as they stood,
and they stood in no list.

E159 to E173 came with the change that holds the names in a riddle table to
plain letters A to Z, with a capital first and not all capitals, and refuses a
riddle holding a character that cannot go on a page (issue #5). They carry the
tag `u7` for the work unit. The AI coding assistant planted them against its
own change. E030 was written again for the same change: the words it replaces
changed.

E174 to E187 came from the review of that change, and carry the tag `u7r`.
E183 to E186 are faults the AI reviewers planted that no test caught. The rest
are the AI coding assistant's, for what the review changed: accents come off
with Unicode 3.2's tables and only as marks, the give-away check reads both
name and riddle in plain letters, a riddle may not hold what Unicode draws as
nothing, sentence() and arrest() refuse what a table refuses, and a name's
refusal says which character is not a letter A to Z. E038, E039, E040, E084
and E170 were written again: the words they replace changed.

E188 to E193 came from the re-check of that change, and carry the tag `u7r2`.
Each is a fault the AI reviewers planted that no test caught: a riddle looked
at with its ends trimmed, in sentence() and arrest(), in the look itself or in
the table check; only marks over a letter come off, or a mark through a letter
stays on; the six kinds are looked for before what Unicode draws as nothing.

E194 and E195 came from the second re-check, and carry the tag `u7r3`. Each
takes off only some kinds of mark: E194 leaves the horn on, and E195 a mark
below a letter as well.

E196 to E199 came from the fourth re-check, and carry the tag `u7r5`. E196 and
E197 are faults the AI reviewers planted that no test caught: an enclosing
mark comes off, or a spacing mark. E198 and E199 are the AI coding
assistant's, for what the re-check changed: a name's refusal names the
character as written, not what is left of it once the accents come off. E198
names what is left, as before, and E199 names an accent written apart from
its letter. E181 and E182 were written again: the line they change changed.

E200 to E203 came from the fifth re-check, and carry the tag `u7r6`. E200 to
E202 are faults the AI reviewers planted that no test caught: a name is looked
at with its ends trimmed, or its refusal looks past them, or joins each accent
to its letter before naming a character. E203 is the AI coding assistant's,
for what the re-check changed: "starting with a capital" is read from the name
as written, so a name may not start with an accent. E030 and E159 were written
again: the words they replace changed.

E204 to E209 came from the sixth re-check, and carry the tag `u7r7`. E204 and
E205 are the AI coding assistant's, for what the re-check changed: the refusal
of a name that starts with a mark gives the mark's code, since the mark draws
on the quote before the name. E204 leaves that out, as before, and E205 names
a later character first. E206 to E209 trim only line breaks, or only tabs,
from a name, before checking it or before naming a character; E206 and E208
are faults the AI reviewers planted that no test caught. E180 was written
again: the words it replaces changed. E200's label now says that only a space
or line break at a name's end passes, since the capital is read as written.

E210 to E219 came from the seventh re-check, and carry the tag `u7r8`. They are
the ten changes to the new ending that the AI reviewers and the AI coding
assistant found passing every test: its code in lower case; the mark found by
its combining class, Unicode 3.2's or this Python's, or by its category, or a
hidden character taken for one; the code read once accents are joined or
letters are split; white space looked past; and the ending given as well to a
mark that has this Python's class. The owner chose to keep the behaviour and
test its edges, so each is killed by a case added with them.

E220 to E227 came from the eighth re-check, and carry the tag `u7r9`. They are
eight more changes to where the new ending starts and stops that the AI
reviewers found passing every test: the mark found by Unicode 3.2's category,
alone or beside its class; a mark that comes off taken only when its category,
Unicode 3.2's or this Python's, is Mn; a mark taken when making it plain
changes it; a character Unicode says to draw as nothing taken for a mark; and a
byte order mark looked past. The owner chose one test that tries every
character first in a name, so each is killed by that test.

E228 to E232 came from the ninth re-check, and carry the tag `u7r10`. They are
five changes that tie the ending to the rest of the name, or to its riddles,
which the AI reviewers found passing every test: the ending only when the name
has at most 9 letters, is not all capitals, has no small letter first, has no
space after the mark, or has its riddles in a list. The owner chose wider cases:
after each mark that comes off whole, the test tries an example of each reason
the name rule gives, and riddles that are missing or not a list, so each is
killed by that test. E221's label no longer gives a count: it is eleven on
newer Pythons and ten on 3.10.

E233 to E247 came from the tenth re-check, and carry the tag `u7r11`. They are
fifteen more conditions on the same ending, which the AI reviewers found passing
every test: the ending kept only when the name holds no tab, line break or
character that cannot go on a page; when it is the first name in the table, no
earlier name was refused, or none is the same in plain letters; or when its
riddles are all text, are at most one, or have none of the problems the check
reports for a riddle. The owner chose to close them: after each mark the test
now also tries a tab and a hidden character in the name, and a table where a
refused twin comes first and the riddles hold each problem the check reports
for a riddle, so each is killed by that test.

E248 to E284 came with the change that lets a riddle in the table be written
as an object, with the places it counts in, whether it may name the victim,
its level, the names to keep off a board where it is used and a note on who it
means, and that reads each riddle as a record (issue #15). They carry the tag
`u9` for the work unit. The AI coding assistant planted them against its own
change, one or more for each thing the check now refuses, for what the reader
fills in and keeps off by itself, and for what counts for a place. E074 and
E077 were written again for the same change: the words they replace came to
stand in two places.
"""

E, W, R, J, T = ("src/wrong_person/engine.py", "src/wrong_person/wording.py", "README.md",
                 "src/wrong_person/riddles.json", "tests/test_readme.py")
RS = "test_engine.TheRuleSpace."
RR = "test_engine.RiddleRecords."

FAULTS = [
    # ---- behaviour that was right but unpinned
    ("E001 [G4-W1] own-name 'contains' pair swapped",
     "test_engine.Wording.test_every_letter_clue_reads_as_its_rule_means", [
        (W, '("contains", True): "The killer\'s name contains {v}."', '("contains", True): "The killer\'s name does not contain {v}."'),
        (W, '("contains", False): "The killer\'s name does not contain {v}."', '("contains", False): "The killer\'s name contains {v}."')]),
    ("E002 [G4-W2] own-name 'ends' pair swapped",
     "test_engine.Wording.test_every_letter_clue_reads_as_its_rule_means", [
        (W, '("ends", True): "The killer\'s name ends in {v}."', '("ends", True): "The killer\'s name does not end in {v}."'),
        (W, '("ends", False): "The killer\'s name does not end in {v}."', '("ends", False): "The killer\'s name ends in {v}."')]),
    ("E003 [G4-W4] 'contains' and 'ends' swapped",
     "test_engine.Wording.test_every_letter_clue_reads_as_its_rule_means", [
        (W, '("contains", True): "The killer\'s name contains {v}."', '("contains", True): "The killer\'s name ends in {v}."'),
        (W, '("ends", True): "The killer\'s name ends in {v}."', '("ends", True): "The killer\'s name contains {v}."')]),
    ("E004 [G4-W5] 'not ' dropped from the negative neighbour letter clue",
     "test_engine.Wording.test_every_letter_clue_reads_as_its_rule_means",
     [(W, "is not {BESIDE", "is {BESIDE")]),
    ("E005 [G4-W17] printed rules: any one -> all",
     "test_engine.Wording.test_the_printed_rules_in_full",
     [(W, "means any one of them", "means all of them")]),
    ("E006 [G4-W18] printed rules: diagonals excluded",
     "test_engine.Wording.test_the_printed_rules_in_full",
     [(W, "diagonals included", "diagonals excluded")]),
    ("E007 [G4-W14] a letter is not printed as a capital",
     "test_engine.Wording.test_a_letter_is_printed_as_a_capital",
     [(W, "    value = value.upper()\n    return value if", "    return value if")]),
    ("E008 [G4-M2] contains: any -> all",
     "test_engine.Semantics.test_a_letter_list_means_any_one_for_contains_too",
     [(E, "return any(c in name for c in value)", "return all(c in name for c in value)")]),
    ("E009 [G4-M3] contains: substring",
     "test_engine.Semantics.test_a_letter_list_means_any_one_for_contains_too",
     [(E, "return any(c in name for c in value)", "return value in name")]),
    ("E010 [G4-M1] is: equality -> substring",
     "test_engine.Semantics.test_is_means_the_whole_name",
     [(E, "return name == value", "return value in name")]),
    ("E011 [G4-N7] a board is one name short",
     "test_engine.Geometry.test_a_board_knows_how_many_names_it_holds",
     [(E, "return len(self.names)", "return len(self.names) - 1")]),
    ("E012 [G4-N8] the last suspect is never looked at",
     "test_engine.WholeCase.test_the_last_name_on_the_board_can_be_the_answer",
     [(E, "for i in range(len(board)) if all(holds", "for i in range(len(board) - 1) if all(holds")]),
    ("E013 [G4-N10] the first rule is never checked for waste",
     "test_engine.WholeCase.test_audit_catches_a_wasted_first_clue",
     [(E, "for k in range(len(rules))", "for k in range(1, len(rules))")]),
    ("E014 [G4-G10] chapter scope covers the whole board",
     "test_engine.Geometry.test_chapters_are_separate", [
        (E, '                if c != c2:\n                    continue\n                scopes["chapter"][i].append(j)\n',
            '                scopes["chapter"][i].append(j)\n                if c != c2:\n                    continue\n')]),
    ("E015 [G4-G11] chapters are not separate",
     "test_engine.Geometry.test_chapters_are_separate",
     [(E, "                if c != c2:\n                    continue\n", "")]),
    ("E016 [G4-R1] rule_space drops the neighbour scopes",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, "    for scope in SCOPES:\n        for match in", "    for scope in CONTAINERS:\n        for match in")]),
    ("E017 [G4-R2] rule_space drops the negative letter rules",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary", [
        (E, "                for positive in (True, False):\n                    space.append(Rule(scope, match, value, positive))",
            "                for positive in (True,):\n                    space.append(Rule(scope, match, value, positive))")]),
    ("E018 [G4-R3] rule_space drops the rules about named people",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, "        for name in named:\n", "        for name in ():\n")]),
    ("E019 [G4-R4] rule_space drops 'ends'",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, 'for match in ("contains", "begins", "ends"):', 'for match in ("contains", "begins"):')]),
    ("E020 [G4-R5] rule_space gives back an empty space",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, "    for scope in SCOPES:\n        for match in", "    return ()\n    for scope in SCOPES:\n        for match in")]),
    ("E021 [G4-R6] rule_space uses only the first letter set",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, "            for value in letter_sets:", "            for value in list(letter_sets)[:1]:")]),
    ("E022 [G4-A6] killer raises when nobody is left",
     "test_engine.WholeCase.test_audit_catches_no_answer",
     [(E, "if len(self.survivors) == 1 else None", "if len(self.survivors) <= 1 else None")]),
    ("E023 [G4-N6] a name is found only in its own case",
     "test_engine.Geometry.test_a_name_is_found_whatever_its_case",
     [(E, "return self.upper.index(name.upper())", "return list(self.names).index(name)")]),
    ("E024 [G4-E10] a saved rule's field order changed on both sides",
     "test_engine.WholeCase.test_a_saved_case_has_a_fixed_form", [
        (E, "return [self.scope, self.match, self.value, self.positive]", "return [self.match, self.scope, self.value, self.positive]"),
        (E, "return cls(*item)", "return cls(item[1], item[0], item[2], item[3])")]),
    ("E025 [G4-J1] a saved case's key renamed on both sides",
     "test_engine.WholeCase.test_a_saved_case_has_a_fixed_form",
     [(E, '"names": list(board.names)', '"people": list(board.names)'),
        (E, 'Board(data["names"], data["shape"])', 'Board(data["people"], data["shape"])'),
        (E, 'parts = ("shape", "names", "rules")', 'parts = ("shape", "people", "rules")')]),
    ("E026 [G2-M1] Rule is not frozen",
     "test_engine.Semantics.test_a_rule_cannot_be_changed_once_made",
     [(E, "@dataclass(frozen=True)\nclass Rule", "@dataclass\nclass Rule")]),
    ("E027 [G2-M5] Audit is not frozen",
     "test_engine.WholeCase.test_an_audit_cannot_be_changed_once_made",
     [(E, "@dataclass(frozen=True)\nclass Audit", "@dataclass\nclass Audit")]),
    ("E028 [G2-M3] scope tables are left as lists",
     "test_engine.Geometry.test_the_names_a_rule_looks_at_cannot_be_edited",
     [(E, "{scope: tuple(tuple(x) for x in lists) for scope, lists in scopes.items()}", "scopes")]),
    ("E029 [G2-M4] repeated-letter check is case-sensitive",
     "test_engine.Semantics.test_a_letter_may_not_repeat_in_another_case",
     [(E, "len(set(self.value.upper()))", "len(set(self.value))")]),
    ("E030 [G4-C1] a table name need not start with a capital",
     "test_engine.Wording.test_a_name_in_the_table_starts_with_a_capital",
     [(W, "and name[0].isupper() and not plain.isupper()):", "and not plain.isupper()):")]),
    ("E031 [G4-C3] a table value need not be a list",
     "test_engine.Wording.test_a_name_needs_a_list_even_for_one_riddle",
     [(W, "if not isinstance(lines, list) or not lines:", "if not lines:")]),
    ("E032 [G4-X13] README quotes a clue the code does not print",
     "test_readme.ReadmeExample.test_the_sentences_the_readme_quotes_are_the_ones_the_code_prints",
     [(R, 'not near the killer."', 'not near the murderer."')]),
    ("E033 [G4-X14] README quotes a note the code does not print",
     "test_readme.ReadmeExample.test_the_sentences_the_readme_quotes_are_the_ones_the_code_prints",
     [(R, 'wrong person." The person', 'wrong man." The person')]),
    ("E034 [G4-T2] the README test tolerates a missing output block",
     "test_readme.ReadmeExample.test_an_example_without_its_output_is_noticed",
     [(T, "if len(code) != 1 or len(shown) != 1:", "if len(code) != 1:")]),
    ("E035 [own] rule_space walks a set (order changes from run to run)",
     "test_engine.Properties.test_same_inputs_same_answer_in_every_run",
     [(E, "    for scope in SCOPES:\n        for match in", "    for scope in set(SCOPES):\n        for match in")]),
    ("E036 [own] near crosses pages",
     "test_engine.Geometry.test_neighbours_never_cross_a_page",
     [(E, "                if p != p2:\n                    continue\n                scopes[\"page\"][i].append(j)\n                if i != j and abs(ln - ln2) <= 1 and abs(col - col2) <= 1:\n                    scopes[\"near\"][i].append(j)\n",
                                        "                if i != j and abs(ln - ln2) <= 1 and abs(col - col2) <= 1:\n                    scopes[\"near\"][i].append(j)\n                if p != p2:\n                    continue\n                scopes[\"page\"][i].append(j)\n")]),
    ("E037 [G2-M2] a board does not copy its names",
     "test_engine.Geometry.test_a_board_keeps_its_own_copy_of_the_names",
     [(E, "names, shape = tuple(names), _sizes(shape)", "shape = _sizes(shape)")]),
    # ---- wording and the riddle file
    ("E038 [G4-C4] the name check is case-sensitive",
     "test_engine.Wording.test_a_riddle_gives_the_name_away_in_any_case", [
        (W, 'return _plain(name).lower() in re.findall(r"[^\\W\\d_]+", _plain(riddle).lower())',
            'return _plain(name) in re.findall(r"[^\\W\\d_]+", _plain(riddle))')]),
    ("E039 [G1-F2] the name check splits on spaces and the straight apostrophe only",
     "test_engine.Wording.test_a_riddle_gives_the_name_away_whatever_touches_it", [
        (W, 'return _plain(name).lower() in re.findall(r"[^\\W\\d_]+", _plain(riddle).lower())',
            'return _plain(name).lower() in _plain(riddle).lower().replace("\'", " ").split()')]),
    ("E040 [own] the name check looks inside longer words",
     "test_engine.Wording.test_a_name_inside_a_longer_word_gives_nothing_away", [
        (W, 'return _plain(name).lower() in re.findall(r"[^\\W\\d_]+", _plain(riddle).lower())',
            'return _plain(name).lower() in _plain(riddle).lower()')]),
    ("E041 [G2-F7] sentence prints a riddle that holds the name",
     "test_engine.Wording.test_a_riddle_that_holds_the_name_is_refused", [
        (W, '        if _gives_away(rule.value, who):\n            raise ValueError(f"the riddle {who!r} gives the name away")\n', '')]),
    ("E042 [G3-M7] a riddle that is not text is printed",
     "test_engine.Wording.test_a_riddle_that_is_not_text_is_refused", [
        (W, '    if riddle is not None and not isinstance(riddle, str):\n        raise ValueError(f"a riddle is one piece of text, got {riddle!r}")\n    if not riddle or not riddle.strip():',
            '    if not riddle or not str(riddle).strip():')]),
    ("E043 [G3-7] an empty riddle passes the checker",
     "test_engine.Wording.test_an_empty_riddle_is_reported",
     [(W, "if not isinstance(line, str) or not line.strip():", "if not isinstance(line, str):")]),
    ("E044 [G3-6] a riddle that is not text reaches the other checks",
     "test_engine.Wording.test_a_riddle_that_is_not_text_is_reported_and_the_check_goes_on",
     [(W, "if not isinstance(line, str) or not line.strip():", "if isinstance(line, str) and not line.strip():")]),
    ("E045 [G4-C13] the same riddle twice under one name is not told apart",
     "test_engine.Wording.test_the_same_riddle_twice_under_one_name_is_reported",
     [(W, "if seen.get(key) == name:", "if False:")]),
    ("E046 [G3-2] a name listed twice in a file is not reported",
     "test_engine.Wording.test_a_name_listed_twice_in_a_file_is_refused", [
        (W, 'problems = [f"{name} is listed twice" for name in twice] + check_riddles(table)', 'problems = check_riddles(table)')]),
    ("E047 [G5-M5] text that is not JSON is refused without the file name",
     "test_engine.Wording.test_every_refusal_of_a_file_starts_with_its_name", [
        (W, '        raise ValueError(f"{path.name}: {error}") from error', '        raise')]),
    ("E048 [G3-6] a file that is not an object is not refused by name",
     "test_engine.Wording.test_a_file_that_is_not_a_table_is_refused", [
        (W, '    if not isinstance(data, dict):\n        raise ValueError(f"{path.name}: a riddle table is a JSON object of names, each with a list of riddles")\n', '')]),
    ("E049 [G3-11] an empty path means the shipped table",
     "test_engine.Wording.test_an_empty_path_is_not_the_shipped_table",
     [(W, "if path is None else Path(path)", "if not path else Path(path)")]),
    ("E050 [G3-D1] riddles.json: a second Jack entry",
     "test_engine.Wording.test_the_riddle_table_is_clean", [
        (J, ' "Charles": ["the author of A Christmas Carol"]\n', ' "Charles": ["the author of A Christmas Carol"],\n "Jack": ["the boy who climbed the beanstalk"]\n')]),
    ("E051 [G3-D2] riddles.json: an empty riddle",
     "test_engine.Wording.test_the_riddle_table_is_clean", [
        (J, ' "Charles": ["the author of A Christmas Carol"]\n', ' "Charles": ["the author of A Christmas Carol"],\n "Zed": [""]\n')]),
    ("E052 [G4-X5] riddles.json: a riddle that opens with its own name and a comma",
     "test_engine.Wording.test_the_riddle_table_is_clean", [
        (J, ' "Charles": ["the author of A Christmas Carol"]\n', ' "Charles": ["the author of A Christmas Carol"],\n "Kevin": ["Kevin, the boy left Home Alone"]\n')]),
    # ---- the engine
    ("E053 [G3-1] survivors does not copy its rules",
     "test_engine.WholeCase.test_rules_may_arrive_one_at_a_time", [
        (E, "    rules = list(rules)             # a generator would be used up on the first suspect\n", "")]),
    ("E054 [G3-M1] audit does not copy its rules",
     "test_engine.WholeCase.test_rules_may_arrive_one_at_a_time",
     [(E, "    rules = list(rules)\n    alive", "    alive")]),
    ("E055 [G3-M2] decoys does not copy its rules",
     "test_engine.WholeCase.test_rules_may_arrive_one_at_a_time",
     [(E, "survivors(list(rules)[:-1], board)", "survivors(rules[:-1], board)")]),
    ("E056 [G3-4] the shape is not checked",
     "test_engine.Geometry.test_a_shape_is_four_positive_whole_numbers", [
        (E, '    if len(sizes) != 4 or not all(type(size) is int and size > 0 for size in sizes):\n'
            '        raise ValueError("shape must be four positive whole numbers "\n'
            '                         f"(chapters, pages, lines, names per line), got {sizes or shape!r}")\n', '')]),
    ("E057 [own] a size may be negative",
     "test_engine.Geometry.test_a_shape_is_four_positive_whole_numbers",
     [(E, "size > 0 for size in sizes", "size != 0 for size in sizes")]),
    ("E058 [own] the number of sizes is not checked",
     "test_engine.Geometry.test_a_shape_is_four_positive_whole_numbers",
     [(E, "if len(sizes) != 4 or not all(", "if not all(")]),
    ("E059 [own] a size need not be a whole number",
     "test_engine.Geometry.test_a_shape_is_four_positive_whole_numbers",
     [(E, "type(size) is int and size > 0", "size > 0")]),
    ("E060 [G3-6] a name that is not text is not refused as such",
     "test_engine.Geometry.test_a_name_that_is_not_text_is_refused", [
        (E, "isinstance(name, str) and name.isalpha() for name in names", "name.isalpha() for name in names")]),
    ("E061 [G2-F6] a board's upper-case names are a list",
     "test_engine.Geometry.test_a_boards_names_cannot_be_edited_in_place", [
        (E, "self.upper = tuple(name.upper() for name in names)", "self.upper = [name.upper() for name in names]")]),
    ("E062 [G2-F6] a board's positions are a list",
     "test_engine.Geometry.test_a_boards_names_cannot_be_edited_in_place",
     [(E, "self.where = tuple((c, p, ln, col)", "self.where = list((c, p, ln, col)")]),
    ("E063 [G3-5] positive is not checked",
     "test_engine.Semantics.test_a_rule_is_for_or_against_and_nothing_else", [
        (E, '        if not isinstance(self.positive, bool):\n'
            '            raise ValueError(f"positive must be True or False, got {self.positive!r}")\n', '')]),
    ("E064 [G3-6] a value that is not text is not refused as such",
     "test_engine.Semantics.test_a_value_that_is_not_text_is_refused", [
        (E, "if not isinstance(self.value, str) or not self.value.isalpha():", "if not self.value or not self.value.isalpha():")]),
    ("E065 [G3-5] a saved rule may have three parts",
     "test_engine.WholeCase.test_a_saved_rule_has_four_parts", [
        (E, "if not isinstance(item, (list, tuple)) or len(item) != 4:", "if not isinstance(item, (list, tuple)) or len(item) > 4:")]),
    ("E066 [own] a saved rule may be any sequence",
     "test_engine.WholeCase.test_a_saved_rule_has_four_parts", [
        (E, "if not isinstance(item, (list, tuple)) or len(item) != 4:", "if len(item) != 4:")]),
    ("E067 [G1-F3] a saved rule is built without its checks",
     "test_engine.WholeCase.test_a_broken_saved_case_is_refused", [
        (E, "        return cls(*item)\n",
            "        rule = object.__new__(cls)\n"
            "        for field, value in zip((\"scope\", \"match\", \"value\", \"positive\"), item):\n"
            "            object.__setattr__(rule, field, value)\n"
            "        return rule\n")]),
    ("E068 [G3-M4] a saved case's keys are not checked",
     "test_engine.WholeCase.test_a_broken_saved_case_is_refused", [
        (E, '    if not isinstance(data, dict) or not all(part in data for part in parts):\n'
            '        raise ValueError("a saved case is a JSON object with shape, names and rules")\n', '')]),
    ("E069 [G3-6] a saved case's parts need not be lists",
     "test_engine.WholeCase.test_a_broken_saved_case_is_refused", [
        (E, '    if not all(isinstance(data[part], list) for part in parts):\n'
            '        raise ValueError("the shape, names and rules of a saved case must each be a list")\n', '')]),
    ("E070 [G3-6] text that is not JSON is refused without saying what it should be",
     "test_engine.WholeCase.test_a_saved_case_in_bytes_that_are_not_text_is_refused_as_not_json", [
        (E, '        raise ValueError(f"a saved case must be JSON: {error}") from error', '        raise')]),
    ("E071 [own] a saved case may not carry other keys",
     "test_engine.WholeCase.test_a_saved_case_may_carry_other_keys",
     [(E, "not all(part in data for part in parts)", "set(data) != set(parts)")]),
    ("E072 [G5-M5] matches refuses with the bare word",
     "test_engine.Semantics.test_an_unknown_match_is_refused_by_matches_too",
     [(E, 'raise ValueError(f"unknown match {match!r}")', "raise ValueError(match)")]),
    # ---- found by the second review, on the fixes' own lines
    ("E073 [G2w-N1a] a name-holding riddle is refused on positive clues only",
     "test_engine.Wording.test_a_riddle_that_holds_the_name_is_refused", [
        (W, "        if _gives_away(rule.value, who):", "        if yes and _gives_away(rule.value, who):")]),
    ("E074 [G2w-N1b] the name check knows only a to z",
     "test_engine.Wording.test_a_name_inside_a_longer_word_gives_nothing_away",
     [(W, 'r"[^\\W\\d_]+", _plain(riddle)', 'r"[a-z]+", _plain(riddle)')]),
    ("E075 [G2w-N1c] positive is not checked on an 'is' rule",
     "test_engine.Semantics.test_a_rule_is_for_or_against_and_nothing_else", [
        (E, "        if not isinstance(self.positive, bool):", '        if self.match != "is" and not isinstance(self.positive, bool):')]),
    ("E076 [G2w-N1d] audit copies its rules after they are used up",
     "test_engine.WholeCase.test_rules_may_arrive_one_at_a_time", [
        (E, "    rules = list(rules)\n    alive = survivors(rules, board)", "    alive = survivors(rules, board)\n    rules = list(rules)")]),
    ("E077 [G2w-N1e] the name check counts digits and underscores as letters",
     "test_engine.Wording.test_a_riddle_gives_the_name_away_whatever_touches_it",
     [(W, 'r"[^\\W\\d_]+", _plain(riddle)', 'r"\\w+", _plain(riddle)')]),
    ("E078 [G3w-N17] a saved case is checked for its rules key only",
     "test_engine.WholeCase.test_a_broken_saved_case_is_refused", [
        (E, "not all(part in data for part in parts)", 'not all(part in data for part in ("rules",))')]),
    ("E079 [G3w-N18] a saved case is not checked for its shape key",
     "test_engine.WholeCase.test_a_broken_saved_case_is_refused", [
        (E, "not all(part in data for part in parts)", 'not all(part in data for part in ("names", "rules"))')]),
    ("E080 [G3w-N19] a saved case is not checked for its names key",
     "test_engine.WholeCase.test_a_broken_saved_case_is_refused", [
        (E, "not all(part in data for part in parts)", 'not all(part in data for part in ("shape", "rules"))')]),
    ("E081 [G3w-N20] only the first two sizes of a shape are checked",
     "test_engine.Geometry.test_a_shape_is_four_positive_whole_numbers", [
        (E, "size > 0 for size in sizes)", "size > 0 for size in sizes[:2])")]),
    ("E082 [G3w-N29] a value that is not text is refused on letter rules only",
     "test_engine.Semantics.test_a_value_that_is_not_text_is_refused", [
        (E, "if not isinstance(self.value, str) or not self.value.isalpha():",
            'if (self.match != "is" and not isinstance(self.value, str)) or not self.value.isalpha():')]),
    ("E083 [G4w-K6] the note refuses a riddle that holds the name",
     "test_engine.Wording.test_the_last_clue_is_the_note", [
        (W, "            return NOTE\n",
            "            if riddle is not None and _gives_away(rule.value, riddle):\n"
            "                raise ValueError('the riddle gives the name away')\n"
            "            return NOTE\n")]),
    ("E084 [G4w-K27] a word's final s is not counted",
     "test_engine.Wording.test_a_name_inside_a_longer_word_gives_nothing_away", [
        (W, 'return _plain(name).lower() in re.findall(r"[^\\W\\d_]+", _plain(riddle).lower())',
            'return _plain(name).lower() in [word.rstrip("s") for word in re.findall(r"[^\\W\\d_]+", _plain(riddle).lower())]')]),
    ("E085 [G4w-K30] a name is checked for truth, not for text",
     "test_engine.Geometry.test_a_name_that_is_not_text_is_refused", [
        (E, "isinstance(name, str) and name.isalpha() for name in names", "name and name.isalpha() for name in names")]),
    ("E086 [G4w-K39] bytes count as a name",
     "test_engine.Geometry.test_a_name_that_is_not_text_is_refused", [
        (E, "isinstance(name, str) and name.isalpha() for name in names", "isinstance(name, (str, bytes)) and name.isalpha() for name in names")]),
    ("E087 [G4w-K42] bytes count as a rule's value",
     "test_engine.Semantics.test_a_value_that_is_not_text_is_refused", [
        (E, "if not isinstance(self.value, str) or not self.value.isalpha():", "if not isinstance(self.value, (str, bytes)) or not self.value.isalpha():")]),
    ("E088 [G4w-K43] a saved rule must be a list, never a tuple",
     "test_engine.WholeCase.test_a_saved_rule_may_be_a_list_or_a_tuple", [
        (E, "if not isinstance(item, (list, tuple)) or len(item) != 4:", "if not isinstance(item, list) or len(item) != 4:")]),
    ("E089 [G4w-K16] a name listed twice with the same riddles is let through",
     "test_engine.Wording.test_a_name_listed_twice_is_reported_once_whatever_else_is_true", [
        (W, "twice = [name for name in dict.fromkeys(names) if names.count(name) > 1]",
            "twice = [name for name in dict.fromkeys(names) if len({repr(lines) for other, lines in outermost if other == name}) > 1]")]),
    ("E090 [G4w-K18] 'listed twice' is dropped when the file has another fault",
     "test_engine.Wording.test_a_name_listed_twice_is_reported_once_whatever_else_is_true", [
        (W, 'problems = [f"{name} is listed twice" for name in twice] + check_riddles(table)',
            'problems = check_riddles(table) or [f"{name} is listed twice" for name in twice]')]),
    # K23 as the reviewer planted it (a repeated note key let through) is what the code now does,
    # by the owner's ruling on S10. Its opposite must die instead.
    ("E091 [S10] a note key listed twice is refused",
     "test_engine.Wording.test_notes_may_repeat_and_what_they_hold_is_not_read", [
        (W, 'names = [name for name, _ in outermost if not name.startswith("_")]', "names = [name for name, _ in outermost]")]),
    ("E092 [S10] a repeated key inside a note is reported as a name",
     "test_engine.Wording.test_notes_may_repeat_and_what_they_hold_is_not_read",
     [(W, "outermost[:] = pairs ", "outermost.extend(pairs) ")]),
    ("E093 [S10] a name listed three times is reported twice",
     "test_engine.Wording.test_a_name_listed_twice_is_reported_once_whatever_else_is_true", [
        (W, "twice = [name for name in dict.fromkeys(names) if names.count(name) > 1]", "twice = [name for at, name in enumerate(names) if name in names[:at]]")]),
    ("E094 [G2w] only the first name listed twice is reported",
     "test_engine.Wording.test_a_name_listed_twice_is_reported_once_whatever_else_is_true", [
        (W, 'problems = [f"{name} is listed twice" for name in twice] + check_riddles(table)',
            'problems = [f"{name} is listed twice" for name in twice[:1]] + check_riddles(table)')]),
    ("E095 [G2w] names listed twice are reported in alphabetical order, not file order",
     "test_engine.Wording.test_a_name_listed_twice_is_reported_once_whatever_else_is_true", [
        (W, "twice = [name for name in dict.fromkeys(names) if names.count(name) > 1]",
            "twice = [name for name in sorted(set(names)) if names.count(name) > 1]")]),
    ("E096 [S14] a riddle file nested too deeply escapes as a RecursionError",
     "test_engine.Wording.test_every_refusal_of_a_file_starts_with_its_name", [
        (W, "except (ValueError, RecursionError) as error:     # not UTF-8", "except ValueError as error:     # not UTF-8")]),
    ("E097 [G4w-K15] the riddle file is read as ASCII",
     "test_engine.Wording.test_a_riddle_file_may_hold_letters_outside_ascii",
     [(W, 'path.read_text(encoding="utf-8")', 'path.read_text(encoding="ascii")')]),
    ("E098 [G4w-K25] the riddle file is read as utf-8-sig",
     "test_engine.Wording.test_every_refusal_of_a_file_starts_with_its_name",
     [(W, 'path.read_text(encoding="utf-8")', 'path.read_text(encoding="utf-8-sig")')]),
    # The next two depend on chance, like E035, and name the same test as it does (see the top of this file).
    ("E099 [G4w-K60] named people are walked as a set",
     "test_engine.Properties.test_same_inputs_same_answer_in_every_run",
     [(E, "        for name in named:\n", "        for name in set(named):\n")]),
    ("E100 [G4w-K68] decoys come back in the hash order of their names",
     "test_engine.Properties.test_same_inputs_same_answer_in_every_run", [
        (E, "    return [i for i in survivors(list(rules)[:-1], board) if i != killer]",
            "    found = [i for i in survivors(list(rules)[:-1], board) if i != killer]\n"
            "    return sorted(found, key=lambda i: hash(board.names[i]))")]),
    ("E112 [G4f-D1] named people are walked in the order of the alphabet",
     "test_engine.Semantics.test_named_people_come_in_the_order_given",
     [(E, "        for name in named:\n", "        for name in sorted(named):\n")]),
    ("E113 [G4f-D2] decoys come back last first",
     "test_engine.WholeCase.test_decoys_come_back_in_board_order", [
        (E, "    return [i for i in survivors(list(rules)[:-1], board) if i != killer]",
            "    return [i for i in survivors(list(rules)[:-1], board) if i != killer][::-1]")]),
    # K38 as the reviewer planted it (True refused as a size) is what the code now does, by the
    # owner's ruling on S13; its opposite is below. K57 (a saved case that is not text at all
    # becomes a ValueError) and K58 are accepted under S18 and are not planted.
    ("E101 [G4w-K71] a second output block in the README is not noticed",
     "test_readme.ReadmeExample.test_a_second_output_block_is_noticed", [
        (T, "if len(code) != 1 or len(shown) != 1:", "if len(code) != 1 or len(shown) < 1:")]),
    ("E102 [G3w-N6] only a JSON syntax error gets the saved-case message",
     "test_engine.WholeCase.test_a_saved_case_in_bytes_that_are_not_text_is_refused_as_not_json", [
        (E, "    except (ValueError, RecursionError) as error:\n        raise ValueError(f\"a saved case must be JSON",
            "    except (json.JSONDecodeError, RecursionError) as error:\n        raise ValueError(f\"a saved case must be JSON")]),
    # ---- the engine, the second round
    ("E103 [S11] a key written twice in a saved case is let through",
     "test_engine.WholeCase.test_a_saved_case_holds_each_key_once",
     [(E, "    if repeated:  ", "    if repeated and False:  ")]),
    ("E104 [mutmut] with two keys written twice the message names the second",
     "test_engine.WholeCase.test_a_saved_case_holds_each_key_once", [
        (E, "got {repeated[0]!r} twice", "got {repeated[1]!r} twice")]),
    ("E105 [S11] only the three needed keys are checked for repeats",
     "test_engine.WholeCase.test_a_saved_case_holds_each_key_once", [
        (E, "keys = [key for key, _ in outermost]", "keys = [key for key, _ in outermost if key in parts]")]),
    ("E106 [S11] a repeated key inside what another key holds is refused",
     "test_engine.WholeCase.test_a_key_may_repeat_inside_what_another_key_holds",
     [(E, "outermost[:] = pairs ", "outermost.extend(pairs) ")]),
    ("E107 [S12] a scope's table of rows is a list, so a suspect's whole row can be swapped",
     "test_engine.Geometry.test_the_names_a_rule_looks_at_cannot_be_edited", [
        (E, "{scope: tuple(tuple(x) for x in lists) for scope, lists in scopes.items()}",
            "{scope: [tuple(x) for x in lists] for scope, lists in scopes.items()}")]),
    ("E108 [S13] True counts as a size",
     "test_engine.Geometry.test_a_shape_is_four_positive_whole_numbers",
     [(E, "type(size) is int and size > 0", "isinstance(size, int) and size > 0")]),
    ("E109 [S13] a shape that cannot be walked raises TypeError",
     "test_engine.Geometry.test_a_shape_that_is_not_a_list_at_all_gets_the_same_refusal", [
        (E, "    except TypeError:                   # a bare number", "    except ZeroDivisionError:                   # a bare number")]),
    ("E110 [S13] the refusal of an unwalkable shape does not show what came",
     "test_engine.Geometry.test_a_shape_that_is_not_a_list_at_all_gets_the_same_refusal",
     [(E, "got {sizes or shape!r}", "got {sizes!r}")]),
    ("E111 [S14] a saved case nested too deeply escapes as a RecursionError",
     "test_engine.WholeCase.test_a_broken_saved_case_is_refused", [
        (E, "    except (ValueError, RecursionError) as error:\n        raise ValueError(f\"a saved case must be JSON",
            "    except ValueError as error:\n        raise ValueError(f\"a saved case must be JSON")]),
    # ---- rule_space checks what it is given (issue #3)
    ("E114 [u5] a named person who is not on the board is let through",
     RS + "test_a_named_person_must_be_on_the_board",
     [(E, "        if name.upper() not in board.upper:\n", "        if False:\n")]),
    ("E115 [u5] a named person is looked for in the case given",
     RS + "test_a_named_person_is_found_whatever_the_case_and_kept_as_given",
     [(E, "        if name.upper() not in board.upper:\n", "        if name not in board.names:\n")]),
    ("E116 [u5] rule_space names the killer outright again",
     RS + "test_the_killer_is_never_named_outright",
     [(E, '                if (scope, positive) != ("name", True):\n', "                if True:\n")]),
    ("E117 [u5] the rule of the last clue is left out with the one that names the killer",
     RS + "test_the_killer_is_never_named_outright",
     [(E, '                if (scope, positive) != ("name", True):\n', '                if scope != "name":\n')]),
    ("E118 [u5] one piece of text is walked letter by letter as letter sets",
     RS + "test_one_piece_of_text_is_not_a_list",
     [(E, "        if not isinstance(given, (list, tuple)):\n",
          '        if not isinstance(given, (list, tuple)) and (what, type(given)) != ("letter sets", str):\n')]),
    ("E119 [u5] one piece of text is walked letter by letter as named people",
     RS + "test_one_piece_of_text_is_not_a_list",
     [(E, "        if not isinstance(given, (list, tuple)):\n",
          '        if not isinstance(given, (list, tuple)) and (what, type(given)) != ("named people", str):\n')]),
    ("E120 [u5] bytes are taken where a list is meant",
     RS + "test_one_piece_of_text_is_not_a_list",
     [(E, "        if not isinstance(given, (list, tuple)):\n", "        if not isinstance(given, (list, tuple, bytes)):\n")]),
    ("E121 [u5] anything that can be walked is taken, text aside: a set, a generator",
     RS + "test_only_a_list_or_a_tuple_is_taken",
     [(E, "        if not isinstance(given, (list, tuple)):\n",
          '        if isinstance(given, (str, bytes)) or not hasattr(given, "__iter__"):\n')]),
    ("E122 [u5] a tuple is refused where a list is taken",
     RS + "test_a_tuple_is_taken_as_a_list_is",
     [(E, "        if not isinstance(given, (list, tuple)):\n", "        if not isinstance(given, list):\n")]),
    ("E123 [u5] the space can be walked only once",
     RS + "test_the_space_is_a_tuple",
     [(E, "    return tuple(space)\n", "    return iter(space)\n")]),
    ("E124 [u5] a name is checked before the letter sets",
     RS + "test_the_first_thing_wrong_is_the_one_named",
     [(E, '        Rule("name", "contains", value)         # made only to be checked: Rule refuses what is no letter set\n',
          "        pass\n")]),
    ("E125 [u5] a name that is no name gets Python's complaint and not the engine's",
     RS + "test_what_is_wrong_is_refused_at_the_call",
     [(E, '        Rule("name", "is", name)                # likewise, for what is no name\n', "")]),
    ("E126 [u5] the named people are looked at before the letter sets are seen to be a list",
     RS + "test_the_first_thing_wrong_is_the_one_named",
     [(E, '(("letter sets", letter_sets), ("named people", named))', '(("named people", named), ("letter sets", letter_sets))')]),
    ("E127 [u5] what is given twice comes out once",
     RS + "test_what_is_given_twice_comes_out_twice",
     [(E, "    return tuple(space)\n", "    return tuple(dict.fromkeys(space))\n")]),
    ("E128 [u5] a letter set that repeats a letter is found only after the names",
     RS + "test_the_first_thing_wrong_is_the_one_named",
     [(E, '        Rule("name", "contains", value)         # made only', '        Rule("name", "is", value)         # made only')]),
    ("E129 [u5] only the first letter set is checked before the names",
     RS + "test_the_first_thing_wrong_is_the_one_named",
     [(E, "    for value in letter_sets:\n        Rule(", "    for value in letter_sets[:1]:\n        Rule(")]),
    ("E130 [u5] the scopes come in another order",
     RS + "test_the_rules_come_in_one_order",
     [(E, "    for scope in SCOPES:\n        for match in", "    for scope in SCOPES[::-1]:\n        for match in")]),
    ("E131 [u5] a letter rule comes against before for",
     RS + "test_the_rules_come_in_one_order", [
        (E, "                for positive in (True, False):\n                    space.append(Rule(scope, match, value, positive))",
            "                for positive in (False, True):\n                    space.append(Rule(scope, match, value, positive))")]),
    ("E132 [u5] the rules come letter set by letter set, not match by match",
     RS + "test_the_rules_come_in_one_order", [
        (E, '        for match in ("contains", "begins", "ends"):\n            for value in letter_sets:\n',
            '        for value in letter_sets:\n            for match in ("contains", "begins", "ends"):\n')]),
    ("E133 [u5] a rule about a named person comes against before for",
     RS + "test_the_rules_come_in_one_order", [
        (E, "            for positive in (True, False):\n                if (scope, positive)",
            "            for positive in (False, True):\n                if (scope, positive)")]),
    ("E134 [u5] the space comes back as a list, which can be edited",
     RS + "test_the_space_is_a_tuple",
     [(E, "    return tuple(space)\n", "    return space\n")]),
    ("E135 [u5] nothing given gives nothing back at all",
     RS + "test_nothing_given_is_an_empty_space",
     [(E, "    space = []\n", "    space = []\n    if not letter_sets and not named:\n        return None\n")]),
    ("E136 [u5r] part of a name on the board passes for a name on it",
     RS + "test_part_of_a_name_on_the_board_is_not_on_it_and_nor_is_more_than_one",
     [(E, "        if name.upper() not in board.upper:\n",
          "        if not any(name.upper() in known for known in board.upper):\n")]),
    ("E137 [u5r] the beginning of a name on the board passes for a name on it",
     RS + "test_part_of_a_name_on_the_board_is_not_on_it_and_nor_is_more_than_one",
     [(E, "        if name.upper() not in board.upper:\n",
          "        if not any(known.startswith(name.upper()) for known in board.upper):\n")]),
    ("E138 [u5r] a name that holds a name on the board passes for a name on it",
     RS + "test_part_of_a_name_on_the_board_is_not_on_it_and_nor_is_more_than_one",
     [(E, "        if name.upper() not in board.upper:\n",
          "        if not any(known in name.upper() for known in board.upper):\n")]),
    ("E139 [u5r] a named person is looked for as if the board wrote every name Like This",
     RS + "test_a_named_person_is_found_however_the_board_writes_its_names",
     [(E, "        if name.upper() not in board.upper:\n", "        if name.title() not in board.names:\n")]),
    ("E140 [u5r] any sequence is taken, text aside: a deque, a range",
     RS + "test_only_a_list_or_a_tuple_is_taken",
     [(E, "        if not isinstance(given, (list, tuple)):\n",
          '        if isinstance(given, (str, bytes)) or not isinstance(given, __import__("collections.abc").abc.Sequence):\n')]),
    ("E141 [u5r] the letter sets are checked last first",
     RS + "test_the_first_thing_wrong_is_the_one_named",
     [(E, "    for value in letter_sets:\n        Rule(", "    for value in reversed(letter_sets):\n        Rule(")]),
    ("E142 [u5r] the letter sets are checked as a set, in no order",
     RS + "test_the_first_thing_wrong_is_the_one_named",
     [(E, "    for value in letter_sets:\n        Rule(", "    for value in set(letter_sets):\n        Rule(")]),
    ("E143 [u5r] the named people are checked last first",
     RS + "test_the_first_thing_wrong_is_the_one_named",
     [(E, "    for name in named:\n        Rule(", "    for name in reversed(named):\n        Rule(")]),
    ("E144 [u5r] the named people are checked as a set, in no order",
     RS + "test_the_first_thing_wrong_is_the_one_named",
     [(E, "    for name in named:\n        Rule(", "    for name in set(named):\n        Rule(")]),
    ("E145 [u5r] a kind of list or of tuple is refused: a named tuple",
     RS + "test_a_kind_of_list_or_of_tuple_is_taken_too",
     [(E, "        if not isinstance(given, (list, tuple)):\n", "        if type(given) not in (list, tuple):\n")]),
    ("E146 [u5r] the letter sets come out in the order of the alphabet, not the order given",
     RS + "test_the_rules_come_in_one_order",
     [(E, "            for value in letter_sets:\n", "            for value in sorted(letter_sets):\n")]),
    ("E147 [u5r] the caller's own list of letter sets is put in the order of the alphabet",
     RS + "test_the_rules_come_in_one_order",
     [(E, "    letter_sets, named = tuple(letter_sets), tuple(named)",
          "    if isinstance(letter_sets, list):\n        letter_sets.sort()\n    letter_sets, named = tuple(letter_sets), tuple(named)")]),
    ("E148 [u5r] the lists are read again when the rules are made",
     RS + "test_each_list_is_copied_once_so_what_was_checked_is_what_is_used",
     [(E, "    letter_sets, named = tuple(letter_sets), tuple(named)      # copied once: what is checked is what is used\n", "")]),
    ("E149 [u5r] the letter sets are read again when the rules are made",
     RS + "test_each_list_is_copied_once_so_what_was_checked_is_what_is_used",
     [(E, "    letter_sets, named = tuple(letter_sets), tuple(named)", "    letter_sets, named = letter_sets, tuple(named)")]),
    ("E150 [u5r] the named people are read again when the rules are made",
     RS + "test_each_list_is_copied_once_so_what_was_checked_is_what_is_used",
     [(E, "    letter_sets, named = tuple(letter_sets), tuple(named)", "    letter_sets, named = tuple(letter_sets), named")]),
    ("E151 [u5r] a letter set comes out in capitals, not written as given",
     RS + "test_a_letter_set_is_kept_as_given",
     [(E, "                    space.append(Rule(scope, match, value, positive))",
          "                    space.append(Rule(scope, match, value.upper(), positive))")]),
    ("E152 [u5r] nothing is checked until the space is walked: a generator again",
     RS + "test_what_is_wrong_is_refused_at_the_call",
     [(E, "    return tuple(space)\n", "    yield from space\n")]),
    ("E153 [u5r] only a list is copied: a tuple of any kind is used as it is",
     RS + "test_each_list_is_copied_once_so_what_was_checked_is_what_is_used",
     [(E, "    letter_sets, named = tuple(letter_sets), tuple(named)",
          "    letter_sets, named = (tuple(given) if isinstance(given, list) else given for given in (letter_sets, named))")]),
    ("E154 [u5r] the letter sets come out in the order of the alphabet backwards",
     RS + "test_the_rules_come_in_one_order",
     [(E, "            for value in letter_sets:\n", "            for value in sorted(letter_sets, reverse=True):\n")]),
    ("E155 [u5r] the named people come out in the order of the alphabet backwards",
     RS + "test_the_rules_come_in_one_order",
     [(E, "        for name in named:\n", "        for name in sorted(named, key=str.upper, reverse=True):\n")]),
    ("E156 [u5r] the letter sets are put in the order of the alphabet backwards before the rules are made",
     RS + "test_the_rules_come_in_one_order",
     [(E, "    space = []\n", "    letter_sets = sorted(letter_sets, reverse=True)\n    space = []\n")]),
    ("E157 [u5r] the caller's own list of letter sets is turned round once it is copied",
     RS + "test_the_rules_come_in_one_order",
     [(E, "    letter_sets, named = tuple(letter_sets), tuple(named)      # copied once: what is checked is what is used\n",
          "    theirs, letter_sets, named = letter_sets, tuple(letter_sets), tuple(named)\n"
          "    if isinstance(theirs, list):\n        theirs.reverse()\n")]),
    ("E158 [u5r] the caller's own list of names is emptied once it is copied",
     RS + "test_the_rules_come_in_one_order",
     [(E, "    letter_sets, named = tuple(letter_sets), tuple(named)      # copied once: what is checked is what is used\n",
          "    theirs, letter_sets, named = named, tuple(letter_sets), tuple(named)\n"
          "    if isinstance(theirs, list):\n        theirs.clear()\n")]),
    # ---- what a riddle table may hold (issue #5)
    ("E159 [u7] a name in all capitals passes",
     "test_engine.Wording.test_a_name_in_all_capitals_is_refused",
     [(W, "name[0].isupper() and not plain.isupper()):", "name[0].isupper()):")]),
    ("E160 [u7] a name is checked with its accents still on",
     "test_engine.Wording.test_a_name_is_counted_in_its_plain_letters",
     [(W, "        plain = _plain(name)\n", "        plain = name\n")]),
    ("E161 [u7] a name may be written in any letters, not only A to Z",
     "test_engine.Wording.test_a_name_with_letters_that_have_no_plain_form_is_refused",
     [(W, "if not (plain.isascii() and plain.isalpha()", "if not (plain.isalpha()")]),
    ("E162 [u7] two names that are one in plain letters both pass",
     "test_engine.Wording.test_two_names_that_are_one_in_plain_letters_are_refused", [
        (W, "        if plain.lower() in plain_names:\n"
            "            problems.append(f\"{name!r} and {plain_names[plain.lower()]!r} are one name in plain letters\")\n",
            "")]),
    ("E163 [u7] a riddle may hold a character that cannot go on a page",
     "test_engine.Wording.test_a_riddle_with_a_character_that_cannot_go_on_a_page_is_refused", [
        (W, "            if hidden is not None:\n"
            "                problems.append(f\"{name}: {line!r} holds U+{ord(hidden):04X}, \"\n"
            "                                \"a character that cannot go on a page\")\n",
            "")]),
    ("E164 [u7] a riddle may hold a control character",
     "test_engine.Wording.test_a_riddle_with_a_character_that_cannot_go_on_a_page_is_refused",
     [(W, 'frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})', 'frozenset({"Cf", "Cs", "Co", "Zl", "Zp"})')]),
    ("E165 [u7] a riddle may hold a format character, such as a zero-width space",
     "test_engine.Wording.test_a_riddle_with_a_character_that_cannot_go_on_a_page_is_refused",
     [(W, 'frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})', 'frozenset({"Cc", "Cs", "Co", "Zl", "Zp"})')]),
    ("E166 [u7] a riddle may hold half of a surrogate pair",
     "test_engine.Wording.test_a_riddle_with_a_character_that_cannot_go_on_a_page_is_refused",
     [(W, 'frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})', 'frozenset({"Cc", "Cf", "Co", "Zl", "Zp"})')]),
    ("E167 [u7] a riddle may hold a private-use character",
     "test_engine.Wording.test_a_riddle_with_a_character_that_cannot_go_on_a_page_is_refused",
     [(W, 'frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})', 'frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})')]),
    ("E168 [u7] a riddle may hold a line separator",
     "test_engine.Wording.test_a_riddle_with_a_character_that_cannot_go_on_a_page_is_refused",
     [(W, 'frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})', 'frozenset({"Cc", "Cf", "Cs", "Co", "Zp"})')]),
    ("E169 [u7] a riddle may hold a paragraph separator",
     "test_engine.Wording.test_a_riddle_with_a_character_that_cannot_go_on_a_page_is_refused",
     [(W, 'frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})', 'frozenset({"Cc", "Cf", "Cs", "Co", "Zl"})')]),
    ("E170 [u7] the refusal names the last such character, not the first",
     "test_engine.Wording.test_only_the_first_such_character_is_named",
     [(W, "for char in text if unicodedata", "for char in reversed(text) if unicodedata")]),
    ("E171 [u7] riddles.json: the table's note no longer states the name rule",
     "test_engine.Wording.test_the_riddle_table_states_the_name_rule_the_checker_holds",
     [(J, "one word of at most 9 letters, A to Z with or without accents, starting with a capital and not all capitals.",
          "one capitalised word, 9 letters or fewer.")]),
    ("E172 [u7] a name's length is counted as written, accent marks included",
     "test_engine.Wording.test_a_name_is_counted_in_its_plain_letters",
     [(W, "and len(plain) <= 9", "and len(name) <= 9")]),
    ("E173 [u7] two names that differ only in their capitals are two names",
     "test_engine.Wording.test_two_names_that_are_one_in_plain_letters_are_refused", [
        (W, "if plain.lower() in plain_names:", "if plain in plain_names:"),
        (W, "plain_names[plain.lower()]!r}", "plain_names[plain]!r}"),
        (W, "plain_names.setdefault(plain.lower(), name)", "plain_names.setdefault(plain, name)")]),
    # ---- from the review of that change
    ("E174 [u7r] accents are taken off with this Python's tables, not Unicode 3.2's",
     "test_engine.Wording.test_accents_come_off_by_tables_every_python_holds_alike",
     [(W, "if not unicodedata.ucd_3_2_0.combining(char))", "if not unicodedata.combining(char))")]),
    ("E175 [u7r] a name in another form of letters, such as full width, passes as plain letters",
     "test_engine.Wording.test_a_name_in_other_forms_of_letters_is_refused",
     [(W, 'unicodedata.ucd_3_2_0.normalize("NFD", text)', 'unicodedata.ucd_3_2_0.normalize("NFKD", text)')]),
    ("E176 [u7r] the give-away check reads the name with its accents on",
     "test_engine.Wording.test_the_name_is_found_in_its_riddle_in_plain_letters",
     [(W, "return _plain(name).lower() in", "return name.lower() in")]),
    ("E177 [u7r] the give-away check reads the riddle with its accents on",
     "test_engine.Wording.test_the_name_is_found_in_its_riddle_in_plain_letters",
     [(W, ", _plain(riddle).lower())", ", riddle.lower())")]),
    ("E178 [u7r] a riddle may hold what Unicode draws as nothing, if it is not a format character",
     "test_engine.Wording.test_every_character_unicode_draws_as_nothing_is_refused_in_a_riddle",
     [(W, " in _UNPRINTED\n                 or any(low <= ord(char) <= high for low, high in _IGNORABLE)), None)",
          " in _UNPRINTED), None)")]),
    ("E179 [u7r] sentence() and arrest() print a riddle holding a character that cannot go on a page",
     "test_engine.Wording.test_a_riddle_that_cannot_go_on_a_page_is_refused_wherever_it_is_printed", [
        (W, "    hidden = _unprinted(riddle)\n    if hidden is not None:\n"
            "        raise ValueError(f\"the riddle {riddle!r} holds U+{ord(hidden):04X}, a character that cannot go on a page\")\n",
            "")]),
    ("E180 [u7r] the refusal of a name does not say which character is not a letter A to Z",
     "test_engine.Wording.test_the_refusal_names_the_first_character_that_is_not_a_letter_a_to_z",
     [(W, 'why = "" if odd is None else f": {odd!r} (U+{ord(odd):04X}) is not a letter A to Z"', 'why = ""')]),
    ("E181 [u7r] the refusal of a name names its last character that is not a letter A to Z",
     "test_engine.Wording.test_a_name_with_letters_that_have_no_plain_form_is_refused",
     [(W, "for char in name\n", "for char in reversed(name)\n")]),
    ("E182 [u7r] the refusal of a name looks for that character with the accents still on",
     "test_engine.Wording.test_a_name_is_counted_in_its_plain_letters",
     [(W, "for part in _plain(char))), None)", "for part in char)), None)")]),
    ("E183 [u7r] a name that breaks the rule is not checked against the names before it",
     "test_engine.Wording.test_a_name_that_breaks_the_rule_is_still_checked_against_the_others",
     [(W, "        if plain.lower() in plain_names:", "        elif plain.lower() in plain_names:")]),
    ("E184 [u7r] a name without a list of riddles is not remembered as a name",
     "test_engine.Wording.test_a_name_without_a_list_of_riddles_still_counts_as_a_name", [
        (W, "        plain_names.setdefault(plain.lower(), name)\n"
            "        if not isinstance(lines, list) or not lines:\n"
            "            problems.append(f\"{name} needs a list with at least one riddle\")\n"
            "            continue\n",
            "        if not isinstance(lines, list) or not lines:\n"
            "            problems.append(f\"{name} needs a list with at least one riddle\")\n"
            "            continue\n"
            "        plain_names.setdefault(plain.lower(), name)\n")]),
    ("E185 [u7r] the refusal of a riddle names the lowest such character, not the first",
     "test_engine.Wording.test_only_the_first_such_character_is_named", [
        (W, "return next((char for char in text if", "return min((char for char in text if"),
        (W, "_IGNORABLE)), None)", "_IGNORABLE)), default=None)")]),
    ("E186 [u7r] accents are taken off by dropping every mark, a grapheme joiner and a variation selector too",
     "test_engine.Wording.test_a_name_with_a_hidden_character_is_refused",
     [(W, "if not unicodedata.ucd_3_2_0.combining(char))", 'if unicodedata.ucd_3_2_0.category(char) != "Mn")')]),
    ("E187 [u7r] a riddle may hold a variation selector from U+E0100 on, or a code point kept for more of them",
     "test_engine.Wording.test_every_character_unicode_draws_as_nothing_is_refused_in_a_riddle",
     [(W, ", (0xE0000, 0xE0FFF))", ")")]),
    # ---- from the re-check of that change
    ("E188 [u7r2] sentence() and arrest() look for a hidden character in the riddle with its ends trimmed",
     "test_engine.Wording.test_a_riddle_that_cannot_go_on_a_page_is_refused_wherever_it_is_printed",
     [(W, "hidden = _unprinted(riddle)", "hidden = _unprinted(riddle.strip())")]),
    ("E189 [u7r2] the look for a hidden character trims the text first",
     "test_engine.Wording.test_a_riddle_that_cannot_go_on_a_page_is_refused_wherever_it_is_printed",
     [(W, "for char in text if unicodedata", "for char in text.strip() if unicodedata")]),
    ("E190 [u7r2] the table check looks for a hidden character in the riddle with its ends trimmed",
     "test_engine.Wording.test_a_hidden_character_at_either_end_of_a_riddle_is_named_too",
     [(W, "hidden = _unprinted(line)", "hidden = _unprinted(line.strip())")]),
    ("E191 [u7r2] only marks drawn over a letter come off, not under or through it",
     "test_engine.Wording.test_a_name_is_counted_in_its_plain_letters",
     [(W, "if not unicodedata.ucd_3_2_0.combining(char))", "if unicodedata.ucd_3_2_0.combining(char) != 230)")]),
    ("E192 [u7r2] a mark drawn through a letter stays on",
     "test_engine.Wording.test_a_name_is_counted_in_its_plain_letters",
     [(W, "if not unicodedata.ucd_3_2_0.combining(char))", "if unicodedata.ucd_3_2_0.combining(char) in (0, 1))")]),
    ("E193 [u7r2] the refusal of a riddle names the first of the six kinds before what Unicode draws as nothing",
     "test_engine.Wording.test_only_the_first_such_character_is_named",
     [(W, " in _UNPRINTED\n                 or any(low <= ord(char) <= high for low, high in _IGNORABLE)), None)",
          " in _UNPRINTED), None) or next(\n                 (char for char in text if any(low <= ord(char) <= high for low, high in _IGNORABLE)), None)")]),
    # ---- from the second re-check
    ("E194 [u7r3] only marks over, under or through a letter come off: the horn stays on",
     "test_engine.Wording.test_a_name_is_counted_in_its_plain_letters",
     [(W, "if not unicodedata.ucd_3_2_0.combining(char))", "if unicodedata.ucd_3_2_0.combining(char) not in (1, 202, 220, 230))")]),
    ("E195 [u7r3] a mark below a letter stays on, such as a comma, and the horn too",
     "test_engine.Wording.test_a_name_is_counted_in_its_plain_letters",
     [(W, "if not unicodedata.ucd_3_2_0.combining(char))", "if unicodedata.ucd_3_2_0.combining(char) not in (1, 202, 230))")]),
    # ---- from the fourth re-check
    ("E196 [u7r5] an enclosing mark comes off, such as a circle drawn round a letter",
     "test_engine.Wording.test_a_name_with_an_enclosing_or_spacing_mark_is_refused",
     [(W, "if not unicodedata.ucd_3_2_0.combining(char))",
       "if not unicodedata.ucd_3_2_0.combining(char) and unicodedata.ucd_3_2_0.category(char) != 'Me')")]),
    ("E197 [u7r5] a spacing mark comes off, such as a vowel sign beside its letter",
     "test_engine.Wording.test_a_name_with_an_enclosing_or_spacing_mark_is_refused",
     [(W, "if not unicodedata.ucd_3_2_0.combining(char))",
       "if not unicodedata.ucd_3_2_0.combining(char) and unicodedata.ucd_3_2_0.category(char) != 'Mc')")]),
    ("E198 [u7r5] the refusal of a name names what is left once the accents come off, not what was written",
     "test_engine.Wording.test_the_refusal_of_a_name_names_the_character_as_written",
     [(W, "for char in name\n                        if not all(part.isascii() and part.isalpha() for part in _plain(char))), None)",
       "for char in plain if not (char.isascii() and char.isalpha())), None)")]),
    ("E199 [u7r5] the refusal of a name names an accent written apart from its letter",
     "test_engine.Wording.test_the_refusal_of_a_name_names_the_character_as_written",
     [(W, "if not all(part.isascii() and part.isalpha() for part in _plain(char))), None)",
       "if not (_plain(char).isascii() and _plain(char).isalpha())), None)")]),
    # ---- from the fifth re-check
    ("E200 [u7r6] a name is looked at with its ends trimmed, so a space or line break at its end passes",
     "test_engine.Wording.test_a_name_with_a_digit_a_sign_or_a_space_is_refused",
     [(W, "        plain = _plain(name)\n", "        plain = _plain(name.strip())\n")]),
    ("E201 [u7r6] the refusal of a name looks past a space or line break at either end, and names nothing",
     "test_engine.Wording.test_a_name_with_a_digit_a_sign_or_a_space_is_refused",
     [(W, "for char in name\n", "for char in name.strip()\n")]),
    ("E202 [u7r6] the refusal of a name joins each accent to its letter first, and names what was not written",
     "test_engine.Wording.test_the_refusal_of_a_name_names_the_character_as_written",
     [(W, "for char in name\n", 'for char in unicodedata.normalize("NFC", name)\n')]),
    ("E203 [u7r6] the capital is read from the plain form, so an accent before the first letter passes",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, "and name[0].isupper() and not plain.isupper()", "and plain[0].isupper() and not plain.isupper()")]),
    # ---- from the sixth re-check
    ("E204 [u7r7] the refusal of a name that starts with a mark does not give the mark's code",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, "if name and not _plain(name[0]):", "if False:")]),
    ("E205 [u7r7] the refusal of a name that starts with a mark names a later character first",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, "if name and not _plain(name[0]):", "if odd is None and name and not _plain(name[0]):")]),
    ("E206 [u7r7] a name is looked at with line breaks trimmed from its ends, so one at its end passes",
     "test_engine.Wording.test_a_name_with_a_digit_a_sign_or_a_space_is_refused",
     [(W, "        plain = _plain(name)\n", '        plain = _plain(name.strip("\\n"))\n')]),
    ("E207 [u7r7] a name is looked at with tabs trimmed from its ends, so one at its end passes",
     "test_engine.Wording.test_a_name_with_a_digit_a_sign_or_a_space_is_refused",
     [(W, "        plain = _plain(name)\n", '        plain = _plain(name.strip("\\t"))\n')]),
    ("E208 [u7r7] the refusal of a name looks past line breaks at its ends, and names nothing",
     "test_engine.Wording.test_a_name_with_a_digit_a_sign_or_a_space_is_refused",
     [(W, "for char in name\n", 'for char in name.strip("\\n")\n')]),
    ("E209 [u7r7] the refusal of a name looks past tabs at its ends, and names nothing",
     "test_engine.Wording.test_a_name_with_a_digit_a_sign_or_a_space_is_refused",
     [(W, "for char in name\n", 'for char in name.strip("\\t")\n')]),
    # ---- from the seventh re-check
    ("E210 [u7r8] the code of a leading mark is written in lower case",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'U+{ord(name[0]):04X}, before any letter', 'U+{ord(name[0]):04x}, before any letter')]),
    ("E211 [u7r8] a leading mark gets the ending by its Unicode 3.2 class, so three Tibetan signs name nothing",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'if name and not _plain(name[0]):', 'if name and unicodedata.ucd_3_2_0.combining(name[0]):')]),
    ("E212 [u7r8] a leading mark gets the ending by this Python's class, so it hangs on the Python",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'if name and not _plain(name[0]):', 'if name and unicodedata.combining(name[0]):')]),
    ("E213 [u7r8] every leading mark gets the ending, even one that stays on",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'if name and not _plain(name[0]):', 'if name and unicodedata.category(name[0]).startswith("M"):')]),
    ("E214 [u7r8] a hidden character first gets the ending, as if it were a mark",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'if name and not _plain(name[0]):', 'if name and (not _plain(name[0]) or _unprinted(name[0]) is not None):')]),
    ("E215 [u7r8] the code of a leading mark is read once accents are joined, and is not the one written",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'U+{ord(name[0]):04X}, before any letter', "U+{ord(unicodedata.normalize('NFC', name)[0]):04X}, before any letter")]),
    ("E216 [u7r8] the code of a leading mark is read once letters are split, and is not the one written",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'U+{ord(name[0]):04X}, before any letter', "U+{ord(unicodedata.normalize('NFD', name)[0]):04X}, before any letter")]),
    ("E217 [u7r8] a leading mark is looked for past white space, and the space gets the ending",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'if name and not _plain(name[0]):', 'if name.strip() and not _plain(name.strip()[0]):')]),
    ("E218 [u7r8] a leading mark is looked for past white space, and named instead of the space",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'if name and not _plain(name[0]):', 'if name.strip() and not _plain(name.strip()[0]):'),
      (W, 'U+{ord(name[0]):04X}, before any letter', 'U+{ord(name.strip()[0]):04X}, before any letter')]),
    ("E219 [u7r8] a leading mark with this Python's class gets the ending too, so it hangs on the Python",
     "test_engine.Wording.test_a_name_that_starts_with_an_accent_is_refused",
     [(W, 'if name and not _plain(name[0]):', 'if name and (not _plain(name[0]) or unicodedata.combining(name[0])):')]),
    # ---- from the eighth re-check
    ("E220 [u7r9] a leading mark gets the ending by Unicode 3.2's category Mn, so marks that stay on get it, and eight that come off do not",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and unicodedata.ucd_3_2_0.category(name[0]) == "Mn":')]),
    ("E221 [u7r9] only a leading mark that comes off and has this Python's category Mn gets the ending, so some name nothing",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and unicodedata.category(name[0]) == "Mn":')]),
    ("E222 [u7r9] a leading mark that changes when made plain gets the ending, so marks that split but stay on get it",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and unicodedata.category(name[0]).startswith("M") and _plain(name[0]) != name[0]:')]),
    ("E223 [u7r9] a leading mark gets the ending by Unicode 3.2's category Mn or Mc, so marks that stay on get it",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and unicodedata.ucd_3_2_0.category(name[0]) in ("Mn", "Mc"):')]),
    ("E224 [u7r9] a leading mark gets the ending by its Unicode 3.2 class or its category Mn, so marks that stay on get it",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and (unicodedata.ucd_3_2_0.combining(name[0]) or unicodedata.ucd_3_2_0.category(name[0]) == "Mn"):')]),
    ("E225 [u7r9] only a leading mark that comes off and has Unicode 3.2's category Mn gets the ending, so eight name nothing",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and unicodedata.ucd_3_2_0.category(name[0]) == "Mn":')]),
    ("E226 [u7r9] a character first that Unicode says to draw as nothing gets the ending, as if it were a mark",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and (not _plain(name[0]) or any(low <= ord(name[0]) <= high for low, high in _IGNORABLE)):')]),
    ("E227 [u7r9] a byte order mark first is looked past, and is called a mark when one follows it",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name.lstrip("\\ufeff") and not _plain(name.lstrip("\\ufeff")[0]):')]),
    # ---- from the ninth re-check
    ("E228 [u7r10] a leading mark gets the ending only when the name has at most 9 letters, so a longer one names nothing",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and len(plain) <= 9:')]),
    ("E229 [u7r10] a leading mark gets the ending only when the name is not all capitals, so TOM after it names nothing",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not plain.isupper():')]),
    ("E230 [u7r10] a leading mark gets the ending only when no small letter starts the name, so tom after it names nothing",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not plain[:1].islower():')]),
    ("E231 [u7r10] a leading mark gets the ending only when the riddles are a list, so a name without one names nothing",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and isinstance(lines, list):')]),
    ("E232 [u7r10] a leading mark gets the ending only when no space follows it, and the space is named instead",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and name[1:2] != " ":')]),
    # ---- from the tenth re-check
    ("E233 [u7r11] a leading mark gets the ending only when the name is printable, so a tab or hidden character after it takes it away",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and name.isprintable():')]),
    ("E234 [u7r11] a leading mark gets the ending only when no earlier name is the same in plain letters",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and plain.lower() not in plain_names:')]),
    ("E235 [u7r11] a leading mark gets the ending only when nothing earlier in the table was refused",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not problems:')]),
    ("E236 [u7r11] a leading mark gets the ending only when no riddle in its list is blank or not text",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not (isinstance(lines, list) and any(not isinstance(line, str) or not line.strip() for line in lines)):')]),
    ("E237 [u7r11] a leading mark loses the ending when a later character that cannot go on a page is named instead",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and (odd is None or _unprinted(odd) is None):')]),
    ("E238 [u7r11] a leading mark gets the ending only when nothing in the name cannot go on a page",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and _unprinted(name) is None:')]),
    ("E239 [u7r11] a leading mark gets the ending only when every riddle in its list is text",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not (isinstance(lines, list) and any(not isinstance(line, str) for line in lines)):')]),
    ("E240 [u7r11] a leading mark gets the ending only when its list holds at most one riddle",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not (isinstance(lines, list) and len(lines) > 1):')]),
    ("E241 [u7r11] a leading mark gets the ending only when no tab or line break is in the name",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not any(char in name for char in "\\t\\n\\r"):')]),
    ("E242 [u7r11] a leading mark gets the ending only when its name is the first in the table",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not plain_names:')]),
    ("E243 [u7r11] a leading mark loses the ending when a riddle has a space at either end or a full stop",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', "if name and not _plain(name[0]) and not (isinstance(lines, list) and any(isinstance(x, str) and (x != x.strip() or x.endswith('.')) for x in lines)):")]),
    ("E244 [u7r11] a leading mark loses the ending when a riddle is said twice under the name",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not (isinstance(lines, list) and len({str(x).lower() for x in lines}) < len(lines)):')]),
    ("E245 [u7r11] a leading mark loses the ending when a riddle gives the name away",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not (isinstance(lines, list) and any(isinstance(x, str) and _gives_away(name, x) for x in lines)):')]),
    ("E246 [u7r11] a leading mark loses the ending when a riddle holds a character that cannot go on a page",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', 'if name and not _plain(name[0]) and not (isinstance(lines, list) and any(isinstance(x, str) and _unprinted(x) is not None for x in lines)):')]),
    ("E247 [u7r11] a leading mark loses the ending when a riddle is under an earlier name too",
     "test_engine.Wording.test_only_a_mark_that_comes_off_whole_gets_the_ending",
     [(W, 'if name and not _plain(name[0]):', "if name and not _plain(name[0]) and not (isinstance(lines, list) and any(isinstance(x, str) and ' '.join(x.lower().split()) in seen for x in lines)):")]),
    # ---- work unit 9: a riddle written as an object, read as a record (#15)
    ("E248 [u9] a field not in the list is passed over, so a misspelt one counts as left out",
     RR + "test_an_object_without_a_riddle_or_with_a_stray_field_is_refused",
     [(W, 'problems = [f" has {field!r}, which is not a field of a riddle" for field in entry if field not in FIELDS]', 'problems = []')]),
    ("E249 [u9] a field's name is read in any case, so Victim passes as victim",
     RR + "test_an_object_without_a_riddle_or_with_a_stray_field_is_refused",
     [(W, 'for field in entry if field not in FIELDS]', 'for field in entry if str(field).lower() not in FIELDS]')]),
    ("E250 [u9] an object with no riddle is reported as None, not as having no riddle",
     RR + "test_an_object_without_a_riddle_or_with_a_stray_field_is_refused",
     [(W, 'if isinstance(entry, dict) and "riddle" not in entry:', 'if False:')]),
    ("E251 [u9] a problem with a field quotes the whole object even when its riddle can be quoted",
     RR + "test_an_object_without_a_riddle_or_with_a_stray_field_is_refused",
     [(W, 'quoted = repr(entry if line is None else line)', 'quoted = repr(entry)')]),
    ("E252 [u9] an empty list of places is taken",
     RR + "test_a_bad_places_is_refused",
     [(W, 'if not isinstance(places, list) or not places:', 'if not isinstance(places, list):')]),
    ("E253 [u9] places need not be a list, so a single code is read letter by letter",
     RR + "test_a_bad_places_is_refused",
     [(W, 'if not isinstance(places, list) or not places:', 'if not places:')]),
    ("E254 [u9] UK is reported as an unknown code, with no word to write GB",
     RR + "test_a_bad_places_is_refused",
     [(W, '    if code == "UK":\n        return "\'UK\' is not a code; write \'GB\'"\n', '')]),
    ("E255 [u9] a code listed twice in places is taken",
     RR + "test_a_bad_places_is_refused",
     [(W, 'elif code in places[:at]:', 'elif False:')]),
    ("E256 [u9] a victim mark of 1 or 0 is taken for true or false",
     RR + "test_a_victim_mark_is_true_or_false_only",
     [(W, 'type(entry["victim"]) is not bool', 'entry["victim"] not in (True, False)')]),
    ("E257 [u9] a level is read in any case and with its spaces trimmed",
     RR + "test_a_level_is_one_of_three_words",
     [(W, 'entry["level"] not in LEVELS', 'str(entry["level"]).strip().lower() not in LEVELS')]),
    ("E258 [u9] an empty list of names to keep off is taken",
     RR + "test_a_bad_keep_off_is_refused",
     [(W, 'if not isinstance(keep_off, list) or not keep_off:', 'if not isinstance(keep_off, list):')]),
    ("E259 [u9] the names to keep off need not be a list, so one name is read letter by letter",
     RR + "test_a_bad_keep_off_is_refused",
     [(W, 'if not isinstance(keep_off, list) or not keep_off:', 'if not keep_off:')]),
    ("E260 [u9] a name to keep off is not held to the name rule",
     RR + "test_a_bad_keep_off_is_refused",
     [(W, 'rule = broken(kept, plain)', 'rule = None')]),
    ("E261 [u9] the riddle's own name is taken among the names to keep off",
     RR + "test_a_bad_keep_off_is_refused",
     [(W, 'if plain.lower() == own:', 'if False:')]),
    ("E262 [u9] a name listed twice among the names to keep off is taken",
     RR + "test_a_bad_keep_off_is_refused",
     [(W, 'elif plain.lower() in held:', 'elif False:')]),
    ("E263 [u9] the names to keep off are compared with their capitals, so one listed twice can be missed",
     RR + "test_a_bad_keep_off_is_refused",
     [(W, 'held.append(plain.lower())', 'held.append(plain)')]),
    ("E264 [u9] a note on who the riddle means is not checked",
     RR + "test_who_is_text_or_left_out",
     [(W, 'if "who" in entry and not isinstance(entry["who"], str):', 'if False:')]),
    ("E265 [u9] an object's text is not given the checks a plain line gets",
     RR + "test_today_s_riddle_checks_apply_to_an_object_s_text",
     [(W, '            if line is None:\n                continue\n', '            if line is None or isinstance(entry, dict):\n                continue\n')]),
    ("E266 [u9] a plain line and an object with the same text are not counted as the same riddle",
     RR + "test_a_plain_line_and_an_object_with_the_same_text_are_listed_twice",
     [(W, 'key = " ".join(line.lower().split())', 'key = (" ".join(line.lower().split()), isinstance(entry, dict))')]),
    ("E267 [u9] a record can be changed",
     RR + "test_a_record_cannot_be_changed",
     [(W, '@dataclass(frozen=True)', '@dataclass')]),
    ("E268 [u9] a plain line may not name the victim",
     RR + "test_a_plain_line_is_a_riddle_with_every_default",
     [(W, 'victim: bool = True', 'victim: bool = False')]),
    ("E269 [u9] a plain line is medium, not easy",
     RR + "test_a_plain_line_is_a_riddle_with_every_default",
     [(W, 'level: str = "easy"', 'level: str = "medium"')]),
    ("E270 [u9] the codes in places come back sorted, not as written",
     RR + "test_an_object_is_read_with_every_mark",
     [(W, 'marks["places"] = tuple(entry["places"])', 'marks["places"] = tuple(sorted(entry["places"]))')]),
    ("E271 [u9] a word in small letters that is a table name keeps that name off",
     RR + "test_a_word_in_small_letters_keeps_no_one_off",
     [(W, 'if word[0].isupper() and word.lower() in names', 'if word.lower() in names')]),
    ("E272 [u9] the names written to keep off come after the printed ones",
     RR + "test_written_names_come_first_and_each_name_once",
     [(W, 'return Riddle(entry["riddle"], keep_off=tuple(keep_off), **marks)',
       'written = len(entry.get("keep_off", ()))\n    return Riddle(entry["riddle"], keep_off=tuple(keep_off[written:] + keep_off[:written]), **marks)')]),
    ("E273 [u9] a printed name that is already written is kept off twice",
     RR + "test_written_names_come_first_and_each_name_once",
     [(W, ' and word.lower() not in held:', ':')]),
    ("E274 [u9] printed names are looked for with their accents on, so a name with an accent is missed",
     RR + "test_a_printed_name_is_found_whatever_its_case_or_accents",
     [(W, 'for word in re.findall(r"[^\\W\\d_]+", _plain(entry["riddle"])):', 'for word in re.findall(r"[^\\W\\d_]+", entry["riddle"]):')]),
    ("E275 [u9] the riddle is split into words before its accents come off, so an accent written apart splits a name",
     RR + "test_a_printed_name_is_found_whatever_its_case_or_accents",
     [(W, 'for word in re.findall(r"[^\\W\\d_]+", _plain(entry["riddle"])):',
       'for word in [_plain(word) for word in re.findall(r"[^\\W\\d_]+", entry["riddle"])]:')]),
    ("E276 [u9] a printed name is kept off as the riddle writes it, not as the table spells it",
     RR + "test_a_printed_name_is_found_whatever_its_case_or_accents",
     [(W, 'keep_off.append(names[word.lower()])', 'keep_off.append(word)')]),
    ("E277 [u9] a printed name is kept off only for a riddle that has names written to keep off",
     RR + "test_the_shipped_table_keeps_off_the_eleven_printed_names",
     [(W, 'for word in re.findall(r"[^\\W\\d_]+", _plain(entry["riddle"])):',
       'for word in (re.findall(r"[^\\W\\d_]+", _plain(entry["riddle"])) if "keep_off" in entry else ()):')]),
    ("E278 [u9] a group counts when any one of its places counts, not every one",
     RR + "test_a_riddle_for_one_nation_does_not_count_for_the_union",
     [(W, 'return all(any(place == named', 'return any(any(place == named')]),
    ("E279 [u9] a riddle that names a group does not count for the places in it",
     RR + "test_a_riddle_counts_for_a_place_it_names_or_a_group_holding_it",
     [(W, 'place == named or place in GROUPS.get(named, ())', 'place == named')]),
    ("E280 [u9] a wrong code is taken when the riddle names no places",
     RR + "test_a_wrong_code_is_refused",
     [(W, '    _refuse_a_wrong(code)\n    if riddle.places is None:\n        return True\n',
       '    if riddle.places is None:\n        return True\n    _refuse_a_wrong(code)\n')]),
    ("E281 [u9] riddles_for refuses a wrong code only when it has a riddle to ask about",
     RR + "test_a_wrong_code_is_refused",
     [(W, '    _refuse_a_wrong(code)\n    kept = ', '    kept = ')]),
    ("E282 [u9] riddles_for keeps a name left with no riddle",
     RR + "test_only_the_riddles_for_a_place_are_kept",
     [(W, 'return {name: riddles for name, riddles in kept.items() if riddles}', 'return kept')]),
    ("E283 [u9] riddles_for takes the riddles that do not count out of the table it was given",
     RR + "test_only_the_riddles_for_a_place_are_kept",
     [(W, 'kept = {name: [riddle for riddle in riddles if counts_for(riddle, code)] for name, riddles in table.items()}',
       'kept = {name: riddles for name, riddles in table.items()\n            if not riddles.__setitem__(slice(None), [riddle for riddle in riddles if counts_for(riddle, code)])}')]),
    ("E284 [u9] the table's notes lose the line on the names kept off",
     RR + "test_the_riddle_table_describes_the_object_form",
     [(J, '  "keep_off: a list of first names that must not be on a board where the riddle is used. '
          'A name from this table that the riddle prints, starting with a capital, is kept off by itself; '
          'list only the names the table lacks.",\n', '')]),
]
