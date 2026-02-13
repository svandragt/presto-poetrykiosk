# framework/kiosk.py

import time
import random
import jpegdec

from framework.text import sanitize_for_bitmap8, wrap_words
from impl.kiosk import build_playlist, load_poem

class KioskConfig:
    __slots__ = (
        "dwell_ms",
        "fade_ms",
        "margin_px",
        "line_spacing_px",
        "title_scale",
        "body_scale",
        "backlight_min",
        "backlight_max",
        "seed",
        "start_poem_id",
        "title_gap_px",
    )

    def __init__(
        self,
        *,
        dwell_ms: int,
        fade_ms: int,
        margin_px: int,
        line_spacing_px: int,
        title_scale: int,
        body_scale: int,
        backlight_min: int,
        backlight_max: int,
        seed: int | None,
        start_poem_id: str | None,
        title_gap_px: int | 6,
    ) -> None:
        self.dwell_ms = int(dwell_ms)
        self.fade_ms = int(fade_ms)
        self.margin_px = int(margin_px)
        self.line_spacing_px = int(line_spacing_px)
        self.title_scale = int(title_scale)
        self.body_scale = int(body_scale)
        self.backlight_min = int(backlight_min)
        self.backlight_max = int(backlight_max)
        self.seed = seed
        self.start_poem_id= start_poem_id
        self.title_gap_px = int(title_gap_px)

class PoetryLibrary:
    def __init__(self, *, seed=None, start_poem_id=None):
        self._seed = seed
        self._start_poem_id = start_poem_id

    def playlist(self) -> list[str]:
        ids = build_playlist("/data/poems", "/data/photos")
        if not ids:
            print('no ids found')
            return []
        random.seed(self._seed)
        shuffle_in_place(ids)
        if self._start_poem_id and self._start_poem_id in ids:
            ids.remove(self._start_poem_id)
            ids.insert(0, self._start_poem_id)
        return ids

    def load_poem(self, poem_id: str) -> dict:
        poem = load_poem(poem_id, "/data/poems")
        if poem is None:
            raise ValueError("invalid or unreadable poem JSON")
        return poem

class Transition:
    def start(self, *, direction: str) -> None:
        raise NotImplementedError

    def update(self, *, now_ms: int) -> bool:
        """Return True when finished."""
        raise NotImplementedError


class BacklightFadeTransition(Transition):
    """
    Uniform fade via backlight.
    direction: "in" or "out"
    easing: smoothstep
    """

    def __init__(self, presto, *, duration_ms: int, min_brightness: int, max_brightness: int):
        self.presto = presto
        self.duration_ms = max(1, int(duration_ms))
        self.min_b = int(min_brightness)
        self.max_b = int(max_brightness)

        self._direction = "in"
        self._t0 = 0

    def start(self, *, direction: str) -> None:
        if direction not in ("in", "out"):
            raise ValueError("direction must be 'in' or 'out'")
        self._direction = direction
        self._t0 = ticks_ms()

    def update(self, *, now_ms: int) -> bool:
        t = clamp01((now_ms - self._t0) / self.duration_ms)
        eased = smoothstep(t)

        if self._direction == "in":
            b = lerp(self.min_b, self.max_b, eased)
        else:
            b = lerp(self.max_b, self.min_b, eased)

        set_backlight_0_100(self.presto, int(b))
        return t >= 1.0


class Poetryclasss:
    """
    Filesystem-backed poem library.
    """

    def __init__(self, *, seed: int, start_poem_id=None):
        self._seed = seed
        self._start_poem_id = start_poem_id

    def playlist(self) -> list[str]:
        ids = build_playlist("/data/poems", "/data/photos")
        if not ids:
            return []

        random.seed(self._seed)
        shuffle_in_place(ids)

        if self._start_poem_id and self._start_poem_id in ids:
            ids.remove(self._start_poem_id)
            ids.insert(0, self._start_poem_id)

        return ids

    def load_poem(self, poem_id: str) -> dict:
        poem = load_poem(poem_id, "/data/poems")
        if poem is None:
            raise ValueError("invalid or unreadable poem JSON")
        return poem


