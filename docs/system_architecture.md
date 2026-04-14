# System Architecture — Lab Day 09

**Nhóm:** Nhóm Y6  
**Ngày:** 2026-04-14  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

Hệ thống **Supervisor-Worker Multi-Agent** được xây dựng bằng **LangGraph** với 4 node chính: Supervisor điều phối, hai Worker song song (Retrieval và PolicyTool), và Synthesis tổng hợp kết quả. Kiến trúc cho phép trace từng bước một cách tường minh qua `AgentState` được chia sẻ xuyên suốt graph.

**Pattern đã chọn:** Supervisor-Worker (LangGraph StateGraph)  
**Lý do chọn pattern này (thay vì single agent):**  
Single-agent RAG (Day 08) xử lý toàn bộ pipeline trong một lần gọi duy nhất nên khi sai không thể biết lỗi nằm ở khâu nào. Kiến trúc Supervisor-Worker tách biệt rõ ràng ba trách nhiệm: tìm chứng cứ (Retrieval), kiểm tra logic nghiệp vụ (PolicyTool), và tổng hợp câu trả lời (Synthesis), giúp test từng module độc lập và trace theo từng node.

---

## 2. Sơ đồ Pipeline

```text
        User Request (task: str)
               │
               ▼
      ┌─────────────────┐
      │   Supervisor    │  → phân tích keyword → gán route, route_reason, risk_high
      └────────┬────────┘
               │
        [route_decision()]  ← conditional edge
               │
     ┌─────────┴──────────────┐
     ▼                        ▼                   ▼
Retrieval Worker       Policy Tool Worker     Human Review
(Dense vector search   (Rule-based check      (HITL breakpoint
 ChromaDB rag_lab)      + MCP tool calls)      → resume → retrieval)
     │                        │
     │                        │ (nếu chưa có chunks)
     │                        ▼
     │                 Retrieval Worker
     │                        │
     └──────────┬─────────────┘
                │
                ▼
        Synthesis Worker
 (LLM grounded + confidence filter)
                │
          [confidence < 0.4?]
               / \
             Yes   No
              ▼     ▼
          HITL   Output
        triggered  (final_answer, sources, confidence)
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py` — thực hiện bởi **starwindee**)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Đọc `task`, phân tích keyword, gán worker phù hợp |
| **Input** | `task: str`, `history: list` |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` |
| **Routing logic** | Keyword-based: policy keywords → `policy_tool_worker`; P1/SLA/ticket → `retrieval_worker` (ưu tiên cao hơn); ERR-code lạ → `human_review` |
| **HITL condition** | `err-` pattern trong task không có keyword đã biết → `human_review` node; sau đó resume về `retrieval_worker` |

**Routing keywords (từ code thực tế):**
```python
policy_keywords = ["hoàn tiền", "refund", "policy", "cấp quyền", "access", "emergency"]
retrieval_keywords = ["p1", "escalation", "ticket", "sla"]
```

### Retrieval Worker (`workers/retrieval.py` — thực hiện bởi **diembattu**)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Embed query → query ChromaDB → trả về top-k chunks làm evidence |
| **Embedding model** | OpenAI `text-embedding-3-small` qua Azure Inference endpoint (`https://models.inference.ai.azure.com`), vector 1536 chiều |
| **ChromaDB collection** | `rag_lab` (kế thừa từ Day 08, 30 documents) |
| **Top-k** | Default = 3, cấu hình qua `state["retrieval_top_k"]` |
| **Stateless?** | Yes — chỉ đọc DB, không ghi |
| **Fallback** | SentenceTransformers nếu không có API key, random nếu thiếu cả hai |

### Policy Tool Worker (`workers/policy_tool.py` — thực hiện bởi **Nguyen Ho Bao Thien**)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Rule-based exception detection + gọi MCP tools khi `needs_tool=True` và chưa có chunks |
| **MCP tools gọi** | `search_kb` (khi không có chunks), `check_access_permission` (khi task chứa "access/level/contractor"), `get_ticket_info` (khi task chứa "ticket/p1/jira") |
| **MCP mode** | Hỗ trợ `mock` (gọi trực tiếp `mcp_server.dispatch_tool`) và `http` → fallback mock |
| **Exception cases xử lý** | Flash Sale, Digital product/license key, Sản phẩm đã kích hoạt, Đơn hàng trước 01/02/2026 (v3 policy) |

