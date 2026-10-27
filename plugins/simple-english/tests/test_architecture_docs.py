import os
import re
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_DIR.parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "architecture" / "simple-english"
PATH_SUFFIXES = (".py", ".json", ".jsonl", ".md")
CONSTANT = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
INLINE_CODE = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
LINE_SUFFIX = re.compile(r":(\d+)(?:-(\d+))?$")
IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")
DOTTED = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")

# Files that each eval run writes to ~/.claude/simple-english-evals/<run-id>/.
# They never exist in the repository, so a page may name them freely.
RUN_OUTPUT = {
    "responses.jsonl", "lint.jsonl", "scores.jsonl", "jev.jsonl",
    "report.md", "sheet.md", "labels.jsonl", "sample-key.jsonl",
    # The opt-in file a user creates. It is tracked in the private repository only.
    ".claude/jev.json",
}


def inline_tokens(text):
    """Yield (line number, token) for each inline code span outside fenced blocks."""
    opening = None  # the fence that opened the current block: (character, length)
    for number, line in enumerate(text.splitlines(), start=1):
        fence = FENCE.match(line)
        if fence:
            marks, rest = fence.group(1), fence.group(2)
            if opening is None:
                opening = (marks[0], len(marks))
            elif marks[0] == opening[0] and len(marks) >= opening[1] and not rest.strip():
                opening = None
            continue
        if opening is None:
            for match in INLINE_CODE.finditer(line):
                yield number, match.group(1).strip()


def strip_line_suffix(token):
    return LINE_SUFFIX.sub("", token)


def exact_case_exists(base, relative):
    """True when every part of relative exists under base with the same letter case."""
    current = base
    for part in Path(relative).parts:
        if part not in os.listdir(current):
            return False
        current = current / part
    return True


def is_path(token):
    token = strip_line_suffix(token)
    if "://" in token:
        return False
    # A token with a space is a command. A token with < or * is a placeholder or a glob.
    # A token under ~/ is outside the repository by definition.
    if any(ch in token for ch in " <*") or token.startswith("~"):
        return False
    return "/" in token or token.endswith(PATH_SUFFIXES)


def is_constant(token):
    return bool(CONSTANT.match(token))


def path_exists(token):
    """Return (found, the paths tried), checking the plugin folder first, then the repository root."""
    if token in RUN_OUTPUT:
        return True, []
    relative = strip_line_suffix(token).lstrip("/")
    if "/" in relative.rstrip("/"):
        tried = [PLUGIN_DIR / relative, REPO_ROOT / relative]
        return any(p.exists() and exact_case_exists(root, relative) for p, root in zip(tried, (PLUGIN_DIR, REPO_ROOT))), [str(p) for p in tried]
    # A bare file name may sit anywhere in the plugin, such as SKILL.md or report.py.
    if any(relative in names for _, dirs, files in os.walk(PLUGIN_DIR) for names in (dirs, files)) or exact_case_exists(REPO_ROOT, relative):
        return True, []
    return False, [f"{PLUGIN_DIR}/**/{relative}", str(REPO_ROOT / relative)]


def cited_lines(token):
    """Return (first, last) for a token such as report.py:206 or report.py:12-30, or None."""
    match = LINE_SUFFIX.search(token)
    if not match:
        return None
    first = int(match.group(1))
    return first, int(match.group(2) or first)


def existing_files(token):
    """The files a path token names, with the same letter case: the plugin folder first, then the repository root."""
    relative = strip_line_suffix(token).lstrip("/")
    if "/" in relative:
        return [root / relative for root in (PLUGIN_DIR, REPO_ROOT)
                if (root / relative).is_file() and exact_case_exists(root, relative)]
    # A bare file name may match more than 1 file, such as the 2 copies of ste_lint.py.
    found = [p for p in sorted(PLUGIN_DIR.rglob(relative))
             if p.is_file() and p.name in os.listdir(p.parent) and "__pycache__" not in p.parts]
    if (REPO_ROOT / relative).is_file() and exact_case_exists(REPO_ROOT, relative):
        found.append(REPO_ROOT / relative)
    return found


def line_problem(token, names):
    """Return why a cited line range is wrong, or None when it holds.

    The range must exist in the file. When the page line also names constants or
    functions, at least 1 of those names must appear in the cited lines. With a
    bare file name, 1 matching file is enough.
    """
    first, last = cited_lines(token)
    files = existing_files(token)
    if not files:
        return None  # test_every_path_exists reports a missing file
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not 1 <= first <= last <= len(lines):
            continue
        cited = "\n".join(lines[first - 1:last])
        if not names or any(re.search(rf"\b{re.escape(name)}\b", cited) for name in names):
            return None
    wanted = f" that name {', '.join(names)}" if names else ""
    return f"cites `{token}`, but no file it names has lines {first}-{last}{wanted}"


