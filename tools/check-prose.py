#!/usr/bin/env python3
"""Report long sentences in changed Markdown files, all tracked Markdown (--all), or explicit paths.

Advisory by default: it prints findings and exits 0 unless --strict is given.
See CONTRIBUTING.md#writing-style for the limits.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from project_common import WorkflowError, repository
from project_markdown import add_selection_args, mask_code, mask_frontmatter, select_markdown

QUOTE=re.compile(r"^\s*(?:>\s?)+")
BLOCK_START=re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
# ATX headings, tables, HTML block tags and thematic breaks; not autolinks or "#123".
SKIP=re.compile(r"^\s*(?:#{1,6}(?:\s|$)|\||<(?:/?[A-Za-z][\w-]*(?:[\s/>]|$)|!--)|(?:[-*_]\s*){3,}$)")
SETEXT=re.compile(r"^\s{0,3}(?:=+|-+)\s*$")
SENTENCE_END=re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[*_])")
WORD=re.compile(r"[\w][\w'’/-]*")
LINK=re.compile(r"!?\[([^]]*)\]\([^)]*\)")
HTML_TAG=re.compile(r"<[^>]+>")


def units(text: str):
    """Yield (line, text) for each paragraph or list item, without frontmatter or fenced code."""
    current,start=[],0
    # Inline code counts as one word.
    for number,line in enumerate(mask_code(mask_frontmatter(text),inline="Code").splitlines(),1):
        # Every blockquote line carries the marker, so strip it before grouping lines.
        line=QUOTE.sub("",line)
        # A setext underline turns the paragraph above it into a heading, which is not prose.
        if SETEXT.match(line) and current:
            current=[]; continue
        if not line.strip() or SKIP.match(line):
            if current: yield start," ".join(current)
            current=[]; continue
        if BLOCK_START.match(line) and current:
            yield start," ".join(current); current=[]
        if not current: start=number
        current.append(BLOCK_START.sub("",line).strip())
    if current: yield start," ".join(current)


def sentences(text: str):
    for line,unit in units(text):
        unit=HTML_TAG.sub("",LINK.sub(r"\1",unit))
        for sentence in SENTENCE_END.split(unit):
            yield line,sentence.strip(),len(WORD.findall(sentence))


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    add_selection_args(ap)
    ap.add_argument("--max-words",type=int,default=25,help="report sentences longer than this (default 25)")
    ap.add_argument("--strict",action="store_true",help="exit 1 when any sentence is too long")
    ap.add_argument("--json",action="store_true")
    args=ap.parse_args()
    try:
        root=repository()
        if args.max_words < 1: raise ValueError("--max-words must be positive")
        explicit,names=select_markdown(root,args.paths,args.all,args.changed,args.base)
        findings,errors=[],[]
        for name in sorted(names):
            source=root/name
            if not source.is_file():
                if name in explicit: errors.append(f"{name}: explicit Markdown source does not exist")
                continue
            try: body=source.read_text(encoding="utf-8")
            except (OSError,UnicodeError) as e:
                errors.append(f"{name}: cannot read Markdown: {e}"); continue
            for line,sentence,words in sentences(body):
                if words > args.max_words:
                    findings.append({"file":name,"line":line,"words":words,"sentence":sentence})
        for error in errors: print(f"check-prose: {error}",file=sys.stderr)
        if args.json: print(json.dumps({"checked":sorted(names),"max_words":args.max_words,"findings":findings},indent=2))
        else:
            for f in findings:
                preview=" ".join(f["sentence"].split()[:10])
                print(f"{f['file']}:{f['line']}: {f['words']} words: {preview} ...")
            print(f"Checked {len(names)} Markdown path(s); {len(findings)} sentence(s) over {args.max_words} words.")
        if errors: return 2
        return 1 if findings and args.strict else 0
    except (WorkflowError,OSError,UnicodeError,ValueError) as e:
        print(f"check-prose: {e}",file=sys.stderr); return 2


if __name__=="__main__": raise SystemExit(main())
