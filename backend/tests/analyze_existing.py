"""Analyze an already-uploaded video by id, with job options.

Run: python tests/analyze_existing.py <video_id> [tile_grid] [sample_step]
Avoids passing JSON through PowerShell, which mangles the quotes.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(path, method="GET", data=None, token=None, timeout=600):
    headers = {}
    if token:
        headers["x-auth-token"] = token
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def main():
    vid = int(sys.argv[1])
    opts = {}
    if len(sys.argv) > 2 and sys.argv[2] not in ("", "0"):
        opts["tile_grid"] = int(sys.argv[2])
    if len(sys.argv) > 3:
        opts["sample_step"] = int(sys.argv[3])

    st, r = req("/api/auth/register", "POST",
                {"email": f"run{int(time.time())}@test.local",
                 "name": "Runner", "password": "run123456"})
    token = r["token"] if st == 200 else req(
        "/api/auth/login", "POST",
        {"email": "demo@retailvision.local", "password": "demo1234"})[1]["token"]

    st, job = req(f"/api/videos/{vid}/analyze", "POST", opts, token)
    assert st == 200, job
    jid = job["id"]
    print("job", jid, "options", opts)

    t0 = time.time()
    while True:
        st, j = req(f"/api/jobs/{jid}", token=token)
        el = time.time() - t0
        print(f"  [{el:6.0f}s] {j.get('status')} {j.get('progress')}% {j.get('stage') or ''}")
        if j.get("status") in ("done", "failed"):
            break
        if el > 5400:
            raise SystemExit("timeout")
        time.sleep(15)
    if j.get("status") != "done":
        raise SystemExit(f"job failed: {j.get('error')}")

    aid = j["analysis"]["id"]
    st, a = req(f"/api/analyses/{aid}", token=token)
    an = a["analysis"]
    print("\n=== ANALYSIS", aid, "===")
    for k in ("processed_frames", "inference_device", "inference_ms_avg",
              "total_detections", "unique_visits_est", "avg_occupancy",
              "max_occupancy", "dwell_avg_s", "dwell_p50_s"):
        print(f"  {k}: {an.get(k)}")
    print("  scene:", an.get("scene"))
    st, ev = req(f"/api/analyses/{aid}/events", token=token)
    print("  events:", len(ev))
    print("\nOPEN:", f"{BASE}/#/analysis/{aid}")


if __name__ == "__main__":
    main()
