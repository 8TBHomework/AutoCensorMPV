#!/usr/bin/env python3
import os
import sys
from operator import itemgetter

import mpv
import tempfile
import time

from PIL import Image
from nudenet import NudeDetector


class OverlayManager:

    def __init__(self, player: mpv.MPV):
        self.player = player
        self.overlays: [mpv.ImageOverlay] = []
        self.to_clear = []

    def cleanup(self):
        for overlay_id, cleared in self.to_clear:
            if cleared <= time.time():
                self.player.remove_overlay(overlay_id)
                self.to_clear.remove((overlay_id, cleared))

    def next_overlay(self, clear=2) -> mpv.ImageOverlay:
        if len(self.overlays) == 0:
            self.overlays.append(player.create_image_overlay())

        o = self.overlays.pop()
        self.to_clear.append((o.overlay_id, time.time() + clear))
        return o


CENSORED_LABELS = [
    "EXPOSED_GENITALIA_F",
    "COVERED_GENITALIA_F",
    "EXPOSED_BREAST_F",
    "EXPOSED_BUTTOCKS"
]

temp_path = tempfile.mkdtemp()
detector = NudeDetector()
player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True)
overlays = OverlayManager(player)
d = {}


def store_dimension(_name, value):
    global d
    d[_name] = value


@player.property_observer('time-pos')
def time_observer(_name, value):
    if value is None or value <= 0:
        return
    overlays.cleanup()

    # osd_w is probably full window width, video is justified to be in the center, we subtract the margin here
    scale_x = (d["osd-dimensions/w"] - 2 * d["osd-dimensions/ml"]) / d["width"]
    scale_y = (d["osd-dimensions/h"] - 2 * d["osd-dimensions/mt"]) / d["height"]

    pillow_img = player.screenshot_raw()
    pillow_img.save(os.path.join(temp_path, f"frame.png"))

    results = detector.detect(os.path.join(temp_path, f"frame.png"), mode="fast")

    print(f"{value:.2f}s {list(map(itemgetter('label'), results))}")

    for detection in results:
        if detection["label"] in CENSORED_LABELS:
            x1 = detection["box"][0]
            y1 = detection["box"][1]
            x2 = detection["box"][2]
            y2 = detection["box"][3]

            box_w = x2 - x1
            box_h = y2 - y1
            pos_x = x1
            pos_y = y1

            box_sw = box_w * scale_x
            box_sh = box_h * scale_y
            pos_sx = pos_x * scale_x + d["osd-dimensions/ml"]
            pos_sy = pos_y * scale_y + d["osd-dimensions/mt"]

            img = Image.new('RGBA', (int(box_sw), int(box_sh)), (0, 0, 0, 255))
            overlays.next_overlay().update(img, (int(pos_sx), int(pos_sy)))


player['vo'] = 'gpu'

player.observe_property("osd-dimensions/mt", store_dimension)
player.observe_property("osd-dimensions/ml", store_dimension)
player.observe_property("osd-dimensions/w", store_dimension)
player.observe_property("osd-dimensions/h", store_dimension)
player.observe_property("width", store_dimension)
player.observe_property("height", store_dimension)

player.play(sys.argv[1])
player.wait_for_playback()

del player
