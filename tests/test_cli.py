"""Unit tests for env-to-ini."""

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

from env_to_ini.cli import main, parse_env, split_prefix, ini_quote


SAMPLE = """# app config
APP_NAME=demo
APP_DEBUG=true

# database
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY="s3cr3t #hash"
EMPTY=
BARE_KEY
not a valid line!!!"""


def run_cli(args, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = main(args)
    finally:
        sys.stdin = old
    return code, out.getvalue(), err.getvalue()


class ParseTest(unittest.TestCase):
    def test_export_prefix_and_quotes(self):
        doc = parse_env('export A=1\nB="two #2"\nC=\'x\'\n')
        self.assertEqual([e.key for e in doc.entries], ["A", "B", "C"])
        self.assertEqual(doc.entries[1].value, "two #2")

    def test_inline_comment_stripped_for_bare(self):
        doc = parse_env("A=1 # trailing\n")
        self.assertEqual(doc.entries[0].value, "1")

    def test_invalid_line_collected(self):
        doc = parse_env("!!!\nA=1\n")
        self.assertEqual(len(doc.invalid_lines), 1)
        self.assertEqual(len(doc.entries), 1)

    def test_bare_key(self):
        doc = parse_env("FLAG\n")
        self.assertEqual(doc.entries[0].value, "")

    def test_split_prefix(self):
        self.assertEqual(split_prefix("DB_POOL_SIZE"), ("db", "POOL_SIZE"))
        self.assertEqual(split_prefix("NOPE"), ("", "NOPE"))

    def test_ini_quote(self):
        self.assertEqual(ini_quote("abc"), "abc")
        self.assertEqual(ini_quote("a b"), "a b")
        self.assertEqual(ini_quote("x#y"), '"x#y"')
        self.assertEqual(ini_quote(""), '""')
        self.assertEqual(ini_quote(" pad "), '" pad "')


class CliTest(unittest.TestCase):
    def test_default_section(self):
        code, out, _ = run_cli(["--no-header"], "A=1\nB=2\n")
        self.assertEqual(code, 0)
        self.assertIn("[default]", out)
        self.assertIn("A = 1", out)

    def test_prefix_keys(self):
        code, out, _ = run_cli(["--prefix-keys", "--no-header"], "DB_HOST=x\nAPP_NAME=y\n")
        self.assertEqual(code, 0)
        self.assertIn("[db]", out)
        self.assertIn("HOST = x", out)
        self.assertIn("[app]", out)

    def test_prefix_keep(self):
        _, out, _ = run_cli(["--prefix-keys", "--keep", "--no-header"], "DB_HOST=x\n")
        self.assertIn("DB_HOST = x", out)

    def test_check_fails_on_invalid(self):
        code, out, err = run_cli(["--check"], SAMPLE)
        self.assertEqual(code, 2)
        self.assertIn("not a valid line", err)
        self.assertIn("[default]", out)  # INI still emitted

    def test_warning_no_prefix(self):
        code, out, err = run_cli(["--prefix-keys"], "NOPE=1\n")
        self.assertEqual(code, 0)
        self.assertIn("no prefix", err)

    def test_json_report_no_values(self):
        code, out, err = run_cli(["--json"], "SECRET=topsecret\nA=1\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertNotIn("topsecret", err)
        self.assertIn('"entries": 2', err)

    def test_require_sections(self):
        code, _, _ = run_cli(["--prefix-keys", "--require-sections", "db,cache"],
                             "DB_A=1\n")
        self.assertEqual(code, 2)

    def test_forbid_section(self):
        code, _, _ = run_cli(["--forbid-section", "default"], "A=1\n")
        self.assertEqual(code, 2)

    def test_max_warnings(self):
        code, _, _ = run_cli(["--max-warnings", "0", "--prefix-keys"], "NOPE=1\n")
        self.assertEqual(code, 2)

    def test_comments_preserved(self):
        code, out, _ = run_cli(["--comments", "--no-header"], "# hello\nA=1\n")
        self.assertIn("; hello", out)

    def test_sort_keys(self):
        _, out, _ = run_cli(["--sort", "--no-header"], "B=2\nA=1\n")
        self.assertLess(out.index("A = 1"), out.index("B = 2"))

    def test_missing_file(self):
        code, _, err = run_cli(["/no/such/file.env"])
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err)

    def test_in_place_requires_file(self):
        code, _, err = run_cli(["--in-place"], "A=1\n")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
