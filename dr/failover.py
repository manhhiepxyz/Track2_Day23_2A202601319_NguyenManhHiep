"""BƯỚC 3b — SINH VIÊN VIẾT. Cutover sang region phụ.

5 bước, THỨ TỰ QUAN TRỌNG (§2 Kiến Trúc Tham Chiếu: DNS/LB, compute, state là 3 lớp riêng):
  1_verify_target    — /v1/state của region phụ: weights? vector count? pool_state?
  2_restore_snapshot — gọi state/snapshot.py get + state/snapshot.py rpo()
                       Log BẮT BUỘC: rpo_seconds, docs_lost, embed_model_version.
                       (§3: "backup index nhưng quên backup embedding model version
                        -> index không tương thích khi restore")
  3_scale_pool       — ghi "full" vào state/region-<t>/pool_state (warm -> full)
  4_wait_ready       — POLL /readyz tới khi 200. Region phụ có WARMUP_SECONDS —
                       đây là GPU pool warm-up của §4, nó nằm trong RTO của bạn.
  5_dns_cutover      — ghi region đích vào edge/active_region

BẪY: nếu bạn đổi edge/active_region TRƯỚC bước 4, user sẽ nhận 503 từ CẢ HAI region
và RTO của bạn dài hơn, không ngắn hơn. Nếu bước 4 timeout -> ABORT, KHÔNG cutover.

Mỗi bước ghi 1 dòng vào reports/failover-events.jsonl với ts + step.
Không có dòng 5_dns_cutover = tools/measure_rto.py không tìm được t_cutover = mất điểm.

Chạy:  python dr/failover.py --target b --backend fs
"""
import argparse
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, ".")
from state import snapshot  # noqa: E402

URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}
LOG = pathlib.Path("reports/failover-events.jsonl")


from datetime import datetime

def emit(**kw):
    """Append 1 dòng JSONL có ts + iso vào LOG, và print ra stdout."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    iso = datetime.fromtimestamp(ts).isoformat()
    record = {"ts": ts, "iso": iso, **kw}
    line = json.dumps(record)
    
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line)


def failover(target: str, backend: str, wait: float) -> dict:
    """5 bước ở trên, đúng thứ tự."""
    # Bước 1: 1_verify_target
    try:
        r = httpx.get(f"{URL[target]}/v1/state", timeout=2.0)
        state_info = r.json()
    except Exception as e:
        state_info = {"error": str(e)}
    emit(step="1_verify_target", state=state_info)
    
    # Bước 2: 2_restore_snapshot
    snapshot.get(target, backend)
    primary = "a" if target == "b" else "b"
    rpo_stats = snapshot.rpo(
        pathlib.Path(f"state/region-{primary}/vectors.sqlite"),
        pathlib.Path(f"state/region-{target}/vectors.sqlite")
    )
    emit(
        step="2_restore_snapshot", 
        rpo_seconds=rpo_stats.get("rpo_seconds", 0),
        docs_lost=rpo_stats.get("docs_lost", 0),
        embed_model_version=rpo_stats.get("embed_model_version", "unknown")
    )
    
    # Bước 3: 3_scale_pool
    pool_state_file = pathlib.Path(f"state/region-{target}/pool_state")
    pool_state_file.write_text("full")
    emit(step="3_scale_pool", action="set pool_state to full")
    
    # Bước 4: 4_wait_ready
    start_wait = time.time()
    ready = False
    while time.time() - start_wait < wait:
        try:
            r = httpx.get(f"{URL[target]}/readyz", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(1)
        
    if not ready:
        emit(step="4_wait_ready_timeout", msg=f"Target {target} not ready after {wait}s. ABORT.")
        return {"ok": False, "status": "aborted", "error": "target not ready"}
        
    emit(step="4_wait_ready", duration=time.time() - start_wait)
    
    # Bước 5: 5_dns_cutover
    pathlib.Path("edge/active_region").write_text(target)
    emit(step="5_dns_cutover", active_region=target)
    
    return {"status": "success", "target": target, "rpo": rpo_stats}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--target", default="b", choices=["a", "b"])
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--wait", type=float, default=60)
    a = p.parse_args()
    print(json.dumps(failover(a.target, a.backend, a.wait), indent=2))
