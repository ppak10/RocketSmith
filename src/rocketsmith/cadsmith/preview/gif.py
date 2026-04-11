"""GIF renderer: rotating ASCII-art animation exported as an image GIF."""

from __future__ import annotations

from pathlib import Path


def render_step_gif(
    step_path: Path,
    output_path: Path,
    frames: int = 36,
    width: int = 120,
    height: int = 80,
    fps: int = 12,
    tolerance: float = 0.5,
) -> Path:
    """Render a rotating ASCII-art GIF of a STEP file.

    Args:
        step_path:   Path to the STEP file.
        output_path: Where to save the GIF.
        frames:      Number of rotation frames (default 36 = 10° per frame).
        width:       ASCII canvas width in characters.
        height:      ASCII canvas height in rows.
        fps:         Playback speed in frames per second.
        tolerance:   Tessellation tolerance in mm.

    Returns:
        output_path on success.
    """
    from rocketsmith.cadsmith.preview.ascii import render_step_ascii
    from PIL import Image, ImageDraw, ImageFont

    output_path.parent.mkdir(parents=True, exist_ok=True)

    images: list[Image.Image] = []
    step = 360 // frames

    for deg in range(0, 360, step):
        ascii_art = render_step_ascii(
            step_path,
            angle_deg=deg,
            width=width,
            height=height,
            wireframe=False,
            tolerance=tolerance,
        )
        lines = ascii_art.split("\n")
        char_w, char_h = 6, 10
        img_w = max(len(line) for line in lines) * char_w
        img_h = len(lines) * char_h
        img = Image.new("RGB", (img_w, img_h), (250, 250, 250))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        for i, line in enumerate(lines):
            draw.text((0, i * char_h), line, fill=(0, 0, 0), font=font)
        images.append(img)

    if images:
        duration = 1000 // fps
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0,
            optimize=True,
        )

    return output_path
