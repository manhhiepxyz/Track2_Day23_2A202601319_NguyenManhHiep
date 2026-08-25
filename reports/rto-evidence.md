# RTO/RPO Evidence — Lab 23

Quy tắc duy nhất: mỗi con số ở đây phải trỏ được về **một dòng log thật**
(`đường/dẫn.jsonl:số_dòng`). `pytest tests/test_rto_evidence.py` sẽ mở từng file ra kiểm tra.
Con số không có evidence = trượt, bất kể các phần khác.

## 1. Drill 1 — không có DR (baseline)

| Chỉ số | Giá trị | Cách đo | Evidence |
|---|---|---|---|
| t_outage | `2026-08-25T04:57:40` | chaos kill | `chaos/chaos-events.jsonl:3` |
| Request fail đầu tiên | `+0.1s` | dòng `ok:false` đầu tiên sau t_outage | `reports/drill-1-nodr.jsonl:17` |
| Request thành công sau đó | không có | không có dòng `ok:true` nào sau t_outage | `reports/measure-drill-1.json` |
| RTO | `NO_RECOVERY` | `tools/measure_rto.py` | `reports/measure-drill-1.json` |

## 2. Drill 2 — có DR

| Mốc | +giây từ t_outage | Cách đo | Evidence |
|---|---|---|---|
| t_outage (mốc 0) | 0 | `action:kill` | `chaos/chaos-events.jsonl:2` |
| User thấy lỗi đầu tiên | 0.4s | dòng `ok:false` đầu | `reports/drill-2-withdr.jsonl:5` |
| Health check phát hiện | 16.9s | `to:UNHEALTHY, region:a` | `reports/health-events.jsonl:2` |
| Snapshot restore xong | 29.8s | `step:2_restore_snapshot` | `reports/failover-events.jsonl:3` |
| Region phụ ready | 29.8s | `step:4_wait_ready` | `reports/failover-events.jsonl:4` |
| DNS cutover | 29.8s | `step:5_dns_cutover` | `reports/failover-events.jsonl:5` |
| **RTO đo được** | 33.6s | dòng `ok:true` đầu sau lỗi | `reports/drill-2-withdr.jsonl:50` |

| Chỉ số | Đo được | Mục tiêu (slide §1) | Verdict |
|---|---|---|---|
| RTO — Inference API | `33.6s` | 300s (5 phút) | PASS |
| RPO — Vector DB | `12.82s` / `5` doc | 300s (5 phút) | PASS |

## 3. RTO của tôi gồm những gì (bắt buộc — đây là phần chấm điểm hiểu bài)

| Thành phần | Giây | Nó đến từ đâu | Giảm được bằng cách nào |
|---|---|---|---|
| Health-check detect floor | 15s | `interval_s × threshold` trong `reports/health-events.jsonl:2` | Giảm interval hoặc threshold (cần cân bằng chống flapping) |
| Snapshot restore | 10-15s | 2_restore → 3_scale | Dùng object storage xịn hơn hoặc snapshot nhỏ hơn |
| GPU pool warm-up | 6.1s | `waited_s` ở `4_wait_ready` | Giữ pool "hot" thay vì "warm" (tốn tiền) |
| DNS/LB TTL cache | 3.8s | t_recovered − t_cutover | Giảm TTL của DNS xuống mức thấp nhất |
