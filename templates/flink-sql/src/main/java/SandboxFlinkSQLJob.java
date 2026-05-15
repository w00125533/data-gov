import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.table.api.EnvironmentSettings;
import org.apache.flink.table.api.bridge.java.StreamTableEnvironment;

public final class SandboxFlinkSQLJob {
    public static void main(String[] args) throws Exception {
        String sandboxUuid = "${sandbox_uuid}";
        String outputPath = "hdfs:///tmp/sandbox/out/" + sandboxUuid;

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        StreamTableEnvironment tEnv = StreamTableEnvironment.create(
            env, EnvironmentSettings.newInstance().inStreamingMode().build());

        // 默认 sink 表 - 用户 SQL 可以用 INSERT INTO sandbox_sink 写入
        tEnv.executeSql(String.format(
            "CREATE TABLE sandbox_sink (data STRING) WITH (" +
            "  'connector' = 'filesystem', " +
            "  'path' = '%s', " +
            "  'format' = 'json'" +
            ")", outputPath));

        // 用户 SQL 注入点 — 多条语句用 ; 分隔
        String userSql = "${user_sql}";
        for (String stmt : userSql.split(";")) {
            String trimmed = stmt.trim();
            if (!trimmed.isEmpty()) {
                tEnv.executeSql(trimmed);
            }
        }
    }
}
