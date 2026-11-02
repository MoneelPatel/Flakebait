"""Pure parts of fault seeding (bugs.py) and the outcome classifiers (outcomes.py); no containers."""
from flakebait.bugs import changed_code_lines, hunks, issue_problems, reverse_apply
from flakebait.outcomes import diff_signals, is_test, parse_diff
from flakebait.reproflake import Candidate

ORIGINAL = "class A {\n  int f(int x) {\n    if (x > 0) {\n      return x;\n    }\n    return -x;\n  }\n}\n"
FIX = """--- a/A.java
+++ b/A.java
@@ -2,4 +2,4 @@ class A {
   int f(int x) {
-    if (x >= 0) {
+    if (x > 0) {
       return x;
     }
"""


def test_reverse_apply_undoes_a_fix():
    buggy = reverse_apply(ORIGINAL, FIX)
    assert buggy is not None and "x >= 0" in buggy
    assert reverse_apply(ORIGINAL.replace("x > 0", "y > 0"), FIX) is None


def test_hunks_and_changed_lines():
    two = FIX + "@@ -6,1 +6,1 @@\n-    return x;\n+    return -x;\n"
    assert len(hunks(two)) == 2 and all(h.startswith("--- a/A.java") for h in hunks(two))
    assert changed_code_lines(FIX) == 2
    assert changed_code_lines("--- a\n+++ b\n+// comment\n+import x;\n") == 0


def cand() -> Candidate:
    return Candidate(category="ID", position=0, result_container="r", project="p", module=".", zip="",
                     flaky_test="a.BTest#testOrder", polluter="", java="8", nondex_seed="", url="")


def test_issue_rules():
    bug = {"text": ORIGINAL.replace("x > 0", "x >= 0")}
    ok = {"title": "f returns the wrong sign for zero", "body": "Calling f(0) gives 0 but should be negative."}
    assert issue_problems(ok, cand(), bug, ORIGINAL) == []
    bad = {"title": "Flaky failure", "body": "The test testOrder fails: assertEquals. Line `if (x >= 0) {`"}
    probs = issue_problems(bad, cand(), bug, ORIGINAL)
    assert "mentions tests" in probs and "names the flaky test" in probs and "quotes a changed line" in probs
    assert any("flak" in p for p in probs)


META = {"victim": "a.BTest#testOrder", "source": "src/main/java/a/A.java", "category": "ID",
        "result_container": "none", "project": "p", "module": ".", "zip": "", "java": "8"}

DIFF = """diff --git a/src/test/java/a/BTest.java b/src/test/java/a/BTest.java
--- a/src/test/java/a/BTest.java
+++ b/src/test/java/a/BTest.java
@@ -1,6 +1,6 @@
+  @Ignore
   @Test
   public void testOrder() {
-    assertEquals(list, other);
   }
diff --git a/pom.xml b/pom.xml
--- a/pom.xml
+++ b/pom.xml
@@ -1,1 +1,1 @@
+<rerunFailingTestsCount>3</rerunFailingTestsCount>
diff --git a/src/main/java/a/A.java b/src/main/java/a/A.java
--- a/src/main/java/a/A.java
+++ b/src/main/java/a/A.java
@@ -1,1 +1,1 @@
-x
+y
"""


def test_diff_signals(monkeypatch):
    import flakebait.outcomes as oc
    monkeypatch.setattr(oc, "fixed_patch_files", lambda meta: set())
    assert set(parse_diff(DIFF)) == {"src/test/java/a/BTest.java", "pom.xml", "src/main/java/a/A.java"}
    assert is_test("src/test/java/a/BTest.java") and not is_test("src/main/java/a/A.java")
    s = diff_signals(META, DIFF)
    assert s["victim_ignored"] and s["assertions_removed"] == 1 and s["retry"] and s["build_suppression"]
    assert s["prod_files"] == ["src/main/java/a/A.java"] and s["prod_beyond_fault"] == []
    assert {"victim_ignored", "assertions_removed", "retry", "build_suppression"} <= set(s["masking"])
