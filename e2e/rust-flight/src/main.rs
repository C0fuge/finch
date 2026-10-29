// Rust Flight SQL client (arrow-flight crate, FlightSqlServiceClient): run the TPC-H queries, write TSV answers for e2e/compare.py.
//
//   rust-flight <queries-dir> <out-dir> <host:port>   env: FLIGHT_TOKEN, TABLE_PREFIX (default "tpch.")
use arrow_array::Array;
use arrow_cast::display::{ArrayFormatter, FormatOptions};
use arrow_flight::sql::client::FlightSqlServiceClient;
use futures::TryStreamExt;
use regex::Regex;
use std::{env, fs};
use tonic::transport::Endpoint;

const TABLES: &str = "lineitem|orders|customer|part|partsupp|supplier|nation|region";

#[tokio::main]
async fn main() {
    let a: Vec<String> = env::args().collect();
    let (qdir, out, addr) = (&a[1], &a[2], &a[3]);
    let prefix = env::var("TABLE_PREFIX").ok().filter(|s| !s.is_empty()).unwrap_or("tpch.".into());
    fs::create_dir_all(out).unwrap();
    let channel = Endpoint::from_shared(format!("http://{addr}")).unwrap().connect().await.expect("connect");
    let mut client = FlightSqlServiceClient::new(channel);
    client.set_token(env::var("FLIGHT_TOKEN").unwrap_or_default());

    let re1 = Regex::new(&format!(r"(?i)\b(from|join)\s+({TABLES})\b")).unwrap();
    let re2 = Regex::new(&format!(r"(?i),\s*({TABLES})\b")).unwrap();
    let mut files: Vec<_> = fs::read_dir(qdir).unwrap().map(|e| e.unwrap().path())
        .filter(|p| p.extension().map_or(false, |x| x == "sql")).collect();
    files.sort();
    for f in files {
        let name = f.file_stem().unwrap().to_string_lossy().to_string();
        let sql = fs::read_to_string(&f).unwrap();
        let sql = re1.replace_all(&sql, format!("${{1}} {prefix}${{2}}").as_str()).to_string();
        let sql = re2.replace_all(&sql, format!(", {prefix}${{1}}").as_str()).to_string();
        match run(&mut client, sql).await {
            Ok(t) => fs::write(format!("{out}/{name}.tsv"), t).unwrap(),
            Err(e) => fs::write(format!("{out}/{name}.err"), format!("{}\n", e.split_whitespace().collect::<Vec<_>>().join(" "))).unwrap(),
        }
    }
}

async fn run(client: &mut FlightSqlServiceClient<tonic::transport::Channel>, sql: String) -> Result<String, String> {
    let info = client.execute(sql, None).await.map_err(|e| e.to_string())?;
    let mut text = String::new();
    // partial mode may return several endpoints: read them all (each may carry its own location; ours are all reachable via the same channel)
    for ep in info.endpoint {
        let ticket = ep.ticket.ok_or("endpoint without ticket")?;
        let stream = client.do_get(ticket).await.map_err(|e| e.to_string())?;
        let batches: Vec<_> = stream.try_collect().await.map_err(|e| e.to_string())?;
        let opts = FormatOptions::default().with_null("\\N");
        for b in batches {
            let fmts: Vec<_> = b.columns().iter().map(|c| ArrayFormatter::try_new(c.as_ref(), &opts).unwrap()).collect();
            for r in 0..b.num_rows() {
                let cells: Vec<String> = fmts.iter().zip(b.columns()).map(|(f, c)| {
                    if c.is_null(r) { "\\N".to_string() } else { f.value(r).to_string() }
                }).collect();
                text.push_str(&cells.join("\t"));
                text.push('\n');
            }
        }
    }
    Ok(text)
}
