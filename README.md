# warframe-void-cascade-tracker
Warframe Void Cascade Tracker which extracts data using AWS Lambda functions from warframe community API regarding fissure information, specifically Steel Path Void Cascade, and then sends push notification via Telegram, while also maintaining a Supabase database of users who have acess to bot and history of Void Cascade appearences.

Architected a decoupled data ecosystem: utilized Supabase (PostgreSQL) for low-latency transactional state management (OLTP), and engineered a monthly Python ETL pipeline to migrate historical telemetry into Google BigQuery (OLAP) for long-term analytical querying, maintaining $0 infrastructure costs.
