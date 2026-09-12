import html
from pathlib import Path

from chb.profiles import read_json


def render(experiment):
    experiment = Path(experiment)
    plan = read_json(experiment / "plan.json")
    rows, step_sections = [], []
    for trial in plan["trials"]:
        result_file = experiment / trial["id"] / "result.json"
        result = read_json(result_file) if result_file.exists() else {"status": "not_run"}
        def fmt(value):
            return "—" if value is None else html.escape(str(value))
        rows.append("<tr>" + "".join(f"<td>{fmt(value)}</td>" for value in (
            trial["profile"], result.get("status"), result.get("accepted"),
            result.get("agent_seconds"), result.get("input_tokens"),
            result.get("output_tokens"), result.get("effective_profile_evidence"),
        )) + f'<td><a href="{trial["id"]}/result.json">结果</a> · '
             f'<a href="{trial["id"]}/harbor/">完整产物</a></td></tr>')
        if result.get("steps"):
            step_rows = []
            for step in result["steps"]:
                skill_reads = ", ".join(read["skill"] for read in step.get("skill_reads", []) if read["complete_read_output_observed"]) or "未观察到"
                step_rows.append("<tr>" + "".join(f"<td>{fmt(value)}</td>" for value in (
                    step["name"], step["status"], step["accepted"], step["agent_seconds"],
                    step.get("profile_load_index"), len(step.get("loaded_skills", [])), skill_reads,
                )) + f'<td><a href="{html.escape(trial["id"] + "/" + step["evidence_path"], quote=True)}/">逐轮证据</a></td></tr>')
            step_sections.append(f'<h2>{fmt(trial["profile"])} · 连续迭代</h2><p>同一会话续接：{fmt(result.get("session_continuity_observed"))} · 完成 {len(result["steps"])} 轮</p>'
                                 '<div class="scroll"><table><tr><th>轮次</th><th>状态</th><th>验收</th><th>Agent 秒数</th><th>配置加载轮次</th><th>Skill 文件数</th><th>完整读取证据</th><th>产物</th></tr>'
                                 + "".join(step_rows) + '</table></div>')
    content = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Codex Harness Bench</title>
<style>body{font:16px/1.7 system-ui,sans-serif;max-width:1120px;margin:48px auto;padding:0 24px;color:#23302c;background:#f6f7f3}h1{font-size:34px;margin:0}p{max-width:850px}table{border-collapse:collapse;background:white;width:100%;font-size:14px}td,th{padding:14px;text-align:left;border-bottom:1px solid #d6ded7}th{background:#e7ede8}a{color:#166044}.note{border-left:4px solid #a17824;padding:12px 18px;background:#fff9e9}.scroll{overflow:auto}code{font-size:13px;overflow-wrap:anywhere}</style>
<p>本地实验</p><h1>Codex 配置对比</h1>
<p class="note">这是一组题目的流程验证，不能据此判断哪套配置更好。多轮属于同一任务，不增加独立样本数。缺失数据用 — 表示；费用未作为实际账单估算。源代码尚未发布的任务不能计入公开基准成绩。</p>"""
    content += f'<p>实验：<code>{html.escape(plan["id"])}</code><br>模型：{html.escape(plan["model"])} · Codex {plan["codex_version"]} · Harbor {plan["harbor_version"]}<br>独立任务：1 · 重复：{plan["repeat"]} · 总运行：{len(plan["trials"])}</p>'
    content += f'<p>题目：{html.escape(plan.get("task_name", "search-notes-v1"))} · 每配置 {max(1, len(plan.get("step_names", [])))} 轮</p>'
    content += '<div class="scroll"><table><tr><th>配置</th><th>执行状态</th><th>全部验收通过</th><th>Agent 秒数</th><th>输入 tokens</th><th>输出 tokens</th><th>配置加载证据</th><th>证据</th></tr>' + "".join(rows) + '</table></div>'
    content += "".join(step_sections)
    if plan.get("step_names"):
        content += '<p>Skill 文件上传与完整读取分别记录，读取不等于完全遵循。多轮 token 总数暂不展示：保留各轮原始上报值，避免会话续接时把累计用量相加。轨迹、原始用量、候选代码和验收日志见逐轮证据。</p>'
    content += '<p>固定项：模型、推理档位、Codex 版本、任务快照、容器镜像、权限、网络策略、每轮 300 秒 Agent 上限。变化项：见配置内容对比。</p><p><a href="plan.json">冻结的实验计划</a> · <a href="profile-diff.txt">配置差异</a></p></html>'
    target = experiment / "report.html"
    target.write_text(content, encoding="utf-8")
    return target
