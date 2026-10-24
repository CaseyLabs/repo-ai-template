"""Disposable CLI tests for the project context, Markdown link and prose helpers."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS=Path(__file__).resolve().parents[1]
CONTEXT=TOOLS/"project-context.py"
CHECK=TOOLS/"check-doc-links.py"
PROSE=TOOLS/"check-prose.py"


class Checkout(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="project docs ")
        self.root=Path(self.tmp.name)/"repo with spaces"
        self.root.mkdir()
        self.run_git("init","-q")
        self.run_git("config","user.email","test@example.invalid")
        self.run_git("config","user.name","Fixture")
        (self.root/"PLAN.md").write_text("# Project roadmap\n\n## Portfolio\nCandidates factual.\n\n## Progress\nNo automatic selection.\n\n## MAINT — Maintenance\nIntro facts.\nSibling project decision.\n\n### MAINT-5 — Helpers\n**Scope:** selected only.\n**Issues:** [F5b-3](ISSUES.md#f5b-3).\n**Checkpoint:** [custom](docs/plans/custom-checkpoint.md).\n\n### MAINT-50 — Similar ID\nMust not match.\n\n### MAINT-6 — Sibling milestone\nMust not appear.\n",encoding="utf-8")
        (self.root/"ISSUES.md").write_text("# Issues\n\n<a id=\"f5b-3\"></a>\n### F5b-3 — Rollback progress promise\nOnly this linked issue.\n\n<a id=\"other\"></a>\n### Other — Unlinked\nMust not appear.\n",encoding="utf-8")
        (self.root/"docs/plans").mkdir(parents=True)
        (self.root/"docs/plans/maint-5.md").write_text("# Default checkpoint\nMust not override an explicit link.\n",encoding="utf-8")
        (self.root/"docs/plans/custom-checkpoint.md").write_text("# Checkpoint\nCustom linked checkpoint.\n",encoding="utf-8")
        (self.root/"README.md").write_text("# Readme\n",encoding="utf-8")
        self.run_git("add","."); self.run_git("commit","-qm","fixture")

    def tearDown(self): self.tmp.cleanup()

    def run_git(self,*args):
        return subprocess.run(["git",*args],cwd=self.root,check=True,capture_output=True,text=True)

    def cli(self, script, *args, cwd=None):
        return subprocess.run([sys.executable,str(script),*args],cwd=cwd or self.root,capture_output=True,text=True)

    def prose_findings(self, name):
        r=self.cli(PROSE,name,"--json")
        self.assertEqual(r.returncode,0,r.stderr)
        return [(f["line"],f["words"]) for f in json.loads(r.stdout)["findings"]]

    def test_context_scope_linked_files_and_path_spaces(self):
        r=self.cli(CONTEXT,"MAINT-5","--json")
        self.assertEqual(r.returncode,0,r.stderr)
        data=json.loads(r.stdout)
        rendered="\n".join(x for sec in data["sections"] for x in sec["lines"])
        self.assertIn("MAINT-5",rendered); self.assertIn("F5b-3",rendered); self.assertIn("Custom linked checkpoint",rendered)
        self.assertNotIn("Candidates factual",rendered)
        self.assertNotIn("Sibling milestone",rendered); self.assertNotIn("MAINT-50",rendered)
        self.assertNotIn("Must not appear",rendered); self.assertNotIn("Default checkpoint",rendered)
        self.assertIn("repo with spaces",data["repository"])

    def test_portfolio_view_and_line_limit(self):
        r=self.cli(CONTEXT,"--json","--max-lines","5")
        self.assertEqual(r.returncode,0,r.stderr)
        data=json.loads(r.stdout)
        self.assertTrue(data["truncated"])
        self.assertTrue(data["follow_up"])
        all_text="\n".join(line for s in data["sections"] for line in s["lines"])
        self.assertIn("Portfolio",all_text)
        self.assertNotIn("MAINT — Maintenance",all_text)

    def test_milestone_id_does_not_match_longer_hyphenated_id(self):
        plan=self.root/"PLAN.md"
        with plan.open("a",encoding="utf-8") as stream:
            stream.write("\n### MAINT-5-extra — Separate milestone\nUnselected detail.\n")
        result=self.cli(CONTEXT,"MAINT-5","--json")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn("Unselected detail",result.stdout)

    def test_fenced_comment_does_not_end_milestone_section(self):
        plan=self.root/"PLAN.md"
        text=plan.read_text(encoding="utf-8").replace("**Scope:** selected only.\n","**Scope:** selected only.\n```bash\n# run tests\n```\nAcceptance after the fence.\n")
        plan.write_text(text,encoding="utf-8")
        result=self.cli(CONTEXT,"MAINT-5","--json")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("Acceptance after the fence",result.stdout)
        self.assertIn("Rollback progress promise",result.stdout)

    def test_heading_slugs_match_github(self):
        sys.path.insert(0,str(TOOLS))
        from project_markdown import anchors
        found=anchors("# No active milestone / handoff\n## A & B\n")
        self.assertEqual(found,{"no-active-milestone--handoff","a--b"})

    def test_context_anchor_range_numbers_slugs_like_link_checker(self):
        import importlib.util
        sys.path.insert(0,str(TOOLS))
        from project_markdown import anchors
        spec=importlib.util.spec_from_file_location("project_context",CONTEXT)
        context=importlib.util.module_from_spec(spec); spec.loader.exec_module(context)
        text="# A\none\n# A\ntwo\n# A-1\nthree\n```\n# fenced\n```\nSetext\n======\nfour\n"
        self.assertEqual(anchors(text),{"a","a-1","a-1-1","setext"})
        lines=text.splitlines()
        self.assertEqual(context.anchor_range(lines,"a-1-1"),(4,9))
        self.assertEqual(context.anchor_range(lines,"setext"),(9,len(lines)))
        self.assertIsNone(context.anchor_range(lines,"fenced"))

    def test_explicit_anchor_on_heading_line_and_quoted_example(self):
        import importlib.util
        sys.path.insert(0,str(TOOLS))
        from project_markdown import anchors
        spec=importlib.util.spec_from_file_location("project_context",CONTEXT)
        context=importlib.util.module_from_spec(spec); spec.loader.exec_module(context)
        text="# Issues\nUse `<a id=\"co2\"></a>` anchors.\n## CO1 — One <a id=\"co1\"></a>\none\n## CO3 — Three\nthree\n"
        lines=text.splitlines()
        self.assertEqual(context.anchor_range(lines,"co1"),(2,4))
        self.assertIsNone(context.anchor_range(lines,"co2"))
        self.assertNotIn("co2",anchors(text))

    def test_missing_plan_and_id_fail(self):
        self.assertNotEqual(self.cli(CONTEXT,"--plan","missing.md").returncode,0)
        self.assertNotEqual(self.cli(CONTEXT,"missing-id").returncode,0)

    def test_missing_referenced_issue_or_checkpoint_is_reported(self):
        plan=self.root/"PLAN.md"
        baseline=plan.read_text(encoding="utf-8")
        plan.write_text(baseline.replace("ISSUES.md#f5b-3","ISSUES.md#missing-issue"),encoding="utf-8")
        r=self.cli(CONTEXT,"MAINT-5")
        self.assertEqual(r.returncode,2)
        self.assertIn("issue anchor #missing-issue not found",r.stderr)
        plan.write_text(baseline.replace("docs/plans/custom-checkpoint.md","docs/plans/missing-checkpoint.md"),encoding="utf-8")
        r=self.cli(CONTEXT,"MAINT-5")
        self.assertEqual(r.returncode,2)
        self.assertIn("referenced checkpoint is missing",r.stderr)

    def test_context_works_inside_worktree_with_exact_milestone_id(self):
        wt=Path(self.tmp.name)/"worktree path with spaces"
        self.run_git("worktree","add","-qb","fixture-wt",str(wt))
        r=self.cli(CONTEXT,"MAINT-5","--json",cwd=wt)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("MAINT-5",r.stdout)
        self.assertNotIn("MAINT-50",r.stdout)

    def test_prose_reports_long_sentences_only_when_strict_fails(self):
        long=" ".join(["word"]*30)
        (self.root/"guide.md").write_text(
            "---\ndescription: "+long+"\n---\n# "+long+"\n\n"
            "Short one. `code` starts this "+" ".join(["sentence"]*24)+".\n\n"
            "- Item one is short.\n- Item "+long+".\n\n"
            "```\n"+long+"\n```\n| "+long+" |\n",encoding="utf-8")
        self.assertEqual(self.prose_findings("guide.md"),[(6,27),(9,31)])
        self.assertEqual(self.cli(PROSE,"guide.md","--strict").returncode,1)
        self.assertEqual(self.cli(PROSE,"guide.md","--strict","--max-words","40").returncode,0)
        self.assertEqual(self.cli(PROSE,"README.md","--strict").returncode,0)

    def test_prose_joins_wrapped_blockquotes_and_rejects_missing_paths(self):
        (self.root/"quote.md").write_text("---\r\ntitle: "+" ".join(["word"]*30)+"\r\n---\r\n"
            "> "+" ".join(["word"]*15)+"\n> "+" ".join(["word"]*15)+".\n",encoding="utf-8")
        self.assertEqual(self.prose_findings("quote.md"),[(4,30)])
        r=self.cli(PROSE,"missing.md")
        self.assertEqual(r.returncode,2)
        self.assertIn("does not exist",r.stderr)

    def test_prose_keeps_wrapped_autolinks_and_drops_setext_headings(self):
        half=" ".join(["word"]*14)
        (self.root/"wrap.md").write_text(
            half+"\n<https://example.com> and\n#123 "+half+".\n\n"
            "Setext "+" ".join(["title"]*30)+"\n---\n\n"
            "Run it. 3 "+" ".join(["retries"]*20)+" follow. `` `a` `` "+" ".join(["x"]*26)+".\n",encoding="utf-8")
        self.assertEqual(self.prose_findings("wrap.md"),[(1,30),(8,27)])

    def test_markdown_frontmatter_is_not_a_setext_heading(self):
        (self.root/"skill.md").write_text("---\nname: x\ndescription: Do things\n---\n\n# Real\n",encoding="utf-8")
        (self.root/"links.md").write_text("[ok](skill.md#real)\n[fake](skill.md#description-do-things)\n",encoding="utf-8")
        r=self.cli(CHECK,"links.md","--json")
        self.assertEqual(r.returncode,1,r.stderr)
        self.assertEqual([e["line"] for e in json.loads(r.stdout)["errors"]],[2])

    def test_markdown_links_paths_anchors_duplicates_and_root_paths(self):
        docs=self.root/"docs"; docs.mkdir(exist_ok=True)
        target=docs/"target page.md"
        target.write_text("<a id=\"old-name\"></a>\n# Repeat\n# Repeat\n",encoding="utf-8")
        (docs/"user-guide").mkdir()
        (docs/"user-guide/index.md").write_text("# Home\n",encoding="utf-8")
        (docs/"user-guide/route.md").write_text("# Café `code`\n\nSetext title\n-------------\n",encoding="utf-8")
        source=docs/"source.md"
        source.write_text("""[encoded](target%20page.md#repeat-1)
[raw spaces](target page.md#repeat)
[bad](missing.md)
[bad anchor](target%20page.md#absent)
[root dir](/docs/)
[root path](/docs/user-guide/route.md#café-code)
[setext](/docs/user-guide/route.md#setext-title)
[local](target%20page.md#old-name)
`[code](nope.md)`
```md
[fenced](nope.md)
```
[reference][ok]
[ok]: <target page.md#repeat>
""",encoding="utf-8")
        r=self.cli(CHECK,"docs/source.md","--json")
        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
        self.assertEqual(json.loads(r.stdout)["error_count"],2,r.stdout)
        self.assertIn("missing link target",r.stdout)
        self.assertIn("missing anchor #absent",r.stdout)
        self.assertNotIn("nope.md",r.stdout)
        self.assertNotIn("repeat-1",r.stdout)

    def test_link_checker_missing_explicit_source_and_bounded_report(self):
        missing=self.cli(CHECK,"missing source.md")
        self.assertEqual(missing.returncode,1)
        self.assertIn("explicit Markdown source does not exist",missing.stdout)
        source=self.root/"lots.md"
        source.write_text("[a](missing-a.md)\n[b](missing-b.md)\n",encoding="utf-8")
        report=self.root/"full report.json"
        r=self.cli(CHECK,"--json","--max-errors","1","--json-output",str(report),"lots.md")
        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
        brief=json.loads(r.stdout)
        full=json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(len(brief["errors"]),1)
        self.assertTrue(brief["errors_truncated"])
        self.assertEqual(full["error_count"],2)

    def test_explicit_sources_resolve_from_invocation_directory(self):
        docs=self.root/"docs"
        (docs/"nested.md").write_text("[root](../README.md#readme)\n[dir](plans/)\n",encoding="utf-8")
        result=self.cli(CHECK,"nested.md",cwd=docs)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_all_checks_tracked_and_untracked_markdown(self):
        (self.root/"docs/plans/old.md").write_text("[bad](gone.md)\n",encoding="utf-8")
        self.run_git("add","."); self.run_git("commit","-qm","old")
        (self.root/"new.md").write_text("[bad](absent.md)\n",encoding="utf-8")
        self.assertEqual(self.cli(CHECK,"--changed").stdout.count("missing link target"),1)
        r=self.cli(CHECK,"--all","--json")
        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
        files={e["file"] for e in json.loads(r.stdout)["errors"]}
        self.assertEqual(files,{"docs/plans/old.md","new.md"})

    def test_json_report_refuses_existing_file(self):
        output=Path(self.tmp.name)/"existing report.json"
        output.write_text("preserve me\n",encoding="utf-8")
        result=self.cli(CHECK,"README.md","--json-output",str(output))
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(output.read_text(),"preserve me\n")

    def test_changed_includes_untracked_markdown_by_default(self):
        (self.root/"untracked file.md").write_text("[broken](absent.md)\n",encoding="utf-8")
        r=self.cli(CHECK)
        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
        self.assertIn("untracked file.md:1",r.stdout)

    def test_changed_union_with_explicit_path(self):
        (self.root/"changed.md").write_text("[bad](missing.md)\n",encoding="utf-8")
        (self.root/"specified.md").write_text("[bad](missing-too.md)\n",encoding="utf-8")
        r=self.cli(CHECK,"--changed","specified.md")
        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
        self.assertIn("changed.md:1",r.stdout)
        self.assertIn("specified.md:1",r.stdout)


if __name__=="__main__": unittest.main()
