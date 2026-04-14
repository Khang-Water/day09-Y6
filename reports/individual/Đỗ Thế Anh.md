# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đỗ Thế Anh  
**Vai trò trong nhóm:** MCP Owner  
**Ngày nộp:** 14/04/2026  
**Mã học viên** 2A202600040

---

## 1. Tôi phụ trách phần nào?

Trong lab này tôi phụ trách phần MCP, cụ thể là xây dựng lớp tool interface trong file `mcp_server.py`. Tôi implement các hàm chính gồm `tool_search_kb()`, `tool_get_ticket_info()`, `tool_check_access_permission()`, `tool_create_ticket()`, cùng với `list_tools()` và `dispatch_tool()` để worker có thể gọi tool theo đúng kiểu MCP thay vì hard-code logic ở nhiều nơi. Phần việc của tôi kết nối trực tiếp với `workers/policy_tool.py`: khi supervisor trong `graph.py` gắn cờ `needs_tool=True`, policy worker sẽ gọi `_call_mcp_tool()` để lấy dữ liệu từ knowledge base hoặc kiểm tra quyền truy cập. Kết quả từ MCP sau đó được đẩy tiếp sang synthesis worker để tạo câu trả lời cuối cùng. Nói cách khác, nếu phần của tôi chưa xong thì pipeline vẫn chạy được, nhưng sẽ thiếu external capability và mất luôn log trace cho các tool call.

**Bằng chứng:** trace `run_20260414_170721_q03_082746` ghi rõ:
- `[policy_tool_worker] called MCP search_kb `
- `[policy_tool_worker] called MCP check_access_permission `

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn làm một lớp MCP server có schema + dispatch rõ ràng, thay vì nhúng trực tiếp logic tra cứu vào policy worker.

**Lý do:** Điểm tôi muốn giải quyết là tính tách biệt giữa orchestration và capability. Nếu `policy_tool_worker` tự import từng hàm business logic rồi gọi thẳng, nhóm sẽ rất khó mở rộng và khó trace: worker biết quá nhiều về implementation của từng tool. Vì vậy tôi thiết kế `TOOL_SCHEMAS` để mô tả input/output, `TOOL_REGISTRY` để map tên tool với hàm thực thi, và `dispatch_tool()` để thống nhất cách gọi. Nhờ cách này, cùng một worker có thể gọi `search_kb`, `get_ticket_info` hoặc `check_access_permission` mà không cần đổi flow ở graph. Đây cũng là nền để sau này chuyển từ mock mode sang FastMCP/HTTP mode mà code phía client gần như giữ nguyên.

**Trade-off đã chấp nhận:** Tôi chấp nhận thêm một lớp abstraction và chi phí maintain schema. Cách này không nhanh bằng việc gọi thẳng Python function, nhưng đổi lại hệ thống rõ ràng hơn, trace tốt hơn, và đúng tinh thần Day 09 là observability + extensibility.

**Bằng chứng từ trace/code:**

```python
TOOL_REGISTRY = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
}

def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    tool_fn = TOOL_REGISTRY[tool_name]
    return tool_fn(**tool_input)
```

---

## 3. Tôi đã sửa một lỗi gì?
**Lỗi:** Policy worker dễ mất dữ liệu tool hoặc trả lời kém ổn định khi đường gọi MCP không sẵn sàng.

**Symptom (pipeline làm gì sai?):** Ở nhiều trace cũ, trường `mcp_tools_used` bị rỗng dù câu hỏi thuộc nhóm policy/access. Điều này làm câu trả lời vẫn có thể ra, nhưng thiếu cảm giác “đã dùng tool thật”, và khó chứng minh rằng pipeline có external capability đúng như yêu cầu Sprint 3. Trong báo cáo tổng hợp, `mcp_usage_rate` cũng chỉ ở mức `5/106 (4.7%)`.

**Root cause:** Gốc lỗi nằm ở lớp integration giữa worker và MCP. Nếu chỉ phụ thuộc vào một đường gọi duy nhất, ví dụ HTTP server chưa bật hoặc retrieval không trả về chunk, policy worker sẽ thiếu fallback và log không nhất quán. Nói ngắn gọn: contract gọi tool chưa đủ resilient.

**Cách sửa:** Tôi bổ sung cơ chế `_call_mcp_tool()` trong `workers/policy_tool.py` để hỗ trợ cả `http` và `mock`, đồng thời fallback về mock nếu HTTP thất bại. Ở `mcp_server.py`, tôi cũng cho `search_kb()` fallback từ dense retrieval sang lexical search trên thư mục docs khi index chưa sẵn sàng. Nhờ vậy pipeline không bị gãy và trace luôn ghi được tool call theo một format thống nhất.

**Bằng chứng trước/sau:**

```text
Trước: nhiều trace chỉ có "mcp_tools_used": []
Sau: run_20260414_170721_q03_082746 ghi đủ
- tool: search_kb
- tool: check_access_permission
- final_answer: Line Manager + IT Admin + IT Security
```

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt ở việc biến yêu cầu “thêm MCP” thành một giao diện có thể dùng thật trong pipeline, không chỉ là mock cho có. Tôi chú ý khá nhiều đến schema, fallback và log trace nên phần của tôi giúp nhóm debug dễ hơn.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa đẩy phần MCP lên mức hoàn chỉnh hơn như HTTP server chạy ổn định 100% hoặc thêm nhiều tool thực tế hơn. Ngoài ra, tỉ lệ MCP usage vẫn còn thấp do một số câu hỗn hợp bị route sang retrieval trước.

**Nhóm phụ thuộc vào tôi ở đâu?**

Nếu tôi chưa xong, policy worker sẽ không có lớp external tool chung để tra KB, tra ticket hoặc check access; trace cũng khó chứng minh được `mcp_tool_called`.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi phụ thuộc vào supervisor owner ở phần routing `needs_tool`, và phụ thuộc vào worker owner để policy worker tiêu thụ output từ MCP đúng contract.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? 

Tôi sẽ cải tiến routing cho các câu “lai” giữa incident và access control. Ví dụ ở câu gq06, truy vấn có cả `P1` lẫn `cấp quyền tạm thời`, nhưng trace vẫn route sang retrieval worker nên MCP access check không được tận dụng. Nếu có thêm thời gian, tôi sẽ đề xuất rule ưu tiên `policy_tool_worker` hoặc dual-route cho nhóm câu này để tăng chất lượng answer và tăng MCP usage rate.

---
