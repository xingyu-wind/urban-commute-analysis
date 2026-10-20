package com.urbancommute.security;

import java.security.Principal;
import java.util.Map;
import org.springframework.security.core.Authentication;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AuthController {
    @GetMapping("/api/v1/auth/csrf") public Map<String, String> csrf(CsrfToken token) {
        return Map.of("token", token.getToken(), "headerName", token.getHeaderName());
    }
    @GetMapping("/api/v1/auth/me") public Map<String, String> me(Principal principal) {
        Authentication auth = (Authentication) principal;
        return Map.of("username", auth.getName(), "role", auth.getAuthorities().iterator().next().getAuthority().replace("ROLE_", ""));
    }
}
