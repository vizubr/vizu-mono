#!/usr/bin/env python3
"""
Seed script to load test data directly to PostgreSQL using SQLAlchemy.
Uses the same pattern as the DBWriterService from data_ingestion_worker.
"""

import pandas as pd
import sys
from sqlalchemy import create_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_computer_products():
    """Load computer_products.csv into PostgreSQL."""

    # Database connection (matching docker-compose.yml)
    db_url = "postgresql://user:password@localhost:5433/vizu_db"

    try:
        logger.info("Creating SQLAlchemy engine...")
        engine = create_engine(db_url)

        # Read the CSV
        csv_path = "test_data/computer_products.csv"
        logger.info(f"Reading CSV from {csv_path}...")
        df = pd.read_csv(csv_path)

        logger.info(f"Loaded {len(df)} rows from CSV")
        logger.info(f"Columns: {df.columns.tolist()}")

        # Load to database using pandas to_sql (same as DBWriterService)
        logger.info("Writing to PostgreSQL...")
        df.to_sql(
            name="computer_products",
            con=engine,
            if_exists="replace",  # Replace the table (fresh load)
            index=False
        )

        # Verify
        logger.info("Verifying data...")
        result_df = pd.read_sql("SELECT COUNT(*) as count FROM computer_products", engine)
        count = result_df['count'].iloc[0]

        logger.info(f"✅ Successfully loaded {count} rows to computer_products table")

        # Show stats
        total_value = pd.read_sql(
            "SELECT SUM(price_usd * stock_quantity) as total_value FROM computer_products",
            engine
        )
        print(f"\n📊 Inventory Statistics:")
        print(f"   Total Products: {count}")
        print(f"   Total Inventory Value: ${total_value['total_value'].iloc[0]:,.2f}")

        engine.dispose()
        return True

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = seed_computer_products()
    sys.exit(0 if success else 1)
