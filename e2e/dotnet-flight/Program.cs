// .NET Flight SQL client (Apache.Arrow.Flight.Sql): run the TPC-H queries, write TSV answers for e2e/compare.py.
//   dotnet-flight <queries-dir> <out-dir> <host:port>   env: FLIGHT_TOKEN, TABLE_PREFIX (default "tpch.")
using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Apache.Arrow;
using Apache.Arrow.Arrays;
using Apache.Arrow.Flight;
using Apache.Arrow.Flight.Client;
using Apache.Arrow.Flight.Sql;
using Apache.Arrow.Flight.Sql.Client;
using Grpc.Core;
using Grpc.Net.Client;

var qdir = args[0]; var outDir = args[1]; var addr = args[2];
var prefix = Environment.GetEnvironmentVariable("TABLE_PREFIX"); if (string.IsNullOrEmpty(prefix)) prefix = "tpch.";
var token = Environment.GetEnvironmentVariable("FLIGHT_TOKEN") ?? "";
Directory.CreateDirectory(outDir);
const string tables = "lineitem|orders|customer|part|partsupp|supplier|nation|region";
var re1 = new Regex($@"\b(from|join)\s+({tables})\b", RegexOptions.IgnoreCase);
var re2 = new Regex($@",\s*({tables})\b", RegexOptions.IgnoreCase);

var channel = GrpcChannel.ForAddress("http://" + addr);
var flight = new FlightClient(channel);
var sqlClient = new FlightSqlClient(flight);
var headers = new Metadata();
if (token != "") headers.Add("authorization", "Bearer " + token);

foreach (var f in Directory.GetFiles(qdir, "*.sql").OrderBy(x => x, StringComparer.Ordinal))
{
    var name = Path.GetFileNameWithoutExtension(f);
    var sql = File.ReadAllText(f);
    sql = re1.Replace(sql, m => $"{m.Groups[1].Value} {prefix}{m.Groups[2].Value}");
    sql = re2.Replace(sql, m => $", {prefix}{m.Groups[1].Value}");
    try
    {
        var text = await Run(sql);
        File.WriteAllText(Path.Combine(outDir, name + ".tsv"), text);
    }
    catch (Exception e)
    {
        File.WriteAllText(Path.Combine(outDir, name + ".err"), string.Join(" ", e.Message.Split((char[])null, StringSplitOptions.RemoveEmptyEntries)) + "\n");
    }
}

async Task<string> Run(string sql)
{
    var opts = new FlightCallOptions { Headers = headers };
    var info = await sqlClient.ExecuteAsync(sql, options: opts);
    var sb = new StringBuilder();
    // partial mode may return several endpoints: read them all
    foreach (var ep in info.Endpoints)
    {
        using var call = flight.GetStream(ep.Ticket, headers);
        var reader = call.ResponseStream;
        while (await reader.MoveNext())
        {
            var b = reader.Current;
            for (int r = 0; r < b.Length; r++)
            {
                var cells = new string[b.ColumnCount];
                for (int c = 0; c < b.ColumnCount; c++) cells[c] = Cell(b.Column(c), r);
                sb.Append(string.Join("\t", cells)).Append('\n');
            }
        }
    }
    return sb.ToString();
}

static string Cell(IArrowArray a, int i)
{
    if (a.IsNull(i)) return "\\N";
    var inv = CultureInfo.InvariantCulture;
    switch (a)
    {
        case Decimal128Array d: return d.GetString(i);
        case Decimal256Array d: return d.GetString(i);
        case DoubleArray d: return d.GetValue(i).Value.ToString("R", inv);
        case FloatArray d: return d.GetValue(i).Value.ToString("R", inv);
        case StringArray s: return s.GetString(i);
        case LargeStringArray s: return s.GetString(i);
        case BooleanArray x: return x.GetValue(i).Value ? "true" : "false";
        case Date32Array x: return x.GetDateTime(i).Value.ToString("yyyy-MM-dd", inv);
        case Date64Array x: return x.GetDateTime(i).Value.ToString("yyyy-MM-dd", inv);
        case TimestampArray x: return x.GetTimestamp(i).Value.ToString("yyyy-MM-dd HH:mm:ss", inv);
        case Int8Array x: return x.GetValue(i).Value.ToString(inv);
        case Int16Array x: return x.GetValue(i).Value.ToString(inv);
        case Int32Array x: return x.GetValue(i).Value.ToString(inv);
        case Int64Array x: return x.GetValue(i).Value.ToString(inv);
        case UInt8Array x: return x.GetValue(i).Value.ToString(inv);
        case UInt16Array x: return x.GetValue(i).Value.ToString(inv);
        case UInt32Array x: return x.GetValue(i).Value.ToString(inv);
        case UInt64Array x: return x.GetValue(i).Value.ToString(inv);
        default: throw new NotSupportedException("column type " + a.Data.DataType.Name);
    }
}
