from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from models.meeting import MeetingData


def export_tasks_excel(target: Path, meeting: MeetingData) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Поручения"

    ws.append(["Совещание", meeting.title])
    ws.append(["Дата", meeting.created_at])
    ws.append([])
    ws.append(["Ответственный", "Поручение", "Срок", "Статус"])

    for cell in ws[4]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for task in meeting.tasks:
        ws.append([
            task.responsible,
            task.description,
            task.deadline,
            task.status,
        ])

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 70
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 18

    wb.save(target)
    return target
