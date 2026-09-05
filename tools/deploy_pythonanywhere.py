"""Push the postclose package to PythonAnywhere and reload the web app.

    export PA_USERNAME=catee
    export PA_TOKEN=...            # Account -> API token
    python3 tools/deploy_pythonanywhere.py [--dry-run] [--remote-dir DIR]

Uploads every file the dashboard needs (code, templates, the locked baseline)
and nothing else. Reported actuals living on the server are never overwritten:
actuals_*.json is excluded, so a deploy cannot destroy months already entered.
"""
import argparse
import os
import sys
import urllib.error
import urllib.request

API = "https://www.pythonanywhere.com/api/v0/user/{user}/"

# Everything the blueprint needs, relative to the repository root.
INCLUDE_DIRS = ["postclose"]
INCLUDE_FILES = ["requirements.txt"]
SKIP_SUFFIXES = (".pyc", ".tmp", ".xlsx", ".xlsm")
SKIP_PARTS = ("__pycache__",)
# Never push over reported data or overwrite it with an empty local copy.
SKIP_NAMES_PREFIX = ("actuals_",)


def collect(root):
    out = []
    for rel in INCLUDE_FILES:
        if os.path.exists(os.path.join(root, rel)):
            out.append(rel)
    for d in INCLUDE_DIRS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, d)):
            dirnames[:] = [x for x in dirnames if x not in SKIP_PARTS]
            for name in sorted(filenames):
                if name.endswith(SKIP_SUFFIXES):
                    continue
                if name.startswith(SKIP_NAMES_PREFIX):
                    continue
                out.append(os.path.relpath(os.path.join(dirpath, name), root))
    return sorted(out)


def request(method, url, token, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Token {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def upload(user, token, remote_path, blob):
    boundary = "----postclose-deploy-boundary"
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="content"; filename="upload"\r\n',
        b"Content-Type: application/octet-stream\r\n\r\n",
        blob, b"\r\n", f"--{boundary}--\r\n".encode(),
    ])
    url = API.format(user=user) + "files/path" + remote_path
    return request("POST", url, token, body,
                   {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote-dir", default=None,
                    help="Absolute path on PythonAnywhere (default /home/<user>)")
    ap.add_argument("--domain", default=None,
                    help="Web app domain to reload (default <user>.pythonanywhere.com)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    user = os.environ.get("PA_USERNAME")
    token = os.environ.get("PA_TOKEN")
    if not user or not token:
        sys.exit("Set PA_USERNAME and PA_TOKEN.")
    remote_dir = (args.remote_dir or f"/home/{user}").rstrip("/")
    domain = args.domain or f"{user}.pythonanywhere.com"

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = collect(root)
    print(f"{len(files)} file(s) -> {remote_dir} on {domain}")
    if args.dry_run:
        for rel in files:
            print("  ", rel)
        return

    for rel in files:
        with open(os.path.join(root, rel), "rb") as fh:
            blob = fh.read()
        status, body = upload(user, token, f"{remote_dir}/{rel}", blob)
        ok = status in (200, 201)
        print(f"  {'ok ' if ok else 'FAIL'} {rel} ({len(blob)}b, {status})")
        if not ok:
            sys.exit(body.decode()[:400])

    status, body = request(
        "POST", API.format(user=user) + f"webapps/{domain}/reload/", token, b"")
    print("reload:", status, body.decode()[:200])


if __name__ == "__main__":
    main()
