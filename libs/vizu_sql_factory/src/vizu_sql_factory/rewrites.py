"""
SQL Query Rewrites

Implements SQL query normalization and safety rewrites:
- Expand SELECT * to explicit columns
- Inject LIMIT clause
- Inject tenant filter
"""

import logging
from typing import Optional, List

try:
    from sqlglot import parse_one, exp
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False
    parse_one = None
    exp = None

logger = logging.getLogger(__name__)


class SqlRewriter:
    """
    SQL Query Rewriter using sqlglot.

    Rewrites queries for safety:
    - Expand SELECT * to explicit columns
    - Inject LIMIT if missing or capped if too high
    - Inject tenant filter if missing
    """

    def __init__(self, dialect: str = "postgres"):
        """
        Initialize rewriter.

        Args:
            dialect: SQL dialect (default: postgres)
        """
        if not SQLGLOT_AVAILABLE:
            logger.warning("sqlglot not installed; rewrites will return original SQL")

        self.dialect = dialect

    def rewrite_expand_select_star(
        self,
        sql: str,
        allowed_columns: dict[str, List[str]]
    ) -> str:
        """
        Expand SELECT * or SELECT table.* to explicit columns.

        Args:
            sql: SQL query
            allowed_columns: Dict mapping table -> allowed column names

        Returns:
            Rewritten SQL with explicit columns
        """
        if not SQLGLOT_AVAILABLE:
            logger.warning("sqlglot not available; returning original SQL")
            return sql

        try:
            ast = parse_one(sql, dialect=self.dialect)
            if ast is None:
                return sql

            # Check if query has SELECT *
            has_star = False
            for expr in ast.expressions:
                if isinstance(expr, exp.Star):
                    has_star = True
                    break

            if not has_star:
                return sql

            # Get table names
            tables = []
            for table in ast.find_all(exp.Table):
                if table.name:
                    tables.append(table.name)

            if not tables:
                return sql

            # Build explicit column list from allowed columns
            explicit_columns = []
            for table in tables:
                if table in allowed_columns:
                    for col in allowed_columns[table]:
                        explicit_columns.append(exp.Column(name=col, table=table))

            if not explicit_columns:
                return sql

            # Replace SELECT * with explicit columns
            new_ast = ast.copy()
            new_ast.set('expressions', explicit_columns)

            rewritten = new_ast.sql(dialect=self.dialect)
            logger.info(f"Expanded SELECT * to {len(explicit_columns)} columns")
            return rewritten
        except Exception as e:
            logger.error(f"Error rewriting SELECT *: {e}")
            return sql

    def rewrite_inject_limit(self, sql: str, max_rows: int) -> str:
        """
        Inject LIMIT clause if missing, or cap if too high.

        Args:
            sql: SQL query
            max_rows: Maximum rows allowed

        Returns:
            Rewritten SQL with LIMIT clause
        """
        if not SQLGLOT_AVAILABLE:
            logger.warning("sqlglot not available; returning original SQL")
            return sql

        try:
            ast = parse_one(sql, dialect=self.dialect)
            if ast is None:
                return sql

            # Check for existing LIMIT
            limit_node = ast.find(exp.Limit)

            if limit_node is None:
                # No LIMIT; inject one
                ast.set('limit', exp.Limit(expression=exp.Literal.number(max_rows)))
                rewritten = ast.sql(dialect=self.dialect)
                logger.info(f"Injected LIMIT {max_rows}")
                return rewritten
            else:
                # Check LIMIT value
                try:
                    limit_expr = limit_node.expression
                    if isinstance(limit_expr, exp.Literal):
                        current_limit = int(limit_expr.this)
                        if current_limit > max_rows:
                            # Cap the LIMIT
                            limit_node.set('expression', exp.Literal.number(max_rows))
                            rewritten = ast.sql(dialect=self.dialect)
                            logger.info(f"Capped LIMIT from {current_limit} to {max_rows}")
                            return rewritten
                except Exception as e:
                    logger.warning(f"Could not parse LIMIT value: {e}")

            return sql
        except Exception as e:
            logger.error(f"Error rewriting LIMIT: {e}")
            return sql

    def rewrite_inject_tenant_filter(
        self,
        sql: str,
        tenant_id: str,
        tenant_column: str = "client_id"
    ) -> str:
        """
        Inject tenant filter if missing.

        Only injects if query doesn't already have a filter for the tenant column.

        Args:
            sql: SQL query
            tenant_id: Tenant ID value
            tenant_column: Column name for tenant filter (default: client_id)

        Returns:
            Rewritten SQL with tenant filter
        """
        if not SQLGLOT_AVAILABLE:
            logger.warning("sqlglot not available; returning original SQL")
            return sql

        try:
            ast = parse_one(sql, dialect=self.dialect)
            if ast is None:
                return sql

            # Check if tenant filter already exists
            where = ast.find(exp.Where)
            if where:
                # Check if tenant_column is mentioned in WHERE clause
                where_sql = where.sql(dialect=self.dialect).lower()
                if tenant_column.lower() in where_sql:
                    # Filter already present
                    return sql

            # Create tenant filter: client_id = '...'
            tenant_filter = exp.EQ(
                this=exp.Column(name=tenant_column),
                expression=exp.Literal.string(tenant_id)
            )

            if where is None:
                # No WHERE clause; add one
                ast.set('where', exp.Where(this=tenant_filter))
            else:
                # Existing WHERE; add as AND
                existing = where.this
                combined = exp.And(this=existing, expression=tenant_filter)
                where.set('this', combined)

            rewritten = ast.sql(dialect=self.dialect)
            logger.info(f"Injected tenant filter: {tenant_column} = '{tenant_id}'")
            return rewritten
        except Exception as e:
            logger.error(f"Error injecting tenant filter: {e}")
            return sql

    def apply_all_rewrites(
        self,
        sql: str,
        tenant_id: str,
        max_rows: int,
        allowed_columns: dict[str, List[str]],
        tenant_column: str = "client_id"
    ) -> str:
        """
        Apply all rewrites in sequence.

        Order: expand SELECT * → inject LIMIT → inject tenant filter

        Args:
            sql: SQL query
            tenant_id: Tenant ID
            max_rows: Maximum rows
            allowed_columns: Allowed columns dict
            tenant_column: Tenant filter column name

        Returns:
            Fully rewritten SQL
        """
        result = sql

        # 1. Expand SELECT *
        result = self.rewrite_expand_select_star(result, allowed_columns)

        # 2. Inject LIMIT
        result = self.rewrite_inject_limit(result, max_rows)

        # 3. Inject tenant filter
        result = self.rewrite_inject_tenant_filter(result, tenant_id, tenant_column)

        return result
