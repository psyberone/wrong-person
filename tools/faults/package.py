"""Planted faults in the package, its riddle table and the README's example.

Each entry is a label, the full name of the one test meant to catch the fault,
and the edits that plant it: (file, the text to replace, what replaces it).
`python3 tools/planted_faults.py` plants each one in a copy of the repository
and sees that its test fails. CONTRIBUTING.md says how to add one.

These were planted by hand during the reviews of the first work units, by the
AI reviewers and by the AI coding assistant that wrote the fixes. The tag in
square brackets is the name a fault had in the review it came from: G1 to G5
are the reviewers of the five gates, and `own` marks a fault the coding
assistant planted against its own fix. Where several tests fail for a fault,
the test named is the one whose name says what the fault breaks.
"""

E, W, R, J, T = ("src/wrong_person/engine.py", "src/wrong_person/wording.py", "README.md",
                 "src/wrong_person/riddles.json", "tests/test_readme.py")

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
        (E, "                for positive in (True, False):\n                    yield Rule(scope, match, value, positive)",
            "                for positive in (True,):\n                    yield Rule(scope, match, value, positive)")]),
    ("E018 [G4-R3] rule_space drops the rules about named people",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, "        for name in named:\n", "        for name in ():\n")]),
    ("E019 [G4-R4] rule_space drops 'ends'",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, 'for match in ("contains", "begins", "ends"):', 'for match in ("contains", "begins"):')]),
    ("E020 [G4-R5] rule_space yields nothing",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, "    for scope in SCOPES:\n        for match in", "    return\n    for scope in SCOPES:\n        for match in")]),
    ("E021 [G4-R6] rule_space uses only the first letter set",
     "test_engine.Semantics.test_the_rule_space_is_the_whole_vocabulary",
     [(E, "for value in letter_sets:", "for value in list(letter_sets)[:1]:")]),
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
     [(W, "name.isalpha() and name[0].isupper() and", "name.isalpha() and")]),
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
        (W, 'return name.lower() in re.findall(r"[^\\W\\d_]+", riddle.lower())', 'return name in re.findall(r"[^\\W\\d_]+", riddle)')]),
    ("E039 [G1-F2] the name check splits on spaces and the straight apostrophe only",
     "test_engine.Wording.test_a_riddle_gives_the_name_away_whatever_touches_it", [
        (W, 'return name.lower() in re.findall(r"[^\\W\\d_]+", riddle.lower())', 'return name.lower() in riddle.lower().replace("\'", " ").split()')]),
    ("E040 [own] the name check looks inside longer words",
     "test_engine.Wording.test_a_name_inside_a_longer_word_gives_nothing_away", [
        (W, 'return name.lower() in re.findall(r"[^\\W\\d_]+", riddle.lower())', 'return name.lower() in riddle.lower()')]),
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
     "test_engine.Wording.test_a_name_with_an_accent_is_guarded_like_any_other",
     [(W, 'r"[^\\W\\d_]+"', 'r"[a-z]+"')]),
    ("E075 [G2w-N1c] positive is not checked on an 'is' rule",
     "test_engine.Semantics.test_a_rule_is_for_or_against_and_nothing_else", [
        (E, "        if not isinstance(self.positive, bool):", '        if self.match != "is" and not isinstance(self.positive, bool):')]),
    ("E076 [G2w-N1d] audit copies its rules after they are used up",
     "test_engine.WholeCase.test_rules_may_arrive_one_at_a_time", [
        (E, "    rules = list(rules)\n    alive = survivors(rules, board)", "    alive = survivors(rules, board)\n    rules = list(rules)")]),
    ("E077 [G2w-N1e] the name check counts digits and underscores as letters",
     "test_engine.Wording.test_a_riddle_gives_the_name_away_whatever_touches_it",
     [(W, 'r"[^\\W\\d_]+"', 'r"\\w+"')]),
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
        (W, 'return name.lower() in re.findall(r"[^\\W\\d_]+", riddle.lower())',
            'return name.lower() in [word.rstrip("s") for word in re.findall(r"[^\\W\\d_]+", riddle.lower())]')]),
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
    ("E099 [G4w-K60] named people are walked as a set",
     "test_engine.Semantics.test_named_people_come_in_the_order_given",
     [(E, "        for name in named:\n", "        for name in set(named):\n")]),
    ("E100 [G4w-K68] decoys come back in the hash order of their names",
     "test_engine.WholeCase.test_decoys_come_back_in_board_order", [
        (E, "    return [i for i in survivors(list(rules)[:-1], board) if i != killer]",
            "    found = [i for i in survivors(list(rules)[:-1], board) if i != killer]\n"
            "    return sorted(found, key=lambda i: hash(board.names[i]))")]),
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
]
