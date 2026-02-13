from framework.display import TextScreen
from framework.text import sanitize_for_bitmap8, wrap_words

class PrestoTextScreen(TextScreen):
    def __init__(self, presto):
        self.presto = presto
        self.display = presto.display

        self.W, self.H = self.display.get_bounds()
        self.BLACK = self.display.create_pen(0, 0, 0)
        self.WHITE = self.display.create_pen(200, 200, 200)

        self.TEXT_SCALE = 1
        self.MARGIN = 10
        self.LINE_SPACING = 1  # px between lines (spec)

        self.display.set_font("bitmap8")

    def _clear(self) -> None:
        self.display.set_pen(self.BLACK)
        self.display.clear()

    def _line_height(self, scale: int) -> int:
        """
        bitmap8 is an 8px-tall font at scale=1.
        We add LINE_SPACING to match the wrap/measure spacing semantics.
        """
        return (8 * scale) + self.LINE_SPACING
    
    def status(self, msg: str) -> None:
        self._clear()
        self.display.set_pen(self.WHITE)
        self.display.text(msg, 5, 10, self.W, scale=self.TEXT_SCALE)
        self.presto.update()


    def show_text(self, text: str) -> None:
        """
        Renders a simple multi-line text screen following the kiosk layout conventions:
        - Symmetric 10px margins
        - First line treated as title at 2x scale
        - 1px line spacing
        """
        self._clear()
        self.display.set_pen(self.WHITE)

        safe_text = sanitize_for_bitmap8(text or "").rstrip("\n")
        lines = wrap_words(
            self.display,
            safe_text,
            width=self.W,
            margin=self.MARGIN,
            scale=self.TEXT_SCALE,
            spacing=self.LINE_SPACING,
        )

        x = self.MARGIN
        y = self.MARGIN
        max_y = self.H - self.MARGIN

        for index, line in enumerate(lines):
            scale = 2 * self.TEXT_SCALE if index == 0 else self.TEXT_SCALE

            # If we can't fit at least one more line, stop.
            if y + (8 * scale) > max_y:
                break

            # Match wrap measurement: uppercase rendering.
            self.display.text(line.upper(), x, y, self.W - (self.MARGIN * 2), scale)
            y += self._line_height(scale)

        self.presto.update()