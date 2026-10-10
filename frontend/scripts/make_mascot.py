"""Generate Pip, the Pulse mascot, as Lottie JSON files.

Run: python frontend/scripts/make_mascot.py
Output: frontend/src/components/mascot/animations/*.json (all drawn here, no third-party art).
"""

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "components" / "mascot" / "animations"
SIZE = 240
FPS = 30
INK = [0.11, 0.13, 0.19, 1]
WHITE = [1, 1, 1, 1]
TEAR = [0.6, 0.82, 1, 1]
COLORS = {
    "good": [0.184, 0.62, 0.49, 1],
    "medium": [0.949, 0.757, 0.306, 1],
    "bad": [0.761, 0.255, 0.357, 1],
}
CONFETTI = [[0.184, 0.62, 0.49, 1], [0.949, 0.757, 0.306, 1], [0.761, 0.255, 0.357, 1], [0.23, 0.39, 0.72, 1]]


def static(value):
    return {"a": 0, "k": value}


def anim(frames):
    """frames: list of (t, value). Values may be numbers or lists."""
    keys = []
    for i, (t, v) in enumerate(frames):
        value = v if isinstance(v, list) else [v]
        key = {"t": t, "s": value}
        if i < len(frames) - 1:
            n = len(value)
            key["i"] = {"x": [0.42] * n, "y": [1] * n}
            key["o"] = {"x": [0.58] * n, "y": [0] * n}
        keys.append(key)
    return {"a": 1, "k": keys}


def transform(p=(0, 0), s=(100, 100), r=0, o=100):
    return {
        "ty": "tr",
        "p": p if isinstance(p, dict) else static(list(p)),
        "a": static([0, 0]),
        "s": s if isinstance(s, dict) else static(list(s)),
        "r": r if isinstance(r, dict) else static(r),
        "o": o if isinstance(o, dict) else static(o),
        "sk": static(0),
        "sa": static(0),
    }


def ellipse(size, color, *, p=(0, 0), s=(100, 100), o=100, r=0, fill_opacity=100):
    size_prop = size if isinstance(size, dict) else static(list(size))
    return {
        "ty": "gr",
        "it": [
            {"ty": "el", "p": static([0, 0]), "s": size_prop, "d": 1},
            {"ty": "fl", "c": static(color), "o": static(fill_opacity), "r": 1},
            transform(p, s, r, o),
        ],
    }


def rect(size, color, *, p=(0, 0), r=0, o=100):
    return {
        "ty": "gr",
        "it": [
            {"ty": "rc", "p": static([0, 0]), "s": static(list(size)), "r": static(2), "d": 1},
            {"ty": "fl", "c": static(color), "o": static(100), "r": 1},
            transform(p, (100, 100), r, o),
        ],
    }


def path(points, *, width=5, color=INK, closed=False, tangents=None):
    n = len(points)
    zero = [[0, 0]] * n
    ins, outs = tangents or (zero, zero)
    shape = {"i": ins, "o": outs, "v": [list(p) for p in points], "c": closed}
    return {
        "ty": "gr",
        "it": [
            {"ty": "sh", "ks": static(shape)},
            {"ty": "st", "c": static(color), "o": static(100), "w": static(width), "lc": 2, "lj": 2},
            transform(),
        ],
    }


def smile(width=30, depth=12, y=18):
    return path(
        [(-width / 2, y), (width / 2, y)],
        tangents=([[0, 0], [width / 4, depth]], [[-width / 4, depth], [0, 0]]),
    )


def frown(width=28, depth=10, y=24):
    return path(
        [(-width / 2, y), (width / 2, y)],
        tangents=([[0, 0], [width / 4, -depth]], [[-width / 4, -depth], [0, 0]]),
    )


