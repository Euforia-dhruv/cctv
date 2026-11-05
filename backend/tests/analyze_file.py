"""Upload one video through the real API and analyze it, then print results.

Run: python tests/analyze_file.py <video> [base_url]
"""
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = (sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000").rstrip("/")
VIDEO = sys.argv[1]


def req(path, method="GET", data=None, token=None, raw=None, ctype=None, timeout=600):
    headers = {}
    if token:
        headers["x-auth-token"] = token
    body = None
    if raw is not None:
        body = raw
        headers["Content-Type"] = ctype
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            text = resp.read().decode()
            try:
                return resp.status, json.loads(text)
            except json.JSONDecodeError:
                return resp.status, text
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def multipart(fields, files):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (fname, path) in files.items():
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; "
                     f"filename=\"{fname}\"\r\nContent-Type: {ctype}\r\n\r\n".encode())
        with open(path, "rb") as f:
            parts.append(f.read())
        parts.append(b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


def main():
    email = f"yt{uuid.uuid4().hex[:6]}@test.local"
    st, r = req("/api/auth/register", "POST",
                {"email": email, "name": "YT Analyst", "password": "yt123456"})
    assert st == 200, r
    token = r["token"]
    st, store = req("/api/stores", "POST", {"name": "Mall CCTV Wall"}, token)
    assert st == 200, store

    body, ctype = multipart(
        {"store_id": store["id"], "consent": "1"},
        {"file": (os.path.basename(VIDEO), VIDEO)})
    print(f"uploading {os.path.getsize(VIDEO)/1e6:.0f} MB ...")
    st, video = req("/api/videos", "POST", token=token, raw=body, ctype=ctype, timeout=1800)
    assert st == 200, video
    print("uploaded:", video["filename"], video["duration_s"], "s")

    # Optional 3rd arg: JSON job options, e.g. '{"tile_grid":3,"sample_step":6}'
    opts = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    st, job = req(f"/api/videos/{video['id']}/analyze", "POST", opts, token)
    assert st == 200, job
    jid = job["id"]
    print("job", jid, "queued")
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
    pc = [c for c in (an.get("per_camera") or []) if c["visits_est"]]
    print(f"  cameras with visits: {len(pc)}/16")
    for c in sorted(pc, key=lambda x: -x["visits_est"])[:8]:
        print(f"    {c['camera']}: {c['visits_est']} visits")
    st, ev = req(f"/api/analyses/{aid}/events", token=token)
    print("  events:", len(ev))
    print("\nOPEN:", f"{BASE}/#/analysis/{aid}")


if __name__ == "__main__":
    main()
