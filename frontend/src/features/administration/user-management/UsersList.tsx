/**
 * UsersList — TENANT_ADMIN user management table.
 * V9 S13.2 — email, role badge, onboarding status, actions.
 * Create User button only shown to TENANT_ADMIN.
 */

import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";
import { useAuth } from "@/context/AuthContext";
import { CreateUserModal } from "./CreateUserModal";
import { EditUserModal } from "./EditUserModal";

interface UserItem {
  user_id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  onboarding_completed: boolean;
}

async function fetchUsers(): Promise<UserItem[]> {
  const { data } = await axios.get<UserItem[]>("/api/v1/tenant/users");
  return data;
}

function RoleBadge({ role }: { role: string }) {
  const cls =
    role === "TENANT_ADMIN"
      ? "badge badge--admin"
      : role === "AUDITOR"
      ? "badge badge--auditor"
      : "badge badge--reviewer";
  return <span className={cls}>{role}</span>;
}

export function UsersList(): React.JSX.Element {
  const labels = useLabels();
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
        <h1 className="users-list__title">{labels.users_title}</h1>
        {canCreateUsers && (
          <button className="btn btn--primary" onClick={() => setShowCreate(true)}>
            {labels.users_btn_create}
          </button>
        )}
      </div>

      {isLoading ? (
        <p>{labels.loading}</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>{labels.users_col_email}</th>
              <th>{labels.users_col_name}</th>
              <th>{labels.users_col_role}</th>
              <th>{labels.users_col_onboarding}</th>
              <th>{labels.users_col_actions}</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id} className="data-table__row">
                <td className="data-table__cell">{u.email}</td>
                <td className="data-table__cell">{u.first_name} {u.last_name}</td>
                <td className="data-table__cell">
                  <RoleBadge role={u.role} />
                </td>
                <td className="data-table__cell">
                  {u.onboarding_completed ? "✓" : "—"}
                </td>
                <td className="data-table__cell">
                  {canCreateUsers && u.role !== "TENANT_ADMIN" && (
                    <button
                      className="btn btn--sm btn--secondary"
                      onClick={() => setEditTarget(u)}
                    >
                      {labels.users_edit_title}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
        <EditUserModal
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
