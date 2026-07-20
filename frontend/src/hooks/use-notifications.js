import { useEffect, useState, useCallback } from 'react';
import { notificationService } from '../services/notifications';

export function useNotifications() {
  const [isReady, setIsReady] = useState(false);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [pendingNotifications, setPendingNotifications] = useState<any[]>([]);

  const init = useCallback(async () => {
    try {
      await notificationService.init();
      const granted = await notificationService.checkPermissions();
      setPermissionGranted(granted);
      const pending = await notificationService.getPendingNotifications();
      setPendingNotifications(pending);
      setIsReady(true);
    } catch (error) {
      console.error('Init notifications error:', error);
    }
  }, []);

  useEffect(() => {
    init();
  }, [init]);

  const requestPermission = useCallback(async () => {
    const granted = await notificationService.requestPermissions();
    setPermissionGranted(granted);
    return granted;
  }, []);

  const scheduleTaskReminder = useCallback(async (taskId: string, taskTitle: string, dueDate: string) => {
    await notificationService.scheduleTaskReminder(taskId, taskTitle, dueDate);
    const pending = await notificationService.getPendingNotifications();
    setPendingNotifications(pending);
  }, []);

  const scheduleHabitReminder = useCallback(async (habitId: string, habitName: string, time: string) => {
    await notificationService.scheduleHabitReminder(habitId, habitName, time);
    const pending = await notificationService.getPendingNotifications();
    setPendingNotifications(pending);
  }, []);

  const scheduleGoalCheck = useCallback(async (goalId: string, goalTitle: string, targetDate: string) => {
    await notificationService.scheduleGoalCheck(goalId, goalTitle, targetDate);
    const pending = await notificationService.getPendingNotifications();
    setPendingNotifications(pending);
  }, []);

  const cancelNotification = useCallback(async (id: string | number) => {
    await notificationService.cancelNotification(id);
    const pending = await notificationService.getPendingNotifications();
    setPendingNotifications(pending);
  }, []);

  const clearAll = useCallback(async () => {
    await notificationService.cancelAllNotifications();
    setPendingNotifications([]);
  }, []);

  return {
    isReady,
    permissionGranted,
    pendingNotifications,
    requestPermission,
    scheduleTaskReminder,
    scheduleHabitReminder,
    scheduleGoalCheck,
    cancelNotification,
    clearAll
  };
}

export default useNotifications;