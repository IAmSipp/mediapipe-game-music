import unittest
from unittest.mock import patch

from setting import control_settings as settings
from setting import hand_controls
from system.controls import GameControls, preset_state
from system.tests import make_hand, make_pose


class ControlTests(unittest.TestCase):
    def setUp(self):
        config = patch.multiple(settings, USE_PRESET=True, LEFT_ACTION="กำมือซ้าย",
                                CENTER_ACTION="กำมือสองข้าง", RIGHT_ACTION="กำมือขวา",
                                SENSITIVITY=1.0, HOLD_SECONDS=0.0)
        config.start()
        self.addCleanup(config.stop)

    def test_default_three_commands_for_both_modes(self):
        cases = [([], None), ([make_hand("Left")], "LEFT"), ([make_hand("Right")], "RIGHT"),
                 ([make_hand("Left"), make_hand("Right")], "CENTER"),
                 ([make_hand("Left", "แบมือ"), make_hand("Right", "แบมือ")], None),
                 ([make_hand("Left", "แบมือ")], None),
                 ([make_hand("Left"), make_hand("Right", "แบมือ")], "LEFT")]
        for use_preset in (True, False):
            with patch.object(settings, "USE_PRESET", use_preset):
                control = GameControls()
                for hands, command in cases:
                    with self.subTest(use_preset=use_preset, command=command):
                        self.assertEqual(control.update(hands, [], 0), command)

    def test_all_hand_presets_and_both_priority(self):
        for gesture in ("กำมือ", "แบมือ", "ชูนิ้วชี้", "ชูสองนิ้ว", "จีบนิ้ว"):
            with self.subTest(gesture=gesture), patch.multiple(
                settings, LEFT_ACTION=gesture + "ซ้าย", CENTER_ACTION=gesture + "สองข้าง",
                RIGHT_ACTION=gesture + "ขวา",
            ):
                control = GameControls()
                left, right = make_hand("Left", gesture), make_hand("Right", gesture)
                self.assertEqual(control.update([left], [], 0), "LEFT")
                self.assertEqual(control.update([right], [], 0), "RIGHT")
                self.assertEqual(control.update([left, right], [], 0), "CENTER")

    def test_both_needs_two_distinct_confident_hands(self):
        left, right = make_hand("Left"), make_hand("Right")
        self.assertFalse(preset_state("กำมือสองข้าง", [left, left], [])[0])
        right["confidence"] = 0.2
        self.assertFalse(preset_state("กำมือสองข้าง", [left, right], [])[0])
        self.assertFalse(preset_state("กำมือซ้าย", [{"side": "Left", "landmarks": []}], [])[0])

    def test_pose_presets_and_model_selection(self):
        for gesture in ("ยกแขน", "เอียงตัว", "เอียงศีรษะ"):
            with self.subTest(gesture=gesture), patch.multiple(
                settings, LEFT_ACTION=gesture + "ซ้าย", RIGHT_ACTION=gesture + "ขวา",
            ):
                control = GameControls()
                self.assertTrue(control.detect_pose and control.detect_hands)
                self.assertEqual(control.update([], make_pose(gesture, "Left"), 0), "LEFT")
                self.assertEqual(control.update([], make_pose(gesture, "Right"), 0), "RIGHT")
                self.assertIsNone(control.update([], make_pose(), 0))
        with patch.multiple(settings, LEFT_ACTION="ยกแขนซ้าย", CENTER_ACTION="เอียงตัวซ้าย",
                            RIGHT_ACTION="ยกแขนขวา"):
            control = GameControls()
            self.assertFalse(control.detect_hands)
            self.assertTrue(control.detect_pose)

    def test_conflicting_single_gestures_produce_no_command(self):
        with patch.object(settings, "CENTER_ACTION", "ชูนิ้วชี้สองข้าง"):
            control = GameControls()
            self.assertIsNone(control.update([make_hand("Left"), make_hand("Right")], [], 0))

    def test_dwell_seconds_release_change_and_reset(self):
        with patch.object(settings, "HOLD_SECONDS", 0.06):
            for fps in (10, 30, 60, 144):
                control = GameControls()
                hands = [make_hand("Left")]
                self.assertIsNone(control.update(hands, [], 50))
                elapsed = 0
                while control.command is None:
                    elapsed += 1 / fps
                    control.update(hands, [], 1 / fps)
                self.assertGreaterEqual(elapsed + 1e-9, 0.06)
                self.assertLessEqual(elapsed, 0.06 + 1 / fps + 1e-9)
                self.assertIsNone(control.update([make_hand("Right")], [], 1))
                self.assertIsNone(control.update([], [], 1))
                self.assertEqual(control.held_seconds, 0)
                control.reset()
                self.assertIsNone(control.command)
                self.assertIsNone(control.pending_command)

    def test_preset_never_calls_custom_rules(self):
        with patch.object(hand_controls, "get_note_command", side_effect=AssertionError("custom called")):
            self.assertEqual(GameControls().update([make_hand("Right")], [], 0), "RIGHT")

    def test_custom_ignores_every_preset_setting(self):
        with patch.multiple(settings, USE_PRESET=False, LEFT_ACTION=None, CENTER_ACTION=None,
                            RIGHT_ACTION=None, SENSITIVITY=-1, HOLD_SECONDS=999), patch.object(
            hand_controls, "get_note_command", return_value="CENTER",
        ) as custom:
            control = GameControls()
            self.assertEqual(control.update([], [], 0), "CENTER")
            custom.assert_called_once_with([], [])

    def test_switching_modes_preserves_custom_function(self):
        custom_function = hand_controls.get_note_command
        for enabled in (False, True, False):
            with patch.object(settings, "USE_PRESET", enabled):
                self.assertEqual(GameControls().update([make_hand("Left")], [], 0), "LEFT")
                self.assertIs(hand_controls.get_note_command, custom_function)

    def test_invalid_config_and_custom_return_are_explained(self):
        for name, value in (("USE_PRESET", "False"), ("USE_PRESET", 1), ("LEFT_ACTION", "bad"),
                            ("RIGHT_ACTION", "กำมือซ้าย"), ("CENTER_ACTION", "bad"),
                            ("HOLD_SECONDS", -1), ("SENSITIVITY", 0),
                            ("HOLD_SECONDS", float("nan"))):
            with self.subTest(name=name), patch.object(settings, name, value):
                with self.assertRaisesRegex(ValueError, "control_settings.py"):
                    GameControls()
        for command in ("bad", "START"):
            with patch.object(settings, "USE_PRESET", False), patch.object(hand_controls, "get_note_command", return_value=command):
                with self.assertRaisesRegex(ValueError, "hand_controls.py"):
                    GameControls().update([], [], 0)
        with patch.object(settings, "USE_PRESET", False), patch.multiple(hand_controls, USE_HANDS=False, USE_POSE=False):
            with self.assertRaisesRegex(ValueError, "USE_HANDS"):
                GameControls()
