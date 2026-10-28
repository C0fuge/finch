import java.sql.*;
import java.util.*;

/**
 * JDBC DatabaseMetaData conformance as DBeaver / DataGrip call it (Arrow Flight SQL JDBC driver).
 * Run: java -cp flight-sql-jdbc-driver.jar MetaConformance.java <host:port> <report-file>   env: FLIGHT_TOKEN
 * Levels: FAIL = a tool cannot show the schema tree / column list; GAP = degraded but usable; OK.
 */
public class MetaConformance {
    static final List<String> rows = new ArrayList<>();
    static int fails = 0;
    static final List<String> pending = new ArrayList<>();
    static void info(String x) { pending.add(x); }

    interface Check { String run() throws Exception; } // returns null = OK, else "GAP: ..." / "FAIL: ..."

    static void check(String name, Check c) {
        String res;
        try { String r = c.run(); res = r == null ? "OK" : r; }
        catch (Throwable t) { res = "FAIL: threw " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).replaceAll("\\s+", " "); }
        if (res.startsWith("FAIL")) fails++;
        String line = String.format("%-4s %-40s %s", res.startsWith("OK") ? "OK" : res.substring(0, 4), name, res.startsWith("OK") ? "" : res.substring(res.indexOf(": ") + 2));
        rows.add(line.stripTrailing());
        for (String x : pending) { System.out.println(x); }
        rows.addAll(pending); pending.clear();
        System.out.println(line.stripTrailing());
    }

    static List<List<String>> rs(ResultSet r, String... cols) throws SQLException {
        List<List<String>> out = new ArrayList<>();
        while (r.next()) { List<String> row = new ArrayList<>(); for (String c : cols) row.add(r.getString(c)); out.add(row); }
        r.close();
        return out;
    }

    public static void main(String[] a) throws Exception {
        String user = System.getenv("FLIGHT_USER"), trust = System.getenv("FLIGHT_TRUSTSTORE");
        // login mode (LDAP): TLS with the throwaway cert in a JKS truststore, user/password; else plaintext + bearer token
        String url = user == null ? "jdbc:arrow-flight-sql://" + a[0] + "/?useEncryption=false&token=" + System.getenv("FLIGHT_TOKEN")
            : "jdbc:arrow-flight-sql://" + a[0] + "/?useEncryption=true&trustStore=" + trust + "&trustStorePassword=changeit";
        if (user != null) {
            try (Connection bad = DriverManager.getConnection(url + "&user=" + user + "&password=" + System.getenv("FLIGHT_BAD_PASSWORD"))) {
                bad.getMetaData().getCatalogs().close();
                fails++; info("FAIL: wrong password accepted");
            } catch (SQLException e) { info("OK: wrong password refused: " + String.valueOf(e.getMessage()).split("\n")[0]); }
            url += "&user=" + user + "&password=" + System.getenv("FLIGHT_PASSWORD");
        }
        String[] tpch = {"customer", "lineitem", "nation", "orders", "part", "partsupp", "region", "supplier"};
        try (Connection c = DriverManager.getConnection(url)) {
            DatabaseMetaData m = c.getMetaData();
            check("product name/version", () -> {
                String n = m.getDatabaseProductName(), v = m.getDatabaseProductVersion();
                info("     info: product=" + n + " " + v + " driver=" + m.getDriverName() + " " + m.getDriverVersion()
                    + " jdbc=" + m.getJDBCMajorVersion() + "." + m.getJDBCMinorVersion());
                return n == null || n.isEmpty() ? "GAP: empty product name" : null; });
            check("getCatalogs", () -> {
                var l = rs(m.getCatalogs(), "TABLE_CAT"); info("     catalogs=" + l); return null; });
            check("getSchemas lists tpch", () -> {
                var l = rs(m.getSchemas(), "TABLE_SCHEM"); info("     schemas=" + l);
                return l.stream().anyMatch(x -> "tpch".equals(x.get(0))) ? null : "FAIL: no schema tpch in " + l; });
            check("getSchemas(null,'tp%')", () -> {
                var l = rs(m.getSchemas(null, "tp%"), "TABLE_SCHEM"); return l.size() >= 1 ? null : "GAP: schema pattern ignored/empty"; });
            check("getTableTypes", () -> {
                var l = rs(m.getTableTypes(), "TABLE_TYPE"); info("     tableTypes=" + l); return l.isEmpty() ? "GAP: empty" : null; });
            check("getTables(tpch, all types)", () -> {
                var l = rs(m.getTables(null, "tpch", "%", null), "TABLE_NAME", "TABLE_TYPE");
                Set<String> got = new TreeSet<>(); for (var r : l) got.add(r.get(0));
                info("     tables=" + l);
                return got.containsAll(Arrays.asList(tpch)) ? null : "FAIL: missing tables, got " + got; });
            check("getTables(types=TABLE)", () -> {
                var l = rs(m.getTables(null, "tpch", "%", new String[]{"TABLE"}), "TABLE_NAME");
                return l.size() >= 8 ? null : "GAP: type filter TABLE returns " + l.size() + " rows (DBeaver filters by TABLE/VIEW)"; });
            check("getTables name pattern 'line%'", () -> {
                var l = rs(m.getTables(null, "tpch", "line%", null), "TABLE_NAME");
                return l.size() == 1 ? null : "GAP: pattern gives " + l; });
            check("getTables TABLE_CAT/SCHEM/REMARKS", () -> {
                try (ResultSet r = m.getTables(null, "tpch", "region", null)) {
                    if (!r.next()) return "FAIL: region not found";
                    info("     region: cat=" + r.getString("TABLE_CAT") + " schem=" + r.getString("TABLE_SCHEM") + " type=" + r.getString("TABLE_TYPE") + " remarks=" + r.getString("REMARKS"));
                    return r.getString("TABLE_SCHEM") == null ? "GAP: TABLE_SCHEM null" : null; } });
            check("getColumns(lineitem) names+order", () -> {
                var l = rs(m.getColumns(null, "tpch", "lineitem", "%"), "COLUMN_NAME", "TYPE_NAME", "DATA_TYPE", "ORDINAL_POSITION", "NULLABLE", "COLUMN_SIZE", "DECIMAL_DIGITS");
                for (var r : l) info("     lineitem." + r);
                if (l.size() != 16) return "FAIL: " + l.size() + " columns, expected 16";
                String first = l.get(0).get(0), last = l.get(15).get(0);
                if (!"l_orderkey".equals(first) || !"l_comment".equals(last)) return "FAIL: order " + first + ".." + last;
                return null; });
            check("getColumns ORDINAL_POSITION", () -> {
                var l = rs(m.getColumns(null, "tpch", "lineitem", "%"), "ORDINAL_POSITION");
                for (int i = 0; i < l.size(); i++) if (!String.valueOf(i + 1).equals(l.get(i).get(0))) return "GAP: ordinal " + l.get(i).get(0) + " at index " + i;
                return null; });
            check("getColumns types (decimal/date)", () -> {
                Map<String, String> t = new HashMap<>();
                for (var r : rs(m.getColumns(null, "tpch", "lineitem", "%"), "COLUMN_NAME", "TYPE_NAME", "DATA_TYPE")) t.put(r.get(0), r.get(1) + "/" + r.get(2));
                info("     l_quantity=" + t.get("l_quantity") + " l_shipdate=" + t.get("l_shipdate") + " l_orderkey=" + t.get("l_orderkey") + " l_comment=" + t.get("l_comment"));
                String d = t.get("l_shipdate"), q = t.get("l_quantity");
                if (d == null || !(d.contains("DATE") || d.contains("date") || d.endsWith("/91"))) return "GAP: l_shipdate type " + d;
                if (q == null || !(q.toUpperCase().contains("DEC") || q.endsWith("/3") || q.endsWith("/2"))) return "GAP: l_quantity type " + q;
                return null; });
            check("getColumns(null,null,'%','%') all", () -> {
                int n = 0; try (ResultSet r = m.getColumns(null, "tpch", "%", "%")) { while (r.next()) n++; }
                return n >= 61 ? null : "GAP: only " + n + " columns across tpch (expect 61)"; });
            check("getPrimaryKeys(region)", () -> {
                var l = rs(m.getPrimaryKeys(null, "tpch", "region"), "COLUMN_NAME"); return l.isEmpty() ? null : "GAP: returns " + l; });
            check("getImportedKeys(lineitem)", () -> {
                var l = rs(m.getImportedKeys(null, "tpch", "lineitem"), "PKTABLE_NAME"); return l.isEmpty() ? null : "GAP: returns " + l; });
            check("getExportedKeys(region)", () -> {
                var l = rs(m.getExportedKeys(null, "tpch", "region"), "FKTABLE_NAME"); return l.isEmpty() ? null : "GAP: returns " + l; });
            check("getIndexInfo(region)", () -> {
                try (ResultSet r = m.getIndexInfo(null, "tpch", "region", false, true)) { int n = 0; while (r.next()) n++; return n == 0 ? null : "GAP: " + n + " rows"; } });
            check("getTypeInfo", () -> {
                int n = 0; try (ResultSet r = m.getTypeInfo()) { while (r.next()) n++; } info("     typeInfo rows=" + n); return n > 0 ? null : "GAP: empty"; });
            check("getProcedures", () -> { try (ResultSet r = m.getProcedures(null, null, "%")) { return null; } });
            check("getFunctions", () -> { try (ResultSet r = m.getFunctions(null, null, "%")) { return null; } });
            check("getSQLKeywords", () -> { String k = m.getSQLKeywords(); info("     keywords.length=" + (k == null ? -1 : k.length())); return k == null || k.isEmpty() ? "GAP: empty (editor highlighting/completion)" : null; });
            check("getIdentifierQuoteString", () -> { String q = m.getIdentifierQuoteString(); info("     quote='" + q + "'"); return "\"".equals(q) ? null : "GAP: quote '" + q + "'"; });
            check("getSearchStringEscape", () -> { info("     escape='" + m.getSearchStringEscape() + "'"); return null; });
            check("getStringFunctions/Numeric/Time", () -> { info("     fn lengths " + m.getStringFunctions().length() + "/" + m.getNumericFunctions().length() + "/" + m.getTimeDateFunctions().length() + "/" + m.getSystemFunctions().length()); return null; });
            Map<String, Check> sq = new LinkedHashMap<>();
            sq.put("supportsTransactions", () -> "" + m.supportsTransactions());
            sq.put("supportsBatchUpdates", () -> "" + m.supportsBatchUpdates());
            sq.put("supportsSchemasInDataManipulation", () -> "" + m.supportsSchemasInDataManipulation());
            sq.put("supportsCatalogsInDataManipulation", () -> "" + m.supportsCatalogsInDataManipulation());
            sq.put("supportsGroupBy", () -> "" + m.supportsGroupBy());
            sq.put("supportsOuterJoins", () -> "" + m.supportsOuterJoins());
            sq.put("supportsSubqueriesInExists", () -> "" + m.supportsSubqueriesInExists());
            sq.put("supportsUnion", () -> "" + m.supportsUnion());
            sq.put("isReadOnly", () -> "" + m.isReadOnly());
            sq.put("storesLowerCaseIdentifiers", () -> "" + m.storesLowerCaseIdentifiers());
            sq.put("storesMixedCaseIdentifiers", () -> "" + m.storesMixedCaseIdentifiers());
            sq.put("nullsAreSortedHigh", () -> "" + m.nullsAreSortedHigh());
            sq.put("supportsMixedCaseIdentifiers", () -> "" + m.supportsMixedCaseIdentifiers());
            sq.put("getMaxColumnsInTable", () -> "" + m.getMaxColumnsInTable());
            sq.put("getDefaultTransactionIsolation", () -> "" + m.getDefaultTransactionIsolation());
            sq.put("supportsSelectForUpdate", () -> "" + m.supportsSelectForUpdate());
            sq.put("supportsStoredProcedures", () -> "" + m.supportsStoredProcedures());
            sq.put("supportsResultSetType(FORWARD_ONLY)", () -> "" + m.supportsResultSetType(ResultSet.TYPE_FORWARD_ONLY));
            for (var e : sq.entrySet()) {
                check("SqlInfo " + e.getKey(), () -> {
                    try { info("     " + e.getKey() + "=" + e.getValue().run()); return null; }
                    catch (NullPointerException | UnsupportedOperationException | SQLException x) { return "GAP: " + x.getClass().getSimpleName() + " (server does not report this SqlInfo)"; }
                });
            }
            check("getURL/getUserName", () -> { info("     user=" + m.getUserName()); return null; });
            check("connection.getCatalog/getSchema", () -> { info("     catalog=" + c.getCatalog() + " schema=" + c.getSchema()); return null; });
            check("ResultSetMetaData of SELECT", () -> {
                try (Statement s = c.createStatement(); ResultSet r = s.executeQuery("select * from tpch.lineitem limit 1")) {
                    ResultSetMetaData md = r.getMetaData();
                    StringBuilder sb = new StringBuilder("     ");
                    for (int i = 1; i <= md.getColumnCount(); i++) sb.append(md.getColumnName(i)).append(':').append(md.getColumnTypeName(i)).append(' ');
                    rows.add(sb.toString().stripTrailing());
                    return md.getColumnCount() == 16 ? null : "FAIL: " + md.getColumnCount() + " columns"; } });
            check("read-only/autocommit/valid", () -> { info("     autocommit=" + c.getAutoCommit() + " readOnly=" + c.isReadOnly() + " valid=" + c.isValid(5)); return c.isValid(5) ? null : "GAP: isValid false"; });
            check("PreparedStatement parameter metadata", () -> {
                try (PreparedStatement p = c.prepareStatement("select * from tpch.region where r_regionkey = ?")) {
                    p.setInt(1, 1);
                    try (ResultSet r = p.executeQuery()) { int n = 0; while (r.next()) n++; return n == 1 ? null : "GAP: " + n + " rows"; } } });
            check("metadata via SQL: information_schema", () -> {
                try (Statement s = c.createStatement(); ResultSet r = s.executeQuery("select table_schema, table_name from information_schema.tables where table_schema='tpch' order by 2")) {
                    int n = 0; while (r.next()) n++; return n >= 8 ? null : "GAP: " + n + " rows"; } });
        }
        java.nio.file.Files.write(java.nio.file.Path.of(a[1]), rows);
        System.out.println(fails == 0 ? "no FAIL" : fails + " FAIL");
        System.exit(fails == 0 ? 0 : 1);
    }
}
