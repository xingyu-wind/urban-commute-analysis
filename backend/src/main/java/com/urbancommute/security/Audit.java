package com.urbancommute.security;

import com.urbancommute.web.RequestIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class Audit {
    private final JdbcTemplate jdbc;
    public Audit(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public void record(String actor, String action, String id, String outcome, HttpServletRequest request) {
        jdbc.update("INSERT INTO security_audit(actor,action,object_id,outcome,request_id) VALUES(?,?,?,?,?)",
                actor, action, id, outcome, RequestIdFilter.requestId(request));
    }
    // Rejected authentication must remain rejected even during database outages.
    public void rejection(String actor, String action, HttpServletRequest request) {
        try { record(actor, action, null, "DENIED", request); }
        catch (org.springframework.dao.DataAccessException ignored) {
            org.slf4j.LoggerFactory.getLogger(Audit.class).warn("Security rejection audit unavailable");
        }
    }
}
