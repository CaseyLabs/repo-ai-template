#!/usr/bin/env python3
"""Check local links in changed Markdown files, all tracked Markdown (--all), or explicit paths."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from project_common import WorkflowError, repository
from project_markdown import add_selection_args, anchors, is_markdown, links, resolve_target, select_markdown


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    add_selection_args(ap)
    ap.add_argument("--json",action="store_true")
    ap.add_argument("--json-output", help="write the complete JSON report to this path")
    ap.add_argument("--max-errors",type=int,default=50)
    args=ap.parse_args()
    try:
        root=repository()
        if args.max_errors < 0: raise ValueError("--max-errors must be nonnegative")
        explicit,names=select_markdown(root,args.paths,args.all,args.changed,args.base)
        errors=[]
        for name in sorted(names):
            source=(root/name).resolve()
            if not is_markdown(source.name): continue
            if not source.exists():
                if name in explicit: errors.append({"file":name,"line":1,"message":"explicit Markdown source does not exist"})
                continue
            try: body=source.read_text(encoding="utf-8")
            except (OSError,UnicodeError) as e:
                errors.append({"file":name,"line":1,"message":f"cannot read Markdown: {e}"}); continue
            for line,dest in links(body):
                target,anchor=resolve_target(source,dest,root)
                if target is None: continue
                if not target.exists():
                    errors.append({"file":name,"line":line,"message":f"missing link target: {dest}"}); continue
                if anchor and is_markdown(target.name):
                    try: target_anchors=anchors(target.read_text(encoding="utf-8"))
                    except (OSError,UnicodeError): target_anchors=set()
                    if anchor not in target_anchors:
                        errors.append({"file":name,"line":line,"message":f"missing anchor #{anchor} in {target.relative_to(root) if target.is_relative_to(root) else target}"})
        report={"root":str(root),"checked":sorted(names),"error_count":len(errors),"errors":errors}
        if args.json_output:
            with Path(args.json_output).open("x",encoding="utf-8") as stream:
                stream.write(json.dumps(report,indent=2)+"\n")
        shown=errors[:args.max_errors]
        if args.json: print(json.dumps({**report,"errors":shown,"errors_truncated":len(shown)<len(errors)},indent=2))
        else:
            for e in shown: print(f"{e['file']}:{e['line']}: {e['message']}")
            if len(shown)<len(errors): print(f"... {len(errors)-len(shown)} additional errors; see --json-output report.")
            print(f"Checked {len(names)} Markdown path(s); {len(errors)} error(s).")
        return 1 if errors else 0
    except (WorkflowError,OSError,ValueError) as e:
        print(f"check-doc-links: {e}",file=sys.stderr); return 2


if __name__=="__main__": raise SystemExit(main())
