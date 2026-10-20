#!/usr/bin/env bash
# Only run in a disposable container. No ports are published by the caller.
set -euo pipefail
[[ ${S6_ALLOW_EMPTY_FORMAT:-} == yes && ${GITHUB_ACTIONS:-} == true ]] || {
  echo 'Requires explicit authorization for a fresh, ephemeral CI NameNode'; exit 2;
}
umask 022
run_dir=$(mktemp -d /tmp/s6-warehouse.XXXXXXXX)
mkdir "$run_dir/name" "$run_dir/data" "$run_dir/conf" "$run_dir/logs"
export HADOOP_CONF_DIR="$run_dir/conf" HIVE_CONF_DIR="$run_dir/conf" TEZ_CONF_DIR="$run_dir/conf"
export HADOOP_LOG_DIR="$run_dir/logs" HADOOP_PID_DIR="$run_dir"
export HADOOP_CLASSPATH="/opt/tez/*:/opt/tez/lib/*"
export HADOOP_HEAPSIZE=512
cp /opt/hadoop/etc/hadoop/log4j.properties "$run_dir/conf/"
cat > "$run_dir/conf/core-site.xml" <<EOF
<configuration><property><name>fs.defaultFS</name><value>hdfs://127.0.0.1:9000</value></property><property><name>hadoop.tmp.dir</name><value>$run_dir/tmp</value></property></configuration>
EOF
cat > "$run_dir/conf/hdfs-site.xml" <<EOF
<configuration>
<property><name>dfs.namenode.name.dir</name><value>file://$run_dir/name</value></property>
<property><name>dfs.datanode.data.dir</name><value>file://$run_dir/data</value></property>
<property><name>dfs.replication</name><value>1</value></property>
<property><name>dfs.namenode.http-address</name><value>127.0.0.1:9870</value></property>
<property><name>dfs.datanode.address</name><value>127.0.0.1:9866</value></property>
<property><name>dfs.datanode.http.address</name><value>127.0.0.1:9864</value></property>
<property><name>dfs.datanode.ipc.address</name><value>127.0.0.1:9867</value></property>
</configuration>
EOF
cat > "$run_dir/conf/hive-site.xml" <<EOF
<configuration>
<property><name>javax.jdo.option.ConnectionURL</name><value>jdbc:derby:;databaseName=$run_dir/metastore;create=true</value></property>
<property><name>hive.metastore.warehouse.dir</name><value>/s6/warehouse</value></property>
<property><name>hive.execution.engine</name><value>tez</value></property>
<property><name>hive.server2.enable.doAs</name><value>false</value></property>
<property><name>hive.exec.submit.local.task.via.child</name><value>false</value></property>
<property><name>hive.tez.container.size</name><value>1024</value></property>
</configuration>
EOF
cat > "$run_dir/conf/tez-site.xml" <<EOF
<configuration>
<property><name>tez.local.mode</name><value>true</value></property>
<property><name>tez.runtime.optimize.local.fetch</name><value>true</value></property>
<property><name>tez.am.resource.memory.mb</name><value>1024</value></property>
<property><name>tez.lib.uris</name><value></value></property>
<property><name>tez.ignore.lib.uris</name><value>true</value></property>
</configuration>
EOF
cp "$run_dir/conf/"*.xml /evidence/
exec > >(tee /evidence/runtime.log) 2>&1
set -x
java -version
hadoop version
ls /opt/hive/lib/hive-common* /opt/tez/tez-api*
# User authorized this exact empty-directory operation. Never use -force.
[[ "$run_dir" == /tmp/s6-warehouse.* && -d "$run_dir/name" && -z "$(ls -A "$run_dir/name")" ]]
hdfs namenode -format -nonInteractive > /evidence/namenode-format.log 2>&1
hdfs --daemon start namenode
hdfs --daemon start datanode
trap 'cp -r "$run_dir/logs" /evidence/daemon-logs; hdfs --daemon stop datanode; hdfs --daemon stop namenode' EXIT
hdfs dfsadmin -safemode wait
hdfs dfsadmin -report
hdfs dfs -mkdir -p /s6/ods/snapshot_id=run1
hdfs dfs -put /bundle/ods.tsv /s6/ods/snapshot_id=run1/observations.tsv
hdfs dfs -ls -R /s6/ods
hdfs dfs -get /s6/ods/snapshot_id=run1/observations.tsv /evidence/download.tsv
sha256sum /bundle/ods.tsv /evidence/download.tsv
cmp /bundle/ods.tsv /evidence/download.tsv
schematool -dbType derby -initSchema > /evidence/schematool.log 2>&1
for iteration in first repeat; do
  beeline -u 'jdbc:hive2://' -n hive --silent=true --showHeader=false --outputformat=tsv2 \
    --hivevar snapshot=run1 --hivevar from="$S6_FROM" --hivevar to="$S6_TO" \
    -f /source/bigdata/sql/warehouse.hql > "/evidence/hive-$iteration.log" 2>&1
  hdfs dfs -getmerge /s6/export/run1 "/evidence/ads-$iteration.tsv"
done
sort /evidence/ads-first.tsv > /evidence/ads-first.sorted
sort /evidence/ads-repeat.tsv > /evidence/ads-repeat.sorted
cmp /evidence/ads-first.sorted /evidence/ads-repeat.sorted
hdfs fsck /s6 -files -blocks > /evidence/hdfs-fsck.log
echo S6_REAL_HDFS_HIVE_PASS
