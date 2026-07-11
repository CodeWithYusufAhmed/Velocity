package com.mdyusufahmed.velocity.data.ws

import com.mdyusufahmed.velocity.BuildConfig
import com.mdyusufahmed.velocity.data.TokenStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import kotlin.math.min

/**
 * Reconnecting WebSocket for /ws/game and /ws/social.
 * Exponential backoff 1s → 2s → 4s … capped at 30s; resets on connect.
 * Incoming frames are exposed as a SharedFlow of JsonObject.
 */
class VelocitySocket(
    private val path: String,               // "/ws/game" or "/ws/social"
    private val tokens: TokenStore,
    private val scope: CoroutineScope,
    private val client: OkHttpClient = OkHttpClient(),
) {
    private val json = Json { ignoreUnknownKeys = true }
    private var ws: WebSocket? = null
    private var job: Job? = null

    private val _messages = MutableSharedFlow<JsonObject>(extraBufferCapacity = 64)
    val messages: SharedFlow<JsonObject> = _messages

    private val _connected = MutableStateFlow(false)
    val connected: StateFlow<Boolean> = _connected

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch { connectLoop() }
    }

    fun stop() {
        job?.cancel()
        ws?.close(1000, null)
        ws = null
        _connected.value = false
    }

    fun send(payload: JsonObject): Boolean = ws?.send(payload.toString()) ?: false

    private suspend fun connectLoop() {
        var backoffMs = 1_000L
        while (true) {
            val access = tokens.access()
            if (access == null) { delay(2_000); continue }
            val url = BuildConfig.SERVER_BASE_URL
                .replaceFirst("http", "ws") + "$path?token=$access"
            val opened = kotlinx.coroutines.CompletableDeferred<Boolean>()
            val closed = kotlinx.coroutines.CompletableDeferred<Unit>()

            ws = client.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: okhttp3.Response) {
                    _connected.value = true
                    opened.complete(true)
                }
                override fun onMessage(webSocket: WebSocket, text: String) {
                    runCatching { json.parseToJsonElement(text) as JsonObject }
                        .onSuccess { _messages.tryEmit(it) }
                }
                override fun onFailure(webSocket: WebSocket, t: Throwable, response: okhttp3.Response?) {
                    _connected.value = false
                    opened.complete(false)
                    closed.complete(Unit)
                }
                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    _connected.value = false
                    closed.complete(Unit)
                }
            })

            if (opened.await()) backoffMs = 1_000L   // healthy connect → reset backoff
            closed.await()                            // wait for drop
            delay(backoffMs)
            backoffMs = min(backoffMs * 2, 30_000L)
        }
    }
}
