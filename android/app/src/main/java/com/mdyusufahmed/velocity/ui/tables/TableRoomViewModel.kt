package com.mdyusufahmed.velocity.ui.tables

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mdyusufahmed.velocity.data.*
import com.mdyusufahmed.velocity.data.ws.SocketManager
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import io.livekit.android.LiveKit
import io.livekit.android.events.collect
import io.livekit.android.room.Room
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.*
import retrofit2.HttpException
import javax.inject.Inject

data class ChatMessage(val userId: Long, val name: String, val vipTier: Int, val text: String)
data class Welcome(val name: String, val vipTier: Int)

data class RoomUiState(
    val tableId: Long = 0,
    val myRole: String = "user",
    val myVip: Int = 0,
    val chairCount: Int = 8,
    val chairs: Map<Int, Long> = emptyMap(),        // position -> user id
    val members: List<MemberDto> = emptyList(),     // owner → admins → users
    val chat: List<ChatMessage> = emptyList(),
    val speaking: Set<Long> = emptySet(),
    val micOn: Boolean = false,
    val seated: Int? = null,
    val welcome: Welcome? = null,
    val giftSheet: Boolean = false,
    val notice: String? = null,
    val closed: Boolean = false,
)

@HiltViewModel
class TableRoomViewModel @Inject constructor(
    private val api: VelocityApi,
    private val sockets: SocketManager,
    @ApplicationContext private val appContext: Context,
) : ViewModel() {

    val state = MutableStateFlow(RoomUiState())
    private var room: Room? = null
    private var myId: Long = -1

    fun join(tableId: Long) {
        if (state.value.tableId == tableId) return
        state.value = RoomUiState(tableId = tableId)
        viewModelScope.launch {
            runCatching { api.profile() }.onSuccess { myId = it.id }
            try {
                val j = api.joinTable(tableId)
                state.value = state.value.copy(
                    myRole = j.role, myVip = j.vipTier, chairCount = j.chairCount,
                    chairs = j.chairs.mapKeys { it.key.toInt() })
                connectVoice(j.livekitUrl, j.livekitToken)
                com.mdyusufahmed.velocity.voice.VoiceService.start(appContext, "Table")
                refreshMembers()
            } catch (e: HttpException) {
                state.value = state.value.copy(
                    notice = if (e.code() == 403) "You are blocked from this Table"
                             else "Could not join", closed = true)
            } catch (e: Exception) {
                state.value = state.value.copy(notice = "Could not join", closed = true)
            }
        }
        viewModelScope.launch { sockets.social.messages.collect(::onSocial) }
    }

    private suspend fun connectVoice(url: String, token: String) {
        try {
            val r = LiveKit.create(appContext)
            r.connect(url, token)
            r.localParticipant.setMicrophoneEnabled(false)  // listener until seated
            room = r
            viewModelScope.launch {
                r.events.collect { e ->
                    if (e is io.livekit.android.events.RoomEvent.ActiveSpeakersChanged) {
                        state.value = state.value.copy(
                            speaking = e.speakers.mapNotNull { it.identity?.value?.toLongOrNull() }.toSet())
                    }
                }
            }
        } catch (e: Exception) {
            state.value = state.value.copy(notice = "Voice unavailable — chat still works")
        }
    }

    fun refreshMembers() = viewModelScope.launch {
        runCatching { api.members(state.value.tableId) }.onSuccess { m ->
            state.value = state.value.copy(
                members = m,
                chairs = m.filter { it.chair != null }.associate { it.chair!! to it.id })
        }
    }

    fun tapChair(position: Int) = viewModelScope.launch {
        val s = state.value
        try {
            if (s.seated == position) {
                api.stand(s.tableId)
                room?.localParticipant?.setMicrophoneEnabled(false)
                state.value = s.copy(seated = null, micOn = false)
            } else {
                api.sit(s.tableId, SitRequest(position))
                room?.localParticipant?.setMicrophoneEnabled(true)
                state.value = s.copy(seated = position, micOn = true)
            }
            refreshMembers()
        } catch (e: HttpException) {
            state.value = state.value.copy(notice = "Chair is taken")
        }
    }

    fun toggleMic() = viewModelScope.launch {
        val s = state.value
        if (s.seated == null) return@launch
        room?.localParticipant?.setMicrophoneEnabled(!s.micOn)
        state.value = s.copy(micOn = !s.micOn)
    }

    fun sendChat(text: String) {
        if (text.isBlank()) return
        sockets.social.send(buildJsonObject {
            put("type", "table_chat_send")
            put("table_id", state.value.tableId)
            put("text", text.trim())
        })
    }

    fun moderate(action: String, target: MemberDto) = viewModelScope.launch {
        val id = state.value.tableId
        try {
            when (action) {
                "kick" -> {
                    val r = api.kick(id, TargetRequest(target.id))
                    if (!r.kicked) state.value = state.value.copy(
                        notice = r.reason ?: "This user has Anti-Kick")
                }
                "mute" -> api.muteUser(id, TargetRequest(target.id))
                "block_table" -> api.blockFromTable(id, TargetRequest(target.id))
                "chat_ban" -> api.chatBan(id, TargetRequest(target.id))
                "make_admin" -> api.grantAdmin(id, TargetRequest(target.id))
                "block_personal" -> api.blockUser(target.id)
                "report" -> api.report(ReportRequest(target.id, "inappropriate", null, id))
            }
            if (action == "report") state.value = state.value.copy(notice = "Report sent — thank you")
            refreshMembers()
        } catch (e: HttpException) {
            state.value = state.value.copy(
                notice = if (e.code() == 403) "You don't have permission for that" else "Action failed")
        }
    }

    val bannedList = MutableStateFlow<List<BlockedUserDto>?>(null)  // non-null = sheet open

    fun openBanned() = viewModelScope.launch {
        runCatching { api.tableBlocks(state.value.tableId) }
            .onSuccess { bannedList.value = it }
            .onFailure { state.value = state.value.copy(notice = "Owner or admin only") }
    }

    fun unbanFromTable(userId: Long) = viewModelScope.launch {
        runCatching { api.tableUnblock(state.value.tableId, userId) }
            .onSuccess { bannedList.value = bannedList.value?.filter { it.userId != userId } }
            .onFailure { state.value = state.value.copy(notice = "Only the owner can unban") }
    }

    fun closeBanned() { bannedList.value = null }

    fun closeTable() = viewModelScope.launch {
        runCatching { api.closeTable(state.value.tableId) }
            .onSuccess { state.value = state.value.copy(closed = true) }
            .onFailure { state.value = state.value.copy(notice = "Only the owner can close") }
    }

    fun openGifts(open: Boolean) { state.value = state.value.copy(giftSheet = open) }
    fun dismissNotice() { state.value = state.value.copy(notice = null) }
    fun dismissWelcome() { state.value = state.value.copy(welcome = null) }

    fun leave() = viewModelScope.launch {
        runCatching { api.leaveTable(state.value.tableId) }
        room?.disconnect()
        room = null
        com.mdyusufahmed.velocity.voice.VoiceService.stop(appContext)
        state.value = RoomUiState()
    }

    override fun onCleared() {
        room?.disconnect()
        com.mdyusufahmed.velocity.voice.VoiceService.stop(appContext)
    }

    private fun onSocial(msg: JsonObject) {
        val s = state.value
        val type = msg["type"]?.jsonPrimitive?.contentOrNull ?: return
        val tid = msg["table_id"]?.jsonPrimitive?.longOrNull
        if (tid != null && tid != s.tableId) return
        when (type) {
            "table_chat_message" -> state.value = s.copy(chat = (s.chat + ChatMessage(
                msg["user_id"]!!.jsonPrimitive.long,
                msg["display_name"]!!.jsonPrimitive.content,
                msg["vip_tier"]?.jsonPrimitive?.intOrNull ?: 0,
                msg["text"]!!.jsonPrimitive.content)).takeLast(100))
            "table_event" -> {
                when (msg["event"]?.jsonPrimitive?.contentOrNull) {
                    "join" -> {
                        val tier = msg["vip_tier"]?.jsonPrimitive?.intOrNull ?: 0
                        if (tier >= 2) state.value = s.copy(welcome = Welcome(
                            msg["display_name"]?.jsonPrimitive?.contentOrNull ?: "?", tier))
                    }
                    "kick" -> if (msg["user_id"]?.jsonPrimitive?.longOrNull == myId &&
                                  msg["kicked"]?.jsonPrimitive?.booleanOrNull == true) {
                        state.value = s.copy(closed = true, notice = "You were removed from the Table")
                    }
                    "closed" -> state.value = s.copy(closed = true, notice = "The owner closed this Table")
                }
                refreshMembers()
            }
        }
    }
}
