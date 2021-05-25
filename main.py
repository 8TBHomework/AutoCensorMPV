#!/usr/bin/env python3
import argparse
import os
import sys
import tempfile
import time
from operator import itemgetter

import mpv
from PIL import Image
from nudenet import NudeDetector

CENSORED_LABELS = [
    "EXPOSED_GENITALIA_F",
    "COVERED_GENITALIA_F",
    "EXPOSED_BREAST_F",
    "EXPOSED_BUTTOCKS"
]


class OverlayManager:

    def __init__(self, player: mpv.MPV):
        self.player = player
        self.to_clear: [mpv.ImageOverlay] = []

    def cleanup(self):
        """
        Run periodically to actually remove expired overlays
        """
        for overlay_id, cleared in self.to_clear:
            if cleared <= time.time():
                self.player.remove_overlay(overlay_id)
                self.to_clear.remove((overlay_id, cleared))

    def next_overlay(self, expire_in=2) -> mpv.ImageOverlay:
        """
        Returns a fresh overlay to draw onto.
        :param expire_in: When should the overlay be deleted again (seconds from now)
        :return: fresh overlay
        """

        o = self.player.create_image_overlay()
        self.to_clear.append((o.overlay_id, time.time() + expire_in))
        return o


class AutoCensor:
    def __init__(self, temp_path: str, model_name="default", censored_labels=None, **kwargs):
        if censored_labels is None:
            censored_labels = CENSORED_LABELS

        self.temp_path = temp_path
        self.censored_labels = censored_labels
        self.detector = NudeDetector(model_name)
        self.player = mpv.MPV(**kwargs)
        self.overlays = OverlayManager(self.player)
        self.props = {}  # dict of property values used later

        self.player.observe_property("osd-dimensions/mt", self.store_prop)
        self.player.observe_property("osd-dimensions/ml", self.store_prop)
        self.player.observe_property("osd-dimensions/w", self.store_prop)
        self.player.observe_property("osd-dimensions/h", self.store_prop)
        self.player.observe_property("width", self.store_prop)
        self.player.observe_property("height", self.store_prop)

        self.player.observe_property("time-pos", self.work)

    def store_prop(self, name, value):
        self.props[name] = value

    def work(self, _, value):  # time-pos observer
        if value is None or value <= 0:
            return
        self.overlays.cleanup()

        # osd_w is probably full window width, video is justified to be in the center, we subtract the margin here
        scale_x = (self.props["osd-dimensions/w"] - 2 * self.props["osd-dimensions/ml"]) / self.props["width"]
        scale_y = (self.props["osd-dimensions/h"] - 2 * self.props["osd-dimensions/mt"]) / self.props["height"]

        frame_file = os.path.join(self.temp_path, f"frame.png")

        pillow_img = self.player.screenshot_raw()
        pillow_img.save(frame_file)

        results = self.detector.detect(frame_file, mode="fast")

        print(f"{value:.2f}s {list(map(itemgetter('label'), results))}")

        for detection in results:
            if detection["label"] in self.censored_labels:
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
                pos_sx = pos_x * scale_x + self.props["osd-dimensions/ml"]
                pos_sy = pos_y * scale_y + self.props["osd-dimensions/mt"]

                img = Image.new('RGBA', (int(box_sw), int(box_sh)), (0, 0, 0, 255))
                self.overlays.next_overlay().update(img, (int(pos_sx), int(pos_sy)))


def play(args):
    with tempfile.TemporaryDirectory(prefix="autocensor") as temp_dir:
        ac = AutoCensor(temp_dir, args.model, args.censor, input_default_bindings=True, input_vo_keyboard=True)
        ac.player['vo'] = 'gpu'
        ac.player.play(args.path)
        ac.player.wait_for_playback()


def info(args):
    if args.labels:
        print("Available labels")
        for label in NudeDetector(args.model).classes:
            print(label)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", default="default", help="Which Nudenet model to use")
    subparsers = parser.add_subparsers()

    play_parser = subparsers.add_parser("play")
    play_parser.add_argument("-c", "--censor", action="append", default=None, help="List of labels to censor")
    play_parser.add_argument("path", type=str, help="Path or URL to play")
    play_parser.set_defaults(func=play)

    info_parser = subparsers.add_parser("info")
    info_parser.add_argument("-l", "--labels", action="store_true", help="Output a list of available labels")
    info_parser.set_defaults(func=info)

    parsed = parser.parse_args()
    parsed.func(parsed)
