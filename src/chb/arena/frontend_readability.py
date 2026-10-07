"""Extract declared browser measurements; never infer a design grade from them."""
import json
import math
from .files import fingerprint

VERSION='browser-readability-v1'
PREFIX='BROWSER_READABILITY '
CHECK_ID='frontend-readability-v1'
IMAGE='chb-verifier:creative-web-v1'
ARGV=['node','/tests/readability-check.cjs','/app']
FOCUS={
    'readable':'正文、标签和反馈能看清；检查字号、截字、重叠、层次和窄屏，不能只看标题是否在视口内。',
    'plain_language':'页面文案与交付说明清楚直接，符合目标用户；内部工程术语应有必要，不用长篇说明掩盖难用。',
    'usable_flow':'从用户目标实际走完关键流程，检查反馈、错误、键盘和触控；按钮变色不等于任务完成。',
    'appropriate_scope':'新增页面、依赖、抽象和操作步骤应有需求理由；实现简单而够用是优点，不能按文件数处罚，也不奖励工程规模。',
}
INSTRUCTION=(
    '\n这是前端交付审查：按frontendReviewFocus检查能看清、能看懂、能操作、实现是否适度。'
    'browserReadability是固定浏览器检查产生的测量数据，不是设计评分；有风险样本须在页面复现并解释其实际影响。'
    'ux或visual拟给75分及以上时，每种风险至少回应一个样本；evidence使用其checkId并从checks.output原文引用包含kind和text的JSON片段，不能仅引用PASS。'
    '若判为不构成问题，要解释文本用途、可用替代或操作间距，不因程序检查passed忽略这些样本。'
    '字号触发值不能一律当作规范，元数据与图注要区别于正文/控件。'
    '保存截图后必须实际查看画面，说明看到的区域与具体问题；仅DOM输出、截图文件存在或源码引用不能证明视觉质量。'
    '无法实际看图时如实保留视觉未验证，不推测审美。'
    '维护性审查必须结合需求说明复杂度是否必要；架构、模块数、依赖多不自动加分。'
    '这些观察仍映射已有冻结维度与权重，不增加隐藏需求、额外加分或未经校准的新综合分。'
)


def check_definition(task,capture):
    """One fixed offline entry point, separate from task acceptance and weights."""
    if not task.get('hasFrontendUI') or 'index.html' not in capture.get('manifest',{}).get('files',{}):return None
    return {'id':CHECK_ID,'label':'浏览器文字与操作区域实测','image':IMAGE,'argv':ARGV.copy(),'weight':0,'timeout':60}


def diagnostic_checks(task,capture):
    return [row for row in capture.get('readabilityChecks',[]) if row.get('id')==CHECK_ID
            and row.get('captureHash')==capture['manifest']['sha256'] and row.get('taskHash')==fingerprint(task)
            and row.get('argv')==ARGV]


def extract(task,checks,capture=None):
    allowed={row['id'] for row in task.get('checks',[]) if row.get('image')=='chb-verifier:creative-web-v1'
             and row.get('argv',[])[:3]==['node','/tests/verify.cjs','/app']}
    measurements=diagnostic_checks(task,capture) if capture and check_definition(task,capture) else []
    checks=[*(row for row in checks if row.get('id') in allowed),*measurements]
    views=[]
    for check in checks:
        for line in str(check.get('output','')).splitlines():
            if not line.startswith(PREFIX) or len(line)>30000:continue
            try:data=json.loads(line[len(PREFIX):])
            except ValueError:continue
            if not isinstance(data,dict) or data.get('version')!=VERSION:continue
            viewport=data.get('viewport')
            if not isinstance(viewport,dict) or any(type(viewport.get(k)) is not int or not 100<=viewport[k]<=5000 for k in ('width','height')):continue
            if any(type(data.get(k)) is not int or not 0<=data[k]<=3000 for k in ('sampledText','sampledControls')):continue
            font=data.get('smallestBodyFont')
            if font is not None and (type(font) not in (int,float) or not math.isfinite(font) or not 0<=font<=1000):continue
            concerns=data.get('concerns')
            if not isinstance(concerns,list) or len(concerns)>32:continue
            def valid_concern(c):
                if not isinstance(c,dict) or c.get('kind') not in {'small-text','clipped-text','overlapping-text','small-control'}:return False
                if any(not isinstance(c.get(k),str) or len(c[k])>500 for k in ('selector','text')):return False
                bounds=c.get('bounds')
                if not isinstance(bounds,dict) or any(type(bounds.get(k)) not in (int,float) or not math.isfinite(bounds[k]) for k in ('x','y','width','height')):return False
                if 'fontSize' in c and (type(c['fontSize']) not in (int,float) or not math.isfinite(c['fontSize']) or not 0<=c['fontSize']<=1000):return False
                if c['kind']=='small-text' and 'fontSize' not in c:return False
                return all(isinstance(c.get(k,''),str) and len(c.get(k,''))<=500 for k in ('otherText','otherSelector','container','role','lineHeight'))
            if any(not valid_concern(c) for c in concerns):continue
            views.append({'version':VERSION,'viewport':viewport,'sampledText':data['sampledText'],
                'sampledControls':data['sampledControls'],'smallestBodyFont':font,'concerns':concerns,
                'limited':bool(data.get('limited')),'checkId':check['id'],'imageId':check.get('imageId'),'checkStatus':check.get('status')})
    return {'version':VERSION,'views':views,'scoresAreAdvisory':True,
            'note':'只记录本次浏览器测量，不证明整题通过、模型看过图像或审美结论正确。'} if views else None
