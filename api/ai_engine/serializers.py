"""
AI Engine Serializers — Audit Request Validation
"""

from rest_framework import serializers


class AuditRequestSerializer(serializers.Serializer):
    """
    Validates the incoming secret for audit analysis.
    The secret is NEVER persisted — it exists only in memory
    for the duration of the request.
    """

    secret = serializers.CharField(
        required=True,
        min_length=1,
        max_length=10000,
        help_text="The secret string to analyze. Will not be saved.",
        trim_whitespace=False,  # Preserve exact input for accurate analysis
    )
