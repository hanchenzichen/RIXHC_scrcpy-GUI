"""本地 agent：把核心能力暴露为 HTTP JSON API，并内置一个 Web 控制台。

设计目的：
    * 让 TUI / 浏览器 / 未来的移动端共用同一套接口，避免为每个前端重复实现逻辑；
    * 用标准库实现（`http.server`），不引入额外依赖，符合「省内存」的目标；
    * 默认只监听 127.0.0.1；如需局域网访问（例如用手机浏览器控制电脑上的 scrcpy），
      需显式指定 `--host 0.0.0.0`，并建议同时设置 `--token`。

接口一览：
    GET    /                       Web 控制台
    GET    /api/status             版本、内置核心、参数数量
    GET    /api/options            参数列表（支持 search / group 过滤）
    GET    /api/devices            adb 设备（含 unauthorized / offline 状态）
    GET    /api/profiles           配置预设
    GET    /api/sessions           会话列表
    POST   /api/sessions           启动会话 {values, extra_args, label}
    DELETE /api/sessions/{id}      停止会话
    GET    /api/sessions/{id}/log  读取会话输出（since 参数用于增量拉取）
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from rix import __version__, vendor
from rix.profiles import ProfileStore
from rix.registry import load_registry
from rix.scrcpy_bin import adb_devices, find_binary, scrcpy_version
from rix.sessions import SessionSupervisor

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class AgentState:
    """agent 的全部业务逻辑（与 HTTP 层解耦，便于测试与复用）。"""

    def __init__(self, token: str | None = None, binary: str | None = None,
                 profile_store: ProfileStore | None = None):
        self.registry = load_registry()
        self.supervisor = SessionSupervisor()
        # 属性名不能叫 profiles，否则会覆盖同名的 profiles() 方法
        self.profile_store = profile_store or ProfileStore()
        self.token = token
        self.binary = binary

    # ---- 查询 ----
    def status(self) -> dict:
        return {
            "app": "rix-scrcpy",
            "version": __version__,
            "option_count": self.registry.option_count,
            "scrcpy": {
                "path": find_binary("scrcpy"),
                "version": scrcpy_version(self.binary or find_binary("scrcpy")),
            },
            "vendor": vendor.status(),
            "sessions": len(self.supervisor.list()),
            "time": time.time(),
        }

    def options(self, search: str | None = None, group: str | None = None) -> list[dict]:
        specs = self.registry.search(search) if search else self.registry.sorted_options()
        if group:
            specs = [spec for spec in specs if spec.group == group]
        return [
            {
                "long": spec.long, "short": spec.short, "group": spec.group,
                "argdesc": spec.argdesc, "enum": spec.enum, "takes_value": spec.takes_value,
                "optional_arg": spec.optional_arg, "help": spec.help,
            }
            for spec in specs
        ]

    def devices(self) -> list[dict]:
        return adb_devices()

    def profiles(self) -> dict:
        return {name: self.profile_store.get(name) for name in self.profile_store.names()}

    def sessions(self) -> list[dict]:
        return [session.to_dict() for session in self.supervisor.list()]

    def session_log(self, session_id: str, since: int = 0) -> dict:
        session = self.supervisor.get(session_id)
        if session is None:
            raise KeyError(session_id)
        lines, next_index = session.read_log(since)
        return {"id": session_id, "lines": lines, "next": next_index,
                "status": session.status, "running": session.running}

    # ---- 操作 ----
    def start_session(self, payload: dict) -> dict:
        values = payload.get("values") or {}
        extra_args = payload.get("extra_args") or []
        label = payload.get("label") or ""

        unknown = [name for name in values if name not in self.registry]
        if unknown:
            return {"ok": False, "error": f"未知参数: {', '.join(unknown)}"}

        binary = payload.get("binary") or self.binary or find_binary("scrcpy")
        if not binary:
            return {"ok": False,
                    "error": "未找到 scrcpy，可执行 `rix-scrcpy vendor install` 安装内置核心"}

        argv = self.registry.build_argv(values, extra_args, binary=binary)
        session = self.supervisor.start(argv, label=label)
        return {
            "ok": session.status != "failed",
            "session": session.to_dict(),
            "warnings": self.registry.validate(values),
            "error": session.error,
        }

    def stop_session(self, session_id: str) -> dict:
        session = self.supervisor.get(session_id)
        if session is None:
            raise KeyError(session_id)
        ok = session.stop()
        return {"ok": ok, "session": session.to_dict()}


class AgentHandler(BaseHTTPRequestHandler):
    """HTTP 路由层。业务逻辑全部在 AgentState 中。"""

    server_version = f"rix-scrcpy-agent/{__version__}"
    state: AgentState
    web_console: bytes = b""

    # ---- 工具 ----
    def _authorized(self) -> bool:
        token = self.state.token
        if not token:
            return True
        if self.headers.get("X-Rix-Token") == token:
            return True
        return self._query().get("token") == token

    def _send(self, payload, status: int = 200, content_type: str = "application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(
            payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message: str, status: int = 400):
        self._send({"ok": False, "error": message}, status=status)

    def log_message(self, fmt, *args):  # noqa: A003 - 覆盖基类，默认不刷屏
        if os.environ.get("RIX_AGENT_VERBOSE"):
            super().log_message(fmt, *args)

    def _path(self) -> str:
        return self.path.split("?", 1)[0].rstrip("/") or "/"

    def _query(self) -> dict:
        if "?" not in self.path:
            return {}
        result = {}
        for item in self.path.split("?", 1)[1].split("&"):
            if "=" in item:
                key, value = item.split("=", 1)
                result[key] = value
        return result

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    # ---- 路由 ----
    def do_GET(self):  # noqa: N802 - 基类约定
        path = self._path()
        if path == "/":
            self._send(self.web_console or b"<h1>rix-scrcpy agent</h1>",
                       content_type="text/html")
            return
        if not self._authorized():
            self._error("未授权：请提供正确的 token", status=401)
            return
        try:
            if path == "/api/status":
                return self._send(self.state.status())
            if path == "/api/options":
                query = self._query()
                return self._send(self.state.options(query.get("search"), query.get("group")))
            if path == "/api/devices":
                return self._send(self.state.devices())
            if path == "/api/profiles":
                return self._send(self.state.profiles())
            if path == "/api/sessions":
                return self._send(self.state.sessions())
            if path.startswith("/api/sessions/") and path.endswith("/log"):
                session_id = path.split("/")[3]
                since = int(self._query().get("since", 0) or 0)
                return self._send(self.state.session_log(session_id, since))
        except KeyError:
            return self._error("会话不存在", status=404)
        except (ValueError, OSError) as exc:
            return self._error(str(exc), status=500)
        except Exception as exc:  # noqa: BLE001 - 兜底，避免连接被静默断开
            return self._error(f"服务内部错误: {exc!r}", status=500)
        self._error("未知接口", status=404)

    def do_POST(self):  # noqa: N802
        if not self._authorized():
            return self._error("未授权：请提供正确的 token", status=401)
        path = self._path()
        if path == "/api/sessions":
            return self._send(self.state.start_session(self._read_json()))
        if path.startswith("/api/sessions/") and path.endswith("/stop"):
            session_id = path.split("/")[3]
            try:
                return self._send(self.state.stop_session(session_id))
            except KeyError:
                return self._error("会话不存在", status=404)
        self._error("未知接口", status=404)

    def do_DELETE(self):  # noqa: N802
        if not self._authorized():
            return self._error("未授权：请提供正确的 token", status=401)
        path = self._path()
        if path.startswith("/api/sessions/"):
            session_id = path.split("/")[3]
            try:
                return self._send(self.state.stop_session(session_id))
            except KeyError:
                return self._error("会话不存在", status=404)
        self._error("未知接口", status=404)


WEB_CONSOLE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RIX Scrcpy 控制台</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 16px; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", "Noto Sans SC", sans-serif;
         background: #16181d; color: #e6e6e6; }
  h1 { font-size: 18px; margin: 0 0 4px; }
  h2 { font-size: 15px; margin: 20px 0 8px; color: #9ad; }
  .muted { color: #8b93a1; font-size: 13px; }
  .card { background: #1e2128; border: 1px solid #2b3038; border-radius: 10px; padding: 12px; margin-bottom: 12px; }
  input, select, textarea, button { font: inherit; color: inherit; background: #262a33;
         border: 1px solid #343a45; border-radius: 8px; padding: 8px 10px; }
  input, select, textarea { width: 100%; }
  button { cursor: pointer; background: #2f6feb; border-color: #2f6feb; }
  button.ghost { background: #262a33; border-color: #343a45; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .row > * { flex: 1; }
  .row > button { flex: 0 0 auto; }
  pre { margin: 8px 0 0; padding: 10px; background: #12141a; border-radius: 8px; overflow: auto;
        max-height: 260px; white-space: pre-wrap; word-break: break-all; font-size: 13px; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; background: #2b3038; }
  .ok { background: #1d4025; color: #9be3a8; }
  .warn { background: #4a3a12; color: #ffd479; }
  .err { background: #4a1d1d; color: #ff9b9b; }
  li { margin: 4px 0; }
</style>
</head>
<body>
<h1>RIX Scrcpy 控制台</h1>
<div class="muted" id="status">正在连接 agent …</div>

<h2>设备</h2>
<div class="card" id="devices"><span class="muted">加载中…</span></div>

<h2>启动会话</h2>
<div class="card">
  <div class="row" style="margin-bottom:8px">
    <select id="profile"><option value="">（不使用预设）</option></select>
    <button class="ghost" onclick="loadProfiles()">刷新预设</button>
  </div>
  <input id="values" placeholder="参数=值，多个用逗号分隔，例如 video-bit-rate=16M,no-audio">
  <input id="extra" placeholder="透传参数（可选），例如 --serial abc123" style="margin-top:8px">
  <div class="row" style="margin-top:8px">
    <button onclick="startSession()">启动</button>
    <button class="ghost" onclick="refreshAll()">刷新</button>
  </div>
  <pre id="startResult" hidden></pre>
</div>

<h2>会话</h2>
<div class="card" id="sessions"><span class="muted">暂无会话</span></div>

<h2>输出</h2>
<div class="card">
  <div class="row">
    <select id="logSession" onchange="resetLog()"><option value="">选择会话</option></select>
  </div>
  <pre id="log">（选择会话后显示输出）</pre>
</div>

<script>
const token = new URLSearchParams(location.search).get("token");
const api = (path, options = {}) => {
  const headers = Object.assign({}, options.headers || {});
  if (token) headers["X-Rix-Token"] = token;
  return fetch(path, Object.assign({}, options, { headers })).then(r => r.json());
};
let logCursor = 0, logSessionId = null;

function esc(text) { return String(text).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }

async function loadStatus() {
  try {
    const s = await api("/api/status");
    const scrcpy = s.scrcpy && s.scrcpy.version ? s.scrcpy.version : "未检测到";
    const vendor = s.vendor && s.vendor.version ? "内置 " + s.vendor.version : "无内置核心";
    document.getElementById("status").innerHTML =
      `v${esc(s.version)} · scrcpy ${esc(scrcpy)} · ${esc(vendor)} · 参数 ${esc(s.option_count)} 个`;
  } catch (e) { document.getElementById("status").textContent = "无法连接 agent：" + e; }
}

async function loadDevices() {
  const devices = await api("/api/devices");
  const box = document.getElementById("devices");
  if (!devices.length) { box.innerHTML = '<span class="muted">未检测到设备（请确认已连接并授权 USB 调试）</span>'; return; }
  box.innerHTML = devices.map(d => {
    const cls = d.state === "device" ? "ok" : "warn";
    return `<div>${esc(d.serial)} <span class="tag ${cls}">${esc(d.state)}</span> ${esc(d.model || "")}</div>`;
  }).join("");
}

async function loadProfiles() {
  const profiles = await api("/api/profiles");
  const select = document.getElementById("profile");
  select.innerHTML = '<option value="">（不使用预设）</option>' +
    Object.keys(profiles).map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
}

function parseValues(text, profileName) {
  const values = {};
  text.split(",").map(s => s.trim()).filter(Boolean).forEach(item => {
    const i = item.indexOf("=");
    if (i < 0) values[item] = true; else values[item.slice(0, i).trim()] = item.slice(i + 1).trim();
  });
  return { values, profile: profileName };
}

async function startSession() {
  const profileName = document.getElementById("profile").value;
  let values = {};
  if (profileName) values = (await api("/api/profiles"))[profileName] || {};
  const parsed = parseValues(document.getElementById("values").value, profileName);
  values = Object.assign({}, values, parsed.values);
  const extra = document.getElementById("extra").value.trim();
  const body = { values, label: profileName || "web", extra_args: extra ? extra.split(/\s+/) : [] };
  const result = await api("/api/sessions", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const pre = document.getElementById("startResult");
  pre.hidden = false;
  pre.textContent = result.ok ? ("已启动：" + result.session.command) : ("启动失败：" + result.error);
  if (result.warnings && result.warnings.length) pre.textContent += "\\n警告：\\n" + result.warnings.join("\\n");
  refreshAll();
}

async function stopSession(id) { await api("/api/sessions/" + id, { method: "DELETE" }); refreshAll(); }

async function loadSessions() {
  const sessions = await api("/api/sessions");
  const box = document.getElementById("sessions");
  const select = document.getElementById("logSession");
  if (!sessions.length) { box.innerHTML = '<span class="muted">暂无会话</span>'; }
  else {
    box.innerHTML = sessions.map(s => {
      const cls = s.status === "running" ? "ok" : (s.status === "failed" ? "err" : "");
      return `<div class="row"><span>${esc(s.id)} <span class="tag ${cls}">${esc(s.status)}</span> `
        + `<span class="muted">${esc(s.uptime)}s</span></span>`
        + `<button class="ghost" onclick="stopSession('${esc(s.id)}')">停止</button></div>`;
    }).join("");
  }
  const current = select.value;
  select.innerHTML = '<option value="">选择会话</option>' +
    sessions.map(s => `<option value="${esc(s.id)}">${esc(s.id)} ${esc(s.label)}</option>`).join("");
  if (current) select.value = current;
}

function resetLog() {
  logSessionId = document.getElementById("logSession").value || null;
  logCursor = 0;
  document.getElementById("log").textContent = logSessionId ? "" : "（选择会话后显示输出）";
}

async function pollLog() {
  if (!logSessionId) return;
  try {
    const data = await api(`/api/sessions/${logSessionId}/log?since=${logCursor}`);
    if (data.lines && data.lines.length) {
      const pre = document.getElementById("log");
      pre.textContent += data.lines.join("\\n") + "\\n";
      pre.scrollTop = pre.scrollHeight;
    }
    logCursor = data.next;
  } catch (e) { /* 会话可能已被清理 */ }
}

function refreshAll() { loadStatus(); loadDevices(); loadSessions(); }
refreshAll();
loadProfiles();
setInterval(refreshAll, 5000);
setInterval(pollLog, 1000);
</script>
</body>
</html>
"""


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                state: AgentState | None = None) -> ThreadingHTTPServer:
    """创建 HTTP 服务（便于测试：port 传 0 可让系统分配空闲端口）。"""
    state = state or AgentState()
    handler = type("BoundAgentHandler", (AgentHandler,), {
        "state": state,
        "web_console": WEB_CONSOLE.encode("utf-8"),
    })
    return ThreadingHTTPServer((host, port), handler)


