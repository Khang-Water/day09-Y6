# Báo Cáo Cá Nhân - Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Lê Minh Khang  
**Vai trò trong nhóm:** Trace owner  
**Ngày nộp:** 4/14/2026  
**Độ dài yêu cầu:** 500-800 từ

---

## 1. Tôi phụ trách phần nào? (100-150 từ)

Trong nhóm, tôi phụ trách luồng đánh giá trace và tổng hợp kết quả ở file `eval_trace.py`. Phần tôi trực tiếp implement/chỉnh sửa gồm `run_test_questions()`, `run_grading_questions()`, `analyze_traces()`, `compare_single_vs_multi()`, và `save_eval_report()`. Công việc của tôi nối với phần graph/worker vì evaluator đọc các trường pipeline trả về như `supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`, `hitl_triggered`, `latency_ms`. Nếu trace schema từ graph đổi, phần eval của tôi phải cập nhật ngay để báo cáo không sai. Bằng chứng chính: commit `6c924cb`, file `eval_trace.py`, và output thật từ lệnh `python eval_trace.py --analyze`.

---

## 2. Tôi đã đưa ra quyết định kỹ thuật gì? (150-200 từ)

**Quyết định:** Tôi chọn chuẩn hóa dữ liệu đầu vào của evaluator ngay trong code thay vì giả định tất cả trace luôn cùng định dạng.

Lý do là trace thực tế có nhiều kiểu dữ liệu: dạng số, dạng chuỗi phần trăm (`"5/106 (4.7%)"`), và baseline Day08 có lúc thiếu dữ liệu. Nếu parse cứng một kiểu thì báo cáo dễ sai. Tôi thêm `_to_float()` để parse số linh hoạt, `_normalize_day08_baseline()` để gom nhiều schema Day08 về một chuẩn, và `_normalize_for_abstain()` + `_is_abstain()` để nhận diện câu trả lời từ chối nhất quán hơn.

So với phương án thay thế (xử lý thủ công trong notebook sau mỗi lần chạy), cách này giúp báo cáo tự động, reproducible và chạy được qua CLI cho cả nhóm. Trade-off tôi chấp nhận là file `eval_trace.py` dài hơn và logic parse phức tạp hơn, cần test kỹ khi thêm field mới.

Bằng chứng từ trace/code: `eval_trace.py` dòng 333-347 có các metric chuẩn hóa (`mcp_usage_rate`, `hitl_rate`, `abstain_rate`, `route_reason_missing_rate`), và output hiện tại cho thấy `route_reason_missing_rate: 0/106 (0.0%)`, chứng minh pipeline trace đủ thông tin để debug.

---

## 3. Tôi đã sửa một lỗi gì? (150-200 từ)

**Lỗi:** Nguy cơ ghi đè trace file khi chạy nhiều lượt trong thời gian rất gần nhau.

Symptom tôi gặp là khi chạy batch liên tục, việc map một câu hỏi cụ thể với đúng trace khó theo dõi, đặc biệt trong các cụm file có suffix thời gian trùng theo giây. Rủi ro là mất trace khi `run_id` bị đụng ở các lần chạy sát nhau.

Root cause nằm ở chỗ `save_trace()` (trong `graph.py`) ghi file theo `state['run_id']`, trong khi trước đó `run_id` chưa được tăng entropy ở tầng evaluator. Nếu một câu được chạy lại nhanh, có thể đụng tên file cũ.

Cách sửa của tôi là bổ sung bước tạo `run_id` duy nhất trước khi gọi `save_trace()` trong `run_test_questions()`: gắn thêm `question_id` và microsecond (`datetime.now().strftime('%f')`). Đoạn sửa nằm ở `eval_trace.py` dòng 142-145.

Bằng chứng trước/sau:
- Trước: naming phụ thuộc `run_id` gốc, dễ va chạm khi chạy dày.
- Sau: mỗi trace có hậu tố riêng (`..._{q_id}_{microsecond}`), và thống kê hiện tại `total_traces: 106`, `trace_files: 106` cho thấy không còn thất thoát file trong tập trace đang phân tích.

---

## 4. Tôi tự đánh giá đóng góp của mình (100-150 từ)

Điểm tôi làm tốt nhất là biến trace từ dữ liệu thô thành dữ liệu có thể chấm và debug: có metric, có report JSON, có log grading JSONL để kiểm chứng từng câu. Tôi cũng chủ động thiết kế evaluator theo hướng “chịu lỗi dữ liệu” (schema không đồng nhất vẫn chạy được), nên giảm rủi ro sát deadline.

Điểm tôi còn yếu là chưa tách metric theo từng run batch. Hiện tại analyzer đọc toàn bộ `artifacts/traces`, nên các trace cũ (bao gồm những trace latency thấp/0 từ giai đoạn đầu) có thể làm méo một vài chỉ số như `p50_latency_ms`.

Nhóm phụ thuộc vào tôi ở phần tổng hợp bằng chứng nộp: nếu không có phần trace analysis thì khó chứng minh chất lượng hệ thống. Ngược lại, tôi phụ thuộc vào các bạn phụ trách `graph.py`, retrieval và policy worker để trace đầu vào đủ giàu thông tin.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50-100 từ)

Tôi sẽ thêm bộ lọc theo run (ví dụ `--run-prefix` hoặc `--since`) cho `analyze_traces()` để chỉ phân tích đúng một phiên chạy mới nhất. Lý do: số liệu hiện tại có dấu hiệu nhiễu lịch sử, cụ thể `avg_latency_ms` là `2653.36` nhưng `p50_latency_ms` lại `0.0`, cho thấy trace cũ đang kéo lệch phân bố. Cải tiến này giúp báo cáo công bằng hơn cho từng lần benchmark.
