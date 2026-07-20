import { useState, useEffect, useCallback } from 'react';
import { db } from '../services/database';
import { syncService } from '../services/sync';
import { dataService } from '../services/data';

export function useDatabase() {
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isOnline, setIsOnline] = useState(true);
  const [pendingSync, setPendingSync] = useState(0);

  const init = useCallback(async () => {
    try {
      await db.init();
      await syncService.init();
      setIsOnline(syncService.getConnectionStatus());
      setIsReady(true);
    } catch (err) {
      setError(err as Error);
      console.error('Database init error:', err);
    }
  }, []);

  useEffect(() => {
    init();

    const interval = setInterval(async () => {
      const count = await syncService.getPendingCount();
      setPendingSync(count);
      setIsOnline(syncService.getConnectionStatus());
    }, 5000);

    return () => {
      clearInterval(interval);
      syncService.destroy();
      db.close();
    };
  }, [init]);

  return {
    isReady,
    error,
    isOnline,
    pendingSync
  };
}

export function useData(userId: string | null) {
  const [tasks, setTasks] = useState<any[]>([]);
  const [habits, setHabits] = useState<any[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [goals, setGoals] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (userId) {
      dataService.setCurrentUser(userId);
      loadData();
    }
  }, [userId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [tasksData, habitsData, transactionsData, goalsData] = await Promise.all([
        dataService.getTasks(),
        dataService.getHabits(),
        dataService.getTransactions(),
        dataService.getGoals()
      ]);
      
      setTasks(tasksData);
      setHabits(habitsData);
      setTransactions(transactionsData);
      setGoals(goalsData);
    } catch (err) {
      console.error('Load data error:', err);
    } finally {
      setLoading(false);
    }
  };

  return {
    tasks,
    habits,
    transactions,
    goals,
    loading,
    refresh: loadData
  };
}

export async function initializeApp(userId: string) {
  await db.init();
  await syncService.init();
  dataService.setCurrentUser(userId);
  
  if (syncService.getConnectionStatus()) {
    await syncService.pullLatestFromServer('tasks', userId);
    await syncService.pullLatestFromServer('habits', userId);
    await syncService.pullLatestFromServer('transactions', userId);
    await syncService.pullLatestFromServer('goals', userId);
  }
}

export { db, syncService, dataService };
export default useDatabase;