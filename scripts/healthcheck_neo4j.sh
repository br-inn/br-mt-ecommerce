#!/usr/bin/env bash
set -euo pipefail

NEO4J_URI=${NEO4J_URI:-bolt://localhost:17687}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-devpassword}

python3 -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('$NEO4J_URI', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))
with driver.session() as session:
    result = session.run('RETURN 1 AS ok').single()
    assert result['ok'] == 1
driver.close()
print('Neo4j healthcheck: OK')
"
