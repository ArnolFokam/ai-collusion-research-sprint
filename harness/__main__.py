import argparse
import asyncio

from harness.config import Config


def main():
    ap = argparse.ArgumentParser(prog="harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run all missing runs, then report")
    r.add_argument("--config", required=True)
    r.add_argument("--no-report", action="store_true")
    r.add_argument("--yes", action="store_true",
                   help="confirm spending: required for real configs of more than 100 API calls")
    pl = sub.add_parser("plan", help="show runs, API calls and estimated cost; runs nothing")
    pl.add_argument("--config", required=True)
    o = sub.add_parser("one", help="(internal) run a single simulation")
    o.add_argument("--config", required=True)
    o.add_argument("--cond", type=int, required=True)
    o.add_argument("--run", type=int, required=True)
    p = sub.add_parser("report", help="rebuild summary + plots from saved metrics")
    p.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = Config.load(a.config)

    if a.cmd == "one":
        from harness.runner import run_one
        run_one(cfg, a.cond, a.run)
    elif a.cmd == "plan":
        from harness.plan import format_plan, make_plan
        print(format_plan(make_plan(cfg)))
    elif a.cmd == "run":
        from harness.plan import format_plan, make_plan, needs_confirmation
        plan = make_plan(cfg)
        if needs_confirmation(plan, cfg) and not a.yes:
            print(format_plan(plan))
            raise SystemExit("\nThis spends real money. Nothing was started. "
                             "Rerun with --yes to confirm (or use `plan` to inspect).")
        from harness.runner import run_all
        asyncio.run(run_all(cfg, a.config))
        if not a.no_report:
            from harness.report import build
            print("report:", build(cfg))
    else:
        from harness.report import build
        print("report:", build(cfg))


if __name__ == "__main__":
    main()
