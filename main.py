from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import TypeVar
import itertools
import bpy
import pysubs2
from pysubs2 import Alignment, Color, SSAEvent, SSAFile, SSAStyle

_T = TypeVar("_T")


OUTPUT_PATH = bpy.path.abspath("//subs.ass")


def roundtuple(
    t: tuple[int, int, int, int], ndigits: int | None = None
) -> tuple[int, int, int, int]:
    return (
        round(t[0], ndigits),
        round(t[1], ndigits),
        round(t[2], ndigits),
        round(t[3], ndigits),
    )


def tuple2c(
    t: bpy.types.bpy_prop_array | tuple[float, float, float, float],
) -> Color:
    return Color(
        r=int(t[0] * 255),
        g=int(t[1] * 255),
        b=int(t[2] * 255),
        a=255 - int(t[3] * 255),  # Alpha is inverted???
    )


def c2bgr_hex(c: Color) -> str:
    # returns a BGR hex representation of the color. does not include the `H` prefix.
    return f"{c.b:02X}{c.g:02X}{c.r:02X}"


def item_counter(lst: Iterable[_T]) -> dict[_T, int]:
    count = defaultdict(int)
    for x in lst:
        count[x] += 1
    return count


def id_counter():
    id = -1

    def counter():
        nonlocal id
        id += 1
        return id

    return counter


@dataclass(frozen=True)
class StyleEvent:
    font_size: float
    bold: bool
    italic: bool
    alignment: pysubs2.Alignment
    color: tuple[float, float, float, float]
    shadow_color: tuple[float, float, float, float]
    shadow_size: float
    outline_color: tuple[float, float, float, float]
    outline_size: float
    start_ms: int | None = None

    def to_style_dict(self) -> dict:
        return {
            "font_size": self.font_size,
            "bold": self.bold,
            "italic": self.italic,
            "alignment": self.alignment,
            "color": self.color,
            "shadow_color": self.shadow_color,
            "shadow_size": self.shadow_size,
            "outline_color": self.outline_color,
            "outline_size": self.outline_size,
        }

    def without_start_ms(self) -> StyleEvent:
        return StyleEvent(start_ms=None, **self.to_style_dict())

    def to_ssa(self) -> SSAStyle:
        return SSAStyle(
            fontsize=self.font_size,
            bold=self.bold,
            italic=self.italic,
            alignment=self.alignment,
            primarycolor=tuple2c(self.color),
            backcolor=tuple2c(self.shadow_color),
            shadow=self.shadow_size,
        )


@dataclass(frozen=True)
class PositionEvent:
    offset_x: float
    offset_y: float
    scale_x: float
    scale_y: float
    rot: float
    start_ms: int | None = None


