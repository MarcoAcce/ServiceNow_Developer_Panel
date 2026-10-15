import csv
import re
from collections.abc import Sequence
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.worksheet._write_only import WriteOnlyWorksheet

from response_cache import DEFAULT_TABLE_NAME, CacheTable

CSV_SUFFIX: str = ".csv"
XLSX_SUFFIX: str = ".xlsx"
CSV_FORMAT: str = "csv"
XLSX_FORMAT: str = "xlsx"
EXPORT_FORMATS: tuple[str, ...] = (CSV_FORMAT, XLSX_FORMAT)
TEXT_TYPE: str = "s"
SHEET_TITLE_LIMIT: int = 31
SHEET_SUFFIX_TEMPLATE: str = "_{index}"
INVALID_SHEET_CHARACTERS: re.Pattern[str] = re.compile(r"[\[\]:*?/\\]")
INVALID_FILE_CHARACTERS: re.Pattern[str] = re.compile(r"[^A-Za-z0-9._-]+")
REPLACEMENT_CHARACTER: str = "_"
SHEET_QUOTE: str = "'"


def export_csv(tables: Sequence[CacheTable], directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    paths: list[Path] = []
    for table in tables:
        path = directory / f"{file_stem(table.name, used)}{CSV_SUFFIX}"
        paths.append(write_csv(path, table.columns, table.records))
    return paths


def write_csv(path: Path, columns: Sequence[str], records: Sequence[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return path


def export_xlsx(tables: Sequence[CacheTable], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook(write_only=True)
    used: set[str] = set()
    for table in tables or (CacheTable(name=DEFAULT_TABLE_NAME, columns=(), records=[]),):
        sheet = workbook.create_sheet(title=sheet_title(table.name, used))
        sheet.append([text_cell(sheet, column) for column in table.columns])
        for record in table.records:
            sheet.append(
                [text_cell(sheet, record.get(column, "")) for column in table.columns]
            )
    workbook.save(path)
    return path


def text_cell(sheet: WriteOnlyWorksheet, value: str) -> WriteOnlyCell:
    cell = WriteOnlyCell(sheet, value=ILLEGAL_CHARACTERS_RE.sub("", value))
    cell.data_type = TEXT_TYPE
    return cell


def sheet_title(name: str, used: set[str]) -> str:
    cleaned = INVALID_SHEET_CHARACTERS.sub(REPLACEMENT_CHARACTER, name).strip(SHEET_QUOTE)
    base = cleaned[:SHEET_TITLE_LIMIT] or DEFAULT_TABLE_NAME
    return unique_name(base, used, SHEET_TITLE_LIMIT)


def file_stem(name: str, used: set[str]) -> str:
    cleaned = INVALID_FILE_CHARACTERS.sub(REPLACEMENT_CHARACTER, name).strip(".")
    return unique_name(cleaned or DEFAULT_TABLE_NAME, used, 0)


def unique_name(base: str, used: set[str], limit: int) -> str:
    candidate = base
    index = 2
    while candidate.lower() in used:
        suffix = SHEET_SUFFIX_TEMPLATE.format(index=index)
        stem = base[: limit - len(suffix)] if limit else base
        candidate = f"{stem}{suffix}"
        index += 1
    used.add(candidate.lower())
    return candidate
