# Hoàng Thị Thanh Tuyền - 2A202600074
"""
graph.py — Supervisor Orchestrator
Sprint 1: Implement AgentState, supervisor_node, route_decision và kết nối graph.

Kiến trúc:
    Input → Supervisor → [retrieval_worker | policy_tool_worker | human_review] → synthesis → Output

Chạy thử:
    python graph.py
"""

import json
import os
from datetime import datetime
from typing import TypedDict, Literal, Optional

# Uncomment nếu dùng LangGraph:
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# ─────────────────────────────────────────────
# 1. Shared State — dữ liệu đi xuyên toàn graph
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    # Input
    task: str                           # Câu hỏi đầu vào từ user

    # Supervisor decisions
    route_reason: str                   # Lý do route sang worker nào
    risk_high: bool                     # True → cần HITL hoặc human_review
    needs_tool: bool                    # True → cần gọi external tool qua MCP
    hitl_triggered: bool                # True → đã pause cho human review

    # Worker outputs
    retrieved_chunks: list              # Output từ retrieval_worker
    retrieved_sources: list             # Danh sách nguồn tài liệu
    policy_result: dict                 # Output từ policy_tool_worker
    mcp_tools_used: list                # Danh sách MCP tools đã gọi

    # Final output
    final_answer: str                   # Câu trả lời tổng hợp
    sources: list                       # Sources được cite
    confidence: float                   # Mức độ tin cậy (0.0 - 1.0)

    # Trace & history
    history: list                       # Lịch sử các bước đã qua
    workers_called: list                # Danh sách workers đã được gọi
    supervisor_route: str               # Worker được chọn bởi supervisor
    latency_ms: Optional[int]           # Thời gian xử lý (ms)
    run_id: str                         # ID của run này


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    }


# ─────────────────────────────────────────────
# 2. Supervisor Node — quyết định route
# ─────────────────────────────────────────────

def supervisor_node(state: AgentState) -> AgentState:
    task = state["task"].lower()
    state["history"].append(f"[supervisor] received task: {state['task'][:80]}")

    route = "retrieval_worker"
    route_reason = "default route"
    needs_tool = False
    risk_high = False

    policy_keywords = ["hoàn tiền", "refund", "policy", "cấp quyền", "access", "emergency"]
    retrieval_keywords = ["p1", "escalation", "ticket", "sla"]

    # policy trước
    if any(kw in task for kw in policy_keywords):
        route = "policy_tool_worker"
        route_reason = "task contains policy/access keywords"
        needs_tool = True

    # retrieval ưu tiên cao hơn policy
    if any(kw in task for kw in retrieval_keywords):
        route = "retrieval_worker"
        route_reason = "task contains retrieval keywords (P1/escalation/ticket/SLA) - priority"
        needs_tool = False

    # unknown error code -> human review
    if "err-" in task and not any(kw in task for kw in policy_keywords + retrieval_keywords):
        route = "human_review"
        route_reason = "unknown error code without enough context -> human review"
        risk_high = True

    # risk flag
    if "emergency" in task or "p1" in task or "escalation" in task:
        risk_high = True
        route_reason += " | risk_high flagged"

    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(f"[supervisor] route={route} reason={route_reason}")

    return state


# ─────────────────────────────────────────────
# 3. Route Decision — conditional edge
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    """
    Trả về tên worker tiếp theo dựa vào supervisor_route trong state.
    Đây là conditional edge của graph.
    """
    route = state.get("supervisor_route", "retrieval_worker")
    return route  # type: ignore


# ─────────────────────────────────────────────
# 4. Human Review Node — HITL placeholder
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """
    HITL node: Được chạy sau khi graph được resume từ interrupt_before.
    """
    state["hitl_triggered"] = True
    state["history"].append("[human_review] HITL processed and approved")
    state["workers_called"].append("human_review")

    print(f"\n✅ [Human Review Node] Đã qua xử lý phê duyệt từ người quản trị.")

    # Sau khi human approve, route về retrieval để lấy evidence
    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human approved → retrieval"

    return state


