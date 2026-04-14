# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhóm Y6  
**Thành viên:**
| Tên | Vai trò | GitHub |
|-----|---------|--------|
| Hoàng Thị Thanh Tuyền | Supervisor Owner | hoangthanhtuyen1412@gmail.com |
| Dương Khoa Điềm | Worker Owner (Retrieval) & Docs Owner  | duongkhoadiemp@gmail.com |
| Nguyễn Hồ Bảo Thiên | Worker Owner (Policy Tool) | thiennguyen3703@gmail.com |
| Võ Thanh Chung | Worker Owner (Synthesis) | vothanhchung95@gmail.com |
| Đỗ Thế Anh | MCP Owner | anh.dothe47@gmail.com |
| Lê Minh Khang | Trace | minhkhangle2k4@gmail.com |
	

**Ngày nộp:** 2026-04-14  
**Repo:** https://github.com/Khang-Water/day09-Y6  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng

**Hệ thống tổng quan:**

Nhóm xây dựng hệ thống **Supervisor-Worker Multi-Agent** sử dụng **LangGraph StateGraph** với 4 node chính. Supervisor đọc câu hỏi đầu vào và phân nhánh sang một trong hai Worker chính: `retrieval_worker` (tìm kiếm ChromaDB) hoặc `policy_tool_worker` (phân tích nghiệp vụ + gọi MCP). Sau đó `synthesis_worker` tổng hợp câu trả lời có citation từ evidence thu được. Toàn bộ dữ liệu trung gian được lưu trong `AgentState` (16 fields) xuyên suốt graph, bao gồm trace đầy đủ `worker_io_logs` và `route_reason` cho từng run.

Vector store sử dụng ChromaDB collection `rag_lab` (kế thừa từ Day 08, 30 documents, 1536-dim OpenAI embeddings). LLM synthesis gọi qua OpenRouter/Azure AI Inference endpoint với model GPT-4o, temperature 0.1.

**Routing logic cốt lõi:**

Supervisor dùng **keyword-based rule routing** với hai tập keyword:
- `policy_keywords` = ["hoàn tiền", "refund", "policy", "cấp quyền", "access", "emergency"] → route `policy_tool_worker`
- `retrieval_keywords` = ["p1", "escalation", "ticket", "sla"] → route `retrieval_worker` (ưu tiên cao hơn)
- Pattern `err-` không khớp keyword nào → `human_review`

Retrieval keywords được kiểm tra sau policy keywords và có thể override — đảm bảo câu hỏi P1/SLA luôn được route về retrieval dù có từ "emergency".

**MCP tools đã tích hợp:**

- `search_kb(query, top_k)`: Gọi `retrieve_dense()` từ `retrieval_worker`, fallback về lexical search trên `data/docs/`. Được gọi trong 5/106 traces (4.7%).
- `get_ticket_info(ticket_id)`: Tra cứu mock ticket database (P1-LATEST, IT-1234) với metadata đầy đủ: SLA deadline, notifications_sent, escalated status.
- `check_access_permission(level, role, emergency)`: Kiểm tra Access Control SOP — Level 2 có emergency bypass, Level 3 không có. Gọi khi task chứa "access/level/contractor".
- `create_ticket(priority, title)`: Mock Jira ticket creation — log ID nhưng không tạo thật.

**Bonus:** `mcp_server.py` tích hợp `FastMCP` library — chạy `python mcp_server.py --serve` để expose real MCP server over stdio.

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Dùng keyword-based routing (rule-based) thay vì LLM classifier cho Supervisor

**Bối cảnh vấn đề:**

Supervisor cần phân loại câu hỏi thành 3 nhánh: retrieval, policy, hoặc human_review. Câu hỏi đầu tiên nhóm đặt ra là: dùng LLM để phân loại (linh hoạt hơn) hay dùng keyword matching (nhanh hơn, rẻ hơn, dễ debug hơn)?

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| LLM Classifier (gọi LLM để phân loại) | Xử lý được câu hỏi mơ hồ, ngôn ngữ tự nhiên | Thêm 1 LLM call (~500ms latency), khó debug khi phân loại sai |
| Keyword Matching (rule-based) | Nhanh (< 1ms), kết quả deterministic, `route_reason` rõ ràng | Dễ fail với câu hỏi không chứa keyword cụ thể |

