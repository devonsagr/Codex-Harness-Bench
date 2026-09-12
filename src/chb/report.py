import html
import os
from pathlib import Path
from urllib.parse import quote

from chb.profiles import read_json, write_json
from chb.experiments import group_comparisons, planned_tasks, task_for_trial


def fmt(value):
    return "—" if value is None else html.escape(str(value))


def render(experiment, *, results=None, output_dir=None, analysis=None):
    experiment = Path(experiment).resolve()
    output_dir = Path(output_dir).resolve() if output_dir is not None else experiment
    def source_link(relative):
        return quote(Path(os.path.relpath(experiment / relative, output_dir)).as_posix(), safe="/:")
    plan = read_json(experiment / "plan.json")
    tasks = planned_tasks(plan)
    if results is None:
        results = {}
        for trial in plan["trials"]:
            result_file = experiment / trial["id"] / "result.json"
            results[trial["id"]] = read_json(result_file) if result_file.exists() else {"status": "not_run"}
    groups = group_comparisons(plan, results)
    rows, step_sections = [], []
    for trial in plan["trials"]:
        result = results.get(trial["id"], {"status": "not_run"})
        task_name, task = task_for_trial(plan, trial)
        rows.append("<tr>" + "".join(f"<td>{fmt(value)}</td>" for value in (
            trial["id"], task_name, trial.get("repeat", 0) + 1, trial["profile"], result.get("status"), result.get("accepted"),
            result.get("agent_seconds"), result.get("input_tokens"),
            result.get("cached_input_tokens"), result.get("output_tokens"), result.get("effective_profile_evidence"),
        )) + (f'<td><a href="{quote(trial["id"])}/result.json">结果</a> · '
              f'<a href="{source_link(trial["id"] + "/harbor")}/">完整产物</a></td></tr>'
              if result.get("status") != "not_run" else '<td>尚无产物</td></tr>'))
        if result.get("steps"):
            step_rows = []
            for step in result["steps"]:
                skill_reads = ", ".join(read["skill"] for read in step.get("skill_reads", []) if read["complete_read_output_observed"]) or "未观察到"
                step_rows.append("<tr>" + "".join(f"<td>{fmt(value)}</td>" for value in (
                    step["name"], step["status"], step["accepted"], step["agent_seconds"],
                    step.get("input_tokens"), step.get("cached_input_tokens"), step.get("output_tokens"),
                    step.get("profile_load_index"), len(step.get("loaded_skills", [])), skill_reads,
                )) + f'<td><a href="{source_link(trial["id"] + "/" + step["evidence_path"])}/">逐轮证据</a></td></tr>')
            step_sections.append(f'<h2>{fmt(trial["id"])} · {fmt(task_name)} · {fmt(trial["profile"])}</h2><p>同一会话续接：{fmt(result.get("session_continuity_observed"))} · 完成 {len(result["steps"])} 轮</p>'
                                 '<div class="scroll"><table><tr><th>轮次</th><th>状态</th><th>验收</th><th>Agent 秒数</th><th>本轮输入</th><th>其中缓存</th><th>本轮输出</th><th>配置加载轮次</th><th>Skill 文件数</th><th>完整读取证据</th><th>产物</th></tr>'
                                 + "".join(step_rows) + '</table></div>'
                                 + f'<p>用量校验：{fmt((result.get("usage_accounting") or {}).get("status", "unavailable"))} · 原因：{fmt((result.get("usage_accounting") or {}).get("reason"))}</p>')
    content = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Codex Harness Bench</title>
