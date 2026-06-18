/**
 * UsersList — TENANT_ADMIN user management table.
 * Phase 7BCD redesign: status badge, role pill, last-login column, empty state.
 */

import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext";
import { CreateUserModal } from "./CreateUserModal";
import { EditUserPanel } from "./EditUserModal";

interface UserItem {
  user_id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  onboarding_completed: boolean;
  last_login_at?: string | null;
}

async function fetchUsers(): Promise<UserItem[]> {
  const { data } = await axios.get<UserItem[]>("/api/v1/tenant/users");
  return data;
}

function RolePill({ role }: { role: string }): React.JSX.Element {
  const cls =
    role === "TENANT_ADMIN"
      ? "badge badge-accent"
      : role === "AUDITOR"
      ? "badge badge-blue"
      : "badge badge-muted";
  const display =
    role === "TENANT_ADMIN" ? "Admin" : role === "AUDITOR" ? "Auditor" : "Reviewer";
  return <span className={cls}>{display}</span>;
}

function StatusBadge({ user }: { user: UserItem }): React.JSX.Element {
  if (!user.is_active) {
    return <span className="user-status-badge user-status-badge--suspended">Suspended</span>;
  }
  if (!user.onboarding_completed) {
    return <span className="user-status-badge user-status-badge--invited">Invited</span>;
  }
  return <span className="user-status-badge user-status-badge--active">Active</span>;
}

export function UsersList(): React.JSX.Element {
  const labelShared = useLabels("shared");
  const labelUsers = useLabels("users");
  const { user: authUser } = useAuth();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState<UserItem | null>(null);

  const { data: users = [], isLoading } = useQuery<UserItem[]>({
    queryKey: ["tenant-users"],
    queryFn: fetchUsers,
    staleTime: 30 * 1000,
  });

  const canCreateUsers = authUser?.role === "TENANT_ADMIN";

  return (
    <div className="users-list">
      <div className="users-list__header">
        <h1 className="users-list__title">
          {labelUsers("title", "User Management")}
        </h1>
        {canCreateUsers && (
          <button
            className="btn btn--primary"
            type="button"
            onClick={() => setShowCreate(true)}
          >
            {labelUsers("btn.create", "Invite User")}
          </button>
        )}
      </div>

      {isLoading ? (
        <p>{labelShared("loading", "Loading…")}</p>
      ) : users.length === 0 ? (
        <div className="data-table__empty">
          <p className="data-table__empty-msg">
            {labelUsers("empty_state", "No team members yet.")}
          </p>
          {canCreateUsers && (
            <button
              className="btn btn--primary btn--sm"
              type="button"
              onClick={() => setShowCreate(true)}
            >
              {labelUsers("empty_cta", "Invite your first team member")}
            </button>
          )}
        </div>
      ) : (
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>{labelUsers("col.name", "Name")}</th>
                <th>{labelUsers("col.email", "Email")}</th>
                <th>{labelUsers("col.role", "Role")}</th>
                <th>{labelUsers("col.status", "Status")}</th>
                <th>{labelUsers("col.last_login", "Last Login")}</th>
                <th>{labelUsers("col.actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="data-table__row">
                  <td className="data-table__cell">
                    {u.first_name} {u.last_name}
                  </td>
                  <td className="data-table__cell">{u.email}</td>
                  <td className="data-table__cell">
                    <RolePill role={u.role} />
                  </td>
                  <td className="data-table__cell">
                    <StatusBadge user={u} />
                  </td>
                  <td className="data-table__cell">
                    <span className="users-list__last-login">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleDateString()
                        : "—"}
                    </span>
                  </td>
                  <td className="data-table__cell">
                    {canCreateUsers && u.role !== "TENANT_ADMIN" && (
                      <button
                        className="btn btn--sm btn--secondary"
                        type="button"
                        onClick={() => setEditTarget(u)}
                      >
                        {labelUsers("col.edit", "Edit")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            void qc.invalidateQueries({ queryKey: ["tenant-users"] });
            setShowCreate(false);
          }}
        />
      )}

      {editTarget && (
        <EditUserPanel
          user={editTarget}
          onClose={() => setEditTarget(null)}
          onUpdated={() => {
            void qc.invalidateQueries({ queryKey: ["tenant-users"] });
            setEditTarget(null);
          }}
        />
      )}
    </div>
  );
}
