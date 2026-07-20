package com.sirius.app.widget

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.SharedPreferences
import android.widget.RemoteViews
import android.app.PendingIntent
import android.content.Intent
import android.view.View
import com.sirius.app.R

class SiriusWidgetProvider : AppWidgetProvider() {
    
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            updateAppWidget(context, appWidgetManager, appWidgetId)
        }
    }

    companion object {
        private const val PREFS_NAME = "SiriusWidgetPrefs"
        private const val KEY_TASKS_COUNT = "tasks_count"
        private const val KEY_HABITS_STREAK = "habits_streak"
        private const val KEY_XP = "current_xp"
        private const val KEY_RANK = "current_rank"

        internal fun updateAppWidget(
            context: Context,
            appWidgetManager: AppWidgetManager,
            appWidgetId: Int
        ) {
            val prefs: SharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            
            val tasksCount = prefs.getInt(KEY_TASKS_COUNT, 0)
            val habitsStreak = prefs.getInt(KEY_HABITS_STREAK, 0)
            val currentXp = prefs.getInt(KEY_XP, 0)
            val currentRank = prefs.getString(KEY_RANK, "Recruta") ?: "Recruta"

            val views = RemoteViews(context.packageName, R.layout.sirius_widget)
            
            if (tasksCount > 0) {
                views.setTextViewText(R.id.widget_tasks, "$tasksCount tarefas hoje")
                views.setViewVisibility(R.id.widget_tasks, View.VISIBLE)
            } else {
                views.setViewVisibility(R.id.widget_tasks, View.GONE)
            }
            
            if (habitsStreak > 0) {
                views.setTextViewText(R.id.widget_streak, "🔥 $habitsStreak dias de sequência!")
                views.setViewVisibility(R.id.widget_streak, View.VISIBLE)
            } else {
                views.setViewVisibility(R.id.widget_streak, View.GONE)
            }
            
            views.setTextViewText(R.id.widget_xp, "$currentXp XP")
            views.setTextViewText(R.id.widget_rank, currentRank)

            val intent = Intent(context, com.sirius.app.MainActivity::class.java)
            val pendingIntent = PendingIntent.getActivity(
                context,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            views.setOnClickPendingIntent(R.id.widget_container, pendingIntent)

            appWidgetManager.updateAppWidget(appWidgetId, views)
        }

        fun updateWidgetData(
            context: Context,
            tasksCount: Int,
            habitsStreak: Int,
            currentXp: Int,
            currentRank: String
        ) {
            val prefs: SharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().apply {
                putInt(KEY_TASKS_COUNT, tasksCount)
                putInt(KEY_HABITS_STREAK, habitsStreak)
                putInt(KEY_XP, currentXp)
                putString(KEY_RANK, currentRank)
                apply()
            }
        }
    }

    override fun onEnabled(context: Context) {
    }

    override fun onDisabled(context: Context) {
    }
}