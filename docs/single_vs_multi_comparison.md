# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Nhóm Y6  
**Ngày:** 2026-04-14

> So sánh Day 08 (single-agent RAG) với Day 09 (supervisor-worker).  
> Số liệu Day 09 lấy từ `artifacts/eval_report.json` và `artifacts/grading_run.jsonl` (10 câu grading, 106 traces test).

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | N/A (không lưu) | **0.714** | — | Tính trên 106 traces |
| Avg latency (ms) | N/A | **2,653 ms** | — | p50 = 0ms (nhiều traces nhỏ) |
| Abstain rate (%) | N/A (dễ hallucinate) | **1.9%** (2/106) | — | Thấp nhờ confidence filter |
| HITL triggered | Không có | **8.5%** (9/106) | — | confidence < 0.4 → HITL |
| MCP tool usage | Không có | **4.7%** (5/106) | — | `search_kb`, `check_access_permission` |
| Routing visibility | ✗ Không có | ✓ **0 traces thiếu** `route_reason` | N/A | 106/106 traces đầy đủ |
| Debug time (estimate) | ~20–30 phút | **~3–5 phút** | Giảm ~5–10x | Nhờ `worker_io_logs` trong trace |

> **Lưu ý:** Day 08 không có baseline file (`eval_report.json` ghi `day08_results_source: null`). Delta được ước tính dựa trên kinh nghiệm thực tế trong lab.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Đúng ở câu dễ | Đúng, có citation rõ ràng |
| Latency | ~3–5s | ~12–17s (thêm overhead LangGraph nodes) |
| Observation | Một prompt xử lý tất cả | Retrieval → Synthesis tách biệt, citation `[filename]` bắt buộc |

**Kết luận:** Với câu đơn giản (ví dụ gq04: store credit 110%, gq08: đổi mật khẩu 90 ngày), multi-agent tốt hơn về chất lượng citation nhưng chậm hơn về latency do overhead của LangGraph nodes.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Dễ thiếu thông tin từ doc thứ 2 | Retrieval lấy được chunk từ nhiều files cùng lúc |
| Routing visible? | ✗ | ✓ — `retrieved_sources` ghi cả 2 files |
| Observation | Single prompt, dễ bỏ sót | `gq09`: lấy đúng `sla-p1-2026.pdf` + `access-control-sop.md` |

**Kết luận:** Multi-agent vượt trội rõ rệt ở câu multi-hop. Ví dụ cụ thể: gq09 (câu khó nhất — 16 điểm) hệ thống trả lời đủ cả 2 phần SLA notification và Level 2 emergency access, confidence = 0.6.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | Thường bịa số liệu (hallucinate) | 1.9% abstain đúng cách |
| Hallucination cases | Cao | 0 trường hợp bịa số liệu trong grading |
| Observation | Không có cơ chế confidence | Synthesis abstain khi không tìm thấy evidence |

**Kết luận:** gq07 (mức phạt tài chính SLA P1) — hệ thống Day 09 trả lời "Không đủ thông tin" thay vì bịa số, đúng với rubric abstain (10/10 điểm). Day 08 rất dễ hallucinate con số này.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: 20-30 phút
```

### Day 09 — Debug workflow
```
Khi answer sai:
  1. Mở trace file trong artifacts/traces/
  2. Xem supervisor_route + route_reason → routing có đúng không?
  3. Xem worker_io_logs[0] (retrieval) → chunks có trả về không?
  4. Xem worker_io_logs[1] (synthesis) → confidence bao nhiêu?
Thời gian ước tính: 3-5 phút
```

**Câu cụ thể nhóm đã debug trong lab:**  
Lỗi `Collection expecting embedding with dimension of 1536, got 384` — retrieval_worker trả về 0 chunks. Nhờ trace log thấy ngay chunks_count = 0 trong `worker_io_logs`. Nguyên nhân: thiếu `.env` với `OPENAI_API_KEY` làm hệ thống fallback sang SentenceTransformers (384 dim) không khớp với collection `rag_lab` (1536 dim). Fix trong 3 phút.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm tool vào `mcp_server.py` + thêm call trong `policy_tool.py` |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới + routing rule |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa `retrieval_worker` độc lập, test với `python workers/retrieval.py` |
| A/B test một phần | Khó — phải clone toàn pipeline | Swap worker bằng cách đổi function reference trong `graph.py` |

**Thực tế trong lab:** Nhóm tích hợp `FastMCP` (`fastmcp` library) vào `mcp_server.py` mà không cần thay đổi bất kỳ dòng nào trong `graph.py` hay các workers khác — đúng với nguyên tắc Open/Closed của kiến trúc này.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 2 LLM calls (supervisor routing + synthesis) |
| Complex query | 1 LLM call | 2–3 LLM calls (retrieval embed + synthesis + optional MCP) |
| Embedding call | 1 embed call | 1 embed call (trong `retrieval_worker`) |
| MCP tool call | N/A | 1–3 tool calls (4.7% traces, via `mcp_server.dispatch_tool`) |

**Nhận xét về cost-benefit:**  
Day 09 tốn thêm ~1–2 LLM/Embedding calls so với Day 08. Tuy nhiên khi nhân với tỷ lệ accuracy và anti-hallucination, đây là trade-off xứng đáng. Trong domain helpdesk nội bộ, sai 1 câu về policy hoàn tiền hoặc SLA P1 có thể gây thiệt hại lớn hơn nhiều lần cost API.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. **Debuggability**: Trace rõ ràng từng node, khoanh vùng lỗi trong < 5 phút thay vì 20–30 phút.
2. **Anti-hallucination**: Confidence filter + grounded synthesis prompt → 0 trường hợp bịa số liệu trong 10 câu grading.
3. **Multi-hop accuracy**: Retrieval lấy được chunks từ nhiều documents, synthesis ghép đầy đủ câu trả lời cross-document.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. **Latency**: Cao hơn Day 08 nhờ overhead của LangGraph nodes (~12–40s cho các câu phức tạp). Câu đơn giản gánh chi phí không cần thiết.

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi domain đơn giản (< 5 docs, < 3 loại câu hỏi), không có yêu cầu audit trail, và latency quan trọng hơn accuracy. Ví dụ: FAQ chatbot đơn giản trên website.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Self-healing loop: khi Synthesis confidence < 0.4, thay vì chỉ HITL, hệ thống tự refine query và route lại Supervisor với context mới (Reflexion pattern). Điều này giảm HITL rate từ 8.5% xuống ước tính < 3%.
