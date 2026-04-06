"""
AI Engine URL Configuration

Routes:
  POST /api/audit/  — Ephemeral secret audit
"""

from django.urls import path
from .views import AuditView

urlpatterns = [
    path("", AuditView.as_view(), name="audit"),
]
