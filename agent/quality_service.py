from pathlib import Path

import pandas as pd


MISSING_TEXT_VALUES = {
    "",
    "null",
    "none",
    "n/a",
    "na",
    "nan",
}


def profile_csv(csv_path: str) -> dict:
    """
    Generate a data-quality report without modifying the source CSV.
    """

    path = Path(csv_path).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError("Dataset file not found")

    if path.suffix.lower() != ".csv":
        raise ValueError("Data quality profiling currently supports CSV files only")

    df = pd.read_csv(path, dtype=object)

    if len(df.columns) == 0:
        raise ValueError("CSV has no columns")

    # Work on a copy so the original file remains unchanged.
    df = df.copy()

    # Normalize header names only for checking whitespace.
    column_whitespace = [
        str(column)
        for column in df.columns
        if str(column) != str(column).strip()
    ]

    # Detect missing values, including blank and whitespace-only cells.
    missing_by_column = {}
    whitespace_by_column = {}
    type_issues = {}

    for column in df.columns:
        series = df[column].astype("string")
        trimmed = series.str.strip()

        missing_mask = (
            series.isna()
            | trimmed.str.lower().isin(MISSING_TEXT_VALUES)
        )

        whitespace_mask = (
            series.notna()
            & series.ne(trimmed).fillna(False)
        )

        missing_by_column[str(column)] = int(missing_mask.sum())
        whitespace_by_column[str(column)] = int(whitespace_mask.sum())

        # Flag mixed values in columns that appear mostly numeric.
        non_missing = trimmed[~missing_mask]

        if len(non_missing) > 0:
            numeric_values = pd.to_numeric(
                non_missing,
                errors="coerce"
            )

            numeric_ratio = float(numeric_values.notna().mean())

            if 0 < numeric_ratio < 1 and numeric_ratio >= 0.7:
                invalid_mask = numeric_values.isna()
                examples = (
                    non_missing[invalid_mask]
                    .drop_duplicates()
                    .head(5)
                    .tolist()
                )

                type_issues[str(column)] = {
                    "issueCount": int(invalid_mask.sum()),
                    "description": (
                        "Mostly numeric column contains values "
                        "that cannot be parsed as numbers"
                    ),
                    "examples": [str(value) for value in examples],
                }

    duplicate_mask = df.duplicated(keep="first")
    duplicate_rows = int(duplicate_mask.sum())

    missing_cells = sum(missing_by_column.values())
    whitespace_cells = sum(whitespace_by_column.values())

    issue_summary = {
        "missingCells": missing_cells,
        "duplicateRows": duplicate_rows,
        "whitespaceCells": whitespace_cells,
        "columnsWithTypeIssues": len(type_issues),
        "columnsWithMissingValues": sum(
            count > 0 for count in missing_by_column.values()
        ),
        "columnsWithWhitespace": sum(
            count > 0 for count in whitespace_by_column.values()
        ),
        "columnHeaderWhitespace": len(column_whitespace),
    }

    return {
        "fileName": path.name,
        "rowCount": int(len(df)),
        "columnCount": int(len(df.columns)),
        "duplicateRows": duplicate_rows,
        "summary": issue_summary,
        "columns": [
            {
                "name": str(column),
                "detectedType": str(df[column].infer_objects().dtype),
                "missingCount": missing_by_column[str(column)],
                "whitespaceCount": whitespace_by_column[str(column)],
                "missingPercentage": round(
                    missing_by_column[str(column)] / max(len(df), 1) * 100,
                    2,
                ),
                "typeIssue": type_issues.get(str(column)),
            }
            for column in df.columns
        ],
        "columnHeaderWhitespace": column_whitespace,
        "note": (
            "This report detects potential issues only. "
            "No rows or values have been changed."
        ),
    }