class PoemPaginator:
    def __init__(self, display, *, cfg: KioskConfig):
        self.display = display
        self.cfg = cfg

    def paginate(self, *, title: str, body: str, display_w: int, display_h: int) -> dict:
        """
        Returns:
          {
            "title": <str>,
            "pages": [ [<line>, ...], [<line>, ...], ... ]
          }
        Title is shown on every page and consumes height on every page.
        Wrapping uses symmetric margins and display.measure_text.
        """

        safe_title = sanitize_for_bitmap8(title or "")
        safe_body = sanitize_for_bitmap8(body or "")

        margin = self.cfg.margin_px
        line_spacing = self.cfg.line_spacing_px

        # Wrap title as a single “line set” (usually one line).
        title_lines = wrap_words(
            self.display,
            safe_title,
            width=display_w,
            margin=margin,
            scale=self.cfg.title_scale,
            spacing=line_spacing,
        )

        # Wrap body at body scale.
        body_lines = wrap_words(
            self.display,
            safe_body,
            width=display_w,
            margin=margin,
            scale=self.cfg.body_scale,
            spacing=line_spacing,
        )

        # Compute how many body lines fit per page (pixel height based).
        usable_h = display_h - (margin * 2)

        title_h = len(title_lines) * line_height_bitmap8(self.cfg.title_scale, self.cfg.line_spacing_px)
        title_h += self.cfg.title_gap_px
        body_line_h = line_height_bitmap8(self.cfg.body_scale, line_spacing)

        body_h_per_page = max(0, usable_h - title_h)
        lines_per_page = max(1, body_h_per_page // body_line_h)

        pages: list[list[str]] = []
        for i in range(0, len(body_lines), lines_per_page):
            pages.append(body_lines[i : i + lines_per_page])

        if not pages:
            pages = [[]]

        return {"title_lines": title_lines, "pages": pages}


class PoemRenderer:
    """
    POC renderer:
      - placeholder “photo” as a dark fill
      - dim overlay behind text region (simple rectangle)
      - white text + 1px shadow
    Later: decode and draw 480x480 JPEG full screen.
    """

    def __init__(self, presto, screen, *, cfg: KioskConfig):
        self.presto = presto
        self.screen = screen
        self.display = screen.display
        self.cfg = cfg
        self._jpeg = jpegdec.JPEG(self.display)
    
        self.W, self.H = self.display.get_bounds()
        self.BLACK = self.display.create_pen(0, 0, 0)
        self.DARK = self.display.create_pen(20, 20, 20)
        self.OVERLAY = self.display.create_pen(0, 0, 0)  # use alpha later if supported
        self.WHITE = self.display.create_pen(255, 255, 255)
        self.SHADOW = self.display.create_pen(0, 0, 0)
        
        self.display.set_font("bitmap8")
        print(self.display.get_bounds())

    def draw(self, *, photo_path, title_lines, body_lines) -> None:
        W, H = self.W, self.H

        # Photo
        if photo_path:
            try:
                self._jpeg.open_file(photo_path)
                self._jpeg.decode(0, 0, jpegdec.JPEG_SCALE_FULL, dither=True)
                self._dither_dim(step=2)
            except Exception as e:
                print(f"[render] jpeg decode failed: {e}")
                self.display.set_pen(self.BLACK)
                self.display.clear()
        else:
            self.display.set_pen(self.BLACK)
            self.display.clear()

        # Dim whole background slightly (choose ONE approach)

        # A) If you confirmed alpha pens work:
        # if self._has_alpha:
        #     self.display.set_pen(self.DIM)
        #     self.display.rectangle(0, 0, W, H)

        # B) Always-works dither dim:
        self._dither_dim(step=3)

        # Text (shadow only)
        m = self.cfg.margin_px
        x = m
        y = m
        wrap_w = W - (m * 2)

        for tl in title_lines:
            self._text_shadow(tl.upper(), x, y, wrap_w, self.cfg.title_scale)
            y += line_height_bitmap8(self.cfg.title_scale, self.cfg.line_spacing_px)

        y += self.cfg.title_gap_px  # extra spacing after title

        for bl in body_lines:
            self._text_shadow(bl.upper(), x, y, wrap_w, self.cfg.body_scale)
            y += line_height_bitmap8(self.cfg.body_scale, self.cfg.line_spacing_px)

        self.presto.update()

    def _dither_dim(self, step: int = 3) -> None:
        # step=2 is heavier/darker, step=3 lighter, step=4 very light
        self.display.set_pen(self.BLACK)
        for y in range(0, self.H, step):
            for x in range((y // step) % step, self.W, step):
                self.display.pixel(x, y)


    def _text_shadow(self, s: str, x: int, y: int, w: int, scale: int) -> None:
        # 1px shadow
        self.display.set_pen(self.SHADOW)
        self.display.text(s, x + 1, y + 1, w, scale)
        self.display.set_pen(self.WHITE)
        self.display.text(s, x, y, w, scale)


class PoetryKioskApp:
    """
    State machine:
      LOAD -> FADE_IN -> DISPLAY -> FADE_OUT -> NEXT
    Touch:
      - ignored during fades
      - during DISPLAY: advance page; last page wraps to first; reset timer; prevents fade
    """

    def __init__(self, *, presto, screen, cfg: KioskConfig):
        self.presto = presto
        self.screen = screen
        self.display = screen.display
        self.cfg = cfg

        self.library = PoetryLibrary(seed=cfg.seed, start_poem_id=cfg.start_poem_id)
        self.playlist = self.library.playlist()
        self.play_index = 0

        self.transition = BacklightFadeTransition(
            presto,
            duration_ms=cfg.fade_ms,
            min_brightness=cfg.backlight_min,
            max_brightness=cfg.backlight_max,
        )

        self.paginator = PoemPaginator(self.display, cfg=cfg)
        self.renderer = PoemRenderer(presto, screen, cfg=cfg)

        self._state = "LOAD"
        self._deadline_ms = 0

        self._poem = None
        self._layout = None
        self._page_i = 0
        
        # touch
        self.touch = presto.touch
        self._touch_was_down = False
        self._last_touch_log_ms = 0
        self._touch_count = 0

    def _dbg_touch(self, now: int) -> None:
        # throttle to avoid log spam
        if now - self._last_touch_log_ms < 200:
            return
        self._last_touch_log_ms = now

        try:
            s = bool(self.touch.state)
            x = getattr(self.touch, "x", None)
            y = getattr(self.touch, "y", None)
            print(f"[touch] state={s} x={x} y={y} was={self._touch_was_down} state_machine={self._state}")
        except Exception as e:
            print(f"[touch] error reading touch: {e}")

        
    def _touch_event(self) -> bool:
        self.touch.poll()
        down = bool(self.touch.state)
        fired = down and not self._touch_was_down
        self._touch_was_down = down
        print('touched')
        return fired

    def run(self) -> None:
        if not self.playlist:
            self._show_empty_library()
            while True:
                time.sleep(1)

        # Start with black backlight
        set_backlight_0_100(self.presto, self.cfg.backlight_min)

        while True:
            now = ticks_ms()

            if self._state == "LOAD":
                set_backlight_0_100(self.presto, self.cfg.backlight_min)  # ensure still black
                self._load_current()
                self._render_current_page() # renders while black
                self._state = "FADE_IN"
                self.transition.start(direction="in")
                continue

            if self._state == "FADE_IN":
                if self.transition.update(now_ms=now):
                    # Start dwell timer when fade-in completes
                    self._deadline_ms = now + self.cfg.dwell_ms
                    self._state = "DISPLAY"
                continue

            if self._state == "DISPLAY":
                # debugging touch: self._dbg_touch(now)

                if self._touch_event():
                    self._page_advance_wrap()
                    self._deadline_ms = now + self.cfg.dwell_ms  # resets timer; prevents fade
                    self._render_current_page()

                if now >= self._deadline_ms:
                    self._state = "FADE_OUT"
                    self.transition.start(direction="out")
                continue

            if self._state == "FADE_OUT":
                # ignore touches while fading
                if self.transition.update(now_ms=now):
                    self._next_poem()
                    self._state = "LOAD"
                continue

    def _load_current(self) -> None:
        poem_id = self.playlist[self.play_index]
        try:
            poem = self.library.load_poem(poem_id)
            title = poem.get("title", "")
            body = poem.get("body", "")
            if not isinstance(title, str) or not isinstance(body, str):
                raise ValueError("title/body must be strings")

            layout = self.paginator.paginate(
                title=title,
                body=body,
                display_w=self.display.get_bounds()[0],
                display_h=self.display.get_bounds()[1],
            )

            self._poem = poem
            self._layout = layout
            self._page_i = 0

        except Exception as e:
            print(f"[kiosk] skipping poem '{poem_id}': {e}")
            self._next_poem()
            # stay in LOAD; next loop will try again

    def _render_current_page(self) -> None:
        if not self._layout or not self._poem:
            return

        title_lines = self._layout["title_lines"]
        pages = self._layout["pages"]
        page = pages[self._page_i]

        poem_id = self.playlist[self.play_index]
        photo_path = f"/data/photos/{poem_id}.jpg"  # spec: derived from id

        self.renderer.draw(
            photo_path=photo_path,
            title_lines=title_lines,
            body_lines=page,
        )


    def _page_advance_wrap(self) -> None:
        pages = self._layout["pages"]
        self._page_i = (self._page_i + 1) % len(pages)

    def _next_poem(self) -> None:
        self.play_index += 1
        if self.play_index >= len(self.playlist):
            self.play_index = 0  # repeat same order

    def _touch_event(self) -> bool:
        self.touch.poll()
        down = bool(self.touch.state)
        fired = down and not self._touch_was_down
        self._touch_was_down = down
        if fired:
            self._touch_count += 1
            print(f"[touch] TAP #{self._touch_count} x={self.touch.x} y={self.touch.y}")
        return fired


    def _show_empty_library(self) -> None:
        set_backlight_0_100(self.presto, self.cfg.backlight_max)
        self.screen.status("No valid poems.\nAdd /data/poems/*.json\nand /data/photos/<id>.jpg")


# ---- small utils ----

def ticks_ms() -> int:
    try:
        return time.ticks_ms()
    except AttributeError:
        # fallback for CPython testing
        return int(time.time() * 1000)


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def smoothstep(t: float) -> float:
    # 3t^2 - 2t^3
    return t * t * (3.0 - 2.0 * t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def line_height_bitmap8(scale: int, spacing_px: int) -> int:
    return (8 * int(scale)) + int(spacing_px)


def set_backlight_0_100(presto, value: int) -> None:
    v = max(0, min(100, int(value)))
    presto.set_backlight(v / 100.0)

def shuffle_in_place(items: list) -> None:
    """
    Fisher–Yates shuffle.
    MicroPython-compatible replacement for random.shuffle().
    """
    n = len(items)
    for i in range(n - 1, 0, -1):
        j = random.randrange(i + 1)
        items[i], items[j] = items[j], items[i]
