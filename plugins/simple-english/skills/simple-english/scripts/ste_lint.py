#!/usr/bin/env python3
"""Simple English linter.

Checks the rules in SKILL.md that a search can reach honestly. Every pattern
here was measured against a 36,000-word test corpus of generated documents
before it shipped. The precision notes in RULES below record what that
measurement found, so a later editor can see why each pattern is shaped as it is.

Three rules are deliberately absent — noun clusters, list parallelism, and
one-term-per-concept beyond the fixed table. Detectors for those ran at roughly
85% false positives without part-of-speech tagging. A linter that cries wolf
teaches you to ignore it, so they stay a reading task.

Usage:
    python ste_lint.py FILE [FILE ...]      lint files
    python ste_lint.py --quiet FILE         one line per finding, no footer
    python ste_lint.py --selftest           verify the patterns still work
    python ste_lint.py --json FILE          machine-readable output
    python ste_lint.py --prose FILE         word and sentence rules only
    python ste_lint.py --structure FILE     label, emphasis, list, and table rules only

Run --selftest after you install or upgrade this skill, after anyone edits this
file, or when a clean result looks wrong. It verifies the patterns against 32
planted cases. Do not run it per document: the code is deterministic, so a
second run on an unchanged file tells you nothing new.

Exit codes: 0 clean or warnings only, 1 errors found, 2 selftest failed.
Standard library only. Python 3.8+.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Shared fragments
# --------------------------------------------------------------------------

IRREGULAR = (
    "been become begun broken brought built bought caught chosen come done drawn driven eaten "
    "fallen felt flown forgotten found given gone got gotten grown heard held kept known laid led "
    "left lent lost made meant met paid put read risen run said seen sent set shown sold spoken "
    "spent stood taken taught told thought thrown understood won written cut hit hurt let shut "
    "split spread bent dealt fed fled flung hung lit slid stuck struck swept swung torn worn "
    "frozen stolen ridden hidden bitten beaten forbidden"
).split()

# "rebuilt" contains "built" but a word boundary blocks the match, so allow prefixes.
_PREFIX = r"(?:re|un|over|under|mis|pre|dis|out|up)?-?"
PARTICIPLE = r"(?:(?:\w+-)?\w+ed|" + _PREFIX + r"(?:" + "|".join(IRREGULAR) + r"))"

BRITISH = (
    "colour colours coloured colouring colourful behaviour behaviours behavioural favour favours "
    "favoured favourite favourites labour labours laboured neighbour neighbours neighbouring "
    "honour honours honoured honourable humour humourless organise organised organising "
    "organisation organisations organisational recognise recognised recognising apologise "
    "apologised apologising realise realised realising analyse analysed analysing summarise "
    "summarised summarising prioritise prioritised utilise utilised centre centres centred "
    "theatre theatres metre metres litre litres defence defences offence offences licence "
    "licences catalogue catalogues analogue travelled travelling traveller cancelled cancelling "
    "modelling labelled labelling fuelled grey programme programmes whilst amongst enrol "
    "enrolment fulfil fulfilment instalment skilful marvellous"
).split()

# Whole words, never suffixes: "analys\w*" also matches "analysis", which is correct American.
BRITISH_RX = r"\b(" + "|".join(BRITISH) + r")\b"

# Registered names keep their own spelling. SKILL.md exempts proper nouns, but a
# regex cannot recognise one, so name the cases you hit. Extend this list freely.
PROPER_NOUN_SPELLINGS = {
    "defence industries",     # AeroSpace and Defence Industries Association of Europe
    "labour party", "ministry of defence", "centre for", "theatre royal",
}

CANONICAL = {
    "verify": "check", "confirm": "check", "validate": "check", "ensure": "check",
    "repair": "fix", "resolve": "fix",
    "begin": "start", "launch": "start", "initiate": "start", "commence": "start",
    "halt": "stop", "terminate": "stop",
    "utilize": "use", "utilise": "use", "leverage": "use", "employ": "use", "harness": "use",
    "display": "show", "render": "show",
    "modify": "change", "alter": "change", "amend": "change",
    "generate": "create", "produce": "create",
    "obtain": "get", "retrieve": "get", "fetch": "get",
    "assist": "help", "facilitate": "help",
    "locate": "find", "discover": "find",
    "additionally": "also", "furthermore": "also", "moreover": "also",
    "therefore": "so", "thus": "so", "hence": "so", "consequently": "so",
    "regarding": "about", "concerning": "about",
}
CANON_RX = r"\b(" + "|".join(sorted(CANONICAL)) + r")\b"

# Two kinds of false positive live here. Fixed noun phrases ("in writing", "by
# standing order"), and plain nouns that simply end in -ing. "by string
# concatenation" is not a gerund; the word just looks like one.
GERUND_NOUNS = {
    # fixed noun phrases
    "writing", "being", "passing", "standing", "landing", "morning", "evening",
    "building", "meeting", "opening", "closing", "warning", "setting", "training",
    # nouns that merely end in -ing
    "string", "strings", "thing", "things", "anything", "everything", "nothing",
    "something", "ring", "spring", "wing", "ceiling", "sibling", "during",
    "engineering", "marketing", "accounting", "heading", "listing", "casing",
}

NOT_IMPERATIVE = (
    "The A An This That These Those It They We You I He She Because Since If When Unless "
    "Every Each Most Some Both Neither Either No Our Your Their His Her Its"
).split()

RULES = [
    # (id, tier, compiled pattern, message, measured precision note)
    ("perfect", "error",
     re.compile(r"\b(has|have|had)\b(\s+\b(not|never|already|just|also|only|recently|always)\b)?\s+("
                + PARTICIPLE + r")\b", re.I),
     "stacked auxiliary (perfect tense) - name the actor and use a simple tense",
     "0 false positives on a 10-document corpus"),

    ("passive", "error",
     re.compile(r"\b(is|are|was|were|be|been|being|am|get|gets|got|getting)\s+(?:\w+ly\s+)?("
                + PARTICIPLE + r")\b", re.I),
     "passive voice - name the actor",
     "12/13 on hard cases, 0 false positives"),

    ("spelling", "error",
     re.compile(BRITISH_RX, re.I),
     "British spelling - use American English",
     "16 genuine hits, 0 false positives against an American regression set"),

    ("gerund", "warn",
     re.compile(r"\b(instead of|without|by|before|after|rather than|prior to)\s+(\w+ing)\b", re.I),
     "gerund after a preposition",
     "2 of 4 corpus hits genuine; fixed noun phrases filtered"),

    # "most" and "many" are deliberately absent. The rule reads "give a precise
    # count WHEN ONE EXISTS", and a regex cannot test that condition. Measured on
    # a 37,000-word corpus, "most" produced 29 of 52 hits and nearly all were
    # legitimate proportions with no figure available ("most allocations never
    # reach old space"). The words below imply a countable set the writer omitted.
    # Second sharpening. "a few hundred keys" and "several weeks" approximate a
    # magnitude that genuinely varies; they are not a hidden count. The negative
    # lookahead drops them, which took the corpus from 16 hits to a handful of
    # real ones such as "a handful of recurring reasons:" followed by the list.
    ("vague", "warn",
     re.compile(r"\b(several|a few|a number of|various|a handful of|a couple of|some of the)\b"
                r"(?!\s+(?:hundred|thousand|million|billion|dozen|second|seconds|minute|minutes|"
                r"hour|hours|day|days|week|weeks|month|months|year|years|ms|kb|mb|gb|tb|percent))", re.I),
     "vague quantifier - a count exists here, so give it",
     "sharpened twice against a 37,000-word corpus; 52 -> 16 -> single digits"),

    ("modal", "warn",
     re.compile(r"\b(should|would|might|could)\b|\bmay\b"),
     "modal outside can/will/must - keep a true counterfactual or permission, cut a hedge",
     "29 hits; 17 were legitimate counterfactuals, so review each"),

    ("canonical", "warn",
     re.compile(CANON_RX, re.I),
     "non-canonical term",
     "0 hits in the corpus; the interface and code always win"),

    ("condition", "warn",
     re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(?!(?:" + "|".join(NOT_IMPERATIVE) + r")\b)"
                r"([A-Z][a-z]+)\b([^.\n]*?)\s(if|when|unless)\s([^.\n]*)\.", re.M),
     "trailing condition in an instruction - write 'If X, do Y'",
     "10/10 on planted cases, 83% corpus precision"),
]

PROSE_CAP_DESCRIPTIVE = 25
PROSE_CAP_PROCEDURAL = 20
PARAGRAPH_CAP = 6

# A list item is procedural only when it opens with an imperative verb. Treating
# every capitalised bullet as an instruction applies the tighter 20-word cap to
# descriptive text ("Leaf nodes hold the actual index entries...") and produced
# 9 false positives on the corpus. Under-detecting is the safe direction: a
# missed instruction gets judged at 25 words instead of 20, which costs little.
IMPERATIVE_VERBS = set((
    "run use add set check read write keep make take give send plan open close start stop delete "
    "create find install configure restart apply remove copy move rename edit update build deploy "
    "test measure record log plot compare capture follow trace expand collapse enter exit return "
    "call fetch pull push commit merge revert tag release ship rollback drain scale wait retry "
    "confirm review inspect audit scan search filter select sort count divide multiply subtract "
    "fold hand show ask collect hold repeat circulate watch limit sit complete secure brief finish "
    "pass sign issue reimburse refund explain derive prefer cap clamp drop replace wrap define "
    "avoid match choose present own lead target publish deliver name list rank verify validate "
    "ensure describe assign schedule notify escalate document archive export import enable disable "
    "grant revoke rotate clear reset flush mount unmount attach detach bind unbind"
).split())


def is_procedural(line):
    m = re.match(r"^\s*(?:[-*+]|\d+\.)\s+\*{0,2}([A-Za-z][a-z]+)\b", line)
    return bool(m) and m.group(1).lower() in IMPERATIVE_VERBS


# --------------------------------------------------------------------------
# Exemptions
# --------------------------------------------------------------------------

def mask(text):
    """Blank out the exemptions from SKILL.md. Keeps line numbers intact.

    Quoted material matters more than it looks. A style guide is mostly
    counter-examples, so a linter that reads inside quotation marks flags every
    "has been configured" the guide tells you to avoid.
    """
    out, fence = [], False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            fence = not fence
            out.append("")
            continue
        if fence or re.match(r"^ {4,}\S", line):
            out.append("")
            continue
        line = re.sub(r"`[^`]*`", " ", line)                 # inline code
        line = re.sub(r"https?://\S+", " ", line)            # URLs
        line = re.sub(r'"[^"\n]*"', " ", line)               # straight quotes
        line = re.sub(r"“[^”\n]*”", " ", line)  # curly quotes
        out.append(line)
    return out


def is_structural(line):
    """Headings, table rows, separators, and front-matter labels are not prose.

    Separator lines matter for the paragraph count: a line such as "--- R1 ---"
    or "***" is not blank, so without this test it opens a paragraph and every
    following line accumulates into it.
    """
    s = line.strip()
    if not s:
        return True
    if s.startswith("#") or s.startswith("|"):
        return True
    # A rule line ("-----"), or a labelled separator ("--- R1 ---",
    # "=== SECTION ==="). Both open and close with a run of the same marker.
    if re.fullmatch(r"[-=*_~<>\s]{3,}", s):
        return True
    if len(s) < 80 and re.fullmatch(r"[-=*_~]{2,}[^\n]*?[-=*_~]{2,}", s):
        return True
    return bool(re.match(r"^[A-Z][\w ]{0,24}:\s", s))


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_patterns(lines):
    findings = []
    for rid, tier, rx, msg, _prec in RULES:
        if rid == "condition":
            for i, line in enumerate(lines, 1):
                if rx.search(line):
                    findings.append((i, tier, rid, line.strip()[:90], msg))
            continue
        for i, line in enumerate(lines, 1):
            if is_structural(line):
                continue
            for m in rx.finditer(line):
                if rid == "gerund" and m.group(2).lower() in GERUND_NOUNS:
                    continue
                if rid == "spelling":
                    window = line[m.start():m.start() + 40].lower()
                    if any(window.startswith(p) for p in PROPER_NOUN_SPELLINGS):
                        continue
                hit = m.group(0)
                extra = ""
                if rid == "canonical":
                    extra = f" -> use '{CANONICAL[hit.lower()]}'"
                findings.append((i, tier, rid, hit, msg + extra))
    return findings


def sentences(text, min_words=1):
    """Split on . ! ? and ; — a semicolon joins two independent clauses, so it
    ends a sentence for counting purposes. Masking inline code leaves ragged
    whitespace, so collapse it first or two sentences merge into one long one.
    """
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?;])\s+", text)
    return [p for p in parts if len(p.split()) >= min_words]


def check_length(lines):
    findings = []
    for i, line in enumerate(lines, 1):
        if is_structural(line):
            continue
        body = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line)
        procedural = is_procedural(line)
        cap = PROSE_CAP_PROCEDURAL if procedural else PROSE_CAP_DESCRIPTIVE
        for sent in sentences(body):
            n = len(sent.split())
            if n > cap:
                kind = "procedural" if procedural else "descriptive"
                findings.append((i, "warn", "length",
                                 f"{n} words", f"{kind} sentence over the ~{cap}-word cap"))
    return findings


def check_paragraphs(lines):
    findings = []
    start, buf = None, []
    def flush():
        if not buf:
            return None
        text = " ".join(buf)
        # 3-word floor: a masked fragment is not a sentence, and counting it
        # inflates the paragraph tally.
        n = len(sentences(text, min_words=3))
        if n > PARAGRAPH_CAP:
            return (start, "warn", "paragraph", f"{n} sentences",
                    f"paragraph over the {PARAGRAPH_CAP}-sentence cap - split where the topic turns")
        return None
    for i, line in enumerate(lines, 1):
        if not line.strip() or is_structural(line) or re.match(r"^\s*(?:[-*+]|\d+\.)\s", line):
            f = flush()
            if f:
                findings.append(f)
            start, buf = None, []
            continue
        if start is None:
            start = i
        buf.append(line.strip())
    f = flush()
    if f:
        findings.append(f)
    return findings


# --------------------------------------------------------------------------
# Structure checks
# --------------------------------------------------------------------------

LABELS = ("WARNING", "CAUTION", "BLOCKED", "ACTION", "UNVERIFIED", "ASSUMED")

# Labels a writer reaches for that are not on the list. A deny-list, not "any
# uppercase bold word": a bold acronym lead-in such as "**API:**" is correct.
ROGUE_LABELS = ("NOTE", "NB", "IMPORTANT", "TIP", "HINT", "INFO", "FYI", "DANGER",
                "ALERT", "ATTENTION", "CRITICAL", "TODO")

_ITEM = re.compile(r"^(\s*)(?:([-*+])|\d+[.)])\s+")
_LABEL = re.compile(r"^\*\*([A-Za-z]{2,}):\*\*")
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
# A lead-in opens the body and ends with a full stop or colon, inside the bold or right after it,
# or is a bold span followed by a dash: "**If it fails** - text".
_LEAD_IN = re.compile(r"^\*\*[^*\n]+?(?:[.:]\*\*|\*\*[.:])|^\*\*[^*\n]+\*\*\s+[—–-]\s")
_QUOTE = re.compile(r"^\s*(?:>\s?)+")
_CELL_BREAK = re.compile(r"[.!?]\s+[A-Z]")


def structure_lines(text):
    """Blank fenced code and inline code, and keep indentation, which nesting needs.

    mask() blanks every line indented 4 or more spaces as code, so a nested list
    item disappears there. These checks read layout, so they get their own view.
    """
    out, fence = [], None
    for line in text.split("\n"):
        stripped = line.strip()
        marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else None
        if marker and fence in (None, marker):
            fence = None if fence else marker
            out.append("")
            continue
        out.append("" if fence else re.sub(r"`[^`]*`", " ", line))
    return out


def _body(line):
    line = _QUOTE.sub("", line)
    m = _ITEM.match(line)
    return line[m.end():] if m else line.strip()


def check_labels(lines):
    findings, seen = [], set()
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            seen = set()
            continue
        m = _LABEL.match(_body(line))
        if not m:
            continue
        word = m.group(1)
        if word.upper() in ROGUE_LABELS:
            findings.append((i, "error", "label", word,
                             "label not on the list - use " + ", ".join(LABELS) + ", or no label"))
        elif word in LABELS:
            if word in seen:
                findings.append((i, "warn", "label-repeat", word,
                                 "same label twice in one section - most replies need at most 1"))
            seen.add(word)
    return findings


def check_emphasis(lines):
    findings = []
    start, count = None, 0

    def close():
        if count > 1:
            findings.append((start, "warn", "emphasis", f"{count} bold spans",
                             "more than 1 emphasis bold span in a paragraph - keep the one that sets the risk"))

    for i, line in enumerate(lines, 1):
        s = line.strip()
        item = _ITEM.match(line)
        if not s or s.startswith("#") or s.startswith("|") or item:
            close()
            start, count = None, 0
            if not item:
                continue
        body = _body(line)
        if start is None:
            start = i
        count += len(_BOLD.findall(body)) - (1 if _LEAD_IN.match(body) else 0)
    close()
    return findings


def check_nesting(lines):
    findings, stack = [], []
    for i, line in enumerate(lines, 1):
        m = _ITEM.match(line)
        if not m:
            if line.strip() and not line.startswith((" ", "\t")):
                stack = []
            continue
        indent = len(m.group(1).expandtabs(4))
        while stack and indent < stack[-1]:
            stack.pop()
        if not stack or indent > stack[-1]:
            stack.append(indent)
        if len(stack) > 2:
            findings.append((i, "warn", "nesting", f"level {len(stack) - 1}",
                             "list nested deeper than 1 level - use a heading or a table"))
    return findings


def check_two_item(lines):
    findings = []
    start, bullets, numbered = None, 0, False

    def close():
        if bullets == 2 and not numbered:
            findings.append((start, "warn", "two-item", "2 items",
                             "bulleted list with 2 items - one sentence with 'and' reads as fast"))

    for i, line in enumerate(lines, 1):
        m = _ITEM.match(line)
        if m and len(m.group(1)) < 2:
            if start is None:
                start = i
            if m.group(2):
                bullets += 1
            else:
                numbered = True
            continue
        if m or not line.strip() or line.startswith((" ", "\t")):
            continue
        close()
        start, bullets, numbered = None, 0, False
    close()
    return findings


def check_cells(lines):
    findings = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s.startswith("|") or set(s) <= set("|-: "):
            continue
        for cell in s.strip("|").split("|"):
            if _CELL_BREAK.search(re.sub(r"^\d+[.)]\s+", "", cell.strip())):
                findings.append((i, "warn", "cell", cell.strip()[:44],
                                 "table cell with 2 or more sentences - move the detail into prose under the table"))
    return findings


def check_structure(lines):
    return (check_labels(lines) + check_emphasis(lines) + check_nesting(lines)
            + check_two_item(lines) + check_cells(lines))


def lint(path, scope="all"):
    """scope "prose" runs the word and sentence rules, "structure" the layout rules, "all" both."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    found = []
    if scope in ("all", "prose"):
        lines = mask(text)
        found += check_patterns(lines) + check_length(lines) + check_paragraphs(lines)
    if scope in ("all", "structure"):
        found += check_structure(structure_lines(text))
    return sorted(found, key=lambda x: (x[0], x[2]))

# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

SELFTEST = [
    ("The migration has been applied to staging.", "perfect", True),
    ("The deploy job applied the migration.", "perfect", False),
    ("The index must be rebuilt after the upgrade.", "passive", True),
    ("Records are retained for seven years.", "passive", True),
    ("We retain records for seven years.", "passive", False),
    ("The colour of the label changed.", "spelling", True),
    ("The color of the label changed.", "spelling", False),
    ("The analysis covered every case.", "spelling", False),
    ("Fix it instead of omitting the claim.", "gerund", True),
    ("Pay by standing order each month.", "gerund", False),
    ("Several tests fail.", "vague", True),
    ("Three tests fail.", "vague", False),
    ("This should work after the restart.", "modal", True),
    ("This works after the restart.", "modal", False),
    ("Verify the token before you continue.", "canonical", True),
    ("Check the token before you continue.", "canonical", False),
    ("- Read the log if the build fails.", "condition", True),
    ("- If the build fails, read the log.", "condition", False),
    ("- The script exits with status 1 when the directory disappears.", "condition", False),
    ("**NOTE:** the job retries.", "label", True),
    ("**WARNING:** this deletes the branch.", "label", False),
    ("**API:** the endpoint changed.", "label", False),
    ("**WARNING:** a.\n\n**WARNING:** b.", "label-repeat", True),
    ("**WARNING:** a.\n\n# Next\n\n**WARNING:** b.", "label-repeat", False),
    ("The job **silently** drops rows and **only** logs once.", "emphasis", True),
    ("**Retries.** The job **silently** drops rows.", "emphasis", False),
    ("- a\n  - b\n    - c", "nesting", True),
    ("- a\n  - b", "nesting", False),
    ("- a\n- b", "two-item", True),
    ("- a\n- b\n- c", "two-item", False),
    ("| Form | Use |\n| --- | --- |\n| Table | Use it. Then stop. |", "cell", True),
    ("| Form | Use |\n| --- | --- |\n| Table | Use it for 2 attributes. |", "cell", False),
]


