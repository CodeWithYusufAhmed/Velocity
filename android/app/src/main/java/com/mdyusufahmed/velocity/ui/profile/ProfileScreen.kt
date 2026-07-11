package com.mdyusufahmed.velocity.ui.profile

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mdyusufahmed.velocity.data.AuthRepository
import com.mdyusufahmed.velocity.data.Profile
import com.mdyusufahmed.velocity.data.VelocityApi
import com.mdyusufahmed.velocity.data.ws.SocketManager
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

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Profile", style = MaterialTheme.typography.headlineMedium)

        when (val p = profile) {
            null -> if (error != null) {
                Text(error!!, color = MaterialTheme.colorScheme.error)
                Button(onClick = vm::refresh) { Text("Retry") }
            } else CircularProgressIndicator()
            else -> {
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
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
                        Text("Today", style = MaterialTheme.typography.titleMedium)
                        Text("Rounds: ${p.today.roundsPlayed} · Won: ${"%,d".format(p.today.totalWon)}" +
                             " · Biggest: ${"%,d".format(p.today.biggestWin)}")
                    }
                }
                Text("Profile picture — coming soon",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
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
