package io.datagov.sandbox;

// 用户代码块完整替换该类体内容。
// 约定 sink 路径: hdfs:///tmp/sandbox/out/${sandbox_uuid}/
// 用户可以使用占位符 ${sandbox_uuid} 在常量字符串里引用 uuid。
public final class SandboxFlinkJob {
    public static final String SANDBOX_UUID = "${sandbox_uuid}";
    public static final String SANDBOX_OUTPUT = "hdfs:///tmp/sandbox/out/" + SANDBOX_UUID;

    ${user_code_block}
}
