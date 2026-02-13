# ICON bomb
# NAME Poetry Kiosk (POC)
# DESC Poem + photo kiosk with fades and paging

from presto import Presto

from impl.presto_screen import PrestoTextScreen
from framework.kiosk import PoetryKioskApp, KioskConfig

import random


def main() -> None:
    presto = Presto(full_res=True)

    screen = PrestoTextScreen(presto)

    cfg = KioskConfig(
        dwell_ms=30_000,
        fade_ms=2_000,
        margin_px=10,
        line_spacing_px=2,
        title_scale=4,
        body_scale=2,
        backlight_min=0,
        backlight_max=100,
        seed=None,  # Fix for debugging
        start_poem_id=None, #"/data/poems/start_poem_id.json"
        title_gap_px=8,
    )

    app = PoetryKioskApp(presto=presto, screen=screen, cfg=cfg)
    app.run()

main()
