#!/usr/bin/env bash
# Start/stop S3 (rclone) + the Flight SQL server for client e2e jobs.
#   ASSETS=<dir with e2e-assets files>  WORK=<scratch dir>  e2e/server.sh start|stop
# Writes $WORK/env.sh (source it): FLIGHT_URI, FLIGHT_TOKEN. Throwaway credentials per run.
# Optional: RESULT_MODE=partial|complete, SERVER_BUILD=int6b, SERVER_HEAP=2g.
set -euo pipefail
WORK="${WORK:?}"; NET=afe2e; SERVER_BUILD="${SERVER_BUILD:-int6b}"; RESULT_MODE="${RESULT_MODE:-partial}"
SERVER_HEAP="${SERVER_HEAP:-2g}"; EXT=v1.4.5

start() {
  ASSETS="${ASSETS:?}"
  mkdir -p "$WORK/server" "$WORK/data" "$WORK/flight" "$WORK/duckdb/extensions/$EXT/linux_amd64"
  cp "$ASSETS/arrow-flight-server-1.0.0-$SERVER_BUILD.jar" "$WORK/server/server.jar"
  tar --zstd -xf "$ASSETS/$SERVER_BUILD-plugins.tar.zst" -C "$WORK/server"
  tar --zstd -xf "$ASSETS/flight-server-libs.tar.zst" -C "$WORK/server"
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
  docker network create $NET >/dev/null 2>&1 || true
  docker run -d --name s3 --network $NET -v "$WORK/s3":/data rclone/rclone:1.68.2 \
    serve s3 /data --addr :9000 --auth-key "$s3key,$s3secret" >/dev/null
  docker run -d --name flight1 --network $NET -p 127.0.0.1:32010:32010 \
    -v "$WORK/server":/app:ro -v "$WORK/duckdb":/ext/duckdb-home:ro -v "$WORK/flight":/work -w /work \
    -e LANG=C.UTF-8 -e FLIGHT_S3_ACCESS_KEY="$s3key" -e FLIGHT_S3_SECRET_KEY="$s3secret" \
    -e FLIGHT_AUTH_PROVIDER=token -e FLIGHT_AUTH_TOKEN="$token" eclipse-temurin:21-jdk \
    java -Xmx"$SERVER_HEAP" --add-opens=java.base/java.nio=ALL-UNNAMED -Darrow.enable_unsafe_memory_access=true \
      -DdataDir=s3://lake/parquet -Ds3Endpoint=http://s3:9000 -Ds3UrlStyle=path -Ds3Region=us-east-1 \
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
stop() { docker logs flight1 > "$WORK/flight1.log" 2>&1 || true; docker rm -f flight1 s3 >/dev/null 2>&1 || true; }
"${1:?start|stop}"
