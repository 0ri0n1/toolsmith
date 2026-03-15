"""
Model Forge — Smoke Tests
Validates that the Ollama model is functional and can handle tool-use patterns.

Usage:
    python tests/tool_smoke_test.py --model toolsmith
    python tests/tool_smoke_test.py --model toolsmith --verbose
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434"
MCPO_URL = "http://localhost:8800"

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

passed = 0
failed = 0
skipped = 0
results = []


def log(msg, color=""):
    print(f"{color}{msg}{RESET}")


def record(name, status, detail=""):
    global passed, failed, skipped
    if status == "PASS":
        passed += 1
        results.append({"test": name, "status": "pass"})
        log(f"  PASS: {name}", GREEN)
    elif status == "FAIL":
        failed += 1
        results.append({"test": name, "status": "fail", "detail": detail})
        log(f"  FAIL: {name} — {detail}", RED)
    elif status == "SKIP":
        skipped += 1
        results.append({"test": name, "status": "skip", "detail": detail})
        log(f"  SKIP: {name} — {detail}", YELLOW)


def api_request(url, data=None, timeout=120):
    """Make an HTTP request, return parsed JSON or None on error."""
    try:
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def test_ollama_running():
    """Test that Ollama API is reachable."""
    result = api_request(f"{OLLAMA_URL}/api/version")
    if result and "_error" not in result:
        record("Ollama API reachable", "PASS")
        return True
    else:
        record("Ollama API reachable", "FAIL", result.get("_error", "Unknown error"))
        return False


def test_model_exists(model):
    """Test that the target model exists in Ollama."""
    result = api_request(f"{OLLAMA_URL}/api/tags")
    if result and "_error" not in result:
        names = [m.get("name", "").split(":")[0] for m in result.get("models", [])]
        if model in names or f"{model}:latest" in [m.get("name", "") for m in result.get("models", [])]:
            record(f"Model '{model}' exists", "PASS")
            return True
        else:
            record(f"Model '{model}' exists", "FAIL", f"Available: {', '.join(names[:10])}")
            return False
    else:
        record(f"Model '{model}' exists", "FAIL", "Cannot list models")
        return False


def test_model_generates(model):
    """Test that the model can generate a basic response."""
    result = api_request(f"{OLLAMA_URL}/api/generate", {
        "model": model,
        "prompt": "Reply with exactly the word 'working' and nothing else.",
        "stream": False,
        "options": {"num_predict": 50}
    }, timeout=180)
    if result and "_error" not in result:
        response = result.get("response", "").strip().lower()
        if len(response) > 0:
            record("Model generates output", "PASS")
            return True
        else:
            record("Model generates output", "FAIL", "Empty response")
            return False
    else:
        record("Model generates output", "FAIL", result.get("_error", "Unknown"))
        return False


def test_model_follows_instructions(model):
    """Test that the model follows simple instructions."""
    result = api_request(f"{OLLAMA_URL}/api/generate", {
        "model": model,
        "prompt": "What is 2 + 3? Answer with just the number.",
        "stream": False,
        "options": {"num_predict": 50}
    }, timeout=180)
    if result and "_error" not in result:
        response = result.get("response", "").strip()
        if "5" in response:
            record("Model follows instructions", "PASS")
            return True
        else:
            record("Model follows instructions", "FAIL", f"Expected '5', got: {response[:100]}")
            return False
    else:
        record("Model follows instructions", "FAIL", result.get("_error", "Unknown"))
        return False


def test_tool_call_format(model):
    """Test that the model produces well-formed tool calls when given tools via the chat API."""
    tool_def = {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone name, e.g. 'America/New_York'"
                    }
                },
                "required": ["timezone"]
            }
        }
    }

    result = api_request(f"{OLLAMA_URL}/api/chat", {
        "model": model,
        "messages": [
            {"role": "user", "content": "What time is it in New York?"}
        ],
        "tools": [tool_def],
        "stream": False,
        "options": {"num_predict": 200}
    }, timeout=180)

    if result and "_error" not in result:
        message = result.get("message", {})
        tool_calls = message.get("tool_calls", [])

        if tool_calls:
            call = tool_calls[0]
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})

            if name == "get_current_time":
                if "timezone" in args:
                    record("Tool call format correct", "PASS")
                    return True
                else:
                    record("Tool call format correct", "FAIL", f"Missing 'timezone' arg. Got: {args}")
                    return False
            else:
                record("Tool call format correct", "FAIL", f"Wrong function name: {name}")
                return False
        else:
            # Check if model put tool call in content (template issue)
            content = message.get("content", "")
            if "tool_call" in content or "get_current_time" in content:
                record("Tool call format correct", "FAIL",
                       "Model produced tool call in content instead of structured output — template may need adjustment")
                return False
            else:
                record("Tool call format correct", "FAIL", f"No tool call produced. Content: {content[:200]}")
                return False
    else:
        record("Tool call format correct", "FAIL", result.get("_error", "Unknown"))
        return False


def test_tool_response_handling(model):
    """Test that the model correctly uses tool response data."""
    tool_def = {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    }

    # Simulate a conversation with tool call and response
    result = api_request(f"{OLLAMA_URL}/api/chat", {
        "model": model,
        "messages": [
            {"role": "user", "content": "What's the weather in Tokyo?"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "get_weather", "arguments": {"city": "Tokyo"}}}
            ]},
            {"role": "tool", "content": json.dumps({"city": "Tokyo", "temperature": "18C", "condition": "Partly Cloudy", "humidity": "65%"})}
        ],
        "tools": [tool_def],
        "stream": False,
        "options": {"num_predict": 200}
    }, timeout=180)

    if result and "_error" not in result:
        content = result.get("message", {}).get("content", "").lower()
        # Check that the model used data from the tool response
        has_temp = "18" in content
        has_city = "tokyo" in content
        has_condition = "cloud" in content or "partly" in content

        if has_temp and has_city:
            record("Tool response handling", "PASS")
            return True
        elif has_temp or has_city or has_condition:
            record("Tool response handling", "PASS")  # Partial but acceptable
            return True
        else:
            record("Tool response handling", "FAIL", f"Response doesn't use tool data: {content[:200]}")
            return False
    else:
        record("Tool response handling", "FAIL", result.get("_error", "Unknown"))
        return False


def test_no_tool_when_unnecessary(model):
    """Test that the model does NOT call tools when the question doesn't need them."""
    tool_def = {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    }

    result = api_request(f"{OLLAMA_URL}/api/chat", {
        "model": model,
        "messages": [
            {"role": "user", "content": "What is 2 + 2?"}
        ],
        "tools": [tool_def],
        "stream": False,
        "options": {"num_predict": 100}
    }, timeout=180)

    if result and "_error" not in result:
        message = result.get("message", {})
        tool_calls = message.get("tool_calls", [])
        content = message.get("content", "")

        if not tool_calls and "4" in content:
            record("No tool when unnecessary", "PASS")
            return True
        elif tool_calls:
            record("No tool when unnecessary", "FAIL", "Model called a tool for a simple math question")
            return False
        else:
            record("No tool when unnecessary", "FAIL", f"No tool call but wrong answer: {content[:100]}")
            return False
    else:
        record("No tool when unnecessary", "FAIL", result.get("_error", "Unknown"))
        return False


