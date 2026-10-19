package com.urbancommute.repository;

import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class CityRepository {
    private final JdbcTemplate jdbc;
    private final String datasetFilter;

    public CityRepository(JdbcTemplate jdbc, @Value("${commute.cities.dataset-filter:}") String datasetFilter) {
        this.jdbc = jdbc;
        this.datasetFilter = datasetFilter;
    }

    public List<CityRow> findAll() {
        // Prepared parameters only. Neither test filter nor user input becomes SQL syntax.
        return jdbc.query("""
                SELECT c.id, c.name, d.source_type, d.dataset_id
                FROM city c JOIN dataset_registry d ON c.dataset_id = d.dataset_id
                WHERE (? = '' OR c.dataset_id = ?)
                ORDER BY c.id
                """, (rs, i) -> new CityRow(rs.getString("id"), rs.getString("name"),
                rs.getString("source_type"), rs.getString("dataset_id")), datasetFilter, datasetFilter);
    }

    public record CityRow(String id, String name, String sourceType, String datasetId) {}
}
