package flakebait.ext.agent;

import net.bytebuddy.asm.Advice;

/**
 * Inlined into an OD flaky test's polluter (category-faithful shim, deviations.md #33): records that the polluter
 * ran in this JVM, so the oracle can apply the failing configuration only when it really ran before the victim.
 */
public final class PolluterAdvice {

    private PolluterAdvice() {}

    @Advice.OnMethodExit(onThrowable = Throwable.class)
    static void exit() {
        VictimHook.polluterRan();
    }
}
