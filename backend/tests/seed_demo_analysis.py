"""Seed a demo analysis on the richest clip (mall_23249) as the demo user.
Run with the server up: python tests/seed_demo_analysis.py"""
import json
import sys
import time
import urllib.request
import urllib.error
import os
import uuid

BASE = "http://127.0.0.1:8000/api"
VIDEO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "..", "data", "videos_demo", "mall_23249_720.mp4")


def req(path, method="GET", data=None, token=None, raw=None, ctype="application/json"):
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
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def main():
    email = "demo@retailvision.ai"
    st, r = req("/auth/login", "POST", {"email": email, "password": "demo1234"})
    if st != 200:
        req("/auth/register", "POST", {"email": email, "name": "Demo Analyst",
                                        "password": "demo1234", "role": "analyst"})
        st, r = req("/auth/login", "POST", {"email": email, "password": "demo1234"})
        assert st == 200
    token = json.loads(r)["token"]

    st, stores = req("/stores", token=token)
    store = None
    for s in json.loads(stores):
        if s["name"] == "Demo Store":
            store = s
    if not store:
        st, r = req("/stores", "POST", {"name": "Demo Store"}, token)
        store = json.loads(r)

    # upload hero clip (skip if already present)
    st, videos = req(f"/videos?store_id={store['id']}", token=token)
    vid = None
    for v in json.loads(videos):
        if v["filename"] == os.path.basename(VIDEO):
            vid = v
    if not vid:
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
        st, r = req("/videos", "POST", token=token, raw=b"".join(parts),
                    ctype=f"multipart/form-data; boundary={boundary}")
        assert st == 200, r
        vid = json.loads(r)
    print("video id:", vid["id"], vid["filename"])

    st, jobs = req(f"/jobs?video_id={vid['id']}", token=token)
    job = None
    for j in json.loads(jobs):
        if j["status"] in ("running", "queued"):
            job = j
        elif j["status"] == "done" and j.get("analysis"):
            print("analysis already exists:", j["analysis"])
            return
    if not job:
        st, r = req(f"/videos/{vid['id']}/analyze", "POST", {"device": "auto"}, token)
        assert st == 200, r
        job = json.loads(r)
        print("job queued:", job["id"])
    deadline = time.time() + 600
    while time.time() < deadline:
        st, r = req(f"/jobs/{job['id']}", token=token)
        j = json.loads(r)
        print("  status:", j["status"], j.get("progress"), j.get("stage"))
        if j["status"] in ("done", "failed"):
            break
        time.sleep(3)
    assert j["status"] == "done", j.get("error")
    st, r = req(f"/analyses/{j['analysis']['id']}", token=token)
    a = json.loads(r)["analysis"]
    print("ANALYSIS", a["id"], "device", a["inference_device"],
          "dets", a["total_detections"], "visits", a["unique_visits_est"],
          "occupancy avg", a["avg_occupancy"], "max", a["max_occupancy"],
          "dwell avg", a["dwell_avg_s"], "ms/frame", a["inference_ms_avg"])
    st, r = req(f"/analyses/{a['id']}/events", token=token)
    events = json.loads(r)
    print("events:", len(events))
    for e in events[:6]:
        print("   ", e["type"], "|", e["label"], "| t=", round(e["ts_s"], 1))
    print("DONE")


if __name__ == "__main__":
    main()
