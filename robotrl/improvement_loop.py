from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ImprovementLoopConfig:
    output_dir: Path = Path("runs/learning/run_next_improvement_loop")
    handoff_log_path: Path = Path("docs/recording_handoff_log.md")
    max_iterations: int = 4
    max_call_attempts: int = 3
    initial_score: int = 20
    target_score: int = 80
    simulated_gain: int = 15
    fail_first_planner_call: bool = False


@dataclass(frozen=True)
class ImprovementLoopResult:
    success: bool
    final_score: int
    iterations_completed: int
    state_path: Path
    decisions: list[dict[str, object]]


@dataclass(frozen=True)
class AgentCall:
    role: str
    status: str
    payload: dict[str, object]


class DeterministicImprovementAgents:
    def __init__(self, config: ImprovementLoopConfig) -> None:
        self._config = config
        self.call_attempts = {"planner": 0, "implementer": 0, "judge": 0}

    def call(self, role: str, context: dict[str, object]) -> AgentCall:
        self.call_attempts[role] += 1
        if (
            role == "planner"
            and self._config.fail_first_planner_call
            and self.call_attempts[role] == 1
        ):
            return AgentCall(role=role, status="retryable_error", payload={"reason": "simulated planner startup miss"})
        if role == "planner":
            return self._plan(context)
        if role == "implementer":
            return self._implement(context)
        if role == "judge":
            return self._judge(context)
        raise ValueError(f"unknown agent role: {role}")

    def _plan(self, context: dict[str, object]) -> AgentCall:
        score = int(context["score"])
        target = int(context["target_score"])
        return AgentCall(
            role="planner",
            status="success",
            payload={
                "proposal": "increase_behavior_alignment_score",
                "expected_gain": self._config.simulated_gain if score < target else 0,
                "rationale": "prioritize the weakest missing manipulation stage before another training pass",
            },
        )

    def _implement(self, context: dict[str, object]) -> AgentCall:
        plan = dict(context["plan"])
        return AgentCall(
            role="implementer",
            status="success",
            payload={
                "change": "accepted deterministic harness improvement",
                "applied_gain": int(plan["expected_gain"]),
                "implementation_note": "local harness records the improvement without mutating learning policy weights",
            },
        )

    def _judge(self, context: dict[str, object]) -> AgentCall:
        implementation = dict(context["implementation"])
        before = int(context["score_before"])
        after = before + int(implementation["applied_gain"])
        return AgentCall(
            role="judge",
            status="success",
            payload={
                "score_before": before,
                "score_after": after,
                "improved": after > before,
                "judgment": "accept" if after > before else "reject",
            },
        )


