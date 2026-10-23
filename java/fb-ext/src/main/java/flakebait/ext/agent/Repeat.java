package flakebait.ext.agent;

import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicBoolean;

import net.bytebuddy.asm.Advice;

/**
 * NIO failing configuration: before JUnit 4 runs the victim's class, run the victim once on its own in the
 * same JVM (full fixture lifecycle, separate notifier, so Surefire does not report it). The run Surefire
 * reports is therefore the victim's second execution in this JVM.
 */
public final class Repeat {

    private static volatile String targetClass;
    private static volatile String targetMethod;
    private static final AtomicBoolean DONE = new AtomicBoolean();

    private Repeat() {}

    static void init(String victim) {
        int hash = victim.indexOf('#');
        targetClass = victim.substring(0, hash);
        targetMethod = victim.substring(hash + 1);
    }

    /** Called with the JUnit runner that is about to run; runs the victim once if this is its class. */
    public static void beforeRun(Object runner) {
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
        static void enter(@Advice.This Object runner) {
            Repeat.beforeRun(runner);
        }
    }
}
