# ==============================================================================
# CLASS SUMMARY: InputValidator
# ==============================================================================
# Purpose:
# Provides a collection of static, pure validation functions designed to verify 
# user-submitted data fields for incident and hazard reporting systems.
#
# Key Features:
# 1. Name Validation: Ensures names only contain valid typography (alphabets, 
#    spaces, quotes, hyphens, percent signs, and periods).
# 2. Contact Verification: Validates official SIT email addresses or standard 
#    local 8-digit phone numbers starting with 6, 8, or 9.
# 3. Location & Headcount Checks: Validates non-empty location strings and ensures 
#    headcounts represent whole numbers within a safe capacity range (1 to 1000).
# 4. Text Length Constraints: Enforces minimum character length requirements 
#    for asset identifiers (5+ chars) and hazard descriptions (15+ chars).
# ==============================================================================

from __future__ import annotations
import re

class InputValidator:
    """Provides pure validation functions for user-submitted hazard report data."""

    # This function validates personal or entity names to ensure they only contain permitted typographic 
    # characters (alphabets, spaces, quotes, hyphens, percent signs, or periods).
    @staticmethod
    def validate_name(name: str) -> bool:
        """Check if name contains only alphabets, spaces, quotes, hyphens, or periods."""
        # Ensure the entire string matches allowed typographic characters for proper names
        return bool(re.fullmatch(r"[A-Za-z\s'.-]+", name))

    # This function validates contact information to ensure it is either a valid SIT email address or 
    # an 8-digit phone number starting with 6, 8, or 9.
    @staticmethod
    def validate_contact(contact: str) -> bool:
        """Check if contact is a valid SIT email or 8-digit phone number."""
        return bool(
            # Validate official university email format ending in sit.singaporetech.edu.sg (case-insensitive)
            re.fullmatch(r"[A-Za-z0-9]+@sit\.singaporetech\.edu\.sg", contact, re.I)
            # Or validate a standard Singapore 8-digit phone number starting with 6, 8, or 9
            or re.fullmatch(r"[689]\d{7}", contact)
        )
    
    # Strip whitespace and convert the resulting string to a boolean.
    # An empty string "" becomes False; a non-empty string becomes True.
    @staticmethod
    def validate_location(location: str) -> bool:
        """Check if location string is not empty or just whitespace."""
        return bool(location.strip())

    # This function ensures that a headcount string input represents a valid whole number within a logical capacity range.
    # Check if the string contains only digits, then convert it to an integer
    # to verify it falls strictly within the 1 to 1000 range.
    @staticmethod
    def validate_headcount(value: str) -> bool:
        """Check if headcount string is a whole number between 1 and 1000."""
        return value.isdigit() and 1 <= int(value) <= 1000

    # This method checks whether a user-submitted asset name is valid by ensuring it meets a minimum length requirement of at least 5 meaningful characters.
    @staticmethod
    # Returns True or False: It evaluates to True if the asset identifier is valid, and False if it's too short.
    def validate_asset(asset: str) -> bool:
        """Check if the asset name has at least 5 non-whitespace characters."""
        # Strip whitespace to prevent padding exploitation and enforce minimum length constraint (>= 5)
        return len(asset.strip()) >= 5

    # This method ensures that the hazard description meets a minimum length requirement of at least 15 meaningful characters.
    @staticmethod
    def validate_description(desc: str) -> bool:
        """Check if the hazard description has at least 15 non-whitespace characters."""
        # Strip whitespace and enforce a minimum detail threshold (>= 15 characters) for incident logs
        return len(desc.strip()) >= 15