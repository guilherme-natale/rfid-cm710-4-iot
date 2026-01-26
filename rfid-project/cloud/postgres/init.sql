-- =============================================================================
-- PostgreSQL Initialization Script
-- =============================================================================

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    mac_address VARCHAR(17) PRIMARY KEY,
    device_name VARCHAR(100),
    location VARCHAR(100),
    description TEXT,
    last_seen TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EPC Registry table
CREATE TABLE IF NOT EXISTS epc_registry (
    epc VARCHAR(24) PRIMARY KEY,
    description TEXT,
    category VARCHAR(50),
    asset_name VARCHAR(100),
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_reads BIGINT DEFAULT 1
);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    mac_address VARCHAR(17),
    epc VARCHAR(24),
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen);
CREATE INDEX IF NOT EXISTS idx_epc_registry_category ON epc_registry(category);
CREATE INDEX IF NOT EXISTS idx_epc_registry_last_seen ON epc_registry(last_seen);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);

-- Update function for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for devices
DROP TRIGGER IF EXISTS update_devices_updated_at ON devices;
CREATE TRIGGER update_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Sample data (optional - comment out in production)
-- INSERT INTO devices (mac_address, device_name, location, status)
-- VALUES ('D8:3A:DD:B3:E0:7F', 'Raspberry Pi 01', 'Warehouse A', 'active')
-- ON CONFLICT (mac_address) DO NOTHING;
