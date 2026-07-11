package com.mdyusufahmed.velocity.ui.about

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mdyusufahmed.velocity.data.OddsSlotDto
import com.mdyusufahmed.velocity.data.VelocityApi
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

// TODO(M13): replace with Yusuf's real Buy Me a Coffee URL.
const val COFFEE_URL = "https://buymeacoffee.com/"

@HiltViewModel
class AboutViewModel @Inject constructor(private val api: VelocityApi) : ViewModel() {
    val odds = MutableStateFlow<List<OddsSlotDto>?>(null)

    init {
        viewModelScope.launch { runCatching { api.odds() }.onSuccess { odds.value = it } }
    }
}

@Composable
fun AboutScreen(vm: AboutViewModel = hiltViewModel()) {
    val odds by vm.odds.collectAsState()
    val context = LocalContext.current

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("About Velocity", style = MaterialTheme.typography.headlineMedium)

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Free means free", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Velocity has no store, no ads, and no in-app purchases. Coins can never " +
                    "be bought, sold, cashed out, or transferred. Nothing of monetary value " +
                    "is ever wagered or won. VIP is earned by playing — never bought.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("The odds favor YOU", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Every slot returns ~113.6% to players over time — the opposite of a " +
                    "house edge. A winning bet pays stake + stake × multiplier. With payout " +
                    "(m+1)×stake, equal RTP r needs Σ r/(mᵢ+1) = 1, so r = 1/0.880277 ≈ 1.1360. " +
                    "This is the live table the server is using right now:",
                    style = MaterialTheme.typography.bodySmall,
                )
                when (val o = odds) {
                    null -> Text("Loading live odds…")
                    else -> o.forEach { s ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(s.name)
                            Text("x${s.multiplier}   ${"%.3f".format(s.probability * 100)}%" +
                                 "   RTP ${"%.1f".format(s.rtp * 100)}%")
                        }
                    }
                }
                Text(
                    "Every round is provably fair: the result's hash is published before " +
                    "betting closes and the seed is revealed after — verify any round in " +
                    "Round History.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Support the server", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Velocity runs on one home computer. If you enjoy it, you can buy the " +
                    "developer a coffee — entirely optional, and it never buys anything in-game.",
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedButton(onClick = {
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(COFFEE_URL)))
                }) { Text("☕ Buy me a coffee") }
            }
        }

        Text(
            "Velocity is a fan-made free game and is not affiliated with, sponsored, or " +
            "endorsed by any car manufacturer. All brand names are property of their " +
            "respective owners.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
