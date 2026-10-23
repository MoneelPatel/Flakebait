package flakebait.tools;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

import org.junit.Test;

public class MutatorTest {

    private static final String SRC = String.join("\n",
            "package p;",
            "public class C {",
            "    int f(int a, int b) {",
            "        if (a < b) {",
            "            log(\"x\" + a);",
            "            return a + 1;",
            "        }",
            "        Runnable r = () -> { int z = a * 2; };",
            "        return -b;",
            "    }",
            "    boolean g() { return true; }",
            "    void log(String s) {}",
            "}",
            "");

    private static List<Mutator.Mutant> mutants(String method) {
        return Mutator.generate(SRC, "p.C", Collections.singleton(method));
    }

    private static String apply(Mutator.Mutant m) {
        return SRC.substring(0, m.start) + m.replacement + SRC.substring(m.end);
    }

    @Test
    public void generatesExpectedOperatorsInSourceOrder() {
        List<String> ops = mutants("f").stream().map(m -> m.operator + "@" + m.line).collect(Collectors.toList());
        assertEquals(java.util.Arrays.asList(
                "CONDITIONALS_BOUNDARY@4", "NEGATE_CONDITIONALS@4",
                "VOID_METHOD_CALLS@5",
                "PRIMITIVE_RETURNS@6", "MATH@6", "INLINE_CONSTS@6", "INLINE_CONSTS@6",
                "PRIMITIVE_RETURNS@9", "INVERT_NEGS@9"), ops);
    }

    @Test
    public void preservesLineCountAndOtherText() {
        for (Mutator.Mutant m : mutants("f")) {
            String out = apply(m);
            assertEquals(SRC.split("\n", -1).length, out.split("\n", -1).length);
        }
        Mutator.Mutant boundary = mutants("f").get(0);
        assertTrue(apply(boundary).contains("if (a <= b) {"));
    }

    @Test
    public void skipsStringConcatenationAndLambdas() {
        for (Mutator.Mutant m : mutants("f")) {
            assertTrue(m.line != 8);
            assertTrue(!(m.operator.equals("MATH") && m.line == 5));
        }
    }

    @Test
    public void flipsBooleanLiteralReturns() {
        List<Mutator.Mutant> g = mutants("g");
        assertEquals(1, g.size());
        assertTrue(apply(g.get(0)).contains("return false;"));
    }
}
