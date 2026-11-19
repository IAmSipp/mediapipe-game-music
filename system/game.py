import math
import random

import pygame

from setting import game_settings as settings


BOARD = pygame.Rect(40, 100, 440, 620)
LANE_CENTERS = (113, 260, 407)
HIT_Y = 624
COMMAND_LANES = {"LEFT": 0, "CENTER": 1, "RIGHT": 2}


def validate_settings():
    values = (settings.BPM, settings.START_SPEED, settings.ACCELERATION,
              settings.MIN_NOTE_INTERVAL, settings.FIRST_NOTE_DELAY,
              settings.HIT_WINDOW_SECONDS, settings.PERFECT_WINDOW_SECONDS,
              settings.SCORE_PER_HIT, settings.PERFECT_BONUS, settings.SOUND_VOLUME)
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
        raise ValueError("setting/game_settings.py: numeric values must be finite")
    if settings.BPM <= 0 or settings.START_SPEED <= 0 or settings.ACCELERATION < 0:
        raise ValueError("setting/game_settings.py: BPM/START_SPEED > 0; ACCELERATION >= 0")
    if settings.FIRST_NOTE_DELAY <= 0 or travel_distance(settings.FIRST_NOTE_DELAY) < HIT_Y - BOARD.top:
        raise ValueError("setting/game_settings.py: FIRST_NOTE_DELAY must allow a full fall from the board top")
    if not 0 < settings.MIN_NOTE_INTERVAL <= 60 / settings.BPM:
        raise ValueError("setting/game_settings.py: MIN_NOTE_INTERVAL must be > 0 and <= 60/BPM")
    if not 0 < settings.HIT_WINDOW_SECONDS < settings.MIN_NOTE_INTERVAL / 2:
        raise ValueError("setting/game_settings.py: HIT_WINDOW_SECONDS must be > 0 and less than half MIN_NOTE_INTERVAL")
    if not 0 <= settings.PERFECT_WINDOW_SECONDS <= settings.HIT_WINDOW_SECONDS:
        raise ValueError("setting/game_settings.py: PERFECT_WINDOW_SECONDS must be within HIT_WINDOW_SECONDS")
    if type(settings.MAX_MISSES) is not int or settings.MAX_MISSES < 1:
        raise ValueError("setting/game_settings.py: MAX_MISSES must be a positive integer")
    if settings.SCORE_PER_HIT < 0 or settings.PERFECT_BONUS < 0 or not 0 <= settings.SOUND_VOLUME <= 1:
        raise ValueError("setting/game_settings.py: scores >= 0; SOUND_VOLUME between 0 and 1")
    if not 30 <= settings.NOTE_WIDTH <= 132 or not 20 <= settings.NOTE_HEIGHT <= 100:
        raise ValueError("setting/game_settings.py: NOTE_WIDTH 30-132; NOTE_HEIGHT 20-100")
    if not settings.NOTE_POOL or any(type(note) is not int or not 21 <= note <= 108 for note in settings.NOTE_POOL):
        raise ValueError("setting/game_settings.py: NOTE_POOL requires MIDI numbers 21-108")
    colors = [settings.BOARD_COLOR, settings.LINE_COLOR, *settings.LANE_COLORS]
    if len(settings.LANE_COLORS) != 3 or any(
        len(color) != 3 or any(type(value) is not int or not 0 <= value <= 255 for value in color)
        for color in colors
    ):
        raise ValueError("setting/game_settings.py: three LANE_COLORS and RGB values 0-255 required")


def travel_distance(elapsed):
    return settings.START_SPEED * elapsed + 0.5 * settings.ACCELERATION * elapsed ** 2


def speed_at(elapsed):
    return settings.START_SPEED + settings.ACCELERATION * elapsed


