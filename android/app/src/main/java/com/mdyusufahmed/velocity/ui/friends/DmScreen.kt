package com.mdyusufahmed.velocity.ui.friends

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mdyusufahmed.velocity.data.DmRepository
import com.mdyusufahmed.velocity.data.db.MessageEntity
import com.mdyusufahmed.velocity.ui.theme.NeonBlue
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
class DmViewModel @Inject constructor(
    private val dms: DmRepository,
    savedState: SavedStateHandle,
) : ViewModel() {
    val peerId: Long = savedState.get<String>("peerId")?.toLongOrNull() ?: 0
    val peerName: String = java.net.URLDecoder.decode(
        savedState.get<String>("peerName") ?: "?", "UTF-8")
    val messages = dms.conversation(peerId)
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList<MessageEntity>())

    fun send(text: String) = dms.send(peerId, peerName, text)
}

@Composable
fun DmScreen(onBack: () -> Unit, vm: DmViewModel = hiltViewModel()) {
    val messages by vm.messages.collectAsState()
    var input by remember { mutableStateOf("") }

    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("←") }
            Text(vm.peerName, style = MaterialTheme.typography.titleLarge)
        }
        Text("Messages are stored only on your device. Reinstalling the app or " +
             "switching phones clears your chat history.",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.outline)

        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp),
            reverseLayout = true) {
            items(messages.reversed()) { m ->
                Row(Modifier.fillMaxWidth(),
                    horizontalArrangement = if (m.mine) Arrangement.End else Arrangement.Start) {
                    Column(horizontalAlignment = if (m.mine) Alignment.End else Alignment.Start) {
                        Box(
                            Modifier.clip(RoundedCornerShape(12.dp))
                                .background(if (m.mine) NeonBlue.copy(alpha = 0.25f)
                                            else MaterialTheme.colorScheme.surface)
                                .padding(horizontal = 12.dp, vertical = 6.dp)
                        ) { Text(m.text, style = MaterialTheme.typography.bodyMedium) }
                        if (m.mine) Text(
                            when (m.state) {
                                "sending" -> "…"
                                "queued" -> "✓ delivers when they're online"
                                "delivered" -> "✓✓"
                                else -> "⚠ not sent"
                            },
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.outline)
                    }
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(input, { input = it }, placeholder = { Text("Message…") },
                singleLine = true, modifier = Modifier.weight(1f))
            Button(onClick = { vm.send(input); input = "" }, enabled = input.isNotBlank()) {
                Text("Send")
            }
        }
    }
}
