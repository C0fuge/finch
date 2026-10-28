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

    interface Check { String run() throws Exception; } // returns null = OK, else "GAP: ..." / "FAIL: ..."

    static void check(String name, Check c) {
        String res;
        try { String r = c.run(); res = r == null ? "OK" : r; }
        catch (Throwable t) { res = "FAIL: threw " + t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).replaceAll("\\s+", " "); }
        if (res.startsWith("FAIL")) fails++;
        String line = String.format("%-4s %-40s %s", res.startsWith("OK") ? "OK" : res.substring(0, 4), name, res.startsWith("OK") ? "" : res.substring(Math.min(6, res.length())));
        rows.add(line.stripTrailing());
        System.out.println(line.stripTrailing());
    }

    static List<List<String>> rs(ResultSet r, String... cols) throws SQLException {
        List<List<String>> out = new ArrayList<>();
        while (r.next()) { List<String> row = new ArrayList<>(); for (String c : cols) row.add(r.getString(c)); out.add(row); }
        r.close();
        return out;
    }

    public static void main(String[] a) throws Exception {
        String url = "jdbc:arrow-flight-sql://" + a[0] + "/?useEncryption=false&token=" + System.getenv("FLIGHT_TOKEN");
        String[] tpch = {"customer", "lineitem", "nation", "orders", "part", "partsupp", "region", "supplier"};
        try (Connection c = DriverManager.getConnection(url)) {
            DatabaseMetaData m = c.getMetaData();
            check("product name/version", () -> {
                String n = m.getDatabaseProductName(), v = m.getDatabaseProductVersion();
                rows.add("     info: product=" + n + " " + v + " driver=" + m.getDriverName() + " " + m.getDriverVersion()
                    + " jdbc=" + m.getJDBCMajorVersion() + "." + m.getJDBCMinorVersion());
                return n == null || n.isEmpty() ? "GAP: empty product name" : null; });
            check("getCatalogs", () -> {
                var l = rs(m.getCatalogs(), "TABLE_CAT"); rows.add("     catalogs=" + l); return null; });
            check("getSchemas lists tpch", () -> {
                var l = rs(m.getSchemas(), "TABLE_SCHEM"); rows.add("     schemas=" + l);
                return l.stream().anyMatch(x -> "tpch".equals(x.get(0))) ? null : "FAIL: no schema tpch in " + l; });
            check("getSchemas(null,'tp%')", () -> {
                var l = rs(m.getSchemas(null, "tp%"), "TABLE_SCHEM"); return l.size() >= 1 ? null : "GAP: schema pattern ignored/empty"; });
            check("getTableTypes", () -> {
                var l = rs(m.getTableTypes(), "TABLE_TYPE"); rows.add("     tableTypes=" + l); return l.isEmpty() ? "GAP: empty" : null; });
            check("getTables(tpch, all types)", () -> {
                var l = rs(m.getTables(null, "tpch", "%", null), "TABLE_NAME", "TABLE_TYPE");
                Set<String> got = new TreeSet<>(); for (var r : l) got.add(r.get(0));
                rows.add("     tables=" + l);
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
                    rows.add("     region: cat=" + r.getString("TABLE_CAT") + " schem=" + r.getString("TABLE_SCHEM") + " type=" + r.getString("TABLE_TYPE") + " remarks=" + r.getString("REMARKS"));
                    return r.getString("TABLE_SCHEM") == null ? "GAP: TABLE_SCHEM null" : null; } });
            check("getColumns(lineitem) names+order", () -> {
                var l = rs(m.getColumns(null, "tpch", "lineitem", "%"), "COLUMN_NAME", "TYPE_NAME", "DATA_TYPE", "ORDINAL_POSITION", "NULLABLE", "COLUMN_SIZE", "DECIMAL_DIGITS");
                for (var r : l) rows.add("     lineitem." + r);
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
                rows.add("     l_quantity=" + t.get("l_quantity") + " l_shipdate=" + t.get("l_shipdate") + " l_orderkey=" + t.get("l_orderkey") + " l_comment=" + t.get("l_comment"));
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
                int n = 0; try (ResultSet r = m.getTypeInfo()) { while (r.next()) n++; } rows.add("     typeInfo rows=" + n); return n > 0 ? null : "GAP: empty"; });
            check("getProcedures", () -> { try (ResultSet r = m.getProcedures(null, null, "%")) { return null; } });
            check("getFunctions", () -> { try (ResultSet r = m.getFunctions(null, null, "%")) { return null; } });
            check("getSQLKeywords", () -> { String k = m.getSQLKeywords(); rows.add("     keywords.length=" + (k == null ? -1 : k.length())); return k == null || k.isEmpty() ? "GAP: empty (editor highlighting/completion)" : null; });
            check("getIdentifierQuoteString", () -> { String q = m.getIdentifierQuoteString(); rows.add("     quote='" + q + "'"); return "\"".equals(q) ? null : "GAP: quote '" + q + "'"; });
            check("getSearchStringEscape", () -> { rows.add("     escape='" + m.getSearchStringEscape() + "'"); return null; });
            check("getStringFunctions/Numeric/Time", () -> { rows.add("     fn lengths " + m.getStringFunctions().length() + "/" + m.getNumericFunctions().length() + "/" + m.getTimeDateFunctions().length() + "/" + m.getSystemFunctions().length()); return null; });
            check("supports* (SqlInfo)", () -> {
                rows.add("     supportsTransactions=" + m.supportsTransactions() + " supportsBatch=" + m.supportsBatchUpdates() + " supportsSchemasInDML=" + m.supportsSchemasInDataManipulation()
                    + " supportsCatalogsInDML=" + m.supportsCatalogsInDataManipulation() + " supportsGroupBy=" + m.supportsGroupBy() + " supportsOuterJoins=" + m.supportsOuterJoins()
                    + " supportsSubqueriesInExists=" + m.supportsSubqueriesInExists() + " supportsUnion=" + m.supportsUnion() + " isReadOnly=" + m.isReadOnly()
                    + " storesLowerCase=" + m.storesLowerCaseIdentifiers() + " storesMixed=" + m.storesMixedCaseIdentifiers() + " nullsSortedHigh=" + m.nullsAreSortedHigh()
                    + " maxCols=" + m.getMaxColumnsInTable() + " defaultTxn=" + m.getDefaultTransactionIsolation());
                return null; });
            check("getURL/getUserName", () -> { rows.add("     user=" + m.getUserName()); return null; });
            check("connection.getCatalog/getSchema", () -> { rows.add("     catalog=" + c.getCatalog() + " schema=" + c.getSchema()); return null; });
            check("ResultSetMetaData of SELECT", () -> {
                try (Statement s = c.createStatement(); ResultSet r = s.executeQuery("select * from tpch.lineitem limit 1")) {
                    ResultSetMetaData md = r.getMetaData();
                    StringBuilder sb = new StringBuilder("     ");
                    for (int i = 1; i <= md.getColumnCount(); i++) sb.append(md.getColumnName(i)).append(':').append(md.getColumnTypeName(i)).append(' ');
                    rows.add(sb.toString().stripTrailing());
                    return md.getColumnCount() == 16 ? null : "FAIL: " + md.getColumnCount() + " columns"; } });
            check("read-only/autocommit/valid", () -> { rows.add("     autocommit=" + c.getAutoCommit() + " readOnly=" + c.isReadOnly() + " valid=" + c.isValid(5)); return c.isValid(5) ? null : "GAP: isValid false"; });
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
