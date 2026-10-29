// Go ADBC Flight SQL client: run the TPC-H queries, write TSV answers for e2e/compare.py.
//
//	go run . <queries-dir> <out-dir> <host:port>   env: FLIGHT_TOKEN, FLIGHT_COMPRESSION (zstd|lz4), TABLE_PREFIX
package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/apache/arrow-adbc/go/adbc"
	"github.com/apache/arrow-adbc/go/adbc/driver/flightsql"
	"github.com/apache/arrow-go/v18/arrow/memory"
)

const tables = "lineitem|orders|customer|part|partsupp|supplier|nation|region"

func main() {
	qdir, out, addr := os.Args[1], os.Args[2], os.Args[3]
	prefix := os.Getenv("TABLE_PREFIX")
	if prefix == "" {
		prefix = "tpch."
	}
	must(os.MkdirAll(out, 0o755))
	opts := map[string]string{
		adbc.OptionKeyURI:                  "grpc+tcp://" + addr,
		flightsql.OptionAuthorizationHeader: "Bearer " + os.Getenv("FLIGHT_TOKEN"),
	}
	if c := os.Getenv("FLIGHT_COMPRESSION"); c != "" {
		opts[flightsql.OptionRPCCallHeaderPrefix+"arrow-compression"] = c
	}
	ctx := context.Background()
	db, err := flightsql.NewDriver(memory.DefaultAllocator).NewDatabase(opts)
	must(err)
	defer db.Close()
	conn, err := db.Open(ctx)
	must(err)
	defer conn.Close()

	files, _ := filepath.Glob(filepath.Join(qdir, "*.sql"))
	sort.Strings(files)
	re1 := regexp.MustCompile(`(?i)\b(from|join)\s+(` + tables + `)\b`)
	re2 := regexp.MustCompile(`(?i),\s*(` + tables + `)\b`)
	for _, f := range files {
		name := strings.TrimSuffix(filepath.Base(f), ".sql")
		b, err := os.ReadFile(f)
		must(err)
		sql := re1.ReplaceAllString(string(b), "${1} "+prefix+"${2}")
		sql = re2.ReplaceAllString(sql, ", "+prefix+"${1}")
		if text, err := run(ctx, conn, sql); err != nil {
			must(os.WriteFile(filepath.Join(out, name+".err"), []byte(strings.Join(strings.Fields(err.Error()), " ")+"\n"), 0o644))
		} else {
			must(os.WriteFile(filepath.Join(out, name+".tsv"), []byte(text), 0o644))
		}
	}
}

func run(ctx context.Context, conn adbc.Connection, sql string) (string, error) {
	st, err := conn.NewStatement()
	if err != nil {
		return "", err
	}
	defer st.Close()
	if err := st.SetSqlQuery(sql); err != nil {
		return "", err
	}
	rr, _, err := st.ExecuteQuery(ctx)
	if err != nil {
		return "", err
	}
	defer rr.Release()
	var sb strings.Builder
	for rr.Next() {
		rec := rr.Record()
		for r := 0; r < int(rec.NumRows()); r++ {
			for c := 0; c < int(rec.NumCols()); c++ {
				if c > 0 {
					sb.WriteByte('\t')
				}
				col := rec.Column(c)
				if col.IsNull(r) {
					sb.WriteString(`\N`)
				} else {
					sb.WriteString(col.ValueStr(r))
				}
			}
			sb.WriteByte('\n')
		}
	}
	return sb.String(), rr.Err()
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
