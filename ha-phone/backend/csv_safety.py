"""Shared CSV-export hardening against formula/CSV injection (OWASP).

Excel, LibreOffice and Google Sheets all treat a cell starting with
=, +, -, @, tab or CR as a formula, regardless of the file's declared
content-type. A phonebook/holiday name is free text an admin can set to
anything (e.g. via CSV import re-export), so a value like
'=cmd|"/c calc"!A1' would be evaluated as a formula the moment the
exported file is opened in a spreadsheet app - not remote code execution
against this server, but a real client-side attack vector against
whoever opens the export. Prefixing a leading apostrophe is the standard,
widely-recommended mitigation: spreadsheet apps display it as literal
text instead of evaluating it.
"""

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: str) -> str:
    if value.startswith(_DANGEROUS_PREFIXES):
        return "'" + value
    return value
