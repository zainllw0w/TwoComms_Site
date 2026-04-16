import re

path = "twocomms/storefront/custom_print_config.py"
with open(path, "r") as f:
    orig = f.read()

tshirt_profile = """
    "tshirt": {
        "default_fit": "regular",
        "regular": {
            "front": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M80 150 C50 160 30 180 20 220 L30 320 C40 330 60 330 80 320 L100 220 L100 450 C100 480 120 490 210 490 C300 490 320 480 320 450 L320 220 L340 320 C360 330 380 330 390 320 L400 220 C390 180 370 160 340 150 L280 120 C240 140 180 140 140 120 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M100 150 C130 180 160 190 210 190 C260 190 290 180 320 150 L340 160 C320 220 320 250 320 450 C320 480 290 490 210 490 C130 490 100 480 100 450 C100 250 100 220 80 160 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M140 120 C160 150 180 160 210 160 C240 160 260 150 280 120 C260 100 160 100 140 120 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M140 120 C160 140 180 150 210 150 C240 150 260 140 280 120'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M120 470 H300'/>",
                ),
                "anchors": {
                    "front": _stage_anchor(
                        50,
                        40,
                        presets={
                            "A6": calc_iso_box("A6", body_width_mm=550, svg_body_width=220, svg_collar_y=160, top_offset_mm=210, x_center=65, radius=16),
                            "A5": calc_iso_box("A5", body_width_mm=550, svg_body_width=220, svg_collar_y=160, top_offset_mm=260, radius=18),
                            "A4": calc_iso_box("A4", body_width_mm=550, svg_body_width=220, svg_collar_y=160, top_offset_mm=280, radius=20),
                        },
                    ),
                    "sleeve_left": _stage_anchor(25, 45, modes={"a6": _stage_box(30, 48, 12, 18, 0, 16, "sleeve_patch")}),
                    "sleeve_right": _stage_anchor(75, 45, modes={"a6": _stage_box(70, 48, 12, 18, 0, 16, "sleeve_patch")})
                },
            },
            "back": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M80 150 C50 160 30 180 20 220 L30 320 C40 330 60 330 80 320 L100 220 L100 450 C100 480 120 490 210 490 C300 490 320 480 320 450 L320 220 L340 320 C360 330 380 330 390 320 L400 220 C390 180 370 160 340 150 L280 120 C240 140 180 140 140 120 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M100 150 C130 130 160 120 210 120 C260 120 290 130 320 150 L340 160 C320 220 320 250 320 450 C320 480 290 490 210 490 C130 490 100 480 100 450 C100 250 100 220 80 160 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M140 120 C160 130 180 140 210 140 C240 140 260 130 280 120 C260 100 160 100 140 120 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M140 120 C160 130 180 135 210 135 C240 135 260 130 280 120'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M120 470 H300'/>",
                ),
                "anchors": {
                    "back": _stage_anchor(
                        50,
                        40,
                        presets={
                            "A4": calc_iso_box("A4", body_width_mm=550, svg_body_width=220, svg_collar_y=135, top_offset_mm=260, radius=20),
                            "A3": calc_iso_box("A3", body_width_mm=550, svg_body_width=220, svg_collar_y=135, top_offset_mm=290, radius=21),
                            "A2": calc_iso_box("A2", body_width_mm=550, svg_body_width=220, svg_collar_y=135, top_offset_mm=320, radius=22),
                        },
                    ),
                    "sleeve_left": _stage_anchor(25, 45, modes={"a6": _stage_box(30, 48, 12, 18, 0, 16, "sleeve_patch")}),
                    "sleeve_right": _stage_anchor(75, 45, modes={"a6": _stage_box(70, 48, 12, 18, 0, 16, "sleeve_patch")})
                },
            },
        },
        "oversize": {
            "front": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M60 150 C30 160 10 180 5 220 L15 360 C25 370 45 370 65 360 L85 240 L85 450 C85 480 105 490 210 490 C315 490 335 480 335 450 L335 240 L355 360 C375 370 395 370 405 360 L415 220 C410 180 390 160 360 150 L280 120 C240 140 180 140 140 120 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M85 150 C115 180 145 190 210 190 C275 190 305 180 335 150 L355 160 C335 240 335 270 335 450 C335 480 305 490 210 490 C115 490 85 480 85 450 C85 270 85 240 65 160 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M140 120 C160 150 180 160 210 160 C240 160 260 150 280 120 C260 100 160 100 140 120 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M140 120 C160 140 180 150 210 150 C240 150 260 140 280 120'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M105 470 H315'/>",
                ),
                "anchors": {
                    "front": _stage_anchor(
                        50,
                        40,
                        presets={
                            "A6": calc_iso_box("A6", body_width_mm=600, svg_body_width=250, svg_collar_y=160, top_offset_mm=210, x_center=65, radius=16),
                            "A5": calc_iso_box("A5", body_width_mm=600, svg_body_width=250, svg_collar_y=160, top_offset_mm=260, radius=18),
                            "A4": calc_iso_box("A4", body_width_mm=600, svg_body_width=250, svg_collar_y=160, top_offset_mm=280, radius=20),
                        },
                    ),
                    "sleeve_left": _stage_anchor(20, 45, modes={"a6": _stage_box(25, 48, 12, 18, 0, 16, "sleeve_patch")}),
                    "sleeve_right": _stage_anchor(80, 45, modes={"a6": _stage_box(75, 48, 12, 18, 0, 16, "sleeve_patch")})
                },
            },
            "back": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M60 150 C30 160 10 180 5 220 L15 360 C25 370 45 370 65 360 L85 240 L85 450 C85 480 105 490 210 490 C315 490 335 480 335 450 L335 240 L355 360 C375 370 395 370 405 360 L415 220 C410 180 390 160 360 150 L280 120 C240 140 180 140 140 120 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M85 150 C115 130 145 120 210 120 C275 120 305 130 335 150 L355 160 C335 240 335 270 335 450 C335 480 305 490 210 490 C115 490 85 480 85 450 C85 270 85 240 65 160 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M140 120 C160 130 180 140 210 140 C240 140 260 130 280 120 C260 100 160 100 140 120 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M140 120 C160 130 180 135 210 135 C240 135 260 130 280 120'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M105 470 H315'/>",
                ),
                "anchors": {
                    "back": _stage_anchor(
                        50,
                        40,
                        presets={
                            "A4": calc_iso_box("A4", body_width_mm=600, svg_body_width=250, svg_collar_y=135, top_offset_mm=260, radius=20),
                            "A3": calc_iso_box("A3", body_width_mm=600, svg_body_width=250, svg_collar_y=135, top_offset_mm=290, radius=21),
                            "A2": calc_iso_box("A2", body_width_mm=600, svg_body_width=250, svg_collar_y=135, top_offset_mm=320, radius=22),
                        },
                    ),
                    "sleeve_left": _stage_anchor(20, 45, modes={"a6": _stage_box(25, 48, 12, 18, 0, 16, "sleeve_patch")}),
                    "sleeve_right": _stage_anchor(80, 45, modes={"a6": _stage_box(75, 48, 12, 18, 0, 16, "sleeve_patch")})
                },
            },
        },
    },"""

orig = orig.replace('\nSTAGE_PROFILES = {', '\nSTAGE_PROFILES = {' + tshirt_profile)

with open(path, "w") as f:
    f.write(orig)

print("done")
