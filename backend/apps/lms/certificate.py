"""Сертификаты о прохождении курса (SPEC §7.4, Фаза 4 #38).

- ``issue_certificate``: создать/вернуть сертификат при завершении курса;
- ``generate_certificate_pdf``: сгенерировать PDF в фирменном стиле.

Фирменный стиль — BRANDBOOK §10.1: цвета из §3.1, шрифт (fallback Helvetica,
т.к. reportlab не поддерживает Ubuntu напрямую без встраивания).
"""

from __future__ import annotations

import io
import uuid
from typing import TYPE_CHECKING

from .models import Certificate

if TYPE_CHECKING:
    from .models import Enrollment

# Фирменные цвета из BRANDBOOK §3.1 (RGB 0-1 для reportlab).
_PRIMARY_RGB = (0.231, 0.357, 0.863)  # #3B5BDB
_ACCENT_RGB = (0.071, 0.722, 0.525)  # #12B886
_TEXT_RGB = (0.102, 0.114, 0.137)  # #1A1D23


def issue_certificate(enrollment: Enrollment) -> Certificate:
    """Создать или вернуть существующий сертификат для завершённого курса.

    Идемпотентно: один сертификат на Enrollment (OneToOne).
    """
    existing = Certificate.objects.filter(enrollment=enrollment).first()
    if existing is not None:
        return existing

    employee = enrollment.employee
    full_name = employee.full_name
    return Certificate.objects.create(
        enrollment=enrollment,
        code=uuid.uuid4().hex[:16].upper(),
        employee_full_name=full_name,
        course_title=enrollment.course.title,
    )


def generate_certificate_pdf(enrollment: Enrollment) -> bytes:
    """Сгенерировать PDF-сертификат в фирменном стиле (SPEC §7.4, #38).

    Возвращает байты PDF. Сертификат должен быть выдан (issue_certificate).
    """
    from reportlab.lib.pagesizes import A4, landscape  # type: ignore[import-untyped]
    from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

    cert = issue_certificate(enrollment)
    buffer = io.BytesIO()
    page_size = landscape(A4)
    width, height = page_size
    c = canvas.Canvas(buffer, pagesize=page_size)

    # Рамка (фирменный цвет Primary, BRANDBOOK §3.1).
    c.setStrokeColorRGB(*_PRIMARY_RGB)
    c.setLineWidth(3)
    c.rect(30, 30, width - 60, height - 60)

    # Акцентная полоса (Accent — мятный рост, BRANDBOOK §3.1).
    c.setFillColorRGB(*_ACCENT_RGB)
    c.rect(30, height - 90, width - 60, 8, fill=1, stroke=0)

    # Заголовок.
    c.setFillColorRGB(*_PRIMARY_RGB)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height - 160, "Сертификат")

    c.setFillColorRGB(*_TEXT_RGB)
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 195, "подтверждает успешное прохождение курса")

    # ФИО сотрудника.
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 260, cert.employee_full_name)

    # Название курса.
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 300, f"«{cert.course_title}»")

    # Дата и код.
    c.setFont("Helvetica", 11)
    issued_date = cert.issued_at.strftime("%d.%m.%Y") if cert.issued_at else ""
    c.drawString(60, 70, f"Дата: {issued_date}")
    c.drawRightString(width - 60, 70, f"Код: {cert.code}")

    # Логотип-знак (стрелка-вектор).
    c.setFillColorRGB(*_PRIMARY_RGB)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 70, "Vektor")

    c.save()
    return buffer.getvalue()
