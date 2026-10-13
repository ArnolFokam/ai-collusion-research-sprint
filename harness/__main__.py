import argparse
import asyncio

from harness.config import Config


def main():
    ap = argparse.ArgumentParser(prog="harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run all missing runs, then report")
    r.add_argument("--config", required=True)
    r.add_argument("--no-report", action="store_true")
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
    elif a.cmd == "run":
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
