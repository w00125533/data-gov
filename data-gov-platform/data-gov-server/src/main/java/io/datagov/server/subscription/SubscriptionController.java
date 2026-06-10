package io.datagov.server.subscription;

import io.datagov.common.dto.GovernanceDtos;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api")
public class SubscriptionController {
    private final SubscriptionService subscriptionService;

    public SubscriptionController(SubscriptionService subscriptionService) {
        this.subscriptionService = subscriptionService;
    }

    @PostMapping("/assets/{assetCode}/subscriptions")
    public GovernanceDtos.SubscriptionResponse createSubscription(
            @PathVariable("assetCode") String assetCode,
            @Valid @RequestBody GovernanceDtos.CreateSubscriptionRequest request
    ) {
        return subscriptionService.createSubscription(assetCode, request);
    }

    @GetMapping("/subscriptions")
    public List<GovernanceDtos.SubscriptionResponse> listSubscriptions() {
        return subscriptionService.listSubscriptions();
    }

    @GetMapping("/subscriptions/{subscriptionId}")
    public GovernanceDtos.SubscriptionResponse getSubscription(
            @PathVariable("subscriptionId") String subscriptionId
    ) {
        return subscriptionService.getSubscription(subscriptionId);
    }

    @PatchMapping("/subscriptions/{subscriptionId}")
    public GovernanceDtos.SubscriptionResponse updateSubscription(
            @PathVariable("subscriptionId") String subscriptionId,
            @Valid @RequestBody GovernanceDtos.UpdateSubscriptionRequest request
    ) {
        return subscriptionService.updateSubscription(subscriptionId, request);
    }
}
