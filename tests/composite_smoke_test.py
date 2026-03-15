"""
Model Forge — Composite Tool Smoke Tests
Validates that the composite tool framework works correctly:
- Steps execute in order
- Results pass between steps
- Partial results returned on failure
- Per-step timeout handling

Usage:
    python tests/composite_smoke_test.py
    python tests/composite_smoke_test.py --verbose
"""

import argparse
import json
import sys
import time

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

passed = 0
failed = 0
results = []


def log(msg, color=""):
    print(f"{color}{msg}{RESET}")


def record(name, status, detail=""):
    global passed, failed
    if status == "PASS":
        passed += 1
        results.append({"test": name, "status": "pass"})
        log(f"  PASS: {name}", GREEN)
    elif status == "FAIL":
        failed += 1
        results.append({"test": name, "status": "fail", "detail": detail})
        log(f"  FAIL: {name} — {detail}", RED)


def test_import():
    """Test that the composite module can be imported."""
    try:
        sys.path.insert(0, "tool-transport")
        from composite import CompositeToolBuilder, Step, StepResult
        record("Import composite module", "PASS")
        return True
    except ImportError as e:
        record("Import composite module", "FAIL", str(e))
        return False


def test_step_creation():
    """Test creating steps with all parameters."""
    from composite import Step

    step = Step(
        name="test_step",
        func=lambda p, prev: {"result": "ok"},
        timeout=30,
        description="A test step"
    )

    if step.name == "test_step" and step.timeout == 30:
        record("Step creation", "PASS")
        return True
    else:
        record("Step creation", "FAIL", "Step attributes incorrect")
        return False


def test_chain_success():
    """Test that a multi-step chain executes all steps in order."""
    from composite import CompositeToolBuilder, Step

    execution_order = []

    def step_a(params, previous):
        execution_order.append("a")
        return {"value": params.get("input", "") + "_a"}

    def step_b(params, previous):
        execution_order.append("b")
        prev_val = previous[-1].data["value"]
        return {"value": prev_val + "_b"}

    def step_c(params, previous):
        execution_order.append("c")
        prev_val = previous[-1].data["value"]
        return {"value": prev_val + "_c"}

    builder = CompositeToolBuilder("test-chain", "Test chain")
    builder.add_step(Step("step_a", step_a, description="First"))
    builder.add_step(Step("step_b", step_b, description="Second"))
    builder.add_step(Step("step_c", step_c, description="Third"))

    result = builder._execute_chain({"input": "start"})

    if result["status"] != "complete":
        record("Chain success — all steps", "FAIL", f"Status: {result['status']}")
        return False

    if result["steps_completed"] != 3:
        record("Chain success — all steps", "FAIL", f"Completed: {result['steps_completed']}")
        return False

    if execution_order != ["a", "b", "c"]:
        record("Chain success — all steps", "FAIL", f"Order: {execution_order}")
        return False

    final_value = result["steps"][-1]["data"]["value"]
    if final_value != "start_a_b_c":
        record("Chain success — all steps", "FAIL", f"Final value: {final_value}")
        return False

    record("Chain success — all steps", "PASS")
    return True


def test_chain_partial_failure():
    """Test that a chain returns partial results when a step fails."""
    from composite import CompositeToolBuilder, Step

    def step_ok(params, previous):
        return {"data": "step_ok_result"}

    def step_fail(params, previous):
        raise ValueError("Simulated failure")

    def step_never(params, previous):
        raise AssertionError("This step should never run")

    builder = CompositeToolBuilder("test-partial", "Test partial failure")
    builder.add_step(Step("ok_step", step_ok))
    builder.add_step(Step("fail_step", step_fail))
    builder.add_step(Step("never_step", step_never))

    result = builder._execute_chain({})

    if result["status"] != "partial":
        record("Chain partial failure", "FAIL", f"Status: {result['status']}")
        return False

    if result["steps_completed"] != 1:
        record("Chain partial failure", "FAIL", f"Completed: {result['steps_completed']}")
        return False

    # Should have 2 step entries (ok + fail), never_step should not appear
    if len(result["steps"]) != 2:
        record("Chain partial failure", "FAIL", f"Steps in result: {len(result['steps'])}")
        return False

    # First step should have data
    if not result["steps"][0].get("data"):
        record("Chain partial failure", "FAIL", "First step missing data")
        return False

    # Second step should have error
    if not result["steps"][1].get("error"):
        record("Chain partial failure", "FAIL", "Failed step missing error")
        return False

    # Top-level error should be set
    if "error" not in result:
        record("Chain partial failure", "FAIL", "Missing top-level error")
        return False

    record("Chain partial failure", "PASS")
    return True


