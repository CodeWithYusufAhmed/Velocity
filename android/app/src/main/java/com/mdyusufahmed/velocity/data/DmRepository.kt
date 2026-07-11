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
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val pendingRefs = mutableMapOf<String, Long>()  // client_ref -> row id
    private var refCounter = 0L

    val conversations = dao.conversations()
    fun conversation(peerId: Long) = dao.conversation(peerId)

    init {
        scope.launch {
            sockets.social.messages.collect { msg ->
                when (msg["type"]?.jsonPrimitive?.contentOrNull) {
                    "dm_incoming" -> dao.insert(MessageEntity(
                        peerId = msg["sender_id"]!!.jsonPrimitive.long,
                        peerName = msg["sender_name"]!!.jsonPrimitive.content,
                        text = msg["text"]!!.jsonPrimitive.content,
                        mine = false, sentAt = System.currentTimeMillis(),
                        state = "delivered"))
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
