"""ASCII side-profile renderer for OpenRocket component trees."""

from .core import (
    BODY_TYPES,
    INTERNAL_TYPES,
    FIN_TYPES,
    SLOPE_THRESHOLD,
    get_default_width,
    fmt_mm,
)
from .nose_cone import get_nose_cone_radius_at
from .body_tube import get_body_radius_at
from .fins import draw_fins


def render_rocket_ascii(
    components: list[dict],
    width: int | None = None,
    cg_x: float | None = None,
    cp_x: float | None = None,
    max_diameter: float | None = None,
) -> str:
    """
    Render a horizontal ASCII side-profile of a rocket design with dimensions.
    """
    if width is None:
        width = get_default_width()

    # Filter components by category
    body_comps = [
        c
        for c in components
        if c["type"] in BODY_TYPES and c.get("position_x_m") is not None
    ]
    internal_comps = [
        c
        for c in components
        if c["type"] in INTERNAL_TYPES and c.get("position_x_m") is not None
    ]
    fin_comps = [
        c
        for c in components
        if c["type"] in FIN_TYPES and c.get("position_x_m") is not None
    ]

    if not body_comps:
        return "(no renderable components)"

    # Total geometric length
    all_geo = body_comps + internal_comps + fin_comps

    def get_end_x(c):
        pos = c.get("position_x_m", 0.0)
        if c["type"] in FIN_TYPES:
            root = c.get("root_chord_m", 0.0)
            sweep = c.get("sweep_m", 0.0)
            tip = c.get("tip_chord_m") or root
            return pos + max(root, sweep + tip)
        return pos + (c.get("length_m") or 0.0)

    total_length = max((get_end_x(c) for c in all_geo), default=0.0)
    if total_length <= 0:
        return "(zero-length rocket)"

    # Maximum outer body radius
    max_outer_r = 0.0
    for c in body_comps:
        length = c.get("length_m") or 0.0
        for frac in (0.0, 0.5, 1.0):
            x_m = c["position_x_m"] + frac * length
            r = get_nose_cone_radius_at(c, x_m) or get_body_radius_at(c, x_m)
            if r is not None and r > max_outer_r:
                max_outer_r = r

    if max_outer_r <= 0:
        return "(zero-diameter rocket)"

    ref_diameter = max_diameter if max_diameter is not None else (max_outer_r * 2)

    # ── Scale factors ────────────────────────────────────────────────────────
    usable_cols = width - 16
    scale_x = usable_cols / total_length
    scale_y = scale_x * 0.6

    body_half_h = max(1, round(max_outer_r * scale_y))
    if body_half_h > 15:
        ratio = 15 / body_half_h
        scale_y *= ratio
        scale_x *= ratio
        body_half_h = 15

    max_fin_span = max((c.get("span_m") or 0.0 for c in fin_comps), default=0.0)
    fin_h = round(max_fin_span * scale_y)
    centerline = fin_h + body_half_h
    total_art_rows = centerline + body_half_h + fin_h + 1

    canvas_rows = total_art_rows + 25
    canvas = [[" "] * width for _ in range(canvas_rows)]
    rocket_offset_y = 6

    def cx_to_x(cx: int) -> float:
        return (cx - 2) / scale_x

    def r_to_top(r: float) -> int:
        return rocket_offset_y + centerline - max(0, round(r * scale_y))

    def r_to_bot(r: float) -> int:
        return rocket_offset_y + centerline + max(0, round(r * scale_y))

    outer_r: list[float] = [0.0] * width
    for cx in range(2, width - 2):
        samples, best = 3, 0.0
        for s in range(samples):
            x_m = cx_to_x(cx + (s / samples) - 0.5)
            for c in body_comps:
                rv = get_nose_cone_radius_at(c, x_m) or get_body_radius_at(c, x_m)
                if rv is not None and rv > best:
                    best = rv
        outer_r[cx] = best

    slope_tol = SLOPE_THRESHOLD / scale_y

    # ── Draw airframe walls ──────────────────────────────────────────────────
    for cx in range(2, width - 2):
        r = outer_r[cx]
        if r <= 0:
            continue
        r_prev, r_next = outer_r[cx - 1], outer_r[cx + 1]
        tr, br = r_to_top(r), r_to_bot(r)
        if r > r_prev + 1e-9 and r > r_next + 1e-9:
            t_ch, b_ch = "^", "v"
        elif r < r_prev - 1e-9 and r < r_next - 1e-9:
            t_ch, b_ch = "v", "^"
        elif r > r_prev + slope_tol:
            t_ch, b_ch = "/", "\\"
        elif r < r_prev - slope_tol:
            t_ch, b_ch = "\\", "/"
        else:
            t_ch, b_ch = "-", "-"
        if cx == 2 or (cx > 2 and outer_r[cx - 1] <= 0):
            if r <= slope_tol:
                t_ch, b_ch = ">", ">"
        if 0 <= tr < canvas_rows:
            canvas[tr][cx] = t_ch
        if 0 <= br < canvas_rows:
            canvas[br][cx] = b_ch
        if cx > 2 and outer_r[cx - 1] > 0:
            ptr, pbr = r_to_top(outer_r[cx - 1]), r_to_bot(outer_r[cx - 1])
            for vr in range(min(tr, ptr) + 1, max(tr, ptr)):
                if 0 <= vr < canvas_rows:
                    canvas[vr][cx] = "|"
            for vr in range(min(br, pbr) + 1, max(br, pbr)):
                if 0 <= vr < canvas_rows:
                    canvas[vr][cx] = "|"

    # ── Tail Cap ─────────────────────────────────────────────────────────────
    tail_cx = 0
    for cx in range(width - 3, 1, -1):
        if outer_r[cx] > 0:
            tail_cx = cx
            break
    if tail_cx:
        r = outer_r[tail_cx]
        for row in range(r_to_top(r), r_to_bot(r) + 1):
            if 0 <= row < canvas_rows:
                canvas[row][tail_cx] = "|"

    # ── Internal components ──────────────────────────────────────────────────
    for c in internal_comps:
        ctype, pos, length = c["type"], c["position_x_m"], c.get("length_m") or 0.0
        cx_s, cx_e = round(2 + pos * scale_x), round(2 + (pos + length) * scale_x)
        if length <= 0 or cx_e <= cx_s:
            cx_e = cx_s + 1
        ch = ":" if ctype == "TubeCoupler" else "*" if ctype == "Parachute" else "."
        for cx in range(cx_s, cx_e + 1):
            if cx < 2 or cx >= width - 2:
                continue
            lr = outer_r[cx]
            if lr <= 0:
                continue
            od = c.get("outer_diameter_m") or c.get("diameter_m") or 0.0
            r_val = min(od / 2, lr * 0.95)
            rt, rb = r_to_top(r_val), r_to_bot(r_val)
            for vr in (rt, rb):
                if 0 <= vr < canvas_rows:
                    t_vr = vr
                    if canvas[t_vr][cx] in ("-", "/", "\\", "_", "^", "v", ">", "|"):
                        if t_vr < rocket_offset_y + centerline:
                            t_vr += 1
                        else:
                            t_vr -= 1
                    if 0 <= t_vr < canvas_rows and canvas[t_vr][cx] == " ":
                        if ch == ":" and (cx_e - cx_s) >= 4 and cx % 2 != 0:
                            continue
                        canvas[t_vr][cx] = ch

    # ── CG / CP Markers ──────────────────────────────────────────────────────
    center_y = rocket_offset_y + centerline
    if cg_x is not None:
        cx = round(2 + cg_x * scale_x)
        if 2 <= cx < width - 2:
            for i, char in enumerate("(CG)"):
                if cx - 1 + i < width:
                    canvas[center_y][cx - 1 + i] = char
    if cp_x is not None:
        cx = round(2 + cp_x * scale_x)
        if 2 <= cx < width - 2:
            for i, char in enumerate("(CP)"):
                if cx - 1 + i < width:
                    canvas[center_y][cx - 1 + i] = char

    # ── Internal Vertical Callouts (ID/OD) ────────────────────────────────────
    callout_comps = [
        c
        for c in components
        if c["type"] in ("BodyTube", "TubeCoupler", "InnerTube", "Transition")
    ]
    for c in callout_comps:
        pos, length = c["position_x_m"], c.get("length_m") or 0.0
        if length < 0.04:
            continue
        mid_x = pos + length / 2
        cx = round(2 + mid_x * scale_x)
        if cx < 5 or cx >= width - 5:
            continue
        od, id_val = c.get("outer_diameter_m") or 0.0, c.get("inner_diameter_m") or 0.0
        if od <= 0:
            continue
        ort, orb = r_to_top(od / 2), r_to_bot(od / 2)
        if orb - ort >= 3:
            canvas[ort + 1][cx] = "^"
            for vr in range(ort + 2, orb - 1):
                if canvas[vr][cx] == " ":
                    canvas[vr][cx] = "│"
            canvas[orb - 1][cx] = "v"
            od_txt = f"OD:{round(od*1000)}"
            for i, char in enumerate(od_txt):
                if cx + 2 + i < width:
                    canvas[ort + 1][cx + 2 + i] = char
            if id_val > 0:
                id_txt = f"ID:{round(id_val*1000)}"
                for i, char in enumerate(id_txt):
                    if cx + 2 + i < width:
                        canvas[ort + 2][cx + 2 + i] = char

    # ── Fins ──────────────────────────────────────────────────────────────────
    draw_fins(
        canvas,
        fin_comps,
        outer_r,
        scale_x,
        scale_y,
        fin_h,
        canvas_rows,
        centerline,
        r_to_top,
        r_to_bot,
        cx_to_x,
        width,
    )

    # ── Global Dimensional Markings ──────────────────────────────────────────
    max_cx = round(2 + total_length * scale_x)
    max_cx = min(width - 1, max_cx)
    if max_cx > 5:
        l_label = f" {total_length * 1000:.0f}mm "
        l_pos = (2 + max_cx) // 2 - len(l_label) // 2
        for cx in range(2, max_cx + 1):
            if cx == 2:
                canvas[rocket_offset_y - 2][cx] = "|"
            elif cx == max_cx:
                canvas[rocket_offset_y - 2][cx] = "|"
            elif l_pos <= cx < l_pos + len(l_label):
                canvas[rocket_offset_y - 2][cx] = l_label[cx - l_pos]
            else:
                canvas[rocket_offset_y - 2][cx] = "-"

    d_row_mid = rocket_offset_y + centerline
    d_label = f" {max_outer_r * 2000:.0f}mm "
    d_col = min(width - 12, max_cx + 2)
    if d_col < width:
        tr, br = r_to_top(max_outer_r), r_to_bot(max_outer_r)
        canvas[tr][d_col], canvas[br][d_col] = "T", "B"
        for r in range(tr + 1, br):
            if r == d_row_mid:
                canvas[r][d_col] = "+"
                for i, char in enumerate(d_label):
                    if d_col + 2 + i < width:
                        canvas[r][d_col + 2 + i] = char
            else:
                canvas[r][d_col] = "|"

    # ── Stability Info Block (Top Right) ──────────────────────────────────────
    if cg_x is not None and cp_x is not None and ref_diameter > 0:
        stability = (cp_x - cg_x) / ref_diameter
        info_lines = [
            f"Stability: {stability:.2f} cal",
            f"CG: {round(cg_x*1000)} mm",
            f"CP: {round(cp_x*1000)} mm",
        ]
        info_x = width - 25
        for row_idx, line in enumerate(info_lines):
            # Place in first 3 rows
            for i, char in enumerate(line):
                if info_x + i < width:
                    canvas[row_idx][info_x + i] = char

    # ── Segment Ruler ────────────────────────────────────────────────────────
    airframe_depth = 0
    for c in body_comps:
        if c["type"] in ("NoseCone", "BodyTube"):
            airframe_depth = c["depth"]
            break

    segments = [
        c
        for c in components
        if c["type"] in (BODY_TYPES | {"TubeCoupler"})
        and (
            c["depth"] == airframe_depth
            or (c["depth"] == airframe_depth + 1 and c["type"] == "TubeCoupler")
        )
    ]
    segments.sort(key=lambda c: (c.get("position_x_m", 0), -(c.get("length_m") or 0)))

    for idx, c in enumerate(segments):
        pos, length = c.get("position_x_m", 0.0), c.get("length_m") or 0.0
        if length <= 0:
            continue
        cx_s, cx_e = round(2 + pos * scale_x), round(2 + (pos + length) * scale_x)
        if cx_e <= cx_s + 1:
            continue
        row = (
            (rocket_offset_y + total_art_rows + 1)
            if idx % 2 == 0
            else (rocket_offset_y + total_art_rows + 3)
        )
        if row < canvas_rows:
            canvas[row][cx_s] = canvas[row][cx_e] = "|"
            l_text = fmt_mm(length)
            if cx_e - cx_s > len(l_text) + 2:
                mid, start = (cx_s + cx_e) // 2, ((cx_s + cx_e) // 2) - len(l_text) // 2
                for i, char in enumerate(l_text):
                    if 0 <= start + i < width:
                        canvas[row][start + i] = char
                for cx in range(cx_s + 1, start):
                    canvas[row][cx] = "-"
                for cx in range(start + len(l_text), cx_e):
                    canvas[row][cx] = "-"
        if row + 1 < canvas_rows:
            disp = c["name"][: cx_e - cx_s - 2]
            if disp:
                start = (cx_s + cx_e) // 2 - len(disp) // 2
                for i, char in enumerate(disp):
                    if 0 <= start + i < width:
                        canvas[row + 1][start + i] = char

    lines = ["".join(row).rstrip() for row in canvas]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    # Summary Details
    details = ["", "Component Details:", "-" * 40]
    relevant_comps = [
        c for c in components if c["type"] in (BODY_TYPES | INTERNAL_TYPES)
    ]
    for c in relevant_comps:
        ctype, name, length = c["type"], c["name"], c.get("length_m") or 0.0
        render = (
            "[>---]"
            if ctype == "NoseCone"
            else (
                "[/---\\]"
                if ctype == "Transition"
                else (
                    "[:---:]"
                    if ctype in ("InnerTube", "TubeCoupler")
                    else (
                        "[*---*]"
                        if ctype == "Parachute"
                        else (
                            "[.---.]"
                            if ctype in ("MassComponent", "ShockCord", "Streamer")
                            else "[----]"
                        )
                    )
                )
            )
        )
        dim_str = f"L: {fmt_mm(length)}"
        if ctype in ("BodyTube", "InnerTube", "TubeCoupler"):
            dim_str += f", OD: {fmt_mm(c.get('outer_diameter_m', 0))}, ID: {fmt_mm(c.get('inner_diameter_m', 0))}"
        elif ctype == "Parachute":
            dim_str += f", D: {fmt_mm(c.get('diameter_m', 0))}"
        elif ctype in ("NoseCone", "Transition"):
            dim_str += f", D: {fmt_mm(c.get('fore_diameter_m', 0))} -> {fmt_mm(c.get('aft_diameter_m', 0))}"
        elif ctype == "MassComponent":
            dim_str += f", M: {(c.get('mass_kg', 0))*1000:.0f}g"
        details.append(f"{render:<8} {name:<15} ({ctype})\n         {dim_str}\n")

    return "\n".join(lines) + "\n" + "\n".join(details)
