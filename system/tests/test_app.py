import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from pathlib import Path
import random
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pygame

from setting import control_settings, game_settings
from system import app
from system.controls import GameControls
from system.game import Game, LANE_CENTERS
from system.tests import make_hand


def click():
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=app.BUTTON.center)


def camera_mock():
    camera = Mock()
    camera.error = ""
    camera.pose_landmarks = []
    camera.read.return_value = (np.zeros((480, 640, 3), dtype=np.uint8), [])
    return camera


class LoopTests(unittest.TestCase):
    def test_full_loop_start_hit_lose_replay_both_modes(self):
        for use_preset in (True, False):
            game = Game(random.Random(1))
            camera = camera_mock()
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            camera.read.side_effect = [(frame, []), (frame, [make_hand("Left")]), (frame, []),
                                       (frame, []), (frame, []), (frame, [])]
            snapshots = []
            controls = []

            def snapshot(screen, current, *args):
                snapshots.append((current.state, current.score, current.elapsed, current.hits, current.misses))
                controls.append((args[-1].command, args[-1].held_seconds))

            with self.subTest(use_preset=use_preset), patch.object(control_settings, "USE_PRESET", use_preset), patch.object(
                control_settings, "HOLD_SECONDS", 0,
            ), patch.object(app, "Game", return_value=game), patch.object(app, "HandCamera", return_value=camera), patch.object(
                app.pygame.time, "Clock", return_value=Mock(),
            ), patch.object(app.time, "perf_counter", side_effect=[0, 50, 52.6, 60, 61, 62, 63]), patch.object(
                app.pygame.event, "get", side_effect=[[click()], [], [], [click()], [], [pygame.event.Event(pygame.QUIT)]],
            ), patch.object(app, "draw_screen", side_effect=snapshot):
                app.main()
            self.assertEqual(snapshots[0], ("MENU", 0, 0, 0, 0))
            self.assertEqual(snapshots[1], ("PLAYING", 0, 0, 0, 0))
            self.assertEqual((snapshots[2][1], snapshots[2][3]), (150, 1))
            self.assertAlmostEqual(snapshots[2][2], 2.6)
            self.assertEqual(snapshots[3][0], "GAME_OVER")
            self.assertEqual(snapshots[4], ("PLAYING", 0, 0, 0, 0))
            self.assertEqual(controls[4], (None, 0))
            camera.close.assert_called_once()
            self.assertFalse(pygame.get_init())

    def test_open_hands_do_not_start_or_replay_without_click_in_both_modes(self):
        for use_preset in (True, False):
            game = Game(random.Random(1))
            camera = camera_mock()
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            opened = [make_hand("Left", "แบมือ"), make_hand("Right", "แบมือ")]
            camera.read.side_effect = [(frame, opened)] * 8
            states = []
            with self.subTest(use_preset=use_preset), patch.multiple(control_settings, USE_PRESET=use_preset, HOLD_SECONDS=0), patch.object(
                app, "Game", return_value=game,
            ), patch.object(app, "HandCamera", return_value=camera), patch.object(app.pygame.time, "Clock", return_value=Mock()), patch.object(
                app.time, "perf_counter", side_effect=[0, 1, 2, 3, 30, 31, 32, 33, 34],
            ), patch.object(app.pygame.event, "get", side_effect=[[], [], [click()], [], [], [], [click()], [pygame.event.Event(pygame.QUIT)]]), patch.object(
                app, "draw_screen", side_effect=lambda screen, current, *args: states.append(current.state),
            ):
                app.main()
            self.assertEqual(states, ["MENU", "MENU", "MENU", "PLAYING", "GAME_OVER", "GAME_OVER", "GAME_OVER", "PLAYING"])
            self.assertEqual((game.score, game.elapsed, game.misses), (0, 0, 0))
            camera.close.assert_called_once()

    def test_unready_camera_blocks_start_and_read_error_closes_resources(self):
        game = Game(random.Random(1))
        self.assertTrue(app.handle_event(click(), game, False))
        self.assertEqual(game.state, "MENU")
        camera = camera_mock()
        camera.read.side_effect = RuntimeError("simulated camera failure")
        with patch.object(app, "HandCamera", return_value=camera):
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                app.main()
        camera.close.assert_called_once()
        self.assertFalse(pygame.get_init())

    def test_escape_and_close_exit(self):
        for event in (pygame.event.Event(pygame.QUIT), pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)):
            self.assertFalse(app.handle_event(event, Game(), True))


class ScreenSoundTests(unittest.TestCase):
    def setUp(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        self.screen = pygame.display.set_mode(app.WINDOW_SIZE)
        names = "tahoma,leelawadeeui,notosansthai,arial"
        self.fonts = [pygame.font.SysFont(names, size, bold=size == 42) for size in (24, 20, 42)]

    def tearDown(self):
        pygame.quit()

    def test_render_all_states_and_custom_instructions(self):
        output = Path("system/artifacts")
        output.mkdir(exist_ok=True)
        frame = np.full((480, 640, 3), (28, 44, 65), dtype=np.uint8)
        for filename, state, error in (("menu", "MENU", ""), ("playing", "PLAYING", ""),
                                       ("game_over", "GAME_OVER", ""), ("camera_error", "MENU", "Camera unavailable"),
                                       ("model_error", "MENU", "Hand model missing")):
            game = Game(random.Random(1))
            if state != "MENU":
                game.reset()
                for _ in range(3):
                    note = game.notes[0]
                    game.update(0, None)
                    game.update(note["hit_time"] - game.elapsed, ("LEFT", "CENTER", "RIGHT")[note["lane"]])
                if state == "GAME_OVER":
                    game.update(100)
                else:
                    game.update(0.4, None)
            game.state = state
            app.draw_screen(self.screen, game, None if error else frame, [], error, *self.fonts)
            pygame.image.save(self.screen, output / f"{filename}.png")
        with patch.object(control_settings, "USE_PRESET", False):
            game = Game(random.Random(1))
            app.draw_screen(self.screen, game, frame, [], "", *self.fonts, GameControls())
            pygame.image.save(self.screen, output / "custom_mode.png")

    def test_game_colors_and_note_sizes_are_editable(self):
        game = Game(random.Random(1))
        game.reset()
        game.elapsed = game.notes[0]["hit_time"] - 1
        note = game.notes[0]
        game.draw(self.screen)
        x, y = LANE_CENTERS[note["lane"]], round(game.note_y(note)) - 5
        self.assertEqual(self.screen.get_at((x, y))[:3], game_settings.LANE_COLORS[0])

    def test_sound_has_expected_pitch_duration_volume_and_clears_queue(self):
        sound = app.PianoSound()
        samples = pygame.sndarray.array(sound.sounds[60])
        self.assertEqual(samples.shape, (35280, 2))
        self.assertLessEqual(np.max(np.abs(samples)), 32767 * game_settings.SOUND_VOLUME + 1)
        frequency = np.argmax(np.abs(np.fft.rfft(samples[:, 0]))) * 44100 / len(samples)
        self.assertAlmostEqual(frequency, 261.63, delta=2)
        game = Game(random.Random(1))
        game.sound_notes = [60, 64]
        sound.play_pending(game)
        self.assertEqual(game.sound_notes, [])
        sound.reset()
        self.assertEqual(pygame.mixer.get_busy(), False)

    def test_sound_disabled_or_no_device_is_supported(self):
        with patch.object(game_settings, "SOUND_ENABLED", False):
            self.assertEqual(app.PianoSound().sounds, {})
        with patch.object(pygame.mixer, "get_init", return_value=None):
            self.assertEqual(app.PianoSound().sounds, {})
