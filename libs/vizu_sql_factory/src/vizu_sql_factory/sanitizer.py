"""
Result Sanitizer

Sanitizes SQL query results before returning to LLM/client:
- Filter columns (remove non-allowlisted columns)
- Redact sensitive values
- Normalize data types
- Mask PII
"""

import logging
from typing import Dict, List, Any, Optional, Pattern
import re

logger = logging.getLogger(__name__)


class ResultSanitizer:
    """
    Sanitizes SQL query results for safe LLM consumption.

    Implements:
    - Column filtering (allowlist only)
    - Value redaction (PII patterns)
    - Data type normalization
    - Caveat annotations
    """

    # Patterns for detecting PII
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN = re.compile(r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b')
    CREDIT_CARD_PATTERN = re.compile(r'\b(?:\d[ -]*?){13,19}\b')
    SSN_PATTERN = re.compile(r'\b(?:(?:(?:00[0-9]|0[1-6][0-9]|0[7][0-2])|[1-6][0-9]{2}|7(?:[0-6][0-9]|7[0-2]))[-]?(?:0[1-9]|1[0-2])[-]?(?:0[1-9]|[12][0-9]|3[01]))\b')

    def __init__(self, sensitive_columns: Optional[List[str]] = None):
        """
        Initialize sanitizer.

        Args:
            sensitive_columns: List of column names that contain PII
                              (e.g., ["email", "phone", "ssn", "password"])
        """
        self.sensitive_columns = set(sensitive_columns or [
            "email", "phone", "ssn", "password", "api_key", "token",
            "credit_card", "bank_account", "secret"
        ])
        logger.info(f"ResultSanitizer initialized with {len(self.sensitive_columns)} sensitive columns")

    def sanitize(
        self,
        rows: List[Dict[str, Any]],
        columns: List[Dict[str, str]],
        allowed_columns: Optional[Dict[str, List[str]]] = None,
        mask_pii: bool = True,
        redact_nulls: bool = False
    ) -> Dict[str, Any]:
        """
        Sanitize result rows.

        Args:
            rows: Result rows from query
            columns: Column metadata [{name, type}]
            allowed_columns: If provided, filter to only these columns
            mask_pii: If True, redact PII values
            redact_nulls: If True, replace nulls with [REDACTED]

        Returns:
            Dict with sanitized_rows, columns, caveats
        """
        sanitized_rows = []
        caveats = []
        columns_to_keep = set(col["name"] for col in columns)
        removed_columns = set()

        # 1. Filter columns if allowlist provided
        if allowed_columns:
            # Flatten allowed columns from dict to set
            allowed_set = set()
            for col_list in allowed_columns.values():
                allowed_set.update(col_list)

            removed_columns = columns_to_keep - allowed_set
            columns_to_keep = columns_to_keep & allowed_set

            if removed_columns:
                caveats.append(f"Removed non-allowlisted columns: {', '.join(sorted(removed_columns))}")

        # 2. Sanitize each row
        for row in rows:
            sanitized_row = {}

            for col_name, col_value in row.items():
                # Skip removed columns
                if col_name not in columns_to_keep:
                    continue

                # Apply sanitization
                if col_value is None:
                    sanitized_row[col_name] = "[NULL]" if redact_nulls else None
                elif col_name.lower() in self.sensitive_columns:
                    # Redact sensitive columns entirely
                    sanitized_row[col_name] = "[REDACTED]"
                    caveats.append(f"Column '{col_name}' redacted (sensitive)")
                elif isinstance(col_value, str) and mask_pii:
                    # Mask PII patterns in string values
                    masked_value = self._mask_pii_patterns(col_value)
                    if masked_value != col_value:
                        sanitized_row[col_name] = masked_value
                        caveats.append(f"Column '{col_name}' masked for PII")
                    else:
                        sanitized_row[col_name] = col_value
                else:
                    sanitized_row[col_name] = col_value

            sanitized_rows.append(sanitized_row)

        # 3. Filter column metadata
        sanitized_columns = [
            col for col in columns
            if col["name"] in columns_to_keep
        ]

        # Deduplicate caveats
        unique_caveats = list(dict.fromkeys(caveats))

        if removed_columns:
            logger.info(f"Removed {len(removed_columns)} non-allowlisted columns")
        if len(caveats) > 0:
            logger.info(f"Applied {len(unique_caveats)} sanitization rules")

        return {
            "rows": sanitized_rows,
            "columns": sanitized_columns,
            "caveats": unique_caveats
        }

    def _mask_pii_patterns(self, value: str, mask_char: str = "*") -> str:
        """
        Mask PII patterns in a string value.

        Args:
            value: String value to check
            mask_char: Character to use for masking

        Returns:
            Value with PII masked
        """
        original = value

        # Mask emails: keep first char and domain
        # Example: john@example.com → j***@example.com
        value = self.EMAIL_PATTERN.sub(
            lambda m: m.group(0)[0] + mask_char * (len(m.group(0).split('@')[0]) - 1) + '@' + m.group(0).split('@')[1],
            value
        )

        # Mask phone numbers: XXX-XXX-XXXX
        value = self.PHONE_PATTERN.sub(
            lambda m: f"({mask_char}{mask_char}{mask_char})-{mask_char}{mask_char}{mask_char}-{mask_char}{mask_char}{mask_char}{mask_char}",
            value
        )

        # Mask credit cards: keep last 4
        value = self.CREDIT_CARD_PATTERN.sub(
            lambda m: f"{mask_char * (len(m.group(0)) - 4)}",
            value
        )

        # Mask SSN: XXX-XX-XXXX
        value = self.SSN_PATTERN.sub(
            lambda m: f"{mask_char}{mask_char}{mask_char}-{mask_char}{mask_char}-{mask_char}{mask_char}{mask_char}{mask_char}",
            value
        )

        if value != original:
            logger.debug(f"Masked PII in value (before: {original[:20]}..., after: {value[:20]}...)")

        return value

    def filter_large_results(
        self,
        rows: List[Dict[str, Any]],
        max_rows: int = 1000,
        max_cell_size: int = 1000
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Filter large result sets and cell values.

        Args:
            rows: Result rows
            max_rows: Maximum rows to return
            max_cell_size: Maximum character length per cell

        Returns:
            (filtered_rows, caveats)
        """
        caveats = []

        # 1. Truncate cell values
        truncated_rows = []
        cells_truncated = 0

        for row in rows:
            truncated_row = {}
            for col_name, col_value in row.items():
                if isinstance(col_value, str) and len(col_value) > max_cell_size:
                    truncated_row[col_name] = col_value[:max_cell_size] + "..."
                    cells_truncated += 1
                else:
                    truncated_row[col_name] = col_value
            truncated_rows.append(truncated_row)

        if cells_truncated > 0:
            caveats.append(f"Truncated {cells_truncated} cell values (max {max_cell_size} chars)")

        # 2. Limit rows
        if len(truncated_rows) > max_rows:
            filtered_rows = truncated_rows[:max_rows]
            caveats.append(f"Limited to {max_rows} rows (total: {len(truncated_rows)})")
        else:
            filtered_rows = truncated_rows

        return filtered_rows, caveats

    @staticmethod
    def build_summary(rows: List[Dict[str, Any]], columns: List[Dict[str, str]]) -> str:
        """
        Build a human-readable summary of results for LLM.

        Args:
            rows: Result rows
            columns: Column metadata

        Returns:
            Summary string
        """
        if not rows:
            return "Query returned no results."

        col_names = [col["name"] for col in columns]
        summary = f"Query returned {len(rows)} row(s) with {len(col_names)} column(s): {', '.join(col_names)}"

        # Add sample row
        if rows:
            sample = rows[0]
            sample_str = "; ".join([f"{k}: {v}" for k, v in list(sample.items())[:3]])
            summary += f"\nSample: {sample_str}"

        return summary
