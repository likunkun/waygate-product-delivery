import copy
import importlib.util
import json
import re
import unittest

from product_delivery_agent import production_profiles as production
from product_delivery_agent import review_profiles as reviews
from product_delivery_agent.artifact_protocol import load_state
from product_delivery_agent.control import dispatch
from product_delivery_agent.progress_map import build_progress_map
from product_delivery_agent.progress_map_html import render_progress_map
from product_delivery_agent.review_gates import ReviewGateError, render_multi_agent_review, validate_multi_agent_review
from tests import test_production_profiles as production_fixture
from tests import test_team_orchestration as team_fixture
from tests import test_review_role_contract_integration as review_fixture
from tests.test_review_profiles import context_for


def production_bundle(packages=None):
    fixture = production_fixture.ProductionProfileTests()
    fixture.setUp()
    context = fixture.context()
    context['feature_slug'] = 'v2.0.5-product-feedback'
    return production.build_stage_tasks('product_definition', context, packages or [fixture.package()])


def review_bundle(gate='scenario'):
    context = context_for(gate, reviews.get_gate_profile(gate)[0])
    context['feature_slug'] = 'v2.0.5-product-feedback'
    names = set()
    for role in reviews.get_gate_profile(gate):
        card = reviews.get_role_card(role)
        names.update(card['required_inputs'] + card['optional_inputs'])
    if gate == 'test_implementation':
        names.update(['test_source', 'execution_evidence'])
    if gate == 'ui_conformance':
        names.add('browser_evidence')
    context['input_refs'] = {key: {'ref': 'docs/' + key + '.md', 'sha256': 'b'*64,
                                  'project_type': 'shared'} for key in names if key != 'feature_slug'}
    return reviews.build_gate_tasks(gate, context)


