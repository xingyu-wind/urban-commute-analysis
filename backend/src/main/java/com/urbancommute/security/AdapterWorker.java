package com.urbancommute.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class AdapterWorker {
    private final ObjectMapper mapper;
    private final String python, bridge;
    private final Semaphore capacity = new Semaphore(2);
    public AdapterWorker(ObjectMapper mapper, @Value("${commute.operations.python}") String python,
            @Value("${commute.operations.bridge}") String bridge) {
        this.mapper=mapper; this.python=python; this.bridge=bridge;
    }
    public JsonNode run(Map<String,Object> input, Path directory) {
        if (!capacity.tryAcquire()) throw new OperationFailure(503,"WORKER_BUSY");
        Path result = directory.resolve("worker-" + UUID.randomUUID() + ".json");
        Process process = null;
        try {
            ProcessBuilder builder = new ProcessBuilder(python, "-I", Path.of(bridge).toAbsolutePath().toString(), result.toString());
            builder.environment().keySet().removeIf(k -> k.matches("(?i).*(password|secret|token|cookie|credential).*|DB_.*|TEST_DB_.*|COMMUTE_BOOTSTRAP_.*|GITHUB_.*"));
            builder.redirectOutput(ProcessBuilder.Redirect.DISCARD).redirectError(ProcessBuilder.Redirect.DISCARD);
            process = builder.start();
            try (var out = process.getOutputStream()) { mapper.writeValue(out, input); }
            if (!process.waitFor(45, TimeUnit.SECONDS)) throw new OperationFailure(503,"WORKER_TIMEOUT");
            if (process.exitValue()!=0 || !Files.exists(result)) throw new OperationFailure(503,"WORKER_UNAVAILABLE");
            JsonNode response = mapper.readTree(result.toFile());
            if (!response.path("ok").asBoolean()) throw new OperationFailure(422,"ADAPTER_REJECTED");
            return response.get("value");
        } catch (OperationFailure e) { throw e; }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new OperationFailure(503,"WORKER_UNAVAILABLE"); }
        catch (Exception e) { throw new OperationFailure(503,"WORKER_UNAVAILABLE"); }
        finally {
            if (process!=null && process.isAlive()) { process.destroyForcibly(); try { process.waitFor(5,TimeUnit.SECONDS); } catch(InterruptedException e) { Thread.currentThread().interrupt(); } }
            try { Files.deleteIfExists(result); }
            catch(Exception e) { throw new OperationFailure(503,"CLEANUP_FAILED"); }
            finally { capacity.release(); }
        }
    }
}
