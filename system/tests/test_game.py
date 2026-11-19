import ast
import io
import random
from pathlib import Path
import runpy
import tokenize
import unittest
from unittest.mock import Mock, patch

from setting import game_settings as settings
from setting import control_settings
from system.game import Game, HIT_Y, speed_at, travel_distance
from system.controls import GameControls
from system.tests import make_hand


class GameTests(unittest.TestCase):
    def make_game(self, seed=1):
        game = Game(random.Random(seed))
        game.state = "PLAYING"
        return game

    def setUp(self):
        self.game = self.make_game()

    def test_menu_and_game_over_do_not_accumulate_time_or_score(self):
        for state in ("MENU", "GAME_OVER"):
            self.game.state = state
            self.game.update(100, "LEFT")
            self.assertEqual((self.game.elapsed, self.game.score), (0, 0))

    def test_random_endless_notes_cover_three_lanes_without_finishing(self):
        game = self.make_game(42)
        lanes = set()
        pitches = set()
        maximum_queue = 0
        for _ in range(1000):
            note = game.notes[0]
            lanes.add(note["lane"])
            pitches.add(note["midi"])
            game.update(0, None)
            game.update(note["hit_time"] - game.elapsed, ("LEFT", "CENTER", "RIGHT")[note["lane"]])
            self.assertAlmostEqual(game.note_y(note), HIT_Y)
            maximum_queue = max(maximum_queue, len(game.notes))
            game.sound_notes.clear()
        self.assertEqual(lanes, {0, 1, 2})
        self.assertEqual(pitches, set(settings.NOTE_POOL))
        self.assertEqual((game.hits, game.misses, game.state), (1000, 0, "PLAYING"))
        self.assertEqual(game.score, 1000 * (settings.SCORE_PER_HIT + settings.PERFECT_BONUS))
        self.assertLess(maximum_queue, 12)
        self.assertGreater(game.elapsed, 500)

    def test_new_round_gets_new_random_notes(self):
        game = self.make_game(42)
        sequences = []
        for _ in range(2):
            sequence = []
            for _ in range(30):
                note = game.notes[0]
                sequence.append((note["lane"], note["midi"]))
                game.update(0, None)
                game.update(note["hit_time"] - game.elapsed, ("LEFT", "CENTER", "RIGHT")[note["lane"]])
            sequences.append(sequence)
            game.reset()
        self.assertNotEqual(sequences[0], sequences[1])

    def test_speed_increases_smoothly_and_notes_get_closer_to_minimum(self):
        game = self.make_game()
        times = []
        for _ in range(250):
            note = game.notes[0]
            times.append(note["hit_time"])
            game.update(0, None)
            game.update(note["hit_time"] - game.elapsed, ("LEFT", "CENTER", "RIGHT")[note["lane"]])
        gaps = [second - first for first, second in zip(times, times[1:])]
        self.assertGreater(game.speed, settings.START_SPEED)
        self.assertLess(gaps[-1], gaps[0])
        self.assertAlmostEqual(gaps[-1], settings.MIN_NOTE_INTERVAL)
        self.assertGreaterEqual(min(gaps) + 1e-9, settings.MIN_NOTE_INTERVAL)
        self.assertTrue(all(second <= first + 1e-9 for first, second in zip(gaps, gaps[1:])))
        note = game.notes[0]
        before = game.note_y(note)
        game.update(0.01)
        movement = game.note_y(note) - before
        self.assertAlmostEqual(movement, speed_at(game.elapsed - 0.01) * 0.01 + 0.5 * settings.ACCELERATION * 0.01 ** 2)

    def test_zero_acceleration_keeps_speed_and_spacing_constant(self):
        with patch.object(settings, "ACCELERATION", 0):
            game = self.make_game()
            times = []
            for _ in range(30):
                note = game.notes[0]
                times.append(note["hit_time"])
                game.update(0, None)
                game.update(note["hit_time"] - game.elapsed, ("LEFT", "CENTER", "RIGHT")[note["lane"]])
            self.assertEqual(game.speed, settings.START_SPEED)
            for first, second in zip(times, times[1:]):
                self.assertAlmostEqual(second - first, 60 / settings.BPM)

    def test_early_wrong_late_and_held_commands_do_not_auto_hit(self):
        first = self.game.notes[0]["hit_time"]
        self.game.update(first - 0.5, "LEFT")
        self.game.update(0.5, "LEFT")
        self.assertEqual(self.game.hits, 0)
        self.game.update(0, "RIGHT")
        self.assertEqual(self.game.hits, 0)
        self.game.update(settings.HIT_WINDOW_SECONDS + 0.01, "LEFT")
        self.assertEqual((self.game.hits, self.game.misses), (0, 1))
        self.assertEqual(self.game.sound_notes, [])

    def test_one_held_gesture_only_hits_one_repeated_note(self):
        rng = Mock()
        rng.randrange.return_value = 0
        rng.choice.return_value = 60
        game = Game(rng)
        game.state = "PLAYING"
        game.update(game.notes[0]["hit_time"], "LEFT")
        game.update(game.notes[0]["hit_time"] - game.elapsed, "LEFT")
        self.assertEqual(game.hits, 1)
        game.update(0, None)
        game.update(0, "LEFT")
        self.assertEqual(game.hits, 2)
        game.update(game.notes[0]["hit_time"] - game.elapsed, "LEFT")
        self.assertEqual(game.hits, 2)

    def test_hit_window_boundaries_and_perfect_bonus(self):
        for offset, expected in ((-0.24, 100), (0.24, 100), (-0.1, 150), (0.1, 150), (0.241, 0)):
            with self.subTest(offset=offset):
                game = self.make_game()
                game.update(game.notes[0]["hit_time"] + offset, "LEFT")
                self.assertEqual(game.score, expected)

    def test_large_frame_does_not_backdate_gesture_or_fill_unbounded_queue(self):
        self.game.update(1000000, "LEFT")
        self.assertEqual(self.game.hits, 0)
        self.assertEqual(self.game.misses, settings.MAX_MISSES)
        self.assertEqual(self.game.state, "GAME_OVER")
        self.assertLess(len(self.game.notes), 12)

    def test_reset_clears_score_speed_spawn_clock_edges_flashes_and_sounds(self):
        self.game.update(self.game.notes[0]["hit_time"], "LEFT")
        self.game.update(100, None)
        self.game.rng = random.Random(1)
        self.game.reset()
        fresh = self.make_game()
        self.assertEqual({key: value for key, value in vars(self.game).items() if key != "rng"},
                         {key: value for key, value in vars(fresh).items() if key != "rng"})
        self.assertEqual(self.game.speed, settings.START_SPEED)

    def test_real_time_motion_and_misses_match_at_different_fps(self):
        outcomes = []
        for fps in (10, 30, 60, 144):
            game = self.make_game()
            for _ in range(fps * 3):
                game.update(1 / fps)
            outcomes.append((game.misses, game.note_y(game.notes[0]), game.elapsed, game.speed))
        for misses, y, elapsed, speed in outcomes:
            self.assertEqual(misses, 1)
            self.assertAlmostEqual(elapsed, 3)
            self.assertAlmostEqual(y, outcomes[0][1])
            self.assertAlmostEqual(speed, outcomes[0][3])

    def test_both_control_paths_play_endless_random_notes_with_dwell(self):
        for use_preset in (True, False):
            for fps in (15, 30, 60, 144):
                with self.subTest(use_preset=use_preset, fps=fps), patch.object(control_settings, "USE_PRESET", use_preset):
                    game = self.make_game(42)
                    control = GameControls()
                    for _ in range(60 * fps):
                        now = game.elapsed + 1 / fps
                        near = next((note for note in game.notes if -0.12 <= now - note["hit_time"] <= 0.12), None)
                        hands = []
                        if near:
                            if near["lane"] in (0, 1):
                                hands.append(make_hand("Left"))
                            if near["lane"] in (1, 2):
                                hands.append(make_hand("Right"))
                        command = control.update(hands, [], 1 / fps)
                        game.update(1 / fps, command)
                        game.sound_notes.clear()
                        if game.state == "GAME_OVER":
                            break
                    self.assertEqual(game.state, "PLAYING")
                    self.assertGreater(game.hits, 70)
                    self.assertEqual(game.misses, 0)


