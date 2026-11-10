import copy
import json
import os
import unittest
from unittest.mock import Mock, patch

from src import history_service as h
from src.demo_anomaly import build_demo_request
from src.ai_service import anomalies_for_frontend


class Conditional(Exception):
    pass


class MemoryStore:
    rows = {}
    hidden = set()
    client = Mock()
    client.exceptions.ConditionalCheckFailedException = Conditional

    def __init__(self, owner):
        self.owner = owner

    def get(self, key):
        return copy.deepcopy(self.rows.get((self.owner, key)))

    def put(self, key, value):
        if (self.owner, key) in self.rows:
            raise Conditional()
        self.update(key, value)

    def update(self, key, value, notification_status=None):
        self.rows[self.owner, key] = copy.deepcopy(value)

    def claim_delivery(self, key, value):
        if self.get(key).get('notification'):
            raise Conditional()
        self.update(key, value)

    def hide_notification(self, key):
        if not (self.get(key) or {}).get('notification'):
            raise h.HistoryError(404, 'notification_not_found')
        self.hidden.add((self.owner, key))

    def page(self, cursor=None):
        values = [v for (owner, _), v in self.rows.items() if owner == self.owner]
        return dict(historyStatus='ok', guideHistory=[v['result']['aiGuide'] for v in values if 'result' in v],
                    notifications=[v['notification'] for v in values if 'notification' in v and (self.owner, v['id']) not in self.hidden], nextCursor=None)


def event(body=None, subject='account-a'):
    return dict(body=json.dumps(body or {}), requestContext=dict(authorizer=dict(jwt=dict(claims=dict(sub=subject)))))


def result(scenario='multi'):
    return dict(statusCode=200, inputKind='virtual', scenario=scenario, scenarioLabel='다중 지표',
        referenceDate='2026-11-14', aiGuide=dict(status='generated', headline='수면 부족', text='가상 시연 가이드'), anomalies=[])