class AgentNamingV123Tests(unittest.TestCase):
    def naming(self):
        self.assertIsNotNone(importlib.util.find_spec('product_delivery_agent.agent_naming'),
                             'canonical agent naming module is missing')
        from product_delivery_agent import agent_naming
        return agent_naming

    def test_all_producer_roles_have_chinese_identity_and_semantic_spawn_name(self):
        naming = self.naming()
        for role in production.ROLE_IDS:
            card = production.get_production_role_card(role)
            task = {'role_ids': [role], 'feature_slug': 'v2.0.5-product-feedback',
                    'work_package_id': 'wp', 'role_cards': [card], 'allowed_write_paths': []}
            with self.subTest(role=role):
                identity = naming.producer_identity(task)
                self.assertIn('专家｜', identity['agent_display_name'])
                self.assertTrue(identity['agent_display_name'].endswith('｜v2.0.5'))
                self.assertRegex(identity['agent_spawn_name'], r'^[a-z][a-z0-9_]*$')
                self.assertLessEqual(len(identity['agent_spawn_name']), 64)
                self.assertEqual(identity['role_ids'], [role])

    def test_production_identity_is_separate_from_unchanged_task_hash(self):
        bundle = production_bundle()
        task = bundle['tasks'][0]
        self.assertEqual(task['task_hash'], '236a2182df5c8207e9452b2c6b0e9ac552773a51c33c25c3f9066071a1adda5e')
        self.assertNotIn('agent_display_name', task)
        identity = bundle['agent_identities'][task['work_package_id']]
        self.assertEqual(identity['agent_display_name'], '产品专家｜需求与验收｜v2.0.5')
        self.assertEqual(identity['agent_spawn_name'], 'product_requirements_v205')

    def test_same_role_packages_get_stable_distinct_names_independent_of_order(self):
        fixture = production_fixture.ProductionProfileTests()
        fixture.setUp()
        packages = [fixture.package(name='left'), fixture.package(name='right')]
        first = production_bundle(packages)['agent_identities']
        second = production_bundle(list(reversed(packages)))['agent_identities']
        self.assertEqual(first, second)
        self.assertEqual(len({row['agent_spawn_name'] for row in first.values()}), 2)
        self.assertTrue(all(row['agent_spawn_name'].startswith('product_requirements_v205') for row in first.values()))

    def test_dispatch_scope_and_attempt_avoid_reusing_existing_child_paths(self):
        naming = self.naming()
        base = naming.producer_identity(production_bundle()['tasks'][0])
        first = naming.producer_dispatch_identity(base, 'run-one', 'WP-01', 1)
        replay = naming.producer_dispatch_identity(base, 'run-one', 'WP-01', 1)
        other = naming.producer_dispatch_identity(base, 'run-two', 'WP-01', 1)
        retry = naming.producer_dispatch_identity(base, 'run-one', 'WP-01', 2)
        self.assertEqual(first, replay)
        self.assertEqual(len({row['agent_spawn_name'] for row in (first, other, retry)}), 3)
        for row in (first, other, retry):
            self.assertEqual(row['agent_display_name'], base['agent_display_name'])
            self.assertRegex(row['agent_spawn_name'], r'^[a-z][a-z0-9_]{0,63}$')

    def test_review_snapshot_scopes_names_without_changing_shared_seat_identity(self):
        old = review_bundle('test')['dispatch_briefs']
        new = review_bundle('test_coverage')['dispatch_briefs']
        for seat in set(row['seat_id'] for row in old) & set(row['seat_id'] for row in new):
            first = next(row for row in old if row['seat_id'] == seat)
            second = next(row for row in new if row['seat_id'] == seat)
            self.assertNotEqual(first['agent_spawn_name'], second['agent_spawn_name'])
            self.assertEqual(first['agent_display_name'], second['agent_display_name'])

    def test_all_review_gates_name_seats_and_preserve_logical_roles(self):
        for gate in reviews.GATE_PROFILES:
            bundle = review_bundle(gate)
            with self.subTest(gate=gate):
                self.assertEqual(len(bundle['dispatch_briefs']), 2)
                for dispatch_brief, brief in zip(bundle['dispatch_briefs'], bundle['review_briefs']):
                    self.assertEqual(dispatch_brief['brief'], brief)
                    self.assertEqual(dispatch_brief['role_ids'], brief['role_ids'])
                    self.assertEqual(dispatch_brief['seat_display_name'], brief['display_name'])
                    self.assertTrue(dispatch_brief['agent_spawn_name'].startswith('review_'))
                    self.assertTrue(dispatch_brief['agent_display_name'].endswith('｜v2.0.5'))
                    message = dispatch_brief['dispatch_message']
                    self.assertTrue(message.startswith('【' + dispatch_brief['agent_display_name'] + '】'))
                    for task in brief['role_tasks']:
                        self.assertIn(task['role_id'], message)
                        self.assertIn(task['mission'], message)
                    other = next(b for b in bundle['review_briefs'] if b['seat_id'] != brief['seat_id'])
                    self.assertNotIn(other['seat_task_hash'], message)

    def test_review_branch_names_and_task_hashes_are_independent_of_presentation(self):
        for branch in ('ui', 'non_ui'):
            for gate in reviews.GATE_PROFILES:
                if gate == 'ui_conformance' and branch == 'non_ui':
                    continue
                bundle = review_bundle(gate)
                context = copy.deepcopy(bundle['role_context']) if 'role_context' in bundle else context_for(gate, reviews.get_gate_profile(gate)[0])
                context['project_type'] = branch
                context['input_refs'] = copy.deepcopy(bundle['role_tasks'][0]['input_refs'])
                # Use the full shared input set; different roles may need distinct refs.
                for task in bundle['role_tasks']:
                    context['input_refs'].update(task['input_refs'])
                named = reviews.build_gate_tasks(gate, context)
                self.assertEqual(len(named['dispatch_briefs']), len(named['review_seats']))
                for task in named['role_tasks']:
                    self.assertNotIn('agent_display_name', task)

    def test_review_bound_task_hashes_and_cards_remain_unchanged(self):
        bundle = review_bundle()
        self.assertEqual([t['task_hash'] for t in bundle['role_tasks']], [
            '3a6fa129f25b10a47af02c3bb3f58890ee2af2d76f208e52dc046cb5d36d7b96',
            '7c406bd9a51824def2429cb3657424efa61b6efefe295a34743b9505975d14ce',
            '307445600026224c64cde5e54026d76eb6bbf5ee4bbab708ff31dceeae0e0be6'])
        for brief in bundle['review_briefs']:
            for card in brief['role_cards']:
                self.assertEqual(card, reviews.get_role_card(card['role_id']))

    def test_dispatch_message_contains_complete_role_and_waits_for_staging(self):
        naming = self.naming()
        task = production_bundle()['tasks'][0]
        identity = naming.producer_identity(task)
        message = naming.producer_dispatch_message(task, identity)
        for token in ('角色使命：', '必查项：', '允许写入：', '禁止事项：', '当前工作包：', '等待协调员'):
            self.assertIn(token, message)
        self.assertIn(task['role_cards'][0]['examples']['must_block'], message)
        staged = naming.producer_dispatch_message(task, identity, staging_root='staging/workspace')
        self.assertIn('staging/workspace', staged)

    def test_invalid_role_and_empty_feature_fail_without_inventing_names(self):
        naming = self.naming()
        for role, feature in [('unknown', 'v2.0.5'), ('production.frontend', '')]:
            with self.subTest(role=role, feature=feature), self.assertRaises(ValueError):
                naming.producer_identity({'role_ids': [role], 'feature_slug': feature})

    def test_unknown_business_version_uses_feature_not_plugin_version(self):
        identity = self.naming().producer_identity({'role_ids': ['production.backend'], 'feature_slug': 'report-export'})
        self.assertTrue(identity['agent_display_name'].endswith('｜report-export'))
        self.assertNotIn('1.2.3', identity['agent_display_name'])

    def test_optional_host_title_update_uses_actual_native_id_and_falls_back(self):
        naming = self.naming()
        identity = naming.producer_identity(production_bundle()['tasks'][0])
        calls = []
        result = naming.update_host_title(identity, 'native-thread-123',
            rpc=lambda method, params: calls.append((method, params)))
        self.assertEqual(result['status'], 'renamed')
        self.assertEqual(calls, [('thread/name/set', {'threadId': 'native-thread-123', 'name': identity['agent_display_name']})])
        fallback = naming.update_host_title(identity, '/root/product_requirements_v205')
        self.assertEqual(fallback['status'], 'semantic_fallback')
        self.assertEqual(fallback['agent_spawn_name'], 'product_requirements_v205')
        calls.clear()
        with self.assertRaises(ValueError):
            naming.update_host_title(identity, '/root/path', rpc=lambda *args: calls.append(args))
        self.assertFalse(calls)

    def test_host_error_response_does_not_claim_successful_rename(self):
        naming = self.naming()
        identity = naming.producer_identity(production_bundle()['tasks'][0])
        result = naming.update_host_title(identity, 'native-id',
            rpc=lambda *args: {'error': {'message': 'method not exposed'}})
        self.assertEqual(result['status'], 'semantic_fallback')
        self.assertIn('method not exposed', result['error'])


