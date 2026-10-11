"""Presentation identities kept outside frozen role cards and task hashes."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Callable

NAMING_VERSION = 'agent-naming-v1'
PRODUCER_NAMES = {
    'production.product_requirements': ('产品专家', '需求与验收', 'product_requirements'),
    'production.architecture_contract': ('架构专家', '契约与版本规划', 'architecture_contracts'),
    'production.scenario_interaction': ('交互专家', '场景与恢复路径', 'scenario_interaction'),
    'production.ui_prototype': ('原型专家', '界面与可访问性', 'ui_prototype'),
    'production.test_design': ('测试专家', '测试设计与覆盖', 'test_design'),
    'production.frontend': ('前端专家', '界面实现', 'frontend_implementation'),
    'production.backend': ('后端专家', '接口与业务实现', 'backend_implementation'),
    'production.test_automation': ('测试专家', '自动化验证', 'test_automation'),
    'production.integration': ('集成专家', '整合与回归', 'integration'),
    'production.delivery_evidence': ('交付专家', '证据与交付准备', 'delivery_evidence'),
    'production.domain_research': ('领域专家', '调研与事实核验', 'domain_research'),
    'production.data_migration': ('数据专家', '迁移与兼容', 'data_migration'),
    'production.security_engineering': ('安全专家', '权限与安全实现', 'security_engineering'),
    'production.performance_reliability': ('可靠性专家', '性能与故障恢复', 'performance_reliability'),
    'production.build_deployment': ('发布专家', '构建与部署准备', 'build_deployment'),
}
REVIEW_SEAT_NAMES = {
    'intent_boundary': ('评审专家', '产品意图与边界'),
    'journey_interaction': ('评审专家', '用户旅程与交互'),
    'test_strategy': ('测试专家', '测试策略'),
    'assertion_quality': ('测试专家', '断言与假通过'),
    'coverage_boundary': ('评审专家', '覆盖追溯与边界'),
    'implementation_evidence': ('评审专家', '测试实现证据'),
    'ui_conformance': ('评审专家', 'UI 一致性'),
}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]


def _spawn_token(value: str) -> str:
    token = re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')
    return token or 'feature_' + _digest(value)


def _feature(feature_slug: str) -> tuple[str, str]:
    if not isinstance(feature_slug, str) or not feature_slug.strip():
        raise ValueError('feature_slug is required for agent naming')
    version = re.match(r'^(v\d+(?:\.\d+)+)(?=$|[-_])', feature_slug, re.I)
    if version:
        label = version[1].lower()
        return label, label.replace('.', '')
    return feature_slug, _spawn_token(feature_slug)


def _bounded(name: str) -> str:
    return name if len(name) <= 64 else name[:55].rstrip('_') + '_' + _digest(name)


def producer_identity(task: dict[str, Any]) -> dict[str, Any]:
    roles = task.get('role_ids')
    if not isinstance(roles, list) or not roles or any(r not in PRODUCER_NAMES for r in roles):
        raise ValueError('known production role_ids are required for agent naming')
    label, version = _feature(task.get('feature_slug'))
    ordered = [r for r in PRODUCER_NAMES if r in roles]
    cards = [PRODUCER_NAMES[r] for r in ordered]
    expert = cards[0][0] if len(cards) == 1 else '生产专家'
    return {
        'naming_version': NAMING_VERSION, 'member_kind': 'producer',
        'agent_display_name': expert + '｜' + '＋'.join(c[1] for c in cards) + '｜' + label,
        'agent_spawn_name': _bounded('_'.join(c[2] for c in cards) + '_' + version),
        'role_ids': list(roles), 'feature_slug': task['feature_slug'],
    }


def producer_identities(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    identities = {t['work_package_id']: producer_identity(t) for t in tasks}
    counts: dict[str, int] = {}
    for identity in identities.values():
        counts[identity['agent_spawn_name']] = counts.get(identity['agent_spawn_name'], 0) + 1
    for key, identity in identities.items():
        if counts[identity['agent_spawn_name']] > 1:
            identity['agent_spawn_name'] = _bounded(identity['agent_spawn_name'] + '_' + _digest(key))
            identity['agent_display_name'] += '｜' + key
    return identities


def producer_dispatch_identity(identity: dict, run_id: str, work_package_id: str, attempt: int) -> dict:
    """Bind a host alias to one prepared run/package/attempt, outside task hashes."""
    if not run_id or not work_package_id or type(attempt) is not int or attempt < 1:
        raise ValueError('run, work package and positive attempt are required')
    base = identity.get('agent_spawn_base') or identity['agent_spawn_name']
    return {**identity, 'agent_spawn_base': base, 'agent_spawn_run_id': run_id,
            'agent_spawn_name': _bounded(base + '_' + _digest([run_id, work_package_id]) + '_a' + str(attempt))}


def review_identity(feature_slug: str, seat: dict[str, Any]) -> dict[str, Any]:
    seat_id = seat.get('seat_id')
    if seat_id not in REVIEW_SEAT_NAMES:
        raise ValueError('known review seat_id is required for agent naming')
    label, version = _feature(feature_slug)
    expert, duty = REVIEW_SEAT_NAMES[seat_id]
    return {
        'naming_version': NAMING_VERSION, 'member_kind': 'reviewer',
        'agent_display_name': expert + '｜' + duty + '｜' + label,
        'agent_spawn_name': _bounded('review_' + seat_id + '_' + version),
        'seat_id': seat_id, 'seat_display_name': seat['display_name'],
        'role_ids': list(seat['role_ids']), 'feature_slug': feature_slug,
    }


def _header(identity: dict, tasks: list[dict], *, package: str, allowed: Any) -> str:
    return '\n'.join([
        '【' + identity['agent_display_name'] + '】',
        '语义任务名：' + identity['agent_spawn_name'],
        '角色使命：' + '；'.join(t['mission'] for t in tasks),
        '必查项：' + '、'.join(check for t in tasks for check in t['must_check']),
        '允许写入：' + str(allowed),
        '禁止事项：' + '、'.join(dict.fromkeys(rule for t in tasks for rule in t['must_not_do'])),
        '当前工作包：' + package,
    ])


def producer_dispatch_message(task: dict, identity: dict, *, staging_root: str | None = None) -> str:
    text = _header(identity, task['role_cards'], package=task['work_package_id'], allowed=task['allowed_write_paths'])
    text += '\n暂存目录：' + (staging_root or '等待协调员登记 dispatched 并提供 staging_root；此前禁止写入。')
    return text + '\n完整绑定任务和角色卡：\n' + json.dumps(task, ensure_ascii=False, indent=2)


def review_dispatches(feature_slug: str, briefs: list[dict]) -> list[dict]:
    result = []
    for brief in briefs:
        identity = review_identity(feature_slug, brief)
        identity['agent_spawn_name'] = _bounded(identity['agent_spawn_name'] + '_' + _digest(brief['seat_task_hash']))
        message = _header(identity, brief['role_tasks'], package=brief['seat_id'], allowed='只返回本席逐角色评审结果')
        message += '\n独立评审；不得读取其他席结果或写入 canonical state。\n完整本席 brief：\n'
        result.append({**identity, 'brief': copy.deepcopy(brief),
                       'dispatch_message': message + json.dumps(brief, ensure_ascii=False, indent=2)})
    return result


def update_host_title(identity: dict, native_agent_id: str, *, rpc: Callable | None = None, host: str = 'codex') -> dict:
    """Call an exposed host title API; absence never masquerades as a rename."""
    if rpc is None:
        return {**identity, 'status': 'semantic_fallback', 'native_agent_id': native_agent_id}
    if not isinstance(native_agent_id, str) or not native_agent_id.strip() or '/' in native_agent_id or '\\' in native_agent_id:
        raise ValueError('actual native host Agent ID is required, not a collaboration path')
    if host not in {'codex', 'paseo'}:
        raise ValueError('unsupported host naming API')
    try:
        if host == 'codex':
            response = rpc('thread/name/set', {'threadId': native_agent_id, 'name': identity['agent_display_name']})
        else:
            response = rpc('update_agent', {'agentId': native_agent_id, 'name': identity['agent_display_name']})
        if isinstance(response, dict) and (response.get('error') or response.get('isError')):
            raise RuntimeError(str(response.get('error') or response))
    except Exception as error:
        return {**identity, 'status': 'semantic_fallback', 'native_agent_id': native_agent_id, 'error': str(error)}
    return {**identity, 'status': 'renamed', 'native_agent_id': native_agent_id}
