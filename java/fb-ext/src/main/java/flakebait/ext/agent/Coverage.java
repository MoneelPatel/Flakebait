package flakebait.ext.agent;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Per-test coverage: after each test, take (and reset) the JaCoCo agent's execution data and write it to
 * {@code <dir>/<class>#<method>.<n>.exec}. Setup code that runs before a test is attributed to that test.
 */
public final class Coverage {

    private static volatile File dir;
    private static final Map<String, AtomicInteger> COUNTS = new ConcurrentHashMap<>();

    private Coverage() {}

    static void init(String path) {
        dir = new File(path);
        dir.mkdirs();
    }

    public static void dump(String test) {
        if (dir == null) {
            return;
        }
        try {
            Class<?> rt = Class.forName("org.jacoco.agent.rt.RT", true, ClassLoader.getSystemClassLoader());
            Object agent = rt.getMethod("getAgent").invoke(null);
            Method get = agent.getClass().getMethod("getExecutionData", boolean.class);
            get.setAccessible(true);
            byte[] data = (byte[]) get.invoke(agent, true);
            int n = COUNTS.computeIfAbsent(test, k -> new AtomicInteger()).incrementAndGet();
            String name = test.replaceAll("[^A-Za-z0-9_.#$-]", "_") + "." + n + ".exec";
            try (FileOutputStream out = new FileOutputStream(new File(dir, name))) {
                out.write(data);
            }
        } catch (ReflectiveOperationException | IOException | RuntimeException e) {
            System.err.println("[fb-coverage] dump failed for " + test + ": " + e);
        }
    }
}
