package com.urbancommute.security;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/** Opt-in, insert-only bootstrap. No account or password exists by default. */
@Component
public class UserProvisioning implements ApplicationRunner {
    private final JdbcTemplate jdbc;
    private final PasswordEncoder encoder;
    public UserProvisioning(JdbcTemplate jdbc, PasswordEncoder encoder) { this.jdbc = jdbc; this.encoder = encoder; }
    @Override public void run(ApplicationArguments args) {
        for (String role : new String[]{"ADMIN", "READER"}) {
            String user = System.getenv("COMMUTE_BOOTSTRAP_" + role + "_USER");
            String password = System.getenv("COMMUTE_BOOTSTRAP_" + role + "_PASSWORD");
            if (user == null && password == null) continue;
            if (user == null || !user.matches("[a-zA-Z0-9_-]{3,64}") || password == null || password.length() < 16 || password.length() > 72)
                throw new IllegalStateException("Invalid explicit bootstrap identity/password policy");
            if (jdbc.queryForObject("SELECT COUNT(*) FROM app_user WHERE username=?", Integer.class, user) == 0)
                jdbc.update("INSERT INTO app_user(username,password_hash,role) VALUES(?,?,?)", user, encoder.encode(password), role);
        }
    }
}
