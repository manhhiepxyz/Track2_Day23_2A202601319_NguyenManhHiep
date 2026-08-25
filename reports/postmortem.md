# Postmortem — DR Drill Lab 23

Theo đúng template §4 "Sau Failover: Blameless Postmortem". Blameless: câu hỏi là
"hệ thống/process nào cho phép chuyện này", không phải "ai làm sai".

## 1. Timeline (mọi dòng phải có evidence path:line)

| ISO time | Sự kiện | Evidence |
|---|---|---|
| 2026-08-25T04:46:18 | outage bắt đầu | `chaos/chaos-events.jsonl:2` |
| 2026-08-25T04:46:18.4 | user đầu tiên bị ảnh hưởng | `reports/drill-final.jsonl:5` |
| 2026-08-25T04:46:34.9 | health check alert | `reports/health-events.jsonl:2` |
| 2026-08-25T04:46:48.4 | operator confirm cutover | `reports/failover-events.jsonl:5` |
| 2026-08-25T04:46:51.6 | resolved (request đầu tiên OK từ region phụ) | `reports/drill-final.jsonl:50` |

## 2. RTO/RPO đo được vs mục tiêu — gap ở bước nào?

- RTO mục tiêu: 300s · đo được: `33.6s` · gap: `+266.4s` (Tốt hơn mục tiêu)
- RPO mục tiêu: 300s · đo được: `12.82s` (`5` doc bị mất) · gap: `+287.18s` (Tốt hơn mục tiêu)
- **Bước tốn nhiều giây nhất:** `Health-check detect floor` — vì sao? Vì phải đợi đủ 3 lần fail liên tiếp (5s x 3) để chống flapping (tránh chuyển hướng nhầm khi mạng chập chờn).

## 3. Root cause (5 whys)

Không phải "vì tôi chạy chaos script". Câu hỏi: *nếu đây là outage thật, bước nào
trong runbook của tôi sẽ thất bại?*
- Runbook bán tự động hiện tại yêu cầu con người bấm Y để confirm. Nếu sự cố xảy ra lúc 3h sáng, thời gian 33.6s là không tưởng, vì người vận hành có thể mất 15 phút để tỉnh ngủ và vào gõ lệnh.
- Hệ thống DNS TTL có thể bị cache lại bởi client, khiến client không trỏ ngay sang region mới dù cutover đã thành công.

## 4. Action items (có owner + deadline)

| # | Action | Owner | Deadline | Giảm RTO/RPO bao nhiêu giây |
|---|---|---|---|---|
| 1 | Cải thiện Runbook thành Full Auto nếu mô hình AI tự tin | SRE Team | Q3 | 10-15 phút (thời gian con người) |
| 2 | Giảm DNS TTL từ 5s xuống 1s | DevOps | Q3 | 4s |

## 5. Ba câu hỏi bắt buộc trả lời

1. `interval × threshold` của bạn là bao nhiêu giây? Nó chiếm bao nhiêu % RTO?
   Là 15 giây (5s x 3). Nó chiếm gần 45% tổng thời gian RTO (15s / 33.6s).
2. Nếu hạ interval xuống 1s, RTO giảm mấy giây — và bạn trả giá gì (§4 flapping)?
   RTO sẽ giảm được khoảng 12 giây. Tuy nhiên, cái giá phải trả là cực kỳ dễ bị "flapping" — chỉ một đợt nghẽn mạng ngắn hạn 3 giây cũng sẽ khiến hệ thống hoảng loạn failover, gây chập chờn trên toàn cục.
3. Nếu outage kéo dài 6 giờ và region chính mất dữ liệu vĩnh viễn, `docs_lost` của
   bạn có nghĩa gì với khách hàng?
   Có nghĩa là 5 tài liệu cuối cùng mà khách hàng vừa tải lên trước thời điểm outage đã vĩnh viễn bốc hơi. Khách hàng sẽ không thể tìm kiếm hay chat về các văn bản đó và phải upload lại từ đầu.
