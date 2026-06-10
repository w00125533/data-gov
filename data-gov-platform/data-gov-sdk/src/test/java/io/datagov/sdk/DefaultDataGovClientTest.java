package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.JobType;
import io.datagov.common.enums.UsageMode;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class DefaultDataGovClientTest {
    @Test
    void registersSubscriptions() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov-server:8080");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(requestTo("http://data-gov-server:8080/api/sdk/subscriptions/register"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(jsonPath("$.consumer.consumerName").value("rno-dashboard"))
                .andRespond(withSuccess("""
                        {
                          "consumer": {
                            "consumerId": "consumer-1",
                            "consumerType": "MICROSERVICE",
                            "consumerName": "rno-dashboard",
                            "owner": "rno",
                            "environment": "prod",
                            "runtimeVersion": null,
                            "instanceId": null,
                            "declarationHash": "hash-1",
                            "lastRegisteredAt": "2026-06-10T00:00:00Z",
                            "lastSeenAt": null
                          },
                          "subscriptions": [],
                          "assetCodeToSubscriptionId": {}
                        }
                        """, MediaType.APPLICATION_JSON));

        GovernanceDtos.SdkSubscriptionRegistrationResponse response = client.registerSubscriptions(
                new GovernanceDtos.SdkSubscriptionRegistrationRequest(
                        new GovernanceDtos.ConsumerRequest(
                                "rno-dashboard",
                                ConsumerType.MICROSERVICE,
                                "rno",
                                "prod",
                                null,
                                null
                        ),
                        "hash-1",
                        List.of(new GovernanceDtos.SubscriptionDeclarationRequest(
                                "ads_cell_profile",
                                UsageMode.API_QUERY,
                                "dashboard lookup",
                                List.of(),
                                List.of()
                        ))
                )
        );

        assertThat(response.consumer().consumerName()).isEqualTo("rno-dashboard");
        server.verify();
    }

    @Test
    void registersJobDeclaration() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov-server:8080");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(requestTo("http://data-gov-server:8080/api/sdk/jobs/register"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(jsonPath("$.jobName").value("cell-hourly-agg"))
                .andRespond(withSuccess("""
                        {
                          "jobId": "job-1",
                          "jobName": "cell-hourly-agg",
                          "jobType": "FLINK",
                          "status": "ACTIVE",
                          "consumer": {
                            "consumerId": "consumer-1",
                            "consumerType": "FLINK_JOB",
                            "consumerName": "cell-hourly-agg",
                            "owner": "rno",
                            "environment": "prod",
                            "runtimeVersion": null,
                            "instanceId": null,
                            "declarationHash": "hash-1",
                            "lastRegisteredAt": "2026-06-10T00:00:00Z",
                            "lastSeenAt": null
                          },
                          "subscriptions": [],
                          "lastRegisteredAt": "2026-06-10T00:00:00Z"
                        }
                        """, MediaType.APPLICATION_JSON));

        GovernanceDtos.JobRegistrationResponse response = client.registerJob(
                new GovernanceDtos.JobRegistrationRequest(
                        new GovernanceDtos.ConsumerRequest(
                                "cell-hourly-agg",
                                ConsumerType.FLINK_JOB,
                                "rno",
                                "prod",
                                null,
                                null
                        ),
                        "cell-hourly-agg",
                        JobType.FLINK,
                        "rno",
                        null,
                        null,
                        List.of("ods_ue_signal"),
                        List.of("dwd_session_qos"),
                        "hash-1",
                        List.of()
                )
        );

        assertThat(response.jobName()).isEqualTo("cell-hourly-agg");
        server.verify();
    }
}
