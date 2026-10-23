package flakebait.tools;

import java.util.Arrays;

public final class Main {

    private Main() {}

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            usage();
            return;
        }
        String[] rest = Arrays.copyOfRange(args, 1, args.length);
        switch (args[0]) {
            case "mutate":
                Mutator.main(rest);
                break;
            case "coverage":
                CoverageReport.main(rest);
                break;
            default:
                usage();
                System.exit(2);
        }
    }

    private static void usage() {
        System.err.println("usage: fb-tools mutate --src FILE --class FQN --methods m1,m2 --out DIR");
        System.err.println("       fb-tools coverage --classes DIR[:DIR] --execs DIR --out CSV [--include PREFIX]");
    }
}
