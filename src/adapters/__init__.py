"""SentinelGraph AI - production adapters (Phase T).

Optional, disabled-by-default integrations.  The local demo satisfies the
same conceptual interfaces with in-process implementations (NetworkX +
JSON/CSV files) and never requires cloud credentials.

Interfaces:
    GraphStore       - node/edge/subgraph/path access (NetworkX impl default)
    SourceRepository - relational access to ingested source records (Postgres)
    DocumentStore    - object storage for raw documents (S3)
    EventStream      - publish/subscribe for pipeline events (Kafka)
    Neo4jGraphStore  - property-graph store mirroring GraphStore (Neo4j)

Each adapter imports its heavy client lazily and raises a descriptive
error when the optional dependency or configuration is missing, so the
demo mode is never broken by their absence.
"""
