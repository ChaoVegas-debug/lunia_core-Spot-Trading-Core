import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { createUser, getUsers, updateUser } from '../../api/endpoints';
import type { UserProfile } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const AdminUsersWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken,
    tenantId: auth.tenantId
  };
  const [refreshKey, setRefreshKey] = useState(0);
  const users = usePolledResource<{ items: UserProfile[] }>(
    (signal) => getUsers(signal, client),
    15000,
    [auth.role, auth.tenantId, refreshKey]
  );

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserProfile['role']>('USER');
  const [error, setError] = useState<string | null>(null);

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const controller = new AbortController();
      await createUser({ email, password, role }, controller.signal, client);
      setEmail('');
      setPassword('');
      setRole('USER');
      setRefreshKey((v) => v + 1);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const toggleActive = async (user: UserProfile) => {
    const controller = new AbortController();
    await updateUser(
      user.id,
      { is_active: !user.is_active },
      controller.signal,
      client
    );
    setRefreshKey((v) => v + 1);
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Users</h3>
          <p className="small">Admin-managed users with roles and activation status.</p>
        </div>
        <DataStatus loading={users.loading} error={users.error} lastUpdated={users.lastUpdated} staleAfterMs={20000} />
      </div>
      {error && <div className="alert">{error}</div>}
      <form className="grid cols-3" onSubmit={onCreate} style={{ gap: 8 }}>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" required />
        <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" type="password" required />
        <select value={role} onChange={(e) => setRole(e.target.value as UserProfile['role'])}>
          {['USER', 'TRADER', 'FUND', 'ADMIN'].map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <button className="button" type="submit">
          Create
        </button>
      </form>
      {users.data ? (
        <table className="table" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Last login</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.data.items.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>{user.role}</td>
                <td>{user.is_active ? 'active' : 'disabled'}</td>
                <td>{user.last_login_at ?? 'n/a'}</td>
                <td>
                  <button className="button ghost" type="button" onClick={() => toggleActive(user)}>
                    {user.is_active ? 'Disable' : 'Enable'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div>Loading users...</div>
      )}
    </div>
  );
};