def test_multi_tool_selection(model):
    """Test that the model selects the correct tool from multiple options."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for information",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "Send an email to a recipient",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"}
                    },
                    "required": ["to", "subject", "body"]
                }
            }
        }
    ]

    result = api_request(f"{OLLAMA_URL}/api/chat", {
        "model": model,
        "messages": [
            {"role": "user", "content": "What's the weather like in London?"}
        ],
        "tools": tools,
        "stream": False,
        "options": {"num_predict": 200}
    }, timeout=180)

    if result and "_error" not in result:
        message = result.get("message", {})
        tool_calls = message.get("tool_calls", [])

        if tool_calls:
            name = tool_calls[0].get("function", {}).get("name", "")
            if name == "get_weather":
                record("Multi-tool selection", "PASS")
                return True
            else:
                record("Multi-tool selection", "FAIL", f"Selected '{name}' instead of 'get_weather'")
                return False
        else:
            record("Multi-tool selection", "FAIL", "No tool call produced")
            return False
    else:
        record("Multi-tool selection", "FAIL", result.get("_error", "Unknown"))
        return False


def test_mcpo_reachable():
    """Test that the MCPO bridge is reachable (informational, not a hard failure)."""
    result = api_request(f"{MCPO_URL}/openapi.json")
    if result and "_error" not in result:
        record("MCPO bridge reachable", "PASS")
        return True
    else:
        record("MCPO bridge reachable", "SKIP", "MCPO not running — tool bridging will not work until configured")
        return False


def load_failed_tests(results_file):
    """Load names of previously failed tests from a results file."""
    try:
        with open(results_file, "r") as f:
            data = json.load(f)
        return [t["test"] for t in data.get("tests", []) if t.get("status") == "fail"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return []


# Map test names to their functions for selective rerun
TEST_REGISTRY = {}


def register_test(name, func):
    TEST_REGISTRY[name] = func


def main():
    parser = argparse.ArgumentParser(description="Model Forge smoke tests")
    parser.add_argument("--model", default="toolsmith", help="Model name to test")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--rerun-failed", action="store_true",
                        help="Only rerun tests that failed in the last run")
    args = parser.parse_args()

    model = args.model
    results_file = "tests/smoke_results.json"

    log(f"\n=== Model Forge Smoke Tests ===", CYAN)
    log(f"Model: {model}\n")

    # Build the test registry
    all_tests = [
        ("Model generates output", lambda: test_model_generates(model)),
        ("Model follows instructions", lambda: test_model_follows_instructions(model)),
        ("Tool call format correct", lambda: test_tool_call_format(model)),
        ("Tool response handling", lambda: test_tool_response_handling(model)),
        ("No tool when unnecessary", lambda: test_no_tool_when_unnecessary(model)),
        ("Multi-tool selection", lambda: test_multi_tool_selection(model)),
    ]

    # Determine which tests to run
    if args.rerun_failed:
        failed_names = load_failed_tests(results_file)
        if not failed_names:
            log("No previous failures found. Running all tests.", YELLOW)
            tests_to_run = all_tests
        else:
            tests_to_run = [(n, f) for n, f in all_tests if n in failed_names]
            log(f"Rerunning {len(tests_to_run)} previously failed test(s)", YELLOW)
    else:
        tests_to_run = all_tests

    # Core tests — always run infrastructure checks
    log("--- Infrastructure ---", YELLOW)
    if not test_ollama_running():
        log("\nCannot proceed without Ollama. Aborting.", RED)
        sys.exit(1)

    if not test_model_exists(model):
        log(f"\nModel '{model}' not found. Build it first: ollama create {model} -f ollama/Modelfile", RED)
        sys.exit(1)

    test_mcpo_reachable()

    # Run selected tests
    test_names_to_run = {n for n, _ in tests_to_run}

    log("\n--- Generation ---", YELLOW)
    for name, func in tests_to_run:
        if name in ("Model generates output", "Model follows instructions"):
            func()

    log("\n--- Tool Use ---", YELLOW)
    for name, func in tests_to_run:
        if name not in ("Model generates output", "Model follows instructions"):
            func()

    # Summary
    log(f"\n=== Results ===", CYAN)
    log(f"Passed:  {passed}", GREEN)
    log(f"Failed:  {failed}", RED if failed > 0 else "")
    log(f"Skipped: {skipped}", YELLOW if skipped > 0 else "")

    # Write results to file
    try:
        with open(results_file, "w") as f:
            json.dump({
                "model": model,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "rerun_failed": args.rerun_failed,
                "tests": results
            }, f, indent=2)
        log(f"\nResults written to {results_file}")
    except Exception as e:
        log(f"\nCould not write results file: {e}", YELLOW)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
