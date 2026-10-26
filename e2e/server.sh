#!/usr/bin/env bash
# Start/stop S3 (rclone) + the Flight SQL server for client e2e jobs.
#   ASSETS=<dir with e2e-assets files>  WORK=<scratch dir>  e2e/server.sh start|stop
# Writes $WORK/env.sh (source it): FLIGHT_URI, FLIGHT_TOKEN. Throwaway credentials per run.
# Optional: S3_BACKEND=rclone(default)|ceph (Ceph RGW from quay.io/ceph/demo, CEPH_IMAGE)|localstack (pinned 3.8.1, path-style)|aws (real S3: needs AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, AWS_TEST_BUCKET; vhost-style, no endpoint; data under prefix finch-ci-<run id>, purged on stop), RESULT_MODE=partial|complete, SERVER_BUILD=int7|4eaab052deaf|c3b276054cc3|20b887839edf|60e888bc26ec|4d707e2aedfc|57d252b1437f, SERVER_HEAP=2g.
set -euo pipefail
WORK="${WORK:?}"; NET=afe2e; SERVER_BUILD="${SERVER_BUILD:-57d252b1437f}"; RESULT_MODE="${RESULT_MODE:-partial}"
SERVER_HEAP="${SERVER_HEAP:-2g}"; EXT=v1.4.5