def test_step_receives_previous_results():
    """Test that each step receives results from all prior steps."""
    from composite import CompositeToolBuilder, Step

    received_counts = []

    def counting_step(params, previous):
        received_counts.append(len(previous))
        return {"count": len(previous)}

    builder = CompositeToolBuilder("test-prev", "Test previous results")
    builder.add_step(Step("s1", counting_step))
    builder.add_step(Step("s2", counting_step))
    builder.add_step(Step("s3", counting_step))

    builder._execute_chain({})

    if received_counts != [0, 1, 2]:
        record("Steps receive previous results", "FAIL", f"Counts: {received_counts}")
        return False

    record("Steps receive previous results", "PASS")
    return True


def test_step_duration_tracked():
    """Test that step durations are tracked."""
    from composite import CompositeToolBuilder, Step

    def slow_step(params, previous):
        time.sleep(0.1)
        return {"done": True}

    builder = CompositeToolBuilder("test-duration", "Test duration tracking")
    builder.add_step(Step("slow", slow_step))

    result = builder._execute_chain({})

    duration = result["steps"][0].get("duration_seconds", 0)
    if duration < 0.05:
        record("Step duration tracked", "FAIL", f"Duration too low: {duration}")
        return False

    total = result.get("total_duration_seconds", 0)
    if total < 0.05:
        record("Step duration tracked", "FAIL", f"Total duration too low: {total}")
        return False

    record("Step duration tracked", "PASS")
    return True


def test_build_creates_mcp_server():
    """Test that build() returns a FastMCP instance."""
    from composite import CompositeToolBuilder, Step

    builder = CompositeToolBuilder("test-build", "Test build")
    builder.add_step(Step("noop", lambda p, prev: {"ok": True}))
    builder.set_input_schema("test_build", "Test tool", {})

    server = builder.build()

    # Check it's a FastMCP instance
    from mcp.server.fastmcp import FastMCP
    if not isinstance(server, FastMCP):
        record("Build creates FastMCP server", "FAIL", f"Got: {type(server)}")
        return False

    record("Build creates FastMCP server", "PASS")
    return True


def test_empty_chain():
    """Test that an empty chain returns gracefully."""
    from composite import CompositeToolBuilder

    builder = CompositeToolBuilder("test-empty", "Empty chain")
    result = builder._execute_chain({})

    if result["steps_completed"] != 0:
        record("Empty chain", "FAIL", f"Completed: {result['steps_completed']}")
        return False

    if result["status"] != "complete":
        record("Empty chain", "FAIL", f"Status: {result['status']}")
        return False

    record("Empty chain", "PASS")
    return True


def main():
    parser = argparse.ArgumentParser(description="Composite tool smoke tests")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    log(f"\n=== Composite Tool Smoke Tests ===", CYAN)

    log("\n--- Module ---", YELLOW)
    if not test_import():
        log("\nCannot import composite module. Aborting.", RED)
        sys.exit(1)

    log("\n--- Unit Tests ---", YELLOW)
    test_step_creation()
    test_chain_success()
    test_chain_partial_failure()
    test_step_receives_previous_results()
    test_step_duration_tracked()
    test_build_creates_mcp_server()
    test_empty_chain()

    # Summary
    log(f"\n=== Results ===", CYAN)
    log(f"Passed: {passed}", GREEN)
    log(f"Failed: {failed}", RED if failed > 0 else "")

    out = "tests/composite_smoke_results.json"
    try:
        with open(out, "w") as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "passed": passed,
                "failed": failed,
                "tests": results
            }, f, indent=2)
        log(f"\nResults: {out}")
    except Exception:
        pass

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
