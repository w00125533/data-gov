package io.datagov.server.subscription;

public class SubscriptionNotFoundException extends RuntimeException {
    private final String subscriptionId;

    public SubscriptionNotFoundException(String subscriptionId) {
        super("Subscription not found: " + subscriptionId);
        this.subscriptionId = subscriptionId;
    }

    public String getSubscriptionId() {
        return subscriptionId;
    }
}
