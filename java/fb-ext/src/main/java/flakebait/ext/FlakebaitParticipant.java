package flakebait.ext;

import java.io.File;
import java.net.URISyntaxException;
import java.util.Properties;
import java.util.UUID;

import javax.inject.Named;
import javax.inject.Singleton;

import org.apache.maven.AbstractMavenLifecycleParticipant;
import org.apache.maven.MavenExecutionException;
import org.apache.maven.execution.MavenSession;
import org.apache.maven.model.Plugin;
import org.apache.maven.model.PluginExecution;
import org.apache.maven.project.MavenProject;
import org.codehaus.plexus.util.xml.Xpp3Dom;

/**
 * Core extension that attaches this jar as a Java agent to every Surefire fork.
 *
 * <p>Victim mode (default): active only when the oracle answers. Each Maven invocation gets an id that the
 * agent sends with every flaky-test execution, so the oracle draws once per invocation and logs the command.
 *
 * <p>Coverage mode ({@code -Dfb.coverage=<dir>}): also attaches the JaCoCo agent given by {@code -Dfb.jacoco}
 * and dumps one exec file per test into the directory.
 */
@Named("flakebait")
@Singleton
public class FlakebaitParticipant extends AbstractMavenLifecycleParticipant {

    private static final String SUREFIRE = "maven-surefire-plugin";

    private String invocationId;
    private boolean victimMode;

    @Override
    public void afterProjectsRead(MavenSession session) throws MavenExecutionException {
        Properties user = session.getUserProperties();
        String agentJar = ownJar();
        if (agentJar == null) {
            return;
        }

        String javaagent;
        String coverageDir = user.getProperty("fb.coverage");
        String repeat = user.getProperty("fb.repeat");
        if (repeat != null) {
            javaagent = "-javaagent:" + agentJar + "=repeat=" + repeat;
        } else if (coverageDir != null) {
            String jacoco = user.getProperty("fb.jacoco", "/opt/fb/jacocoagent.jar");
            javaagent = "-javaagent:" + jacoco + "=output=none,dumponexit=false"
                    + " -javaagent:" + agentJar + "=coverage=" + coverageDir;
        } else {
            invocationId = UUID.randomUUID().toString();
            String command = System.getProperty("sun.java.command", "");
            String cwd = session.getRequest().getBaseDirectory();
            if (!OracleClient.invocationStarted(invocationId, cwd, command)) {
                return; // No oracle reachable: behave exactly like plain Maven.
            }
            victimMode = true;
            javaagent = "-javaagent:" + agentJar + "=inv=" + invocationId;
        }

        for (MavenProject project : session.getProjects()) {
            for (Plugin plugin : project.getBuildPlugins()) {
                if (SUREFIRE.equals(plugin.getArtifactId())) {
                    attach(project, plugin, javaagent, user);
                }
            }
        }
    }

    @Override
    public void afterSessionEnd(MavenSession session) {
        if (victimMode) {
            boolean failed = session.getResult() != null && session.getResult().hasExceptions();
            OracleClient.invocationEnded(invocationId, failed ? "FAILURE" : "SUCCESS");
        }
    }

    /**
     * Executions carry their own copy of the plugin-level configuration (expanded while the model was built),
     * so the agent is added to the plugin and to every execution.
     */
    private static void attach(MavenProject project, Plugin plugin, String javaagent, Properties user) {
        Xpp3Dom conf = (Xpp3Dom) plugin.getConfiguration();
        if (conf == null) {
            conf = new Xpp3Dom("configuration");
            plugin.setConfiguration(conf);
        }
        addAgent(conf, project, javaagent, user);
        for (PluginExecution execution : plugin.getExecutions()) {
            Xpp3Dom execConf = (Xpp3Dom) execution.getConfiguration();
            if (execConf == null) {
                execConf = new Xpp3Dom("configuration");
                execution.setConfiguration(execConf);
            }
            addAgent(execConf, project, javaagent, user);
        }
    }

    private static void addAgent(Xpp3Dom conf, MavenProject project, String javaagent, Properties user) {
        Xpp3Dom argLine = conf.getChild("argLine");
        if (argLine != null) {
            if (!argLine.getValue().contains(javaagent)) {
                argLine.setValue(join(argLine.getValue(), javaagent));
            }
            return;
        }
        // Without an explicit <argLine>, Surefire reads the argLine property; keep whatever it would have used.
        String base;
        if (user.getProperty("argLine") != null) {
            base = user.getProperty("argLine");
        } else if (project.getProperties().getProperty("argLine") != null) {
            base = project.getProperties().getProperty("argLine");
        } else if (setsArgLineAtRuntime(project)) {
            base = "@{argLine}";
        } else {
            base = null;
        }
        Xpp3Dom child = new Xpp3Dom("argLine");
        child.setValue(join(base, javaagent));
        conf.addChild(child);
    }

    /** JaCoCo's prepare-agent goal sets the argLine property only once the build is running. */
    private static boolean setsArgLineAtRuntime(MavenProject project) {
        for (Plugin p : project.getBuildPlugins()) {
            if ("jacoco-maven-plugin".equals(p.getArtifactId())) {
                return true;
            }
        }
        return false;
    }

    private static String join(String base, String extra) {
        return base == null || base.trim().isEmpty() ? extra : base + " " + extra;
    }

    private static String ownJar() {
        try {
            File f = new File(FlakebaitParticipant.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            return f.isFile() ? f.getAbsolutePath() : null;
        } catch (URISyntaxException | RuntimeException e) {
            return null;
        }
    }
}
