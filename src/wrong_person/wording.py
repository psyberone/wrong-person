"""
wording.py - turns rules into sentences. The only place wording and riddles live.

The engine only ever sees Rule(..., "is", "Michael"). The caller hands that
person's riddle to sentence(), which prints "The singer of Thriller is ..." and
never the name. Change any sentence here and no logic moves.
"""
import json
import re
import unicodedata
from dataclasses import dataclass
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

# Where a riddle counts (#15), as ISO 3166 codes. A riddle may name places, groups or both.
# A group holds places only, never another group, and no place twice; a place may be in any
# number of groups. More places are added here as data.
PLACES = frozenset({"US", "GB-ENG", "GB-SCT", "GB-WLS", "GB-NIR"})
GROUPS = {"GB": ("GB-ENG", "GB-SCT", "GB-WLS", "GB-NIR"),     # the United Kingdom
          "GB-GBN": ("GB-ENG", "GB-SCT", "GB-WLS")}           # Great Britain
LEVELS = ("easy", "medium", "hard")
FIELDS = ("riddle", "places", "victim", "level", "keep_off", "who")     # what a riddle written as an object may hold
_NAME_RULE = ("must be one word of at most 9 letters, A to Z with or without accents, "
              "starting with a capital and not all capitals")


@dataclass(frozen=True)
class Riddle:
    """One riddle as load_riddles gives it, with every mark filled in.

    `text` is what is printed. `places` holds the codes the table gave, as written, or
    None when the riddle counts everywhere. `victim` says whether the riddle may name the
    victim. `level` is "easy", "medium" or "hard". `keep_off` holds the first names that
    must not be on a board where the riddle is used. `who` is a note for people on who
    the riddle means, or None. A record cannot be changed once made.
    """
    text: str
    places: tuple[str, ...] | None = None
    victim: bool = True
    level: str = "easy"
    keep_off: tuple[str, ...] = ()
    who: str | None = None


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
    two marks that have one. Any other mark with no class stays on, in whole or in part,
    so a name holding one is refused: the grapheme joiner, an enclosing circle, many
    vowel signs, and any mark newer than Unicode 3.2. A letter in another form, such as
    full width or circled, stays as it is; only a sign Unicode holds to be that very
    letter, such as the Kelvin sign for K, is read as the letter. Unicode 3.2's tables
    are used, which every Python holds alike, so the answer is the same on each."""
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
    """Read a riddle table -> {name: [Riddle, ...]}.

    With no `path` it reads the riddles.json shipped beside this file. Keys that
    start with "_" are notes for people: they are left out, whatever they hold
    and however often they come. A file that is not UTF-8 JSON, is nested too
    deeply to read or to check, is not an object, lists a name twice, writes a
    field twice in one riddle, or fails check_riddles is refused with a
    ValueError that starts with the file's name.

    Each riddle comes back as a record, a plain line as if it were an object with
    only its text. A field left out gets the record's default: every place, may be
    the victim, easy, no names written to keep off, and no note on who it means.
    The record's `keep_off` holds the names written for the riddle, as written, then
    each name from the table that the riddle prints, as the table spells it, in the
    order the riddle prints them, leaving out one already there in plain letters. A
    name is printed when one of the riddle's words, in plain letters, starts with a
    capital and is that name in any case: "Bart Simpson's father" and "BART's dad"
    print Bart, while "the jack of all trades" prints no Jack and "Kentucky" no Ken.
    A word is a run of letters, and a capital a letter of category Lu or Lt, both by
    Unicode 3.2's tables as _plain reads them, so a table gives the same records on
    every Python.
    """
    path = Path(__file__).with_name("riddles.json") if path is None else Path(path)
    outermost, repeats = [], {}

    def remember(pairs):
        outermost[:] = pairs        # an object ends after all it holds, so the last one seen is the file's own
        made = dict(pairs)
        if len(made) < len(pairs):  # a key written more than once: kept with the object, so its id stays its own
            keys = [key for key, _ in pairs]
            repeats[id(made)] = (made, [key for key in made if keys.count(key) > 1])
        return made

    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=remember)
    except (ValueError, RecursionError) as error:     # not UTF-8, not JSON, or nested too deeply
        raise ValueError(f"{path.name}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: a riddle table is a JSON object of names, each with a list of riddles")
    names = [name for name, _ in outermost if not name.startswith("_")]
    twice = [name for name in dict.fromkeys(names) if names.count(name) > 1]
    table = {name: lines for name, lines in data.items() if not name.startswith("_")}
    try:            # a value nested deeply enough overflows when a message quotes it
        problems = [f"{name} is listed twice" for name in twice] + check_riddles(table)
        for name, lines in table.items():       # a dict in memory has no repeats, so check_riddles cannot see them
            for entry in lines if isinstance(lines, list) else ():
                if id(entry) in repeats:        # each object in repeats is kept alive there, so no other has its id
                    line = entry.get("riddle")
                    quoted = repr(line if isinstance(line, str) and line.strip() else entry)
                    problems += [f"{name}: {quoted} has {field!r} more than once" for field in repeats[id(entry)][1]]
    except RecursionError as error:
        raise ValueError(f"{path.name}: the file is nested too deeply to check") from error
    if problems:
        raise ValueError(f"{path.name}: " + "; ".join(problems))
    names = {_plain(name).lower(): name for name in table}
    return {name: [_record(entry, names) for entry in lines] for name, lines in table.items()}


def _record(entry, names):
    """The record of one riddle as a table that check_riddles passed writes it: a plain
    line or an object. `names` maps each of the table's names, in plain letters and
    small letters, to the name as the table spells it."""
    entry = entry if isinstance(entry, dict) else {"riddle": entry}
    marks = {field: entry[field] for field in ("victim", "level", "who") if field in entry}
    if "places" in entry:
        marks["places"] = tuple(entry["places"])
    keep_off = list(entry.get("keep_off", ()))
    held = {_plain(name).lower() for name in keep_off}
    for word in _words(_plain(entry["riddle"])):
        if unicodedata.ucd_3_2_0.category(word[0]) in ("Lu", "Lt") and word.lower() in names and word.lower() not in held:
            keep_off.append(names[word.lower()])
            held.add(word.lower())
    return Riddle(entry["riddle"], keep_off=tuple(keep_off), **marks)


def _words(text):
    """The runs of letters in the text, a letter being a character whose category in
    Unicode 3.2's tables starts with L. A character that table does not hold, such as
    a letter added to Unicode since, ends a word, on every Python alike."""
    return "".join(char if unicodedata.ucd_3_2_0.category(char)[0] == "L" else " " for char in text).split()


def check_riddles(table):
    """What a machine can check in a riddle table -> a list of problems, empty when clean.

    The table is as the file holds it: each name has a list of riddles, and each riddle
    is a plain line or an object with the fields in FIELDS (a Riddle record is neither,
    so it is not a riddle here). An object's text is checked first, then any field it
    holds that is not in FIELDS, then its other fields in the order FIELDS gives, and
    then its text as a plain line's is.

    Whether a riddle is easy, and whether it points to one person only, is on the author.
    """
    problems, seen, plain_names = [], {}, {}

    def broken(name, plain):
        """What the name breaks of the name rule, as the words that follow it, or None.
        `plain` is the name with its accents taken off."""
        if not (plain.isascii() and plain.isalpha() and len(plain) <= 9
                and name[0].isupper() and not plain.isupper()):
            odd = next((char for char in name
                        if not all(part.isascii() and part.isalpha() for part in _plain(char))), None)
            why = "" if odd is None else f": {odd!r} (U+{ord(odd):04X}) is not a letter A to Z"
            if name and not _plain(name[0]):    # a mark first draws on the quote before the name: give its code
                why = f": it starts with an accent or other mark, U+{ord(name[0]):04X}, before any letter"
            return _NAME_RULE + why
        return None

    for name, lines in table.items():
        plain = _plain(name)
        rule = broken(name, plain)
        if rule is not None:
            problems.append(f"{name!r} {rule}")
        if plain.lower() in plain_names:
            problems.append(f"{name!r} and {plain_names[plain.lower()]!r} are one name in plain letters")
        plain_names.setdefault(plain.lower(), name)
        if not isinstance(lines, list) or not lines:
            problems.append(f"{name} needs a list with at least one riddle")
            continue
        for entry in lines:
            line = entry.get("riddle") if isinstance(entry, dict) else entry
            if isinstance(entry, dict) and "riddle" not in entry:
                problems.append(f"{name}: {entry!r} has no riddle")
                line = None
            elif not isinstance(line, str) or not line.strip():
                problems.append(f"{name}: {line!r} is not a riddle")
                line = None
            if isinstance(entry, dict):     # with no riddle to quote, the whole object is quoted
                quoted = repr(entry if line is None else line)
                problems += [f"{name}: {quoted}{problem}" for problem in _field_problems(entry, name, broken)]
            if line is None:
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


def counts_for(riddle, code):
    """Does the riddle count for this code? -> True or False.

    For a place: the riddle has no places, or names the place, or names a group the
    place is in. For a group: the riddle counts for every place in it, so a riddle for
    Scotland alone does not count for GB. A code that is not one of PLACES or GROUPS,
    UK among them, is refused with a ValueError. The riddle is taken as load_riddles
    made it, and not checked again.
    """
    _refuse_a_wrong(code)
    if riddle.places is None:
        return True
    return all(any(place == named or place in GROUPS.get(named, ()) for named in riddle.places)
               for place in GROUPS.get(code, (code,)))


def riddles_for(table, code):
    """Only the riddles that count for the code -> {name: [Riddle, ...]}.

    `table` is what load_riddles gave. A name left with no riddle is left out, and the
    table given is not changed. A wrong code is refused as counts_for refuses it, even
    when the table is empty.
    """
    _refuse_a_wrong(code)
    kept = {name: [riddle for riddle in riddles if counts_for(riddle, code)] for name, riddles in table.items()}
    return {name: riddles for name, riddles in kept.items() if riddles}


def _refuse_a_wrong(code):
    """A code that is not one of PLACES or GROUPS is refused with a ValueError that says why."""
    wrong = _code_problem(code)
    if wrong is not None:
        raise ValueError(wrong)


def _code_problem(code):
    """What is wrong with a code for a place or a group, or None when it is one of PLACES or GROUPS."""
    if code == "UK":
        return "'UK' is not a code; write 'GB'"
    if not isinstance(code, str) or (code not in PLACES and code not in GROUPS):
        return f"{code!r} is not a known place or group"
    return None


def _field_problems(entry, owner, broken):
    """What is wrong with the fields of a riddle written as an object, other than its text.

    Each problem is given as the words that follow the riddle in its message: a field not
    in FIELDS, in the object's own order, then each field in the order FIELDS gives.
    `owner` is the name the riddle is under. `broken(name, plain)` says what a name
    breaks of the name rule, or None.
    """
    problems = [f" has {field!r}, which is not a field of a riddle" for field in entry if field not in FIELDS]
    if "places" in entry:
        places = entry["places"]
        if not isinstance(places, list) or not places:
            problems.append(": places must be a list of codes; leave it out to count everywhere")
        else:
            for at, code in enumerate(places):
                wrong = _code_problem(code)
                if wrong is not None:
                    problems.append(f": {wrong}")
                elif code in places[:at]:
                    problems.append(f": {code!r} is listed twice in places")
    if "victim" in entry and type(entry["victim"]) is not bool:      # not 0 or 1, which JSON tells apart
        problems.append(f": victim must be true or false, got {entry['victim']!r}")
    if "level" in entry and entry["level"] not in LEVELS:
        problems.append(f": level must be easy, medium or hard, got {entry['level']!r}")
    if "keep_off" in entry:
        keep_off = entry["keep_off"]
        if not isinstance(keep_off, list) or not keep_off:
            problems.append(": keep_off must be a list of names; leave it out to keep no one off")
        else:
            own, held = _plain(owner).lower(), []
            for kept in keep_off:
                if not isinstance(kept, str):
                    problems.append(f": keep_off holds {kept!r}, which {_NAME_RULE}")
                    continue
                plain = _plain(kept)
                rule = broken(kept, plain)
                if rule is not None:
                    problems.append(f": keep_off holds {kept!r}, which {rule}")
                if plain.lower() == own:
                    problems.append(": keep_off holds the riddle's own name")
                elif plain.lower() in held:
                    problems.append(f": {kept!r} is listed twice in keep_off")
                held.append(plain.lower())
    if "who" in entry and not isinstance(entry["who"], str):
        problems.append(f": who must be text, got {entry['who']!r}")
    return problems
