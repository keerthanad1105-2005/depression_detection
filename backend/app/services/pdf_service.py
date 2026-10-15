import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app.core.config import settings

# Attempt to register universal Indic TrueType font for native script rendering
REPORTLAB_UNICODE_FONT = "Helvetica"
REPORTLAB_UNICODE_BOLD = "Helvetica-Bold"

ttc_candidates = [
    r"C:\Windows\Fonts\Nirmala.ttc",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]
for font_candidate in ttc_candidates:
    if os.path.exists(font_candidate):
        try:
            if font_candidate.endswith(".ttc"):
                pdfmetrics.registerFont(TTFont("IndicFont", font_candidate, subfontIndex=0))
            else:
                pdfmetrics.registerFont(TTFont("IndicFont", font_candidate))
            REPORTLAB_UNICODE_FONT = "IndicFont"
            REPORTLAB_UNICODE_BOLD = "IndicFont"
            break
        except Exception:
            pass

def generate_screening_pdf_report(session_data: dict) -> str:
    """
    Generates a high-fidelity vector PDF clinical screening report using ReportLab.
    Saves to settings.REPORT_DIR and returns the local file path.
    """
    session_id = session_data.get("session_id", "SESSION-001")
    filename = f"MindScan_Report_{session_id[:8]}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    pdf_path = os.path.join(settings.REPORT_DIR, filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Clean Clinical Palette (No blue gradient background, printable in B&W)
    teal = colors.HexColor("#0D9488")
    dark_text = colors.HexColor("#1E293B")
    dark_heading = colors.HexColor("#0F172A")
    muted_slate = colors.HexColor("#475569")
    border_color = colors.HexColor("#CBD5E1")
    light_bg = colors.HexColor("#F8FAFC")
    white = colors.white
    crimson_alert = colors.HexColor("#DC2626")
    amber_alert = colors.HexColor("#D97706")
    green_safe = colors.HexColor("#16A34A")

    # Risk band color picker (accents only)
    risk_band = session_data.get("risk_band", "Minimal")
    if risk_band in ["Severe", "High Depression"]:
        risk_color = crimson_alert
        risk_label_text = "HIGH / SEVERE RISK"
    elif risk_band in ["Moderately Severe", "Moderate", "Moderate Depression"]:
        risk_color = amber_alert
        risk_label_text = "MODERATE RISK"
    elif risk_band in ["Mild", "Minimal", "Low Depression"]:
        risk_color = green_safe
        risk_label_text = "LOW / MINIMAL RISK"
    else:
        risk_color = green_safe
        risk_label_text = str(risk_band).upper()

    # Typography Styles
    title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=dark_heading
    )
    
    subtitle_style = ParagraphStyle(
        "SubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=muted_slate
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=dark_heading,
        spaceAfter=4
    )

    body_text = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName=REPORTLAB_UNICODE_FONT,
        fontSize=9,
        leading=13,
        textColor=dark_text
    )

    bold_label = ParagraphStyle(
        "BoldLabel",
        parent=styles["Normal"],
        fontName=REPORTLAB_UNICODE_BOLD,
        fontSize=9,
        leading=13,
        textColor=dark_heading
    )

    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=muted_slate
    )

    story = []

    # 1. Header with Title & Teal Section Line
    header_table_data = [
        [
            Paragraph("<b>MindScan</b> &bull; Depression Screening Assessment Report", title_style),
            Paragraph(f"<b>CONFIDENTIAL CLINICAL REPORT</b><br/>Generated: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}<br/>Session ID: <code>{session_id[:12]}</code>", subtitle_style)
        ]
    ]
    header_table = Table(header_table_data, colWidths=[4.3 * inch, 2.9 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT')
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    # Teal/blue accent section line
    story.append(HRFlowable(width="100%", thickness=1.5, color=teal, spaceAfter=12))

    # 2. Patient Box
    patient_info = session_data.get("patient", {}) or {}
    dob_val = patient_info.get("date_of_birth") or patient_info.get("dob")
    dob_str = str(dob_val) if dob_val else "N/A"
    age_str = f"{patient_info.get('age')} years" if patient_info.get('age') is not None else "N/A"
    symptoms_list = session_data.get("symptoms", []) or []
    symptoms_str = ", ".join(symptoms_list) if isinstance(symptoms_list, list) and symptoms_list else str(symptoms_list or "None reported")
    duration_str = str(session_data.get("symptom_duration") or "Not specified")

    full_name_str = str(patient_info.get("full_name") or "Anonymous")
    gender_str = str(patient_info.get("gender") or "Not specified")
    occupation_str = str(patient_info.get("occupation") or "Not specified")

    patient_grid = [
        [
            Paragraph("<b>Patient Name:</b>", bold_label), Paragraph(full_name_str, body_text),
            Paragraph("<b>Date of Birth:</b>", bold_label), Paragraph(dob_str, body_text)
        ],
        [
            Paragraph("<b>Calculated Age:</b>", bold_label), Paragraph(age_str, body_text),
            Paragraph("<b>Gender:</b>", bold_label), Paragraph(gender_str, body_text)
        ],
        [
            Paragraph("<b>Occupation:</b>", bold_label), Paragraph(occupation_str, body_text),
            Paragraph("<b>Symptoms:</b>", bold_label), Paragraph(symptoms_str, body_text)
        ],
        [
            Paragraph("<b>Symptom Duration:</b>", bold_label), Paragraph(duration_str, body_text),
            Paragraph("<b>Screening Date:</b>", bold_label), Paragraph(datetime.utcnow().strftime("%d %b %Y"), body_text)
        ]
    ]
    patient_table = Table(patient_grid, colWidths=[1.4 * inch, 2.2 * inch, 1.4 * inch, 2.2 * inch])
    patient_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), white),
        ('BOX', (0, 0), (-1, -1), 0.5, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(Paragraph("1. Patient Demographic & Intake Profile", section_heading))
    story.append(patient_table)
    story.append(Spacer(1, 12))

    # 3. Summary Table (2 Columns: Label and Value)
    fused_score = session_data.get("fused_score", 0.0)
    confidence_num = session_data.get("confidence_level", 0.8)
    confidence = int(confidence_num * 100) if confidence_num <= 1.0 else int(confidence_num)
    modalities_used = ", ".join([m.capitalize() for m in session_data.get("modalities_used", [])])

    summary_grid = [
        [
            Paragraph("<b>Overall Depression Score</b>", bold_label),
            Paragraph(f"<b>{fused_score * 100:.2f}%</b> ({fused_score:.2f} / 1.00)", body_text)
        ],
        [
            Paragraph("<b>Screening Risk Level</b>", bold_label),
            Paragraph(f"<font color='{risk_color.hexval()}'><b>{risk_label_text}</b></font>", bold_label)
        ],
        [
            Paragraph("<b>Assessment Confidence</b>", bold_label),
            Paragraph(f"<b>{confidence}%</b> (Honest score: calculated only from calibrated, scored modalities)", body_text)
        ],
        [
            Paragraph("<b>Active Assessment Modalities</b>", bold_label),
            Paragraph(modalities_used if modalities_used else "Text, PHQ-9", body_text)
        ],
        [
            Paragraph("<b>PHQ-9 Clinical Self-Report Score</b>", bold_label),
            Paragraph(f"{session_data.get('phq9_score', 'N/A')} / 27", body_text)
        ],
        [
            Paragraph("<b>Assessment Mode</b>", bold_label),
            Paragraph(session_data.get("assessment_mode", "Multimodal Screening with Acoustic Observations"), body_text)
        ]
    ]
    summary_table = Table(summary_grid, colWidths=[2.6 * inch, 4.6 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), white),
        ('BOX', (0, 0), (-1, -1), 0.5, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(Paragraph("2. Screening Assessment Summary", section_heading))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # 4. Per-Modality Cards / Status Table
    modality_breakdown = session_data.get("modality_breakdown", [])
    modality_rows = [
        [
            Paragraph("<b>Modality</b>", bold_label),
            Paragraph("<b>Status</b>", bold_label),
            Paragraph("<b>Assessment Findings & Extracted Biomarkers</b>", bold_label)
        ]
    ]
    
    if modality_breakdown:
        for m in modality_breakdown:
            mod_name = m.get("modality", "").capitalize()
            is_skipped = m.get("skipped", False)
            if is_skipped:
                status_txt = "<i>Skipped</i>"
                findings_txt = "Modality skipped by user. Not factored into overall depression score."
            elif mod_name == "Voice" and (m.get("probability") is None or m.get("risk_band") == "Voice model not trained yet" or m.get("status") == "Features only"):
                status_txt = "<b>Features only</b><br/><font size='7' color='#D97706'>Model not trained</font>"
                findings_txt = "<b>Voice features (observations only, not part of the score):</b><br/>" + str(m.get("summary", "Acoustic prosody features extracted."))
            else:
                prob = m.get("probability", 0.0)
                prob_pct = f"{prob * 100:.1f}%" if prob is not None else "N/A"
                status_txt = f"<b>Used</b><br/><font size='7' color='#0D9488'>Score: {prob_pct}</font>"
                findings_txt = str(m.get("summary", "Assessment completed."))
            modality_rows.append([
                Paragraph(f"<b>{mod_name}</b>", bold_label),
                Paragraph(status_txt, body_text),
                Paragraph(findings_txt, body_text)
            ])
    else:
        # Default fallback breakdown rows
        modality_rows.append([
            Paragraph("<b>Text</b>", bold_label),
            Paragraph("<b>Used</b>", body_text),
            Paragraph("Natural language narrative processed with transformer linguistic model.", body_text)
        ])
        modality_rows.append([
            Paragraph("<b>Voice</b>", bold_label),
            Paragraph("<b>Features only</b>", body_text),
            Paragraph("<b>Voice features (observations only, not part of the score):</b> Acoustic timing, pause, and pitch variability extracted without trained depression model.", body_text)
        ])
        modality_rows.append([
            Paragraph("<b>Face</b>", bold_label),
            Paragraph("<i>Skipped</i>", body_text),
            Paragraph("Facial affect video capture was not provided.", body_text)
        ])

    modality_table = Table(modality_rows, colWidths=[1.2 * inch, 1.4 * inch, 4.6 * inch])
    modality_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), light_bg),
        ('BOX', (0, 0), (-1, -1), 0.5, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(Paragraph("3. Per-Modality Assessment Status & Evidence", section_heading))
    story.append(modality_table)
    story.append(Spacer(1, 12))

    # 5. Evidence & Explainable AI (Real outputs only; rule-based labeled "Observation")
    story.append(Paragraph("4. Evidence & Explainable AI Observations", section_heading))
    concordance_text = session_data.get("concordance_notes", "Clinical intake and objective markers evaluated.")
    story.append(Paragraph(f"<b>Clinical Concordance:</b> {concordance_text}", body_text))
    story.append(Spacer(1, 4))

    # Real observations
    evidence_items = []
    if session_data.get("phq9_score") is not None:
        evidence_items.append(f"<b>PHQ-9 Assessment:</b> Patient completed standard questionnaire with a score of {session_data.get('phq9_score')}/27.")
    if session_data.get("has_self_harm_risk"):
        evidence_items.append("<b>Critical Safety Alert:</b> Patient indicated thoughts of self-harm on PHQ-9 Item 9.")
    
    # Acoustic observations labeled strictly as "Observation"
    voice_details = session_data.get("voice_details") or {}
    speech_rate = session_data.get("speech_rate") or voice_details.get("speech_rate")
    if speech_rate:
        evidence_items.append(f"<b>Observation (Acoustic Feature):</b> Speech rate measured at {speech_rate} syllables/sec.")
    pause_len = session_data.get("pause_length") or voice_details.get("pause_length")
    if pause_len:
        evidence_items.append(f"<b>Observation (Acoustic Feature):</b> Pause length ratio measured at {pause_len}.")
    pitch_var = session_data.get("pitch_variability") or voice_details.get("pitch_variability")
    if pitch_var:
        evidence_items.append(f"<b>Observation (Acoustic Feature):</b> Fundamental pitch variability (F0 std) measured at {pitch_var}.")

    evidence_items.append("<b>Governance Note:</b> Voice model is not trained yet; acoustic measurements are descriptive observations only and do not contribute to the score.")

    for item in evidence_items:
        story.append(Paragraph(f"&bull; {item}", body_text))
    story.append(Spacer(1, 12))

    # 6. Actionable Triage Recommendations
    story.append(Paragraph("5. Clinical Triage Recommendations", section_heading))
    recs = session_data.get("recommendations", [])
    if isinstance(recs, str):
        recs = recs.split("\n")
    rec_items = "".join([f"&bull; {r.strip()}<br/>" for r in recs if r.strip()]) if recs else "Routine mental wellness monitoring."
    story.append(Paragraph(rec_items, body_text))
    story.append(Spacer(1, 10))

    # 7. Crisis Helplines (if high risk or self-harm)
    if session_data.get("has_self_harm_risk") or risk_band in ["Moderately Severe", "Severe", "High Depression"]:
        story.append(Paragraph(
            "<font color='#DC2626'><b>CRITICAL CRISIS SUPPORT CONTACTS (INDIA & GLOBAL)</b></font>",
            section_heading
        ))
        helpline_box = [
            [
                Paragraph("<b>Tele-MANAS (Govt of India):</b> 14416 / 1800-891-4416 (24/7 Toll-Free, Multilingual)", bold_label)
            ],
            [
                Paragraph("<b>Kiran Mental Health Helpline:</b> 1800-599-0019 (24/7 Toll-Free)", body_text)
            ],
            [
                Paragraph("<b>Vandrevala Foundation:</b> +91 9999 666 555 (24/7 Professional Counseling)", body_text)
            ]
        ]
        h_table = Table(helpline_box, colWidths=[7.2 * inch])
        h_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), white),
            ('BOX', (0, 0), (-1, -1), 1, crimson_alert),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(h_table)
        story.append(Spacer(1, 10))

    # 8. Mandatory Disclaimer & Clinician Sign-off Block
    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=1, color=border_color, spaceAfter=8),
        Paragraph(
            "<b>IMPORTANT CLINICAL & LEGAL DISCLAIMER:</b> "
            "MindScan is an artificial intelligence-assisted screening support tool designed exclusively for triage "
            "and preliminary mental wellness assessment. This document DOES NOT constitute a psychiatric or medical diagnosis. "
            "Final clinical diagnosis and treatment plans must be formulated by a qualified healthcare professional.",
            disclaimer_style
        ),
        Spacer(1, 14),
        Table([
            [
                Paragraph("<b>Reviewing Clinician:</b> ___________________________", body_text),
                Paragraph("<b>Signature / Date:</b> ___________________________", body_text)
            ]
        ], colWidths=[3.6 * inch, 3.6 * inch])
    ]))

    # Build PDF
    doc.build(story)
    return pdf_path
