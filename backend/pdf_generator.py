from fpdf import FPDF
from PIL import Image
from xhtml2pdf import pisa
import io
import base64
from html import escape


def _safe_text(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value if item is not None)
    return str(value)


def _latin1(value):
    return _safe_text(value).encode("latin-1", "replace").decode("latin-1")


def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item not in (None, "")]
    return [value]


def _write_section(pdf, title, content=None, list_mode=False):
    if list_mode:
        items = _normalize_list(content)
        if not items:
            return
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, _latin1(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for item in items:
            pdf.multi_cell(0, 6, _latin1(f"- {item}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        return
    if not content:
        return
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, _latin1(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, _latin1(content), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

# Method A: Traditional FPDF manual typesetting
def create_manual_pdf(data, img_b64=None, enrichment=None):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_fill_color(15, 23, 42)
    pdf.rect(0, 0, 210, 297, 'F')

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 32)
    pdf.set_y(80)
    pdf.cell(0, 15, "GAME DESIGN", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 15, "SPECIFICATION", new_x="LMARGIN", new_y="NEXT", align='C')

    pdf.set_font("Helvetica", '', 20)
    pdf.ln(20)

    title = data.get('name', 'Untitled').encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align='C')

    if img_b64:
        try:
            img_data = base64.b64decode(img_b64)
            img_io = io.BytesIO(img_data)
            img = Image.open(img_io)
            pdf.image(img, x=45, y=160, w=120)
        except Exception:
            pass

    pdf.add_page()
    pdf.set_text_color(0, 0, 0)

    details = data.get("details", {}) if isinstance(data, dict) else {}
    enrichment = enrichment if isinstance(enrichment, dict) else {}

    exec_summary = enrichment.get("executive_summary") or (
        f"Genre: {data.get('name', '')}\nConcept: {details.get('release_blurb', '')}"
        if isinstance(data, dict)
        else ""
    )
    pillars = enrichment.get("pillars")
    target_audience = enrichment.get("target_audience")
    player_experience = enrichment.get("player_experience")
    key_features = enrichment.get("key_features")
    progression = enrichment.get("progression")
    content_scope = enrichment.get("content_scope")
    art_direction = enrichment.get("art_direction")
    audio_direction = enrichment.get("audio_direction")
    ui_ux = enrichment.get("ui_ux")
    accessibility = enrichment.get("accessibility")
    tech_scope = enrichment.get("tech_scope")
    production_plan = enrichment.get("production_plan")
    risks = enrichment.get("risks")
    success_metrics = enrichment.get("success_metrics")
    monetization = enrichment.get("monetization")
    live_ops = enrichment.get("live_ops")
    marketing_hooks = enrichment.get("marketing_hooks")

    storyline = details.get("storyline")
    optimized_outline = details.get("optimized_outline")
    protagonist = details.get("protagonist")
    core_loop = details.get("core_loop")
    release_blurb = details.get("release_blurb")
    reason = data.get("reason") if isinstance(data, dict) else None
    cycle = data.get("cycle") if isinstance(data, dict) else None
    full_prediction = details.get("full_game_prediction") if isinstance(details, dict) else None
    classic_refs = data.get("classic_references") if isinstance(data, dict) else None

    narrative_bits = []
    if release_blurb:
        narrative_bits.append(release_blurb)
    if protagonist:
        narrative_bits.append(f"Protagonist: {protagonist}")
    if storyline:
        narrative_bits.append(storyline)
    if optimized_outline:
        narrative_bits.append(optimized_outline)
    narrative_text = "\n".join(narrative_bits)

    experience_bits = []
    if target_audience:
        experience_bits.append(f"Target Audience: {target_audience}")
    if player_experience:
        experience_bits.append(player_experience)
    experience_text = "\n".join(experience_bits)

    scope_bits = []
    if progression:
        scope_bits.append(f"Progression: {progression}")
    if content_scope:
        scope_bits.append(f"Content Scope: {content_scope}")
    scope_text = "\n".join(scope_bits)

    art_audio_bits = []
    if art_direction:
        art_audio_bits.append(f"Art Direction: {art_direction}")
    if audio_direction:
        art_audio_bits.append(f"Audio Direction: {audio_direction}")
    art_audio_text = "\n".join(art_audio_bits)

    ui_bits = []
    if ui_ux:
        ui_bits.append(f"UI/UX: {ui_ux}")
    if accessibility:
        ui_bits.append(f"Accessibility: {accessibility}")
    ui_text = "\n".join(ui_bits)

    schedule_bits = []
    if cycle:
        schedule_bits.append(f"Initial Cycle: {cycle}")
    if isinstance(full_prediction, dict):
        if full_prediction.get("cycle"):
            schedule_bits.append(f"Projected Full Cycle: {full_prediction.get('cycle')}")
        if full_prediction.get("budget"):
            schedule_bits.append(f"Projected Budget: {full_prediction.get('budget')}")
    schedule_text = "\n".join(schedule_bits)

    ref_lines = []
    if isinstance(classic_refs, list):
        for ref in classic_refs:
            if isinstance(ref, dict):
                title = ref.get("title", "")
                url = ref.get("url", "")
                if title and url:
                    ref_lines.append(f"{title} - {url}")
                elif title:
                    ref_lines.append(title)
    if reason:
        ref_lines.insert(0, f"Market Fit: {reason}")
    refs_text = "\n".join(ref_lines)

    production_lines = []
    if isinstance(production_plan, list):
        for phase in production_plan:
            if isinstance(phase, dict):
                name = phase.get("phase") or phase.get("name") or "Phase"
                duration = phase.get("duration") or ""
                deliverables = phase.get("deliverables") or phase.get("outcomes") or ""
                parts = [str(name)]
                if duration:
                    parts.append(f"({duration})")
                if deliverables:
                    parts.append(f"- {deliverables}")
                production_lines.append(" ".join(part for part in parts if part))
            else:
                production_lines.append(str(phase))

    _write_section(pdf, "1. Executive Summary", exec_summary)
    _write_section(pdf, "2. Design Pillars", pillars, list_mode=True)
    _write_section(pdf, "3. Target Audience & Experience", experience_text)
    _write_section(pdf, "4. Narrative Overview", narrative_text)
    _write_section(pdf, "5. Core Gameplay Loop", core_loop)
    _write_section(pdf, "6. Key Features", key_features, list_mode=True)
    _write_section(pdf, "7. Progression & Content Scope", scope_text)
    _write_section(pdf, "8. Art & Audio Direction", art_audio_text)
    _write_section(pdf, "9. UI/UX & Accessibility", ui_text)
    _write_section(pdf, "10. Technical Scope", tech_scope)
    _write_section(pdf, "11. Production Plan", production_lines, list_mode=True)
    _write_section(pdf, "12. Schedule & Budget Outlook", schedule_text)
    _write_section(pdf, "13. Risks & Mitigations", risks, list_mode=True)
    _write_section(pdf, "14. Success Metrics", success_metrics, list_mode=True)
    _write_section(pdf, "15. Monetization & Live Ops", "\n".join(filter(None, [monetization, live_ops])))
    _write_section(pdf, "16. Marketing Hooks", marketing_hooks, list_mode=True)
    _write_section(pdf, "17. References & Positioning", refs_text)

    pdf_output = pdf.output()
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1')
    return bytes(pdf_output)

# Method B: HTML to PDF (AI Design Solution)
def convert_html_to_pdf(html_content):
    """
    Use xhtml2pdf to convert the HTML string generated by AI into a PDF binary stream.
    """
    pdf_output = io.BytesIO()

    try:
        pisa_status = pisa.CreatePDF(
            io.StringIO(html_content),
            dest=pdf_output
        )

        if pisa_status.err:
            print("PDF Generation Failed")
            return b""

        return pdf_output.getvalue()

    except Exception as e:
        print(f"转换异常: {e}")
        return b""

# Fallback method: Should the AI fail to generate the HTML template
def get_fallback_html(data):
    """Keep the design content available when AI layout generation fails."""
    def text(value):
        return escape(_safe_text(value)).replace("\n", "<br/>")

    details = data.get("details", {})
    sections = [
        ("Feasibility", data.get("reason")),
        ("Development Cycle", data.get("cycle")),
        ("Core Concept", details.get("release_blurb")),
        ("Design Outline", details.get("optimized_outline")),
        ("Protagonist", details.get("protagonist")),
        ("Story", details.get("storyline")),
        ("Core Gameplay Loop", details.get("core_loop")),
    ]
    content = "".join(
        f"<h2>{title}</h2><p>{text(value)}</p>"
        for title, value in sections if value
    )
    return (
        '<html><head><meta charset="utf-8"/><style>'
        'body {font-family: Helvetica; color: #333;} '
        'h1, h2 {color: #2563eb;} @page {margin: 36pt;}'
        '</style></head><body>'
        f"<h1>{text(data.get('name', 'Untitled'))}</h1>{content}</body></html>"
    )
