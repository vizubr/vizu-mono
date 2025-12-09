#!/usr/bin/env python3
"""
Script to create a test cliente-vizu and configure it for text-to-SQL testing.
This script directly manipulates the database to set up test data.
"""

import psycopg2
import uuid
import json
from psycopg2.extras import execute_values

# Database connection
conn = psycopg2.connect(
    host="localhost",
    port=5433,  # Note: Docker Compose maps 5433 (host) to 5432 (container)
    user="user",
    password="password",
    database="vizu_db"
)

cursor = conn.cursor()

def create_cliente_vizu():
    """Create a test cliente-vizu record with SQL tool enabled."""

    cliente_id = str(uuid.uuid4())
    api_key = str(uuid.uuid4())

    # Insert into cliente_vizu table
    sql = """
    INSERT INTO cliente_vizu
    (id, nome_empresa, tipo_cliente, tier, api_key, enabled_tools)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id, api_key, nome_empresa
    """

    cursor.execute(sql, (
        cliente_id,
        "Teste Produtos Computador",
        "INTERNAL",  # tipo_cliente
        "ENTERPRISE",  # tier
        api_key,
        json.dumps(["executar_sql_agent"])  # enabled_tools
    ))

    result = cursor.fetchone()
    conn.commit()

    if result:
        return {
            "cliente_id": result[0],
            "api_key": result[1],
            "nome_empresa": result[2]
        }
    return None

def create_fonte_de_dados():
    """Create a data source (fonte_de_dados) linking cliente to the test table."""

    # First, get the cliente_id we just created
    cursor.execute("SELECT id FROM cliente_vizu WHERE nome_empresa = %s",
                   ("Teste Produtos Computador",))
    result = cursor.fetchone()

    if not result:
        print("ERROR: Could not find the cliente_vizu record")
        return None

    cliente_id = result[0]

    # Create a data source entry
    fonte_id = str(uuid.uuid4())
    sql = """
    INSERT INTO fonte_de_dados
    (id, cliente_vizu_id, nome_fonte, tipo_fonte, config)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id, cliente_vizu_id
    """

    config = {
        "schema": "public",
        "table": "computer_products",
        "connection_string": "postgresql://user:password@postgres:5432/vizu_db"
    }

    cursor.execute(sql, (
        fonte_id,
        cliente_id,
        "Computer Products (Test)",
        "postgres",
        json.dumps(config)
    ))

    result = cursor.fetchone()
    conn.commit()

    if result:
        return {
            "fonte_id": result[0],
            "cliente_id": str(result[1])
        }
    return None

def main():
    try:
        print("🔧 Creating test cliente-vizu...")
        cliente = create_cliente_vizu()

        if not cliente:
            print("❌ Failed to create cliente-vizu")
            return

        print(f"✅ Cliente created:")
        print(f"   Cliente ID: {cliente['cliente_id']}")
        print(f"   API Key: {cliente['api_key']}")
        print(f"   Name: {cliente['nome_empresa']}")
        print()

        # Try to create fonte_de_dados
        try:
            print("🔧 Creating data source...")
            fonte = create_fonte_de_dados()

            if fonte:
                print(f"✅ Data source created:")
                print(f"   Fonte ID: {fonte['fonte_id']}")
                print(f"   Cliente ID: {fonte['cliente_id']}")
        except Exception as e:
            print(f"⚠️  Could not create data source (table may not exist): {e}")

        print()
        print("=" * 60)
        print("TEST CONFIGURATION READY")
        print("=" * 60)
        print()
        print("Use this API key for testing:")
        print(f"  X-API-KEY: {cliente['api_key']}")
        print()
        print("Example curl request:")
        print(f"  curl -X POST http://localhost:8003/chat \\")
        print(f"    -H 'Content-Type: application/json' \\")
        print(f"    -H 'X-API-KEY: {cliente['api_key']}' \\")
        print(f"    -d '{{\"message\": \"How many laptop products do we have?\"}}' ")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