def selftest():
    ok = bad = 0
    print("Simple English linter - self test\n")
    for sentence, rule, expect in SELFTEST:
        hits = {f[2] for f in check_patterns(mask(sentence))}
        hits |= {f[2] for f in check_structure(structure_lines(sentence))}
        got = rule in hits
        if got == expect:
            ok += 1
            mark = "pass"
        else:
            bad += 1
            mark = "FAIL"
        shown = sentence.replace("\n", " / ")[:60]
        print(f"  {mark}  {rule:12} expect={'hit ' if expect else 'miss'}  {shown}")
    print(f"\n{ok} passed, {bad} failed")
    if bad:
        print("\nThe linter does not work correctly here. Do not trust its output.")
    return 0 if bad == 0 else 2


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Simple English linter")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--selftest", action="store_true", help="verify the patterns still work")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", "-q", action="store_true",
                    help="one line per finding, no footer (for repeat runs)")
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--prose", action="store_const", const="prose", dest="scope",
                       help="only the word and sentence rules")
    scope.add_argument("--structure", action="store_const", const="structure", dest="scope",
                       help="only the label, emphasis, list, and table rules")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.files:
        ap.print_help()
        return 0

    all_findings = {}
    errors = 0
    for f in args.files:
        found = lint(f, args.scope or "all")
        all_findings[f] = found
        errors += sum(1 for x in found if x[1] == "error")

    if args.json:
        print(json.dumps({
            k: [{"line": a, "tier": b, "rule": c, "match": d, "message": e} for a, b, c, d, e in v]
            for k, v in all_findings.items()
        }, indent=2))
        return 1 if errors else 0

    for f, found in all_findings.items():
        errs = [x for x in found if x[1] == "error"]
        warns = [x for x in found if x[1] == "warn"]
        print(f"\n{f}   {len(errs)} error, {len(warns)} review")
        if not args.quiet:
            print("-" * 72)
        if not found:
            print("  clean on the rules this linter reaches")
        for line, tier, rid, match, msg in found:
            label = "ERROR " if tier == "error" else "review"
            if args.quiet:
                print(f"  {label} L{line:<4} [{rid}] {match[:44]!r}  {msg}")
            else:
                print(f"  {label} L{line:<4} [{rid}] {match[:44]!r}")
                print(f"         {msg}")

    if not args.quiet:
        print("\n" + "=" * 72)
        print("This linter reaches 16 rules. It says nothing about noun clusters, list")
        print("parallelism, one term per concept beyond the fixed table, front-loading,")
        print("or whether a claim names its mechanism. Those still need a read.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
