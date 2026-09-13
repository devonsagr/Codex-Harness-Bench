"""Loopback-only workbench. Explicit operations reuse the CLI's frozen experiment layer."""
import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import subprocess
import threading
import tomllib
from urllib.parse import unquote, urlsplit
import webbrowser

from chb.cli import CODEX_VERSION, make_plan, profile_diff, task_settings
from chb.configuration import import_current, restore_profile, save_private
from chb.experiments import group_comparisons, planned_tasks, task_for_trial
from chb.profiles import digest, files_in, read_json, validate_profile

TASK_NAMES = ("search-notes-v1", "storage-migration-v1", "csv-catalog-v1")
ASSETS = Path(__file__).parent / "web"


def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", value):
        raise ValueError("名称请使用 1–40 位小写字母、数字和连字符。")
    return value


def checked_path(root, *parts):
    """Reject linked parents as well as traversal; private files have no generic route."""
    target = root
    for part in parts:
        if part in {"", ".", ".."} or "/" in part or "\\" in part or ":" in part:
            raise ValueError("无效的本地路径。")
        target = target / part
        if target.is_symlink() or target.is_junction():
            raise ValueError("不支持符号链接或目录联接。")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("请求超出项目范围。")
    return target


def safe_json(root, *parts):
    return read_json(checked_path(root, *parts))