# ─────────────────────────────────────────────
# 5. Import Workers
# ─────────────────────────────────────────────

# TODO Sprint 2: Uncomment sau khi implement workers
from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run


def retrieval_worker_node(state: AgentState) -> AgentState:
    state["workers_called"].append("retrieval_worker")
    state["history"].append(f"[retrieval_worker] called | route_reason={state['route_reason']}")
    return retrieval_run(state)


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi policy/tool worker."""
    state["workers_called"].append("policy_tool_worker")
    state["history"].append("[policy_tool_worker] called")
    return policy_tool_run(state)


def synthesis_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi synthesis worker."""
    state["workers_called"].append("synthesis_worker")
    state["history"].append("[synthesis_worker] called")
    return synthesis_run(state)


# ─────────────────────────────────────────────
# 6. Build Graph
# ─────────────────────────────────────────────

def policy_to_next(state: AgentState) -> str:
    if not state.get("retrieved_chunks"):
        return "retrieval_worker"
    return "synthesis_worker"


def build_graph():
    """
    Xây dựng graph với supervisor-worker pattern.

    Option B (nâng cao): Dùng LangGraph StateGraph với conditional edges.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("retrieval_worker", retrieval_worker_node)
    workflow.add_node("policy_tool_worker", policy_tool_worker_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("synthesis_worker", synthesis_worker_node)

    # Build edges
    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        {
            "retrieval_worker": "retrieval_worker",
            "policy_tool_worker": "policy_tool_worker",
            "human_review": "human_review"
        }
    )

    workflow.add_edge("human_review", "retrieval_worker")
    workflow.add_edge("retrieval_worker", "synthesis_worker")
    
    workflow.add_conditional_edges(
        "policy_tool_worker",
        policy_to_next,
        {
            "retrieval_worker": "retrieval_worker",
            "synthesis_worker": "synthesis_worker"
        }
    )

    workflow.add_edge("synthesis_worker", END)

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory, interrupt_before=["human_review"])

    def run(state: AgentState) -> AgentState:
        import time
        start = time.time()
        
        config = {"configurable": {"thread_id": state["run_id"]}}
        result = app.invoke(state, config)
        
        # Checkpoint loop cho HITL
        snapshot = app.get_state(config)
        if snapshot.next and "human_review" in snapshot.next:
            print(f"\n⚠️  HITL TRIGGERED (Breakpoint)")
            print(f"   Task: {snapshot.values.get('task')}")
            print(f"   Reason: {snapshot.values.get('route_reason')}")
            
            user_input = input("   👉 Nhấn Enter để tự động duyệt, hoặc nhập chỉ dẫn mới: ")
            
            if user_input.strip():
                new_task = snapshot.values.get("task", "") + f" [Human: {user_input}]"
                app.update_state(config, {"task": new_task}, as_node="supervisor")
            
            # Resume graph từ breakpoint
            result = app.invoke(None, config)
            
        result["latency_ms"] = int((time.time() - start) * 1000)
        result["history"].append(f"[graph] completed in {result['latency_ms']}ms")
        return result

    return run


# ─────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────

_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """
    Entry point: nhận câu hỏi, trả về AgentState với full trace.

    Args:
        task: Câu hỏi từ user

    Returns:
        AgentState với final_answer, trace, routing info, v.v.
    """
    state = make_initial_state(task)
    result = _graph(state)
    return result


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run_graph(query)
        print(f"  Route   : {result['supervisor_route']}")
        print(f"  Reason  : {result['route_reason']}")
        print(f"  Workers : {result['workers_called']}")
        print(f"  Answer  : {result['final_answer'][:100]}...")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Latency : {result['latency_ms']}ms")

        # Lưu trace
        trace_file = save_trace(result)
        print(f"  Trace saved → {trace_file}")

    print("\n✅ graph.py test complete. Implement TODO sections in Sprint 1 & 2.")
