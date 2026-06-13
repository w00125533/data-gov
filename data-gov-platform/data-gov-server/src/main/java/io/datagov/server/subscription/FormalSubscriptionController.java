package io.datagov.server.subscription;

import io.datagov.common.dto.FormalSubscriptionDtos;
import io.datagov.common.enums.SubscriptionStatus;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/rest/oss/inner/modelengineservice/v1")
public class FormalSubscriptionController {
    private final SubscriptionService subscriptionService;

    public FormalSubscriptionController(SubscriptionService subscriptionService) {
        this.subscriptionService = subscriptionService;
    }

    @PostMapping("/subscriptions/{metadataId}")
    public FormalSubscriptionDtos.FormalSubscriptionResponse createSubscription(
            @PathVariable("metadataId") String metadataId,
            @Valid @RequestBody FormalSubscriptionDtos.FormalCreateSubscriptionRequest request
    ) {
        return subscriptionService.createFormalSubscription(metadataId, request);
    }

    @GetMapping("/subscriptions/{metadataId}")
    public FormalSubscriptionDtos.FormalSubscriptionListResponse listSubscriptions(
            @PathVariable("metadataId") String metadataId,
            @RequestParam(name = "consumerId", required = false) String consumerId,
            @RequestParam(name = "status", required = false) SubscriptionStatus status,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size
    ) {
        return subscriptionService.listFormalSubscriptions(metadataId, consumerId, status, page, size);
    }

    @DeleteMapping("/subscriptions/{metadataId}")
    public FormalSubscriptionDtos.FormalCancelSubscriptionResponse cancelSubscriptions(
            @PathVariable("metadataId") String metadataId,
            @Valid @RequestBody FormalSubscriptionDtos.FormalCancelSubscriptionRequest request
    ) {
        return subscriptionService.cancelFormalSubscriptions(metadataId, request);
    }
}
