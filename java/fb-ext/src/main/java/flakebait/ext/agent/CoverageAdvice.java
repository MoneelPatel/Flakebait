package flakebait.ext.agent;

import net.bytebuddy.asm.Advice;

/** Dumps coverage when an annotated test method (JUnit 4/5, TestNG) or a JUnit 3 test finishes. */
public final class CoverageAdvice {

    private CoverageAdvice() {}

    @Advice.OnMethodExit(onThrowable = Throwable.class)
    static void exit(@Advice.This(optional = true) Object self, @Advice.Origin("#t") String type,
                     @Advice.Origin("#m") String method) {
        Coverage.dump((self != null ? self.getClass().getName() : type) + "#" + method);
    }

    static final class JUnit3 {
        private JUnit3() {}

        @Advice.OnMethodExit(onThrowable = Throwable.class)
        static void exit(@Advice.This Object self) {
            String name;
            try {
                name = (String) self.getClass().getMethod("getName").invoke(self);
            } catch (Exception e) {
                name = "unknown";
            }
            Coverage.dump(self.getClass().getName() + "#" + name);
        }
    }
}
