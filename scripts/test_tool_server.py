#!/usr/bin/env python3
"""
Model Forge — MCP Tool Server Validator
Starts an MCP server via stdio, sends initialize, calls tools/list,
and optionally invokes a tool with test input.

Usage:
    python scripts/test_tool_server.py tool-transport/nmap-server.py
    python scripts/test_tool_server.py tool-transport/my-server.py --invoke my_tool '{"param": "value"}'
    python scripts/test_tool_server.py tool-transport/my-server.py --verbose
"""

import argparse
import json
import subprocess
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


def make_jsonrpc(method, params=None, req_id=1):
    """Build a JSON-RPC 2.0 request."""
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def send_message(proc, message):
    """Send a JSON-RPC message over stdio using the MCP content-length framing."""
    body = json.dumps(message)
    header = f"Content-Length: {len(body)}\r\n\r\n"
    proc.stdin.write(header + body)
    proc.stdin.flush()


def read_message(proc, timeout=15):
    """Read a JSON-RPC response from the server's stdout with content-length framing."""
    import selectors
    import io

    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)

    deadline = time.time() + timeout
    header_buf = ""

    # Read headers until we get Content-Length and blank line
    content_length = None
    while time.time() < deadline:
        remaining = deadline - time.time()
        events = sel.select(timeout=remaining)
        if not events:
            sel.close()
            return None

        char = proc.stdout.read(1)
        if not char:
            sel.close()
            return None
        header_buf += char

        if header_buf.endswith("\r\n\r\n"):
            for line in header_buf.strip().split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())
            break

    if content_length is None:
        sel.close()
        return None

    # Read exactly content_length bytes
    body = ""
    while len(body) < content_length and time.time() < deadline:
        remaining_time = deadline - time.time()
        events = sel.select(timeout=remaining_time)
        if not events:
            break
        chunk = proc.stdout.read(content_length - len(body))
        if not chunk:
            break
        body += chunk

    sel.close()

    if len(body) < content_length:
        return None

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def test_server_starts(server_path, python_cmd="python"):
    """Test that the MCP server process starts without crashing."""
    try:
        proc = subprocess.Popen(
            [python_cmd, server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
        # Give it a moment to crash or start
        time.sleep(1)
        if proc.poll() is not None:
            stderr = proc.stderr.read()
            record("Server starts", "FAIL", f"Exited immediately with code {proc.returncode}: {stderr[:300]}")
            return None
        record("Server starts", "PASS")
        return proc
    except FileNotFoundError:
        record("Server starts", "FAIL", f"Python not found at '{python_cmd}'")
        return None
    except Exception as e:
        record("Server starts", "FAIL", str(e))
        return None


def test_initialize(proc):
    """Test that the server responds to MCP initialize."""
    init_msg = make_jsonrpc("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test_tool_server", "version": "1.0.0"}
    }, req_id=1)

    try:
        send_message(proc, init_msg)
        response = read_message(proc, timeout=10)

        if response is None:
            record("Initialize response", "FAIL", "No response received (timeout)")
            return False

        if "error" in response:
            record("Initialize response", "FAIL", f"Error: {response['error']}")
            return False

        result = response.get("result", {})
        if "serverInfo" in result or "capabilities" in result:
            server_name = result.get("serverInfo", {}).get("name", "unknown")
            record("Initialize response", "PASS")

            # Send initialized notification
            notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            send_message(proc, notif)
            time.sleep(0.3)
            return True
        else:
            record("Initialize response", "FAIL", f"Missing serverInfo/capabilities: {json.dumps(result)[:200]}")
            return False

    except Exception as e:
        record("Initialize response", "FAIL", str(e))
        return False


def test_tools_list(proc):
    """Test that the server returns a valid tools list."""
    list_msg = make_jsonrpc("tools/list", {}, req_id=2)

    try:
        send_message(proc, list_msg)
        response = read_message(proc, timeout=10)

        if response is None:
            record("Tools list", "FAIL", "No response received (timeout)")
            return []

        if "error" in response:
            record("Tools list", "FAIL", f"Error: {response['error']}")
            return []

        tools = response.get("result", {}).get("tools", [])
        if not tools:
            record("Tools list", "FAIL", "No tools returned")
            return []

        # Validate tool schema
        all_valid = True
        tool_names = []
        for tool in tools:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            schema = tool.get("inputSchema", {})

            tool_names.append(name)

            if not name:
                all_valid = False
                record("Tools list", "FAIL", "Tool missing 'name'")
                return tools
            if not desc:
                all_valid = False
                record("Tools list", "FAIL", f"Tool '{name}' missing 'description'")
                return tools
            if not schema or schema.get("type") != "object":
                all_valid = False
                record("Tools list", "FAIL", f"Tool '{name}' has invalid inputSchema")
                return tools

        if all_valid:
            record("Tools list", "PASS")
            log(f"    Tools found: {', '.join(tool_names)}", CYAN)

        return tools

    except Exception as e:
        record("Tools list", "FAIL", str(e))
        return []


