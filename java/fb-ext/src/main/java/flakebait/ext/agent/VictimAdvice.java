package flakebait.ext.agent;

import net.bytebuddy.asm.Advice;

/** Inlined into the flaky test method: the oracle decides its outcome, and the original body never runs. */
public final class VictimAdvice {

    private VictimAdvice() {}

    @Advice.OnMethodEnter(skipOn = Advice.OnNonDefaultValue.class)
    static boolean enter(@Advice.Origin("#t") String type, @Advice.Origin("#m") String method) throws Throwable {
        return VictimHook.run(type, method);
    }
}