class FormatTests(unittest.TestCase):
    def test_data_files_are_literal_assignments_only(self):
        for filename in ("game_settings.py", "control_settings.py"):
            for node in ast.parse(Path("setting", filename).read_text(encoding="utf-8")).body:
                self.assertIsInstance(node, ast.Assign)
                ast.literal_eval(node.value)

    def test_system_has_no_comments_or_docstrings(self):
        for filename in Path("system").rglob("*.py"):
            if "artifacts" in filename.parts:
                continue
            source = filename.read_text(encoding="utf-8")
            with self.subTest(filename=str(filename)):
                self.assertFalse(any(token.type == tokenize.COMMENT for token in tokenize.generate_tokens(io.StringIO(source).readline)))
                for node in ast.walk(ast.parse(source)):
                    if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.assertIsNone(ast.get_docstring(node))

    def test_root_launcher_passes_camera_argument(self):
        with patch("system.app.main") as run_game, patch("sys.argv", ["main.py", "--camera", "2"]):
            runpy.run_path("main.py", run_name="__main__")
        run_game.assert_called_once_with(2)

    def test_invalid_game_settings_are_explained(self):
        for name, value in (("BPM", 0), ("START_SPEED", 0), ("FIRST_NOTE_DELAY", 0),
                            ("HIT_WINDOW_SECONDS", 1), ("PERFECT_WINDOW_SECONDS", 1),
                            ("MAX_MISSES", 0), ("NOTE_WIDTH", 200), ("NOTE_POOL", []),
                            ("NOTE_POOL", [150]), ("ACCELERATION", -1), ("MIN_NOTE_INTERVAL", 0),
                            ("SOUND_VOLUME", 2), ("BPM", float("inf")), ("LANE_COLORS", [(0, 0, 0)])):
            with self.subTest(name=name), patch.object(settings, name, value):
                with self.assertRaisesRegex(ValueError, "game_settings.py"):
                    Game()
