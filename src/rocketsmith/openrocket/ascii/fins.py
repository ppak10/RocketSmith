"""Fin rendering logic."""


def draw_fins(
    canvas: list[list[str]],
    fin_comps: list[dict],
    outer_r: list[float],
    scale_x: float,
    scale_y: float,
    fin_h: int,
    total_rows: int,
    centerline: int,
    r_to_top: callable,
    r_to_bot: callable,
    cx_to_x: callable,
    width: int,
):
    """Render trapezoidal fins on the canvas."""
    for c in fin_comps:
        pos = c.get("position_x_m", 0.0)
        root_chord = c.get("root_chord_m") or 0.0
        tip_chord = c.get("tip_chord_m") or root_chord
        span = c.get("span_m") or 0.0
        sweep = c.get("sweep_m") or 0.0

        if span <= 0 or root_chord <= 0:
            continue

        cx_root_leading = 1 + pos * scale_x
        cx_tip_trailing = 1 + (pos + sweep + tip_chord) * scale_x

        fin_rows = min(fin_h, max(1, round(span * scale_y)))

        start_cx = max(1, int(cx_root_leading))
        end_cx = min(width - 2, int(cx_tip_trailing))

        for cx in range(start_cx, end_cx + 1):
            x_m = cx_to_x(cx)
            br = outer_r[cx]
            if br <= 0:
                continue

            b_top = r_to_top(br)
            b_bot = r_to_bot(br)

            for fr in range(1, fin_rows + 1):
                f = fr / fin_rows
                curr_le = pos + sweep * f
                curr_te = curr_le + root_chord + (tip_chord - root_chord) * f

                if curr_le - (0.5 / scale_x) <= x_m <= curr_te + (0.5 / scale_x):
                    tr = b_top - fr
                    br2 = b_bot + fr

                    if 0 <= tr < total_rows:
                        canvas[tr][cx] = "|"
                    if 0 <= br2 < total_rows:
                        canvas[br2][cx] = "|"
