import React, { useState } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string | number;
  onRowClick?: (row: T) => void;
  loading?: boolean;
  emptyMessage?: string;
}

type SortDir = "asc" | "desc" | null;

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  onRowClick,
  loading = false,
  emptyMessage = "No data available.",
}: DataTableProps<T>): React.JSX.Element {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  const handleSort = (col: Column<T>) => {
    if (!col.sortable) return;
    if (sortKey === col.key) {
      setSortDir((d) => (d === "asc" ? "desc" : d === "desc" ? null : "asc"));
      if (sortDir === "desc") setSortKey(null);
    } else {
      setSortKey(col.key);
      setSortDir("asc");
    }
  };

  const sortIndicator = (col: Column<T>) => {
    if (!col.sortable) return null;
    if (sortKey !== col.key) return <span style={{ opacity: 0.3 }}> ↕</span>;
    return <span style={{ color: "var(--brand)" }}>{sortDir === "asc" ? " ↑" : " ↓"}</span>;
  };

  if (loading) {
    return (
      <div className="data-table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} style={{ width: col.width }}>{col.header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col.key}>
                    <div className="skeleton" style={{ height: "16px", width: "80%" }} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="data-table-wrapper">
        <div className="empty-state">
          <span className="empty-state-icon">📋</span>
          <span>{emptyMessage}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  width: col.width,
                  cursor: col.sortable ? "pointer" : "default",
                  userSelect: "none",
                }}
                onClick={() => handleSort(col)}
              >
                {col.header}
                {sortIndicator(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={getRowKey(row)}
              onClick={() => onRowClick?.(row)}
              style={{ cursor: onRowClick ? "pointer" : "default" }}
            >
              {columns.map((col) => (
                <td key={col.key}>{col.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
