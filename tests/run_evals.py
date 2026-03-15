"""
Model Forge — Eval Runner
Runs structured eval cases from evals/tool_use_cases.json against the model.

Usage:
    python tests/run_evals.py --model toolsmith
"""

import argparse
import json
import sys
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def log(msg, color=""):
    print(f"{color}{msg}{RESET}")


def api_chat(model, messages, tools=None, timeout=180):
    data = {"model": model, "messages": messages, "stream": False, "options": {"num_predict": 300}}
    if tools:
        data["tools"] = tools
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def check_assertion(assertion, result):
    """Check a single assertion against the model result."""
    atype = assertion.get("type")
    message = result.get("message", {})
    content = message.get("content", "").lower()
    tool_calls = message.get("tool_calls", [])

    if atype == "tool_called":
        expected = assertion.get("name")
        actual_names = [tc.get("function", {}).get("name") for tc in tool_calls]
        return expected in actual_names, f"Expected tool '{expected}', got {actual_names}"

    elif atype == "no_tool_called":
        if not tool_calls:
            return True, ""
        names = [tc.get("function", {}).get("name") for tc in tool_calls]
        return False, f"Expected no tool call, got {names}"

    elif atype == "arg_present":
        arg_name = assertion.get("name")
        for tc in tool_calls:
            args = tc.get("function", {}).get("arguments", {})
            if arg_name in args:
                return True, ""
        return False, f"Argument '{arg_name}' not found in tool call args"

    elif atype == "arg_value":
        arg_name = assertion.get("name")
        expected_val = str(assertion.get("value")).lower()
        for tc in tool_calls:
            args = tc.get("function", {}).get("arguments", {})
            if arg_name in args and expected_val in str(args[arg_name]).lower():
                return True, ""
        return False, f"Argument '{arg_name}' not set to '{expected_val}'"

    elif atype == "content_contains":
        expected = assertion.get("value", "").lower()
        if expected in content:
            return True, ""
        return False, f"Content doesn't contain '{expected}': {content[:150]}"

    elif atype == "content_not_contains":
        unexpected = assertion.get("value", "").lower()
        if unexpected not in content:
            return True, ""
        return False, f"Content unexpectedly contains '{unexpected}'"

    else:
        return False, f"Unknown assertion type: {atype}"


def run_eval(model, case):
    """Run a single eval case."""
    name = case.get("name", "unnamed")
    messages = case.get("messages", [])
    tools = case.get("tools", None)
    assertions = case.get("assertions", [])

    result = api_chat(model, messages, tools)
    if "_error" in result:
        return False, f"API error: {result['_error']}"

    all_pass = True
    details = []
    for assertion in assertions:
        ok, detail = check_assertion(assertion, result)
        if not ok:
            all_pass = False
            details.append(detail)

    return all_pass, "; ".join(details) if details else ""


def main():
    parser = argparse.ArgumentParser(description="Model Forge eval runner")
    parser.add_argument("--model", default="toolsmith", help="Model to evaluate")
    parser.add_argument("--evals", default="evals/tool_use_cases.json", help="Eval cases file")
    args = parser.parse_args()

    log(f"\n=== Model Forge Evals ===", CYAN)
    log(f"Model: {args.model}")

    try:
        with open(args.evals, "r") as f:
            data = json.load(f)
    except Exception as e:
        log(f"ERROR: Cannot load evals from {args.evals}: {e}", RED)
        sys.exit(1)

    cases = data.get("test_cases", [])
    log(f"Cases: {len(cases)}\n")

    passed = 0
    failed = 0
    results = []

    for case in cases:
        name = case.get("name", "unnamed")
        ok, detail = run_eval(args.model, case)
        if ok:
            passed += 1
            log(f"  PASS: {name}", GREEN)
            results.append({"name": name, "status": "pass"})
        else:
            failed += 1
            log(f"  FAIL: {name} — {detail}", RED)
            results.append({"name": name, "status": "fail", "detail": detail})

    log(f"\n=== Eval Results ===", CYAN)
    log(f"Passed: {passed}/{len(cases)}", GREEN if failed == 0 else "")
    log(f"Failed: {failed}/{len(cases)}", RED if failed > 0 else "")

    # Write results
    out_file = "evals/eval_results.json"
    try:
        with open(out_file, "w") as f:
            json.dump({
                "model": args.model,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "passed": passed,
                "failed": failed,
                "total": len(cases),
                "results": results
            }, f, indent=2)
        log(f"\nResults written to {out_file}")
    except Exception as e:
        log(f"Could not write results: {e}", YELLOW)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
