import csv
import io
import json
import re
import sqlite3
import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree


MAX_DATA_ROWS = 5000


def _scalar(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _table_summary(headers, rows):
    columns = []
    for index, header in enumerate(headers):
        values = [row[index] if index < len(row) else None for row in rows]
        numeric = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
        columns.append({
            "name": str(header),
            "type": "number" if numeric and len(numeric) >= max(1, len(values) // 2) else "text",
            "nulls": sum(value in (None, "") for value in values),
            "distinct": len({str(value) for value in values if value not in (None, "")}),
            "min": min(numeric) if numeric else None,
            "max": max(numeric) if numeric else None,
        })
    return {"columns": columns, "row_count": len(rows), "sample": [dict(zip(headers, row)) for row in rows[:50]]}


def _xlsx_rows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for item in root.findall("x:si", namespace):
                shared.append("".join(node.text or "" for node in item.findall(".//x:t", namespace)))
        sheet_name = next((name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")), None)
        if not sheet_name:
            return [], []
        root = ElementTree.fromstring(archive.read(sheet_name))
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rows = []
        for row in root.findall(".//x:sheetData/x:row", namespace):
            values = []
            for cell in row.findall("x:c", namespace):
                value = cell.find("x:v", namespace)
                text = value.text if value is not None else ""
                if cell.get("t") == "s" and text.isdigit() and int(text) < len(shared):
                    text = shared[int(text)]
                values.append(_scalar(text))
            rows.append(values)
        return rows[0] if rows else [], rows[1:] if len(rows) > 1 else []


def analyze_data_file(filename, raw, query=""):
    extension = PurePosixPath(filename).suffix.lower()
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError("Data files are limited to 25 MB.")
    if extension == ".csv":
        text = raw.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = [[_scalar(value) for value in row] for row in reader]
        headers = [str(value or "column_" + str(index + 1)) for index, value in enumerate(rows[0] if rows else [])]
        data = rows[1:MAX_DATA_ROWS]
    elif extension == ".json":
        payload = json.loads(raw.decode("utf-8-sig"))
        data = payload if isinstance(payload, list) else payload.get("rows", []) if isinstance(payload, dict) else []
        if not isinstance(data, list):
            raise ValueError("JSON must contain an array or a rows array.")
        records = [item for item in data[:MAX_DATA_ROWS] if isinstance(item, dict)]
        headers = list(dict.fromkeys(key for item in records for key in item.keys()))
        data = [[item.get(header) for header in headers] for item in records]
    elif extension == ".xlsx":
        headers, data = _xlsx_rows(raw)
        headers = [str(value or "column_" + str(index + 1)) for index, value in enumerate(headers)]
        data = data[:MAX_DATA_ROWS]
    elif extension in {".db", ".sqlite", ".sqlite3"}:
        connection = sqlite3.connect(":memory:")
        connection.deserialize(raw)
        tables = [row[0] for row in connection.execute("select name from sqlite_master where type='table' order by name")]
        if not tables:
            connection.close()
            return {"filename": filename, "tables": [], "schema": {}}
        table = tables[0]
        safe_table = re.sub(r"[^A-Za-z0-9_]", "", table)
        cursor = connection.execute(f'SELECT * FROM "{safe_table}" LIMIT {MAX_DATA_ROWS}')
        headers = [item[0] for item in cursor.description or []]
        data = [list(row) for row in cursor.fetchall()]
        connection.close()
    else:
        raise ValueError("Supported formats are CSV, JSON, XLSX, SQLite, DB, and SQLITE3.")
    if not headers:
        return {"filename": filename, "schema": {"columns": [], "row_count": 0, "sample": []}, "rows": []}
    if query:
        lowered = query.lower()
        data = [row for row in data if lowered in " ".join(str(value or "") for value in row).lower()]
    summary = _table_summary(headers, data)
    summary["headers"] = headers
    return {"filename": filename, "schema": summary, "rows": [dict(zip(headers, row)) for row in data[:100]], "suggested_chart": {"x": headers[0], "y": headers[1] if len(headers) > 1 else None}}
