import org.apache.spark.sql.Dataset;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.SparkSession;

public final class SandboxSparkJob {
    public static void main(String[] args) {
        String sandboxUuid = "${sandbox_uuid}";
        String outputPath = "hdfs:///tmp/sandbox/out/" + sandboxUuid;

        SparkSession spark = SparkSession.builder()
            .appName("data-gov-sandbox-" + sandboxUuid)
            .enableHiveSupport()
            .getOrCreate();

        // 用户 SQL 注入点（一条 SELECT；DDL 用户用 spark.sql() 串内）
        String userSql = "${user_sql}";
        Dataset<Row> df = spark.sql(userSql);
        df.limit(1).coalesce(1).write().mode("overwrite").json(outputPath);

        spark.stop();
    }
}