@dataclass(frozen=True)
class BigEvent:
    style: StyleEvent
    pos: PositionEvent

    def diff_override(
        self,
        other: BigEvent,
        screen_res: tuple[int, int],
        animated: bool,
    ) -> list[tuple[str, str] | str]:
        return list(self._diff_override(other, screen_res, animated))

    def _diff_override(
        self,
        other: BigEvent,
        screen_res: tuple[int, int],
        animated: bool,  # used for stuff like moving and rotating
    ) -> Generator[tuple[str, str] | str]:
        """Gets the string that would turn `self` into other"""
        # if self == other:
        #     return

        if self.style.bold != other.style.bold:
            yield f"\\b{int(other.style.bold)}"
        if self.style.italic != other.style.italic:
            yield f"\\i{int(other.style.italic)}"
        if self.style.alignment != other.style.alignment:
            yield f"\\an{other.style.alignment.value}"

        if self.style.color != other.style.color:
            print("self.style.color != other.style.color")
            print(self.style.color)
            print(other.style.color)
            yield (
                f"\\c&H{c2bgr_hex(tuple2c(self.style.color))}&",
                f"\\c&H{c2bgr_hex(tuple2c(other.style.color))}&",
            )
        # check if alpha has changed
        if self.style.color[-1] != other.style.color[-1]:
            yield (
                f"\\1a{tuple2c(self.style.color).a:X}",
                f"\\1a{tuple2c(other.style.color).a:X}",
            )

        if self.style.shadow_size != other.style.shadow_size:
            yield (
                f"\\shad{round(self.style.shadow_size, 2)}",
                f"\\shad{round(other.style.shadow_size, 2)}",
            )
        if other.style.shadow_size > 0:
            if self.style.shadow_color != other.style.shadow_color:
                yield (
                    f"\\4c{c2bgr_hex(tuple2c(self.style.shadow_color))}",
                    f"\\4c{c2bgr_hex(tuple2c(other.style.shadow_color))}",
                )
            if self.style.shadow_color[-1] != other.style.shadow_color[-1]:
                yield (
                    f"\\4a{tuple2c(self.style.color).a:X}",
                    f"\\4a{tuple2c(other.style.color).a:X}",
                )
        if self.style.outline_size != other.style.outline_size:
            yield (
                f"\\bord{round(self.style.outline_size, 2)}",
                f"\\bord{round(other.style.outline_size, 2)}",
            )
        if other.style.outline_size > 0:
            if self.style.outline_color != other.style.outline_color:
                yield (
                    f"\\3c{c2bgr_hex(tuple2c(self.style.outline_color))}",
                    f"\\3c{c2bgr_hex(tuple2c(other.style.outline_color))}",
                )
            if self.style.outline_color[-1] != other.style.outline_color[-1]:
                yield (
                    f"\\3a{tuple2c(self.style.color).a:X}",
                    f"\\3a{tuple2c(other.style.color).a:X}",
                )

        if other.pos.offset_x != 0 or other.pos.offset_y != 0:
            match self.style.alignment:
                case Alignment.BOTTOM_LEFT:
                    align_x = 0
                    align_y = screen_res[1]
                case Alignment.BOTTOM_CENTER:
                    align_x = screen_res[0] / 2
                    align_y = screen_res[1]
                case Alignment.BOTTOM_RIGHT:
                    align_x = screen_res[0]
                    align_y = screen_res[1]
                case Alignment.MIDDLE_LEFT:
                    align_x = 0
                    align_y = screen_res[1] / 2
                case Alignment.MIDDLE_CENTER:
                    align_x = screen_res[0] / 2
                    align_y = screen_res[1] / 2
                case Alignment.MIDDLE_RIGHT:
                    align_x = screen_res[0]
                    align_y = screen_res[1] / 2
                case Alignment.TOP_LEFT:
                    align_x = 0
                    align_y = 0
                case Alignment.TOP_CENTER:
                    align_x = screen_res[0] / 2
                    align_y = 0
                case Alignment.TOP_RIGHT:
                    align_x = screen_res[0]
                    align_y = 0

            new_coord_x = round(align_x + other.pos.offset_x)
            new_coord_y = round(align_y + other.pos.offset_y)
            yield f"\\pos({new_coord_x},{new_coord_y})"

        if self.pos.rot != other.pos.rot:
            yield (f"\\fr{self.pos.rot}", f"\\fr{other.pos.rot}")
        elif self.pos.rot != 0:
            yield f"\\fr{self.pos.rot}"

        if other.pos.scale_x != 1 or other.pos.scale_y != 1:
            yield (
                f"\\fscx{round(self.pos.scale_x * 100, 2)}\\fscy{round(self.pos.scale_y * 100)}",
                f"\\fscx{round(other.pos.scale_x * 100, 2)}\\fscy{round(self.pos.scale_y * 100)}",
            )


ALIGN_ENUM = {
    (0.0, 1.0, "TOP", "LEFT"): Alignment.TOP_LEFT,
    (0.5, 1.0, "TOP", "CENTER"): Alignment.TOP_CENTER,
    (1.0, 1.0, "TOP", "RIGHT"): Alignment.TOP_RIGHT,
    (0.0, 0.5, "CENTER", "LEFT"): Alignment.MIDDLE_LEFT,
    (0.5, 0.5, "CENTER", "CENTER"): Alignment.MIDDLE_CENTER,
    (1.0, 0.5, "CENTER", "RIGHT"): Alignment.MIDDLE_RIGHT,
    (0.0, 0.0, "BOTTOM", "LEFT"): Alignment.BOTTOM_LEFT,
    (0.5, 0.0, "BOTTOM", "CENTER"): Alignment.BOTTOM_CENTER,
    (1.0, 0.0, "BOTTOM", "RIGHT"): Alignment.BOTTOM_RIGHT,
}


def ssafile_from_events(
    text: str,
    events: list[BigEvent],
    screen_res: tuple[int, int],
    id_counter: Callable[[], int],
    ms_calculator: Callable[[int], float],
    layer=0,
) -> SSAFile:
    file = SSAFile()

    file.info.update()

    pure_styles = [e.style.without_start_ms() for e in events]

    # Get the most common style and save it as a style for easy access
    counted_styles = sorted(
        ((count, style) for style, count in item_counter(pure_styles).items()),
        key=lambda x: x[0],
    )
    most_common_style = counted_styles[-1][1]

    uid = str(id_counter())
    file.styles[uid] = most_common_style.to_ssa()

    # generate actual SSAEvents
    actual_events: list[pysubs2.SSAEvent] = []
    last_event: BigEvent | None = None
    while len(events):
        big_event = events.pop(0)
        assert big_event.style.start_ms is not None

        event = SSAEvent(
            big_event.style.start_ms,
            end=int(big_event.style.start_ms + ms_calculator(r.step)),
        )

        if last_event is None:
            actual_events.append(event)
            last_event = big_event

        override = last_event.diff_override(
            big_event,
            screen_res=screen_res,
            animated=True,
        )

        s = text
        overrides: tuple[list[str], list[str]] = ([], [])
        for o in override:
            match o:
                case (before_t, in_t):
                    overrides[0].append(before_t)
                    overrides[1].append(in_t)
                case before:
                    overrides[0].append(before)

        before = "".join(overrides[0])
        animated = "".join(overrides[1])
        if animated:
            s = f"{{{before}\\t({animated})}}{s}"
        elif before:
            s = f"{{{before}}}{s}"

        event.text = s
        # print(event)
        actual_events.append(event)
        last_event = big_event

    # remove consecutive identical events
    es = []
    for text, group in itertools.groupby(actual_events, key=lambda e: e.text):
        print(text, group)
        group = list(group)
        print(group)
        start_event = group[0]
        end_event = group[-1]

        event = SSAEvent(
            start=start_event.start,
            end=end_event.end,
            style=uid,
            layer=layer,
            text=text,
        )
        es.append(event)

    file.events = es

    return file


