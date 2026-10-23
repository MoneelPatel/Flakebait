package flakebait.ext.agent;

import static net.bytebuddy.matcher.ElementMatchers.isAnnotatedWith;
import static net.bytebuddy.matcher.ElementMatchers.named;
import static net.bytebuddy.matcher.ElementMatchers.takesArguments;

import java.lang.instrument.Instrumentation;
import java.util.HashMap;
import java.util.Map;

import flakebait.ext.OracleClient;
import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import net.bytebuddy.description.method.MethodDescription;
import net.bytebuddy.description.type.TypeDescription;
import net.bytebuddy.matcher.ElementMatcher;
import net.bytebuddy.matcher.ElementMatchers;

/**
 * Java agent entry point. Arguments are comma-separated key=value pairs:
 * <ul>
 *   <li>{@code inv=<id>[,oracle=<url>]}: victim mode, relays the flaky test's outcome from the oracle;</li>
 *   <li>{@code coverage=<dir>}: dumps per-test JaCoCo execution data into dir.</li>
 * </ul>
 */
public final class Premain {

    private Premain() {}

    public static void premain(String args, Instrumentation inst) {
        Map<String, String> opts = parse(args);
        if (opts.containsKey("oracle")) {
            OracleClient.setBaseUrl(opts.get("oracle"));
        }
        if (opts.containsKey("coverage")) {
            Coverage.init(opts.get("coverage"));
            installCoverage(inst);
        } else if (opts.containsKey("repeat")) {
            Repeat.init(opts.get("repeat"));
            baseBuilder()
                    .type(named("org.junit.runners.ParentRunner")
                            .or(named("org.junit.internal.runners.JUnit38ClassRunner")))
                    .transform((b, td, cl, module, pd) -> b.visit(Advice.to(Repeat.RunAdvice.class)
                            .on(named("run").and(takesArguments(1)))))
                    .installOn(inst);
        } else if (opts.containsKey("inv")) {
            VictimHook.init(opts.get("inv"), inst);
            installVictims(inst);
        }
    }

    private static void installVictims(Instrumentation inst) {
        String victims = OracleClient.post("/victims", "inv=" + OracleClient.enc(VictimHook.invocation()), 2000, 10000);
        if (victims == null) {
            return;
        }
        AgentBuilder builder = baseBuilder();
        for (String line : victims.split("\n")) {
            int hash = line.indexOf('#');
            if (hash <= 0) {
                continue;
            }
            String type = line.substring(0, hash).trim();
            String method = line.substring(hash + 1).trim();
            builder = builder.type(named(type)).transform((b, td, cl, module, pd) ->
                    b.visit(Advice.to(VictimAdvice.class).on(named(method).and(takesArguments(0)))));
        }
        builder.installOn(inst);
        MessageOverrides.install(inst);
    }

    private static void installCoverage(Instrumentation inst) {
        ElementMatcher.Junction<MethodDescription> testMethod =
                isAnnotatedWith(named("org.junit.Test"))
                        .or(isAnnotatedWith(named("org.junit.jupiter.api.Test")))
                        .or(isAnnotatedWith(named("org.junit.jupiter.api.RepeatedTest")))
                        .or(isAnnotatedWith(named("org.junit.jupiter.params.ParameterizedTest")))
                        .or(isAnnotatedWith(named("org.junit.jupiter.api.TestTemplate")))
                        .or(isAnnotatedWith(named("org.testng.annotations.Test")));
        ElementMatcher<TypeDescription> hasTests =
                ElementMatchers.declaresMethod(testMethod);
        baseBuilder()
                .type(hasTests)
                .transform((b, td, cl, module, pd) -> b.visit(Advice.to(CoverageAdvice.class).on(testMethod)))
                .type(named("junit.framework.TestCase"))
                .transform((b, td, cl, module, pd) ->
                        b.visit(Advice.to(CoverageAdvice.JUnit3.class).on(named("runBare"))))
                .installOn(inst);
    }

    static AgentBuilder baseBuilder() {
        return new AgentBuilder.Default()
                .disableClassFormatChanges()
                .with(AgentBuilder.RedefinitionStrategy.RETRANSFORMATION)
                .with(AgentBuilder.Listener.NoOp.INSTANCE)
                .ignore(ElementMatchers.nameStartsWith("flakebait.").or(ElementMatchers.nameStartsWith("java.")));
    }

    static Map<String, String> parse(String args) {
        Map<String, String> out = new HashMap<>();
        if (args == null) {
            return out;
        }
        for (String part : args.split(",")) {
            int eq = part.indexOf('=');
            if (eq > 0) {
                out.put(part.substring(0, eq), part.substring(eq + 1));
            }
        }
        return out;
    }
}
