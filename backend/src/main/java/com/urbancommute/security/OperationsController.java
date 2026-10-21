package com.urbancommute.security;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/operations")
public class OperationsController {
    private final Operations operations;
    public OperationsController(Operations operations) { this.operations=operations; }
    @GetMapping("/tasks") public Object tasks() { return operations.tasks(); }
    @PostMapping(value="/uploads", consumes="multipart/form-data") public Object upload(@RequestPart("file") MultipartFile file, HttpServletRequest request) { return operations.upload(file,request); }
    @PostMapping("/imports/{id}/confirm") public Object confirm(@PathVariable String id, @RequestBody JsonNode body, HttpServletRequest req) { return operations.confirm(id,body,req); }
    @PostMapping("/imports/{id}/execute") public Object execute(@PathVariable String id, HttpServletRequest req) { return operations.execute(id,false,req); }
    @PostMapping("/imports/{id}/retry") public Object retry(@PathVariable String id, HttpServletRequest req) { return operations.execute(id,true,req); }
}
