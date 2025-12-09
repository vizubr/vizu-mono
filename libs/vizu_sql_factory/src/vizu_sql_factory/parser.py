"""
SQL Parser Module

Wraps sqlglot for parsing SQL queries into AST.
Provides graceful error handling and fallback for unparseable queries.

Usage:
    parser = SqlParser()
    ast = parser.parse("SELECT * FROM orders WHERE client_id = '123'")
    if ast:
        print(f"Parsed: {ast.sql()}")
    else:
        print("Failed to parse")
"""

import logging
from typing import Optional, Union

try:
    import sqlglot
    from sqlglot import parse_one, exp
    from sqlglot.errors import ParseError as SqlglotParseError
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False
    sqlglot = None
    parse_one = None
    exp = None
    SqlglotParseError = Exception

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Custom exception for parse failures."""

    def __init__(self, message: str, original_sql: str, parse_error: Optional[Exception] = None):
        self.message = message
        self.original_sql = original_sql
        self.parse_error = parse_error
        super().__init__(message)


class SqlParser:
    """
    SQL Parser using sqlglot.

    Parses SQL strings into AST for validation and transformation.
    """

    def __init__(self, dialect: str = "postgres"):
        """
        Initialize parser.

        Args:
            dialect: SQL dialect (default: postgres)
        """
        if not SQLGLOT_AVAILABLE:
            logger.warning("sqlglot not installed; parse() will return None")

        self.dialect = dialect

    def parse(self, sql: str) -> Optional["exp.Expression"]:
        """
        Parse SQL string into AST.

        Args:
            sql: SQL query string

        Returns:
            sqlglot AST Expression or None if parse fails

        Raises:
            ParseError: On critical parse failures (optional, controlled by raise_on_error)
        """
        if not SQLGLOT_AVAILABLE:
            logger.error("sqlglot not available; cannot parse SQL")
            return None

        if not sql or not sql.strip():
            logger.warning("Empty SQL string provided to parser")
            return None

        try:
            ast = parse_one(sql, dialect=self.dialect)
            logger.debug(f"Successfully parsed SQL: {sql[:100]}...")
            return ast
        except SqlglotParseError as e:
            logger.warning(f"Parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing SQL: {e}")
            return None

    def is_select(self, ast: Optional[exp.Expression]) -> bool:
        """
        Check if AST is a SELECT statement.

        Args:
            ast: sqlglot AST Expression

        Returns:
            True if ast is a SELECT, False otherwise
        """
        if ast is None:
            return False
        return isinstance(ast, exp.Select)

    def extract_tables(self, ast: Optional[exp.Expression]) -> list[str]:
        """
        Extract all table/view names from AST.

        Args:
            ast: sqlglot AST Expression

        Returns:
            List of table names (e.g., ['orders', 'customers'])
        """
        if ast is None:
            return []

        try:
            tables = []
            for table in ast.find_all(exp.Table):
                name = table.name
                if name:
                    tables.append(name)
            return tables
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            return []

    def extract_columns(self, ast: Optional[exp.Expression]) -> list[str]:
        """
        Extract all column names from SELECT clause.

        Args:
            ast: sqlglot AST Expression

        Returns:
            List of column names (e.g., ['id', 'name', 'created_at'])
        """
        if ast is None:
            return []

        if not self.is_select(ast):
            return []

        try:
            columns = []
            for col in ast.expressions:
                # Handle SELECT * or SELECT table.*
                if isinstance(col, exp.Star):
                    columns.append("*")
                elif isinstance(col, exp.Column):
                    columns.append(col.name)
                elif isinstance(col, exp.Alias):
                    # Extract column name, not alias
                    columns.append(col.this.name if hasattr(col.this, 'name') else str(col.this))
                else:
                    # For complex expressions, use string representation
                    columns.append(str(col).split(" AS ")[0].strip())
            return columns
        except Exception as e:
            logger.error(f"Error extracting columns: {e}")
            return []

    def extract_where_predicates(self, ast: Optional[exp.Expression]) -> list[str]:
        """
        Extract WHERE clause predicates as strings.

        Args:
            ast: sqlglot AST Expression

        Returns:
            List of predicate strings (e.g., ['client_id = 123', 'status = "active"'])
        """
        if ast is None:
            return []

        if not self.is_select(ast):
            return []

        try:
            where = ast.find(exp.Where)
            if not where:
                return []

            predicates = []
            # Get the WHERE clause expression
            where_expr = where.this

            if isinstance(where_expr, exp.And):
                # Multiple predicates joined by AND
                for pred in where_expr.find_all(exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.In, exp.Between):
                    predicates.append(pred.sql(dialect=self.dialect))
            else:
                # Single predicate
                predicates.append(where_expr.sql(dialect=self.dialect))

            return predicates
        except Exception as e:
            logger.error(f"Error extracting WHERE predicates: {e}")
            return []

    def has_limit(self, ast: Optional[exp.Expression]) -> bool:
        """
        Check if query has LIMIT clause.

        Args:
            ast: sqlglot AST Expression

        Returns:
            True if LIMIT clause present, False otherwise
        """
        if ast is None:
            return False

        if not self.is_select(ast):
            return False

        try:
            return ast.find(exp.Limit) is not None
        except Exception as e:
            logger.error(f"Error checking LIMIT: {e}")
            return False

    def get_limit_value(self, ast: Optional[exp.Expression]) -> Optional[int]:
        """
        Extract LIMIT value from query.

        Args:
            ast: sqlglot AST Expression

        Returns:
            Limit value as int, or None if not found
        """
        if ast is None:
            return None

        if not self.is_select(ast):
            return None

        try:
            limit = ast.find(exp.Limit)
            if not limit:
                return None

            # LIMIT has an 'expression' attribute with the limit value
            limit_expr = limit.expression
            if isinstance(limit_expr, exp.Literal):
                return int(limit_expr.this)
            return None
        except Exception as e:
            logger.error(f"Error getting LIMIT value: {e}")
            return None

    def extract_joins(self, ast: Optional[exp.Expression]) -> list[dict]:
        """
        Extract JOIN clauses.

        Args:
            ast: sqlglot AST Expression

        Returns:
            List of join dicts: {'type': 'INNER', 'left': 'table1', 'right': 'table2', 'on': 'predicate'}
        """
        if ast is None:
            return []

        if not self.is_select(ast):
            return []

        try:
            joins = []
            for join in ast.find_all(exp.Join):
                join_dict = {
                    'type': join.kind or 'INNER',
                    'right': join.this.name if hasattr(join.this, 'name') else str(join.this),
                    'on': join.on.sql(dialect=self.dialect) if join.on else None
                }
                joins.append(join_dict)
            return joins
        except Exception as e:
            logger.error(f"Error extracting joins: {e}")
            return []

    def extract_aggregates(self, ast: Optional[exp.Expression]) -> list[str]:
        """
        Extract aggregate functions (COUNT, SUM, AVG, MIN, MAX, etc.).

        Args:
            ast: sqlglot AST Expression

        Returns:
            List of aggregate function names
        """
        if ast is None:
            return []

        if not self.is_select(ast):
            return []

        try:
            aggregates = []
            agg_functions = {exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Stddev}

            for node in ast.walk():
                for agg_class in agg_functions:
                    if isinstance(node, agg_class):
                        aggregates.append(node.__class__.__name__.upper())

            return list(set(aggregates))  # Remove duplicates
        except Exception as e:
            logger.error(f"Error extracting aggregates: {e}")
            return []
