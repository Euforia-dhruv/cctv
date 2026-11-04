"""Verify a deployed backend end-to-end over the internet.
Usage: python tests/verify_remote.py [BASE_URL]
Uploads a small demo clip, analyzes it, prints results."""
import json
import sys
import time
import urllib.request
import urllib.error
import os
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1
        else "https://cctv-kjyj.onrender.com").rstrip("/")
VIDEO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "..", "data", "videos_demo", "49349_refrigerator_720.mp4")


def req(path, method="GET", data=None, token=None, raw=None, ctype="application/json", timeout=180):
    headers = {}
    if token:
        headers["x-auth-token"] = token
    body = None
    if raw is not None:
        body = raw
        headers["Content-Type"] = ctype
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = ctype
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            text = resp.read().decode()
            try:
                return resp.status, json.loads(text)
            except json.JSONDecodeError:
                return resp.status, text
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:
        return -1, str(e)


def main():
    print("BASE:", BASE)
    st, r = req("/api/health")
    print("health:", st, r)
    assert st == 200 and r.get("ok"), "backend unreachable"

    email = f"remote{uuid.uuid4().hex[:6]}@test.local"
    st, r = req("/api/auth/register", "POST", {"email": email, "name": "Remote Tester",
                                                "password": "remote1234"})
    if st != 200:
        print("register failed:", st, r)
        return
    token = r["token"]
    print("registered", email)

    st, r = req("/api/stores", "POST", {"name": "Remote Store"}, token)
    assert st == 200, r
    store = r
    print("store", store["id"])

    boundary = uuid.uuid4().hex
    with open(VIDEO, "rb") as f:
        content = f.read()
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"store_id\"\r\n\r\n{store['id']}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"consent\"\r\n\r\n1\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(VIDEO)}\"\r\nContent-Type: video/mp4\r\n\r\n".encode(),
        content,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    st, video = req("/api/videos", "POST", token=token, raw=b"".join(parts),
                    ctype=f"multipart/form-data; boundary={boundary}", timeout=300)
    print("upload:", st, video if isinstance(video, dict) else video[:120])
    assert st == 200, "upload failed"
    vid = video["id"]

    st, job = req(f"/api/videos/{vid}/analyze", "POST", {}, token)
    print("analyze:", st, job)
    job_id = job["id"]

    deadline = time.time() + 1200
    while time.time() < deadline:
        st, j = req(f"/api/jobs/{job_id}", token=token)
        print("  job:", j.get("status"), j.get("progress"), j.get("stage"))
        if j.get("status") in ("done", "failed"):
            break
        time.sleep(10)
    assert j.get("status") == "done", j.get("error")
    aid = j["analysis"]["id"]
    st, a = req(f"/api/analyses/{aid}", token=token)
    an = a["analysis"]
    print("ANALYSIS", aid, "device", an["inference_device"],
          "dets", an["total_detections"], "visits", an["unique_visits_est"],
          "scene", an.get("scene"))
    st, ev = req(f"/api/analyses/{aid}/events", token=token)
    print("events:", len(ev), ev[:2] if ev else "")
    print("REMOTE VERIFY PASSED")


if __name__ == "__main__":
    main()
