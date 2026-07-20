import { db } from './database';
import { syncService } from './sync';

interface Task {
  task_id: string;
  user_id: string;
  title: string;
  description?: string;
  completed: boolean;
  date: string;
  priority: string;
  xp_reward: number;
  recurrence: string;
  is_template: boolean;
  created_at: string;
  updated_at?: string;
  synced_at?: string;
}

interface Habit {
  habit_id: string;
  user_id: string;
  name: string;
  description?: string;
  color: string;
  streak: number;
  best_streak: number;
  completions: string[];
  created_at: string;
  updated_at?: string;
  synced_at?: string;
}

interface Transaction {
  transaction_id: string;
  user_id: string;
  type: string;
  amount: number;
  category: string;
  description?: string;
  date: string;
  created_at: string;
  updated_at?: string;
  synced_at?: string;
}

interface Goal {
  goal_id: string;
  user_id: string;
  title: string;
  description?: string;
  target_date: string;
  progress: number;
  sprint_duration: number;
  daily_checks: string[];
  sprints: any[];
  created_at: string;
  updated_at?: string;
  synced_at?: string;
}

class DataService {
  private currentUserId: string | null = null;

  setCurrentUser(userId: string) {
    this.currentUserId = userId;
  }

  getCurrentUserId(): string | null {
    return this.currentUserId;
  }

