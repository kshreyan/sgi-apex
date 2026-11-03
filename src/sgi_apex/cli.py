"""`sgi` command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sgi_apex import config


def _site():
    from sgi_apex.reporting import brief
    path = config.SITE / "data" / "apex.json"
    if not path.exists():
        from sgi_apex.reporting import build
        return build.run()
    return brief.load_site()


def cmd_run(_):
    from sgi_apex.reporting import brief, build
    site = build.run()
    print(brief.write(site))


def cmd_brief(_):
    from sgi_apex.reporting import brief
    print(brief.write(_site()))


def cmd_registry(_):
    from sgi_apex.entities import registry
    reg = registry.load_registry()
    problems = registry.reconcile(reg, registry.load_programmes())
    registry.write_master(reg)
    print(reg[["entity_id", "legal_name", "entity_type", "campus", "confidence"]].to_string(index=False))
    print("\nUnverified / conflicting:")
    print(registry.unverified_items(reg).to_string(index=False))
    print("\nReconciliation:", "OK" if not problems else problems)


def cmd_ingest(args):
    from sgi_apex.data import pipeline
    if not args.file:
        df = pipeline.to_silver(pipeline.ingest())
        print(f"silver rows: {len(df):,} ({df.programme_id.nunique()} programmes, source={df.source.unique().tolist()})")
        return
    import pandas as pd

    from sgi_apex.data import adapters, quality
    from sgi_apex.entities import registry
    try:
        funnel, issues, sha = pipeline.ingest_file(args.file, args.live_year)
    except adapters.IngestError as e:
        print(adapters.issues_frame(e.issues).to_string(index=False))
        sys.exit(f"\nINGEST BLOCKED — {e}")
    if args.finals:
        issues += adapters.reconcile_finals(funnel, pd.read_csv(args.finals), registry.load_programmes(), args.tol)
    intake = registry.load_programmes().set_index("programme_id").sanctioned_intake
    dq = []
    for pid, g in funnel.groupby("programme_id"):
        year = int(g.admission_year.max())
        week = int(g[g.admission_year == year].cycle_week.max())
        s = quality.score_programme(g, int(intake[pid]), year, week)
        dq.append({"programme_id": pid, "year": year, "week": week, "score": s["score"], "hold": s["hold"]})
    dq = pd.DataFrame(dq)
    report = adapters.report_markdown(args.file, sha, funnel, issues, dq)
    out = config.DATA / "reports" / f"ingest_{sha[:12]}.md"  # data/ is git-ignored: real figures never get committed
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(report)
    errors = [i for i in issues if i.severity == "ERROR"]
    if errors:
        sys.exit(f"INGEST BLOCKED — {len(errors)} error(s). Report: {out}")
    if args.dry_run:
        print(f"dry run: silver not written. Report: {out}")
        return
    pipeline.to_silver(funnel)
    print(f"silver written: {pipeline.SILVER_ADMISSIONS} · report: {out}")


def cmd_forecast(args):
    if args.target != "admissions":
        sys.exit(f"forecast target '{args.target}' is not built yet (milestone 1 = admissions). See docs/roadmap in README.")
    site = _site()
    print(f"{'programme':<26}{'campus':<9}{'to date':>8}{'median':>8}{'90% interval':>16}{'P(target)':>11}  status")
    for p in site["programmes"]:
        print(f"{p['programme']:<26}{p['campus']:<9}{p['enrolled_to_date']:>8}{p['median']:>8.0f}"
              f"{p['q05']:>8.0f}–{p['q95']:<7.0f}{p['p_meet_target']:>10.0%}  {p['status']}")


def cmd_risks(_):
    site = _site()
    for pid in site["attention"]:
        p = next(x for x in site["programmes"] if x["programme_id"] == pid)
        print(f"{p['status']:<6}{p['programme']} ({p['campus']}): P(target)={p['p_meet_target']:.0%}")


def cmd_decisions(_):
    from sgi_apex.decisions import register
    for d in register.current().values():
        print(json.dumps({k: d.get(k) for k in ("decision_id", "status", "recommended_action", "confidence",
                                                 "decision_owner", "deadline")}))


def cmd_backtest(_):
    site = _site()
    sel = site["backtest"]["selection"]
    print("roles:", sel["roles"])
    print("mean CRPS/intake (validation):", sel["crps_by_model"])


def cmd_todo(name):
    def f(_):
        sys.exit(f"`sgi {name}` is planned for a later milestone — see README 'Roadmap'.")
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sgi", description="SGI APEX chairman intelligence system")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="run the full milestone-1 loop and build site data").set_defaults(fn=cmd_run)
    sub.add_parser("chairman-brief").set_defaults(fn=cmd_brief)
    sub.add_parser("registry", help="validate and print the entity registry").set_defaults(fn=cmd_registry)
    ing = sub.add_parser("ingest", help="synthetic demo data, or --file an admissions-office export")
    ing.add_argument("--file", type=Path, help="CSV/XLSX export (see docs/data_ingest.md)")
    ing.add_argument("--finals", type=Path, help="CSV of programme_id,admission_year,final_enrolled to reconcile")
    ing.add_argument("--tol", type=int, default=1, help="reconciliation tolerance per institution-year")
    ing.add_argument("--live-year", type=int, default=config.LIVE_YEAR, help="cycle still in progress")
    ing.add_argument("--dry-run", action="store_true", help="validate and report only")
    ing.set_defaults(fn=cmd_ingest)
    f = sub.add_parser("forecast")
    f.add_argument("target", choices=["admissions", "cash"])
    f.set_defaults(fn=cmd_forecast)
    sub.add_parser("risks").set_defaults(fn=cmd_risks)
    sub.add_parser("decisions").set_defaults(fn=cmd_decisions)
    sub.add_parser("backtest").set_defaults(fn=cmd_backtest)
    for name in ("institution-health", "simulate", "benchmark", "expansion-screen"):
        sub.add_parser(name, help="planned").set_defaults(fn=cmd_todo(name))
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
