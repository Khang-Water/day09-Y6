# Routing Decisions Log — Lab Day 09

**Nhóm:** Nhóm Y6 
**Ngày:** 2026-04-14

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.
> Không ghi giả định — phải từ trace thật (`artifacts/traces/`).
> 
> Mỗi entry phải có: task đầu vào → worker được chọn → route_reason → kết quả thực tế.

---

## Routing Decision #1

**Task đầu vào:**
> Ticket P1 được tạo lúc 22:47. Đúng theo SLA, ai nhận thông báo đầu tiên và qua kênh nào? Deadline escalation là mấy giờ?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains retrieval keywords (P1/escalation/ticket/SLA) - priority | risk_high flagged`  
**MCP tools được gọi:** `None (Mảng mcp_tools_used: [])`  
**Workers called sequence:** `["retrieval_worker", "retrieval_worker", "synthesis_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Người nhận đầu là On-call qua #incident-p1 & email. Deadline escalate là tự động sau 10 phút.
- confidence: 0.59
- Correct routing? **Yes**

**Nhận xét:** _(Routing này đúng hay sai? Nếu sai, nguyên nhân là gì?)_
Routing xử lý rất chính xác. Cụm từ khóa 'P1/escalation' được ưu tiên đánh cờ độ rủi ro cao để đưa trực tiếp cho `retrieval_worker` dò tìm thông tin SLA trong file `sla-p1-2026.pdf`.

---

## Routing Decision #2

**Task đầu vào:**
> Khách hàng đặt đơn ngày 31/01/2026 và gửi yêu cầu hoàn tiền ngày 07/02/2026 vì lỗi nhà sản xuất. Sản phẩm chưa kích hoạt, không phải Flash Sale... Chính sách nào áp dụng và có được hoàn tiền không?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keywords`  
**MCP tools được gọi:** `["search_kb"]`  
**Workers called sequence:** `["policy_tool_worker", "policy_tool_worker", "synthesis_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Không đủ thông tin do cần tra cứu chính sách v3 (đơn được đặt trước ngày hiệu lực 01/02/2026 của v4).
- confidence: 0.3 (HITL_triggered = true)
- Correct routing? **Yes**

**Nhận xét:**
Router đã nhận dạng đây là bài toán cần phân tích quy luật nên đã đá cho `policy_tool_worker` sử dụng kết hợp MCP gọi `search_kb`. Worker đã rất thông minh nhận biết điều kiện ngày không đủ thoả mãn và HITL trigger thành công do độ tự tin thấp (0.3).

---

## Routing Decision #3

**Task đầu vào:**
> Mức phạt tài chính cụ thể khi đội IT vi phạm SLA P1 resolution time (không resolve trong 4 giờ) là bao nhiêu?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains retrieval keywords (P1/escalation/ticket/SLA) - priority | risk_high flagged`  
**MCP tools được gọi:** `[]`  
**Workers called sequence:** `["retrieval_worker", "retrieval_worker", "synthesis_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Không đủ thông tin trong tài liệu nội bộ. Các tài liệu không đề cập mức phạt tài chính.
- confidence: 0.3 (HITL_triggered = true)
- Correct routing? **Yes**

**Nhận xét:**
Hệ thống chống bịa số liệu (Hallucination) hoạt động đặc biệt tốt! Bằng chứng từ trace cho thấy pipeline kiểm tra tài liệu và trung thực abstain, báo cáo là không biết.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> Sự cố P1 xảy ra lúc 2am. Đồng thời cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix...

**Worker được chọn:** `retrieval_worker`  
**Route reason:** `task contains retrieval keywords (P1/escalation/ticket/SLA) - priority | risk_high flagged`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**
Đây là Multi-hop Cross-Document Retrieval. Hệ thống phải cùng lúc tra cứu trong 2 nơi: `support/sla-p1-2026.pdf` (cho SLA notification) và `it/access-control-sop.md` (cho Level 2 temp access). Do router ưu tiên rule khẩn cấp của P1 nên đã điều hướng sang `retrieval` và may mắn đáp ứng đủ cả 2 files nguồn.

---

## Tổng kết

### Routing Distribution (Dựa trên `eval_report.json`)

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 58 | 54.7% |
| policy_tool_worker | 48 | 45.3% |
| human_review | 0 | 0% |

### Routing Accuracy

> Trong số 106 câu nhóm đã chạy, bao nhiêu câu supervisor route đúng?

- Câu route đúng: 106 / 106 (Tỷ lệ phân nhánh tuyệt đối)
- Câu route sai (đã sửa bằng cách nào?): 0
- Câu trigger HITL: 9 câu (8.5%)

### Lesson Learned về Routing

> Quyết định kỹ thuật quan trọng nhất nhóm đưa ra về routing logic là gì?  

1. Sử dụng Keyword Mapping (e.g. `P1`, `escalation`, `ticket`) kết hợp ưu tiên cờ `risk_high flagged` cho các tài liệu khẩn nhằm tránh rườm rà chạy Tool.
2. Với các luồng logic về policy/claim cần dùng Worker mang interface MCP `search_kb` linh động hơn.

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?  
Các `route_reason` được log trong trace vô cùng tường minh (e.g., `task contains policy/access keywords`). Việc debug cực kỳ mượt mà vì khi sai ta ngay lập tức biết là lỗi do Rule Router sai hay API LLM ở Worker trả về rác. Trang bị log trace thay vì log terminal trống trải là quyết định cốt lõi.
