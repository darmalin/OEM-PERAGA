"""The quotation as a PDF, laid out like the sales team's Excel sheet on the PNJS letterhead
(docs/EXHIBITOR_QUOTATIONS.md, decisions Q5 and Q7)."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen.canvas import Canvas

from app.modules.quotations.rules import STAND_LABELS, StandType

LETTERHEAD = Path(__file__).parent / "assets" / "letterhead.jpg"
WIDTH, HEIGHT = A4
LEFT, RIGHT = 56.0, WIDTH - 56.0
TOP = HEIGHT - 118.0  # below the letterhead's address lines
BOTTOM = 60.0
LABEL_X, COLON_X, VALUE_X = LEFT + 16, LEFT + 150, LEFT + 160
REGULAR, BOLD, ITALIC = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"
SIZE, LEADING = 10.0, 14.0
INK = (0.09, 0.09, 0.15)


def readable_image(data: bytes) -> bool:
    try:
        ImageReader(BytesIO(data)).getSize()
    except Exception:  # any decoding failure: not an image we can print
        return False
    return True


def _money(value: Decimal | str, currency: str) -> str:
    amount = Decimal(str(value))
    prefix = "Rp" if currency == "IDR" else currency
    whole = amount == amount.to_integral_value()
    text = f"{amount:,.0f}" if whole else f"{amount:,.2f}"
    return f"{prefix} {text}"


def _num(value: Decimal | str | None) -> str:
    """Sizes as people write them: 15.5, 18, 279."""
    amount = Decimal(str(value or 0)).normalize()
    return f"{amount:f}"


def _long_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _due(value: str | None) -> str:
    if not value:
        return ""
    d = date.fromisoformat(value)
    return f"{d.day} {d.strftime('%B')} {d.year}"


class _Page:
    """A cursor down the page; a new page repeats the letterhead."""

    def __init__(self, canvas: Canvas) -> None:
        self.c = canvas
        self.y = TOP
        self._letterhead()

    def _letterhead(self) -> None:
        image = ImageReader(str(LETTERHEAD))
        w, h = image.getSize()
        drawn_h = WIDTH * h / w  # full width, top aligned; the blank bottom runs off the page
        self.c.drawImage(image, 0, HEIGHT - drawn_h, WIDTH, drawn_h)
        self.c.setFillColorRGB(*INK)

    def need(self, height: float) -> None:
        if self.y - height < BOTTOM:
            self.c.showPage()
            self.y = TOP
            self._letterhead()

    def text(self, x: float, value: str, font: str = REGULAR, size: float = SIZE) -> None:
        self.c.setFont(font, size)
        self.c.drawString(x, self.y, value)

    def right(self, value: str, font: str = REGULAR) -> None:
        self.c.setFont(font, SIZE)
        self.c.drawRightString(RIGHT, self.y, value)

    def down(self, lines: float = 1) -> None:
        self.y -= LEADING * lines

    def wrapped(
        self, x: float, value: str, font: str = REGULAR, width: float | None = None
    ) -> None:
        for line in simpleSplit(value, font, SIZE, width or (RIGHT - x)):
            self.need(LEADING)
            self.text(x, line, font)
            self.down()

    def row(self, label: str, value: str, font: str = REGULAR) -> None:
        """`Label : value`, the value wrapping under itself."""
        lines = simpleSplit(value, font, SIZE, RIGHT - VALUE_X) or [""]
        self.need(LEADING * len(lines))
        if label:
            self.text(LABEL_X, label)
            self.text(COLON_X, ":")
        for line in lines:
            self.text(VALUE_X, line, font)
            self.down()


def render(q: Any, edition_name: str, signature: bytes | None) -> bytes:
    """One quotation (an ExhibitorQuotation) as PDF bytes."""
    buf = BytesIO()
    canvas = Canvas(buf, pagesize=A4)
    canvas.setTitle(f"Quotation {q.number}")
    canvas.setAuthor("PT. Peraga Nusantara Jaya Sakti")
    p = _Page(canvas)
    letter: dict[str, Any] = q.letter or {}
    cur = q.currency
    stand = StandType(q.stand_type)

    p.text(LEFT, "No")
    p.text(LEFT + 50, f":  {q.number}")
    p.right(f"{letter.get('place') or 'Jakarta'}, {_long_date(q.issued_on)}")
    p.down()
    p.text(LEFT, "Subject")
    p.text(LEFT + 50, ":  Quotation")
    p.down(2)

    p.text(LEFT, q.recipient_company.upper(), BOLD)
    p.right(f"( {STAND_LABELS[stand]} )", BOLD)
    p.down()
    for line in (q.recipient_address or "").splitlines():
        p.wrapped(LEFT, line, width=RIGHT - LEFT - 140)
    p.down()
    p.text(LEFT, f"Dear, {q.attention}," if q.attention else "Dear Sir or Madam,")
    p.down(1.5)
    event = letter.get("letter_name") or edition_name
    when = letter.get("event_text")
    intro = f"Thank you for your interest in participating our {event}"
    intro += f", which will be held on {when}." if when else "."
    p.wrapped(LEFT, intro)
    p.down(0.5)
    p.wrapped(LEFT, "Herewith, we would like to give you the best rental space cost as follow :")
    p.down(0.5)

    size = f"{_num(q.area_sqm)} sqm"
    if q.width_m and q.length_m:
        size = f"{_num(q.width_m)} m  x  {_num(q.length_m)} m  =  {size}"
    if q.booth_code:
        size += f"  (booth {q.booth_code})"
    p.row("Total space booking", size)
    if q.complimentary_sqm and Decimal(str(q.complimentary_sqm)) > 0:
        p.row(
            "Complimentary space",
            f"{_num(q.complimentary_sqm)} sqm, charged {_num(q.charged_sqm)} sqm",
        )
    if stand == StandType.SHELL:
        p.row("Shell scheme cost", f"{_money(q.stand_rate, cur)} /sqm")
        if q.includes:
            p.row("", f"(Include : {q.includes})", ITALIC)
        if q.discount_percent:
            p.row("Raw space cost", f"{_money(q.raw_rate, cur)} /sqm")
    else:
        p.row("Raw space cost", f"{_money(q.stand_rate, cur)} /sqm  (Space only)")
        if q.includes:
            p.row("", f"(Include : {q.includes})", ITALIC)
    p.down(0.5)

    charged = f"{_num(q.charged_sqm)} sqm"
    if q.discount_percent:
        pct = _num(q.discount_percent)
        p.row(q.discount_label or "Discount", f"{pct}% of raw space cost")
        p.row(
            "",
            f"({charged} x {_money(q.raw_rate, cur)}) x {pct}%"
            f"  =  {_money(q.discount_amount, cur)}",
        )
        p.down(0.5)
    space = "raw space" if stand == StandType.RAW else "shell scheme"
    basis = f"(Total space x {space})"
    p.row(
        "Cost of participant",
        f"{basis} - discount based on raw space cost" if q.discount_percent else basis,
    )
    p.row(
        "",
        f"({charged} x {_money(q.stand_rate, cur)})"
        + (f" - {_money(q.discount_amount, cur)}" if q.discount_percent else ""),
    )
    if q.discount_percent:
        p.row("", f"=  {_money(q.gross_amount, cur)} - {_money(q.discount_amount, cur)}")
    p.row("", f"=  {_money(q.cost_amount, cur)}", BOLD)
    if Decimal(str(q.vat_rate)) > 0:
        base = f"{q.vat_base_num}/{q.vat_base_den}"
        p.row(
            "VAT",
            f"[{_money(q.cost_amount, cur)} x TAX BASE {base}] x VAT {_num(q.vat_rate)}%"
            f"  =  {_money(q.vat_amount, cur)}",
        )
        p.row("Total after tax", f"=  {_money(q.total_amount, cur)}", BOLD)
    if q.notes:
        p.down(0.5)
        for line in q.notes.splitlines():
            p.row("", line)
    p.down()

    p.need(LEADING * (3 + len(q.terms)))
    p.text(LEFT, "Please find our terms of payment as per below :")
    p.down(1.5)
    cols = (LEFT + 16, LEFT + 170, LEFT + 230, LEFT + 380)
    for x, head in zip(cols, ("Terms of Payment", "%", cur, "Date"), strict=True):
        p.text(x, head, BOLD)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT + 16, p.y - 4, RIGHT, p.y - 4)
    p.down(1.3)
    for term in q.terms:
        p.text(cols[0], str(term["label"]))
        p.text(cols[1], f"{_num(term['percent'])}%")
        p.text(cols[2], _money(term["amount"], cur))
        p.text(cols[3], _due(term.get("due_on")))
        p.down()
    p.down()

    p.need(LEADING * 8)
    p.wrapped(
        LEFT,
        f"Thank you once again for your kind cooperation and continual support to {edition_name}.",
    )
    p.down()
    p.text(LEFT, "Your Faithfully,")
    p.down()
    if signature and readable_image(signature):
        image = ImageReader(BytesIO(signature))
        w, h = image.getSize()
        drawn_h = 54.0
        canvas.drawImage(image, LEFT, p.y - drawn_h, drawn_h * w / h, drawn_h, mask="auto")
    p.down(4.5)
    if letter.get("signer_name"):
        p.text(LEFT, str(letter["signer_name"]), BOLD)
        p.down()
    if letter.get("signer_title"):
        p.text(LEFT, str(letter["signer_title"]))
    canvas.showPage()
    canvas.save()
    return buf.getvalue()
