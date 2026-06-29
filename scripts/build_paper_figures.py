#!/usr/bin/env python3
"""Build PDF figure assets for the workshop LaTeX submission without external deps."""

from __future__ import annotations

from pathlib import Path


OUT_DIR = Path("docs/workshop_submission/figures")


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class PdfCanvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.commands: list[str] = []

    def rect(self, x: int, y: int, w: int, h: int, *, stroke: str = "0.2 0.25 0.33", fill: str = "0.97 0.98 0.99") -> None:
        self.commands.append(f"{fill} rg {stroke} RG 1.2 w {x} {y} {w} {h} re B")

    def line(self, x1: int, y1: int, x2: int, y2: int, *, stroke: str = "0.2 0.25 0.33", width: float = 1.2) -> None:
        self.commands.append(f"{stroke} RG {width} w {x1} {y1} m {x2} {y2} l S")

    def text(self, x: int, y: int, text: str, *, size: int = 10, align: str = "left") -> None:
        escaped = pdf_escape(text)
        if align == "center":
            # Helvetica average glyph width is close enough for simple figure labels.
            x -= int(len(text) * size * 0.25)
        # Set an explicit black non-stroking (fill) colour for the glyphs. Without this the
        # text inherits whatever fill colour the previous rect() set (a near-white box fill),
        # which renders the labels invisible.
        self.commands.append(f"BT 0 0 0 rg /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET")

    def write(self, path: Path) -> None:
        stream = "\n".join(self.commands).encode("utf-8")
        objects: list[bytes] = []
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width} {self.height}] "
            f"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>".encode("utf-8")
        )
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

        chunks = [b"%PDF-1.4\n"]
        offsets: list[int] = []
        for index, obj in enumerate(objects, start=1):
            offsets.append(sum(len(chunk) for chunk in chunks))
            chunks.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
        xref_offset = sum(len(chunk) for chunk in chunks)
        chunks.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets:
            chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
        chunks.append(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join(chunks))


def build_funnel(path: Path) -> None:
    c = PdfCanvas(720, 250)
    c.text(360, 222, "Three-stage evaluation funnel", size=14, align="center")
    boxes = [
        (35, 105, 120, 50, "All validated", "cases"),
        (205, 105, 125, 50, "Stage 1", "Bare Flash"),
        (380, 105, 125, 50, "Stage 2", "Bare Pro"),
        (555, 105, 125, 50, "Stage 3", "Flash + harness"),
    ]
    for x, y, w, h, a, b in boxes:
        c.rect(x, y, w, h)
        c.text(x + w // 2, y + 30, a, size=11, align="center")
        c.text(x + w // 2, y + 14, b, size=10, align="center")
    for x1, x2 in ((155, 205), (330, 380), (505, 555)):
        c.line(x1, 130, x2, 130)
        c.text((x1 + x2) // 2 - 5, 137, ">", size=10)
    c.rect(215, 35, 105, 34, stroke="0.02 0.45 0.25", fill="0.93 0.99 0.96")
    c.text(267, 49, "Solved", size=10, align="center")
    c.rect(390, 35, 105, 34, stroke="0.02 0.45 0.25", fill="0.93 0.99 0.96")
    c.text(442, 49, "Strong solves", size=10, align="center")
    c.rect(565, 35, 105, 34, stroke="0.76 0.28 0.03", fill="1 0.97 0.93")
    c.text(617, 49, "Harness lift", size=10, align="center")
    c.line(267, 105, 267, 69, stroke="0.02 0.45 0.25")
    c.line(442, 105, 442, 69, stroke="0.02 0.45 0.25")
    c.line(617, 105, 617, 69, stroke="0.76 0.28 0.03")
    c.write(path)


def build_judge_floor(path: Path) -> None:
    c = PdfCanvas(640, 300)
    c.text(320, 270, "Judge variance floor across repeated identical runs", size=14, align="center")
    c.text(320, 252, "Spread in pass counts; lower is better", size=10, align="center")
    x0, y0 = 95, 65
    c.line(x0, y0, 570, y0)
    c.line(x0, y0, x0, 220)
    data = [
        ("Single vote", 5, "18% flips", "0.98 0.57 0.24"),
        ("Majority of 3", 2, "9% flips", "0.06 0.73 0.51"),
        ("Temp 0.4", 11, "27% flips", "0.58 0.64 0.72"),
    ]
    max_value = 12
    bar_w = 72
    for i, (label, value, note, fill) in enumerate(data):
        x = 145 + i * 145
        h = int(140 * value / max_value)
        c.rect(x, y0, bar_w, h, stroke=fill, fill=fill)
        c.text(x + bar_w // 2, y0 + h + 12, str(value), size=13, align="center")
        c.text(x + bar_w // 2, 42, label, size=10, align="center")
        c.text(x + bar_w // 2, 25, note, size=9, align="center")
    for value in (0, 4, 8, 12):
        y = y0 + int(140 * value / max_value)
        c.line(x0 - 4, y, x0, y)
        c.text(65, y - 3, str(value), size=9)
    c.write(path)


def main() -> int:
    build_funnel(OUT_DIR / "figure1_three_stage_funnel.pdf")
    build_judge_floor(OUT_DIR / "figure2_judge_variance_floor.pdf")
    print(f"Wrote {OUT_DIR / 'figure1_three_stage_funnel.pdf'}")
    print(f"Wrote {OUT_DIR / 'figure2_judge_variance_floor.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
