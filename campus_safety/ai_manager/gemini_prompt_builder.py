# FILE GUIDE: Build privacy-aware Gemini prompts for campus hazard reports.
# Redact recognizable reporter identifiers before sending free-text fields to the API.

"""Prompt construction and limited personal-information redaction for Gemini."""

from __future__ import annotations

import re

from campus_safety.domain.hazard_report import HazardReport


class GeminiPromptBuilder:
    """Build the required five-field assessment prompt without reporter identity fields.

    Redaction reduces exposure of recognizable personal details but does not
    guarantee that all identifying information has been removed.
    """

    @staticmethod
    def redact_personal_details(value: object, report: HazardReport) -> str:
        """Mask reporter identifiers, email addresses, and common SG phone formats.

        Args:
            value: Free-text hazard field to inspect.
            report: Hazard report containing reporter identifiers to redact.

        Returns:
            str: Text with recognized identifiers replaced by placeholders.
        """
        text = str(value or "")

        # Remove the reporter's name and contact when repeated in free text.
        for field in ("reporter_name", "reporter_contact"):
            identifier = str(report.get(field) or "").strip()
            if identifier:
                text = re.sub(
                    rf"(?<!\w){re.escape(identifier)}(?!\w)",
                    "[REDACTED]",
                    text,
                    flags=re.IGNORECASE,
                )

        # Mask email addresses and common Singapore phone-number formats.
        text = re.sub(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            "[REDACTED EMAIL]",
            text,
        )
        text = re.sub(
            r"(?<!\d)(?:\+65[\s-]?)?[689]\d{7}(?!\d)",
            "[REDACTED PHONE]",
            text,
        )
        return text

    @staticmethod
    def build_prompt(report: HazardReport) -> str:
        """Create the Gemini prompt with the five-field JSON schema.

        Args:
            report: Validated hazard report to assess.

        Returns:
            str: Prompt with relevant hazard details and recognized
                personal details redacted from free-text fields.
        """
        location = GeminiPromptBuilder.redact_personal_details(
            report.location, report
        )
        asset_info = GeminiPromptBuilder.redact_personal_details(
            report.asset_info, report
        )
        description = GeminiPromptBuilder.redact_personal_details(
            report.get("description"), report
        )

        # Reporter name and contact are intentionally excluded.
        return (
            "Analyze this campus safety hazard. Respond with ONLY a JSON object "
            "containing exactly these five string keys: risk_summary, category, "
            "severity, operational_impact, contextual_insights. "
            "category: Electrical, Plumbing, Structural, HVAC, IT/Equipment; "
            "severity: Low, Medium, High, Critical; operational_impact: "
            "Minor, Moderate, Severe, Catastrophic.\n"
            f"Location: {location}\n"
            f"Impact Headcount: {report.get('impact_headcount')}\n"
            f"Asset Information: {asset_info}\n"
            f"Description: {description}"
        )