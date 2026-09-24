from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

from app.database.models import Report
from app.search_utils import is_fallback_message


def ptext(value: str) -> str:
    return escape(str(value or ""))


def concise_text(value: str, max_words: int = 15) -> str:
    words = str(value or "").split()
    return " ".join(words[: max_words - 1] + ["..."]) if len(words) > max_words else " ".join(words)


def benchmark_price(price: str, format_name: str) -> str:
    if str(price or "").strip().lower() == "not found":
        formats = {part.strip().lower() for part in str(format_name or "").split(",")}
        return "$29 – $49 (Benchmark)" if formats.intersection({"excel", "spreadsheet"}) else "$19 – $29 (Benchmark)"
    return str(price)


def generate_pdf(report: Report, output_path: Path) -> Path:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontSize=26, leading=31, textColor=colors.HexColor("#123B5D"), alignment=TA_CENTER, spaceAfter=18))
    styles.add(ParagraphStyle(name="Subtitle", parent=styles["Normal"], fontSize=12, leading=18, textColor=colors.HexColor("#4B6475"), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontSize=18, leading=23, textColor=colors.HexColor("#123B5D"), spaceBefore=12, spaceAfter=10))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#455A64")))
    styles.add(ParagraphStyle(name="Callout", parent=styles["Normal"], fontSize=11, leading=16, backColor=colors.HexColor("#EAF4F4"), borderColor=colors.HexColor("#78A6A6"), borderWidth=0.5, borderPadding=8, spaceAfter=10))
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=.65*inch, leftMargin=.65*inch, topMargin=.6*inch, bottomMargin=.6*inch)
    reportable_evidence = [item for item in report.evidence if not item.metadata.get("error") and not is_fallback_message(item.title, item.text)]
    story = [Spacer(1, 1.1*inch), Paragraph("GLOBAL DIGITAL PRODUCT<br/>OPPORTUNITY ENGINE", styles["CoverTitle"]), Paragraph("Evidence-backed opportunity scan · Version 1.4", styles["Subtitle"]), Spacer(1, .35*inch), Paragraph(f"<b>Topic:</b> {ptext(report.topic)}<br/><b>Generated:</b> {report.created_at.strftime('%Y-%m-%d %H:%M UTC')}<br/><b>Evidence items:</b> {len(reportable_evidence)}", styles["Subtitle"]), PageBreak(), Paragraph("Executive summary", styles["Section"]), Paragraph(ptext(report.executive_summary), styles["Callout"])]
    story += [Paragraph("Objection Matrix", styles["Section"])]
    matrix_rows = [[Paragraph("Bucket", styles["Small"]), Paragraph("Observed customer objections", styles["Small"])]]
    for bucket, objections in report.objection_matrix.items():
        matrix_rows.append([Paragraph(ptext(bucket), styles["Small"]), Paragraph("<br/>".join(f"• {ptext(item)}" for item in objections) or "No explicit signals", styles["Small"])])
    matrix = Table(matrix_rows, colWidths=[1.9*inch, 4.8*inch], repeatRows=1)
    matrix.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#123B5D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#B0BEC5")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7)]))
    story += [matrix, Spacer(1, .18*inch), Paragraph("Hormozi Sales Hooks", styles["Section"])]
    for hook in report.sales_hooks:
        story.append(Paragraph(f"<b>Hook:</b> {ptext(concise_text(hook))}", styles["Callout"]))

    story += [Paragraph("Marketplace Gap Table", styles["Section"])]
    if report.marketplace_gaps:
        gap_rows = [[Paragraph(label, styles["Small"]) for label in ("Marketplace", "Product", "Price", "Format", "Rating", "Gap")]]
        for gap in report.marketplace_gaps:
            gap_rows.append([Paragraph(ptext(value), styles["Small"]) for value in (gap.marketplace, concise_text(gap.title, 15), benchmark_price(gap.price, gap.format), gap.format, gap.rating, gap.gap_signal)])
        gap_table = Table(gap_rows, colWidths=[.8*inch, 2.0*inch, .95*inch, 1.0*inch, .6*inch, 1.35*inch], repeatRows=1)
        gap_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#123B5D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#B0BEC5")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4)]))
        story.append(gap_table)
        for gap in report.marketplace_gaps[:8]:
            story.append(Paragraph(f"<b>{ptext(gap.marketplace)} review/gap notes:</b> {ptext('; '.join(gap.review_insights))}", styles["Small"]))
    else:
        story.append(Paragraph("No public Etsy or Gumroad results were available; marketplace claims should be validated manually before launch.", styles["Small"]))

    story += [Paragraph("Day-1 Deliverable Blueprint", styles["Section"])]
    blueprint = report.product_blueprint
    if blueprint:
        story.append(Paragraph(f"<b>Product:</b> {ptext(blueprint.get('product_name', ''))}<br/><b>Promise:</b> {ptext(concise_text(blueprint.get('one_sentence_promise', '')))}", styles["Callout"]))
        for module in blueprint.get("modules", []):
            story.append(Paragraph(f"<b>{ptext(module.get('name', 'Module'))}</b>: {ptext(', '.join(module.get('pages', [])))}", styles["Small"]))
        story.append(Paragraph(f"<b>Bonuses:</b> {ptext('; '.join(blueprint.get('bonuses', [])))}<br/><b>Build order:</b> {ptext(' → '.join(blueprint.get('day_one_build_order', [])))}", styles["Small"]))
    else:
        story.append(Paragraph("No blueprint was generated because no explicit opportunity was found.", styles["Small"]))

    story += [Paragraph("Launch & Marketing Kit", styles["Section"])]
    kit = report.launch_kit
    if kit:
        story.append(Paragraph(f"<b>Listing description:</b> {ptext(concise_text(kit.get('listing_description', '')))}", styles["Small"]))
        story.append(Paragraph(f"<b>SEO tags:</b> {ptext(', '.join(kit.get('seo_tags', [])))}", styles["Small"]))
        story.append(Paragraph("<b>Short-form video hooks:</b><br/>" + "<br/>".join(f"• {ptext(concise_text(hook))}" for hook in kit.get("short_form_hooks", [])), styles["Small"]))
        story.append(Paragraph(f"<b>ROI justification:</b> {ptext(kit.get('roi_justification', ''))}", styles["Small"]))
    else:
        story.append(Paragraph("No launch kit was generated because no explicit opportunity was found.", styles["Small"]))

    story += [Paragraph("Opportunity portfolio", styles["Section"])]
    for i, opp in enumerate(report.opportunities, 1):
        data = [[Paragraph(f"<b>{i}. {ptext(opp.name)}</b>", styles["Normal"]), Paragraph(f"<b>{opp.validation_score}/100</b><br/>{'Strong candidate' if opp.validation_score >= 70 else 'Needs validation'}", styles["Normal"])], [Paragraph(f"<b>Audience:</b> {ptext(opp.audience)}<br/><b>Promise:</b> {ptext(opp.promise)}<br/><b>Objection bucket:</b> {ptext(opp.objection_bucket)}", styles["Small"]), Paragraph(f"<b>Pricing:</b><br/>Starter {ptext(opp.pricing['starter'])}<br/>Core {ptext(opp.pricing['core'])}<br/>Premium {ptext(opp.pricing['premium'])}", styles["Small"])], [Paragraph(f"<b>Value hook:</b> {ptext(opp.value_hook)}<br/><b>Pricing rationale:</b> {ptext(opp.pricing_rationale)}", styles["Small"]), Paragraph("<b>Format:</b> " + ptext(", ".join(opp.format)), styles["Small"])] ]
        table = Table(data, colWidths=[5.25*inch, 1.45*inch], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#DCEAF4")), ("BOX", (0,0), (-1,-1), .7, colors.HexColor("#9BB8C8")), ("INNERGRID", (0,0), (-1,-1), .3, colors.HexColor("#C7D8E0")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
        story += [KeepTogether(table), Spacer(1, .16*inch), Paragraph("<b>Differentiation:</b> " + ptext("; ".join(opp.differentiation)), styles["Small"]), Paragraph("<b>Validation next:</b> " + ptext("; ".join(opp.next_steps)), styles["Small"]), Spacer(1, .15*inch)]
    story += [PageBreak(), Paragraph("Recurring problem signals", styles["Section"])]
    for problem in report.problems:
        story.append(Paragraph(f"<b>{ptext(concise_text(problem.problem))}</b> · {ptext(problem.objection_bucket)} · frequency {problem.frequency} · urgency {problem.urgency:.2f}<br/>Customer language: {' | '.join(ptext(concise_text(x)) for x in problem.customer_language)}", styles["Small"]))
        story.append(Spacer(1, 8))
    story += [Paragraph("Evidence appendix", styles["Section"]), Paragraph("Evidence is collected from public endpoints and should be rechecked before making a material investment. Collection failures are excluded from customer-language analysis.", styles["Small"])]
    evidence_rows = [[Paragraph("Source", styles["Small"]), Paragraph("Title / observed language", styles["Small"]), Paragraph("Link", styles["Small"])]]
    for e in reportable_evidence[:35]:
        evidence_rows.append([Paragraph(ptext(e.source), styles["Small"]), Paragraph(f"<b>{ptext(e.title)}</b><br/>{ptext(e.text[:300])}", styles["Small"]), Paragraph(f'<link href="{ptext(e.url)}">{ptext(e.url[:48])}</link>', styles["Small"])])
    table = Table(evidence_rows, colWidths=[.75*inch, 4.65*inch, 1.3*inch], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#123B5D")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#B0BEC5")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5)]))
    story.append(table)
    doc.build(story)
    return output_path
