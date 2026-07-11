package com.mdyusufahmed.velocity.data

import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: VelocityApi,
    private val tokens: TokenStore,
) {
    val isLoggedIn = tokens.isLoggedIn

    suspend fun register(email: String, displayName: String, password: String) =
        save(api.register(RegisterRequest(email, displayName, password)))

    suspend fun login(email: String, password: String) =
        save(api.login(LoginRequest(email, password)))

    suspend fun googleLogin(idToken: String) =
        save(api.google(GoogleLoginRequest(idToken)))

    suspend fun logout() {
        tokens.refresh()?.let { runCatching { api.logout(RefreshRequest(it)) } }
        tokens.clear()
    }

    private suspend fun save(resp: AuthResponse): AuthResponse {
        tokens.save(resp.tokens.accessToken, resp.tokens.refreshToken)
        return resp
    }
}
