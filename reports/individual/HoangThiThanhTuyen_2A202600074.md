# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Hoàng Thị Thanh Tuyền
**Vai trò trong nhóm:** Supervisor Owner
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.

**Module/file tôi chịu trách nhiệm:**

- File chính: `graph.py`
- Functions tôi implement: `build_graph()`, `supervisor_node()`, và `human_review_node()`.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Tôi chịu trách nhiệm refactor toàn bộ pipeline monolith tuyến tính cũ sang kiến trúc định tuyến đa tác vụ (Multi-Agent Orchestrator) bằng LangGraph. Công việc của tôi tạo ra cấu trúc xương sống lưu dữ liệu dùng chung (`AgentState`), giúp dẫn đường dữ liệu `task` của User vào trạm trung chuyển `supervisor_node`, từ đó gọi chéo đến các workers do các bạn khác phát triển (retrieval_worker, policy_tool_worker, synthesis_worker).

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

Hoàn thành triển khai `StateGraph(AgentState)` với conditional edges trong `graph.py` (Sprint 1). Tích hợp full logic state checkpointing (`MemorySaver`).

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
>
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Dùng cơ chế `interrupt_before` kết hợp với `MemorySaver` của LangGraph để thực hiện HITL (Human-in-the-loop) thay vì dừng script bằng lệnh `input()` thủ công.

**Lý do:**

Ban đầu, để giả lập việc yêu cầu duyệt task từ con người (human review), tôi có thể tạo một node chờ lệnh `input()`. Tuy nhiên, cách đó chỉ phù hợp cho local script mà không mô phỏng kiến trúc server agent. Bằng cách dùng Checkpointing của LangGraph, State lúc này sẽ được lưu cố định an toàn. Pipeline sẽ dừng và nhả context ra, chỉ hoạt động lại khi `update_state` hoặc pass một Command mang input mới rồi invoke lại ID luồng đó.

**Trade-off đã chấp nhận:**

Quyết định này khiến hàm `run()` cần phải inject thêm logic kiểm tra `snapshot.next` để biết graph đã bị chặn hay chưa thay vì chỉ gọi 1 lần `app.invoke()` là xong, làm tăng tính phức tạp của boilerplate orchestrator.

**Bằng chứng từ trace/code:**

```python
memory = MemorySaver()
app = workflow.compile(checkpointer=memory, interrupt_before=["human_review"])

# Trong run() kiểm tra breakpoint và update state:
snapshot = app.get_state(config)
if snapshot.next and "human_review" in snapshot.next:
    # ... human review input
    app.update_state(config, {"task": new_task}, as_node="supervisor")
    result = app.invoke(None, config)
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Supervisor điều hướng sai Node khi câu lệnh chứa từ khoá hỗn độn có nhiều độ ưu tiên.

**Symptom (pipeline làm gì sai?):**

Với câu hỏi giả lập: *"Cần cấp quyền Level 3 để khắc phục lỗi P1 khẩn cấp"*, câu trả lời lại đi vào nhánh `policy_tool_worker` (vì có từ "cấp quyền") thay vì đưa vào nhánh `retrieval_worker` — vốn yêu cầu ưu tiên lấy bằng chứng khẩn cấp liên quan đến P1/SLA.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Lỗi nằm tại logic xếp hạng keywords trong hàm `supervisor_node()`. Logic cũ sử dụng các khối lệnh `if/elif` ưu tiên xuất hiện trước, nên "cấp quyền" thuộc nhóm policy đã ăn theo route đó và return tắt bỏ qua check nhóm retrieval.

**Cách sửa:**

Thay vì dùng `if/elif` cản luồng, tôi tách các khối `if` thành chuỗi. Kiểm tra policy trước, sau đó chạy check retrieval. Nếu có retrieval keyword (`p1`, `escalation`), hệ thống sẽ gán đè `route = retrieval_worker`. Cuối cùng kiểm tra `err-`, nếu có sẽ gán đè thành `human_review` với mức độ ưu tiên vĩnh viễn cao nhất.

**Bằng chứng trước/sau:**

```python
# Sửa logic ưu tiên ngược:
if any(kw in task for kw in policy_keywords):
    route = "policy_tool_worker"

if any(kw in task for kw in retrieval_keywords):
    route = "retrieval_worker" # Ghi đè policy!

if "err-" in task:
    route = "human_review" # Ghi đè tất cả
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Nắm vững cách vận hành của object State (`AgentState` TypedDict). Tôi đã kết nối thành công các Node lại với nhau dùng conditional edges không xảy ra xung đột key-value, và ứng dụng được memory checkpointer.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Hệ thống routing hiện tại dựa quá nhiều vào tập `keywords` thủ công (Hardcoded). Nó rất dễ rẽ nhánh sai nếu context câu hỏi bị lệch so với thư viện keyword.

**Nhóm phụ thuộc vào tôi ở đâu?** *(Phần nào của hệ thống bị block nếu tôi chưa xong?)*

Nếu tôi không xây dựng thành công `build_graph()` và define `AgentState` đúng chuẩn, thì tất cả các component Worker và tool search do các bạn làm sẽ không nhận được dữ liệu Input và không có chỗ để gán Output trả về. Pipeline sẽ chết ngay từ lúc nhận câu hỏi.

**Phần tôi phụ thuộc vào thành viên khác:** *(Tôi cần gì từ ai để tiếp tục được?)*

Tôi cần các bạn Worker phải tuân thủ nghiêm ngặt Schema của `AgentState` (VD: trả đúng dict chứa key `policy_result`, `retrieved_chunks`...). Nếu module các bạn trả sai format, LangGraph DictUpdate mặc định sẽ xảy ra Type Error toàn Graph.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

Nếu có thêm thời gian, tôi sẽ thử nghiệm tích hợp một LLM mini (VD: thư viện Semantic Router hoặc mô hình local nhỏ) vào thẳng nhánh `supervisor_node` để thay thế cơ chế Rule-based keyword matching. Lý do là vì ở các edge case nâng cao, khi query dài và ẩn dụ, keyword rule sẽ phân luồng sai khiến Retrieval không được gọi, gây halluciation ở đầu cuối.
