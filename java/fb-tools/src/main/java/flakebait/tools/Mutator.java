package flakebait.tools;

import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.Position;
import com.github.javaparser.Range;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.CallableDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.expr.BinaryExpr;
import com.github.javaparser.ast.expr.BooleanLiteralExpr;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.IntegerLiteralExpr;
import com.github.javaparser.ast.expr.LambdaExpr;
import com.github.javaparser.ast.expr.LongLiteralExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NullLiteralExpr;
import com.github.javaparser.ast.expr.StringLiteralExpr;
import com.github.javaparser.ast.expr.UnaryExpr;
import com.github.javaparser.ast.stmt.ExpressionStmt;
import com.github.javaparser.ast.stmt.ReturnStmt;
import com.github.javaparser.ast.stmt.SwitchEntry;
import com.github.javaparser.ast.type.Type;

/**
 * Source-level mutator implementing PIT's default operator families on selected methods of one class:
 * conditionals boundary, negated conditionals, math, increments, invert negatives, return values
 * (true/false/primitive/null/empty), removed method calls, and inline constant +/-1.
 *
 * <p>Mutants are produced by splicing the source text at token positions, so formatting and line numbers
 * of everything else are preserved exactly. Each mutant is written as a full copy of the file; compilation
 * is checked later, which filters out type-invalid mutants (e.g. "return null" for a primitive).
 *
 * <p>Output: {@code <out>/mutants.tsv} (one row per mutant) and {@code <out>/<id>.java}.
 */
public final class Mutator {

    private Mutator() {}

    /** One textual replacement. Offsets are into the original file text. */
    static final class Mutant {
        final String operator;
        final String method;
        final int line;
        final int start;
        final int end;
        final String replacement;
        final String original;

        Mutant(String operator, String method, int line, int start, int end, String replacement, String original) {
            this.operator = operator;
            this.method = method;
            this.line = line;
            this.start = start;
            this.end = end;
            this.replacement = replacement;
            this.original = original;
        }
    }

    public static void main(String[] args) throws IOException {
        Map<String, String> opts = Args.parse(args);
        Path src = Paths.get(Args.required(opts, "src"));
        String className = Args.required(opts, "class");
        Set<String> methods = new HashSet<>(Arrays.asList(Args.required(opts, "methods").split(",")));
        Path out = Paths.get(Args.required(opts, "out"));
        Files.createDirectories(out);

        String text = new String(Files.readAllBytes(src), StandardCharsets.UTF_8);
        List<Mutant> mutants = generate(text, className, methods);

        try (Writer tsv = Files.newBufferedWriter(out.resolve("mutants.tsv"), StandardCharsets.UTF_8)) {
            tsv.write("id\toperator\tmethod\tline\toriginal\tmutated\n");
            int n = 0;
            for (Mutant m : mutants) {
                String id = String.format("M%04d", ++n);
                String mutated = text.substring(0, m.start) + m.replacement + text.substring(m.end);
                Files.write(out.resolve(id + ".java"), mutated.getBytes(StandardCharsets.UTF_8));
                tsv.write(String.join("\t", id, m.operator, m.method, String.valueOf(m.line),
                        oneLine(m.original), oneLine(m.replacement)) + "\n");
            }
        }
        System.out.println(mutants.size() + " mutants");
    }

    static List<Mutant> generate(String text, String className, Set<String> methods) {
        CompilationUnit cu = parse(text);
        LineIndex index = new LineIndex(text);
        String simple = className.substring(className.lastIndexOf('.') + 1);
        String outerSimple = simple.contains("$") ? simple.substring(0, simple.indexOf('$')) : simple;
        String nestedSimple = simple.contains("$") ? simple.substring(simple.lastIndexOf('$') + 1) : simple;

        List<Mutant> out = new ArrayList<>();
        for (TypeDeclaration<?> type : cu.findAll(TypeDeclaration.class)) {
            String name = type.getNameAsString();
            if (!name.equals(nestedSimple) || (!simple.contains("$") && !type.isTopLevelType())) {
                continue;
            }
            if (simple.contains("$") && !isNestedIn(type, outerSimple)) {
                continue;
            }
            for (CallableDeclaration<?> callable : type.findAll(CallableDeclaration.class)) {
                if (nearestType(callable) != type) {
                    continue;
                }
                String mname = callable instanceof ConstructorDeclaration ? "<init>" : callable.getNameAsString();
                if (!methods.contains(mname)) {
                    continue;
                }
                new SiteVisitor(text, index, callable, mname, out).visit();
            }
        }
        return out;
    }

