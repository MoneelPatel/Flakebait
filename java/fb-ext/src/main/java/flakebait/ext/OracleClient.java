package flakebait.ext;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

/**
 * Minimal HTTP client for the oracle sidecar. Shared by the Maven extension and the Java agent, so it uses
 * only the JDK. Every call fails closed: on any error the caller behaves like plain Maven.
 */
public final class OracleClient {

    static final String DEFAULT_URL = "http://fb-oracle:8765";

    private static volatile String override;

    private OracleClient() {}

    public static void setBaseUrl(String url) {
        override = url;
    }

    static String baseUrl() {
        if (override != null) {
            return override;
        }
        String url = System.getProperty("fb.oracle");
        return url != null ? url : DEFAULT_URL;
    }

    static boolean invocationStarted(String inv, String cwd, String command) {
        String body = "inv=" + enc(inv) + "&cwd=" + enc(cwd) + "&command=" + enc(command);
        return post("/invocation/start", body, 2000, 5000) != null;
    }

    static void invocationEnded(String inv, String result) {
        post("/invocation/end", "inv=" + enc(inv) + "&result=" + enc(result), 2000, 5000);
    }

    /** Returns the response body, or null on any failure. */
    public static String post(String path, String body, int connectTimeoutMs, int readTimeoutMs) {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(baseUrl() + path).openConnection();
            conn.setConnectTimeout(connectTimeoutMs);
            conn.setReadTimeout(readTimeoutMs);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
            try (OutputStream out = conn.getOutputStream()) {
                out.write(body.getBytes(StandardCharsets.UTF_8));
            }
            if (conn.getResponseCode() != 200) {
                return null;
            }
            try (InputStream in = conn.getInputStream()) {
                ByteArrayOutputStream buf = new ByteArrayOutputStream();
                byte[] chunk = new byte[8192];
                int n;
                while ((n = in.read(chunk)) > 0) {
                    buf.write(chunk, 0, n);
                }
                return new String(buf.toByteArray(), StandardCharsets.UTF_8);
            }
        } catch (IOException | RuntimeException e) {
            return null;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    public static String enc(String s) {
        try {
            return URLEncoder.encode(s == null ? "" : s, "UTF-8");
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }
}