def run_improvement_loop(config: ImprovementLoopConfig) -> ImprovementLoopResult:
    if config.max_iterations < 1:
        raise ValueError("max_iterations must be positive")
    if config.max_call_attempts < 1:
        raise ValueError("max_call_attempts must be positive")
    if not 0 <= config.initial_score <= 100:
        raise ValueError("initial_score must be between 0 and 100")
    if not 0 <= config.target_score <= 100:
        raise ValueError("target_score must be between 0 and 100")

    agents = DeterministicImprovementAgents(config)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    score = config.initial_score
    decisions: list[dict[str, object]] = []
    call_history: list[dict[str, object]] = []

    state_path = config.output_dir / "improvement_loop_state.json"
    try:
        for iteration in range(1, config.max_iterations + 1):
            plan = _call_until_success(
                agents,
                role="planner",
                context={"iteration": iteration, "score": score, "target_score": config.target_score},
                call_history=call_history,
                max_call_attempts=config.max_call_attempts,
            )
            implementation = _call_until_success(
                agents,
                role="implementer",
                context={"iteration": iteration, "score": score, "plan": plan},
                call_history=call_history,
                max_call_attempts=config.max_call_attempts,
            )
            judgment = _call_until_success(
                agents,
                role="judge",
                context={"iteration": iteration, "score_before": score, "implementation": implementation},
                call_history=call_history,
                max_call_attempts=config.max_call_attempts,
            )

            improved = bool(judgment["improved"])
            decision = {
                "iteration": iteration,
                "score_before": score,
                "score_after": int(judgment["score_after"]) if improved else score,
                "planner_proposal": plan["proposal"],
                "implementer_change": implementation["change"],
                "judge_judgment": judgment["judgment"],
                "orchestrator_action": "accept_improvement" if improved else "reject_no_improvement",
            }
            decisions.append(decision)
            if improved:
                score = int(judgment["score_after"])
                _append_handoff_entry(config.handoff_log_path, decision)
            if score >= config.target_score:
                break
    except RuntimeError as exc:
        failed_role = _failed_role_from_error(str(exc))
        _write_state(
            state_path,
            agents=agents,
            call_history=call_history,
            decisions=decisions,
            final_score=score,
            target_score=config.target_score,
            success=False,
            failed_role=failed_role,
            error=str(exc),
        )
        raise

    _write_state(
        state_path,
        agents=agents,
        call_history=call_history,
        decisions=decisions,
        final_score=score,
        target_score=config.target_score,
        success=score >= config.target_score,
    )
    return ImprovementLoopResult(
        success=score >= config.target_score,
        final_score=score,
        iterations_completed=len(decisions),
        state_path=state_path,
        decisions=decisions,
    )


def _call_until_success(
    agents: DeterministicImprovementAgents,
    *,
    role: str,
    context: dict[str, object],
    call_history: list[dict[str, object]],
    max_call_attempts: int,
) -> dict[str, object]:
    for attempt in range(1, max_call_attempts + 1):
        call = agents.call(role, context)
        call_history.append(
            {
                "role": role,
                "attempt": attempt,
                "status": call.status,
                "payload": call.payload,
            }
        )
        if call.status == "success":
            return call.payload
    raise RuntimeError(f"{role} agent did not succeed after {max_call_attempts} attempts")


def _append_handoff_entry(path: Path, decision: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry_number = _next_handoff_entry_number(path)
    entry = (
        "\n"
        f"## {entry_number:03d} - {timestamp} KST - Multi-agent improvement loop\n\n"
        "### 요청\n"
        "- 오케스트레이터는 planner/implementer/judge 서브에이전트 호출 결과만 보고 판단한다.\n\n"
        "### 개선 기록\n"
        f"- iteration: {decision['iteration']}\n"
        f"- score {decision['score_before']} -> {decision['score_after']}\n"
        f"- planner: {decision['planner_proposal']}\n"
        f"- implementer: {decision['implementer_change']}\n"
        f"- judge: {decision['judge_judgment']}\n"
        f"- orchestrator: {decision['orchestrator_action']}\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def _write_state(
    path: Path,
    *,
    agents: DeterministicImprovementAgents,
    call_history: list[dict[str, object]],
    decisions: list[dict[str, object]],
    final_score: int,
    target_score: int,
    success: bool,
    failed_role: str | None = None,
    error: str | None = None,
) -> None:
    state: dict[str, object] = {
        "agents": [
            {"role": "planner", "responsibility": "propose the next bounded improvement"},
            {"role": "implementer", "responsibility": "apply the proposed improvement"},
            {"role": "judge", "responsibility": "score whether the implementation improved the objective"},
        ],
        "agent_call_attempts": agents.call_attempts,
        "call_history": call_history,
        "decisions": decisions,
        "final_score": final_score,
        "success": success,
        "target_score": target_score,
    }
    if failed_role is not None:
        state["failed_role"] = failed_role
    if error is not None:
        state["error"] = error
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _failed_role_from_error(message: str) -> str:
    match = re.match(r"^([a-z_]+) agent did not succeed", message)
    if match:
        return match.group(1)
    return "unknown"


def _next_handoff_entry_number(path: Path) -> int:
    if not path.exists():
        return 1
    highest = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^##\s+(\d{3})\b", line)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1
