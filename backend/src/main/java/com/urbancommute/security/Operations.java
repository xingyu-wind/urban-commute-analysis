package com.urbancommute.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.web.multipart.MultipartFile;

@Service
public class Operations {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final AdapterWorker worker;
    private final Audit audit;
    private final TransactionTemplate tx;
    private final Path root;
    public Operations(JdbcTemplate jdbc, ObjectMapper mapper, AdapterWorker worker, Audit audit,
            PlatformTransactionManager manager, @Value("${commute.operations.root}") String root) throws Exception {
        this.jdbc=jdbc; this.mapper=mapper; this.worker=worker; this.audit=audit; this.tx=new TransactionTemplate(manager);
        this.root=Path.of(root).toAbsolutePath().normalize();
        Files.createDirectories(this.root);
        if (!this.root.toRealPath().equals(this.root)) throw new IllegalStateException("Private root must not contain symlinks");
        try { Files.setPosixFilePermissions(this.root, java.nio.file.attribute.PosixFilePermissions.fromString("rwx------")); }
        catch (UnsupportedOperationException ignored) { /* Windows: use the owning account's private directory ACL. */ }
    }
    private Path dir(String id) {
        if (!id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")) throw new OperationFailure(400,"INVALID_ID");
        Path p=root.resolve(id);
        if (Files.isSymbolicLink(p)) throw new OperationFailure(400,"INVALID_PATH");
        return p;
    }
    private JsonNode json(Object value) {
        try { return mapper.readTree(value.toString()); } catch(Exception e) { throw new OperationFailure(503,"INVALID_STORED_STATE"); }
    }
    private Map<String,Object> row(String id) {
        dir(id);
        return jdbc.queryForList("SELECT * FROM managed_import WHERE id=?",id).stream().findFirst().orElseThrow(() -> new OperationFailure(404,"IMPORT_NOT_FOUND"));
    }
    private void erase(Path path) {
        try { Files.deleteIfExists(path); } catch(Exception e) { throw new OperationFailure(503,"CLEANUP_FAILED"); }
    }
    public Object upload(MultipartFile file, HttpServletRequest req) {
        String id=UUID.randomUUID().toString(); Path directory=dir(id); boolean retained=false;
        String ext="";
        try {
            String name=file.getOriginalFilename();
            if (name==null || !name.matches("[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,99}\\.(csv|json)")) throw new OperationFailure(400,"INVALID_FILENAME");
            ext=name.substring(name.lastIndexOf('.')+1);
            if (file.isEmpty() || file.getSize()>2*1024*1024) throw new OperationFailure(413,"FILE_SIZE");
            String type=file.getContentType();
            if (type==null || !(ext.equals("csv") ? Set.of("text/csv","application/csv","text/plain") : Set.of("application/json")).contains(type))
                throw new OperationFailure(415,"FILE_TYPE");
            Files.createDirectory(directory);
            Path raw=directory.resolve("input."+ext);
            try(var in=file.getInputStream(); var out=Files.newOutputStream(raw,java.nio.file.StandardOpenOption.CREATE_NEW)) {
                byte[] buffer=new byte[8192]; int n; long total=0;
                while((n=in.read(buffer))!=-1) { total+=n; if(total>2*1024*1024) throw new OperationFailure(413,"FILE_SIZE"); out.write(buffer,0,n); }
            }
            JsonNode proposal=worker.run(Map.of("action","inspect","file",raw.toString()),directory);
            final String extension=ext;
            tx.executeWithoutResult(s -> {
                jdbc.update("INSERT INTO managed_import(id,extension,input_sha256,proposal,created_by) VALUES(?,?,?,?,?)",
                    id,extension,proposal.path("file").path("sha256").asText(),proposal.toString(),req.getRemoteUser());
                audit.record(req.getRemoteUser(),"UPLOAD",id,"SUCCESS",req);
            });
            retained=true;
            return Map.of("id",id,"proposal",proposal);
        } catch(OperationFailure e) { audit.record(req.getRemoteUser(),"UPLOAD",id,e.code,req); throw e; }
        catch(Exception e) { audit.record(req.getRemoteUser(),"UPLOAD",id,"UPLOAD_FAILED",req); throw new OperationFailure(503,"UPLOAD_FAILED"); }
        finally {
            if (!retained && Files.exists(directory,LinkOption.NOFOLLOW_LINKS)) {
                erase(directory.resolve("input."+ext)); erase(directory);
            }
        }
    }
    public Object confirm(String id, JsonNode body, HttpServletRequest req) {
        Map<String,Object> record=row(id);
        if (body==null || body.size()!=2 || !body.has("review") || !body.has("acknowledgement")) throw new OperationFailure(400,"INVALID_CONFIRMATION");
        try {
            JsonNode config=worker.run(Map.of("action","confirm","file",dir(id).resolve("input."+record.get("extension")).toString(),
                "proposal",json(record.get("proposal")),"review",body.get("review"),"actor",req.getRemoteUser(),
                "acknowledgement",body.path("acknowledgement").asText()),dir(id));
            tx.executeWithoutResult(s -> {
                int changed=jdbc.update("UPDATE managed_import SET configuration=?,configuration_sha256=?,confirmed_by=?,confirmed_at=UTC_TIMESTAMP(3) WHERE id=? AND configuration IS NULL",
                    config.toString(),config.path("configurationSha256").asText(),req.getRemoteUser(),id);
                if(changed!=1) throw new OperationFailure(409,"ALREADY_CONFIRMED");
                audit.record(req.getRemoteUser(),"CONFIRM",id,"SUCCESS",req);
            });
            return Map.of("id",id,"configurationSha256",config.path("configurationSha256").asText(),"confirmedBy",req.getRemoteUser());
        } catch(OperationFailure e) { audit.record(req.getRemoteUser(),"CONFIRM",id,e.code,req); throw e; }
    }
    public Object execute(String id, boolean retry, HttpServletRequest req) {
        Map<String,Object> record=row(id);
        if(record.get("configuration")==null) { audit.record(req.getRemoteUser(),"IMPORT",id,"UNCONFIRMED",req); throw new OperationFailure(409,"UNCONFIRMED"); }
        String job=UUID.randomUUID().toString();
        // Compare-and-set/unique key prevents concurrent duplicate execution across server instances.
        if(retry) {
            List<Map<String,Object>> jobs=jdbc.queryForList("SELECT id FROM managed_job WHERE import_id=?",id);
            if(jobs.isEmpty()) throw new OperationFailure(409,"NOT_RETRYABLE");
            job=jobs.getFirst().get("id").toString();
        }
        final String jobId=job;
        try {
            tx.executeWithoutResult(s -> {
                if(retry) {
                    if(jdbc.update("UPDATE managed_job SET status='RUNNING',attempts=attempts+1,operated_by=?,error_code=NULL,updated_at=UTC_TIMESTAMP(3) WHERE id=? AND status='FAILED' AND attempts<3",req.getRemoteUser(),jobId)!=1)
                        throw new OperationFailure(409,"NOT_RETRYABLE");
                } else jdbc.update("INSERT INTO managed_job(id,import_id,status,operated_by,input_sha256,mapping_sha256) VALUES(?,?,'RUNNING',?,?,?)",
                        jobId,id,req.getRemoteUser(),record.get("input_sha256"),record.get("configuration_sha256"));
                audit.record(req.getRemoteUser(),retry?"RETRY":"IMPORT",jobId,"RUNNING",req);
            });
        } catch(org.springframework.dao.DuplicateKeyException e) { audit.record(req.getRemoteUser(),"IMPORT",id,"DUPLICATE",req); throw new OperationFailure(409,"ALREADY_STARTED"); }
        catch(OperationFailure e) { audit.record(req.getRemoteUser(),"RETRY",jobId,e.code,req); throw e; }
        Path output=dir(id).resolve("normalized.json");
        try {
            erase(output);
            JsonNode result=worker.run(Map.of("action","import","file",dir(id).resolve("input."+record.get("extension")).toString(),
                    "configuration",json(record.get("configuration")),"normalized",output.toString()),dir(id));
            tx.executeWithoutResult(s -> {
                jdbc.update("UPDATE managed_job SET status='SUCCEEDED',output_sha256=?,quality=?,updated_at=UTC_TIMESTAMP(3) WHERE id=? AND status='RUNNING'",
                    result.path("outputSha256").asText(),result.path("quality").toString(),jobId);
                audit.record(req.getRemoteUser(),"IMPORT_FINISHED",jobId,"SUCCEEDED",req);
            });
            return Map.of("jobId",jobId,"status","SUCCEEDED","outputSha256",result.path("outputSha256").asText(),"quality",result.path("quality"));
        } catch(Exception e) {
            erase(output);
            String code=e instanceof OperationFailure f ? f.code : "IMPORT_FAILED";
            tx.executeWithoutResult(s -> {
                jdbc.update("UPDATE managed_job SET status='FAILED',error_code=?,updated_at=UTC_TIMESTAMP(3) WHERE id=?",code,jobId);
                audit.record(req.getRemoteUser(),"IMPORT_FINISHED",jobId,code,req);
            });
            throw e instanceof OperationFailure f ? f : new OperationFailure(503,"IMPORT_FAILED");
        }
    }
    public Object tasks() {
        // Explicit projections: never expose raw file names, documents, rejected records or paths.
        return Map.of("imports",jdbc.queryForList("SELECT id,import_id,status,attempts,operated_by,input_sha256,mapping_sha256,output_sha256,error_code,updated_at FROM managed_job ORDER BY updated_at DESC LIMIT 100"),
            "etl",jdbc.queryForList("SELECT batch_id,status,attempts,source_sha256,file_sha256,input_count,written_count,error_code,started_at,finished_at FROM etl_batch ORDER BY started_at DESC LIMIT 100"),
            "hive",jdbc.queryForList("SELECT release_id,status,content_sha256,ads_sha256,row_count,error_code,published_at FROM warehouse_release ORDER BY captured_at DESC LIMIT 100"),
            "ml",jdbc.queryForList("SELECT job_id,status,model_version,dataset_id,city_id,content_sha256,data_cutoff,attempts,published_at FROM prediction_job ORDER BY generated_at DESC LIMIT 100"));
    }
}