def test_tool_invoke(proc, tool_name, arguments):
    """Test invoking a specific tool with given arguments."""
    call_msg = make_jsonrpc("tools/call", {
        "name": tool_name,
        "arguments": arguments
    }, req_id=3)

    try:
        send_message(proc, call_msg)
        response = read_message(proc, timeout=30)

        if response is None:
            record(f"Invoke '{tool_name}'", "FAIL", "No response received (timeout)")
            return False

        if "error" in response:
            record(f"Invoke '{tool_name}'", "FAIL", f"Error: {response['error']}")
            return False

        result = response.get("result", {})
        content = result.get("content", [])

        if not content:
            record(f"Invoke '{tool_name}'", "FAIL", "Empty content in response")
            return False

        # Check that the response is structured (has text content)
        text_parts = [c for c in content if c.get("type") == "text"]
        if text_parts:
            text = text_parts[0].get("text", "")
            # Try to parse as JSON to check structure
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    is_error = parsed.get("error", False)
                    if is_error:
                        record(f"Invoke '{tool_name}'", "PASS")
                        log(f"    Tool returned error (expected for test): {parsed.get('message', '')[:100]}", YELLOW)
                    else:
                        record(f"Invoke '{tool_name}'", "PASS")
                        log(f"    Response keys: {list(parsed.keys())}", CYAN)
                else:
                    record(f"Invoke '{tool_name}'", "PASS")
            except json.JSONDecodeError:
                # Non-JSON text is still valid
                record(f"Invoke '{tool_name}'", "PASS")
                log(f"    Response (text): {text[:100]}", CYAN)
            return True
        else:
            record(f"Invoke '{tool_name}'", "FAIL", f"No text content in response: {content}")
            return False

    except Exception as e:
        record(f"Invoke '{tool_name}'", "FAIL", str(e))
        return False


def main():
    parser = argparse.ArgumentParser(description="MCP Tool Server Validator")
    parser.add_argument("server", help="Path to the MCP server Python file")
    parser.add_argument("--python", default="python", help="Python interpreter (default: python)")
    parser.add_argument("--invoke", nargs=2, metavar=("TOOL", "ARGS_JSON"),
                        help="Invoke a tool with JSON arguments after listing")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    log(f"\n=== MCP Tool Server Validator ===", CYAN)
    log(f"Server: {args.server}\n")

    # Test 1: Server starts
    log("--- Startup ---", YELLOW)
    proc = test_server_starts(args.server, args.python)
    if proc is None:
        log("\nServer failed to start. Aborting.", RED)
        sys.exit(1)

    try:
        # Test 2: Initialize handshake
        log("\n--- Protocol ---", YELLOW)
        if not test_initialize(proc):
            log("\nInitialize failed. Aborting.", RED)
            sys.exit(1)

        # Test 3: Tools list
        log("\n--- Tools ---", YELLOW)
        tools = test_tools_list(proc)

        # Test 4: Optional tool invocation
        if args.invoke and tools:
            tool_name, args_json = args.invoke
            log(f"\n--- Invocation ---", YELLOW)
            try:
                arguments = json.loads(args_json)
            except json.JSONDecodeError as e:
                log(f"  Invalid JSON for tool arguments: {e}", RED)
                sys.exit(1)
            test_tool_invoke(proc, tool_name, arguments)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Summary
    log(f"\n=== Results ===", CYAN)
    log(f"Passed: {passed}", GREEN)
    log(f"Failed: {failed}", RED if failed > 0 else "")

    # Write results
    out_file = "scripts/test_tool_server_results.json"
    try:
        with open(out_file, "w") as f:
            json.dump({
                "server": args.server,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "passed": passed,
                "failed": failed,
                "tests": results
            }, f, indent=2)
    except Exception:
        pass

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
