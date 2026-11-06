db = db.getSiblingDB('fraud_db');

db.createCollection('transactions');

// Create indexes
db.transactions.createIndex({ "processed_at": -1 });
db.transactions.createIndex({ "fraud_flag": 1 });
db.transactions.createIndex({ "risk_level": 1 });
db.transactions.createIndex({ "type": 1 });
db.transactions.createIndex({ "amount": 1 });
db.transactions.createIndex({ "nameOrig": 1 });

// Optional: Add a TTL index to prune old transactions in production
// Keep documents for 30 days (2592000 seconds)
// db.transactions.createIndex({ "processed_at": 1 }, { expireAfterSeconds: 2592000 });

print("Database and indexes initialized.");
