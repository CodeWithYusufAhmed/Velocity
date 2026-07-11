package com.mdyusufahmed.velocity.ui.game

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mdyusufahmed.velocity.data.OddsSlotDto
import com.mdyusufahmed.velocity.data.RecentRound
import com.mdyusufahmed.velocity.data.Top3Entry
import com.mdyusufahmed.velocity.data.VelocityApi
import com.mdyusufahmed.velocity.data.ws.SocketManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.*
import javax.inject.Inject

data class SpinResult(
    val winningPosition: Int, val winningName: String, val multiplier: Int,
    val top3: List<Top3Entry>, val myPayout: Long,
)

data class GameUiState(
    val phase: String = "…",            // BETTING / SPINNING / RESULTS
    val roundId: Long = 0,
    val secondsLeft: Int = 0,
    val balance: Long = 0,
    val selectedChip: Long = 500,
    val myBets: Map<Int, Long> = emptyMap(),   // slot position -> total this round
    val odds: List<OddsSlotDto> = emptyList(),
    val recent: List<RecentRound> = emptyList(),
    val result: SpinResult? = null,            // non-null → results overlay
    val bonusReady: Boolean = false,
    val rescueOffered: Boolean = false,
    val rescuesLeft: Int = 0,
    val limitReached: Boolean = false,
    val moneyNotSpent: Double = 0.0,
    val todayWon: Long = 0,
    val error: String? = null,
    val connected: Boolean = false,
)

val CHIPS = listOf(200L, 500L, 1_000L, 4_000L, 10_000L, 30_000L, 100_000L)

@HiltViewModel
class GameViewModel @Inject constructor(
    private val api: VelocityApi,
    sockets: SocketManager,
) : ViewModel() {

    val state = MutableStateFlow(GameUiState())
    private val socket = sockets.game

    init {
        viewModelScope.launch { socket.connected.collect { c ->
            state.value = state.value.copy(connected = c) } }
        viewModelScope.launch { socket.messages.collect(::onMessage) }
        refreshStatic()
    }

    fun refreshStatic() = viewModelScope.launch {
        runCatching { api.odds() }.onSuccess { state.value = state.value.copy(odds = it) }
        runCatching { api.recentRounds() }.onSuccess { state.value = state.value.copy(recent = it) }
        runCatching { api.profile() }.onSuccess { p ->
            state.value = state.value.copy(
                balance = p.balance,
                bonusReady = !p.today.bonusClaimed,
                rescuesLeft = 3 - p.today.rescuesUsed,
                rescueOffered = p.balance < 200 && p.today.rescuesUsed < 3,
                moneyNotSpent = p.moneyNotSpent.dollarsNotSpent,
                todayWon = p.today.totalWon,
            )
        }
    }

    fun selectChip(v: Long) { state.value = state.value.copy(selectedChip = v) }

    fun tapSlot(position: Int) {
        val s = state.value
        if (s.phase != "BETTING" || s.limitReached) return
        socket.send(buildJsonObject {
            put("type", "place_bet"); put("slot", position); put("amount", s.selectedChip)
        })
    }

    fun claimBonus() = viewModelScope.launch {
        runCatching { api.claimBonus() }.onSuccess {
            state.value = state.value.copy(balance = it.balance, bonusReady = false)
        }
    }

    fun claimRescue() = viewModelScope.launch {
        runCatching { api.claimRescue() }.onSuccess {
            state.value = state.value.copy(
                balance = it.balance, rescueOffered = false,
                rescuesLeft = state.value.rescuesLeft - 1)
        }.onFailure { state.value = state.value.copy(rescueOffered = false) }
    }

    val verify = MutableStateFlow<com.mdyusufahmed.velocity.data.VerifyResponse?>(null)
    fun openVerify(roundId: Long) = viewModelScope.launch {
        runCatching { api.verifyRound(roundId) }.onSuccess { verify.value = it }
    }
    fun closeVerify() { verify.value = null }

    fun dismissResult() { state.value = state.value.copy(result = null) }
    fun dismissError() { state.value = state.value.copy(error = null) }

    private fun onMessage(msg: JsonObject) {
        val s = state.value
        when (msg["type"]?.jsonPrimitive?.contentOrNull) {
            "round_state" -> {
                val phase = msg["phase"]!!.jsonPrimitive.content
                val roundId = msg["round_id"]!!.jsonPrimitive.long
                val newRound = roundId != s.roundId && phase == "BETTING"
                state.value = s.copy(
                    phase = phase, roundId = roundId,
                    secondsLeft = msg["seconds_left"]?.jsonPrimitive?.intOrNull ?: 0,
                    myBets = if (newRound) emptyMap() else s.myBets,
                    limitReached = if (newRound) false else s.limitReached,
                )
            }
            "bet_ack" -> {
                val slot = msg["slot"]!!.jsonPrimitive.int
                val amount = msg["amount"]!!.jsonPrimitive.long
                state.value = s.copy(
                    balance = msg["balance"]!!.jsonPrimitive.long,
                    myBets = s.myBets + (slot to (s.myBets[slot] ?: 0L) + amount),
                )
            }
            "spin_result" -> {
                val pos = msg["winning_position"]!!.jsonPrimitive.int
                val mult = msg["multiplier"]!!.jsonPrimitive.int
                val stake = s.myBets[pos] ?: 0L
                val payout = stake * (mult + 1)
                val top3 = msg["top3"]?.jsonArray?.map {
                    val o = it.jsonObject
                    Top3Entry(o["user_id"]!!.jsonPrimitive.long,
                        o["display_name"]!!.jsonPrimitive.content,
                        o["won"]!!.jsonPrimitive.long)
                } ?: emptyList()
                state.value = s.copy(
                    result = SpinResult(pos, msg["winning_name"]!!.jsonPrimitive.content,
                        mult, top3, payout),
                    balance = s.balance + payout,
                    todayWon = s.todayWon + payout,
                    rescueOffered = s.balance + payout < 200 && s.rescuesLeft > 0,
                )
                viewModelScope.launch {
                    runCatching { api.recentRounds() }
                        .onSuccess { state.value = state.value.copy(recent = it) }
                }
            }
            "error" -> {
                val text = msg["message"]?.jsonPrimitive?.contentOrNull ?: "Error"
                state.value = if (text.contains("round limit"))
                    s.copy(limitReached = true) else s.copy(error = text)
            }
        }
    }
}
