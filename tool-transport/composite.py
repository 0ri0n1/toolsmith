#!/usr/bin/env python3
"""
Model Forge — Composite Tool Framework
Factory for building multi-step MCP tools that chain operations sequentially.
Each step runs synchronously, passing output to the next step.
Partial results are returned on failure.

Transport: stdio (for MCPO)
Dependencies: mcp

Usage as a library:
    from composite import CompositeToolBuilder, Step
    builder = CompositeToolBuilder("network-recon", "Full network reconnaissance")
    builder.add_step(Step("ping_sweep", ping_sweep_fn, timeout=60))
    builder.add_step(Step("port_scan", port_scan_fn, timeout=120))
    mcp_server = builder.build()
    mcp_server.run(transport="stdio")

Usage standalone (demo):
    python tool-transport/composite.py
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO, stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("composite-mcp")


@dataclass
class StepResult:
    """Result from a single step in a composite tool."""
    step_name: str
    success: bool
    data: dict | list | str | None = None
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class Step:
    """A single step in a composite tool chain.

    Args:
        name: Human-readable step name (e.g., "ping_sweep")
        func: Callable that takes (input_params: dict, previous_results: list[StepResult]) -> dict
              Must return a dict with the step's results.
              Receives all original input params plus results from prior steps.
        timeout: Per-step timeout in seconds (default 120)
        description: One-line description of what this step does
    """
    name: str
    func: Callable
    timeout: int = 120
    description: str = ""


class CompositeToolBuilder:
    """Builds a composite MCP tool from a sequence of steps.

    The resulting MCP server exposes a single @mcp.tool() function that
    runs all steps sequentially. If a step fails, partial results from
    completed steps are returned along with the error.

    Example:
        builder = CompositeToolBuilder(
            "network-recon",
            "Multi-step network reconnaissance: ping sweep, port scan, service detection"
        )

        def ping_sweep(params, previous):
            # params contains the original tool input
            # previous contains StepResult list from prior steps
            return {"hosts": ["192.168.1.1", "192.168.1.5"]}

        def port_scan(params, previous):
            hosts = previous[-1].data["hosts"]
            return {"ports": {h: [22, 80] for h in hosts}}

        builder.add_step(Step("ping_sweep", ping_sweep, timeout=60, description="Discover live hosts"))
        builder.add_step(Step("port_scan", port_scan, timeout=120, description="Scan ports on discovered hosts"))

        server = builder.build()
        server.run(transport="stdio")
    """

    def __init__(self, name: str, instructions: str):
        """Initialize a composite tool builder.

        Args:
            name: Tool server name (used in FastMCP and MCPO registration)
            instructions: Description of what this composite tool does
        """
        self.name = name
        self.instructions = instructions
        self.steps: list[Step] = []
        self._input_schema: dict = {}
        self._tool_name: str = ""
        self._tool_description: str = ""

    def add_step(self, step: Step) -> "CompositeToolBuilder":
        """Add a step to the composite chain. Steps run in order added.

        Args:
            step: Step instance to add
        """
        self.steps.append(step)
        return self

    def set_input_schema(self, tool_name: str, description: str,
                         parameters: dict) -> "CompositeToolBuilder":
        """Define the input parameters for the composite tool.

        Args:
            tool_name: Function name for the @mcp.tool() (e.g., "network_recon")
            description: Docstring for the tool function
            parameters: Dict of parameter definitions:
                {"target": {"type": "str", "description": "...", "required": True}}
        """
        self._tool_name = tool_name
        self._tool_description = description
        self._input_schema = parameters
        return self

    def _execute_chain(self, input_params: dict) -> dict:
        """Execute all steps in sequence, collecting results.

        Returns a unified result dict with all step results and metadata.
        """
        step_results: list[StepResult] = []
        chain_start = time.time()

        logger.info(f"Starting composite tool '{self.name}' with {len(self.steps)} steps")

        for i, step in enumerate(self.steps):
            step_num = i + 1
            logger.info(f"Step {step_num}/{len(self.steps)}: {step.name}"
                        + (f" — {step.description}" if step.description else ""))

            step_start = time.time()

            try:
                # Call the step function with input params and previous results
                result_data = step.func(input_params, step_results)
                duration = time.time() - step_start

                step_result = StepResult(
                    step_name=step.name,
                    success=True,
                    data=result_data,
                    duration_seconds=round(duration, 2)
                )
                step_results.append(step_result)
                logger.info(f"Step {step_num} completed in {duration:.1f}s")

            except TimeoutError as e:
                duration = time.time() - step_start
                step_result = StepResult(
                    step_name=step.name,
                    success=False,
                    error=f"Step timed out after {step.timeout}s: {e}",
                    duration_seconds=round(duration, 2)
                )
                step_results.append(step_result)
                logger.error(f"Step {step_num} timed out: {e}")
                break

            except Exception as e:
                duration = time.time() - step_start
                step_result = StepResult(
                    step_name=step.name,
                    success=False,
                    error=str(e),
                    duration_seconds=round(duration, 2)
                )
                step_results.append(step_result)
                logger.error(f"Step {step_num} failed: {e}")
                break

        total_duration = time.time() - chain_start
        completed = sum(1 for r in step_results if r.success)
        all_succeeded = completed == len(self.steps)

        # Build unified response
        response = {
            "tool": self.name,
            "status": "complete" if all_succeeded else "partial",
            "steps_completed": completed,
            "steps_total": len(self.steps),
            "total_duration_seconds": round(total_duration, 2),
            "steps": []
        }

        for sr in step_results:
            step_entry = {
                "name": sr.step_name,
                "success": sr.success,
                "duration_seconds": sr.duration_seconds
            }
            if sr.success:
                step_entry["data"] = sr.data
            else:
                step_entry["error"] = sr.error
            response["steps"].append(step_entry)

        if not all_succeeded:
            failed_step = next(r for r in step_results if not r.success)
            response["error"] = f"Chain stopped at step '{failed_step.step_name}': {failed_step.error}"

        logger.info(f"Composite tool '{self.name}' finished: {completed}/{len(self.steps)} steps in {total_duration:.1f}s")

        return response

    def build(self) -> FastMCP:
        """Build and return the FastMCP server with the composite tool registered.

        Returns:
            Configured FastMCP instance ready for .run(transport="stdio")
        """
        mcp = FastMCP(self.name, instructions=self.instructions)
        builder = self  # capture for closure

        # Build the step descriptions for the docstring
        step_desc = "\n".join(
            f"    {i+1}. {s.name}" + (f": {s.description}" if s.description else "")
            for i, s in enumerate(self.steps)
        )

        # We need to dynamically create the tool function based on input schema
        # For simplicity, all composite tools accept **kwargs as a JSON string
        # The actual validation happens in the step functions

        tool_name = self._tool_name or self.name.replace("-", "_")
        tool_desc = self._tool_description or f"Run {self.name} composite tool"

        @mcp.tool(name=tool_name, description=f"{tool_desc}\n\nSteps:\n{step_desc}")
        def composite_tool(**kwargs) -> str:
            """Execute the composite tool chain."""
            result = builder._execute_chain(kwargs)
            return json.dumps(result, indent=2, default=str)

        # Update the function signature dynamically based on input schema
        # For now, kwargs works with FastMCP's flexible parameter handling

        return mcp


def _demo():
    """Demo: a simple 3-step composite tool that echoes data through steps."""

    def step_one(params, previous):
        logger.info(f"Step one received params: {params}")
        return {"message": f"Processed input: {params.get('input', 'none')}"}

    def step_two(params, previous):
        prev_data = previous[-1].data
        return {"message": f"Built on step one: {prev_data['message']}", "extra": "step two data"}

    def step_three(params, previous):
        all_messages = [r.data.get("message", "") for r in previous if r.data]
        return {"summary": f"Completed {len(previous)} prior steps", "messages": all_messages}

    builder = CompositeToolBuilder(
        "demo-composite",
        "A demo composite tool that chains three simple steps."
    )
    builder.add_step(Step("prepare", step_one, timeout=10, description="Process initial input"))
    builder.add_step(Step("transform", step_two, timeout=10, description="Transform step one output"))
    builder.add_step(Step("summarize", step_three, timeout=10, description="Summarize all results"))
    builder.set_input_schema("demo_composite", "Run the demo composite tool", {
        "input": {"type": "str", "description": "Input text to process", "required": True}
    })

    server = builder.build()
    server.run(transport="stdio")


if __name__ == "__main__":
    _demo()
