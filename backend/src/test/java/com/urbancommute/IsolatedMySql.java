package com.urbancommute;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.regex.Pattern;
import org.springframework.boot.autoconfigure.flyway.FlywayMigrationStrategy;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.test.context.DynamicPropertyRegistry;

/** Test-only gate: no fallback to DB_URL or the application datasource. */
@TestConfiguration(proxyBeanMethods = false)
public class IsolatedMySql {
    static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalStateException("Missing isolated test setting: " + name);
        return value;
    }

    static void properties(DynamicPropertyRegistry registry) {
        String url = required("TEST_DB_URL");
        // Reject driver options such as createDatabaseIfNotExist before opening a connection.
        if (!url.matches("jdbc:mysql://127\\.0\\.0\\.1:[0-9]{1,5}/s3test_[0-9a-f]{32}\\?connectionTimeZone=UTC")) {
            throw new IllegalStateException("Refusing non-isolated test JDBC URL");
        }
        registry.add("spring.datasource.url", () -> url);
        registry.add("spring.datasource.username", () -> required("TEST_DB_USER"));
        registry.add("spring.datasource.password", () -> required("TEST_DB_PASSWORD"));
        registry.add("spring.sql.init.mode", () -> "never");
    }

    static void verify(Connection connection, String schema, String user, String serverUuid) throws SQLException {
        if (!Pattern.matches("s3test_[0-9a-f]{32}", schema)
                || !Pattern.matches("s3t_[0-9a-f]{20}", user)) {
            throw new IllegalStateException("Refusing non-isolated test identity");
        }
        try (var statement = connection.createStatement();
             var row = statement.executeQuery("SELECT DATABASE(), CURRENT_USER(), @@server_uuid")) {
            if (!row.next() || !schema.equals(row.getString(1))
                    || !user.equals(row.getString(2).split("@", 2)[0])
                    || !serverUuid.equals(row.getString(3))) {
                throw new IllegalStateException("Actual MySQL test identity mismatch; migration refused");
            }
        }
    }

    @Bean
    FlywayMigrationStrategy isolatedMigration() {
        return flyway -> {
            try (var connection = flyway.getConfiguration().getDataSource().getConnection()) {
                verify(connection, required("TEST_DB_SCHEMA"), required("TEST_DB_USER"), required("TEST_DB_SERVER_UUID"));
            } catch (SQLException exception) {
                throw new IllegalStateException("Cannot verify isolated MySQL identity", exception);
            }
            // Exercise the released V1 -> V2 upgrade path as well as later no-op restarts.
            org.flywaydb.core.Flyway.configure().configuration(flyway.getConfiguration())
                    .target("1").load().migrate();
            flyway.migrate();
        };
    }
}
