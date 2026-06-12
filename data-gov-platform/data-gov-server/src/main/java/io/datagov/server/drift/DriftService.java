package io.datagov.server.drift;

import io.datagov.common.dto.DriftDtos;
import io.datagov.common.enums.DriftType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class DriftService {
    private final DriftRepository driftRepository;
    private final TransactionTemplate transactionTemplate;

    public DriftService(DriftRepository driftRepository, TransactionTemplate transactionTemplate) {
        this.driftRepository = driftRepository;
        this.transactionTemplate = transactionTemplate;
    }

    public DriftDtos.DriftAnalysisResponse analyze(DriftDtos.AnalyzeDriftRequest request) {
        Instant now = Instant.now();
        Instant unusedCutoff = now.minus(days(request == null ? null : request.unusedAfterDays()), ChronoUnit.DAYS);
        Instant staleCutoff = now.minus(days(request == null ? null : request.staleAfterDays()), ChronoUnit.DAYS);
        Instant usageSince = now.minus(days(request == null ? null : request.usageLookbackDays()), ChronoUnit.DAYS);

        return transactionTemplate.execute(status -> {
            AnalysisAccumulator accumulator = new AnalysisAccumulator();
            for (DriftRepository.DriftCandidate candidate : driftRepository.findDeclaredUnusedCandidates(unusedCutoff)) {
                Map<String, Object> evidence = new LinkedHashMap<>();
                evidence.put("subscriptionId", candidate.subscriptionId());
                evidence.put("assetCode", candidate.assetCode());
                evidence.put("consumerName", candidate.consumerName());
                evidence.put("lastRuntimeSeenAt", candidate.lastRuntimeSeenAt());
                evidence.put("unusedCutoff", unusedCutoff);
                accumulator.add(process(
                        DriftType.DECLARED_UNUSED,
                        candidate,
                        "DECLARED_UNUSED:" + candidate.subscriptionId(),
                        evidence));
            }

            for (DriftRepository.DriftCandidate candidate : driftRepository.findUndeclaredUsageCandidates(usageSince)) {
                Map<String, Object> evidence = new LinkedHashMap<>();
                evidence.put("assetCode", candidate.assetCode());
                evidence.put("consumerName", candidate.consumerName());
                evidence.put("queryCount", candidate.queryCount());
                evidence.put("firstSeenAt", candidate.firstSeenAt());
                evidence.put("lastSeenAt", candidate.lastSeenAt());
                evidence.put("usageSince", usageSince);
                accumulator.add(process(
                        DriftType.UNDECLARED_USAGE,
                        candidate,
                        "UNDECLARED_USAGE:" + candidate.assetId() + ":" + candidate.consumerId(),
                        evidence));
            }

            for (DriftRepository.DriftCandidate candidate : driftRepository.findStaleDeclarationCandidates(staleCutoff)) {
                Map<String, Object> evidence = new LinkedHashMap<>();
                evidence.put("subscriptionId", candidate.subscriptionId());
                evidence.put("assetCode", candidate.assetCode());
                evidence.put("consumerName", candidate.consumerName());
                evidence.put("lastRegisteredAt", candidate.lastRegisteredAt());
                evidence.put("staleCutoff", staleCutoff);
                accumulator.add(process(
                        DriftType.STALE_DECLARATION,
                        candidate,
                        "STALE_DECLARATION:" + candidate.subscriptionId(),
                        evidence));
            }

            return new DriftDtos.DriftAnalysisResponse(
                    accumulator.createdCount,
                    accumulator.refreshedCount,
                    accumulator.records);
        });
    }

    public List<DriftDtos.DriftRecordResponse> listRecords() {
        return driftRepository.listRecords();
    }

    private ProcessedRecord process(
            DriftType driftType,
            DriftRepository.DriftCandidate candidate,
            String uniqueKey,
            Map<String, Object> evidence
    ) {
        Instant detectedAt = Instant.now();
        if (driftRepository.findOpenByUniqueKey(uniqueKey).isPresent()) {
            return new ProcessedRecord(driftRepository.refreshOpen(uniqueKey, evidence, detectedAt), false);
        }
        return new ProcessedRecord(driftRepository.insertOpen(
                newId("drift_"),
                driftType,
                candidate,
                uniqueKey,
                evidence,
                detectedAt), true);
    }

    private int days(Integer value) {
        return value == null || value <= 0 ? 30 : value;
    }

    private String newId(String prefix) {
        return prefix + UUID.randomUUID().toString().replace("-", "");
    }

    private record ProcessedRecord(DriftDtos.DriftRecordResponse record, boolean created) {
    }

    private static class AnalysisAccumulator {
        private int createdCount;
        private int refreshedCount;
        private final List<DriftDtos.DriftRecordResponse> records = new ArrayList<>();

        private void add(ProcessedRecord processedRecord) {
            records.add(processedRecord.record());
            if (processedRecord.created()) {
                createdCount++;
            } else {
                refreshedCount++;
            }
        }
    }
}
