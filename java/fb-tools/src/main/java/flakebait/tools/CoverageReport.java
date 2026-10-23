package flakebait.tools;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import org.jacoco.core.analysis.Analyzer;
import org.jacoco.core.analysis.CoverageBuilder;
import org.jacoco.core.analysis.IClassCoverage;
import org.jacoco.core.analysis.ICounter;
import org.jacoco.core.analysis.IMethodCoverage;
import org.jacoco.core.data.ExecutionData;
import org.jacoco.core.data.ExecutionDataStore;
import org.jacoco.core.tools.ExecFileLoader;

/**
 * Turns per-test exec files ({@code <class>#<method>.<n>.exec}) into one CSV row per (test, covered method):
 * {@code test,class,method,desc,first_line,last_line,covered_lines}. Only classes found under the given class
 * directories (the module's production classes) are analyzed.
 */
public final class CoverageReport {

    private CoverageReport() {}

    public static void main(String[] args) throws IOException {
        Map<String, String> opts = Args.parse(args);
        List<Path> classDirs = new ArrayList<>();
        for (String d : Args.required(opts, "classes").split(File.pathSeparator)) {
            classDirs.add(Paths.get(d));
        }
        Path execs = Paths.get(Args.required(opts, "execs"));
        String include = opts.getOrDefault("include", "").replace('.', '/');

        // Several exec files for one test (parameterized or repeated runs) are merged.
        Map<String, List<Path>> byTest = new TreeMap<>();
        try (java.util.stream.Stream<Path> files = Files.list(execs)) {
            files.filter(p -> p.toString().endsWith(".exec")).forEach(p -> {
                String name = p.getFileName().toString().replaceAll("\\.\\d+\\.exec$", "");
                byTest.computeIfAbsent(name, k -> new ArrayList<>()).add(p);
            });
        }

        try (Writer out = Files.newBufferedWriter(Paths.get(Args.required(opts, "out")), StandardCharsets.UTF_8)) {
            out.write("test,class,method,desc,first_line,last_line,covered_lines\n");
            for (Map.Entry<String, List<Path>> e : byTest.entrySet()) {
                ExecFileLoader loader = new ExecFileLoader();
                for (Path p : e.getValue()) {
                    loader.load(p.toFile());
                }
                ExecutionDataStore store = loader.getExecutionDataStore();
                CoverageBuilder builder = new CoverageBuilder();
                Analyzer analyzer = new Analyzer(store, builder);
                for (ExecutionData data : store.getContents()) {
                    if (!data.hasHits() || !data.getName().startsWith(include)) {
                        continue;
                    }
                    for (Path dir : classDirs) {
                        Path cls = dir.resolve(data.getName() + ".class");
                        if (Files.isRegularFile(cls)) {
                            try (InputStream in = Files.newInputStream(cls)) {
                                analyzer.analyzeClass(in, cls.toString());
                            } catch (IOException ex) {
                                // Stale class file whose id does not match the exec data; skip it.
                            }
                            break;
                        }
                    }
                }
                for (IClassCoverage c : builder.getClasses()) {
                    for (IMethodCoverage m : c.getMethods()) {
                        int covered = m.getLineCounter().getCoveredCount();
                        if (covered == 0 && m.getInstructionCounter().getStatus() == ICounter.NOT_COVERED) {
                            continue;
                        }
                        if (covered == 0) {
                            continue;
                        }
                        out.write(String.join(",", csv(e.getKey()), c.getName().replace('/', '.'), csv(m.getName()),
                                csv(m.getDesc()), String.valueOf(m.getFirstLine()), String.valueOf(m.getLastLine()),
                                String.valueOf(covered)) + "\n");
                    }
                }
            }
        }
    }

    private static String csv(String s) {
        return s.contains(",") || s.contains("\"") ? "\"" + s.replace("\"", "\"\"") + "\"" : s;
    }
}
