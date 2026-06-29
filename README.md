# BenchlingSentry
BenchlingSentry: Serverless Lab Sample Integration Engine

BenchlingSentry is a high-performance, zero-dependency AWS Lambda microservice engineered to securely validate, clean, and synchronize incoming laboratory sample inventories with a live Benchling registry.

By leveraging serverless best practices, BenchlingSentry acts as an intelligent firewall for your laboratory information systems—ensuring only pristine, strictly formatted, and deduplicated sample records make it into your registry.


🛠️ System Architecture

Payload Ingestion: Accepts incoming batches of raw laboratory sample names (via API Gateway, S3 triggers, or manual event triggers).

Security Handshake: Queries AWS Secrets Manager dynamically using IAM permissions to fetch API authorization headers.

First-Pass Validation: Filters structural data abnormalities, type violations, and name pattern anomalies.

Cloud Registry Synchronization: Executes an optimized, secure HTTPS query using native sockets to scan current Benchling inventory.

Telemetry Reporting: Compiles runtime statistics, isolates brand-new unique samples, and returns a comprehensive processing report.
