#!/bin/bash
# Seed script to create test cliente and configure SQL tool access
# This requires PostgreSQL client to be available

set -e

echo "🔍 Checking if cliente_vizu table exists..."

# Check if table exists
TABLE_EXISTS=$(docker exec vizu_postgres psql -U user -d vizu_db -tAc "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'cliente_vizu');")

if [ "$TABLE_EXISTS" != "t" ]; then
    echo "❌ Error: cliente_vizu table does not exist."
    echo ""
    echo "The database schema needs to be migrated first."
    echo "Please run: docker compose up db_manager --build"
    echo ""
    echo "Or run migrations with vizu-db CLI:"
    echo "  cd libs/vizu_db_connector && poetry run vizu-db migrate"
    exit 1
fi

echo "✅ cliente_vizu table exists"
echo ""

# Generate a UUID for the cliente
CLIENTE_ID="$(python3 -c 'import uuid; print(str(uuid.uuid4()))')"
API_KEY="$(python3 -c 'import uuid; print(str(uuid.uuid4()))')"

echo "📋 Creating test cliente-vizu..."
echo "   Cliente ID: $CLIENTE_ID"
echo "   API Key: $API_KEY"
echo ""

# Create the cliente-vizu record
docker exec -i vizu_postgres psql -U user -d vizu_db << EOF
INSERT INTO cliente_vizu
(id, nome_empresa, tipo_cliente, tier, api_key, enabled_tools, ferramenta_sql_habilitada)
VALUES
(
    '$CLIENTE_ID'::uuid,
    'Teste Produtos Computador',
    'INTERNAL',
    'ENTERPRISE',
    '$API_KEY',
    '["executar_sql_agent"]'::jsonb,
    true
);
EOF

echo "✅ Cliente created successfully!"
echo ""
echo "=" * 60
echo "TEST CONFIGURATION READY"
echo "=" * 60
echo ""
echo "Use this API key for testing:"
echo "  X-API-KEY: $API_KEY"
echo ""
echo "Example curl request:"
echo "  curl -X POST http://localhost:8003/chat \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'X-API-KEY: $API_KEY' \\"
echo "    -d '{\"message\": \"How many laptop products do we have?\"}'"
echo ""
echo "Example batch test with jq:"
echo "  curl -s -X POST http://localhost:8003/chat \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'X-API-KEY: $API_KEY' \\"
echo "    -d '{\"message\": \"Show me the 5 most expensive products\"}' | jq ."
echo ""