class HistoryFlowTest(unittest.TestCase):
    def setUp(self):
        MemoryStore.rows = {}
        MemoryStore.hidden = set()
        self.env = patch.dict(os.environ, {'DEMO_SNS_TOPIC_ARN': 'arn:aws:sns:ap-northeast-2:709569057941:wearcare-mate-alert'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def analyze(self, subject='account-a'):
        self.runner = Mock(side_effect=lambda scenario: result(scenario))
        return h.handle_demo(event({'scenario': 'multi'}, subject), MemoryStore, self.runner)

    def test_scenarios_are_server_fixed_and_analysis_never_sends(self):
        expected = {'sleep': 'sleep_hours', 'hrv': 'heart_rate_variability', 'stress': 'stress_level', 'restless': 'movement_during_sleep'}
        for scenario, metric in expected.items():
            request = build_demo_request(scenario)
            self.assertIn(metric, request['metrics'])
            self.assertEqual(request['metrics']['steps'], 10000)
            self.assertIs(request['notify'], False)
        request = build_demo_request('multi')
        self.assertTrue({'sleep_hours', 'heart_rate_variability', 'stress_level'} <= set(request['metrics']))
        request['metrics']['sleep_hours'] = 99
        self.assertEqual(build_demo_request('multi')['metrics']['sleep_hours'], 3)

    def test_analyze_persists_and_relogin_can_read_without_generating(self):
        res = self.analyze()
        self.assertEqual(res['persistenceStatus'], 'saved')
        self.assertEqual(len(h.read_history(event(), MemoryStore)['guideHistory']), 1)
        self.assertEqual(self.runner.call_count, 1)

    def test_other_account_cannot_read_or_send_saved_guide(self):
        res = self.analyze()
        self.assertEqual(h.read_history(event(subject='account-b'), MemoryStore)['guideHistory'], [])
        sns = Mock()
        with self.assertRaises(h.HistoryError) as caught:
            h.handle_demo(event({'action': 'send', 'eventId': res['eventId']}, 'account-b'), MemoryStore, sns_factory=lambda: sns)
        self.assertEqual(caught.exception.status, 404)
        sns.publish.assert_not_called()

    def test_repeated_send_calls_publish_only_once_and_preserve_history(self):
        res = self.analyze()
        sns = Mock()
        sns.publish.return_value = {'MessageId': 'accepted-id'}
        send = event({'action': 'send', 'eventId': res['eventId']})
        first = h.handle_demo(send, MemoryStore, sns_factory=lambda: sns)
        second = h.handle_demo(send, MemoryStore, sns_factory=lambda: sns)
        self.assertEqual(first['notification']['status'], 'accepted')
        self.assertTrue(second['duplicate'])
        self.assertEqual(sns.publish.call_count, 1)
        self.assertIn('실제 사용자 기록 아님', sns.publish.call_args.kwargs['Message'])
        self.assertEqual(len(h.read_history(event(), MemoryStore)['notifications']), 1)

    def test_timeout_does_not_resend_or_claim_email_delivered(self):
        res = self.analyze()
        sns = Mock()
        sns.publish.side_effect = TimeoutError()
        send = event({'action': 'send', 'eventId': res['eventId']})
        first = h.handle_demo(send, MemoryStore, sns_factory=lambda: sns)
        h.handle_demo(send, MemoryStore, sns_factory=lambda: sns)
        self.assertEqual(first['notification']['status'], 'unknown')
        self.assertEqual(sns.publish.call_count, 1)

    def test_rejects_untrusted_metrics_recipient_subject_and_invalid_scenario(self):
        for body in ({'metrics': {'steps': 0}}, {'recipient': 'x'}, {'subject': 'account-b'},
                     {'scenario': 'oops'}, {'scenario': []}, {'action': 'oops'}):
            with self.assertRaises(h.HistoryError) as caught:
                h.handle_demo(event(body), MemoryStore)
            self.assertEqual(caught.exception.status, 400)
        with self.assertRaises(h.HistoryError):
            h.handle_demo({'body': '{}'}, MemoryStore)

    def test_storage_unavailable_prevents_analysis(self):
        factory, runner = Mock(), Mock()
        factory.return_value.put.side_effect = RuntimeError()
        with self.assertRaises(RuntimeError):
            h.handle_demo(event(), factory, runner)
        runner.assert_not_called()

    def test_population_anomalies_have_distinct_titles(self):
        body = {'date': '2026-11-14', 'anomalies': [dict(type=t, severity='high', value=3,
            metric='test', basis='population', population_mean=7) for t in ('SLEEP_SHORT', 'HRV_LOW', 'STRESS_HIGH')]}
        rows = anomalies_for_frontend(body)
        self.assertEqual(len({r['title'] for r in rows}), 3)
        self.assertTrue(all('집단 기준' in r['desc'] for r in rows))

    def test_query_cursor_never_changes_owner_and_returns_continuation(self):
        client = Mock()
        key = '00000000000000000000000000000001'
        client.query.return_value = {'Items': [], 'LastEvaluatedKey': {'sk': {'S': 'EVENT#' + key}}}
        store = h.HistoryStore('a', client=client, table='history')
        page = store.page()
        store.page(page['nextCursor'])
        args = client.query.call_args.kwargs
        self.assertEqual(args['ExclusiveStartKey']['pk']['S'], 'USER#a')
        self.assertEqual(args['ExpressionAttributeValues'][':pk']['S'], 'USER#a')
        self.assertTrue(args['ConsistentRead'])
        with self.assertRaises(h.HistoryError):
            store.page('bad-cursor')

    def test_saved_result_missing_guide_cannot_send(self):
        res = self.analyze()
        store = MemoryStore(h.principal(event()))
        saved = store.get(res['eventId'])
        saved['result']['aiGuide']['status'] = 'missing'
        store.update(res['eventId'], saved)
        with self.assertRaises(h.HistoryError) as caught:
            h.send_saved(store, res['eventId'])
        self.assertEqual(caught.exception.status, 409)

    def test_real_generated_guide_is_saved_once(self):
        store = MemoryStore('real-owner')
        guide = dict(status='generated', updatedAt='2026-11-10T12:00:00+09:00',
                     referenceDate='2016-04-10', headline='실제 기록 가이드', text='안내')
        h.persist_real_guide(store, guide)
        h.persist_real_guide(store, guide)
        self.assertEqual(len(store.rows), 1)
        self.assertEqual(next(iter(store.rows.values()))['result']['inputKind'], 'real')

    def test_failed_result_save_does_not_offer_an_email_event_id(self):
        store = Mock()
        store.update.side_effect = RuntimeError()
        response = h.handle_demo(event(), lambda owner: store, Mock(return_value=result()))
        self.assertEqual(response['persistenceStatus'], 'unavailable')
        self.assertIsNone(response['eventId'])

    def test_sns_accepted_but_record_save_failed_is_not_reported_saved(self):
        response = self.analyze()
        store = MemoryStore(h.principal(event()))
        sns = Mock()
        sns.publish.return_value = {'MessageId': 'accepted'}
        # claim_delivery uses MemoryStore.update, so fail only the final update.
        original = store.update
        store.update = Mock(side_effect=lambda key, data, notification_status=None:
            original(key, data) if notification_status is None else (_ for _ in ()).throw(RuntimeError()))
        sent = h.send_saved(store, response['eventId'], lambda: sns)
        self.assertEqual(sent['persistenceStatus'], 'unavailable')
        h.send_saved(store, response['eventId'], lambda: sns)
        self.assertEqual(sns.publish.call_count, 1)

    def test_delivery_claim_uses_atomic_absence_condition(self):
        client = Mock()
        store = h.HistoryStore('owner', client=client, table='history')
        store.claim_delivery('a' * 32, {'id': 'a' * 32})
        args = client.update_item.call_args.kwargs
        self.assertEqual(args['ConditionExpression'], 'attribute_exists(pk) AND attribute_not_exists(delivery)')
        self.assertEqual(args['Key']['pk']['S'], 'USER#owner')


class NotificationHidingTest(unittest.TestCase):
    setUp = HistoryFlowTest.setUp
    analyze = HistoryFlowTest.analyze
    def test_hide_keeps_guide_receipt_and_duplicate_send_prevention(self):
        res = self.analyze()
        sns = Mock()
        sns.publish.return_value = {'MessageId': 'accepted'}
        send = event({'action': 'send', 'eventId': res['eventId']})
        h.handle_demo(send, MemoryStore, sns_factory=lambda: sns)
        hidden = h.handle_demo(event({'action': 'hide_notification', 'eventId': res['eventId']}), MemoryStore)
        self.assertEqual(hidden['hiddenEventId'], res['eventId'])
        page = h.read_history(event(), MemoryStore)
        self.assertEqual(page['notifications'], [])
        self.assertEqual(len(page['guideHistory']), 1)
        duplicate = h.handle_demo(send, MemoryStore, sns_factory=lambda: sns)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(sns.publish.call_count, 1)

    def test_other_account_cannot_hide(self):
        res = self.analyze()
        with self.assertRaises(h.HistoryError) as caught:
            h.handle_demo(event({'action': 'hide_notification', 'eventId': res['eventId']}, 'other'), MemoryStore)
        self.assertEqual(caught.exception.status, 404)

    def test_dynamodb_hide_changes_only_visibility_attribute(self):
        client = Mock()
        store = h.HistoryStore('owner', client=client, table='history')
        client.get_item.return_value = {'Item': {'payload': {'S': json.dumps({'notification': {'status': 'accepted'}})}}}
        store.hide_notification('a' * 32)
        args = client.update_item.call_args.kwargs
        self.assertEqual(args['UpdateExpression'], 'SET notificationHidden = :hidden')
        client.query.return_value = {'Items': [{'notificationHidden': {'BOOL': True},
            'payload': {'S': json.dumps({'notification': {'status': 'accepted'}})}}]}
        self.assertEqual(store.page()['notifications'], [])
