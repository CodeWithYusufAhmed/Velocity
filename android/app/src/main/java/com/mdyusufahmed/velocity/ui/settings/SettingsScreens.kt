package com.mdyusufahmed.velocity.ui.settings

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
import com.mdyusufahmed.velocity.data.RoundLimitRequest
import com.mdyusufahmed.velocity.data.VelocityApi
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val limit: Int? = null,
    val pendingLimit: Int? = null,
    val pendingDate: String? = null,
    val error: String? = null,
    val loading: Boolean = true,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val api: VelocityApi,
    private val tokens: com.mdyusufahmed.velocity.data.TokenStore,
) : ViewModel() {
    val state = MutableStateFlow(SettingsUiState())
    val studioNoise = MutableStateFlow(false)

    fun setStudioNoise(on: Boolean) = viewModelScope.launch {
        tokens.setStudioNoise(on)
        studioNoise.value = on
    }

    init {
        refresh()
        viewModelScope.launch { tokens.studioNoise.collect { studioNoise.value = it } }
    }

    fun refresh() = viewModelScope.launch {
        runCatching { api.profile() }
            .onSuccess { state.value = SettingsUiState(limit = it.dailyRoundLimit, loading = false) }
            .onFailure { state.value = SettingsUiState(error = "Could not load", loading = false) }
    }

    fun setLimit(limit: Int?) = viewModelScope.launch {
        runCatching { api.setRoundLimit(RoundLimitRequest(limit)) }
            .onSuccess {
                state.value = state.value.copy(
                    limit = it.dailyRoundLimit, pendingLimit = it.pendingRoundLimit,
                    pendingDate = it.pendingEffectiveDate, error = null)
            }
            .onFailure { state.value = state.value.copy(error = "Could not save") }
    }
}

@Composable
fun SettingsScreen(vm: SettingsViewModel = hiltViewModel()) {
    val state by vm.state.collectAsState()
    var input by remember(state.limit) { mutableStateOf(state.limit?.toString() ?: "") }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Settings", style = MaterialTheme.typography.headlineMedium)

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Daily round limit", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Set a maximum number of rounds you can bet in per day. " +
                    "Lowering it applies right away; raising it only applies from tomorrow. " +
                    "Watching is always free.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Row(verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        input, { input = it.filter(Char::isDigit) },
                        label = { Text("Rounds per day") },
                        singleLine = true, modifier = Modifier.weight(1f))
                    Button(onClick = { input.toIntOrNull()?.let(vm::setLimit) }) { Text("Set") }
                }
                if (state.limit != null) {
                    TextButton(onClick = { vm.setLimit(null) }) { Text("Turn limit off") }
                }
                state.pendingLimit?.let {
                    Text("Raise to $it takes effect on ${state.pendingDate}",
                        color = MaterialTheme.colorScheme.secondary,
                        style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Voice", style = MaterialTheme.typography.titleMedium)
                Text("Noise cancellation, echo cancellation and auto gain are always ON " +
                     "(WebRTC built-ins).", style = MaterialTheme.typography.bodySmall)
                val studio by vm.studioNoise.collectAsState()
                Row(verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()) {
                    Text("Studio Noise Removal (RNNoise)", style = MaterialTheme.typography.bodyMedium)
                    Switch(checked = studio, onCheckedChange = vm::setStudioNoise)
                }
                Text("Deep-learning noise removal on your mic (experimental). " +
                     "Takes effect the next time you join a Table.",
                    style = MaterialTheme.typography.labelSmall)
            }
        }

        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    }
}
