package io.datagov.server.common;

import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.subscription.SubscriptionNotFoundException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(AssetNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleAssetNotFound(AssetNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of(
                        "error", "ASSET_NOT_FOUND",
                        "message", ex.getMessage(),
                        "assetCode", ex.getAssetCode()));
    }

    @ExceptionHandler(SubscriptionNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleSubscriptionNotFound(SubscriptionNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of(
                        "error", "SUBSCRIPTION_NOT_FOUND",
                        "detail", ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException ex) {
        return ResponseEntity.badRequest()
                .body(Map.of(
                        "error", "VALIDATION_ERROR",
                        "message", "Request validation failed"));
    }
}
