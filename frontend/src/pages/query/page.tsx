import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Play,
  Database,
  Table2,
  Loader2,
  AlertCircle,
  CheckCircle,
  Clock,
  Code2,
  Network
} from "lucide-react";
import { toast } from "sonner";
import api, { databasesApi } from "@/services/api";
import SchemaGraph from "./components/schema-graph";
import DataEditor from "./components/data-editor";

interface TableInfo {
  name: string;
  type: string;
}

interface QueryResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms: number;
}

export default function QueryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialDbId = searchParams.get("dbId") ? parseInt(searchParams.get("dbId")!) : null;
  const [databaseId, setDatabaseId] = useState<number | null>(initialDbId);
  const [allDatabases, setAllDatabases] = useState<unknown[]>([]);

  const [query, setQuery] = useState("SELECT * FROM ");
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("sql");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingTables, setLoadingTables] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadDatabases = useCallback(async () => {
    try {
      const response = await databasesApi.getAll();
      setAllDatabases(response.data);
      if (response.data.length > 0 && !databaseId) {
        setDatabaseId(response.data[0].id);
        setSearchParams({ dbId: response.data[0].id.toString() });
      }
    } catch (err) {
      console.error("Failed to load databases:", err);
    }
  }, [databaseId, setSearchParams]);

  // Load all databases
  useEffect(() => {
    loadDatabases();
  }, [loadDatabases]);

  // Load database info and tables when db changes
  useEffect(() => {
    if (databaseId) {
      loadTables(databaseId);
    } else {
      setTables([]);
    }
  }, [databaseId, allDatabases]);

  const handleDatabaseChange = (val: string) => {
    const id = parseInt(val);
    setDatabaseId(id);
    setSearchParams({ dbId: id.toString() });
    setTables([]); // Clear tables to show loading
    setResult(null); // Clear previous results
    setQuery("SELECT * FROM ");
  };


  const loadTables = async (dbId: number) => {
    setLoadingTables(true);
    try {
      const response = await api.get(`/databases/${dbId}/tables`);
      setTables(response.data);
    } catch (err) {
      console.error("Failed to load tables:", err);
    } finally {
      setLoadingTables(false);
    }
  };

  const executeQuery = async () => {
    if (!query.trim()) {
      toast.error("Please enter a query");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.post(`/databases/${databaseId}/query`, { query, limit: 1000 });
      setResult(response.data);
      toast.success(`Query returned ${response.data.row_count} rows in ${response.data.execution_time_ms}ms`);

      // If the query was a DDL command (CREATE, ALTER, DROP), refresh the tables list
      if (query.match(/\b(CREATE|ALTER|DROP)\b/i) && databaseId) {
        loadTables(databaseId);
      }
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage = apiErr.response?.data?.detail || apiErr.message || "Query execution failed";
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleTableClick = (tableName: string) => {
    setSelectedTable(tableName);
    setActiveTab("data");
    setQuery(`SELECT * FROM ${tableName} LIMIT 100;`);
  };

  const formatCellValue = (value: unknown): string => {
    if (value === null) return "NULL";
    if (value === undefined) return "";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  return (
    <div className="h-full flex flex-col p-6 space-y-4 bg-background">
      {/* Header */}
      <Card className="shadow-sm">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="h-5 w-5 text-muted-foreground" />
            <div>
              <h1 className="text-xl font-semibold">
                Query Editor
              </h1>
              {allDatabases.length > 0 && (
                <div className="mt-1">
                  <Select
                    value={databaseId ? databaseId.toString() : undefined}
                    onValueChange={handleDatabaseChange}
                  >
                    <SelectTrigger className="w-[250px] h-8 text-sm">
                      <SelectValue placeholder="Select a database..." />
                    </SelectTrigger>
                    <SelectContent>
                      {allDatabases.map((db: { id: number; name: string; provider: string } | unknown) => {
                        const dbTyped = db as { id: number; name: string; provider: string };
                        return (
                        <SelectItem key={dbTyped.id} value={dbTyped.id.toString()}>
                          {dbTyped.name} <span className="text-muted-foreground ml-1">({dbTyped.provider})</span>
                        </SelectItem>
                      )})}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
          <Button onClick={executeQuery} disabled={loading || !databaseId}>
            {loading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            Execute
          </Button>
        </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Tables Sidebar */}
        <Card className="w-72 flex flex-col shadow-sm">
          <CardHeader className="py-4 border-b bg-muted/10">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Table2 className="h-4 w-4 text-primary" />
              Tables
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-auto p-0">
            {loadingTables ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : tables.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                No tables found
              </div>
            ) : (
              <div className="py-2">
                {tables.map((table) => (
                  <button
                    key={table.name}
                    onClick={() => handleTableClick(table.name)}
                    className={`w-full px-4 py-2 text-left text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 ${
                      selectedTable === table.name ? "bg-muted" : ""
                    }`}
                  >
                    <Table2 className="h-4 w-4 text-muted-foreground" />
                    <span className="truncate">{table.name}</span>
                    <Badge variant="outline" className="ml-auto text-xs">
                      {table.type === "BASE TABLE" ? "Table" : table.type}
                    </Badge>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Action Area (Tabs) */}
        <Card className="flex-1 flex flex-col shadow-sm border overflow-hidden">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col h-full">
            <div className="px-4 py-3 border-b bg-muted/10 flex items-center justify-between">
              <TabsList className="bg-muted">
                <TabsTrigger value="sql" className="text-xs">
                  <Code2 className="h-4 w-4 mr-2" />
                  SQL Editor
                </TabsTrigger>
                <TabsTrigger value="data" className="text-xs" disabled={!selectedTable}>
                  <Table2 className="h-4 w-4 mr-2" />
                  Data Editor
                </TabsTrigger>
                <TabsTrigger value="schema" className="text-xs">
                  <Network className="h-4 w-4 mr-2" />
                  Schema Graph
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="flex-1 relative flex flex-col overflow-hidden">
              <TabsContent value="sql" className="mt-0 h-full flex flex-col m-0 p-0 border-0 outline-none flex-1 data-[state=active]:flex">
                {/* Query Editor */}
                <div className="border-b bg-background">
                  <div className="p-4">
              <Textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter your SELECT query..."
                className="h-48 font-mono text-sm resize-none border-0 focus-visible:ring-0 bg-background"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    executeQuery();
                  }
                }}
              />
            </div>
            <div className="px-4 py-2 border-t text-xs text-muted-foreground">
              Press Ctrl+Enter to execute
            </div>
          </div>

          {/* Results */}
          <div className="flex-1 overflow-auto">
            <div className="px-4 py-2 border-b bg-muted/30 flex items-center justify-between">
              <span className="text-sm font-medium">Results</span>
              {result && (
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <CheckCircle className="h-3 w-3 text-green-500" />
                    {result.row_count} rows
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {result.execution_time_ms}ms
                  </span>
                </div>
              )}
            </div>

            <div className="flex-1 overflow-auto">
              {error ? (
                <div className="flex flex-col items-center justify-center h-full text-center p-8">
                  <AlertCircle className="h-10 w-10 text-destructive mb-4" />
                  <p className="text-destructive font-medium">Query Error</p>
                  <p className="text-sm text-muted-foreground mt-1 max-w-md">
                    {error}
                  </p>
                </div>
              ) : result ? (
                result.row_count === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-center p-8">
                    <CheckCircle className="h-10 w-10 text-green-500 mb-4" />
                    <p className="font-medium">Query executed successfully</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      No rows returned
                    </p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader className="sticky top-0 bg-background">
                      <TableRow>
                        {result.columns.map((col, i) => (
                          <TableHead key={i} className="font-medium">
                            {col}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.rows.map((row, i) => (
                        <TableRow key={i}>
                          {row.map((cell, j) => (
                            <TableCell
                              key={j}
                              className="font-mono text-sm max-w-xs truncate"
                            >
                              {formatCellValue(cell)}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center p-8">
                  <Database className="h-10 w-10 text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">
                    Execute a query to see results
                  </p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>
        {/* Schema Graph Tab */}
        <TabsContent value="schema" className="mt-0 h-full flex flex-col m-0 p-0 border-0 outline-none flex-1 data-[state=active]:flex">
          {databaseId ? (
            <SchemaGraph databaseId={databaseId} />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Select a database to view its schema
            </div>
          )}
        </TabsContent>

        {/* Data Editor Tab */}
        <TabsContent value="data" className="mt-0 h-full flex flex-col m-0 p-0 border-0 outline-none flex-1 data-[state=active]:flex">
          {databaseId && selectedTable ? (
            <DataEditor databaseId={databaseId} tableName={selectedTable} />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Select a table to view and edit its data
            </div>
          )}
        </TabsContent>
      </div>
          </Tabs>
        </Card>
      </div>
    </div>
  );
}