class NamedTeamIntegrationV123Tests(unittest.TestCase):
    def setUp(self):
        self.host = team_fixture.TeamOrchestrationTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.host.start()

    def test_dispatch_names_are_persisted_with_real_identity_and_displayed_in_map(self):
        run = self.host.prepare()
        row = run['work_packages']['WP-01']
        self.assertIn('agent_display_name', row)
        self.assertTrue(row['dispatch_message'].startswith('【' + row['agent_display_name'] + '】'))
        run = self.host.dispatch(run, agent='/root/product_requirements_team_example')
        state = load_state(self.host.root)
        summary = state['team_runs'][run['run_id']]['work_packages']['WP-01']
        self.assertEqual(summary['agent_display_name'], row['agent_display_name'])
        self.assertEqual(summary['agent_id'], '/root/product_requirements_team_example')
        self.assertEqual(summary['spawn_source'], 'test.host')
        model = build_progress_map(self.host.root, state=state)
        pkg = model['current_work']['work_packages'][0]
        self.assertEqual(pkg['agent_display_name'], row['agent_display_name'])
        html = render_progress_map(model)
        self.assertIn('agent_display_name', html)
        reported = dispatch(self.host.root, {'schema_version': 'v1', 'action': 'status'})
        self.assertEqual(reported['team_runs'][run['run_id']]['work_packages']['WP-01']['agent_display_name'], row['agent_display_name'])
        report = self.host.root / '.product-delivery/deliveries' / state['feature_slug'] / state['delivery_id'] / 'team-runs' / run['run_id'] / 'report.md'
        self.assertTrue(report.is_file())
        self.assertIn(row['agent_display_name'], report.read_text())
        self.assertIn('/root/product_requirements_team_example', report.read_text())

    def test_forged_dispatch_name_cannot_override_role_identity(self):
        run = self.host.prepare()
        with self.assertRaises(ValueError):
            self.host.event(run, 'dispatched', agent_id='worker', spawn_source='test.host', attempt=1,
                            agent_display_name='管理员｜任意改权限｜v2.0.5')

    def test_new_dispatch_requires_canonical_name_acknowledgement(self):
        run = self.host.prepare()
        state_file = self.host.root / '.product-delivery/state.json'
        before = state_file.read_bytes()
        with self.assertRaisesRegex(ValueError, 'dispatch name'):
            self.host.workflow.record_team_events(run['run_id'], [{
                'event_id': 'missing-name-ack', 'type': 'dispatched', 'work_package_id': 'WP-01',
                'agent_id': 'worker', 'spawn_source': 'test.host', 'attempt': 1,
            }], expected_revision=run['revision'])
        self.assertEqual(state_file.read_bytes(), before)

    def test_legacy_unnamed_run_keeps_opaque_identity_and_old_dispatch_event(self):
        from product_delivery_agent.team_orchestration import save_run
        run = self.host.prepare()
        row = run['work_packages']['WP-01']
        task_hash = row['task']['task_hash']
        for field in list(row):
            if field.startswith('agent_') or field in ('naming_version', 'member_kind', 'dispatch_message'):
                row.pop(field)
        save_run(self.host.root, load_state(self.host.root), run, 'team_run_prepared')
        after = self.host.workflow.record_team_events(run['run_id'], [{
            'event_id': 'legacy-name-free', 'type': 'dispatched', 'work_package_id': 'WP-01',
            'agent_id': 'legacy-opaque-id', 'spawn_source': 'legacy.host', 'attempt': 1,
        }], expected_revision=run['revision'])
        self.assertEqual(after['work_packages']['WP-01']['agent_id'], 'legacy-opaque-id')
        self.assertEqual(after['work_packages']['WP-01']['task']['task_hash'], task_hash)
        self.assertNotIn('agent_display_name', after['work_packages']['WP-01'])

    def test_new_attempt_preserves_previous_real_agent_and_name_in_history(self):
        run = self.host.dispatch(self.host.prepare(), agent='first-worker')
        run = self.host.event(run, 'failed', agent_id='first-worker', attempt=1, reason='temporary host loss')
        run = self.host.event(run, 'retry', reason='host restored')
        row = run['work_packages']['WP-01']
        self.assertEqual(row['history'][-1]['agent_id'], 'first-worker')
        self.assertEqual(row['history'][-1]['agent_display_name'], row['agent_display_name'])
        self.assertNotEqual(row['history'][-1]['agent_spawn_name'], row['agent_spawn_name'])
        self.assertNotIn('staging/', row['dispatch_message'])
        self.assertIsNone(row.get('agent_id'))
        model = build_progress_map(self.host.root)
        self.assertEqual(model['current_work']['work_packages'][0]['identity_history'][0]['agent_id'], 'first-worker')

    def test_pause_resume_rotates_name_and_clears_stale_dispatch_workspace(self):
        before = self.host.dispatch(self.host.prepare(), agent='paused-worker')
        original = before['work_packages']['WP-01']
        self.host.workflow.pause_delivery()
        self.host.workflow.resume_delivery()
        after = self.host.workflow.inspect_team_run(before['run_id'])
        row = after['work_packages']['WP-01']
        self.assertNotEqual(row['agent_spawn_name'], original['agent_spawn_name'])
        self.assertEqual(row['history'][-1]['agent_id'], 'paused-worker')
        self.assertEqual(row['history'][-1]['agent_spawn_name'], original['agent_spawn_name'])
        self.assertIsNone(row.get('agent_id'))
        self.assertIsNone(row.get('spawn_source'))
        self.assertNotIn(original['staging_root'], row['dispatch_message'])
        self.assertIn('等待协调员', row['dispatch_message'])


