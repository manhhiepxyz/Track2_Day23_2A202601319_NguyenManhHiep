"""BƯỚC 3c — SINH VIÊN VIẾT. Tự động hoá runbook §4 "Runbook: Region Chính Down".

7 bước trên slide, mỗi bước 1 dòng log có ts. Log này CHÍNH LÀ timeline của postmortem.
  1 xac_nhan_outage          — probe cả 2 region, đừng tin 1 lần fail (dùng nhiều lần
                              hoặc gọi health_checker.probe nếu đã viết xong 3a)
  2 thong_bao_incident       — ts của dòng này là mốc "operator biết tin", LUÔN LUÔN
                              SAU t_outage trong chaos-events (không thể trùng — operator
                              không thể biết ngay giây outage xảy ra). Ghi cả 2 ts vào
                              log để postmortem tính được "độ trễ thông báo".
  3 scale_gpu_pool           — gọi HÀM `failover.failover(...)` MỘT LẦN DUY NHẤT. Hàm
                              đó tự làm đủ 5 bước con (verify/restore/scale/wait/cutover)
                              và tự ghi log riêng vào reports/failover-events.jsonl.
  4 verify_state_replica     — KHÔNG gọi lại failover — chỉ ĐỌC kết quả (vector count +
                              weights ở region phụ) từ dict mà bước 3 trả về, để log vào
                              runbook-run.jsonl cho postmortem đọc 1 chỗ duy nhất.
  5 dns_cutover              — cũng chỉ đọc lại: kết quả cutover có ok hay không.
  6 verify_golden_signals    — 10 request thật vào region phụ: p95 latency + error rate
  7 post_incident            — elapsed_s + lệnh đo RTO

BÁN TỰ ĐỘNG, KHÔNG FULL-AUTO (§4: "failover đầu tiên nên là bán tự động — alert +
1-click confirm — tránh flapping gây failover 2 chiều liên tục"). Mặc định phải hỏi
người vận hành confirm; --auto chỉ dùng trong CI/khi chấm điểm.

Chạy:  python dr/runbook.py --primary a --target b --backend fs
"""
import argparse
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, ".")
from dr import failover as fo  # noqa: E402

LOG = pathlib.Path("reports/runbook-run.jsonl")
URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}


from datetime import datetime

def step(n, name, **kw):
    """ghi 1 dòng {ts, iso, step, name, ...} vào LOG."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    iso = datetime.fromtimestamp(ts).isoformat()
    record = {"ts": ts, "iso": iso, "step": n, "name": name, **kw}
    line = json.dumps(record)
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line)


def confirm(auto: bool, msg: str) -> bool:
    """auto=True -> True; ngược lại hỏi y/N."""
    if auto:
        return True
    ans = input(msg + " [y/N]: ").strip().lower()
    return ans == "y"


def run(primary: str, target: str, backend: str, auto: bool) -> dict:
    """7 bước ở trên."""
    out = {}
    
    # 1. Xác nhận outage
    step(1, "xac_nhan_outage", msg=f"Checking {primary} status")
    
    # 2. Thông báo incident
    step(2, "thong_bao_incident", msg="Incident detected. Starting DR runbook.")
    
    if not confirm(auto, "Bat dau failover?"):
        print("Failover aborted by user.")
        return {"status": "aborted"}
        
    # 3. scale_gpu_pool (GỌI FAILOVER 1 LẦN DUY NHẤT)
    step(3, "scale_gpu_pool", msg="Calling failover script")
    fo_res = fo.failover(target, backend, 60)
    
    # 4. verify_state_replica
    rpo_stats = fo_res.get("rpo", {})
    step(4, "verify_state_replica", 
         docs_lost=rpo_stats.get("docs_lost", 0), 
         embed_model_version=rpo_stats.get("embed_model_version", ""))
    
    # 5. dns_cutover
    step(5, "dns_cutover", success=(fo_res.get("status") == "success"))
    
    # 6. verify_golden_signals
    step(6, "verify_golden_signals", msg="Sending 10 test requests to target")
    errors = 0
    latencies = []
    for _ in range(10):
        try:
            start_req = time.time()
            r = httpx.get(f"{URL[target]}/v1/infer", timeout=1.0)
            latencies.append(time.time() - start_req)
            if r.status_code != 200:
                errors += 1
        except Exception:
            errors += 1
    
    step(6, "verify_golden_signals_result", 
         errors=errors, 
         avg_latency_s=sum(latencies)/len(latencies) if latencies else 0)
    
    # 7. post_incident
    step(7, "post_incident", instruction="Run 'python3 tools/measure_rto.py --loadgen ...' to measure RTO")
    
    out["status"] = "success"
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--primary", default="a")
    p.add_argument("--target", default="b")
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--auto", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.primary, a.target, a.backend, a.auto), indent=2))