<style>body{font:16px/1.7 system-ui,sans-serif;max-width:1120px;margin:48px auto;padding:0 24px;color:#23302c;background:#f6f7f3}h1{font-size:34px;margin:0}p{max-width:850px}table{border-collapse:collapse;background:white;width:100%;font-size:14px}td,th{padding:14px;text-align:left;border-bottom:1px solid #d6ded7}th{background:#e7ede8}a{color:#166044}.note{border-left:4px solid #a17824;padding:12px 18px;background:#fff9e9}.scroll{overflow:auto}code{font-size:13px;overflow-wrap:anywhere}</style>
<p>本地实验</p><h1>Codex 配置对比</h1>
<p class="note">这是小规模原创题的流程验证，不能据此判断哪套配置更好。任务组来自题目声明，尚未证明统计独立；多轮与同题重复都不增加独立样本。缺失数据用 — 表示；费用未作为实际账单估算。源代码尚未发布的任务不能计入公开基准成绩。</p>"""
    content += f'<p>实验：<code>{fmt(plan["id"])}</code><br>模型：{fmt(plan["model"])} · Codex {fmt(plan["codex_version"])} · Harbor {fmt(plan["harbor_version"])}<br>题目：{len(tasks)} · 声明任务组：{len(groups)} · 重复：{fmt(plan["repeat"])} · 总运行：{len(plan["trials"])}</p>'
    content += '<p>' + '<br>'.join(f'{fmt(name)} · {fmt(task["group"])} · 每次 {max(1, len(task["step_names"]))} 轮' for name, task in tasks.items()) + '</p>'
    content += f'<p>计划 Agent 轮次：{fmt(plan.get("planned_agent_turns"))} · Agent 总预算上限：{fmt(plan.get("max_total_agent_seconds"))} 秒（不含环境准备和验收）</p>'
    if analysis is not None:
        content += f'<p class="note">这是已有日志的重新分析，未调用模型；原计划、原验收结果和原报告保留不变。<br>分析编号：{html.escape(analysis["id"])} · <a href="analysis.json">来源哈希与分析版本</a> · <a href="{source_link("report.html")}">原报告</a></p>'
    group_rows = []
    for group in groups:
        for profile, values in group["profiles"].items():
            group_rows.append('<tr>' + ''.join(f'<td>{fmt(value)}</td>' for value in (
                group["group"], profile, values["planned"], values["accepted"], values["failed"], values["error"], values["pending"],
                f'{group["accepted_pairs"]}/{group["planned_pairs"]}', values["paired_agent_seconds"],
            )) + '</tr>')
    content += '<h2>同批按组对比</h2><p>计数单位为整题运行；多轮题须全部通过。秒数只合计同题、同重复中双方都通过的配对，并显示覆盖数；没有配对或任一耗时缺失时显示 —。任务组之间不拼成速度排名。</p>'
    content += '<div class="scroll"><table><tr><th>任务组</th><th>配置</th><th>计划</th><th>通过</th><th>未通过</th><th>异常</th><th>待完成</th><th>双方通过配对</th><th>配对 Agent 秒数</th></tr>' + ''.join(group_rows) + '</table></div>'
    content += '<h2>逐次运行与证据</h2><div class="scroll"><table><tr><th>顺序</th><th>题目</th><th>重复</th><th>配置</th><th>执行状态</th><th>全部验收通过</th><th>Agent 秒数</th><th>输入 tokens</th><th>其中缓存</th><th>输出 tokens</th><th>配置加载证据</th><th>证据</th></tr>' + "".join(rows) + '</table></div>'
    content += "".join(step_sections)
    if any(task["step_names"] for task in tasks.values()):
        content += '<p>多轮用量须通过原生会话编号、历史记录前缀、计数不回退与 CLI 上报一致性检查。通过后，总量取最后累计值，各轮取相邻差值；缺证据显示 —，原因写入结果。输入已包含缓存，不能再加一次。Skill 文件上传与完整读取分别记录，读取不等于完全遵循。</p>'
    content += f'<p>固定项：模型、推理档位、Codex 版本、任务快照、容器镜像、权限、网络策略、每轮 300 秒 Agent 上限。变化项：见配置内容对比。</p><p><a href="{source_link("plan.json")}">冻结的实验计划</a> · <a href="{source_link("profile-diff.txt")}">配置差异</a> · <a href="comparison.json">分组汇总数据</a></p></html>'
    write_json(output_dir / "comparison.json", {"schema": 1, "experiment": plan["id"], "groups": groups,
                                               "statistical_claim": "none; descriptive paired coverage only"})
    target = output_dir / "report.html"
    target.write_text(content, encoding="utf-8")
    return target
