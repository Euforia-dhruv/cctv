"""E2E API test against a running server (uvicorn on :8000).
Run with the server up: python tests/test_api_e2e.py"""
import json
import time
import urllib.request
import urllib.error
import mimetypes
import os
import uuid

BASE = "http://127.0.0.1:8000/api"
VIDEO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "..", "data", "videos_demo", "49349_refrigerator_720.mp4")


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
            text = resp.read().decode()
            try:
                return resp.status, json.loads(text)
            except json.JSONDecodeError:
                return resp.status, text
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def main():
    print("== E2E API test ==")
    # register a fresh user
    email = f"e2e{uuid.uuid4().hex[:8]}@test.local"
    st, r = req("/auth/register", "POST", {"email": email, "name": "E2E", "password": "e2e1234"})
    assert st == 200, (st, r)
    token = r["token"]
    print("register ok")

    st, stores = req("/stores", token=token)
    assert st == 200
    st, store = req("/stores", "POST", {"name": "E2E Store"}, token)
    assert st == 200, (st, store)
    print("store ok")

    # upload video
    boundary = uuid.uuid4().hex
    with open(VIDEO, "rb") as f:
        content = f.read()
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"store_id\"\r\n\r\n{store['id']}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"consent\"\r\n\r\n1\r\n".encode())
    fn = os.path.basename(VIDEO)
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fn}\"\r\nContent-Type: video/mp4\r\n\r\n".encode())
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)
    st, video = req("/videos", "POST", token=token, raw=body,
                    ctype=f"multipart/form-data; boundary={boundary}")
    assert st == 200, (st, video)
    vid = video["id"]
    print("upload ok:", video["filename"], video["duration_s"], "s")

    st, job = req(f"/videos/{vid}/analyze", "POST", {}, token)
    assert st == 200, (st, job)
    job_id = job["id"]
    print("analyze queued:", job_id)

    # poll
    deadline = time.time() + 360
    last = ""
    while time.time() < deadline:
        st, j = req(f"/jobs/{job_id}", token=token)
        assert st == 200
        status = j["status"]
        if status != last:
            print("  job status:", status, j.get("progress"), j.get("stage"))
            last = status
        if status in ("done", "failed"):
            break
        time.sleep(2)
    assert status == "done", (status, j.get("error"))
    analysis_id = j["analysis"]["id"]
    print("analysis id:", analysis_id)

    st, a = req(f"/analyses/{analysis_id}", token=token)
    assert st == 200
    print("summary:", {k: a["analysis"][k] for k in
          ("total_detections", "unique_visits_est", "avg_occupancy", "dwell_avg_s")})
    assert a["analysis"]["total_detections"] > 0, "no detections recorded"
    assert a["analysis"]["heatmap_path"], "heatmap missing"

    st, tr = req(f"/analyses/{analysis_id}/tracks", token=token)
    assert st == 200 and isinstance(tr, list)
    print("tracks:", len(tr))

    st, ev = req(f"/analyses/{analysis_id}/events", token=token)
    assert st == 200
    print("events:", len(ev))

    # review an event + feedback
    if ev:
        eid = ev[0]["id"]
        st, upd = req(f"/events/{eid}", "PATCH", {"status": "resolved", "reviewer_notes": "ok"}, token)
        assert st == 200 and upd["status"] == "resolved"
        st, fb = req("/feedback", "POST", {"event_id": eid, "label_original": ev[0]["label"],
                                            "label_corrected": "reviewed", "video_time": ev[0]["ts_s"]}, token)
        assert st == 200
        print("event review + feedback ok")

    st, csv_ = req(f"/analyses/{analysis_id}/report.csv", token=token)
    assert st == 200 and "metric" in str(csv_)
    print("csv report ok")
    print("ALL E2E CHECKS PASSED")


if __name__ == "__main__":
    main()
