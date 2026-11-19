#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排盘演示服务：接收时间参数 → 调 qintianjian 引擎 → 返回盘面 JSON。

只为本地面板演示用，监听 127.0.0.1。零第三方依赖（标准库 http.server）。

启动：
    QJ_ENGINE=/path/to/qintianjian python3 serve.py 8901
"""
import json
import os
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# 默认取仓库根（ui/ 的上一级）；也支持独立引用引擎目录
ENGINE_DIR = os.environ.get(
    "QJ_ENGINE",
    str(_HERE.parent if (_HERE.parent / "scripts" / "bazi.py").is_file() else _HERE),
)
ROOT = Path(__file__).resolve().parent

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


def run_bazi(date_str, hour_str, sex, shichen=None):
    """调引擎。shichen 优先（不确定时只给辰）。"""
    cmd = [sys.executable, str(Path(ENGINE_DIR) / "scripts" / "bazi.py")]
    if shichen:
        cmd += ["--shichen", shichen]
    else:
        cmd += ["--hour", hour_str]
    cmd += ["--solar", date_str, "--sex", sex or "男", "--json"]

    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        return {"ok": False, "error": {"code": "ENGINE_ERROR",
                                       "message": (p.stderr or p.stdout)[:600]}}
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"code": "BAD_JSON",
                                       "message": p.stdout[:600]}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # 安静

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)

        if u.path == "/api/bazi":
            q = urllib.parse.parse_qs(u.query)
            date_str = (q.get("date") or [""])[0]
            hour_str = (q.get("hour") or ["12:00"])[0]
            sex = (q.get("sex") or ["男"])[0]
            vague = (q.get("vague") or ["0"])[0] == "1"
            sex_ok = (q.get("sex_ok") or ["1"])[0] == "1"

            # 只给辰不给分：用 --shichen（引擎取该时辰中点）
            shichen = None
            if vague:
                shichen = (q.get("shichen") or [""])[0] or None
                if not shichen:
                    return self._send(400, json.dumps(
                        {"ok": False, "error": {"code": "NEED_SHICHEN",
                                                "message": "不确定模式下必须给 shichen"}},
                        ensure_ascii=False))

            if not date_str:
                return self._send(400, json.dumps(
                    {"ok": False, "error": {"code": "NEED_DATE", "message": "缺少 date"}},
                    ensure_ascii=False))

            data = run_bazi(date_str, hour_str,
                            sex if sex_ok else None, shichen)
            # 把不确定标记透出去，渲染时据此标注
            if isinstance(data, dict):
                data.setdefault("_demo", {})
                data["_demo"].update({"vague": vague, "sex_ok": sex_ok})
            return self._send(200, json.dumps(data, ensure_ascii=False))

        # 静态文件
        p = u.path.lstrip("/") or "index.html"
        if p.endswith("/"):
            p += "index.html"          # 目录默认页
        f = (ROOT / p).resolve()
        if not str(f).startswith(str(ROOT)) or not f.is_file():
            return self._send(404, "not found", "text/plain; charset=utf-8")
        self._send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8901
    print(f"引擎目录: {ENGINE_DIR}")
    print(f"静态根目录: {ROOT}")
    print(f"→ http://127.0.0.1:{port}/demo-picker.html")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
