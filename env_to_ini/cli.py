"""Convert dotenv (.env) files to INI configuration format.

Reads a dotenv file (KEY=VALUE lines with optional comments and `export`
prefixes) and emits an INI document. Keys are mapped to INI sections:

  * by the ``--section`` flag for every key (default),
  * by the key prefix with ``--prefix-keys`` (``DB_HOST`` -> ``[db]``),
  * by an explicit ``KEY=section`` mapping file via ``--map``.

Values are never printed in the JSON report (``--json``) and comment-only
lines are preserved as INI comments when ``--comments`` is set.

Exit codes:
    0  success
    1  CLI / I/O error
    2  a lint gate failed (--check, --max-warnings, --require-sections, ...)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_EXPORT_RE = re.compile(r"^\s*export\s+")


@dataclass
class EnvEntry:
    key: str
    value: str          # unquoted / unescaped value, used for quoting decisions
    raw_value: str      # exact RHS after '=', comments stripped
    quote: str          # '', "'", '"' as found in the file
    line: int           # 1-based line number
    section: str = ""   # resolved later


@dataclass
class ParsedEnv:
    entries: List[EnvEntry] = field(default_factory=list)
    comments: List[Tuple[int, str]] = field(default_factory=list)  # (before_line, text)
    blank_lines: int = 0
    invalid_lines: List[Tuple[int, str]] = field(default_factory=list)


def _strip_inline_comment(value: str) -> str:
    """Remove `` # comment`` python-dotenv style (outside quotes)."""
    out: List[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "#" and (i == 0 or value[i - 1] in " \t"):
            break
        if ch == "\\" and i + 1 < len(value):
            out.append(value[i:i + 2])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _unescape_double(value: str) -> str:
    out: List[str] = []
    i = 0
    mapping = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            out.append(mapping.get(nxt, ch + nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _unescape_single(value: str) -> str:
    return value.replace("\\'", "'").replace("\\\\", "\\")


def parse_env(text: str) -> ParsedEnv:
    doc = ParsedEnv()
    pending: List[str] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if not stripped:
            doc.comments.append((lineno, ""))
            doc.blank_lines += 1
            pending = []
            continue
        if stripped.startswith("#"):
            pending.append(line)
            continue
        body = _EXPORT_RE.sub("", line, count=1)
        if "=" not in body:
            head = body.strip()
            if _KEY_RE.match(head):
                for c in pending:
                    doc.comments.append((lineno, c))
                pending = []
                doc.entries.append(EnvEntry(key=head, value="", raw_value="", quote="", line=lineno))
            else:
                doc.invalid_lines.append((lineno, line))
                pending = []
            continue
        key, _, rhs = body.partition("=")
        key = key.strip()
        if not _KEY_RE.match(key):
            doc.invalid_lines.append((lineno, line))
            pending = []
            continue
        rhs_stripped = rhs.strip()
        quote = ""
        value = rhs_stripped
        if len(rhs_stripped) >= 2 and rhs_stripped[0] == rhs_stripped[-1] and rhs_stripped[0] in "\"'":
            quote = rhs_stripped[0]
            value = rhs_stripped[1:-1]
            value = _unescape_double(value) if quote == '"' else _unescape_single(value)
        else:
            value = _strip_inline_comment(rhs_stripped)
        for c in pending:
            doc.comments.append((lineno, c))
        pending = []
        doc.entries.append(EnvEntry(key=key, value=value, raw_value=rhs_stripped, quote=quote, line=lineno))
    # dedupe comment lines
    seen = set()
    uniq: List[Tuple[int, str]] = []
    for item in doc.comments:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    doc.comments = uniq
    return doc


def split_prefix(key: str) -> Tuple[str, str]:
    """``DB_POOL_SIZE`` -> (``db``, ``POOL_SIZE``)."""
    parts = key.split("_", 1)
    if len(parts) == 2 and parts[0]:
        return parts[0].lower(), parts[1]
    return "", key


def resolve_sections(
    entries: List[EnvEntry],
    default_section: str,
    prefix_keys: bool,
    mapping: Dict[str, str],
    keep: bool,
) -> List[str]:
    warnings: List[str] = []
    for e in entries:
        if e.key in mapping:
            e.section = mapping[e.key]
        elif prefix_keys:
            prefix, rest = split_prefix(e.key)
            if prefix:
                e.section = prefix
                if not keep:
                    e.key = rest
            else:
                e.section = default_section
                warnings.append(f"line {e.line}: key {e.key!r} has no prefix, fallback to [{default_section}]")
        else:
            e.section = default_section
    return warnings


_SAFE_RE = re.compile(r"^[A-Za-z0-9_.,:/@%+\-= \t]*$")


def ini_quote(value: str) -> str:
    if value == "" or value != value.strip():
        return '"' + value + '"'
    if not _SAFE_RE.match(value):
        escaped = (value.replace("\\", "\\\\").replace('"', '\\"')
                        .replace("\n", "\\n").replace("\t", "\\t"))
        return '"' + escaped + '"'
    return value


def ini_comment(text: str) -> str:
    t = text.strip()
    if t.startswith("#"):
        t = t[1:].lstrip()
    return "; " + t


def emit_ini(doc: ParsedEnv, sort: bool, comments: bool, header: bool) -> str:
    lines: List[str] = []
    by_section: Dict[str, List[EnvEntry]] = {}
    order: List[str] = []
    for e in doc.entries:
        if e.section not in by_section:
            by_section[e.section] = []
            order.append(e.section)
        by_section[e.section].append(e)
    if header:
        lines.append("; generated by env-to-ini")
        lines.append("")
    first_line = min((e.line for e in doc.entries), default=None)
    if comments and first_line is not None:
        top = [t for (ln, t) in doc.comments if ln < first_line and t]
        for t in top:
            lines.append(ini_comment(t))
        if top:
            lines.append("")
    for section in order:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(f"[{section}]")
        entries = by_section[section]
        if sort:
            entries = sorted(entries, key=lambda x: x.key.lower())
        for e in entries:
            if comments:
                for ln, t in doc.comments:
                    if ln == e.line and t:
                        lines.append(ini_comment(t))
            lines.append(f"{e.key} = {ini_quote(e.value)}")
    return "\n".join(lines) + ("\n" if lines else "")


def load_mapping(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for sep in ("=", ":"):
            if sep in line:
                k, _, v = line.partition(sep)
                k, v = k.strip(), v.strip()
                if k and v:
                    out[k] = v
                break
    return out


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _write(text: str, in_path: Optional[str], out_path: Optional[str], in_place: bool) -> None:
    if in_place and in_path and in_path != "-":
        with open(in_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    elif out_path:
        with open(out_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="env-to-ini",
        description="Convert dotenv (.env) files to INI configuration with section mapping.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("file", nargs="?", default="-", help="input .env file (default: stdin, use '-' explicitly)")
    p.add_argument("--section", "-s", default="default",
                   help="section for keys without explicit mapping (default: %(default)s)")
    p.add_argument("--prefix-keys", "-k", action="store_true",
                   help="map DB_HOST -> section [db] key HOST (prefix before first underscore)")
    p.add_argument("--keep", action="store_true",
                   help="with --prefix-keys, keep the full key name instead of stripping the prefix")
    p.add_argument("--map", "-m", help="file with KEY=section mappings (highest precedence)")
    p.add_argument("--sort", action="store_true", help="sort keys inside each section")
    p.add_argument("--comments", "-c", action="store_true",
                   help="preserve '#' comments as INI ';' comments")
    p.add_argument("--no-header", action="store_true", help="omit the generated header line")
    p.add_argument("--output", "-o", help="write to FILE instead of stdout")
    p.add_argument("--in-place", action="store_true", help="overwrite the input file")
    p.add_argument("--json", action="store_true", help="print a JSON report on stderr instead of INI")
    p.add_argument("-q", "--quiet", action="store_true", help="suppress warnings (exit code still set)")
    p.add_argument("--check", action="store_true",
                   help="exit 2 if any warning or invalid line is found (CI mode)")
    p.add_argument("--max-warnings", type=int, metavar="N",
                   help="exit 2 when more than N warnings are raised")
    p.add_argument("--require-sections", metavar="LIST",
                   help="comma separated sections that must be present")
    p.add_argument("--forbid-section", metavar="LIST",
                   help="comma separated sections that must not be present")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.in_place and args.file == "-":
        print("env-to-ini: --in-place requires a real file path", file=sys.stderr)
        return 1
    try:
        text = _read(args.file)
    except OSError as exc:
        print(f"env-to-ini: cannot read {args.file!r}: {exc}", file=sys.stderr)
        return 1

    doc = parse_env(text)

    mapping: Dict[str, str] = {}
    if args.map:
        try:
            mapping = load_mapping(_read(args.map))
        except OSError as exc:
            print(f"env-to-ini: cannot read mapping {args.map!r}: {exc}", file=sys.stderr)
            return 1

    warnings = resolve_sections(doc.entries, args.section, args.prefix_keys, mapping, args.keep)
    for lineno, line in doc.invalid_lines:
        warnings.append(f"line {lineno}: ignored invalid line {line.strip()!r}")

    ini_text = emit_ini(doc, args.sort, args.comments, not args.no_header)
    present = {e.section for e in doc.entries}

    gates: List[str] = []
    if args.check and warnings:
        gates.append(f"{len(warnings)} warning(s) under --check")
    if args.max_warnings is not None and len(warnings) > args.max_warnings:
        gates.append(f"{len(warnings)} warnings > --max-warnings {args.max_warnings}")
    if args.require_sections:
        missing = [s for s in args.require_sections.split(",") if s and s not in present]
        if missing:
            gates.append("missing required section(s): " + ", ".join(missing))
    if args.forbid_section:
        bad = [s for s in args.forbid_section.split(",") if s and s in present]
        if bad:
            gates.append("forbidden section(s) present: " + ", ".join(bad))

    if args.json:
        report = {
            "file": args.file,
            "entries": len(doc.entries),
            "sections": sorted(present),
            "invalid_lines": len(doc.invalid_lines),
            "warnings": warnings,
            "ok": not gates,
        }
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)

    if not args.json:
        _write(ini_text, args.file, args.output, args.in_place)

    if gates:
        if not args.quiet:
            for w in warnings:
                print(f"env-to-ini: warning: {w}", file=sys.stderr)
            for g in gates:
                print(f"env-to-ini: {g}", file=sys.stderr)
        return 2

    if warnings and not args.quiet and not args.json:
        for w in warnings:
            print(f"env-to-ini: warning: {w}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