class Workbench:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.Lock()
        self.previews = {}

    def profile_path(self, name):
        slug(name)
        candidates = [checked_path(self.root, "profiles", name), checked_path(self.root, ".local", "profiles", name)]
        matches = [path for path in candidates if path.is_dir()]
        if len(matches) != 1:
            raise ValueError("配置不存在或同名；请在本机处理同名目录后刷新。")
        # Validate file links before validate_profile reads its metadata.
        files_in(matches[0])
        validate_profile(matches[0])
        return matches[0]

    def profile(self, name, detail=True):
        path = self.profile_path(name)
        metadata, native = validate_profile(path)
        content = files_in(path)
        data = {"name": name, "description": metadata.get("description", ""), "native": native,
                "private": path.parent.name == "profiles" and path.parent.parent.name == ".local",
                "sha256": digest(content)[0],
                "skills": sorted({p.split('/')[1] for p in content if p.startswith('skills/')})}
        if detail:
            data["agents"] = content["AGENTS.md"].decode("utf-8")
            data["skill_documents"] = {p: value.decode("utf-8", errors="replace") for p, value in content.items() if p.endswith("/SKILL.md")}
        return data

    def profiles(self):
        names, warnings = set(), []
        for parts in [("profiles",), (".local", "profiles")]:
            base = checked_path(self.root, *parts)
            if base.exists():
                names.update(path.name for path in base.iterdir() if path.is_dir())
        entries = []
        for name in sorted(names):
            try:
                entries.append(self.profile(name, detail=False))
            except (ValueError, OSError, KeyError, TypeError):
                warnings.append(f"有一份配置无效或同名，已跳过：{name}")
        return entries, warnings

    def tasks(self):
        entries = []
        for name in TASK_NAMES:
            path = checked_path(self.root, "tasks", name)
            files_in(path)
            task = tomllib.loads((path / "task.toml").read_text(encoding="utf-8"))
            entries.append({"name": name, **task["metadata"], "turns": max(1, len(task.get("steps", []))),
                            "steps": [step["name"] for step in task.get("steps", [])],
                            "instruction": (path / "instruction.md").read_text(encoding="utf-8")})
        return entries

    def experiment_path(self, name):
        if not isinstance(name, str) or not re.fullmatch(r"\d{8}T\d{6}Z-[a-f0-9]{8}", name):
            raise ValueError("实验编号无效。")
        return checked_path(self.root, "runs", name)

    def experiment(self, name, detail=True):
        path = self.experiment_path(name)
        plan = safe_json(path, "plan.json")
        results, trials = {}, []
        for trial in plan["trials"]:
            if not re.fullmatch(r"trial-\d{3,5}", trial["id"]):
                raise ValueError("实验包含无效运行编号。")
            result_path = checked_path(path, trial["id"], "result.json")
            result = read_json(result_path) if result_path.exists() else {"status": "not_run", "accepted": None}
            results[trial["id"]] = result
            task_name, task = task_for_trial(plan, trial)
            status = result.get("status", "unknown")
            # Raw exception messages can contain commands, prompts or private data.
            # Present a bounded known cause, never tracebacks or arbitrary logs.
            error = json.dumps(result.get("error") or result.get("reason") or {}, ensure_ascii=False)
            cause = "工作区额度不足，后续题目已停止。" if "Your workspace is out of credits" in error else "查看本机原始日志以定位原因。" if status not in {"completed", "not_run", "running"} else ""
            row = {**trial, "task": task_name, "group": task["group"], "status": status,
                   **{key: result.get(key) for key in ("accepted", "agent_seconds", "input_tokens", "cached_input_tokens", "output_tokens", "effective_profile_evidence")},
                   "cause": cause, "steps": [{key: step.get(key) for key in ("name", "status", "accepted", "agent_seconds", "input_tokens", "cached_input_tokens", "output_tokens", "profile_load_index", "skill_reads")}
                                              for step in result.get("steps", [])],
                   "session_continuity": result.get("session_continuity_observed"),
                   "usage_status": (result.get("usage_accounting") or {}).get("status"),
                   "skill_reads": result.get("skill_reads", [])}
            trials.append(row)
        counts = Counter(t["status"] for t in trials)
        state = "running" if counts["running"] else "interrupted" if any(t["status"] not in {"completed", "not_run"} for t in trials) else "planned" if counts["not_run"] == len(trials) else "partial" if counts["not_run"] else "finished"
        data = {"id": name, "model": plan["model"], "profiles": list(plan["profiles"]),
                "tasks": list(planned_tasks(plan)), "status": state, "planned": len(trials),
                "accepted": sum(t["accepted"] is True for t in trials), "finished": sum(t["status"] not in {"running", "not_run"} for t in trials),
                "pending": counts["not_run"], "turns": plan.get("planned_agent_turns"),
                "budget_seconds": plan.get("max_total_agent_seconds"), "codex_version": plan["codex_version"]}
        if detail:
            data.update({"trials": trials, "groups": group_comparisons(plan, results),
                         "native": plan.get("native_config", {}), "repeat": plan.get("repeat", 1),
                         "diff": checked_path(path, "profile-diff.txt").read_text(encoding="utf-8"),
                         "local_evidence": str(path), "schema": plan.get("schema", 1)})
        return data

    def state(self):
        profiles, warnings = self.profiles()
        base = checked_path(self.root, "runs")
        experiments = []
        candidates = sorted(base.iterdir(), reverse=True) if base.exists() else []
        for path in candidates[:100]:
            if not path.is_dir():
                continue
            try:
                experiments.append(self.experiment(path.name, detail=False))
            except (OSError, ValueError, KeyError, TypeError):
                warnings.append(f"有一份实验记录不完整，已跳过：{path.name}")
        return {"profiles": profiles, "tasks": self.tasks(), "experiments": experiments,
                "warnings": warnings, "history_limit": 100}

    def environment(self):
        try:
            result = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=5)
            docker = result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            docker = None
        return {"docker": docker, "codex": CODEX_VERSION,
                "authentication_present": (Path.home() / ".codex/auth.json").is_file(),
                "message": "认证文件存在不代表模型额度可用；浏览和配置操作不调用模型。"}

    def save_profile(self, data):
        name = slug(data.get("name"))
        source = slug(data.get("source"))
        profile = self.profile_path(source)
        files = files_in(profile)
        if data.get("source_sha256") != digest(files)[0]:
            raise ValueError("源配置已变化，请刷新后重新编辑。")
        agents, description, reasoning = data.get("agents"), data.get("description"), data.get("reasoning")
        if not isinstance(agents, str) or len(agents) > 300000 or not isinstance(description, str) or len(description) > 500:
            raise ValueError("说明或配置内容过长/格式无效。")
        if reasoning not in {"low", "medium", "high", "xhigh"}:
            raise ValueError("不支持的推理档位。")
        keep = data.get("skills", [])
        available = {p.split('/')[1] for p in files if p.startswith('skills/')}
        if not isinstance(keep, list) or any(not isinstance(s, str) or s not in available for s in keep):
            raise ValueError("只能选择源配置包含的技能。")
        files = {key: value for key, value in files.items() if not key.startswith('skills/') or key.split('/')[1] in keep}
        files.update({"AGENTS.md": agents.encode("utf-8"),
                      "profile.json": json.dumps({"name": name, "description": description}, ensure_ascii=False).encode("utf-8"),
                      "config.toml": f'model_reasoning_effort = "{reasoning}"\nweb_search = "disabled"\n'.encode()})
        save_private(self.root, name, files, {"operation": "ui-save-copy", "source_profile": source,
                                            "source_sha256": data["source_sha256"], "selected_skills": keep})
        return self.profile(name)

    def selection(self, data):
        profiles, tasks, repeat, model = data.get("profiles"), data.get("tasks"), data.get("repeat"), data.get("model")
        if not isinstance(profiles, list) or len(profiles) != 2 or profiles[0] == profiles[1]:
            raise ValueError("请选择两套不同的配置。")
        paths = [self.profile_path(name) for name in profiles]
        native = [validate_profile(path)[1] for path in paths]
        if native[0] != native[1]:
            raise ValueError("两套配置的推理档位必须一致；请先另存为相同设置。")
        if not isinstance(tasks, list) or not tasks or any(not isinstance(name, str) or name not in TASK_NAMES for name in tasks) or len(set(tasks)) != len(tasks):
            raise ValueError("请选择题目，每道题只能出现一次。")
        if type(repeat) is not int or not 1 <= repeat <= 5:
            raise ValueError("重复次数必须为 1–5。")
        if not isinstance(model, str) or len(model) > 100 or not re.fullmatch(r"[A-Za-z0-9._/-]+", model):
            raise ValueError("模型名称格式无效。")
        lookup = {task['name']: task for task in self.tasks()}
        turns = 2 * repeat * sum(lookup[name]['turns'] for name in tasks)
        fingerprint = {"profiles": {name: digest(files_in(path))[0] for name, path in zip(profiles, paths)},
                       "tasks": {name: digest(files_in(task_settings(name, self.root)[0]))[0] for name in tasks}}
        return {"selection": {"profiles": profiles, "tasks": tasks, "repeat": repeat, "model": model},
                "fingerprint": fingerprint, "diff": profile_diff(*paths), "native": native[0],
                "trials": 2 * repeat * len(tasks), "turns": turns, "budget_seconds": 300 * turns}

    def post(self, route, data):
        with self.lock:
            if route == "/api/profiles/save":
                return self.save_profile(data)
            if route == "/api/profiles/import":
                name = slug(data.get("name"))
                effort = data.get("reasoning", "medium")
                if effort not in {"low", "medium", "high", "xhigh"}:
                    raise ValueError("不支持的推理档位。")
                import_current(self.root, name, reasoning=effort)
                return self.profile(name)
            if route == "/api/profiles/restore":
                exp = self.experiment_path(data.get("experiment"))
                profile, name = slug(data.get("profile")), slug(data.get("name"))
                checked_path(exp, "inputs", "profiles", profile)
                restore_profile(self.root, exp, profile, name)
                return self.profile(name)
            if route == "/api/plans/preview":
                preview = self.selection(data)
                token = secrets.token_urlsafe(24)
                # Bound in-memory draft storage; drafts do not start model calls.
                if len(self.previews) >= 32:
                    self.previews.pop(next(iter(self.previews)))
                self.previews[token] = preview
                return {**preview, "preview_id": token}
            if route == "/api/plans/create":
                token = data.get("preview_id")
                if not isinstance(token, str) or token not in self.previews:
                    raise ValueError("请先预览差异与预算；预览已失效时需要重新生成。")
                preview = self.previews[token]
                fresh = self.selection(preview["selection"])
                if fresh["fingerprint"] != preview["fingerprint"]:
                    raise ValueError("配置或题目已变化，请重新预览后保存。")
                selected = preview["selection"]
                args = argparse.Namespace(profiles=','.join(selected['profiles']), tasks=','.join(selected['tasks']), task=None,
                                          repeat=selected['repeat'], model=selected['model'])
                directory = make_plan(args, root=self.root, emit=False)
                del self.previews[token]
                return {"id": directory.name, "model_calls_started": 0}
            raise ValueError("当前版本没有这个操作。")


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, root, port=8765):
        self.app = Workbench(root)
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Request paths and private inputs do not belong in terminal logs.

    def reply(self, status, data, mime="application/json; charset=utf-8"):
        body = json.dumps(data, ensure_ascii=False).encode() if mime.startswith("application/json") else data
        self.send_response(status)
        for key, value in {"Content-Type": mime, "Content-Length": str(len(body)), "Cache-Control": "no-store",
                           "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                           "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def guard(self, write=False):
        if self.headers.get("Host") != urlsplit(self.server.origin).netloc:
            self.reply(403, {"error": "只允许本机工作台访问。"})
            return False
        if write and (self.headers.get("Origin") != self.server.origin or not secrets.compare_digest(self.headers.get("X-CHB-Token", ""), self.server.token)):
            self.reply(403, {"error": "操作来源无效，请从本机工作台重试。"})
            return False
        if unquote(urlsplit(self.path).path).startswith('/api/') and not secrets.compare_digest(self.headers.get("X-CHB-Token", ""), self.server.token):
            self.reply(403, {"error": "请刷新工作台后重试。"})
            return False
        return True

    def do_GET(self):
        if not self.guard():
            return
        route = unquote(urlsplit(self.path).path)
        try:
            if route == "/":
                text = (ASSETS / "index.html").read_text(encoding="utf-8").replace("__CHB_TOKEN__", self.server.token)
                return self.reply(200, text.encode(), "text/html; charset=utf-8")
            if route == "/favicon.ico":
                return self.reply(204, b"", "image/x-icon")
            if route in {"/app.js", "/app.css"}:
                return self.reply(200, (ASSETS / route[1:]).read_bytes(), "text/javascript; charset=utf-8" if route.endswith('.js') else "text/css; charset=utf-8")
            if route == "/api/state":
                return self.reply(200, self.server.app.state())
            if route == "/api/environment":
                return self.reply(200, self.server.app.environment())
            if route.startswith("/api/profiles/"):
                return self.reply(200, self.server.app.profile(route.removeprefix("/api/profiles/")))
            if route.startswith("/api/experiments/"):
                return self.reply(200, self.server.app.experiment(route.removeprefix("/api/experiments/")))
            return self.reply(404, {"error": "页面不存在。"})
        except (ValueError, KeyError, TypeError):
            return self.reply(400, {"error": "记录无效或输入已变化；请刷新并核对本机文件。"})
        except OSError:
            return self.reply(404, {"error": "无法读取该记录，请核对文件是否存在。"})

    def do_POST(self):
        if not self.guard(write=True):
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 500000 or self.headers.get("Content-Type") != "application/json":
                return self.reply(413, {"error": "请求过大或格式无效。"})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("请求必须是对象。")
            result = self.server.app.post(urlsplit(self.path).path, data)
            return self.reply(200, result)
        except ValueError as exc:
            message = str(exc)
            # Only application-authored Chinese validations are safe for the UI.
            safe = message if re.search(r"[\u4e00-\u9fff]", message) and len(message) < 180 and ':\\' not in message else "配置无效或名称已存在；请选择新名称并核对输入。"
            return self.reply(400, {"error": safe})
        except (OSError, subprocess.SubprocessError):
            return self.reply(409, {"error": "本地操作未完成。保存计划需要 Docker 与所选题目的镜像；配置操作需要有效来源文件。"})
        except (KeyError, TypeError):
            return self.reply(400, {"error": "请求字段缺失或格式无效。"})


def serve(root, port=8765, open_browser=True):
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535")
    server = LocalServer(root, port)
    print(f"本地工作台：{server.origin} · 本版本不从页面启动模型 · Ctrl+C 关闭", flush=True)
    if open_browser:
        webbrowser.open(server.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
