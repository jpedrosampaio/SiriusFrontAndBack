import { LocalNotifications, LocalNotificationSchema, ScheduledLocalNotification } from '@capacitor/local-notifications';
import { Platform } from '@capacitor/core';

class NotificationService {
  private isInitialized = false;
  private permissionGranted = false;

  async init() {
    if (this.isInitialized) return;
    
    if (Platform.isNativePlatform()) {
      await this.requestPermissions();
      await this.registerTypes();
    }
    
    this.isInitialized = true;
  }

  async requestPermissions(): Promise<boolean> {
    try {
      const result = await LocalNotifications.requestPermissions();
      this.permissionGranted = result.granted;
      return result.granted;
    } catch (error) {
      console.error('Notification permission error:', error);
      return false;
    }
  }

  async checkPermissions(): Promise<boolean> {
    try {
      const result = await LocalNotifications.checkPermissions();
      this.permissionGranted = result.granted;
      return result.granted;
    } catch {
      return false;
    }
  }

  private async registerTypes() {
    try {
      await LocalNotifications.registerNotificationTypes({
        types: [
          {
            id: 1,
            actions: [
              {
                id: 'complete',
                title: 'Concluir',
                foreground: true
              },
              {
                id: 'snooze',
                title: 'Adiar',
                foreground: false
              }
            ]
          },
          {
            id: 2,
            actions: [
              {
                id: 'view',
                title: 'Ver',
                foreground: true
              }
            ]
          },
          {
            id: 3,
            actions: [
              {
                id: 'done',
                title: 'Feito!',
                foreground: true
              }
            ]
          }
        ]
      });
    } catch (error) {
      console.error('Register types error:', error);
    }
  }

  async scheduleTaskReminder(taskId: string, taskTitle: string, dueDate: string) {
    if (!this.permissionGranted) {
      const granted = await this.requestPermissions();
      if (!granted) return;
    }

    const dueDateTime = new Date(dueDate);
    const now = new Date();
    
    if (dueDateTime <= now) return;

    const notification: LocalNotificationSchema = {
      id: this.generateId(taskId),
      title: '📋 Tarefa pendente',
      body: taskTitle,
      schedule: { at: dueDateTime },
     Extra: {
        'taskId': taskId,
        'type': 'task_reminder'
      },
      actionTypeId: 1,
      smallIcon: 'ic_notification',
      color: '#007AFF'
    };

    await LocalNotifications.schedule({ notifications: [notification] });
  }

  async scheduleHabitReminder(habitId: string, habitName: string, time: string) {
    if (!this.permissionGranted) {
      const granted = await this.requestPermissions();
      if (!granted) return;
    }

    const [hours, minutes] = time.split(':').map(Number);
    const scheduleDate = new Date();
    scheduleDate.setHours(hours, minutes, 0, 0);
    
    if (scheduleDate <= new Date()) {
      scheduleDate.setDate(scheduleDate.getDate() + 1);
    }

    const notification: LocalNotificationSchema = {
      id: this.generateId(habitId),
      title: '💪 Hora do hábito!',
      body: habitName,
      schedule: {
        at: scheduleDate,
        repeats: {
          every: 'day'
        }
      },
      extra: {
        'habitId': habitId,
        'type': 'habit_reminder'
      },
      actionTypeId: 2,
      smallIcon: 'ic_notification',
      color: '#007AFF'
    };

    await LocalNotifications.schedule({ notifications: [notification] });
  }

  async scheduleGoalCheck(goalId: string, goalTitle: string, targetDate: string) {
    if (!this.permissionGranted) {
      const granted = await this.requestPermissions();
      if (!granted) return;
    }

    const targetDateTime = new Date(targetDate);
    const daysBefore = new Date(targetDateTime);
    daysBefore.setDate(daysBefore.getDate() - 1);
    
    if (daysBefore > new Date()) {
      const notification: LocalNotificationSchema = {
        id: this.generateId(goalId),
        title: '🎯 Verifique sua meta!',
        body: `${goalTitle} - Amanhã é o prazo!`,
        schedule: { at: daysBefore },
        extra: {
          'goalId': goalId,
          'type': 'goal_reminder'
        },
        actionTypeId: 3,
        smallIcon: 'ic_notification',
        color: '#FFD700'
      };

      await LocalNotifications.schedule({ notifications: [notification] });
    }
  }

  async scheduleWorkoutReminder(workoutName: string, scheduledTime: string) {
    if (!this.permissionGranted) {
      const granted = await this.requestPermissions();
      if (!granted) return;
    }

    const [hours, minutes] = scheduledTime.split(':').map(Number);
    const scheduleDate = new Date();
    scheduleDate.setHours(hours, minutes, 0, 0);
    
    if (scheduleDate <= new Date()) {
      scheduleDate.setDate(scheduleDate.getDate() + 1);
    }

    const notification: LocalNotificationSchema = {
      id: Date.now(),
      title: '🏋️ Hora de treinar!',
      body: workoutName,
      schedule: {
        at: scheduleDate,
        repeats: {
          every: 'day'
        }
      },
      extra: {
        'type': 'workout_reminder'
      },
      actionTypeId: 2,
      smallIcon: 'ic_notification',
      color: '#FF6B35'
    };

    await LocalNotifications.schedule({ notifications: [notification] });
  }

  async scheduleFinancialAlert(month: string, category: string, percentUsed: number) {
    if (!this.permissionGranted) {
      const granted = await this.requestPermissions();
      if (!granted) return;
    }

    if (percentUsed >= 80) {
      const notification: LocalNotificationSchema = {
        id: Date.now(),
        title: '⚠️ Alerta de orçamento!',
        body: `${category}: ${percentUsed}% do orçamento usado em ${month}`,
        schedule: { at: new Date(Date.now() + 3600000) },
        extra: {
          'type': 'budget_alert',
          'category': category
        },
        actionTypeId: 2,
        smallIcon: 'ic_notification',
        color: '#FF3B30'
      };

      await LocalNotifications.schedule({ notifications: [notification] });
    }
  }

  async cancelNotification(id: string | number) {
    await LocalNotifications.cancel({
      notifications: [{ id: Number(id) }]
    });
  }

  async cancelAllNotifications() {
    await LocalNotifications.cancelAll();
  }

  async getPendingNotifications(): Promise<ScheduledLocalNotification[]> {
    const result = await LocalNotifications.getPending();
    return result.notifications;
  }

  async removeAllDeliveredNotifications() {
    await LocalNotifications.removeAllDelivered();
  }

  private generateId(prefix: string): number {
    const hash = prefix.split('').reduce((acc, char) => {
      return ((acc << 5) - acc) + char.charCodeAt(0);
    }, 0);
    return Math.abs(hash % 100000);
  }
}

export const notificationService = new NotificationService();
export default notificationService;