package com.mdyusufahmed.velocity.ui.profile

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mdyusufahmed.velocity.data.AuthRepository
import com.mdyusufahmed.velocity.data.Profile
import com.mdyusufahmed.velocity.data.VelocityApi
import com.mdyusufahmed.velocity.data.ws.SocketManager
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val api: VelocityApi,
    private val auth: AuthRepository,
    val sockets: SocketManager,
) : ViewModel() {
    val profile = MutableStateFlow<Profile?>(null)
    val error = MutableStateFlow<String?>(null)

    init { refresh() }

    fun refresh() = viewModelScope.launch {
        runCatching { api.profile() }
            .onSuccess { profile.value = it; error.value = null }
            .onFailure { error.value = "Could not load profile" }
    }

    fun logout() = viewModelScope.launch {
        sockets.stop()
        auth.logout()
    }

    fun uploadAvatar(context: android.content.Context, uri: android.net.Uri) = viewModelScope.launch {
        runCatching {
            val src = context.contentResolver.openInputStream(uri)!!.use {
                android.graphics.BitmapFactory.decodeStream(it)
            }
            val size = 128  // small circular avatar per spec change
            val scaled = android.graphics.Bitmap.createScaledBitmap(src, size, size, true)
            val out = java.io.ByteArrayOutputStream()
            scaled.compress(android.graphics.Bitmap.CompressFormat.JPEG, 85, out)
            val part = okhttp3.MultipartBody.Part.createFormData(
                "file", "avatar.jpg", out.toByteArray().toRequestBody("image/jpeg".toMediaType()))
            api.uploadAvatar(part)
        }.onSuccess { refresh() }
            .onFailure { error.value = "Avatar upload failed" }
    }
}

@Composable
fun ProfileScreen(
    onOpenSettings: () -> Unit,
    onOpenAbout: () -> Unit,
    vm: ProfileViewModel = hiltViewModel(),
) {
    val profile by vm.profile.collectAsState()
    val error by vm.error.collectAsState()
    val gameConnected by vm.sockets.game.connected.collectAsState()
    val context = androidx.compose.ui.platform.LocalContext.current

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Profile", style = MaterialTheme.typography.headlineMedium)

        val picker = androidx.activity.compose.rememberLauncherForActivityResult(
            androidx.activity.result.contract.ActivityResultContracts.GetContent()) { uri ->
            uri?.let { vm.uploadAvatar(context, it) }
        }
        when (val p = profile) {
            null -> if (error != null) {
                Text(error!!, color = MaterialTheme.colorScheme.error)
                Button(onClick = vm::refresh) { Text("Retry") }
            } else CircularProgressIndicator()
            else -> {
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            com.mdyusufahmed.velocity.ui.tables.Avatar(p.id, p.displayName, 56)
                            TextButton(onClick = { picker.launch("image/*") }) {
                                Text("Change photo")
                            }
                        }
                        Text(p.displayName, style = MaterialTheme.typography.titleLarge)
                        if (p.vipTier > 0) {
                            Text("VIP${p.vipTier}", color = MaterialTheme.colorScheme.secondary,
                                style = MaterialTheme.typography.labelLarge)
                        }
                        Text(p.email, style = MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.height(8.dp))
                        Text("Balance: ${"%,d".format(p.balance)} coins",
                            style = MaterialTheme.typography.titleMedium)
                    }
                }
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("💸 Money you did NOT spend",
                            style = MaterialTheme.typography.titleMedium)
                        Text("$${"%.2f".format(p.moneyNotSpent.dollarsNotSpent)}",
                            style = MaterialTheme.typography.displaySmall,
                            color = MaterialTheme.colorScheme.secondary)
                        Text(p.moneyNotSpent.estimateNote,
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("👑 VIP status", style = MaterialTheme.typography.titleMedium)
                        if (p.vipTier > 0) {
                            Text("VIP${p.vipTier} active",
                                style = MaterialTheme.typography.titleLarge,
                                color = MaterialTheme.colorScheme.secondary)
                            Text("Earned by playing — never bought. Higher tiers replace " +
                                 "lower ones instantly.", style = MaterialTheme.typography.bodySmall)
                        } else {
                            Text("No VIP right now", style = MaterialTheme.typography.bodyMedium)
                            Text("Win 1,000,000+ coins in a single day (Dhaka time) to earn VIP1.",
                                style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Today", style = MaterialTheme.typography.titleMedium)
                        Text("Rounds: ${p.today.roundsPlayed} · Won: ${"%,d".format(p.today.totalWon)}" +
                             " · Biggest: ${"%,d".format(p.today.biggestWin)}")
                    }
                }
            }
        }

        Text(
            if (gameConnected) "● Connected to game server" else "○ Reconnecting…",
            style = MaterialTheme.typography.bodySmall,
            color = if (gameConnected) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.error,
        )

        OutlinedButton(onClick = onOpenSettings, modifier = Modifier.fillMaxWidth()) { Text("Settings") }
        OutlinedButton(onClick = onOpenAbout, modifier = Modifier.fillMaxWidth()) { Text("About & odds") }
        TextButton(onClick = vm::logout, modifier = Modifier.fillMaxWidth()) { Text("Log out") }
    }
}
