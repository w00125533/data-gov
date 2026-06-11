package io.datagov.server.common;

import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.event.EventDataAccessException;
import io.datagov.server.lineage.LineageDataAccessException;
import io.datagov.server.lineage.LineageValidationException;
import io.datagov.server.query.QueryExecutionException;
import io.datagov.server.query.QueryValidationException;
import io.datagov.server.subscription.AssetCodeMismatchException;
import io.datagov.server.subscription.SubscriptionDataAccessException;
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

    @ExceptionHandler(AssetCodeMismatchException.class)
    public ResponseEntity<Map<String, Object>> handleAssetCodeMismatch(AssetCodeMismatchException ex) {
        return ResponseEntity.badRequest()
                .body(Map.of(
                        "error", "ASSET_CODE_MISMATCH",
                        "detail", ex.getMessage(),
                        "pathAssetCode", ex.getPathAssetCode(),
                        "bodyAssetCode", ex.getBodyAssetCode()));
    }

    @ExceptionHandler(SubscriptionNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleSubscriptionNotFound(SubscriptionNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of(
                        "error", "SUBSCRIPTION_NOT_FOUND",
                        "detail", ex.getMessage()));
    }

    @ExceptionHandler(SubscriptionDataAccessException.class)
    public ResponseEntity<Map<String, Object>> handleSubscriptionDataAccess(SubscriptionDataAccessException ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of(
                        "error", "SUBSCRIPTION_DATA_ACCESS_ERROR",
                        "detail", ex.getMessage()));
    }

    @ExceptionHandler(EventDataAccessException.class)
    public ResponseEntity<Map<String, Object>> handleEventDataAccess(EventDataAccessException ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of(
                        "error", "EVENT_DATA_ACCESS_ERROR",
                        "message", ex.getMessage()));
    }

    @ExceptionHandler(QueryValidationException.class)
    public ResponseEntity<Map<String, Object>> handleQueryValidation(QueryValidationException ex) {
        return ResponseEntity.badRequest()
                .body(Map.of(
                        "error", ex.getErrorCode(),
                        "message", ex.getMessage()));
    }

    @ExceptionHandler(QueryExecutionException.class)
    public ResponseEntity<Map<String, Object>> handleQueryExecution(QueryExecutionException ex) {
        HttpStatus status = "STARROCKS_NOT_CONFIGURED".equals(ex.getErrorCode())
                ? HttpStatus.SERVICE_UNAVAILABLE
                : HttpStatus.INTERNAL_SERVER_ERROR;
        return ResponseEntity.status(status)
                .body(Map.of(
                        "error", ex.getErrorCode(),
                        "message", ex.getMessage()));
    }

    @ExceptionHandler(LineageValidationException.class)
    public ResponseEntity<Map<String, Object>> handleLineageValidation(LineageValidationException ex) {
        return ResponseEntity.badRequest()
                .body(Map.of(
                        "error", ex.getErrorCode(),
                        "message", ex.getMessage()));
    }

    @ExceptionHandler(LineageDataAccessException.class)
    public ResponseEntity<Map<String, Object>> handleLineageDataAccess(LineageDataAccessException ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of(
                        "error", "LINEAGE_DATA_ACCESS_ERROR",
                        "message", ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException ex) {
        return ResponseEntity.badRequest()
                .body(Map.of(
                        "error", "VALIDATION_ERROR",
                        "message", "Request validation failed"));
    }
}
