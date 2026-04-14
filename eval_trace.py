"""
eval_trace.py - Trace evaluation and Day08 vs Day09 comparison.

Usage:
    python eval_trace.py
    python eval_trace.py --grading
    python eval_trace.py --analyze
    python eval_trace.py --compare
    python eval_trace.py --compare --day08-results artifacts/day08_baseline.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from statistics import median
from typing import Any, Optional

# Import graph
sys.path.insert(0, os.path.dirname(__file__))
from graph import run_graph, save_trace

ABSTAIN_PHRASES = (
    "khong du thong tin",
    "khong co trong tai lieu",
    "khong tim thay",
    "khong duoc de cap",
    "khong co thong tin",
    "tai lieu khong co",
    "khong du thong tin trong tai lieu noi bo",
)


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _format_rate(part: int, total: int) -> str:
    if total <= 0:
        return "0/0 (0.0%)"
    pct = (part / total) * 100
    return f"{part}/{total} ({pct:.1f}%)"


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        # Accept strings like "12.3", "12.3%", "3/10 (30%)"
        percent_match = re.search(r"(-?\d+(?:\.\d+)?)\s*%", cleaned)
        if percent_match:
            return float(percent_match.group(1))
        frac_match = re.search(r"(\d+)\s*/\s*(\d+)", cleaned)
        if frac_match:
            n = float(frac_match.group(1))
            d = float(frac_match.group(2))
            return (n / d) * 100 if d else None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _normalize_for_abstain(text: str) -> str:
    text = text.lower()
    # Normalize Vietnamese accents for robust abstain detection.
    table = str.maketrans(
        "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ",
        "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd",
    )
    return text.translate(table)


def _find_day08_baseline_file(explicit_path: Optional[str]) -> Optional[str]:
    if explicit_path:
        return explicit_path if os.path.exists(explicit_path) else None

    candidates = [
        "artifacts/day08_baseline.json",
        "artifacts/day08_eval_report.json",
        "day08_eval_report.json",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _normalize_day08_baseline(payload: Any) -> dict:
    """
    Normalize many possible Day08 JSON shapes into one baseline schema.
    """
    if not isinstance(payload, dict):
        return {}

    base = payload.get("day08_single_agent", payload)

    return {
        "total_questions": base.get("total_questions") or base.get("total_traces"),
        "avg_confidence": _to_float(base.get("avg_confidence")),
        "avg_latency_ms": _to_float(base.get("avg_latency_ms")),
        "abstain_rate": base.get("abstain_rate"),
        "multi_hop_accuracy": base.get("multi_hop_accuracy"),
    }


def _is_abstain(answer: str) -> bool:
    normalized = _normalize_for_abstain(answer or "")
    return any(phrase in normalized for phrase in ABSTAIN_PHRASES)


def run_test_questions(questions_file: str = "data/test_questions.json") -> list:
    """
    Run pipeline for test questions and save per-question traces.
    """
    questions = _load_json(questions_file)

    print(f"\n[RUN] Running {len(questions)} test questions from {questions_file}")
    print("=" * 60)

    results = []
    for i, q in enumerate(questions, 1):
        question_text = q["question"]
        q_id = q.get("id", f"q{i:02d}")
        print(f"[{i:02d}/{len(questions)}] {q_id}: {question_text[:65]}...")

        try:
            result = run_graph(question_text)
            result["question_id"] = q_id

            # Prevent trace overwrite when multiple runs happen in the same second.
            result["run_id"] = (
                f"{result.get('run_id', 'run')}_{q_id}_{datetime.now().strftime('%f')}"
            )

            trace_file = save_trace(result, "artifacts/traces")
            print(
                "  OK "
                f"route={result.get('supervisor_route', '?')}, "
                f"conf={result.get('confidence', 0):.2f}, "
                f"{result.get('latency_ms', 0)}ms, "
                f"trace={trace_file}"
            )

            results.append(
                {
                    "id": q_id,
                    "question": question_text,
                    "expected_answer": q.get("expected_answer", ""),
                    "expected_sources": q.get("expected_sources", []),
                    "difficulty": q.get("difficulty", "unknown"),
                    "category": q.get("category", "unknown"),
                    "result": result,
                    "trace_file": trace_file,
                }
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append(
                {
                    "id": q_id,
                    "question": question_text,
                    "error": str(e),
                    "result": None,
                }
            )

    ok_count = sum(1 for r in results if r.get("result"))
    print(f"\n[DONE] {ok_count}/{len(results)} succeeded.")
    return results


def run_grading_questions(questions_file: str = "data/grading_questions.json") -> str:
    """
    Run pipeline for grading questions and write JSONL log.
    """
    if not os.path.exists(questions_file):
        print(f"[ERROR] {questions_file} not found.")
        return ""

    questions = _load_json(questions_file)
    os.makedirs("artifacts", exist_ok=True)
    output_file = "artifacts/grading_run.jsonl"

    print(f"\n[RUN] Running grading questions: {len(questions)}")
    print(f"[OUT] {output_file}")
    print("=" * 60)

    with open(output_file, "w", encoding="utf-8") as out:
        for i, q in enumerate(questions, 1):
            q_id = q.get("id", f"gq{i:02d}")
            question_text = q["question"]
            print(f"[{i:02d}/{len(questions)}] {q_id}: {question_text[:65]}...")

            try:
                result = run_graph(question_text)
                record = {
                    "id": q_id,
                    "question": question_text,
                    "answer": result.get("final_answer", "PIPELINE_ERROR: no answer"),
                    "sources": result.get("retrieved_sources", []),
                    "supervisor_route": result.get("supervisor_route", ""),
                    "route_reason": result.get("route_reason", ""),
                    "workers_called": result.get("workers_called", []),
                    "mcp_tools_used": [
                        t.get("tool") if isinstance(t, dict) else str(t)
                        for t in result.get("mcp_tools_used", [])
                    ],
                    "confidence": result.get("confidence", 0.0),
                    "hitl_triggered": result.get("hitl_triggered", False),
                    "latency_ms": result.get("latency_ms"),
                    "timestamp": datetime.now().isoformat(),
                }
                print(
                    "  OK "
                    f"route={record['supervisor_route']}, conf={record['confidence']:.2f}"
                )
            except Exception as e:
                record = {
                    "id": q_id,
                    "question": question_text,
                    "answer": f"PIPELINE_ERROR: {e}",
                    "sources": [],
                    "supervisor_route": "error",
                    "route_reason": str(e),
                    "workers_called": [],
                    "mcp_tools_used": [],
                    "confidence": 0.0,
                    "hitl_triggered": False,
                    "latency_ms": None,
                    "timestamp": datetime.now().isoformat(),
                }
                print(f"  ERROR: {e}")

            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n[DONE] Grading log saved: {output_file}")
    return output_file


def analyze_traces(traces_dir: str = "artifacts/traces") -> dict:
    """
    Read traces and compute aggregate metrics.
    """
    if not os.path.exists(traces_dir):
        print(f"[WARN] Trace dir not found: {traces_dir}")
        return {}

    trace_files = sorted(f for f in os.listdir(traces_dir) if f.endswith(".json"))
    if not trace_files:
        print(f"[WARN] No trace files in {traces_dir}")
        return {}

    traces: list[dict] = []
    for fname in trace_files:
        path = os.path.join(traces_dir, fname)
        try:
            traces.append(_load_json(path))
        except Exception as e:
            print(f"[WARN] Skip invalid trace {path}: {e}")

    if not traces:
        return {}

    routing_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    mcp_tool_counts: dict[str, int] = {}

    confidences: list[float] = []
    latencies: list[int] = []
    mcp_calls = 0
    hitl_triggers = 0
    abstain_count = 0
    route_reason_missing = 0

    for t in traces:
        route = str(t.get("supervisor_route", "unknown"))
        routing_counts[route] = routing_counts.get(route, 0) + 1

        conf = _to_float(t.get("confidence"))
        if conf is not None:
            confidences.append(conf)

        lat = _to_float(t.get("latency_ms"))
        if lat is not None:
            latencies.append(int(lat))

        tools = t.get("mcp_tools_used") or []
        if tools:
            mcp_calls += 1
            for tool in tools:
                if isinstance(tool, dict):
                    tool_name = tool.get("tool", "unknown")
                else:
                    tool_name = str(tool)
                mcp_tool_counts[tool_name] = mcp_tool_counts.get(tool_name, 0) + 1

        if t.get("hitl_triggered"):
            hitl_triggers += 1

        answer = str(t.get("final_answer", ""))
        if _is_abstain(answer):
            abstain_count += 1

        route_reason = str(t.get("route_reason", "")).strip()
        if not route_reason:
            route_reason_missing += 1

        merged_sources = []
        merged_sources.extend(t.get("retrieved_sources") or [])
        merged_sources.extend(t.get("sources") or [])
        for src in set(merged_sources):
            source_counts[src] = source_counts.get(src, 0) + 1

    total = len(traces)
    routing_distribution = {
        k: _format_rate(v, total) for k, v in sorted(routing_counts.items(), key=lambda x: -x[1])
    }
    top_sources = sorted(source_counts.items(), key=lambda x: -x[1])[:10]
    top_mcp_tools = sorted(mcp_tool_counts.items(), key=lambda x: -x[1])[:10]

    metrics = {
        "total_traces": total,
        "trace_files": len(trace_files),
        "routing_distribution": routing_distribution,
        "routing_counts": routing_counts,
        "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "p50_latency_ms": round(median(latencies), 2) if latencies else None,
        "mcp_usage_rate": _format_rate(mcp_calls, total),
        "hitl_rate": _format_rate(hitl_triggers, total),
        "abstain_rate": _format_rate(abstain_count, total),
        "route_reason_missing_rate": _format_rate(route_reason_missing, total),
        "top_sources": top_sources,
        "top_mcp_tools": top_mcp_tools,
    }
    return metrics


def compare_single_vs_multi(
    multi_traces_dir: str = "artifacts/traces",
    day08_results_file: Optional[str] = None,
) -> dict:
    """
    Compare Day08 single-agent metrics vs Day09 multi-agent metrics.
    """
    multi_metrics = analyze_traces(multi_traces_dir)

    day08_source = _find_day08_baseline_file(day08_results_file)
    day08_payload = _load_json(day08_source) if day08_source else {}
    day08_baseline = _normalize_day08_baseline(day08_payload)

    if not day08_baseline:
        day08_baseline = {
            "total_questions": None,
            "avg_confidence": None,
            "avg_latency_ms": None,
            "abstain_rate": None,
            "multi_hop_accuracy": None,
        }

    day08_avg_conf = _to_float(day08_baseline.get("avg_confidence"))
    day08_avg_lat = _to_float(day08_baseline.get("avg_latency_ms"))
    day08_abstain_pct = _to_float(day08_baseline.get("abstain_rate"))
    day08_multihop_pct = _to_float(day08_baseline.get("multi_hop_accuracy"))

    day09_avg_conf = _to_float(multi_metrics.get("avg_confidence"))
    day09_avg_lat = _to_float(multi_metrics.get("avg_latency_ms"))
    day09_abstain_pct = _to_float(multi_metrics.get("abstain_rate"))
    # No auto multi-hop metric in current Day09 traces unless user labels them.
    day09_multihop_pct = _to_float(multi_metrics.get("multi_hop_accuracy"))

    comparison = {
        "generated_at": datetime.now().isoformat(),
        "day08_results_source": day08_source,
        "day08_single_agent": day08_baseline,
        "day09_multi_agent": multi_metrics,
        "analysis": {
            "routing_visibility": "Day09 has per-run route_reason and worker sequence in trace.",
            "confidence_delta_day09_minus_day08": (
                round(day09_avg_conf - day08_avg_conf, 3)
                if day09_avg_conf is not None and day08_avg_conf is not None
                else None
            ),
            "latency_delta_ms_day09_minus_day08": (
                round(day09_avg_lat - day08_avg_lat, 2)
                if day09_avg_lat is not None and day08_avg_lat is not None
                else None
            ),
            "abstain_rate_delta_pp_day09_minus_day08": (
                round(day09_abstain_pct - day08_abstain_pct, 2)
                if day09_abstain_pct is not None and day08_abstain_pct is not None
                else None
            ),
            "multi_hop_accuracy_delta_pp_day09_minus_day08": (
                round(day09_multihop_pct - day08_multihop_pct, 2)
                if day09_multihop_pct is not None and day08_multihop_pct is not None
                else None
            ),
            "debuggability": (
                "Day09 is easier to debug: can isolate supervisor/retrieval/policy/synthesis "
                "from trace and worker-level logs."
            ),
            "mcp_benefit": (
                "Day09 can extend capability via MCP tools without changing core graph flow."
            ),
            "baseline_note": (
                "Day08 baseline loaded."
                if day08_source
                else "No Day08 baseline file found; pass --day08-results to enable true deltas."
            ),
        },
    }
    return comparison


def save_eval_report(comparison: dict) -> str:
    """
    Save comparison report to JSON.
    """
    os.makedirs("artifacts", exist_ok=True)
    output_file = "artifacts/eval_report.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    return output_file


def print_metrics(metrics: dict):
    """
    Pretty-print metrics dict.
    """
    if not metrics:
        return
    print("\n[METRICS] Trace analysis")
    for k, v in metrics.items():
        if isinstance(v, list):
            print(f"  {k}:")
            for item in v:
                print(f"    - {item}")
        elif isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day09 trace evaluation")
    parser.add_argument("--grading", action="store_true", help="Run grading questions")
    parser.add_argument("--analyze", action="store_true", help="Analyze existing traces")
    parser.add_argument("--compare", action="store_true", help="Compare single vs multi")
    parser.add_argument(
        "--test-file",
        default="data/test_questions.json",
        help="Test questions file",
    )
    parser.add_argument(
        "--traces-dir",
        default="artifacts/traces",
        help="Trace directory",
    )
    parser.add_argument(
        "--day08-results",
        default=None,
        help="Optional Day08 baseline JSON file",
    )
    args = parser.parse_args()

    if args.grading:
        log_file = run_grading_questions()
        if log_file:
            print(f"\n[DONE] Grading log: {log_file}")

    elif args.analyze:
        metrics = analyze_traces(args.traces_dir)
        print_metrics(metrics)

    elif args.compare:
        comparison = compare_single_vs_multi(
            multi_traces_dir=args.traces_dir,
            day08_results_file=args.day08_results,
        )
        report_file = save_eval_report(comparison)
        print(f"\n[DONE] Comparison report saved: {report_file}")
        print("\n=== Day08 vs Day09 analysis ===")
        for k, v in comparison.get("analysis", {}).items():
            print(f"  {k}: {v}")

    else:
        run_test_questions(args.test_file)
        metrics = analyze_traces(args.traces_dir)
        print_metrics(metrics)
        comparison = compare_single_vs_multi(
            multi_traces_dir=args.traces_dir,
            day08_results_file=args.day08_results,
        )
        report_file = save_eval_report(comparison)
        print(f"\n[OUT] Eval report: {report_file}")
