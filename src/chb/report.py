import html
from pathlib import Path

from chb.profiles import read_json


def render(experiment):
    experiment = Path(experiment)
    plan = read_json(experiment / "plan.json")
    rows = []
    for trial in plan["trials"]:
        result_file = experiment / trial["id"] / "result.json"
        result = read_json(result_file) if result_file.exists() else {"status": "not_run"}
        def fmt(value):
            return "—" if value is None else html.escape(str(value))
        rows.append("<tr>" + "".join(f"<td>{fmt(value)}</td>" for value in (
            trial["profile"], result.get("status"), result.get("accepted"),
            result.get("agent_seconds"), result.get("input_tokens"),
            result.get("output_tokens"), result.get("profile_marker_observed"),
        )) + f'<td><a href="{trial["id"]}/result.json">结果</a> · '
             f'<a href="{trial["id"]}/harbor/">完整产物</a></td></tr>')
    content = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Codex Harness Bench</title>
<style>body{font:16px/1.7 system-ui,sans-serif;max-width:1120px;margin:48px auto;padding:0 24px;color:#23302c;background:#f6f7f3}h1{font-size:34px;margin:0}p{max-width:850px}table{border-collapse:collapse;background:white;width:100%;font-size:14px}td,th{padding:14px;text-align:left;border-bottom:1px solid #d6ded7}th{background:#e7ede8}a{color:#166044}.note{border-left:4px solid #a17824;padding:12px 18px;background:#fff9e9}.scroll{overflow:auto}code{font-size:13px;overflow-wrap:anywhere}</style>
<p>本地实验 · v0.1</p><h1>Codex 配置对比</h1>
<p class="note">这是一个题目的一次管线验证，不能据此判断哪套配置更好。缺失数据用 — 表示；费用未作为实际账单估算。源代码尚未发布的任务不能计入公开基准成绩。</p>"""
    content += f'<p>实验：<code>{html.escape(plan["id"])}</code><br>模型：{html.escape(plan["model"])} · Codex {plan["codex_version"]} · Harbor {plan["harbor_version"]}<br>独立任务：1 · 重复：{plan["repeat"]} · 总运行：{len(plan["trials"])}</p>'
    content += '<div class="scroll"><table><tr><th>配置</th><th>执行状态</th><th>验收通过</th><th>Agent 秒数</th><th>输入 tokens</th><th>输出 tokens</th><th>配置标记</th><th>证据</th></tr>' + "".join(rows) + '</table></div>'
    content += '<p>固定项：模型、推理档位、Codex 版本、任务快照、容器镜像、权限、网络策略、300 秒 Agent 上限。变化项：见配置内容对比。</p><p><a href="plan.json">冻结的实验计划</a> · <a href="profile-diff.txt">配置差异</a></p></html>'
    target = experiment / "report.html"
    target.write_text(content, encoding="utf-8")
    return target
