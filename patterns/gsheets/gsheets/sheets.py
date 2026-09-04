"""
Google Sheets API utility functions.
"""

from googleapiclient.errors import HttpError

from .auth import get_sheets_service


def read_sheet(spreadsheet_id: str, range_name: str) -> list[list] | None:
    """
    Read a range from a Google Sheet.

    Args:
        spreadsheet_id: The spreadsheet ID (from the sheet URL)
        range_name:     A1 notation range, e.g. 'Sheet1!A1:D10'

    Returns:
        List of rows (each row is a list of values), or None on error.
    """
    try:
        service = get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name,
        ).execute()
        return result.get('values', [])
    except HttpError as e:
        print(f"gsheets.read_sheet error: {e}")
        return None


def add_rows(spreadsheet_id: str, range_name: str, values: list[list[str]]) -> dict | None:
    """
    Append rows to a Google Sheet.

    Args:
        spreadsheet_id: The spreadsheet ID
        range_name:     A1 notation of the target range, e.g. 'Sheet1!A:D'
        values:         Rows to append, e.g. [['John', 'Doe'], ['Jane', 'Smith']]

    Returns:
        API response dict, or None on error.
    """
    try:
        service = get_sheets_service()
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': values},
        ).execute()
        print(f"gsheets: {result['updates']['updatedRows']} row(s) appended.")
        return result
    except HttpError as e:
        print(f"gsheets.add_rows error: {e}")
        return None


def find_row_by_value(
    spreadsheet_id: str,
    range_name: str,
    column_index: int,
    value,
) -> tuple[int, list] | None:
    """
    Find the first row where a column matches a value.

    Args:
        spreadsheet_id: The spreadsheet ID
        range_name:     A1 notation range to search, e.g. 'Sheet1!A:Z'
        column_index:   0-based column index to search (0 = A, 1 = B, ...)
        value:          Value to search for (compared as string)

    Returns:
        (row_number, row_data) where row_number is 1-based, or None if not found.
    """
    try:
        data = read_sheet(spreadsheet_id, range_name)
        if not data:
            return None
        for i, row in enumerate(data):
            if column_index < len(row) and row[column_index] == str(value):
                return (i + 1, row)
        return None
    except Exception as e:
        print(f"gsheets.find_row_by_value error: {e}")
        return None


def update_row(
    spreadsheet_id: str,
    sheet_name: str,
    row_number: int,
    values: list,
) -> dict | None:
    """
    Overwrite all values in a specific row.

    Args:
        spreadsheet_id: The spreadsheet ID
        sheet_name:     Sheet tab name, e.g. 'Sheet1'
        row_number:     1-based row number
        values:         List of values for the entire row

    Returns:
        API response dict, or None on error.
    """
    try:
        end_col = _col_letter(len(values) - 1)
        range_name = f"{sheet_name}!A{row_number}:{end_col}{row_number}"
        service = get_sheets_service()
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body={'values': [values]},
        ).execute()
        print(f"gsheets: row {row_number} updated ({result.get('updatedCells')} cells).")
        return result
    except HttpError as e:
        print(f"gsheets.update_row error: {e}")
        return None


def update_row_columns(
    spreadsheet_id: str,
    sheet_name: str,
    row_number: int,
    column_updates: dict,
) -> dict | None:
    """
    Update specific columns in a row without touching others.

    Args:
        spreadsheet_id: The spreadsheet ID
        sheet_name:     Sheet tab name, e.g. 'Sheet1'
        row_number:     1-based row number
        column_updates: Mapping of column → value.
                        Column can be a 0-based int (0=A) or a letter string ('A').
                        Example: {0: 'John', 2: 'john@example.com'}
                                 {'A': 'John', 'C': 'john@example.com'}

    Returns:
        API response dict, or None on error.
    """
    try:
        service = get_sheets_service()
        data = [
            {
                'range': f"{sheet_name}!{_col_letter(col) if isinstance(col, int) else col.upper()}{row_number}",
                'values': [[value]],
            }
            for col, value in column_updates.items()
        ]
        result = service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'valueInputOption': 'USER_ENTERED', 'data': data},
        ).execute()
        print(f"gsheets: {result.get('totalUpdatedCells', 0)} cell(s) updated in row {row_number}.")
        return result
    except HttpError as e:
        print(f"gsheets.update_row_columns error: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _col_letter(index: int) -> str:
    """Convert a 0-based column index to an A1-notation column letter (e.g. 0→'A', 26→'AA')."""
    result = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result