class Game:
    def __init__(self, rng=None):
        validate_settings()
        self.rng = random.Random() if rng is None else rng
        self.reset()
        self.state = "MENU"

    def reset(self):
        self.state = "PLAYING"
        self.elapsed = 0.0
        self.score = 0
        self.hits = 0
        self.misses = 0
        self.previous_command = None
        self.feedback = ""
        self.feedback_until = 0.0
        self.flashes = [0.0, 0.0, 0.0]
        self.sound_notes = []
        self.notes = []
        self.next_hit_time = settings.FIRST_NOTE_DELAY
        self.fill_notes()

    @property
    def speed(self):
        return speed_at(self.elapsed)

    def spawn_note(self):
        hit_time = self.next_hit_time
        self.notes.append({"lane": self.rng.randrange(3), "midi": self.rng.choice(settings.NOTE_POOL),
                           "hit_time": hit_time, "target_distance": travel_distance(hit_time)})
        interval = max(settings.MIN_NOTE_INTERVAL, 60 / settings.BPM * settings.START_SPEED / speed_at(hit_time))
        self.next_hit_time += interval

    def fill_notes(self):
        horizon = travel_distance(self.elapsed) + HIT_Y - BOARD.top
        while not self.notes or self.notes[-1]["target_distance"] <= horizon:
            self.spawn_note()

    def note_y(self, note):
        return HIT_Y - (note["target_distance"] - travel_distance(self.elapsed))

    def update(self, delta_seconds, command=None):
        if self.state != "PLAYING":
            return
        self.elapsed += max(0.0, delta_seconds)
        while self.notes and self.elapsed - self.notes[0]["hit_time"] > settings.HIT_WINDOW_SECONDS + 1e-9:
            self.notes.pop(0)
            self.misses += 1
            self.feedback = "พลาด"
            self.feedback_until = self.elapsed + 0.45
            if self.misses >= settings.MAX_MISSES:
                self.state = "GAME_OVER"
                break
            if not self.notes:
                self.spawn_note()
        if self.state == "PLAYING":
            self.fill_notes()
        if self.state == "PLAYING" and command in COMMAND_LANES and command != self.previous_command:
            lane = COMMAND_LANES[command]
            self.flashes[lane] = self.elapsed + 0.14
            candidates = [note for note in self.notes if note["lane"] == lane
                          and abs(note["hit_time"] - self.elapsed) <= settings.HIT_WINDOW_SECONDS + 1e-9]
            if candidates:
                note = min(candidates, key=lambda item: abs(item["hit_time"] - self.elapsed))
                perfect = abs(note["hit_time"] - self.elapsed) <= settings.PERFECT_WINDOW_SECONDS + 1e-9
                self.notes.remove(note)
                self.hits += 1
                self.score += settings.SCORE_PER_HIT + (settings.PERFECT_BONUS if perfect else 0)
                self.sound_notes.append(note["midi"])
                self.feedback = "ตรงจังหวะ!" if perfect else "ดี!"
                self.feedback_until = self.elapsed + 0.45
        self.previous_command = command
        if self.state == "PLAYING":
            self.fill_notes()

    def draw(self, screen):
        pygame.draw.rect(screen, settings.BOARD_COLOR, BOARD, border_radius=12)
        old_clip = screen.get_clip()
        screen.set_clip(BOARD)
        for lane in range(3):
            left = BOARD.left + round(lane * BOARD.width / 3)
            right = BOARD.left + round((lane + 1) * BOARD.width / 3)
            if lane:
                pygame.draw.line(screen, (59, 72, 94), (left, BOARD.top), (left, BOARD.bottom), 2)
            key = pygame.Rect(left + 5, HIT_Y + 14, right - left - 10, 72)
            color = settings.LANE_COLORS[lane] if self.flashes[lane] > self.elapsed else (215, 225, 237)
            pygame.draw.rect(screen, color, key, border_radius=6)
            pygame.draw.rect(screen, settings.LANE_COLORS[lane], (left + 5, HIT_Y - 8, right - left - 10, 16), 2, 4)
        pygame.draw.line(screen, settings.LINE_COLOR, (BOARD.left + 6, HIT_Y), (BOARD.right - 6, HIT_Y), 3)
        for note in self.notes:
            y = self.note_y(note)
            if BOARD.top - settings.NOTE_HEIGHT <= y <= BOARD.bottom + settings.NOTE_HEIGHT:
                rect = pygame.Rect(0, 0, settings.NOTE_WIDTH, settings.NOTE_HEIGHT)
                rect.midbottom = (LANE_CENTERS[note["lane"]], round(y))
                pygame.draw.rect(screen, settings.LANE_COLORS[note["lane"]], rect, border_radius=8)
                pygame.draw.line(screen, (240, 246, 255), (rect.left + 14, rect.top + 12),
                                 (rect.right - 14, rect.top + 12), 3)
        screen.set_clip(old_clip)