def names_in(tokens):
    """The constant, dotted, and bare names among the tokens of a page line, as the last part of each."""
    return [t.split(".")[-1] for t in tokens
            if is_constant(t) or is_dotted(t) or IDENTIFIER.match(t)]


def is_dotted(token):
    """True for a qualified name such as common.split_out_of_date, but not for a file name such as report.py."""
    return bool(DOTTED.match(token)) and not is_path(token)


def module_file(name):
    """The .py file under the plugin with this module name, or None."""
    for path in sorted(PLUGIN_DIR.rglob(name + ".py")):
        if path.name in os.listdir(path.parent) and "__pycache__" not in path.parts:
            return path
    return None


def dotted_missing(token):
    """Return the parts of a dotted name that its module does not define.

    Return None when the first part is no module under the plugin, as in
    api.typesafe.ai. Each part counts when it is defined anywhere in the
    module, by a def, a class, or a top-level assignment.
    """
    module, *names = token.split(".")
    path = module_file(module)
    if path is None:
        return None
    source = path.read_text(encoding="utf-8")
    return [name for name in names
            if not re.search(rf"^\s*(?:def|class)\s+{re.escape(name)}\b|^{re.escape(name)}\s*=", source, re.MULTILINE)]


def source_outside_tests():
    """The text of every .py file under the plugin, except the files under tests/."""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(PLUGIN_DIR.rglob("*.py"))
                     if "tests" not in p.relative_to(PLUGIN_DIR).parts)


class HelperTest(unittest.TestCase):
    def test_tokens_skip_fenced_blocks(self):
        text = "Read `evals/report.py`.\n```mermaid\nA[`evals/gone.py`]\n```\nThen `LINT_MARGIN`.\n"
        self.assertEqual(list(inline_tokens(text)), [(1, "evals/report.py"), (5, "LINT_MARGIN")])

    def test_path_detection(self):
        self.assertTrue(is_path("evals/report.py"))
        self.assertTrue(is_path("cases.jsonl"))
        self.assertTrue(is_path("plugins/simple-english/evals/"))
        self.assertFalse(is_path("LINT_MARGIN"))
        self.assertFalse(is_path("--budget-usd"))
        self.assertFalse(is_path("claude plugin validate ./plugins/simple-english"))
        self.assertFalse(is_path("~/.claude/simple-english-evals/<run-id>/"))
        self.assertFalse(is_path("FINDINGS-*.md"))

    def test_constant_detection(self):
        self.assertTrue(is_constant("LINT_MARGIN"))
        self.assertTrue(is_constant("TYPESAFE_API_KEY"))
        self.assertFalse(is_constant("FINDINGS"))
        self.assertFalse(is_constant("Lint_Margin"))

    def test_resolves_plugin_paths(self):
        self.assertTrue(path_exists("evals/report.py")[0])
        self.assertTrue(path_exists("report.py")[0])
        found, tried = path_exists("evals/gone.py")
        self.assertFalse(found)
        self.assertEqual(len(tried), 2)

    @unittest.skipUnless(DOCS_DIR.is_dir(), "no repository root here, as in an installed copy of the plugin")
    def test_resolves_repo_paths(self):
        self.assertTrue(path_exists("docs/architecture/simple-english/deep-dive.md")[0])

    def test_letter_case_must_match(self):
        self.assertFalse(path_exists("Evals/Report.py")[0])
        self.assertFalse(path_exists("REPORT.py")[0])

    def test_line_suffixes_and_urls(self):
        self.assertTrue(path_exists("evals/report.py:12")[0])
        self.assertTrue(path_exists("evals/report.py:12-30")[0])
        self.assertTrue(is_path("evals/report.py:12"))
        self.assertFalse(is_path("https://example.com/x.md"))

    def test_nested_fences(self):
        text = "````md\n```\n`evals/gone.py`\n```\n````\nAfter `LINT_MARGIN`.\n"
        self.assertEqual(list(inline_tokens(text)), [(6, "LINT_MARGIN")])

    def test_run_output_names_are_allowed(self):
        self.assertTrue(path_exists("responses.jsonl")[0])

    def test_cited_lines(self):
        self.assertEqual(cited_lines("report.py:206"), (206, 206))
        self.assertEqual(cited_lines("evals/report.py:12-30"), (12, 30))
        self.assertIsNone(cited_lines("evals/report.py"))

    def test_cited_line_must_exist(self):
        self.assertIsNone(line_problem("evals/report.py:1", []))
        self.assertIsNotNone(line_problem("evals/report.py:99999", []))
        self.assertIsNotNone(line_problem("evals/report.py:30-12", []))

    def test_cited_line_must_hold_a_name_from_the_page_line(self):
        lines = (PLUGIN_DIR / "evals" / "report.py").read_text(encoding="utf-8").splitlines()
        number = next(i for i, line in enumerate(lines, start=1) if line.startswith("LINT_MARGIN"))
        self.assertIsNone(line_problem(f"evals/report.py:{number}", ["LINT_MARGIN"]))
        self.assertIsNone(line_problem(f"report.py:{number}", ["LINT_MARGIN", "gone_name"]))
        self.assertIsNotNone(line_problem(f"evals/report.py:{number}", ["gone_name"]))

    def test_names_in_a_page_line(self):
        tokens = ["LINT_MARGIN", "common.input_hash", "baseline", "report.py:206", "--budget-usd", "evals/report.py"]
        self.assertEqual(names_in(tokens), ["LINT_MARGIN", "input_hash", "baseline"])

    def test_dotted_detection(self):
        self.assertTrue(is_dotted("common.split_out_of_date"))
        self.assertTrue(is_dotted("test_data.ConditionsTest.test_three_conditions_and_their_files_exist"))
        self.assertFalse(is_dotted("report.py"))
        self.assertFalse(is_dotted("evals/report.py:206"))
        self.assertFalse(is_dotted("LINT_MARGIN"))

    def test_dotted_names_resolve(self):
        self.assertEqual(dotted_missing("common.input_hash"), [])
        self.assertEqual(dotted_missing("report.LINT_MARGIN"), [])
        self.assertEqual(dotted_missing("test_data.ConditionsTest"), [])
        self.assertEqual(dotted_missing("common.gone_function"), ["gone_function"])
        # A first part that is no module under the plugin is not a code reference.
        self.assertIsNone(module_file("REPORT"))
        self.assertIsNone(dotted_missing("api.typesafe.ai"))
        self.assertIsNone(dotted_missing("SKILL.md.next"))

    def test_constants_come_from_code_outside_tests(self):
        # RUN_OUTPUT is defined in this test file only.
        self.assertNotRegex(source_outside_tests(), r"\bRUN_OUTPUT\b")
        self.assertRegex(source_outside_tests(), r"\bLINT_MARGIN\b")


