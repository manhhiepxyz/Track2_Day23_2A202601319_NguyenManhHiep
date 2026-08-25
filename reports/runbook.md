# Runbook 1 trang — Region chính down

Runbook phải chạy được lúc 3h sáng bởi người KHÔNG viết nó. Mỗi bước: lệnh copy-paste
được + cách biết bước đó xong.

| # | Bước | Lệnh | Biết là xong khi | Ai làm |
|---|---|---|---|---|
| 1 | Xác nhận outage | `python chaos/kill_region.py status` | `a.alive=false` 3 lần liên tiếp | on-call |
| 2 | Mở incident + bấm giờ RTO | `python3 dr/runbook.py --primary a --target b --backend fs` | ts ghi vào `reports/runbook-run.jsonl` | on-call |
| 3 | Restore state ở region phụ | (Tự động trong runbook) | Log in ra `docs_lost` | automation |
| 4 | Scale pool warm→full | (Tự động trong runbook) | `/readyz` của b trả 200 | automation |
| 5 | DNS/LB cutover | (Tự động trong runbook) | `curl localhost:8080/edge/state` cho `active_region=b` | automation |
| 6 | Verify golden signals | (Tự động trong runbook) | p95 < 100ms, error rate = 0 | automation |
| 7 | Đo RTO + postmortem | `python tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300` | `rto_verdict` = PASS | on-call |

**Rollback (failover ngược):** điều kiện nào thì trả traffic về region A? Ai quyết định?
(§4 Anti-Patterns: full-auto không có circuit breaker → 2 region flap qua lại.)
- **Điều kiện:** Trả traffic về Region A khi và chỉ khi Region A đã online ổn định trở lại (ví dụ: pass toàn bộ health check liên tục trong 15 phút), VÀ dữ liệu mới từ Region B đã được replicate (đồng bộ) ngược lại A đầy đủ 100%.
- **Ai quyết định:** Việc Fallback (Rollback) TUYỆT ĐỐI không bao giờ được auto. Nó phải được quyết định và bấm nút thực hiện bằng tay bởi Engineering Manager hoặc Incident Commander sau khi đã confirm thủ công, nhằm tránh hiện tượng split-brain hoặc flapping hai chiều.
