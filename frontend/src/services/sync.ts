import { Network, NetworkStatus } from '@capacitor/network';
import { db } from './database';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
const SYNC_FIELDS: Record<string, string[]> = {
  tasks: ['task_id','user_id','title','description','completed','date','priority','xp_reward','recurrence','is_template','created_at','updated_at','synced_at'],
  habits: ['habit_id','user_id','name','description','color','streak','best_streak','completions','created_at','updated_at','synced_at'],
  transactions: ['transaction_id','user_id','type','amount','category','description','date','created_at','updated_at','synced_at'],
  goals: ['goal_id','user_id','title','description','target_date','progress','sprint_duration','daily_checks','sprints','created_at','updated_at','synced_at'],
};

function sqliteRecord(tableName: string, record: any, syncedAt: string) {
  const fields = SYNC_FIELDS[tableName];
  if (!fields) throw new Error('Unsupported sync table');
  return Object.fromEntries(fields.filter(key => key in record || key === 'synced_at').map(key => {
    const value = key === 'synced_at' ? syncedAt : record[key];
    return [key, Array.isArray(value) ? JSON.stringify(value) : typeof value === 'boolean' ? Number(value) : value];
  }));
}

interface SyncRecord {
  id: number;
  table_name: string;
  record_id: string;
  operation: 'INSERT' | 'UPDATE' | 'DELETE';
  data: string;
  created_at: string;
  attempts: number;
}

class SyncService {
  private isOnline = true;
  private isSyncing = false;
  private networkListener: any = null;
  private syncInterval: any = null;

  async init() {
    this.checkConnection();
    
    this.networkListener = await Network.addListener('networkStatusChange', (status: NetworkStatus) => {
      const wasOnline = this.isOnline;
      this.isOnline = status.connected;
      
      if (!wasOnline && this.isOnline) {
        console.log('Back online - triggering sync');
        this.syncPendingChanges();
      }
    });

    this.syncInterval = setInterval(() => {
      if (this.isOnline && !this.isSyncing) {
        this.syncPendingChanges();
      }
    }, 30000);
  }

  async checkConnection(): Promise<boolean> {
    try {
      const status = await Network.getStatus();
      this.isOnline = status.connected;
      return this.isOnline;
    } catch {
      this.isOnline = false;
      return false;
    }
  }

  getConnectionStatus(): boolean {
    return this.isOnline;
  }

  async queueChange(
    tableName: string,
    recordId: string,
    operation: 'INSERT' | 'UPDATE' | 'DELETE',
    data: any
  ) {
    await db.execute(
      `INSERT INTO sync_queue (table_name, record_id, operation, data, created_at) VALUES (?, ?, ?, ?, ?)`,
      [tableName, recordId, operation, JSON.stringify(data), new Date().toISOString()]
    );
    
    if (this.isOnline) {
      this.syncPendingChanges();
    }
  }

  async syncPendingChanges() {
    if (this.isSyncing || !this.isOnline) return;
    
    this.isSyncing = true;
    try {
      const pendingChanges = await db.query<SyncRecord>(
        `SELECT * FROM sync_queue ORDER BY created_at ASC LIMIT 50`
      );

      for (const change of pendingChanges) {
        try {
          await this.syncRecord(change);
          await db.execute(`DELETE FROM sync_queue WHERE id = ?`, [change.id]);
        } catch (error) {
          console.error('Sync failed for record:', change, error);
          await db.execute(
            `UPDATE sync_queue SET attempts = attempts + 1 WHERE id = ?`,
            [change.id]
          );
        }
      }
    } catch (error) {
      console.error('Sync pendingChanges error:', error);
    } finally {
      this.isSyncing = false;
    }
  }

  private async syncRecord(change: SyncRecord) {
    const endpoint = `${API_URL}/api/sync/${change.table_name}`;
    const payload = {
      record_id: change.record_id,
      operation: change.operation,
      data: JSON.parse(change.data),
      timestamp: change.created_at
    };

    await axios.post(endpoint, payload, { withCredentials: true });
  }

  async pullLatestFromServer(tableName: string, userId: string) {
    if (!this.isOnline) return [];

    try {
      const response = await axios.get(`${API_URL}/api/sync/${tableName}/${userId}`, { withCredentials: true });
      const records = response.data;
      
      for (const record of records) {
        await this.mergeRecord(tableName, record);
      }
      
      return records;
    } catch (error) {
      console.error('Pull error:', error);
      return [];
    }
  }

  private async mergeRecord(tableName: string, serverRecord: any) {
    const idField = SYNC_FIELDS[tableName]?.[0];
    if (!idField) throw new Error('Unsupported sync table');
    const existing = await db.query(
      `SELECT * FROM ${tableName} WHERE ${idField} = ? AND user_id = ?`,
      [serverRecord[idField], serverRecord.user_id]
    );

    const now = new Date().toISOString();
    
    if (existing.length === 0) {
      await this.insertRecord(tableName, serverRecord, now);
    } else {
      const serverTime = new Date(serverRecord.updated_at || serverRecord.created_at);
      const localTime = new Date(existing[0].updated_at || existing[0].created_at);
      
      if (serverTime > localTime) {
        await this.updateRecord(tableName, serverRecord, now);
      }
    }
  }

  private async insertRecord(tableName: string, record: any, syncedAt: string) {
    const data = sqliteRecord(tableName, record, syncedAt);
    const columns = Object.keys(data).join(', ');
    const placeholders = Object.keys(data).map(() => '?').join(', ');
    const values = Object.values(data);
    
    await db.execute(
      `INSERT OR REPLACE INTO ${tableName} (${columns}) VALUES (${placeholders})`,
      values
    );
  }

  private async updateRecord(tableName: string, record: any, syncedAt: string) {
    const idField = SYNC_FIELDS[tableName][0];
    const data = sqliteRecord(tableName, record, syncedAt);
    delete data[idField];
    
    const sets = Object.keys(data).map(k => `${k} = ?`).join(', ');
    const values = [...Object.values(data), record[idField], record.user_id];
    
    await db.execute(
      `UPDATE ${tableName} SET ${sets} WHERE ${idField} = ? AND user_id = ?`,
      values
    );
  }

  async getPendingCount(): Promise<number> {
    const result = await db.query<{count: number}[]>(
      `SELECT COUNT(*) as count FROM sync_queue`
    );
    return result[0]?.count || 0;
  }

  destroy() {
    if (this.networkListener) {
      this.networkListener.remove();
    }
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }
  }
}

export const syncService = new SyncService();
export default syncService;
