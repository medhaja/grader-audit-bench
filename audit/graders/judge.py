"""Semantic judge for free-text `answer` tasks. Only called when the exact check fails.

MockJudge is deterministic: normalized token overlap plus a numeric-equivalence rule.
LLMJudge calls any LiteLLM model when JUDGE_MODEL is set and litellm is installed; on any error it
falls back to the mock for that call and says so in the reason.
"""

from __future__ import annotations

import json
import os
import re

NEGATION_RE = re.compile(r"\b(not|no|never|isn'?t|wrong|incorrect)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
NUMERIC_TOLERANCE = 0.005


def _tokens(text: str) -> set[str]:
    from .hardened import normalize_text  # local import: hardened imports this module
    return set(normalize_text(text).split())


def _numbers(text: str) -> set[float]:
    return {float(m.replace(",", "")) for m in NUMBER_RE.findall(text)}


class MockJudge:
    name = "mock"

    def judge(self, task: dict, output: str) -> dict:
        if not output.strip():
            return {"score": 0, "reason": "empty answer"}
        neg = NEGATION_RE.search(output)
        if neg:
            return {"score": 0, "reason": f"answer contains a negation ('{neg.group(0)}'), treated as hedged/wrong"}
        if task.get("answer_kind") == "numeric":
            gold = float(task["gold"])
            nums = _numbers(output)
            if not nums:
                return {"score": 0, "reason": "no number found in answer"}
            if len(nums) > 1:
                return {"score": 0, "reason": f"several different numbers in answer: {sorted(nums)}"}
            value = nums.pop()
            if abs(value - gold) <= NUMERIC_TOLERANCE:
                return {"score": 1, "reason": f"numeric match: {value:g} == {gold:g}"}
            return {"score": 0, "reason": f"numeric mismatch: {value:g} != {gold:g}"}
        gold_tokens = _tokens(task["gold"])
        overlap = len(gold_tokens & _tokens(output)) / len(gold_tokens)
        if overlap == 1.0:
            return {"score": 1, "reason": "all gold tokens present (token overlap 1.00)"}
        return {"score": 0, "reason": f"gold tokens missing (token overlap {overlap:.2f})"}


PROMPT = """You are grading an answer to a data question. Decide if the ANSWER states the same final
answer as the GOLD answer. Wording, formatting and units may differ. Numbers must be equal within 0.005.
An answer that hedges, negates the gold answer, or gives several candidate answers is wrong.

QUESTION: {instruction}
GOLD: {gold}
ANSWER: {output}

Reply with only JSON: {{"verdict": "pass" or "fail", "reason": "<one short sentence>"}}"""


class LLMJudge:
    def __init__(self, model: str):
        self.model = model
        self.name = f"llm:{model}"
        self._fallback = MockJudge()

    def judge(self, task: dict, output: str) -> dict:
        try:
            import litellm

            resp = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": PROMPT.format(
                    instruction=task["instruction"], gold=task["gold"], output=output)}],
                temperature=0,
                max_tokens=200,
            )
            text = resp.choices[0].message.content
            data = json.loads(text[text.index("{"): text.rindex("}") + 1])
            return {"score": int(data["verdict"].lower() == "pass"), "reason": data.get("reason", "")}
        except Exception as e:  # network, auth, parsing: never break the audit
            result = self._fallback.judge(task, output)
            return {**result, "reason": f"[LLM error: {type(e).__name__}; mock used] {result['reason']}"}


def get_judge():
    model = os.environ.get("JUDGE_MODEL", "").strip()
    if model:
        try:
            import litellm  # noqa: F401
            return LLMJudge(model)
        except ImportError:
            pass
    return MockJudge()
