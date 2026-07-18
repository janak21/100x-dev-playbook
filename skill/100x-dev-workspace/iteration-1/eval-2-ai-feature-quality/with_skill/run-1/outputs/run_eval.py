#!/usr/bin/env python3
"""
run_eval.py - eval runner for the support-email -> 3-bullet summary prompt.

Loads PROMPT.txt (your prompt, with an {{EMAIL}} placeholder), runs every case in
cases.json through the generator model, then scores each output two ways:

  1. Mechanical checks (deterministic code): bullet count, bullet length,
     required terms present, forbidden strings absent.
  2. LLM judge (different model, fresh context, blind to your prompt): grades
     against rubric.md + the case's pass_criterion.

A case passes only if BOTH layers pass. Prints the rate and the failure list,
and writes results_<timestamp>.json for the audit trail.

Usage:
  export ANTHROPIC_API_KEY=sk-ant-...
  pip install anthropic
  python run_eval.py                  # full run
  python run_eval.py --no-judge      # mechanical checks only
  python run_eval.py --cases 16,19   # subset while debugging (final call is always all 20)

Iteration rule: change ONE thing in PROMPT.txt, rerun ALL cases. Every production
failure becomes a new case in cases.json.
"""

import argparse, datetime, json, os, re, sys

GENERATOR_MODEL = os.environ.get("EVAL_GENERATOR_MODEL", "claude-sonnet-4-5")
JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-haiku-4-5")  # different model = fewer shared blind spots
MAX_BULLET_WORDS = 30
HERE = os.path.dirname(os.path.abspath(__file__))

BULLET_RE = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+(.*\S)\s*$")


def load_prompt():
    with open(os.path.join(HERE, "PROMPT.txt"), encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    prompt = "".join(lines).strip()
    if "{{EMAIL}}" not in prompt:
        sys.exit("PROMPT.txt must contain the {{EMAIL}} placeholder.")
    return prompt


def load_cases(subset):
    with open(os.path.join(HERE, "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    if subset:
        wanted = {int(x) for x in subset.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    return cases


def call_model(client, model, prompt_text):
    resp = client.messages.create(
        model=model, max_tokens=1024,
        messages=[{"role": "user", "content": prompt_text}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def extract_bullets(output):
    return [m.group(1) for line in output.splitlines() if (m := BULLET_RE.match(line))]


def mechanical_check(case, output):
    """Return list of failure strings (empty = pass)."""
    fails, low = [], output.lower()
    checks = case.get("checks", {})
    if not case.get("format_exempt"):
        bullets = extract_bullets(output)
        if len(bullets) != 3:
            fails.append(f"format: expected exactly 3 bullets, found {len(bullets)}")
        for i, b in enumerate(bullets, 1):
            if len(b.split()) > MAX_BULLET_WORDS:
                fails.append(f"format: bullet {i} has {len(b.split())} words (max {MAX_BULLET_WORDS})")
    for group in checks.get("must_mention_any", []):
        if not any(term.lower() in low for term in group):
            fails.append(f"coverage: none of {group} mentioned")
    for bad in checks.get("must_not_contain", []):
        if bad.lower() in low:
            fails.append(f"safety: forbidden string present: {bad!r}")
    return fails


JUDGE_TEMPLATE = """You are grading the output of an email-summarization system. You do not know \
which prompt produced it; grade only what is in front of you, strictly against the rubric.

<rubric>
{rubric}
</rubric>

<case_pass_criterion>
{criterion}
</case_pass_criterion>

<input_email>
Subject: {subject}

{body}
</input_email>

<output_to_grade>
{output}
</output_to_grade>

Apply the rubric. Any single violation is a FAIL; no partial credit. Respond with exactly:
VERDICT: PASS or VERDICT: FAIL
REASON: <one line>"""


def judge_check(client, rubric, case, output):
    reply = call_model(client, JUDGE_MODEL, JUDGE_TEMPLATE.format(
        rubric=rubric, criterion=case["pass_criterion"],
        subject=case["subject"], body=case["body"] or "(empty body)", output=output))
    m = re.search(r"VERDICT:\s*(PASS|FAIL)", reply, re.I)
    verdict = m.group(1).upper() if m else "FAIL"
    reason_m = re.search(r"REASON:\s*(.*)", reply)
    return verdict == "PASS", (reason_m.group(1).strip() if reason_m else reply[:200])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge (mechanical only)")
    ap.add_argument("--cases", help="comma-separated case ids to run, e.g. 16,19")
    args = ap.parse_args()

    try:
        import anthropic
    except ImportError:
        sys.exit("pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first.")
    client = anthropic.Anthropic()

    prompt = load_prompt()
    cases = load_cases(args.cases)
    with open(os.path.join(HERE, "rubric.md"), encoding="utf-8") as f:
        rubric = f.read()

    results, passes = [], 0
    for case in cases:
        email = f"Subject: {case['subject']}\n\n{case['body']}"
        output = call_model(client, GENERATOR_MODEL, prompt.replace("{{EMAIL}}", email))
        mech_fails = mechanical_check(case, output)
        judge_pass, judge_reason = (True, "skipped")
        if not args.no_judge:
            judge_pass, judge_reason = judge_check(client, rubric, case, output)
        ok = not mech_fails and judge_pass
        passes += ok
        results.append({
            "id": case["id"], "slug": case["slug"], "category": case["category"],
            "pass": ok, "mechanical_failures": mech_fails,
            "judge": {"pass": judge_pass, "reason": judge_reason}, "output": output,
        })
        print(f"[{'PASS' if ok else 'FAIL'}] #{case['id']:>2} {case['slug']}"
              + ("" if ok else f"  -> {'; '.join(mech_fails) or judge_reason}"))

    total = len(cases)
    safety = [r for r in results if r["id"] in (15, 16, 19)]
    safety_ok = all(r["pass"] for r in safety) if safety else None
    print(f"\nRate: {passes}/{total} ({100 * passes // max(total, 1)}%)"
          + (f" | safety-critical: {sum(r['pass'] for r in safety)}/{len(safety)}" if safety else ""))
    if passes < total:
        print("Failures are the product - each names the constraint to tighten in PROMPT.txt.")
        print("Fix ONE thing, then rerun ALL cases.")
    if safety and not safety_ok:
        print("DO NOT roll out: a safety-critical case (15/16/19) is failing.")
    if not args.no_judge:
        print("Reminder: spot-check ~20% of judge verdicts yourself (see rubric.md).")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(HERE, f"results_{stamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"generator_model": GENERATOR_MODEL, "judge_model": JUDGE_MODEL,
                   "rate": f"{passes}/{total}", "results": results}, f, indent=2, ensure_ascii=False)
    print(f"Full outputs + verdicts written to {out_path}")


if __name__ == "__main__":
    main()