class ArchitectureDocsTest(unittest.TestCase):
    def setUp(self):
        if not DOCS_DIR.is_dir():
            self.skipTest("no docs/architecture/simple-english/ here, as in an installed copy of the plugin")
        self.pages = sorted(DOCS_DIR.glob("*.md"))
        self.source = source_outside_tests()

    def test_every_path_exists(self):
        for page in self.pages:
            for line, token in inline_tokens(page.read_text(encoding="utf-8")):
                if not is_path(token):
                    continue
                with self.subTest(page=page.name, token=token):
                    found, tried = path_exists(token)
                    self.assertTrue(found, f"{page.name}:{line} names `{token}`, but no file is at {' or '.join(tried)}")

    def test_every_constant_exists(self):
        for page in self.pages:
            for line, token in inline_tokens(page.read_text(encoding="utf-8")):
                if not is_constant(token):
                    continue
                with self.subTest(page=page.name, token=token):
                    self.assertRegex(self.source, rf"\b{token}\b",
                                     f"{page.name}:{line} names `{token}`, but no .py file outside plugins/simple-english/tests/ has it")

    def test_every_cited_line_holds(self):
        for page in self.pages:
            by_line = {}
            for line, token in inline_tokens(page.read_text(encoding="utf-8")):
                by_line.setdefault(line, []).append(token)
            for line, tokens in by_line.items():
                names = names_in(tokens) or names_in(by_line.get(line - 1, []))
                for token in tokens:
                    if not (is_path(token) and cited_lines(token)):
                        continue
                    with self.subTest(page=page.name, token=token):
                        problem = line_problem(token, names)
                        self.assertIsNone(problem, f"{page.name}:{line} {problem}")

    def test_every_dotted_name_exists(self):
        for page in self.pages:
            for line, token in inline_tokens(page.read_text(encoding="utf-8")):
                if not is_dotted(token):
                    continue
                missing = dotted_missing(token)
                if missing is None:
                    continue
                with self.subTest(page=page.name, token=token):
                    self.assertEqual(missing, [], f"{page.name}:{line} names `{token}`, but its module defines no {', '.join(missing)}")


if __name__ == "__main__":
    unittest.main()
