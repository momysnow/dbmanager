import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Plus, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import api from "@/services/api";

interface DataEditorProps {
  databaseId: number;
  tableName: string;
}

export default function DataEditor({ databaseId, tableName }: DataEditorProps) {
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<unknown[][]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isAddRowOpen, setIsAddRowOpen] = useState(false);
  const [newRowData, setNewRowData] = useState<Record<string, string>>({});
  const [addingRow, setAddingRow] = useState(false);

  // Auto-save typing timeout ref
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // Track modified cells to show save state
  const [savingCells, setSavingCells] = useState<Record<string, boolean>>({});

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query = `SELECT * FROM ${tableName} LIMIT 1000`;
      const response = await api.post(`/databases/${databaseId}/query`, { query });
      setColumns(response.data.columns || []);
      setRows(response.data.rows || []);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(apiErr.response?.data?.detail || apiErr.message || "Failed to load table data");
    } finally {
      setLoading(false);
    }
  }, [databaseId, tableName]);

  useEffect(() => {
    if (tableName) {
      loadData();
    }
  }, [tableName, loadData]);

  const updateCell = async (rowIndex: number, colIndex: number, newValue: string) => {
    const colName = columns[colIndex];
    const row = rows[rowIndex];
    
    // We need a primary key to reliably update!
    // For now, let's assume the first column is the ID/Primary key as a best effort
    const pkCol = columns[0];
    const pkVal = row[0];

    // Optimistic update
    const newRows = [...rows];
    newRows[rowIndex][colIndex] = newValue;
    setRows(newRows);

    const cellKey = `${rowIndex}-${colIndex}`;
    setSavingCells((prev: Record<string, boolean>) => ({ ...prev, [cellKey]: true }));

    try {
      // NOTE: This is a simplistic update strategy relying on the first column being a unique identifier.
      // In a real robust system, we'd need to fetch actual primary keys from the schema.
      const query = `UPDATE ${tableName} SET ${colName} = '${newValue}' WHERE ${pkCol} = '${pkVal}'`;
      await api.post(`/databases/${databaseId}/query`, { query });
      
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(`Failed to save cell: ${apiErr.response?.data?.detail || apiErr.message}`);
      // Revert optimistic update
      loadData(); 
    } finally {
      setSavingCells((prev: Record<string, boolean>) => ({ ...prev, [cellKey]: false }));
    }
  };

  const handleCellChange = (rowIndex: number, colIndex: number, newValue: string) => {
    const newRows = [...rows];
    newRows[rowIndex][colIndex] = newValue;
    setRows(newRows);

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(() => {
      updateCell(rowIndex, colIndex, newValue);
    }, 500);
  };
  
  const handleAddRow = () => {
    setNewRowData({});
    setIsAddRowOpen(true);
  };

  const submitNewRow = async () => {
    setAddingRow(true);
    try {
      const keys = Object.keys(newRowData).filter((k) => newRowData[k] !== undefined && newRowData[k] !== "");
      let query = "";

      if (keys.length === 0) {
        query = `INSERT INTO ${tableName} DEFAULT VALUES`;
      } else {
        const cols = keys.join(", ");
        const vals = keys.map((k) => `'${newRowData[k].replace(/'/g, "''")}'`).join(", ");
        query = `INSERT INTO ${tableName} (${cols}) VALUES (${vals})`;
      }

      await api.post(`/databases/${databaseId}/query`, { query });
      toast.success("Row added successfully");
      setIsAddRowOpen(false);
      loadData();
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      toast.error(`Failed to add row: ${apiErr.response?.data?.detail || apiErr.message}`);
    } finally {
      setAddingRow(false);
    }
  };


  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center text-destructive">
        <AlertCircle className="h-8 w-8 mb-2" />
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-background relative">
        <div className="flex items-center justify-between p-2 border-b bg-muted/10">
          <span className="text-sm font-medium text-muted-foreground px-2">Table: {tableName}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={handleAddRow}>
                <Plus className="h-4 w-4 mr-2" /> Add Row
            </Button>
             <Button size="sm" variant="outline" onClick={loadData}>
                Refresh
            </Button>
          </div>
        </div>
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader className="sticky top-0 bg-background z-10 shadow-sm">
            <TableRow>
              {columns.map((col: string, i: number) => (
                <TableHead key={i} className="font-medium whitespace-nowrap">
                  {col}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row: unknown[], rowIndex: number) => (
              <TableRow key={rowIndex} className="hover:bg-muted/30">
                {row.map((cell, colIndex) => {
                   const isSaving = savingCells[`${rowIndex}-${colIndex}`];
                   return (
                  <TableCell key={colIndex} className="p-0 border-r relative">
                    <Input
                      value={cell === null ? "" : (cell as string | number | readonly string[] | undefined)}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleCellChange(rowIndex, colIndex, e.target.value)}
                      className={`h-full w-full min-h-[40px] border-0 rounded-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-primary bg-transparent font-mono text-sm ${cell === null ? 'italic text-muted-foreground placeholder:text-muted-foreground/50' : ''}`}
                      placeholder={cell === null ? 'NULL' : ''}
                    />
                    {isSaving && (
                        <div className="absolute right-2 top-1/2 -translate-y-1/2">
                            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                        </div>
                    )}
                  </TableCell>
                )})}
              </TableRow>
            ))}
            {rows.length === 0 && (
                <TableRow>
                    <TableCell colSpan={columns.length} className="text-center py-8 text-muted-foreground">
                        No rows in table
                    </TableCell>
                </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={isAddRowOpen} onOpenChange={setIsAddRowOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Add Row to {tableName}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto pr-2">
            {columns.map((col) => (
              <div key={col} className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor={col} className="text-right text-xs truncate" title={col}>
                  {col}
                </Label>
                <Input
                  id={col}
                  placeholder="NULL / Default"
                  className="col-span-3 text-sm"
                  value={newRowData[col] || ""}
                  onChange={(e) => setNewRowData((prev) => ({ ...prev, [col]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddRowOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitNewRow} disabled={addingRow}>
              {addingRow && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save Row
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
