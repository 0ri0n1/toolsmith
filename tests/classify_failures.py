#!/usr/bin/env python3
"""
Model Forge — Failure Classifier
Takes smoke test or eval results JSON, classifies each failure by type,
and returns suggested fixes for the model-forge retry loop.

Usage:
    python tests/classify_failures.py tests/smoke_results.json
    python tests/classify_failures.py evals/eval_results.json --verbose
    python tests/classify_failures.py tests/smoke_results.json evals/eval_results.json

Output: JSON to stdout with classified failures and suggested fixes.
"""

import argparse
import json
import sys

# Failure types and their fix strategies
FAILURE_TYPES = {
    "wrong_tool": {
        "description": "Model called the wrong tool",
        "fixable_by": "model",
        "fix": "Adjust system prompt tool descriptions; add negative examples showing which tool NOT to use for this query"
    },
    "bad_args": {
        "description": "Tool called correctly but arguments are malformed or missing",
        "fixable_by": "model",
        "fix": "Adjust tool schema descriptions; add parameter examples to system prompt"
    },
    "no_tool_call": {
        "description": "Model answered in prose instead of calling a tool",
        "fixable_by": "model",
        "fix": "Strengthen 'always use tools' instruction in system prompt; lower temperature"
    },
    "hallucinated_tool": {
        "description": "Model called a tool that doesn't exist",
        "fixable_by": "model",
        "fix": "Add explicit 'only use these tools: [list]' constraint to system prompt"
    },
    "tool_error": {
        "description": "Tool was called correctly but the tool itself errored",
        "fixable_by": "tool",
        "fix": "Check tool server implementation — this is NOT a model issue"
    },
    "truncated": {
        "description": "Response was cut off mid-generation",
        "fixable_by": "model",
        "fix": "Increase num_predict or num_ctx parameters in Modelfile"
    },
    "wrong_content": {
        "description": "Model response content didn't match expected values",
        "fixable_by": "model",
        "fix": "Adjust system prompt to emphasize using tool data in responses; add grounding instructions"
    },
    "unknown": {
        "description": "Failure couldn't be classified",
        "fixable_by": "unknown",
        "fix": "Manual investigation required"
    }
}


def classify_smoke_failure(test_result):
    """Classify a single smoke test failure."""
    name = test_result.get("test", "")
    detail = test_result.get("detail", "")
    detail_lower = detail.lower()

    # Tool call format failures
    if "tool call" in name.lower() or "tool call format" in name.lower():
        if "no tool call" in detail_lower or "no tool call produced" in detail_lower:
            return "no_tool_call"
        if "wrong function name" in detail_lower:
            return "wrong_tool"
        if "missing" in detail_lower and "arg" in detail_lower:
            return "bad_args"
        if "content instead of structured" in detail_lower:
            return "no_tool_call"
        return "bad_args"

    # Tool response handling failures
    if "tool response" in name.lower():
        if "doesn't use tool data" in detail_lower:
            return "wrong_content"
        return "wrong_content"

    # Multi-tool selection failures
    if "multi-tool" in name.lower() or "selection" in name.lower():
        if "selected" in detail_lower and "instead of" in detail_lower:
            return "wrong_tool"
        if "no tool call" in detail_lower:
            return "no_tool_call"
        return "wrong_tool"

    # No-tool-when-unnecessary failures
    if "no tool when" in name.lower() or "unnecessary" in name.lower():
        if "model called a tool" in detail_lower:
            return "wrong_tool"
        return "wrong_content"

    # Generation failures
    if "generates" in name.lower() or "follows instructions" in name.lower():
        if "empty response" in detail_lower:
            return "truncated"
        return "wrong_content"

    # Infrastructure failures
    if "api error" in detail_lower or "timeout" in detail_lower:
        return "tool_error"

    return "unknown"


def classify_eval_failure(eval_result):
    """Classify a single eval case failure."""
    detail = eval_result.get("detail", "")
    detail_lower = detail.lower()

    # Parse the detail string for assertion failures
    if "expected tool" in detail_lower and "got" in detail_lower:
        if "got []" in detail_lower or "got none" in detail_lower:
            return "no_tool_call"
        return "wrong_tool"

    if "expected no tool call" in detail_lower:
        return "wrong_tool"

    if "argument" in detail_lower and "not found" in detail_lower:
        return "bad_args"

    if "not set to" in detail_lower:
        return "bad_args"

    if "content doesn't contain" in detail_lower:
        return "wrong_content"

    if "content unexpectedly contains" in detail_lower:
        return "wrong_content"

    if "api error" in detail_lower:
        return "tool_error"

    return "unknown"