def layer(ind, name, shapes, op, *, p=(120, 132), s=(100, 100), r=0, o=100, parent=None):
    data = {
        "ddd": 0,
        "ind": ind,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": {
            "o": o if isinstance(o, dict) else static(o),
            "r": r if isinstance(r, dict) else static(r),
            "p": p if isinstance(p, dict) else static(list(p)),
            "a": static([0, 0, 0]),
            "s": s if isinstance(s, dict) else static(list(s)),
        },
        "ao": 0,
        "shapes": shapes,
        "ip": 0,
        "op": op,
        "st": 0,
        "bm": 0,
    }
    if parent is not None:
        data["parent"] = parent
    return data


def eyes(*, height=20, pupil_x=None, pupil_scale=None):
    pupil_p = lambda dx: pupil_x(dx) if pupil_x else (dx, 3)  # noqa: E731
    return [
        ellipse((18, height), WHITE, p=(-16, -6)),
        ellipse((18, height), WHITE, p=(16, -6)),
        ellipse((8, 8), INK, p=pupil_p(-15), s=pupil_scale or (100, 100)),
        ellipse((8, 8), INK, p=pupil_p(17), s=pupil_scale or (100, 100)),
    ]


def shadow(op, s=(100, 100)):
    return layer(99, "shadow", [ellipse((110, 14), [0, 0, 0, 1], fill_opacity=12)], op, p=(120, 212), s=s)


def body(op, color, **kw):
    return layer(1, "body", [ellipse((150, 140), color)], op, **kw)


def document(name, op, layers):
    return {"v": "5.7.4", "nm": f"Pip {name}", "fr": FPS, "ip": 0, "op": op, "w": SIZE, "h": SIZE,
            "ddd": 0, "assets": [], "layers": layers}  # fmt: skip


def good():
    op = 60
    bounce = anim([(0, [120, 132]), (15, [120, 118]), (30, [120, 132]), (45, [120, 120]), (60, [120, 132])])
    squash = anim([(0, [100, 100]), (15, [97, 104]), (30, [104, 96]), (45, [98, 103]), (60, [100, 100])])
    arm = lambda side, phase: anim([  # noqa: E731
        (0, -30 * side), (15 + phase, -70 * side), (30, -30 * side), (45 + phase, -65 * side), (60, -30 * side),
    ])  # fmt: skip
    return document("good", op, [
        layer(10, "face", [smile(32, 14), *eyes()], op, p=(0, 0), parent=1),
        layer(11, "arm-l", [ellipse((14, 34), COLORS["good"], p=(0, -14))], op, p=(-70, 10), r=arm(-1, 0), parent=1),
        layer(12, "arm-r", [ellipse((14, 34), COLORS["good"], p=(0, -14))], op, p=(70, 10), r=arm(1, 3), parent=1),
        body(op, COLORS["good"], p=bounce, s=squash),
        shadow(op, anim([(0, [100, 100]), (15, [85, 85]), (30, [100, 100]), (45, [88, 88]), (60, [100, 100])])),
    ])  # fmt: skip


def medium():
    op = 90
    look = anim([(0, [-4, 3]), (20, [-4, 3]), (35, [5, 3]), (70, [5, 3]), (85, [-4, 3]), (90, [-4, 3])])
    tap = anim([(0, 0), (8, -18), (16, 0), (24, -18), (32, 0), (90, 0)])
    return document("medium", op, [
        layer(10, "face", [path([(-14, 22), (14, 18)], width=5),
                           *eyes(height=12, pupil_x=lambda dx: anim([(t, [dx + v[0], v[1]]) for t, v in
                                 [(k["t"], k["s"]) for k in look["k"]]]))],  # fmt: skip
              op, p=(0, 0), parent=1),
        layer(11, "foot", [ellipse((30, 14), COLORS["medium"])], op, p=(36, 70), r=tap, parent=1),
        layer(12, "foot-still", [ellipse((30, 14), COLORS["medium"])], op, p=(-36, 70), parent=1),
        body(op, COLORS["medium"], p=(120, 128)),
        shadow(op),
    ])  # fmt: skip