def events_from_strips(
    strips: list[bpy.types.TextSequence],
    r: range,
    ms_calculator: Callable[[int], float],
) -> dict[bpy.types.TextSequence, list[BigEvent]]:
    strip_ranges = {
        strip: range(
            int(max(bpy.context.scene.frame_start, strip.frame_start)),
            int(min(bpy.context.scene.frame_end, strip.frame_final_end)),
            bpy.context.scene.frame_step,
        )
        for strip in strips
    }

    # Get all the frames that are in all the ranges
    frames = sorted({frame for r in strip_ranges.values() for frame in r})

    current_frame = bpy.context.scene.frame_current
    events = defaultdict(list)
    for i in frames:
        bpy.context.scene.frame_set(i)
        frametime = round(ms_calculator(i))

        for strip in strips:
            if i in strip_ranges[strip]:
                position = strip.transform
                # fontname = "Arial"
                # if strip.font is not None:
                #     fontname = strip.font.filepath
                event = BigEvent(
                    StyleEvent(
                        start_ms=frametime,
                        font_size=strip.font_size * 2,
                        bold=strip.use_bold,
                        italic=strip.use_italic,
                        alignment=ALIGN_ENUM.get(
                            (
                                strip.location[0],
                                strip.location[1],
                                strip.align_y,
                                strip.align_x,
                            ),
                            Alignment.MIDDLE_CENTER,
                        ),
                        # color
                        color=roundtuple(tuple(strip.color), 1),  # type: ignore
                        # shadow
                        shadow_color=roundtuple(tuple(strip.shadow_color), 1),  # type: ignore
                        shadow_size=round(
                            strip.shadow_offset
                            * strip.font_size
                            * 2
                            * strip.use_shadow,
                            1,
                        ),
                        # outline
                        outline_color=roundtuple(tuple(strip.outline_color), 1),  # type: ignore
                        outline_size=round(
                            strip.outline_width
                            * strip.font_size
                            * 2
                            * strip.use_outline,
                            1,
                        ),
                    ),
                    PositionEvent(
                        start_ms=frametime,
                        offset_x=position.offset_x,
                        offset_y=-position.offset_y,
                        scale_x=round(position.scale_x, 4),
                        scale_y=round(position.scale_y, 4),
                        rot=round(math.degrees(position.rotation), 2),
                    ),
                )
                events[strip].append(event)

    # reset the frame
    bpy.context.scene.frame_set(current_frame)

    return events


fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
percent = bpy.context.scene.render.resolution_percentage
x_res = round(bpy.context.scene.render.resolution_x * (percent / 100))
y_res = round(bpy.context.scene.render.resolution_y * (percent / 100))


def calculate_ms(frame: int) -> float:
    return (frame / fps) * 1000


r = range(
    bpy.context.scene.frame_preview_start,
    bpy.context.scene.frame_preview_end,
    bpy.context.scene.frame_step,
)

file = pysubs2.SSAFile()


file.info.update(
    {
        "PlayResX": str(x_res),  # horizontal resolution
        "PlayResY": str(y_res),  # vertical resolution
    }
)

selected_strips = [
    strip
    for strip in bpy.context.selected_sequences
    if isinstance(strip, bpy.types.TextSequence)
]
print(selected_strips)

event_mapping = events_from_strips(
    selected_strips,
    r=r,
    ms_calculator=calculate_ms,
)

print(event_mapping.keys())

screen_res = (x_res, y_res)
idc = id_counter()

for strip, events in event_mapping.items():
    text = strip.text
    new_file = ssafile_from_events(
        text=text,
        events=events,
        screen_res=screen_res,
        id_counter=idc,
        ms_calculator=calculate_ms,
        layer=strip.channel,
    )

    print(new_file)
    file.import_styles(new_file)
    file.extend(new_file)

file.styles["Default"].fontsize = 100

print("Saving to ", OUTPUT_PATH)
file.save(OUTPUT_PATH)
