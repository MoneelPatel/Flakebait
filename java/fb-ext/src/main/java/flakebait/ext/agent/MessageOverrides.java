package flakebait.ext.agent;

import static net.bytebuddy.matcher.ElementMatchers.isDeclaredBy;
import static net.bytebuddy.matcher.ElementMatchers.named;
import static net.bytebuddy.matcher.ElementMatchers.takesArguments;

import java.lang.instrument.Instrumentation;
import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;

import net.bytebuddy.asm.Advice;

/**
 * Some exception types compute getMessage() from their own fields (e.g. JUnit's ComparisonFailure). For a
 * rebuilt instance those fields are empty, so the recorded message is returned instead. The advice is added
 * to such a type only when the first rebuilt instance of it is created.
 */
public final class MessageOverrides {

    private static final Map<Throwable, String> MESSAGES = Collections.synchronizedMap(new WeakHashMap<>());
    private static final Set<String> TYPES = ConcurrentHashMap.newKeySet();

    private MessageOverrides() {}

    static void install(Instrumentation inst) {
        Premain.baseBuilder()
                .type(td -> TYPES.contains(td.getName()))
                .transform((b, td, cl, module, pd) -> b.visit(Advice.to(GetMessage.class)
                        .on(named("getMessage").and(takesArguments(0)).and(isDeclaredBy(td)))))
                .installOn(inst);
    }

    static void set(Throwable t, String message, Instrumentation inst) {
        MESSAGES.put(t, message);
        for (Class<?> c = t.getClass(); c != Throwable.class && c != null; c = c.getSuperclass()) {
            if (TYPES.add(c.getName())) {
                try {
                    inst.retransformClasses(c);
                } catch (Exception | LinkageError ignored) {
                    // The message falls back to the type's own getMessage().
                }
            }
        }
    }

    /** Called from advice; returns the recorded message, or null when this instance has none. */
    public static String lookup(Throwable t) {
        return MESSAGES.containsKey(t) ? MESSAGES.get(t) : null;
    }

    public static boolean has(Throwable t) {
        return MESSAGES.containsKey(t);
    }

    static final class GetMessage {
        private GetMessage() {}

        @Advice.OnMethodExit
        static void exit(@Advice.This Throwable self,
                         @Advice.Return(readOnly = false) String returned) {
            if (MessageOverrides.has(self)) {
                returned = MessageOverrides.lookup(self);
            }
        }
    }
}