    private static boolean isNestedIn(TypeDeclaration<?> type, String outer) {
        Optional<Node> p = type.getParentNode();
        while (p.isPresent()) {
            if (p.get() instanceof TypeDeclaration && ((TypeDeclaration<?>) p.get()).getNameAsString().equals(outer)) {
                return true;
            }
            p = p.get().getParentNode();
        }
        return false;
    }

    private static TypeDeclaration<?> nearestType(Node n) {
        Optional<Node> p = n.getParentNode();
        while (p.isPresent()) {
            if (p.get() instanceof TypeDeclaration) {
                return (TypeDeclaration<?>) p.get();
            }
            p = p.get().getParentNode();
        }
        return null;
    }

    static CompilationUnit parse(String text) {
        ParserConfiguration.LanguageLevel[] levels = {
            ParserConfiguration.LanguageLevel.JAVA_17, ParserConfiguration.LanguageLevel.JAVA_8
        };
        for (ParserConfiguration.LanguageLevel level : levels) {
            ParserConfiguration conf = new ParserConfiguration().setLanguageLevel(level).setTabSize(1);
            ParseResult<CompilationUnit> r = new JavaParser(conf).parse(text);
            if (r.isSuccessful() && r.getResult().isPresent()) {
                return r.getResult().get();
            }
        }
        throw new IllegalArgumentException("cannot parse source");
    }

    private static String oneLine(String s) {
        return s.replace("\t", " ").replaceAll("\\s*\\R\\s*", " ");
    }

    /** Collects mutation sites inside one method or constructor, in source order. */
    private static final class SiteVisitor {
        private final String text;
        private final LineIndex index;
        private final CallableDeclaration<?> callable;
        private final String method;
        private final List<Mutant> out;

        SiteVisitor(String text, LineIndex index, CallableDeclaration<?> callable, String method, List<Mutant> out) {
            this.text = text;
            this.index = index;
            this.callable = callable;
            this.method = method;
            this.out = out;
        }

        void visit() {
            List<Node> nodes = new ArrayList<>();
            callable.walk(Node.TreeTraversal.PREORDER, nodes::add);
            for (Node n : nodes) {
                if (n == callable || insideAnnotation(n) || nestedCallable(n)) {
                    continue;
                }
                if (n instanceof BinaryExpr) {
                    binary((BinaryExpr) n);
                } else if (n instanceof UnaryExpr) {
                    unary((UnaryExpr) n);
                } else if (n instanceof ReturnStmt) {
                    returned((ReturnStmt) n);
                } else if (n instanceof ExpressionStmt) {
                    removedCall((ExpressionStmt) n);
                } else if (n instanceof IntegerLiteralExpr || n instanceof LongLiteralExpr) {
                    constant((Expression) n);
                }
            }
        }

        private boolean insideAnnotation(Node n) {
            return n.findAncestor(AnnotationExpr.class).isPresent() || n.findAncestor(SwitchEntry.class)
                    .map(e -> e.getLabels().stream().anyMatch(l -> l == n || l.isAncestorOf(n))).orElse(false);
        }

        /** Code in lambdas or local/anonymous classes belongs to a different method at bytecode level. */
        private boolean nestedCallable(Node n) {
            Optional<Node> p = n.getParentNode();
            while (p.isPresent() && p.get() != callable) {
                if (p.get() instanceof LambdaExpr || p.get() instanceof TypeDeclaration
                        || p.get() instanceof com.github.javaparser.ast.expr.ObjectCreationExpr
                        && ((com.github.javaparser.ast.expr.ObjectCreationExpr) p.get()).getAnonymousClassBody().isPresent()) {
                    return true;
                }
                p = p.get().getParentNode();
            }
            return false;
        }

