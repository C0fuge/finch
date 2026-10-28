import java.io.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.LocalDate;
import java.util.*;
import java.util.regex.*;
import org.apache.arrow.flight.*;
import org.apache.arrow.flight.grpc.CredentialCallOption;
import org.apache.arrow.flight.sql.FlightSqlClient;
import org.apache.arrow.memory.RootAllocator;
import org.apache.arrow.vector.*;

/**
 * Plain Java Flight SQL client (FlightSqlClient, no JDBC), TSV answers for e2e/compare.py.
 * Run: java JavaFlight.java <queries-dir> <out-dir> <host:port>   env: FLIGHT_TOKEN, TABLE_PREFIX (default 'tpch.'),
 * FLIGHT_COMPRESSION (optional zstd|lz4 -> call header 'arrow-compression').  Reads every endpoint.
 */
public class JavaFlight {
    static String cell(FieldVector v, int i) {
        if (v.isNull(i)) return "\\N";
        if (v instanceof DateDayVector d) return LocalDate.ofEpochDay(d.get(i)).toString();
        Object o = v.getObject(i);
        if (o instanceof BigDecimal b) return b.toPlainString();
        return String.valueOf(o);
    }

    public static void main(String[] a) throws Exception {
        Path qdir = Path.of(a[0]), out = Path.of(a[1]);
        String prefix = System.getenv().getOrDefault("TABLE_PREFIX", "tpch.");
        String comp = System.getenv("FLIGHT_COMPRESSION");
        Files.createDirectories(out);
        String[] hp = a[2].split(":");
        String tables = "lineitem|orders|customer|part|partsupp|supplier|nation|region";
        List<CallOption> opts = new ArrayList<>();
        opts.add(new HeaderCallOption(hdr(comp)));
        try (var alloc = new RootAllocator();
             var fc = FlightClient.builder(alloc, Location.forGrpcInsecure(hp[0], Integer.parseInt(hp[1]))).build();
             var client = new FlightSqlClient(fc)) {
            CallOption[] co = opts.toArray(new CallOption[0]);
            List<String> names = new ArrayList<>();
            try (var s = Files.list(qdir)) { s.forEach(p -> { String n = p.getFileName().toString(); if (n.endsWith(".sql")) names.add(n.substring(0, n.length() - 4)); }); }
            Collections.sort(names);
            for (String name : names) {
                String sql = Files.readString(qdir.resolve(name + ".sql"));
                sql = Pattern.compile("\\b(from|join)\\s+(" + tables + ")\\b", Pattern.CASE_INSENSITIVE).matcher(sql).replaceAll(m -> m.group(1) + " " + prefix + m.group(2));
                sql = Pattern.compile(",\\s*(" + tables + ")\\b", Pattern.CASE_INSENSITIVE).matcher(sql).replaceAll(m -> ", " + prefix + m.group(1));
                try {
                    FlightInfo info = client.execute(sql, co);
                    StringBuilder sb = new StringBuilder();
                    for (FlightEndpoint ep : info.getEndpoints()) {
                        try (FlightStream st = client.getStream(ep.getTicket(), co)) {
                            while (st.next()) {
                                var root = st.getRoot();
                                for (int r = 0; r < root.getRowCount(); r++) {
                                    for (int c = 0; c < root.getFieldVectors().size(); c++) {
                                        if (c > 0) sb.append('\t');
                                        sb.append(cell(root.getFieldVectors().get(c), r));
                                    }
                                    sb.append('\n');
                                }
                            }
                        }
                    }
                    Files.writeString(out.resolve(name + ".tsv"), sb.toString(), StandardCharsets.UTF_8);
                } catch (Throwable t) {
                    Files.writeString(out.resolve(name + ".err"), String.valueOf(t).replaceAll("\\s+", " ") + "\n");
                }
            }
        }
    }

    static CallHeaders hdr(String comp) {
        var h = new FlightCallHeaders();
        h.insert("authorization", "Bearer " + System.getenv("FLIGHT_TOKEN"));
        if (comp != null && !comp.isEmpty()) h.insert("arrow-compression", comp);
        return h;
    }
}