def classify_results_file(filepath):
    """Load and classify all failures from a results JSON file."""
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"error": f"Cannot load {filepath}: {e}", "failures": []}

    failures = []

    # Handle smoke test results format
    if "tests" in data:
        for test in data["tests"]:
            if test.get("status") == "fail":
                failure_type = classify_smoke_failure(test)
                type_info = FAILURE_TYPES[failure_type]
                failures.append({
                    "source": filepath,
                    "test": test.get("test", test.get("name", "unknown")),
                    "detail": test.get("detail", ""),
                    "type": failure_type,
                    "description": type_info["description"],
                    "fixable_by": type_info["fixable_by"],
                    "suggested_fix": type_info["fix"]
                })

    # Handle eval results format
    if "results" in data:
        for result in data["results"]:
            if result.get("status") == "fail":
                failure_type = classify_eval_failure(result)
                type_info = FAILURE_TYPES[failure_type]
                failures.append({
                    "source": filepath,
                    "test": result.get("name", "unknown"),
                    "detail": result.get("detail", ""),
                    "type": failure_type,
                    "description": type_info["description"],
                    "fixable_by": type_info["fixable_by"],
                    "suggested_fix": type_info["fix"]
                })

    return {"model": data.get("model", "unknown"), "failures": failures}


def summarize(all_failures):
    """Produce a summary with counts by type and actionable fix groups."""
    by_type = {}
    model_fixable = []
    tool_fixable = []
    unknown_fixable = []

    for f in all_failures:
        ftype = f["type"]
        by_type[ftype] = by_type.get(ftype, 0) + 1

        if f["fixable_by"] == "model":
            model_fixable.append(f)
        elif f["fixable_by"] == "tool":
            tool_fixable.append(f)
        else:
            unknown_fixable.append(f)

    return {
        "total_failures": len(all_failures),
        "by_type": by_type,
        "model_fixable": model_fixable,
        "tool_fixable": tool_fixable,
        "unknown": unknown_fixable
    }


def main():
    parser = argparse.ArgumentParser(description="Classify test/eval failures")
    parser.add_argument("files", nargs="+", help="Result JSON files to classify")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output to stderr")
    args = parser.parse_args()

    all_failures = []
    model = "unknown"

    for filepath in args.files:
        result = classify_results_file(filepath)
        if "error" in result:
            print(result["error"], file=sys.stderr)
            continue
        model = result.get("model", model)
        all_failures.extend(result["failures"])

    summary = summarize(all_failures)
    summary["model"] = model

    if args.verbose:
        print(f"\n=== Failure Classification ===", file=sys.stderr)
        print(f"Model: {model}", file=sys.stderr)
        print(f"Total failures: {summary['total_failures']}", file=sys.stderr)
        print(f"By type: {json.dumps(summary['by_type'], indent=2)}", file=sys.stderr)
        print(f"Model-fixable: {len(summary['model_fixable'])}", file=sys.stderr)
        print(f"Tool-fixable:  {len(summary['tool_fixable'])}", file=sys.stderr)
        print(f"Unknown:       {len(summary['unknown'])}", file=sys.stderr)

        if summary["model_fixable"]:
            print(f"\n--- Model Fixes ---", file=sys.stderr)
            for f in summary["model_fixable"]:
                print(f"  [{f['type']}] {f['test']}: {f['suggested_fix']}", file=sys.stderr)

        if summary["tool_fixable"]:
            print(f"\n--- Tool Issues (do NOT fix model) ---", file=sys.stderr)
            for f in summary["tool_fixable"]:
                print(f"  [{f['type']}] {f['test']}: {f['detail']}", file=sys.stderr)

    # Output structured JSON to stdout for consumption by retry loop
    json.dump(summary, sys.stdout, indent=2)
    print()  # trailing newline

    sys.exit(1 if all_failures else 0)


if __name__ == "__main__":
    main()
