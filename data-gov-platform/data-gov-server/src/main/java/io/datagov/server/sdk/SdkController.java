package io.datagov.server.sdk;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.server.subscription.SubscriptionService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/sdk")
public class SdkController {
    private final SubscriptionService subscriptionService;

    public SdkController(SubscriptionService subscriptionService) {
        this.subscriptionService = subscriptionService;
    }

    @PostMapping("/subscriptions/register")
    public GovernanceDtos.SdkSubscriptionRegistrationResponse registerSubscriptions(
            @Valid @RequestBody GovernanceDtos.SdkSubscriptionRegistrationRequest request
    ) {
        return subscriptionService.registerSdkSubscriptions(request);
    }

    @PostMapping("/jobs/register")
    public GovernanceDtos.JobRegistrationResponse registerJob(
            @Valid @RequestBody GovernanceDtos.JobRegistrationRequest request
    ) {
        return subscriptionService.registerJob(request);
    }
}