### Synthesis Worker (`workers/synthesis.py` — thực hiện bởi **Vo Chung**)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | OpenRouter/OpenAI compatible — đọc từ `OPENROUTER_MODEL` hoặc `OPENAI_API_KEY` |
| **Temperature** | 0.1 — giữ câu trả lời Deterministic, bám sát context |
| **Grounding strategy** | System prompt nghiêm ngặt: "CHỈ dùng context được cung cấp, không dùng kiến thức ngoài", citation `[filename]` bắt buộc |
| **Abstain condition** | Confidence < 0.4 → `hitl_triggered = True`; các cụm "không đủ thông tin", "không được đề cập"... → confidence = 0.3 |
| **Confidence tính** | Weighted avg của chunk scores, trừ penalty khi có exceptions |

### MCP Server (`mcp_server.py` — thực hiện bởi **abcdefya**)

| Tool | Input | Output |
|------|-------|--------|
| `search_kb` | `query: str`, `top_k: int = 3` | `chunks[]`, `sources[]`, `total_found`, `search_mode` |
| `get_ticket_info` | `ticket_id: str` | ticket metadata (priority, status, assignee, SLA deadline, notifications) |
| `check_access_permission` | `access_level: int`, `requester_role: str`, `is_emergency: bool` | `can_grant`, `required_approvers`, `emergency_override` |
| `create_ticket` | `priority: str`, `title: str`, `description: str` | `ticket_id`, `url`, `created_at` (MOCK) |

**Bonus:** `mcp_server.py` tích hợp **FastMCP** (`fastmcp` library) — khi chạy `python mcp_server.py --serve` sẽ expose real MCP server qua stdio.

---

## 4. Shared State Schema (AgentState)

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| `task` | str | Câu hỏi đầu vào | supervisor đọc |
| `supervisor_route` | str | Worker được chọn | supervisor ghi |
| `route_reason` | str | Lý do route, dùng để debug | supervisor ghi |
| `risk_high` | bool | Cờ rủi ro cao (P1/escalation/emergency) | supervisor ghi |
| `needs_tool` | bool | Cần gọi MCP tool không | supervisor ghi |
| `retrieved_chunks` | list | Evidence chunks từ ChromaDB | retrieval ghi, policy/synthesis đọc |
| `retrieved_sources` | list | Danh sách tên file nguồn | retrieval ghi |
| `policy_result` | dict | Kết quả phân tích policy + exceptions | policy_tool ghi, synthesis đọc |
| `mcp_tools_used` | list | Log toàn bộ MCP calls (tool, input, output, timestamp) | policy_tool ghi |
| `final_answer` | str | Câu trả lời cuối có citation | synthesis ghi |
| `sources` | list | Sources được cite trong answer | synthesis ghi |
| `confidence` | float | Mức tin cậy 0.0–1.0 | synthesis ghi |
| `hitl_triggered` | bool | Cờ HITL — true khi confidence < 0.4 | synthesis ghi |
| `workers_called` | list | Danh sách workers theo thứ tự gọi | tất cả workers ghi |
| `worker_io_logs` | list | Log chi tiết I/O của từng worker | tất cả workers ghi |
| `history` | list | Chuỗi log text qua các bước | tất cả nodes ghi |
| `latency_ms` | int | Tổng thời gian xử lý | graph ghi |
| `run_id` | str | ID run duy nhất (`run_YYYYMMDD_HHMMSS`) | graph khởi tạo |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|-----------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu | Dễ — isolate từng worker qua trace `worker_io_logs` |
| Thêm capability mới | Phải sửa toàn prompt | Thêm MCP tool hoặc worker mới trong graph |
| Routing visibility | Không có | Có `route_reason` đầy đủ trong mỗi trace |
| Test độc lập | Không được | Mỗi worker có `if __name__ == "__main__"` test riêng |
| HITL | Không có | LangGraph `interrupt_before` tích hợp sẵn |

**Quan sát thực tế từ lab:**  
Trong quá trình debug lỗi `dimension mismatch` của ChromaDB (collection 1536 dim vs SentenceTransformers 384 dim), nhờ có trace rõ ràng từng bước mà nhóm khoanh vùng lỗi ở `retrieval_worker` trong vòng 3 phút, thay vì phải đọc toàn bộ pipeline.

---

## 6. Giới hạn và điểm cần cải tiến

1. **Không có Self-healing loop**: Khi Synthesis abstain (confidence < 0.4), hệ thống chỉ gắn cờ HITL thay vì tự retry với query khác hoặc route lại supervisor.
2. **Routing dựa hoàn toàn vào keyword**: Không có LLM classifier, nên các câu hỏi có keyword mơ hồ có thể bị route sai (ví dụ câu hỏi về "access" nhưng thực ra là SLA).
3. **Policy Worker chưa dùng LLM**: `analyze_policy()` vẫn là rule-based. Các edge case phức tạp (ví dụ đơn hàng trước 01/02/2026) cần được phân tích bằng LLM để chính xác hơn.
