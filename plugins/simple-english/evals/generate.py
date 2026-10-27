"""Stage 1: one response per case, trial, and condition. See README.md."""

import argparse
import sys

import common


CONTENT_ERRORS = ("fake-tool-call", "empty-result", "bad-result")


def generate(cases, cfg, trials, budget_usd, out_path, spent_so_far=0.0, call=common.run_claude, retries=2,
             retry_failed=False):
    """Make each missing or out-of-date response. Returns {made, failed, skipped, stopped, spent}.

    A row whose latest try failed on its content (CONTENT_ERRORS) under the current
    input_hash is skipped and counted in `skipped`, because the same input would
    most likely fail the same way and cost the same again. `retry_failed` tries
    those rows again. A timeout or any other failure is always retried.

    `stopped` is False, "budget" when the run cap is reached, or a reason after
    common.STOP_AFTER_FAILURES rows of one condition in a row end failed after
    their retries: "timeouts" when each of those rows ended on a timeout or an
    unpriced failure, else "failures". Each condition keeps its own count,
    because rows run trial, then case, then condition: with 1 count, the other
    conditions' successes would reset it, and a condition that always fails
    would run to the cap. One overall count runs beside them, so a run where
    every call fails stops after 3 rows, not after one condition's 3rd row. A
    row that succeeds resets its condition's count and the overall count. So
    one row whose content always fails is recorded and the stage carries on.
    After a "timeouts" or "failures" stop, `error` holds the last error and
    `condition` names the condition that stopped it, or is None when the
    overall count did.
    """
    texts = {name: common.condition_text(cfg, name) for name in cfg["conditions"]}
    spent = spent_so_far
    made = failed = skipped = 0
    stopped = False
    streaks = {name: common.FailureStreak() for name in cfg["conditions"]}
    overall = common.FailureStreak()
    latest = common.latest(common.read_jsonl(out_path))
    for trial in range(1, trials + 1):
        for case in cases:
            for name in cfg["conditions"]:
                current = common.response_hash(case, cfg, name, texts[name])
                old = latest.get((case["id"], trial, name))
                if old and old.get("input_hash") == current:
                    if old.get("ok"):
                        continue
                    if old.get("error") in CONTENT_ERRORS and not retry_failed:
                        skipped += 1
                        continue
                if budget_usd - spent < common.MIN_CALL_USD:
                    return {"made": made, "failed": failed, "skipped": skipped, "stopped": "budget", "spent": spent}
                cost, estimated, duration = 0.0, False, None
                for _attempt in range(retries + 1):
                    try:
                        result = call(case["prompt"], texts[name], cfg["model"], common.call_budget(budget_usd, spent),
                                      effort=cfg.get("effort"))
                    except Exception as error:
                        result = {"ok": False, "error": repr(error)[:300], "cost_usd": None}
                    attempt_usd, guessed = common.attempt_cost(result)
                    cost += attempt_usd
                    spent += attempt_usd
                    estimated = estimated or guessed
                    duration = common.slowest(duration, result)
                    if result["ok"]:
                        break
                    if budget_usd - spent < common.MIN_CALL_USD:
                        stopped = "budget"
                        break
                row = {"case_id": case["id"], "trial": trial, "condition": name, "ok": result["ok"],
                       "model": cfg["model"], "effort": cfg.get("effort"), "models": result.get("models", []),
                       "cost_usd": cost, "trials": trials, "input_hash": current}
                if estimated:
                    row["cost_estimated"] = True
                if duration is not None:
                    row["duration_ms"] = duration  # the slowest attempt, as the CLI reported it
                if result["ok"]:
                    row["text"] = result["text"]
                    made += 1
                else:
                    row["error"] = result.get("error")
                    failed += 1
                common.append_jsonl(out_path, row)
                reason = streaks[name].add(result["ok"], guessed)
                across = overall.add(result["ok"], guessed)
                if reason or across:
                    return {"made": made, "failed": failed, "skipped": skipped, "stopped": reason or across,
                            "spent": spent, "error": result.get("error"), "condition": name if reason else None}
    return {"made": made, "failed": failed, "skipped": skipped, "stopped": stopped, "spent": spent}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--budget-usd", type=float, required=True,
                        help="cap for the whole run, generation and judging together")
    parser.add_argument("--retry-failed", action="store_true",
                        help="also retry rows that failed on their content (%s)" % ", ".join(CONTENT_ERRORS))
    args = parser.parse_args(argv)
    common.require_claude()
    folder = common.run_dir(args.run_id)
    summary = generate(common.load_cases(), common.load_conditions(), args.trials, args.budget_usd,
                       folder / "responses.jsonl", spent_so_far=common.spent(folder), retry_failed=args.retry_failed)
    print("generate: %d made, %d failed, $%.2f spent in the run folder so far" % (summary["made"], summary["failed"], summary["spent"]))
    if summary.get("skipped"):
        print("generate: skipped %d rows that failed on their content (%s) under the same inputs. "
              "Pass --retry-failed to try them again." % (summary["skipped"], ", ".join(CONTENT_ERRORS)))
    if summary["stopped"] in ("timeouts", "failures"):
        print(common.stop_message("generate", summary))
        return 1
    if summary["stopped"]:
        print("generate: the budget cap is reached, so the run is partial. Raise --budget-usd and rerun to resume.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
