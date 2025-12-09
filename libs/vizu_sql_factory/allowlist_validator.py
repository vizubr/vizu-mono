"""
Allowlist validator for schema governance.

Validates that:
1. All allowlist entries reference existing schema objects
2. Views and columns actually exist in the current schema
3. No typos or orphaned entries
4. Allowlist configuration is consistent

Can be run in CI to validate schema changes.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """A validation error."""
    error_type: str  # "missing_view", "missing_column", "orphaned_entry", "invalid_config"
    severity: str   # "error", "warning"
    message: str
    path: Optional[str] = None  # Path in allowlist config
    schema_reference: Optional[str] = None  # What it references


class AllowlistValidator:
    """Validates allowlist configuration against actual schema."""

    def __init__(self, schema_info: Dict[str, Any]):
        """
        Initialize validator.

        Args:
            schema_info: Schema metadata (views, columns) from database
                        Format: {
                            "views": {
                                "customers": {
                                    "columns": ["id", "name", "email", "client_id"],
                                    "type": "table" | "view"
                                },
                                ...
                            }
                        }
        """
        self.schema_info = schema_info
        self.available_views = set(schema_info.get("views", {}).keys())
        self.view_columns = {
            view: set(info.get("columns", []))
            for view, info in schema_info.get("views", {}).items()
        }

    def validate_allowlist(self, allowlist: Dict[str, Any]) -> Tuple[bool, List[ValidationError]]:
        """
        Validate an entire allowlist configuration.

        Args:
            allowlist: Allowlist configuration dict with roles

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        if not isinstance(allowlist, dict):
            return False, [ValidationError(
                error_type="invalid_config",
                severity="error",
                message="Allowlist must be a dictionary"
            )]

        # Validate structure
        for role_name, role_config in allowlist.items():
            if not isinstance(role_config, dict):
                errors.append(ValidationError(
                    error_type="invalid_config",
                    severity="error",
                    message=f"Role '{role_name}' config must be a dictionary",
                    path=role_name
                ))
                continue

            # Validate views
            if "views" in role_config:
                view_errors = self._validate_views(
                    role_name,
                    role_config["views"]
                )
                errors.extend(view_errors)

            # Validate columns
            if "columns" in role_config:
                column_errors = self._validate_columns(
                    role_name,
                    role_config.get("views", []),
                    role_config["columns"]
                )
                errors.extend(column_errors)

        # Separate errors and warnings
        has_errors = any(e.severity == "error" for e in errors)
        return not has_errors, errors

    def _validate_views(self, role_name: str, views: Any) -> List[ValidationError]:
        """Validate views list for a role."""
        errors = []

        if not isinstance(views, list):
            return [ValidationError(
                error_type="invalid_config",
                severity="error",
                message=f"Views for role '{role_name}' must be a list",
                path=f"{role_name}.views"
            )]

        for view_name in views:
            if not isinstance(view_name, str):
                errors.append(ValidationError(
                    error_type="invalid_config",
                    severity="error",
                    message=f"View name must be a string: {view_name}",
                    path=f"{role_name}.views"
                ))
                continue

            if view_name not in self.available_views:
                errors.append(ValidationError(
                    error_type="missing_view",
                    severity="error",
                    message=f"View '{view_name}' does not exist in schema",
                    path=f"{role_name}.views",
                    schema_reference=view_name
                ))

        return errors

    def _validate_columns(
        self,
        role_name: str,
        allowed_views: List[str],
        columns_config: Dict[str, List[str]]
    ) -> List[ValidationError]:
        """Validate columns config for a role."""
        errors = []

        if not isinstance(columns_config, dict):
            return [ValidationError(
                error_type="invalid_config",
                severity="error",
                message=f"Columns for role '{role_name}' must be a dictionary",
                path=f"{role_name}.columns"
            )]

        for view_name, column_list in columns_config.items():
            # Check view exists
            if view_name not in self.available_views:
                errors.append(ValidationError(
                    error_type="missing_view",
                    severity="error",
                    message=f"View '{view_name}' in columns config does not exist",
                    path=f"{role_name}.columns.{view_name}",
                    schema_reference=view_name
                ))
                continue

            # Check columns exist in view
            if not isinstance(column_list, list):
                errors.append(ValidationError(
                    error_type="invalid_config",
                    severity="error",
                    message=f"Columns for view '{view_name}' must be a list",
                    path=f"{role_name}.columns.{view_name}"
                ))
                continue

            available_columns = self.view_columns.get(view_name, set())

            for col_name in column_list:
                if not isinstance(col_name, str):
                    errors.append(ValidationError(
                        error_type="invalid_config",
                        severity="error",
                        message=f"Column name must be a string: {col_name}",
                        path=f"{role_name}.columns.{view_name}"
                    ))
                    continue

                if col_name not in available_columns:
                    errors.append(ValidationError(
                        error_type="missing_column",
                        severity="error",
                        message=f"Column '{col_name}' does not exist in view '{view_name}'",
                        path=f"{role_name}.columns.{view_name}",
                        schema_reference=f"{view_name}.{col_name}"
                    ))

        # Check for orphaned entries (view in columns but not in views list)
        for view_name in columns_config.keys():
            if view_name not in allowed_views:
                errors.append(ValidationError(
                    error_type="orphaned_entry",
                    severity="warning",
                    message=f"View '{view_name}' has column config but is not in allowed views",
                    path=f"{role_name}.columns.{view_name}"
                ))

        return errors

    def validate_allowlist_file(self, filepath: Path) -> Tuple[bool, List[ValidationError]]:
        """
        Load and validate allowlist from JSON file.

        Args:
            filepath: Path to allowlist JSON file

        Returns:
            Tuple of (is_valid, list of errors)
        """
        try:
            with open(filepath, "r") as f:
                allowlist = json.load(f)
        except json.JSONDecodeError as e:
            return False, [ValidationError(
                error_type="invalid_config",
                severity="error",
                message=f"Invalid JSON in allowlist file: {str(e)}"
            )]
        except Exception as e:
            return False, [ValidationError(
                error_type="invalid_config",
                severity="error",
                message=f"Failed to read allowlist file: {str(e)}"
            )]

        return self.validate_allowlist(allowlist)

    def get_schema_diff(self, old_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare current schema with previous schema.

        Args:
            old_schema: Previous schema metadata

        Returns:
            Dict with added/removed/modified views and columns
        """
        old_views = set(old_schema.get("views", {}).keys())
        new_views = self.available_views

        return {
            "added_views": list(new_views - old_views),
            "removed_views": list(old_views - new_views),
            "modified_views": self._find_modified_views(old_schema),
        }

    def _find_modified_views(self, old_schema: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
        """Find views with added/removed columns."""
        modifications = {}

        for view_name in self.available_views:
            if view_name not in old_schema.get("views", {}):
                continue

            old_cols = set(old_schema["views"][view_name].get("columns", []))
            new_cols = self.view_columns.get(view_name, set())

            added = list(new_cols - old_cols)
            removed = list(old_cols - new_cols)

            if added or removed:
                modifications[view_name] = {
                    "added_columns": added,
                    "removed_columns": removed,
                }

        return modifications

    def recommend_allowlist_updates(
        self,
        current_allowlist: Dict[str, Any],
        schema_diff: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recommend updates to allowlist based on schema changes.

        Args:
            current_allowlist: Current allowlist config
            schema_diff: Output from get_schema_diff()

        Returns:
            Recommendations dict
        """
        recommendations = {
            "new_views_to_consider": schema_diff.get("added_views", []),
            "removed_views_affected": self._find_affected_roles(
                current_allowlist,
                schema_diff.get("removed_views", [])
            ),
            "column_changes": schema_diff.get("modified_views", {}),
            "suggested_actions": [],
        }

        # Suggest actions
        if schema_diff.get("added_views"):
            recommendations["suggested_actions"].append(
                f"Review new views: {', '.join(schema_diff['added_views'])} "
                "and consider adding to appropriate roles"
            )

        if schema_diff.get("removed_views"):
            recommendations["suggested_actions"].append(
                f"Remove deleted views from allowlist: {', '.join(schema_diff['removed_views'])}"
            )

        if schema_diff.get("modified_views"):
            recommendations["suggested_actions"].append(
                "Review column changes in modified views"
            )

        return recommendations

    def _find_affected_roles(
        self,
        allowlist: Dict[str, Any],
        removed_views: List[str]
    ) -> Dict[str, List[str]]:
        """Find which roles are affected by removed views."""
        affected = {}

        for role_name, role_config in allowlist.items():
            role_views = set(role_config.get("views", []))
            removed_from_role = list(role_views & set(removed_views))

            if removed_from_role:
                affected[role_name] = removed_from_role

        return affected


def validate_allowlist_json(
    allowlist_path: Path,
    schema_path: Path
) -> Tuple[bool, List[ValidationError]]:
    """
    Convenience function to validate allowlist against schema files.

    Args:
        allowlist_path: Path to allowlist.json
        schema_path: Path to schema snapshot JSON

    Returns:
        Tuple of (is_valid, list of errors)
    """
    try:
        with open(schema_path, "r") as f:
            schema_info = json.load(f)
    except Exception as e:
        return False, [ValidationError(
            error_type="invalid_config",
            severity="error",
            message=f"Failed to load schema: {str(e)}"
        )]

    validator = AllowlistValidator(schema_info)
    return validator.validate_allowlist_file(allowlist_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python allowlist_validator.py <allowlist.json> <schema.json>")
        sys.exit(1)

    allowlist_path = Path(sys.argv[1])
    schema_path = Path(sys.argv[2])

    is_valid, errors = validate_allowlist_json(allowlist_path, schema_path)

    for error in errors:
        level = "ERROR" if error.severity == "error" else "WARNING"
        print(f"[{level}] {error.message}")
        if error.path:
            print(f"        Path: {error.path}")

    sys.exit(0 if is_valid else 1)