**Phương án đã chọn và lý do:**

Keyword matching với **priority override** — retrieval keywords ghi đè policy keywords. Lý do: với domain hẹp của lab (5 tài liệu, 2 loại nghiệp vụ chính là SLA và refund/access), keyword matching đủ chính xác và quan trọng hơn là `route_reason` luôn rõ ràng trong trace để debug. Trong 106 traces thực tế, 0 trace bị thiếu `route_reason`.

**Bằng chứng từ trace/code:**

```json
// Trace gq01 — routing đúng nhờ keyword priority
{
  "supervisor_route": "retrieval_worker",
  "route_reason": "task contains retrieval keywords (P1/escalation/ticket/SLA) - priority | risk_high flagged",
  "workers_called": ["retrieval_worker", "synthesis_worker"],
  "confidence": 0.59
}

// Code trong graph.py:
// policy được check trước, nhưng retrieval có thể override
if any(kw in task for kw in policy_keywords):
    route = "policy_tool_worker"
if any(kw in task for kw in retrieval_keywords):  # override
    route = "retrieval_worker"
```

---

## 3. Kết quả grading questions

**Tổng điểm raw ước tính:** ~72–80 / 96

**Câu pipeline xử lý tốt nhất:**
- **gq05** (latency 17,472ms, confidence 0.65): "P1 không phản hồi sau 10 phút → hệ thống làm gì?" — Retrieval tìm đúng ngay câu escalation rule trong `sla-p1-2026.pdf`, synthesis trả lời súc tích, đúng hoàn toàn.
- **gq08** (latency 16,714ms, confidence 0.61): Mật khẩu đổi sau 90 ngày, cảnh báo trước 7 ngày — lấy đúng từ `helpdesk-faq.md`.
- **gq10** (latency 11,532ms, confidence 0.58): Flash Sale + lỗi nhà sản xuất → không được hoàn tiền — Policy worker nhận diện đúng exception Flash Sale.

**Câu pipeline gặp khó khăn:**
- **gq02** (confidence 0.3, hitl_triggered): Đơn ngày 31/01/2026 yêu cầu hoàn tiền 07/02/2026 — Pipeline phát hiện đơn thuộc trước 01/02/2026 nên phải dùng policy v3, nhưng v3 không có trong tài liệu → abstain đúng nhưng mất điểm partial vì không trả lời được câu hỏi chính.
- **gq03** (confidence 0.51): Level 3 access, 3 người phê duyệt — Trả lời đúng quy trình thông thường nhưng chưa làm rõ ai là "người có thẩm quyền cao nhất cuối cùng".

**Câu gq07 (abstain):** Pipeline trả lời "Không đủ thông tin trong tài liệu nội bộ. Các tài liệu không đề cập bất kỳ mức phạt tài chính nào khi vi phạm SLA." — hoàn toàn đúng theo rubric abstain (confidence 0.3, hitl_triggered=true). Không hallucinate con số nào.

**Câu gq09 (multi-hop, 16 điểm):** Trace ghi đầy đủ 2 sources — `["it/access-control-sop.md", "support/sla-p1-2026.pdf"]`. Synthesis ghép được cả 2 phần: SLA notification steps và Level 2 emergency access conditions. Workers called: `["retrieval_worker", "synthesis_worker"]`. Confidence = 0.6 (đạt partial → full nếu đủ tiêu chí).

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được

**Metric thay đổi rõ nhất:**

| Metric | Day 08 | Day 09 |
|--------|--------|--------|
| Debuggability | ~20–30 phút/bug | **~3–5 phút/bug** |
| Hallucination | Cao (không có guard) | **0 trường hợp** trong 10 câu grading |
| HITL / Abstain | Không có | 8.5% HITL, 1.9% abstain — chính xác |
| route_reason coverage | 0% (không có routing) | **100%** (0 traces thiếu) |

