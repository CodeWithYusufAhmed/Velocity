package com.mdyusufahmed.velocity.ui.mod

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.mdyusufahmed.velocity.data.*
import com.mdyusufahmed.velocity.ui.theme.Amber
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ModViewModel @Inject constructor(private val api: VelocityApi) : ViewModel() {
    val results = MutableStateFlow<List<SearchResult>>(emptyList())
    val reports = MutableStateFlow<List<ModReport>>(emptyList())
    val notice = MutableStateFlow<String?>(null)

    init { loadReports() }

    fun search(q: String) = viewModelScope.launch {
        if (q.length < 2) { results.value = emptyList(); return@launch }
        runCatching { api.searchUsers(q) }.onSuccess { results.value = it }
    }

    fun loadReports() = viewModelScope.launch {
        runCatching { api.modReports() }.onSuccess { reports.value = it }
    }

    private fun act(ok: String, block: suspend () -> Unit) = viewModelScope.launch {
        runCatching { block() }
            .onSuccess { notice.value = ok }
            .onFailure { notice.value = "Failed — are you a moderator?" }
    }

    fun giftVip(userId: Long, tier: Int) = act("Gifted VIP$tier") {
        api.modGiftVip(GiftVipRequest(userId, tier)) }
    fun giftCoins(userId: Long, amount: Long) = act("Gifted ${"%,d".format(amount)} coins") {
        api.modGiftCoins(GiftCoinsRequest(userId, amount)) }
    fun ban(userId: Long, minutes: Int?) = act(
        if (minutes == null) "Banned permanently" else "Banned $minutes min") {
        api.modBan(BanRequest(userId, minutes)) }
    fun unban(userId: Long) = act("Unbanned") { api.modUnban(userId) }
    fun resolve(id: Long) = act("Report resolved") { api.modResolveReport(id); loadReports() }
    fun dismiss() { notice.value = null }
}

@Composable
fun ModeratorScreen(onBack: () -> Unit, vm: ModViewModel = hiltViewModel()) {
    val results by vm.results.collectAsState()
    val reports by vm.reports.collectAsState()
    val notice by vm.notice.collectAsState()
    var query by remember { mutableStateOf("") }
    var target by remember { mutableStateOf<SearchResult?>(null) }
    var coins by remember { mutableStateOf("100000") }
    var banMinutes by remember { mutableStateOf("10") }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("←") }
            Text("🛡️ Moderator", style = MaterialTheme.typography.headlineMedium)
        }

        OutlinedTextField(query, { query = it; vm.search(it) },
            label = { Text("Find user") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        results.take(5).forEach { u ->
            TextButton(onClick = { target = u }) {
                Text("${u.displayName} (#${u.id})" + if (u.vipTier > 0) " VIP${u.vipTier}" else "")
            }
        }

        target?.let { t ->
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Target: ${t.displayName} (#${t.id})",
                        style = MaterialTheme.typography.titleMedium, color = Amber)

                    Text("Gift VIP", style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        (1..5).forEach { tier ->
                            Button(onClick = { vm.giftVip(t.id, tier) },
                                contentPadding = PaddingValues(horizontal = 10.dp)) { Text("V$tier") }
                        }
                    }

                    Text("Gift coins", style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(coins, { coins = it.filter(Char::isDigit) },
                            singleLine = true, modifier = Modifier.weight(1f))
                        Button(onClick = { coins.toLongOrNull()?.let { vm.giftCoins(t.id, it) } }) {
                            Text("Gift")
                        }
                    }

                    Text("Ban", style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(banMinutes, { banMinutes = it.filter(Char::isDigit) },
                            label = { Text("minutes") }, singleLine = true,
                            modifier = Modifier.weight(1f))
                        Button(onClick = { banMinutes.toIntOrNull()?.let { vm.ban(t.id, it) } }) {
                            Text("Timed")
                        }
                        Button(onClick = { vm.ban(t.id, null) },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.error)) { Text("Perm") }
                    }
                    TextButton(onClick = { vm.unban(t.id) }) { Text("Lift ban") }
                }
            }
        }

        Text("Open reports (${reports.size})", style = MaterialTheme.typography.titleMedium)
        reports.forEach { r ->
            Card {
                Row(Modifier.fillMaxWidth().padding(12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("${r.reporter} → ${r.reported}", style = MaterialTheme.typography.bodyMedium)
                        Text(r.reason + (r.note?.let { " — $it" } ?: ""),
                            style = MaterialTheme.typography.bodySmall)
                    }
                    TextButton(onClick = { vm.resolve(r.id) }) { Text("Resolve") }
                }
            }
        }
    }
    notice?.let {
        LaunchedEffect(it) { kotlinx.coroutines.delay(2000); vm.dismiss() }
        Snackbar(Modifier.padding(8.dp)) { Text(it) }
    }
}
