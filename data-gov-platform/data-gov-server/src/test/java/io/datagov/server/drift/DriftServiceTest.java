package io.datagov.server.drift;

import io.datagov.common.dto.DriftDtos;
import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DriftServiceTest {
    private final DriftRepository driftRepository = mock(DriftRepository.class);
    private final DriftService driftService = new DriftService(driftRepository, transactionTemplate());

    @Test
    void analyzeReopensExistingNonOpenRecordForUniqueKey() {
        DriftRepository.DriftCandidate candidate = declaredUnusedCandidate("sub_existing");
        DriftDtos.DriftRecordResponse ignored = record("drift_existing", DriftStatus.IGNORED, null);
        DriftDtos.DriftRecordResponse reopened = record("drift_existing", DriftStatus.OPEN, null);
        when(driftRepository.findDeclaredUnusedCandidates(any())).thenReturn(List.of(candidate));
        when(driftRepository.findUndeclaredUsageCandidates(any())).thenReturn(List.of());
        when(driftRepository.findStaleDeclarationCandidates(any())).thenReturn(List.of());
        when(driftRepository.findByUniqueKey("DECLARED_UNUSED:sub_existing")).thenReturn(Optional.of(ignored));
        when(driftRepository.refreshOrReopenByUniqueKey(eq("DECLARED_UNUSED:sub_existing"), any(), any()))
                .thenReturn(reopened);

        DriftDtos.DriftAnalysisResponse response = driftService.analyze(new DriftDtos.AnalyzeDriftRequest(30, 90, 7));

        assertThat(response.createdCount()).isZero();
        assertThat(response.refreshedCount()).isEqualTo(1);
        assertThat(response.records()).containsExactly(reopened);
        verify(driftRepository, never()).insertOpen(any(), any(), any(), any(), any(), any());
    }

    @Test
    void analyzeRefreshesWinnerWhenConcurrentInsertCreatesDuplicateUniqueKey() {
        DriftRepository.DriftCandidate candidate = declaredUnusedCandidate("sub_race");
        DriftDtos.DriftRecordResponse reopened = record("drift_winner", DriftStatus.OPEN, null);
        when(driftRepository.findDeclaredUnusedCandidates(any())).thenReturn(List.of(candidate));
        when(driftRepository.findUndeclaredUsageCandidates(any())).thenReturn(List.of());
        when(driftRepository.findStaleDeclarationCandidates(any())).thenReturn(List.of());
        when(driftRepository.findByUniqueKey("DECLARED_UNUSED:sub_race")).thenReturn(Optional.empty());
        when(driftRepository.insertOpen(any(), eq(DriftType.DECLARED_UNUSED), eq(candidate),
                eq("DECLARED_UNUSED:sub_race"), any(), any()))
                .thenThrow(new DriftRepository.DuplicateDriftUniqueKeyException("DECLARED_UNUSED:sub_race", null));
        when(driftRepository.refreshOrReopenByUniqueKey(eq("DECLARED_UNUSED:sub_race"), any(), any()))
                .thenReturn(reopened);

        DriftDtos.DriftAnalysisResponse response = driftService.analyze(new DriftDtos.AnalyzeDriftRequest(30, 90, 7));

        assertThat(response.createdCount()).isZero();
        assertThat(response.refreshedCount()).isEqualTo(1);
        assertThat(response.records()).containsExactly(reopened);
    }

    @Test
    void analyzeUsesSameDetectedAtForAllRecordsInOneRun() {
        List<Instant> detectedAtValues = new ArrayList<>();
        DriftRepository.DriftCandidate first = declaredUnusedCandidate("sub_one");
        DriftRepository.DriftCandidate second = declaredUnusedCandidate("sub_two");
        when(driftRepository.findDeclaredUnusedCandidates(any())).thenReturn(List.of(first, second));
        when(driftRepository.findUndeclaredUsageCandidates(any())).thenReturn(List.of());
        when(driftRepository.findStaleDeclarationCandidates(any())).thenReturn(List.of());
        when(driftRepository.findByUniqueKey(any())).thenReturn(Optional.empty());
        when(driftRepository.insertOpen(any(), any(), any(), any(), any(), any())).thenAnswer(invocation -> {
            Instant detectedAt = invocation.getArgument(5);
            detectedAtValues.add(detectedAt);
            Thread.sleep(2);
            return record(invocation.getArgument(0), DriftStatus.OPEN, detectedAt);
        });

        driftService.analyze(new DriftDtos.AnalyzeDriftRequest(30, 90, 7));

        assertThat(detectedAtValues).hasSize(2);
        assertThat(detectedAtValues.get(0)).isEqualTo(detectedAtValues.get(1));
    }

    private DriftRepository.DriftCandidate declaredUnusedCandidate(String subscriptionId) {
        return new DriftRepository.DriftCandidate(
                subscriptionId,
                "asset_1",
                "ads_cell_profile",
                "consumer_1",
                "rno-dashboard",
                null,
                Instant.parse("2026-01-01T00:00:00Z"),
                0,
                null,
                null);
    }

    private DriftDtos.DriftRecordResponse record(String driftId, DriftStatus status, Instant detectedAt) {
        return new DriftDtos.DriftRecordResponse(
                driftId,
                DriftType.DECLARED_UNUSED,
                status,
                "asset_1",
                "ads_cell_profile",
                "consumer_1",
                "rno-dashboard",
                "sub_existing",
                Map.of(),
                detectedAt == null ? Instant.parse("2026-02-01T00:00:00Z") : detectedAt,
                status == DriftStatus.OPEN ? null : Instant.parse("2026-02-02T00:00:00Z"));
    }

    private TransactionTemplate transactionTemplate() {
        return new TransactionTemplate(new PlatformTransactionManager() {
            @Override
            public TransactionStatus getTransaction(TransactionDefinition definition) {
                return new SimpleTransactionStatus();
            }

            @Override
            public void commit(TransactionStatus status) {
            }

            @Override
            public void rollback(TransactionStatus status) {
            }
        });
    }
}
