"""
Schema snapshot generator for CI/CD governance.

Generates snapshots of the current schema (views, columns, constraints)
for version control and diff analysis. Can be run in CI to detect schema changes.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import hashlib

logger = logging.getLogger(__name__)


class SchemaSnapshot:
    """Represents a point-in-time snapshot of the schema."""

    def __init__(
        self,
        views: Dict[str, Dict[str, Any]],
        timestamp: Optional[str] = None,
        version: str = "1.0"
    ):
        """
        Initialize schema snapshot.

        Args:
            views: Dict of view metadata
            timestamp: ISO 8601 timestamp (defaults to now)
            version: Schema snapshot format version
        """
        self.views = views
        self.timestamp = timestamp or datetime.utcnow().isoformat()
        self.version = version
        self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute checksum of views for integrity checking."""
        views_json = json.dumps(self.views, sort_keys=True)
        return hashlib.sha256(views_json.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "checksum": self.checksum,
            "views": self.views,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchemaSnapshot":
        """Create from dictionary."""
        return cls(
            views=data.get("views", {}),
            timestamp=data.get("timestamp"),
            version=data.get("version", "1.0")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SchemaSnapshot":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class SchemaDiff:
    """Represents differences between two schema snapshots."""

    def __init__(self, old_snapshot: SchemaSnapshot, new_snapshot: SchemaSnapshot):
        """
        Initialize diff.

        Args:
            old_snapshot: Previous schema snapshot
            new_snapshot: Current schema snapshot
        """
        self.old_snapshot = old_snapshot
        self.new_snapshot = new_snapshot
        self.added_views = self._find_added_views()
        self.removed_views = self._find_removed_views()
        self.modified_views = self._find_modified_views()

    def _find_added_views(self) -> List[str]:
        """Find views added in new snapshot."""
        old_views = set(self.old_snapshot.views.keys())
        new_views = set(self.new_snapshot.views.keys())
        return sorted(list(new_views - old_views))

    def _find_removed_views(self) -> List[str]:
        """Find views removed in new snapshot."""
        old_views = set(self.old_snapshot.views.keys())
        new_views = set(self.new_snapshot.views.keys())
        return sorted(list(old_views - new_views))

    def _find_modified_views(self) -> Dict[str, Dict[str, Any]]:
        """Find views that have been modified."""
        modified = {}
        old_views = set(self.old_snapshot.views.keys())
        new_views = set(self.new_snapshot.views.keys())
        common_views = old_views & new_views

        for view_name in common_views:
            old_view = self.old_snapshot.views[view_name]
            new_view = self.new_snapshot.views[view_name]

            if old_view != new_view:
                old_cols = set(old_view.get("columns", []))
                new_cols = set(new_view.get("columns", []))

                modified[view_name] = {
                    "added_columns": sorted(list(new_cols - old_cols)),
                    "removed_columns": sorted(list(old_cols - new_cols)),
                    "old_definition": old_view,
                    "new_definition": new_view,
                }

        return modified

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "old_timestamp": self.old_snapshot.timestamp,
            "new_timestamp": self.new_snapshot.timestamp,
            "added_views": self.added_views,
            "removed_views": self.removed_views,
            "modified_views": self.modified_views,
            "summary": {
                "views_added": len(self.added_views),
                "views_removed": len(self.removed_views),
                "views_modified": len(self.modified_views),
                "total_changes": len(self.added_views) + len(self.removed_views) + len(self.modified_views),
            },
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def has_breaking_changes(self) -> bool:
        """Check if diff contains breaking changes."""
        # Breaking changes: removed views or removed columns
        return len(self.removed_views) > 0 or any(
            m.get("removed_columns") for m in self.modified_views.values()
        )

    def get_summary(self) -> str:
        """Get human-readable summary of changes."""
        lines = [
            f"Schema changes between {self.old_snapshot.timestamp} and {self.new_snapshot.timestamp}:",
            "",
        ]

        if self.added_views:
            lines.append(f"✓ Added views ({len(self.added_views)}):")
            for view in self.added_views:
                lines.append(f"  + {view}")

        if self.removed_views:
            lines.append(f"✗ Removed views ({len(self.removed_views)}):")
            for view in self.removed_views:
                lines.append(f"  - {view}")

        if self.modified_views:
            lines.append(f"~ Modified views ({len(self.modified_views)}):")
            for view, changes in self.modified_views.items():
                lines.append(f"  {view}:")
                for col in changes.get("added_columns", []):
                    lines.append(f"    + {col}")
                for col in changes.get("removed_columns", []):
                    lines.append(f"    - {col}")

        if not self.added_views and not self.removed_views and not self.modified_views:
            lines.append("No schema changes detected.")

        if self.has_breaking_changes():
            lines.append("")
            lines.append("⚠️  WARNING: Breaking changes detected!")

        return "\n".join(lines)


class SchemaSnapshotGenerator:
    """Generates schema snapshots from database."""

    @staticmethod
    def generate_snapshot_from_dict(schema_dict: Dict[str, Any]) -> SchemaSnapshot:
        """
        Generate snapshot from schema dict.

        Args:
            schema_dict: Dict with 'views' key containing view metadata

        Returns:
            SchemaSnapshot instance
        """
        views = schema_dict.get("views", {})
        return SchemaSnapshot(views=views)

    @staticmethod
    def save_snapshot(snapshot: SchemaSnapshot, filepath: Path):
        """
        Save snapshot to JSON file.

        Args:
            snapshot: SchemaSnapshot to save
            filepath: Path to save to
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(snapshot.to_json())
        logger.info(f"Schema snapshot saved to {filepath}")

    @staticmethod
    def load_snapshot(filepath: Path) -> SchemaSnapshot:
        """
        Load snapshot from JSON file.

        Args:
            filepath: Path to load from

        Returns:
            SchemaSnapshot instance
        """
        with open(filepath, "r") as f:
            json_str = f.read()
        snapshot = SchemaSnapshot.from_json(json_str)
        logger.info(f"Schema snapshot loaded from {filepath}")
        return snapshot

    @staticmethod
    def compare_snapshots(old_path: Path, new_path: Path) -> SchemaDiff:
        """
        Compare two snapshot files.

        Args:
            old_path: Path to old snapshot
            new_path: Path to new snapshot

        Returns:
            SchemaDiff instance
        """
        old_snapshot = SchemaSnapshotGenerator.load_snapshot(old_path)
        new_snapshot = SchemaSnapshotGenerator.load_snapshot(new_path)
        return SchemaDiff(old_snapshot, new_snapshot)

    @staticmethod
    def get_latest_snapshot(snapshots_dir: Path) -> Optional[Path]:
        """
        Find the most recent snapshot file.

        Args:
            snapshots_dir: Directory containing snapshots

        Returns:
            Path to latest snapshot or None if none exist
        """
        snapshots = sorted(snapshots_dir.glob("schema_*.json"), reverse=True)
        return snapshots[0] if snapshots else None


def generate_snapshot_filename(snapshot_dir: Path) -> Path:
    """Generate a timestamped snapshot filename."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    return snapshot_dir / f"schema_{timestamp}.json"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python schema_snapshot.py generate <output_dir>")
        print("  python schema_snapshot.py compare <old.json> <new.json>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate":
        output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
        print(f"Schema snapshot generation not fully implemented (would generate to {output_dir})")

    elif command == "compare":
        if len(sys.argv) < 4:
            print("Usage: python schema_snapshot.py compare <old.json> <new.json>")
            sys.exit(1)

        old_path = Path(sys.argv[2])
        new_path = Path(sys.argv[3])

        try:
            diff = SchemaSnapshotGenerator.compare_snapshots(old_path, new_path)
            print(diff.get_summary())
            print("\nDetailed diff:")
            print(diff.to_json())

            if diff.has_breaking_changes():
                sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
