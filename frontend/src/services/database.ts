import { Capacitor } from '@capacitor/core';
import { SQLite, SQLiteObject } from '@capacitor-community/sqlite';

const DB_NAME = 'sirius.db';

class DatabaseService {
  private db: SQLiteObject | null = null;
  private isInitialized = false;

  async init() {
    if (this.isInitialized) return;
    
    try {
      this.db = await SQLite.createDatabase({ name: DB_NAME });
      await this.createTables();
      this.isInitialized = true;
      console.log('SQLite initialized');
    } catch (error) {
      console.error('Failed to init database:', error);
      throw error;
    }
  }

  private async createTables() {
    if (!this.db) return;

    const queries = `
      CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        email TEXT,
        name TEXT,
        xp INTEGER DEFAULT 0,
        rank TEXT DEFAULT 'Recruta',
        picture TEXT,
        birth_date TEXT,
        bio TEXT,
        gemini_api_key TEXT,
        created_at TEXT,
        updated_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        user_id TEXT,
        title TEXT,
        description TEXT,
        completed INTEGER DEFAULT 0,
        date TEXT,
        priority TEXT DEFAULT 'medium',
        xp_reward INTEGER DEFAULT 10,
        recurrence TEXT DEFAULT 'once',
        is_template INTEGER DEFAULT 1,
        created_at TEXT,
        updated_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS habits (
        habit_id TEXT PRIMARY KEY,
        user_id TEXT,
        name TEXT,
        description TEXT,
        color TEXT,
        streak INTEGER DEFAULT 0,
        best_streak INTEGER DEFAULT 0,
        completions TEXT,
        created_at TEXT,
        updated_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS transactions (
        transaction_id TEXT PRIMARY KEY,
        user_id TEXT,
        type TEXT,
        amount REAL,
        category TEXT,
        description TEXT,
        date TEXT,
        created_at TEXT,
        updated_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS budgets (
        budget_id TEXT PRIMARY KEY,
        user_id TEXT,
        category TEXT,
        limit REAL,
        spent REAL DEFAULT 0,
        month TEXT,
        created_at TEXT,
        updated_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS goals (
        goal_id TEXT PRIMARY KEY,
        user_id TEXT,
        title TEXT,
        description TEXT,
        target_date TEXT,
        progress REAL DEFAULT 0,
        sprint_duration INTEGER DEFAULT 60,
        daily_checks TEXT,
        sprints TEXT,
        created_at TEXT,
        updated_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS workout_plans (
        plan_id TEXT PRIMARY KEY,
        user_id TEXT,
        name TEXT,
        description TEXT,
        exercises TEXT,
        plan_duration TEXT DEFAULT 'dia',
        generated_by_ai INTEGER DEFAULT 0,
        days TEXT,
        objective TEXT,
        level TEXT,
        created_at TEXT,
        updated_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS workout_logs (
        log_id TEXT PRIMARY KEY,
        user_id TEXT,
        plan_id TEXT,
        activity_type TEXT,
        name TEXT,
        duration_minutes INTEGER DEFAULT 0,
        distance_km REAL,
        calories INTEGER,
        exercises_completed TEXT,
        notes TEXT,
        xp_earned INTEGER DEFAULT 20,
        completed INTEGER DEFAULT 1,
        date TEXT,
        created_at TEXT,
        updated_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS notifications (
        notification_id TEXT PRIMARY KEY,
        user_id TEXT,
        title TEXT,
        message TEXT,
        type TEXT DEFAULT 'reminder',
        category TEXT DEFAULT 'custom',
        scheduled_time TEXT,
        repeat TEXT DEFAULT 'none',
        repeat_days TEXT,
        enabled INTEGER DEFAULT 1,
        channels TEXT,
        last_sent TEXT,
        created_at TEXT,
        synced_at TEXT
      );

      CREATE TABLE IF NOT EXISTS sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT,
        record_id TEXT,
        operation TEXT,
        data TEXT,
        created_at TEXT,
        attempts INTEGER DEFAULT 0
      );

      CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
      CREATE INDEX IF NOT EXISTS idx_habits_user ON habits(user_id);
      CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
      CREATE INDEX IF NOT EXISTS idx_goals_user ON goals(user_id);
      CREATE INDEX IF NOT EXISTS idx_workout_logs_user ON workout_logs(user_id);
    `;

    const statements = queries.split(';').filter(s => s.trim());
    for (const sql of statements) {
      if (sql.trim()) {
        await this.db.execute(sql);
      }
    }
  }

  async execute(sql: string, params: any[] = []) {
    if (!this.db) throw new Error('Database not initialized');
    return this.db.execute(sql, params);
  }

  async query<T>(sql: string, params: any[] = []): Promise<T[]> {
    if (!this.db) throw new Error('Database not initialized');
    const result = await this.db.query(sql, params);
    return result.values as T[];
  }

  async close() {
    if (this.db) {
      await this.db.close();
      this.db = null;
      this.isInitialized = false;
    }
  }
}

export const db = new DatabaseService();
export default db;