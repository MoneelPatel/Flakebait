package flakebait.ext.agent;

import java.lang.instrument.Instrumentation;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;

/**
 * Rebuilds the throwable chain recorded by a reproduction run, so the relayed failure prints exactly like
 * the original: same exception class, message, stack frames and causes.
 *
 * <p>Instances are allocated without running a constructor, and Throwable's private fields are written
 * through sun.misc.Unsafe, which works on Java 8 through 17 without --add-opens.
 */
final class Failures {

    private Failures() {}

    static Throwable build(String[] lines, Instrumentation inst) {
        List<Throwable> chain = new ArrayList<>();
        List<StackTraceElement> frames = null;
        String type = null;
        String message = null;
        for (int i = 1; i < lines.length; i++) {
            String line = lines[i];
            if (line.startsWith("T ")) {
                if (type != null) {
                    chain.add(make(type, message, frames, inst));
                }
                String[] parts = line.substring(2).split(" ", 2);
                type = parts[0];
                message = parts.length < 2 || "-".equals(parts[1])
                        ? null
                        : new String(Base64.getDecoder().decode(parts[1].trim()), StandardCharsets.UTF_8);
                frames = new ArrayList<>();
            } else if (line.startsWith("F ") && frames != null) {
                frames.add(frame(line.substring(2)));
            }
        }
        if (type != null) {
            chain.add(make(type, message, frames, inst));
        }
        if (chain.isEmpty()) {
            return new AssertionError();
        }
        for (int i = 0; i + 1 < chain.size(); i++) {
            Unsafes.put(chain.get(i), Unsafes.CAUSE, chain.get(i + 1));
        }
        return chain.get(0);
    }

    private static Throwable make(String type, String message, List<StackTraceElement> frames,
                                  Instrumentation inst) {
        Throwable t = allocate(type, message, inst);
        Unsafes.put(t, Unsafes.STACK_TRACE, frames.toArray(new StackTraceElement[0]));
        return t;
    }

    private static Throwable allocate(String type, String message, Instrumentation inst) {
        Class<?> cls = load(type);
        if (cls == null || !Throwable.class.isAssignableFrom(cls)) {
            AssertionError fallback = new AssertionError(message == null ? type : type + ": " + message);
            fallback.setStackTrace(new StackTraceElement[0]);
            return fallback;
        }
        try {
            Throwable t = (Throwable) Unsafes.allocate(cls);
            Unsafes.put(t, Unsafes.DETAIL_MESSAGE, message);
            Unsafes.put(t, Unsafes.CAUSE, null);
            if (overridesMessage(cls)) {
                MessageOverrides.set(t, message, inst);
            }
            return t;
        } catch (InstantiationException | RuntimeException e) {
            return construct(cls, message);
        }
    }

    private static Throwable construct(Class<?> cls, String message) {
        for (Class<?> param : new Class<?>[] {String.class, Object.class}) {
            try {
                Constructor<?> c = cls.getConstructor(param);
                return (Throwable) c.newInstance(message);
            } catch (ReflectiveOperationException | RuntimeException ignored) {
                // try the next shape
            }
        }
        return new AssertionError(message);
    }

    private static boolean overridesMessage(Class<?> cls) {
        try {
            return cls.getMethod("getMessage").getDeclaringClass() != Throwable.class;
        } catch (NoSuchMethodException e) {
            return false;
        }
    }

    private static Class<?> load(String name) {
        ClassLoader[] loaders = {Thread.currentThread().getContextClassLoader(), ClassLoader.getSystemClassLoader()};
        for (ClassLoader cl : loaders) {
            if (cl == null) {
                continue;
            }
            try {
                return Class.forName(name, false, cl);
            } catch (ClassNotFoundException | LinkageError ignored) {
                // try the next loader
            }
        }
        return null;
    }

    /** Parses "loader|module|moduleVersion|declaringClass|method|file|line". */
    static StackTraceElement frame(String spec) {
        String[] p = spec.split("\\|", -1);
        String file = p[5].isEmpty() ? null : p[5];
        int line = Integer.parseInt(p[6]);
        if (!p[0].isEmpty() || !p[1].isEmpty()) {
            StackTraceElement withModule = java9Frame(p[0], p[1], p[2], p[3], p[4], file, line);
            if (withModule != null) {
                return withModule;
            }
        }
        return new StackTraceElement(p[3], p[4], file, line);
    }

    private static StackTraceElement java9Frame(String loader, String module, String version, String cls,
                                                String method, String file, int line) {
        try {
            Constructor<StackTraceElement> c = StackTraceElement.class.getConstructor(String.class, String.class,
                    String.class, String.class, String.class, String.class, int.class);
            return c.newInstance(empty(loader), empty(module), empty(version), cls, method, file, line);
        } catch (ReflectiveOperationException e) {
            return null;
        }
    }

    private static String empty(String s) {
        return s.isEmpty() ? null : s;
    }

    /**
     * Access to Throwable's private fields through sun.misc.Unsafe. Reached by reflection because
     * {@code --release 8} does not expose sun.misc to the compiler.
     */
    static final class Unsafes {
        private static final Object UNSAFE;
        private static final Method ALLOCATE;
        private static final Method PUT_OBJECT;
        static final long DETAIL_MESSAGE;
        static final long STACK_TRACE;
        static final long CAUSE;

        static {
            try {
                Class<?> cls = Class.forName("sun.misc.Unsafe");
                Field f = cls.getDeclaredField("theUnsafe");
                f.setAccessible(true);
                UNSAFE = f.get(null);
                ALLOCATE = cls.getMethod("allocateInstance", Class.class);
                PUT_OBJECT = cls.getMethod("putObject", Object.class, long.class, Object.class);
                Method offset = cls.getMethod("objectFieldOffset", Field.class);
                DETAIL_MESSAGE = (Long) offset.invoke(UNSAFE, Throwable.class.getDeclaredField("detailMessage"));
                STACK_TRACE = (Long) offset.invoke(UNSAFE, Throwable.class.getDeclaredField("stackTrace"));
                CAUSE = (Long) offset.invoke(UNSAFE, Throwable.class.getDeclaredField("cause"));
            } catch (ReflectiveOperationException e) {
                throw new ExceptionInInitializerError(e);
            }
        }

        private Unsafes() {}

        static Object allocate(Class<?> cls) throws InstantiationException {
            try {
                return ALLOCATE.invoke(UNSAFE, cls);
            } catch (ReflectiveOperationException e) {
                throw new InstantiationException(String.valueOf(e.getCause()));
            }
        }

        static void put(Throwable t, long offset, Object value) {
            try {
                PUT_OBJECT.invoke(UNSAFE, t, offset, value);
            } catch (ReflectiveOperationException e) {
                throw new IllegalStateException(e);
            }
        }
    }
}
