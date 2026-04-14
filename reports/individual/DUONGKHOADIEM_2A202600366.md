# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Dương Khoa Điềm  
**MSSV:** 2A202600366  
**Vai trò trong nhóm:** Worker Owner (Retrieval)  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.

**Module/file tôi chịu trách nhiệm:**

- File chính: `workers/retrieval.py`
- Functions tôi implement: `_get_embedding_fn()`, `_get_collection()`, `retrieve_dense()`, `run(state)`
- Ngoài ra: chạy pipeline grading (`artifacts/grading_run.jsonl` — 10 câu grading questions), viết tài liệu nhóm (`docs/system_architecture.md`, `docs/routing_decisions.md`, `docs/single_vs_multi_comparison.md`)

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`retrieval_worker` là bước **thu thập bằng chứng** (evidence) cho toàn hệ thống. Khi `supervisor_node` của Hoàng Thị Thanh Tuyền route câu hỏi về `retrieval_worker`, module của tôi sẽ embed query và truy xuất ChromaDB `rag_lab`, sau đó ghi `retrieved_chunks` và `retrieved_sources` vào `AgentState` để `synthesis_worker` của Võ Thanh Chung tổng hợp câu trả lời. Nếu `retrieved_chunks` rỗng, hệ thống sẽ abstain thay vì hallucinate — đây là cơ chế chống bịa thông tin cốt lõi.

**Bằng chứng:** Commit `f4fb746` ("report retrival"), commit `b995f2f` ("grading"), và toàn bộ file `workers/retrieval.py` có comment `# DƯƠNG KHOA ĐIỀM - 2A202600366` ở dòng đầu.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Ưu tiên OpenAI Embedding API (1536 dims) thay vì SentenceTransformers (384 dims) khi khởi tạo `_get_embedding_fn()`, và cấu hình endpoint trỏ về Azure AI Inference thay vì OpenAI trực tiếp.

**Lý do:**

Khi kết nối với ChromaDB collection `rag_lab` (kế thừa từ Day 08), tôi phát hiện collection này đã được index bằng vector 1536 chiều (OpenAI). File boilerplate gốc mặc định chạy SentenceTransformers (384 chiều) — gây ra lỗi `Collection expecting embedding with dimension of 1536, got 384`, khiến retrieval trả về 0 chunks cho mọi câu hỏi.

Các lựa chọn thay thế tôi cân nhắc là: (1) Re-index toàn bộ `rag_lab` bằng SentenceTransformers — mất thời gian và mất dữ liệu cũ, (2) Dùng OpenAI API với endpoint chuẩn — nhưng nhóm dùng GitHub Models qua Azure endpoint nên URL khác, (3) Cấu hình lại `_get_embedding_fn()` để ưu tiên OpenAI (có `OPENAI_API_KEY`) và trỏ `base_url` về Azure Inference endpoint.

Tôi chọn phương án 3 vì không cần re-index, tận dụng được collection đã có và tương thích với cách nhóm cấu hình API.

**Bằng chứng từ code:**

```python
# Ưu tiên OpenAI trước nếu có API key
if os.getenv("OPENAI_API_KEY"):
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url="https://models.inference.ai.azure.com"
    )
    def embed(text: str) -> list:
        resp = client.embeddings.create(input=text, model="text-embedding-3-small")
        return resp.data[0].embedding
    return embed
```

Sau khi sửa, retrieval trả về đúng 3 chunks với score ~0.5–0.6 cho mọi query test, và grading pipeline chạy thành công 10/10 câu.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** `UnicodeEncodeError` khi chạy `python workers/retrieval.py` trên Windows Terminal khiến test script crash ngay khi in ra kết quả.

**Symptom (pipeline làm gì sai?):**

Khi chạy standalone test (`python workers/retrieval.py`), script crash với lỗi:
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u25b6' in position 2
```
Tuy nhiên trước đó, hệ thống đã gọi được embedding nhưng lại báo `WARNING: ChromaDB query failed: Collection expecting embedding with dimension of 1536, got 384` — tức là có 2 lỗi chồng nhau.

**Root cause:**

Lỗi 1 (UnicodeEncodeError): File gốc dùng Emoji `▶`, `✅`, `⚠️` trong câu `print()`. Windows Terminal mặc định dùng encoding `cp1252` không hỗ trợ các ký tự này.

Lỗi 2 (Dimension mismatch): Như đã mô tả ở Mục 2 — SentenceTransformers (384 dim) không khớp với ChromaDB collection (1536 dim).

**Cách sửa:**

- Lỗi 1: Thay toàn bộ Emoji bằng ký tự ASCII thuần (`->`, `[OK]`, `WARNING:`)
- Lỗi 2: Đảo thứ tự ưu tiên trong `_get_embedding_fn()`, đặt OpenAI lên trước và bổ sung `base_url` Azure endpoint; đồng thời sửa `except ImportError` thành `except Exception` để bắt được lỗi cấu hình, không chỉ lỗi import.

**Bằng chứng trước/sau:**

```python
# Trước (crash):
client = OpenAI(api_key=OPENAI_API_KEY, ...)  # NameError ngầm

# Sau khi sửa (hoạt động):
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="...")
```

Sau khi sửa, test script chạy đủ 3 queries, trả về chunks chính xác từ các file `sla-p1-2026.pdf`, `refund-v4.pdf`, `access-control-sop.md`.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Chẩn đoán và xử lý vấn đề môi trường (environment debugging) nhanh. Khi phát hiện mismatch dimension, tôi không re-index lại từ đầu mà tìm cách giữ nguyên dữ liệu cũ và chỉ sửa cấu hình embedding phía client — tránh mất thời gian của cả nhóm. Ngoài ra, việc viết đầy đủ tài liệu docs giúp nhóm có bằng chứng rõ ràng cho phần chấm điểm Group Documentation.

**Tôi làm chưa tốt ở điểm nào?**

Embedding model hiện tại load lại mỗi lần query (không cache). Với 106 traces trong eval, đây là overhead không cần thiết — mỗi query phải tải lại model weights, tốn ~500–1000ms.

**Nhóm phụ thuộc vào tôi ở đâu?**

`synthesis_worker` của Võ Thanh Chung phụ thuộc hoàn toàn vào `retrieved_chunks` tôi trả về để tổng hợp câu trả lời. Nếu `retrieval_worker` trả về danh sách rỗng (do lỗi ChromaDB hoặc embedding sai), synthesis sẽ không có context và tự động abstain — toàn bộ câu trả lời của nhóm bị mất điểm.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần `graph.py` của Hoàng Thị Thanh Tuyền định nghĩa đúng `AgentState` với các fields `retrieved_chunks`, `retrieved_sources`, `worker_io_logs` — để `run(state)` của tôi có thể ghi vào đúng vị trí mà các worker khác sẽ đọc ra sau.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ implement **embedding cache** để tránh load model lại mỗi lần query. Lý do cụ thể từ trace: `eval_report.json` cho thấy `avg_latency_ms = 2653ms` trên 106 traces, nhưng khi đo riêng grading_run thì nhiều câu mất 12,000–49,000ms — phần lớn là do embedding call lặp lại.

Cụ thể tôi sẽ thêm singleton pattern cho `_get_embedding_fn()`:
```python
_embed_fn_cache = None
def _get_embedding_fn():
    global _embed_fn_cache
    if _embed_fn_cache is None:
        _embed_fn_cache = _build_embed_fn()
    return _embed_fn_cache
```

Điều này ước tính giảm latency trung bình xuống còn < 5,000ms/câu cho toàn grading pipeline.