**Điều nhóm bất ngờ nhất:**

Bất ngờ lớn nhất là việc `policy_tool_worker` **tự detect được edge case** đơn hàng trước 01/02/2026 áp dụng policy v3 (không có trong tài liệu) chỉ bằng rule-based string matching — không cần LLM. Điều này giúp pipeline abstain đúng cách cho gq02 thay vì hallucinate một câu trả lời sai.

Bất ngờ thứ hai: Retrieval worker với Dense vector search tự nhiên lấy được chunks từ 2 documents khác nhau cho câu multi-hop (gq09), mà không cần pipeline đặc biệt nào.

**Trường hợp multi-agent KHÔNG giúp ích:**

Với các câu đơn giản như gq04 (store credit 110%) hay gq08 (mật khẩu 90 ngày), pipeline Day 09 chạy mất 11–17 giây do overhead LangGraph nodes và embedding call. Day 08 single-agent cho kết quả tương đương trong < 5 giây. Multi-agent không cần thiết cho câu trả lời lookup đơn giản từ 1 file.

---

## 5. Phân công và đánh giá nhóm

**Phân công thực tế (từ git log):**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Hoàng Thị Thanh Tuyền | `graph.py` — AgentState, supervisor_node, route_decision, build_graph với LangGraph | Sprint 1 |
| Dương Khoa Điềm | `workers/retrieval.py` — dense retrieval, ChromaDB integration, Azure embedding config | Sprint 2 |
| Nguyễn Hồ Bảo Thiên | `workers/policy_tool.py` — rule-based exceptions, MCP tool calls, access control | Sprint 2+3 |
| Võ Thanh Chung | `workers/synthesis.py` — LLM grounding, confidence estimation, HITL trigger | Sprint 2 |
| Đỗ Thế Anh | `mcp_server.py` — 4 tools, FastMCP integration, lexical fallback search | Sprint 3 |
| Lê Minh Khang | `eval_trace.py`, trace files, eval_report.json, project initialization | Sprint 4 |

**Điều nhóm làm tốt:**

Phân công theo Sprint rõ ràng ngay từ đầu, mỗi người phụ trách module độc lập test được. Không có merge conflict lớn. Hệ thống trace đầy đủ giúp nhóm debug nhanh khi tích hợp các module. Đặc biệt việc mỗi worker có `if __name__ == "__main__"` test riêng giúp validate trước khi tích hợp vào graph.

**Điều nhóm làm chưa tốt:**

Thiếu `.env` setup guide rõ ràng cho từng thành viên — dẫn đến lỗi dimension mismatch ChromaDB khi chạy ở máy khác nhau (OpenAI 1536 dim vs SentenceTransformers 384 dim). Mất ~30 phút debug vấn đề môi trường thay vì logic.

**Nếu làm lại, nhóm sẽ thay đổi gì:**

Setup `Makefile` hoặc `setup.sh` để chuẩn hóa môi trường ngay từ đầu (`.env`, ChromaDB index, dependency). Thêm unit test tự động cho từng worker contract để phát hiện breaking change sớm khi ai đó sửa code.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

**Ưu tiên 1 — Self-healing loop (bằng chứng từ trace):**  
9/106 traces (8.5%) bị HITL do confidence < 0.4. Thay vì dừng và chờ người, hệ thống nên tự refine query và retry với keyword khác — pattern Reflexion. Ví dụ: gq02 abstain vì thiếu policy v3, lần retry có thể thêm context "áp dụng policy nào trước 01/02/2026" để tìm được câu trả lời gần đúng hơn.

**Ưu tiên 2 — LLM Classifier cho Supervisor:**  
Câu gq09 được route sang `retrieval_worker` nhờ keyword P1/escalation, nhưng thực ra cũng cần `policy_tool_worker` (access control). Với LLM classifier, Supervisor có thể nhận ra câu cần cả 2 workers và chạy parallel thay vì tuần tự.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
