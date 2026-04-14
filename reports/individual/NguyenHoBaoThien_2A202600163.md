# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Hồ Bảo Thiên
**Vai trò trong nhóm:** Worker Owner (Policy Tool)
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.

**Module/file tôi chịu trách nhiệm:**

- File chính: `policy_tool.py`
- Functions tôi implement: `_call_mcp_tool()`, `analyze_policy()`, và `human_review_node()`.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Worker của tôi sẽ tiếp nhận yêu cầu từ Supervisor, kết hợp với các tài liệu bối cảnh (retrieved_chunks) do retrieval_worker cung cấp. Code của tôi sẽ xử lý logic (Rule-based + LLM) để phân tích ngoại lệ và trả về quyết định cuối cùng (policy_result) cho hệ thống. Khi cần xác thực thông tin đơn hàng thực tế, file của tôi đóng vai trò là cầu nối gọi ra các API bên ngoài thông qua MCP Server (Sprint 3). Cuối cùng, toàn bộ lịch sử input/output và log lỗi từ tool của tôi sẽ là dữ liệu nền tảng quan trọng để team trace luồng và đánh giá hiệu năng hệ thống trong Sprint 4.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

commit hash: e20fb43 (Add policy_tool)
commit hash: 8d952d9 (Modify policy_tool.py)

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
>
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Tôi chọn implement logic kiểm tra policy theo hướng rule-based trong policy_tool, thay vì gọi LLM để phân tích policy.

**Lý do:**

Có hai lựa chọn chính: (1) dùng LLM để hiểu context và suy luận policy, hoặc (2) dùng rule-based (keyword matching + hard-coded rules). Tôi chọn rule-based vì các policy exceptions (Flash Sale, digital product, activated product) là các điều kiện rõ ràng, có thể encode trực tiếp bằng keyword. Cách này giúp giảm latency đáng kể (không cần gọi model), tăng tính deterministic và dễ debug trong giai đoạn đầu. Ngoài ra, hệ thống đã có retrieval_worker, nên context đã tương đối structured, phù hợp với rule-based filtering.

**Trade-off đã chấp nhận:**

Rule-based kém linh hoạt, dễ bỏ sót các cách diễn đạt khác nhau và khó scale khi policy phức tạp hơn.

**Bằng chứng từ trace/code:**

```python
# Exception 1: Flash Sale
if "flash sale" in task_lower or "flash sale" in context_text:
    exceptions_found.append({
        "type": "flash_sale_exception",
        "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
    })

# Exception 2: Digital product
if any(kw in task_lower for kw in ["license key", "license", "subscription", "kỹ thuật số"]):
    exceptions_found.append({
        "type": "digital_product_exception",
        "rule": "Sản phẩm kỹ thuật số không được hoàn tiền (Điều 3).",
    })
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** policy_tool không gọi MCP tool khi retrieved_chunks rỗng trong một số trường hợp.

**Symptom (pipeline làm gì sai?):**

Khi user query không có context từ retrieval_worker, pipeline vẫn tiếp tục sang bước policy analysis nhưng không có dữ liệu để kiểm tra. Kết quả là policy_applies=True dù đáng ra phải tìm thêm thông tin từ knowledge base. 

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Lỗi nằm ở worker logic + routing condition trong policy_tool. Cụ thể, MCP chỉ được gọi khi not chunks AND needs_tool=True. Tuy nhiên, trong một số flow, needs_tool không được set đúng từ supervisor, dẫn đến việc skip MCP dù thiếu context.

**Cách sửa:**

Sửa điều kiện gọi MCP: cho phép gọi khi retrieved_chunks rỗng, không phụ thuộc hoàn toàn vào needs_tool. Ví dụ: fallback tự động khi thiếu context.

**Bằng chứng trước/sau:**

- Trace trước:
[policy_tool_worker] policy_applies=True, exceptions=0
(no MCP call)

- Trace sau:
[policy_tool_worker] called MCP search_kb (mode=mock)
[policy_tool_worker] policy_applies=False, exceptions=1

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt ở việc implement policy_tool với logic rõ ràng, tách biệt giữa policy analysis và MCP tool calling.  Ngoài ra, tôi chủ động thiết kế fallback từ HTTP sang mock MCP để tránh pipeline bị crash.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa xử lý tốt các edge cases trong routing, ví dụ bug khi retrieved_chunks rỗng nhưng không gọi MCP. Logic hiện tại còn phụ thuộc nhiều vào keyword nên chưa đủ linh hoạt.

**Nhóm phụ thuộc vào tôi ở đâu?** *(Phần nào của hệ thống bị block nếu tôi chưa xong?)*

Nhóm phụ thuộc vào tôi ở phần policy decision và tool integration. Nếu worker này sai, toàn bộ pipeline sẽ đưa ra quyết định sai.

**Phần tôi phụ thuộc vào thành viên khác:** *(Tôi cần gì từ ai để tiếp tục được?)*

Tôi phụ thuộc vào retrieval worker để cung cấp context chính xác và supervisor để set needs_tool đúng.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

Tôi sẽ cải thiện routing logic trong policy_tool_worker bằng cách thêm fallback tự động khi retrieved_chunks rỗng, thay vì phụ thuộc hoàn toàn vào needs_tool. Lý do: trace cho thấy có trường hợp không có MCP call dẫn đến policy_applies=True sai. Ngoài ra, tôi sẽ thử hybrid approach (rule-based + LLM) cho analyze_policy để xử lý các câu hỏi phức tạp hơn và giảm miss cases do keyword matching.
