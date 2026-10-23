package flakebait.ext.agent;

import java.lang.instrument.Instrumentation;

import flakebait.ext.OracleClient;

/**
 * Asks the oracle for the flaky test's outcome in this invocation.
 *
 * <p>Response protocol (one item per line):
 * <pre>
 * PASS                     the test passes; skip the body
 * RUN                      run the original body (oracle has no opinion)
 * FAIL                     followed by one or more throwables, outermost first:
 * T &lt;class&gt; &lt;base64 message or -&gt;
 * F &lt;loader&gt;|&lt;module&gt;|&lt;moduleVersion&gt;|&lt;declaringClass&gt;|&lt;method&gt;|&lt;file&gt;|&lt;line&gt;
 * </pre>
 */
public final class VictimHook {

    /** A reproduction can include a full Maven build of the module. */
    private static final int READ_TIMEOUT_MS = 45 * 60 * 1000;

    private static volatile String invocation = "";
    private static volatile Instrumentation instrumentation;

    private VictimHook() {}

    static void init(String inv, Instrumentation inst) {
        invocation = inv;
        instrumentation = inst;
    }

    static String invocation() {
        return invocation;
    }

    /** Returns true to skip the test body (pass), false to run it; throws to fail. */
    public static boolean run(String type, String method) throws Throwable {
        String body = "inv=" + OracleClient.enc(invocation) + "&victim=" + OracleClient.enc(type + "#" + method);
        String response = OracleClient.post("/exec", body, 5000, READ_TIMEOUT_MS);
        if (response == null) {
            return false;
        }
        String[] lines = response.split("\n");
        switch (lines[0].trim()) {
            case "PASS":
                return true;
            case "FAIL":
                throw Failures.build(lines, instrumentation);
            default:
                return false;
        }
    }
}
