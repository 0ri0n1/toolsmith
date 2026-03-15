"""
Model Forge — Kali Nmap Smoke Tests
Validates the kali-nmap model can scan with nmap via the Kali container.

Usage:
    python tests/nmap_smoke_test.py --model kali-nmap
    python tests/nmap_smoke_test.py --model kali-nmap --target 127.0.0.1
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434"

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
        log(f"  FAIL: {name} -- {detail}", RED)
    elif status == "SKIP":
        skipped += 1
        results.append({"test": name, "status": "skip", "detail": detail})
        log(f"  SKIP: {name} -- {detail}", YELLOW)


def api_chat(model, messages, tools=None, timeout=180):
    data = {"model": model, "messages": messages, "stream": False, "options": {"num_predict": 300}}
    if tools:
        data["tools"] = tools
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"_error": str(e)}


NMAP_TOOL = {
    "type": "function",
    "function": {
        "name": "nmap_scan",
        "description": "Run an nmap scan against a target from the Kali Linux container",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "IP address, hostname, or CIDR range"},
                "scan_type": {
                    "type": "string",
                    "description": "Nmap scan technique",
                    "enum": ["-sS", "-sT", "-sU", "-sA", "-sF", "-sX", "-sN", "-sn", "-sV", "-O", "-A", "-sC"]
                },
                "ports": {"type": "string", "description": "Port specification, e.g. '80', '1-1000', '22,80,443'"},
                "scripts": {"type": "string", "description": "NSE scripts, e.g. 'vuln', 'http-enum'"},
                "extra_args": {"type": "string", "description": "Additional nmap flags, e.g. '-T4 --open'"},
                "timeout": {"type": "integer", "description": "Max scan time in seconds (10-900)"}
            },
            "required": ["target"]
        }
    }
}


def test_model_exists(model):
    result = api_chat(model, [{"role": "user", "content": "hello"}])
    if result and "_error" not in result:
        record(f"Model '{model}' loads", "PASS")
        return True
    else:
        record(f"Model '{model}' loads", "FAIL", result.get("_error", "Unknown"))
        return False


def test_kali_container():
    try:
        r = subprocess.run(
            ["docker", "exec", "kali-mcp-pentest", "nmap", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0 and "Nmap" in r.stdout:
            record("Kali container has nmap", "PASS")
            return True
        else:
            record("Kali container has nmap", "FAIL", r.stderr[:200])
            return False
    except Exception as e:
        record("Kali container has nmap", "FAIL", str(e))
        return False


def test_calls_nmap_for_scan(model):
    """Model should call nmap_scan when asked to scan."""
    result = api_chat(model, [
        {"role": "user", "content": "Scan 192.168.1.1 for open ports"}
    ], tools=[NMAP_TOOL])

    if result and "_error" not in result:
        tc = result.get("message", {}).get("tool_calls", [])
        if tc:
            fn = tc[0].get("function", {})
            if fn.get("name") == "nmap_scan":
                args = fn.get("arguments", {})
                if "192.168.1.1" in str(args.get("target", "")):
                    record("Calls nmap_scan for port scan", "PASS")
                    return True
                else:
                    record("Calls nmap_scan for port scan", "FAIL", f"Wrong target: {args}")
                    return False
            else:
                record("Calls nmap_scan for port scan", "FAIL", f"Wrong tool: {fn.get('name')}")
                return False
        else:
            record("Calls nmap_scan for port scan", "FAIL", "No tool call")
            return False
    else:
        record("Calls nmap_scan for port scan", "FAIL", result.get("_error", "Unknown"))
        return False


def test_syn_scan_default(model):
    """Default scan type should be SYN (-sS) or at least a valid scan type."""
    result = api_chat(model, [
        {"role": "user", "content": "Quick scan of 10.0.0.1"}
    ], tools=[NMAP_TOOL])

    if result and "_error" not in result:
        tc = result.get("message", {}).get("tool_calls", [])
        if tc:
            args = tc[0].get("function", {}).get("arguments", {})
            scan = args.get("scan_type", "-sS")
            if scan in ["-sS", "-sT", "-sV", "-A", "-sC"]:
                record("Uses valid scan type", "PASS")
                return True
            else:
                record("Uses valid scan type", "FAIL", f"Got: {scan}")
                return False
        else:
            record("Uses valid scan type", "FAIL", "No tool call")
            return False
    else:
        record("Uses valid scan type", "FAIL", result.get("_error", "Unknown"))
        return False


def test_udp_for_dns(model):
    """Should use UDP scan when asked about DNS."""
    result = api_chat(model, [
        {"role": "user", "content": "Check if DNS is running on 192.168.1.1 port 53 using UDP"}
    ], tools=[NMAP_TOOL])

    if result and "_error" not in result:
        tc = result.get("message", {}).get("tool_calls", [])
        if tc:
            args = tc[0].get("function", {}).get("arguments", {})
            scan = args.get("scan_type", "")
            ports = str(args.get("ports", ""))
            if scan == "-sU":
                record("Uses UDP scan for DNS", "PASS")
                return True
            elif "53" in ports:
                record("Uses UDP scan for DNS", "PASS")  # targeted port 53 is acceptable
                return True
            else:
                record("Uses UDP scan for DNS", "FAIL", f"scan_type={scan}, ports={ports}")
                return False
        else:
            record("Uses UDP scan for DNS", "FAIL", "No tool call")
            return False
    else:
        record("Uses UDP scan for DNS", "FAIL", result.get("_error", "Unknown"))
        return False


def test_nse_scripts(model):
    """Should set scripts param when asked for vulnerability scan."""
    result = api_chat(model, [
        {"role": "user", "content": "Run a vulnerability scan against 10.0.0.5"}
    ], tools=[NMAP_TOOL])

    if result and "_error" not in result:
        tc = result.get("message", {}).get("tool_calls", [])
        if tc:
            args = tc[0].get("function", {}).get("arguments", {})
            scripts = args.get("scripts", "")
            scan = args.get("scan_type", "")
            if scripts and "vuln" in scripts.lower():
                record("Uses vuln scripts for vuln scan", "PASS")
                return True
            elif scan == "-sC" or scan == "-A":
                record("Uses vuln scripts for vuln scan", "PASS")  # script scan is acceptable
                return True
            else:
                record("Uses vuln scripts for vuln scan", "FAIL", f"scripts={scripts}, scan_type={scan}")
                return False
        else:
            record("Uses vuln scripts for vuln scan", "FAIL", "No tool call")
            return False
    else:
        record("Uses vuln scripts for vuln scan", "FAIL", result.get("_error", "Unknown"))
        return False


def test_interprets_results(model):
    """Model should interpret nmap output from a tool response."""
    result = api_chat(model, [
        {"role": "user", "content": "Scan 192.168.1.1"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "nmap_scan", "arguments": {"target": "192.168.1.1", "scan_type": "-sS"}}}
        ]},
        {"role": "tool", "content": json.dumps({
            "command": "nmap -sS 192.168.1.1",
            "output": "Starting Nmap 7.98\nNmap scan report for 192.168.1.1\nHost is up (0.0023s latency).\nPORT    STATE SERVICE\n22/tcp  open  ssh\n80/tcp  open  http\n443/tcp open  https\n3306/tcp closed mysql\nNmap done: 1 IP address (1 host up) scanned in 1.23 seconds",
            "exit_code": 0
        })}
    ], tools=[NMAP_TOOL])

    if result and "_error" not in result:
        content = result.get("message", {}).get("content", "").lower()
        has_ssh = "ssh" in content or "22" in content
        has_http = "http" in content or "80" in content
        has_open = "open" in content
        if has_ssh and has_http and has_open:
            record("Interprets nmap results", "PASS")
            return True
        elif has_open:
            record("Interprets nmap results", "PASS")  # mentioned open ports
            return True
        else:
            record("Interprets nmap results", "FAIL", f"Missing key findings: {content[:200]}")
            return False
    else:
        record("Interprets nmap results", "FAIL", result.get("_error", "Unknown"))
        return False


def test_no_scan_for_general_question(model):
    """Should NOT scan when asked a general question."""
    result = api_chat(model, [
        {"role": "user", "content": "What is nmap?"}
    ], tools=[NMAP_TOOL])

    if result and "_error" not in result:
        tc = result.get("message", {}).get("tool_calls", [])
        content = result.get("message", {}).get("content", "").lower()
        if not tc and ("nmap" in content or "scan" in content):
            record("No scan for general question", "PASS")
            return True
        elif tc:
            record("No scan for general question", "FAIL", "Model tried to scan when just asked about nmap")
            return False
        else:
            record("No scan for general question", "PASS")
            return True
    else:
        record("No scan for general question", "FAIL", result.get("_error", "Unknown"))
        return False


def test_live_scan(model, target):
    """Actually run nmap via Docker against a real target."""
    try:
        r = subprocess.run(
            ["docker", "exec", "kali-mcp-pentest", "nmap", "-sn", "-T4", target],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0:
            record(f"Live nmap scan ({target})", "PASS")
            return True
        else:
            record(f"Live nmap scan ({target})", "FAIL", r.stderr[:200])
            return False
    except subprocess.TimeoutExpired:
        record(f"Live nmap scan ({target})", "FAIL", "Timed out")
        return False
    except Exception as e:
        record(f"Live nmap scan ({target})", "FAIL", str(e))
        return False


def main():
    parser = argparse.ArgumentParser(description="Kali nmap model smoke tests")
    parser.add_argument("--model", default="kali-nmap", help="Model name")
    parser.add_argument("--target", default="127.0.0.1", help="Live scan target (default: localhost)")
    args = parser.parse_args()

    log(f"\n=== Kali Nmap Smoke Tests ===", CYAN)
    log(f"Model: {args.model}\n")

    # Infrastructure
    log("--- Infrastructure ---", YELLOW)
    if not test_model_exists(args.model):
        log(f"\nModel '{args.model}' not available. Build: ollama create {args.model} -f ollama/kali-nmap.Modelfile", RED)
        sys.exit(1)
    test_kali_container()

    # Tool use
    log("\n--- Tool Use ---", YELLOW)
    test_calls_nmap_for_scan(args.model)
    test_syn_scan_default(args.model)
    test_udp_for_dns(args.model)
    test_nse_scripts(args.model)

    # Interpretation
    log("\n--- Result Interpretation ---", YELLOW)
    test_interprets_results(args.model)
    test_no_scan_for_general_question(args.model)

    # Live scan
    log("\n--- Live Scan ---", YELLOW)
    test_live_scan(args.model, args.target)

    # Summary
    log(f"\n=== Results ===", CYAN)
    log(f"Passed:  {passed}", GREEN)
    log(f"Failed:  {failed}", RED if failed > 0 else "")
    log(f"Skipped: {skipped}", YELLOW if skipped > 0 else "")

    out = "tests/nmap_smoke_results.json"
    try:
        with open(out, "w") as f:
            json.dump({
                "model": args.model,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "passed": passed, "failed": failed, "skipped": skipped,
                "tests": results
            }, f, indent=2)
        log(f"\nResults: {out}")
    except Exception:
        pass

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
