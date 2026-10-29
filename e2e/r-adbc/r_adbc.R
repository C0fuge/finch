# R ADBC Flight SQL client (adbcdrivermanager + adbcflightsql): run the TPC-H queries, write TSV answers for e2e/compare.py.
#
#   Rscript r_adbc.R <queries-dir> <out-dir> <host:port>   env: FLIGHT_TOKEN, TABLE_PREFIX (default "tpch.")
suppressMessages({ library(adbcdrivermanager); library(adbcflightsql) })
a <- commandArgs(TRUE)
qdir <- a[1]; out <- a[2]; addr <- a[3]
prefix <- Sys.getenv("TABLE_PREFIX", "tpch."); if (prefix == "") prefix <- "tpch."
dir.create(out, showWarnings = FALSE, recursive = TRUE)
tables <- "lineitem|orders|customer|part|partsupp|supplier|nation|region"

db <- adbc_database_init(adbcflightsql(), uri = paste0("grpc+tcp://", addr),
                         adbc.flight.sql.authorization_header = paste("Bearer", Sys.getenv("FLIGHT_TOKEN")))
con <- adbc_connection_init(db)

cell <- function(x) {
  if (is.na(x)) return("\\N")
  if (is.numeric(x) && !is.integer(x) && !inherits(x, "integer64")) return(format(x, digits = 17, scientific = FALSE, trim = TRUE))
  as.character(x)
}

for (f in sort(list.files(qdir, pattern = "\\.sql$", full.names = TRUE))) {
  name <- sub("\\.sql$", "", basename(f))
  sql <- paste(readLines(f, warn = FALSE), collapse = "\n")
  sql <- gsub(paste0("(?i)\\b(from|join)\\s+(", tables, ")\\b"), paste0("\\1 ", prefix, "\\2"), sql, perl = TRUE)
  sql <- gsub(paste0("(?i),\\s*(", tables, ")\\b"), paste0(", ", prefix, "\\1"), sql, perl = TRUE)
  res <- tryCatch({
    df <- as.data.frame(read_adbc(con, sql))
    lines <- vapply(seq_len(nrow(df)), function(i)
      paste(vapply(df, function(col) cell(col[[i]]), ""), collapse = "\t"), "")
    writeLines(lines, file.path(out, paste0(name, ".tsv")))
    NULL
  }, error = function(e) e)
  if (!is.null(res)) writeLines(paste(strsplit(conditionMessage(res), "\\s+")[[1]], collapse = " "), file.path(out, paste0(name, ".err")))
}
adbc_connection_release(con); adbc_database_release(db)
