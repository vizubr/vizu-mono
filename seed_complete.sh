#!/bin/bash
# Complete seed script for test environment
# Creates cliente-vizu and loads computer_products CSV

set -e

echo "🌱 Starting database seeding..."
echo ""

# Generate UUIDs for the test cliente
CLIENTE_ID=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
API_KEY=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')

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
    'EXTERNO',
    'ENTERPRISE',
    '$API_KEY',
    '["executar_sql_agent"]'::jsonb,
    true
);

INSERT INTO fonte_de_dados
(id, cliente_vizu_id, nome_fonte, tipo_fonte, config)
VALUES
(
    gen_random_uuid(),
    '$CLIENTE_ID'::uuid,
    'computer_products',
    'postgres',
    '{"schema": "public", "table": "computer_products"}'::jsonb
);
EOF

echo "✅ Cliente created successfully!"
echo ""
echo "📊 Importing test data..."

# Check if CSV file exists
if [ ! -f "test_data/computer_products.csv" ]; then
    echo "❌ Error: test_data/computer_products.csv not found!"
    exit 1
fi

# Create the table
docker exec -i vizu_postgres psql -U user -d vizu_db << 'SQLEOF'
CREATE TABLE IF NOT EXISTS computer_products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255),
    category VARCHAR(100),
    price_usd DECIMAL(10,2),
    stock_quantity INT,
    description TEXT,
    manufacturer VARCHAR(100),
    warranty_months INT
);
SQLEOF

# Import CSV data using cat and psql
cat test_data/computer_products.csv | docker exec -i vizu_postgres psql -U user -d vizu_db -c "COPY computer_products(product_id, product_name, category, price_usd, stock_quantity, description, manufacturer, warranty_months) FROM STDIN WITH CSV HEADER;"

echo "✅ Data imported successfully!"
echo ""

# Verify the data
echo "🔍 Verifying data..."
docker exec -it vizu_postgres psql -U user -d vizu_db -c "
SELECT
    COUNT(*) as total_products,
    COUNT(CASE WHEN stock_quantity > 0 THEN 1 END) as in_stock,
    SUM(price_usd * stock_quantity)::money as total_inventory_value
FROM computer_products;
"

echo ""
echo "=" * 80
echo "✅ SEEDING COMPLETE"
echo "=" * 80
echo ""
echo "Test Environment Ready:"
echo "  Cliente ID: $CLIENTE_ID"
echo "  API Key: $API_KEY"
echo "  Endpoint: http://localhost:8003/chat"
echo ""
echo "Example curl request:"
echo "  curl -X POST http://localhost:8003/chat \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'X-API-KEY: $API_KEY' \\"
echo "    -d '{\"message\": \"How many laptop products do we have?\"}'"
echo ""