def bad():
    op = 90
    melt_s = anim([(0, [100, 100]), (45, [108, 90]), (90, [100, 100])])
    melt_p = anim([(0, [120, 134]), (45, [120, 141]), (90, [120, 134])])
    tear = lambda x, delay: layer(  # noqa: E731
        20 + delay, f"tear{delay}", [ellipse((7, 11), TEAR)], op,
        p=anim([(delay, [x, 2]), (delay + 30, [x, 40]), (delay + 31, [x, 2]), (90, [x, 2])]),
        o=anim([(delay, 100), (delay + 28, 0), (delay + 31, 0), (delay + 32, 100), (90, 100)]),
        parent=1,
    )  # fmt: skip
    return document("bad", op, [
        layer(10, "face", [frown(), *eyes(height=16, pupil_x=lambda dx: (dx, 6))], op, p=(0, 0), parent=1),
        tear(-22, 5),
        tear(22, 40),
        body(op, COLORS["bad"], p=melt_p, s=melt_s),
        shadow(op, anim([(0, [100, 100]), (45, [120, 110]), (90, [100, 100])])),
    ])  # fmt: skip


def celebrate():
    op = 50
    jump = anim([(0, [120, 132]), (10, [120, 140]), (22, [120, 78]), (36, [120, 132]), (42, [120, 136]), (50, [120, 132])])
    stretch = anim([(0, [100, 100]), (10, [110, 90]), (22, [92, 110]), (36, [108, 92]), (50, [100, 100])])
    pieces = []
    for i in range(14):
        angle = math.tau * i / 14
        dist = 95 + (i % 3) * 12
        end = [120 + math.cos(angle) * dist, 110 + math.sin(angle) * dist * 0.8]
        pieces.append(layer(
            30 + i, f"confetti{i}", [rect((8, 14), CONFETTI[i % 4])], op,
            p=anim([(12, [120, 110]), (40, end)]), r=anim([(12, 0), (40, 360 * (1 if i % 2 else -1))]),
            o=anim([(0, 0), (12, 0), (13, 100), (34, 100), (46, 0)]),
        ))  # fmt: skip
    return document("celebrate", op, [
        *pieces,
        layer(10, "face", [smile(40, 20, 14), *eyes(height=22)], op, p=(0, 0), parent=1),
        body(op, COLORS["good"], p=jump, s=stretch),
        shadow(op, anim([(0, [100, 100]), (22, [60, 60]), (36, [100, 100])])),
    ])  # fmt: skip


def gasp():
    op = 40
    shake = anim([(0, 0), (4, -6), (8, 6), (12, -5), (16, 4), (20, 0), (40, 0)])
    mouth = ellipse(anim([(0, [6, 6]), (8, [18, 24]), (40, [18, 24])]), INK, p=(0, 24))
    return document("gasp", op, [
        layer(10, "face", [mouth, *eyes(height=24, pupil_scale=anim([(0, [100, 100]), (8, [70, 70]), (40, [70, 70])]))],
              op, p=(0, 0), parent=1),  # fmt: skip
        body(op, COLORS["medium"], p=anim([(0, [120, 132]), (6, [120, 124]), (16, [120, 132])]),
             s=anim([(0, [100, 100]), (6, [94, 106]), (16, [100, 100])]), r=shake),  # fmt: skip
        shadow(op),
    ])  # fmt: skip


def fresh_start():
    op = 50
    pop = anim([(0, [0, 0]), (14, [112, 112]), (22, [96, 96]), (30, [100, 100]), (50, [100, 100])])
    blink = anim([(0, [100, 100]), (34, [100, 100]), (37, [100, 10]), (40, [100, 100]), (50, [100, 100])])
    face = [smile(32, 14), *eyes()]
    return document("fresh_start", op, [
        layer(10, "face", face, op, p=(0, 0), s=blink, parent=1),
        body(op, COLORS["good"], s=pop),
        shadow(op, pop),
    ])  # fmt: skip


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in [("good", good), ("medium", medium), ("bad", bad), ("celebrate", celebrate),
                        ("gasp", gasp), ("fresh_start", fresh_start)]:  # fmt: skip
        data = json.dumps(build(), separators=(",", ":"))
        (OUT / f"{name}.json").write_text(data)
        print(f"{name}.json  {len(data) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
