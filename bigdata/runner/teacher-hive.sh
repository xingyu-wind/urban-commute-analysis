#!/usr/bin/env bash
set -euo pipefail
# Explicit modes, no fabricated CI identity. Docker must have no host Hadoop mounts.
[[ ${TEACHER_RUN_MODE:-} == local-container || ${TEACHER_RUN_MODE:-} == ci-container ]] || exit 2
run_dir=$(mktemp -d /tmp/teacher-reproduction.XXXXXXXX)
mkdir "$run_dir/name" "$run_dir/data" "$run_dir/conf" "$run_dir/logs"
export HADOOP_CONF_DIR="$run_dir/conf" HIVE_CONF_DIR="$run_dir/conf" TEZ_CONF_DIR="$run_dir/conf"
export HADOOP_LOG_DIR="$run_dir/logs" HADOOP_PID_DIR="$run_dir" HADOOP_HEAPSIZE=1024
export HADOOP_CLASSPATH='/opt/tez/*:/opt/tez/lib/*'
cp /opt/hadoop/etc/hadoop/log4j.properties "$run_dir/conf/"
cat > "$run_dir/conf/core-site.xml" <<EOF
<configuration><property><name>fs.defaultFS</name><value>hdfs://127.0.0.1:9000</value></property><property><name>hadoop.tmp.dir</name><value>$run_dir/tmp</value></property></configuration>
EOF
cat > "$run_dir/conf/hdfs-site.xml" <<EOF
<configuration><property><name>dfs.namenode.name.dir</name><value>file://$run_dir/name</value></property><property><name>dfs.datanode.data.dir</name><value>file://$run_dir/data</value></property><property><name>dfs.replication</name><value>1</value></property></configuration>
EOF
cat > "$run_dir/conf/hive-site.xml" <<EOF
<configuration><property><name>javax.jdo.option.ConnectionURL</name><value>jdbc:derby:;databaseName=$run_dir/metastore;create=true</value></property><property><name>hive.execution.engine</name><value>tez</value></property><property><name>hive.server2.enable.doAs</name><value>false</value></property><property><name>hive.exec.submit.local.task.via.child</name><value>false</value></property></configuration>
EOF
cat > "$run_dir/conf/tez-site.xml" <<EOF
<configuration><property><name>tez.local.mode</name><value>true</value></property><property><name>tez.runtime.optimize.local.fetch</name><value>true</value></property><property><name>tez.lib.uris</name><value></value></property><property><name>tez.ignore.lib.uris</name><value>true</value></property></configuration>
EOF
exec > >(tee /evidence/runtime.log) 2>&1
set -x
java -version
hadoop version
[[ "$run_dir" == /tmp/teacher-reproduction.* && -d "$run_dir/name" && -z "$(ls -A "$run_dir/name")" ]]
hdfs namenode -format -nonInteractive
hdfs --daemon start namenode
hdfs --daemon start datanode
trap 'hdfs --daemon stop datanode; hdfs --daemon stop namenode' EXIT
hdfs dfsadmin -safemode wait
hdfs dfs -mkdir -p /teacher-reproduction/ods /teacher-reproduction/manifests
hdfs dfs -put /bundle/source.tsv /teacher-reproduction/ods/observations.tsv
hdfs dfs -put /bundle/manifest.json /teacher-reproduction/manifests/manifest.json
hdfs dfs -get /teacher-reproduction/ods/observations.tsv /evidence/download.tsv
cmp /bundle/source.tsv /evidence/download.tsv
sha256sum /bundle/source.tsv /evidence/download.tsv
schematool -dbType derby -initSchema
beeline -u 'jdbc:hive2://' -n root --silent=true --showHeader=false --outputformat=tsv2 -f /source/bigdata/sql/teacher-reproduction.hql
for topic in daily weekday hour road_length; do
  hdfs dfs -getmerge "/teacher-reproduction/export/$topic" "/evidence/$topic.tsv"
done
hdfs dfs -ls -R /teacher-reproduction
hdfs fsck /teacher-reproduction -files -blocks
echo TEACHER_REAL_HDFS_HIVE_PASS
