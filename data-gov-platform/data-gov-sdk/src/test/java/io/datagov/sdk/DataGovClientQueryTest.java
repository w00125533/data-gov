package io.datagov.sdk;

import io.datagov.common.dto.QueryDtos;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withBadRequest;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class DataGovClientQueryTest {
    @Test
    void assetQueryBuilderPostsToAssetQueryEndpoint() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov-server:8080");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(requestTo("http://data-gov-server:8080/api/assets/ads_cell_profile/query"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(jsonPath("$.select[0]").value("cell_id"))
                .andExpect(jsonPath("$.select[1]").value("coverage_score"))
                .andExpect(jsonPath("$.filters[0].field").value("dt"))
                .andExpect(jsonPath("$.filters[0].op").value("="))
                .andExpect(jsonPath("$.filters[0].value").value("2026-06-10"))
                .andExpect(jsonPath("$.limit").value(100))
                .andExpect(jsonPath("$.subscriptionId").value("sub-1"))
                .andExpect(jsonPath("$.consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.environment").value("prod"))
                .andRespond(withSuccess("""
                        {
                          "queryId": "query-1",
                          "columns": ["cell_id", "coverage_score"],
                          "rows": [{"cell_id": "cell-1", "coverage_score": 98}],
                          "rowCount": 1,
                          "elapsedMs": 12
                        }
                        """, MediaType.APPLICATION_JSON));

        QueryDtos.QueryResponse response = client.asset("ads_cell_profile")
                .select("cell_id", "coverage_score")
                .where("dt", "=", LocalDate.of(2026, 6, 10))
                .limit(100)
                .subscriptionId("sub-1")
                .consumerName("rno-dashboard")
                .environment("prod")
                .query();

        assertThat(response.queryId()).isEqualTo("query-1");
        assertThat(response.rows()).containsExactly(Map.of("cell_id", "cell-1", "coverage_score", 98));
        server.verify();
    }

    @Test
    void sqlHelperPostsToSqlEndpoint() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov-server:8080");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(requestTo("http://data-gov-server:8080/api/sql"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(jsonPath("$.sql").value("select cell_id from ads_cell_profile"))
                .andExpect(jsonPath("$.limit").value(25))
                .andExpect(jsonPath("$.subscriptionId").value("sub-1"))
                .andExpect(jsonPath("$.consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.environment").value("prod"))
                .andRespond(withSuccess("""
                        {
                          "queryId": "query-2",
                          "columns": ["cell_id"],
                          "rows": [{"cell_id": "cell-1"}],
                          "rowCount": 1,
                          "elapsedMs": 8
                        }
                        """, MediaType.APPLICATION_JSON));

        QueryDtos.QueryResponse response = client.sql(new QueryDtos.SqlQueryRequest(
                "select cell_id from ads_cell_profile",
                25,
                "sub-1",
                "rno-dashboard",
                "prod"
        ));

        assertThat(response.columns()).containsExactly("cell_id");
        server.verify();
    }

    @Test
    void queryFailureThrowsDataGovClientException() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov-server:8080");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(requestTo("http://data-gov-server:8080/api/assets/ads_cell_profile/query"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withBadRequest().contentType(MediaType.APPLICATION_JSON).body("""
                        {
                          "error": "UNKNOWN_FIELD",
                          "message": "Unknown field: bad_field",
                          "path": "/api/assets/ads_cell_profile/query"
                        }
                        """));

        assertThatThrownBy(() -> client.asset("ads_cell_profile")
                .select("bad_field")
                .where("bad_field", "=", List.of("x"))
                .query())
                .isInstanceOf(DataGovClientException.class)
                .hasMessageContaining("Failed to query asset ads_cell_profile");

        server.verify();
    }
}