  generateId(prefix: string): string {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  async saveTask(task: Partial<Task>) {
    const now = new Date().toISOString();
    const taskId = task.task_id || this.generateId('task');
    
    const taskData = {
      task_id: taskId,
      user_id: task.user_id || this.currentUserId,
      title: task.title,
      description: task.description || null,
      completed: task.completed ? 1 : 0,
      date: task.date,
      priority: task.priority || 'medium',
      xp_reward: task.xp_reward || 10,
      recurrence: task.recurrence || 'once',
      is_template: task.is_template ? 1 : 0,
      created_at: task.created_at || now,
      updated_at: now,
      synced_at: null
    };

    await db.execute(
      `INSERT OR REPLACE INTO tasks (task_id, user_id, title, description, completed, date, priority, xp_reward, recurrence, is_template, created_at, updated_at, synced_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      Object.values(taskData)
    );

    await syncService.queueChange('tasks', taskId, 'INSERT', taskData);
    return taskId;
  }

  async getTasks(userId?: string, includeCompleted = true): Promise<Task[]> {
    const uid = userId || this.currentUserId;
    const sql = includeCompleted
      ? `SELECT * FROM tasks WHERE user_id = ? ORDER BY date DESC`
      : `SELECT * FROM tasks WHERE user_id = ? AND completed = 0 ORDER BY date DESC`;
    
    const results = await db.query<Task>(sql, [uid]);
    return results.map(t => ({
      ...t,
      completed: Boolean(t.completed),
      is_template: Boolean(t.is_template)
    }));
  }

  async completeTask(taskId: string) {
    await db.execute(
      `UPDATE tasks SET completed = 1, updated_at = ? WHERE task_id = ?`,
      [new Date().toISOString(), taskId]
    );
    
    await syncService.queueChange('tasks', taskId, 'UPDATE', { task_id: taskId, completed: 1 });
  }

  async saveHabit(habit: Partial<Habit>) {
    const now = new Date().toISOString();
    const habitId = habit.habit_id || this.generateId('habit');
    
    const habitData = {
      habit_id: habitId,
      user_id: habit.user_id || this.currentUserId,
      name: habit.name,
      description: habit.description || null,
      color: habit.color || '#007AFF',
      streak: habit.streak || 0,
      best_streak: habit.best_streak || 0,
      completions: JSON.stringify(habit.completions || []),
      created_at: habit.created_at || now,
      updated_at: now,
      synced_at: null
    };

    await db.execute(
      `INSERT OR REPLACE INTO habits (habit_id, user_id, name, description, color, streak, best_streak, completions, created_at, updated_at, synced_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      Object.values(habitData)
    );

    await syncService.queueChange('habits', habitId, 'INSERT', habitData);
    return habitId;
  }

  async getHabits(userId?: string): Promise<Habit[]> {
    const uid = userId || this.currentUserId;
    const results = await db.query<Habit>(
      `SELECT * FROM habits WHERE user_id = ? ORDER BY created_at DESC`,
      [uid]
    );
    return results.map(h => ({
      ...h,
      completions: JSON.parse(h.completions as any || '[]')
    }));
  }

  async saveTransaction(transaction: Partial<Transaction>) {
    const now = new Date().toISOString();
    const transactionId = transaction.transaction_id || this.generateId('txn');
    
    const txnData = {
      transaction_id: transactionId,
      user_id: transaction.user_id || this.currentUserId,
      type: transaction.type,
      amount: transaction.amount,
      category: transaction.category,
      description: transaction.description || null,
      date: transaction.date,
      created_at: transaction.created_at || now,
      updated_at: now,
      synced_at: null
    };

    await db.execute(
      `INSERT OR REPLACE INTO transactions (transaction_id, user_id, type, amount, category, description, date, created_at, updated_at, synced_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      Object.values(txnData)
    );

    await syncService.queueChange('transactions', transactionId, 'INSERT', txnData);
    return transactionId;
  }

  async getTransactions(userId?: string, month?: string): Promise<Transaction[]> {
    const uid = userId || this.currentUserId;
    let sql = `SELECT * FROM transactions WHERE user_id = ?`;
    const params: any[] = [uid];
    
    if (month) {
      sql += ` AND date LIKE ?`;
      params.push(`${month}%`);
    }
    
    sql += ` ORDER BY date DESC`;
    
    return db.query<Transaction>(sql, params);
  }

  async saveGoal(goal: Partial<Goal>) {
    const now = new Date().toISOString();
    const goalId = goal.goal_id || this.generateId('goal');
    
    const goalData = {
      goal_id: goalId,
      user_id: goal.user_id || this.currentUserId,
      title: goal.title,
      description: goal.description || null,
      target_date: goal.target_date,
      progress: goal.progress || 0,
      sprint_duration: goal.sprint_duration || 60,
      daily_checks: JSON.stringify(goal.daily_checks || []),
      sprints: JSON.stringify(goal.sprints || []),
      created_at: goal.created_at || now,
      updated_at: now,
      synced_at: null
    };

    await db.execute(
      `INSERT OR REPLACE INTO goals (goal_id, user_id, title, description, target_date, progress, sprint_duration, daily_checks, sprints, created_at, updated_at, synced_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      Object.values(goalData)
    );

    await syncService.queueChange('goals', goalId, 'INSERT', goalData);
    return goalId;
  }

  async getGoals(userId?: string): Promise<Goal[]> {
    const uid = userId || this.currentUserId;
    const results = await db.query<Goal>(
      `SELECT * FROM goals WHERE user_id = ? ORDER BY target_date ASC`,
      [uid]
    );
    return results.map(g => ({
      ...g,
      daily_checks: JSON.parse(g.daily_checks as any || '[]'),
      sprints: JSON.parse(g.sprints as any || '[]')
    }));
  }

  async getFinancialSummary(userId?: string, month?: string) {
    const uid = userId || this.currentUserId;
    let sql = `SELECT type, SUM(amount) as total FROM transactions WHERE user_id = ?`;
    const params: any[] = [uid];
    
    if (month) {
      sql += ` AND date LIKE ?`;
      params.push(`${month}%`);
    }
    
    sql += ` GROUP BY type`;
    
    const results = await db.query<{type: string, total: number}>(sql, params);
    
    const income = results.find(r => r.type === 'income')?.total || 0;
    const expense = results.find(r => r.type === 'expense')?.total || 0;
    
    return {
      income,
      expense,
      balance: income - expense
    };
  }

  async clearAllData() {
    const tables = ['tasks', 'habits', 'transactions', 'budgets', 'goals', 'workout_plans', 'workout_logs', 'notifications', 'sync_queue'];
    for (const table of tables) {
      await db.execute(`DELETE FROM ${table}`);
    }
  }
}

export const dataService = new DataService();
export default dataService;