        private void binary(BinaryExpr b) {
            int[] op = operatorSpan(b);
            if (op == null) {
                return;
            }
            String symbol = text.substring(op[0], op[1]);
            int line = b.getBegin().get().line;
            switch (b.getOperator()) {
                case LESS:
                    add("CONDITIONALS_BOUNDARY", line, op, "<=");
                    add("NEGATE_CONDITIONALS", line, op, ">=");
                    break;
                case LESS_EQUALS:
                    add("CONDITIONALS_BOUNDARY", line, op, "<");
                    add("NEGATE_CONDITIONALS", line, op, ">");
                    break;
                case GREATER:
                    add("CONDITIONALS_BOUNDARY", line, op, ">=");
                    add("NEGATE_CONDITIONALS", line, op, "<=");
                    break;
                case GREATER_EQUALS:
                    add("CONDITIONALS_BOUNDARY", line, op, ">");
                    add("NEGATE_CONDITIONALS", line, op, "<");
                    break;
                case EQUALS:
                    add("NEGATE_CONDITIONALS", line, op, "!=");
                    break;
                case NOT_EQUALS:
                    add("NEGATE_CONDITIONALS", line, op, "==");
                    break;
                case PLUS:
                    if (!isStringConcat(b)) {
                        add("MATH", line, op, "-");
                    }
                    break;
                case MINUS:
                    add("MATH", line, op, "+");
                    break;
                case MULTIPLY:
                    add("MATH", line, op, "/");
                    break;
                case DIVIDE:
                case REMAINDER:
                    add("MATH", line, op, "*");
                    break;
                case BINARY_AND:
                    add("MATH", line, op, "|");
                    break;
                case BINARY_OR:
                case XOR:
                    add("MATH", line, op, "&");
                    break;
                case LEFT_SHIFT:
                    add("MATH", line, op, ">>");
                    break;
                case SIGNED_RIGHT_SHIFT:
                case UNSIGNED_RIGHT_SHIFT:
                    add("MATH", line, op, "<<");
                    break;
                default:
                    break;
            }
            if (!symbol.equals(b.getOperator().asString())) {
                throw new IllegalStateException("operator mismatch at line " + line + ": " + symbol);
            }
        }

        /** The operator token lies between the end of the left operand and the start of the right one. */
        private int[] operatorSpan(BinaryExpr b) {
            Optional<Range> left = b.getLeft().getRange();
            Optional<Range> right = b.getRight().getRange();
            if (!left.isPresent() || !right.isPresent()) {
                return null;
            }
            int from = index.offset(left.get().end) + 1;
            int to = index.offset(right.get().begin);
            String between = text.substring(from, to);
            String sym = b.getOperator().asString();
            int at = indexOfToken(between, sym);
            return at < 0 ? null : new int[] {from + at, from + at + sym.length()};
        }

        /** Finds the operator outside comments and closing parentheses of the left operand. */
        private int indexOfToken(String between, String sym) {
            int i = 0;
            while (i < between.length()) {
                if (between.startsWith("//", i)) {
                    int nl = between.indexOf('\n', i);
                    i = nl < 0 ? between.length() : nl + 1;
                } else if (between.startsWith("/*", i)) {
                    int close = between.indexOf("*/", i + 2);
                    i = close < 0 ? between.length() : close + 2;
                } else if (between.startsWith(sym, i)) {
                    return i;
                } else {
                    i++;
                }
            }
            return -1;
        }

        private boolean isStringConcat(BinaryExpr b) {
            for (Node n : b.findAll(Node.class)) {
                if (n instanceof StringLiteralExpr
                        || n instanceof com.github.javaparser.ast.expr.TextBlockLiteralExpr
                        || n instanceof com.github.javaparser.ast.expr.CharLiteralExpr) {
                    return true;
                }
            }
            return false;
        }

        private void unary(UnaryExpr u) {
            int[] span = span(u);
            if (span == null) {
                return;
            }
            String src = text.substring(span[0], span[1]);
            int line = u.getBegin().get().line;
            switch (u.getOperator()) {
                case PREFIX_INCREMENT:
                case POSTFIX_INCREMENT:
                    add("INCREMENTS", line, span, src.replaceFirst("\\+\\+", "--"));
                    break;
                case PREFIX_DECREMENT:
                case POSTFIX_DECREMENT:
                    add("INCREMENTS", line, span, src.replaceFirst("--", "++"));
                    break;
                case MINUS:
                    if (!(u.getExpression() instanceof IntegerLiteralExpr || u.getExpression() instanceof LongLiteralExpr)) {
                        add("INVERT_NEGS", line, span, src.replaceFirst("^-\\s*", ""));
                    }
                    break;
                default:
                    break;
            }
        }

