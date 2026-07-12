package com.mdyusufahmed.velocity.data

import com.mdyusufahmed.velocity.data.db.MessageDao
import com.mdyusufahmed.velocity.data.db.MessageEntity
import com.mdyusufahmed.velocity.data.ws.SocketManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.serialization.json.*
import javax.inject.Inject
import javax.inject.Singleton

/** Bridges /ws/social DMs to the on-device Room history.
 *  Incoming dm_incoming → insert; our send → insert as "sending", then the
 *  server's dm_delivered (matched by client_ref) flips it to delivered/queued. */
@Singleton
class DmRepository @Inject constructor(
    private val dao: MessageDao,
    private val sockets: SocketManager,
    @dagger.hilt.android.qualifiers.ApplicationContext private val context: android.content.Context,
) {

    private fun notify(title: String, text: String, id: Int) {
        // System notification with default sound — like any messenger.
        val nm = context.getSystemService(android.app.NotificationManager::class.java)
        val channelId = "velocity_social"
        if (nm.getNotificationChannel(channelId) == null) {
            nm.createNotificationChannel(android.app.NotificationChannel(
                channelId, "Messages & friends",
                android.app.NotificationManager.IMPORTANCE_HIGH))
        }
        val tap = android.app.PendingIntent.getActivity(context, 0,
            android.content.Intent(context, com.mdyusufahmed.velocity.MainActivity::class.java),
            android.app.PendingIntent.FLAG_IMMUTABLE)
        runCatching {
            nm.notify(id, androidx.core.app.NotificationCompat.Builder(context, channelId)
                .setSmallIcon(com.mdyusufahmed.velocity.R.drawable.ic_launcher_foreground)
                .setContentTitle(title).setContentText(text)
                .setContentIntent(tap).setAutoCancel(true)
                .setPriority(androidx.core.app.NotificationCompat.PRIORITY_HIGH)
                .build())
        }
    }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val pendingRefs = mutableMapOf<String, Long>()  // client_ref -> row id
    private var refCounter = 0L

    val conversations = dao.conversations()
    fun conversation(peerId: Long) = dao.conversation(peerId)

    init {
        scope.launch {
            sockets.social.messages.collect { msg ->
                when (msg["type"]?.jsonPrimitive?.contentOrNull) {
                    "dm_incoming" -> {
                        val senderId = msg["sender_id"]!!.jsonPrimitive.long
                        val senderName = msg["sender_name"]!!.jsonPrimitive.content
                        val text = msg["text"]!!.jsonPrimitive.content
                        dao.insert(MessageEntity(
                            peerId = senderId, peerName = senderName, text = text,
                            mine = false, sentAt = System.currentTimeMillis(),
                            state = "delivered"))
                        notify(senderName, text, senderId.toInt())
                    }
                    "friend_request" -> notify(
                        "Friend request",
                        "${msg["sender_name"]?.jsonPrimitive?.contentOrNull ?: "Someone"} wants to be your friend",
                        -1)
                    "friend_accepted" -> notify(
                        "Friend request accepted",
                        "${msg["display_name"]?.jsonPrimitive?.contentOrNull ?: "Someone"} accepted your request",
                        -2)
                    "dm_delivered" -> {
                        val ref = msg["client_ref"]?.jsonPrimitive?.contentOrNull ?: return@collect
                        val rowId = pendingRefs.remove(ref) ?: return@collect
                        val live = msg["delivered"]?.jsonPrimitive?.booleanOrNull == true
                        dao.setState(rowId, if (live) "delivered" else "queued")
                    }
                    "error" -> {
                        val ref = msg["client_ref"]?.jsonPrimitive?.contentOrNull ?: return@collect
                        pendingRefs.remove(ref)?.let { dao.setState(it, "failed") }
                    }
                }
            }
        }
    }

    fun send(peerId: Long, peerName: String, text: String) {
        if (text.isBlank()) return
        scope.launch {
            val ref = "r${refCounter++}-${System.currentTimeMillis()}"
            val rowId = dao.insert(MessageEntity(
                peerId = peerId, peerName = peerName, text = text.trim(),
                mine = true, sentAt = System.currentTimeMillis(), state = "sending"))
            pendingRefs[ref] = rowId
            sockets.social.send(buildJsonObject {
                put("type", "send_dm"); put("recipient_id", peerId)
                put("text", text.trim()); put("client_ref", ref)
            })
        }
    }
}
