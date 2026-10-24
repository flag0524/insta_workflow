"""Pure scheduling/format tests; never contact Instagram or other services."""
import copy
import datetime as dt
import json
from pathlib import Path
import unittest
from plan_publish import choose_post, is_done, state_bucket, validate_plan, publish_safely

PLAN = json.loads((Path(__file__).parent / 'content_plan_20261025.json').read_text(encoding='utf-8'))
KST = dt.timezone(dt.timedelta(hours=9))


def at(text):
    return dt.datetime.fromisoformat(text).replace(tzinfo=KST)


def state(*days):
    value = {'published': {}, 'published_carousel': {}}
    for day in days:
        p = PLAN['posts'][day - 1]
        value[state_bucket(p)][p['id']] = {'media_id': 'test-only'}
    return value


class PlanTests(unittest.TestCase):
    def pick(self, text, done=(), **kwargs):
        return choose_post(PLAN, state(*done), now=at(text), **kwargs)

    def test_valid_workbook_plan(self):
        self.assertTrue(validate_plan(PLAN))

    def test_before_start(self):
        self.assertIsNone(self.pick('2026-10-24T20:00:00'))

    def test_not_early(self):
        self.assertIsNone(self.pick('2026-10-25T19:59:59'))

    def test_first_day_2000(self):
        p = self.pick('2026-10-25T20:00:00')
        self.assertEqual((p['day'], p['format']), (1, 'reel'))

    def test_same_day_retry(self):
        self.assertEqual(self.pick('2026-10-25T20:40:00')['day'], 1)

    def test_done_is_noop(self):
        self.assertIsNone(self.pick('2026-10-25T20:20:00', (1,)))

    def test_no_legacy_day_collision(self):
        old = {'published': {str(i): {'media_id': 'legacy'} for i in range(1, 50)}}
        self.assertEqual(choose_post(PLAN, old, now=at('2026-10-25T20:00:00'))['day'], 1)
        self.assertEqual(len(old['published']), 49)

    def test_recovery_not_before_0715(self):
        self.assertIsNone(self.pick('2026-10-26T07:14:59'))

    def test_reel_morning_recovery(self):
        self.assertEqual(self.pick('2026-10-26T07:15:00')['day'], 1)

    def test_delayed_morning_trigger(self):
        self.assertEqual(self.pick('2026-10-26T09:37:00')['day'], 1)

    def test_carousel_only_on_carousel_day(self):
        p = self.pick('2026-10-26T20:00:00')
        self.assertEqual((p['day'], p['format']), (2, 'carousel'))
        self.assertEqual(len(p['cards']), 6)

    def test_today_priority_over_old(self):
        self.assertEqual(self.pick('2026-10-26T20:20:00')['day'], 2)

    def test_no_evening_extra_backlog(self):
        self.assertIsNone(self.pick('2026-10-26T20:20:00', (2,)))

    def test_carousel_morning_recovery(self):
        self.assertEqual(self.pick('2026-10-27T07:15:00', (1,))['day'], 2)

    def test_only_yesterday(self):
        self.assertIsNone(self.pick('2026-10-27T07:15:00', (2,)))

    def test_end_date(self):
        self.assertEqual(self.pick('2026-11-23T20:00:00')['day'], 30)

    def test_last_morning_recovery(self):
        self.assertEqual(self.pick('2026-11-24T07:15:00')['day'], 30)

    def test_no_new_post_after_end(self):
        self.assertIsNone(self.pick('2026-11-24T20:00:00'))

    def test_long_after_end(self):
        self.assertIsNone(self.pick('2026-11-25T07:15:00'))

    def test_force_preview_allowed(self):
        self.assertEqual(self.pick('2026-10-24T20:00:00', force_day=30, dry_run=True)['day'], 30)

    def test_force_future_publish_blocked(self):
        with self.assertRaises(ValueError):
            self.pick('2026-10-24T20:00:00', force_day=1)

    def test_force_duplicate_blocked(self):
        with self.assertRaises(ValueError):
            self.pick('2026-10-25T20:20:00', (1,), force_day=1)

    def test_invalid_tag_count(self):
        bad = copy.deepcopy(PLAN)
        bad['posts'][0]['hashtags'].pop()
        with self.assertRaises(AssertionError):
            validate_plan(bad)

    def test_reel_verification_cannot_be_disabled(self):
        bad = copy.deepcopy(PLAN)
        bad['posts'][0]['verification_required'] = False
        with self.assertRaises(AssertionError):
            validate_plan(bad)

    def test_each_format_has_one_state_bucket(self):
        for p in PLAN['posts']:
            self.assertEqual(state_bucket(p), 'published' if p['format'] == 'reel' else 'published_carousel')

    def test_uncertain_publish_blocked_before_network(self):
        p = PLAN['posts'][0]
        with self.assertRaisesRegex(RuntimeError, 'uncertain'):
            publish_safely(None, p, {'pending_manual': {p['id']: {}}}, None, None, '')


if __name__ == '__main__':
    unittest.main()
