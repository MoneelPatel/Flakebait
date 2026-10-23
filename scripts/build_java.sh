#!/usr/bin/env bash
# Build the Java components and stage the jars that containers mount at /opt/fb/jars.
set -euo pipefail
cd "$(dirname "$0")/.."
mvn -q -f java/pom.xml package
mkdir -p data/jars
cp java/fb-ext/target/fb-ext.jar java/fb-tools/target/fb-tools.jar data/jars/
[ -f data/jars/jacocoagent.jar ] || curl -sfL -o data/jars/jacocoagent.jar \
  https://repo1.maven.org/maven2/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar
ls -la data/jars
# ReproFlake's OD extension (built into fb-base); mounted into Maven's lib/ext for OD agent runs.
[ -f data/jars/od-ext.jar ] || docker run --rm fb-base:8 cat /opt/fb/od-ext/surefire-changing-maven-extension-1.0-SNAPSHOT.jar > data/jars/od-ext.jar
cp data/jars/fb-ext.jar docker/fb-ext.jar
