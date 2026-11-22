"""Pass or fail a mutation run against the floor.

After `python -m mutmut run` and `python -m mutmut export-cicd-stats`:

    python tools/mutation_floor.py [mutants/mutmut-cicd-stats.json]

It ends with 0 when the share of mutants killed is at or above the floor, 1 when
it is under the floor or the run cannot be trusted, and 2 when the summary
cannot be read. A development tool: the package never imports it.
"""
import json
import sys
from pathlib import Path

FLOOR = 80.0                                          # per cent of mutants that the tests must kill
SUMMARY = Path("mutants/mutmut-cicd-stats.json")      # where mutmut writes its summary
INTERRUPTED = "check_was_interrupted_by_user"


def verdict(stats, floor=FLOOR):
    """Whether a run's summary meets the floor -> (passed, a sentence that says why).

    The rate is killed / total. A mutant that timed out, looked suspicious or had
    no test counts against it exactly as a survivor does.
    """
    if not isinstance(stats, dict):
        return False, f"the mutation summary must be a JSON object, got {stats!r}"
    counts = {}
    for name, required in (("killed", True), ("total", True), (INTERRUPTED, False)):
        if name not in stats:
            if required:
                return False, f"the mutation summary has no count of {name!r}"
            counts[name] = 0                          # an older mutmut does not say; take the run as whole
            continue
        counts[name] = stats[name]
        if type(counts[name]) is not int:             # True is an int to Python, and not a count
            return False, f"the count of {name!r} must be a whole number, got {counts[name]!r}"
    killed, total = counts["killed"], counts["total"]
    if counts[INTERRUPTED]:
        return False, "the mutation run was interrupted, so its counts cannot be trusted"
    if not 0 <= killed <= total:
        return False, f"{killed} mutants killed out of {total} made cannot be right"
    if total == 0:
        return False, "no mutants were made, so the tests were not tried against anything"
    rate = (1000 * killed // total) / 10              # never rounded up: 79.99% must not read as 80.0%
    told = f"{killed} of {total} mutants killed ({rate:.1f}%)"
    if 100 * killed < floor * total:
        return False, f"{told}, under the floor of {floor:g}%"
    return True, f"{told}; the floor is {floor:g}%"


def main(argv=None):
    """Read one summary file and say whether it meets the floor -> the exit status."""
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) > 1:
        print("usage: python tools/mutation_floor.py [summary.json]", file=sys.stderr)
        return 2
    path = Path(args[0]) if args else SUMMARY
    try:
        stats = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as error:      # missing, not text, not JSON, nested too deeply
        print(f"cannot read the mutation summary {path}: {error}", file=sys.stderr)
        return 2
    passed, message = verdict(stats)
    print(message, file=sys.stdout if passed else sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
