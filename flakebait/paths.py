"""Filesystem layout. Everything under data/ and runs/ is local-only (gitignored)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
REPORTS = ROOT / "reports" / "milestone1"

DATA = ROOT / "data"
META = DATA / "reproflake" / "meta"
ZIPS = DATA / "reproflake" / "zips"
WORK = DATA / "work"            # extracted ReproFlake modules, one directory per zip
SCRATCH = DATA / "scratch"      # per-check working copies
INSTANCES = DATA / "instances"  # built task instances (repo + hidden metadata)
RUNS = ROOT / "runs"            # agent runs: trajectories, diffs, oracle logs

JARS = DATA / "jars"
FB_EXT_JAR = ROOT / "java" / "fb-ext" / "target" / "fb-ext.jar"
FB_TOOLS_JAR = ROOT / "java" / "fb-tools" / "target" / "fb-tools.jar"
JACOCO_AGENT = JARS / "jacocoagent.jar"

# Paths inside containers.
C_SRC = "/app/source"
C_M2 = "/root/.m2"
C_JARS = "/opt/fb/jars"
C_OD_EXT = "/opt/fb/od-ext/surefire-changing-maven-extension-1.0-SNAPSHOT.jar"
C_TOOLS_M2 = "/opt/fb/tools-m2"
