#!/usr/bin/env python3
"""Synthetic clock/correlation checks; this does not run the game."""
import unittest

from analyze_playability import os_event_metrics


class OSReceiptAnalysis(unittest.TestCase):
    sync = {'us': 0, 'unix_us': 1_000_000}

    def setUp(self):
        self.actions = [
            {'kind': 'key', 'key': 'Left', 'wall_unix_ns': 1_000_000_000},
            {'kind': 'mouse_click', 'x': 20, 'y': 30, 'wall_unix_ns': 1_100_000_000},
            {'kind': 'key', 'key': 'z', 'wall_unix_ns': 1_200_000_000},
        ]
        self.trace = []
        self.event(0, 5_000, 15_000, event_type='key', physical_key_name='Left', echo=False)
        self.event(1, 10_000, 16_000, event_type='key', physical_key_name='Left', pressed=False)
        self.event(2, 20_000, 25_000, event_type='key', physical_key_name='Left', echo=True)
        self.event(3, 105_000, 115_000, event_type='mouse_button', button=1, x=20.7, y=31)
        self.event(4, 1_600_000, 1_620_000, event_type='key', physical_keycode=90)

    def event(self, event_id, received, drawn, **fields):
        self.trace.extend([
            {'kind': 'os_input_received', 'event_id': event_id, 'us': received, 'pressed': True, **fields},
            {'kind': 'os_event_frame_post_draw_feedback', 'event_id': event_id, 'us': drawn,
             'event_us': received, 'elapsed_ms': (drawn-received)/1000},
        ])

    def test_receipts_and_correlated_command_timestamps_are_separate(self):
        result = os_event_metrics(self.trace, self.actions, self.sync)
        self.assertEqual(result['OS_event_received_to_frame_post_draw']['n'], 3)
        self.assertEqual(result['OS_event_received_to_frame_post_draw']['max_ms'], 20)
        self.assertEqual(result['OS_event_all_received_to_frame_post_draw']['n'], 5)
        self.assertEqual(result['OS_command_to_matched_OS_event_received']['max_ms'], 1400)
        self.assertEqual(result['OS_command_to_matched_OS_event_frame_post_draw']['max_ms'], 1420)
        self.assertEqual(result['OS_event_matching']['matched_commands'], 3)
        self.assertEqual(result['OS_event_matching']['latency_outliers_removed'], 0)

    def test_wrong_button_coordinates_do_not_match(self):
        self.trace = []
        self.event(8, 105_000, 115_000, event_type='mouse_button', button=1, x=40, y=31)
        result = os_event_metrics(self.trace, self.actions[1:2], self.sync)
        self.assertEqual(result['OS_event_matching']['matched_commands'], 0)
        self.assertEqual(result['OS_event_matching']['unmatched_engine_presses'], 1)

    def test_phase_bounds_follow_receipt_time(self):
        result = os_event_metrics(self.trace, self.actions, self.sync, 1_100_000, 1_200_000)
        self.assertEqual(result['OS_event_matching']['matched_commands'], 1)
        self.assertEqual(result['OS_event_received_to_frame_post_draw']['n'], 1)

    def test_late_ambiguous_receipt_is_retained_and_flagged(self):
        actions = [self.actions[2], dict(self.actions[2], wall_unix_ns=1_300_000_000)]
        result = os_event_metrics(self.trace, actions, self.sync)
        self.assertEqual(result['OS_event_matching']['ambiguous_crosses_later_compatible_command'], 1)
        self.assertEqual(result['OS_command_to_matched_OS_event_received']['max_ms'], 1400)

    def test_old_trace_is_not_run(self):
        result = os_event_metrics([], self.actions, self.sync)
        self.assertEqual(result['OS_event_matching']['status'], 'NOT_RUN')
        self.assertEqual(result['OS_event_received_to_frame_post_draw']['status'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