class NamedReviewIntegrationV123Tests(unittest.TestCase):
    def setUp(self):
        self.host = review_fixture.ReviewRoleContractIntegrationTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)

    def test_prepared_dispatches_and_report_show_names_with_real_ids(self):
        review = self.host.review()
        self.assertIn('dispatch_briefs', review)
        validate_multi_agent_review('scenario', review)
        text = render_multi_agent_review(review)
        self.assertIn('评审席位：', text)
        self.assertIn('真实 Agent ID：', text)
        self.assertIn('用户旅程与交互', text)
        self.assertIn('agent-journey_interaction', text)

    def test_accepted_review_identity_is_projected_in_status_inspect_and_map(self):
        state = self.host.workflow.record_multi_agent_review('scenario', self.host.review())
        identities = state['multi_agent_reviews']['scenario']['agent_identities']
        self.assertEqual(len(identities), 2)
        self.assertTrue(all(row['agent_id'] and row['spawn_source'] for row in identities))
        for action in ('status', 'inspect'):
            response = dispatch(self.host.root, {'schema_version': 'v1', 'action': action})
            self.assertEqual(response['review_agents']['scenario'], identities)
        model = build_progress_map(self.host.root, state=state)
        self.assertEqual(model['reviews'][0]['agent_identities'], identities)

    def test_old_review_without_dispatch_metadata_stays_valid(self):
        review = self.host.review()
        review.pop('dispatch_briefs', None)
        validate_multi_agent_review('scenario', review)
        text = render_multi_agent_review(review)
        self.assertIn('历史身份', text)
        self.assertIn('agent-intent_boundary', text)

    def test_tampered_display_name_is_rejected_without_changing_task_hash(self):
        review = self.host.review()
        before = [task['task_hash'] for task in review['role_tasks']]
        review['dispatch_briefs'][0]['agent_display_name'] = '不受约束的评审者'
        with self.assertRaises(ReviewGateError):
            validate_multi_agent_review('scenario', review)
        self.assertEqual([task['task_hash'] for task in review['role_tasks']], before)
