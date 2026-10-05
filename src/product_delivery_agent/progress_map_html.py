"""Self-contained, read-only delivery maps that work directly from file://."""
from __future__ import annotations

import html
import json


def render_progress_map(model: dict, *, live: bool = True, enabled: bool = True) -> str:
    """Render a portable map; model data is never interpolated into executable JS."""
    active = bool(enabled and model.get("enabled", True))
    payload = json.dumps({"model": model, "live": bool(live and active), "enabled": active}, ensure_ascii=False)
    # HTML's script parser recognizes end tags even in JSON string literals.
    payload = (payload.replace("&", "\\u0026").replace("<", "\\u003c")
               .replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    title = html.escape(str(model.get("title") or "交付进度地图"), quote=True)
    return ("<!doctype html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{title} · 交付进度地图</title><style>{_CSS}</style></head>"
            '<body><a class="skip-link" href="#main">跳到进度地图</a><main id="main">'
            '<noscript>请启用 JavaScript 查看交付地图。此页面无需网络连接。</noscript></main>'
            f'<script id="progress-map-data" type="application/json">{payload}</script>'
            f"<script>{_JS}</script></body></html>\n")


_CSS = r"""
:root{color-scheme:light;--paper:#f3f7fb;--ink:#183149;--muted:#536b81;--line:#cedbe7;--blue:#255d94;--blue-light:#e8f1fa;--orange:#a34c0f;--orange-light:#fff2df;--green:#226c51;--white:#fff;font-family:"Aptos","Noto Sans CJK SC","Microsoft YaHei","PingFang SC",sans-serif;font-size:15px;line-height:1.6}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink)}button{font:inherit;cursor:pointer}button,a{-webkit-tap-highlight-color:transparent}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid var(--blue);outline-offset:4px}button{min-height:44px}button:hover{background:var(--blue-light)}button:active{transform:translateY(1px)}[hidden]{display:none!important}h1,h2,h3,h4,p{margin:0}h1{font-size:clamp(25px,3vw,39px);font-weight:750;letter-spacing:-.035em;line-height:1.25}h2{font-size:20px;letter-spacing:-.02em}h3{font-size:17px}h4{font-size:14px}p,li,dd,small,strong,button{overflow-wrap:anywhere}ul,ol{padding-left:20px}a{color:var(--blue)}.skip-link{position:absolute;top:-80px;left:20px;z-index:9;background:white;padding:12px}.skip-link:focus{top:12px}#main{max-width:1680px;margin:0 auto;padding:38px 42px 56px}.masthead{display:flex;gap:24px;justify-content:space-between;align-items:flex-start;padding-bottom:28px;border-bottom:2px solid var(--ink)}.masthead-copy{max-width:850px}.masthead p{max-width:75ch;margin-top:12px;color:var(--muted)}.edition{flex-shrink:0;text-align:right;max-width:260px;font-size:13px;color:var(--muted)}.edition strong{font-size:17px;color:var(--ink);display:block}.edition span{display:block}.live-indicator{display:inline-flex!important;align-items:center;gap:7px;color:var(--green);margin-top:7px}.live-indicator:before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}.notice{margin:16px 0;padding:12px 16px;border-left:3px solid var(--orange);background:var(--orange-light);color:#754011}.toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:20px 0}.toolbar button{border:1px solid var(--line);border-radius:5px;background:var(--white);padding:8px 14px;font-size:14px;color:var(--ink)}.toolbar button[aria-pressed="true"]{background:var(--ink);color:white;border-color:var(--ink)}.toolbar button#locate-current{margin-left:auto;border-color:#cb9a65;color:var(--orange);background:var(--orange-light)}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:24px;align-items:start}.main-column{min-width:0}.map-panel,.content-panel{border:1px solid var(--line);background:var(--white);border-radius:8px;overflow:hidden}.panel-heading{padding:21px 24px 17px;display:flex;gap:16px;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line)}.panel-heading p{font-size:13px;color:var(--muted);margin-top:4px}.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted)}.legend span{display:flex;gap:5px;align-items:center}.legend i{width:9px;height:9px;display:inline-block;border:1px solid var(--muted);border-radius:2px}.legend .working{background:var(--orange-light);border-color:var(--orange)}.legend .verified{background:#dcefe5;border-color:var(--green)}.map-canvas{position:relative;padding:30px 26px 42px;background-color:#f9fcff;background-image:radial-gradient(#d2dfed .8px,transparent .8px);background-size:16px 16px}.map-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:84px;row-gap:92px;position:relative;z-index:1}.component{min-width:0;align-self:start;border:1px solid #a9bfd3;border-radius:7px;background:var(--white);padding:17px;box-shadow:0 3px 0 #e0e9f1}.component.current{border-top:3px solid var(--orange);padding-top:15px}.component-header{margin-bottom:16px}.component-header p{font-size:13px;color:var(--muted);margin-top:5px}.component-label{font-size:11px;color:var(--muted);margin-bottom:5px;display:block}.component.current .component-label{color:var(--orange)}.capability{border-top:1px solid #e4ebf2;padding-top:9px;margin-top:9px}.capability-button{width:100%;text-align:left;display:flex;align-items:flex-start;gap:8px;justify-content:space-between;padding:8px 6px;border:0;border-radius:4px;background:transparent;color:var(--ink)}.capability-button .cap-name{font-size:14px;font-weight:650;line-height:1.5}.capability-button .cap-name:before{content:"+";font-size:16px;font-weight:400;margin-right:7px;color:var(--blue)}.capability-button[aria-expanded="true"] .cap-name:before{content:"−"}.status{display:inline-block;font-size:11px;line-height:1.5;border:1px solid var(--line);border-radius:3px;padding:2px 5px;white-space:nowrap;color:var(--muted);background:#f5f8fb}.status.working{background:var(--orange-light);border-color:#dfbd96;color:var(--orange)}.status.verified,.status.reviewed,.status.delivered,.status.complete,.status.approved{background:#e8f5ee;border-color:#abd1bd;color:var(--green)}.capability-detail{font-size:13px;padding:8px 6px 12px}.capability-detail p{color:var(--muted)}.capability-detail h4{margin-top:16px}.capability-detail ul{margin:5px 0}.milestones{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:7px;margin:12px 0!important}.milestones li{font-size:11px;padding:3px 6px;border:1px solid var(--line);border-radius:3px;color:var(--muted)}.milestones li[data-complete="true"]{color:var(--green);border-color:#abd1bd;background:#e8f5ee}.source{display:block;border-left:2px solid var(--line);padding:5px 8px;margin-top:6px;word-break:break-all}.source small{display:block;color:var(--muted);font-size:11px}.node-task{margin-top:6px;padding:7px;background:var(--paper)}#connectors{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:2;overflow:visible}#connectors .edge{fill:none;stroke:var(--blue);stroke-width:1.6}#connectors .dependency{stroke-dasharray:5 4}#connectors text{font-family:inherit;font-size:11px;fill:var(--blue);paint-order:stroke;stroke:#f9fcff;stroke-width:6;stroke-linejoin:round}.edge-list{margin:0;padding:12px 24px;list-style:none;font-size:12px;color:var(--muted);border-top:1px solid var(--line)}.edge-list li{margin:3px 0}.goal-line{padding:15px 24px;border-bottom:1px solid var(--line);display:flex;gap:12px;flex-wrap:wrap;font-size:13px;background:#eef5fc}.goal-line strong{color:var(--blue)}.sidebar{position:sticky;top:20px;min-width:0}.current-work{background:#fffaf2;border:1px solid #dcc3a1;border-top:4px solid var(--orange);border-radius:5px;padding:22px}.current-work .label{color:var(--orange);font-size:13px;margin-bottom:9px}.current-work h2{font-size:21px}.current-work>p{font-size:14px;margin-top:12px;color:var(--muted)}.current-work dl{margin:21px 0 0}.current-work dt{font-size:12px;color:var(--muted);margin-top:18px}.current-work dd{font-size:14px;margin:3px 0 0}.current-work dd ul{margin:0}.next-action{border-top:1px solid #e9d7be;margin-top:22px;padding-top:16px}.next-action span{font-size:12px;color:var(--orange)}.next-action p{margin-top:5px;font-size:15px;font-weight:600}.aside-note{margin:14px 6px;color:var(--muted);font-size:12px}.stages-panel{margin-top:24px;padding:22px 24px;background:var(--white);border:1px solid var(--line);border-radius:8px}.stages-panel p{color:var(--muted);font-size:13px;margin-top:4px}#stages{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;list-style:none;padding:0;margin:22px 0 0}#stages li{position:relative;border-top:3px solid var(--line);padding:10px 0 0}#stages li[data-status="current"],#stages li[data-status="working"],#stages li[data-status="in_progress"]{border-color:var(--orange)}#stages li[data-status="complete"],#stages li[data-status="completed"],#stages li[data-status="passed"]{border-color:var(--green)}#stages strong{font-size:14px;display:block}#stages small{color:var(--muted);font-size:11px}.content-panel{padding:24px}.content-panel>p{font-size:14px;color:var(--muted);margin:8px 0 20px}.list-item{padding:19px 0;border-top:1px solid var(--line)}.list-item p{font-size:14px;color:var(--muted);margin-top:6px}.list-item .action{color:var(--blue)}.list-item small{font-size:12px;color:var(--muted)}.history-title{margin-top:30px}.baseline{margin:12px 0 20px;padding:12px;background:var(--paper);font-size:13px}.empty{padding:28px 18px;text-align:center;color:var(--muted);font-size:14px}.requirements{margin-top:22px;padding:0 4px;font-size:13px;color:var(--muted)}.requirements summary{min-height:44px;cursor:pointer;display:list-item}.requirements ul{margin-top:0}footer{display:flex;gap:15px;justify-content:space-between;flex-wrap:wrap;margin-top:28px;color:var(--muted);font-size:11px;border-top:1px solid var(--line);padding-top:15px}.disabled{max-width:760px;margin:12vh auto;padding:38px;border:1px solid var(--line);border-left:5px solid var(--orange);background:white}.disabled p{margin-top:14px;color:var(--muted)}
@media(min-width:1500px){.workspace{grid-template-columns:minmax(0,1fr) 350px}.map-grid{column-gap:110px}.map-canvas{padding:36px 40px 45px}}
.map-meta{display:flex;gap:8px 24px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-top:12px}.live-indicator.frozen{color:var(--orange)}.roadmap{padding:14px 24px 18px;border-bottom:1px solid var(--line)}.roadmap h3{font-size:12px;color:var(--muted);font-weight:500;margin-bottom:10px}#roadmap-versions{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:0}#roadmap-versions li{flex:1;min-width:140px;padding:8px 15px 8px 0;border-top:2px solid var(--line)}#roadmap-versions li[aria-current="step"]{border-color:var(--blue)}#roadmap-versions strong{display:block;font-size:13px}#roadmap-versions span{font-size:12px;color:var(--muted)}#roadmap-versions em{font-style:normal;color:var(--blue);font-size:11px;margin-left:8px}.comparison-label{color:var(--blue)!important}.change-summary{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px}.change-summary>div{padding:10px 12px;background:var(--paper);border-left:2px solid var(--line)}.change-summary>div:last-child{border-color:var(--blue)}.change-summary small{display:block}.change-detail{margin-top:14px}.change-detail summary{min-height:44px;padding:10px 0;cursor:pointer;color:var(--blue);font-size:13px}.change-columns{display:grid;grid-template-columns:1fr 1fr;gap:18px}.change-columns>div{min-width:0;padding:14px;background:var(--paper);border:1px solid var(--line);border-radius:4px}.change-columns h4{margin-bottom:10px}.change-columns dl{margin:0}.change-columns dt{font-size:12px;color:var(--muted);margin-top:12px}.change-columns dd{font-size:13px;margin:2px 0 0;white-space:pre-wrap}.change-columns ul{margin:3px 0}.change-columns pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}
@media(max-width:1100px){#main{padding:26px 24px}.workspace{grid-template-columns:minmax(0,1fr) 270px;gap:18px}.map-grid{column-gap:40px}.map-canvas{padding:24px 17px}.component{padding:12px}.panel-heading{align-items:flex-start;flex-direction:column}.current-work{padding:18px}}
@media(max-width:850px){.workspace{grid-template-columns:minmax(0,1fr)}.sidebar{position:static;grid-row:1}.current-work{display:grid;grid-template-columns:1fr 1fr;gap:0 24px}.current-work .label{grid-column:1/-1}.current-work>p{grid-column:1}.current-work dl{grid-column:2;grid-row:2/5;margin:0}.current-work dt:first-child{margin-top:0}.next-action{grid-column:1/-1}.aside-note{display:none}.panel-heading{flex-direction:row}.map-grid{column-gap:85px}.toolbar button#locate-current{margin-left:0}}
@media(max-width:540px){#main{padding:22px 16px 32px}.masthead{display:block;padding-bottom:20px}.masthead h1{font-size:27px}.edition{text-align:left;max-width:none;margin-top:18px;display:flex;gap:6px 14px;flex-wrap:wrap;align-items:center}.edition strong{font-size:14px}.edition .timestamp{width:100%}.live-indicator{margin:0}.toolbar{gap:8px;padding:17px 0}.toolbar button{padding:8px 11px;font-size:13px;flex-grow:1}.current-work{display:block}.current-work dl{margin-top:14px}.current-work dt{margin-top:12px}.current-work h2{font-size:20px}.panel-heading{padding:17px;display:block}.legend{margin-top:12px}.goal-line{padding:13px 17px}.map-canvas{padding:24px 18px 30px}.map-grid{grid-template-columns:minmax(0,1fr);row-gap:80px}.component{padding:16px}.component.current{padding-top:14px}.stages-panel{padding:18px}#stages{grid-template-columns:repeat(3,minmax(0,1fr));row-gap:22px}.content-panel{padding:18px}.edge-list{padding:12px 18px}.disabled{padding:24px;margin:7vh auto}.disabled h1{font-size:24px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important;transition:none!important}}@media print{.toolbar,.skip-link{display:none}.sidebar{position:static}.workspace{display:block}.current-work{margin-top:20px}.map-panel,.component{break-inside:avoid}#main{padding:0}}
@media(max-width:540px){.roadmap{padding:14px 17px}.change-columns{grid-template-columns:minmax(0,1fr)}.change-summary{gap:10px}.map-meta{display:block}.map-meta span{display:block;margin-top:4px}}
.scenario-trace{border-left:2px solid #9ab8d4;padding:2px 0 2px 12px;margin-top:14px}.scenario-trace>strong{display:block;font-size:12px}.scenario-trace>p{margin-top:5px}.obligation-trace{border-top:1px solid var(--line);padding-top:10px;margin-top:12px}.obligation-trace>strong{display:block;font-size:12px}.obligation-trace>small{display:block;color:var(--muted);font-size:11px}.obligation-trace .status{margin:6px 0}.trace-heading{color:var(--ink)!important;font-size:12px;font-weight:600;margin-top:8px}.trace-error{color:#913f13!important;background:var(--orange-light);border-left:2px solid var(--orange);padding:7px 9px;margin-top:9px!important}.source[data-status="stale"]{border-color:var(--orange)}.source .source-error{color:#913f13}
"""


_JS = r"""
(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('progress-map-data').textContent);
  const m = config.model || {};
  const root = document.getElementById('main');
  const list = value => Array.isArray(value) ? value : [];
  const str = (value, fallback = '') => value === undefined || value === null || value === '' ? fallback : String(value);
  const el = (tag, text, cls) => {const node = document.createElement(tag); if (text !== undefined) node.textContent = str(text); if (cls) node.className = cls; return node;};
  const append = (parent, ...children) => {children.forEach(child => parent.appendChild(child)); return parent;};
  const statusNames = {unknown:'待核实',planned:'待实现',pending:'待开始',working:'进行中',in_progress:'进行中',current:'当前阶段',produced:'已产出',integrated:'已集成',verified:'已验证',reviewed:'已评审',delivered:'已交付',complete:'已完成',completed:'已完成',passed:'已通过',approved:'已确认',blocked:'有阻塞',failed:'未通过',present:'已找到',missing:'缺失',stale:'已过期',not_started:'待开始'};
  const status = value => str(statusNames[value], str(value, '待核实'));
  const knownStatus = value => Object.hasOwn(statusNames, value) ? value : 'unknown';
  const badge = value => el('span', status(value), 'status ' + knownStatus(value));
  const notes = (parent, values) => {const ul = el('ul'); list(values).forEach(value => ul.appendChild(el('li', value))); if (ul.children.length) parent.appendChild(ul);};
  const field = (parent, label, value) => {append(parent, el('dt', label), el('dd', str(value, '待明确')));};
  const storageKey = 'waygate-progress-map:' + str(m.delivery_id, str(m.feature_slug, 'unassigned'));
  let saved = {}; try {saved = JSON.parse(sessionStorage.getItem(storageKey) || '{}') || {};} catch (_) {}
  const state = {view: ['architecture','remaining','changes'].includes(saved.view) ? saved.view : 'architecture', selected: str(saved.selected), currentVersion: saved.currentVersion === true, scroll: Number.isFinite(saved.scroll) ? saved.scroll : 0};
  const persist = () => {try {sessionStorage.setItem(storageKey, JSON.stringify(state));} catch (_) {}};
  const saveScroll = () => {state.scroll = window.scrollY; persist();};
  const header = el('header', undefined, 'masthead');
  const copy = el('div', undefined, 'masthead-copy');
  append(copy, el('h1', m.title || m.feature_slug || '交付进度地图'), el('p', m.objective || '交付目标尚未记录。明确目标后，地图将展示目标与能力的对应关系。'));
  const edition = el('div', undefined, 'edition');
  append(edition, el('strong', m.current_version || '当前交付'), el('span', !config.enabled ? '自动更新已关闭' : config.live ? '实时地图 · 每 5 秒更新' : '离线快照 · 内容已固定', 'live-indicator' + (!config.enabled ? ' frozen' : '')), el('span', '数据时间：' + str(m.generated_at, '尚未记录'), 'timestamp'));
  append(header, copy, edition); root.replaceChildren(header);
  const meta=el('div',undefined,'map-meta');const identity=el('span','交付标识：'+str(m.delivery_id,'尚未分配'));identity.id='delivery-identity';const settingNames={system_default:'系统默认设置',project_default:'项目默认设置',delivery_override:'本次交付设置'};const setting=el('span','设置来源：'+str(settingNames[m.settings_source],str(m.settings_source,'尚未记录')));setting.id='settings-source';append(meta,identity,setting);root.appendChild(meta);
  if (!config.enabled) {const message=el('p','自动更新已关闭。保留数据时间为 '+str(m.generated_at,'尚未记录')+' 的内容，仍可筛选、展开能力与查看变更历史。','notice');message.id='disabled-message';root.appendChild(message);}
  list(m.warnings).forEach(warning => root.appendChild(el('p', warning, 'notice')));
  if (m.frozen_reason && m.frozen_reason !== '自动更新已关闭') root.appendChild(el('p', m.frozen_reason, 'notice'));
  const toolbar = el('nav', undefined, 'toolbar'); toolbar.setAttribute('aria-label', '地图视图与筛选'); root.appendChild(toolbar);
  const workspace = el('div', undefined, 'workspace'); const mainColumn = el('div', undefined, 'main-column'); const aside = el('aside', undefined, 'sidebar'); append(workspace, mainColumn, aside); root.appendChild(workspace);
  const views = {};
  for (const name of ['architecture','remaining','changes']) {views[name] = el('section', undefined, name === 'architecture' ? 'map-panel' : 'content-panel'); views[name].id = name + '-view'; mainColumn.appendChild(views[name]);}
  const buttons = {};
  const button = (label, handler, id) => {const b = el('button', label); b.type = 'button'; if (id) b.id = id; b.addEventListener('click', handler); toolbar.appendChild(b); return b;};
  const setView = name => {state.view = name; for (const key of Object.keys(views)) {views[key].hidden = key !== name; buttons[key].setAttribute('aria-pressed', String(key === name));} persist(); requestAnimationFrame(drawEdges);};
  buttons.architecture = button('架构地图', () => setView('architecture'));
  buttons.version = button('仅看本版本', () => {state.currentVersion = !state.currentVersion; buttons.version.setAttribute('aria-pressed', String(state.currentVersion)); persist(); renderMap();});
  buttons.version.setAttribute('aria-pressed', String(state.currentVersion));
  buttons.remaining = button('剩余差距', () => setView('remaining'));
  buttons.changes = button('查看变更', () => setView('changes'));
  button('定位当前任务', () => {
    setView('architecture');
    const cap = list(m.capabilities).find(c => c.current || list(c.task_ids).includes((m.current_work || {}).task_id));
    if (cap) {state.selected = str(cap.id); if (!inVersion(cap)) {state.currentVersion = false; buttons.version.setAttribute('aria-pressed','false');} persist(); renderMap(); requestAnimationFrame(() => {const node = capabilityNodes.get(state.selected); if (node) {node.scrollIntoView({block:'center'}); node.querySelector('button').focus({preventScroll:true});}});}
    else {work.scrollIntoView({block:'center'}); work.focus({preventScroll:true});}
  }, 'locate-current');
  const heading = el('div', undefined, 'panel-heading'); const headingCopy = el('div'); append(headingCopy, el('h2', '产品架构与交付能力'), el('p', '沿着接口看整体，展开能力看证据。'));
  const legend = el('div', undefined, 'legend'); [['working','当前工作'],['verified','已验证'],['','待推进']].forEach(([cls,title]) => {const item = el('span'); append(item, el('i', undefined, cls), document.createTextNode(title)); legend.appendChild(item);});
  append(heading, headingCopy, legend); views.architecture.appendChild(heading);
  if (list(m.goals).length) {const goals = el('div', undefined, 'goal-line'); goals.appendChild(el('strong','产品目标')); list(m.goals).forEach(goal => goals.appendChild(el('span',goal.title || goal.id))); views.architecture.appendChild(goals);}
  if (list(m.versions).length) {const roadmap=el('section',undefined,'roadmap');roadmap.appendChild(el('h3','版本路线图'));const versions=el('ol');versions.id='roadmap-versions';list(m.versions).forEach(version=>{const row=el('li');const name=el('strong',version.id);if(version.id===m.current_version){row.setAttribute('aria-current','step');name.appendChild(el('em','当前版本'));}append(row,name,el('span',version.title || version.description || '版本目标待记录'));versions.appendChild(row);});roadmap.appendChild(versions);views.architecture.appendChild(roadmap);}
  const canvas = el('div', undefined, 'map-canvas'); const grid = el('div', undefined, 'map-grid');
  const svgNS = 'http://www.w3.org/2000/svg'; const svgEl = tag => document.createElementNS(svgNS, tag);
  const connectors = svgEl('svg'); connectors.id = 'connectors'; connectors.setAttribute('aria-hidden','true'); append(canvas, connectors, grid); views.architecture.appendChild(canvas);
  const edgeList = el('ul', undefined, 'edge-list'); edgeList.setAttribute('aria-label','组件接口与依赖'); views.architecture.appendChild(edgeList);
  const componentNodes = new Map(); const capabilityNodes = new Map();
  const inVersion = item => !state.currentVersion || !m.current_version || list(item.version_ids).includes(m.current_version);
  const sourceList = (parent, sources) => {list(sources).forEach(source => {const item = el('div', undefined, 'source'); item.dataset.status=str(source.status); append(item, el('span', source.path || '未记录路径'), el('small', '证据状态：' + (source.status === 'current' ? '文件已核对' : status(source.status)))); if (source.sha256) item.appendChild(el('small', 'SHA-256：' + str(source.sha256))); if(source.included === false)item.appendChild(el('small','附件未嵌入此 HTML'));if(source.error)item.appendChild(el('small',source.error,'source-error'));parent.appendChild(item);});};
  const scenarioTrace=(parent,cap)=>{
    const scenarios=list(cap.scenarios),obligations=list(cap.obligations);
    if(!scenarios.length&&!obligations.length)return;
    parent.appendChild(el('h4','场景与测试义务'));
    const shown=new Set();const pathNames={normal:'正常路径',happy:'正常路径',happy_path:'正常路径',main:'主路径',exception:'异常路径',error:'错误路径',failure:'失败路径',boundary:'边界路径'};
    const traceItems=(target,label,values)=>{if(list(values).length){target.appendChild(el('p',label,'trace-heading'));notes(target,list(values).map(value=>value&&typeof value==='object'?JSON.stringify(value):str(value)));}};
    const obligationRow=(obligation)=>{
      const row=el('div',undefined,'obligation-trace');row.dataset.obligation=str(obligation.obligation_id);row.dataset.status=str(obligation.status);
      append(row,el('strong','测试：'+str(obligation.test_id,'尚未关联具体测试')),el('small','测试义务：'+str(obligation.obligation_id,'尚未登记标识')));
      const label=obligation.status==='verified'?'已验证':obligation.status==='missing'?'测试义务未被任务覆盖':'待验证';
      row.appendChild(el('span',label,'status '+knownStatus(obligation.status)));
      if(obligation.status==='missing')row.appendChild(el('p','需要将该义务关联到当前交付任务，再执行对应测试。','trace-error'));
      if(obligation.user_story)row.appendChild(el('p','测试故事：'+str(obligation.user_story)));
      if(obligation.journey)row.appendChild(el('p','测试旅程：'+str(obligation.journey)));
      traceItems(row,'语义断言',obligation.semantic_assertions);traceItems(row,'覆盖项',obligation.coverage_items);
      const taskIds=list(m.tasks).filter(task=>list(task.obligation_ids).includes(obligation.obligation_id)).map(task=>task.task_id);if(taskIds.length)row.appendChild(el('p','关联任务：'+taskIds.join('、')));
      return row;
    };
    scenarios.forEach(scenario=>{
      const section=el('section',undefined,'scenario-trace');section.dataset.scenario=str(scenario.scenario_id);
      append(section,el('strong','场景：'+str(scenario.scenario_id,'尚未登记标识')),el('p','角色：'+str(scenario.role,'尚未记录')),el('p','用户故事：'+str(scenario.user_story,'尚未记录')),el('p','用户旅程：'+str(scenario.journey,'尚未记录')));
      if(scenario.path_type)section.appendChild(el('p','路径：'+str(pathNames[scenario.path_type],scenario.path_type)));
      const related=obligations.filter(obligation=>obligation.scenario_id===scenario.scenario_id);
      related.forEach(obligation=>{shown.add(obligation);section.appendChild(obligationRow(obligation));});
      if(!related.length)section.appendChild(el('p','场景缺少测试义务：尚未登记可以验证此场景的测试。','trace-error'));
      parent.appendChild(section);
    });
    obligations.filter(obligation=>!shown.has(obligation)).forEach(obligation=>{const section=el('section',undefined,'scenario-trace');section.dataset.scenario=str(obligation.scenario_id);section.appendChild(el('strong','关联场景：'+str(obligation.scenario_id,'尚未关联')));section.appendChild(el('p','场景详情尚未记录，以下保留已登记的测试义务。'));section.appendChild(obligationRow(obligation));parent.appendChild(section);});
  };
  const capability = cap => {
    const node = el('div', undefined, 'capability'); node.dataset.capability = str(cap.id); capabilityNodes.set(str(cap.id), node);
    const b = el('button', undefined, 'capability-button'); b.type = 'button'; b.setAttribute('aria-expanded', String(state.selected === str(cap.id)));
    append(b, el('span', cap.title || cap.id || '待命名能力', 'cap-name'), badge(cap.status)); node.appendChild(b);
    b.addEventListener('click', () => {state.selected = state.selected === str(cap.id) ? '' : str(cap.id); persist(); renderMap(); const updated = capabilityNodes.get(str(cap.id)); if (updated) updated.querySelector('button').focus({preventScroll:true});});
    if (state.selected !== str(cap.id)) return node;
    const detail = el('div', undefined, 'capability-detail'); node.appendChild(detail); detail.appendChild(el('p', cap.description || '能力说明尚未记录。'));
    const milestones = el('ul', undefined, 'milestones');
    [['produced','产出'],['integrated','集成'],['verified','验证'],['reviewed','评审'],['delivered','交付']].forEach(([key,label]) => {const complete = (cap.milestones || {})[key] === true; const item = el('li', (complete ? '✓ ' : '○ ') + label); item.dataset.milestone = key; item.dataset.complete = String(complete); milestones.appendChild(item);}); detail.appendChild(milestones);
    const goals = list(m.goals).filter(goal => list(cap.goal_ids).includes(goal.id)); if (goals.length) {detail.appendChild(el('h4','服务目标')); notes(detail,goals.map(goal => goal.title || goal.id));}
    if (list(cap.gaps).length) {detail.appendChild(el('h4','尚缺什么')); notes(detail,cap.gaps);}
    const tasks = list(m.tasks).filter(task => list(cap.task_ids).includes(task.task_id));
    if (tasks.length) {detail.appendChild(el('h4','关联任务')); tasks.forEach(task => {const row = el('div', undefined, 'node-task'); append(row,el('strong',task.title || task.task_id),el('p','状态：' + status(task.status)),el('p','验证：' + str(task.verification,'尚未记录'))); if (task.owner) row.appendChild(el('p','负责：' + task.owner)); list(task.work_packages).forEach(pkg => row.appendChild(el('p','工作包 ' + str(pkg.id) + '：' + status(pkg.status) + ' · ' + str(pkg.agent_id,'待分配')))); sourceList(row,task.evidence); detail.appendChild(row);});}
    scenarioTrace(detail,cap);
    detail.appendChild(el('h4','来源与证据')); if (list(cap.sources).length) sourceList(detail,cap.sources); else detail.appendChild(el('p','尚未记录可追溯的来源。'));
    return node;
  };
  function renderMap() {
    grid.replaceChildren(); componentNodes.clear(); capabilityNodes.clear(); edgeList.replaceChildren();
    const caps = list(m.capabilities).filter(inVersion);
    list(m.components).forEach(component => {
      const owned = caps.filter(cap => list(component.capability_ids).includes(cap.id) || list(cap.component_ids).includes(component.id));
      if (!inVersion(component) && !owned.length) return;
      const node = el('article', undefined, 'component' + (component.current || owned.some(cap => cap.current) ? ' current' : '')); node.dataset.component = str(component.id); componentNodes.set(str(component.id),node);
      const h = el('div', undefined, 'component-header'); append(h,el('span',component.current || owned.some(cap => cap.current) ? '当前工作所在组件' : '产品组件','component-label'),el('h3',component.title || component.id || '待命名组件'),el('p',component.description || '组件说明尚未记录。')); node.appendChild(h);
      owned.forEach(cap => node.appendChild(capability(cap))); if (!owned.length) node.appendChild(el('p','尚未关联本视图内的能力。','empty')); grid.appendChild(node);
    });
    const loose = caps.filter(cap => !capabilityNodes.has(str(cap.id))); if (loose.length) {const group=el('article',undefined,'component');group.appendChild(el('h3','待关联组件的能力'));loose.forEach(cap=>group.appendChild(capability(cap)));grid.appendChild(group);}
    if (!grid.children.length) grid.appendChild(el('p',state.currentVersion ? '当前版本尚未关联组件。可关闭版本筛选查看整体。' : '架构尚未记录。确认组件与能力后，这里将显示交付地图。','empty'));
    list(m.edges).filter(edge => componentNodes.has(str(edge.from)) && componentNodes.has(str(edge.to))).forEach(edge => {const from = list(m.components).find(c=>c.id===edge.from); const to=list(m.components).find(c=>c.id===edge.to);edgeList.appendChild(el('li',str(from && from.title,edge.from)+' → '+str(to && to.title,edge.to)+'：'+(edge.kind==='dependency'?'依赖 · ':'接口 · ')+str(edge.label,'未命名关系')));});
    edgeList.hidden = !edgeList.children.length; requestAnimationFrame(drawEdges);
  }
  function drawEdges() {
    if (views.architecture.hidden) return; connectors.replaceChildren();
    const defs=svgEl('defs'),marker=svgEl('marker'),arrow=svgEl('path'); marker.id='map-arrow';marker.setAttribute('viewBox','0 0 10 10');marker.setAttribute('refX','9');marker.setAttribute('refY','5');marker.setAttribute('markerWidth','5');marker.setAttribute('markerHeight','5');marker.setAttribute('orient','auto-start-reverse');arrow.setAttribute('d','M 0 0 L 10 5 L 0 10 z');arrow.setAttribute('fill','#255d94');append(marker,arrow);append(defs,marker);connectors.appendChild(defs);
    const box=canvas.getBoundingClientRect();connectors.setAttribute('viewBox','0 0 '+box.width+' '+box.height);
    list(m.edges).forEach(edge=>{
      const from=componentNodes.get(str(edge.from)),to=componentNodes.get(str(edge.to));if(!from||!to||from===to)return;
      const a=from.getBoundingClientRect(),b=to.getBoundingClientRect();let x1,y1,x2,y2,path,labelX,labelY;
      if(Math.abs(a.top-b.top)<20){const forward=a.left<b.left;x1=(forward?a.right:a.left)-box.left;x2=(forward?b.left:b.right)-box.left;y1=a.top-box.top+40;y2=b.top-box.top+40;const mid=(x1+x2)/2;path=`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`;labelX=mid;labelY=(y1+y2)/2-12;}
      else{const forward=a.top<b.top;x1=a.left-box.left+a.width/2;x2=b.left-box.left+b.width/2;y1=(forward?a.bottom:a.top)-box.top;y2=(forward?b.top:b.bottom)-box.top;const mid=(y1+y2)/2;path=`M${x1},${y1} C${x1},${mid} ${x2},${mid} ${x2},${y2}`;labelX=(x1+x2)/2;labelY=mid-10;}
      const line=svgEl('path');line.setAttribute('d',path);line.setAttribute('class','edge '+(edge.kind==='dependency'?'dependency':'interface'));line.setAttribute('marker-end','url(#map-arrow)');connectors.appendChild(line);
      const text=svgEl('text');text.setAttribute('x',labelX);text.setAttribute('text-anchor','middle');
      const relation=edge.kind==='dependency'?'依赖':'接口';const label=str(edge.label,'未命名');let lines=[relation+'：'+label];
      if(Math.abs(a.top-b.top)<20){const limit=Math.max(2,Math.floor((Math.abs(x2-x1)-14)/11));const letters=Array.from(label);lines=[relation];for(let offset=0;offset<letters.length;offset+=limit)lines.push(letters.slice(offset,offset+limit).join(''));}
      text.setAttribute('y',labelY-(lines.length-1)*14);lines.forEach((part,index)=>{const span=svgEl('tspan');span.setAttribute('x',labelX);span.setAttribute('dy',index?'14':'0');span.textContent=part;text.appendChild(span);});connectors.appendChild(text);
    });
  }
  const current = m.current_work || {}; const work = el('section',undefined,'current-work'); work.id='current-work'; work.tabIndex=-1;
  append(work,el('div','正在推进','label'),el('h2',current.title || '当前任务尚未明确'),el('p',current.description || '明确下一项任务后，这里将说明它对交付的作用。'));
  const workFields=el('dl');field(workFields,'为什么现在做',current.why);field(workFields,'完成后解锁',list(current.unlocks).join('；'));field(workFields,'负责',current.owner);field(workFields,'当前阻塞',list(current.blockers).length?list(current.blockers).join('；'):'未记录阻塞');
  list(current.work_packages).forEach(pkg=>field(workFields,'工作包 '+str(pkg.id),list(pkg.role_ids).join('、')+' / '+status(pkg.status)+(pkg.agent_id?' / '+pkg.agent_id:'')));work.appendChild(workFields);
  const next=el('div',undefined,'next-action');append(next,el('span','下一步'),el('p',current.next_action || '明确当前任务和验收方式'));work.appendChild(next);append(aside,work,el('p','阶段推进与能力完成分别记录；完成产出不代表已验证或已交付。','aside-note'));
  const stagesPanel=el('section',undefined,'stages-panel');append(stagesPanel,el('h2','六阶段交付路径'),el('p','每一步保留自己的完成条件。'));
  const stages=el('ol');stages.id='stages';
  const stageItems=list(m.stages).length?list(m.stages):['需求','设计','实现','验证','评审','交付'].map(title=>({title,status:'unknown'}));
  stageItems.forEach((stage,index)=>{const item=el('li');item.dataset.status=knownStatus(stage.status);append(item,el('strong',(index+1)+'. '+str(stage.title,stage.id)),el('small',status(stage.status)));stages.appendChild(item);});stagesPanel.appendChild(stages);mainColumn.appendChild(stagesPanel);
  if(list(m.success_criteria).length){const criteria=el('details',undefined,'requirements');criteria.appendChild(el('summary','交付成功标准'));notes(criteria,m.success_criteria);mainColumn.appendChild(criteria);}
  append(views.remaining,el('h2','距离交付还差什么'),el('p','差距对应下一步动作；证据不足的能力仍然保留在这里。'));
  if(!list(m.remaining).length) views.remaining.appendChild(el('p','尚无已记录的剩余差距。是否完成交付仍以验证、评审与最终确认为准。','empty'));
  list(m.remaining).forEach(gap=>{const row=el('article',undefined,'list-item');append(row,el('h3',gap.title || gap.id || '待明确差距'),el('p',gap.reason || '原因尚未记录'),el('p','下一步：'+str(gap.next_action,'明确解决动作'),'action'));views.remaining.appendChild(row);});
  append(views.changes,el('h2','变更与交付历史'),el('p','查看范围为何改变，以及每次记录对交付的影响。'));
  const baseline=m.baseline||{};views.changes.appendChild(el('div','初始基线：'+str(baseline.initial_revision,'未记录')+'　已确认基线：'+str(baseline.approved_revision,'未记录'),'baseline'));
  if(baseline.history_complete===false)views.changes.appendChild(el('p','历史记录不完整，以下仅显示已记录的变更。','notice'));
  if(!list(m.changes).length)views.changes.appendChild(el('p','尚未记录变更。','empty'));
  const detailLabels={id:'标识',title:'名称',description:'说明',goal_ids:'关联目标',component_ids:'关联组件',capability_ids:'关联能力',version_ids:'所属版本',task_ids:'关联任务',task_id:'任务',sources:'依据文件',status:'状态',from:'起点',to:'终点',kind:'关系类型',label:'关系说明'};
  const planDetail=(value,cls,title)=>{const column=el('div',undefined,cls);column.appendChild(el('h4',title));if(value===null||value===undefined){column.appendChild(el('p','无此项'));return column;}if(typeof value!=='object'){column.appendChild(el('p',value));return column;}const fields=el('dl');Object.entries(value).forEach(([key,val])=>{fields.appendChild(el('dt',detailLabels[key] || key));const dd=el('dd');if(Array.isArray(val)){if(!val.length)dd.textContent='无';else notes(dd,val.map(item=>typeof item==='object'?JSON.stringify(item,null,2):str(item)));}else if(val&&typeof val==='object')dd.appendChild(el('pre',JSON.stringify(val,null,2)));else dd.textContent=str(val,'无');fields.appendChild(dd);});column.appendChild(fields);return column;};
  list(m.changes).forEach(change=>{
    const row=el('article',undefined,'list-item');append(row,el('small',change.kind || '交付变更'),el('h3',change.title || change.id),el('p','原因：'+str(change.reason,'尚未记录')),el('p','影响：'+str(change.impact,'尚未记录')),el('p','负责：'+str(change.owner,'尚未记录')),el('p','下一步：'+str(change.next_action,'尚未记录'),'action'));
    if(change.comparison)row.appendChild(el('p',({initial:'相对初始基线',approved:'相对最近批准基线'})[change.comparison] || change.comparison,'comparison-label'));
    if(list(change.affected_ids).length)row.appendChild(el('p','涉及：'+change.affected_ids.join('、')));
    if(Object.hasOwn(change,'before')||Object.hasOwn(change,'after')){const summary=el('div',undefined,'change-summary');for(const [key,label] of [['before','原计划'],['after','当前计划']]){const cell=el('div');append(cell,el('small',label),el('strong',str(change[key],'无此项')));summary.appendChild(cell);}row.appendChild(summary);}
    if(Object.hasOwn(change,'before_detail')||Object.hasOwn(change,'after_detail')){const details=el('details',undefined,'change-detail');details.appendChild(el('summary','查看变更前后详情'));const columns=el('div',undefined,'change-columns');append(columns,planDetail(change.before_detail,'change-before','原计划详情'),planDetail(change.after_detail,'change-after','当前计划详情'));details.appendChild(columns);row.appendChild(details);}
    sourceList(row,change.sources);views.changes.appendChild(row);
  });
  views.changes.appendChild(el('h3','历史记录','history-title'));if(!list(m.history).length)views.changes.appendChild(el('p','尚无历史快照。','empty'));
  list(m.history).forEach(entry=>{const row=el('article',undefined,'list-item');append(row,el('small','修订 '+str(entry.revision,'未知')+'　'+str(entry.generated_at)),el('h4',entry.summary || '交付记录已更新'),el('p','基线：'+status(entry.baseline_status)));if(list(entry.sources).length){const sources=el('details');sources.appendChild(el('summary','查看该修订的来源'));sourceList(sources,entry.sources);row.appendChild(sources);}views.changes.appendChild(row);});
  if(list(m.reviews).length||list(m.confirmations).length){views.changes.appendChild(el('h3','评审与确认','history-title'));list(m.reviews).forEach(review=>views.changes.appendChild(el('p',str(review.gate)+'：'+status(review.status))));list(m.confirmations).forEach(confirmation=>views.changes.appendChild(el('p',str(confirmation.target)+'：'+status(confirmation.status))));}
  const footer=el('footer');append(footer,el('span','交付 '+str(m.delivery_id,'尚未分配')),el('span','内容修订 '+str(m.source_revision,'尚未记录').slice(0,16)),el('span',!config.enabled?'只读冻结地图 · 自动更新已关闭':config.live?'只读视图 · 随交付记录更新':'只读离线快照 · 筛选与展开仍可使用'));root.appendChild(footer);
  renderMap();setView(state.view);const restoreScroll=state.scroll;requestAnimationFrame(()=>requestAnimationFrame(()=>{window.scrollTo(0,restoreScroll);window.addEventListener('scroll',saveScroll,{passive:true});}));
  window.addEventListener('pagehide',saveScroll);window.addEventListener('resize',()=>requestAnimationFrame(drawEdges));
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(()=>requestAnimationFrame(drawEdges)).observe(grid);
  if(config.live)window.setInterval(()=>{saveScroll();const url=new URL(window.location.href);url.searchParams.set('_map_refresh',String(Date.now()));window.location.replace(url.href);},5000);
})();
"""
