"""Build the bilingual PDF from paper content files."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from content.p1_seq2seq import PAPER1
from content.p2_attention import PAPER2
from content.p3_scaling import PAPER3

OUTPUT = Path("/Users/calla/work/claude-sc2/paper_translation/output")
OUTPUT.mkdir(parents=True, exist_ok=True)

# Register CID CJK font
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


# ---- Styles ----
styles = getSampleStyleSheet()

CN = "STSong-Light"
EN = "Times-Roman"
EN_B = "Times-Bold"
EN_I = "Times-Italic"

TITLE = ParagraphStyle(
    "Title", parent=styles["Title"], fontName=EN_B, fontSize=18,
    leading=24, alignment=1, textColor=colors.HexColor("#0a2a52"), spaceAfter=8,
)
AUTHOR = ParagraphStyle(
    "Author", parent=styles["Normal"], fontName=EN, fontSize=10.5,
    leading=14, alignment=1, textColor=colors.HexColor("#333333"), spaceAfter=10,
)
META = ParagraphStyle(
    "Meta", parent=styles["Normal"], fontName=EN_I, fontSize=9, leading=11,
    alignment=1, textColor=colors.HexColor("#666666"), spaceAfter=14,
)
H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontName=EN_B, fontSize=14,
    leading=18, textColor=colors.HexColor("#0a2a52"), spaceBefore=10, spaceAfter=4,
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontName=EN_B, fontSize=11.5,
    leading=15, textColor=colors.HexColor("#1a3a6e"), spaceBefore=8, spaceAfter=3,
)
H3 = ParagraphStyle(
    "H3", parent=styles["Heading3"], fontName=EN_B, fontSize=10.5,
    leading=13, textColor=colors.HexColor("#1a3a6e"), spaceBefore=6, spaceAfter=2,
)

ABSTRACT_TITLE = ParagraphStyle(
    "AbstractTitle", parent=styles["Normal"], fontName=EN_B, fontSize=10,
    leading=13, alignment=1, textColor=colors.HexColor("#0a2a52"),
    spaceBefore=6, spaceAfter=4,
)
EN_P = ParagraphStyle(
    "EnP", parent=styles["Normal"], fontName=EN, fontSize=9.5, leading=12.5,
    textColor=colors.black, spaceBefore=0, spaceAfter=2, alignment=4,  # justify
)
ZH_P = ParagraphStyle(
    "ZhP", parent=styles["Normal"], fontName=CN, fontSize=10, leading=14,
    textColor=colors.HexColor("#0a2a52"), leftIndent=8, spaceBefore=0, spaceAfter=8,
    alignment=4,
)
ZH_P_ABS = ParagraphStyle(
    "ZhP_Abstract", parent=styles["Normal"], fontName=CN, fontSize=10, leading=14,
    textColor=colors.HexColor("#0a2a52"), leftIndent=8, spaceAfter=12,
    alignment=4,
)
EN_P_ABS = ParagraphStyle(
    "EnP_Abstract", parent=styles["Normal"], fontName=EN, fontSize=9.5, leading=12.5,
    textColor=colors.black, spaceAfter=2, alignment=4,
)

CAPTION = ParagraphStyle(
    "Caption", parent=styles["Normal"], fontName=EN_I, fontSize=8.5, leading=11,
    textColor=colors.HexColor("#555555"), alignment=1, spaceAfter=10,
)
MATH = ParagraphStyle(
    "Math", parent=styles["Normal"], fontName=EN_I, fontSize=9.5, leading=13,
    textColor=colors.HexColor("#222222"), leftIndent=14, spaceBefore=2, spaceAfter=6,
)
MATH_ZH = ParagraphStyle(
    "MathZh", parent=styles["Normal"], fontName=CN, fontSize=10, leading=14,
    textColor=colors.HexColor("#0a2a52"), leftIndent=22, spaceAfter=8,
)
NOTE = ParagraphStyle(
    "Note", parent=styles["Normal"], fontName=EN_I, fontSize=9, leading=11,
    textColor=colors.HexColor("#666666"), leftIndent=6, spaceBefore=2, spaceAfter=6,
)


def page_decoration(canvas, doc):
    """Draw page header and footer."""
    canvas.saveState()
    canvas.setFont(EN_I, 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(2 * cm, 1.2 * cm, "AI Papers - Bilingual Edition (EN / 中文)")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


def render_paragraph(item, first_section=False):
    """Render one content item. Returns list of flowables."""
    t = item.get("type")
    out = []
    if t == "title":
        out.append(Paragraph(item["text"], TITLE))
    elif t == "authors":
        out.append(Paragraph(item["text"], AUTHOR))
    elif t == "meta":
        out.append(Paragraph(item["text"], META))
    elif t == "h1":
        out.append(Paragraph(item["text"], H1))
    elif t == "h2":
        out.append(Paragraph(item["text"], H2))
    elif t == "h3":
        out.append(Paragraph(item["text"], H3))
    elif t == "abstract_title":
        out.append(Paragraph(item["text"], ABSTRACT_TITLE))
    elif t == "p":
        out.append(Paragraph(item["en"], EN_P))
        out.append(Paragraph(item["zh"], ZH_P))
    elif t == "p_abstract":
        out.append(Paragraph(item["en"], EN_P_ABS))
        out.append(Paragraph(item["zh"], ZH_P_ABS))
    elif t == "math":
        out.append(Paragraph(item["en"], MATH))
        if item.get("zh"):
            out.append(Paragraph(item["zh"], MATH_ZH))
    elif t == "caption":
        out.append(Paragraph(item["text"], CAPTION))
    elif t == "note":
        out.append(Paragraph(item["text"], NOTE))
    elif t == "spacer":
        out.append(Spacer(1, float(item.get("size", 6))))
    elif t == "page_break":
        out.append(PageBreak())
    elif t == "table":
        rows = item["rows"]
        # Style: header row bold, grid
        n_cols = len(rows[0]) if rows else 1
        tbl = Table(rows, colWidths=item.get("col_widths"))
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), EN),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), EN_B),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce5f1")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        out.append(tbl)
        out.append(Spacer(1, 4))
        if item.get("caption_en"):
            out.append(Paragraph(item["caption_en"], CAPTION))
        if item.get("caption_zh"):
            out.append(Paragraph(item["caption_zh"], CAPTION))
    elif t == "divider":
        out.append(Spacer(1, 4))
    else:
        # ignore unknown
        pass
    return out


def build_paper(paper_id, paper_data, output_path):
    """Build one bilingual paper PDF."""
    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title=paper_data.get("title_for_pdf", paper_id),
        author="Bilingual Edition",
    )
    flowables = []
    for item in paper_data["content"]:
        flowables.extend(render_paragraph(item))
    doc.build(flowables, onFirstPage=page_decoration, onLaterPages=page_decoration)
    print(f"Wrote {output_path}")


def build_combined(output_path):
    """Build a single combined PDF with all three papers."""
    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title="AI Classic Papers - Bilingual Edition (EN/中文)",
        author="Bilingual Edition",
    )
    flowables = []
    for paper in [PAPER1, PAPER2, PAPER3]:
        for item in paper["content"]:
            flowables.extend(render_paragraph(item))
        flowables.append(PageBreak())
    doc.build(flowables, onFirstPage=page_decoration, onLaterPages=page_decoration)
    print(f"Wrote combined {output_path}")


if __name__ == "__main__":
    # Individual PDFs
    build_paper("seq2seq", PAPER1, OUTPUT / "01_Sequence_to_Sequence_zh_en.pdf")
    build_paper("attention", PAPER2, OUTPUT / "02_Attention_Is_All_You_Need_zh_en.pdf")
    build_paper("scaling", PAPER3, OUTPUT / "03_Scaling_Laws_zh_en.pdf")
    # Combined
    build_combined(OUTPUT / "AI_Papers_Bilingual_EN_ZH.pdf")