        private void returned(ReturnStmt r) {
            if (!r.getExpression().isPresent() || !(callable instanceof MethodDeclaration)) {
                return;
            }
            Expression e = r.getExpression().get();
            int[] span = span(e);
            if (span == null) {
                return;
            }
            int line = e.getBegin().get().line;
            Type t = ((MethodDeclaration) callable).getType();
            String type = t.asString();
            switch (type) {
                case "boolean":
                case "Boolean":
                    if (e instanceof BooleanLiteralExpr) {
                        add("RETURN_VALS", line, span, ((BooleanLiteralExpr) e).getValue() ? "false" : "true");
                    } else {
                        add("TRUE_RETURNS", line, span, "true");
                        add("FALSE_RETURNS", line, span, "false");
                    }
                    break;
                case "int":
                case "long":
                case "short":
                case "byte":
                case "char":
                case "float":
                case "double":
                case "Integer":
                case "Long":
                case "Short":
                case "Byte":
                case "Float":
                case "Double":
                    if (isZero(e)) {
                        add("PRIMITIVE_RETURNS", line, span, "1");
                    } else {
                        add("PRIMITIVE_RETURNS", line, span, "0");
                    }
                    break;
                case "String":
                    if (!(e instanceof StringLiteralExpr && ((StringLiteralExpr) e).getValue().isEmpty())) {
                        add("EMPTY_RETURNS", line, span, "\"\"");
                    }
                    if (!(e instanceof NullLiteralExpr)) {
                        add("NULL_RETURNS", line, span, "null");
                    }
                    break;
                default:
                    if (!(e instanceof NullLiteralExpr) && !t.isPrimitiveType()) {
                        add("NULL_RETURNS", line, span, "null");
                    }
                    break;
            }
        }

        private boolean isZero(Expression e) {
            String s = e.toString().replaceAll("[lLfFdD]$", "");
            return s.equals("0") || s.equals("0.0");
        }

        private void removedCall(ExpressionStmt s) {
            if (!(s.getExpression() instanceof MethodCallExpr)) {
                return;
            }
            int[] span = span(s);
            if (span == null) {
                return;
            }
            String original = text.substring(span[0], span[1]);
            StringBuilder blank = new StringBuilder(";");
            for (char c : original.toCharArray()) {
                if (c == '\n') {
                    blank.append('\n');
                }
            }
            add("VOID_METHOD_CALLS", s.getBegin().get().line, span, blank.toString());
        }

        private void constant(Expression lit) {
            if (lit.getParentNode().filter(p -> p instanceof UnaryExpr
                    && ((UnaryExpr) p).getOperator() == UnaryExpr.Operator.MINUS).isPresent()) {
                return; // negative literals are handled as part of their unary expression elsewhere
            }
            int[] span = span(lit);
            if (span == null) {
                return;
            }
            String src = text.substring(span[0], span[1]);
            String digits = src.replaceAll("[_lL]", "");
            boolean isLong = src.endsWith("l") || src.endsWith("L");
            long value;
            try {
                value = decode(digits);
            } catch (NumberFormatException e) {
                return;
            }
            String suffix = isLong ? "L" : "";
            int line = lit.getBegin().get().line;
            add("INLINE_CONSTS", line, span, (value + 1) + suffix);
            if (value != 0) {
                add("INLINE_CONSTS", line, span, (value - 1) + suffix);
            }
        }

        private long decode(String s) {
            if (s.startsWith("0x") || s.startsWith("0X")) {
                return Long.parseUnsignedLong(s.substring(2), 16);
            }
            if (s.startsWith("0b") || s.startsWith("0B")) {
                return Long.parseUnsignedLong(s.substring(2), 2);
            }
            if (s.length() > 1 && s.startsWith("0")) {
                return Long.parseUnsignedLong(s.substring(1), 8);
            }
            return Long.parseLong(s);
        }

        private int[] span(Node n) {
            Optional<Range> r = n.getRange();
            if (!r.isPresent()) {
                return null;
            }
            return new int[] {index.offset(r.get().begin), index.offset(r.get().end) + 1};
        }

        private void add(String operator, int line, int[] span, String replacement) {
            out.add(new Mutant(operator, method, line, span[0], span[1], replacement, text.substring(span[0], span[1])));
        }
    }

    /** Maps JavaParser (line, column) positions, both 1-based with tab size 1, to string offsets. */
    static final class LineIndex {
        private final int[] starts;

        LineIndex(String text) {
            List<Integer> s = new ArrayList<>();
            s.add(0);
            for (int i = 0; i < text.length(); i++) {
                char c = text.charAt(i);
                if (c == '\n') {
                    s.add(i + 1);
                } else if (c == '\r' && (i + 1 >= text.length() || text.charAt(i + 1) != '\n')) {
                    s.add(i + 1);
                }
            }
            starts = s.stream().mapToInt(Integer::intValue).toArray();
        }

        int offset(Position p) {
            return starts[p.line - 1] + p.column - 1;
        }
    }
}
