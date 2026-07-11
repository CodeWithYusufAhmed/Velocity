package com.mdyusufahmed.velocity.data.ws

import com.mdyusufahmed.velocity.data.TokenStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import javax.inject.Inject
import javax.inject.Singleton

/** App-lifetime holder of the two realtime channels. */
@Singleton
class SocketManager @Inject constructor(tokens: TokenStore) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    val game = VelocitySocket("/ws/game", tokens, scope)
    val social = VelocitySocket("/ws/social", tokens, scope)

    fun start() { game.start(); social.start() }
    fun stop() { game.stop(); social.stop() }
}
