package com.urbancommute.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.urbancommute.api.ApiResponse;
import com.urbancommute.api.ResponseMeta;
import com.urbancommute.web.RequestIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {
    @Bean PasswordEncoder passwordEncoder() { return new BCryptPasswordEncoder(12); }
    @Bean UserDetailsService users(JdbcTemplate jdbc) {
        return name -> jdbc.query("SELECT username,password_hash,role,enabled FROM app_user WHERE username=?", (rs, row) ->
                User.withUsername(rs.getString(1)).password(rs.getString(2)).roles(rs.getString(3))
                    .disabled(!rs.getBoolean(4)).build(), name).stream().findFirst()
                .orElseThrow(() -> new UsernameNotFoundException("Invalid credentials"));
    }
    public static void error(ObjectMapper mapper, HttpServletRequest req, HttpServletResponse res, int status) throws IOException {
        res.setStatus(status); res.setContentType("application/json");
        String code = switch(status) { case 401 -> "UNAUTHORIZED"; case 503 -> "SERVICE_UNAVAILABLE"; default -> "FORBIDDEN"; };
        mapper.writeValue(res.getOutputStream(), new ApiResponse<>(code,
                status == 401 ? "Authentication required" : status == 503 ? "Service unavailable" : "Access denied", null,
                ResponseMeta.error(RequestIdFilter.requestId(req))));
    }
    @Bean SecurityFilterChain security(HttpSecurity http, ObjectMapper mapper, Audit audit) throws Exception {
        var denied = (org.springframework.security.web.access.AccessDeniedHandler) (req, res, ex) -> {
            var auth = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
            boolean signedIn = auth != null && auth.isAuthenticated() && !(auth instanceof org.springframework.security.authentication.AnonymousAuthenticationToken);
            audit.rejection(signedIn ? auth.getName() : "anonymous", "ACCESS_DENIED", req);
            error(mapper, req, res, signedIn ? 403 : 401);
        };
        http.authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.GET, "/health", "/api/v1/cities", "/api/v1/traffic/**",
                        "/api/v1/warehouse/**", "/api/v1/predictions", "/api/v1/auth/csrf").permitAll()
                .requestMatchers("/api/v1/auth/login").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/v1/operations/tasks").hasAnyRole("ADMIN", "READER")
                .requestMatchers("/api/v1/operations/**").hasRole("ADMIN")
                .requestMatchers("/api/v1/auth/**").authenticated()
                // Preserve legacy controller's own 404/405 contracts for non-management routes.
                .anyRequest().permitAll())
            .requestCache(cache -> cache.disable())
            .exceptionHandling(e -> e.authenticationEntryPoint((req, res, ex) -> { audit.rejection("anonymous","AUTH_REQUIRED",req); error(mapper, req, res, 401); })
                    .accessDeniedHandler(denied))
            .csrf(csrf -> csrf.requireCsrfProtectionMatcher(req ->
                (req.getServletPath().startsWith("/api/v1/auth/") || req.getServletPath().startsWith("/api/v1/operations/"))
                && !java.util.Set.of("GET", "HEAD", "OPTIONS", "TRACE").contains(req.getMethod())))
            .formLogin(form -> form.loginPage("/api/v1/auth/me").loginProcessingUrl("/api/v1/auth/login")
                .successHandler((req, res, auth) -> {
                    try { audit.record(auth.getName(), "LOGIN", null, "SUCCESS", req); }
                    catch (org.springframework.dao.DataAccessException e) {
                        new org.springframework.security.web.authentication.logout.SecurityContextLogoutHandler().logout(req,res,auth);
                        error(mapper,req,res,503); return;
                    }
                    res.setContentType("application/json"); mapper.writeValue(res.getOutputStream(), java.util.Map.of("authenticated", true));
                })
                .failureHandler((req, res, ex) -> {
                    // Never persist attacker-supplied usernames or credentials in audit.
                    audit.rejection("anonymous", "LOGIN_FAILED", req); error(mapper, req, res, 401);
                }))
            .logout(logout -> logout.logoutUrl("/api/v1/auth/logout").deleteCookies("JSESSIONID")
                .addLogoutHandler((req, res, auth) -> {
                    if (auth != null) try { audit.record(auth.getName(), "LOGOUT", null, "SUCCESS", req); }
                    catch (org.springframework.dao.DataAccessException e) {
                        org.slf4j.LoggerFactory.getLogger(SecurityConfig.class).warn("Logout audit unavailable; session invalidation continues");
                    }
                })
                .logoutSuccessHandler((req, res, auth) -> { res.setContentType("application/json"); res.getWriter().write("{\"authenticated\":false}"); }));
        return http.build();
    }
}
