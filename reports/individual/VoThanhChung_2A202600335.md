# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Võ Thanh Chung  
**MSSV:** 2A202600335  
**Vai trò trong nhóm:** Worker Owner (Synthesis)  
**Ngày nộp:** 14/04/2026  

---

## 1. Tôi phụ trách phần nào?

Module tôi chịu trách nhiệm chính là **synthesis_worker** trong file `workers/synthesis.py`. Các function tôi implement gồm: `_call_llm()`, `_build_context()`, `_estimate_confidence()`, `synthesize()`, và `run(state)`.

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/synthesis.py`
- Functions tôi implement: `_call_llm()`, `_build_context()`, `_estimate_confidence()`, `synthesize()`, `run(state)`

Synthesis worker là bước **cuối cùng** trong pipeline — luôn được gọi sau retrieval_worker hoặc policy_tool_worker. Nó nhận `retrieved_chunks` (evidence từ ChromaDB) và `policy_result` (kết quả từ policy worker), xây dựng context, gọi LLM để sinh câu trả lời có citation, tính confidence, và trigger HITL nếu cần. Output của tôi (`final_answer`, `sources`, `confidence`, `hitl_triggered`) là dữ liệu mà eval_trace.py của Lê Minh Khang đọc để chấm điểm.

**Bằng chứng:** commit `3b612ce` (15:50, ngày 14/04), commit `5147f41` (16:36, ngày 14/04), comment `VÕ THANH CHUNG - 2A202600335` ở đầu file `workers/synthesis.py`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Tôi implement cơ chế **HITL tự động dựa trên ngưỡng confidence** — khi `confidence < 0.4`, synthesis_worker tự đặt `hitl_triggered = True` và ghi vào history, không cần supervisor quyết định.

**Các lựa chọn thay thế:**
- Để supervisor quyết định HITL sau khi nhận kết quả synthesis (tập trung logic ở graph.py)
- Hard-code một số câu hỏi cụ thể phải HITL (kém linh hoạt)
- Không có HITL, để mọi câu đều trả lời (rủi ro hallucination cao)

**Lý do tôi chọn cách này:** Synthesis worker là node duy nhất có đủ thông tin để tính confidence — nó vừa biết số lượng chunks, điểm relevance của từng chunk, vừa biết nội dung câu trả lời (có abstain phrase không). Nếu để supervisor quyết định, graph.py phải thêm logic parse confidence từ state, tạo coupling không cần thiết. Đặt threshold ở synthesis layer đảm bảo bất kỳ câu trả lời nào thiếu evidence đều được escalate, bất kể route ban đầu là gì.

**Trade-off đã chấp nhận:** Ngưỡng 0.4 là heuristic — có thể một số câu đúng nhưng confidence thấp vẫn bị HITL (false positive). Tuy nhiên trong context lab, false positive tốt hơn hallucination.

**Bằng chứng từ trace/code:**

```python
# workers/synthesis.py — run(), commit 3b612ce
if result["confidence"] < 0.4:
    state["hitl_triggered"] = True
    state["history"].append(f"[{WORKER_NAME}] LOW_CONFIDENCE: HITL triggered")
else:
    state["hitl_triggered"] = False
```

Từ group report: 9/106 traces (8.5%) bị HITL triggered, 0 trường hợp hallucination trong 10 câu grading — HITL mechanism hoạt động đúng, đặc biệt câu gq07 (financial penalty không có trong tài liệu) được abstain thay vì bịa số.

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** Synthesis worker không đọc được API key khi chạy standalone (`python workers/synthesis.py`), dẫn đến chuỗi fallback hết OpenRouter → Gemini → trả về error string thay vì câu trả lời thật.

**Symptom:** Chạy `python workers/synthesis.py` luôn in ra `[SYNTHESIS ERROR] Không thể gọi LLM. Kiểm tra API key trong .env.` dù file `.env` đã có `OPENROUTER_API_KEY`.

**Root cause:** File `workers/synthesis.py` import `os` nhưng **không gọi `load_dotenv()`**. Khi `graph.py` chạy, nó load dotenv ở top-level nên synthesis hoạt động bình thường. Nhưng khi test synthesis.py trực tiếp, `os.getenv("OPENROUTER_API_KEY")` trả về `None` vì `.env` chưa được parse.

**Cách sửa:** Thêm `from dotenv import load_dotenv` và `load_dotenv()` vào phần đầu module, ngay sau import os (commit `5147f41`).

**Bằng chứng trước/sau:**

```python
# TRƯỚC (commit 3b612ce) — synthesis.py chỉ có:
import os
WORKER_NAME = "synthesis_worker"

# SAU (commit 5147f41) — đã thêm:
import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables từ .env file
WORKER_NAME = "synthesis_worker"
```

Sau khi sửa, chạy độc lập `python workers/synthesis.py` trả về câu trả lời thật từ LLM cho cả 3 test cases (SLA P1, Flash Sale exception, abstain case gq07-style).

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**  
Thiết kế `_estimate_confidence()` và HITL trigger. Việc expand abstain detection từ 1 điều kiện cứng thành list 6 phrases (`"không đủ thông tin"`, `"không có trong tài liệu"`, v.v.) giúp pipeline nhận diện câu trả lời abstain đa dạng hơn, quan trọng cho câu gq07. Cũng thiết kế `_call_llm()` với fallback 2 lớp (OpenRouter → Gemini → safe error) đảm bảo pipeline không crash ngay cả khi cả hai API key lỗi.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**  
Confidence scoring vẫn dùng weighted average của chunk similarity scores — chưa dùng LLM-as-Judge. Trong một số câu (gq03), confidence 0.51 là low nhưng không đủ để trigger HITL, dù câu trả lời chưa đầy đủ. File synthesis.py còn có duplicate `from dotenv import load_dotenv` và `load_dotenv()` do merge từ hai commit.

**Nhóm phụ thuộc vào tôi ở đâu?**  
Toàn bộ output cuối (`final_answer`, `confidence`, `hitl_triggered`) đều từ synthesis_worker. Nếu synthesis không chạy được hoặc confidence sai, eval_trace.py không thể tính đúng `hitl_rate` và `abstain_rate`, ảnh hưởng trực tiếp đến điểm grading.

**Phần tôi phụ thuộc vào thành viên khác:**  
Tôi phụ thuộc vào Dương Khoa Điềm (retrieval_worker cung cấp `retrieved_chunks` đúng format với field `source` và `score`) và Nguyễn Hồ Bảo Thiên (policy_tool_worker cung cấp `exceptions_found` list trong `policy_result`). Nếu hai field này sai schema, `_build_context()` và `_estimate_confidence()` sẽ fallback về empty context.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thay thế `_estimate_confidence()` heuristic bằng **LLM-as-Judge** — gọi thêm một LLM call nhỏ để đánh giá câu trả lời có thực sự được support bởi context hay không. Lý do: trace gq03 cho thấy confidence 0.51 dù câu trả lời thiếu thông tin về "người có thẩm quyền cao nhất cuối cùng" — một LLM judge có thể phát hiện gap này và hạ confidence xuống dưới 0.4, trigger HITL đúng chỗ, thay vì để câu trả lời partial đi qua.

---

*File lưu tại: `reports/individual/VoThanhChung_2A202600335.md`*
