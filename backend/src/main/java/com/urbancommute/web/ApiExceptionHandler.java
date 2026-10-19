package com.urbancommute.web;

import com.urbancommute.api.ApiResponse;
import com.urbancommute.api.ResponseMeta;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.ServletWebRequest;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

@RestControllerAdvice
public class ApiExceptionHandler extends ResponseEntityExceptionHandler {
    private static final Logger LOG = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @Override
    protected ResponseEntity<Object> handleExceptionInternal(Exception exception, Object body,
            HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        return error(status, headers, ((ServletWebRequest) request).getRequest());
    }

    @ExceptionHandler(InvalidRequestException.class)
    public ResponseEntity<Object> invalidRequest(InvalidRequestException exception,
            HttpServletRequest request) {
        return error(HttpStatus.BAD_REQUEST, new HttpHeaders(), request);
    }

    @ExceptionHandler(ServiceUnavailableException.class)
    public ResponseEntity<Object> unavailable(ServiceUnavailableException exception,
            HttpServletRequest request) {
        return error(HttpStatus.SERVICE_UNAVAILABLE, new HttpHeaders(), request);
    }

    @ExceptionHandler({org.springframework.jdbc.CannotGetJdbcConnectionException.class,
            org.springframework.transaction.CannotCreateTransactionException.class})
    public ResponseEntity<Object> databaseUnavailable(Exception exception, HttpServletRequest request) {
        // Do not log connection strings, driver messages, or authentication details.
        LOG.warn("requestId={} database unavailable", RequestIdFilter.requestId(request));
        return error(HttpStatus.SERVICE_UNAVAILABLE, new HttpHeaders(), request);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Object> unexpected(Exception exception, HttpServletRequest request) {
        LOG.error("requestId={} unexpected server exception", RequestIdFilter.requestId(request), exception);
        return error(HttpStatus.INTERNAL_SERVER_ERROR, new HttpHeaders(), request);
    }

    private ResponseEntity<Object> error(HttpStatusCode status, HttpHeaders originalHeaders,
            HttpServletRequest request) {
        String code;
        String message;
        switch (status.value()) {
            case 400 -> { code = "BAD_REQUEST"; message = "Invalid request"; }
            case 404 -> { code = "NOT_FOUND"; message = "Route not found"; }
            case 405 -> { code = "METHOD_NOT_ALLOWED"; message = "Method not allowed"; }
            case 406 -> { code = "NOT_ACCEPTABLE"; message = "Only application/json is supported"; }
            case 503 -> { code = "SERVICE_UNAVAILABLE"; message = "Service unavailable"; }
            default -> { code = "INTERNAL_ERROR"; message = "Internal service error"; status = HttpStatus.INTERNAL_SERVER_ERROR; }
        }
        HttpHeaders headers = new HttpHeaders();
        headers.putAll(originalHeaders);
        // A 406 error describes the available JSON representation; it never becomes a 200 fallback.
        headers.setContentType(MediaType.APPLICATION_JSON);
        return new ResponseEntity<>(new ApiResponse<>(code, message, null,
                ResponseMeta.error(RequestIdFilter.requestId(request))), headers, status);
    }
}
