package com.urbancommute.security;

public class OperationFailure extends RuntimeException {
    public final int status;
    public final String code;
    public OperationFailure(int status, String code) { super(code); this.status=status; this.code=code; }
}