start() {
  ASSETS="${ASSETS:?}"
  mkdir -p "$WORK/server" "$WORK/data" "$WORK/flight" "$WORK/duckdb/extensions/$EXT/linux_amd64"
  if [ "$SERVER_BUILD" = int7 ] || [ "$SERVER_BUILD" = int6b ]; then
    cp "$ASSETS/arrow-flight-server-1.0.0-$SERVER_BUILD.jar" "$WORK/server/server.jar"
    tar --zstd -xf "$ASSETS/$SERVER_BUILD-plugins.tar.zst" -C "$WORK/server"
    tar --zstd -xf "$ASSETS/flight-server-libs.tar.zst" -C "$WORK/server"
  else  # newer builds: <hash>, own plugins/libs archives
    cp "$ASSETS/arrow-flight-server-1.0.0-$SERVER_BUILD-linux.jar" "$WORK/server/server.jar"
    tar --zstd -xf "$ASSETS/flight-plugins-1.0.0-$SERVER_BUILD.tar.zst" -C "$WORK/server"
    tar --zstd -xf "$ASSETS/flight-server-libs-1.0.0-$SERVER_BUILD.tar.zst" -C "$WORK/server"
  fi
  mkdir -p "$WORK/server/libs"
  tar --zstd -xf "$ASSETS/test-data-sf1-types.tar.zst" -C "$WORK/data"
  curl -fsSL "http://extensions.duckdb.org/$EXT/linux_amd64/httpfs.duckdb_extension.gz" | gunzip \
    > "$WORK/duckdb/extensions/$EXT/linux_amd64/httpfs.duckdb_extension"
  local s3key="ci$(openssl rand -hex 8)" s3secret token
  s3secret="$(openssl rand -hex 24)"; token="$(openssl rand -hex 24)"
  mkdir -p "$WORK/s3/lake/parquet"
  mv "$(dirname "$(find "$WORK/data" -type d -name lineitem -print -quit)")" "$WORK/s3/lake/parquet/tpch"
  local types; types="$(find "$WORK/data" -maxdepth 2 -type d -name types -print -quit)"
  [ -z "$types" ] || mv "$types" "$WORK/s3/lake/parquet/types"
  S3_BACKEND="${S3_BACKEND:-rclone}"; local s3ep=http://s3:9000
  local bucket=lake prefix=parquet s3opts region=us-east-1
  if [ "$S3_BACKEND" = aws ]; then
    : "${AWS_ACCESS_KEY_ID:?missing secret AWS_ACCESS_KEY_ID}" "${AWS_SECRET_ACCESS_KEY:?missing secret AWS_SECRET_ACCESS_KEY}"
    : "${AWS_REGION:?missing secret AWS_REGION}" "${AWS_TEST_BUCKET:?missing secret AWS_TEST_BUCKET}"
    bucket="$AWS_TEST_BUCKET"; region="$AWS_REGION"; prefix="finch-ci-${GITHUB_RUN_ID:-local}"
    s3key="$AWS_ACCESS_KEY_ID"; s3secret="$AWS_SECRET_ACCESS_KEY"
    echo "$prefix" > "$WORK/aws-prefix"
    s3opts="-Ds3UrlStyle=vhost -Ds3Region=$region"
    docker network create $NET >/dev/null 2>&1 || true
    # load data (rclone, provider AWS); the prefix is purged in stop()
    docker run --rm --network $NET -v "$WORK/s3/lake/parquet":/data -e RCLONE_CONFIG_C_TYPE=s3 -e RCLONE_CONFIG_C_PROVIDER=AWS \
      -e RCLONE_CONFIG_C_REGION="$region" -e RCLONE_CONFIG_C_ACCESS_KEY_ID="$s3key" -e RCLONE_CONFIG_C_SECRET_ACCESS_KEY="$s3secret" \
      rclone/rclone:1.68.2 copy /data "C:$bucket/$prefix/parquet" --transfers 16 --s3-no-check-bucket
    prefix="$prefix/parquet"
  elif [ "$S3_BACKEND" = localstack ]; then
    docker network create $NET >/dev/null 2>&1 || true
    docker run -d --name s3 --network $NET -e SERVICES=s3 localstack/localstack:3.8.1 >/dev/null
    for _ in $(seq 1 60); do
      docker exec s3 curl -sf http://localhost:4566/_localstack/health >/dev/null && break; sleep 2
    done
    s3ep=http://s3:4566; s3key=test; s3secret=test
    docker run --rm --network $NET -v "$WORK/s3":/data -e RCLONE_CONFIG_C_TYPE=s3 -e RCLONE_CONFIG_C_PROVIDER=Other \
      -e RCLONE_CONFIG_C_ENDPOINT=$s3ep -e RCLONE_CONFIG_C_ACCESS_KEY_ID=test -e RCLONE_CONFIG_C_SECRET_ACCESS_KEY=test \
      rclone/rclone:1.68.2 copy /data/lake C:lake --transfers 16
  elif [ "$S3_BACKEND" = ceph ]; then
    docker network create --subnet 172.30.0.0/24 $NET >/dev/null 2>&1 || true
    docker run -d --name s3 --network $NET --ip 172.30.0.10 -e MON_IP=172.30.0.10 -e CEPH_PUBLIC_NETWORK=172.30.0.0/24 \
      -e DEMO_DAEMONS="mon,mgr,osd,rgw" -e CEPH_DEMO_UID=ci -e CEPH_DEMO_ACCESS_KEY="$s3key" \
      -e CEPH_DEMO_SECRET_KEY="$s3secret" -e CEPH_DEMO_BUCKET=lake -e RGW_FRONTEND_PORT=8080 \
      "${CEPH_IMAGE:-quay.io/ceph/demo:latest-squid}" >/dev/null
    for _ in $(seq 1 90); do
      curl -s -o /dev/null http://172.30.0.10:8080/ && break; sleep 3
    done
    docker logs s3 2>&1 | tail -15
    s3ep=http://s3:8080
    # load data: rclone copy into the bucket (provider Ceph, path-style)
    docker run --rm --network $NET -v "$WORK/s3":/data -e RCLONE_CONFIG_C_TYPE=s3 -e RCLONE_CONFIG_C_PROVIDER=Ceph \
      -e RCLONE_CONFIG_C_ENDPOINT=$s3ep -e RCLONE_CONFIG_C_ACCESS_KEY_ID="$s3key" -e RCLONE_CONFIG_C_SECRET_ACCESS_KEY="$s3secret" \
      rclone/rclone:1.68.2 copy /data/lake C:lake --transfers 16 --s3-no-check-bucket
  else
    docker network create $NET >/dev/null 2>&1 || true
    docker run -d --name s3 --network $NET -v "$WORK/s3":/data rclone/rclone:1.68.2 \
      serve s3 /data --addr :9000 --auth-key "$s3key,$s3secret" >/dev/null
  fi
  if [ "$S3_BACKEND" != aws ]; then s3opts="-Ds3Endpoint=$s3ep -Ds3UrlStyle=path -Ds3Region=us-east-1"; fi
  docker run -d --name flight1 --network $NET -p 127.0.0.1:32010:32010 \
    -v "$WORK/server":/app:ro -v "$WORK/duckdb":/ext/duckdb-home:ro -v "$WORK/flight":/work -w /work \
    -e LANG=C.UTF-8 -e FLIGHT_S3_ACCESS_KEY="$s3key" -e FLIGHT_S3_SECRET_KEY="$s3secret" \
    -e FLIGHT_AUTH_PROVIDER=token -e FLIGHT_AUTH_TOKEN="$token" eclipse-temurin:21-jdk \
    java -Xmx"$SERVER_HEAP" --add-opens=java.base/java.nio=ALL-UNNAMED -Darrow.enable_unsafe_memory_access=true \
      -DdataDir=s3://$bucket/$prefix $s3opts \
      -Darrowflight.plugins.dir=/app/plugins -Darrowflight.duckdb.extensionDir=/ext/duckdb-home/extensions \
      -DresultMode="$RESULT_MODE" -cp "/app/server.jar:/app/libs/*" \
      pro.surpin.data.arrowflight.server.HadoopArrowFlightServer --port 32010 --localhost flight1 --hosts flight1 >/dev/null
  for _ in $(seq 1 90); do
    docker logs flight1 2>&1 | grep -q 'Server Arrow Flight SQL started' && break
    docker ps -q -f name=flight1 -f status=running | grep -q . || break
    sleep 2
  done
  docker logs flight1 > "$WORK/flight1.log" 2>&1 || true
  grep -q 'Server Arrow Flight SQL started' "$WORK/flight1.log" || { tail -50 "$WORK/flight1.log"; exit 1; }
  # clients on the host reach the server via the published port; --hosts flight1 is resolved via /etc/hosts
  printf 'export FLIGHT_URI=grpc://localhost:32010\nexport FLIGHT_TOKEN=%s\n' "$token" > "$WORK/env.sh"
  echo "127.0.0.1 flight1" | sudo tee -a /etc/hosts >/dev/null
}
stop() { docker logs flight1 > "$WORK/flight1.log" 2>&1 || true
  if [ "${S3_BACKEND:-}" = aws ] && [ -s "$WORK/aws-prefix" ]; then  # delete the test prefix
    docker run --rm -e RCLONE_CONFIG_C_TYPE=s3 -e RCLONE_CONFIG_C_PROVIDER=AWS -e RCLONE_CONFIG_C_REGION="$AWS_REGION" \
      -e RCLONE_CONFIG_C_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" -e RCLONE_CONFIG_C_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
      rclone/rclone:1.68.2 purge "C:$AWS_TEST_BUCKET/$(cat "$WORK/aws-prefix")" || true
  fi
   docker rm -f grafana flight1 s3 >/dev/null 2>&1 || true; }
"${1:?start|stop}"
