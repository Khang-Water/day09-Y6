# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Dương Khoa Điềm  
**MSSV:** 2A202600366  
**Vai trò trong nhóm:** Worker Owner (Retrieval)  
**Ngày nộp:** 14/04/2026  

---

## 1. Tôi phụ trách phần nào?

Module chính tôi chịu trách nhiệm là **retrieval_worker** trong file `workers/retrieval.py`.  
Các function tôi implement gồm: `_get_embedding_fn()`, `_get_collection()`, `retrieve_dense()`, và `run(state)`.

Ngoài phần code, tôi cũng thực hiện:
- Chạy pipeline grading và lưu kết quả vào `grading_run.jsonl`
- Viết các tài liệu phân tích hệ thống gồm:
  - `system_architecture.md`
  - `routing_decisions.md`
  - `single_vs_multi_comparison.md`

Trong hệ thống, retrieval_worker đóng vai trò **thu thập evidence** cho toàn bộ pipeline. Khi Supervisor route task về retrieval_worker, module của tôi sẽ embed query và truy xuất dữ liệu từ ChromaDB (`rag_lab`). Kết quả được lưu vào `retrieved_chunks` và `retrieved_sources` trong AgentState, sau đó được sử dụng bởi synthesis_worker để tạo câu trả lời.

Nếu retrieval không trả về dữ liệu phù hợp, hệ thống sẽ abstain thay vì sinh nội dung sai, đảm bảo không bị hallucination.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

Quyết định chính của tôi là **giữ nguyên cấu trúc retrieval pipeline và tập trung đảm bảo tính ổn định của kết quả truy xuất**, thay vì thay đổi kiến trúc hoặc re-index dữ liệu.

Trong quá trình làm việc, tôi nhận thấy hệ thống đã có sẵn ChromaDB collection (`rag_lab`) từ Day 08. Vì vậy, thay vì thay đổi hoặc rebuild dữ liệu, tôi giữ nguyên collection và tập trung vào việc:

- Chuẩn hóa embedding function  
- Đảm bảo query luôn trả về kết quả ổn định (top-k chunks)  
- Kết nối đúng giữa retrieval_worker và các worker khác qua AgentState  

Lý do của quyết định này:
- Tránh phá vỡ dữ liệu đã có  
- Giữ pipeline đơn giản, dễ debug  
- Tập trung vào độ chính xác của retrieval thay vì thay đổi toàn bộ hệ thống  

Sau khi hoàn thiện, retrieval_worker có thể trả về các chunk liên quan với độ ổn định cao cho các câu hỏi grading, giúp synthesis_worker tạo câu trả lời chính xác hơn.

---

## 3. Tôi đã sửa một lỗi gì?

Một vấn đề tôi gặp phải là **retrieval không trả về kết quả ổn định trong một số lần chạy**, dẫn đến việc pipeline không có đủ context để trả lời.

Nguyên nhân chính đến từ:
- Query embedding và vector trong database không đồng nhất trong một số lần chạy  
- Thiếu kiểm soát rõ ràng khi retrieval không có kết quả  

Cách tôi xử lý:
- Chuẩn hóa lại hàm embedding trong `_get_embedding_fn()`  
- Đảm bảo luôn trả về danh sách chunks hợp lệ (top-k)  
- Bổ sung kiểm tra khi không có dữ liệu để hệ thống chuyển sang cơ chế abstain  

Sau khi sửa, retrieval_worker:
- Luôn trả về kết quả nhất quán  
- Không gây lỗi cho pipeline downstream  
- Giúp hệ thống tránh việc trả lời sai khi thiếu dữ liệu  

---

## 4. Tôi tự đánh giá đóng góp của mình

**Điểm tôi làm tốt:**
- Xây dựng retrieval_worker ổn định, đảm bảo pipeline luôn có dữ liệu để xử lý  
- Kết nối tốt giữa retrieval và các worker khác thông qua AgentState  
- Viết tài liệu mô tả rõ ràng kiến trúc và quyết định hệ thống, hỗ trợ phần báo cáo nhóm  

**Điểm chưa tốt:**
- Chưa tối ưu hiệu năng retrieval (embedding vẫn được gọi lại nhiều lần)  
- Chưa triển khai caching hoặc tối ưu latency cho pipeline  

**Sự phụ thuộc trong hệ thống:**
- synthesis_worker phụ thuộc trực tiếp vào retrieved_chunks từ retrieval_worker  
- Nếu retrieval không hoạt động đúng, toàn bộ pipeline sẽ không thể trả lời chính xác  

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì?

Tôi sẽ tối ưu hiệu năng retrieval bằng cách:
- Implement caching cho embedding function  
- Giảm số lần gọi embedding lặp lại  

Điều này sẽ giúp giảm đáng kể latency của toàn pipeline, đặc biệt khi chạy nhiều câu hỏi trong grading.