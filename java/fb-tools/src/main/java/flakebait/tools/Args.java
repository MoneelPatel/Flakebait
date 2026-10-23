package flakebait.tools;

import java.util.HashMap;
import java.util.Map;

final class Args {

    private Args() {}

    static Map<String, String> parse(String[] args) {
        Map<String, String> out = new HashMap<>();
        for (int i = 0; i < args.length; i++) {
            if (args[i].startsWith("--") && i + 1 < args.length) {
                out.put(args[i].substring(2), args[++i]);
            }
        }
        return out;
    }

    static String required(Map<String, String> opts, String key) {
        String v = opts.get(key);
        if (v == null) {
            throw new IllegalArgumentException("missing --" + key);
        }
        return v;
    }
}
