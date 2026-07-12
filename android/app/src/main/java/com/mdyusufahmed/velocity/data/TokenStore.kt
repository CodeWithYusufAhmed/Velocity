package com.mdyusufahmed.velocity.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore("velocity_tokens")

@Singleton
class TokenStore @Inject constructor(@ApplicationContext private val context: Context) {
    private val accessKey = stringPreferencesKey("access")
    private val refreshKey = stringPreferencesKey("refresh")

    val isLoggedIn: Flow<Boolean> =
        context.dataStore.data.map { !it[refreshKey].isNullOrEmpty() }

    suspend fun save(access: String, refresh: String) {
        context.dataStore.edit { it[accessKey] = access; it[refreshKey] = refresh }
    }

    suspend fun access(): String? = context.dataStore.data.first()[accessKey]
    suspend fun refresh(): String? = context.dataStore.data.first()[refreshKey]

    /** Used by the OkHttp Authenticator, which runs on a background thread. */
    fun accessBlocking(): String? = runBlocking { access() }
    fun refreshBlocking(): String? = runBlocking { refresh() }
    fun saveBlocking(access: String, refresh: String) = runBlocking { save(access, refresh) }

    // Studio Noise Removal (RNNoise) preference — device-local.
    private val studioNoiseKey = stringPreferencesKey("studio_noise")
    val studioNoise: Flow<Boolean> =
        context.dataStore.data.map { it[studioNoiseKey] == "on" }

    suspend fun setStudioNoise(on: Boolean) {
        context.dataStore.edit { it[studioNoiseKey] = if (on) "on" else "off" }
    }

    suspend fun studioNoiseNow(): Boolean =
        context.dataStore.data.first()[studioNoiseKey] == "on"

    suspend fun clear() {
        val keep = studioNoiseNow()
        context.dataStore.edit { it.clear() }
        setStudioNoise(keep)  // logout shouldn't reset audio preferences
    }
}
