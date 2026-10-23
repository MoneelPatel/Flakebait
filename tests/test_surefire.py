from flakebait.surefire import parse_trace

TRACE = """org.junit.ComparisonFailure: expected:<[a]> but was:<[b]>
\tat org.junit.Assert.assertEquals(Assert.java:115)
\tat com.x.FooTest.testA(FooTest.java:42)
\tat java.base/jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
\tat app//com.x.Run.go(Run.java:7)
Caused by: java.lang.IllegalStateException: bad
  second line
\tat com.x.Foo.bar(Foo.java:10)
\t... 2 more
\tSuppressed: java.lang.RuntimeException: s
\t\tat com.x.S.s(S.java:1)
"""


def test_chain_and_frames():
    chain = parse_trace(TRACE, "org.junit.ComparisonFailure", "expected:<[a]> but was:<[b]>")
    assert [t.type for t in chain] == ["org.junit.ComparisonFailure", "java.lang.IllegalStateException"]
    outer, cause = chain
    assert outer.message == "expected:<[a]> but was:<[b]>"
    assert outer.frames[1].cls == "com.x.FooTest" and outer.frames[1].line == 42
    native = outer.frames[2]
    assert native.module == "java.base" and native.line == -2 and native.loader == ""
    app = outer.frames[3]
    assert app.loader == "app" and app.module == "" and app.cls == "com.x.Run"
    assert cause.message == "bad\n  second line"
    assert [f.cls for f in cause.frames] == ["com.x.Foo", "jdk.internal.reflect.NativeMethodAccessorImpl", "com.x.Run"]


def test_no_message_and_fallback():
    assert parse_trace("java.lang.NullPointerException\n\tat a.B.c(B.java:1)")[0].message is None
    assert parse_trace("", "java.lang.AssertionError", "m")[0].message == "m"