def local_ip() -> str:
    """获取本机在局域网中的地址（用于提示手机访问地址）。"""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, token: str | None = None,
          binary: str | None = None, open_browser: bool = False, log=print) -> int:
    """启动 agent，阻塞直到中断。"""
    state = AgentState(token=token, binary=binary)
    try:
        httpd = make_server(host, port, state)
    except OSError as exc:
        log(f"无法监听 {host}:{port} —— {exc}")
        return 1

    actual_port = httpd.server_address[1]
    log(f"agent 已启动：http://{host}:{actual_port}/")
    if host not in ("127.0.0.1", "localhost"):
        suffix = f"?token={token}" if token else ""
        log(f"局域网访问：http://{local_ip()}:{actual_port}/{suffix}")
        if not token:
            log("提示：当前监听非本机地址且未设置 token，同网络内的其他设备可以直接访问。")
            log("      如需限制访问，请使用 --token 指定访问令牌。")
    if open_browser:
        import webbrowser

        webbrowser.open(f"http://127.0.0.1:{actual_port}/")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("收到中断信号，正在停止…")
    finally:
        stopped = state.supervisor.stop_all()
        httpd.server_close()
        log(f"已停止 {stopped} 个会话，agent 退出。")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m rix.agent", description="本地 agent 与 Web 控制台")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址（默认仅本机）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    parser.add_argument("--token", help="访问令牌（局域网访问时建议设置）")
    parser.add_argument("--binary", help="scrcpy 可执行文件路径")
    parser.add_argument("--open", action="store_true", help="启动后打开浏览器")
    args = parser.parse_args(argv)
    return serve(args.host, args.port, args.token, args.binary, args.open)


if __name__ == "__main__":
    import sys

    sys.exit(main())
