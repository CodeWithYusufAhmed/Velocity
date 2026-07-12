package com.mdyusufahmed.velocity.voice

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.mdyusufahmed.velocity.MainActivity
import com.mdyusufahmed.velocity.R

/**
 * Keeps voice alive while the screen is off / app is backgrounded.
 * Android suspends normal apps on lock; a foreground service with the
 * microphone/mediaPlayback types tells the OS "this is an ongoing call".
 */
class VoiceService : Service() {

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val channelId = "velocity_voice"
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(channelId) == null) {
            nm.createNotificationChannel(
                NotificationChannel(channelId, "Voice Table",
                    NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Shown while you are in a voice Table"
                })
        }
        val tableName = intent?.getStringExtra("table_name") ?: "a Table"
        val tapIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE)
        val notification: Notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle("Velocity — in $tableName")
            .setContentText("Voice is active. Tap to return.")
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentIntent(tapIntent)
            .setOngoing(true)
            .build()

        val types = if (Build.VERSION.SDK_INT >= 30)
            ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE or
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
        else 0
        ServiceCompat.startForeground(this, 1, notification, types)
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        fun start(context: Context, tableName: String) {
            context.startForegroundService(
                Intent(context, VoiceService::class.java).putExtra("table_name", tableName))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, VoiceService::class.java))
        }
    }
}
