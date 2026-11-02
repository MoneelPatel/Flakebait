package flakebait.ext.agent;

import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicBoolean;

import net.bytebuddy.asm.Advice;

/**
 * Runs the victim twice in one JVM: before JUnit 4 runs the victim's class, run the victim once on its own
 * (full fixture lifecycle). The execution JUnit then runs is the victim's second in this JVM.
 *
 * <p>NIO failing configuration (reproduction, validation): the first run uses a separate notifier, so Surefire
 * does not report it. Category-faithful shim (deviations.md #33): the first run reports to the class's own
 * notifier, so the agent sees the test executed twice ("Tests run" counts both).
 */
public final class Repeat {

    private static volatile String targetClass;
    private static volatile String targetMethod;
    private static volatile boolean visible;
    private static final AtomicBoolean DONE = new AtomicBoolean();

    private Repeat() {}

    static void init(String victim, boolean reported) {
        visible = reported;
        int hash = victim.indexOf('#');
        targetClass = victim.substring(0, hash);
        targetMethod = victim.substring(hash + 1);
    }

    /** Called with the JUnit runner that is about to run; runs the victim once if this is its class. */
    public static void beforeRun(Object runner, Object notifier) {
        if (DONE.get()) {
            return;
        }
        try {
            Class<?> testClass = testClassOf(runner);
            if (testClass == null || !testClass.getName().equals(targetClass) || !DONE.compareAndSet(false, true)) {
                return;
            }
            ClassLoader cl = testClass.getClassLoader();
            Class<?> request = Class.forName("org.junit.runner.Request", true, cl);
            Class<?> core = Class.forName("org.junit.runner.JUnitCore", true, cl);
            Object req = request.getMethod("method", Class.class, String.class).invoke(null, testClass, targetMethod);
            if (visible && notifier != null) {
                Class<?> notifierType = Class.forName("org.junit.runner.notification.RunNotifier", true, cl);
                Object first = request.getMethod("getRunner").invoke(req);
                first.getClass().getMethod("run", notifierType).invoke(first, notifier);
                return;
            }
            Object junit = core.getConstructor().newInstance();
            core.getMethod("run", request).invoke(junit, req);
        } catch (ReflectiveOperationException | RuntimeException | LinkageError e) {
            System.err.println("[fb-repeat] first run failed to start: " + e);
        }
    }

    private static Class<?> testClassOf(Object runner) throws ReflectiveOperationException {
        try {
            Object tc = runner.getClass().getMethod("getTestClass").invoke(runner);
            return (Class<?>) tc.getClass().getMethod("getJavaClass").invoke(tc);
        } catch (NoSuchMethodException e) {
            // JUnit38ClassRunner: its description names the class.
            Method describe = runner.getClass().getMethod("getDescription");
            Object description = describe.invoke(runner);
            Object cls = description.getClass().getMethod("getTestClass").invoke(description);
            return (Class<?>) cls;
        }
    }

    static final class RunAdvice {
        private RunAdvice() {}

        @Advice.OnMethodEnter
        static void enter(@Advice.This Object runner, @Advice.Argument(0) Object notifier) {
            Repeat.beforeRun(runner, notifier);
        }
    }
}
